"""tests/test_v0_13_5_2_1_evaluations.py — v0.13.5.2.1.

Tests des services CRUD bas niveau pour les évaluations, et de la
migration v0.13.5.2.

Couvre :
  - Création / lecture / liste / modification / suppression d'évaluations
  - Validation des paramètres (mode_notation, etat_code,
    item_langue_francaise)
  - Numéros et ordres auto-incrémentés
  - Liaisons evaluation ↔ exercice (ajout, retrait, réordonnancement)
  - Modification de barème
  - Réordonnancement d'évaluations
  - Migration v0.13.5.2 (ajout mtime, type_format, création des tables)
  - Idempotence de la migration
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluations import (
    creer_evaluation, lire_evaluation, lister_evaluations,
    modifier_evaluation, supprimer_evaluation,
    ajouter_exo_a_evaluation, retirer_exo_de_evaluation,
    lister_exos_evaluation, reordonner_exos_evaluation,
    modifier_bareme_exo, reordonner_evaluations,
    EvaluationIntrouvable, NumeroDejaUtilise, ModeNotationInvalide,
    EtatCodeInvalide, ItemLangueFrancaiseInvalide,
    ExerciceIntrouvable, ExoDejaPresent,
    ExoIntrouvableDansEvaluation, ReordonnancementInvalide,
)
from scripts.migrer_v0_13_5_2 import (
    calculer_modifications, appliquer,
)


# ── Schéma minimal pour les tests services ───────────────────────────────────


_SCHEMA_TEST = """
CREATE TABLE exercices (
    id          TEXT PRIMARY KEY,
    serie       TEXT NOT NULL DEFAULT '',
    titre         TEXT NOT NULL DEFAULT '',
    -- v0.13.5.2.5 : champs joints par lister_exos_evaluation pour
    -- permettre à l'UI de construire le label métier N10/S01/F01
    -- et de différencier QCM/standard.
    niveau      TEXT NOT NULL DEFAULT '',
    sequence    TEXT NOT NULL DEFAULT '',
    num         INTEGER,
    serie_code  TEXT NOT NULL DEFAULT '',
    type_format TEXT NOT NULL DEFAULT 'standard'
);
CREATE TABLE evaluations (
    id                          TEXT PRIMARY KEY,
    niveau                      TEXT NOT NULL,
    numero                      INTEGER NOT NULL,
    ordre                       INTEGER NOT NULL,
    titre                       TEXT NOT NULL DEFAULT '',
    mode_notation               TEXT NOT NULL DEFAULT 'note',
    afficher_bareme_dans_exos   INTEGER NOT NULL DEFAULT 1,
    item_langue_francaise       TEXT NOT NULL DEFAULT '',
    etat_code                   TEXT NOT NULL DEFAULT 'en_cours',
    mtime                       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (niveau, numero),
    CHECK  (mode_notation IN ('note', 'criteres', 'note_criteres', 'aucun')),
    CHECK  (etat_code IN ('en_cours', 'valide')),
    CHECK  (afficher_bareme_dans_exos IN (0, 1))
);
CREATE INDEX idx_evaluations_niveau_ordre
    ON evaluations (niveau, ordre);
CREATE TABLE evaluation_exercices (
    evaluation_id      TEXT NOT NULL
                       REFERENCES evaluations(id) ON DELETE CASCADE,
    exercice_id        TEXT NOT NULL
                       REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre              INTEGER NOT NULL,
    bareme_points      REAL,
    bareme_qcm_ok      REAL,
    bareme_qcm_partiel REAL,
    bareme_qcm_ko      REAL,
    PRIMARY KEY (evaluation_id, exercice_id),
    UNIQUE      (evaluation_id, ordre)
);
"""


@pytest.fixture
def conn(tmp_path):
    """Connexion SQLite avec schéma minimal."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_TEST)
    yield conn
    conn.close()


@pytest.fixture
def base_avec_exos(conn):
    """Connexion peuplée avec quelques exercices."""
    for ex_id in ("ex1", "ex2", "ex3", "ex4"):
        conn.execute(
            "INSERT INTO exercices (id, serie, titre) VALUES (?, 'fondamental', ?)",
            (ex_id, f"Exercice {ex_id}"),
        )
    return conn


