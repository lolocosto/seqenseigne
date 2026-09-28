"""tests/test_v0_10_assemblage.py — v0.10.

Tests des nouveaux services et routes de l'atelier d'assemblage :
  - reordonner_parties (drag & drop des parties)
  - reordonner_objectifs_dans_partie (drag & drop des objectifs)
  - activer_objectif_connaitre (création de l'obj '0X' avec critères pré-remplis)
  - exos R/EA au niveau partie (ajouter / retirer / lister / réordonner)
  - état UI persistant (objectif ouvert)
  - intégration : v2_lecture renvoie maintenant exos_revision_approche et etat_ui

Architecture : on suit le pattern de test_R4e2_edition / test_R4e4b_edition_exos :
  - une fixture `conn` SQLite mémoire, schéma minimal mais incluant les
    nouvelles tables v0.10
  - une fixture `base_peuplee` avec 2 séquences, des parties, des objectifs,
    des exercices factices
  - tests services + tests routes via client Flask
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Schéma minimal pour les tests unitaires ──────────────────────────────────

_SCHEMA_TEST = """
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
    UNIQUE (sequence_par_niveau_id, numero)
);
CREATE TABLE objectifs (
    id         TEXT PRIMARY KEY,
    partie_id  TEXT NOT NULL
               REFERENCES sequence_parties(id) ON DELETE CASCADE,
    code       TEXT NOT NULL,
    nom        TEXT NOT NULL DEFAULT '',
    methode_id TEXT,
    critere_F  TEXT NOT NULL DEFAULT '',
    critere_A  TEXT NOT NULL DEFAULT '',
    critere_E  TEXT NOT NULL DEFAULT '',
    fin_cycle  TEXT NOT NULL DEFAULT 'N',
    UNIQUE (partie_id, code)
);
CREATE TABLE exercices (
    id           TEXT PRIMARY KEY,
    titre          TEXT NOT NULL DEFAULT '',
    fichier      TEXT NOT NULL DEFAULT '',
    niveau       TEXT NOT NULL DEFAULT '',
    sequence     TEXT NOT NULL DEFAULT '',
    num          INTEGER,
    serie_code   TEXT NOT NULL DEFAULT '',
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE objectif_exos (
    objectif_id    TEXT NOT NULL
                   REFERENCES objectifs(id) ON DELETE CASCADE,
    serie          TEXT NOT NULL,
    exercice_id    TEXT NOT NULL
                   REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre          INTEGER NOT NULL DEFAULT 0,
    origin_niveau  TEXT,
    origin_seq     TEXT,
    origin_serie   TEXT,
    origin_num     INTEGER,
    PRIMARY KEY (objectif_id, serie, exercice_id),
    UNIQUE (objectif_id, serie, ordre)
);
CREATE TABLE partie_exos_revision_approche (
    partie_id      TEXT NOT NULL
                   REFERENCES sequence_parties(id) ON DELETE CASCADE,
    type           TEXT NOT NULL,
    exercice_id    TEXT NOT NULL
                   REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre          INTEGER NOT NULL DEFAULT 0,
    origin_niveau  TEXT,
    origin_seq     TEXT,
    origin_serie   TEXT,
    origin_num     INTEGER,
    PRIMARY KEY (partie_id, type, exercice_id),
    UNIQUE (partie_id, type, ordre)
);
CREATE TABLE ui_etat_atelier_sequence (
    sequence_par_niveau_id TEXT PRIMARY KEY
                           REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    objectif_ouvert_id     TEXT REFERENCES objectifs(id) ON DELETE SET NULL,
    derniere_maj           TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE notions (
    id     TEXT PRIMARY KEY,
    titre  TEXT NOT NULL DEFAULT '',
    corps  TEXT NOT NULL DEFAULT '',
    niveau TEXT NOT NULL DEFAULT '',
    sequence TEXT NOT NULL DEFAULT '',
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE objectif_notions (
    objectif_id TEXT NOT NULL,
    notion_id   TEXT NOT NULL,
    ordre       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, notion_id)
);
CREATE TABLE partie_precedences (
    partie_id        TEXT NOT NULL
                     REFERENCES sequence_parties(id) ON DELETE CASCADE,
    precedent_niveau TEXT NOT NULL,
    precedent_seq    TEXT NOT NULL,
    PRIMARY KEY (partie_id, precedent_niveau, precedent_seq)
);
CREATE TABLE methodes (
    id        TEXT PRIMARY KEY,
    titre     TEXT NOT NULL DEFAULT '',
    niveau    TEXT NOT NULL DEFAULT '',
    sequence  TEXT NOT NULL DEFAULT '',
    fichier   TEXT NOT NULL DEFAULT '',
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
-- Tables nécessaires aux jointures de v2_lecture._charger_sequence_par_niveau
-- (LEFT JOIN avec sequences_du_cycle et themes pour enrichir avec nom et thème).
-- Vides dans les tests.
CREATE TABLE themes (
    id           TEXT PRIMARY KEY,
    code         TEXT NOT NULL DEFAULT '',
    nom          TEXT NOT NULL DEFAULT '',
    code_couleur TEXT NOT NULL DEFAULT ''
);
CREATE TABLE sequences_du_cycle (
    id         TEXT PRIMARY KEY,
    code       TEXT NOT NULL,
    nom        TEXT NOT NULL DEFAULT '',
    numero     INTEGER,
    theme_id   TEXT
);
-- v0.10.2 : précédences au niveau séquence-niveau
CREATE TABLE sequence_par_niveau_precedences (
    sequence_par_niveau_id TEXT NOT NULL
                           REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    precedent_niveau       TEXT NOT NULL,
    precedent_seq          TEXT NOT NULL,
    ordre                  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (sequence_par_niveau_id, precedent_niveau, precedent_seq)
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
def base_peuplee(conn):
    """État de référence :
        sn_A : N11/S03 avec 3 parties (pt_A1 #1, pt_A2 #2, pt_A3 #3)
               pt_A1 a obj ob_A1_01 (code '01' Connaître), ob_A1_02 (code '02')
               pt_A2 a obj ob_A2_11 (code '11' Connaître), ob_A2_12 (code '12')
               pt_A3 a obj ob_A3_22 (code '22') — pas de Connaître, c'est OK
        sn_B : N10/S03 avec 1 partie (pt_B1 #1) avec obj ob_B1_01 (code '01')
        sn_vide : N12/S05 sans aucune partie

        Exercices : ex_1 à ex_5 dans la séquence courante, ex_R1, ex_R2 du n-1
    """
    conn.executescript("""
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
            ('sn_A', 'N11', 'S03'),
            ('sn_B', 'N10', 'S03'),
            ('sn_vide', 'N12', 'S05');

        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
            ('pt_A1', 'sn_A', 1),
            ('pt_A2', 'sn_A', 2),
            ('pt_A3', 'sn_A', 3),
            ('pt_B1', 'sn_B', 1);

        INSERT INTO objectifs (id, partie_id, code, nom) VALUES
            ('ob_A1_01', 'pt_A1', '01', 'Cours partie 1'),
            ('ob_A1_02', 'pt_A1', '02', 'Obj 02'),
            ('ob_A2_11', 'pt_A2', '11', 'Cours partie 2'),
            ('ob_A2_12', 'pt_A2', '12', 'Obj 12'),
            ('ob_A3_22', 'pt_A3', '22', 'Obj 22'),
            ('ob_B1_01', 'pt_B1', '01', 'Cours B1');

        INSERT INTO exercices (id, titre, fichier, niveau, sequence, num, serie_code) VALUES
            ('ex_1', 'Exo 1', 'N11_S03_F01.tex', 'N11', 'S03', 1, 'F'),
            ('ex_2', 'Exo 2', 'N11_S03_F02.tex', 'N11', 'S03', 2, 'F'),
            ('ex_3', 'Exo 3', 'N11_S03_EA01.tex', 'N11', 'S03', 1, 'AE'),
            ('ex_4', 'Exo 4', 'N11_S03_EA02.tex', 'N11', 'S03', 2, 'AE'),
            ('ex_5', 'Exo 5', 'N11_S03_A01.tex', 'N11', 'S03', 1, 'A'),
            ('ex_R1', 'Rev 1', 'N10_S03_A01.tex', 'N10', 'S03', 1, 'A'),
            ('ex_R2', 'Rev 2', 'N10_S03_A02.tex', 'N10', 'S03', 2, 'A');
    """)
    conn.commit()
    return conn


# ═════════════════════════════════════════════════════════════════════════════
# 1. code_objectif_connaitre — helper pur
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    code_objectif_connaitre,
    NumeroPartieInvalide,
)


class TestCodeObjectifConnaitre:
    @pytest.mark.parametrize("numero,attendu", [
        (1, "01"),
        (2, "11"),
        (3, "21"),
        (4, "31"),
        (10, "91"),
    ])
    def test_codes_canoniques(self, numero, attendu):
        assert code_objectif_connaitre(numero) == attendu

    @pytest.mark.parametrize("invalide", [0, -1, "abc", None])
    def test_numeros_invalides_levent(self, invalide):
        with pytest.raises(NumeroPartieInvalide):
            code_objectif_connaitre(invalide)


# ═════════════════════════════════════════════════════════════════════════════
# 2. reordonner_parties
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    reordonner_parties,
    SequenceParNiveauIntrouvable,
    ReordonnancementInvalide,
)


class TestReordonnerParties:
    def test_permutation_simple(self, base_peuplee):
        # Inverse pt_A1 et pt_A3 (1↔3), pt_A2 reste à 2
        rep = reordonner_parties(
            base_peuplee, "sn_A", ["pt_A3", "pt_A2", "pt_A1"],
        )
        assert rep == [
            {"id": "pt_A3", "numero": 1},
            {"id": "pt_A2", "numero": 2},
            {"id": "pt_A1", "numero": 3},
        ]
        # Vérification BDD
        nums = {
            r["id"]: r["numero"]
            for r in base_peuplee.execute(
                "SELECT id, numero FROM sequence_parties "
                "WHERE sequence_par_niveau_id = ?",
                ("sn_A",),
            )
        }
        assert nums == {"pt_A1": 3, "pt_A2": 2, "pt_A3": 1}

    def test_no_op_si_meme_ordre(self, base_peuplee):
        rep = reordonner_parties(
            base_peuplee, "sn_A", ["pt_A1", "pt_A2", "pt_A3"],
        )
        assert [p["numero"] for p in rep] == [1, 2, 3]

    def test_codes_objectifs_pas_renumerotes(self, base_peuplee):
        """Après un swap pt_A1↔pt_A3, les codes des objectifs restent
        tels quels (volonté : la fonction est bas niveau). Le frontend
        appellera reordonner_objectifs_dans_partie ensuite si besoin."""
        reordonner_parties(
            base_peuplee, "sn_A", ["pt_A3", "pt_A2", "pt_A1"],
        )
        # ob_A1_01 a toujours le code '01' (mais sa partie est maintenant #3)
        row = base_peuplee.execute(
            "SELECT code FROM objectifs WHERE id = ?", ("ob_A1_01",)
        ).fetchone()
        assert row["code"] == "01"

    def test_sequence_inexistante_404(self, base_peuplee):
        with pytest.raises(SequenceParNiveauIntrouvable):
            reordonner_parties(base_peuplee, "sn_inconnu", [])

    def test_liste_pas_liste(self, base_peuplee):
        with pytest.raises(ReordonnancementInvalide):
            reordonner_parties(base_peuplee, "sn_A", "pas_une_liste")

    def test_doublons_dans_liste(self, base_peuplee):
        with pytest.raises(ReordonnancementInvalide):
            reordonner_parties(
                base_peuplee, "sn_A", ["pt_A1", "pt_A1", "pt_A2"],
            )

    def test_partie_manquante(self, base_peuplee):
        with pytest.raises(ReordonnancementInvalide) as ei:
            reordonner_parties(base_peuplee, "sn_A", ["pt_A1", "pt_A2"])
        assert "pt_A3" in ei.value.details["manquants"]

    def test_partie_inconnue(self, base_peuplee):
        with pytest.raises(ReordonnancementInvalide) as ei:
            reordonner_parties(
                base_peuplee, "sn_A",
                ["pt_A1", "pt_A2", "pt_A3", "pt_BIDON"],
            )
        assert "pt_BIDON" in ei.value.details["inconnus"]

    def test_sequence_vide_liste_vide(self, base_peuplee):
        # sn_vide n'a aucune partie → liste vide doit passer
        rep = reordonner_parties(base_peuplee, "sn_vide", [])
        assert rep == []


# ═════════════════════════════════════════════════════════════════════════════
# 3. reordonner_objectifs_dans_partie
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    reordonner_objectifs_dans_partie,
    PartieIntrouvable,
)


class TestReordonnerObjectifsDansPartie:
    def test_sans_connaitre_renomme_codes(self, base_peuplee):
        """pt_A3 a juste ob_A3_22 (pas de Connaître). Si on ajoute un
        autre obj et qu'on les permute, les codes doivent prendre 22, 23
        en partie 3."""
        # Ajout d'un 2e obj dans pt_A3
        base_peuplee.execute(
            "INSERT INTO objectifs (id, partie_id, code, nom) "
            "VALUES ('ob_A3_23', 'pt_A3', '23', 'Obj 23')"
        )
        # Permutation : ob_A3_23 d'abord, ob_A3_22 ensuite
        rep = reordonner_objectifs_dans_partie(
            base_peuplee, "pt_A3", ["ob_A3_23", "ob_A3_22"],
        )
        # En partie 3, prefixe = 2, donc codes attendus '22' puis '23'
        assert rep == [
            {"id": "ob_A3_23", "code": "22"},
            {"id": "ob_A3_22", "code": "23"},
        ]
        # BDD
        rows = {
            r["id"]: r["code"]
            for r in base_peuplee.execute(
                "SELECT id, code FROM objectifs WHERE partie_id = ?",
                ("pt_A3",),
            )
        }
        assert rows == {"ob_A3_23": "22", "ob_A3_22": "23"}

    def test_avec_connaitre_doit_etre_premier(self, base_peuplee):
        """pt_A1 a ob_A1_01 (Connaître) et ob_A1_02. Connaître doit
        rester en premier."""
        rep = reordonner_objectifs_dans_partie(
            base_peuplee, "pt_A1", ["ob_A1_01", "ob_A1_02"],
        )
        assert rep == [
            {"id": "ob_A1_01", "code": "01"},
            {"id": "ob_A1_02", "code": "02"},
        ]

    def test_connaitre_pas_premier_leve(self, base_peuplee):
        """pt_A1 a un Connaître ; tenter de le mettre en 2e doit lever."""
        with pytest.raises(ReordonnancementInvalide) as ei:
            reordonner_objectifs_dans_partie(
                base_peuplee, "pt_A1", ["ob_A1_02", "ob_A1_01"],
            )
        assert "Connaître" in str(ei.value)

    def test_renumerotation_partie_2(self, base_peuplee):
        """En partie 2, prefixe = 1, codes attendus '11' puis '12'."""
        # Ajout d'un 3e obj dans pt_A2 pour avoir 3 obj
        base_peuplee.execute(
            "INSERT INTO objectifs (id, partie_id, code, nom) "
            "VALUES ('ob_A2_13', 'pt_A2', '13', 'Obj 13')"
        )
        rep = reordonner_objectifs_dans_partie(
            base_peuplee, "pt_A2",
            ["ob_A2_11", "ob_A2_13", "ob_A2_12"],
        )
        # Connaître reste à 11, puis 12, puis 13
        assert rep == [
            {"id": "ob_A2_11", "code": "11"},
            {"id": "ob_A2_13", "code": "12"},
            {"id": "ob_A2_12", "code": "13"},
        ]

    def test_partie_inexistante(self, base_peuplee):
        with pytest.raises(PartieIntrouvable):
            reordonner_objectifs_dans_partie(base_peuplee, "pt_INC", [])

    def test_objectif_manquant(self, base_peuplee):
        with pytest.raises(ReordonnancementInvalide):
            reordonner_objectifs_dans_partie(
                base_peuplee, "pt_A1", ["ob_A1_01"],
            )

    def test_doublons(self, base_peuplee):
        with pytest.raises(ReordonnancementInvalide):
            reordonner_objectifs_dans_partie(
                base_peuplee, "pt_A1", ["ob_A1_01", "ob_A1_01"],
            )


# ═════════════════════════════════════════════════════════════════════════════
# 4. activer_objectif_connaitre
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    activer_objectif_connaitre,
    ObjectifConnaitreDejaPresent,
)


