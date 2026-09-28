"""
services/suivi.py — Logique métier du suivi des élèves.

Calcul des niveaux depuis les exercices cochés, saisie manuelle.
Toutes les fonctions sont pures (pas d'I/O).
"""

from __future__ import annotations
from services.niveaux import deduire_niveau


# ── Suivi (exercices cochés) ───────────────────────────────────────────────────

def cocher_exercice(suivi: dict, cid: str, seq: str, eid: str,
                    serie: str, num: int, checked: bool) -> dict:
    """
    Coche ou décoche un exercice dans le suivi.
    Retourne le suivi modifié.
    """
    suivi.setdefault(cid, {}).setdefault(seq, {}).setdefault(
        eid, {"F": [], "A": [], "E": [], "cours": []}
    )
    arr = suivi[cid][seq][eid].get(serie, [])
    if checked and num not in arr:
        arr.append(num)
        arr.sort()
    elif not checked and num in arr:
        arr.remove(num)
    suivi[cid][seq][eid][serie] = arr
    return suivi


# ── Niveaux ────────────────────────────────────────────────────────────────────

def set_niveau_manuel(niveaux: dict, cid: str, seq: str,
                      eid: str, obj_code: str, niveau: str) -> dict:
    """
    Définit manuellement le niveau d'un élève sur un objectif.
    Retourne niveaux modifié.
    """
    niveaux.setdefault(cid, {}).setdefault(seq, {}).setdefault(eid, {})[obj_code] = niveau
    return niveaux


def calculer_niveaux_sequence(suivi: dict, niveaux: dict,
                              cid: str, seq_code: str,
                              eleves: list, objectifs: list) -> dict:
    """
    Recalcule les niveaux de tous les élèves d'une classe sur une séquence.
    Retourne niveaux modifié.
    """
    niveaux.setdefault(cid, {}).setdefault(seq_code, {})

    for eleve in eleves:
        eid = eleve["id"]
        niveaux[cid][seq_code].setdefault(eid, {})
        suivi_eleve = suivi.get(cid, {}).get(seq_code, {}).get(eid, {})

        for obj in objectifs:
            code = obj["code"]
            niveaux[cid][seq_code][eid][code] = deduire_niveau(suivi_eleve, obj)

    return niveaux
