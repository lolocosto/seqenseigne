"""Service d'exposition de paquet_definitions vers le frontend.

Filtre et formate les définitions du paquet `seqenseigne` pour l'onglet
« Tout le paquet » de l'éditeur LaTeX (v0.13.7.1+).

Conventions
-----------

  - Seuls les types `command`, `environment`, `tcolorbox` sont exposés.
    Les types `cmdkey` (paramétrage de tcolorbox), `columntype`, `counter`,
    `if` sont des outils internes du paquet, pas insérables tels quels
    par un enseignant.
  - Les macros « internes » (nom contenant `@`) sont exclues. C'est la
    convention LaTeX classique : les macros publiques n'ont pas de `@`.
  - Seuls 4 fichiers sources sont exposés : core, theme, exos,
    carte-automatisme. Les autres (data, legacy, core-eval) contiennent
    de la plomberie non pertinente pour la rédaction d'atomes.
  - **Macros structurelles** (v0.13.7.2.1) : par défaut, on exclut les
    macros que l'app **ajoute automatiquement** autour du contenu
    saisi par l'enseignant (seqExercice, seqCorrige, seqNotion, etc.).
    Les insérer manuellement dans un textarea produirait du LaTeX cassé
    (double-enrobage) ou simplement inutile.
    Un paramètre `inclure_structurelles=True` permet de réafficher ces
    macros pour les utilisateurs experts (case à cocher côté UI).

La structure de retour est pensée pour la navigation UI : panneau gauche
= liste de fichiers, panneau droit = liste des définitions du fichier
sélectionné.

Note de cohérence avec preambule_atome.py
-----------------------------------------

Le module `services.preambule_atome` définit `WRAPPER_COMMUN` et
`WRAPPER_PAR_TYPE` qui listent les macros utilisées par l'app pour
enrober le contenu d'un atome. La liste `MACROS_STRUCTURELLES` ci-
dessous **dérive** logiquement de ces wrappers, mais sert une finalité
différente (filtrage UI vs. fermeture transitive des dépendances).
Les deux listes ne sont volontairement PAS partagées :

  - `WRAPPER_*` inclut `seqColItem` qui est utilisé pour le rendu des
    sections « Exemples / Remarques », mais c'est aussi un
    environnement **légitimement utilisable** par l'enseignant pour
    faire des listes multi-colonnes dans son contenu. Donc pas
    structurel au sens UI.

  - `MACROS_STRUCTURELLES` ajoute `\\seqTitreLivret*` qui n'est jamais
    présent dans un atome (utilisé pour les livrets agrégés), mais
    qu'on veut malgré tout cacher du panneau pour éviter la confusion.

Quand on ajoute une macro structurelle dans `preambule_atome.py`, il
faut **réfléchir** si elle doit aussi être ajoutée ici. La réciproque
n'est pas forcément vraie.
"""

from __future__ import annotations
import sqlite3


# Fichiers exposés et leur libellé UI court.
# L'ordre est l'ordre d'affichage dans le panneau de navigation.
FICHIERS_EXPOSES: dict[str, str] = {
    'seqenseigne-core.sty':              'Cœur',
    'seqenseigne-theme.sty':             'Thème',
    'seqenseigne-core-exos.sty':         'Exercices',
    'seqenseigne-carte-automatisme.sty': 'Cartes',
}

# Types LaTeX exposables.
TYPES_EXPOSES: set[str] = {'command', 'environment', 'tcolorbox'}


