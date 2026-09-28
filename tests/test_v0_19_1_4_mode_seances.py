"""tests/test_v0_19_1_4_mode_seances.py — v0.19.1.4

Modèle de séances à deux régimes :
  - 'par_objectif' (défaut, modèle courant) ;
  - 'par_serie' (modèle historique) : matrice (niveau-cible × série) par
    (séquence, partie), stockée dans `referentiel_parties_seances`, clé sur le
    référentiel.

Le mode est porté par `referentiel_niveaux.mode_seances` (decision A). Une
progression hérite du mode via son referentiel_id.

Tests :
  - migration : colonne mode_seances (défaut 'par_objectif') + table créée ;
  - store.lister_seances_par_serie ;
  - route /parties expose mode_seances + seances_par_serie (vide en
    'par_objectif', peuplé en 'par_serie').
"""

import pytest

from persistence.sqlite_store import SqliteStore


@pytest.fixture
def db(tmp_path):
    return SqliteStore(tmp_path / "data")


def _ref(db, ref_id="N11_v2021", niveau="N11", mode="par_objectif"):
    with db._conn() as conn:
        conn.execute("""INSERT INTO referentiel_niveaux
            (id, niveau, version, date_debut, date_fin, description, etat,
             mode_seances)
            VALUES (?, ?, '2021', '2021-09-01', '2022-08-31', 'T', 'verrouille', ?)""",
            (ref_id, niveau, mode))
        conn.execute("""INSERT INTO referentiel_themes
            (referentiel_id, code, nom, couleur) VALUES (?, 'D', 'Géo', 'geo')""",
            (ref_id,))
        conn.execute("""INSERT INTO referentiel_sequences
            (referentiel_id, code, numero, nom, theme_code)
            VALUES (?, 'S12', 12, 'Géométrie plane', 'D')""", (ref_id,))
    return ref_id


def _matrice_s12(db, ref_id):
    """Renseigne la matrice historique de S12 partie 1 (cibles TB et S)."""
    lignes = [
        # cible TB : R/F/A/E
        ('S12', 1, 'TB', 'R', 1.0), ('S12', 1, 'TB', 'F', 1.5),
        ('S12', 1, 'TB', 'A', 2.0), ('S12', 1, 'TB', 'E', 2.5),
        # cible S : R/F/A (pas d'exploration)
        ('S12', 1, 'S', 'R', 1.5), ('S12', 1, 'S', 'F', 2.5),
        ('S12', 1, 'S', 'A', 3.0),
    ]
    with db._conn() as conn:
        for (seq, p, cible, serie, nb) in lignes:
            conn.execute("""INSERT INTO referentiel_parties_seances
                (referentiel_id, seq_code, partie_numero, niveau_cible,
                 serie, nb_seances) VALUES (?,?,?,?,?,?)""",
                (ref_id, seq, p, cible, serie, nb))


class TestMigration:
    def test_colonne_mode_seances_defaut(self, db):
        with db._conn() as conn:
            cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(referentiel_niveaux)")}
        assert "mode_seances" in cols

    def test_table_seances_par_serie_creee(self, db):
        with db._conn() as conn:
            t = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='referentiel_parties_seances'").fetchone()
        assert t is not None

    def test_referentiel_neuf_est_par_objectif(self, db):
        ref = _ref(db)  # sans préciser → defaut colonne
        r = db.lire_referentiel(ref)
        assert r["mode_seances"] in ("par_objectif",)


class TestListerSeancesParSerie:
    def test_vide_si_par_objectif(self, db):
        ref = _ref(db, mode="par_objectif")
        assert db.lister_seances_par_serie(ref) == []

    def test_matrice_complete(self, db):
        ref = _ref(db, mode="par_serie")
        _matrice_s12(db, ref)
        rows = db.lister_seances_par_serie(ref)
        assert len(rows) == 7
        # Cible TB a 4 séries, cible S en a 3 (pas d'E).
        tb = {r["serie"]: r["nb_seances"] for r in rows
              if r["niveau_cible"] == "TB"}
        s = {r["serie"]: r["nb_seances"] for r in rows
             if r["niveau_cible"] == "S"}
        assert set(tb) == {"R", "F", "A", "E"}
        assert set(s) == {"R", "F", "A"}
        assert tb["E"] == 2.5 and s["F"] == 2.5


class TestRouteParties:
    def test_mode_par_objectif_seances_vides(self, client, app):
        _ref(app.json_store, mode="par_objectif")
        r = client.get("/api/referentiels/N11_v2021/parties")
        data = r.get_json()
        assert data["ref"]["mode_seances"] == "par_objectif"
        assert data["seances_par_serie"] == []

    def test_mode_par_serie_expose_matrice(self, client, app):
        ref = _ref(app.json_store, mode="par_serie")
        _matrice_s12(app.json_store, ref)
        r = client.get("/api/referentiels/N11_v2021/parties")
        data = r.get_json()
        assert data["ref"]["mode_seances"] == "par_serie"
        assert len(data["seances_par_serie"]) == 7
        # Vérifie une cellule.
        cell = next(x for x in data["seances_par_serie"]
                    if x["niveau_cible"] == "TB" and x["serie"] == "E")
        assert cell["nb_seances"] == 2.5
