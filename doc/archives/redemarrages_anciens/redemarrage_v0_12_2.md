# Redémarrage seqenseigne — v0.12.2 (chantier 3/5 de la série v0.12)

## Synthèse

**Harmonisation visuelle des sidebars d'ateliers.** Trois objectifs :

1. **Corriger le recouvrement titre** dans la sidebar (titre long écrasant
   le badge état à droite) — bug visuel reporté dans la roadmap v0.12.
2. **Aligner les 4 ateliers d'atome** (Exercice / Notion / Méthode /
   Fiche) sur un rendu d'item commun via un helper unique.
3. **Faire entrer les 2 ateliers de cycle** (Thème, Séquence-cycle)
   dans le design system des sidebars : ils utilisaient `.atl-item`
   mais avec des styles inline qui contournaient les classes propres.

Aucune modification de comportement, purement front. Cible tests
inchangée : **1888** au vert.

## Lot D — Correction du recouvrement titre

### Diagnostic

Cause racine localisée dans `static/app.css`. La sidebar utilisait :

```css
.atl-item       { display: flex; align-items: center; gap: 7px; }
.atl-item-titre { flex: 1; overflow: hidden; text-overflow: ellipsis;
                  white-space: nowrap; }
.atl-list-item-etat { margin-left: auto; flex: 0 0 auto; }
.atl-item-objs  { width: 100%; ... }   /* hack pour 2e ligne */
```

Deux problèmes :

1. **`flex: 1` sur le titre + `margin-left: auto` sur le badge état**
   se neutralisent. Le titre à `flex: 1 1 0` absorbe tout l'espace
   libre, ne laissant rien au `margin-left: auto` à pousser. Ajouté à
   l'absence de `min-width: 0` sur le titre (indispensable pour que
   l'ellipsis fonctionne dans un parent flex), un titre long déborde
   et **recouvre visuellement le badge**.
2. **`.atl-item-objs { width: 100% }`** est un hack qui dépend du
   wrap du parent flex sans que `flex-wrap: wrap` soit explicitement
   activé. Comportement non garanti selon les navigateurs.

### Correction

Quatre changements minimaux dans `static/app.css` :

```css
.atl-item       { ...; flex-wrap: wrap; }       /* + */
.atl-item-titre { flex: 1 1 auto; min-width: 0; ... }  /* changé */
.atl-list-item-etat { ...; flex: 0 0 auto; }    /* margin-left:auto retiré */
.atl-item-objs  { ...; flex: 1 0 100%; }        /* width:100% remplacé */
```

Le `min-width: 0` est le **vrai** correctif : il permet au titre de
shrinker en dessous de la largeur de son contenu, ce qui active
l'ellipsis. Le `flex-wrap` rend explicite le retour à la ligne pour
les chips. Le retrait de `margin-left: auto` est cohérent : le titre
en `flex: 1 1 auto` pousse naturellement le badge à droite.

Aucune réécriture de layout ni passage en grid : on reste dans le
modèle flex existant, simplement on le corrige.

## Lot B — Classe `.atl-sidebar-btn-creer`

Le bouton « + Créer » des sidebars portait, dans 6 endroits du HTML,
le style inline `style="font-size:12px;padding:4px 10px"`. Refactor
en classe CSS dédiée :

```css
.atl-sidebar-btn-creer {
  font-size: 12px;
  padding: 4px 10px;
}
```

