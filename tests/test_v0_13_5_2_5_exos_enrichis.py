"""tests/test_v0_13_5_2_5_exos_enrichis.py — v0.13.5.2.5.

Tests du contrat enrichi de `lister_exos_evaluation` qui expose
désormais les champs descriptifs des exercices (titre, niveau, sequence,
serie_code, num, type_format) nécessaires à l'UI pour construire un
label métier lisible (N10/S01/F01).

Justification : en v0.13.5.2.4, l'UI affichait l'ID BDD opaque des
exos faute de pouvoir construire le label métier — bug rapporté par
Laurent. Le service exposait juste exercice_id + barèmes.
"""
from __future__ import annotations
import sqlite3

import pytest


@pytest.fixture
def conn_avec_struct(tmp_path):
    """BDD minimale avec un exo doté de ses champs métier."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE exercices (
            id          TEXT PRIMARY KEY,
            serie       TEXT NOT NULL DEFAULT '',
            titre         TEXT NOT NULL DEFAULT '',
            enonce      TEXT NOT NULL DEFAULT '',
            corrige     TEXT NOT NULL DEFAULT '',
            niveau      TEXT NOT NULL DEFAULT '',
            sequence    TEXT NOT NULL DEFAULT '',
            num         INTEGER,
            serie_code  TEXT NOT NULL DEFAULT '',
            type_format TEXT NOT NULL DEFAULT 'standard',
            etat_code   TEXT NOT NULL DEFAULT 'en_cours'
        );
        CREATE TABLE evaluations (
            id                          TEXT PRIMARY KEY,
            niveau                      TEXT NOT NULL,
            numero                      INTEGER NOT NULL,
            ordre                       INTEGER NOT NULL DEFAULT 1,
            titre                       TEXT NOT NULL DEFAULT '',
            mode_notation               TEXT NOT NULL DEFAULT 'note',
            afficher_bareme_dans_exos   INTEGER NOT NULL DEFAULT 1,
            item_langue_francaise       TEXT,
            etat_code                   TEXT NOT NULL DEFAULT 'en_cours',
            mtime                       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE evaluation_exercices (
            evaluation_id        TEXT NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
            exercice_id          TEXT NOT NULL REFERENCES exercices(id) ON DELETE RESTRICT,
            ordre                INTEGER NOT NULL DEFAULT 1,
            bareme_points        REAL,
            bareme_qcm_ok        REAL,
            bareme_qcm_partiel   REAL,
            bareme_qcm_ko        REAL,
            PRIMARY KEY (evaluation_id, exercice_id)
        );
    """)
    # Un exo avec tous les champs métier renseignés
    conn.execute(
        "INSERT INTO exercices (id, serie, titre, enonce, corrige, niveau, "
        "sequence, num, serie_code, type_format) "
        "VALUES ('ex_a01', 'fondamental', 'Calcul de proportions', "
        "        'én', 'cor', 'N10', 'S01', 1, 'F', 'standard')"
    )
    # Un exo QCM
    conn.execute(
        "INSERT INTO exercices (id, serie, titre, enonce, corrige, niveau, "
        "sequence, num, serie_code, type_format) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('ex_q01', 'avancé', 'QCM révisions',
         r'\begin{seqQcm}', 'cor', 'N10', 'S01', 2, 'A', 'qcm')
    )
    # Une éval N10
    conn.execute(
        "INSERT INTO evaluations (id, niveau, numero, titre, mode_notation) "
        "VALUES ('ev1', 'N10', 1, 'Bilan T1', 'note')"
    )
    # Liaisons
    conn.execute(
        "INSERT INTO evaluation_exercices (evaluation_id, exercice_id, "
        "ordre, bareme_points) VALUES ('ev1', 'ex_a01', 1, 4.0)"
    )
    conn.execute(
        "INSERT INTO evaluation_exercices (evaluation_id, exercice_id, "
        "ordre, bareme_qcm_ok, bareme_qcm_partiel, bareme_qcm_ko) "
        "VALUES ('ev1', 'ex_q01', 2, 2.0, 1.0, 0.0)"
    )
    conn.commit()
    return conn


# ── Tests ───────────────────────────────────────────────────────────────────


def test_lister_exos_expose_nom_metier(conn_avec_struct):
    """Le titre de l'exo (saisi par l'enseignant) est exposé."""
    from services.evaluations import lister_exos_evaluation
    exos = lister_exos_evaluation(conn_avec_struct, 'ev1')
    assert len(exos) == 2
    e1 = exos[0]
    assert e1['titre'] == 'Calcul de proportions'
    assert e1['exercice_id'] == 'ex_a01'


def test_lister_exos_expose_champs_label_metier(conn_avec_struct):
    """niveau, sequence, serie_code, num sont exposés pour permettre
    à l'UI de construire le label N10/S01/F01."""
    from services.evaluations import lister_exos_evaluation
    exos = lister_exos_evaluation(conn_avec_struct, 'ev1')
    e1 = exos[0]
    assert e1['niveau']     == 'N10'
    assert e1['sequence']   == 'S01'
    assert e1['serie_code'] == 'F'
    assert e1['num']        == 1
    # On peut reconstituer le label métier
    assert f"{e1['niveau']}/{e1['sequence']}/{e1['serie_code']}{e1['num']:02d}" == 'N10/S01/F01'


def test_lister_exos_expose_type_format(conn_avec_struct):
    """type_format est exposé pour différencier standard/QCM dans l'UI."""
    from services.evaluations import lister_exos_evaluation
    exos = lister_exos_evaluation(conn_avec_struct, 'ev1')
    assert exos[0]['type_format'] == 'standard'  # ex_a01
    assert exos[1]['type_format'] == 'qcm'       # ex_q01


