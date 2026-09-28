# seqenseigne — Redémarrage v0.8

**Date** : 26 avril 2026
**État** : v0.8 livrée. Compilateur batch des atomes (P1 du redémarrage v0.7) opérationnel.

---

## Ce qui a été fait dans cette version

P1 du redémarrage v0.7 : **compilateur batch des atomes**. Permet de compiler en série tous les atomes (notions, méthodes, exercices) via un sous-onglet Admin > Compilation, avec filtrage par type / niveau / séquence, suivi en temps réel via SSE, et rapport Markdown produit en fin de run.

Bénéfice immédiat : passer une fois la compilation complète détecte tous les atomes problématiques (LaTeX cassé, atome vide, etc.) et tous les autres entrent en cache. Les runs suivants ne re-compilent que ce qui a changé, donc sont quasi-instantanés.

### Choix de scoping retenus

- 3 selects pour le filtrage : Type / Niveau / Séquence, valeur « Tous » par défaut sur chacun. Couvre les 5 combinaisons utiles (type seul, type+niveau, type+niveau+sequence, niveau seul, niveau+sequence).
- 5 statuts par atome : `succes`, `cache`, `echec_vide`, `echec_compilation` (LaTeX a planté), `echec_infra` (pdflatex introuvable, timeout, exception Python).
- Aperçu avant lancement (compte les atomes éligibles) puis confirmation par dialogue *« X atomes seront compilés. Comptez quelques secondes par atome non encore en cache. Continuer ? »*. Pas de chiffre de durée annoncé : trop variable.
- Run via SSE, un événement par atome ajouté en haut de liste, clic sur une ligne ouvre l'atelier dans le même onglet.
- Cache affiché en clair dans la liste (statut « cache » distinct du statut « succès »).
- Pas de bouton « tout retenter » : un nouveau run (avec ou sans filtre) s'en charge.
- Rapport Markdown nommé `Compilation_atomes_<YYYY-MM-DD>_<HH-MM-SS>.md` dans `appli/data/rapports/`.
- Ordre de traitement : niveau (N10 → N12) → séquence (S01 → S14) → type (notion → methode → exercice) → numéro (F avant A pour les exercices).
- Paramètres modifiables in-place (Option A) :
  - **Délai max par atome** : réutilise la clé existante `timeout_compilation_s` (défaut 30 s, partagée avec le rendu individuel pour cohérence).
  - **Erreurs infra consécutives avant abandon** : nouvelle clé `compilation_batch_max_erreurs_consecutives` (défaut 5).
- Définition de « erreur infra » : `pdflatex introuvable`, timeout, ou exception Python. Les `echec_compilation` LaTeX **ne comptent pas** dans le compteur d'abandon.
- « Consécutives » : le compteur reset dès qu'un atome passe avec n'importe quel autre statut (y compris `echec_compilation`).

Une page de paramétrage globale et un menu « aide / historique des versions / FAQ » sont prévus pour des versions futures.

---

## Fichiers touchés

### Nouveaux

