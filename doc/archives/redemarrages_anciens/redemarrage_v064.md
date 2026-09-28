# Doc de redémarrage — seqenseigne v0.6.4

> Document à fournir en tête de la prochaine session pour reprendre le contexte.

## Ce qu'est seqenseigne

Application Flask de gestion pédagogique pour Laurent, professeur de
mathématiques au collège. Génère et gère :
- Livrets de séquence (`livrets_de_sequence/`)
- Plans de travail annuels (`documents_annuels/`)
- Livrets d'exercices et fiches de résumé
- 3 niveaux : N10 (5e), N11 (4e), N12 (3e), avec 14 séquences chacun

Stack : Python/Flask, SQLite, JavaScript vanilla, LaTeX (paquet
`seqenseigne` maintenu en `.dtx`).

Forge : `forge.apps.education.fr/laurentcoste/seqenseigne`

Structure principale :
- `Enseignement_new/seqenseigne/` — sources `.dtx` du paquet LaTeX
- `Enseignement_new/sequences/N1[012]/{livrets_de_sequence,documents_annuels}/`
- `Enseignement_new/2025-2026/Collège Les Hautes Ourmes/` — classes
- `Enseignement_new/appli/` — l'application Flask de pilotage

## État actuel — v0.6.4 déployée et validée

### Cycle 1 — Performance compilation (déployé)
Préambule sur mesure remplaçant `\usepackage{seqenseigne}` complet :
271 → 46-67 définitions, 110 → 25-29 paquets. Compilation < 3s par atome.

### Cycle 2 — Migration fin_cycle / notions vers objectifs (déployé)
- `fin_cycle` est désormais une caractéristique d'OBJECTIF, plus de méthode
- Schéma : `objectifs_v2.fin_cycle` + table `objectif_notions`
- Onglet « Objectif/critères » de l'atelier méthode supprimé
- Édition côté seqniv (case fin_cycle + tags notions par objectif)
- Champ `fin_cycle` retiré de la dataclass Atome (méthode)

### Cycle 3 — UX ateliers (déployé)
- Modale LaTeX (Ctrl+L) qui remplace l'onglet « LaTeX généré »
- Autosize automatique des textareas
- Mode split édition+rendu côte-à-côte (toggle dans Préférences)
- Module `static/atelier_commun.js`

### Cycle 4 — Sections universelles + Mise en forme en BDD (déployé)
**Modèle de sections d'atomes refondu.** Avant : 2 catégories fixes
(`exemples`, `remarques`) + toggle binaire de permutation. Après :
**modèle universel à 2 niveaux** où chaque atome a une liste ordonnée de
sections, chacune avec un titre libre (vocabulaire normalisé extensible)
et une liste d'items LaTeX brut.

Schéma SQL : `items_texte` → `atome_sections` + `atome_section_items`.

