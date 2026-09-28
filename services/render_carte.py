r"""services/render_carte.py — v0.15.2.2

Compilation isolée d'une carte d'automatisme (atelier de prévisualisation).

Historique
----------
- v0.13.6.2 : version initiale, préambule explicite + \seqCarteAuto.
- v0.15.2.1 : migration vers render_carte_centralise pour la cohérence
  inter-contextes (cf. cadrage option C1). Le préambule explicite et la
  logique de génération du corps déménagent dans render_carte_centralise
  (fonction rendre_carte_isole).
- v0.15.2.2 : alignement sur la nouvelle API du paquet
  seqenseigne-carte-automatisme (\seqInitCartes obligatoire après
  \begin{document}, \seqCarteAutomatisme au lieu de \seqCarteAuto, groupe
  {...} pour les variables xint maintenant émis directement dans le corps
  par rendre_carte_isole).
"""
from __future__ import annotations
import sqlite3

from services import cartes_automatisme as svc
from services.render_carte_centralise import (
    # Utilitaires partagés (réexportés pour rétrocompatibilité)
    LIBELLE_TYPE_PEDAGO,
    CODE_COULEUR_DEFAUT,
    resoudre_code_couleur,
    resoudre_libelle_type_pedago,
    _echapper_valeur_option,
    # API contexte « isolé »
    rendre_carte_isole,
)


# ── Exceptions ──────────────────────────────────────────────────────────────


class RenderCarteErreur(Exception):
    """Erreur de rendu d'une carte. Pattern aligné sur CarteErreur."""
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


# ── Construction du préambule ───────────────────────────────────────────────


def _construire_preambule_carte() -> str:
    r"""Préambule statique pour le .tex d'une carte unique en mode isolé.

    Ne déclare PAS tcolorbox, tabularray, xintexpr : amenés
    transitivement par seqenseigne-core et seqenseigne-theme. Toute
    déclaration explicite ici provoquerait un « Option clash » avec
    seqenseigne-theme qui charge tcolorbox avec ses options
    (cf. v0.15.1.3.1).
    """
    return r"""\documentclass[10pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[french]{babel}
\usepackage{lmodern}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{xcolor}
\usepackage{siunitx}
\usepackage{seqenseigne-core}
\usepackage{seqenseigne-theme}
\usepackage{seqenseigne-carte-automatisme}
"""


# ── Génération du .tex ──────────────────────────────────────────────────────


def generer_tex_carte(conn: sqlite3.Connection, carte_id: str) -> str:
    r"""Génère le .tex complet d'une carte d'automatisme (recto+verso).

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion BDD.
    carte_id : str
        Id de la carte à rendre.

    Returns
    -------
    str
        Contenu .tex prêt à compiler.

    Raises
    ------
    services.cartes_automatisme.CarteIntrouvable
        Si la carte n'existe pas en BDD.
    """
    # 1. Lecture de la carte
    carte = svc.lire_carte(conn, carte_id)

    # 2. Délégation à rendre_carte_isole (factorisation v0.15.2.1, API v0.15.2.2)
    rendu = rendre_carte_isole(conn, carte)

    # 3. Assemblage : préambule + \seqInitCartes + corps (qui inclut déjà
    # le groupe {...} des variables xint le cas échéant, cf. v0.15.2.2).
    preambule = _construire_preambule_carte()

    body = (
        '\\begin{document}\n'
        '\\seqInitCartes\n'
        + rendu['corps']
        + '\\end{document}\n'
    )

    return preambule + '\n' + body
