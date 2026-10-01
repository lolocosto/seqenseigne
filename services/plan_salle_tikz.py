"""services/plan_salle_tikz.py — v0.37.0

Conversion d'un plan de salle dessiné en TikZ/tkz-euclide (style du
`plan_salle_302.tex` de l'enseignant) en liste de places pour `services.salles`.

Mini-interpréteur des seules commandes utilisées par ce style de plan :
  - \\tkzDefPoints{x/y/N, ...}
  - \\tkzDefPointsBy[translation= from P to Q](L1,...){N1,...}
  - \\tkzDefPointsBy[rotation = center O angle a](L1,...){N1,...}
  - \\tkzDrawPolygon[...](P1,P2,P3,P4)
Chaque quadrilatère dessiné = un emplacement d'une personne.

Conventions de sortie (celles de l'éditeur de plan) :
  - unité : cm. Le rectangle de base TikZ 6×4 unités = une table 60×40 cm,
    donc 1 unité TikZ = 10 cm (l'option `scale` du tikzpicture est ignorée :
    elle ne joue que sur l'impression) ;
  - repère écran : x vers la droite, y vers le BAS (tableau en haut) ;
  - (x, y) = centre de la place ; angle en degrés, sens horaire à l'écran
    (convention SVG rotate), dans [0, 360) ; l'angle est celui du grand côté ;
  - îlots : deux places qui se touchent appartiennent au même îlot ;
  - numérotation : îlots dans l'ordre de lecture (haut→bas, gauche→droite),
    puis places de l'îlot dans le même ordre.

Fonction pure (pas de base) : `places_depuis_tikz(texte) -> list[dict]`.
"""

from __future__ import annotations
import math
import re

UNITE_CM = 10.0          # 1 unité TikZ = 10 cm
_EPS = 1e-6


class PlanTikzErreur(ValueError):
    pass


def _liste(s: str) -> list[str]:
    return [t.strip() for t in s.split(",") if t.strip()]


