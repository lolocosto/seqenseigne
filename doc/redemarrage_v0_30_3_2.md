# Redémarrage v0.30.3.2 — Filtre « en cours » depuis la tuile : clic du vrai bouton

Corrige le filtrage d'état quand on ouvre un atelier depuis la tuile « Atomes à
finaliser », en particulier pour les cartes d'automatisme.

## Cause

La v0.30.3(.1) posait le filtre en écrivant la variable globale
`ATL_FILTRE_ETAT[<type>] = 'en_cours'`. Or les ateliers ne partagent pas tous le
même mécanisme de filtre :
- exercice / notion / méthode / fiche : filtre générique
  (`atelAtomeFiltrerEtat`, variable `ATL_FILTRE_ETAT`) ;
- **carte d'automatisme** : mécanisme **propre** (`ATELIER_CARTE.filtreEtat`),
  qui n'est PAS `ATL_FILTRE_ETAT`.

Conséquences pour la carte : le filtre programmatique n'était pas pris en compte
par l'atelier, le bouton visuel restait sur « Tous », et l'état interne était
incohérent (passer sur « Validé » donnait une liste vide).

## Correctif

Au lieu de manipuler une variable, on **clique le vrai bouton « En cours »** du
panneau de l'atelier ouvert (`#atl-<atelier> .exo-etat[data-etat="en_cours"]`).
Chaque atelier applique alors son propre mécanisme de filtre, le bouton visuel
est synchronisé, et la liste chargée reste complète (le filtre est un filtre
d'affichage) — donc rebasculer sur « Tous » ou « Validé » fonctionne.

## Fichiers

- `static/app.js` : `ouvrirAtelierAtomesEnCours` clique le bouton « En cours »
  du panneau de l'atelier (après application de la portée et activation de
  l'atelier).

## Tests

- `node --check` (exit 0). vitest : 193 passed. Logique vérifiée : carte N10 →
  niveau N10, atelier carte_automatisme, bouton « En cours » cliqué sur le bon
  panneau.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement front. Se déploie
par-dessus la v0.30.3.1. Vérifier sur les cartes : le filtre « En cours » est
bien actif à l'ouverture, et « Validé » affiche ensuite les cartes validées.
