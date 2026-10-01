r"""
tests/test_paquet_parseur.py — Tests du parseur de .sty pour le chantier 14.

Couvre :
  - strip_comments : % / \%
  - extract_balanced : accolades imbriquées, caractères échappés
  - parser_sty : les 7 primitives reconnues, \define@cmdkey
  - analyser_corps : filtrage des primitives LaTeX, détection \\ de saut de ligne
  - extraire_requirepackage : options et sans options
"""

from __future__ import annotations
import pytest

from services.paquet_parseur import (
    strip_comments,
    extract_balanced,
    parser_sty,
    extraire_requirepackage,
    Definition,
    PRIMITIVES_LATEX,
)


# ── strip_comments ────────────────────────────────────────────────────────────

class TestStripComments:

    def test_commentaire_simple(self):
        src = "abc % commentaire\nsuite"
        assert strip_comments(src) == "abc \nsuite"

    def test_pourcent_echappe_preserve(self):
        src = r"taux 5\% de remise"
        assert strip_comments(src) == r"taux 5\% de remise"

    def test_ligne_commentaire_entiere(self):
        src = "% toute la ligne\nvrai code"
        assert strip_comments(src) == "\nvrai code"

    def test_sans_commentaire(self):
        src = "\\newcommand{\\foo}{bar}"
        assert strip_comments(src) == src

    def test_multilignes_preserve_sauts(self):
        """Les numéros de lignes doivent rester cohérents."""
        src = "ligne1 % comm\nligne2\nligne3 % autre"
        out = strip_comments(src)
        assert out.count('\n') == src.count('\n')


# ── extract_balanced ──────────────────────────────────────────────────────────

class TestExtractBalanced:

    def test_accolades_simples(self):
        src = "{contenu}"
        contenu, pos = extract_balanced(src, 0, '{', '}')
        assert contenu == "contenu"
        assert pos == 9

    def test_accolades_imbriquees(self):
        src = "{a{b}c}"
        contenu, pos = extract_balanced(src, 0, '{', '}')
        assert contenu == "a{b}c"

    def test_crochets(self):
        src = "[opt=val]"
        contenu, pos = extract_balanced(src, 0, '[', ']')
        assert contenu == "opt=val"

    def test_accolade_echappee_ignoree(self):
        src = r"{a\}b}"  # \} ne compte pas comme fermante
        contenu, pos = extract_balanced(src, 0, '{', '}')
        assert contenu == r"a\}b"

    def test_non_ferme_leve_erreur(self):
        with pytest.raises(ValueError, match="non fermé"):
            extract_balanced("{jamais ferme", 0, '{', '}')

    def test_mauvaise_position_leve_erreur(self):
        with pytest.raises(ValueError, match="attendu"):
            extract_balanced("abc{def}", 0, '{', '}')


# ── parser_sty : primitives individuelles ──────────────────────────────────────

