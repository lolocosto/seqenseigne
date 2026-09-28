r"""
tests/test_preambule_atome.py — Tests du module de préambule sur mesure.

Couvre :
  - Fermeture transitive sur le graphe paquet_definitions
  - Filtrage des définitions au statut 'ignore'
  - Wrapper systématique selon le type d'atome
  - Détection des paquets externes (siunitx, xint…)
  - Options [geometrie] / [scratch] tirent les paquets tkz-* / scratch3
  - Ordre d'émission : theme avant core, ligne_debut croissante
  - Préambule ne contient pas \usepackage{seqenseigne}
  - Wrapping \makeatletter / \makeatother autour des définitions
"""

from __future__ import annotations
import sqlite3
import pytest

from services.preambule_atome import (
    Preambule,
    PAQUETS_NOYAU,
    WRAPPER_COMMUN,
    WRAPPER_PAR_TYPE,
    INITIALISATIONS_BIBLIOTHEQUES,
    construire_preambule,
    _fermeture_transitive,
    _wrapper_du_type,
    _charger_index_definitions,
    _compresser_lignes_vides,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_paquet():
    """Base SQLite avec un mini-graphe de définitions du paquet seqenseigne.

    Schéma minimal nécessaire au module + données illustrant :
      - une chaîne de dépendances (\\macroA → \\macroB → \\macroC)
      - une macro 'ignore' (\\seqLoadData)
      - un environnement (seqExercice) qui appelle deux macros
      - une définition de chaque fichier source pour tester l'ordre de tri
    """
    conn = sqlite3.connect(':memory:')
    conn.executescript(r"""
        CREATE TABLE paquet_definitions (
            nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
            corps TEXT, corps_fin TEXT, texte_complet TEXT,
            fichier_source TEXT, ligne_debut INTEGER,
            macros_appelees TEXT, environnements_utilises TEXT,
            statut_rendu_atome TEXT, contenu_atome TEXT
        );
    """)
    # Chaîne A → B → C, dans des fichiers différents pour tester l'ordre
    rows = [
        # (nom, type, fichier, ligne, macros_appelees, envs_utilises, statut, texte)
        ('\\macroA', 'command', 'seqenseigne-core.sty', 100,
         '["\\\\macroB"]', '[]', 'reutilise',
         '\\newcommand{\\macroA}{\\macroB{}}'),
        ('\\macroB', 'command', 'seqenseigne-theme.sty', 50,
         '["\\\\macroC"]', '[]', 'reutilise',
         '\\newcommand{\\macroB}[1]{\\macroC{#1}}'),
        ('\\macroC', 'command', 'seqenseigne-theme.sty', 20,
         '[]', '[]', 'reutilise',
         '\\newcommand{\\macroC}[1]{[#1]}'),
        # Macro 'ignore' (à filtrer même si dans la fermeture)
        ('\\seqLoadData', 'command', 'seqenseigne-data.sty', 10,
         '[]', '[]', 'ignore', '\\newcommand{\\seqLoadData}{...}'),
        # Macro non utilisée par le test (ne doit pas apparaître dans la fermeture)
        ('\\macroIsolee', 'command', 'seqenseigne-core.sty', 200,
         '[]', '[]', 'reutilise',
         '\\newcommand{\\macroIsolee}{ISO}'),
        # Un environnement qui appelle macroA
        ('envTest', 'environment', 'seqenseigne-core.sty', 300,
         '["\\\\macroA"]', '[]', 'reutilise',
         '\\newenvironment{envTest}{\\macroA}{}'),
        # Un environnement de wrapper (seqExercice) — minimal
        ('seqExercice', 'environment', 'seqenseigne-core.sty', 400,
         '[]', '[]', 'reutilise',
         '\\newenvironment{seqExercice}[1][]{EXO}{}'),
        ('seqSerieExos', 'environment', 'seqenseigne-core.sty', 410,
         '[]', '[]', 'reutilise',
         '\\newenvironment{seqSerieExos}[1]{}{}'),
        ('seqNotion', 'environment', 'seqenseigne-core.sty', 500,
         '[]', '[]', 'reutilise',
         '\\newenvironment{seqNotion}[2]{}{}'),
        ('seqMethode', 'environment', 'seqenseigne-core.sty', 600,
         '[]', '[]', 'reutilise',
         '\\newenvironment{seqMethode}[2]{}{}'),
        ('seqColItem', 'environment', 'seqenseigne-core.sty', 700,
         '[]', '[]', 'reutilise',
         '\\newenvironment{seqColItem}[1][]{}{}'),
        # Macros wrapper basiques — vides, juste pour qu'elles soient résolues
        ('\\seqCreeCompteurs', 'command', 'seqenseigne-core.sty', 800,
         '[]', '[]', 'reutilise', '\\newcommand{\\seqCreeCompteurs}{}'),
        ('\\seqSetColorsTheme', 'command', 'seqenseigne-data.sty', 50,
         '[]', '[]', 'reutilise',
         '\\newcommand{\\seqSetColorsTheme}[1]{}'),
        ('\\seqSetCodeNiveau', 'command', 'seqenseigne-core.sty', 810,
         '[]', '[]', 'reutilise',
         '\\newcommand{\\seqSetCodeNiveau}[1]{}'),
        ('\\seqSetCodeSequence', 'command', 'seqenseigne-core.sty', 820,
         '[]', '[]', 'reutilise',
         '\\newcommand{\\seqSetCodeSequence}[1]{}'),
        ('\\seqInitCorriges', 'command', 'seqenseigne-core.sty', 830,
         '[]', '[]', 'reutilise',
         '\\newcommand{\\seqInitCorriges}{}'),
        ('\\seqInitAnnexes', 'command', 'seqenseigne-core.sty', 840,
         '[]', '[]', 'reutilise',
         '\\newcommand{\\seqInitAnnexes}{}'),
        ('\\seqAfficheCorriges', 'command', 'seqenseigne-core.sty', 850,
         '[]', '[]', 'reutilise',
         '\\newcommand{\\seqAfficheCorriges}{}'),
        ('\\seqAfficheAnnexes', 'command', 'seqenseigne-core.sty', 860,
         '[]', '[]', 'reutilise',
         '\\newcommand{\\seqAfficheAnnexes}{}'),
        ('\\seqCorrigesExos', 'command', 'seqenseigne-core.sty', 870,
         '[]', '[]', 'reutilise',
         '\\newcommand{\\seqCorrigesExos}{}'),
        ('\\seqCorrige', 'command', 'seqenseigne-core.sty', 880,
         '[]', '[]', 'reutilise',
         '\\newcommand{\\seqCorrige}[1]{}'),
    ]
    for r in rows:
        conn.execute(
            "INSERT INTO paquet_definitions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (r[0], r[1], '', '', '', r[7],   # nom, type, args_spec, corps, corps_fin, texte
             r[2], r[3], r[4], r[5], r[6], ''),  # fichier, ligne, macros, envs, statut, contenu
        )
    conn.commit()
    yield conn
    conn.close()


