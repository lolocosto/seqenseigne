# Redémarrage v0.61.0 — atelier Encarts (atomes) ; PDF servis à jour dans le référentiel

Delta par rapport à 2e8a763 « v0.60.3 » (déployée et poussée par Laurent). Brief :
`col4/BRIEF_V0610.md`. **Paquet LaTeX inchangé** (`seqenseigne-style6e` v0.16). Base : deux
colonnes ajoutées à `encarts` (migration automatique, outil d'essai à blanc). Format d'échange
inchangé.

## Demandes de Laurent (19 novembre)

1. 16 h 03 : « Créer un atelier pour les encarts (à considérer comme des atomes) selon les
   mêmes règles que les autres ateliers d'atomes, où on choisit le type d'encart, le texte et
   le corrigé le cas échéant. […] positionner l'encart dans le livret […] "après tel élément
   (fiche de cours, activité n° tant, exercice n° tant, etc.)". Ceci permettra d'enlever la
   ligne "encarts du livret" de l'atelier d'assemblage de séquence. »
2. Signalement : avec la v0.60.3 et le paquet copié, le livret N09 A1 compilé depuis l'atelier
   a les filets noirs, celui affiché depuis le référentiel de 6e (« Tester ») non.

## Ce qui change pour Laurent

- **Atelier « Encart »** (portée Séquence, après « Carte mentale ») : liste à gauche avec
  filtres partie, objectif (ou « encarts de partie »), type, état ; niveau et séquence par la
  barre de portée, « toutes les séquences » compris ; poignée ; sélection multiple (Ctrl+clic,
  Maj+clic, clic droit, Échap) et validation groupée ; onglets Édition / Rendu PDF (l'encart
  seul, version élève ou corrigée, cache, « Recompiler sans cache », LaTeX généré) ; mode
  côte-à-côte ; lien direct `?atelier=encart&niveau=N11&seq=A1&atome=<id>`.
- **Formulaire** : type, largeur (pleine / demi), titre, place (partie, objectif, « Après »),
  texte (LaTeX), corrigé (imprimé dans la version corrigée seulement ; attendu pour un défi,
  facultatif sinon), sources (jamais imprimées). La liste « Après » donne les éléments de
  l'objectif **tels qu'ils apparaissent dans le livret, avec leur numéro du livret** :
  « Début de l'objectif », « Activité 2 — … », « Fiche de résumé — … », « Exercice 7 (EN05) —
  … », …, « Fin de l'objectif (par défaut) » ; pour un encart de partie : début de la partie,
  activités et fiches de la partie, fin de la partie (avant la carte mentale), après la carte
  mentale. L'élément est enregistré par **son identifiant**, pas par son numéro : un
  exercice ajouté avant lui change son numéro, l'encart le suit.
- **Cycle de vie** : un encart est « en cours » ou « validé » (validé = lecture seule, comme
  les autres atomes). Valider exige un type et un texte (macros `\seq…` connues du module) ;
  avertissements (non bloquants) : élément d'ancrage absent du livret, défi sans corrigé,
  encart sans source, texte long. La validation d'une **séquence** avertit aussi d'un encart
  dont l'élément d'ancrage a quitté le livret.
- **Élément d'ancrage disparu** (exercice retiré de l'objectif, supprimé…) : l'encart
  s'imprime en fin d'objectif (de partie) ; l'atelier l'affiche « ⚠ élément d'ancrage absent
  du livret : placé en fin ».
- **Assemblage de séquence** : la ligne « Encarts du livret » (lecture seule) de l'onglet
  Rendu PDF a disparu.
- **Référentiel** (modèle Fiches, principal) : les encarts non validés comptent dans la
  préparation et la validation (« n encarts non validé(s) ») ; l'aperçu avant création
  indique « Encarts du livret : n, dont k non validé(s) ».
