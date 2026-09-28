r"""tests/test_v0_15_2_2_2_migrer_xint_eval.py — v0.15.2.2.2

Tests pour `scripts/migrer_xint_eval_vers_the_expr.py`.

Ce script convertit les macros xint **protégées** vers leurs équivalents
**expansibles** dans les champs `recto`, `verso` et `variables` de la
table `cartes_automatisme`. Cette migration est nécessaire pour que
le `\\edef` de `\\seqCartePlanche` puisse figer les valeurs par cellule
(cf. cadrage v0.15.2.2.2 — approche C).
"""
from __future__ import annotations

import pytest

from scripts.migrer_xint_eval_vers_the_expr import migrer_chaine


# ── Conversions élémentaires ─────────────────────────────────────────────────

class TestMigrerChaine:
    def test_xintiieval_simple(self):
        out, stats = migrer_chaine(r'$\xintiieval{p}$')
        assert out == r'$\xinttheiiexpr p\relax{}$'
        assert stats == {'xintiieval': 1}

    def test_xintfloateval_simple(self):
        out, stats = migrer_chaine(r'$\xintfloateval{p}$')
        assert out == r'$\xintthefloatexpr p\relax{}$'
        assert stats == {'xintfloateval': 1}

    def test_xinteval_simple(self):
        out, stats = migrer_chaine(r'$\xinteval{a/b}$')
        assert out == r'$\xinttheexpr a/b\relax{}$'
        assert stats == {'xinteval': 1}

    def test_argument_avec_variable_typique(self):
        """Cas typique du corpus : nom de variable structuré."""
        s = r'\xintiieval{N10S01C04_p}'
        out, _ = migrer_chaine(s)
        assert out == r'\xinttheiiexpr N10S01C04_p\relax{}'

    def test_argument_avec_expression(self):
        """Cas du corpus : expression arithmétique sans accolade ni backslash."""
        s = r'\xintiieval{N10S07C03_a + N10S07C03_b}'
        out, _ = migrer_chaine(s)
        assert out == r'\xinttheiiexpr N10S07C03_a + N10S07C03_b\relax{}'


# ── Cas du bug v0.15.2.2.2 (corrigé en v0.15.2.2.2.1) ───────────────────────

class TestBugRelaxColleLettre:
    """v0.15.2.2.2 — Bug découvert : sans `{}` après `\\relax`, un caractère
    lettre qui suivait `\\xintiieval{...}` dans le contenu BDD se collait à
    `\\relax` pour former `\\relaxx` (commande inconnue).

    Exemple réel du corpus : N10/S05/CA06 contient :
        `$\\xintiieval{N10S05C06_a}x + \\xintiieval{N10S05C06_b}x$`
    où le `x` est la variable algébrique (le ax + bx du cours).

    Le patch v0.15.2.2.2.1 émet maintenant `\\relax{}` au lieu de `\\relax`.
    """
    def test_xintiieval_suivi_de_lettre_x(self):
        """Cas exact du corpus N10/S05/CA06."""
        s = r'$\xintiieval{N10S05C06_a}x + \xintiieval{N10S05C06_b}x$'
        out, _ = migrer_chaine(s)
        # \relaxx (collé) ne doit JAMAIS apparaître
        assert r'\relaxx' not in out
        # Forme attendue : \relax{}x
        assert out == r'$\xinttheiiexpr N10S05C06_a\relax{}x + \xinttheiiexpr N10S05C06_b\relax{}x$'

    def test_xintfloateval_suivi_de_lettre(self):
        s = r'$\xintfloateval{p}km$'
        out, _ = migrer_chaine(s)
        assert r'\relaxk' not in out
        assert out == r'$\xintthefloatexpr p\relax{}km$'

    def test_xintiieval_suivi_de_dollar(self):
        """Cas le plus fréquent : suivi de `$` (fin de math). Pas de bug
        mais on vérifie que le `{}` est inoffensif."""
        s = r'$\xintiieval{p}$'
        out, _ = migrer_chaine(s)
        # `\relax{}$` est équivalent à `\relax$` ; le `{}` est inoffensif
        assert out == r'$\xinttheiiexpr p\relax{}$'

    def test_xintiieval_suivi_de_virgule(self):
        """Cas N10/S01/CA11 : suivi de `,` (LaTeX, virgule)."""
        s = r'$\xintiieval{a},\xintiieval{b}$'
        out, _ = migrer_chaine(s)
        assert out == r'$\xinttheiiexpr a\relax{},\xinttheiiexpr b\relax{}$'

    def test_xintiieval_suivi_d_un_backslash(self):
        """Cas N10/S01/CA04 : suivi de `\\,` (espace fine math)."""
        s = r'$\xintiieval{p}\,\%$'
        out, _ = migrer_chaine(s)
        # `\relax{}\,` est correct ; sans `{}` ce serait `\relax\,` qui marche
        # aussi (\, est une commande, pas une lettre), mais on uniformise.
        assert out == r'$\xinttheiiexpr p\relax{}\,\%$'


