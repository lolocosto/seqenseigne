# seqenseigne v0.6.3d — patch B1 (correctif B)

Correctif au patch B : les sélecteurs Année et Établissement restaient
vides à l'ouverture de l'onglet Progression annuelle.

## Cause

Dans l'ancien code (avant patch B), le bloc de sélection était entièrement
statique dans le HTML — le sélecteur de niveau avait ses 3 options en
dur, la liste des progressions se chargeait uniquement via
`progNiveauChange()` déclenchée par le `onchange` du sélecteur de niveau.
Rien n'appelait `progInit()` au premier passage sur l'onglet : ce
n'était pas nécessaire.

Le patch B a introduit deux nouveaux sélecteurs (Année, Établissement)
qui doivent se peupler **depuis le serveur** via `progInit()`. Cette
fonction n'était appelée nulle part au moment où l'utilisateur entre
sur le sous-onglet → sélecteurs vides, aucune XHR vers
`/api/annees-scolaires` ni `/api/etablissements`.

## Correctif

Dans `sousOnglet('progression')`, on appelle `progInit()` au premier
passage (quand aucune progression n'est encore chargée). Si une
progression est déjà en mémoire, on garde l'ancien comportement
(`progAjoutInit()` pour rafraîchir le formulaire d'ajout de créneau).

## Fichier modifié

`appli/static/app.js` — 6 lignes modifiées dans la fonction `sousOnglet`.

## Déploiement

```powershell
cd D:\Enseignement\seqenseigne
copy /Y patch_B1\appli\static\app.js appli\static\
```

Puis **Ctrl+F5** dans le navigateur.

## Vérification

Après rechargement de la page et clic sur « Progression annuelle »,
tu dois voir dans la console (ou dans l'onglet Réseau) :

```
XHR GET /api/annees-scolaires    200
XHR GET /api/etablissements      200
XHR GET /api/progression/N11/rechercher?annee=2025-2026&etablissement_id=et_2165207c   200
```

Et les 3 sélecteurs sont remplis, la progression N11 2025-2026 se
charge automatiquement.
