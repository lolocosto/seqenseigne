# Spécification — Décalage de progression par « semaines neutralisées »

Version cible : v0.27.2
Objet : refondre le décalage de progression (principale et MER) pour qu'un
décalage se comporte comme une **période de vacances insérée** : il neutralise
une ou plusieurs semaines de cours, que les créneaux enjambent (comme ils
enjambent les vacances de Noël), au lieu de déplacer les blocs en bloc.

Ce document décrit le comportement attendu et l'algorithme, avec des exemples
chiffrés couvrant les cas limites. Il sera validé avant toute écriture de code.

---

## 1. Rappel du problème

Le décalage actuel déplace un créneau **en bloc** : il ajoute N×7 jours à
`date_debut` et `date_fin`. Conséquences fausses constatées :

- un créneau qui **enjambe** la date de décalage glisse entièrement au lieu de
  « garder » ses semaines antérieures et de ne repousser que les suivantes ;
- des décalages cumulés appliqués en une seule passe sur les dates d'origine se
  télescopent (le 2ᵉ décalage compare la date d'origine, pas la date déjà
  décalée).

Exemple réel (classe 4E4) : S03·P1 couvre `2026-09-07 → 2026-09-18` (semaines du
07 et du 14). Décalages : +1 sem au 11/09, puis +1 sem au 22/09.
- Attendu : S03 sur les semaines du **14 et du 28** (la semaine du 21 est
  neutralisée par le décalage du 22).
- Obtenu : S03 sur les semaines du 21 et du 28 (bloc déplacé), la semaine du 28
  vide.

---

## 2. Principe retenu (validé)

Un décalage **neutralise des semaines de cours**, exactement comme une période
de vacances :

- une **semaine neutralisée** est transparente pour les créneaux : un créneau
  qui l'enjambe s'affiche de part et d'autre, en la sautant ;
- une semaine neutralisée porte un **marqueur** « décalage : <motif> » (Qa=b) ;
- c'est **la semaine (de cours) contenant l'indisponibilité** qui est
  neutralisée, plus, si N>1, les N−1 semaines de cours suivantes (Qb) ;
- la neutralisation ne « consomme » que des **semaines de cours** : elle ne
  tombe jamais sur une semaine déjà entièrement en vacances (celles-ci sont
  ignorées / sautées lors du décompte).

### 2.1 Unité de raisonnement : la semaine de cours

Le calendrier scolaire est une suite de semaines (lundis). On distingue :

- **semaine de vacances** : les 5 jours lundi→vendredi sont tous en vacances
  (définition existante `_semaineEntierementEnVacances`) ;
- **semaine de cours** : au moins un jour lundi→vendredi n'est pas en vacances
  (un férié seul ne rend pas la semaine « de vacances ») ;
- **semaine neutralisée** : une semaine de cours rendue transparente par un
  décalage.

Une semaine peut être neutralisée seulement si elle est une semaine de cours.

---

## 3. Données

Un décalage (inchangé en base) :
`decalage_progression(classe_id, annee, a_partir_de, nb_semaines, motif,
indispo_id)`.

Interprétation nouvelle de `a_partir_de` + `nb_semaines` :
- soit `S0` la **semaine de cours contenant** la date `a_partir_de` (le lundi de
  cette semaine) ;
- le décalage neutralise `nb_semaines` **semaines de cours** consécutives à
  partir de `S0` incluse (en sautant les semaines de vacances rencontrées).

Exemple : `a_partir_de = 2026-09-22`, `nb_semaines = 1` → neutralise la semaine
de cours du lundi 21/09 (celle qui contient le 22).

---

## 4. Ensemble des semaines neutralisées d'une classe

Fonction pure `semaines_neutralisees(decalages, calendrier) -> set(lundiISO)` :

1. Pour chaque décalage, trouver `S0` = lundi de la semaine contenant
   `a_partir_de`.
2. À partir de `S0`, avancer semaine par semaine, en **ignorant** les semaines
   de vacances, et marquer comme neutralisées les `nb_semaines` premières
   semaines de cours rencontrées (S0 incluse si c'est une semaine de cours ;
   si `a_partir_de` tombe un jour de vacances — cas exclu par Qb mais géré
   défensivement — on démarre à la première semaine de cours suivante).
