# Redémarrage v0.17.3 — Aperçu PDF au survol (sidebar seqniv) + libellé bouton

Deux éléments : un correctif de libellé trivial, et le chantier 2 de la v0.17
(aperçu PDF au survol des atomes), livré pour la sidebar du seqniv.

## 1. Libellé bouton seqniv

`atelier_seqniv_assemblage.js` : le bouton « Voir le .tex » de l'onglet Rendu
devient « LaTeX généré », par cohérence avec tous les autres ateliers.

## 2. Aperçu PDF au survol (chantier 2)

Cadrage : `cadrage_unification_ateliers_assemblage.md` §2bis/§5bis.
Décisions : A1 (atomes compilables), A2 (modale unique large flottante),
A3 (hybride avec bouton « Générer l'aperçu »), délai **1500 ms** (constante,
non exposée en réglage — choix assumé : trop bas niveau pour l'utilisateur).

### Mécanique commune — `static/atelier_assemblage.js`

Tout est dans `AtelierAssemblage` (hérité par le seqniv et l'évaluation), donc
réutilisable directement quand on instrumentera les autres éléments :

- `_installerApercuSurvol(conteneur)` : pose un listener **délégué**
  (mouseover/mouseout) sur un conteneur stable, idempotent (dataset). Cible les
  éléments portant `data-atome-type` + `data-atome-id`.
- `_armerApercu` / `_desarmerApercu` : timer unique de
  `AtelierAssemblage.DELAI_APERCU_MS` (1500). Réarmer remplace le timer (un seul
  actif). mouseout vers l'extérieur de l'atome → désarme.
- `_declencherApercu(type, id)` : à l'expiration, `GET
  /api/atomes/<type>/<id>/rendu-pdf/info` (cache-check sans compiler) →
  `cache_valide` → affichage PDF, sinon modale « non généré » + bouton.
- `_afficherApercuPdf` : `GET .../rendu-pdf`, blob → viewer pdf.js hérité
  (`_afficherPdfDansViewer`).
- `_afficherApercuNonGenere` + `_genererPuisAfficherApercu` : `POST .../rendu-pdf`
  puis affichage (stratégie hybride A3).
- **Anti-empilement** : compteur `_apercuGen` incrémenté à chaque déclenchement
  et à la fermeture ; toute réponse `fetch` dont le `gen` n'est plus courant est
  ignorée (souris déjà repartie).
- **Modale unique** : `_assurerModaleApercu` crée UNE fois un panneau flottant
  `fixed` large ancré en haut à droite (≈ min(46vw,560px) × min(80vh,760px)),
  avec tête + bouton ✕ + zone corps. Fermeture : bouton ✕, `mouseleave` de la
  modale, ou `Escape`.

### Instrumentation — sidebar du seqniv

- `_renduItem` (point de rendu factorisé des lignes sidebar) dérive
  `data-atome-type` + `data-atome-id` depuis `dragData.kind` :
  `methode → methode`, `notion → notion`, `fiche → fiche`,
  `exo_catalogue → exercice`. Seules les lignes **draggables** (atomes du
  catalogue) sont instrumentées dans cette livraison.
- `_rendreSidebar` appelle `_installerApercuSurvol(this._sidebarBody())`
  (conteneur stable `#liv-atl-sidebar-body`), idempotent.

### Périmètre de cette livraison (décision Laurent)

**Sidebar du seqniv uniquement.** Les chips d'atomes déjà placés (dans les
objectifs/parties) et l'atelier Évaluation seront instrumentés dans une
livraison suivante — la mécanique commune étant déjà en place, il suffira
d'ajouter `data-atome-type/id` sur ces éléments et d'appeler
`_installerApercuSurvol` sur leurs conteneurs.

## Tests

- **Vitest** : 86 passed (77 + 9 nouveaux).
  - `tests_js/apercu_survol.test.js` : délai = 1500, idempotence du listener,
    armement/désarmement, réarmement (un seul timer), modale unique, hybride
    (cache_valide=false → bouton Générer), invalidation des réponses obsolètes
    (gen périmé), fermeture qui invalide les réponses en vol.
- **pytest** : 3793 passed, 7 skipped, 0 failed (backend inchangé : les routes
  `/rendu-pdf/info` et `/rendu-pdf` existaient déjà).
- **Syntaxe** : node --check OK sur les 2 fichiers JS modifiés.

## À vérifier côté Windows (validation visuelle)

1. Onglet Rendu du seqniv : le bouton s'intitule « LaTeX généré ».
2. Survoler une ligne du catalogue (sidebar) ~1,5 s :
   - si l'atome a un PDF en cache → la modale flottante affiche l'aperçu ;
   - sinon → modale « Aperçu non encore généré » + bouton « Générer l'aperçu »
     (qui compile puis affiche).
3. Déplacer la souris ailleurs avant 1,5 s → rien ne s'affiche (pas de
   clignotement, pas d'empilement de modales).
4. Survoler rapidement plusieurs lignes → une seule modale, contenu cohérent
   avec la dernière ligne survolée (pas de PDF d'une ligne précédente).
5. Fermeture : bouton ✕, sortie de la souris de la modale, ou Escape.
6. Les chips déjà placés et l'évaluation n'ont pas encore l'aperçu (prévu
   ensuite) — comportement normal.

## Suite possible

Étendre l'aperçu aux chips placés (exos/notions/fiches/méthodes dans les
objectifs et parties) et à l'atelier Évaluation : il suffit d'ajouter
`data-atome-type` + `data-atome-id` sur ces éléments et d'appeler
`_installerApercuSurvol` sur leurs conteneurs respectifs.