- `services/compilation_batch.py` (~480 lignes) — service métier pur, sans dépendance Flask. Exporte `Atome`, `Filtre`, `recenser_atomes()`, `compiler_un_atome()`, `iter_compilation()` (générateur d'événements), `ecrire_rapport_md()`, `evenement_vers_sse()`, `nom_rapport()`. Constantes `STATUT_*` et `LIBELLES_STATUTS`.
- `tests/test_compilation_batch.py` — 35 tests unitaires (mocks de `generer_tex_atome` et `compiler_atome` pour ne pas dépendre de pdflatex).
- `tests/test_route_compilation_batch.py` — 17 tests d'intégration HTTP/SSE.

### Modifiés

- `services/configuration.py` : ajout de la clé `compilation_batch_max_erreurs_consecutives` (défaut 5) et de l'accesseur typé du même nom.
- `routes/admin.py` : ajout de 3 routes :
  - `GET /api/admin/compilation-atomes/preview?type=&niveau=&sequence=` → JSON avec `total`, `par_type`, `config`.
  - `GET /api/admin/compilation-atomes/run?type=&niveau=&sequence=&timeout=&max_erreurs=` → `text/event-stream`. Persiste `timeout` et `max_erreurs` en config si fournis. Écrit le rapport MD à la fin (et même en cas d'annulation par le client, pour ne pas perdre le travail déjà fait — rapport partiel).
  - `GET /api/admin/compilation-atomes/rapport/<nom>` → téléchargement du fichier MD (vérification anti path-traversal : pas de `/`, `\`, `..`, et extension `.md` obligatoire).
  - Helpers internes `_filtre_depuis_query()` (validation des paramètres GET) et `_configuration_admin()`.
- `templates/index.html` : nouveau sous-onglet Admin « Compilation » entre « Images » et « Base de données ». Filtres (3 selects), Paramètres (timeout + max_erreurs), boutons Aperçu/Lancer/Annuler, barre de progression, lien rapport, liste défilante des atomes traités (cap visuel à 2000 lignes).
- `static/app.js` :
  - `adminSousOnglet()` étendu : ajoute `'compilation'` à la liste des sous-onglets et appelle `compilBatchInit()` au switch.
  - Module v0.8 ajouté en fin de fichier : `compilBatchInit()`, `compilBatchPreview()`, `compilBatchRun()` (utilise `EventSource`), `compilBatchAnnuler()`, `compilBatchOuvrirAtelier(type, id)` (clic ligne → bascule sur l'onglet Ateliers + sous-onglet + chargement avec retry 2 s pour attendre que la liste soit fetchée), `_compilAjouterLigne()`, `_compilFinaliser()`.
  - Globales : `COMPIL_EVENTSOURCE`, `COMPIL_PREVIEW_OK`, `COMPIL_RUN_TOTAL`.

---

## Comment tester rapidement

### Fonctionnellement, dans l'app

1. Décompresser `seqenseigne_v08.zip` sur l'appli existante.
2. Lancer le serveur (`python server.py`).
3. Aller sur **Admin > Compilation**.
4. Cliquer sur **Aperçu** sans filtre : la BDD doit annoncer ses ~1124 atomes.
5. Mettre un filtre étroit (par exemple Type = Notions, Niveau = N10, Séquence = S01) puis **Aperçu** : on doit voir un nombre cohérent.
6. **Lancer la compilation** : la liste se remplit en temps réel, la barre de progression avance, chaque ligne est cliquable pour ouvrir l'atelier de l'atome.
7. À la fin, un lien « Télécharger le rapport » apparaît. Le fichier `Compilation_atomes_*.md` est dans `appli/data/rapports/`.
8. Relancer le même run : tout doit être en cache (statut « cache » sur chaque ligne, durée totale très faible).

### Tests automatisés

```
cd appli
python -m pytest tests/test_compilation_batch.py tests/test_route_compilation_batch.py -v
```

→ 52 tests, doivent tous passer en < 15 s.

Le reste de la suite (1264 tests pré-existants + 4 skipped) reste vert : aucune régression introduite.

---

## Architecture en bref

### Pourquoi un service pur séparé de la route

`services/compilation_batch.py` n'importe pas Flask. C'est testable directement avec un `SqliteStore` et des mocks, sans monter le serveur. La route HTTP/SSE dans `routes/admin.py` est juste une fine couche qui :

- valide les paramètres GET (type/niveau/séquence)
- persiste les overrides timeout/max_erreurs en config
- consomme le générateur `iter_compilation()` et le formatte en frames SSE
- écrit le rapport MD à la fin

### Pourquoi GET pour le SSE

`EventSource` côté navigateur est GET-only. Les paramètres passent donc en query string. Les overrides timeout/max_erreurs y sont aussi, et sont persistés en config si fournis (pour le run suivant).

### Pourquoi le cache est transparent

`services/compilateur_pdf.compiler_atome()` hashe déjà le `.tex` rendu (SHA256, 16 caractères) et stocke `<hash>.pdf` dans `data/cache_rendus/`. Si le hash existe déjà, retour direct avec `depuis_cache=True`. Le batch s'appuie là-dessus sans rien ajouter : toute modif d'atome change automatiquement le hash.

### Distinction echec_compilation / echec_infra

Dans `compiler_un_atome()`, après un échec de `compiler_atome()`, on regarde le message d'erreur du premier `ErreurLatex` :

- contient « pdflatex introuvable » ou « timeout » → `echec_infra`
- toute autre erreur LaTeX (Undefined control sequence, etc.) → `echec_compilation`

Les exceptions Python attrapées dans le service sont systématiquement reclassées en `echec_infra` (ce sont des erreurs d'environnement ou de bug, pas des erreurs LaTeX).

---

## Roadmap restante (P2 → P5 du redémarrage v0.7)

- **P2** — Compilateur batch des livrets et fiches résumé. Même pattern que P1 mais sur les documents composés (livrets de séquence, fiches résumé).
- **P3** — Atelier fiche résumé (édition de la fiche A4 recto-verso par séquence).
- **P4** — Référentiels (édition des C04_themes, C04_sequences via l'UI plutôt que par CSV).
- **P5** — Progressions (vue annuelle planifiée par classe, déjà partiellement en place dans l'onglet Progression).

À voir aussi pour une future version :

- Page de paramétrage globale (centralise tous les réglages actuellement dispersés).
- Menu « Aide / Historique des versions / FAQ ».
- Option de compilation en mode dyslexie (xeLaTeX + OpenDyslexic + A3, déjà cadrée dans les notes du paquet LaTeX `seqenseigne`).
