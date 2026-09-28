# Patch v0.12.1.2 — corrections post-déploiement v0.12.1.1

Deux fixes suite au déploiement de v0.12.1.1 chez Laurent.

## 1. Bug : cycle 3 affiché en 5ème, 4ème et 3ème

**Symptôme reporté** : « le PDF du livret des plans de travail affiche
les séquences cycle 3 (Nombres entiers, Fractions, Calcul mental…) en
N10/N12 alors qu'on est au cycle 4 ». Pas de duplication (le fix
v0.12.1.1 a bien tenu) mais cycle complètement faux.

**Cause** : la v0.12.1.1 a fixé `_lire_sequences_du_niveau` mais a
laissé intact son jumeau caché `_cycle_du_niveau`, qui souffrait
*exactement du même bug* :

```sql
SELECT DISTINCT sdc.cycle_code
FROM sequences_par_niveau spn
JOIN sequences_du_cycle sdc ON spn.sequence_code = sdc.code
WHERE spn.niveau = ?
LIMIT 1
```

Quand le code de séquence (ex. `S01`) existe à la fois dans la table
`sequences_du_cycle` pour C03 et pour C04, la jointure ramène deux
lignes. Le `LIMIT 1` en ramasse une selon l'ordre interne SQLite — en
pratique C03 par ordre alphabétique d'index. Du coup le `cycle_code`
passé ensuite à `_lire_sequences_du_niveau` est faux, mais celui-ci
filtre proprement et remonte 14 séquences C03. Pas de duplication, mais
le mauvais cycle. Reproduit sur la BDD de Laurent : `N10` →
`_cycle_du_niveau()` retourne `C03`.

**Fix** : remplacement de la jointure SQL par un mapping en dur
`_CYCLE_PAR_NIVEAU`, calqué sur le pattern déjà en place dans
`services/livret_sequence.py:578` (avec note « à remplacer par BDD en
v0.13 (référentiel de niveau) »). Ça aligne les deux services et
supprime toute ambiguïté possible. Source de vérité :
`data/param_niveaux.csv`.

**Test de régression** : `TestCycleDuNiveau::test_pas_de_confusion_cycle3_cycle4`
crée explicitement un schéma avec C03+C04 partageant le code S01 et
vérifie que `_cycle_du_niveau('N10')` retourne bien C04 quel que soit le
contenu de la BDD. Quatre tests supplémentaires (`test_n09_renvoie_c03`,
`test_n11_renvoie_c04`, `test_n12_renvoie_c04`) couvrent l'ensemble du
mapping.

## 2. Comportement : bouton « Compiler le plan de travail » au scope séquence

**Inversion de comportement assumée** (pas un bug du code livré, mais
une réinterprétation de l'intention initiale).

La v0.12.1.1 avait fait du bouton « Compiler le plan de travail » dans
l'atelier d'assemblage de séquence un raccourci vers le **livret
annuel du niveau** (toutes les séquences, ~19 pages). À l'usage, ça
ne correspond pas à ce qu'on veut là : depuis l'atelier d'une
séquence, le bouton naturel est de produire le plan de travail **de
cette séquence uniquement** (1 page par partie de la séquence).

Le livret annuel reste accessible par son emplacement attendu :
l'atelier « Plans de travail » de la portée Niveau, qui n'est pas
modifié.

### Modèle de service

Nouvelle fonction `generer_plan_de_travail_sequence(conn, niveau,
sequence_code)` dans `services/livret_plans_de_travail.py`. Elle
réutilise toute la machinerie existante (préambule construit via
`construire_preambule`, helpers `_lire_parties_de_sequence`,
`_lire_objectifs_de_partie`, `_emettre_page_partie`) mais :

- ne génère **pas** de page de titre (calqué sur `livret_sequence.py`)
- émet une seule séquence (filtrée par `sequence_code`)
- positionne `\seqSetCodeSequence{<sequence_code>}` correctement (vs
  `S00` pour le livret niveau, qui est un agrégat sans séquence
  particulière)

Lève `SequenceParNiveauIntrouvable` (nouvelle classe d'exception, dérivée
de `LookupError`) dans deux cas :
- couple `(niveau, sequence_code)` absent de `sequences_par_niveau`
- séquence-niveau présente mais sans aucune partie assemblée

Cette exception est mappée en HTTP 404 par les routes (vs 500 pour
les autres erreurs). Elle expose les attributs `niveau`,
`sequence_code`, `motif` pour permettre au front de produire un
message utile.

### Routes HTTP

Deux nouvelles routes dans `routes/plans_de_travail.py`, calquées sur
les routes niveau existantes :

- `GET  /api/plans-de-travail/<niveau>/<sequence_code>/tex`
- `POST/GET /api/plans-de-travail/<niveau>/<sequence_code>/pdf`

Codes :
- 200 : tex / pdf
- 400 : niveau invalide (hors N09–N12)
- 404 : `sequence_par_niveau_introuvable` (avec `niveau`, `sequence_code`, `motif`)
- 422 : compilation LaTeX échouée
- 500 : erreur de génération du .tex
- 503 : pdflatex introuvable / timeout

Les routes niveau (`/api/plans-de-travail/<niveau>/{tex,pdf}`) restent
inchangées et continuent de produire le livret annuel agrégé.

### UI

Deux modifications dans `static/atelier_seqniv_assemblage.js` :

- Le tooltip du bouton « Compiler le plan de travail » est mis à jour
  pour refléter le nouveau comportement (« compile le plan de travail
  de cette séquence (une page par partie de la séquence) »).
- Le handler `livretSeqCompilerPlanTravail` appelle désormais l'URL
  scope séquence `/api/plans-de-travail/{niveau}/{sequence_code}/pdf`
  au lieu de l'URL scope niveau.

L'iframe d'affichage est partagée avec le livret de séquence (un seul
PDF visible à la fois, le plus récent écrase le précédent) — pas de
changement.

L'atelier « Plans de travail » de la portée Niveau (fichier
`static/atelier_plansdetravail.js`) n'est pas touché : son bouton
continue d'appeler l'URL scope niveau et produit le livret annuel.

