r"""
services/preambule_atome.py — Préambule LaTeX sur mesure pour un atome isolé.

Au lieu de charger \usepackage{seqenseigne} qui tire ~110 paquets LaTeX
(datatool, tracklang, datetime, fmtcount, fancyhdr, lastpage, xltabular,
longtable, hyperref, eurosym…), on calcule la fermeture transitive des
définitions du paquet effectivement utilisées par l'atome et on les inline
directement dans le préambule.

Gain mesuré : passer de ~110 paquets à ~25-30 → temps de compilation
divisé par 2 à 3 sur un atome typique.

Principe :

1. Partir des macros et environnements seqXxx que l'atome utilise vraiment
   (corps + corrigé + variables) + un noyau "wrapper" toujours nécessaire
   selon le type d'atome (seqExercice/seqSerieExos pour un exercice,
   seqNotion pour une notion, etc.).
2. Calculer la fermeture transitive sur le graphe paquet_definitions :
   chaque définition pointe vers ses macros_appelees + environnements_utilises.
3. Filtrer les définitions au statut 'ignore' (non émises).
4. Émettre les texte_complet des définitions retenues, dans l'ordre des
   fichiers source (theme avant core, etc., pour respecter les dépendances)
   et dans l'ordre de ligne_debut à l'intérieur d'un fichier.
5. Charger via \\usepackage les paquets TeX externes dont les macros
   apparaissent dans les corps retenus, plus une liste fixe de paquets
   "noyau" toujours nécessaires (tcolorbox, amsmath, xcolor, multicol,
   enumitem, ninecolors, etc.).

Aucune dépendance externe. Importable par Flask et par les scripts.
"""

from __future__ import annotations
import json
import re
import sqlite3
from dataclasses import dataclass, field


# ── Liste fixe des paquets externes "noyau" ──────────────────────────────────
#
# Toujours nécessaires pour la mise en forme de base d'un atome — peu importe
# son contenu. Ils sont liés au fonctionnement même de l'environnement
# seqExercice/seqNotion/seqMethode et de la machinerie tcolorbox/multicol qui
# l'enveloppe.
#
# L'ordre de chargement est important : les dépendances en bas s'attendent
# à trouver les paquets du haut déjà chargés. Cette liste reproduit l'ordre
# du paquet source.
PAQUETS_NOYAU: list[tuple[str, str]] = [
    # Encodage et police
    ('inputenc',   'utf8'),
    ('fontenc',    'T1'),
    ('lmodern',    ''),
    ('babel',      'french'),
    # Mise en page
    ('geometry',   ''),
    # Maths
    ('amsmath',    ''),
    ('amssymb',    ''),
    # Outils
    ('etoolbox',   ''),
    ('xkeyval',    ''),
    ('xifthen',    ''),
    ('environ',    ''),
    ('forloop',    ''),
    # Couleurs et tableaux
    ('xcolor',     ''),
    ('ninecolors', ''),
    ('multirow',   ''),
    ('colortbl',   ''),
    ('tabularray', ''),
    # Listes et colonnes
    ('multicol',   ''),
    ('enumitem',   'inline'),
    # Graphiques
    ('graphicx',   ''),
    ('adjustbox',  ''),
    ('tikz',       ''),
    # Boîtes pédagogiques
    ('tcolorbox',  'theorems,breakable,skins'),
    # Symboles divers utilisés dans les boîtes (croix, coches…)
    ('pifont',     ''),
]


# v0.8.6 — Marges des livrets, à appliquer dans le préambule de chaque
# atome compilé en isolation.
#
# Les livrets seqenseigne utilisent \newgeometry{...} dans \seqTitreSection
# pour réduire les marges et obtenir une `\linewidth` large (~528 pt). Sans
# cette réduction, un atome rendu en isolation hérite des marges article
# par défaut (~180 pt de chaque côté, `\linewidth` ~345 pt) et la mise en
# page diffère beaucoup du livret final.
#
# Conséquences observées avant ce fix :
#   - Le paquet `vwcol` (variable-width columns) calcule la largeur de chaque
#     colonne à partir de `\linewidth`. En isolation, les colonnes étaient
#     assez étroites pour qu'une figure tikz ne tienne plus dans la colonne
#     allouée → erreur « Not enough lines to fit the entire text ».
#   - Trois notions de N11/S12 (Pythagore, Thalès, trigonométrie) plantaient
#     pour cette raison alors que leur livret compile parfaitement.
#
# Valeur identique à celle utilisée par seqenseigne-core.sty dans
# \seqTitreSection. Si l'utilisateur veut tester d'autres marges, il
# pourra surcharger via une option de configuration plus tard ; pour
# l'instant on s'aligne strictement sur le livret.
GEOMETRY_NEWGEOMETRY: str = (
    r'\newgeometry{left=35pt,right=35pt,top=65pt,bottom=70pt}'
)


