# Redémarrage v0.14.8 — Remédiation optionnelle dans l'UI Exercice

## Position dans la roadmap

| Étape | Statut |
|---|---|
| v0.14.7 : Chantier v1 cosmétiquement clos | ✓ Déployé |
| **v0.14.8 : Remédiation optionnelle** (cette livraison) | ⏳ |
| v0.15 : Classe `AtelierAssemblage` + migration Évaluation | À venir |

## Cadrage validé (Q1-Q3)

| Question | Réponse |
|---|---|
| Q1 — Lien avec série F/A | (b) Case dans le périmètre F/A (E/AE = cadre caché comme avant) |
| Q2 — Stockage de l'état | (a) Dérivé des champs (pas de nouveau champ BDD) |
| Q2bis — Décocher avec contenu | (i) Confirmation, vider à la sauvegarde |
| Q3 — Validation pédagogique | (a) Symétrie obligatoire au passage en `valide` |

## Ce qui change dans cette livraison

### 1. UI — case à cocher en tête du cadre Remédiation

Dans l'atelier Exercice, pour les séries F (fondamental) et A
(avancé), le cadre Remédiation contient désormais en tête une case à
cocher **« Rédiger une remédiation pour cet exercice »**.

- **Décochée** : le contenu du cadre (champs énoncé/corrigé +
  cadre de réponse) est masqué. Rien n'est inséré dans le `.tex`
  pour la remédiation.
- **Cochée** : le contenu s'affiche. Les champs Énoncé et Corrigé
  de remédiation sont marqués obligatoires (étoile rouge). Le `.tex`
  émettra `\seqRemediation{...}{...}`.

### 2. Comportement de bascule de la case

- **Cocher** : affiche le contenu du cadre. Si l'exo avait déjà un
  contenu de remédiation (champs non vides), il est restauré.
- **Décocher avec contenu** : confirmation explicite demandée
  (`confirm()` natif). Si l'utilisateur valide, les textareas sont
  vidés et la prochaine sauvegarde persistera les champs vides. Si
  l'utilisateur annule, la case est recochée et rien ne change.

### 3. Initialisation à l'ouverture d'un exercice

L'état de la case est **dérivé du contenu** :
- Si `remed_enonce` ou `remed_corrige` est non vide → case cochée.
- Sinon → case décochée.

### 4. Comportement à la sauvegarde

Si la case est décochée, `collecterFormulaire()` force les champs
`remed_enonce`, `remed_corrige` et `cadre_reponse_lignes_remed` à
leurs valeurs neutres (vides, 0). Le payload envoyé au backend est
donc cohérent avec la décision.

### 5. Validation pédagogique étendue

Le hook `_valider_exercice_hook` (qui contrôle le passage d'un
exercice en état `valide`) est étendu pour vérifier la **symétrie**
des champs de remédiation :

- Si `remed_enonce` et `remed_corrige` sont tous deux vides → pas de
  remédiation, OK.
