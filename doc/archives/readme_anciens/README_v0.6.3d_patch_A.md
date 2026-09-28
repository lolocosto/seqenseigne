# seqenseigne v0.6.3d — patch A « recherche de progression par triplet »

Backend du chantier de refonte du bloc « Sélection de progression » de
l'écran Progression annuelle.

## Objet du patch

Préparer le bloc « Sélection de progression » côté backend, en fournissant
les données dont le frontend (patch B) aura besoin :

1. la liste des années scolaires connues du système (fichier de config JSON) ;
2. la liste des référentiels disponibles par niveau ;
3. la recherche d'une progression par son triplet métier
   `(niveau, année, établissement)`.

## Endpoints nouveaux

```
GET /api/annees-scolaires
    → { "annee_courante": "2025-2026",
        "annees_scolaires": [
          {"code": "2025-2026", "libelle": "2025-2026", "archive": false},
          ...
        ] }

GET /api/referentiels?niveau=N10
    → { "referentiels": [
          {"id": "N10_v2024", "niveau": "N10", "version": "2024",
           "description": "Mis en place à la rentrée 2024",
           "etat": "verrouille"},
          ...
        ] }
    Tri : version décroissante (plus récent en tête).
    Sans paramètre niveau : retourne tous les référentiels.

GET /api/progression/<niveau>/rechercher?annee=AAAA-AAAA&etablissement_id=et_xxx
    → 200 { "trouve": true,  "progression": {...} }
    → 200 { "trouve": false, "triplet": {"niveau":..., "annee":..., "etablissement_id":...} }
    → 400 si annee ou etablissement_id manquants
    → 500 { "code": "doublon_base" } si incohérence (≥ 2 progressions,
           normalement impossible grâce à UNIQUE (niveau, annee, etablissement_id))
```

## Nouveaux fichiers

```
appli/config/annees_scolaires.json          — liste statique éditable à la main
appli/services/annees_scolaires.py          — lecture du JSON
appli/routes/annees_scolaires.py            — blueprint Flask
appli/services/referentiels.py              — logique par-niveau + recommandé
appli/routes/referentiels.py                — blueprint Flask
appli/tests/test_annees_scolaires.py        — 10 tests
appli/tests/test_referentiels_service.py    — 10 tests
appli/tests/test_progression_rechercher.py  — 11 tests
```

## Fichiers modifiés

```
appli/app.py
    → import et enregistrement de 2 nouveaux blueprints
      (bp_annees_scolaires, bp_referentiels).

appli/persistence/sqlite_store.py
    → ajout de lire_progression_par_triplet(niveau, annee, etablissement_id).
      Méthode jumelle de lire_progression() qui prend l'UUID opaque au lieu
      du nom d'établissement. Lève RuntimeError en cas d'incohérence.

appli/routes/progression.py
    → ajout de la route /api/progression/<niveau>/rechercher.
```

## Contenu du fichier `config/annees_scolaires.json`

Fichier statique édité à la main. Pour ajouter une année :

```json
{
  "annee_courante": "2025-2026",
  "annees_scolaires": [
    {"code": "2021-2022", "libelle": "2021-2022", "archive": true},
    {"code": "2025-2026", "libelle": "2025-2026", "archive": false},
    {"code": "2026-2027", "libelle": "2026-2027", "archive": false},
    {"code": "2027-2028", "libelle": "2027-2028", "archive": false}   ← ajouter ici
  ]
}
```

- `archive: true` : l'année apparaît en fin de liste (plus récente d'abord
  dans la section archivée).
- `annee_courante` : code de l'année présélectionnée à l'ouverture de
  l'écran Progression annuelle (à basculer chaque rentrée).

## Déploiement

```powershell
# Depuis D:\Enseignement\seqenseigne, avec l'archive du patch dézippée :
# les fichiers écrasent ceux existants et ajoutent les nouveaux.

copy /Y patch_A\appli\config\annees_scolaires.json          appli\config\
copy /Y patch_A\appli\services\annees_scolaires.py          appli\services\
copy /Y patch_A\appli\services\referentiels.py              appli\services\
copy /Y patch_A\appli\routes\annees_scolaires.py            appli\routes\
copy /Y patch_A\appli\routes\referentiels.py                appli\routes\
copy /Y patch_A\appli\routes\progression.py                 appli\routes\
copy /Y patch_A\appli\persistence\sqlite_store.py           appli\persistence\
copy /Y patch_A\appli\app.py                                appli\
copy /Y patch_A\appli\tests\test_annees_scolaires.py        appli\tests\
copy /Y patch_A\appli\tests\test_referentiels_service.py    appli\tests\
copy /Y patch_A\appli\tests\test_progression_rechercher.py  appli\tests\
```

Le dossier `appli\config\` n'existe pas avant ce patch — le fichier
`annees_scolaires.json` le crée automatiquement à la copie, à condition
d'utiliser `xcopy /I` ou de créer le dossier au préalable. Robuste :

```powershell
if not exist appli\config mkdir appli\config
```

Aucune migration de base n'est nécessaire (la contrainte UNIQUE sur
`(niveau, annee, etablissement_id)` est déjà en place).

## Tests

```powershell
cd appli
..\outils\python\python.exe -m pytest tests\ -q
```

Résultat attendu : **400 tests verts** (369 existants + 31 nouveaux).
Aucun test existant n'est modifié, aucune régression.

## Ce qui ne change pas côté UI

Aucune modification de `templates/index.html`, `static/app.js` ou
`static/app.css` dans ce patch. Le bloc « Sélection de progression »
actuel fonctionne toujours comme avant — les nouveaux endpoints ne
sont pas encore consommés par le front. Ce sera l'objet du patch B.

## Points d'attention

- **Cache JSON** : `services/annees_scolaires.py` lit le fichier à chaque
  appel (pas de cache en mémoire). Une modification du JSON est donc prise
  en compte sans redémarrage de Flask. C'est volontaire : volume minime,
  fichier édité très rarement.
- **Validation d'année à la création** : le patch A ne vérifie pas que
  `annee` fournie dans une requête figure bien dans le JSON. C'est laissé
  à la charge du patch B (l'UI ne proposera que des années valides) et
  le cas dégradé du patch C (clic « + Créer » sur un triplet exotique
  tombera sur l'endpoint existant `POST /api/progression/<niveau>`).