class TestActiverObjectifConnaitre:
    def test_partie_sans_connaitre_creation_ok(self, base_peuplee):
        """pt_A3 n'a pas de Connaître → on peut le créer."""
        rep = activer_objectif_connaitre(
            base_peuplee, "pt_A3",
            critere_F="A noté la trace écrite en classe.",
            critere_A="A complété les fiches de résumé.",
            critere_E="Sait résumer le cours à l'oral.",
        )
        # Code attendu : partie 3 → '21'
        assert rep["code"] == "21"
        assert rep["partie_id"] == "pt_A3"
        assert rep["nom"] == "Connaître les notions et les méthodes"
        assert rep["critere_F"] == "A noté la trace écrite en classe."
        assert rep["critere_A"] == "A complété les fiches de résumé."
        assert rep["critere_E"] == "Sait résumer le cours à l'oral."

    def test_partie_avec_connaitre_409(self, base_peuplee):
        """pt_A1 a déjà '01' → 409."""
        with pytest.raises(ObjectifConnaitreDejaPresent) as ei:
            activer_objectif_connaitre(base_peuplee, "pt_A1")
        assert ei.value.details["code_existant"] == "01"

    def test_critères_par_defaut_vides(self, base_peuplee):
        """Sans paramètres, les critères sont vides."""
        rep = activer_objectif_connaitre(base_peuplee, "pt_A3")
        assert rep["critere_F"] == ""
        assert rep["critere_A"] == ""
        assert rep["critere_E"] == ""

    def test_partie_inexistante(self, base_peuplee):
        with pytest.raises(PartieIntrouvable):
            activer_objectif_connaitre(base_peuplee, "pt_INC")

    def test_nom_personnalise(self, base_peuplee):
        rep = activer_objectif_connaitre(
            base_peuplee, "pt_A3", nom="Mon nom à moi",
        )
        assert rep["nom"] == "Mon nom à moi"


