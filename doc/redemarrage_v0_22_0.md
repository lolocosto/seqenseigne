# Redémarrage v0.22.0 — Mises en route : cartes d'automatismes (Leitner)

Première livraison du chantier MER. Une classe peut être marquée « fait des
mises en route » en mode **automatismes** ; l'appli produit alors le planning
annuel des enveloppes Leitner à réviser, et un PDF A3 paysage à afficher.

## Marquage MER par classe

Deux colonnes sur `classes` (migration idempotente) :
- `mer_active` (0/1) : la classe fait-elle des mises en route.
- `mer_mode` : `automatismes` (Leitner) | `progression` | `panache`
  (les deux derniers modes viendront plus tard).

Édité dans le **détail de la classe** (bloc « Mises en route »), à côté du
rythme A/B. On **sélectionne** les classes qui font des MER (les autres n'en
font pas) — ce qui couvre les trois cas : aucune, exclure un niveau, exclure une
classe.

## Ordonnancement Leitner

4 enveloppes numérotées **1 à 4**, cadence géométrique ×2 :

| Enveloppe | Révisée |
|-----------|---------|
| 1 | chaque séance |
| 2 | une séance sur 2 |
| 3 | une séance sur 4 |
| 4 | une séance sur 8 |

Une carte « connue » (au-delà de l'enveloppe 4) sort du dispositif (géré hors
logiciel : l'élève rend la carte, l'enseignant la redemande à son tour
d'interrogation).

Le compteur avance d'une séance par séance d'automatismes. En mode
« automatismes pur », toutes les séances comptées de la classe sont des séances
d'automatismes → le rang Leitner = le numéro de séance de la projection
(réutilise EdT × calendrier × indisponibilités des livraisons précédentes).

Fonction pure `services/leitner.enveloppes_a_reviser(n)` / `planning(seances)`.

## Planning A3 paysage (PDF LaTeX)

`services/planning_automatismes_tex.generer_planning_tex` produit un source
LaTeX **A3 paysage**, organisé par mois (n° séance, date, enveloppes), avec la
légende de la cadence. Compilé via la chaîne existante (`compiler_atome`).

## API

- `GET /api/classes/<id>/planning-automatismes` : planning JSON (séances +
  enveloppes).
- `GET /api/classes/<id>/planning-automatismes.pdf` : PDF A3 à imprimer /
  afficher (ouvert dans un nouvel onglet depuis le détail classe).

## Fichiers

- `persistence/sqlite_store.py` : colonnes `mer_active`/`mer_mode` +
  propagation dans l'INSERT/UPDATE de `classes`.
- `services/classes.py` : `modifier_classe` accepte mer_active/mer_mode (+
  seances_A/B).
- `services/leitner.py` (nouveau) : cadence + planning (pur).
- `services/planning_automatismes_tex.py` (nouveau) : source LaTeX A3.
- `routes/leitner.py` (nouveau) : planning JSON + PDF.
- `app.py` : blueprint `bp_leitner`.
- `templates/index.html` : bloc « Mises en route » dans le détail classe.
- `static/app.js` : remplissage + `sauverMerClasse`, `_majBlocMer`,
  `ouvrirPlanningAutomatismes`.
- `tests/test_v0_22_0_leitner.py` (nouveau, 4 cas).
- `doc/ROADMAP.md` : filtrage classes, tableau de bord hebdo, panachage.

## Tests

- `tests/test_v0_22_0_leitner.py` : 4 passed (cadence, 4 enveloppes, planning,
  migration).
- vitest : 193 passed (0 régression). Syntaxe OK.
- Circuit MER vérifié (PUT + persistance + relecture).
- Génération A3 vérifiée : PDF compilé au format A3 paysage (1190×842 pts), 1
  page, titre + légende + tableaux par mois. (En sandbox, avertissement babel
  `french` sans conséquence ; OK avec le MiKTeX de production.)

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Les colonnes se créent au
premier lancement. Dans le détail d'une classe : cocher « fait des mises en
route », mode « automatismes », puis « Planning des automatismes (PDF A3) ».

## Suite

- v0.23.x : correctifs de l'audit (sécurité / RGPD / RGAA).
- v0.24.x : progression de séquences de mise en route (mode `progression`).
- Roadmap : filtrage de la liste des classes, tableau de bord hebdomadaire,
  panachage automatismes/progression.
