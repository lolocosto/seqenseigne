"""tests/test_v0_51_2_paquet.py — v0.51.2

Paquet de publication : zip (paquet.json + referentiels/<id>.json +
fichiers/<sha256>.<ext>), référentiels publiables, rapport (documents sans
PDF, écarts de durée), contrôles d'intégrité, journal, routes.
"""
import io
import json
import zipfile

import pytest

from services import format_referentiel as fmt
from services import paquet_publication as pqt
from services import referentiel_principal_externe as rpe

from test_v0_51_1_format_referentiel import AUJ, _externe, _interne


def _creer(app, rids):
    with app.json_store._conn() as c:
        return pqt.creer(c, app.json_store.data_dir, rids)


def _zip(contenu):
    return zipfile.ZipFile(io.BytesIO(contenu))


def test_publiables(app):
    rint = _interne(app)
    rext, *_ = _externe(app)
    with app.json_store._conn() as c:
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
                  "VALUES ('2026_N11', 'N11', '2026', 'en_cours')")
        liste = pqt.lister_publiables(c, app.json_store.data_dir)
    ids = [r["id"] for r in liste]
    assert rint in ids and rext in ids and "2026_N11" not in ids   # interne en cours
    r = next(x for x in liste if x["id"] == rext)
    assert r["valide"] and r["derniere_publication"] is None and not r["modifie_depuis"]
    # La liste ne fige rien.
    assert not (app.json_store.data_dir / "referentiels" / rint / "_publication").exists()


def test_paquet_contenu_et_manifeste(app):
    rint = _interne(app)
    rext, seq, fid, tid = _externe(app)
    contenu, m = _creer(app, [rint, rext])
    assert m["format"] == "seqenseigne.paquet" and m["format_version"] == "1.0"
    assert m["nom"].startswith("paquet_") and m["nom"].endswith(".zip")
    assert [r["id"] for r in m["referentiels"]] == [rint, rext]
    z = _zip(contenu)
    noms = set(z.namelist())
    assert {"paquet.json", f"referentiels/{rint}.json", f"referentiels/{rext}.json"} <= noms
    # 1 livret compilé (interne) + 2 fichiers déposés (externe).
    assert len(m["fichiers"]) == 3
    for f in m["fichiers"]:
        assert f["chemin"] == f"fichiers/{f['sha256']}.pdf" and f["chemin"] in noms
    doc = json.loads(z.read(f"referentiels/{rext}.json"))
    assert fmt.valider(doc) == [] and "publication_figee" not in doc
    # Publier fige l'interne verrouillé.
    assert (app.json_store.data_dir / "referentiels" / rint / "_publication"
            / "referentiel.json").is_file()
    assert pqt.verifier(contenu)[1] == []


def test_rapport_documents_sans_pdf_et_ecarts(app):
    rint = _interne(app)
    rext, seq, *_ = _externe(app)
    with app.json_store._conn() as c:
        c.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document) "
                  "VALUES ('rd2', ?, 'livret_cours')", (rint,))
        rpe.modifier_partie(c, rext, seq, 1, 5, AUJ)        # saisie 5, objectifs 3
    _, m = _creer(app, [rint, rext])
    r = m["rapport"]
    assert any("Livret de cours" in x for x in r["documents_sans_pdf"])
    assert any("5 saisie(s) sur la partie, 3 d'après les objectifs" in x
               for x in r["parties_ecart"])
    assert r["erreurs"] == [] and r["taille_totale"] > 0


def test_fichier_identique_stocke_une_fois(app):
    rext, seq, *_ = _externe(app)
    with app.json_store._conn() as c:
        rpe.ajouter_fichier(c, rext, seq, 1, nom_fichier="copie.pdf",
                            contenu=b"%PDF activite", mime="application/pdf",
                            data_dir=app.json_store.data_dir)
    contenu, m = _creer(app, [rext])
    assert len(m["fichiers"]) == 2                          # activite = copie
    doc = json.loads(_zip(contenu).read(f"referentiels/{rext}.json"))
    assert len(doc["sequences"][0]["parties"][0]["documents"]) == 2


