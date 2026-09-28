r"""
scripts/peuplement_14_rapport_dette.py — Rapport de dette de cohérence.

Pour chaque macro détectée comme non-couverte par la vérification de couverture,
retrouve dans quel(s) atome(s) elle est définie et où elle est appelée.

Objectif : produire un plan de remontée dans le paquet ou dans un fichier
de variables partagé au niveau séquence.

Usage :
    python3 scripts/peuplement_14_rapport_dette.py
    python3 scripts/peuplement_14_rapport_dette.py --db <chemin>
    python3 scripts/peuplement_14_rapport_dette.py --md rapport.md
"""

from __future__ import annotations
import argparse
import re
import sqlite3
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

# On réutilise la logique de couverture déjà validée
from scripts.peuplement_14_verif_couverture import (
    couverture,
    extraire_macros_definies_localement,
)


# ── Scan : trouver où une macro est définie ────────────────────────────────────

# Patterns de définition de macros en LaTeX
PATTERNS_DEFINITION = [
    # \newcommand{\foo}[...]{...}  ou  \newcommand\foo[...]{...}
    (r'\\(?:new|renew|provide|DeclareRobust)command\*?\s*'
     r'(?:\{\s*\\([A-Za-z@]+)\s*\}|\\([A-Za-z@]+))',
     'newcommand'),
    # \def\foo{...}
    (r'\\(?:def|edef|gdef|xdef)\\([A-Za-z@]+)',
     'def'),
    # \newenvironment{nom}
    (r'\\(?:new|renew)environment\*?\s*\{\s*([A-Za-z@]+)\s*\}',
     'newenvironment'),
]


def trouver_definitions(conn: sqlite3.Connection,
                        macros_cibles: set[str]) -> dict[str, list[tuple]]:
    """Retourne {nom_macro: [(table, fichier, type_def), ...]}.

    Scanne notions.corps, methodes.corps, exercices.(enonce,corrige,variables).
    """
    # Macros cibles : {'\\foo', 'monenv', ...}
    # On normalise en noms sans backslash pour matcher les patterns env/cmd
    # et on garde en parallèle le set original pour l'appartenance.
    cibles_sans_bs = {n.lstrip('\\') for n in macros_cibles}

    definitions = defaultdict(list)

    sources = [
        ('notions',   'corps',     ['corps']),
        ('methodes',  'corps',     ['corps']),
        ('exercices', 'enonce',    ['enonce', 'corrige', 'variables']),
    ]

    for table, _, champs in sources:
        select = ', '.join(['fichier'] + champs)
        for row in conn.execute(f"SELECT {select} FROM {table}"):
            fichier = row[0]
            for i, champ in enumerate(champs, start=1):
                texte = row[i] or ''
                if not texte:
                    continue
                for pattern, kind in PATTERNS_DEFINITION:
                    for m in re.finditer(pattern, texte):
                        nom = next((g for g in m.groups() if g), None)
                        if nom and nom in cibles_sans_bs:
                            key = ('\\' + nom) if kind != 'newenvironment' else nom
                            definitions[key].append((table, fichier, champ, kind))

    return dict(definitions)


def trouver_appels(conn: sqlite3.Connection,
                   macros_cibles: set[str]) -> dict[str, list[tuple]]:
    """Retourne {nom_macro: [(table, fichier, champ), ...]} des appels."""
    appels = defaultdict(set)   # set pour dédoublonner
    sources = [
        ('notions',   ['corps']),
        ('methodes',  ['corps']),
        ('exercices', ['enonce', 'corrige', 'variables']),
    ]
    # Précompiler un pattern par nom (évite une regex globale coûteuse)
    for table, champs in sources:
        select = ', '.join(['fichier'] + champs)
        for row in conn.execute(f"SELECT {select} FROM {table}"):
            fichier = row[0]
            for i, champ in enumerate(champs, start=1):
                texte = row[i] or ''
                if not texte:
                    continue
                # Neutraliser \\
                texte_n = texte.replace('\\\\', '  ')
                # Extraire tout ce qui commence par \
                for m in re.finditer(r'\\([A-Za-z@]+)', texte_n):
                    nom = '\\' + m.group(1)
                    if nom in macros_cibles:
                        appels[nom].add((table, fichier, champ))
                # Environnements
                for m in re.finditer(r'\\begin\s*\{([^}]+)\}', texte_n):
                    env = m.group(1).strip()
                    if env in macros_cibles:
                        appels[env].add((table, fichier, champ))
    return {k: sorted(v) for k, v in appels.items()}


# ── Construction du rapport ───────────────────────────────────────────────────

