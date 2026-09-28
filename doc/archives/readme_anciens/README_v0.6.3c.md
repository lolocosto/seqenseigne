# seqenseigne v0.6.3c — calendrier scolaire visuel + états de progression

Dernière grosse livraison du chantier Progression annuelle. Remplace la
liste textuelle des créneaux par un vrai calendrier semainier, avec
vacances scolaires (selon l'académie de l'établissement) et jours
fériés. Introduit les 3 états de progression : `en_cours`, `valide`,
`verrouille`, avec transitions automatiques et manuelles.

**Prérequis** : v0.6.3a (schéma etablissements + services calendrier) et
v0.6.3b (UI gestion établissements + fusion) déployées.

## Calendrier visuel

### Panneau gauche refondu

La sidebar de Progression annuelle (380px désormais, au lieu de 260)
contient :

- Les sélecteurs niveau + progression (inchangé)
- **Badge d'état** à côté du titre : ✏️ En cours (bleu) / ✓ Validée
  (vert) / 🔒 Verrouillée (rouge)
- **Bandeau d'alerte** si l'établissement n'a pas d'académie
- **Calendrier semainier** septembre → août avec :
  - Séparateurs de mois
  - Une ligne par semaine (date du lundi)
  - Vacances scolaires en fond rouge pâle + label "🌴 Vacances de la
    Toussaint" etc.
  - Jours fériés en badges orange "🔸 Toussaint", "🔸 Noël"…
  - **Créneaux bleus** posés aux semaines couvertes par `date_debut` →
    `date_fin`, cliquables pour sélection
- Boutons Marquer valide / Remettre en cours (selon l'état)
- Boutons Enregistrer / Réinitialiser (existants)

### Blocage quand l'établissement n'est pas utilisable

Conformément à la décision "griser et imposer" : si l'établissement de
la progression n'a pas d'académie renseignée, le calendrier est
remplacé par un message "Calendrier indisponible sans académie", et
tous les contrôles d'édition (formulaire Ajouter un créneau, Marquer
valide) sont grisés à `opacity 0.4` et `pointer-events none`.

Un bouton "Aller à la gestion des établissements" dans le bandeau
amène directement au bon sous-onglet.

## États de progression

### Trois états

- **`en_cours`** (défaut) : édition libre. Bouton "Marquer valide"
  disponible.
- **`valide`** (manuel) : état intermédiaire pour indiquer qu'on est
  satisfait de la progression. L'édition reste possible. Bouton
  "Remettre en cours" disponible.
- **`verrouille`** (automatique) : toutes les éditions (ajout/
  modification/suppression de créneaux) sont désactivées. Les boutons
  Marquer valide et Remettre en cours sont masqués.

### Transitions

| Depuis      | Vers         | Qui               | Comment                                       |
| ----------- | ------------ | ----------------- | --------------------------------------------- |
| en_cours    | valide       | enseignant (UI)   | bouton "Marquer valide"                       |
| valide      | en_cours     | enseignant (UI)   | bouton "Remettre en cours"                    |
| en_cours    | verrouille   | automatique       | 1ʳᵉ évaluation saisie dans une classe liée    |
| valide      | verrouille   | automatique       | idem                                          |
| verrouille  | (bloqué)     | —                 | pas de déverrouillage automatique en v0.6.3c  |

Le déverrouillage (avec suppression des évaluations associées) est
prévu pour v0.6.4 ou plus tard.

### Nouvelle route

`POST /api/progression_id/<id>/etat` avec body `{"etat":
"en_cours"|"valide"}`.
Retourne `409` si la progression est déjà `verrouille`.

### Verrouillage automatique

Le même hook qui verrouille le référentiel dès qu'une évaluation est
saisie (existant depuis v0.6.1) verrouille maintenant aussi la
progression liée. Implémenté dans `routes/suivi.py::_verrouiller_referentiel_de_classe`,
appelé par `/api/suivi/exo` et `/api/niveaux/set`.

Robustesse ajoutée : si `classe.progression_id` est NULL (cas historique
des classes non-principales d'un groupe, déjà géré en v0.6.2d), on
retrouve la progression par clé métier (niveau, annee, etablissement).

## Roadmap notée (pour plus tard)

**Verrouillage granulaire** — Laurent suggère un verrouillage par
créneau et par séquence, plutôt que par progression entière. L'idée :
tant qu'aucune évaluation n'est saisie sur les objectifs d'un créneau,
ce créneau reste modifiable même si d'autres créneaux de la même
progression sont verrouillés. Impact schéma (colonne `etat` sur
`creneaux`). À traiter dans une future version dédiée (pas en 0.6.3d).

## Tests

**361 tests verts** (355 + 6 nouveaux).

Nouveaux tests (`test_progression_etat.py`) :
- `verrouiller_progression` : passe à verrouille, idempotent
- `changer_etat_progression` : en_cours ↔ valide, refus sur valeur
  invalide
- Intégration : saisie d'évaluation via `/api/niveaux/set` déclenche le
  verrouillage automatique

## Validation Playwright

Scénarios testés visuellement :

1. **Progression "Collège Les Hautes Ourmes" (Rennes)** : 6 cases de
   créneaux affichées (2 créneaux × 3 semaines chacun), 9 semaines de
   vacances en rouge pâle (Toussaint + Noël + Hiver), 9 badges de
   jours fériés répartis dans l'année. Badge "✏️ En cours" en haut.
2. **Progression "Collège Sans Académie"** : message "Calendrier
   indisponible sans académie" + bandeau d'alerte avec bouton "Aller à
   la gestion des établissements". Formulaire d'ajout grisé.
3. **Verrouillage auto** : saisie d'un niveau `I/F/A/E` via
   `/api/niveaux/set` → la progression de la classe passe de
   `en_cours` à `verrouille`. Sa voisine sur un autre établissement
   reste intacte.

## Fichiers

```
appli/persistence/sqlite_store.py   (verrouiller_progression, changer_etat_progression)
appli/routes/suivi.py               (verrouillage auto enrichi, robustesse FK)
appli/routes/progression.py         (endpoint POST /etat)
appli/static/app.js                 (~240 lignes calendrier + état + UI bloquée)
appli/static/app.css                (styles calendrier)
appli/templates/index.html          (sidebar 380px refondue avec badge + alerte)
appli/tests/test_progression_etat.py (nouveau, 6 tests)
```

## Déploiement

```powershell
# Copier les 7 fichiers (pas de migration DB — la v0.6.3a a tout posé)
# Redémarrer Flask
# Ctrl+F5 dans le navigateur
```

## Vérifications recommandées côté Laurent

1. **Gestion des classes → Établissements** : renseigner l'académie
   pour chaque établissement (au moins "Rennes" pour Les Hautes Ourmes)
2. **Progression annuelle** : ouvrir une progression, vérifier que le
   calendrier s'affiche avec les vacances Zone B et les jours fériés
3. **Saisie d'un niveau** dans Suivi des séquences → revenir sur
   Progression → le badge doit passer à "🔒 Verrouillée", les
   contrôles d'édition disparaissent

## Après v0.6.3c

Le chantier Progression annuelle est complet. Prochaines étapes à
choisir :

- **v0.6.3d (prévu)** : détail créneau enrichi avec liste d'objectifs,
  suppression de la vue synthétique devenue redondante.
- **Plus tard** : verrouillage par créneau, déverrouillage explicite
  avec suppression en cascade des évaluations, import/export des
  évaluations, écran de gestion des référentiels (duplication,
  déverrouillage manuel).
