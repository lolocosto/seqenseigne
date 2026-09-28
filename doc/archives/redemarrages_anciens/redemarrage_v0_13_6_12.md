# Redémarrage v0.13.6.12 — Uniformisation `exercices.nom` → `exercices.titre` + 4 demandes UI

## Périmètre

Livraison à double objet, demandée par Laurent dans le cadre de l'effort
général d'harmonisation des champs et libellés à travers les ateliers :

### Volet 1 — Renommage transverse `nom` → `titre` côté exo

L'attribut métier d'un exercice était stocké comme `nom` (héritage du
scanner LaTeX, dont l'option `\begin{seqExercice}[nom=...]` est nommée
ainsi). Tous les autres atomes (notion, méthode, fiche) utilisent
`titre`. Cette asymétrie est levée : BDD, JSON, JS, ID HTML parlent
désormais `titre`. **La couche LaTeX conserve l'option `nom=`** —
frontière de mapping explicite, pas de retour en arrière (option 2
actée en scoping : « BDD + JSON + JS uniquement. La couche LaTeX garde
`nom=` cause d'inertie des .tex existants. Asymétrie assumée »).

### Volet 2 — 4 demandes UI

1. Harmoniser le libellé du titre : « Titre » seul, sans qualificatif
   (notion, méthode, exercice, fiche).
2. Bouton « ⤵ reprendre titre objectif » sur la même ligne que le label
   « Titre », tout à droite. Tooltip conservé.
3. Supprimer le paragraphe d'aide notion (« Le titre doit être
   compréhensible hors contexte. Le numéro d'ordre est attribué dans
   l'atelier Séquence (niveau). »).
4. Supprimer le fallback titre côté fiche (le code affichait
   `f.objectif_nom` en italique quand `f.titre` était vide). En
   contrepartie : **migration BDD one-shot** des 149 fiches sans titre
   pour leur assigner `titre = objectif_nom`, matérialisant ce qui
   était implicite.

Le bloc « objectif lié » côté fiche (sélecteur + chargement
`_chargerObjectifsDisponibles`) reste : c'est le chantier D, reporté.

## Décisions de scoping actées

| Question | Décision |
|---|---|
| Que faire des 149 fiches existantes sans titre ? | Migration one-shot : titre := objectif_nom |
| Supprimer aussi le sélecteur d'objectif fiche ? | Non, reporté chantier D |
| Ampleur du renommage `nom` → `titre` exo | Option 2 : BDD + JSON + JS, LaTeX intacte (`nom=` côté option du paquet) |
| Élagage des tests (3200+, 8 min) | Reporté à session dédiée |

## Architecture — frontière LaTeX

Le champ métier `titre` traverse BDD → JSON → JS, mais la sérialisation
vers le LaTeX écrit toujours `\begin{seqExercice}[nom=...]`. De
même, le scanner LaTeX lit l'option `nom=` du .tex et la stocke dans
le champ interne `titre`.

```
LaTeX (.tex, paquet seqenseigne)          Interne (BDD, JSON, JS)
─────────────────────────────────         ─────────────────────────
\begin{seqExercice}[nom=...]   ──[scan]──>   exercice.titre
                                <─[rendu]──   exercice.titre
```

3 sites font ce mapping côté serveur :
- `importers/scanner_latex.py` (lecture)
- `services/latex_rendu_atome.py` ligne 837 (écriture, `opts.append(f'nom={...}')`)
- `services/livret_recap_exos.py` ligne 252 (idem)

1 site côté frontend (génération preview) :
- `static/atelier_exercice.js::genererLatex()` ligne 441 (variable JS `titre` → option `nom=`)

## Fichiers livrés

### Backend (9 fichiers)

| Fichier | Modification |
|---|---|
| `persistence/schema.sql` | CREATE TABLE exercices : `nom` → `titre` |
| `persistence/sqlite_store.py` | Migration `ALTER TABLE RENAME COLUMN` + migration one-shot fiches ; INSERT/UPDATE adaptés |
| `services/atomes.py` | 3 occurrences `nom` → `titre` |
| `services/latex_rendu_atome.py` | SELECT exercice : `nom` → `titre` (`charger_atome`) |
| `services/v2_edition.py` | 4 sites : SELECT + dicts de retour (`exercice.nom` → `exercice.titre`) |
| `services/v2_lecture.py` | 2 sites : SELECT + dicts (idem) |
| `services/evaluations.py` | 2 SELECT `e.nom` → `e.titre`, dicts de retour |
| `services/render_evaluation.py` | `eb.get('nom')` → `eb.get('titre')` |
| `routes/evaluations.py` | SELECT et dict de retour |
| `scanner_latex.py` (racine) | Champ interne `nom` → `titre` (option LaTeX `nom=` conservée) |

### Frontend (6 fichiers)

| Fichier | Modification |
|---|---|
| `templates/index.html` | 4 zones titre refondues (`<div class="atl-field-titre-row" data-slot-reprendre-obj="...">`), libellés harmonisés « Titre », ID `atl-exo-nom` → `atl-exo-titre`, paragraphe d'aide notion supprimé |
| `static/app.css` | Nouvelles classes `.atl-field-titre-row` (flex space-between) + `.atl-btn-reprendre-obj` |
| `static/atelier_exercice.js` | `ex.nom` → `ex.titre`, `this.$('nom')` → `this.$('titre')`, ID `atl-exo-titre`, variable JS `nom` renommée |
| `static/atelier_evaluation.js` | `ex.nom` → `ex.titre` (ligne 532) |
| `static/atelier_fiche.js` | Fallback `f.objectif_nom` italique supprimé |
| `static/atelier_editeur.js` | `_injecterBoutonReprendreTitre` cible le slot `[data-slot-reprendre-obj]` plutôt que d'insérer après l'input |
| `static/app.js` | 5 sites adaptés (rendu liste, deux `collecter`, `atelExoRemplir`, ID HTML, variable LaTeX) |

### Tests adaptés (16 fichiers, automatique via 2 scripts)

Tests migrés via `tools/migrer_tests.py` (INSERT/UPDATE/SELECT) et
`tools/migrer_tests2.py` (CREATE TABLE) :
`test_R4e1_v2_lecture.py`, `test_R4e4b_edition_exos.py`, `test_latex_rendu_atome.py`,
`test_v0_10_assemblage.py`, `test_v0_10_4_etats_edition.py`, `test_v0_10_2_precedences.py`,
`test_v0_12_0_seances.py`, `test_v0_12_1_livret_plans_de_travail.py`,
`test_v0_12_3_0_deplacer_objectif.py`, `test_v0_13_5_2_1_evaluations.py`,
`test_v0_13_5_2_2_evaluations_metier.py`, `test_v0_13_5_2_3_type_format.py`,
`test_v0_13_5_2_5_exos_enrichis.py`, `test_v0_13_5_3_render_evaluation.py`,
`test_livret_sequence.py`, `test_route_livret_sequence.py`, `test_route_rendu_atome.py`,
`test_peuplement_schema.py`.

Adaptations ponctuelles (assertions sur le nom de clé) :
- `test_R4e1_v2_lecture.py` : `["nom"]` → `["titre"]` (test_exo_metadonnees_exercice_jointes)
- `test_R4e4b_edition_exos.py` : set de keys assertion
- `test_ecrire_exercices_fk.py` : helper `_exo` + lignes 211/215
- `test_v0_10_7_regles_metier.py` : lignes 257/261
- `test_v0_13_5_2_4_evaluations_routes.py` : helper `_creer_exo` + 1 appel
- `test_v0_13_5_2_5_exos_enrichis.py` : assertions lignes 104/243
- `test_v0_13_5_3_render_evaluation.py` : ligne 845

## Migration BDD — validation

Testée sur la BDD réelle de Laurent (149 fiches sans titre, 1 avec) :

**Avant** :
```
exercices : ['cadre_reponse_lignes_principal', ..., 'nom', ...]  (a 'nom' : True,  a 'titre' : False)
fiches sans titre : 149
```

**Après** :
```
exercices : (a 'nom' : False, a 'titre' : True)
fiches sans titre : 0
fiches avec titre : 150
```

Idempotente confirmée (2e exécution → 0 modification).

Exemples de fiches migrées :
```
titre='Pour les nombres décimaux, passer de l'écriture décimale à l'...'
obj  ='Pour les nombres décimaux, passer de l'écriture décimale à l'...'
```

Les libellés d'objectifs (phrases pédagogiques officielles du
programme) deviennent les titres des 149 fiches, modifiables ensuite
librement depuis l'atelier.

