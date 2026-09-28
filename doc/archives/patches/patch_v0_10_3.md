# patch v0.10.3 — Refonte sidebar + édition rapide + corrections

**Date** : 1 mai 2026

**Périmètre** : refonte majeure de la sidebar de l'atelier d'assemblage,
zone notion dans les objectifs, édition rapide depuis la sidebar/chips,
règle (b) sur les précédences, robustification de l'auto-import des
cycles avec diagnostic et relance manuelle depuis l'UI.

**Score tests** : 1561/1561 passent (4 skipped historiques inchangés).
6 nouveaux tests pour la règle (b).

---

## 1 — Règle (b) sur les précédences

Le backend valide désormais que `precedent_niveau` est ≤ niveau courant
de la séquence. Comparaison lexicographique sur les codes `NXX`
(N07 < N08 < … < N12), qui correspond à l'ordre numérique.

Cas autorisés :
- Niveau strictement inférieur (N12/S03 → N11/S05 ✓)
- Même niveau, autre séquence (N12/S03 → N12/S05 ✓)
- Cycles virtuels préfixés non-N (N10/S03 → C03/S04 ✓ — toujours autorisé)

Cas refusés (`HTTP 400 precedence_invalide`) :
- Circulaire (déjà refusé en v0.10.2 : N12/S03 → N12/S03)
- Niveau supérieur (N11/S03 → N12/S05 ✗)

### UI

Le sélecteur de niveau du popover Précédences ne propose plus C03
(option α : « C03 n'est pas un niveau, c'est un cycle de trois niveaux »).
Pour référencer du contenu C03 dans une précédence, peupler N09 d'abord
(roadmap : CRUD du découpage de cycle). Les niveaux disponibles : N09,
N10, N11, N12. Le mapping niveau → cycle pour alimenter les séquences
est étendu : N07/N08/N09 → C03, N10/N11/N12 → C04.

---

## 2 — Auto-import des cycles plus robuste

### Logger fichier

`services/cycle_auto_import.py` écrit maintenant chaque évènement dans
`data/auto_import.log` en plus de stderr. Plus fiable quand Flask
debug+reloader avale stderr.

### Endpoints diagnostic et relance manuelle

| Méthode | URL | Rôle |
|---|---|---|
| GET | `/api/admin/cycles/auto-import-status` | État (CSV présent ? cycle en BDD ?) + extrait du log |
| POST | `/api/admin/cycles/auto-import-relancer` | Relance manuelle. Idempotent. |

### UI Admin > BDD

Nouveau bloc « Auto-import des cycles » avec deux boutons :
- **État** : affiche pour chaque cycle (C03, C04) si CSV présents et si
  cycle déjà en BDD, plus les ~50 dernières lignes du log.
- **Relancer l'auto-import** : déclenche l'auto-import à la demande.
  Idempotent — ne fait rien pour les cycles déjà en BDD.

Utile en dépannage si un démarrage initial a échoué silencieusement.

---

## 3 — Refonte de la sidebar

### Mode 1 — Aucun objectif ouvert

Trois sections repliables :

- **Méthodes** de la séquence courante. Bouton ✎ « Éditer » sur chaque
  ligne pour ouvrir l'atelier Méthode. Méthodes déjà placées : grisées,
  non draggables, tag `P{n}/{code obj}`.
- **Exos d'approche (EA)** de la séquence courante. Tag `P{n} EA` si
  déjà placé.
- **Exos de révision (R)**, une section par précédence déclarée. Si
  aucune précédence : section « Exos de révision (R) » vide avec message
  « Aucune précédence déclarée. ».

Les exos R/EA déjà placés en révision/approche d'une partie sont
toujours affichés mais non re-draggables (le tag à droite indique où
ils sont).

### Mode 2 — Objectif "exo" ouvert

Quatre sections repliables :