# ── Tests : chargement de l'index ─────────────────────────────────────────────

class TestChargerIndex:

    def test_charge_toutes_definitions(self, db_paquet):
        index = _charger_index_definitions(db_paquet)
        assert '\\macroA' in index
        assert '\\macroB' in index
        assert 'envTest' in index

    def test_parse_listes_json(self, db_paquet):
        index = _charger_index_definitions(db_paquet)
        assert index['\\macroA'].macros_appelees == ['\\macroB']
        assert index['\\macroB'].macros_appelees == ['\\macroC']
        assert index['\\macroC'].macros_appelees == []

    def test_environnement_charge(self, db_paquet):
        index = _charger_index_definitions(db_paquet)
        env = index['envTest']
        assert env.type_latex == 'environment'
        assert env.macros_appelees == ['\\macroA']


# ── Tests : fermeture transitive ──────────────────────────────────────────────

class TestFermetureTransitive:

    def test_fermeture_chaine_simple(self, db_paquet):
        index = _charger_index_definitions(db_paquet)
        ferme = _fermeture_transitive({'\\macroA'}, index)
        assert ferme == {'\\macroA', '\\macroB', '\\macroC'}

    def test_fermeture_unique_meme_si_repete(self, db_paquet):
        """Pas de boucle infinie même si on part de plusieurs noms qui
        partagent des dépendances."""
        index = _charger_index_definitions(db_paquet)
        ferme = _fermeture_transitive({'\\macroA', '\\macroB'}, index)
        assert ferme == {'\\macroA', '\\macroB', '\\macroC'}

    def test_fermeture_environnement(self, db_paquet):
        """Un environnement qui appelle une macro tire la macro et toute sa
        chaîne."""
        index = _charger_index_definitions(db_paquet)
        ferme = _fermeture_transitive({'envTest'}, index)
        assert ferme == {'envTest', '\\macroA', '\\macroB', '\\macroC'}

    def test_macro_inconnue_ignoree(self, db_paquet):
        """Une macro non présente dans l'index est silencieusement écartée
        de la frontière initiale."""
        index = _charger_index_definitions(db_paquet)
        ferme = _fermeture_transitive({'\\macroInconnue', '\\macroA'}, index)
        # \macroInconnue est dans la fermeture (on a accepté tous les inputs),
        # mais ne tire rien.
        assert '\\macroInconnue' in ferme
        assert ferme >= {'\\macroA', '\\macroB', '\\macroC'}

    def test_macro_isolee_pas_tiree(self, db_paquet):
        index = _charger_index_definitions(db_paquet)
        ferme = _fermeture_transitive({'\\macroA'}, index)
        assert '\\macroIsolee' not in ferme

    def test_set_vide_donne_set_vide(self, db_paquet):
        index = _charger_index_definitions(db_paquet)
        assert _fermeture_transitive(set(), index) == set()


# ── Tests : wrapper par type d'atome ──────────────────────────────────────────

