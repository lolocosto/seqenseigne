# Redémarrage v0.13.6.5.2.1

**Session du 14 mai 2026 — Correctifs post-v0.13.6.5.2**

---

## Périmètre

Après ton test des 4 documents v0.13.6.5.2, 4 problèmes signalés :

| # | Problème | Diagnostic |
|---|---|---|
| 1 | Boutons « Voir le .tex / log » affichent toujours le dernier élément compilé | Tous les types unitaires utilisent `cible_id='unique'` → artefacts écrasés mutuellement dans `_artefacts/unique.{tex,log}` |
| 2 | livret_corriges : définitions xint oubliées | J'avais oublié de propager `exercices.variables` dans mon service, contrairement à `livret_sequence` qui le fait |
| 3 | livret_cartes_planches : `\seq@setColors`, `\seqca@recto`, etc. hors `\makeatletter` | Ces macros internes contiennent `@` qui n'est lettre qu'entre `\makeatletter` et `\makeatother` |
| 4 | cartes_recap + cartes unitaires : `\num` non défini | `siunitx` manquant dans les préambules statiques cartes |

Les 4 sont corrigés.

---

## Détails des fixes

### Fix 1 — Sous-dossier par doc_id pour les artefacts

**Avant** : `data/referentiels/<ref_id>/_artefacts/<cible_key>.{tex,log,pdf}`

**Après** : `data/referentiels/<ref_id>/_artefacts/<doc_id>/<cible_key>.{tex,log,pdf}`

Pour les types multi-cibles (`livret_sequence`, `evaluation`), le `cible_key` reste pertinent (1 fichier par séquence/éval). Pour les types unitaires, `cible_key='unique'` ne collisionne plus puisque chaque doc a son sous-dossier.

Fichiers modifiés :
- `appli/services/referentiel_documents_compilation.py` : `dossier_artefacts = dossier_ref / '_artefacts' / doc_id`
- `appli/services/referentiel_documents_compilation.py` : `chemin_artefact(store, ref_id, doc_id, cible_key, extension)` (signature étendue avec `doc_id`)
- `appli/routes/referentiel_documents_compilation.py` : passage de `doc_id` à `chemin_artefact`

### Fix 2 — livret_corriges embarque les définitions xint

Lecture du champ `exercices.variables` (qui contient `\xintdefiivar N10S01A01_x := randrange(1,10);` etc.) et émission **avant** la liste des corrigés de chaque série, alignée sur le pattern de `services.livret_sequence`.

Fichier modifié : `appli/services/livret_corriges.py`
- `_lire_exos_corriges` retourne aussi `variables`
- Propagation dans `exos_resolus` puis émission au début de chaque
  `\subsubsection{Série X}` avant le `\begin{description}` des corrigés

Vérifié sur la vraie BDD N10 toutes séries : 50 `\xintdefiivar` émis pour 105 `\xintiieval` (toutes les variables référencées sont définies).

### Fix 3 — `\makeatletter` autour des sous-macros internes dans planches

Les sous-macros `\seq@setColors`, `\seqca@recto`, `\seqca@verso`,
`\seqca@applytheme`, `\setkeys[seqca]` contiennent `@` qui n'est lettre
qu'entre `\makeatletter` et `\makeatother`. Chaque appel de carte sur
les planches est maintenant enveloppé dans :
```
{%
  \makeatletter
  ...définitions xint si paramétrée...
  \setkeys[seqca]{carte}{...}
  \seq@setColors{...}
  \seqca@applytheme
  \seqca@recto{...}{...}{...}{...}{...}    OU \seqca@verso
  \makeatother
}
```

Fichier modifié : `appli/services/livret_cartes_planches.py` (fonction `_rendre_face`)

**Note** : c'est un fix temporaire (et un peu moche). En v0.13.6.5.2.2,
on passera à `\seqCarteRecto[options]{contenu}` et
`\seqCarteVerso[options]{contenu}` qui seront des macros publiques
exposées par le `.dtx` (sans `@`). Tu prends en charge cette évolution
côté paquet, je ferai le passage Python ensuite.

