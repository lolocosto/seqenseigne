# Redémarrage v0.14.5 — Audit v1/v2 des objectifs (lecture seule)

## Position dans le chantier de suppression v1

Le workstream « suppression de la table `objectifs` v1 » se découpe en
3 livraisons :

| | Statut |
|---|---|
| **v0.14.5** : Audit lecture seule (cette livraison) | ⏳ |
| **v0.14.6** : Réécriture services + suppression effective | À venir |
| **v0.14.7** : Renommage cosmétique `objectifs_v2` → `objectifs` | À venir |

Cette livraison ne **modifie rien** côté code applicatif : elle ajoute
juste un script d'audit qui permet de vérifier sur ta vraie BDD que la
suppression de v1 peut se faire sans perte de données.

## Cadrage validé

| Question | Réponse |
|---|---|
| Q1 — Commencer par l'audit ? | (a) Oui, audit lecture seule d'abord |
| Q2 — Découpage | (b) 3 livraisons : audit / réécriture+suppression / renommage |
| Q3 — Périmètre élargi en v0.14.6 | (a) Oui : aussi `exercice_objectifs`, `services/edition_progression.py`, route `/api/objectifs`, JS `ATL_OBJ_CAT` |
| Q4 — Renommer `objectifs_v2` → `objectifs` après ? | (a) Oui en v0.14.7 |

## Ce que fait le script

Le nouveau script `scripts/audit_v1_v2.py` :

1. **Ouvre la base en mode read-only** (URI SQLite `file:...?mode=ro`)
   — impossible de modifier quoi que ce soit même par accident
2. Vérifie l'existence des 4 tables concernées (`objectifs`,
   `objectifs_v2`, `exercice_objectifs`, `objectif_exos`)
3. Compte les enregistrements de chacune
4. Pour chaque objectif v1, cherche son pendant v2 par la clé
   `(niveau, sequence, code)` — reconstituée en v2 via
   `objectifs_v2 ⨝ sequence_parties ⨝ sequences_par_niveau`
5. Détecte les divergences sur chaque champ commun (`methode_id`,
   `nom`, `critere_F/A/E`)
6. Détecte les champs v1 sans pendant v2 :
   - `est_nouveau` (booléen utilisé par `seqObjectifGetFinCycle`)
   - `obj_precedent_id` (chaîne de prérequis)
7. Compare les liaisons `exercice_objectifs` (v1) vs `objectif_exos`
   (v2) : pour chaque liaison v1, vérifie qu'une liaison équivalente
   existe en v2
8. Émet un verdict final avec un **code de sortie** parlant :
   - `0` : base prête pour suppression, aucun obstacle détecté
   - `1` : divergences/orphelins détectés, intervention requise
   - `2` : base introuvable
   - `3` : erreur SQL pendant l'audit

## Usage

```
cd appli
python -m scripts.audit_v1_v2
```

Par défaut, le script cherche la base à `appli/data/seqenseigne.db`.
Tu peux spécifier un autre chemin :

```
python -m scripts.audit_v1_v2 --db /chemin/vers/ma-base.db
```

Et pour avoir le détail complet (sans troncature à 30 entrées par
catégorie) :

```
python -m scripts.audit_v1_v2 --verbose
```

## Exemple de sortie

Pour une base sans problème :

```
Audit v1/v2 — base : data/seqenseigne.db

──────────────────────────────────────────────────────────────────────
  Tables présentes
──────────────────────────────────────────────────────────────────────
  ✓ objectifs
  ✓ objectifs_v2
  ✓ exercice_objectifs
  ✓ objectif_exos

──────────────────────────────────────────────────────────────────────
  Comptes globaux
──────────────────────────────────────────────────────────────────────
  objectifs (v1)       :   xxx
  objectifs_v2 (v2)    :   xxx
  ...

──────────────────────────────────────────────────────────────────────
  VERDICT
──────────────────────────────────────────────────────────────────────
  ✓ Aucun obstacle détecté. La suppression de v1 peut se faire sans
    perte de données.
  ✓ Tu peux enchaîner sur v0.14.6 (réécriture services + DROP TABLE).
```

Pour une base avec problèmes (exemple, base de test du script) :

```
──────────────────────────────────────────────────────────────────────
  VERDICT
──────────────────────────────────────────────────────────────────────
  ⚠ 4 catégorie(s) de problème détectée(s) :
    - 1 objectif(s) v1 sans pendant v2
    - 1 statut(s) est_nouveau non migré(s)
    - 1 divergence(s) de contenu (champ par champ)
    - 1 liaison(s) exercice→objectif non migrée(s)

  ➡ Recommandation : ré-exécuter scanner_vers_v2.py pour synchroniser,
    ou décider en v0.14.6 quels champs doivent être ajoutés à v2.
    Relance ce script avec --verbose pour le détail exhaustif.
```