class TestWrapperParType:

    def test_exercice_inclut_corrige_et_serie(self):
        w = _wrapper_du_type('exercice')
        assert 'seqExercice' in w
        assert 'seqSerieExos' in w
        assert '\\seqCorrige' in w
        assert '\\seqAfficheCorriges' in w

    def test_notion_inclut_seqNotion(self):
        w = _wrapper_du_type('notion')
        assert 'seqNotion' in w
        # Pas de seqExercice pour une notion
        assert 'seqExercice' not in w

    def test_methode_inclut_seqMethode(self):
        w = _wrapper_du_type('methode')
        assert 'seqMethode' in w
        assert 'seqExercice' not in w

    def test_wrapper_commun_partout(self):
        """\\seqCreeCompteurs et \\seqSetColorsTheme sont dans tous les types."""
        for t in ('exercice', 'notion', 'methode'):
            w = _wrapper_du_type(t)
            assert '\\seqCreeCompteurs' in w
            assert '\\seqSetColorsTheme' in w
            assert '\\seqSetCodeNiveau' in w
            assert '\\seqSetCodeSequence' in w

    def test_type_inconnu_leve(self):
        with pytest.raises(ValueError):
            _wrapper_du_type('autre')


# ── Tests : construire_preambule (cas nominaux) ───────────────────────────────

