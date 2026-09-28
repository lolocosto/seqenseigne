"""tests/test_v0_13_1_param_niveaux_helpers.py — v0.13.1.

Tests des helpers de lecture du référentiel des niveaux scolaires
(`services/param_niveaux.py`).

Le module est volontairement minimaliste — il fournit 4 fonctions
pures de lecture sur la table `param_niveaux`. Cette suite couvre :
  - Lecture nominale (`lire_attributs`, `lire_cycle`, `lire_nom_court`,
    `lister_tous`).
  - Cas niveau inconnu : NiveauInconnu pour la lecture stricte,
    fallback transparent pour la lecture tolérante.
  - Compatibilité avec connexion sqlite3 standard ET avec
    `row_factory = sqlite3.Row`.
  - Robustesse : table vide, niveau avec espaces dans le code, etc.
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.param_niveaux import (
    lire_attributs,
    lire_cycle,
    lire_nom_court,
    lister_tous,
    NiveauInconnu,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

_SCHEMA_MIN = """
CREATE TABLE cycles (
    code TEXT PRIMARY KEY,
    nom TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE param_niveaux (
    code              TEXT PRIMARY KEY,
    cycle_code        TEXT NOT NULL REFERENCES cycles(code),
    annee_dans_cycle  TEXT NOT NULL,
    nom_court         TEXT NOT NULL,
    nom_long          TEXT NOT NULL DEFAULT '',
    ordre             INTEGER NOT NULL DEFAULT 0
);
INSERT INTO cycles (code, nom) VALUES
    ('C03', 'Cycle 3'),
    ('C04', 'Cycle 4');
INSERT INTO param_niveaux
    (code, cycle_code, annee_dans_cycle, nom_court, nom_long, ordre) VALUES
    ('N09', 'C03', 'anneetrois', '6ème', 'sixième',     3),
    ('N10', 'C04', 'anneeun',    '5ème', 'cinquième',   4),
    ('N11', 'C04', 'anneedeux',  '4ème', 'quatrième',   5),
    ('N12', 'C04', 'anneetrois', '3ème', 'troisième',   6);
"""


@pytest.fixture
def conn():
    """Connexion avec row_factory standard (tuples)."""
    c = sqlite3.connect(":memory:")
    c.executescript(_SCHEMA_MIN)
    yield c
    c.close()


@pytest.fixture
def conn_row():
    """Connexion avec row_factory=sqlite3.Row (accès par clé)."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA_MIN)
    yield c
    c.close()


@pytest.fixture
def conn_vide():
    """Connexion avec param_niveaux vide (BDD non amorcée)."""
    c = sqlite3.connect(":memory:")
    c.executescript("""
        CREATE TABLE cycles (code TEXT PRIMARY KEY, nom TEXT, description TEXT);
        CREATE TABLE param_niveaux (
            code              TEXT PRIMARY KEY,
            cycle_code        TEXT NOT NULL,
            annee_dans_cycle  TEXT NOT NULL,
            nom_court         TEXT NOT NULL,
            nom_long          TEXT NOT NULL DEFAULT '',
            ordre             INTEGER NOT NULL DEFAULT 0
        );
    """)
    yield c
    c.close()


# ═════════════════════════════════════════════════════════════════════════════
# 1. lire_attributs
# ═════════════════════════════════════════════════════════════════════════════

class TestLireAttributs:

    def test_n10_complet(self, conn):
        a = lire_attributs(conn, 'N10')
        assert a == {
            'code':             'N10',
            'cycle_code':       'C04',
            'annee_dans_cycle': 'anneeun',
            'nom_court':        '5ème',
            'nom_long':         'cinquième',
            'ordre':            4,
        }

    def test_n09_cycle_3(self, conn):
        a = lire_attributs(conn, 'N09')
        assert a is not None
        assert a['cycle_code'] == 'C03'
        assert a['nom_court'] == '6ème'

    def test_niveau_inconnu_renvoie_none(self, conn):
        assert lire_attributs(conn, 'N99') is None

    def test_compatible_row_factory(self, conn_row):
        """Avec row_factory=sqlite3.Row, doit retourner un vrai dict."""
        a = lire_attributs(conn_row, 'N10')
        assert isinstance(a, dict)
        assert a['nom_court'] == '5ème'

    def test_compatible_tuple_factory(self, conn):
        """Avec row_factory standard (tuples), doit aussi retourner un dict."""
        a = lire_attributs(conn, 'N10')
        assert isinstance(a, dict)
        assert a['nom_court'] == '5ème'


# ═════════════════════════════════════════════════════════════════════════════
# 2. lire_cycle (strict)
# ═════════════════════════════════════════════════════════════════════════════

class TestLireCycle:

    def test_cycle_c04(self, conn):
        assert lire_cycle(conn, 'N10') == 'C04'
        assert lire_cycle(conn, 'N11') == 'C04'
        assert lire_cycle(conn, 'N12') == 'C04'

    def test_cycle_c03(self, conn):
        assert lire_cycle(conn, 'N09') == 'C03'

    def test_niveau_inconnu_leve_NiveauInconnu(self, conn):
        with pytest.raises(NiveauInconnu) as exc:
            lire_cycle(conn, 'N99')
        assert exc.value.niveau == 'N99'

    def test_niveau_chaine_vide_leve(self, conn):
        with pytest.raises(NiveauInconnu):
            lire_cycle(conn, '')

    def test_table_vide_leve(self, conn_vide):
        with pytest.raises(NiveauInconnu):
            lire_cycle(conn_vide, 'N10')

    def test_compatible_row_factory(self, conn_row):
        assert lire_cycle(conn_row, 'N10') == 'C04'


# ═════════════════════════════════════════════════════════════════════════════
# 3. lire_nom_court (tolérant — fallback sur code)
# ═════════════════════════════════════════════════════════════════════════════

class TestLireNomCourt:

    def test_nom_courts_connus(self, conn):
        assert lire_nom_court(conn, 'N10') == '5ème'
        assert lire_nom_court(conn, 'N11') == '4ème'
        assert lire_nom_court(conn, 'N12') == '3ème'
        assert lire_nom_court(conn, 'N09') == '6ème'

    def test_niveau_inconnu_renvoie_le_code(self, conn):
        """Fallback : pas d'exception, on retourne le code tel quel.
        Aligné sur l'ancien comportement de `_NOM_COURT_NIVEAU.get(code, code)`."""
        assert lire_nom_court(conn, 'N99') == 'N99'
        assert lire_nom_court(conn, 'XXX') == 'XXX'

    def test_table_vide_renvoie_le_code(self, conn_vide):
        """Si la table est vide, on tombe sur le fallback systématique."""
        assert lire_nom_court(conn_vide, 'N10') == 'N10'


# ═════════════════════════════════════════════════════════════════════════════
# 4. lister_tous
# ═════════════════════════════════════════════════════════════════════════════

class TestListerTous:

    def test_renvoie_tous_dans_l_ordre(self, conn):
        tous = lister_tous(conn)
        codes = [n['code'] for n in tous]
        assert codes == ['N09', 'N10', 'N11', 'N12']

    def test_chaque_entree_est_un_dict_complet(self, conn):
        tous = lister_tous(conn)
        for n in tous:
            assert set(n.keys()) == {
                'code', 'cycle_code', 'annee_dans_cycle',
                'nom_court', 'nom_long', 'ordre',
            }

    def test_tri_par_ordre(self, conn):
        tous = lister_tous(conn)
        ordres = [n['ordre'] for n in tous]
        assert ordres == sorted(ordres)

    def test_table_vide_renvoie_liste_vide(self, conn_vide):
        assert lister_tous(conn_vide) == []

    def test_compatible_row_factory(self, conn_row):
        tous = lister_tous(conn_row)
        assert len(tous) == 4
        assert tous[0]['code'] == 'N09'


# ═════════════════════════════════════════════════════════════════════════════
# 5. lire_nom_court_latex : conversion nom_court brut → forme LaTeX
# ═════════════════════════════════════════════════════════════════════════════

class TestLireNomCourtLatex:
    """Le helper `lire_nom_court_latex` substitue la table en dur
    `_NOM_COURT_NIVEAU` qui était dans `services/livret_sequence.py`.
    Il lit le nom_court brut depuis la BDD et applique une conversion
    'Xème' → 'X\\ieme' pour les niveaux du collège.

    Critère d'équivalence : pour tout niveau du CSV de référence, le
    résultat doit être strictement identique à celui de l'ancien
    `_NOM_COURT_NIVEAU.get(code, code)`. Cf. tests d'équivalence en
    fin de classe."""

    def test_collge_5e_converti_en_5ieme(self, conn):
        from services.param_niveaux import lire_nom_court_latex
        assert lire_nom_court_latex(conn, 'N10') == r'5\ieme'

    def test_college_4e_converti(self, conn):
        from services.param_niveaux import lire_nom_court_latex
        assert lire_nom_court_latex(conn, 'N11') == r'4\ieme'

    def test_college_3e_converti(self, conn):
        from services.param_niveaux import lire_nom_court_latex
        assert lire_nom_court_latex(conn, 'N12') == r'3\ieme'

    def test_college_6e_converti(self, conn):
        from services.param_niveaux import lire_nom_court_latex
        assert lire_nom_court_latex(conn, 'N09') == r'6\ieme'

    def test_fallback_niveau_inconnu_renvoie_code(self, conn):
        """Si le niveau n'existe pas en BDD, on retombe sur le code
        lui-même (cohérent avec le fallback de `lire_nom_court`)."""
        from services.param_niveaux import lire_nom_court_latex
        assert lire_nom_court_latex(conn, 'N99') == 'N99'

    def test_table_vide_fallback_sur_code(self, conn_vide):
        from services.param_niveaux import lire_nom_court_latex
        assert lire_nom_court_latex(conn_vide, 'N10') == 'N10'

    def test_compatible_row_factory(self, conn_row):
        from services.param_niveaux import lire_nom_court_latex
        assert lire_nom_court_latex(conn_row, 'N10') == r'5\ieme'

    def test_equivalence_avec_ancien_dict(self, conn):
        """Test d'équivalence avec l'ancien `_NOM_COURT_NIVEAU` qui
        était hardcodé dans `services/livret_sequence.py`. Reproduction
        du dict pour vérifier que la lecture BDD + conversion donne
        exactement les mêmes valeurs."""
        from services.param_niveaux import lire_nom_court_latex

        # Reproduction de _NOM_COURT_NIVEAU tel qu'il était avant v0.13.1.
        # Note : la fixture ne définit que N09..N12 en BDD, donc on
        # ne teste l'équivalence que sur ces 4 codes.
        ancien_dict = {
            'N09': '6\\ieme',
            'N10': '5\\ieme',
            'N11': '4\\ieme',
            'N12': '3\\ieme',
        }
        for code, valeur_attendue in ancien_dict.items():
            assert lire_nom_court_latex(conn, code) == valeur_attendue, (
                f"Régression sur {code} : helper={lire_nom_court_latex(conn, code)!r}, "
                f"ancien_dict={valeur_attendue!r}"
            )

    def test_idempotence_si_deja_latex(self, conn):
        """Si la BDD contient déjà la forme LaTeX (cas non observé en
        prod mais théoriquement possible), la fonction doit la
        retourner telle quelle (pas de double conversion)."""
        # Insertion d'un niveau déjà en forme LaTeX. En SQLite, le
        # backslash n'a pas de signification spéciale dans les chaînes,
        # donc '5\ieme' s'écrit littéralement avec un seul backslash.
        conn.execute(
            "INSERT INTO param_niveaux "
            "(code, cycle_code, annee_dans_cycle, nom_court, nom_long, ordre) "
            "VALUES (?, 'C04', 'anneeun', ?, 'cinquième', 99)",
            ('N99', '5\\ieme'),  # En Python : "5\\ieme" = chaîne de 6 chars : 5 \ i e m e
        )
        from services.param_niveaux import lire_nom_court_latex
        # La regex 'Xème' ne matche pas '5\ieme' donc on retourne tel quel
        result = lire_nom_court_latex(conn, 'N99')
        assert result == '5\\ieme', f"got {result!r}"

    def test_primaire_pas_modifie(self, conn):
        """Pour les niveaux primaires (CM1, CM2), pas de transformation —
        le nom court reste tel quel."""
        # Ajouter N07 (CM1) et N08 (CM2)
        conn.execute(
            "INSERT INTO param_niveaux "
            "(code, cycle_code, annee_dans_cycle, nom_court, nom_long, ordre) "
            "VALUES ('N07', 'C03', 'anneeun', 'CM1', 'cours moyen 1', 1)"
        )
        conn.execute(
            "INSERT INTO param_niveaux "
            "(code, cycle_code, annee_dans_cycle, nom_court, nom_long, ordre) "
            "VALUES ('N08', 'C03', 'anneedeux', 'CM2', 'cours moyen 2', 2)"
        )
        from services.param_niveaux import lire_nom_court_latex
        assert lire_nom_court_latex(conn, 'N07') == 'CM1'
        assert lire_nom_court_latex(conn, 'N08') == 'CM2'
