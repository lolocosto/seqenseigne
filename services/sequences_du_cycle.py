"""services/sequences_du_cycle.py — R3.

CRUD des séquences du cycle. S'appuie sur la table `sequences_du_cycle`
créée au chantier R1.

Règles métier :
  - Le code est unique dans un cycle (format libre mais typiquement 'S01'..'S14')
  - Le numéro est unique dans un cycle (entier positif)
  - Le nom est une chaîne libre non vide
  - Le rattachement à un thème est optionnel (theme_id nullable)
  - Si un thème est renseigné, il doit exister dans le même cycle
  - Suppression refusée si la séquence est référencée par des atomes
    vivants (objectifs, méthodes, notions, exercices via leur colonne
    `sequence`) ou par des sequences_par_niveau (FK réelle à terme).
    Aujourd'hui on détecte la présence de chaînes correspondantes
    dans les colonnes texte `sequence` des atomes.
"""

from __future__ import annotations
import sqlite3

from persistence.ids import nouveau_id_sequence_du_cycle


# ── Exceptions ───────────────────────────────────────────────────────────────

class SequenceErreur(Exception):
    """Erreur métier sur les séquences du cycle."""
    def __init__(self, message: str, code: str = "erreur"):
        super().__init__(message)
        self.code = code


class SequenceIntrouvable(SequenceErreur):
    def __init__(self, seq_id: str):
        super().__init__(
            f"Séquence introuvable : {seq_id}",
            "sequence_introuvable"
        )


class SequenceDoublonCode(SequenceErreur):
    def __init__(self, code: str):
        super().__init__(
            f"Une séquence avec le code '{code}' existe déjà dans ce cycle",
            "doublon_code"
        )


class SequenceDoublonNumero(SequenceErreur):
    def __init__(self, numero: int):
        super().__init__(
            f"Une séquence avec le numéro {numero} existe déjà dans ce cycle",
            "doublon_numero"
        )


class SequenceThemeInvalide(SequenceErreur):
    def __init__(self, theme_id: str):
        super().__init__(
            f"Thème '{theme_id}' inconnu ou dans un autre cycle",
            "theme_invalide"
        )


class SequenceEnUsage(SequenceErreur):
    def __init__(self, details: dict):
        total = sum(details.values())
        parties = ", ".join(f"{n} {k}" for k, n in details.items() if n > 0)
        super().__init__(
            f"Séquence référencée par {total} atome(s) vivant(s) : {parties}. "
            "Suppression refusée.",
            "en_usage"
        )
        self.details = details


class CycleIntrouvable(SequenceErreur):
    def __init__(self, cycle_code: str):
        super().__init__(
            f"Cycle introuvable : {cycle_code}",
            "cycle_introuvable"
        )


# ── Helpers internes ─────────────────────────────────────────────────────────

def _valider_donnees(
    code: str | None,
    numero: int | None,
    nom: str | None,
) -> None:
    if not code or not code.strip():
        raise SequenceErreur("Code obligatoire", "code_vide")
    if numero is None:
        raise SequenceErreur("Numéro obligatoire", "numero_vide")
    try:
        numero_int = int(numero)
    except (TypeError, ValueError):
        raise SequenceErreur("Numéro non numérique", "numero_invalide")
    if numero_int <= 0:
        raise SequenceErreur("Numéro doit être positif", "numero_invalide")
    if not nom or not nom.strip():
        raise SequenceErreur("Nom obligatoire", "nom_vide")


def _lire_sequence_ou_404(conn: sqlite3.Connection, seq_id: str) -> sqlite3.Row:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM sequences_du_cycle WHERE id = ?", (seq_id,)
    ).fetchone()
    if not row:
        raise SequenceIntrouvable(seq_id)
    return row


def _verifier_theme(
    conn: sqlite3.Connection,
    cycle_code: str,
    theme_id: str | None,
) -> None:
    """Vérifie que si theme_id est fourni, le thème existe dans ce cycle."""
    if theme_id is None or theme_id == "":
        return
    row = conn.execute(
        "SELECT id FROM themes WHERE id = ? AND cycle_code = ?",
        (theme_id, cycle_code)
    ).fetchone()
    if not row:
        raise SequenceThemeInvalide(theme_id)


