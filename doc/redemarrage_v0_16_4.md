# Redémarrage v0.16.4 — Verrou « validé = lecture seule »

## Contexte

La validation (`etat_code = 'valide'`) a changé de nature. À l'origine simple
marqueur de confort, elle certifie désormais la cohérence d'un item (barèmes
valides, exos notés — v0.16.3). Or on pouvait encore éditer après validation,
donc casser l'invariant que la validation est censée garantir (ex. passer un
barème d'exo à 0 après l'avoir validée).

**Règle introduite** : un item validé est en LECTURE SEULE. Pour le modifier,
il faut explicitement le repasser en cours, puis revalider.

Cf. `cadrage_verrou_validation.md`. Décisions : périmètre = tous les ateliers ;
mécanisme = UI grisée + backend qui refuse (défense en profondeur) ; suppression
d'un item validé autorisée (confirmation UI) ; opérations de structure refusées ;
code HTTP 409 ; pas de bandeau.

## Périmètre de cette version

- **Backend (garde 409)** : TOUS types, **y compris l'évaluation** → ferme le
  trou de sécurité partout immédiatement (c'est la vraie garantie).
- **UI lecture seule** : **atomes seulement** (générique dans `AtelierEditeur` :
  notion, méthode, exercice, fiche, carte).
- **UI évaluation** : suivra en 2b-2. En attendant, l'UI éval reste éditable
  mais le backend refuse (409) ; l'éval affiche un message clair sur ce 409.

## Ce qui est livré

### Backend — refus de modification d'un item validé (409 `item_verrouille`)

- `services/etats_edition.py` : nouvelle exception `ItemVerrouille` + helper
  `assert_atome_modifiable(conn, type, id)` (lève si `valide` ; laisse passer si
  introuvable pour ne pas masquer un 404).
- `routes/atomes.py` : garde dans `_update` du helper générique → couvre
  notion/méthode/exercice. **Pas** de garde sur `_delete` (suppression permise).
- `routes/fiches_resume.py`, `routes/cartes_automatisme.py` : garde dans la
  route PATCH.
- `routes/evaluations.py` : helper `_assert_eval_modifiable` + `item_verrouille`
  ajouté au mapping HTTP (409). Garde appliquée aux routes de CONTENU : PATCH
  éval (**sauf** si le PATCH ne touche que `etat_code` — c'est une
  (dé)validation, autorisée), ajout/retrait/PATCH d'exo, barèmes groupés,
  réordonnancement, ajout/retrait d'objectif. **Pas** de garde sur
  valider/devalider, DELETE éval, rendu-pdf.

### UI atomes — lecture seule

- `static/atelier_editeur.js` : méthode `_appliquerVerrouLectureSeule(estValide)`
  qui désactive les champs (input/select/textarea/button/[contenteditable])
  DANS le formulaire quand l'item est validé. Appelée depuis `afficherEditeur`.
  Le bouton « Repasser en cours », les onglets et « Compiler » sont hors
  formulaire → restent actifs (seule action d'édition = repasser en cours ;
  consulter le rendu reste permis). Idempotent (mémorise l'état d'origine via
  `data-verrou-orig`) ; exemption possible via `data-verrou-exempt`. Classe CSS
  `atl-verrou-lecture-seule` posée sur le form (style optionnel).

### UI évaluation — gestion propre du 409 (transitoire)

- `static/atelier_evaluation_oo.js` : `_api` affiche un toast explicite sur un
  409 `item_verrouille` (« Évaluation validée (lecture seule)… »), au lieu des
  messages génériques des catch appelants. Verrou UI complet en 2b-2.

### Test mis à jour (changement de règle assumé)

- `tests/test_v0_10_4_etats_edition.py` : l'ancien `test_put_notion_preserve_etat`
  (qui vérifiait qu'on pouvait modifier une notion validée en préservant l'état,
  Q2-N) est remplacé par `test_modif_notion_validee_refusee` (→ 409) et
  `test_modif_notion_apres_devalidation_ok` (repasser en cours puis modifier →
  200). Documente le renversement de règle v0.16.4.

## Tests

**v0.16.4 : 3758 passed, 7 skipped, 0 failed.**

Nouveau `tests/test_v0_16_4_verrou_validation.py` :
- Helper `assert_atome_modifiable` : en_cours passe, validé lève, introuvable
  ne lève pas.
- Routes atomes : PATCH notion validée → 409 ; en cours → 200 ; DELETE validée
  → autorisée.
- Routes éval : PATCH champ validé → 409 ; PATCH etat_code seul → 200 ; ajout
  exo / barèmes groupés sur éval validée → 409 ; suppression éval validée →
  autorisée.
- UI structurel : `_appliquerVerrouLectureSeule` présent et appelé.

## Fichiers livrés (`seqenseigne_v0_16_4.zip` — incrémental depuis v0.16.3)

| Fichier | Action |
|---|---|
| `appli/services/etats_edition.py` | Modifié (ItemVerrouille + assert_atome_modifiable) |
| `appli/routes/atomes.py` | Modifié (garde _update) |
| `appli/routes/fiches_resume.py` | Modifié (garde PATCH) |
| `appli/routes/cartes_automatisme.py` | Modifié (garde PATCH) |
| `appli/routes/evaluations.py` | Modifié (garde routes contenu) |
| `appli/static/atelier_editeur.js` | Modifié (verrou UI atomes) |
| `appli/static/atelier_evaluation_oo.js` | Modifié (toast 409) |
| `appli/tests/test_v0_10_4_etats_edition.py` | Modifié (règle renversée) |
| `appli/tests/test_v0_16_4_verrou_validation.py` | Nouveau |
| `appli/doc/cadrage_verrou_validation.md` | Nouveau (cadrage) |
| `appli/doc/redemarrage_v0_16_4.md` | Nouveau (ce document) |

## Vérification post-déploiement

```powershell
.\outils\python\python.exe outils\verifier_md5.py --racine . --manifest MANIFEST.md5
.\outils\python\python.exe -m pytest tests/ -q
```

Tests fonctionnels :
1. Atome (notion/méthode/exercice/fiche/carte) validé → champs grisés, seul
   « Repasser en cours » est actif. Repasser en cours → champs réactivés.
2. Tenter (via outil/API) de modifier un atome validé → 409.
3. Évaluation validée → l'UI reste éditable (normal cette version), mais toute
   tentative de modification renvoie un message « validée (lecture seule) ».
   La suppression d'une éval validée reste possible.

## Suite

- **v0.16.5 (2b-2)** : régime de persistance mixte de l'évaluation (form +
  collecterFormulaire + snapshot) ET verrou UI lecture seule de l'évaluation
  (les deux chantiers convergent ici).
- **Observation notée (préexistante, hors sujet)** : on peut valider une éval
  via `PATCH etat_code=valide` en contournant les contrôles métier de
  `/valider`. À traiter séparément si souhaité.
