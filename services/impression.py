"""services/impression.py — v0.50.0

Documents imprimables hors ateliers, rendus en HTML + CSS d'impression
(templates/impression/, static/impression.css) au lieu de LaTeX : le
navigateur imprime ou enregistre en PDF. Aucune distribution LaTeX requise.

Ce module ne contient que la préparation des données propre à l'impression ;
les gabarits échappent eux-mêmes le texte (autoescape Jinja).
"""

from __future__ import annotations


def lignes_theoriques(parties: list) -> tuple[list[dict], int]:
    """Aperçu théorique MER : chaque partie avec sa plage de numéros de séance
    (enchaînées depuis 1). Retourne (lignes, total de séances)."""
    lignes = []
    debut = 1
    for p in parties or []:
        nb = int(p.get("nb_seances", 0) or 0)
        fin = debut + nb - 1
        plage = f"séances {debut}" + (f"–{fin}" if nb > 1 else "")
        lignes.append({
            "libelle": p.get("libelle", "") or "",
            "sequence": p.get("sequence_nom", "") or p.get("sequence_code", "") or "",
            "plage": plage if nb > 0 else "—",
            "nb": nb,
        })
        debut = fin + 1
    return lignes, debut - 1
