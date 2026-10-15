"""tests/test_v0_51_16_api_boite.py — v0.51.16

Boîte aux lettres par API : l'atelier (client) appelle l'appli de classe avec
un jeton.

  - jeton : expiration obligatoire (défaut 1er août suivant), montré une seule
    fois, empreinte seule conservée, régénération = révocation, expiré refusé ;
  - accès : jeton exigé (même avec le mot de passe de l'appli), limitation
    des appels, portée limitée à la boîte aux lettres ;
  - échange complet : paquet déposé (mode confirmation : en attente ; mode
    automatique : importé), envoi immédiat à la création, retours d'usage
    produits automatiquement et rapatriés, accusés dans les deux sens ;
  - appli de classe injoignable : erreur notée, envois gardés, reprise ;
  - adresse : HTTPS obligatoire hors localhost.
Données fictives.
"""
import json
from datetime import date

import pytest

from services import api_boite as ab
from services import api_client as ac
from services import depot
from services import echanges as ech

from test_v0_51_1_format_referentiel import _externe
from test_v0_51_3_import_paquet import apps  # noqa: F401
from test_v0_51_8_retour_usage import _planifier


@pytest.fixture(autouse=True)
def _limites():
    ab.remettre_a_zero()
    yield
    ab.remettre_a_zero()


@pytest.fixture
def relie(apps, monkeypatch):
    """Atelier et classe reliés : jeton généré côté classe, enregistré côté
    atelier ; les appels HTTP de l'atelier passent par le client de test de
    la classe."""
    atelier, classe = apps
    cl = classe.test_client()
    etat = {"joignable": True}

    def appel(d, methode, chemin, corps=None, entetes=None, delai=10):
        if not etat["joignable"]:
            raise ac.ClientErreur("Appli de classe injoignable (connexion refusée).")
        h = {"Authorization": f"Bearer {d['jeton']}", **(entetes or {})}
        r = cl.open("/api/boite/v1" + chemin, method=methode, data=corps, headers=h)
        if r.status_code >= 400:
            msg = (r.get_json(silent=True) or {}).get("error", "")
            raise ac.ClientErreur(msg or f"HTTP {r.status_code}",
                                  "jeton" if r.status_code == 401 else "refuse")
        return r.data, dict(r.headers)

    monkeypatch.setattr(ac, "_appel", appel)
    r = cl.post("/api/jeton", json={"expire_le": "2028-08-01"})
    jeton = r.get_json()["jeton"]
    at = atelier.test_client()
    assert at.put("/api/api-client/destination",
                  json={"url": "http://localhost:5001", "jeton": jeton}).status_code == 200
    return {"atelier": atelier, "classe": classe, "cl": cl, "at": at, "jeton": jeton,
            "etat": etat}


def _mode(app, mode):
    with app.json_store._conn() as c:
        depot.definir(c, app.json_store.data_dir, {"mode": mode})


def _publier(r, rids):
    resp = r["at"].post("/api/publication/paquet", json={"referentiels": rids})
    assert resp.status_code == 200, resp.get_json()
    return json.loads(resp.headers["X-Paquet-Envoi"])


# ── Jeton ────────────────────────────────────────────────────────────────────

def test_expiration_par_defaut():
    assert ab.expiration_par_defaut(date(2026, 10, 15)) == "2027-08-01"
    assert ab.expiration_par_defaut(date(2027, 3, 1)) == "2027-08-01"
    assert ab.expiration_par_defaut(date(2027, 8, 1)) == "2028-08-01"


def test_jeton_montre_une_fois_et_empreinte_seule(apps):
    _, classe = apps
    cl = classe.test_client()
    assert cl.post("/api/jeton", json={}).status_code == 400            # date obligatoire
    assert cl.post("/api/jeton", json={"expire_le": "2020-01-01"}).status_code == 400
    j = cl.post("/api/jeton", json={"expire_le": "2027-08-01"}).get_json()
    assert j["jeton"].startswith(ab.PREFIXE) and j["actif"] and j["expire_le"] == "2027-08-01"
    e = cl.get("/api/jeton").get_json()
    assert "jeton" not in e and e["actif"]
    with classe.json_store._conn() as c:
        stocke = [r[0] for r in c.execute("SELECT empreinte FROM api_jetons")]
    assert j["jeton"] not in stocke and len(stocke[0]) == 64


