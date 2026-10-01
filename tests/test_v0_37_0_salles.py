"""tests/test_v0_37_0_salles.py — v0.37.0

Salles et plans de salle versionnés (services/salles.py), routes REST,
rattachement des salles lors d'une fusion d'établissements, et conversion du
plan TikZ de la salle 302 (services/plan_salle_tikz.py).

« Salle utilisée » : la colonne `edt_creneaux.salle_id` n'arrive qu'en v0.38.
Les tests la simulent en l'ajoutant à la main.
"""
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore
from services import salles as sv
from services import etablissements as etabs
from services.plan_salle_tikz import places_depuis_tikz, PlanTikzErreur

# Jeudi 1er octobre 2026 : lundi de la semaine = 28/09, prochain lundi = 05/10.
AUJ = date(2026, 10, 1)
LUNDI = "2026-09-28"
PROCHAIN = "2026-10-05"
FIXTURE_302 = Path(__file__).parent / "fixtures" / "plan_salle_302.tex"


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def _etab(conn, eid="et_test", nom="Collège test"):
    conn.execute("INSERT OR IGNORE INTO etablissements (id, nom, etat) "
                 "VALUES (?,?, 'propose')", (eid, nom))
    return eid


def _rendre_utilisee(conn, salle_id):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(edt_creneaux)")}
    if "salle_id" not in cols:
        conn.execute("ALTER TABLE edt_creneaux ADD COLUMN salle_id TEXT")
    conn.execute(
        "INSERT INTO edt_creneaux (id, annee, jour, creneau_code, semaine, "
        "etablissement_id, salle_id) VALUES (?,?,?,?,?,?,?)",
        ("edt_" + salle_id, "2026-2027", "lun", "M1", "AB", "et_test", salle_id))


def _p(x, y, angle=0, ilot="", numero=None):
    return {"x": x, "y": y, "angle": angle, "ilot": ilot, "numero": numero}


# ── Schéma ───────────────────────────────────────────────────────────────────

def test_tables_creees(store, tmp_path):
    con = sqlite3.connect(tmp_path / "data" / "seqenseigne.db")
    noms = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"salles", "salle_versions", "salle_places"} <= noms


# ── Salles ───────────────────────────────────────────────────────────────────

class TestSalles:
    def test_creer_avec_version_initiale_vide(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), " 302 ", AUJ)
            vs = sv.lister_versions(c, s["id"], AUJ)
        assert s["nom"] == "302" and s["nb_places"] == 0
        assert not s["utilisee"] and not s["archivee"]
        assert [v["date_effet"] for v in vs] == [""]
        assert vs[0]["statut"] == "en_vigueur"

    def test_nom_obligatoire_et_unique_insensible_casse(self, store):
        with store._conn() as c:
            e = _etab(c)
            sv.creer(c, e, "Salle B", AUJ)
            with pytest.raises(sv.DonneesInvalides):
                sv.creer(c, e, "salle b", AUJ)
            with pytest.raises(sv.DonneesInvalides):
                sv.creer(c, e, "   ", AUJ)

    def test_meme_nom_dans_deux_etablissements(self, store):
        with store._conn() as c:
            sv.creer(c, _etab(c, "et_a", "A"), "302", AUJ)
            sv.creer(c, _etab(c, "et_b", "B"), "302", AUJ)

    def test_etablissement_inconnu(self, store):
        with store._conn() as c:
            with pytest.raises(sv.DonneesInvalides):
                sv.creer(c, "et_absent", "302", AUJ)

    def test_renommer_et_archiver(self, store):
        with store._conn() as c:
            e = _etab(c)
            s = sv.creer(c, e, "302", AUJ)
            sv.creer(c, e, "310", AUJ)
            with pytest.raises(sv.DonneesInvalides):
                sv.modifier(c, s["id"], {"nom": "310"}, AUJ)
            m = sv.modifier(c, s["id"], {"nom": "302 bis", "archivee": True}, AUJ)
            assert m["nom"] == "302 bis" and m["archivee"]
            # Les salles archivées sont listées après les autres.
            assert [x["nom"] for x in sv.lister(c, e, AUJ)] == ["310", "302 bis"]
            assert not sv.modifier(c, s["id"], {"archivee": False}, AUJ)["archivee"]

    def test_supprimer_salle_non_utilisee(self, store):
        with store._conn() as c:
            e = _etab(c)
            s = sv.creer(c, e, "302", AUJ)
            sv.enregistrer_plan(c, s["id"], [_p(0, 0)], AUJ)
            sv.supprimer(c, s["id"])
            assert sv.lister(c, e, AUJ) == []
            assert c.execute("SELECT COUNT(*) FROM salle_places").fetchone()[0] == 0

    def test_supprimer_salle_utilisee_refuse(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), "302", AUJ)
            _rendre_utilisee(c, s["id"])
            assert sv.lire(c, s["id"], AUJ)["utilisee"]
            with pytest.raises(sv.SalleUtilisee):
                sv.supprimer(c, s["id"])
            # … mais l'archivage reste possible.
            assert sv.modifier(c, s["id"], {"archivee": True}, AUJ)["archivee"]

    def test_salle_jamais_utilisee_sans_colonne_edt(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), "302", AUJ)
            assert sv.salle_est_utilisee(c, s["id"]) is False


