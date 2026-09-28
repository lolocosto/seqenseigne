# seqenseigne — Patch v0.8.1

**Date** : 26 avril 2026
**Type** : correctif sur v0.8

---

## Bugs corrigés

### 1. Le run de compilation se relance en boucle après la fin

**Symptôme observé** : après un run terminé proprement (avec rapport généré), `EventSource` côté navigateur relançait automatiquement la compilation toutes les quelques secondes, créant un cycle infini.

**Cause** : `EventSource` se reconnecte automatiquement quand le serveur ferme un stream — c'est sa résilience native aux coupures réseau. La v0.8 reposait sur un faux postulat ("il ferme tout seul à la fin du stream") qui n'a rien à voir avec ce qui se passe réellement.

**Correction** :
- À réception de `fin`/`abandon`/`annule` côté client → `setTimeout(close, 500)` pour laisser passer l'événement `rapport` qui suit, puis fermeture explicite de l'EventSource.
- À réception de `rapport` (qui est toujours le dernier) → fermeture immédiate.
- Le handler `onerror` ferme aussi proactivement pour empêcher la reconnexion automatique en cas de coupure.

### 2. Clic sur une ligne de la liste : sous-onglet "Suivi" parasite

**Symptôme observé** : clic sur un atome dans la liste → bascule vers Ateliers OK, mais réinitialisation parasite du sous-onglet "Suivi des séquences" (visible dans la console : `[sousOnglet] appelé avec nom="suivi"` à chaque clic).

**Cause** : `compilBatchOuvrirAtelier()` faisait `btnTab.click()` pour basculer vers l'onglet Ateliers. Le handler `.tab` attaché aux boutons d'onglet contient une logique défensive `if (btn.dataset.tab !== 'classe') sousOnglet('suivi')` qui réinitialise un sous-onglet sans rapport.

**Correction** : remplacer le `btnTab.click()` par une bascule manuelle (retirer `.active` partout, masquer tous les `.tab-content`, afficher `tab-ateliers`, appeler `initAteliers()`). On ne déclenche que ce qu'on veut, sans effet de bord.

### 3. Délai d'attente pour la liste Ateliers porté à 5 s

Sur la BDD réelle (~1124 atomes), les 3 fetch parallèles de `initAteliers()` peuvent prendre ~1 s. Le délai de 2 s du retry était trop court → certains atomes étaient marqués "introuvables dans ATL_NOTIONS" (visible dans tes logs avec `no_e8df677d` et `no_4994fef3`).

Délai porté à 5 s, ça laisse une marge confortable.

---

## Fichiers modifiés

- `static/app.js` : corrections 1, 2, 3 dans le module `compilBatch*` (en fin de fichier).

---

## Tests

53 tests verts (35 unitaires + 18 d'intégration HTTP/SSE), incluant un nouveau test
`test_run_rapport_est_le_dernier_evenement` qui vérifie l'invariant côté serveur sur
lequel s'appuie la correction n°1 : `rapport` est bien le dernier événement émis.

```
python -m pytest tests/test_compilation_batch.py tests/test_route_compilation_batch.py
```
