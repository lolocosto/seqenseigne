# Redémarrage v0.34.0 — Suivi par créneau (option 1) + sélecteurs Suivi (étape A)

Delta cumulatif : inclut aussi les correctifs v0.33.1→v0.33.4 (le déploiement
courant pouvait ne pas les contenir).

## Option 1 — Saisie du suivi PAR CRÉNEAU (partie de séquence)

Le sélecteur du suivi de classe liste désormais les PARTIES de séquence
(S03 · P1, S03 · P2…) au lieu des séquences entières. La vue n'affiche que les
objectifs de la partie sélectionnée, et la note se calcule sur cette partie
(cohérent avec « une évaluation par créneau »).

La partie d'un objectif se déduit de son code (règle du système, appliquée et
maintenue automatiquement au réordonnancement : 01–09 → P1, 11–19 → P2,
21–29 → P3 ; num_partie = int(code[0])+1). Robuste par construction : déplacer un
objectif entre parties recalcule son code, donc le suivi le regroupe au bon
endroit.

Détails : `currentPartie` (mémorisé par classe), helpers `_partieDObjectif`,
`_partiesDeSequence`, `_objectifsDeLaPartie` ; `buildSeqSel` (parties),
`renderClasseView` (objectifs de la partie), `calcNote(seq,eid,partie)` (note de
la partie en vue classe ; séquence entière en vue élève).

## Sélecteurs du Suivi (étape A)

Le sous-onglet Suivi de classe expose maintenant Établissement + Niveau + Classe
(au lieu de Classe seule), via le même mécanisme que la Planification (pool de
labels). Changer l'établissement, le niveau ou l'année filtre la liste des
classes — ce qui lève l'ambiguïté des classes homonymes (ex. plusieurs « 4E4 »
d'années différentes). L'année courante (globale) filtre aussi la liste.

L'étape B (homogénéisation complète Suivi/Planif/Conception + Gestion) est en
ROADMAP pour v0.35.

## Correctifs cumulatifs inclus

- v0.33.1 : `_appliquerDeeplink` — `atelier` défini (sinon init() plante).
- v0.33.2 : `#prog-creneau-form` fermé (sinon panneaux Suivi/Gestion vides).
- v0.33.3 : clés d'exercices longues dans `renderClasseView`.
- v0.33.4a : niveau par défaut « - » (0) au lieu de « I » (note « — » avant saisie).
- v0.33.4b : progression retrouvée par triplet (id établissement) → bon référentiel.

## Fichiers

- `static/app.js` : option 1 (parties) + étape A (buildClasseSel filtré,
  onEtabChangeGlobal, onNiveauChangeGlobal) + correctifs v0.33.x.
- `routes/classes.py` : progression par triplet.
- `templates/index.html` : `#prog-creneau-form` fermé + onchange etab.
- `tests_js/suivi_navigation.test.js` : tests adaptés (Suivi = etab+niveau+classe).

## Tests

- vitest : 193 passed. Option 1 vérifiée (parties S03 = [1,2], objectifs
  filtrés). Correctifs v0.33 vérifiés.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Ctrl+Shift+R.
