# Redémarrage v0.13.6.5.1.1

**Session du 13 mai 2026 — Service de compilation centralisé + UI d'erreurs**

---

## Récap version

| Version | État |
|---|---|
| v0.13.6.5.1 | ✅ Compilation des documents publiables (UI + squelette) |
| **v0.13.6.5.1.1** | 🟡 **À déployer** — Orchestrateur centralisé + UI erreurs riches |
| v0.13.6.5.2 | À venir : 4 services métier manquants |
| v0.13.6.5.3 | À venir : figeage étendu |

---

## Demande initiale

> *À améliorer : les infos en cas d'erreur. Donner accès au log de
> compilation permettrait de mieux qualifier l'erreur (syntaxe dans un
> atome, préambule incomplet, etc).*
>
> *Il y a déjà tout ça dans la compilation des atomes par exemple, et
> je crois qu'il est temps de mettre en place un service de compilation
> centralisé.*

Deux besoins liés :
1. **Pratique** : accéder au log de compilation + au .tex brut depuis
   l'UI des documents publiables (comme l'atelier exo/notion/etc. le
   propose déjà)
2. **Architectural** : centraliser le code de compilation, aujourd'hui
   dupliqué dans 5+ endroits

---

## Stratégie : refacto en 3 étapes, on fait l'étape A

| Étape | Périmètre | Cette session ? |
|---|---|---|
| **A** | Orchestrateur + UI erreurs centralisée + intégration côté référentiel | ✅ |
| B | Migrer une à une les routes existantes (rendu_atome, recap_cours, etc.) vers l'orchestrateur | ⏳ plus tard |
| C | Suppression du code mort, doc finale | ⏳ plus tard |

L'étape A apporte la valeur immédiate (accès au log pour les documents
publiables) sans rien casser des routes existantes.

---

## Ce qui a été fait

### Backend

#### `services/orchestrateur_compilation.py` (nouveau, ~400 lignes)

Couche d'orchestration entre les routes/services métier et le
compilateur LaTeX bas niveau.

- **Registre** `REGISTRE: dict[str, ProducteurTex]` : un producteur de
  .tex par type de cible compilable.
- **Décorateur** `@enregistrer_producteur(type_cible)` : enregistre un
  producteur dans le registre.
- **Façade** `compiler(conn, type_cible, cible, options, ...)` qui :
  1. Cherche le producteur dans le registre
  2. Produit le .tex (peut lever `ProducteurErreur`)
  3. Compile via `compilateur_pdf.compiler_atome`
  4. Persiste sur disque les artefacts : `.tex`, `.log`, `.pdf` (sous
     `dossier_artefacts/<cible_key>.<ext>`)
  5. Renvoie un `ResultatOrchestration` avec `type_echec ∈
     {producteur, latex, infrastructure, None}`
- **Producteurs enregistrés** pour les 9 types de documents publiables :
  - 5 fonctionnels : `livret_sequence`, `livret_cours`, `livret_exercices`,
    `livret_plans`, `evaluation`
  - 4 prévus pour v0.13.6.5.2 : lèvent `ProducteurErreur(code='type_non_implemente')`

#### `services/referentiel_documents_compilation.py` (refactorisé)

- `_generer_tex` devient un thin wrapper qui délègue au registre
  (rétrocompat pour les tests v0.13.6.5.1).
- `compiler_document` utilise désormais `orchestrateur_compilation.compiler()`
  au lieu de l'ancien duo `_generer_tex` + `compiler_atome` recopié.
- Nouveau format de `compile_log` (JSON) :
  ```json
  {
    "version": "1",
    "type_document": "livret_sequence",
    "cibles": [
      {
        "cible_id": "N10/S01",
        "libelle": "Livret N10/S01",
        "cible_key": "N10_S01",
        "ok": false,
        "type_echec": "latex",
        "duree_ms": 12345,
        "nb_erreurs": 3,
        "premieres_erreurs": [
          {"ligne": 42, "message": "Undefined control sequence", "contexte": "\\machin{...}"}
        ]
      }
    ]
  }
  ```
- Stockage des artefacts : `data/referentiels/<ref_id>/_artefacts/<cible_key>.{tex,log,pdf}`
- Le PDF métier (chemin original) est aussi écrit pour préserver l'API
  GET `/pdf` existante.
