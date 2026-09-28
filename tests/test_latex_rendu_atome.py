r"""
tests/test_latex_rendu_atome.py — Tests de la génération .tex atomique.

v0.7 — Tests adaptés au modèle universel à 2 niveaux pour les sections
d'atomes. La table items_texte a été remplacée par atome_sections +
atome_section_items en v0.6.4 ; les fixtures et assertions de ce fichier
sont mises à jour en conséquence.

Couvre :
  - Chargement des 3 types d'atomes
  - Détection des options [geometrie] / [scratch]
  - Résolution du thème depuis le référentiel
  - Substitution des getters CSV (seqObjectifGetNom, etc.)
  - Collecte des réécritures
  - Génération complète (exercice, notion, méthode)
  - Modèle universel à 2 niveaux : sections avec titre libre + items
"""

from __future__ import annotations
import pytest

import sqlite3
import tempfile
from pathlib import Path

from services.latex_rendu_atome import (
    Atome,
    TABLES_ATOMES,
    charger_atome,
    detecter_options_paquet,
    detecter_paquets_tex_manquants,
    resoudre_theme,
    resoudre_macros_csv,
    collecter_reecritures,
    generer_corps_exercice,
    generer_corps_notion,
    generer_corps_methode,
    generer_corps_fiche,
    generer_tex_atome,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_peuplee():
    """Base SQLite minimale avec les tables utilisées par le service."""
    conn = sqlite3.connect(':memory:')
    conn.executescript("""
        -- Référentiel
        CREATE TABLE referentiel_niveaux (
            id TEXT PRIMARY KEY,
            niveau TEXT NOT NULL,
            version TEXT NOT NULL,
            date_debut TEXT,
            date_fin TEXT,
            description TEXT DEFAULT '',
            etat TEXT DEFAULT 'en_cours'
        );
        CREATE TABLE referentiel_themes (
            referentiel_id TEXT NOT NULL,
            code TEXT NOT NULL,
            nom TEXT NOT NULL,
            couleur TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (referentiel_id, code)
        );
        CREATE TABLE referentiel_sequences (
            referentiel_id TEXT NOT NULL,
            code TEXT NOT NULL,
            numero INTEGER NOT NULL,
            nom TEXT NOT NULL,
            theme_code TEXT,
            PRIMARY KEY (referentiel_id, code)
        );

        -- Atomes
        CREATE TABLE exercices (
            id TEXT PRIMARY KEY,
            serie TEXT, titre TEXT DEFAULT '',
            variables TEXT DEFAULT '', enonce TEXT DEFAULT '', corrige TEXT DEFAULT '',
            niveau TEXT DEFAULT '', sequence TEXT DEFAULT '',
            num INTEGER, serie_code TEXT DEFAULT '', fichier TEXT DEFAULT '',
            -- v0.11.6 : remédiation et cadre de réponse
            remed_enonce TEXT NOT NULL DEFAULT '',
            remed_corrige TEXT NOT NULL DEFAULT '',
            cadre_reponse_lignes_principal INTEGER NOT NULL DEFAULT 0,
            cadre_reponse_lignes_remed INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE notions (
            id TEXT PRIMARY KEY,
            titre TEXT DEFAULT '', corps TEXT DEFAULT '',
            ordre_sections TEXT DEFAULT 'ER',
            niveau TEXT DEFAULT '', sequence TEXT DEFAULT '',
            num_connaissance TEXT DEFAULT '', fichier TEXT DEFAULT ''
        );
        CREATE TABLE methodes (
            id TEXT PRIMARY KEY,
            titre TEXT DEFAULT '', corps TEXT DEFAULT '',
            fin_cycle TEXT DEFAULT 'N', ordre_sections TEXT DEFAULT 'ER',
            niveau TEXT DEFAULT '', sequence TEXT DEFAULT '',
            num_methode INTEGER, num_objectif TEXT DEFAULT '',
            fichier TEXT DEFAULT ''
        );
        -- v0.11.1 — Table fiches_resume pour les tests de rendu fiche.
        -- Schéma minimal : on ne teste pas les liaisons obj_fiches ici.
        CREATE TABLE fiches_resume (
            id TEXT PRIMARY KEY,
            titre TEXT NOT NULL DEFAULT '',
            objectif_id TEXT,
            num_fiche INTEGER,
            niveau TEXT NOT NULL DEFAULT '',
            sequence TEXT NOT NULL DEFAULT '',
            fichier TEXT NOT NULL DEFAULT '',
            etat_code TEXT NOT NULL DEFAULT 'en_cours'
        );
        CREATE TABLE atome_sections (
            id           TEXT PRIMARY KEY,
            entite_type  TEXT NOT NULL,
            entite_id    TEXT NOT NULL,
            titre        TEXT NOT NULL,
            ordre        INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE atome_section_items (
            id           TEXT PRIMARY KEY,
            section_id   TEXT NOT NULL REFERENCES atome_sections(id) ON DELETE CASCADE,
            ordre        INTEGER NOT NULL DEFAULT 0,
            corps        TEXT NOT NULL DEFAULT ''
        );
        -- v0.14.7 — Table `objectifs` unique (anciennement `objectifs_v2`).
        -- L'ancienne table v1 a été supprimée en v0.14.6.b.2.
        CREATE TABLE sequences_par_niveau (
            id TEXT PRIMARY KEY,
            niveau TEXT NOT NULL,
            sequence_code TEXT NOT NULL,
            parametres TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE sequence_parties (
            id TEXT PRIMARY KEY,
            sequence_par_niveau_id TEXT NOT NULL,
            numero INTEGER NOT NULL
        );
        CREATE TABLE objectifs (
            id TEXT PRIMARY KEY,
            partie_id TEXT,
            code TEXT NOT NULL DEFAULT '',
            nom TEXT NOT NULL DEFAULT '',
            methode_id TEXT,
            critere_F TEXT DEFAULT '',
            critere_A TEXT DEFAULT '',
            critere_E TEXT DEFAULT ''
        );

        -- Paquet
        CREATE TABLE paquet_definitions (
            nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
            corps TEXT, corps_fin TEXT, texte_complet TEXT,
            fichier_source TEXT, ligne_debut INTEGER,
            macros_appelees TEXT, environnements_utilises TEXT,
            statut_rendu_atome TEXT, contenu_atome TEXT
        );
        CREATE TABLE paquet_requirepackage (
            fichier_source TEXT NOT NULL,
            ordre INTEGER NOT NULL,
            nom TEXT NOT NULL,
            options TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (fichier_source, ordre)
        );

        -- Peuplement : référentiel N10
        INSERT INTO referentiel_niveaux (id, niveau, version, date_fin)
            VALUES ('ref_n10', 'N10', '2021', NULL);
        INSERT INTO referentiel_themes VALUES
            ('ref_n10', 'A', 'Nombres et Calculs', 'nombres'),
            ('ref_n10', 'D', 'Espace et Géométrie', 'geometrie');
        INSERT INTO referentiel_sequences VALUES
            ('ref_n10', 'S01', 1, 'Représentations d''un nombre', 'A'),
            ('ref_n10', 'S10', 10, 'Triangles', 'D');

        -- Un objectif, pour tester seqObjectifGetNom.
        -- v0.14.7 — Table unique `objectifs` après renommage.
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code)
            VALUES ('sn_n10s01', 'N10', 'S01');
        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
            VALUES ('pt_n10s01_1', 'sn_n10s01', 1);
        INSERT INTO objectifs (id, partie_id, code, nom)
            VALUES ('obj1', 'pt_n10s01_1', '02', 'Utiliser les fractions');

        -- Une notion, pour tester seqConnaissanceGetNom
        INSERT INTO notions (id, niveau, sequence, num_connaissance, titre, corps, fichier)
            VALUES ('no1', 'N10', 'S01', '01', 'Proportion.',
                    'Définition de la proportion.',
                    'N10_S01_Notion_01.tex');

        -- Un exercice, pour les tests de bout en bout
        INSERT INTO exercices (id, niveau, sequence, fichier, titre, serie, num,
                               variables, enonce, corrige)
            VALUES ('ex1', 'N10', 'S01', 'N10S01F01.tex', 'Premier exercice',
                    'fondamental', 1,
                    '',
                    'Calculer $\\seqFrac{1}{2}$.',
                    'Le résultat est $0,5$.');

        -- Une méthode, référençant un objectif via getter CSV
        INSERT INTO methodes (id, niveau, sequence, fichier, titre, corps,
                              num_methode, num_objectif, ordre_sections)
            VALUES ('me1', 'N10', 'S01', 'N10_S01_Methode_01.tex',
                    'Calculer avec des fractions',
                    'Voir méthode \\og \\seqObjectifGetNom{02} \\fg{}',
                    1, '02', 'RE');

        -- v0.7 : sections (modèle universel à 2 niveaux).
        -- no1 : 1 section "Remarques" avec 1 item.
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_no_r', 'notion', 'no1', 'Remarques', 0);
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_no_r0', 'sec_no_r', 0,
                    'La grandeur est un nombre décimal.');

        -- me1 : sections dans l'ordre [Remarques, Exemples] avec respectivement
        -- 1 et 2 items. L'ordre dans la liste « sections » fait office d'ordre
        -- d'affichage (l'ancien ordre_sections='RE' n'est plus piloté par la
        -- colonne mais par la position des sections elles-mêmes).
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_me_r', 'methode', 'me1', 'Remarques', 0);
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_me_r0', 'sec_me_r', 0,
                    'Penser à simplifier la fraction si possible.');
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_me_e', 'methode', 'me1', 'Exemples', 1);
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_me_e0', 'sec_me_e', 0,
                    '$\\seqFrac{3}{10} = 0{,}3$');
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_me_e1', 'sec_me_e', 1,
                    '$\\seqFrac{7}{100} = 0{,}07$');

        -- v0.11.1 — fi1 : fiche de résumé avec 2 sections (Définition,
        -- Propriété) — couvre le cas usuel d'une fiche multi-zones avec
        -- des \\acompleter dans le contenu (test du préambule).
        INSERT INTO fiches_resume (id, niveau, sequence, fichier, titre)
            VALUES ('fi1', 'N10', 'S01', 'N10_S01_Fiche_01.tex',
                    'Calculer une proportion.');
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_fi_d', 'fiche_resume', 'fi1', 'Définition', 0);
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_fi_d0', 'sec_fi_d', 0,
                    'Une proportion est \\acompleter{une fraction}.');
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_fi_p', 'fiche_resume', 'fi1', 'Propriété', 1);
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_fi_p0', 'sec_fi_p', 0,
                    'On a $a/b = \\acompleter{c/d}$.');

        -- v0.11.1.x — fi2 : fiche SANS titre, mais liée à un objectif.
        -- Sert à tester le fallback titre = nom de l'objectif.
        INSERT INTO objectifs (id, nom)
            VALUES ('obj_fi2', 'Calculer une fréquence');
        INSERT INTO fiches_resume (id, niveau, sequence, fichier, titre, objectif_id)
            VALUES ('fi2', 'N10', 'S01', 'N10_S01_Fiche_02.tex',
                    '', 'obj_fi2');
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_fi2_d', 'fiche_resume', 'fi2', 'Définition', 0);
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_fi2_d0', 'sec_fi2_d', 0,
                    'La fréquence est le rapport \\acompleter{n/N}.');

        -- v0.11.1.x — fi3 : fiche SANS titre, SANS objectif lié.
        -- Le titre généré doit rester vide (ni titre, ni fallback).
        INSERT INTO fiches_resume (id, niveau, sequence, fichier, titre)
            VALUES ('fi3', 'N10', 'S01', 'N10_S01_Fiche_03.tex', '');
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_fi3_d', 'fiche_resume', 'fi3', 'Définition', 0);
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_fi3_d0', 'sec_fi3_d', 0,
                    'Un nombre décimal a une partie entière et une partie décimale.');

        -- Règles de paquet : une `reecrit`, une `reutilise`
        INSERT INTO paquet_definitions
            VALUES ('\\seqCorrige', 'command', '[1]', '...', '', '', 'core.sty', 1,
                    '[]', '[]', 'reecrit',
                    '\\renewcommand{\\seqCorrige}[1]{CORRIGE: #1}');
        INSERT INTO paquet_definitions
            VALUES ('\\seqFrac', 'command', '[2]', '\\dfrac{#1}{#2}', '',
                    '', 'core.sty', 1, '[]', '[]', 'reutilise', '');

        -- Paquets TeX déjà chargés par seqenseigne (pour detecter_paquets_tex_manquants)
        INSERT INTO paquet_requirepackage VALUES
            ('seqenseigne-core.sty', 0, 'amsmath', ''),
            ('seqenseigne-core.sty', 1, 'tikz', ''),
            ('seqenseigne-core.sty', 2, 'booktabs', ''),
            ('seqenseigne-core.sty', 3, 'tabularray', ''),
            ('seqenseigne-core.sty', 4, 'multicol', ''),
            ('seqenseigne-core.sty', 5, 'datatool', ''),
            ('seqenseigne-theme.sty', 0, 'pifont', ''),
            ('seqenseigne-theme.sty', 1, 'enumitem', '');
    """)
    conn.commit()
    yield conn
    conn.close()


# ── Chargement des atomes ─────────────────────────────────────────────────────

class TestChargerAtome:

    def test_exercice(self, db_peuplee):
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        assert atome.type_atome == 'exercice'
        assert atome.niveau == 'N10'
        assert atome.sequence == 'S01'
        assert atome.serie == 'fondamental'
        assert 'seqFrac' in atome.corps

    def test_notion(self, db_peuplee):
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        assert atome.type_atome == 'notion'
        assert atome.titre == 'Proportion.'
        assert atome.num_connaissance == '01'

    def test_methode(self, db_peuplee):
        atome = charger_atome(db_peuplee, 'methode', 'me1')
        assert atome.type_atome == 'methode'
        assert atome.num_objectif == '02'
        assert atome.num == 1

    def test_fiche(self, db_peuplee):
        # v0.11.1 — chargement d'une fiche : titre + scope + sections.
        atome = charger_atome(db_peuplee, 'fiche', 'fi1')
        assert atome.type_atome == 'fiche'
        assert atome.niveau == 'N10'
        assert atome.sequence == 'S01'
        assert atome.titre == 'Calculer une proportion.'
        # 2 sections dans l'ordre stocké en BDD (ordre 0, 1)
        assert len(atome.sections) == 2
        assert atome.sections[0]['titre'] == 'Définition'
        assert atome.sections[1]['titre'] == 'Propriété'
        # Les items contiennent bien le LaTeX brut, y compris \acompleter.
        assert '\\acompleter' in atome.sections[0]['items'][0]

    def test_type_inconnu(self, db_peuplee):
        with pytest.raises(ValueError, match='type_atome'):
            charger_atome(db_peuplee, 'inconnu', 'x')

    def test_atome_inexistant(self, db_peuplee):
        with pytest.raises(LookupError):
            charger_atome(db_peuplee, 'exercice', 'pas_existant')


# ── Détection des options du paquet ──────────────────────────────────────────

class TestDetecterOptions:

    def test_exercice_sans_option(self, db_peuplee):
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        # Utilise seulement \seqFrac → aucune option
        assert detecter_options_paquet(db_peuplee, atome) == []

    def test_exercice_avec_tkz(self, db_peuplee):
        db_peuplee.execute("""
            UPDATE exercices SET enonce = 'Construire \\tkzDefPoint(0,0){A}'
            WHERE id = 'ex1'
        """)
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        opts = detecter_options_paquet(db_peuplee, atome)
        assert 'geometrie' in opts

    def test_exercice_avec_scratch(self, db_peuplee):
        db_peuplee.execute("""
            UPDATE exercices SET enonce = 'Voir \\greenflag et \\blockmove{10}'
            WHERE id = 'ex1'
        """)
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        opts = detecter_options_paquet(db_peuplee, atome)
        assert 'scratch' in opts

    def test_exercice_avec_les_deux(self, db_peuplee):
        db_peuplee.execute("""
            UPDATE exercices SET enonce = '\\tkzDefPoint(0,0){A} et \\greenflag'
            WHERE id = 'ex1'
        """)
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        opts = detecter_options_paquet(db_peuplee, atome)
        assert 'geometrie' in opts
        assert 'scratch' in opts


# ── Détection des paquets TeX manquants ──────────────────────────────────────

class TestDetecterPaquetsTexManquants:

    def test_aucun_paquet_si_macros_deja_dispo(self, db_peuplee):
        """Un atome qui n'utilise que \\seqFrac (défini par seqenseigne)
        ne nécessite aucun \\usepackage supplémentaire."""
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        assert detecter_paquets_tex_manquants(db_peuplee, atome) == []

    def test_siunitx_detecte(self, db_peuplee):
        """\\num{123} déclenche le chargement de siunitx (chez l'utilisateur
        seqenseigne c'est siunitx qui fournit \\num, pas numprint)."""
        db_peuplee.execute("""
            UPDATE exercices SET enonce = 'Prix : \\num{1250} euros'
            WHERE id = 'ex1'
        """)
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        manquants = detecter_paquets_tex_manquants(db_peuplee, atome)
        assert 'siunitx' in manquants
        # Et pas numprint, justement
        assert 'numprint' not in manquants

    def test_numprint_distinct_de_siunitx(self, db_peuplee):
        """\\numprint (macro spécifique) → numprint, distinct de \\num → siunitx."""
        db_peuplee.execute("""
            UPDATE exercices SET enonce = 'valeur \\numprint{3.14}'
            WHERE id = 'ex1'
        """)
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        manquants = detecter_paquets_tex_manquants(db_peuplee, atome)
        assert 'numprint' in manquants

    def test_xlop_detecte(self, db_peuplee):
        """\\opidiv déclenche le chargement de xlop."""
        db_peuplee.execute("""
            UPDATE exercices SET enonce = '\\opidiv{100}{7}'
            WHERE id = 'ex1'
        """)
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        assert 'xlop' in detecter_paquets_tex_manquants(db_peuplee, atome)

    def test_paquets_deja_charges_exclus(self, db_peuplee):
        """\\num (siunitx) + macro amsmath : amsmath est déjà chargé par
        seqenseigne, donc pas dans la liste des manquants."""
        db_peuplee.execute("""
            UPDATE exercices SET enonce = '\\num{3} et \\cfrac{1}{2}'
            WHERE id = 'ex1'
        """)
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        manquants = detecter_paquets_tex_manquants(db_peuplee, atome)
        assert 'siunitx' in manquants
        assert 'amsmath' not in manquants   # déjà chargé

    def test_tkz_exclu_car_option_geometrie(self, db_peuplee):
        """tkz-euclide est géré par l'option [geometrie], pas un \\usepackage
        à ajouter."""
        db_peuplee.execute("""
            UPDATE exercices SET enonce = '\\tkzDefPoint(0,0){A}'
            WHERE id = 'ex1'
        """)
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        assert 'tkz-euclide' not in detecter_paquets_tex_manquants(db_peuplee, atome)

    def test_pseudo_paquets_filtres(self, db_peuplee):
        """Les étiquettes comme 'tex-primitive' ne doivent jamais apparaître
        comme paquets à charger, même si l'atome utilise les macros concernées."""
        # Les primitives n'ont pas de macro courante qui map vers tex-primitive,
        # mais on vérifie le cas limite du filtre ensembliste.
        db_peuplee.execute("""
            UPDATE exercices SET enonce = '\\linewidth et \\textwidth'
            WHERE id = 'ex1'
        """)
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        manquants = detecter_paquets_tex_manquants(db_peuplee, atome)
        assert 'tex-primitive' not in manquants
        assert 'babel-french' not in manquants

    def test_ordre_deterministe(self, db_peuplee):
        """La liste retournée est triée (pour que les .tex générés soient
        reproductibles à hash près)."""
        db_peuplee.execute("""
            UPDATE exercices SET enonce = '\\opidiv{1}{2} \\num{3} \\cancel{x}'
            WHERE id = 'ex1'
        """)
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        manquants = detecter_paquets_tex_manquants(db_peuplee, atome)
        assert manquants == sorted(manquants)


# ── Résolution du thème ──────────────────────────────────────────────────────

class TestResoudreTheme:

    def test_theme_connu(self, db_peuplee):
        assert resoudre_theme(db_peuplee, 'N10', 'S01') == 'nombres'
        assert resoudre_theme(db_peuplee, 'N10', 'S10') == 'geometrie'

    def test_sequence_inconnue(self, db_peuplee):
        assert resoudre_theme(db_peuplee, 'N10', 'S99') == 'gris'

    def test_niveau_inconnu(self, db_peuplee):
        assert resoudre_theme(db_peuplee, 'N99', 'S01') == 'gris'

    def test_theme_vide(self, db_peuplee):
        # Séquence existante mais sans couleur de thème
        db_peuplee.execute(
            "UPDATE referentiel_themes SET couleur = '' WHERE code = 'A'"
        )
        assert resoudre_theme(db_peuplee, 'N10', 'S01') == 'gris'


# ── Résolution des macros CSV ────────────────────────────────────────────────

class TestResoudreMacrosCsv:

    def test_objectif_get_nom(self, db_peuplee):
        texte = r'Voir \seqObjectifGetNom{02} dans la séquence.'
        r = resoudre_macros_csv(db_peuplee, texte, 'N10', 'S01')
        assert 'Utiliser les fractions' in r
        assert 'seqObjectifGetNom' not in r

    def test_objectif_inconnu(self, db_peuplee):
        texte = r'\seqObjectifGetNom{99}'
        r = resoudre_macros_csv(db_peuplee, texte, 'N10', 'S01')
        assert '[OBJ-99]' in r

    def test_sequence_get_nom(self, db_peuplee):
        texte = r'Dans \seqSequenceGetNom{S10}.'
        r = resoudre_macros_csv(db_peuplee, texte, 'N10', 'S01')
        assert 'Triangles' in r

    def test_sequence_get_nom_argument_vide(self, db_peuplee):
        r"""\seqSequenceGetNom{} → utilise la séquence courante."""
        texte = r'\seqSequenceGetNom{}'
        r = resoudre_macros_csv(db_peuplee, texte, 'N10', 'S01')
        assert "Représentations d'un nombre" in r

    def test_niveau_get_nom_court(self, db_peuplee):
        texte = r'\seqNiveauGetNomCourt{N10}'
        r = resoudre_macros_csv(db_peuplee, texte, 'N10', 'S01')
        assert r == '5e'

    def test_connaissance_get_nom(self, db_peuplee):
        texte = r'\seqConnaissanceGetNom{01}'
        r = resoudre_macros_csv(db_peuplee, texte, 'N10', 'S01')
        assert r == 'Proportion.'

    def test_texte_sans_getter(self, db_peuplee):
        texte = r'Pas de getter ici, juste \seqFrac{1}{2}.'
        r = resoudre_macros_csv(db_peuplee, texte, 'N10', 'S01')
        assert r == texte   # inchangé

    def test_texte_vide(self, db_peuplee):
        assert resoudre_macros_csv(db_peuplee, '', 'N10', 'S01') == ''
        assert resoudre_macros_csv(db_peuplee, None, 'N10', 'S01') is None


# ── v0.13.4.1 — Sélection déterministe de référentiel ────────────────────────

class TestRefSelectionDeterministe:
    """v0.13.4.1 — Quand plusieurs référentiels existent pour un même
    niveau, les requêtes de résolution doivent toujours en sélectionner
    UN, déterministe, selon le tri :
      etat préféré : verrouille > fige > valide > en_cours > autres
      puis version DESC.
    """

    def _db_multi_ref(self, refs):
        """Crée une BDD minimale avec N référentiels du même niveau N10
        et 1 séquence S01 dans chacun, avec un nom différent par
        référentiel pour identifier facilement lequel est sélectionné.

        `refs` = liste de tuples (id, version, etat, date_fin).
        Le nom de la séquence sera "Nom_<id>" pour traçabilité.
        """
        conn = sqlite3.connect(':memory:')
        conn.executescript("""
            CREATE TABLE referentiel_niveaux (
                id TEXT PRIMARY KEY, niveau TEXT NOT NULL,
                version TEXT NOT NULL, date_debut TEXT, date_fin TEXT,
                description TEXT DEFAULT '', etat TEXT DEFAULT 'en_cours'
            );
            CREATE TABLE referentiel_themes (
                referentiel_id TEXT NOT NULL, code TEXT NOT NULL,
                nom TEXT NOT NULL, couleur TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (referentiel_id, code)
            );
            CREATE TABLE referentiel_sequences (
                referentiel_id TEXT NOT NULL, code TEXT NOT NULL,
                numero INTEGER NOT NULL, nom TEXT NOT NULL,
                theme_code TEXT, PRIMARY KEY (referentiel_id, code)
            );
        """)
        for ref_id, version, etat, date_fin in refs:
            conn.execute(
                "INSERT INTO referentiel_niveaux "
                "(id, niveau, version, etat, date_fin) VALUES (?,?,?,?,?)",
                (ref_id, 'N10', version, etat, date_fin),
            )
            conn.execute(
                "INSERT INTO referentiel_themes VALUES (?, ?, ?, ?)",
                (ref_id, 'A', 'Nombres et Calculs', 'nombres'),
            )
            conn.execute(
                "INSERT INTO referentiel_sequences VALUES (?, ?, ?, ?, ?)",
                (ref_id, 'S01', 1, f'Nom_{ref_id}', 'A'),
            )
        return conn

    # ── Préférence par état ───────────────────────────────────────────────

    def test_verrouille_prefere_a_valide(self):
        """Avec 2 ref de même version, on prend verrouille avant valide."""
        conn = self._db_multi_ref([
            ('ref_v', '2024', 'valide',     None),
            ('ref_w', '2024', 'verrouille', None),
        ])
        r = resoudre_macros_csv(conn, r'\seqSequenceGetNom{S01}', 'N10', 'S01')
        assert 'Nom_ref_w' in r  # verrouille gagne

    def test_verrouille_prefere_a_valide_v2(self):
        """v0.15.3 — Avec 2 ref de même version, verrouille > valide.
        (Anciennement nommé test_fige_prefere_a_valide quand `fige` était
        un état distinct.)"""
        conn = self._db_multi_ref([
            ('ref_v', '2024', 'valide', None),
            ('ref_f', '2024', 'verrouille',   None),
        ])
        r = resoudre_macros_csv(conn, r'\seqSequenceGetNom{S01}', 'N10', 'S01')
        assert 'Nom_ref_f' in r  # verrouille gagne

    def test_utilise_prefere_a_verrouille(self):
        """v0.15.3 — utilise > verrouille (utilisé en priorité)."""
        conn = self._db_multi_ref([
            ('ref_v', '2024', 'verrouille', None),
            ('ref_u', '2024', 'utilise',    None),
        ])
        r = resoudre_macros_csv(conn, r'\seqSequenceGetNom{S01}', 'N10', 'S01')
        assert 'Nom_ref_u' in r  # utilise gagne

    # ── Tri par version à état égal ───────────────────────────────────────

    def test_version_decroissante_a_etat_egal(self):
        """Deux ref verrouille, on prend la version la plus récente."""
        conn = self._db_multi_ref([
            ('ref_2021', '2021', 'verrouille', None),
            ('ref_2024', '2024', 'verrouille', None),
        ])
        r = resoudre_macros_csv(conn, r'\seqSequenceGetNom{S01}', 'N10', 'S01')
        assert 'Nom_ref_2024' in r

    def test_etat_prime_sur_version(self):
        """Un verrouille v2021 gagne contre un valide v2024 (état prime)."""
        conn = self._db_multi_ref([
            ('ref_2024_v', '2024', 'valide',     None),
            ('ref_2021_w', '2021', 'verrouille', None),
        ])
        r = resoudre_macros_csv(conn, r'\seqSequenceGetNom{S01}', 'N10', 'S01')
        assert 'Nom_ref_2021_w' in r  # verrouille (même plus ancien) gagne

    # ── Cas réaliste : base de Laurent post-migration v0.13.4.1 ───────────

    def test_cas_realiste_post_migration(self):
        """Reproduit le cas après migration v0.13.4.1 : 4 référentiels
        verrouille avec date_fin posée sur les 3 plus anciens, le plus
        récent gardant date_fin = NULL. Le tri doit prendre le plus
        récent (date_fin = NULL n'est plus une condition mais reste
        cohérent avec le tri par version).
        """
        conn = self._db_multi_ref([
            ('N10_v2021', '2021', 'verrouille', '2022-09-01'),
            ('N10_v2022', '2022', 'verrouille', '2023-09-01'),
            ('N10_v2023', '2023', 'verrouille', '2024-09-01'),
            ('N10_v2024', '2024', 'verrouille', None),  # courant
        ])
        r = resoudre_macros_csv(conn, r'\seqSequenceGetNom{S01}', 'N10', 'S01')
        assert 'Nom_N10_v2024' in r  # le plus récent

    def test_resoudre_theme_avec_plusieurs_ref(self):
        """resoudre_theme bénéficie aussi du tri déterministe."""
        conn = self._db_multi_ref([
            ('ref_2021', '2021', 'verrouille', '2022-09-01'),
            ('ref_2024', '2024', 'verrouille', None),
        ])
        # Les 2 référentiels ont le même thème pour S01 ('nombres')
        # donc le résultat est identique. Test surtout : pas d'erreur,
        # pas de comportement aléatoire.
        assert resoudre_theme(conn, 'N10', 'S01') == 'nombres'

    # ── Cas dégénéré : aucun référentiel ──────────────────────────────────

    def test_pas_de_ref_pour_le_niveau(self):
        """Si aucun référentiel pour le niveau, retour du placeholder."""
        conn = self._db_multi_ref([
            ('ref_2024', '2024', 'verrouille', None),
        ])
        # On demande N12 (absent)
        r = resoudre_macros_csv(conn, r'\seqSequenceGetNom{S01}', 'N12', 'S01')
        assert '[SEQ-S01]' in r


# ── Collecte des réécritures ─────────────────────────────────────────────────

class TestCollecterReecritures:

    def test_recupere_contenus_reecrits(self, db_peuplee):
        r = collecter_reecritures(db_peuplee, set())
        assert len(r) >= 1
        assert any('CORRIGE:' in c for c in r)

    def test_ignore_les_reutilise(self, db_peuplee):
        r = collecter_reecritures(db_peuplee, set())
        # \seqFrac est 'reutilise' avec contenu_atome vide → pas dans la liste
        assert not any('seqFrac' in c and 'dfrac' in c for c in r)


# ── Génération du corps selon type ───────────────────────────────────────────

class TestGenererCorps:

    def test_corps_exercice_a_seqExercice(self, db_peuplee):
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        tex = generer_corps_exercice(atome)
        assert r'\begin{seqExercice}' in tex
        assert r'\end{seqExercice}' in tex
        assert 'seqFrac' in tex

    def test_corps_exercice_avec_corrige(self, db_peuplee):
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        tex = generer_corps_exercice(atome)
        assert r'\seqCorrige' in tex
        assert '0,5' in tex

    def test_corps_exercice_sans_variables(self, db_peuplee):
        """Si variables est vide, pas de section 'Variables'."""
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        assert atome.variables == ''
        tex = generer_corps_exercice(atome)
        assert 'Variables' not in tex

    def test_corps_exercice_dans_seqSerieExos(self, db_peuplee):
        """L'exercice est encapsulé dans \\begin{seqSerieExos}{N} ...
        \\end{seqSerieExos} pour obtenir la mise en page livret à 2 colonnes."""
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        tex = generer_corps_exercice(atome)
        assert r'\begin{seqSerieExos}' in tex
        assert r'\end{seqSerieExos}' in tex
        # seqSerieExos doit encapsuler seqExercice (ouvert avant, fermé après)
        idx_serie_ouvert = tex.find(r'\begin{seqSerieExos}')
        idx_exo_ouvert   = tex.find(r'\begin{seqExercice}')
        idx_exo_ferme    = tex.find(r'\end{seqExercice}')
        idx_serie_ferme  = tex.find(r'\end{seqSerieExos}')
        assert idx_serie_ouvert < idx_exo_ouvert < idx_exo_ferme < idx_serie_ferme

    def test_corps_exercice_numero_serie_correct(self, db_peuplee):
        """serie='fondamental' → seqSerieExos{1}, 'avancé' → {2}, 'exploration' → {3}."""
        # fondamental (valeur par défaut dans la fixture)
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        tex = generer_corps_exercice(atome)
        assert r'\begin{seqSerieExos}{1}' in tex

        # avancé
        db_peuplee.execute("UPDATE exercices SET serie = 'avancé' WHERE id = 'ex1'")
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        tex = generer_corps_exercice(atome)
        assert r'\begin{seqSerieExos}{2}' in tex

        # exploration
        db_peuplee.execute("UPDATE exercices SET serie = 'exploration' WHERE id = 'ex1'")
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        tex = generer_corps_exercice(atome)
        assert r'\begin{seqSerieExos}{3}' in tex

    def test_corps_exercice_init_et_affiche_corriges(self, db_peuplee):
        """Avant la série, \\seqInitCorriges et \\seqInitAnnexes. Après la
        série, \\seqAfficheAnnexes puis \\seqAfficheCorriges pour que le
        corrigé apparaisse en fin de document, en une colonne, fond blanc."""
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        tex = generer_corps_exercice(atome)

        idx_init_corr = tex.find(r'\seqInitCorriges')
        idx_init_ann  = tex.find(r'\seqInitAnnexes')
        idx_serie_ouv = tex.find(r'\begin{seqSerieExos}')
        idx_serie_fin = tex.find(r'\end{seqSerieExos}')
        idx_aff_ann   = tex.find(r'\seqAfficheAnnexes')
        idx_aff_corr  = tex.find(r'\seqAfficheCorriges')

        # Ordre : init avant la série, affichages après
        assert 0 <= idx_init_corr < idx_serie_ouv
        assert 0 <= idx_init_ann  < idx_serie_ouv
        assert idx_serie_fin < idx_aff_ann  < idx_aff_corr

    def test_corps_exercice_force_corriges_oui(self, db_peuplee):
        """Sans \\renewcommand{\\seqCorrigesExos}{oui}, le paquet n'écrit
        pas les corrigés dans CorrList.tex pour les séries 2 (avancé) et
        3 (exploration) : voir core.sty lignes 838 et 870.

        Comme en mode atomique on n'appelle pas \\seqTitreLivret (qui gère
        cette option via son argument [corriges=oui]), on doit forcer le
        flag à la main."""
        # Atome en série avancée (2) : sans le renewcommand, rien n'écrirait
        db_peuplee.execute("UPDATE exercices SET serie = 'avancé' WHERE id = 'ex1'")
        atome = charger_atome(db_peuplee, 'exercice', 'ex1')
        tex = generer_corps_exercice(atome)
        assert r'\renewcommand{\seqCorrigesExos}{oui}' in tex
        # Doit être AVANT le \begin{seqSerieExos} pour que la série en tienne compte
        idx_renewcmd = tex.find(r'\renewcommand{\seqCorrigesExos}{oui}')
        idx_serie    = tex.find(r'\begin{seqSerieExos}')
        assert idx_renewcmd < idx_serie

    def test_corps_notion(self, db_peuplee):
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        tex = generer_corps_notion(atome)
        assert r'\begin{seqNotion}' in tex
        assert 'Proportion.' in tex

    def test_corps_notion_initialise_compteur(self, db_peuplee):
        """Le compteur doit être mis à num-1 (refstepcounter incrémente)."""
        db_peuplee.execute(
            "UPDATE notions SET num_connaissance = '03' WHERE id = 'no1'"
        )
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        tex = generer_corps_notion(atome)
        assert r'\setcounter{NotionNum}{2}' in tex

    def test_corps_methode(self, db_peuplee):
        atome = charger_atome(db_peuplee, 'methode', 'me1')
        tex = generer_corps_methode(atome)
        assert r'\begin{seqMethode}' in tex
        assert 'Calculer avec des fractions' in tex

    def test_corps_methode_initialise_compteur(self, db_peuplee):
        atome = charger_atome(db_peuplee, 'methode', 'me1')
        tex = generer_corps_methode(atome)
        assert r'\setcounter{MethodeNum}{0}' in tex

    def test_corps_notion_avec_remarque(self, db_peuplee):
        """no1 a 1 section "Remarques" avec 1 item dans la fixture : elle
        doit être rendue entre la fermeture du 2e argument de seqNotion et
        \\end{seqNotion}, avec le titre 'Remarques' au pluriel français."""
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        tex = generer_corps_notion(atome)
        assert r'\underline{Remarques}' in tex
        assert 'La grandeur est un nombre décimal.' in tex
        # La remarque est bien à l'intérieur de l'environnement seqNotion
        idx_remarque = tex.find(r'\underline{Remarques}')
        idx_end_notion = tex.find(r'\end{seqNotion}')
        assert idx_remarque < idx_end_notion

    def test_corps_notion_sans_exemple_pas_de_section_exemple(self, db_peuplee):
        """no1 n'a pas de section Exemples : pas d'\\underline{Exemples}
        dans le rendu."""
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        tex = generer_corps_notion(atome)
        assert r'\underline{Exemples}' not in tex

    def test_corps_methode_avec_exemples_et_remarques(self, db_peuplee):
        """me1 a 2 sections : Remarques (ordre=0) puis Exemples (ordre=1).
        Les remarques apparaissent AVANT les exemples dans le rendu, parce
        que c'est l'ordre des sections en BDD qui pilote l'affichage
        (modèle universel v0.6.4, ordre_sections devenu inopérant)."""
        atome = charger_atome(db_peuplee, 'methode', 'me1')
        tex = generer_corps_methode(atome)
        assert r'\underline{Remarques}' in tex
        assert r'\underline{Exemples}' in tex
        # Les 2 exemples sont présents dans un seqColItem
        assert r'\begin{seqColItem}[nbCols=1]' in tex
        assert r'\seqFrac{3}{10}' in tex
        assert r'\seqFrac{7}{100}' in tex
        # Ordre Remarques avant Exemples (dérivé de atome_sections.ordre)
        idx_remarques = tex.find(r'\underline{Remarques}')
        idx_exemples  = tex.find(r'\underline{Exemples}')
        assert idx_remarques < idx_exemples

    def test_corps_methode_inversion_ordre_sections(self, db_peuplee):
        """v0.6.4+ : l'ordre d'affichage est piloté par atome_sections.ordre.
        Si on inverse les ordres en BDD (Exemples=0, Remarques=1), le
        rendu reflète ce nouvel ordre."""
        db_peuplee.execute(
            "UPDATE atome_sections SET ordre = 1 WHERE id = 'sec_me_r'"
        )
        db_peuplee.execute(
            "UPDATE atome_sections SET ordre = 0 WHERE id = 'sec_me_e'"
        )
        atome = charger_atome(db_peuplee, 'methode', 'me1')
        tex = generer_corps_methode(atome)
        idx_exemples  = tex.find(r'\underline{Exemples}')
        idx_remarques = tex.find(r'\underline{Remarques}')
        assert idx_exemples < idx_remarques

    def test_corps_notion_sans_items_reste_compact(self, db_peuplee):
        """Si la notion n'a aucune section (atome.sections vide), aucune
        section n'est émise (pas de \\underline fantôme, pas de seqColItem
        vide)."""
        # Retirer les sections de no1 (cascade nettoie les items).
        db_peuplee.execute(
            "DELETE FROM atome_sections WHERE entite_id = 'no1'"
        )
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        assert atome.sections == []
        tex = generer_corps_notion(atome)
        assert r'\underline' not in tex
        assert r'\begin{seqColItem}' not in tex

    def test_charger_sections_table_absente_retourne_liste_vide(self, tmp_path):
        """Si la table atome_sections n'existe pas (cas BDD ancienne ou
        partielle), _charger_sections doit lever sqlite3.OperationalError
        — c'est un comportement attendu, signalant que le schéma est
        incomplet. _charger_items_texte (vestige) renvoie quant à lui
        toujours ([], []) sans toucher à la base."""
        from services.latex_rendu_atome import (
            _charger_sections, _charger_items_texte,
        )
        import sqlite3
        conn = sqlite3.connect(':memory:')
        conn.executescript("""
            CREATE TABLE notions (id TEXT PRIMARY KEY);
            INSERT INTO notions VALUES ('x');
        """)
        # Vestige : ne doit rien lever, renvoie ([], []).
        exemples, remarques = _charger_items_texte(conn, 'notion', 'x')
        assert exemples == []
        assert remarques == []
        # Le nouveau loader signale l'absence de la table par une erreur
        # SQLite plutôt qu'un retour vide silencieux.
        with pytest.raises(sqlite3.OperationalError):
            _charger_sections(conn, 'notion', 'x')

    def test_charger_sections_avec_table_vide(self, tmp_path):
        """Avec les tables présentes mais sans ligne pour cette entité,
        _charger_sections renvoie une liste vide."""
        from services.latex_rendu_atome import _charger_sections
        import sqlite3
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE notions (id TEXT PRIMARY KEY);
            INSERT INTO notions VALUES ('x');
            CREATE TABLE atome_sections (
                id TEXT PRIMARY KEY, entite_type TEXT, entite_id TEXT,
                titre TEXT, ordre INTEGER DEFAULT 0
            );
            CREATE TABLE atome_section_items (
                id TEXT PRIMARY KEY, section_id TEXT, ordre INTEGER, corps TEXT
            );
        """)
        sections = _charger_sections(conn, 'notion', 'x')
        assert sections == []


# ── v0.11.1 — Fiche de résumé : corps + e2e ──────────────────────────────────

class TestFicheV111:
    """v0.11.1 — Génération du corps LaTeX pour une fiche de résumé,
    et test de bout-en-bout via generer_tex_atome (sans pdflatex).

    Trois axes :
    - structure du corps (titre via \\seqTitreSection, sections via
      seqBoiteContenuFlashcard, fill final);
    - pipeline complet (l'atome 'fiche' traverse generer_tex_atome
      sans erreur, le préambule est construit, \\acompleter est défini);
    - cas dégénérés (fiche sans sections, section sans titre, etc.).
    """

    def test_corps_structure_titre_seqtitresection(self, db_peuplee):
        atome = charger_atome(db_peuplee, 'fiche', 'fi1')
        corps = generer_corps_fiche(atome)
        # Le titre est posé via \seqTitreSection (pas via seqBoiteTitreFlashcard
        # qui dépendrait de la machinerie .dbtex — choix Q1 du cadrage).
        assert '\\seqTitreSection{Calculer une proportion.}' in corps

    def test_corps_sections_boitecontenuflashcard(self, db_peuplee):
        atome = charger_atome(db_peuplee, 'fiche', 'fi1')
        corps = generer_corps_fiche(atome)
        # Chaque section : ouverture avec [titre=...] et fermeture.
        assert '\\begin{seqBoiteContenuFlashcard}[titre=Définition]' in corps
        assert '\\begin{seqBoiteContenuFlashcard}[titre=Propriété]' in corps
        # Le nombre de \end{...} matche le nombre de \begin{...}
        assert corps.count('\\begin{seqBoiteContenuFlashcard}') == \
               corps.count('\\end{seqBoiteContenuFlashcard}')

    def test_corps_items_inseres_avec_acompleter(self, db_peuplee):
        atome = charger_atome(db_peuplee, 'fiche', 'fi1')
        corps = generer_corps_fiche(atome)
        # Le contenu LaTeX brut est inséré tel-quel, y compris \acompleter.
        assert '\\acompleter{une fraction}' in corps
        assert '\\acompleter{c/d}' in corps

    def test_corps_fill_final_present(self, db_peuplee):
        # Q3 du cadrage : le \seqBoiteFillContenuFlashcard final est ajouté
        # automatiquement, même quand la fiche est non-vide.
        atome = charger_atome(db_peuplee, 'fiche', 'fi1')
        corps = generer_corps_fiche(atome)
        assert ('\\begin{seqBoiteFillContenuFlashcard}'
                '\\end{seqBoiteFillContenuFlashcard}') in corps

    def test_corps_ordre_des_sections_respecte(self, db_peuplee):
        # Les sections sortent dans l'ordre stocké en BDD (champ ordre).
        atome = charger_atome(db_peuplee, 'fiche', 'fi1')
        corps = generer_corps_fiche(atome)
        i_def = corps.find('titre=Définition]')
        i_prop = corps.find('titre=Propriété]')
        assert 0 < i_def < i_prop

    def test_corps_section_sans_titre_genere_boite_anonyme(self):
        # Une section sans titre mais avec un item produit une boîte
        # `\begin{seqBoiteContenuFlashcard}` (sans clé titre=).
        atome = Atome(
            id='x', type_atome='fiche',
            niveau='N10', sequence='S01', fichier='',
            titre='Test',
            sections=[{'titre': '', 'items': ['contenu libre']}],
        )
        corps = generer_corps_fiche(atome)
        assert '\\begin{seqBoiteContenuFlashcard}\n' in corps  # sans crochets
        assert '\\begin{seqBoiteContenuFlashcard}[' not in corps

    def test_corps_section_completement_vide_ignoree(self):
        # Une section sans titre ET sans item est ignorée.
        atome = Atome(
            id='x', type_atome='fiche',
            niveau='N10', sequence='S01', fichier='',
            titre='Test',
            sections=[{'titre': '', 'items': []}],
        )
        corps = generer_corps_fiche(atome)
        # Pas de seqBoiteContenuFlashcard tout court (que le fill final).
        assert '\\begin{seqBoiteContenuFlashcard}' not in corps
        # Mais le fill est toujours là.
        assert '\\begin{seqBoiteFillContenuFlashcard}' in corps

    def test_corps_fiche_sans_sections_donne_juste_titre_et_fill(self):
        atome = Atome(
            id='x', type_atome='fiche',
            niveau='N10', sequence='S01', fichier='',
            titre='Vide', sections=[],
        )
        corps = generer_corps_fiche(atome)
        assert '\\seqTitreSection{Vide}' in corps
        assert '\\begin{seqBoiteFillContenuFlashcard}' in corps
        assert '\\begin{seqBoiteContenuFlashcard}' not in corps

    def test_dispatcher_genere_corps_fiche(self, db_peuplee):
        # generer_corps() (le dispatcher) reconnaît le type 'fiche'.
        from services.latex_rendu_atome import generer_corps
        atome = charger_atome(db_peuplee, 'fiche', 'fi1')
        corps = generer_corps(atome)
        # Doit produire la même chose que generer_corps_fiche directement.
        assert corps == generer_corps_fiche(atome)

    def test_pipeline_e2e_genere_tex_atome(self, db_peuplee):
        # generer_tex_atome('fiche', ...) produit un .tex complet.
        tex = generer_tex_atome(db_peuplee, 'fiche', 'fi1')
        # Présence des éléments structurants attendus dans le rendu.
        assert r'\documentclass[11pt,a4paper]{article}' in tex
        assert r'\begin{document}' in tex
        assert r'\end{document}' in tex
        # Le corps fiche est bien là.
        assert r'\seqTitreSection{Calculer une proportion.}' in tex
        assert '\\begin{seqBoiteContenuFlashcard}[titre=Définition]' in tex
        # Le préambule fournit \acompleter (Q6=b : commun à tous les types).
        assert r'\providecommand{\acompleter}' in tex
        # Le thème de la séquence est correctement résolu (S01 → 'nombres').
        assert r'\seqSetColorsTheme{nombres}' in tex
        # Niveau et séquence posés.
        assert r'\seqSetCodeNiveau{N10}' in tex
        assert r'\seqSetCodeSequence{S01}' in tex


class TestFicheFallbackTitre:
    """v0.11.1.x — Quand le titre d'une fiche est vide, on utilise le nom
    de l'objectif lié comme titre LaTeX. Si pas d'objectif lié, le titre
    reste vide (l'utilisateur peut créer une fiche sans objectif pendant
    l'édition).
    """

    def test_titre_explicite_a_priorite(self, db_peuplee):
        """Si le titre est rempli, c'est lui qui est utilisé — pas de
        fallback même si l'objectif lié a un nom."""
        atome = charger_atome(db_peuplee, 'fiche', 'fi1')
        # fi1 a titre='Calculer une proportion.' et pas d'objectif_id
        # (les fixtures fi1 historiques ne référencent pas obj_fi2).
        corps = generer_corps_fiche(atome)
        assert r'\seqTitreSection{Calculer une proportion.}' in corps

    def test_fallback_objectif_quand_titre_vide(self, db_peuplee):
        """Si titre vide ET objectif lié, fallback = nom de l'objectif."""
        atome = charger_atome(db_peuplee, 'fiche', 'fi2')
        # fi2 : titre='', objectif_id='obj_fi2', objectifs.nom='Calculer une fréquence'
        assert atome.titre == ''
        assert atome.objectif_nom == 'Calculer une fréquence'
        corps = generer_corps_fiche(atome)
        assert r'\seqTitreSection{Calculer une fréquence}' in corps

    def test_titre_vide_sans_objectif_reste_vide(self, db_peuplee):
        """Si pas de titre ET pas d'objectif lié, le titre reste vide."""
        atome = charger_atome(db_peuplee, 'fiche', 'fi3')
        # fi3 : titre='', pas d'objectif_id
        assert atome.titre == ''
        assert atome.objectif_nom == ''
        corps = generer_corps_fiche(atome)
        # Le \seqTitreSection est généré quand même mais avec arg vide.
        assert r'\seqTitreSection{}' in corps

    def test_objectif_nom_chargee_pour_fiche_avec_titre(self, db_peuplee):
        """Robustesse : objectif_nom doit être correctement chargé même
        pour les fiches qui ont un titre explicite (LEFT JOIN)."""
        atome = charger_atome(db_peuplee, 'fiche', 'fi1')
        # fi1 n'a pas d'objectif_id → objectif_nom doit être '' (pas null)
        assert atome.objectif_nom == ''


class TestInitAnnexesV091:
    """v0.9.1 — generer_corps_notion et generer_corps_methode encadrent
    désormais le corps par \\seqInitAnnexes / \\seqAfficheAnnexes.

    Ce fix répond au cas concret observé en compilation par lot des
    méthodes (27/04/26) : trois méthodes utilisaient \\seqAnnexe pour
    insérer un algorithme en annexe, ce qui plantait avec « Undefined
    control sequence » sur \\annfile car \\seqInitAnnexes (qui ouvre
    \\newwrite\\annfile) n'était jamais appelé pour les notions et les
    méthodes — seulement pour les exercices (cf. generer_corps_exercice).

    Effet visuel attendu pour les atomes sans \\seqAnnexe : zéro.
    \\seqAfficheAnnexes inclut AnnList.tex uniquement si AnnexeNum > 0
    (cf. seqenseigne-core.dtx).
    """

    def test_notion_emet_seqInitAnnexes(self, db_peuplee):
        """Le corps d'une notion contient \\seqInitAnnexes en début."""
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        tex = generer_corps_notion(atome)
        assert r'\seqInitAnnexes' in tex

    def test_notion_emet_seqAfficheAnnexes(self, db_peuplee):
        """Le corps d'une notion contient \\seqAfficheAnnexes en fin."""
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        tex = generer_corps_notion(atome)
        assert r'\seqAfficheAnnexes' in tex

    def test_notion_init_avant_seqNotion(self, db_peuplee):
        """\\seqInitAnnexes doit être émis AVANT \\begin{seqNotion} pour
        que \\annfile soit ouvert quand \\seqAnnexe est éventuellement
        appelé dans le corps."""
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        tex = generer_corps_notion(atome)
        idx_init = tex.find(r'\seqInitAnnexes')
        idx_seqNotion = tex.find(r'\begin{seqNotion}')
        assert idx_init >= 0 and idx_seqNotion >= 0
        assert idx_init < idx_seqNotion

    def test_notion_affiche_apres_seqNotion(self, db_peuplee):
        """\\seqAfficheAnnexes doit être émis APRÈS \\end{seqNotion}."""
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        tex = generer_corps_notion(atome)
        idx_fin = tex.find(r'\end{seqNotion}')
        idx_aff = tex.find(r'\seqAfficheAnnexes')
        assert idx_fin >= 0 and idx_aff >= 0
        assert idx_fin < idx_aff

    def test_methode_emet_seqInitAnnexes(self, db_peuplee):
        """Le corps d'une méthode contient \\seqInitAnnexes en début."""
        atome = charger_atome(db_peuplee, 'methode', 'me1')
        tex = generer_corps_methode(atome)
        assert r'\seqInitAnnexes' in tex

    def test_methode_emet_seqAfficheAnnexes(self, db_peuplee):
        """Le corps d'une méthode contient \\seqAfficheAnnexes en fin."""
        atome = charger_atome(db_peuplee, 'methode', 'me1')
        tex = generer_corps_methode(atome)
        assert r'\seqAfficheAnnexes' in tex

    def test_methode_init_avant_seqMethode(self, db_peuplee):
        """\\seqInitAnnexes émis AVANT \\begin{seqMethode}."""
        atome = charger_atome(db_peuplee, 'methode', 'me1')
        tex = generer_corps_methode(atome)
        idx_init = tex.find(r'\seqInitAnnexes')
        idx_seqMet = tex.find(r'\begin{seqMethode}')
        assert idx_init >= 0 and idx_seqMet >= 0
        assert idx_init < idx_seqMet

    def test_methode_affiche_apres_seqMethode(self, db_peuplee):
        """\\seqAfficheAnnexes émis APRÈS \\end{seqMethode}."""
        atome = charger_atome(db_peuplee, 'methode', 'me1')
        tex = generer_corps_methode(atome)
        idx_fin = tex.find(r'\end{seqMethode}')
        idx_aff = tex.find(r'\seqAfficheAnnexes')
        assert idx_fin >= 0 and idx_aff >= 0
        assert idx_fin < idx_aff


# ── Génération de bout en bout ────────────────────────────────────────────────

class TestGenererTexAtome:

    def test_exercice_simple_compilable(self, db_peuplee):
        tex = generer_tex_atome(db_peuplee, 'exercice', 'ex1')
        # Structure complète
        assert r'\documentclass' in tex
        assert r'\begin{document}' in tex
        assert r'\end{document}' in tex
        # Plus de \usepackage{seqenseigne} : on inline le paquet (préambule
        # sur mesure). On vérifie en ignorant les commentaires LaTeX qui
        # peuvent citer le paquet à titre explicatif.
        for ligne in tex.split('\n'):
            if ligne.lstrip().startswith('%'):
                continue
            assert 'seqenseigne}' not in ligne, (
                "Le préambule ne doit plus charger seqenseigne via \\usepackage : "
                f"ligne '{ligne}'"
            )
        # Thème appliqué
        assert r'\seqSetColorsTheme{nombres}' in tex
        # Niveau/séquence
        assert r'\seqSetCodeNiveau{N10}' in tex
        assert r'\seqSetCodeSequence{S01}' in tex
        # Corps
        assert r'\begin{seqExercice}' in tex

    def test_exercice_avec_options(self, db_peuplee):
        """Avec une macro tkz-* dans l'énoncé, les paquets tkz-base/tkz-euclide/
        tkz-tab doivent être chargés directement (anciennement via l'option
        [geometrie] passée à \\usepackage{seqenseigne})."""
        db_peuplee.execute("""
            UPDATE exercices SET enonce = '\\tkzDefPoint(0,0){A}'
            WHERE id = 'ex1'
        """)
        tex = generer_tex_atome(db_peuplee, 'exercice', 'ex1')
        # Les 3 paquets tirés par l'option [geometrie] doivent apparaître
        assert r'\usepackage{tkz-base}' in tex
        assert r'\usepackage{tkz-euclide}' in tex
        assert r'\usepackage{tkz-tab}' in tex

    def test_methode_avec_getter_csv_resolu(self, db_peuplee):
        tex = generer_tex_atome(db_peuplee, 'methode', 'me1')
        # \seqObjectifGetNom{02} doit être remplacé par "Utiliser les fractions"
        assert 'seqObjectifGetNom' not in tex
        assert 'Utiliser les fractions' in tex

    def test_reecritures_emises(self, db_peuplee):
        tex = generer_tex_atome(db_peuplee, 'exercice', 'ex1')
        # La règle reecrit pour \seqCorrige doit être émise dans le préambule
        assert 'CORRIGE:' in tex

    def test_seqCreeCompteurs_appele_apres_begin_document(self, db_peuplee):
        """Les compteurs (SerieExosNum, ExoNum, etc.) sont créés par la
        macro \\seqCreeCompteurs du paquet, appelée en temps normal par
        \\seqTitreLivret (marqué 'ignore' en atomique). Il faut donc
        l'appeler explicitement après \\begin{document}, avant le corps
        qui fait des \\setcounter."""
        tex = generer_tex_atome(db_peuplee, 'exercice', 'ex1')
        idx_begin = tex.find(r'\begin{document}')
        idx_cree = tex.find(r'\seqCreeCompteurs')
        idx_corps = tex.find(r'\begin{seqExercice}')
        assert idx_begin < idx_cree < idx_corps, (
            '\\seqCreeCompteurs doit être appelé entre \\begin{document} '
            'et le corps de l\'atome.'
        )

    def test_aucune_regle_reecrit_nutilise_newcommand(self):
        """Garde-fou structurel : aucune règle 'reecrit' ne doit utiliser
        \\newcommand, car les macros cibles sont déjà définies par le paquet
        chargé via \\usepackage{seqenseigne}. Utiliser \\newcommand donnerait
        'Command ... already defined'. C'est \\renewcommand (ou \\def) qui
        est correct."""
        from services.paquet_regles_atome import REGLES, STATUT_REECRIT
        import re

        coupables = []
        for nom, (statut, contenu) in REGLES.items():
            if statut != STATUT_REECRIT or not contenu:
                continue
            # Détecter \newcommand sans précision de la variante ou avec \newcommand{...}
            if re.search(r'\\newcommand\b(?!\*)', contenu):
                # Note : on exclut \newcommand* qui a la même sémantique
                coupables.append(nom)

        assert not coupables, (
            f"Ces règles utilisent \\newcommand alors qu'elles redéfinissent "
            f"des macros du paquet : {coupables}. "
            f"Utiliser \\renewcommand à la place."
        )

    def test_reecritures_entourees_par_makeatletter(self, db_peuplee):
        """Les définitions inlinées dans le préambule contiennent souvent des
        macros avec @ (ex. \\seq@ecrit@corrige@Exo). Le bloc des définitions
        doit donc être enveloppé dans \\makeatletter / \\makeatother pour que
        LaTeX accepte ces noms internes hors d'un .sty."""
        # Forcer la présence d'une macro avec @ dans le préambule en
        # l'injectant comme dépendance du wrapper.
        # On ajoute une macro \seq@test@at puis on fait que \seqCorrige
        # (qui est dans le wrapper exercice) l'appelle, ce qui la tire
        # via la fermeture transitive.
        import json
        db_peuplee.execute("""
            INSERT INTO paquet_definitions
            VALUES ('\\seq@test@at', 'command', '', '...', '',
                    '\\newcommand{\\seq@test@at}{}',
                    'core.sty', 1, '[]', '[]', 'reutilise', '')
        """)
        # Ajouter \seq@test@at aux dépendances de \seqCorrige (déjà dans la BDD)
        db_peuplee.execute(
            "UPDATE paquet_definitions SET macros_appelees = ? WHERE nom = '\\seqCorrige'",
            (json.dumps(['\\seq@test@at']),),
        )
        tex = generer_tex_atome(db_peuplee, 'exercice', 'ex1')
        # Vérifier l'encadrement
        assert r'\makeatletter' in tex
        assert r'\makeatother' in tex
        # La macro avec @ doit être DANS le bloc
        idx_at_letter = tex.find(r'\makeatletter')
        idx_at_other = tex.find(r'\makeatother')
        idx_regle = tex.find(r'\newcommand{\seq@test@at}')
        assert idx_at_letter != -1 and idx_at_other != -1
        assert idx_at_letter < idx_regle < idx_at_other

    def test_pas_d_input_params_sequence(self, db_peuplee, tmp_path):
        """v0.10 : le mécanisme \\input{NXX_SYY_params.tex} a été supprimé.

        Les variables xint et macros locales sont stockées par exercice en
        base, donc l'inclusion d'un fichier de séquence n'a plus de raison
        d'être. On vérifie qu'aucun \\input{...params.tex} n'est émis,
        même quand un tel fichier existe dans racine_sources (cas de
        cohabitation pendant la migration).
        """
        # On crée un faux fichier params à l'emplacement où l'ancien code
        # le cherchait, pour être sûr que le test détecte une éventuelle
        # régression (réintroduction de l'\input).
        p = tmp_path / 'N10' / 'S01'
        p.mkdir(parents=True)
        (p / 'N10_S01_params.tex').write_text('% params', encoding='utf-8')

        tex = generer_tex_atome(db_peuplee, 'exercice', 'ex1',
                                racine_sources=tmp_path)
        # Aucun \input vers un fichier de params de séquence
        assert 'N10_S01_params.tex' not in tex
        assert '_params.tex' not in tex

    def test_hash_stable_quel_que_soit_chemin_absolu(self, db_peuplee, tmp_path):
        """v0.10 : le .tex généré ne doit contenir aucun chemin absolu issu
        de racine_sources, pour que le hash de cache de compilation soit
        identique quel que soit le mapping de la clé USB (D: vs E:).

        Régression : avant v0.10, racine_sources était inscrit dans
        \\input{params_file.as_posix()}, ce qui faisait que monter la clé
        sur D: puis E: invalidait tout le cache de compilation par lot.
        """
        import hashlib
        # Deux racines absolues différentes (simulent D:\... et E:\...)
        r1 = tmp_path / 'mapping_D'
        r2 = tmp_path / 'mapping_E'
        for r in (r1, r2):
            (r / 'N10' / 'S01').mkdir(parents=True)
            (r / 'N10' / 'S01' / 'N10_S01_params.tex').write_text(
                '% params', encoding='utf-8')

        tex1 = generer_tex_atome(db_peuplee, 'exercice', 'ex1',
                                 racine_sources=r1)
        tex2 = generer_tex_atome(db_peuplee, 'exercice', 'ex1',
                                 racine_sources=r2)
        h1 = hashlib.sha256(tex1.encode()).hexdigest()
        h2 = hashlib.sha256(tex2.encode()).hexdigest()
        assert h1 == h2, (
            "Le .tex généré doit avoir le même hash quelle que soit "
            "racine_sources, pour que le cache de compilation reste valide "
            "lorsque la clé USB est mappée sur une lettre différente."
        )

    def test_paquet_externe_emis_si_utilise(self, db_peuplee):
        """\\num{} → \\usepackage{siunitx} émis dans le préambule."""
        db_peuplee.execute("""
            UPDATE exercices SET enonce = 'Prix \\num{1250} euros'
            WHERE id = 'ex1'
        """)
        tex = generer_tex_atome(db_peuplee, 'exercice', 'ex1')
        assert r'\usepackage{siunitx}' in tex
        # L'ajout doit être AVANT \begin{document}
        idx_usepackage = tex.find(r'\usepackage{siunitx}')
        idx_begin = tex.find(r'\begin{document}')
        assert idx_usepackage < idx_begin

    def test_aucun_paquet_externe_si_pas_necessaire(self, db_peuplee):
        """Atome sans macro externe (siunitx, xint…) : pas de \\usepackage
        supplémentaire au-delà du noyau et d'éventuels paquets d'option.

        Anciennement : 1 seul \\usepackage{seqenseigne}.
        Maintenant : N paquets noyau (~24) inlinés dans le préambule mais
        aucun paquet « optionnel » (siunitx, scratch3, tkz-*, etc.)."""
        tex = generer_tex_atome(db_peuplee, 'exercice', 'ex1')
        # Aucun paquet optionnel : pas de section "additionnels"
        assert "additionnels" not in tex
        # Pas de siunitx, scratch3, tkz-* dans le préambule
        for nom in ('siunitx', 'scratch3', 'tkz-base', 'tkz-euclide', 'tkz-tab'):
            assert f'\\usepackage{{{nom}}}' not in tex, (
                f"Paquet optionnel '{nom}' chargé alors qu'il n'est pas nécessaire"
            )


# ── v0.8.2 : détection des paquets dans les sections (régression bug ──────────
#                tkz-base manquant pour notions/méthodes utilisant tkz-euclide)

class TestPaquetsDetectesDansSections:
    """Régression v0.8.2.

    Avant ce correctif, _analyser_paquets_utilises ne regardait que les champs
    scalaires (corps/corrige/variables). Pour les notions et méthodes, le
    contenu LaTeX réel vit dans `sections[].items[]` (modèle universel à
    2 niveaux). Conséquence : les macros tkz-euclide utilisées dans des
    items n'étaient pas détectées, l'option [geometrie] n'était pas activée,
    tkz-base n'était pas chargé, et \\tkzLabelX (notamment) plantait à la
    compilation avec « Undefined control sequence ».
    """

    def test_notion_avec_tkz_dans_section_active_geometrie(self, db_peuplee):
        """Une notion dont la SEULE occurrence de tkz est dans une section
        doit déclencher l'option [geometrie] (donc le chargement de
        tkz-base + tkz-euclide + tkz-tab par le préambule)."""
        # La notion 'no1' de la fixture a son corps vide et utilise déjà
        # des sections — on remplace l'item par du contenu tkz-euclide.
        db_peuplee.execute(
            "UPDATE atome_section_items SET corps = ? WHERE id = ?",
            (r"\begin{tikzpicture}\tkzInit[xmin=-3,xmax=3]\tkzDrawX"
             r"\tkzLabelX\end{tikzpicture}", 'it_no_r0'),
        )
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        # Sanity check : le corps lui-même n'a pas de tkz, c'est bien la
        # section qui le porte.
        assert '\\tkz' not in atome.corps
        assert any('\\tkzInit' in (it or '')
                   for sec in atome.sections
                   for it in sec.get('items', []))

        opts = detecter_options_paquet(db_peuplee, atome)
        assert 'geometrie' in opts, (
            "L'option [geometrie] doit être détectée même quand les "
            "macros tkz-euclide sont uniquement dans les sections."
        )

    def test_methode_avec_tkz_dans_section_active_geometrie(self, db_peuplee):
        """Idem pour une méthode (modèle universel à 2 niveaux aussi)."""
        db_peuplee.execute(
            "UPDATE atome_section_items SET corps = ? WHERE id = ?",
            (r"\tkzDefPoints{0/0/A,2/0/B}\tkzDrawSegments(A,B)",
             'it_me_e0'),
        )
        atome = charger_atome(db_peuplee, 'methode', 'me1')
        opts = detecter_options_paquet(db_peuplee, atome)
        assert 'geometrie' in opts

    def test_notion_avec_scratch3_dans_section_active_scratch(self, db_peuplee):
        """Même logique pour scratch3 — autre paquet derrière une option."""
        db_peuplee.execute(
            "UPDATE atome_section_items SET corps = ? WHERE id = ?",
            (r"Voir \greenflag puis \blockmove{10}", 'it_no_r0'),
        )
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        opts = detecter_options_paquet(db_peuplee, atome)
        assert 'scratch' in opts

    def test_titre_section_contribue_aussi(self, db_peuplee):
        """Si une macro spécifique apparaît dans le titre d'une section
        (cas plus rare mais possible), elle doit aussi être détectée."""
        # On vide les items et on met du tkz dans le titre de section.
        db_peuplee.execute(
            "UPDATE atome_section_items SET corps = '' WHERE id = ?",
            ('it_no_r0',),
        )
        db_peuplee.execute(
            "UPDATE atome_sections SET titre = ? WHERE id = ?",
            (r"Voir \tkzInit", 'sec_no_r'),
        )
        atome = charger_atome(db_peuplee, 'notion', 'no1')
        opts = detecter_options_paquet(db_peuplee, atome)
        assert 'geometrie' in opts


class TestAplatirTextes:
    """Tests directs du helper _aplatir_textes : robustesse aux structures
    imbriquées et garde-fou de profondeur."""

    def test_string_simple(self):
        from services.latex_rendu_atome import _aplatir_textes
        assert _aplatir_textes("hello") == ["hello"]

    def test_none_retourne_liste_vide(self):
        from services.latex_rendu_atome import _aplatir_textes
        assert _aplatir_textes(None) == []

    def test_liste_de_strings(self):
        from services.latex_rendu_atome import _aplatir_textes
        assert _aplatir_textes(["a", "b", "c"]) == ["a", "b", "c"]

    def test_dict_de_strings(self):
        """Les valeurs string d'un dict sont récupérées (l'ordre n'importe
        pas pour la détection de macros — l'analyse est ensembliste)."""
        from services.latex_rendu_atome import _aplatir_textes
        out = _aplatir_textes({"k1": "a", "k2": "b"})
        assert sorted(out) == ["a", "b"]

    def test_recursion_2_niveaux(self):
        """Liste de dicts contenant des listes — cas hypothétique évoqué
        dans le commentaire de la dataclass Atome (multicols, sous-listes
        imbriquées)."""
        from services.latex_rendu_atome import _aplatir_textes
        struct = [
            {"texte": "A", "sous": ["B", "C"]},
            "D",
        ]
        out = _aplatir_textes(struct)
        assert sorted(out) == ["A", "B", "C", "D"]

    def test_types_inattendus_ignores(self):
        """Les ints, bools, etc. ne contiennent pas de LaTeX → ignorés."""
        from services.latex_rendu_atome import _aplatir_textes
        assert _aplatir_textes([1, "x", True, None, "y"]) == ["x", "y"]

    def test_profondeur_excessive_leve_recursion_error(self):
        """Garde-fou demandé : si un jour le format évolue et qu'un item
        dépasse la profondeur autorisée, on doit le détecter explicitement
        plutôt que tronquer silencieusement (ce qui ferait à nouveau manquer
        des macros et casser la compilation, comme c'était le cas en v0.8)."""
        from services.latex_rendu_atome import _aplatir_textes
        # Construit une structure de profondeur 6 (1 string entouré de 6
        # niveaux de listes). _PROFONDEUR_MAX_ITEMS = 4 → ça doit lever.
        x = "feuille"
        for _ in range(6):
            x = [x]
        with pytest.raises(RecursionError, match="Profondeur d'item"):
            _aplatir_textes(x)

    def test_profondeur_juste_a_la_limite_passe(self):
        """À la profondeur exactement = limite, ça doit passer."""
        from services.latex_rendu_atome import (
            _aplatir_textes, _PROFONDEUR_MAX_ITEMS,
        )
        x = "feuille"
        for _ in range(_PROFONDEUR_MAX_ITEMS):
            x = [x]
        # Aucune exception attendue
        out = _aplatir_textes(x)
        assert out == ["feuille"]
