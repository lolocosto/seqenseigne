"""tests/test_v0_38_0_edt_versionne.py — v0.38.0

EdT versionné : migration (reconstruction de edt_creneaux), états « en
saisie » / « figé », scission des cases au lundi d'effet, héritage des
affectations de séance, suppression datée, changements programmés et leur
annulation, salle et AESH par case, filtre de période dans la projection et
les vues hebdomadaires, aperçu de l'effet sur les séances, routes.
"""
import sqlite3
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt
from services import grille_horaire as gh
from services import salles as sv
from services.projection_seances import projeter

ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)          # jeudi ; semaine du 28/09
PROCHAIN = "2026-10-05"
PLUS_TARD = "2026-11-02"


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def _etab(conn, eid="et_test"):
    conn.execute("INSERT OR IGNORE INTO etablissements (id, nom, etat) "
                 "VALUES (?,?, 'propose')", (eid, "Collège " + eid))
    gh.peupler_defauts_si_vide(conn, eid)
    return eid


def _classe(conn, cid="cl_4e3", nom="4EME3", eid="et_test", annee=ANNEE):
    conn.execute("INSERT OR IGNORE INTO classes (id, nom, niveau, annee, "
                 "etablissement_id) VALUES (?,?,?,?,?)",
                 (cid, nom, "N11", annee, eid))
    return cid


def _case(conn, jour="lun", code="M1", semaine="AB", **kw):
    return edt.ajouter(conn, ANNEE, jour, code, "et_test", semaine=semaine,
                       classe_id=kw.pop("classe_id", "cl_4e3"),
                       aujourd_hui=AUJ, **kw)


def _figer(conn):
    edt.figer(conn, ANNEE, "et_test", AUJ)


# ── Migration ────────────────────────────────────────────────────────────────

