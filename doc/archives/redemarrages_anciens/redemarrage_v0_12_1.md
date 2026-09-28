# Redémarrage seqenseigne — v0.12.1 (chantier 2/5 de la série v0.12)

## Synthèse

**Livret annuel des plans de travail (portée Niveau)** + 3 ajustements UI
v0.12.0.

Cette livraison contient **deux blocs distincts** :

1. **Ajustements UI v0.12.0** (3 corrections demandées après déploiement
   du chantier 1)
2. **Génération du livret annuel des plans de travail** (chantier 2 du
   plan v0.12)

## Bloc 1 — Ajustements UI v0.12.0

### `s.` → `séance(s)` (3 emplacements)

Le suffixe d'unité dans les inputs des bandeaux partie + objectif fermé
+ objectif ouvert passe de l'abréviation `s.` au libellé complet
`séance(s)`. Plus explicite à la lecture, en particulier pour l'élève
qui consulte un PDF avec ces valeurs.

Modification : trois `<span class="asm-seances-unite">` dans
`static/atelier_seqniv_assemblage.js`.

### Total partie « total : N séance(s) » à côté du titre

Affichage en lecture seule du total des séances prévues pour la partie,
calculé comme `nb_seances_R_AE` + Σ `nb_seances` des objectifs (cours +
exos confondus) — même formule que pour le `seancesTotal` du livret
LaTeX, donc cohérence garantie entre l'UI et le PDF généré.

Placement : juste à côté de « Partie N » dans le titre du bandeau de
partie (option C de la consultation). Affiché uniquement si total > 0
(évite le bruit visuel quand rien n'est saisi).

Recalcul : à chaque rendu **et** à chaque saisie d'un input séances
(partie ou objectif). Le rafraîchissement cible le DOM (`querySelector`
+ `textContent`) plutôt que de re-rendre la partie complète, ce qui
préserverait sinon le focus dans l'input que l'utilisateur vient de
quitter (perte de focus = mauvais UX au tab/blur).

Style discret : `font-size: var(--font-xs)`, badge avec fond `--surface`
et bordure `--border-light`, `font-variant-numeric: tabular-nums` pour
les chiffres alignés.

### Objectifs « cours » : résumé toujours vide

Pour les objectifs « cours » (codes 01/11/21), le résumé du bandeau
fermé est désormais toujours vide. La règle « N exo(s) · méthode : X »
ne s'applique plus à ces objectifs (option B de la consultation : par
construction ils n'ont pas d'exos rattachés et leur méthode liée
éventuelle n'est pas pertinente dans le bandeau).

Pour les autres objectifs (code 02 et plus), comportement inchangé.

## Bloc 2 — Livret annuel des plans de travail

### Format de sortie

A4 portrait standard (`a4paper, 11pt`), marges modérées
(`vmargin=25pt, hmargin=20pt`). L'enseignant choisit le mode
d'impression à la sortie (1 page par feuille pour l'usage standard, ou
mode brochure A5 du pilote d'imprimante pour la version pliée-agrafée).

Le livret est composé de :

- **Page de titre minimaliste** : « Plans de travail » + nom de niveau
  (« Classe de 5ᵉ » etc.) + 3 lignes Année/Établissement/Classe à
  `\ldots` que l'élève complète à la rentrée
- **Une page par (séquence-niveau, partie)** : si une séquence a
  plusieurs parties, chacune produit sa propre page

### Structure d'une page de plan

Chaque page d'une (séquence, partie) contient :

1. `\seqBoiteTitrePlan[titre={<nom de la séquence>(suffixe partie)}]` —
   boîte d'en-tête avec le nom (résolu depuis la BDD) et
   éventuellement le suffixe « (1ᵉʳᵉ partie) », « (2ᵉ partie) »…
2. **Bloc 2-colonnes Repères temporels / Niveaux atteints** :
   - Colonne 1 : Dates (à compléter à la main), Travail en classe
     (calculé), puis liste détaillée Révisions / Cours / Objectif XX
     avec leurs nombres de séances
   - Colonne 2 : un item par objectif avec un niveau de maîtrise à
     compléter (`\ldots`), et la « Note équivalente: \ldots/20 »
3. **Bloc « Révisions et découverte »** (renommé v0.12.1) avec deux
   lignes :
   - `Révisions: <numéros des exos R, ou ->`
   - `Découverte: <numéros des exos EA, ou ->`
4. **Pour chaque objectif d'exo** (codes ≠ 01/11/21) : une boîte avec
   le nom de l'objectif, la liste des notions liées (résolues depuis
   la BDD via `objectif_notions → notions.titre`), et les listes des
   exos par série F / A / E (numéros d'ordre dans l'objectif)

### Choix architectural important : indépendance vis-à-vis de `\seqLoadData`

Le tex de référence de Laurent (`N10_Plan_de_travail.tex`) utilise
`\seqLoadData` pour charger les fichiers `.dbtex` archivés et invoque
ensuite `\seqConnaissanceGetNom`, `\seqObjectifGetNom`,
`\seqSequenceGetNom`, `\seqPlanReperesNiveaux`, `\seqPlanObjectif` qui
parcourent ces bases CSV.

