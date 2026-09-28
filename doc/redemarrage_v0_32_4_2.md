# Redémarrage v0.32.4.2 — Récap cartes : num=0 sur les positions vides

Corrige l'erreur de compilation « Missing number, treated as zero » du récap,
sur les lignes incomplètes (moins de 4 cartes).

## Cause

Le fichier `recaprecto.tex` (flux généré par la macro pendant la compilation)
montrait des cellules `\seqCarteVerso[...,num=,codecouleur=nombres]` avec un
`num` **vide** — sur les positions manquantes d'une ligne de moins de 4 cartes
(ex. la dernière ligne de S14 : 2 cartes + 2 positions vides). Les macros
`\seqCarteRecto` / `\seqCarteVerso` attendent un numéro ; un `num` vide déclenche
« Missing number ».

`rendre_ligne_recap` remplissait les positions vides avec `num{pos}={}` (vide).

## Correctif

Les positions vides utilisent désormais `num=0` (un nombre valide). Le contenu
recto/verso reste vide (macros vides), donc la cellule est visuellement vide,
mais le `num` numérique satisfait la macro.

## Fichiers

- `services/render_carte_centralise.py` : positions vides → `num=0`.

## Tests

- pytest : 3905 passed, 7 skipped. vitest : 192 passed. Vérifié : plus aucun
  `num=` vide dans le .tex généré (N11, 29 lignes).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Nécessite le
paquet à jour (avec `\expandafter` sur les recto/verso, déjà installé).
Recompiler le récap : la compilation doit passer et l'impression recto-verso
« bord court » doit être alignée.