3. L'union de toutes ces semaines (tous décalages confondus) forme l'ensemble
   des semaines neutralisées. Deux décalages peuvent neutraliser des semaines
   distinctes ; s'ils se recouvrent, l'union dédoublonne naturellement.

Remarque cumul : comme on raisonne en **ensemble de semaines** (et non en
addition de jours), l'ordre d'application ne pose plus le problème de
télescopage du modèle actuel.

---

## 5. Recalcul des dates des créneaux

Le but : produire, pour l'affichage « réalisé » d'une classe, des créneaux dont
les `date_debut`/`date_fin` tiennent compte des semaines neutralisées, de sorte
que le mécanisme d'enjambement existant (sauter les semaines transparentes)
produise le bon rendu.

Fonction pure `appliquer_neutralisations(creneaux, semaines_neutralisees,
calendrier) -> creneaux'` :

Pour chaque créneau, on raisonne en **semaines de cours effectives** :

- `date_debut` d'un créneau se décale du nombre de semaines neutralisées qui
  sont **strictement avant** sa semaine de début (dans l'ordre du calendrier,
  en comptant en semaines réelles) ;
- `date_fin` se décale du nombre de semaines neutralisées **avant ou pendant**
  la plage du créneau — c'est ce qui « étire » un créneau qui enjambe une
  semaine neutralisée (sa fin est repoussée pour compenser la semaine sautée).

Formulation opératoire (par créneau, ordre chronologique du calendrier) :

1. Repérer la semaine de début `Sd` (lundi de `date_debut`) et de fin `Sf`
   (lundi de `date_fin`).
2. `avant` = nombre de semaines neutralisées dont le lundi est `< Sd`.
3. `pendant` = nombre de semaines neutralisées dont le lundi est dans
   `[Sd, Sf]`.
4. Nouvelle semaine de début = `Sd` avancée de `avant` semaines de cours (en
   sautant vacances et semaines neutralisées).
5. Nouvelle semaine de fin = `Sf` avancée de `avant + pendant` semaines de
   cours (même règle de saut).
6. Reporter le décalage jour à jour : `date_debut' = date_debut + (nouvelle
   semaine de début − Sd)` ; idem pour `date_fin'`.

Le pas 5 (ajouter `pendant`) est la clé de l'« étirement » : un créneau qui
contient une semaine neutralisée voit sa fin repoussée pour la sauter, tout en
gardant ses semaines de cours antérieures.

---

## 6. Affichage

Inchangé dans son principe (`_creneauxDeLaSemaine` + transparence des semaines) :

- une semaine neutralisée est traitée comme une semaine de vacances : elle
  n'affiche pas les créneaux (transparence) ;
- elle affiche à la place un **marqueur** « ⤵ décalage : <motif> » (couleur
  distincte des vacances, ex. le violet des indisponibilités) ;
- les créneaux, recalculés par §5, s'affichent naturellement de part et d'autre.

---

## 7. Exemples chiffrés (cas de validation)

Calendrier simplifié : semaines de cours lundis 07/09, 14/09, 21/09, 28/09,
05/10, 12/10, puis vacances Toussaint (19/10, 26/10), reprise 02/11…

### Exemple A — le cas réel S03 (enjambement + cumul)
Créneau S03·P1 : `date_debut 2026-09-07`, `date_fin 2026-09-18` (semaines 07 et
14). Décalages : +1 au 11/09 (neutralise sem 07), +1 au 22/09 (neutralise
sem 21).

- Semaines neutralisées : {07/09, 21/09}.
- S03·P1 : Sd=07, Sf=14.
  - `avant` (< 07) = 0.
  - `pendant` (dans [07,14]) = 1 (la semaine 07 est neutralisée).
  - nouvelle Sd = 07 avancée de 0 sem de cours = **07**… mais 07 est
    neutralisée ! Voir §8 (règle du créneau dont la semaine de début est
    elle-même neutralisée).