class TestConstruirePreambule:

    def test_paquets_noyau_toujours_charges(self, db_paquet):
        p = construire_preambule(db_paquet, 'exercice', set(), set())
        # Tous les paquets noyau doivent être présents, dans l'ordre
        for nom, _ in PAQUETS_NOYAU:
            assert f'{{{nom}}}' in p.texte, f"Paquet noyau manquant : {nom}"

    def test_pas_de_usepackage_seqenseigne(self, db_paquet):
        """L'idée même de ce module : on n'inclut JAMAIS \\usepackage{seqenseigne}.
        Toutes ses définitions sont inlinées.

        On ignore les lignes qui commencent par '%' (commentaires LaTeX) car
        le préambule peut citer \\usepackage{seqenseigne} dans une explication."""
        p = construire_preambule(db_paquet, 'exercice', set(), set())
        for ligne in p.texte.split('\n'):
            if ligne.lstrip().startswith('%'):
                continue
            assert 'seqenseigne}' not in ligne, (
                f"Le préambule charge encore le paquet seqenseigne via "
                f"\\usepackage : ligne '{ligne}'"
            )

    def test_definitions_du_wrapper_emises(self, db_paquet):
        """Sans aucune macro de l'atome, le wrapper systématique seul doit
        produire l'émission de seqExercice et compagnie."""
        p = construire_preambule(db_paquet, 'exercice', set(), set())
        emises = set(p.definitions_emises)
        assert 'seqExercice' in emises
        assert 'seqSerieExos' in emises
        assert '\\seqCreeCompteurs' in emises
        assert '\\seqCorrige' in emises

    def test_macros_atome_tirent_chaine_dependances(self, db_paquet):
        """\\macroA appelle \\macroB qui appelle \\macroC : passer macroA
        en macros_atome doit faire émettre les trois."""
        p = construire_preambule(
            db_paquet, 'exercice', {'\\macroA'}, set(),
        )
        emises = set(p.definitions_emises)
        assert '\\macroA' in emises
        assert '\\macroB' in emises
        assert '\\macroC' in emises

    def test_environnement_atome_tire_dependances(self, db_paquet):
        """Un environnement utilisé par l'atome doit tirer ses dépendances."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), {'envTest'},
        )
        emises = set(p.definitions_emises)
        assert 'envTest' in emises
        assert '\\macroA' in emises
        assert '\\macroB' in emises
        assert '\\macroC' in emises

    def test_macro_isolee_non_emise_si_non_utilisee(self, db_paquet):
        """Une macro qui n'est ni dans l'atome ni dans le wrapper ne doit
        pas être émise."""
        p = construire_preambule(db_paquet, 'exercice', set(), set())
        assert '\\macroIsolee' not in p.definitions_emises

    def test_definitions_ignore_pas_emises(self, db_paquet):
        """\\seqLoadData a statut 'ignore' : même si on la met dans
        macros_atome, elle ne doit pas être émise."""
        p = construire_preambule(
            db_paquet, 'exercice', {'\\seqLoadData'}, set(),
        )
        assert '\\seqLoadData' not in p.definitions_emises
        assert '\\seqLoadData' not in p.texte or 'ignore' in p.texte.lower()

    def test_definition_reecrite_emet_contenu_atome(self, db_paquet):
        """Une définition au statut 'reecrit' doit émettre son `contenu_atome`
        (renewcommand explicite) à la place de son `texte_complet` (définition
        d'origine du paquet)."""
        # Ajouter dynamiquement une règle reecrit
        db_paquet.execute("""
            INSERT INTO paquet_definitions
            VALUES ('\\macroReecrite', 'command', '', '', '',
                    '\\newcommand{\\macroReecrite}{ORIGINAL}',
                    'seqenseigne-core.sty', 999, '[]', '[]', 'reecrit',
                    '\\renewcommand{\\macroReecrite}{REMPLACE}')
        """)
        db_paquet.commit()
        p = construire_preambule(
            db_paquet, 'exercice', {'\\macroReecrite'}, set(),
        )
        assert '\\macroReecrite' in p.definitions_emises
        # On doit voir REMPLACE et pas ORIGINAL
        assert 'REMPLACE' in p.texte
        assert 'ORIGINAL' not in p.texte

    def test_definition_reecrite_sans_contenu_emet_texte_complet(self, db_paquet):
        """Si une règle est marquée 'reecrit' mais sans contenu_atome (cas
        défensif : ne devrait pas arriver), on retombe sur texte_complet
        — préférable à une émission vide qui casserait la compilation."""
        db_paquet.execute("""
            INSERT INTO paquet_definitions
            VALUES ('\\macroReecriteVide', 'command', '', '', '',
                    '\\newcommand{\\macroReecriteVide}{ORIG_VIDE}',
                    'seqenseigne-core.sty', 999, '[]', '[]', 'reecrit',
                    '')
        """)
        db_paquet.commit()
        p = construire_preambule(
            db_paquet, 'exercice', {'\\macroReecriteVide'}, set(),
        )
        assert 'ORIG_VIDE' in p.texte


# ── Tests : ordre d'émission ──────────────────────────────────────────────────

class TestOrdreEmission:

    def test_theme_avant_core(self, db_paquet):
        """seqenseigne-theme.sty doit être émis avant seqenseigne-core.sty
        (les définitions de core peuvent dépendre de celles de theme)."""
        p = construire_preambule(
            db_paquet, 'exercice', {'\\macroA'}, set(),
        )
        # macroA est dans core (ligne 100), macroB et C sont dans theme (50, 20)
        idx_a = p.definitions_emises.index('\\macroA')
        idx_b = p.definitions_emises.index('\\macroB')
        idx_c = p.definitions_emises.index('\\macroC')
        # theme.sty doit venir avant core.sty :
        # macroC (theme, ligne 20) avant macroB (theme, ligne 50) avant macroA (core, ligne 100)
        assert idx_c < idx_b < idx_a

    def test_meme_fichier_par_ligne_croissante(self, db_paquet):
        """À l'intérieur d'un même fichier, l'ordre suit ligne_debut croissante."""
        p = construire_preambule(
            db_paquet, 'exercice', {'\\macroB'}, set(),
        )
        # macroC est ligne 20 dans theme.sty, macroB est ligne 50
        idx_b = p.definitions_emises.index('\\macroB')
        idx_c = p.definitions_emises.index('\\macroC')
        assert idx_c < idx_b


# ── Tests : wrapping makeatletter ────────────────────────────────────────────

class TestMakeatletter:

    def test_definitions_entourees_makeatletter(self, db_paquet):
        """Le bloc des définitions inlinées doit être enveloppé par
        \\makeatletter / \\makeatother (les définitions du paquet contiennent
        des @ dans leurs noms internes)."""
        p = construire_preambule(db_paquet, 'exercice', set(), set())
        idx_let = p.texte.find(r'\makeatletter')
        idx_other = p.texte.find(r'\makeatother')
        idx_seqExo = p.texte.find('\\newenvironment{seqExercice}')
        assert idx_let != -1, '\\makeatletter manquant'
        assert idx_other != -1, '\\makeatother manquant'
        assert idx_let < idx_seqExo < idx_other, (
            'Les définitions inlinées doivent être encadrées par '
            '\\makeatletter/\\makeatother'
        )


# ── Tests : paquets externes ──────────────────────────────────────────────────

class TestPaquetsExternes:

    def test_paquets_supplementaires_ajoutes(self, db_paquet):
        """Les paquets passés en `paquets_tex_supplementaires` apparaissent
        dans le préambule final."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            paquets_tex_supplementaires=['siunitx'],
        )
        assert '\\usepackage{siunitx}' in p.texte

    def test_paquets_supplementaires_dedoublonnes_avec_noyau(self, db_paquet):
        """Si un paquet supplémentaire est déjà dans le noyau, il n'est pas
        ajouté à nouveau."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            paquets_tex_supplementaires=['amsmath'],
        )
        # amsmath est dans le noyau → pas de doublon
        nb = p.texte.count('\\usepackage{amsmath}')
        assert nb == 1

    def test_option_geometrie_charge_tkz(self, db_paquet):
        """L'option [geometrie] doit charger tkz-base, tkz-euclide, tkz-tab."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            options_atome=['geometrie'],
        )
        assert 'tkz-base' in p.texte
        assert 'tkz-euclide' in p.texte
        assert 'tkz-tab' in p.texte

    def test_option_scratch_charge_scratch3(self, db_paquet):
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            options_atome=['scratch'],
        )
        assert 'scratch3' in p.texte

    def test_pas_de_pseudo_paquets(self, db_paquet):
        """Les pseudo-paquets 'tex-primitive' et 'babel-french' ne doivent
        jamais apparaître comme \\usepackage."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            paquets_tex_supplementaires=['tex-primitive', 'babel-french'],
        )
        assert '\\usepackage{tex-primitive}' not in p.texte
        assert '\\usepackage{babel-french}' not in p.texte


# ── Tests : statistiques de Preambule ─────────────────────────────────────────

