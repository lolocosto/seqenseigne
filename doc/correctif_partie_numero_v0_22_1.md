# Correctif données v0.22.1 — partie_numero des référentiels figés

Corrige l'incohérence qui empêchait de placer la **2nde partie** d'une séquence
dans l'atelier Progression.

## Le problème

Dans les référentiels figés (N11_v2024, N11_v2025…), **tous** les objectifs
avaient `partie_numero = 1`, y compris ceux de la 2nde partie — celle-ci n'étant
identifiée que par le **préfixe du code** (codes 0x = partie 1, 1x = partie 2,
2x = partie 3). Conséquence : `lister_parties_referentiel` (qui déduit les
parties de `partie_numero`) ne voyait qu'une partie par séquence, et l'atelier
Progression n'affichait donc que la partie 1. Impossible de placer la partie 2.

## Origine

Les objectifs de ces référentiels ont `partie_numero = 1` par défaut (import /
figeage n'ayant pas renseigné le champ depuis la convention de code). La
convention 0x/1x/2x, elle, est fiable et cohérente sur tous les référentiels
(vérifiée : S01, S03, S05, S11, S12 ont bien 2 parties en N11_v2024 et v2025).

## Le correctif (script de données)

`outils/corriger_partie_numero_referentiels.py` :
- parcourt les référentiels **figés** (verrouille / utilise) ;
- recale `referentiel_objectifs.partie_numero` d'après le préfixe du code
  (0x→1, 1x→2, 2x→3…) ;
- régénère `referentiel_parties` (découpage figé) de façon cohérente, en
  préservant les `nb_seances_R_AE` existants.

Idempotent, transactionnel, dry-run par défaut.

## Utilisation

```
# aperçu (aucune écriture) :
python -m outils.corriger_partie_numero_referentiels

# corriger tous les référentiels figés :
python -m outils.corriger_partie_numero_referentiels --apply

# ou cibler un référentiel :
python -m outils.corriger_partie_numero_referentiels --ref N11_v2025 --apply
```

Tester sur une copie de la base d'abord.

## Vérifié

Sur une copie de la base réelle : N11_v2025 → 20 objectifs recalés,
`lister_parties_referentiel` renvoie ensuite 19 parties (14 séquences dont 5 à
2 parties), et S01 expose bien partie 1 (codes 01-04) et partie 2 (codes 11-13).
Après application, l'atelier Progression affichera S01-P1, S01-P2, etc.

## Note

Ce correctif traite le **problème 2** (parties 2 invisibles). Le **problème 1**
(changer le référentiel support d'une progression, ex. passer 2026-2027 de
N11_v2024 à N11_v2025) est une fonctionnalité distincte, livrée séparément.
