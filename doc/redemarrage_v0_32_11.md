# Redémarrage v0.32.11 — Poignée visible + séquence suivante calendaire

Corrige les deux points restants de la v0.32.10.

## Bug 1 — poignée toujours invisible

`progSyncPoignee` faisait `poignee.style.display = ''` pour l'afficher. Mais une
chaîne vide fait retomber l'élément sur sa règle CSS `.prog-poignee { display:
none }` → la poignée restait masquée. Corrigé : `display: 'block'` (valeur
explicite) quand le détail est visible.

## Bug 2 — « séquence suivante » = S06 au lieu de S11

La séquence suivante était calculée dans l'ordre de STOCKAGE des créneaux (champ
`ordre`), pas dans l'ordre CALENDAIRE (dates). Sur la progression, S03 (07/09) a
`ordre=6` et le créneau `ordre=7` est S06 — d'où S06. Or le créneau daté juste
après S03 est S11 (21/09).

Corrigé : `_progDocsCtx` trie les créneaux par `date_debut` et prend la séquence
du créneau daté immédiatement après le créneau sélectionné.

## Fichiers

- `static/progression_doc.js` : affichage poignée (`display:'block'`) ;
  séquence suivante en ordre calendaire (tri par date_debut).

## Tests

- `node --check` (exit 0). vitest : 193 passed. Vérifié : S03 (07/09) → suivante
  S11 (21/09), pas S06.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.32.10.
