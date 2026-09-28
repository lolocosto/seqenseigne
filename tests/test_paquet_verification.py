r"""
tests/test_paquet_verification.py — Tests de la vérification de couverture.

Couvre :
  - extraire_utilisations : filtrage \\ (saut de ligne), macros 1 caractère
  - extraire_macros_definies_localement : \newcommand, \def, \foreach, \tkzGetLength
  - classification couvert/externe/non_couvert
"""

from __future__ import annotations
import pytest
import sqlite3
from pathlib import Path

from scripts.peuplement_14_verif_couverture import (
    extraire_utilisations,
    extraire_macros_definies_localement,
    couverture,
    MACROS_PAQUETS_EXTERNES,
)


# ── extraire_utilisations ─────────────────────────────────────────────────────

class TestExtraireUtilisations:

    def test_macro_simple(self):
        macros, envs = extraire_utilisations(r"\seqFrac{1}{2}")
        assert macros == {'\\seqFrac'}
        assert envs == set()

    def test_environnement(self):
        macros, envs = extraire_utilisations(
            r"\begin{seqNotion}{01}{Titre}contenu\end{seqNotion}"
        )
        assert 'seqNotion' in envs

    def test_primitives_latex_filtrees(self):
        """sin, cos, hline, textbf sont des primitives, pas des dépendances."""
        macros, envs = extraire_utilisations(
            r"\sin(x) + \cos(y) \hline \textbf{gras}"
        )
        assert macros == set()

    def test_saut_de_ligne_pas_capture_comme_macro(self):
        r"""Bug historique : `\\Il` (où `\\` est un saut de ligne) ne doit
        PAS être interprété comme la macro `\Il`."""
        texte = r"Première ligne.\\Il faut ensuite calculer..."
        macros, envs = extraire_utilisations(texte)
        assert '\\Il' not in macros

    def test_macros_un_caractere_filtrees(self):
        r"""`\x` et `\y` (variables de \foreach) ne sont pas des dépendances."""
        macros, envs = extraire_utilisations(r"\foreach \x in {1,2} {\draw (\x,0);}")
        assert '\\x' not in macros

    def test_texte_vide(self):
        macros, envs = extraire_utilisations('')
        assert macros == set() and envs == set()


# ── extraire_macros_definies_localement ───────────────────────────────────────

class TestExtraireMacrosDefiniesLocalement:

    def test_newcommand_avec_accolades(self):
        src = r"\newcommand{\maMacro}{contenu}"
        assert extraire_macros_definies_localement(src) == {'\\maMacro'}

    def test_newcommand_sans_accolades(self):
        src = r"\newcommand\maMacro{contenu}"
        assert extraire_macros_definies_localement(src) == {'\\maMacro'}

    def test_plusieurs_formes(self):
        src = r"""
\newcommand{\un}{1}
\renewcommand\deux{2}
\def\trois{3}
\providecommand{\quatre}{4}
"""
        defs = extraire_macros_definies_localement(src)
        assert defs == {'\\un', '\\deux', '\\trois', '\\quatre'}

    def test_foreach_variables(self):
        r"""Les variables de \foreach \x/\y/\z in {...} sont locales."""
        src = r"\foreach \x/\lab/\fmt in {0.5/A/F1}{\draw (\x,0);}"
        defs = extraire_macros_definies_localement(src)
        assert '\\x' in defs
        assert '\\lab' in defs
        assert '\\fmt' in defs

    def test_tkzGetLength(self):
        r"""\tkzGetLength{rCD} définit \rCD."""
        src = r"\tkzCalcLength(C,D) \tkzGetLength{rCD}"
        defs = extraire_macros_definies_localement(src)
        assert '\\rCD' in defs

    def test_tkzGetPoint(self):
        src = r"\tkzDefLine[parallel=through P](A,B) \tkzGetPoint{P'}"
        defs = extraire_macros_definies_localement(src)
        # P' contient une apostrophe, donc non capturé
        # mais \tkzGetFirstPoint{M} doit l'être :
        src2 = r"\tkzInterLL(A,B)(C,D) \tkzGetPoint{M}"
        defs2 = extraire_macros_definies_localement(src2)
        assert '\\M' in defs2

    def test_texte_sans_def(self):
        """Du texte sans définition → ensemble vide."""
        assert extraire_macros_definies_localement("juste du texte") == set()


# ── couverture : classification ───────────────────────────────────────────────

