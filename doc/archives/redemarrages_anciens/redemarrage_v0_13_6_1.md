# redemarrage_v0_13_6_1.md

Document de continuité — fin de session **v0.13.6.1**.

## Statut

| Version | Statut |
|---|---|
| v0.13.5.* | ✅ Atelier Évaluation complet (CRUD + UI + génération PDF) |
| **v0.13.6.1** | 🟡 **À déployer** — Atelier Cartes d'automatisme : CRUD + UI (1ère brique) |
| v0.13.6.2 | À venir : génération planche A4 (avec paquet `core-cartes.dtx`) |
| v0.13.6.3 | À venir : livret d'automatismes + badges |
| v0.13.6.4 | À venir : saisie résultats éval orale (suivi de classe) |

## Ce qui a été fait en v0.13.6.1

**Scoping complet** en début de session : 4 vagues de questions (pédagogique,
forme, BDD, sortie/UI), donnant lieu au document
`spec_cartes_automatisme_v0_13_6.md`. Décisions structurantes :
- Cartes attachées à une séquence d'un niveau (pas d'import inter-séquence)
- 2 types : fixe (identique pour tous) et paramétrée (16 variantes via xint)
- Sortie planche A4 = 16 exemplaires d'une carte sur une feuille
- Préférence `cartes_param_nb_uniques` (multiple de 16, défaut 16) pour
  les paramétrées
- Référentiel **générique**, pas personnalisé élève (les élèves écrivent
  leur nom à la main)
- TikZ inline dans recto/verso (pas de table image)
- Module hôte LaTeX : `seqenseigne-core-cartes.dtx` (v0.13.6.2)

**Implémentation côté backend** :
- Schéma BDD : 3 tables avec CHECK constraints et FK CASCADE/RESTRICT
- Service métier `services/cartes_automatisme.py` (~700 lignes) :
  - 15 classes d'exception avec `code` stable et `details`
  - CRUD : `creer_carte`, `lire_carte`, `lister_cartes`,
    `modifier_carte`, `supprimer_carte`
  - Objectifs : `lister_objectifs_carte`, `ajouter_objectif_a_carte`,
    `retirer_objectif_de_carte`
  - Workflow : `valider_carte` (avec validation pédagogique : recto/verso
    non vides + ≥1 objectif + variables non vides si paramétrée),
    `devalider_carte`
  - Config : `lire_config` (avec défaut), `modifier_config` (avec
    validation par clé)
- Routes REST `routes/cartes_automatisme.py` (~330 lignes) :
  - 12 endpoints CRUD + objectifs + workflow + config + sélecteur UI
  - Mapping `code → HTTP` aligné sur `routes/evaluations.py`
- Blueprint enregistré dans `app.py`

**Implémentation côté UI** :
- Nouveau bouton de nav « Carte d'automatisme » dans la portée séquence
- Panneau atelier complet dans `templates/index.html` (~200 lignes) :
  sidebar avec filtre état, toolbar, sous-onglets Édition/Rendu PDF,
  formulaire 4 cadres (Identification, Recto, Verso, Variables, Objectifs)
- Module JS `static/atelier_carte_automatisme.js` (~611 lignes) :
  - Pattern aligné sur `atelier_evaluation.js`
  - Variables globales `ATL_CARTE_*`, fonctions privées `_carteXxx`,
    publiques `atelCarteXxx`
  - Hook d'init via `ATL_INITS['carte_automatisme'] = 'atelCarteCharger'`
- Mapping libellé dans `atelier_commun.js` (`atelierAfficherLatex`)
- Enregistrement dans `ATL_PORTEES.sequence.ateliers` dans `app.js`

**Tests** (`tests/test_v0_13_6_1_cartes_automatisme.py`, ~750 lignes) :
- 41 tests métier (CRUD, objectifs, workflow, config, schéma)
- 25 tests routes (intégration via test_client Flask)
- 3 tests schéma (contraintes CHECK et UNIQUE)
- **69 tests, tous verts** sur Linux

