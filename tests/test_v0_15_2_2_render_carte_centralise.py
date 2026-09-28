r"""tests/test_v0_15_2_2_render_carte_centralise.py — v0.15.2.2

Tests du module render_carte_centralise après refonte v0.15.2.2 (alignement
sur la nouvelle API du paquet seqenseigne-carte-automatisme : 3 wrappers
au lieu de 4, macros publiques renommées).

Vérifie que les 3 wrappers produisent le code LaTeX attendu :
- rendre_carte_isole : pour atelier de prévisualisation (\seqCarteAutomatisme)
- rendre_carte_recap : pour cellule dans seqCarteRecap
  (\seqCarteRecapAjouteCarte, 1 macro pour 2 flux d'écriture côté .dtx)
- rendre_carte_planche : pour planche élève (\seqCartePlanche, unifié
  fixe/paramétré, vars vide pour fixe)

Toutes les variables xint sont émises côté LaTeX (jamais substituées en
Python). Le partage des valeurs recto/verso est assuré par les flux
d'écriture du .dtx, pas par substitution Python.
"""
from __future__ import annotations
import uuid

import pytest

from services.render_carte_centralise import (
    rendre_carte_isole,
    rendre_carte_recap,
    rendre_carte_planche,
    resoudre_code_couleur,
    resoudre_libelle_type_pedago,
)


def _conn(store):
    """Helper aligné sur test_v0_13_6_5_2 : store._conn() est déjà un CM."""
    return store._conn()


def _setup_minimal_niveau(conn, niveau='N10', sequence='S01',
                            code_couleur='nombres'):
    """Crée le minimum BDD pour les lookups (param_niveaux + thème + séquence)."""
    cycle_code = 'C04'
    theme_id = f"th_{uuid.uuid4().hex[:8]}"
    conn.execute(
        "INSERT OR IGNORE INTO cycles (code, nom, description) VALUES (?, ?, ?)",
        (cycle_code, 'Cycle test', ''),
    )
    conn.execute(
        "INSERT INTO themes (id, code, nom, description, code_couleur, ordre, "
        "cycle_code) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (theme_id, 'TH99', 'Thème test', '', code_couleur, 1, cycle_code),
    )
    conn.execute(
        "INSERT INTO sequences_du_cycle (code, theme_id, cycle_code, numero, "
        "nom) VALUES (?, ?, ?, ?, ?)",
        (sequence, theme_id, cycle_code, 1, 'Séquence test'),
    )
    conn.execute(
        "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
        "VALUES (?, ?, ?)",
        (f"sn_{uuid.uuid4().hex[:8]}", niveau, sequence),
    )


def _carte_fixe(niveau='N10', sequence='S01', num=1,
                recto='RECTO_TEST', verso='VERSO_TEST', type_pedago='calcul'):
    """Construit un dict carte fixe pour les tests."""
    return {
        'id': f"c_{uuid.uuid4().hex[:8]}",
        'niveau': niveau, 'sequence': sequence, 'num': num,
        'type_pedago': type_pedago, 'type_tech': 'fixe',
        'titre': '', 'recto': recto, 'verso': verso, 'variables': '',
    }


def _carte_parametree(niveau='N10', sequence='S01', num=13,
                       recto='Q $\\xintiieval{N10S01C13_n}$',
                       verso='R $\\xintfloateval{N10S01C13_res}$',
                       variables=(
                           r'\xintdefiivar N10S01C13_n := randrange(10,999);'
                           '\n'
                           r'\xintdeffloatvar N10S01C13_res := N10S01C13_n / 100;'
                       ),
                       type_pedago='calcul'):
    """Construit un dict carte paramétrée pour les tests."""
    return {
        'id': f"c_{uuid.uuid4().hex[:8]}",
        'niveau': niveau, 'sequence': sequence, 'num': num,
        'type_pedago': type_pedago, 'type_tech': 'parametree',
        'titre': '', 'recto': recto, 'verso': verso, 'variables': variables,
    }


# ── Lookups utilitaires ─────────────────────────────────────────────────────

def test_resoudre_libelle_type_pedago_connu():
    assert resoudre_libelle_type_pedago('definition') == 'Définition'
    assert resoudre_libelle_type_pedago('propriete') == 'Propriété'
    assert resoudre_libelle_type_pedago('calcul') == 'Calcul'


def test_resoudre_libelle_type_pedago_inconnu():
    # Capitalise le code en fallback
    assert resoudre_libelle_type_pedago('xxx') == 'Xxx'
    assert resoudre_libelle_type_pedago('') == 'Carte'


def test_resoudre_code_couleur_sequence_existante(sqlite_store):
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01', code_couleur='geometrie')
        cc = resoudre_code_couleur(conn, 'N10', 'S01')
    assert cc == 'geometrie'


