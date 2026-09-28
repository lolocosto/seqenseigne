# Redémarrage v0.13.6.5.2

**Session du 14 mai 2026 — 4 services métier manquants**

---

## Périmètre

> *ok tout compile dans le référentiel sauf 4 : livret de fiches de
> résumé, livret de corrigés d'exercices, récap des cartes et planches
> de cartes*

Les 4 types levaient volontairement `type_non_implemente` depuis
v0.13.6.5.1.1 (stubs dans l'orchestrateur). Cette session les
implémente.

| Service | État | Volume sur N10 (BDD Laurent) |
|---|---|---|
| `livret_fiches` | ✅ | 84 k caractères, 57 fiches |
| `livret_corriges` | ✅ | 85 k (R+F) → 228 k (toutes séries) |
| `livret_cartes_recap` | ✅ | 55 k, 123 cartes (90 fixes + 33 paramétrées) |
| `livret_cartes_planches` | ✅ | 104 k, A4 paysage, 16 cartes/page |

---

## Décisions de session

### Q1 — Macros LaTeX récap/planches
> *Pas de nouvelle macro LaTeX, j'écris directement le code de mise en
> page (16 \\seqCarteAuto par page) dans les services Python*

Le paquet `seqenseigne-carte-automatisme` n'expose qu'une seule macro
publique : `\seqCarteAuto[options]{recto}{verso}`. Toute la mise en
page (récap 8/page recto+verso à suivre, planches 16/page recto puis
16/page verso) est faite dans le code Python qui assemble des
tabulars LaTeX autour des appels à la macro.

### Q2 — Cartes paramétrées sur planches
> *Utiliser des groupes LaTeX ({...}) pour scoper les définitions —
> chaque carte dans son groupe, mêmes noms réutilisés*

Vérifié par test isolation : les `\def` à l'intérieur d'un groupe
LaTeX `{...}` ne polluent pas le scope global. Chaque carte
paramétrée est donc enveloppée dans son propre groupe avec ses
variables xint définies juste avant l'appel à `\seqCarteAuto`.

Note importante : tu as confirmé que les noms de variables sont
**déjà préfixés par l'identifiant de la carte** (ex:
`N10S01C04_p`), donc même sans scoping, les cartes différentes
n'auraient pas conflit. Le scoping protège contre le cas futur où
tu voudras 16 tirages **différents** d'une même carte paramétrée
sur une planche (16 groupes, mêmes noms, 16 valeurs distinctes).

### Q3 — Disposition planches
> *A4 paysage : 16 cartes/page sans rotation*

`\geometry{a4paper, landscape, hmargin=0.5mm, vmargin=1mm}` permet
de loger 4 × 74mm = 296mm en largeur (< 297mm A4 paysage) et
4 × 52mm = 208mm en hauteur (< 210mm). Grille 4×4.

### Q4 — Corrigés
> *Livret pour l'enseignant qui ne contient que les corrigés (comme
> la section corrigé d'un livret de séquence), organisés par séquence
> et par série dans chaque séquence, en collectant les champs
> corrigés en base*

