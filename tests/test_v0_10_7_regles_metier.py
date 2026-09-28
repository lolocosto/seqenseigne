"""tests/test_v0_10_7_regles_metier.py — v0.10.7

Tests pour les nouvelles règles métier :
  1. Notion : scope (notion liée à un objectif de la même séquence
     uniquement, sauf legacy)
  2. Méthode : scope (idem) + cardinalité 1-1 (méthode → un seul obj)
  3. Création de notion/méthode : héritage de niveau/sequence depuis
     le payload
  4. Suppression de la zone Objectifs associés exo : payload
     `objectifs` ignoré côté création/modif d'exercice.
"""

from __future__ import annotations
import sqlite3
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Schéma minimal in-memory ────────────────────────────────────────────────

_SCHEMA_TEST = """
PRAGMA foreign_keys = ON;

CREATE TABLE sequences_par_niveau (
    id TEXT PRIMARY KEY, niveau TEXT, sequence_code TEXT
);
CREATE TABLE sequence_parties (
    id TEXT PRIMARY KEY,
    sequence_par_niveau_id TEXT REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    numero INTEGER
);
CREATE TABLE methodes (
    id TEXT PRIMARY KEY,
    titre TEXT,
    niveau TEXT NOT NULL DEFAULT '',
    sequence TEXT NOT NULL DEFAULT '',
    num_objectif TEXT NOT NULL DEFAULT ''
);
CREATE TABLE notions (
    id TEXT PRIMARY KEY,
    titre TEXT,
    niveau TEXT NOT NULL DEFAULT '',
    sequence TEXT NOT NULL DEFAULT ''
);
CREATE TABLE objectifs (
    id TEXT PRIMARY KEY,
    partie_id TEXT REFERENCES sequence_parties(id) ON DELETE CASCADE,
    code TEXT,
    nom TEXT,
    methode_id TEXT REFERENCES methodes(id) ON DELETE SET NULL,
    critere_F TEXT NOT NULL DEFAULT '',
    critere_A TEXT NOT NULL DEFAULT '',
    critere_E TEXT NOT NULL DEFAULT '',
    fin_cycle TEXT NOT NULL DEFAULT 'N'
);
CREATE TABLE objectif_notions (
    objectif_id TEXT REFERENCES objectifs(id) ON DELETE CASCADE,
    notion_id TEXT REFERENCES notions(id) ON DELETE CASCADE,
    ordre INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, notion_id)
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA_TEST)
    # Données de base : N11/S03 (deux parties, deux objectifs avec
    # méthodes scope-cohérentes) et N11/S05 (autre séquence).
    c.executescript("""
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
            ('sn_S03', 'N11', 'S03'),
            ('sn_S05', 'N11', 'S05');
        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
            ('pt_S03_1', 'sn_S03', 1),
            ('pt_S03_2', 'sn_S03', 2),
            ('pt_S05_1', 'sn_S05', 1);
        INSERT INTO methodes (id, titre, niveau, sequence) VALUES
            ('me_S03_a', 'Méthode A S03', 'N11', 'S03'),
            ('me_S03_b', 'Méthode B S03', 'N11', 'S03'),
            ('me_S05_a', 'Méthode A S05', 'N11', 'S05'),
            ('me_legacy', 'Sans scope',   '',   '');
        INSERT INTO notions (id, titre, niveau, sequence) VALUES
            ('no_S03_a', 'Notion A S03', 'N11', 'S03'),
            ('no_S03_b', 'Notion B S03', 'N11', 'S03'),
            ('no_S05_a', 'Notion A S05', 'N11', 'S05'),
            ('no_legacy','Sans scope',   '',   '');
        INSERT INTO objectifs (id, partie_id, code, nom, methode_id) VALUES
            ('ob_S03_01', 'pt_S03_1', '01', 'Cours',     NULL),
            ('ob_S03_02', 'pt_S03_1', '02', 'Calculer A', NULL),
            ('ob_S03_12', 'pt_S03_2', '12', 'Calculer B', NULL),
            ('ob_S05_01', 'pt_S05_1', '01', 'Cours',     NULL);
    """)
    c.commit()
    yield c
    c.close()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Notion : scope séquence
# ═══════════════════════════════════════════════════════════════════════════


from services.v2_edition import (
    ajouter_notion_objectif, NotionHorsSequence,
    modifier_methode_objectif, MethodeHorsSequence, MethodeDejaLiee,
)


class TestNotionScope:
    def test_meme_sequence_accepte(self, conn):
        """Notion N11/S03 → objectif N11/S03 : OK."""
        rep = ajouter_notion_objectif(conn, 'ob_S03_02', 'no_S03_a')
        assert any(n['id'] == 'no_S03_a' for n in rep['notions'])

    def test_autre_sequence_refuse(self, conn):
        """Notion N11/S05 → objectif N11/S03 : NotionHorsSequence."""
        with pytest.raises(NotionHorsSequence):
            ajouter_notion_objectif(conn, 'ob_S03_02', 'no_S05_a')

    def test_legacy_sans_scope_accepte(self, conn):
        """Notion sans (niveau, sequence) → tolérance fallback."""
        rep = ajouter_notion_objectif(conn, 'ob_S03_02', 'no_legacy')
        assert any(n['id'] == 'no_legacy' for n in rep['notions'])

    def test_plusieurs_obj_meme_sequence_accepte(self, conn):
        """Cardinalité M-N : une notion peut être liée à plusieurs
        objectifs DE LA MEME séquence."""
        ajouter_notion_objectif(conn, 'ob_S03_02', 'no_S03_a')
        # Lier la même notion à un autre obj de S03 → OK
        rep = ajouter_notion_objectif(conn, 'ob_S03_12', 'no_S03_a')
        assert any(n['id'] == 'no_S03_a' for n in rep['notions'])


# ═══════════════════════════════════════════════════════════════════════════
# 2. Méthode : scope séquence + cardinalité 1-1
# ═══════════════════════════════════════════════════════════════════════════


class TestMethodeScope:
    def test_meme_sequence_accepte(self, conn):
        rep = modifier_methode_objectif(conn, 'ob_S03_02', 'me_S03_a')
        assert rep['methode_id'] == 'me_S03_a'

    def test_autre_sequence_refuse(self, conn):
        with pytest.raises(MethodeHorsSequence):
            modifier_methode_objectif(conn, 'ob_S03_02', 'me_S05_a')

    def test_legacy_sans_scope_accepte(self, conn):
        rep = modifier_methode_objectif(conn, 'ob_S03_02', 'me_legacy')
        assert rep['methode_id'] == 'me_legacy'


class TestMethodeCardinalite:
    def test_lier_meme_methode_a_deux_obj_refuse(self, conn):
        """Cardinalité 1-1 méthode → obj : me_S03_a ne peut être liée
        qu'à un seul objectif."""
        modifier_methode_objectif(conn, 'ob_S03_02', 'me_S03_a')
        with pytest.raises(MethodeDejaLiee):
            modifier_methode_objectif(conn, 'ob_S03_12', 'me_S03_a')

    def test_idempotent(self, conn):
        """Réattacher la même méthode au même objectif est OK."""
        modifier_methode_objectif(conn, 'ob_S03_02', 'me_S03_a')
        rep = modifier_methode_objectif(conn, 'ob_S03_02', 'me_S03_a')
        assert rep['methode_id'] == 'me_S03_a'

    def test_detacher_puis_rattacher_ok(self, conn):
        """Cardinalité respectée si on détache d'abord."""
        modifier_methode_objectif(conn, 'ob_S03_02', 'me_S03_a')
        modifier_methode_objectif(conn, 'ob_S03_02', None)
        rep = modifier_methode_objectif(conn, 'ob_S03_12', 'me_S03_a')
        assert rep['methode_id'] == 'me_S03_a'