# ── Numérotation des places ──────────────────────────────────────────────────

class TestNumerotation:
    def test_nouvelles_places_numerotees_dans_l_ordre(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), "302", AUJ)
            plan = sv.enregistrer_plan(c, s["id"], [_p(0, 0), _p(60, 0)], AUJ)
        assert [p["numero"] for p in plan["places"]] == [1, 2]
        assert plan["prochain_numero"] == 3

    def test_numero_supprime_jamais_reattribue(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), "302", AUJ)
            sv.enregistrer_plan(c, s["id"], [_p(0, 0), _p(60, 0), _p(120, 0)], AUJ)
            # On supprime la place 3 puis on en ajoute une nouvelle.
            plan = sv.enregistrer_plan(
                c, s["id"], [_p(0, 0, numero=1), _p(60, 0, numero=2), _p(9, 9)], AUJ)
        assert [p["numero"] for p in plan["places"]] == [1, 2, 4]

    def test_numero_inconnu_ou_double_refuse(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), "302", AUJ)
            sv.enregistrer_plan(c, s["id"], [_p(0, 0)], AUJ)
            with pytest.raises(sv.DonneesInvalides):
                sv.enregistrer_plan(c, s["id"], [_p(0, 0, numero=7)], AUJ)
            with pytest.raises(sv.DonneesInvalides):
                sv.enregistrer_plan(c, s["id"],
                                    [_p(0, 0, numero=1), _p(5, 5, numero=1)], AUJ)

    def test_valeurs_normalisees(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), "302", AUJ)
            plan = sv.enregistrer_plan(c, s["id"], [_p(10.04, 20.06, -5, "i1")], AUJ)
            p = plan["places"][0]
            assert (p["x"], p["y"], p["angle"], p["ilot"]) == (10.0, 20.1, 355.0, "i1")
            with pytest.raises(sv.DonneesInvalides):
                sv.enregistrer_plan(c, s["id"], [_p("abc", 0)], AUJ)
            with pytest.raises(sv.DonneesInvalides):
                sv.enregistrer_plan(c, s["id"], "pas une liste", AUJ)


# ── Versions ─────────────────────────────────────────────────────────────────

