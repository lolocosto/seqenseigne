"""
services/annees_scolaires.py — Liste des années scolaires connues.

Les années scolaires sont déclarées dans `appli/config/annees_scolaires.json`.
Ce fichier est statique, édité à la main par l'enseignant quand une nouvelle
année scolaire doit être ajoutée au système (typiquement en avril/mai pour
préparer l'année suivante).

Structure du JSON :
  {
    "annee_courante": "2025-2026",
    "annees_scolaires": [
      {"code": "2025-2026", "libelle": "2025-2026", "archive": false},
      ...
    ]
  }

Aucune dépendance Flask, aucun I/O hors lecture du JSON.
"""

from __future__ import annotations
import json
from datetime import date
from pathlib import Path


def annee_scolaire_de_date(d: date | None = None) -> str:
    """Année scolaire au format "AAAA-AAAA" pour une date donnée (aujourd'hui
    par défaut). Convention : septembre→décembre = N/N+1 ; janvier→août =
    (N-1)/N. Sert de repli si `annee_courante` n'est pas définie dans la config
    (ne se périme jamais, contrairement à une valeur codée en dur)."""
    d = d or date.today()
    debut = d.year if d.month >= 9 else d.year - 1
    return f"{debut}-{debut + 1}"


# ── Chemin par défaut ──────────────────────────────────────────────────────────

def _chemin_par_defaut() -> Path:
    """Chemin du fichier annees_scolaires.json livré avec l'appli."""
    return Path(__file__).parent.parent / "config" / "annees_scolaires.json"


def _charger(chemin: Path | None = None) -> dict:
    """Charge et retourne le contenu du JSON. Fichier absent → structure vide."""
    p = chemin or _chemin_par_defaut()
    if not p.exists():
        return {"annee_courante": "", "annees_scolaires": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ── API publique ──────────────────────────────────────────────────────────────

def lister(chemin: Path | None = None) -> list[dict]:
    """
    Retourne la liste des années scolaires connues, triées par code croissant.
    Chaque entrée : {code, libelle, archive}.

    Les années archivées sont en fin de liste (tri sur `archive` puis `code`).
    """
    data = _charger(chemin)
    annees = list(data.get("annees_scolaires", []))
    # Tri : non-archivées d'abord (par code), puis archivées (par code décroissant
    # pour que les plus récentes viennent en premier dans la section archivées).
    annees.sort(key=lambda a: (a.get("archive", False), a.get("code", "")))
    # Réinverser uniquement la queue archivée pour "plus récent en premier"
    actives   = [a for a in annees if not a.get("archive", False)]
    archivees = sorted(
        (a for a in annees if a.get("archive", False)),
        key=lambda a: a.get("code", ""),
        reverse=True,
    )
    return actives + archivees


def courante(chemin: Path | None = None) -> str:
    """
    Retourne le code de l'année scolaire par défaut, à présélectionner dans
    l'UI. Repli sur l'année scolaire calculée depuis la date si la config ne
    définit pas `annee_courante`.
    """
    return _charger(chemin).get("annee_courante", "") or annee_scolaire_de_date()


def existe(code: str, chemin: Path | None = None) -> bool:
    """Indique si `code` (ex: '2025-2026') figure dans la liste."""
    return any(a.get("code") == code for a in lister(chemin))