# ═══════════════════════════════════════════════════════════════════════════
# 3. Service atomes : héritage niveau/sequence à la création
# ═══════════════════════════════════════════════════════════════════════════


from services.atomes import (
    creer_notion, modifier_notion,
    creer_methode, modifier_methode,
    creer_exercice, modifier_exercice,
)


class TestCreerAtomesAvecScope:
    def test_creer_notion_avec_scope(self):
        liste, n, err = creer_notion([], {
            'titre': 'Ma notion', 'niveau': 'N11', 'sequence': 'S03',
        })
        assert err is None
        assert n['niveau'] == 'N11'
        assert n['sequence'] == 'S03'

    def test_creer_notion_sans_scope_legacy(self):
        liste, n, err = creer_notion([], {'titre': 'Legacy'})
        assert err is None
        assert n['niveau'] == ''
        assert n['sequence'] == ''

    def test_creer_methode_avec_scope(self):
        liste, m, err = creer_methode([], {
            'titre': 'Ma méthode', 'niveau': 'N11', 'sequence': 'S03',
        })
        assert err is None
        assert m['niveau'] == 'N11'
        assert m['sequence'] == 'S03'

    def test_modifier_notion_pose_scope(self):
        liste, n, _ = creer_notion([], {'titre': 'X'})
        liste, n, err = modifier_notion(liste, n['id'], {
            'niveau': 'N11', 'sequence': 'S03',
        })
        assert err is None
        assert n['niveau'] == 'N11'

    def test_modifier_methode_pose_scope(self):
        liste, m, _ = creer_methode([], {'titre': 'X'})
        liste, m, err = modifier_methode(liste, m['id'], {
            'niveau': 'N11', 'sequence': 'S03',
        })
        assert err is None
        assert m['sequence'] == 'S03'


# ═══════════════════════════════════════════════════════════════════════════
# 4. Exercice : champ `objectifs` ignoré (zone supprimée v0.10.7)
# ═══════════════════════════════════════════════════════════════════════════


class TestExerciceObjectifsRetire:
    def test_creer_exercice_objectifs_ignore(self):
        """Le champ `objectifs` envoyé dans le payload est forcé à []."""
        liste, e, err = creer_exercice([], {
            'serie': 'fondamental',
            'enonce': 'X', 'corrige': 'Y',
            'objectifs': ['obj_legacy_42'],  # devrait être ignoré
        })
        assert err is None
        assert e['objectifs'] == []

    def test_modifier_exercice_objectifs_non_modifiable(self):
        """Le champ `objectifs` n'est plus dans la liste des champs
        modifiables."""
        liste, e, _ = creer_exercice([], {
            'serie': 'fondamental', 'enonce': 'X', 'corrige': 'Y',
        })
        liste, e, err = modifier_exercice(liste, e['id'], {
            'objectifs': ['nouveau_obj_id'],  # devrait être ignoré
            'titre': 'Nouveau nom',  # celui-là OK
        })
        assert err is None
        assert e['objectifs'] == []  # non modifié
        assert e['titre'] == 'Nouveau nom'  # modifié
