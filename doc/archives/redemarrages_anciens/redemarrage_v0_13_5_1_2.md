# Redémarrage v0.13.5.1.2 — Atelier Référentiel : refonte du rendu

## Périmètre

Suite des retours d'usage sur l'atelier Référentiel. Cinq évolutions
sur la mise en page de l'arbre du niveau et la cliquabilité des atomes.

### 1. Zone partie : R et EA toujours présents

Les lignes "Révisions :" et "Activité :" sont **toujours affichées**,
même si la partie n'a aucun exo dans cette catégorie. Quand il n'y a
rien : la mention "(aucun)" en gris italique.

Les exos R portent désormais leur **identifiant complet d'origine** :
`N09/S01/A01` (au lieu du code court R01 + tooltip). Les EA gardent le
code court `EA01`, `EA02`… (rangement local de la partie).

### 2. Zone objectif : mise en page fixe en lignes

```
Objectif 01 — Représentations d'un nombre
  Méthode    Fiche de résumé
  Notion : Proportionnalité    Notion : Pourcentages
  Série F :  F01 F02 F03
  Série A :  A01 A02
  Série E :  E01
```

- **Ligne 1** : `Méthode` + `Fiche de résumé` côte à côte. Pas de
  titre affiché (il est identique à celui de l'objectif). Tooltip au
  survol = titre complet.
- **Lignes notions** : `Notion : <titre>` en clair, flex-wrap si
  plusieurs.
- **Lignes F / A / E** : une ligne par série, code des exos en chip
  compact (`F01`, `F02`…). Toujours présentes, "(aucun)" si vide.

### 3. Méthode / fiche manquantes

Si l'objectif n'a pas de méthode liée (champ `methode_id` vide) ou pas
de fiche de résumé, le libellé devient `Méthode (manquante)` /
`Fiche de résumé (manquante)` en rouge pâle, non cliquable.

### 4. État valide / en_cours par couleur du texte

Les pastilles préfixe (point vert / point gris) ont disparu de l'arbre.
À la place, c'est la **couleur du texte** de chaque atome qui
indique l'état : vert (`#256029`) si `valide`, gris foncé (`#555`)
sinon. Plus discret, plus lisible quand il y a beaucoup d'atomes.

### 5. Atomes cliquables — ouverture en nouvel onglet

Chaque atome (méthode, fiche, notion, exo F/A/E, exo R/EA) est un lien
qui **ouvre un nouvel onglet** sur l'atelier d'atome correspondant,
avec sélection automatique de l'atome cible. Les R empruntés ouvrent
le bon niveau/séquence d'origine (par exemple, un R dans N11/S07
référencé `N10/S07/A01` ouvre l'atelier Exercice en N10/S07).

## Mécanique du deeplink (technique)

Le clic produit une URL `/?atelier=exercice&niveau=N11&seq=S07&atome=ex_abc`.
Au démarrage de l'appli (init), un nouveau bloc `_appliquerDeeplink()`
dans `app.js` :

1. Lit les paramètres URL.
2. Pose la portée Séquence + sélection (niveau, seq) en `localStorage`
   sous les clés existantes (`atl-portee-active`, `atl-portee-sel-sequence`).
3. Bascule sur l'onglet **Ateliers** (déclenche `initAteliers()`).
4. Appelle `atelSwitch(atelier)` après 300ms (laisse le pipeline
   d'init finir).
5. Re-tente `atel<Type>Charger(atome)` toutes les 150ms (jusqu'à 3s)
   pour attraper le moment où la liste de l'atelier est chargée.
6. Nettoie l'URL avec `history.replaceState` pour qu'un F5 ne
   replonge pas dans le deeplink.

**Limites** : si l'utilisateur a des modifs non sauvegardées dans
l'atelier source, la garde de sortie n'intercepte pas l'ouverture en
nouvel onglet (ce qui est cohérent — l'onglet source reste intact).

## Procédure de déploiement

1. Décompresser `seqenseigne-v0.13.5.1.2.zip` à la racine de `appli/`.
   **3 fichiers modifiés** :
   - `services/referentiels.py` (structure typée des objectifs)
   - `static/app.js` (mécanique deeplink dans `init()`)
   - `static/atelier_referentiel.js` (rendu refait)
   - `tests/test_v0_13_5_1_referentiels.py` (1 test ajouté)
   - `doc/redemarrage_v0_13_5_1_2.md` (ce fichier)

2. **Aucune migration de schéma** dans cette livraison.

3. Côté navigateur : **vider le cache** (Ctrl+F5).

## Compatibilité API

L'API `GET /api/referentiels/<id>/arbre` change de structure côté
objectifs :
- **Avant** : `objectif.atomes = [{type, id, code, ...}]` (liste plate)
- **Après** : `objectif.{methode, fiche, notions, exos_F, exos_A, exos_E}`
  (sous-sections typées)

Aucun autre consommateur de cette API en v0.13.5 — la structure n'est
utilisée que par l'atelier Référentiel.

## Tests

- **47 tests pytest verts** sur le périmètre v0.13.5.1.x (+1 nouveau
  pour la structure typée des objectifs).
- Suite globale : **2023 tests verts, 0 régression** (hors les
  20 tests `test_migrer_methodes_objectifs.py` cassés sur Windows par
  un bug d'encodage cp1252 indépendant — fix planifié en v0.14).

## Validation

Sur la BDD de Laurent :
- L'arbre du niveau N11 doit afficher 14 séquences.
- Pour S07 P1 : ligne `Révisions :` avec 5 items au format
  `N10/S07/A01`, `N10/S07/A02`, … et ligne `Activité :` avec ses EA.
- Pour les objectifs avec des fiches (ex. S01 P1 obj 02) : la fiche
  est présente avec le libellé "Fiche de résumé" cliquable.
- Cliquer sur "Méthode" d'un objectif → nouvel onglet, atelier
  Méthode ouvert sur la bonne méthode.
- Cliquer sur un exo R `N10/S07/A01` → nouvel onglet en N10/S07,
  atelier Exercice ouvert sur cet exo.
