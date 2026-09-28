# Chantier 14 — Rendu LaTeX d'un atome isolé

## Session 3 — Compilation PDF + route Flask + configuration

### Objectif de la session

Compléter la chaîne : `.tex` généré (session 2) → PDF compilé, via une
route Flask avec cache, timeout, gestion d'erreurs structurée.

### Ce qui est livré

#### Service `services/compilateur_pdf.py`

Service de compilation via `subprocess pdflatex`. API principale :

```python
compiler_atome(tex_source, racine_sources, cache_dir, pdflatex,
               racine_appli, timeout) -> ResultatCompilation
```

La structure `ResultatCompilation` retournée contient :
- `ok` : True si PDF produit
- `pdf_bytes`, `pdf_path` : le PDF (si succès)
- `erreurs` : liste de `ErreurLatex(ligne, message, contexte)`
- `log_complet` : log pdflatex complet
- `duree_ms`, `depuis_cache`, `pdflatex_utilise` : métadonnées

#### Service `services/configuration.py`

Mécanisme minimal de configuration utilisateur via `data/configuration.json`.
Clés connues (défauts appliqués automatiquement) :

| Clé | Défaut | Rôle |
|---|---|---|
| `chemin_sources_livrets` | `''` | Racine des .tex sources (pour `_params.tex` et TEXINPUTS) |
| `chemin_pdflatex` | `''` | Override du pdflatex auto-détecté |
| `timeout_compilation_s` | `30` | Timeout pdflatex en secondes |

Écriture atomique (tmpfile + rename), rejet des clés inconnues, robuste au
JSON corrompu. Helpers typés : `chemin_sources_livrets() → Path | None`,
`timeout_compilation() → int`, etc.

#### Blueprint `routes/rendu_atome.py`

Cinq routes :

| Méthode + route | Rôle |
|---|---|
| `GET /api/atomes/<type>/<id>/rendu-tex` | Retourne le .tex qui serait compilé (debug) |
| `POST /api/atomes/<type>/<id>/rendu-pdf` | Compile et retourne le PDF ou 422 JSON |
| `GET /api/atomes/<type>/<id>/rendu-log` | Retourne le log pdflatex si en cache (debug) |
| `GET /api/configuration` | Lecture de la configuration courante |
| `POST /api/configuration` | Mise à jour partielle de la configuration |