Pas de passage par la machinerie `\seqAfficheCorriges` du paquet
(qui nécessite la phase d'émission des énoncés). Extraction directe
du champ `corrige` de la table `exercices`, structuré par
thème → séquence → série, ordre canonique R / AE / F / A / E.
Filtrage par les options `inclure_serie_*` du catalogue v0.13.6.4.

---

## Fichiers livrés

### Nouveaux

| Fichier | Lignes | Rôle |
|---|---|---|
| `appli/services/livret_fiches.py` | ~270 | Pattern recap_cours, boucle fiches |
| `appli/services/livret_corriges.py` | ~300 | Extraction directe champ `corrige`, par série |
| `appli/services/livret_cartes_recap.py` | ~250 | Préambule statique, flux `\seqCarteAuto` |
| `appli/services/livret_cartes_planches.py` | ~280 | A4 paysage, grille 4×4 recto+verso |
| `appli/tests/test_v0_13_6_5_2_livrets_manquants.py` | ~480 | 23 nouveaux tests |
| `appli/doc/redemarrage_v0_13_6_5_2.md` | — | Ce fichier |

### Modifiés

| Fichier | Changement |
|---|---|
| `appli/services/orchestrateur_compilation.py` | Remplacement des 4 stubs `_TYPES_A_VENIR` par les 4 vrais producteurs |
| `appli/tests/test_v0_13_6_5_1_compilation.py` | 1 test adapté (sémantique inversée) |
| `appli/tests/test_v0_13_6_5_1_1_orchestrateur.py` | 3 tests adaptés (sémantique inversée) |

---

## Architecture

```
orchestrateur_compilation.py
  REGISTRE = {
    'livret_sequence':         services/livret_sequence.py         (v0.13.6.5.1)
    'livret_cours':            services/livret_recap_cours.py      (existant)
    'livret_exercices':        services/livret_recap_exos.py       (existant)
    'livret_plans':            services/livret_plans_de_travail.py (existant)
    'evaluation':              services/render_evaluation.py       (existant)
    'livret_fiches':           services/livret_fiches.py           ← v0.13.6.5.2
    'livret_corriges':         services/livret_corriges.py         ← v0.13.6.5.2
    'livret_cartes_recap':     services/livret_cartes_recap.py     ← v0.13.6.5.2
    'livret_cartes_planches':  services/livret_cartes_planches.py  ← v0.13.6.5.2
  }
```

Tous les types du catalogue v0.13.6.4 ont désormais leur producteur.

---

## Détails d'implémentation

### `livret_fiches.py`

- Pattern strictement copié de `livret_recap_cours.py` :
  `charger_atome('fiche', id)` → `generer_corps_fiche(atome)`.
- Préambule construit via `construire_preambule` (analyse des macros
  utilisées dans les champs `corps` des fiches).
- Option `version_fiches` :
  - `'a_completer'` (défaut) : pas de redéfinition, `\acompleter{X}`
    produit un trait souligné (version élève).
  - `'completes'` : ajoute `\renewcommand{\acompleter}[1]{#1}` dans
    le préambule (version prof, fiches complètes).
- Structure : page de garde + TOC + thème → séquence → fiches.

### `livret_corriges.py`

- Pas de boucle sur `charger_atome` : lecture directe du champ
  `corrige` de la table `exercices`.
- Résolution des getters CSV (`\seqObjectifGetNom`, etc.) sur chaque
  corrigé via `resoudre_macros_csv`.
- Préambule construit via `construire_preambule` sur le profil
  `exercice` (le plus large), analysé sur la concaténation des
  corrigés.
- Mapping des options du catalogue :
  - `inclure_serie_r_ae` → `serie_code IN ('R', 'AE')`
  - `inclure_serie_f` → `'F'`
  - `inclure_serie_a` → `'A'`
  - `inclure_serie_e` → `'E'`
- Défauts : R/AE et F inclus ; A et E exclus.
- Structure : page de garde + TOC + thème → séquence → série → liste
  d'exos numérotés avec leur corrigé.
- Note : seuls les exos dont le corrigé est non vide sont inclus.
  Comme tous tes exos ont un corrigé (règle métier), pas d'impact en
  pratique.

### `livret_cartes_recap.py`

- Préambule **statique** (calqué sur `services.render_carte`) — pas
  de passage par `construire_preambule` car les cartes ne déclenchent
  pas d'analyse de macros (le champ `recto`/`verso` est libre).
- Charge `seqenseigne-carte-automatisme` + `xint` + `seqenseigne-core` +
  `seqenseigne-theme`.
- Flux : 1 appel à `\seqCarteAuto` par carte, enveloppé dans un
  groupe LaTeX `{...}` qui scope les variables xint (pour les
  paramétrées).
- Saut de page `\cleardoublepage` entre séquences.
- En-tête par séquence avec le code de séquence et le nombre de
  cartes.
- Pas d'inversion (recto+verso à suivre naturellement, c'est
  `\seqCarteAuto` qui s'en charge).

### `livret_cartes_planches.py`

- Préambule statique idem recap, mais en **A4 paysage**.
- Grille **4 × 4** par page. Sur le verso, **ordre horizontal
  inversé** ligne par ligne pour que le pliage recto-verso fasse
  correspondre les bonnes faces.
- Logique sous-jacente : ne pas appeler `\seqCarteAuto` qui émet
  recto + verso d'un coup, mais appeler directement les sous-macros
  internes `\seqca@recto{...}` et `\seqca@verso{...}` après avoir
  initialisé les couleurs via `\setkeys[seqca]{carte}{...}` +
  `\seq@setColors{}` + `\seqca@applytheme`.
- Page de garde + 1 page double (recto + verso) par groupe de 16
  cartes par séquence.

---

## Tests

23 nouveaux tests dans `test_v0_13_6_5_2_livrets_manquants.py`,
couvrant :
- Génération .tex valide pour chaque type (4 tests)
- Options `version_fiches` (mode prof / élève) (2 tests)
- Options `inclure_serie_*` pour corrigés (4 tests : par défaut,
  toutes, exo sans corrigé ignoré, ordre canonique des séries)
- Paquet de cartes correctement chargé (1 test)
- Carte fixe rendue (1 test)
- Cartes paramétrées : variables xint scopées dans un groupe avant
  `\seqCarteAuto` (1 test)
- Cartes non-validées (`etat_code='en_cours'`) ignorées (2 tests)
- Saut de page entre séquences (1 test)
- Inversion horizontale des versos sur planches (1 test)
- 16 cartes = 1 page double (1 test)
- 17 cartes = 2 pages doubles (1 test)
- Orchestrateur : les 4 types sont enregistrés et ne lèvent plus
  `type_non_implemente` (3 tests)

4 tests existants des sessions précédentes adaptés à la nouvelle
sémantique :
- v0.13.6.5.1 : `test_generer_tex_type_non_implemente`
- v0.13.6.5.1.1 : `test_types_a_venir_levent_producteur_erreur`,
  `test_compiler_type_non_implemente`,
  `test_generer_tex_delegue_a_orchestrateur`

**Suite complète : 2464 passed, 5 skipped, 0 régression**
(2441 baseline v0.13.6.5.1.2 + 23 nouveaux v0.13.6.5.2).

---

## Vérifications côté Laurent

### Tests rapides à faire

1. **Activer un `livret_fiches`** dans l'atelier référentiel N10,
   cliquer Tester → doit produire un PDF avec 57 fiches.
2. **Activer `livret_corriges`** N10 (options par défaut : R/AE + F)
   → PDF avec corrigés des séries R/AE et F uniquement.
3. **Activer `livret_cartes_recap`** N10 → PDF avec 123 cartes,
   8 cartes/page, recto+verso à suivre.
4. **Activer `livret_cartes_planches`** N10 → PDF en A4 paysage,
   16 cartes/page, recto puis verso (inversion horizontale pour
   pliage).
5. **Test cartes paramétrées** : vérifier dans un PDF récap ou
   planches que les `\xintiieval{N10S01C04_p}` du recto et verso
   d'une carte paramétrée affichent **la même valeur** (preuve que
   les variables ont été tirées une seule fois et utilisées dans les
   deux faces).

