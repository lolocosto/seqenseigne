# Redémarrage v0.51.12 — Bascule vers deux bases

Séparation effective des deux applis : la base partagée (`data\`, profil
complet) donne naissance à `data_atelier\` (conception) et `data_classe\`
(planification et suivi), d'après la répartition validée table par table
(v0.51.11).

## Décisions (validées)

- Deux dossiers suffixés, **`data_atelier\`** et **`data_classe\`** : aucune
  des deux applis n'est « l'ajout » de l'autre. `data\` reste la base
  partagée du profil complet et **n'est jamais modifié** par la bascule (il
  sert de sauvegarde d'avant la bascule).
- **Structures absentes** : chaque base ne garde que ses tables et celles
  des deux côtés (`services/repartition.py` : 43 tables classe, 33 atelier,
  18 des deux côtés). Les lectures croisées sont gardées (table absente →
  rien à lire).
- **Par le protocole d'échange** : les référentiels publiables partent de
  l'atelier dans un paquet (n° suivant de l'atelier), importé par la classe ;
  la classe renvoie aussitôt son retour d'usage n° 1, importé par l'atelier.
- **Tests des données attendues côté classe** : classes et élèves, cases du
  suivi, titres des notions et méthodes (synthèse Pronote), noms des
  documents proposés et PDF servis — identiques avant et après la bascule
  (seuls les titres LaTeX des séquences deviennent du texte lisible, comme
  dans tout paquet).

## Fonctionnement

- **Rôle d'une base** : `instance_locale.role` ('' = base partagée,
  'atelier', 'classe'). Au démarrage d'une base qui a un rôle, les tables de
  l'autre côté sont retirées si elles sont vides (ou seulement amorcées par
  le schéma) ; une table de l'autre côté non vide est gardée et signalée.
  Les préférences de l'autre côté (titres de zone de fiche côté classe,
  types de mise en route côté atelier) sont retirées.
- **Profil et base** : une base basculée ne s'ouvre qu'avec le profil de son
  rôle (refus au lancement sinon). `lancer.bat atelier` ouvre
  `data_atelier\` et `lancer.bat classe` ouvre `data_classe\` dès qu'ils
  contiennent la base de leur rôle ; sinon `data\` (comme avant).
  `--base-partagee` force `data\`.
- **Bascule** (Système › Administration › « Bascule », profil complet) :
  aperçu sans écriture (lignes par côté, devenir de chaque référentiel,
  avertissements), puis bascule sur confirmation :
  1. copie de `data\` vers `data_atelier\` (base, référentiels, images ;
     sans caches ni fichiers en attente) et des fichiers de premier niveau
     (CSV, YAML des cases du suivi, configuration) vers `data_classe\` ;
     bases copiées par sauvegarde SQLite ;
  2. atelier : rôle, identité gardée (numérotation des paquets continuée),
     correspondants et réceptions remis à zéro, paquet des référentiels
     publiables ;
  3. classe : nouvelle identité, tables de conception vidées, référentiels
     non publiables et non utilisés retirés, référentiels gardés marqués
     « publication », repère de séquence si le paquet n'est pas le n° 1,
     import du paquet, retour d'usage n° 1 ;
  4. atelier : import du retour d'usage (séquences commencées, verrous ;
     le paquet est acquitté) ;
  5. boîtes aux lettres croisées (sortie de chaque appli = entrée de
     l'autre ; à changer à la mise en ligne) ;
  6. tables de l'autre côté vidées puis retirées, VACUUM ; rapport
     `BASCULE.json` dans les deux dossiers.
  En cas d'échec, les deux dossiers créés sont retirés. Un `data_atelier\`
  ou `data_classe\` d'essai (sans rôle) est renommé `…_essai_<date>`, jamais
  supprimé ; une bascule déjà faite est refusée.
- **Référentiel non publiable utilisé** (interne non verrouillé, externe
  annulé, ou erreurs de publication) : gardé côté classe avec sa structure,
  sans documents, et signalé dans l'aperçu ; il se publiera ensuite
  normalement depuis l'atelier.
- Côté classe, « Livrets distribués » d'une progression : les livrets reçus
  par le paquet. Les vues de conception des référentiels (arbre des
  atomes, éligibilité à la validation) sont réservées à l'atelier.

## Code

- `services/repartition.py` (nouveau) : tables par côté, rôle, vidage,
  élagage au démarrage (appelé par `persistence/sqlite_store.py`).
- `services/bascule.py` (nouveau) : aperçu, exécution, dossier par défaut
  d'un profil, contrôle profil/base ; `routes/bascule.py` (nouveau, profil
  complet) ; `static/bascule.js` (nouveau), `templates/index.html`,
  `static/app.js`, `static/app.css`.
- `services/echanges.py` (colonne `role`), `app.py` (contrôle du profil,
  dossier par défaut), `lancer.bat`, `.gitignore`.
- Gardes : `services/referentiel_principal_externe.py` (`est_utilise`,
  `sequence_commencee`, `supprimer_sequence`), `services/synthese_seance.py`,
  `services/progression_doc.py`, `services/admin.py`,
  `services/paquet_expose.py`, `persistence/sqlite_store.py`
  (`lire_annees_disponibles`), `routes/referentiel_documents.py`,
  `services/profils.py`.
- Tests : `tests/test_v0_51_12_bascule.py` (répartition, élagage, aperçu,
  bascule, données attendues côté classe, balayage des routes GET de chaque
  appli avec des identifiants réels, refus, dossiers par défaut, routes).

## Après déploiement

1. Lancer `lancer.bat` (profil complet), Système › Administration ›
   Bascule : lire l'aperçu, basculer.
2. Arrêter, puis lancer `lancer.bat atelier` et `lancer.bat classe` (deux
   fenêtres) : vérifier établissements, classes, plans, progressions, suivi
   côté classe ; référentiels et ateliers côté atelier.
3. Si besoin de revenir en arrière : supprimer `data_atelier\` et
   `data_classe\` (ou les renommer) — `data\` est intact.
