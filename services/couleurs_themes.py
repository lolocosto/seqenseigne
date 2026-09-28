"""services/couleurs_themes.py — R2.

Familles de couleurs disponibles pour les thèmes.

Chaque famille correspond à un ensemble de macros LaTeX définies dans
seqenseigne-theme.dtx (lignes ~76-122) qui déclinent une teinte
principale en 4 nuances : Vif / Moyen / Modéré / Pâle.

Le `slug` est la valeur stockée en base dans la colonne
`themes.code_couleur`. Il est court (identifiant technique) et compatible
avec la chaîne LaTeX.

Le `libelle` est le texte affiché dans l'interface.

`hex_principal` est la couleur d'aperçu affichée à côté du libellé dans
le sélecteur (approximation de la teinte Vif).

Pour ajouter une famille : ajouter une entrée ici, pas besoin de toucher
à la base ni aux routes. Le sélecteur se met à jour automatiquement.

À terme (post-R2), un module d'édition permettra de personnaliser ces
familles via color-picker.
"""

from __future__ import annotations


# Ordre = ordre d'affichage dans le sélecteur
FAMILLES_COULEURS = [
    {
        "slug":          "nombres",
        "libelle":       "Rouge / Jaune",
        "hex_principal": "#d92626",   # red!85!black approximatif
    },
    {
        "slug":          "donnees",
        "libelle":       "Bleu / Canard",
        "hex_principal": "#2638d9",   # blue!85!black
    },
    {
        "slug":          "grandeurs",
        "libelle":       "Marron / Orange",
        "hex_principal": "#8b4513",   # brown!85!black
    },
    {
        "slug":          "geometrie",
        "libelle":       "Violet / Vert",
        "hex_principal": "#7326a0",   # violet!85!black
    },
    {
        "slug":          "algorithmique",
        "libelle":       "Rose / Lime",
        "hex_principal": "#c41e80",   # magenta!85!black
    },
    {
        "slug":          "noir_gris",
        "libelle":       "Noir / Gris",
        "hex_principal": "#262626",   # black!85!black
    },
]


def slugs_valides() -> set[str]:
    """Ensemble des slugs utilisables pour le champ code_couleur."""
    return {f["slug"] for f in FAMILLES_COULEURS}


def famille_par_slug(slug: str) -> dict | None:
    """Retourne la famille correspondant au slug, ou None si inconnu."""
    for f in FAMILLES_COULEURS:
        if f["slug"] == slug:
            return f
    return None