## Suite pytest

**2378 passed, 5 skipped, 0 failed** (en 3 min 43 s).

### Tests ignorés (4 fichiers, 97 tests) — hors périmètre

Les fichiers suivants dépendent de la feature `referentiel_documents`
(`services/referentiel_documents.py`) qui n'est **pas déployée** dans
ton arborescence actuelle. Le service Python existe dans la sandbox
mais ni le schéma BDD ni la migration ne créent la table
`referentiel_documents`. Cette feature appartient à une livraison
v0.13.6.4 qui n'a pas été appliquée chez toi. À traiter en livraison
dédiée si tu veux remettre ça en ordre.

```
tests/test_v0_13_6_4_documents_publiables.py
tests/test_v0_13_6_5_1_compilation.py
tests/test_v0_13_6_5_1_1_orchestrateur.py
tests/test_v0_13_6_5_2_livrets_manquants.py
```

Le total **2378 + 97 = 2475** correspond exactement à la suite de
v0.13.6.11. **0 régression** sur les tests qui passaient auparavant.

## CSS — nouvelles classes

```css
.atl-field-titre-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.atl-field-titre-row .atl-label { margin-bottom: 0; }
.atl-btn-reprendre-obj {
  font-size: 11px;
  padding: 2px 8px;
  background: transparent;
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-muted);
  white-space: nowrap;
}
.atl-btn-reprendre-obj:hover {
  background: var(--surface-light);
  color: var(--text-secondary);
}
```

