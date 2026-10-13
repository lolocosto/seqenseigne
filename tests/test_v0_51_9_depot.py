"""tests/test_v0_51_9_depot.py — v0.51.9

Boîte aux lettres : réglages (dossiers, mode, période), copie de chaque envoi
dans le dossier de sortie, relève en mode confirmation (rien d'appliqué) ou
automatique, traitement dans l'ordre des numéros (tampon : un envoi hors
séquence attend le manquant), doublons et refus rangés, retours d'usage
relevés par l'atelier, relève au démarrage (fil d'exécution), routes.
"""
import time

import pytest

from services import depot
from services import echanges as ech
from services import retour_usage as ru

from test_v0_51_1_format_referentiel import _externe
from test_v0_51_3_import_paquet import apps, _paquet  # noqa: F401


def _regler(app, **champs):
    with app.json_store._conn() as c:
        return depot.definir(c, app.json_store.data_dir, champs)


def _boite(app):
    with app.json_store._conn() as c:
        return depot.dossier_entrants(c, app.json_store.data_dir)


def _deposer(app, nom, contenu):
    d = _boite(app)
    d.mkdir(parents=True, exist_ok=True)
    (d / nom).write_bytes(contenu)


def _recus(app, type_="paquet"):
    with app.json_store._conn() as c:
        return sorted(r["numero"] for r in ech.recus(c, type_))


def test_reglages(apps, tmp_path):
    atelier, _ = apps
    with atelier.json_store._conn() as c:
        r = depot.reglages(c, atelier.json_store.data_dir)
    assert (r["mode"], r["periode_min"], r["sortants"]) == ("confirmation", 5, "")
    assert r["entrants_effectif"].endswith("entrants")
    r = _regler(atelier, entrants=str(tmp_path / "boite"), mode="automatique", periode_min=10)
    assert (r["entrants_effectif"], r["mode"], r["periode_min"]) == \
        (str(tmp_path / "boite"), "automatique", 10)
    for mauvais in ({"mode": "parfois"}, {"periode_min": 0}, {"periode_min": "x"},
                    {"sortants": "relatif/dossier"}):
        with pytest.raises(depot.DepotErreur):
            _regler(atelier, **mauvais)


def test_copie_dans_le_dossier_de_sortie(apps):
    atelier, classe = apps
    _regler(atelier, sortants=str(_boite(classe)))
    rext, *_ = _externe(atelier)
    _paquet(atelier, [rext])
    assert [p.name[:12] for p in _boite(classe).iterdir()] == ["paquet_0001_"]


