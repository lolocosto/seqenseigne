# Patch correctif : splitter — clic intercepté

## Bug

Dans la livraison v0.6.4 (livraison B), un clic dans la zone d'un atelier
près du splitter (3 pixels de chaque côté) était systématiquement
intercepté par le splitter au lieu d'atteindre l'item / champ sous-jacent.
L'utilisateur se retrouvait en mode redimensionnement (curseur
col-resize) au lieu de cliquer normalement.

## Cause

Un pseudo-élément `.atelier-splitter::before` avec `position: absolute;
left: -3px; right: -3px` était posé pour élargir la zone hit-testing
autour de la poignée du splitter. Bien intentionné (faciliter
l'attrapage), mais il débordait sur les zones adjacentes (sidebar à
gauche, main à droite) et capturait les clics destinés à ces zones.

## Correction

- Suppression du pseudo-élément `::before` débordant.
- La poignée passe de 4px à 6px de large pour rester confortable à viser
  sans avoir besoin d'élargir artificiellement la zone cliquable.
- Aucun débordement sur les zones adjacentes : un clic ne déclenche un
  événement cliquer-tirer que s'il est exactement sur la poignée.

## Application du patch

Remplacer `appli/static/app.css` par le fichier fourni dans ce patch.
Vider le cache navigateur (Ctrl+F5) pour s'assurer que le nouveau CSS est
chargé.

Aucun autre fichier n'est modifié.
