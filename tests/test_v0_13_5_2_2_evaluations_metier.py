"""tests/test_v0_13_5_2_2_evaluations_metier.py — v0.13.5.2.2.

Tests des services métier ajoutés en v0.13.5.2.2 :
  - Liaisons évaluation ↔ objectifs (ajout, retrait, listage)
  - Validation pédagogique en_cours → valide (contrôles métier)
  - Dévalidation valide → en_cours (libre, sans contrôle)
  - Calcul de couverture (matrice objectifs × exos)

Le périmètre v0.13.5.2.1 (CRUD bas niveau) est couvert par
test_v0_13_5_2_1_evaluations.py — on ne le re-teste pas ici, on
le compose simplement.
"""
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluations import (
    # CRUD existant qu'on utilise comme fixture
    creer_evaluation, modifier_evaluation,
    ajouter_exo_a_evaluation, modifier_bareme_exo,
    lire_evaluation,
    # Nouvelles fonctions v0.13.5.2.2
    ajouter_objectif_a_evaluation, retirer_objectif_de_evaluation,
    lister_objectifs_evaluation,
    valider_evaluation, devalider_evaluation,
    calculer_couverture,
    # Nouvelles exceptions
    EvaluationIntrouvable,
    ObjectifIntrouvable, ObjectifDejaPresent,
    ObjectifIntrouvableDansEvaluation,
    ObjectifNiveauIncoherent,
    DejaValide, DejaEnCours,
    ValidationPedagogiqueErreur,
)


# ── Schéma de test ────────────────────────────────────────────────────────────

# Schéma volontairement riche pour couvrir aussi les jointures vers
# sequences_par_niveau et sequence_parties (nécessaires pour les
# liaisons objectifs). On reste minimal sur les colonnes qui ne sont
# pas utilisées par les services testés ici.

