# Inventaire — logique métier côté JS (chantier de rapatriement serveur)

Objet : recenser la logique **métier** (règles de gestion) qui subsiste côté
client (JS), pour planifier son rapatriement côté serveur (Python). La
**présentation** (comment dessiner, couleurs, marqueurs, mise en page) reste
côté JS et n'est pas concernée.

Frontière retenue (validée) : les **règles de gestion** (calculs de dates,
projections, cadences, validations, dérivations) vont au serveur ; le JS
demande le résultat et l'affiche.

Statut de chaque élément :
- 🔴 **à migrer** : règle métier encore en JS, à rapatrier.
- 🟡 **à examiner** : cas limite (mi-métier, mi-présentation) à trancher.
- 🟢 **fait / non concerné** : déjà côté serveur, ou pure présentation.

---

## Déjà rapatrié

- 🟢 **Décalage de progression** (semaines neutralisées) — rapatrié en v0.27.3.
  Route `/api/classes/<id>/progression-realisee` ; le JS affiche les créneaux
  décalés reçus. L'ancienne fonction JS `appliquerDecalagesJS` est supprimée.

## Migré (v0.27.4) — anciennement 🔴

- 🟢 **`_semainesTouchees(ind)`** — MIGRÉ v0.27.4 : `services/indisponibilites.semaines_touchees`, exposé via l'API (ind.semaines_touchees). Ancien (`atelier_progression.js`) : calcule le nombre
  de semaines civiles touchées par une indisponibilité (valeur par défaut du
  décalage). C'est une règle de calendrier → à exposer côté serveur (p. ex.
  dans la réponse de l'API indisponibilités, ou un endpoint dédié). Impact
  faible, migration simple.

- 🟢 **`anneeScolaireCourante()`** — MIGRÉ v0.27.4 : l'année courante vient du serveur (/api/annees-scolaires → ANNEE_COURANTE) ; le JS ne calcule plus. Ancien (`app.js`) : déduit l'année scolaire de la
  date. Le serveur a déjà `annees_scolaires.courante()` et
  `annee_scolaire_de_date()`. Le JS devrait lire l'année courante fournie par le
  serveur (déjà injectée dans plusieurs réponses) plutôt que la recalculer.
  Migration : supprimer le calcul JS, s'appuyer sur la valeur serveur.

## À examiner (🟡)

- 🟢 **Cadence Leitner à l'affichage** — VÉRIFIÉ v0.27.4 : aucun recalcul en JS. Ancien : le planning des automatismes est
  calculé côté serveur (bien), mais vérifier qu'aucun écran ne recalcule les
  enveloppes en JS. (Rien trouvé de flagrant ; à confirmer lors de la migration.)

- 🟢 **`prefRecalculerDerives()` / `prefDerive()`** — EXAMINÉ v0.27.4 : présentation d'un formulaire de préférences (aide à la saisie), sans règle métier partagée → gardé en JS. Ancien (`app.js`) : dérive des
  chemins de fichiers à partir d'une racine (préférences). C'est une règle de
  dérivation, mais purement locale à la configuration et sans données
  partagées ; probablement acceptable en JS (présentation d'un formulaire).
  À trancher : si la dérivation doit être identique côté serveur (ex. pour la
  compilation), la centraliser.

- 🟢 **Projection à la séance côté affichage** — VÉRIFIÉ v0.27.4 : aucune projection locale en JS. Ancien : la projection (EdT × calendrier
  × indisponibilités) est côté serveur (bien). Vérifier que les ateliers ne
  refont pas de projection locale.

## Non concerné / présentation (🟢)

- 🟢 Tri, filtrage d'affichage, mise en forme des dates (jj/mm), couleurs,
  marqueurs, gestion des onglets et sélecteurs, viewer PDF, drag-drop (geste
  d'interface). Ce sont des choix de présentation, à garder en JS.
- 🟢 `_lundiDe`, `_jourSemaine`, `_bornesAnneeScolaire` utilisés **uniquement**
  pour dessiner le calendrier (positionner les semaines) : présentation, à
  garder — tant qu'ils ne portent pas de règle métier (le décalage, lui, est
  parti côté serveur).

---

## Méthode de migration proposée (chantier B)

1. Pour chaque 🔴, exposer le résultat via une API (ou l'ajouter à une réponse
   existante), écrire le calcul en Python avec tests, puis remplacer le calcul
   JS par la lecture du résultat.
2. Traiter les 🟡 au cas par cas (trancher métier vs présentation).
3. À chaque migration : supprimer le code JS mort, vérifier vitest + pytest.
4. Avancer **écran par écran**, sans big-bang, pour garder l'appli fonctionnelle.

Priorité suggérée : `_semainesTouchees` et `anneeScolaireCourante` d'abord
(simples, sans risque), puis confirmation des 🟡.
