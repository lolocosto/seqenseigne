"""tests/test_v0_15_2_10_importer_referentiel_externe.py — v0.15.2.10

Outil de reconstitution rétroactive du dossier `_verrouille/` d'un référentiel
utilisé hors-système.

Tests :
- Détection du type+séquence par regex sur le nom de fichier.
- Chargement d'un mapping CSV explicite (override).
- Convention de nom métier seqenseigne pour les PDFs cibles.
- Importer en dry-run : aucune écriture.
- Importer réel : trace.json créé, PDFs copiés et renommés, état BDD
  inchangé.
- Idempotence : relancer écrase proprement.
- PDFs non reconnus (mapping absent) listés en sortie sans bloquer.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from outils.importer_referentiel_externe import (  # noqa: E402
    _detecter_mapping_par_defaut,
    _charger_mapping_csv,
    _nom_metier,
    importer,
)


# ── Détection regex ────────────────────────────────────────────────────────


def test_detecter_livret_sequence_avec_prefixe_classe():
    """Convention Laurent : `4e3_S01_Livret.pdf` → livret_sequence S01."""
    assert _detecter_mapping_par_defaut('4e3_S01_Livret.pdf') \
        == ('livret_sequence', 'S01')


def test_detecter_livret_sequence_avec_espace_separateur():
    """v0.15.2.12.2 — Cas réel terrain Laurent : séparateur ESPACE.
    `4e3 S01_Livret.pdf` (espace entre classe et séquence)."""
    assert _detecter_mapping_par_defaut('4e3 S01_Livret.pdf') \
        == ('livret_sequence', 'S01')


def test_detecter_livret_sequence_avec_tiret_separateur():
    """v0.15.2.12.2 — Tiret accepté aussi."""
    assert _detecter_mapping_par_defaut('classe-S14_Livret.pdf') \
        == ('livret_sequence', 'S14')


def test_detecter_livret_sequence_sans_prefixe():
    """v0.15.2.12.2 — Nom minimaliste : juste `S<NN>_Livret.pdf`."""
    assert _detecter_mapping_par_defaut('S05_Livret.pdf') \
        == ('livret_sequence', 'S05')


def test_detecter_livret_sequence_autre_prefixe():
    assert _detecter_mapping_par_defaut('classe2_S14_Livret.pdf') \
        == ('livret_sequence', 'S14')


def test_detecter_ignore_noms_non_conformes():
    """Aucun pattern reconnu → None."""
    assert _detecter_mapping_par_defaut('progression_annuelle.pdf') is None
    assert _detecter_mapping_par_defaut('S01.pdf') is None
    assert _detecter_mapping_par_defaut('4e3_S1_Livret.pdf') is None
    # 1 chiffre, le regex en demande 2


# ── Mapping CSV explicite ──────────────────────────────────────────────────


def test_charger_mapping_csv(tmp_path):
    csv = tmp_path / 'm.csv'
    csv.write_text(
        "fichier_S01.pdf;livret_sequence;S01\n"
        "fichier_S14.pdf;livret_corriges;S14\n"
        "# commentaire ignoré\n"
        "\n"
        "global.pdf;livret_exercices;\n",
        encoding='utf-8'
    )
    m = _charger_mapping_csv(csv)
    assert m['fichier_S01.pdf'] == ('livret_sequence', 'S01')
    assert m['fichier_S14.pdf'] == ('livret_corriges', 'S14')
    assert m['global.pdf']      == ('livret_exercices', '')
    assert '# commentaire ignoré' not in m


# ── Convention de nom métier ───────────────────────────────────────────────


def test_nom_metier_par_sequence():
    assert _nom_metier('N11', 'livret_sequence', 'S01') \
        == 'livret_sequence__N11__S01.pdf'


def test_nom_metier_niveau_global():
    """Pour les types sans séquence : pas de double souligné final."""
    assert _nom_metier('N11', 'livret_exercices', None) \
        == 'livret_exercices__N11.pdf'
    assert _nom_metier('N11', 'livret_exercices', '') \
        == 'livret_exercices__N11.pdf'


# ── Importer — bout en bout ────────────────────────────────────────────────


def _creer_ref(conn, ref_id='ref_test', niveau='N11', etat='verrouille'):
    conn.execute("""INSERT INTO referentiel_niveaux
        (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES (?, ?, '2025_v1', '2025-09-01', '2026-08-31', 'Test', ?)""",
        (ref_id, niveau, etat))


def _placer_pdf(dossier, nom, contenu=b'%PDF-1.7 fake'):
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / nom).write_bytes(contenu)


def test_importer_inconnu_leve(sqlite_store, tmp_path):
    """Référentiel introuvable en BDD → ValueError."""
    src = tmp_path / 'pdfs_src'
    src.mkdir()
    data_dir = Path(sqlite_store.data_dir)
    with pytest.raises(ValueError, match='introuvable'):
        importer('inexistant', src, data_dir)


def test_importer_dry_run_n_ecrit_rien(sqlite_store, tmp_path):
    """En dry-run, aucun fichier créé."""
    with sqlite_store._conn() as conn:
        rid = f"ref_{uuid.uuid4().hex[:8]}"
        _creer_ref(conn, ref_id=rid)
        conn.commit()
    src = tmp_path / 'pdfs_src'
    _placer_pdf(src, '4e3_S01_Livret.pdf')
    data_dir = Path(sqlite_store.data_dir)

    rapport = importer(rid, src, data_dir, dry_run=True)
    assert rapport['dry_run'] is True
    # Aucun dossier _verrouille créé
    assert not (data_dir / 'referentiels' / rid / '_verrouille').exists()


def test_importer_reel_cree_dossier_verrouille_et_copie_pdfs(
        sqlite_store, tmp_path):
    with sqlite_store._conn() as conn:
        rid = f"ref_{uuid.uuid4().hex[:8]}"
        _creer_ref(conn, ref_id=rid, niveau='N11')
        conn.commit()
    src = tmp_path / 'pdfs_src'
    _placer_pdf(src, '4e3_S01_Livret.pdf',  b'%PDF S01')
    _placer_pdf(src, '4e3_S14_Livret.pdf',  b'%PDF S14')
    data_dir = Path(sqlite_store.data_dir)

    rapport = importer(rid, src, data_dir)

    dossier_verrouille = data_dir / 'referentiels' / rid / '_verrouille'
    # Fichiers attendus
    assert (dossier_verrouille / 'trace.json').is_file()
    assert (dossier_verrouille / 'pdfs'
            / 'livret_sequence__N11__S01.pdf').is_file()
    assert (dossier_verrouille / 'pdfs'
            / 'livret_sequence__N11__S14.pdf').is_file()
    # Contenu copié à l'identique
    assert (dossier_verrouille / 'pdfs'
            / 'livret_sequence__N11__S01.pdf').read_bytes() == b'%PDF S01'
    # Rapport
    assert len(rapport['pdfs_copies']) == 2
    assert rapport['pdfs_non_mappes'] == []


def test_importer_pdfs_non_mappes_listes_sans_bloquer(
        sqlite_store, tmp_path):
    """Un PDF au nom inconnu doit apparaître dans `pdfs_non_mappes`
    sans empêcher le traitement des autres."""
    with sqlite_store._conn() as conn:
        rid = f"ref_{uuid.uuid4().hex[:8]}"
        _creer_ref(conn, ref_id=rid)
        conn.commit()
    src = tmp_path / 'pdfs_src'
    _placer_pdf(src, '4e3_S01_Livret.pdf')
    _placer_pdf(src, 'progression_annuelle.pdf')   # nom non reconnu
    data_dir = Path(sqlite_store.data_dir)

    rapport = importer(rid, src, data_dir)
    assert len(rapport['pdfs_copies']) == 1
    assert rapport['pdfs_non_mappes'] == ['progression_annuelle.pdf']


def test_importer_idempotent_relance_efface_anciennement_copies(
        sqlite_store, tmp_path):
    """Relancer après changement du dossier source écrase proprement
    l'ancien `_verrouille/` (pas d'accumulation)."""
    with sqlite_store._conn() as conn:
        rid = f"ref_{uuid.uuid4().hex[:8]}"
        _creer_ref(conn, ref_id=rid)
        conn.commit()
    src = tmp_path / 'pdfs_src'
    _placer_pdf(src, '4e3_S01_Livret.pdf')
    data_dir = Path(sqlite_store.data_dir)

    # 1er run : S01
    importer(rid, src, data_dir)
    assert (data_dir / 'referentiels' / rid / '_verrouille' / 'pdfs'
            / 'livret_sequence__N11__S01.pdf').is_file()

    # Changement du dossier source : S01 supprimé, S02 ajouté
    (src / '4e3_S01_Livret.pdf').unlink()
    _placer_pdf(src, '4e3_S02_Livret.pdf')

    # 2e run
    importer(rid, src, data_dir)
    pdfs = data_dir / 'referentiels' / rid / '_verrouille' / 'pdfs'
    assert not (pdfs / 'livret_sequence__N11__S01.pdf').exists()
    assert (pdfs / 'livret_sequence__N11__S02.pdf').is_file()


def test_importer_ne_modifie_pas_etat_bdd(sqlite_store, tmp_path):
    """Le référentiel reste à son état initial (typiquement
    'verrouille' pour un référentiel rétro-importé)."""
    with sqlite_store._conn() as conn:
        rid = f"ref_{uuid.uuid4().hex[:8]}"
        _creer_ref(conn, ref_id=rid, etat='verrouille')
        conn.commit()
    src = tmp_path / 'pdfs_src'
    _placer_pdf(src, '4e3_S01_Livret.pdf')
    data_dir = Path(sqlite_store.data_dir)

    importer(rid, src, data_dir)

    with sqlite_store._conn() as conn:
        row = conn.execute(
            "SELECT etat FROM referentiel_niveaux WHERE id=?", (rid,)
        ).fetchone()
    assert row['etat'] == 'verrouille'


def test_importer_trace_contient_documents_externes(
        sqlite_store, tmp_path):
    """Les PDFs externes apparaissent dans trace.documents avec
    `provenance: 'externe'`."""
    with sqlite_store._conn() as conn:
        rid = f"ref_{uuid.uuid4().hex[:8]}"
        _creer_ref(conn, ref_id=rid, niveau='N11')
        conn.commit()
    src = tmp_path / 'pdfs_src'
    _placer_pdf(src, '4e3_S01_Livret.pdf')
    data_dir = Path(sqlite_store.data_dir)

    importer(rid, src, data_dir)
    trace = json.loads(
        (data_dir / 'referentiels' / rid / '_verrouille' / 'trace.json'
         ).read_text(encoding='utf-8')
    )
    assert len(trace['documents']) == 1
    doc = trace['documents'][0]
    assert doc['provenance'] == 'externe'
    assert doc['type_document'] == 'livret_sequence'
    c = doc['cibles'][0]
    assert c['nom_fichier'] == 'livret_sequence__N11__S01.pdf'
    assert c['chemin_pdf']  == 'pdfs/livret_sequence__N11__S01.pdf'


def test_importer_avec_mapping_csv_override(sqlite_store, tmp_path):
    """Le CSV explicite prime sur la détection regex."""
    with sqlite_store._conn() as conn:
        rid = f"ref_{uuid.uuid4().hex[:8]}"
        _creer_ref(conn, ref_id=rid, niveau='N11')
        conn.commit()
    src = tmp_path / 'pdfs_src'
    _placer_pdf(src, 'foo_unknown.pdf')
    csv = tmp_path / 'mapping.csv'
    csv.write_text("foo_unknown.pdf;livret_corriges;S05\n", encoding='utf-8')
    data_dir = Path(sqlite_store.data_dir)

    rapport = importer(rid, src, data_dir, mapping_csv=csv)
    assert len(rapport['pdfs_copies']) == 1
    nom = rapport['pdfs_copies'][0]['destination']
    assert nom.endswith('livret_corriges__N11__S05.pdf')
