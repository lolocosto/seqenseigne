"""
services/versions.py — Logique métier des versions (snapshots) de livrets.
"""

from __future__ import annotations
from datetime import datetime


def creer_snapshot(versions: dict, niveau: str, seq: str,
                   tag: str, label: str,
                   seq_data: dict) -> tuple[dict, dict | None, str | None]:
    """
    Crée un snapshot de la version courante d'une séquence.
    Retourne (versions_modifié, snapshot, erreur_msg).
    erreur_msg est None si OK.
    """
    existing = versions.get(niveau, {}).get(seq, [])
    if any(v["tag"] == tag for v in existing):
        return versions, None, f"Le tag '{tag}' existe déjà pour {niveau}/{seq}"

    snapshot = {
        "tag":    tag,
        "date":   datetime.now().isoformat(timespec="seconds"),
        "label":  label or tag,
        "objectifs": [
            {
                "code": o["code"],
                "nom":  o["nom"],
                "exercices": o["exercices"],
            }
            for o in seq_data["objectifs"]
        ],
        "connaissances": seq_data.get("connaissances", []),
    }
    versions.setdefault(niveau, {}).setdefault(seq, []).append(snapshot)
    return versions, snapshot, None


def supprimer_snapshot(versions: dict, classes_data: dict,
                       niveau: str, seq: str,
                       tag: str) -> tuple[dict, str | None]:
    """
    Supprime un snapshot si aucune classe ne l'utilise.
    Retourne (versions_modifié, erreur_msg).
    """
    key = f"{niveau}_{seq}"
    for c in classes_data.get("classes", []):
        if c.get("versions_actives", {}).get(key) == tag:
            return versions, (
                f"La classe {c['nom']} utilise cette version — "
                "impossible de la supprimer"
            )
    lst = versions.get(niveau, {}).get(seq, [])
    versions.setdefault(niveau, {})[seq] = [v for v in lst if v["tag"] != tag]
    return versions, None