def _sans_commentaires(texte: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", l) for l in texte.splitlines())


def polygones_tikz(texte: str) -> list[list[tuple[float, float]]]:
    """Interprète le TikZ et renvoie les polygones dessinés (coordonnées
    TikZ, y vers le haut), dans l'ordre de dessin."""
    texte = _sans_commentaires(texte)
    # On interprète le premier tikzpicture (le document peut l'appeler
    # plusieurs fois via une macro : un seul plan suffit).
    m = re.search(r"\\begin\{tikzpicture\}(.*?)\\end\{tikzpicture\}", texte, re.S)
    if not m:
        raise PlanTikzErreur("Aucun environnement tikzpicture trouvé.")
    corps = m.group(1)
    pts: dict[str, tuple[float, float]] = {}
    polys: list[list[tuple[float, float]]] = []
    motif = re.compile(
        r"\\tkzDefPoints\{(?P<defs>[^}]*)\}"
        r"|\\tkzDefPointsBy\[(?P<transfo>[^\]]*)\]\((?P<src>[^)]*)\)\{(?P<dst>[^}]*)\}"
        r"|\\tkzDrawPolygon(?:\[[^\]]*\])?\((?P<poly>[^)]*)\)")

    def get(n):
        if n not in pts:
            raise PlanTikzErreur(f"Point {n!r} utilisé avant d'être défini.")
        return pts[n]

    for mo in motif.finditer(corps):
        if mo.group("defs") is not None:
            for d in _liste(mo.group("defs")):
                x, y, n = d.split("/")
                pts[n.strip()] = (float(x), float(y))
        elif mo.group("transfo") is not None:
            t = mo.group("transfo")
            src, dst = _liste(mo.group("src")), _liste(mo.group("dst"))
            if len(src) != len(dst):
                raise PlanTikzErreur("Listes de points de longueurs différentes.")
            mt = re.search(r"translation\s*=\s*from\s+(\S+)\s+to\s+(\S+)", t)
            mr = re.search(r"rotation\s*=\s*center\s+(\S+)\s+angle\s+(-?[\d.]+)", t)
            if mt:
                (ax, ay), (bx, by) = get(mt.group(1)), get(mt.group(2))
                dx, dy = bx - ax, by - ay
                f = lambda p: (p[0] + dx, p[1] + dy)
            elif mr:
                cx, cy = get(mr.group(1))
                a = math.radians(float(mr.group(2)))
                ca, sa = math.cos(a), math.sin(a)
                f = lambda p: (cx + (p[0] - cx) * ca - (p[1] - cy) * sa,
                               cy + (p[0] - cx) * sa + (p[1] - cy) * ca)
            else:
                raise PlanTikzErreur(f"Transformation non gérée : {t!r}")
            images = [f(get(s)) for s in src]   # calculées avant affectation
            for n, p in zip(dst, images):
                pts[n] = p
        else:
            noms = _liste(mo.group("poly"))
            polys.append([get(n) for n in noms])
    if not polys:
        raise PlanTikzErreur("Aucun polygone dessiné.")
    return polys


def _sur_segment(p, a, b, tol=1e-4) -> bool:
    (px, py), (ax, ay), (bx, by) = p, a, b
    abx, aby = bx - ax, by - ay
    l2 = abx * abx + aby * aby
    if l2 < _EPS:
        return math.hypot(px - ax, py - ay) < tol
    t = ((px - ax) * abx + (py - ay) * aby) / l2
    if t < -tol or t > 1 + tol:
        return False
    qx, qy = ax + t * abx, ay + t * aby
    return math.hypot(px - qx, py - qy) < tol


def _se_touchent(p1, p2) -> bool:
    for poly_a, poly_b in ((p1, p2), (p2, p1)):
        n = len(poly_b)
        for v in poly_a:
            for i in range(n):
                if _sur_segment(v, poly_b[i], poly_b[(i + 1) % n]):
                    return True
    return False


def places_depuis_tikz(texte: str) -> list[dict]:
    polys = polygones_tikz(texte)
    brutes = []
    for poly in polys:
        if len(poly) != 4:
            raise PlanTikzErreur("Seuls les quadrilatères sont gérés.")
        cx = sum(p[0] for p in poly) / 4
        cy = sum(p[1] for p in poly) / 4
        # Grand côté : on prend la plus longue des deux arêtes issues de P1.
        (x0, y0), (x1, y1), (x3, y3) = poly[0], poly[1], poly[3]
        e1, e2 = (x1 - x0, y1 - y0), (x3 - x0, y3 - y0)
        grand = e1 if math.hypot(*e1) >= math.hypot(*e2) else e2
        ang_tikz = math.degrees(math.atan2(grand[1], grand[0]))
        brutes.append({"poly": poly, "cx": cx, "cy": cy,
                       "angle": (-ang_tikz) % 180.0})  # rectangle : mod 180
    # Îlots : composantes connexes de la relation « se touchent ».
    parent = list(range(len(brutes)))

    def racine(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(brutes)):
        for j in range(i + 1, len(brutes)):
            if _se_touchent(brutes[i]["poly"], brutes[j]["poly"]):
                parent[racine(i)] = racine(j)
    # Passage en cm, repère écran (y vers le bas), origine au coin haut-gauche
    # de l'ensemble avec une marge de 60 cm.
    xs = [p[0] for b in brutes for p in b["poly"]]
    ys = [p[1] for b in brutes for p in b["poly"]]
    xmin, ymax = min(xs), max(ys)
    marge = 60.0
    for b in brutes:
        b["x"] = round((b["cx"] - xmin) * UNITE_CM + marge, 1)
        b["y"] = round((ymax - b["cy"]) * UNITE_CM + marge, 1)
        a = round(b["angle"], 1) % 180.0
        b["angle"] = 0.0 if abs(a - 180.0) < 0.05 else a
    groupes: dict[int, list[dict]] = {}
    for i, b in enumerate(brutes):
        groupes.setdefault(racine(i), []).append(b)
    lecture = lambda b: (round(b["y"] / 40.0), b["x"])
    ordre_ilots = sorted(
        groupes.values(),
        key=lambda g: (round(sum(b["y"] for b in g) / len(g) / 80.0),
                       sum(b["x"] for b in g) / len(g)))
    places, num = [], 0
    for k, g in enumerate(ordre_ilots, start=1):
        ilot = f"i{k}" if len(g) > 1 else ""
        for b in sorted(g, key=lecture):
            num += 1
            places.append({"numero": num, "x": b["x"], "y": b["y"],
                           "angle": b["angle"], "ilot": ilot})
    return places
