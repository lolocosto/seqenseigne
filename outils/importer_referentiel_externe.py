"""outils/importer_referentiel_externe.py — v0.15.2.10

Reconstitution rétroactive du dossier `_verrouille/` d'un référentiel qui a
été utilisé HORS du système (PDF produits manuellement par l'enseignant
avant que le système de verrouillage automatisé n'existe).

Cas d'usage type (Laurent, mai 2026)
-----------------------------------
- Le référentiel `N11_v2025` est déjà à l'état `verrouille` en BDD
  (verrouillé après verrouillage minimal pré-v0.15.2.9).
- Sa structure pédagogique est complète en BDD (sequences, objectifs,
  atomes).
- Les PDFs ont été générés en externe ; ils ne sont liés à aucune ligne
  `referentiel_documents`.
- On veut RÉTROACTIVEMENT créer le dossier `<ref>/_verrouille/` (trace.json +
  pdfs/) pour ce référentiel.

Cet outil :
1. Génère `trace.json` depuis la BDD actuelle (utilise `generer_trace`
   du service `referentiel_verrouillage`), en y intégrant les PDFs externes
   comme `documents` avec `provenance: 'externe'`.
2. Copie les PDFs du dossier source vers `<ref>/_verrouille/pdfs/` en les
   renommant selon la convention seqenseigne
   (`livret_sequence__<niveau>__<sequence>.pdf` pour les livrets de
   séquence).
3. NE TOUCHE PAS à l'état BDD du référentiel.

Mapping des PDFs : par défaut, regex sur le nom :
  - `*_S<NN>_Livret.pdf`  → livret_sequence, séquence S<NN>

Un override par fichier CSV `mapping.csv` peut être fourni si les noms
ne suivent pas la convention par défaut. Format CSV : trois colonnes
sans en-tête : `fichier_source ; type_document ; sequence`.

Usage CLI
---------
::

    python -m outils.importer_referentiel_externe \\
        --ref-id      N11_v2025 \\
        --pdfs-source /chemin/vers/dossier/de/pdfs \\
        --data-dir    /chemin/vers/data \\
        [--mapping    /chemin/vers/mapping.csv] \\
        [--dry-run]

Exemple :
    python -m outils.importer_referentiel_externe \\
        --ref-id N11_v2025 \\
        --pdfs-source ~/PDFs_4e_2025 \\
        --data-dir ./data

Idempotence
-----------
Le dossier `<ref>/_verrouille/` est SUPPRIMÉ puis recréé à chaque exécution :
on peut relancer l'outil autant de fois que nécessaire pour ajuster
le mapping ou ajouter des PDFs.

Le mode `--dry-run` affiche ce qui SERAIT fait sans rien modifier.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path


_RE_LIVRET_SEQUENCE = re.compile(r'^[^/]*?S(\d{2})_Livret\.pdf$',
                                   re.IGNORECASE)
# v0.15.2.12.2 — non-greedy `[^/]*?` au lieu de `[^/]*_` : tolère
# n'importe quel séparateur (espace, tiret, underscore, ou aucun)
# entre le préfixe et `S<NN>_Livret.pdf`. Couvre les conventions
# de nommage variées rencontrées chez les enseignants
# (`4e3 S01_Livret.pdf`, `4e3-S01_Livret.pdf`, `S01_Livret.pdf`…).


def _detecter_mapping_par_defaut(nom_fichier: str) -> tuple[str, str] | None:
    """Retourne (type_document, sequence) ou None si pas de match.

    Conventions reconnues :
      - `<prefix>_S<NN>_Livret.pdf` → livret_sequence, S<NN>

    Ajouter d'autres conventions ici quand nécessaire (livret_corriges,
    livret_fiches, livret_cartes_*, etc.).
    """
    m = _RE_LIVRET_SEQUENCE.match(nom_fichier)
    if m:
        return ('livret_sequence', f'S{m.group(1)}')
    return None


def _charger_mapping_csv(chemin: Path) -> dict[str, tuple[str, str]]:
    """Charge un mapping explicite depuis un CSV à 3 colonnes
    (fichier_source ; type_document ; sequence). Pas d'en-tête."""
    mapping: dict[str, tuple[str, str]] = {}
    with chemin.open(encoding='utf-8') as f:
        rdr = csv.reader(f, delimiter=';')
        for ligne_num, ligne in enumerate(rdr, 1):
            if not ligne or all(c.strip() == '' for c in ligne):
                continue
            if ligne[0].strip().startswith('#'):
                continue
            if len(ligne) < 3:
                print(f"⚠ ligne {ligne_num} ignorée (3 colonnes attendues) : "
                      f"{ligne!r}", file=sys.stderr)
                continue
            fichier, type_doc, sequence = (c.strip() for c in ligne[:3])
            mapping[fichier] = (type_doc, sequence)
    return mapping