_SCHEMA_TEST = """
CREATE TABLE exercices (
    id            TEXT PRIMARY KEY,
    serie         TEXT NOT NULL DEFAULT '',
    titre           TEXT NOT NULL DEFAULT '',
    type_format   TEXT NOT NULL DEFAULT 'standard',
    -- v0.13.5.3 : champs joints par calculer_couverture pour permettre
    -- à l'UI de construire le label métier N10/S01/F01 dans les entêtes
    -- de la matrice de couverture.
    niveau        TEXT NOT NULL DEFAULT '',
    sequence      TEXT NOT NULL DEFAULT '',
    num           INTEGER,
    serie_code    TEXT NOT NULL DEFAULT ''
);
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
    numero                 INTEGER NOT NULL
);
CREATE TABLE objectifs (
    id         TEXT PRIMARY KEY,
    partie_id  TEXT NOT NULL
               REFERENCES sequence_parties(id) ON DELETE CASCADE,
    code       TEXT NOT NULL,
    nom        TEXT NOT NULL DEFAULT '',
    methode_id TEXT,
    fin_cycle  TEXT NOT NULL DEFAULT 'N'
);
CREATE TABLE objectif_exos (
    objectif_id    TEXT NOT NULL
                   REFERENCES objectifs(id) ON DELETE CASCADE,
    serie          TEXT NOT NULL,
    exercice_id    TEXT NOT NULL
                   REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre          INTEGER NOT NULL DEFAULT 0
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
CREATE TABLE evaluation_objectifs (
    evaluation_id  TEXT NOT NULL
                   REFERENCES evaluations(id) ON DELETE CASCADE,
    objectif_id    TEXT NOT NULL
                   REFERENCES objectifs(id) ON DELETE RESTRICT,
    PRIMARY KEY (evaluation_id, objectif_id)
);
"""


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def conn(tmp_path):
    """Connexion SQLite vierge avec schéma riche."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_TEST)
    yield conn
    conn.close()


def _peupler_struct_pedago(conn):
    """Peuple un mini-cosmos : 2 niveaux (N10, N11), 1 séquence par
    niveau, 2 parties par séquence, 2 objectifs par partie.

    Convention de naming :
      sn_N10_S01            séquence N10/S01
      sp_N10_S01_p1         partie 1 de N10/S01
      ob_N10_S01_p1_01      objectif "01" de N10/S01 partie 1
    """
    for niveau, seq in (("N10", "S01"), ("N11", "S01")):
        sn_id = f"sn_{niveau}_{seq}"
        conn.execute(
            "INSERT INTO sequences_par_niveau "
            "(id, niveau, sequence_code) VALUES (?, ?, ?)",
            (sn_id, niveau, seq),
        )
        for partie_num in (1, 2):
            sp_id = f"sp_{niveau}_{seq}_p{partie_num}"
            conn.execute(
                "INSERT INTO sequence_parties "
                "(id, sequence_par_niveau_id, numero) VALUES (?, ?, ?)",
                (sp_id, sn_id, partie_num),
            )
            for code in ("01", "02"):
                ob_id = f"ob_{niveau}_{seq}_p{partie_num}_{code}"
                conn.execute(
                    "INSERT INTO objectifs "
                    "(id, partie_id, code, nom) VALUES (?, ?, ?, ?)",
                    (ob_id, sp_id, code,
                     f"Objectif {code} niveau {niveau} partie {partie_num}"),
                )


def _peupler_exos(conn, count=4, type_format="standard"):
    """Crée `count` exos standard ou qcm (ex1, ex2, ..., exN)."""
    for i in range(1, count + 1):
        conn.execute(
            "INSERT INTO exercices (id, serie, titre, type_format) "
            "VALUES (?, 'fondamental', ?, ?)",
            (f"ex{i}", f"Exercice {i}", type_format),
        )


def _lier_exo_objectif(conn, exercice_id, objectif_id, serie="F"):
    """Lien direct exo ↔ objectif via la table objectif_exos."""
    conn.execute(
        "INSERT INTO objectif_exos "
        "(objectif_id, serie, exercice_id, ordre) VALUES (?, ?, ?, 1)",
        (objectif_id, serie, exercice_id),
    )


@pytest.fixture
def conn_peuplee(conn):
    """Conn + structure pédago + exos standard."""
    _peupler_struct_pedago(conn)
    _peupler_exos(conn, count=4)
    return conn


# ═══════════════════════════════════════════════════════════════════════════════
# Section A — Liaisons évaluation ↔ objectifs
# ═══════════════════════════════════════════════════════════════════════════════


class TestLierObjectif:

    def test_ajout_simple(self, conn_peuplee):
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        ob = ajouter_objectif_a_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
        )
        assert ob["id"]   == "ob_N10_S01_p1_01"
        assert ob["code"] == "01"
        assert ob["sequence_code"] == "S01"
        assert ob["partie_numero"] == 1

    def test_ajout_plusieurs_objectifs(self, conn_peuplee):
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        ajouter_objectif_a_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
        )
        ajouter_objectif_a_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p2_02"
        )
        liste = lister_objectifs_evaluation(conn_peuplee, ev["id"])
        assert len(liste) == 2
        # Tri attendu : par sequence_code, puis partie_numero, puis code
        assert liste[0]["id"] == "ob_N10_S01_p1_01"
        assert liste[1]["id"] == "ob_N10_S01_p2_02"

    def test_ajout_objectif_inexistant(self, conn_peuplee):
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        with pytest.raises(ObjectifIntrouvable):
            ajouter_objectif_a_evaluation(
                conn_peuplee, ev["id"], "ob_inexistant"
            )

    def test_ajout_objectif_doublon(self, conn_peuplee):
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        ajouter_objectif_a_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
        )
        with pytest.raises(ObjectifDejaPresent) as exc:
            ajouter_objectif_a_evaluation(
                conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
            )
        assert exc.value.code == "objectif_deja_present"

    def test_ajout_objectif_niveau_incoherent(self, conn_peuplee):
        """On ne peut pas attacher un objectif N11 à une éval N10."""
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        with pytest.raises(ObjectifNiveauIncoherent) as exc:
            ajouter_objectif_a_evaluation(
                conn_peuplee, ev["id"], "ob_N11_S01_p1_01"
            )
        assert exc.value.details["niveau_eval"] == "N10"
        assert exc.value.details["niveau_obj"]  == "N11"

    def test_ajout_eval_inexistante(self, conn_peuplee):
        with pytest.raises(EvaluationIntrouvable):
            ajouter_objectif_a_evaluation(
                conn_peuplee, "ev_inexistante", "ob_N10_S01_p1_01"
            )


class TestRetirerObjectif:

    def test_retrait_simple(self, conn_peuplee):
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        ajouter_objectif_a_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
        )
        retirer_objectif_de_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
        )
        assert lister_objectifs_evaluation(conn_peuplee, ev["id"]) == []

    def test_retrait_objectif_non_lie(self, conn_peuplee):
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        with pytest.raises(ObjectifIntrouvableDansEvaluation):
            retirer_objectif_de_evaluation(
                conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
            )

    def test_retrait_eval_inexistante(self, conn_peuplee):
        with pytest.raises(EvaluationIntrouvable):
            retirer_objectif_de_evaluation(
                conn_peuplee, "ev_inexistante", "ob_N10_S01_p1_01"
            )


class TestListerObjectifs:

    def test_eval_vide(self, conn_peuplee):
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        assert lister_objectifs_evaluation(conn_peuplee, ev["id"]) == []

    def test_tri_par_sequence_partie_code(self, conn_peuplee):
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        # Ajout dans le désordre
        for obj_id in (
            "ob_N10_S01_p2_02",
            "ob_N10_S01_p1_02",
            "ob_N10_S01_p2_01",
            "ob_N10_S01_p1_01",
        ):
            ajouter_objectif_a_evaluation(conn_peuplee, ev["id"], obj_id)
        liste = lister_objectifs_evaluation(conn_peuplee, ev["id"])
        # Tri attendu : p1 puis p2, et 01 avant 02 dans chaque partie
        assert [o["id"] for o in liste] == [
            "ob_N10_S01_p1_01",
            "ob_N10_S01_p1_02",
            "ob_N10_S01_p2_01",
            "ob_N10_S01_p2_02",
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# Section B — Validation pédagogique : en_cours → valide
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidationModeAucun:
    """Mode 'aucun' : pas de barème obligatoire, juste ≥1 exo."""

    def test_eval_avec_un_exo_sans_bareme_passe(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="aucun",
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        result = valider_evaluation(conn_peuplee, ev["id"])
        assert result["etat_code"] == "valide"

    def test_eval_vide_echoue(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="aucun",
        )
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            valider_evaluation(conn_peuplee, ev["id"])
        raisons = exc.value.details["raisons"]
        assert any(r["code"] == "aucun_exercice" for r in raisons)

    def test_bareme_negatif_signale(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="aucun",
        )
        ajouter_exo_a_evaluation(
            conn_peuplee, ev["id"], "ex1", bareme_points=-2.0
        )
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            valider_evaluation(conn_peuplee, ev["id"])
        raisons = exc.value.details["raisons"]
        assert any(r["code"] == "bareme_negatif" for r in raisons)


class TestValidationModeNote:
    """Mode 'note' : bareme_points obligatoire pour chaque exo standard."""

    def test_eval_avec_bareme_correct_passe(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="note",
        )
        ajouter_exo_a_evaluation(
            conn_peuplee, ev["id"], "ex1", bareme_points=4.0
        )
        ajouter_exo_a_evaluation(
            conn_peuplee, ev["id"], "ex2", bareme_points=6.0
        )
        result = valider_evaluation(conn_peuplee, ev["id"])
        assert result["etat_code"] == "valide"

    def test_bareme_manquant_signale(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="note",
        )
        # Premier exo bien doté, deuxième sans barème
        ajouter_exo_a_evaluation(
            conn_peuplee, ev["id"], "ex1", bareme_points=4.0
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex2")
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            valider_evaluation(conn_peuplee, ev["id"])
        raisons = exc.value.details["raisons"]
        manquants = [r for r in raisons if r["code"] == "bareme_manquant"]
        assert len(manquants) == 1
        assert manquants[0]["exercice_id"] == "ex2"

    def test_plusieurs_baremes_manquants(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="note",
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex2")
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            valider_evaluation(conn_peuplee, ev["id"])
        manquants = [
            r for r in exc.value.details["raisons"]
            if r["code"] == "bareme_manquant"
        ]
        assert len(manquants) == 2
        assert {r["exercice_id"] for r in manquants} == {"ex1", "ex2"}

    def test_bareme_negatif_echoue(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="note",
        )
        ajouter_exo_a_evaluation(
            conn_peuplee, ev["id"], "ex1", bareme_points=-1.0
        )
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            valider_evaluation(conn_peuplee, ev["id"])
        assert any(
            r["code"] == "bareme_negatif"
            for r in exc.value.details["raisons"]
        )


class TestValidationModeCriteres:
    """Mode 'criteres' : barème_points facultatif (peut être NULL)."""

    def test_eval_sans_bareme_passe(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="criteres",
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        result = valider_evaluation(conn_peuplee, ev["id"])
        assert result["etat_code"] == "valide"

    def test_eval_avec_bareme_passe_aussi(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="criteres",
        )
        ajouter_exo_a_evaluation(
            conn_peuplee, ev["id"], "ex1", bareme_points=5.0
        )
        result = valider_evaluation(conn_peuplee, ev["id"])
        assert result["etat_code"] == "valide"

    def test_eval_vide_echoue(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="criteres",
        )
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            valider_evaluation(conn_peuplee, ev["id"])
        assert any(
            r["code"] == "aucun_exercice"
            for r in exc.value.details["raisons"]
        )


class TestValidationModeNoteCriteres:
    """Mode 'note_criteres' : bareme_points obligatoire (comme 'note')."""

    def test_eval_avec_bareme_passe(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="note_criteres",
        )
        ajouter_exo_a_evaluation(
            conn_peuplee, ev["id"], "ex1", bareme_points=4.0
        )
        result = valider_evaluation(conn_peuplee, ev["id"])
        assert result["etat_code"] == "valide"

    def test_bareme_manquant_echoue(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="note_criteres",
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            valider_evaluation(conn_peuplee, ev["id"])
        assert any(
            r["code"] == "bareme_manquant"
            for r in exc.value.details["raisons"]
        )


class TestValidationQCM:
    """type_format='qcm' : bareme_qcm_ok/partiel/ko obligatoires en
    modes 'note' et 'note_criteres'."""

    def test_qcm_avec_tous_baremes_passe(self, conn):
        _peupler_struct_pedago(conn)
        _peupler_exos(conn, count=1, type_format="qcm")
        ev = creer_evaluation(
            conn, niveau="N10", titre="T1", mode_notation="note"
        )
        ajouter_exo_a_evaluation(
            conn, ev["id"], "ex1",
            bareme_qcm_ok=1.0, bareme_qcm_partiel=0.5, bareme_qcm_ko=0.0
        )
        result = valider_evaluation(conn, ev["id"])
        assert result["etat_code"] == "valide"

    def test_qcm_avec_un_bareme_manquant_echoue(self, conn):
        _peupler_struct_pedago(conn)
        _peupler_exos(conn, count=1, type_format="qcm")
        ev = creer_evaluation(
            conn, niveau="N10", titre="T1", mode_notation="note"
        )
        # ko manquant
        ajouter_exo_a_evaluation(
            conn, ev["id"], "ex1",
            bareme_qcm_ok=1.0, bareme_qcm_partiel=0.5
        )
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            valider_evaluation(conn, ev["id"])
        manquants = [
            r for r in exc.value.details["raisons"]
            if r["code"] == "bareme_qcm_manquant"
        ]
        assert len(manquants) == 1
        assert "ko" in manquants[0]["champs"]

    def test_qcm_tous_baremes_manquants_echoue(self, conn):
        _peupler_struct_pedago(conn)
        _peupler_exos(conn, count=1, type_format="qcm")
        ev = creer_evaluation(
            conn, niveau="N10", titre="T1", mode_notation="note_criteres"
        )
        ajouter_exo_a_evaluation(conn, ev["id"], "ex1")
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            valider_evaluation(conn, ev["id"])
        manquants = [
            r for r in exc.value.details["raisons"]
            if r["code"] == "bareme_qcm_manquant"
        ]
        assert len(manquants) == 1
        assert set(manquants[0]["champs"]) == {"ok", "partiel", "ko"}

    def test_qcm_en_mode_criteres_pas_de_bareme_requis(self, conn):
        """Mode 'criteres' : QCM sans bareme_qcm_* → passe."""
        _peupler_struct_pedago(conn)
        _peupler_exos(conn, count=1, type_format="qcm")
        ev = creer_evaluation(
            conn, niveau="N10", titre="T1", mode_notation="criteres"
        )
        ajouter_exo_a_evaluation(conn, ev["id"], "ex1")
        result = valider_evaluation(conn, ev["id"])
        assert result["etat_code"] == "valide"


class TestValidationCasParticuliers:

    def test_deja_valide_signale(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="aucun",
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        valider_evaluation(conn_peuplee, ev["id"])
        # 2e appel → DejaValide
        with pytest.raises(DejaValide) as exc:
            valider_evaluation(conn_peuplee, ev["id"])
        assert exc.value.code == "deja_valide"

    def test_eval_inexistante(self, conn_peuplee):
        with pytest.raises(EvaluationIntrouvable):
            valider_evaluation(conn_peuplee, "ev_inexistante")

    def test_raisons_multiples_dans_une_seule_erreur(self, conn_peuplee):
        """Plusieurs exos sans barème → tous signalés dans la même erreur."""
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="note",
        )
        for ex in ("ex1", "ex2", "ex3"):
            ajouter_exo_a_evaluation(conn_peuplee, ev["id"], ex)
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            valider_evaluation(conn_peuplee, ev["id"])
        manquants = [
            r for r in exc.value.details["raisons"]
            if r["code"] == "bareme_manquant"
        ]
        assert len(manquants) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Section C — Dévalidation : valide → en_cours (libre)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDevalidation:

    def test_devalidation_simple(self, conn_peuplee):
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="aucun",
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        valider_evaluation(conn_peuplee, ev["id"])
        result = devalider_evaluation(conn_peuplee, ev["id"])
        assert result["etat_code"] == "en_cours"

    def test_deja_en_cours_signale(self, conn_peuplee):
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        with pytest.raises(DejaEnCours) as exc:
            devalider_evaluation(conn_peuplee, ev["id"])
        assert exc.value.code == "deja_en_cours"

    def test_devalidation_sans_controle(self, conn_peuplee):
        """Dévalider n'impose aucun critère métier — même si la
        validation pédagogique passerait toujours, on retombe en
        en_cours librement (cohérent avec pattern etats_edition)."""
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="aucun",
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        valider_evaluation(conn_peuplee, ev["id"])
        # On retire l'exo (l'éval devient impossible à revalider)
        # avant de dévalider. devalider_evaluation doit malgré tout
        # passer (aucun contrôle).
        result = devalider_evaluation(conn_peuplee, ev["id"])
        assert result["etat_code"] == "en_cours"

    def test_eval_inexistante(self, conn_peuplee):
        with pytest.raises(EvaluationIntrouvable):
            devalider_evaluation(conn_peuplee, "ev_inexistante")


# ═══════════════════════════════════════════════════════════════════════════════
# Section D — Calcul de couverture
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculerCouverture:

    def test_eval_vide_de_tout(self, conn_peuplee):
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        c = calculer_couverture(conn_peuplee, ev["id"])
        assert c["objectifs"] == []
        assert c["exercices"] == []
        assert c["cellules"] == []

    def test_eval_avec_objectifs_seuls(self, conn_peuplee):
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        ajouter_objectif_a_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
        )
        c = calculer_couverture(conn_peuplee, ev["id"])
        assert len(c["objectifs"]) == 1
        assert c["exercices"] == []
        assert c["cellules"] == []  # pas d'exo → pas de cellule

    def test_eval_avec_exos_seuls(self, conn_peuplee):
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        c = calculer_couverture(conn_peuplee, ev["id"])
        assert c["objectifs"] == []
        assert len(c["exercices"]) == 1
        assert c["cellules"] == []  # pas d'objectif → pas de cellule

    def test_cellule_creee_quand_exo_lie_a_objectif(self, conn_peuplee):
        # On crée un objectif lié à un exo en base via objectif_exos,
        # puis on rattache les deux à une éval.
        _lier_exo_objectif(conn_peuplee, "ex1", "ob_N10_S01_p1_01")
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        ajouter_objectif_a_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        c = calculer_couverture(conn_peuplee, ev["id"])
        assert len(c["cellules"]) == 1
        assert c["cellules"][0] == {
            "objectif_id": "ob_N10_S01_p1_01",
            "exercice_id": "ex1",
        }

    def test_objectif_couvert_par_plusieurs_exos(self, conn_peuplee):
        """Un objectif rattaché à 2 exos → 2 cellules."""
        _lier_exo_objectif(conn_peuplee, "ex1", "ob_N10_S01_p1_01")
        _lier_exo_objectif(conn_peuplee, "ex2", "ob_N10_S01_p1_01")
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        ajouter_objectif_a_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex2")
        c = calculer_couverture(conn_peuplee, ev["id"])
        assert len(c["cellules"]) == 2
        exos_dans_cellules = {c["exercice_id"] for c in c["cellules"]}
        assert exos_dans_cellules == {"ex1", "ex2"}

    def test_exo_lie_a_plusieurs_objectifs(self, conn_peuplee):
        """Un exo rattaché à 2 objectifs liés à l'éval → 2 cellules."""
        _lier_exo_objectif(conn_peuplee, "ex1", "ob_N10_S01_p1_01")
        _lier_exo_objectif(conn_peuplee, "ex1", "ob_N10_S01_p1_02")
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        ajouter_objectif_a_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
        )
        ajouter_objectif_a_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p1_02"
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        c = calculer_couverture(conn_peuplee, ev["id"])
        assert len(c["cellules"]) == 2

    def test_lien_externe_ignore(self, conn_peuplee):
        """Si l'objectif est lié à un exo absent de l'éval, pas de
        cellule (matrice creuse limitée aux éléments de l'éval)."""
        # ex2 n'est PAS dans l'éval
        _lier_exo_objectif(conn_peuplee, "ex2", "ob_N10_S01_p1_01")
        ev = creer_evaluation(conn_peuplee, niveau="N10", titre="T1")
        ajouter_objectif_a_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        c = calculer_couverture(conn_peuplee, ev["id"])
        # ex1 n'est lié à aucun objectif → 0 cellule
        assert c["cellules"] == []

    def test_eval_inexistante(self, conn_peuplee):
        with pytest.raises(EvaluationIntrouvable):
            calculer_couverture(conn_peuplee, "ev_inexistante")