def test_resoudre_code_couleur_sequence_inexistante(sqlite_store):
    with _conn(sqlite_store) as conn:
        cc = resoudre_code_couleur(conn, 'N99', 'S99')
    # Fallback CODE_COULEUR_DEFAUT = 'nombres'
    assert cc == 'nombres'


# ── rendre_carte_isole ──────────────────────────────────────────────────────

def test_rendre_carte_isole_fixe(sqlite_store):
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        carte = _carte_fixe()
        rendu = rendre_carte_isole(conn, carte)
    # API v0.15.2.2 : 1 clé 'corps' uniquement (pas de preambule_variables séparé)
    assert set(rendu.keys()) == {'corps'}
    assert r'\seqCarteAutomatisme' in rendu['corps']
    assert 'RECTO_TEST' in rendu['corps']
    assert 'VERSO_TEST' in rendu['corps']
    # Options présentes
    assert 'niveau=N10' in rendu['corps']
    assert 'sequence=S01' in rendu['corps']
    assert 'num=1' in rendu['corps']
    assert 'codecouleur={nombres}' in rendu['corps']
    # Pas de groupe {...} englobant pour une carte fixe (pas de variables)
    assert not rendu['corps'].startswith('{')


def test_rendre_carte_isole_parametree(sqlite_store):
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        carte = _carte_parametree()
        rendu = rendre_carte_isole(conn, carte)
    # Pour une carte paramétrée, le corps englobe { variables + appel } dans
    # un groupe LaTeX pour limiter la portée des \xintdefiivar et partager
    # les valeurs entre recto et verso.
    assert rendu['corps'].lstrip().startswith('{')
    assert rendu['corps'].rstrip().endswith('}')
    # Variables xint d'origine, NON SUBSTITUÉES
    assert r'\xintdefiivar N10S01C13_n' in rendu['corps']
    assert r'\xintdeffloatvar N10S01C13_res' in rendu['corps']
    # Le corps utilise \xintiieval{...} et \xintfloateval{...} qui seront
    # évalués par LaTeX au moment de la compilation
    assert r'\xintiieval{N10S01C13_n}' in rendu['corps']
    assert r'\xintfloateval{N10S01C13_res}' in rendu['corps']
    # Et la macro publique reste \seqCarteAutomatisme
    assert r'\seqCarteAutomatisme' in rendu['corps']


def test_rendre_carte_isole_avec_titre(sqlite_store):
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        carte = _carte_fixe()
        carte['titre'] = 'Mon titre, avec virgule'
        rendu = rendre_carte_isole(conn, carte)
    # Le titre avec virgule doit être enveloppé d'accolades pour xkeyval
    assert 'nom={Mon titre, avec virgule}' in rendu['corps']


# ── rendre_carte_recap ──────────────────────────────────────────────────────

def test_rendre_carte_recap_fixe(sqlite_store):
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        carte = _carte_fixe()
        rendu = rendre_carte_recap(conn, carte)
    # API v0.15.2.2 : 1 clé 'appel' (la macro \seqCarteRecapAjouteCarte
    # gère elle-même les 2 flux d'écriture recto/verso)
    assert set(rendu.keys()) == {'appel'}
    assert r'\seqCarteRecapAjouteCarte' in rendu['appel']
    assert 'RECTO_TEST' in rendu['appel']
    assert 'VERSO_TEST' in rendu['appel']
    # codecouleur PRÉSENTE dans les options (chaque carte porte sa couleur,
    # cf. nouvelle API : l'env seqCarteRecap n'a plus d'option codecouleur)
    assert 'codecouleur={nombres}' in rendu['appel']
    # Bloc vars vide pour une carte fixe
    # La macro a 3 arguments : {vars}{recto}{verso}.
    # Pour une fixe : {}{RECTO_TEST}{VERSO_TEST}
    assert '{}{RECTO_TEST}{VERSO_TEST}' in rendu['appel']


def test_rendre_carte_recap_parametree(sqlite_store):
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        carte = _carte_parametree()
        rendu = rendre_carte_recap(conn, carte)
    # Variables xint dans le bloc #2 de la macro
    assert r'\xintdefiivar N10S01C13_n' in rendu['appel']
    assert r'\xintdeffloatvar N10S01C13_res' in rendu['appel']
    # Les \xint*eval restent intacts dans le recto et le verso —
    # pas de substitution Python
    assert r'\xintiieval{N10S01C13_n}' in rendu['appel']
    assert r'\xintfloateval{N10S01C13_res}' in rendu['appel']