def _nom_metier(niveau: str, type_doc: str, sequence: str | None) -> str:
    """Calcule le nom de fichier "métier" seqenseigne pour ce document.

    Convention identique à celle utilisée par `lister_cibles_document` :
      - livret_sequence/livret_cartes_planches/livret_corriges →
        `<type>__<niveau>__<sequence>.pdf` (par séquence)
      - autres types (niveau global) →
        `<type>__<niveau>.pdf`
    """
    if sequence:
        return f"{type_doc}__{niveau}__{sequence}.pdf"
    return f"{type_doc}__{niveau}.pdf"


def importer(ref_id: str,
              pdfs_source: Path,
              data_dir: Path,
              mapping_csv: Path | None = None,
              dry_run: bool = False) -> dict:
    """Importe les PDFs externes d'un référentiel dans son dossier `_verrouille/`.

    Retourne un rapport :
      {
        'ref_id': ...,
        'niveau': ...,
        'dossier_verrouille': str,
        'pdfs_copies': [{'source', 'destination', 'type_doc', 'sequence'}],
        'pdfs_non_mappes': [str],
        'trace': str | None,
        'dry_run': bool,
      }
    """
    db_path = data_dir / 'seqenseigne.db'
    if not db_path.is_file():
        raise FileNotFoundError(f"BDD introuvable : {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, niveau, etat FROM referentiel_niveaux WHERE id = ?",
            (ref_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Référentiel introuvable en BDD : {ref_id}")
        niveau = row['niveau']
        etat   = row['etat']

        # Préparation mapping
        mapping_csv_data = (_charger_mapping_csv(mapping_csv)
                             if mapping_csv else {})

        # Inventaire des PDFs source
        if not pdfs_source.is_dir():
            raise FileNotFoundError(
                f"Dossier de PDFs source introuvable : {pdfs_source}"
            )
        pdfs = sorted(pdfs_source.glob('*.pdf'))

        # Résolution du mapping pour chaque PDF
        cibles_pdf: list[dict] = []
        non_mappes: list[str] = []
        for pdf in pdfs:
            if pdf.name in mapping_csv_data:
                type_doc, sequence = mapping_csv_data[pdf.name]
            else:
                detected = _detecter_mapping_par_defaut(pdf.name)
                if detected is None:
                    non_mappes.append(pdf.name)
                    continue
                type_doc, sequence = detected
            cibles_pdf.append({
                'source_pdf':   pdf,
                'type_doc':     type_doc,
                'sequence':     sequence,
                'nom_metier':   _nom_metier(niveau, type_doc, sequence),
            })

        # Dossier figé cible
        dossier_ref = data_dir / 'referentiels' / ref_id
        dossier_verrouille = dossier_ref / '_verrouille'

        # Génération de la trace JSON depuis BDD
        # Import déféré : services importables seulement si on est dans
        # l'arborescence appli/ ou avec le PYTHONPATH posé.
        try:
            sys.path.insert(0, str(data_dir.parent))
        except Exception:
            pass
        from services.referentiel_figeage import generer_trace
        try:
            from services.referentiel_documents_compilation import (
                lister_cibles_document,
            )
        except Exception:
            # Fallback si on est appelé hors-app : pas de cibles BDD
            def lister_cibles_document(conn, doc_id, ref_id, type_doc):
                return []

        trace = generer_trace(conn, ref_id, lister_cibles_document)

        # Enrichissement : ajouter les PDFs externes comme documents
        # avec provenance='externe'.
        for c in cibles_pdf:
            trace['documents'].append({
                'id':            f"externe_{c['type_doc']}_{c['sequence'] or ''}",
                'type_document': c['type_doc'],
                'options':       {'actif': True, 'provenance': 'externe'},
                'compile_date':  None,
                'provenance':    'externe',
                'cibles': [{
                    'cible_id':    (f"{niveau}/{c['sequence']}"
                                     if c['sequence'] else 'unique'),
                    'libelle':     f"{c['type_doc']} {niveau}"
                                    + (f"/{c['sequence']}"
                                        if c['sequence'] else ''),
                    'nom_fichier': c['nom_metier'],
                    'chemin_pdf':  f"pdfs/{c['nom_metier']}",
                }],
            })

        rapport = {
            'ref_id':           ref_id,
            'niveau':           niveau,
            'etat_referentiel': etat,
            'dossier_verrouille':     str(dossier_verrouille),
            'pdfs_copies':      [],
            'pdfs_non_mappes':  non_mappes,
            'trace':            None,
            'dry_run':          dry_run,
        }

        if dry_run:
            print(f"[DRY-RUN] {len(cibles_pdf)} PDFs seraient copiés :")
            for c in cibles_pdf:
                print(f"  - {c['source_pdf'].name}  →  pdfs/{c['nom_metier']}")
            if non_mappes:
                print(f"\n[DRY-RUN] {len(non_mappes)} PDF(s) NON mappé(s) :")
                for n in non_mappes:
                    print(f"  - {n}")
            return rapport

        # Effacer + recréer le dossier _verrouille (idempotent)
        if dossier_verrouille.exists():
            shutil.rmtree(dossier_verrouille)
        dossier_verrouille.mkdir(parents=True)
        dossier_pdfs = dossier_verrouille / 'pdfs'
        dossier_pdfs.mkdir()

        # Copier les PDFs
        for c in cibles_pdf:
            dest = dossier_pdfs / c['nom_metier']
            shutil.copy2(c['source_pdf'], dest)
            rapport['pdfs_copies'].append({
                'source':      str(c['source_pdf']),
                'destination': str(dest),
                'type_doc':    c['type_doc'],
                'sequence':    c['sequence'],
            })

        # Écrire la trace
        chemin_trace = dossier_verrouille / 'trace.json'
        chemin_trace.write_text(
            json.dumps(trace, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        rapport['trace'] = str(chemin_trace)
        return rapport
    finally:
        conn.close()


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Reconstitution rétroactive du _verrouille/ d'un référentiel."
    )
    p.add_argument('--ref-id', required=True,
                    help="ID du référentiel (ex. N11_v2025)")
    p.add_argument('--pdfs-source', required=True, type=Path,
                    help="Dossier contenant les PDFs externes à intégrer")
    p.add_argument('--data-dir', required=True, type=Path,
                    help="Racine `data/` de l'application")
    p.add_argument('--mapping', type=Path, default=None,
                    help="CSV optionnel de mapping fichier→(type_doc,séquence)")
    p.add_argument('--dry-run', action='store_true',
                    help="Affiche ce qui serait fait sans rien modifier")
    args = p.parse_args(argv)

    rapport = importer(
        ref_id=args.ref_id,
        pdfs_source=args.pdfs_source,
        data_dir=args.data_dir,
        mapping_csv=args.mapping,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        print(f"✅ Référentiel {rapport['ref_id']} ({rapport['niveau']}) "
              f"importé.")
        print(f"   Trace : {rapport['trace']}")
        print(f"   PDFs copiés : {len(rapport['pdfs_copies'])}")
        if rapport['pdfs_non_mappes']:
            print(f"   ⚠ PDFs non mappés ({len(rapport['pdfs_non_mappes'])}) :")
            for n in rapport['pdfs_non_mappes']:
                print(f"     - {n}")


if __name__ == '__main__':
    main()