### En cas d'échec

Le panneau « Voir les erreurs » de v0.13.6.5.1.1 te donne :
- Liste des erreurs avec ligne
- Bouton « Voir le .tex brut » avec lignes numérotées et highlight
- Bouton « Voir le log complet »
- Clic sur erreur → scroll vers la ligne fautive

Les artefacts sont sur disque sous
`data/referentiels/<ref_id>/_artefacts/<cible_key>.{tex,log}`.

### Limitations connues

- **Cartes paramétrées sur planches** : actuellement chaque
  exemplaire d'une carte sur la planche utilise les mêmes valeurs
  de variables xint (1 tirage par carte). Le mécanisme à 16 tirages
  différents par planche est l'objectif futur. Le scaffolding
  (groupes LaTeX) est en place, il manquera juste la logique de
  multi-tirage.
- **Préambule cartes statique** : pas d'analyse `construire_preambule`.
  Si une carte utilise une macro non standard absente de
  `seqenseigne-core`, elle pourrait planter sans message clair. À
  surveiller si tu introduis du contenu original dans `recto`/`verso`.

---

## Suite logique

| Version | Périmètre |
|---|---|
| **v0.13.6.5.3** | Figeage étendu — exiger `actif=True` + remplir tables `referentiel_*` à partir des données actives |
| Étape B refacto | Migrer routes existantes (rendu_atome, recap_cours, etc.) vers l'orchestrateur |
| Étape C refacto | Cleanup code mort |

Le scope de v0.13.6.5 est désormais clos sur les 4 services métier.
La feuille de route post-v0.13 reste celle annoncée (référentiel
niveau v0.13, admin tab v0.14, etc.).
