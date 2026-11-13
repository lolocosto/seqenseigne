# Redémarrage v0.56.2 — atelier Carte mentale (poignée, toutes séquences) ; invalidation manuelle du rendu PDF

> Base de comparaison : 03894ca « v0.56.1 » (déployée). Aucune migration, aucune table,
> aucun `.dtx` modifié (pas de `tex seqenseigne.ins`), aucun import de lot.

## Besoin (Laurent, 13 novembre 2026, 16 h 11)

1. « Ajouter un ascenseur horizontal pour redimensionner la liste à gauche (comme dans
   les autres ateliers). »
2. « Permettre de ne choisir aucune séquence (comme dans les autres ateliers) et à ce
   moment les cartes de toutes les séquences sont présentées dans la liste. »
3. « Invalider le rendu PDF manuellement, par exemple quand une macro de mise en forme a
   changé, même si le contenu de l'atome est identique. »

## 1. Poignée de redimensionnement (décision CM-POIGNEE)

Même mécanisme que Thème, Découpage en séquences et Évaluation : entrée
`{ shell: '#atl-carte_mentale .atl-shell', cle: 'split:atl-cm:aside' }` dans
`initAtelierSplitters` (`static/app.js`) → `atelierInstallerSplitter`
(`static/atelier_commun.js`) : séparateur glissant, bornes 200 / 300 px, largeur
mémorisée en `localStorage` sous `split:atl-cm:aside`. Pas de séparateur édition / rendu
(l'atelier n'a pas de mode côte à côte, comme Évaluation).

## 2. Aucune séquence choisie (décision CM-TOUTES)

Le sélecteur de séquence de la portée Séquence propose déjà « — Toutes les séquences — »
(valeur vide). La v0.56.1 affichait alors « Choisir une séquence précise » : décision
renversée.

- API : `GET /api/v2/livret-sequence/<niveau>/cartes-mentales` →
  `{niveau, sequences: [{sequence, modifiable, parties}]}` ; séquences principales du
  niveau (`livret_sequence_6e.sequences_du_niveau` : ni archives Xnn ni mises en route
  Mnn, qui n'ont pas de carte), parties au format de la liste d'une séquence
  (`cartes_mentales.parties_du_niveau`). Catégorie « atelier » (blueprint).
- Liste : toutes les parties, groupées par séquence (regroupement d'`AtelierEditeur`,
  comme les autres ateliers), préfixe `N09/S03/P2` ; filtres d'état et « Sans carte »
  inchangés.
- Identifiant d'élément en mode « toutes » : `S03:2` (le numéro seul n'est plus unique).
  L'élément renvoyé par le serveur (GET, PATCH, POST) reçoit cet identifiant (accesseur
  `itemActif` de l'atelier) pour rester reconnu par la liste. En mode séquence,
  l'identifiant reste le numéro (contrat v0.56.1 inchangé).
- URL : `AtelierEditeur` construit désormais l'URL d'un élément à un seul endroit,
  `urlItem(id)` (GET, PATCH, DELETE) et `urlRenduItem(id)` (rendu-pdf/info, rendu-pdf,
  rendu-tex) — même résultat qu'avant pour tous les ateliers. L'atelier Carte mentale
  les surcharge : séquence tirée de l'identifiant. Ouvrir une entrée = édition, rendu,
  compilation comme avant ; « Toutes les cartes de la séquence » porte sur la séquence de
  l'entrée ouverte.
- « + Créer » : partie ouverte si elle n'a pas de carte, sinon première partie sans carte
  de la séquence de l'entrée ouverte (hook `sequenceDeCreation` d'`AtelierEditeur`) ;
  séquence validée : refus (droit porté par chaque entrée).

## 3. Cache des rendus PDF (décisions CACHE-AUDIT, CACHE-SANS, CACHE-VIDER, CACHE-EMPREINTE)

**Audit.**

- Emplacement : `data/cache_rendus/` (plat) : `<clé>.pdf` et `<clé>.log` ; sous-dossiers
  `echecs/` (rendu par lot) et `echecs_mer/` (Tout compiler) : logs d'échec, pas des PDF
  en cache.
- Clé (avant) : `compilateur_pdf.hash_tex` = sha256 du `.tex` complet, 16 caractères.
  **Aucune empreinte du paquet** : un PDF restait servi après la modification d'une macro
  du paquet si le `.tex` de l'atome était identique — c'est le cas signalé.
