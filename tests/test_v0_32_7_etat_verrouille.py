"""tests/test_v0_32_7_etat_verrouille.py — v0.32.7

Référentiels importés en état verrouillé/utilisé : leurs PDF sont figés dans
_verrouille/pdfs/ sans que compile_ok soit posé. L'état effectif d'un document
doit alors être « ok » (et non « non_compile ») si les PDF figés existent.
"""
import pytest

from persistence.sqlite_store import SqliteStore
from services.referentiel_documents_compilation import etat_effectif_document


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def _creer_ref_utilise(conn, ref_id, niveau):
    conn.execute(
        "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
        "VALUES (?,?,?,'utilise')", (ref_id, niveau, "2025"))
    # un document livret_sequence non compilé (compile_ok NULL)
    conn.execute(
        "INSERT INTO referentiel_documents (id, referentiel_id, type_document, "
        "options, ordre) VALUES ('d1', ?, 'livret_sequence', '{}', 0)",
        (ref_id,))
    conn.commit()


def test_verrouille_avec_pdf_figes_est_ok(store, tmp_path):
    ref_id = "N11_v2025"
    with store._conn() as conn:
        _creer_ref_utilise(conn, ref_id, "N11")
    # séquences du niveau (pour que lister_cibles_document produise des cibles)
    with store._conn() as conn:
        seqs = [r[0] for r in conn.execute(
            "SELECT DISTINCT sequence_code FROM sequences_par_niveau "
            "WHERE niveau='N11'").fetchall()]
    # créer les PDF figés correspondants
    pdfs = tmp_path / "data" / "referentiels" / ref_id / "_verrouille" / "pdfs"
    pdfs.mkdir(parents=True, exist_ok=True)
    for s in seqs:
        (pdfs / f"livret_sequence__N11__{s}.pdf").write_bytes(b"%PDF")
    with store._conn() as conn:
        doc = dict(conn.execute(
            "SELECT id, referentiel_id, type_document, compile_ok, "
            "compile_date, compile_en_cours FROM referentiel_documents "
            "WHERE id='d1'").fetchone())
        etat = etat_effectif_document(conn, doc, store.data_dir)
    # Si le niveau a des séquences → PDF figés présents → ok.
    if seqs:
        assert etat == "ok"


def test_verrouille_sans_pdf_reste_non_compile(store):
    with store._conn() as conn:
        _creer_ref_utilise(conn, "N11_v2025", "N11")
        doc = dict(conn.execute(
            "SELECT id, referentiel_id, type_document, compile_ok, "
            "compile_date, compile_en_cours FROM referentiel_documents "
            "WHERE id='d1'").fetchone())
        etat = etat_effectif_document(conn, doc, store.data_dir)
    assert etat == "non_compile"


def test_sans_data_dir_ne_plante_pas(store):
    with store._conn() as conn:
        _creer_ref_utilise(conn, "N11_v2025", "N11")
        doc = dict(conn.execute(
            "SELECT id, referentiel_id, type_document, compile_ok, "
            "compile_date, compile_en_cours FROM referentiel_documents "
            "WHERE id='d1'").fetchone())
        etat = etat_effectif_document(conn, doc)  # pas de data_dir
    assert etat == "non_compile"