# ── Tests CRUD evaluations ───────────────────────────────────────────────────


class TestCreerEvaluation:

    def test_creation_simple(self, conn):
        ev = creer_evaluation(conn, niveau="N10", titre="Bilan T1")
        assert ev["niveau"] == "N10"
        assert ev["titre"] == "Bilan T1"
        assert ev["numero"] == 1
        assert ev["ordre"] == 1
        assert ev["mode_notation"] == "note"
        assert ev["afficher_bareme_dans_exos"] is True
        assert ev["item_langue_francaise"] is None
        assert ev["etat_code"] == "en_cours"
        assert ev["mtime"] is not None

    def test_numero_auto_incremente(self, conn):
        ev1 = creer_evaluation(conn, niveau="N10", titre="A")
        ev2 = creer_evaluation(conn, niveau="N10", titre="B")
        ev3 = creer_evaluation(conn, niveau="N10", titre="C")
        assert ev1["numero"] == 1
        assert ev2["numero"] == 2
        assert ev3["numero"] == 3

    def test_numero_indep_par_niveau(self, conn):
        ev_n10 = creer_evaluation(conn, niveau="N10", titre="A")
        ev_n11 = creer_evaluation(conn, niveau="N11", titre="A")
        # N10 et N11 ont chacun leur compteur
        assert ev_n10["numero"] == 1
        assert ev_n11["numero"] == 1

    def test_numero_explicite(self, conn):
        ev = creer_evaluation(conn, niveau="N10", titre="A", numero=42)
        assert ev["numero"] == 42

    def test_numero_deja_utilise(self, conn):
        creer_evaluation(conn, niveau="N10", titre="A", numero=5)
        with pytest.raises(NumeroDejaUtilise) as exc:
            creer_evaluation(conn, niveau="N10", titre="B", numero=5)
        assert exc.value.code == "numero_deja_utilise"
        assert exc.value.details["niveau"] == "N10"
        assert exc.value.details["numero"] == 5

    def test_mode_notation_invalide(self, conn):
        with pytest.raises(ModeNotationInvalide) as exc:
            creer_evaluation(conn, niveau="N10", mode_notation="bidule")
        assert exc.value.code == "mode_notation_invalide"
        assert exc.value.details["valeur"] == "bidule"

    def test_mode_notation_valides(self, conn):
        for mode in ("note", "criteres", "note_criteres", "aucun"):
            ev = creer_evaluation(conn, niveau="N10", mode_notation=mode)
            assert ev["mode_notation"] == mode

    def test_item_langue_francaise_dict(self, conn):
        ev = creer_evaluation(
            conn, niveau="N10",
            item_langue_francaise={"points": 1},
        )
        assert ev["item_langue_francaise"] == {"points": 1}

    def test_item_langue_francaise_invalide_pas_dict(self, conn):
        with pytest.raises(ItemLangueFrancaiseInvalide):
            creer_evaluation(
                conn, niveau="N10",
                item_langue_francaise="pas un dict",
            )

    def test_item_langue_francaise_invalide_sans_points(self, conn):
        with pytest.raises(ItemLangueFrancaiseInvalide):
            creer_evaluation(
                conn, niveau="N10",
                item_langue_francaise={"truc": 1},
            )

    def test_item_langue_francaise_invalide_points_pas_int(self, conn):
        with pytest.raises(ItemLangueFrancaiseInvalide):
            creer_evaluation(
                conn, niveau="N10",
                item_langue_francaise={"points": "deux"},
            )

    def test_afficher_bareme_dans_exos_false(self, conn):
        ev = creer_evaluation(
            conn, niveau="N10",
            afficher_bareme_dans_exos=False,
        )
        assert ev["afficher_bareme_dans_exos"] is False


class TestLireEvaluation:

    def test_lire_existante(self, conn):
        ev = creer_evaluation(conn, niveau="N10", titre="A")
        rel = lire_evaluation(conn, ev["id"])
        assert rel["id"] == ev["id"]
        assert rel["titre"] == "A"

    def test_lire_introuvable(self, conn):
        with pytest.raises(EvaluationIntrouvable) as exc:
            lire_evaluation(conn, "id_qui_n_existe_pas")
        assert exc.value.code == "evaluation_introuvable"


