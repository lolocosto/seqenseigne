# Fix FK `objectif_exos` → `exercices` (crash import multi-niveaux)

Livré le 23 avril 2026, en réponse à la régression observée après
déploiement de `correctifs_imports_ui` :

```
POST /api/scanner/lancer → 500
sqlite3.IntegrityError: FOREIGN KEY constraint failed
  File ".../persistence/sqlite_store.py", line 1088, in ecrire_exercices
    conn.execute("DELETE FROM exercices")
```

## Diagnostic

Deux problèmes se combinaient pour produire le crash :

### 1. FK RESTRICT ignorée par `ecrire_exercices`

La table `objectif_exos` a une contrainte
`exercice_id → exercices.id ON DELETE RESTRICT`. Depuis `nettoyage_6`,
`scanner_vers_bdd` appelle `peupler_v2_depuis_base` à la fin de chaque
scan, ce qui peuple `objectif_exos` avec les liaisons pédagogiques
(objectif → exercice).

Au **scan suivant** (ou au 2e scan parallèle), `ecrire_exercices`
faisait un `DELETE FROM exercices` brutal. SQLite refusait : les
lignes `objectif_exos` pointaient encore vers ces exercices.

### 2. Scans lancés en parallèle

Côté UI (`adminImporter` dans `app.js`), les 3 niveaux étaient lancés
avec `Promise.all(niveaux.map(...))`. Visible dans les logs Flask de
Laurent aux timestamps 12:01:30 / 12:01:31 / 12:01:31 (trois POST
dans la même seconde).

Les 3 scans écrivent concurremment sur `exercices`, `objectifs` et
`objectif_exos`. Même sans la FK RESTRICT, la cohérence n'était pas
garantie — le DELETE+INSERT complet sur `exercices` ne tolère aucune
concurrence.

## Correctifs

### A. `static/app.js` — scans séquentiels

Remplacement du `Promise.all` par une boucle `for ... of` avec `await` :

```js
const resultats = [];
for (const niv of niveaux) {
  const r = await api('/api/scanner/lancer', { ... });
  resultats.push(r);
}
```

Le traitement séquentiel garantit la cohérence : un scan termine
(jusqu'au peuplement v2 inclus) avant que le suivant ne commence.

### B. `persistence/sqlite_store.py` — `ecrire_exercices` diff-based

Refonte complète de la méthode. Plutôt qu'un `DELETE FROM exercices`
+ réinsertion complète (qui casse la FK RESTRICT), on calcule la
différence entre la base et la liste cible :

- **Exos à supprimer** (en base mais pas dans la liste) : on nettoie
  d'abord leurs liaisons `objectif_exos` (RESTRICT) et
  `exercice_objectifs` (CASCADE, explicité pour la clarté), puis on
  supprime les exos eux-mêmes.
- **Exos à mettre à jour** (ids présents des deux côtés) : `UPDATE`
  in-place. Les liaisons `objectif_exos` sont **préservées**, seules
  les liaisons `exercice_objectifs` (purement informatives) sont
  reconstruites à partir des `objectifs_codes` du scanner.
- **Exos à insérer** (dans la liste mais pas en base) : `INSERT`
  classique.

Cette approche résout les deux problèmes :

- Plus de DELETE + FK RESTRICT : on nettoie les liaisons **juste pour
  les exos qui disparaissent**.
- Les liaisons v2 des niveaux scannés précédemment sont préservées
  quand on scanne un autre niveau. Auparavant un DELETE+INSERT les
  aurait toutes invalidées.

## Fichiers livrés

| Fichier | Nature |
|---|---|
| `persistence/sqlite_store.py` | `ecrire_exercices` refondu en diff-based |
| `static/app.js` | Sérialisation des 3 scans dans `adminImporter` |
| `tests/test_ecrire_exercices_fk.py` | NOUVEAU — 7 tests de non-régression |

## Déploiement côté Laurent

Écraser ces 2 fichiers, Ctrl+F5 côté navigateur.

Procédure de test :

1. Admin → Base de données → **Vider la référence**
2. Admin → Import référence → Scanner + Importer
   - Vérifier dans les logs Flask : les 3 `POST /api/scanner/lancer`
     doivent apparaître avec des timestamps **espacés** de quelques
     secondes (et non plus tous dans la même seconde)
   - Plus aucun 500 avec `IntegrityError`
3. Atelier **Séquence (niveau)** → ouvrir N11/S01
   - Les parties 1 et 2 doivent avoir leurs objectifs + liaisons aux
     méthodes + liaisons aux exercices
4. Relancer un second import (sans reset cette fois) : doit être
   instantané et ne rien afficher comme « nouveau »

## Vérifications effectuées

- **992 tests pytest verts** (985 précédents + 7 nouveaux)
- Les 7 nouveaux tests reproduisent précisément le scénario Laurent :
  - Un scan qui pose des liaisons v2 doit pouvoir être suivi d'un
    autre `ecrire_exercices` sans IntegrityError
  - Les liaisons v2 d'un niveau ne doivent pas disparaître quand un
    autre niveau est scanné (simule le flux N10 → N11 → N12)
  - La suppression d'un exo doit nettoyer sa liaison `objectif_exos`
    en amont (garantit qu'un exo qui disparaît ne bloque pas le DELETE)

## Notes

- Cette refonte apporte aussi un bénéfice de performance : les IDs des
  exos non modifiés sont préservés, et leurs liaisons v2 aussi. Plus
  besoin de tout recalculer à chaque scan.
- Le chemin d'écriture `UPDATE` au lieu de `DELETE+INSERT` est plus
  sûr si un scan planten en milieu de route : la base reste cohérente
  au lieu d'être vidée + partiellement remplie.
- La même logique diff-based pourrait être appliquée à `ecrire_notions`
  et `ecrire_methodes` lors d'un chantier futur, mais ce n'est pas
  urgent — leurs FK ne sont pas en RESTRICT, donc elles n'ont pas le
  crash.
