"""tests/test_v0_13_6_1_cartes_automatisme.py — v0.13.6.1 (refondu en v0.13.6.1.2)

Tests de l'atelier Cartes d'automatisme :
- Service métier (CRUD, validation pédagogique, lien notion/méthode,
  workflow, config)
- Routes REST (codes HTTP, payloads, gestion d'erreurs)

Refonte v0.13.6.1.2 :
- TYPES_PEDAGO élargi à 5 valeurs (definition/propriete/reconnaissance/
  calcul/procedure)
- Lien direct vers notion OU méthode (lien_type + lien_id), plus de table
  carte_objectifs
- Sélecteurs notions-disponibles / methodes-disponibles
"""
from __future__ import annotations
import sqlite3

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Schéma BDD minimal pour les tests d'isolation (service métier)
# ─────────────────────────────────────────────────────────────────────────────

_SCHEMA_TEST = """
-- v0.13.6.8.2 : ajout de etats_edition + mtime sur notions/methodes
-- pour supporter le mécanisme unifié changer_etat_atome qui consulte
-- cette table et met à jour mtime sur la table cible.
CREATE TABLE etats_edition (
    code TEXT PRIMARY KEY, nom TEXT, ordre INTEGER, est_final INTEGER
);
INSERT INTO etats_edition VALUES
    ('en_cours', 'En cours', 10, 0),
    ('valide',   'Validé',   20, 1);

CREATE TABLE sequences_par_niveau (
    id            TEXT PRIMARY KEY,
    niveau        TEXT NOT NULL,
    sequence_code TEXT NOT NULL,
    UNIQUE (niveau, sequence_code)
);
CREATE TABLE sequence_parties (
    id                     TEXT PRIMARY KEY,
    sequence_par_niveau_id TEXT NOT NULL
                           REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    numero                 INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE notions (
    id               TEXT PRIMARY KEY,
    titre            TEXT NOT NULL DEFAULT '',
    corps            TEXT NOT NULL DEFAULT '',
    niveau           TEXT NOT NULL,
    sequence         TEXT NOT NULL,
    num_connaissance TEXT,
    etat_code        TEXT NOT NULL DEFAULT 'en_cours',
    mtime            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE methodes (
    id            TEXT PRIMARY KEY,
    titre         TEXT NOT NULL DEFAULT '',
    corps         TEXT NOT NULL DEFAULT '',
    niveau        TEXT NOT NULL,
    sequence      TEXT NOT NULL,
    num_methode   INTEGER,
    num_objectif  TEXT,
    etat_code     TEXT NOT NULL DEFAULT 'en_cours',
    mtime         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE cartes_automatisme (
    id            TEXT PRIMARY KEY,
    niveau        TEXT NOT NULL,
    sequence      TEXT NOT NULL,
    num           INTEGER NOT NULL,
    type_pedago   TEXT NOT NULL DEFAULT 'definition',
    type_tech     TEXT NOT NULL DEFAULT 'fixe',
    titre         TEXT NOT NULL DEFAULT '',  -- v0.13.6.15 : renommé depuis `nom`
    lien_type     TEXT,
    lien_id       TEXT,
    recto         TEXT NOT NULL DEFAULT '',
    verso         TEXT NOT NULL DEFAULT '',
    variables     TEXT NOT NULL DEFAULT '',
    etat_code     TEXT NOT NULL DEFAULT 'en_cours',
    ordre         INTEGER NOT NULL DEFAULT 1,
    mtime         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (niveau, sequence, num),
    CHECK  (type_pedago IN ('definition', 'propriete', 'reconnaissance',
                            'calcul', 'procedure')),
    CHECK  (type_tech IN ('fixe', 'parametree')),
    CHECK  (etat_code IN ('en_cours', 'valide')),
    CHECK  (num > 0 AND num < 100),
    CHECK  ((lien_type IS NULL AND lien_id IS NULL)
            OR (lien_type IN ('notion', 'methode')
                AND lien_id IS NOT NULL))
);
-- v0.13.6.13 : tables nécessaires au nouveau modèle de lien carte → objectif
CREATE TABLE objectifs (
    id          TEXT PRIMARY KEY,
    methode_id  TEXT REFERENCES methodes(id) ON DELETE CASCADE,
    partie_id   TEXT,
    code        TEXT,
    nom         TEXT
);
CREATE TABLE objectif_notions (
    objectif_id TEXT NOT NULL
                REFERENCES objectifs(id) ON DELETE CASCADE,
    notion_id   TEXT NOT NULL
                REFERENCES notions(id) ON DELETE CASCADE,
    PRIMARY KEY (objectif_id, notion_id)
);
CREATE TABLE objectif_cartes (
    objectif_id TEXT NOT NULL
                REFERENCES objectifs(id) ON DELETE CASCADE,
    carte_id    TEXT NOT NULL
                REFERENCES cartes_automatisme(id) ON DELETE CASCADE,
    ordre       INTEGER NOT NULL DEFAULT 0,
    mtime       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (objectif_id, carte_id)
);
CREATE TABLE cartes_atelier_config (
    cle    TEXT PRIMARY KEY,
    valeur TEXT NOT NULL DEFAULT ''
);
"""


