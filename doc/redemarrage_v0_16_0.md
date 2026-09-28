# Redémarrage v0.16.0 — Affichage PDF en iframe forcé (viewer pdf.js embarqué)

## Objectif

Forcer le rendu inline des PDF dans l'iframe d'aperçu des ateliers, quel que
soit le navigateur et ses réglages. Sur poste verrouillé d'établissement, le
navigateur peut ouvrir les PDF dans une nouvelle fenêtre ou les télécharger au
lieu de les afficher dans l'iframe (symptôme historique côté Firefox PC pro).

## Solution retenue

Viewer **pdf.js embarqué** (Mozilla, build legacy v4.10.38), servi en local par
Flask depuis `static/vendor/pdfjs/`. pdf.js dessine le PDF dans un `<canvas>` :
le navigateur ne voit jamais un content-type `application/pdf` à « gérer »,
donc le rendu inline est garanti par construction.

**100 % hors-ligne** : aucune dépendance CDN. Tout (viewer, worker, cmaps,
polices standard) est servi depuis le dépôt. Vérifié : aucune ressource externe
bloquante référencée dans viewer.html / viewer.mjs.

**Choix de version** : build *legacy* pour compatibilité maximale ; usage réel
sur Chrome/Edge (moteur Chromium récent) où pdf.js v4 tourne sans souci.

## Périmètre (décidé en cadrage)

**Ateliers d'atomes uniquement** : notion, méthode, exercice, fiche de résumé,
carte d'automatisme. Tous héritent du rendu PDF d'`AtelierEditeur`, donc une
seule méthode modifiée les couvre tous.

**Hors périmètre (volontaire)** : les ateliers d'assemblage (séquence,
évaluation) et les PDF au niveau référentiel continuent d'utiliser l'affichage
natif. Ils seront recâblés sur le viewer quand leur machinerie sera revue, pour
éviter une factorisation prématurée. (Repères : `atelier_evaluation_oo.js`,
`atelier_seqniv_assemblage.js`, et la compilation référentiel.)

## Détail technique

### 1. Vendor pdf.js (`static/vendor/pdfjs/`)

Distribution officielle `pdfjs-4.10.38-legacy-dist`, **élaguée** (21 Mo → 6.6 Mo) :
- Conservé : `build/pdf.mjs`, `build/pdf.worker.mjs`, `web/viewer.{html,mjs,css}`,
  `web/images/`, `web/cmaps/`, `web/standard_fonts/`, `web/locale/{fr,en-US}/`.
- Supprimé : sourcemaps `.map` (~9.6 Mo), PDF de démo, `debugger.*`,
  `pdf.sandbox.*`, 110 locales inutiles (`locale.json` réduit à fr + en-US).

Le viewer attend le worker en `../build/pdf.worker.mjs` (relatif à `web/`) et les
cmaps/polices en `../web/cmaps/` et `../web/standard_fonts/` — l'arborescence
respecte ces chemins par défaut, aucune reconfiguration nécessaire.

### 2. MIME `.mjs` forcé (`app.py`)

**Piège Windows critique** : les navigateurs n'exécutent un module ES que si le
serveur le renvoie avec un MIME JavaScript. Sur Windows (runtime de prod sur clé
USB), la base de registre peut associer `.mjs` à un type incorrect/absent, ce
qui casserait le chargement du viewer. On force donc, au niveau module dans
`app.py`, avant toute création d'app :

```python
import mimetypes
mimetypes.add_type("text/javascript", ".mjs")
```

### 3. Branchement (`static/atelier_editeur.js`)

Nouvelle méthode `_afficherPdfDansViewer(iframe, blobUrl)` :
- Charge `iframe.src = /static/vendor/pdfjs/web/viewer.html?file=<blobUrl>`.
- Le blob est créé par la page (même origine que le viewer servi par Flask),
  donc accepté par la validation d'origine de pdf.js (`validateFileURL`).
- Le blob URL est mémorisé sur `iframe._seqBlobUrl` pour révocation propre
  (puisque `iframe.src` pointe désormais vers le viewer, plus vers le blob).

Le flux backend est **inchangé** : `POST …/rendu-pdf` → blob (cache SHA-256
conservé). Seul l'affichage du blob côté client passe par le viewer.

L'ancienne affectation directe `iframe.src = url` est remplacée. La logique de
révocation du blob précédent (`_remettrePlaceholderRendu`) est adaptée pour
révoquer via `iframe._seqBlobUrl`.

## Tests

**v0.16.0 : 3704 passed, 7 skipped, 0 failed.** (+16 vs v0.15.5.)

Nouveau fichier `tests/test_v0_16_viewer_pdfjs.py` (16 tests) :
- Présence des fichiers runtime essentiels (build + web).
- Worker résolu au bon chemin relatif.
- `locale.json` réduit à fr/en-US.
- MIME `.mjs` forcé à `text/javascript` (via import de `app`).
- Flask sert viewer.html (200) et les `.mjs` avec un Content-Type JavaScript.
- Aucune ressource externe bloquante dans viewer.html.
- `atelier_editeur.js` route bien par `_afficherPdfDansViewer` et n'a plus
  l'affectation directe `iframe.src = url`.

## Validation en production (à faire chez toi)

1. Lancer l'app, ouvrir un atelier d'atome (ex. une notion), onglet Rendu PDF,
   compiler. Le PDF doit s'afficher **dans l'iframe** avec la barre d'outils
   pdf.js (zoom, pagination), sans ouverture de nouvelle fenêtre ni
   téléchargement.
2. Vérifier sur le navigateur réellement utilisé (Chrome/Edge). NB : Chromium
   affiche souvent déjà bien les PDF en iframe ; le bénéfice du viewer est
   surtout la garantie d'un comportement identique quel que soit le réglage.
3. Tester les 5 ateliers d'atomes (notion, méthode, exercice, fiche, carte).
4. Confirmer le fonctionnement **hors-ligne** (débrancher le réseau : le viewer
   doit fonctionner intégralement).

## Notes pour la suite

- Quand on reverra la machinerie des ateliers d'assemblage (séquence,
  évaluation) et la compilation référentiel : factoriser
  `_afficherPdfDansViewer` (probablement dans `atelier_commun.js`) et brancher
  ces rendus sur le viewer embarqué.
- Le `compressed.tracemonkey-pldi-09.pdf` (PDF de démo) a été retiré : si tu
  ouvres `viewer.html` sans `?file=`, il n'y aura pas de PDF par défaut — c'est
  voulu (on passe toujours un blob).

## Roadmap (rappel)

- **CRUD cycle/niveaux/thèmes/séquences** (gros chantier, prochaine grosse
  version) — prérequis internationalisation + import C03 complet.
- **Cartes d'automatisme 4ème/3ème** : pilote 1 séquence (format xint validé +
  compilé) avant industrialisation sur 14 séquences × 2 niveaux. La structure
  existe (`cartes_automatisme`, `objectif_cartes`, atelier dédié), peuplée pour
  la 5ème (123 cartes, modèle de référence).
- Recâblage des assemblages + référentiel sur le viewer pdf.js.