def test_regeneration_revoque_et_expiration(apps):
    _, classe = apps
    cl = classe.test_client()
    j1 = cl.post("/api/jeton", json={"expire_le": "2028-08-01"}).get_json()["jeton"]
    assert cl.get("/api/boite/v1/etat", headers={"Authorization": f"Bearer {j1}"}).status_code == 200
    j2 = cl.post("/api/jeton", json={"expire_le": "2028-08-01"}).get_json()["jeton"]
    assert cl.get("/api/boite/v1/etat", headers={"Authorization": f"Bearer {j1}"}).status_code == 401
    assert cl.get("/api/boite/v1/etat", headers={"Authorization": f"Bearer {j2}"}).status_code == 200
    with classe.json_store._conn() as c:
        with pytest.raises(ab.ApiErreur, match="expiré"):
            ab.verifier(c, j2, aujourd_hui=date(2028, 8, 1))
        assert ab.etat_jeton(c, date(2028, 7, 20))["expire_bientot"]
    cl.delete("/api/jeton")
    assert cl.get("/api/boite/v1/etat", headers={"Authorization": f"Bearer {j2}"}).status_code == 401


def test_jeton_exige_et_portee(apps, monkeypatch):
    monkeypatch.setenv("SEQ_MDP", "secret")             # appli protégée par mot de passe
    from app import create_app
    classe = create_app(apps[1].json_store.data_dir, profil="classe")
    cl = classe.test_client()
    assert cl.get("/api/classes").status_code == 401                    # session exigée
    assert cl.get("/api/boite/v1/etat").status_code == 401              # jeton exigé
    with classe.json_store._conn() as c:
        j = ab.generer(c, "2028-08-01")["jeton"]
    h = {"Authorization": f"Bearer {j}"}
    assert cl.get("/api/boite/v1/etat", headers=h).status_code == 200   # sans session
    assert cl.get("/api/classes", headers=h).status_code == 401         # portée limitée


def test_limitation_des_appels(apps):
    _, classe = apps
    cl = classe.test_client()
    for _ in range(ab.ECHECS_MAX):
        assert cl.get("/api/boite/v1/etat", headers={"Authorization": "Bearer faux"}).status_code == 401
    assert cl.get("/api/boite/v1/etat", headers={"Authorization": "Bearer faux"}).status_code == 429
    assert ab.limiter("autre", maintenant=0.0)
    for k in range(ab.APPELS_PAR_MINUTE - 1):
        ab.limiter("autre", maintenant=1.0)
    assert not ab.limiter("autre", maintenant=2.0)
    assert ab.limiter("autre", maintenant=70.0)


# ── Échange complet ──────────────────────────────────────────────────────────

def test_envoi_immediat_mode_confirmation(relie):
    r = relie
    rext, *_ = _externe(r["atelier"])
    envoi = _publier(r, [rext])
    assert envoi == {"configuree": True, "ok": True, "livre": True, "erreur": ""}
    with r["classe"].json_store._conn() as c:                 # en attente de « Traiter »
        att = depot.lister(c, r["classe"].json_store.data_dir, "classe")
        assert [(x["type"], x["statut"]) for x in att] == [("paquet", "attendu")]
        assert c.execute("SELECT COUNT(*) FROM referentiel_niveaux WHERE id=?",
                         (rext,)).fetchone()[0] == 0
    with r["atelier"].json_store._conn() as c:
        assert ech.envois(c, "paquet")[0]["livre_le"]
    # Une seconde synchronisation ne renvoie pas le paquet livré.
    assert ac.synchroniser(r["atelier"].json_store)["livres"] == []


def test_echange_automatique_complet(relie):
    r = relie
    _mode(r["classe"], "automatique")
    _mode(r["atelier"], "automatique")
    rext, seq, *_ = _externe(r["atelier"])
    assert _publier(r, [rext])["livre"]
    with r["classe"].json_store._conn() as c:                 # importé aussitôt
        assert c.execute("SELECT origine FROM referentiel_niveaux WHERE id=?",
                         (rext,)).fetchone()[0] == "publication"
    _planifier(r["classe"], rext, {seq: "2026-09-07"})
    s = ac.synchroniser(r["atelier"].json_store)              # retour d'usage produit et rapatrié
    assert s["ok"] and len(s["recus"]) == 1 and s["releve"]["traites"]
    with r["atelier"].json_store._conn() as c:
        from services import referentiel_principal_externe as rpe
        assert rpe.est_utilise(c, rext)
        assert ech.envois(c, "paquet")[0]["acquitte_le"]       # le retour accuse le paquet
    # Usage inchangé : pas de nouveau retour.
    assert ac.synchroniser(r["atelier"].json_store)["recus"] == []
    # Paquet suivant : il accuse le retour n° 1, qui est retiré de l'archive côté classe.
    _publier(r, [rext])
    with r["classe"].json_store._conn() as c:
        assert ech.envois(c, "usage")[0]["acquitte_le"]