Codes de retour :
- 200 : PDF en `application/pdf` (headers `X-Seq-Duree-Ms`, `X-Seq-Depuis-Cache`)
- 400 : type_atome invalide
- 404 : atome introuvable (ou log absent)
- 422 : compilation échouée (erreur LaTeX du code de l'atome)
- 503 : pdflatex introuvable ou timeout

### Décisions architecturales

**Détection de pdflatex** : ordre env var → PATH → MiKTeX portable relatif.
La convention MiKTeX portable testée est
`<racine_appli>/../outils/MiKTeX/miktex/bin/x64/pdflatex.exe` (Windows)
ou `.../bin/pdflatex` (Unix). Ça correspond à ton installation chez toi.

**Cache disque** : dans `data/cache_rendus/`. Un PDF par hash SHA-256 tronqué
à 16 caractères du `.tex` source. Cache invalidé automatiquement dès que
le contenu change (le hash change). Fichiers associés :
- `<hash>.pdf` : le PDF compilé
- `<hash>.log` : le log pdflatex (pour debug)

**Note** : pense à ajouter `data/cache_rendus/` dans ton `.gitignore`.

**Une seule passe pdflatex** : un atome isolé n'a pas de références croisées,
pas de TOC. Pas besoin de 2 ou 3 passes. Si tu observes un jour des
warnings « references may have changed », on repassera.

**TEXINPUTS étendu** : la racine des sources (configurée via
`chemin_sources_livrets`) est ajoutée à `TEXINPUTS` avec `//` pour que
pdflatex trouve tous les fichiers inclus, à toute profondeur.

**Timeout 30 s par défaut** : suffisant pour un atome normal (2-5 s),
laisse une marge confortable, évite de bloquer l'UI sur un atome
pathologique (macro récursive infinie par exemple — testé).

**Pas de nettoyage automatique du cache** : volontaire. Tu verras toi-même
si le cache grossit au point de devoir le vider. Une `rm -rf
data/cache_rendus/` le reconstruira lentement au fil des usages.

### Tests

**53 nouveaux tests, tous verts :**

- `test_compilateur_pdf.py` — 26 tests :
  - hash_tex : stabilité, unicité, UTF-8
  - detecter_pdflatex : env var, PATH, MiKTeX portable, absence complète
  - extraire_erreurs : formats `!` et `fichier:N:`, log vide
  - compiler_atome : erreurs sans pdflatex, vrais cas de compilation si
    disponible (succès, erreur LaTeX, cache hit, cache invalidé,
    timeout, TEXINPUTS)

- `test_configuration.py` — 17 tests : lecture par défaut, JSON corrompu,
  persistance, clés inconnues, helpers typés.

- `test_route_rendu_atome.py` — 10 tests : validation des types, 404
  atome absent, 503 si pdflatex absent, lecture/écriture de la
  configuration, cas d'erreur JSON.

**Total chantier 14 : 162 tests** (109 sessions 1-2 + 53 session 3).

Tests de compilation réelle avec pdflatex : testés dans cet environnement
sur un `.tex` minimal `\documentclass{article} \begin{document} Bonjour.
\end{document}` → PDF produit en ~250 ms, magic `%PDF-1.5` OK, cache hit
en 0 ms au 2e appel.

### Bout en bout

Sur un atome réel de la BDD (`ex_c604c3d2` = N10/S01) :
- `GET /api/atomes/exercice/ex_c604c3d2/rendu-tex` → 200, 5 Ko de .tex
- `POST /api/atomes/exercice/ex_c604c3d2/rendu-pdf` → 422 dans l'env de
  test (seqenseigne.sty absent de TeX Live système), avec erreur
  structurée identifiant la ligne 6 et le message lisible. Chez toi,
  MiKTeX trouvera seqenseigne.sty et la compilation réussira.

### Utilisation côté UI (session 4)

Pour afficher le rendu d'un atome dans l'appli, une fois la session 4
implémentée :

1. Au premier démarrage de l'appli, remplir la configuration :
   ```
   POST /api/configuration
   {"chemin_sources_livrets": "D:\\Enseignement\\seqenseigne\\sequences"}
   ```

2. Depuis un atelier, bouton « Voir le rendu » :
   ```js
   const r = await fetch(`/api/atomes/exercice/${id}/rendu-pdf`, {method: 'POST'});
   if (r.ok) {
     const blob = await r.blob();
     const url = URL.createObjectURL(blob);
     // Afficher dans une iframe ou ouvrir dans un nouvel onglet
   } else {
     const err = await r.json();
     // Afficher err.message + err.erreurs
   }
   ```

### Fichiers créés

```
services/compilateur_pdf.py             (service pur, ~280 lignes)
services/configuration.py               (module simple, ~130 lignes)
routes/rendu_atome.py                   (blueprint Flask, ~190 lignes)
tests/test_compilateur_pdf.py           (26 tests)
tests/test_configuration.py             (17 tests)
tests/test_route_rendu_atome.py         (10 tests)
doc/chantier_14_session_3.md            (ce fichier)
```

### Fichiers modifiés

```
app.py : ajout de l'import et de l'enregistrement du blueprint bp_rendu_atome
```

Rien d'autre modifié.

### État global du chantier 14

| Session | Objectif | Statut |
|---|---|---|
| 1 | Schéma + peuplement + vérification de couverture | ✓ Livrée |
| 2 | Génération du .tex d'un atome isolé | ✓ Livrée |
| 3 | Compilation PDF + cache + route Flask | ✓ Livrée (cette session) |
| 4 | UI bouton « Voir le rendu » | À faire |

Tests globaux du chantier : 162 verts.

### Prochaines étapes chez Laurent

1. Copier les 6 nouveaux fichiers aux emplacements indiqués.
2. Adapter `app.py` (3 lignes) selon le correctif de cette doc.
3. Lancer les tests : `pytest tests/test_compilateur_pdf.py tests/test_configuration.py tests/test_route_rendu_atome.py -v`
4. Si tout est vert, tester à la main :
   ```
   POST http://localhost:5000/api/configuration
   {"chemin_sources_livrets": "D:\\Enseignement\\seqenseigne\\sequences"}
   ```
   puis
   ```
   POST http://localhost:5000/api/atomes/exercice/<un_vrai_id>/rendu-pdf
   ```
   → tu dois recevoir un PDF.

Si ça marche, on enchaîne avec la session 4 (UI). Si un problème
apparaît (chemin MiKTeX mal détecté, erreur de compilation sur un atome
réel, etc.), on corrige avant d'attaquer l'UI.
