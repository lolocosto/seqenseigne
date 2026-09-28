"""tests/test_v0_13_5_3_render_evaluation.py — v0.13.5.3.

Tests du générateur .tex des évaluations (services/render_evaluation.py)
+ routes rendu-tex et rendu-pdf + correction des résidus v25 dans
api_exos_disponibles et calculer_couverture.

Structure :
- TestHelpersRender : helpers internes (romain, label objectif, barème exo/langue)
- TestSectionTitre : section \\seqTitreEval
- TestSectionBareme : section seqEvalBareme (modes + item langue)
- TestSectionObjectifs : section seqEvalObjectifs
- TestSectionExo : section seqEvalExercice
- TestGenerationComplete : .tex complet avec préambule
- TestRoutesRendu : routes /api/evaluations/<id>/rendu-tex et /rendu-pdf
- TestResidusV25 : api_exos_disponibles et calculer_couverture enrichis
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

# Schéma minimal pour tester en isolation le générateur et les services :
# inclut exercices avec tous les champs métier, evaluations, et les tables
# de liaison.

_SCHEMA = """
CREATE TABLE exercices (
    id            TEXT PRIMARY KEY,
    serie         TEXT NOT NULL DEFAULT '',
    titre           TEXT NOT NULL DEFAULT '',
    enonce        TEXT NOT NULL DEFAULT '',
    corrige       TEXT NOT NULL DEFAULT '',
    variables     TEXT NOT NULL DEFAULT '',
    niveau        TEXT NOT NULL DEFAULT '',
    sequence      TEXT NOT NULL DEFAULT '',
    num           INTEGER,
    serie_code    TEXT NOT NULL DEFAULT '',
    type_format   TEXT NOT NULL DEFAULT 'standard',
    etat_code     TEXT NOT NULL DEFAULT 'en_cours',
    fichier       TEXT NOT NULL DEFAULT '',
    remed_enonce  TEXT NOT NULL DEFAULT '',
    remed_corrige TEXT NOT NULL DEFAULT '',
    cadre_reponse_lignes_principal INTEGER NOT NULL DEFAULT 0,
    cadre_reponse_lignes_remed     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE evaluations (
    id                          TEXT PRIMARY KEY,
    niveau                      TEXT NOT NULL,
    numero                      INTEGER NOT NULL,
    ordre                       INTEGER NOT NULL DEFAULT 1,
    titre                       TEXT NOT NULL DEFAULT '',
    mode_notation               TEXT NOT NULL DEFAULT 'note',
    afficher_bareme_dans_exos   INTEGER NOT NULL DEFAULT 1,
    item_langue_francaise       TEXT,
    etat_code                   TEXT NOT NULL DEFAULT 'en_cours',
    mtime                       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE evaluation_exercices (
    evaluation_id        TEXT NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    exercice_id          TEXT NOT NULL REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre                INTEGER NOT NULL DEFAULT 1,
    bareme_points        REAL,
    bareme_qcm_ok        REAL,
    bareme_qcm_partiel   REAL,
    bareme_qcm_ko        REAL,
    PRIMARY KEY (evaluation_id, exercice_id)
);
CREATE TABLE evaluation_objectifs (
    evaluation_id TEXT NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    objectif_id   TEXT NOT NULL,
    PRIMARY KEY (evaluation_id, objectif_id)
);
CREATE TABLE sequences_par_niveau (
    id            TEXT PRIMARY KEY,
    niveau        TEXT NOT NULL,
    sequence_code TEXT NOT NULL,
    UNIQUE (niveau, sequence_code)
);
CREATE TABLE sequence_parties (
    id                     TEXT PRIMARY KEY,
    sequence_par_niveau_id TEXT NOT NULL REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    numero                 INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE objectifs (
    id         TEXT PRIMARY KEY,
    partie_id  TEXT NOT NULL REFERENCES sequence_parties(id) ON DELETE CASCADE,
    code       TEXT NOT NULL,
    nom        TEXT NOT NULL DEFAULT '',
    methode_id TEXT,
    critere_F  TEXT NOT NULL DEFAULT '',
    critere_A  TEXT NOT NULL DEFAULT '',
    critere_E  TEXT NOT NULL DEFAULT '',
    fin_cycle  TEXT NOT NULL DEFAULT 'N',
    nb_seances REAL NOT NULL DEFAULT 0
);
-- v0.14.7 — La 2e table `objectifs` v1 (CSV-getter pour
-- resoudre_macros_csv) a été supprimée : depuis v0.14.6.b.1, la
-- macro lit la table `objectifs` (anciennement `objectifs_v2`).
CREATE TABLE sequences (
    niveau   TEXT NOT NULL,
    sequence TEXT NOT NULL,
    nom      TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (niveau, sequence)
);
CREATE TABLE objectif_exos (
    objectif_id TEXT NOT NULL,
    serie       TEXT NOT NULL DEFAULT 'F',
    exercice_id TEXT NOT NULL,
    ordre       INTEGER NOT NULL DEFAULT 1,
    origin_niveau TEXT NOT NULL DEFAULT '',
    origin_seq    TEXT NOT NULL DEFAULT '',
    origin_serie  TEXT NOT NULL DEFAULT '',
    origin_num    INTEGER,
    PRIMARY KEY (objectif_id, serie, exercice_id)
);
-- Tables nécessaires à construire_preambule (fermeture transitive).
-- Volontairement laissées vides : la fermeture ne trouvera rien à
-- ajouter, le préambule contiendra juste les paquets externes du noyau.
-- Suffisant pour vérifier la STRUCTURE du .tex généré.
CREATE TABLE paquet_definitions (
    nom              TEXT PRIMARY KEY,
    type_latex       TEXT,
    args_spec        TEXT,
    corps            TEXT,
    corps_fin        TEXT,
    texte_complet    TEXT,
    fichier_source   TEXT,
    ligne_debut      INTEGER,
    macros_appelees  TEXT,
    environnements_utilises TEXT,
    statut_rendu_atome TEXT,
    contenu_atome    TEXT
);
CREATE TABLE paquet_requirepackage (
    fichier_source TEXT NOT NULL,
    ordre          INTEGER NOT NULL,
    nom            TEXT NOT NULL,
    options        TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (fichier_source, ordre)
);
"""


@pytest.fixture
def conn(tmp_path):
    """BDD vide avec le schéma. Le test peuple ce qu'il lui faut."""
    db = tmp_path / "test.db"
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


@pytest.fixture
def conn_eval_simple(conn):
    """BDD pré-peuplée avec une éval N10/S01 contenant 2 exos standards et
    3 objectifs. Cas le plus courant. Pas d'item langue française."""
    # Pour les INSERT d'exos avec du contenu LaTeX, on utilise des
    # paramètres SQL (?) plutôt que des chaînes inline, pour éviter
    # tout problème d'échappement de backslash.
    conn.execute(
        "INSERT INTO exercices (id, serie, titre, enonce, corrige, niveau, "
        "sequence, num, serie_code, type_format) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('ex_f01', 'fondamental', 'Calcul de proportions',
         r'Calculer $\frac{1}{2}$.', 'Réponse : 0,5',
         'N10', 'S01', 1, 'F', 'standard')
    )
    conn.execute(
        "INSERT INTO exercices (id, serie, titre, enonce, corrige, niveau, "
        "sequence, num, serie_code, type_format) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('ex_a01', 'avancé', 'Thalès',
         'Soit ABC un triangle...', '',
         'N10', 'S01', 1, 'A', 'standard')
    )
    conn.execute(
        "INSERT INTO evaluations (id, niveau, numero, ordre, titre, "
        "mode_notation) VALUES ('ev1', 'N10', 1, 1, 'Bilan T1', 'note')"
    )
    conn.execute(
        "INSERT INTO evaluation_exercices (evaluation_id, exercice_id, "
        "ordre, bareme_points) VALUES ('ev1', 'ex_f01', 1, 4.0)"
    )
    conn.execute(
        "INSERT INTO evaluation_exercices (evaluation_id, exercice_id, "
        "ordre, bareme_points) VALUES ('ev1', 'ex_a01', 2, 6.0)"
    )
    # Objectifs : la liaison passe par sequences_par_niveau / sequence_parties
    conn.execute(
        "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
        "VALUES ('spn1', 'N10', 'S01')"
    )
    conn.execute(
        "INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
        "VALUES ('sp1', 'spn1', 1)"
    )
    conn.execute(
        "INSERT INTO objectifs (id, partie_id, code, nom) VALUES (?, ?, ?, ?)",
        ('o02', 'sp1', '02', "Passer d'écriture décimale à fractionnaire.")
    )
    conn.execute(
        "INSERT INTO objectifs (id, partie_id, code, nom) "
        "VALUES ('o04', 'sp1', '04', 'Calculer un PGCD.')"
    )
    conn.execute(
        "INSERT INTO objectifs (id, partie_id, code, nom) "
        "VALUES ('o07', 'sp1', '07', 'Utiliser Thalès.')"
    )
    conn.execute(
        "INSERT INTO evaluation_objectifs (evaluation_id, objectif_id) "
        "VALUES ('ev1', 'o02')"
    )
    conn.execute(
        "INSERT INTO evaluation_objectifs (evaluation_id, objectif_id) "
        "VALUES ('ev1', 'o04')"
    )
    conn.execute(
        "INSERT INTO evaluation_objectifs (evaluation_id, objectif_id) "
        "VALUES ('ev1', 'o07')"
    )
    conn.commit()
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# TestHelpersRender — helpers internes du module
# ─────────────────────────────────────────────────────────────────────────────


class TestHelpersRender:
    """Tests des helpers internes (chiffres romains, label objectif, barèmes)."""

    def test_romain_unite(self):
        from services.render_evaluation import _romain
        assert _romain(1) == 'I'
        assert _romain(2) == 'II'
        assert _romain(3) == 'III'

    def test_romain_dizaine(self):
        from services.render_evaluation import _romain
        assert _romain(4) == 'IV'
        assert _romain(5) == 'V'
        assert _romain(9) == 'IX'
        assert _romain(10) == 'X'

    def test_romain_au_dela_de_10(self):
        from services.render_evaluation import _romain
        # Cas hors usage normal (>10 exos dans une éval) mais on garde
        # la conversion fonctionnelle pour ne pas tronquer en silence.
        assert _romain(14) == 'XIV'
        assert _romain(50) == 'L'

    def test_romain_zero(self):
        from services.render_evaluation import _romain
        assert _romain(0) == ''

    def test_label_objectif_court_avec_padding(self):
        from services.render_evaluation import _label_objectif_court
        o = {'sequence_code': 'S01', 'code': '2'}
        assert _label_objectif_court(o) == 'S01.Obj. 02'

    def test_label_objectif_court_deja_padde(self):
        from services.render_evaluation import _label_objectif_court
        o = {'sequence_code': 'S04', 'code': '14'}
        assert _label_objectif_court(o) == 'S04.Obj. 14'

    def test_label_objectif_court_code_non_numerique(self):
        # Cas d'usage marginal mais possible (codes alphabétiques)
        from services.render_evaluation import _label_objectif_court
        o = {'sequence_code': 'S01', 'code': '2bis'}
        assert _label_objectif_court(o) == 'S01.Obj. 2bis'

    def test_bareme_exo_str_standard_4_points(self):
        from services.render_evaluation import _bareme_exo_str
        eb = {'type_format': 'standard', 'bareme_points': 4.0}
        assert _bareme_exo_str(eb, 'note') == '4 points'

    def test_bareme_exo_str_singulier(self):
        from services.render_evaluation import _bareme_exo_str
        eb = {'type_format': 'standard', 'bareme_points': 1.0}
        assert _bareme_exo_str(eb, 'note') == '1 point'

    def test_bareme_exo_str_demi_point(self):
        from services.render_evaluation import _bareme_exo_str
        eb = {'type_format': 'standard', 'bareme_points': 2.5}
        assert _bareme_exo_str(eb, 'note') == '2.5 points'

    def test_bareme_exo_str_qcm_utilise_qcm_ok(self):
        from services.render_evaluation import _bareme_exo_str
        eb = {'type_format': 'qcm', 'bareme_qcm_ok': 1.0,
              'bareme_qcm_partiel': 0.5, 'bareme_qcm_ko': -0.25}
        assert _bareme_exo_str(eb, 'note') == '1 point'

    def test_bareme_exo_str_mode_aucun_vide(self):
        from services.render_evaluation import _bareme_exo_str
        eb = {'type_format': 'standard', 'bareme_points': 4.0}
        assert _bareme_exo_str(eb, 'aucun') == ''

    def test_bareme_exo_str_mode_criteres_vide(self):
        from services.render_evaluation import _bareme_exo_str
        eb = {'type_format': 'standard', 'bareme_points': 4.0}
        assert _bareme_exo_str(eb, 'criteres') == ''

    def test_bareme_exo_str_points_none(self):
        from services.render_evaluation import _bareme_exo_str
        eb = {'type_format': 'standard', 'bareme_points': None}
        assert _bareme_exo_str(eb, 'note') == ''

    def test_bareme_langue_dict(self):
        from services.render_evaluation import _bareme_langue_str
        # lire_evaluation parse le JSON, donc le helper reçoit un dict
        assert _bareme_langue_str({'points': 1}, 'note') == '1 point'
        assert _bareme_langue_str({'points': 2}, 'note') == '2 points'

    def test_bareme_langue_omet_en_mode_criteres(self):
        # Décision Q8 Laurent
        from services.render_evaluation import _bareme_langue_str
        assert _bareme_langue_str({'points': 1}, 'criteres') == ''

    def test_bareme_langue_inclut_en_mode_aucun(self):
        # 'aucun' n'a pas été exclu — décision Q8 ciblait 'criteres' seul
        from services.render_evaluation import _bareme_langue_str
        # En pratique en mode 'aucun' on émet quand même la ligne, ce qui
        # est cohérent : si l'enseignant a saisi un item langue, c'est qu'il
        # veut le voir.
        assert _bareme_langue_str({'points': 1}, 'aucun') == '1 point'

    def test_bareme_langue_vide_si_none(self):
        from services.render_evaluation import _bareme_langue_str
        assert _bareme_langue_str(None, 'note') == ''
        assert _bareme_langue_str('', 'note') == ''
        assert _bareme_langue_str({}, 'note') == ''

    def test_bareme_langue_tolere_string_json(self):
        # Tolérance défensive : si jamais l'appelant nous passe une string
        # JSON brute (au lieu du dict parsé), le helper la décode.
        from services.render_evaluation import _bareme_langue_str
        assert _bareme_langue_str('{"points": 3}', 'note') == '3 points'


# ─────────────────────────────────────────────────────────────────────────────
# TestSectionTitre — \seqTitreEval
# ─────────────────────────────────────────────────────────────────────────────


class TestSectionTitre:
    def test_titre_passe_dans_macro(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert '\\seqTitreEval[' in tex
        assert 'titre={Bilan T1}' in tex

    def test_etab_et_classe_sont_des_ellipses(self, conn_eval_simple):
        """v0.13.5.5 — Décision Q3 Laurent + fix bug \\seqTitreEval :
        on émet `etab={\\ldots}` et `classe={\\dots}` (placeholders non
        vides) plutôt que des valeurs vides, parce que la macro
        \\seqTitreEval utilise \\eue (= \\expandafter\\unexpanded\\expandafter)
        qui ne tolère pas un argument vide (cf. CorrList.tex via \\write).
        """
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert r'etab={\ldots}' in tex
        assert r'classe={\dots}' in tex
        # Garde-fou contre une régression vers les valeurs vides du
        # générateur initial (qui auraient cassé la compilation).
        assert 'etab=,' not in tex
        # 'classe=' (sans suffixe) reste tolérable car contenu dans
        # 'classe={\dots}' — on teste donc la forme nuisible précise :
        assert 'classe=\n]' not in tex

    def test_pas_de_theme(self, conn_eval_simple):
        # Décision Q2 Laurent : pas de theme= (défaut macro)
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert 'theme=' not in tex

    def test_init_corriges_eval_emis_avant_titre(self, conn_eval_simple):
        """v0.13.5.6 — Le générateur émet \\seqInitCorrigesEval juste
        avant \\seqTitreEval pour initialiser le canal d'écriture
        \\corrfileeval.

        \\seqInitCorrigesEval est la macro publique (paquet v0.13.5.6+)
        qui encapsule \\newwrite\\corrfileeval. Sans cet appel, la
        compilation échouait avec « Undefined control sequence » sur
        \\corrfileeval, parce que l'allocation TeX top-level dans
        seqenseigne-core.sty n'est pas indexée par le parser de paquet.
        """
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        # 1. \seqInitCorrigesEval est présent
        assert r'\seqInitCorrigesEval' in tex
        # 2. Et il apparaît AVANT \seqTitreEval (ordre essentiel : \openout
        # dans \seqTitreEval suppose que le canal est alloué)
        pos_init = tex.find(r'\seqInitCorrigesEval')
        pos_titre = tex.find(r'\seqTitreEval')
        assert pos_init >= 0
        assert pos_titre >= 0
        assert pos_init < pos_titre, (
            r"\seqInitCorrigesEval doit être émis AVANT \seqTitreEval"
        )

    def test_titre_vide_fallback(self, conn):
        from services.render_evaluation import generer_tex_evaluation
        conn.execute(
            "INSERT INTO evaluations (id, niveau, numero, ordre, titre) "
            "VALUES ('ev_no_title', 'N10', 1, 1, '')"
        )
        conn.commit()
        tex = generer_tex_evaluation(conn, 'ev_no_title')
        # Doit produire un titre par défaut, pas titre={}
        assert 'titre={Évaluation}' in tex


# ─────────────────────────────────────────────────────────────────────────────
# TestSectionBareme — seqEvalBareme
# ─────────────────────────────────────────────────────────────────────────────


class TestSectionBareme:
    def test_lignes_par_exo_en_romain(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert 'Exercice I & 4 points' in tex
        assert 'Exercice II & 6 points' in tex

    def test_pas_de_ligne_langue_si_champ_vide(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert 'Présentation et usage de la langue française' not in tex

    def test_ligne_langue_si_champ_rempli(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        # Ajouter l'item langue
        conn_eval_simple.execute(
            "UPDATE evaluations SET item_langue_francaise = ? WHERE id='ev1'",
            (json.dumps({'points': 1}),)
        )
        conn_eval_simple.commit()
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert 'Présentation et usage de la langue française & 1 point' in tex

    def test_ligne_langue_omise_en_mode_criteres(self, conn_eval_simple):
        # Q8 : on cache l'item langue en mode critères
        from services.render_evaluation import generer_tex_evaluation
        conn_eval_simple.execute(
            "UPDATE evaluations SET item_langue_francaise = ?, "
            "mode_notation = 'criteres' WHERE id='ev1'",
            (json.dumps({'points': 1}),)
        )
        conn_eval_simple.commit()
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert 'Présentation et usage de la langue française' not in tex

    def test_baremes_exo_vides_en_mode_criteres(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        conn_eval_simple.execute(
            "UPDATE evaluations SET mode_notation = 'criteres' WHERE id='ev1'"
        )
        conn_eval_simple.commit()
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        # Le libellé "Exercice I" est toujours là, mais sans valeur de points
        assert 'Exercice I &  \\\\' in tex

    def test_environnement_seqEvalBareme_present(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert '\\begin{seqEvalBareme}' in tex
        assert '\\end{seqEvalBareme}' in tex


# ─────────────────────────────────────────────────────────────────────────────
# TestSectionObjectifs — seqEvalObjectifs
# ─────────────────────────────────────────────────────────────────────────────


class TestSectionObjectifs:
    def test_section_emise_quand_objectifs_presents(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert '\\begin{seqEvalObjectifs}' in tex
        assert '\\end{seqEvalObjectifs}' in tex

    def test_section_omise_quand_aucun_objectif(self, conn):
        from services.render_evaluation import generer_tex_evaluation
        # Éval sans objectifs
        conn.execute(
            "INSERT INTO exercices (id, niveau, sequence, num, serie_code, "
            "type_format, titre, enonce) VALUES ('ex1', 'N10', 'S01', 1, 'F', "
            "'standard', 'Test', 'Un énoncé')"
        )
        conn.execute(
            "INSERT INTO evaluations (id, niveau, numero, ordre, titre) "
            "VALUES ('ev_no_obj', 'N10', 1, 1, 'Sans obj')"
        )
        conn.execute(
            "INSERT INTO evaluation_exercices (evaluation_id, exercice_id, "
            "ordre, bareme_points) VALUES ('ev_no_obj', 'ex1', 1, 4.0)"
        )
        conn.commit()
        tex = generer_tex_evaluation(conn, 'ev_no_obj')
        assert '\\begin{seqEvalObjectifs}' not in tex

    def test_format_code_objectif_avec_sequence(self, conn_eval_simple):
        # Décision Q4 : "S01.Obj. 02"
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert 'S01.Obj. 02' in tex
        assert 'S01.Obj. 04' in tex
        assert 'S01.Obj. 07' in tex

    def test_quatre_cases_a_cocher(self, conn_eval_simple):
        # 4 ❑ par ligne (Insuffisant / À consolider / Satisfaisant / Très bon)
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        # On vérifie qu'au moins une ligne contient 4 \ding{113}
        ligne_attendue = '\\ding{113} & \\ding{113} & \\ding{113} & \\ding{113}'
        assert ligne_attendue in tex

    def test_libelle_objectif_emis(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert 'Calculer un PGCD.' in tex
        assert 'Utiliser Thalès.' in tex


# ─────────────────────────────────────────────────────────────────────────────
# TestSectionExo — seqEvalExercice (un par exo)
# ─────────────────────────────────────────────────────────────────────────────


class TestSectionExo:
    def test_un_bloc_par_exo(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        # 2 exos → 2 \begin{seqEvalExercice}
        assert tex.count('\\begin{seqEvalExercice}') == 2
        assert tex.count('\\end{seqEvalExercice}') == 2

    def test_titre_passe_dans_options(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert 'titre={Calcul de proportions}' in tex
        assert 'titre={Thalès}' in tex

    def test_bareme_passe_dans_options(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert 'bareme={4 points}' in tex
        assert 'bareme={6 points}' in tex

    def test_enonce_insere_tel_quel(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        # L'énoncé brut "Calculer $\frac{1}{2}$." doit apparaître tel quel
        # (la fixture insère le contenu via paramètre SQL avec raw string
        # r'Calculer $\frac{1}{2}$.' → 1 backslash en BDD → 1 backslash en .tex)
        assert r'Calculer $\frac{1}{2}$.' in tex
        assert 'Soit ABC un triangle...' in tex

    def test_corrige_toujours_emis(self, conn_eval_simple):
        # Décision Q7 : \seqEvalCorrigeExo toujours présent
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert tex.count('\\seqEvalCorrigeExo{') == 2

    def test_corrige_renseigne_inclus(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert 'Réponse : 0,5' in tex

    def test_corrige_vide_marque_par_emph(self, conn_eval_simple):
        # ex_a01 a un corrigé vide → marque par défaut
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert '\\emph{Corrigé non rédigé.}' in tex

    def test_variables_avant_le_bloc(self, conn):
        # Vérifier que les variables xint sont émises AVANT le seqEvalExercice
        from services.render_evaluation import generer_tex_evaluation
        conn.execute(
            "INSERT INTO exercices (id, niveau, sequence, num, serie_code, "
            "type_format, titre, enonce, variables) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ('ex_var', 'N10', 'S01', 1, 'F', 'standard',
             'Test variables', 'Calculer x', r'\xintdefiivar x := 5;')
        )
        conn.execute(
            "INSERT INTO evaluations (id, niveau, numero, ordre, titre, "
            "mode_notation) VALUES ('ev_var', 'N10', 1, 1, 'Test', 'note')"
        )
        conn.execute(
            "INSERT INTO evaluation_exercices (evaluation_id, exercice_id, "
            "ordre, bareme_points) VALUES ('ev_var', 'ex_var', 1, 2.0)"
        )
        conn.commit()
        tex = generer_tex_evaluation(conn, 'ev_var')
        # Les variables doivent apparaître AVANT \begin{seqEvalExercice}
        pos_vars = tex.find(r'\xintdefiivar x := 5;')
        pos_bloc = tex.find(r'\begin{seqEvalExercice}[titre={Test variables}')
        assert pos_vars >= 0
        assert pos_bloc >= 0
        assert pos_vars < pos_bloc, "Variables doivent être AVANT le bloc seqEvalExercice"


# ─────────────────────────────────────────────────────────────────────────────
# TestGenerationComplete — .tex complet avec préambule
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerationComplete:
    def test_documentclass_present(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert '\\documentclass[a4paper,11pt]{article}' in tex

    def test_begin_et_end_document(self, conn_eval_simple):
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert '\\begin{document}' in tex
        assert '\\end{document}' in tex

    def test_affiche_corriges_en_fin(self, conn_eval_simple):
        # Q7 : toujours appeler \seqEvalAfficheCorriges
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        pos_macro = tex.find('\\seqEvalAfficheCorriges')
        pos_end = tex.find('\\end{document}')
        assert pos_macro >= 0
        assert pos_end > pos_macro

    def test_pifont_dans_preambule_pour_ding(self, conn_eval_simple):
        # \ding (cases ❑ du tableau objectifs) requiert pifont
        from services.render_evaluation import generer_tex_evaluation
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert 'pifont' in tex

    def test_evaluation_introuvable_leve_exception(self, conn):
        from services.render_evaluation import generer_tex_evaluation
        from services.evaluations import EvaluationIntrouvable
        with pytest.raises(EvaluationIntrouvable):
            generer_tex_evaluation(conn, 'inexistant_xyz')

    def test_eval_sans_exos_genere_quand_meme(self, conn):
        # Cas dégénéré : éval sans exo. Doit générer un .tex valide
        # (avec une ligne placeholder dans le barème pour ne pas casser
        # tabularray qui exige >= 1 ligne).
        from services.render_evaluation import generer_tex_evaluation
        conn.execute(
            "INSERT INTO evaluations (id, niveau, numero, ordre, titre, "
            "mode_notation) VALUES ('ev_vide', 'N10', 1, 1, 'Vide', 'note')"
        )
        conn.commit()
        tex = generer_tex_evaluation(conn, 'ev_vide')
        assert '\\begin{seqEvalBareme}' in tex
        # Pas de ligne 'Exercice I'
        assert 'Exercice I' not in tex


# ─────────────────────────────────────────────────────────────────────────────
# TestRoutesRendu — /api/evaluations/<id>/rendu-tex et /rendu-pdf
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def app_avec_eval(tmp_path):
    """App Flask de test avec une éval prête à compiler."""
    # On utilise l'app réelle (create_app) mais avec un data_dir temporaire
    # pour ne pas polluer la BDD de Laurent. On peuple via le store officiel.
    import sys, os, shutil
    # Préparer un data_dir vide avec les CSVs requis par l'auto-import
    data = tmp_path / "data"
    data.mkdir()
    # CSV minimaux pour que create_app ne lève pas
    (data / "param_niveaux.csv").write_text(
        "Code,CodeCycle,AnneeDansCycle,NomCourt,NomLong\n"
        "N10,C04,anneeun,5e,cinquième\n", encoding="utf-8"
    )
    (data / "C04_themes.csv").write_text(
        "Code,Nom,CodeCouleur,Description\nA,Test,a,desc\n",
        encoding="utf-8"
    )
    (data / "C04_sequences.csv").write_text(
        "Code,Numero,Nom,Theme\nS01,1,Test,A\n", encoding="utf-8"
    )

    from app import create_app
    app = create_app(data_dir=data)

    # Peupler la BDD avec une éval testable.
    # create_app n'inclut PAS paquet_definitions (créée séparément par
    # scripts/peuplement_14_paquet_vers_base.py au déploiement initial).
    # On les ajoute vides pour ne pas casser construire_preambule.
    with app.json_store._conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS paquet_definitions (
            nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
            corps TEXT, corps_fin TEXT, texte_complet TEXT,
            fichier_source TEXT, ligne_debut INTEGER,
            macros_appelees TEXT, environnements_utilises TEXT,
            statut_rendu_atome TEXT, contenu_atome TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS paquet_requirepackage (
            fichier_source TEXT NOT NULL,
            ordre          INTEGER NOT NULL,
            nom            TEXT NOT NULL,
            options        TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (fichier_source, ordre)
        )""")
        conn.execute(
            "INSERT INTO exercices (id, niveau, sequence, num, serie_code, "
            "type_format, serie, titre, enonce, corrige) "
            "VALUES ('ex_t1', 'N10', 'S01', 1, 'F', 'standard', "
            "'fondamental', 'Test', 'Un énoncé.', 'Le corrigé.')"
        )
        conn.execute(
            "INSERT INTO evaluations (id, niveau, numero, ordre, titre, "
            "mode_notation) VALUES ('ev_route_test', 'N10', 1, 1, 'Test routes', 'note')"
        )
        conn.execute(
            "INSERT INTO evaluation_exercices (evaluation_id, exercice_id, "
            "ordre, bareme_points) VALUES ('ev_route_test', 'ex_t1', 1, 4.0)"
        )
        conn.commit()
    return app


class TestRoutesRendu:
    def test_rendu_tex_200(self, app_avec_eval):
        client = app_avec_eval.test_client()
        r = client.get('/api/evaluations/ev_route_test/rendu-tex')
        assert r.status_code == 200

    def test_rendu_tex_content_type_text(self, app_avec_eval):
        client = app_avec_eval.test_client()
        r = client.get('/api/evaluations/ev_route_test/rendu-tex')
        # text/plain (avec ou sans charset suffix)
        assert r.headers.get('Content-Type', '').startswith('text/plain')

    def test_rendu_tex_contient_macros_eval(self, app_avec_eval):
        client = app_avec_eval.test_client()
        r = client.get('/api/evaluations/ev_route_test/rendu-tex')
        body = r.data.decode('utf-8')
        assert '\\seqTitreEval' in body
        assert '\\begin{seqEvalBareme}' in body
        assert '\\begin{seqEvalExercice}' in body
        assert '\\seqEvalAfficheCorriges' in body

    def test_rendu_tex_404_si_eval_inexistante(self, app_avec_eval):
        client = app_avec_eval.test_client()
        r = client.get('/api/evaluations/inexistant_xyz/rendu-tex')
        assert r.status_code == 404
        data = r.get_json()
        assert data['error'] == 'evaluation_introuvable'

    def test_rendu_pdf_404_si_eval_inexistante(self, app_avec_eval):
        client = app_avec_eval.test_client()
        r = client.post('/api/evaluations/inexistant_xyz/rendu-pdf')
        assert r.status_code == 404

    def test_rendu_pdf_echec_expose_log_complet(self, app_avec_eval):
        """v0.13.5.4 : le payload d'échec inclut log_complet pour le
        diagnostic, comme dans recap_cours/livret_sequence.

        Sur Linux sans MiKTeX, on tombe systématiquement en 503
        (pdflatex absent) — c'est la branche d'échec qu'on teste ici.
        """
        client = app_avec_eval.test_client()
        r = client.post('/api/evaluations/ev_route_test/rendu-pdf')
        # 503 (pdflatex absent) ou 422 (erreur LaTeX), peu importe le code :
        # tant que ce n'est pas 200, on a un payload d'échec à inspecter.
        assert r.status_code in (422, 503)
        data = r.get_json()
        # Le payload d'échec a une structure stable (cf. routes/evaluations.py
        # et le pattern partagé avec recap_cours.py / livret_sequence.py) :
        assert 'error' in data and data['error'] == 'compilation_echouee'
        assert 'message' in data
        assert 'erreurs' in data and isinstance(data['erreurs'], list)
        assert 'duree_ms' in data
        # v0.13.5.4 : log_complet exposé pour le bouton "Voir le .tex brut"
        # côté UI (charge le .tex via une route séparée, mais le log est
        # disponible si on veut l'afficher plus tard).
        assert 'log_complet' in data


# ─────────────────────────────────────────────────────────────────────────────
# TestResidusV25 — Fix résidus '?' dans dropdown et matrice de couverture
# ─────────────────────────────────────────────────────────────────────────────


class TestResidusV25:
    """Vérifie que api_exos_disponibles et calculer_couverture exposent
    les champs nécessaires à la construction du label métier N10/S01/F01
    côté UI. C'était le résidu connu de v25."""

    def test_api_exos_disponibles_expose_label_fields(self, app_avec_eval):
        # Pour que api_exos_disponibles trouve l'exo via objectifs,
        # il faut une liaison complète. Ajoutons-la.
        with app_avec_eval.json_store._conn() as conn:
            conn.execute(
                "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
                "VALUES ('spn_t', 'N10', 'S01')"
            )
            conn.execute(
                "INSERT INTO sequence_parties (id, sequence_par_niveau_id, "
                "numero) VALUES ('sp_t', 'spn_t', 1)"
            )
            conn.execute(
                "INSERT INTO objectifs (id, partie_id, code, nom) "
                "VALUES ('obj_t', 'sp_t', '01', 'Test')"
            )
            conn.execute(
                "INSERT INTO objectif_exos (objectif_id, serie, exercice_id, "
                "ordre) VALUES ('obj_t', 'F', 'ex_t1', 1)"
            )
            conn.commit()

        client = app_avec_eval.test_client()
        r = client.get('/api/evaluations/niveau/N10/exos-disponibles')
        assert r.status_code == 200
        data = r.get_json()
        assert 'par_sequence' in data
        assert 'S01' in data['par_sequence']
        exos = data['par_sequence']['S01']
        assert len(exos) == 1
        exo = exos[0]
        # Les nouveaux champs (v0.13.5.3) sont présents :
        assert exo['niveau']     == 'N10'
        assert exo['sequence']   == 'S01'
        assert exo['serie_code'] == 'F'
        assert exo['num']        == 1
        # Et les anciens aussi (pas de régression)
        assert exo['titre']        == 'Test'
        assert exo['type_format'] == 'standard'

    def test_calculer_couverture_expose_label_fields(self, app_avec_eval):
        # calculer_couverture est un service Python pur ; on l'appelle direct.
        from services.evaluations import calculer_couverture
        with app_avec_eval.json_store._conn() as conn:
            # Ajouter au moins un objectif lié à l'éval pour que la
            # couverture ait du sens
            conn.execute(
                "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
                "VALUES ('spn_c', 'N10', 'S01')"
            )
            conn.execute(
                "INSERT INTO sequence_parties (id, sequence_par_niveau_id, "
                "numero) VALUES ('sp_c', 'spn_c', 1)"
            )
            conn.execute(
                "INSERT INTO objectifs (id, partie_id, code, nom) "
                "VALUES ('obj_c', 'sp_c', '01', 'Test couv')"
            )
            conn.execute(
                "INSERT INTO evaluation_objectifs (evaluation_id, objectif_id) "
                "VALUES ('ev_route_test', 'obj_c')"
            )
            conn.commit()

            result = calculer_couverture(conn, 'ev_route_test')

        assert 'exercices' in result
        assert len(result['exercices']) == 1
        ex = result['exercices'][0]
        # Champs v0.13.5.3 :
        assert ex['niveau']     == 'N10'
        assert ex['sequence']   == 'S01'
        assert ex['serie_code'] == 'F'
        assert ex['num']        == 1
        # Champs préexistants :
        assert ex['type_format'] == 'standard'
        assert ex['ordre']      == 1


# ─────────────────────────────────────────────────────────────────────────────
# Sanity check : préambule 'evaluation' accepté
# ─────────────────────────────────────────────────────────────────────────────


class TestPreambuleEvaluation:
    def test_type_evaluation_accepte_par_construire_preambule(self, conn_eval_simple):
        """Régression : si quelqu'un retirait 'evaluation' de WRAPPER_PAR_TYPE,
        la génération .tex casserait via construire_preambule."""
        from services.render_evaluation import generer_tex_evaluation
        # Doit pas lever
        tex = generer_tex_evaluation(conn_eval_simple, 'ev1')
        assert len(tex) > 1000  # un .tex complet d'une éval, c'est gros

    def test_wrapper_par_type_inclut_evaluation(self):
        from services.preambule_atome import WRAPPER_PAR_TYPE
        assert 'evaluation' in WRAPPER_PAR_TYPE
        wrap = WRAPPER_PAR_TYPE['evaluation']
        # Vérifier la présence des macros/envs clés
        assert '\\seqTitreEval' in wrap
        assert 'seqEvalBareme' in wrap
        assert 'seqEvalObjectifs' in wrap
        assert 'seqEvalExercice' in wrap
        assert '\\seqEvalCorrigeExo' in wrap
        assert '\\seqEvalAfficheCorriges' in wrap
        assert '\\ding' in wrap
        # v0.13.5.6 — Ajout de \seqInitCorrigesEval. Cette macro est
        # appelée par le générateur avant \seqTitreEval pour initialiser
        # le canal \corrfileeval. Si elle n'est pas dans le wrapper, la
        # fermeture transitive ne tirera pas sa définition dans le
        # préambule et son corps \newwrite\corrfileeval ne sera pas
        # exécuté.
        assert '\\seqInitCorrigesEval' in wrap

    def test_regle_init_corriges_eval_presente(self):
        """v0.13.5.6 — \\seqInitCorrigesEval est marquée STATUT_REUTILISE
        (et pas STATUT_IGNORE qui empêcherait son inlining)."""
        from services.paquet_regles_atome import REGLES, STATUT_REUTILISE
        statut, _ = REGLES.get('\\seqInitCorrigesEval', (None, None))
        assert statut == STATUT_REUTILISE