def _compter_atomes_rattaches(
    conn: sqlite3.Connection,
    seq_code: str,
) -> dict[str, int]:
    """
    Compte les atomes vivants qui référencent une séquence via leur
    colonne texte `sequence`. Ignore le niveau — une séquence du cycle
    est partagée par tous les niveaux.

    Retourne {'objectifs': N, 'methodes': N, 'notions': N, 'exercices': N}
    """
    return {
        "objectifs":  int(conn.execute(
            # v0.14.6.b.1 — Lecture v2 via JOIN partie → sequence_par_niveau.
            # On compte les objectifs v2 rattachés à toute partie d'une
            # sequence_par_niveau dont le sequence_code matche. Comme une
            # séquence du cycle peut exister dans plusieurs niveaux, on
            # additionne (cohérent avec le comportement v1 qui ignorait
            # le niveau).
            "SELECT COUNT(*) FROM objectifs ov2 "
            "JOIN sequence_parties      p  ON p.id  = ov2.partie_id "
            "JOIN sequences_par_niveau  sn ON sn.id = p.sequence_par_niveau_id "
            "WHERE sn.sequence_code = ?",
            (seq_code,)
        ).fetchone()[0]),
        "methodes":   int(conn.execute(
            "SELECT COUNT(*) FROM methodes WHERE sequence = ?",
            (seq_code,)
        ).fetchone()[0]),
        "notions":    int(conn.execute(
            "SELECT COUNT(*) FROM notions WHERE sequence = ?",
            (seq_code,)
        ).fetchone()[0]),
        "exercices":  int(conn.execute(
            "SELECT COUNT(*) FROM exercices WHERE sequence = ?",
            (seq_code,)
        ).fetchone()[0]),
    }


# ── CRUD ─────────────────────────────────────────────────────────────────────

