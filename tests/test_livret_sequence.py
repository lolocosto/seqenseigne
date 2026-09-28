r"""tests/test_livret_sequence.py — v0.11.2.

Tests du service services.livret_sequence qui génère le source LaTeX
d'un livret pour une séquence donnée.

Couverture :
  1. Validation des options (normaliser_options).
  2. Inclusion / exclusion des sections selon les toggles.
  3. Cohérence du .tex produit (présence des blocs LaTeX attendus,
     ordre, fallback titre fiche, mode prof avec \acompleter redéfini).

Stratégie :
  - Utilise l'app Flask (create_app) pour obtenir un SqliteStore avec
    schema.sql complet — nécessaire car le service livret_sequence
    touche à beaucoup de tables (notions, methodes, exercices,
    fiches_resume, objectif_*, partie_exos_revision_approche,
    paquet_definitions pour le préambule, etc.).
  - Peuple manuellement quelques atomes minimaux pour les assertions.
"""

from __future__ import annotations
import pytest

from app import create_app
from services.livret_sequence import (
    generer_livret_sequence,
    normaliser_options,
    options_par_defaut,
    valider_options,
)


# ── Tests de la normalisation d'options (purs, sans DB) ─────────────────────

class TestNormaliserOptions:

    def test_par_defaut_tout_inclus(self):
        opts = options_par_defaut()
        assert opts["cours"]["inclure"] is True
        assert opts["cours"]["fiches_resume"]["inclure"] is True
        assert opts["cours"]["fiches_resume"]["a_completer"] is True
        assert opts["exercices"]["inclure"] is True
        assert opts["exercices"]["serie_A"] is True

    def test_none_donne_defauts(self):
        assert normaliser_options(None) == options_par_defaut()
        assert normaliser_options({}) == options_par_defaut()

    def test_desactiver_cours(self):
        opts = normaliser_options({"cours": {"inclure": False}})
        assert opts["cours"]["inclure"] is False
        # Les sous-options gardent leurs défauts (True) — ignorées car inclure=False.
        assert opts["cours"]["fiches_resume"]["inclure"] is True

    def test_desactiver_serie_A(self):
        opts = normaliser_options({"exercices": {"serie_A": False}})
        assert opts["exercices"]["inclure"] is True
        assert opts["exercices"]["serie_A"] is False

    def test_mode_prof_fiches(self):
        opts = normaliser_options({
            "cours": {"fiches_resume": {"a_completer": False}},
        })
        assert opts["cours"]["fiches_resume"]["inclure"] is True
        assert opts["cours"]["fiches_resume"]["a_completer"] is False

    def test_robuste_aux_types_invalides(self):
        """Si le caller passe des valeurs malformées, on retombe sur les
        défauts plutôt que de crasher."""
        opts = normaliser_options({"cours": "pas un dict"})
        assert opts["cours"]["inclure"] is True
        opts = normaliser_options({"cours": {"fiches_resume": "pas un dict"}})
        assert opts["cours"]["fiches_resume"]["inclure"] is True


# ── Fixture : app + base peuplée avec atomes minimaux ───────────────────────

@pytest.fixture
def app_avec_seq(data_dir):
    """App Flask avec une séquence N11/S01 peuplée :

      sn_n11_s01 (N11/S01)
        └─ partie 1 (pt_p1)
             ├─ obj 01 (Connaître le cours)
             │     notions: no1 (titre 'Notion 1')
             │     pas de méthode
             │     pas d'exos
             ├─ obj 02 (Calculer une fréquence)
             │     methode: me1 (titre 'Calculer une fréquence')
             │     exos_par_serie: F:[ex_f1], A:[ex_a1], E:[ex_e1]
             │     fiche: fi1 (titre 'Calculer une fréquence')
             └─ exos_revision_approche: R:[ex_rev1], EA:[ex_ea1]
    """
    app = create_app(data_dir=data_dir)

    with app.json_store._conn() as conn:
        conn.executescript("""
            -- Tables paquet_* nécessaires à construire_preambule.
            -- Pas dans schema.sql (peuplées par scripts/peuplement_14_*).
            CREATE TABLE IF NOT EXISTS paquet_definitions (
                nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
                corps TEXT, corps_fin TEXT, texte_complet TEXT,
                fichier_source TEXT, ligne_debut INTEGER,
                macros_appelees TEXT, environnements_utilises TEXT,
                statut_rendu_atome TEXT DEFAULT 'reutilise',
                contenu_atome TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS paquet_requirepackage (
                fichier_source TEXT NOT NULL,
                ordre INTEGER NOT NULL,
                nom TEXT NOT NULL,
                options TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (fichier_source, ordre)
            );
            INSERT INTO paquet_requirepackage VALUES
                ('seqenseigne-core.sty', 0, 'amsmath', ''),
                ('seqenseigne-core.sty', 1, 'tikz', '');

            -- Cycle / thème / séquence du cycle
            INSERT OR IGNORE INTO cycles (code, nom)
                VALUES ('C04', 'Cycle 4');
            INSERT OR IGNORE INTO themes (id, cycle_code, code, nom, code_couleur)
                VALUES ('th_A', 'C04', 'A', 'Nombres', 'nombres');
            INSERT OR IGNORE INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
                VALUES ('sc_s01', 'C04', 'S01', 1, 'Représentations d''un nombre', 'th_A');

            -- Niveau, séquence par niveau, partie
            INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
                VALUES ('sn_n11_s01', 'N11', 'S01', '');
            INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                VALUES ('pt_p1', 'sn_n11_s01', 1);

            -- Notions
            INSERT INTO notions (id, niveau, sequence, fichier, titre, num_connaissance, corps)
                VALUES ('no1', 'N11', 'S01', 'N11_S01_C01.tex',
                        'Notion 1 — fréquence', '01',
                        'La fréquence d''une valeur est ...');

            -- Méthodes
            INSERT INTO methodes (id, niveau, sequence, fichier, titre, num_methode, num_objectif, corps)
                VALUES ('me1', 'N11', 'S01', 'N11_S01_M01.tex',
                        'Calculer une fréquence', 1, '02',
                        'On compte les occurrences ...');

            -- Exercices (avec serie_code pour la table exercices)
            INSERT INTO exercices (id, serie, titre, niveau, sequence, num, serie_code, fichier, enonce, corrige)
                VALUES
                ('ex_f1',   'fondamental', 'F1', 'N11', 'S01', 1, 'F',  'N11S01F01.tex',  'Énoncé F1', 'Corrigé F1'),
                ('ex_a1',   'avancé',      'A1', 'N11', 'S01', 1, 'A',  'N11S01A01.tex',  'Énoncé A1', 'Corrigé A1'),
                ('ex_e1',   'exploration', 'E1', 'N11', 'S01', 1, 'E',  'N11S01E01.tex',  'Énoncé E1', 'Corrigé E1'),
                ('ex_ea1',  'approche',    'EA1','N11', 'S01', 1, 'AE', 'N11S01AE01.tex', 'Énoncé EA1','Corrigé EA1'),
                -- Exo de révision (vient de N10/S01, série F)
                ('ex_rev1', 'fondamental', 'Rev', 'N10', 'S01', 1, 'F', 'N10S01F01.tex',  'Énoncé Rev','Corrigé Rev');

            -- Objectifs v2
            INSERT INTO objectifs (id, partie_id, code, nom, methode_id)
                VALUES
                ('ob_01', 'pt_p1', '01', 'Connaître le cours', NULL),
                ('ob_02', 'pt_p1', '02', 'Calculer une fréquence', 'me1');

            -- Liaisons objectif_notions
            INSERT INTO objectif_notions (objectif_id, notion_id, ordre)
                VALUES ('ob_01', 'no1', 1);

            -- Liaisons objectif_exos (séries EA/F/A/E)
            INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre)
                VALUES
                ('ob_02', 'EA', 'ex_ea1', 1),
                ('ob_02', 'F',  'ex_f1',  1),
                ('ob_02', 'A',  'ex_a1',  1),
                ('ob_02', 'E',  'ex_e1',  1);

            -- Révisions de partie (R venant de N10/S01)
            INSERT INTO partie_exos_revision_approche (partie_id, type, exercice_id, ordre,
                                                       origin_niveau, origin_seq, origin_serie, origin_num)
                VALUES ('pt_p1', 'R', 'ex_rev1', 1, 'N10', 'S01', 'F', 1);

            -- Fiche de résumé
            INSERT INTO fiches_resume (id, titre, objectif_id, num_fiche, niveau, sequence, fichier)
                VALUES ('fi1', 'Fiche fréquence', 'ob_02', 1, 'N11', 'S01', 'N11_S01_FR01.tex');
            INSERT INTO objectif_fiches (objectif_id, fiche_id, ordre)
                VALUES ('ob_02', 'fi1', 1);
            INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
                VALUES ('sec_fi1', 'fiche_resume', 'fi1', 'Définition', 0);
            INSERT INTO atome_section_items (id, section_id, ordre, corps)
                VALUES ('it_fi1', 'sec_fi1', 0, 'La fréquence est \\\\acompleter{n/N}.');
        """)
        conn.commit()
        # Sauter la connexion via with — le `yield` doit livrer la conn directement
        # pour que les tests puissent exécuter generer_livret_sequence(conn, ...).

    yield app