## Points de vigilance pour la prochaine livraison

1. **Cohérence côté `app.js` legacy** : `app.js` contient encore du
   code legacy de l'atelier exercice (lignes ~2390-2790) maintenu par
   compat. Si tu touches à ce code, garde `titre` et non `nom`.
2. **Frontière LaTeX explicite** : tout ajout d'option LaTeX côté
   `seqExercice` doit garder la syntaxe `nom=` côté .tex. Le mapping
   se fait dans `latex_rendu_atome.py` / `livret_recap_exos.py` /
   `atelier_exercice.js::genererLatex()`.
3. **Tests externes** : si tu ajoutes un test qui INSERT dans
   `exercices`, utilise le champ `titre`. Si tu utilises `lire_exercices()`
   ou des SELECT, la clé est `titre`.
4. **Backend `services/referentiel_documents.py`** : ce fichier traîne
   dans la sandbox mais n'est pas chez toi. À nettoyer si tu veux
   éviter de futures confusions.

## Prochaine étape (chantier D)

Suite logique : suppression du sélecteur d'objectif fiche (« le bloc
gros et redondant en mode édition disparaît »). Question ouverte :
**comment crée-t-on une fiche désormais** ? Workflow à scoper en
session dédiée. Pistes :
- Sous-mode « nouvelle fiche » avec un mini-sélecteur léger
- Création depuis l'atelier d'assemblage (drag-and-drop d'un objectif
  vers une zone « créer fiche »)
- Autre proposition

## Style de la livraison

- ZIP unique, MD5 vérifiables via `verifier_md5.py`
- 0 régression pytest (sur les tests qui passaient avant)
- Migration BDD testée idempotente sur la BDD réelle
- Tous les fichiers backend Python sont sanity-checkés par `ast.parse`
- Tous les fichiers JS sont sanity-checkés par `node -c`
