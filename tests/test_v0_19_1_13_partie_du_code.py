"""tests/test_v0_19_1_13_partie_du_code.py — v0.19.1.13

La déduction du numéro de partie depuis le code d'objectif (convention 2023-24 :
0x→P1, 1x→P2, 2x→P3) doit être correcte. Codes « cours » 01/11/21 inclus.
"""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "import_historique_5e1_2023",
    Path(__file__).resolve().parent.parent / "outils"
    / "import_historique_5e1_2023.py")
m = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(m)


def test_partie_du_code():
    # Partie 1 : codes 0x (01 cours, 02-09 exos)
    for c in ("01", "02", "03", "09"):
        assert m._partie_du_code(c) == 1, c
    # Partie 2 : codes 1x (11 cours, 12-19 exos)
    for c in ("11", "12", "16", "19"):
        assert m._partie_du_code(c) == 2, c
    # Partie 3 : codes 2x (21 cours, 22-29 exos)
    for c in ("21", "22", "23", "29"):
        assert m._partie_du_code(c) == 3, c
