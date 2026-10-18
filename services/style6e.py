"""services/style6e.py — v0.52.0 (correctif 2)

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

La liste ci-dessous est celle de seqenseigne-style6e v0.4 ; un test la
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
    "seqLocBande", "seqLocCellule", "seqLocChiffres", "seqLocCol", "seqLocCroix",
    "seqLocEcran", "seqLocEntoure", "seqLocExplication", "seqLocFlechesOG",
    "seqLocGrilleOp", "seqLocHiero", "seqLocHieroNombre", "seqLocLig",
    "seqLocPotence", "seqLocPotenceVisible", "seqLocSiCorrige", "seqLocSurligne",
    "seqLocTableauDecimal", "seqLocTableauNumeration", "seqLocTableauOG",
    "seqLocTrait", "seqMotCle", "seqNumSix", "seqPartieSix", "seqPointilles",
    "seqReponse", "seqScore", "seqSectionFicheSix", "seqTitreCM",
    "seqTitreComplementSix", "seqTitreEvalSix", "seqTitreFicheSix",
    "seqTitreTravailSix", "seqTrous", "seqVersionACompleter",
    "seqVersionComplete", "seqVersionCorrigee", "seqVersionEleve",
)


def correspondances() -> dict[str, str]:
    """Entrées à ajouter à MACROS_PAQUETS_EXTERNES (macros avec leur \\,
    environnements sans, comme le reste de la table)."""
    d = {"\\" + m: NOM_PAQUET for m in MACROS}
    d.update({e: NOM_PAQUET for e in ENVIRONNEMENTS})
    return d
