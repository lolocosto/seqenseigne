r"""
scripts/peuplement_14_paquet_vers_base.py — Chantier 14.

Parse les fichiers .sty du paquet seqenseigne et peuple les tables
`paquet_definitions` et `paquet_requirepackage`.

Étapes :
  1. Crée les tables si absentes (DDL idempotent).
  2. Vide les tables (rescan complet à chaque lancement).
  3. Pour chaque .sty (core, core-exos, core-eval, theme, data, legacy) :
     - parse et extrait les définitions
     - applique les règles de rendu atomique (services/paquet_regles_atome)
     - insère les définitions en base
     - extrait les \RequirePackage

Usage :
    cd appli
    ..\outils\python\python.exe scripts\peuplement_14_paquet_vers_base.py \
        --paquet ../reference/seqenseigne/paquet

En CI / test :
    python3 scripts/peuplement_14_paquet_vers_base.py --paquet <chemin> --db <chemin>
"""

from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Permettre l'import de services depuis scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.paquet_parseur import (
    parser_sty, extraire_requirepackage, Definition,
)
from services.paquet_regles_atome import (
    statut_de, REGLES, STATUT_REUTILISE, STATUT_REECRIT, STATUT_IGNORE,
)


# ── DDL idempotent ─────────────────────────────────────────────────────────────

DDL_PAQUET = r"""
-- Table des définitions extraites des .sty du paquet seqenseigne.
-- Une ligne = une \newcommand, \newenvironment, \newtcolorbox, etc.
CREATE TABLE IF NOT EXISTS paquet_definitions (
    nom               TEXT PRIMARY KEY,       -- '\seqFrac', 'seqNotion', 'boiteTitreGen'
    type_latex        TEXT NOT NULL,          -- 'command' | 'environment' | 'tcolorbox' | ...
    args_spec         TEXT NOT NULL DEFAULT '',  -- '' | '[2]' | '[1][]'
    corps             TEXT NOT NULL DEFAULT '',
    corps_fin         TEXT NOT NULL DEFAULT '',  -- uniquement pour environment
    texte_complet     TEXT NOT NULL,          -- source brut complet, pour diff/traçabilité
    fichier_source    TEXT NOT NULL,          -- 'seqenseigne-core.sty', etc.
    ligne_debut       INTEGER NOT NULL,
    -- Dépendances détectées dans le corps
    macros_appelees          TEXT NOT NULL DEFAULT '[]',    -- JSON : liste de strings
    environnements_utilises  TEXT NOT NULL DEFAULT '[]',    -- JSON : liste de strings
    -- Stratégie de rendu atomique
    statut_rendu_atome       TEXT NOT NULL DEFAULT 'reutilise'
        CHECK (statut_rendu_atome IN ('reutilise', 'reecrit', 'ignore')),
    contenu_atome            TEXT NOT NULL DEFAULT ''
        -- Rempli uniquement si statut = 'reecrit'
);

CREATE INDEX IF NOT EXISTS idx_paquet_def_fichier
    ON paquet_definitions (fichier_source);
CREATE INDEX IF NOT EXISTS idx_paquet_def_type
    ON paquet_definitions (type_latex);
CREATE INDEX IF NOT EXISTS idx_paquet_def_statut
    ON paquet_definitions (statut_rendu_atome);

-- Table des paquets LaTeX externes requis par chaque .sty.
-- Clé composite : fichier_source + nom_paquet (un paquet peut être re-listé).
CREATE TABLE IF NOT EXISTS paquet_requirepackage (
    fichier_source TEXT NOT NULL,             -- 'seqenseigne-core.sty'
    ordre          INTEGER NOT NULL,          -- ordre d'apparition dans le .sty
    nom            TEXT NOT NULL,             -- 'tikz', 'tabularray', 'pifont'
    options        TEXT NOT NULL DEFAULT '',  -- 'theorems,breakable,skins'
    PRIMARY KEY (fichier_source, ordre)
);

CREATE INDEX IF NOT EXISTS idx_paquet_req_nom
    ON paquet_requirepackage (nom);
"""


