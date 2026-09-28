# Redémarrage seqenseigne — v0.12.4 (chantier 5/5 série v0.12)

## Synthèse

**Migration ponctuelle méthodes ↔ objectifs.** Script CLI qui peuple
`objectifs_v2.methode_id` quand le titre d'une méthode coïncide
exactement (après TRIM) avec le nom d'un objectif des mêmes niveau et
séquence.

C'est le dernier chantier de la série v0.12. Une fois cette migration
exécutée, le lien méthode↔objectif passera de la dénormalisation par
égalité de chaînes (jointure artificielle dans plusieurs services)
à une vraie FK, ce qui permettra à terme d'allègir le code.

## Ce qui change

### Nouveau script

`scripts/migrer_methodes_objectifs.py` — outil CLI calqué sur
`purger_fiches.py` :
- Dry-run par défaut (analyse sans modification)
- `--apply` pour exécuter, `--yes` pour skip la confirmation interactive
- `--niveau` / `--sequence` pour filtrer (combinables)
- `-v` / `--verbose` pour afficher le détail des correspondances

### Stratégie de matching

Stricte : `TRIM(methodes.titre) == TRIM(objectifs_v2.nom)`, restreint
au même couple `(niveau, sequence_code)`.

Pour chaque objectif, le script calcule l'une des 6 catégories :

| Catégorie | Condition | Action |
|---|---|---|
| **À lier** | `methode_id IS NULL` + 1 méthode candidate trouvée | UPDATE en apply |
| **Déjà OK** | `methode_id` non NULL = ce que l'auto donnerait | Préservé |
| **Conflit** | `methode_id` non NULL ≠ ce que l'auto donnerait | Préservé, signalé |
| **Ambigu** | 2+ méthodes ont le même titre dans la séquence | Pas lié, signalé |
| **Sans match** | Aucune méthode candidate (ou objectif sans nom) | Pas lié, signalé |
| **Cours ignorés** | Objectif Cours (code finissant par '1' avec convention) | Toujours ignoré |

L'identification du Cours utilise la convention métier :
`code == f"{numero_partie - 1}1"` (donc 01 en partie 1, 11 en partie 2,
21 en partie 3, etc.).

### Résultat attendu sur la BDD de prod

Sur la BDD actuelle (243 objectifs, 156 méthodes) :

```
À lier (methode_id NULL → posé) :  182
Déjà liés correctement          :    0
Conflits (methode_id ≠ attendu) :    0
Ambigus (titre dupliqué)        :    0
Sans match (méthode absente)    :    6
Cours ignorés (code 0X1)        :   55
```

Total cohérent : 182 + 0 + 0 + 0 + 6 + 55 = 243 ✓

Les 6 « sans match » sont des cas légitimes :
- N10/S01/05 « Repérer et placer un nombre décimal sur une droite graduée »
  (titre voisin mais pas identique à la méthode existante)
- N10/S10 « Convertir entre unités de longueurs, entre unités d'aires,
  et entre unités de volumes » (méthode existe avec suffixe différent)
- 4 objectifs « Modéliser… » / « Démontrer… » qui n'ont pas de
  méthode dédiée (cas légitime : ces objectifs mobilisent plusieurs
  méthodes)

Ces cas restent avec `methode_id = NULL` après migration et pourront
être traités à la main via l'atelier d'assemblage si besoin.

### Sécurités

- **Dry-run par défaut** : aucune modification sans `--apply`
- **Confirmation interactive** : `--apply` sans `--yes` demande de taper
  exactement `OUI`
- **Préservation des liens existants** : un `methode_id` non NULL
  n'est jamais écrasé, même si le matching auto donnerait une autre
  méthode (signalé en `conflit`)
- **Refus de l'ambiguïté** : si plusieurs méthodes partagent le même
  titre dans une séquence (cas non observé en prod mais
  théoriquement possible), aucun lien n'est posé pour les objectifs
  concernés
