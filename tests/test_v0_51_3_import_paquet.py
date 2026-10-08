"""tests/test_v0_51_3_import_paquet.py — v0.51.3

Import d'un paquet de publication dans l'appli en ligne (profil classe), sur
une base séparée : nouveaux référentiels, structure et fichiers en place,
lecture par les écrans de classe (documents, synthèse, parties), paquet
identique, mise à jour avec rapport, refus (séquence commencée, base
partagée), documents orphelins signalés, paquet corrompu, routes.
"""
import io
import json
import shutil
import zipfile
from datetime import date

import pytest

from app import create_app
from services import format_referentiel as fmt
from services import import_publication as imp
from services import paquet_publication as pqt
from services import referentiel_principal_externe as rpe

from test_v0_51_1_format_referentiel import AUJ, _externe, _interne


@pytest.fixture
def apps(data_dir, tmp_path):
    copie = tmp_path / "data_classe"
    shutil.copytree(data_dir, copie, ignore=shutil.ignore_patterns("*.db"))
    atelier = create_app(data_dir, profil="atelier")
    classe = create_app(copie, profil="classe")
    for a in (atelier, classe):
        a.config["TESTING"] = True
    return atelier, classe


def _paquet(app, rids):
    with app.json_store._conn() as c:
        return pqt.creer(c, app.json_store.data_dir, rids)[0]


def _importer(app, contenu, auj=None):
    return imp.importer(app.json_store._conn, app.json_store.data_dir, contenu, auj)


def _statuts(res):
    return {r["id"]: r["statut"] for r in res["referentiels"]}


def test_nouveaux_referentiels(apps):
    atelier, classe = apps
    rint = _interne(atelier)
    rext, seq, fid, tid = _externe(atelier)
    res = _importer(classe, _paquet(atelier, [rint, rext]))
    assert _statuts(res) == {rint: "nouveau", rext: "nouveau"}
    assert all(r["importe"] for r in res["referentiels"])
    d = classe.json_store.data_dir
    with classe.json_store._conn() as c:
        r = c.execute("SELECT * FROM referentiel_niveaux WHERE id=?", (rext,)).fetchone()
        assert (r["origine"], r["source"], r["annee"]) == ("publication", "externe", "2026-2027")
        # Durée de partie = somme des objectifs (1 + 2).
        p = c.execute("SELECT nb_seances_R_AE, libelle FROM referentiel_parties WHERE "
                      "referentiel_id=?", (rext,)).fetchone()
        assert (p["nb_seances_R_AE"], p["libelle"]) == (3, "Comparer")
        f = c.execute("SELECT * FROM referentiel_fichiers WHERE id=?", (fid,)).fetchone()
        assert (f["type_id"], f["seance_n"], f["retour"], f["delai_type"]) == \
            (tid, 2, "rendre", "semaines")
        assert (d / f["chemin"]).read_bytes() == b"%PDF activite"
        assert c.execute("SELECT libelle FROM types_documents WHERE id=?",
                         (tid,)).fetchone()["libelle"] == "Fiche d'activité"
        livret = c.execute("SELECT * FROM referentiel_docs_publies WHERE referentiel_id=?",
                           (rint,)).fetchone()
        assert livret["ref"] == "livret_sequence|N11/S01" and livret["seq_code"] == "S01"
        assert (d / livret["chemin"]).read_bytes() == b"%PDF-1.4 livret S01"
        o = c.execute("SELECT type_obj FROM referentiel_objectifs WHERE referentiel_id=? "
                      "AND code='01'", (rint,)).fetchone()
        assert o["type_obj"] == "connaissance"
        assert [x["id"] for x in imp.importes(c)] == [rint, rext]
        assert len(imp.journal(c)) == 2


def test_les_ecrans_de_classe_lisent_l_import(apps):
    atelier, classe = apps
    rint = _interne(atelier)
    rext, seq, fid, _ = _externe(atelier)
    _importer(classe, _paquet(atelier, [rint, rext]))
    from services import progression_doc as pgd
    from services.synthese_seance import candidats
    with classe.json_store._conn() as c:
        docs = pgd.documents_disponibles(c, "N11", "2026-2027", "S01")
        refs = {d["doc_ref"] for d in docs["sequence"]}
        assert "livret_sequence|N11/S01" in refs           # PDF compilé (interne)
        assert fid in refs                                 # fichier déposé (externe)
        cand = candidats(c, "N11", "S01", 1, 1)
        assert cand["notions"] == [{"id": "n1", "titre": "Distributivité"}]
        assert cand["methodes"][0]["titre"] == "Développer k(a+b)"
        assert rpe.lire(c, rext)["sequences"][0]["parties"][0]["objectifs"]
    parties = classe.json_store.lister_parties_referentiel(rint)
    assert [(p["seq_code"], p["partie_numero"], p["nb_seances_prevues"]) for p in parties][0] \
        == ("S01", 1, 3)
    r = classe.test_client().get("/api/referentiels?niveau=N11").get_json()
    assert rint in [x["id"] for x in r["referentiels"]]


