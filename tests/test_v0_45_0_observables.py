"""tests/test_v0_45_0_observables.py — v0.45.0

Observables par niveau : création, renommage, ordre, désactivation, période,
portée commun / individuel (refus de changer s'il y a des exceptions),
exceptions masquer / attribuer avec période et commentaire, liste effective
d'un élève à une date, copie depuis un autre niveau, routes.
"""
import pytest

from persistence.sqlite_store import SqliteStore
from services import observables as ob

ANNEE = "2026-2027"


@pytest.fixture
def conn(tmp_path):
    st = SqliteStore(tmp_path / "data")
    with st._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('et', 'C', 'propose')")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('c1', '4EME3', 'N11', ?, 'et')", (ANNEE,))
        for eid, nom in (("e1", "ALI"), ("e2", "BEN")):
            c.execute("INSERT INTO eleves (id, nom, prenom) VALUES (?,?,'X')", (eid, nom))
            c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES (?, 'c1')", (eid,))
        yield c


def _libs(l, section):
    return [x["libelle"] for x in l[section]]


def test_creer_ordonner_renommer_desactiver(conn):
    a = ob.creer(conn, "N11", "valoriser", "Participation")
    b = ob.creer(conn, "N11", "valoriser", "Entraide")
    ob.creer(conn, "N11", "sanctionner", "Bavardage")
    assert [o["libelle"] for o in ob.lister(conn, "N11") if o["section"] == "valoriser"] \
        == ["Participation", "Entraide"]
    ob.deplacer(conn, b["id"], -1)
    assert [o["libelle"] for o in ob.lister(conn, "N11") if o["section"] == "valoriser"] \
        == ["Entraide", "Participation"]
    ob.modifier(conn, a["id"], {"libelle": "Participation orale"})
    ob.modifier(conn, b["id"], {"actif": False})
    l = ob.liste_effective(conn, "N11", "e1", "2026-10-05")
    assert _libs(l, "valoriser") == ["Participation orale"]
    assert _libs(l, "sanctionner") == ["Bavardage"]
    with pytest.raises(ob.ObservableErreur):
        ob.creer(conn, "N11", "autre", "X")
    with pytest.raises(ob.ObservableErreur):
        ob.modifier(conn, a["id"], {"libelle": "  "})


def test_periode_de_l_observable(conn):
    o = ob.creer(conn, "N11", "sanctionner", "Retard de matériel")
    ob.modifier(conn, o["id"], {"du": "2026-10-01", "au": "2026-12-18"})
    assert _libs(ob.liste_effective(conn, "N11", "e1", "2026-09-30"), "sanctionner") == []
    assert _libs(ob.liste_effective(conn, "N11", "e1", "2026-12-18"), "sanctionner") \
        == ["Retard de matériel"]
    with pytest.raises(ob.ObservableErreur):
        ob.modifier(conn, o["id"], {"du": "2026-12-20", "au": "2026-12-18"})
    with pytest.raises(ob.ObservableErreur):
        ob.modifier(conn, o["id"], {"du": "20/12/2026"})


def test_masquer_un_observable_commun(conn):
    o = ob.creer(conn, "N11", "sanctionner", "Bavardage")
    x = ob.ajouter_exception(conn, o["id"], "e1", commentaire="Aménagement PAP")
    assert x["type"] == "masquer" and x["commentaire"] == "Aménagement PAP"
    assert _libs(ob.liste_effective(conn, "N11", "e1", "2026-10-05"), "sanctionner") == []
    assert _libs(ob.liste_effective(conn, "N11", "e2", "2026-10-05"), "sanctionner") == ["Bavardage"]


def test_attribuer_un_observable_individuel_temporaire(conn):
    o = ob.creer(conn, "N11", "sanctionner", "Téléphone sorti")
    ob.modifier(conn, o["id"], {"portee": "individuel"})
    ob.ajouter_exception(conn, o["id"], "e2", du="2026-10-05", au="2026-11-06",
                         commentaire="Fiche de suivi")
    assert _libs(ob.liste_effective(conn, "N11", "e2", "2026-10-05"), "sanctionner") \
        == ["Téléphone sorti"]
    assert _libs(ob.liste_effective(conn, "N11", "e2", "2026-11-09"), "sanctionner") == []
    assert _libs(ob.liste_effective(conn, "N11", "e1", "2026-10-05"), "sanctionner") == []
    # Changer la portée alors qu'il y a des élèves concernés : refusé.
    with pytest.raises(ob.ObservableErreur):
        ob.modifier(conn, o["id"], {"portee": "commun"})
    assert [e["id"] for e in ob.eleves_avec_exceptions(conn, "N11")] == ["e2"]


def test_exceptions_modifier_supprimer(conn):
    o = ob.creer(conn, "N11", "valoriser", "Aide un camarade")
    ob.modifier(conn, o["id"], {"portee": "individuel"})
    x = ob.ajouter_exception(conn, o["id"], "e1")
    ob.modifier_exception(conn, x["id"], {"au": "2026-10-01", "commentaire": "objectif"})
    assert ob.lister_exceptions(conn, o["id"])[0]["commentaire"] == "objectif"
    assert _libs(ob.liste_effective(conn, "N11", "e1", "2026-10-05"), "valoriser") == []
    ob.supprimer_exception(conn, x["id"])
    assert ob.lister_exceptions(conn, o["id"]) == []
    with pytest.raises(ob.ObservableErreur):
        ob.ajouter_exception(conn, o["id"], "zz")


def test_eleves_du_niveau(conn):
    assert [e["id"] for e in ob.eleves_du_niveau(conn, "N11", ANNEE)] == ["e1", "e2"]
    assert ob.eleves_du_niveau(conn, "N09", ANNEE) == []


def test_copier_depuis(conn):
    ob.creer(conn, "N11", "valoriser", "Participation")
    ind = ob.creer(conn, "N11", "valoriser", "Individuel")
    ob.modifier(conn, ind["id"], {"portee": "individuel"})
    off = ob.creer(conn, "N11", "sanctionner", "Ancien")
    ob.modifier(conn, off["id"], {"actif": False})
    ob.creer(conn, "N09", "valoriser", "participation")
    assert ob.copier_depuis(conn, "N11", "N09") == 0       # déjà présent, autres exclus
    ob.creer(conn, "N11", "sanctionner", "Bavardage")
    assert ob.copier_depuis(conn, "N11", "N09") == 1
    with pytest.raises(ob.ObservableErreur):
        ob.copier_depuis(conn, "N11", "N11")


def test_routes(client):
    r = client.post("/api/observables", json={"niveau": "N11", "section": "valoriser",
                                              "libelle": "Participation"})
    assert r.status_code == 201
    oid = r.get_json()["id"]
    assert client.put(f"/api/observables/{oid}", json={"portee": "individuel"}).status_code == 200
    l = client.get("/api/observables?niveau=N11").get_json()
    assert l["observables"][0]["portee"] == "individuel"
    assert client.post(f"/api/observables/{oid}/exceptions",
                       json={"eleve_id": "absent"}).status_code == 400
    assert client.get("/api/observables/effectifs?niveau=N11&eleve_id=x").get_json() \
        == {"valoriser": [], "sanctionner": []}
    assert client.put("/api/observables/zz", json={"libelle": "a"}).status_code == 404