def creer_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL_PAQUET)
    conn.commit()


def vider_tables(conn: sqlite3.Connection) -> None:
    """Rescan complet : on vide et on repart de zéro."""
    conn.execute("DELETE FROM paquet_definitions")
    conn.execute("DELETE FROM paquet_requirepackage")
    conn.commit()


# ── Peuplement d'un .sty ──────────────────────────────────────────────────────

FICHIERS_ORDRE = [
    'seqenseigne-core.sty',
    'seqenseigne-core-exos.sty',   # ← v0.11.5+ : extrait de core
    'seqenseigne-core-eval.sty',   # ← v0.13.5.2+ : module évaluation
    'seqenseigne-theme.sty',
    'seqenseigne-data.sty',
    'seqenseigne-legacy.sty',
    # ← v0.13.6.2.1 : nouveau module pour les cartes d'automatisme
    # (remplace seqenseigne-flashcard.sty qui n'avait jamais été
    # peuplé non plus). À la livraison v0.13.6.2 j'avais oublié
    # d'ajouter ici, donc le peuplement 14 ne le scannait pas et
    # \seqCarteAuto n'apparaissait pas dans paquet_definitions.
    'seqenseigne-carte-automatisme.sty',
]


def inserer_definitions(conn: sqlite3.Connection,
                        defs: list[Definition]) -> dict:
    """Insère les définitions en base avec application des règles de statut.

    Retourne un compteur par statut.
    """
    compteurs = {STATUT_REUTILISE: 0, STATUT_REECRIT: 0, STATUT_IGNORE: 0,
                 'doublons_ecrases': 0}

    for d in defs:
        statut, contenu = statut_de(d.nom)
        compteurs[statut] += 1

        # Si doublon (même nom déjà en base), on écrase — le dernier parsé
        # gagne. Cas connu : \ifdocstd redéfini dans plusieurs .sty.
        row = conn.execute(
            "SELECT nom FROM paquet_definitions WHERE nom = ?", (d.nom,)
        ).fetchone()
        if row:
            compteurs['doublons_ecrases'] += 1
            conn.execute("DELETE FROM paquet_definitions WHERE nom = ?", (d.nom,))

        conn.execute("""
            INSERT INTO paquet_definitions (
                nom, type_latex, args_spec, corps, corps_fin,
                texte_complet, fichier_source, ligne_debut,
                macros_appelees, environnements_utilises,
                statut_rendu_atome, contenu_atome
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            d.nom, d.type_latex, d.args_spec, d.corps, d.corps_fin,
            d.texte_complet, d.fichier_source, d.ligne_debut,
            json.dumps(sorted(d.macros_appelees), ensure_ascii=False),
            json.dumps(sorted(d.environnements_utilises), ensure_ascii=False),
            statut, contenu or '',
        ))

    return compteurs


def inserer_requirepackage(conn: sqlite3.Connection,
                           fichier: str,
                           paquets: list[tuple[str, str]]) -> None:
    """Insère les paquets TeX requis par ce fichier."""
    for ordre, (nom, options) in enumerate(paquets):
        conn.execute("""
            INSERT INTO paquet_requirepackage (fichier_source, ordre, nom, options)
            VALUES (?, ?, ?, ?)
        """, (fichier, ordre, nom, options))


# ── Vérification : règles orphelines ──────────────────────────────────────────

def regles_orphelines(conn: sqlite3.Connection) -> list[str]:
    """Retourne les noms de règles qui ne correspondent à aucune définition
    en base. Indicateur d'un bug de règle (faute de frappe, nom périmé…).

    Attention : certaines règles visent volontairement des macros de paquets
    externes (pas seqenseigne). À analyser au cas par cas.
    """
    noms_en_base = {
        row[0] for row in conn.execute("SELECT nom FROM paquet_definitions")
    }
    return sorted(n for n in REGLES if n not in noms_en_base)


# ── main ──────────────────────────────────────────────────────────────────────

def peupler(db_path: Path, paquet_dir: Path) -> dict:
    """Exécute le peuplement complet. Retourne un rapport."""
    if not paquet_dir.exists():
        raise FileNotFoundError(f"Dossier paquet introuvable : {paquet_dir}")
    for fn in FICHIERS_ORDRE:
        if not (paquet_dir / fn).exists():
            raise FileNotFoundError(f"Fichier paquet manquant : {paquet_dir / fn}")

    # Créer la base si absente
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        creer_tables(conn)
        vider_tables(conn)

        rapport_par_fichier = {}
        total_defs = 0
        compteurs_globaux = {
            STATUT_REUTILISE: 0, STATUT_REECRIT: 0, STATUT_IGNORE: 0,
            'doublons_ecrases': 0,
        }

        for fn in FICHIERS_ORDRE:
            src = (paquet_dir / fn).read_text(encoding='utf-8')
            defs = parser_sty(src, fichier_source=fn)
            pkgs = extraire_requirepackage(src)

            compteurs = inserer_definitions(conn, defs)
            inserer_requirepackage(conn, fn, pkgs)
            conn.commit()

            total_defs += len(defs)
            for k, v in compteurs.items():
                compteurs_globaux[k] = compteurs_globaux.get(k, 0) + v
            rapport_par_fichier[fn] = {
                'definitions': len(defs),
                'paquets_tex': len(pkgs),
                'par_statut': {k: v for k, v in compteurs.items()
                               if k != 'doublons_ecrases'},
            }

        orphelines = regles_orphelines(conn)

        return {
            'ok': True,
            'total_definitions': total_defs,
            'par_fichier': rapport_par_fichier,
            'par_statut': compteurs_globaux,
            'regles_orphelines': orphelines,
        }
    finally:
        conn.close()


def formatter_rapport(rapport: dict) -> str:
    out = []
    out.append('=' * 60)
    out.append('Peuplement 14 — Paquet seqenseigne → base')
    out.append('=' * 60)
    out.append(f"Total : {rapport['total_definitions']} définitions")
    out.append('')
    out.append('Par fichier :')
    for fn, info in rapport['par_fichier'].items():
        out.append(
            f"  {fn:30s} {info['definitions']:3d} defs, "
            f"{info['paquets_tex']:2d} \\RequirePackage"
        )
        stats = info['par_statut']
        out.append(
            f"    → reutilise: {stats[STATUT_REUTILISE]}"
            f"   reecrit: {stats[STATUT_REECRIT]}"
            f"   ignore: {stats[STATUT_IGNORE]}"
        )
    out.append('')
    out.append('Globaux :')
    stats = rapport['par_statut']
    out.append(f"  reutilise     : {stats[STATUT_REUTILISE]}")
    out.append(f"  reecrit       : {stats[STATUT_REECRIT]}")
    out.append(f"  ignore        : {stats[STATUT_IGNORE]}")
    out.append(f"  doublons écrasés : {stats['doublons_ecrases']}")
    out.append('')
    orph = rapport['regles_orphelines']
    if orph:
        out.append(f'⚠  {len(orph)} règle(s) orpheline(s) (nom non trouvé en base) :')
        for n in orph:
            out.append(f'    {n}')
    else:
        out.append('✓ Toutes les règles explicites correspondent à une définition en base.')
    return '\n'.join(out)


def main() -> int:
    racine = Path(__file__).parent.parent

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--paquet', type=Path,
        default=racine.parent / 'reference' / 'seqenseigne' / 'paquet',
        help='Dossier contenant les .sty du paquet seqenseigne',
    )
    parser.add_argument(
        '--db', type=Path,
        default=racine / 'data' / 'seqenseigne.db',
        help='Chemin de la base SQLite',
    )
    args = parser.parse_args()

    try:
        rapport = peupler(args.db, args.paquet)
    except Exception as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        return 2

    print(formatter_rapport(rapport))
    return 0 if not rapport['regles_orphelines'] else 1  # 1 = warning, 0 = nominal


if __name__ == '__main__':
    sys.exit(main())
