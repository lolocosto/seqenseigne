"""tests/test_v0_19_1_5_resolution_partie_libelle.py — v0.19.1.5

Régression : la résolution des objectifs d'un créneau doit utiliser
`creneaux.partie_debut` (entier), JAMAIS le champ `partie` (libellé texte
optionnel). Bug exposé par l'import historique 4e3 : un créneau S12 avec
partie='1ère partie : Pythagore' faisait `WHERE partie_numero='1ère partie…'`
→ aucun objectif résolu.
"""
import uuid
import pytest
from persistence.sqlite_store import SqliteStore


@pytest.fixture
def db(tmp_path):
    return SqliteStore(tmp_path / "data")


def _setup(db):
    """Référentiel N11 + S12 en 2 parties + progression avec 2 créneaux S12
    portant un LIBELLÉ texte dans `partie`."""
    rid = "N11_vTEST"
    with db._conn() as conn:
        conn.execute("""INSERT INTO referentiel_niveaux
            (id,niveau,version,date_debut,date_fin,description,etat)
            VALUES (?,?,'T','2021-09-01','2022-08-31','T','verrouille')""",
            (rid, "N11"))
        conn.execute("""INSERT INTO referentiel_themes
            (referentiel_id,code,nom,couleur) VALUES (?,'D','Géo','geo')""", (rid,))
        conn.execute("""INSERT INTO referentiel_sequences
            (referentiel_id,code,numero,nom,theme_code)
            VALUES (?,'S12',12,'Géométrie','D')""", (rid,))
        for code, pn in [("01",1),("02",1),("03",1),("04",2),("05",2),("06",2)]:
            conn.execute("""INSERT INTO referentiel_objectifs
                (referentiel_id,seq_code,code,nom,fin_cycle,critere_f,critere_a,
                 critere_e,partie_numero,nb_seances)
                VALUES (?,?,?,?,0,'','','',?,0)""",
                (rid, "S12", code, f"obj {code}", pn))
        # Établissement + progression + 2 créneaux S12 avec LIBELLÉ.
        eid = "et_test"
        conn.execute("""INSERT INTO etablissements (id,nom,academie)
            VALUES (?,?,?)""", (eid, "Collège Test", "Rennes"))
        pid = "pg_test"
        conn.execute("""INSERT INTO progressions
            (id,niveau,annee,etablissement_id,referentiel_id,etat)
            VALUES (?,?,?,?,?,'en_cours')""",
            (pid, "N11", "2021-2022", eid, rid))
        conn.execute("""INSERT INTO creneaux
            (id,progression_id,seq_code,partie_debut,partie_fin,partie,
             periode,date_debut,date_fin,revisions,ordre)
            VALUES ('cr_p1',?,'S12',1,1,'1ère partie : Pythagore','T2',
                    '2022-01-24','2022-02-24','',1)""", (pid,))
        conn.execute("""INSERT INTO creneaux
            (id,progression_id,seq_code,partie_debut,partie_fin,partie,
             periode,date_debut,date_fin,revisions,ordre)
            VALUES ('cr_p2',?,'S12',2,2,'2ème partie : Thalès','T3',
                    '2022-03-14','2022-04-01','',2)""", (pid,))
    return pid


def test_objectifs_resolus_par_partie_debut_pas_par_libelle(db):
    pid = _setup(db)
    prog = db.lire_progression_par_id(pid)
    creneaux = {c["partie_debut"]: c for c in prog["creneaux"]}
    # Le libellé texte ne doit pas casser la résolution.
    codes_p1 = sorted(o["code"] for o in creneaux[1]["objectifs"])
    codes_p2 = sorted(o["code"] for o in creneaux[2]["objectifs"])
    assert codes_p1 == ["01", "02", "03"]
    assert codes_p2 == ["04", "05", "06"]
