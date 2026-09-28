# Redémarrage v0.13.6.14 — Atelier carte (3 affinages) + Chantier D fiche

## Périmètre

Deux chantiers UI dans la même livraison :

### Atelier carte — 3 affinages

1. Suppression du cadre « Objectifs liés » (redondant avec l'affichage
   en sidebar via les tags `obj XX`).
2. Numéro affiché en lecture seule. Il est fixé par l'application à la
   création de la carte. Un réordonnancement par drag-and-drop dans la
   sidebar pourra être ajouté plus tard.
3. Renommage « Nom (interne) » → « Titre » avec, sur la même ligne, le
   bouton « ⤵ reprendre titre objectif » (cohérent avec les autres
   ateliers atomiques). Le mécanisme du chantier B (v0.13.6.11) fonctionne
   directement : c'est `_injecterBoutonReprendreTitre('atl-carte-titre')`
   appelé dans `remplirFormulaire` qui pilote l'affichage conditionnel.

**Côté BdD/API** : la colonne `nom` de `cartes_automatisme` n'est pas
renommée. L'asymétrie « UI parle de Titre, API/BdD parlent de nom » est
assumée — c'est la même politique que la migration `exercices.nom →
titre` v0.13.6.12, mais en plus minimal : pas de migration du tout, juste
un mapping côté JS (`this.$('titre').value → nom` dans
`collecterFormulaire`).

### Chantier D — Suppression du sélecteur d'objectif dans l'atelier fiche

Le sélecteur d'objectif disparaît de l'atelier fiche. Le rattachement
d'une fiche à un objectif se fait désormais **uniquement depuis l'atelier
d'assemblage de séquence** (cohérent avec la politique générale actée
au chantier C : on crée les atomes dans leur atelier, on les rattache
en assemblage).

**Workflow nouveau** :
1. L'enseignant filtre sur une séquence (N10/S01 par exemple)
2. Clic sur « Nouvelle fiche » → fiche orpheline créée dans N10/S01
   avec un `num_fiche` calculé automatiquement
3. L'enseignant remplit le titre + les sections
4. Plus tard, depuis l'atelier d'assemblage de séquence (N10/S01), il
   rattache la fiche à un objectif de la séquence

**Workflow ancien préservé** : les appels API qui passent encore
`objectif_id` (typiquement des scripts ou tests existants) fonctionnent
comme avant — la dérivation niveau/séquence depuis l'objectif est
préservée.

## Statut alpha — rappel

Aucune mise en production nulle part. Aucune modification de schéma
BdD dans cette livraison. La colonne `fiches_resume.objectif_id` est
déjà nullable (FK avec `ON DELETE SET NULL`), donc le code support des
fiches orphelines est compatible avec les données existantes.

## Décisions actées

| Q | R |
|---|---|
| Renommage colonne `cartes_automatisme.nom` ? | Non : mapping UI seulement |
| Validation fiche : exiger objectif rattaché ? | Non : une fiche orpheline peut être validée. Cohérent avec le workflow « créer dans l'atelier, rattacher depuis l'assemblage ». |
| niveau/sequence à la création | Toujours envoyés dans le body POST. Ignorés par PUT (uniformité collecterFormulaire). |
| Suppression de `_chargerObjectifsDisponibles`, `_peuplerSelectObjectif` | Oui, code mort après le retrait du sélecteur. |

## Architecture backend du chantier D

### Signature `creer_fiche` étendue

```python
def creer_fiche(
    conn, *,
    objectif_id: str | None = None,    # NOUVEAU : optionnel
    niveau:      str | None = None,    # NOUVEAU : obligatoire si pas d'objectif
    sequence:    str | None = None,    # NOUVEAU : obligatoire si pas d'objectif
    titre:       str = "",
    sections:    list[dict] | None = None,
) -> dict:
```

Deux modes :

- **Mode historique** (`objectif_id` fourni) : comportement inchangé.
  `niveau`/`sequence` déduits de l'objectif. Tous les tests et scripts
  existants continuent de fonctionner sans modification.
- **Mode v0.13.6.14** (`objectif_id=None`) : `niveau` et `sequence`
  obligatoires. La fiche est créée orpheline (`objectif_id` NULL).
  Lève `ValueError` si `niveau` ou `sequence` manque.

### Route `/api/fiches-resume` (POST)

Body accepté :

```json
// Mode historique
{ "objectif_id": "ob_xxx", "titre": "...", "sections": [...] }

// Mode v0.13.6.14
{ "niveau": "N10", "sequence": "S01", "titre": "...", "sections": [...] }
```

Erreur 400 `champ_manquant` si `objectif_id` absent ET `niveau`/`sequence`
manquants. Erreur 400 `params_invalides` si le service lève `ValueError`.

### Route `/api/fiches-resume/<id>` (PUT) inchangée

Le PUT continue d'accepter `titre`, `sections`, `objectif_id` (tous
optionnels). C'est le mécanisme à utiliser pour **rattacher une fiche
orpheline** à un objectif depuis l'atelier d'assemblage de séquence
(cf. test `test_creation_orpheline_puis_rattachement`).

## Fichiers livrés

```
appli/services/fiches_resume.py           creer_fiche : objectif_id optionnel
appli/routes/fiches_resume.py             api_creer_fiche : mode sans objectif
appli/static/atelier_carte_automatisme.js Titre + bouton reprendre + num RO
appli/static/atelier_fiche.js             Suppression sélecteur objectif
appli/templates/index.html                Bloc Objectif lié + cadre Objectifs liés
                                          + cadre Identification carte refondu
