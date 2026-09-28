# patch v0.10.1 — Atelier d'assemblage de séquence (UI)

**Date** : 30 avril 2026

**Périmètre** : UI complète + 2 routes backend complémentaires.
Premier draft livrable de l'atelier d'assemblage. La documentation utilisateur viendra
au fur et à mesure du retour d'usage.

**Score tests** : 1522/1522 passent (4 skipped historiques inchangés).
14 nouveaux tests par rapport à v0.10 pour couvrir les fonctions ajoutées
(`creer_objectif_simple`, `supprimer_objectif`).

---

## Vue d'ensemble

L'onglet **Séquence** contient désormais deux modes coexistants, basculables
via un toggle dans la toolbar :

- **◆ Assemblage** (par défaut) : nouvel atelier avec drag-and-drop, sidebar
  méthodes/exercices à gauche, parties cartonnées au centre.
- **⚙ Édition avancée** : l'éditeur v2 historique, intact. Conservé tant que
  toutes les fonctionnalités fines ne sont pas couvertes par l'assemblage.

Les deux modes opèrent sur les mêmes données BDD. On peut basculer à tout
moment et retrouver la séquence en cours dans l'autre mode.

---

## Architecture UI

### Fichiers nouveaux

- `static/atelier_seqniv_assemblage.js` (~750 lignes) — IIFE, hooks publics
  `seqnivAssemblageRafraichir()` et `seqnivBasculerMode(mode)`.

### Fichiers modifiés

- `templates/index.html`
  - Refonte du panneau `#atl-livret` : sidebar polymorphe, toolbar avec
    toggle, deux conteneurs frères `#liv-atl-content-assemblage` (visible
    par défaut) et `#liv-atl-content-v2` (caché par défaut).
  - Inclusion du nouveau script avant la balise `</body>`.
  - Nouvelle section **Préférences > Atelier d'assemblage de séquence**
    avec 4 champs (nom, critères F/A/E) modifiables et persistés.

- `static/app.css`
  - Bloc `v0.10.1` à la fin : ~360 lignes de styles dédiés (toggle modes,
    sidebar, parties, objectifs ouverts/fermés, zones de drop, chips d'exos,
    section Préférences).
  - Toutes les couleurs viennent des variables CSS existantes ; rien de
    durci en valeur littérale.

- `static/app.js`
  - `initLivret()` appelle maintenant les **deux** hooks (`seqnivAssemblageRafraichir`
    + `seqnivEditRafraichir`). Le second court-circuite quand son conteneur
    est caché.
  - 2 nouvelles fonctions Préférences : `prefChargerCriteresConnaitre()` et
    `prefEnregistrerCriteresConnaitre()`. Hookées sur l'entrée dans l'onglet.

- `static/ateliers_seqniv_v2_edit.js`
  - Ajout d'une garde au début de `_rafraichirEdition()` : early-return si
    le conteneur `#liv-atl-content-v2` est caché. Évite les doubles fetchs
    inutiles au chargement initial.

---

## Modèle d'interaction

### Mode 'assemblage' — sidebar polymorphe

- **Aucun objectif ouvert** : la sidebar montre la **liste des méthodes** de
  la séquence courante, draggables. Une méthode déjà placée dans un
  objectif apparaît grisée, non draggable, avec un tag `→ P2` indiquant
  la partie où elle est. Affichage statique, pas de scroll-to.

- **Un objectif ouvert** : la sidebar montre les **exercices** de la
  séquence en 4 catégories pliables (EA, F, A, E), chaque exo draggable.
  Pas de dédoublonnage : un même exo peut être placé dans plusieurs
  objectifs (PK = (objectif, série, exercice), donc unicité dans une
  série donnée).

L'état « objectif ouvert » est persisté côté serveur dans
`ui_etat_atelier_sequence` (livré en v0.10), donc recharger la page ou
basculer d'atelier puis revenir conserve l'objectif ouvert.

### Zone centrale — pile de parties

Chaque partie est une carte avec :
- En-tête : « Partie N », bouton Supprimer, handle de drag.
- **Zone Révision/Approche** : 2 colonnes côte à côte. Si on est en N10
  (1ère année du cycle), la colonne Révision est visible mais grisée
  avec « Indisponible » — comme prévu dans le cahier des charges.