class TestPreambuleStats:

    def test_compteurs_diag(self, db_paquet):
        """Les compteurs nb_definitions_* doivent refléter la réalité."""
        p = construire_preambule(
            db_paquet, 'exercice', {'\\macroA'}, {'envTest'},
        )
        # nb_macros_utilisees = macros_atome + envs_atome
        assert p.nb_macros_utilisees == 2
        # Au moins macroA + envTest dans l'initial (en plus du wrapper)
        assert p.nb_definitions_initiales >= 2
        # Fermeture >= initial
        assert p.nb_definitions_fermees >= p.nb_definitions_initiales
        # Émises = fermeture sans 'ignore'
        assert p.nb_definitions_emises <= p.nb_definitions_fermees
        assert p.nb_definitions_emises == len(p.definitions_emises)

    def test_paquets_externes_dans_resultat(self, db_paquet):
        """Le champ paquets_externes contient toute la liste finale."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            paquets_tex_supplementaires=['siunitx'],
        )
        noms = {nom for nom, _ in p.paquets_externes}
        assert 'amsmath' in noms       # noyau
        assert 'tcolorbox' in noms     # noyau
        assert 'siunitx' in noms       # supplémentaire


# ── Tests : compression des lignes vides ──────────────────────────────────────
#
# Régression v0.6.4 : le scanner du paquet (paquet_parseur.strip_comments)
# enlève les commentaires LaTeX mais conserve les retours à la ligne pour
# préserver les numéros de lignes (utile au diagnostic). Conséquence : un
# bloc de N commentaires devient N lignes vides dans `texte_complet`.
#
# Quand cette définition est ensuite inlinée au préambule du .tex de l'atome,
# ces lignes vides se traduisent par un \par à l'exécution. Si un \par tombe
# au milieu d'un argument à \pgfkeys (utilisé en interne par tcolorbox pour
# ses options), pdflatex plante avec :
#
#     ! Paragraph ended before \pgfkeys@addpath was complete.
#
# On teste ici que _compresser_lignes_vides (utilisé par texte_a_emettre)
# élimine ces blocs de manière conservatrice.

class TestCompresserLignesVides:

    def test_3_lignes_vides_compressees_a_1(self):
        """Trois lignes vides consécutives → une seule (pas de \\par)."""
        assert _compresser_lignes_vides("a\n\n\n\nb") == "a\n\nb"

    def test_1_ligne_vide_isolee_conservee(self):
        """Une seule ligne vide n'est pas un \\par : on la garde pour la
        lisibilité."""
        assert _compresser_lignes_vides("a\n\nb") == "a\n\nb"

    def test_lignes_de_blancs_traitees_comme_vides(self):
        """Une ligne ne contenant que des espaces/tabs équivaut à vide."""
        assert _compresser_lignes_vides("a\n   \n\t\nb") == "a\n\nb"

    def test_pas_de_ligne_vide_inchange(self):
        """Texte sans ligne vide : inchangé."""
        assert _compresser_lignes_vides("a\nb\nc") == "a\nb\nc"

    def test_chaine_vide(self):
        assert _compresser_lignes_vides("") == ""

    def test_blocs_multiples(self):
        """Plusieurs blocs séparés sont chacun compressés."""
        src = "a\n\n\nb\n\n\n\nc"
        assert _compresser_lignes_vides(src) == "a\n\nb\n\nc"

    def test_definition_seqCreeCompteurs_realiste(self):
        r"""Cas réel reproduit du paquet seqenseigne : la définition de
        \seqCreeCompteurs contient 3 commentaires consécutifs entre les
        \newcounter et les \renewcommand{\theHxxx}, ce qui après strip_comments
        produit 3 lignes vides → \par parasite à l'exécution."""
        src = (
            r"\newcommand\seqCreeCompteurs{" "\n"
            r"\newcounter{NotionNum}" "\n"
            r"\newcounter{ExoNum}" "\n"
            "\n"   # ex-commentaire 1
            "\n"   # ex-commentaire 2
            "\n"   # ex-commentaire 3
            r"\renewcommand{\theHExoNum}{X}" "\n"
            "}"
        )
        compresse = _compresser_lignes_vides(src)
        # Au plus 1 ligne vide consécutive dans la sortie
        lignes = compresse.split('\n')
        max_consec = 0
        n = 0
        for l in lignes:
            if l == '':
                n += 1
                max_consec = max(max_consec, n)
            else:
                n = 0
        assert max_consec <= 1, (
            f"_compresser_lignes_vides a laissé {max_consec} lignes vides "
            f"consécutives, ce qui produira un \\par à l'exécution"
        )


class TestEmissionSansLignesVidesMultiples:
    """Vérifie que le préambule final n'émet jamais de blocs de 2+ lignes
    vides consécutives à l'intérieur d'une définition inlinée."""

    def test_preambule_ne_contient_pas_de_par_parasites(self, db_paquet):
        """Injecter une définition avec 3 lignes vides dans son texte_complet,
        et vérifier qu'au final le préambule produit ne contient pas de
        bloc de 2+ lignes vides consécutives à l'intérieur du bloc inliné."""
        # Modifier seqExercice pour qu'il ait 3 lignes vides dans son corps
        db_paquet.execute(
            "UPDATE paquet_definitions SET texte_complet = ? WHERE nom = ?",
            (
                "\\newenvironment{seqExercice}[1][]{EXO\n\n\n\n\nDEBUT}{}",
                'seqExercice',
            ),
        )
        p = construire_preambule(db_paquet, 'exercice', set(), set())
        # Inspecter la zone des définitions inlinées
        idx_let = p.texte.find(r'\makeatletter')
        idx_other = p.texte.find(r'\makeatother')
        zone_inlinee = p.texte[idx_let:idx_other]
        # Pas de 2+ lignes vides consécutives dans cette zone
        assert '\n\n\n' not in zone_inlinee, (
            "Le préambule contient des blocs de >=3 \\n consécutifs, "
            "ce qui produira un \\par parasite à l'exécution"
        )


