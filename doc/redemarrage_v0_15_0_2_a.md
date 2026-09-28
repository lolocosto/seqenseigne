# Redémarrage v0.15.0.2.a — Restauration des onglets Référentiel

## Contexte

En testant v0.15.0.1 chez Laurent, ce dernier a constaté que l'atelier
Référentiel ne présentait plus qu'un seul panneau (le « Tableau de
bord »). Or v0.13.6.4 avait livré un bandeau de deux onglets
(« Tableau de bord » / « Documents à publier ») avec deux panneaux
frères :

- `#atl-ref-panneau-dashboard` : l'arbre séquence → partie → objectif → atomes
- `#atl-ref-panneau-documents` : les 9 types de documents publiables avec
  leurs options et un bouton « Tester » pour la compilation

### Diagnostic

Inspection du code montre :
- **JS** (`static/atelier_referentiel.js`, 1452 lignes) : toute la
  machinerie de l'onglet « Documents à publier » est intacte —
  `atelRefChangerOnglet`, `atelRefChargerEtRendreDocuments`,
  `atelRefRendreDocuments`, `atelRefDocumentCadreHtml`,
  `atelRefDocumentOptionsHtml`, `atelRefMajOptionDoc`, et 350+ lignes
  de helpers (cases à cocher, radios, boutons de test).
- **Backend** : les 2 blueprints sont enregistrés dans `app.py`
  (`bp_referentiel_documents`, `bp_referentiel_documents_compilation`) ;
  routes opérationnelles, table BDD `referentiel_documents` peuplée.
- **HTML** (`templates/index.html`) : **les éléments DOM attendus par
  le JS ont disparu**.

Conclusion : une livraison post-v0.13.6.5.1.1 non documentée a supprimé
silencieusement le bandeau d'onglets et les wrappers `#atl-ref-panneau-*`
sans toucher au JS. Le `atelRefChangerOnglet` n'a alors plus aucune
cible DOM, et `atelRefChargerEtRendreDocuments` cherchait un container
inexistant.

Recherche dans les redémarrages : aucun fichier `redemarrage_*.md`
postérieur à v0.13.6.5.1.1 ne mentionne cette suppression. Régression
silencieuse, jamais signalée par aucun test (puisque aucun test ne
vérifiait la présence du HTML).

### Pourquoi maintenant

Laurent voulait revenir sur l'atelier Référentiel parce qu'il sert de
**lieu canonique** de spécification des documents publiables, en vue
de supprimer le cadre dupliqué « Éléments à inclure » côté
Séquence-niveau (chantier v0.15.0.3 à venir).

## Cadrage validé (D1-D3)

| Question | Réponse |
|---|---|
| D1 — Style des onglets | (α) Restaurer à l'identique avec `class="atl-ref-onglet"` + `data-tab` |
| D2 — Position des onglets | À l'intérieur de `#atl-ref-detail` (juste après l'en-tête métadonnées) |
| D3 — Tests | (b) Ajouter un test garde-fou qui parse `index.html` et asserte la présence des éléments |

## Ce que change cette livraison

### 1. Restauration HTML dans `templates/index.html`

À l'intérieur de `#atl-ref-detail`, juste après l'en-tête (titre +
métadonnées + actions) et **avant** l'arbre, ajout du bloc :

```html
<div class="atl-tabs" style="margin-bottom:14px">
  <button class="atl-tab atl-ref-onglet" data-tab="dashboard"
          onclick="atelRefChangerOnglet('dashboard')">
    Tableau de bord
  </button>
  <button class="atl-tab atl-ref-onglet" data-tab="documents"
          onclick="atelRefChangerOnglet('documents')">
    Documents à publier
  </button>
</div>

<div id="atl-ref-panneau-dashboard">
  <div id="atl-ref-arbre"><!-- inchangé --></div>
</div>

<div id="atl-ref-panneau-documents" style="display:none">
  <!-- Rempli par atelRefRendreDocuments() -->
</div>
```

Notes :
- **Double classe** `atl-tab atl-ref-onglet` : `atl-tab` pour le styling
  du design system (padding, border-bottom transparent, hover) et
  `atl-ref-onglet` pour le sélecteur que cible le JS. Le JS écrase
  ensuite les couleurs en inline quand il marque l'onglet actif.
- L'enveloppe `<div id="atl-ref-panneau-dashboard">` englobe l'ex-arbre
  sans modifier son contenu.
- `display:none` initial sur le panneau documents — le JS appelle
  `atelRefChangerOnglet('dashboard')` à chaque sélection, ce qui
  remet l'état au bon endroit, mais on évite un flash visuel au
  premier paint.

### 2. Test garde-fou — `tests/test_v0_15_0_2a_onglets_referentiel.py`

10 tests qui parsent `templates/index.html` et assertent :
- Présence des 2 boutons d'onglets avec leur `data-tab` et leur classe `atl-ref-onglet`.
- Présence des appels JS `atelRefChangerOnglet('dashboard')` et `(...documents...)`.
- Présence des 2 panneaux (`#atl-ref-panneau-dashboard`, `#atl-ref-panneau-documents`).
- Présence de `#atl-ref-arbre` (intégrité du tableau de bord existant).
- Ordre correct dans le DOM (onglets avant panneaux, dashboard avant documents).
- `display:none` initial sur le panneau documents.