# ── Paquets externes optionnels tirés par les macros de l'atome ──────────────

# Pseudo-paquets à filtrer (cf. latex_rendu_atome.py)
_PSEUDO_PAQUETS = frozenset({'tex-primitive', 'babel-french'})

# Paquets tirés par les options [geometrie] ou [scratch] du paquet,
# qu'on charge directement maintenant qu'on n'utilise plus le paquet entier.
_PAQUETS_GEOMETRIE = ['tkz-base', 'tkz-euclide', 'tkz-tab']
_PAQUETS_SCRATCH = ['scratch3']

# Paquets déjà chargés par PAQUETS_NOYAU (à exclure des "manquants")
_PAQUETS_NOYAU_NOMS = frozenset(nom for nom, _ in PAQUETS_NOYAU)


# ── Initialisations de bibliothèques ─────────────────────────────────────────
#
# Certains paquets LaTeX nécessitent l'activation d'une « library » via une
# commande spécifique APRÈS leur \usepackage. seqenseigne fait ces appels dans
# ses .sty au top-level, mais comme on ne charge pas le paquet entier, on doit
# les reproduire ici à la main.
#
# Clé : nom du paquet. Valeur : liste de lignes à émettre juste après tous
# les \usepackage du préambule.
INITIALISATIONS_BIBLIOTHEQUES: dict[str, list[str]] = {
    # NB v0.9.1 : l'init `\UseTblrLibrary{booktabs}` introduite à l'origine
    # ici a migré vers la liste paramétrable `tblr_libraries` dans la
    # configuration utilisateur (voir construire_preambule), sur le modèle
    # de tikz_libraries (v0.8.5). Elle reste chargée par défaut, mais
    # l'utilisateur peut maintenant ajouter d'autres bibliothèques
    # (varwidth pour `measure=vbox`, par exemple) sans toucher au code.
    # Cas qui a motivé la migration : N11/S11/Méthode 05 utilisait
    # `measure=vbox` dans un \begin{tblr}, qui depuis tabularray v2025A
    # nécessite `\UseTblrLibrary{varwidth}`.
    #
    # v0.8.6 — vwcol ne fournit pas de valeur par défaut pour la clé
    # `widths`. Si un atome écrit `\begin{vwcol}[lines=N]` (sans `widths=`)
    # dans un scope où aucun `\vwcolsetup{widths=...}` antérieur n'a été
    # exécuté, alors `\vwcol@widths` est undefined et l'expansion de
    # `\expandafter\vwcol@process@widths\expandafter{\vwcol@widths}` lève
    # une « Undefined control sequence ». Sur TeX Live cette erreur est
    # tolérée (PDF produit malgré tout) mais sur MiKTeX elle est fatale.
    #
    # Cas concret : N11/S12/Notion 01-02-03 ont des `\begin{vwcol}[lines=6]`
    # à l'intérieur d'environnements `seqColItem` qui ouvrent un groupe
    # TeX (via leur `\begin{itemize}` interne). Tout `\vwcolsetup{widths=...}`
    # exécuté dans un précédent `seqColItem` est local à son groupe et
    # disparaît à la fermeture de l'environnement. Le `\begin{vwcol}[lines=6]`
    # du `seqColItem` suivant trouve donc `\vwcol@widths` undefined.
    #
    # Fix préventif : initialiser `widths` globalement à une valeur neutre
    # (deux colonnes de poids égal) juste après le `\usepackage{vwcol}`.
    # Si le contenu de l'atome surcharge `widths=` localement, cette valeur
    # par défaut est ignorée. Le fix n'a aucun impact visuel sur les atomes
    # qui n'utilisent pas vwcol.
    #
    # Note : `\vwcolsetup` fait un `\def` (non global), donc cette
    # initialisation est elle aussi locale au scope où elle s'exécute —
    # mais comme elle est dans le préambule (avant `\begin{document}`),
    # elle est bien globale au document.
    'vwcol': [
        r'\vwcolsetup{widths={0.5,0.5}}',
    ],
    # NB v0.8.5 : l'init `\usetikzlibrary{babel}` introduite en v0.8.4
    # a migré vers la liste paramétrable `tikz_libraries` dans la
    # configuration utilisateur (voir construire_preambule). Elle reste
    # chargée par défaut, mais l'utilisateur peut maintenant ajouter
    # d'autres bibliothèques (shapes.geometric, arrows.meta, etc.) sans
    # toucher au code Python.
}