# ═════════════════════════════════════════════════════════════════════════════
# 5. Exos R/EA au niveau partie
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    lister_exos_revision_approche,
    ajouter_exo_revision_approche,
    retirer_exo_revision_approche,
    reordonner_exos_revision_approche,
    TypeRevisionApprocheInvalide,
    ExoRevisionApprocheDejaPresent,
    ExoRevisionApprocheIntrouvable,
    ExerciceIntrouvable,
)


class TestExosRevisionApproche:
    def test_lister_partie_vide(self, base_peuplee):
        rep = lister_exos_revision_approche(base_peuplee, "pt_A1")
        assert rep == {"R": [], "EA": []}

    def test_ajouter_EA_simple(self, base_peuplee):
        rep = ajouter_exo_revision_approche(
            base_peuplee, "pt_A1", "EA", "ex_3",
        )
        assert len(rep["EA"]) == 1
        assert rep["EA"][0]["exercice_id"] == "ex_3"
        assert rep["EA"][0]["ordre"] == 1
        assert rep["R"] == []

    def test_ajouter_R_avec_origin(self, base_peuplee):
        # v0.10.2 : il faut d'abord déclarer la précédence N10/S03 sur la
        # séquence sn_A (qui est N11/S03), sinon l'exo R est rejeté.
        from services.v2_edition import ajouter_precedence_sequence
        ajouter_precedence_sequence(base_peuplee, "sn_A", "N10", "S03")
        # Les paramètres origin_* passés en signature sont ignorés depuis
        # v0.10.2 — le backend les remplit lui-même depuis l'exo.
        rep = ajouter_exo_revision_approche(
            base_peuplee, "pt_A1", "R", "ex_R1",
        )
        assert len(rep["R"]) == 1
        r = rep["R"][0]
        # Origines remplies automatiquement par le backend depuis l'exo
        assert r["origin_niveau"] == "N10"
        assert r["origin_seq"] == "S03"
        assert r["origin_serie"] == "A"
        assert r["origin_num"] == 1

    def test_ajouter_plusieurs_ordres_consécutifs(self, base_peuplee):
        ajouter_exo_revision_approche(base_peuplee, "pt_A1", "EA", "ex_3")
        rep = ajouter_exo_revision_approche(
            base_peuplee, "pt_A1", "EA", "ex_4",
        )
        assert [e["ordre"] for e in rep["EA"]] == [1, 2]
        assert [e["exercice_id"] for e in rep["EA"]] == ["ex_3", "ex_4"]

    def test_doublon_exo_409(self, base_peuplee):
        ajouter_exo_revision_approche(base_peuplee, "pt_A1", "EA", "ex_3")
        with pytest.raises(ExoRevisionApprocheDejaPresent):
            ajouter_exo_revision_approche(
                base_peuplee, "pt_A1", "EA", "ex_3",
            )

    def test_R_et_EA_independants_meme_partie(self, base_peuplee):
        """v0.10.2 : R et EA sont stockés séparément (PK = partie, type,
        exo). On peut avoir un EA et un R dans la même partie, du moment
        que chaque type respecte ses contraintes de provenance.
        """
        from services.v2_edition import ajouter_precedence_sequence
        ajouter_precedence_sequence(base_peuplee, "sn_A", "N10", "S03")
        # ex_3 : N11/S03 série EA → légitime en EA
        ajouter_exo_revision_approche(base_peuplee, "pt_A1", "EA", "ex_3")
        # ex_R1 : N10/S03 série A → légitime en R via la précédence
        rep = ajouter_exo_revision_approche(
            base_peuplee, "pt_A1", "R", "ex_R1",
        )
        assert len(rep["EA"]) == 1
        assert len(rep["R"]) == 1

    def test_type_invalide(self, base_peuplee):
        with pytest.raises(TypeRevisionApprocheInvalide):
            ajouter_exo_revision_approche(
                base_peuplee, "pt_A1", "X", "ex_3",
            )

    def test_partie_inexistante(self, base_peuplee):
        with pytest.raises(PartieIntrouvable):
            ajouter_exo_revision_approche(
                base_peuplee, "pt_INC", "EA", "ex_3",
            )

    def test_exercice_inexistant(self, base_peuplee):
        with pytest.raises(ExerciceIntrouvable):
            ajouter_exo_revision_approche(
                base_peuplee, "pt_A1", "EA", "ex_INC",
            )

    def test_retirer_existant(self, base_peuplee):
        ajouter_exo_revision_approche(base_peuplee, "pt_A1", "EA", "ex_3")
        ajouter_exo_revision_approche(base_peuplee, "pt_A1", "EA", "ex_4")
        rep = retirer_exo_revision_approche(
            base_peuplee, "pt_A1", "EA", "ex_3",
        )
        assert len(rep["EA"]) == 1
        # Recompactage : ex_4 doit avoir ordre 1
        assert rep["EA"][0]["exercice_id"] == "ex_4"
        assert rep["EA"][0]["ordre"] == 1

    def test_retirer_inexistant_404(self, base_peuplee):
        with pytest.raises(ExoRevisionApprocheIntrouvable):
            retirer_exo_revision_approche(
                base_peuplee, "pt_A1", "EA", "ex_3",
            )

    def test_reordonner_simple(self, base_peuplee):
        ajouter_exo_revision_approche(base_peuplee, "pt_A1", "EA", "ex_3")
        ajouter_exo_revision_approche(base_peuplee, "pt_A1", "EA", "ex_4")
        rep = reordonner_exos_revision_approche(
            base_peuplee, "pt_A1", "EA", ["ex_4", "ex_3"],
        )
        assert [e["exercice_id"] for e in rep["EA"]] == ["ex_4", "ex_3"]
        assert [e["ordre"] for e in rep["EA"]] == [1, 2]

    def test_reordonner_liste_incoherente(self, base_peuplee):
        ajouter_exo_revision_approche(base_peuplee, "pt_A1", "EA", "ex_3")
        with pytest.raises(ReordonnancementInvalide):
            reordonner_exos_revision_approche(
                base_peuplee, "pt_A1", "EA", ["ex_4"],
            )

    def test_lister_ne_melange_pas_les_parties(self, base_peuplee):
        ajouter_exo_revision_approche(base_peuplee, "pt_A1", "EA", "ex_3")
        ajouter_exo_revision_approche(base_peuplee, "pt_A2", "EA", "ex_4")
        rep_a1 = lister_exos_revision_approche(base_peuplee, "pt_A1")
        rep_a2 = lister_exos_revision_approche(base_peuplee, "pt_A2")
        assert [e["exercice_id"] for e in rep_a1["EA"]] == ["ex_3"]
        assert [e["exercice_id"] for e in rep_a2["EA"]] == ["ex_4"]


