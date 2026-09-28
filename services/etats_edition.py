"""services/etats_edition.py — v0.13.6.8.2

Gestion de l'état d'édition des atomes pédagogiques.

Modèle simple :
  - Une table `etats_edition` énumère les états possibles avec un code,
    un nom affichable, un ordre de tri et un flag `est_final`.
  - Chaque atome porte une colonne `etat_code` qui pointe (sans FK
    formelle pour rester souple) vers un code d'état.
  - Le seul état avec `est_final=1` est `valide` ; il autorise la
    génération de PDF "définitifs" (sans filigrane ÉPREUVE).
  - Les transitions sont manuelles et libres — pas de machine à états
    pour la plupart des types.

Validation pédagogique (v0.13.6.8.2) :
  - Au passage `→ 'valide'`, un hook optionnel par type peut effectuer
    des contrôles métier supplémentaires et lever
    `ValidationPedagogiqueErreur` avec des raisons listées.
  - Le registre `HOOKS_VALIDATION_PEDAGOGIQUE` est peuplé par les
    services métier (ex: cartes_automatisme enregistre son hook au
    chargement du module).
  - Si pas de hook pour un type, la transition est libre.

API publique :
  - lister_etats(conn) → liste ordonnée
  - lire_etat_atome(conn, type_atome, atome_id) → code
  - changer_etat_atome(conn, type_atome, atome_id, nouvel_etat_code)
  - enregistrer_hook_validation(type_atome, hook) — appelée à
    l'initialisation du service métier qui fournit le hook
"""

from __future__ import annotations

from typing import Callable


# Mapping type_atome → nom de table. Codé ici pour éviter un dispatch
# à plusieurs endroits ; centralisé.
#
# v0.13.6.8.2 : ajout de 'carte' pour unifier le mécanisme d'état (la
# carte avait avant ses propres routes /valider et /devalider, supprimées).
TABLES_ATOMES = {
    "notion":       "notions",
    "methode":      "methodes",
    "exercice":     "exercices",
    "fiche_resume": "fiches_resume",  # v0.10.5
    "carte":        "cartes_automatisme",  # v0.13.6.8.2
}


# Registre des hooks de validation pédagogique au passage → 'valide'.
# Peuplé par enregistrer_hook_validation() depuis les services métier.
# Signature : hook(conn, atome_id) -> None  (lève ValidationPedagogiqueErreur
# en cas d'échec).
HOOKS_VALIDATION_PEDAGOGIQUE: dict[str, Callable] = {}


def enregistrer_hook_validation(type_atome: str, hook: Callable) -> None:
    """Enregistre un hook de validation pédagogique pour un type d'atome.

    Le hook reçoit (conn, atome_id) et doit lever
    ValidationPedagogiqueErreur si la validation échoue. Sinon, ne rien
    faire (l'UPDATE de l'état sera effectué par changer_etat_atome).

    Appelée typiquement au chargement du module métier qui définit le hook.
    """
    if type_atome not in TABLES_ATOMES:
        raise TypeAtomeInvalide(type_atome)
    HOOKS_VALIDATION_PEDAGOGIQUE[type_atome] = hook


class EtatEditionErreur(Exception):
    """Erreur de domaine pour les opérations sur les états d'édition."""
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class TypeAtomeInvalide(EtatEditionErreur):
    def __init__(self, type_atome):
        super().__init__(
            f"Type d'atome invalide : {type_atome!r}. "
            f"Attendu parmi {sorted(TABLES_ATOMES.keys())}.",
            "type_atome_invalide",
            type_atome=type_atome,
        )


class AtomeIntrouvable(EtatEditionErreur):
    def __init__(self, type_atome, atome_id):
        super().__init__(
            f"Atome {type_atome}/{atome_id} introuvable.",
            "atome_introuvable",
            type_atome=type_atome, atome_id=atome_id,
        )


class EtatInconnu(EtatEditionErreur):
    def __init__(self, etat_code):
        super().__init__(
            f"État d'édition inconnu : {etat_code!r}. Voir la table "
            f"etats_edition pour la liste des codes valides.",
            "etat_inconnu",
            etat_code=etat_code,
        )


class ValidationPedagogiqueErreur(EtatEditionErreur):
    """Levée par un hook de validation pédagogique au passage → 'valide'.

    `raisons` est une liste de chaînes décrivant les contrôles qui ont
    échoué. Affichée à l'utilisateur dans un toast ou modal.
    """
    def __init__(self, message: str, raisons: list[str], **details):
        super().__init__(
            message,
            "validation_pedagogique_echec",
            raisons=raisons, **details,
        )


class ItemVerrouille(EtatEditionErreur):
    """v0.16.4 — Levée quand on tente de MODIFIER le contenu d'un item
    (atome ou évaluation) qui est en état 'valide'.

    Un item validé est en lecture seule : il faut explicitement le repasser
    en 'en_cours' (route de changement d'état) pour le modifier, puis
    revalider. Cela garantit que la validation certifie réellement la
    cohérence de l'item (barèmes, complétude…) et qu'on ne peut pas la
    contourner après coup.

    Traduite en HTTP 409 Conflict par les routes (code 'item_verrouille').
    NB : la SUPPRESSION d'un item validé reste autorisée (après confirmation
    côté UI) — seules les modifications de contenu sont refusées.
    """
    def __init__(self, type_item: str, item_id: str):
        super().__init__(
            f"L'item {type_item}/{item_id} est validé (lecture seule). "
            f"Repassez-le en cours pour le modifier.",
            "item_verrouille",
            type_item=type_item, item_id=item_id,
        )


