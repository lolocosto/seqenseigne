# Redémarrage v0.13.7.0e.2 — Convention uniforme POST / PATCH

## Périmètre

Petit patch consolidant la convention pour les 5 ateliers atomiques :

> **POST initial avec niveau/séquence, puis PATCH de modification
> sans niveau/séquence.**

Avant v0.13.7.0e.2, trois ateliers (notion, méthode, fiche)
envoyaient encore `niveau` et `sequence` dans le body PATCH, ce qui
fonctionnait par chance parce que les backends correspondants soit les
acceptaient (notion, méthode), soit les ignoraient silencieusement
(fiche). Seule la carte rejetait ces champs (cf. v0.13.7.0e.1).

L'incohérence n'était plus tenable. v0.13.7.0e.2 aligne les 5 ateliers
sur le même contrat.

## Contrat uniforme post-v0.13.7.0e.2

| Méthode JS | Envoie niveau/sequence ? | Utilisée par |
|---|---|---|
| `_payloadCreation()` | **OUI** | POST de création (`nouvelItem`) |
| `collecterFormulaire()` | **NON** | PATCH de modification (`sauvegarder`) + snapshot dirty |

Chaque atelier respecte la convention :

| Atelier | `_payloadCreation` | `collecterFormulaire` |
|---|---|---|
| Carte | surcharge + niveau/seq | sans niveau/seq (v0.13.7.0e.1) |
| Notion | hérite du parent (+ niveau/seq) | sans niveau/seq (v0.13.7.0e.2) |
| Méthode | hérite du parent (+ niveau/seq) | sans niveau/seq (v0.13.7.0e.2) |
| Fiche | surcharge + niveau/seq | sans niveau/seq (v0.13.7.0e.2) |
| Exercice | surcharge avec niveau/seq+serie+enonce+corrige | sans niveau/seq (déjà) |

Note exercice : `nouvelItem` est surchargé pour intercaler la modale de
choix de série. Le POST est fait directement dans cette méthode (n'utilise
pas `_payloadCreation`), avec un body qui contient niveau/séquence comme
attendu.

## Code retiré

Pour notion et méthode, le bloc « fallback legacy » (qui ajoutait
niveau/séquence à la modification dans le cas où l'atome legacy n'en
avait pas) est supprimé. En pratique, ce code n'était plus déclenché
depuis longtemps (toutes les notions/méthodes en BdD ont leur scope
correct). Le retrait simplifie sans changer le comportement réel.

## Fichiers livrés

```
appli/static/atelier_notion.js               [MOD]   simplification collecterFormulaire
appli/static/atelier_methode.js              [MOD]   idem
appli/static/atelier_fiche.js                [MOD]   idem
appli/doc/redemarrage_v0_13_7_0e_2.md        [NEW]
```

Bilan : ~45 lignes supprimées (les 3 blocs « règle de scope » qui
deviennent inutiles).

## Vérifications

- Suite pytest : **3238 passed, 5 skipped, 0 failed** (identique)
- Sanity JS sur les 3 fichiers modifiés : OK
- Cohérence : aucun `niveau:` ni `sequence:` ne subsiste dans le retour
  d'un `collecterFormulaire` sur les 5 ateliers atomiques

## À tester chez toi

### Scénario A — Sauvegarde directe (les 5 ateliers)

1. Ouvrir un item existant (carte, notion, méthode, fiche, exercice).
2. Modifier un champ.
3. Cliquer « Enregistrer ».
4. **Doit sauvegarder sans erreur** (log Flask : `PATCH ... 200`).

Pour la carte, c'est la confirmation de la correction v0.13.7.0e.1.
Pour les autres, c'est une vérification de non-régression — leur
sauvegarde marchait déjà.

### Scénario B — Garde modale (les 5 ateliers)

1. Modifier sans sauvegarder.
2. Cliquer ailleurs → modale 3 boutons.
3. « Sauvegarder » fait le PATCH et bascule.
4. « Ne pas sauvegarder » restaure visuellement le DOM.
5. « Annuler » reste sur place.

### Scénario C — Création (les 5 ateliers)

1. « + Nouveau / Nouvelle » dans chaque atelier.
2. La création doit positionner l'atome dans la séquence courante
   (vérifier qu'il apparaît bien dans la sidebar de la séquence active).

### Diagnostic log

Côté serveur, tu devrais voir uniquement :
- `POST /api/<atome>` pour la création
- `PATCH /api/<atome>/<id>` pour la modification
- Plus aucun `405` ni `400` sur ces routes (sauf cas d'erreur métier
  réelle comme une validation pédagogique qui échoue).

## Conclusion du fil garde-de-sortie

Cette livraison ferme **vraiment** le fil garde-de-sortie. Bilan
complet :

| Version | Apport |
|---|---|
| v0.13.7.0a | Câblage oninput HTML (incomplet) |
| v0.13.7.0c | Modale 3 boutons unifiée + suppression code legacy |
| v0.13.7.0d | Snapshot + listener délégué + restauration DOM dans AtelierEditeur |
| v0.13.7.0d.1 | Bug HTTP 405 carte (PUT vs PATCH côté serveur) |
| v0.13.7.0e | Factorisation routes atomes + PATCH partout (strict) |
| v0.13.7.0e.1 | Bug HTTP 400 carte (champs niveau/seq non acceptés) |
| v0.13.7.0e.2 | Convention POST/PATCH uniforme sur les 5 ateliers |

État après v0.13.7.0e.2 :
- Architecture parente unique pour la garde, snapshot-based
- UX uniforme : modale 3 boutons partout
- Sémantique HTTP correcte (PATCH partout)
- Routes atomes factorisées dans `_enregistrer_routes_atome`
- Convention POST/PATCH explicite et homogène

## Prochaine étape

Avec cette base saine, **v0.13.7.1 — squelette éditeur LaTeX** peut
démarrer (cadrage déjà acté dans `cadrage_v0_13_7_1_editeur_latex.md`).

Petit reste à connaître :
- `AtelierExercice.nouvelItem` utilise encore `confirm()` natif L310-314
  au lieu de `atelGardeAvantAction`. Pas critique (la garde fonctionne
  quand même), à harmoniser quand ça se présentera.
- Les méthodes `_payloadCreation` de carte/fiche/exercice surchargent
  le parent alors que notion/méthode héritent. Asymétrie acceptable
  (chaque atelier a ses valeurs par défaut spécifiques), mais on
  pourrait factoriser via une convention « `_champsCreationParDefaut()`
  → dict de champs ajoutés au payload de base ». Pas urgent.
