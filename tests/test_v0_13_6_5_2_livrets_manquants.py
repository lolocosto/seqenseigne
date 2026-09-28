"""tests/test_v0_13_6_5_2_livrets_manquants.py — v0.13.6.5.2

Tests des 4 services métier de génération de livrets ajoutés en
v0.13.6.5.2 :
  - livret_fiches
  - livret_corriges
  - livret_cartes_recap
  - livret_cartes_planches

Stratégie de test :
  - Tests structurels du registre orchestrateur et signature
    (`sqlite_store` standard, sans paquet_definitions)
  - Tests fonctionnels de génération avec données peuplées
    (fixture dédiée qui ajoute les tables paquet_*)

La compilation pdflatex effective sera testée chez Laurent sur son
MiKTeX configuré.
"""
from __future__ import annotations

from pathlib import Path
import sys
import sqlite3
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.livret_fiches import generer_livret_fiches  # noqa: E402
from services.livret_corriges import generer_livret_corriges  # noqa: E402
from services.livret_cartes_recap import (  # noqa: E402
    generer_livret_cartes_recap,
)
from services.livret_cartes_planches import (  # noqa: E402
    generer_livret_cartes_planches,
)
from services import orchestrateur_compilation as orch  # noqa: E402


def _conn(store):
    return store._conn()


# ── Fixture : BDD peuplée pour les services qui passent par construire_preambule ─

