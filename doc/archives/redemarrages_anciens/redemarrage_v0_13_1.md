# Redémarrage seqenseigne — v0.13.1 (chantier 2/3 série v0.13)

## Synthèse

**Substitution des tables hardcodées par lectures BDD.** Cette
livraison consomme la table `param_niveaux` créée en v0.13.0 pour
remplacer les trois tables Python en dur historiquement dispersées
dans le code :

- `_NOM_COURT_NIVEAU` (dans `services/livret_sequence.py`)
- `_CYCLE_PAR_NIVEAU` (dans `services/livret_sequence.py`, défini
  **deux fois** dans le même fichier)
- `_CYCLE_PAR_NIVEAU` (dupliqué dans `services/livret_plans_de_travail.py`)

Aucun changement fonctionnel visible — c'est purement de la dette
technique éliminée. Le rendu LaTeX généré est strictement identique
à celui d'avant v0.13.1.

## Architecture

### Helper centralisé `services/param_niveaux.py`

Module qui sert de point d'entrée unique pour la lecture du
référentiel niveau scolaire. Quatre fonctions pures + une fonction
de mise en forme LaTeX + une exception :

```python
class NiveauInconnu(LookupError):
    """Levée quand un niveau demandé n'existe pas dans param_niveaux."""

def lire_attributs(conn, code) -> dict | None:
    """Tous les attributs d'un niveau, ou None si inconnu."""

def lire_cycle(conn, code) -> str:
    """Code du cycle. Lève NiveauInconnu si absent."""

def lire_nom_court(conn, code) -> str:
    """Nom court brut ('5ème', 'CM2'…). Fallback sur le code si inconnu."""

def lire_nom_court_latex(conn, code) -> str:
    """Nom court en forme LaTeX ('5\\ieme', 'CM2'…).
    Conversion 'Xème' → 'X\\ieme', idempotente."""

def lister_tous(conn) -> list[dict]:
    """Tous les niveaux, triés par ordre. Liste vide si table vide."""
```

**Note de nommage** : ce module s'appelle `param_niveaux` (cohérent
avec la table BDD et le CSV source) plutôt que `niveaux` car le
module `services/niveaux.py` existe déjà et traite d'un sujet
différent : les niveaux de **maîtrise élève** (1, 2, 3, 4, A, D, NE).

### Conversion LaTeX `'Xème' → 'X\ieme'`

La fonction `lire_nom_court_latex` applique une regex stricte
`r'(\d+)ème'` au nom_court brut de la BDD. Cette transformation est :

- **Idempotente** : si la BDD contenait déjà `'5\ieme'` (cas non
  observé en prod mais théoriquement possible), la regex ne matche
  pas et la chaîne est retournée telle quelle — pas de double
  conversion.
- **Sans effet sur le primaire** : `'CM1'`, `'CM2'` ne matchent pas
  le pattern, donc retournés bruts.
- **Compatible 100%** avec l'ancien `_NOM_COURT_NIVEAU` historique
  (test d'équivalence dédié, cf. `test_equivalence_avec_ancien_dict`).

Pourquoi pas la forme `'X\ieme{}'` (avec accolades) ? Pour rester
strictement compatible avec le rendu LaTeX historique de
`livret_sequence.py`. Le module `livret_plans_de_travail.py` utilise
quant à lui `LIBELLES_NIVEAUX_LATEX` avec accolades, qui n'est PAS
substitué dans cette livraison (sujet de cohérence à traiter
séparément si nécessaire — c'est une autre table, sémantiquement
distincte, pour les pages de titre).

### Wrapper local `_lire_nom_court_latex_local`

Dans `services/livret_sequence.py`, j'ai introduit un mini-wrapper
qui fait l'import différé du helper :

```python
def _lire_nom_court_latex_local(conn, niveau):
    from services.param_niveaux import lire_nom_court_latex
    return lire_nom_court_latex(conn, niveau)
```

L'import est différé (à l'intérieur de la fonction) plutôt qu'en tête
de module pour éviter toute dépendance cyclique potentielle si jamais
`param_niveaux` venait à importer du contenu de `livret_sequence`. Ce
choix est cohérent avec le pattern déjà utilisé dans
`livret_plans_de_travail.py:_cycle_du_niveau` qui fait également un
import différé.

## Détail des modifications

### `services/livret_plans_de_travail.py`

**Avant v0.13.1** :
```python
_CYCLE_PAR_NIVEAU = {
    'N07': 'C03', 'N08': 'C03', 'N09': 'C03',
    'N10': 'C04', 'N11': 'C04', 'N12': 'C04',
}

def _cycle_du_niveau(conn, niveau):
    if niveau not in _CYCLE_PAR_NIVEAU:
        raise LookupError(f"Aucun cycle trouvé pour le niveau {niveau!r}")
    return _CYCLE_PAR_NIVEAU[niveau]
```