# ═════════════════════════════════════════════════════════════════════════════
# 6. État UI persistant
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    lire_etat_ui_atelier_sequence,
    ecrire_etat_ui_atelier_sequence,
    ObjectifIntrouvable,
)


class TestEtatUiAtelierSequence:
    def test_lecture_initiale_vide(self, base_peuplee):
        """Aucune ligne en BDD → objectif_ouvert_id None, pas d'erreur."""
        rep = lire_etat_ui_atelier_sequence(base_peuplee, "sn_A")
        assert rep["sequence_par_niveau_id"] == "sn_A"
        assert rep["objectif_ouvert_id"] is None
        assert rep["derniere_maj"] is None

    def test_ecriture_lecture_simple(self, base_peuplee):
        ecrire_etat_ui_atelier_sequence(
            base_peuplee, "sn_A", "ob_A1_01",
        )
        rep = lire_etat_ui_atelier_sequence(base_peuplee, "sn_A")
        assert rep["objectif_ouvert_id"] == "ob_A1_01"
        assert rep["derniere_maj"] is not None

    def test_ecriture_avec_None_ferme(self, base_peuplee):
        """Écrire None = fermer tout."""
        ecrire_etat_ui_atelier_sequence(
            base_peuplee, "sn_A", "ob_A1_01",
        )
        ecrire_etat_ui_atelier_sequence(base_peuplee, "sn_A", None)
        rep = lire_etat_ui_atelier_sequence(base_peuplee, "sn_A")
        assert rep["objectif_ouvert_id"] is None

    def test_upsert_remplace(self, base_peuplee):
        ecrire_etat_ui_atelier_sequence(
            base_peuplee, "sn_A", "ob_A1_01",
        )
        ecrire_etat_ui_atelier_sequence(
            base_peuplee, "sn_A", "ob_A2_11",
        )
        rep = lire_etat_ui_atelier_sequence(base_peuplee, "sn_A")
        assert rep["objectif_ouvert_id"] == "ob_A2_11"
        # Une seule ligne en BDD
        n = base_peuplee.execute(
            "SELECT COUNT(*) FROM ui_etat_atelier_sequence",
        ).fetchone()[0]
        assert n == 1

    def test_objectif_dans_autre_sequence_404(self, base_peuplee):
        """Tenter de pointer un objectif qui appartient à sn_B alors qu'on
        est sur sn_A doit lever ObjectifIntrouvable."""
        with pytest.raises(ObjectifIntrouvable):
            ecrire_etat_ui_atelier_sequence(
                base_peuplee, "sn_A", "ob_B1_01",
            )

    def test_objectif_inexistant_404(self, base_peuplee):
        with pytest.raises(ObjectifIntrouvable):
            ecrire_etat_ui_atelier_sequence(
                base_peuplee, "sn_A", "ob_INC",
            )

    def test_sequence_inexistante_404_lecture(self, base_peuplee):
        with pytest.raises(SequenceParNiveauIntrouvable):
            lire_etat_ui_atelier_sequence(base_peuplee, "sn_INC")

    def test_sequence_inexistante_404_ecriture(self, base_peuplee):
        with pytest.raises(SequenceParNiveauIntrouvable):
            ecrire_etat_ui_atelier_sequence(
                base_peuplee, "sn_INC", None,
            )

    def test_seq_indep_ecritures_separees(self, base_peuplee):
        """Deux séquences ont chacune leur état UI."""
        ecrire_etat_ui_atelier_sequence(
            base_peuplee, "sn_A", "ob_A1_01",
        )
        ecrire_etat_ui_atelier_sequence(
            base_peuplee, "sn_B", "ob_B1_01",
        )
        rep_a = lire_etat_ui_atelier_sequence(base_peuplee, "sn_A")
        rep_b = lire_etat_ui_atelier_sequence(base_peuplee, "sn_B")
        assert rep_a["objectif_ouvert_id"] == "ob_A1_01"
        assert rep_b["objectif_ouvert_id"] == "ob_B1_01"


