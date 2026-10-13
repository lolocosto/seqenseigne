"""tests/test_v0_51_10_echanges_reglages.py — v0.51.10

Retours de l'auteur après le premier essai réel (atelier et appli en ligne
lancés sur la même base) : la relève explique le cas de la base partagée
(référentiels identiques, rien à importer) et l'état des échanges le signale ;
réglages dans Système › Préférences ; plus d'import manuel de retour d'usage
dans l'atelier (la boîte aux lettres suffit).
"""
from pathlib import Path

from app import create_app
from services import depot
from services import echanges as ech

from test_v0_51_1_format_referentiel import _externe
from test_v0_51_3_import_paquet import _paquet

RACINE = Path(__file__).resolve().parent.parent


def test_base_partagee_expliquee(data_dir):
    atelier = create_app(data_dir, profil="atelier")
    classe = create_app(data_dir, profil="classe")          # même base
    rext, *_ = _externe(atelier)
    contenu = _paquet(atelier, [rext])
    with classe.json_store._conn() as c:
        boite = depot.dossier_entrants(c, classe.json_store.data_dir)
        assert not ech.etat(c)["base_partagee"]
    boite.mkdir(parents=True, exist_ok=True)
    (boite / "p.zip").write_bytes(contenu)
    r = depot.relever(classe.json_store, "classe", appliquer=True)
    msg = r["traites"][0]["message"]
    assert "0 référentiel(s) importé(s), 1 identique(s) sur 1" in msg and "base partagée" in msg
    with classe.json_store._conn() as c:
        assert ech.etat(c)["base_partagee"]


def test_interface():
    html = (RACINE / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="pref-echanges"' in html and 'data-profils="atelier classe"' in html
    tdb = (RACINE / "static" / "tableau_bord.js").read_text(encoding="utf-8")
    assert "tdbUsageImporter" not in tdb and "aucun référentiel n\\'a été importé" in tdb
    js = (RACINE / "static" / "echanges.js").read_text(encoding="utf-8")
    assert "prefEchangesCharger" in js and "depot-reglages\">" not in js.split("prefEchangesCharger")[0]