- Utilisateurs : `compiler_atome(cache_dir=…)` depuis `routes/rendu_atome.py` (notion,
  méthode, exercice, fiche, carte d'automatisme), `routes/evaluations.py`,
  `routes/livret_sequence.py` (livret et documents de séquence, cartes mentales, deux
  « Tout compiler » : séquence et mise en route), `routes/plans_de_travail.py`,
  `routes/admin.py` (rendu par lot) ; les routes `…/rendu-pdf/info` calculent la même clé.
  `orchestrateur_compilation` n'utilise pas de cache.
- Le cache ne garde pas le niveau d'un PDF : le vidage « par niveau » n'est pas simple ;
  le vidage porte sur tout le cache.

**Recompiler sans cache.** `compiler_atome(…, ignorer_cache=True)` : le PDF (et son log)
en cache est supprimé avant la compilation — un PDF périmé ne revient jamais, même si la
recompilation échoue — puis remplacé par le nouveau. Paramètre de requête commun
`?sans_cache=1` (`services/cache_rendus.sans_cache_demande`), lu par toutes les routes de
compilation ci-dessus sauf le rendu par lot. Interface :

- onglet Rendu PDF de chaque atelier hérité d'`AtelierEditeur` (Exercice, Notion,
  Méthode, Fiche de résumé, Carte d'automatisme, Évaluation, Carte mentale) : bouton
  « Recompiler sans cache » créé par `_assurerToolbarRendu` (brique commune, aucune copie
  par atelier) → `recompilerSansCache()` → `compilerRendu()` avec `?sans_cache=1` (helper
  `Atelier.urlSansCache`) ;
- atelier Séquence (onglet Rendu PDF, code propre) : case « Sans cache » appliquée à
  « Compiler le livret / le document », « Compiler le plan de travail », « Compiler les
  cartes mentales » et « 📦 Tout compiler » (option « sans cache » demandée).

**Vider le cache.** Système › Administration › Base de données › « Cache des rendus
PDF » : « État » (nombre de PDF et de logs, taille, empreinte du paquet) et « Vider le
cache des rendus PDF » (confirmation, puis nombre de fichiers supprimés). Routes
`GET /api/admin/cache-rendus`, `POST /api/admin/cache-rendus/vider` (catégorie
« atelier » dans `services/profils.py`). Les dossiers d'échecs sont gardés.

**Empreinte du paquet dans la clé.** Simple et sûr : `hash_tex` ajoute au `.tex` une
empreinte (sha256 du contenu) des `.sty` et `.dtx` de `appli/paquet` et de
`<racine>/reference/paquet` (dossier du TEXINPUTS). Recalcul seulement quand la
signature (nom, taille, date) d'un fichier change. Toutes les routes passent par
`hash_tex`, la clé est donc la même partout (info et compilation). Sans aucun de ces
dossiers, clé inchangée (sha256 du `.tex` seul). Conséquence au déploiement : **toutes
les clés changent une fois**, les anciens PDF en cache ne sont plus servis (à vider avec
le nouveau bouton) ; ensuite, toute modification du paquet invalide le cache seule.
Limite : un paquet installé ailleurs (MiKTeX) et modifié sans toucher à ces deux dossiers
n'est pas suivi — « Recompiler sans cache » ou « Vider » y répondent.

## Tests

- `tests/test_v0_56_2_cache_rendus_et_cartes_toutes.py` (15) : clé qui change avec un
  `.sty` ou un `.dtx` (pas avec un autre fichier), clé d'avant sans paquet, dossiers de
  l'empreinte, PDF ignoré et remplacé, PDF périmé retiré même si la recompilation échoue,
  paramètre `sans_cache`, vidage (compte, dossiers d'échecs gardés), routes
  d'administration et leur catégorie, transmission de `?sans_cache=1` au compilateur,
  chaque route qui compile lit le paramètre, liste du niveau (sans Mnn ni Xnn, droit par
  séquence), catégorie de la route.
- `tests_js/v0_56_2_carte_mentale_toutes_et_cache.test.js` (14) : poignée (même
  mécanisme, largeur mémorisée), logique pure du mode « toutes », liste groupée et
  préfixée, filtres, ouverture / enregistrement / rendu sur l'URL de la séquence de
  l'entrée, création, séquence validée, bouton commun (absent des ateliers), URL avec
  `sans_cache=1`, case de l'atelier Séquence, bloc d'administration.
- `tests_js/cartes_mentales_atelier.test.js` : le test « sans séquence précise » suit la
  nouvelle décision.

## Contrôles

- pytest : 4886 réussis, 8 ignorés, 0 échec (v0.56.1 : 4871).
- vitest : 361 réussis (39 fichiers).
- Même `.tex` : 1590 sorties comparées (code v0.56.1 / v0.56.2, même base) : 0 différence.

## Appli

- Nouveaux : `services/cache_rendus.py`,
  `tests/test_v0_56_2_cache_rendus_et_cartes_toutes.py`,
  `tests_js/v0_56_2_carte_mentale_toutes_et_cache.test.js`, `doc/redemarrage_v0_56_2.md`.
- Modifiés : `services/compilateur_pdf.py`, `services/cartes_mentales.py`,
  `services/profils.py`, `routes/admin.py`, `routes/livret_sequence.py`,
  `routes/rendu_atome.py`, `routes/evaluations.py`, `routes/plans_de_travail.py`,
  `static/atelier.js`, `static/atelier_editeur.js`, `static/atelier_carte_mentale.js`,
  `static/atelier_seqniv_assemblage.js`, `static/app.js`, `templates/index.html`,
  `tests_js/cartes_mentales_atelier.test.js`, `doc/ETAT_COURANT.md`.
- Aucun fichier supprimé.

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`).
2. Depuis `appli\` : `..\outils\python\python.exe .\outils\verifier_md5.py` (facultatif).
3. Lancer l'appli ; Système › Administration › Base de données › « Vider le cache des
   rendus PDF » (les anciens PDF ne sont plus servis de toute façon : place libérée).

## Risques

- Première compilation de chaque document plus lente après le déploiement (clés
  changées) ; « Tout compiler » d'une séquence recompile tout la première fois.
- Le rendu par lot n'a pas d'option « sans cache » (il bénéficie de l'empreinte du
  paquet et du vidage).
- Paquet modifié hors de `appli\paquet` et `reference\paquet` : pas d'invalidation
  automatique.
