# Redémarrage v0.48.4 — Harmonisation des écrans de référentiels

## Décisions validées

- **Nom calculé pour tous les référentiels** (internes et externes) :
  « 4e — 2026-2027 — Principal » ou « … — MER », plus la lettre de version
  (b, c…) si plusieurs ; description libre facultative affichée dessous.
  Internes : année déduite de la version (« 2025b » → 2025-2026, lettre b).
- **Type principal / MER pour tous**, choisi à la création (sélecteur à côté
  de « + Créer »). Les internes existants sont « principal ». Un référentiel
  de type MER n'est **pas** proposé à la progression principale (la source
  interne de la progression de MER viendra avec les référentiels internes de
  MER, cf. ROADMAP).
- **Écran des référentiels externes** organisé comme l'écran interne :
  liste à gauche (principaux et MER, pastille d'état, nom calculé,
  description), détail à droite ; création par type + description. Le
  détail d'un principal reprend l'éditeur v0.48.2 (structure figée, fichiers
  typés) ; celui d'une MER reprend l'éditeur existant.
- Référentiels externes de MER : nom calculé à la création (« 6e — 2026-2027
  — MER », « … MER b ») + description ; les noms existants sont conservés.

## Code

- `services/referentiel_principal_externe.nom_calcule` : tout référentiel figé.
- `services/referentiels.py` : `lister_par_niveau` expose `type_ref`,
  `source`, `nom` ; `creer_coquille(..., type_ref)`.
- `routes/referentiels.py` : coquille avec `type_ref` ; filtre `type=` ;
  externes filtrés par type.
- `services/referentiel_externe.py` : `nom_calcule_mer`, `creer(...,
  description)` ; migration : colonne `referentiel_externe.description`.
- `static/referentiel_pe.js` (contrôleur `rxa*` : liste / détail, création),
  `static/referentiel_externe.js`, `static/atelier_referentiel.js` (type à la
  création, nom dans la liste et le titre), `static/atelier_progression.js`
  (`type=principal`), `templates/index.html`, `static/app.css`.

## Tests

- pytest `tests/test_v0_48_4_harmonisation_referentiels.py` (4) ; test
  v0.48.2 ajusté (la source est toujours renseignée).
- Suite complète : pytest 4154 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : écran externe (principaux + MER dans une même liste,
  création d'une MER « Calcul mental »), sélecteur de type de l'écran interne.
