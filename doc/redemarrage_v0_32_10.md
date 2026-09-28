# Redémarrage v0.32.10 — Corrections : calendrier, poignée, séquence suivante

Corrige trois points de la v0.32.9.

## Bug 1 — le calendrier disparaissait à la sélection d'un créneau

Le CSS de `.prog-detail` et `.prog-poignee` avait été perdu (éditions
successives) : `.prog-detail` n'avait plus de `flex`/largeur définis, ce qui
cassait le layout de `.prog-zone` et faisait disparaître le calendrier quand le
détail s'affichait. Bloc CSS réinséré, avec un layout robuste :
- `.prog-calendrier` : `flex: 1 1 auto; min-width: 280px` (ne disparaît jamais) ;
- `.prog-detail` : `flex: 0 0 auto; width 320px; min 240 / max 70vw`.

Le calendrier reste désormais visible en permanence, détail sélectionné ou non.

## Bug 2 — poignée de redimensionnement absente

Conséquence du même CSS perdu (`.prog-poignee` supprimée). Réinsérée
(`flex: 0 0 6px`, masquée par défaut, affichée avec le détail via
`progSyncPoignee`). On la tire horizontalement entre calendrier et détail.

## Correctif 3 — « séquence suivante »

La séquence suivante était calculée par incrément numérique (S03 → S04). Or il
s'agit de la séquence du **créneau suivant dans la progression** (S03 peut être
suivi de S11). `_progDocsCtx` calcule maintenant `sequence_suivante` en parcourant
les créneaux dans l'ordre jusqu'à la première séquence différente.

## Fichiers

- `static/app.css` : `.prog-zone` / `.prog-calendrier` / `.prog-detail` /
  `.prog-poignee` (layout réparé).
- `static/progression_doc.js` : `sequence_suivante` = séquence du créneau suivant.

## Tests

- `node --check` (exit 0). vitest : 193 passed. Vérifié : séquence suivante de
  S03 = S11 (créneaux S03 → S11 → S14) ; poignée, calendrier et détail présents.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.32.9.