class TestParserStyPrimitives:

    def test_newcommand_simple(self):
        src = r"\newcommand{\foo}{bar}"
        defs = parser_sty(src, fichier_source='test.sty')
        assert len(defs) == 1
        assert defs[0].nom == '\\foo'
        assert defs[0].type_latex == 'command'
        assert defs[0].corps == 'bar'
        assert defs[0].args_spec == ''

    def test_newcommand_avec_nbargs(self):
        src = r"\newcommand{\frac}[2]{\dfrac{#1}{#2}}"
        defs = parser_sty(src)
        assert len(defs) == 1
        assert defs[0].args_spec == '[2]'

    def test_newcommand_avec_default(self):
        src = r"\newcommand{\boite}[2][jaune]{couleur=#1, contenu=#2}"
        defs = parser_sty(src)
        assert defs[0].args_spec == '[2][jaune]'

    def test_newcommand_sans_accolades_autour_nom(self):
        """Variante syntaxique : \newcommand\foo{bar}"""
        src = r"\newcommand\foo{bar}"
        defs = parser_sty(src)
        assert len(defs) == 1
        assert defs[0].nom == '\\foo'

    def test_renewcommand(self):
        src = r"\renewcommand{\foo}{nouveau}"
        defs = parser_sty(src)
        assert defs[0].type_latex == 'command'
        assert defs[0].nom == '\\foo'

    def test_newenvironment(self):
        src = r"\newenvironment{monenv}[1]{debut#1}{fin}"
        defs = parser_sty(src)
        assert len(defs) == 1
        d = defs[0]
        assert d.nom == 'monenv'
        assert d.type_latex == 'environment'
        assert d.args_spec == '[1]'
        assert d.corps == 'debut#1'
        assert d.corps_fin == 'fin'

    def test_newenvironment_avec_begin_dans_corps(self):
        r"""Cas qui fait planter TexSoup : \begin{...} dans le corps
        d'une \newenvironment n'a pas de \end correspondant au top-level."""
        src = r"\newenvironment{monenv}{\begin{center}}{\end{center}}"
        defs = parser_sty(src)
        assert len(defs) == 1
        assert defs[0].corps == r'\begin{center}'

    def test_newtcolorbox(self):
        src = r"\newtcolorbox{maboite}[2][default]{colback=#1, title=#2}"
        defs = parser_sty(src)
        assert defs[0].type_latex == 'tcolorbox'
        assert defs[0].nom == 'maboite'

    def test_newcounter(self):
        src = r"\newcounter{monctr}"
        defs = parser_sty(src)
        assert defs[0].type_latex == 'counter'
        assert defs[0].nom == 'monctr'

    def test_newif(self):
        src = r"\newif\ifoption"
        defs = parser_sty(src)
        assert defs[0].type_latex == 'if'
        assert defs[0].nom == '\\ifoption'

    def test_define_cmdkey(self):
        src = r"\define@cmdkey[seq]{exercice}{nom}[defaut]{}"
        defs = parser_sty(src)
        assert len(defs) == 1
        assert defs[0].type_latex == 'cmdkey'
        assert defs[0].nom == '\\cmdseq@exercice@nom'
        # Le texte_complet doit inclure TOUS les arguments (prefix, famille,
        # clé, défaut, action) — sinon l'inlining ultérieur dans un préambule
        # planterait avec une erreur xkeyval (cf. bug v0.6.4).
        assert defs[0].texte_complet == r'\define@cmdkey[seq]{exercice}{nom}[defaut]{}'

    def test_define_cmdkey_avec_default_et_action_vide(self):
        """Cas réel du paquet seqenseigne — \\define@cmdkey[seq]{colEnum}{nbCols}[2]{}.

        Régression de v0.6.4 : l'ancienne regex tronquait `texte_complet` après
        la clé et perdait à la fois la valeur par défaut [2] (cruciale pour
        xkeyval : sans elle, \\setkeys sans valeur explicite plante avec
        `no value specified for key`) et l'action {} (aussi obligatoire).
        """
        src = r"\define@cmdkey[seq]{colEnum}{nbCols}[2]{}"
        defs = parser_sty(src)
        assert len(defs) == 1
        assert defs[0].type_latex == 'cmdkey'
        # On exige l'intégralité de la définition, valeur par défaut comprise
        assert defs[0].texte_complet == src

    def test_define_cmdkey_default_avec_macro(self):
        """Cas avec une macro dans la valeur par défaut — \\arabic*).

        Issu de \\define@cmdkey[seq]{colEnum}{label}[\\arabic*)]{}.
        Vérifie que le scanner gère bien les caractères spéciaux dans [...]."""
        src = r"\define@cmdkey[seq]{colEnum}{label}[\arabic*)]{}"
        defs = parser_sty(src)
        assert len(defs) == 1
        assert defs[0].texte_complet == src

    def test_define_cmdkey_action_non_vide(self):
        """Cas avec action non-vide — assignation d'un compteur, par exemple."""
        src = r"\define@cmdkey[seq]{xxx}{val}[0]{\setcounter{c}{#1}}"
        defs = parser_sty(src)
        assert len(defs) == 1
        assert defs[0].texte_complet == src

    def test_define_cmdkey_consecutifs(self):
        """Plusieurs \\define@cmdkey à la suite : chacun doit être capturé
        complètement, sans déborder sur le suivant."""
        src = (r"\define@cmdkey[seq]{colEnum}{nbCols}[2]{}" + "\n"
               r"\define@cmdkey[seq]{colEnum}{label}[\arabic*)]{}")
        defs = parser_sty(src)
        assert len(defs) == 2
        assert defs[0].texte_complet == r'\define@cmdkey[seq]{colEnum}{nbCols}[2]{}'
        assert defs[1].texte_complet == r'\define@cmdkey[seq]{colEnum}{label}[\arabic*)]{}'

    # ── v0.13.7.2.2 — \define@choicekey (xkeyval) ───────────────────────────
    # Régression : le parseur connaissait \define@cmdkey mais pas
    # \define@choicekey. Conséquence : pour l'environnement seqQcm qui
    # utilise \define@choicekey pour la clé `explication`, la définition
    # n'était pas indexée. Au moment de générer le préambule d'un atome
    # contenant `\begin{seqQcm}`, la fermeture transitive cherchait
    # \cmdseq@seqQcm@explication (déclaré dans macros_appelees) mais ne
    # le trouvait pas, donc ne l'incluait pas. À la compilation,
    # \setkeys[seq]{seqQcm}{...,explication,...} échouait avec
    # « key explication unknown ».

    def test_define_choicekey_simple(self):
        """Cas réel : \\define@choicekey[seq]{seqQcm}{explication}
                       [\\val\\nr]{oui,non}[oui]{action}.

        On exige la même chose que pour cmdkey :
        - une définition indexée (au même format synthétique)
        - texte_complet COMPLET (sans troncature avant l'action)
        """
        src = (r"\define@choicekey[seq]{seqQcm}{explication}"
               r"[\val\nr]{oui,non}[oui]{\def\foo{bar}}")
        defs = parser_sty(src)
        assert len(defs) == 1
        assert defs[0].type_latex == 'cmdkey'
        # Convention de nommage : identique à cmdkey (les deux clés sont
        # consommées par \setkeys de la même manière côté LaTeX)
        assert defs[0].nom == '\\cmdseq@seqQcm@explication'
        # texte_complet doit contenir l'intégralité, action incluse
        assert defs[0].texte_complet == src

    def test_define_choicekey_avec_corps_multiligne(self):
        """Cas plus représentatif : action multi-ligne avec \\ifcase
        (comme dans le .dtx réel de seqenseigne pour la clé explication
        du seqQcm)."""
        src = (
            r"\define@choicekey[seq]{seqQcm}{explication}"
            r"[\val\nr]{oui,non}[oui]{%" "\n"
            r"\ifcase\nr\relax" "\n"
            r"\def\cmdseq@seqQcm@explication{oui}" "\n"
            r"\or" "\n"
            r"\def\cmdseq@seqQcm@explication{non}" "\n"
            r"\fi" "\n"
            r"}"
        )
        defs = parser_sty(src)
        assert len(defs) == 1
        assert defs[0].type_latex == 'cmdkey'
        assert defs[0].nom == '\\cmdseq@seqQcm@explication'
        # L'action complète (8 lignes) doit être dans texte_complet
        assert r'\ifcase\nr' in defs[0].texte_complet
        assert r'\fi' in defs[0].texte_complet

    def test_define_choicekey_sans_default_optionnel(self):
        """Cas où le default optionnel est absent : [\\val\\nr]{oui,non}{action}
        (pas de [default] entre choix et action)."""
        src = (r"\define@choicekey[seq]{famille}{cle}"
               r"[\val\nr]{a,b}{\def\foo{bar}}")
        defs = parser_sty(src)
        assert len(defs) == 1
        assert defs[0].nom == '\\cmdseq@famille@cle'
        assert defs[0].texte_complet == src

    def test_define_cmdkey_et_choicekey_melanges(self):
        """Quand on a un mix de cmdkey et choicekey sur la même famille
        (cas réel du paquet seqenseigne pour seqQcm), les deux types sont
        indexés et leurs texte_complet respectifs ne se chevauchent pas.
        """
        src = (
            r"\define@cmdkey[seq]{seqQcm}{ptOK}{}" + "\n"
            + r"\define@cmdkey[seq]{seqQcm}{ptKO}{}" + "\n"
            + r"\define@choicekey[seq]{seqQcm}{explication}"
              r"[\val\nr]{oui,non}[oui]{\def\foo{bar}}"
        )
        defs = parser_sty(src)
        noms = {d.nom for d in defs}
        assert '\\cmdseq@seqQcm@ptOK' in noms
        assert '\\cmdseq@seqQcm@ptKO' in noms
        assert '\\cmdseq@seqQcm@explication' in noms
        # Au minimum 3 entrées (les deux cmdkey + le choicekey)
        assert len([d for d in defs
                    if d.nom.startswith('\\cmdseq@seqQcm@')]) == 3


