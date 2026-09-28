# redemarrage_v0_13_6_1_2.md

Document de continuité — fin de session **v0.13.6.1.2**.

## Statut

| Version | Statut |
|---|---|
| v0.13.6.1 | ✅ CRUD + UI cartes (avec liens objectifs) |
| v0.13.6.1.1 | ✅ Fix bouton « + Créer » (accès filtres niveau/séquence) |
| **v0.13.6.1.2** | 🟡 **À déployer** — Fix badge + refonte modèle (lien notion/méthode + 5 types) |
| v0.13.6.2 | À venir : production PDF des cartes + premier peuplement |
| v0.13.6.3 | À venir : intégration éval + cartes dans référentiels |
| v0.13.6.4 | À venir : UI « Livrets annuels » remplaçant 3 onglets |

## Ce qui a été fait en v0.13.6.1.2

**Diagnostic et fixs** suite au retour de Laurent après déploiement v0.13.6.1 :

1. **Bug badge "modifié"** qui ne disparaissait pas après Enregistrer :
   `_carteRemplirFormulaire` cascade vers `atelCarteTypeTechChange` →
   `atelCarteFormChange` qui remettait `MODIFIE=true`. Fix : séparation
   logique d'affichage / handler utilisateur. Même pattern appliqué au
   nouveau cadre Lien.

2. **Refonte du modèle** (décisions scoping Laurent) :
   - **Lien direct vers UNE notion OU UNE méthode** (au lieu de
     many-to-many vers objectifs). Champs `lien_type` + `lien_id` dans
     `cartes_automatisme`, table `carte_objectifs` supprimée.
   - **5 types pédagogiques unifiés** : `definition`, `propriete`,
     `reconnaissance`, `calcul`, `procedure`. Liste indépendante du
     lien (souple, à l'enseignant de juger).

**Implémentation** :
- BDD : refonte `cartes_automatisme` (CHECK élargi, ajout
  `lien_type`/`lien_id` avec CHECK cohérence, suppression
  `carte_objectifs`), migration automatique destructive dans
  `_migrer_schema_post_ddl` (détecte absence de `lien_type` → DROP +
  recréation)
- Service : ajout `LienTypeInvalide`/`LienIntrouvable`/`LienIncoherent`,
  refonte `creer_carte`/`modifier_carte`/`valider_carte` (validation
  pédagogique exige un lien), ajout `lister_notions_disponibles` et
  `lister_methodes_disponibles`, suppression fonctions objectifs
- Routes : suppression endpoints `/objectifs`, ajout
  `notions-disponibles` et `methodes-disponibles` (paramétrés par
  niveau **et** séquence pour liste courte)
- UI : refonte cadre Lien (2 radios + select dynamique), 5 options du
  select type_pedago, fix badge, mise à jour des icônes
- Tests : refonte (63 tests au lieu de 69, suppression section
  objectifs, ajout tests lien + sélecteurs)

## Tests

| | Linux (CI Claude) | Windows attendu |
|---|---|---|
| v0.13.6.1.1 baseline | 2364 + 5 skipped | 2353 + 16 skipped |
| **v0.13.6.1.2 final** | **2358 + 5 skipped** | **~2347 + 16 skipped** |

Variation : -6 tests entre v0.13.6.1 et v0.13.6.1.2 = suppression des
14 tests objectifs (TestObjectifs + TestRoutesObjectifs +
TestRoutesObjectifsDisponibles) compensée par +8 tests nouveaux (lien,
sélecteurs notions/méthodes, schéma CHECK lien).

## Fichiers livrés (7)

```
appli/persistence/schema.sql                  (refonte bloc cartes)
appli/persistence/sqlite_store.py             (+ migration v0.13.6.1.2)
appli/services/cartes_automatisme.py          (refonte complète)
appli/routes/cartes_automatisme.py            (refonte routes)
appli/static/atelier_carte_automatisme.js     (refonte complète)
appli/templates/index.html                    (refonte cadre Lien + 5 options)
appli/tests/test_v0_13_6_1_cartes_automatisme.py  (refonte tests)
```

## Décisions clés à retenir

1. **Lien unique** : une carte → une notion OU une méthode. Pas de
   multi-lien. Pour les cas transversaux : duplication manuelle.

2. **Types pédagogiques unifiés** : 5 valeurs indépendantes du lien.
   L'exemple « rotation » de Laurent peut être typé `reconnaissance`
   (figure préfabriquée) ou `procedure` (étapes), selon ce qu'il veut
   souligner — pas de contrainte croisée notion/méthode.

3. **Migration destructive en alpha** : on assume la perte des cartes
   test v0.13.6.1 vu qu'on a peu de données réelles.

4. **Sélecteur scopé à la séquence** : pour rester court et lisible. Pas
   de cross-séquence (cohérent avec l'absence d'import inter-séquence
   pour les cartes elles-mêmes).

## Pour la prochaine session (v0.13.6.2)

**Objectif** : génération PDF planche A4 (16 cartes/feuille) +
**premier peuplement** de cartes en base.

**Côté paquet** (à faire par Laurent ou à proposer) :
- Créer `seqenseigne-core-cartes.dtx` avec :
  - Macro `\seqCartePlanche{type}{id}{contenu}` (1 carte unique)
  - Environnement `seqPlancheCartes` (16 cartes en grille 4×4 avec
    miroir horizontal recto/verso pour massicotage)
  - Allocations TeX encapsulées dans macro publique

**Côté appli** :
- Module `services/render_cartes_planche.py` avec tirage déterministe
  `hash(carte_id, indice_variante)` pour les paramétrées
- Routes `/api/cartes/planche/<niveau>/<sequence>/rendu-tex` et
  `.../rendu-pdf` (similaire à routes éval)
- UI : activer le bouton « Compiler le rendu » (désactivé en v0.13.6.1)
- Enrichir `WRAPPER_PAR_TYPE['carte_automatisme']` avec les macros du
  paquet
- Premier peuplement : créer une commande CLI ou un script de bootstrap
  pour générer des cartes d'exemple, en accord avec Laurent sur le
  contenu pédagogique

**Mémo paramétrée** : 1 carte paramétrée = 16 variantes uniques sur 1
feuille A4 (multipliable via préférence `cartes_param_nb_uniques`).
Carte fixe = 16 exemplaires identiques sur 1 feuille A4.

## Roadmap globale (rappel Laurent)

- **v0.13.6.2** : production PDF + premier peuplement
- **v0.13.6.3** : intégration éval (niveau) + cartes (séquence) dans
  référentiels
- **v0.13.6.4** : refonte UI « Livrets annuels » (regroupe Récap cours
  + Récap exos + Plans de travail dans un seul onglet)
- **Au-delà** :
  - Finalisation référentiels : gestion complète du cycle de vie,
    production centralisée des documents
  - **Services applicatifs communs** sur lesquels s'appuieront les
    services métiers : persistence en base, compilation LaTeX, etc.
    (point intéressant : commence à se sentir au fur et à mesure
    qu'on a 6+ ateliers similaires — il y aura matière à factoriser
    les invariants)
