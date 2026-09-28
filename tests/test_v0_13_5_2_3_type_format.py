"""tests/test_v0_13_5_2_3_type_format.py — v0.13.5.2.3.

Tests de la déduction automatique du champ type_format des exercices,
calculé à partir de la présence de \\begin{seqQcm} dans l'énoncé.

Décisions (Laurent, v0.13.5.2.3) :
  - type_format n'est PAS un champ saisi par l'enseignant : il est
    dérivé du contenu de l'énoncé à chaque écriture.
  - Détection limitée à `enonce` (pas `corrige`, pas `remed_*`).
  - Règle binaire : présence de `\\begin{seqQcm}` ⇒ 'qcm',
    sinon 'standard'.

Couvre :
  - Helper _deduire_type_format : cas nominaux et limites
  - creer_exercice : type_format calculé à la création
  - modifier_exercice : type_format recalculé à chaque modification
  - Persistance via lire_exercices / ecrire_exercices
  - Migration de rattrapage v0.13.5.2.3 (exos pré-existants en
    type_format='standard' mais contenant un seqQcm dans l'énoncé)
"""
from __future__ import annotations
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.atomes import (
    _deduire_type_format,
    creer_exercice, modifier_exercice,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Section A — Helper _deduire_type_format
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeduireTypeFormat:
    """Le helper de détection est binaire et tolérant aux espaces."""

    def test_chaine_vide_standard(self):
        assert _deduire_type_format("") == "standard"

    def test_chaine_none_standard(self):
        # Sécurité : si quelqu'un appelle avec None, on tombe pas
        assert _deduire_type_format(None) == "standard"

    def test_enonce_classique_standard(self):
        enonce = "Calculer les expressions suivantes :\n$2 + 3 = ?$"
        assert _deduire_type_format(enonce) == "standard"

    def test_seqqcm_simple_qcm(self):
        enonce = r"\begin{seqQcm}\seqQcmQuestion{Question}\end{seqQcm}"
        assert _deduire_type_format(enonce) == "qcm"

    def test_seqqcm_avec_options_qcm(self):
        enonce = (
            r"\begin{seqQcm}[ptOK=1, ptPartiel=0.5, ptKO=0]"
            r"\seqQcmQuestion{Q1}\end{seqQcm}"
        )
        assert _deduire_type_format(enonce) == "qcm"

    def test_seqqcm_avec_espace_avant_brace_qcm(self):
        """\\begin {seqQcm} avec espace : on tolère (LaTeX aussi)."""
        enonce = r"\begin {seqQcm}\seqQcmQuestion{Q1}\end{seqQcm}"
        assert _deduire_type_format(enonce) == "qcm"

    def test_seqqcm_avec_tab_avant_brace_qcm(self):
        enonce = "\\begin\t{seqQcm}\\end{seqQcm}"
        assert _deduire_type_format(enonce) == "qcm"

    def test_seqqcm_en_milieu_de_texte_qcm(self):
        """Le seqQcm peut être précédé de texte introductif."""
        enonce = (
            "Choisissez la bonne réponse :\n"
            r"\begin{seqQcm}\seqQcmQuestion{Q1}\end{seqQcm}"
        )
        assert _deduire_type_format(enonce) == "qcm"

    def test_seqqcm_dans_commentaire_qcm(self):
        """Cas marginal documenté : un seqQcm en commentaire LaTeX est
        détecté comme QCM. On ne fait pas le travail de filtrer les
        commentaires — la présence du marqueur dans le source compte."""
        enonce = r"% \begin{seqQcm} (test)" + "\nCalculer 2+2."
        assert _deduire_type_format(enonce) == "qcm"

    def test_seqqcm_partiel_non_detecte_standard(self):
        """`seqQcm` mentionné sans `\\begin{` ne déclenche pas."""
        enonce = "On parle ici de l'environnement seqQcm sans l'utiliser."
        assert _deduire_type_format(enonce) == "standard"

    def test_begin_autre_env_standard(self):
        """`\\begin{enumerate}` ne doit pas être confondu."""
        enonce = r"\begin{enumerate}\item Question 1\end{enumerate}"
        assert _deduire_type_format(enonce) == "standard"

    def test_plusieurs_seqqcm_qcm(self):
        """Plusieurs blocs seqQcm dans le même énoncé : qcm aussi."""
        enonce = (
            r"\begin{seqQcm}\seqQcmQuestion{Q1}\end{seqQcm}"
            "\n"
            r"\begin{seqQcm}\seqQcmQuestion{Q2}\end{seqQcm}"
        )
        assert _deduire_type_format(enonce) == "qcm"


# ═══════════════════════════════════════════════════════════════════════════════
# Section B — creer_exercice : type_format calculé à la création
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreerExerciceTypeFormat:

    def test_creation_standard(self):
        liste, exo, err = creer_exercice([], {
            "serie":   "fondamental",
            "enonce":  "Calculer 2+2.",
            "corrige": "4",
        })
        assert err is None
        assert exo["type_format"] == "standard"

    def test_creation_qcm(self):
        liste, exo, err = creer_exercice([], {
            "serie":   "fondamental",
            "enonce":  r"\begin{seqQcm}\seqQcmQuestion{?}\end{seqQcm}",
            "corrige": "A",
        })
        assert err is None
        assert exo["type_format"] == "qcm"

    def test_creation_type_format_dans_data_est_ignore(self):
        """Si le client envoie type_format dans le payload, on l'ignore :
        la valeur stockée est purement dérivée de l'énoncé.
        """
        liste, exo, err = creer_exercice([], {
            "serie":       "fondamental",
            "enonce":      "Standard.",
            "corrige":     "...",
            # Le client tente de tricher en mettant 'qcm' alors que
            # l'énoncé est standard : on l'ignore.
            "type_format": "qcm",
        })
        assert err is None
        assert exo["type_format"] == "standard"

    def test_creation_qcm_avec_options(self):
        liste, exo, err = creer_exercice([], {
            "serie":   "fondamental",
            "enonce":  (
                r"\begin{seqQcm}[ptOK=1, ptPartiel=0.5, ptKO=0]"
                r"\seqQcmQuestion{Q1}\end{seqQcm}"
            ),
            "corrige": "A",
        })
        assert err is None
        assert exo["type_format"] == "qcm"


# ═══════════════════════════════════════════════════════════════════════════════
# Section C — modifier_exercice : recalcul à chaque modification
# ═══════════════════════════════════════════════════════════════════════════════


class TestModifierExerciceTypeFormat:

    def _exo_standard(self):
        liste, exo, _ = creer_exercice([], {
            "serie":   "fondamental",
            "enonce":  "Standard.",
            "corrige": "...",
        })
        return liste, exo

    def test_passage_standard_vers_qcm(self):
        """Si on remplace l'énoncé par un seqQcm, type_format passe à qcm."""
        liste, exo = self._exo_standard()
        assert exo["type_format"] == "standard"
        liste, modifie, err = modifier_exercice(liste, exo["id"], {
            "enonce": r"\begin{seqQcm}\seqQcmQuestion{Q}\end{seqQcm}",
        })
        assert err is None
        assert modifie["type_format"] == "qcm"

    def test_passage_qcm_vers_standard(self):
        """Inverse : on retire le seqQcm, on retombe en standard."""
        liste, exo, _ = creer_exercice([], {
            "serie":   "fondamental",
            "enonce":  r"\begin{seqQcm}\seqQcmQuestion{Q}\end{seqQcm}",
            "corrige": "A",
        })
        assert exo["type_format"] == "qcm"
        liste, modifie, err = modifier_exercice(liste, exo["id"], {
            "enonce": "Texte standard sans qcm.",
        })
        assert err is None
        assert modifie["type_format"] == "standard"

    def test_modification_sans_toucher_a_enonce_preserve_le_calcul(self):
        """Si on modifie le titre seul, type_format reste le bon : il
        est recalculé à partir de l'énoncé en base, qui est inchangé."""
        liste, exo, _ = creer_exercice([], {
            "serie":   "fondamental",
            "enonce":  r"\begin{seqQcm}\seqQcmQuestion{Q}\end{seqQcm}",
            "corrige": "A",
        })
        liste, modifie, err = modifier_exercice(liste, exo["id"], {
            "nom": "Nouveau titre",
        })
        assert err is None
        # type_format est recalculé depuis enonce inchangé : reste 'qcm'
        assert modifie["type_format"] == "qcm"

    def test_type_format_dans_data_ignore_aussi_en_modification(self):
        """Même règle qu'en création : type_format dans data est ignoré."""
        liste, exo = self._exo_standard()
        liste, modifie, err = modifier_exercice(liste, exo["id"], {
            # Tentative de forcer qcm sans changer l'énoncé
            "type_format": "qcm",
        })
        assert err is None
        # L'énoncé est resté 'Standard.' → type_format reste 'standard'
        assert modifie["type_format"] == "standard"


# ═══════════════════════════════════════════════════════════════════════════════
# Section D — Persistance via lire_exercices / ecrire_exercices
# ═══════════════════════════════════════════════════════════════════════════════


# Schéma minimal pour tester lire/ecrire exercices. Reprend la définition
# de schema.sql ; on garde seulement ce qui est strictement nécessaire au
# pipeline lire/ecrire (objectifs/objectif_exos peuvent être vides).
_SCHEMA_PERSIST = """
CREATE TABLE exercices (
    id                              TEXT PRIMARY KEY,
    serie                           TEXT NOT NULL DEFAULT '',
    titre                             TEXT NOT NULL DEFAULT '',
    variables                       TEXT NOT NULL DEFAULT '',
    enonce                          TEXT NOT NULL DEFAULT '',
    corrige                         TEXT NOT NULL DEFAULT '',
    niveau                          TEXT NOT NULL DEFAULT '',
    sequence                        TEXT NOT NULL DEFAULT '',
    num                             INTEGER,
    serie_code                      TEXT NOT NULL DEFAULT '',
    fichier                         TEXT NOT NULL DEFAULT '',
    etat_code                       TEXT NOT NULL DEFAULT 'en_cours',
    remed_enonce                    TEXT NOT NULL DEFAULT '',
    remed_corrige                   TEXT NOT NULL DEFAULT '',
    cadre_reponse_lignes_principal  INTEGER NOT NULL DEFAULT 0,
    cadre_reponse_lignes_remed      INTEGER NOT NULL DEFAULT 0,
    type_format                     TEXT NOT NULL DEFAULT 'standard'
);
CREATE TABLE objectifs (
    id       TEXT PRIMARY KEY,
    niveau   TEXT,
    sequence TEXT,
    code     TEXT
);
CREATE TABLE exercice_objectifs (
    exercice_id  TEXT NOT NULL REFERENCES exercices(id) ON DELETE CASCADE,
    objectif_id  TEXT NOT NULL REFERENCES objectifs(id) ON DELETE CASCADE,
    PRIMARY KEY (exercice_id, objectif_id)
);
CREATE TABLE objectif_exos (
    objectif_id TEXT NOT NULL REFERENCES objectifs(id) ON DELETE CASCADE,
    serie       TEXT NOT NULL,
    exercice_id TEXT NOT NULL REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE livret_exercices (
    livret_id    TEXT NOT NULL,
    exercice_id  TEXT NOT NULL,
    PRIMARY KEY (livret_id, exercice_id)
);
"""


@pytest.fixture
def store(tmp_path, monkeypatch):
    """SqliteStore réel pointant sur une BDD test minimale."""
    from persistence.sqlite_store import SqliteStore

    db_path = tmp_path / "test.db"
    # Initialiser un schéma minimal au lieu du schema.sql complet :
    # le init de SqliteStore va exécuter schema.sql + post_ddl, mais on
    # peut court-circuiter en créant les tables avant.
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_PERSIST)
    conn.commit()
    conn.close()

    # Patch : on shunte _init_db pour ne pas écraser notre schéma minimal.
    # Le but du test est d'isoler lire_exercices/ecrire_exercices.
    monkeypatch.setattr(SqliteStore, "_init_db", lambda self: None)

    s = SqliteStore(data_dir=tmp_path)
    s.db_path = db_path  # forcer le chemin sur notre BDD test
    # Réinitialiser le _conn() interne pour qu'il pointe sur la bonne BDD
    return s


