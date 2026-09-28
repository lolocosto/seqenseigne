# patch v0.10.5.2 — Préférences + Sélecteur titre zone + Import fiches `.tex`

**Date** : 2 mai 2026

**Périmètre** : table `preferences_items` paramétrable, sélecteur de
titre de zone fiche avec liste paramétrable, import des fiches de
résumé depuis fichiers `.tex` cycle complet.

**Score tests** : 1656/1656 + 4 skipped historiques. **29 nouveaux
tests v0.10.5.2**. Aucune régression.

---

## 1 — Table `preferences_items` (Q4-a)

Schéma :

```sql
CREATE TABLE preferences_items (
    id     TEXT PRIMARY KEY,
    type   TEXT NOT NULL,
    valeur TEXT NOT NULL DEFAULT '',
    ordre  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_preferences_items_type ON preferences_items (type, ordre);
```

Table générique pour tous les paramètres utilisateur. Le `type` est un
discriminant qui regroupe les items du même paramètre.

**Deux modes d'usage** selon le type :
- **Liste** : plusieurs items du même type forment une liste triée
  par `ordre`. Ex: `type='titre_zone_fiche'` avec items Définition,
  Propriété, Méthode.
- **Valeur unique** : un seul item de ce type ; l'API valeur unique
  fait un upsert qui supprime les éventuels doublons.

