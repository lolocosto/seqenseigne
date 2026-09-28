"""tests/test_v0_12_0_seances.py — v0.12.0.

Tests du chantier 1 « Plan de travail générique » :
- Schéma : présence des deux nouvelles colonnes après init du SqliteStore.
- Service : modifier_seances_partie et modifier_seances_objectif
  (validation, bornes, types acceptés, intégration _format_retour_objectif).
- Lecture : v2_lecture expose `nb_seances_R_AE` et `nb_seances`.
- Routes : 200 / 400 / 404 sur les deux nouveaux PATCH.

Convention : on suit le pattern des tests R4e* (schéma minimal in-memory pour
les tests de service, client Flask via conftest pour les tests de routes).
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Schéma minimal pour les tests unitaires ──────────────────────────────────
# Inclut nb_seances_R_AE (sequence_parties) et nb_seances (objectifs)
# qui sont les nouvelles colonnes v0.12.0. On garde la définition la plus
# proche possible du schema.sql réel pour limiter les divergences.

_SCHEMA_TEST = """
CREATE TABLE methodes (
    id       TEXT PRIMARY KEY,
    titre    TEXT NOT NULL DEFAULT '',
    niveau   TEXT NOT NULL DEFAULT '',
    sequence TEXT NOT NULL DEFAULT '',
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);