- **Zone Objectifs** : empilement vertical des objectifs existants + une
  zone de drop générique en bas, avec bouton « + Activer Connaître »
  intégré et invitation « Glisser une méthode pour créer un objectif ».

### Objectifs

- **Fermé** : carte compacte (code, nom, résumé). Cliquable pour ouvrir.
- **Ouvert** : seul objectif éditable à un moment donné. Affiche :
  - Input éditable du nom.
  - Méthode liée (si présente) avec bouton « Délier ».
  - 3 textareas pour les critères F/A/E.
  - 3 zones de drop (Série F, Série A, Série E) pour déposer les exos.
  - Tous les exos déposés sont des chips avec ✕ et numéro d'ordre.

L'ouverture d'un objectif :
1. Bascule la sidebar du mode « méthodes » vers « exercices ».
2. Persiste l'ID de l'objectif ouvert via PUT /api/v2/...etat-ui.
3. Ré-affiche la zone centrale avec l'objectif déplié.

### Drag-and-drop

Drag-and-drop natif HTML5 (`draggable=true`, `dragstart/dragover/drop`).
Pas de lib externe, par cohérence avec les autres ateliers de l'app.

Les drags supportés :
| Source | Destination | Effet |
|---|---|---|
| Méthode (sidebar) | Zone Objectifs d'une partie | Crée un objectif lié à cette méthode et l'ouvre |
| Exo catalogue (sidebar, obj ouvert) | Zone série F/A/E de l'obj ouvert | POST /objectifs/<id>/exos |
| Exo catalogue (sidebar) | Zone Approche d'une partie | POST /parties/<id>/exos-revision-approche (type=EA) |
| Carte de partie | Autre carte de partie | PATCH /parties/ordre (réordonnancement) |

Drags **non supportés en v0.10.1** (à venir si besoin) :
- Cross-partie d'un objectif (utiliser l'éditeur v2 si nécessaire).
- Cross-zone d'un exo (R↔EA, F↔A, etc.).
- Drag d'exo de révision (la sidebar ne montre les exos R d'un n-1 que
  s'ils sont déjà placés). Pour ajouter de la révision, l'éditeur v2
  fournit le sélecteur.

---

## Backend complémentaire

Deux nouvelles fonctions et routes nécessaires au support des dépôts de
méthode et de la suppression d'objectif :

### Service — `services/v2_edition.py`

- **`creer_objectif_simple(conn, partie_id, nom, methode_id, critere_*)`**
  Crée un objectif avec code auto-incrémenté respectant la convention
  `0X / 1X / 2X` (chiffre des dizaines = numero_partie - 1, chiffre des
  unités = prochain libre). Lie une méthode si `methode_id` fourni.

- **`supprimer_objectif(conn, objectif_id)`** Suppression simple ; les
  exos rattachés et les notions partent en cascade (FK ON DELETE CASCADE),
  les références dans `ui_etat_atelier_sequence` partent en SET NULL.

### Routes — `routes/v2_edition.py`

| Méthode | URL | Rôle |
|---|---|---|
| POST | `/api/v2/parties/<partie_id>/objectif` | Crée un objectif (drop méthode) |
| DELETE | `/api/v2/objectifs/<objectif_id>` | Supprime un objectif |

### Configuration — `services/configuration.py`

Nouvelle clé `atelier_assemblage_criteres_connaitre` dans `CLES_DEFAUT` :
```python
{
    'nom':       'Connaître les notions et les méthodes',
    'critere_F': 'A noté la trace écrite en classe.',
    'critere_A': 'A complété les fiches de résumé.',
    'critere_E': "Sait résumer le cours à l'oral.",
}
```
Et accesseur typé `Configuration.atelier_assemblage_criteres_connaitre()`
qui complète avec les défauts si la config est partielle.

Le frontend lit ces valeurs au chargement de l'atelier (cache local
`CRIT_DEFAUTS`) et les envoie au backend lors du clic sur
« + Activer Connaître ».

---

## Tests ajoutés

`tests/test_v0_10_assemblage.py` étendu avec 14 tests :

- `TestCreerObjectifSimple` (6) — création, code auto-incrémenté, méthode liée.
- `TestSupprimerObjectif` (3) — suppression et cascades.
- `TestRoutesObjectifSimple` (5) — intégration via client Flask.

