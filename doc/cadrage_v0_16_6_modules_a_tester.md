# Annexe — Modules à tester sous Vitest (cible), par priorité/risque

> Établie à partir de l'audit du code réel de `atelier_seqniv_assemblage.js`
> (2498 lignes). Une fois le seqniv migré en `AtelierSeqnivAssemblage`, ces
> unités deviennent des méthodes testables. Priorité = valeur × risque ÷ coût.
>
> Légende priorité : **P1** (à faire en premier, fort risque ou socle), **P2**
> (important), **P3** (utile, après coup), **P4** (optionnel / couvert par la
> validation visuelle).

## Groupe A — Logique PURE (P1) : calculs, placements, recherche

Fonctions sans DOM ni fetch ni dépendance d'état global mutable (ou état
injectable en argument). **Meilleur ratio valeur/coût** : déterministes,
rapides, protègent la logique métier la plus subtile (placement des exos/notions
dans la structure, totaux de séances). À tester en priorité.

| Unité | Rôle | Risque | Prio |
|---|---|---|---|
| `_placementsExos` | Calcule où un exo est placé (séries F/A/E par objectif) | Élevé (logique de placement, source de bugs d'affichage) | **P1** |
| `_placementsExosRA` | Placements des exos en Révision/Approche par partie | Élevé | **P1** |
| `_placementsNotions` | Placements des notions | Moyen | **P1** |
| `_placementsMethodes` | Placements des méthodes | Moyen | **P1** |
| `_calculerTotalSeancesPartie` | Somme séances (R+AE + objectifs) d'une partie | Élevé (affiché à l'utilisateur, calcul cumulatif) | **P1** |
| `_indexObjDansPartie` | Index d'un objectif dans sa partie | Moyen (ordre, réordonnancement) | **P1** |
| `_fmtSeances` / `_fmtSeancesAffichage` | Formatage nombre de séances (demi-séances ?) | Moyen (formatage, cas limites 0/0.5/n) | **P1** |
| `_trouverObj` / `_trouverPartie` / `_trouverPartiePourObj` / `_trouverPartieDeObj` | Recherche dans l'arbre DATA | Moyen (helpers très utilisés ; un bug se propage partout) | **P1** |
| `_couleurTheme` | Mappe un code thème → couleur | Faible | **P3** |
| `esc` / `escAttr` | Échappement HTML | Faible (mais critique sécurité/rendu) | **P2** |

## Groupe B — Logique d'ACCEPTATION du DnD (P1) : le cœur du risque

Chaque `Drop*` lit `DRAG.kind` et décide d'accepter/refuser puis persiste. La
**décision d'acceptation** (quelle source est acceptée par quelle cible) est
testable en injectant un `this._drag = {kind, …}` simulé et en mockant
`apiJson`. C'est LA zone à risque (multi-source × multi-cible) et celle que la
validation visuelle couvre le moins bien (combinatoire).