# ═════════════════════════════════════════════════════════════════════════════
# 7. v2_lecture enrichie : exos_revision_approche + etat_ui
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_lecture import lire_sequence_par_niveau


class TestV2LectureEnrichie:
    def test_parties_ont_exos_revision_approche_vides(self, base_peuplee):
        rep = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
        for p in rep["parties"]:
            assert "exos_revision_approche" in p
            assert p["exos_revision_approche"] == {"R": [], "EA": []}

    def test_parties_montrent_exos_ajoutes(self, base_peuplee):
        # v0.10.2 : ajouter d'abord la précédence pour permettre l'exo R
        from services.v2_edition import ajouter_precedence_sequence
        ajouter_precedence_sequence(base_peuplee, "sn_A", "N10", "S03")
        ajouter_exo_revision_approche(
            base_peuplee, "pt_A1", "EA", "ex_3",
        )
        ajouter_exo_revision_approche(
            base_peuplee, "pt_A1", "R", "ex_R1",
        )
        rep = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
        pt_A1 = next(p for p in rep["parties"] if p["id"] == "pt_A1")
        assert len(pt_A1["exos_revision_approche"]["EA"]) == 1
        assert len(pt_A1["exos_revision_approche"]["R"]) == 1
        # L'autre partie reste vide
        pt_A2 = next(p for p in rep["parties"] if p["id"] == "pt_A2")
        assert pt_A2["exos_revision_approche"] == {"R": [], "EA": []}

    def test_etat_ui_present_au_top_level(self, base_peuplee):
        rep = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
        assert "etat_ui" in rep
        assert rep["etat_ui"]["objectif_ouvert_id"] is None

    def test_etat_ui_remplit_apres_ecriture(self, base_peuplee):
        ecrire_etat_ui_atelier_sequence(
            base_peuplee, "sn_A", "ob_A1_02",
        )
        rep = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
        assert rep["etat_ui"]["objectif_ouvert_id"] == "ob_A1_02"