- **Notions** de la séquence (toutes, draggables vers la zone notion de
  l'objectif). Tag `[01] [12]` pour les codes d'obj où la notion est déjà
  placée. Double-clic = ouvrir l'atelier Notion.
- **Exos série F**, **A**, **E** (chaque série dans sa propre section).
  Mêmes badges que pour les notions. Double-clic = ouvrir l'atelier
  Exercice.

Plus de méthodes, plus de EA, plus de R en mode obj exo ouvert.

### Mode 3 — Objectif "Connaître" ouvert

Sidebar **vide**. Message explicatif :

> L'objectif Connaître ne reçoit que des notions (à déposer dans
> l'objectif lui-même via la zone Notions). Aucun élément à glisser
> depuis la sidebar.

L'objectif Connaître a une zone notion comme tous les autres ; on y
dépose des notions depuis le mode 2 (qui montre les notions à gauche).
Si on ouvre directement le Connaître depuis le mode 1, il faut le
fermer puis ouvrir un autre obj exo pour avoir les notions à dispo
(ou fermer-et-rouvrir si on a déjà des notions ailleurs). C'est un
compromis temporaire — pourra être amélioré en mode 4 (« sidebar
notions toujours visible » sur Connaître ouvert) si demandé.

---

## 4 — Zone notion dans les objectifs

### Tous les objectifs

Une nouvelle zone « Notions » apparaît en première position dans le
corps de l'objectif ouvert (avant les zones F/A/E pour les obj exo).

- Drop d'une notion (mode sidebar 2) → POST `/api/v2/objectifs/<id>/notions`
- Chaque notion placée est un chip avec ✕ pour retirer
- Double-clic sur le chip = ouvrir l'atelier Notion

### Objectif Connaître

Pas de zones F/A/E (Q5 du cahier des charges). Seulement :
- Méthode liée (toujours rare pour Connaître mais possible)
- Critères F/A/E (textareas de niveau de maîtrise)
- Zone Notion

---

## 5 — Édition rapide

Nouvelle fonction `seqnivAsmEditerAtome(type, id)` qui :

1. Bascule sur l'onglet Ateliers
2. Active le sous-onglet correspondant (notion / methode / exercice)
3. Charge l'atome dans le formulaire d'édition

Réutilise `compilBatchOuvrirAtelier(type, id)` déjà présent dans
app.js (initialement écrit pour le rapport de compilation par lot).
Pas de fil d'Ariane (roadmap) — pour revenir à l'atelier d'assemblage,
cliquer sur l'onglet Séquence (l'objectif ouvert sera restauré
puisque persisté en BDD via v0.10).

### Déclencheurs de l'édition rapide

- **Double-clic** sur une notion ou un exo dans la sidebar
- **Double-clic** sur un chip notion ou exo placé dans un objectif ouvert
- **Bouton ✎** sur chaque ligne méthode dans la sidebar (les méthodes
  ne sont jamais des chips — pas d'événement double-clic, donc bouton
  explicite)
- **Bouton « Éditer »** à côté de la méthode liée affichée dans
  l'objectif ouvert (en plus du bouton « Délier » existant)

---

## 6 — Suppression des zones EA/R des objectifs

Les zones EA et R disparaissent de la carte d'objectif ouvert. Les exos
EA/R sont attachés UNIQUEMENT à la partie via la table
`partie_exos_revision_approche` (déjà le cas depuis v0.10). Cohérent
avec ton modèle : un objectif ne reçoit pas d'EA/R, ces exos sont
contextuels à la partie (révision en début de partie, approche en début
de partie).

---

## 7 — Badges d'affectation

Chaque ligne de la sidebar affiche à droite le ou les emplacements où
l'élément est déjà utilisé :

- **Notions / exos F/A/E** : codes des objectifs (par ex. `01 12`)
- **Exos EA/R** : `P{n} EA` ou `P{n} R`
- **Méthodes** : `P{n}/{code obj}`

Affichage statique, pas d'interaction (Q4 du cahier des charges).

---

## Fichiers modifiés

```
services/v2_edition.py        — règle (b) sur ajouter_precedence_sequence
services/cycle_auto_import.py — log fichier, traceback, exception filet
routes/cycle.py               — endpoints diagnostic + relance
templates/index.html          — bloc Admin > BDD auto-import cycles
static/atelier_seqniv_assemblage.js
                              — refonte sidebar (700+ lignes touchées)
                              — refactor _renduItem / _renduSection
                              — drag/drop notion, édition rapide
static/app.js                 — adminCyclesAutoImportStatus / Relancer
                              — pas d'autres modifs
static/app.css                — badges N/R/M, bouton Éditer
tests/test_v0_10_2_precedences.py  — 6 nouveaux tests règle (b)
```

