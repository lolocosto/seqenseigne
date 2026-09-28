# seqenseigne — Mise à jour du matching auto des liaisons (v0.6.3e C1+)

Cette mise à jour enrichit `peuplement_03_deduire_liaisons.py` avec
3 nouvelles règles de matching automatique pour réduire le nombre
d'entrées `a_completer: true` à traiter manuellement.

## Fichiers modifiés (3)

| Fichier | Remplacement |
|---|---|
| `appli/scripts/peuplement_03_deduire_liaisons.py` | Oui (nouvelles règles) |
| `appli/scripts/peuplement_04_appliquer_liaisons.py` | Oui (rapport enrichi) |
| `appli/tests/test_peuplement_liaisons.py` | Oui (13 tests ajoutés) |

Aucun autre fichier n'est touché. 476 tests verts.

## Nouvelles règles auto

| # | Nom | Description |
|---|---|---|
| 1 | `triviale` | (existait) même (sequence, code) au niveau N-1 |
| 2 | `nom_identique_meme_seq` | même libellé, même séquence — code différent |
| 3 | `nom_identique_autre_seq` | même libellé dans une autre séquence — objectif déplacé |
| 4 | `nom_proche_meme_seq` | similarité ≥ 0.85, même séquence — variation mineure |

Les règles 2, 3 et 4 marquent la liaison `_auto_match: true` pour que
tu puisses vérifier. Pour figer la décision, supprimer `_auto_match`
et `_regle` de l'entrée YAML. Pour l'invalider, la remplacer par
un autre `precedent` ou `est_nouveau: true`.

## Procédure de mise à jour

```powershell
# Depuis D:\Enseignement\seqenseigne\

# 1. Remplacer les 3 fichiers
# (copier à la main depuis le ZIP vers appli\scripts et appli\tests)

# 2. Sauvegarder le YAML actuel au cas où (les saisies manuelles seront
# préservées, mais une sauvegarde ne fait jamais de mal)
copy appli\config\liaisons_objectifs.yaml ^
     appli\config\liaisons_objectifs.yaml.backup

# 3. Re-lancer la déduction
cd appli
..\outils\python\python.exe scripts\peuplement_03_deduire_liaisons.py

# Les 126 'a_completer' devraient largement diminuer.
# Les nouvelles entrées marquées `_auto_match: true` sont à vérifier.

# 4. Vérifier les tests
..\outils\python\python.exe -m pytest tests -q
# Attendu : 476 verts
```

## Comportement sur ton YAML existant

Les entrées de ton YAML actuel sont classées ainsi au re-run :
- Entrées **triviales** (119 chez toi) → préservées telles quelles (rejouées par règle 1)
- Entrées **à compléter** (126 chez toi) → re-tentées par règles 2, 3, 4
- Entrées avec `est_nouveau: true` **saisies à la main** → préservées
- Entrées avec `precedent: {...}` **saisies à la main** → préservées

Donc tu peux re-lancer sans perdre aucun travail déjà fait.

## Résultat attendu sur ta base

Je ne peux pas prédire le chiffre exact (ça dépend de la cohérence
des libellés entre niveaux) mais à vue de nez :
- règle 2 (nom identique même seq) : devrait attraper 30-60% des 126
- règle 3 (nom identique autre seq) : devrait attraper 5-15% des 126
- règle 4 (nom proche) : devrait attraper 5-15% des 126

Donc environ 40-80% des 126 devraient passer en auto, à vérifier
dans le YAML (elles sont marquées `_auto_match: true`).

Le reste est vraiment à compléter à la main, mais ce sera un volume
beaucoup plus raisonnable.