@pytest.fixture
def conn(tmp_path):
    """BDD vierge avec le schéma minimal."""
    db = tmp_path / "test.db"
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(_SCHEMA_TEST)
    return c


@pytest.fixture
def conn_avec_atomes(conn):
    """BDD avec une séquence N10/S01 contenant 2 notions et 2 méthodes.

    v0.13.6.13 — Ajoute aussi des objectifs liés aux atomes pour que
    la dérivation automatique objectif_ids dans creer_carte / modifier_carte
    fonctionne (la validation pédagogique exige désormais une liaison
    objectif_cartes non vide).
    """
    conn.execute(
        "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
        "VALUES ('spn1', 'N10', 'S01')"
    )
    conn.execute(
        "INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
        "VALUES ('sp1', 'spn1', 1)"
    )
    # Notions
    conn.execute(
        "INSERT INTO notions (id, niveau, sequence, num_connaissance, titre) "
        "VALUES ('no_a', 'N10', 'S01', '01', 'Connaissance A')"
    )
    conn.execute(
        "INSERT INTO notions (id, niveau, sequence, num_connaissance, titre) "
        "VALUES ('no_b', 'N10', 'S01', '02', 'Connaissance B')"
    )
    # Méthodes
    conn.execute(
        "INSERT INTO methodes (id, niveau, sequence, num_methode, titre) "
        "VALUES ('me_a', 'N10', 'S01', 1, 'Méthode A')"
    )
    conn.execute(
        "INSERT INTO methodes (id, niveau, sequence, num_methode, titre) "
        "VALUES ('me_b', 'N10', 'S01', 2, 'Méthode B')"
    )
    # v0.13.6.13 — Objectifs liés aux atomes (1 par méthode + 1 par notion)
    conn.execute(
        "INSERT INTO objectifs (id, methode_id, partie_id, code, nom) "
        "VALUES ('ob_a', 'me_a', 'sp1', '01', 'Objectif méthode A')"
    )
    conn.execute(
        "INSERT INTO objectifs (id, methode_id, partie_id, code, nom) "
        "VALUES ('ob_b', 'me_b', 'sp1', '02', 'Objectif méthode B')"
    )
    conn.execute(
        "INSERT INTO objectifs (id, methode_id, partie_id, code, nom) "
        "VALUES ('ob_n_a', NULL, 'sp1', '03', 'Objectif notion A')"
    )
    conn.execute(
        "INSERT INTO objectifs (id, methode_id, partie_id, code, nom) "
        "VALUES ('ob_n_b', NULL, 'sp1', '04', 'Objectif notion B')"
    )
    conn.execute(
        "INSERT INTO objectif_notions (objectif_id, notion_id) "
        "VALUES ('ob_n_a', 'no_a')"
    )
    conn.execute(
        "INSERT INTO objectif_notions (objectif_id, notion_id) "
        "VALUES ('ob_n_b', 'no_b')"
    )
    conn.commit()
    return conn


# ═════════════════════════════════════════════════════════════════════════════
# CRUD principal
# ═════════════════════════════════════════════════════════════════════════════