-- Tables nécessaires aux jointures de v2_lecture._charger_sequence_par_niveau
-- (qui joint sn → sequences_du_cycle → themes pour récupérer le nom et le
-- thème de la séquence).
CREATE TABLE cycles (
    code        TEXT PRIMARY KEY,
    nom         TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE themes (
    id           TEXT PRIMARY KEY,
    cycle_code   TEXT NOT NULL,
    code         TEXT NOT NULL,
    nom          TEXT NOT NULL,
    code_couleur TEXT NOT NULL DEFAULT '',
    description  TEXT NOT NULL DEFAULT '',
    ordre        INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE sequences_du_cycle (
    id          TEXT PRIMARY KEY,
    cycle_code  TEXT NOT NULL,
    code        TEXT NOT NULL,
    numero      INTEGER NOT NULL,
    nom         TEXT NOT NULL,
    theme_id    TEXT
);

CREATE TABLE sequences_par_niveau (
    id            TEXT PRIMARY KEY,
    niveau        TEXT NOT NULL,
    sequence_code TEXT NOT NULL,
    parametres    TEXT NOT NULL DEFAULT '',
    UNIQUE (niveau, sequence_code)
);

CREATE TABLE sequence_parties (
    id                     TEXT PRIMARY KEY,
    sequence_par_niveau_id TEXT NOT NULL
                           REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    numero                 INTEGER NOT NULL,
    nb_seances_R_AE        REAL NOT NULL DEFAULT 0,
    UNIQUE (sequence_par_niveau_id, numero)
);

CREATE TABLE objectifs (
    id         TEXT PRIMARY KEY,
    partie_id  TEXT NOT NULL
               REFERENCES sequence_parties(id) ON DELETE CASCADE,
    code       TEXT NOT NULL,
    nom        TEXT NOT NULL DEFAULT '',
    methode_id TEXT REFERENCES methodes(id) ON DELETE SET NULL,
    critere_F  TEXT NOT NULL DEFAULT '',
    critere_A  TEXT NOT NULL DEFAULT '',
    critere_E  TEXT NOT NULL DEFAULT '',
    fin_cycle  TEXT NOT NULL DEFAULT 'N',
    nb_seances REAL NOT NULL DEFAULT 0,
    UNIQUE (partie_id, code)
);

-- Tables annexes nécessaires aux services (lecture des notions liées,
-- résolution d'exos par série).
CREATE TABLE notions (
    id     TEXT PRIMARY KEY,
    titre  TEXT NOT NULL DEFAULT '',
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE objectif_notions (
    objectif_id TEXT NOT NULL REFERENCES objectifs(id) ON DELETE CASCADE,
    notion_id   TEXT NOT NULL REFERENCES notions(id) ON DELETE CASCADE,
    ordre       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, notion_id)
);
CREATE TABLE exercices (
    id         TEXT PRIMARY KEY,
    serie      TEXT NOT NULL,
    titre        TEXT NOT NULL DEFAULT '',
    niveau     TEXT NOT NULL DEFAULT '',
    sequence   TEXT NOT NULL DEFAULT '',
    num        INTEGER,
    fichier    TEXT NOT NULL DEFAULT '',
    serie_code TEXT NOT NULL DEFAULT '',
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE objectif_exos (
    objectif_id    TEXT NOT NULL REFERENCES objectifs(id) ON DELETE CASCADE,
    serie          TEXT NOT NULL,
    exercice_id    TEXT NOT NULL REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre          INTEGER NOT NULL DEFAULT 0,
    origin_niveau  TEXT,
    origin_seq     TEXT,
    origin_serie   TEXT,
    origin_num     INTEGER,
    PRIMARY KEY (objectif_id, serie, exercice_id)
);

-- Tables touchées (en lecture) par v2_lecture mais avec un try/except.
-- On les crée pour que les rares qui sont sans try (comme
-- partie_precedences) ne fassent pas planter le test.
CREATE TABLE partie_precedences (
    partie_id        TEXT NOT NULL REFERENCES sequence_parties(id) ON DELETE CASCADE,
    precedent_niveau TEXT NOT NULL,
    precedent_seq    TEXT NOT NULL,
    PRIMARY KEY (partie_id, precedent_niveau, precedent_seq)
);
CREATE TABLE partie_exos_revision_approche (
    partie_id      TEXT NOT NULL REFERENCES sequence_parties(id) ON DELETE CASCADE,
    type           TEXT NOT NULL,
    exercice_id    TEXT NOT NULL,
    ordre          INTEGER NOT NULL DEFAULT 0,
    origin_niveau  TEXT,
    origin_seq     TEXT,
    origin_serie   TEXT,
    origin_num     INTEGER,
    PRIMARY KEY (partie_id, type, exercice_id)
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(_SCHEMA_TEST)
    yield c
    c.close()


@pytest.fixture
def base(conn):
    """Structure : 1 séquence sn_A (N11/S03) avec 2 parties.
       pt_A1 (#1) : ob_01 (Cours, code 01) + ob_02 (Calculer, code 02)
       pt_A2 (#2) : ob_11 (Cours bis, code 11)
    Toutes les valeurs nb_seances_R_AE et nb_seances démarrent à 0
    (DEFAULT du schéma).
    """
    conn.executescript("""
        INSERT INTO cycles (code, nom) VALUES ('C04', 'Cycle 4');
        INSERT INTO themes (id, cycle_code, code, nom) VALUES
            ('th_A', 'C04', 'A', 'Nombres');
        INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
            VALUES ('sc_S03', 'C04', 'S03', 3, 'Calcul numérique', 'th_A');
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
            ('sn_A', 'N11', 'S03');
        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
            ('pt_A1', 'sn_A', 1),
            ('pt_A2', 'sn_A', 2);
        INSERT INTO objectifs (id, partie_id, code, nom) VALUES
            ('ob_01', 'pt_A1', '01', 'Cours'),
            ('ob_02', 'pt_A1', '02', 'Calculer'),
            ('ob_11', 'pt_A2', '11', 'Cours bis');
    """)
    conn.commit()
    return conn


# ═════════════════════════════════════════════════════════════════════════════
# 1. Présence des colonnes après init du SqliteStore (test bout-en-bout)
# ═════════════════════════════════════════════════════════════════════════════

class TestSchemaInit:
    """Vérifie que le SqliteStore crée bien les deux colonnes au démarrage,
    soit via le DDL principal (base neuve), soit via la migration ALTER
    TABLE (base préexistante). On simule les deux cas.
    """

    def test_base_neuve_a_les_colonnes(self, tmp_path):
        from persistence.sqlite_store import SqliteStore
        s = SqliteStore(tmp_path / "data1")
        with s._conn() as conn:
            cols_pt = {r["name"] for r in conn.execute(
                "PRAGMA table_info(sequence_parties)"
            )}
            cols_ob = {r["name"] for r in conn.execute(
                "PRAGMA table_info(objectifs)"
            )}
        assert "nb_seances_R_AE" in cols_pt
        assert "nb_seances" in cols_ob

    def test_migration_idempotente(self, tmp_path):
        """Réinitialiser plusieurs fois ne casse pas la base."""
        from persistence.sqlite_store import SqliteStore
        s1 = SqliteStore(tmp_path / "data2")
        s2 = SqliteStore(tmp_path / "data2")  # même chemin = même base
        with s2._conn() as conn:
            cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(objectifs)"
            )}
        assert "nb_seances" in cols


# ═════════════════════════════════════════════════════════════════════════════
# 2. Service modifier_seances_partie
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    modifier_seances_partie,
    modifier_seances_objectif,
    SeancesInvalides,
    PartieIntrouvable,
    ObjectifIntrouvable,
)


class TestModifierSeancesPartie:

    def test_valeur_entiere(self, base):
        rep = modifier_seances_partie(base, "pt_A1", 3)
        assert rep["nb_seances_R_AE"] == 3.0
        assert rep["id"] == "pt_A1"
        assert rep["numero"] == 1

    def test_demi_seance(self, base):
        rep = modifier_seances_partie(base, "pt_A1", 1.5)
        assert rep["nb_seances_R_AE"] == 1.5

    def test_zero(self, base):
        rep = modifier_seances_partie(base, "pt_A1", 0)
        assert rep["nb_seances_R_AE"] == 0.0

    def test_string_convertible(self, base):
        rep = modifier_seances_partie(base, "pt_A1", "2.5")
        assert rep["nb_seances_R_AE"] == 2.5

    def test_string_virgule_fr(self, base):
        rep = modifier_seances_partie(base, "pt_A1", "1,5")
        assert rep["nb_seances_R_AE"] == 1.5

    def test_string_avec_espaces(self, base):
        rep = modifier_seances_partie(base, "pt_A1", "  2 ")
        assert rep["nb_seances_R_AE"] == 2.0

    def test_persistance(self, base):
        modifier_seances_partie(base, "pt_A1", 4)
        row = base.execute(
            "SELECT nb_seances_R_AE FROM sequence_parties WHERE id = ?",
            ("pt_A1",),
        ).fetchone()
        assert row["nb_seances_R_AE"] == 4.0

    def test_negatif_refuse(self, base):
        with pytest.raises(SeancesInvalides):
            modifier_seances_partie(base, "pt_A1", -1)

    def test_borne_haute_refusee(self, base):
        with pytest.raises(SeancesInvalides):
            modifier_seances_partie(base, "pt_A1", 1000)

    def test_borne_haute_acceptee(self, base):
        rep = modifier_seances_partie(base, "pt_A1", 999)
        assert rep["nb_seances_R_AE"] == 999.0

    def test_none_refuse(self, base):
        with pytest.raises(SeancesInvalides):
            modifier_seances_partie(base, "pt_A1", None)

    def test_string_non_convertible_refusee(self, base):
        with pytest.raises(SeancesInvalides):
            modifier_seances_partie(base, "pt_A1", "abc")

    def test_bool_refuse(self, base):
        with pytest.raises(SeancesInvalides):
            modifier_seances_partie(base, "pt_A1", True)

    def test_partie_introuvable(self, base):
        with pytest.raises(PartieIntrouvable):
            modifier_seances_partie(base, "pt_inconnu", 1)


# ═════════════════════════════════════════════════════════════════════════════
# 3. Service modifier_seances_objectif
# ═════════════════════════════════════════════════════════════════════════════

class TestModifierSeancesObjectif:

    def test_objectif_cours(self, base):
        rep = modifier_seances_objectif(base, "ob_01", 2)
        assert rep["nb_seances"] == 2.0
        assert rep["code"] == "01"
        # _format_retour_objectif inclut tous les champs habituels
        assert "methode_titre" in rep
        assert "fin_cycle" in rep
        assert "code_coherent" in rep

    def test_objectif_exo(self, base):
        rep = modifier_seances_objectif(base, "ob_02", 1.5)
        assert rep["nb_seances"] == 1.5
        assert rep["code"] == "02"

    def test_persistance(self, base):
        modifier_seances_objectif(base, "ob_02", 3.5)
        row = base.execute(
            "SELECT nb_seances FROM objectifs WHERE id = ?", ("ob_02",)
        ).fetchone()
        assert row["nb_seances"] == 3.5

    def test_objectif_introuvable(self, base):
        with pytest.raises(ObjectifIntrouvable):
            modifier_seances_objectif(base, "ob_inconnu", 1)

    def test_negatif_refuse(self, base):
        with pytest.raises(SeancesInvalides):
            modifier_seances_objectif(base, "ob_01", -0.5)


# ═════════════════════════════════════════════════════════════════════════════
# 4. Lecture via v2_lecture : exposition des nouveaux champs
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_lecture import lire_sequence_par_niveau


class TestLectureSeances:

    def test_partie_expose_nb_seances_R_AE(self, base):
        modifier_seances_partie(base, "pt_A1", 2.5)
        modifier_seances_partie(base, "pt_A2", 1)
        data = lire_sequence_par_niveau(base, "N11", "S03")
        parties = data["parties"]
        assert len(parties) == 2
        assert parties[0]["nb_seances_R_AE"] == 2.5
        assert parties[1]["nb_seances_R_AE"] == 1.0

    def test_objectif_expose_nb_seances(self, base):
        modifier_seances_objectif(base, "ob_01", 3)
        modifier_seances_objectif(base, "ob_02", 1.5)
        data = lire_sequence_par_niveau(base, "N11", "S03")
        objs = {o["code"]: o for o in data["parties"][0]["objectifs"]}
        assert objs["01"]["nb_seances"] == 3.0
        assert objs["02"]["nb_seances"] == 1.5

    def test_defaut_zero(self, base):
        # Aucune mutation : tous à 0 par DEFAULT
        data = lire_sequence_par_niveau(base, "N11", "S03")
        for p in data["parties"]:
            assert p["nb_seances_R_AE"] == 0
            for o in p["objectifs"]:
                assert o["nb_seances"] == 0


# ═════════════════════════════════════════════════════════════════════════════
# 5. Routes HTTP (intégration via le client Flask du conftest)
# ═════════════════════════════════════════════════════════════════════════════
#
# Les fixtures 'client' / 'store' du conftest global montent une vraie
# instance Flask avec base SQLite en tmp_path, donc la migration
# v0.12.0 a déjà tourné — les colonnes existent.

class TestRoutesSeancesPartie:
    """PATCH /api/v2/parties/<id>/seances"""

    def _setup(self, store):
        with store._conn() as conn:
            conn.executescript("""
                INSERT INTO sequences_par_niveau (id, niveau, sequence_code)
                    VALUES ('sn_T', 'N11', 'S03');
                INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                    VALUES ('pt_T', 'sn_T', 1);
            """)
            conn.commit()

    def test_patch_nominal(self, client, store):
        self._setup(store)
        r = client.patch(
            "/api/v2/parties/pt_T/seances",
            json={"nb_seances": 2.5},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["nb_seances_R_AE"] == 2.5
        assert data["id"] == "pt_T"

    def test_patch_demi_seance(self, client, store):
        self._setup(store)
        r = client.patch(
            "/api/v2/parties/pt_T/seances",
            json={"nb_seances": 0.5},
        )
        assert r.status_code == 200
        assert r.get_json()["nb_seances_R_AE"] == 0.5

    def test_patch_string_virgule(self, client, store):
        self._setup(store)
        r = client.patch(
            "/api/v2/parties/pt_T/seances",
            json={"nb_seances": "1,5"},
        )
        assert r.status_code == 200
        assert r.get_json()["nb_seances_R_AE"] == 1.5

    def test_patch_partie_inconnue(self, client, store):
        self._setup(store)
        r = client.patch(
            "/api/v2/parties/pt_inconnu/seances",
            json={"nb_seances": 1},
        )
        assert r.status_code == 404
        assert r.get_json()["code"] == "partie_introuvable"

    def test_patch_payload_sans_champ(self, client, store):
        self._setup(store)
        r = client.patch(
            "/api/v2/parties/pt_T/seances",
            json={},
        )
        assert r.status_code == 400
        assert r.get_json()["code"] == "champ_manquant"

    def test_patch_valeur_negative(self, client, store):
        self._setup(store)
        r = client.patch(
            "/api/v2/parties/pt_T/seances",
            json={"nb_seances": -1},
        )
        assert r.status_code == 400
        assert r.get_json()["code"] == "seances_invalides"

    def test_patch_valeur_aberrante(self, client, store):
        self._setup(store)
        r = client.patch(
            "/api/v2/parties/pt_T/seances",
            json={"nb_seances": 10000},
        )
        assert r.status_code == 400
        assert r.get_json()["code"] == "seances_invalides"

    def test_patch_string_invalide(self, client, store):
        self._setup(store)
        r = client.patch(
            "/api/v2/parties/pt_T/seances",
            json={"nb_seances": "abc"},
        )
        assert r.status_code == 400
        assert r.get_json()["code"] == "seances_invalides"


class TestRoutesSeancesObjectif:
    """PATCH /api/v2/objectifs/<id>/seances"""

    def _setup(self, store):
        with store._conn() as conn:
            conn.executescript("""
                INSERT INTO sequences_par_niveau (id, niveau, sequence_code)
                    VALUES ('sn_T2', 'N11', 'S04');
                INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                    VALUES ('pt_T2', 'sn_T2', 1);
                INSERT INTO objectifs (id, partie_id, code, nom)
                    VALUES ('ob_T2', 'pt_T2', '02', 'Calculer');
            """)
            conn.commit()

    def test_patch_nominal(self, client, store):
        self._setup(store)
        r = client.patch(
            "/api/v2/objectifs/ob_T2/seances",
            json={"nb_seances": 2},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["nb_seances"] == 2.0
        # Le retour est _format_retour_objectif complet
        assert data["code"] == "02"
        assert "methode_titre" in data
        assert "code_coherent" in data

    def test_patch_objectif_inconnu(self, client, store):
        self._setup(store)
        r = client.patch(
            "/api/v2/objectifs/ob_inconnu/seances",
            json={"nb_seances": 1},
        )
        assert r.status_code == 404
        assert r.get_json()["code"] == "objectif_introuvable"

    def test_patch_payload_sans_champ(self, client, store):
        self._setup(store)
        r = client.patch(
            "/api/v2/objectifs/ob_T2/seances",
            json={},
        )
        assert r.status_code == 400
        assert r.get_json()["code"] == "champ_manquant"

    def test_patch_borne_haute(self, client, store):
        self._setup(store)
        r = client.patch(
            "/api/v2/objectifs/ob_T2/seances",
            json={"nb_seances": 999},
        )
        assert r.status_code == 200
        assert r.get_json()["nb_seances"] == 999.0
