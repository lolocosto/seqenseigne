# Redémarrage seqenseigne — v0.12.0 (chantier 1/5 de la série v0.12)

## Synthèse

**Plan de travail générique — données et saisie.**

C'est le premier chantier d'une série de 5 qui constituent ensemble la
v0.12. La série dans son ordre :

1. **v0.12.0** ← cette livraison : données du plan de travail (BDD +
   saisie dans l'atelier d'assemblage)
2. v0.12.1 : génération du livret annuel des plans de travail (portée
   niveau, agrégation des 14 séquences-niveau pour le cycle 4)
3. v0.12.2 : harmonisation visuelle des sidebars (notion / méthode /
   exercice / fiche)
4. v0.12.3 : suppression du toggle Assemblage / Édition avancée + retrait
   du rappel niveau/séquence sur la toolbar
5. v0.12.4 : migration ponctuelle méthodes ↔ objectifs (peuplement de
   `objectifs_v2.methode_id` quand le titre d'une méthode coïncide avec
   le nom d'un objectif de mêmes niveau et séquence)

## Ce qui change en v0.12.0

### Modèle de données

Deux nouvelles colonnes pour porter les nombres de séances prévues du
plan de travail générique (indépendamment de tout calendrier — les
colonnes `nb_seances_*` de la table `creneaux` restent dédiées au suivi
de classe annuel) :

- `sequence_parties.nb_seances_R_AE  REAL NOT NULL DEFAULT 0`
- `objectifs_v2.nb_seances           REAL NOT NULL DEFAULT 0`

Type **`REAL`** pour autoriser les demi-séances (0,5 — usage courant
attesté dans les plans de travail réels). Valeur par défaut **0** pour
le sens « non renseigné ».

Trois sémantiques de saisie :

| Champ | Localisation UI | Sens |
|---|---|---|
| `nb_seances_R_AE` (partie) | bandeau de partie | Total de séances pour les exos R + AE (regroupés) de cette partie |
| `nb_seances` (objectif code 01/11/21) | bandeau d'objectif "Cours" | Séances d'explication du cours en classe par l'enseignant |
| `nb_seances` (autre objectif) | bandeau d'objectif "Exo" | Séances de réalisation des exercices F + A + E |

### Migration

Idempotente, dans `_migrer_schema_post_ddl` (cohabite avec les
migrations v0.11.6 préexistantes). Détection via `PRAGMA table_info`,
`ALTER TABLE … ADD COLUMN` quand la colonne est absente. Aucune
manipulation de données existantes : tout repart à 0.

`schema.sql` (CREATE TABLE de référence) est aussi mis à jour pour les
bases neuves.

### API

Deux nouvelles routes :

- `PATCH /api/v2/parties/<partie_id>/seances`
  - Body : `{"nb_seances": <number|string>}`
  - Réponse 200 : `{"id", "numero", "nb_seances_R_AE"}`

- `PATCH /api/v2/objectifs/<objectif_id>/seances`
  - Body : `{"nb_seances": <number|string>}`
  - Réponse 200 : structure complète d'objectif (cf.
    `_format_retour_objectif`), avec un nouveau champ `nb_seances`

Codes d'erreur :

- 400 `champ_manquant` — payload sans `nb_seances`
- 400 `seances_invalides` — < 0, > 999, NaN, infini, types non
  numériques (None, bool, string non convertible)
- 404 `partie_introuvable` / `objectif_introuvable`

Tolérance d'entrée côté service `_valider_nb_seances` : accepte int,
float, et **string** convertible en float (utile en API HTTP) y compris
avec **virgule décimale française** (`"1,5"` → `1.5`) et espaces
parasites.

### Lecture (v2_lecture)

`lire_sequence_par_niveau` retourne désormais :

```json
{
  "sequence_par_niveau": { ... },
  "parties": [
    {
      "id": "pt_x",
      "numero": 1,
      "nb_seances_R_AE": 1.5,        ← NOUVEAU
      "precedences": [...],
      "objectifs": [
        {
          "id": "ob_x",
          "code": "01",
          "nom": "Cours",
          ...
          "nb_seances": 2.0,         ← NOUVEAU
          ...
        }
      ],
      ...
    }
  ],
  ...
}
```

Sélection défensive via `PRAGMA table_info` : si la base n'a pas encore
les colonnes (cas des tests qui chargent un schéma minimal antérieur),
le service retourne `0` sans planter.

### UI — atelier d'assemblage

Trois inputs numériques ajoutés (pattern `<label> + <input> + <unité s.>`) :

- **Bandeau de partie** (`.asm-partie-meta`) : `R+AE :  __  s.` —
  juste avant le bouton « Supprimer »
- **Objectif fermé** (`.asm-obj-actions`) : `Cours :  __  s.` (pour
  code 01/11/21) ou `Exos :  __  s.` (autres) — juste avant le bouton
  « Ouvrir »
- **Objectif ouvert** (`.asm-obj-actions`) : idem, juste avant
  « Fermer »

