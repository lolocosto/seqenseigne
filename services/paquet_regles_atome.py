r"""
services/paquet_regles_atome.py — Règles de rendu d'un atome isolé.

Pour chaque macro/environnement du paquet seqenseigne, indique :
  - 'reutilise'  : la définition du paquet est réemployée telle quelle
  - 'reecrit'    : une définition alternative est fournie (contenu_atome)
  - 'ignore'     : rien n'est émis (macro sans objet hors d'un livret)

Les règles listées explicitement priment. Pour le reste, le statut par défaut
est 'reutilise' (= émettre le code du paquet tel quel).

Ce module sert à deux usages :
  1. Peupler la colonne statut_rendu_atome de paquet_definitions à l'import.
  2. Fournir les corps de remplacement pour les macros en 'reecrit'.

Les règles évoluent au fil des découvertes de bugs de compilation.
Convention : une règle ajoutée ici doit être accompagnée d'un test pytest
qui compile un atome représentatif utilisant la macro concernée.
"""

from __future__ import annotations


# ── Statuts possibles ──────────────────────────────────────────────────────────

STATUT_REUTILISE = 'reutilise'
STATUT_REECRIT   = 'reecrit'
STATUT_IGNORE    = 'ignore'

STATUTS_VALIDES = {STATUT_REUTILISE, STATUT_REECRIT, STATUT_IGNORE}


# ── Corps de remplacement pour les macros réécrites ────────────────────────────

# Historique : une ancienne version du service neutralisait les mécanismes
# de corrigés/annexes du paquet et affichait le corrigé inline via une
# réécriture de \seqCorrige. Approche abandonnée — elle produisait une mise
# en page incohérente avec les livrets (boîte différente, position différente).
#
# Aujourd'hui, le service laisse le paquet orchestrer corrigés et annexes
# comme dans un livret : \seqCorrige écrit dans Corriges/cNeM.tex pendant
# que seqSerieExos compose l'énoncé en 2 colonnes, puis \seqAfficheCorriges
# en fin de document repasse en 1 colonne sur fond blanc.
#
# Plus aucune règle n'est en statut 'reecrit' pour l'instant. Si un besoin
# réapparaît (ex. changement radical du paquet), ajouter ici la constante
# du corps de remplacement et rétablir le mapping dans REGLES.


# ── Table des règles ──────────────────────────────────────────────────────────
#
# Format : nom_macro → (statut, contenu_atome_ou_None)
# Les noms sont ceux produits par le parseur (ex. '\\seqCorrige' avec backslash,
# 'seqNotion' pour un environnement, 'boiteTitreGen' pour un tcolorbox).

