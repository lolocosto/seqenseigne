"""tests/test_v0_51_11_retraits.py — v0.51.11

Retrait de l'ancien modèle de MER (referentiel_externe*) et des anciens
livrets (livrets_de_sequence, livret_revisions, versions, versions_classes) :
sauvegarde JSON avant suppression, progressions de MER remises à choisir,
idempotence, base neuve sans ces tables, routes retirées ; documents annuels
des référentiels de la structure figée proposés à la progression ; onglet
« Import retours d'usage » de l'atelier.
"""
import json
from datetime import date
from pathlib import Path

from app import create_app
from persistence.sqlite_store import SqliteStore
from services import progression_doc as pgd
from services import referentiel_principal_externe as rpe
from services import retraits

RACINE = Path(__file__).resolve().parent.parent
ANCIENNES = set(retraits.ANCIEN_MODELE_MER) | set(retraits.ANCIENS_LIVRETS)


def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_base_neuve_sans_tables_retirees(tmp_path):
    st = SqliteStore(tmp_path / "data")
    with st._conn() as c:
        assert not (_tables(c) & ANCIENNES)
    assert not (tmp_path / "data" / "sauvegardes").exists()     # rien à sauvegarder


def test_retrait_ancien_modele_mer(tmp_path):
    st = SqliteStore(tmp_path / "data")
    with st._conn() as c:
        c.executescript("""
            CREATE TABLE referentiel_externe (id TEXT PRIMARY KEY, niveau TEXT, nom TEXT);
            CREATE TABLE referentiel_externe_sequence (id TEXT PRIMARY KEY, ref_ext_id TEXT);
            CREATE TABLE referentiel_externe_partie (id TEXT PRIMARY KEY, sequence_id TEXT);
            CREATE TABLE referentiel_externe_doc (id TEXT PRIMARY KEY, partie_id TEXT);
            INSERT INTO referentiel_externe VALUES ('rx1', 'N09', 'MER 6e');
            INSERT INTO referentiel_externe_sequence VALUES ('rs1', 'rx1');
            INSERT INTO referentiel_externe_partie VALUES ('rp1', 'rs1');
            INSERT INTO referentiel_externe_doc VALUES ('rd1', 'rp1');
        """)
        c.execute("INSERT INTO progression_mer (id, niveau, annee, ref_mer_id, ref_mer_source) "
                  "VALUES ('pm1', 'N09', '2026-2027', 'rx1', 'externe')")
        c.execute("INSERT INTO progression_mer_partie (id, progression_mer_id, partie_id, "
                  "partie_source) VALUES ('pp1', 'pm1', 'rp1', 'externe')")
        c.execute("INSERT INTO progression_doc (id, prog_kind, prog_ref, creneau_ref, doc_source, "
                  "doc_ref) VALUES ('pd1', 'mer', 'pm1', 'rp1', 'externe', 'rd1')")
        r = retraits.retirer_ancien_modele_mer(c, st.data_dir)
        assert (r["progressions_mer"], r["parties_posees"]) == (1, 1)
        assert not (_tables(c) & set(retraits.ANCIEN_MODELE_MER))
        pm = c.execute("SELECT ref_mer_id, ref_mer_source FROM progression_mer").fetchone()
        assert (pm["ref_mer_id"], pm["ref_mer_source"]) == (None, "fige")
        assert c.execute("SELECT COUNT(*) FROM progression_mer_partie").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM progression_doc").fetchone()[0] == 0
        assert retraits.retirer_ancien_modele_mer(c, st.data_dir) is None      # idempotent
    sauvegarde = json.loads(Path(r["sauvegarde"]).read_text(encoding="utf-8"))
    assert sauvegarde["tables"]["referentiel_externe"][0]["nom"] == "MER 6e"
    assert sauvegarde["progressions_mer"][0]["id"] == "pm1"


def test_retrait_anciens_livrets_au_demarrage(tmp_path):
    d = tmp_path / "data"
    st = SqliteStore(d)
    with st._conn() as c:
        c.executescript("""
            CREATE TABLE versions (id INTEGER PRIMARY KEY, niveau TEXT, seq_code TEXT, tag TEXT);
            CREATE TABLE versions_classes (classe_id TEXT, niveau TEXT, seq_code TEXT);
            INSERT INTO versions (niveau, seq_code, tag) VALUES ('N10', 'S01', 'v1');
        """)
    SqliteStore(d)                                         # redémarrage : retrait
    with st._conn() as c:
        assert not (_tables(c) & set(retraits.ANCIENS_LIVRETS))
    fichiers = list((d / "sauvegardes").glob("retrait_anciens_livrets_*.json"))
    assert len(fichiers) == 1
    assert json.loads(fichiers[0].read_text())["tables"]["versions"][0]["tag"] == "v1"


def test_routes_retirees_et_onglet_atelier(data_dir):
    app = create_app(data_dir, profil="complet")
    cl = app.test_client()
    assert cl.get("/api/versions?niveau=N10&seq=S01").status_code == 404
    assert cl.get("/api/referentiels-externes?niveau=N09").status_code == 404
    assert cl.get("/api/atomes/livrets").status_code == 404
    html = (RACINE / "templates" / "index.html").read_text(encoding="utf-8")
    # v0.51.13 — L'import des retours d'usage est dans Administration › Échanges.
    assert 'id="admin-importusage" data-profils="atelier"' in html
    assert "referentiel_externe.js" not in html
    atelier = create_app(data_dir, profil="atelier")
    assert atelier.test_client().get("/api/retour-usage/etat").status_code == 200


def test_documents_annuels_de_la_structure_figee(tmp_path):
    st = SqliteStore(tmp_path / "data")
    with st._conn() as c:
        rid = rpe.creer(c, "N09", "2026-2027", type_ref="mer")["id"]
        rpe.ajouter_sequence(c, rid, "Tables")
        f = rpe.ajouter_fichier(c, rid, "", 0, nom_fichier="recap.pdf", contenu=b"%",
                                mime="application/pdf", data_dir=st.data_dir)
        docs = pgd.documents_disponibles(c, "N09", "2026-2027", "M01")
    assert [(d["doc_ref"], d["categorie"]) for d in docs["annuels"]] == [(f["id"], "annuel")]