## Quoi faire après l'audit

### Cas 1 : Verdict ✓ (exit 0)

C'est le scénario idéal. Tu peux directement enchaîner sur v0.14.6
(qui supprimera physiquement la v1).

### Cas 2 : Verdict ⚠ (exit 1)

Selon les catégories de problèmes détectés :

- **Orphelins v1** : objectifs en v1 sans pendant v2. Plusieurs options :
  - Relancer `services/scanner_vers_v2.py` pour faire la migration
    automatique
  - Décider que ces objectifs sont obsolètes et les abandonner
  - En v0.14.6, ajouter un mode « migration en force » qui crée les
    objectifs v2 manquants à partir de v1

- **`est_nouveau` perdu** : la v2 n'a pas cette colonne. Décisions
  possibles en v0.14.6 :
  - Ajouter `est_nouveau INTEGER DEFAULT 0` à `objectifs_v2`
  - Stocker autrement (par exemple via un attribut de la méthode)
  - Abandonner (si l'usage est purement historique)

- **`obj_precedent_id` perdu** : chaîne de prérequis. La logique est
  déjà gérée ailleurs (CSV de prérequis dans `livret_sequence.py`),
  donc ce champ est probablement redondant. À confirmer en v0.14.6.

- **Divergences `methode_id`/`nom`/`critere_*`** : v1 et v2 contiennent
  des valeurs différentes pour le même objectif. La source de vérité
  doit être tranchée : généralement c'est v2 qui est plus à jour
  (puisqu'alimentée par les ateliers récents), mais à vérifier au cas
  par cas avant la suppression.

- **Liaisons perdues** : `exercice_objectifs` (v1) contient des liens
  exercice→objectif qui n'existent pas dans `objectif_exos` (v2). À
  migrer en v0.14.6 (script de copie des liens).

## Fichiers livrés

```
NOUVEAUX
  appli/scripts/audit_v1_v2.py                      (~600 lignes)
  appli/tests/test_v0_14_5_audit_v1_v2.py           (21 tests)
  appli/doc/redemarrage_v0_14_5.md                  (ce document)
```

## Vérifs

- `ast.parse` sur le script : OK
- 21 tests pytest dédiés au script :
  - Présence et syntaxe valide
  - Code retour correct pour 8 scénarios (base concordante, orphelin v1,
    divergence methode, est_nouveau, liaison perdue, base sans v1,
    base sans v2, base inexistante)
  - Contenu du rapport (verdicts, mentions, listings)
  - Lecture seule garantie (snapshots avant/après identiques sur 2 bases)
  - Vérification structurelle de l'URI `file:...?mode=ro`
  - Arguments `--db`, `--verbose`, `--help`
- Suite complète : **3517 passed, 5 skipped, 0 failed**
  (3496 baseline v0.14.4 + 21 nouveaux v0.14.5)

## À tester chez toi

### 1. Sanity du script

```
cd appli
python -m pytest tests/test_v0_14_5_audit_v1_v2.py -v
```

Attendu : 21 passed.

### 2. Exécuter l'audit sur ta vraie base

```
cd appli
python -m scripts.audit_v1_v2
```

Et **m'envoyer la sortie complète** (copier-coller du terminal). Sur
cette base, je pourrai cadrer précisément v0.14.6 :
- Si verdict ✓ → v0.14.6 sera plus simple (juste réécriture services
  + DROP TABLE)
- Si verdict ⚠ → on intègre dans v0.14.6 un script de migration
  complémentaire (ou un script qui appelle `scanner_vers_v2.py` puis
  refait l'audit), et on décide ensemble si on garde `est_nouveau` et
  `obj_precedent_id` en v2

### 3. Si tu veux explorer les détails

```
python -m scripts.audit_v1_v2 --verbose
```

Affiche TOUS les orphelins/divergences (au lieu de tronquer à 30/15).

## Prochaine étape : v0.14.6

Une fois ton retour reçu, je cadrerai v0.14.6 avec :
- Le script de réécriture pour `services/edition_progression.py` (ou
  sa suppression complète si la fonctionnalité est obsolète)
- La réécriture de `seqObjectifGetNom` / `seqObjectifGetFinCycle` dans
  `services/latex_rendu_atome.py`
- Les éventuelles décisions sur `est_nouveau` et `obj_precedent_id`
- Le script de migration des liaisons `exercice_objectifs` →
  `objectif_exos` si nécessaire
- Les `DROP TABLE objectifs` et `DROP TABLE exercice_objectifs`
- La suppression de la route `/api/objectifs` et du JS `ATL_OBJ_CAT`
- La suppression des scripts de peuplement v1 (03/04/05/06/15) et de
  `services/scanner_vers_v2.py` devenus inutiles
- Adaptation/suppression des tests qui simulaient la v1