# ── Tests : initialisations de bibliothèques ──────────────────────────────────

class TestInitialisationsBibliotheques:
    """Certains paquets nécessitent un appel d'initialisation après leur
    \\usepackage. Deux mécanismes coexistent :

    1. INITIALISATIONS_BIBLIOTHEQUES : table interne pour les inits qui
       ne sont pas configurables (ex. vwcol et son `widths={0.5,0.5}`
       préventif depuis v0.8.6).
    2. Listes paramétrables `tikz_libraries` (v0.8.5) et `tblr_libraries`
       (v0.9.1) : émises explicitement par l'utilisateur via la config.
       Couvrent respectivement \\usetikzlibrary{...} et
       \\UseTblrLibrary{...}.

    L'historique de la migration :
      - v0.8.4 : `\\usetikzlibrary{babel}` codé en dur dans
        INITIALISATIONS_BIBLIOTHEQUES['tikz']
      - v0.8.5 : migré vers la liste configurable `tikz_libraries`
      - v0.9.1 : `\\UseTblrLibrary{booktabs}` migré hors de
        INITIALISATIONS_BIBLIOTHEQUES['tabularray'] vers la liste
        configurable `tblr_libraries`. Motif : permettre aux atomes
        utilisant `measure=vbox` (depuis tabularray v2025A) d'ajouter
        `varwidth` à la liste sans toucher au code.
    """

    def test_pas_de_use_tblr_library_sans_liste(self, db_paquet):
        """v0.9.1 — Sans tblr_libraries, le préambule n'émet AUCUN
        \\UseTblrLibrary depuis ce mécanisme. C'est la nouvelle règle
        depuis la migration de booktabs hors de INITIALISATIONS_BIBLIOTHEQUES."""
        p = construire_preambule(db_paquet, 'exercice', set(), set())
        assert r'\UseTblrLibrary{booktabs}' not in p.texte
        assert r'\UseTblrLibrary{varwidth}' not in p.texte

    def test_dictionnaire_initialisations_n_inclut_plus_tabularray(self, db_paquet):
        """v0.9.1 — La clé 'tabularray' a été retirée d'INITIALISATIONS_BIBLIOTHEQUES.
        Seule 'vwcol' reste codée en dur (pas configurable car init préventive
        sans valeur métier exposable à l'utilisateur)."""
        assert 'tabularray' not in INITIALISATIONS_BIBLIOTHEQUES
        # vwcol reste : c'est une init préventive (`widths={0.5,0.5}`)
        # qui n'a pas de raison d'être paramétrable côté utilisateur.
        assert 'vwcol' in INITIALISATIONS_BIBLIOTHEQUES

    # v0.8.4 / v0.8.5 — Régression sur les notions tkz-euclide qui plantaient
    # avec « + or - expected » à cause de l'incompatibilité babel-french / tikz.
    # En v0.8.4, la lib `babel` était codée en dur dans
    # INITIALISATIONS_BIBLIOTHEQUES['tikz']. En v0.8.5, elle a migré vers la
    # liste paramétrable `tikz_libraries` exposée à l'utilisateur via la
    # configuration. Les tests ci-dessous figent le nouveau comportement :
    # `babel` n'est PAS chargée par défaut sans liste explicite, mais elle
    # l'est dès qu'on passe une liste qui la contient — ce qui est le cas
    # par défaut dans `Configuration.tikz_libraries()`.

    def test_pas_de_usetikzlibrary_sans_liste(self, db_paquet):
        """Sans `tikz_libraries`, le préambule n'émet aucun
        \\usetikzlibrary depuis ce mécanisme. Les éventuelles
        \\usetikzlibrary internes au contenu de l'atome ne sont pas
        affectées (mais ne sont pas non plus produites par le préambule)."""
        p = construire_preambule(db_paquet, 'exercice', set(), set())
        assert r'\usetikzlibrary{babel}' not in p.texte
        assert r'\usetikzlibrary{shapes.geometric}' not in p.texte

    def test_tikz_libraries_emet_usetikzlibrary(self, db_paquet):
        """Avec une liste passée, le préambule émet une seule ligne
        \\usetikzlibrary{lib1,lib2,...} qui contient toutes les libs."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            tikz_libraries=['babel', 'shapes.geometric', 'arrows.meta'],
        )
        assert r'\usetikzlibrary{babel,shapes.geometric,arrows.meta}' in p.texte

    def test_tikz_libraries_apres_usepackage_tikz(self, db_paquet):
        """\\usetikzlibrary doit être émis APRÈS \\usepackage{tikz}
        (sinon la macro \\usetikzlibrary n'est pas encore définie)."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            tikz_libraries=['shapes.geometric'],
        )
        idx_pkg = p.texte.find(r'\usepackage{tikz}')
        idx_init = p.texte.find(r'\usetikzlibrary{shapes.geometric}')
        assert idx_pkg != -1, "tikz non chargé"
        assert idx_init != -1, r"\usetikzlibrary{shapes.geometric} manquant"
        assert idx_pkg < idx_init

    def test_tikz_libraries_dedoublonne_preserve_ordre(self, db_paquet):
        """Doublons éliminés en préservant l'ordre de première apparition."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            tikz_libraries=['babel', 'calc', 'babel', 'positioning', 'calc'],
        )
        assert r'\usetikzlibrary{babel,calc,positioning}' in p.texte

    def test_tikz_libraries_filtre_entrees_vides(self, db_paquet):
        """Entrées vides ou n'ayant que des espaces sont éliminées."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            tikz_libraries=['  babel  ', '', '  ', 'calc'],
        )
        assert r'\usetikzlibrary{babel,calc}' in p.texte

    def test_tikz_libraries_liste_vide_n_emet_rien(self, db_paquet):
        """Liste totalement vide après filtrage → aucun \\usetikzlibrary."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            tikz_libraries=['', '   ', ''],
        )
        assert r'\usetikzlibrary' not in p.texte


# ── v0.9.1 — Bibliothèques tabularray paramétrables ─────────────────────────

class TestTblrLibrariesV091:
    """v0.9.1 — Pendant frontal exact de tikz_libraries pour tabularray.

    Différence syntaxique notable : \\UseTblrLibrary n'accepte qu'UNE
    bibliothèque par appel (contrairement à \\usetikzlibrary qui accepte
    une liste séparée par virgules). Le préambule émet donc une commande
    par bibliothèque.
    """

    def test_tblr_libraries_emet_use_tblr_library(self, db_paquet):
        """Avec une liste passée, une commande \\UseTblrLibrary par lib."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            tblr_libraries=['booktabs', 'varwidth'],
        )
        assert r'\UseTblrLibrary{booktabs}' in p.texte
        assert r'\UseTblrLibrary{varwidth}' in p.texte

    def test_tblr_libraries_apres_usepackage_tabularray(self, db_paquet):
        """\\UseTblrLibrary{...} doit être émis APRÈS \\usepackage{tabularray}
        (sinon la macro \\UseTblrLibrary n'est pas encore définie)."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            tblr_libraries=['booktabs'],
        )
        idx_pkg = p.texte.find(r'\usepackage{tabularray}')
        idx_init = p.texte.find(r'\UseTblrLibrary{booktabs}')
        assert idx_pkg != -1, "tabularray non chargé"
        assert idx_init != -1, r"\UseTblrLibrary{booktabs} manquant"
        assert idx_pkg < idx_init

    def test_tblr_libraries_dedoublonne_preserve_ordre(self, db_paquet):
        """Doublons éliminés en préservant l'ordre de première apparition.
        Note : on ne teste pas l'ordre exact d'émission au format texte
        car chaque lib est sur sa propre ligne ; on vérifie la présence."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            tblr_libraries=['booktabs', 'varwidth', 'booktabs', 'counter'],
        )
        # Chaque lib apparaît UNE seule fois dans le préambule
        assert p.texte.count(r'\UseTblrLibrary{booktabs}') == 1
        assert p.texte.count(r'\UseTblrLibrary{varwidth}') == 1
        assert p.texte.count(r'\UseTblrLibrary{counter}')  == 1

    def test_tblr_libraries_filtre_entrees_vides(self, db_paquet):
        """Entrées vides ou n'ayant que des espaces sont éliminées."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            tblr_libraries=['  booktabs  ', '', '  ', 'varwidth'],
        )
        assert r'\UseTblrLibrary{booktabs}' in p.texte
        assert r'\UseTblrLibrary{varwidth}' in p.texte
        # Pas d'entrée vide qui aurait été émise
        assert r'\UseTblrLibrary{}' not in p.texte
        assert r'\UseTblrLibrary{ }' not in p.texte

    def test_tblr_libraries_liste_vide_n_emet_rien(self, db_paquet):
        """Liste totalement vide après filtrage → aucun \\UseTblrLibrary."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            tblr_libraries=['', '   ', ''],
        )
        assert r'\UseTblrLibrary' not in p.texte

    def test_tblr_libraries_chaque_lib_ligne_separee(self, db_paquet):
        """\\UseTblrLibrary n'accepte qu'une bibliothèque à la fois.
        Vérifie qu'on ne génère pas accidentellement
        \\UseTblrLibrary{booktabs,varwidth} (qui planterait)."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), set(),
            tblr_libraries=['booktabs', 'varwidth'],
        )
        assert r'\UseTblrLibrary{booktabs,varwidth}' not in p.texte
        assert r'\UseTblrLibrary{booktabs, varwidth}' not in p.texte


# v0.8.6 — Marges alignées sur les livrets et init préventive de vwcol.

class TestNewGeometry:
    """Le préambule reconstruit doit appliquer `\\newgeometry` avec les
    mêmes valeurs que les livrets seqenseigne, pour que `\\linewidth`
    (et donc le paquet `vwcol`) se comporte identiquement.
    """

    def test_newgeometry_present(self, db_paquet):
        """\\newgeometry doit être émis dans le préambule de tout atome."""
        p = construire_preambule(db_paquet, 'exercice', set(), set())
        assert r'\newgeometry{left=35pt,right=35pt,top=65pt,bottom=70pt}' \
               in p.texte

    def test_newgeometry_apres_usepackage_geometry(self, db_paquet):
        """\\newgeometry doit être émis après \\usepackage{geometry}
        (sinon la commande n'est pas définie)."""
        p = construire_preambule(db_paquet, 'exercice', set(), set())
        idx_pkg = p.texte.find(r'\usepackage{geometry}')
        idx_new = p.texte.find(r'\newgeometry')
        assert idx_pkg != -1, "geometry non chargé"
        assert idx_new != -1, r"\newgeometry manquant"
        assert idx_pkg < idx_new

    def test_newgeometry_avant_definitions_seqenseigne(self, db_paquet):
        """\\newgeometry doit être émis AVANT les définitions inlinées
        de seqenseigne (qui peuvent référencer \\linewidth dans des
        \\newcommand). Pour qu'elles voient la bonne `\\linewidth` quand
        elles sont effectivement utilisées, il faut que la geometry soit
        définie en premier dans le préambule."""
        p = construire_preambule(db_paquet, 'exercice', set(), set())
        idx_new = p.texte.find(r'\newgeometry')
        idx_makeat = p.texte.find(r'\makeatletter')
        assert idx_new != -1
        assert idx_makeat != -1
        assert idx_new < idx_makeat

    def test_geometry_newgeometry_export(self):
        """La constante GEOMETRY_NEWGEOMETRY est exportée pour usage
        externe (tests, debug)."""
        from services.preambule_atome import GEOMETRY_NEWGEOMETRY
        assert isinstance(GEOMETRY_NEWGEOMETRY, str)
        assert 'left=35pt' in GEOMETRY_NEWGEOMETRY
        assert 'right=35pt' in GEOMETRY_NEWGEOMETRY


class TestVwcolInitialisation:
    """Le paquet vwcol ne fournit pas de valeur par défaut pour `widths`.
    Si un atome appelle `\\begin{vwcol}[lines=N]` sans `widths=` dans un
    scope où aucun `\\vwcolsetup{widths=...}` antérieur n'a été exécuté,
    `\\vwcol@widths` est undefined et provoque une erreur fatale sur
    MiKTeX. Le préambule doit donc initialiser `widths` à une valeur
    neutre quand vwcol est chargé."""

    def test_pas_d_init_si_vwcol_absent(self, db_paquet):
        """Si l'atome n'utilise pas vwcol, aucune initialisation `\\vwcolsetup`
        ne doit être émise (l'appel planterait — vwcol non chargé)."""
        p = construire_preambule(db_paquet, 'exercice', set(), set())
        assert r'\vwcolsetup' not in p.texte

    def test_init_si_vwcol_dans_envs(self, db_paquet):
        """Si l'atome utilise l'environnement vwcol, le préambule charge
        le paquet ET émet le `\\vwcolsetup{widths=...}` initial.

        Note : on passe vwcol via `paquets_tex_supplementaires` car c'est
        ainsi que le pipeline normal procède. `latex_rendu_atome.py` analyse
        les environnements utilisés et alimente cette liste pour les
        paquets non-noyau (cf. detecter_paquets_tex_manquants).
        """
        p = construire_preambule(
            db_paquet, 'exercice',
            macros_atome=set(), envs_atome={'vwcol'},
            paquets_tex_supplementaires=['vwcol'],
        )
        assert r'\usepackage{vwcol}' in p.texte
        assert r'\vwcolsetup{widths={0.5,0.5}}' in p.texte

    def test_init_apres_usepackage_vwcol(self, db_paquet):
        """L'init doit être émise APRÈS le `\\usepackage{vwcol}` (sinon
        la macro `\\vwcolsetup` n'est pas encore définie)."""
        p = construire_preambule(
            db_paquet, 'exercice', set(), {'vwcol'},
            paquets_tex_supplementaires=['vwcol'],
        )
        idx_pkg = p.texte.find(r'\usepackage{vwcol}')
        idx_init = p.texte.find(r'\vwcolsetup{widths={0.5,0.5}}')
        assert idx_pkg != -1
        assert idx_init != -1
        assert idx_pkg < idx_init

    def test_dictionnaire_initialisations_contient_vwcol(self):
        """Le dictionnaire exporté contient bien l'entrée vwcol avec la
        ligne d'initialisation widths."""
        assert 'vwcol' in INITIALISATIONS_BIBLIOTHEQUES
        assert any(
            r'\vwcolsetup' in ligne and 'widths' in ligne
            for ligne in INITIALISATIONS_BIBLIOTHEQUES['vwcol']
        )