appli/tests/test_v0_10_5_fiches_resume.py +5 tests pour le mode v0.13.6.14
```

## Vérification

- Suite complète : **3238 passed, 5 skipped, 0 failed** chez moi (4 min 46 s)
- 0 régression sur les 3233 tests qui passaient en v0.13.6.13
- 5 nouveaux tests ajoutés couvrent : création orpheline, validation
  niveau/sequence obligatoires, rattachement ultérieur, partage du
  compteur num_fiche entre fiches orphelines et rattachées
- Syntaxe Python (`ast.parse`) et JS (`node -c`) validées
- Audit refs orphelines : `atl-fiche-objectif`, `objectifsCache`,
  `_peuplerSelectObjectif`, `_chargerObjectifsDisponibles` n'apparaissent
  plus que dans des commentaires explicatifs

## À tester chez toi

### Atelier carte

1. **Cadre Identification** : le numéro doit s'afficher en lecture
   seule (`CA03` par exemple) avec le rappel niveau/séquence à côté.
   Plus d'input numérique modifiable.
2. **Label « Titre »** : à la place de « Nom (interne) ». Bouton
   « ⤵ reprendre titre objectif » à droite sur la même ligne, visible
   uniquement si la carte a exactement 1 lien obj avec un nom non vide.
3. **Bouton « reprendre titre objectif »** : clic → titre = nom de
   l'objectif (avec confirm si titre déjà rempli, comportement standard
   chantier B).
4. **Cadre « Objectifs liés »** : doit avoir disparu (la sidebar
   affiche déjà les tags `obj XX`).
5. **Tags sidebar** : doivent toujours s'afficher.
6. **Régression** : enregistrer une carte doit toujours fonctionner ;
   la valeur saisie dans « Titre » se retrouve bien dans la BdD comme
   `cartes_automatisme.nom`.

### Atelier fiche

1. **Bloc « Objectif lié »** : doit avoir disparu.
2. **Création d'une nouvelle fiche** :
   - Filtrer N10/S01 dans la barre globale
   - Cliquer « Nouvelle fiche »
   - Remplir « Titre » + sections, enregistrer
   - La fiche apparaît dans la sidebar avec son numéro
   - En BdD, `objectif_id` est NULL, `niveau='N10'`, `sequence='S01'`
3. **Bouton « ⤵ reprendre titre objectif »** : pour une fiche orpheline
   (sans objectif), le bouton est masqué (`_reprendreObjectifDispo`
   retourne `null` quand `liens` est vide). Quand la fiche sera
   rattachée à un objectif depuis l'assemblage, le bouton apparaîtra.
4. **Bouton « Initialiser depuis » dans les zones** : sur une fiche
   orpheline, le sélecteur affiche « Pas d'objectif lié sélectionné »
   (comportement déjà présent avant cette livraison, non modifié).
5. **Régression sur les fiches existantes** (déjà rattachées à un
   objectif) :
   - Ouverture : OK, titre et sections s'affichent comme avant
   - Modification du titre/sections : OK
   - Le PUT continue d'envoyer `objectif_id` du body collecté (qui ne
     contient plus ce champ) mais ne le change pas — le service ne
     touche à `objectif_id` que si explicitement fourni dans le body.

### Vérification BdD (post-déploiement)

```sql
-- Nombre de fiches orphelines en BdD
SELECT COUNT(*) FROM fiches_resume WHERE objectif_id IS NULL;
-- Attendu : 0 sur ta BdD actuelle (toutes les fiches sont rattachées)
-- Après création d'une fiche depuis l'atelier : 1, 2, ...

-- Vérification de la numérotation continue
SELECT niveau, sequence, num_fiche, objectif_id, titre
  FROM fiches_resume ORDER BY niveau, sequence, num_fiche;
-- Les num_fiche doivent rester contigus dans chaque séquence
```

## Points de vigilance

1. **`collecterFormulaire` envoie niveau/sequence aussi en PUT** : c'est
   inoffensif (la route les ignore), mais c'est une trace utile pour le
   debug futur. Si un jour quelqu'un ajoute une logique « si niveau
   change, refaire X » côté PUT, il faudra distinguer les cas.

2. **Numérotation `num_fiche` mélange orphelines et rattachées** :
   c'est un compteur unique par (niveau, sequence). Une fiche orpheline
   prend son numéro dans la même séquence que les fiches rattachées.
   À la suppression d'une fiche, on ne renumérote pas — comportement
   inchangé.

3. **Bouton « Initialiser depuis » nécessite un objectif rattaché** :
   à terme, dans le workflow nominal, l'enseignant créera la fiche
   orpheline, la rattachera à un objectif depuis l'assemblage, puis
   reviendra dans l'atelier fiche pour utiliser « Initialiser depuis »
   sur une zone. C'est cohérent mais demande un aller-retour atelier
   → assemblage → atelier. À surveiller comme friction UX.

## Prochaine étape

Migration des ateliers d'édition restants :
- **Migration `AtelierEvaluation` en OO** (~1235 lignes, encore à
  variables globales `ATL_EVAL_*` + 49 fonctions globales `atelEval*`).
  C'est le gros morceau qu'il reste pour finir la migration OO
  initialement prévue.
- **Création de `AtelierAssemblage`** : indispensable pour matérialiser
  l'UI de rattachement carte→objectif et fiche→objectif (sans cette UI,
  les fiches orphelines créées par le chantier D restent orphelines en
  pratique). Étape 2 de la roadmap globale.
- **Création de `AtelierRecap`** : pour les ateliers récap.
- **Nettoyage `atelier_atome_generique.js`** (~600 lignes de code mort)
  + audit de `atelier_commun.js` (832 lignes).
- **v0.14** : retraits de schéma planifiés
  (`cartes_automatisme.lien_type`/`lien_id`, etc.)