class TestVersions:
    def test_salle_non_utilisee_edition_en_place(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), "302", AUJ)
            sv.enregistrer_plan(c, s["id"], [_p(0, 0)], AUJ)
            sv.enregistrer_plan(c, s["id"], [_p(0, 0, numero=1), _p(60, 0)], AUJ)
            vs = sv.lister_versions(c, s["id"], AUJ)
        assert len(vs) == 1 and vs[0]["nb_places"] == 2

    def test_salle_utilisee_exige_une_date_d_effet(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), "302", AUJ)
            v0 = sv.lister_versions(c, s["id"], AUJ)[0]["id"]
            _rendre_utilisee(c, s["id"])
            with pytest.raises(sv.VersionFigee):
                sv.enregistrer_plan(c, s["id"], [_p(0, 0)], AUJ)
            with pytest.raises(sv.VersionFigee):
                sv.enregistrer_plan(c, s["id"], [_p(0, 0)], AUJ, version_id=v0)
            assert sv.lire_plan(c, s["id"], AUJ)["version"]["modifiable"] is False

    def test_date_d_effet_lundi_a_partir_de_la_semaine_prochaine(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), "302", AUJ)
            _rendre_utilisee(c, s["id"])
            with pytest.raises(sv.VersionFigee):      # semaine en cours
                sv.enregistrer_plan(c, s["id"], [], AUJ, date_effet=LUNDI)
            with pytest.raises(sv.DonneesInvalides):  # pas un lundi
                sv.enregistrer_plan(c, s["id"], [], AUJ, date_effet="2026-10-06")
            with pytest.raises(sv.DonneesInvalides):
                sv.enregistrer_plan(c, s["id"], [], AUJ, date_effet="05/10/2026")
            plan = sv.enregistrer_plan(c, s["id"], [_p(0, 0)], AUJ,
                                       date_effet=PROCHAIN)
        assert plan["version"]["date_effet"] == PROCHAIN
        assert plan["version"]["statut"] == "future"
        assert plan["version"]["modifiable"] is True
        assert plan["date_effet_min"] == PROCHAIN

    def test_version_future_remplacee_puis_en_vigueur(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), "302", AUJ)
            sv.enregistrer_plan(c, s["id"], [_p(0, 0)], AUJ)
            _rendre_utilisee(c, s["id"])
            sv.enregistrer_plan(c, s["id"], [_p(0, 0, numero=1), _p(60, 0)], AUJ,
                                date_effet=PROCHAIN)
            # Même date : la version future est remplacée, pas dupliquée.
            fut = sv.enregistrer_plan(c, s["id"], [_p(1, 1, numero=1)], AUJ,
                                      date_effet=PROCHAIN)
            assert len(sv.lister_versions(c, s["id"], AUJ)) == 2
            # Modifiable aussi par son id tant qu'elle est future.
            sv.enregistrer_plan(c, s["id"], [_p(2, 2, numero=1)], AUJ,
                                version_id=fut["version"]["id"])
            # Cette semaine : l'ancienne version ; la semaine prochaine : la nouvelle.
            assert len(sv.lire_plan(c, s["id"], AUJ)["places"]) == 1
            assert sv.lire_plan(c, s["id"], AUJ)["places"][0]["x"] == 0
            semaine_proch = sv.lire_plan(c, s["id"], AUJ, d=date(2026, 10, 7))
            assert semaine_proch["places"][0]["x"] == 2
            # Vu depuis le 7 octobre, l'ancienne version est passée.
            statuts = [v["statut"] for v in
                       sv.lister_versions(c, s["id"], date(2026, 10, 7))]
            assert statuts == ["passee", "en_vigueur"]
            # … et la nouvelle n'est plus modifiable.
            with pytest.raises(sv.VersionFigee):
                sv.enregistrer_plan(c, s["id"], [], date(2026, 10, 7),
                                    version_id=fut["version"]["id"])

    def test_numerotation_stable_entre_versions(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), "302", AUJ)
            sv.enregistrer_plan(c, s["id"], [_p(0, 0), _p(60, 0)], AUJ)
            _rendre_utilisee(c, s["id"])
            # Nouvelle version : la place 2 disparaît, une place est ajoutée.
            plan = sv.enregistrer_plan(c, s["id"], [_p(0, 0, numero=1), _p(0, 90)],
                                       AUJ, date_effet=PROCHAIN)
        assert [p["numero"] for p in plan["places"]] == [1, 3]

    def test_supprimer_versions(self, store):
        with store._conn() as c:
            s = sv.creer(c, _etab(c), "302", AUJ)
            v0 = sv.lister_versions(c, s["id"], AUJ)[0]["id"]
            _rendre_utilisee(c, s["id"])
            fut = sv.enregistrer_plan(c, s["id"], [_p(0, 0)], AUJ,
                                      date_effet=PROCHAIN)["version"]["id"]
            with pytest.raises(sv.DonneesInvalides):   # version initiale
                sv.supprimer_version(c, v0, AUJ)
            # Une version devenue en vigueur ne se supprime plus.
            with pytest.raises(sv.VersionFigee):
                sv.supprimer_version(c, fut, date(2026, 10, 7))
            sv.supprimer_version(c, fut, AUJ)
            assert len(sv.lister_versions(c, s["id"], AUJ)) == 1
            with pytest.raises(sv.VersionIntrouvable):
                sv.supprimer_version(c, fut, AUJ)

    def test_lire_plan_version_d_une_autre_salle(self, store):
        with store._conn() as c:
            e = _etab(c)
            a, b = sv.creer(c, e, "A", AUJ), sv.creer(c, e, "B", AUJ)
            vb = sv.lister_versions(c, b["id"], AUJ)[0]["id"]
            with pytest.raises(sv.VersionIntrouvable):
                sv.lire_plan(c, a["id"], AUJ, version_id=vb)


# ── Fusion d'établissements ──────────────────────────────────────────────────