class TestCreerCarte:
    def test_creation_minimale_sans_lien(self, conn):
        # v0.13.6.1.2 : le lien est optionnel à la création
        from services.cartes_automatisme import creer_carte
        carte = creer_carte(conn, niveau='N10', sequence='S01')
        assert carte['niveau'] == 'N10'
        assert carte['sequence'] == 'S01'
        assert carte['num'] == 1
        assert carte['type_pedago'] == 'definition'  # défaut v0.13.6.1.2
        assert carte['type_tech'] == 'fixe'
        assert carte['lien_type'] is None
        assert carte['lien_id'] is None

    def test_creation_avec_lien_notion(self, conn_avec_atomes):
        from services.cartes_automatisme import creer_carte
        carte = creer_carte(
            conn_avec_atomes, niveau='N10', sequence='S01',
            type_pedago='propriete',
            lien_type='notion', lien_id='no_a',
            recto='Q', verso='R',
        )
        assert carte['lien_type'] == 'notion'
        assert carte['lien_id'] == 'no_a'
        assert carte['type_pedago'] == 'propriete'

    def test_creation_avec_lien_methode(self, conn_avec_atomes):
        from services.cartes_automatisme import creer_carte
        carte = creer_carte(
            conn_avec_atomes, niveau='N10', sequence='S01',
            type_pedago='procedure',
            lien_type='methode', lien_id='me_a',
        )
        assert carte['lien_type'] == 'methode'
        assert carte['lien_id'] == 'me_a'

    def test_creation_avec_tous_les_types_pedago(self, conn):
        """v0.13.6.1.2 : 5 valeurs autorisées."""
        from services.cartes_automatisme import creer_carte
        for i, tp in enumerate(['definition', 'propriete', 'reconnaissance',
                                 'calcul', 'procedure'], start=1):
            carte = creer_carte(conn, niveau='N10', sequence='S01',
                                num=i, type_pedago=tp)
            assert carte['type_pedago'] == tp

    def test_creation_type_pedago_v0136_calcul_mental_rejete(self, conn):
        """L'ancien 'calcul_mental' de v0.13.6.1 doit être rejeté."""
        from services.cartes_automatisme import (
            creer_carte, TypePedagoInvalide
        )
        with pytest.raises(TypePedagoInvalide):
            creer_carte(conn, niveau='N10', sequence='S01',
                        type_pedago='calcul_mental')

    def test_num_auto_increment(self, conn):
        from services.cartes_automatisme import creer_carte
        c1 = creer_carte(conn, niveau='N10', sequence='S01')
        c2 = creer_carte(conn, niveau='N10', sequence='S01')
        assert (c1['num'], c2['num']) == (1, 2)

    def test_num_independant_par_sequence(self, conn):
        from services.cartes_automatisme import creer_carte
        c_s1 = creer_carte(conn, niveau='N10', sequence='S01')
        c_s2 = creer_carte(conn, niveau='N10', sequence='S02')
        assert c_s1['num'] == 1
        assert c_s2['num'] == 1

    def test_num_deja_utilise_leve(self, conn):
        from services.cartes_automatisme import creer_carte, NumDejaUtilise
        creer_carte(conn, niveau='N10', sequence='S01', num=5)
        with pytest.raises(NumDejaUtilise) as e:
            creer_carte(conn, niveau='N10', sequence='S01', num=5)
        assert e.value.code == 'num_deja_utilise'

    def test_num_invalide_leve(self, conn):
        from services.cartes_automatisme import creer_carte, NumInvalide
        with pytest.raises(NumInvalide):
            creer_carte(conn, niveau='N10', sequence='S01', num=0)
        with pytest.raises(NumInvalide):
            creer_carte(conn, niveau='N10', sequence='S01', num=100)

    def test_type_pedago_invalide_leve(self, conn):
        from services.cartes_automatisme import creer_carte, TypePedagoInvalide
        with pytest.raises(TypePedagoInvalide):
            creer_carte(conn, niveau='N10', sequence='S01',
                        type_pedago='inexistant')

    def test_lien_type_invalide_leve(self, conn):
        from services.cartes_automatisme import creer_carte, LienTypeInvalide
        with pytest.raises(LienTypeInvalide) as e:
            creer_carte(conn, niveau='N10', sequence='S01',
                        lien_type='exercice', lien_id='ex_x')
        assert e.value.code == 'lien_type_invalide'

    def test_lien_introuvable_leve(self, conn_avec_atomes):
        from services.cartes_automatisme import creer_carte, LienIntrouvable
        with pytest.raises(LienIntrouvable) as e:
            creer_carte(conn_avec_atomes, niveau='N10', sequence='S01',
                        lien_type='notion', lien_id='no_inexistant')
        assert e.value.code == 'lien_introuvable'

    def test_lien_incoherent_type_seul_leve(self, conn):
        from services.cartes_automatisme import creer_carte, LienIncoherent
        with pytest.raises(LienIncoherent):
            creer_carte(conn, niveau='N10', sequence='S01',
                        lien_type='notion', lien_id=None)

    def test_lien_incoherent_id_seul_leve(self, conn):
        from services.cartes_automatisme import creer_carte, LienIncoherent
        with pytest.raises(LienIncoherent):
            creer_carte(conn, niveau='N10', sequence='S01',
                        lien_type=None, lien_id='no_a')

    def test_lien_vides_acceptes(self, conn):
        from services.cartes_automatisme import creer_carte
        # Les deux NULL → OK
        carte = creer_carte(conn, niveau='N10', sequence='S01',
                            lien_type=None, lien_id=None)
        assert carte['lien_type'] is None
        # Les deux '' → normalisés en NULL → OK
        carte2 = creer_carte(conn, niveau='N10', sequence='S01',
                             lien_type='', lien_id='')
        assert carte2['lien_type'] is None


class TestLireCarte:
    def test_lire_existante(self, conn):
        from services.cartes_automatisme import creer_carte, lire_carte
        c = creer_carte(conn, niveau='N10', sequence='S01', recto='r')
        relu = lire_carte(conn, c['id'])
        assert relu['id'] == c['id']
        assert relu['recto'] == 'r'

    def test_lire_inexistante_leve(self, conn):
        from services.cartes_automatisme import lire_carte, CarteIntrouvable
        with pytest.raises(CarteIntrouvable) as e:
            lire_carte(conn, 'crt_inexistant')
        assert e.value.code == 'carte_introuvable'


