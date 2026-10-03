"""tests/test_v0_43_2_mer_debut_non_faite.py — v0.43.2

Début effectif des mises en route (par classe × année) et « mise en route
non faite » cochée au début de séance : dans les deux cas la suite des MER se
décale (la séance n° 1, ou la séance reportée, est la suivante).
"""
from datetime import date, datetime

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt, grille_horaire as gh
from services import affectation as aff
from services import calendrier_scolaire as cal
from services import planification_hebdo as ph
from services import seance

ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    st = SqliteStore(tmp_path / "data")
    with st._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id, "
                  "mer_active, mer_mode) VALUES ('c1', '4EME3', 'N11', ?, 'et', 1, "
                  "'automatismes')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", aujourd_hui=AUJ)
    return st


def _rang(store, jour):
    with store._conn() as c:
        return ph.detail_seance(c, store, ANNEE, "c1", jour, "M1")["mer_rang"]


def test_neutralisations():
    n = aff.Neutralisations({"2026-10-12"}, "2026-10-05")
    assert "2026-09-28" in n and "2026-10-12" in n and "2026-10-05" not in n
    assert bool(aff.Neutralisations(set(), "2026-10-05")) is True
    assert bool(aff.Neutralisations(set(), "")) is False


class TestDebutEffectif:
    def test_decalage_de_la_numerotation(self, store):
        # Semaine de rentrée ignorée par la projection : 14/09 = séance 1.
        assert _rang(store, "2026-09-14") == 1
        assert _rang(store, "2026-10-05") == 4
        with store._conn() as c:
            assert aff.definir_date_debut(c, "c1", ANNEE, "2026-09-28") == "2026-09-28"
        assert _rang(store, "2026-09-21") == 0          # avant : pas de MER
        assert _rang(store, "2026-09-28") == 1
        assert _rang(store, "2026-10-05") == 2
        with store._conn() as c:
            aff.definir_date_debut(c, "c1", ANNEE, "")
        assert _rang(store, "2026-10-05") == 4

    def test_date_invalide(self, store):
        with store._conn() as c:
            with pytest.raises(aff.DonneesInvalides):
                aff.definir_date_debut(c, "c1", ANNEE, "28/09/2026")

    def test_route_config_sans_toucher_au_mode(self, client, app):
        with app.json_store._conn() as c:
            aff.definir_mode(c, "cx", ANNEE, "classe_entiere") \
                if "classe_entiere" in aff.MODES else None
            mode_avant = aff.lire_mode(c, "cx", ANNEE)
        r = client.put("/api/classes/cx/affectation-config",
                       json={"annee": ANNEE, "date_debut": "2026-09-28"}).get_json()
        assert r["date_debut"] == "2026-09-28" and r["mode"] == mode_avant
        g = client.get(f"/api/classes/cx/affectation-config?annee={ANNEE}").get_json()
        assert g["date_debut"] == "2026-09-28"


class TestNonFaite:
    def test_cocher_decaler_decocher(self, store):
        assert _rang(store, "2026-10-12") == 5
        with store._conn() as c:
            r = seance.marquer_mer_non_faite(c, store, ANNEE, "c1", "2026-10-05", "M1",
                                             True, "Exercice incendie")
            assert r["non_faite"]["motif"] == "Exercice incendie"
        assert _rang(store, "2026-10-05") == 0
        assert _rang(store, "2026-10-12") == 4           # reportée
        with store._conn() as c:
            l = seance.lire(c, store, ANNEE, "c1", "2026-10-05", "M1", datetime(2026, 10, 5, 9))
            assert l["mise_en_route"]["non_faite"]["motif"] == "Exercice incendie"
            assert l["mise_en_route"]["type"] is None and l["mise_en_route"]["active"]
            # Recocher met à jour le commentaire, sans doublon.
            seance.marquer_mer_non_faite(c, store, ANNEE, "c1", "2026-10-05", "M1", True, "")
            assert len(aff.lister_exceptions(c, "c1", ANNEE)) == 1
            assert aff.lister_exceptions(c, "c1", ANNEE)[0]["motif"] == "Mise en route non faite"
            seance.marquer_mer_non_faite(c, store, ANNEE, "c1", "2026-10-05", "M1", False)
            assert aff.lister_exceptions(c, "c1", ANNEE) == []
        assert _rang(store, "2026-10-12") == 5

    def test_seance_inexistante(self, store):
        with store._conn() as c:
            with pytest.raises(seance.SeanceErreur):
                seance.marquer_mer_non_faite(c, store, ANNEE, "c1", "2026-10-06", "M1", True)


def test_route_non_faite(client, app, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    with app.json_store._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id, "
                  "mer_active, mer_mode) VALUES ('c1', '4E', 'N11', ?, 'et', 1, "
                  "'automatismes')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", aujourd_hui=AUJ)
    r = client.put("/api/seance/mer-non-faite", json={
        "annee": ANNEE, "classe_id": "c1", "date": "2026-10-05", "creneau": "M1",
        "non_faite": True, "commentaire": "Sortie"}).get_json()
    assert r["non_faite"]["motif"] == "Sortie"
