"""services/themes.py — R2.

CRUD des thèmes du cycle. S'appuie sur la table `themes` créée au
chantier R1.

Règles métier :
  - Le code est unique dans un cycle
  - Le nom est unique dans un cycle
  - Suppression refusée si des séquences du cycle pointent sur le thème
    (même si techniquement la FK est en ON DELETE SET NULL, on garde
    la main sur la suppression explicite)
  - Le code couleur doit être un slug connu (voir services/couleurs_themes.py)
  - La description est un texte LaTeX brut, aucune validation syntaxique
"""

from __future__ import annotations
import sqlite3

from persistence.ids import nouveau_id_theme
from services.couleurs_themes import slugs_valides


# ── Exceptions ───────────────────────────────────────────────────────────────

class ThemeErreur(Exception):
    """Erreur métier sur les thèmes."""
    def __init__(self, message: str, code: str = "erreur"):
        super().__init__(message)
        self.code = code


class ThemeIntrouvable(ThemeErreur):
    def __init__(self, theme_id: str):
        super().__init__(f"Thème introuvable : {theme_id}", "theme_introuvable")


class ThemeDoublonCode(ThemeErreur):
    def __init__(self, code: str):
        super().__init__(
            f"Un thème avec le code '{code}' existe déjà dans ce cycle",
            "doublon_code"
        )


class ThemeDoublonNom(ThemeErreur):
    def __init__(self, nom: str):
        super().__init__(
            f"Un thème avec le nom '{nom}' existe déjà dans ce cycle",
            "doublon_nom"
        )


class ThemeCouleurInvalide(ThemeErreur):
    def __init__(self, slug: str):
        super().__init__(
            f"Code couleur inconnu : '{slug}'",
            "couleur_invalide"
        )


class ThemeEnUsage(ThemeErreur):
    def __init__(self, nb_sequences: int):
        super().__init__(
            f"Thème rattaché à {nb_sequences} séquence(s), suppression refusée",
            "en_usage"
        )


class CycleIntrouvable(ThemeErreur):
    def __init__(self, cycle_code: str):
        super().__init__(
            f"Cycle introuvable : {cycle_code}",
            "cycle_introuvable"
        )


# ── Helpers internes ─────────────────────────────────────────────────────────

def _valider_donnees(
    code: str | None,
    nom: str | None,
    code_couleur: str | None,
) -> None:
    """Vérifie les champs non-vides et le code_couleur si fourni."""
    if not code or not code.strip():
        raise ThemeErreur("Code obligatoire", "code_vide")
    if not nom or not nom.strip():
        raise ThemeErreur("Nom obligatoire", "nom_vide")
    if code_couleur and code_couleur not in slugs_valides():
        raise ThemeCouleurInvalide(code_couleur)


def _lire_theme_ou_404(conn: sqlite3.Connection, theme_id: str) -> sqlite3.Row:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM themes WHERE id = ?", (theme_id,)
    ).fetchone()
    if not row:
        raise ThemeIntrouvable(theme_id)
    return row


def _compter_sequences(conn: sqlite3.Connection, theme_id: str) -> int:
    n = conn.execute(
        "SELECT COUNT(*) FROM sequences_du_cycle WHERE theme_id = ?",
        (theme_id,)
    ).fetchone()[0]
    return int(n)


# ── CRUD ─────────────────────────────────────────────────────────────────────