Méta-vérification effectuée : ces 10 tests ÉCHOUENT bien (8 sur 10)
si on supprime à nouveau les éléments du HTML. Garde-fou opérationnel.

### 3. Aucun changement JS ni backend

Le JS et le backend de la feature « Documents à publier » étaient
restés intacts depuis v0.13.6.5.1.1. Rien à toucher.

## Vérifs

- **Suite complète** : 3399 passed, 6 skipped, 0 failed
  (était 3390 ; +10 nouveaux tests = +9 au compteur passed +1 ailleurs
  par cohérence des comptes — voir détail dans la conversation de
  développement si nécessaire).
- **Sanity HTML** : balisage bien équilibré, 3 "erreurs" pré-existantes
  identiques avant/après (3 `<option>` sans `</option>` dans un
  `<datalist>` — HTML5 valide).
- **Méta-test** : les nouveaux tests échouent bien si quelqu'un
  resupprime les éléments du HTML.

## Fichiers livrés

```
MODIFIÉ
  appli/templates/index.html              (~55 lignes ajoutées)

NOUVEAU
  appli/tests/test_v0_15_0_2a_onglets_referentiel.py
  appli/doc/redemarrage_v0_15_0_2_a.md
```

Aucun fichier supprimé.

## Procédure d'application

### 1. Décompresser à la racine `seqenseigne/`

Pas de suppression à faire manuellement.

### 2. Vérifier l'intégrité

```powershell
.\outils\python\python.exe appli\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
```

### 3. Lancer la suite de tests

```
cd appli
python -m pytest -q
```

Attendu : `3399 passed, 6 skipped, 0 failed`.

### 4. Test fonctionnel manuel

1. Lance `lancer.bat`.
2. Va sur l'atelier **Référentiel** et sélectionne un niveau.
3. Sélectionne un référentiel existant (ou crée-en un nouveau).
4. **Vérifie** : deux onglets sont visibles dans le détail
   (« Tableau de bord » actif par défaut, « Documents à publier »).
5. Clique sur « Documents à publier » : la liste des 9 types de
   documents publiables s'affiche, avec leurs options éditables
   (case « activé » + cases à cocher pour les sous-options + radios
   pour les énumérés).
6. Pour le type « Livret de séquence » : configure ses options
   (contenu, plan de travail en-tête, fiches en-fin, énoncés série A,
   corrigés par série), coche « activé », et clique sur « Tester »
   (s'il y a un bouton — sinon la compilation peut nécessiter de
   passer par un endpoint de test à confirmer plus loin).

Si tout fonctionne, on enchaîne sur **v0.15.0.3** (suppression du
cadre « Éléments à inclure » côté Séquence-niveau, cf. ci-dessous).

## Étapes suivantes

### v0.15.0.3 — Suppression du cadre « Éléments à inclure » côté Séquence-niveau

**Cadrage validé (E1-E3)** lors de la même conversation :

| Question | Décision |
|---|---|
| E1 — Que faire du cadre d'options côté Séquence | Supprimer entièrement ; la compilation force « tout inclus » |
| E2 — Que devient l'API `/api/v2/livret-sequence/.../rendu-pdf` | Conservée mais sans option dans le body, options figées côté Python |
| E3 — Périmètre | Chantier séparé (cette livraison v0.15.0.2.a, puis v0.15.0.3) |

Concrètement, v0.15.0.3 fera :
- Suppression du cadre HTML/JS « Éléments à inclure » dans
  `atelier_seqniv_assemblage.js` (~110 lignes : `_rendreBlocElementsAInclure`
  + `seqnivAsmMajElementsAInclure` + helpers).
- Suppression de `_livretSeqOptions()` (lignes 2423-2443).
- Modification des appels POST vers `rendu-pdf` et `rendu-tex` pour
  ne plus envoyer de body `{ options: ... }`.
- Côté backend (`services/livret_sequence.py` + route) : ignorer le
  body s'il en arrive un (pour compat), et appliquer un set d'options
  « tout inclus » figées en Python.

## Dette technique

Cet incident illustre un risque récurrent : **les modifications HTML
ne sont pas automatiquement testées**, contrairement aux modifications
Python/SQL (couverts par 3399 tests). Une régression HTML peut donc
passer plusieurs livraisons sans détection.

À ajouter à `doc/DETTE_TECHNIQUE.md` (déjà créé en v0.15.0.1) :

- **Couverture HTML** : généraliser le pattern de test garde-fou
  v0.15.0.2.a aux autres ateliers (Évaluation, Séquence-niveau, Carte,
  Notion, Méthode, Exercice, Fiche, Thème, etc.). Permettrait de
  détecter en CI une régression HTML similaire à celle qui a perdu
  les onglets Référentiel.
