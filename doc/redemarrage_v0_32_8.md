# Redémarrage v0.32.8 — Saisie de l'association au bon endroit + panneau redimensionnable

Corrige l'absence de l'UI de saisie « Documents à distribuer » (v0.32.6 avait
livré le JS mais pas le HTML du formulaire) et rend le panneau de détail
redimensionnable.

## Bug corrigé — le formulaire de saisie n'existait pas dans le HTML

La v0.32.6 avait livré `static/progression_doc.js` et l'appel à
`progDocsCharger`, mais le **formulaire HTML** (select, rang, bouton) n'avait
jamais été inséré (str_replace raté à l'époque, non détecté). Le JS cherchait
`prog-docs-liste`, `prog-docs-select`, etc. — introuvables. D'où l'impossibilité
de planifier la distribution.

## Emplacement (clarifié avec l'utilisateur)

La saisie est dans **Suivi de classe → Progression principale**, dans le détail
du créneau sélectionné, sous « Objectifs de ce créneau » (id `prog-docs-saisie`)
— PAS dans Conception de référentiel. Le contexte (progression, créneau,
séquence) vient de `ATELIER_PROGRESSION`.

Le formulaire : liste des docs associés (avec rang + retrait), sélecteur groupé
(cette séquence / séquence suivante / annuels), champ « séance n° », bouton
« associer », case « séquence suivante ». Les planches de cartes d'automatisme
sont dans la liste.

L'affichage reste : dans la Planification hebdo, le détail d'une séance montre
les docs prévus (déduits de l'association au niveau + rang).

## Panneau redimensionnable

`.prog-detail` (colonne de droite du calendrier) devient redimensionnable en
largeur (`resize: horizontal`, min 240px, max 70vw). La poignée est au coin
bas-droit du panneau.

## Fichiers

- `templates/index.html` : formulaire `prog-docs-saisie` dans le détail du
  créneau.
- `static/progression_doc.js` : cible `prog-docs-saisie` (au lieu de l'ancien id
  en collision).
- `static/app.css` : `.prog-detail` redimensionnable.

## Tests

- vitest : 193 passed. pytest (progression_doc, état verrouillé) : 7 passed.
  Documents disponibles vérifiés (N11 S01 : livret + planches + 6 annuels).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Suivi →
Progression principale → sélectionner un créneau → « Documents à distribuer ».

## État du projet (voir aussi doc/ETAT_COURANT.md)

Chantier planification : socle (v0.32.5), affichage (v0.32.6), correctif état
verrouillé (v0.32.7), UI de saisie au bon endroit (v0.32.8) — fonctionnel.
Dettes préexistantes : test_v0_29_0_verso_miroir (obsolète),
test_annees_scolaires (date-dépendant).