# ── Structure d'un préambule calculé ─────────────────────────────────────────

@dataclass
class Preambule:
    """Résultat du calcul de préambule pour un atome.

    Le contenu textuel à insérer dans le .tex est dans `texte`. Les autres
    champs sont là pour le diagnostic, le debug et les tests.
    """
    texte: str = ''                         # à insérer entre \documentclass et \begin{document}
    paquets_externes: list[tuple[str, str]] = field(default_factory=list)  # (nom, options)
    definitions_emises: list[str] = field(default_factory=list)            # noms en ordre d'émission
    nb_macros_utilisees: int = 0            # diag : combien de macros seqXxx l'atome utilise
    nb_definitions_initiales: int = 0       # diag : avant fermeture
    nb_definitions_fermees: int = 0         # diag : après fermeture
    nb_definitions_emises: int = 0          # diag : après filtre 'ignore'


# ── Index des définitions du paquet ──────────────────────────────────────────

@dataclass
class _Definition:
    """Vue compacte d'une ligne paquet_definitions."""
    nom: str
    type_latex: str
    fichier_source: str
    ligne_debut: int
    macros_appelees: list[str]
    environnements_utilises: list[str]
    statut: str
    texte_complet: str
    contenu_atome: str       # corps de remplacement si statut='reecrit'

    def texte_a_emettre(self) -> str:
        r"""Retourne le texte LaTeX à inliner pour cette définition.

        - Si statut='reecrit' : on émet `contenu_atome` (renewcommand
          défini explicitement par les règles de paquet_regles_atome.py).
        - Sinon : on émet `texte_complet` (la définition d'origine du paquet).

        Le `texte_complet` peut contenir des suites de lignes vides — issues
        du fait que `strip_comments` (paquet_parseur) supprime les commentaires
        mais conserve les retours à la ligne pour préserver les numéros de
        lignes. Ces lignes vides à l'intérieur du corps d'une `\newcommand`
        ou d'un `\newtcolorbox` se traduisent en `\par` à l'exécution, ce
        qui peut faire planter pgfkeys (utilisé par tcolorbox pour ses
        options) avec :

            ! Paragraph ended before \pgfkeys@addpath was complete.

        Exemple concret : dans le paquet seqenseigne, la définition de
        `\seqCreeCompteurs` contient 3 commentaires consécutifs entre les
        compteurs et les `\renewcommand{\theHxxx}` ; après strip_comments,
        cela donne 3 lignes vides → 1 `\par` parasite à l'exécution.

        On compresse donc les blocs de >=2 lignes vides en une seule
        (qui est inoffensive : ce n'est pas un `\par`).
        """
        if self.statut == 'reecrit' and self.contenu_atome:
            return _compresser_lignes_vides(self.contenu_atome)
        return _compresser_lignes_vides(self.texte_complet)


def _compresser_lignes_vides(texte: str) -> str:
    r"""Compresse les blocs de 2+ lignes vides consécutives en 1 seule.

    Une ligne vide isolée (1 seule) est conservée pour la lisibilité.
    Une ligne ne contenant que des espaces ou tabulations est traitée
    comme vide.

    Exemples :
        "a\n\n\nb"      -> "a\n\nb"      (3 vides → 1 vide)
        "a\n\nb"        -> "a\n\nb"      (1 vide isolée → conservée)
        "a\n   \n\t\nb" -> "a\n\nb"      (2 vides 'blanches' → 1 vide)
        "a\nb"          -> "a\nb"        (pas de ligne vide → inchangé)
    """
    if not texte:
        return texte
    # Une ligne vide est représentée par '\n\n' ou plus dans la chaîne ;
    # mais on doit aussi gérer les lignes de blancs ('\n   \n').
    # On normalise : transformer toute ligne ne contenant que des blancs
    # en chaîne vide pure, puis compresser '\n\n+' en '\n\n'.
    lignes = [l if l.strip() else '' for l in texte.split('\n')]
    # Compresser les runs de >=2 lignes vides en 1
    out = []
    n_vides = 0
    for l in lignes:
        if l == '':
            n_vides += 1
            if n_vides == 1:
                out.append(l)
            # sinon : on saute (compression)
        else:
            n_vides = 0
            out.append(l)
    return '\n'.join(out)