def test_confirmation_puis_traitement_dans_l_ordre(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    p1, p2 = _paquet(atelier, [rext]), _paquet(atelier, [rext])
    _deposer(classe, "b.zip", p1)
    _deposer(classe, "a.zip", p2)                       # nom trié avant, n° 2
    r = depot.relever(classe.json_store, "classe")      # mode confirmation : liste seulement
    assert not r["applique"] and r["traites"] == []
    assert [(x["numero"], x["statut"]) for x in r["en_attente"]] == \
        [(1, "attendu"), (2, "manquants")]
    assert _recus(classe) == []
    r = depot.relever(classe.json_store, "classe", appliquer=True)
    assert [x["numero"] for x in r["traites"]] == [1, 2] and r["en_attente"] == []
    assert _recus(classe) == [1, 2]
    assert sorted(p.name for p in (_boite(classe) / "traites").iterdir()) == ["a.zip", "b.zip"]


def test_un_envoi_hors_sequence_attend_le_manquant(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    p1, p2, p3 = (_paquet(atelier, [rext]) for _ in range(3))
    _deposer(classe, "p1.zip", p1)
    _deposer(classe, "p3.zip", p3)
    r = depot.relever(classe.json_store, "classe", appliquer=True)
    assert [x["numero"] for x in r["traites"]] == [1]
    assert [(x["fichier"], x["manquants"]) for x in r["en_attente"]] == [("p3.zip", [2])]
    assert (_boite(classe) / "p3.zip").is_file()        # resté dans le dépôt
    _deposer(classe, "p2.zip", p2)
    r = depot.relever(classe.json_store, "classe", appliquer=True)
    assert [x["numero"] for x in r["traites"]] == [2, 3] and _recus(classe) == [1, 2, 3]


def test_doublons_et_refus(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    p1 = _paquet(atelier, [rext])
    _deposer(classe, "p1.zip", p1)
    depot.relever(classe.json_store, "classe", appliquer=True)
    _deposer(classe, "p1_bis.zip", p1)                  # doublon
    _deposer(classe, "notes.txt", b"bonjour")           # illisible
    _deposer(classe, "faux.zip", b"pas un zip")
    with classe.json_store._conn() as c:
        _, contenu, _ = ru.creer(c, classe.json_store.data_dir)
    _deposer(classe, "usage.json", contenu)             # pas pour l'appli en ligne
    r = depot.relever(classe.json_store, "classe", appliquer=True)
    assert [x["fichier"] for x in r["doublons"]] == ["p1_bis.zip"]
    assert sorted(x["fichier"] for x in r["refuses"]) == ["faux.zip", "notes.txt", "usage.json"]
    refuses = _boite(classe) / "refuses"
    assert (refuses / "usage.json.raison.txt").read_text(encoding="utf-8").startswith("Envoi « usage »")
    assert _recus(classe) == [1] and r["en_attente"] == []
    with classe.json_store._conn() as c:
        issues = [j["issue"] for j in depot.etat(classe.json_store, "classe")["journal"]]
    assert issues.count("refuse") == 3 and "doublon" in issues


def test_mode_automatique_et_retour_d_usage_releve_par_l_atelier(apps):
    atelier, classe = apps
    # Les deux applis sur le même PC : la sortie de l'une est l'entrée de l'autre.
    _regler(atelier, sortants=str(_boite(classe)), mode="automatique")
    _regler(classe, sortants=str(_boite(atelier)), mode="automatique")
    rext, *_ = _externe(atelier)
    _paquet(atelier, [rext])
    r = depot.relever(classe.json_store, "classe")      # automatique : appliqué
    assert [x["numero"] for x in r["traites"]] == [1]
    with classe.json_store._conn() as c:
        ru.creer(c, classe.json_store.data_dir)          # copié dans la boîte de l'atelier
    r = depot.relever(atelier.json_store, "atelier")
    assert r["traites"][0]["type"] == "usage" and "paquet(s) n° 1 acquitté(s)" in \
        r["traites"][0]["message"]
    with atelier.json_store._conn() as c:
        assert ech.envois(c, "paquet")[0]["acquitte_le"]
        assert ech.correspondant(c, "classe")


def test_releve_au_demarrage(apps):
    atelier, classe = apps
    _regler(classe, mode="automatique")
    rext, *_ = _externe(atelier)
    _deposer(classe, "p1.zip", _paquet(atelier, [rext]))
    t = depot.demarrer(classe)
    try:
        for _ in range(50):
            if _recus(classe) == [1]:
                break
            time.sleep(0.1)
        assert _recus(classe) == [1]
    finally:
        t.arret.set()
        t.join(2)


def test_routes(apps, tmp_path):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    _deposer(classe, "p1.zip", _paquet(atelier, [rext]))
    cc = classe.test_client()
    e = cc.get("/api/depot/etat").get_json()
    assert e["reglages"]["mode"] == "confirmation" and e["en_attente"][0]["statut"] == "attendu"
    r = cc.post("/api/depot/relever", json={"appliquer": False}).get_json()
    assert r["traites"] == [] and len(r["en_attente"]) == 1
    r = cc.post("/api/depot/relever", json={"appliquer": True}).get_json()
    assert [x["numero"] for x in r["traites"]] == [1]
    assert cc.put("/api/depot/reglages", json={"mode": "automatique"}).get_json()["mode"] == \
        "automatique"
    assert cc.put("/api/depot/reglages", json={"periode_min": 9999}).status_code == 400
    assert atelier.test_client().get("/api/depot/etat").status_code == 200
