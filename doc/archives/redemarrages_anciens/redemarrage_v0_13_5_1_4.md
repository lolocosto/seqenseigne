# Redémarrage v0.13.5.1.4 — Atelier Référentiel : objectifs Cours allégés

## Périmètre

Petit ajustement de l'arbre du tableau de bord. Les objectifs "Cours"
d'une partie (conventionnellement codés `01`, `11`, `21` selon le
numéro de partie) sont structurellement à part : ils n'ont pas de
méthode liée, pas de fiche de résumé, pas d'exos rattachés. Avant
v0.13.5.1.4, ils s'affichaient comme les autres avec :

- `Méthode (manquante)` en rouge pâle
- `Fiche de résumé (manquante)` en rouge pâle
- `Série F : (aucun)`
- `Série A : (aucun)`
- `Série E : (aucun)`

Soit cinq lignes de bruit visuel par objectif Cours, alors qu'aucune
de ces sections n'a de sens pour eux.

À partir de v0.13.5.1.4, les objectifs Cours sont affichés en mode
allégé : **uniquement leur titre**, pas de lignes en dessous.

## Implémentation

- Helper `_est_objectif_cours(code, numero_partie)` dupliqué depuis
  `services/livret_plans_de_travail.py` (où la convention métier est
  déjà codée). La duplication évite une dépendance entre services ;
  si la convention évolue un jour, les deux fichiers sont à mettre à
  jour ensemble.
- Champ `est_cours: bool` ajouté au dict de chaque objectif dans la
  réponse de `GET /api/referentiels/<id>/arbre`. Pour les objectifs
  Cours, les sections (`methode`, `fiche`, `notions`, `exos_F/A/E`)
  sont garanties vides côté backend (pas même de requête BDD).
- Côté frontend : `atelRefObjectifHtml(o)` court-circuite quand
  `o.est_cours === true` et n'affiche que la ligne de titre.

## Procédure de déploiement

1. Décompresser `seqenseigne-v0.13.5.1.4.zip` à la racine de `appli/`.

2. Lancer le script de vérification :
   ```powershell
   .\verifier_md5_v0_13_5_1_4.ps1
   ```
   Si "TOUT EST OK" en vert, déploiement validé. Sinon, demander un
   mini-ZIP de récupération.

3. Côté navigateur : Ctrl+F5.

## Fichiers modifiés

| Fichier | Nature |
|---------|--------|
| `services/referentiels.py` | Modifié — helper `_est_objectif_cours` + champ `est_cours` |
| `static/atelier_referentiel.js` | Modifié — court-circuit du rendu pour Cours |
| `tests/test_v0_13_5_1_referentiels.py` | Modifié — 1 test ajouté |
| `doc/redemarrage_v0_13_5_1_4.md` | **Ajouté** — ce fichier |
| `verifier_md5_v0_13_5_1_4.ps1` | **Ajouté** — script de vérif |

## Tests

48 tests pytest verts sur le périmètre v0.13.5.1.x (+1 nouveau pour la
détection des objectifs Cours). Suite globale : 2024 verts (hors les
20 tests cassés Windows de migrer_methodes_objectifs.py, fix v0.14).

## Validation

Sur la BDD de Laurent (N11) : **19 objectifs Cours détectés** sur les
14 séquences. Ils s'affichent maintenant avec leur seul titre, pas de
ligne supplémentaire.
