r"""
tests/test_v0_15_5_cycle_du_niveau.py — Factorisation de `_cycle_du_niveau`.

CONTEXTE (dette technique v0.15.5)
----------------------------------
Avant v0.15.5, six services « livret » embarquaient chacun leur propre
fonction `_cycle_du_niveau(conn, niveau)`. Cinq d'entre eux (recap_exos,
recap_cours, fiches, corriges) portaient la MÊME implémentation buggée :

    SELECT DISTINCT sdc.cycle_code
      FROM sequences_par_niveau spn
      JOIN sequences_du_cycle sdc ON spn.sequence_code = sdc.code
     WHERE spn.niveau = ?
     LIMIT 1

Cette jointure résout le cycle d'un niveau à partir d'un CODE de séquence
(ex. S01). Or S01 existe à la fois en C03 (« Nombres entiers ») et en C04
(« Représentations d'un nombre »). Le `LIMIT 1`, sans filtre cycle ni ordre
déterministe, pouvait remonter C03 pour un niveau de cycle 4 (N10, N11, N12).
Bug confirmé en production (cf. redemarrage v0.12.1.2).

Seul `livret_plans_de_travail` avait été corrigé (v0.13.1) en déléguant à
`services.param_niveaux.lire_cycle`, qui lit la table `param_niveaux`
(source unique de vérité, indépendante des tables séquence).

DÉCISION v0.15.5
----------------
On supprime les six wrappers locaux et on appelle directement
`services.param_niveaux.lire_cycle` partout. Le wrapper de
`livret_plans_de_travail` ne servait qu'à reformuler le message de
l'exception ; or `NiveauInconnu` est déjà une `LookupError` et aucun
appelant ne matche le texte du message (vérifié à la main).

CE QUE CE TEST VERROUILLE
-------------------------
1. La fonction canonique `lire_cycle` résout C04 pour N10/N11/N12 même
   dans le contexte-piège (S01 présent en C03 ET C04).
2. Aucun des cinq services concernés ne contient plus la jointure buggée
   ni une définition `def _cycle_du_niveau`. Si quelqu'un réintroduit un
   wrapper local (régression de duplication), ce test échoue et rappelle
   pourquoi via son nom et ce docstring.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from services.param_niveaux import lire_cycle, NiveauInconnu


# Les cinq services dont le wrapper a été supprimé en v0.15.5.
_SERVICES_FACTORISES = [
    "livret_recap_exos",
    "livret_recap_cours",
    "livret_fiches",
    "livret_corriges",
    "livret_plans_de_travail",
]

_SERVICES_DIR = Path(__file__).resolve().parent.parent / "services"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(
        """
        CREATE TABLE cycles (
            code TEXT PRIMARY KEY,
            nom  TEXT NOT NULL
        );
        CREATE TABLE param_niveaux (
            code             TEXT PRIMARY KEY,
            cycle_code       TEXT NOT NULL REFERENCES cycles(code),
            annee_dans_cycle TEXT,
            nom_court        TEXT,
            nom_long         TEXT,
            ordre            INTEGER
        );
        CREATE TABLE sequences_du_cycle (
            id          TEXT PRIMARY KEY,
            cycle_code  TEXT NOT NULL REFERENCES cycles(code),
            code        TEXT NOT NULL,
            numero      INTEGER,
            nom         TEXT
        );
        CREATE TABLE sequences_par_niveau (
            id            TEXT PRIMARY KEY,
            niveau        TEXT NOT NULL,
            sequence_code TEXT NOT NULL
        );
        """
    )
    # Amorce param_niveaux : N09→C03, N10/N11/N12→C04.
    c.executescript(
        """
        INSERT INTO cycles (code, nom) VALUES
            ('C03', 'Cycle 3'), ('C04', 'Cycle 4');
        INSERT INTO param_niveaux (code, cycle_code, ordre) VALUES
            ('N09', 'C03', 3),
            ('N10', 'C04', 4),
            ('N11', 'C04', 5),
            ('N12', 'C04', 6);
        """
    )
    c.commit()
    yield c
    c.close()


class TestResolutionCanonique:
    """`lire_cycle` est la seule source de vérité, indépendante des
    tables séquence."""

    def test_n10_n11_n12_renvoient_c04(self, conn):
        assert lire_cycle(conn, "N10") == "C04"
        assert lire_cycle(conn, "N11") == "C04"
        assert lire_cycle(conn, "N12") == "C04"

    def test_n09_renvoie_c03(self, conn):
        assert lire_cycle(conn, "N09") == "C03"

    def test_niveau_inconnu_leve_lookuperror(self, conn):
        # NiveauInconnu est une sous-classe de LookupError : les appelants
        # qui attrapent LookupError continuent de fonctionner.
        assert issubclass(NiveauInconnu, LookupError)
        with pytest.raises(LookupError):
            lire_cycle(conn, "N99")

    def test_piege_s01_dans_les_deux_cycles_nignore_pas_param_niveaux(self, conn):
        """Contexte-piège exact du bug : S01 existe en C03 ET C04, et une
        séquence-niveau N10/S01 est assemblée. La jointure buggée pouvait
        remonter C03. `lire_cycle` lit `param_niveaux` et renvoie C04."""
        conn.executescript(
            """
            INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom)
              VALUES
              ('sc3_S01', 'C03', 'S01', 1, 'Nombres entiers'),
              ('sc4_S01', 'C04', 'S01', 1, 'Représentations d''un nombre');
            INSERT INTO sequences_par_niveau (id, niveau, sequence_code)
              VALUES ('sn_N10_S01', 'N10', 'S01');
            """
        )
        conn.commit()
        assert lire_cycle(conn, "N10") == "C04"


class TestPlusDeWrapperLocal:
    """Garde-fou anti-régression : aucun des cinq services ne doit
    réintroduire un wrapper `_cycle_du_niveau` ni la jointure buggée."""

    def _source(self, module: str) -> str:
        return (_SERVICES_DIR / f"{module}.py").read_text(encoding="utf-8")

    @pytest.mark.parametrize("module", _SERVICES_FACTORISES)
    def test_pas_de_def_cycle_du_niveau(self, module):
        src = self._source(module)
        assert not re.search(r"^\s*def\s+_cycle_du_niveau\b", src, re.MULTILINE), (
            f"{module} a réintroduit un wrapper local `_cycle_du_niveau`. "
            f"Utiliser services.param_niveaux.lire_cycle (cf. v0.15.5)."
        )

    @pytest.mark.parametrize("module", _SERVICES_FACTORISES)
    def test_pas_de_jointure_buggee(self, module):
        src = self._source(module)
        # La signature du bug : résoudre le CYCLE en sélectionnant
        # `sdc.cycle_code` via une jointure sur le code de séquence puis
        # `LIMIT 1`, SANS filtre `sdc.cycle_code = ?`. On détecte ce motif
        # précis (SELECT cycle_code ... JOIN sequences_du_cycle ... LIMIT 1).
        #
        # NB : une jointure `spn.sequence_code = sdc.code` reste légitime
        # ailleurs (ex. _lire_sequences_du_niveau) DÈS LORS qu'elle porte
        # un filtre `AND sdc.cycle_code = ?`. Ce n'est pas ce qu'on traque.
        motif = re.compile(
            r"SELECT\s+DISTINCT\s+sdc\.cycle_code"
            r"(?:(?!cycle_code\s*=).)*?"
            r"LIMIT\s+1",
            re.IGNORECASE | re.DOTALL,
        )
        assert not motif.search(src), (
            f"{module} contient encore la résolution de cycle buggée "
            f"(SELECT sdc.cycle_code via jointure séquence + LIMIT 1 sans "
            f"filtre cycle). Utiliser services.param_niveaux.lire_cycle "
            f"(cf. v0.15.5)."
        )

    @pytest.mark.parametrize("module", _SERVICES_FACTORISES)
    def test_importe_lire_cycle(self, module):
        src = self._source(module)
        assert "lire_cycle" in src, (
            f"{module} devrait importer et utiliser lire_cycle."
        )
