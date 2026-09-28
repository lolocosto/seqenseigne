"""tests/test_v0_15_2_9_log_parser_first_page.py — v0.15.2.9

Fix regex du parser pdflatex pour capturer le marqueur de PREMIÈRE page.

Bug v0.15.2.8 (rapporté par Laurent sur les planches de cartes) :
pdflatex émet pour la première page `[1\\n\\n{/path/to/pdftex.map}]`
(la carte des polices est embarquée DANS le marqueur). L'ancienne
regex stricte `\\[(\\d+)\\]` ne matchait pas — l'UI restait sans
compteur de pages tant que la page 2 n'arrivait pas.

Pour `livret_exercices`, la page 2 arrivait en quelques secondes →
compteur fonctionnel. Pour `livret_cartes_planches`, la première
page (16 cartes tcolorbox) peut prendre 15-20s → l'UI restait
silencieuse tout ce temps.

Fix v0.15.2.9 : regex `\\[(\\d+)(?![\\d.a-zA-Z])` — capture `[N`
suivi de n'importe quel caractère qui n'est ni chiffre, ni point,
ni lettre. Couvre le cas `[1\\n{...}]` ET rejette `[1pt]`, `[1.5]`,
`[Lab12]`, `[Sec1.2]`.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.log_pdflatex_parser import progression_courante


def _ecrire(tmp_path: Path, contenu_bytes: bytes) -> Path:
    p = tmp_path / 'atome.log'
    p.write_bytes(contenu_bytes)
    return p


def test_premiere_page_avec_map_font_capturee(tmp_path):
    """Cas réel pdflatex sur première page : `[1\\n\\n{...path...}]`.
    Avant v0.15.2.9 cette occurrence était INVISIBLE pour le parser.
    """
    contenu = (b"Some preamble output...\n"
               b"(/usr/share/texlive/something) [1\n\n"
               b"{/var/lib/texmf/fonts/map/pdftex/updmap/pdftex.map}]\n")
    p = _ecrire(tmp_path, contenu)
    res = progression_courante(p)
    assert res == {'page_courante': 1}, (
        "La première page de pdflatex doit être détectée même quand la "
        "carte des polices est embarquée dans le marqueur."
    )


def test_premiere_page_puis_seconde_la_derniere_gagne(tmp_path):
    """Toujours le LAST match : si page 2 ship juste après, on remonte 2."""
    contenu = (b"[1\n\n{/var/lib/texmf/fonts/map/pdftex/updmap/pdftex.map}]"
               b" [2]\n")
    p = _ecrire(tmp_path, contenu)
    assert progression_courante(p) == {'page_courante': 2}


def test_pas_de_faux_positif_unite_pt(tmp_path):
    """`[1pt]` (Overfull \\hbox warning) ne doit PAS être pris comme page 1.
    Si c'est le SEUL "[N..." du log → None.
    """
    contenu = b"Overfull \\hbox (1.2pt too wide) [1pt] some warning\n"
    p = _ecrire(tmp_path, contenu)
    assert progression_courante(p) is None


def test_pas_de_faux_positif_ratio(tmp_path):
    """`[1.5]` ne doit pas matcher."""
    contenu = b"badness 1234 ratio [1.5] hbox\n"
    p = _ecrire(tmp_path, contenu)
    assert progression_courante(p) is None


def test_pas_de_faux_positif_label(tmp_path):
    """`[Lab12]` ou `[Sec1.2]` (références, etc.) ne doivent pas matcher
    (ils commencent par lettre — la regex démarre par `\\d`)."""
    contenu = b"see [Sec1.2] and [Lab12] for context\n"
    p = _ecrire(tmp_path, contenu)
    assert progression_courante(p) is None


def test_pages_apres_warning_avec_pt_isole_correctement(tmp_path):
    """Cas réaliste mixte : warnings avec `[1.5pt]` (rejeté) PUIS
    shipouts standards `[1]`, `[2]`, ... → on doit capter 2 comme last."""
    contenu = (b"Overfull \\hbox (1.5pt too wide) detected\n"
               b"[1\n\n{/path/font.map}] [2]\n")
    p = _ecrire(tmp_path, contenu)
    assert progression_courante(p) == {'page_courante': 2}


def test_page_avec_marqueur_brace_seul(tmp_path):
    """Variation : `[1{...}]` sur la même ligne (sans newline avant)."""
    contenu = b"[1{/path/font.map}] [2{/another.map}] [3]\n"
    p = _ecrire(tmp_path, contenu)
    assert progression_courante(p) == {'page_courante': 3}


def test_grand_numero_avec_map_initial(tmp_path):
    """Le bug ne dépendait pas du numéro : un log qui commence par
    `[1{...}]` peut se terminer par `[238]` pour un livret 14 séquences.
    """
    contenu = (b"[1\n\n{/path/font.map}] "
               + b" ".join(f"[{n}]".encode() for n in range(2, 239))
               + b"\n")
    p = _ecrire(tmp_path, contenu)
    assert progression_courante(p) == {'page_courante': 238}
