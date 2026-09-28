# Redémarrage v0.27.0 — Progression de MER par niveau (onglet dédié)

Refonte des progressions de mise en route : elles deviennent **communes à un
niveau** (comme la progression principale), avec un **onglet dédié** dans Suivi
annuel, juste avant « Progression principale ».

## Changement de modèle

- `progression_mer` passe de **par classe** à **par niveau** :
  `(niveau, annee, ref_mer_id, ref_mer_source)`. Migration : les bases avec
  l'ancienne colonne `classe_id` voient la table recréée (les rares
  progressions par classe sont à recomposer au niveau — une seule, incomplète,
  chez l'utilisateur).
- Les parties posées sont communes au niveau. Plus besoin de refaire la
  progression pour chaque classe.

## Onglet « Progression de MER »

Nouveau sous-onglet de Suivi annuel (avant « Progression principale »), même
esprit visuel que la progression principale :
- **colonne gauche** : référentiel MER (externes validés du niveau) + parties
  disponibles à ajouter ;
- **colonne droite** : la progression composée (parties ordonnées, ↑/↓/×, total
  de séances) + le **planning** (frise).
- Sélecteurs globaux : établissement, niveau, classe.
  - **aucune classe** → planning **théorique** (PDF A4 : parties et plages de
    séances, sans dates réelles) ;
  - **une classe** → planning **réel** (frise A3, dates de la classe, tenant
    compte de ses indisponibilités).

## Onglet « Mises en route » allégé

Il ne garde que la configuration par classe (fait des MER + mode) et le planning
des automatismes. La composition de la progression MER a migré vers l'onglet
dédié.

## Fichiers

- `persistence/sqlite_store.py` : `progression_mer` par niveau + migration de
  recréation.
- `services/progression_mer.py` : `lire_par_niveau` / `creer_ou_lire` par
  niveau.
- `routes/progression_mer.py` : routes par niveau (`/api/progression-mer?niveau`
  …), planning classe (via le niveau de la classe), planning théorique PDF.
- `services/planning_mer_tex.py` : `generer_planning_theorique_tex` (A4).
- `templates/index.html` : sous-onglet + panneau `stab-progmer` ; onglet MER
  allégé ; niveau routé par `onNiveauChangeGlobal`.
- `static/app.js` : `progmer` dans le mapping (établissement/niveau/classe),
  init, `onNiveauChangeGlobal`, `onClasseChange` route vers progmer.
- `static/progression_mer.js` (nouveau) : atelier progression MER.
- `static/mer.js` : simplifié (progression retirée).

## Tests

- vitest : 193 passed (0 régression).
- Backend par niveau vérifié : migration (colonne niveau, plus de classe_id),
  progression par niveau, planning d'une classe utilisant la progression de son
  niveau. Compilation du planning théorique OK.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. La table `progression_mer` est
recréée au premier lancement (migration). Suivi annuel › Progression de MER.

## Note (à corriger en v0.27.1)

L'effet fin des indisponibilités (choix **absorber** / **décaler** par
indisponibilité, cf. cadrage) n'est pas encore là : pour une classe, les
indisponibilités retirent des séances, ce qui décale naturellement la fin. Le
choix absorber/décaler viendra en v0.27.1.

Le bug d'affichage « planning s'ouvre en externe » (signalé sur l'ancienne UI
MER) est résorbé : le planning s'affiche en iframe dans l'onglet dédié.
