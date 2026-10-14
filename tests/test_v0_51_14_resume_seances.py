"""tests/test_v0_51_14_resume_seances.py — v0.51.14

Résumé de chaque séance (planification hebdo, tuile Journée) : MER
(automatismes et enveloppes, partie de la progression de MER et rang, aucune),
principale (code et nom de séquence, partie seulement si la séquence en a
plusieurs, rang dans le créneau), documents à distribuer ; cohérent avec le
détail d'une séance ; présent dans la grille de la semaine.
Données fictives.
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import calendrier_scolaire as cal
from services import edt, grille_horaire as gh
from services import leitner
from services import planification_hebdo as ph
from services import progression_mer as pm
from services import referentiel_principal_externe as rpe
from services import seances_resume as sr

ANNEE = "2026-2027"
AUJ = date(2026, 9, 1)


@pytest.fixture
def st(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    st = SqliteStore(tmp_path / "data")
    with st._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        # 4EME3 : principale sur S01 (2 parties) puis S02 (1 partie) ; MER automatismes.
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id, mer_active, "
                  "mer_mode) VALUES ('c4', '4EME3', 'N11', ?, 'et', 1, 'automatismes')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c4", aujourd_hui=date(2026, 8, 25))
        rid = rpe.creer(c, "N11", ANNEE)["id"]
        rpe.ajouter_sequence(c, rid, "Nombres")
        rpe.ajouter_partie(c, rid, "S01", 3, AUJ)
        rpe.ajouter_partie(c, rid, "S01", 4, AUJ)
        rpe.ajouter_objectif(c, rid, "S01", 1, "Comparer", 3)
        rpe.ajouter_objectif(c, rid, "S01", 2, "Ranger", 4)
        rpe.ajouter_sequence(c, rid, "Fractions")
        rpe.ajouter_partie(c, rid, "S02", 2, AUJ)
        rpe.ajouter_objectif(c, rid, "S02", 1, "Simplifier", 2)
        f = rpe.ajouter_fichier(c, rid, "S01", 1, nom_fichier="fiche1.pdf", contenu=b"%",
                                mime="application/pdf", data_dir=st.data_dir)
        rpe.placer_fichier(c, f["id"], 1)
        # 6EME3 : MER en progression (2 parties posées), pas de progression principale.
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id, mer_active, "
                  "mer_mode) VALUES ('c6', '6EME3', 'N09', ?, 'et', 1, 'progression')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M2", "et", classe_id="c6", aujourd_hui=date(2026, 8, 25))
        rmer = rpe.creer(c, "N09", ANNEE, type_ref="mer")["id"]
        rpe.ajouter_sequence(c, rmer, "Calcul mental")
        rpe.ajouter_partie(c, rmer, "M01", 3, AUJ, libelle="Série 1")
        rpe.ajouter_partie(c, rmer, "M01", 2, AUJ, libelle="Série 2")
        rpe.ajouter_objectif(c, rmer, "M01", 1, "Série 1", 3)
        rpe.ajouter_objectif(c, rmer, "M01", 2, "Série 2", 2)
        cours = rpe.ajouter_fichier(c, rmer, "M01", 1, nom_fichier="cours.pdf", contenu=b"%",
                                    mime="application/pdf", data_dir=st.data_dir)
        rpe.placer_fichier(c, cours["id"], 1)
        prog = pm.creer_ou_lire(c, "N09", ANNEE)
        pm.definir_referentiel(c, prog["id"], rmer, "fige")
        for num in (1, 2):
            pm.poser_partie(c, prog["id"], f"{rmer}|M01|{num}", "fige")
    st.ecrire_progression({"niveau": "N11", "annee": ANNEE, "etablissement_id": "et",
                           "referentiel_id": rid,
                           "creneaux": [
                               {"id": "cr1", "sequence": "S01", "partie_debut": 1,
                                "partie_fin": 2, "ordre": 1,
                                "date_debut": "2026-09-28", "date_fin": "2026-11-23"},
                               {"id": "cr2", "sequence": "S02", "partie_debut": 1,
                                "partie_fin": 1, "ordre": 2,
                                "date_debut": "2026-11-30", "date_fin": "2026-12-14"}]})
    return st


def _r(st, cid, d, cr):
    with st._conn() as c:
        return sr.resumer(c, st, ANNEE, [{"classe_id": cid, "date": d, "creneau": cr}])[(cid, d, cr)]


def test_principale_plusieurs_parties_et_mer_automatismes(st):
    r = _r(st, "c4", "2026-09-28", "M1")
    assert r["principale"] == {"code": "S01", "nom": "Nombres", "partie": "1–2", "rang": 1, "nb": 9}
    assert r["docs"] == ["fiche1.pdf"]
    assert r["mer"]["type"] == "auto"
    with st._conn() as c:
        det = ph.detail_seance(c, st, ANNEE, "c4", "2026-09-28", "M1")
    assert r["mer"]["enveloppes"] == det["mer_enveloppes"] == leitner.enveloppes_a_reviser(det["mer_rang"])
    r5 = _r(st, "c4", "2026-10-26", "M1")
    assert (r5["principale"]["rang"], r5["docs"]) == (5, [])


def test_une_seule_partie_pas_de_numero(st):
    r = _r(st, "c4", "2026-12-07", "M1")
    assert r["principale"] == {"code": "S02", "nom": "Fractions", "partie": "", "rang": 2, "nb": 3}


def test_aucune_principale_hors_creneau(st):
    assert _r(st, "c4", "2026-09-14", "M1")["principale"] is None


def test_mer_progression_partie_et_rang(st):
    r1 = _r(st, "c6", "2026-09-14", "M2")          # 1re séance de MER (cf. v0.49.1)
    assert r1["mer"] == {"type": "prog", "partie": {"libelle": "Série 1", "rang": 1, "nb": 3}}
    assert r1["principale"] is None and r1["docs"] == ["cours.pdf"]
    assert _r(st, "c6", "2026-09-21", "M2")["mer"]["partie"]["rang"] == 2
    assert _r(st, "c6", "2026-10-05", "M2")["mer"]["partie"] == {"libelle": "Série 2", "rang": 1,
                                                                  "nb": 2}
    # Au-delà des parties posées : progression sans partie.
    assert _r(st, "c6", "2026-11-30", "M2")["mer"] == {"type": "prog", "partie": None}


def test_classe_sans_mer(st):
    with st._conn() as c:
        c.execute("UPDATE classes SET mer_active=0 WHERE id='c4'")
    assert _r(st, "c4", "2026-09-28", "M1")["mer"] is None


def test_coherent_avec_le_detail(st):
    for cid, d, cr in (("c4", "2026-10-26", "M1"), ("c4", "2026-12-07", "M1"),
                       ("c6", "2026-09-14", "M2")):
        r = _r(st, cid, d, cr)
        with st._conn() as c:
            det = ph.detail_seance(c, st, ANNEE, cid, d, cr)
        p = r["principale"] or {}
        assert (p.get("code", ""), p.get("rang", 0)) == (det["sequence_code"],
                                                         det["rang_dans_partie"])
        if p:
            assert p["nb"] == det["nb_partie"]
        assert r["docs"] == [x["libelle"] for x in det["docs_a_distribuer"]]
        assert (r["mer"] or {}).get("type") == {"mer_auto": "auto", "mer_prog": "prog",
                                                None: None}[det["mer_type"]]


def test_grille_de_la_semaine(st):
    with st._conn() as c:
        g = ph.grille_semaine(c, st, ANNEE, "2026-09-28")
    lundi = {x["classe"]: x["resume"] for x in g["cases"] if x["date"] == "2026-09-28"}
    assert lundi["4EME3"]["principale"]["code"] == "S01"
    assert lundi["6EME3"]["mer"]["partie"]["libelle"] == "Série 1"
