# Redémarrage v0.17.2 — Nettoyage : LaTeX côté serveur uniquement

Finalisation de la décision d'architecture actée en v0.17.1 :

> Le LaTeX est produit côté serveur uniquement ; le client le récupère pour
> l'afficher (séparation des rôles). Pas deux endroits de production.

v0.17.1 avait posé le `voirLatex` unifié dans la base (récupère le `.tex`
serveur + modale commune). v0.17.2 **retire la génération LaTeX CLIENT**
devenue redondante et unifie tous les affichages sur la modale commune.

## Ce qui est retiré (génération client)

Pour exercice, notion, méthode, fiche :
- les surcharges `voirLatex()` (qui généraient un fragment côté client) ;
- les méthodes `genererLatex()` (construction du LaTeX dans le DOM) ;
- les méthodes `copierLatex()` ;
- les wrappers globaux `window.atelXxxGenererLatex` / `atelXxxCopierLatex`.

Conséquence : ces 4 ateliers héritent désormais du `voirLatex()` de la base
(v0.17.1) → le bouton « LaTeX généré » récupère le `.tex` réellement compilé
par le serveur et l'affiche dans la modale commune (qui fournit déjà un bouton
« Copier »). Le wrapper `window.atelXxxVoirLatex` est conservé (délègue au
`voirLatex` hérité).

Dans `app.js` : suppression du bloc legacy `atelExerciceVoirLatex/
GenererLatex/CopierLatex` (anciennes fonctions globales qui manipulaient
`#atl-exercice-latex-out`). Le wrapper de `atelier_exercice.js`, chargé après
`app.js`, prend le relais.

## HTML — panneaux LaTeX intégrés retirés

`templates/index.html` : suppression des panneaux `#atl-exercice-latex`,
`#atl-notion-latex` (et leur `<pre id="…-latex-out">` + bouton « Copier »).
Le panneau méthode est vidé (conteneur conservé vide, inoffensif). Ces
panneaux n'étaient affichés par aucun onglet : ils servaient seulement de
tampon à l'ancienne génération client.

## Séquence (seqniv) — affichage unifié sur la modale

`atelier_seqniv_assemblage.js` : `_livretSeqAfficherTex` affiche désormais le
`.tex` (déjà récupéré du serveur) dans la modale commune
(`atelierAfficherLatex('livret_sequence', …)`) au lieu d'une zone intégrée.
Nouveau libellé `livret_sequence` → « Livret de séquence » ajouté à la table
des libellés de `atelier_commun.js`. (La zone `#livret-seq-tex-out` du template
seqniv reste en place mais n'est plus utilisée — masquée, inoffensive.)

## Bilan : un seul chemin d'affichage du LaTeX

Tous les ateliers (exercice, notion, méthode, fiche, carte, évaluation,
séquence) :
1. récupèrent le `.tex` du SERVEUR (route `/rendu-tex` ou équivalent livret) ;
2. l'affichent dans la **modale commune** `atelierAfficherLatex` (titre selon
   le type, bouton « Copier » intégré).

Plus aucune génération LaTeX côté client. Le serveur (latex_rendu_atome.py et
les services de livret) est la source de vérité unique.

## Tests

- **Vitest** : 77 passed (inchangé — aucun test ne dépendait de la génération
  client ; le voirLatex unifié est couvert par `voirlatex_unifie.test.js` de
  v0.17.1).
- **pytest** : 3793 passed, 7 skipped, 0 failed. Aucun test ne dépendait des
  panneaux `latex-out` ni des fonctions client supprimées.
- **Syntaxe** : node --check OK sur les 7 fichiers JS modifiés.

## À vérifier côté Windows (validation visuelle)

1. exercice / notion / méthode / fiche → « LaTeX généré » : ouvre la modale
   commune avec le LaTeX **complet** produit par le serveur (titre correct,
   bouton « Copier »). Plus de panneau LaTeX intégré dans l'onglet.
2. Le LaTeX affiché correspond bien à l'état SAUVEGARDÉ (le bouton sauvegarde
   d'abord si des modifications sont en attente — comportement de la base).
3. Séquence → « Voir le .tex » : ouvre la modale commune « Livret de séquence ».
4. Carte / évaluation : inchangés depuis v0.17.1 (déjà sur la modale commune).
5. Vérifier que rien n'appelle plus une fonction inexistante (console sans
   erreur « atelXxxGenererLatex is not defined »).

## Suite — v0.17 / roadmap

Le chantier 2 de v0.17 (aperçu PDF au survol des atomes dans les ateliers
d'assemblage) reste à faire : cadrage dans
`cadrage_unification_ateliers_assemblage.md` §2bis/§5bis ; décisions A1 (tout
atome compilable), A2 (modale unique large flottante), A3 (hybride avec bouton
« Générer l'aperçu »), délai 1500 ms. Infrastructure backend déjà en place
(`/api/atomes/<type>/<id>/rendu-pdf/info` + `/rendu-pdf` + viewer pdf.js).
