# seqenseigne v0.5.4 — Livraison

Patch incrémental sur v0.5.3 : support des années organisées en trimestres
(T1/T2/T3) et découverte dynamique des périodes depuis `Periodes.CSV`.

## Nouveautés v0.5.4

### Découverte dynamique des périodes depuis Periodes.CSV

Avant : `lire_sequencesdb` supposait que les périodes étaient toujours
`Sem1`, `Sem2`, `FinAnnee` (codées en dur).

Maintenant : le fichier `Periodes.CSV` présent dans `Suivi_eleves/` est lu
en premier pour découvrir la liste des périodes réellement utilisées cette
année-là. Pour chaque période trouvée, le fichier `{Periode}-sequences.csv`
correspondant est chargé.

Résultat :
- Années 2021-2022 / 2022-2023 (trimestres `T1/T2/T3`) : créneaux correctement
  importés. Auparavant : 0 créneaux.
- Années 2023-2024+ (semestres `Sem1/Sem2/FinAnnee`) : non-régression.
- Fallback : si aucun `Periodes.CSV` n'est trouvé, retombe sur
  `Sem1/Sem2/FinAnnee` (rétrocompatibilité).

La casse du nom de fichier est tolérante : `Periodes.CSV`, `periodes.csv`,
`PERIODES.CSV` sont tous reconnus, même sur Linux (case-sensitive).

### Format de suivi trimestriel

Les fichiers `T1bilan.csv` (bilan trimestriel global par séquence) sont
**ignorés** : seuls les `SXXsuivi.csv` par séquence × objectif sont lus.
Si une année ancienne n'en a pas, le suivi sera vide (mais les créneaux
restent importés correctement).

Les `SXXsuivi.csv` sans colonne `Numero` (format 2021-2022) sont déjà pris
en charge : le mapping élève se fait sur `(Nom, Prenom)`.

## Fichier modifié par rapport à v0.5.3

```
appli/importers/sequencesdb.py
```

Tous les autres fichiers v0.5.3 sont conservés tels quels dans l'archive
pour faciliter le déploiement (un seul zip à dézipper).

## Tests

**295 tests verts**, aucune régression.

```
cd F:\Enseignement\seqenseigne\appli
..\outils\python\python.exe -m pytest tests\ -q
```

## Déploiement

1. Dézipper l'archive à la racine de `F:\Enseignement\seqenseigne\`
   (écrase les fichiers v0.5.3 ; si vous êtes déjà en v0.5.3, seul
   `sequencesdb.py` change réellement).
2. Si des classes 2021-2022 / 2022-2023 avaient été importées en v0.5.3
   avec `0 créneaux`, les supprimer puis relancer l'import :
   ```
   python importer_arborescence.py --racine F:\Suivi --force
   ```
3. Vérifier que les classes 2021-2022 et 2022-2023 ont maintenant des créneaux.
