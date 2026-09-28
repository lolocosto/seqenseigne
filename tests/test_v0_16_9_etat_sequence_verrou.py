"""tests/test_v0_16_9_etat_sequence_verrou.py — v0.16.9

Tests du régime « état validable + verrou » de la séquence-niveau :
  - lire_etat_sequence / valider / devalider (cycle de vie de l'état) ;
  - hook de validation pédagogique strict (_valider_sequence_hook), ses 4
    règles, et l'agrégation des raisons ;
  - assert_sequence_modifiable (verrou) et ses variantes par partie/objectif.

On construit un schéma minimal réaliste INCLUANT etat_code et objectif_exos.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.v2_edition import (  # noqa: E402
    lire_etat_sequence,
    valider_sequence_niveau,
    devalider_sequence_niveau,
    changer_etat_sequence_niveau,
    assert_sequence_modifiable,
    assert_sequence_modifiable_par_partie,
    assert_sequence_modifiable_par_objectif,
    SequenceVerrouillee,
    ValidationSequenceErreur,
    EtatSequenceInvalide,
    SequenceParNiveauIntrouvable,
    code_objectif_connaitre,
)

_SCHEMA = """
CREATE TABLE sequences_par_niveau (
    id            TEXT PRIMARY KEY,
    niveau        TEXT NOT NULL,
    sequence_code TEXT NOT NULL,
    parametres    TEXT NOT NULL DEFAULT '',
    etat_code     TEXT NOT NULL DEFAULT 'en_cours',
    UNIQUE (niveau, sequence_code)
);
CREATE TABLE sequence_parties (
    id                     TEXT PRIMARY KEY,
    sequence_par_niveau_id TEXT NOT NULL,
    numero                 INTEGER NOT NULL,
    nb_seances_R_AE        REAL NOT NULL DEFAULT 0
);
CREATE TABLE objectifs (
    id         TEXT PRIMARY KEY,
    partie_id  TEXT NOT NULL,
    code       TEXT NOT NULL,
    nom        TEXT NOT NULL DEFAULT '',
    methode_id TEXT,
    critere_F  TEXT NOT NULL DEFAULT '',
    critere_A  TEXT NOT NULL DEFAULT '',
    critere_E  TEXT NOT NULL DEFAULT '',
    fin_cycle  TEXT NOT NULL DEFAULT 'N',
    nb_seances REAL NOT NULL DEFAULT 0,
    UNIQUE (partie_id, code)
);
CREATE TABLE objectif_exos (
    objectif_id TEXT NOT NULL,
    serie       TEXT NOT NULL,
    exercice_id TEXT NOT NULL,
    ordre       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, serie, exercice_id)
);
"""


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _sn(conn, sn_id="sn_1", niveau="N10", seq="S01", etat="en_cours"):
    conn.execute(
        "INSERT INTO sequences_par_niveau (id, niveau, sequence_code, etat_code) "
        "VALUES (?, ?, ?, ?)",
        (sn_id, niveau, seq, etat),
    )
    return sn_id


def _partie(conn, pid, sn_id, numero):
    conn.execute(
        "INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
        "VALUES (?, ?, ?)",
        (pid, sn_id, numero),
    )
    return pid


def _objectif(conn, oid, pid, code, nom="Obj", f="cF", a="cA", e="cE"):
    conn.execute(
        "INSERT INTO objectifs (id, partie_id, code, nom, critere_F, critere_A, "
        "critere_E) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (oid, pid, code, nom, f, a, e),
    )
    return oid


def _exo(conn, oid, serie, exo_id, ordre=1):
    conn.execute(
        "INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) "
        "VALUES (?, ?, ?, ?)",
        (oid, serie, exo_id, ordre),
    )


def _sequence_complete_valide(conn):
    """Construit une séquence qui DOIT passer les 4 règles du hook.

    1 partie (numero=1), objectif Cours (code '01') nommé + 3 critères,
    1 objectif exo (code '02') nommé + 3 critères + 1 exo dans F, A et E.
    """
    sn = _sn(conn)
    p = _partie(conn, "p1", sn, 1)
    code_cours = code_objectif_connaitre(1)  # '01'
    _objectif(conn, "oc", p, code_cours, nom="Cours")
    _objectif(conn, "oe", p, "02", nom="Calculer")
    for serie in ("F", "A", "E"):
        _exo(conn, "oe", serie, f"ex_{serie}")
    return sn


# ── Cycle de vie de l'état ───────────────────────────────────────────────────

class TestCycleDeVieEtat:
    def test_etat_initial_en_cours(self):
        conn = _conn()
        sn = _sn(conn)
        assert lire_etat_sequence(conn, sn) == "en_cours"

    def test_lire_etat_introuvable_leve(self):
        conn = _conn()
        with pytest.raises(SequenceParNiveauIntrouvable):
            lire_etat_sequence(conn, "sn_inexistant")

    def test_valider_puis_devalider(self):
        conn = _conn()
        sn = _sequence_complete_valide(conn)
        rep = valider_sequence_niveau(conn, sn)
        assert rep["etat_code"] == "valide"
        assert lire_etat_sequence(conn, sn) == "valide"
        rep2 = devalider_sequence_niveau(conn, sn)
        assert rep2["etat_code"] == "en_cours"
        assert lire_etat_sequence(conn, sn) == "en_cours"

    def test_valider_idempotent(self):
        conn = _conn()
        sn = _sequence_complete_valide(conn)
        valider_sequence_niveau(conn, sn)
        # Re-valider ne doit pas relancer le hook ni échouer.
        rep = valider_sequence_niveau(conn, sn)
        assert rep["etat_code"] == "valide"

    def test_changer_etat_code_invalide(self):
        conn = _conn()
        sn = _sn(conn)
        with pytest.raises(EtatSequenceInvalide):
            changer_etat_sequence_niveau(conn, sn, "brouillon")


# ── Hook de validation pédagogique (4 règles) ───────────────────────────────

class TestHookValidation:
    def test_sequence_complete_passe(self):
        conn = _conn()
        sn = _sequence_complete_valide(conn)
        # Ne lève pas.
        valider_sequence_niveau(conn, sn)

    def test_regle1_aucune_partie(self):
        conn = _conn()
        sn = _sn(conn)
        with pytest.raises(ValidationSequenceErreur) as ei:
            valider_sequence_niveau(conn, sn)
        assert any("aucune partie" in r.lower() for r in ei.value.raisons)

    def test_regle2_partie_sans_objectif_exo(self):
        conn = _conn()
        sn = _sn(conn)
        p = _partie(conn, "p1", sn, 1)
        # Seulement le Cours, pas d'objectif exo.
        _objectif(conn, "oc", p, code_objectif_connaitre(1), nom="Cours")
        with pytest.raises(ValidationSequenceErreur) as ei:
            valider_sequence_niveau(conn, sn)
        assert any("aucun objectif d'exercices" in r.lower()
                   for r in ei.value.raisons)

    def test_regle3_critere_manquant(self):
        conn = _conn()
        sn = _sn(conn)
        p = _partie(conn, "p1", sn, 1)
        _objectif(conn, "oc", p, code_objectif_connaitre(1), nom="Cours")
        # Objectif exo avec critère E vide.
        _objectif(conn, "oe", p, "02", nom="Calculer", e="")
        for serie in ("F", "A", "E"):
            _exo(conn, "oe", serie, f"ex_{serie}")
        with pytest.raises(ValidationSequenceErreur) as ei:
            valider_sequence_niveau(conn, sn)
        assert any("critère E" in r for r in ei.value.raisons)

    def test_regle3_nom_manquant(self):
        conn = _conn()
        sn = _sn(conn)
        p = _partie(conn, "p1", sn, 1)
        _objectif(conn, "oc", p, code_objectif_connaitre(1), nom="")
        _objectif(conn, "oe", p, "02", nom="Calculer")
        for serie in ("F", "A", "E"):
            _exo(conn, "oe", serie, f"ex_{serie}")
        with pytest.raises(ValidationSequenceErreur) as ei:
            valider_sequence_niveau(conn, sn)
        assert any("n'a pas de nom" in r for r in ei.value.raisons)

    def test_regle4_serie_exo_manquante(self):
        conn = _conn()
        sn = _sn(conn)
        p = _partie(conn, "p1", sn, 1)
        _objectif(conn, "oc", p, code_objectif_connaitre(1), nom="Cours")
        _objectif(conn, "oe", p, "02", nom="Calculer")
        # Seulement F et A : E manque.
        _exo(conn, "oe", "F", "ex_F")
        _exo(conn, "oe", "A", "ex_A")
        with pytest.raises(ValidationSequenceErreur) as ei:
            valider_sequence_niveau(conn, sn)
        assert any("série E" in r for r in ei.value.raisons)

    def test_cours_sans_exo_est_ok(self):
        # L'objectif Cours n'est PAS soumis à la règle 4 (pas d'exos requis).
        conn = _conn()
        sn = _sequence_complete_valide(conn)
        # Le Cours 'oc' n'a aucun exo : la séquence doit quand même valider.
        valider_sequence_niveau(conn, sn)

    def test_raisons_agregees_multiples(self):
        conn = _conn()
        sn = _sn(conn)
        p = _partie(conn, "p1", sn, 1)
        # Objectif exo sans nom, sans critères, sans exos → plusieurs raisons.
        _objectif(conn, "oe", p, "02", nom="", f="", a="", e="")
        with pytest.raises(ValidationSequenceErreur) as ei:
            valider_sequence_niveau(conn, sn)
        # nom + 3 critères + 1 raison (séries F,A,E groupées) = 5 raisons.
        assert len(ei.value.raisons) >= 5
        assert any("n'a pas de nom" in r for r in ei.value.raisons)
        assert any("série" in r for r in ei.value.raisons)


# ── Verrou (assert_sequence_modifiable) ──────────────────────────────────────

class TestVerrou:
    def test_modifiable_si_en_cours(self):
        conn = _conn()
        sn = _sn(conn, etat="en_cours")
        # Ne lève pas.
        assert_sequence_modifiable(conn, sn)

    def test_verrouille_si_valide(self):
        conn = _conn()
        sn = _sn(conn, etat="valide")
        with pytest.raises(SequenceVerrouillee) as ei:
            assert_sequence_modifiable(conn, sn)
        assert ei.value.code == "item_verrouille"

    def test_introuvable_ne_leve_pas_verrou(self):
        # Tolérance : un id inconnu ne doit pas masquer le futur 404 par un 409.
        conn = _conn()
        assert_sequence_modifiable(conn, "sn_inexistant")  # ne lève pas

    def test_verrou_par_partie(self):
        conn = _conn()
        sn = _sn(conn, etat="valide")
        _partie(conn, "p1", sn, 1)
        with pytest.raises(SequenceVerrouillee):
            assert_sequence_modifiable_par_partie(conn, "p1")

    def test_verrou_par_objectif(self):
        conn = _conn()
        sn = _sn(conn, etat="valide")
        p = _partie(conn, "p1", sn, 1)
        _objectif(conn, "oe", p, "02", nom="X")
        with pytest.raises(SequenceVerrouillee):
            assert_sequence_modifiable_par_objectif(conn, "oe")

    def test_verrou_par_partie_en_cours_ok(self):
        conn = _conn()
        sn = _sn(conn, etat="en_cours")
        _partie(conn, "p1", sn, 1)
        assert_sequence_modifiable_par_partie(conn, "p1")  # ne lève pas
