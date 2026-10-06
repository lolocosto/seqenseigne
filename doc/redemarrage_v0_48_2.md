# Redémarrage v0.48.2 — Référentiel principal externe (même structure qu'un interne)

Découpage validé de la suite : v0.48.2 (ce lot : modèle, écran de détail,
règles, usage par la progression principale) ; v0.48.3 harmonisation des
écrans interne / externe (liste à gauche, détail à droite, nom calculé, type
principal / MER pour tous — un référentiel interne « MER » ne sera proposé
qu'à la progression de MER, les internes existants deviennent « principal ») ;
v0.48.4 fichiers externes portant leur séance / retour / délai (placement
automatique, remplacé par une association manuelle) + documents de MER.

## Décisions validées

- **Un seul modèle** : un référentiel principal externe est un référentiel
  figé (`referentiel_niveaux` + séquences, parties, objectifs) avec
  `source = 'externe'`. Progression principale, début de séance, travail,
  compétences l'utilisent sans distinction.
- **Nom calculé** : « 4e — 2026-2027 — Principal », lettre b, c… si plusieurs
  pour le même niveau et la même année ; **description** libre facultative.
  Identifiant `X<année>_<niveau><lettre>` (convention interne).
- **Structure** : séquences (code S01… attribué à la création, jamais
  modifié ; ordre réordonnable) → parties (nb de séances) → objectifs
  (nb de séances, critères F/A/E), **numérotés automatiquement** et
  renumérotés au réordonnancement. Thèmes : plus tard (facultatifs).
- **Fichiers** de tous formats, par séquence ou par partie ; les PDF
  s'affichent, les autres se téléchargent.
- **Utilisable dès sa création** (même incomplet) par la progression
  principale (liste des référentiels : internes verrouillés / utilisés +
  externes non annulés, marqués « (externe) ») ; passe « utilisé » quand une
  progression s'y rattache ; non supprimable ensuite.
- **Séquence commencée** (un créneau d'une progression qui l'utilise a
  démarré) : plus de modification de structure ni de suppression ; restent
  la correction des libellés (séquence, objectifs, critères) et l'ajout de
  fichiers. Une séquence placée dans une progression (pas encore commencée)
  ne se supprime pas tant que ses créneaux existent.
- Fichiers proposés dans « Cette séquence » des documents associables de la
  progression (libellé = nom du fichier, + « (partie n) »).
- Pas de conversion des anciens référentiels externes « principal » ; les
  référentiels externes de MER ne changent pas.

## Code

- Migration : colonnes `source`, `type_ref`, `annee` de
  `referentiel_niveaux` ; table `referentiel_fichiers`.
- `services/referentiel_principal_externe.py`,
  `routes/referentiel_principal_externe.py`
  (`/api/referentiels-principaux-externes…`), `static/referentiel_pe.js`,
  section « Principaux » de Conception › Niveau › Référentiel externe.
- Séparation interne / externe : `services/referentiels.lister_par_niveau`
  (internes seulement, pas de mise à jour d'éligibilité des externes),
  `/api/referentiels?externes=1` (progression), contrôle d'état du
  changement de référentiel d'une progression, passage « utilisé »,
  `progression_doc` (documents internes du référentiel interne seulement ;
  fichiers externes ajoutés).
- `static/atelier_progression.js` : référentiels externes proposés.

## Tests

- pytest `tests/test_v0_48_2_referentiel_principal_externe.py` (7).
- Suite complète : pytest 4147 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : création (« 5e — 2026-2027 — Principal », « Manuel
  Sésamath »), séquence, partie, deux objectifs (01, 02), fichier PDF.

## ROADMAP

- Référentiel interne de MER : nécessite de concevoir les documents LaTeX
  adaptés (activités de 5-10 min en début de séance ; fiches de cours, séries
  de calcul mental avec score, corrigés et tests séparés) et sans doute de
  nouveaux ateliers ; le type « MER » sera ouvert dès v0.48.3.
