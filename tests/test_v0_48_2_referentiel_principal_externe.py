"""tests/test_v0_48_2_referentiel_principal_externe.py — v0.48.2

Référentiel principal externe = référentiel figé de source « externe » :
nom calculé (+ lettre), structure séquences / parties / objectifs (codes
d'objectifs renumérotés), fichiers de tous formats, utilisable dès sa
création par la progression principale, séquence commencée verrouillée
(sauf libellés et ajout de fichiers), séparation interne / externe.
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import referentiel_principal_externe as rpe
from services import progression_doc as pgd

ANNEE = "2026-2027"
AUJ = date(2026, 10, 6)


@pytest.fixture
def st(tmp_path):
    return SqliteStore(tmp_path / "data")


def _ref(st, **kw):
    with st._conn() as c:
        return rpe.creer(c, "N11", ANNEE, **kw)


def test_creation_nom_et_lettre(st):
    a = _ref(st, description="Manuel X")
    b = _ref(st)
    assert a["id"] == "X2026_N11" and a["nom"] == "4e — 2026-2027 — Principal"
    assert b["id"] == "X2026_N11b" and b["nom"].endswith("Principal b")
    assert a["description"] == "Manuel X" and a["etat"] == "en_cours"
    with st._conn() as c:
        assert [r["id"] for r in rpe.lister(c, "N11")] == ["X2026_N11", "X2026_N11b"]
        with pytest.raises(rpe.RefExtErreur):
            rpe.creer(c, "N99", ANNEE)


def test_structure_et_renumerotation(st):
    rid = _ref(st)["id"]
    with st._conn() as c:
        assert rpe.ajouter_sequence(c, rid, "Nombres")["code"] == "S01"
        assert rpe.ajouter_sequence(c, rid, "Géométrie")["code"] == "S02"
        rpe.ajouter_partie(c, rid, "S01", 4, AUJ)
        rpe.ajouter_partie(c, rid, "S01", 3, AUJ)
        rpe.ajouter_objectif(c, rid, "S01", 1, "Comparer", 2)
        rpe.ajouter_objectif(c, rid, "S01", 2, "Ranger", 1)
        rpe.ajouter_objectif(c, rid, "S01", 1, "Encadrer", 2)        # dans la partie 1
        l = rpe.lire(c, rid, AUJ)["sequences"][0]
        assert [(o["code"], o["nom"]) for p in l["parties"] for o in p["objectifs"]] == \
            [("01", "Comparer"), ("02", "Encadrer"), ("03", "Ranger")]
        rpe.deplacer_objectif(c, rid, "S01", "02", -1, AUJ)
        rpe.modifier_objectif(c, rid, "S01", "01", {"critere_f": "sans aide"}, AUJ)
        l = rpe.lire(c, rid, AUJ)["sequences"][0]
        p1 = l["parties"][0]["objectifs"]
        assert [(o["code"], o["nom"]) for o in p1] == [("01", "Encadrer"), ("02", "Comparer")]
        assert p1[0]["critere_f"] == "sans aide"
        # Supprimer la partie 1 : la partie 2 devient 1, objectifs renumérotés.
        rpe.supprimer_partie(c, rid, "S01", 1, AUJ)
        l = rpe.lire(c, rid, AUJ)["sequences"][0]
        assert [p["numero"] for p in l["parties"]] == [1]
        assert [(o["code"], o["nom"]) for o in l["parties"][0]["objectifs"]] == [("01", "Ranger")]
        rpe.deplacer_sequence(c, rid, "S02", -1, AUJ)
        assert [s["code"] for s in rpe.lire(c, rid, AUJ)["sequences"]] == ["S02", "S01"]


def test_fichiers(st, tmp_path):
    rid = _ref(st)["id"]
    with st._conn() as c:
        rpe.ajouter_sequence(c, rid, "Nombres")
        rpe.ajouter_partie(c, rid, "S01", 4, AUJ)
        f1 = rpe.ajouter_fichier(c, rid, "S01", 0, nom_fichier="cours.pdf", contenu=b"%PDF",
                                 mime="application/pdf", data_dir=st.data_dir)
        f2 = rpe.ajouter_fichier(c, rid, "S01", 1, nom_fichier="ex.odt", contenu=b"x",
                                 mime="application/vnd.oasis.opendocument.text",
                                 data_dir=st.data_dir)
        assert f1["affichable"] and not f2["affichable"]
        s = rpe.lire(c, rid, AUJ)["sequences"][0]
        assert [f["nom_fichier"] for f in s["fichiers"]] == ["cours.pdf"]
        assert [f["nom_fichier"] for f in s["parties"][0]["fichiers"]] == ["ex.odt"]
        dispo = pgd.documents_disponibles(c, "N11", ANNEE, "S01")["sequence"]
        assert {d["libelle"] for d in dispo} == {"cours.pdf", "ex.odt (partie 1)"}
        rpe.supprimer_fichier(c, f1["id"], st.data_dir)
        assert not (st.data_dir / f1["chemin"]).exists()


def _progression(st, rid, debut):
    st.ecrire_progression({"niveau": "N11", "annee": ANNEE, "etablissement_id": "et",
                           "referentiel_id": rid,
                           "creneaux": [{"id": "cr1", "sequence": "S01", "partie_debut": 1,
                                         "partie_fin": 1, "ordre": 1,
                                         "date_debut": debut, "date_fin": "2026-12-18"}]})


def test_sequence_commencee_verrouillee(st):
    rid = _ref(st)["id"]
    with st._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('et', 'C', 'propose')")
        rpe.ajouter_sequence(c, rid, "Nombres")
        rpe.ajouter_partie(c, rid, "S01", 4, AUJ)
        rpe.ajouter_objectif(c, rid, "S01", 1, "Comparer", 2)
    _progression(st, rid, "2026-10-05")
    with st._conn() as c:
        ref = rpe.lire(c, rid, AUJ)
        assert ref["utilise"] and ref["etat"] == "utilise" and ref["sequences"][0]["commencee"]
        for action in (lambda: rpe.ajouter_partie(c, rid, "S01", 2, AUJ),
                       lambda: rpe.supprimer_sequence(c, rid, "S01", AUJ),
                       lambda: rpe.ajouter_objectif(c, rid, "S01", 1, "X", 1, AUJ),
                       lambda: rpe.modifier_objectif(c, rid, "S01", "01", {"nb_seances": 5}, AUJ)):
            with pytest.raises(rpe.RefExtErreur):
                action()
        # Restent permis : libellés et fichiers ; nouvelles séquences.
        rpe.modifier_sequence(c, rid, "S01", "Nombres entiers")
        rpe.modifier_objectif(c, rid, "S01", "01", {"nom": "Comparer des entiers"}, AUJ)
        rpe.ajouter_fichier(c, rid, "S01", 0, nom_fichier="a.pdf", contenu=b"%",
                            mime="application/pdf", data_dir=st.data_dir)
        assert rpe.ajouter_sequence(c, rid, "Fractions")["code"] == "S02"
        with pytest.raises(rpe.RefExtErreur):
            rpe.supprimer(c, rid, st.data_dir)                  # utilisé


def test_sequence_planifiee_non_commencee(st):
    rid = _ref(st)["id"]
    with st._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('et', 'C', 'propose')")
        rpe.ajouter_sequence(c, rid, "Nombres")
    _progression(st, rid, "2026-11-02")
    with st._conn() as c:
        assert not rpe.sequence_commencee(c, rid, "S01", AUJ)
        rpe.ajouter_partie(c, rid, "S01", 3, AUJ)               # permis
        with pytest.raises(rpe.RefExtErreur):                   # placée dans une progression
            rpe.supprimer_sequence(c, rid, "S01", AUJ)


def test_separation_interne_externe(client, app):
    from services import referentiels as refs_svc
    with app.json_store._conn() as c:
        rpe.creer(c, "N11", ANNEE)
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat) VALUES "
                  "('2026_N11', 'N11', '2026', 'verrouille')")
    ids_internes = [r["id"] for r in refs_svc.lister_par_niveau(app.json_store, "N11")]
    assert ids_internes == ["2026_N11"]
    r = client.get("/api/referentiels?niveau=N11&etats=verrouille,utilise&externes=1").get_json()
    assert [(x["id"], x.get("source")) for x in r["referentiels"]] == \
        [("2026_N11", "interne"), ("X2026_N11", "externe")]  # v0.48.4 : source toujours renseignée
    assert client.get("/api/referentiels?niveau=N11").get_json()["referentiels"][0]["id"] == "2026_N11"


def test_routes(client, app):
    P = "/api/referentiels-principaux-externes"
    r = client.post(P, json={"niveau": "N11", "annee": ANNEE, "description": "Manuel"})
    assert r.status_code == 201
    rid = r.get_json()["id"]
    assert client.post(f"{P}/{rid}/sequences", json={"nom": "Nombres"}).status_code == 201
    assert client.post(f"{P}/{rid}/sequences/S01/parties", json={"nb_seances": 4}).status_code == 201
    assert client.post(f"{P}/{rid}/sequences/S01/parties/1/objectifs",
                       json={"nom": "Comparer", "nb_seances": 2}).status_code == 201
    import io
    r = client.post(f"{P}/{rid}/sequences/S01/fichiers", data={
        "partie": "1", "fichier": (io.BytesIO(b"%PDF-1.4"), "cours.pdf", "application/pdf")},
        content_type="multipart/form-data")
    assert r.status_code == 201
    fid = r.get_json()["id"]
    g = client.get(f"{P}/fichiers/{fid}")
    assert g.status_code == 200 and "inline" in g.headers["Content-Disposition"]
    l = client.get(f"{P}/{rid}").get_json()
    assert l["sequences"][0]["parties"][0]["objectifs"][0]["code"] == "01"
    assert client.delete(f"{P}/{rid}").status_code == 200
    assert client.get(f"{P}/{rid}").status_code == 404
