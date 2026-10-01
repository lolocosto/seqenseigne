# Redémarrage v0.38.0 — EdT versionné, salle et AESH par case

Deuxième livraison du chantier « plans de classe »
(`doc/cadrage_plans_de_classe.md`).

## Décisions validées

- **Modèle** : chaque case d'EdT porte une période `[valide_du, valide_au)` en
  lundis ISO ('' = début / fin d'année). Pas de copie de l'EdT par version :
  les cases inchangées gardent leur identifiant (et leurs affectations).
- **États** par (année, établissement), table `edt_etats` :
  - « en saisie » (défaut, dont l'EdT 2026-2027 existant) : modifications sur
    place, valables toute l'année, aucun changement daté ;
  - « figé » (bouton, **définitif**) : plus de modification sur place sauf
    libellé et ordre ; tout autre changement prend effet un lundi ≥ semaine
    prochaine (pas de rétroactivité). Seul l'état figé permet des états futurs.
- **Scission** : modifier une case en cours au lundi D ferme l'ancienne
  période en D et crée une nouvelle case à partir de D, qui **hérite des
  affectations de séance** (automatisme / progression / MER). Supprimer une
  case en cours = la terminer en D. Une case future se modifie / supprime
  directement.
- **Changements programmés** : liste par lundi (cases qui commencent / qui
  s'arrêtent), annulables tant qu'ils sont à venir (la case remplacée reprend
  jusqu'à la fin de la case qui la remplaçait).
- **Aperçu** avant enregistrement d'un changement daté : séances restantes
  par classe jusqu'à la fin de l'année, avant → après (opération jouée dans un
  SAVEPOINT puis annulée).
- **Salle** (facultative, salles de l'établissement) et **nombre d'AESH**
  (0 à 5, sans les noms) par case. Action « Mettre cette salle sur tous mes
  cours » (cases avec une classe ; datée si l'EdT est figé).
- Une salle posée dans l'EdT est « utilisée » (v0.37.0) : elle ne se supprime
  plus et son plan ne se modifie plus qu'à partir de la semaine prochaine.

## Code

- Migration : reconstruction de `edt_creneaux` (suppression de la contrainte
  UNIQUE historique ; + `valide_du`, `valide_au`, `salle_id`, `nb_aesh` ;
  index), table `edt_etats`. Le non-chevauchement (même créneau, semaines
  A/B/AB compatibles, périodes qui se recouvrent) est contrôlé par le service.
- `services/edt.py` : `lister(..., a_la_date=, etablissement_id=)`, `etat`,
  `figer`, `ajouter/modifier/supprimer(..., a_partir_du=, aujourd_hui=)`,
  `changements_programmes`, `annuler_changement`, `appliquer_salle`,
  `compter_seances(..., a_la_date=)`.
- `services/projection_seances.py` : filtre de période semaine par semaine →
  numérotation continue et alternance A/B intactes à travers les changements.
- `services/planification_hebdo.py`, `services/tableau_bord.py` : cases
  valides la semaine affichée.
- `services/edt_apercu.py` + routes `routes/edt.py` :
  `GET /api/edt?semaine_du=&etablissement_id=` (état, changements, date
  d'effet min), `POST /api/edt/figer`, `DELETE /api/edt/changements/<lundi>`,
  `POST /api/edt/appliquer-salle`, `POST /api/edt/apercu`,
  `DELETE /api/edt/<id>?a_partir_du=`.
- `static/edt.js` : navigation par semaine, état + bouton « Figer », salle
  partout, salle/AESH/date d'effet dans le popover, marque « ⟳ jj/mm » sur
  une case qui change, « nouveau » sur une case qui commence la semaine
  affichée, liste des changements programmés (Voir / Annuler), aperçu.

## Tests

- pytest `tests/test_v0_38_0_edt_versionne.py` (19) : migration d'une base à
  l'ancien schéma, en saisie, figé (libellé sur place, date obligatoire,
  scission + héritage, case future, ajout/suppression datés, chevauchement),
  changements programmés et annulation (y compris entre deux changements),
  salle/AESH, salle utilisée, salle partout, comptage à la date, projection à
  travers un changement, parcours REST avec aperçu.
- Parcours navigateur : figeage, AESH 2 → 1 au 05/10 (aperçu « inchangé »),
  suppression datée du jeudi M3 de 4EME3 (aperçu 129 → 86 séances), semaine
  suivante affichée avec le changement.

## Déploiement

Décompresser ; `..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5`.
Redémarrer (migration automatique, sauvegarder `data\seqenseigne.db` avant),
Ctrl+Shift+R. Puis, dans Planification → EdT hebdo : renseigner salles et AESH
(« Mettre cette salle sur tous mes cours »), vérifier, et seulement ensuite
« Figer l'emploi du temps ».

## Dettes relevées (non traitées)

- Préparation de la projection (grille, indispos, vacances, borne du
  1er septembre) dupliquée dans 5 routes + `edt_apercu`.
- Planification hebdo et tableau de bord listent les cases de la semaine
  sans filtrer la semaine A/B (préexistant).
- Écran MER (affectation case par case) : il montre l'EdT de la semaine en
  cours ; une affectation modifiée après un changement programmé ne se
  reporte pas sur la case future (l'héritage se fait au moment de la
  scission).
- L'outil d'import `outils/migrer_edt_groupe_usage.py` (v0.20.2) suppose
  l'ancien schéma ; obsolète.