class TestPersistanceTypeFormat:

    def test_ecrire_puis_lire_standard(self, store):
        exo = {
            "id": "ex_test_standard",
            "serie": "fondamental",
            "nom": "Test",
            "variables": "",
            "enonce": "Énoncé standard.",
            "corrige": "Corrigé.",
            "type_format": "standard",
        }
        store.ecrire_exercices([exo])
        liste = store.lire_exercices()
        assert len(liste) == 1
        assert liste[0]["type_format"] == "standard"

    def test_ecrire_puis_lire_qcm(self, store):
        exo = {
            "id": "ex_test_qcm",
            "serie": "fondamental",
            "nom": "Test QCM",
            "variables": "",
            "enonce": r"\begin{seqQcm}\seqQcmQuestion{Q1}\end{seqQcm}",
            "corrige": "A",
            "type_format": "qcm",
        }
        store.ecrire_exercices([exo])
        liste = store.lire_exercices()
        assert len(liste) == 1
        assert liste[0]["type_format"] == "qcm"

    def test_default_standard_si_type_format_absent(self, store):
        """Si un appelant (ex: scanner LaTeX) ne fournit pas type_format,
        on stocke 'standard' par défaut. La sauvegarde suivante via l'UI
        recalculera la vraie valeur."""
        exo = {
            "id": "ex_test_sans_tf",
            "serie": "fondamental",
            "nom": "Test sans tf",
            "variables": "",
            "enonce": "Énoncé.",
            "corrige": "Corrigé.",
            # pas de type_format
        }
        store.ecrire_exercices([exo])
        liste = store.lire_exercices()
        assert liste[0]["type_format"] == "standard"

    def test_update_modifie_type_format(self, store):
        """Un UPDATE doit faire passer type_format de standard à qcm."""
        # Création initiale (standard)
        exo = {
            "id": "ex_evol",
            "serie": "fondamental",
            "nom": "Évolution",
            "variables": "",
            "enonce": "Texte initial.",
            "corrige": "...",
            "type_format": "standard",
        }
        store.ecrire_exercices([exo])

        # Modification : on remplace l'énoncé par un seqQcm
        exo["enonce"] = r"\begin{seqQcm}\seqQcmQuestion{Q}\end{seqQcm}"
        exo["type_format"] = "qcm"
        store.ecrire_exercices([exo])

        liste = store.lire_exercices()
        assert len(liste) == 1
        assert liste[0]["type_format"] == "qcm"