Composée avec `.btn-prim` qui apporte couleurs / hover / active.
Les 6 styles inline sont nettoyés dans `templates/index.html`
(4 ateliers d'atome + Thème + Séquence-cycle).

## Lot C — Classe `.atl-item-titre--derive`

L'atelier Fiche utilise un fallback titre quand `f.titre` est vide :
il affiche à la place le nom de l'objectif lié, en italique pour
signaler que c'est un dérivé. L'italique était posé en
`<span style="font-style:italic">`. Remplacé par une classe :

```css
.atl-item-titre--derive {
  font-style: italic;
}
```

Sera réutilisée également comme variante du fallback « (sans titre) »
dans Exercice / Notion / Méthode (cf. Lot A).

## Lot A — Convergence du rendu d'item via helper unique

### Helper `atelAtomeRenderItemHtml`

Ajouté dans `static/atelier_atome_generique.js`, exposé sur `window`.
Centralise la structure visuelle des items de sidebar pour les 4
ateliers d'atome :

```js
window.atelAtomeRenderItemHtml({
  actif: bool,
  onclick: 'atelXxxCharger("id")',
  badge: '<span class="badge-fondamental">F</span>',  // optionnel
  id: 'N10/S04/F01',
  titre: 'Mon titre' | { html: '...', derive: true },
  meta: '<span class="atl-list-item-etat">...</span>', // optionnel
  chips: '<span class="atl-item-objchip">...</span>',  // optionnel (2e ligne)
})
```

Produit la structure standard `.atl-item > [badge] [id] [titre]
[meta] [chips]`. L'appelant reste responsable de l'échappement HTML
de ses inputs — le helper fait le minimum (composition de structure +
classe `active` + classe `--derive` pour le titre dérivé).

### Migrations

Les 4 fonctions de rendu utilisent désormais le helper :

- `atelExoRenderListe` (`static/app.js`) — Exercice : badge série,
  fallback `(sans titre)`, chips obj_lies
- `atelNotionRenderListe` (`static/app.js`) — Notion : id, titre,
  badge état, chips obj_lies
- `atelMethodeRenderListe` (`static/app.js`) — Méthode : id, titre,
  badge état, chips obj_lies (1 chip max, cardinalité 1-1)
- `atelFicheRenderListe` (`static/atelier_fiche.js`) — Fiche : id,
  titre avec fallback double (titre dérivé du nom de l'objectif si
  `f.titre` vide ; sinon `(sans titre)`), code obj + badge état dans
  `meta` (sans chips de 2e ligne, cardinalité 1-1)

Spécificités préservées :

- Exercice garde son badge série coloré (`.badge-fondamental` etc.)
- Fiche garde son fallback titre depuis `objectif_nom`
- Fiche garde son code obj affiché à droite (et non en chip de 2e
  ligne) — c'est une info structurelle de la fiche
- Notion / Méthode / Exercice utilisent toujours `atelObjLiesBadgesHtml`
  pour leurs chips d'objectifs liés

### Nouvelle classe `.atl-item-obj-code`

Pour le code objectif affiché à droite d'un item Fiche (« obj 02 »),
en remplacement du `<span style="font-size:10px;color:var(--text-muted)">`
inline. Style aligné sur `.atl-list-item-etat` (taille 10px, couleur
muted), placé juste avant le badge état dans le `meta`.

## Migration Thème + Séquence-cycle dans le design system

Les fichiers `static/ateliers_theme.js` et `static/ateliers_seqcycle.js`
utilisaient `.atl-item` mais leurs enfants étaient des `<span>` avec
styles inline (`flex:1;font-size:12px;overflow:hidden;text-overflow:
ellipsis;white-space:nowrap` pour le titre, etc.). Migration vers les
classes propres :

- `<span style="display:inline-block;width:10px;height:10px;
  border-radius:50%;background:...">` → `.atl-item-pastille`
  (avec `style="background:..."` minimal pour la couleur, qui reste
  variable selon la famille du thème)
- `<span style="display:inline-block;width:10px;height:10px;
  flex-shrink:0">` (pastille vide) → `.atl-item-pastille
  .atl-item-pastille--vide`
- `<span style="font-weight:500;width:20px">CODE</span>` →
  `.atl-item-id .atl-item-id--compact` (variante sans `min-width:78px`,
  plus adaptée aux codes courts comme `A` ou `S01`)
- `<span style="flex:1;font-size:12px;...">TITRE</span>` →
  `.atl-item-titre`
- `<span style="font-size:10px;color:var(--text-muted)">5 seq</span>`
  → `.atl-item-compteur`

Avantage immédiat : ces deux ateliers bénéficient du correctif Lot D
sans modification supplémentaire (puisqu'ils utilisent maintenant
`.atl-item-titre` qui hérite du `min-width: 0`).

Particularité conservée pour Séquence-cycle : la pastille « pas de
thème » reste en gris `#ddd` (et non invisible comme pour Thème) —
utile pour signaler l'absence de rattachement.

## Tests

**Total : 1888 tests** (inchangé). Cette livraison est purement front,
aucun test Python touché. Validation syntaxique JS (`node --check`)
sur les 5 fichiers modifiés : OK.

Validation visuelle à faire côté Laurent (cf. ci-dessous).

## Fichiers touchés

```
static/app.css                          (~95 lignes :
                                           - .atl-item : flex-wrap
                                           - .atl-item-titre : min-width:0
                                           - .atl-item-titre--derive : nouveau
                                           - .atl-list-item-etat : margin-left retiré
                                           - .atl-item-objs : flex:1 0 100%
                                           - .atl-item-id--compact : nouveau
                                           - .atl-item-pastille[--vide] : nouveau
                                           - .atl-item-compteur : nouveau
                                           - .atl-item-obj-code : nouveau
                                           - .atl-sidebar-btn-creer : nouveau)
static/atelier_atome_generique.js       (~50 lignes : nouveau helper
                                           atelAtomeRenderItemHtml)
static/app.js                           (~60 lignes : refactor des 3
                                           rendus Exo/Notion/Méthode)
static/atelier_fiche.js                 (~25 lignes : refactor render +
                                           passage à atelAtomeRenderItemHtml)
static/ateliers_theme.js                (~15 lignes : passage aux classes)
static/ateliers_seqcycle.js             (~15 lignes : passage aux classes)
templates/index.html                    (6 lignes : nettoyage des styles
                                           inline du bouton "+ Créer")
doc/redemarrage_v0_12_2.md              (NOUVEAU)
```

Aucune modification BDD, Python, route, service. Aucune migration.

## Procédure de déploiement

1. Décompresser le ZIP par-dessus la v0.12.1.2 actuellement déployée.
2. Relancer l'application — démarrage immédiat (pas de migration).
3. **Forcer le rafraîchissement du cache navigateur** (Ctrl+F5 sur
   Firefox/Chrome) — la livraison ne change que JS/CSS, le cache HTTP
   peut servir les anciens fichiers.

## Points de validation côté Laurent

Validation visuelle exhaustive sur les 6 sidebars :

### Atelier Exercice (portée Séquence)
- Item avec **titre court** : badge série + ID + titre + badge état
  alignés sur une ligne, badge état collé à droite
- Item avec **titre long** : titre tronqué par ellipsis (`…`), badge
  état toujours visible et collé à droite, **pas de recouvrement**
- Item avec **chips obj_lies** : chips sur une 2e ligne, alignés sous
  le titre
- Bouton « + Créer » : style identique à avant (mais maintenant via
  classe au lieu de inline)

### Atelier Notion / Méthode / Fiche
- Mêmes vérifs que Exercice (sauf badge série, propre à Exercice)
- Fiche : code obj « obj 02 » à droite avant le badge état
- Fiche avec titre vide + objectif lié : nom de l'objectif en italique

### Atelier Thème (portée Cycle)
- Pastille de couleur en tête + code thème compact + nom + compteur
  « N seq » à droite
- Vérifier que la pastille a la bonne couleur (variant selon le thème)

### Atelier Séquence-cycle (portée Cycle)
- Pastille de couleur (ou grise si pas de thème) + code séquence + nom
  + compteur d'atomes
- Vérifier que la pastille grise apparaît bien quand le thème n'est
  pas défini

### Cas de régression à surveiller
- Items actifs (sélectionnés) : fond bleu pâle visible
- Hover : fond surface-light apparent
- Filtres exo (série) : fonctionnent toujours
- Filtres état (Tous/En cours/Validé) : fonctionnent toujours

## Prochaine étape

v0.12.3 — **Suppression du toggle Assemblage / Édition avancée + retrait
du rappel niveau/séquence sur la toolbar** (chantier 4/5 de la série
v0.12). Cf. roadmap.