# ═════════════════════════════════════════════════════════════════════════════
# 8. Tests d'intégration via routes Flask
# ═════════════════════════════════════════════════════════════════════════════
#
# On utilise le client Flask + un sqlite_store réel (fixture data_dir),
# pattern utilisé par test_R4e2_edition pour les routes.

class TestRoutes:
    """Intégration : on peuple via INSERT direct sur store.db_path
    (pas d'API d'écriture pour créer notre fixture), puis on tape les
    nouvelles routes."""

    @pytest.fixture
    def populated(self, app, sqlite_store):
        """Peuple une mini-séquence via SQL direct sur la base réelle de
        l'app, puis renvoie les ids utiles."""
        import sqlite3 as _sql
        with _sql.connect(sqlite_store.db_path) as c:
            c.execute("PRAGMA foreign_keys = ON")
            # On insère 1 séquence avec 2 parties, 2 objectifs en partie 1,
            # et 2 exos catalogue. La table 'methodes' est laissée vide.
            # v0.10.2 : on ajoute aussi un exo N10/S03 série A pour les
            # tests R (révision), avec la précédence correspondante.
            c.executescript("""
                INSERT INTO sequences_par_niveau (id, niveau, sequence_code)
                  VALUES ('sn_X', 'N11', 'S03');
                INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                  VALUES ('pt_X1', 'sn_X', 1),
                         ('pt_X2', 'sn_X', 2);
                INSERT INTO objectifs (id, partie_id, code, nom)
                  VALUES ('ob_X1_01', 'pt_X1', '01', 'Cours'),
                         ('ob_X1_02', 'pt_X1', '02', 'Obj 02'),
                         ('ob_X2_12', 'pt_X2', '12', 'Obj 12');
                INSERT INTO exercices (id, serie, titre, fichier, niveau,
                                       sequence, num, serie_code)
                  VALUES ('ex_a',     'approche', 'A',     'a.tex', 'N11', 'S03', 1, 'AE'),
                         ('ex_b',     'approche', 'B',     'b.tex', 'N11', 'S03', 2, 'AE'),
                         ('ex_r_n10', 'avancee',  'R n10', 'r.tex', 'N10', 'S03', 1, 'A');
                INSERT INTO sequence_par_niveau_precedences
                    (sequence_par_niveau_id, precedent_niveau, precedent_seq, ordre)
                  VALUES ('sn_X', 'N10', 'S03', 1);
            """)
            c.commit()
        return {
            "sn_id": "sn_X",
            "pt_X1": "pt_X1", "pt_X2": "pt_X2",
            "ob_X1_01": "ob_X1_01", "ob_X1_02": "ob_X1_02",
            "ob_X2_12": "ob_X2_12",
            "ex_r_n10": "ex_r_n10",
        }

    def test_reordonner_parties_via_route(self, client, populated):
        rep = client.patch(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/parties/ordre",
            json={"partie_ids": ["pt_X2", "pt_X1"]},
        )
        assert rep.status_code == 200
        data = rep.get_json()
        assert data["parties"] == [
            {"id": "pt_X2", "numero": 1},
            {"id": "pt_X1", "numero": 2},
        ]

    def test_reordonner_parties_payload_manquant(self, client, populated):
        rep = client.patch(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/parties/ordre",
            json={},
        )
        assert rep.status_code == 400

    def test_reordonner_objectifs_route(self, client, populated):
        rep = client.patch(
            f"/api/v2/parties/{populated['pt_X1']}/objectifs/ordre",
            json={"objectif_ids": ["ob_X1_01", "ob_X1_02"]},
        )
        assert rep.status_code == 200
        data = rep.get_json()
        assert data["objectifs"][0]["code"] == "01"
        assert data["objectifs"][1]["code"] == "02"

    def test_activer_objectif_connaitre_route(self, client, populated):
        # pt_X2 n'a pas de Connaître (juste ob_X2_12)
        rep = client.post(
            f"/api/v2/parties/{populated['pt_X2']}/objectif-connaitre",
            json={
                "critere_F": "F text",
                "critere_A": "A text",
                "critere_E": "E text",
            },
        )
        assert rep.status_code == 201
        data = rep.get_json()
        assert data["code"] == "11"
        assert data["partie_id"] == "pt_X2"
        assert data["nom"] == "Connaître les notions et les méthodes"
        assert data["critere_F"] == "F text"

    def test_activer_objectif_connaitre_409_si_existe(self, client, populated):
        # pt_X1 a déjà '01'
        rep = client.post(
            f"/api/v2/parties/{populated['pt_X1']}/objectif-connaitre",
            json={},
        )
        assert rep.status_code == 409
        assert rep.get_json()["code"] == "objectif_connaitre_deja_present"

    def test_lister_exos_ra_partie_vide(self, client, populated):
        rep = client.get(
            f"/api/v2/parties/{populated['pt_X1']}/exos-revision-approche",
        )
        assert rep.status_code == 200
        assert rep.get_json()["exos"] == {"R": [], "EA": []}

    def test_ajouter_exo_EA_route(self, client, populated):
        rep = client.post(
            f"/api/v2/parties/{populated['pt_X1']}/exos-revision-approche",
            json={"type": "EA", "exercice_id": "ex_a"},
        )
        assert rep.status_code == 201
        data = rep.get_json()
        assert len(data["exos"]["EA"]) == 1

    def test_ajouter_exo_R_route_avec_origin(self, client, populated):
        # v0.10.2 : utilise ex_r_n10 (N10/S03 série A) qui correspond à la
        # précédence déclarée dans la fixture. Les origin_* du payload
        # sont ignorés : le backend les remplit lui-même.
        rep = client.post(
            f"/api/v2/parties/{populated['pt_X1']}/exos-revision-approche",
            json={
                "type": "R", "exercice_id": "ex_r_n10",
                # ces champs ne sont plus utilisés par le backend mais
                # gardés ici pour rétrocompatibilité de signature
                "origin_niveau": "N10", "origin_seq": "S03",
                "origin_serie": "A", "origin_num": 1,
            },
        )
        assert rep.status_code == 201
        r = rep.get_json()["exos"]["R"][0]
        assert r["origin_niveau"] == "N10"

    def test_ajouter_exo_doublon_409(self, client, populated):
        client.post(
            f"/api/v2/parties/{populated['pt_X1']}/exos-revision-approche",
            json={"type": "EA", "exercice_id": "ex_a"},
        )
        rep = client.post(
            f"/api/v2/parties/{populated['pt_X1']}/exos-revision-approche",
            json={"type": "EA", "exercice_id": "ex_a"},
        )
        assert rep.status_code == 409

    def test_ajouter_exo_type_invalide(self, client, populated):
        rep = client.post(
            f"/api/v2/parties/{populated['pt_X1']}/exos-revision-approche",
            json={"type": "FOO", "exercice_id": "ex_a"},
        )
        assert rep.status_code == 400

    def test_retirer_exo_route(self, client, populated):
        client.post(
            f"/api/v2/parties/{populated['pt_X1']}/exos-revision-approche",
            json={"type": "EA", "exercice_id": "ex_a"},
        )
        rep = client.delete(
            f"/api/v2/parties/{populated['pt_X1']}/"
            f"exos-revision-approche/EA/ex_a",
        )
        assert rep.status_code == 200
        assert rep.get_json()["exos"]["EA"] == []

    def test_reordonner_exos_ra_route(self, client, populated):
        client.post(
            f"/api/v2/parties/{populated['pt_X1']}/exos-revision-approche",
            json={"type": "EA", "exercice_id": "ex_a"},
        )
        client.post(
            f"/api/v2/parties/{populated['pt_X1']}/exos-revision-approche",
            json={"type": "EA", "exercice_id": "ex_b"},
        )
        rep = client.patch(
            f"/api/v2/parties/{populated['pt_X1']}/"
            f"exos-revision-approche/EA/ordre",
            json={"exercice_ids": ["ex_b", "ex_a"]},
        )
        assert rep.status_code == 200
        assert [
            e["exercice_id"] for e in rep.get_json()["exos"]["EA"]
        ] == ["ex_b", "ex_a"]

    def test_etat_ui_lecture_initiale(self, client, populated):
        rep = client.get(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/etat-ui",
        )
        assert rep.status_code == 200
        data = rep.get_json()
        assert data["objectif_ouvert_id"] is None

    def test_etat_ui_ecriture_lecture(self, client, populated):
        rep = client.put(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/etat-ui",
            json={"objectif_ouvert_id": "ob_X1_02"},
        )
        assert rep.status_code == 200
        rep2 = client.get(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/etat-ui",
        )
        assert rep2.get_json()["objectif_ouvert_id"] == "ob_X1_02"

    def test_etat_ui_ecriture_null(self, client, populated):
        client.put(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/etat-ui",
            json={"objectif_ouvert_id": "ob_X1_02"},
        )
        rep = client.put(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/etat-ui",
            json={"objectif_ouvert_id": None},
        )
        assert rep.status_code == 200
        assert rep.get_json()["objectif_ouvert_id"] is None

    def test_etat_ui_objectif_autre_seq_404(self, client, populated):
        # Insérer une 2e séquence avec son propre objectif pour tester
        import sqlite3 as _sql
        from flask import current_app
        with client.application.app_context():
            with _sql.connect(current_app.json_store.db_path) as c:
                c.executescript("""
                    INSERT INTO sequences_par_niveau (id, niveau, sequence_code)
                      VALUES ('sn_Y', 'N12', 'S03');
                    INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                      VALUES ('pt_Y1', 'sn_Y', 1);
                    INSERT INTO objectifs (id, partie_id, code, nom)
                      VALUES ('ob_Y1_01', 'pt_Y1', '01', 'Y cours');
                """)
                c.commit()
        # Essayer d'ouvrir ob_Y1_01 sur sn_X → 404
        rep = client.put(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/etat-ui",
            json={"objectif_ouvert_id": "ob_Y1_01"},
        )
        assert rep.status_code == 404

    def test_v2_lecture_renvoie_exos_ra_et_etat_ui(self, client, populated):
        # Depuis l'API GET /api/v2/sequences-par-niveau/<niveau>/<seq>
        rep = client.get("/api/v2/sequences-par-niveau/N11/S03")
        assert rep.status_code == 200
        data = rep.get_json()
        assert "etat_ui" in data
        for p in data["parties"]:
            assert "exos_revision_approche" in p


