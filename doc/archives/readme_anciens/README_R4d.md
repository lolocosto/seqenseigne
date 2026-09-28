# seqenseigne — R4d : Renommage UI « Livret » → « Séquence (niveau) »

Quatrième sous-chantier de R4. Rebaptise l'atelier « Livret » en
« Séquence (niveau) » pour bien le distinguer de l'atelier « Séquence
(cycle) » de R3.

**Status** : renommage cosmétique UI, **715 tests verts** (inchangé), 0 régression.

## Périmètre

**Inclus** — 4 libellés visibles à l'utilisateur dans `templates/index.html` :

| Ligne | Avant | Après |
|---|---|---|
| Bouton sous-nav ateliers | `Livret` | `Séquence (niveau)` |
| Note atelier Notion | `...attribué dans l'atelier Livret.` | `...attribué dans l'atelier Séquence (niveau).` |
| Commentaire HTML | `<!-- ── Atelier Livret ── -->` | `<!-- ── Atelier Séquence (niveau) ── -->` |
| Titre du panneau | `Atelier Livret` | `Atelier Séquence (niveau)` |

**Hors scope** (comme décidé) :
- URLs d'API (`/api/livrets/...`) inchangées — renommage plus invasif pour plus tard
- Noms de tables SQL (`livrets_de_sequence`, `livret_exercices`, `livret_revisions`) inchangés
- IDs HTML (`atl-livret`, `atl-btn-livret`, `liv-atl-titre`) inchangés — pas visibles par l'utilisateur
- Fichier `static/ateliers_livret.js` inchangé (nom de fichier)
- Fonction JS `atelSwitch('livret')` inchangée (identifiant interne)
- Commentaires et docstrings Python — nettoyés en R4f
- Écran Admin/Scanner mentionnant les fichiers `.tex` `livrets_de_sequence/` — à conserver car ces fichiers sur disque gardent leur nom
- Zone « Versions de livrets » dans Suivi — concept distinct (snapshots YAML)

## Fichiers livrés

Un seul fichier modifié : `appli/templates/index.html`.

## Déploiement

### 1. Remplacer le fichier

Extraire le ZIP dans `appli/`. Un seul fichier est remplacé :
`templates/index.html`.

### 2. Recharger le navigateur

Flask sert le template à chaque requête — donc pas besoin de le redémarrer.
Fais un **Ctrl+F5** dans le navigateur pour que la nouvelle version soit
affichée.

### 3. Vérifier visuellement

Aller dans **Ateliers** → voir que le bouton de la sous-nav s'appelle
maintenant « Séquence (niveau) ». Cliquer dessus : le titre du panneau
affiche « Atelier Séquence (niveau) » tant qu'aucune séquence n'est
sélectionnée, puis `N11 S01 — Nom` une fois sélectionnée (comportement
inchangé).

## Prochaine étape : R4e

Le gros morceau UI : refondre l'atelier « Séquence (niveau) » pour qu'il
édite le **nouveau modèle v2** (parties, objectifs v2, objectif_exos),
au lieu du modèle legacy (livrets_de_sequence, livret_exercices).

Ce sera un chantier conséquent — on en discutera la découpe.
