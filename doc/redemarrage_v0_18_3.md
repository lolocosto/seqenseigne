# Redémarrage v0.18.3 — Unification série approche (AE) + ouverture R/EA

Trois corrections liées, plus un inventaire de ménage.

## Problèmes traités

1. **Ctrl+double-clic inopérant pour les exos de révision (R) et d'approche
   (EA) dans l'atelier séquence-niveau.** Les chips R/EA n'avaient aucun
   handler d'ouverture (ni clic ni double-clic).
2. **Exos d'approche invisibles** dans l'atelier exercice et la sidebar
   d'assemblage (ex. N10/S03).
3. **Incohérence de préfixe** `EA` (N10/S03) vs `AE` (N10/S04), à unifier.

## Cause racine commune

La série « approche » coexistait en base sous DEUX `serie_code` : `AE` (89 exos,
convention dominante — livrets, compilation, nommage `...AExx.tex`) et `EA`
(2 exos, anomalie). Le code était contradictoire : `v2_edition` *créait* en
`EA` (validation) mais *lisait* en `AE` (mapping `_SERIE_CODE_EQUIVALENT`).
Selon le chemin emprunté, des exos approche devenaient invisibles (un filtre
attendait l'un, la donnée portait l'autre).

**Distinction clé** : le sigle `EA` servait à DEUX choses différentes —
- le **RÔLE** d'un exo dans une partie (`partie_exos_revision_approche.type`,
  valeurs `'R'`/`'EA'`) → **conservé en `EA`** (rôle, pas une série) ;
- la **SÉRIE** d'un exercice (`serie_code`) → **unifiée en `AE`** partout.

## Décisions (D1–D8)

- **D1** — `serie_code` de la série approche = `AE` partout (code, API, base,
  affichage).
- **D2** — `v2_edition.py` : `_SERIES_VALIDES`/`_SERIE_CODE_EQUIVALENT` en `AE`
  (mapping devenu identité) ; validation d'ajout approche exige
  `serie_code='AE'` ; message d'erreur corrigé. `v2_lecture.py` : `SERIES_V2`
  en `AE`.
- **D3** — Script de migration `outils/migrer_serie_ea_vers_ae.py` (dry-run par
  défaut, confirmation `OUI`, vérification post-migration). Migre
  `exercices.serie_code` et `objectif_exos.serie` de `EA` vers `AE`.
  **La base n'est PAS incluse dans ce delta** (tu as tes propres données sur
  D:/E:). **Action requise au déploiement** : lancer le script sur chaque base
  AVANT d'utiliser les nouveaux écrans, sinon les exos `EA` resteront
  invisibles :

      # Dry-run (compte, ne touche à rien) :
      python -m outils.migrer_serie_ea_vers_ae
      # Application réelle (confirmation OUI) :
      python -m outils.migrer_serie_ea_vers_ae --apply
- **D4** — Affichage en `AE` (l'identifiant dérive de `serie_code`, donc
  automatique ; badge/titre front passés à `AE`).
- **D6** — Rôle `EA` dans `partie_exos_revision_approche.type` **inchangé**.
  Le front conserve la dropzone de rôle `EA` mais l'exo catalogue porte
  désormais la série `AE` : le drop est **découplé** (`okEA` exige
  `dz==='EA'` ET `_drag.serie==='AE'`).
- **D7** — Chips R/EA : ajout d'un `ondblclick` →
  `editerAtome('exercice', id, event, niveau, sequence)`. Ctrl/⌘+double-clic =
  nouvel onglet, vers la séquence d'**origine** (révision : `origin_niveau/seq`
  ; approche : `origin_*` NULL en base → on retombe sur le niveau/séquence de
  l'exercice, qui est la séquence courante).
- **D8** — Inventaire du ménage Python (racine, scripts/, outils/) consigné
  dans `doc/inventaire_menage_python_v0_18_3.md`. **Aucune suppression
  effectuée** : décision et déplacement à venir dans une livraison dédiée.

## Fichiers modifiés

- `services/v2_edition.py` — constantes série `AE`, validation `AE`, message
  d'erreur.
- `services/v2_lecture.py` — `SERIES_V2` = `("AE","F","A","E")`.
- `static/atelier_seqniv_assemblage.js` — front série/affichage `AE` (badge,
  `serie_cible`, titre de section) ; `okEA` découplé rôle/série ; ouverture
  des chips R/EA (`_rendreChipsRA`).

(La base `data/seqenseigne.db` n'est pas livrée — migration via le script,
cf. D3.)

## Fichiers ajoutés

- `outils/migrer_serie_ea_vers_ae.py` — script de migration.
- `doc/inventaire_menage_python_v0_18_3.md` — inventaire D8.
- `doc/redemarrage_v0_18_3.md` — cette note.

## Tests

- pytest : 4 fichiers adaptés en distinguant rôle/série
  (`test_v0_10_assemblage`, `test_v0_10_2_precedences`, `test_R4e1_v2_lecture`,
  `test_R4e4b_edition_exos`) : fixtures `serie_code` `EA`→`AE`, assertions de
  série et de clés `exos_par_serie` `EA`→`AE`. Les `type_='EA'` (rôle) et les
  clés de résultat `rep["EA"]` (rôle) sont **inchangés**.
- vitest : `tests_js/atelier_seqniv_assemblage.test.js` +6 cas (découplage
  drop rôle/série ; ouverture chips R/EA vers la bonne séquence d'origine ;
  badge d'origine).

**Zéro régression** : pytest → 3832 passed, 7 skipped ; vitest → 136 passed
(13 fichiers).

## Anomalie annexe signalée (hors périmètre v0.18.3)

`objectif_exos.serie` contient 2 lignes avec la valeur `'avancé'` au lieu du
code `'A'`. Sans impact visible mais incohérent avec le reste (codes courts).
À nettoyer dans une passe ultérieure (un simple UPDATE, mais à cadrer).
