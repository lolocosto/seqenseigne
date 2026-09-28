# Redémarrage v0.36.2 — Palette des niveaux unique, alignée sur Pronote

Retour d'usage sur v0.36.1 : le fond des cellules « Très bien » du tableau de
suivi était bleu, alors que le reste de l'appli montre ce niveau en vert foncé.
Demande associée : reprendre pour tous les niveaux les teintes de Pronote.

## Cause

Deux palettes indépendantes coexistaient :
- les badges (§20 de `app.css`, variables `--niv-<code>-bg/text`) ;
- les fonds de cellule ajoutés en v0.36.1 (`.td-niv.niv-rouge/orange/vert/bleu…`),
  indexés sur le champ sémantique `couleur` de `services/niveaux.py`, qui valait
  « bleu » pour le niveau 4.
En outre, `.td-niv select` était redéclaré avec `background: var(--surface)`,
ce qui masquait en partie le fond de cellule.

## Décisions (validées)

- D1 — Source unique : les variables `--niv-*` du §20. La cellule reçoit
  `td-niv niv-<code>` (niv-1…niv-4, niv-A, niv-D, niv-0, niv-NE). L'ancienne
  palette par nom de couleur est supprimée. Le champ `couleur` du référentiel
  est corrigé pour décrire la teinte réelle : 2 → `jaune`, 4 → `vert_fonce`,
  A/D → `bleu` (servi par /api/referentiel/niveaux, + fallback JS).
- D2 — Teintes Pronote relevées au pixel : rouge #F80A0A, jaune #FFDA01,
  vert #45B851, vert foncé #008000. Badges : teinte pleine (texte blanc sur
  rouge et vert foncé, texte foncé sur jaune et vert). Cellules du tableau :
  même teinte éclaircie à 30 % sur blanc (`--niv-<code>-cell`), à l'essai.
  Le `<select>` de cellule est transparent et hérite de la couleur de texte.
- D3 — Absent/Dispensé : lettres en bleu Pronote #009EE1 sur fond neutre.
- D4 — Nettoyage : suppression des variables héritées `--niv-TB/S/F/I-*` et des
  règles `.badge-TB/S/F/I` qui les utilisaient (déjà écrasées plus bas par le
  bloc « Compatibilité anciens badges »). `.asm-crit-label--F/A/E` repointés
  sur `--niv-2-text` / `--niv-3-text` / `--niv-4-bg`.

## Fichiers

- `static/app.css` : §20 (palette + fonds de cellule), bloc hérité retiré,
  `.td-niv select` transparent, `.asm-crit-label--*`.
- `static/app.js` : `renderClasseView` (classe par code), fallback NIV_REF.
- `services/niveaux.py` : champ `couleur`.
- `tests_js/palette_niveaux_pronote.test.js` (nouveau), `tests/test_niveaux.py`
  (classe `TestCouleursPronote`).

## Tests

- vitest : 200 passed (dont 7 nouveaux). `deeplink_atelier_defini.test.js`
  échoue à la collecte : chemin absolu codé en dur (préexistant).
- pytest : 3942 passed ; 16 failed + 5 errors identiques à la base v0.36.1
  (préexistants, cf. ETAT_COURANT). `test_v0_29_0_verso_miroir.py` ignoré
  (collecte cassée, préexistant).

## Effet visible hors tableau de suivi

Les badges de niveau (légende, récapitulatifs) passent en teintes Pronote
pleines. Les libellés de critères de l'Assemblage (F/A/E) changent légèrement
de teinte.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Ctrl+Shift+R.