## Tests

| | Linux (CI Claude) | Windows attendu |
|---|---|---|
| v0.13.5.6 baseline | 2295 passed + 5 skipped | ~2284 + 16 skipped |
| **v0.13.6.1 final** | **2364 passed + 5 skipped** | **~2353 + 16 skipped** |
| Δ vs baseline | +69 | +69 |

## Décisions clés du scoping

À conserver pour les sessions suivantes :

1. **Référentiel générique** : l'atelier produit des cartes-modèles, pas
   d'objet personnalisé par élève. La personnalisation (nom, classe,
   tirage spécifique) sera gérée plus tard côté suivi de classe.

2. **Planche A4 = 16 cartes** : peu importe la nature, toujours 1 carte
   par feuille. Identiques (fixe) ou différentes (paramétrée). La
   préférence `cartes_param_nb_uniques` permet de produire plusieurs
   feuilles de variantes pour les paramétrées (multiple de 16).

3. **Numérotation locale à la séquence** : `S05/C03` (sur la carte) et
   `C03` (dans le livret). Pas de numérotation globale.

4. **Pas de suivi d'enveloppes** : l'appli n'enregistre pas l'état
   Leitner des cartes en classe (physique). Seuls les résultats d'éval
   orale mensuelle seront stockés en v0.13.6.4.

5. **Badge platine** (100% au premier passage) : à voir si on l'ajoute
   en v0.13.6.3 ou si on l'abandonne (nécessite info « replongé au
   niveau 1 » que l'appli ne suit pas).

## Fichiers livrés (10)

```
appli/persistence/schema.sql
appli/services/cartes_automatisme.py
appli/services/preambule_atome.py
appli/routes/cartes_automatisme.py
appli/app.py
appli/static/atelier_carte_automatisme.js
appli/static/atelier_commun.js
appli/static/app.js
appli/templates/index.html
appli/tests/test_v0_13_6_1_cartes_automatisme.py
```

## Pour la prochaine session (v0.13.6.2)

**Objectif** : génération PDF d'une planche A4 (16 cartes) pour une
séquence donnée.

**Côté paquet** (à demander à Laurent) :
- Créer `seqenseigne-core-cartes.dtx` avec :
  - Macro `\seqCartePlanche{type}{id}{contenu}` (1 carte unique)
  - Environnement `seqPlancheCartes` (16 cartes en grille 4×4)
  - Layout TikZ pour le miroir horizontal recto/verso (impression
    recto-verso + massicotage)
  - Allocations TeX éventuelles encapsulées dans une macro publique
    (cf. pattern `\seqInitCorrigesEval` de v0.13.5.6)

**Côté appli** :
- Module `services/render_cartes_planche.py` :
  - Générer le .tex d'une planche pour (niveau, séquence) avec tirage
    déterministe `hash(carte_id, indice_variante)` pour les paramétrées
- Routes `/api/cartes/planche/<niveau>/<sequence>/rendu-tex` et
  `.../rendu-pdf` (similaire aux routes éval v0.13.5.3)
- UI : panneau « Génération » ou directement bouton « Compiler le
  rendu » qui produit la planche
- Enrichir `WRAPPER_PAR_TYPE['carte_automatisme']` avec les macros du
  paquet
- Enrichir `paquet_regles_atome.py` avec les nouvelles macros en
  `STATUT_REUTILISE`
- Mise à jour du peuplement paquet pour intégrer `core-cartes.sty`

**Pour anticiper** :
- Le rendu d'aperçu d'**une seule carte** (déjà esquissé dans l'UI
  v0.13.6.1, bouton désactivé) sera réactivé en v0.13.6.2
- Penser au cas particulier de la planche pour une carte fixe : 16
  exemplaires identiques (juste de la duplication)
- Penser à la **production multi-élèves** : l'enseignant imprime
  plusieurs fois la même feuille pour avoir suffisamment d'exemplaires
  (côté impression, pas côté appli)
