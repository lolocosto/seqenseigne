# seqenseigne v0.6.3d — patch B « bloc Sélection de progression (frontend) »

Frontend du chantier de refonte du bloc « Sélection de progression » de
l'écran Progression annuelle. Doit être installé **après le patch A** (qui
fournit les endpoints backend consommés par ce patch).

## Objet du patch

Remplacer l'ancien bloc de sélection (« Progression » avec sélecteur de
niveau + liste déroulante de progressions) par le nouveau bandeau
« Sélection de progression » conforme à la maquette validée :

- bandeau bleu primaire avec titre et sous-titre explicites ;
- trois sélecteurs numérotés dans l'ordre 1-Année / 2-Établissement / 3-Niveau ;
- bouton « Rechercher » explicite ;
- lien discret « Ajouter un établissement » qui renvoie vers la gestion
  des établissements ;
- état 0 résultat : encadré ambre avec bouton « + Créer la progression » ;
- dialogue de création inline avec sélection du référentiel
  (le plus récent du niveau présélectionné) ;
- état défensif ≥ 2 progressions : encadré rouge.

À l'ouverture de l'écran, si les trois critères ont une valeur par défaut
(année courante + établissement unique + niveau N11), la recherche est
déclenchée automatiquement.

## Fichiers modifiés

```
appli/templates/index.html
    → remplacement du bloc lignes 42-69 ancien par le nouveau bandeau
      et les 3 encadrés (aucune / erreur).
    → suppression des ids devenus obsolètes : prog-niveau, prog-liste,
      prog-liste-container, prog-meta, prog-meta-etab, prog-meta-info.
    → nouveaux ids : prog-sel-annee, prog-sel-etab, prog-sel-niveau,
      prog-aucune, prog-aucune-triplet, prog-erreur, prog-erreur-msg.

appli/static/app.css
    → ajout en fin de fichier des classes .prog-selection-*, .prog-aucune,
      .prog-erreur, .prog-dialogue-* (150 lignes).
    → utilise les variables CSS existantes (--primary, --primary-bg, etc.).

appli/static/app.js
    → réécriture complète des fonctions progInit, progNiveauChange,
      progListeChange, progChargerListe par la nouvelle logique :
      · progInit : charge années + établissements en parallèle, peuple les
        sélecteurs, déclenche recherche auto si les 3 critères ont une valeur
      · progSelectionRechercher : appelle /api/progression/<niv>/rechercher
      · progAfficherAucune / progAfficherErreur : états dégradés
      · progOuvrirDialogueCreation / progFermerDialogueCreation /
        progCreerProgression : dialogue de création avec choix du référentiel
    → remplacement de 12 références document.getElementById('prog-niveau')
      par document.getElementById('prog-sel-niveau') dans les fonctions
      existantes inchangées (progSauvegarder, progReset, progAjouterCreneau,
      progSupprimerCreneau, etc.).
    → progAfficherVide et progAfficherMeta rendues défensives (gardes sur
      l'existence des éléments supprimés).
    → suppression de l'appel obsolète à progChargerListe dans progReset.

    Nouvelles variables globales :
      PROG_ANNEES, PROG_ANNEE_DEFAUT, PROG_ETABS, PROG_REFS_CACHE.
    Variable PROG_LISTE conservée pour compat, non utilisée.
```

## Ce qui ne change pas

Toute la logique existante de l'écran Progression annuelle continue à
fonctionner à l'identique :

- calendrier visuel semainier (grille sept → août, vacances, jours fériés) ;
- ajout / modification / suppression de créneaux ;
- drag & drop des créneaux ;
- badge d'état (en_cours / valide / verrouille) ;
- boutons Marquer valide / Remettre en cours / Enregistrer / Réinitialiser ;
- alerte académie manquante ;
- transition automatique verrouille quand une évaluation est saisie.

## Nouveau comportement à l'ouverture

1. L'écran charge en parallèle `GET /api/annees-scolaires` et
   `GET /api/etablissements` (patch A).