**Seed** : 3 titres de zone par défaut (Définition, Propriété,
Méthode), insérés via `INSERT OR IGNORE` (idempotent — ne réécrase
pas une liste modifiée par l'utilisateur).

**API REST** :
- `GET    /api/preferences/<type>` — lister
- `POST   /api/preferences/<type>` — ajouter `{valeur, ordre?}`
- `PUT    /api/preferences/items/<id>` — modifier `{valeur?, ordre?}`
- `DELETE /api/preferences/items/<id>` — supprimer
- `PUT    /api/preferences/<type>/ordre` — réordonner `{ids: [...]}`
- `GET    /api/preferences/valeur/<type>` — lire valeur unique
- `PUT    /api/preferences/valeur/<type>` — upsert valeur unique

---

## 2 — Sélecteur titre de zone (Q4-b, Q4-c)

Le champ texte « Titre de la zone » dans l'atelier Fiche est remplacé
par un `<select>` qui propose :

1. Une option `— choisir —` (vide)
2. Les valeurs de la liste paramétrable (chargée depuis
   `/api/preferences/titre_zone_fiche`)
3. **Si la fiche a un titre hors liste** : une option `<valeur> (hors
   liste)` en tête, sélectionnée par défaut. Q4-c respectée — la
   valeur saisie historiquement est conservée même si elle n'est
   plus dans la liste paramétrable.
4. Une option finale `+ Personnalisé…` qui déclenche un `prompt()`
   pour saisie libre (Q4-b avec **info** : « Pour ajouter ce titre de
   manière permanente à la liste, rendez-vous dans Admin >
   Préférences. »).

**UI gestion de la liste** : nouvelle section dans l'onglet
**Préférences** (déjà existant) → « Titres de zone des fiches de
résumé ». Permet :

- Édition inline du libellé (blur = sauvegarde)
- Boutons monter / descendre
- Suppression avec confirmation (qui rappelle que les fiches existantes
  conservent leur titre)
- Ajout via input + bouton

Pas de bouton « Enregistrer » global : chaque action est persistée
immédiatement.

**Cache d'invalidation** : le module `atelier_fiche.js` expose une
fonction `atelFicheInvaliderCacheTitres()` que la section Préférences
appelle à chaque modification, pour que la liste soit rerelée au
prochain render de l'atelier.

---

## 3 — Import des fiches de résumé depuis `.tex` (Q7-a, Q7-c, Q7-d)

### Format source supporté

Fichiers historiques « Flashcards année complète » (5e, 4e, 3e). Format :

```latex
\seqSetSequence{S01}
\boiteTitreFlashcard{Objectif 02}{}
\begin{boiteContenuFlashcard}[titre=Définition]
contenu LaTeX
\end{boiteContenuFlashcard}
\begin{boiteContenuFlashcard}[titre=Propriété]
contenu LaTeX
\end{boiteContenuFlashcard}
\begin{boiteFillContenuFlashcard}\end{boiteFillContenuFlashcard}
\boiteTitreFlashcard{03}{}        ← format adapté sans préfixe "Objectif"
\begin{boiteContenuFlashcard}[titre=Méthode]
...
\end{boiteContenuFlashcard}
\begin{boiteFillContenuFlashcard}\end{boiteFillContenuFlashcard}
```

Le parser accepte indifféremment `\boiteTitreFlashcard{Objectif 02}{...}`
et `\boiteTitreFlashcard{02}{...}`.

### Convention « plusieurs fiches par objectif » (subtilité importante)

Le format source **autorise** plusieurs flashcards distinctes pour le
même objectif (cf. `\boiteTitreFlashcard{Objectif 04}{1\iere fiche}\boiteTitreFlashcard{Objectif 04}{2\ieme fiche}`
ligne 60 du 5e).

**Décision** : on **fusionne** ces flashcards multiples en une seule
fiche en BDD, avec toutes les zones concaténées. Cohérent avec la
spec Q3-1 « 1 fiche = 1 méthode = 1 objectif » (cardinalité 1-1).

### Algorithme du parser

Walker linéaire sur le texte avec gestion d'une **file FIFO de titres**.

- À chaque `\boiteTitreFlashcard{XX}` rencontré → ajouter `XX` dans la
  file (sans le consommer).
- À chaque `\begin{boiteContenuFlashcard}` (début de section) → si
  aucune section en cours, dépiler le 1er titre de la file pour devenir
  l'objectif courant.
- À chaque `\begin{boiteFillContenuFlashcard}` (séparateur) → fin de
  la section ; le prochain `boiteContenuFlashcard` consommera le
  titre suivant.

Cette logique reproduit fidèlement la convention du format source
(plusieurs titres consécutifs annoncent les sections à venir, dans
l'ordre).

### Idempotence (Q7-c)

Pour chaque fiche extraite :
- Si **pas** de fiche en BDD pour `(niveau, sequence, code_obj)` →
  **création** (avec `num_fiche` auto, `etat_code='en_cours'`).
- Si **fiche existante** → **ajout** des zones extraites à la fin
  (sans toucher aux zones existantes).

Le rapport distingue `fiches_creees` et `fiches_etendues`.

### Objectifs introuvables (Q7-d)

Si la fiche extraite cible un objectif qui n'existe pas en BDD
(`objectifs_v2` pour `(niveau, sequence, code)`), elle est **ignorée**
et son code est ajouté à `rapport.objectifs_introuvables`. Le rapport
HTTP 200 reste en succès — l'import continue avec les autres fiches.

### Volumétrie validée

Tests sur les 3 fichiers fournis :
- 5e (N10) : 57 fiches, 142 zones
- 4e (N11) : 57 fiches, 130 zones
- 3e (N12) : 36 fiches, 153 zones

### UI Admin

Nouveau sous-onglet **Import fiches** dans Admin (entre Images et
Base de données). Formulaire :

- **Niveau cible** (sélecteur N09…N12, défaut N11)
- **Fichier .tex** (input file)
- **Importer**

Le rapport s'affiche après l'import : nombre de fiches créées /
étendues / objectifs introuvables, avec liste détaillée.

---

## 4 — Ce qui n'est PAS dans v0.10.5.2

Volontairement reportés pour minimiser le risque de régression :

- **Refonte des sous-onglets Import existants** (importref +
  importpaquet + images en un seul écran avec chemins lecture seule
  depuis préférences). Reportée à une livraison dédiée — les écrans
  actuels fonctionnent et la base technique (service `configuration.py`,
  endpoint `/api/configuration/chemins-resolus`) est déjà en place
  côté backend.

- **Compilation PDF d'une fiche** (bouton manquant dans la toolbar).
  La compilation suppose un préambule LaTeX adapté
  (`documentclass=a5paper,landscape`, paquets dédiés). Reportée à
  v0.11.0 quand on tranchera entre :
  - inclusion des fiches dans chaque livret de séquence,
  - livret annuel à part « cahier de cours ».

---

## 5 — Fichiers ajoutés / modifiés

### Backend (nouveaux)
```
services/preferences.py                   — CRUD + valeur unique
routes/preferences.py                     — 7 endpoints
services/fiches_import.py                 — parser + import idempotent
```

### Backend (modifiés)
```
persistence/schema.sql                    — table preferences_items + seed
app.py                                    — enregistre bp_preferences
routes/admin.py                           — POST /api/admin/fiches/import
```

### Frontend (modifiés)
```
templates/index.html                      — section Préférences > Titres
                                            de zone, sous-onglet Admin
                                            > Import fiches
static/atelier_fiche.js                   — sélecteur titre avec liste
                                            paramétrable + saisie libre,
                                            cache invalidable
static/app.js                             — gestion section Préférences
                                            (CRUD inline), gestion sous-
                                            onglet Import fiches (upload)
```

### Tests
```
tests/test_v0_10_5_2_preferences_et_imports.py
                                          — 29 tests (service prefs, routes,
                                            parser, import, route admin)
```

---

## 6 — Test manuel après déploiement

### Préférences > Titres de zone fiche

1. Ouvrir l'onglet **Préférences** (en haut à droite, à côté de Aide).
2. Section « Titres de zone des fiches de résumé » : doit lister
   Définition / Propriété / Méthode (le seed).
3. Ajouter un titre « Démonstration » → apparaît à la fin.
4. Drag/drop pas implémenté, mais utiliser ↑ / ↓ pour réordonner.
5. Renommer un titre en cliquant dans le champ, modifier, blur (Tab
   ou clic ailleurs).
6. Supprimer un titre via × → confirm.

### Sélecteur titre dans l'atelier Fiche

1. Aller dans Atelier > Fiche de résumé.
2. Créer une nouvelle fiche.
3. Le champ « Titre » d'une zone est maintenant un sélecteur avec les
   options de la liste paramétrable + « + Personnalisé… ».
4. Choisir « + Personnalisé… » → un `prompt()` s'ouvre avec un message
   sur les Préférences. Saisir « Démo » → le sélecteur affiche « Démo
   (hors liste) » comme option sélectionnée.
5. Ouvrir une fiche qui a un titre historique non dans la liste : le
   sélecteur affiche bien la valeur sous « (hors liste) ».

### Import fiches `.tex`

1. Admin > **Import fiches**.
2. Choisir niveau N10, sélectionner `5e_Flashcards_-_année_complète.tex`.
3. Cliquer Importer.
4. Vérifier le rapport : ~57 fiches créées, ~142 zones ajoutées (chiffres
   exacts dépendent des objectifs présents en BDD).
5. **Test idempotence** : relancer le même import → 0 fiche créée, 57
   fiches étendues, 142 zones ajoutées (les anciennes zones ne sont
   pas écrasées).
6. **Test objectif introuvable** : si certains objectifs ne sont pas
   en BDD (par ex. car non encore importés depuis le référentiel),
   ils apparaissent dans la section « Objectifs introuvables » du
   rapport.

---

## 7 — Pièges connus

- **Les fiches multiples par objectif sont fusionnées**. Si tu veux
  garder distinct « Obj 04 fiche 1 » et « Obj 04 fiche 2 » comme deux
  fiches BDD séparées, il faudra adapter le modèle (passer la
  cardinalité à 1-N) et le parser. À l'usage classique, la fusion
  est cohérente avec la spec Q3-1 et le visuel d'une fiche unique
  par objectif.

- **Le parser ne supporte pas les commentaires `%`** au milieu des
  blocs `boiteContenuFlashcard`. Si une ligne `% commentaire` apparaît
  au milieu du LaTeX d'une zone, elle est conservée telle quelle dans
  le corps importé (ce qui est correct pour l'usage final).

- **Aucune compilation PDF des fiches importées**. À l'import, on
  pose juste le contenu LaTeX brut dans `atome_section_items.corps`.
  La compilation viendra avec v0.11.0.

- **L'import n'utilise pas les préférences `chemin_*`**. L'utilisateur
  sélectionne le fichier directement via `<input type="file">`. Une
  amélioration future serait de proposer un chemin par défaut depuis
  les préférences.

- **`atelFicheInvaliderCacheTitres` n'est appelé que depuis le panneau
  Préférences**. Si tu ouvres deux onglets navigateur, l'un éditant
  les Préférences et l'autre l'atelier Fiche, ce dernier ne verra pas
  les modifs avant un rechargement complet (Ctrl+R). Pas un cas
  pratique courant.