REGLES: dict[str, tuple[str, str | None]] = {

    # ──── Corrigés & annexes : on laisse le paquet faire son travail ─────────
    # Le mécanisme livret est conservé : \seqCorrige écrit dans Corriges/cNeM.tex,
    # \seqAfficheCorriges affiche le tout plus tard via CorrList.tex.
    # Dans generer_tex_atome, on appelle explicitement \seqInitCorriges et
    # \seqInitAnnexes (normalement appelés par \seqTitreLivret qu'on saute),
    # puis à la fin \seqAfficheAnnexes et \seqAfficheCorriges.
    # Le service compilateur_pdf.py crée les dossiers Corriges/ et Annexes/
    # dans le dossier de compilation (tcbverbatimwrite les exige pré-existants).
    '\\seqCorrige':                    (STATUT_REUTILISE, None),
    '\\seq@ecrit@corrige@Exo':         (STATUT_REUTILISE, None),
    '\\seq@ecrit@corrige@serieExos':   (STATUT_REUTILISE, None),
    '\\seqAfficheCorriges':            (STATUT_REUTILISE, None),
    '\\seqAfficheAnnexes':             (STATUT_REUTILISE, None),
    '\\seqAnnexe':                     (STATUT_REUTILISE, None),
    '\\seqInitCorriges':               (STATUT_REUTILISE, None),
    '\\seqInitAnnexes':                (STATUT_REUTILISE, None),

    # ──── Macros de données (CSV-dépendantes) : résolues à la génération ──────
    # On ne les définit pas en LaTeX. Si elles apparaissent dans un atome,
    # elles sont substituées côté Python par leur valeur depuis la BDD.
    '\\seqObjectifGetNom':             (STATUT_IGNORE, None),
    '\\seqObjectifGetFinCycle':        (STATUT_IGNORE, None),
    '\\seqObjectifGetMaitriseTB':      (STATUT_IGNORE, None),
    '\\seqObjectifGetMaitriseS':       (STATUT_IGNORE, None),
    '\\seqObjectifGetMaitriseF':       (STATUT_IGNORE, None),
    '\\seqConnaissanceGetNom':         (STATUT_IGNORE, None),
    '\\seqSequenceGetNom':             (STATUT_IGNORE, None),
    '\\seqSequenceGetNomOf':           (STATUT_IGNORE, None),
    '\\seqSequenceGetNumero':          (STATUT_IGNORE, None),
    '\\seqSequenceGetTheme':           (STATUT_IGNORE, None),
    '\\seqSequenceSaveThemeOf':        (STATUT_IGNORE, None),
    '\\seqThemeGetNom':                (STATUT_IGNORE, None),
    '\\seqThemeGetCodeCouleur':        (STATUT_IGNORE, None),
    '\\seqThemeGetDescription':        (STATUT_IGNORE, None),
    '\\seqNiveauGetNomCourt':          (STATUT_IGNORE, None),
    '\\seqNiveauGetNomLong':           (STATUT_IGNORE, None),
    '\\seqNiveauGetCodeCycle':         (STATUT_IGNORE, None),
    '\\seqMaitriseGetNom':             (STATUT_IGNORE, None),

    # ──── Chargement de données : sans objet ─────────────────────────────────
    '\\seqLoadData':                   (STATUT_IGNORE, None),
    '\\seqLoadDataSuivi':              (STATUT_IGNORE, None),
    '\\seqSetDataPath':                (STATUT_IGNORE, None),
    '\\seqDTLfetchsave':               (STATUT_IGNORE, None),
    '\\seqFiltreDonnees':              (STATUT_IGNORE, None),
    '\\seq@bases@filter':              (STATUT_IGNORE, None),
    '\\seq@bases@filter@cycle':        (STATUT_IGNORE, None),
    '\\seqForeachTheme':               (STATUT_IGNORE, None),
    '\\seqForeachSequence':            (STATUT_IGNORE, None),
    '\\seqSetColors':                  (STATUT_IGNORE, None),

    # ──── Macros de livret : sans objet dans un atome isolé ──────────────────
    '\\seqTitreLivret':                (STATUT_IGNORE, None),
    '\\seqTitreLivretAuto':            (STATUT_IGNORE, None),
    '\\seqTableauObjectifs':           (STATUT_IGNORE, None),
    '\\seqTableauPrerequis':           (STATUT_IGNORE, None),
    # seqCarteMentale est un environnement (pas de backslash)
    'seqCarteMentale':                 (STATUT_IGNORE, None),
    # seqPrerequis, seqObjectifs, seqObjectifsN2 : environnements de livret
    # (seqPrerequis n'est pas défini dans le paquet actuel, il est mentionné
    #  dans le README mais le code de base n'a que seqObjectifs et seqObjectifsN2)
    'seqObjectifs':                    (STATUT_IGNORE, None),
    'seqObjectifsN2':                  (STATUT_IGNORE, None),

    # ──── Macros de plan de travail : sans objet ─────────────────────────────
    '\\seqBoiteTitrePlan':             (STATUT_IGNORE, None),
    '\\seqPlanObjectif':               (STATUT_IGNORE, None),
    '\\seqPlanReperesNiveaux':         (STATUT_IGNORE, None),

    # ──── Macros de bilan de classe : sans objet ─────────────────────────────
    '\\seqBilan':                      (STATUT_IGNORE, None),
    '\\seqBilanItemAlea':              (STATUT_IGNORE, None),
    '\\seqBilanObjectifsItem':         (STATUT_IGNORE, None),
    '\\seqBilanRAZExoNum':             (STATUT_IGNORE, None),
    '\\seqBilanCorrigeExo':            (STATUT_IGNORE, None),
    '\\seqAfficheCorrigesBilan':       (STATUT_IGNORE, None),
    'seqBilanObjectifs':               (STATUT_IGNORE, None),
    'seqBilanQCM':                     (STATUT_IGNORE, None),
    'seqBilanExo':                     (STATUT_IGNORE, None),

    # ──── Macros d'évaluation (paquet seqenseigne-core-eval, v0.13.5.2+) ─────
    # Réutilisées telles quelles par le générateur services/render_evaluation.py
    # (v0.13.5.3) qui produit le .tex complet d'une évaluation. La fermeture
    # transitive du préambule (services/preambule_atome.py) tire ces
    # définitions du paquet quand elles apparaissent dans le .tex généré.
    #
    # v0.13.5.6 — Ajout de \seqInitCorrigesEval : macro publique introduite
    # côté paquet pour encapsuler \newwrite\corrfileeval (allocation TeX
    # qui était au top-level de seqenseigne-core.sty et n'était pas
    # indexable par le parser). Le générateur l'appelle systématiquement
    # avant \seqTitreEval. Cf. seqenseigne-core-eval.sty v0.13.5.6+.
    '\\seqInitCorrigesEval':           (STATUT_REUTILISE, None),
    '\\seqTitreEval':                  (STATUT_REUTILISE, None),
    '\\seqEvalCorrigeExo':             (STATUT_REUTILISE, None),
    '\\seqEvalAfficheCorriges':        (STATUT_REUTILISE, None),
    'seqEvalBareme':                   (STATUT_REUTILISE, None),
    'seqEvalObjectifs':                (STATUT_REUTILISE, None),
    'seqEvalExercice':                 (STATUT_REUTILISE, None),
    # Note v0.13.5.3 — Les macros suivantes ont été retirées du paquet en
    # v0.13.5.2 lors de la refonte du module éval, donc plus aucune règle
    # pour elles ici (sinon ce sont des règles orphelines au sens de
    # regles_orphelines) :
    #   - \seqEvalBaremeItem    (suppression : colspec automatique
    #                            de tabularray a remplacé la macro)
    #   - \seqEvalQCMItem       (suppression : seqQcm est désormais un
    #                            environnement enfant avec \seqQcmQuestion)
    #   - qcm                   (renommé seqQcm dans seqenseigne-core-exos)

    # ──── Macros de suivi de classe : sans objet ─────────────────────────────
    '\\seqTitreSuivi':                 (STATUT_IGNORE, None),
    '\\seqSuiviSequence':              (STATUT_IGNORE, None),
    '\\seqSuiviAnnuelParEleve':        (STATUT_IGNORE, None),
    '\\seqSuiviAnnuelParSequence':     (STATUT_IGNORE, None),
    '\\seqSuiviPeriodiqueParSequence': (STATUT_IGNORE, None),

    # ──── PPRE (Plan Personnalisé de Réussite Éducative) : sans objet ────────
    '\\seqPPRE':                       (STATUT_IGNORE, None),
    '\\seqPPRESequence':               (STATUT_IGNORE, None),
    '\\seqPPRE@tmpCode':               (STATUT_IGNORE, None),
    '\\seqPPRE@tmpExosF':              (STATUT_IGNORE, None),
    '\\seqPPRE@tmpExosA':              (STATUT_IGNORE, None),
    '\\seqPPRE@tmpExosE':              (STATUT_IGNORE, None),
    '\\seqPPRE@tmpAideF':              (STATUT_IGNORE, None),
    '\\seqPPRE@tmpAideA':              (STATUT_IGNORE, None),
    '\\seqPPRE@tmpAideE':              (STATUT_IGNORE, None),
}


# ── API ──────────────────────────────────────────────────────────────────────

def statut_de(nom: str) -> tuple[str, str | None]:
    """Retourne (statut, contenu_reecrit) pour un nom donné.

    Par défaut : ('reutilise', None).
    """
    return REGLES.get(nom, (STATUT_REUTILISE, None))


def toutes_regles_explicites() -> dict[str, tuple[str, str | None]]:
    """Retourne une copie du dict des règles (pour test/inspection)."""
    return dict(REGLES)
