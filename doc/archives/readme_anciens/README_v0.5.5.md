# seqenseigne v0.5.5 — Livraison

Patch incrémental sur v0.5.4 : affichage détaillé des avertissements lors
de l'import en lot.

## Nouveautés v0.5.5

### Affichage des avertissements par classe

Jusqu'à présent, le script `importer_arborescence.py` se contentait de
compter les avertissements (« · 3 avert. ») sans en révéler le contenu,
ce qui rendait le diagnostic pénible quand une classe n'importait aucun
créneau.

Maintenant :
- Les avertissements sont **affichés automatiquement** pour toute classe
  qui termine avec 0 créneaux (cas où le problème mérite une inspection).
- Le nouveau flag `-v` / `--verbose` affiche le détail pour **toutes**
  les classes, même celles qui ont correctement importé leurs créneaux.

Exemple de sortie quand une classe 2022-2023 n'a pas les
`T*-sequences.csv` attendus :
```
  ✓ 2022-2023 / Collège Les Hautes Ourmes / 3E3 — 24 élèves · 0 créneaux · 3 avert.
      ⚠ Périodes.CSV cite 'T1' mais T1-sequences.csv introuvable
      ⚠ Périodes.CSV cite 'T2' mais T2-sequences.csv introuvable
      ⚠ Périodes.CSV cite 'T3' mais T3-sequences.csv introuvable
```

### Les avertissements sont aussi enregistrés dans le rapport

Le dict retourné par `importer_toutes` contient maintenant, pour chaque
classe importée, une clé `avertissements: list[str]` avec le détail.
Utile si ce script est réutilisé comme bibliothèque.

## Fichier modifié par rapport à v0.5.4

```
appli/importer_arborescence.py
```

## Tests

**295 tests verts**, aucune régression.

## Déploiement

1. Dézipper l'archive à la racine de `D:\Enseignement\seqenseigne\`
   (écrase les fichiers v0.5.4 ; seul `importer_arborescence.py` change
   réellement depuis v0.5.4).
2. Relancer l'import sans `--force` (ou avec, peu importe) pour voir
   ce qui cloche sur les 6 classes à 0 créneaux. Le détail s'affichera
   automatiquement.

Exemple :
```
python importer_arborescence.py --racine D:\Enseignement_old
```

Et pour voir toutes les warnings, même sur les classes OK :
```
python importer_arborescence.py --racine D:\Enseignement_old --verbose
```
