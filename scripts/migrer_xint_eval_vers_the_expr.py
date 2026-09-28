#!/usr/bin/env python3
r"""scripts/migrer_xint_eval_vers_the_expr.py — v0.15.2.2.2

Migration ponctuelle (idempotente) : convertit les macros xint **protégées**
(`\xintiieval{...}`, `\xinteval{...}`, `\xintfloateval{...}`) en macros
xint **expansibles** (`\xinttheiiexpr ...\relax`, etc.) dans les champs
`recto`, `verso` et `variables` de la table `cartes_automatisme`.

Pourquoi ?
----------
Les macros `\xint*eval{...}` sont marquées `\protected` côté xintexpr.
Conséquence : dans un `\edef` (par exemple celui qu'on doit faire dans
`\seqCartePlanche` pour figer le tirage par cellule), elles ne s'expansent
pas et restent symboliques. Le partage de valeur recto/verso casse.

Les variantes `\xintthe<truc>expr ...\relax` sont **purement expansibles**.
Dans un `\edef` elles produisent la valeur courante. C'est le pattern
recommandé par la doc xint pour les "moving arguments" (cf. xint.pdf
section sur l'écriture dans des fichiers auxiliaires).

Mapping
-------
| Avant (protégé)          | Après (expansible)               |
|--------------------------|----------------------------------|
| `\xintiieval{expr}`      | `\xinttheiiexpr expr\relax`      |
| `\xinteval{expr}`        | `\xinttheexpr expr\relax`        |
| `\xintfloateval{expr}`   | `\xintthefloatexpr expr\relax`   |

Macros laissées inchangées
--------------------------
- `\xintdefiivar`, `\xintdeffloatvar` : assignations, pas concernées
- `\xintiiifCmp`, `\xintifsgnexpr` : conditionnels, comportement
  spécifique, hors scope de cette migration

Sécurités
---------
- **Dry-run par défaut** : affiche ce qui serait modifié, ne touche
  à rien.
- Avec `--ecrire`, demande confirmation interactive (`OUI` à taper)
  sauf si `--yes` est passé.
- **Idempotence** : si un champ est déjà migré (présence de
  `\xinttheiiexpr` etc.), il est laissé tel quel.
- Ne traite que les cartes valides (`etat_code = 'valide'`).
- Sauvegarde la BDD avant écriture (copie `.bak` horodatée).

Usage
-----
    # Dry-run (par défaut, ne modifie rien)
    python -m scripts.migrer_xint_eval_vers_the_expr

    # Application réelle (avec confirmation 'OUI')
    python -m scripts.migrer_xint_eval_vers_the_expr --ecrire

    # Application sans confirmation interactive (à éviter manuellement)
    python -m scripts.migrer_xint_eval_vers_the_expr --ecrire --yes

    # Sur une BDD alternative
    python -m scripts.migrer_xint_eval_vers_the_expr --db /chemin/vers/db
"""
from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


# Mapping des conversions à appliquer.
# Chaque entrée : (regex_recherche, fonction_remplacement, étiquette pour rapport)
# La regex capture le nom de macro et son argument {...} équilibré
# sans imbrication (vérifié sur le corpus N10 : 0 cas d'imbrication).
#
# IMPORTANT (v0.15.2.2.2.1) : on émet `\relax{}` plutôt que `\relax`. Sans le
# `{}`, si le caractère qui suit dans le contenu original est une lettre (ce
# qui arrive dans le corpus N10 : `\xintiieval{N10S05C06_a}x + ...` avec `x`
# comme variable algébrique), le `x` se colle à `\relax` pour former `\relaxx`
# — commande inconnue qui plante la compilation. `\relax{}` est l'idiome TeX
# standard pour terminer une commande sans introduire d'espace ni de fusion
# avec un token suivant.
#
# IMPORTANT (v0.15.2.2.2.2) : les usages de `\num{\xint*eval{...}}` (siunitx)
# nécessitent un traitement spécifique, MAIS PAS celui qu'on croyait d'abord.
#
# Découverte (v0.15.2.2.2.3) : le crash siunitx
# (« Argument of \__siunitx_number_parse_loop_main_digit:NNNN has an extra } »)
# n'est PAS dû à `\xintthefloatexpr` lui-même. Tests MWE à l'appui :
#   - `\num{\xintthefloatexpr p\relax}`     → COMPILE (OK)
#   - `\num{\xintthefloatexpr p\relax{}}`   → CRASHE
# Le coupable est le `\relax{}` (avec accolades vides) introduit en
# v0.15.2.2.2.1 : à l'intérieur d'un `\num{...}`, le groupe vide `{}` reste
# dans l'argument et siunitx le lit comme un `}` parasite après le nombre.
#
# Solution : pour les motifs `\num[opts?]{\xint*eval{X}}`, on produit
# `\num[opts?]{\xintthe*expr X\relax}` — la forme expansible SANS le `{}`.
# `\num` consomme son argument `{...}` qui se termine par le `}` de
# fermeture, donc le `\relax` n'a aucune lettre collée à craindre : pas
# besoin de `{}`. (Et pas besoin de `\expanded`/`\noexpand` non plus :
# `\num` déclenche correctement l'expansion de `\xintthefloatexpr` dans
# son argument.)

