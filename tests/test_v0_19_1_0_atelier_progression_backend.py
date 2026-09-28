"""tests/test_v0_19_1_0_atelier_progression_backend.py — v0.19.1.0

Backend de l'ossature OO « Progression devient atelier d'assemblage ».

Périmètre v0.19.1.0 (sans DnD ni changement de référentiel) :
- `store.lister_parties_referentiel` : liste à plat des parties de séquence
  d'un référentiel figé, pour la barre latérale (toutes les parties, même
  non placées). Lit le SNAPSHOT figé, pas les tables actives.
- `GET /api/referentiels/<ref_id>/parties` : route exposant cette liste.
- `GET /api/referentiels?niveau=&etats=verrouille,utilise` : filtre la liste
  des référentiels par état — l'atelier Progression ne peut s'appuyer que sur
  un référentiel `verrouille` ou `utilise` (D2).

Pourquoi ces invariants :
- La sidebar doit montrer TOUTES les parties (placées ou non) — sans le
  filtre d'état correct, on proposerait des référentiels `en_cours` non
  exploitables, ou on masquerait les `utilise` (déjà consommés par une
  progression mais toujours valides comme support).
"""

import pytest

from persistence.sqlite_store import SqliteStore


@pytest.fixture
def db(tmp_path):
    return SqliteStore(tmp_path / "data")


def _referentiel(db, ref_id, niveau, version, etat="verrouille",
                 sequences=None):
    """Crée un référentiel. `sequences` : liste de
    (seq_code, numero, nom, [(obj_code, partie_numero, nb_seances), ...])."""
    if sequences is None:
        sequences = [
            ("S01", 1, "Séquence un", [
                ("01", 1, 3), ("02", 1, 2), ("03", 2, 4),
            ]),
            ("S02", 2, "Séquence deux", [
                ("01", 1, 1),
            ]),
        ]
    seqs_payload = []
    for code, numero, nom, objs in sequences:
        seqs_payload.append({
            "code": code, "numero": numero, "nom": nom, "theme_code": "A",
            "objectifs": [
                {"code": oc, "nom": f"obj {oc}", "fin_cycle": False}
                for (oc, _pn, _nb) in objs
            ],
        })
    db.creer_referentiel({
        "id": ref_id, "niveau": niveau, "version": version,
        "etat": "verrouille" if etat in ("verrouille", "utilise") else etat,
        "themes": [{"code": "A", "nom": "Nombres et Calculs"}],
        "sequences": seqs_payload,
    })
    # Renseigner partie_numero / nb_seances (creer_referentiel ne les gère pas)
    with db._conn() as conn:
        for code, _numero, _nom, objs in sequences:
            for (oc, pn, nb) in objs:
                conn.execute(
                    "UPDATE referentiel_objectifs "
                    "SET partie_numero=?, nb_seances=? "
                    "WHERE referentiel_id=? AND seq_code=? AND code=?",
                    (pn, nb, ref_id, code, oc))
        # Forcer l'état final (utilise n'est pas accepté par creer_referentiel)
        conn.execute("UPDATE referentiel_niveaux SET etat=? WHERE id=?",
                     (etat, ref_id))
    return ref_id


class TestListerPartiesReferentiel:
    def test_introuvable_retourne_none(self, db):
        assert db.lister_parties_referentiel("inexistant") is None

    def test_parties_a_plat_ordonnees(self, db):
        ref = _referentiel(db, "N11_v2024", "N11", "2024")
        parties = db.lister_parties_referentiel(ref)
        # S01 a 2 parties (1, 2), S02 a 1 partie (1) → 3 parties.
        cles = [(p["seq_code"], p["partie_numero"]) for p in parties]
        assert cles == [("S01", 1), ("S01", 2), ("S02", 1)]

    def test_compte_objectifs_et_seances(self, db):
        ref = _referentiel(db, "N11_v2024", "N11", "2024")
        parties = db.lister_parties_referentiel(ref)
        p_s01_1 = next(p for p in parties
                       if p["seq_code"] == "S01" and p["partie_numero"] == 1)
        # S01 partie 1 : objectifs 01 (3 séances) + 02 (2 séances)
        assert p_s01_1["nb_objectifs"] == 2
        assert p_s01_1["nb_seances_prevues"] == 5
        p_s01_2 = next(p for p in parties
                       if p["seq_code"] == "S01" and p["partie_numero"] == 2)
        assert p_s01_2["nb_objectifs"] == 1
        assert p_s01_2["nb_seances_prevues"] == 4

    def test_porte_metadonnees_sequence(self, db):
        ref = _referentiel(db, "N11_v2024", "N11", "2024")
        parties = db.lister_parties_referentiel(ref)
        p = parties[0]
        assert p["seq_numero"] == 1
        assert p["seq_nom"] == "Séquence un"
        assert p["theme_code"] == "A"

    def test_sequence_sans_objectif_expose_partie_1(self, db):
        # Référentiel avec une séquence sans aucun objectif.
        ref = _referentiel(db, "N11_v2025", "N11", "2025", sequences=[
            ("S09", 9, "Séquence vide", []),
        ])
        parties = db.lister_parties_referentiel(ref)
        assert len(parties) == 1
        assert parties[0]["seq_code"] == "S09"
        assert parties[0]["partie_numero"] == 1
        assert parties[0]["nb_objectifs"] == 0