# v0.13.7.2.1 — Macros et environnements que l'app émet automatiquement
# autour du contenu utilisateur. Ces noms ne doivent pas apparaître par
# défaut dans l'onglet « Tout le paquet » de l'éditeur : les insérer
# manuellement produirait soit du LaTeX cassé (double enrobage), soit
# rien (machinerie sans objet hors d'un livret).
#
# Convention de nommage : commands préfixées d'un backslash, environments
# sans backslash (cohérent avec ce qu'expose paquet_definitions et avec
# preambule_atome.WRAPPER_PAR_TYPE).
MACROS_STRUCTURELLES: set[str] = {
    # ── Setup commun à tous les atomes ────────────────────────────────────
    '\\seqSetColorsTheme',
    '\\seqSetCodeNiveau',
    '\\seqSetCodeSequence',
    '\\seqCreeCompteurs',
    '\\seqRAZCompteurs',

    # ── Wrapper exercice ──────────────────────────────────────────────────
    'seqExercice',          # environnement enrobant l'énoncé
    'seqSerieExos',         # environnement enrobant la série
    '\\seqCorrige',         # commande enrobant le corrigé (champ corrigé séparé)
    '\\seqCorrigesExos',    # option de livret renommée par l'app
    '\\seqInitCorriges',
    '\\seqInitAnnexes',
    '\\seqInitRemediation',
    '\\seqAfficheCorriges',
    '\\seqAfficheAnnexes',
    '\\seqAfficheRemediations',
    '\\seqAfficheCorrigesRemediation',
    '\\seqRemediation',     # commande enrobant la remédiation (champ dédié)
    '\\seqCadreReponse',    # pilotée par la case à cocher de l'atelier

    # ── Wrapper notion ────────────────────────────────────────────────────
    'seqNotion',            # environnement enrobant le corps de notion

    # ── Wrapper méthode ───────────────────────────────────────────────────
    'seqMethode',           # environnement enrobant le corps de méthode

    # ── Wrapper fiche de résumé ───────────────────────────────────────────
    '\\seqTitreSection',    # émise par l'app pour le titre de fiche
    'seqBoiteContenuFlashcard',
    'seqBoiteFillContenuFlashcard',

    # ── Wrapper évaluation ────────────────────────────────────────────────
    '\\seqInitCorrigesEval',
    '\\seqTitreEval',
    '\\seqEvalCorrigeExo',
    '\\seqEvalAfficheCorriges',
    'seqEvalBareme',
    'seqEvalObjectifs',
    'seqEvalExercice',

    # ── Wrapper carte d'automatisme ───────────────────────────────────────
    '\\seqCarteAuto',

    # ── Macros de livret jamais utilisables dans un atome ─────────────────
    '\\seqTitreLivret',
    '\\seqTitreLivretAuto',
}


def lister_definitions(conn: sqlite3.Connection,
                       inclure_structurelles: bool = False) -> dict:
    """Liste toutes les définitions exposables, groupées par fichier source.

    Args:
      conn: connection SQLite ouverte sur la base seqenseigne.
      inclure_structurelles: si False (défaut), exclut les macros que
        l'app émet automatiquement autour du contenu utilisateur (cf.
        MACROS_STRUCTURELLES). Si True, retourne tout — pour l'option
        « afficher les macros structurelles » côté UI.

    Returns:
      Dictionnaire au format :
        {
          "fichiers": [
            {
              "nom":  "seqenseigne-core.sty",
              "label": "Cœur",
              "commands": [
                {"nom": "\\seqFrac", "args_spec": "[2]"},
                ...
              ],
              "environments": [
                {"nom": "seqDefinition", "args_spec": "[2]"},
                ...
              ],
              "tcolorbox": [
                {"nom": "boiteTitreGen", "args_spec": "[1]"},
                ...
              ],
            },
            ...
          ]
        }

      Pour les environnements et tcolorbox, `nom` ne contient PAS le
      backslash initial (puisque ce sont des noms d'environnement, pas
      des macros).
    """
    fichiers_out = []
    for fichier, label in FICHIERS_EXPOSES.items():
        bloc = {
            "nom": fichier,
            "label": label,
            "commands": [],
            "environments": [],
            "tcolorbox": [],
        }
        rows = conn.execute(
            """
            SELECT nom, type_latex, args_spec
            FROM paquet_definitions
            WHERE fichier_source = ?
              AND type_latex IN ('command', 'environment', 'tcolorbox')
              AND instr(nom, '@') = 0
            ORDER BY nom
            """,
            (fichier,),
        ).fetchall()
        for row in rows:
            nom = row[0]
            # v0.13.7.2.1 — Filtre des macros structurelles (sauf si
            # explicitement demandé)
            if not inclure_structurelles and nom in MACROS_STRUCTURELLES:
                continue
            entree = {"nom": nom, "args_spec": row[2] or ""}
            if row[1] == 'command':
                bloc["commands"].append(entree)
            elif row[1] == 'environment':
                bloc["environments"].append(entree)
            else:  # 'tcolorbox'
                bloc["tcolorbox"].append(entree)
        fichiers_out.append(bloc)
    return {"fichiers": fichiers_out}
