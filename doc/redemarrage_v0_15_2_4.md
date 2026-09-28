# Redémarrage v0.15.2.4 — Découpage des planches par séquence (performance)

## Objectif

Résoudre le problème de **timeout de compilation** des planches de
cartes d'automatisme. Compiler les 119 planches d'un niveau dans un
seul `.tex` prend ~5min40 (3808 tcolorbox : 119 × 2 pages × 16 cellules),
au-delà du timeout appli (300s).

Solution actée avec Laurent : **découpage en 1 PDF par séquence**
(≈8-9 planches → ~25-30s/séquence), TOUT EN conservant **une cible
unique** (PDF complet du niveau) pour qui peut compiler hors contrainte
de temps.

Aucune modification du paquet LaTeX (`.dtx`/`.sty`) : la refonte
`\seqCartePlanche` de v0.15.2.3 reste en place. Tous les changements
sont côté Python.

## Décisions tranchées en début de session

| # | Question | Décision |
|---|---|---|
| Q1 | Quel chantier en premier ? | **Découpage planches (chantier 1, cadré).** |
| Q2 | Garder aussi une cible PDF unique « toutes planches » ? | **Oui, les deux** (unique + 14 séquences). |
| Q3 | Découper aussi le récap des cartes ? | **Non**, reste unitaire (17 pages, rapide). |

## Changements

### 1. `services/referentiel_documents_compilation.py` — `lister_cibles_document`

Nouvelle branche `livret_cartes_planches`. Renvoie **deux familles** de
cibles :

- **1 cible `'unique'`** (rétrocompatible) :
  `nom_fichier = 'livret_cartes_planches.pdf'`, pas de clé `'sequence'`
  → le générateur produit toutes les planches du niveau.
- **N cibles par séquence** (sur les séquences ayant au moins une carte
  `etat_code='valide'`) :
  - `cible_id = 'N10/Sxx'`
  - `nom_fichier = 'livret_cartes_planches__N10__Sxx.pdf'`
  - `sequence = 'Sxx'` → le générateur filtre à cette séquence.

Modèle calqué sur la branche `livret_sequence` existante. Source : table
`cartes_automatisme` (et non `sequences_par_niveau`), car une planche
n'existe que s'il y a effectivement des cartes valides.

### 2. `services/livret_cartes_planches.py` — paramètre `sequence` optionnel

- `_lire_cartes_du_niveau(conn, niveau, sequence=None)` : si `sequence`
  est fourni, ajoute `AND sequence = ?` au SQL. Sans `sequence` (défaut)
  → comportement v0.15.2.3 inchangé.
- `_page_de_garde(niveau, cartes, sequence=None)` : ajoute
  « — séquence Sxx » au sous-titre si filtré.
- `generer_livret_cartes_planches(..., sequence=None, ...)` : propage
  partout. Commentaire en-tête `%% Séquence : Sxx (découpage par séquence)`
  si filtré. Message d'erreur dédié si la séquence n'a aucune carte
  valide.

**Rétrocompatibilité totale** : tous les appels existants
(`generer_livret_cartes_planches(conn, 'N10')` ou avec `options={}`)
continuent de produire le PDF complet du niveau.

### 3. `services/orchestrateur_compilation.py` — `_produire_livret_cartes_planches`

Passe `cible.get('sequence')` au générateur. Cible `'unique'` → `None` →
toutes séquences. Cible par séquence → `'Sxx'` → filtrage.

### 4. Tests nouveaux — `tests/test_v0_15_2_4_planches_decoupage_sequence.py`

9 tests nommés protègent les décisions non-évidentes :

1. `test_cibles_planches_vide_renvoie_seulement_unique`
2. `test_cibles_planches_unique_plus_une_par_sequence` (ordre, noms de fichier)
3. `test_cibles_planches_ignore_cartes_non_valides`
4. `test_lire_cartes_filtre_sequence`
5. `test_generer_sequence_ne_contient_que_la_sequence`
6. `test_generer_sans_sequence_contient_tout` (rétrocompat)
7. `test_page_de_garde_mentionne_sequence`
8. `test_generer_sequence_vide_message_dedie` (équilibre `{}`, `\end{document}`)
9. `test_producteur_propage_sequence` (orchestrateur)

## Vérifications validées

- **Pas de collision de cibles.** `slug_cible('unique') = 'unique'`,
  `slug_cible('N10/S01') = 'N10_S01'`. Les artefacts sont isolés par
  `doc_id` (`_artefacts/<doc_id>/<cible_key>.{tex,log,pdf}`), donc les
  15 cibles d'un même document coexistent sans conflit.
- **`nom_fichier` métier rétrocompatible.** La cible unique conserve
  `livret_cartes_planches.pdf` : tout appel existant pointant ce chemin
  continue de fonctionner.
- **Données réelles N10** (sauvegarde de production) : 14 séquences
  valides, 3 à 18 planches par séquence (médiane ~7). Découpage
  parfaitement adapté.

## Effet attendu côté UI

Pour un référentiel N10 complet, le document « livret_cartes_planches »
exposera désormais **15 cibles** dans la barre de progression :
- `Planches N10 (toutes séquences)` — cible `unique`
- `Planches N10/S01` à `Planches N10/S14` — une par séquence valide

Laurent peut compiler les séquences individuellement (chacune sous le
timeout) et garder l'option du PDF unique pour les compilations en
arrière-plan.

## État des tests

**v0.15.2.4 : 3503 passed, 6 skipped, 0 failed** (+9 nouveaux tests
par rapport à v0.15.2.3).

## Pas dans v0.15.2.4 (suite roadmap)

Conservés dans `redemarrage_prochaine_session.md` pour cadrage en
session suivante :

- **Chantier 2** : péremption ciblée (par type de document → tables
  d'atomes concernées ; granularité par cible).
- **Chantier 3** : figeage du référentiel (snapshot des données de
  référence dans les tables `referentiel_*` millésimées).
- Retour à l'**atelier assemblage séquence-dans-niveau** (chantier 2 de
  la roadmap globale, marqué EN COURS dans userMemories) — à arbitrer
  avec Laurent.

## Fichiers livrés

Tous complets, conformément à la convention :

| Fichier | Type |
|---|---|
| `appli/services/referentiel_documents_compilation.py` | Modifié |
| `appli/services/livret_cartes_planches.py` | Modifié |
| `appli/services/orchestrateur_compilation.py` | Modifié |
| `appli/tests/test_v0_15_2_4_planches_decoupage_sequence.py` | Nouveau |
| `appli/doc/redemarrage_v0_15_2_4.md` | Nouveau (ce document) |

Pas de `.dtx`/`.sty` cette livraison : aucune nouvelle macro paquet.

## Vérification du delta

```powershell
.\outils\python\python.exe scripts\verifier_md5.py --racine . --manifest MANIFEST.md5
```

Puis :

```powershell
.\outils\python\python.exe -m pytest -q
# Attendu : 3503 passed, 6 skipped, 0 failed
```