# ═════════════════════════════════════════════════════════════════════════════
# 9. v0.10.1 — Création / suppression d'objectif simple
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    creer_objectif_simple,
    supprimer_objectif,
    MethodeIntrouvable,
)


class TestCreerObjectifSimple:
    def test_partie_vide_premier_code_01(self, base_peuplee):
        """pt_A3 a déjà '22' (pas de Connaître). Le prochain code libre
        en partie 3 (prefixe=2) est '21'."""
        # On part de pt_A3 qui n'a que '22'. Codes pris = {'22'}.
        # On essaie '21', '22', '23'... → '21' libre.
        rep = creer_objectif_simple(base_peuplee, "pt_A3", nom="Nouveau")
        assert rep["partie_id"] == "pt_A3"
        assert rep["code"] == "21"
        assert rep["nom"] == "Nouveau"
        assert rep["methode_id"] is None

    def test_partie_avec_obj_creation_suivante(self, base_peuplee):
        """pt_A1 a déjà '01' et '02'. Prochain libre = '03'."""
        rep = creer_objectif_simple(base_peuplee, "pt_A1", nom="Nouveau")
        assert rep["code"] == "03"

    def test_avec_methode(self, base_peuplee):
        """Création avec methode_id : la méthode doit exister."""
        # Insérer une méthode test
        base_peuplee.execute(
            "INSERT INTO methodes (id, titre, niveau, sequence, fichier) "
            "VALUES ('me_test', 'Méthode test', 'N11', 'S03', 'm.tex')"
        )
        rep = creer_objectif_simple(
            base_peuplee, "pt_A3",
            nom="Avec méthode",
            methode_id="me_test",
        )
        assert rep["methode_id"] == "me_test"
        assert rep["methode_titre"] == "Méthode test"

    def test_methode_inexistante(self, base_peuplee):
        with pytest.raises(MethodeIntrouvable):
            creer_objectif_simple(
                base_peuplee, "pt_A3", methode_id="me_inexistante",
            )

    def test_partie_inexistante(self, base_peuplee):
        with pytest.raises(PartieIntrouvable):
            creer_objectif_simple(base_peuplee, "pt_INC")

    def test_critères_par_defaut_vides(self, base_peuplee):
        rep = creer_objectif_simple(base_peuplee, "pt_A3")
        assert rep["critere_F"] == ""
        assert rep["critere_A"] == ""
        assert rep["critere_E"] == ""


