"""outils/archiver_docs.py — v0.15.4

Audit + archivage des documents obsolètes du dossier `appli/doc/`.

Au fil des sessions (≈ 250 fichiers `.md` accumulés), le dossier `doc/`
est devenu illisible. Cet outil déplace les fichiers obsolètes dans
`doc/archives/` en préservant leur historique mais en sortant du
chemin principal.

Catégories archivées :

- `redemarrage_v0_*.md` antérieurs à v0.15 (notes de livraison figées).
- `README_*` autres que `README.md` (anciens chantiers R1-R4, patches,
  README de versions ≤ 0.6.x).
- `patch_*.md` (notes de patch d'anciennes époques).
- `chantier_*.md` (chantier 14, fermé).
- `NOTE_*.md` (notes ponctuelles, peuvent être ressuscitées si besoin).
- `seqenseigne_*v0_10_7*.md`, `*v0.6.3e*.md` (anciennes versions des
  CDC / doc technique / use cases).
- `scoping_*.md`, `finalisation_*.md`, `reprise_*.md`, `patch_etape*.md`,
  `redemarrage_paquet_*.md` (notes de cadrage / pilotage).

Conservés à la racine de `doc/` :

- Les 6 canoniques : INDEX, README, CONVENTIONS, GOTCHAS,
  DETTE_TECHNIQUE, NETTOYAGE.
- Les `redemarrage_v0_15_*.md` (notes encore vivantes pour le travail
  en cours).

Modes :
  --dry-run   : affiche ce qui serait déplacé, ne touche à rien.
  (défaut)    : déplace effectivement les fichiers et écrit un index
                `doc/archives/INDEX_ARCHIVES.md` listant tout ce qui a
                été archivé avec le motif.

Idempotent : on peut relancer plusieurs fois. Les fichiers déjà dans
`doc/archives/` ne sont pas touchés.

Usage CLI :

    python -m outils.archiver_docs --doc-dir ./doc          # archive
    python -m outils.archiver_docs --doc-dir ./doc --dry-run  # preview
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


# Documents à TOUJOURS garder à la racine de doc/ (canoniques + vivants).
GARDES_RACINE = {
    'INDEX.md',
    'README.md',
    'CONVENTIONS.md',
    'GOTCHAS.md',
    'DETTE_TECHNIQUE.md',
    'NETTOYAGE.md',
}


def categoriser(nom: str) -> tuple[str, str] | None:
    """Retourne (categorie, motif) si le fichier doit être archivé,
    None s'il doit rester à la racine."""
    if nom in GARDES_RACINE:
        return None

    # Notes de redémarrage v0.15.* : on garde, c'est l'historique vivant.
    if re.match(r'^redemarrage_v0_15_', nom):
        return None

    # Redemarrages anciens (v0.05 à v0.14)
    if re.match(r'^redemarrage_v0_(09|10|11|12|13|14)', nom):
        return ('redemarrages_anciens',
                'Note de livraison v0.09–v0.14 (gelée, conservée pour historique)')
    if re.match(r'^redemarrage_(v0_5|v0\.|v09|V02)', nom, re.IGNORECASE):
        return ('redemarrages_anciens',
                'Note de livraison v0.5/v0.9 (gelée)')
    # Anciennes notations sans underscore (v010, v0112, v07, v08, etc.)
    if re.match(r'^redemarrage_v0?\d+', nom):
        # v0.15 sans underscore (redemarrage_v0_15.md, sans suffixe)
        # → c'est le récap général qu'on archive (les v0_15_X sont gardés).
        return ('redemarrages_anciens',
                'Note de livraison v0.x ancienne (notation sans underscore)')
    if re.match(r'^redemarrage_paquet_', nom):
        return ('redemarrages_anciens',
                'Note de redémarrage du chantier paquet LaTeX')

    # README anciens (R1-R4, README_v0_x, README_chantier, etc.)
    if re.match(r'^README_', nom):
        return ('readme_anciens',
                'Ancien README de chantier ou version (R1-R4, v0.5-0.11)')

    # Patches anciens
    if re.match(r'^patch_', nom):
        return ('patches', 'Note de patch d\'une ancienne version')

    # Chantier 14 (fermé)
    if re.match(r'^chantier_', nom):
        return ('chantiers', 'Notes du chantier 14 (closed)')

    # Notes ponctuelles
    if re.match(r'^NOTE_', nom):
        return ('notes', 'Note ponctuelle (fix cache, atelier recapcours, …)')

    # Anciennes versions CDC / doc technique / use cases
    if re.search(r'v0_10_7|v0\.6\.3e|v0\.5\.|v0\.6\.', nom):
        return ('archives_cdc_doc',
                'Ancienne version du CDC / doc technique / use cases')
    if re.match(r'^seqenseigne_', nom):
        # cdc, doc, usecases anciennes
        return ('archives_cdc_doc',
                'Ancienne version du CDC / doc technique / use cases')

    # Notes de scoping / cadrage / pilotage
    if re.match(r'^scoping_', nom):
        return ('scoping', 'Note de cadrage')
    if re.match(r'^(finalisation_|reprise_)', nom):
        return ('pilotage', 'Note de finalisation ou de reprise de session')

    # Tout autre fichier .md non identifié
    return ('autres', 'Catégorie inconnue — à vérifier manuellement')


