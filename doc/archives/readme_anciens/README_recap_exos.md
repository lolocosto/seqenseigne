# Atelier Récap exos — v0.10

## Fichiers

### Nouveaux
- `services/livret_recap_exos.py` (~370 lignes) — génération du .tex agrégé
- `routes/recap_exos.py` (~150 lignes) — routes Flask `/api/recap-exos/<niveau>/{tex,pdf}`
- `static/atelier_recapexos.js` (~210 lignes) — UI atelier (calque exact de atelier_recapcours.js)

### Modifiés
- `app.py` — import + register du blueprint `bp_recap_exos`
- `static/app.js` — ajout `'recapexos': 'recapexosInit'` dans `ATL_INITS`
- `templates/index.html` — placeholder remplacé par un vrai panel + ajout du `<script>`

## Architecture

Calque livret_recap_cours pour la structure et l'orchestration. La spécificité
des exos est gérée dans `_generer_corps_exercice_continu`, qui produit un bloc
`\begin{seqExercice}…\end{seqExercice}` sans les `\seqInitCorriges`,
`\seqAfficheCorriges`, `\begin{seqSerieExos}` (qui sont posés une seule fois
au niveau de l'orchestrateur).

## Hack option 2 (validé)

Pour éviter les collisions de fichiers `Corriges/c<SerieExosNum>e<ExoNum>.tex`
entre plusieurs séquences ayant chacune une « série fondamentale » (toutes
avec `SerieExosNum=1`), on injecte juste après chaque `\begin{seqSerieExos}{X}`
un `\setcounter{SerieExosNum}{<unique>}` (101, 102, 103…). Ainsi :
- le titre « Série fondamentale/avancée/exploration » est figé sur la base de X
  (1/2/3) avant qu'on touche au compteur ;
- les fichiers physiques `Corriges/cNeM.tex` sont uniques ;
- les labels `exo:N-M` sont uniques.

Le label `corrigeExos<X>` du paquet sera en doublon entre séquences (warning
LaTeX, pas une erreur). On n'utilise pas la `pageref{corrigeExos<X>}` du
paquet (on a notre propre structure de corrigés en fin de livret).

## Mapping séries

| Code BDD | Numéro paquet | Affichage |
|---|---|---|
| `AE` | 0 | Activités d'approche (sémantiquement = révisions) |
| `F`  | 1 | Série fondamentale |
| `A`  | 2 | Série avancée |
| `E`  | 3 | Série exploration |

Les AE n'existent que pour 4 séquences en N10 (S03, S04, S12, S14).

## Corrigés non rédigés

Pour chaque exo sans corrigé en BDD (par exemple S14/E2 PGCD aujourd'hui), on
émet `\seqCorrige{\emph{Corrigé non rédigé.}}`. Sinon le paquet écrirait un
`\input{Corriges/cNeM.tex}` vers un fichier inexistant → erreur fatale.

## Validation

Génération .tex testée pour N10, N11, N12 :
- N10 : 242 exos, 46 séries (4 AE + 14 F + 14 A + 14 E)
- N11 : 281 exos
- N12 : 279 exos, 42 séries (14 × 3, pas d'AE)

Tous les `\setcounter{SerieExosNum}{N}` ont des valeurs distinctes.
1434 tests existants passent.

## À faire de ton côté

1. Remplace les fichiers ci-dessus dans ton arborescence
2. Ctrl+F5 dans le navigateur (cache .js)
3. Ouvre l'app, sélectionne portée Niveau, choisis un niveau, va dans l'onglet
   « Récap exos », clique « Voir le LaTeX » d'abord pour vérifier la structure
4. Puis « Générer le PDF » pour le vrai test de compilation MiKTeX
5. Si erreur de compilation : utilise le bouton « Télécharger le log .log »
   et envoie-moi le log

Si MiKTeX se plaint des warnings de doublons de label (corrigeExos1, 2, 3),
c'est attendu et bénin (on en a discuté pendant la conception).
