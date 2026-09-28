# Cadrage — Progressions « à la séance » : mises en route & automatismes (Leitner)

Statut : **cadrage consolidé après décisions Q1–Q7.** Prêt à passer en
spécification de la livraison 1. Rien n'est codé tant que la spec détaillée
n'est pas validée.

---

## 1. Le besoin

En parallèle de la progression principale (séquences/parties comptées en
**semaines**), les collègues font tourner une seconde progression
**indépendante**, comptée **en séances** :

- **mises en route** : les 5-10 premières minutes de chaque séance (calcul
  mental, etc.) ;
- **automatismes** : cartes recto/verso imprimées et distribuées aux élèves,
  révisées selon la méthode de **Leitner** (enveloppes 0 à 4, révision espacée).

Ces deux progressions à la séance sont **génériques** (cycle 3 et cycle 4), pas
spécifiques à la 6ᵉ.

---

## 2. Décisions actées (Q1–Q7)

- **Q1 — Modélisation : Option A.** Entité dédiée `progression_seance`
  (indépendante de `creneaux`), pour ne pas mélanger les deux unités de temps
  (semaine vs séance).
- **Q2 — Alternance réelle, granularité CLASSE.** Les semaines sont étiquetées
  alternativement **A** et **B**. Pour chaque classe, on saisit le nombre de
  séances en semaine A et en semaine B (ex. 6ᵉ : A=4, B=5 ; 5ᵉ/4ᵉ/3ᵉ : A=3,
  B=4). Ce couple (séances A, séances B) par classe absorbe les évolutions
  futures et permet une projection séance→date exacte.
- **Q3 — Un seul type de mise en route par séance** (exclusif). Une séance porte
  soit une mise en route, soit un automatisme, pas les deux.
- **Q4 — Atelier + import, à terme intégré au référentiel.** On construit (ou
  adapte) un atelier pour saisir/importer les documents des mises en route ;
  à terme tout entre dans le référentiel avec le mécanisme
  verrouillage/utilisation (comme les séquences).
- **Q5 — Les cartes d'automatisme n'ont PAS de niveau Leitner en base.** Elles
  sont imprimées et distribuées ; le classement Leitner (enveloppe 0-4) est
  **physique, côté élève**. L'appli ne suit donc pas le niveau d'une carte : elle
  produit un **planning de révision par enveloppe** (voir §5.4).
- **Q6 — Générique** (cycle 3 et cycle 4), pas seulement la 6ᵉ.
- **Q7 — Chantier prioritaire** (avant la reprise de l'import historique 4e3
  2023-24).

---

## 3. Correction du modèle Leitner (suite Q5)

Le champ `niveau` de `cartes_automatisme` est le **niveau scolaire** (N09…N12),
pas un niveau Leitner. Il n'existe aucun suivi Leitner par carte en base — c'est
voulu : le dispositif est physique.

Donc la « progression d'automatismes » n'est **pas** un suivi de cartes, mais un
**calendrier de révision par enveloppe** : à chaque séance dédiée aux
automatismes, on indique quelles enveloppes (niveaux Leitner) sont révisées,
selon la cadence :

| Enveloppe Leitner | Révisée… |
|-------------------|----------|
| 0 | chaque séance d'automatismes |
| 1 | 1 séance sur 2 |
| 2 | 1 sur 4 |
| 3 | 1 sur 8 |
| 4 | 1 sur 16 |

Progression géométrique (×2). Le compteur avance d'**une unité par séance dédiée
aux automatismes** (pas par séance tout court, puisque Q3 rend les jours
exclusifs). L'appli génère ce planning ; l'enseignant sait ainsi, pour chaque
séance d'automatismes, quelles enveloppes faire réviser.

---

## 4. L'existant à réutiliser

- **Cartes d'automatisme** : atelier + table `cartes_automatisme` déjà en place
  (recto/verso A8, 5 types pédagogiques, lien notion/méthode). Le nouveau
  chantier s'appuie dessus ; il ne recrée pas les cartes.
- **`preferences_items (id, type, valeur, ordre)`** : table générique de
  préférences déjà utilisée (`type='titre_zone_fiche'`). Support idéal pour la
  liste extensible des **types de mise en route**
  (`type='type_mise_en_route'`).
- **`classes (id, nom, niveau, annee, etablissement_id, progression_id)`** :
  point de rattachement des séances A/B (granularité classe, Q2).
