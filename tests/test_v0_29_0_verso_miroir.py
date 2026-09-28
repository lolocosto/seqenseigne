"""tests/test_v0_29_0_verso_miroir.py — v0.29.0

Impression recto-verso « bord court » (paysage) des planches de cartes : le
verso doit être un miroir gauche-droite du recto (colonnes inversées par ligne)
pour que chaque réponse tombe derrière son énoncé. Crucial pour les cartes
paramétrées (16 tirages différents par planche).
"""
from services.render_carte_centralise import (
    _miroir_horizontal_verso, PLANCHE_NB_CELLULES, PLANCHE_NB_COLONNES)


def test_miroir_inverse_colonnes_par_ligne():
    cells = [f"c{i:02d}" for i in range(PLANCHE_NB_CELLULES)]
    res = _miroir_horizontal_verso(cells)
    attendu = ["c03", "c02", "c01", "c00",
               "c07", "c06", "c05", "c04",
               "c11", "c10", "c09", "c08",
               "c15", "c14", "c13", "c12"]
    assert res == attendu


def test_reponse_tombe_derriere_enonce():
    # La cellule recto (ligne L, colonne C) doit avoir sa réponse verso en
    # (ligne L, colonne ncol-1-C).
    cells = list(range(PLANCHE_NB_CELLULES))
    res = _miroir_horizontal_verso(cells)
    ncol = PLANCHE_NB_COLONNES
    for L in range(PLANCHE_NB_CELLULES // ncol):
        for C in range(ncol):
            pos_verso = L * ncol + C
            valeur_recto_derriere = L * ncol + (ncol - 1 - C)
            assert res[pos_verso] == valeur_recto_derriere


def test_longueur_preservee():
    cells = list(range(PLANCHE_NB_CELLULES))
    assert len(_miroir_horizontal_verso(cells)) == PLANCHE_NB_CELLULES
