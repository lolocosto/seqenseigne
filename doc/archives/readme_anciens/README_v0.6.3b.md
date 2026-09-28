# seqenseigne v0.6.3b — UI gestion des établissements, fusion, validation UAI

Livraison construisant sur v0.6.3a. Ajoute l'interface visible pour gérer
les établissements créés à l'import : compléter l'académie manquante,
valider par UAI, fusionner les doublons.

**Prérequis** : la v0.6.3a doit être déjà déployée (schéma DB avec table
`etablissements`, `cache_api`, FK `etablissement_id`, service
`services/etablissements.py`, service `services/calendrier_scolaire.py`).

## Nouveautés backend

### Fusion d'établissements

Nouvelle fonction `services/etablissements.fusionner(store, source_id, cible_id)` :
- Migre toutes les classes de source vers cible
- Migre toutes les progressions de source vers cible
- Supprime source

Le tout atomique, dans une transaction.

Règles dures (levées comme `ConflitFusion` avec code machine) :

- **`source_validee`** : interdiction absolue de supprimer un
  établissement validé. L'enseignant doit inverser le sens de la fusion.
- **`conflit_progression`** : si source ET cible ont tous deux une
  progression sur la même `(niveau, annee)`, refus — il faut résoudre
  manuellement avant de fusionner.

### Détection de doublon à la validation UAI

`valider_par_uai` détecte le cas Laurent : un établissement `propose`
"Collège des Hautes Ourmes" qu'on valide avec son UAI officiel → l'annuaire
remonte "Collège Les Hautes Ourmes" → un autre établissement en base porte
déjà ce nom → refus avec exception `DoublonEtablissement(etab_cible_id,
nom)`.

L'API renvoie alors :

```json
409 Conflict
{
  "error": "Un autre établissement porte déjà le nom 'Collège Les Hautes Ourmes' (id=et_xxx, état=propose). Une fusion est nécessaire avant validation.",
  "code": "doublon_detecte",
  "etab_cible_id": "et_2165207c",
  "nom_officiel": "Collège Les Hautes Ourmes"
}
```

L'UI bascule automatiquement sur le flux de fusion (source "des" → cible
"Les").

### Nouvelle route

`POST /api/etablissements/<source_id>/fusionner` avec body `{"cible_id": "et_xxx"}`.
Retourne la cible enrichie de `classes_migrees` et `progressions_migrees`, ou
`409` avec `code` et `details` structurés si refus.

## Nouveautés UI

### Sous-onglets dans Gestion des classes

L'écran Gestion des classes est désormais découpé en 2 sous-onglets :
- **Classes** (existant, inchangé)
- **Établissements** (nouveau)

### Bandeau d'invitation

Un bandeau orange s'affiche en haut de Gestion des classes tant qu'un
établissement utilisé n'a pas d'académie renseignée. Il disparaît
automatiquement dès que tous ont une académie (peu importe si validés par
UAI ou saisis à la main).

### Liste des établissements

Carte par établissement avec 3 boutons :

- **Valider avec UAI** (bouton principal bleu, pour les non-validés) :
  popup saisie UAI → appel API → si succès, tous les champs sont remplis
  depuis l'annuaire ; si doublon détecté, bascule automatiquement sur le
  popup de fusion.
- **Modifier** (secondaire) : popup d'édition des champs nom / académie /
  ville.
- **Fusionner avec…** (secondaire) : popup avec un select des autres
  établissements, pour corriger à la main les coquilles (ex: "des/Les")
  sans passer par la validation UAI.

### Badge d'état

Chaque carte affiche un badge :
- **"✓ Validé"** vert : état `valide`, champs sourcés de l'annuaire EN
- **"Académie saisie"** bleu : état `propose`, mais académie renseignée
  (le calendrier fonctionnera)
- **"À compléter"** orange : état `propose`, académie vide

### Gestion des erreurs

Les erreurs serveur (`400`, `409`) sont capturées et affichées dans la
carte concernée, jamais en popup bloquant (sauf succès de fusion : un
`alert()` récapitule `N classes migrées, M progressions`).

## Scénarios UI testés (Playwright headless)

Scénario Laurent (cas réel) :
- 3 établissements en base : "Collège Jean Moulin" (Rennes saisi),
  "Collège Les Hautes Ourmes" (vide), "Collège des Hautes Ourmes" (vide,
  coquille)
- Bandeau affiché : "2 établissements n'ont pas d'académie"
- Clic "Fusionner avec…" sur "des Hautes Ourmes"
- Popup propose les 2 autres comme cibles
- Sélection "Les Hautes Ourmes" + Fusionner
- Alert de succès : "1 classe migrée, 0 progressions"
- Après : il ne reste que 2 établissements, la classe 4e6 2021-2022
  pointe maintenant vers "Collège Les Hautes Ourmes"
- Bandeau mis à jour : "1 établissement n'a pas d'académie"

## Tests

**355 tests verts** (348 + 7 nouveaux).

Les 7 nouveaux tests couvrent :
- fusion simple (migration classes + progressions)
- fusion refusée si source validée
- fusion autorisée quand cible validée
- fusion refusée si conflit de progression (`(niveau, annee)` identique
  des 2 côtés)
- fusion avec source == cible refusée
- validation UAI détecte un doublon et lève `DoublonEtablissement`
- validation d'un établissement sur son propre nom officiel (pas de faux
  positif)

## Fichiers

```
appli/services/etablissements.py     (ajout DoublonEtablissement, ConflitFusion, fusionner)
appli/routes/etablissements.py       (409 doublon sur /valider, nouveau /fusionner)
appli/static/app.js                  (~260 lignes ajoutées)
appli/templates/index.html           (sous-onglets Classes/Établissements + bandeau)
appli/tests/test_etablissements.py   (7 nouveaux tests)
```

## Déploiement

```powershell
# Copier les 5 fichiers
# (Pas de migration DB — la v0.6.3a a déjà tout posé)
# Redémarrer Flask
# Ctrl+F5 dans le navigateur
```

## Vérifications recommandées côté Laurent

1. Ouvrir "Suivi de classe" → "Gestion des classes" → "Établissements"
2. Vérifier que tous les établissements sont listés
3. Pour chacun, renseigner au minimum l'académie (sinon le calendrier ne
   fonctionnera pas en v0.6.3c)
4. Pour le cas Les/des Hautes Ourmes : soit valider "Les" par UAI puis
   fusionner "des" dedans, soit fusionner directement les deux (peu
   importe le sens tant qu'aucun des deux n'est validé), puis valider le
   résultat par UAI.

## Prochaines étapes

- **v0.6.3c** : calendrier visuel (grille semainière sept→août) dans le
  panneau gauche du sous-onglet Progression. Vacances grisées, jours
  fériés marqués. Badge d'état de la progression sur la progression.
  Fonction `progUIEnabled(etat)` qui active/désactive les boutons
  d'édition selon l'état.
- **v0.6.3d** : détail créneau enrichi avec liste d'objectifs, suppression
  de la vue synthétique devenue redondante.
