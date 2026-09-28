r"""
tests/test_paquet_peuplement.py — Tests du peuplement 14 (paquet → base).

Couvre :
  - DDL idempotent (CREATE TABLE IF NOT EXISTS)
  - Insertion avec application des règles de statut
  - Idempotence (rejouer le peuplement donne le même résultat)
  - Contraintes CHECK sur statut_rendu_atome
  - Détection des règles orphelines
"""

from __future__ import annotations
import json
import sqlite3
import pytest
from pathlib import Path

from scripts.peuplement_14_paquet_vers_base import (
    creer_tables, vider_tables, inserer_definitions, inserer_requirepackage,
    peupler, regles_orphelines, FICHIERS_ORDRE, DDL_PAQUET,
)
from services.paquet_parseur import Definition


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    """Base SQLite vide avec tables du chantier 14 créées."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    creer_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def paquet_mini(tmp_path):
    """Crée un mini-paquet factice pour tests d'intégration rapides."""
    d = tmp_path / "paquet"
    d.mkdir()
    # On réutilise le nom des fichiers attendus mais avec un contenu réduit
    (d / "seqenseigne-core.sty").write_text(
        r"""
\RequirePackage{tikz}
\RequirePackage[breakable]{tcolorbox}
\newcommand{\seqFrac}[2]{\dfrac{#1}{#2}}
\newcommand{\seqCorrige}[1]{%
  \scantokens{\begin{tcbverbatimwrite}{c.tex} #1 \end{tcbverbatimwrite}}%
}
\newenvironment{seqNotion}[2]{debut #1 #2}{fin}
\newif\ifdocstd
""",
        encoding='utf-8',
    )
    (d / "seqenseigne-theme.sty").write_text(
        r"""
\RequirePackage{pifont}
\newcommand{\seqBoiteJaune}[1]{\fbox{#1}}
\newif\ifdocstd
""",
        encoding='utf-8',
    )
    (d / "seqenseigne-data.sty").write_text(
        r"""
\RequirePackage{datatool}
\newcommand{\seqLoadData}{%
  \DTLloaddb{objectifs}{data/objectifs.csv}%
}
""",
        encoding='utf-8',
    )
    (d / "seqenseigne-core-exos.sty").write_text(
        r"""
\newcommand{\seqInitCorriges}{}
\newcommand{\seqAfficheCorriges}{}
\newcommand{\seqInitRemediation}{}
\newcommand{\seqAfficheRemediations}{}
\newcommand{\seqAfficheCorrigesRemediation}{}
\newcommand{\seqRemediation}[2]{}
\newcommand{\seqCadreReponse}[1]{}
""",
        encoding='utf-8',
    )
    # v0.13.5.3 — Module éval (ajouté au pipeline de peuplement).
    # Mini-définitions juste pour ne pas casser le pipeline ; les vraies
    # macros (seqEvalBareme, seqEvalObjectifs, etc.) sont testées
    # séparément dans test_v0_13_5_3_render_evaluation.
    (d / "seqenseigne-core-eval.sty").write_text(
        r"""
\newcommand{\seqTitreEval}[1][]{}
\newcommand{\seqEvalCorrigeExo}[1]{}
\newcommand{\seqEvalAfficheCorriges}{}
\newenvironment{seqEvalBareme}{}{}
\newenvironment{seqEvalObjectifs}{}{}
\newenvironment{seqEvalExercice}[1][]{}{}
""",
        encoding='utf-8',
    )
    (d / "seqenseigne-legacy.sty").write_text("", encoding='utf-8')
    # v0.13.6.2.1 — Module carte d'automatisme (ajouté au pipeline de
    # peuplement_14). Mini-définition juste pour ne pas casser le
    # pipeline ; la vraie macro \seqCarteAuto avec ses options
    # xkeyval est testée séparément dans test_v0_13_6_2_render_carte.
    (d / "seqenseigne-carte-automatisme.sty").write_text(
        r"""
\newcommand{\seqCarteAuto}[3][]{}
""",
        encoding='utf-8',
    )
    return d


# ── DDL ───────────────────────────────────────────────────────────────────────