class TestListerCartes:
    def test_liste_vide(self, conn):
        from services.cartes_automatisme import lister_cartes
        assert lister_cartes(conn, niveau='N10', sequence='S01') == []

    def test_liste_filtree(self, conn):
        from services.cartes_automatisme import creer_carte, lister_cartes
        creer_carte(conn, niveau='N10', sequence='S01', titre='a')
        creer_carte(conn, niveau='N10', sequence='S01', titre='b')
        creer_carte(conn, niveau='N10', sequence='S02', titre='c')
        cartes = lister_cartes(conn, niveau='N10', sequence='S01')
        assert len(cartes) == 2

    def test_liste_triee_par_ordre(self, conn):
        from services.cartes_automatisme import creer_carte, lister_cartes
        creer_carte(conn, niveau='N10', sequence='S01', titre='A', ordre=3)
        creer_carte(conn, niveau='N10', sequence='S01', titre='B', ordre=1)
        cartes = lister_cartes(conn, niveau='N10', sequence='S01')
        assert [c['titre'] for c in cartes] == ['B', 'A']


class TestModifierCarte:
    def test_modification_partielle(self, conn):
        from services.cartes_automatisme import creer_carte, modifier_carte
        c = creer_carte(conn, niveau='N10', sequence='S01', recto='old')
        nouvelle = modifier_carte(conn, c['id'], recto='new')
        assert nouvelle['recto'] == 'new'
        assert nouvelle['niveau'] == 'N10'

    def test_modification_lien_couple(self, conn_avec_atomes):
        """v0.13.6.1.2 : on doit pouvoir modifier le lien notion → autre notion."""
        from services.cartes_automatisme import creer_carte, modifier_carte
        c = creer_carte(conn_avec_atomes, niveau='N10', sequence='S01',
                        lien_type='notion', lien_id='no_a')
        nouvelle = modifier_carte(conn_avec_atomes, c['id'],
                                   lien_type='notion', lien_id='no_b')
        assert nouvelle['lien_id'] == 'no_b'

    def test_modification_lien_notion_vers_methode(self, conn_avec_atomes):
        """v0.13.6.1.2 : on peut basculer notion → méthode."""
        from services.cartes_automatisme import creer_carte, modifier_carte
        c = creer_carte(conn_avec_atomes, niveau='N10', sequence='S01',
                        lien_type='notion', lien_id='no_a')
        nouvelle = modifier_carte(conn_avec_atomes, c['id'],
                                   lien_type='methode', lien_id='me_a')
        assert nouvelle['lien_type'] == 'methode'
        assert nouvelle['lien_id'] == 'me_a'

    def test_modification_lien_seul_id_change_revalidation(self, conn_avec_atomes):
        """v0.13.6.1.2 : si on change seulement lien_id, le service
        récupère lien_type depuis la BDD pour valider la cohérence."""
        from services.cartes_automatisme import creer_carte, modifier_carte
        c = creer_carte(conn_avec_atomes, niveau='N10', sequence='S01',
                        lien_type='notion', lien_id='no_a')
        # Changer juste lien_id (sans lien_type) → service utilise
        # lien_type existant ('notion') et valide que 'no_b' existe en notions
        nouvelle = modifier_carte(conn_avec_atomes, c['id'],
                                   lien_id='no_b')
        assert nouvelle['lien_id'] == 'no_b'
        assert nouvelle['lien_type'] == 'notion'

    def test_modification_champ_inconnu_leve(self, conn):
        from services.cartes_automatisme import (
            creer_carte, modifier_carte, ChampInvalide
        )
        c = creer_carte(conn, niveau='N10', sequence='S01')
        with pytest.raises(ChampInvalide):
            modifier_carte(conn, c['id'], niveau='N11')

    def test_modification_carte_inexistante_leve(self, conn):
        from services.cartes_automatisme import (
            modifier_carte, CarteIntrouvable
        )
        with pytest.raises(CarteIntrouvable):
            modifier_carte(conn, 'crt_xyz', recto='r')


class TestSupprimerCarte:
    def test_suppression_simple(self, conn):
        from services.cartes_automatisme import (
            creer_carte, supprimer_carte, lire_carte, CarteIntrouvable
        )
        c = creer_carte(conn, niveau='N10', sequence='S01')
        supprimer_carte(conn, c['id'])
        with pytest.raises(CarteIntrouvable):
            lire_carte(conn, c['id'])

    def test_suppression_inexistante_leve(self, conn):
        from services.cartes_automatisme import (
            supprimer_carte, CarteIntrouvable
        )
        with pytest.raises(CarteIntrouvable):
            supprimer_carte(conn, 'crt_xyz')


# ═════════════════════════════════════════════════════════════════════════════
# Sélecteurs notions/méthodes disponibles
# ═════════════════════════════════════════════════════════════════════════════