- **Idempotence** : rejouer après un apply réussi retourne 0 à lier
- **Foreign keys activées** : `PRAGMA foreign_keys = ON` à l'ouverture
  de la connexion (la FK `methode_id → methodes(id)` est vérifiée
  par SQLite à l'UPDATE)
- **Transaction atomique** : tous les UPDATE passent dans une seule
  transaction ; en cas d'erreur SQL, rollback intégral

### Codes de sortie

- `0` : opération réussie (dry-run ou apply confirmé)
- `1` : apply annulé (réponse ≠ OUI ou EOF)
- `2` : base introuvable
- `3` : erreur SQL pendant l'exécution

## Tests

**Total : 1931 tests** (vs 1907 baseline v0.12.3.1) → **+24 tests v0.12.4**.

Nouveau fichier `tests/test_migrer_methodes_objectifs.py`, 24 tests
organisés en 6 sections :

1. **TestDryRun** (4 tests) : compteurs globaux, idempotence dry-run,
   message d'orientation, mode verbose.
2. **TestFiltres** (4 tests) : niveau seul, niveau autre, combiné,
   filtre sans match.
3. **TestApply** (6 tests) : pose des liens, préservation des conflits,
   préservation des ambigus, préservation des Cours, préservation des
   déjà liés, apply filtré.
4. **TestIdempotence** (2 tests) : re-apply identique, dry-run après
   apply.
5. **TestSecurites** (5 tests) : confirmation OUI requise, refus
   minuscule, refus explicite, refus EOF, BDD introuvable.
6. **TestRobustesse** (3 tests) : TRIM appliqué, objectif sans nom,
   apply sans rien à faire.

Pattern aligné sur `test_purger_fiches.py` (subprocess, BDD temporaire
in-tmp_path, helpers `_compter_lies` / `_methode_de`).

## Fichiers touchés

```
scripts/migrer_methodes_objectifs.py     (NOUVEAU — ~360 lignes)
tests/test_migrer_methodes_objectifs.py  (NOUVEAU — ~330 lignes, 24 tests)
doc/redemarrage_v0_12_4.md               (NOUVEAU)
```

Aucune modification du code applicatif (services, routes, frontend).
Aucune migration de schéma (la colonne `methode_id` existait déjà).

## Procédure de déploiement

### Côté serveur de l'application

1. Décompresser le ZIP par-dessus la v0.12.3.1 actuellement déployée.
2. Pas besoin de relancer l'application — c'est juste un script CLI.

### Exécution de la migration (manuelle, à ton rythme)

D'abord en dry-run, pour voir ce qui se passera :

```bash
cd appli/
python -m scripts.migrer_methodes_objectifs --verbose
```

Vérifier :
- les compteurs correspondent à l'attendu (182 à lier sur ta BDD)
- pas de conflit ni d'ambigu inattendu
- les 6 « sans match » sont bien les cas légitimes

Puis, quand prêt :

```bash
python -m scripts.migrer_methodes_objectifs --apply
```

Le script affiche l'aperçu, puis demande `OUI` pour confirmer.

### Filtrer pour une migration progressive (optionnel)

Si tu préfères y aller niveau par niveau pour vérifier en chemin :

```bash
python -m scripts.migrer_methodes_objectifs --apply --niveau N10
# vérifier dans l'app que les liens sont posés
python -m scripts.migrer_methodes_objectifs --apply --niveau N11
python -m scripts.migrer_methodes_objectifs --apply --niveau N12
```

L'idempotence garantit qu'un apply global après ces apply niveau ne
fait rien de plus.

## Effet utilisateur

Côté UI, la migration n'a **aucun effet visible immédiat** : la
plupart des écrans utilisaient déjà le matching par titre comme fallback.
Mais à partir du moment où `methode_id` est posé :

- L'atelier d'assemblage affiche correctement la méthode liée à un
  objectif dès l'ouverture (le bandeau d'objectif fermé indique
  « N exo(s) · méthode : X »)
- Les services pourront progressivement remplacer leurs jointures par
  titre par de vraies jointures FK (refactoring à venir, hors v0.12.4)

## Points de validation côté Laurent

Avant `--apply` :
- Lancer le dry-run global et vérifier que les chiffres correspondent à
  ceux annoncés (182 / 0 / 0 / 0 / 6 / 55)
- Lancer en `--verbose` et lire la liste des "À lier" pour repérer un
  éventuel match suspect (ne devrait pas arriver vu l'égalité stricte)

Après `--apply` :
- Ouvrir l'atelier d'assemblage sur quelques séquences
  (ex. N10/S01, N11/S03)
- Vérifier que les bandeaux d'objectifs fermés affichent bien le nom
  de la méthode liée (« méthode : Pour les nombres décimaux… »)
- Vérifier qu'aucun lien faux ne s'est glissé (les conflits étaient
  à 0 avant migration, donc 0 risque)

## Fin de la série v0.12

Avec cette livraison, la série v0.12 est complète :

- ✅ v0.12.0   : Plan de travail générique — données et saisie
- ✅ v0.12.1   : Génération du livret annuel des plans de travail
- ✅ v0.12.1.x : Patches (cycle 3 affiché, scope séquence, etc.)
- ✅ v0.12.2   : Harmonisation visuelle des sidebars
- ✅ v0.12.3.0 : Port des fonctions essentielles d'editv2 dans l'assemblage
- ✅ v0.12.3.1 : Suppression effective d'editv2
- ✅ v0.12.4   : Migration ponctuelle méthodes↔objectifs (cette livraison)

## Prochaine étape

**Série v0.13** — Création d'un référentiel de niveau. Au programme :
- Fin de la dette `_NOM_COURT_NIVEAU` hardcodé (remplacement par lecture
  BDD)
- Activation des tables `referentiel_*` (jusqu'ici archives historiques
  read-only)
- Refonte du `_CYCLE_PAR_NIVEAU` (introduit en v0.12.1.2) pour qu'il
  lise depuis la BDD
- Jeter les bases de l'internationalisation des niveaux (N09–N12
  hardcodés → lus depuis BDD, ouvre la voie à N13-GT, N13-ASSP,
  lycée, primaire, etc.)

C'est plus structurel que la v0.12, on en reparle quand tu seras prêt.
