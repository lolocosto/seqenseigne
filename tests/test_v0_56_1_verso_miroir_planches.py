"""tests/test_v0_56_1_verso_miroir_planches.py — v0.56.1

Planches de cartes d'automatisme (16 exemplaires d'une carte) imprimées en
recto-verso BORD COURT : le verso doit être le miroir gauche-droite du recto, ligne
par ligne, sinon la réponse d'une cellule d'une carte PARAMÉTRÉE (un tirage par
cellule) ne tombe pas derrière son énoncé.

Correctif de la v0.29.0, perdu entre la v0.29.0 et la v0.32.5 ; son test
(test_v0_29_0_verso_miroir.py) avait été supprimé en v0.41.0 en croyant le miroir
passé côté LaTeX — seul le récap l'est (\\seqCarteRecapAjouteLigneCartes) ;
\\seqCartePlanche place les cellules dans l'ordre reçu. Voir doc/redemarrage_v0_56_1.md.
"""
from __future__ import annotations

import re
from pathlib import Path

from services.render_carte_centralise import (
    PLANCHE_NB_CELLULES, PLANCHE_NB_COLONNES, _miroir_horizontal_verso, rendre_carte_planche)
from tests.test_v0_15_2_2_render_carte_centralise import (  # noqa: F401
    _carte_fixe, _carte_parametree, _conn, _setup_minimal_niveau)

ORDRE_VERSO = [3, 2, 1, 0, 7, 6, 5, 4, 11, 10, 9, 8, 15, 14, 13, 12]


def _cellules(appel: str, cote: str) -> list[str]:
    return re.findall(r"\\seqCellule" + cote + r"\{(.*?)\}\}?$", appel, flags=re.M)


def test_miroir_inverse_chaque_ligne_de_quatre():
    assert PLANCHE_NB_COLONNES == 4 and PLANCHE_NB_CELLULES == 16
    assert _miroir_horizontal_verso(list(range(16))) == ORDRE_VERSO


def test_miroir_conserve_la_longueur_et_les_cellules():
    v = _miroir_horizontal_verso(list(range(16)))
    assert len(v) == 16 and sorted(v) == list(range(16))
    assert _miroir_horizontal_verso(v) == list(range(16))        # involution


def test_carte_parametree_reponse_derriere_son_enonce_apres_retournement_bord_court(sqlite_store):
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        appel = rendre_carte_planche(conn, _carte_parametree())['appel']
    recto, verso = _cellules(appel, 'Recto'), _cellules(appel, 'Verso')
    assert len(recto) == len(verso) == 16
    sfx = lambda txt: re.search(r"_(\d\d)\b", txt).group(1)          # noqa: E731
    # Retournement bord court : la cellule (ligne l, colonne c) du recto est derrière
    # la cellule (ligne l, colonne 3 - c) du verso ; elles doivent porter le même tirage.
    for i in range(16):
        l, c = divmod(i, 4)
        assert sfx(recto[i]) == sfx(verso[l * 4 + (3 - c)]), i
    # Ligne 1 : recto colonne 1 = tirage 01, verso colonne 4 = tirage 01.
    assert sfx(recto[0]) == "01" and sfx(verso[3]) == "01" and sfx(verso[0]) == "04"


def test_non_regression_retirer_le_miroir_des_planches_fait_echouer_ce_test(sqlite_store):
    # Si quelqu'un retire l'appel au miroir (ou reconstruit le fichier sans lui, comme
    # entre la v0.29.0 et la v0.32.5), l'ordre des versos redevient celui des rectos.
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        appel = rendre_carte_planche(conn, _carte_parametree())['appel']
    ordre = [int(re.search(r"_(\d\d)\b", v).group(1)) - 1 for v in _cellules(appel, 'Verso')]
    assert ordre == ORDRE_VERSO, "verso des planches sans miroir : réponses désalignées au dos"
    src = (Path(__file__).parent.parent / "services" / "render_carte_centralise.py").read_text("utf-8")
    corps = src[src.index("def rendre_carte_planche"):]
    assert "_miroir_horizontal_verso(cellules_verso)" in corps


def test_carte_fixe_seize_cellules_identiques_inchangees(sqlite_store):
    with _conn(sqlite_store) as conn:
        _setup_minimal_niveau(conn, 'N10', 'S01')
        appel = rendre_carte_planche(conn, _carte_fixe())['appel']
    assert _cellules(appel, 'Verso') == ['VERSO_TEST'] * 16
    assert _cellules(appel, 'Recto') == ['RECTO_TEST'] * 16
