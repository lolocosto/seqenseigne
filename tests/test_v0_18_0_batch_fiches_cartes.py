"""tests/test_v0_18_0_batch_fiches_cartes.py — v0.18.0

Le rendu par lot accepte désormais les fiches de résumé et les cartes
d'automatisme (même mécanisme que notion/methode/exercice). On vérifie :
  - TYPES_VALIDES / ORDRE_TYPES étendus ;
  - recenser_atomes recense fiches et cartes, avec filtre par type ;
  - les identifiants sont formés correctement ;
  - fiche/carte ne sont PAS court-circuitées comme « vides » (le data de
    recensement ne contient pas leur contenu complet).
"""

import pytest

from services.compilation_batch import (
    recenser_atomes, Filtre, TYPES_VALIDES, ORDRE_TYPES,
    _identifiant_fiche, _identifiant_carte,
)


@pytest.fixture
def store_fiches_cartes(store):
    """Insère une fiche et deux cartes directement en BDD (pas de helper
    ecrire_* pour ces types dans le store)."""
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO fiches_resume (id, titre, num_fiche, niveau, sequence, etat_code) "
            "VALUES ('fi_1', 'Fiche test', 1, 'N10', 'S01', 'valide')"
        )
        conn.executemany(
            "INSERT INTO cartes_automatisme "
            "(id, niveau, sequence, num, titre, recto, verso, ordre, etat_code) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ('ca_1', 'N10', 'S01', 1, 'Carte 1', 'R', 'V', 0, 'en_cours'),
                ('ca_2', 'N11', 'S02', 2, 'Carte 2', 'R', 'V', 1, 'valide'),
            ],
        )
        conn.commit()
    return store


def test_types_valides_etendus():
    assert 'fiche' in TYPES_VALIDES
    assert 'carte' in TYPES_VALIDES
    assert ORDRE_TYPES.index('fiche') > ORDRE_TYPES.index('exercice')
    assert ORDRE_TYPES.index('carte') > ORDRE_TYPES.index('fiche')


def test_recensement_fiches(store_fiches_cartes):
    atomes = recenser_atomes(store_fiches_cartes, Filtre(type='fiche'))
    assert len(atomes) == 1
    assert atomes[0].type == 'fiche'
    assert atomes[0].id == 'fi_1'
    assert atomes[0].niveau == 'N10'
    assert atomes[0].identifiant == 'N10/S01/Fiche 01'


def test_recensement_cartes(store_fiches_cartes):
    atomes = recenser_atomes(store_fiches_cartes, Filtre(type='carte'))
    ids = {a.id for a in atomes}
    assert ids == {'ca_1', 'ca_2'}
    assert all(a.type == 'carte' for a in atomes)


def test_filtre_niveau_sur_cartes(store_fiches_cartes):
    atomes = recenser_atomes(
        store_fiches_cartes, Filtre(type='carte', niveau='N11'))
    assert [a.id for a in atomes] == ['ca_2']


def test_fiches_cartes_dans_recensement_global(store_fiches_cartes):
    atomes = recenser_atomes(store_fiches_cartes, Filtre())
    par_type = {}
    for a in atomes:
        par_type[a.type] = par_type.get(a.type, 0) + 1
    assert par_type.get('fiche', 0) >= 1
    assert par_type.get('carte', 0) >= 2


def test_identifiants():
    assert _identifiant_fiche(
        {'niveau': 'N10', 'sequence': 'S03', 'num_fiche': 5}
    ) == 'N10/S03/Fiche 05'
    assert _identifiant_carte(
        {'niveau': 'N11', 'sequence': 'S02', 'num': 12}
    ) == 'N11/S02/Carte 12'
    # Dégradé sans num
    assert 'Fiche' in _identifiant_fiche({'niveau': 'N10', 'sequence': 'S01'})


def test_ordre_tri_fiches_apres_exercices(store_fiches_cartes):
    # Ajoute un exercice N10/S01 pour vérifier l'ordre relatif.
    store_fiches_cartes.ecrire_exercices([{
        "id": "ex_z", "serie": "fondamental", "nom": "Exo",
        "objectifs": [], "variables": "", "enonce": "E", "corrige": "C",
        "niveau": "N10", "sequence": "S01", "num": 1, "serie_code": "F",
        "fichier": "x.tex",
    }])
    atomes = recenser_atomes(
        store_fiches_cartes, Filtre(niveau='N10', sequence='S01'))
    types_ordonnes = [a.type for a in atomes]
    # exercice doit précéder fiche, qui précède carte.
    if 'exercice' in types_ordonnes and 'fiche' in types_ordonnes:
        assert types_ordonnes.index('exercice') < types_ordonnes.index('fiche')
    if 'fiche' in types_ordonnes and 'carte' in types_ordonnes:
        assert types_ordonnes.index('fiche') < types_ordonnes.index('carte')


def test_carte_genere_tex_via_dispatch_v0_18_0_2(store_fiches_cartes):
    """v0.18.0.2 — Régression : le batch utilisait generer_tex_atome (4 types,
    sans carte) → les cartes échouaient avec « type_atome inconnu : 'carte' ».
    Le batch doit utiliser generer_tex_par_type (dispatch carte →
    generer_tex_carte). On vérifie que la génération du .tex d'une carte ne
    lève PAS ValueError 'type inconnu'."""
    from services.latex_rendu_atome import generer_tex_par_type
    with store_fiches_cartes._conn() as conn:
        # ca_1 a recto/verso renseignés dans la fixture.
        tex = generer_tex_par_type(conn, 'carte', 'ca_1')
    assert isinstance(tex, str)
    assert 'documentclass' in tex


def test_batch_n_utilise_plus_generer_tex_atome_seul():
    """v0.18.0.2 — Garde : le batch importe generer_tex_par_type (5 types),
    pas l'ancien generer_tex_atome (4 types) qui excluait les cartes."""
    import services.compilation_batch as cb
    src = __import__('inspect').getsource(cb)
    assert 'generer_tex_par_type' in src
    # L'appel de génération doit passer par le dispatch 5 types.
    assert 'generer_tex_par_type(conn' in src
