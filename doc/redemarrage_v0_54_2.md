# Redémarrage v0.54.2 — « Tout compiler » pour toute séquence

## Besoin (Laurent, 26 octobre 2026)

> « Pourrais-tu ajouter un bouton "Tout compiler" pour n'importe quelle séquence (par Fiches et
> par Notions/Méthodes) ? »

Le bouton existait pour les mises en route (Mnn, v0.53.3). Il est maintenant dans l'onglet
« Rendu PDF » de **toute séquence** de l'atelier.

## Audit (état de la v0.54.1)

- L'onglet « Rendu PDF » d'une séquence principale (Snn) n'a **pas** de sélecteur « Document » :
  il a deux boutons, « Compiler le livret » (livret 6e version élève, ou livret du cycle 4
  « tout en un », selon le modèle de l'atelier, règle R1b) et « Compiler le plan de travail ».
  Le sélecteur « Document » n'existe que pour les mises en route.
- La liste des documents qu'un modèle sait produire est le **catalogue du modèle**
  (`services/gabarits_documents.py`) : c'est la source des « Documents à publier » et des
  producteurs de l'orchestrateur. C'est donc la source retenue (voir D-LISTE).

## Décisions

- **D-TOUT-SEQ** — Route `GET /api/v2/livret-sequence/<niveau>/<Snn>/tout-compiler`
  (`services/sequence_tout_compiler.py`) : même mécanisme et mêmes événements que le
  « Tout compiler » des mises en route (flux SSE, un événement par document avec son statut,
  cache `cache_rendus`, annulation par le bouton « Annuler », abandon après N erreurs
  d'infrastructure consécutives, archive ZIP dans `data\rapports\`, .tex et .log d'un échec
  dans `cache_rendus\echecs_mer\`, liens communs `mer/archive` et `mer/echec`). La boucle est
  partagée : `mer_tout_compiler.iter_compiler_documents` (les mises en route l'utilisent, leur
  liste et leur route ne changent pas). Chaque événement « document » porte aussi sa durée
  (`duree_ms`), « fin » la durée totale. Modèle : celui de l'onglet (`_gabarit_demande`,
  `?gabarit=` accepté). Route de la catégorie « atelier » (blueprint `livret_sequence`).
- **D-LISTE** — Une table par modèle, rattachée au catalogue :
  `DOCUMENTS_SEQUENCE_FICHES` et `DOCUMENTS_SEQUENCE_NOTIONS` ; les types du catalogue qui ne
  concernent pas une séquence sont dans `EXCLUS_FICHES` / `EXCLUS_NOTIONS` avec leur raison.
  Un test exige que table + exclusions = catalogue : un type ajouté plus tard au catalogue doit
  être rangé (donc compilé s'il concerne une séquence).

  | Modèle Fiches (6e) | PDF |
  |---|---|
  | Livret | élève, corrigé |
  | Fiches de cours (complètes) | si la séquence a des fiches |
  | Plan de travail | 1 |
  | Évaluations de la séquence | sujets A et B, élève et corrigé (sujets en deux parties compris : le découpage est dans le document) |
  | TP, AC, AT de la séquence | élève et corrigé |
  | exclu : Corrigés enseignant | pour une séquence = le livret corrigé (seul le titre interne change) |

  | Modèle Notions et méthodes (cycle 4) | PDF |
  |---|---|
  | Livret de séquence | 1 (celui du bouton) |
  | Notions et méthodes | le livret sans ses exercices (option `contenu = cours_seul` du catalogue) |
  | Plan de travail | 1 (celui du bouton) |
  | Fiches de résumé de la séquence | à compléter, complètes |
  | Planches de cartes d'automatisme | si la séquence a des cartes validées |
  | Évaluations de la séquence | 1 par évaluation |
  | exclus : livrets d'exercices, de cours, de corrigés, récap des cartes | livrets annuels du niveau |

  Il n'existe pas de document « méthodes » seul ni « notions » seul par séquence : les deux
  sont dans « Notions et méthodes ». Une évaluation appartient à la séquence de la majorité de
  ses exercices (comme pour la publication du référentiel) ; elle est numérotée par son rang
  dans la séquence (`eval2` = 2e évaluation de S03).
- **Noms** : `S03_livret_eleve.pdf`, `S03_eval2_A_corrige.pdf`, `S03_TP01_corrige.pdf`,
  `S02_AT01_eleve.pdf` (6e : séquence seule, comme `M03_…`) ; `N10_S01_livret.pdf`,
  `N11_S04_notions_methodes.pdf`, `N10_S01_eval1.pdf` (autres niveaux : niveau et séquence).
  Archive : `S03_sequence_documents_<date>.zip`, `N10_S01_sequence_documents_<date>.zip`.
- **Même .tex que les boutons** : livret et plan de travail de la liste = ceux des boutons
  (tests, 6e et cycle 4) ; les autres documents passent par les producteurs de la publication
  du référentiel. Aucun générateur modifié.
- **Aucune écriture en base** : les générateurs lisent (empreinte du dump SQL identique avant et
  après un « Tout compiler » réel) ; seuls le cache de compilation, `echecs_mer\` et
  `rapports\` reçoivent des fichiers.
- Interface (`static/atelier_seqniv_assemblage.js`, `static/seqniv_pur.js`) : le bouton
  « 📦 Tout compiler » est affiché pour toute séquence (infobulle selon le modèle) ; une Snn
  ignore le sélecteur de partie des mises en route (`SeqnivPur.urlToutCompiler`) ; changer de
  séquence annule un « Tout compiler » en cours.

## Appli

- Nouveaux : `services/sequence_tout_compiler.py`, `tests/test_v0_54_2_tout_compiler_sequence.py`
  (13), `tests_js/tout_compiler_sequence.test.js` (5).
- Modifiés : `services/mer_tout_compiler.py` (boucle partagée, durées), `routes/livret_sequence.py`
  (route), `static/atelier_seqniv_assemblage.js`, `static/seqniv_pur.js`, `doc/ETAT_COURANT.md`.
- Aucune migration, aucune table, module LaTeX inchangé. Cycle 4, 6e et mises en route : même
  `.tex` qu'en v0.54.1 (comparaison des sorties). N11_v2025 : rien d'écrit.

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`) : `appli\…`.
2. Relancer l'appli ; Atelier › une séquence (S03, ou une séquence du cycle 4) › onglet
   « Rendu PDF » › « 📦 Tout compiler ».