@pytest.fixture
def store_avec_paquet(sqlite_store):
    """Ajoute les tables paquet_definitions / paquet_requirepackage à la
    BDD de test (elles ne sont pas dans schema.sql, peuplées par scripts).

    Ces tables sont nécessaires à services.preambule_atome qui est utilisé
    par livret_fiches et livret_corriges. Les services cartes (recap/
    planches) utilisent un préambule statique et n'en ont pas besoin.
    """
    with sqlite_store._conn() as conn:
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
                fichier_source TEXT NOT NULL,
                ordre INTEGER NOT NULL,
                nom TEXT NOT NULL,
                options TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (fichier_source, ordre)
            );
            INSERT INTO paquet_requirepackage VALUES
                ('seqenseigne-core.sty', 0, 'amsmath', ''),
                ('seqenseigne-core.sty', 1, 'tikz', '');
        """)
        conn.commit()
    return sqlite_store


# ── Fixtures de données minimales ────────────────────────────────────────────

def _setup_minimal_niveau(conn, niveau='N10'):
    """Crée un cycle, un thème, une séquence pour le niveau donné.

    v0.15.5 — Les services livret résolvent le cycle d'un niveau via
    `services.param_niveaux.lire_cycle` (table `param_niveaux`, source
    unique de vérité), et non plus via une jointure sur les séquences.
    La fixture doit donc créer thème + séquence sous le cycle RÉEL du
    niveau (lu dans `param_niveaux`, amorcé par le CSV de conftest :
    N10→C04, N09→C03, …). Auparavant on utilisait un cycle fictif 'C99'
    qui fonctionnait avec l'ancienne résolution par jointure mais produit
    désormais un livret vide (mismatch cycle séquences ≠ cycle param).
    """
    from services.param_niveaux import lire_cycle
    cycle_code = lire_cycle(conn, niveau)
    theme_id = f"theme_test_{uuid.uuid4().hex[:6]}"
    seq_code = 'S01'

    conn.execute("""
        INSERT OR IGNORE INTO cycles (code, nom, description)
        VALUES (?, 'Cycle test', 'Pour tests')
    """, (cycle_code,))
    conn.execute("""
        INSERT INTO themes (id, code, nom, description, code_couleur,
                            ordre, cycle_code)
        VALUES (?, ?, ?, '', ?, 1, ?)
    """, (theme_id, 'TH99', 'Thème test', 'nombres', cycle_code))
    conn.execute("""
        INSERT INTO sequences_du_cycle (code, theme_id, cycle_code,
                                          numero, nom)
        VALUES (?, ?, ?, 1, 'Séquence test')
    """, (seq_code, theme_id, cycle_code))
    conn.execute("""
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code)
        VALUES (?, ?, ?)
    """, (f"sn_{uuid.uuid4().hex[:8]}", niveau, seq_code))
    conn.commit()
    return seq_code


def _ajouter_exo(conn, niveau, sequence, num, serie, corrige='',
                  variables=''):
    """Insère un exercice avec corrigé et variables xint optionnels.

    Note : la table exercices n'a pas de colonne etat_code (contrairement
    à cartes_automatisme). Le filtrage métier se fait par d'autres moyens
    (présence dans la séquence, etc.). On insère simplement sans état.
    Les champs `serie` (texte long) et `serie_code` (code court) sont
    redondants : on met la même valeur dans les deux pour simplicité.

    v0.13.6.5.2.1 — Paramètre `variables` ajouté pour tester l'émission
    des définitions xint dans livret_corriges.
    """
    conn.execute("""
        INSERT INTO exercices
            (id, serie, niveau, sequence, num, serie_code, fichier,
             enonce, corrige, variables)
        VALUES (?, ?, ?, ?, ?, ?, '', '', ?, ?)
    """, (f"ex_{uuid.uuid4().hex[:8]}", serie, niveau, sequence, num,
          serie, corrige, variables))


def _ajouter_carte(conn, niveau, sequence, num, type_tech='fixe',
                   nom='', recto='RECTO', verso='VERSO', variables='',
                   etat='valide'):
    """Insère une carte d'automatisme.

    CHECK constraint en BDD : (lien_type, lien_id) doit être :
      - (NULL, NULL), OU
      - (notion|methode, <id non-NULL>)
    Pour simplicité de test : on insère sans lien (NULL, NULL).
    """
    conn.execute("""
        INSERT INTO cartes_automatisme
            (id, niveau, sequence, num, type_pedago, type_tech,
             titre, lien_type, lien_id, recto, verso, variables,
             etat_code, ordre)
        VALUES (?, ?, ?, ?, 'definition', ?, ?, NULL, NULL,
                ?, ?, ?, ?, 0)
    """, (f"c_{uuid.uuid4().hex[:8]}", niveau, sequence, num,
          type_tech, nom, recto, verso, variables, etat))


# ── 1. livret_fiches ─────────────────────────────────────────────────────────


def test_livret_fiches_genere_tex_valide(store_avec_paquet):
    """Niveau minimal : .tex valide avec page de garde."""
    with _conn(store_avec_paquet) as conn:
        _setup_minimal_niveau(conn, 'N10')
        tex = generer_livret_fiches(conn, 'N10', options={})
    assert r'\documentclass' in tex
    assert r'\begin{document}' in tex
    assert r'\end{document}' in tex
    assert 'Livret de fiches' in tex
    assert tex.count('{') == tex.count('}')


def test_livret_fiches_mode_completes_redefinit_acompleter(store_avec_paquet):
    """Mode 'completes' (version prof) : \\acompleter redéfini."""
    with _conn(store_avec_paquet) as conn:
        _setup_minimal_niveau(conn, 'N10')
        tex = generer_livret_fiches(
            conn, 'N10', options={'version_fiches': 'completes'},
        )
    assert r'\renewcommand{\acompleter}' in tex


def test_livret_fiches_mode_a_completer_pas_redefini(store_avec_paquet):
    """Mode défaut 'a_completer' : pas de redéfinition (souligné par défaut)."""
    with _conn(store_avec_paquet) as conn:
        _setup_minimal_niveau(conn, 'N10')
        tex = generer_livret_fiches(conn, 'N10', options={})
    assert r'\renewcommand{\acompleter}' not in tex


def test_livret_fiches_niveau_inconnu_leve_lookup_error(store_avec_paquet):
    """Niveau sans cycle → LookupError."""
    with _conn(store_avec_paquet) as conn:
        with pytest.raises(LookupError):
            generer_livret_fiches(conn, 'N99', options={})


# ── 2. livret_corriges ───────────────────────────────────────────────────────


def test_livret_corriges_genere_tex_valide(store_avec_paquet):
    """Niveau minimal vide : .tex valide."""
    with _conn(store_avec_paquet) as conn:
        _setup_minimal_niveau(conn, 'N10')
        tex = generer_livret_corriges(conn, 'N10', options={})
    assert r'\documentclass' in tex
    assert r'\begin{document}' in tex
    assert r'\end{document}' in tex
    assert 'Livret de corrigés' in tex
    assert tex.count('{') == tex.count('}')


def test_livret_corriges_series_par_defaut(store_avec_paquet):
    """Par défaut : R/AE et F inclus, A et E non."""
    with _conn(store_avec_paquet) as conn:
        _setup_minimal_niveau(conn, 'N10')
        for serie in ['R', 'AE', 'F', 'A', 'E']:
            _ajouter_exo(conn, 'N10', 'S01', 1, serie,
                         corrige=f'CORR_{serie}')
        conn.commit()
        tex = generer_livret_corriges(conn, 'N10', options={})

    assert "Révisions / activités d'entrée" in tex
    assert 'Série F' in tex
    assert 'CORR_R' in tex or 'CORR_AE' in tex
    assert 'CORR_F' in tex
    # CORR_A et CORR_E ne doivent pas apparaître. Mais attention à
    # CORR_AE qui contient 'CORR_A' comme préfixe. On vérifie l'absence
    # de "Série A" (libellé exact) à la place.
    assert 'Série A\\}' not in tex.replace('Série AE', '')
    assert 'Série E (entraînement)' not in tex


def test_livret_corriges_toutes_series(store_avec_paquet):
    """Avec toutes les options : 4 séries présentes."""
    with _conn(store_avec_paquet) as conn:
        _setup_minimal_niveau(conn, 'N10')
        for serie in ['R', 'AE', 'F', 'A', 'E']:
            _ajouter_exo(conn, 'N10', 'S01', 1, serie,
                         corrige=f'CORR_{serie}')
        conn.commit()
        tex = generer_livret_corriges(
            conn, 'N10',
            options={
                'inclure_serie_r_ae': True,
                'inclure_serie_f':    True,
                'inclure_serie_a':    True,
                'inclure_serie_e':    True,
            },
        )
    for serie in ['R', 'F', 'A', 'E']:
        assert f'CORR_{serie}' in tex, f"manque CORR_{serie}"


def test_livret_corriges_exo_sans_corrige_ignore(store_avec_paquet):
    """Un exo sans corrigé n'apparaît pas dans le livret."""
    with _conn(store_avec_paquet) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_exo(conn, 'N10', 'S01', 1, 'F', corrige='')
        _ajouter_exo(conn, 'N10', 'S01', 2, 'F', corrige='SENTINELLE_VALIDE')
        conn.commit()
        tex = generer_livret_corriges(conn, 'N10', options={})
    assert 'SENTINELLE_VALIDE' in tex
    # 1 seule entrée Exercice X. (l'exo 2)
    assert tex.count(r'Exercice 1.') + tex.count(r'Exercice 2.') == 1


def test_livret_corriges_ordre_des_series(store_avec_paquet):
    """L'ordre canonique AE, F, A, E est respecté à la lecture."""
    with _conn(store_avec_paquet) as conn:
        _setup_minimal_niveau(conn, 'N10')
        # Insertion dans l'ordre inverse
        for serie in ['E', 'A', 'F', 'AE']:
            _ajouter_exo(conn, 'N10', 'S01', 1, serie,
                         corrige=f'CORR_{serie}')
        conn.commit()
        tex = generer_livret_corriges(
            conn, 'N10',
            options={
                'inclure_serie_r_ae': True,
                'inclure_serie_f':    True,
                'inclure_serie_a':    True,
                'inclure_serie_e':    True,
            },
        )
    pos_ae_lbl = tex.find("Révisions / activités d'entrée")
    pos_f_lbl = tex.find('Série F')
    pos_a_lbl = tex.find('Série A}')  # libellé strict (pas Série AE)
    pos_e_lbl = tex.find('Série E (entraînement)')
    assert -1 < pos_ae_lbl < pos_f_lbl < pos_a_lbl < pos_e_lbl