def test_migration_reconstruit_la_table_et_garde_les_cases(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    con = sqlite3.connect(d / "seqenseigne.db")
    con.executescript("""
        CREATE TABLE edt_creneaux (
            id TEXT PRIMARY KEY, annee TEXT NOT NULL, jour TEXT NOT NULL,
            creneau_code TEXT NOT NULL, semaine TEXT NOT NULL DEFAULT 'AB',
            classe_id TEXT, etablissement_id TEXT NOT NULL,
            libelle TEXT NOT NULL DEFAULT '',
            usage TEXT NOT NULL DEFAULT 'classe_entiere',
            ordre INTEGER NOT NULL DEFAULT 0,
            groupe TEXT NOT NULL DEFAULT 'classe_entiere',
            UNIQUE (annee, jour, creneau_code, semaine, etablissement_id));
        INSERT INTO edt_creneaux (id, annee, jour, creneau_code, semaine,
            classe_id, etablissement_id, libelle, usage, ordre, groupe)
        VALUES ('edt_1', '2026-2027', 'lun', 'M1', 'AB', 'cl_x', 'et_x',
                'Maths', 'cours', 10, 'demi_classe_A');
    """)
    con.commit()
    con.close()
    st = SqliteStore(d)
    with st._conn() as c:
        r = dict(c.execute("SELECT * FROM edt_creneaux").fetchone())
        sql = c.execute("SELECT sql FROM sqlite_master "
                        "WHERE name='edt_creneaux'").fetchone()[0]
    assert r["libelle"] == "Maths" and r["groupe"] == "demi_classe_A"
    assert r["valide_du"] == "" and r["valide_au"] == "" and r["nb_aesh"] == 0
    assert "UNIQUE" not in sql
    SqliteStore(d)   # idempotente


# ── En saisie ────────────────────────────────────────────────────────────────

class TestEnSaisie:
    def test_etat_par_defaut(self, store):
        with store._conn() as c:
            assert edt.etat(c, ANNEE, _etab(c))["etat"] == "en_saisie"

    def test_modifs_sur_place_sans_date(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            k = _case(c)
            n = edt.modifier(c, k["id"], {"semaine": "A", "nb_aesh": 2},
                             aujourd_hui=AUJ)
            assert n["id"] == k["id"] and n["valide_du"] == ""
            assert len(edt.lister(c, ANNEE)) == 1
            with pytest.raises(edt.DonneesInvalides):    # pas d'état futur
                edt.modifier(c, k["id"], {"semaine": "B"}, a_partir_du=PROCHAIN,
                             aujourd_hui=AUJ)
            with pytest.raises(edt.DonneesInvalides):
                _case(c, code="M2", a_partir_du=PROCHAIN)
            edt.supprimer(c, k["id"], aujourd_hui=AUJ)
            assert edt.lister(c, ANNEE) == []

    def test_controle_ab_contre_a_b(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            _case(c, semaine="A")
            with pytest.raises(edt.DonneesInvalides):
                _case(c, semaine="AB")
            _case(c, semaine="B")
            with pytest.raises(edt.DonneesInvalides):
                _case(c, semaine="B")


# ── Figé ─────────────────────────────────────────────────────────────────────

class TestFige:
    def test_figeage_definitif(self, store):
        with store._conn() as c:
            _etab(c)
            assert edt.figer(c, ANNEE, "et_test", AUJ)["date_figeage"] == "2026-10-01"
            with pytest.raises(edt.DonneesInvalides):
                edt.figer(c, ANNEE, "et_test", AUJ)
            # L'autre établissement reste en saisie.
            assert edt.etat(c, ANNEE, _etab(c, "et_b"))["etat"] == "en_saisie"

    def test_libelle_sur_place(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            k = _case(c, libelle="Mats")
            _figer(c)
            n = edt.modifier(c, k["id"], {"libelle": "Maths"}, aujourd_hui=AUJ)
            assert n["id"] == k["id"] and len(edt.lister(c, ANNEE)) == 1

    def test_changement_structurel_exige_une_date_future(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            k = _case(c)
            _figer(c)
            with pytest.raises(edt.DonneesInvalides):
                edt.modifier(c, k["id"], {"nb_aesh": 1}, aujourd_hui=AUJ)
            with pytest.raises(edt.DonneesInvalides):   # semaine en cours
                edt.modifier(c, k["id"], {"nb_aesh": 1},
                             a_partir_du="2026-09-28", aujourd_hui=AUJ)
            with pytest.raises(edt.DonneesInvalides):   # pas un lundi
                edt.modifier(c, k["id"], {"nb_aesh": 1},
                             a_partir_du="2026-10-06", aujourd_hui=AUJ)

    def test_scission_et_heritage_des_affectations(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            k = _case(c)
            c.execute("INSERT INTO affectation_seance (id, classe_id, annee, "
                      "edt_creneau_id, affectation) VALUES ('a1', 'cl_4e3', ?, ?, "
                      "'automatisme')", (ANNEE, k["id"]))
            _figer(c)
            n = edt.modifier(c, k["id"], {"nb_aesh": 2}, a_partir_du=PROCHAIN,
                             aujourd_hui=AUJ)
            assert n["id"] != k["id"] and n["scindee_de"] == k["id"]
            assert n["valide_du"] == PROCHAIN and n["nb_aesh"] == 2
            toutes = edt.lister(c, ANNEE)
            assert [(x["valide_du"], x["valide_au"]) for x in toutes] == [
                ("", PROCHAIN), (PROCHAIN, "")]
            # Cette semaine : l'ancienne case ; la semaine prochaine : la nouvelle.
            assert edt.lister(c, ANNEE, a_la_date=AUJ)[0]["nb_aesh"] == 0
            assert edt.lister(c, ANNEE, a_la_date=date(2026, 10, 8))[0]["nb_aesh"] == 2
            aff = {r["edt_creneau_id"]: r["affectation"] for r in c.execute(
                "SELECT * FROM affectation_seance").fetchall()}
            assert aff == {k["id"]: "automatisme", n["id"]: "automatisme"}

    def test_case_future_modifiee_sur_place(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            k = _case(c)
            _figer(c)
            n = edt.modifier(c, k["id"], {"nb_aesh": 1}, a_partir_du=PROCHAIN,
                             aujourd_hui=AUJ)
            m = edt.modifier(c, n["id"], {"nb_aesh": 3}, a_partir_du=PROCHAIN,
                             aujourd_hui=AUJ)
            assert m["id"] == n["id"] and len(edt.lister(c, ANNEE)) == 2

    def test_ajout_et_suppression_dates(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            k = _case(c)
            _figer(c)
            with pytest.raises(edt.DonneesInvalides):
                _case(c, code="M2")                   # date obligatoire
            nouv = _case(c, code="M2", a_partir_du=PLUS_TARD)
            assert nouv["valide_du"] == PLUS_TARD
            edt.supprimer(c, k["id"], a_partir_du=PROCHAIN, aujourd_hui=AUJ)
            assert edt.lister(c, ANNEE, a_la_date=AUJ)[0]["id"] == k["id"]
            assert edt.lister(c, ANNEE, a_la_date=date(2026, 10, 5)) == []
            # Une case future se supprime vraiment.
            edt.supprimer(c, nouv["id"], aujourd_hui=AUJ)
            assert len(edt.lister(c, ANNEE)) == 1
            # Le créneau libéré au 05/10 peut être réoccupé à partir du 05/10.
            _case(c, a_partir_du=PROCHAIN, classe_id=None, libelle="Concertation")

    def test_chevauchement_de_periodes_refuse(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            _case(c)
            _figer(c)
            with pytest.raises(edt.DonneesInvalides):
                _case(c, a_partir_du=PROCHAIN)

    def test_changements_programmes_et_annulation(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            k1 = _case(c)
            k2 = _case(c, code="M2")
            _figer(c)
            edt.modifier(c, k1["id"], {"semaine": "A"}, a_partir_du=PROCHAIN,
                         aujourd_hui=AUJ)
            edt.supprimer(c, k2["id"], a_partir_du=PROCHAIN, aujourd_hui=AUJ)
            n3 = _case(c, code="M3", a_partir_du=PLUS_TARD)
            ch = edt.changements_programmes(c, ANNEE, "et_test", AUJ)
            assert ch == [{"lundi": PROCHAIN, "debuts": 1, "fins": 2},
                          {"lundi": PLUS_TARD, "debuts": 1, "fins": 0}]
            edt.annuler_changement(c, ANNEE, "et_test", PROCHAIN, AUJ)
            toutes = edt.lister(c, ANNEE)
            assert sorted((x["id"], x["valide_du"], x["valide_au"]) for x in toutes) \
                == sorted([(k1["id"], "", ""), (k2["id"], "", ""),
                           (n3["id"], PLUS_TARD, "")])
            with pytest.raises(edt.DonneesInvalides):   # rien ce lundi-là
                edt.annuler_changement(c, ANNEE, "et_test", PROCHAIN, AUJ)
            with pytest.raises(edt.DonneesInvalides):   # pas dans le passé
                edt.annuler_changement(c, ANNEE, "et_test", "2026-09-28", AUJ)

    def test_annulation_entre_deux_changements(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            k = _case(c)
            _figer(c)
            a = edt.modifier(c, k["id"], {"nb_aesh": 1}, a_partir_du=PROCHAIN,
                             aujourd_hui=AUJ)
            edt.modifier(c, a["id"], {"nb_aesh": 2}, a_partir_du=PLUS_TARD,
                         aujourd_hui=date(2026, 10, 20))
            # Annuler le 05/10 : la case d'origine reprend jusqu'au 02/11.
            edt.annuler_changement(c, ANNEE, "et_test", PROCHAIN, AUJ)
            per = [(x["valide_du"], x["valide_au"], x["nb_aesh"])
                   for x in edt.lister(c, ANNEE)]
            assert per == [("", PLUS_TARD, 0), (PLUS_TARD, "", 2)]


# ── Salle et AESH ────────────────────────────────────────────────────────────

class TestSalleAesh:
    def test_salle_et_aesh(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            s302 = sv.creer(c, "et_test", "302", AUJ)
            k = _case(c, salle_id=s302["id"], nb_aesh=2)
            [x] = edt.lister(c, ANNEE)
            assert x["salle_nom"] == "302" and x["nb_aesh"] == 2
            with pytest.raises(edt.DonneesInvalides):
                _case(c, code="M2", nb_aesh=9)
            autre = sv.creer(c, _etab(c, "et_b"), "B12", AUJ)
            with pytest.raises(edt.DonneesInvalides):
                edt.modifier(c, k["id"], {"salle_id": autre["id"]}, aujourd_hui=AUJ)
            # La salle est désormais utilisée : suppression refusée.
            assert sv.salle_est_utilisee(c, s302["id"])
            with pytest.raises(sv.SalleUtilisee):
                sv.supprimer(c, s302["id"])

    def test_appliquer_salle_partout(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            s302 = sv.creer(c, "et_test", "302", AUJ)
            _case(c); _case(c, code="M2")
            _case(c, code="M3", classe_id=None, usage="autre", libelle="Concertation")
            assert edt.appliquer_salle(c, ANNEE, "et_test", s302["id"],
                                       aujourd_hui=AUJ) == 2
            _figer(c)
            s310 = sv.creer(c, "et_test", "310", AUJ)
            assert edt.appliquer_salle(c, ANNEE, "et_test", s310["id"],
                                       a_partir_du=PROCHAIN, aujourd_hui=AUJ) == 2
            sem = edt.lister(c, ANNEE, a_la_date=date(2026, 10, 5))
            assert {x["salle_nom"] for x in sem if x["classe_id"]} == {"310"}
            assert {x["salle_nom"] for x in edt.lister(c, ANNEE, a_la_date=AUJ)
                    if x["classe_id"]} == {"302"}

    def test_compter_seances_a_la_date(self, store):
        with store._conn() as c:
            _etab(c); _classe(c)
            k = _case(c)
            _case(c, code="M2")
            _figer(c)
            edt.supprimer(c, k["id"], a_partir_du=PROCHAIN, aujourd_hui=AUJ)
            assert edt.compter_seances(c, "cl_4e3", ANNEE, AUJ) == {"A": 2, "B": 2}
            assert edt.compter_seances(c, "cl_4e3", ANNEE,
                                       date(2026, 10, 5)) == {"A": 1, "B": 1}


# ── Projection ───────────────────────────────────────────────────────────────

GRILLE = [{"code": "M1", "heure_debut": "08:25", "heure_fin": "09:20", "ordre": 10},
          {"code": "M2", "heure_debut": "09:25", "heure_fin": "10:20", "ordre": 20}]
VAC_ETE = [{"start_date": "2025-08-01", "end_date": "2025-09-01"}]


def test_projection_suit_les_periodes_et_numerote_en_continu():
    edt_cases = [
        {"id": "a", "jour": "lun", "creneau_code": "M1", "semaine": "AB",
         "valide_du": "", "valide_au": "2025-09-22"},
        {"id": "b", "jour": "mar", "creneau_code": "M2", "semaine": "AB",
         "valide_du": "2025-09-22", "valide_au": ""},
    ]
    s = projeter("2025-2026", edt_cases, GRILLE, VAC_ETE, {})
    # Rentrée (01/09) ignorée ; 08/09 et 15/09 : lundi ; puis mardis.
    assert [x["date"] for x in s[:4]] == ["2025-09-08", "2025-09-15",
                                          "2025-09-23", "2025-09-30"]
    assert [x["edt_creneau_id"] for x in s[:4]] == ["a", "a", "b", "b"]
    assert [x["numero"] for x in s[:4]] == [1, 2, 3, 4]
    # L'alternance A/B continue à travers le changement.
    assert [x["semaine_label"] for x in s[:4]] == ["B", "A", "B", "A"]


def test_projection_sans_periode_inchangee():
    s = projeter("2025-2026", [{"jour": "lun", "creneau_code": "M1",
                                "semaine": "AB"}], GRILLE, VAC_ETE, {})
    assert s[0]["date"] == "2025-09-08"


# ── Aperçu et routes ─────────────────────────────────────────────────────────

class TestRoutes:
    """Les routes utilisent la vraie date du jour : l'année scolaire du test
    est donc l'année courante (sinon l'aperçu compterait 0 séance)."""

    def test_parcours(self, client, app, monkeypatch):
        from services import edt_apercu, annees_scolaires
        monkeypatch.setattr(edt_apercu, "_calendrier",
                            lambda store, annee, academie: ([], {}))
        ANNEE = annees_scolaires.courante()
        with app.json_store._conn() as c:
            _etab(c); _classe(c, annee=ANNEE)
        base = {"annee": ANNEE, "etablissement_id": "et_test"}
        r = client.post("/api/edt", json={**base, "jour": "lun",
                                          "creneau_code": "M1",
                                          "classe_id": "cl_4e3", "nb_aesh": 1})
        assert r.status_code == 201
        kid = r.get_json()["id"]
        client.post("/api/edt", json={**base, "jour": "mar", "creneau_code": "M1",
                                      "classe_id": "cl_4e3"})
        g = client.get(f"/api/edt?annee={ANNEE}&etablissement_id=et_test").get_json()
        assert g["etat"]["etat"] == "en_saisie" and len(g["creneaux"]) == 2
        assert g["date_effet_min"] > g["semaine_courante"]
        assert client.post("/api/edt/figer", json=base).status_code == 200
        lundi = g["date_effet_min"]
        # Aperçu : supprimer la case du lundi retire des séances, sans l'enregistrer.
        ap = client.post("/api/edt/apercu", json={**base, "operation": "supprimer",
                                                  "edt_id": kid,
                                                  "a_partir_du": lundi}).get_json()
        [ligne] = ap["classes"]
        assert ligne["apres"] < ligne["avant"]
        g2 = client.get(f"/api/edt?annee={ANNEE}&etablissement_id=et_test"
                        f"&semaine_du={lundi}").get_json()
        assert len(g2["creneaux"]) == 2          # rien n'a été écrit
        # Suppression datée réelle puis annulation.
        assert client.delete(f"/api/edt/{kid}?a_partir_du={lundi}").status_code == 200
        g3 = client.get(f"/api/edt?annee={ANNEE}&etablissement_id=et_test"
                        f"&semaine_du={lundi}").get_json()
        assert len(g3["creneaux"]) == 1 and g3["changements"][0]["lundi"] == lundi
        assert client.delete(f"/api/edt/changements/{lundi}?annee={ANNEE}"
                             f"&etablissement_id=et_test").status_code == 200
        g4 = client.get(f"/api/edt?annee={ANNEE}&etablissement_id=et_test"
                        f"&semaine_du={lundi}").get_json()
        assert len(g4["creneaux"]) == 2 and g4["changements"] == []
        # Modification sans date sur un EdT figé : refusée.
        r = client.put(f"/api/edt/{kid}", json={"nb_aesh": 2})
        assert r.status_code == 400
