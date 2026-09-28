# Redémarrage v0.13.6.16.2 — Patch creer_exercice

## Périmètre

Patch correctif minimal suite au déploiement de v0.13.6.16.1.

## Bug corrigé

**Symptôme** : à la création d'un exercice via la modale de choix de
série (F/A/E/EA), l'exercice apparaît classé dans la section « Autres »
de la sidebar, quelle que soit la série choisie.

**Cause** : `services/atomes.py::creer_exercice` ne posait **ni
`serie_code` ni `num`** dans l'objet exercice. À l'écriture en BdD,
ces champs restaient donc vides (`serie_code=''`, `num=NULL`). Le
service `lister_atomes_sequence` construit le champ `code` retourné
au frontend comme `serie_code + format(num)` — donc avec `serie_code`
vide, `code` était vide ou bizarre, sa première lettre était `''`,
et le bucketing par série en sidebar repliait tout dans « Autres ».

Auparavant (avant v0.13.6.16), le frontend remplissait le formulaire
avec une `serie` choisie via dropdown puis envoyait un PUT qui passait
par `modifier_exercice` (qui non plus ne posait pas `serie_code`),
ce qui faisait que tous les exos créés via UI auraient eu le même
problème depuis longtemps. Le bug est resté caché parce que dans la
pratique, tous les exos existants venaient de l'import .tex qui pose
`serie_code` correctement via `persistence/sqlite_store.py:serie_vers_code`.

**Fix** :

1. Ajout d'un mapping `_SERIE_VERS_CODE` dans `services/atomes.py` :
   ```python
   {"fondamental": "F", "avancé": "A", "exploration": "E", "approche": "EA"}
   ```
   Cohérent avec ce qu'attend la sidebar (boutons F/A/E/EA).

2. Ajout d'un helper `_prochain_num_exercice(liste, niveau, seq, serie_code)` :
   retourne `max(num existants pour cette série) + 1`.

3. `creer_exercice` calcule et pose désormais `serie_code` et `num`
   dans l'objet créé.

4. **Bonus** : `modifier_exercice` recalcule aussi `serie_code` et `num`
   quand l'utilisateur change la série d'un exercice via PUT (sinon
   l'exo aurait conservé son ancien `serie_code` après changement de
   série — bug latent qui n'avait pas encore été observé).

## Fichier livré (1 fichier)

```
appli/services/atomes.py    +_SERIE_VERS_CODE, +_prochain_num_exercice,
                            creer_exercice pose serie_code et num,
                            modifier_exercice répercute le changement
                            de série sur serie_code et num.
```

Pas de modif frontend, pas de modif tests (3238 passed inchangés).

## Vérification

- Suite complète : **3238 passed, 5 skipped, 0 failed**
- Sanity Python (ast.parse) OK

## À tester chez toi

1. Ouvrir l'atelier exercice sur une séquence avec déjà quelques
   exercices.
2. Cliquer « + Créer ». La modale apparaît.
3. Choisir F. L'exercice apparaît dans la section « Fondamentaux »
   avec un code `F0X` (X = max(num existants en F) + 1).
4. Re-créer un exercice avec série A. Apparaît dans « Avancés » avec
   code `A0Y` (Y = max(num existants en A) + 1).
5. Pareil pour E et EA.

### Test changement de série après création

1. Créer un exercice en F → apparaît en F.
2. L'ouvrir, changer la série en A via le sélecteur en haut, sauvegarder.
3. L'exercice doit basculer dans la section « Avancés » avec un nouveau
   `num` (le prochain libre en A).

## Note sur la cohérence du mapping

Trois mappings série→code coexistent dans le projet :
- `services/atomes.py::_SERIE_VERS_CODE` (créé en v0.13.6.16.2) : 'approche'→'EA'
- `persistence/sqlite_store.py:serie_vers_code` : 'approche'→'AE' (livrets)
- `services/v2_edition.py::_SERIE_CODE_EQUIVALENT` : 'EA'→'AE'

L'incohérence 'EA' vs 'AE' est gérée par le `_SERIE_CODE_EQUIVALENT`
(qui sert dans la résolution des exos pour génération LaTeX). On a
choisi 'EA' pour la création UI car c'est ce que la sidebar affiche
(`SERIE_BUCKETS.EA = { label: 'Approche (EA)' }`). À long terme,
l'harmonisation des trois mappings serait un nettoyage v0.14 sans
impact métier (juste rinçage de la dette nominative).
