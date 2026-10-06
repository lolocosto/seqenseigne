"""tests/test_v0_48_3_types_documents.py — v0.48.3

Types de documents (liste par défaut, extensible, désactivable, ordonnée) et
type de chaque fichier d'un référentiel principal externe ; libellé dans les
documents associables de la progression ; routes.
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import referentiel_principal_externe as rpe
from services import progression_doc as pgd

AUJ = date(2026, 10, 6)


@pytest.fixture
def st(tmp_path):
    return SqliteStore(tmp_path / "data")


def test_types_par_defaut_et_parametrage(st):
    with st._conn() as c:
        assert [t["libelle"] for t in rpe.lister_types(c)] == list(rpe.TYPES_DEFAUT)
        t = rpe.ajouter_type(c, "Fiche méthode")
        with pytest.raises(rpe.RefExtErreur):
            rpe.ajouter_type(c, "évaluation")
        rpe.deplacer_type(c, t["id"], -1)
        assert [x["libelle"] for x in rpe.lister_types(c)][-2:] == ["Fiche méthode",
                                                                     "Activité complémentaire"]
        rpe.modifier_type(c, t["id"], {"actif": False})
        assert "Fiche méthode" not in [x["libelle"] for x in rpe.lister_types(c)]
        assert "Fiche méthode" in [x["libelle"] for x in rpe.lister_types(c, True)]


def test_type_d_un_fichier(st):
    with st._conn() as c:
        rid = rpe.creer(c, "N11", "2026-2027")["id"]
        rpe.ajouter_sequence(c, rid, "Nombres")
        f = rpe.ajouter_fichier(c, rid, "S01", 0, nom_fichier="exos.pdf", contenu=b"%",
                                mime="application/pdf", data_dir=st.data_dir)
        tid = next(t["id"] for t in rpe.lister_types(c) if t["libelle"] == "Livret d'exercices")
        rpe.typer_fichier(c, f["id"], tid)
        s = rpe.lire(c, rid, AUJ)["sequences"][0]
        assert s["fichiers"][0]["type_libelle"] == "Livret d'exercices"
        dispo = pgd.documents_disponibles(c, "N11", "2026-2027", "S01")["sequence"]
        assert dispo[0]["libelle"] == "Livret d'exercices : exos.pdf"
        with pytest.raises(rpe.RefExtErreur):
            rpe.typer_fichier(c, f["id"], "inconnu")
        rpe.typer_fichier(c, f["id"], "")
        assert rpe.lire(c, rid, AUJ)["sequences"][0]["fichiers"][0]["type_libelle"] == ""


def test_routes(client):
    l = client.get("/api/types-documents").get_json()["types"]
    assert len(l) == 6
    r = client.post("/api/types-documents", json={"libelle": "Fiche méthode"})
    assert r.status_code == 201
    tid = r.get_json()["id"]
    assert client.put(f"/api/types-documents/{tid}", json={"actif": False}).status_code == 200
    assert len(client.get("/api/types-documents").get_json()["types"]) == 6
    assert len(client.get("/api/types-documents?tout=1").get_json()["types"]) == 7
    assert client.post(f"/api/types-documents/{tid}/deplacer", json={"sens": -1}).status_code == 200