## Tests

**Total : 1888 tests** (vs 1872 baseline v0.12.1.1) → **+16 tests v0.12.1.2**.

Détail des ajouts dans `tests/test_v0_12_1_livret_plans_de_travail.py` :

- `TestCycleDuNiveau` (+4 tests) : `test_n09_renvoie_c03`,
  `test_n11_renvoie_c04`, `test_n12_renvoie_c04`,
  `test_pas_de_confusion_cycle3_cycle4` (régression v0.12.1.2)
- `TestGenerationScopeSequence` (+5 tests) : structure du .tex pour 1
  partie / 2 parties, absence de page de titre, `seqSetCodeSequence`
  et `seqSetCodeNiveau` corrects
- `TestErreursScopeSequence` (+3 tests) : niveau inconnu →
  `LookupError`, séquence inconnue → `SequenceParNiveauIntrouvable`,
  séquence sans partie → `SequenceParNiveauIntrouvable` avec motif
- `TestRouteScopeSequence` (+4 tests) : 400 niveau invalide (tex et
  pdf), 404 séquence inconnue (tex et pdf)

Validation manuelle bout-en-bout sur la BDD réelle :
`generer_plan_de_travail_sequence(conn, 'N10', 'S12')` produit un
.tex avec 3 pages partie correctement intitulées « Géométrie plane
(1ère partie) », « (2e partie) », « (3e partie) ».

Pas de validation pdflatex automatisée (besoin de TeXLive complet),
à valider sur poste après déploiement.

## Fichiers touchés

```
services/livret_plans_de_travail.py        (~150 lignes :
                                              - _cycle_du_niveau remplacé
                                                par mapping _CYCLE_PAR_NIVEAU
                                              - nouvelle classe
                                                SequenceParNiveauIntrouvable
                                              - nouvelle fonction
                                                generer_plan_de_travail_sequence)
routes/plans_de_travail.py                 (~135 lignes :
                                              - 2 nouvelles routes scope séquence
                                              - mise à jour de la docstring)
static/atelier_seqniv_assemblage.js        (~6 lignes :
                                              - URL et tooltip du bouton)
tests/test_v0_12_1_livret_plans_de_travail.py
                                           (~155 lignes :
                                              - 4 tests cycle additionnels
                                              - 12 tests scope séquence)
doc/redemarrage_v0_12_1_2.md               (NOUVEAU)
```

Aucune migration BDD nécessaire.

## Procédure de déploiement

1. Décompresser le ZIP par-dessus la v0.12.1.1 actuellement déployée.
2. Relancer l'application — démarrage immédiat (pas de migration).
3. Tests à effectuer côté UI :

   **Point 1 (cycle correct)** :
   - Aller dans la portée Niveau, atelier « Plans de travail », N10
   - Cliquer « Voir le LaTeX » : vérifier que les noms de séquences
     sont ceux du cycle 4 (« Représentations d'un nombre »,
     « Comparaison de nombres », etc.) et **pas** ceux du cycle 3
     (« Nombres entiers », etc.)
   - Cliquer « Générer le PDF » : vérifier le rendu visuel
   - Refaire la vérification en N12

   **Point 2 (scope séquence)** :
   - Aller dans la portée Séquence, atelier d'assemblage, N10/S12
     (séquence à 3 parties)
   - Onglet « Rendu PDF » → bouton « Compiler le plan de travail »
   - Vérifier : le PDF a 3 pages (une par partie), pas de page de
     titre, premier titre = « Géométrie plane (1ère partie) »
   - Tester sur une séquence à 1 seule partie (ex. N10/S01) : le
     PDF doit avoir 1 page

4. Pour les tests pytest : `python -m pytest tests/` (1888 tests
   attendus, ~2m35).

## Points de validation côté Laurent

- **Compilation pdflatex bout-en-bout sur MiKTeX** du nouveau format
  (plan de travail scope séquence) — la machinerie LaTeX est
  strictement la même que pour le livret niveau (préambule identique,
  seul le contenu de `\begin{document}` change), donc une compilation
  qui marche pour le livret niveau marchera ici aussi
- **Cohérence des numéros de pages dans les renvois éventuels** —
  vérifier qu'aucune référence interne (`\pageref`) ne se casse au
  scope réduit (le modèle ne semble pas en utiliser, mais à vérifier
  visuellement)
- **Cas dégénérés non testés en automatique** : séquence à 4+ parties,
  séquence sans aucun objectif. Le service est censé gérer
  proprement, mais le rendu visuel est à confirmer

## Prochaine étape

v0.12.2 — **Harmonisation visuelle des sidebars** (chantier 3/5) :
chip objectif fiche, recouvrement titre, design system unifié pour
les sidebars notion / méthode / exercice / fiche.
