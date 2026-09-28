# seqenseigne v0.5.3 — Livraison

Cumul de v0.5.2 (sous-onglets + IDs élèves UUID + anti-doublon) plus :

## Nouveautés v0.5.3

### Import en lot d'une arborescence de suivi
Nouveau script `appli/importer_arborescence.py` qui scanne un répertoire
racine organisé par année / établissement / classe et importe toutes les
classes détectées en base.

Arborescence attendue :
```
<racine>/
  <annee>/                      ex: 2024-2025
    <etablissement>/            ex: Collège Les Hautes Ourmes
      <classe>/                 ex: 5e2
        Suivi_eleves/           (obligatoire)
          liste_eleves.csv
          S01suivi.csv … S14suivi.csv
          Sem1-sequences.csv, Sem2-sequences.csv, FinAnnee-sequences.csv
        SequencesDB/            (obligatoire)
          N10S01Objectifs.csv …
          N10S01Connaissances.csv …
        autres fichiers/dossiers ignorés
```

Un sous-dossier de `<etablissement>/` est reconnu comme classe SI
et seulement si il contient à la fois `Suivi_eleves/` ET `SequencesDB/`.
Les dossiers parasites (Club Espace, Découverte des métiers, Blason…)
sont automatiquement ignorés.

Le niveau (N09/N10/N11/N12) est déduit des fichiers `N1XS*Objectifs.csv`
du dossier `SequencesDB` — plus fiable que de deviner depuis le nom.

### Utilisation
```
cd F:\Enseignement\seqenseigne\appli

# Inspection préalable (aucune modification)
..\outils\python\python.exe importer_arborescence.py --racine F:\Suivi --dry-run

# Import réel (les classes déjà en base sont ignorées)
..\outils\python\python.exe importer_arborescence.py --racine F:\Suivi

# Forcer : supprime les classes existantes avant de les réimporter
..\outils\python\python.exe importer_arborescence.py --racine F:\Suivi --force

# Limiter à une année précise
..\outils\python\python.exe importer_arborescence.py --racine F:\Suivi --annee 2024-2025
```

### Corrections en passant

- **Bug préexistant dans `lire_suivi_historique`** : `row.get(col, "").strip()`
  plantait avec `AttributeError` sur les CSV contenant des valeurs `None`
  (lignes plus courtes que l'en-tête). Corrigé avec `(row.get(col) or "").strip()`.
- **Bug de `supprimer_donnees_classe` en mode SQLite** : les élèves orphelins
  (plus rattachés à aucune classe) n'étaient pas supprimés de la table globale
  `eleves`. Les lignes de `suivi` et `niveaux` n'étaient pas non plus nettoyées.
  Corrigé.

## Fichiers livrés

```
appli/templates/index.html
appli/routes/progression.py
appli/services/classes.py
appli/importers/sequencesdb.py
appli/persistence/sqlite_store.py        ← nouveau dans cette livraison
appli/tests/test_services.py
appli/tests/test_routes.py
appli/tests/test_progression.py
appli/tests/test_sqlite_store.py         ← nouveau (+ 2 tests orphelins)
appli/importer_arborescence.py           ← nouveau script CLI
```

## Tests

**295 tests verts** (293 précédents + 2 nouveaux pour le nettoyage d'orphelins).

```
cd F:\Enseignement\seqenseigne\appli
..\outils\python\python.exe -m pytest tests\ -q
```

## Procédure de déploiement

1. Dézipper cette archive à la racine de `F:\Enseignement\seqenseigne\` :
   les fichiers s'installent aux bons emplacements (y compris le nouveau
   fichier `persistence/sqlite_store.py`).
2. Vider les données de suivi si la base contient les 3 classes contaminées
   (de la session précédente) :
   - Via l'UI : Administration → reset suivi ;
   - OU supprimer `data/seqenseigne.db` et relancer l'appli.
3. Placer tes dossiers d'années sous une racine de ton choix (ex. `F:\Suivi\`)
   avec la structure `<racine>/<annee>/<établissement>/<classe>/`.
4. Inspecter avec `--dry-run`, puis importer.