# Pré-conversions : traitent `\num[opts?]{\xint*eval{...}}` AVANT les
# conversions générales, sinon la conversion « simple » de \xintfloateval
# produirait `\num{\xintthefloatexpr X\relax{}}` (avec le {} fatal).
PRE_CONVERSIONS_NUM = [
    # \num[opts?]{\xintfloateval{X}} → \num[opts?]{\xintthefloatexpr X\relax}
    (re.compile(r'\\num(\[[^\]]*\])?\{\\xintfloateval\{([^{}]*)\}\}'),
     r'\\num\1{\\xintthefloatexpr \2\\relax}',
     'num_xintfloateval'),
    # \num[opts?]{\xintiieval{X}} → \num[opts?]{\xinttheiiexpr X\relax}
    (re.compile(r'\\num(\[[^\]]*\])?\{\\xintiieval\{([^{}]*)\}\}'),
     r'\\num\1{\\xinttheiiexpr \2\\relax}',
     'num_xintiieval'),
    # \num[opts?]{\xinteval{X}} → \num[opts?]{\xinttheexpr X\relax}
    (re.compile(r'\\num(\[[^\]]*\])?\{\\xinteval\{([^{}]*)\}\}'),
     r'\\num\1{\\xinttheexpr \2\\relax}',
     'num_xinteval'),
]

CONVERSIONS = [
    # \xintiieval{expr} → \xinttheiiexpr expr\relax{}
    (re.compile(r'\\xintiieval\{([^{}]*)\}'),
     r'\\xinttheiiexpr \1\\relax{}',
     'xintiieval'),
    # \xintfloateval{expr} → \xintthefloatexpr expr\relax{}
    (re.compile(r'\\xintfloateval\{([^{}]*)\}'),
     r'\\xintthefloatexpr \1\\relax{}',
     'xintfloateval'),
    # \xinteval{expr} → \xinttheexpr expr\relax{}
    # ATTENTION : regex doit éviter de matcher \xintiieval et \xintfloateval.
    # On s'appuie sur l'ordre des conversions : les plus spécifiques d'abord,
    # car ce script applique séquentiellement. Quand on arrive ici, les
    # \xintiieval et \xintfloateval sont déjà convertis.
    (re.compile(r'\\xinteval\{([^{}]*)\}'),
     r'\\xinttheexpr \1\\relax{}',
     'xinteval'),
]


def migrer_chaine(s: str) -> tuple[str, dict]:
    """Applique toutes les conversions à une chaîne et renvoie :
        (chaîne_migrée, {étiquette: nombre_de_substitutions, ...})

    Procède en deux phases :
    1. Pré-conversions ciblées : les motifs `\\num{\\xint*eval{...}}` sont
       enveloppés dans un `\\expanded{\\noexpand\\num{\\xintthe*expr ...\\relax{}}}`
       pour éviter le crash siunitx (cf. v0.15.2.2.2.2).
    2. Conversions générales : `\\xint*eval{...}` → `\\xintthe*expr ...\\relax{}`
       pour toutes les autres occurrences.
    """
    stats = {}
    nouveau = s
    # Phase 1 : pré-conversions ciblées (num + xint)
    for pattern, remplacement, etiquette in PRE_CONVERSIONS_NUM:
        nouveau, n = pattern.subn(remplacement, nouveau)
        if n > 0:
            stats[etiquette] = n
    # Phase 2 : conversions générales
    for pattern, remplacement, etiquette in CONVERSIONS:
        nouveau, n = pattern.subn(remplacement, nouveau)
        if n > 0:
            stats[etiquette] = n
    return nouveau, stats


def fusionner_stats(a: dict, b: dict) -> dict:
    """Additionne deux dictionnaires de stats."""
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + v
    return out