class TestDDL:

    def test_creer_tables_cree_les_deux_tables(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        creer_tables(conn)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert 'paquet_definitions' in tables
        assert 'paquet_requirepackage' in tables
        conn.close()

    def test_creer_tables_idempotent(self, tmp_path):
        """Relancer la création ne doit pas planter."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        creer_tables(conn)
        creer_tables(conn)  # ne doit pas lever
        conn.close()

    def test_check_constraint_sur_statut(self, db):
        """La contrainte CHECK sur statut_rendu_atome doit bloquer
        les valeurs invalides."""
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("""
                INSERT INTO paquet_definitions
                (nom, type_latex, texte_complet, fichier_source,
                 ligne_debut, statut_rendu_atome)
                VALUES ('\\foo', 'command', 'src', 'fichier.sty', 1, 'INVALIDE')
            """)


# ── inserer_definitions ───────────────────────────────────────────────────────

class TestInsererDefinitions:

    def test_insertion_simple(self, db):
        d = Definition(
            type_latex='command',
            nom='\\monMacro',
            args_spec='[1]',
            corps='#1',
            corps_fin='',
            texte_complet=r'\newcommand{\monMacro}[1]{#1}',
            fichier_source='test.sty',
            ligne_debut=1,
        )
        d.macros_appelees = {'\\seqFoo'}
        d.environnements_utilises = {'boiteTest'}

        compteurs = inserer_definitions(db, [d])
        assert compteurs['reutilise'] == 1

        row = db.execute(
            "SELECT nom, macros_appelees, environnements_utilises, statut_rendu_atome "
            "FROM paquet_definitions WHERE nom = ?", ('\\monMacro',)
        ).fetchone()
        assert row[0] == '\\monMacro'
        assert json.loads(row[1]) == ['\\seqFoo']
        assert json.loads(row[2]) == ['boiteTest']
        assert row[3] == 'reutilise'  # aucune règle → défaut

    def test_regle_reecrit_stocke_le_contenu(self, db, monkeypatch):
        """Quand une règle 'reecrit' existe, son contenu est stocké en base.

        Note : actuellement REGLES n'a aucune règle 'reecrit' (le rendu
        atomique laisse le paquet faire son travail). Pour tester cette
        branche du peuplement, on injecte une règle fictive via monkeypatch.
        """
        from services import paquet_regles_atome

        regles_modifiees = dict(paquet_regles_atome.REGLES)
        regles_modifiees['\\seqCorrige'] = (
            paquet_regles_atome.STATUT_REECRIT,
            r'\renewcommand{\seqCorrige}[1]{TEST_REMPLACEMENT}',
        )
        monkeypatch.setattr(paquet_regles_atome, 'REGLES', regles_modifiees)

        d = Definition(
            type_latex='command',
            nom='\\seqCorrige',
            args_spec='[1]',
            corps='original',
            corps_fin='',
            texte_complet=r'\newcommand{\seqCorrige}[1]{original}',
            fichier_source='seqenseigne-core.sty',
            ligne_debut=1,
        )
        inserer_definitions(db, [d])

        row = db.execute(
            "SELECT statut_rendu_atome, contenu_atome "
            "FROM paquet_definitions WHERE nom = '\\seqCorrige'"
        ).fetchone()
        assert row[0] == 'reecrit'
        assert 'TEST_REMPLACEMENT' in row[1]

    def test_regle_ignore_pas_de_contenu(self, db):
        d = Definition(
            type_latex='command',
            nom='\\seqLoadData',
            args_spec='',
            corps='...',
            corps_fin='',
            texte_complet=r'\newcommand{\seqLoadData}{...}',
            fichier_source='seqenseigne-data.sty',
            ligne_debut=1,
        )
        inserer_definitions(db, [d])

        row = db.execute(
            "SELECT statut_rendu_atome FROM paquet_definitions "
            "WHERE nom = '\\seqLoadData'"
        ).fetchone()
        assert row[0] == 'ignore'

    def test_doublon_ecrase(self, db):
        """Un nom déjà en base est écrasé par le second."""
        d1 = Definition(
            type_latex='if', nom='\\ifdocstd', args_spec='',
            corps='', corps_fin='',
            texte_complet=r'\newif\ifdocstd',
            fichier_source='core.sty', ligne_debut=10,
        )
        d2 = Definition(
            type_latex='if', nom='\\ifdocstd', args_spec='',
            corps='', corps_fin='',
            texte_complet=r'\newif\ifdocstd',
            fichier_source='theme.sty', ligne_debut=20,
        )
        inserer_definitions(db, [d1])
        compteurs = inserer_definitions(db, [d2])
        assert compteurs['doublons_ecrases'] == 1

        # Après écrasement, c'est theme.sty qui est en base
        row = db.execute(
            "SELECT fichier_source, ligne_debut FROM paquet_definitions "
            "WHERE nom = '\\ifdocstd'"
        ).fetchone()
        assert row[0] == 'theme.sty'
        assert row[1] == 20


# ── inserer_requirepackage ────────────────────────────────────────────────────

class TestInsererRequirepackage:

    def test_plusieurs_paquets(self, db):
        inserer_requirepackage(
            db, 'test.sty',
            [('tikz', ''), ('tcolorbox', 'breakable')],
        )
        rows = db.execute(
            "SELECT ordre, nom, options FROM paquet_requirepackage "
            "WHERE fichier_source = 'test.sty' ORDER BY ordre"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0] == (0, 'tikz', '')
        assert rows[1] == (1, 'tcolorbox', 'breakable')


# ── peupler : pipeline complet sur mini-paquet ───────────────────────────────

class TestPeuplerIntegration:

    def test_pipeline_complet(self, tmp_path, paquet_mini):
        db_path = tmp_path / "test.db"
        rapport = peupler(db_path, paquet_mini)

        assert rapport['ok'] is True
        # 5 fichiers, au moins une définition par fichier
        assert rapport['total_definitions'] >= 5

        conn = sqlite3.connect(str(db_path))
        try:
            noms = {row[0] for row in conn.execute(
                "SELECT nom FROM paquet_definitions"
            )}
            assert '\\seqFrac' in noms
            assert '\\seqCorrige' in noms
            assert 'seqNotion' in noms
            assert '\\seqBoiteJaune' in noms
            assert '\\seqLoadData' in noms

            # statut_rendu_atome appliqué
            statuts = dict(conn.execute(
                "SELECT nom, statut_rendu_atome FROM paquet_definitions"
            ).fetchall())
            assert statuts['\\seqFrac'] == 'reutilise'
            # seqCorrige n'est plus en 'reecrit' : le service laisse le paquet
            # faire son travail pour la mise en page livret-like.
            assert statuts['\\seqCorrige'] == 'reutilise'
            assert statuts['\\seqLoadData'] == 'ignore'
        finally:
            conn.close()

    def test_idempotence(self, tmp_path, paquet_mini):
        """Rejouer le peuplement donne le même résultat (à ifdocstd près
        qui apparaît dans plusieurs fichiers)."""
        db_path = tmp_path / "test.db"
        r1 = peupler(db_path, paquet_mini)
        r2 = peupler(db_path, paquet_mini)
        assert r1['total_definitions'] == r2['total_definitions']
        assert r1['par_statut'] == r2['par_statut']

    def test_paquet_inexistant_leve_erreur(self, tmp_path):
        db_path = tmp_path / "test.db"
        with pytest.raises(FileNotFoundError):
            peupler(db_path, tmp_path / "n_existe_pas")

    def test_fichier_manquant_leve_erreur(self, tmp_path, paquet_mini):
        """Si un fichier .sty attendu manque, erreur explicite."""
        (paquet_mini / 'seqenseigne-core.sty').unlink()
        with pytest.raises(FileNotFoundError, match='seqenseigne-core.sty'):
            peupler(tmp_path / "test.db", paquet_mini)


# ── regles_orphelines ────────────────────────────────────────────────────────

class TestReglesOrphelines:

    def test_base_vide_toutes_orphelines(self, db):
        """Base vide → toutes les règles explicites sont orphelines."""
        from services.paquet_regles_atome import REGLES
        orph = regles_orphelines(db)
        assert len(orph) == len(REGLES)

    def test_definition_presente_pas_orpheline(self, db):
        d = Definition(
            type_latex='command', nom='\\seqCorrige',
            args_spec='[1]', corps='...', corps_fin='',
            texte_complet='', fichier_source='test.sty', ligne_debut=1,
        )
        inserer_definitions(db, [d])
        orph = regles_orphelines(db)
        assert '\\seqCorrige' not in orph

    def test_mini_paquet_pas_orpheline_critique(self, tmp_path, paquet_mini):
        """Après peuplement du mini-paquet, certaines règles sont orphelines
        (normal, le mini-paquet ne contient pas toutes les macros) mais pas
        celles qui concernent les macros qu'on a peuplées."""
        db_path = tmp_path / "test.db"
        peupler(db_path, paquet_mini)
        conn = sqlite3.connect(str(db_path))
        try:
            orph = regles_orphelines(conn)
            # Les règles pour \seqCorrige et \seqLoadData ne doivent PAS être
            # orphelines car ces macros sont dans le mini-paquet
            assert '\\seqCorrige' not in orph
            assert '\\seqLoadData' not in orph
        finally:
            conn.close()
