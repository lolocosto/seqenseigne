r"""
scripts/peuplement_14_verif_couverture.py — Chantier 14.

Analyse les 1 124 atomes en base (notions, méthodes, exercices) et vérifie
que toutes les macros/environnements qu'ils utilisent sont couverts par les
définitions de paquet_definitions.

Sortie : rapport détaillé des macros utilisées vs couvertes/non couvertes,
avec les fichiers atomes impactés.

Usage :
    cd appli
    python3 scripts/peuplement_14_verif_couverture.py
    python3 scripts/peuplement_14_verif_couverture.py --db <chemin>
    python3 scripts/peuplement_14_verif_couverture.py --csv rapport.csv
"""

from __future__ import annotations
import argparse
import csv
import re
import sqlite3
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.paquet_parseur import (
    PRIMITIVES_LATEX,
    MACROS_PAQUETS_EXTERNES,
    extraire_utilisations,
    extraire_macros_definies_localement,
)

# ── Collecte des utilisations dans les atomes BDD ─────────────────────────────

def scanner_atomes(conn: sqlite3.Connection) -> dict[str, dict]:
    """Retourne {nom_macro_ou_env: {'macro'|'env', 'atomes': [(table, fichier), ...]}}."""
    utilisation = defaultdict(lambda: {'type': None, 'atomes': []})

    # Notions : champ corps
    for fichier, corps in conn.execute("SELECT fichier, corps FROM notions"):
        texte = corps or ''
        macros_locales = extraire_macros_definies_localement(texte)
        macros, envs = extraire_utilisations(texte)
        macros -= macros_locales
        for m in macros:
            utilisation[m]['type'] = 'macro'
            utilisation[m]['atomes'].append(('notion', fichier))
        for e in envs:
            utilisation[e]['type'] = 'env'
            utilisation[e]['atomes'].append(('notion', fichier))

    # Items de sections d'atome (v0.6.4 : ex-items_texte → atome_section_items)
    try:
        for row in conn.execute("SELECT corps FROM atome_section_items"):
            texte = row[0] or ''
            macros_locales = extraire_macros_definies_localement(texte)
            macros, envs = extraire_utilisations(texte)
            macros -= macros_locales
            for m in macros:
                utilisation[m]['type'] = 'macro'
                utilisation[m]['atomes'].append(('atome_section_items', '?'))
            for e in envs:
                utilisation[e]['type'] = 'env'
                utilisation[e]['atomes'].append(('atome_section_items', '?'))
    except sqlite3.OperationalError:
        pass

    # Méthodes : champ corps
    for fichier, corps in conn.execute("SELECT fichier, corps FROM methodes"):
        texte = corps or ''
        macros_locales = extraire_macros_definies_localement(texte)
        macros, envs = extraire_utilisations(texte)
        macros -= macros_locales
        for m in macros:
            utilisation[m]['type'] = 'macro'
            utilisation[m]['atomes'].append(('methode', fichier))
        for e in envs:
            utilisation[e]['type'] = 'env'
            utilisation[e]['atomes'].append(('methode', fichier))

    # Exercices : enonce + corrige + variables
    # ATTENTION : les macros définies localement dans l'un des champs
    # (\newcommand\denomTexte{}, \def\fmt{...}, etc.) ne sont pas des
    # dépendances externes. On les collecte dans TOUS les champs et on les exclut.
    for fichier, enonce, corrige, variables in conn.execute(
        "SELECT fichier, enonce, corrige, variables FROM exercices"
    ):
        texte_complet = '\n'.join([enonce or '', corrige or '', variables or ''])
        macros_locales = extraire_macros_definies_localement(texte_complet)

        for src in [enonce, corrige, variables]:
            macros, envs = extraire_utilisations(src or '')
            macros -= macros_locales
            for m in macros:
                utilisation[m]['type'] = 'macro'
                utilisation[m]['atomes'].append(('exercice', fichier))
            for e in envs:
                utilisation[e]['type'] = 'env'
                utilisation[e]['atomes'].append(('exercice', fichier))

    return dict(utilisation)


# ── Analyse de couverture ─────────────────────────────────────────────────────