def archiver(doc_dir: Path, dry_run: bool = False) -> dict:
    """Déplace les fichiers obsolètes dans `<doc_dir>/archives/<categorie>/`.

    Retourne un rapport :
      {
        'racine':          [str],   # gardés à la racine
        'par_categorie':   {categ: [(nom, motif)]},
        'total_archives':  int,
        'dry_run':         bool,
      }
    """
    if not doc_dir.is_dir():
        raise FileNotFoundError(f"Dossier introuvable : {doc_dir}")

    archives_dir = doc_dir / 'archives'

    racine = []
    par_categorie: dict[str, list[tuple[str, str]]] = {}
    for f in sorted(doc_dir.glob('*.md')):
        cat = categoriser(f.name)
        if cat is None:
            racine.append(f.name)
            continue
        categorie, motif = cat
        par_categorie.setdefault(categorie, []).append((f.name, motif))

    rapport = {
        'racine': racine,
        'par_categorie': par_categorie,
        'total_archives': sum(len(v) for v in par_categorie.values()),
        'dry_run': dry_run,
    }

    if dry_run:
        return rapport

    # Effectuer le déplacement
    archives_dir.mkdir(exist_ok=True)
    for categorie, fichiers in par_categorie.items():
        cible = archives_dir / categorie
        cible.mkdir(exist_ok=True)
        for nom, _motif in fichiers:
            src = doc_dir / nom
            dst = cible / nom
            if dst.exists():
                # Idempotent : on ne réécrit pas, on supprime juste la
                # source (le contenu est déjà archivé).
                src.unlink()
            else:
                shutil.move(str(src), str(dst))

    # Écrire un INDEX_ARCHIVES.md récapitulatif
    index = archives_dir / 'INDEX_ARCHIVES.md'
    lignes = [
        '# Index des archives — `doc/archives/`',
        '',
        f"Archivage automatique via `outils/archiver_docs.py` "
        f"(v0.15.4).",
        '',
        ('Les fichiers ci-dessous ont été déplacés depuis `doc/` pour '
         'désengorger le dossier principal. Ils sont **figés** : on n\'y '
         'revient pas pour les modifier, ils servent d\'historique '
         'factuel des versions et chantiers antérieurs.'),
        '',
    ]
    for categorie in sorted(par_categorie):
        fichiers = par_categorie[categorie]
        lignes.append(f'## `{categorie}/` ({len(fichiers)} fichiers)')
        lignes.append('')
        if fichiers:
            lignes.append(f'Motif : *{fichiers[0][1]}*')
            lignes.append('')
        for nom, _motif in sorted(fichiers):
            lignes.append(f'- `{nom}`')
        lignes.append('')
    index.write_text('\n'.join(lignes) + '\n', encoding='utf-8')

    return rapport


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Archive les documents obsolètes de doc/."
    )
    p.add_argument('--doc-dir', required=True, type=Path,
                    help="Chemin du dossier doc/ à nettoyer")
    p.add_argument('--dry-run', action='store_true',
                    help="Affiche ce qui serait fait sans rien modifier")
    args = p.parse_args(argv)

    rapport = archiver(args.doc_dir, dry_run=args.dry_run)

    mode = '[DRY-RUN] ' if args.dry_run else ''
    print(f"{mode}Gardés à la racine ({len(rapport['racine'])}) :")
    for n in rapport['racine']:
        print(f"  ✓ {n}")
    print()
    print(f"{mode}Archives ({rapport['total_archives']}) :")
    for categorie in sorted(rapport['par_categorie']):
        fichiers = rapport['par_categorie'][categorie]
        print(f"  archives/{categorie}/  ({len(fichiers)} fichiers)")
        if fichiers:
            print(f"    motif : {fichiers[0][1]}")
    if not args.dry_run:
        print(f"\n✅ Archivage effectué. Index dans "
              f"`{args.doc_dir / 'archives' / 'INDEX_ARCHIVES.md'}`.")


if __name__ == '__main__':
    main()
