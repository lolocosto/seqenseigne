-- seqenseigne — Schéma SQLite v3
-- Généré depuis schema.sql, appliqué par SqliteStore._init_db()

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── Structure du programme officiel (chantier R1) ─────────────────────────────
-- Ces trois tables décrivent la hiérarchie partagée par tout le cycle :
-- cycle → thèmes + séquences du cycle.
-- Elles ne dépendent pas du niveau (spécificité niveau = objectifs et atomes,
-- qui seront rattachés plus tard via un futur chantier R4).

CREATE TABLE IF NOT EXISTS cycles (
    code        TEXT PRIMARY KEY,        -- 'C04', 'C03'…
    nom         TEXT NOT NULL,           -- 'Cycle 4'
    description TEXT NOT NULL DEFAULT ''
);

-- ── Niveaux scolaires (chantier v0.13.0) ──────────────────────────────────────
-- Source de vérité des attributs intrinsèques d'un niveau (cycle, ordre dans
-- le cycle, libellés). Initialement importée depuis data/param_niveaux.csv
-- au premier démarrage avec table vide ; ensuite la BDD devient maître.
--
-- Note : la table existante `niveaux` (sans suffixe) est une table de
-- tracking d'élèves (classe_id, eleve_id, niveau_code) sans rapport avec
-- les niveaux scolaires. C'est pour cela que la nouvelle table porte le
-- nom `param_niveaux` (calqué sur param_niveaux.csv) plutôt que `niveaux`.

CREATE TABLE IF NOT EXISTS param_niveaux (
    code              TEXT PRIMARY KEY,                                 -- 'N10', 'N11', 'N12', 'N09', 'N08', 'N07'
    cycle_code        TEXT NOT NULL REFERENCES cycles(code) ON DELETE RESTRICT,
    annee_dans_cycle  TEXT NOT NULL,                                    -- 'anneeun', 'anneedeux', 'anneetrois'
    nom_court         TEXT NOT NULL,                                    -- '5ème', '4ème', '3ème', '6ème', 'CM2', 'CM1'
    nom_long          TEXT NOT NULL DEFAULT '',                         -- 'cinquième', 'quatrième', 'troisième'…
    ordre             INTEGER NOT NULL DEFAULT 0                        -- pour tri global (N07=1, N08=2, …, N12=6)
);
CREATE INDEX IF NOT EXISTS idx_param_niveaux_cycle
    ON param_niveaux (cycle_code, ordre);

CREATE TABLE IF NOT EXISTS themes (
    id           TEXT PRIMARY KEY,        -- UUID 'th_xxx'
    cycle_code   TEXT NOT NULL REFERENCES cycles(code) ON DELETE CASCADE,
    code         TEXT NOT NULL,           -- 'A', 'B', 'C'…
    nom          TEXT NOT NULL,           -- 'Nombres et Calculs'
    code_couleur TEXT NOT NULL DEFAULT '', -- 'nombres', 'donnees'…
    description  TEXT NOT NULL DEFAULT '', -- LaTeX libre
    ordre        INTEGER NOT NULL DEFAULT 0,
    UNIQUE (cycle_code, nom),
    UNIQUE (cycle_code, code)
);
CREATE INDEX IF NOT EXISTS idx_themes_cycle
    ON themes (cycle_code, ordre);

CREATE TABLE IF NOT EXISTS sequences_du_cycle (
    id          TEXT PRIMARY KEY,         -- UUID 'sc_xxx'
    cycle_code  TEXT NOT NULL REFERENCES cycles(code) ON DELETE CASCADE,
    code        TEXT NOT NULL,            -- 'S01', 'S02'…
    numero      INTEGER NOT NULL,         -- 1, 2, 3…
    nom         TEXT NOT NULL,
    theme_id    TEXT REFERENCES themes(id) ON DELETE SET NULL,
    UNIQUE (cycle_code, code),
    UNIQUE (cycle_code, numero)
);
CREATE INDEX IF NOT EXISTS idx_sequences_cycle
    ON sequences_du_cycle (cycle_code, numero);
CREATE INDEX IF NOT EXISTS idx_sequences_theme
    ON sequences_du_cycle (theme_id);

