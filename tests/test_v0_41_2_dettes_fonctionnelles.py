"""tests/test_v0_41_2_dettes_fonctionnelles.py — v0.41.2

1. Séances de la semaine (planification hebdo, tableau de bord) issues de la
   projection : alternance A/B, versions d'EdT, fériés, semaine de rentrée,
   exceptions MER ; indisponibilités gardées et marquées.
2. Report des affectations MER sur les cases futures d'un changement d'EdT,
   seulement si elles avaient encore l'ancienne valeur.
3. Création de classe par identifiant d'établissement, académies connues,
   recherche d'établissement par nom insensible à la casse et aux espaces.
4. Fusion d'établissements refusée si la source a un EdT, des
   indisponibilités ou une grille horaire personnalisée.
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt, grille_horaire as gh, indisponibilites as ind
from services import affectation as aff
from services import calendrier_scolaire as cal
from services import contexte_projection as ctx
from services import etablissements as etabs
from services import tableau_bord

ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)
VACANCES = [{"description": "Toussaint", "start_date": "2026-10-17",
             "end_date": "2026-11-02"}]
FERIES = {"2026-11-11": "Armistice"}


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [dict(v) for v in VACANCES])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: dict(FERIES))
    return SqliteStore(tmp_path / "data")


@pytest.fixture
def base(store):
    with store._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'Collège', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id, "
                  "mer_active, mer_mode) VALUES ('cl', '4EME3', 'N11', ?, 'et', 1, "
                  "'automatismes')", (ANNEE,))
        ids = {
            "lun": edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="cl", aujourd_hui=AUJ)["id"],
            "marA": edt.ajouter(c, ANNEE, "mar", "M2", "et", semaine="A", classe_id="cl", aujourd_hui=AUJ)["id"],
            "mer": edt.ajouter(c, ANNEE, "mer", "M3", "et", semaine="B", classe_id="cl", aujourd_hui=AUJ)["id"],
        }
    return ids


def _semaine(store, lundi):
    with store._conn() as c:
        return ctx.seances_de_la_semaine(c, store, ANNEE, lundi)


# ── 1. Séances de la semaine ─────────────────────────────────────────────────

class TestSemaine:
    def test_alternance_a_b(self, store, base):
        # Rentrée (31/08) ignorée ; 07/09 = 1re semaine comptée = B ; 14/09 = A.
        s_b = {(x["jour"], x["creneau"]) for x in _semaine(store, "2026-09-07")}
        s_a = {(x["jour"], x["creneau"]) for x in _semaine(store, "2026-09-14")}
        assert s_b == {("lun", "M1"), ("mer", "M3")}
        assert s_a == {("lun", "M1"), ("mar", "M2")}

    def test_rentree_et_vacances_vides(self, store, base):
        assert _semaine(store, "2026-08-31") == []
        assert _semaine(store, "2026-10-19") == []

    def test_ferie_retire(self, store, base):
        # Semaine du 09/11 : le mercredi 11/11 est férié.
        jours = {x["date"] for x in _semaine(store, "2026-11-09")}
        assert "2026-11-11" not in jours

    def test_indispo_gardee_et_marquee(self, store, base):
        with store._conn() as c:
            ind.creer(c, ANNEE, "et", type="journees", date_debut="2026-09-07")
        lun = [x for x in _semaine(store, "2026-09-07") if x["jour"] == "lun"]
        assert lun and lun[0]["indispo"] is True

    def test_types_mer_et_exception(self, store, base):
        with store._conn() as c:
            aff.definir_affectations(c, "cl", ANNEE, [
                {"edt_creneau_id": base["mer"], "affectation": "progression"}])
            aff.ajouter_exception(c, "cl", ANNEE, "2026-09-14", "Sortie")
        t = {x["jour"]: x["type_mer"] for x in _semaine(store, "2026-09-07")}
        assert t == {"lun": "mer_auto", "mer": "mer_prog"}
        t2 = {x["jour"]: x["type_mer"] for x in _semaine(store, "2026-09-14")}
        assert t2["lun"] is None and t2["mar"] == "mer_auto"

    def test_version_d_edt(self, store, base):
        with store._conn() as c:
            edt.figer(c, ANNEE, "et", AUJ)
            edt.supprimer(c, base["lun"], a_partir_du="2026-11-02", aujourd_hui=AUJ)
        assert ("lun", "M1") in {(x["jour"], x["creneau"]) for x in _semaine(store, "2026-10-05")}
        assert ("lun", "M1") not in {(x["jour"], x["creneau"]) for x in _semaine(store, "2026-11-02")}

    def test_tableau_de_bord(self, store, base):
        r = tableau_bord.seances_de_la_semaine(None, store, ANNEE, date(2026, 9, 9))
        par_jour = {j["jour"]: [s["creneau"] for s in j["seances"]] for j in r["jours"]}
        assert par_jour["lun"] == ["M1"] and par_jour["mer"] == ["M3"]
        assert par_jour["mar"] == []

    def test_planification_hebdo(self, client, app, monkeypatch):
        monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
        monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
        with app.json_store._conn() as c:
            c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                      "('et', 'C', 'propose', 'Rennes')")
            gh.peupler_defauts_si_vide(c, "et")
            c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                      "VALUES ('cl', '4EME3', 'N11', ?, 'et')", (ANNEE,))
            edt.ajouter(c, ANNEE, "mar", "M2", "et", semaine="A", classe_id="cl", aujourd_hui=AUJ)
            edt.ajouter(c, ANNEE, "mer", "M3", "et", semaine="B", classe_id="cl", aujourd_hui=AUJ)
        g = client.get(f"/api/planification-hebdo?annee={ANNEE}&lundi=2026-09-07"
                       f"&etablissement_id=et").get_json()
        assert [(x["jour"], x["type_mer"]) for x in g["cases"]] == [("mer", "principale")]


# ── 2. Report des affectations MER ───────────────────────────────────────────

class TestReportAffectation:
    def test_report_si_ancienne_valeur(self, store, base):
        with store._conn() as c:
            aff.definir_affectations(c, "cl", ANNEE, [
                {"edt_creneau_id": base["lun"], "affectation": "automatisme"}])
            edt.figer(c, ANNEE, "et", AUJ)
            n = edt.modifier(c, base["lun"], {"nb_aesh": 1}, a_partir_du="2026-11-02",
                             aujourd_hui=AUJ)          # hérite « automatisme »
            assert aff.cases_suivantes(c, "cl", base["lun"]) == [n["id"]]
            aff.definir_affectations(c, "cl", ANNEE, [
                {"edt_creneau_id": base["lun"], "affectation": "progression"}])
            lu = aff.lire_affectations(c, "cl", ANNEE)
        assert lu[base["lun"]] == "progression" and lu[n["id"]] == "progression"

    def test_pas_de_report_si_choix_propre(self, store, base):
        with store._conn() as c:
            edt.figer(c, ANNEE, "et", AUJ)
            n = edt.modifier(c, base["lun"], {"nb_aesh": 1}, a_partir_du="2026-11-02",
                             aujourd_hui=AUJ)
            aff.definir_affectations(c, "cl", ANNEE, [
                {"edt_creneau_id": n["id"], "affectation": "progression"}])
            aff.definir_affectations(c, "cl", ANNEE, [
                {"edt_creneau_id": base["lun"], "affectation": "automatisme"}])
            lu = aff.lire_affectations(c, "cl", ANNEE)
        assert lu[base["lun"]] == "automatisme" and lu[n["id"]] == "progression"

    def test_report_de_aucun(self, store, base):
        with store._conn() as c:
            aff.definir_affectations(c, "cl", ANNEE, [
                {"edt_creneau_id": base["lun"], "affectation": "automatisme"}])
            edt.figer(c, ANNEE, "et", AUJ)
            n = edt.modifier(c, base["lun"], {"nb_aesh": 1}, a_partir_du="2026-11-02",
                             aujourd_hui=AUJ)
            aff.definir_affectations(c, "cl", ANNEE, [
                {"edt_creneau_id": base["lun"], "affectation": "aucun"}])
            lu = aff.lire_affectations(c, "cl", ANNEE)
        assert base["lun"] not in lu and n["id"] not in lu

    def test_case_sans_suite(self, store, base):
        with store._conn() as c:
            assert aff.cases_suivantes(c, "cl", base["lun"]) == []


# ── 3. Création de classe et établissements ──────────────────────────────────

class TestCreationClasse:
    def test_par_identifiant(self, client, app):
        with app.json_store._conn() as c:
            c.execute("INSERT INTO etablissements (id, nom, etat) VALUES "
                      "('et_x', 'Collège les Hautes Ourmes', 'propose')")
        r = client.post("/api/classes", json={"nom": "4EME9", "niveau": "N11",
                                              "annee": ANNEE, "etablissement_id": "et_x"})
        assert r.status_code == 200
        assert r.get_json()["etablissement_id"] == "et_x"
        assert client.post("/api/classes", json={
            "nom": "4EME8", "etablissement_id": "et_absent"}).status_code == 400
        with app.json_store._conn() as c:
            assert c.execute("SELECT COUNT(*) FROM etablissements").fetchone()[0] == 1

    def test_nom_insensible_casse_et_espaces(self, client, app):
        with app.json_store._conn() as c:
            c.execute("INSERT INTO etablissements (id, nom, etat) VALUES "
                      "('et_x', 'Collège les Hautes Ourmes', 'propose')")
        r = client.post("/api/classes", json={
            "nom": "4EME7", "annee": ANNEE,
            "etablissement": "  collège LES hautes   ourmes "})
        assert r.get_json()["etablissement_id"] == "et_x"

    def test_academies(self, client):
        acas = client.get("/api/academies").get_json()["academies"]
        assert "Rennes" in acas and acas == sorted(acas)
        assert client.post("/api/etablissements", json={
            "nom": "X", "academie": "Atlantide"}).status_code == 400
        r = client.post("/api/etablissements", json={"nom": "X", "academie": "Rennes"})
        assert r.status_code == 201
        eid = r.get_json()["id"]
        assert client.patch(f"/api/etablissements/{eid}",
                            json={"academie": "Atlantide"}).status_code == 400


# ── 4. Fusion d'établissements ───────────────────────────────────────────────

class TestFusion:
    def _deux(self, store):
        src = etabs.creer(store, nom="Collège doublon")
        cib = etabs.creer(store, nom="Collège", academie="Rennes")
        return src["id"], cib["id"]

    def test_doublon_avec_grille_par_defaut(self, store):
        src, cib = self._deux(store)
        with store._conn() as c:
            gh.peupler_defauts_si_vide(c, src)
        etabs.fusionner(store, src, cib)
        with store._conn() as c:
            assert c.execute("SELECT COUNT(*) FROM grille_horaire_creneaux "
                             "WHERE etablissement_id=?", (src,)).fetchone()[0] == 0

    @pytest.mark.parametrize("cas", ["edt", "indispo", "grille"])
    def test_refus(self, store, cas):
        src, cib = self._deux(store)
        with store._conn() as c:
            gh.peupler_defauts_si_vide(c, src)
            if cas == "edt":
                edt.ajouter(c, ANNEE, "lun", "M1", src, aujourd_hui=AUJ)
            elif cas == "indispo":
                ind.creer(c, ANNEE, src, type="journees", date_debut="2026-10-05")
            else:
                c.execute("UPDATE grille_horaire_creneaux SET heure_debut='08:30' "
                          "WHERE etablissement_id=? AND code='M1'", (src,))
        with pytest.raises(etabs.ConflitFusion) as e:
            etabs.fusionner(store, src, cib)
        assert e.value.code == "source_avec_edt"
        assert store.lire_etablissement_par_id(src) is not None
