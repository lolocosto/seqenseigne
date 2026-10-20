"""services/style6e.py — v0.52.0 (correctif 2), v0.52.5

Module LaTeX `seqenseigne-style6e` (documents de 6e, option `sixieme` du
paquet) : chargé **en entier** par `\\usepackage{seqenseigne-style6e}` dès
qu'un atome ou un livret utilise une de ses macros ou un de ses
environnements.

Pourquoi pas par l'import « mise en forme » (paquet_definitions) comme les
autres modules :
  - le parseur `services/paquet_parseur.py` est écrit pour la syntaxe des
    modules du cycle 4 ; sur style6e il ne voit que 49 définitions sur ~80
    (manquent \\seqReponse, \\seqCase, \\seqACompleter, la potence, la grille
    d'opération… : arguments optionnels xparse, \\def à paramètres, boucles) ;
  - le module est autonome (ses couleurs, compteurs et macros internes sont
    tous définis chez lui, aucun nom commun avec les autres modules), donc
    le charger entier est sûr et ne change rien au rendu du cycle 4.

La liste ci-dessous est celle de seqenseigne-style6e v0.7 (v0.52.4 :
\\seqNiveauCourt, \\seqNiveauExposant ; v0.52.5 : macros du lot S05
\\seqLocCadreTrace, \\seqLocAngle, \\seqLocRapporteur ; du lot S04 \\seqLocBloc,
\\seqLocAccolade, \\seqLocBalance, \\seqLocSac, \\seqLocMasse, \\seqLocObjet ; page de garde par
partie : \\seqPartieCouvertureSix ; v0.7, v0.52.7 : marqueurs de l'exercice
\\seqMaterielSix, \\seqOrdinateurSix, \\seqCalculatriceSix et leurs pictogrammes) ; un test la
compare au .dtx du dossier `paquet/` quand il est présent. Le dossier du
paquet (`reference\\paquet` par défaut) est ajouté au TEXINPUTS par
services/compilateur_pdf.py pour que pdflatex trouve le .sty.
"""

from __future__ import annotations

NOM_PAQUET = "seqenseigne-style6e"

ENVIRONNEMENTS = (
    "seqActiviteSix", "seqBande", "seqCalculMental", "seqCopies",
    "seqEncadreDefSix", "seqEncadreIntroSix", "seqExoSix", "seqFicheResumeSix",
    "seqPlancheFiches",
)

MACROS = (
    "seqACompleter", "seqBandeauCapacite", "seqBaremeCompetences", "seqCase",
    "seqCaseCocher", "seqComplSix", "seqCouvertureLivretSix", "seqDemiDroite",
    "seqExoEval", "seqFiguresSix", "seqIdentEleve", "seqItemCM", "seqItemRond",
    "seqLocAccolade", "seqLocAngle", "seqLocBalance", "seqLocBande", "seqLocBloc", "seqLocCadreTrace", "seqLocCellule", "seqLocChiffres", "seqLocCol", "seqLocCroix",
    "seqLocEcran", "seqLocEntoure", "seqLocExplication", "seqLocFlechesOG",
    "seqLocGrilleOp", "seqLocHiero", "seqLocHieroNombre", "seqLocLig", "seqLocMasse", "seqLocObjet",
    "seqLocPotence", "seqLocPotenceVisible", "seqLocRapporteur", "seqLocSac", "seqLocSiCorrige", "seqLocSurligne",
    "seqLocTableauDecimal", "seqLocTableauNumeration", "seqLocTableauOG",
    "seqLocTrait", "seqMotCle", "seqNiveauCourt", "seqNiveauExposant", "seqNumSix", "seqPartieCouvertureSix", "seqPartieSix", "seqPointilles",
    "seqMaterielSix", "seqOrdinateurSix", "seqCalculatriceSix",            # v0.7 (v0.52.7)
    "seqPictoOrdinateurSix", "seqPictoCalculatriceSix",
    "seqReponse", "seqScore", "seqSectionFicheSix", "seqTitreCM",
    "seqTitreComplementSix", "seqTitreEvalSix", "seqTitreFicheSix",
    "seqTitreTravailSix", "seqTrous", "seqVersionACompleter",
    "seqVersionComplete", "seqVersionCorrigee", "seqVersionEleve",
)

# v0.52.5 (décision S1) — Styles TikZ du module : ce ne sont pas des macros
# (on écrit `[seqLocCorr]`, jamais `\seqLocCorr`), ils ne vont donc pas dans
# MACROS ni dans MACROS_PAQUETS_EXTERNES. Les documents qui les emploient
# (modèle « Fiches de résumé par objectif ») chargent le module en entier.
STYLES_TIKZ = ("seqLocCorr",                                   # lot S05
               "seqLocBarre", "seqLocBarreR", "seqLocBarreV", "seqLocBarreQ")  # lot S04


def correspondances() -> dict[str, str]:
    """Entrées à ajouter à MACROS_PAQUETS_EXTERNES (macros avec leur \\,
    environnements sans, comme le reste de la table)."""
    d = {"\\" + m: NOM_PAQUET for m in MACROS}
    d.update({e: NOM_PAQUET for e in ENVIRONNEMENTS})
    return d
