"""tests/test_v0_51_7_echanges.py — v0.51.7

Protocole d'échange atelier ↔ classe appliqué aux paquets : identité des
instances, en-tête (émetteur, destinataire, numéro, accusé), archive et
renvoi, réception dans l'ordre (déjà reçu, manquants), lien au premier
échange, refus d'une autre instance, paquet sans en-tête (antérieur),
acquittement, base partagée, routes.
"""
import io
import json
import shutil
import zipfile

import pytest

from app import create_app
from services import echanges as ech
from services import import_publication as imp
from services import paquet_publication as pqt

from test_v0_51_1_format_referentiel import _externe
from test_v0_51_3_import_paquet import apps, _importer, _paquet  # noqa: F401


def _manifeste(contenu: bytes) -> dict:
    return json.loads(zipfile.ZipFile(io.BytesIO(contenu)).read("paquet.json"))


def _sans_entete(contenu: bytes) -> bytes:
    """Paquet tel qu'avant la v0.51.7 (manifeste sans « echange »)."""
    src, tampon = zipfile.ZipFile(io.BytesIO(contenu)), io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        for n in src.namelist():
            if n == "paquet.json":
                m = json.loads(src.read(n))
                m.pop("echange")
                z.writestr(n, json.dumps(m))
            else:
                z.writestr(n, src.read(n))
    return tampon.getvalue()


