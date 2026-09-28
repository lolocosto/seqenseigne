# Redémarrage v0.13.5.1.3 — Atelier Référentiel : badges colorés

## Périmètre

Suite des retours d'usage : la distinction visuelle entre atomes
`valide` et `en_cours` par couleur du texte (vert vs gris foncé)
n'était pas assez nette. **Tous les atomes de l'arbre sont maintenant
des badges colorés cliquables**, avec un **fond vert pâle** si
l'atome est validé, **fond gris** sinon.

### Avant (v0.13.5.1.2)

- Méthode et fiche : libellé souligné en couleur (vert ou gris foncé).
- Notion : "Notion : <titre>" en couleur, titre souligné.
- Exos F/A/E et R/EA : chip avec bordure simple, couleur du texte
  selon l'état.

→ Différence vert/gris-foncé difficile à percevoir.

### Après (v0.13.5.1.3)

Tous les atomes sont rendus avec un **badge uniforme** :

- Fond vert pâle (`#c8e6c9`), texte vert foncé (`#1b5e20`) si **validé**.
- Fond gris clair (`#eeeeee`), texte gris foncé (`#444`) si **en_cours**.
- Bordure assortie pour le contraste.
- Cliquable (lien `<a target="_blank">`) si l'atome a un id valide.

L'état devient lisible **au premier coup d'œil**. Le hover des
liens (visible avec le curseur main) reste l'indication de cliquabilité.

### Méthode/fiche manquantes : inchangé

Les méthodes et fiches absentes restent affichées en **rouge pâle**
(`#c0392b` à 70% d'opacité), non cliquables. C'est un message
d'alerte, pas un atome.

## Procédure de déploiement

1. Décompresser `seqenseigne-v0.13.5.1.3.zip` à la racine de `appli/`.
   Fichiers livrés (cumulatif depuis v0.13.5.0) :
   - `persistence/schema.sql`
   - `persistence/sqlite_store.py`
   - `services/referentiels.py`
   - `routes/referentiels.py`
   - `templates/index.html`
   - `static/app.js`
   - `static/atelier_referentiel.js`  ← **modifié dans cette livraison**
   - `doc/*.md` (4 fichiers)
   - `tests/test_v0_13_5_1_referentiels.py`
   - `verifier_md5_v0_13_5_1_3.ps1`  ← **nouveau** : script de vérif post-déploiement

2. **Vérifie l'intégrité de la livraison** : ouvre PowerShell à la
   racine de `appli/` et lance :
   ```powershell
   .\verifier_md5_v0_13_5_1_3.ps1
   ```
   Si tous les MD5 matchent, "TOUT EST OK" en vert. Sinon, le script
   liste les fichiers corrompus (à demander en mini-ZIP de récup).

3. Côté navigateur : **Ctrl+F5** pour vider le cache.

## Note sur le script de vérification

Suite à plusieurs incidents de fichiers corrompus à la décompression
côté Windows (`routes/referentiels.py` tronqué, `static/app.css`
écrasé par du markdown), un script PowerShell de vérification est
désormais livré à chaque ZIP. Il contient les MD5 attendus de tous
les fichiers de la livraison ; à exécuter après chaque déploiement
pour confirmer que les fichiers sont arrivés intacts.

## Tests

47 tests pytest verts sur le périmètre v0.13.5.1.x. Suite globale :
2023 verts (hors les 20 cassés Windows de migrer_methodes_objectifs.py,
fix planifié v0.14).