| Unité | Cible / acceptation | Risque | Prio |
|---|---|---|---|
| `seqnivAsmDropObj` | Zone objectif (méthode→nouvel obj…) | Élevé (66 lignes, plusieurs `kind`) | **P1** |
| `seqnivAsmDropRA` | Zone Révision/Approche (exo) | Élevé | **P1** |
| `seqnivAsmDropMethode` | Méthode sur objectif | Élevé | **P1** |
| `seqnivAsmDropExoObj` | Exo dans série F/A/E d'un objectif | Élevé | **P1** |
| `seqnivAsmDropNotion` | Notion sur objectif | Moyen | **P2** |
| `seqnivAsmDropFiche` | Fiche sur objectif | Moyen | **P2** |
| `_dropPartie` / `_dragOverPartie` / `_dragLeavePartie` | Réordonnancement de parties (calcul d'index d'insertion) | Élevé (calcul d'index = bug classique) | **P1** |

**Approche de test** : tester la fonction de décision, pas l'événement DOM réel.
On vérifie : (a) un `kind` non accepté est ignoré (pas d'appel apiJson) ; (b) un
`kind` accepté déclenche le bon appel (URL + body) ; (c) calcul d'index
d'insertion pour le réordonnancement.

## Groupe C — Transitions d'ÉTAT / sidebar (P2)

Le seqniv a 3 modes de sidebar selon `OBJ_OUVERT`. La sélection du bon mode est
de la logique testable (le rendu lui-même est P4).

| Unité | Rôle | Risque | Prio |
|---|---|---|---|
| `_setObjOuvert` / `OuvrirObj` / `FermerObj` | Transition d'objectif ouvert → mode sidebar | Élevé (3 modes, source de bugs d'état) | **P1** |
| `_rendreSidebar` (sélection du mode, pas le HTML) | Choisit quelle sidebar rendre selon l'état | Moyen | **P2** |
| `ActiverConnaitre` | Bascule objectif « Connaître » | Moyen | **P2** |
| `BasculerOnglet` | Édition ↔ Rendu PDF | Faible (déjà éprouvé) | **P3** |

## Groupe D — Handlers de CHAMPS (P2) : critères, séances, nom

Persistance immédiate aujourd'hui (deviendront snapshot plus tard). Tester que
le bon body est envoyé (URL + payload), en mockant apiJson.

| Unité | Rôle | Risque | Prio |
|---|---|---|---|
| `ChangerCritere` | PATCH critère_F/A/E d'un objectif | Moyen (envoie les 3 critères ensemble) | **P2** |
| `ChangerSeancesObj` | PATCH nb_seances objectif | Moyen (parsing nombre, demi-séances) | **P2** |
| `ChangerSeancesPartie` | PATCH nb_seances_R_AE partie | Moyen | **P2** |
| `ChangerNom` | PATCH nom objectif | Faible | **P3** |
| `ChangerFinCycle` | Toggle fin de cycle | Faible | **P3** |

## Groupe E — Handlers de STRUCTURE (P2) : parties, objectifs, retraits

Vérifier l'appel API correct + (plus tard) la garde anti-perte.

| Unité | Rôle | Risque | Prio |
|---|---|---|---|
| `NouvellePartie` / `SupprimerPartie` | Création/suppression de partie | Moyen | **P2** |
| `SupprimerObj` | Suppression d'objectif | Moyen | **P2** |
| `RetirerExoObj` / `RetirerExoRA` / `RetirerMethode` / `RetirerNotion` / `RetirerFiche` | Retraits de composants | Moyen (combinatoire) | **P2** |
| `ValiderPrecedence` / `RetirerPrecedence` / `TogglePrecPopover` | Sous-système précédences | Moyen (spécifique, fragile) | **P2** |

## Groupe F — RENDU HTML (P4) : large surface, couvert par le visuel

Les `_rendre*` produisent du HTML. Testables (jsdom + assertions sur la chaîne),
mais coût élevé et fragile (le HTML change souvent). La **validation visuelle de
Laurent** les couvre mieux. À ne tester que ponctuellement (présence d'un
attribut critique, ex. `data-exo-id`, `varGlobale.X` dans les onclick générés).

| Unité | Prio |
|---|---|
| `_rendreObjOuvert` (210 l.), `_rendrePartie`, `_rendreObjFerme`, `_rendreZone*`, `_rendreChip*`, `_renduItem`, `_renduSection`, `_rendreBlocPrecedences`, `_rendreCentre`, `_rendreSidebarObj*` | **P4** (sauf 1-2 assertions ciblées P3 : présence des hooks `varGlobale.*` et `data-*`) |

## Groupe G — I/O & infrastructure (P3) : à mocker, pas à tester en profondeur

| Unité | Rôle | Prio |
|---|---|---|
| `apiJson` | Wrapper fetch | **P3** (tester la gestion d'erreur ; mocker fetch) |
| `_rafraichir` | Charge DATA puis rend | **P3** (orchestration ; mocker apiJson) |
| `_sn` | Résout la séquence courante (niveau+seq) | **P2** (jointure cycle — bug historique connu) |
| `_chargerCriteresDefaut` | Charge les critères par défaut une fois | **P3** |
| `_livretSeq*` (rendu PDF livret) | Affichage PDF/loader/erreur | **P4** (visuel) |
| `_status` / `_afficher` / `_container` / `_sidebar*` | Helpers DOM | **P4** |

## Plan de test recommandé (ordre d'écriture)

1. **P1 Groupe A** (logique pure) : le socle, rapide, haute valeur. ~10 unités.
2. **P1 Groupe B** (décision DnD) : le cœur du risque. ~7 unités, avec apiJson
   mocké.
3. **P1 Groupe C** (transitions sidebar/objectif ouvert).
4. **P2** Groupes D/E (handlers champs + structure) + `_sn` (Groupe G).
5. **P3/P4** au fil de l'eau, assertions ciblées seulement (hooks `varGlobale.*`
   présents dans le HTML généré — utile pour verrouiller la réécriture HTML).

> Cible réaliste v0.16.6 : Groupes A + B + C (les P1) couverts, soit le socle
> pur + la décision DnD + les transitions d'état. Le reste (P2+) au fil des
> versions suivantes, notamment quand on branchera le modèle mixte/verrou.