def test_lister_exos_conserve_baremes(conn_avec_struct):
    """Régression : les champs de barème historiquement exposés sont
    toujours présents (le changement v0.13.5.2.5 ne doit pas casser)."""
    from services.evaluations import lister_exos_evaluation
    exos = lister_exos_evaluation(conn_avec_struct, 'ev1')
    assert exos[0]['bareme_points'] == 4.0
    assert exos[1]['bareme_qcm_ok']      == 2.0
    assert exos[1]['bareme_qcm_partiel'] == 1.0
    assert exos[1]['bareme_qcm_ko']      == 0.0


def test_lister_exos_serie_et_ordre(conn_avec_struct):
    """La série du compagnon (champ exo.serie) et l'ordre sont aussi exposés."""
    from services.evaluations import lister_exos_evaluation
    exos = lister_exos_evaluation(conn_avec_struct, 'ev1')
    assert exos[0]['serie'] == 'fondamental'
    assert exos[1]['serie'] == 'avancé'
    assert exos[0]['ordre'] == 1
    assert exos[1]['ordre'] == 2


def test_lister_exos_tri_par_ordre(conn_avec_struct):
    """Le tri par ordre est préservé indépendamment de l'ordre d'insertion."""
    # Réinsérer ex_q01 en ordre 1 et ex_a01 en ordre 2
    conn_avec_struct.execute("DELETE FROM evaluation_exercices WHERE evaluation_id='ev1'")
    conn_avec_struct.execute(
        "INSERT INTO evaluation_exercices "
        "(evaluation_id, exercice_id, ordre, bareme_qcm_ok) "
        "VALUES ('ev1', 'ex_q01', 1, 3.0)"
    )
    conn_avec_struct.execute(
        "INSERT INTO evaluation_exercices "
        "(evaluation_id, exercice_id, ordre, bareme_points) "
        "VALUES ('ev1', 'ex_a01', 2, 5.0)"
    )
    conn_avec_struct.commit()

    from services.evaluations import lister_exos_evaluation
    exos = lister_exos_evaluation(conn_avec_struct, 'ev1')
    assert [e['exercice_id'] for e in exos] == ['ex_q01', 'ex_a01']


def test_lister_exos_evaluation_inexistante_404(conn_avec_struct):
    from services.evaluations import (
        lister_exos_evaluation, EvaluationIntrouvable,
    )
    with pytest.raises(EvaluationIntrouvable):
        lister_exos_evaluation(conn_avec_struct, 'ev_inexistant')


def test_lister_exos_champs_optionnels_remplis_par_defaut(tmp_path):
    """Si titre/niveau/sequence/serie_code sont vides en BDD (cas d'un exo
    importé sans métadonnées), les champs sont exposés comme chaînes vides
    plutôt que None (pour simplifier la vie de l'UI)."""
    db = tmp_path / "test2.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE exercices (
            id          TEXT PRIMARY KEY,
            serie       TEXT NOT NULL DEFAULT '',
            titre         TEXT NOT NULL DEFAULT '',
            enonce      TEXT NOT NULL DEFAULT '',
            corrige     TEXT NOT NULL DEFAULT '',
            niveau      TEXT NOT NULL DEFAULT '',
            sequence    TEXT NOT NULL DEFAULT '',
            num         INTEGER,
            serie_code  TEXT NOT NULL DEFAULT '',
            type_format TEXT NOT NULL DEFAULT 'standard',
            etat_code   TEXT NOT NULL DEFAULT 'en_cours'
        );
        CREATE TABLE evaluations (
            id            TEXT PRIMARY KEY,
            niveau        TEXT NOT NULL,
            numero        INTEGER NOT NULL,
            ordre         INTEGER NOT NULL DEFAULT 1,
            titre         TEXT NOT NULL DEFAULT '',
            mode_notation TEXT NOT NULL DEFAULT 'note',
            afficher_bareme_dans_exos INTEGER NOT NULL DEFAULT 1,
            item_langue_francaise TEXT,
            etat_code     TEXT NOT NULL DEFAULT 'en_cours',
            mtime         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE evaluation_exercices (
            evaluation_id      TEXT NOT NULL,
            exercice_id        TEXT NOT NULL,
            ordre              INTEGER NOT NULL DEFAULT 1,
            bareme_points      REAL,
            bareme_qcm_ok      REAL,
            bareme_qcm_partiel REAL,
            bareme_qcm_ko      REAL,
            PRIMARY KEY (evaluation_id, exercice_id)
        );
    """)
    # Un exo sans titre, sans niveau/sequence (cas dégénéré)
    conn.execute(
        "INSERT INTO exercices (id, serie, enonce, corrige) "
        "VALUES ('ex_orphan', 'fondamental', 'en', 'co')"
    )
    conn.execute(
        "INSERT INTO evaluations (id, niveau, numero, titre) "
        "VALUES ('ev2', 'N10', 1, 'Test')"
    )
    conn.execute(
        "INSERT INTO evaluation_exercices (evaluation_id, exercice_id, ordre) "
        "VALUES ('ev2', 'ex_orphan', 1)"
    )
    conn.commit()

    from services.evaluations import lister_exos_evaluation
    exos = lister_exos_evaluation(conn, 'ev2')
    assert len(exos) == 1
    # Tous les champs string sont '' (pas None)
    assert exos[0]['titre']         == ''
    assert exos[0]['niveau']      == ''
    assert exos[0]['sequence']    == ''
    assert exos[0]['serie_code']  == ''
    assert exos[0]['type_format'] == 'standard'
    # num reste None (entier nullable)
    assert exos[0]['num'] is None
