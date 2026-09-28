# Redémarrage v0.24.1 — MER en sous-onglet + corrections du planning

Ajustements sur la v0.24.0 suite aux retours.

## 1. « Mises en route » déplacé dans Suivi annuel

L'onglet n'est plus un onglet principal : il devient un **sous-onglet de Suivi
de classe › Suivi annuel**, positionné **entre « Indisponibilités » et
« Progression principale »**. Il utilise les **sélecteurs globaux** du Suivi
annuel : **année**, **établissement** et **classe**.

- La zone A (configuration MER par classe) liste les classes de
  l'établissement/année globaux.
- La zone B (planning des automatismes) affiche le PDF de la **classe
  sélectionnée** dans la barre globale (si elle fait des automatismes). Le
  planning se rafraîchit quand on change de classe.

Le bloc « Mises en route » du détail de classe (Gestion) reste disponible ; les
deux partagent les mêmes champs `mer_active` / `mer_mode`.

## 2. Planning : corrections de mise en page

- **Débordement corrigé** : les dates reviennent à la ligne proprement. Chaque
  date est une `\parbox` de largeur fixe, séparée par un `\penalty0` (autorise
  la coupure) et `\sloppy` (évite les débordements en marge). Vérifié :
  0 « overfull hbox » sur un planning de 30 séances.
- **Dates plus visibles** : chaque date est encadrée (`\fbox`).
- **Interligne ×1,5** (`\linespread{1.5}`) pour l'aération.
- (Rappel v0.24.0 : dates horizontales, enveloppes ①②③④ pifont, bandes de
  vacances, ∅ pour indisponibilité.)

## Fichiers

- `templates/index.html` : suppression de l'onglet principal MER et de son
  panneau ; ajout du sous-onglet `suivi-btn-mer` et du panneau `stab-mer`.
- `static/app.js` : `mer` dans `SUIVI_ATELIER_PANNEAU`
  (sélecteurs `etablissement` + `classe`), dans la liste des panneaux, init dans
  `suiviSwitch` ; `onClasseChange` rafraîchit le planning MER si l'onglet est
  actif.
- `static/mer.js` : réécrit pour le contexte Suivi (sélecteurs globaux ; planning
  de la classe sélectionnée).
- `services/planning_automatismes_tex.py` : `\fbox` sur les dates, `\parbox`
  largeur fixe + `\penalty0` + `\sloppy` (anti-débordement), `\linespread{1.5}`.

## Tests

- vitest : 193 passed (0 régression). Syntaxe OK. Sous-onglet vérifié (plus
  d'onglet principal).
- Compilation réelle vérifiée : 30 séances, 0 overfull hbox, dates encadrées
  complètes, enveloppes pifont, bande de vacances, A3 paysage.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Suivi de
classe › Suivi annuel › Mises en route.

## Suite

- Référentiels externes (docs PDF/ODT de collègues), puis panachage.