# ── parser_sty : analyse des dépendances ──────────────────────────────────────

class TestAnalyserCorps:

    def test_macros_appelees(self):
        src = r"\newcommand{\foo}{\seqBar \seqBaz{arg}}"
        defs = parser_sty(src)
        assert defs[0].macros_appelees == {'\\seqBar', '\\seqBaz'}

    def test_primitives_exclues(self):
        src = r"\newcommand{\foo}{\textbf{\sin x} \hline}"
        defs = parser_sty(src)
        # textbf, sin, hline sont des primitives → pas dans les dépendances
        assert defs[0].macros_appelees == set()

    def test_environnements_detectes(self):
        src = r"\newcommand{\foo}{\begin{boitePale}texte\end{boitePale}}"
        defs = parser_sty(src)
        assert 'boitePale' in defs[0].environnements_utilises

    def test_primitives_env_exclues(self):
        src = r"\newcommand{\foo}{\begin{center}centré\end{center}}"
        defs = parser_sty(src)
        assert 'center' not in defs[0].environnements_utilises

    def test_macros_de_un_caractere_exclues(self):
        r"""\x dans \foreach \x/\y/\z ne doit pas être considéré comme dépendance."""
        src = r"\newcommand{\foo}{\foreach \x in {1,2,3}{\draw (\x,0);}}"
        defs = parser_sty(src)
        assert '\\x' not in defs[0].macros_appelees

    # ── v0.13.7.2.3 — Détection des compteurs référencés par nom textuel ──
    # Régression : seqQcm fait `\setcounter{seq@qcm@alphcode}{40}` mais le
    # nom du compteur (sans backslash) n'était pas détecté. Conséquence :
    # la fermeture transitive ne tirait pas la définition du compteur, et
    # à la compilation : « No counter 'seq@qcm@alphcode' defined ».

    def test_setcounter_detecte_le_compteur(self):
        """\\setcounter{nom}{val} ajoute `nom` (sans backslash) à
        macros_appelees, pour permettre à la fermeture transitive de
        tirer le \\newcounter correspondant."""
        src = r"\newcommand{\foo}{\setcounter{monCompteur}{42}}"
        defs = parser_sty(src)
        assert 'monCompteur' in defs[0].macros_appelees

    def test_stepcounter_detecte_le_compteur(self):
        src = r"\newcommand{\foo}{\stepcounter{monCompteur}}"
        defs = parser_sty(src)
        assert 'monCompteur' in defs[0].macros_appelees

    def test_refstepcounter_detecte_le_compteur(self):
        src = r"\newcommand{\foo}{\refstepcounter{monCompteur}}"
        defs = parser_sty(src)
        assert 'monCompteur' in defs[0].macros_appelees

    def test_addtocounter_detecte_le_compteur(self):
        src = r"\newcommand{\foo}{\addtocounter{monCompteur}{2}}"
        defs = parser_sty(src)
        assert 'monCompteur' in defs[0].macros_appelees

    def test_value_detecte_le_compteur(self):
        src = r"\newcommand{\foo}{\ifnum\value{monCompteur} < 3 truc \fi}"
        defs = parser_sty(src)
        assert 'monCompteur' in defs[0].macros_appelees

    def test_forloop_detecte_le_compteur(self):
        r"""\forloop (du paquet `forloop`) prend le compteur en 1er arg."""
        src = r"\newcommand{\foo}{\forloop{monCompteur}{0}{\value{monCompteur}<3}{X}}"
        defs = parser_sty(src)
        assert 'monCompteur' in defs[0].macros_appelees

    def test_arabic_detecte_le_compteur(self):
        src = r"\newcommand{\foo}{Question \arabic{monCompteur}.}"
        defs = parser_sty(src)
        assert 'monCompteur' in defs[0].macros_appelees

    def test_alph_detecte_le_compteur(self):
        src = r"\newcommand{\foo}{\alph{monCompteur})}"
        defs = parser_sty(src)
        assert 'monCompteur' in defs[0].macros_appelees

    def test_compteurs_multiples_dans_un_corps(self):
        """Cas réel seqQcm : 4 références à 2 compteurs différents."""
        src = (
            r"\newenvironment{seqQcm}[1][]{%" + "\n"
            r"\setcounter{seq@qcm@alphcode}{40}" + "\n"
            r"\forloop{seq@qcm@iter}{0}"
            r"{\value{seq@qcm@iter} < \cmdseq@seqQcm@nbReps}"
            r"{\stepcounter{seq@qcm@alphcode} truc}" + "\n"
            r"}{}"
        )
        defs = parser_sty(src)
        seqQcm = next(d for d in defs if d.nom == 'seqQcm')
        assert 'seq@qcm@alphcode' in seqQcm.macros_appelees
        assert 'seq@qcm@iter' in seqQcm.macros_appelees

    def test_compteurs_LaTeX_standard_aussi_detectes(self):
        """Les compteurs standard (page, section, equation…) sont aussi
        détectés. Pas grave : la fermeture transitive les ignore puisqu'ils
        ne sont pas dans paquet_definitions. C'est la cohérence qui compte :
        on ne sait pas a priori si un compteur est standard ou local."""
        src = r"\newcommand{\foo}{\setcounter{equation}{0}}"
        defs = parser_sty(src)
        # Ce qui compte : la détection a lieu (pas de filtrage à ce niveau).
        assert 'equation' in defs[0].macros_appelees