class TestFusion:
    def test_salles_rattachees_a_la_cible(self, store):
        src = etabs.creer(store, nom="Source")
        cib = etabs.creer(store, nom="Cible")
        with store._conn() as c:
            sv.creer(c, src["id"], "302", AUJ)
        r = etabs.fusionner(store, src["id"], cib["id"])
        assert r["salles_migrees"] == 1
        with store._conn() as c:
            assert [s["nom"] for s in sv.lister(c, cib["id"], AUJ)] == ["302"]

    def test_conflit_de_nom_refuse_la_fusion(self, store):
        src = etabs.creer(store, nom="Source")
        cib = etabs.creer(store, nom="Cible")
        with store._conn() as c:
            sv.creer(c, src["id"], "302", AUJ)
            sv.creer(c, cib["id"], "302", AUJ)
        with pytest.raises(etabs.ConflitFusion) as ei:
            etabs.fusionner(store, src["id"], cib["id"])
        assert ei.value.code == "conflit_salle"
        assert store.lire_etablissement_par_id(src["id"]) is not None


# ── Routes ───────────────────────────────────────────────────────────────────

class TestRoutes:
    def test_parcours_complet(self, client, app):
        with app.json_store._conn() as c:
            _etab(c)
        r = client.post("/api/etablissements/et_test/salles", json={"nom": "302"})
        assert r.status_code == 201
        sid = r.get_json()["id"]
        assert client.post("/api/etablissements/et_test/salles",
                           json={"nom": "302"}).status_code == 400
        r = client.put(f"/api/salles/{sid}/plan",
                       json={"places": [_p(100, 100, 30, "i1"), _p(160, 100, 30, "i1")]})
        assert r.status_code == 200
        assert [p["numero"] for p in r.get_json()["places"]] == [1, 2]
        plan = client.get(f"/api/salles/{sid}/plan").get_json()
        assert plan["version"]["modifiable"] and len(plan["places"]) == 2
        assert len(client.get(f"/api/salles/{sid}/versions").get_json()["versions"]) == 1
        lst = client.get("/api/etablissements/et_test/salles").get_json()["salles"]
        assert lst[0]["nb_places"] == 2
        assert client.put(f"/api/salles/{sid}", json={"archivee": True}
                          ).get_json()["archivee"] is True
        assert client.delete(f"/api/salles/{sid}").status_code == 200
        assert client.get(f"/api/salles/{sid}/plan").status_code == 404


# ── Conversion du plan TikZ de la salle 302 ──────────────────────────────────

@pytest.fixture(scope="module")
def places():
    return places_depuis_tikz(FIXTURE_302.read_text(encoding="utf-8"))


class TestPlanTikz:

    def test_33_places_numerotees(self, places):
        assert len(places) == 33
        assert [p["numero"] for p in places] == list(range(1, 34))

    def test_ilots_par_contact(self, places):
        from collections import Counter
        tailles = sorted(Counter(p["ilot"] for p in places).values(), reverse=True)
        assert tailles == [6, 4, 4, 4, 4, 4, 3, 2, 2]

    def test_paire_du_haut_numerotee_en_premier(self, places):
        p1, p2 = places[0], places[1]
        assert p1["ilot"] == p2["ilot"]
        assert p1["y"] == p2["y"] == min(p["y"] for p in places)
        assert p1["x"] < p2["x"] and p1["angle"] == p2["angle"] == 0

    def test_tables_60x40_espacees_d_un_grand_cote(self, places):
        # Deux tables accolées par le petit côté : centres à 60 cm.
        assert round(places[1]["x"] - places[0]["x"], 1) == 60.0

    def test_angles_du_plan(self, places):
        assert {p["angle"] for p in places} == {
            0, 20, 30, 60, 70, 90, 110, 120, 150, 160}

    def test_plan_sans_tikz(self):
        with pytest.raises(PlanTikzErreur):
            places_depuis_tikz("\\begin{document}rien\\end{document}")

    def test_import_cli(self, tmp_path):
        from outils.importer_plan_salle_tikz import main
        st = SqliteStore(tmp_path / "data")
        with st._conn() as c:
            _etab(c)
        db = str(tmp_path / "data" / "seqenseigne.db")
        assert main([str(FIXTURE_302), "--salle", "302", "--db", db]) == 0  # dry-run
        with st._conn() as c:
            assert sv.lister(c, "et_test", AUJ) == []
        assert main([str(FIXTURE_302), "--salle", "302", "--db", db, "--apply"]) == 0
        with st._conn() as c:
            [s] = sv.lister(c, "et_test", AUJ)
            assert s["nom"] == "302" and s["nb_places"] == 33
        with pytest.raises(SystemExit):      # la salle existe déjà
            main([str(FIXTURE_302), "--salle", "302", "--db", db, "--apply"])
