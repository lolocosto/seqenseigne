"""tests/test_v0_15_2_6_log_pdflatex_parser.py — v0.15.2.6

Parser ultra-léger du log pdflatex : extraction du numéro de page courant
pour donner à l'UI un signal de vie ~à chaque seconde pendant les
~25-30s que dure la compilation d'une cible.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.log_pdflatex_parser import progression_courante


def _ecrire(tmp_path: Path, contenu: str) -> Path:
    p = tmp_path / 'test.log'
    p.write_text(contenu, encoding='utf-8')
    return p


def test_log_absent_renvoie_none(tmp_path):
    """Avant que pdflatex démarre, le `.log` n'existe pas encore."""
    p = tmp_path / 'pas_la.log'
    assert progression_courante(p) is None


def test_log_vide_renvoie_none(tmp_path):
    """Log existant mais sans marqueur `[N]` (tout début de pdflatex)."""
    p = _ecrire(tmp_path, "")
    assert progression_courante(p) is None


def test_log_sans_marqueur_renvoie_none(tmp_path):
    """Quelques lignes de préambule sans aucun shipout."""
    p = _ecrire(tmp_path, """
This is pdfTeX, Version 3.141592653-2.6-1.40.25
(./test.tex
LaTeX2e <2023-11-01> patch level 1
""")
    assert progression_courante(p) is None


def test_log_une_seule_page(tmp_path):
    p = _ecrire(tmp_path, "loading... [1]\n")
    assert progression_courante(p) == {'page_courante': 1}


def test_log_plusieurs_pages_renvoie_la_derniere(tmp_path):
    """Pdflatex émet `[N]` à chaque shipout : on prend la dernière vue."""
    p = _ecrire(tmp_path, """
[1] [2] [3]
Overfull \\hbox ...
[4]
Underfull \\hbox ...
[5] [6] [7] [8] [9] [10]
""")
    assert progression_courante(p) == {'page_courante': 10}


def test_log_grandes_pages(tmp_path):
    """Numéros à plusieurs chiffres (238 pages pour les planches N10)."""
    contenu = ' '.join(f'[{n}]' for n in range(1, 239))
    p = _ecrire(tmp_path, contenu)
    assert progression_courante(p) == {'page_courante': 238}


def test_log_bytes_invalides_robuste(tmp_path):
    """Robustesse aux séquences non-UTF8 (logs MiKTeX mixtes Win-1252
    + UTF-8 selon les paquets). On lit en bytes : pas de surprise."""
    p = tmp_path / 'test.log'
    # Bytes Win-1252 (é = 0xE9) au milieu d'un log par ailleurs ASCII
    p.write_bytes(b"Compiling \xe9chec... [42] more \xe9\xe9\xe9 stuff [43]\n")
    assert progression_courante(p) == {'page_courante': 43}


def test_log_3pass_pdflatex_ecrase_donc_derniere_passe(tmp_path):
    """pdflatex 3-pass : MiKTeX écrase le .log à chaque passe. Le dernier
    `[N]` est donc la page courante de la passe en cours — exactement ce
    qu'on veut afficher. On simule en écrivant un contenu correspondant
    à la passe 3 (la précédente a été overwritten)."""
    # Pas de moyen de simuler "le log a été écrasé" autrement qu'en
    # écrivant le contenu attendu après écrasement. C'est le contrat
    # du parser : il lit ce qui est là, point.
    p = _ecrire(tmp_path, "[1] [2] [3] (passe 3 en cours)")
    assert progression_courante(p) == {'page_courante': 3}


def test_log_chemin_inexistant_pas_d_exception(tmp_path):
    """Le parser ne doit JAMAIS lever, même sur un chemin invalide."""
    # Path absolu vers un dossier qui n'existe pas
    p = tmp_path / 'inexistant' / 'sub' / 'test.log'
    # Aucune exception attendue
    assert progression_courante(p) is None


def test_log_dossier_pas_fichier_pas_d_exception(tmp_path):
    """Si quelqu'un passe un Path qui pointe vers un dossier, on renvoie
    None plutôt que de lever."""
    assert progression_courante(tmp_path) is None
