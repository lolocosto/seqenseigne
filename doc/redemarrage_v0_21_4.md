# Redémarrage v0.21.4 — Décalages de progression par classe (socle) + indispos au calendrier

Première des deux livraisons sur l'effet des indisponibilités sur la progression
principale. Choix de modèle : **option 3** — la progression reste **commune** à
un niveau/année (partagée par les classes) ; les décalages propres à une classe
sont une couche **dérivée et non destructive**.

## Modèle : décalages de progression

Un décalage = « à partir de telle date, tout glisse de N semaines » pour UNE
classe (ex. voyage scolaire d'une semaine). La progression commune n'est jamais
modifiée ; les décalages sont appliqués à la volée pour produire la
« progression annuelle réalisée » d'une classe.

- Table `decalage_progression(id, classe_id, annee, a_partir_de, nb_semaines,
  motif, indispo_id)` (migration idempotente). `indispo_id` (optionnel) trace
  l'indisponibilité qui a motivé le décalage.
- Fonction pure `appliquer_decalages(creneaux, decalages)` : décale
  `date_debut`/`date_fin` d'un créneau si sa date de début est ≥ au
  `a_partir_de` d'un décalage ; **cumulatif** (plusieurs décalages) ; **non
  destructif** (retourne une copie).
- CRUD : `GET/POST /api/classes/<id>/decalages-progression`,
  `PUT/DELETE /api/decalages-progression/<id>`. Validations : date valide,
  nb_semaines ≥ 1.

## Affichage des indisponibilités sur le calendrier de la progression

L'atelier Progression charge désormais les indisponibilités de
l'année/établissement et les affiche sur les semaines concernées (pastille
violette ⛔ avec motif + détail au survol). Nouvelle entrée « Indisponibilité »
dans la légende. Une indispo de portée « classes » est signalée « (classe) ».

Note : les indispos sont chargées avec le calendrier (au chargement de la
progression). Après ajout d'une indispo dans son onglet, recharger la
progression pour la voir.

## Vocabulaire (préparé pour v0.21.5)

- Aucune classe sélectionnée → « progression annuelle commune prévue » (sans
  décalage).
- Une classe sélectionnée → « progression annuelle réalisée » (décalages de la
  classe appliqués). La vue par classe et le bouton de décalage arrivent en
  v0.21.5.

## Fichiers

- `persistence/sqlite_store.py` : table `decalage_progression`.
- `services/decalage_progression.py` (nouveau).
- `routes/decalage_progression.py` (nouveau).
- `app.py` : blueprint `bp_decalage_progression`.
- `static/atelier_progression.js` : chargement + affichage des indisponibilités
  (helper `_indisposDeLaSemaine`, rendu dans `_ligneSemaine`, légende).
- `tests/test_v0_21_4_decalage_progression.py` (nouveau, 5 cas).
- `doc/ROADMAP.md` : résorption des débordements, option 2 (plan B), v0.21.5.

## Tests

- `tests/test_v0_21_4_decalage_progression.py` : 5 passed (table, application
  seuil + non destructif, cumul, copie sans décalage, CRUD + validations).
- vitest : 193 passed (0 régression). Syntaxe atelier_progression.js OK, 4
  routes décalage exposées.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. La table se crée au premier
lancement. Les indisponibilités s'affichent dans l'atelier Progression.

## Suite

- v0.21.5 : vue « progression annuelle réalisée » par classe (sélecteur de
  classe → décalages appliqués) + bouton « décaler pour cette classe » depuis
  une indisponibilité de portée « classes ».
- Roadmap : résorption des débordements de fin d'année.