def _charger_index_definitions(conn: sqlite3.Connection) -> dict[str, _Definition]:
    """Charge toutes les définitions du paquet en mémoire, indexées par nom.

    Une seule requête : on garde tout, on filtre au moment de l'émission.
    Les colonnes JSON sont parsées ici.
    """
    index: dict[str, _Definition] = {}
    rows = conn.execute("""
        SELECT nom, type_latex, fichier_source, ligne_debut,
               macros_appelees, environnements_utilises,
               statut_rendu_atome, texte_complet, contenu_atome
        FROM paquet_definitions
    """).fetchall()
    for r in rows:
        index[r[0]] = _Definition(
            nom=r[0],
            type_latex=r[1],
            fichier_source=r[2],
            ligne_debut=int(r[3] or 0),
            macros_appelees=json.loads(r[4] or '[]'),
            environnements_utilises=json.loads(r[5] or '[]'),
            statut=r[6] or 'reutilise',
            texte_complet=r[7] or '',
            contenu_atome=r[8] or '',
        )
    return index


# ── Fermeture transitive ─────────────────────────────────────────────────────

def _fermeture_transitive(initial: set[str],
                          index: dict[str, _Definition]) -> set[str]:
    """Calcule la fermeture transitive d'un ensemble de noms de définitions.

    Pour chaque nom n dans le résultat, toutes les macros et environnements
    appelés par n (transitivement) qui ont aussi une définition dans index
    sont inclus.

    Les noms qui ne sont pas dans index sont silencieusement ignorés
    (= macros externes, primitives LaTeX, ou définitions locales d'atomes).
    """
    ferme: set[str] = set()
    todo: list[str] = list(initial)
    while todo:
        n = todo.pop()
        if n in ferme:
            continue
        ferme.add(n)
        d = index.get(n)
        if d is None:
            continue
        for m in d.macros_appelees:
            if m in index and m not in ferme:
                todo.append(m)
        for e in d.environnements_utilises:
            if e in index and e not in ferme:
                todo.append(e)
    return ferme


# ── Macros toujours nécessaires selon le type d'atome ────────────────────────
#
# Le wrapper qu'on émet autour du corps de l'atome (cf. latex_rendu_atome.py)
# appelle ces macros et environnements indépendamment du contenu de l'atome.
# Sans elles dans la fermeture de départ, on ne tirerait pas certaines
# définitions essentielles (compteurs, init, affichage des corrigés…).

WRAPPER_COMMUN = frozenset({
    '\\seqCreeCompteurs',
    '\\seqSetColorsTheme',
    '\\seqSetCodeNiveau',
    '\\seqSetCodeSequence',
})

WRAPPER_PAR_TYPE = {
    'exercice': frozenset({
        '\\seqInitCorriges',
        '\\seqInitAnnexes',
        '\\seqAfficheCorriges',
        '\\seqAfficheAnnexes',
        '\\seqCorrigesExos',
        '\\seqCorrige',
        'seqExercice',
        'seqSerieExos',
    }),
    'notion': frozenset({
        'seqNotion',
        'seqColItem',  # utilisé pour les Exemples / Remarques
    }),
    'methode': frozenset({
        'seqMethode',
        'seqColItem',
    }),
    # v0.11.1 — Fiche de résumé. Le titre passe par \seqTitreSection, le
    # contenu par seqBoiteContenuFlashcard, et la fin par
    # seqBoiteFillContenuFlashcard. Convention de nommage `seq*` cohérente
    # avec ce qu'indexe paquet_definitions (cf. seqenseigne-theme.sty,
    # post-normalisation). Un livret annuel pré-normalisation utilisait
    # les noms courts sans préfixe — ces livrets devront être recompilés
    # ou les anciens noms n'existent plus.
    # Pas de seqColItem ici : les items dans une fiche sont des paragraphes
    # LaTeX libres, pas une liste sectionnée comme pour notion/méthode.
    'fiche': frozenset({
        '\\seqTitreSection',
        'seqBoiteContenuFlashcard',
        'seqBoiteFillContenuFlashcard',
    }),
    # v0.13.5.3 — Évaluation. Le générateur services/render_evaluation.py
    # émet toujours \seqTitreEval, le barème et la liste d'objectifs
    # (envs seqEvalBareme, seqEvalObjectifs), au moins un seqEvalExercice
    # avec son \seqEvalCorrigeExo, et clôt par \seqEvalAfficheCorriges.
    # Les cases ❑ du tableau d'objectifs utilisent \ding (paquet pifont,
    # chargé via la fermeture transitive). On référence ici les macros et
    # environnements TOUJOURS utilisés ; les macros conditionnelles à
    # l'énoncé/corrigé des exos sont détectées par extraire_utilisations.
    #
    # v0.13.5.6 — Ajout de \seqInitCorrigesEval. Cette macro publique
    # encapsule \newwrite\corrfileeval (allocation TeX qui était au
    # top-level de seqenseigne-core.sty et n'était donc pas indexée par
    # le parser de paquet). Le générateur l'appelle explicitement avant
    # \seqTitreEval pour que le canal d'écriture des corrigés soit prêt
    # au moment du \openout\corrfileeval interne à \seqTitreEval.
    # Pendant exact de \seqInitCorriges et \seqInitAnnexes pour les
    # autres canaux d'écriture.
    'evaluation': frozenset({
        '\\seqInitCorrigesEval',
        '\\seqTitreEval',
        '\\seqEvalCorrigeExo',
        '\\seqEvalAfficheCorriges',
        '\\ding',
        'seqEvalBareme',
        'seqEvalObjectifs',
        'seqEvalExercice',
    }),
    # v0.13.6.1 — Cartes d'automatisme (jeux Leitner).
    #
    # Wrapper minimal en v0.13.6.1 : pas encore de macros publiques du
    # paquet (le module seqenseigne-core-cartes.sty sera créé en
    # v0.13.6.2). Côté .tex généré, on appellera juste les wrappers
    # standard pour l'aperçu d'une carte (cf. services/render_carte.py).
    #
    # À enrichir en v0.13.6.2 avec :
    #   - \seqCartePlanche, environnement seqPlancheCartes (macros à
    #     créer côté paquet)
    #   - éventuellement des compteurs d'allocation à initialiser
    #     (pattern \seqInitCorrigesEval)
    'carte_automatisme': frozenset(),
}


