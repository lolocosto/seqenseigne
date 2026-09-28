# redemarrage_v0_13_6_1_3.md

Document de continuité — fin de session **v0.13.6.1.3**.

## Statut

| Version | Statut |
|---|---|
| v0.13.6.1.2 | ✅ Refonte modèle (lien notion/méthode + 5 types + fix badge) |
| v0.13.6.1.2.1 | ✅ Fix crash démarrage (index dans migration au lieu de schema.sql) |
| **v0.13.6.1.3** | 🟡 **À déployer** — Préfixes unifiés N/M/CA + refonte sidebar cartes |
| v0.13.6.2 | À venir : production PDF + premier peuplement |
| v0.13.6.3 | À venir : intégration éval + cartes dans référentiels |
| v0.13.6.4 | À venir : UI Livrets annuels |

## Ce qui a été fait en v0.13.6.1.3

**Diagnostic préalable** :
- Vérification que les codes `C01`/`O02` ne sont stockés nulle part en
  BDD (uniquement formatés à l'affichage dans 2 lignes de `app.js`)
- Vérification que le LaTeX stocké ne contient pas ces codes
- Vérification que les noms de fichiers `.tex` n'utilisent pas ces codes
- Conclusion : **pas de migration BDD requise**, changement purement
  cosmétique

**Implémentation** :

1. **Préfixes unifiés** :
   - `app.js` ligne 2863 : `'C' + num_connaissance` → `'N' + num_connaissance`
     (atelier Notion)
   - `app.js` ligne 3216 : `'O' + num_objectif` → `'M' + num_methode`
     (atelier Méthode — **changement de source** : on passe du numéro
     d'objectif rattaché au numéro propre de la méthode)

2. **Sidebar cartes refondue** :
   - Remplacement du HTML custom par appel à `atelAsmItemHtml` (helper
     standard, cohérent avec Notion/Méthode/Exercice/Fiche)
   - Format ID : `N11/S01/CA03` (CA = carte d'automatisme, distinct du
     C de connaissance/notion désormais)
   - Helper `_carteLabelLien` qui renvoie `'n 03'` ou `'m 02'` selon le
     lien, alimentant `placedTags` du helper standard
   - Badge `P` à gauche pour les cartes paramétrées

3. **Réordonnancement formulaire** (cadres dans `index.html`) :
   Identification → **Lien** → **Variables** → Recto → Verso

## Décisions de scoping

| Question | Réponse Laurent |
|---|---|
| M = num_methode ou num_objectif ? | `num_methode` (séquentiel propre 1, 2, 3) |
| Une livraison ou deux ? | Tout dans v0.13.6.1.3 |

**Note importante sur les méthodes** : on **renumérote** dans l'affichage.
Avant `O02` (= méthode liée à l'objectif 02). Après `M01` (= première
méthode de la séquence). Le lien à l'objectif reste en BDD via
`methodes.num_objectif`, juste plus visible dans le préfixe
d'identification. Cohérent avec `services/referentiels.py` qui utilisait
déjà cette convention.

## Tests

| | Linux (CI Claude) | Windows attendu |
|---|---|---|
| v0.13.6.1.2.1 baseline | 2358 + 5 skipped | ~2347 + 16 skipped |
| **v0.13.6.1.3 final** | **2358 + 5 skipped** | **~2347 + 16 skipped** |

Aucun test métier impacté (changements d'affichage purs côté JS/HTML).

## Fichiers livrés (3)

```
appli/static/app.js                       (2 lignes modifiées)
appli/static/atelier_carte_automatisme.js (refonte sidebar avec helper)
appli/templates/index.html                (réordonnancement cadres)
```

## Pour la prochaine session (v0.13.6.2)

**Objectif principal** : génération PDF planche A4 (16 cartes / feuille).

**Côté paquet** (à demander à Laurent) :
- Créer `seqenseigne-core-cartes.dtx` avec :
  - Macro `\seqCartePlanche{type}{id}{contenu}` (1 carte unique)
  - Environnement `seqPlancheCartes` (16 cartes en grille 4×4, miroir
    horizontal recto/verso pour le massicotage)
  - Allocations TeX encapsulées dans une macro publique (pattern
    `\seqInitCorrigesEval`)

**Côté appli** :
- Module `services/render_cartes_planche.py` :
  - 16 exemplaires identiques pour les cartes fixes
  - 16 (ou multiple) variantes uniques pour les paramétrées, avec
    tirage déterministe `hash(carte_id, indice_variante)` pour la
    reproductibilité
- Routes `/api/cartes/planche/<niveau>/<sequence>/rendu-tex` et
  `.../rendu-pdf`
- UI : activer le bouton « Compiler le rendu » (désactivé en v0.13.6.1)
- Enrichir `WRAPPER_PAR_TYPE['carte_automatisme']` avec les macros du
  paquet (vide aujourd'hui en v0.13.6.1)
- **Premier peuplement** : créer en accord avec Laurent quelques cartes
  d'exemple (en accord sur le contenu pédagogique)

**Mémo planche A4** :
- 1 carte = 1 feuille A4 = 16 exemplaires (identiques si fixe,
  distincts si paramétrée)
- Préférence `cartes_param_nb_uniques` (multiple de 16, défaut 16)
  pour produire 1+ feuilles de variantes par carte paramétrée

## Notes pour l'agent

Pour les sessions à venir, deux chantiers d'infra méritent d'être
remontés à un moment opportun :

1. **Tests JS automatisés** (Vitest ou Jest) : aurait détecté le bug
   `_carteNiveau`/`_carteSequence` en v0.13.6.1.1
2. **Tests d'intégration de migration** : prend la BDD d'une version
   N-1 et vérifie que `SqliteStore` v_N migre proprement. Aurait
   détecté le bug d'index v0.13.6.1.2.1

Ces deux chantiers sont déjà notés dans la roadmap longue de Laurent.
Pas urgents mais à proposer dès qu'on aura une session « infra ».