class TestCorpusReel:
    def test_carte_avec_quatre_xintiieval(self):
        """N10/S10/CA13 — 4 \\xintiieval dans le recto."""
        s = (r"Durée entre $\xintiieval{N10S10C13_hd}$h"
             r"$\xintiieval{N10S10C13_md}$ et "
             r"$\xintiieval{N10S10C13_hf}$h"
             r"$\xintiieval{N10S10C13_mf}$")
        out, stats = migrer_chaine(s)
        assert stats == {'xintiieval': 4}
        # Vérif individuelle des 4 substitutions
        assert r'\xinttheiiexpr N10S10C13_hd\relax{}' in out
        assert r'\xinttheiiexpr N10S10C13_md\relax{}' in out
        assert r'\xinttheiiexpr N10S10C13_hf\relax{}' in out
        assert r'\xinttheiiexpr N10S10C13_mf\relax{}' in out
        # Aucun \xintiieval restant
        assert r'\xintiieval' not in out

    def test_xintiieval_et_xintfloateval_dans_meme_carte(self):
        """N10/S01/CA13 — mélange xintiieval (numérateur) et xintfloateval (résultat)."""
        s = (r"Donne l'écriture décimale de:\smallskip\par "
             r"$\frac{\xintiieval{N10S01C13_num}}{100}$\smallskip\par "
             r"Réponse : $\xintfloateval{N10S01C13_res}$")
        out, stats = migrer_chaine(s)
        assert stats == {'xintiieval': 1, 'xintfloateval': 1}
        assert r'\xinttheiiexpr N10S01C13_num\relax{}' in out
        assert r'\xintthefloatexpr N10S01C13_res\relax{}' in out


# ── Idempotence et non-corruption ────────────────────────────────────────────

class TestIdempotence:
    def test_appliquer_deux_fois_donne_meme_resultat(self):
        """Garde-fou : la migration est idempotente."""
        s = r'$\xintiieval{p}$ et $\xintfloateval{q}$'
        out1, stats1 = migrer_chaine(s)
        out2, stats2 = migrer_chaine(out1)
        assert out1 == out2
        assert stats2 == {}

    def test_pas_de_xint_pas_de_modification(self):
        """Une chaîne sans macros xint doit être renvoyée à l'identique."""
        s = r'Bonjour \textbf{le} monde \smallskip avec $\frac{1}{2}$.'
        out, stats = migrer_chaine(s)
        assert out == s
        assert stats == {}

    def test_chaine_vide(self):
        out, stats = migrer_chaine('')
        assert out == ''
        assert stats == {}


# ── Cas du bug v0.15.2.2.2.2 — siunitx ──────────────────────────────────────

