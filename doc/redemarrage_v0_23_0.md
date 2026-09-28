# Redémarrage v0.23.0 — Correctifs de l'audit (sécurité, RGPD, RGAA)

Traite les points de l'audit `doc/audit_securite_rgpd_rgaa.md` qui peuvent l'être
sans décision structurante, et prépare (désactivé par défaut) ce qui touche au
déploiement. **Rien ne change pour l'usage local actuel** tant que les variables
d'environnement d'activation ne sont pas définies.

## Sécurité

### #1 `debug=True` désactivé par défaut (🔴)
`app.py` ne lance plus Flask en mode debug en dur (qui exposait un débogueur
permettant l'exécution de code arbitraire). Le debug est piloté par la variable
d'environnement **`SEQ_DEBUG`** (défaut : OFF).
- usage local classique : rien à faire (plus sûr) ;
- pour déboguer ponctuellement : `SEQ_DEBUG=1 python app.py`.

### #5 Exceptions non gérées masquées (🟠)
Gestionnaire d'erreur global : hors debug, une exception **non capturée** renvoie
un message générique (« Erreur interne du serveur. ») au lieu d'une trace, et
logue le détail côté serveur. Les erreurs métier volontaires (4xx explicites)
gardent leurs messages utiles.

### #2 Authentification optionnelle (🔴)
Nouveau `services/auth.py` : protection par **mot de passe unique**,
**désactivée par défaut**. Activation par la variable d'environnement
**`SEQ_MDP`**.
- sans `SEQ_MDP` : aucun changement (usage local mono-poste) ;
- avec `SEQ_MDP="…"` : page `/login`, session, toutes les pages et l'API
  protégées (401 sur `/api/…` sans session), `/logout` disponible. Comparaison
  du mot de passe à temps constant.
- mot de passe jamais stocké dans le projet (vit dans l'environnement) ;
  `SEQ_SECRET` (optionnel) fixe une clé de session dédiée.

Mécanisme volontairement minimal (un mot de passe partagé). Un système de
comptes / SSO académique pourra le remplacer — **à décider** selon le contexte
de déploiement.

## RGPD

### #7 Purge des données élèves anciennes (🟠)
Nouveau `outils/purge_rgpd_eleves.py` : supprime les données d'élèves
(liens classe, suivi, niveaux, et élèves devenus orphelins) des années
scolaires antérieures à un seuil. La **durée de conservation n'est pas imposée**
(à définir avec le DPO) : elle est passée en paramètre. Dry-run par défaut,
préserve les élèves encore présents dans une année conservée.
```
python -m outils.purge_rgpd_eleves --conserver-depuis 2024-2025        # aperçu
python -m outils.purge_rgpd_eleves --garder-annees 3 --apply           # exécute
```
Vérifié en dry-run sur la base réelle (conserver depuis 2024-2025 → 3 années
purgeables, 283 élèves, 0 préservé à tort).

### À mener hors code (avec le DPO) — non traité ici
- #3 Chiffrement au repos : chiffrer le disque (BitLocker/LUKS) — mesure système,
  pas du code.
- #6 Base légale, information des familles, registre des traitements.
- #8 Consigne d'usage pour les exports.

## RGAA

### #9 `aria-label` sur les boutons à icône (🟠)
Les boutons à icône seule (× supprimer, ↑/↓ réordonner) reçoivent un
`aria-label` (nom accessible fiable, le `title` seul ne suffisait pas). 9 boutons
des écrans récents traités.

### #10 Rôles et zones live (🔴/🟠)
- La barre d'onglets principale porte `role="tablist"` / `role="tab"` avec
  `aria-selected` mis à jour au changement d'onglet.
- 17 zones de statut (« ✓ enregistré », erreurs) reçoivent
  `role="status" aria-live="polite"` pour être annoncées par les lecteurs
  d'écran.

### Reste à faire (RGAA, progressif)
- #10 (suite) : `role="dialog"` sur les popovers, balisage des sous-barres
  d'onglets.
- #11 : équivalents clavier du glisser-déposer et des zones cliquables.
- #12 : contrastes et tailles de police minimales.

## Fichiers

- `app.py` : debug par env, handler d'erreur global, branchement auth.
- `services/auth.py` (nouveau) : authentification optionnelle.
- `outils/purge_rgpd_eleves.py` (nouveau) : purge RGPD paramétrable.
- `templates/index.html` : rôles ARIA onglets, aria-live sur les statuts,
  onchange début (sync min fin — déjà en v0.22.2).
- `static/app.js` : aria-selected au changement d'onglet, aria-label boutons.
- `static/edt.js`, `static/indispo.js`, `static/atelier_progression.js` :
  aria-label boutons icône.

## Tests

- pytest ciblé : 198 passed. vitest : 193 passed. 0 régression.
- Auth vérifiée dans les deux modes (sans SEQ_MDP : accès libre ; avec :
  login requis, API 401, connexion OK, mauvais mot de passe refusé).
- Purge RGPD vérifiée en dry-run sur la base réelle.
- App démarre en debug=False par défaut.

## À valider à ton retour

- **Mécanisme d'authentification** : le mot de passe unique convient-il, ou
  faut-il des comptes / SSO ? (Pour l'instant : désactivé, donc sans impact.)
- **Durée de conservation RGPD** : quel seuil, à fixer avec le DPO.
- Les points RGAA restants (#10 suite, #11, #12) et RGPD hors code (#3, #6, #8)
  sont à planifier.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. En local, rien
ne change (debug off = pas de trace détaillée ; utiliser `SEQ_DEBUG=1` pour
déboguer). Pour un déploiement serveur : définir `SEQ_MDP` (auth), envisager
`SEQ_SECRET`, et chiffrer le disque.