def test_livret_corriges_variables_xint_emises_avant_corriges(store_avec_paquet):
    """v0.13.6.5.2.1 — Bugfix : les définitions \\xintdefiivar de
    chaque exo doivent être émises AVANT leur \\xintiieval dans le
    corrigé, sinon erreur de compilation.

    Pattern aligné sur services.livret_sequence : variables émises au
    top du document avant le bloc d'exercices/corrigés.
    """
    with _conn(store_avec_paquet) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_exo(
            conn, 'N10', 'S01', 1, 'A',
            corrige=r'Le résultat est $\xintiieval{N10S01A01_x}$.',
            variables=r'\xintdefiivar N10S01A01_x := randrange(1,10);',
        )
        conn.commit()
        tex = generer_livret_corriges(
            conn, 'N10',
            options={'inclure_serie_r_ae': True, 'inclure_serie_f': True,
                     'inclure_serie_a': True, 'inclure_serie_e': True},
        )

    pos_defin = tex.find(r'\xintdefiivar N10S01A01_x')
    pos_usage = tex.find(r'\xintiieval{N10S01A01_x}')
    assert pos_defin != -1, "\\xintdefiivar n'apparaît pas dans le .tex"
    assert pos_usage != -1, "\\xintiieval n'apparaît pas dans le .tex"
    assert pos_defin < pos_usage, (
        f"définition \\xintdefiivar (pos {pos_defin}) doit précéder "
        f"l'usage \\xintiieval (pos {pos_usage})"
    )


def test_livret_corriges_envs_referencés_par_variables_sont_dans_preambule(
        store_avec_paquet, monkeypatch):
    """v0.15.1.1 — Bugfix : les environnements (et macros) utilisés DANS
    les `variables` d'un exo doivent aussi être détectés par l'analyse
    du préambule, sinon ils ne sont pas inlinés et la compilation échoue.

    Cas réel rencontré (cf. /mnt/.../livret_de_corriges.tex de Laurent
    le 22 mai 2026) : un exo dont les `variables` contiennent
    ``\\newcommand{\\myDef}[2]{\\begin{boitePaleNoBreak}{#1} #2
    \\end{boitePaleNoBreak}}``. Sans la correction, `boitePaleNoBreak`
    n'est jamais analysée (livret_corriges n'ajoutait que le `corrige`
    aux textes analysés, pas les `variables`).

    Stratégie de test : on espionne `extraire_utilisations` pour
    capturer le texte qu'on lui passe — sans la correction, ce texte
    contient seulement le corrigé ; avec la correction, il contient
    aussi les variables.

    Pattern aligné sur services.livret_sequence (lignes 898-900).
    """
    from services import paquet_parseur

    appels = []
    extraire_reel = paquet_parseur.extraire_utilisations
    def extraire_espion(texte):
        appels.append(texte)
        return extraire_reel(texte)

    # Patcher la fonction LÀ OÙ elle est importée (livret_corriges l'a
    # importée dans son propre namespace).
    monkeypatch.setattr(
        'services.livret_corriges.extraire_utilisations', extraire_espion,
    )

    with _conn(store_avec_paquet) as conn:
        _setup_minimal_niveau(conn, 'N10')
        # Variables qui définissent \myDef qui utilise un env
        # `boitePaleBreakNoTitle`. Le `corrige` lui-même n'utilise QUE
        # \myDef — donc sans la correction, l'analyse statique du
        # corrigé seul ne verrait jamais `boitePaleBreakNoTitle`.
        _ajouter_exo(
            conn, 'N10', 'S01', 1, 'A',
            corrige=r'\myDef{Titre}{Le contenu.}',
            variables=(
                r'\newcommand{\myDef}[2]{'
                r'\begin{boitePaleBreakNoTitle} #2 \end{boitePaleBreakNoTitle}}'
            ),
        )
        conn.commit()
        generer_livret_corriges(
            conn, 'N10',
            options={'inclure_serie_r_ae': True, 'inclure_serie_f': True,
                     'inclure_serie_a': True, 'inclure_serie_e': True},
        )

    # Au moins un appel à extraire_utilisations doit avoir été fait,
    # avec un texte qui contient à la fois le corrigé ET les variables.
    assert appels, "extraire_utilisations n'a pas été appelée"
    texte_analyse = appels[0]
    assert r'\myDef{Titre}' in texte_analyse, (
        "Le corrigé doit être dans le texte d'analyse (sanity)"
    )
    # Le test principal : les variables (qui contiennent l'env) doivent
    # AUSSI être dans le texte d'analyse, sinon l'env n'est pas vu.
    assert 'boitePaleBreakNoTitle' in texte_analyse, (
        "Les `variables` doivent être incluses dans le texte d'analyse "
        "du préambule, pour que les environnements/macros qu'elles "
        "utilisent (transitivement) soient détectés et inlinés. "
        "Sans cela, la compilation LaTeX échoue avec « Environment "
        "boitePaleBreakNoTitle undefined ». Texte d'analyse actuel : "
        f"{texte_analyse!r}"
    )


# ── 3. livret_cartes_recap ───────────────────────────────────────────────────


def test_livret_cartes_recap_genere_tex_valide(sqlite_store):
    """Niveau sans cartes : .tex valide avec page de garde.

    Pas besoin de paquet_definitions : préambule statique.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        tex = generer_livret_cartes_recap(conn, 'N10', options={})
    assert r'\documentclass' in tex
    assert 'Récap des cartes' in tex
    assert tex.count('{') == tex.count('}')


def test_livret_cartes_recap_charge_siunitx(sqlite_store):
    """v0.13.6.5.2.1 — Bugfix : siunitx doit être chargé pour les
    cartes qui utilisent \\num{...} (4 cartes N10 + des paramétrées).
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        tex = generer_livret_cartes_recap(conn, 'N10', options={})
    assert r'\usepackage{siunitx}' in tex