class TestCouverture:

    @pytest.fixture
    def db_peuplee(self, tmp_path):
        """Base minimale : 1 définition paquet + 1 exercice utilisant plusieurs macros."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Schéma minimal nécessaire (uniquement ce que scanner_atomes lit)
        conn.executescript("""
            CREATE TABLE paquet_definitions (
                nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
                corps TEXT, corps_fin TEXT, texte_complet TEXT,
                fichier_source TEXT, ligne_debut INTEGER,
                macros_appelees TEXT, environnements_utilises TEXT,
                statut_rendu_atome TEXT, contenu_atome TEXT
            );
            CREATE TABLE notions (fichier TEXT, corps TEXT);
            CREATE TABLE methodes (fichier TEXT, corps TEXT);
            CREATE TABLE exercices (
                fichier TEXT, enonce TEXT, corrige TEXT, variables TEXT
            );
        """)

        # Définir \seqFrac dans le paquet
        conn.execute("""
            INSERT INTO paquet_definitions (nom, type_latex, args_spec, corps,
                corps_fin, texte_complet, fichier_source, ligne_debut,
                macros_appelees, environnements_utilises,
                statut_rendu_atome, contenu_atome)
            VALUES ('\\seqFrac', 'command', '[2]', '', '', '',
                'seqenseigne-core.sty', 1, '[]', '[]', 'reutilise', '')
        """)

        # Un exercice qui utilise :
        #   - \seqFrac (couvert par paquet)
        #   - \tkzDefPoint (couvert externe : tkz-euclide)
        #   - \inconnue (non couvert)
        conn.execute("""
            INSERT INTO exercices (fichier, enonce, corrige, variables)
            VALUES (?, ?, ?, ?)
        """, (
            'test.tex',
            r'Calculer $\seqFrac{1}{2}$ puis \tkzDefPoint(0,0){A} et \inconnue{x}.',
            '', '',
        ))
        conn.commit()
        yield conn
        conn.close()

    def test_classification_des_trois_categories(self, db_peuplee):
        rapport = couverture(db_peuplee)
        noms_paquet = {e['nom'] for e in rapport['couvert_paquet']}
        noms_externe = {e['nom'] for e in rapport['couvert_externe']}
        noms_non_couvert = {e['nom'] for e in rapport['non_couvert']}

        assert '\\seqFrac' in noms_paquet
        assert '\\tkzDefPoint' in noms_externe
        assert '\\inconnue' in noms_non_couvert

    def test_macros_definies_localement_exclues(self, tmp_path):
        """Une macro définie dans variables ne doit pas apparaître en non-couvert."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE paquet_definitions (
                nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
                corps TEXT, corps_fin TEXT, texte_complet TEXT,
                fichier_source TEXT, ligne_debut INTEGER,
                macros_appelees TEXT, environnements_utilises TEXT,
                statut_rendu_atome TEXT, contenu_atome TEXT
            );
            CREATE TABLE notions (fichier TEXT, corps TEXT);
            CREATE TABLE methodes (fichier TEXT, corps TEXT);
            CREATE TABLE exercices (
                fichier TEXT, enonce TEXT, corrige TEXT, variables TEXT
            );
        """)
        conn.execute("""
            INSERT INTO exercices VALUES (?, ?, ?, ?)
        """, (
            'test.tex',
            r'\denomTexte et ensuite...',
            '',
            r'\newcommand\denomTexte{abc}',
        ))
        conn.commit()

        rapport = couverture(conn)
        noms_non_couvert = {e['nom'] for e in rapport['non_couvert']}
        assert '\\denomTexte' not in noms_non_couvert
        conn.close()

    def test_base_vide(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE paquet_definitions (nom TEXT PRIMARY KEY);
            CREATE TABLE notions (fichier TEXT, corps TEXT);
            CREATE TABLE methodes (fichier TEXT, corps TEXT);
            CREATE TABLE exercices (
                fichier TEXT, enonce TEXT, corrige TEXT, variables TEXT
            );
        """)
        conn.commit()
        rapport = couverture(conn)
        assert rapport['total_utilisations'] == 0
        assert rapport['non_couvert'] == []
        conn.close()


# ── Test d'intégration : dictionnaire MACROS_PAQUETS_EXTERNES cohérent ────────

class TestDictionnaireMacrosExternes:

    def test_cles_macros_ont_backslash(self):
        """Toutes les clés qui représentent des macros doivent commencer par \\."""
        # Exception : certaines clés sont des environnements, sans backslash.
        # Convention : une clé sans backslash est un environnement.
        for key in MACROS_PAQUETS_EXTERNES:
            if key.startswith('\\'):
                # macro : OK
                pass
            else:
                # environnement : doit être sans espace/caractère spécial
                assert key.replace('*', '').isalpha() or '-' in key, (
                    f"Clé suspecte (ni macro ni env) : {key!r}"
                )

    def test_valeurs_sont_strings(self):
        for key, val in MACROS_PAQUETS_EXTERNES.items():
            assert isinstance(val, str)
            assert len(val) > 0
