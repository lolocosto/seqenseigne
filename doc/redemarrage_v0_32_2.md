# Redémarrage v0.32.2 — Planification hebdo : détail de séance enrichi

Enrichit le détail d'une séance (au clic) avec les informations demandées : MER
avec enveloppes, séquence principale avec nom, partie et rang de la séance.

## Contenu du détail

Au clic sur une séance :
- **MER** (gras) :
  - automatismes → **enveloppes à réviser** à cette séance (numéros), calculées
    via `leitner.enveloppes_a_reviser` sur le rang de la séance auto ;
  - progression → mention « progression ».
- **Principal** (gras) :
  - **code + nom** de séquence (le nom vient de `referentiel_sequences` via le
    référentiel de la progression) ;
  - **partie** (ex. « 1ère partie : … ») issue du créneau daté ;
  - **rang de la séance dans la partie** (séance n/N), compté sur les séances
    comptées de la classe dans la plage de dates du créneau.

Quand la progression n'est pas datée (cas des progressions 2026-2027 en cours de
construction), le principal affiche « séquence non datée / aucune » ; le rang
apparaît dès que l'EdT et la progression datée coexistent.

## Fichiers

- `services/planification_hebdo.py` : `detail_seance` enrichi (MER + enveloppes ;
  séquence code/nom/partie/rang). Réutilise projection, affectation MER, Leitner,
  progression réalisée.
- `static/planification_hebdo.js` : rendu du détail enrichi dans la modale.

## Tests

- `node --check` (exit 0) + exécution OK. vitest : 193 passed.
- Détail vérifié sur une progression datée : S14 « Algorithmique et
  programmation », 1ère partie. Logique de rang validée en isolation (séance
  3/4). La route renvoie tous les nouveaux champs.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.32.1.

## Suite

- v0.32.3 (prochaine) : association de documents à une séance (docs à publier du
  référentiel interne / attachés aux parties du référentiel externe, de la
  séquence et en option la suivante).
- puis rappels d'impression ; puis tuile « Séances de la semaine » cliquable.
