"""
services/niveaux.py — Référentiel des niveaux de maîtrise de seqenseigne.

Point d'entrée unique pour toute l'application (back et front via /api/referentiel/niveaux).
Aucune dépendance externe : pas de Flask, pas d'I/O.

Codes valides :
    "1"  Insuffisant     — pas de travail évaluable fourni          (4 pts)
    "2"  À consolider    — série F réalisée / notes de cours prises  (10 pts)
    "3"  Satisfaisant    — précédent + série A / fiches remplies     (16 pts)
    "4"  Très bien       — précédent + série E / cours oral          (20 pts)
    "A"  Absent          — élève absent lors de l'évaluation
    "D"  Dispensé        — élève dispensé pour raison officielle
    "NE" Non évalué      — séquence non évaluée (aucun exercice déclaré
                           ou absence trop longue / dispense totale)

Anciens codes (v0.3 et antérieurs) :
    I → 1,  F → 2,  S → 3,  A → 3,  TB → 4,  E → 4,  - → A
"""

from __future__ import annotations
from typing import Optional

# ── Référentiel ────────────────────────────────────────────────────────────────

NIVEAUX: dict[str, dict] = {
    "1": {
        "libelle":    "Insuffisant",
        "libelle_court": "I",
        "points":     4,
        "couleur":    "rouge",
        "description": "Pas de travail évaluable fourni.",
        "ordre":      1,
    },
    "2": {
        "libelle":    "À consolider",
        "libelle_court": "F",
        "points":     10,
        "couleur":    "jaune",
        "description": "Série fondamentale réalisée / notes de cours prises.",
        "ordre":      2,
    },
    "3": {
        "libelle":    "Satisfaisant",
        "libelle_court": "A",
        "points":     16,
        "couleur":    "vert",
        "description": "Précédent + série avancée réalisée / fiches de résumé remplies.",
        "ordre":      3,
    },
    "4": {
        "libelle":    "Très bien",
        "libelle_court": "E",
        "points":     20,
        "couleur":    "vert_fonce",
        "description": "Précédent + série exploration réalisée / cours présenté à l'oral.",
        "ordre":      4,
    },
    "0": {
        "libelle":    "Aucune donnée",
        "libelle_court": "-",
        "points":     None,
        "couleur":    "neutre",
        "description": "Aucune donnée saisie pour cet objectif.",
        "ordre":      0,
    },
    "A": {
        "libelle":    "Absent",
        "libelle_court": "Abs",
        "points":     None,
        "couleur":    "bleu",
        "description": "Élève absent lors de l'évaluation.",
        "ordre":      5,
    },
    "D": {
        "libelle":    "Dispensé",
        "libelle_court": "Disp",
        "points":     None,
        "couleur":    "bleu",
        "description": "Élève dispensé pour raison officielle.",
        "ordre":      6,
    },
    "NE": {
        "libelle":    "Non évalué",
        "libelle_court": "NE",
        "points":     None,
        "couleur":    "blanc",
        "description": "Séquence non évaluée pour cet élève.",
        "ordre":      7,
    },
}

# Codes qui contribuent à une moyenne (points non None)
CODES_NOTES = {"1", "2", "3", "4"}

# Codes qui indiquent une absence totale de travail évaluable
CODES_SANS_NOTE = {"0", "A", "D", "NE"}

# Mapping anciens codes → nouveaux codes
# Couvre : convention I/F/S/TB (v0.3), convention I/F/A/E (intermédiaire),
# et le tiret "-" utilisé dans les CSV de suivi historiques.
MIGRATION_CODES: dict[str, str] = {
    # Convention I/F/S/TB (ancienne)
    "I":  "1",
    "F":  "2",
    "S":  "3",
    "TB": "4",
    # Convention I/F/A/E (intermédiaire — chevauchement avec "A" = Absent)
    # "A" en ancien contexte = Satisfaisant → "3"
    # "E" en ancien contexte = Très bien    → "4"
    # Ces deux cas sont détectés par le contexte (voir migrer_ancien_code)
    "E":  "4",
    # Tiret = aucune donnée dans les CSV historiques
    "-":  "0",
    # NE reste NE
    "NE": "NE",
    # Codes déjà nouveaux (idempotent)
    "1":  "1",
    "2":  "2",
    "3":  "3",
    "4":  "4",
    "0":  "0",
    "A":  "A",
    "D":  "D",
}

# Note : "A" dans l'ancienne convention signifiait "Satisfaisant" (=3),
# mais "A" dans la nouvelle convention signifie "Absent".
# La fonction migrer_ancien_code gère ce cas via le paramètre `contexte`.


# ── Fonctions de traduction ────────────────────────────────────────────────────

def est_code_valide(code: str) -> bool:
    """Retourne True si le code est un code de niveau valide (nouvelle convention)."""
    return code in NIVEAUX


def code_vers_libelle(code: str) -> str:
    """
    Retourne le libellé complet d'un code de niveau.
    Lève ValueError si le code est inconnu.
    """
    if code not in NIVEAUX:
        raise ValueError(f"Code de niveau inconnu : {repr(code)}. "
                         f"Codes valides : {list(NIVEAUX)}")
    return NIVEAUX[code]["libelle"]


def code_vers_libelle_court(code: str) -> str:
    """Retourne le libellé court (I, F, A, E, Abs, Disp, NE)."""
    if code not in NIVEAUX:
        raise ValueError(f"Code de niveau inconnu : {repr(code)}")
    return NIVEAUX[code]["libelle_court"]


def code_vers_points(code: str) -> Optional[int]:
    """
    Retourne la valeur en points d'un code (4, 10, 16 ou 20).
    Retourne None pour A, D, NE (pas de note calculable).
    Lève ValueError si le code est inconnu.
    """
    if code not in NIVEAUX:
        raise ValueError(f"Code de niveau inconnu : {repr(code)}")
    return NIVEAUX[code]["points"]


