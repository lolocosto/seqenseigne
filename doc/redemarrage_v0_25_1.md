# Redémarrage v0.25.1 — Référentiels externes : édition, import multiple, réordonnancement

Améliorations de l'atelier « Référentiel externe ». Front + ajout d'endpoints de
déplacement.

## Changements

1. **Modifier une séquence** : code et nom éditables inline (sauvegarde à la
   sortie du champ).
2. **Modifier une partie** : libellé et **nombre de séances** éditables inline.
3. **Import de plusieurs documents à la fois** : sélecteur `multiple` ; envoi
   séquentiel (un fichier par requête) ; message récapitulatif (ajoutés /
   échecs).
4. **Réordonner les parties** d'une séquence : boutons ↑/↓. Les parties sont
   renumérotées (P1, P2…) selon le nouvel ordre.
5. **Réordonner les séquences** d'un référentiel : boutons ↑/↓.

## Fichiers

- `services/referentiel_externe.py` : `deplacer_sequence`, `deplacer_partie`
  (échange de position + renormalisation des `ordre` ; le numéro de partie suit
  l'ordre).
- `routes/referentiel_externe.py` : routes
  `…/sequences/<id>/deplacer` et `…/parties/<id>/deplacer` (POST, `sens`
  haut/bas).
- `static/referentiel_externe.js` : champs éditables (séquence, partie),
  `rxtModifierSeq`, `rxtModifierPartie`, `rxtImporterDoc` (multi-fichiers),
  `rxtDeplacerSeq`, `rxtDeplacerPartie`, boutons ↑/↓.

## Tests

- vitest : 193 passed (0 régression). Syntaxe OK.
- Vérifié via API : modification nom séquence / libellé + nb séances partie ;
  import de 3 documents d'affilée ; réordonnancement séquences (A B C → B C A) et
  parties (avec renumérotation).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration (champ `ordre`
déjà présent). Se déploie par-dessus la v0.25.0.

## Suite

- Progressions de MER « à la séance » s'appuyant sur les référentiels externes
  validés.
