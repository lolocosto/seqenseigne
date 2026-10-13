"""tests/test_v0_51_8_retour_usage.py — v0.51.8

Retour d'usage (appli en ligne → appli locale) sur le protocole d'échange :
contenu (sans donnée d'élève), import dans l'atelier (verrous des séquences
commencées et état « utilisé », jamais perdus), séquence stricte,
acquittements dans les deux sens, états de synchronisation, interne
verrouillé devenu « utilisé », routes et profils.
"""
import json
from datetime import date

import pytest

from services import echanges as ech
from services import import_publication as imp
from services import referentiel_principal_externe as rpe
from services import retour_usage as ru

from test_v0_51_1_format_referentiel import _externe, _interne
from test_v0_51_3_import_paquet import apps, _importer, _paquet  # noqa: F401

AUJ = date(2026, 10, 1)


def _planifier(classe, rid, seqs):
    """Progression de la classe sur `rid` : un créneau daté par séquence."""
    with classe.json_store._conn() as c:
        if not c.execute("SELECT 1 FROM etablissements WHERE id='et'").fetchone():
            c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('et', 'C', 'propose')")
        c.execute("INSERT OR IGNORE INTO progressions (id, niveau, annee, etablissement_id, "
                  "referentiel_id) VALUES ('pg', 'N11', '2026-2027', 'et', ?)", (rid,))
        for k, (code, debut) in enumerate(seqs.items()):
            c.execute("INSERT INTO creneaux (id, progression_id, seq_code, date_debut) VALUES "
                      "(?, 'pg', ?, ?)", (f"cr{k}_{code}", code, debut))


def _retour(classe) -> bytes:
    with classe.json_store._conn() as c:
        return ru.creer(c, classe.json_store.data_dir)[1]


def _importer_retour(atelier, contenu):
    with atelier.json_store._conn() as c:
        return ru.importer(c, atelier.json_store.data_dir, contenu)


def _seq2(atelier, rext):
    with atelier.json_store._conn() as c:
        return rpe.ajouter_sequence(c, rext, "Décimaux")["code"]


def test_contenu_du_retour(apps):
    atelier, classe = apps
    rext, seq, *_ = _externe(atelier)
    s2 = _seq2(atelier, rext)
    _importer(classe, _paquet(atelier, [rext]))
    _planifier(classe, rext, {seq: "2026-09-07", s2: "2026-11-02"})
    with classe.json_store._conn() as c:
        c.execute("INSERT INTO progression_mer_partie (id, progression_mer_id, partie_id, "
                  "partie_source) VALUES ('pp', 'pm', ?, 'fige')", (f"{rext}|{s2}|1",))
        doc = ru.construire(c)
    assert doc["format"] == "seqenseigne.usage" and doc["echange"]["numero"] == 1
    assert doc["echange"]["accuse"] == 1 and doc["echange"]["emetteur"]["role"] == "classe"
    r = doc["referentiels"][0]
    assert set(r) == {"id", "nom", "empreinte", "utilise", "utilise_depuis", "sequences",
                      "parties_mer"}
    assert (r["id"], r["utilise"], r["utilise_depuis"]) == (rext, True, "2026-09-07")
    assert r["sequences"] == [{"code": seq, "debut": "2026-09-07"},
                              {"code": s2, "debut": "2026-11-02"}]
    assert r["parties_mer"] == [f"{s2}|1"]
    with classe.json_store._conn() as c:
        assert r["empreinte"] == imp.importes(c)[0]["empreinte"]
    texte = json.dumps(doc)
    assert "eleve" not in texte and "etablissement" not in texte and "classe_id" not in texte


def test_import_dans_l_atelier_et_verrous(apps):
    atelier, classe = apps
    rext, seq, *_ = _externe(atelier)
    s2 = _seq2(atelier, rext)
    _importer(classe, _paquet(atelier, [rext]))
    _planifier(classe, rext, {seq: "2026-09-07", s2: "2026-11-02"})
    with atelier.json_store._conn() as c:
        assert not rpe.sequence_commencee(c, rext, seq, AUJ)
    res = _importer_retour(atelier, _retour(classe))
    assert res["paquets_acquittes"] == [1] and res["inconnus"] == []
    assert res["referentiels"][0]["nouvelles_sequences"] == [seq, s2]
    with atelier.json_store._conn() as c:
        assert rpe.est_utilise(c, rext)
        assert rpe.sequence_commencee(c, rext, seq, AUJ)               # 07/09 passé
        assert not rpe.sequence_commencee(c, rext, s2, AUJ)            # 02/11 à venir
        assert rpe.sequence_commencee(c, rext, s2, date(2026, 11, 2))  # le jour venu
        with pytest.raises(rpe.RefExtErreur, match="a commencé"):
            rpe.supprimer_sequence(c, rext, seq, AUJ, atelier.json_store.data_dir)
        # Lien à l'appli en ligne ; le prochain paquet lui est destiné et accuse le retour 1.
        with classe.json_store._conn() as cc:
            assert ech.correspondant(c, "classe")["id"] == ech.instance(cc)["id"]
        e = ech.entete(c, "paquet")
        assert e["destinataire"] == ech.correspondant(c, "classe")["id"] and e["accuse"] == 1
        assert ech.envois(c, "paquet")[0]["acquitte_le"]


def test_verrous_jamais_perdus(apps):
    atelier, classe = apps
    rext, seq, *_ = _externe(atelier)
    _importer(classe, _paquet(atelier, [rext]))
    _planifier(classe, rext, {seq: "2026-09-07"})
    _importer_retour(atelier, _retour(classe))
    with classe.json_store._conn() as c:                 # créneau retiré côté classe
        c.execute("DELETE FROM creneaux")
        c.execute("DELETE FROM progressions")
    _importer_retour(atelier, _retour(classe))
    with atelier.json_store._conn() as c:
        assert rpe.sequence_commencee(c, rext, seq, AUJ) and rpe.est_utilise(c, rext)