class TestBugSiunitxNum:
    r"""v0.15.2.2.2.3 — Bug siunitx + correctif définitif.

    Historique :
    - v0.15.2.2.2.2 (faux correctif) : on enveloppait dans
      `\expanded{\noexpand\num{...}}` en croyant que `\xintthefloatexpr`
      cassait siunitx. C'était faux.
    - v0.15.2.2.2.3 (vrai correctif) : le coupable est le `\relax{}` (avec
      accolades vides) à l'intérieur du `\num{...}`. Le groupe vide `{}`
      reste dans l'argument et siunitx le lit comme un `}` parasite.

    MWE à l'appui :
      - `\num{\xintthefloatexpr p\relax}`   → COMPILE
      - `\num{\xintthefloatexpr p\relax{}}` → CRASHE (extra })

    Solution : dans un `\num{...}`, émettre `\relax` SANS le `{}`. Le `}`
    de fermeture du `\num{...}` termine l'argument, donc aucune lettre ne
    peut se coller à `\relax` : le `{}` est inutile et nuisible ici.
    """
    def test_num_avec_xintfloateval_simple(self):
        """N10/S01/CA14 verso : $\\num{\\xintfloateval{N10S01C14_res}}$"""
        s = r'$\num{\xintfloateval{N10S01C14_res}}$'
        out, stats = migrer_chaine(s)
        assert stats == {'num_xintfloateval': 1}
        # Forme expansible SANS {} (le } de \num termine l'argument)
        assert out == r'$\num{\xintthefloatexpr N10S01C14_res\relax}$'
        # Pas de \xintfloateval restant
        assert r'\xintfloateval' not in out
        # Surtout : PAS de \relax{} dans le \num (cause du crash siunitx)
        assert r'\relax{}}' not in out

    def test_num_avec_options_siunitx(self):
        """N10/S01/CA13 verso : siunitx avec options round-mode et marker."""
        s = (r'$\num[round-mode=none,output-decimal-marker={,}]'
             r'{\xintfloateval{N10S01C13_res}}$')
        out, stats = migrer_chaine(s)
        assert stats == {'num_xintfloateval': 1}
        # Les options sont préservées telles quelles
        assert r'[round-mode=none,output-decimal-marker={,}]' in out
        # Forme finale attendue (sans {} après relax)
        attendu = (r'$\num[round-mode=none,output-decimal-marker={,}]'
                   r'{\xintthefloatexpr N10S01C13_res\relax}$')
        assert out == attendu

    def test_num_avec_xintiieval(self):
        """Cas théorique : \\num{\\xintiieval{...}}."""
        s = r'$\num{\xintiieval{n}}$'
        out, stats = migrer_chaine(s)
        assert stats == {'num_xintiieval': 1}
        assert out == r'$\num{\xinttheiiexpr n\relax}$'

    def test_num_et_xintiieval_orphelin_meme_chaine(self):
        """Cas mixte : un \\num{\\xint*eval} + un \\xint*eval hors \\num.

        Le \\xint*eval hors \\num garde le {} (cas général v0.15.2.2.2.1),
        celui dans le \\num n'a PAS de {} (cas siunitx v0.15.2.2.2.3).
        """
        s = r'$\num{\xintfloateval{a}} + \xintiieval{b}$'
        out, stats = migrer_chaine(s)
        assert stats == {'num_xintfloateval': 1, 'xintiieval': 1}
        assert r'\xintfloateval' not in out
        # Dans le \num : \relax (sans {}) ; hors \num : \relax{} (avec {})
        attendu = r'$\num{\xintthefloatexpr a\relax} + \xinttheiiexpr b\relax{}$'
        assert out == attendu

    def test_num_carte_N10S02C04_multi_occurrences(self):
        """N10/S02/CA04 : 2 \\num{\\xintfloateval{...}} dans la même chaîne."""
        s = (r'$\num{\xintfloateval{N10S02C04_a}}$ \;\ldots\; '
             r'$\num{\xintfloateval{N10S02C04_b}}$')
        out, stats = migrer_chaine(s)
        assert stats == {'num_xintfloateval': 2}
        # Aucun \relax{} fatal dans les \num
        assert r'\relax{}}' not in out
        # 2 \num convertis
        assert out.count(r'\num{\xintthefloatexpr') == 2

    def test_idempotence_avec_num(self):
        """Une chaîne déjà migrée ne doit plus être touchée."""
        s = r'$\num{\xintthefloatexpr p\relax}$'
        out, stats = migrer_chaine(s)
        assert out == s
        assert stats == {}


# ── Cas qui doivent rester intacts (autres macros xint) ──────────────────────

class TestNonConcernes:
    def test_xintdefiivar_intact(self):
        """Les assignations ne sont pas concernées."""
        s = r'\xintdefiivar p := randrange(5,95);'
        out, stats = migrer_chaine(s)
        assert out == s
        assert stats == {}

    def test_xintdeffloatvar_intact(self):
        """Idem pour les assignations float."""
        s = r'\xintdeffloatvar res := p / 100;'
        out, stats = migrer_chaine(s)
        assert out == s
        assert stats == {}

    def test_xintiiifCmp_intact(self):
        """Les conditionnels xint sont laissés tels quels (3 cas dans corpus N10)."""
        s = r'\xintiiifCmp{a}{b}{<}{=}{>}'
        out, stats = migrer_chaine(s)
        assert out == s
        assert stats == {}
