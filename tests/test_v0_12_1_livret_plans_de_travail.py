"""tests/test_v0_12_1_livret_plans_de_travail.py — v0.12.1.

Tests du chantier 2 « Livret annuel des plans de travail » :
- Service : génération .tex sur BDD minimale
- Format : présence des macros et environnements clés
- Cas limites : séquence sans partie, partie sans objectif, valeurs à 0
- Routes HTTP : 200 / 400 / 500

NB : on ne teste PAS la compilation pdflatex (besoin d'un binaire externe
et de TeXLive complet). Validation d'intégration faite manuellement par
Laurent côté production. Mais on s'assure que la structure du .tex
respecte les contrats clés (macros utilisées, échappement, calculs).
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Schéma minimal ──────────────────────────────────────────────────────────

_SCHEMA_TEST = """
CREATE TABLE cycles (
    code TEXT PRIMARY KEY, nom TEXT NOT NULL, description TEXT NOT NULL DEFAULT ''
);
-- v0.13.1 — Référentiel des niveaux scolaires (consommé par
-- services.param_niveaux helpers). Cette table est créée et amorcée
-- par SqliteStore en prod ; ici on la déclare manuellement et on
-- l'amorce dans la fixture (cf. _peupler_param_niveaux ci-dessous).
CREATE TABLE param_niveaux (
    code              TEXT PRIMARY KEY,
    cycle_code        TEXT NOT NULL REFERENCES cycles(code) ON DELETE RESTRICT,
    annee_dans_cycle  TEXT NOT NULL,
    nom_court         TEXT NOT NULL,
    nom_long          TEXT NOT NULL DEFAULT '',
    ordre             INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE themes (
    id TEXT PRIMARY KEY, cycle_code TEXT NOT NULL,
    code TEXT NOT NULL, nom TEXT NOT NULL,
    code_couleur TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    ordre INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE sequences_du_cycle (
    id TEXT PRIMARY KEY, cycle_code TEXT NOT NULL, code TEXT NOT NULL,
    numero INTEGER NOT NULL, nom TEXT NOT NULL, theme_id TEXT
);
CREATE TABLE sequences_par_niveau (
    id TEXT PRIMARY KEY, niveau TEXT NOT NULL, sequence_code TEXT NOT NULL,
    parametres TEXT NOT NULL DEFAULT '',
    UNIQUE (niveau, sequence_code)
);
CREATE TABLE sequence_parties (
    id TEXT PRIMARY KEY, sequence_par_niveau_id TEXT NOT NULL,
    numero INTEGER NOT NULL,
    nb_seances_R_AE REAL NOT NULL DEFAULT 0,
    UNIQUE (sequence_par_niveau_id, numero)
);
CREATE TABLE objectifs (
    id TEXT PRIMARY KEY, partie_id TEXT NOT NULL,
    code TEXT NOT NULL, nom TEXT NOT NULL DEFAULT '',
    methode_id TEXT,
    critere_F TEXT NOT NULL DEFAULT '',
    critere_A TEXT NOT NULL DEFAULT '',
    critere_E TEXT NOT NULL DEFAULT '',
    fin_cycle TEXT NOT NULL DEFAULT 'N',
    nb_seances REAL NOT NULL DEFAULT 0,
    UNIQUE (partie_id, code)
);
CREATE TABLE notions (
    id TEXT PRIMARY KEY, titre TEXT NOT NULL DEFAULT '',
    niveau TEXT NOT NULL DEFAULT '', sequence TEXT NOT NULL DEFAULT ''
);
CREATE TABLE objectif_notions (
    objectif_id TEXT NOT NULL, notion_id TEXT NOT NULL,
    ordre INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, notion_id)
);
CREATE TABLE exercices (
    id TEXT PRIMARY KEY, serie TEXT NOT NULL,
    nom TEXT NOT NULL DEFAULT '',
    niveau TEXT NOT NULL DEFAULT '',
    sequence TEXT NOT NULL DEFAULT '',
    num INTEGER, fichier TEXT NOT NULL DEFAULT '',
    serie_code TEXT NOT NULL DEFAULT ''
);
CREATE TABLE objectif_exos (
    objectif_id TEXT NOT NULL, serie TEXT NOT NULL,
    exercice_id TEXT NOT NULL, ordre INTEGER NOT NULL DEFAULT 0,
    origin_niveau TEXT, origin_seq TEXT, origin_serie TEXT, origin_num INTEGER,
    PRIMARY KEY (objectif_id, serie, exercice_id)
);
CREATE TABLE partie_exos_revision_approche (
    partie_id TEXT NOT NULL, type TEXT NOT NULL,
    exercice_id TEXT NOT NULL, ordre INTEGER NOT NULL DEFAULT 0,
    origin_niveau TEXT, origin_seq TEXT, origin_serie TEXT, origin_num INTEGER,
    PRIMARY KEY (partie_id, type, exercice_id)
);
"""


# v0.13.1 — Données de référence des niveaux pour les fixtures.
# Calque exact de data/param_niveaux.csv, factorisé pour éviter la
# duplication entre les multiples fixtures de ce fichier. Le service
# `livret_plans_de_travail._cycle_du_niveau` lit désormais cette table
# (au lieu d'un dict hardcodé), donc chaque fixture en a besoin.
_NIVEAUX_REF = [
    ('N07', 'C03', 'anneeun',    'CM1',  'cours moyen (1ère année)', 1),
    ('N08', 'C03', 'anneedeux',  'CM2',  'cours moyen (2nde année)', 2),
    ('N09', 'C03', 'anneetrois', '6ème', 'sixième',                  3),
    ('N10', 'C04', 'anneeun',    '5ème', 'cinquième',                4),
    ('N11', 'C04', 'anneedeux',  '4ème', 'quatrième',                5),
    ('N12', 'C04', 'anneetrois', '3ème', 'troisième',                6),
]


def _peupler_param_niveaux(conn, *, cycles_requis=None):
    """Insère les niveaux de référence dans `param_niveaux`. Crée aussi
    les cycles requis (C03, C04 ou un sous-ensemble selon les besoins
    du test) avant — la FK l'exige.

    Si `cycles_requis` est None, on amorce tous les niveaux N07..N12 et
    leurs deux cycles. Sinon on filtre sur les cycles demandés (utile
    pour les tests qui ont des assertions strictes sur le contenu de
    cycles, ex. test_seq_meme_code_dans_les_deux_cycles).
    """
    if cycles_requis is not None:
        cycles_requis = set(cycles_requis)
        rows = [r for r in _NIVEAUX_REF if r[1] in cycles_requis]
    else:
        rows = list(_NIVEAUX_REF)
    # Amorcer les cycles via INSERT OR IGNORE (n'écrase rien si déjà là).
    cycles_a_amorcer = sorted({r[1] for r in rows})
    for cc in cycles_a_amorcer:
        nom = f"Cycle {int(cc[1:])}" if cc.startswith('C') and cc[1:].isdigit() else cc
        conn.execute("INSERT OR IGNORE INTO cycles (code, nom) VALUES (?, ?)",
                     (cc, nom))
    conn.executemany(
        "INSERT OR IGNORE INTO param_niveaux "
        "(code, cycle_code, annee_dans_cycle, nom_court, nom_long, ordre) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(_SCHEMA_TEST)
    # v0.13.1 — Amorcer param_niveaux par défaut. Les tests qui veulent
    # un état différent peuvent DELETE ou re-INSERT après. Amorcer ici
    # via INSERT OR IGNORE garantit la compatibilité avec les fixtures
    # qui font ensuite leurs propres INSERT OR IGNORE INTO cycles.
    _peupler_param_niveaux(c)
    yield c
    c.close()


@pytest.fixture
def base(conn):
    """Base minimale : N10/C04, 1 thème, 2 séquences (S01: 1 partie ;
    S02: 2 parties), avec quelques objectifs et notions.
    """
    conn.executescript("""
        INSERT OR IGNORE INTO cycles (code, nom) VALUES ('C04', 'Cycle 4');
        INSERT INTO themes (id, cycle_code, code, nom, code_couleur, ordre)
            VALUES ('th_N', 'C04', 'N', 'Nombres', 'nombres', 1);
        INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
            VALUES
            ('sc_S01', 'C04', 'S01', 1, 'Représentations d''un nombre', 'th_N'),
            ('sc_S02', 'C04', 'S02', 2, 'Comparaison de nombres', 'th_N');
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
            ('sn_A', 'N10', 'S01'),
            ('sn_B', 'N10', 'S02');
        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero, nb_seances_R_AE) VALUES
            ('pt_A1', 'sn_A', 1, 2),
            ('pt_B1', 'sn_B', 1, 1.5),
            ('pt_B2', 'sn_B', 2, 0.5);
        INSERT INTO objectifs (id, partie_id, code, nom, nb_seances) VALUES
            ('ob_A01', 'pt_A1', '01', 'Cours', 1),
            ('ob_A02', 'pt_A1', '02', 'Calculer une fraction, simplifier.', 2),
            ('ob_B01', 'pt_B1', '01', 'Cours', 1),
            ('ob_B02', 'pt_B1', '02', 'Comparer dans Q', 1),
            ('ob_B11', 'pt_B2', '11', 'Cours bis', 0),
            ('ob_B12', 'pt_B2', '12', 'Avec puissances', 0);
        INSERT INTO notions (id, titre) VALUES
            ('n_A1', 'Fraction'),
            ('n_A2', 'Numérateur');
        INSERT INTO objectif_notions (objectif_id, notion_id, ordre) VALUES
            ('ob_A02', 'n_A1', 1),
            ('ob_A02', 'n_A2', 2);
        INSERT INTO exercices (id, serie, nom) VALUES
            ('ex_1', 'F', 'F1'), ('ex_2', 'F', 'F2'),
            ('ex_3', 'A', 'A1'), ('ex_4', 'E', 'E1');
        INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) VALUES
            ('ob_A02', 'F', 'ex_1', 1),
            ('ob_A02', 'F', 'ex_2', 2),
            ('ob_A02', 'A', 'ex_3', 1),
            ('ob_A02', 'E', 'ex_4', 1);
        INSERT INTO partie_exos_revision_approche (partie_id, type, exercice_id, ordre) VALUES
            ('pt_A1', 'R', 'ex_1', 1),
            ('pt_A1', 'EA', 'ex_2', 1);
    """)
    conn.commit()
    return conn


# ═════════════════════════════════════════════════════════════════════════════
# 1. Génération minimale et structure
# ═════════════════════════════════════════════════════════════════════════════

# Note : on ne peut pas appeler `generer_livret_plans_de_travail` directement
# avec une connexion `:memory:` car `construire_preambule` interroge la table
# `paquet_definitions` qui n'existe pas dans notre schéma minimal. Les tests
# ci-dessous ciblent les helpers internes qui n'utilisent que la BDD métier.

from services.livret_plans_de_travail import (
    _lire_sequences_du_niveau,
    _lire_parties_de_sequence,
    _lire_objectifs_de_partie,
    _calculer_total_partie,
    _est_objectif_cours,
    _fmt_seances,
    _fmt_total_seances,
    _fmt_liste_exos,
    _suffixe_partie,
    _emettre_bloc_revisions,
    _emettre_objectif_exo,
    _emettre_bloc_reperes,
    _emettre_page_titre,
)
# v0.15.5 — `_cycle_du_niveau` (wrapper local) supprimé des services livret.
# La résolution du cycle passe désormais par la source unique de vérité
# `services.param_niveaux.lire_cycle`. Les tests de régression C03/C04
# ci-dessous ciblent donc directement cette fonction.
from services.param_niveaux import lire_cycle as _cycle_du_niveau


class TestCycleDuNiveau:

    def test_n10_renvoie_c04(self, base):
        assert _cycle_du_niveau(base, 'N10') == 'C04'

    def test_n11_renvoie_c04(self, base):
        assert _cycle_du_niveau(base, 'N11') == 'C04'

    def test_n12_renvoie_c04(self, base):
        assert _cycle_du_niveau(base, 'N12') == 'C04'

    def test_n09_renvoie_c03(self, base):
        assert _cycle_du_niveau(base, 'N09') == 'C03'

    def test_niveau_inconnu_leve(self, base):
        with pytest.raises(LookupError):
            _cycle_du_niveau(base, 'N99')

    def test_pas_de_confusion_cycle3_cycle4(self, conn):
        """Test de régression v0.12.1.2, durci en v0.15.5 : la résolution
        du cycle d'un niveau ne doit JAMAIS dépendre des tables
        `sequences_par_niveau × sequences_du_cycle`. Une jointure sur le
        code de séquence (ex. S01, partagé entre C03 et C04) suivie d'un
        `LIMIT 1` remontait le mauvais cycle.

        Cf. bug reporté en production après v0.12.1.1 : « Le livret
        affiche les séquences cycle 3 (Nombres entiers, Fractions, …)
        en N10/N12 alors qu'on est au cycle 4 ».

        v0.15.5 : la fonction testée est désormais
        `services.param_niveaux.lire_cycle`, qui lit la table
        `param_niveaux` (source unique de vérité) et ignore donc
        totalement le contenu des tables séquence. Ce test reproduit le
        contexte piège (S01 en C03 ET C04, séquence-niveau N10/S01) et
        vérifie que C04 sort bien — indépendamment de ce piège.
        """
        conn.executescript("""
            INSERT OR IGNORE INTO cycles (code, nom) VALUES
                ('C03', 'Cycle 3'),
                ('C04', 'Cycle 4');
            INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom) VALUES
                ('sc3_S01', 'C03', 'S01', 1, 'Nombres entiers'),
                ('sc4_S01', 'C04', 'S01', 1, 'Représentations d''un nombre');
            INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
                ('sn_N10_S01', 'N10', 'S01');
        """)
        conn.commit()
        # La résolution doit être indépendante du contenu BDD.
        assert _cycle_du_niveau(conn, 'N10') == 'C04'
        # Et N09 reste C03 même si rien n'est assemblé en N09 dans cette BDD.
        assert _cycle_du_niveau(conn, 'N09') == 'C03'


class TestLireSequencesDuNiveau:

    def test_ordonnees_par_numero(self, base):
        seqs = _lire_sequences_du_niveau(base, 'N10', 'C04')
        assert [s['sequence_code'] for s in seqs] == ['S01', 'S02']
        assert seqs[0]['numero'] == 1
        assert seqs[1]['numero'] == 2

    def test_couleur_theme(self, base):
        seqs = _lire_sequences_du_niveau(base, 'N10', 'C04')
        assert seqs[0]['theme_code_couleur'] == 'nombres'

    def test_niveau_inexistant(self, base):
        seqs = _lire_sequences_du_niveau(base, 'N12', 'C04')
        assert seqs == []

    def test_pas_de_duplication_cycle3_cycle4(self, conn):
        """Test de régression v0.12.1.1 : sans le filtre `cycle_code`, la
        jointure `sequences_par_niveau × sequences_du_cycle` matche sur
        le seul `code` (ex. 'S01') et duplique chaque ligne quand le
        même code existe en C03 ET en C04. Cf. bug reporté en
        production : « le PDF de 5e contient toutes les séquences de
        5e ET de 6e ».

        Cas reproducteur : on insère 'S01' dans les deux cycles avec
        des noms différents ; le résultat ne doit ramener que la ligne
        du cycle demandé (C04).
        """
        conn.executescript("""
            INSERT OR IGNORE INTO cycles (code, nom) VALUES
                ('C03', 'Cycle 3'),
                ('C04', 'Cycle 4');
            INSERT INTO themes (id, cycle_code, code, nom, code_couleur, ordre) VALUES
                ('th_N3', 'C03', 'N', 'Nombres 6e', 'nombres', 1),
                ('th_N4', 'C04', 'N', 'Nombres collège', 'nombres', 1);
            INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id) VALUES
                ('sc3_S01', 'C03', 'S01', 1, 'Nombres entiers', 'th_N3'),
                ('sc4_S01', 'C04', 'S01', 1, 'Représentations d''un nombre', 'th_N4');
            INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
                ('sn_N10_S01', 'N10', 'S01');
        """)
        conn.commit()
        # Avec le filtre cycle_code='C04', on ne ramène que la ligne C04
        seqs = _lire_sequences_du_niveau(conn, 'N10', 'C04')
        assert len(seqs) == 1, f"Attendu 1 ligne, obtenu {len(seqs)}"
        assert seqs[0]['nom'] == "Représentations d'un nombre"
        # Avec C03 par erreur, on aurait l'ancien nom
        seqs_c3 = _lire_sequences_du_niveau(conn, 'N10', 'C03')
        assert len(seqs_c3) == 1
        assert seqs_c3[0]['nom'] == 'Nombres entiers'


class TestLireParties:

    def test_partie_unique(self, base):
        seqs = _lire_sequences_du_niveau(base, 'N10', 'C04')
        sn_A = seqs[0]['sn_id']
        parties = _lire_parties_de_sequence(base, sn_A)
        assert len(parties) == 1
        assert parties[0]['numero'] == 1
        assert parties[0]['nb_seances_R_AE'] == 2

    def test_parties_multiples(self, base):
        seqs = _lire_sequences_du_niveau(base, 'N10', 'C04')
        sn_B = seqs[1]['sn_id']
        parties = _lire_parties_de_sequence(base, sn_B)
        assert len(parties) == 2
        assert parties[0]['numero'] == 1
        assert parties[1]['numero'] == 2

    def test_exos_R_et_EA(self, base):
        seqs = _lire_sequences_du_niveau(base, 'N10', 'C04')
        parties = _lire_parties_de_sequence(base, seqs[0]['sn_id'])
        assert parties[0]['exos_R'] == [1]
        assert parties[0]['exos_EA'] == [1]


class TestLireObjectifs:

    def test_ordre_par_code(self, base):
        objs = _lire_objectifs_de_partie(base, 'pt_A1')
        assert [o['code'] for o in objs] == ['01', '02']

    def test_notions(self, base):
        objs = _lire_objectifs_de_partie(base, 'pt_A1')
        # ob_A02 a Fraction puis Numérateur
        ob_02 = next(o for o in objs if o['code'] == '02')
        assert ob_02['notions_titres'] == ['Fraction', 'Numérateur']

    def test_exos_par_serie(self, base):
        objs = _lire_objectifs_de_partie(base, 'pt_A1')
        ob_02 = next(o for o in objs if o['code'] == '02')
        assert ob_02['exos_F'] == [1, 2]
        assert ob_02['exos_A'] == [1]
        assert ob_02['exos_E'] == [1]

    def test_nom_avec_latex_intentionnel(self, base):
        # Le nom contient une virgule et un point — pas d'échappement attendu
        objs = _lire_objectifs_de_partie(base, 'pt_A1')
        ob_02 = next(o for o in objs if o['code'] == '02')
        assert ',' in ob_02['nom']  # virgule préservée


# ═════════════════════════════════════════════════════════════════════════════
# 2. Calculs et formatage
# ═════════════════════════════════════════════════════════════════════════════

class TestCalculerTotalPartie:

    def test_total_simple(self):
        partie = {'nb_seances_R_AE': 2}
        objs = [{'nb_seances': 1}, {'nb_seances': 2}]
        assert _calculer_total_partie(partie, objs) == 5.0

    def test_total_demi_seances(self):
        partie = {'nb_seances_R_AE': 1.5}
        objs = [{'nb_seances': 0.5}, {'nb_seances': 2}]
        assert _calculer_total_partie(partie, objs) == 4.0

    def test_total_zero(self):
        partie = {'nb_seances_R_AE': 0}
        objs = []
        assert _calculer_total_partie(partie, objs) == 0


class TestEstObjectifCours:
    def test_partie_1_code_01(self):
        assert _est_objectif_cours('01', 1) is True
    def test_partie_2_code_11(self):
        assert _est_objectif_cours('11', 2) is True
    def test_partie_3_code_21(self):
        assert _est_objectif_cours('21', 3) is True
    def test_partie_1_code_02(self):
        assert _est_objectif_cours('02', 1) is False
    def test_code_vide(self):
        assert _est_objectif_cours('', 1) is False


class TestFmtSeances:
    def test_zero_donne_ldots(self):
        assert _fmt_seances(0) == r'\ldots'
    def test_none_donne_ldots(self):
        assert _fmt_seances(None) == r'\ldots'
    def test_entier(self):
        assert _fmt_seances(2) == '2'
    def test_demi_avec_virgule_fr(self):
        assert _fmt_seances(1.5) == '1,5'
    def test_string_acceptee(self):
        assert _fmt_seances('2') == '2'


class TestFmtListeExos:
    def test_liste_vide(self):
        assert _fmt_liste_exos([]) == '-'
    def test_liste_simple(self):
        assert _fmt_liste_exos([1, 2, 3]) == '1,2,3'
    def test_liste_unitaire(self):
        assert _fmt_liste_exos([5]) == '5'


class TestSuffixePartie:
    def test_partie_unique_pas_de_suffixe(self):
        assert _suffixe_partie(1, 1) == ''
    def test_premiere_partie(self):
        assert r'1\iere' in _suffixe_partie(1, 2)
    def test_deuxieme_partie(self):
        assert r'2\ieme' in _suffixe_partie(2, 3)


# ═════════════════════════════════════════════════════════════════════════════
# 3. Émission des blocs LaTeX (vérifications de format)
# ═════════════════════════════════════════════════════════════════════════════

class TestBlocRevisions:

    def test_renomme_revisions_decouverte(self):
        partie = {'exos_R': [1, 2], 'exos_EA': [3]}
        tex = '\n'.join(_emettre_bloc_revisions(partie))
        assert 'Révisions et découverte' in tex
        # Plus de "Auto-évaluation"
        assert 'Auto-évaluation' not in tex

    def test_deux_lignes_R_et_decouverte(self):
        partie = {'exos_R': [1, 2], 'exos_EA': [3, 4]}
        tex = '\n'.join(_emettre_bloc_revisions(partie))
        assert r'\item Révisions: 1,2' in tex
        assert r'\item Découverte: 3,4' in tex

    def test_listes_vides(self):
        partie = {'exos_R': [], 'exos_EA': []}
        tex = '\n'.join(_emettre_bloc_revisions(partie))
        assert r'\item Révisions: -' in tex
        assert r'\item Découverte: -' in tex

    def test_double_accolades_titre(self):
        # Le titre est encadré par {{...}} pour éviter l'erreur tcolorbox
        # « Incomplete \iffalse » causée par les virgules
        partie = {'exos_R': [], 'exos_EA': []}
        tex = '\n'.join(_emettre_bloc_revisions(partie))
        assert r'\begin{boitePaleNoBreak}{{\textbf{Révisions et découverte}}}' in tex


class TestObjectifExo:

    def test_titre_double_accolades(self):
        # CRITIQUE : le bug `Incomplete \iffalse` se déclenche si le titre
        # n'a qu'une paire d'accolades. Le test garantit la double paire.
        o = {
            'code': '02',
            'nom': 'Foo, bar.',  # virgule volontaire
            'notions_titres': [],
            'exos_F': [1], 'exos_A': [], 'exos_E': [],
        }
        tex = '\n'.join(_emettre_objectif_exo(o))
        assert r'\begin{boitePaleNoBreak}{{\begin{minipage}' in tex
        assert r'\end{minipage}}}' in tex

    def test_nom_objectif_dans_titre(self):
        o = {
            'code': '03', 'nom': 'Calculer',
            'notions_titres': [],
            'exos_F': [], 'exos_A': [], 'exos_E': [],
        }
        tex = '\n'.join(_emettre_objectif_exo(o))
        assert r'\textbf{03}: Calculer' in tex

    def test_notions_listees_avec_og_fg(self):
        o = {
            'code': '02', 'nom': 'X',
            'notions_titres': ['Fraction', 'Décimal'],
            'exos_F': [], 'exos_A': [], 'exos_E': [],
        }
        tex = '\n'.join(_emettre_objectif_exo(o))
        assert r'\og Fraction \fg{}' in tex
        assert r'\og Décimal \fg{}' in tex

    def test_pas_de_notion_donne_dash(self):
        o = {
            'code': '02', 'nom': 'X', 'notions_titres': [],
            'exos_F': [], 'exos_A': [], 'exos_E': [],
        }
        tex = '\n'.join(_emettre_objectif_exo(o))
        assert r'\item Notions: -' in tex

    def test_listes_F_A_E(self):
        o = {
            'code': '02', 'nom': 'X', 'notions_titres': [],
            'exos_F': [1, 2], 'exos_A': [3], 'exos_E': [],
        }
        tex = '\n'.join(_emettre_objectif_exo(o))
        assert 'Série fondamentale: 1,2' in tex
        assert 'Série avancée: 3' in tex
        assert 'Série exploration: -' in tex

    def test_nom_avec_latex_intentionnel_preserve(self):
        # Cas réel : Laurent met du LaTeX dans les noms d'objectifs
        o = {
            'code': '04',
            'nom': r'Factoriser \mbox{$a^2-b^2$}',
            'notions_titres': [],
            'exos_F': [], 'exos_A': [], 'exos_E': [],
        }
        tex = '\n'.join(_emettre_objectif_exo(o))
        # Le LaTeX est préservé tel quel (pas d'échappement de $)
        assert r'\mbox{$a^2-b^2$}' in tex


class TestBlocReperes:

    def test_repere_revisions_avec_seances(self):
        partie = {'nb_seances_R_AE': 2, 'exos_R': [], 'exos_EA': []}
        objs = [
            {'code': '01', 'nb_seances': 1, 'nom': 'C'},
            {'code': '02', 'nb_seances': 2, 'nom': 'X'},
        ]
        tex = '\n'.join(_emettre_bloc_reperes(1, 1, partie, objs))
        assert r'\item Révisions: 2~séances' in tex
        assert r'\item Cours: 1~séances' in tex
        assert r'\item Objectif 02: 2~séances' in tex

    def test_total_calcule(self):
        partie = {'nb_seances_R_AE': 2, 'exos_R': [], 'exos_EA': []}
        objs = [
            {'code': '01', 'nb_seances': 1, 'nom': 'C'},
            {'code': '02', 'nb_seances': 1.5, 'nom': 'X'},
        ]
        tex = '\n'.join(_emettre_bloc_reperes(1, 1, partie, objs))
        # Total = 2 + 1 + 1.5 = 4.5 → '4,5'
        assert r'\item Travail en classe: 4,5~séances' in tex

    def test_niveaux_atteints(self):
        partie = {'nb_seances_R_AE': 0, 'exos_R': [], 'exos_EA': []}
        objs = [
            {'code': '01', 'nb_seances': 0, 'nom': 'C'},
            {'code': '02', 'nb_seances': 0, 'nom': 'X'},
        ]
        tex = '\n'.join(_emettre_bloc_reperes(1, 1, partie, objs))
        # Niveaux atteints : un item par objectif (cours + exo)
        # Le bloc doit afficher des \ldots quand nb_seances=0
        assert 'Niveaux atteints' in tex
        assert 'Note équivalente' in tex


class TestPageTitre:

    def test_libelle_niveau_n10(self):
        tex = '\n'.join(_emettre_page_titre('N10'))
        assert r'5\ieme' in tex

    def test_ldots_pour_annee_etablissement(self):
        # Année / Établissement / Classe restent à compléter à la main
        tex = '\n'.join(_emettre_page_titre('N10'))
        assert tex.count(r'\ldots') >= 3

    def test_titre_principal(self):
        tex = '\n'.join(_emettre_page_titre('N11'))
        assert 'Plans de travail' in tex


# ═════════════════════════════════════════════════════════════════════════════
# 4. (Tests des routes HTTP supprimés en v0.15.1)
# ═════════════════════════════════════════════════════════════════════════════
#
# Les classes TestRouteTex et TestRoutePdf testaient les routes
# `/api/plans-de-travail/<niveau>/{tex,pdf}` qui ont été supprimées
# en v0.15.1 (les 3 ateliers Récap cours / Récap exos / Plans de
# travail sont remplacés par Référentiel > Documents à publier).
# Le service Python `livret_plans_de_travail` reste testé en amont
# (sections 1 à 3 et 5) car il est encore utilisé par d'autres
# modules (referentiels.py, orchestrateur_compilation.py).

# ═════════════════════════════════════════════════════════════════════════════
# 5. v0.12.1.2 — Plan de travail au scope séquence
# ═════════════════════════════════════════════════════════════════════════════
#
# `generer_plan_de_travail_sequence(conn, niveau, sequence_code)` produit un
# .tex limité à une seule séquence-niveau, sans page de titre. Tests sur la
# fixture `base` (N10/C04, S01 à 1 partie / S02 à 2 parties).

from services.livret_plans_de_travail import (
    generer_plan_de_travail_sequence,
    SequenceParNiveauIntrouvable,
)
from services import livret_plans_de_travail as _mod_lpdt


@pytest.fixture
def stub_preambule(monkeypatch):
    """Stub `construire_preambule` pour les tests qui utilisent la fixture
    `base` mémoire (sans `paquet_definitions`). On évite ainsi le crash
    dû à l'absence de cette table dans le schéma minimal — les
    fonctions à tester sont des helpers de structuration, pas le
    préambule.
    """
    class _FakePreambule:
        texte = '%% (préambule stubbed pour tests)'

    monkeypatch.setattr(_mod_lpdt, 'construire_preambule',
                        lambda *a, **kw: _FakePreambule())
    monkeypatch.setattr(_mod_lpdt, '_recuperer_texte_macro',
                        lambda conn, macro: f'%% (macro {macro} stubbed)')
    yield


class TestGenerationScopeSequence:
    """Vérifie la structure du .tex produit pour une seule séquence."""

    def test_tex_genere_pour_sequence_a_1_partie(self, base, stub_preambule):
        tex = generer_plan_de_travail_sequence(base, 'N10', 'S01')
        # Une seule page de partie pour S01.
        assert tex.count('seqBoiteTitrePlan[titre=') == 1
        # Le titre de la séquence doit apparaître dans la boîte.
        assert "Représentations d'un nombre" in tex
        # \begin{document} et \end{document} présents.
        assert r'\begin{document}' in tex
        assert r'\end{document}' in tex

    def test_tex_genere_pour_sequence_a_2_parties(self, base, stub_preambule):
        tex = generer_plan_de_travail_sequence(base, 'N10', 'S02')
        # Deux pages de partie pour S02.
        assert tex.count('seqBoiteTitrePlan[titre=') == 2
        # Suffixes (1ère partie) / (2e partie) présents
        assert r'1\iere{} partie' in tex
        assert r'2\ieme{} partie' in tex

    def test_pas_de_page_de_titre(self, base, stub_preambule):
        """Différence majeure avec le livret niveau : pas de page titre."""
        tex = generer_plan_de_travail_sequence(base, 'N10', 'S01')
        # Le titre annuel « Plans de travail » ne doit PAS être présent
        # (c'est le titre de la page-titre du livret niveau, qui n'existe
        # pas ici).
        assert 'Plans de travail' not in tex
        # Pas non plus de libellé « Classe de 5e ».
        assert 'Classe de' not in tex

    def test_seqSetCodeSequence_correct(self, base, stub_preambule):
        """Le compteur de séquence doit refléter la séquence demandée
        (et pas S00 comme dans le livret niveau)."""
        tex = generer_plan_de_travail_sequence(base, 'N10', 'S02')
        assert r'\seqSetCodeSequence{S02}' in tex
        assert r'\seqSetCodeSequence{S00}' not in tex

    def test_seqSetCodeNiveau_correct(self, base, stub_preambule):
        tex = generer_plan_de_travail_sequence(base, 'N10', 'S01')
        assert r'\seqSetCodeNiveau{N10}' in tex


class TestErreursScopeSequence:
    """Cas d'erreur : niveau inconnu, séquence non assemblée, séquence
    sans partie."""

    def test_niveau_inconnu_leve_lookup_error(self, base):
        with pytest.raises(LookupError):
            generer_plan_de_travail_sequence(base, 'N99', 'S01')

    def test_sequence_inconnue_leve_introuvable(self, base, stub_preambule):
        with pytest.raises(SequenceParNiveauIntrouvable) as exc:
            generer_plan_de_travail_sequence(base, 'N10', 'S99')
        assert exc.value.niveau == 'N10'
        assert exc.value.sequence_code == 'S99'

    def test_sequence_sans_partie_leve_introuvable(self, conn, stub_preambule):
        """Cas limite : la séquence-niveau existe mais n'a aucune
        partie (assemblage interrompu). Le service doit lever plutôt
        que de produire un .tex sans page valide (qui crasherait
        pdflatex)."""
        conn.executescript("""
            INSERT OR IGNORE INTO cycles (code, nom) VALUES ('C04', 'Cycle 4');
            INSERT INTO themes (id, cycle_code, code, nom) VALUES
                ('th_N', 'C04', 'N', 'Nombres');
            INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
                VALUES ('sc_S01', 'C04', 'S01', 1, 'X', 'th_N');
            INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
                ('sn_vide', 'N10', 'S01');
        """)
        conn.commit()
        with pytest.raises(SequenceParNiveauIntrouvable) as exc:
            generer_plan_de_travail_sequence(conn, 'N10', 'S01')
        assert 'aucune partie' in exc.value.motif


# v0.15.1 — TestRouteScopeSequence supprimée (testait
# `/api/plans-de-travail/<niveau>/<sequence_code>/{tex,pdf}`, route
# HTTP retirée en même temps que les 3 ateliers Récap/Plans).