class TestListerEvaluations:

    def test_liste_vide(self, conn):
        assert lister_evaluations(conn) == []

    def test_lister_tout(self, conn):
        creer_evaluation(conn, niveau="N10", titre="A")
        creer_evaluation(conn, niveau="N11", titre="B")
        creer_evaluation(conn, niveau="N10", titre="C")
        evs = lister_evaluations(conn)
        assert len(evs) == 3
        # Tri par (niveau, ordre)
        assert evs[0]["niveau"] == "N10"
        assert evs[0]["titre"] == "A"
        assert evs[1]["titre"] == "C"  # N10 ordre 2
        assert evs[2]["niveau"] == "N11"

    def test_lister_par_niveau(self, conn):
        creer_evaluation(conn, niveau="N10", titre="A")
        creer_evaluation(conn, niveau="N11", titre="B")
        creer_evaluation(conn, niveau="N10", titre="C")
        evs = lister_evaluations(conn, niveau="N10")
        assert len(evs) == 2
        assert all(e["niveau"] == "N10" for e in evs)


class TestModifierEvaluation:

    def test_modifier_titre(self, conn):
        ev = creer_evaluation(conn, niveau="N10", titre="Avant")
        rel = modifier_evaluation(conn, ev["id"], titre="Après")
        assert rel["titre"] == "Après"

    def test_modifier_introuvable(self, conn):
        with pytest.raises(EvaluationIntrouvable):
            modifier_evaluation(conn, "no", titre="x")

    def test_modifier_mode_invalide(self, conn):
        ev = creer_evaluation(conn, niveau="N10")
        with pytest.raises(ModeNotationInvalide):
            modifier_evaluation(conn, ev["id"], mode_notation="bidon")

    def test_modifier_etat_invalide(self, conn):
        ev = creer_evaluation(conn, niveau="N10")
        with pytest.raises(EtatCodeInvalide):
            modifier_evaluation(conn, ev["id"], etat_code="foobar")

    def test_modifier_etat_valide(self, conn):
        ev = creer_evaluation(conn, niveau="N10")
        rel = modifier_evaluation(conn, ev["id"], etat_code="valide")
        assert rel["etat_code"] == "valide"

    def test_modifier_item_lf_effacer(self, conn):
        ev = creer_evaluation(
            conn, niveau="N10",
            item_langue_francaise={"points": 1},
        )
        rel = modifier_evaluation(conn, ev["id"], item_langue_francaise=None)
        assert rel["item_langue_francaise"] is None

    def test_modifier_item_lf_pas_passe_pas_change(self, conn):
        """Si item_langue_francaise n'est pas passé en argument, il ne
        doit pas changer."""
        ev = creer_evaluation(
            conn, niveau="N10",
            item_langue_francaise={"points": 1},
        )
        rel = modifier_evaluation(conn, ev["id"], titre="autre")
        assert rel["item_langue_francaise"] == {"points": 1}

    def test_mtime_mis_a_jour(self, conn):
        import time
        ev = creer_evaluation(conn, niveau="N10")
        ancien_mtime = ev["mtime"]
        time.sleep(1.05)  # SQLite CURRENT_TIMESTAMP a la précision seconde
        rel = modifier_evaluation(conn, ev["id"], titre="x")
        assert rel["mtime"] >= ancien_mtime
        assert rel["mtime"] != ancien_mtime  # doit avoir bougé


class TestSupprimerEvaluation:

    def test_supprimer_existante(self, conn):
        ev = creer_evaluation(conn, niveau="N10")
        supprimer_evaluation(conn, ev["id"])
        with pytest.raises(EvaluationIntrouvable):
            lire_evaluation(conn, ev["id"])

    def test_supprimer_introuvable(self, conn):
        with pytest.raises(EvaluationIntrouvable):
            supprimer_evaluation(conn, "no")

    def test_cascade_sur_liaisons(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex1")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex2")
        supprimer_evaluation(base_avec_exos, ev["id"])
        # Les liaisons doivent avoir été cascadées
        rows = base_avec_exos.execute(
            "SELECT * FROM evaluation_exercices WHERE evaluation_id = ?",
            (ev["id"],),
        ).fetchall()
        assert rows == []