### Fix 4 — `siunitx` dans les préambules cartes

`\num{...}` est utilisé dans 4 cartes N10 (et probablement plus avec les
autres niveaux à venir). `siunitx` était absent des préambules statiques
cartes. Ajouté dans :

- `appli/services/render_carte.py` (cartes unitaires, atelier carte)
- `appli/services/livret_cartes_recap.py`
- `appli/services/livret_cartes_planches.py`

---

## Fichiers livrés

### Modifiés (6)

| Fichier | Changement |
|---|---|
| `appli/services/referentiel_documents_compilation.py` | Sous-dossier `_artefacts/<doc_id>/` + signature `chemin_artefact` étendue |
| `appli/routes/referentiel_documents_compilation.py` | Passage `doc_id` à `chemin_artefact` |
| `appli/services/livret_corriges.py` | Propagation et émission des `variables` xint |
| `appli/services/livret_cartes_recap.py` | `\usepackage{siunitx}` dans préambule |
| `appli/services/livret_cartes_planches.py` | `siunitx` + `\makeatletter`/`\makeatother` autour des `\seq@*` |
| `appli/services/render_carte.py` | `\usepackage{siunitx}` (impact aussi sur l'atelier cartes unitaires) |

### Tests (1)

| Fichier | Changement |
|---|---|
| `appli/tests/test_v0_13_6_5_2_livrets_manquants.py` | +5 tests v0.13.6.5.2.1 (variables xint, siunitx ×2, makeatletter, chemin_artefact par doc_id) |

### Documentation (1)

| Fichier | Type |
|---|---|
| `appli/doc/redemarrage_v0_13_6_5_2_1.md` | Ce fichier |

---

## Tests

- Tests v0.13.6.5.2.1 (5 nouveaux) : tous passent
- Suite complète : **2469 passed, 5 skipped, 0 régression**

---

## Validation chez toi

### À retester en priorité

1. **Recompiler les 4 documents** dans l'atelier référentiel N10. Cliquer
   « Voir les erreurs » sur chacun → tu dois voir **4 .tex et 4 logs
   différents** (un par document), pas un seul partagé.
2. **livret_corriges N10 toutes séries** : doit compiler maintenant que
   les `\xintdefiivar` sont émis avant les `\xintiieval` qui les
   utilisent.
3. **livret_cartes_recap N10** : doit compiler les 4 cartes utilisant
   `\num` grâce à `siunitx`.
4. **livret_cartes_planches N10** : doit compiler les `\seq@setColors`
   etc. grâce à `\makeatletter`/`\makeatother`. **Note** : c'est un fix
   temporaire ; on passera à des macros publiques `\seqCarteRecto`/
   `\seqCarteVerso` en v0.13.6.5.2.2 quand tu auras fait évoluer le
   `.dtx`.

### Bug UI à observer

Le panneau « Voir les erreurs » devrait maintenant te montrer **le bon
.tex et le bon log** pour chaque document, plus le contenu du dernier
compilé. Si tu compiles tous les 4, puis cliques « Voir les erreurs »
sur chacun, tu verras 4 contenus distincts.

---

## Suite logique

- **v0.13.6.5.2.2** (prochaine) : passage à `\seqCarteRecto[options]{contenu}`
  et `\seqCarteVerso[options]{contenu}` dans `livret_cartes_planches.py`
  une fois que tu auras :
  - Ajouté les 2 macros publiques dans `seqenseigne-carte-automatisme.dtx`
    (mêmes options que `\seqCarteAuto`, mêmes dimensions 74mm×52mm)
  - Réimporté tes définitions pour que `paquet_definitions` connaisse
    les nouvelles macros
- **v0.13.6.5.3** : figeage étendu (suite logique de v0.13.6.5)
- Étape B refacto : migrer routes existantes vers l'orchestrateur
