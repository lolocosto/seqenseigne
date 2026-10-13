"""
services/sequences.py — Logique métier des séquences pédagogiques.

Construit les structures de séquences depuis le YAML ou depuis les
livrets importés. Aucune dépendance Flask, aucun accès direct aux fichiers
(tout passe par les stores injectés).
"""

from __future__ import annotations
from typing import Optional


# ── Construction depuis le YAML ────────────────────────────────────────────────

def build_sequences(niveau: str, yaml_store, json_store, csv_store) -> list:
    """
    Retourne la liste des séquences d'un niveau, prête pour l'API.
    Lit le YAML du niveau (v0.51.11 : plus de reconstruction depuis les
    anciens livrets importés, retirés).
    """
    raw = yaml_store.lire_brut(niveau)
    return _parser_yaml(raw) if raw else []


def _parser_yaml(raw: dict) -> list:
    """Parse la structure brute YAML en liste de séquences normalisées."""
    result = []
    for seq in raw.get("sequences", []):
        yaml_objs = seq.get("objectifs", [])
        objectifs = []

        # Injecter obj.01 uniquement s'il n'est pas déjà dans le YAML
        if "01" not in {o["code"] for o in yaml_objs}:
            objectifs.append(_obj01())

        for obj in yaml_objs:
            exos_src = obj.get("exercices", {})
            objectifs.append({
                "code":      obj["code"],
                "nom":       obj["nom"],
                "is01":      obj["code"] in ("01", "11", "21"),
                "fin_cycle": obj.get("fin_cycle", False),
                "criteres":  _normaliser_criteres(obj),
                "exercices": _normaliser_exercices(exos_src),
            })

        result.append({
            "code":      seq["code"],
            "numero":    seq.get("numero", 0),
            "nom":       seq["nom"],
            "theme":     seq.get("theme", ""),
            "objectifs": objectifs,
        })
    return result


def _obj01() -> dict:
    return {
        "code": "01", "nom": "Cours et méthodes",
        "is01": True, "fin_cycle": False,
        "criteres": {"2": "", "3": "", "4": ""},
        "exercices": {"fondamental": [], "avancé": [], "exploration": []},
    }


# ── Construction depuis un référentiel en BDD (v0.6.1) ────────────────────────

def build_sequences_from_referentiel(referentiel_id: str, sqlite_store) -> list:
    """
    Retourne la liste des séquences d'un référentiel, dans le même format que
    build_sequences (consommable par l'UI de suivi sans modification).

    Source : tables referentiel_* en BDD. Les champs exercices sont remplis
    de listes vides — la liaison référentiel ↔ atomes pédagogiques est prévue
    plus tard dans la roadmap. L'UI de suivi utilise les cases d'exercices à
    travers la table `suivi` séparément, pas via seq.objectifs.exercices.

    Retourne None si le référentiel est introuvable.
    """
    ref = sqlite_store.lire_referentiel(referentiel_id)
    if not ref:
        return None

    result = []
    for seq in ref["sequences"]:
        objectifs = []
        codes_existants = {o["code"] for o in seq.get("objectifs", [])}

        # Injecter obj.01 uniquement s'il n'est pas déjà dans le référentiel
        if "01" not in codes_existants:
            objectifs.append(_obj01())

        for o in seq.get("objectifs", []):
            objectifs.append({
                "code":      o["code"],
                "nom":       o["nom"],
                "is01":      o["code"] in ("01", "11", "21"),
                "fin_cycle": bool(o.get("fin_cycle", False)),
                "criteres": {
                    "2": o.get("critere_f", ""),
                    "3": o.get("critere_a", ""),
                    "4": o.get("critere_e", ""),
                },
                "exercices": {
                    "fondamental": [],
                    "avancé":      [],
                    "exploration": [],
                },
            })

        result.append({
            "code":      seq["code"],
            "numero":    seq.get("numero", 0),
            "nom":       seq["nom"],
            "theme":     seq.get("theme_code") or "",
            "objectifs": objectifs,
        })
    return result


def _normaliser_criteres(obj: dict) -> dict:
    """
    Normalise les critères vers la convention {2, 3, 4}.
    Supporte l'ancienne convention {F, A, E} et la très ancienne {maitrise: {F,S,TB}}.
    """
    if "criteres" in obj:
        c = obj["criteres"]
        # Ancienne convention F/A/E → 2/3/4
        if "F" in c or "A" in c or "E" in c:
            return {
                "2": c.get("F", ""),
                "3": c.get("A", ""),
                "4": c.get("E", ""),
            }
        # Déjà en nouvelle convention
        return {"2": c.get("2", ""), "3": c.get("3", ""), "4": c.get("4", "")}
    # Très ancienne convention via clé "maitrise"
    m = obj.get("maitrise", {})
    return {
        "2": m.get("F", ""),
        "3": m.get("S", ""),
        "4": m.get("TB", ""),
    }


def _normaliser_exercices(exos_src: dict) -> dict:
    """Normalise les clés d'exercices (fondamentaux/autonomes/enrichissement → fondamental/avancé/exploration)."""
    return {
        "fondamental": exos_src.get("fondamentaux",   exos_src.get("fondamental",  [])),
        "avancé":      exos_src.get("autonomes",      exos_src.get("avancé",       [])),
        "exploration": exos_src.get("enrichissement", exos_src.get("exploration",  [])),
    }


# ── Construction depuis les livrets importés ───────────────────────────────────

# ── Persistance YAML ───────────────────────────────────────────────────────────

def save_sequences_yaml(niveau: str, sequences: list, yaml_store) -> None:
    """Sérialise et persiste la liste des séquences dans le YAML du niveau."""
    payload = {"niveau": niveau, "cycle": "C04", "sequences": []}
    for seq in sequences:
        entry = {
            "code":      seq["code"],
            "numero":    seq["numero"],
            "nom":       seq["nom"],
            "theme":     seq["theme"],
            "objectifs": [],
        }
        for obj in seq["objectifs"]:
            if obj.get("is01"):
                continue  # obj01 est injecté dynamiquement
            entry["objectifs"].append({
                "code":      obj["code"],
                "nom":       obj["nom"],
                "fin_cycle": obj.get("fin_cycle", False),
                "criteres":  obj.get("criteres", {"2": "", "3": "", "4": ""}),
                "exercices": {
                    "fondamental": obj["exercices"].get("fondamental", []),
                    "avancé":      obj["exercices"].get("avancé", []),
                    "exploration": obj["exercices"].get("exploration", []),
                },
            })
        payload["sequences"].append(entry)
    yaml_store.ecrire(niveau, payload)


# ── Recherche ──────────────────────────────────────────────────────────────────

def trouver_sequence(sequences: list, code: str) -> Optional[dict]:
    """Retourne la séquence avec ce code, ou None."""
    return next((s for s in sequences if s["code"] == code), None)
