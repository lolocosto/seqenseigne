r"""tests/test_v0_15_2_3_planche_suffixation.py — v0.15.2.3

Tests du module de suffixation des variables xint pour les planches
(services/planche_suffixation).

Couvre :
  - extraction des noms déclarés (\xintdefiivar, \xintdeffloatvar)
  - substitution mot-entier (pas de collision p / prix)
  - cohérence des références internes entre variables
  - format du suffixe (01..16, zéro-padé)
  - cas réels du corpus N10
"""
from __future__ import annotations

import pytest

from services.planche_suffixation import (
    extraire_noms_variables,
    suffixer_noms,
    suffixe_cellule,
)


# ── Extraction des noms ──────────────────────────────────────────────────────

class TestExtraction:
    def test_xintdefiivar_simple(self):
        bloc = r'\xintdefiivar p := randrange(5,95);'
        assert extraire_noms_variables(bloc) == ['p']

    def test_xintdeffloatvar(self):
        bloc = r'\xintdeffloatvar res := p / 100;'
        assert extraire_noms_variables(bloc) == ['res']

    def test_plusieurs_variables_ordre(self):
        bloc = (r'\xintdefiivar a := 5;'
                r'\xintdefiivar b := 3;'
                r'\xintdefiivar s := a + b;')
        assert extraire_noms_variables(bloc) == ['a', 'b', 's']

    def test_pas_de_doublon(self):
        # Si le même nom est déclaré deux fois, il n'apparaît qu'une fois.
        bloc = r'\xintdefiivar a := 5; \xintdefiivar a := 7;'
        assert extraire_noms_variables(bloc) == ['a']

    def test_bloc_vide(self):
        assert extraire_noms_variables('') == []
        assert extraire_noms_variables(None) == []

    def test_noms_structures(self):
        """Cas du corpus : noms NiveauSequenceCarte_xxx."""
        bloc = (r'\xintdefiivar N10S12C05_a := randrange(30,80);'
                r'\xintdefiivar N10S12C05_b := randrange(30,80);'
                r'\xintdefiivar N10S12C05_c := 180 - N10S12C05_a - N10S12C05_b;')
        assert extraire_noms_variables(bloc) == [
            'N10S12C05_a', 'N10S12C05_b', 'N10S12C05_c']

    def test_espaces_variables(self):
        """Tolérance aux espaces autour du := et du nom."""
        bloc = r'\xintdefiivar   p   :=  42 ;'
        assert extraire_noms_variables(bloc) == ['p']


# ── Substitution mot-entier ──────────────────────────────────────────────────

class TestSuffixation:
    def test_substitution_simple(self):
        texte = r'$\xinttheiiexpr p\relax$'
        assert suffixer_noms(texte, ['p'], '01') == r'$\xinttheiiexpr p_01\relax$'

    def test_pas_de_collision_p_prix(self):
        """Le cas piège : 'p' ne doit pas être substitué dans 'prix'."""
        texte = r'$\xinttheiiexpr p\relax$ et $\xinttheiiexpr prix\relax$'
        out = suffixer_noms(texte, ['p', 'prix'], '07')
        assert r'p_07\relax' in out
        assert r'prix_07\relax' in out
        # Surtout PAS de p_07rix
        assert 'p_07rix' not in out

    def test_references_internes_coherentes(self):
        """Quand une variable en référence une autre, les deux sont
        suffixées de façon cohérente."""
        bloc = r'\xintdefiivar prix := p * 10;'
        out = suffixer_noms(bloc, ['p', 'prix'], '03')
        assert out == r'\xintdefiivar prix_03 := p_03 * 10;'

    def test_cas_reel_S12C05(self):
        """Cas réel : 3 variables avec référence interne (_c := 180 - _a - _b)."""
        bloc = (r'\xintdefiivar N10S12C05_a := randrange(30,80);'
                r'\xintdefiivar N10S12C05_b := randrange(30,80);'
                r'\xintdefiivar N10S12C05_c := 180 - N10S12C05_a - N10S12C05_b;')
        noms = extraire_noms_variables(bloc)
        out = suffixer_noms(bloc, noms, '07')
        assert 'N10S12C05_a_07' in out
        assert 'N10S12C05_b_07' in out
        assert 'N10S12C05_c_07' in out
        # La référence interne est cohérente
        assert '180 - N10S12C05_a_07 - N10S12C05_b_07' in out
        # Aucun nom non suffixé ne subsiste (vérif : pas de _a sans _07 derrière)
        import re
        assert not re.search(r'N10S12C05_a(?!_07)', out)

    def test_idempotence_partielle(self):
        """Suffixer un texte déjà suffixé avec les noms ORIGINAUX ne
        re-suffixe pas (car les noms originaux ne matchent plus en
        mot-entier : 'p' ne matche pas dans 'p_01')."""
        texte = r'$\xinttheiiexpr p_01\relax$'
        # On re-suffixe avec le nom original 'p'
        out = suffixer_noms(texte, ['p'], '02')
        # 'p' ne doit PAS matcher dans 'p_01' (car suivi de '_')
        assert out == texte  # inchangé

    def test_texte_sans_variable(self):
        texte = r'Texte fixe sans variable.'
        assert suffixer_noms(texte, ['p'], '01') == texte

    def test_liste_noms_vide(self):
        texte = r'$\xinttheiiexpr p\relax$'
        assert suffixer_noms(texte, [], '01') == texte

    def test_variable_collee_a_lettre(self):
        """Cas N10/S05/CA06 : variable suivie d'une lettre (x algébrique).
        Le nom 'a' suivi de '\\relax{}x' : on suffixe 'a' mais pas le 'x'.
        """
        texte = r'$\xinttheiiexpr N10S05C06_a\relax{}x$'
        out = suffixer_noms(texte, ['N10S05C06_a'], '04')
        assert out == r'$\xinttheiiexpr N10S05C06_a_04\relax{}x$'


# ── Format du suffixe ────────────────────────────────────────────────────────

class TestSuffixeCellule:
    def test_format_zero_pade(self):
        assert suffixe_cellule(1) == '01'
        assert suffixe_cellule(9) == '09'
        assert suffixe_cellule(10) == '10'
        assert suffixe_cellule(16) == '16'

    def test_tous_distincts(self):
        suffixes = [suffixe_cellule(i) for i in range(1, 17)]
        assert len(set(suffixes)) == 16
        assert suffixes[0] == '01'
        assert suffixes[-1] == '16'
