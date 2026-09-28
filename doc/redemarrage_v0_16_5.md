# Redémarrage v0.16.5 — Régime de persistance mixte + verrou UI de l'évaluation (2b-2)

## Contexte

Aboutissement du chantier 2b : l'évaluation adopte le régime de persistance
mixte (comme prévu §5ter du cadrage d'unification) ET reçoit le verrou UI
lecture seule (complète v0.16.4, où seul le backend protégeait l'éval). Les deux
convergent ici car ils dépendent du `<form id="atl-eval-form">`.

Cf. `cadrage_2b2_regime_mixte_verrou_eval.md`.

## Décisions (Laurent)

- **Conception Y** : barèmes HORS snapshot, marqués par un drapeau dédié
  (`oninput` explicite). `collecterFormulaire()` ne capture que les champs
  stables (titre, mode, afficher-barème, langue). Rationale : un barème est
  attaché à un exo dont la présence relève de la structure ; le mettre dans le
  snapshot ferait diverger celui-ci à chaque ajout/retrait d'exo et effacerait
  la trace d'un champ modifié.
- **Barèmes poussés à l'Enregistrer** : TOUS (endpoint groupé idempotent).
- **Tout ensemble** (régime mixte + verrou UI) dans cette version.
- **Opération de structure sur éval modifiée** : BLOQUÉE (`_garderAvantStructure`).
  Une op de structure recharge l'éval depuis la BDD et re-remplit le form, ce
  qui écraserait une saisie non enregistrée → on exige d'enregistrer d'abord.

## Ce qui est livré

### Régime de persistance mixte

- **Getter `modifie` combiné** : `super.modifie || this._baremesModifies`.
  L'ancien flag manuel `_modifieFlag` est supprimé partout.
- **`collecterFormulaire()`** : capture titre, mode_notation,
  afficher_bareme_dans_exos, item_langue_francaise (champs stables).
- **`<form id="atl-eval-form">`** ajouté autour de l'onglet édition ;
  `_installerListenerForm` (hérité) câblé dans `_rendreVueComplete` → les champs
  stables mettent à jour la toolbar (badge + bouton save) via le snapshot.
- **Barèmes** : inputs marqués `data-exo-id` + `data-bareme-champ`, `oninput`
  → `marquerModifie()` (lève `_baremesModifies`). `sauverBareme` (PATCH immédiat
  par champ) et son wrapper SUPPRIMÉS. À l'Enregistrer, `sauvegarder()` PATCHe
  les champs puis pousse TOUS les barèmes via `PATCH .../baremes` (groupé,
  v0.16.3), puis reprend un état propre.
- **Snapshot pris APRÈS rendu** dans `selectionner`/`nouvelItem` (état propre) ;
  PAS repris après une opération de structure (préserve l'état modifié → garde
  de sortie fiable).

### Garde avant opération de structure

`_garderAvantStructure()` appelée par les 5 opérations de structure
(ajouterExo, retirerExo, **deplacerExo** = réordonnancement, ajouterObjectif,
retirerObjectif), y compris via les hooks polymorphes `ajouter/retirer/
deplacerElement`. Si `this.modifie` → toast « Enregistrez vos modifications
avant de modifier la structure » et opération annulée.

### Verrou UI lecture seule de l'évaluation

`_majToolbar` appelle `_appliquerVerrouLectureSeule(etat === 'valide')` (méthode
héritée d'AtelierEditeur, qui agit sur `#atl-eval-form`). Quand l'éval est
validée : champs et boutons de structure grisés ; « Repasser en cours », onglets
et « Compiler » restent actifs (hors form). Complète la protection backend
(409) de v0.16.4.

## Tests

**v0.16.5 : 3774 passed, 7 skipped, 0 failed.**

Nouveau `tests/test_v0_16_5_regime_mixte_eval.py` (16 tests structurels — pas de
tests JS dans le dépôt) :
- Form présent ; `collecterFormulaire` = champs stables seulement (pas de
  barème) ; listener form installé ; getter combiné.
- `sauverBareme` supprimé ; inputs barème avec data-attrs + oninput ;
  `_collecterBaremes` existe ; push groupé dans `sauvegarder`.
- `_garderAvantStructure` existe et est appelée par les 5 op. de structure.
- Verrou UI appliqué dans `_majToolbar` ; plus de `_modifieFlag`.

## Fichiers livrés (`seqenseigne_v0_16_5.zip` — incrémental depuis v0.16.4)

| Fichier | Action |
|---|---|
| `appli/static/atelier_evaluation_oo.js` | Modifié (régime mixte, verrou, garde) |
| `appli/templates/index.html` | Modifié (form englobant) |
| `appli/tests/test_v0_16_5_regime_mixte_eval.py` | Nouveau |
| `appli/doc/cadrage_2b2_regime_mixte_verrou_eval.md` | Nouveau (cadrage) |
| `appli/doc/README.md` | Modifié (roadmap : badges assemblage) |
| `appli/doc/redemarrage_v0_16_5.md` | Nouveau (ce document) |

## Vérification post-déploiement

```powershell
.\outils\python\python.exe outils\verifier_md5.py --racine . --manifest MANIFEST.md5
.\outils\python\python.exe -m pytest tests/ -q
```

Tests fonctionnels (IMPORTANT — pas de tests JS, validation visuelle requise) :
1. **Champ** : modifier titre/mode/afficher-barème/langue → badge « modifié »
   apparaît + bouton Enregistrer actif. Quitter sans enregistrer → garde.
2. **Barème** : modifier un barème d'exo → badge « modifié ». Enregistrer →
   tous les barèmes persistés (vérifier en rouvrant). Plus de sauvegarde à la
   frappe.
3. **Structure bloquée** : modifier un champ (badge allumé), puis tenter
   d'ajouter/retirer/réordonner un exo → refusé avec toast « Enregistrez… ».
   Enregistrer d'abord → l'opération de structure passe.
4. **Structure sans modif** : sur une éval propre, ajouter/retirer/réordonner →
   OK, pas de badge parasite.
5. **Verrou** : valider une éval → champs et boutons de structure grisés ;
   seul « Repasser en cours » actif. Repasser en cours → tout réactivé.

## Suite

Chantier 2 (consolidation de la base) terminé. Reprise du plan d'unification :
- **Étape 3-4** : migration OO du seqniv (procédural → `AtelierSeqnivAssemblage`),
  réécriture HTML, puis DnD (avec tests JS Vitest).
- **Étape 2bis** : aperçu PDF au survol (dans `AtelierAssemblage`).
- Roadmap : badges verts pâle des atomes validés dans le panneau d'assemblage.
