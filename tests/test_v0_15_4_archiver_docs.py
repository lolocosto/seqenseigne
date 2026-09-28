"""tests/test_v0_15_4_archiver_docs.py — v0.15.4

Outil d'archivage des documents obsolètes de `doc/` vers
`doc/archives/<categorie>/`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from outils.archiver_docs import categoriser, archiver  # noqa: E402


def test_canoniques_restent_a_la_racine():
    """Les 6 documents canoniques ne sont JAMAIS archivés."""
    for nom in ('INDEX.md', 'README.md', 'CONVENTIONS.md',
                  'GOTCHAS.md', 'DETTE_TECHNIQUE.md', 'NETTOYAGE.md'):
        assert categoriser(nom) is None


def test_redemarrage_v0_15_reste_a_la_racine():
    """Les redemarrages v0.15 sont vivants (en cours), pas archivés."""
    for nom in ('redemarrage_v0_15.md',           # le récap v0.15 général
                'redemarrage_v0_15_3.md',
                'redemarrage_v0_15_2_12_2_hotfix.md'):
        cat = categoriser(nom)
        # v0_15.md (sans suffixe) → archivé en tant qu'ancienne notation
        # v0_15_X → conservé. Distinguons les deux cas :
        if nom == 'redemarrage_v0_15.md':
            assert cat is not None
            assert cat[0] == 'redemarrages_anciens'
        else:
            assert cat is None


def test_redemarrage_ancien_archive():
    cat = categoriser('redemarrage_v0_10_7.md')
    assert cat is not None
    assert cat[0] == 'redemarrages_anciens'


def test_redemarrage_v0_14_archive():
    cat = categoriser('redemarrage_v0_14_7.md')
    assert cat[0] == 'redemarrages_anciens'


def test_readme_ancien_archive():
    """Les README_* (autres que README.md) sont archivés."""
    assert categoriser('README_R1.md')[0]      == 'readme_anciens'
    assert categoriser('README_v0_6_4_3abc.md')[0] == 'readme_anciens'
    assert categoriser('README_chantier_14.md')[0] == 'readme_anciens'


def test_patches_archives():
    assert categoriser('patch_v0_10_3.md')[0] == 'patches'
    assert categoriser('patch_etape2_v3.md')[0] == 'patches'


def test_chantiers_archives():
    assert categoriser('chantier_14_session_1.md')[0] == 'chantiers'


def test_notes_archives():
    assert categoriser('NOTE_atelier_recapcours.md')[0] == 'notes'


def test_anciens_cdc_archives():
    assert categoriser('seqenseigne_cdc_v0_10_7.md')[0] == 'archives_cdc_doc'
    assert categoriser('seqenseigne_doc_v0.6.3e.md')[0] == 'archives_cdc_doc'


def test_scoping_archive():
    assert categoriser('scoping_v0_13_5_referentiels.md')[0] == 'scoping'


def test_pilotage_archive():
    assert categoriser('reprise_2026-05-07.md')[0] == 'pilotage'
    assert categoriser('finalisation_paquet_v0_13_5_2.md')[0] == 'pilotage'


# ── Tests bout-en-bout ─────────────────────────────────────────────────────


def test_archiver_dry_run_ne_modifie_rien(tmp_path):
    """En dry-run, aucun fichier n'est déplacé."""
    doc_dir = tmp_path / 'doc'
    doc_dir.mkdir()
    (doc_dir / 'INDEX.md').write_text('canonique', encoding='utf-8')
    (doc_dir / 'patch_v0_8.md').write_text('patch', encoding='utf-8')
    rapport = archiver(doc_dir, dry_run=True)
    assert rapport['dry_run'] is True
    # Aucun déplacement
    assert (doc_dir / 'patch_v0_8.md').is_file()
    assert not (doc_dir / 'archives').exists()


def test_archiver_vrai_deplace_les_fichiers(tmp_path):
    doc_dir = tmp_path / 'doc'
    doc_dir.mkdir()
    (doc_dir / 'INDEX.md').write_text('canonique', encoding='utf-8')
    (doc_dir / 'README.md').write_text('readme', encoding='utf-8')
    (doc_dir / 'redemarrage_v0_15_3.md').write_text('v0.15.3', encoding='utf-8')
    (doc_dir / 'patch_v0_8.md').write_text('patch', encoding='utf-8')
    (doc_dir / 'README_R1.md').write_text('readme R1', encoding='utf-8')
    (doc_dir / 'redemarrage_v0_13_2.md').write_text('v0.13.2', encoding='utf-8')
    (doc_dir / 'chantier_14_session_1.md').write_text('c14', encoding='utf-8')

    rapport = archiver(doc_dir)
    assert rapport['dry_run'] is False
    assert rapport['total_archives'] == 4   # patch, R1, v0.13.2, chantier14

    # Racine : seuls les 3 vivants restent
    assert (doc_dir / 'INDEX.md').is_file()
    assert (doc_dir / 'README.md').is_file()
    assert (doc_dir / 'redemarrage_v0_15_3.md').is_file()

    # Archives par catégorie
    arc = doc_dir / 'archives'
    assert (arc / 'patches' / 'patch_v0_8.md').is_file()
    assert (arc / 'readme_anciens' / 'README_R1.md').is_file()
    assert (arc / 'redemarrages_anciens'
                / 'redemarrage_v0_13_2.md').is_file()
    assert (arc / 'chantiers'
                / 'chantier_14_session_1.md').is_file()
    assert (arc / 'INDEX_ARCHIVES.md').is_file()


def test_archiver_idempotent(tmp_path):
    """Relancer sur un dossier déjà partiellement archivé ne casse rien."""
    doc_dir = tmp_path / 'doc'
    doc_dir.mkdir()
    (doc_dir / 'INDEX.md').write_text('x', encoding='utf-8')
    (doc_dir / 'patch_v0_8.md').write_text('patch1', encoding='utf-8')

    archiver(doc_dir)  # 1er passage
    assert (doc_dir / 'archives' / 'patches' / 'patch_v0_8.md').is_file()

    # Réinjecter une copie du même fichier (cas où un user le remet par
    # mégarde après archivage)
    (doc_dir / 'patch_v0_8.md').write_text('reposé', encoding='utf-8')

    archiver(doc_dir)  # 2e passage
    # Le fichier source a été retiré (idempotent), mais la copie dans
    # archives/ reste celle du 1er passage (on n'écrase pas).
    assert not (doc_dir / 'patch_v0_8.md').exists()
    contenu_archive = (doc_dir / 'archives' / 'patches'
                       / 'patch_v0_8.md').read_text(encoding='utf-8')
    assert contenu_archive == 'patch1'   # 1er passage préservé


def test_archiver_index_archives_genere(tmp_path):
    doc_dir = tmp_path / 'doc'
    doc_dir.mkdir()
    (doc_dir / 'README.md').write_text('r', encoding='utf-8')
    (doc_dir / 'patch_a.md').write_text('p1', encoding='utf-8')
    (doc_dir / 'patch_b.md').write_text('p2', encoding='utf-8')
    (doc_dir / 'NOTE_x.md').write_text('n', encoding='utf-8')

    archiver(doc_dir)
    idx = (doc_dir / 'archives' / 'INDEX_ARCHIVES.md').read_text(encoding='utf-8')
    assert 'patches' in idx
    assert 'patch_a.md' in idx
    assert 'patch_b.md' in idx
    assert 'NOTE_x.md' in idx
