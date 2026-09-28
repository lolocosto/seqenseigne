# Redémarrage v0.21.0.1 — Indisponibilités : modification + dates en français

Deux ajustements de l'écran Indisponibilités (v0.21.0). Purement front (un
fichier, `static/indispo.js`).

## 1. Modification d'une indisponibilité

Un bouton **« Modifier »** sur chaque ligne pré-remplit le formulaire avec les
valeurs de l'indisponibilité (type, dates, créneaux, portée, classes, motif).
Le formulaire passe alors en mode édition : son titre devient « Modifier
l'indisponibilité », le bouton devient « Enregistrer les modifications », et un
bouton « Annuler » apparaît. L'enregistrement fait un PUT
`/api/indisponibilites/<id>` (endpoint déjà présent depuis v0.21.0).

Le mode édition est automatiquement quitté si l'indisponibilité éditée
disparaît (suppression, changement d'établissement ou d'année).

## 2. Dates au format français dans la liste

La colonne « Quand » affiche les dates en **jj/mm/aaaa** (au lieu de
aaaa-mm-jj) : « le 22/09/2026 », « du 09/09/2026 au 11/09/2026 », « le
11/09/2026, de S1 à S4 ». Les champs de saisie restent des sélecteurs de date
natifs (affichés selon la locale du navigateur).

## Fichiers

- `static/indispo.js` : helper `_indispoDateFr`, état `INDISPO_EDIT_ID`,
  formulaire adaptatif création/édition (`indispoRenderForm`),
  `indispoEnregistrer` (POST ou PUT), `indispoEditer` / `indispoAnnulerEdition`,
  bouton « Modifier » dans la liste, dates FR dans `_indispoDescription`.

## Tests

- vitest : 192 passed (0 régression). Syntaxe indispo.js OK.
- Vérifié : format date FR (22/09/2026…), PUT de modification (motif + date mis
  à jour, statut 200).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement front (un fichier).

## Suite

- v0.21.1 : effet des indisponibilités sur la progression principale.
