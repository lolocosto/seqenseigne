# Redémarrage v0.19.1.18 — Projection séance → date + heure

Quatrième livraison du chantier « progressions à la séance ». L'EDT devient un
**planning de séances datées** sur l'année scolaire, en tenant compte des
vacances, des jours fériés et de la convention d'alternance A/B. Sans UI ;
fonction pure + route d'orchestration + tests.

## Fonction pure `services/projection_seances.py`

`projeter(annee_scolaire, edt_classe, grille, vacances, feries,
date_min=None) -> [seances]`, testable sans réseau (reçoit vacances/fériés déjà
récupérés). Chaque séance : `{numero, date, jour, creneau_code, heure_debut,
heure_fin, semaine_label}`.

Conventions implémentées :
- **Bornes** de l'année "YYYY-YYYY" : 1er août YYYY → 31 juillet YYYY+1 (borne
  neutre entre deux années ; en France la rentrée est toujours en septembre).
- **Semaine de rentrée** (1re semaine avec cours effectifs) : ignorée.
- **1re semaine comptée** (= 2e) : étiquetée **B**, puis A, B, A…
- **Semaine sans cours effectif** (hors année, entièrement en vacances ou
  fériée) : sautée, l'alternance A/B **ne progresse pas**.
- **Jours fériés / vacances individuels** : sautés (l'alternance progresse
  quand même à l'échelle de la semaine).
- **Numéro de séance** : continu sur l'année, par classe (rang de la séance).
- **date_min** : borne basse optionnelle (voir ci-dessous).

## Borne basse au 1er septembre (systématique)

Constat : les données officielles (education.gouv) ne contiennent **jamais** les
vacances d'été de **début** d'année scolaire (elles relèvent de l'année
précédente). Juillet-août ne sont donc couverts par aucune période. La route
applique donc **systématiquement** `date_min = "{YYYY}-09-01"` : aucune séance
n'est projetée avant le 1er septembre. Correct puisque la rentrée est toujours
en septembre en France, et sans effet quand les vacances d'été de fin d'année
sont présentes.

## Alerte « vacances absentes »

Si les vacances ne peuvent pas être récupérées du tout (problème réseau ou zone
inconnue — ne devrait jamais arriver en pratique), la route remonte
`vacances_absentes: true` et un message dans `avertissements[]`. **L'affichage
de cette alerte dans l'UI reste à faire** (noté dans `doc/ROADMAP.md`) : pour
l'instant l'information est disponible dans la réponse de l'API.

## Route `routes/projection.py`

`GET /api/classes/<classe_id>/projection[?annee=]` :
- résout établissement + académie → zone de vacances ;
- récupère l'EDT de la classe filtré sur `USAGES_COMPTES` (classe_entiere), la
  grille horaire, les vacances (zone) et les fériés ;
- appelle `projeter(...)` avec la borne septembre ;
- renvoie `{classe_id, annee, zone, vacances_absentes, avertissements,
  nb_seances, seances}`.

## Fichiers

- `services/projection_seances.py` (nouveau).
- `routes/projection.py` (nouveau).
- `app.py` : import + enregistrement du blueprint `bp_projection`.
- `tests/test_v0_19_1_18_projection.py` (nouveau, 8 cas).
- `doc/ROADMAP.md` : L4 marquée faite + note sur l'alerte UI à faire.

## Tests

- `tests/test_v0_19_1_18_projection.py` : 8 passed (bornes, rentrée ignorée +
  1re semaine B, filtrage A/B par semaine, saut semaine de vacances sans
  double-saut d'alternance, saut férié, numérotation continue, effet et
  non-effet de date_min).
- pytest ciblé (projection + edt + grille + classes) : 77 passed, 0 régression.
- vitest : 187 passed. Démarrage app + route projection vérifiés.
- Vérifié avec les vraies données education.gouv (zone B / Rennes) : projection
  démarrant le 8 septembre 2025, aucune séance en août ni pendant la Toussaint.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Rien à migrer (pas de nouvelle
table). La route est disponible immédiatement. La récupération des vacances
utilise le cache calendrier existant (réseau au premier appel par zone/année).

## Suite

- Livraison 5 : règle d'affectation des mises en route / automatismes aux
  séances projetées (a par jour de semaine / b par répartition + retraits
  manuels ponctuels type évaluation).
- Puis : progression de séquences de mise en route, ordonnancement Leitner, UI
  (dont l'affichage de l'alerte « vacances absentes »).