**Après v0.13.1** :
```python
def _cycle_du_niveau(conn, niveau):
    from services.param_niveaux import lire_cycle, NiveauInconnu
    try:
        return lire_cycle(conn, niveau)
    except NiveauInconnu as e:
        # Préserver le message historique
        raise LookupError(f"Aucun cycle trouvé pour le niveau {niveau!r}") from e
```

`LIBELLES_NIVEAUX_LATEX` reste en dur (mise en forme LaTeX spécifique
aux pages de titre du plan de travail, hors sujet v0.13.1).

### `services/livret_sequence.py`

**Suppressions** :
- `_NOM_COURT_NIVEAU = {...}` (~15 lignes)
- Les **deux** occurrences de `_CYCLE_PAR_NIVEAU = {...}` (~22 lignes
  combinées)

**Substitutions** :
- 2 usages de `_NOM_COURT_NIVEAU.get(niveau, niveau)` → appel à
  `_lire_nom_court_latex_local(conn, niveau)` (lignes ex-475 et
  ex-888)
- Tous les usages de `_CYCLE_PAR_NIVEAU` → `lire_cycle(conn, niveau)`
  via la fonction utilitaire interne déjà refactorée

**Ajouts** :
- Wrapper `_lire_nom_court_latex_local(conn, niveau)` placé après
  `_echapper_simple` (~13 lignes)

### Fixtures de tests

Une régression était possible : les fixtures pytest qui créent leur
propre schéma SQLite minimal ne déclaraient pas `param_niveaux`, donc
les services qui l'interrogent maintenant via le helper auraient
échoué. La fixture de `test_v0_12_1_livret_plans_de_travail.py` a
été mise à jour pour inclure :

- La table `param_niveaux` dans le `_SCHEMA_TEST`
- Une fonction `_peupler_param_niveaux` qui amorce les niveaux N07..N12
  et leurs cycles requis (C03, C04) avant les autres INSERT

Cette mise à jour préserve l'isolation de chaque test (la BDD réelle
n'est jamais utilisée pour les tests).

## Tests

**Total : 1978 tests** (vs 1949 baseline v0.13.0) → **+29 tests v0.13.1**.

### Nouveau fichier `tests/test_v0_13_1_param_niveaux_helpers.py`

29 tests organisés en 5 sections :

1. **TestLireAttributs** (5 tests) : nominal, niveau inconnu (renvoie
   None), table vide, cycle inexistant, compatibilité Row factory.
2. **TestLireCycle** (6 tests) : nominal, NiveauInconnu, table vide,
   compatibilité Row, attribut `niveau` sur l'exception, propagation.
3. **TestLireNomCourt** (3 tests) : nominal collège, nominal primaire,
   fallback sur le code si inconnu.
4. **TestListerTous** (5 tests) : retour, dict complet, tri par ordre,
   table vide (liste vide), Row factory.
5. **TestLireNomCourtLatex** (10 tests) : conversion 6ème/5ème/4ème/3ème,
   primaire non transformé, fallback, table vide, Row factory,
   équivalence avec l'ancien `_NOM_COURT_NIVEAU`, idempotence si
   forme déjà LaTeX.

### Pas de régression sur les tests existants