# ── extraire_requirepackage ───────────────────────────────────────────────────

class TestExtraireRequirepackage:

    def test_sans_options(self):
        src = r"\RequirePackage{tikz}"
        assert extraire_requirepackage(src) == [('tikz', '')]

    def test_avec_options(self):
        src = r"\RequirePackage[theorems,breakable]{tcolorbox}"
        assert extraire_requirepackage(src) == [('tcolorbox', 'theorems,breakable')]

    def test_plusieurs_paquets(self):
        src = r"""
\RequirePackage{tikz}
\RequirePackage[utf8]{inputenc}
\RequirePackage{amsmath}
"""
        result = extraire_requirepackage(src)
        assert len(result) == 3
        assert result[0] == ('tikz', '')
        assert result[1] == ('inputenc', 'utf8')
        assert result[2] == ('amsmath', '')

    def test_ignore_commentaires(self):
        src = r"""
% \RequirePackage{faux}   <- commenté
\RequirePackage{vrai}
"""
        assert extraire_requirepackage(src) == [('vrai', '')]


# ── Test d'intégration sur le vrai paquet ─────────────────────────────────────

class TestIntegration:
    """Tests contre le paquet réel si disponible."""

    @pytest.fixture
    def paquet_dir(self):
        from pathlib import Path
        # v0.41.3 — Paquet LaTeX du projet, voisin d'appli/ :
        # seqenseigne/reference/paquet. Ignoré sur un clone GitHub (qui ne
        # contient que appli/). Le paquet peut être directement dans
        # reference/paquet ou dans un sous-dossier paquet/.
        racine = Path(__file__).resolve().parent.parent.parent / "reference" / "paquet"
        for p in (racine, racine / "paquet"):
            if (p / "seqenseigne-core.sty").is_file():
                return p
        pytest.skip(f"Paquet LaTeX non disponible dans {racine}")

    def test_core_sty_parse(self, paquet_dir):
        src = (paquet_dir / 'seqenseigne-core.sty').read_text(encoding='utf-8')
        defs = parser_sty(src, fichier_source='seqenseigne-core.sty')
        # On attend au moins 100 définitions ; la valeur exacte peut évoluer
        assert len(defs) >= 100, f"Seulement {len(defs)} définitions parsées"

        noms = {d.nom for d in defs}
        # Quelques macros-clés qu'on doit retrouver
        # NB : depuis v0.11.5, \seqCorrige et seqExercice ont été extraits
        # vers seqenseigne-core-exos.sty (cf. test_core_exos_sty_parse).
        assert '\\seqFrac' in noms
        assert 'seqNotion' in noms

    def test_core_exos_sty_parse(self, paquet_dir):
        """v0.11.5+ : module core-exos extrait de core."""
        src = (paquet_dir / 'seqenseigne-core-exos.sty').read_text(encoding='utf-8')
        defs = parser_sty(src, fichier_source='seqenseigne-core-exos.sty')
        noms = {d.nom for d in defs}
        # Macros-clés du module exos
        assert '\\seqCorrige' in noms
        assert 'seqExercice' in noms
        # v0.11.5 — Macros de remédiation et cadre de réponse
        assert '\\seqInitRemediation' in noms
        assert '\\seqRemediation' in noms
        assert '\\seqCadreReponse' in noms
        assert '\\seqAfficheRemediations' in noms
        assert '\\seqAfficheCorrigesRemediation' in noms

    def test_theme_sty_parse(self, paquet_dir):
        src = (paquet_dir / 'seqenseigne-theme.sty').read_text(encoding='utf-8')
        defs = parser_sty(src, fichier_source='seqenseigne-theme.sty')
        noms = {d.nom for d in defs}
        assert '\\seqBoiteJaune' in noms

    def test_seqFrac_corps_correct(self, paquet_dir):
        src = (paquet_dir / 'seqenseigne-core.sty').read_text(encoding='utf-8')
        defs = parser_sty(src, fichier_source='seqenseigne-core.sty')
        d_frac = next(d for d in defs if d.nom == '\\seqFrac')
        assert r'\dfrac' in d_frac.corps
        assert d_frac.args_spec == '[2]'

    def test_pas_de_faux_doublons_massifs(self, paquet_dir):
        """Seul \\ifdocstd est connu pour être délibérément en doublon."""
        src_core = (paquet_dir / 'seqenseigne-core.sty').read_text(encoding='utf-8')
        defs_core = parser_sty(src_core)
        src_theme = (paquet_dir / 'seqenseigne-theme.sty').read_text(encoding='utf-8')
        defs_theme = parser_sty(src_theme)

        noms_core = {d.nom for d in defs_core}
        noms_theme = {d.nom for d in defs_theme}
        doublons = noms_core & noms_theme
        # Tolérance : uniquement ifdocstd connu
        assert doublons.issubset({'\\ifdocstd'}), (
            f"Doublons inattendus entre core et theme : {doublons}"
        )


