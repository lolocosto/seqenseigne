# seqenseigne v0.5.2 — Livraison

## Ce qui change

### Corrections
- **Sous-onglets "Suivi des séquences" et "Gestion des classes"** : s'affichent à nouveau.
  Cause : `</div>` manquant dans `stab-progression`, qui faisait imbriquer à tort
  les deux autres sous-onglets dedans (donc cachés avec lui).
- **Listes de choix dupliquées** : les 3 `<select>` (année, classe, séquence)
  qui étaient aussi dans `stab-suivi` sont supprimés. Ils causaient aussi
  le bug "élèves de la 1re classe quelle que soit la classe choisie".
- **Collision d'id d'élève en mode SQLite** : les eid sont désormais des UUID
  courts `e_xxxxxxxx` (au lieu de `e01`, `e02`…). L'ancien format causait des
  écrasements silencieux en base quand on importait une seconde classe.

### Nouveautés
- **Vérif anti-doublon à l'import** : rejet 409 si une classe avec
  (même nom, même établissement, même année) existe déjà.
  Comparaison insensible à la casse et aux espaces.

## Fichiers modifiés

```
appli/templates/index.html
appli/routes/progression.py
appli/services/classes.py
appli/importers/sequencesdb.py
appli/tests/test_services.py
appli/tests/test_routes.py
appli/tests/test_progression.py
```

## Tests

**293 tests verts** (291 précédents + 2 nouveaux pour l'anti-doublon).

```
cd F:\Enseignement\seqenseigne\appli
..\outils\python\python.exe -m pytest tests\ -q
```

## Procédure de déploiement

1. Dézipper cette archive à la racine de `F:\Enseignement\seqenseigne\` :
   les fichiers s'installent directement aux bons emplacements.
2. **Vider les données de suivi** (les classes actuelles sont contaminées
   par l'ancien bug d'eid) :
   - Via l'UI : Administration → reset suivi.
   - OU supprimer `data/seqenseigne.db` et relancer l'appli (la DB sera
     recréée vide ; les progressions en JSON sur disque sont conservées).
3. Recharger la page navigateur (Ctrl+F5).
4. Ré-importer les 3 classes via Administration → Import suivi.

## Vérifications rapides après déploiement

Dans la console navigateur (F12) :

```js
// doit retourner "tab-classe", plus "stab-progression"
document.getElementById('stab-suivi').parentElement.id
```

- Changer de classe dans le sélecteur : les élèves affichés doivent
  correspondre à la classe sélectionnée.
- Tenter de réimporter une classe déjà présente : message d'erreur explicite.
