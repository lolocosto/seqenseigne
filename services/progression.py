"""
services/progression.py — Logique métier des progressions pédagogiques.

Une Progression est la référence calendaire et pédagogique à laquelle
se rattache le suivi d'une classe. Elle contient des créneaux : un créneau
est un passage sur une séquence à des dates données, avec les objectifs
évalués lors de ce créneau.

Convention de numérotation des objectifs par créneau :
  01–09 → créneau 1,  11–19 → créneau 2,  21–29 → créneau 3, etc.

Aucune dépendance Flask, aucun I/O.
"""

from __future__ import annotations
from typing import Optional
from services.niveaux import rang_creneau, grouper_objectifs_par_creneau
from persistence.ids import nouveau_id_progression, nouveau_id_creneau


# ── Identifiants ───────────────────────────────────────────────────────────────
#
# Les ids de progression et de créneau sont des UUID opaques. La contrainte
# d'unicité métier d'une progression (une seule par niveau × année ×
# établissement) est portée par la base via un index UNIQUE composite.

def progression_id(niveau: str = "", annee: str = "", etablissement: str = "") -> str:
    """
    Génère un identifiant opaque pour une progression.

    Les paramètres niveau/annee/etablissement sont acceptés pour rétrocompat
    des appels existants mais ne sont plus utilisés — la clé métier est
    portée par les colonnes de la table `progressions` avec un index UNIQUE.
    """
    return nouveau_id_progression()


def creneau_id() -> str:
    return nouveau_id_creneau()


# ── Construction d'une progression vide ───────────────────────────────────────

def progression_vide(niveau: str, annee: str, sequences_c04: list,
                     etablissement: str = "") -> dict:
    """
    Crée une progression vide pour un niveau, une année et un établissement,
    avec 14 créneaux dans l'ordre naturel (un par séquence, sans dates).

    sequences_c04  : liste de dicts {code, numero, nom, theme}
                     triée par numéro (depuis CsvStore.lire_c04_sequences()).
    etablissement  : nom de l'établissement (inclus dans l'id).
    """
    creneaux = [
        {
            "id":         creneau_id(),
            "sequence":   seq["code"],
            "partie":     None,
            "periode":    None,
            "date_debut": None,
            "date_fin":   None,
            "ordre":      i + 1,
            "objectifs":  [],
            "connaissances": [],
        }
        for i, seq in enumerate(
            sorted(sequences_c04, key=lambda s: s.get("numero", 0))
        )
    ]
    return {
        "id":            progression_id(niveau, annee, etablissement),
        "niveau":        niveau,
        "annee":         annee,
        "etablissement": etablissement,
        "periodes":      [],
        "creneaux":      creneaux,
    }


# ── Opérations sur une progression ────────────────────────────────────────────

def trouver_creneau(progression: dict, creneau_id_: str) -> Optional[dict]:
    return next(
        (c for c in progression.get("creneaux", []) if c["id"] == creneau_id_),
        None,
    )


def modifier_creneau(progression: dict, creneau_id_: str,
                     champs: dict) -> tuple[dict, str | None]:
    """
    Met à jour les champs d'un créneau (date_debut, date_fin, periode,
    partie, ordre, objectifs, connaissances).
    Retourne (progression_modifiée, erreur).
    """
    for c in progression.get("creneaux", []):
        if c["id"] == creneau_id_:
            champs_editables = {
                "date_debut", "date_fin", "periode",
                "partie", "ordre", "objectifs", "connaissances",
            }
            for k, v in champs.items():
                if k in champs_editables:
                    c[k] = v
            return progression, None
    return progression, f"Créneau {creneau_id_!r} introuvable"


def reordonner_creneaux(progression: dict, ordre: list[str]) -> dict:
    """
    Réordonne les créneaux selon la liste d'ids fournie.
    Les créneaux absents de la liste sont placés à la fin.
    Retourne la progression mise à jour.
    """
    index = {c["id"]: i for i, c in enumerate(progression["creneaux"])}
    in_list = [c for c in progression["creneaux"] if c["id"] in set(ordre)]
    not_in_list = [c for c in progression["creneaux"] if c["id"] not in set(ordre)]

    sorted_in = sorted(in_list, key=lambda c: ordre.index(c["id"]))
    for i, c in enumerate(sorted_in + not_in_list, 1):
        c["ordre"] = i
    progression["creneaux"] = sorted_in + not_in_list
    return progression


def objectifs_par_creneau_rang(creneaux: list, rang: int) -> list:
    """
    Retourne les objectifs du rang de créneau donné pour une séquence.
    Utile pour reconstituer quels objectifs vont dans quel créneau.
    """
    return [
        obj for c in creneaux
        for obj in c.get("objectifs", [])
        if rang_creneau(obj.get("code", "01")) == rang
    ]


# ── Validation ─────────────────────────────────────────────────────────────────

def valider_progression(progression: dict) -> list[str]:
    """
    Retourne une liste d'avertissements (non bloquants) sur la progression.
    """
    warnings = []
    creneaux = progression.get("creneaux", [])

    seqs_vues = set()
    for c in creneaux:
        seq = c.get("sequence")
        if not seq:
            warnings.append(f"Créneau {c['id']} : séquence manquante")
        if not c.get("date_debut") and not c.get("date_fin"):
            pass  # OK pour une progression en cours de construction
        if seq and seq in seqs_vues and not c.get("partie"):
            warnings.append(
                f"Séquence {seq} apparaît plusieurs fois sans libellé 'partie'"
            )
        if seq:
            seqs_vues.add(seq)

    return warnings


# ── Snapshot pour le suivi ─────────────────────────────────────────────────────

def snapshot_creneau(creneau: dict) -> dict:
    """
    Retourne une version allégée d'un créneau pour inclusion dans le suivi.
    Conserve id, sequence, partie, periode, objectifs (codes + noms seulement).
    """
    return {
        "id":       creneau["id"],
        "sequence": creneau.get("sequence"),
        "partie":   creneau.get("partie"),
        "periode":  creneau.get("periode"),
        "objectifs": [
            {"code": o["code"], "nom": o.get("nom", "")}
            for o in creneau.get("objectifs", [])
        ],
    }