def test_livret_cartes_recap_preambule_complet(sqlite_store):
    """Préambule charge les bons paquets seqenseigne.

    v0.15.1.3.1 — Plus d'imports explicites de tcolorbox, tabularray ou
    xintexpr : ils sont amenés transitivement par seqenseigne-core (qui
    charge xintexpr + tabularray) et seqenseigne-theme (qui charge
    tcolorbox AVEC options [theorems,breakable,skins] — d'où Option
    clash si on tente de le charger sans options au préalable).
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        tex = generer_livret_cartes_recap(conn, 'N10', options={})
    assert r'\usepackage{seqenseigne-carte-automatisme}' in tex
    assert r'\usepackage{seqenseigne-core}' in tex
    assert r'\usepackage{seqenseigne-theme}' in tex
    # Ces paquets NE doivent PAS être déclarés explicitement (option clash
    # avec seqenseigne-theme pour tcolorbox ; redondance pour les autres)
    assert r'\usepackage{tcolorbox}' not in tex, (
        "tcolorbox ne doit PAS être chargé explicitement (Option clash "
        "avec seqenseigne-theme qui le charge avec options)."
    )
    assert r'\usepackage{xintexpr}' not in tex, (
        "xintexpr ne doit PAS être chargé explicitement (déjà chargé "
        "par seqenseigne-core)."
    )
    assert r'\usepackage{tabularray}' not in tex, (
        "tabularray ne doit PAS être chargé explicitement (déjà chargé "
        "par seqenseigne-core avec lib booktabs)."
    )


def test_livret_cartes_recap_carte_fixe(sqlite_store):
    """Carte fixe : son recto et verso apparaissent.

    v0.15.2.2 : utilise l'environnement `seqCarteRecap` avec
    `\\seqCarteRecapAjouteCarte[opts]{vars}{recto}{verso}` (la macro
    .dtx gère elle-même les 2 flux d'écriture recto/verso).
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(conn, 'N10', 'S01', 1,
                       recto='SENTINEL_RECTO', verso='SENTINEL_VERSO')
        conn.commit()
        tex = generer_livret_cartes_recap(conn, 'N10', options={})
    assert 'SENTINEL_RECTO' in tex
    assert 'SENTINEL_VERSO' in tex
    # Doit utiliser l'environnement seqCarteRecap (nouvelle API v0.15.2.2)
    assert r'\begin{seqCarteRecap}' in tex
    assert r'\seqCarteRecapAjouteLigneCartes' in tex
    # \seqInitCartes doit être présent (initialise les flux d'écriture)
    assert r'\seqInitCartes' in tex


def test_livret_cartes_recap_seqCarteAuto_pas_commente(sqlite_store):
    r"""v0.15.2.2 — Garde-fou hérité : aucune occurrence de macro carte
    ne doit être commentée accidentellement par un % sur la même ligne.

    Adapté : on vérifie pour \seqCarteRecapAjouteCarte (la macro publique
    utilisée par le nouveau récap, qui gère elle-même les 2 flux d'écriture).
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(conn, 'N10', 'S01', 1,
                       recto='SENTINEL_RECTO', verso='SENTINEL_VERSO')
        conn.commit()
        tex = generer_livret_cartes_recap(conn, 'N10', options={})

    for macro in (r'\seqCarteRecapAjouteLigneCartes',
                  r'\begin{seqCarteRecap}'):
        lignes = [l for l in tex.splitlines() if macro in l]
        assert lignes, f"Aucune ligne avec {macro} dans le .tex"
        for ligne in lignes:
            avant = ligne.split(macro)[0]
            commente = False
            i = 0
            while i < len(avant):
                if avant[i] == '%' and (i == 0 or avant[i-1] != '\\'):
                    commente = True
                    break
                i += 1
            assert not commente, (
                f"La ligne `{ligne}` commente {macro} avec un % :\n"
                f"  avant = {avant!r}"
            )


def test_livret_cartes_recap_non_valide_ignoree(sqlite_store):
    """Cartes en_cours ignorées."""
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(conn, 'N10', 'S01', 1,
                       recto='NEVER_RECTO', etat='en_cours')
        conn.commit()
        tex = generer_livret_cartes_recap(conn, 'N10', options={})
    assert 'NEVER_RECTO' not in tex


def test_livret_cartes_recap_carte_parametree_variables_dans_appel(sqlite_store):
    """v0.15.2.2 — Carte paramétrée : ses variables xint apparaissent
    LITTÉRALEMENT dans l'appel \\seqCarteRecapAjouteCarte (bloc #2 de la
    macro), JAMAIS substituées en Python.

    Plus de substitution Python (cf. cadrage P1=alpha). Les variables
    xint sont insérées telles quelles dans le bloc {vars} de la macro,
    qui les exécute côté LaTeX dans un groupe partagé entre recto et
    verso (via les flux d'écriture recaprecto.tex / recapverso.tex).
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(
            conn, 'N10', 'S01', 1,
            type_tech='parametree',
            recto=r'$\xintiieval{N10S01C01_p}$',
            verso=r'$\xintiieval{N10S01C01_p}$',
            variables=r'\xintdefiivar N10S01C01_p := randrange(1,10);',
        )
        conn.commit()
        tex = generer_livret_cartes_recap(conn, 'N10', options={})

    # Les \xintdefiivar DOIVENT être présents (nouvelle stratégie)
    assert r'\xintdefiivar N10S01C01_p' in tex, (
        "Les variables xint doivent être présentes dans le .tex : "
        "elles sont évaluées par xintexpr côté LaTeX, pas substituées."
    )
    # Le nom de variable DOIT apparaître dans recto ET verso (le partage
    # de valeur est assuré par la macro côté .dtx, pas par substitution).
    assert tex.count('N10S01C01_p') >= 3, (
        "Le nom de variable doit apparaître dans variables + recto + verso "
        "(le partage de valeur est assuré côté LaTeX, pas côté Python)."
    )
    # \seqCarteRecapAjouteCarte présente (la macro intègre variables, recto et verso)
    assert r'\seqCarteRecapAjouteLigneCartes' in tex


def test_livret_cartes_recap_un_env_par_bloc_de_16(sqlite_store):
    """v0.15.2.2 — Cartes de séquences différentes : toutes mélangées,
    triées par séquence puis num, et **découpées en blocs de 16 cartes
    maximum** (cf. Q1=A + Q saut de page : un env `seqCarteRecap` produit
    une paire de pages recto+verso, et son `tblr` interne ne gère pas le
    saut de page automatique).

    Avec 2 cartes seulement (cas de ce test minimal), un seul bloc suffit
    donc un seul environnement `seqCarteRecap`.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        conn.execute("""
            INSERT INTO sequences_du_cycle (code, theme_id, cycle_code,
                                              numero, nom)
            SELECT 'S02', theme_id, cycle_code, 2, 'Seq 2'
              FROM sequences_du_cycle WHERE code='S01'
        """)
        conn.execute("""
            INSERT INTO sequences_par_niveau (id, niveau, sequence_code)
            VALUES (?, 'N10', 'S02')
        """, (f"sn_S02_{uuid.uuid4().hex[:6]}",))
        _ajouter_carte(conn, 'N10', 'S01', 1, recto='IN_S01')
        _ajouter_carte(conn, 'N10', 'S02', 1, recto='IN_S02')
        conn.commit()
        tex = generer_livret_cartes_recap(conn, 'N10', options={})

    # 2 cartes seulement → 1 seul bloc → 1 seul environnement seqCarteRecap
    n_env = tex.count(r'\begin{seqCarteRecap}')
    assert n_env == 1, (
        f"2 cartes tiennent dans 1 bloc de 16 ; attendu 1 environnement "
        f"seqCarteRecap, obtenu {n_env}."
    )
    assert 'IN_S01' in tex
    assert 'IN_S02' in tex
    # Et l'ordre doit être S01 avant S02 (tri par séquence puis num)
    assert tex.find('IN_S01') < tex.find('IN_S02')


def test_livret_cartes_recap_decoupage_en_blocs_de_16(sqlite_store):
    """v0.15.2.2 — Avec plus de 16 cartes, le livret émet un environnement
    `seqCarteRecap` par bloc de 16 cartes maximum.

    Le `tblr` interne de `seqCarteRecap` ne gère pas de saut de page,
    donc pour dépasser 16 cartes par paire de pages on enchaîne plusieurs
    environnements. Le `\\clearpage` séparant les paires est émis en
    interne par l'environnement (`.dtx`), pas par Python.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        # 35 cartes → ceil(35/16) = 3 blocs
        for i in range(1, 36):
            _ajouter_carte(conn, 'N10', 'S01', i, recto=f'R{i:02d}',
                           verso=f'V{i:02d}')
        conn.commit()
        tex = generer_livret_cartes_recap(conn, 'N10', options={})

    n_env = tex.count(r'\begin{seqCarteRecap}')
    assert n_env == 3, (
        f"35 cartes → ceil(35/16) = 3 blocs de seqCarteRecap ; "
        f"obtenu {n_env}."
    )
    # Bordures de blocs : carte 16 et 17 doivent être dans des envs
    # différents → entre les deux on a un \end{seqCarteRecap} puis
    # \begin{seqCarteRecap}.
    pos_16 = tex.find('{R16}')
    pos_17 = tex.find('{R17}')
    assert pos_16 < pos_17
    inter = tex[pos_16:pos_17]
    assert r'\end{seqCarteRecap}' in inter
    assert r'\begin{seqCarteRecap}' in inter
    assert inter.find(r'\end{seqCarteRecap}') < inter.find(r'\begin{seqCarteRecap}')


def test_livret_cartes_recap_decoupage_en_lignes(sqlite_store):
    """v0.32.4 — Le récap appelle \\seqCarteRecapAjouteLigneCartes une fois par
    ligne de 4 cartes (rectos dans l'ordre, versos en miroir gérés par la macro).

    Test : 18 cartes → ceil(18/4) = 5 appels de ligne.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        for i in range(1, 19):
            _ajouter_carte(conn, 'N10', 'S01', i, recto=f'R{i:02d}')
        conn.commit()
        tex = generer_livret_cartes_recap(conn, 'N10', options={})

    import math
    n_lignes = tex.count(r'\seqCarteRecapAjouteLigneCartes')
    assert n_lignes == math.ceil(18 / 4) == 5, (
        f"18 cartes → 5 lignes de 4 ; obtenu {n_lignes}."
    )
    assert r'\seqCarteRecapAjouteCarte[' not in tex


# ── 4. livret_cartes_planches ────────────────────────────────────────────────


def test_livret_cartes_planches_genere_tex_valide(sqlite_store):
    """Niveau minimal : .tex valide en A4 paysage.

    v0.15.2.2 — La géométrie A4 paysage n'est plus posée explicitement
    par le préambule Python : c'est seqenseigne-carte-automatisme.sty
    qui la fixe via `\\geometry{a4paper,landscape,margin=1mm,...}`
    (cf. .dtx ligne 114-118). On vérifie donc que le paquet est chargé,
    et la géométrie suivra.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        tex = generer_livret_cartes_planches(conn, 'N10', options={})
    assert r'\documentclass' in tex
    # seqenseigne-carte-automatisme.sty pose la géométrie A4 paysage
    assert r'\usepackage{seqenseigne-carte-automatisme}' in tex
    assert tex.count('{') == tex.count('}')


def test_livret_cartes_planches_charge_siunitx(sqlite_store):
    """v0.13.6.5.2.1 — Bugfix : siunitx doit être chargé pour les cartes
    qui utilisent \\num{...}.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        tex = generer_livret_cartes_planches(conn, 'N10', options={})
    assert r'\usepackage{siunitx}' in tex


def test_livret_cartes_planches_macros_publiques(sqlite_store):
    """v0.15.2.2 — Le code utilise UNIQUEMENT la macro publique unifiée
    `\\seqCartePlanche` (gère fixe ET paramétré) et JAMAIS les sous-macros
    internes `\\seq@*`, `\\seqca@*` ni `\\makeatletter`.

    La macro \\seqCartePlanche prend 3 arguments : {vars}{recto}{verso},
    vars pouvant être vide pour une carte fixe.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(conn, 'N10', 'S01', 1, recto='R1', verso='V1')
        conn.commit()
        tex = generer_livret_cartes_planches(conn, 'N10', options={})

    debut = tex.find(r'\begin{document}')
    corps = tex[debut:]
    # Aucune sous-macro interne ni \makeatletter dans le corps
    assert r'\seq@' not in corps, (
        "Le corps ne doit plus contenir de \\seq@... (sous-macros internes)"
    )
    assert r'\seqca@' not in corps, (
        "Le corps ne doit plus contenir de \\seqca@... (sous-macros internes)"
    )
    assert r'\makeatletter' not in corps, (
        "Plus besoin de \\makeatletter avec les macros publiques"
    )
    # Carte FIXE → \seqCartePlanche (unifié)
    assert r'\seqCartePlanche' in corps, (
        "Pour une carte fixe, on doit utiliser \\seqCartePlanche (unifié)"
    )
    # Plus de référence aux anciennes macros pré-v0.15.2.2
    assert r'\seqCartePageRecto' not in corps, (
        "\\seqCartePageRecto a été remplacée par \\seqCartePlanche en v0.15.2.2"
    )
    assert r'\seqCartePageVerso' not in corps, (
        "\\seqCartePageVerso a été remplacée par \\seqCartePlanche en v0.15.2.2"
    )


def test_livret_cartes_planches_pas_de_miroir_horizontal(sqlite_store):
    """v0.15.2.2 — Cadrage P4 acté : impression recto-verso bord court,
    PAS de miroir horizontal côté Python (la macro \\seqCartePlanche émet
    recto et verso dans le même ordre).

    On vérifie en injectant 2 cartes et en confirmant que la sortie ne
    contient aucun signe d'inversion (pas de logique miroir Python).
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(conn, 'N10', 'S01', 1, recto='R_A', verso='V_A')
        _ajouter_carte(conn, 'N10', 'S01', 2, recto='R_B', verso='V_B')
        conn.commit()
        tex = generer_livret_cartes_planches(conn, 'N10', options={})

    # Chaque carte produit 1 seul appel \seqCartePlanche
    assert tex.count(r'\seqCartePlanche') == 2
    # v0.15.2.3 : chaque carte fixe est dupliquée en 16 cellules recto +
    # 16 cellules verso (pré-tirage suffixé). Le recto R_A apparaît donc
    # 16 fois (dans 16 \seqCelluleRecto), idem pour les autres.
    assert tex.count(r'\seqCelluleRecto{R_A}') == 16
    assert tex.count(r'\seqCelluleVerso{V_A}') == 16
    assert tex.count(r'\seqCelluleRecto{R_B}') == 16
    assert tex.count(r'\seqCelluleVerso{V_B}') == 16
    # Pas de miroir : recto et verso de chaque carte présents (même ordre)
    assert r'\seqCelluleRecto{R_A}' in tex
    assert r'\seqCelluleVerso{V_A}' in tex


def test_livret_cartes_planches_non_valide_ignoree(sqlite_store):
    """Cartes en_cours ignorées."""
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(conn, 'N10', 'S01', 1,
                       recto='NEVER_RECTO', etat='en_cours')
        conn.commit()
        tex = generer_livret_cartes_planches(conn, 'N10', options={})
    assert 'NEVER_RECTO' not in tex


def test_livret_cartes_planches_16_cartes_seize_planches(sqlite_store):
    """v0.15.2.2 — 16 cartes différentes : 16 planches (16 paires recto/verso).

    Chaque carte a sa propre planche avec 16 copies de la même carte,
    via la macro unifiée \\seqCartePlanche. La duplication ×16 est faite
    à l'intérieur de la macro côté .dtx (xintReplicate).
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        for i in range(1, 17):
            _ajouter_carte(conn, 'N10', 'S01', i,
                           recto=f'R{i}', verso=f'V{i}')
        conn.commit()
        tex = generer_livret_cartes_planches(conn, 'N10', options={})

    # 16 appels à \seqCartePlanche (1 par carte)
    assert tex.count(r'\seqCartePlanche') == 16
    # Chaque recto/verso (carte fixe) apparaît dans 16 cellules de SA planche.
    for i in range(1, 17):
        assert tex.count(f'\\seqCelluleRecto{{R{i}}}') == 16, f'manque R{i}'
        assert tex.count(f'\\seqCelluleVerso{{V{i}}}') == 16, f'manque V{i}'


def test_livret_cartes_planches_17_cartes_dix_sept_planches(sqlite_store):
    """v0.15.2.2 — 17 cartes : 17 planches (17 appels \\seqCartePlanche).

    Chaque planche montre 16 copies de la MÊME carte ; il y a donc 17
    planches (= 17 paires recto/verso) pour 17 cartes.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        for i in range(1, 18):
            _ajouter_carte(conn, 'N10', 'S01', i,
                           recto=f'R{i}', verso=f'V{i}')
        conn.commit()
        tex = generer_livret_cartes_planches(conn, 'N10', options={})

    n_planches = tex.count(r'\seqCartePlanche')
    assert n_planches == 17, (
        f"17 \\seqCartePlanche attendus, obtenu {n_planches}"
    )


def test_livret_cartes_planches_parametree_variables_dans_appel(sqlite_store):
    """v0.15.2.3 — Pour une carte paramétrée, les variables xint sont
    SUFFIXÉES _01.._16 (un tirage figé par cellule, cf. pré-tirage suffixé).

    Le bloc de tirage de la variable apparaît donc 16 fois (une par
    cellule), avec des suffixes distincts.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(
            conn, 'N10', 'S01', 1,
            type_tech='parametree',
            recto=r'R$\xintiieval{N10S01C01_v}$',
            verso=r'V$\xintiieval{N10S01C01_v}$',
            variables=r'\xintdefiivar N10S01C01_v := randrange(0,1000);',
        )
        conn.commit()
        tex = generer_livret_cartes_planches(conn, 'N10', options={})

    # Le bloc de tirage est suffixé : 16 déclarations (_01.._16)
    assert tex.count(r'\xintdefiivar N10S01C01_v_') == 16, (
        "16 tirages suffixés attendus (1 par cellule de la planche)."
    )
    # Les suffixes extrêmes existent
    assert r'\xintdefiivar N10S01C01_v_01' in tex
    assert r'\xintdefiivar N10S01C01_v_16' in tex
    # Le contenu référence la variable suffixée (recto + verso, cellule 01)
    assert r'\xintiieval{N10S01C01_v_01}' in tex


def test_livret_cartes_planches_parametree_recto_verso_meme_variable(sqlite_store):
    """v0.15.2.3 — Garde-fou : le recto et le verso d'une carte paramétrée
    référencent LA MÊME variable, suffixée de façon cohérente par cellule.

    Le partage de valeur recto/verso d'une cellule donnée est assuré par
    le suffixe commun : la cellule 01 du recto et la cellule 01 du verso
    référencent toutes deux `N10S01C01_v_01`, défini une seule fois dans
    les tirages.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(
            conn, 'N10', 'S01', 1,
            type_tech='parametree',
            recto=r'R$\xintiieval{N10S01C01_v}$',
            verso=r'V$\xintiieval{N10S01C01_v}$',
            variables=r'\xintdefiivar N10S01C01_v := randrange(0,1000);',
        )
        conn.commit()
        tex = generer_livret_cartes_planches(conn, 'N10', options={})

    # La variable suffixée _01 apparaît dans le recto ET le verso de la
    # cellule 01 (2 occurrences : R...v_01 et V...v_01).
    assert tex.count(r'\xintiieval{N10S01C01_v_01}') == 2, (
        "La variable suffixée _01 doit être référencée dans le recto ET "
        "le verso de la cellule 01 (partage de valeur via suffixe commun)."
    )
    # Et le tirage _01 est défini une seule fois
    assert tex.count(r'\xintdefiivar N10S01C01_v_01 :') == 1


def test_livret_cartes_recap_parametree_recto_verso_meme_variable(sqlite_store):
    """v0.15.2.2 — Garde-fou : pour le récap, recto et verso d'une carte
    paramétrée doivent référencer LA MÊME variable xint.

    Le partage de VALEUR à l'exécution est assuré par la macro
    \\seqCarteRecapAjouteCarte côté .dtx, qui exécute les variables une
    fois dans un groupe partagé entre les flux recaprecto.tex et
    recapverso.tex.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(
            conn, 'N10', 'S01', 1,
            type_tech='parametree',
            recto=r'Question : $\xintiieval{N10S01C01_v}$',
            verso=r'Réponse : $\xintiieval{N10S01C01_v}$',
            variables=r'\xintdefiivar N10S01C01_v := randrange(0,1000);',
        )
        conn.commit()
        tex = generer_livret_cartes_recap(conn, 'N10', options={})

    # \xintiieval{N10S01C01_v} apparaît dans recto ET verso (2 occurrences)
    assert tex.count(r'\xintiieval{N10S01C01_v}') == 2, (
        "La variable xint doit être référencée dans recto ET verso. "
        "Le partage de valeur est assuré côté .dtx."
    )


def test_livret_cartes_recap_xintfloateval_preserve(sqlite_store):
    r"""v0.15.2.2 — Garde-fou : `\xintfloateval{...}` DOIT être préservé
    dans le .tex (et non plus substitué par sa valeur).

    Inversion de sémantique vs v0.15.1.3.2 : plus de substitution Python
    (cf. cadrage P1=alpha). xintexpr évalue côté LaTeX, et les variantes
    \xintfloateval{...}, \xintiieval{...}, etc. apparaissent telles
    quelles dans le .tex final.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(
            conn, 'N10', 'S01', 13,
            type_tech='parametree',
            recto=r'$\seqFrac{N10S01C13_num}{100}$',
            verso=r'$\xintfloateval{N10S01C13_res}$',
            variables=(
                r'\xintdefiivar N10S01C13_num := randrange(100,1000);'
                '\n'
                r'\xintdeffloatvar N10S01C13_res := N10S01C13_num / 100;'
            ),
        )
        conn.commit()
        tex = generer_livret_cartes_recap(conn, 'N10', options={})

    # \xintfloateval{N10S01C13_res} DOIT être préservé (sera évalué côté LaTeX)
    assert r'\xintfloateval{N10S01C13_res}' in tex, (
        "\\xintfloateval{...} doit être préservé dans le .tex en v0.15.2.2 "
        "(plus de substitution Python — xintexpr évalue côté LaTeX)."
    )
    # \xintdeffloatvar préservé aussi
    assert r'\xintdeffloatvar N10S01C13_res' in tex


def test_livret_cartes_recap_pas_de_detection_python_only(sqlite_store):
    r"""v0.15.2.2 — Plus de détection Python d'incompatibilité xintexpr.

    Anciennement (v0.15.1.3.3), si la variable utilisait `float(x, n)`
    ou `int(x)` (non supportés par xintexpr), le code Python émettait
    un message d'erreur visible dans la carte. Avec la nouvelle
    stratégie (variables évaluées entièrement côté LaTeX), il n'y a
    plus de détection : si la variable utilise une syntaxe non
    supportée, c'est xintexpr qui plantera à la compilation.

    Ce test garantit qu'on n'a plus de détection résiduelle et que les
    variables sont émises telles quelles, pour traitement par xintexpr.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(
            conn, 'N10', 'S01', 13,
            type_tech='parametree',
            recto=r'Q : $\xintiieval{N10S01C13_n}$',
            verso=r'R : $\xintfloateval{N10S01C13_res}$',
            variables=(
                r'\xintdefiivar N10S01C13_n := randrange(10,999);'
                '\n'
                # Note : float(x, n) n'est pas supporté par xintexpr,
                # mais ce n'est plus à Python de le détecter en v0.15.2.2.
                r'\xintdeffloatvar N10S01C13_res := float(N10S01C13_n / 100,2);'
            ),
        )
        conn.commit()
        tex = generer_livret_cartes_recap(conn, 'N10', options={})

    # Plus de message d'erreur Python (la détection a été retirée)
    assert r'Erreur carte CA13' not in tex
    # Les variables sont émises littéralement, telles que définies en BDD
    assert r'\xintdeffloatvar N10S01C13_res := float(N10S01C13_n / 100,2)' in tex


def test_livret_cartes_planches_pas_de_detection_python_only(sqlite_store):
    r"""v0.15.2.2 — Idem pour les planches : plus de détection Python."""
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(
            conn, 'N10', 'S01', 13,
            type_tech='parametree',
            recto=r'Q : $\xintiieval{N10S01C13_n}$',
            verso=r'R : $\xintfloateval{N10S01C13_res}$',
            variables=(
                r'\xintdefiivar N10S01C13_n := randrange(10,999);'
                '\n'
                r'\xintdeffloatvar N10S01C13_res := float(N10S01C13_n / 100,2);'
            ),
        )
        conn.commit()
        tex = generer_livret_cartes_planches(conn, 'N10', options={})

    assert r'Erreur carte CA13' not in tex
    # v0.15.2.3 : les noms de variables sont suffixés par cellule. La
    # syntaxe `float(...)` est préservée (xintexpr l'évalue), avec les
    # noms suffixés. Cellule 01 :
    assert (r'\xintdeffloatvar N10S01C13_res_01 := '
            r'float(N10S01C13_n_01 / 100,2)') in tex


def test_livret_cartes_planches_variables_quo_passees_telles_quelles(
        sqlite_store):
    r"""v0.15.2.3 — La syntaxe xintexpr (`quo`, etc.) est préservée ;
    seuls les NOMS de variables déclarées sont suffixés.

    On vérifie que :
      - le bloc de tirage est suffixé _01.._16 (16 occurrences)
      - le mot-clé `quo` (opérateur xintexpr, PAS une variable) n'est
        jamais suffixé
      - la référence interne reste cohérente (n et q suffixés ensemble)
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10')
        _ajouter_carte(
            conn, 'N10', 'S01', 1,
            type_tech='parametree',
            recto=r'Q : $\xintiieval{N10S01C01_q}$',
            verso=r'R : $\xintiieval{N10S01C01_q}$',
            variables=(
                r'\xintdefiivar N10S01C01_n := randrange(100,1000);'
                '\n'
                r'\xintdefiivar N10S01C01_q := N10S01C01_n quo 60;'
            ),
        )
        conn.commit()
        tex = generer_livret_cartes_planches(conn, 'N10', options={})

    # 16 tirages suffixés de la variable n
    assert tex.count(r'\xintdefiivar N10S01C01_n_') == 16
    # Le mot-clé `quo` est préservé et N'EST PAS suffixé (pas de quo_01)
    assert 'quo_' not in tex, "Le mot-clé `quo` ne doit jamais être suffixé."
    # Référence interne cohérente pour la cellule 01 :
    assert 'N10S01C01_q_01 := N10S01C01_n_01 quo 60' in tex


# ── 5. Orchestrateur : producteurs enregistrés ───────────────────────────────


def test_chemin_artefact_par_doc_id(sqlite_store):
    """v0.13.6.5.2.1 — Bugfix : `chemin_artefact` doit inclure le doc_id
    dans le chemin pour éviter que plusieurs documents partageant le
    même cible_key (typiquement les types unitaires avec cible_id='unique')
    ne s'écrasent mutuellement.
    """
    from services import referentiel_documents_compilation as svc_cmp
    from pathlib import Path

    chemin_a = svc_cmp.chemin_artefact(
        sqlite_store, 'ref_X', 'doc_AAA', 'unique', 'tex',
    )
    chemin_b = svc_cmp.chemin_artefact(
        sqlite_store, 'ref_X', 'doc_BBB', 'unique', 'tex',
    )
    # Deux documents distincts avec même cible_key → chemins distincts
    assert chemin_a != chemin_b
    # Le doc_id doit être dans le chemin
    assert 'doc_AAA' in str(chemin_a)
    assert 'doc_BBB' in str(chemin_b)
    # Sous _artefacts/
    assert '_artefacts' in str(chemin_a)


def test_orchestrateur_4_nouveaux_types_enregistres():
    """Les 4 types précédemment 'à venir' sont maintenant enregistrés."""
    for type_doc in ['livret_fiches', 'livret_corriges',
                     'livret_cartes_recap', 'livret_cartes_planches']:
        assert type_doc in orch.REGISTRE, f"{type_doc} pas enregistré"


def test_orchestrateur_types_anciennement_a_venir_plus_de_stub(
        store_avec_paquet):
    """Les 4 producteurs ne lèvent plus type_non_implemente."""
    with _conn(store_avec_paquet) as conn:
        _setup_minimal_niveau(conn, 'N10')
        for type_doc in ['livret_fiches', 'livret_corriges',
                         'livret_cartes_recap', 'livret_cartes_planches']:
            producteur = orch.REGISTRE[type_doc]
            try:
                tex = producteur(conn, {'niveau': 'N10'}, {}, [], [])
                assert isinstance(tex, str)
                assert r'\documentclass' in tex
            except orch.ProducteurErreur as e:
                if e.code == 'type_non_implemente':
                    pytest.fail(
                        f"{type_doc} lève encore type_non_implemente"
                    )
                raise


def test_orchestrateur_producteurs_signalent_cible_invalide(sqlite_store):
    """Sans niveau dans la cible : ProducteurErreur(code='cible_invalide')."""
    with _conn(sqlite_store) as conn:
        for type_doc in ['livret_fiches', 'livret_corriges',
                         'livret_cartes_recap', 'livret_cartes_planches']:
            producteur = orch.REGISTRE[type_doc]
            with pytest.raises(orch.ProducteurErreur) as ei:
                producteur(conn, {}, {}, [], [])
            assert ei.value.code == 'cible_invalide'