**Le livret v0.12.1 NE FAIT PAS** d'appel à `\seqLoadData` ni aux
macros qui en dépendent. Justification :

- Cohérence avec le principe « BDD = source de vérité » : les `.dbtex`
  sont des archives historiques qui peuvent diverger de l'état BDD
  courant si l'enseignant a édité ses objectifs/notions
- Cohérence avec `livret_sequence.py` (qui n'utilise pas non plus
  `\seqLoadData`)
- Compatibilité automatique avec les modifs futures (renommage,
  réordonnancement) sans devoir régénérer les `.dbtex`

À la place, **toutes les résolutions sont faites côté Python** :
- noms de séquences, de notions, d'objectifs : lus depuis BDD
- bloc « Repères temporels / Niveaux atteints » : réimplémenté en
  LaTeX direct (utilise les environnements `blocReperesNiveaux`,
  `seqColItem`, `multicols`, `boitePaleNoBreak` qui sont autonomes,
  pas la macro `\seqPlanReperesNiveaux` qui parcourt les bases)
- bloc « plan d'objectif » : émission directe (pas via
  `\seqPlanObjectif` qui appelle `\seqObjectifGetNom`)

Le seul appel macro paquet conservé est `\seqBoiteTitrePlan` parce
qu'il prend son titre en paramètre (résolu Python) — sa machinerie
interne `boiteTitreGen` est cosmétique et n'interroge pas les bases.

### Préambule LaTeX sur mesure

Construit via `services.preambule_atome.construire_preambule` avec une
graine spécifique au livret (cf. `_MACROS_LIVRET` et
`_ENVIRONNEMENTS_LIVRET` dans `services/livret_plans_de_travail.py`).
La fermeture transitive tire toutes les dépendances nécessaires depuis
`paquet_definitions`.

Particularité : `\seqBoiteTitrePlan` a le statut `'ignore'` dans
`paquet_definitions` (filtrée par défaut pour les rendus d'atomes
isolés). Le service la **ré-inline manuellement** après le préambule
principal, encadrée par `\makeatletter…\makeatother` — sans cela les
macros `\cmdseq@boiteTitrePlan@*` (créées par `\define@cmdkey`) ne
seraient pas accessibles depuis le corps de la macro.

### Bug technique résolu : virgules dans titre tcolorbox

`tcolorbox` parse l'argument `title=#1` comme une **liste de clés**
`key=value` séparées par virgules. Quand le titre d'une boîte contient
une virgule (ex. nom d'objectif « Pour les nombres décimaux, passer de
l'écriture… »), la virgule est interprétée comme séparateur de clé →
erreur cryptique « Incomplete \\iffalse ».

**Fix** : encadrer le titre par une **paire d'accolades supplémentaire**
`{{...}}` au lieu de `{...}`. Cela force tcolorbox à traiter le contenu
comme un seul argument littéral.

Appliqué dans `_emettre_objectif_exo` (titre de la boîte d'objectif) et
`_emettre_bloc_revisions` (titre « Révisions et découverte »).

### Échappement des contenus utilisateur

`_echapper_texte` est désormais l'identité (`return s or ''`). Les noms
saisis par l'enseignant peuvent contenir du **LaTeX intentionnel** :
`\mbox{$a^2-b^2$}`, `\og`, `\ieme`, etc. Un échappement aveugle
(remplacer `$` par `\$`) casse ces saisies légitimes.

Choix cohérent avec `livret_recap_cours.py` (même politique) et avec
le contrat des autres ateliers : la BDD stocke le texte tel que saisi,
charge à l'enseignant de produire un LaTeX valide à la saisie.

### API HTTP

Deux nouvelles routes :

- `GET /api/plans-de-travail/<niveau>/tex` — renvoie le source .tex
  (debug / inspection)
- `POST/GET /api/plans-de-travail/<niveau>/pdf` — compile et renvoie le
  PDF

Codes :
- 200 + .tex / application/pdf
- 400 niveau invalide (hors N09–N12)
- 422 erreur de compilation LaTeX (avec détail des erreurs et log
  complet pour diagnostic)
- 500 erreur de génération du .tex
- 503 pdflatex introuvable / timeout

Réutilise le cache de compilation (`compiler_atome` avec hash sha256
de la source) — les régénérations à contenu identique sont
instantanées.

### UI

L'atelier « Plans de travail » est intégré dans la portée **Niveau**,
à côté de « Récap cours » et « Récap exos ». Pattern UI strictement
calqué sur l'atelier Récap cours :

- bandeau d'en-tête avec libellé du niveau actif (mémorisé en portée
  via `ATL_FILTRE_NIVEAU`)
- 2 boutons : « Voir le LaTeX » (affichage `<pre>`) et « Générer le
  PDF » (iframe)
- gestion empty/loader/erreur identique
- en cas d'échec de compilation, le log complet est dépliable et
  téléchargeable en .log pour diagnostic

Fichiers UI :
- `templates/index.html` : panneau `atl-plantravail` (qui était déjà
  un placeholder « à venir » — remplacé par le panneau complet)
- `static/atelier_plansdetravail.js` : init + handlers (calque
  `atelier_recapcours.js`)
- `static/app.js::ATL_INITS` : ajout de `plantravail: 'plansdetravailInit'`

Le bouton de l'onglet existait déjà côté HTML (hérité d'une session
antérieure de cadrage).

