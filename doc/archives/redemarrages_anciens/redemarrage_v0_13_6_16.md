# Redémarrage v0.13.6.16 — Harmonisation frontend + relâche création

## Périmètre

Suite et fin de l'harmonisation engagée en v0.13.6.15 (backend). Cette
livraison couvre :

1. **Frontend aligné** sur le contrat à 6 clés du backend
2. **Pattern de création unifié** dans la classe parente AtelierEditeur
   (POST direct + ouverture)
3. **Création relâchée** : champs obligatoires uniquement à la
   validation pédagogique (modèle « en cours = peut être incomplet »)
4. **Cache PDF** : invalidation uniquement quand la BdD change
5. **Diagnostic + fix** de la régression « impossible de créer un
   atome sauf carte »
6. **Modale dédiée** au choix de la série pour la création d'exercice
7. **Suppression** de « Initialiser depuis » dans atelier_fiche

## Décisions actées

| Q | R |
|---|---|
| Cache PDF/.tex invalidation | Uniquement à modif BdD (sauvegarde, suppression). Pas à l'ouverture. À terme : cache persistant côté serveur pour servir des imagettes en assemblage. |
| Création d'atome (notion/méthode/exercice/fiche) | Pattern unifié dans la classe parente : POST direct avec valeurs par défaut → ouverture immédiate de l'item retourné. Chaque sous-classe expose `_payloadCreation()`. |
| Champs obligatoires à la création | Relâchés (modèle « en cours »). Backend autorise titre/énoncé/corrigé vides à la création ; les hooks de validation pédagogique exigent ces champs uniquement au passage en `valide`. |
| Création d'exercice | Modale dédiée au choix de la série (F/A/E/EA) avant POST. La série reste le seul champ imposé à la création (creer_exercice l'exige). |
| « Initialiser depuis » dans atelier_fiche | Retiré (s'appuyait sur les fetchs `/api/methodes` et `/api/notions` sans filtre, plus supportés). À réintroduire plus tard avec un design propre. |

## Régression diagnostiquée

**Symptôme** : depuis v0.13.6.14 ou avant, impossible de créer un atome
dans les ateliers notion/méthode/exercice/fiche. Seule la carte
permettait la création (parce qu'elle avait un pattern différent).

**Cause** : dans `AtelierEditeur.afficherEditeur(existant)`, le
paramètre `existant` était ignoré. La méthode appelait
`basculerOnglet` qui n'affichait le formulaire que si `this.itemActif`
était truthy. À la création, `itemActif = null` → formulaire caché →
impossible de saisir quoi que ce soit. La carte échappait au bug parce
qu'elle surchargeait `nouvelItem` pour faire un POST direct + ouverture
immédiate (qui pose `itemActif != null`).

**Fix** : avec le nouveau pattern unifié (POST direct + ouvrirItem)
pour tous les ateliers, `itemActif` est désormais toujours posé quand
le form s'affiche. La régression disparaît structurellement. Le
paramètre `existant` d'`afficherEditeur` n'est plus nécessaire (gardé
pour compatibilité des appels).

## Architecture cible

### Pattern de création unifié (v0.13.6.16)

```javascript
// Dans AtelierEditeur (classe parente)
async nouvelItem() {
  // vérifications préalables (niveau/sequence, modifs en cours)
  const payload = this._payloadCreation();
  // POST direct
  const resp = await fetch(this.config.endpointBase, {
    method: 'POST', body: JSON.stringify(payload)
  });
  const item = await resp.json();
  // Rafraîchit la liste (format contrat 6 clés) puis ouvre l'item
  await this.chargerListe();
  await this.ouvrirItem(item.id);
}

// Chaque sous-classe surcharge _payloadCreation pour ses valeurs par défaut
_payloadCreation() {
  return { niveau: ..., sequence: ..., /* champs spécifiques */ };
}
```

Surcharges effectives :

| Atelier | Spécificités |
|---------|-------------|
| Notion, méthode | Payload par défaut suffit (niveau + sequence). Backend pose titre = '' |
| Exercice | Surcharge `nouvelItem` pour intercaler une modale de choix de série. Payload final : `{niveau, sequence, serie, enonce: '', corrige: ''}` |
| Fiche | Surcharge `nouvelItem` pour `_chargerTitresZoneSiBesoin` avant `super.nouvelItem()`. `_payloadCreation` retourne `{niveau, sequence, titre: ''}` |
| Carte | `_payloadCreation` retourne le payload historique : `{niveau, sequence, type_pedago: 'definition', type_tech: 'fixe', titre: '', recto: '', verso: ''}` |

### Cache PDF/.tex

Avant : `_texCharge` (booléen global) invalidé à chaque ouverture
d'item.

Maintenant : `_texChargeId` (id de l'item dont le DOM contient le .tex).
- Validé quand `_texChargeId === itemActif.id`
- Invalidé uniquement à `sauvegarder()` réussi (PUT/POST) et
  `supprimer()` réussi (= quand la BdD change)
- Conservé à `ouvrirItem` (le DOM peut être obsolète pour l'item
  actuel ; au prochain toggleTexBrut, le cache détectera que l'id
  ne correspond pas et refetchera — invalidation paresseuse)

Long terme : cache persistant côté serveur pour servir des miniatures
en assemblage sans recompiler.

### Hooks de validation pédagogique

Avant : seule la carte avait un hook (refuse `valide` si recto/verso/lien/variables manquants).

Maintenant : ajout de hooks pour notion, méthode, exercice, fiche.

| Type | Règles refusant la validation |
|------|------------------------------|
| notion | titre vide |
| méthode | titre vide |
| exercice | énoncé vide OU corrigé vide |
| fiche_resume | titre vide OU aucune section avec contenu |

L'enseignant peut donc créer un atome incomplet (clic « + Créer »
direct) et le compléter progressivement. Au moment où il essaie de
valider (passage en `valide`), le backend lui dit ce qui manque via
le toast d'erreur (qui inclut `raisons[]` depuis v0.13.6.14.1).

### Modale choix série

Nouveau élément DOM dans `index.html` (ajouté avant `</body>`) :
`#atl-exo-modale-serie`. Affiché par `AtelierExercice.nouvelItem` qui
surcharge le pattern parent pour intercaler le choix interactif.

Contrôles :
- 4 boutons F/A/E/EA stylisés `.serie-btn` (style identique à la
  sidebar de l'atelier)
- Bouton × en haut à droite : annule
- Touche Esc : annule
- Clic sur l'overlay (en dehors du contenu) : annule
- Annulation = pas de POST, retour silencieux

Implémentation : Promise/resolve dans `_demanderSerie()`, gestionnaire
keydown ajouté/retiré dynamiquement.

## Fichiers livrés

### Production (10 fichiers)

```
appli/services/atomes.py                   creer_notion/methode/exercice relâchés
                                           + hooks _valider_*_hook + enregistrement
appli/services/fiches_resume.py            hook _valider_fiche_hook + enregistrement
appli/static/atelier_editeur.js            nouvelItem unifié POST direct +
                                           _payloadCreation, ouvrirItem GET unitaire
                                           systématique, invalidation cache à
                                           sauvegarder/supprimer
appli/static/atelier_atomique.js           _texCharge → _texChargeId (cache par item),
                                           suppression invalidation à ouvrirItem
appli/static/atelier_notion.js             rendreItem utilise c.code + filtres globaux,
                                           itemVide supprimé, titre relâché
appli/static/atelier_methode.js            idem notion
appli/static/atelier_exercice.js           rendreItem utilise ex.code + extraction série,
                                           nouvelItem surchargé avec modale série,
                                           _payloadCreation et helpers modale,
                                           énoncé/corrigé relâchés
appli/static/atelier_fiche.js              rendreItem utilise f.code + filtres globaux,
                                           ouvrirItem/nouvelItem simplifiés (super +
                                           spécificité fiche), _payloadCreation,
                                           "Initialiser depuis" supprimé (2 méthodes +
                                           HTML select + listener + alias orphelin)
appli/static/atelier_carte_automatisme.js  rendreItem aligné contrat 6 clés (badge P +
                                           icône retirés sidebar), nom → titre partout
                                           (BdD migrée), nouvelItem remplacé par
                                           _payloadCreation
appli/templates/index.html                 #atl-exo-modale-serie ajoutée avant </body>
```

### Tests adaptés (4 fichiers)

```
appli/tests/test_routes.py                       2 tests : titre/corrigé vide
                                                 maintenant ACCEPTÉS (201)
appli/tests/test_services.py                     3 tests transformés :
                                                 « obligatoire » → « optionnel à la
                                                 création, hook côté validation »
appli/tests/test_v0_10_4_etats_edition.py        test_tous_les_types : transitions
                                                 neutres pour ne pas déclencher hooks
                                                 (schéma de test minimal incompatible)
appli/tests/test_v0_10_5_fiches_resume.py        sections fournies au POST pour
                                                 passer le hook fiche
```

## Vérification

- Suite complète : **3238 passed, 5 skipped, 0 failed**
- Syntaxe JS (`node -c`) et Python (`ast.parse`) validées
- Audit refs orphelines : `atelFicheInitialiserDepuisSelect`,
  `initialiserDepuisSelect`, `_peuplerSelectInitialisationAuOuverture`,
  `itemVide()` → tous retirés ou commentés

## À tester chez toi

### Création d'atome (régression corrigée)

1. Ouvrir l'atelier notion. Sélectionner niveau/séquence.
2. Cliquer « + Créer ». Une notion vide doit apparaître dans la
   sidebar (code `N03` ou similaire), être ouverte automatiquement,
   formulaire vide affiché, titre vide.
3. Saisir un titre, sauvegarder. La notion se met à jour dans la
   sidebar.
4. Tenter de valider via « Valider ». Si le titre est vide, le toast
   d'erreur indique « Le titre est vide ».
5. Pareil pour méthode, fiche.

### Création d'exercice (modale)

1. Ouvrir l'atelier exercice. Sélectionner niveau/séquence.
2. Cliquer « + Créer ». La modale doit apparaître avec 4 boutons
   colorés F/A/E/EA.
3. Essayer Esc → modale fermée, aucun exercice créé.
4. Réouvrir « + Créer », essayer clic en dehors → idem.
5. Réouvrir, cliquer sur F. L'exercice apparaît dans la sidebar
   (code `E01` ou similaire) avec énoncé et corrigé vides. Le rendu
   PDF doit afficher un exercice (avec contenu minimal probablement
   compilable, dépend du paquet seqenseigne).
6. Tenter de valider sans saisir énoncé/corrigé. Toast d'erreur :
   « L'énoncé est vide. ; Le corrigé est vide. ».

### Création de carte

Doit continuer à fonctionner comme avant (le pattern carte était
déjà le bon, désormais c'est le pattern partagé).

### Cache PDF/.tex

1. Ouvrir une notion. Activer « Voir le .tex brut ». Le .tex se
   charge.
2. Refermer puis ré-ouvrir « Voir le .tex brut ». Le .tex doit
   s'afficher **sans nouveau fetch** (instantané).
3. Sauvegarder une modification. Re-ouvrir « Voir le .tex brut ».
   Cette fois, un fetch (le .tex en BdD a changé).
4. Naviguer à une autre notion via la sidebar. Activer « Voir le
   .tex brut ». Le .tex correspond à la nouvelle notion (fetch
   automatique car `_texChargeId !== itemActif.id`).

### Suppression « Initialiser depuis »

Le sélecteur « Initialiser depuis… » a disparu des zones de fiche.
Plus de double sélecteur, juste le sélecteur de titre de zone.

## Points d'attention

1. **Pattern POST direct** : crée un atome immédiatement à chaque
   clic sur « + Créer ». Si l'enseignant clique par erreur, l'atome
   reste en `en_cours` mais existe en BdD. Pour le retirer, il doit
   le sélectionner et cliquer « Supprimer ». Tu peux aussi laisser
   un atome vide en `en_cours` (pas gênant pour la compilation
   puisque seuls les `valide` sont compilés).

2. **Hooks de validation** : la fiche exige maintenant au moins une
   section avec contenu pour être validée. Si tes fiches existantes
   ont déjà du contenu, aucun impact. Sinon, le hook les empêchera
   de passer en `valide` (toast d'erreur explicite).

3. **Note v0.13.6.15** : la livraison précédente cassait l'UI. Cette
   v0.13.6.16 répare tout et reste sur le nouveau contrat à 6 clés.
   Si tu n'as pas encore déployé v0.13.6.15, déploie les deux en
   bloc.

## Prochaine étape — v0.13.6.17+

Idées qui restent :

- **Cache PDF persistant côté serveur** : pour servir des imagettes
  en assemblage sans recompiler. Probablement table
  `rendu_atome_cache(item_id, type_atome, pdf_bytes, mtime)` avec
  invalidation au trigger de modification.
- **Tests HTTP nouveaux** pour `PATCH /api/atomes/<type>/<id>/etat`
  (couverture qui aurait évité le bug 1 de v0.13.6.14).
- **Atelier d'assemblage avec imagettes** : matérialise les liens
  notion↔objectif, méthode↔objectif, exercice↔objectif via des
  cartes-vignettes. Dépend du cache PDF persistant.
- **Réintroduction « Initialiser depuis »** avec un GET dédié
  `/api/v2/fiches/<id>/atomes-aplatissables` qui retourne les
  atomes éligibles depuis l'objectif lié (= ne s'appuie plus sur
  les routes liste légères, design propre).
