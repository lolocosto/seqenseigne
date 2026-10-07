"""tests/test_v0_48_5_placement_fichiers.py — v0.48.5

Fichiers d'un référentiel principal externe portant leur séance de
distribution dans la partie, leur retour et leur délai : placement
automatique dans la progression principale (créneau couvrant plusieurs
parties compris), remplacement par une association manuelle, conversion en
travail, détail de la planification hebdo ; type des documents de MER.

Classe c1 : lundi M1 ; créneau cr1 S01 parties 1-2 du 28/09 au 23/11 →
séances 28/09 (1), 05/10 (2), 12/10 (3), 19/10 (4), 26/10 (5)…
Partie 1 = 3 séances : la séance 2 de la partie 2 est la 5e du créneau.
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt, grille_horaire as gh
from services import calendrier_scolaire as cal
from services import referentiel_principal_externe as rpe
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
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('c1', '4EME3', 'N11', ?, 'et')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", aujourd_hui=date(2026, 8, 25))
        rid = rpe.creer(c, "N11", ANNEE)["id"]
        rpe.ajouter_sequence(c, rid, "Nombres")
        rpe.ajouter_partie(c, rid, "S01", 3, AUJ)
        rpe.ajouter_partie(c, rid, "S01", 4, AUJ)
        f1 = rpe.ajouter_fichier(c, rid, "S01", 1, nom_fichier="fiche1.pdf", contenu=b"%",
                                 mime="application/pdf", data_dir=st.data_dir)
        f2 = rpe.ajouter_fichier(c, rid, "S01", 2, nom_fichier="dm.pdf", contenu=b"%",
                                 mime="application/pdf", data_dir=st.data_dir)
        tid = next(t["id"] for t in rpe.lister_types(c) if t["libelle"] == "Travail personnel")
        rpe.typer_fichier(c, f2["id"], tid)
        rpe.placer_fichier(c, f1["id"], 1)
        rpe.placer_fichier(c, f2["id"], 2, "rendre", "jours", 7)
    st.ecrire_progression({"niveau": "N11", "annee": ANNEE, "etablissement_id": "et",
                           "referentiel_id": rid,
                           "creneaux": [{"id": "cr1", "sequence": "S01", "partie_debut": 1,
                                         "partie_fin": 2, "ordre": 1,
                                         "date_debut": "2026-09-28", "date_fin": "2026-11-23"}]})
    return st, rid, f1["id"], f2["id"]


def _prevus(st):
    with st._conn() as c:
        return {d["libelle"]: d for d in docs.documents_prevus(c, st, ANNEE, "c1")}


def test_placement_automatique(ctx):
    st, rid, f1, f2 = ctx
    p = _prevus(st)
    assert p["fiche1.pdf"]["date"] == "2026-09-28"
    dm = p["Travail personnel : dm.pdf"]
    assert dm["date"] == "2026-10-26" and dm["retour"] == "rendre" and dm["delai_jours"] == 7


def test_association_manuelle_remplace(ctx):
    st, rid, f1, f2 = ctx
    prog = st.lire_progression_par_triplet("N11", ANNEE, "et")
    with st._conn() as c:
        pgd.ajouter(c, prog_kind="principale", prog_ref=prog["id"], creneau_ref="cr1",
                    rang_seance=4, doc_source="externe", doc_ref=f2, doc_libelle="DM avancé")
    p = _prevus(st)
    assert "Travail personnel : dm.pdf" not in p and p["DM avancé"]["date"] == "2026-10-19"


def test_detail_planification_et_distribution(ctx):
    st, rid, f1, f2 = ctx
    with st._conn() as c:
        d = ph.detail_seance(c, st, ANNEE, "c1", "2026-10-26", "M1")
        assert [x["libelle"] for x in d["docs_a_distribuer"]] == ["Travail personnel : dm.pdf"]
        nv = docs.pour_seance(c, st, ANNEE, "c1", "2026-10-26", "M1", [])["nouveaux"]
        assert nv[0]["retour"] == "rendre"


def test_validations(ctx):
    st, rid, f1, f2 = ctx
    with st._conn() as c:
        fs = rpe.ajouter_fichier(c, rid, "S01", 0, nom_fichier="seq.pdf", contenu=b"%",
                                 mime="application/pdf", data_dir=st.data_dir)
        with pytest.raises(rpe.RefExtErreur):
            rpe.placer_fichier(c, fs["id"], 2)                  # fichier de séquence
        with pytest.raises(rpe.RefExtErreur):
            rpe.placer_fichier(c, f1, 1, "zz")
        rpe.placer_fichier(c, f1, 0)                            # retirer la séance
    assert "fiche1.pdf" not in _prevus(st)


def test_type_document_mer(app, client):
    from services import referentiel_externe as rx
    with app.json_store._conn() as c:
        r = rx.creer(c, niveau="N09", annee=ANNEE)
        c.execute("INSERT INTO referentiel_externe_doc (id, partie_id, nom_fichier, chemin) "
                  "VALUES ('d1', 'p1', 'calcul.pdf', 'x')")
        tid = rpe.lister_types(c)[0]["id"]
    assert client.put("/api/referentiels-externes/docs/d1/type",
                      json={"type_id": tid}).status_code == 200
    with app.json_store._conn() as c:
        assert c.execute("SELECT type_id FROM referentiel_externe_doc WHERE id='d1'").fetchone()[0] == tid
    assert client.put("/api/referentiels-externes/docs/d1/type",
                      json={"type_id": "zz"}).status_code == 400