def test_journal_et_modifie_depuis(app):
    rext, *_ = _externe(app)
    _creer(app, [rext])
    with app.json_store._conn() as c:
        j = pqt.journal(c)
        r = next(x for x in pqt.lister_publiables(c, app.json_store.data_dir)
                 if x["id"] == rext)
        assert len(j) == 1 and j[0]["referentiels"][0]["id"] == rext
        assert r["derniere_publication"] and not r["modifie_depuis"]
        rpe.modifier(c, rext, "Autre description")
        r = next(x for x in pqt.lister_publiables(c, app.json_store.data_dir)
                 if x["id"] == rext)
    assert r["modifie_depuis"]


def test_refus_non_publiable_et_fichiers(app):
    rint = _interne(app)
    rext, seq, fid, _ = _externe(app)
    with app.json_store._conn() as c:
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
                  "VALUES ('2026_N11', 'N11', '2026', 'en_cours')")
    with pytest.raises(pqt.PaquetErreur) as e:
        _creer(app, ["2026_N11"])
    assert "non publiable" in e.value.rapport["erreurs"][0]
    with pytest.raises(pqt.PaquetErreur):
        _creer(app, [])
    # Fichier déposé disparu du disque.
    with app.json_store._conn() as c:
        chemin = c.execute("SELECT chemin FROM referentiel_fichiers WHERE id=?",
                           (fid,)).fetchone()["chemin"]
    (app.json_store.data_dir / chemin).unlink()
    with pytest.raises(pqt.PaquetErreur) as e:
        _creer(app, [rext])
    assert any("introuvable" in x for x in e.value.rapport["erreurs"])
    # PDF figé modifié après la publication figée de l'interne.
    _creer(app, [rint])
    pdf = (app.json_store.data_dir / "referentiels" / rint / "_verrouille" / "pdfs"
           / "livret_sequence__N11__S01.pdf")
    pdf.write_bytes(b"%PDF modifie")
    with pytest.raises(pqt.PaquetErreur) as e:
        _creer(app, [rint])
    assert any("modifié depuis la publication" in x for x in e.value.rapport["erreurs"])


def test_verifier_detecte_une_alteration(app):
    rext, *_ = _externe(app)
    contenu, m = _creer(app, [rext])
    src, tampon = _zip(contenu), io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        for n in src.namelist():
            data = src.read(n)
            if n.startswith("fichiers/"):
                data = b"altere"
            z.writestr(n, data)
    erreurs = pqt.verifier(tampon.getvalue())[1]
    assert any("Empreinte incorrecte" in e for e in erreurs)
    assert pqt.verifier(b"pas un zip")[1]


# ── Routes ───────────────────────────────────────────────────────────────────

def test_routes(app, client):
    rext, *_ = _externe(app)
    d = client.get("/api/publication/publiables").get_json()
    assert [r["id"] for r in d["referentiels"]] == [rext] and d["journal"] == []
    r = client.post("/api/publication/paquet", json={"referentiels": [rext]})
    assert r.status_code == 200 and r.mimetype == "application/zip"
    assert "attachment" in r.headers["Content-Disposition"]
    resume = json.loads(r.headers["X-Paquet-Resume"])
    assert resume["nb_referentiels"] == 1 and resume["nb_fichiers"] == 2
    assert pqt.verifier(r.data)[1] == []
    r = client.post("/api/publication/paquet", json={"referentiels": ["inconnu"]})
    assert r.status_code == 422 and r.get_json()["rapport"]["erreurs"]
    assert len(client.get("/api/publication/journal").get_json()["journal"]) == 1


def test_routes_absentes_du_profil_classe(data_dir):
    from app import create_app
    c = create_app(data_dir, profil="classe").test_client()
    assert c.get("/api/publication/publiables").status_code == 404
    assert c.post("/api/publication/paquet", json={}).status_code == 404