class TestSelecteurs:
    def test_lister_notions(self, conn_avec_atomes):
        from services.cartes_automatisme import lister_notions_disponibles
        notions = lister_notions_disponibles(conn_avec_atomes, 'N10', 'S01')
        assert len(notions) == 2
        assert notions[0]['titre'] == 'Connaissance A'
        assert notions[0]['num_connaissance'] == '01'

    def test_lister_methodes(self, conn_avec_atomes):
        from services.cartes_automatisme import lister_methodes_disponibles
        methodes = lister_methodes_disponibles(conn_avec_atomes, 'N10', 'S01')
        assert len(methodes) == 2
        assert methodes[0]['titre'] == 'Méthode A'
        assert methodes[0]['num_methode'] == 1

    def test_lire_lien_label_notion(self, conn_avec_atomes):
        from services.cartes_automatisme import lire_lien_label
        label = lire_lien_label(conn_avec_atomes, 'notion', 'no_a')
        assert label == 'N01 — Connaissance A'

    def test_lire_lien_label_methode(self, conn_avec_atomes):
        from services.cartes_automatisme import lire_lien_label
        label = lire_lien_label(conn_avec_atomes, 'methode', 'me_a')
        assert label == 'M1 — Méthode A'

    def test_lire_lien_label_null(self, conn_avec_atomes):
        from services.cartes_automatisme import lire_lien_label
        assert lire_lien_label(conn_avec_atomes, None, None) is None


# ═════════════════════════════════════════════════════════════════════════════
# Workflow valider / dévalider
# ═════════════════════════════════════════════════════════════════════════════


class TestValiderDevalider:
    """v0.13.6.8.2 — Le workflow valider/dévalider de la carte passe
    maintenant par le mécanisme unifié des états d'édition :
        services.etats_edition.changer_etat_atome(conn, 'carte', id, état)

    La validation pédagogique (recto/verso/lien/variables) est conservée
    sous forme de hook, levant
        services.etats_edition.ValidationPedagogiqueErreur
    au lieu de l'ancienne services.cartes_automatisme.ValidationPedagogiqueErreur
    (supprimée).

    Les anciennes erreurs DejaValide et DejaEnCours ont été supprimées :
    le nouveau mécanisme n'a pas de garde sur la « transition vers l'état
    déjà courant » (un UPDATE re-validant a juste un coût négligeable).
    """

    def test_valider_complet(self, conn_avec_atomes):
        """recto + verso + lien → validable."""
        from services.cartes_automatisme import creer_carte, lire_carte
        from services.etats_edition import changer_etat_atome
        c = creer_carte(conn_avec_atomes, niveau='N10', sequence='S01',
                        recto='Q', verso='R',
                        lien_type='notion', lien_id='no_a')
        changer_etat_atome(conn_avec_atomes, 'carte', c['id'], 'valide')
        validee = lire_carte(conn_avec_atomes, c['id'])
        assert validee['etat_code'] == 'valide'

    def test_valider_sans_lien_leve(self, conn):
        """v0.13.6.1.2 : la validation exige un lien.
        v0.13.6.8.2 : exception levée = ValidationPedagogiqueErreur de
        etats_edition (et non plus celle de cartes_automatisme).
        v0.13.6.13  : la raison parle désormais d'objectif (table de
        liaison objectif_cartes) au lieu de notion/méthode."""
        from services.cartes_automatisme import creer_carte
        from services.etats_edition import (
            changer_etat_atome, ValidationPedagogiqueErreur,
        )
        c = creer_carte(conn, niveau='N10', sequence='S01',
                        recto='Q', verso='R')
        with pytest.raises(ValidationPedagogiqueErreur) as e:
            changer_etat_atome(conn, 'carte', c['id'], 'valide')
        raisons = e.value.details['raisons']
        assert any('objectif' in r.lower() for r in raisons)

    def test_valider_sans_recto_leve(self, conn_avec_atomes):
        from services.cartes_automatisme import creer_carte
        from services.etats_edition import (
            changer_etat_atome, ValidationPedagogiqueErreur,
        )
        c = creer_carte(conn_avec_atomes, niveau='N10', sequence='S01',
                        recto='', verso='R',
                        lien_type='notion', lien_id='no_a')
        with pytest.raises(ValidationPedagogiqueErreur) as e:
            changer_etat_atome(conn_avec_atomes, 'carte', c['id'], 'valide')
        assert any('recto' in r.lower() for r in e.value.details['raisons'])

    def test_valider_parametree_sans_variables_leve(self, conn_avec_atomes):
        from services.cartes_automatisme import creer_carte
        from services.etats_edition import (
            changer_etat_atome, ValidationPedagogiqueErreur,
        )
        c = creer_carte(conn_avec_atomes, niveau='N10', sequence='S01',
                        type_tech='parametree',
                        recto='Q', verso='R', variables='',
                        lien_type='notion', lien_id='no_a')
        with pytest.raises(ValidationPedagogiqueErreur) as e:
            changer_etat_atome(conn_avec_atomes, 'carte', c['id'], 'valide')
        assert any('variables' in r.lower() for r in e.value.details['raisons'])

    def test_valider_deux_fois_idempotent(self, conn_avec_atomes):
        """v0.13.6.8.2 — Plus de DejaValide : appeler changer_etat_atome
        sur un atome déjà à l'état cible est idempotent (refait l'UPDATE
        + le hook, mais ne lève rien si le hook passe)."""
        from services.cartes_automatisme import creer_carte, lire_carte
        from services.etats_edition import changer_etat_atome
        c = creer_carte(conn_avec_atomes, niveau='N10', sequence='S01',
                        recto='Q', verso='R',
                        lien_type='notion', lien_id='no_a')
        changer_etat_atome(conn_avec_atomes, 'carte', c['id'], 'valide')
        # Second appel idempotent
        changer_etat_atome(conn_avec_atomes, 'carte', c['id'], 'valide')
        assert lire_carte(conn_avec_atomes, c['id'])['etat_code'] == 'valide'

    def test_devalider(self, conn_avec_atomes):
        from services.cartes_automatisme import creer_carte, lire_carte
        from services.etats_edition import changer_etat_atome
        c = creer_carte(conn_avec_atomes, niveau='N10', sequence='S01',
                        recto='Q', verso='R',
                        lien_type='notion', lien_id='no_a')
        changer_etat_atome(conn_avec_atomes, 'carte', c['id'], 'valide')
        changer_etat_atome(conn_avec_atomes, 'carte', c['id'], 'en_cours')
        assert lire_carte(conn_avec_atomes, c['id'])['etat_code'] == 'en_cours'

    def test_devalider_idempotent(self, conn):
        """v0.13.6.8.2 — Plus de DejaEnCours : passer à 'en_cours' un
        atome déjà 'en_cours' est idempotent (pas de hook pour 'en_cours',
        donc juste UPDATE sans effet)."""
        from services.cartes_automatisme import creer_carte, lire_carte
        from services.etats_edition import changer_etat_atome
        c = creer_carte(conn, niveau='N10', sequence='S01')
        # Création : état par défaut 'en_cours'
        assert lire_carte(conn, c['id'])['etat_code'] == 'en_cours'
        # Re-passer en 'en_cours' : aucun effet, aucune erreur
        changer_etat_atome(conn, 'carte', c['id'], 'en_cours')
        assert lire_carte(conn, c['id'])['etat_code'] == 'en_cours'

    def test_mtime_mis_a_jour_au_changement_etat(self, conn_avec_atomes):
        """v0.13.6.8.2 — Le mtime est mis à jour à chaque changement d'état,
        utile pour le mécanisme futur de figeage des référentiels."""
        from services.cartes_automatisme import creer_carte, lire_carte
        from services.etats_edition import changer_etat_atome
        import time
        c = creer_carte(conn_avec_atomes, niveau='N10', sequence='S01',
                        recto='Q', verso='R',
                        lien_type='notion', lien_id='no_a')
        mtime_initial = lire_carte(conn_avec_atomes, c['id'])['mtime']
        time.sleep(1.1)  # SQLite CURRENT_TIMESTAMP a une résolution seconde
        changer_etat_atome(conn_avec_atomes, 'carte', c['id'], 'valide')
        mtime_apres = lire_carte(conn_avec_atomes, c['id'])['mtime']
        assert mtime_apres > mtime_initial