- Si tous deux sont non vides → remédiation complète, OK.
- Si UN seul des deux est non vide (XOR) → **bloqué** au passage en
  `valide` avec une raison explicite ("Remédiation activée : le
  corrigé de remédiation est vide.", ou similaire).

Cette règle garantit la cohérence métier : on ne peut pas valider
un exercice avec une remédiation à moitié rédigée.

### 6. Aucun changement BDD

Pas de nouveau champ. Pas de migration. Le schéma reste tel quel.
L'état "remédiation activée" est purement dérivé du contenu des champs
`remed_enonce` / `remed_corrige` existants.

## Fichiers livrés

```
MODIFIÉS
  appli/templates/index.html        (case à cocher + contenu masqué par défaut)
  appli/static/atelier_exercice.js  (toggleRemediation + visibilité + collect)
  appli/services/atomes.py          (hook _valider_exercice_hook étendu)

NOUVEAU
  appli/tests/test_v0_14_8_remediation_optionnelle.py  (10 tests)
  appli/doc/redemarrage_v0_14_8.md
```

## Vérifs

- Suite complète : **3389 passed, 6 skipped, 0 failed**
- 10 nouveaux tests v0.14.8 :
  - 3 tests : exo sans remédiation (validation comme avant)
  - 2 tests : exo avec remédiation complète (passe en valide)
  - 4 tests : exo avec remédiation partielle XOR (bloqué)
  - 1 test : activation dérivée des champs (sanity)
- Sanity JS et Python OK

## Procédure d'application

1. **Décompresser le ZIP** dans le répertoire racine `seqenseigne/`.
   Aucun fichier à supprimer manuellement.
2. **Lancer la suite de tests** :
   ```
   cd appli
   python -m pytest -q
   ```
   Attendu : ~3389 passed, ~6 skipped, 0 failed (peut varier sous
   Windows).
3. **Tests fonctionnels manuels** :

### a) Ouvrir un exercice F existant sans remédiation

- Cadre Remédiation visible (série F).
- Case « Rédiger une remédiation » décochée.
- Champs énoncé/corrigé NON visibles (masqués sous la case décochée).

### b) Cocher la case

- Les champs Énoncé / Corrigé de remédiation s'affichent.
- Les étoiles d'obligation (rouge) sont visibles à côté des labels.
- Le bouton "Enregistrer" en haut indique "modifié".

### c) Remplir les deux champs et sauvegarder

- Sauvegarde sans erreur.
- Rouvrir l'exo : la case est cochée, le contenu est restauré.

### d) Décocher la case sans rien avoir saisi

- Confirmation NON demandée (rien à perdre).
- Contenu masqué.
- Sauvegarder : remed_enonce et remed_corrige restent vides.

### e) Décocher la case avec contenu non vide

- Confirmation demandée : "Désactiver la remédiation supprimera
  l'énoncé et le corrigé de remédiation à la prochaine sauvegarde.
  Continuer ?"
- Cliquer **Annuler** : la case se recoche, le contenu est préservé.
- Recliquer pour décocher et cliquer **OK** : le contenu est vidé
  immédiatement dans l'UI. Sauvegarder : les champs sont vides en BDD.

### f) Essayer de valider un exercice avec remédiation partielle

- Remplir Énoncé de remédiation, laisser Corrigé vide.
- Cliquer "Valider" : message d'erreur "L'exercice ne peut pas être
  validé en l'état" avec raison "Remédiation activée : le corrigé de
  remédiation est vide.".

### g) Vérifier qu'un exo de série E ou AE n'a plus de cadre Remédiation

- Ouvrir un exo de série E (exploration) ou AE (approche).
- Le cadre Remédiation ne doit PAS être visible (comportement v0.11.6
  préservé : la remédiation reste cantonnée à F/A).

### h) Compiler le PDF d'un exercice

- **Sans remédiation** (case décochée à la sauvegarde) : le PDF ne
  contient pas de section remédiation.
- **Avec remédiation** (case cochée + champs remplis) : le PDF
  contient la section remédiation comme avant.

## Compatibilité ascendante

- Les exos existants qui avaient déjà du contenu de remédiation
  auront automatiquement la case cochée à l'ouverture (dérivation).
- Les exos sans remédiation auront la case décochée.
- Aucune migration de données nécessaire.

## Limites connues

- Le marquage "modifié" est déclenché par le changement de la case
  (event `change`) ET par la modification des textareas. Donc cocher
  + saisir + sauvegarder fonctionne, mais cocher seul (sans saisir)
  fait apparaître "modifié" — ce qui est correct au sens où le
  formulaire collecté reflète bien le nouvel état (case cochée, mais
  champs vides forcés à vides à la sauvegarde si elle est décochée
  avant).

- Si l'utilisateur saisit du contenu dans les textareas alors que la
  case est décochée (cas qui ne devrait pas arriver puisqu'ils sont
  masqués), le contenu serait perdu à la sauvegarde
  (`collecterFormulaire` les force à vides). Le pattern UI courant
  rend ce cas inaccessible.
