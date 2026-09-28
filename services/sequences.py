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
    Stratégie :
      1. Lire le YAML du niveau.
      2. Si absent ou vide → reconstruire depuis les livrets importés,
         persister le YAML généré, retourner le résultat.
    """
    raw = yaml_store.lire_brut(niveau)
    if raw:
        return _parser_yaml(raw)

    # Fallback : construire depuis les livrets importés
    seqs = build_sequences_from_livrets(niveau, json_store, csv_store)
    if seqs:
        save_sequences_yaml(niveau, seqs, yaml_store)
    return seqs


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

def build_sequences_from_livrets(niveau: str, json_store, csv_store) -> list:
    """
    Reconstruit les séquences d'un niveau depuis :
      - livrets_importes.json  (structure notions/méthodes/exercices)
      - methodes.json          (num_objectif, titre, critères, finCycle)
      - exercices.json         (serie_code, num, objectifs_codes)
      - C04_sequences.csv      (nom, theme)
    """
    c04 = csv_store.lire_c04_sequences()
    livrets_data   = json_store.lire_livrets_importes()
    methodes_data  = json_store.lire_methodes()
    exercices_data = json_store.lire_exercices()

    methodes_by_file = {m["fichier"]: m for m in methodes_data}

    niveaux_livrets = sorted(
        [l for l in livrets_data if l["niveau"] == niveau],
        key=lambda l: l["sequence"],
    )

    result = []
    for livret in niveaux_livrets:
        seq_code = livret["sequence"]
        c04_seq  = c04.get(seq_code, {})

        objectifs = [_obj01()]

        for fichier_methode in livret.get("methodes", []):
            m = methodes_by_file.get(fichier_methode)
            if not m:
                continue
            code_obj = m.get("num_objectif", "??")

            exos_F = sorted([
                int(e["num"]) for e in exercices_data
                if e["niveau"] == niveau and e["sequence"] == seq_code
                and e["serie_code"] == "F" and code_obj in e.get("objectifs_codes", [])
            ])
            exos_A = sorted([
                int(e["num"]) for e in exercices_data
                if e["niveau"] == niveau and e["sequence"] == seq_code
                and e["serie_code"] == "A" and code_obj in e.get("objectifs_codes", [])
            ])
            exos_E = sorted([
                int(e["num"]) for e in exercices_data
                if e["niveau"] == niveau and e["sequence"] == seq_code
                and e["serie_code"] == "E" and code_obj in e.get("objectifs_codes", [])
            ])

            criteres_src = m.get("criteres", {})
            objectifs.append({
                "code":      code_obj,
                "nom":       m.get("titre", ""),
                "is01":      False,
                "fin_cycle": m.get("finCycle", False),
                "criteres": {
                    "2": criteres_src.get("fondamental", criteres_src.get("F", "")),
                    "3": criteres_src.get("avancé",      criteres_src.get("A", "")),
                    "4": criteres_src.get("exploration", criteres_src.get("E", "")),
                },
                "exercices": {
                    "fondamental": exos_F,
                    "avancé":      exos_A,
                    "exploration": exos_E,
                },
            })

        result.append({
            "code":      seq_code,
            "numero":    c04_seq.get("numero", 0),
            "nom":       c04_seq.get("nom", seq_code),
            "theme":     c04_seq.get("theme", ""),
            "objectifs": objectifs,
        })

    return result


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