def _wrapper_du_type(type_atome: str) -> frozenset[str]:
    """Retourne les macros et environnements toujours nécessaires pour un type
    d'atome donné, en plus du wrapper commun à tous les atomes.

    Lève ValueError si type_atome est inconnu.
    """
    par_type = WRAPPER_PAR_TYPE.get(type_atome)
    if par_type is None:
        raise ValueError(
            f"type_atome inconnu : {type_atome!r}. "
            f"Valeurs attendues : {sorted(WRAPPER_PAR_TYPE)}"
        )
    return WRAPPER_COMMUN | par_type


# ── Détection des paquets externes ───────────────────────────────────────────

def _paquets_externes_optionnels(
    macros_atome: set[str],
    envs_atome: set[str],
    fermeture: set[str],
    index: dict[str, _Definition],
) -> set[str]:
    r"""Retourne les paquets externes (au-delà du noyau) nécessaires pour
    compiler ce préambule + cet atome.

    Sources d'information :
      1. Macros utilisées directement par l'atome qui sont mappées dans
         MACROS_PAQUETS_EXTERNES (siunitx, xint, hyperref…).
      2. Macros présentes dans les corps des définitions retenues
         (l'atome utilise \seqFrac qui en interne utilise \displaystyle ;
         pas un paquet externe, mais si une définition retenue utilisait
         \DTLfetch, il faudrait datatool).

    On filtre les pseudo-paquets et ceux déjà dans PAQUETS_NOYAU.
    """
    # Import local pour éviter le couplage à l'import du module
    from services.paquet_parseur import MACROS_PAQUETS_EXTERNES, extraire_utilisations

    paquets: set[str] = set()

    # 1. Macros utilisées directement par l'atome
    for m in macros_atome:
        pkg = MACROS_PAQUETS_EXTERNES.get(m)
        if pkg:
            paquets.add(pkg)

    # 2. Macros dans les corps des définitions retenues (uniquement celles
    # qui seront émises, donc statut != 'ignore').
    for nom in fermeture:
        d = index.get(nom)
        if d is None or d.statut == 'ignore':
            continue
        macros_corps, _ = extraire_utilisations(d.texte_complet)
        for m in macros_corps:
            pkg = MACROS_PAQUETS_EXTERNES.get(m)
            if pkg:
                paquets.add(pkg)

    paquets -= _PSEUDO_PAQUETS
    paquets -= _PAQUETS_NOYAU_NOMS
    return paquets


# ── Tri des définitions à émettre ────────────────────────────────────────────

