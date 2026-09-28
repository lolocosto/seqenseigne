# Redémarrage v0.30.1 — Tableau de bord : barre d'actions + tuile atomes actionnable

Rend le tableau de bord actionnable : une barre d'actions rapides et une action
sur la tuile « Atomes à finaliser ».

## Contenu

### Barre d'actions rapides
Au-dessus de la grille de tuiles, une barre (hors tuiles) qui regroupe les
actions globales. Pour l'instant : un bouton **⚙ Paramètres** qui ouvre l'onglet
Préférences (où vivent les paramètres ; la configuration de la barre pourra y
être ajoutée plus tard). Structure prévue pour accueillir d'autres raccourcis.

### Tuile « Atomes à finaliser » → actionnable
Chaque ligne (un niveau) est cliquable : elle ouvre l'**atelier de conception**
en portée **Niveau**, sur ce niveau (option (a) — pas de filtre « en cours »
pour l'instant ; on arrive au bon endroit). Curseur main + surbrillance au
survol + chevron « › » pour signaler l'action.

La tuile « Séances de la semaine » reste en affichage seul (son action naturelle
serait le suivi de séance, qui n'existe pas encore).

## Mécanisme

Nouvelle fonction `ouvrirAtelierNiveau(niveau)` (dans `app.js`) : pose la portée
Niveau + le niveau en localStorage (comme le deeplink existant le fait pour la
portée Séquence), puis bascule sur l'onglet Ateliers. Réutilise le mécanisme de
navigation interne en place. Le deeplink URL existant (atome précis) est
inchangé.

## Fichiers

- `templates/index.html` : barre d'actions `tdb-barre-actions` (bouton
  Paramètres).
- `static/app.js` : `ouvrirAtelierNiveau`.
- `static/tableau_bord.js` : lignes atomes cliquables ; `tdbOuvrirParametres`.

## Tests

- `node --check` (exit 0) + exécution sans erreur (`tableau_bord.js`). vitest :
  193 passed. Page rendue vérifiée (barre + bouton présents). Logique
  `ouvrirAtelierNiveau` vérifiée : pose portée=niveau, niveau, clique l'onglet.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.30.0.

## Suite

- Nouvelles tuiles (éléments non rattachés, derniers résultats d'évaluation) avec
  leurs actions.
- Autres raccourcis dans la barre d'actions ; configuration de la barre dans les
  Préférences.
- Cadrage (sans code) : suivi de séance (retour des profs d'EPS) ; architecture
  mobile (app installée vs serveur hébergé).
