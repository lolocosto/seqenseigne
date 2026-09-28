"""outils/diagnostic_cartes_validation.py — v0.16.8

Diagnostic LECTURE SEULE des cartes d'automatisme qui refusent le passage
en état « validé » (HTTP 400 côté serveur).

Contexte
--------
La validation pédagogique d'une carte (passage `en_cours → valide`) est
soumise à un hook (`services.cartes_automatisme._valider_carte_hook`) qui
vérifie quatre règles :

  1. recto non vide ;
  2. verso non vide ;
  3. la carte est liée à AU MOINS UN objectif (table `objectif_cartes`,
     liaison N:M introduite en v0.13.6.13) ;
  4. si `type_tech = 'parametree'`, le champ `variables` est non vide.

Si une règle échoue, le serveur renvoie HTTP 400 avec la liste des raisons.
Avant v0.16.8, ces raisons n'étaient pas affichées à l'écran (toast
invisible faute de `window.showToast`), d'où l'impression de « 400 sans
message ». v0.16.8 corrige l'affichage ; cet outil, lui, permet d'auditer
en lot quelles cartes sont concernées et POURQUOI, sans cliquer une par une.

Cet outil RÉUTILISE le vrai hook du service : son verdict est donc
strictement celui du serveur (pas de logique dupliquée qui pourrait
diverger).

Important
---------
- LECTURE SEULE : cet outil n'écrit JAMAIS dans la base. Il ne crée aucune
  liaison, ne modifie aucun état. La réparation (lier une notion/carte à un
  objectif) reste une décision pédagogique manuelle.
- Pour les cartes liées à une notion non rattachée à un objectif, l'outil
  signale aussi la notion en cause et son rattachement objectif (vide), ce
  qui indique le geste à faire dans l'atelier d'assemblage.

Usage
-----
    # Auditer toutes les cartes en_cours de la base par défaut (data/seqenseigne.db) :
    python -m outils.diagnostic_cartes_validation

    # Restreindre à un niveau / une séquence :
    python -m outils.diagnostic_cartes_validation --niveau N10 --sequence S03

    # Spécifier une autre base :
    python -m outils.diagnostic_cartes_validation --db D:\\Enseignement\\seqenseigne\\appli\\data\\seqenseigne.db

    # Inclure aussi les cartes déjà validées (par défaut on ne liste que
    # celles en_cours, seules concernées par le blocage) :
    python -m outils.diagnostic_cartes_validation --tous-etats
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Import du service métier pour réutiliser le hook RÉEL (verdict identique
# au serveur). On ajoute la racine de l'appli au sys.path si nécessaire.
_RACINE = Path(__file__).resolve().parent.parent
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from services.cartes_automatisme import lire_carte  # noqa: E402
from services.etats_edition import ValidationPedagogiqueErreur  # noqa: E402

# Le hook n'est pas exporté publiquement ; on l'importe directement (outil
# de diagnostic interne, couplage assumé).
from services.cartes_automatisme import _valider_carte_hook  # noqa: E402


def _db_par_defaut() -> Path:
    return _RACINE / "data" / "seqenseigne.db"


def _objectifs_de_notion(conn: sqlite3.Connection, notion_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT objectif_id FROM objectif_notions WHERE notion_id = ?",
        (notion_id,),
    ).fetchall()
    return [r[0] for r in rows]


def diagnostiquer(db_path: Path,
                  niveau: str | None,
                  sequence: str | None,
                  tous_etats: bool) -> int:
    """Affiche le rapport. Retourne le nombre de cartes non validables."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    clauses = []
    params: list = []
    if not tous_etats:
        clauses.append("etat_code = 'en_cours'")
    if niveau:
        clauses.append("niveau = ?")
        params.append(niveau)
    if sequence:
        clauses.append("sequence = ?")
        params.append(sequence)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    rows = conn.execute(
        f"SELECT id, niveau, sequence, num, titre, type_tech, etat_code, "
        f"lien_type, lien_id FROM cartes_automatisme{where} "
        f"ORDER BY niveau, sequence, num",
        params,
    ).fetchall()

    print(f"Base : {db_path}")
    filtre = []
    if niveau:
        filtre.append(f"niveau={niveau}")
    if sequence:
        filtre.append(f"sequence={sequence}")
    if not tous_etats:
        filtre.append("etat=en_cours")
    print(f"Filtre : {', '.join(filtre) if filtre else '(aucun)'}")
    print(f"{len(rows)} carte(s) examinée(s).\n")

    nb_bloquees = 0
    for r in rows:
        ref = f"{r['niveau']}/{r['sequence']}/CA{r['num']:02d}"
        try:
            # Verdict RÉEL : on appelle le hook du serveur. S'il ne lève pas,
            # la carte est validable.
            _valider_carte_hook(conn, r["id"])
            verdict = "VALIDABLE"
            raisons = []
        except ValidationPedagogiqueErreur as e:
            verdict = "BLOQUÉE"
            raisons = e.details.get("raisons", [])
            nb_bloquees += 1

        if verdict == "VALIDABLE" and not tous_etats:
            # En mode défaut (en_cours seulement), inutile de bruiter avec
            # les cartes en_cours pourtant validables — on les saute.
            continue

        marqueur = "✗" if verdict == "BLOQUÉE" else "·"
        titre = (r["titre"] or "")[:55]
        print(f"  {marqueur} {ref}  [{r['etat_code']}]  «{titre}»")
        for raison in raisons:
            print(f"        → {raison}")

        # Aide ciblée : si la carte est bloquée pour défaut d'objectif ET
        # qu'elle pointe (lien legacy) vers une notion, indiquer le
        # rattachement objectif de cette notion (souvent vide = geste à faire).
        defaut_objectif = any("objectif" in x.lower() for x in raisons)
        if defaut_objectif and r["lien_type"] == "notion" and r["lien_id"]:
            objs_notion = _objectifs_de_notion(conn, r["lien_id"])
            if objs_notion:
                print(f"        ℹ notion liée {r['lien_id']} → "
                      f"objectif(s) {objs_notion} : penser à lier la carte "
                      f"à l'un d'eux (atelier Carte / assemblage).")
            else:
                print(f"        ℹ notion liée {r['lien_id']} n'est elle-même "
                      f"rattachée à AUCUN objectif. Pour valider : placer cette "
                      f"notion sous un objectif de la séquence (atelier "
                      f"d'assemblage), puis lier la carte à cet objectif.")

    conn.close()

    print()
    if nb_bloquees == 0:
        print("✓ Aucune carte bloquée dans le périmètre examiné.")
    else:
        print(f"✗ {nb_bloquees} carte(s) bloquée(s) — voir les motifs ci-dessus. "
              f"(Aucune modification effectuée : diagnostic lecture seule.)")
    return nb_bloquees


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Diagnostic lecture seule des cartes non validables.")
    p.add_argument("--db", type=Path, default=_db_par_defaut(),
                   help="Chemin de la base SQLite (défaut : data/seqenseigne.db).")
    p.add_argument("--niveau", default=None, help="Filtrer par niveau (ex. N10).")
    p.add_argument("--sequence", default=None, help="Filtrer par séquence (ex. S03).")
    p.add_argument("--tous-etats", action="store_true",
                   help="Inclure aussi les cartes déjà validées "
                        "(défaut : seulement en_cours).")
    args = p.parse_args(argv)

    if not args.db.exists():
        print(f"Base introuvable : {args.db}", file=sys.stderr)
        return 2

    diagnostiquer(args.db, args.niveau, args.sequence, args.tous_etats)
    # Code de sortie 0 (diagnostic réussi), indépendamment du nombre de
    # cartes bloquées — c'est un rapport, pas un test CI.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
