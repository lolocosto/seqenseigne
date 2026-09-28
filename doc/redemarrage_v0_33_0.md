# Redémarrage v0.33.0 — Onglet principal « Planification »

Réorganise la navigation de premier niveau : un nouvel onglet « Planification »
regroupe tout ce qui relève du prévu ; « Suivi de classe » devient « Suivi » et
ne garde que le suivi des séquences + la gestion.

## Navigation

Navbar : Tableau de bord · **Suivi** · **Planification** · Conception de
référentiel · Administration · Préférences.

- **Planification** (nouvel onglet, entre Suivi et Conception) : EdT hebdo,
  Planification hebdo, Indisponibilités, Mises en route, Progression de MER,
  Progression principale (même ordre qu'avant).
- **Suivi** (ex-« Suivi de classe ») : le sous-onglet « Suivi de classe » (accès
  direct, l'étage intermédiaire disparaît) + la Gestion (Classe, Établissement).

Les deux onglets partagent le conteneur `tab-classe` ; chacun force sa portée
(planification vs suivi/gestion). La barre de portées n'apparaît que dans
« Suivi ».

## Implémentation

- `SUIVI_PORTEES` : 3 groupes (`planification`, `suivi`, `gestion`) au lieu de 2
  (`annuel`, `gestion`). Défaut : `planification`.
- Classes des sous-onglets : `suivi-grp-planification` (6), `suivi-grp-suivi`
  (1), `suivi-grp-gestion` (2).
- Gestionnaire d'onglets : « planification » et « classe » pointent vers
  `tab-classe` et forcent la portée ; la barre de portées (row) est masquée en
  planification.

## Fichiers

- `static/app.js` : `SUIVI_PORTEES`, `suiviPorteeSwitch`, gestionnaire d'onglets.
- `templates/index.html` : navbar (Planification + renommage), barres de portées
  et de sous-onglets.
- `tests_js/suivi_navigation.test.js` : DOM factice et tests adaptés au nouveau
  modèle.

## Tests

- vitest : 193 passed. Page vérifiée : onglet Planification présent, Suivi
  renommé, 6 sous-onglets planification, portées suivi/gestion.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.32.12. Note : la portée mémorisée en localStorage
(`suivi-portee-active`) est revalidée ; si elle valait « annuel », elle
retombe sur « planification ».

## Suite (onglet « Suivi » à enrichir — à cadrer)

- Outil de conception de plan de classe.
- Définition des infos capturées en séance (associées au plan de classe).
- Suivi par élève (absences, docs (non) distribués, évals (non) faites, travaux
  (non) rendus…). Cf. reflexion_metier_enseignant_roadmap.md (§8, retours EPS).
