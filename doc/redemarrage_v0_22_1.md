# Redémarrage v0.22.1 — Changement de référentiel + correction des parties

Résout les deux problèmes signalés sur la construction des progressions
2026-2027 : impossibilité de changer le référentiel support, et parties 2
invisibles.

## Problème 2 (données) — parties 2 invisibles

Dans les référentiels figés, tous les objectifs avaient `partie_numero = 1`, y
compris ceux de la 2nde partie (identifiée par le préfixe de code : 0x→partie 1,
1x→partie 2…). L'atelier n'affichait donc qu'une partie par séquence.

**Correctif de données** : `outils/corriger_partie_numero_referentiels.py`
recale `partie_numero` d'après le préfixe du code et régénère
`referentiel_parties`. Idempotent, dry-run par défaut.

```
python -m outils.corriger_partie_numero_referentiels           # aperçu
python -m outils.corriger_partie_numero_referentiels --apply   # applique
```

Vérifié sur copie de la base : N11_v2025 → 20 objectifs recalés, S01 expose
partie 1 (codes 01-04) et partie 2 (codes 11-13).

## Problème 1 (fonctionnalité) — changer le référentiel support

Fonctionnalité qui manquait (notée « v0.19.1.1 » dans le code, jamais faite) :
sur une progression existante, changer le sélecteur de référentiel ne faisait
rien.

**Nouveau** : `POST /api/progression_id/<id>/referentiel`
`{ referentiel_id }` change le référentiel d'une progression **en cours** et
**purge ses créneaux** (option (a) validée). Validations : progression en cours,
référentiel existant, figé (verrouille/utilise), même niveau.

Côté UI (atelier Progression), `onReferentielChange` détecte le changement de
référentiel sur une progression existante et demande une **confirmation
explicite** avant de basculer (« Attention : … va effacer TOUS les créneaux
existants … Confirmez-vous ? »). Si l'utilisateur annule, le sélecteur revient
au référentiel actuel.

## Fichiers

- `outils/corriger_partie_numero_referentiels.py` (nouveau) : correction des
  données.
- `routes/progression.py` : route `…/referentiel` (changement + purge).
- `static/atelier_progression.js` : `onReferentielChange` (confirmation +
  bascule).

## Tests

- vitest : 193 passed (0 régression). Syntaxe OK.
- Backend vérifié sur copie de la base réelle : changement N11_v2024→N11_v2025
  (200, créneaux 9→0) ; référentiel inexistant (404) ; mauvais niveau (400).
- Flux complet vérifié : après correction des parties + changement de
  référentiel, la progression 2026-2027 sur N11_v2025 expose S01-P1 et S01-P2
  (19 parties au total).

## Ordre de déploiement recommandé

1. Décompresser ; `python -m outils.verifier_md5`.
2. **Corriger les données** (sur copie d'abord) :
   `python -m outils.corriger_partie_numero_referentiels --apply`
   → les parties 2 deviennent visibles dans l'atelier.
3. Pour la progression 2026-2027 : dans l'atelier Progression, choisir
   « N11_v2025 » dans le sélecteur Référentiel → confirmer le changement (les 9
   créneaux non datés sont purgés) → reposer les parties (dont les parties 2)
   sur le nouveau référentiel.

## Note

Le figeage n'a pas rempli `partie_numero` pour ces référentiels importés. Si tu
réimportes/refiges un référentiel à l'avenir, vérifier que le modèle actif porte
bien les 2 parties, ou relancer le script de correction. Un durcissement du
figeage pourra être envisagé plus tard.