- Nouveau helper `chemin_artefact(store, ref_id, cible_key, ext)` pour
  servir les artefacts.

#### `routes/referentiel_documents_compilation.py` (étendu)

Deux nouveaux endpoints :
- `GET /api/referentiels/<ref_id>/documents/<doc_id>/tex` — renvoie le
  .tex source effectivement compilé
- `GET /api/referentiels/<ref_id>/documents/<doc_id>/log` — renvoie le
  log complet pdflatex

Pour les types multi-cible, query string `?cible=<cible_id>` requise.

### Frontend

#### `static/compilation_erreurs.js` (nouveau, ~330 lignes)

Module UI partagé pour afficher les erreurs de compilation. API :

```js
compErreursAfficher(conteneurId, {
  titre, sousTitre,
  cibles: [{cible_id, libelle, ok, type_echec, premieres_erreurs}, ...],
  texUrl: cibleId => '...',
  logUrl: cibleId => '...',
});
```

- Sélecteur de cible en haut (visible si >1 cible KO)
- Liste cliquable des erreurs (clic → scroll vers la ligne dans le .tex)
- Bouton « Voir le .tex brut » avec lignes numérotées + highlight des
  lignes fautives
- Bouton « Voir le log complet » avec rendu pre/monospace
- Gestion multi-instances (utilisable plus tard dans d'autres ateliers)
- Différencie les types d'échec :
  - `producteur` : erreur avant compilation → pas de .tex/log à montrer
  - `latex` : erreur pdflatex classique → .tex/log disponibles
  - `infrastructure` : pdflatex absent / timeout → pas de .tex/log utile

#### `static/atelier_referentiel.js` (étendu)

- Nouveau bouton **« Voir les erreurs »** à côté du badge `ko`
- Nouvelle fonction `atelRefBasculerErreurs(docId)` qui :
  1. Récupère le `compile_log` JSON via l'API statut
  2. Délègue le rendu au module `compilation_erreurs.js`
  3. Pose le panneau dans une zone dépliable du cadre document

#### `templates/index.html` (modifié)

Inclusion du nouveau module `<script src="/static/compilation_erreurs.js">`
juste avant `atelier_referentiel.js`.

### Tests

`tests/test_v0_13_6_5_1_1_orchestrateur.py` — **20 tests** :
- 3 sur le registre (présence des 9 types, types à venir, remplacement)
- 3 sur slug_cible (basique, caractères spéciaux, idempotence)
- 4 sur compiler() (type inconnu, type à venir, cible invalide,
  producteur qui lève)
- 2 sur la persistance des artefacts
- 2 sur la rétrocompat `_generer_tex` (délégation à l'orchestrateur)
- 1 sur le format JSON de `compile_log`
- 5 sur les routes /tex et /log (doc non compilé, doc inconnu,
  cible requise, cible inconnue)

Tous passent. **Tests v0.13.6.5.1 (21) passent toujours** : la
refactorisation est rétrocompatible.

Suite complète : **2441 passed, 5 skipped, 0 régression**
(= 2421 baseline v0.13.6.5.1 + 20 nouveaux).

---

## Validation côté Laurent

1. Décompresser le ZIP, recharger Flask.
2. Aller dans l'atelier Référentiel d'un référentiel `en_cours`,
   onglet « Documents à publier ».
3. **Reproduire ton test précédent** : activer un document, lancer
   « Tester ». Si le PDF compile : tu vois le lien « 📄 Voir le PDF »
   comme avant.
4. **Faire échouer une compilation** (ex: introduire une faute LaTeX
   volontaire dans une notion, puis tester un `livret_cours` qui
   l'inclut). À l'échec :
   - Le badge devient rouge « Erreur »
   - Un bouton **« Voir les erreurs »** apparaît à côté
   - Au clic : panneau d'erreurs avec
     - liste des erreurs (ligne + message)
     - bouton **« Voir le .tex brut »** → ouvre une zone avec lignes
       numérotées, les lignes fautives en rouge clair
     - bouton **« Voir le log complet »** → ouvre le log pdflatex en
       texte intégral
     - clic sur une erreur → scroll automatique vers sa ligne dans le
       .tex (avec flash de surbrillance)
5. **Multi-cible** : tester un `livret_sequence` activé. Si plusieurs
   séquences échouent, un sélecteur de cible apparaît en haut du
   panneau. Bascule entre les cibles KO pour voir leurs erreurs
   respectives.

---

## Décisions prises

| Question | Décision |
|---|---|
| Périmètre refacto | Étape A : orchestrateur + UI erreurs centralisée + intégration référentiel (pas migration des routes atomes existantes — c'est l'étape B) |
| UI erreurs | Comme `rendu_atome.js` : liste cliquable + .tex brut + log complet |
| Multi-cible | Sélecteur de cible en haut du panneau (uniquement si >1 cible KO) |
| Format `compile_log` | JSON structuré (sérialisé en TEXT) au lieu de texte concaténé |
| Stockage artefacts | `data/referentiels/<ref_id>/_artefacts/<cible_key>.{tex,log,pdf}` |
| Rétrocompat des tests v0.13.6.5.1 | OUI — `_generer_tex` reste exposée et délègue à l'orchestrateur |

---

## Hors scope (v0.13.6.5.2 et au-delà)

- ❌ Migrer `rendu_atome.py`, `recap_cours.py`, `recap_exos.py`,
  `cartes_automatisme.py`, `evaluations.py` vers l'orchestrateur
  (= étape B). Ces routes continuent d'appeler `compiler_atome`
  directement.
- ❌ Les 4 services métier manquants
  (`livret_fiches/_corriges/_cartes_*`) — leurs producteurs lèvent
  `type_non_implemente` jusqu'à v0.13.6.5.2
- ❌ Affinage du critère « périmé » atome→documents
- ❌ Figeage étendu
- ❌ UI unifiée pour les erreurs des atomes (ils continuent d'utiliser
  leur propre code `rendu_atome.js` ; il pourra être remplacé par
  `compilation_erreurs.js` à l'étape B)

---

## Architecture cible (visée)

```
┌──────────────────────────────────────────────────────────────────┐
│ Routes Flask                                                     │
│  - rendu_atome.py                                                │
│  - recap_cours.py / recap_exos.py / livret_sequence.py           │
│  - evaluations.py / cartes_automatisme.py                        │
│  - referentiel_documents_compilation.py   ← MIGRÉE v0.13.6.5.1.1 │
└────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│ services/orchestrateur_compilation.py     ← NOUVEAU              │
│  - REGISTRE: dict[str, ProducteurTex]                            │
│  - compiler(conn, type_cible, cible, options, ...)               │
│    → ResultatOrchestration(ok, pdf_bytes, log, tex_source, …)    │
│  - Persistance des artefacts sur disque                          │
└────────────────┬─────────────────────────────────┬───────────────┘
                  │                                  │
┌─────────────────▼───────────┐ ┌──────────────────▼─────────────┐
│ services/compilateur_pdf.py │ │ Producteurs .tex (enregistrés  │
│  (inchangé)                 │ │ via décorateur dans            │
│  - compiler_atome           │ │ orchestrateur_compilation.py)  │
│  - extraire_erreurs         │ │  - 5 fonctionnels              │
└─────────────────────────────┘ │  - 4 'à venir' (v0.13.6.5.2)   │
                                 └────────────────────────────────┘
```

À terme (étapes B/C), toutes les routes ci-dessus passeront par
l'orchestrateur. Les services métier individuels (livret_sequence,
livret_recap_cours, render_evaluation, …) restent inchangés — c'est
juste l'aiguillage qui se centralise.

---

## Fichiers livrés

```
appli/services/orchestrateur_compilation.py            (nouveau, ~400 lignes)
appli/services/referentiel_documents_compilation.py    (refacto)
appli/routes/referentiel_documents_compilation.py      (étendu)
appli/static/compilation_erreurs.js                    (nouveau, ~330 lignes)
appli/static/atelier_referentiel.js                    (étendu)
appli/templates/index.html                             (+1 ligne <script>)
appli/tests/test_v0_13_6_5_1_1_orchestrateur.py        (nouveau, 20 tests)
appli/doc/redemarrage_v0_13_6_5_1_1.md                 (ce fichier)
```