# Ordre des fichiers source : les définitions de chaque fichier dépendent
# souvent de celles du précédent. theme.sty redéfinit des couleurs et boîtes
# en s'appuyant sur core.sty, mais inversement core.sty appelle des macros
# de theme.sty — c'est pour ça qu'on met theme **avant** core dans l'ordre
# d'émission, ce qui correspond aussi à l'ordre où le paquet seqenseigne
# les charge (theme via \input dans seqenseigne.sty avant core).
_ORDRE_FICHIERS = [
    'seqenseigne-theme.sty',
    'seqenseigne-data.sty',     # quasiment vide après filtrage 'ignore'
    'seqenseigne-core.sty',
    'seqenseigne-core-exos.sty',  # v0.11.5+ : étend core (corrigés, remédiation)
    'seqenseigne-legacy.sty',
]


def _cle_tri(d: _Definition) -> tuple[int, int]:
    """Clé de tri pour l'ordre d'émission des définitions retenues.

    1) Par fichier source selon _ORDRE_FICHIERS (autres en queue),
    2) Par numéro de ligne_debut dans le fichier (préserve les dépendances
       intra-fichier).
    """
    try:
        rang_fichier = _ORDRE_FICHIERS.index(d.fichier_source)
    except ValueError:
        rang_fichier = len(_ORDRE_FICHIERS)
    return (rang_fichier, d.ligne_debut)


# ── Construction du préambule ────────────────────────────────────────────────

def _ligne_usepackage(nom: str, options: str) -> str:
    """Formatte une ligne \\usepackage[opts]{nom}."""
    if options:
        return f'\\usepackage[{options}]{{{nom}}}'
    return f'\\usepackage{{{nom}}}'


