"""tests/test_v0_19_0_progression_referentiel.py — v0.19.0

Réalignement de la progression sur le référentiel verrouillé :
- la colonne `source` n'existe plus (aucune distinction entre progressions) ;
- créer une progression liée à un référentiel `verrouille` le fait passer
  `utilise` (et il n'est alors plus déverrouillable) ;
- les objectifs d'un créneau sont lus depuis `referentiel_objectifs`
  (séquence + partie unique) ;
- les progressions `annule` sont filtrées de la liste.
"""

import pytest

from persistence.sqlite_store import SqliteStore


@pytest.fixture
def db(tmp_path):
    return SqliteStore(tmp_path / "data")


def _referentiel_verrouille(db, ref_id="N11_v2024", niveau="N11"):
    """Crée un référentiel verrouillé avec 1 séquence et 2 objectifs en
    partie 1, et insère partie_numero / nb_seances directement (creer_referentiel
    ne gère pas ces colonnes — elles relèvent de l'atelier référentiel)."""
    db.creer_referentiel({
        "id": ref_id, "niveau": niveau, "version": "2024",
        "verrouille": True,
        "themes": [{"code": "A", "nom": "Nombres et Calculs"}],
        "sequences": [{
            "code": "S01", "numero": 1, "nom": "Séquence test", "theme_code": "A",
            "objectifs": [
                {"code": "01", "nom": "Connaître", "fin_cycle": False},
                {"code": "02", "nom": "Calculer", "fin_cycle": True},
            ],
        }],
    })
    with db._conn() as conn:
        conn.execute(
            "UPDATE referentiel_objectifs SET partie_numero=1, nb_seances=3 "
            "WHERE referentiel_id=? AND seq_code='S01'", (ref_id,))
    return ref_id


def _etat_ref(db, ref_id):
    with db._conn() as conn:
        return conn.execute(
            "SELECT etat FROM referentiel_niveaux WHERE id=?", (ref_id,)
        ).fetchone()["etat"]


class TestSourceSupprimee:
    def test_colonne_source_absente_du_schema(self, db):
        with db._conn() as conn:
            cols = [c[1] for c in conn.execute(
                "PRAGMA table_info(progressions)").fetchall()]
        assert "source" not in cols

    def test_ecrire_progression_ignore_source(self, db):
        _referentiel_verrouille(db)
        # Même si un appelant legacy passe `source`, ça ne casse pas.
        db.ecrire_progression({
            "id": "pg_x", "niveau": "N11", "annee": "2024-2025",
            "etablissement": "Test", "source": "sequencesdb",
            "referentiel_id": "N11_v2024", "creneaux": [],
        })
        prog = db.lire_progression_par_id("pg_x")
        assert prog is not None
        assert "source" not in prog


class TestPassageUtilise:
    def test_creation_progression_passe_referentiel_a_utilise(self, db):
        ref = _referentiel_verrouille(db)
        assert _etat_ref(db, ref) == "verrouille"
        db.ecrire_progression({
            "id": "pg_1", "niveau": "N11", "annee": "2024-2025",
            "etablissement": "Test", "referentiel_id": ref, "creneaux": [],
        })
        assert _etat_ref(db, ref) == "utilise"

    def test_utilise_non_deverrouillable(self, db):
        from services import referentiels as svc
        ref = _referentiel_verrouille(db)
        db.ecrire_progression({
            "id": "pg_1", "niveau": "N11", "annee": "2024-2025",
            "etablissement": "Test", "referentiel_id": ref, "creneaux": [],
        })
        # Déverrouiller un référentiel `utilise` doit être refusé.
        with db._conn() as conn:
            with pytest.raises(ValueError):
                svc.deverrouiller(conn, ref)

    def test_idempotent_si_deja_utilise(self, db):
        ref = _referentiel_verrouille(db)
        for i in range(2):
            db.ecrire_progression({
                "id": f"pg_{i}", "niveau": "N11", "annee": f"202{i}-202{i+1}",
                "etablissement": "Test", "referentiel_id": ref, "creneaux": [],
            })
        assert _etat_ref(db, ref) == "utilise"


class TestObjectifsDepuisReferentiel:
    def test_objectifs_creneau_lus_du_referentiel(self, db):
        ref = _referentiel_verrouille(db)
        db.ecrire_progression({
            "id": "pg_1", "niveau": "N11", "annee": "2024-2025",
            "etablissement": "Test", "referentiel_id": ref,
            "creneaux": [{
                "id": "cr1", "sequence": "S01",
                "partie_debut": 1, "partie_fin": 1, "partie": 1,
                "ordre": 1,
            }],
        })
        prog = db.lire_progression_par_id("pg_1")
        cr = prog["creneaux"][0]
        assert len(cr["objectifs"]) == 2
        codes = {o["code"] for o in cr["objectifs"]}
        assert codes == {"01", "02"}
        # nb_seances et fin_cycle remontés depuis le référentiel.
        o2 = next(o for o in cr["objectifs"] if o["code"] == "02")
        assert o2["nb_seances"] == 3
        assert o2["fin_cycle"] is True

    def test_objectifs_filtres_par_partie(self, db):
        ref = _referentiel_verrouille(db)
        # Déplacer l'objectif 02 en partie 2 : un créneau partie 1 ne doit
        # plus voir que l'objectif 01.
        with db._conn() as conn:
            conn.execute(
                "UPDATE referentiel_objectifs SET partie_numero=2 "
                "WHERE referentiel_id=? AND code='02'", (ref,))
        db.ecrire_progression({
            "id": "pg_1", "niveau": "N11", "annee": "2024-2025",
            "etablissement": "Test", "referentiel_id": ref,
            "creneaux": [{
                "id": "cr1", "sequence": "S01",
                "partie_debut": 1, "partie_fin": 1, "partie": 1, "ordre": 1,
            }],
        })
        prog = db.lire_progression_par_id("pg_1")
        codes = {o["code"] for o in prog["creneaux"][0]["objectifs"]}
        assert codes == {"01"}

    def test_sans_referentiel_pas_objectifs(self, db):
        # Une progression sans referentiel_id n'a pas d'objectifs auto.
        db.ecrire_progression({
            "id": "pg_1", "niveau": "N11", "annee": "2024-2025",
            "etablissement": "Test", "referentiel_id": None,
            "creneaux": [{
                "id": "cr1", "sequence": "S01",
                "partie_debut": 1, "partie_fin": 1, "partie": 1, "ordre": 1,
            }],
        })
        prog = db.lire_progression_par_id("pg_1")
        assert prog["creneaux"][0]["objectifs"] == []


class TestFiltreAnnule:
    def test_progression_annule_exclue_de_la_liste(self, db):
        ref = _referentiel_verrouille(db)
        db.ecrire_progression({
            "id": "pg_ok", "niveau": "N11", "annee": "2024-2025",
            "etablissement": "EtabA", "referentiel_id": ref, "creneaux": [],
        })
        db.ecrire_progression({
            "id": "pg_ann", "niveau": "N11", "annee": "2025-2026",
            "etablissement": "EtabB", "referentiel_id": ref,
            "etat": "annule", "creneaux": [],
        })
        ids = {p["id"] for p in db.lister_progressions("N11")}
        assert "pg_ok" in ids
        assert "pg_ann" not in ids