def planifier_migration(conn: sqlite3.Connection) -> list[dict]:
    """Inventorie les modifications à appliquer.

    Returns
    -------
    list de dicts :
        - id, niveau, sequence, num
        - changements : dict[champ → (avant, apres, stats)]
    """
    conn.row_factory = sqlite3.Row
    plan = []
    for r in conn.execute("""
        SELECT id, niveau, sequence, num, recto, verso, variables
          FROM cartes_automatisme
         WHERE etat_code = 'valide'
         ORDER BY niveau, sequence, CAST(num AS INTEGER)
    """):
        changements = {}
        for champ in ('recto', 'verso', 'variables'):
            avant = r[champ] or ''
            apres, stats = migrer_chaine(avant)
            if avant != apres:
                changements[champ] = (avant, apres, stats)
        if changements:
            plan.append({
                'id': r['id'],
                'niveau': r['niveau'],
                'sequence': r['sequence'],
                'num': r['num'],
                'changements': changements,
            })
    return plan


def afficher_plan(plan: list[dict]) -> None:
    """Affiche le détail du plan de migration."""
    if not plan:
        print("✅ Aucune carte à migrer (déjà à jour ou rien à convertir).")
        return

    total = {}
    for entry in plan:
        ident = f"{entry['niveau']}/{entry['sequence']}/CA{entry['num']:02d}"
        print(f"\n--- {ident} (id={entry['id'][:12]}…) ---")
        for champ, (avant, apres, stats) in entry['changements'].items():
            resume = ', '.join(f"{n}× \\{k}" for k, n in stats.items())
            print(f"  [{champ}]  {resume}")
            # Affichage du diff sur les lignes concernées (extraits courts)
            for ligne_avant, ligne_apres in zip(avant.split('\n'),
                                                  apres.split('\n')):
                if ligne_avant != ligne_apres:
                    print(f"    - {ligne_avant.strip()[:100]}")
                    print(f"    + {ligne_apres.strip()[:100]}")
            for k, n in stats.items():
                total[k] = total.get(k, 0) + n

    print(f"\n=== Récapitulatif global ===")
    print(f"Cartes à migrer : {len(plan)}")
    print(f"Substitutions totales :")
    for k, n in sorted(total.items()):
        print(f"  {n:4d} × \\{k}")


def appliquer_plan(conn: sqlite3.Connection, plan: list[dict]) -> None:
    """Applique les modifications à la BDD. Une transaction."""
    cur = conn.cursor()
    for entry in plan:
        params = {}
        sets = []
        for champ, (_avant, apres, _stats) in entry['changements'].items():
            sets.append(f"{champ} = :{champ}")
            params[champ] = apres
        params['id'] = entry['id']
        cur.execute(
            f"UPDATE cartes_automatisme SET {', '.join(sets)} WHERE id = :id",
            params,
        )
    conn.commit()
    print(f"\n✅ {len(plan)} carte(s) migrée(s).")


def sauvegarder_bdd(chemin_db: Path) -> Path:
    """Crée une copie .bak horodatée de la BDD."""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = chemin_db.with_suffix(chemin_db.suffix + f'.{ts}.bak')
    shutil.copy2(chemin_db, bak)
    return bak


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                       formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', type=Path,
                          default=Path(__file__).resolve().parent.parent / 'data' / 'seqenseigne.db',
                          help="Chemin vers la BDD (défaut : appli/data/seqenseigne.db)")
    parser.add_argument('--ecrire', action='store_true',
                          help="Appliquer la migration (sinon dry-run)")
    parser.add_argument('--yes', action='store_true',
                          help="Sauter la confirmation interactive (à utiliser avec précaution)")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"❌ BDD introuvable : {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    try:
        plan = planifier_migration(conn)
        afficher_plan(plan)

        if not args.ecrire:
            print(f"\n💡 Dry-run : aucune modification. "
                  f"Utilisez --ecrire pour appliquer.")
            return 0

        if not plan:
            return 0

        # Confirmation
        if not args.yes:
            print(f"\n⚠️  Vous allez modifier {len(plan)} carte(s) en BDD.")
            print(f"   BDD cible : {args.db}")
            reponse = input("   Tapez 'OUI' pour confirmer : ")
            if reponse.strip() != 'OUI':
                print("Annulé.")
                return 1

        # Sauvegarde
        bak = sauvegarder_bdd(args.db)
        print(f"\n💾 Sauvegarde : {bak}")

        appliquer_plan(conn, plan)
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