def construire_rapport(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    try:
        cov = couverture(conn)
        non_couverts = [e['nom'] for e in cov['non_couvert']]
        definitions = trouver_definitions(conn, set(non_couverts))
        appels = trouver_appels(conn, set(non_couverts))
    finally:
        conn.close()

    items = []
    for nom in non_couverts:
        defs = definitions.get(nom, [])
        calls = appels.get(nom, [])
        items.append({
            'nom': nom,
            'definitions': defs,       # [(table, fichier, champ, kind)]
            'appels': calls,           # [(table, fichier, champ)]
            'nb_appels': len(calls),
            'nb_definitions': len(defs),
        })

    # Classer : macros définies ailleurs (dette) vs vraies inconnues
    avec_definition = [i for i in items if i['nb_definitions'] > 0]
    sans_definition = [i for i in items if i['nb_definitions'] == 0]

    return {
        'total_non_couverts': len(non_couverts),
        'avec_definition': avec_definition,
        'sans_definition': sans_definition,
    }


# ── Formatage texte ───────────────────────────────────────────────────────────

def formatter_texte(rapport: dict) -> str:
    out = []
    out.append('=' * 70)
    out.append('Rapport de dette de cohérence — macros non-couvertes')
    out.append('=' * 70)
    out.append('')
    out.append(f"Total macros non-couvertes : {rapport['total_non_couverts']}")
    out.append(f"  Définies quelque part dans les atomes (DETTE) : {len(rapport['avec_definition'])}")
    out.append(f"  Sans définition trouvée                       : {len(rapport['sans_definition'])}")
    out.append('')

    if rapport['avec_definition']:
        out.append('─' * 70)
        out.append('Catégorie 1 — Macros définies dans un atome (à remonter)')
        out.append('─' * 70)
        out.append('')
        for item in rapport['avec_definition']:
            out.append(f"◆ {item['nom']}  ({item['nb_appels']} appel(s))")
            out.append('  Définitions trouvées :')
            for table, fichier, champ, kind in item['definitions']:
                out.append(f"    • {kind:15s} dans {table}:{fichier} ({champ})")
            out.append('  Appelée depuis :')
            for table, fichier, champ in item['appels'][:10]:
                out.append(f"    • {table}:{fichier} ({champ})")
            if len(item['appels']) > 10:
                out.append(f"    • … et {len(item['appels']) - 10} autres")
            out.append('')

    if rapport['sans_definition']:
        out.append('─' * 70)
        out.append('Catégorie 2 — Macros sans définition trouvée (probables bugs)')
        out.append('─' * 70)
        out.append('')
        for item in rapport['sans_definition']:
            out.append(f"◆ {item['nom']}  ({item['nb_appels']} appel(s))")
            out.append('  Appelée depuis :')
            for table, fichier, champ in item['appels'][:10]:
                out.append(f"    • {table}:{fichier} ({champ})")
            if len(item['appels']) > 10:
                out.append(f"    • … et {len(item['appels']) - 10} autres")
            out.append('')

    return '\n'.join(out)


# ── Formatage Markdown ────────────────────────────────────────────────────────

def formatter_markdown(rapport: dict) -> str:
    out = []
    out.append('# Rapport de dette de cohérence — macros non-couvertes')
    out.append('')
    out.append(f"**Total macros non-couvertes** : {rapport['total_non_couverts']}")
    out.append('')
    out.append(f"- Définies dans un atome (dette à remonter) : "
               f"**{len(rapport['avec_definition'])}**")
    out.append(f"- Sans définition trouvée : **{len(rapport['sans_definition'])}**")
    out.append('')

    if rapport['avec_definition']:
        out.append('## Catégorie 1 — Macros définies dans un atome (à remonter)')
        out.append('')
        out.append('Ces macros ont été définies directement dans un livret ou dans les '
                   '`variables` d\'un exercice, puis réutilisées depuis d\'autres '
                   'atomes de la même séquence. Deux chemins de résolution :')
        out.append('')
        out.append('1. **Remontée dans le paquet** si la macro est d\'intérêt général '
                   '(cas type : `\\boiteJauneModere`, `\\seqTitreTabV`).')
        out.append('2. **Fichier de variables de séquence partagé** si la macro est '
                   'spécifique à une séquence (cas type : figures tkz construites par '
                   'un exercice et réutilisées par les suivants).')
        out.append('')
        for item in rapport['avec_definition']:
            out.append(f"### `{item['nom']}`")
            out.append('')
            out.append(f"**{item['nb_appels']} appel(s)** — "
                       f"**{item['nb_definitions']} définition(s) trouvée(s)**")
            out.append('')
            out.append('**Définitions :**')
            out.append('')
            out.append('| Table | Fichier | Champ | Type |')
            out.append('|---|---|---|---|')
            for table, fichier, champ, kind in item['definitions']:
                out.append(f"| {table} | `{fichier}` | {champ} | {kind} |")
            out.append('')
            out.append('**Appels :**')
            out.append('')
            out.append('| Table | Fichier | Champ |')
            out.append('|---|---|---|')
            for table, fichier, champ in item['appels'][:15]:
                out.append(f"| {table} | `{fichier}` | {champ} |")
            if len(item['appels']) > 15:
                out.append(f"| … | … et {len(item['appels']) - 15} autres | … |")
            out.append('')

    if rapport['sans_definition']:
        out.append('## Catégorie 2 — Macros sans définition trouvée')
        out.append('')
        out.append('Aucune définition détectée dans les atomes ni dans le paquet. '
                   'Probables bugs dormants (les atomes concernés ne doivent pas '
                   'compiler en isolation, et peut-être pas en livret non plus si '
                   'la macro n\'est définie nulle part).')
        out.append('')
        for item in rapport['sans_definition']:
            out.append(f"### `{item['nom']}`")
            out.append('')
            out.append(f"**{item['nb_appels']} appel(s)**")
            out.append('')
            out.append('**Appels :**')
            out.append('')
            out.append('| Table | Fichier | Champ |')
            out.append('|---|---|---|')
            for table, fichier, champ in item['appels'][:15]:
                out.append(f"| {table} | `{fichier}` | {champ} |")
            if len(item['appels']) > 15:
                out.append(f"| … | … et {len(item['appels']) - 15} autres | … |")
            out.append('')

    return '\n'.join(out)


def main() -> int:
    racine = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path,
                        default=racine / 'data' / 'seqenseigne.db')
    parser.add_argument('--md', type=Path, default=None,
                        help='Si précisé, écrit le rapport en Markdown')
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERREUR : base introuvable à {args.db}", file=sys.stderr)
        return 2

    rapport = construire_rapport(args.db)
    print(formatter_texte(rapport))

    if args.md:
        args.md.write_text(formatter_markdown(rapport), encoding='utf-8')
        print(f"\nRapport Markdown écrit : {args.md}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
