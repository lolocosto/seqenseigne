"""tests/test_v0_12_3_0_deplacer_objectif.py — v0.12.3.0.

Tests du chantier 4/5 « Suppression du toggle Assemblage / Édition
avancée » — partie 1 (port des fonctionnalités).

Ce fichier couvre **uniquement** le Bloc 0 du chantier : le service
`deplacer_objectif_avec_position` et sa route HTTP. Les blocs 1+2
(drag-and-drop frontend, fin-de-cycle UI) sont purement front,
pas de tests Python.

Les blocs 3+4 (suppression effective d'editv2 et retrait du rappel
niveau/séquence) feront l'objet de la livraison v0.12.3.1.

Convention : on suit le pattern de test_v0_12_0_seances.py (schéma
minimal in-memory pour les services, client Flask via conftest pour
les routes).
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.v2_edition import (
    deplacer_objectif_avec_position,
    ReassignationImpossible,
    ReordonnancementInvalide,
    ObjectifIntrouvable,
    PartieIntrouvable,
)


# ── Schéma minimal ───────────────────────────────────────────────────────────
# Identique à celui de test_v0_12_0_seances.py (parties + objectifs avec
# UNIQUE(partie_id, code), fin_cycle, et toutes les tables annexes).

_SCHEMA_TEST = """
CREATE TABLE methodes (
    id       TEXT PRIMARY KEY,
    titre    TEXT NOT NULL DEFAULT '',
    niveau   TEXT NOT NULL DEFAULT '',
    sequence TEXT NOT NULL DEFAULT ''
);
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
CREATE TABLE notions (id TEXT PRIMARY KEY, titre TEXT NOT NULL DEFAULT '');
CREATE TABLE objectif_notions (
    objectif_id TEXT NOT NULL REFERENCES objectifs(id) ON DELETE CASCADE,
    notion_id   TEXT NOT NULL REFERENCES notions(id) ON DELETE CASCADE,
    ordre       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, notion_id)
);
CREATE TABLE exercices (
    id         TEXT PRIMARY KEY,
    serie      TEXT NOT NULL,
    nom        TEXT NOT NULL DEFAULT '',
    niveau     TEXT NOT NULL DEFAULT '',
    sequence   TEXT NOT NULL DEFAULT '',
    num        INTEGER,
    fichier    TEXT NOT NULL DEFAULT '',
    serie_code TEXT NOT NULL DEFAULT ''
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
    """Structure de test plus riche pour les déplacements :

    sn_A (N11/S03) :
      pt_A1 (#1) : ob_A1_01 (Cours, code 01)
                   ob_A1_02 (Calculer, code 02)
                   ob_A1_03 (Représenter, code 03)
      pt_A2 (#2) : ob_A2_11 (Cours bis, code 11)
                   ob_A2_12 (Modéliser, code 12)
      pt_A3 (#3) : (vide, juste pour tester le déplacement vers une partie vide)

    sn_B (N11/S04) : 1 partie pt_B1 avec 1 objectif
      pt_B1 (#1) : ob_B1_01 (Cours, code 01)

    Permet de tester : intra-partie, inter-partie même séquence,
    inter-séquence (refusé), partie vide, conflit Connaître.
    """
    conn.executescript("""
        INSERT INTO cycles (code, nom) VALUES ('C04', 'Cycle 4');
        INSERT INTO themes (id, cycle_code, code, nom) VALUES
            ('th_A', 'C04', 'A', 'Nombres');
        INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id) VALUES
            ('sc_S03', 'C04', 'S03', 3, 'Calcul numérique', 'th_A'),
            ('sc_S04', 'C04', 'S04', 4, 'Calcul mental', 'th_A');
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
            ('sn_A', 'N11', 'S03'),
            ('sn_B', 'N11', 'S04');
        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
            ('pt_A1', 'sn_A', 1),
            ('pt_A2', 'sn_A', 2),
            ('pt_A3', 'sn_A', 3),
            ('pt_B1', 'sn_B', 1);
        INSERT INTO objectifs (id, partie_id, code, nom) VALUES
            ('ob_A1_01', 'pt_A1', '01', 'Cours A1'),
            ('ob_A1_02', 'pt_A1', '02', 'Calculer'),
            ('ob_A1_03', 'pt_A1', '03', 'Représenter'),
            ('ob_A2_11', 'pt_A2', '11', 'Cours A2'),
            ('ob_A2_12', 'pt_A2', '12', 'Modéliser'),
            ('ob_B1_01', 'pt_B1', '01', 'Cours B1');
    """)
    conn.commit()
    return conn


def _codes_par_partie(conn, partie_id):
    """Helper : liste des (id, code) d'une partie, dans l'ordre des codes."""
    return [
        (r["id"], r["code"]) for r in conn.execute(
            "SELECT id, code FROM objectifs WHERE partie_id = ? ORDER BY code",
            (partie_id,),
        ).fetchall()
    ]


# ═════════════════════════════════════════════════════════════════════════════
# 1. Cas nominal : déplacement inter-partie
# ═════════════════════════════════════════════════════════════════════════════

class TestDeplacementInterPartie:
    """Déplacement d'un objectif d'une partie vers une autre, dans la
    même séquence-niveau, avec recalcul automatique des codes des deux
    parties."""

    def test_deplace_obj_03_vers_pt_A2_position_1(self, base):
        """Cas standard : on prend ob_A1_03 (code 03) et on le met juste
        après le Cours de pt_A2 (en position 1, derrière ob_A2_11).

        Attendu :
          pt_A1 : Cours (01), Calculer (02)            — ob_A1_03 retiré
          pt_A2 : Cours (11), Représenter (12), Modéliser (13)
                                       (ex-12 Modéliser passe en 13)
        """
        rep = deplacer_objectif_avec_position(
            base, 'ob_A1_03', 'pt_A2', position_dans_cible=1,
        )
        assert rep['objectif_id'] == 'ob_A1_03'
        assert rep['code_apres'] == '12'
        assert rep['partie_source_id'] == 'pt_A1'
        assert rep['partie_cible_id'] == 'pt_A2'

        assert _codes_par_partie(base, 'pt_A1') == [
            ('ob_A1_01', '01'),
            ('ob_A1_02', '02'),
        ]
        assert _codes_par_partie(base, 'pt_A2') == [
            ('ob_A2_11', '11'),
            ('ob_A1_03', '12'),
            ('ob_A2_12', '13'),
        ]

    def test_deplace_obj_02_vers_pt_A2_fin(self, base):
        """Insertion en queue de la partie cible (position = nb_objs)."""
        rep = deplacer_objectif_avec_position(
            base, 'ob_A1_02', 'pt_A2', position_dans_cible=2,
        )
        assert rep['code_apres'] == '13'
        assert _codes_par_partie(base, 'pt_A2') == [
            ('ob_A2_11', '11'),
            ('ob_A2_12', '12'),
            ('ob_A1_02', '13'),
        ]

    def test_deplace_vers_partie_vide_ok(self, base):
        """Cas pt_A3 vide : l'objectif déplacé devient le seul de la partie.
        Comme pt_A3 n'a pas de Cours, l'objectif prend code '22' (X2 avec
        X = numero - 1 = 2)."""
        rep = deplacer_objectif_avec_position(
            base, 'ob_A1_02', 'pt_A3', position_dans_cible=0,
        )
        assert rep['code_apres'] == '22'
        assert _codes_par_partie(base, 'pt_A3') == [
            ('ob_A1_02', '22'),
        ]

    def test_partie_source_renumerotee_apres_retrait(self, base):
        """Quand on retire ob_A1_02 (au milieu), pt_A1 se réordonne :
        Cours reste en 01, Représenter passe de 03 à 02."""
        deplacer_objectif_avec_position(
            base, 'ob_A1_02', 'pt_A2', position_dans_cible=1,
        )
        assert _codes_par_partie(base, 'pt_A1') == [
            ('ob_A1_01', '01'),
            ('ob_A1_03', '02'),    # ex-03, renuméroté en 02
        ]


# ═════════════════════════════════════════════════════════════════════════════
# 2. Cas intra-partie : équivalent à un réordonnancement pur
# ═════════════════════════════════════════════════════════════════════════════

class TestDeplacementIntraPartie:
    """Si partie_source = partie_cible, on délègue à
    `reordonner_objectifs_dans_partie` qui recalcule les codes."""

    def test_intra_partie_descend_obj_02(self, base):
        """ob_A1_02 (code 02) → position 2 dans pt_A1 (= dernière).
        Attendu : 01, ex-03 (devient 02), ex-02 (devient 03)."""
        rep = deplacer_objectif_avec_position(
            base, 'ob_A1_02', 'pt_A1', position_dans_cible=2,
        )
        assert rep['partie_source_id'] == rep['partie_cible_id'] == 'pt_A1'
        assert rep['code_apres'] == '03'
        assert _codes_par_partie(base, 'pt_A1') == [
            ('ob_A1_01', '01'),
            ('ob_A1_03', '02'),
            ('ob_A1_02', '03'),
        ]

    def test_intra_partie_remonte_obj_03(self, base):
        """ob_A1_03 → position 1. Attendu : 01, ex-03 (en 02), ex-02 (en 03)."""
        deplacer_objectif_avec_position(
            base, 'ob_A1_03', 'pt_A1', position_dans_cible=1,
        )
        assert _codes_par_partie(base, 'pt_A1') == [
            ('ob_A1_01', '01'),
            ('ob_A1_03', '02'),
            ('ob_A1_02', '03'),
        ]


# ═════════════════════════════════════════════════════════════════════════════
# 3. Cas d'erreur : Cours non déplaçable, hors séquence, position invalide
# ═════════════════════════════════════════════════════════════════════════════

class TestRefusCours:
    """L'objectif Connaître/Cours est ancré en position 1 de sa partie
    d'origine — on refuse de le déplacer."""

    def test_refus_deplacer_cours_pt_A1(self, base):
        with pytest.raises(ReordonnancementInvalide) as exc:
            deplacer_objectif_avec_position(
                base, 'ob_A1_01', 'pt_A2', position_dans_cible=1,
            )
        assert exc.value.details.get('code_connaitre') == '01'

    def test_refus_deplacer_cours_pt_A2(self, base):
        """Cours code 11 dans pt_A2."""
        with pytest.raises(ReordonnancementInvalide):
            deplacer_objectif_avec_position(
                base, 'ob_A2_11', 'pt_A1', position_dans_cible=1,
            )

    def test_refus_position_0_si_cours_present_dans_cible(self, base):
        """Tenter de placer ob_A1_02 en position 0 de pt_A2 (qui a déjà
        un Cours en 11) doit échouer."""
        with pytest.raises(ReordonnancementInvalide) as exc:
            deplacer_objectif_avec_position(
                base, 'ob_A1_02', 'pt_A2', position_dans_cible=0,
            )
        assert 'position 0' in str(exc.value).lower()

    def test_position_0_ok_si_cible_sans_cours(self, base):
        """Si la cible n'a pas de Cours, position 0 est valide."""
        rep = deplacer_objectif_avec_position(
            base, 'ob_A1_02', 'pt_A3', position_dans_cible=0,
        )
        assert rep['code_apres'] == '22'  # X2 = 2*1 + offset, X = numero-1 = 2


class TestRefusHorsSequence:

    def test_refus_partie_autre_sequence(self, base):
        """sn_A → sn_B : refusé (cohérent avec reassigner_objectif_a_partie)."""
        with pytest.raises(ReassignationImpossible) as exc:
            deplacer_objectif_avec_position(
                base, 'ob_A1_02', 'pt_B1', position_dans_cible=1,
            )
        assert exc.value.code == 'partie_hors_sequence'


class TestPositionInvalide:

    def test_position_negative(self, base):
        with pytest.raises(ReordonnancementInvalide):
            deplacer_objectif_avec_position(
                base, 'ob_A1_02', 'pt_A2', position_dans_cible=-1,
            )

    def test_position_trop_grande(self, base):
        """pt_A2 a 2 objectifs, position max valide = 2 (queue).
        Position 3 doit échouer."""
        with pytest.raises(ReordonnancementInvalide) as exc:
            deplacer_objectif_avec_position(
                base, 'ob_A1_02', 'pt_A2', position_dans_cible=3,
            )
        assert 'hors bornes' in str(exc.value).lower()


class TestEntitesIntrouvables:

    def test_objectif_inconnu(self, base):
        with pytest.raises(ObjectifIntrouvable):
            deplacer_objectif_avec_position(
                base, 'ob_INEXISTANT', 'pt_A2', position_dans_cible=1,
            )

    def test_partie_cible_inconnue(self, base):
        with pytest.raises(PartieIntrouvable):
            deplacer_objectif_avec_position(
                base, 'ob_A1_02', 'pt_INEXISTANTE', position_dans_cible=0,
            )


# ═════════════════════════════════════════════════════════════════════════════
# 4. Routes HTTP (intégration via le client Flask)
# ═════════════════════════════════════════════════════════════════════════════

class TestRouteDeplacer:
    """Tests d'intégration de la route PATCH /api/v2/objectifs/<id>/deplacer."""

    def test_route_400_sans_partie_cible_id(self, client):
        r = client.patch(
            '/api/v2/objectifs/ob_X/deplacer',
            json={'position_dans_cible': 0},
        )
        assert r.status_code == 400
        assert r.get_json()['code'] == 'partie_cible_id_manquant'

    def test_route_400_sans_position(self, client):
        r = client.patch(
            '/api/v2/objectifs/ob_X/deplacer',
            json={'partie_cible_id': 'pt_X'},
        )
        assert r.status_code == 400
        assert r.get_json()['code'] == 'position_invalide'

    def test_route_400_position_pas_entiere(self, client):
        r = client.patch(
            '/api/v2/objectifs/ob_X/deplacer',
            json={'partie_cible_id': 'pt_X', 'position_dans_cible': 'abc'},
        )
        assert r.status_code == 400

    def test_route_404_objectif_inconnu(self, client, store):
        r = client.patch(
            '/api/v2/objectifs/ob_inconnu/deplacer',
            json={'partie_cible_id': 'pt_X', 'position_dans_cible': 0},
        )
        # ObjectifIntrouvable → V2EditionErreur → mappé via _erreur, code 404 attendu
        assert r.status_code == 404
