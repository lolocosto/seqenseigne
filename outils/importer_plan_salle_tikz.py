"""outils/importer_plan_salle_tikz.py — v0.37.0

Crée une salle à partir d'un plan dessiné en TikZ/tkz-euclide (style de
`plan_salle_302.tex`) : chaque quadrilatère devient une place, les places qui
se touchent forment un îlot (cf. services/plan_salle_tikz.py).

La salle ne doit pas déjà exister dans l'établissement. Par défaut : dry-run
(affiche ce qui serait créé). Toujours tester sur une copie de la base.

Usage :
    python -m outils.importer_plan_salle_tikz plan_salle_302.tex --salle 302
    python -m outils.importer_plan_salle_tikz plan_salle_302.tex --salle 302 --apply
    python -m outils.importer_plan_salle_tikz plan.tex --salle 302 --etab "Hautes Ourmes" --apply
    python -m outils.importer_plan_salle_tikz plan.tex --salle 302 --db chemin/seqenseigne.db
"""

import argparse
import sqlite3
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from services import salles as svc
from services.plan_salle_tikz import places_depuis_tikz, PlanTikzErreur

DB = Path(__file__).resolve().parent.parent / "data" / "seqenseigne.db"


def _trouver_etab(conn, critere: str | None) -> dict:
    etabs = [dict(r) for r in conn.execute(
        "SELECT id, nom FROM etablissements ORDER BY nom").fetchall()]
    if not etabs:
        sys.exit("Aucun établissement en base.")
    if critere:
        c = critere.strip().lower()
        trouves = [e for e in etabs if e["id"] == critere or c in e["nom"].lower()]
        if len(trouves) != 1:
            noms = ", ".join(e["nom"] for e in (trouves or etabs))
            sys.exit(f"Établissement {critere!r} ambigu ou introuvable : {noms}")
        return trouves[0]
    if len(etabs) > 1:
        sys.exit("Plusieurs établissements : préciser --etab. "
                 + ", ".join(e["nom"] for e in etabs))
    return etabs[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tex", help="fichier .tex du plan")
    ap.add_argument("--salle", required=True, help="nom de la salle à créer")
    ap.add_argument("--etab", help="id ou partie du nom de l'établissement")
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--apply", action="store_true", help="écrire en base")
    a = ap.parse_args(argv)

    try:
        texte = Path(a.tex).read_text(encoding="utf-8")
        places = places_depuis_tikz(texte)
    except (OSError, PlanTikzErreur) as e:
        sys.exit(f"Lecture du plan impossible : {e}")

    ilots = Counter(p["ilot"] for p in places if p["ilot"])
    isolees = sum(1 for p in places if not p["ilot"])
    print(f"{len(places)} places, {len(ilots)} îlots "
          f"({', '.join(str(n) for n in sorted(ilots.values(), reverse=True))})"
          + (f", {isolees} place(s) isolée(s)" if isolees else ""))

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(svc.SCHEMA)
    etab = _trouver_etab(conn, a.etab)
    print(f"Établissement : {etab['nom']} — salle {a.salle!r}")
    if not a.apply:
        print("Dry-run : rien n'est écrit (ajouter --apply).")
        return 0
    try:
        aujourd_hui = date.today()
        s = svc.creer(conn, etab["id"], a.salle, aujourd_hui)
        # Numéros attribués par le service dans l'ordre de la liste.
        svc.enregistrer_plan(conn, s["id"],
                             [{**p, "numero": None} for p in places], aujourd_hui)
        conn.commit()
    except svc.SalleErreur as e:
        conn.rollback()
        sys.exit(f"Import refusé : {e}")
    finally:
        conn.close()
    print(f"Salle {a.salle!r} créée avec {len(places)} places.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
