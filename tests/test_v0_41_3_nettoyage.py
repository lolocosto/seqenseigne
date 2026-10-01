"""tests/test_v0_41_3_nettoyage.py — v0.41.3

Non-régression du nettoyage : une seule table des libellés LaTeX des niveaux
(services.param_niveaux.LIBELLES_NIVEAUX_LATEX), partagée par tous les livrets,
avec exactement les valeurs historiques ; outil obsolète bien supprimé.
"""
import importlib
from pathlib import Path

import pytest

from services.param_niveaux import LIBELLES_NIVEAUX_LATEX

LIVRETS = ["livret_cartes_recap", "livret_cartes_planches", "livret_recap_exos",
           "livret_fiches", "livret_recap_cours", "livret_corriges"]


def test_valeurs_historiques():
    assert LIBELLES_NIVEAUX_LATEX == {
        "N09": "6\\ieme{}", "N10": "5\\ieme{}",
        "N11": "4\\ieme{}", "N12": "3\\ieme{}"}


@pytest.mark.parametrize("nom", LIVRETS)
def test_livrets_partagent_la_table(nom):
    mod = importlib.import_module(f"services.{nom}")
    assert mod.LIBELLES_NIVEAUX is LIBELLES_NIVEAUX_LATEX


def test_plans_de_travail_partage_la_table():
    from services import livret_plans_de_travail as m
    assert m.LIBELLES_NIVEAUX_LATEX is LIBELLES_NIVEAUX_LATEX


def test_plus_aucune_copie_dans_les_services():
    racine = Path(__file__).resolve().parent.parent / "services"
    copies = [f.name for f in racine.glob("*.py")
              if f.name != "param_niveaux.py"
              and "'N11': '4\\\\ieme{}'" in f.read_text(encoding="utf-8")]
    assert copies == []


def test_outil_obsolete_supprime():
    racine = Path(__file__).resolve().parent.parent
    assert not (racine / "outils" / "migrer_edt_groupe_usage.py").exists()