Total fichier : 88 tests (74 v0.10 + 14 v0.10.1).

---

## Procédure de test manuel après déploiement

Un déroulé recommandé pour vérifier que tout fonctionne :

1. **Préférences** : aller dans Préférences, vérifier que la nouvelle
   section « Atelier d'assemblage de séquence » s'affiche. Modifier le
   critère F (par exemple « Test critère F »), Enregistrer. Recharger la
   page et revenir : la valeur doit être conservée. Restaurer la valeur.

2. **Onglet Séquence** : ouvrir l'atelier Séquence sur N11/S03 (qui a déjà
   des parties et objectifs en BDD). Vérifier que le mode Assemblage
   s'affiche par défaut, avec les parties existantes. Basculer vers
   « ⚙ Édition avancée » : l'ancien éditeur revient. Re-basculer.

3. **Drag d'une méthode** : la sidebar montre les méthodes de la séquence.
   En faire glisser une dans la zone d'objectifs d'une partie. Un nouvel
   objectif doit apparaître, déjà ouvert pour édition, avec la méthode
   liée. La sidebar doit basculer vers les exercices.

4. **Activer Connaître** : sur une partie qui n'a pas d'objectif Connaître,
   cliquer « + Activer Connaître » dans la zone d'objectifs. L'objectif
   `0X` doit apparaître avec les critères pré-remplis depuis Préférences.

5. **Drop d'exos** : sur l'objectif ouvert, faire glisser un exo de la
   sidebar (par ex série F) vers la zone « Série F » de l'objectif. Le
   chip apparaît avec son numéro d'ordre.

6. **Drop révision/approche** : avec un objectif ouvert (donc sidebar =
   exos), faire glisser un exo vers la zone Approche d'une partie. Le
   chip apparaît dans la zone EA.

7. **Réordonner les parties** : faire glisser la carte « Partie 2 » au-
   dessus de « Partie 1 ». Les numéros se réajustent. (Note : les codes
   d'objectifs ne sont pas auto-renumérotés — c'est volontaire ; pour
   suivre la convention, faire la renumérotation explicite ensuite via
   l'éditeur v2.)

8. **Persistance objectif ouvert** : laisser un objectif ouvert, basculer
   vers un autre atelier (Exercice par exemple), revenir : l'objectif
   doit être encore ouvert.

9. **Suppression** : ✕ sur un objectif → confirmation → suppression.
   ✕ sur une partie vide → confirmation → suppression.

---

## Pas inclus dans v0.10.1 (différé)

- **Réordonnancement des objectifs *à l'intérieur* d'une partie** par drag.
  Le service backend (`reordonner_objectifs_dans_partie`) est livré en
  v0.10 mais pas branché à l'UI. À ajouter quand le besoin se fera sentir.
- **Réordonnancement des exos** dans une zone (R/EA d'une partie, série
  d'un objectif). Idem : services prêts, pas de drag-handle dans l'UI.
- **Cross-partie pour les objectifs.** À voir selon le retour d'usage.
- **Auto-renumérotation des codes d'objectifs après réordonnancement de
  parties.** Pourrait être ajouté comme « renuméroter les codes » dans la
  toolbar.

---

## Pièges connus / points d'attention

- **Première ouverture d'une séquence après déploiement** : l'état UI
  (`ui_etat_atelier_sequence`) n'a pas encore de ligne pour cette séquence.
  Le backend retourne `objectif_ouvert_id: null` et le mode démarre tous
  objectifs fermés. Comportement attendu.

- **Le mode est mémorisé en sessionStorage**, pas en BDD. Si tu fermes
  l'onglet du navigateur, l'app rouvrira en mode Assemblage par défaut.

- **Les valeurs hardcodées dans l'HTML** des champs Préférences (texte
  par défaut visible avant chargement async) sont juste un fallback
  visuel. Le vrai chargement se fait via `prefChargerCriteresConnaitre()`
  à l'entrée dans l'onglet et écrase les valeurs HTML.

- **Drag de chip d'exo** : si un drop ne fonctionne pas, un message
  d'erreur orange apparaît dans la toolbar (zone `liv-atl-status`).
  Notamment, le déplacement entre zones (R↔EA, F↔A) n'est pas géré ;
  retire et redépose.