- **`param_niveaux`** : déjà multi-cycles (N07/N08 = CM1/CM2), cohérent avec le
  caractère générique (Q6).
- **Calendrier** (`atelier_progression.js`) : gère déjà vacances et jours
  fériés ; à réutiliser pour projeter séances→dates.

---

## 5. Architecture proposée

### 5.1 Rythme de séances par classe (semaines A/B)

Nouvelle table (ou colonnes sur `classes`) : pour chaque classe, `seances_A` et
`seances_B` (entiers), plus le point de départ de l'alternance (quelle semaine
est « A »). La projection séance→date parcourt le calendrier semaine par
semaine, en attribuant 4 ou 5 (resp. 3/4) séances selon l'étiquette A/B, en
sautant les semaines de vacances (déjà connues du calendrier).

### 5.2 Types de mise en route (extensible, Préférences)

Dans `preferences_items`, `type='type_mise_en_route'` : chaque item = un type
(libellé + nature `mise_en_route`|`automatisme` encodée dans `valeur`, ex.
JSON). Éditable dans Préférences, sans redéploiement.

### 5.3 Entité `progression_seance` (Q1 : Option A)

Progression à la séance rattachée à une classe (ou au couple niveau/année,
à préciser). Chaque « créneau à la séance » : numéro de séance (ou plage), type
de démarrage (référence à un type de mise en route OU « automatismes »),
contenu/lien. Indépendante de la progression principale.

### 5.4 Générateur d'ordonnancement

À partir de la progression de démarrage + du rythme A/B de la classe :
- projette chaque séance sur une date réelle ;
- pour les séances « automatismes », calcule les enveloppes Leitner à réviser
  (cadence ×2, compteur sur les séances d'automatismes) ;
- pour les séances « mise en route », rattache le type/document.

---

## 6. Impact / compatibilité (vérifié)

1. **Deux unités de temps** : la progression principale reste en semaines ; la
   progression de démarrage est en séances, projetée via A/B. Nouvelle vue à
   concevoir, mais le calendrier (vacances/fériés) est réutilisable. **OK.**
2. **Cartes d'automatisme réutilisées** telles quelles ; pas de niveau Leitner à
   ajouter (Q5). **OK, aucun impact sur `cartes_automatisme`.**
3. **Mises en route ≠ séquences du référentiel** au départ, mais Q4 prévoit leur
   intégration à terme au référentiel (verrouillage/utilisation). Prévoir une
   structure qui pourra converger vers ce mécanisme.
4. **Documents des collègues** (PDF/ODT) : importés via l'atelier (Q4), pas en
   masse automatique. **Acté.**
5. **Préférences extensibles** : `preferences_items` déjà éprouvé. **OK.**

---

## 7. Découpage en livraisons proposé

1. **Modèle & préférences** : (a) rythme A/B par classe ; (b) types de mise en
   route extensibles dans Préférences. Tests. Pas encore d'UI de progression.
2. **Entité `progression_seance` + projection séance→date** (via A/B +
   calendrier), CRUD minimal.
3. **Ordonnancement Leitner** : planning de révision par enveloppe pour les
   séances d'automatismes (cadence ×2).
4. **Atelier mises en route + import des documents** (Q4), convergence
   progressive vers le référentiel.
5. **Vue calendrier** de la progression de démarrage, en parallèle de la
   principale.

---

## 8. Questions restantes pour la spec de la livraison 1

- **R1** — Rythme A/B : nouvelles colonnes `seances_A`/`seances_B` sur `classes`,
  ou table dédiée `rythme_classe` ? Et comment fixe-t-on quelle semaine
  calendaire est « A » (date de référence de l'alternance) ?
- **R2** — `progression_seance` rattachée à la **classe** ou au couple
  **niveau/année** (comme les progressions principales, partagées entre classes
  jumelles) ? Sachant que le rythme A/B est par classe (Q2), l'un peut différer
  de l'autre.
- **R3** — Types de mise en route : structure exacte de `valeur` dans
  `preferences_items` (libellé seul, ou libellé + nature + couleur en JSON) ?
- **R4** — Faut-il, dès la livraison 1, préparer la convergence vers le
  référentiel (Q4), ou la traiter plus tard sans contrainte de modèle maintenant ?

À réception des réponses R1–R4, je rédige la spec détaillée de la livraison 1
(modèle + préférences) puis je code.