def test_paquet_identique(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    contenu = _paquet(atelier, [rext])
    _importer(classe, contenu)
    res = _importer(classe, contenu)
    assert _statuts(res) == {rext: "identique"} and not res["referentiels"][0]["importe"]


def test_mise_a_jour_et_rapport(apps):
    atelier, classe = apps
    rext, seq, fid, _ = _externe(atelier)
    _importer(classe, _paquet(atelier, [rext]))
    with atelier.json_store._conn() as c:
        s2 = rpe.ajouter_sequence(c, rext, "Décimaux")
        rpe.ajouter_partie(c, rext, s2["code"], 0, AUJ)
        rpe.supprimer_fichier(c, fid, atelier.json_store.data_dir)
    with classe.json_store._conn() as c:
        ancien = c.execute("SELECT chemin FROM referentiel_fichiers WHERE id=?",
                           (fid,)).fetchone()["chemin"]
    res = _importer(classe, _paquet(atelier, [rext]))
    r = res["referentiels"][0]
    assert r["statut"] == "mise_a_jour" and r["importe"]
    assert any(f"Séquence {s2['code']} ajoutée" in x for x in r["changements"])
    assert any("1 retiré(s)" in x for x in r["changements"])
    assert not (classe.json_store.data_dir / ancien).exists()
    with classe.json_store._conn() as c:
        assert c.execute("SELECT COUNT(*) FROM referentiel_sequences WHERE referentiel_id=?",
                         (rext,)).fetchone()[0] == 2


def test_orphelins_signales_jamais_supprimes(apps):
    atelier, classe = apps
    rext, seq, fid, _ = _externe(atelier)
    _importer(classe, _paquet(atelier, [rext]))
    with classe.json_store._conn() as c:
        c.execute("INSERT INTO progression_doc (id, prog_kind, prog_ref, creneau_ref, "
                  "doc_source, doc_ref, doc_libelle) VALUES ('pd1', 'principale', 'pg', 'cr', "
                  "'externe', ?, 'Fiche activité')", (fid,))
    with atelier.json_store._conn() as c:
        rpe.supprimer_fichier(c, fid, atelier.json_store.data_dir)
    r = _importer(classe, _paquet(atelier, [rext]))["referentiels"][0]
    assert r["statut"] == "mise_a_jour" and r["orphelins"] == ["Fiche activité"]
    with classe.json_store._conn() as c:
        assert c.execute("SELECT 1 FROM progression_doc WHERE id='pd1'").fetchone()


def test_refus_sequence_commencee_retiree(apps):
    atelier, classe = apps
    rext, seq, *_ = _externe(atelier)
    with atelier.json_store._conn() as c:
        s2 = rpe.ajouter_sequence(c, rext, "Décimaux")
    _importer(classe, _paquet(atelier, [rext]))
    # La classe a commencé la séquence 2 (créneau daté dans le passé).
    with classe.json_store._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('et', 'C', 'propose')")
        c.execute("INSERT INTO progressions (id, niveau, annee, etablissement_id, "
                  "referentiel_id) VALUES ('pg', 'N11', '2026-2027', 'et', ?)", (rext,))
        c.execute("INSERT INTO creneaux (id, progression_id, seq_code, date_debut) "
                  "VALUES ('cr', 'pg', ?, '2026-09-07')", (s2["code"],))
    with atelier.json_store._conn() as c:
        rpe.supprimer_sequence(c, rext, s2["code"], AUJ, atelier.json_store.data_dir)
    res = _importer(classe, _paquet(atelier, [rext]), date(2026, 10, 1))
    r = res["referentiels"][0]
    assert r["statut"] == "refuse" and not r["importe"]
    assert any("a commencé" in x for x in r["raisons"])
    with classe.json_store._conn() as c:                 # rien n'a changé
        assert c.execute("SELECT 1 FROM referentiel_sequences WHERE referentiel_id=? AND "
                         "code=?", (rext, s2["code"])).fetchone()


def test_paquet_corrompu_rien_n_est_importe(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    contenu = _paquet(atelier, [rext])
    src, tampon = zipfile.ZipFile(io.BytesIO(contenu)), io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        for n in src.namelist():
            z.writestr(n, b"x" if n.startswith("fichiers/") else src.read(n))
    with pytest.raises(imp.ImportErreur) as e:
        _importer(classe, tampon.getvalue())
    assert any("Empreinte incorrecte" in x for x in e.value.erreurs)
    with classe.json_store._conn() as c:
        assert imp.importes(c) == []


def test_base_partagee_referentiel_local_protege(data_dir):
    app = create_app(data_dir, profil="complet")
    rext, seq, *_ = _externe(app)
    contenu = _paquet(app, [rext])
    assert _statuts(_importer(app, contenu)) == {rext: "identique"}
    with app.json_store._conn() as c:
        rpe.modifier(c, rext, "Modifié après publication")
    res = _importer(app, contenu)
    assert _statuts(res) == {rext: "refuse"}
    assert "base partagée" in res["referentiels"][0]["raisons"][0]
    with app.json_store._conn() as c:
        assert c.execute("SELECT description FROM referentiel_niveaux WHERE id=?",
                         (rext,)).fetchone()[0] == "Modifié après publication"


def test_routes(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    contenu = _paquet(atelier, [rext])
    c = classe.test_client()
    envoi = lambda: {"paquet": (io.BytesIO(contenu), "paquet.zip")}   # noqa: E731
    a = c.post("/api/import-publication/analyse", data=envoi(),
               content_type="multipart/form-data").get_json()
    assert a["referentiels"][0]["statut"] == "nouveau" and a["paquet"]["nb_fichiers"] == 2
    with classe.json_store._conn() as cx:                 # l'analyse n'importe rien
        assert imp.importes(cx) == []
    r = c.post("/api/import-publication/importer", data=envoi(),
               content_type="multipart/form-data").get_json()
    assert r["referentiels"][0]["importe"]
    e = c.get("/api/import-publication/etat").get_json()
    assert [x["id"] for x in e["importes"]] == [rext] and len(e["journal"]) == 1
    assert c.post("/api/import-publication/analyse", data={},
                  content_type="multipart/form-data").status_code == 400
    bad = c.post("/api/import-publication/analyse",
                 data={"paquet": (io.BytesIO(b"pas un zip"), "x.zip")},
                 content_type="multipart/form-data")
    assert bad.status_code == 422
    assert atelier.test_client().get("/api/import-publication/etat").status_code == 404