def couverture(conn: sqlite3.Connection) -> dict:
    """Retourne le rapport de couverture complet."""
    # 1) Ce qu'on sait faire : définitions du paquet + paquets externes connus
    noms_paquet = {
        row[0] for row in conn.execute("SELECT nom FROM paquet_definitions")
    }

    # Définitions de séquence (NXX_SYY_param.tex) — valides pour les atomes
    # de la séquence correspondante. On construit une map
    # {(niveau, sequence): set(noms_de_macros)}.
    noms_sequence: dict[tuple[str, str], set[str]] = {}
    try:
        for niv, seq, nom in conn.execute(
            "SELECT niveau, sequence, nom FROM paquet_definitions_sequence"
        ):
            noms_sequence.setdefault((niv, seq), set()).add(nom)
    except sqlite3.OperationalError:
        # Table absente (peuplement_14_sequence_params non lancé) → OK,
        # on continue sans ces définitions
        pass

    # 2) Ce qu'on utilise dans les atomes (avec infos de séquence pour matcher
    #    contre noms_sequence)
    utilisation = scanner_atomes(conn)

    # 3) Classer chaque utilisation
    couvert_paquet = []
    couvert_sequence = []
    couvert_externe = []
    non_couvert = []

    for nom, info in sorted(utilisation.items()):
        nb_atomes = len(info['atomes'])
        fichiers_uniques = sorted(set(a[1] for a in info['atomes']))[:5]

        # Un nom est couvert par une définition de séquence s'il existe
        # pour TOUTES les (niveau, sequence) dont proviennent les appels.
        # C-à-d : pour chaque fichier qui appelle ce nom, sa (niv, seq)
        # doit avoir la définition.
        niv_seq_appels = _extraire_niveaux_sequences(info['atomes'])

        if nom in noms_paquet:
            couvert_paquet.append({
                'nom': nom, 'type': info['type'],
                'nb_atomes': nb_atomes,
                'exemples': fichiers_uniques,
            })
        elif niv_seq_appels and all(
            nom in noms_sequence.get(ns, set()) for ns in niv_seq_appels
        ):
            couvert_sequence.append({
                'nom': nom, 'type': info['type'],
                'nb_atomes': nb_atomes,
                'exemples': fichiers_uniques,
                'niveaux_sequences': sorted(niv_seq_appels),
            })
        elif nom in MACROS_PAQUETS_EXTERNES:
            couvert_externe.append({
                'nom': nom, 'type': info['type'],
                'paquet_tex': MACROS_PAQUETS_EXTERNES[nom],
                'nb_atomes': nb_atomes,
                'exemples': fichiers_uniques,
            })
        else:
            non_couvert.append({
                'nom': nom, 'type': info['type'],
                'nb_atomes': nb_atomes,
                'exemples': fichiers_uniques,
                'niveaux_sequences': sorted(niv_seq_appels),
            })

    non_couvert.sort(key=lambda x: -x['nb_atomes'])

    return {
        'total_utilisations': len(utilisation),
        'couvert_paquet': couvert_paquet,
        'couvert_sequence': couvert_sequence,
        'couvert_externe': couvert_externe,
        'non_couvert': non_couvert,
    }


_RE_NIV_SEQ_FICHIER = re.compile(r'^(N\d{2})[_]?(S\d{2})')


def _extraire_niveaux_sequences(atomes: list) -> set[tuple[str, str]]:
    """Depuis [(table, fichier), ...], extrait l'ensemble des (niveau, sequence)
    correspondants. Accepte les formats 'N12S11A01.tex', 'N11_S08_Methode_01.tex',
    'N10_S05_Notion_02.tex'."""
    result = set()
    for _, fichier in atomes:
        if not fichier or fichier == '?':
            continue
        m = _RE_NIV_SEQ_FICHIER.match(fichier)
        if m:
            result.add((m.group(1), m.group(2)))
    return result


def formatter_rapport(rapport: dict) -> str:
    out = []
    out.append('=' * 70)
    out.append('Vérification de couverture — atomes BDD × paquet seqenseigne')
    out.append('=' * 70)
    out.append(f"Total noms distincts utilisés : {rapport['total_utilisations']}")
    out.append(f"  Couverts par paquet_definitions          : {len(rapport['couvert_paquet'])}")
    out.append(f"  Couverts par définitions de séquence      : {len(rapport.get('couvert_sequence', []))}")
    out.append(f"  Couverts par paquets TeX externes connus : {len(rapport['couvert_externe'])}")
    out.append(f"  NON couverts : {len(rapport['non_couvert'])}")
    out.append('')

    # Paquets externes utilisés, groupés
    externes_par_paquet = defaultdict(list)
    for e in rapport['couvert_externe']:
        externes_par_paquet[e['paquet_tex']].append(e)

    out.append('Paquets TeX externes utilisés (par fréquence) :')
    for pkg, entries in sorted(externes_par_paquet.items(),
                                 key=lambda x: -sum(e['nb_atomes'] for e in x[1])):
        total = sum(e['nb_atomes'] for e in entries)
        out.append(f"  {pkg:20s} {len(entries):2d} macros/envs, {total:5d} usages total")

    if rapport.get('couvert_sequence'):
        out.append('')
        out.append('Définitions de séquence utilisées :')
        for e in rapport['couvert_sequence']:
            ns = ', '.join(f"{n}/{s}" for n, s in e['niveaux_sequences'])
            out.append(
                f"  {e['nom']:30s} {e['nb_atomes']:3d}x  → {ns}"
            )

    out.append('')
    if rapport['non_couvert']:
        out.append(f'⚠  {len(rapport["non_couvert"])} nom(s) non couvert(s) :')
        for e in rapport['non_couvert'][:50]:
            fichiers = ', '.join(e['exemples'][:3])
            if len(e['exemples']) > 3:
                fichiers += ', …'
            out.append(
                f'  [{e["type"]:5s}] {e["nom"]:40s} '
                f'{e["nb_atomes"]:4d}x  ex: {fichiers}'
            )
        if len(rapport['non_couvert']) > 50:
            out.append(f'  ... et {len(rapport["non_couvert"]) - 50} autres')
    else:
        out.append('✓ Tous les noms utilisés sont couverts.')

    return '\n'.join(out)


def main() -> int:
    racine = Path(__file__).parent.parent

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--db', type=Path,
        default=racine / 'data' / 'seqenseigne.db',
        help='Chemin de la base SQLite (doit être peuplée)',
    )
    parser.add_argument(
        '--csv', type=Path, default=None,
        help='Si précisé, écrit le rapport des non-couverts en CSV',
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERREUR : base introuvable à {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(args.db))
    try:
        rapport = couverture(conn)
    finally:
        conn.close()

    print(formatter_rapport(rapport))

    if args.csv:
        with open(args.csv, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(['type', 'nom', 'nb_atomes', 'fichiers_exemples'])
            for e in rapport['non_couvert']:
                w.writerow([e['type'], e['nom'], e['nb_atomes'],
                            '|'.join(e['exemples'])])
        print(f"\nRapport CSV écrit : {args.csv}")

    return 0 if not rapport['non_couvert'] else 1


if __name__ == '__main__':
    sys.exit(main())