def test_sequence_stricte_des_retours(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    _importer(classe, _paquet(atelier, [rext]))
    r1, r2 = _retour(classe), _retour(classe)
    with pytest.raises(ru.UsageErreur) as e:
        _importer_retour(atelier, r2)
    assert e.value.code == "sequence" and "le n° 1" in str(e.value)
    with atelier.json_store._conn() as c:
        assert ru.analyser(c, r2)["echange"]["manquants"] == [1]
    _importer_retour(atelier, r1)
    with pytest.raises(ru.UsageErreur, match="déjà reçu"):
        _importer_retour(atelier, r1)
    _importer_retour(atelier, r2)
    with pytest.raises(ru.UsageErreur):
        _importer_retour(atelier, b"pas du json")


def test_le_paquet_acquitte_les_retours(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    _importer(classe, _paquet(atelier, [rext]))
    _importer_retour(atelier, _retour(classe))
    res = _importer(classe, _paquet(atelier, [rext]))     # accusé : retour n° 1
    assert res["usages_acquittes"] == [1]
    with classe.json_store._conn() as c:
        assert ech.envois(c, "usage")[0]["acquitte_le"]
        with pytest.raises(ech.EchangeErreur):
            ech.lire_archive(c, classe.json_store.data_dir, "usage", 1)


def test_etats_de_synchronisation(apps):
    atelier, classe = apps
    rext, seq, *_ = _externe(atelier)
    dd = atelier.json_store.data_dir

    def etat():
        with atelier.json_store._conn() as c:
            return ru.etat_synchro(c, dd, rext)["etat"]
    assert etat() == "non_publie"
    p1 = _paquet(atelier, [rext])
    assert etat() == "en_attente"                          # pas encore acquitté
    _importer(classe, p1)
    _importer_retour(atelier, _retour(classe))
    assert etat() == "synchronise"
    with atelier.json_store._conn() as c:
        rpe.modifier(c, rext, "Nouvelle description")
    assert etat() == "modifie"
    p2 = _paquet(atelier, [rext])
    assert etat() == "en_attente"
    _importer(classe, p2)
    _importer_retour(atelier, _retour(classe))
    assert etat() == "synchronise"
    # L'appli en ligne n'a pas appliqué le paquet n° 3 (ancienne version
    # gardée) alors que le paquet lui est parvenu : en retard.
    with atelier.json_store._conn() as c:
        rpe.modifier(c, rext, "Encore")
    _paquet(atelier, [rext])
    with classe.json_store._conn() as c:
        doc = ru.construire(c)
    doc["echange"]["accuse"] = 3
    with classe.json_store._conn() as c:
        ech.archiver(c, classe.json_store.data_dir, doc["echange"], "u3.json", b"{}")
    _importer_retour(atelier, json.dumps(doc).encode())
    assert etat() == "en_retard"
    # Version inconnue de l'atelier : désynchronisé.
    with classe.json_store._conn() as c:
        doc = ru.construire(c)
    doc["referentiels"][0]["empreinte"] = "sha256:jamais-publiee"
    _importer_retour(atelier, json.dumps(doc).encode())
    assert etat() == "desynchronise"
    with atelier.json_store._conn() as c:
        from services import paquet_publication as pqt
        pub = next(x for x in pqt.lister_publiables(c, dd) if x["id"] == rext)
        assert pub["synchro"]["etat"] == "desynchronise"


def test_interne_verrouille_devient_utilise(apps):
    atelier, classe = apps
    rint = _interne(atelier)
    _importer(classe, _paquet(atelier, [rint]))
    _planifier(classe, rint, {"S01": "2026-09-07"})
    _importer_retour(atelier, _retour(classe))
    with atelier.json_store._conn() as c:
        assert c.execute("SELECT etat FROM referentiel_niveaux WHERE id=?",
                         (rint,)).fetchone()[0] == "utilise"


def test_routes_et_profils(apps):
    atelier, classe = apps
    rext, *_ = _externe(atelier)
    _importer(classe, _paquet(atelier, [rext]))
    cc, ca = classe.test_client(), atelier.test_client()
    assert cc.get("/api/retour-usage/apercu").get_json()["echange"]["numero"] == 1
    r = cc.post("/api/retour-usage/creer")
    assert r.status_code == 200 and json.loads(r.headers["X-Usage-Resume"])["numero"] == 1
    contenu = r.data
    assert ca.post("/api/retour-usage/creer").status_code == 404
    envoi = lambda: {"fichier": (__import__("io").BytesIO(contenu), "u.json")}   # noqa: E731
    assert cc.post("/api/retour-usage/importer", data=envoi(),
                   content_type="multipart/form-data").status_code == 404
    a = ca.post("/api/retour-usage/analyse", data=envoi(), content_type="multipart/form-data")
    assert a.get_json()["echange"]["statut"] == "attendu"
    r = ca.post("/api/retour-usage/importer", data=envoi(), content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json()["paquets_acquittes"] == [1]
    r = ca.post("/api/retour-usage/importer", data=envoi(), content_type="multipart/form-data")
    assert r.status_code == 409
    assert ca.post("/api/retour-usage/importer", data={},
                   content_type="multipart/form-data").status_code == 400
    assert ca.get("/api/retour-usage/etat").get_json()["usages"][0]["referentiel_id"] == rext
    assert cc.get("/api/echanges/envois/usage/1").status_code == 200