class TestRouteParties:
    def test_404_si_introuvable(self, client):
        r = client.get("/api/referentiels/inexistant/parties")
        assert r.status_code == 404

    def test_retourne_ref_et_parties(self, client, app):
        _referentiel(app.json_store, "N11_v2024", "N11", "2024",
                     etat="verrouille")
        r = client.get("/api/referentiels/N11_v2024/parties")
        assert r.status_code == 200
        data = r.get_json()
        assert data["ref"]["id"] == "N11_v2024"
        assert data["ref"]["etat"] == "verrouille"
        cles = [(p["seq_code"], p["partie_numero"]) for p in data["parties"]]
        assert ("S01", 1) in cles and ("S01", 2) in cles


class TestFiltreEtatListe:
    def _creer_jeu(self, db):
        _referentiel(db, "N11_vA", "N11", "2021", etat="verrouille")
        _referentiel(db, "N11_vB", "N11", "2022", etat="utilise")
        _referentiel(db, "N11_vC", "N11", "2023", etat="en_cours")

    def test_sans_filtre_tous_les_etats(self, client, app):
        self._creer_jeu(app.json_store)
        r = client.get("/api/referentiels?niveau=N11")
        ids = {x["id"] for x in r.get_json()["referentiels"]}
        assert {"N11_vA", "N11_vB", "N11_vC"} <= ids

    def test_filtre_verrouille_utilise(self, client, app):
        self._creer_jeu(app.json_store)
        r = client.get(
            "/api/referentiels?niveau=N11&etats=verrouille,utilise")
        refs = r.get_json()["referentiels"]
        ids = {x["id"] for x in refs}
        # en_cours exclu, verrouille + utilise inclus.
        assert ids == {"N11_vA", "N11_vB"}
        assert all(x["etat"] in ("verrouille", "utilise") for x in refs)

    def test_filtre_un_seul_etat(self, client, app):
        self._creer_jeu(app.json_store)
        r = client.get("/api/referentiels?niveau=N11&etats=utilise")
        ids = {x["id"] for x in r.get_json()["referentiels"]}
        assert ids == {"N11_vB"}


class TestCreneauDesambiguationParProgressionId:
    """v0.19.1.0 — creneau-ajouter et creneau DELETE acceptent un
    `progression_id` pour cibler la bonne progression quand plusieurs
    établissements partagent le même couple (niveau, année). Sans cet id,
    lire_progression retomberait sur l'établissement « Non renseigné ».
    """

    def _deux_progressions(self, app):
        db = app.json_store
        _referentiel(db, "N11_v2024", "N11", "2024", etat="verrouille")
        db.ecrire_progression({
            "niveau": "N11", "annee": "2030-2031",
            "etablissement": "Collège A", "referentiel_id": "N11_v2024",
            "creneaux": [],
        })
        db.ecrire_progression({
            "niveau": "N11", "annee": "2030-2031",
            "etablissement": "Collège B", "referentiel_id": "N11_v2024",
            "creneaux": [],
        })
        pa = db.lire_progression("N11", "2030-2031", "Collège A")
        pb = db.lire_progression("N11", "2030-2031", "Collège B")
        return pa, pb

    def test_ajout_cible_la_bonne_progression(self, client, app):
        pa, pb = self._deux_progressions(app)
        r = client.post("/api/progression/N11/creneau-ajouter", json={
            "progression_id": pb["id"], "annee": "2030-2031",
            "sequence": "S01", "partie_debut": 1, "partie_fin": 1,
            "partie": "", "periode": "", "date_debut": None, "date_fin": None,
        })
        assert r.status_code == 200 and r.get_json().get("ok")
        pb2 = app.json_store.lire_progression_par_id(pb["id"])
        pa2 = app.json_store.lire_progression_par_id(pa["id"])
        assert len(pb2["creneaux"]) == 1
        assert len(pa2["creneaux"]) == 0

    def test_suppression_cible_la_bonne_progression(self, client, app):
        pa, pb = self._deux_progressions(app)
        client.post("/api/progression/N11/creneau-ajouter", json={
            "progression_id": pb["id"], "annee": "2030-2031",
            "sequence": "S01", "partie_debut": 1, "partie_fin": 1,
            "partie": "", "periode": "", "date_debut": None, "date_fin": None,
        })
        cid = app.json_store.lire_progression_par_id(pb["id"])["creneaux"][0]["id"]
        r = client.delete(f"/api/progression/N11/creneau/{cid}", json={
            "progression_id": pb["id"], "annee": "2030-2031",
        })
        assert r.status_code == 200 and r.get_json().get("ok")
        assert len(app.json_store.lire_progression_par_id(pb["id"])["creneaux"]) == 0

    def test_creneau_sans_date_accepte(self, client, app):
        """poserPartie (Q-F b) : un créneau peut être créé sans date."""
        _, pb = self._deux_progressions(app)
        r = client.post("/api/progression/N11/creneau-ajouter", json={
            "progression_id": pb["id"], "annee": "2030-2031",
            "sequence": "S02", "partie_debut": 1, "partie_fin": 1,
            "partie": "", "periode": "", "date_debut": None, "date_fin": None,
        })
        assert r.status_code == 200
        cr = app.json_store.lire_progression_par_id(pb["id"])["creneaux"][0]
        assert not cr.get("date_debut")