**→ Ce cas révèle un point à trancher (voir §8).** Selon la règle choisie,
le résultat attendu est S03 sur **14 et 28**.

### Exemple B — créneau entièrement après le décalage
Créneau S05 : semaine 12/10 seulement. Décalage +1 au 22/09 (neutralise 21/09).
- `avant` (< 12/10) = 1 ; `pendant` = 0.
- nouvelle Sd = 12/10 avancé de 1 semaine de cours. La semaine suivante de cours
  après 12/10 est… 02/11 (car 19/10 et 26/10 sont des vacances, sautées).
- Résultat : S05 passe à la semaine du **02/11**. (Le décalage « pousse » S05
  d'une semaine de cours, en sautant les vacances.)

### Exemple C — créneau entièrement avant le décalage
Créneau S01 : semaine 07/09. Décalage +1 au 22/09.
- `avant` (< 07) = 0 ; `pendant` (dans [07,07]) = 0 (la semaine neutralisée 21
  n'est pas dans [07,07]).
- Résultat : S01 **inchangé**. ✔

### Exemple D — cumul sur un même créneau long
Créneau qui couvre 5 semaines de cours, 2 décalages neutralisant 2 semaines
distinctes dans sa plage : `pendant`=2 → sa fin est repoussée de 2 semaines de
cours ; il s'étale en sautant les 2 semaines neutralisées.

---

## 8. Point à trancher — créneau dont la semaine de DÉBUT est neutralisée

Dans l'exemple A, la semaine de début de S03 (07/09) est elle-même neutralisée
par le décalage du 11/09. Deux interprétations :

- **(i)** La semaine de début neutralisée « pousse » aussi le début : S03
  commencerait alors semaine 14, et sa fin (14, +1 pour la sem 21 neutralisée)
  irait à 28 → **S03 sur 14 et 28**. ✅ (correspond à l'attendu)
- **(ii)** Seules les semaines neutralisées strictement après le début étirent
  le créneau ; une neutralisation sur la semaine de début décale le début →
  revient au même ici.

Les deux donnent 14 et 28 sur cet exemple. La règle générale retenue :
**une semaine neutralisée décale le début si elle est ≤ à la semaine de début,
et étire la fin si elle est dans la plage [début, fin]** — ce qui se résume à :

- `decalage_debut` = nb de semaines neutralisées de lundi ≤ Sd ;
- `decalage_fin`   = nb de semaines neutralisées de lundi ≤ Sf ;
- nouvelle Sd = Sd avancé de `decalage_debut` semaines de cours ;
- nouvelle Sf = Sf avancé de `decalage_fin` semaines de cours.

Vérification exemple A (S03, Sd=07, Sf=14 ; neutralisées {07, 21}) :
- `decalage_debut` = |{07}| = 1 → nouvelle Sd = 07 avancé de 1 sem de cours = 14.
- `decalage_fin`   = |{07}|  = 1 (21 > 14, pas comptée) → nouvelle Sf = 14
  avancé de 1 = 21… **donne 14–21, pas 14–28.** ✗

Donc cette formulation simple ne suffit pas : la semaine 21 (neutralisée) tombe
APRÈS la fin d'origine (14) mais DANS la plage d'affichage étirée. Il faut donc
un calcul **itératif** : on étire la fin tant que des semaines neutralisées
tombent dans la plage courante (voir §9).

---

## 9. Algorithme itératif retenu (robuste)

Pour chaque créneau, en raisonnant sur la liste ordonnée des semaines de cours
(hors vacances) et l'ensemble `N` des semaines neutralisées :

```
Sd, Sf = semaine_debut, semaine_fin du créneau (lundis)
# 1) décaler le début : sauter les semaines neutralisées <= Sd
nouvelle_Sd = avancer(Sd, nb_neutralisees(lundi <= Sd))
# 2) longueur du créneau en semaines de cours effectives (hors neutralisées)
long = nb_semaines_de_cours_entre(Sd, Sf)  # bornes incluses, hors vacances
# 3) étaler depuis nouvelle_Sd sur `long` semaines de cours NON neutralisées,
#    en sautant vacances ET semaines neutralisées ; nouvelle_Sf = dernière.
nouvelle_Sf = nieme_semaine_de_cours_non_neutralisee(nouvelle_Sd, long)
```

`avancer(S, k)` = la k-ième semaine de cours après S (en sautant les vacances).
`nb_neutralisees(lundi <= Sd)` = nombre de semaines de `N` dont le lundi ≤ Sd.
`nb_semaines_de_cours_entre(Sd, Sf)` = compte les semaines de cours de la plage
d'origine (le créneau occupait `long` semaines de cours effectives).
`nieme_semaine_de_cours_non_neutralisee(depart, long)` = en partant de `depart`,
prendre `long` semaines qui sont de cours ET non neutralisées, retourner la
dernière (les semaines neutralisées et de vacances sont sautées, donc étirent).

Vérification exemple A (S03, occupe 2 semaines de cours : 07 et 14 ; N={07,21}) :
- nouvelle_Sd = avancer(07, 1) = 14 (on saute la neutralisée 07).
- long = 2 (le créneau occupait 2 semaines de cours).
- étaler depuis 14 sur 2 semaines non neutralisées : 14 (ok, 1) → 21 (neutralisée,
  sautée) → 28 (ok, 2). nouvelle_Sf = **28**.
- Résultat : S03 sur **14 → 28**, semaine 21 transparente. ✅

Vérification exemple B (S05, 1 sem de cours : 12/10 ; N={21/09}) :
- nouvelle_Sd = avancer(12/10, nb neutralisées ≤ 12/10 = 1) = 02/11 (saut
  vacances). long = 1. étaler depuis 02/11 sur 1 sem = 02/11.
- Résultat : S05 → **02/11**. ✅

Vérification exemple C (S01, 1 sem : 07 ; N={21}) :
- nouvelle_Sd = avancer(07, nb neutralisées ≤ 07 = 0) = 07. long=1. Sf=07.
- Résultat : **inchangé**. ✅

L'algorithme itératif (§9) est celui retenu.

---

## 10. Portée du changement

- Remplace `appliquer_decalages` (Python) et `appliquerDecalagesJS` (JS) par la
  logique « semaines neutralisées » ci-dessus. Les deux doivent rester
  strictement équivalentes (mêmes résultats).
- **S'applique UNIQUEMENT à la progression principale** (vue réalisée par
  classe), qui pose des créneaux datés sur des **semaines**.
- **NE s'applique PAS à la progression MER**, qui se compte **à la séance** :
  là, les indisponibilités retirent déjà des séances de la projection
  (`projeter_mer` sur les séances datées issues de la projection EdT × calendrier
  × indisponibilités), donc le décalage à la séance est déjà intrinsèque et
  correct. L'unité de décompte diffère (semaine vs séance), donc le mécanisme
  diffère aussi — et c'est voulu.
- Affichage : ajouter le marqueur « décalage : <motif> » sur les semaines
  neutralisées (comme le libellé de vacances), couleur indisponibilité.
- Tests : porter les cas A/B/C/D + cumul + proximité vacances.

## 11. Hors périmètre (inchangé)

- Le choix « absorber » (réduire le nb de séances au lieu de décaler) reste non
  implémenté ; ce document ne traite que « décaler » (désormais par
  neutralisation de semaines).
- La création/suppression des décalages (bouton sur l'indisponibilité,
  anti-empilement) est déjà en place (v0.27.1).

---

## 12. Questions ouvertes pour validation

- **Q1** : le libellé du marqueur sur une semaine neutralisée — « Décalage :
  <motif de l'indisponibilité> » convient-il ? (ex. « Décalage : Voyage à
  Nantes »).
- **Q2** : si deux décalages neutralisent la **même** semaine (recouvrement),
  on ne la neutralise qu'une fois (union). Confirmer que c'est le comportement
  voulu (un décalage de +2 et un de +1 qui se chevauchent ne cumulent pas les
  semaines communes).
- **Q3** : un créneau **sans date** (« à dater ») n'est pas affiché au
  calendrier ; il n'est pas concerné par les décalages. OK.
