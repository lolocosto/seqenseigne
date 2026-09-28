# Redémarrage v0.20.3 — EdT : rendu des cases (couleur, groupe, libellé)

Trois ajustements d'affichage des cases de l'emploi du temps. Purement visuel
(un seul fichier, `static/edt.js`).

## Changements

1. **Couleur grise dès que ce n'est pas un cours.** Une case dont l'usage
   n'est pas `cours` (vie de classe, co-animation, autre) s'affiche en gris,
   quelle que soit la classe. Un cours (y compris en groupe) garde la couleur de
   sa classe.

2. **Groupe affiché dans la case** quand ce n'est pas la classe entière — sauf
   le groupe `autre`, qui est déjà précisé par le libellé. Ex. un cours en
   « Groupe (horaire ordinaire) » affiche le nom de la classe puis le groupe.

3. **Libellé affiché** dès qu'il est saisi (ex. « CEC », « Concertation Maths »,
   « Co-animation 6E7 Mme Chemin »).

Le contenu d'une case est désormais multi-lignes : nom de classe (en gras) /
groupe (si pertinent) / libellé (si saisi). L'opacité du « non compté » est
adoucie (la couleur grise porte déjà l'information).

## Exemples de rendu

| Case | Affichage | Couleur |
|------|-----------|---------|
| 4e3, classe entière, cours | 4e3 | couleur classe |
| 4e3, groupe horaire ordinaire, cours, « CEC » | 4e3 / Groupe (horaire ordinaire) / CEC | couleur classe |
| 4e3, classe entière, vie de classe | 4e3 / Vie de classe | gris |
| autre, co-animation, « Co-animation 6E7 Mme Chemin » | Co-animation 6E7 Mme Chemin | gris |
| 4e3, classe entière, autre, « Concertation Maths » | 4e3 / Concertation Maths | gris |

## Fichiers

- `static/edt.js` : `_edtLibelleCase` (retourne des lignes : classe / groupe /
  libellé), nouveau `_edtCouleurCase` (gris hors cours), `sousCase` adaptée.

## Tests

- vitest : 187 passed (0 régression). Syntaxe edt.js OK.
- Logique de rendu vérifiée sur les cas réels (cours, groupe, vie de classe,
  co-animation, concertation).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement front (un fichier).

## Suite

- v0.21.x : utilisation des automatismes (ordonnancement Leitner).