2. Les 3 sélecteurs se peuplent.
3. Présélections par défaut :
   - année = `annee_courante` du JSON (2025-2026 aujourd'hui),
   - établissement = premier de la liste (présélectionné de fait s'il
     n'y en a qu'un),
   - niveau = N11 (inchangé).
4. Si les 3 valeurs sont non vides → recherche auto, la progression s'affiche.
5. Sinon → écran vierge, l'enseignant clique Rechercher après choix.

Quand l'enseignant change un critère, il doit cliquer Rechercher :
pas de recherche au changement, pas de raccourci Entrée.

## Comportement de l'encadré 0 résultat

Clic sur « + Créer la progression » :

- charge `GET /api/referentiels?niveau=<niv>` (patch A) ;
- si aucun référentiel disponible : message d'erreur avec orientation
  vers les ateliers de conception ;
- sinon : affiche le dialogue inline avec liste déroulante des
  référentiels, le plus récent présélectionné (suffixe « (recommandé) ») ;
- clic « Créer la progression » : `POST /api/progression/<niv>` avec
  `{annee, etablissement_id, referentiel_id, creneaux: []}` puis relance
  la recherche → la progression fraîchement créée est chargée.

## Déploiement

```powershell
cd D:\Enseignement\seqenseigne
# Dézipper l'archive, puis :
copy /Y patch_B\appli\templates\index.html  appli\templates\
copy /Y patch_B\appli\static\app.css        appli\static\
copy /Y patch_B\appli\static\app.js         appli\static\

# Puis Ctrl+F5 dans le navigateur (pas besoin de redémarrer Flask, c'est du front).
```

Aucune modification backend, aucune migration de base, aucun nouveau test
pytest (le frontend n'est pas testé par pytest).

## Tests de non-régression (manuels)

Dans l'ordre, à vérifier après déploiement :

1. **Ouverture de l'onglet Progression annuelle** : le bandeau bleu
   « Sélection de progression » est visible, les 3 sélecteurs sont
   remplis, la progression N11 2025-2026 se charge automatiquement
   dans le calendrier.
2. **Changement de niveau → Rechercher** : passer à N10, cliquer
   Rechercher → encadré ambre « Aucune progression pour 2025-2026 ·
   Collège les Hautes Ourmes · N10 » avec bouton « + Créer la progression ».
3. **Clic « + Créer »** : le dialogue apparaît, le référentiel N10_v2024
   est présélectionné, les 3 autres sont listés. Clic « Créer » → la
   progression se crée et se charge dans le calendrier (vide).
4. **Changement d'année (archivée)** : passer à 2023-2024, Rechercher →
   la progression N11 2023-2024 se charge normalement, calendrier visible.
5. **Retour à une année sans progression** : 2026-2027 par exemple →
   encadré ambre.
6. **Bouton « Ajouter un établissement »** : clic sur le lien sous les
   sélecteurs → l'utilisateur est emmené sur l'onglet Gestion des classes
   → sous-onglet Établissements (comportement préexistant).
7. **Calendrier + créneaux** : vérifier que l'ajout / la modification /
   la suppression de créneaux fonctionne toujours comme avant.
8. **Bouton Enregistrer / Réinitialiser / Marquer valide** : inchangé.

## Points d'attention

- **Cache de référentiels côté JS** : `PROG_REFS_CACHE` garde en mémoire
  les référentiels par niveau dans la session. Si tu ajoutes un nouveau
  référentiel dans l'UI (atelier de conception à venir), prévoir
  d'invalider ce cache ou d'appeler `delete PROG_REFS_CACHE[niv]`.
- **Ids HTML retirés** : les anciens `prog-niveau`, `prog-liste`,
  `prog-meta`, `prog-meta-etab`, `prog-meta-info` n'existent plus.
  Toute extension tierce qui y accédait planterait. Les fonctions
  `progAfficherVide` et `progAfficherMeta` restent appelables et sont
  défensives (gardes sur l'existence des éléments).
- **Validation des années saisies** : le frontend ne propose que des
  années présentes dans le JSON. Un appel forgé à la main avec une année
  exotique serait accepté par le backend (pas de validation côté serveur).
  À ajouter dans un patch ultérieur si tu veux verrouiller.