def test_identite_et_entete(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    with atelier.json_store._conn() as c:
        moi = ech.instance(c)
        assert moi["id"].startswith("inst_") and ech.instance(c)["id"] == moi["id"]
        assert ech.renommer(c, "Atelier — maison")["nom"] == "Atelier — maison"
        with pytest.raises(ech.EchangeErreur):
            ech.renommer(c, " ")
    with classe.json_store._conn() as c:
        assert ech.instance(c)["id"] != moi["id"]
    contenu = _paquet(atelier, [rext])
    e = _manifeste(contenu)["echange"]
    assert e == {"type": "paquet", "numero": 1, "destinataire": None, "accuse": None,
                 "emetteur": {"id": moi["id"], "nom": "Atelier — maison", "role": "atelier"}}
    assert _manifeste(contenu)["nom"].startswith("paquet_0001_")
    with atelier.json_store._conn() as c:
        assert pqt.journal(c)[0]["numero"] == 1
        nom, archive = ech.lire_archive(c, atelier.json_store.data_dir, "paquet", 1)
        assert archive == contenu and nom.startswith("paquet_0001_")
        assert _manifeste(_paquet(atelier, [rext]))["echange"]["numero"] == 2


def test_reception_dans_l_ordre(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    p1, p2, p3 = (_paquet(atelier, [rext]) for _ in range(3))
    _importer(classe, p1)
    with classe.json_store._conn() as c:
        lie = ech.correspondant(c, "atelier")
        with atelier.json_store._conn() as ca:
            assert lie["id"] == ech.instance(ca)["id"]
        a = imp.analyser(c, classe.json_store.data_dir, p3)
        assert a["echange"]["statut"] == "manquants" and a["echange"]["manquants"] == [2]
        assert imp.analyser(c, classe.json_store.data_dir, p1)["echange"]["statut"] == "deja_recu"
    with pytest.raises(imp.ImportErreur) as e:
        _importer(classe, p3)
    assert e.value.code == "sequence" and "le n° 2" in str(e.value)
    _importer(classe, p2)
    _importer(classe, p3)
    with classe.json_store._conn() as c:
        assert ech.etat(c)["attendu"]["paquet"] == 4
        assert [r["numero"] for r in ech.recus(c, "paquet")] == [3, 2, 1]


def test_autre_atelier_et_destinataire(apps, tmp_path, data_dir):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    _importer(classe, _paquet(atelier, [rext]))
    d2 = tmp_path / "autre_atelier"
    shutil.copytree(data_dir, d2, ignore=shutil.ignore_patterns("*.db"))
    autre = create_app(d2, profil="atelier")
    r2, *_ = _externe(autre)
    with pytest.raises(imp.ImportErreur, match="liée à"):
        _importer(classe, _paquet(autre, [r2]))
    # Destinataire inconnu de la classe : refusé.
    with atelier.json_store._conn() as c:
        ech._lier(c, "classe", {"id": "inst_quelqu_un_d_autre", "nom": "X"})
    with pytest.raises(imp.ImportErreur, match="autre instance"):
        _importer(classe, _paquet(atelier, [rext]))


def test_paquet_sans_entete(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    p1 = _paquet(atelier, [rext])
    ancien = _sans_entete(_paquet(atelier, [rext]))
    res = _importer(classe, ancien)                  # accepté : séquence pas commencée
    assert res["echange"]["statut"] == "sans_numero"
    _importer(classe, p1)                            # la séquence numérotée commence
    with pytest.raises(imp.ImportErreur, match="sans numéro"):
        _importer(classe, ancien)


def test_premier_numero_attendu_apres_un_ancien(apps):
    """Le n° 1 est attendu même après un paquet sans en-tête."""
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    p1 = _paquet(atelier, [rext])
    _importer(classe, _sans_entete(_paquet(atelier, [rext])))
    assert _importer(classe, p1)["echange"]["statut"] == "attendu"


def test_acquittement(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    for _ in range(3):
        _paquet(atelier, [rext])
    dd = atelier.json_store.data_dir
    with atelier.json_store._conn() as c:
        assert ech.acquitter(c, dd, "paquet", 2) == [1, 2]
        with pytest.raises(ech.EchangeErreur, match="acquitté"):
            ech.lire_archive(c, dd, "paquet", 1)
        assert ech.lire_archive(c, dd, "paquet", 3)[1]
        assert not list((dd / "echanges" / "envoyes").glob("paquet_0001_*"))
        assert ech.acquitter(c, dd, "paquet", None) == []


def test_base_partagee(data_dir):
    app = create_app(data_dir, profil="complet")
    rext, *_ = _externe(app)
    res = _importer(app, _paquet(app, [rext]))
    assert res["echange"]["statut"] == "meme_base"
    with app.json_store._conn() as c:
        assert ech.correspondant(c, "atelier") is None


def test_routes(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    contenu = _paquet(atelier, [rext])
    ca = atelier.test_client()
    e = ca.get("/api/echanges/etat").get_json()
    assert e["prochain"]["paquet"] == 2 and e["envois"]["paquet"][0]["numero"] == 1
    assert ca.put("/api/echanges/instance", json={"nom": "Maison"}).get_json()["nom"] == "Maison"
    r = ca.get("/api/echanges/envois/paquet/1")
    assert r.status_code == 200 and r.data == contenu
    assert ca.get("/api/echanges/envois/paquet/9").status_code == 404
    cc = classe.test_client()
    envoi = lambda c: {"paquet": (io.BytesIO(c), "p.zip")}   # noqa: E731
    assert cc.post("/api/import-publication/importer", data=envoi(contenu),
                   content_type="multipart/form-data").status_code == 200
    r = cc.post("/api/import-publication/importer", data=envoi(contenu),
                content_type="multipart/form-data")
    assert r.status_code == 409 and "déjà reçu" in r.get_json()["error"]
    e = cc.get("/api/echanges/etat").get_json()
    # Nom de l'atelier tel que porté par le paquet (créé avant le renommage).
    assert e["correspondants"]["atelier"]["nom"] == _manifeste(contenu)["echange"]["emetteur"]["nom"]
    assert e["attendu"]["paquet"] == 2
    assert cc.delete("/api/echanges/correspondants/atelier").status_code == 200
    assert cc.get("/api/echanges/etat").get_json()["correspondants"]["atelier"] is None
    assert cc.delete("/api/echanges/correspondants/x").status_code == 400