- **Documents à publier** : sous chaque document, la version montrée et sa date — « Compilé
  le 19/11/2026 à 15 h 02 » ; pour un référentiel **verrouillé ou utilisé**, deux lignes :
  « Version compilée active le … » et « Version figée au verrouillage le … (publiée) », chacune
  avec ses liens ; « Tester » y est proposé (sauf structure du niveau archivée), avec la
  phrase : « « Tester » recompile la version active depuis l'atelier ; la version figée au
  verrouillage (celle de la publication) ne change pas. »
- Tous les PDF servis par l'appli partent avec `Cache-Control: no-cache` (le navigateur
  redemande toujours) ; les liens des documents portent la date de compilation (`&v=…`).

## Cause du signalement (PDF)

Le `.tex` et le TEXINPUTS des deux chemins étant identiques, la différence est le **fichier
servi**. Un référentiel a deux jeux de PDF : ceux de la **dernière compilation**
(`data_atelier\referentiels\<ref>\<nom>.pdf`, écrits par « Tester ») et, une fois verrouillé, la
**copie figée** au verrouillage (`…\<ref>\_verrouille\pdfs\`, utilisée par la publication et
le bloc « Données verrouillées »). Jusqu'à la v0.60.3, « Documents à publier » liait le
premier **sans en donner la date**, et pour un référentiel verrouillé **ne proposait pas
« Tester »** (options en lecture seule), alors que le serveur accepte la recompilation. Dans la
base de test, le référentiel interne de 6e (2026_N09) est verrouillé et son livret a été
compilé le 18/11 à 09 h 34, avant la v0.60.3 : c'est ce PDF, aux filets gris, que le lien
montrait. Le cache du navigateur n'est pas en cause avec `send_file` (Flask ≥ 2 envoie déjà
`no-cache` et un ETag) ; les PDF rendus en mémoire n'avaient, eux, aucun en-tête. À vérifier
chez Laurent : l'état de son référentiel « 6e 2027-2028 » — désormais affiché avec la date de
chaque version, ce qui lève le doute.

## Décisions

- **A1 Stockage** — même table `encarts` (identifiants, péremption, répartition atelier
  inchangés) ; colonnes ajoutées `etat_code` (`en_cours` / `valide`) et `ancre` ; type d'atome
  `encart` dans `services/etats_edition.TABLES_ATOMES` (route d'état commune, hook de
  validation, avertissements renvoyés par la route). Les anciennes colonnes (`position`,
  `exercice`, `exercice_id`) restent en base, plus lues par le livret.
- **A2 Ancre** — identifiant d'atome (activité ou exercice `ex_…`, fiche de résumé, carte
  mentale `cm_…`) ; `''` = fin (défaut), `debut` = début. Livret : l'encart vient juste après
  son élément ; élément absent de l'objectif (de la partie) : fin, après les encarts de fin
  d'avant. Activité non imprimée (option du livret) : l'encart garde sa place ; exercice de
  série E non incluse : fin d'objectif (règle E3 de la v0.59.2, même sortie).
- **A3 Corrigé** — `solution` permis pour tous les types, imprimé par `\seqSolutionDefiSix`
  (version corrigée seulement) : aucun changement du paquet ; l'import ne refuse plus un
  corrigé hors défi.
- **A4 Migration** — `apres_activite` → dernière activité de l'objectif dans le livret
  (`debut` s'il n'en a pas) ; `apres_exercice` → l'exercice (code du lot si l'identifiant
  manque) ; `fin_objectif` / `fin_partie` → fin ; ordre renuméroté dans l'ordre d'émission
  d'avant ; état = celui de la séquence ; `mtime` inchangé (rien n'est à recompiler). Faite au
  démarrage, en dernier (elle lit le livret), et par `outils/migrer_encarts_atomes.py` (essai
  à blanc / `--apply` avec sauvegarde et journal) — même fonction, idempotente.
- **A5 Import** (`outils/import_lot6e.py`, § 16) — clé facultative `apres` d'un encart, élément
  du lot : « F03 » (exercice), « activite:AE01 », « fiche », « carte_mentale » (encart de
  partie), « debut », « fin » ; prioritaire sur `position` (toujours lue). Élément introuvable
  ou valeur non reconnue : anomalie, encart non importé. Encarts créés « en cours » ; un
  encart **validé** n'est jamais modifié ni retiré par l'import (anomalie). Séquence validée :
  lot non importé (inchangé). Clé d'idempotence : (partie, objectif, ancre, rang).
- **A6 Atelier** — `AtelierEncart` ← `AtelierEditeur` (aucune copie du code commun) ; seules
  surcharges : filtres, formulaire (listes de la place chargées avant l'instantané « non
  modifié »), rendu élève / corrigé. Brique commune ajoutée à `AtelierEditeur` : les
  avertissements renvoyés par la route d'état sont affichés (validation unitaire et résumé
  de l'action groupée). Routes : `routes/encarts.py`.
- **A7 Péremption** — inchangée pour le livret et les corrigés (`encarts` y était) ; tout
  enregistrement, changement d'état ou suppression d'un encart périme ces documents (à la
  suppression, l'encart le plus récent du niveau reçoit un nouveau `mtime`).
- **A8 Référentiel** — encarts comptés comme atomes au modèle Fiches (principal) ; jamais au
  modèle « Notions et méthodes » ni pour une mise en route.
- **P1** `Cache-Control: no-cache` sur toute réponse `application/pdf` (`app.py`).
- **P2** `GET /api/referentiels/<ref>/documents` : `versions_pdf` par document (compilée :
  présente, date ; figée : présente, date de la trace `_verrouille\trace.json` ; version
  montrée ; recompilable).
- **P3** `GET …/documents/<id>/pdf?version=compilee|figee` ; sans paramètre : la compilée,
  sinon la figée d'un référentiel figé (avant : 404) ; en-têtes `X-Seq-Version-Pdf`,
  `X-Seq-Pdf-Date`.
- **P4** « Tester » pour un référentiel verrouillé ou utilisé dont la structure n'est pas
  archivée, avec la phrase qui dit que la version figée ne change pas.

## Marche à suivre (Windows)

1. Fermer l'appli, décompresser `seqenseigne_v0_61_0_delta.zip` à la racine (le dossier
   `appli\` du zip sur `appli\`), puis depuis `appli\` :
   ```
   ..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
   ```
2. **Migration des encarts, essai à blanc** (rien n'est écrit) :
   ```
   ..\outils\python\python.exe .\outils\migrer_encarts_atomes.py > ..\essai_encarts.txt
   ```
   Lire `essai_encarts.txt` : une ligne par encart « ancienne position → ancre [ordre, état] »,
   puis le total (base de test : 174 encarts, 83 validés, 91 en cours, 1 remarque « aucune
   activité : début de l'objectif »).
3. **Migration** : `..\outils\python\python.exe .\outils\migrer_encarts_atomes.py --apply`
   (répondre « o ») ; sauvegarde `data_atelier\sauvegardes\avant_encarts_atomes_<date>.db`,
   journal `journal_encarts_atomes_<date>.json`. Relancer sans `--apply` : « rien à faire ».
   (Si l'appli est lancée avant, elle fait la même migration au démarrage.)
4. `.\lancer.bat atelier` (depuis `appli\`), Ctrl+F5. Ateliers › Encart : choisir 6e ou 4e ;
   les encarts des séquences validées sont « validés », les autres « en cours » (à valider
   comme les autres atomes avant la validation du référentiel de 4e).
5. Référentiel › Documents à publier : chaque document dit maintenant de quand date le PDF
   montré ; pour le référentiel de 6e verrouillé, « Version compilée active » et « Version
   figée au verrouillage » ; « Tester » met à jour la première (livret aux filets noirs).

Aucun réimport des lots n'est nécessaire (réimport des mêmes lots : rien ne change).

## Pièges

- La version **figée** d'un référentiel verrouillé (celle de la publication) garde les filets
  gris : elle ne se recompile pas (c'est son rôle). Pour publier des filets noirs, il faut un
  nouveau verrouillage (déverrouiller seulement si le référentiel n'est pas utilisé) ; pour
  imprimer, la version compilée active ou l'atelier Séquence suffisent.
- Un encart dont l'élément d'ancrage a quitté l'objectif s'imprime en fin d'objectif : la
  validation le signale ; choisir une nouvelle place dans l'atelier.
- Les lots continuent d'accepter `position` ; `apres` est conseillé pour les nouveaux lots
  (`lot6e/FORMAT_ENCARTS.md`, section v0.61.0).

## Tests

`tests/test_v0_61_0_atelier_encarts_pdf.py` (19) : migration (positions → ancres, livret
identique dans cinq variantes, mtime inchangé, dernière activité, état de la séquence,
idempotence ; outil : essai à blanc sans écriture et même rapport que `--apply`, sauvegarde ;
démarrage ; base sans table) ; atelier (création, ancres avec numéros du livret, placement
après l'exercice et sa remédiation, ancre d'un autre objectif refusée, rendu élève / corrigé,
renumérotation, repli et avertissements, validation groupée côté serveur, lecture seule,
encart de partie après la carte mentale, objectif « Cours » refusé) ; import (`apres` sous ses
formes, réimport nul, valeurs refusées, réimport après migration, encart validé gardé) ;
péremption ; référentiel ; ligne retirée ; PDF (cause : version compilée / figée datées,
`?version`, figée servie sans compilée, structure archivée, `no-cache` partout).
`tests_js/v0_61_0_atelier_encarts.test.js` (14) : héritage sans copie, filtres, toutes
séquences, création, validation groupée et unitaire avec avertissements, formulaire (place
chargée avant l'instantané, ancre disparue gardée, changement de partie), rendu, ligne
retirée, inscriptions de l'atelier, affichage des versions de PDF et de « Tester ».
Mis à jour (motif en commentaire) : `tests/test_v0_59_2_vue_encarts.py`,
`tests_js/v0_56_3_carte_mentale_fonctions_communes.test.js`.

## Non fait (signalé)

- Recherche (onglet Outils) : les encarts n'y sont pas encore (comme les autres atomes, à
  ajouter si besoin) ; rendu par lot : non plus.
- La route en lecture `GET /api/v2/livret-sequence/<niveau>/<séq>/encarts` reste (plus
  utilisée par l'interface).

## Fichiers

Nouveaux : `routes/encarts.py`, `static/atelier_encart.js`, `outils/migrer_encarts_atomes.py`,
`tests/test_v0_61_0_atelier_encarts_pdf.py`, `tests_js/v0_61_0_atelier_encarts.test.js`,
`doc/redemarrage_v0_61_0.md`. Modifiés : `app.py`, `persistence/sqlite_store.py`,
`services/encarts.py`, `services/livret_sequence_6e.py`, `services/etats_edition.py`,
`services/v2_edition.py`, `services/referentiel_validation.py`,
`services/referentiels_internes.py`, `services/referentiel_documents_compilation.py`,
`services/profils.py`, `routes/livret_sequence.py`, `routes/referentiel_documents.py`,
`routes/referentiel_documents_compilation.py`, `outils/import_lot6e.py`, `static/app.js`,
`static/app.css`, `static/atelier_editeur.js`, `static/atelier_filtres_hook.js`,
`static/atelier_seqniv_assemblage.js`, `static/atelier_referentiel.js`,
`static/referentiel_unifie.js`, `templates/index.html`, `tests/test_v0_59_2_vue_encarts.py`,
`tests_js/v0_56_3_carte_mentale_fonctions_communes.test.js`, `doc/ETAT_COURANT.md`,
`doc/ROADMAP.md`, `paquet/CHANGELOG.md`. Aucun fichier supprimé.