def test_rendre_carte_recap_pas_de_substitution_python(sqlite_store):
    """v0.15.2.2 — Garde-fou : aucune valeur ne doit être substituée
    côté Python. Tout reste sous forme symbolique pour LaTeX.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        carte = _carte_parametree()
        rendu = rendre_carte_recap(conn, carte)
    # Aucun chiffre substitué (les variables restent sous forme \xintiieval{NAME})
    assert 'N10S01C13_n' in rendu['appel'], \
        "Le nom de variable doit rester intact (pas substitué)"
    assert 'N10S01C13_res' in rendu['appel']


def test_rendre_carte_recap_fin_ligne_oui(sqlite_store):
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        carte = _carte_fixe()
        rendu = rendre_carte_recap(conn, carte, fin_ligne=True)
    # finLigne=oui doit apparaître dans les options
    assert 'finLigne=oui' in rendu['appel']


def test_rendre_carte_recap_fin_ligne_non(sqlite_store):
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        carte = _carte_fixe()
        rendu = rendre_carte_recap(conn, carte, fin_ligne=False)
    # finLigne ne doit PAS être passé : la valeur par défaut côté .dtx
    # est 'non' (cf. \define@cmdkey[seqca]{addrecap}{finLigne}[non])
    assert 'finLigne' not in rendu['appel']


# ── rendre_carte_planche (unifié fixe + paramétré) ─────────────────────────

def test_rendre_carte_planche_fixe(sqlite_store):
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01', code_couleur='nombres')
        carte = _carte_fixe()
        rendu = rendre_carte_planche(conn, carte)
    # API v0.15.2.3 : 1 clé 'appel' (macro \seqCartePlanche, pré-tirage suffixé)
    assert set(rendu.keys()) == {'appel'}
    assert r'\seqCartePlanche' in rendu['appel']
    assert 'codecouleur={nombres}' in rendu['appel']
    # Carte fixe : 16 cellules recto + 16 cellules verso, contenu identique
    assert rendu['appel'].count(r'\seqCelluleRecto{RECTO_TEST}') == 16
    assert rendu['appel'].count(r'\seqCelluleVerso{VERSO_TEST}') == 16
    # Bloc tirages vide pour une carte fixe : ]\n{}\n{\seqCelluleRecto
    assert ']\n{}\n{\\seqCelluleRecto' in rendu['appel']


def test_rendre_carte_planche_parametree(sqlite_store):
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01', code_couleur='nombres')
        carte = _carte_parametree()
        rendu = rendre_carte_planche(conn, carte)
    appel = rendu['appel']
    assert r'\seqCartePlanche' in appel
    # v0.15.2.3 : les variables sont SUFFIXÉES _01.._16 dans les tirages.
    # Les noms suffixés doivent apparaître (cellules 01 et 16 au moins).
    assert r'\xintdefiivar N10S01C13_n_01' in appel
    assert r'\xintdefiivar N10S01C13_n_16' in appel
    assert r'\xintdeffloatvar N10S01C13_res_01' in appel
    # 16 cellules recto + 16 verso
    assert appel.count(r'\seqCelluleRecto{') == 16
    assert appel.count(r'\seqCelluleVerso{') == 16
    # Les références dans le contenu sont suffixées en accord
    assert 'N10S01C13_n_01' in appel
    assert 'N10S01C13_res_01' in appel
    # La référence interne (res := n / 100) reste cohérente par cellule
    assert 'N10S01C13_res_07 := N10S01C13_n_07 / 100' in appel
    # Options
    assert 'codecouleur={nombres}' in appel
    assert 'niveau=N10' in appel
    assert 'num=13' in appel


def test_rendre_carte_planche_accepte_fixe_et_parametree(sqlite_store):
    """v0.15.2.2 — Garde-fou : la macro unifiée \\seqCartePlanche accepte
    les deux types de carte. Pas d'assertion bloquante côté Python.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        # Fixe : OK, pas d'exception
        rendre_carte_planche(conn, _carte_fixe())
        # Paramétrée : OK, pas d'exception
        rendre_carte_planche(conn, _carte_parametree())


# ── Cohérence transverse ────────────────────────────────────────────────────

def test_variables_xint_meme_contenu_dans_tous_les_contextes(sqlite_store):
    """Garde-fou : les variables xint d'une carte paramétrée apparaissent
    intégralement dans les contextes isolé et récap (bloc tel quel).

    Pour la planche (v0.15.2.3), les variables sont SUFFIXÉES par cellule
    (_01.._16) — le bloc n'apparaît donc pas tel quel, mais chaque nom
    déclaré doit s'y retrouver sous forme suffixée.
    """
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        carte = _carte_parametree()
        r_isole = rendre_carte_isole(conn, carte)
        r_recap = rendre_carte_recap(conn, carte)
        r_planche = rendre_carte_planche(conn, carte)
    # Isolé et récap : bloc tel quel
    bloc_attendu = carte['variables'].strip()
    assert bloc_attendu in r_isole['corps']
    assert bloc_attendu in r_recap['appel']
    # Planche : chaque nom déclaré apparaît suffixé (au moins _01)
    from services.planche_suffixation import extraire_noms_variables
    for nom in extraire_noms_variables(carte['variables']):
        assert f'{nom}_01' in r_planche['appel'], (
            f"Le nom {nom} devrait apparaître suffixé _01 dans la planche")
