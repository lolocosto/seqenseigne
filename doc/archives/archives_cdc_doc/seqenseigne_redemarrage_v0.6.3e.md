# seqenseigne — Document de redémarrage

**Version 0.6.3e — avril 2026 · Laurent Coste**

---

## 1. Contexte du projet

| Élément                  | Valeur                                                              |
|--------------------------|---------------------------------------------------------------------|
| Auteur                   | Laurent Coste, enseignant collège cycle 4                           |
| Niveaux                  | N09 = 6ème, N10 = 5ème, N11 = 4ème, N12 = 3ème — 14 séquences chacun |
| Dépôt                    | forge.apps.education.fr/laurentcoste/seqenseigne                    |
| Répertoire dev Windows   | `D:\Enseignement\seqenseigne\` (`appli\`, `reference\`, `outils\`)  |
| Base de données          | `appli\data\seqenseigne.db` (SQLite, créée automatiquement)         |
| Lancement                | `lancer.bat` (Python + Flask portable, port 5000)                   |
| Version livrée           | v0.6.3e — **992 tests pytest verts**                                |

---

## 2. Historique récent

### 2.1 v0.6.1 → v0.6.2d — UUID opaques, référentiels d'époque

- Migration vers des UUID opaques partout (`cl_`, `el_`, `pg_`, `ref_`, `et_`) au lieu de clés métier concaténées.
- Contraintes UNIQUE renforcées en base.
- Référentiels versionnés : une classe consulte son référentiel d'époque même quand le courant a évolué.
- Script `reparer_progression_id.py` pour nettoyer les classes orphelines de `progression_id`.

### 2.2 v0.6.3a — Infrastructure établissements + calendrier scolaire

- Nouvelle table `etablissements` avec UUID `et_xxx`, état `propose`/`valide`, champs nom/uai/academie/ville/adresse.
- Refacto `classes.etablissement_id` et `progressions.etablissement_id` (FK ON DELETE RESTRICT).
- Nouvelle colonne `progressions.etat` : `en_cours`/`valide`/`verrouille`.
- Table `cache_api` pour mettre en cache les appels externes.
- `services/calendrier_scolaire.py` : mapping `ACADEMIE_ZONE` (25 académies), `vacances()`, `jours_feries()`, `jours_feries_annee_scolaire()` avec tolérance aux pannes d'API.
- `services/etablissements.py` : CRUD + `valider_par_uai()` qui interroge fr-en-annuaire-education.
- 9 nouveaux endpoints `/api/etablissements/*` et `/api/calendrier/*`.

### 2.3 v0.6.3b — UI établissements + validation UAI + fusion

- Refonte « Gestion des classes » en 2 sous-onglets : Classes et Établissements.
- Bandeau d'invitation en haut tant qu'au moins un établissement n'a pas d'académie.
- 3 boutons par carte : Valider avec UAI / Modifier / Fusionner avec…
- Badges à 3 états : ✓ Validé (vert) / Académie saisie (bleu) / À compléter (orange).
- Exceptions structurées `DoublonEtablissement` et `ConflitFusion`.
- Fusion atomique classes + progressions, avec garde-fous.

### 2.4 v0.6.3c — Calendrier visuel + états de progression + 3 patches

- Refonte du panneau gauche de Progression annuelle : sidebar 380px, badge d'état, bandeau alerte, calendrier semainier.
- Grille septembre → août avec séparateurs de mois, vacances en fond rouge, jours fériés en badges orange.
- Créneaux bleus posés aux semaines correspondantes, cliquables.
- Trois états : ✏️ En cours / ✓ Validée / 🔒 Verrouillée. Transitions manuelles et automatiques (→ verrouille dès qu'une évaluation est saisie).
- Patches 1/2/3 : vacances d'été + pont Ascension en dur, filtres API corrects, timezone frontend/backend, semaines de classe lun-ven.

### 2.5 v0.6.3d — Nettoyage en 6 points + correctifs (avril 2026)

Journée de nettoyage complète sur les ateliers, la résolution de macros et les imports.

**Points 1-3** (non détaillés dans ce doc — dette technique initiale).

**Point 4 — Convention de nommage UI + suppression JSON archive**
- Convention `<section>-<sousSection>[-<élément>][-<modifier>]` adoptée pour les ids DOM/CSS.
- Section Admin renommée : `stab-*` → `admin-*`, ids internes préfixés `admin-importsuivi-hist-*`/`admin-importsuivi-sdb-*`.
- Label « Import historique » → « Import suivi ».
- Méthodes `suivi_historique_*.json` de `SqliteStore` supprimées.

**Point 5 — Résolution des macros nommantes à l'import**
- 17 macros `\seq*Get*` identifiées dans `seqenseigne-data.dtx`.
- Résolution via `services/resoudre_macros.py` à l'import, hors champs de saisie LaTeX.
- Fallback `[à saisir]` + rapport UI groupé par fichier.

**Révision 5b — param_niveaux.csv + C03**
- Support complet C03/C04 dans le résolveur.
- Convention `AnneeDansCycle = anneeun/anneedeux/anneetrois`.

**Révision 6 — CSV connaissances/objectifs + peuplement v2 intégré**
- 4 CSV ajoutés dans `data/` : `C03_connaissances.csv`, `C04_connaissances.csv` (226 entrées), `C03_objectifs.csv`, `C04_objectifs.csv` (418 entrées).
- La résolution se fait **uniquement** depuis les CSV, la fonction `enrichir_contexte_depuis_scan` est supprimée.
- Appel à `peupler_v2_depuis_base` enchaîné automatiquement dans `scanner_vers_bdd` — plus besoin du script CLI séparé.
- `FinCycle="N"` et critères vides ne sont plus signalés comme incidents à tort.

**Hotfix `reset_reference` (bug FK IntegrityError)**
- Le `DELETE FROM exercices` tombait sur la FK RESTRICT de `objectif_exos`.
- Correctif : 7 tables manquantes ajoutées au reset dans le bon ordre FK.
- Conserve les référentiels stables (cycles, themes, referentiel_*) et le suivi.

### 2.6 v0.6.3e — Correctifs d'imports + UI (23 avril 2026)

**Correctif `correctifs_imports_ui`**

Bug #1 — *Import partiel, 6-7 passes nécessaires* :
- Cause : `lire_notions` ne renvoyait pas le champ `fichier`. La déduplication par `fichier` dans `scanner_vers_bdd` échouait systématiquement → chaque réimport comptait toutes les notions comme « nouvelles ».
- Correctif : `lire_notions` renvoie `niveau`, `sequence`, `num_connaissance`, `fichier` en plus des champs existants.

Bug #2 — *Atelier Séquence : parties vides, pas de liaison aux méthodes* :
- Cause : `reset_reference` vidait `objectifs` (legacy) mais pas `referentiel_objectifs` (stable). `scanner_vers_bdd` n'avait pas de pont : `objectifs` restait vide après un reset + scan.
- Correctif : `scanner_vers_bdd` appelle désormais `json_store.ecrire_objectifs()` entre la persistance des notions et celle des méthodes. Cette méthode rehydrate `objectifs` depuis `referentiel_objectifs`. Non-bloquant en cas d'erreur.

3 évolutions UI :
- Panneaux latéraux des ateliers Exercice, Notion, Méthode → affichent **identification** (`N11/S01/F01`, `N11/S01/C01`, `N11/S01/O02`) + **titre**. Fallback sur l'énoncé supprimé.
- Listes thèmes et séquences de cycle → classe `.atl-item` unifiée (au lieu de `.atl-list-item` sans CSS associé) → hover ombré cohérent.
- Nouvelles classes CSS : `.atl-item-id` (monospace, largeur fixe), `.atl-item-titre` (ellipsis), `.atl-item-fc` (badge fin de cycle).

**Correctif `fix_fk_exercices`**

Après le déploiement précédent, crash SQLite au 2e scan :
```
sqlite3.IntegrityError: FOREIGN KEY constraint failed
  File ".../sqlite_store.py", line 1088, in ecrire_exercices
    conn.execute("DELETE FROM exercices")
```

Diagnostic croisé :
- Le peuplement v2 automatique (depuis `nettoyage_6`) peuple `objectif_exos` à la fin de chaque scan. La FK `objectif_exos.exercice_id → exercices.id` est en **RESTRICT**.
- L'UI lançait les 3 scans en **parallèle** via `Promise.all(niveaux.map(...))` — écritures concurrentes et explosions FK.

Correctifs :
- `static/app.js` : sérialisation des scans (`for (const niv of niveaux) { await ... }`) — plus de Promise.all.
- `persistence/sqlite_store.py` : `ecrire_exercices` refondu en **diff-based**. Plus de `DELETE FROM exercices` brutal ; on calcule la différence entre la base et la liste cible, et seuls les exos qui disparaissent sont supprimés (avec leurs liaisons au préalable). Les liaisons `objectif_exos` des exos inchangés sont préservées.

---

## 3. État de la base actuelle (chez Laurent)

### 3.1 Schéma

Tables principales :

- `etablissements` (et_xxx) : UNIQUE(nom), état `propose`/`valide`
- `classes` (cl_xxx) : nom, niveau, annee, etablissement_id, progression_id nullable
- `eleves` (el_xxx) + `eleves_classes` (table d'association)
- `progressions` (pg_xxx) : niveau, annee, etablissement_id, etat `en_cours`/`valide`/`verrouille`, referentiel_id
- `creneaux` (cr_xxx) : progression_id, sequence, rang_debut, rang_fin, periode, date_debut, date_fin, ordre, partie, livret_version_id
- `referentiel_niveaux` (ref_xxx) : niveau, version, etat `en_cours`/`valide`/`verrouille`
- `referentiel_sequences`, `referentiel_objectifs` : données de référence pour la réhydratation des objectifs
- `notions`, `methodes`, `exercices` : atomes pédagogiques (avec métadonnées niveau/sequence/fichier)
- `objectifs` : table legacy, réhydratée depuis `referentiel_objectifs` à chaque scan
- `sequences_par_niveau`, `sequence_parties`, `objectifs_v2`, `objectif_exos`, `partie_precedences` : tables v2 pour l'atelier Séquence
- `suivi`, `niveaux` (dénormalisés avec classe_id + seq_code directs)
- `versions`, `versions_classes` (snapshots de livrets)
- `cache_api` (cle, payload, fetched_at) : `vacances:B:2025-2026:Rennes`, `feries:2026`, `annuaire:0351234A`

### 3.2 Données de référence

- **N10** : entièrement migré, références stables.
- **N11** : migration terminée, utilisé en classe.
- **N12** : migration terminée.
- **N09** : données 6ème non encore migrées.

### 3.3 CSV de référence dans `data/`

| Fichier                        | Entrées | Contenu                                                   |
|--------------------------------|---------|-----------------------------------------------------------|
| `param_niveaux.csv`            | 6       | Mapping niveau → (cycle, nom court, nom long, année)     |
| `C03_sequences.csv`            | 16      | Séquences du cycle 3 (pour N09)                          |
| `C04_sequences.csv`            | 14      | Séquences du cycle 4 (pour N10/N11/N12)                  |
| `C03_themes.csv`               | 3       | Thèmes cycle 3                                            |
| `C04_themes.csv`               | 5       | Thèmes cycle 4                                            |
| `C03_connaissances.csv`        | 98      | Noms des connaissances (résolution `\seqConnaissanceGetNom{01}`) |
| `C04_connaissances.csv`        | 128     | Idem cycle 4                                              |
| `C03_objectifs.csv`            | 208     | Noms + fin_cycle + critères TB/S/F des objectifs         |
| `C04_objectifs.csv`            | 211     | Idem cycle 4                                              |

Totaux : 226 connaissances + 418 objectifs chargés par `construire_contexte_global()`.

### 3.4 Utilitaires

| Script                          | Usage                                                                                       |
|---------------------------------|---------------------------------------------------------------------------------------------|
| `clean_cache.py`                | Vide le cache API des vacances (à lancer après chaque modif de `services/calendrier_scolaire.py`) |
| `importer_arborescence.py`      | Re-crée la base à partir de l'arborescence des sources LaTeX                              |
| `reparer_progression_id.py`     | Répare les classes dont `progression_id` pointe vers une progression absente               |
| `scripts/peuplement_13_v2_depuis_base.py` | Repeuple les tables v2 manuellement (devenu inutile en flux normal, utile en dépannage) |
| `lancer.bat`                    | Démarre Flask (port 5000) avec Python + MiKTeX portables                                   |

---

## 4. Commandes de démarrage

```bat
cd D:\Enseignement\seqenseigne
appli\lancer.bat
```

Tests :
```bat
cd appli && ..\outils\python\python.exe -m pytest tests\ -q
```

Vider le cache des vacances après modif du service calendrier :
```bat
cd appli && python clean_cache.py
```

### 4.1 Variables d'environnement

| Variable      | Défaut | Effet                                        |
|---------------|--------|----------------------------------------------|
| `USE_SQLITE`  | 1      | 1 = SqliteStore (prod), 0 = JsonStore (legacy) |
| `FLASK_DEBUG` | —      | Mettre à 1 pour le mode debug                |

### 4.2 Après modification du schéma SQL

Supprimer la base et relancer :

```bat
del data\seqenseigne.db
del data\seqenseigne.db-shm
del data\seqenseigne.db-wal
python importer_arborescence.py --racine D:\Enseignement_old
lancer.bat
```

### 4.3 Cycle type d'import de la référence

Flux nominal après modification des sources `.tex` :

1. Admin → Base de données → **Vider la référence** (préserve le suivi et les référentiels stables)
2. Admin → Import référence → Scanner + Importer
3. Les 3 niveaux sont scannés **séquentiellement** (N10 → N11 → N12) avec peuplement v2 automatique en fin de chaque scan.
4. Le rapport affiche les atomes importés et les éventuels incidents de macros non résolues.

Une **seule** passe suffit pour que tout soit en base. Relancer un import est idempotent.

---

## 5. Points en suspens

### 5.1 Court terme (v0.6.3f, petite livraison)

- 🔲 Détail créneau enrichi : afficher la liste d'objectifs associés dans le panneau de détail.
- 🔲 Suppression de la vue synthétique (tableau redondant avec le calendrier visuel).

### 5.2 Moyen terme

- 🔲 Verrouillage granulaire par créneau + par séquence (nécessite colonne etat sur creneaux — changement de schéma, à faire dans une version dédiée).
- 🔲 Déverrouillage explicite des progressions avec suppression en cascade des évaluations.
- 🔲 Périodes d'évaluation S1/S2, vue bulletin par période, export CSV pour bulletin.
- 🔲 Migration des données N09 (6ème).
- 🔲 Écran de gestion des référentiels : duplication, déverrouillage manuel.

### 5.3 Long terme — Génération LaTeX

- 🔲 Atelier Exercice : persistance vers `.tex`/`.csv` (actuellement lecture seule depuis les imports).
- 🔲 Atelier Livret : assemblage des atomes, génération `N1X_S01_Livret.tex`.
- 🔲 Atelier Progression : plan de travail annuel `N1X_Plan_de_travail.tex` à partir du calendrier v0.6.3c.
- 🔲 Génération PDF depuis l'appli (3 passes pdflatex).
- 🔲 Peupler `creneau_objectifs_exos` depuis l'UI.
- 🔲 Script migration `\usepackage[geometrie]` dans les 17 livrets concernés.
- 🔲 Option compilation dyslexie.
- 🔲 Test et mesure des formats précompilés `.fmt`.

### 5.4 Contenu pédagogique

- 🔲 Intégrer les 16 corrigés N11 dans les fichiers `.tex` exercices.
- 🔲 Vérifier N12 : exercices sans corrigé.
- 🔲 Les noms d'objectifs N11/N12 référencés par `\seqObjectifGetNom{02}` sont maintenant résolus automatiquement depuis les CSV — vérifier qu'il ne reste pas de `[à saisir]` dans les imports.

### 5.5 Dette technique

- 🔲 Refonte diff-based de `ecrire_notions` et `ecrire_methodes` (même motif que `ecrire_exercices`, pas urgent car pas de FK RESTRICT).
- 🔲 Renommage des identifiants `stab-*` de Suivi de classe vers `suivi-*` (cohérence avec la convention adoptée dans Admin).
- 🔲 Suppression de `.atl-item-meta` dans `app.css` (devenue inutilisée après refonte des sidebars).
- 🔲 Ajouter l'année 2027-2028 dans `VACANCES_ETE_DEBUT` et `PONT_ASCENSION` quand les dates sortent au JO en octobre 2026.

---

## 6. Points d'attention

> **⚑** L'API `fr-en-calendrier-scolaire` renvoie les dates avec un offset UTC (+00:00) mais elles représentent minuit heure française. Une date `2026-05-13T22:00:00+00:00` signifie 14 mai 00h Paris. La fonction `_iso_date()` applique +2h pour corriger. **Ne JAMAIS la contourner.**

> **⚑** Côté frontend, utiliser `_dateToISO(d)` au lieu de `d.toISOString().slice(0,10)` pour tout formatage de Date en `AAAA-MM-JJ`. `toISOString()` convertit en UTC, ce qui décale d'un jour en UTC+2.

> **⚑** Le calendrier teste les vacances sur la semaine de classe lundi-vendredi. Si ce comportement change, il faut réviser `_vacancesDeLaSemaine()` ET `_creneauxDeLaSemaine()` pour rester cohérents.

> **⚑** L'API `fr-en-calendrier-scolaire` renvoie les vacances d'été et le pont de l'Ascension de façon incomplète. On les complète TOUJOURS depuis les tables embarquées `VACANCES_ETE_DEBUT` et `PONT_ASCENSION`. Dédoublonnage par `_normalise_desc(description)` + `start_date`.

> **⚑** Le filtre `population:Élèves` NE doit PAS être ajouté au `refine=` lors des appels à data.education.gouv.fr. Il cache Toussaint/Noël/Hiver/Printemps (qui ont `population="-"`).

> **⚑** Cache API : toujours vider `cache_api` après une modification de `services/calendrier_scolaire.py`, sinon les anciennes données buguées sont servies. Utiliser `clean_cache.py`.

> **⚑** **FK `objectif_exos` → `exercices` en RESTRICT**. Toute méthode qui voudrait supprimer des exercices doit d'abord nettoyer les liaisons dans `objectif_exos`. `ecrire_exercices` (v0.6.3e) est diff-based pour gérer ça proprement. Si on ajoute une autre méthode qui touche `exercices`, appliquer le même motif.

> **⚑** **Scans séquentiels, pas parallèles.** `adminImporter()` côté JS utilise une boucle `for ... of` avec `await`, pas `Promise.all`. Les scans parallèles provoquaient des `IntegrityError` sur `exercices` / `objectif_exos`. Si on ajoute d'autres scans multi-niveaux, conserver ce patron.

> **⚑** **Déduplication par `fichier`**. Tous les `lire_*` des atomes (notions, méthodes, exercices) doivent renvoyer le champ `fichier`. Sinon la dédup dans `scanner_vers_bdd` échoue et on réinsère les atomes en doublon à chaque import.

> **⚑** **Résolution des macros nommantes** : seuls les titres de notions et méthodes sont résolus. Les champs libres (corps, exemples, remarques, énoncés, corrigés) restent intacts. C'est une règle métier forte.

> **⚑** **`ecrire_objectifs()` dans `scanner_vers_bdd`**. Cette étape est indispensable après un `reset_reference` : elle rehydrate `objectifs` depuis `referentiel_objectifs`. Sans elle, l'atelier Séquence affiche des parties vides. Non-bloquante en cas d'erreur (logs dans `resume["erreurs"]`).

> **⚑** Tiret dans les CSV historiques : « - » → code 0 (aucune donnée), PAS A (absent). Vérifier après migration.

> **⚑** Structure HTML : respecter l'équilibrage des div. Toute régression visuelle inexplicable → vérifier la pile d'ouverture/fermeture via un HTMLParser.

> **⚑** `creneau_objectifs_exos` : table créée dans le schéma mais non encore peuplée par l'UI. Nécessaire pour la génération LaTeX des plans de travail (roadmap v0.7+).

> **⚑** Verrouillage automatique : dès qu'une évaluation est saisie via `/api/niveaux/set` ou `/api/suivi/exo`, la progression de la classe passe à `verrouille` via `_verrouiller_referentiel_de_classe`. Fallback par clé métier si `classe.progression_id` est NULL.

> **⚑** **992 tests verts.** Contrainte : 0 régression à chaque livraison. Chaque patch s'accompagne d'un test nouveau ou d'une adaptation explicite.

---

## 7. Prompt de redémarrage pour nouvelle conversation

Pour reprendre le travail dans une nouvelle conversation, uploader les 3 documents markdown :

- `seqenseigne_doc_v0.6.3e.md` — documentation technique
- `seqenseigne_redemarrage_v0.6.3e.md` — ce document
- `seqenseigne_usecases_v0.6.3e.md` — cas d'usage

Et demander :

> « Je reprends seqenseigne v0.6.3e. Les documents techniques et cas d'usage sont en pièces jointes. Lis-les et propose-moi les prochaines étapes à partir de la roadmap (v0.6.3f en priorité). »

Le modèle connaît alors :

- L'architecture complète (UUID opaques, SQLite, services, routes, ateliers).
- L'historique des chantiers et leurs pièges résolus.
- Les points d'attention à ne pas oublier.
- La feuille de route ordonnée par urgence.
- Les conventions de code et les invariants (FK RESTRICT, scans séquentiels, déduplication par `fichier`, résolution via CSV…).

Le travail peut reprendre directement avec cohérence.