def code_vers_info(code: str) -> dict:
    """Retourne le dict complet d'un code (libelle, points, couleur, etc.)."""
    if code not in NIVEAUX:
        raise ValueError(f"Code de niveau inconnu : {repr(code)}")
    return {"code": code, **NIVEAUX[code]}


def migrer_ancien_code(ancien: str, contexte: str = "nouveau") -> str:
    """
    Convertit un ancien code vers la nouvelle convention.

    contexte :
      "ancien_IFSATB"  — convention I/F/S/A/TB ("A" = Satisfaisant = 3)
      "ancien_IFAE"    — convention I/F/A/E ("A" = Satisfaisant = 3)
      "nouveau"        — code déjà en nouvelle convention (idempotent)
      "csv_historique" — depuis les fichiers S0Xsuivi.csv ("-" = absent,
                         "A" = Satisfaisant ancien, "NE" = non évalué)

    Lève ValueError si la migration est impossible.
    """
    code = ancien.strip()

    if contexte in ("ancien_IFSATB", "ancien_IFAE", "csv_historique"):
        # Dans ces contextes, "A" signifiait Satisfaisant → "3"
        if code == "A":
            return "3"
        if code in MIGRATION_CODES:
            return MIGRATION_CODES[code]
        raise ValueError(f"Code ancien inconnu : {repr(code)} (contexte={contexte})")

    # contexte "nouveau" : on accepte uniquement les codes déjà valides
    if code in NIVEAUX:
        return code
    raise ValueError(f"Code inconnu en contexte 'nouveau' : {repr(code)}. "
                     f"Utiliser migrer_ancien_code(code, 'csv_historique') "
                     f"pour convertir un ancien code.")


def migrer_batch(codes: dict[str, str], contexte: str = "csv_historique") -> dict[str, str]:
    """
    Migre un dictionnaire {objectif_code: ancien_code} vers les nouveaux codes.
    Retourne un dict {objectif_code: nouveau_code}.
    Les erreurs de migration sont signalées par le code "?" (non bloquant).
    """
    result = {}
    for obj_code, ancien in codes.items():
        try:
            result[obj_code] = migrer_ancien_code(ancien, contexte)
        except ValueError:
            result[obj_code] = "?"
    return result


def calculer_moyenne(codes: list[str]) -> Optional[float]:
    """
    Calcule la moyenne /20 d'une liste de codes.
    Seuls les codes avec points (1/2/3/4) contribuent.
    Retourne None si aucun code ne contribue.
    """
    points = [NIVEAUX[c]["points"] for c in codes
              if c in CODES_NOTES]
    if not points:
        return None
    return round(sum(points) / len(points), 2)


def deduire_niveau(suivi_eleve: dict, objectif: dict) -> str:
    """
    Déduit automatiquement le niveau d'un élève sur un objectif
    depuis les exercices cochés.

    suivi_eleve : { "F": [1,2,3], "A": [1], "E": [], "cours": [1,2,3] }
    objectif    : { "is01": bool, "exercices": { "fondamental": [...], ... } }

    Retourne un code nouvelle convention ("1".."4" ou "NE").
    """
    if objectif.get("is01"):
        cours = suivi_eleve.get("cours", [])
        if 1 not in cours:
            return "1"
        if 2 not in cours:
            return "2"
        if 3 not in cours:
            return "3"
        return "4"

    ex = objectif.get("exercices", {})
    has_F = bool(ex.get("fondamental") or ex.get("F"))
    has_A = bool(ex.get("avancé") or ex.get("A"))
    has_E = bool(ex.get("exploration") or ex.get("E"))

    if not has_F and not has_A and not has_E:
        return "NE"

    def tous_ok(serie_key, alt_key=None):
        nums = ex.get(serie_key) or ex.get(alt_key or serie_key, [])
        if not nums:
            return True   # série vide = non concerné, ne bloque pas
        done = suivi_eleve.get(serie_key[0].upper(), [])  # "fondamental"→"F"
        return all(n in done for n in nums)

    if not tous_ok("fondamental", "F"):
        return "1"
    if not tous_ok("avancé", "A"):
        return "2"
    if not tous_ok("exploration", "E"):
        return "3"
    return "4"


def rang_creneau(code_objectif: str) -> int:
    """
    Retourne le rang (1-based) du créneau auquel appartient un objectif,
    selon la convention de numérotation :
      01-09 → créneau 1,  11-19 → créneau 2,  21-29 → créneau 3, etc.

    >>> rang_creneau("01")
    1
    >>> rang_creneau("11")
    2
    >>> rang_creneau("21")
    3
    """
    try:
        n = int(code_objectif)
        return (n // 10) + 1
    except (ValueError, TypeError):
        return 1


def grouper_objectifs_par_creneau(objectifs: list[dict]) -> dict[int, list[dict]]:
    """
    Regroupe une liste d'objectifs par rang de créneau.
    Retourne { 1: [obj, ...], 2: [obj, ...], ... }
    """
    groupes: dict[int, list] = {}
    for obj in objectifs:
        rang = rang_creneau(obj.get("code", "01"))
        groupes.setdefault(rang, []).append(obj)
    return groupes


# ── Sérialisation pour l'API ───────────────────────────────────────────────────

def referentiel_api() -> list[dict]:
    """
    Retourne la liste complète des niveaux pour /api/referentiel/niveaux,
    triée par ordre d'affichage.
    """
    return [
        {"code": code, **info}
        for code, info in sorted(NIVEAUX.items(), key=lambda x: x[1]["ordre"])
    ]