def _table_pour(type_atome: str) -> str:
    """Résout le type d'atome vers son nom de table SQL."""
    if type_atome not in TABLES_ATOMES:
        raise TypeAtomeInvalide(type_atome)
    return TABLES_ATOMES[type_atome]


def lister_etats(conn) -> list[dict]:
    """Retourne la liste des états d'édition triés par ordre.

    Format : [{"code", "nom", "ordre", "est_final"}, ...]
    """
    rows = conn.execute(
        "SELECT code, nom, ordre, est_final FROM etats_edition "
        "ORDER BY ordre, code"
    ).fetchall()
    return [
        {
            "code":      r["code"],
            "nom":       r["nom"],
            "ordre":     r["ordre"],
            "est_final": bool(r["est_final"]),
        }
        for r in rows
    ]


def lire_etat_atome(conn, type_atome: str, atome_id: str) -> str:
    """Retourne le code d'état de l'atome.

    Lève AtomeIntrouvable si l'atome n'existe pas.
    """
    table = _table_pour(type_atome)
    row = conn.execute(
        f"SELECT etat_code FROM {table} WHERE id = ?",
        (atome_id,),
    ).fetchone()
    if row is None:
        raise AtomeIntrouvable(type_atome, atome_id)
    return row["etat_code"] or "en_cours"


def assert_atome_modifiable(conn, type_atome: str, atome_id: str) -> None:
    """v0.16.4 — Lève ItemVerrouille si l'atome est en état 'valide'.

    À appeler en garde au début de toute route/service qui MODIFIE le
    contenu d'un atome (PATCH champ, ajout/retrait de composant). Ne PAS
    appeler sur la route de changement d'état (qui doit pouvoir dévalider)
    ni sur la suppression (autorisée après confirmation UI).

    Si l'atome est introuvable, on laisse passer (la couche appelante
    renverra son propre 404) : on ne veut pas masquer un 404 par un 409.
    """
    try:
        etat = lire_etat_atome(conn, type_atome, atome_id)
    except AtomeIntrouvable:
        return
    if etat == "valide":
        raise ItemVerrouille(type_atome, atome_id)


def changer_etat_atome(
    conn, type_atome: str, atome_id: str, nouvel_etat_code: str,
) -> dict:
    """Change l'état d'édition d'un atome.

    Validations :
      - type_atome ∈ TABLES_ATOMES → sinon TypeAtomeInvalide
      - atome existant en BDD → sinon AtomeIntrouvable
      - nouvel_etat_code ∈ etats_edition → sinon EtatInconnu
      - si transition → 'valide' et hook enregistré pour type_atome,
        le hook est exécuté (peut lever ValidationPedagogiqueErreur)

    Effets :
      - UPDATE de la colonne `etat_code`
      - mise à jour de `mtime = CURRENT_TIMESTAMP` (toutes les tables
        atomes ont cette colonne, ajoutée par migration v0.13.5.2 puis
        unifiée v0.13.6.8.2)

    Retourne {"type_atome", "atome_id", "etat_code"} après mise à jour.

    Note : pas de garde sur la transition côté étape. L'enseignant peut
    librement passer d'un état à l'autre, dans n'importe quel sens — la
    seule contrainte est le hook de validation pédagogique au passage
    → 'valide' (si défini).
    """
    table = _table_pour(type_atome)

    # Vérifier que l'atome existe
    row = conn.execute(
        f"SELECT 1 FROM {table} WHERE id = ?", (atome_id,),
    ).fetchone()
    if row is None:
        raise AtomeIntrouvable(type_atome, atome_id)

    # Vérifier que le code d'état existe
    row = conn.execute(
        "SELECT 1 FROM etats_edition WHERE code = ?",
        (nouvel_etat_code,),
    ).fetchone()
    if row is None:
        raise EtatInconnu(nouvel_etat_code)

    # Hook de validation pédagogique au passage → 'valide'
    if nouvel_etat_code == 'valide':
        hook = HOOKS_VALIDATION_PEDAGOGIQUE.get(type_atome)
        if hook is not None:
            # Le hook lève ValidationPedagogiqueErreur en cas d'échec.
            # On laisse remonter — la route HTTP le traduira en 400 avec
            # details.raisons.
            hook(conn, atome_id)

    conn.execute(
        f"UPDATE {table} SET etat_code = ?, "
        f"mtime = CURRENT_TIMESTAMP WHERE id = ?",
        (nouvel_etat_code, atome_id),
    )
    return {
        "type_atome": type_atome,
        "atome_id":   atome_id,
        "etat_code":  nouvel_etat_code,
    }


def compter_atomes_par_etat(conn) -> dict:
    """Diagnostic — retourne le nombre d'atomes par (type, etat).

    Format : {"notion": {"en_cours": 12, "valide": 5}, "methode": ...}.
    Utile pour les vues de récap en admin et pour les tests.

    Tolérant aux tables manquantes (cas test sandbox) : un type dont la
    table n'existe pas est simplement omis du résultat.
    """
    rep = {}
    for type_atome, table in TABLES_ATOMES.items():
        try:
            rows = conn.execute(
                f"SELECT etat_code, COUNT(*) AS n FROM {table} "
                f"GROUP BY etat_code"
            ).fetchall()
        except Exception:
            # Table absente (test minimaliste, ou type non encore migré).
            continue
        rep[type_atome] = {}
        for r in rows:
            rep[type_atome][r["etat_code"] or "en_cours"] = r["n"]
    return rep
