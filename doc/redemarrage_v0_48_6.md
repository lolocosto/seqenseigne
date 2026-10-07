# Redémarrage v0.48.6 — Présentation commune des référentiels externes

Retours d'usage sur v0.48.5. Renumérotation : la partie « MER » de la
v0.48.x (séance / retour / délai sur les documents de MER, délai « fin de la
partie de MER », placement automatique, panneau « documents à distribuer »
de la Progression de MER) devient la **v0.48.7**.

## Décisions

- **Présentation commune, sur le modèle des MER** : cadre violet autour de
  chaque séquence (bandeau « SÉQUENCE », code, nom, ↑ ↓ ×), parties en
  retrait (« P1 · n séance(s) »), sous-titres « Objectifs », « Documents de
  la séquence », « Documents de la partie ».
- **Documents un par ligne**, avec leur type à côté ; le bouton
  « + document(s) » sur sa propre ligne — principaux et MER (documents de
  partie et documents annuels).
- **Libellés harmonisés** : « document(s) » partout (plus de « fichier(s) »).
- **Objectifs typés** (référentiels principaux externes), sur le modèle des
  internes : **connaissance** (« Connaître les notions et les méthodes »,
  nom et critères pré-remplis depuis les préférences de l'objectif
  « Connaître ») — **un seul par partie, toujours en 1re position** (ne se
  déplace pas, les capacités ne passent pas devant) ; **capacité** (maîtrise
  d'une capacité). Boutons « + objectif « Connaître » » (si absent) et
  « + capacité ».
- **Critères F/A/E repliés** : bouton « critères d'atteinte des niveaux de
  maîtrise » qui déplie trois zones de texte larges.

## Code

- Migration : colonne `referentiel_objectifs.type_obj` (`capacite` par
  défaut).
- `services/referentiel_principal_externe.py` : `TYPES_OBJ`,
  `ajouter_objectif(..., type_obj, criteres)` (unicité de la connaissance),
  renumérotation connaissance en tête, déplacement borné.
- `routes/referentiel_principal_externe.py` : objectif « connaissance »
  pré-rempli depuis `Configuration.atelier_assemblage_criteres_connaitre`.
- `static/referentiel_pe.js` (`_rpeSeq`, `_rpePartie`, `_rpeObjectif`),
  `static/referentiel_externe.js` (documents un par ligne), `static/app.css`
  (classes `rx-*` communes).

## Tests

- pytest `tests/test_v0_48_6_objectifs_types.py` (2).
- Suite complète : pytest 4161 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : séquence, partie, capacité puis « Connaître » (placé
  en tête, critères pré-remplis dépliés), deux documents sur deux lignes.