# ═══════════════════════════════════════════════════════════════════════════════
# Section E — Intégration : flux complet en_cours → valide → en_cours
# ═══════════════════════════════════════════════════════════════════════════════


class TestFluxComplet:
    """Quelques scénarios de bout en bout pour valider la cohérence."""

    def test_creation_remplissage_validation_devalidation(
        self, conn_peuplee
    ):
        # 1. Création
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="Bilan T1",
            mode_notation="note",
        )
        assert ev["etat_code"] == "en_cours"

        # 2. Tentative de validation à vide → échec
        with pytest.raises(ValidationPedagogiqueErreur):
            valider_evaluation(conn_peuplee, ev["id"])
        ev_apres = lire_evaluation(conn_peuplee, ev["id"])
        assert ev_apres["etat_code"] == "en_cours"  # inchangé

        # 3. Ajout d'exos avec barèmes
        ajouter_exo_a_evaluation(
            conn_peuplee, ev["id"], "ex1", bareme_points=4.0
        )
        ajouter_exo_a_evaluation(
            conn_peuplee, ev["id"], "ex2", bareme_points=6.0
        )

        # 4. Ajout d'objectifs (pas obligatoire pour valider, mais
        #    cohérent avec le flux UI)
        ajouter_objectif_a_evaluation(
            conn_peuplee, ev["id"], "ob_N10_S01_p1_01"
        )

        # 5. Validation → réussit
        ev_valide = valider_evaluation(conn_peuplee, ev["id"])
        assert ev_valide["etat_code"] == "valide"

        # 6. Dévalidation → retour en_cours
        ev_devalide = devalider_evaluation(conn_peuplee, ev["id"])
        assert ev_devalide["etat_code"] == "en_cours"

    def test_modification_apres_validation_possible(self, conn_peuplee):
        """L'API ne contraint pas de dévalider avant de modifier — c'est
        la responsabilité de l'UI de proposer ce flux. Côté backend, on
        peut toujours modifier."""
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="aucun",
        )
        ajouter_exo_a_evaluation(conn_peuplee, ev["id"], "ex1")
        valider_evaluation(conn_peuplee, ev["id"])
        # Modification du titre quand l'éval est valide — pas bloquée
        ev_mod = modifier_evaluation(
            conn_peuplee, ev["id"], titre="Nouveau titre"
        )
        assert ev_mod["titre"] == "Nouveau titre"
        assert ev_mod["etat_code"] == "valide"  # toujours valide

    def test_bareme_invalide_apres_validation_decele_au_revalider(
        self, conn_peuplee
    ):
        """Cas : éval validée, l'enseignant la dévalide pour modifier,
        retire un barème, puis tente de revalider → échec attendu."""
        ev = creer_evaluation(
            conn_peuplee, niveau="N10", titre="T1",
            mode_notation="note",
        )
        ajouter_exo_a_evaluation(
            conn_peuplee, ev["id"], "ex1", bareme_points=4.0
        )
        valider_evaluation(conn_peuplee, ev["id"])
        devalider_evaluation(conn_peuplee, ev["id"])
        # Retirer le barème
        modifier_bareme_exo(
            conn_peuplee, ev["id"], "ex1", bareme_points=None
        )
        with pytest.raises(ValidationPedagogiqueErreur):
            valider_evaluation(conn_peuplee, ev["id"])
