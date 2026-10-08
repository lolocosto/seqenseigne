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


# ── Plans de classe (v0.50.1) ────────────────────────────────────────────────
# Mêmes conventions que l'éditeur de salle et que l'ancien rendu TikZ : unités
# en cm de salle, y vers le bas, tableau en haut, angle en degrés dans le sens
# horaire — c'est exactement le repère SVG, il n'y a donc rien à retourner.
# Seuls les rectangles des places tournent ; les textes restent droits.

PLACE_L, PLACE_H = 60.0, 40.0             # cm de salle, taille d'une place
PAGE_L, PAGE_H = 17.0, 21.0               # cm de papier disponibles (A4)
_MARGE = 12.0                             # cm de salle autour du plan
_TABLEAU = 50.0                           # espace réservé au tableau en haut
_FS_NOM, _FS_NUM = 9.0, 11.0              # tailles de police (cm de salle)


def _coins(p):
    import math
    a = math.radians(p.get("angle") or 0)
    ca, sa = math.cos(a), math.sin(a)
    return [(p["x"] + u * ca - v * sa, p["y"] + u * sa + v * ca)
            for u, v in ((-PLACE_L / 2, -PLACE_H / 2), (PLACE_L / 2, -PLACE_H / 2),
                         (PLACE_L / 2, PLACE_H / 2), (-PLACE_L / 2, PLACE_H / 2))]


def _date_fr(iso: str) -> str:
    try:
        a, m, j = iso.split("-")
        return f"{j}/{m}/{a}"
    except ValueError:
        return iso


def _ligne(texte: str, fs: float) -> dict:
    """Une ligne de texte ; compressée (textLength) si elle déborde de la
    place, à partir d'une estimation de largeur (0,56 × corps par signe)."""
    largeur_max = PLACE_L - 4
    estimee = len(texte) * fs * 0.56
    return {"texte": texte,
            "longueur": round(largeur_max, 1) if estimee > largeur_max else None}


def plan_svg(plan: dict) -> dict:
    """Page imprimable d'un plan (une classe, une semaine, une salle) :
    titre, dessin SVG (viewBox en cm de salle, taille en cm de papier),
    élèves non placés. Même contenu que l'ancien page_tikz."""
    titre = (f"Plan de la salle {plan['salle']['nom']} — {plan['classe']['nom']}"
             f" — semaine du {_date_fr(plan['lundi'])}")
    places = plan.get("places") or []
    if not places:
        return {"titre": titre, "vide": True}
    pts = [c for p in places for c in _coins(p)]
    xmin, xmax = min(x for x, _ in pts), max(x for x, _ in pts)
    ymin, ymax = min(y for _, y in pts), max(y for _, y in pts)
    vx, vy = xmin - _MARGE, ymin - _MARGE - _TABLEAU
    vw, vh = (xmax - xmin) + 2 * _MARGE, (ymax - ymin) + 2 * _MARGE + _TABLEAU
    s = min(PAGE_L / vw, PAGE_H / vh)          # cm de papier par cm de salle
    larg_tab = min(300.0, (xmax - xmin) * 0.5)
    cx = (xmin + xmax) / 2
    noms = {e["id"]: e["etiquette"] for e in plan.get("eleves") or []}
    par_num = {p["numero"]: p for p in plan.get("placements") or []}
    reservees = set(plan.get("reservations") or [])
    avec_noms = bool(par_num)
    dessin = []
    for p in places:
        place = {"x": round(p["x"], 2), "y": round(p["y"], 2),
                 "angle": round(p.get("angle") or 0, 1),
                 "rx": round(p["x"] - PLACE_L / 2, 2),
                 "ry": round(p["y"] - PLACE_H / 2, 2),
                 "lignes": [], "classe": "num", "fs": _FS_NUM}
        pl = par_num.get(p["numero"])
        if p["numero"] in reservees:                 # v0.40.0 — place AESH
            place.update(classe="aesh", lignes=[_ligne("AESH", _FS_NUM)])
        elif pl:
            nom = noms.get(pl["eleve_id"], "?")
            morceaux = nom.split(" ", 1) if " " in nom else [nom]
            style = ("impose" if pl.get("statut") == "impose"
                     else "a-confirmer" if not pl.get("confirme", 1) else "eleve")
            place.update(classe=style, fs=_FS_NOM,
                         lignes=[_ligne(m, _FS_NOM) for m in morceaux])
        else:
            place.update(classe="num-gris" if avec_noms else "num",
                         lignes=[_ligne(str(p["numero"]), _FS_NUM)])
        dessin.append(place)
    non_places = [noms[e] for e in plan.get("non_places") or [] if e in noms] \
        if avec_noms else []
    return {
        "titre": titre, "vide": False, "avec_noms": avec_noms,
        "viewbox": f"{vx:.2f} {vy:.2f} {vw:.2f} {vh:.2f}",
        "largeur_cm": round(vw * s, 2), "hauteur_cm": round(vh * s, 2),
        "tableau": {"x": round(cx - larg_tab / 2, 2), "y": round(ymin - _MARGE - 45, 2),
                    "l": round(larg_tab, 2), "h": 10.0,
                    "tx": round(cx, 2), "ty": round(ymin - _MARGE - 20, 2)},
        "places": dessin, "L": PLACE_L, "H": PLACE_H,
        "non_places": non_places,
    }