Persistance via le pattern habituel `onblur=…` (et `Entrée` qui blure)
appelant les nouveaux handlers `seqnivAsmChangerSeancesPartie` /
`seqnivAsmChangerSeancesObj`. État local rafraîchi silencieusement (pas
de re-rendu pour ne pas perdre le focus).

CSS : nouvelle classe `.asm-seances-input` + `.asm-seances-label` +
`.asm-seances-libelle` + `.asm-seances-unite` dans `app.css`. Largeur
52px, alignement à droite avec `font-variant-numeric: tabular-nums`,
flèches Chrome/Edge masquées (la molette et les flèches clavier
restent fonctionnelles).

## Tests

**Total : 1821 tests** (vs 1785 baseline v0.11.6.3) → **+36 tests v0.12.0**.

Nouveau fichier : `tests/test_v0_12_0_seances.py` avec 36 tests organisés en
6 sections :

1. `TestSchemaInit` (2) : présence des colonnes après init du
   `SqliteStore` + idempotence des relances
2. `TestModifierSeancesPartie` (14) : nominal, demi-séances, zéro,
   strings convertibles (point + virgule FR), espaces, persistance,
   bornes (négatif, > 999, exact 999), None, bool, partie introuvable
3. `TestModifierSeancesObjectif` (5) : objectif cours, objectif exo,
   persistance, objectif introuvable, négatif refusé
4. `TestLectureSeances` (3) : exposition des champs sur partie et
   objectif via `lire_sequence_par_niveau` + valeur par défaut 0
5. `TestRoutesSeancesPartie` (8) : intégration HTTP — nominal, demi,
   virgule FR, 404 partie inconnue, 400 sans champ, 400 négatif, 400
   aberrante, 400 string non convertible
6. `TestRoutesSeancesObjectif` (4) : nominal, 404, 400 sans champ,
   borne haute (999 accepté)

Mises à jour secondaires (assertions qui figeaient la liste des
colonnes du schéma — c'est leur rôle de signaler que le schéma a
changé) :
- `tests/test_R4a_schema.py::test_colonnes_sequence_parties` :
  ajout de `nb_seances_R_AE`
- `tests/test_R4a_schema.py::test_colonnes_objectifs_v2` :
  ajout de `nb_seances`

## Fichiers touchés

```
persistence/schema.sql                       (+15 lignes)
persistence/sqlite_store.py                  (+34 lignes)
services/v2_lecture.py                       (+50 lignes — réécriture
                                              _charger_parties + _charger_objectifs
                                              avec sélection défensive PRAGMA)
services/v2_edition.py                       (+~140 lignes — exception
                                              SeancesInvalides, helper de
                                              validation, deux mutations,
                                              nb_seances inclus dans
                                              _format_retour_objectif)
routes/v2_edition.py                         (+~80 lignes — 2 routes PATCH +
                                              import + mappage HTTP)
static/atelier_seqniv_assemblage.js          (+~80 lignes — 3 emplacements
                                              UI + 2 handlers + helper
                                              _fmtSeances + _trouverPartie)
static/app.css                               (+~45 lignes — classes
                                              .asm-seances-*)
tests/test_v0_12_0_seances.py                (NOUVEAU — 36 tests)
tests/test_R4a_schema.py                     (+4 lignes — assertions)
doc/redemarrage_v0_12_0.md                   (NOUVEAU)
```

## Procédure de déploiement

1. Décompresser le ZIP par-dessus `appli/` (au-dessus de la version
   v0.11.6.3 actuellement en place).
2. Relancer l'application — la migration de schéma s'exécute
   automatiquement au démarrage (idempotente, transparente, log
   classique).
3. Ouvrir l'atelier d'assemblage d'une séquence-niveau : les inputs
   apparaissent dans les bandeaux. Saisir des valeurs, vérifier la
   persistance (recharger la page, valeurs conservées).
4. Pour le test à froid sur le poste : `python -m pytest tests/` en
   environnement de dev (1821 tests attendus, ~1m45 sur poste rapide).

## Points de validation

À tester côté Laurent (déploiement réel) :

- **Migration** : la base existante doit accepter les nouvelles
  colonnes sans incident, sans perte de données. Les valeurs partent à
  0 partout (c'est attendu).
- **Saisie demi-séance** : taper `1.5` ou `1,5` doit fonctionner ; le
  PDF/JSON renvoie 1.5 dans les deux cas.
- **Saisie zéro** : vider l'input (chaîne vide) doit être interprété
  comme 0 et persisté.
- **Comportement Entrée** : appui sur Entrée doit valider et
  enregistrer (équivalent à un blur).
- **Layout** : vérifier que les inputs s'insèrent proprement à toutes
  les largeurs d'écran sans casser l'alignement de la barre d'actions.

## Prochaine étape

v0.12.1 — **Génération du livret annuel des plans de travail**
(portée niveau). Réutilise la mécanique LaTeX existante (`titrePlan`,
`\seqPlanObjectif`, `\blocReperesNiveaux` déjà présents dans
`seqenseigne-core.sty`), agrégation Python des séquences-niveau du
cycle. La nouvelle saisie v0.12.0 alimentera la ligne « Cours: …
séances » et les lignes « Objectif XX: … séances » du livret.
