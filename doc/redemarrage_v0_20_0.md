# Redémarrage v0.20.0 — UI de la grille horaire (établissement)

Première livraison du chantier « saisie de l'EdT » (v0.20.x). Interface
d'édition de la **grille horaire** d'un établissement (les créneaux M1–M4 /
S1–S4). Le backend existait déjà (livré en v0.19.1.16) ; cette livraison ajoute
uniquement l'UI, dans **Suivi de classe › Gestion › Établissements**.

## Contenu

Sur chaque carte d'établissement (panneau Établissements), un bouton **« Grille
horaire »** déplie un éditeur :
- tableau des créneaux : code (non modifiable), libellé, heure de début, heure
  de fin, demi-journée (Matin / Après-midi) ;
- modification à la volée (au `blur` de chaque champ, PUT) ;
- ajout d'un créneau (code + horaires + demi-journée) ;
- suppression (avec confirmation ; refusée côté serveur si le créneau est
  référencé par l'emploi du temps — la garde de cohérence de v0.19.1.17
  s'applique et le message d'erreur est affiché).

L'éditeur réutilise la zone dépliable partagée `etab-form-<id>` (comme le
formulaire « Modifier »). Le dernier bouton cliqué (Modifier / Grille horaire)
occupe la zone.

Backend utilisé (inchangé) :
- `GET/POST /api/etablissements/<id>/grille-horaire`
- `PUT/DELETE /api/grille-horaire/<creneau_id>`

## Fichiers

- `static/app.js` : bouton « Grille horaire » dans `etabCard`, et fonctions
  `grilleHoraireToggle/Charger/Render/Maj/Ajouter/Supprimer` (+ `_grilleStatus`).

## Tests

- vitest : 187 passed (0 régression).
- Syntaxe `app.js` vérifiée.
- API grille vérifiée (GET renvoie les 8 créneaux par défaut ; app.js servi avec
  les nouvelles fonctions ; bouton intégré à la carte établissement).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration (backend
grille déjà en place). Dans Suivi de classe › Gestion › Établissements, cliquer
« Grille horaire » sur un établissement.

## Suite

- **v0.20.1 — UI de saisie de l'emploi du temps** (le gros morceau) : grille
  jours × créneaux façon PDF, avec demi-cases semaine A / B (et case pleine AB),
  saisie de la classe et de l'usage par case. Emplacement : Suivi annuel, en
  première position (nouvel onglet « EdT »).
- Nommage à prévoir avec le chantier MER : renommer « Progression » en
  « Progression principale » et ajouter un onglet « Progression MER » au même
  niveau que « EdT ».
