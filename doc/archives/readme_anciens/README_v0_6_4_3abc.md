# Livraison v0.6.4 — Sous-livraisons 3a + 3b + 3c

**Migration de la propriété `fin_cycle` et des notions associées vers les objectifs**, et **suppression de l'onglet « Objectif / critères »** dans l'atelier méthode.

## Pourquoi

Dans le programme officiel du cycle 4, **« fin de cycle »** est une caractéristique d'**objectif** (compétence attendue à la fin du cycle), pas de méthode. La modélisation initiale plaçait à tort `fin_cycle` sur la table `methodes` et les notions associées sur `methode_notions`. Cette livraison corrige cette erreur et rend les trois ateliers (exercice, notion, méthode) strictement identiques en termes de propriétés métier — toute caractéristique pédagogique (fin_cycle, notions, critères F/A/E) est désormais portée par l'objectif et éditée dans la « Séquence (niveau) ».

## Changements

### Backend (sous-livraison 3a)

1. **Schéma BDD** (`persistence/schema.sql`)
   - Nouvelle colonne `objectifs_v2.fin_cycle TEXT NOT NULL DEFAULT 'N'`
   - Nouvelle table `objectif_notions(objectif_id, notion_id, ordre)` avec FK CASCADE

2. **Script de migration** (`scripts/peuplement_15_fin_cycle_vers_objectifs.py`)
   - Idempotent (peut être relancé sans effet)
   - Propage `objectifs.methode_id` (legacy) → `objectifs_v2.methode_id`
   - Crée la colonne `fin_cycle` si absente
   - Copie `methodes.fin_cycle` → `objectifs_v2.fin_cycle` via la jointure `methode_id`
   - Crée la table `objectif_notions` si absente
   - Migre `methode_notions` → `objectif_notions` (option `--no-copier-notions` pour désactiver)

3. **Service `services/v2_edition.py`** : 4 nouvelles fonctions
   - `modifier_fin_cycle_objectif(conn, objectif_id, fin_cycle)`
   - `ajouter_notion_objectif(conn, objectif_id, notion_id)`
   - `retirer_notion_objectif(conn, objectif_id, notion_id)`
   - `lister_notions_de_sequence(conn, niveau, sequence)`
   - `_format_retour_objectif` étendu pour inclure `fin_cycle` et `notions`

4. **Routes `routes/v2_edition.py`** : 4 nouveaux endpoints
   - `PATCH /api/v2/objectifs/<id>/fin-cycle`
   - `POST /api/v2/objectifs/<id>/notions`
   - `DELETE /api/v2/objectifs/<id>/notions/<notion_id>`
   - `GET /api/v2/notions-de-sequence?niveau=&sequence=`

5. **Service `services/v2_lecture.py`** : `_charger_objectifs` retourne désormais `fin_cycle` et `notions` (chacune avec id, titre, ordre).

### Frontend seqniv (sous-livraison 3b)

`static/ateliers_seqniv_v2_edit.js` : pour chaque objectif dans le panneau « Séquence (niveau) », deux nouveaux blocs sont insérés après la sélection de méthode :

- **Case à cocher « Attendu de fin de cycle 4 »** avec label dynamique « Oui »/« Non »
- **Notions associées** : tags supprimables + `<select>` d'ajout avec lazy-load du catalogue par séquence

Trois nouveaux handlers JS :
- `seqnivEditChangerFinCycle`
- `seqnivEditAjouterNotion` (gère aussi le `__load__` du catalogue)
- `seqnivEditRetirerNotion`

CSS dans `static/app.css` : nouvelles classes `.seqniv-fin-cycle-toggle`, `.seqniv-notion-tag`, etc.

### Suppression onglet méthode (sous-livraison 3c)

- **HTML** (`templates/index.html`) : suppression du bouton onglet « Objectif / critères » et de tout son contenu (~40 lignes : champ fin_cycle, tags notions, 3 textareas critères F/A/E).
- **JS** (`static/app.js`) :
  - `atelMethodeTab` réduit à 3 onglets : `edition`, `latex`, `rendu`
  - `atelMethodeRemplir` ne lit plus fin_cycle/critères/notions
  - `atelMethodeGenererLatex` ne génère plus les commentaires critères
  - `atelMethodeSauvegarder` : payload sans fin_cycle/critères/notions
  - 4 fonctions supprimées : `atelMethodeNotionAjouter/Retirer/RenderNotionTags/PeuplerNotionSel`
  - Variable `ATL_METHODE_NOTIONS` supprimée
  - Badge « FC » retiré de la liste des méthodes (incohérent avec la nouvelle modélisation)
- **`services/latex_rendu_atome.py`** : champ `fin_cycle` retiré de la dataclass `Atome` (jamais utilisé). La requête SQL et le constructeur sont adaptés en conséquence.
- **`services/atomes.py`** : laissé tel quel — accepte encore `finCycle` et `criteres` en lecture/écriture pour préserver la rétrocompatibilité avec d'anciens fichiers `methodes.json` (tolérance Postel).

## Action requise au déploiement

Sur le poste de Laurent, après mise à jour des fichiers :

```powershell
cd appli
..\outils\python\python.exe scripts\peuplement_15_fin_cycle_vers_objectifs.py
```

Le script est idempotent et rapide (< 1 s). Il :
1. Propage `objectifs.methode_id` → `objectifs_v2.methode_id` (~156 lignes attendues)
2. Crée `objectifs_v2.fin_cycle`
3. Copie les valeurs de `methodes.fin_cycle` vers `objectifs_v2.fin_cycle` via la jointure (toutes à 'N' actuellement)
4. Crée `objectif_notions` (vide initialement)

## Tests

**440 tests verts** :
- 13 tests `test_peuplement_15_fin_cycle.py` (script de migration : création colonne, propagation, idempotence, préservation des saisies utilisateur)
- ~25 tests dans `test_R4e3_edition_objectif.py` (modifier_fin_cycle, ajouter/retirer notion, routes correspondantes)
- 4 tests dans `test_R4e1_v2_lecture.py` (fin_cycle et notions présents dans la lecture)
- DDL des 4 fichiers de tests R4e mis à jour (colonne fin_cycle + table objectif_notions + table notions)

## Compatibilité

- La colonne `methodes.fin_cycle` n'est **pas** supprimée — elle reste en BDD pour rétrocompatibilité avec `methodes.json` legacy. Elle n'est plus utilisée dans la chaîne de rendu LaTeX ni exposée dans l'UI.
- La table `methode_notions` n'est **pas** supprimée non plus — elle peut rester vide. Si elle contient des données au moment de la migration, elles sont copiées vers `objectif_notions` (configurable via `--no-copier-notions`).
- Les anciens fichiers `methodes.json` continuent à se charger sans erreur (`services/atomes.py` accepte encore `finCycle` et `criteres` mais ne les écrit plus).

## Reste à faire (livraisons suivantes)

- 3d : Modale « LaTeX généré » + bouton dans la toolbar (à côté de Enregistrer) — supprimer l'onglet LaTeX
- 3e : Autosize textareas
- 3f : Onglet « Préférences » + mode split (édition + PDF côte-à-côte, désactive les onglets Édition/Rendu)