def construire_preambule(
    conn: sqlite3.Connection,
    type_atome: str,
    macros_atome: set[str],
    envs_atome: set[str],
    options_atome: list[str] | None = None,
    paquets_tex_supplementaires: list[str] | None = None,
    tikz_libraries: list[str] | None = None,
    tblr_libraries: list[str] | None = None,
    omettre_inits_paquets: list[str] | None = None,
) -> Preambule:
    r"""Calcule et construit le préambule sur mesure pour un atome.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion à la BDD seqenseigne.
    type_atome : {'exercice', 'notion', 'methode', 'fiche', 'evaluation'}
        Détermine le wrapper systématique à inclure dans la fermeture.
        v0.13.5.3 — Ajout du type 'evaluation' pour le générateur
        services/render_evaluation.py.
    macros_atome : set[str]
        Macros LaTeX (avec le \\) utilisées par l'atome (corps + corrigé +
        variables). Produit par services.paquet_parseur.extraire_utilisations.
    envs_atome : set[str]
        Environnements (sans \\) utilisés par l'atome. Idem.
    options_atome : list[str], optional
        Options du paquet seqenseigne ('geometrie', 'scratch') détectées
        pour cet atome (cf. detecter_options_paquet). Détermine quels
        paquets supplémentaires tkz-* / scratch3 charger.
    paquets_tex_supplementaires : list[str], optional
        Paquets externes utilisés par l'atome qui ne sont pas dans
        MACROS_PAQUETS_EXTERNES (déterminés via detecter_paquets_tex_manquants
        de latex_rendu_atome.py). Ajoutés tels quels à la liste des
        \\usepackage finaux.
    tikz_libraries : list[str], optional
        v0.8.5 — Liste de bibliothèques tikz à charger inconditionnellement
        via `\\usetikzlibrary{...}` après le `\\usepackage{tikz}`. Sert de
        filet de sécurité pour les bibliothèques utilisées via styles
        (`\\node[decision]` → shapes.geometric) ou clés (`>=Latex` →
        arrows.meta) qu'on ne sait pas détecter par analyse de macros.
        Ordre préservé. Doublons dédupliqués. Si None, aucune
        bibliothèque tikz n'est ajoutée par ce mécanisme (les éventuelles
        \\usetikzlibrary internes au contenu de l'atome restent valides).
    tblr_libraries : list[str], optional
        v0.9.1 — Liste de bibliothèques tabularray à charger via
        `\\UseTblrLibrary{...}` après le `\\usepackage{tabularray}`.
        Pendant frontal exact de tikz_libraries pour les fonctionnalités
        tabularray qui ne sont accessibles qu'après chargement d'une
        bibliothèque (booktabs pour \\toprule etc., varwidth pour la clé
        `measure=`). Ordre préservé, doublons dédupliqués. Remplace
        l'init en dur de `\\UseTblrLibrary{booktabs}` qui était auparavant
        dans INITIALISATIONS_BIBLIOTHEQUES.
    omettre_inits_paquets : list[str], optional
        v0.10 — Liste de noms de paquets dont l'initialisation
        (entrée correspondante dans INITIALISATIONS_BIBLIOTHEQUES) ne
        doit PAS être émise dans le préambule. Sert aux contextes
        agrégés (récap cours, livret) où une initialisation utile en
        rendu d'atome isolé peut au contraire perturber le rendu
        agrégé. Note : actuellement aucun appelant n'utilise ce
        paramètre — il est exposé pour laisser une porte ouverte au
        cas où un futur diagnostic identifierait un cas d'usage.

    Returns
    -------
    Preambule
        Structure avec le texte complet à insérer dans le .tex et des
        statistiques pour le diagnostic.
    """
    options_atome = options_atome or []
    paquets_tex_supplementaires = paquets_tex_supplementaires or []
    tikz_libraries = list(tikz_libraries or [])
    tblr_libraries = list(tblr_libraries or [])
    omettre_inits_paquets = set(omettre_inits_paquets or [])

    # 1. Charger l'index des définitions
    index = _charger_index_definitions(conn)

    # 2. Frontière initiale : macros et envs de l'atome qui sont des
    # définitions du paquet, plus le wrapper systématique.
    wrapper = _wrapper_du_type(type_atome)
    initial = (macros_atome | envs_atome | wrapper) & set(index.keys())

    # 3. Fermeture transitive
    ferme = _fermeture_transitive(initial, index)

    # 4. Définitions à émettre (filtrer 'ignore')
    a_emettre = sorted(
        (index[n] for n in ferme if index[n].statut != 'ignore'),
        key=_cle_tri,
    )

    # 5. Paquets externes nécessaires
    paquets_optionnels = _paquets_externes_optionnels(
        macros_atome, envs_atome, ferme, index,
    )
    # Ajout des options du paquet
    if 'geometrie' in options_atome:
        for p in _PAQUETS_GEOMETRIE:
            if p not in _PAQUETS_NOYAU_NOMS:
                paquets_optionnels.add(p)
    if 'scratch' in options_atome:
        for p in _PAQUETS_SCRATCH:
            if p not in _PAQUETS_NOYAU_NOMS:
                paquets_optionnels.add(p)
    # Ajout des paquets explicitement passés (supplémentaires détectés)
    for p in paquets_tex_supplementaires:
        if p and p not in _PAQUETS_NOYAU_NOMS and p not in _PSEUDO_PAQUETS:
            paquets_optionnels.add(p)

    # 6. Construction du texte
    lignes: list[str] = []

    # --- Paquets noyau ---
    lignes.append(r'%% ── Paquets externes (noyau pour atome) ───────────────')
    for nom, opts in PAQUETS_NOYAU:
        lignes.append(_ligne_usepackage(nom, opts))

    # v0.8.6 — Marges alignées sur celles des livrets seqenseigne.
    # Sans cette ligne, l'atome compilé en isolation a une `\linewidth`
    # beaucoup plus petite que dans le livret, ce qui fait planter le
    # paquet `vwcol` qui calcule ses colonnes à partir de `\linewidth`
    # (cas concrets : N11/S12/Notion 01-02-03).
    lignes.append('')
    lignes.append(r'%% ── Marges (alignées sur les livrets) ───────────────')
    lignes.append(GEOMETRY_NEWGEOMETRY)

    # --- Paquets optionnels ---
    if paquets_optionnels:
        lignes.append('')
        lignes.append(r"%% ── Paquets externes additionnels (selon l'atome) ─────")
        for p in sorted(paquets_optionnels):
            lignes.append(_ligne_usepackage(p, ''))

    # --- Initialisations de bibliothèques ---
    # Certains paquets (tabularray, tcolorbox, tikz…) requièrent l'activation
    # d'une library après leur \usepackage. Émettons-les ici pour les paquets
    # effectivement chargés.
    paquets_charges = (
        {nom for nom, _ in PAQUETS_NOYAU} | paquets_optionnels
    )
    inits: list[str] = []
    for paquet, lignes_init in INITIALISATIONS_BIBLIOTHEQUES.items():
        if paquet in paquets_charges and paquet not in omettre_inits_paquets:
            inits.extend(lignes_init)

    # v0.8.5 — Bibliothèques tikz paramétrables.
    # Si l'utilisateur a configuré une liste (clé `tikz_libraries` dans
    # configuration.json), on émet `\usetikzlibrary{lib1, lib2, ...}` une
    # seule fois, juste après les inits ci-dessus. On vérifie que tikz est
    # chargé pour ne pas émettre cette ligne dans le vide.
    #
    # Pourquoi ce mécanisme : seqenseigne.sty charge plein de libs tikz
    # quand utilisé en entier ; notre préambule reconstruit n'en charge
    # que ce que l'analyse de macros permet de déduire. Mais des styles
    # comme `\node[decision]` (→ shapes.geometric) ou des clés comme
    # `>=Latex` (→ arrows.meta) ne sont pas des macros et ne sont donc
    # pas détectés. Cette liste sert de filet de sécurité, modifiable
    # par l'utilisateur sans toucher au code.
    if tikz_libraries and 'tikz' in paquets_charges:
        # Filtre des entrées vides au cas où (déjà fait par l'accesseur
        # de Configuration mais on refait au cas où l'appel viendrait
        # d'ailleurs). Préserve l'ordre, déduplique.
        vues: set[str] = set()
        libs_finales: list[str] = []
        for lib in tikz_libraries:
            lib = (lib or '').strip()
            if lib and lib not in vues:
                vues.add(lib)
                libs_finales.append(lib)
        if libs_finales:
            inits.append(
                r'\usetikzlibrary{' + ','.join(libs_finales) + '}'
            )

    # v0.9.1 — Bibliothèques tabularray paramétrables.
    # Pendant frontal exact de tikz_libraries (v0.8.5). Si tabularray est
    # chargé et que l'utilisateur a configuré `tblr_libraries`, on émet
    # une `\UseTblrLibrary{lib}` PAR bibliothèque (la commande n'accepte
    # pas une liste séparée par virgules contrairement à \usetikzlibrary).
    #
    # Pourquoi ce mécanisme : depuis tabularray v2025A, certaines clés
    # qui marchaient sans library nécessitent maintenant une `varwidth`
    # (clé `measure=`), `counter`, `siunitx`, etc. Le filet de sécurité
    # permet de couvrir ces cas sans diagnostic syntaxique fin du contenu.
    if tblr_libraries and 'tabularray' in paquets_charges:
        vues_tblr: set[str] = set()
        for lib in tblr_libraries:
            lib = (lib or '').strip()
            if lib and lib not in vues_tblr:
                vues_tblr.add(lib)
                # Une commande par lib (différence syntaxique vs tikz).
                inits.append(r'\UseTblrLibrary{' + lib + '}')

    if inits:
        lignes.append('')
        lignes.append(r"%% ── Initialisations de bibliothèques ─────────────────")
        lignes.extend(inits)

    # --- Définitions inlinées du paquet seqenseigne ---
    # Toutes ces définitions contiennent des @ (macros internes du paquet),
    # il faut donc les envelopper dans \makeatletter / \makeatother pour que
    # LaTeX accepte les noms à @ pendant la lecture des \newcommand etc.
    # Une fois les définitions créées, le @ peut redevenir caractère ordinaire :
    # les corps des macros gardent en mémoire les tokens à @ tels qu'ils ont
    # été parsés (comme dans un .sty chargé via \usepackage).
    lignes.append('')
    lignes.append(r'%% ── Définitions du paquet seqenseigne (inlinées) ─────')
    lignes.append(r'%%    Fermeture transitive des macros effectivement utilisées')
    lignes.append(r"%%    par l'atome — au lieu de \usepackage{seqenseigne}")
    lignes.append(r'%%    qui chargerait ~110 paquets.')
    lignes.append(r'\makeatletter')
    for d in a_emettre:
        texte = d.texte_a_emettre().rstrip()
        if texte:
            lignes.append(texte)
    lignes.append(r'\makeatother')

    # v0.11.1 — Macros transverses définies par les livrets utilisateurs.
    # \acompleter{X} produit un trait souligné de la même largeur que X
    # (zone à compléter par l'élève) — utilisée principalement par les
    # fiches de résumé en version élève, mais commun à tous les types
    # d'atomes au cas où l'enseignant l'utilise dans une notion ou un
    # exercice. Définie en dehors du \makeatletter pour rester une macro
    # utilisateur (pas de @ dans le nom).
    lignes.append('')
    lignes.append(r'%% ── Macros transverses ───────────────────────────────')
    lignes.append(r'\providecommand{\acompleter}[1]{\;\underline{\phantom{#1}}\;}')

    # Liste finale des paquets externes (pour info dans Preambule)
    paquets_finaux = list(PAQUETS_NOYAU) + [(p, '') for p in sorted(paquets_optionnels)]

    return Preambule(
        texte='\n'.join(lignes),
        paquets_externes=paquets_finaux,
        definitions_emises=[d.nom for d in a_emettre],
        nb_macros_utilisees=len(macros_atome) + len(envs_atome),
        nb_definitions_initiales=len(initial),
        nb_definitions_fermees=len(ferme),
        nb_definitions_emises=len(a_emettre),
    )