-- ── Séquences par niveau et parties (chantier R4) ────────────────────────────
-- Modèle cible : chaque séquence du cycle se décline en une déclinaison par
-- niveau (N10, N11, N12). Chaque déclinaison contient 1..N parties
-- qui regroupent des objectifs. Les précédences sont au niveau de la partie
-- (pas de l'objectif). Les exercices rattachés à un objectif sont indexés
-- par (série, num).
--
-- v0.14.7 — La table `objectifs` est désormais le modèle unique
-- d'objectifs pédagogiques (issue du chantier R4 sous le nom temporaire
-- `objectifs_v2`, renommée définitivement en `objectifs` après
-- suppression de l'ancienne table v1 en v0.14.6.b.2).

CREATE TABLE IF NOT EXISTS sequences_par_niveau (
    id            TEXT PRIMARY KEY,         -- UUID 'sn_xxx'
    niveau        TEXT NOT NULL,            -- 'N10', 'N11', 'N12'
    sequence_code TEXT NOT NULL,            -- 'S01'..'S14' (code de la séquence du cycle)
    parametres    TEXT NOT NULL DEFAULT '', -- contenu LaTeX du fichier _param.tex
    -- v0.16.9 — État validable de la séquence-niveau (régime mixte + verrou).
    -- 'en_cours' (modifiable) | 'valide' (lecture seule). Tout est en_cours par
    -- défaut ; Laurent valide manuellement une séquence prête (un hook
    -- pédagogique contrôle alors sa complétude, cf. services/v2_edition.py).
    etat_code     TEXT NOT NULL DEFAULT 'en_cours',
    UNIQUE (niveau, sequence_code)
);
CREATE INDEX IF NOT EXISTS idx_sequences_par_niveau_seq
    ON sequences_par_niveau (sequence_code);

CREATE TABLE IF NOT EXISTS sequence_parties (
    id                     TEXT PRIMARY KEY,  -- UUID 'pt_xxx'
    sequence_par_niveau_id TEXT NOT NULL
                           REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    numero                 INTEGER NOT NULL,  -- 1, 2, 3...
    -- v0.12.0 — Plan de travail générique : nombre de séances prévues pour
    -- la réalisation des exercices de Révision et d'Approche dans cette
    -- partie. REAL pour permettre les demi-séances (cohérent avec
    -- creneaux.nb_seances_*). Saisie dans l'atelier d'assemblage de
    -- séquence-niveau, agrégée dans le livret annuel des plans de travail.
    nb_seances_R_AE        REAL NOT NULL DEFAULT 0,
    UNIQUE (sequence_par_niveau_id, numero)
);
CREATE INDEX IF NOT EXISTS idx_sequence_parties_seq
    ON sequence_parties (sequence_par_niveau_id, numero);

CREATE TABLE IF NOT EXISTS partie_precedences (
    partie_id        TEXT NOT NULL
                     REFERENCES sequence_parties(id) ON DELETE CASCADE,
    precedent_niveau TEXT NOT NULL,    -- ex: 'N10'
    precedent_seq    TEXT NOT NULL,    -- ex: 'S01'
    PRIMARY KEY (partie_id, precedent_niveau, precedent_seq)
);

-- v0.10.2 — Précédences au niveau séquence-niveau (et plus seulement partie).
-- Les exos de révision (R) qu'on peut placer dans une partie viennent
-- nécessairement d'une séquence-niveau qui figure dans cette table.
--
-- Conserver `partie_precedences` (héritage R4) pour rétrocompatibilité ;
-- les deux notions coexistent : `partie_precedences` reste utilisée par
-- l'éditeur v2 historique pour annoter une partie individuellement.
-- L'atelier d'assemblage v0.10.2 utilise exclusivement cette nouvelle table
-- pour valider la provenance des exos R.
--
-- precedent_niveau peut être un niveau collège (N10, N11, N12) OU un niveau
-- du cycle 3 (CM1, CM2, etc. — pas encore importés en v0.10.2 ; pour l'instant
-- on accepte la convention "C03" comme niveau virtuel pointant vers le
-- découpage de cycle C03). À terme, quand le CRUD du découpage de cycle sera
-- en place, on basculera vers de vrais niveaux N09, N08, etc.
CREATE TABLE IF NOT EXISTS sequence_par_niveau_precedences (
    sequence_par_niveau_id TEXT NOT NULL
                           REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    precedent_niveau       TEXT NOT NULL,
    precedent_seq          TEXT NOT NULL,
    ordre                  INTEGER NOT NULL DEFAULT 0,  -- pour tri stable
    PRIMARY KEY (sequence_par_niveau_id, precedent_niveau, precedent_seq)
);
CREATE INDEX IF NOT EXISTS idx_seq_niv_prec_seq
    ON sequence_par_niveau_precedences (sequence_par_niveau_id, ordre);

CREATE TABLE IF NOT EXISTS objectifs (
    id         TEXT PRIMARY KEY,         -- UUID 'ob_xxx' (même préfixe que l'ancienne)
    partie_id  TEXT NOT NULL
               REFERENCES sequence_parties(id) ON DELETE CASCADE,
    code       TEXT NOT NULL,            -- '01', '02', 'Cours'... (libre dans la séquence)
    nom        TEXT NOT NULL DEFAULT '',
    methode_id TEXT REFERENCES methodes(id) ON DELETE SET NULL,
    critere_F  TEXT NOT NULL DEFAULT '',  -- critère Fondamental
    critere_A  TEXT NOT NULL DEFAULT '',  -- critère Approfondissement
    critere_E  TEXT NOT NULL DEFAULT '',  -- critère Expertise
    fin_cycle  TEXT NOT NULL DEFAULT 'N', -- 'O' = attendu de fin de cycle 4, 'N' sinon
    -- v0.12.0 — Plan de travail générique : nombre de séances prévues pour
    -- l'objectif. Pour l'objectif "cours" (code 01/11/21) : séances
    -- d'explication par l'enseignant. Pour les autres objectifs : séances
    -- de réalisation des exercices F/A/E. REAL pour permettre les
    -- demi-séances. Saisie dans l'atelier d'assemblage, agrégée dans le
    -- livret annuel des plans de travail.
    nb_seances REAL NOT NULL DEFAULT 0,
    UNIQUE (partie_id, code)
);
CREATE INDEX IF NOT EXISTS idx_objectifs_partie
    ON objectifs (partie_id);

-- Notions associées à un objectif (v0.6.4 : remplace methode_notions).
-- Une notion peut être référencée par plusieurs objectifs ; un objectif peut
-- citer plusieurs notions. L'ordre est libre, géré par la colonne `ordre`.
CREATE TABLE IF NOT EXISTS objectif_notions (
    objectif_id TEXT NOT NULL
                REFERENCES objectifs(id) ON DELETE CASCADE,
    notion_id   TEXT NOT NULL
                REFERENCES notions(id) ON DELETE CASCADE,
    ordre       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, notion_id)
);
CREATE INDEX IF NOT EXISTS idx_objectif_notions_objectif
    ON objectif_notions (objectif_id);
CREATE INDEX IF NOT EXISTS idx_objectif_notions_notion
    ON objectif_notions (notion_id);

-- ── Liaison objectif ↔ carte d'automatisme (v0.13.6.13) ──────────────────────
-- Avant v0.13.6.13 : une carte portait directement (lien_type, lien_id)
-- pointant soit une notion, soit une méthode. C'était une cardinalité
-- 1:1 implicite, gérée par contrainte CHECK sur cartes_automatisme.
--
-- Depuis v0.13.6.13 : remplacement par une table de liaison N:M classique,
-- alignée sur la structure d'objectif_notions, d'objectif_exos et
-- d'objectif_fiches. Cela permet à terme à une carte de servir plusieurs
-- objectifs (cas d'usage non actuel mais anticipé). En pratique, Laurent
-- utilise aujourd'hui une seule liaison par carte ; l'application ne pose
-- pas de contrainte d'unicité sur carte_id mais l'UI atelier carte
-- garantit le 1:1 par défaut.
--
-- Les colonnes lien_type / lien_id de cartes_automatisme restent en place
-- en v0.13.6.13 (donnée historique non écrite) ; leur suppression est
-- prévue dans le nettoyage v0.14.

CREATE TABLE IF NOT EXISTS objectif_cartes (
    objectif_id TEXT NOT NULL
                REFERENCES objectifs(id) ON DELETE CASCADE,
    carte_id    TEXT NOT NULL
                REFERENCES cartes_automatisme(id) ON DELETE CASCADE,
    ordre       INTEGER NOT NULL DEFAULT 0,
    mtime       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (objectif_id, carte_id)
);
CREATE INDEX IF NOT EXISTS idx_objectif_cartes_objectif
    ON objectif_cartes (objectif_id);
CREATE INDEX IF NOT EXISTS idx_objectif_cartes_carte
    ON objectif_cartes (carte_id);

CREATE TABLE IF NOT EXISTS objectif_exos (
    objectif_id    TEXT NOT NULL
                   REFERENCES objectifs(id) ON DELETE CASCADE,
    serie          TEXT NOT NULL,   -- 'EA', 'F', 'A', 'E' (v0.11.2 : 'R' retiré)
    exercice_id    TEXT NOT NULL
                   REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre          INTEGER NOT NULL DEFAULT 0,  -- rang d'affichage (dense, démarre à 1)
    -- v0.11.2 : les colonnes origin_* ne servaient qu'à la série 'R'
    -- (révisions héritées d'un niveau précédent). Cette série ayant été
    -- supprimée, ces colonnes ne sont plus écrites par les nouvelles
    -- entrées. Conservées au schéma pour rétrocompatibilité ; le retrait
    -- effectif (ALTER TABLE équivalent) est planifié en v0.x ultérieure
    -- (cf. roadmap "nettoyage 3-full série R").
    origin_niveau  TEXT,
    origin_seq     TEXT,
    origin_serie   TEXT,
    origin_num     INTEGER,
    PRIMARY KEY (objectif_id, serie, exercice_id),
    UNIQUE (objectif_id, serie, ordre)
);
CREATE INDEX IF NOT EXISTS idx_objectif_exos_exo
    ON objectif_exos (exercice_id);

-- ── v0.10 — Atelier d'assemblage de séquence-dans-niveau ─────────────────────
-- Exos de révision (R) ou d'approche (EA) attachés directement à une partie,
-- indépendamment de tout objectif. Permet à l'enseignant de prévoir des
-- exos en début de partie sans être contraint d'avoir activé l'objectif
-- "Connaître les notions et les méthodes" de la partie.
--
-- Le `type` vaut 'R' (révision : exos venant d'un niveau précédent, série A
-- du même code de séquence à n-1) ou 'EA' (approche : exos de la série EA
-- de la séquence courante).
--
-- Pour les exos R, les colonnes origin_* identifient l'exo source
-- (origin_niveau/origin_seq/origin_serie='A'/origin_num) ; pour les exos EA,
-- elles peuvent rester nulles (l'exo appartient déjà à la séquence courante).
CREATE TABLE IF NOT EXISTS partie_exos_revision_approche (
    partie_id      TEXT NOT NULL
                   REFERENCES sequence_parties(id) ON DELETE CASCADE,
    type           TEXT NOT NULL,   -- 'R' ou 'EA'
    exercice_id    TEXT NOT NULL
                   REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre          INTEGER NOT NULL DEFAULT 0,
    origin_niveau  TEXT,
    origin_seq     TEXT,
    origin_serie   TEXT,
    origin_num     INTEGER,
    PRIMARY KEY (partie_id, type, exercice_id),
    UNIQUE (partie_id, type, ordre)
);
CREATE INDEX IF NOT EXISTS idx_partie_exos_ra_exo
    ON partie_exos_revision_approche (exercice_id);

-- État UI persistant de l'atelier d'assemblage : quel objectif est ouvert
-- en édition pour chaque séquence par niveau. Permet de retrouver l'état
-- exact en quittant et revenant sur l'atelier.
--
-- Une seule ligne par sequence_par_niveau_id. objectif_ouvert_id NULL
-- signifie « tous les objectifs fermés » (mode liste des méthodes à
-- gauche). FK ON DELETE SET NULL pour garder la ligne après suppression
-- d'un objectif.
CREATE TABLE IF NOT EXISTS ui_etat_atelier_sequence (
    sequence_par_niveau_id TEXT PRIMARY KEY
                           REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    objectif_ouvert_id     TEXT REFERENCES objectifs(id) ON DELETE SET NULL,
    derniere_maj           TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ui_etat_atelier_obj
    ON ui_etat_atelier_sequence (objectif_ouvert_id);

-- ── Images ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS images (
    id        TEXT PRIMARY KEY,
    chemin    TEXT NOT NULL UNIQUE,   -- relatif à data/images/
    sha256    TEXT NOT NULL,
    taille    INTEGER,
    mime_type TEXT NOT NULL DEFAULT 'image/png'
);

-- ── Sections d'atome (notion / méthode) ───────────────────────────────────
--
-- v0.6.4 : remplace l'ancienne table items_texte (qui n'avait que 2
-- catégories en dur : 'exemple' et 'remarque').
--
-- Modèle générique à 2 niveaux :
--   atome_sections        — une « section » d'un atome avec un titre libre
--                           ('Exemples', 'Remarques', 'Conséquences',
--                            'Démonstration', 'Démonstration de la
--                            réciproque', 'Propriété', etc.)
--   atome_section_items   — les items à l'intérieur d'une section, chacun
--                           contient du LaTeX brut (peut inclure
--                           multicols, tikzpicture, sous-listes, etc.)
--
-- L'ordre des sections (et des items) est piloté par la colonne `ordre`.
CREATE TABLE IF NOT EXISTS atome_sections (
    id           TEXT PRIMARY KEY,
    entite_type  TEXT NOT NULL,      -- 'notion' | 'methode'
    entite_id    TEXT NOT NULL,
    titre        TEXT NOT NULL,      -- libellé libre ; vocabulaire normalisé
                                     -- recommandé : 'Exemples', 'Remarques',
                                     -- 'Conséquences', 'Démonstration',
                                     -- 'Démonstration de la réciproque',
                                     -- 'Démonstration de la contraposée',
                                     -- 'Propriété'
    ordre        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_atome_sections
    ON atome_sections (entite_type, entite_id, ordre);

CREATE TABLE IF NOT EXISTS atome_section_items (
    id           TEXT PRIMARY KEY,
    section_id   TEXT NOT NULL REFERENCES atome_sections(id) ON DELETE CASCADE,
    ordre        INTEGER NOT NULL DEFAULT 0,
    corps        TEXT NOT NULL DEFAULT ''   -- LaTeX brut
);
CREATE INDEX IF NOT EXISTS idx_atome_section_items
    ON atome_section_items (section_id, ordre);

-- Annexes (figures, tableaux) de notions, méthodes et exercices
CREATE TABLE IF NOT EXISTS annexes (
    id          TEXT PRIMARY KEY,
    entite_type TEXT NOT NULL,  -- 'notion' | 'methode' | 'exercice'
    entite_id   TEXT NOT NULL,
    ordre       INTEGER NOT NULL DEFAULT 0,
    titre       TEXT NOT NULL DEFAULT '',
    corps       TEXT NOT NULL DEFAULT '',
    image_id    TEXT REFERENCES images(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_annexes
    ON annexes (entite_type, entite_id, ordre);

-- ── Notions ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS notions (
    id               TEXT PRIMARY KEY,
    titre            TEXT NOT NULL DEFAULT '',
    corps            TEXT NOT NULL DEFAULT '',
    ordre_sections   TEXT NOT NULL DEFAULT 'ER',  -- 'ER' | 'RE'
    -- v0.6.3e : métadonnées préservées par ecrire_notions depuis le scanner
    niveau           TEXT NOT NULL DEFAULT '',
    sequence         TEXT NOT NULL DEFAULT '',
    num_connaissance TEXT NOT NULL DEFAULT '',
    fichier          TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_notions_niv_seq ON notions (niveau, sequence);
CREATE INDEX IF NOT EXISTS idx_notions_fichier ON notions (fichier);

-- ── Méthodes ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS methodes (
    id             TEXT PRIMARY KEY,
    titre          TEXT NOT NULL DEFAULT '',
    corps          TEXT NOT NULL DEFAULT '',
    fin_cycle      TEXT NOT NULL DEFAULT 'N',  -- 'O' | 'N'
    ordre_sections TEXT NOT NULL DEFAULT 'ER',
    -- v0.6.3e : métadonnées préservées par ecrire_methodes depuis le scanner.
    -- num_methode = ordre dans la séquence (1, 2, 3…)
    -- num_objectif = code d'objectif porté par la méthode (encode le rang).
    niveau         TEXT NOT NULL DEFAULT '',
    sequence       TEXT NOT NULL DEFAULT '',
    num_methode    INTEGER,
    num_objectif   TEXT NOT NULL DEFAULT '',
    fichier        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_methodes_niv_seq ON methodes (niveau, sequence);
CREATE INDEX IF NOT EXISTS idx_methodes_fichier ON methodes (fichier);

-- Notions associées à une méthode (M:N ordonnée)
CREATE TABLE IF NOT EXISTS methode_notions (
    methode_id TEXT NOT NULL REFERENCES methodes(id) ON DELETE CASCADE,
    notion_id  TEXT NOT NULL REFERENCES notions(id) ON DELETE CASCADE,
    ordre      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (methode_id, notion_id)
);

-- ── Objectifs ────────────────────────────────────────────────────────────────
-- v0.14.7 — Renommage de `objectifs_v2` → `objectifs` après que
-- l'ancienne table v1 a été supprimée en v0.14.6.b.2. La déclaration
-- `CREATE TABLE objectifs` est plus haut dans ce schéma (section
-- modèle séquences-par-niveau).
--
-- Historique : la table v1 avait pour colonnes
--   id, methode_id, code, critere_F/A/E, niveau, sequence, nom,
--   est_nouveau (abandonné, remplacé par les précédences inter-parties),
--   obj_precedent_id (abandonné, idem).
-- Chronologie : v0.14.5 (audit) → v0.14.6.a (migration v1→v2) →
-- v0.14.6.b.1 (réécriture services) → v0.14.6.b.2 (DROP v1) →
-- v0.14.7 (renommage cosmétique).

-- ── Exercices ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS exercices (
    id         TEXT PRIMARY KEY,
    serie      TEXT NOT NULL,              -- 'fondamental' | 'avancé' | 'exploration' | 'approche'
    -- v0.13.6.12 — Renommé : `nom` → `titre` pour uniformiser avec les autres
    -- atomes (notion, méthode, fiche). La couche LaTeX (génération + scan)
    -- continue d'utiliser l'option `nom=` du paquet `seqExercice` — c'est
    -- une frontière de mapping explicite, pas un retour en arrière.
    titre      TEXT NOT NULL DEFAULT '',
    variables  TEXT NOT NULL DEFAULT '',   -- bloc _param.tex (xintexpr), compilé séparément
    enonce     TEXT NOT NULL DEFAULT '',
    corrige    TEXT NOT NULL DEFAULT '',
    -- v0.6.3e : métadonnées préservées par ecrire_exercices depuis le scanner.
    -- serie_code = code court 'F' | 'A' | 'E' | 'AE' (pour résolution livret).
    niveau     TEXT NOT NULL DEFAULT '',
    sequence   TEXT NOT NULL DEFAULT '',
    num        INTEGER,
    serie_code TEXT NOT NULL DEFAULT '',
    fichier    TEXT NOT NULL DEFAULT '',
    -- v0.11.6 — Remédiation et cadre de réponse.
    -- remed_enonce / remed_corrige : section optionnelle. Chaîne vide si
    -- l'exercice n'a pas de remédiation. Côté génération de livret, le
    -- bloc \seqRemediation n'est émis que si remed_enonce != ''.
    -- Côté UI, le cadre Remédiation n'est affiché que pour les exercices
    -- de série F et A (cf. mémoire #19), pas pour E.
    -- cadre_reponse_lignes_principal / cadre_reponse_lignes_remed :
    -- 0 = pas de cadre de réponse, sinon hauteur en lignes (1-99).
    -- À la compilation, \seqCadreReponse{N} est émis après l'énoncé
    -- (placement validé v0.11.6 Q1 option A).
    remed_enonce                    TEXT NOT NULL DEFAULT '',
    remed_corrige                   TEXT NOT NULL DEFAULT '',
    cadre_reponse_lignes_principal  INTEGER NOT NULL DEFAULT 0,
    cadre_reponse_lignes_remed      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_exercices_niv_seq ON exercices (niveau, sequence, num);
CREATE INDEX IF NOT EXISTS idx_exercices_fichier ON exercices (fichier);

-- Lien M:N exercice ↔ objectifs
-- v0.14.6.b.2 — Table `exercice_objectifs` (v1) SUPPRIMÉE. Remplacée par
-- `objectif_exos` (v2, déclarée plus bas) qui porte en plus les
-- attributs `serie` et `ordre` (utiles pour l'ordre de présentation
-- dans les livrets). Voir l'historique du chantier v0.14.6.b dans
-- doc/redemarrage_v0_14_6_b2.md.

-- ── Livrets de séquence ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS livrets_de_sequence (
    id       TEXT PRIMARY KEY,
    niveau   TEXT NOT NULL,
    sequence TEXT NOT NULL,  -- 'S01', 'S03'…
    contenu  TEXT NOT NULL DEFAULT '{}'  -- snapshot JSON du YAML courant
);
CREATE INDEX IF NOT EXISTS idx_livrets
    ON livrets_de_sequence (niveau, sequence);

-- Affectation ordonnée des exercices dans un livret
-- v0.14.6.b.2 — Table `livret_exercices` SUPPRIMÉE. Cette table était
-- écrite par `ecrire_livrets_importes` (chaîne d'import legacy via
-- `scanner_vers_v2.py`) mais n'était lue par aucun service productif —
-- son rôle d'origine (numéro d'ordre des exos dans un livret imprimé)
-- est désormais assuré par `objectif_exos` (v2) qui porte `ordre`.
-- La suppression est sans risque puisque le code la lisant
-- (`scanner_vers_v2.py`) est lui-même supprimé en v0.14.6.b.2.

-- v0.6.3e : révisions d'un livret (exercices hérités du niveau N-1)
-- Peuplée par ecrire_livrets_importes depuis prerequis.exercices_revision.
-- Les exercices de révision ne sont pas forcément présents en base comme
-- exercices (ils appartiennent à un autre niveau), on stocke donc les
-- coordonnées métier plutôt qu'un FK vers exercices.id.
CREATE TABLE IF NOT EXISTS livret_revisions (
    livret_id     TEXT NOT NULL REFERENCES livrets_de_sequence(id) ON DELETE CASCADE,
    niveau_source TEXT NOT NULL,        -- 'N10' lorsque N11 révise N10
    seq_source    TEXT NOT NULL,        -- 'S03'
    serie         TEXT NOT NULL,        -- 'fondamental' | 'avancé' | 'exploration'
    num           INTEGER NOT NULL,     -- n° de l'exercice dans sa série source
    ordre         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (livret_id, niveau_source, seq_source, serie, num)
);

-- ── Référentiels versionnés ──────────────────────────────────────────────────
-- Un référentiel fige la structure pédagogique d'un niveau à un instant donné :
-- liste des séquences, objectifs, thèmes, critères d'évaluation.
-- Un référentiel devient immuable dès qu'une classe l'a utilisé pour évaluer
-- des élèves (verrouille=1), afin de garantir la stabilité de l'historique.
--
-- v0.13.5.1 : 5 états dans le cycle de vie (en_cours → valide → fige →
-- verrouille, plus annule pour les coquilles écartées au figeage).
-- Cf. doc/scoping_v0_13_5_referentiels.md.

-- v0.15.3 — Cycle de vie révisé : en_cours → valide → verrouille → utilise
-- avec annule (concurrents écartés au verrouillage d'un autre).
-- `fige` (intermédiaire entre valide et verrouille en v0.13.5+) a été
-- fusionné dans `verrouille`. `utilise` est nouveau (référentiel associé
-- à ≥1 progression). Migration assurée par
-- persistence.sqlite_store._migrer_schema_post_ddl (idempotente).
-- Cf. doc/scoping_v0_13_5_referentiels.md + doc/redemarrage_v0_15_3.md.

CREATE TABLE IF NOT EXISTS referentiel_niveaux (
    id           TEXT PRIMARY KEY,       -- '2025_N11', '2025_N11b'…
    niveau       TEXT NOT NULL,          -- 'N10', 'N11', 'N12'
    version      TEXT NOT NULL,          -- '2025', '2025b'… (ANNÉE + suffixe)
    date_debut   TEXT,                   -- 'AAAA-MM-JJ', posée au verrouillage
    date_fin     TEXT,                   -- NULL = courant ; posée auto si remplacé
    description  TEXT NOT NULL DEFAULT '',
    etat         TEXT NOT NULL DEFAULT 'en_cours'
                 CHECK (etat IN ('en_cours', 'valide', 'verrouille',
                                 'utilise', 'annule')),
    UNIQUE (niveau, version)
);
CREATE INDEX IF NOT EXISTS idx_referentiel_niveau ON referentiel_niveaux (niveau);

CREATE TABLE IF NOT EXISTS referentiel_themes (
    referentiel_id TEXT NOT NULL REFERENCES referentiel_niveaux(id) ON DELETE CASCADE,
    code           TEXT NOT NULL,        -- 'A', 'B', 'C'…
    nom            TEXT NOT NULL,        -- 'Nombres et Calculs'
    couleur        TEXT NOT NULL DEFAULT '',  -- slug de couleur, libre
    PRIMARY KEY (referentiel_id, code)
);

CREATE TABLE IF NOT EXISTS referentiel_sequences (
    referentiel_id TEXT NOT NULL REFERENCES referentiel_niveaux(id) ON DELETE CASCADE,
    code           TEXT NOT NULL,        -- 'S01', 'S14'…
    numero         INTEGER NOT NULL,
    nom            TEXT NOT NULL,
    theme_code     TEXT,                 -- FK composite sur referentiel_themes
    PRIMARY KEY (referentiel_id, code),
    FOREIGN KEY (referentiel_id, theme_code)
        REFERENCES referentiel_themes (referentiel_id, code)
        ON DELETE SET NULL
);

-- v0.13.5.1 : parties de séquence figées (servent de support aux créneaux
-- dans les progressions). Peuplé au figeage, vide en phase coquille.
CREATE TABLE IF NOT EXISTS referentiel_parties (
    referentiel_id   TEXT NOT NULL,
    seq_code         TEXT NOT NULL,
    numero           INTEGER NOT NULL,
    nb_seances_R_AE  REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (referentiel_id, seq_code, numero),
    FOREIGN KEY (referentiel_id, seq_code)
        REFERENCES referentiel_sequences (referentiel_id, code)
        ON DELETE CASCADE
);

-- v0.13.5.1 : objectifs avec rattachement à une partie (pour les
-- progressions) et nb_seances. Les colonnes partie_numero et nb_seances
-- sont ajoutées en migration post-DDL pour les BDD existantes.
CREATE TABLE IF NOT EXISTS referentiel_objectifs (
    referentiel_id TEXT NOT NULL,
    seq_code       TEXT NOT NULL,
    code           TEXT NOT NULL,        -- '01', '02', '11', '12'…
    nom            TEXT NOT NULL,
    fin_cycle      INTEGER NOT NULL DEFAULT 0,
    critere_f      TEXT NOT NULL DEFAULT '',
    critere_a      TEXT NOT NULL DEFAULT '',
    critere_e      TEXT NOT NULL DEFAULT '',
    partie_numero  INTEGER NOT NULL DEFAULT 1,  -- v0.13.5.1
    nb_seances     REAL NOT NULL DEFAULT 0,     -- v0.13.5.1
    PRIMARY KEY (referentiel_id, seq_code, code),
    FOREIGN KEY (referentiel_id, seq_code)
        REFERENCES referentiel_sequences (referentiel_id, code)
        ON DELETE CASCADE
);

-- v0.13.5.1 : liste des exos rattachés aux objectifs (pour le suivi des
-- cases cochées). Liste seule — le contenu des exos est figé par les PDF
-- au figeage. Peuplée au figeage, vide en phase coquille.
CREATE TABLE IF NOT EXISTS referentiel_obj_exos (
    referentiel_id  TEXT NOT NULL,
    seq_code        TEXT NOT NULL,
    obj_code        TEXT NOT NULL,
    serie           TEXT NOT NULL,        -- 'F', 'A', 'E'
    num             INTEGER NOT NULL,
    ordre           INTEGER NOT NULL,
    -- Origine en cas d'exo emprunté (R notamment)
    origin_niveau   TEXT,                 -- NULL si exo natif
    origin_seq      TEXT,
    PRIMARY KEY (referentiel_id, seq_code, obj_code, serie, num),
    FOREIGN KEY (referentiel_id, seq_code, obj_code)
        REFERENCES referentiel_objectifs (referentiel_id, seq_code, code)
        ON DELETE CASCADE
);

-- ── Documents publiables d'un référentiel (v0.13.6.4) ────────────────────────
-- Catalogue par référentiel des 9 types de documents qu'il peut publier
-- (livret_sequence, livret_exercices, livret_cours, livret_fiches,
-- livret_plans, livret_corriges, evaluation, livret_cartes_recap,
-- livret_cartes_planches). Chaque entrée porte ses options sérialisées en
-- JSON et un statut de compilation (colonnes `compile_*` ajoutées en
-- v0.13.6.5.1). L'UNIQUE (referentiel_id, type_document) garantit qu'il
-- n'existe qu'une seule entrée par couple. La CHECK fige la liste des
-- types autorisés. La FK ON DELETE CASCADE assure que la suppression
-- d'un référentiel emporte ses documents.

CREATE TABLE IF NOT EXISTS referentiel_documents (
    id              TEXT PRIMARY KEY,         -- 'rd_xxx'
    referentiel_id  TEXT NOT NULL
                    REFERENCES referentiel_niveaux(id) ON DELETE CASCADE,
    type_document   TEXT NOT NULL,
    options         TEXT NOT NULL DEFAULT '{}',  -- JSON
    ordre           INTEGER NOT NULL DEFAULT 0,
    mtime           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- v0.13.6.5.1 : statut de la dernière compilation.
    -- compile_ok      : 1 = succès, 0 = échec, NULL = jamais compilé
    -- compile_date    : timestamp de la dernière tentative
    -- compile_log     : JSON détaillant la compilation (cibles, retours…)
    -- compile_en_cours: 1 si une compilation est en cours, 0 sinon
    --                  (verrou + auto-reset par sqlite_store au démarrage)
    compile_ok       INTEGER,
    compile_date     DATETIME,
    compile_log      TEXT,
    compile_en_cours INTEGER NOT NULL DEFAULT 0,
    UNIQUE (referentiel_id, type_document),
    CHECK (type_document IN (
        'livret_sequence', 'livret_exercices', 'livret_cours',
        'livret_fiches', 'livret_plans', 'livret_corriges',
        'evaluation', 'livret_cartes_recap', 'livret_cartes_planches'
    ))
);

CREATE INDEX IF NOT EXISTS idx_referentiel_documents_referentiel_id
    ON referentiel_documents(referentiel_id);

-- ── Établissements ───────────────────────────────────────────────────────────
-- Un établissement = collège, lycée, etc. Identifié par un UUID opaque.
-- Les méta (académie, ville…) peuvent être saisies à la main (état='propose')
-- ou validées via l'annuaire de l'Éducation Nationale par UAI (état='valide').
--
-- L'académie est la source de vérité pour déterminer la zone de vacances
-- scolaires (A/B/C) via le mapping ACADEMIE_ZONE défini dans
-- services/calendrier_scolaire.py.

CREATE TABLE IF NOT EXISTS etablissements (
    id        TEXT PRIMARY KEY,      -- 'et_xxxxxxxx'
    nom       TEXT NOT NULL,
    uai       TEXT,                   -- code UAI (optionnel, renseigné lors de la validation)
    academie  TEXT NOT NULL DEFAULT '',   -- ex: 'Rennes'
    ville     TEXT NOT NULL DEFAULT '',
    adresse   TEXT NOT NULL DEFAULT '',
    etat      TEXT NOT NULL DEFAULT 'propose' CHECK (etat IN ('propose','valide')),
    UNIQUE (nom)
);

-- ── Cache API externes ───────────────────────────────────────────────────────
-- Cache pour les appels aux API publiques (vacances scolaires, jours fériés,
-- annuaire des établissements). Évite les appels répétés pour des données
-- stables.
-- Clé : 'vacances:<zone>:<annee_scolaire>' | 'feries:<annee>' | 'annuaire:<uai>'
-- Payload : JSON de la réponse API.

CREATE TABLE IF NOT EXISTS cache_api (
    cle         TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    fetched_at  TEXT NOT NULL      -- ISO 8601
);

-- ── Progressions ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS progressions (
    id               TEXT PRIMARY KEY,              -- UUID opaque 'pg_xxx'
    niveau           TEXT NOT NULL,
    annee            TEXT NOT NULL,
    etablissement_id TEXT NOT NULL REFERENCES etablissements(id) ON DELETE RESTRICT,
    referentiel_id   TEXT REFERENCES referentiel_niveaux(id) ON DELETE RESTRICT,
    -- v0.19.0 : colonne `source` supprimée (aucune distinction entre
    -- progressions) ; état `annule` ajouté (suppression logique).
    etat             TEXT NOT NULL DEFAULT 'en_cours'
                          CHECK (etat IN ('en_cours','valide','verrouille','annule')),
    -- Clé métier : une seule progression par (niveau, année, établissement).
    UNIQUE (niveau, annee, etablissement_id)
);

-- Un créneau = bloc calendaire sur une tranche d'objectifs d'une séquence.
-- Convention : partie 1 → objectifs 01–09, partie 2 → objectifs 11–19, etc.
-- Les objectifs du créneau se déduisent mécaniquement : code BETWEEN partie*10-9 AND partie*10-1
-- (partie 1 : 01–09, partie 2 : 11–19, partie 3 : 21–29…)
-- Un créneau = bloc calendaire couvrant partie_debut à partie_fin d'une séquence.
-- partie 1 → objectifs 01–09, partie 2 → objectifs 11–19, partie 3 → objectifs 21–29.
-- partie_debut = partie_fin dans le cas usuel (1 partie = 1 créneau).
-- L'enseignant peut regrouper plusieurs parties consécutives dans un seul créneau.
CREATE TABLE IF NOT EXISTS creneaux (
    id                    TEXT PRIMARY KEY,
    progression_id        TEXT NOT NULL REFERENCES progressions(id) ON DELETE CASCADE,
    seq_code              TEXT NOT NULL,
    partie_debut          INTEGER NOT NULL DEFAULT 1,
    partie_fin            INTEGER NOT NULL DEFAULT 1,
    partie                TEXT,          -- libellé affiché : '1re partie', '2e partie'…
    periode               TEXT,          -- 'Sem1' | 'Sem2' | 'FinAnnee'
    date_debut            TEXT,          -- 'AAAA-MM-JJ'
    date_fin              TEXT,
    revisions             TEXT,          -- liste libre d'exercices : '1,2,3,4,5'
    ordre                 INTEGER NOT NULL DEFAULT 0,
    -- v0.6.3f — édition de progression : nombres de séances (demi-séances autorisées)
    nb_seances_total      REAL NOT NULL DEFAULT 0,
    nb_seances_revisions  REAL NOT NULL DEFAULT 0,
    nb_seances_cours      REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_creneaux_progression
    ON creneaux (progression_id, ordre);
CREATE INDEX IF NOT EXISTS idx_creneaux_seq
    ON creneaux (progression_id, seq_code, partie_debut);

-- Exercices par objectif dans un créneau (pour génération du plan de travail)
-- obj_code : '02', '03'… (pas '01' qui a des cases fixes cours/fiches/oral)
CREATE TABLE IF NOT EXISTS creneau_objectifs_exos (
    creneau_id  TEXT NOT NULL REFERENCES creneaux(id) ON DELETE CASCADE,
    obj_code    TEXT NOT NULL,   -- ex: '02', '12'
    exos_F      TEXT NOT NULL DEFAULT '',   -- ex: '1,2,3'
    exos_A      TEXT NOT NULL DEFAULT '',
    exos_E      TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (creneau_id, obj_code)
);

-- v0.6.3f — nb de séances par objectif dans un créneau
-- (0,5 séance est courant dans les plans de travail réels)
CREATE TABLE IF NOT EXISTS creneau_objectifs_seances (
    creneau_id  TEXT NOT NULL REFERENCES creneaux(id) ON DELETE CASCADE,
    obj_code    TEXT NOT NULL,
    nb_seances  REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (creneau_id, obj_code)
);

-- ── Versions de livrets ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS versions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    niveau   TEXT NOT NULL,
    seq_code TEXT NOT NULL,
    tag      TEXT NOT NULL,
    label    TEXT NOT NULL DEFAULT '',
    date     TEXT NOT NULL DEFAULT '',
    contenu  TEXT NOT NULL DEFAULT '{}',  -- snapshot JSON figé, jamais modifié
    UNIQUE (niveau, seq_code, tag)
);

-- Version active par classe × séquence, avec verrouillage
CREATE TABLE IF NOT EXISTS versions_classes (
    classe_id  TEXT NOT NULL,
    niveau     TEXT NOT NULL,
    seq_code   TEXT NOT NULL,
    tag_actif  TEXT,
    verrouille INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (classe_id, niveau, seq_code)
);

-- ── Classes et élèves ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS classes (
    id               TEXT PRIMARY KEY,             -- UUID opaque 'cl_xxx'
    nom              TEXT NOT NULL,
    niveau           TEXT NOT NULL,
    annee            TEXT NOT NULL DEFAULT '',
    etablissement_id TEXT NOT NULL REFERENCES etablissements(id) ON DELETE RESTRICT,
    progression_id   TEXT REFERENCES progressions(id) ON DELETE SET NULL,
    -- Clé métier : une seule classe par (nom, année, établissement).
    UNIQUE (nom, annee, etablissement_id)
);
CREATE INDEX IF NOT EXISTS idx_classes_annee
    ON classes (annee, etablissement_id);

CREATE TABLE IF NOT EXISTS eleves (
    id     TEXT PRIMARY KEY,
    nom    TEXT NOT NULL,
    prenom TEXT NOT NULL
);

-- Relation élève ↔ classe avec dates (gestion des changements en cours d'année)
-- date_entree et date_sortie NULL = toujours dans la classe depuis le début
CREATE TABLE IF NOT EXISTS eleves_classes (
    eleve_id    TEXT NOT NULL REFERENCES eleves(id) ON DELETE CASCADE,
    classe_id   TEXT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    date_entree TEXT,  -- 'AAAA-MM-JJ', NULL si depuis la rentrée
    date_sortie TEXT,  -- 'AAAA-MM-JJ', NULL si toujours présent
    PRIMARY KEY (eleve_id, classe_id)
);
CREATE INDEX IF NOT EXISTS idx_eleves_classes_classe
    ON eleves_classes (classe_id, date_sortie);  -- filtre les élèves actifs

-- ── Suivi ────────────────────────────────────────────────────────────────────

-- Exercices cochés
-- creneau_id peut être NULL pour les imports sans progression définie
CREATE TABLE IF NOT EXISTS suivi (
    classe_id  TEXT NOT NULL,   -- dénormalisé pour requêtes rapides
    seq_code   TEXT NOT NULL,   -- dénormalisé
    creneau_id TEXT REFERENCES creneaux(id) ON DELETE CASCADE,
    eleve_id   TEXT NOT NULL,
    serie      TEXT NOT NULL,   -- 'F' | 'A' | 'E' | 'cours'
    num        INTEGER NOT NULL,
    PRIMARY KEY (classe_id, seq_code, eleve_id, serie, num)
);
CREATE INDEX IF NOT EXISTS idx_suivi_classe  ON suivi (classe_id);
CREATE INDEX IF NOT EXISTS idx_suivi_creneau ON suivi (creneau_id);

-- Niveaux de maîtrise atteints
-- v0.14.6.b.2 — colonne `objectif_id` retirée (référait à `objectifs` v1
-- avec ON DELETE SET NULL ; lecture confirmée nulle part en prod). Le
-- rattachement à l'objectif passe désormais exclusivement par
-- `obj_code` (dénormalisé), conforme aux usages réels du code.
-- creneau_id peut être NULL pour les imports sans référentiel
CREATE TABLE IF NOT EXISTS niveaux (
    classe_id   TEXT NOT NULL,  -- dénormalisé
    seq_code    TEXT NOT NULL,  -- dénormalisé
    eleve_id    TEXT NOT NULL,
    obj_code    TEXT NOT NULL,  -- dénormalisé ('01', '02'…)
    creneau_id  TEXT REFERENCES creneaux(id) ON DELETE SET NULL,
    niveau_code TEXT NOT NULL,
    PRIMARY KEY (classe_id, seq_code, eleve_id, obj_code)
);
CREATE INDEX IF NOT EXISTS idx_niveaux_classe  ON niveaux (classe_id);
CREATE INDEX IF NOT EXISTS idx_niveaux_creneau ON niveaux (creneau_id);

-- ── v0.10.4 — État d'édition des atomes ─────────────────────────────────────
--
-- Modèle simple : chaque atome (notion, méthode, exercice, et bientôt fiche
-- de résumé) porte un code d'état d'édition. L'unique état "final" (celui
-- qui débloque la génération de référentiels/PDF "définitifs") est `valide`.
--
-- Liste extensible : pour ajouter `archive`, `obsolete`, `a_revoir` plus
-- tard, faire INSERT ... ON CONFLICT IGNORE dans cette table. Aucun
-- changement de schéma requis.
--
-- Les transitions sont manuelles (clic dans l'atelier), pas de
-- machine à états formelle — l'enseignant assume la responsabilité des
-- transitions et de la cohérence du contenu vs statut.

CREATE TABLE IF NOT EXISTS etats_edition (
    code      TEXT PRIMARY KEY,
    nom       TEXT NOT NULL,
    ordre     INTEGER NOT NULL DEFAULT 0,
    -- est_final = 1 → état qui autorise la génération du livret en mode
    -- "définitif" (sans filigrane ÉPREUVE). Convention : exactement un
    -- état avec est_final=1 dans le système (à un moment donné).
    est_final INTEGER NOT NULL DEFAULT 0
);

-- Seed des 2 états initiaux. INSERT OR IGNORE pour idempotence.
-- Si Laurent veut ajouter d'autres états (archive, etc.), il fera des
-- INSERT directs en BDD ou via une UI future.
INSERT OR IGNORE INTO etats_edition (code, nom, ordre, est_final) VALUES
    ('en_cours', 'En cours',  10, 0),
    ('valide',   'Validé',    20, 1);

-- Note : la colonne etat_code des tables atomes (notions, methodes,
-- exercices, fiches_resume) est ajoutée par le script de migration
-- 16_etat_edition.py au démarrage. SQLite n'autorise pas ADD COLUMN
-- IF NOT EXISTS, donc on ne peut pas mettre les ALTER directement ici.

-- ── v0.10.5 — Fiches de résumé ──────────────────────────────────────────────
--
-- Modèle :
--   - 1 fiche = 1 méthode = 1 objectif (cardinalité 1-1, Q3-1).
--   - L'objectif lié donne accès au niveau et à la séquence (jointure).
--   - Les sections sont stockées dans la table universelle `atome_sections`
--     avec entite_type='fiche_resume', réutilisant le pattern notion/méthode.
--   - num_fiche : numérotation par séquence (Q3-3), gérée côté service.
--   - etat_code : réutilise le mécanisme v0.10.4 (en_cours / valide).
--
-- Lien fiche → objectif Connaître (pour l'inclusion dans le livret) :
--   table de jointure objectif_fiches (Q3-4/5/6). Une fiche peut être
--   "droppée" sur un ou plusieurs objectifs Connaître ; en pratique c'est
--   1-1 dans le même partie de séquence, mais on n'impose pas la contrainte
--   en BDD.
CREATE TABLE IF NOT EXISTS fiches_resume (
    id           TEXT PRIMARY KEY,
    titre        TEXT NOT NULL DEFAULT '',
    -- v0.10.5 : la fiche pointe vers objectifs (modèle de l'atelier
    -- d'assemblage) et non vers la table legacy `objectifs`. Permet de
    -- résoudre la partie de séquence via une jointure simple.
    objectif_id  TEXT REFERENCES objectifs(id) ON DELETE SET NULL,
    num_fiche    INTEGER,
    -- Métadonnées dénormalisées (cohérence avec notions/methodes/exercices) :
    -- alimentées au moment de l'écriture pour permettre les requêtes par
    -- (niveau, sequence) sans jointure.
    niveau       TEXT NOT NULL DEFAULT '',
    sequence     TEXT NOT NULL DEFAULT '',
    fichier      TEXT NOT NULL DEFAULT '',
    etat_code    TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE INDEX IF NOT EXISTS idx_fiches_resume_objectif
    ON fiches_resume (objectif_id);
CREATE INDEX IF NOT EXISTS idx_fiches_resume_niveau_seq
    ON fiches_resume (niveau, sequence);

-- Une fiche ne peut être attachée qu'une seule fois à un objectif donné
-- (pas de doublon). L'ordre permet de contrôler la position dans le
-- livret quand plusieurs fiches sont attachées au même Connaître.
CREATE TABLE IF NOT EXISTS objectif_fiches (
    objectif_id  TEXT NOT NULL REFERENCES objectifs(id) ON DELETE CASCADE,
    fiche_id     TEXT NOT NULL REFERENCES fiches_resume(id) ON DELETE CASCADE,
    ordre        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, fiche_id)
);
CREATE INDEX IF NOT EXISTS idx_objectif_fiches_fiche
    ON objectif_fiches (fiche_id);

-- ── v0.10.5.2 — Préférences utilisateur paramétrables ────────────────────────
--
-- Table générique pour les listes/valeurs paramétrables par l'utilisateur
-- depuis l'écran Préférences. Le `type` joue le rôle de discriminant pour
-- regrouper les items appartenant au même paramètre.
--
-- Usages prévus :
--   - type='titre_zone_fiche' : titres de zone proposés dans l'atelier
--     Fiche (Définition, Propriété, Méthode...). Liste extensible par
--     l'enseignant.
--   - type='chemin_donnees_sequences' : chemin du dossier de référence
--     (atomes + images). Une seule ligne par type pour ce cas.
--   - type='chemin_paquet_mise_en_forme' : idem, paquet TikZ/CSS/etc.
--
-- Pour les listes : `valeur` = libellé affichable, `ordre` = position
-- dans la liste.
-- Pour les valeurs uniques : on ignore `ordre`, `valeur` = la valeur.
CREATE TABLE IF NOT EXISTS preferences_items (
    id      TEXT PRIMARY KEY,
    type    TEXT NOT NULL,
    valeur  TEXT NOT NULL DEFAULT '',
    ordre   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_preferences_items_type
    ON preferences_items (type, ordre);

-- Seed des titres de zone fiche (Q4 v0.10.5.2). Idempotent via
-- INSERT OR IGNORE — on ne réécrase pas la liste si l'enseignant l'a
-- modifiée. Les UUID sont fixes pour stabilité du seed (ré-import
-- prévisible).
INSERT OR IGNORE INTO preferences_items (id, type, valeur, ordre) VALUES
    ('seed_tzf_definition', 'titre_zone_fiche', 'Définition', 10),
    ('seed_tzf_propriete',  'titre_zone_fiche', 'Propriété',  20),
    ('seed_tzf_methode',    'titre_zone_fiche', 'Méthode',    30);

-- ── v0.13.5.2 — Atome Évaluation ────────────────────────────────────────────
--
-- Modèle :
--   - 1 évaluation = N exercices ordonnés, attachés à un niveau (N09..N12).
--   - numero : numéro stable (jamais modifié, pour référence externe).
--   - ordre : position dans l'index (réordonnable par l'enseignant).
--   - mode_notation : note | criteres | note_criteres | aucun.
--   - afficher_bareme_dans_exos : si oui, l'option [bareme=...] est passée
--     à seqEvalExercice côté paquet, et bareme_points doit être renseigné
--     dans evaluation_exercices.
--   - item_langue_francaise : JSON {points: int} ou vide. Si non vide,
--     l'appli ajoute un \seqEvalBaremeItem en fin de bareme.
--   - etat_code : réutilise le mécanisme v0.10.4 (en_cours | valide).
--   - mtime : horodatage de dernière modification, pour le mécanisme de
--     compilation différentielle (v0.13.5.5).
--
-- Note : la colonne mtime des tables d'atomes existantes (notions,
-- methodes, exercices, fiches_resume) et la colonne type_format de la
-- table exercices sont ajoutées par la migration v0.13.5.2 au démarrage
-- (cf. SqliteStore._migrer_schema_post_ddl). SQLite n'autorise pas
-- ADD COLUMN IF NOT EXISTS, donc on ne peut pas mettre les ALTER ici.

CREATE TABLE IF NOT EXISTS evaluations (
    id                          TEXT PRIMARY KEY,
    niveau                      TEXT NOT NULL,
    numero                      INTEGER NOT NULL,
    ordre                       INTEGER NOT NULL,
    titre                       TEXT NOT NULL DEFAULT '',
    mode_notation               TEXT NOT NULL DEFAULT 'note',
    afficher_bareme_dans_exos   INTEGER NOT NULL DEFAULT 1,
    item_langue_francaise       TEXT NOT NULL DEFAULT '',
    etat_code                   TEXT NOT NULL DEFAULT 'en_cours',
    mtime                       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (niveau, numero),
    CHECK  (mode_notation IN ('note', 'criteres', 'note_criteres', 'aucun')),
    CHECK  (etat_code IN ('en_cours', 'valide')),
    CHECK  (afficher_bareme_dans_exos IN (0, 1))
);
CREATE INDEX IF NOT EXISTS idx_evaluations_niveau_ordre
    ON evaluations (niveau, ordre);

-- Liaison évaluation ↔ exercice. PK composite (evaluation_id, exercice_id) :
-- un même exo ne peut pas apparaître deux fois dans la même éval. UNIQUE
-- (evaluation_id, ordre) : pas de collision de rang dans une éval.
--
-- Les paramètres bareme_qcm_* sont sur la liaison (et non sur l'exercice
-- lui-même) parce qu'un même QCM peut avoir des barèmes différents selon
-- les évals dans lesquelles il est utilisé.
--
-- ON DELETE CASCADE côté evaluations : si on supprime une éval, ses
-- liaisons disparaissent. ON DELETE RESTRICT côté exercices : on ne
-- peut pas supprimer un exo référencé par une éval (protection
-- pédagogique, validation explicite si l'éval est en_cours/valide
-- côté service).
CREATE TABLE IF NOT EXISTS evaluation_exercices (
    evaluation_id      TEXT NOT NULL
                       REFERENCES evaluations(id) ON DELETE CASCADE,
    exercice_id        TEXT NOT NULL
                       REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre              INTEGER NOT NULL,
    bareme_points      REAL,
    bareme_qcm_ok      REAL,
    bareme_qcm_partiel REAL,
    bareme_qcm_ko      REAL,
    PRIMARY KEY (evaluation_id, exercice_id),
    UNIQUE      (evaluation_id, ordre)
);
CREATE INDEX IF NOT EXISTS idx_evaluation_exercices_eval
    ON evaluation_exercices (evaluation_id, ordre);

-- v0.13.5.2.2 — Liaison directe évaluation ↔ objectifs.
-- L'enseignant déclare manuellement quels objectifs son évaluation
-- couvre (décision pédagogique). C'est cette table qui sert ensuite
-- au tableau de bord de l'évaluation et à la génération PDF du
-- tableau `seqEvalObjectifs` (le tableau des critères de maîtrise).
-- Pas de colonne `ordre` : les objectifs sont triés par leur code
-- naturel (séquence + position dans la partie) à la lecture.
CREATE TABLE IF NOT EXISTS evaluation_objectifs (
    evaluation_id  TEXT NOT NULL
                   REFERENCES evaluations(id) ON DELETE CASCADE,
    objectif_id    TEXT NOT NULL
                   REFERENCES objectifs(id) ON DELETE RESTRICT,
    PRIMARY KEY (evaluation_id, objectif_id)
);
CREATE INDEX IF NOT EXISTS idx_evaluation_objectifs_objectif
    ON evaluation_objectifs (objectif_id);

-- ════════════════════════════════════════════════════════════════════════════
-- v0.13.6.1 — Atelier Cartes d'automatisme (refondu en v0.13.6.1.2)
-- ════════════════════════════════════════════════════════════════════════════
--
-- Système Leitner de mémorisation (5 niveaux d'enveloppes). L'atelier
-- gère le RÉFÉRENTIEL des cartes : objets génériques au niveau, attachés
-- à une séquence précise (pas d'import inter-séquence — on duplique avec
-- un nouveau code à la main si besoin).
--
-- L'appli ne suit PAS l'état des enveloppes des élèves (objet physique
-- en classe). Elle stocke en revanche les résultats d'évaluation orale
-- mensuelle (v0.13.6.4, table à venir).
--
-- Une carte peut être :
--   - 'fixe'       : recto/verso identiques pour tous les élèves
--   - 'parametree' : énoncé calculé à partir de variables xint, plusieurs
--                    variantes générées (cf. cartes_atelier_config.cle =
--                    'cartes_param_nb_uniques')
--
-- Le contenu recto/verso est du LaTeX libre — TikZ inline supporté pour
-- les figures (Pythagore, rotation, etc.). Pas de table image dédiée.
--
-- v0.13.6.1.2 — Refonte du lien : la carte pointe désormais vers UNE
-- notion OU UNE méthode (pas un objectif). Décision de scoping
-- Laurent : « pour le lien, j'aimerais qu'il pointe vers une notion ou
-- une méthode, pas un objectif. Comme on est dans une séquence précise,
-- ça réduit la liste. » Le lien unique simplifie le modèle ; si une
-- carte est transversale on duplique à la main.
--
-- Liste des types pédagogiques unifiée (v0.13.6.1.2) :
--   definition, propriete, reconnaissance, calcul, procedure
-- Indépendamment du lien (souple) : c'est à l'enseignant de juger.
CREATE TABLE IF NOT EXISTS cartes_automatisme (
    id            TEXT PRIMARY KEY,
    niveau        TEXT NOT NULL,
    sequence      TEXT NOT NULL,
    -- Numéro local à la séquence (C01 à C99 typiquement). Affiché sur
    -- la carte sous forme « S05/C03 », et dans le livret comme « C03 ».
    num           INTEGER NOT NULL,
    -- Type pédagogique : indicateur visuel sur la carte (icône/couleur).
    -- Liste unifiée v0.13.6.1.2 : indépendante du lien_type, à charge de
    -- l'enseignant de choisir la plus pertinente.
    --   - definition     : énoncé d'une définition
    --   - propriete      : énoncé d'une propriété
    --   - reconnaissance : identification d'un cas, application visuelle
    --   - calcul         : calcul à exécuter
    --   - procedure      : suite d'étapes à appliquer
    type_pedago   TEXT NOT NULL DEFAULT 'definition',
    -- Type technique de génération.
    type_tech     TEXT NOT NULL DEFAULT 'fixe',
    -- Titre de la carte (renommé depuis `nom` en v0.13.6.15 pour
    -- harmonisation avec les autres atomes — notion/methode/exercice/fiche
    -- exposent tous `titre`). Affiché côté UI (sidebar + formulaire) mais
    -- pas sur le rendu PDF de la carte (qui n'a que recto/verso).
    titre         TEXT NOT NULL DEFAULT '',
    -- Lien unique vers UNE notion OU UNE méthode. Les deux colonnes
    -- (lien_type, lien_id) doivent être cohérentes :
    --   - lien_type = 'notion'   : lien_id ∈ notions.id
    --   - lien_type = 'methode'  : lien_id ∈ methodes.id
    --   - les deux NULL          : carte non encore liée (incomplète,
    --                              ne peut pas être validée)
    -- SQLite ne supporte pas les FK conditionnelles ; on vérifie la
    -- cohérence côté service (services/cartes_automatisme.py). Pas de
    -- CASCADE sur la suppression d'une notion/méthode : on laisse le
    -- service refuser la suppression d'une notion/méthode liée à une
    -- carte (ou la mettre à NULL — décision à prendre au moment où le
    -- problème se posera réellement). En attendant : niveau alpha,
    -- pas de migration à gérer.
    lien_type     TEXT,
    lien_id       TEXT,
    -- Recto et verso : LaTeX libre. TikZ inline accepté pour les figures.
    recto         TEXT NOT NULL DEFAULT '',
    verso         TEXT NOT NULL DEFAULT '',
    -- Variables xint (pour type_tech='parametree'), même format que
    -- exercices.variables.
    variables     TEXT NOT NULL DEFAULT '',
    -- État dans le workflow pédagogique.
    etat_code     TEXT NOT NULL DEFAULT 'en_cours',
    -- Ordre dans la séquence (interface ; n'impacte pas le num qui sert
    -- de référence stable).
    ordre         INTEGER NOT NULL DEFAULT 1,
    -- Audit.
    mtime         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (niveau, sequence, num),
    CHECK  (type_pedago IN ('definition', 'propriete', 'reconnaissance',
                            'calcul', 'procedure')),
    CHECK  (type_tech IN ('fixe', 'parametree')),
    CHECK  (etat_code IN ('en_cours', 'valide')),
    CHECK  (num > 0 AND num < 100),
    -- Cohérence des colonnes de lien : soit les deux NULL (pas encore
    -- lié), soit lien_type ∈ {'notion', 'methode'} ET lien_id non vide.
    CHECK  ((lien_type IS NULL AND lien_id IS NULL)
            OR (lien_type IN ('notion', 'methode') AND lien_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_cartes_automatisme_niveau_sequence_ordre
    ON cartes_automatisme (niveau, sequence, ordre);
-- Note v0.13.6.1.2 : l'index sur (lien_type, lien_id) est créé dans
-- _migrer_schema_post_ddl (persistence/sqlite_store.py) parce qu'il
-- dépend de colonnes ajoutées en v0.13.6.1.2. Le mettre ici planterait
-- au démarrage sur une BDD existante avec l'ancien schéma cartes
-- (CREATE INDEX IF NOT EXISTS ne court-circuite pas la validation des
-- colonnes référencées).

-- Configuration de l'atelier Cartes d'automatisme.
--
-- Stockage clé/valeur générique pour les préférences globales de
-- l'atelier (pas par niveau ni par séquence). Clés v0.13.6.1 prévues :
--   - 'cartes_param_nb_uniques' : nombre de variantes générées pour
--      chaque carte paramétrée dans les planches A4 (multiple de 16,
--      défaut '16').
--   - 'badges_actifs' (v0.13.6.3) : 'oui' ou 'non' — toggle des badges
--      dans le livret d'automatismes.
--
-- Le défaut est appliqué côté service (services/cartes_automatisme.py)
-- avec un dict `DEFAULTS_CONFIG` qui sert de référence si la clé n'est
-- pas en BDD. Ça évite d'avoir à INSERT-er la valeur par défaut au
-- premier démarrage.
CREATE TABLE IF NOT EXISTS cartes_atelier_config (
    cle    TEXT PRIMARY KEY,
    valeur TEXT NOT NULL DEFAULT ''
);

-- Note v0.13.6.1.2 : la table carte_objectifs (v0.13.6.1) a été supprimée
-- du modèle. Les cartes pointent maintenant directement vers une notion
-- ou une méthode via les colonnes (lien_type, lien_id) ci-dessus. Tu es
-- en alpha (pas de migration), donc la table peut simplement être
-- droppée si elle existe encore dans une BDD existante.