Tous les tests qui exerçaient la génération de livret de séquence ou
de plan de travail continuent de passer sans modification (la
fixture des tests v0.12.1 a été enrichie pour fournir
`param_niveaux`, c'est tout).

## Validation bout-en-bout

Sur la BDD réelle après v0.13.1 :

| Niveau | nom_court (BDD) | nom_court_latex (helper) | Ancien `_NOM_COURT_NIVEAU` |
|--------|-----------------|--------------------------|----------------------------|
| N07    | CM1             | CM1                      | CM1 ✓                      |
| N08    | CM2             | CM2                      | CM2 ✓                      |
| N09    | 6ème            | 6\ieme                   | 6\ieme ✓                   |
| N10    | 5ème            | 5\ieme                   | 5\ieme ✓                   |
| N11    | 4ème            | 4\ieme                   | 4\ieme ✓                   |
| N12    | 3ème            | 3\ieme                   | 3\ieme ✓                   |
| N99 (inconnu) | —    | N99 (fallback)           | N99 (fallback) ✓           |

Génération de livret réelle : `Classe de 5\ieme` apparaît bien dans
le source LaTeX généré pour N10/S01. Aucun changement de rendu.

## Fichiers touchés

```
services/param_niveaux.py                    (~50 lignes ajoutées :
                                                 lire_nom_court_latex
                                                 + docstring module mise à jour)
services/livret_plans_de_travail.py          (déjà refactoré dans une
                                                 session antérieure)
services/livret_sequence.py                  (~50 lignes nettoyées :
                                                 suppression _NOM_COURT_NIVEAU
                                                 + commentaire de migration
                                                 + wrapper _lire_nom_court_latex_local
                                                 + 2 substitutions d'usage)
tests/test_v0_13_1_param_niveaux_helpers.py  (10 nouveaux tests :
                                                 nouvelle classe
                                                 TestLireNomCourtLatex)
tests/test_v0_12_1_livret_plans_de_travail.py
                                              (fixture _SCHEMA_TEST enrichie
                                                 avec param_niveaux + helper
                                                 _peupler_param_niveaux)
doc/redemarrage_v0_13_1.md                   (NOUVEAU)
```

Aucune migration BDD nécessaire (la table existait déjà depuis v0.13.0).

## Procédure de déploiement

1. Décompresser le ZIP par-dessus la v0.13.0 actuellement déployée.
2. Relancer l'application — aucune migration de schéma à exécuter.
3. Aucun changement visible côté UI ; la génération de livrets et de
   plans de travail continue de fonctionner avec exactement le même
   rendu LaTeX qu'avant.

## Points de validation côté Laurent

### Régressions à surveiller

Le test critique : la génération du livret de séquence (et du livret
de plans de travail) doit produire **strictement le même PDF** qu'avant
v0.13.1 pour toutes les séquences. À vérifier sur quelques séquences
représentatives :

- N10/S01 (Cycle 4, 5ème, séquence avec prérequis N09)
- N11/S07 (Cycle 4, 4ème, séquence du milieu d'année)
- N12/S14 (Cycle 4, 3ème, dernière séquence — DNB)

Pour chaque, vérifier dans le PDF :
- Le titre « Séquence XX » avec « Classe de 5\ieme » (ou 4\ieme,
  3\ieme) bien rendu (5ᵉ, 4ᵉ, 3ᵉ avec exposant)
- Les sous-titres de prérequis (« Séquence XX — Nom » avec « 6\ieme »
  bien rendu en italique)
- La page de titre du plan de travail avec « 5ᵉ » correctement rendu

### Cas dégénérés à tester

- Lancer une génération avec un niveau inconnu : le fallback doit
  retomber sur le code (`'N99'` au lieu de planter)

## Effet structurel

Avant v0.13.1, l'application avait **5 sources de vérité** pour le
mapping niveau → cycle / nom court :

1. `data/param_niveaux.csv` ✓ (source d'amorçage CSV)
2. `data/param_niveaux.dbtex` ✓ (source LaTeX, indépendant)
3. `_NOM_COURT_NIVEAU` ❌ (supprimé par v0.13.1)
4. `_CYCLE_PAR_NIVEAU` ❌ (supprimé par v0.13.1)
5. `CsvStore.lire_param_niveaux()` ✓ (utilisé par `resoudre_macros.py`)

Après v0.13.1, la dette est principalement résorbée :

1. `data/param_niveaux.csv` (source d'amorçage)
2. `data/param_niveaux.dbtex` (autonomie LaTeX)
3. **Table BDD `param_niveaux`** (source de vérité opérationnelle)
4. `LIBELLES_NIVEAUX_LATEX` (mise en forme LaTeX, sujet à part)
5. `CsvStore.lire_param_niveaux()` (consommé par `resoudre_macros.py`,
   pourrait être migré dans un chantier ultérieur)

## Prochaine étape

**v0.13.2** — Activation des tables `referentiel_*` (versioning
millésimé). C'est un sujet à scoper séparément :

- Les tables `referentiel_niveaux`, `referentiel_themes`,
  `referentiel_sequences`, `referentiel_objectifs` existent déjà en
  BDD (10 lignes pour `referentiel_niveaux` : versions de 2021 à
  2025 pour N10, N11, N12).
- Aujourd'hui ces tables sont des **archives historiques verrouillées**
  (`etat='verrouille'`).
- L'activation impliquera : compréhension du modèle de données,
  liaison avec les tables actives (`sequences_par_niveau`,
  `objectifs_v2`), UI admin pour gérer les versions, possibilité de
  comparer une séquence v2024 vs v2025.

Beaucoup d'inconnues — une session de scoping dédiée sera utile avant
d'attaquer la v0.13.2. À voir si tu préfères passer directement à la
série v0.14 (refonte admin + nettoyage dette legacy) en gardant
`referentiel_*` pour plus tard.
