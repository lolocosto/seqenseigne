"""tests/test_v0_49_1_documents_mer.py — v0.49.1

Documents de MER (référentiel de MER de la structure figée) : placement
automatique à la séance de MER de rang n dans sa partie, délai « fin de la
partie de MER » (même échéance pour tous), association manuelle de la
progression de MER (remplace le placement automatique du même fichier ;
distribue un document sans séance), détail de la planification hebdo, sans
progression principale.

Classe c1 en mode MER « progression » : lundi M1 → séances de MER à partir du
14/09 (rentrée ignorée) : 14/09 (1), 21/09 (2), 28/09 (3)… Partie 1 de 3
séances, partie 2 de 2 séances.
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt, grille_horaire as gh
from services import calendrier_scolaire as cal
from services import referentiel_principal_externe as rpe
from services import progression_mer as pm
from services import progression_doc as pgd
from services import documents_seance as docs
from services import planification_hebdo as ph

ANNEE = "2026-2027"
AUJ = date(2026, 9, 1)


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    st = SqliteStore(tmp_path / "data")
    with st._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id, mer_active, "
                  "mer_mode) VALUES ('c1', '6EME3', 'N09', ?, 'et', 1, 'progression')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", aujourd_hui=date(2026, 8, 25))
        rid = rpe.creer(c, "N09", ANNEE, type_ref="mer")["id"]
        rpe.ajouter_sequence(c, rid, "Calcul mental")
        rpe.ajouter_partie(c, rid, "M01", 3, AUJ, libelle="Série 1")
        rpe.ajouter_partie(c, rid, "M01", 2, AUJ, libelle="Série 2")
        f_cours = rpe.ajouter_fichier(c, rid, "M01", 1, nom_fichier="cours.pdf", contenu=b"%",
                                      mime="application/pdf", data_dir=st.data_dir)
        f_test = rpe.ajouter_fichier(c, rid, "M01", 1, nom_fichier="test.pdf", contenu=b"%",
                                     mime="application/pdf", data_dir=st.data_dir)
        f_s2 = rpe.ajouter_fichier(c, rid, "M01", 2, nom_fichier="serie2.pdf", contenu=b"%",
                                   mime="application/pdf", data_dir=st.data_dir)
        rpe.placer_fichier(c, f_cours["id"], 1)
        rpe.placer_fichier(c, f_test["id"], 1, "faire", "fin_partie")
        prog = pm.creer_ou_lire(c, "N09", ANNEE)
        pm.definir_referentiel(c, prog["id"], rid, "fige")
        for num in (1, 2):
            pm.poser_partie(c, prog["id"], f"{rid}|M01|{num}", "fige")
    return st, rid, prog["id"], f_cours["id"], f_test["id"], f_s2["id"]


def _prevus(st):
    with st._conn() as c:
        return {d["libelle"]: d for d in docs.documents_prevus(c, st, ANNEE, "c1")}


def test_placement_automatique_et_fin_de_partie(ctx):
    st, *_ = ctx
    p = _prevus(st)
    assert p["cours.pdf"]["date"] == "2026-09-14"
    t = p["test.pdf"]
    assert t["retour"] == "faire" and t["echeance"] == ("2026-09-28", "M1")   # fin de la partie 1
    assert "serie2.pdf" not in p                                             # pas de séance


def test_association_manuelle(ctx):
    st, rid, prog_id, f_cours, f_test, f_s2 = ctx
    with st._conn() as c:
        pgd.ajouter(c, prog_kind="mer", prog_ref=prog_id, creneau_ref=f"{rid}|M01|1",
                    rang_seance=2, doc_source="externe", doc_ref=f_cours, doc_libelle="Cours (avancé)")
        pgd.ajouter(c, prog_kind="mer", prog_ref=prog_id, creneau_ref=f"{rid}|M01|2",
                    rang_seance=2, doc_source="externe", doc_ref=f_s2, doc_libelle="Série 2",
                    retour="rendre", delai_type="prochaine")
    p = _prevus(st)
    assert "cours.pdf" not in p and p["Cours (avancé)"]["date"] == "2026-09-21"
    assert p["Série 2"]["date"] == "2026-10-12" and p["Série 2"]["retour"] == "rendre"


def test_detail_planification(ctx):
    st, *_ = ctx
    with st._conn() as c:
        d = ph.detail_seance(c, st, ANNEE, "c1", "2026-09-14", "M1")
    assert [x["libelle"] for x in d["docs_a_distribuer"]] == ["cours.pdf", "test.pdf"]


def test_delai_fin_partie_valide():
    assert pgd._valider_retour("faire", "fin_partie", 1) == ("faire", "fin_partie", 1)
    assert pgd.delai_en_jours("fin_partie", 1) == 0


def test_classe_sans_mer(ctx):
    st, *_ = ctx
    with st._conn() as c:
        c.execute("UPDATE classes SET mer_active=0 WHERE id='c1'")
    assert _prevus(st) == {}