Vocabulaire normalisé recommandé (datalist HTML5 dans l'UI atelier) :
- Pluriel canonique : Exemples, Remarques, Conséquences, Propriétés
- Singulier canonique : Démonstration (et apparentés : « Démonstration de
  la réciproque », « Démonstration de la contraposée », gardés tels quels)
- Titres exotiques (« Équivalence entre la première définition et la
  deuxième définition », etc.) préservés à l'identique

Bugs corrigés :
- `\underline{...}` du **corps** des méthodes (sous-titres internes des
  méthodes complexes type « Comparer deux fractions ») n'est plus
  confondu avec un séparateur de section top-level. Le scan démarre
  désormais APRÈS la fermeture du 2e argument de `seqMethode/seqNotion`
  via le helper `_skip_balanced` qui équilibre les accolades.
- Sous-listes imbriquées (Notion 4 « Nombre décimal » avec sa
  hiérarchie) : les `\item` à l'intérieur d'un `seqColItem` imbriqué
  restent dans le LaTeX brut de l'item parent au lieu de remonter au
  top-level.

UI ateliers Notion + Méthode : zone Sections dynamique avec datalist
HTML5, boutons ⬆⬇ pour réordonner sections et items, bouton ✕ avec
confirm pour supprimer. Combobox accepte titres libres.

API breaking change : `/api/notions` et `/api/methodes` renvoient
`sections: [{titre, items: [...]}]` au lieu de
`exemples`/`remarques`/`ordreExRem`. Pas de rétrocompatibilité (alpha).

UX rapides additionnels :
- Hauteur fixe toolbar (`min-height: 48px`, titre tronqué en ellipsis)
- Splitters cliquer-tirer : aside↔main (toujours actif) et form↔rendu
  (mode split). Persistance localStorage par écran. 4 écrans : 3
  ateliers + seqniv. Bornes 200/300 px.
- Sauvegarde auto avant compilation (déclenchée par bouton « Compiler »)
- Fix scrollbar absent en mode split (passage en `display: grid` avec
  `min-height: 0`)

Mise en forme LaTeX en BDD de référence :
- Renommage « Atomes pédagogiques » → « Référence » dans Administration
- Nouvelle carte « Mise en forme » : totaux par catégorie + détail
  dépliable
- Nouveau bouton « Vider la mise en forme LaTeX »
- Nouveau sous-onglet « Import mise en forme » (chemin par défaut
  `../reference/paquet`)
- Routes : `POST /api/admin/reset/paquet`, `POST /api/admin/paquet/import`

### Patch correctif post-déploiement

Bug du splitter : zone hit-testing de la poignée débordait de 3px sur
sidebar et main via un pseudo-élément `::before` mal calibré. Tous les
clics près du splitter étaient interceptés. Corrigé : suppression du
`::before`, poignée passe de 4px à 6px de large.

### Tests
6 fichiers `tests/test_*.py` qui utilisaient l'ancien schéma
`items_texte` ont été marqués `pytest.skip(allow_module_level=True)`.
À adapter au nouveau schéma. Test fonctionnel manuel validé sur tout le
corpus : 142 notions + 156 méthodes → 473 sections, 0 erreur.

## Architecture des fichiers clés

```
appli/
├── app.py                              — entry point Flask
├── persistence/
│   ├── schema.sql                      — atome_sections + atome_section_items
│   └── sqlite_store.py                 — _lire_sections / _ecrire_sections
├── scanner_latex.py                    — parseur, modèle universel à 2 niveaux
├── services/
│   ├── atomes.py                       — CRUD avec champ `sections`
│   ├── latex_rendu_atome.py            — dataclass Atome.sections, _rendu_sections
│   ├── admin.py                        — statut_bdd avec breakdown paquet
│   └── paquet_parseur.py               — parse les .sty
├── routes/
│   └── admin.py                        — routes paquet/reset, paquet/import
├── scripts/
│   └── peuplement_14_paquet_vers_base.py — peuple paquet_definitions
├── static/
│   ├── app.js                          — ATL_NOTION/METHODE_SECTIONS, init splitters
│   ├── atelier_commun.js               — atelierInstallerSplitter[Grid]
│   ├── rendu_atome.js                  — sauvegarde auto avant compilation
│   └── app.css                         — splitters, zone Sections, mode split grid
└── templates/
    └── index.html                      — datalist atl-vocab-sections
```

Schéma BDD pour les sections (essentiel pour comprendre la suite) :

```sql
CREATE TABLE atome_sections (
    id           TEXT PRIMARY KEY,
    entite_type  TEXT NOT NULL,    -- 'notion' | 'methode'
    entite_id    TEXT NOT NULL,
    titre        TEXT NOT NULL,
    ordre        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE atome_section_items (
    id           TEXT PRIMARY KEY,
    section_id   TEXT NOT NULL REFERENCES atome_sections(id) ON DELETE CASCADE,
    ordre        INTEGER NOT NULL DEFAULT 0,
    corps        TEXT NOT NULL DEFAULT ''
);
```

Format JSON d'échange API :
```json
{
  "id": "n-123",
  "titre": "Nombre entier relatif.",
  "corps": "Un entier relatif est...",
  "sections": [
    {"titre": "Conséquences", "items": ["Tous les naturels..."]},
    {"titre": "Remarques",    "items": ["...", "..."]},
    {"titre": "Exemples",     "items": ["..."]}
  ]
}
```

## Décisions architecturales actées

- **Pas de rétrocompatibilité** côté API ni BDD — Laurent vide la base
  quand il veut (alpha).
- **Items** contiennent du LaTeX brut quelconque (sous-listes imbriquées,
  multicols, tikzpicture, etc.) — préservés tels quels par le parseur.
- **Sections multiples** (« Démonstration » + « Démonstration de la
  réciproque ») = sections distinctes, pas fusion.
- **1 seul item** est toujours rendu dans un `seqColItem` (uniformité,
  même pour les conséquences inline).
- **Ordre des sections** dérivé de l'apparition dans le `.tex` à
  l'import, modifiable ensuite via boutons ⬆⬇ (pas de drag-and-drop).
- **Vocabulaire normalisé extensible** : datalist HTML5 + champ libre.
- **Méthodes** ont aussi le système de sections (peu utile en pratique
  mais cohérence).
- **2 Makefile** : `Makefile.win` (PCs école, MiKTeX, 3 passes pdflatex)
  et `Makefile.unix` (latexmk).
- **`@` dans .tex** restreint aux `.dtx` ; wrappers publics requis pour
  toute macro interne exposée.

## Roadmap pour la suite

### Priorité 1 : Migration N11 et N12 (5 sequences chacun, ≈ 10 séquences)

N10 a été migré vers le refactoring du paquet (axes 1/2/3) et fait office
de modèle. Le guide de référence est `synthese_migration_N10.md`. Pour
chaque séquence de N11 et N12, il faut :

1. Adapter les `.tex` de séquence aux nouveaux setters (`\seqSetCodeNiveau`,
   `\seqSetCodeSequence`) à la place des anciens keys (`codeNiveau=`,
   `codeSequence=`).
2. Adapter les annual documents (`plan-de-travail`, etc.) à
   `\seqForeachTheme` / `\seqForeachSequence` / `\seqSetColorsTheme` /
   `\seqFiltreDonnees`.
3. Tester compilation séquence par séquence.
4. Faire le travail de contenu en parallèle :
   - Corriger les exercices sans solution
   - Vérifier la cohérence exercice ↔ objectif pédagogique
   - Harmoniser les fiches de résumé en format fill-in-the-blank
   - Supprimer les fichiers vides

### Priorité 2 : Adapter les tests désactivés

6 fichiers en `pytest.skip` :
- `tests/test_latex_rendu_atome.py`
- `tests/test_peuplement_plans_de_travail.py`
- `tests/test_peuplement_repeupler.py`
- `tests/test_reset_reference_full.py`
- `tests/test_resoudre_macros.py`
- `tests/test_services.py`
- `tests/test_sqlite_store.py`

Tous utilisaient `items_texte` (table supprimée). À refaire avec le
nouveau schéma `atome_sections` + `atome_section_items` et le format
JSON `sections: [...]`.

### Priorité 3 : Bug image N10S01E03

L'exercice N10S01E03 ne compile pas (« image non trouvée »). À
investiguer : est-ce un problème de chemin relatif vs absolu, de cache
de rendu, ou de macro `\includegraphics` mal résolue dans le préambule
sur mesure ?

### Sur la table : Roadmap dyslexie

Mode de rendu dyslexie-friendly à activer à la demande :
- Compilateur : xeLaTeX
- Police : OpenDyslexic
- Format : A3
- LetterSpace = 20, WordSpace = 1.5, baselinestretch = 1.2
- `unicode-math` avec `latinmodern-math.otf`

Configuration à garder commentée dans le `.tex` et activée via une
option de compilation. Pas démarré.

## Comment tester rapidement

Pour valider qu'une nouvelle session a bien repris le contexte :

```bash
cd Enseignement_new/appli
make -s install                    # regénère les .sty depuis .dtx
make -s n10-s01                    # compile la séquence S01 de N10
```

Pour démarrer l'application :
```bash
python3 app.py                     # → http://localhost:5000
```

Pour vérifier la base :
```bash
sqlite3 data/seqenseigne.db "SELECT COUNT(*) FROM atome_sections;"
# devrait retourner ~473 si toutes les séquences sont importées
```

## Conventions de communication

- Laurent préfère **un seul ZIP par livraison** (pas de patches
  successifs sauf bug critique post-déploiement).
- Cadrage rigoureux **avant** de coder : poser les questions
  bloquantes, valider l'archi, puis exécuter.
- Pas de migration de données BDD nécessaire (Laurent vide la base
  quand il veut).
- `make -s` (silent) suffit pour Laurent ; pas besoin de bavardage des
  commandes.
- Style : warm + technique + pas d'emojis sauf petite victoire (🎉).