def creer_theme(
    conn: sqlite3.Connection,
    cycle_code: str,
    code: str,
    nom: str,
    code_couleur: str = "",
    description: str = "",
    ordre: int | None = None,
) -> dict:
    """
    Crée un thème dans le cycle donné.

    `ordre` : si None, placé en fin de liste (max(ordre) + 1).

    Retourne le thème créé.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    _valider_donnees(code, nom, code_couleur)
    code = code.strip()
    nom  = nom.strip()

    # Cycle existe ?
    cyc = conn.execute(
        "SELECT code FROM cycles WHERE code = ?", (cycle_code,)
    ).fetchone()
    if not cyc:
        raise CycleIntrouvable(cycle_code)

    # Doublons ?
    existant = conn.execute(
        "SELECT id, code, nom FROM themes WHERE cycle_code = ? AND code = ?",
        (cycle_code, code)
    ).fetchone()
    if existant:
        raise ThemeDoublonCode(code)

    existant = conn.execute(
        "SELECT id, code, nom FROM themes WHERE cycle_code = ? AND nom = ?",
        (cycle_code, nom)
    ).fetchone()
    if existant:
        raise ThemeDoublonNom(nom)

    # Ordre auto si absent
    if ordre is None:
        ordre = (conn.execute(
            "SELECT COALESCE(MAX(ordre), 0) + 1 "
            "FROM themes WHERE cycle_code = ?",
            (cycle_code,)
        ).fetchone()[0]) or 1

    theme_id = nouveau_id_theme()
    conn.execute(
        "INSERT INTO themes "
        "(id, cycle_code, code, nom, code_couleur, description, ordre) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (theme_id, cycle_code, code, nom, code_couleur or "",
         description or "", ordre)
    )
    conn.commit()
    return dict(_lire_theme_ou_404(conn, theme_id))


def modifier_theme(
    conn: sqlite3.Connection,
    theme_id: str,
    code: str | None = None,
    nom: str | None = None,
    code_couleur: str | None = None,
    description: str | None = None,
    ordre: int | None = None,
) -> dict:
    """
    Modification partielle d'un thème. Seuls les champs passés en
    argument sont modifiés. Les `None` sont ignorés.

    Retourne le thème mis à jour.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    actuel = _lire_theme_ou_404(conn, theme_id)
    cycle_code = actuel["cycle_code"]

    # Valider les nouveaux champs
    nouveau_code = code.strip() if code is not None else actuel["code"]
    nouveau_nom  = nom.strip() if nom is not None else actuel["nom"]
    nouvelle_couleur = (
        code_couleur if code_couleur is not None else actuel["code_couleur"]
    )
    _valider_donnees(nouveau_code, nouveau_nom, nouvelle_couleur)

    # Doublons (en excluant le thème courant)
    if nouveau_code != actuel["code"]:
        r = conn.execute(
            "SELECT id FROM themes WHERE cycle_code = ? AND code = ? AND id <> ?",
            (cycle_code, nouveau_code, theme_id)
        ).fetchone()
        if r:
            raise ThemeDoublonCode(nouveau_code)
    if nouveau_nom != actuel["nom"]:
        r = conn.execute(
            "SELECT id FROM themes WHERE cycle_code = ? AND nom = ? AND id <> ?",
            (cycle_code, nouveau_nom, theme_id)
        ).fetchone()
        if r:
            raise ThemeDoublonNom(nouveau_nom)

    nouvelle_description = (
        description if description is not None else actuel["description"]
    )
    nouvel_ordre = ordre if ordre is not None else actuel["ordre"]

    conn.execute(
        "UPDATE themes "
        "SET code = ?, nom = ?, code_couleur = ?, description = ?, ordre = ? "
        "WHERE id = ?",
        (nouveau_code, nouveau_nom, nouvelle_couleur or "",
         nouvelle_description or "", nouvel_ordre, theme_id)
    )
    conn.commit()
    return dict(_lire_theme_ou_404(conn, theme_id))


def supprimer_theme(conn: sqlite3.Connection, theme_id: str) -> dict:
    """
    Supprime un thème. Refusé si des séquences du cycle y sont rattachées.

    Retourne un rapport {supprime: True, nb_sequences_check: N}.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    _ = _lire_theme_ou_404(conn, theme_id)  # 404 si absent
    n = _compter_sequences(conn, theme_id)
    if n > 0:
        raise ThemeEnUsage(n)

    conn.execute("DELETE FROM themes WHERE id = ?", (theme_id,))
    conn.commit()
    return {"supprime": True, "id": theme_id}


def lire_theme(conn: sqlite3.Connection, theme_id: str) -> dict:
    """Retourne un thème avec un champ supplémentaire `nb_sequences`."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    row = _lire_theme_ou_404(conn, theme_id)
    d = dict(row)
    d["nb_sequences"] = _compter_sequences(conn, theme_id)
    return d


def lister_themes_avec_compteurs(
    conn: sqlite3.Connection,
    cycle_code: str,
) -> list[dict]:
    """
    Liste tous les thèmes d'un cycle avec pour chacun le nombre de
    séquences rattachées.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT t.id, t.cycle_code, t.code, t.nom, t.code_couleur,
               t.description, t.ordre,
               COUNT(s.id) AS nb_sequences
        FROM themes t
        LEFT JOIN sequences_du_cycle s ON s.theme_id = t.id
        WHERE t.cycle_code = ?
        GROUP BY t.id
        ORDER BY t.ordre, t.code
    """, (cycle_code,)).fetchall()
    return [dict(r) for r in rows]