# ═════════════════════════════════════════════════════════════════════════════
# Configuration atelier
# ═════════════════════════════════════════════════════════════════════════════


class TestConfig:
    def test_lecture_defaut(self, conn):
        from services.cartes_automatisme import lire_config
        assert lire_config(conn, 'cartes_param_nb_uniques') == '16'

    def test_modification_puis_lecture(self, conn):
        from services.cartes_automatisme import lire_config, modifier_config
        modifier_config(conn, 'cartes_param_nb_uniques', '32')
        assert lire_config(conn, 'cartes_param_nb_uniques') == '32'

    def test_cle_inconnue_leve(self, conn):
        from services.cartes_automatisme import (
            lire_config, CleConfigInconnue
        )
        with pytest.raises(CleConfigInconnue):
            lire_config(conn, 'cle_inexistante')

    def test_valeur_non_multiple_16_leve(self, conn):
        from services.cartes_automatisme import (
            modifier_config, ValeurConfigInvalide
        )
        with pytest.raises(ValeurConfigInvalide):
            modifier_config(conn, 'cartes_param_nb_uniques', '17')


# ═════════════════════════════════════════════════════════════════════════════
# Routes REST (intégration)
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def app_test(tmp_path):
    """App Flask de test avec data_dir temporaire et BDD initialisée."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "param_niveaux.csv").write_text(
        "Code,CodeCycle,AnneeDansCycle,NomCourt,NomLong\n"
        "N10,C04,anneeun,5e,cinquième\n", encoding="utf-8"
    )
    (data / "C04_themes.csv").write_text(
        "Code,Nom,CodeCouleur,Description\nA,Test,a,desc\n",
        encoding="utf-8"
    )
    (data / "C04_sequences.csv").write_text(
        "Code,Numero,Nom,Theme\nS01,1,Test,A\n", encoding="utf-8"
    )

    from app import create_app
    app = create_app(data_dir=data)
    return app


@pytest.fixture
def app_avec_atomes(app_test):
    """app_test enrichie avec une notion et une méthode en N10/S01.

    v0.13.6.13 — Ajoute aussi un objectif lié à la notion via
    objectif_notions et une séquence_parties parente, de sorte que la
    dérivation automatique objectif_ids dans creer_carte fonctionne
    quand un test crée une carte avec lien_type='notion'/lien_id='no_t'
    (la validation pédagogique exigerait sinon un lien dans
    objectif_cartes pour passer à 'valide')."""
    with app_test.json_store._conn() as conn:
        conn.execute(
            "INSERT INTO notions (id, niveau, sequence, num_connaissance, titre) "
            "VALUES ('no_t', 'N10', 'S01', '01', 'Notion test')"
        )
        conn.execute(
            "INSERT INTO methodes (id, niveau, sequence, num_methode, titre) "
            "VALUES ('me_t', 'N10', 'S01', 1, 'Méthode test')"
        )
        # Séquence + partie parents puis objectif lié à la notion no_t
        conn.execute(
            "INSERT OR IGNORE INTO sequences_par_niveau "
            "(id, niveau, sequence_code) "
            "VALUES ('spn_t', 'N10', 'S01')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO sequence_parties "
            "(id, sequence_par_niveau_id, numero) "
            "VALUES ('sp_t', 'spn_t', 1)"
        )
        conn.execute(
            "INSERT INTO objectifs (id, methode_id, partie_id, code, nom) "
            "VALUES ('ob_n_t', NULL, 'sp_t', '01', 'Objectif notion test')"
        )
        conn.execute(
            "INSERT INTO objectif_notions (objectif_id, notion_id) "
            "VALUES ('ob_n_t', 'no_t')"
        )
        conn.commit()
    return app_test


class TestRoutesCRUD:
    def test_lister_sans_params_400(self, app_test):
        r = app_test.test_client().get('/api/cartes')
        assert r.status_code == 400

    def test_lister_vide_200(self, app_test):
        r = app_test.test_client().get('/api/cartes?niveau=N10&sequence=S01')
        assert r.status_code == 200
        # v0.13.6.15 — format de retour passé à liste directe (avant
        # enveloppe {'cartes': [...]}).
        assert r.get_json() == []

    def test_creer_201(self, app_test):
        r = app_test.test_client().post('/api/cartes', json={
            'niveau': 'N10', 'sequence': 'S01',
            'recto': 'Q', 'verso': 'R',
        })
        assert r.status_code == 201
        assert r.get_json()['id'].startswith('crt_')

    def test_creer_avec_lien(self, app_avec_atomes):
        r = app_avec_atomes.test_client().post('/api/cartes', json={
            'niveau': 'N10', 'sequence': 'S01',
            'type_pedago': 'propriete',
            'lien_type': 'notion', 'lien_id': 'no_t',
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data['lien_type'] == 'notion'
        assert data['lien_id'] == 'no_t'

    def test_creer_lien_invalide_400(self, app_test):
        r = app_test.test_client().post('/api/cartes', json={
            'niveau': 'N10', 'sequence': 'S01',
            'lien_type': 'xyz', 'lien_id': 'no_a',
        })
        assert r.status_code == 400
        assert r.get_json()['code'] == 'lien_type_invalide'

    def test_creer_lien_introuvable_404(self, app_test):
        r = app_test.test_client().post('/api/cartes', json={
            'niveau': 'N10', 'sequence': 'S01',
            'lien_type': 'notion', 'lien_id': 'no_inconnu',
        })
        assert r.status_code == 404
        assert r.get_json()['code'] == 'lien_introuvable'

    def test_patch_lien(self, app_avec_atomes):
        client = app_avec_atomes.test_client()
        r = client.post('/api/cartes', json={
            'niveau': 'N10', 'sequence': 'S01',
            'lien_type': 'notion', 'lien_id': 'no_t',
        })
        carte_id = r.get_json()['id']
        # Basculer vers la méthode
        r = client.patch(f'/api/cartes/{carte_id}', json={
            'lien_type': 'methode', 'lien_id': 'me_t',
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data['lien_type'] == 'methode'
        assert data['lien_id'] == 'me_t'

    def test_lire_inexistante_404(self, app_test):
        r = app_test.test_client().get('/api/cartes/crt_xyz')
        assert r.status_code == 404

    def test_supprimer(self, app_test):
        client = app_test.test_client()
        r = client.post('/api/cartes', json={'niveau': 'N10', 'sequence': 'S01'})
        carte_id = r.get_json()['id']
        r = client.delete(f'/api/cartes/{carte_id}')
        assert r.status_code == 200


class TestRoutesSelecteurs:
    def test_notions_disponibles(self, app_avec_atomes):
        r = app_avec_atomes.test_client().get(
            '/api/cartes/niveau/N10/sequence/S01/notions-disponibles'
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data['niveau'] == 'N10'
        assert data['sequence'] == 'S01'
        assert len(data['notions']) == 1
        assert data['notions'][0]['id'] == 'no_t'

    def test_methodes_disponibles(self, app_avec_atomes):
        r = app_avec_atomes.test_client().get(
            '/api/cartes/niveau/N10/sequence/S01/methodes-disponibles'
        )
        assert r.status_code == 200
        data = r.get_json()
        assert len(data['methodes']) == 1
        assert data['methodes'][0]['id'] == 'me_t'

    def test_notions_disponibles_vide(self, app_test):
        r = app_test.test_client().get(
            '/api/cartes/niveau/N99/sequence/S99/notions-disponibles'
        )
        assert r.status_code == 200
        assert r.get_json()['notions'] == []


class TestRoutesWorkflow:
    """v0.13.6.8.2 — Les routes /api/cartes/<id>/valider et /devalider
    ont été supprimées. Le workflow passe par le mécanisme unifié :
        PATCH /api/atomes/carte/<id>/etat  body: {"etat_code": ...}
    """

    def test_valider_sans_lien_400(self, app_test):
        client = app_test.test_client()
        r = client.post('/api/cartes', json={
            'niveau': 'N10', 'sequence': 'S01',
            'recto': 'Q', 'verso': 'R',
        })
        carte_id = r.get_json()['id']
        r = client.patch(f'/api/atomes/carte/{carte_id}/etat',
                         json={'etat_code': 'valide'})
        assert r.status_code == 400
        data = r.get_json()
        assert data['code'] == 'validation_pedagogique_echec'
        # v0.13.6.8.2 — Les raisons sont au top level du payload (et
        # non dans details.raisons comme avant).
        assert 'raisons' in data
        assert len(data['raisons']) > 0

    def test_valider_complet_200(self, app_avec_atomes):
        client = app_avec_atomes.test_client()
        r = client.post('/api/cartes', json={
            'niveau': 'N10', 'sequence': 'S01',
            'recto': 'Q', 'verso': 'R',
            'lien_type': 'notion', 'lien_id': 'no_t',
        })
        carte_id = r.get_json()['id']
        r = client.patch(f'/api/atomes/carte/{carte_id}/etat',
                         json={'etat_code': 'valide'})
        assert r.status_code == 200
        data = r.get_json()
        assert data['etat_code'] == 'valide'
        # v0.13.6.8.2 — La réponse est au format etats_edition :
        # {type_atome, atome_id, etat_code} (et non la carte complète).
        assert data['type_atome'] == 'carte'
        assert data['atome_id'] == carte_id

    def test_anciennes_routes_404(self, app_test):
        """v0.13.6.8.2 — Vérifie que les anciennes routes /valider et
        /devalider ont bien été supprimées."""
        client = app_test.test_client()
        r = client.post('/api/cartes', json={'niveau': 'N10', 'sequence': 'S01'})
        carte_id = r.get_json()['id']
        r1 = client.post(f'/api/cartes/{carte_id}/valider')
        r2 = client.post(f'/api/cartes/{carte_id}/devalider')
        assert r1.status_code == 404
        assert r2.status_code == 404


class TestRoutesConfig:
    def test_lecture_defaut(self, app_test):
        r = app_test.test_client().get('/api/cartes/config/cartes_param_nb_uniques')
        assert r.status_code == 200
        assert r.get_json()['valeur'] == '16'

    def test_modification(self, app_test):
        r = app_test.test_client().put(
            '/api/cartes/config/cartes_param_nb_uniques',
            json={'valeur': '32'},
        )
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# Schéma BDD : vérifications structurelles
# ═════════════════════════════════════════════════════════════════════════════


class TestSchema:
    def test_check_type_pedago_v0136_calcul_mental_rejete(self, conn):
        """v0.13.6.1.2 : 'calcul_mental' (ancien) rejeté."""
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO cartes_automatisme "
                "(id, niveau, sequence, num, type_pedago) "
                "VALUES ('crt_1', 'N10', 'S01', 1, 'calcul_mental')"
            )

    def test_check_type_pedago_nouveaux_acceptes(self, conn):
        """v0.13.6.1.2 : les 5 nouveaux types acceptés."""
        for i, tp in enumerate(['definition', 'propriete', 'reconnaissance',
                                 'calcul', 'procedure'], start=1):
            conn.execute(
                "INSERT INTO cartes_automatisme "
                "(id, niveau, sequence, num, type_pedago) "
                "VALUES (?, 'N10', 'S01', ?, ?)",
                (f'crt_{tp}', i, tp),
            )

    def test_check_lien_coherence(self, conn):
        """v0.13.6.1.2 : CHECK contraint (lien_type, lien_id) cohérents."""
        # OK : les deux NULL
        conn.execute(
            "INSERT INTO cartes_automatisme (id, niveau, sequence, num) "
            "VALUES ('crt_null', 'N10', 'S01', 1)"
        )
        # OK : les deux fournis
        conn.execute(
            "INSERT INTO cartes_automatisme "
            "(id, niveau, sequence, num, lien_type, lien_id) "
            "VALUES ('crt_lie', 'N10', 'S01', 2, 'notion', 'no_x')"
        )
        # KO : un seul fourni
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO cartes_automatisme "
                "(id, niveau, sequence, num, lien_type, lien_id) "
                "VALUES ('crt_partial', 'N10', 'S01', 3, 'notion', NULL)"
            )