# ═══════════════════════════════════════════════════════════════════════════════
# Section E — Migration de rattrapage v0.13.5.2.3
# ═══════════════════════════════════════════════════════════════════════════════


class TestMigrationRattrapage:
    """Vérifie que la migration `_migrer_schema_post_ddl` corrige
    rétroactivement les type_format='standard' qui devraient être 'qcm'."""

    def _bdd_avec_exos_pre_existants(self, tmp_path, exos):
        """Crée une BDD minimale, injecte les exos passés en paramètre
        avec type_format='standard' systématique (état pré-rattrapage)."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_PERSIST)
        for exo_id, enonce in exos:
            conn.execute(
                "INSERT INTO exercices (id, serie, enonce, corrige, "
                "type_format) VALUES (?, 'fondamental', ?, '', 'standard')",
                (exo_id, enonce),
            )
        conn.commit()
        return conn

    def test_rattrapage_passe_qcm_a_qcm(self, tmp_path):
        from persistence.sqlite_store import SqliteStore

        conn = self._bdd_avec_exos_pre_existants(tmp_path, [
            ("ex_standard", "Énoncé tout normal."),
            ("ex_qcm",      r"\begin{seqQcm}\seqQcmQuestion{Q}\end{seqQcm}"),
        ])

        # Avant migration : les deux sont 'standard'
        rows = conn.execute(
            "SELECT id, type_format FROM exercices ORDER BY id"
        ).fetchall()
        assert {r[0]: r[1] for r in rows} == {
            "ex_qcm": "standard", "ex_standard": "standard"
        }

        # Application du rattrapage (on appelle directement la méthode)
        store = SqliteStore.__new__(SqliteStore)
        store._migrer_schema_post_ddl(conn)

        # Après : seul ex_qcm est passé à 'qcm', ex_standard reste 'standard'
        rows = conn.execute(
            "SELECT id, type_format FROM exercices ORDER BY id"
        ).fetchall()
        assert {r[0]: r[1] for r in rows} == {
            "ex_qcm": "qcm", "ex_standard": "standard"
        }
        conn.close()

    def test_rattrapage_idempotent(self, tmp_path):
        """Re-appliquer le rattrapage ne change rien."""
        from persistence.sqlite_store import SqliteStore

        conn = self._bdd_avec_exos_pre_existants(tmp_path, [
            ("ex_qcm", r"\begin{seqQcm}\seqQcmQuestion{Q}\end{seqQcm}"),
        ])

        store = SqliteStore.__new__(SqliteStore)
        store._migrer_schema_post_ddl(conn)
        # 1er passage : standard → qcm
        v1 = conn.execute(
            "SELECT type_format FROM exercices WHERE id='ex_qcm'"
        ).fetchone()[0]
        assert v1 == "qcm"

        # 2e passage : doit rester qcm, pas de modification
        store._migrer_schema_post_ddl(conn)
        v2 = conn.execute(
            "SELECT type_format FROM exercices WHERE id='ex_qcm'"
        ).fetchone()[0]
        assert v2 == "qcm"
        conn.close()

    def test_rattrapage_ne_touche_pas_exos_deja_corrects(self, tmp_path):
        """Si type_format est déjà à 'qcm' au départ, le rattrapage
        ne fait rien (idempotence sur cas mixte)."""
        from persistence.sqlite_store import SqliteStore

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_PERSIST)
        # Cas 1 : déjà 'qcm' avec contenu QCM (correct, ne pas toucher)
        conn.execute(
            "INSERT INTO exercices (id, serie, enonce, corrige, type_format) "
            "VALUES ('ex1', 'fondamental', "
            "'\\begin{seqQcm}\\seqQcmQuestion{Q}\\end{seqQcm}', '', 'qcm')"
        )
        # Cas 2 : 'standard' avec contenu QCM (à corriger)
        conn.execute(
            "INSERT INTO exercices (id, serie, enonce, corrige, type_format) "
            "VALUES ('ex2', 'fondamental', "
            "'\\begin{seqQcm}\\seqQcmQuestion{Q}\\end{seqQcm}', '', 'standard')"
        )
        # Cas 3 : 'standard' avec contenu standard (correct, ne pas toucher)
        conn.execute(
            "INSERT INTO exercices (id, serie, enonce, corrige, type_format) "
            "VALUES ('ex3', 'fondamental', 'Calculer 2+2.', '', 'standard')"
        )
        conn.commit()

        store = SqliteStore.__new__(SqliteStore)
        store._migrer_schema_post_ddl(conn)

        rows = conn.execute(
            "SELECT id, type_format FROM exercices ORDER BY id"
        ).fetchall()
        assert {r[0]: r[1] for r in rows} == {
            "ex1": "qcm",        # inchangé
            "ex2": "qcm",        # corrigé
            "ex3": "standard",   # inchangé
        }
        conn.close()