class TestSupprimerObjectif:
    def test_objectif_simple(self, base_peuplee):
        rep = supprimer_objectif(base_peuplee, "ob_A1_02")
        assert rep["objectif_id"] == "ob_A1_02"
        assert rep["supprime"] is True
        # Vérifier en BDD
        n = base_peuplee.execute(
            "SELECT COUNT(*) FROM objectifs WHERE id = ?",
            ("ob_A1_02",),
        ).fetchone()[0]
        assert n == 0

    def test_avec_exos_cascade(self, base_peuplee):
        """Les exos rattachés à un objectif sont supprimés en cascade."""
        # Ajouter un exo à ob_A1_02
        base_peuplee.execute(
            "INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) "
            "VALUES ('ob_A1_02', 'F', 'ex_1', 1)"
        )
        # Vérifier qu'il est là
        n0 = base_peuplee.execute(
            "SELECT COUNT(*) FROM objectif_exos WHERE objectif_id = 'ob_A1_02'",
        ).fetchone()[0]
        assert n0 == 1
        # Supprimer l'objectif → exo cascadé
        supprimer_objectif(base_peuplee, "ob_A1_02")
        n1 = base_peuplee.execute(
            "SELECT COUNT(*) FROM objectif_exos WHERE objectif_id = 'ob_A1_02'",
        ).fetchone()[0]
        assert n1 == 0

    def test_inexistant_404(self, base_peuplee):
        with pytest.raises(ObjectifIntrouvable):
            supprimer_objectif(base_peuplee, "ob_INC")


class TestRoutesObjectifSimple:
    """Tests d'intégration via routes Flask pour création/suppression."""

    @pytest.fixture
    def populated(self, app, sqlite_store):
        import sqlite3 as _sql
        with _sql.connect(sqlite_store.db_path) as c:
            c.execute("PRAGMA foreign_keys = ON")
            c.executescript("""
                INSERT INTO sequences_par_niveau (id, niveau, sequence_code)
                  VALUES ('sn_X', 'N11', 'S03');
                INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                  VALUES ('pt_X1', 'sn_X', 1);
                INSERT INTO objectifs (id, partie_id, code, nom)
                  VALUES ('ob_existant', 'pt_X1', '01', 'Cours');
                INSERT INTO methodes (id, titre, niveau, sequence)
                  VALUES ('me_test', 'Méthode test', 'N11', 'S03');
            """)
            c.commit()
        return {"sn_id": "sn_X", "pt_X1": "pt_X1", "ob_existant": "ob_existant"}

    def test_post_objectif_minimal(self, client, populated):
        rep = client.post(
            f"/api/v2/parties/{populated['pt_X1']}/objectif",
            json={"nom": "Nouveau"},
        )
        assert rep.status_code == 201
        data = rep.get_json()
        # Codes pris dans pt_X1 = {'01'}, prefixe=0, prochain libre = '02'
        assert data["code"] == "02"
        assert data["nom"] == "Nouveau"

    def test_post_objectif_avec_methode(self, client, populated):
        rep = client.post(
            f"/api/v2/parties/{populated['pt_X1']}/objectif",
            json={"nom": "Avec méthode", "methode_id": "me_test"},
        )
        assert rep.status_code == 201
        data = rep.get_json()
        assert data["methode_id"] == "me_test"

    def test_post_objectif_methode_inconnue_404(self, client, populated):
        rep = client.post(
            f"/api/v2/parties/{populated['pt_X1']}/objectif",
            json={"methode_id": "me_INC"},
        )
        assert rep.status_code == 404

    def test_delete_objectif(self, client, populated):
        rep = client.delete(
            f"/api/v2/objectifs/{populated['ob_existant']}",
        )
        assert rep.status_code == 200
        data = rep.get_json()
        assert data["supprime"] is True

    def test_delete_objectif_inexistant_404(self, client, populated):
        rep = client.delete("/api/v2/objectifs/ob_INCONNU")
        assert rep.status_code == 404