---

## Test manuel après déploiement

1. **Précédences règle (b)**
   - Ouvrir N12/S03. Précédences. Tenter d'ajouter N12/S05 → doit
     accepter. Tenter d'ajouter N12/S03 → circulaire, refusé.
     Tenter d'ajouter N09/S03 → accepté (niveau inférieur).
   - Ouvrir N10/S03. Tenter d'ajouter N11/S03 → refusé.

2. **Auto-import C03 robuste**
   - Aller dans Admin > Base de données > « Auto-import des cycles »
   - Cliquer **État** : doit montrer C03 et C04 avec leur statut
     (CSV présents, en BDD ou non) + extrait du log
   - Si C03 manque : cliquer **Relancer l'auto-import** → C03 importé.

3. **Sidebar mode 1 (aucun obj ouvert) sur N11/S03**
   - Vérifier 3 sections : Méthodes, Exos EA, Exos R par précédence
     (autant de sections R que de précédences)
   - Pour chaque méthode, bouton ✎ visible
   - Pour chaque exo R/EA déjà placé, badge à droite (`P1 EA`, `P2 R`)
   - Cliquer ✎ sur une méthode → l'atelier Méthode s'ouvre, la méthode
     est sélectionnée

4. **Sidebar mode 2 (obj exo ouvert)**
   - Ouvrir un obj qui n'est pas le Connaître (par ex. obj 02)
   - Sidebar : 4 sections (Notions, F, A, E)
   - Drag d'une notion vers la zone Notion de l'obj → notion ajoutée
   - Drag d'un exo F vers la zone F → exo ajouté
   - Double-clic sur une notion (sidebar ou chip) → atelier Notion s'ouvre

5. **Sidebar mode 3 (obj Connaître ouvert)**
   - Ouvrir l'obj 01 (Connaître) d'une partie
   - Sidebar : message « L'objectif Connaître ne reçoit que des notions… »
   - L'objectif lui-même contient : critères F/A/E + zone Notion
     (pas de zones F/A/E dans le corps !)

6. **Édition rapide depuis chips placés**
   - Dans un obj exo ouvert, double-clic sur un chip d'exo placé →
     atelier Exercice s'ouvre, exo sélectionné
   - Idem double-clic sur un chip notion

7. **Retour à l'assemblage**
   - Cliquer sur l'onglet Séquence : on retrouve l'atelier dans son
     état précédent, l'objectif éventuellement ouvert est restauré

---

## Pas inclus dans v0.10.3 (différé)

- **Fil d'Ariane généralisé** avec navigation précédent/suivant : roadmap
- **CRUD du découpage de cycle** (création/modif/suppression de séquences) :
  roadmap (item séparé)
- **Génération du livret PDF** : prévue v0.10.4
- **Récap livrets en portée niveau** : roadmap
- **Sidebar en mode obj Connaître ouvert** : actuellement vide. On
  pourrait montrer les notions de la séquence (cohérent avec la zone
  Notion). À envisager si tu trouves le mode actuel gênant.

---

## Pièges connus

- **L'auto-import au démarrage initial v0.10.2 a échoué silencieusement
  chez Laurent.** v0.10.3 met en place le diagnostic et la relance
  manuelle ; en cas d'échec ré-occurrent, le log fichier
  `data/auto_import.log` montrera la stacktrace exacte.

- **Le payload des drags depuis la sidebar est sérialisé en JSON dans
  `data-drag-payload`.** Si tu regardes le DOM en debug, tu verras des
  éléments `data-drag-payload="{&quot;kind&quot;:&quot;notion&quot;,…}"`
  — c'est normal, c'est l'encodage HTML pour échapper les guillemets.

- **Drag d'un exo R sans précédence déclarée** : le drag est autorisé
  par l'UI (la sidebar n'affiche pas de section R sans précédence,
  donc la situation ne se produit pas) ; mais si on appelait l'API à
  la main, le backend rejette en 409 `exo_revision_hors_precedences`.