def creer_sequence(
    conn: sqlite3.Connection,
    cycle_code: str,
    code: str,
    numero: int,
    nom: str,
    theme_id: str | None = None,
) -> dict:
    """Crée une séquence dans le cycle donné."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    _valider_donnees(code, numero, nom)
    code   = code.strip()
    numero = int(numero)
    nom    = nom.strip()

    # Cycle existe ?
    cyc = conn.execute(
        "SELECT code FROM cycles WHERE code = ?", (cycle_code,)
    ).fetchone()
    if not cyc:
        raise CycleIntrouvable(cycle_code)

    # Unicité code
    if conn.execute(
        "SELECT id FROM sequences_du_cycle WHERE cycle_code = ? AND code = ?",
        (cycle_code, code)
    ).fetchone():
        raise SequenceDoublonCode(code)

    # Unicité numéro
    if conn.execute(
        "SELECT id FROM sequences_du_cycle WHERE cycle_code = ? AND numero = ?",
        (cycle_code, numero)
    ).fetchone():
        raise SequenceDoublonNumero(numero)

    # Thème valide ?
    _verifier_theme(conn, cycle_code, theme_id)

    seq_id = nouveau_id_sequence_du_cycle()
    conn.execute(
        "INSERT INTO sequences_du_cycle "
        "(id, cycle_code, code, numero, nom, theme_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (seq_id, cycle_code, code, numero, nom, theme_id or None)
    )
    conn.commit()
    return dict(_lire_sequence_ou_404(conn, seq_id))


def modifier_sequence(
    conn: sqlite3.Connection,
    seq_id: str,
    code: str | None = None,
    numero: int | None = None,
    nom: str | None = None,
    theme_id: str | None = None,
    detacher_theme: bool = False,
) -> dict:
    """
    Modification partielle. Les champs `None` sont ignorés.

    Pour **détacher** un thème (mettre theme_id à NULL), passer
    `detacher_theme=True` (on ne peut pas distinguer "ne pas modifier"
    d'"effacer" avec juste theme_id=None).
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    actuel = _lire_sequence_ou_404(conn, seq_id)
    cycle_code = actuel["cycle_code"]

    nouveau_code = code.strip() if code is not None else actuel["code"]
    nouveau_nom  = nom.strip() if nom is not None else actuel["nom"]
    nouveau_num  = int(numero) if numero is not None else actuel["numero"]

    _valider_donnees(nouveau_code, nouveau_num, nouveau_nom)

    # Unicité code (en excluant la ligne courante)
    if nouveau_code != actuel["code"]:
        r = conn.execute(
            "SELECT id FROM sequences_du_cycle "
            "WHERE cycle_code = ? AND code = ? AND id <> ?",
            (cycle_code, nouveau_code, seq_id)
        ).fetchone()
        if r:
            raise SequenceDoublonCode(nouveau_code)

    # Unicité numéro
    if nouveau_num != actuel["numero"]:
        r = conn.execute(
            "SELECT id FROM sequences_du_cycle "
            "WHERE cycle_code = ? AND numero = ? AND id <> ?",
            (cycle_code, nouveau_num, seq_id)
        ).fetchone()
        if r:
            raise SequenceDoublonNumero(nouveau_num)

    # Thème
    if detacher_theme:
        nouveau_theme = None
    elif theme_id is not None:
        _verifier_theme(conn, cycle_code, theme_id)
        nouveau_theme = theme_id or None
    else:
        nouveau_theme = actuel["theme_id"]

    conn.execute(
        "UPDATE sequences_du_cycle "
        "SET code = ?, numero = ?, nom = ?, theme_id = ? "
        "WHERE id = ?",
        (nouveau_code, nouveau_num, nouveau_nom, nouveau_theme, seq_id)
    )
    conn.commit()
    return dict(_lire_sequence_ou_404(conn, seq_id))


def supprimer_sequence(conn: sqlite3.Connection, seq_id: str) -> dict:
    """
    Supprime une séquence. Refusée si des atomes vivants la référencent.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    actuel = _lire_sequence_ou_404(conn, seq_id)
    details = _compter_atomes_rattaches(conn, actuel["code"])
    if sum(details.values()) > 0:
        raise SequenceEnUsage(details)

    conn.execute("DELETE FROM sequences_du_cycle WHERE id = ?", (seq_id,))
    conn.commit()
    return {"supprime": True, "id": seq_id}


def lire_sequence(conn: sqlite3.Connection, seq_id: str) -> dict:
    """Retourne une séquence enrichie : theme_code, theme_nom, compteurs atomes."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    row = conn.execute("""
        SELECT s.id, s.cycle_code, s.code, s.numero, s.nom, s.theme_id,
               t.code AS theme_code, t.nom AS theme_nom,
               t.code_couleur AS theme_couleur
        FROM sequences_du_cycle s
        LEFT JOIN themes t ON t.id = s.theme_id
        WHERE s.id = ?
    """, (seq_id,)).fetchone()
    if not row:
        raise SequenceIntrouvable(seq_id)
    d = dict(row)
    d["atomes"] = _compter_atomes_rattaches(conn, d["code"])
    d["nb_atomes_total"] = sum(d["atomes"].values())
    return d


def lister_sequences(
    conn: sqlite3.Connection,
    cycle_code: str,
) -> list[dict]:
    """
    Liste toutes les séquences d'un cycle, triées par numéro croissant,
    enrichies avec le thème et les compteurs d'atomes.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT s.id, s.cycle_code, s.code, s.numero, s.nom, s.theme_id,
               t.code AS theme_code, t.nom AS theme_nom,
               t.code_couleur AS theme_couleur
        FROM sequences_du_cycle s
        LEFT JOIN themes t ON t.id = s.theme_id
        WHERE s.cycle_code = ?
        ORDER BY s.numero
    """, (cycle_code,)).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["atomes"] = _compter_atomes_rattaches(conn, d["code"])
        d["nb_atomes_total"] = sum(d["atomes"].values())
        result.append(d)
    return result
