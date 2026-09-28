"""
persistence/yaml_store.py — Accès aux fichiers YAML de séquences.

Les fichiers N10_sequences.yaml, N11_sequences.yaml, N12_sequences.yaml
sont la source de vérité pour la structure des séquences (objectifs,
exercices, critères). Ce module gère leur lecture et écriture.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import yaml


class YamlStore:
    """Accès aux fichiers YAML du dossier data/."""

    NIVEAUX_CONNUS = ("N09", "N10", "N11", "N12")

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def _chemin(self, niveau: str) -> Path:
        return self.data_dir / f"{niveau}_sequences.yaml"

    def existe(self, niveau: str) -> bool:
        return self._chemin(niveau).exists()

    def lire_brut(self, niveau: str) -> Optional[dict]:
        """
        Lit le YAML d'un niveau et retourne la structure brute.
        Retourne None si le fichier n'existe pas ou est vide.
        """
        p = self._chemin(niveau)
        if not p.exists():
            return None
        with open(p, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if not raw or not raw.get("sequences"):
            return None
        return raw

    def ecrire(self, niveau: str, payload: dict) -> None:
        """Écrit un dict dans le fichier YAML du niveau."""
        p = self._chemin(niveau)
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(payload, f, allow_unicode=True,
                      sort_keys=False, default_flow_style=False)

    def statut(self) -> dict:
        """
        Retourne l'état des fichiers YAML pour tous les niveaux connus.
        { "N10": {"present": True, "sequences": 14}, ... }
        """
        result = {}
        for niveau in self.NIVEAUX_CONNUS:
            p = self._chemin(niveau)
            if not p.exists():
                result[niveau] = {"present": False, "sequences": 0}
            else:
                raw = self.lire_brut(niveau)
                nb = len((raw or {}).get("sequences", []))
                result[niveau] = {"present": True, "sequences": nb}
        return result