## Tests

**Total : 1871 tests** (vs 1821 baseline v0.12.0) → **+50 tests v0.12.1**.

Nouveau fichier `tests/test_v0_12_1_livret_plans_de_travail.py` (50
tests organisés en 4 sections) :

1. **Lecture BDD** (12 tests) : `_cycle_du_niveau`, `_lire_sequences_du_niveau`,
   `_lire_parties_de_sequence`, `_lire_objectifs_de_partie` — vérifie
   l'ordonnancement, la résolution des notions, les exos par série
2. **Calculs et formatage** (16 tests) : `_calculer_total_partie`,
   `_est_objectif_cours`, `_fmt_seances`, `_fmt_liste_exos`,
   `_suffixe_partie`
3. **Émission des blocs LaTeX** (17 tests) : `_emettre_bloc_revisions`
   (renommage « Révisions et découverte », deux lignes R / EA, double
   accolades sur le titre), `_emettre_objectif_exo` (double accolades,
   notions, listes F/A/E, préservation du LaTeX intentionnel),
   `_emettre_bloc_reperes` (calcul du total, niveaux atteints),
   `_emettre_page_titre` (libellé niveau, `\ldots` pour
   année/établissement/classe)
4. **Routes HTTP** (5 tests) : validation niveau invalide, format
   réponse `tex`, gestion d'erreur

Validation manuelle compilation pdflatex : N10/N11/N12 produisent
respectivement 41/41/37 pages PDF en environnement TeX Live 2023. Pas
de test pdflatex automatisé (besoin de TeX Live complet).

## Fichiers touchés

```
services/livret_plans_de_travail.py                (NOUVEAU — ~620 lignes)
routes/plans_de_travail.py                         (NOUVEAU — ~165 lignes)
app.py                                             (+2 lignes : import + register)

static/atelier_plansdetravail.js                   (NOUVEAU — ~210 lignes)
static/app.js                                      (+1 ligne : ATL_INITS)
templates/index.html                               (~50 lignes : remplacement
                                                     placeholder + 1 include JS)

static/atelier_seqniv_assemblage.js                (~80 lignes : 3 ajustements UI
                                                     + helper _calculerTotalSeancesPartie
                                                     + _rafraichirTotalPartie)
static/app.css                                     (+15 lignes : .asm-partie-total)

tests/test_v0_12_1_livret_plans_de_travail.py      (NOUVEAU — 50 tests, ~410 lignes)
doc/redemarrage_v0_12_1.md                         (NOUVEAU)
```

Aucune migration BDD nécessaire : la v0.12.0 a déjà ajouté les colonnes
`nb_seances_R_AE` et `nb_seances` qui sont consommées ici.

## Procédure de déploiement

1. Décompresser le ZIP par-dessus `appli/` (au-dessus de la version
   v0.12.0 actuellement déployée).
2. Relancer l'application — pas de migration de schéma, démarrage
   immédiat.
3. Tester côté UI :
   - Ouvrir un atelier d'assemblage de séquence-niveau (portée
     Séquence, atelier Séquence) : vérifier que `s.` est devenu
     `séance(s)` dans les inputs, que le total partie s'affiche en
     temps réel à côté du titre, et que les objectifs « Cours » ont
     un résumé vide
   - Saisir quelques `nb_seances` sur N10/S01 : vérifier que le total
     se met à jour sans perte de focus
   - Aller dans la portée Niveau, atelier « Plans de travail » :
     cliquer « Voir le LaTeX » puis « Générer le PDF » sur N10
4. Pour le test pytest : `python -m pytest tests/` (1871 tests
   attendus, ~2m20).

## Points de validation côté Laurent

- **Compilation pdflatex bout-en-bout** : la compilation manuelle a
  réussi sur N10 (41 pages), N11 (41 pages), N12 (37 pages) sur
  TeX Live 2023. À valider sur MiKTeX Portable côté poste.
- **Rendu visuel** : vérifier que les couleurs de thème sont bien
  appliquées (chaque page séquence a la couleur de son thème),
  que les boîtes ne débordent pas, que les longues listes d'exos ne
  cassent pas la mise en page.
- **Fidélité au PDF de référence** : le livret v0.12.1 ne contient
  PAS le préambule statique du PDF de référence (programme du cycle,
  progression annuelle, matériel pédagogique, évaluation). Si Laurent
  veut les conserver, il les ajoute manuellement à la sortie ou
  imprime un PDF en plus.

## Prochaine étape

v0.12.2 — **Harmonisation visuelle des sidebars** (chantier 3/5) :
chip objectif fiche, recouvrement titre, design system unifié pour
les sidebars notion / méthode / exercice / fiche.