# ── v0.9.1 — Mapping macros → paquets externes ──────────────────────────────

class TestMacrosPaquetsExternesV091:
    """v0.9.1 — Vérification de mappings macro → paquet TeX externe.

    Ces mappings servent à `latex_rendu_atome.detecter_paquets_tex_manquants`
    pour ajouter dynamiquement des `\\usepackage{...}` au préambule
    reconstruit lorsqu'un atome utilise une macro fournie par un paquet
    qui n'est pas dans `PAQUETS_NOYAU`.

    Bug corrigé : `\\wideparen` était mappé sur 'wideparen', un paquet
    qui n'existe pas. La macro vient en réalité du paquet 'yhmath'
    (Yannis Haralambous, ctan.org/pkg/yhmath). Détecté par batch
    méthodes du 27/04/26 sur N11/S11/M02-04 et N12/S11/M02 — chaque
    `\\usepackage{wideparen}` injecté faisait planter la compilation
    sur « LaTeX Error: File `wideparen.sty' not found. ».
    """

    def test_wideparen_mappe_vers_yhmath(self):
        """\\wideparen doit être mappé vers le paquet 'yhmath', pas
        'wideparen' (qui n'existe pas)."""
        from services.paquet_parseur import MACROS_PAQUETS_EXTERNES
        assert '\\wideparen' in MACROS_PAQUETS_EXTERNES, (
            "\\wideparen doit être listé dans MACROS_PAQUETS_EXTERNES"
        )
        assert MACROS_PAQUETS_EXTERNES['\\wideparen'] == 'yhmath', (
            f"\\wideparen mappé vers {MACROS_PAQUETS_EXTERNES['\\wideparen']!r}, "
            "attendu : 'yhmath'"
        )

    def test_aucune_macro_mappe_vers_wideparen(self):
        """Aucune macro ne doit être mappée vers le paquet inexistant
        'wideparen'. Garde-fou contre une régression du fix v0.9.1."""
        from services.paquet_parseur import MACROS_PAQUETS_EXTERNES
        macros_vers_wideparen = [
            m for m, p in MACROS_PAQUETS_EXTERNES.items() if p == 'wideparen'
        ]
        assert not macros_vers_wideparen, (
            f"Le paquet 'wideparen' n'existe pas sur CTAN. "
            f"Macros mappées vers lui (à corriger) : {macros_vers_wideparen}"
        )
