# Nettoyage à faire dans la base de code

> v0.15.4 — refonte. Petit fichier de TODO de nettoyage de code, distinct de la dette technique (qui pèse plus lourd et touche au design).

## Code mort à supprimer

### ~~`appli/static/atelier_atome_generique.js`~~ — déjà supprimé

Legacy avant factorisation `AtelierEditeur` (v0.13.6.16). Vérifié absent du
dépôt en v0.15.5. Item clos.

### ~~Scripts one-shot v1~~ — supprimés v0.15.5

`scripts/supprimer_v1.py` et `scripts/peuplement_02_repeupler.py` supprimés en
v0.15.5 (office terminé : BDD de production déjà migrée v1→v2). Tests associés
retirés/corrigés en conséquence.

### Aliases rétrocompat v0.15.3 (à retirer en v0.16+)

| Emplacement | Alias | Cible |
|---|---|---|
| `services/referentiels.py` | `figer_minimal` | `verrouiller_minimal` |
| `services/referentiel_figeage.py` | `figer_complet` | `verrouiller_complet` |
| `routes/referentiels.py` | route `/api/referentiels/<id>/figer` | `/verrouiller` |
| `static/atelier_referentiel.js` | `atelRefFiger` | `atelRefVerrouiller` |

Conserver tant qu'on n'a pas confirmé qu'aucun appelant externe (script utilisateur, intégration tierce) ne les référence.

## Imports inutiles potentiels

À vérifier au fil des sessions. Pas de chasse systématique en cours.

## Fichiers vides ou orphelins

### ~~`tests/test_v0_15_2_11_ui_fiche_objectif.py`~~ — déjà supprimé

Reverté en v0.15.2.12, recréé en placeholder vide v0.15.3.1, supprimé depuis.
Vérifié absent du dépôt en v0.15.5. Item clos.

## CSS inutilisé

### Classes `.elem-incl-*` supprimées en v0.15.4

OK : déjà retirées en v0.15.4 avec la suppression du bloc « Éléments à inclure ».

## Données

### Workdirs orphelins `tempfile.gettempdir()/seqenseigne_workdir/<hash>`

Si Python plante avant nettoyage, des workdirs traînent. À nettoyer périodiquement à la main. Future amélioration : nettoyer au démarrage les workdirs de plus de X jours.