def test_classe_injoignable_puis_reprise(relie):
    r = relie
    rext, *_ = _externe(r["atelier"])
    r["etat"]["joignable"] = False
    envoi = _publier(r, [rext])
    assert envoi["ok"] is False and not envoi["livre"] and "injoignable" in envoi["erreur"]
    e = r["at"].get("/api/api-client/etat").get_json()
    assert e["injoignable"] and e["erreur_depuis"] and "jeton" not in e
    r["etat"]["joignable"] = True
    s = r["at"].post("/api/api-client/synchroniser").get_json()
    assert s["ok"] and s["livres"] == [1] and not s["etat"]["injoignable"]
    assert s["etat"]["expire_le"] == "2028-08-01"


def test_jeton_refuse_cote_atelier(relie):
    r = relie
    r["cl"].delete("/api/jeton")
    t = r["at"].post("/api/api-client/tester").get_json()
    assert not t["ok"] and "refusé" in t["message"]


def test_non_configuree_rien_ne_change(apps):
    atelier, _ = apps
    rext, *_ = _externe(atelier)
    resp = atelier.test_client().post("/api/publication/paquet", json={"referentiels": [rext]})
    assert json.loads(resp.headers["X-Paquet-Envoi"])["configuree"] is False
    assert ac.synchroniser(atelier.json_store) == {"configuree": False, "ok": False, "livres": [],
                                                   "recus": [], "erreur": "", "releve": None}


def test_retour_usage_cree_a_la_main_pas_de_doublon(relie):
    r = relie
    _mode(r["classe"], "automatique")
    rext, *_ = _externe(r["atelier"])
    _publier(r, [rext])
    resp = r["cl"].post("/api/retour-usage/creer")
    assert resp.headers["X-Usage-Api"] == "1"
    s = ac.synchroniser(r["atelier"].json_store)
    assert len(s["recus"]) == 1                              # celui créé à la main seulement


def test_paquet_invalide_refuse(relie):
    r = relie
    h = {"Authorization": f"Bearer {r['jeton']}", "Content-Type": "application/zip"}
    resp = r["cl"].post("/api/boite/v1/paquets", data=b"pas un zip", headers=h)
    assert resp.status_code == 400


def test_adresse_https_hors_localhost():
    assert ac.valider_url("http://localhost:5001/") == "http://localhost:5001"
    assert ac.valider_url("https://classe.exemple.fr") == "https://classe.exemple.fr"
    with pytest.raises(ac.ClientErreur, match="HTTPS"):
        ac.valider_url("http://classe.exemple.fr")
    with pytest.raises(ac.ClientErreur):
        ac.valider_url("ftp://x")


def test_routes_par_profil(apps):
    atelier, classe = apps
    assert atelier.test_client().get("/api/jeton").status_code == 404
    assert atelier.test_client().get("/api/boite/v1/etat").status_code == 404
    assert classe.test_client().get("/api/api-client/etat").status_code == 404


def test_vrai_http_local(apps):
    """Bout en bout par HTTP (serveur local de l'appli de classe)."""
    import threading
    from werkzeug.serving import make_server
    atelier, classe = apps
    serveur = make_server("127.0.0.1", 0, classe, threaded=True)
    t = threading.Thread(target=serveur.serve_forever, daemon=True)
    t.start()
    try:
        cl = classe.test_client()
        jeton = cl.post("/api/jeton", json={"expire_le": "2028-08-01"}).get_json()["jeton"]
        at = atelier.test_client()
        at.put("/api/api-client/destination",
               json={"url": f"http://127.0.0.1:{serveur.server_port}", "jeton": jeton})
        assert at.post("/api/api-client/tester").get_json()["ok"]
        rext, *_ = _externe(atelier)
        envoi = json.loads(at.post("/api/publication/paquet", json={"referentiels": [rext]})
                           .headers["X-Paquet-Envoi"])
        assert envoi["livre"]
        at.put("/api/api-client/destination", json={"jeton": "seqj_faux"})
        t2 = at.post("/api/api-client/tester").get_json()
        assert not t2["ok"] and "refusé" in t2["message"]
    finally:
        serveur.shutdown()
