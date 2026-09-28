"""services/log_pdflatex_parser.py — v0.15.2.6

Parser ultra-léger du log pdflatex pour exposer la page en cours de
compilation à l'UI (signal de vie en temps quasi-réel).

Principe
--------
pdflatex émet `[N]` dans le log au moment du shipout de la page N. On
extrait la DERNIÈRE occurrence pour donner à l'UI un indicateur qui
bouge ~à chaque seconde.

Choix de conception
-------------------
- Lecture en bytes : robuste aux encodages incohérents qu'on rencontre
  parfois dans les logs MiKTeX (Windows + paquets variés).
- Pas de tail incrémental : on relit le fichier en entier à chaque
  appel. L'UI poll typiquement à 1Hz et un log de planche fait ~quelques
  centaines de Ko : impact négligeable.
- pdflatex 3-pass : MiKTeX écrase le `.log` à chaque passe. La dernière
  occurrence `[N]` est donc la page de la passe en cours, ce qui est
  exactement ce qu'on veut afficher.
- Faux positifs possibles (`[42]` dans un commentaire ou une citation)
  mais sans impact : le numéro change toujours vers la vraie page
  suivante dès qu'elle est shippée.

API
---
`progression_courante(chemin_log) -> dict | None`
    {'page_courante': int} si une page a été shippée, None sinon
    (log absent, illisible, ou pas encore de marqueur).
"""
from __future__ import annotations

import re
from pathlib import Path

# Marqueur de shipout pdflatex : `[N` suivi d'un séparateur (whitespace,
# newline, accolade, crochet fermant…). Robuste au cas réel des premières
# pages où pdflatex émet `[1\n\n{/path/to/pdftex.map}]` (la map font est
# embarquée DANS le marqueur de page 1) — notre ancienne regex stricte
# `\[(\d+)\]` ratait ce cas. v0.15.2.9 — fix.
#
# Le negative-lookahead `(?![\d.a-zA-Z])` évite les faux positifs :
#   `[1pt]` (longueur dans warning) — ne matche pas
#   `[1.5]` (ratio quelconque)       — ne matche pas
#   `[Lab12]`, `[Sec1.2]`            — commencent par lettre, exclus
# tout en capturant `[1]`, `[42]`, `[1\n{path}]`, `[N` suivi d'espace, etc.
_RE_PAGE = re.compile(rb'\[(\d+)(?![\d.a-zA-Z])')


def progression_courante(chemin_log: Path) -> dict | None:
    """Renvoie la dernière page shippée d'après le log pdflatex.

    Parameters
    ----------
    chemin_log : Path
        Chemin vers le `.log` pdflatex de la cible en cours. Peut ne pas
        exister (compilation pas encore démarrée).

    Returns
    -------
    dict | None
        {'page_courante': N} où N est le dernier entier rencontré dans
        un marqueur `[N]`. None si le fichier n'existe pas, est illisible,
        ou ne contient aucun marqueur (très début de compilation).
    """
    try:
        data = Path(chemin_log).read_bytes()
    except (FileNotFoundError, PermissionError, OSError, IsADirectoryError):
        return None
    matches = _RE_PAGE.findall(data)
    if not matches:
        return None
    try:
        return {'page_courante': int(matches[-1])}
    except ValueError:
        # Improbable (la regex garantit \d+), mais ceinture+bretelles
        return None