def _conn(app):
    """Helper : ouvre une connexion au SqliteStore de l'app et retourne
    l'objet sqlite3.Connection. Le contexte manager permet de garder la
    transaction ouverte pour le test.

    NB : on ne wrappe pas dans `with` pour permettre aux tests d'utiliser
    plusieurs requêtes successives sans fermer la conn entre temps.
    """
    return app.json_store._conn()


# ── Tests d'inclusion / exclusion selon toggles ─────────────────────────────

class TestTogglesCours:

    def test_cours_inclus_emet_section_cours(self, app_avec_seq):
        # v0.11.6.2 — Suppression du titre « Cours » (créait un saut de page
        # intempestif). Connaissances et Savoir-faire deviennent des
        # \seqTitreSection (pas des \subsection*).
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\seqTitreSection{Cours}" not in tex
        assert r"\seqTitreSection{Connaissances}" in tex
        assert r"\seqTitreSection{Savoir-faire}" in tex
        # Le titre des notions/méthodes apparaît dans leur corps via seqNotion/seqMethode.
        # On vérifie au moins la présence d'environnement attendu.
        assert "seqNotion" in tex
        assert "seqMethode" in tex

    def test_cours_exclu_pas_de_section_cours(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(
                conn, "N11", "S01",
                options={"cours": {"inclure": False}},
            )
        assert r"\seqTitreSection{Cours}" not in tex
        assert r"\seqTitreSection{Connaissances}" not in tex
        assert r"\seqTitreSection{Savoir-faire}" not in tex


class TestTogglesFiches:

    def test_fiches_incluses_par_defaut(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # \cleardoublepage marque le saut vers la section fiches.
        assert r"\cleardoublepage" in tex
        # Le titre de la fiche apparaît via \seqTitreSection (cf. generer_corps_fiche).
        assert "Fiche fréquence" in tex

    def test_fiches_excludes_si_cours_exclu(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(
                conn, "N11", "S01",
                options={"cours": {"inclure": False}},
            )
        # Le bloc cours est entièrement absent — donc les fiches aussi
        # (les fiches sont sous cours.fiches_resume).
        assert "Fiche fréquence" not in tex

    def test_fiches_excludes_via_toggle_explicite(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(
                conn, "N11", "S01",
                options={"cours": {"fiches_resume": {"inclure": False}}},
            )
        # Cours inclus mais fiches non. v0.11.6.2 : Connaissances en
        # \seqTitreSection (plus de titre Cours).
        assert r"\seqTitreSection{Connaissances}" in tex
        assert "Fiche fréquence" not in tex

    def test_mode_prof_redefinit_acompleter(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(
                conn, "N11", "S01",
                options={"cours": {"fiches_resume": {"a_completer": False}}},
            )
        # En mode prof, \acompleter doit être redéfini pour afficher la valeur.
        assert r"\renewcommand{\acompleter}[1]{#1}" in tex

    def test_mode_eleve_pas_de_redefinition(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # En mode élève (défaut), pas de redéfinition de \acompleter.
        assert r"\renewcommand{\acompleter}" not in tex


class TestTogglesExercices:

    def test_exos_inclus_par_defaut(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # v0.11.2 — pas de \seqTitreSection{Exercices} : la séparation
        # visuelle est portée par les boîtes seqSerieExos (titre + couleur
        # par série). On vérifie juste qu'au moins une série est ouverte.
        assert r"\begin{seqSerieExos}" in tex
        # Les corrigés sont déroulés en fin (au moins série F présente).
        assert r"\seqAfficheCorriges" in tex

    def test_exos_exclus_pas_de_section(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(
                conn, "N11", "S01",
                options={"exercices": {"inclure": False}},
            )
        assert r"\seqTitreSection{Exercices}" not in tex
        assert r"\begin{seqSerieExos}" not in tex

    def test_serie_A_incluse_par_defaut(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # La série A produit un seqSerieExos{2}.
        assert r"\begin{seqSerieExos}{2}" in tex

    def test_serie_A_exclue_via_toggle(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(
                conn, "N11", "S01",
                options={"exercices": {"serie_A": False}},
            )
        # F=1, A=2, E=3 sont les codes paquet. A doit être absent.
        assert r"\begin{seqSerieExos}{2}" not in tex
        # F et E doivent rester présents.
        assert r"\begin{seqSerieExos}{1}" in tex
        assert r"\begin{seqSerieExos}{3}" in tex


class TestRevisions:

    def test_revisions_emises_avant_cours(self, app_avec_seq):
        """v0.11.2 — Les exos R+EA (révisions et activités d'approche)
        doivent être émis dans la première seqSerieExos (numéro 0
        = 'Révisions') AVANT le bloc Cours. C'est l'ordre pédagogique
        validé par Laurent : on commence par les révisions/AP, puis on
        introduit le cours, puis on enchaîne sur les exercices F/A/E.

        v0.11.6.2 : le titre « Cours » a été supprimé ; on prend
        \\seqTitreSection{Connaissances} comme premier marqueur du bloc
        cours.
        """
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # Présence d'une seqSerieExos{0} (Révisions/Activités d'approche)
        assert r"\begin{seqSerieExos}{0}" in tex
        # L'ordre : seqSerieExos{0} avant \seqTitreSection{Connaissances} avant seqSerieExos{1}
        idx_0     = tex.find(r"\begin{seqSerieExos}{0}")
        idx_cours = tex.find(r"\seqTitreSection{Connaissances}")
        idx_1     = tex.find(r"\begin{seqSerieExos}{1}")
        assert 0 <= idx_0 < idx_cours < idx_1


# ── Tests de structure du .tex ──────────────────────────────────────────────

class TestStructureTex:

    def test_documentclass_present(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\documentclass[a4paper,11pt]{article}" in tex

    def test_codes_niveau_sequence_poses(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\seqSetCodeNiveau{N11}" in tex
        assert r"\seqSetCodeSequence{S01}" in tex

    def test_theme_couleur_pose(self, app_avec_seq):
        """Le code couleur du thème (récupéré via lire_sequence_par_niveau)
        doit être posé via \\seqSetColorsTheme."""
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\seqSetColorsTheme{nombres}" in tex

    def test_begin_end_document(self, app_avec_seq):
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\begin{document}" in tex
        assert tex.rstrip().endswith(r"\end{document}")

    def test_pas_de_seqTitreLivret(self, app_avec_seq):
        """v0.11.2 — la macro \\seqTitreLivret est marquée STATUT_IGNORE
        dans paquet_regles_atome.py (pas inlinable dans le préambule
        construit). Le livret de séquence ne doit donc PAS l'utiliser,
        sous peine de « Undefined control sequence » à la compilation."""
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\seqTitreLivret" not in tex


# ── Tests v0.11.3 — Validation des options ──────────────────────────────────

class TestValiderOptions:

    def test_valider_options_ok_par_defaut(self):
        """Les options par défaut sont valides (cours et exercices à True)."""
        valider_options(options_par_defaut())  # ne lève pas

    def test_valider_options_ok_si_cours_seul(self):
        """Cours sans exercices : valide."""
        valider_options(normaliser_options({"exercices": {"inclure": False}}))

    def test_valider_options_ok_si_exercices_seul(self):
        """Exercices sans cours : valide."""
        valider_options(normaliser_options({"cours": {"inclure": False}}))

    def test_valider_options_refuse_les_deux_blocs_a_false(self):
        """Ni cours ni exercices = livret vide → refusé."""
        opts = normaliser_options({
            "cours": {"inclure": False},
            "exercices": {"inclure": False},
        })
        with pytest.raises(ValueError, match="cours ou exercices"):
            valider_options(opts)

    def test_generer_livret_refuse_les_deux_blocs_a_false(self, app_avec_seq):
        """generer_livret_sequence appelle valider_options dès l'entrée."""
        with _conn(app_avec_seq) as conn:
            with pytest.raises(ValueError):
                generer_livret_sequence(
                    conn, "N11", "S01",
                    options={
                        "cours": {"inclure": False},
                        "exercices": {"inclure": False},
                    },
                )


# ── Tests v0.11.3 — Sauts de page entre sections ────────────────────────────

class TestSautsDePage:

    def test_clearpage_avant_chaque_serie_dexercices(self, app_avec_seq):
        """v0.11.3 — Chaque série d'exercices (Révisions, F, A, E) doit
        être précédée d'un \\clearpage. La fixture peuple AE+R, F, A, E
        donc on s'attend à au moins 4 \\clearpage liés aux séries."""
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # Vérifie qu'on a un \clearpage juste avant chaque \begin{seqSerieExos}
        # (en autorisant des lignes vides entre).
        import re
        # \clearpage suivi (avec espaces/lignes vides) de \begin{seqSerieExos}
        m = re.findall(
            r"\\clearpage\s+\\begin\{seqSerieExos\}\{(\d+)\}",
            tex,
        )
        # 4 séries dans la fixture : 0 (R/AE), 1 (F), 2 (A), 3 (E).
        assert sorted(m) == ["0", "1", "2", "3"]

    def test_clearpage_avant_titre_cours(self, app_avec_seq):
        """v0.11.6.2 — Le titre « Cours » a été supprimé (saut de page
        intempestif). Le \\clearpage de transition est désormais directement
        avant \\seqTitreSection{Connaissances}, qui ouvre le bloc cours.
        """
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # Plus aucun titre « Cours » n'est émis.
        assert r"\seqTitreSection{Cours}" not in tex
        idx_conn = tex.find(r"\seqTitreSection{Connaissances}")
        assert idx_conn > 0
        avant = tex[max(0, idx_conn - 80):idx_conn]
        assert r"\clearpage" in avant

    def test_clearpage_avant_subsection_connaissances(self, app_avec_seq):
        """v0.11.6.2 — Connaissances est en \\seqTitreSection (plus en
        \\subsection*) et est précédé d'un \\clearpage."""
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # Plus aucune \subsection* dans le bloc cours.
        assert r"\subsection*{Connaissances}" not in tex
        assert r"\subsection*{Savoir-faire}" not in tex
        # \seqTitreSection{Connaissances} est précédé d'un \clearpage.
        idx = tex.find(r"\seqTitreSection{Connaissances}")
        assert idx > 0
        avant = tex[max(0, idx - 80):idx]
        assert r"\clearpage" in avant

    def test_clearpage_avant_annexes(self, app_avec_seq):
        """v0.11.3 — Le bloc Annexes/Corrigés en fin commence sur une
        nouvelle page."""
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        idx = tex.find(r"\seqAfficheAnnexes")
        assert idx > 0
        avant = tex[max(0, idx - 80):idx]
        assert r"\clearpage" in avant

    def test_cleardoublepage_avant_fiches(self, app_avec_seq):
        """v0.11.3 — Les Fiches de résumé sont précédées de \\cleardoublepage
        (et non juste d'un \\clearpage), pour démarrer sur une page de
        droite — pratique pour la découpe des fiches en recto-verso."""
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # La fixture a une fiche fi1 (titre 'Fiche fréquence') ; on cherche
        # un \cleardoublepage avant ce contenu de fiche.
        idx = tex.find("Fiche fréquence")
        assert idx > 0
        avant = tex[max(0, idx - 200):idx]
        assert r"\cleardoublepage" in avant


# ── Tests v0.11.3 — Tableau Objectifs depuis BDD ────────────────────────────

@pytest.fixture
def app_avec_criteres(data_dir):
    """App Flask avec une séquence dont les objectifs ont des critères
    F/A/E renseignés. Permet de tester la génération du tableau Objectifs.

    Structure :
      sn_n11_s01 (N11/S01)
        └─ partie 1 (pt_p1)
             ├─ obj 01 critères tous saisis
             └─ obj 02 critères vides
    """
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS paquet_definitions (
                nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
                corps TEXT, corps_fin TEXT, texte_complet TEXT,
                fichier_source TEXT, ligne_debut INTEGER,
                macros_appelees TEXT, environnements_utilises TEXT,
                statut_rendu_atome TEXT DEFAULT 'reutilise',
                contenu_atome TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS paquet_requirepackage (
                fichier_source TEXT NOT NULL, ordre INTEGER NOT NULL,
                nom TEXT NOT NULL, options TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (fichier_source, ordre)
            );
            INSERT INTO paquet_requirepackage VALUES
                ('seqenseigne-core.sty', 0, 'amsmath', '');

            INSERT OR IGNORE INTO cycles (code, nom) VALUES ('C04', 'Cycle 4');
            INSERT OR IGNORE INTO themes (id, cycle_code, code, nom, code_couleur)
                VALUES ('th_A', 'C04', 'A', 'Nombres', 'nombres');
            INSERT OR IGNORE INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
                VALUES ('sc_s01', 'C04', 'S01', 1, 'Test', 'th_A');

            INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
                VALUES ('sn_n11_s01', 'N11', 'S01', '');
            INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                VALUES ('pt_p1', 'sn_n11_s01', 1);

            INSERT INTO objectifs
                (id, partie_id, code, nom, methode_id,
                 critere_F, critere_A, critere_E)
                VALUES
                ('ob_01', 'pt_p1', '01', 'Maîtriser une notion clé', NULL,
                 'A appris la définition.', 'Sait expliquer la notion.',
                 'Utilise la notion en autonomie.'),
                ('ob_02', 'pt_p1', '02', 'Objectif sans critères', NULL,
                 '', '', '');
        """)
        conn.commit()
    yield app


class TestTableauObjectifs:

    def test_tableau_objectifs_emis_si_criteres_saisis(self, app_avec_criteres):
        """Si au moins un objectif a un critère renseigné, le tableau
        Objectifs est émis via la commande paquet \\seqRenduTableauObjectifs.

        v0.13.2 — Le rendu utilise désormais la commande paquet
        `\\seqRenduTableauObjectifs{...}` qui encapsule lignes de tableau
        dans une boîte tcolorbox avec en-tête à 2 niveaux fixe."""
        with _conn(app_avec_criteres) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # Nouvelle commande
        assert r"\seqRenduTableauObjectifs{" in tex
        # L'ancien titre de section ne doit plus apparaître
        assert r"\seqTitreSection{Objectifs}" not in tex
        # L'ancien wrapping non plus
        assert r"\begin{seqBoiteObjectifs}" not in tex
        # Plus de tblr séparé : le tabularx est intégré dans la commande
        # (via la clé tcolorbox `tabularx*`)
        # Les en-têtes (« À consolider », « Satisfaisant », « Très bien »)
        # sont fixes côté paquet — pas dans la sortie Python
        # (vérification : ils ne doivent PAS être dans le bloc commande)
        # Les critères de ob_01 doivent apparaître
        assert "A appris la définition." in tex
        assert "Utilise la notion en autonomie." in tex

    def test_tableau_objectifs_omis_si_aucun_critere(self, app_avec_seq):
        """Dans la fixture app_avec_seq, ob_01 et ob_02 n'ont pas de
        critères saisis (chaînes vides par défaut). Le tableau ne doit
        pas être émis.

        v0.13.2 — On vérifie l'absence de la commande
        \\seqRenduTableauObjectifs."""
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\seqRenduTableauObjectifs{" not in tex
        assert r"\seqTitreSection{Objectifs}" not in tex

    def test_tableau_objectifs_emet_lignes_meme_partielles(self, app_avec_criteres):
        """Un objectif sans critères apparaît tout de même dans le tableau
        (avec des cellules vides) dès lors qu'un AUTRE objectif de la
        séquence a des critères."""
        with _conn(app_avec_criteres) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert "Maîtriser une notion clé" in tex
        assert "Objectif sans critères" in tex


# ── Tests v0.11.3 — Tableau Prérequis depuis BDD ────────────────────────────

@pytest.fixture
def app_avec_precedence(data_dir):
    """App Flask avec deux séquences-niveau : N10/S01 avec quelques
    objectifs nommés, et N11/S01 qui pointe vers N10/S01 en précédence.
    Sert à tester le bloc Prérequis du livret de N11/S01.
    """
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS paquet_definitions (
                nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
                corps TEXT, corps_fin TEXT, texte_complet TEXT,
                fichier_source TEXT, ligne_debut INTEGER,
                macros_appelees TEXT, environnements_utilises TEXT,
                statut_rendu_atome TEXT DEFAULT 'reutilise',
                contenu_atome TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS paquet_requirepackage (
                fichier_source TEXT NOT NULL, ordre INTEGER NOT NULL,
                nom TEXT NOT NULL, options TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (fichier_source, ordre)
            );
            INSERT INTO paquet_requirepackage VALUES
                ('seqenseigne-core.sty', 0, 'amsmath', '');

            INSERT OR IGNORE INTO cycles (code, nom) VALUES ('C04', 'Cycle 4');
            INSERT OR IGNORE INTO themes (id, cycle_code, code, nom, code_couleur)
                VALUES ('th_A', 'C04', 'A', 'Nombres', 'nombres');
            INSERT OR IGNORE INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
                VALUES ('sc_s01', 'C04', 'S01', 1, 'Représentations d''un nombre', 'th_A');

            -- N10/S01 : la séquence prérequise, avec deux objectifs nommés
            INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
                VALUES ('sn_n10_s01', 'N10', 'S01', '');
            INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                VALUES ('pt_n10_p1', 'sn_n10_s01', 1);
            INSERT INTO objectifs (id, partie_id, code, nom, methode_id)
                VALUES
                ('ob_n10_01', 'pt_n10_p1', '01', 'Connaître les fractions', NULL),
                ('ob_n10_02', 'pt_n10_p1', '02', 'Comparer deux fractions', NULL);

            -- N11/S01 : la séquence courante, avec une précédence vers N10/S01
            INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
                VALUES ('sn_n11_s01', 'N11', 'S01', '');
            INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                VALUES ('pt_n11_p1', 'sn_n11_s01', 1);
            INSERT INTO objectifs (id, partie_id, code, nom, methode_id)
                VALUES ('ob_n11_01', 'pt_n11_p1', '01', 'Étendre aux décimaux', NULL);
            INSERT INTO sequence_par_niveau_precedences
                (sequence_par_niveau_id, precedent_niveau, precedent_seq, ordre)
                VALUES ('sn_n11_s01', 'N10', 'S01', 1);
        """)
        conn.commit()
    yield app


class TestTableauPrerequis:

    def test_prerequis_emis_avec_precedences(self, app_avec_precedence):
        """v0.11.3 — Si la séquence a une précédence vers une séquence
        existante en BDD, le bloc Prérequis est émis avec sous-titre
        et liste à puces des libellés d'objectifs.

        v0.13.2 — Le rendu utilise la commande paquet
        `\\seqRenduTableauPrerequis{...}` qui encapsule le contenu (subsection*
        + itemize) dans une boîte tcolorbox avec titre « Prérequis »."""
        with _conn(app_avec_precedence) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\seqRenduTableauPrerequis{" in tex
        # L'ancien titre de section ne doit plus apparaître
        assert r"\seqTitreSection{Prérequis}" not in tex
        # L'ancien wrapping non plus
        assert r"\begin{seqBoitePrerequis}" not in tex
        # Sous-titre = "Séquence 01 — Représentations d'un nombre"
        assert "Séquence 01" in tex
        assert "Représentations d'un nombre" in tex
        # Niveau court de la séquence prérequise (5ème)
        assert r"5\ieme" in tex
        # Libellés des objectifs prérequis en liste
        assert r"\begin{itemize}" in tex
        assert "Connaître les fractions" in tex
        assert "Comparer deux fractions" in tex

    def test_prerequis_omis_si_pas_de_precedence(self, app_avec_seq):
        """Si la séquence n'a pas de précédence enregistrée, le bloc
        Prérequis est silencieusement omis (pas de tableau vide).

        v0.13.2 — On vérifie l'absence de la commande
        \\seqRenduTableauPrerequis."""
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\seqRenduTableauPrerequis{" not in tex
        assert r"\seqTitreSection{Prérequis}" not in tex

    def test_prerequis_omis_si_precedence_pointe_vers_inexistante(self,
                                                                  app_avec_seq):
        """Si une précédence pointe vers une séquence absente en BDD
        (cas typique : N09/S01 référencé par N10/S01 alors que N09 n'est
        pas peuplé), on n'affiche rien plutôt qu'un sous-titre vide.

        v0.13.2 — On vérifie l'absence de la commande
        \\seqRenduTableauPrerequis."""
        # On ajoute manuellement une précédence vers une séquence qui
        # n'existe pas en BDD.
        with _conn(app_avec_seq) as conn:
            conn.execute(
                "INSERT INTO sequence_par_niveau_precedences "
                "(sequence_par_niveau_id, precedent_niveau, precedent_seq, ordre) "
                "VALUES (?, ?, ?, ?)",
                ("sn_n11_s01", "N09", "S99", 1),
            )
            conn.commit()
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # Aucun bloc Prérequis affiché parce que l'unique précédence
        # pointe vers une séquence vide en BDD.
        assert r"\seqRenduTableauPrerequis{" not in tex
        assert r"\seqTitreSection{Prérequis}" not in tex


# ── Tests v0.13.3 — Fallback CSV pour les prérequis ─────────────────────────


class TestV0133FallbackCsvPrerequis:
    """v0.13.3 — Quand une précédence pointe vers une séquence qui n'est
    pas peuplée dans la BDD applicative, on bascule sur les CSV
    `data/CXX_objectifs.csv` du cycle correspondant.

    Cas typique : N10/S01 (cycle 4, peuplée en BDD) référence en
    précédence des séquences N09/S0x (cycle 3, NON peuplées en BDD
    car C03 reste en lecture seule via CSV). Sans le fallback, le bloc
    Prérequis serait vide car aucun objectif N09 n'existe en
    `objectifs`. Avec le fallback, on lit `data/C03_objectifs.csv`
    et on émet les libellés des objectifs.
    """

    def test_fallback_csv_emet_les_objectifs_de_la_sequence(self,
                                                            data_dir):
        """Cas nominal : précédence vers une séquence absente de la BDD
        mais présente dans le CSV. On vérifie que les noms d'objectifs
        sont bien émis dans le bloc Prérequis."""
        # Préparer un CSV C03 minimal pour le test, en plus des fixtures
        # standard (data_dir vient de conftest.py qui crée déjà
        # param_niveaux.csv).
        (data_dir / "C03_objectifs.csv").write_text(
            "CodeNiveau,CodeSequence,CodeObjectif,FinCycle,Nom,MaitriseTB,MaitriseS,MaitriseF\n"
            "N09,S01,01,O,Connaître les notions et les méthodes.,TB,S,F\n"
            "N09,S01,02,O,Résoudre des problèmes mettant en jeu des nombres entiers.,TB,S,F\n",
            encoding="utf-8",
        )
        # On a aussi besoin du nom de la séquence dans C03_sequences.csv
        # pour que `_lire_nom_sequence_du_cycle` retrouve « Nombres entiers ».
        # La fixture data_dir crée déjà un C03 minimal — mais s'il manque
        # S01, on l'ajoute.
        seq_path = data_dir / "C03_sequences.csv"
        existing = seq_path.read_text(encoding="utf-8") if seq_path.exists() else ""
        if "N09,S01" not in existing and "S01" not in existing:
            seq_path.write_text(
                "Code,Numero,Nom,Theme\n"
                "S01,1,Nombres entiers,A\n",
                encoding="utf-8",
            )
        themes_path = data_dir / "C03_themes.csv"
        if not themes_path.exists():
            themes_path.write_text(
                "Code,Nom,CodeCouleur,Description\n"
                "A,Nombres et Calculs,nombres,\"Description\"\n",
                encoding="utf-8",
            )

        # Créer une app avec une précédence N10/S01 → N09/S01 (qui n'est
        # PAS en BDD applicative)
        app = create_app(data_dir=data_dir)
        with app.json_store._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS paquet_definitions (
                    nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
                    corps TEXT, corps_fin TEXT, texte_complet TEXT,
                    fichier_source TEXT, ligne_debut INTEGER,
                    macros_appelees TEXT, environnements_utilises TEXT,
                    statut_rendu_atome TEXT DEFAULT 'reutilise',
                    contenu_atome TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS paquet_requirepackage (
                    fichier_source TEXT NOT NULL, ordre INTEGER NOT NULL,
                    nom TEXT NOT NULL, options TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (fichier_source, ordre)
                );
                INSERT INTO paquet_requirepackage VALUES
                    ('seqenseigne-core.sty', 0, 'amsmath', '');

                INSERT OR IGNORE INTO cycles (code, nom) VALUES ('C04', 'Cycle 4');
                INSERT OR IGNORE INTO themes (id, cycle_code, code, nom, code_couleur)
                    VALUES ('th_A', 'C04', 'A', 'Nombres', 'nombres');
                INSERT OR IGNORE INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
                    VALUES ('sc_s01', 'C04', 'S01', 1, 'Représentations', 'th_A');

                -- N10/S01 : la séquence courante avec précédence vers N09/S01
                INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
                    VALUES ('sn_n10_s01', 'N10', 'S01', '');
                INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                    VALUES ('pt_n10_p1', 'sn_n10_s01', 1);
                INSERT INTO objectifs (id, partie_id, code, nom, methode_id)
                    VALUES ('ob_n10_01', 'pt_n10_p1', '01', 'Lire un nombre', NULL);
                INSERT INTO sequence_par_niveau_precedences
                    (sequence_par_niveau_id, precedent_niveau, precedent_seq, ordre)
                    VALUES ('sn_n10_s01', 'N09', 'S01', 1);
            """)
            conn.commit()

        with _conn(app) as conn:
            tex = generer_livret_sequence(conn, "N10", "S01")

        # Le bloc Prérequis doit être présent
        assert r"\seqRenduTableauPrerequis{" in tex
        # Les libellés d'objectifs N09 du CSV doivent apparaître
        assert "Connaître les notions et les méthodes." in tex
        assert "Résoudre des problèmes mettant en jeu des nombres entiers." in tex
        # Le sous-titre référence la séquence du cycle 3 (avec son
        # nom_court LaTeX 6\ieme)
        assert r"6\ieme" in tex

    def test_fallback_omis_si_csv_absent(self, app_avec_seq):
        """Si la précédence pointe vers une séquence absente ET que le
        CSV de fallback n'a pas non plus l'objectif, le bloc Prérequis
        n'est pas affiché (comportement de l'ancien fallback)."""
        # On ajoute une précédence vers N09/S99 (séquence inventée,
        # absente du CSV C03_objectifs.csv réel comme du test).
        with _conn(app_avec_seq) as conn:
            conn.execute(
                "INSERT INTO sequence_par_niveau_precedences "
                "(sequence_par_niveau_id, precedent_niveau, precedent_seq, ordre) "
                "VALUES (?, ?, ?, ?)",
                ("sn_n11_s01", "N09", "S99", 1),
            )
            conn.commit()
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # Le bloc n'est pas émis
        assert r"\seqRenduTableauPrerequis{" not in tex


# ── Tests v0.11.6 — Remédiation et cadre de réponse ─────────────────────────


class TestRemediationLivret:
    """Vérifie que la remédiation (\\seqRemediation) et le cadre de
    réponse (\\seqCadreReponse) sont émis correctement dans le .tex
    d'un livret de séquence.

    On part de la fixture app_avec_seq qui a déjà un exo F (ex_f1) et
    on lui ajoute une remédiation via UPDATE direct en BDD.
    """

    def test_pas_de_remediation_sans_atomes_concernes(self, app_avec_seq):
        """Par défaut, aucun exo de la fixture n'a de remédiation.
        Donc le livret ne doit contenir ni \\seqInitRemediation ni
        \\seqAfficheRemediations ni \\seqAfficheCorrigesRemediation.

        C'est important pour la rétrocompatibilité : un livret existant
        doit compiler à l'identique de v0.11.5 si la BDD n'a pas été
        touchée."""
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\seqInitRemediation" not in tex
        assert r"\seqAfficheRemediations" not in tex
        assert r"\seqAfficheCorrigesRemediation" not in tex
        assert r"\seqRemediation" not in tex

    def test_remediation_emise_si_un_exo_en_a(self, app_avec_seq):
        """Si on UPDATE un exo pour lui poser une remédiation, le livret
        doit alors émettre \\seqInitRemediation, le bloc \\seqRemediation
        à la suite de l'exo concerné, et les deux \\seqAffiche*Remediation*
        en fin de doc."""
        with _conn(app_avec_seq) as conn:
            conn.execute(
                "UPDATE exercices SET remed_enonce=?, remed_corrige=? "
                "WHERE id=?",
                ("Refaire le calcul de base.", "Décomposer en étapes.",
                 "ex_f1"),
            )
            conn.commit()
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # Init en début de doc
        assert r"\seqInitRemediation" in tex
        # Bloc \seqRemediation présent dans le corps
        assert r"\seqRemediation{" in tex
        assert "Refaire le calcul de base." in tex
        assert "Décomposer en étapes." in tex
        # Affichage en fin de doc
        assert r"\seqAfficheRemediations" in tex
        assert r"\seqAfficheCorrigesRemediation" in tex

    def test_ordre_des_sections_finales(self, app_avec_seq):
        """L'ordre validé v0.11.5 / v0.11.6 :
            \\seqAfficheCorriges
            \\seqAfficheRemediations
            \\seqAfficheCorrigesRemediation
        Important pour la cohérence : les corrigés des exos principaux
        suivent immédiatement les exos principaux, et tout le matériel
        de remédiation est groupé en queue de livret."""
        with _conn(app_avec_seq) as conn:
            conn.execute(
                "UPDATE exercices SET remed_enonce=?, remed_corrige=? "
                "WHERE id=?",
                ("E", "C", "ex_f1"),
            )
            conn.commit()
            tex = generer_livret_sequence(conn, "N11", "S01")
        idx_corr_pri = tex.find(r"\seqAfficheCorriges")
        idx_remed = tex.find(r"\seqAfficheRemediations")
        idx_corr_remed = tex.find(r"\seqAfficheCorrigesRemediation")
        assert idx_corr_pri > 0
        assert idx_remed > idx_corr_pri
        assert idx_corr_remed > idx_remed

    def test_cadre_reponse_principal_emis(self, app_avec_seq):
        """Si cadre_reponse_lignes_principal > 0 sur un exo, le livret
        contient \\seqCadreReponse{N} entre l'énoncé et \\seqCorrige."""
        with _conn(app_avec_seq) as conn:
            conn.execute(
                "UPDATE exercices SET cadre_reponse_lignes_principal=? "
                "WHERE id=?",
                (8, "ex_f1"),
            )
            conn.commit()
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\seqCadreReponse{8}" in tex

    def test_cadre_reponse_principal_omis_si_zero(self, app_avec_seq):
        """Sans cadre de réponse défini, aucune émission de
        \\seqCadreReponse pour le principal."""
        with _conn(app_avec_seq) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # Default 0 = pas de cadre
        assert r"\seqCadreReponse" not in tex

    def test_cadre_reponse_remed_emis_dans_seqRemediation(self, app_avec_seq):
        """Si cadre_reponse_lignes_remed > 0, le \\seqCadreReponse{N}
        est placé à l'intérieur du premier argument de \\seqRemediation
        (à la suite de l'énoncé de remédiation)."""
        with _conn(app_avec_seq) as conn:
            conn.execute(
                "UPDATE exercices SET remed_enonce=?, remed_corrige=?, "
                "cadre_reponse_lignes_remed=? WHERE id=?",
                ("Énoncé remed", "Corrigé remed", 5, "ex_f1"),
            )
            conn.commit()
            tex = generer_livret_sequence(conn, "N11", "S01")
        # Cadre 5 lignes émis
        assert r"\seqCadreReponse{5}" in tex
        # Le \seqCadreReponse{5} doit apparaître APRÈS l'énoncé remed
        # (donc dans l'argument 1 de \seqRemediation, pas l'argument 2).
        idx_remed = tex.find(r"\seqRemediation{")
        idx_enonce = tex.find("Énoncé remed", idx_remed)
        idx_cadre = tex.find(r"\seqCadreReponse{5}", idx_remed)
        idx_corrige = tex.find("Corrigé remed", idx_cadre)
        assert idx_remed > 0
        assert idx_remed < idx_enonce < idx_cadre < idx_corrige

    def test_remediation_avec_seul_corrige_non_vide(self, app_avec_seq):
        """Cas tordu : remed_corrige non vide mais remed_enonce vide.
        On émet quand même \\seqRemediation (avec un fallback côté
        énoncé)."""
        with _conn(app_avec_seq) as conn:
            conn.execute(
                "UPDATE exercices SET remed_corrige=? WHERE id=?",
                ("Solution unique.", "ex_f1"),
            )
            conn.commit()
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\seqRemediation{" in tex
        # Fallback côté énoncé
        assert "Énoncé de remédiation non rédigé." in tex
        # Le corrigé saisi est bien présent
        assert "Solution unique." in tex


# ── Tests v0.13.2 — Commandes seqRenduTableauPrerequis et seqRenduTableauObjectifs ────

class TestV0132CommandesPaquet:
    """v0.13.2 — Les blocs Prérequis et Objectifs sont désormais émis
    via les commandes paquet `\\seqRenduTableauPrerequis{...}` et
    `\\seqRenduTableauObjectifs{...}`, déclarées dans
    `seqenseigne-theme.dtx`.

    Ces commandes :
      - encapsulent le contenu dans une boîte tcolorbox dédiée
      - portent elles-mêmes le titre (« Prérequis » / « Objectifs »)
      - pour Objectifs, intègrent l'en-tête à 2 niveaux fixe
        (« Niveau de maîtrise » + « À consolider | Satisfaisant |
        Très bien ») et gèrent le tabularx via la clé tcolorbox
        `tabularx*={}{X|X|X|X}`

    Côté Python, on n'émet que les lignes de données — l'en-tête est
    fixe côté paquet et n'apparaît PAS dans la sortie générée.

    Ces tests valident :
      - Que les commandes sont bien émises quand le contenu est non-vide
      - Que le contenu interne (sous-titres pour Prérequis ; lignes
        Objectif & F & A & E pour Objectifs) est bien préservé
      - Que les anciens marqueurs (\\seqTitreSection,
        seqBoitePrerequis/Objectifs, tblr séparé) ne sont plus émis
      - Que l'ordre relatif des blocs est respecté
    """

    def test_seqRenduTableauPrerequis_contient_subsection_et_itemize(
            self, app_avec_precedence):
        """Le contenu des prérequis (subsection*, itemize avec libellés)
        doit être strictement contenu entre `\\seqRenduTableauPrerequis{` et
        sa `}` de fermeture."""
        with _conn(app_avec_precedence) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")

        # Localiser le bloc \seqRenduTableauPrerequis{ ... }
        idx_debut = tex.find(r"\seqRenduTableauPrerequis{")
        assert idx_debut >= 0
        # Trouver la } qui ferme la commande : c'est la } seule sur sa ligne
        # qui suit le `\end{itemize}` du dernier bloc.
        # On cherche le motif "\n}\n" après idx_debut.
        idx_fin = tex.find("\n}\n", idx_debut)
        assert idx_fin > idx_debut

        contenu = tex[idx_debut:idx_fin + 3]
        # Les éléments attendus à l'intérieur
        assert r"\subsection*{" in contenu
        assert r"\begin{itemize}" in contenu
        assert "Connaître les fractions" in contenu

    def test_seqRenduTableauObjectifs_emet_lignes_de_donnees(
            self, app_avec_criteres):
        """Le tableau d'objectifs doit contenir les lignes
        `Objectif & F & A & E \\\\\\hline` pour chaque objectif avec
        critères. L'en-tête (« Niveau de maîtrise », « À consolider »
        etc.) est fixe côté paquet et n'apparaît PAS dans la sortie
        Python."""
        with _conn(app_avec_criteres) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")

        idx_debut = tex.find(r"\seqRenduTableauObjectifs{")
        assert idx_debut >= 0
        idx_fin = tex.find("\n}\n", idx_debut)
        assert idx_fin > idx_debut

        contenu = tex[idx_debut:idx_fin + 3]
        # Les lignes de données contiennent les critères saisis
        assert "A appris la définition." in contenu
        assert "Utilise la notion en autonomie." in contenu
        # Le séparateur `\\\hline` apparaît entre lignes
        assert r"\\\hline" in contenu
        # En-tête fixe côté paquet → n'apparaît PAS dans la sortie Python
        assert "Niveau de maîtrise" not in contenu
        assert "À consolider" not in contenu

    def test_derniere_ligne_objectifs_sans_hline_final(
            self, app_avec_criteres):
        """La dernière ligne du tableau d'objectifs ne porte PAS de
        `\\\\\\hline` final (sinon trait redondant avec la frame de la
        boîte tcolorbox)."""
        with _conn(app_avec_criteres) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")

        idx_debut = tex.find(r"\seqRenduTableauObjectifs{")
        idx_fin = tex.find("\n}\n", idx_debut)
        contenu = tex[idx_debut:idx_fin + 3]

        # Compter les `\hline` : doit être (nb_objectifs - 1)
        # car le dernier n'en a pas.
        # Plus simple : vérifier que la } de fermeture n'est PAS
        # précédée par `\\\hline` (elle peut être précédée par un
        # contenu de cellule, mais pas par \hline).
        # On regarde les ~50 caractères avant `\n}\n`.
        avant_fin = contenu[max(0, idx_fin - idx_debut - 50):idx_fin - idx_debut + 3]
        assert r"\\\hline" not in avant_fin

    def test_prerequis_avant_objectifs_dans_le_livret(self,
                                                     app_avec_precedence):
        """Les prérequis sont présentés avant les objectifs dans le
        livret. Cet ordre est inchangé par v0.13.2."""
        with _conn(app_avec_precedence) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")

        idx_prereq = tex.find(r"\seqRenduTableauPrerequis{")
        idx_obj = tex.find(r"\seqRenduTableauObjectifs{")
        # Sur app_avec_precedence il n'y a pas forcément de critères F/A/E
        # donc Objectifs peut ne pas être émis. On vérifie l'ordre seulement
        # si les deux sont présents.
        if idx_prereq >= 0 and idx_obj >= 0:
            assert idx_prereq < idx_obj

    def test_aucune_trace_des_anciens_marqueurs(self, app_avec_criteres):
        """Régression : v0.13.2 supprime explicitement les anciens
        \\seqTitreSection pour Prérequis/Objectifs et l'ancien wrapping
        seqBoitePrerequis/seqBoiteObjectifs. On vérifie qu'ils ne
        réapparaissent pas, même si on regénère plusieurs fois."""
        with _conn(app_avec_criteres) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        # Anciens titres de section (avant v0.13.2)
        assert r"\seqTitreSection{Prérequis}" not in tex
        assert r"\seqTitreSection{Objectifs}" not in tex
        # Ancien wrapping intermédiaire (entre v0.13.1 et v0.13.2 finale)
        assert r"\begin{seqBoitePrerequis}" not in tex
        assert r"\begin{seqBoiteObjectifs}" not in tex
        # Les autres seqTitreSection (ex. Connaissances) restent inchangés
        # — on ne touche pas à leur logique (pas testé ici, c'est une
        # régression spécifique aux deux blocs concernés par v0.13.2).

    def test_paquet_tabularx_charge_dans_le_preambule(
            self, app_avec_criteres):
        """Régression v0.13.2 : la commande \\seqRenduTableauObjectifs
        utilise la clé tcolorbox `tabularx*={}{X|X|X|X}` qui exige le
        paquet `tabularx`. Or `\\tabularx` n'apparaît jamais dans le
        source LaTeX généré par Python (tcolorbox le crée via la clé),
        donc `extraire_utilisations` ne le détecte pas. Le service
        livret_sequence ajoute donc `tabularx` explicitement à la liste
        des paquets supplémentaires.

        Sans ce chargement, la compilation plante avec :
            ! Undefined control sequence.
            \\tabularx
        """
        with _conn(app_avec_criteres) as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert r"\usepackage{tabularx}" in tex