# ── Tests liaisons evaluation ↔ exercices ────────────────────────────────────


class TestAjouterExoAEvaluation:

    def test_ajout_simple(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex1")
        exos = lister_exos_evaluation(base_avec_exos, ev["id"])
        assert len(exos) == 1
        assert exos[0]["exercice_id"] == "ex1"
        assert exos[0]["ordre"] == 1

    def test_ordre_auto_incremente(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex1")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex2")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex3")
        exos = lister_exos_evaluation(base_avec_exos, ev["id"])
        assert [e["ordre"] for e in exos] == [1, 2, 3]
        assert [e["exercice_id"] for e in exos] == ["ex1", "ex2", "ex3"]

    def test_avec_bareme(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(
            base_avec_exos, ev["id"], "ex1",
            bareme_points=4.0,
        )
        exos = lister_exos_evaluation(base_avec_exos, ev["id"])
        assert exos[0]["bareme_points"] == 4.0

    def test_avec_bareme_qcm(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(
            base_avec_exos, ev["id"], "ex1",
            bareme_qcm_ok=1.0,
            bareme_qcm_partiel=0.5,
            bareme_qcm_ko=-0.25,
        )
        exos = lister_exos_evaluation(base_avec_exos, ev["id"])
        assert exos[0]["bareme_qcm_ok"] == 1.0
        assert exos[0]["bareme_qcm_partiel"] == 0.5
        assert exos[0]["bareme_qcm_ko"] == -0.25

    def test_evaluation_introuvable(self, base_avec_exos):
        with pytest.raises(EvaluationIntrouvable):
            ajouter_exo_a_evaluation(base_avec_exos, "no", "ex1")

    def test_exercice_introuvable(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        with pytest.raises(ExerciceIntrouvable):
            ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "exo_inex")

    def test_exo_deja_present(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex1")
        with pytest.raises(ExoDejaPresent):
            ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex1")

    def test_mtime_evaluation_mis_a_jour(self, base_avec_exos):
        import time
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ancien_mtime = ev["mtime"]
        time.sleep(1.05)
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex1")
        rel = lire_evaluation(base_avec_exos, ev["id"])
        assert rel["mtime"] != ancien_mtime


class TestRetirerExo:

    def test_retrait_simple(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex1")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex2")
        retirer_exo_de_evaluation(base_avec_exos, ev["id"], "ex1")
        exos = lister_exos_evaluation(base_avec_exos, ev["id"])
        assert len(exos) == 1
        assert exos[0]["exercice_id"] == "ex2"

    def test_retrait_evaluation_introuvable(self, base_avec_exos):
        with pytest.raises(EvaluationIntrouvable):
            retirer_exo_de_evaluation(base_avec_exos, "no", "ex1")

    def test_retrait_exo_pas_lie(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        with pytest.raises(ExoIntrouvableDansEvaluation):
            retirer_exo_de_evaluation(base_avec_exos, ev["id"], "ex1")


class TestReordonnerExos:

    def test_inversion(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex1")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex2")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex3")
        reordonner_exos_evaluation(
            base_avec_exos, ev["id"], ["ex3", "ex2", "ex1"],
        )
        exos = lister_exos_evaluation(base_avec_exos, ev["id"])
        assert [e["exercice_id"] for e in exos] == ["ex3", "ex2", "ex1"]
        assert [e["ordre"] for e in exos] == [1, 2, 3]

    def test_doublons(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex1")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex2")
        with pytest.raises(ReordonnancementInvalide):
            reordonner_exos_evaluation(
                base_avec_exos, ev["id"], ["ex1", "ex1"],
            )

    def test_manquants(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex1")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex2")
        with pytest.raises(ReordonnancementInvalide):
            reordonner_exos_evaluation(
                base_avec_exos, ev["id"], ["ex1"],  # ex2 manque
            )

    def test_id_inconnu(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(base_avec_exos, ev["id"], "ex1")
        with pytest.raises(ReordonnancementInvalide):
            reordonner_exos_evaluation(
                base_avec_exos, ev["id"], ["ex1", "ex_pas_la"],
            )


class TestModifierBaremeExo:

    def test_changer_points(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(
            base_avec_exos, ev["id"], "ex1", bareme_points=2.0,
        )
        modifier_bareme_exo(
            base_avec_exos, ev["id"], "ex1", bareme_points=4.0,
        )
        exos = lister_exos_evaluation(base_avec_exos, ev["id"])
        assert exos[0]["bareme_points"] == 4.0

    def test_effacer_points(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(
            base_avec_exos, ev["id"], "ex1", bareme_points=2.0,
        )
        modifier_bareme_exo(
            base_avec_exos, ev["id"], "ex1", bareme_points=None,
        )
        exos = lister_exos_evaluation(base_avec_exos, ev["id"])
        assert exos[0]["bareme_points"] is None

    def test_no_change_par_default(self, base_avec_exos):
        """Sans paramètre, rien n'est touché."""
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        ajouter_exo_a_evaluation(
            base_avec_exos, ev["id"], "ex1", bareme_points=2.0,
        )
        modifier_bareme_exo(base_avec_exos, ev["id"], "ex1")
        exos = lister_exos_evaluation(base_avec_exos, ev["id"])
        assert exos[0]["bareme_points"] == 2.0

    def test_introuvable_dans_evaluation(self, base_avec_exos):
        ev = creer_evaluation(base_avec_exos, niveau="N10")
        with pytest.raises(ExoIntrouvableDansEvaluation):
            modifier_bareme_exo(
                base_avec_exos, ev["id"], "ex1", bareme_points=4.0,
            )


class TestReordonnerEvaluations:

    def test_inversion(self, conn):
        ev_a = creer_evaluation(conn, niveau="N10", titre="A")
        ev_b = creer_evaluation(conn, niveau="N10", titre="B")
        ev_c = creer_evaluation(conn, niveau="N10", titre="C")
        # Ordre initial : A(1), B(2), C(3). On veut C, A, B.
        reordonner_evaluations(
            conn, "N10", [ev_c["id"], ev_a["id"], ev_b["id"]],
        )
        evs = lister_evaluations(conn, niveau="N10")
        assert [e["titre"] for e in evs] == ["C", "A", "B"]
        assert [e["ordre"] for e in evs] == [1, 2, 3]

    def test_doublons(self, conn):
        ev_a = creer_evaluation(conn, niveau="N10", titre="A")
        with pytest.raises(ReordonnancementInvalide):
            reordonner_evaluations(
                conn, "N10", [ev_a["id"], ev_a["id"]],
            )


# ── Tests de la migration ────────────────────────────────────────────────────


# Schéma "ancien" sans mtime, sans type_format, sans evaluations.
_SCHEMA_AVANT_MIGRATION = """
CREATE TABLE notions (
    id    TEXT PRIMARY KEY,
    titre TEXT NOT NULL DEFAULT ''
);
CREATE TABLE methodes (
    id    TEXT PRIMARY KEY,
    titre TEXT NOT NULL DEFAULT ''
);
CREATE TABLE exercices (
    id    TEXT PRIMARY KEY,
    serie TEXT NOT NULL,
    titre   TEXT NOT NULL DEFAULT ''
);
CREATE TABLE fiches_resume (
    id    TEXT PRIMARY KEY,
    titre TEXT NOT NULL DEFAULT ''
);
"""


@pytest.fixture
def conn_avant_migration(tmp_path):
    """BDD à l'état pré-v0.13.5.2 : tables d'atomes sans mtime,
    pas de type_format sur exercices, pas de tables evaluations."""
    db_path = tmp_path / "test_avant.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_AVANT_MIGRATION)
    # Quelques atomes existants pour tester l'initialisation des mtime
    conn.execute("INSERT INTO notions (id, titre) VALUES ('n1', 'N')")
    conn.execute("INSERT INTO methodes (id, titre) VALUES ('m1', 'M')")
    conn.execute("INSERT INTO exercices (id, serie) VALUES ('e1', 'fondamental')")
    conn.execute("INSERT INTO fiches_resume (id, titre) VALUES ('f1', 'F')")
    conn.commit()
    yield conn
    conn.close()


class TestMigration:

    def test_calculer_modifications_avant(self, conn_avant_migration):
        mods = calculer_modifications(conn_avant_migration)
        # Toutes les tables doivent recevoir mtime
        assert set(mods["mtime_a_ajouter"]) == {
            "notions", "methodes", "exercices", "fiches_resume",
        }
        assert mods["type_format_a_ajouter"] is True
        assert mods["evaluations_a_creer"] is True
        assert mods["evaluation_exercices_a_creer"] is True

    def test_appliquer_migration(self, conn_avant_migration):
        mods = calculer_modifications(conn_avant_migration)
        n = appliquer(conn_avant_migration, mods)
        # 4 mtime + 1 type_format + 1 evaluations + 1 evaluation_exercices
        assert n == 7

        # Vérifier mtime ajouté partout
        for table in ("notions", "methodes", "exercices", "fiches_resume"):
            cols = {r["name"] for r in conn_avant_migration.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()}
            assert "mtime" in cols, f"mtime manquant dans {table}"

        # Vérifier que les enregistrements ont bien un mtime non-NULL
        for table in ("notions", "methodes", "exercices", "fiches_resume"):
            rows = conn_avant_migration.execute(
                f"SELECT mtime FROM {table}"
            ).fetchall()
            assert all(r["mtime"] is not None for r in rows)

        # Vérifier type_format
        cols_e = {r["name"] for r in conn_avant_migration.execute(
            "PRAGMA table_info(exercices)"
        ).fetchall()}
        assert "type_format" in cols_e
        # Les exercices existants doivent avoir 'standard' par défaut
        rows = conn_avant_migration.execute(
            "SELECT type_format FROM exercices"
        ).fetchall()
        assert all(r["type_format"] == "standard" for r in rows)

        # Vérifier les nouvelles tables
        tables = {r["name"] for r in conn_avant_migration.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "evaluations" in tables
        assert "evaluation_exercices" in tables

    def test_migration_idempotente(self, conn_avant_migration):
        """Rejouer la migration sur une BDD déjà migrée ne fait rien."""
        # Première application
        mods1 = calculer_modifications(conn_avant_migration)
        appliquer(conn_avant_migration, mods1)

        # Deuxième détection : tout doit être à jour
        mods2 = calculer_modifications(conn_avant_migration)
        assert mods2["mtime_a_ajouter"] == []
        assert mods2["type_format_a_ajouter"] is False
        assert mods2["evaluations_a_creer"] is False
        assert mods2["evaluation_exercices_a_creer"] is False

    def test_migration_partielle_idempotente(self, conn_avant_migration):
        """Si certaines colonnes sont déjà là, on ne les recrée pas."""
        # Ajout préalable de mtime sur notions seulement
        conn_avant_migration.execute(
            "ALTER TABLE notions ADD COLUMN mtime DATETIME"
        )
        conn_avant_migration.commit()

        mods = calculer_modifications(conn_avant_migration)
        assert "notions" not in mods["mtime_a_ajouter"]
        assert set(mods["mtime_a_ajouter"]) == {
            "methodes", "exercices", "fiches_resume",
        }

        # Application : les autres tables doivent être migrées sans erreur
        appliquer(conn_avant_migration, mods)

        # Vérification finale
        mods_apres = calculer_modifications(conn_avant_migration)
        assert mods_apres["mtime_a_ajouter"] == []


# ── Tests intégration migration auto via SqliteStore ─────────────────────────


class TestMigrationViaSqliteStore:
    """Vérifie que la migration auto au démarrage de SqliteStore fait
    bien la même chose que le script CLI."""

    def test_demarrage_sur_bdd_neuve(self, tmp_path):
        """Sur une BDD vide, SqliteStore crée tout, y compris evaluations."""
        from persistence.sqlite_store import SqliteStore
        store = SqliteStore(tmp_path)
        with store._conn() as conn:
            tables = {r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            # Tables d'atomes existantes
            assert "notions" in tables
            assert "exercices" in tables
            assert "fiches_resume" in tables
            # Nouvelles tables v0.13.5.2
            assert "evaluations" in tables
            assert "evaluation_exercices" in tables
            # mtime sur les tables d'atomes
            for table in ("notions", "methodes", "exercices",
                            "fiches_resume"):
                cols = {r["name"] for r in conn.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()}
                assert "mtime" in cols, f"mtime manquant dans {table}"
            # type_format sur exercices
            cols_e = {r["name"] for r in conn.execute(
                "PRAGMA table_info(exercices)"
            ).fetchall()}
            assert "type_format" in cols_e

    def test_demarrage_sur_bdd_pre_v0_13_5_2(self, tmp_path):
        """Sur une BDD pré-v0.13.5.2 (sans mtime, sans type_format,
        sans evaluations), le démarrage SqliteStore fait la migration.

        On utilise un schéma réaliste minimal : les colonnes/indexes
        qui existaient déjà avant v0.13.5.2 sont présents, seules les
        colonnes/tables ajoutées en v0.13.5.2 sont absentes."""
        db_path = tmp_path / "seqenseigne.db"
        conn = sqlite3.connect(str(db_path))
        # Schéma proche du schema.sql actuel mais sans les ajouts v0.13.5.2.
        # On reprend juste ce qui est nécessaire pour que SqliteStore
        # démarre sans erreur (il doit trouver toutes les tables et
        # leurs colonnes que le schéma référence dans les indexes).
        conn.executescript("""
            CREATE TABLE notions (
                id               TEXT PRIMARY KEY,
                titre            TEXT NOT NULL DEFAULT '',
                corps            TEXT NOT NULL DEFAULT '',
                ordre_sections   TEXT NOT NULL DEFAULT 'ER',
                niveau           TEXT NOT NULL DEFAULT '',
                sequence         TEXT NOT NULL DEFAULT '',
                num_connaissance TEXT NOT NULL DEFAULT '',
                fichier          TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE methodes (
                id             TEXT PRIMARY KEY,
                titre          TEXT NOT NULL DEFAULT '',
                corps          TEXT NOT NULL DEFAULT '',
                fin_cycle      TEXT NOT NULL DEFAULT 'N',
                ordre_sections TEXT NOT NULL DEFAULT 'ER',
                niveau         TEXT NOT NULL DEFAULT '',
                sequence       TEXT NOT NULL DEFAULT '',
                num_methode    INTEGER,
                num_objectif   TEXT NOT NULL DEFAULT '',
                fichier        TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE exercices (
                id         TEXT PRIMARY KEY,
                serie      TEXT NOT NULL,
                titre        TEXT NOT NULL DEFAULT '',
                variables  TEXT NOT NULL DEFAULT '',
                enonce     TEXT NOT NULL DEFAULT '',
                corrige    TEXT NOT NULL DEFAULT '',
                niveau     TEXT NOT NULL DEFAULT '',
                sequence   TEXT NOT NULL DEFAULT '',
                num        INTEGER,
                serie_code TEXT NOT NULL DEFAULT '',
                fichier    TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE fiches_resume (
                id           TEXT PRIMARY KEY,
                titre        TEXT NOT NULL DEFAULT '',
                objectif_id  TEXT,
                num_fiche    INTEGER,
                niveau       TEXT NOT NULL DEFAULT '',
                sequence     TEXT NOT NULL DEFAULT '',
                fichier      TEXT NOT NULL DEFAULT '',
                etat_code    TEXT NOT NULL DEFAULT 'en_cours'
            );
        """)
        conn.execute("INSERT INTO notions (id, titre) VALUES ('n1', 'X')")
        conn.commit()
        conn.close()

        # Démarrage de SqliteStore qui doit migrer tout seul
        from persistence.sqlite_store import SqliteStore
        store = SqliteStore(tmp_path)

        with store._conn() as conn:
            # mtime ajouté et peuplé
            cols_n = {r["name"] for r in conn.execute(
                "PRAGMA table_info(notions)"
            ).fetchall()}
            assert "mtime" in cols_n
            row = conn.execute(
                "SELECT mtime FROM notions WHERE id='n1'"
            ).fetchone()
            assert row["mtime"] is not None
            # type_format sur exercices
            cols_e = {r["name"] for r in conn.execute(
                "PRAGMA table_info(exercices)"
            ).fetchall()}
            assert "type_format" in cols_e
            # Nouvelles tables créées
            tables = {r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            assert "evaluations" in tables
            assert "evaluation_exercices" in tables
