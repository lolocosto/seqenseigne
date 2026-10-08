"""
persistence/sqlite_store.py — Couche SQLite v2 pour seqenseigne.

Interface publique compatible avec les routes et services existants.
Nouvelles méthodes pour le multi-années, les atomes normalisés,
et les progressions relationnelles.

Le schéma est défini dans persistence/schema.sql.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from persistence.ids import nouveau_id_livret, nouveau_id_objectif, nouveau_id_partie


# ── Helpers ───────────────────────────────────────────────────────────────────

def _j(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)

def _uj(s: str | None, defaut: Any = None) -> Any:
    if s is None:
        return defaut
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return defaut

def _rowid() -> str:
    """
    Id interne de ligne pour les tables de détail (items_texte) qui stockent
    des sous-éléments non exposés côté API (ex: lignes d'un exemple/remarque
    d'une notion). Ce n'est pas une entité métier, donc pas de préfixe typé.
    """
    return uuid.uuid4().hex[:12]

def _rang_depuis_code(code: str) -> int:
    """'01'→1, '09'→1, '11'→2, '21'→3."""
    try:
        n = int(code)
        if n <= 0:
            return 1
        return (n - 1) // 10 + 1
    except ValueError:
        return 1


def _num_partie_depuis_code_v2(code: str) -> int | None:
    """v0.14.6.b.1 — Déduit le numéro de partie depuis le code d'objectif,
    selon la convention canonique documentée dans services/scanner_vers_v2.py :

        code '01'..'09' → partie 1
        code '11'..'19' → partie 2
        code '21'..'29' → partie 3

    Règle : num_partie = int(code[0]) + 1.

    Ne s'applique que si le code est un entier à 2 chiffres (convention
    standard du projet). Pour tout autre format (alpha, 1 ou 3 chiffres,
    ou code vide), retourne None — l'appelant doit alors décider que
    faire (ignorer / signaler).
    """
    if not isinstance(code, str) or len(code) != 2 or not code.isdigit():
        return None
    return int(code[0]) + 1


def _normaliser_nom(s: str) -> str:
    """
    Normalisation pour comparer des noms d'objectifs / séquences / thèmes
    d'un référentiel à l'autre : insensible à la casse, aux accents,
    aux ponctuations de fin, et aux espaces multiples.
    """
    import unicodedata
    if not s:
        return ""
    # Retirer les accents (décomposer, garder que les lettres de base)
    decompose = unicodedata.normalize("NFKD", s)
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    # Minuscules + strip + collapse des espaces
    lower = sans_accent.lower().strip()
    # Collapse des espaces multiples
    collapsed = " ".join(lower.split())
    # Retirer la ponctuation finale (point, virgule…)
    while collapsed and collapsed[-1] in ".,;:!?":
        collapsed = collapsed[:-1].rstrip()
    return collapsed


def _cle_referentiel(niveau: str, themes: list[dict],
                      sequences: list[dict]) -> tuple:
    """
    Construit une clé canonique comparable pour détecter les référentiels
    identiques. Voir trouver_referentiel_equivalent.
    """
    themes_set = frozenset(
        (t["code"], _normaliser_nom(t["nom"]))
        for t in themes
    )
    sequences_set = frozenset(
        (
            s["code"],
            _normaliser_nom(s["nom"]),
            s.get("theme_code", ""),
            frozenset(
                (o["code"], _normaliser_nom(o["nom"]))
                for o in s.get("objectifs", [])
            ),
        )
        for s in sequences
    )
    return (niveau, themes_set, sequences_set)


# ── Store ─────────────────────────────────────────────────────────────────────

class SqliteStore:
    """Couche de persistance SQLite pour seqenseigne."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "seqenseigne.db"
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        schema_path = Path(__file__).parent / "schema.sql"
        schema = schema_path.read_text(encoding="utf-8")
        with self._conn() as conn:
            # ── Migrations AVANT le DDL (colonnes manquantes) ─────────────────
            # Les migrations ajoutent des colonnes sur des tables existantes
            # AVANT que le DDL tente de créer des indexes sur ces colonnes.
            self._migrer_schema(conn)
            # ── DDL principal (CREATE TABLE IF NOT EXISTS) ────────────────────
            conn.executescript(schema)
            # ── Migrations APRÈS le DDL (ajouts de colonnes, etc.) ────────────
            # v0.10.4 : la colonne etat_code des tables atomes doit être
            # ajoutée APRÈS le DDL parce que les tables sont créées par lui
            # (CREATE TABLE IF NOT EXISTS). Si on essaie ALTER TABLE avant,
            # la table n'existe pas encore.
            self._migrer_schema_post_ddl(conn)
            # ── Peuplement initial v0.13.0 : param_niveaux ────────────────────
            # Si la table param_niveaux vient d'être créée et est vide, on
            # importe son contenu depuis data/param_niveaux.csv. Une fois
            # peuplée, la BDD devient maître ; les modifications ultérieures
            # passent par script CLI ou SQL direct (pas de re-synchro auto).
            self._peupler_param_niveaux_si_vide(conn)
            # ── Peuplement initial v0.19.1.16 : grille horaire par étab. ──────
            # Chaque établissement sans créneau reçoit les 8 créneaux par
            # défaut (M1..M4, S1..S4 — modèle Hautes Ourmes). Idempotent.
            self._peupler_grille_horaire_si_vide(conn)

    def _migrer_schema(self, conn):
        """Applique les migrations de schéma de manière idempotente."""
        # Lire les colonnes existantes de creneaux
        try:
            cols_rows = conn.execute("PRAGMA table_info(creneaux)").fetchall()
            cols = {r["name"] for r in cols_rows}
        except Exception:
            return  # table pas encore créée

        # Migration v1→v2 : rang → rang_debut + rang_fin
        if "rang" in cols and "rang_debut" not in cols:
            conn.execute("ALTER TABLE creneaux ADD COLUMN rang_debut INTEGER NOT NULL DEFAULT 1")
            conn.execute("ALTER TABLE creneaux ADD COLUMN rang_fin   INTEGER NOT NULL DEFAULT 1")
            conn.execute("UPDATE creneaux SET rang_debut = rang, rang_fin = rang")
            conn.commit()
            # Recharger les colonnes pour que la migration suivante les voie
            cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(creneaux)"
            ).fetchall()}

        # Migration R4c : rang_debut/rang_fin → partie_debut/partie_fin
        # Utilise RENAME COLUMN (SQLite ≥ 3.25, Python ≥ 3.9 en pratique).
        if "rang_debut" in cols and "partie_debut" not in cols:
            conn.execute(
                "ALTER TABLE creneaux RENAME COLUMN rang_debut TO partie_debut"
            )
            conn.commit()
        if "rang_fin" in cols and "partie_fin" not in cols:
            conn.execute(
                "ALTER TABLE creneaux RENAME COLUMN rang_fin TO partie_fin"
            )
            conn.commit()
        # Recharger les colonnes après le rename
        cols = {r["name"] for r in conn.execute(
            "PRAGMA table_info(creneaux)"
        ).fetchall()}

        # Migration : ajouter revisions si absent
        if "revisions" not in cols:
            try:
                conn.execute("ALTER TABLE creneaux ADD COLUMN revisions TEXT NOT NULL DEFAULT ''")
                conn.commit()
            except Exception:
                pass

        # Migration : créer creneau_objectifs_exos si absente
        conn.execute("""
            CREATE TABLE IF NOT EXISTS creneau_objectifs_exos (
                creneau_id  TEXT NOT NULL REFERENCES creneaux(id) ON DELETE CASCADE,
                obj_code    TEXT NOT NULL,
                exos_F      TEXT NOT NULL DEFAULT '',
                exos_A      TEXT NOT NULL DEFAULT '',
                exos_E      TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (creneau_id, obj_code)
            )
        """)

        # Migration : supprimer creneau_objectifs si elle traîne encore
        try:
            conn.execute("DROP TABLE IF EXISTS creneau_objectifs")
            conn.commit()
        except Exception:
            pass

        # Migration v2→v3 : ajouter referentiel_id à progressions
        try:
            prog_cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(progressions)"
            ).fetchall()}
            if prog_cols and "referentiel_id" not in prog_cols:
                conn.execute(
                    "ALTER TABLE progressions ADD COLUMN referentiel_id TEXT"
                )
                conn.commit()
        except Exception:
            pass

        # Migration v0.19.0 : retirer la colonne `source` de progressions
        # (aucune distinction entre progressions) et étendre le CHECK etat
        # avec `annule` (suppression logique). Recréation de table FK-safe :
        # créer la table neuve sous nom temporaire, copier, DROP l'ancienne,
        # RENAME — sans renommer l'ancienne d'abord (sinon les FK entrantes de
        # creneaux ET classes suivraient puis casseraient au DROP).
        try:
            prog_cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(progressions)"
            ).fetchall()}
            if prog_cols and "source" in prog_cols:
                conn.execute("PRAGMA foreign_keys = OFF")
                conn.executescript("""
                    CREATE TABLE _progressions_v19 (
                        id               TEXT PRIMARY KEY,
                        niveau           TEXT NOT NULL,
                        annee            TEXT NOT NULL,
                        etablissement_id TEXT NOT NULL REFERENCES etablissements(id) ON DELETE RESTRICT,
                        referentiel_id   TEXT REFERENCES referentiel_niveaux(id) ON DELETE RESTRICT,
                        etat             TEXT NOT NULL DEFAULT 'en_cours'
                              CHECK (etat IN ('en_cours','valide','verrouille','annule')),
                        UNIQUE (niveau, annee, etablissement_id)
                    );
                    INSERT INTO _progressions_v19
                      (id, niveau, annee, etablissement_id, referentiel_id, etat)
                    SELECT id, niveau, annee, etablissement_id, referentiel_id, etat
                      FROM progressions;
                    DROP TABLE progressions;
                    ALTER TABLE _progressions_v19 RENAME TO progressions;
                """)
                violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise RuntimeError(f"FK cassées : {violations[:3]}")
                conn.execute("PRAGMA foreign_keys = ON")
                conn.commit()
        except Exception:
            pass

        # Migration R4e4a : objectif_exos — num → origin_num + nouvelle
        # PK (objectif_id, serie, exercice_id) + nouvelle contrainte
        # UNIQUE (objectif_id, serie, ordre). Comme SQLite ne permet pas
        # de changer PK/UNIQUE via ALTER TABLE, on procède par table neuve
        # + INSERT ... SELECT + DROP + RENAME. La valeur d'ordre est
        # recalculée via ROW_NUMBER() pour satisfaire la nouvelle contrainte
        # UNIQUE (garantit un ordre dense 1, 2, 3... par (objectif, serie)
        # même si les données d'origine avaient des collisions).
        try:
            oe_cols_rows = conn.execute(
                "PRAGMA table_info(objectif_exos)"
            ).fetchall()
        except Exception:
            oe_cols_rows = []
        oe_cols = {r["name"] for r in oe_cols_rows}
        if oe_cols and "num" in oe_cols and "origin_num" not in oe_cols:
            conn.executescript("""
                CREATE TABLE objectif_exos_new (
                    objectif_id    TEXT NOT NULL
                                   REFERENCES objectifs(id) ON DELETE CASCADE,
                    serie          TEXT NOT NULL,
                    exercice_id    TEXT NOT NULL
                                   REFERENCES exercices(id) ON DELETE RESTRICT,
                    ordre          INTEGER NOT NULL DEFAULT 0,
                    origin_niveau  TEXT,
                    origin_seq     TEXT,
                    origin_serie   TEXT,
                    origin_num     INTEGER,
                    PRIMARY KEY (objectif_id, serie, exercice_id),
                    UNIQUE       (objectif_id, serie, ordre)
                );
                INSERT INTO objectif_exos_new
                    (objectif_id, serie, exercice_id, ordre,
                     origin_niveau, origin_seq, origin_serie, origin_num)
                SELECT objectif_id, serie, exercice_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY objectif_id, serie
                           ORDER BY ordre, num, exercice_id
                       ) AS ordre,
                       origin_niveau, origin_seq, origin_serie,
                       num AS origin_num
                FROM objectif_exos;
                DROP TABLE objectif_exos;
                ALTER TABLE objectif_exos_new RENAME TO objectif_exos;
                CREATE INDEX IF NOT EXISTS idx_objectif_exos_exo
                    ON objectif_exos (exercice_id);
            """)
            conn.commit()

        # ── v0.13.5.1 — Référentiels millésimés : étendre le CHECK ───────────
        # Le CHECK historique autorise 3 états (en_cours, valide, verrouille).
        # Le nouveau modèle en a 5 : ajout de `fige` et `annule`.
        # SQLite ne permettant pas de modifier un CHECK via ALTER, on
        # recrée la table : CREATE _new + INSERT … SELECT + DROP + RENAME.
        # Idempotence : on détecte la signature de l'ancien CHECK dans
        # sqlite_master.sql (présence de 'verrouille' ET absence de 'fige').
        try:
            row = conn.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name='referentiel_niveaux'"
            ).fetchone()
        except Exception:
            row = None
        ddl_actuel = (row["sql"] if row else "") or ""
        # On recrée seulement depuis le VRAI ancien schéma (3 états :
        # en_cours/valide + un 3e), reconnaissable à l'absence simultanée de
        # 'fige', 'verrouille' ET 'utilise'. Sinon (schéma déjà migré en
        # v0.13.5.1 « fige » ou en v0.15.3 « verrouille/utilise »), on ne
        # touche pas — évite de redéclencher la migration sur un schéma déjà
        # moderne (et de planter si des lignes sont déjà 'utilise').
        deja_moderne = ("'fige'" in ddl_actuel
                        or "'verrouille'" in ddl_actuel
                        or "'utilise'" in ddl_actuel)
        if ddl_actuel and not deja_moderne:
            # Les FK depuis referentiel_themes/_sequences/_objectifs et
            # progressions pointent sur referentiel_niveaux.id : on désactive
            # temporairement les FK pendant la recréation. La cohérence est
            # préservée par construction (INSERT … SELECT identique).
            # Pattern recommandé par la doc SQLite (section "Making Other
            # Kinds Of Table Schema Changes").
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.executescript("""
                CREATE TABLE referentiel_niveaux_new (
                    id           TEXT PRIMARY KEY,
                    niveau       TEXT NOT NULL,
                    version      TEXT NOT NULL,
                    date_debut   TEXT,
                    date_fin     TEXT,
                    description  TEXT NOT NULL DEFAULT '',
                    etat         TEXT NOT NULL DEFAULT 'en_cours'
                                 CHECK (etat IN ('en_cours', 'valide', 'fige',
                                                 'verrouille', 'utilise',
                                                 'annule')),
                    UNIQUE (niveau, version)
                );
                INSERT INTO referentiel_niveaux_new
                    (id, niveau, version, date_debut, date_fin,
                     description, etat)
                SELECT id, niveau, version, date_debut, date_fin,
                       description, etat
                FROM referentiel_niveaux;
                DROP TABLE referentiel_niveaux;
                ALTER TABLE referentiel_niveaux_new
                    RENAME TO referentiel_niveaux;
                CREATE INDEX IF NOT EXISTS idx_referentiel_niveau
                    ON referentiel_niveaux (niveau);
            """)
            conn.commit()
            # Vérification de la cohérence FK avant réactivation
            integrity = conn.execute("PRAGMA foreign_key_check").fetchall()
            if integrity:
                # Cas pathologique : ne devrait pas arriver puisqu'on a
                # juste recopié le contenu. On signale et on laisse les
                # FK désactivées pour ne pas tout faire crasher.
                import logging
                logging.warning(
                    "Migration v0.13.5.1 : %d violation(s) FK détectée(s) "
                    "après recréation de referentiel_niveaux : %s",
                    len(integrity), integrity,
                )
            conn.execute("PRAGMA foreign_keys = ON")

        # ── v0.15.3 — Renommage des états (fige → verrouille, +utilise) ──────
        # Le CHECK v0.13.5.1 autorise 5 états (en_cours, valide, fige,
        # verrouille, annule). En v0.15.3 le modèle a évolué :
        # - `fige` fusionné dans `verrouille` (action unique de verrouillage)
        # - nouveau `utilise` (référentiel associé à ≥1 progression)
        # Donc nouveau CHECK : (en_cours, valide, verrouille, utilise, annule).
        # Idempotence : détecter la signature `'utilise'` dans le DDL pour
        # savoir si la migration a déjà tourné.
        try:
            row = conn.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name='referentiel_niveaux'"
            ).fetchone()
        except Exception:
            row = None
        ddl_v153 = (row["sql"] if row else "") or ""
        # On recrée la table si `utilise` absent du CHECK courant.
        if ddl_v153 and "'utilise'" not in ddl_v153:
            # Étape A — Convertir les lignes `fige` en `verrouille` AVANT la
            # recréation. Sinon l'INSERT…SELECT vers la nouvelle table (qui
            # n'autorise plus `fige`) échouerait sur la CHECK constraint.
            conn.execute(
                "UPDATE referentiel_niveaux SET etat='verrouille' "
                "WHERE etat='fige'"
            )
            conn.commit()
            # Étape B — Recréation de la table avec le nouveau CHECK.
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.executescript("""
                CREATE TABLE referentiel_niveaux_v153 (
                    id           TEXT PRIMARY KEY,
                    niveau       TEXT NOT NULL,
                    version      TEXT NOT NULL,
                    date_debut   TEXT,
                    date_fin     TEXT,
                    description  TEXT NOT NULL DEFAULT '',
                    etat         TEXT NOT NULL DEFAULT 'en_cours'
                                 CHECK (etat IN ('en_cours', 'valide',
                                                 'verrouille', 'utilise',
                                                 'annule')),
                    UNIQUE (niveau, version)
                );
                INSERT INTO referentiel_niveaux_v153
                    (id, niveau, version, date_debut, date_fin,
                     description, etat)
                SELECT id, niveau, version, date_debut, date_fin,
                       description, etat
                FROM referentiel_niveaux;
                DROP TABLE referentiel_niveaux;
                ALTER TABLE referentiel_niveaux_v153
                    RENAME TO referentiel_niveaux;
                CREATE INDEX IF NOT EXISTS idx_referentiel_niveau
                    ON referentiel_niveaux (niveau);
            """)
            conn.commit()
            integrity = conn.execute("PRAGMA foreign_key_check").fetchall()
            if integrity:
                import logging
                logging.warning(
                    "Migration v0.15.3 : %d violation(s) FK détectée(s) "
                    "après recréation de referentiel_niveaux : %s",
                    len(integrity), integrity,
                )
            conn.execute("PRAGMA foreign_keys = ON")

        # ── v0.15.3 — Renommage du dossier `_fige/` en `_verrouille/` ────────
        # Si un dossier `_fige/` traîne sous un référentiel (héritage des
        # versions ≤ v0.15.2), on le renomme. La trace.json est désormais
        # dans `_verrouille/trace.json`.
        # Ne JAMAIS bloquer le démarrage sur ce renommage cosmétique.
        try:
            from pathlib import Path as _P
            racine = _P(self.data_dir) / 'referentiels'
            if racine.is_dir():
                for ref_dir in racine.iterdir():
                    if not ref_dir.is_dir():
                        continue
                    ancien = ref_dir / '_fige'
                    nouveau = ref_dir / '_verrouille'
                    if ancien.is_dir() and not nouveau.exists():
                        ancien.rename(nouveau)
        except Exception:
            pass

    def _migrer_schema_post_ddl(self, conn):
        """v0.10.4 — Migrations qui doivent tourner APRÈS le DDL principal.

        Ces migrations supposent que les tables visées sont déjà créées
        (donc soit existantes en BDD, soit créées par le CREATE TABLE
        IF NOT EXISTS qui vient juste de tourner). Utilisé pour ajouter
        des colonnes à des tables nouvellement créées.
        """
        # ── v0.10.4 — Ajout de la colonne etat_code aux tables d'atomes ──
        # Tables concernées : notions, methodes, exercices.
        # Les fiches_resume seront ajoutées plus tard (v0.10.5).
        # SQLite n'autorise pas ADD COLUMN IF NOT EXISTS, on doit donc
        # détecter explicitement la présence de la colonne.
        for table in ("notions", "methodes", "exercices"):
            try:
                cols_t = {r["name"] for r in conn.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()}
            except Exception:
                continue  # table pas encore créée (cas pathologique)
            if cols_t and "etat_code" not in cols_t:
                # Default 'en_cours' : tous les atomes existants démarrent
                # en état "en cours" — Laurent valide manuellement ensuite
                # ce qu'il considère comme prêt.
                try:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN etat_code TEXT "
                        f"NOT NULL DEFAULT 'en_cours'"
                    )
                    conn.commit()
                except Exception:
                    pass

        # ── v0.11.6 — Ajout des champs de remédiation et de cadre de réponse ──
        # à la table exercices. La remédiation est optionnelle (chaîne vide
        # si absente) et seuls les exercices de série F et A peuvent l'avoir
        # côté UI (la BDD elle, accepte tous les exos par cohérence). Les
        # cadres de réponse : 0 = pas de cadre, sinon nombre de lignes.
        try:
            cols_t = {r["name"] for r in conn.execute(
                "PRAGMA table_info(exercices)"
            ).fetchall()}
        except Exception:
            cols_t = set()
        nouvelles_colonnes_v0116 = [
            ("remed_enonce",                   "TEXT NOT NULL DEFAULT ''"),
            ("remed_corrige",                  "TEXT NOT NULL DEFAULT ''"),
            ("cadre_reponse_lignes_principal", "INTEGER NOT NULL DEFAULT 0"),
            ("cadre_reponse_lignes_remed",     "INTEGER NOT NULL DEFAULT 0"),
        ]
        for nom_col, type_col in nouvelles_colonnes_v0116:
            if cols_t and nom_col not in cols_t:
                try:
                    conn.execute(
                        f"ALTER TABLE exercices ADD COLUMN {nom_col} {type_col}"
                    )
                    conn.commit()
                except Exception:
                    pass

        # ── v0.12.0 — Plan de travail générique : nb_seances ──────────────────
        # Deux nouvelles colonnes pour porter les nombres de séances prévues
        # dans l'atelier d'assemblage de séquence-niveau, indépendamment du
        # calendrier (les colonnes nb_seances_* de la table `creneaux`
        # restent dédiées au suivi de classe).
        #
        #   sequence_parties.nb_seances_R_AE  — séances pour les exos R + AE
        #                                        d'une partie
        #   objectifs.nb_seances           — séances pour l'objectif
        #                                        (cours pour 01/11/21,
        #                                        exos F/A/E pour les autres)
        #
        # Type REAL pour permettre les demi-séances (0,5 — usage courant
        # dans les plans de travail réels). Defaut 0 = "non renseigné".
        for table, col, typ in (
            ("sequence_parties", "nb_seances_R_AE", "REAL NOT NULL DEFAULT 0"),
            ("objectifs",     "nb_seances",      "REAL NOT NULL DEFAULT 0"),
        ):
            try:
                cols_t2 = {r["name"] for r in conn.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()}
            except Exception:
                continue
            if cols_t2 and col not in cols_t2:
                try:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {col} {typ}"
                    )
                    conn.commit()
                except Exception:
                    pass

        # ── v0.16.9 — État validable de la séquence-niveau ────────────────────
        # Colonne etat_code sur sequences_par_niveau (régime mixte + verrou de
        # validation, sur le modèle des évaluations). 'en_cours' (modifiable)
        # ou 'valide' (lecture seule). Les séquences existantes démarrent
        # toutes en_cours ; Laurent valide manuellement (un hook pédagogique
        # contrôle alors la complétude, cf. services/v2_edition.py).
        try:
            cols_spn = {r["name"] for r in conn.execute(
                "PRAGMA table_info(sequences_par_niveau)"
            ).fetchall()}
        except Exception:
            cols_spn = set()
        if cols_spn and "etat_code" not in cols_spn:
            try:
                conn.execute(
                    "ALTER TABLE sequences_par_niveau ADD COLUMN etat_code "
                    "TEXT NOT NULL DEFAULT 'en_cours'"
                )
                conn.commit()
            except Exception:
                pass
        # Deux nouvelles colonnes sur `referentiel_objectifs` :
        #   partie_numero : rattachement de l'objectif à une partie de
        #                   séquence (DEFAULT 1, donnée présente dans les
        #                   tables actives via objectifs.partie_id mais
        #                   absente côté référentiel jusqu'à présent).
        #   nb_seances    : nombre de séances pour l'objectif (idem,
        #                   présent dans objectifs mais pas figé).
        # Pour les référentiels historiques (peuplés avant v0.13.5.1), les
        # valeurs par défaut s'appliquent — le contenu reste consultable
        # mais avec partie_numero=1 partout (acceptable car ces référentiels
        # sont déjà figés et leur contenu PDF fait foi).
        try:
            cols_ro = {r["name"] for r in conn.execute(
                "PRAGMA table_info(referentiel_objectifs)"
            ).fetchall()}
        except Exception:
            cols_ro = set()
        if cols_ro and "partie_numero" not in cols_ro:
            try:
                conn.execute(
                    "ALTER TABLE referentiel_objectifs "
                    "ADD COLUMN partie_numero INTEGER NOT NULL DEFAULT 1"
                )
                conn.commit()
            except Exception:
                pass
        if cols_ro and "nb_seances" not in cols_ro:
            try:
                conn.execute(
                    "ALTER TABLE referentiel_objectifs "
                    "ADD COLUMN nb_seances REAL NOT NULL DEFAULT 0"
                )
                conn.commit()
            except Exception:
                pass

        # ── v0.13.5.2 — Atomes : ajout de mtime ────────────────────────────────
        # Horodatage de dernière modification. Sera lu par le mécanisme de
        # compilation différentielle de v0.13.5.5 pour détecter les atomes
        # modifiés depuis la dernière compilation. Les services qui modifient
        # un atome sont responsables de mettre à jour ce mtime.
        # Pour les enregistrements existants : default CURRENT_TIMESTAMP, ce
        # qui les marque comme "récemment modifiés" — le pire qui puisse
        # arriver est qu'ils soient recompilés une fois inutilement.
        for table in ("notions", "methodes", "exercices", "fiches_resume"):
            try:
                cols_t = {r["name"] for r in conn.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()}
            except Exception:
                continue
            if cols_t and "mtime" not in cols_t:
                try:
                    # SQLite n'autorise pas un default non-constant comme
                    # CURRENT_TIMESTAMP sur ADD COLUMN. On ajoute en deux
                    # temps : colonne nullable, puis UPDATE.
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN mtime DATETIME"
                    )
                    conn.execute(
                        f"UPDATE {table} SET mtime = CURRENT_TIMESTAMP "
                        f"WHERE mtime IS NULL"
                    )
                    conn.commit()
                except Exception:
                    pass

        # ── v0.13.5.2 — exercices : ajout de type_format ──────────────────────
        # Distingue les exercices "standard" (énoncé/corrigé classiques) des
        # exercices "qcm" (qui activent un rendu spécifique côté paquet).
        # Les valeurs futures pourraient inclure d'autres formats.
        try:
            cols_e = {r["name"] for r in conn.execute(
                "PRAGMA table_info(exercices)"
            ).fetchall()}
        except Exception:
            cols_e = set()
        if cols_e and "type_format" not in cols_e:
            try:
                conn.execute(
                    "ALTER TABLE exercices ADD COLUMN type_format TEXT "
                    "NOT NULL DEFAULT 'standard'"
                )
                conn.commit()
            except Exception:
                pass

        # ── v0.13.5.2.3 — Rattrapage type_format depuis l'énoncé ─────────────
        # Décision : type_format est dérivé du contenu de `enonce`. Tous les
        # exos en base ont actuellement la valeur par défaut 'standard'
        # (issue du DEFAULT de la migration v0.13.5.2 ci-dessus, ou de la
        # création initiale de la colonne pour les BDD neuves). Cette
        # migration corrige rétroactivement la valeur pour les exos qui
        # contiennent un `\begin{seqQcm}` dans leur énoncé.
        #
        # Idempotente : ne touche que les exos dont le type_format calculé
        # diffère de celui en base. Si on relance, plus rien à faire.
        #
        # Détection : LIKE '%\begin{seqQcm}%' suffit pour la BDD (pas de
        # tolérance espaces/tabs comme côté Python car la BDD contient le
        # source LaTeX réel produit par l'enseignant via l'atelier ou le
        # scanner — pas de format ambigu).
        #
        # Note : pas d'auto-correction de la BDD pour 'standard' → 'standard'
        # (no-op trivial). Seul le cas 'standard' → 'qcm' est traité ici.
        # La correction inverse 'qcm' → 'standard' (si un enseignant retire
        # un seqQcm) sera faite à la prochaine sauvegarde via l'UI.
        try:
            n_corriges = conn.execute(
                "UPDATE exercices SET type_format = 'qcm' "
                "WHERE type_format != 'qcm' "
                "  AND enonce LIKE '%\\begin{seqQcm}%'"
            ).rowcount
            if n_corriges:
                conn.commit()
        except Exception:
            pass

        # ── v0.13.6.12 — exercices : RENAME COLUMN nom → titre ───────────────
        # Uniformisation avec les autres atomes (notion, méthode, fiche) qui
        # ont déjà un champ `titre`. La colonne `exercices.nom` devient
        # `exercices.titre`. Idempotente via détection de la présence des
        # colonnes.
        #
        # Note : la couche LaTeX (scanner_latex.py, latex_rendu_atome.py,
        # livret_recap_exos.py) continue d'utiliser l'option LaTeX `nom=`
        # de `\begin{seqExercice}[nom=...]`. C'est une frontière assumée :
        # interne = `titre`, syntaxe LaTeX = `nom=`. Le mapping est explicite
        # dans les services concernés.
        try:
            cols_e = {r["name"] for r in conn.execute(
                "PRAGMA table_info(exercices)"
            ).fetchall()}
        except Exception:
            cols_e = set()
        if cols_e and "nom" in cols_e and "titre" not in cols_e:
            try:
                conn.execute("ALTER TABLE exercices RENAME COLUMN nom TO titre")
                conn.commit()
            except Exception:
                pass

        # ── v0.13.6.12 — fiches : migration one-shot des fiches sans titre ───
        # Suite à la suppression du fallback côté UI (la sidebar ne dérive
        # plus le titre depuis objectif_nom quand titre est vide), on
        # matérialise ce qui était implicite : si une fiche a titre vide,
        # on lui assigne le nom de son objectif. Idempotente : ne touche que
        # les fiches strictement vides ; les fiches avec titre saisi sont
        # préservées.
        try:
            n_migrees = conn.execute("""
                UPDATE fiches_resume
                   SET titre = (
                       SELECT COALESCE(o.nom, '')
                       FROM objectifs o
                       WHERE o.id = fiches_resume.objectif_id
                   )
                 WHERE (titre IS NULL OR titre = '')
                   AND objectif_id IS NOT NULL
                   AND EXISTS (
                       SELECT 1 FROM objectifs o
                       WHERE o.id = fiches_resume.objectif_id
                         AND o.nom IS NOT NULL AND o.nom != ''
                   )
            """).rowcount
            if n_migrees:
                conn.commit()
        except Exception:
            pass

        # ── v0.13.6.1.2 — Refonte du schéma cartes_automatisme ────────────────
        # La v0.13.6.1 stockait un type_pedago restreint à
        # {calcul_mental, methode, definition, reconnaissance} et un lien
        # many-to-many via la table carte_objectifs. La v0.13.6.1.2
        # remplace ce schéma par :
        #   - type_pedago élargi à {definition, propriete, reconnaissance,
        #     calcul, procedure}
        #   - lien direct (lien_type, lien_id) vers UNE notion OU UNE méthode
        #   - suppression de carte_objectifs
        #
        # Détection : on regarde si la colonne `lien_type` existe déjà
        # dans cartes_automatisme. Si non, on est sur l'ancien schéma et
        # on reconstruit. Stratégie : DROP + recréation in-situ (SQLite
        # ne supporte pas ALTER TABLE CHECK, et il n'y a pas de données
        # à préserver — l'atelier est en alpha, les cartes test peuvent
        # être perdues).
        try:
            cols_cartes = {r["name"] for r in conn.execute(
                "PRAGMA table_info(cartes_automatisme)"
            ).fetchall()}
        except Exception:
            cols_cartes = set()
        if cols_cartes and 'lien_type' not in cols_cartes:
            # Schéma v0.13.6.1 obsolète. On supprime et on recrée.
            # Note : c'est destructif (les cartes existantes sont perdues)
            # mais l'atelier est en alpha sans peuplement réel — Laurent
            # est prévenu via le README de v0.13.6.1.2.
            try:
                conn.execute("DROP TABLE IF EXISTS carte_objectifs")
                conn.execute("DROP TABLE IF EXISTS cartes_automatisme")
                # Le CREATE TABLE IF NOT EXISTS du schema.sql n'a pas pu
                # créer la nouvelle structure (puisque l'ancienne existait
                # déjà au moment où executescript a tourné). On exécute
                # ici le DDL de la nouvelle table en parallèle au schema
                # principal — copie minimale, à garder synchronisée avec
                # persistence/schema.sql section v0.13.6.1.2.
                conn.executescript("""
                    CREATE TABLE cartes_automatisme (
                        id            TEXT PRIMARY KEY,
                        niveau        TEXT NOT NULL,
                        sequence      TEXT NOT NULL,
                        num           INTEGER NOT NULL,
                        type_pedago   TEXT NOT NULL DEFAULT 'definition',
                        type_tech     TEXT NOT NULL DEFAULT 'fixe',
                        nom           TEXT NOT NULL DEFAULT '',
                        lien_type     TEXT,
                        lien_id       TEXT,
                        recto         TEXT NOT NULL DEFAULT '',
                        verso         TEXT NOT NULL DEFAULT '',
                        variables     TEXT NOT NULL DEFAULT '',
                        etat_code     TEXT NOT NULL DEFAULT 'en_cours',
                        ordre         INTEGER NOT NULL DEFAULT 1,
                        mtime         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (niveau, sequence, num),
                        CHECK  (type_pedago IN ('definition', 'propriete', 'reconnaissance',
                                                'calcul', 'procedure')),
                        CHECK  (type_tech IN ('fixe', 'parametree')),
                        CHECK  (etat_code IN ('en_cours', 'valide')),
                        CHECK  (num > 0 AND num < 100),
                        CHECK  ((lien_type IS NULL AND lien_id IS NULL)
                                OR (lien_type IN ('notion', 'methode')
                                    AND lien_id IS NOT NULL))
                    );
                    CREATE INDEX idx_cartes_automatisme_niveau_sequence_ordre
                        ON cartes_automatisme (niveau, sequence, ordre);
                """)
                conn.commit()
            except Exception as e:
                # On laisse remonter en log pour ne pas masquer un vrai
                # problème, mais on ne fait pas planter l'appli.
                print(f"[seqenseigne] ⚠ migration cartes v0.13.6.1.2 : {e}")

        # v0.13.6.1.2 — Index sur (lien_type, lien_id). Créé ici
        # systématiquement (et idempotent via IF NOT EXISTS) plutôt que
        # dans schema.sql, parce que sur une BDD existante avec l'ancien
        # schéma cartes, schema.sql tourne AVANT cette migration et
        # planterait. Tant qu'on est ici, la table existe avec les
        # bonnes colonnes (soit créée par schema.sql sur BDD vierge,
        # soit recréée par le bloc ci-dessus sur BDD existante).
        try:
            cols_cartes = {r["name"] for r in conn.execute(
                "PRAGMA table_info(cartes_automatisme)"
            ).fetchall()}
        except Exception:
            cols_cartes = set()
        if 'lien_type' in cols_cartes and 'lien_id' in cols_cartes:
            try:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cartes_automatisme_lien "
                    "ON cartes_automatisme (lien_type, lien_id)"
                )
                conn.commit()
            except Exception as e:
                print(f"[seqenseigne] ⚠ création index lien_type/lien_id : {e}")

        # ── v0.13.6.5.1 — referentiel_documents : colonnes compile_* ─────────
        # Les 4 colonnes compile_* ont été introduites en v0.13.6.5.1 pour
        # porter l'état de la dernière compilation d'un document publiable.
        # Pour une BDD pré-v0.13.6.5.1 dont la table referentiel_documents
        # existait déjà sans ces colonnes, on les ajoute ici via ALTER.
        # Pour une BDD neuve, le CREATE TABLE de schema.sql les a déjà
        # posées : la détection via PRAGMA évite alors le doublon.
        try:
            cols_rd = {r["name"] for r in conn.execute(
                "PRAGMA table_info(referentiel_documents)"
            ).fetchall()}
        except Exception:
            cols_rd = set()
        if cols_rd:
            nouvelles_compile = [
                ("compile_ok",       "INTEGER"),
                ("compile_date",     "DATETIME"),
                ("compile_log",      "TEXT"),
                ("compile_en_cours", "INTEGER NOT NULL DEFAULT 0"),
            ]
            for nom_col, type_col in nouvelles_compile:
                if nom_col not in cols_rd:
                    try:
                        conn.execute(
                            f"ALTER TABLE referentiel_documents "
                            f"ADD COLUMN {nom_col} {type_col}"
                        )
                        conn.commit()
                    except Exception:
                        pass

        # ── v0.13.6.5.1 — Reset des verrous compile_en_cours orphelins ───────
        # Si Flask a été interrompu pendant une compilation
        # (Ctrl+C, crash, kill), le flag compile_en_cours peut rester à 1
        # alors qu'aucun thread ne tourne. Au démarrage du store on remet
        # tous les verrous à 0 — il n'y a par construction aucune
        # compilation en cours puisqu'on est en train de démarrer.
        # Idempotent : si tout est déjà à 0, l'UPDATE est un no-op.
        try:
            conn.execute(
                "UPDATE referentiel_documents SET compile_en_cours = 0 "
                "WHERE compile_en_cours = 1"
            )
            conn.commit()
        except Exception:
            pass

        # ── v0.13.6.13 — Migration carte → objectif_cartes ────────────────────
        # Avant v0.13.6.13 : une carte portait directement (lien_type, lien_id).
        # Depuis v0.13.6.13 : on utilise la table de liaison objectif_cartes.
        #
        # Cette migration peuple objectif_cartes à partir des liens historiques :
        #   - cartes liées à une méthode → 1 ligne (méthode → 0..1 objectif via
        #     objectifs.methode_id, 1:1 strict)
        #   - cartes liées à une notion → 1 ligne PAR objectif lié à cette notion
        #     (via objectif_notions, peut être N pour une notion multi-liée)
        #   - cartes sans lien (orphelines) → 0 ligne (carte présente mais non
        #     reliée à un objectif)
        #
        # Idempotente : INSERT OR IGNORE + condition que objectif_cartes soit
        # cohérente (on n'écrase pas un lien existant). En pratique, la
        # migration ne s'exécute "réellement" que la première fois ; sur les
        # démarrages suivants tout est INSERT OR IGNORE no-op.
        #
        # ATTENTION : les colonnes lien_type/lien_id de cartes_automatisme
        # restent en place et inchangées (conservation pour rollback éventuel
        # et pour le retrait planifié en v0.14).
        try:
            # Existence des tables sources et cible
            tables_existantes = {r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            tables_requises = {
                "cartes_automatisme", "objectifs",
                "objectif_notions", "objectif_cartes"
            }
            if tables_requises.issubset(tables_existantes):
                # Cartes liées à une méthode → objectif via methode_id
                conn.execute("""
                    INSERT OR IGNORE INTO objectif_cartes (objectif_id, carte_id)
                    SELECT o.id, c.id
                      FROM cartes_automatisme c
                      JOIN methodes m
                        ON m.id = c.lien_id AND c.lien_type = 'methode'
                      JOIN objectifs o
                        ON o.methode_id = m.id
                """)
                # Cartes liées à une notion → objectif via objectif_notions
                conn.execute("""
                    INSERT OR IGNORE INTO objectif_cartes (objectif_id, carte_id)
                    SELECT on1.objectif_id, c.id
                      FROM cartes_automatisme c
                      JOIN objectif_notions on1
                        ON on1.notion_id = c.lien_id AND c.lien_type = 'notion'
                """)
                conn.commit()
        except Exception as e:
            print(f"[seqenseigne] ⚠ migration objectif_cartes : {e}")

        # ── v0.13.6.15 — Migration cartes_automatisme.nom → titre ──────────
        # Harmonisation du contrat des atomes : tous les types exposent
        # désormais `titre` (notion, methode, exercice, fiche le faisaient
        # déjà ; carte avait `nom`). Pour éliminer l'asymétrie BdD/UI
        # introduite en v0.13.6.14 (mapping côté JS), on renomme la colonne.
        #
        # Idempotente : on inspecte les colonnes via PRAGMA table_info et
        # on ne fait l'ALTER que si l'ancienne colonne `nom` existe et que
        # la nouvelle `titre` n'existe pas encore.
        try:
            cols_ca = {r["name"] for r in conn.execute(
                "PRAGMA table_info(cartes_automatisme)"
            ).fetchall()}
            if 'nom' in cols_ca and 'titre' not in cols_ca:
                conn.execute(
                    "ALTER TABLE cartes_automatisme RENAME COLUMN nom TO titre"
                )
                conn.commit()
                print("[seqenseigne] ✓ migration cartes_automatisme.nom → titre")
        except Exception as e:
            print(f"[seqenseigne] ⚠ migration cartes_automatisme.nom → titre : {e}")

        # ── v0.15.0.1 — Réconciliation objectifs ← objectifs_v2 ─────────────
        #
        # Contexte : en v0.14.7 le renommage devait être effectué par
        # `scripts/renommer_objectifs_v2.py` lancé manuellement AVANT le
        # premier démarrage post-déploiement. Si l'utilisateur lançait
        # `lancer.bat` d'abord, le `CREATE TABLE IF NOT EXISTS objectifs`
        # de schema.sql créait une table `objectifs` vide tandis que
        # `objectifs_v2` (avec les vraies données) restait intacte à côté.
        # Le script de renommage refusait ensuite de tourner (conflit
        # « la table de destination existe déjà »), laissant l'utilisateur
        # avec une table `objectifs` vide silencieusement.
        #
        # Détection : `objectifs_v2` existe ET `objectifs` est vide ET
        # `objectifs_v2` n'est pas vide → on copie. Idempotent.
        #
        # NB : la suppression définitive de `objectifs_v2` est différée
        # (dette technique). Tant que la table existe, cette migration
        # tourne au démarrage. Comme elle est idempotente et que le
        # COUNT(*) est rapide sur 245 lignes, le coût est négligeable.
        try:
            tables = {r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            if "objectifs_v2" in tables and "objectifs" in tables:
                n_actif = conn.execute(
                    "SELECT COUNT(*) AS n FROM objectifs"
                ).fetchone()["n"]
                n_v2 = conn.execute(
                    "SELECT COUNT(*) AS n FROM objectifs_v2"
                ).fetchone()["n"]
                if n_actif == 0 and n_v2 > 0:
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO objectifs "
                        "    (id, partie_id, code, nom, methode_id, "
                        "     critere_F, critere_A, critere_E, "
                        "     fin_cycle, nb_seances) "
                        "SELECT id, partie_id, code, nom, methode_id, "
                        "       critere_F, critere_A, critere_E, "
                        "       fin_cycle, nb_seances "
                        "FROM objectifs_v2"
                    )
                    conn.commit()
                    print(
                        "[seqenseigne] ✓ migration v0.15.0.1 : "
                        f"{cur.rowcount} objectif(s) reconciliés depuis "
                        "objectifs_v2 (cf. note v0.14.7 incomplète)"
                    )
        except Exception as e:
            print(f"[seqenseigne] ⚠ migration v0.15.0.1 objectifs : {e}")

        # ── v0.19.1.4 — Mode de séances + table des séances par série ─────────
        # Deux régimes de saisie des séances coexistent désormais :
        #   - 'par_objectif' (modèle courant, défaut) : nb_seances par objectif
        #     + nb_seances_R_AE par partie ;
        #   - 'par_serie' (modèle historique, ex. 2021-22) : une matrice de
        #     séances (niveau-cible × série) par (séquence, partie), sans
        #     granularité objectif.
        # Le mode est porté par le RÉFÉRENTIEL figé (decision A) ; une
        # progression hérite du mode via son referentiel_id. Les référentiels
        # existants restent 'par_objectif' (aucune régression).
        try:
            cols_rn = {r["name"] for r in conn.execute(
                "PRAGMA table_info(referentiel_niveaux)"
            ).fetchall()}
        except Exception:
            cols_rn = set()
        if cols_rn and "mode_seances" not in cols_rn:
            try:
                conn.execute(
                    "ALTER TABLE referentiel_niveaux ADD COLUMN mode_seances "
                    "TEXT NOT NULL DEFAULT 'par_objectif'"
                )
                conn.commit()
            except Exception:
                pass

        # Table des séances par série (mode 'par_serie'). Clé sur le
        # référentiel (decision B) : la matrice est figée et partagée par
        # toutes les progressions s'appuyant sur ce référentiel.
        #   niveau_cible : 'TB' (Très bon) | 'S' (Satisfaisant)
        #   serie        : 'R' (auto-éval/révisions) | 'F' | 'A' | 'E'
        # La cible 'S' n'a pas de ligne 'E' (rythme sans exploration).
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS referentiel_parties_seances (
                    referentiel_id TEXT    NOT NULL,
                    seq_code       TEXT    NOT NULL,
                    partie_numero  INTEGER NOT NULL,
                    niveau_cible   TEXT    NOT NULL,
                    serie          TEXT    NOT NULL,
                    nb_seances     REAL    NOT NULL DEFAULT 0,
                    PRIMARY KEY (referentiel_id, seq_code, partie_numero,
                                 niveau_cible, serie)
                )
            """)
            conn.commit()
        except Exception:
            pass

        # ── v0.19.1.15 — Rythme de séances par classe (semaines A/B) ──────────
        # Deux colonnes sur `classes` : nombre de séances EN CLASSE ENTIÈRE en
        # semaine A et en semaine B. Sert à projeter la progression « à la
        # séance » (mises en route / automatismes) sur le calendrier réel.
        # Pour les classes à horaire aménagé (musique/danse/cinéma), on ne
        # compte que la classe entière ; les heures en groupe (remédiation /
        # approfondissement) ne comptent pas. 0 = non renseigné.
        for col in ("seances_A", "seances_B"):
            try:
                cols_cl = {r["name"] for r in conn.execute(
                    "PRAGMA table_info(classes)"
                ).fetchall()}
            except Exception:
                cols_cl = set()
            if cols_cl and col not in cols_cl:
                try:
                    conn.execute(
                        f"ALTER TABLE classes ADD COLUMN {col} "
                        "INTEGER NOT NULL DEFAULT 0"
                    )
                    conn.commit()
                except Exception:
                    pass

        # ── v0.22.0 — Mises en route (MER) par classe ─────────────────────────
        # `mer_active` : la classe fait-elle des mises en route (0/1).
        # `mer_mode`   : 'automatismes' (Leitner) | 'progression' | 'panache'.
        # Par défaut une classe ne fait pas de MER (mer_active=0).
        try:
            cols_cl = {r["name"] for r in conn.execute(
                "PRAGMA table_info(classes)").fetchall()}
        except Exception:
            cols_cl = set()
        if cols_cl and "mer_active" not in cols_cl:
            try:
                conn.execute("ALTER TABLE classes ADD COLUMN mer_active "
                             "INTEGER NOT NULL DEFAULT 0")
                conn.commit()
            except Exception:
                pass
        if cols_cl and "mer_mode" not in cols_cl:
            try:
                conn.execute("ALTER TABLE classes ADD COLUMN mer_mode "
                             "TEXT NOT NULL DEFAULT 'automatismes'")
                conn.commit()
            except Exception:
                pass

        # ── v0.19.1.16 — Grille horaire par établissement ─────────────────────
        # Créneaux de cours communs à un collège : M1..M4 (matin), S1..S4
        # (après-midi). Paramétrage permanent, éditable par établissement (les
        # horaires varient d'un collège à l'autre). Socle de la saisie d'EDT et
        # de la projection séance→date+heure (progressions « à la séance »).
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS grille_horaire_creneaux (
                    id               TEXT    PRIMARY KEY,
                    etablissement_id TEXT    NOT NULL,
                    code             TEXT    NOT NULL,
                    libelle          TEXT    NOT NULL DEFAULT '',
                    heure_debut      TEXT    NOT NULL DEFAULT '',
                    heure_fin        TEXT    NOT NULL DEFAULT '',
                    demi_journee     TEXT    NOT NULL DEFAULT 'M',
                    ordre            INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (etablissement_id, code)
                )
            """)
            conn.commit()
        except Exception:
            pass

        # ── v0.19.1.17 — Emploi du temps de l'enseignant (année courante) ─────
        # Une ligne = une case de l'EDT : un créneau (M1..S4) un jour donné,
        # en semaine A, B ou AB (toutes semaines, défaut). `usage` distingue ce
        # qui compte pour les progressions (classe_entiere) du reste
        # (demi-classe, groupes, autres activités affichées mais non comptées).
        # Ancré sur l'année scolaire ; l'archivage des années passées (avec la
        # grille horaire figée) sera cadré ultérieurement.
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS edt_creneaux (
                    id               TEXT    PRIMARY KEY,
                    annee            TEXT    NOT NULL,
                    jour             TEXT    NOT NULL,
                    creneau_code     TEXT    NOT NULL,
                    semaine          TEXT    NOT NULL DEFAULT 'AB',
                    classe_id        TEXT,
                    etablissement_id TEXT    NOT NULL,
                    libelle          TEXT    NOT NULL DEFAULT '',
                    usage            TEXT    NOT NULL DEFAULT 'classe_entiere',
                    ordre            INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (annee, jour, creneau_code, semaine, etablissement_id)
                )
            """)
            conn.commit()
        except Exception:
            pass

        # ── v0.20.2 — Séparation groupe / usage dans l'EDT ────────────────────
        # `usage` mélangeait deux notions : à QUI on fait cours (groupe) et CE
        # qu'on fait (usage). On ajoute une colonne `groupe`. La reventilation
        # des données d'alors se faisait par un script ponctuel, supprimé en
        # v0.41.3 (obsolète depuis le schéma v0.38).
        try:
            cols_edt = {r["name"] for r in conn.execute(
                "PRAGMA table_info(edt_creneaux)").fetchall()}
            if cols_edt and "groupe" not in cols_edt:
                conn.execute(
                    "ALTER TABLE edt_creneaux ADD COLUMN groupe TEXT "
                    "NOT NULL DEFAULT 'classe_entiere'")
                conn.commit()
        except Exception:
            pass

        # ── v0.19.1.19 — Affectation des séances (mises en route / autos) ─────
        # Décide, pour chaque séance projetée, quelle activité de démarrage a
        # lieu. Deux modes par classe/année : `par_seance` (affectation case par
        # case de l'EDT, défaut) et `par_repartition` (motif cyclique). Des
        # exceptions ponctuelles (dates) forcent « aucun ».
        # Valeurs d'affectation : 'automatisme' (→ Leitner), 'progression'
        # (→ séquences de mise en route), 'aucun', ou 'mer:<id>' (étiquette
        # personnalisée référençant un preferences_items type_mise_en_route).
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS affectation_config (
                    classe_id TEXT NOT NULL,
                    annee     TEXT NOT NULL,
                    mode      TEXT NOT NULL DEFAULT 'par_seance',
                    PRIMARY KEY (classe_id, annee)
                );
                CREATE TABLE IF NOT EXISTS affectation_seance (
                    id             TEXT PRIMARY KEY,
                    classe_id      TEXT NOT NULL,
                    annee          TEXT NOT NULL,
                    edt_creneau_id TEXT NOT NULL,
                    affectation    TEXT NOT NULL DEFAULT 'aucun',
                    UNIQUE (classe_id, annee, edt_creneau_id)
                );
                CREATE TABLE IF NOT EXISTS regle_repartition (
                    classe_id TEXT NOT NULL,
                    annee     TEXT NOT NULL,
                    motif     TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (classe_id, annee)
                );
                CREATE TABLE IF NOT EXISTS affectation_exception (
                    id        TEXT PRIMARY KEY,
                    classe_id TEXT NOT NULL,
                    annee     TEXT NOT NULL,
                    date      TEXT NOT NULL,
                    motif     TEXT NOT NULL DEFAULT '',
                    UNIQUE (classe_id, annee, date)
                );
            """)
            conn.commit()
        except Exception:
            pass

        # ── v0.21.0 — Indisponibilités ────────────────────────────────────────
        # Périodes où des séances prévues à l'EDT n'ont pas lieu (surveillance
        # d'examen, sortie, journée de cohésion…). Retirent des séances du
        # planning projeté, décalant la suite. Deux granularités (seances /
        # journees) et deux portées (moi / classes).
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS indisponibilites (
                    id               TEXT PRIMARY KEY,
                    annee            TEXT NOT NULL,
                    etablissement_id TEXT NOT NULL,
                    type             TEXT NOT NULL DEFAULT 'journees',
                    date_debut       TEXT NOT NULL,
                    date_fin         TEXT NOT NULL DEFAULT '',
                    creneau_debut    TEXT NOT NULL DEFAULT '',
                    creneau_fin      TEXT NOT NULL DEFAULT '',
                    portee           TEXT NOT NULL DEFAULT 'moi',
                    classes_ids      TEXT NOT NULL DEFAULT '[]',
                    motif            TEXT NOT NULL DEFAULT ''
                );
            """)
            conn.commit()
        except Exception:
            pass

        # ── v0.21.4 — Décalages de progression par classe ─────────────────────
        # La progression est commune à un niveau/année (partagée par plusieurs
        # classes). Un décalage matérialise un glissement de dates propre à UNE
        # classe (ex. voyage scolaire d'une semaine) : « à partir de telle date,
        # tout glisse de N semaines ». Non destructif : la progression commune
        # n'est pas modifiée ; le décalage est appliqué à la volée pour la vue
        # « progression réalisée » d'une classe. Peut être lié à l'indispo qui
        # l'a motivé (indispo_id).
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS decalage_progression (
                    id          TEXT PRIMARY KEY,
                    classe_id   TEXT NOT NULL,
                    annee       TEXT NOT NULL,
                    a_partir_de TEXT NOT NULL,
                    nb_semaines INTEGER NOT NULL DEFAULT 1,
                    motif       TEXT NOT NULL DEFAULT '',
                    indispo_id  TEXT
                );
            """)
            conn.commit()
        except Exception:
            pass

        # ── v0.25.0 — Référentiels externes ───────────────────────────────────
        # Référentiels dont le contenu est conçu HORS de l'appli (docs PDF/ODT…
        # de collègues), intégrés « tels quels ». Structure légère : séquences →
        # parties (avec nb de séances) → documents attachés. Type 'mer' pour
        # l'instant (les référentiels MER sont exclusivement externes). Deux
        # états : 'en_cours' (éditable) et 'valide' (utilisable en progression).
        # Des docs peuvent être ajoutés à tout moment, même après validation.
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS referentiel_externe (
                    id      TEXT PRIMARY KEY,
                    niveau  TEXT NOT NULL,
                    annee   TEXT NOT NULL DEFAULT '',
                    type    TEXT NOT NULL DEFAULT 'mer',
                    nom     TEXT NOT NULL DEFAULT '',
                    etat    TEXT NOT NULL DEFAULT 'en_cours'
                );
                CREATE TABLE IF NOT EXISTS referentiel_externe_sequence (
                    id         TEXT PRIMARY KEY,
                    ref_ext_id TEXT NOT NULL,
                    code       TEXT NOT NULL DEFAULT '',
                    nom        TEXT NOT NULL DEFAULT '',
                    ordre      INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS referentiel_externe_partie (
                    id          TEXT PRIMARY KEY,
                    sequence_id TEXT NOT NULL,
                    numero      INTEGER NOT NULL DEFAULT 1,
                    libelle     TEXT NOT NULL DEFAULT '',
                    nb_seances  INTEGER NOT NULL DEFAULT 1,
                    ordre       INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS referentiel_externe_doc (
                    id          TEXT PRIMARY KEY,
                    partie_id   TEXT NOT NULL,
                    nom_fichier TEXT NOT NULL,
                    chemin      TEXT NOT NULL,
                    mime        TEXT NOT NULL DEFAULT '',
                    taille      INTEGER NOT NULL DEFAULT 0
                );
            """)
            conn.commit()
        except Exception:
            pass

        # ── v0.32.3 — Documents ANNUELS des référentiels externes ─────────────
        # Un doc externe est rattaché soit à une partie (doc de séquence,
        # partie_id renseigné), soit au référentiel lui-même (doc annuel,
        # ref_ext_id renseigné, partie_id vide). On ajoute la colonne ref_ext_id
        # (nullable) sans toucher aux docs de partie existants.
        try:
            cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(referentiel_externe_doc)").fetchall()}
            if cols and "ref_ext_id" not in cols:
                conn.execute("ALTER TABLE referentiel_externe_doc "
                             "ADD COLUMN ref_ext_id TEXT")
                conn.commit()
        except Exception:
            pass

        # ── v0.32.5 — Association de documents à la progression ────────────────
        # Un document (à distribuer) est associé à un point de la progression, au
        # NIVEAU (pas par classe) : (progression, type, créneau/partie, rang de
        # séance). Toutes les classes du niveau en héritent ; les décalages réels
        # restent gérés par les indisponibilités.
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS progression_doc (
                    id          TEXT PRIMARY KEY,
                    prog_kind   TEXT NOT NULL,
                    prog_ref    TEXT NOT NULL,
                    creneau_ref TEXT NOT NULL,
                    rang_seance INTEGER NOT NULL DEFAULT 1,
                    doc_source  TEXT NOT NULL,
                    doc_ref     TEXT NOT NULL,
                    doc_libelle TEXT NOT NULL DEFAULT '',
                    ordre       INTEGER NOT NULL DEFAULT 0
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_progression_doc_creneau "
                         "ON progression_doc (prog_kind, prog_ref, creneau_ref)")
            conn.commit()
        except Exception:
            pass

        # ── v0.26.0 — Progressions de mise en route (à la séance) ─────────────
        # Pendant, en séances, de la progression principale (en semaines). Une
        # progression MER par classe/année, adossée à UN référentiel MER
        # (externe pour l'instant ; interne plus tard, d'où `ref_mer_source`).
        # On y pose des parties du référentiel, dans l'ordre ; chaque partie
        # consomme son nombre de séances (lu dans le référentiel, non dupliqué).
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS progression_mer (
                    id             TEXT PRIMARY KEY,
                    niveau         TEXT NOT NULL DEFAULT '',
                    annee          TEXT NOT NULL,
                    ref_mer_id     TEXT,
                    ref_mer_source TEXT NOT NULL DEFAULT 'externe',
                    etat           TEXT NOT NULL DEFAULT 'en_cours',
                    UNIQUE (niveau, annee)
                );
                CREATE TABLE IF NOT EXISTS progression_mer_partie (
                    id                TEXT PRIMARY KEY,
                    progression_mer_id TEXT NOT NULL,
                    partie_id         TEXT NOT NULL,
                    partie_source     TEXT NOT NULL DEFAULT 'externe',
                    ordre             INTEGER NOT NULL DEFAULT 0
                );
            """)
            conn.commit()
        except Exception:
            pass

        # ── v0.27.0 — Progressions de MER PAR NIVEAU (et non plus par classe) ──
        # La v0.26.0 avait créé progression_mer avec `classe_id`. On passe à une
        # progression commune au niveau (comme la progression principale). Si
        # une base existante a encore la colonne `classe_id` sans `niveau`, on
        # recrée la table (les rares progressions par classe ne se transposent
        # pas automatiquement — l'enseignant les recompose au niveau).
        try:
            cols_pm = {r["name"] for r in conn.execute(
                "PRAGMA table_info(progression_mer)").fetchall()}
            if cols_pm and "niveau" not in cols_pm:
                conn.executescript("""
                    DROP TABLE IF EXISTS progression_mer_partie;
                    DROP TABLE IF EXISTS progression_mer;
                    CREATE TABLE progression_mer (
                        id             TEXT PRIMARY KEY,
                        niveau         TEXT NOT NULL DEFAULT '',
                        annee          TEXT NOT NULL,
                        ref_mer_id     TEXT,
                        ref_mer_source TEXT NOT NULL DEFAULT 'externe',
                        etat           TEXT NOT NULL DEFAULT 'en_cours',
                        UNIQUE (niveau, annee)
                    );
                    CREATE TABLE progression_mer_partie (
                        id                 TEXT PRIMARY KEY,
                        progression_mer_id TEXT NOT NULL,
                        partie_id          TEXT NOT NULL,
                        partie_source      TEXT NOT NULL DEFAULT 'externe',
                        ordre              INTEGER NOT NULL DEFAULT 0
                    );
                """)
                conn.commit()
        except Exception:
            pass

        # ── v0.37.0 — Salles et plans de salle versionnés ─────────────────────
        # Tables `salles`, `salle_versions`, `salle_places` (schéma porté par
        # services/salles.py). Migration additive, idempotente.
        try:
            from services.salles import SCHEMA as _SCHEMA_SALLES
            conn.executescript(_SCHEMA_SALLES)
            conn.commit()
        except Exception:
            pass

        # ── v0.38.0 — EdT versionné : périodes de validité, salle, AESH ───────
        # Chaque case porte une période [valide_du, valide_au) en lundis ISO
        # ('' = début / fin d'année). La contrainte UNIQUE historique (annee,
        # jour, creneau_code, semaine, etablissement_id) interdisait deux
        # lignes pour une même case à des périodes différentes : on reconstruit
        # la table sans elle (le non-chevauchement est contrôlé par
        # services/edt.py). + `edt_etats` : EdT « en saisie » ou « figé » par
        # (année, établissement).
        try:
            cols_edt = {r["name"] for r in conn.execute(
                "PRAGMA table_info(edt_creneaux)").fetchall()}
            if cols_edt and "valide_du" not in cols_edt:
                conn.executescript("""
                    CREATE TABLE edt_creneaux_v38 (
                        id               TEXT    PRIMARY KEY,
                        annee            TEXT    NOT NULL,
                        jour             TEXT    NOT NULL,
                        creneau_code     TEXT    NOT NULL,
                        semaine          TEXT    NOT NULL DEFAULT 'AB',
                        classe_id        TEXT,
                        etablissement_id TEXT    NOT NULL,
                        libelle          TEXT    NOT NULL DEFAULT '',
                        usage            TEXT    NOT NULL DEFAULT 'cours',
                        groupe           TEXT    NOT NULL DEFAULT 'classe_entiere',
                        ordre            INTEGER NOT NULL DEFAULT 0,
                        valide_du        TEXT    NOT NULL DEFAULT '',
                        valide_au        TEXT    NOT NULL DEFAULT '',
                        salle_id         TEXT,
                        nb_aesh          INTEGER NOT NULL DEFAULT 0
                    );
                    INSERT INTO edt_creneaux_v38
                        (id, annee, jour, creneau_code, semaine, classe_id,
                         etablissement_id, libelle, usage, groupe, ordre)
                    SELECT id, annee, jour, creneau_code, semaine, classe_id,
                           etablissement_id, libelle, usage, groupe, ordre
                    FROM edt_creneaux;
                    DROP TABLE edt_creneaux;
                    ALTER TABLE edt_creneaux_v38 RENAME TO edt_creneaux;
                """)
            conn.executescript("""
                CREATE INDEX IF NOT EXISTS idx_edt_annee_classe
                    ON edt_creneaux (annee, classe_id);
                CREATE INDEX IF NOT EXISTS idx_edt_case
                    ON edt_creneaux (annee, etablissement_id, jour, creneau_code);
                CREATE TABLE IF NOT EXISTS edt_etats (
                    annee            TEXT NOT NULL,
                    etablissement_id TEXT NOT NULL,
                    etat             TEXT NOT NULL DEFAULT 'en_saisie',
                    date_figeage     TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (annee, etablissement_id)
                );
            """)
            conn.commit()
        except Exception:
            pass

        # ── v0.39.0 — Plans de classe hebdomadaires ───────────────────────────
        # Tables `plans_classe` et `plan_placements` (schéma porté par
        # services/plans_classe.py). Migration additive, idempotente.
        try:
            from services.plans_classe import SCHEMA as _SCHEMA_PLANS
            conn.executescript(_SCHEMA_PLANS)
            conn.commit()
        except Exception:
            pass

        # ── v0.40.0 — Sexe des élèves, places réservées (AESH) ────────────────
        try:
            cols_el = {r["name"] for r in conn.execute(
                "PRAGMA table_info(eleves)").fetchall()}
            if cols_el and "sexe" not in cols_el:
                conn.execute("ALTER TABLE eleves ADD COLUMN sexe TEXT NOT NULL DEFAULT ''")
            from services.plans_classe import SCHEMA_RESERVATIONS as _SCH_RES
            conn.executescript(_SCH_RES)
            conn.commit()
        except Exception:
            pass

        # ── v0.43.0 — Absences (début de séance) ─────────────────────────────
        try:
            from services.seance import SCHEMA as _SCHEMA_SEANCE
            conn.executescript(_SCHEMA_SEANCE)
            conn.commit()
        except Exception:
            pass

        # ── v0.43.2 — Début effectif des mises en route (par classe × année) ──
        try:
            cols_ac = {r["name"] for r in conn.execute(
                "PRAGMA table_info(affectation_config)").fetchall()}
            if cols_ac and "mer_date_debut" not in cols_ac:
                conn.execute("ALTER TABLE affectation_config ADD COLUMN "
                             "mer_date_debut TEXT NOT NULL DEFAULT ''")
                conn.commit()
        except Exception:
            pass

        # ── v0.44.0 — Documents de séance (remise, rattrapage) ────────────────
        try:
            from services.documents_seance import SCHEMA as _SCHEMA_DOCS
            conn.executescript(_SCHEMA_DOCS)
            conn.commit()
        except Exception:
            pass

        # ── v0.45.0 — Observables de séance ──────────────────────────────────
        try:
            from services.observables import SCHEMA as _SCHEMA_OBS
            conn.executescript(_SCHEMA_OBS)
            conn.commit()
        except Exception:
            pass

        # ── v0.46.0 — Observations en séance ─────────────────────────────────
        try:
            from services.observation import SCHEMA as _SCHEMA_OBSV
            conn.executescript(_SCHEMA_OBSV)
            conn.commit()
        except Exception:
            pass

        # ── v0.47.0 — Travail à faire / à rendre, documents à rapporter ───────
        try:
            from services import travail as _travail
            _travail.migrer(conn)
            conn.commit()
        except Exception:
            pass

        # ── v0.47.1 — Synthèse Pronote : contenu de séance, activités ─────────
        try:
            from services import synthese_seance as _synth
            _synth.migrer(conn)
            conn.commit()
        except Exception:
            pass

        # ── v0.48.0 — Retour et délai des documents associés ; échéance fixe ──
        try:
            from services import progression_doc as _pgd
            _pgd.migrer_v0_48(conn)
            cols_sd = {r[1] for r in conn.execute("PRAGMA table_info(seance_documents)")}
            for nom in ("echeance_date", "echeance_creneau"):
                if cols_sd and nom not in cols_sd:
                    conn.execute(f"ALTER TABLE seance_documents ADD COLUMN {nom} "
                                 "TEXT NOT NULL DEFAULT ''")
            conn.commit()
        except Exception:
            pass

        # ── v0.48.2 — Référentiels principaux externes (source, type, année ;
        #    fichiers déposés) ──────────────────────────────────────────────
        try:
            from services import referentiel_principal_externe as _rpe
            _rpe.migrer(conn)
            conn.commit()
        except Exception:
            pass

        # ── v0.51.2 — Journal des publications (paquets) ─────────────────────
        try:
            from services import paquet_publication as _pub
            _pub.migrer(conn)
            conn.commit()
        except Exception:
            pass

        # ── v0.51.3 — Import de paquets (appli en ligne) ─────────────────────
        try:
            from services import import_publication as _imp
            _imp.migrer(conn)
            conn.commit()
        except Exception:
            pass

    # ── v0.13.0 — Peuplement initial param_niveaux depuis CSV ────────────────

    def _peupler_param_niveaux_si_vide(self, conn) -> None:
        """Si la table `param_niveaux` est vide, l'amorce depuis
        `data/param_niveaux.csv`.

        Comportement :
          - Si la table contient déjà ≥ 1 ligne : ne fait rien (la BDD est
            maître, on ne ré-importe pas le CSV automatiquement).
          - Si la table est vide ET le CSV existe : insère toutes les lignes
            du CSV. L'ordre est dérivé de l'ordre de lecture du CSV
            (champ `ordre` = 1, 2, 3… selon position).
          - Si la table est vide ET le CSV est absent : ne fait rien
            (laisse la table vide ; les services consommateurs gèreront
            cette situation par défaut, prévu en v0.13.1).

        Idempotente : appelée à chaque démarrage, ne fait rien si la table
        est déjà peuplée.

        Pourquoi pas de re-synchro automatique : si l'utilisateur édite la
        table en BDD (via SQL direct, futur script CLI ou future UI admin),
        on ne veut pas que ces modifications soient écrasées par le CSV au
        prochain démarrage. Le CSV n'est qu'une source d'amorçage.
        """
        n = conn.execute(
            "SELECT COUNT(*) FROM param_niveaux"
        ).fetchone()[0]
        if n > 0:
            return

        csv_path = Path(self.data_dir) / "param_niveaux.csv"
        if not csv_path.exists():
            return

        import csv as _csv  # éviter le shadowing de csv dans ce module
        rows_a_inserer: list[tuple] = []
        try:
            with open(csv_path, encoding="utf-8-sig", newline="") as f:
                reader = _csv.DictReader(f)
                for ordre, row in enumerate(reader, start=1):
                    code = (row.get("Code") or "").strip()
                    cycle_code = (row.get("CodeCycle") or "").strip()
                    annee = (row.get("AnneeDansCycle") or "").strip()
                    nom_court = (row.get("NomCourt") or "").strip()
                    nom_long = (row.get("NomLong") or "").strip()
                    if not code or not cycle_code:
                        # Ligne mal formée, on saute (pas d'exception au démarrage)
                        continue
                    rows_a_inserer.append((
                        code, cycle_code, annee, nom_court, nom_long, ordre,
                    ))
        except Exception:
            # En cas d'erreur de lecture, on n'amorce pas et on laisse la
            # table vide. Le démarrage de l'application doit rester robuste.
            return

        if not rows_a_inserer:
            return

        try:
            # Avant les niveaux : s'assurer que les cycles référencés
            # existent (la FK le requiert). Si un cycle est absent en BDD,
            # on l'amorce avec un nom par défaut dérivé du code (ex.
            # "Cycle 4" pour C04). INSERT OR IGNORE : si le cycle existe
            # déjà, on ne touche pas (l'utilisateur peut avoir personnalisé
            # son nom ou sa description).
            cycles_requis = sorted({r[1] for r in rows_a_inserer})
            for cycle_code in cycles_requis:
                # Nom par défaut : "Cycle 3" pour C03, "Cycle 4" pour C04…
                # Si format différent (ex. CGT pour cycle général technologique),
                # on retombe sur le code lui-même comme nom.
                if cycle_code.startswith("C") and cycle_code[1:].isdigit():
                    nom_defaut = f"Cycle {int(cycle_code[1:])}"
                else:
                    nom_defaut = cycle_code
                conn.execute(
                    "INSERT OR IGNORE INTO cycles (code, nom, description) "
                    "VALUES (?, ?, '')",
                    (cycle_code, nom_defaut),
                )

            conn.executemany(
                "INSERT INTO param_niveaux "
                "(code, cycle_code, annee_dans_cycle, nom_court, nom_long, ordre) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows_a_inserer,
            )
            conn.commit()
        except Exception:
            # Si l'insertion échoue (par ex. FK manquante vers cycles), on
            # rollback et on laisse la table vide. Pas de blocage du démarrage.
            try:
                conn.rollback()
            except Exception:
                pass

    # ── v0.19.1.16 — Peuplement grille horaire par établissement ─────────────

    def _peupler_grille_horaire_si_vide(self, conn) -> None:
        """Pour chaque établissement sans créneau, insère les 8 créneaux par
        défaut (M1..M4, S1..S4 — modèle Hautes Ourmes).

        Idempotent : un établissement qui a déjà au moins un créneau n'est pas
        touché (l'utilisateur peut avoir personnalisé ses horaires). Robuste :
        toute erreur laisse le démarrage se poursuivre.
        """
        try:
            from services import grille_horaire as gh
            etabs = [r[0] for r in conn.execute(
                "SELECT id FROM etablissements").fetchall()]
            for eid in etabs:
                gh.peupler_defauts_si_vide(conn, eid)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

    # ── Classes ───────────────────────────────────────────────────────────────

    def lire_classes(self, annee: str | None = None,
                     etablissement: str | None = None) -> dict:
        """
        Retourne les classes avec leur établissement résolu.
        Chaque classe a :
          - etablissement_id  : id opaque (source de vérité)
          - etablissement     : nom (dénormalisé pour compat ascendante)
          - etab_academie     : académie (pour consommation par l'UI calendrier)
          - etab_etat         : 'propose' | 'valide'
        """
        with self._conn() as conn:
            conditions, params = [], []
            if annee:
                conditions.append("c.annee = ?")
                params.append(annee)
            if etablissement:
                conditions.append("e.nom = ?")
                params.append(etablissement)
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            rows_c = conn.execute(f"""
                SELECT c.*,
                       e.nom       AS etab_nom,
                       e.academie  AS etab_academie,
                       e.ville     AS etab_ville,
                       e.etat      AS etab_etat,
                       e.uai       AS etab_uai
                FROM classes c
                LEFT JOIN etablissements e ON e.id = c.etablissement_id
                {where}
                ORDER BY c.annee DESC, c.nom
            """, params).fetchall()

            classes = []
            for r in rows_c:
                c = dict(r)
                c["progression_id"] = c["progression_id"] or ""
                # Dénormalisation : etablissement = nom de l'établissement
                # (compat ascendante avec les appels existants côté services/UI)
                c["etablissement"] = c.pop("etab_nom") or ""
                c["etab_academie"] = c.get("etab_academie") or ""
                c["etab_ville"]    = c.get("etab_ville") or ""
                c["etab_etat"]     = c.get("etab_etat") or "propose"
                c["etab_uai"]      = c.get("etab_uai") or ""

                # Élèves actifs (date_sortie IS NULL), triés alphabétiquement
                rows_e = conn.execute("""
                    SELECT e.id, e.nom, e.prenom, e.sexe FROM eleves e
                    JOIN eleves_classes ec ON ec.eleve_id = e.id
                    WHERE ec.classe_id = ? AND ec.date_sortie IS NULL
                    ORDER BY e.nom, e.prenom
                """, (c["id"],)).fetchall()
                c["eleves"] = [dict(e) for e in rows_e]

                # versions_actives et sequences_verouillees
                rows_vc = conn.execute(
                    "SELECT * FROM versions_classes WHERE classe_id = ?",
                    (c["id"],)
                ).fetchall()
                va, sv = {}, []
                for vc in rows_vc:
                    key = f"{vc['niveau']}_{vc['seq_code']}"
                    if vc["tag_actif"]:
                        va[key] = vc["tag_actif"]
                    if vc["verrouille"]:
                        sv.append(key)
                c["versions_actives"] = va
                c["sequences_verouillees"] = sv
                classes.append(c)

        return {"classes": classes}

    def ecrire_classes(self, data: dict) -> None:
        """
        Écrit les classes.

        Chaque classe peut fournir :
          - etablissement_id : id opaque (prioritaire)
          - etablissement    : nom (legacy/import) — l'établissement est
            créé avec l'état 'propose' s'il n'existe pas encore en base.

        L'un des deux doit être fourni.
        """
        classes = data.get("classes", [])
        with self._conn() as conn:
            ids_entrants = {c["id"] for c in classes}
            existants = {r[0] for r in conn.execute(
                "SELECT id FROM classes"
            ).fetchall()}
            for cid in existants - ids_entrants:
                conn.execute("DELETE FROM eleves_classes WHERE classe_id=?", (cid,))
                conn.execute("DELETE FROM versions_classes WHERE classe_id=?", (cid,))
                conn.execute("DELETE FROM classes WHERE id=?", (cid,))

            for c in classes:
                # Résoudre etablissement_id : priorité à l'id, sinon créer
                # par nom. Nom vide toléré → fallback "Non renseigné".
                etab_id = c.get("etablissement_id") or None
                if not etab_id:
                    nom_etab = c.get("etablissement", "").strip()
                    if not nom_etab:
                        nom_etab = "Non renseigné"
                    # Chercher ou créer l'établissement. v0.41.2 — nom
                    # comparé sans tenir compte de la casse ni des espaces
                    # (« collège  les hautes ourmes » = « Collège les Hautes
                    # Ourmes ») : évite les doublons d'établissement.
                    def _cle(n):
                        return " ".join((n or "").split()).casefold()
                    row = next((r for r in conn.execute(
                        "SELECT id, nom FROM etablissements").fetchall()
                        if _cle(r[1]) == _cle(nom_etab)), None)
                    if row:
                        etab_id = row[0]
                    else:
                        from persistence.ids import nouveau_id_etablissement
                        etab_id = nouveau_id_etablissement()
                        conn.execute("""
                            INSERT INTO etablissements (id, nom, etat)
                            VALUES (?, ?, 'propose')
                        """, (etab_id, nom_etab))

                # Vérifier que la progression existe avant de la référencer
                pid_ref = c.get("progression_id","") or None
                if pid_ref:
                    exists = conn.execute(
                        "SELECT 1 FROM progressions WHERE id=?", (pid_ref,)
                    ).fetchone()
                    if not exists:
                        pid_ref = None
                conn.execute("""
                    INSERT INTO classes
                      (id, nom, niveau, annee, etablissement_id, progression_id,
                       seances_A, seances_B, mer_active, mer_mode)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                      nom=excluded.nom, niveau=excluded.niveau,
                      annee=excluded.annee,
                      etablissement_id=excluded.etablissement_id,
                      progression_id=excluded.progression_id,
                      seances_A=excluded.seances_A,
                      seances_B=excluded.seances_B,
                      mer_active=excluded.mer_active,
                      mer_mode=excluded.mer_mode
                """, (
                    c["id"], c.get("nom",""), c.get("niveau","N10"),
                    c.get("annee",""), etab_id, pid_ref,
                    int(c.get("seances_A", 0) or 0),
                    int(c.get("seances_B", 0) or 0),
                    1 if c.get("mer_active") else 0,
                    c.get("mer_mode", "automatismes") or "automatismes",
                ))

                for e in c.get("eleves", []):
                    conn.execute(
                        "INSERT OR IGNORE INTO eleves (id, nom, prenom) VALUES (?,?,?)",
                        (e["id"], e.get("nom",""), e.get("prenom",""))
                    )
                    conn.execute("""
                        INSERT OR IGNORE INTO eleves_classes (eleve_id, classe_id)
                        VALUES (?,?)
                    """, (e["id"], c["id"]))

                for key, tag in c.get("versions_actives", {}).items():
                    parts = key.split("_", 1)
                    if len(parts) == 2:
                        niv, seq = parts
                        conn.execute("""
                            INSERT INTO versions_classes
                              (classe_id, niveau, seq_code, tag_actif, verrouille)
                            VALUES (?,?,?,?,0)
                            ON CONFLICT(classe_id, niveau, seq_code)
                            DO UPDATE SET tag_actif=excluded.tag_actif
                        """, (c["id"], niv, seq, tag))

                for key in c.get("sequences_verouillees", []):
                    parts = key.split("_", 1)
                    if len(parts) == 2:
                        niv, seq = parts
                        conn.execute("""
                            INSERT INTO versions_classes
                              (classe_id, niveau, seq_code, tag_actif, verrouille)
                            VALUES (?,?,?,NULL,1)
                            ON CONFLICT(classe_id, niveau, seq_code)
                            DO UPDATE SET verrouille=1
                        """, (c["id"], niv, seq))

    def ajouter_eleve(self, classe_id: str, eleve_id: str, nom: str, prenom: str,
                      date_entree: str | None = None) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO eleves (id, nom, prenom) VALUES (?,?,?)",
                (eleve_id, nom, prenom)
            )
            conn.execute("""
                INSERT OR IGNORE INTO eleves_classes (eleve_id, classe_id, date_entree)
                VALUES (?,?,?)
            """, (eleve_id, classe_id, date_entree))

    def retirer_eleve(self, eleve_id: str, classe_id: str,
                      date_sortie: str | None = None) -> None:
        with self._conn() as conn:
            if date_sortie:
                conn.execute("""
                    UPDATE eleves_classes SET date_sortie=?
                    WHERE eleve_id=? AND classe_id=?
                """, (date_sortie, eleve_id, classe_id))
            else:
                conn.execute(
                    "DELETE FROM eleves_classes WHERE eleve_id=? AND classe_id=?",
                    (eleve_id, classe_id)
                )

    def supprimer_donnees_eleve(self, classe_id: str, eleve_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM suivi WHERE classe_id=? AND eleve_id=?",
                (classe_id, eleve_id)
            )
            conn.execute(
                "DELETE FROM niveaux WHERE classe_id=? AND eleve_id=?",
                (classe_id, eleve_id)
            )
            conn.execute(
                "DELETE FROM eleves_classes WHERE eleve_id=? AND classe_id=?",
                (eleve_id, classe_id)
            )

    def supprimer_donnees_classe(self, classe_id: str) -> None:
        """
        Supprime la classe et toutes ses données dérivées :
        versions_classes, suivi, niveaux, eleves_classes (cascade).
        Supprime également les élèves devenus orphelins (plus rattachés
        à aucune classe) — nécessaire car la table eleves est globale.
        """
        with self._conn() as conn:
            # Récupérer d'abord la liste des eid rattachés à cette classe
            rows = conn.execute(
                "SELECT eleve_id FROM eleves_classes WHERE classe_id=?",
                (classe_id,)
            ).fetchall()
            eids_classe = [r[0] for r in rows]

            # Nettoyer les tables de suivi dénormalisées (pas de FK cascade dessus)
            conn.execute("DELETE FROM suivi WHERE classe_id=?", (classe_id,))
            conn.execute("DELETE FROM niveaux WHERE classe_id=?", (classe_id,))
            conn.execute("DELETE FROM versions_classes WHERE classe_id=?", (classe_id,))

            # DELETE FROM classes cascade sur eleves_classes (FK ON DELETE CASCADE)
            conn.execute("DELETE FROM classes WHERE id=?", (classe_id,))

            # Supprimer les élèves devenus orphelins (aucune autre classe ne les référence)
            for eid in eids_classe:
                reste = conn.execute(
                    "SELECT 1 FROM eleves_classes WHERE eleve_id=? LIMIT 1",
                    (eid,)
                ).fetchone()
                if not reste:
                    conn.execute("DELETE FROM eleves WHERE id=?", (eid,))

    # ── Suivi ────────────────────────────────────────────────────────────────

    def _creneau_id_pour(self, conn, classe_id: str,
                          seq_code: str, rang: int = 1) -> str | None:
        """Créneau qui couvre ce rang (partie_debut <= rang <= partie_fin)."""
        row = conn.execute("""
            SELECT cr.id FROM creneaux cr
            JOIN classes cl ON cl.progression_id = cr.progression_id
            WHERE cl.id=? AND cr.seq_code=?
              AND cr.partie_debut <= ? AND cr.partie_fin >= ?
            LIMIT 1
        """, (classe_id, seq_code, rang, rang)).fetchone()
        return row[0] if row else None

    def lire_suivi(self, annee: str | None = None) -> dict:
        with self._conn() as conn:
            if annee:
                rows = conn.execute("""
                    SELECT s.classe_id, s.seq_code, s.eleve_id, s.serie, s.num
                    FROM suivi s
                    JOIN classes cl ON cl.id = s.classe_id
                    WHERE cl.annee=?
                """, (annee,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT classe_id, seq_code, eleve_id, serie, num FROM suivi"
                ).fetchall()
        result: dict = {}
        for r in rows:
            (result.setdefault(r["classe_id"], {})
             .setdefault(r["seq_code"], {})
             .setdefault(r["eleve_id"], {})
             .setdefault(r["serie"], [])
             .append(r["num"]))
        return result

    def lire_suivi_classe(self, classe_id: str) -> dict:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT seq_code, eleve_id, serie, num FROM suivi WHERE classe_id=?",
                (classe_id,)
            ).fetchall()
        result: dict = {}
        for r in rows:
            (result.setdefault(r["seq_code"], {})
             .setdefault(r["eleve_id"], {})
             .setdefault(r["serie"], [])
             .append(r["num"]))
        return result

    def ecrire_suivi(self, data: dict) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM suivi")
            for cid, seqs in data.items():
                for seq, eleves in seqs.items():
                    creneau_id = self._creneau_id_pour(conn, cid, seq)
                    for eid, series in eleves.items():
                        for serie, nums in series.items():
                            for num in nums:
                                conn.execute(
                                    "INSERT OR IGNORE INTO suivi "
                                    "(classe_id, seq_code, creneau_id, eleve_id, serie, num) "
                                    "VALUES (?,?,?,?,?,?)",
                                    (cid, seq, creneau_id, eid, serie, int(num))
                                )

    def cocher_exercice(self, classe_id: str, seq_code: str, eleve_id: str,
                         serie: str, num: int, coche: bool) -> None:
        with self._conn() as conn:
            creneau_id = self._creneau_id_pour(conn, classe_id, seq_code)
            if coche:
                conn.execute(
                    "INSERT OR IGNORE INTO suivi "
                    "(classe_id, seq_code, creneau_id, eleve_id, serie, num) "
                    "VALUES (?,?,?,?,?,?)",
                    (classe_id, seq_code, creneau_id, eleve_id, serie, num)
                )
            else:
                conn.execute(
                    "DELETE FROM suivi WHERE classe_id=? AND seq_code=? "
                    "AND eleve_id=? AND serie=? AND num=?",
                    (classe_id, seq_code, eleve_id, serie, num)
                )

    # ── Niveaux ───────────────────────────────────────────────────────────────

    def _objectif_id_pour(self, conn, classe_id: str,
                           seq_code: str, obj_code: str) -> str | None:
        # v0.14.6.b.1 — Lecture v2 (objectifs) via JOIN partie. La
        # signature publique est inchangée : on cherche l'objectif dont
        # le `code` matche, en privilégiant ceux qui ont une méthode liée
        # (cohérent avec l'ancien comportement v1). On ignore classe_id
        # comme avant (pas de filtre niveau dans cette fonction utilitaire).
        row = conn.execute(
            "SELECT ov2.id FROM objectifs ov2 "
            "WHERE ov2.code=? AND ov2.methode_id IS NOT NULL LIMIT 1",
            (obj_code,)
        ).fetchone()
        if row:
            return row[0]
        row2 = conn.execute(
            "SELECT id FROM objectifs WHERE code=? LIMIT 1", (obj_code,)
        ).fetchone()
        return row2[0] if row2 else None

    def lire_niveaux(self, annee: str | None = None) -> dict:
        with self._conn() as conn:
            if annee:
                rows = conn.execute("""
                    SELECT n.classe_id, n.seq_code, n.eleve_id,
                           n.obj_code, n.niveau_code
                    FROM niveaux n
                    JOIN classes cl ON cl.id = n.classe_id
                    WHERE cl.annee=?
                """, (annee,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT classe_id, seq_code, eleve_id, obj_code, niveau_code "
                    "FROM niveaux"
                ).fetchall()
        result: dict = {}
        for r in rows:
            (result.setdefault(r["classe_id"], {})
             .setdefault(r["seq_code"], {})
             .setdefault(r["eleve_id"], {}))[r["obj_code"]] = r["niveau_code"]
        return result

    def lire_niveaux_classe(self, classe_id: str) -> dict:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT seq_code, eleve_id, obj_code, niveau_code "
                "FROM niveaux WHERE classe_id=?",
                (classe_id,)
            ).fetchall()
        result: dict = {}
        for r in rows:
            (result.setdefault(r["seq_code"], {})
             .setdefault(r["eleve_id"], {}))[r["obj_code"]] = r["niveau_code"]
        return result

    def ecrire_niveaux(self, data: dict) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM niveaux")
            for cid, seqs in data.items():
                for seq, eleves in seqs.items():
                    for eid, objs in eleves.items():
                        for obj_code, niv in objs.items():
                            rang = _rang_depuis_code(obj_code)
                            creneau_id  = self._creneau_id_pour(conn, cid, seq, rang)
                            # v0.14.6.b.2 — colonne `objectif_id` retirée
                            # (FK orpheline vers `objectifs` v1 supprimée).
                            # Le rattachement métier se fait par `obj_code`.
                            conn.execute(
                                "INSERT OR REPLACE INTO niveaux "
                                "(classe_id, seq_code, eleve_id, obj_code, "
                                " creneau_id, niveau_code) "
                                "VALUES (?,?,?,?,?,?)",
                                (cid, seq, eid, obj_code, creneau_id, niv)
                            )

    def set_niveau(self, classe_id: str, seq_code: str, eleve_id: str,
                   obj_code: str, niveau: str) -> None:
        with self._conn() as conn:
            rang = _rang_depuis_code(obj_code)
            creneau_id  = self._creneau_id_pour(conn, classe_id, seq_code, rang)
            # v0.14.6.b.2 — colonne `objectif_id` retirée (cf. ecrire_niveaux).
            conn.execute(
                "INSERT OR REPLACE INTO niveaux "
                "(classe_id, seq_code, eleve_id, obj_code, "
                " creneau_id, niveau_code) "
                "VALUES (?,?,?,?,?,?)",
                (classe_id, seq_code, eleve_id, obj_code,
                 creneau_id, niveau)
            )

    # ── Versions ─────────────────────────────────────────────────────────────

    def lire_versions(self) -> dict:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM versions ORDER BY date DESC"
            ).fetchall()
        result: dict = {}
        for r in rows:
            entry = {"tag": r["tag"], "label": r["label"],
                     "date": r["date"], **_uj(r["contenu"], {})}
            result.setdefault(r["niveau"], {}).setdefault(r["seq_code"], []).append(entry)
        return result

    def ecrire_versions(self, data: dict) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM versions")
            for niv, seqs in data.items():
                for seq, versions in seqs.items():
                    for v in versions:
                        tag, label, date = v.get("tag",""), v.get("label",""), v.get("date","")
                        extra = {k: val for k, val in v.items()
                                 if k not in ("tag","label","date")}
                        conn.execute(
                            "INSERT OR REPLACE INTO versions "
                            "(niveau,seq_code,tag,label,date,contenu) VALUES (?,?,?,?,?,?)",
                            (niv, seq, tag, label, date, _j(extra))
                        )

    def upsert_version(self, niveau: str, seq: str, tag: str,
                       label: str, date: str, contenu: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO versions "
                "(niveau,seq_code,tag,label,date,contenu) VALUES (?,?,?,?,?,?)",
                (niveau, seq, tag, label, date, _j(contenu))
            )

    def supprimer_version(self, niveau: str, seq: str, tag: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM versions WHERE niveau=? AND seq_code=? AND tag=?",
                (niveau, seq, tag)
            )

    def version_utilisee(self, niveau: str, seq: str, tag: str) -> bool:
        with self._conn() as conn:
            return conn.execute(
                "SELECT 1 FROM versions_classes WHERE niveau=? AND seq_code=? "
                "AND tag_actif=? LIMIT 1", (niveau, seq, tag)
            ).fetchone() is not None

    def lire_version_active(self, classe_id: str, niveau: str, seq: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT tag_actif FROM versions_classes "
                "WHERE classe_id=? AND niveau=? AND seq_code=?",
                (classe_id, niveau, seq)
            ).fetchone()
        return row["tag_actif"] if row else None

    def set_version_active(self, classe_id: str, niveau: str, seq: str,
                           tag: str | None) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO versions_classes (classe_id,niveau,seq_code,tag_actif,verrouille)
                VALUES (?,?,?,?,0)
                ON CONFLICT(classe_id,niveau,seq_code) DO UPDATE SET tag_actif=excluded.tag_actif
            """, (classe_id, niveau, seq, tag))

    def est_verrouille(self, classe_id: str, niveau: str, seq: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT verrouille FROM versions_classes "
                "WHERE classe_id=? AND niveau=? AND seq_code=?",
                (classe_id, niveau, seq)
            ).fetchone()
        return bool(row["verrouille"]) if row else False

    def verrouiller(self, classe_id: str, niveau: str, seq: str) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO versions_classes (classe_id,niveau,seq_code,verrouille)
                VALUES (?,?,?,1)
                ON CONFLICT(classe_id,niveau,seq_code) DO UPDATE SET verrouille=1
            """, (classe_id, niveau, seq))

    # ── Atomes ───────────────────────────────────────────────────────────────

    # v0.6.4 — Modèle de sections à 2 niveaux
    # ----------------------------------------
    # Avant v0.6.4, les exemples et remarques d'une notion ou méthode étaient
    # stockés à plat dans `items_texte` avec une colonne `categorie`
    # (`exemple` ou `remarque`). Ce modèle ne pouvait porter qu'une trentaine
    # de variantes de sections rencontrées dans le corpus réel : Conséquences,
    # Démonstration, Démonstration de la réciproque, Propriété, etc.
    #
    # Le nouveau modèle utilise 2 tables :
    #   atome_sections        — une section avec un titre libre et un ordre
    #   atome_section_items   — les items à l'intérieur d'une section
    #
    # Format dict d'échange (lire/ecrire notions et méthodes) :
    #   "sections": [
    #     {"titre": "Conséquences",  "items": ["item LaTeX 1", "item 2", ...]},
    #     {"titre": "Remarques",     "items": [...]},
    #     {"titre": "Démonstration", "items": [...]},
    #     ...
    #   ]
    # L'ordre de la liste `sections` est l'ordre d'affichage. L'ordre des
    # items dans chaque section est aussi l'ordre d'affichage.

    def _lire_sections(self, conn, entite_type: str,
                       entite_id: str) -> list[dict]:
        """Lit toutes les sections d'une entité (notion/méthode), avec
        leurs items, dans l'ordre."""
        sections_rows = conn.execute(
            "SELECT id, titre FROM atome_sections "
            "WHERE entite_type=? AND entite_id=? ORDER BY ordre",
            (entite_type, entite_id),
        ).fetchall()
        out = []
        for sr in sections_rows:
            items_rows = conn.execute(
                "SELECT corps FROM atome_section_items "
                "WHERE section_id=? ORDER BY ordre",
                (sr["id"],),
            ).fetchall()
            out.append({
                "titre": sr["titre"],
                "items": [ir["corps"] for ir in items_rows],
            })
        return out

    def _ecrire_sections(self, conn, entite_type: str,
                         entite_id: str, sections: list[dict]) -> None:
        """Remplace toutes les sections d'une entité par celles fournies.
        Les items existants sont supprimés en cascade via ON DELETE CASCADE
        sur atome_section_items.section_id."""
        # On supprime d'abord les sections (cascade nettoie les items)
        conn.execute(
            "DELETE FROM atome_sections WHERE entite_type=? AND entite_id=?",
            (entite_type, entite_id),
        )
        for i, sec in enumerate(sections or []):
            section_id = _rowid()
            conn.execute(
                "INSERT INTO atome_sections (id, entite_type, entite_id, "
                "titre, ordre) VALUES (?,?,?,?,?)",
                (section_id, entite_type, entite_id,
                 sec.get("titre", "") or "", i),
            )
            for j, corps in enumerate(sec.get("items", []) or []):
                conn.execute(
                    "INSERT INTO atome_section_items (id, section_id, "
                    "ordre, corps) VALUES (?,?,?,?)",
                    (_rowid(), section_id, j, corps),
                )

    def ecrire_objectifs(self, referentiel_ids: list[str] | None = None) -> dict:
        """
        v0.14.6.b.1 — Écrit dans `objectifs` (anciennement `objectifs` v1).

        Crée les objectifs comme atomes pédagogiques de premier ordre à
        partir des données de `referentiel_objectifs`. La table v1 est
        désormais ignorée — elle sera supprimée en v0.14.6.b.2.

        Pour chaque objectif déclaré dans un référentiel verrouillé (ou
        dans la liste des référentiels passés en argument), on crée une
        ligne dans `objectifs` :
          - id : UUID opaque
          - partie_id : déduit du niveau + seq_code + premier chiffre du
            code (convention canonique :
                code '01'..'09' → partie 1
                code '11'..'19' → partie 2
                etc.)
          - code : code métier (02, 12, 21, ...)
          - nom : libellé pédagogique
          - methode_id NULL : sera posé par `ecrire_methodes` quand la
            méthode correspondante sera importée.
          - critere_F, critere_A, critere_E : recopiés du référentiel

        Stratégie UPSERT (idempotent, non destructif) :
          - si l'objectif (partie_id, code) existe déjà : UPDATE de nom
            + critères ; on préserve methode_id.
          - sinon : INSERT avec UUID généré. Crée la partie au besoin.

        Note : les champs v1 `est_nouveau` et `obj_precedent_id` ne sont
        plus migrés (remplacés en v2 par le mécanisme des précédences
        inter-parties).

        Retourne un dict rapport {referentiels_traites, objectifs_crees,
        objectifs_maj}.
        """
        rapport = {
            "referentiels_traites": 0,
            "objectifs_crees":      0,
            "objectifs_maj":        0,
        }
        with self._conn() as conn:
            if referentiel_ids is None:
                rows = conn.execute(
                    "SELECT id FROM referentiel_niveaux WHERE etat='verrouille'"
                ).fetchall()
                referentiel_ids = [r["id"] for r in rows]

            for ref_id in referentiel_ids:
                ref = conn.execute(
                    "SELECT niveau FROM referentiel_niveaux WHERE id=?",
                    (ref_id,)
                ).fetchone()
                if not ref:
                    continue
                niveau = ref["niveau"]

                obj_rows = conn.execute(
                    "SELECT seq_code, code, nom, fin_cycle, "
                    "       critere_f, critere_a, critere_e "
                    "FROM referentiel_objectifs "
                    "WHERE referentiel_id=? "
                    "ORDER BY seq_code, code",
                    (ref_id,)
                ).fetchall()

                for r in obj_rows:
                    seq_code = r["seq_code"]
                    code = r["code"]
                    nom_obj = r["nom"] or ""
                    cF = r["critere_f"] or ""
                    cA = r["critere_a"] or ""
                    cE = r["critere_e"] or ""

                    # 1. Trouver / créer (niveau, seq_code) dans
                    # sequences_par_niveau.
                    # v0.14.6.b.1 — Création à la volée si absent. Cohérent
                    # avec le pipeline d'import : un référentiel verrouillé
                    # pour un niveau implique que ses séquences existent
                    # logiquement pour ce niveau. La création vide ici
                    # est inoffensive (parametres='' par défaut) et permet
                    # à la chaîne ecrire_objectifs → ecrire_methodes →
                    # ecrire_exercices d'être autonome.
                    sn = conn.execute(
                        "SELECT id FROM sequences_par_niveau "
                        "WHERE niveau=? AND sequence_code=?",
                        (niveau, seq_code)
                    ).fetchone()
                    if sn:
                        sn_id = sn["id"]
                    else:
                        sn_id = uuid.uuid4().hex[:16]
                        conn.execute(
                            "INSERT INTO sequences_par_niveau "
                            "(id, niveau, sequence_code, parametres) "
                            "VALUES (?, ?, ?, '')",
                            (sn_id, niveau, seq_code)
                        )

                    # 2. Déduire le numéro de partie depuis le code.
                    num_partie = _num_partie_depuis_code_v2(code)
                    if num_partie is None:
                        # Code non-standard : on saute. Ces cas doivent
                        # être rares (cf. audit v0.14.5) ; s'il y en a,
                        # ils sont à corriger à la main dans le
                        # référentiel.
                        continue

                    # 3. Trouver / créer la partie.
                    partie = conn.execute(
                        "SELECT id FROM sequence_parties "
                        "WHERE sequence_par_niveau_id=? AND numero=?",
                        (sn_id, num_partie)
                    ).fetchone()
                    if partie:
                        partie_id = partie["id"]
                    else:
                        partie_id = nouveau_id_partie()
                        conn.execute(
                            "INSERT INTO sequence_parties "
                            "(id, sequence_par_niveau_id, numero) "
                            "VALUES (?, ?, ?)",
                            (partie_id, sn_id, num_partie)
                        )

                    # 4. UPSERT de l'objectif sur (partie_id, code).
                    existant = conn.execute(
                        "SELECT id FROM objectifs "
                        "WHERE partie_id=? AND code=? LIMIT 1",
                        (partie_id, code)
                    ).fetchone()
                    if existant:
                        # UPDATE nom + critères, préserver methode_id
                        conn.execute(
                            "UPDATE objectifs "
                            "SET nom=?, critere_F=?, critere_A=?, critere_E=? "
                            "WHERE id=?",
                            (nom_obj, cF, cA, cE, existant["id"])
                        )
                        rapport["objectifs_maj"] += 1
                    else:
                        nouvel_id = nouveau_id_objectif()
                        conn.execute(
                            "INSERT INTO objectifs "
                            "(id, partie_id, code, nom, methode_id, "
                            " critere_F, critere_A, critere_E) "
                            "VALUES (?, ?, ?, ?, NULL, ?, ?, ?)",
                            (nouvel_id, partie_id, code, nom_obj,
                             cF, cA, cE)
                        )
                        rapport["objectifs_crees"] += 1

                rapport["referentiels_traites"] += 1

        return rapport

    def lire_notions(self) -> list:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM notions ORDER BY rowid").fetchall()
            return [{
                "id":               r["id"],
                "titre":            r["titre"],
                "corps":            r["corps"],
                "ordreExRem":       r["ordre_sections"] == "ER",
                # Métadonnées du scanner — indispensables à la déduplication
                # par `fichier` lors des réimports (sinon chaque scan traite
                # toutes les notions comme nouvelles et accumule les doublons).
                "niveau":           r["niveau"] or "",
                "sequence":         r["sequence"] or "",
                "num_connaissance": r["num_connaissance"] or "",
                "fichier":          r["fichier"] or "",
                # v0.6.4 — modèle universel à 2 niveaux (cf. _lire_sections).
                # L'API renvoie maintenant `sections` au lieu de
                # `exemples`/`remarques`. Breaking change frontend assumé.
                "sections":         self._lire_sections(conn, "notion", r["id"]),
                # v0.10.4 — état d'édition (`en_cours` par défaut).
                "etat_code":        r["etat_code"] or "en_cours",
            } for r in rows]

    def ecrire_notions(self, liste: list) -> None:
        with self._conn() as conn:
            # v0.10.4 : préserver l'état d'édition au travers du DELETE/INSERT
            # qui implémente "écrire la liste complète". Sans ça, chaque
            # sauvegarde unitaire (PUT) referait passer toutes les notions
            # à 'en_cours'. Le payload `liste` peut aussi porter explicitement
            # `etat_code` (si le client a un nouvel état à appliquer) — il
            # prend alors le dessus sur l'état préexistant.
            etats_preexistants = {
                r["id"]: r["etat_code"] for r in conn.execute(
                    "SELECT id, etat_code FROM notions"
                )
            }
            conn.execute("DELETE FROM notions")
            # v0.6.4 — Le DELETE FROM atome_sections cascade vers
            # atome_section_items (FK ON DELETE CASCADE).
            conn.execute("DELETE FROM atome_sections WHERE entite_type='notion'")
            for n in liste:
                os_ = "ER" if n.get("ordreExRem", True) else "RE"
                # v0.6.3e : on préserve les métadonnées scanner (niveau, sequence,
                # num_connaissance, fichier) pour pouvoir retrouver une notion par
                # son fichier source ou par sa position (niveau, sequence, num).
                etat = (
                    n.get("etat_code")
                    or etats_preexistants.get(n["id"])
                    or "en_cours"
                )
                conn.execute(
                    "INSERT INTO notions "
                    "(id, titre, corps, ordre_sections, "
                    " niveau, sequence, num_connaissance, fichier, etat_code) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        n["id"], n.get("titre",""), n.get("corps",""), os_,
                        n.get("niveau", ""), n.get("sequence", ""),
                        n.get("num_connaissance", "") or "",
                        n.get("fichier", ""),
                        etat,
                    )
                )
                # v0.6.4 — Sections universelles
                self._ecrire_sections(conn, "notion", n["id"],
                                      n.get("sections", []))

    def lire_methodes(self) -> list:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM methodes ORDER BY rowid").fetchall()
            result = []
            for r in rows:
                rows_n = conn.execute(
                    "SELECT notion_id FROM methode_notions WHERE methode_id=? ORDER BY ordre",
                    (r["id"],)
                ).fetchall()
                # v0.14.6.b.1 — Lecture des critères depuis objectifs
                # (la colonne methode_id existe en v2). Plus aucune
                # dépendance à la v1 (table `objectifs`).
                row_obj = conn.execute(
                    "SELECT critere_F, critere_A, critere_E FROM objectifs "
                    "WHERE methode_id=? ORDER BY rowid LIMIT 1", (r["id"],)
                ).fetchone()
                result.append({
                    "id":        r["id"],
                    "titre":     r["titre"],
                    "corps":     r["corps"],
                    "finCycle":  r["fin_cycle"],
                    "ordreExRem": r["ordre_sections"] == "ER",
                    "notions":   [rn["notion_id"] for rn in rows_n],
                    # Fix nettoyage YAML/JSON : conserver les clés attendues
                    # par services/sequences.py::build_sequences_from_livrets.
                    "niveau":      r["niveau"],
                    "sequence":    r["sequence"],
                    "num_methode": r["num_methode"],
                    "num_objectif": r["num_objectif"],
                    "fichier":     r["fichier"],
                    "criteres":  {
                        "2": row_obj["critere_F"] if row_obj else "",
                        "3": row_obj["critere_A"] if row_obj else "",
                        "4": row_obj["critere_E"] if row_obj else "",
                        "F": row_obj["critere_F"] if row_obj else "",
                        "A": row_obj["critere_A"] if row_obj else "",
                        "E": row_obj["critere_E"] if row_obj else "",
                    },
                    # v0.6.4 — modèle universel à 2 niveaux
                    "sections":  self._lire_sections(conn, "methode", r["id"]),
                    # v0.10.4 — état d'édition
                    "etat_code": r["etat_code"] or "en_cours",
                })
            return result

    def ecrire_methodes(self, liste: list) -> None:
        with self._conn() as conn:
            # v0.10.4 : préserver etat_code (cf. ecrire_notions).
            etats_preexistants = {
                r["id"]: r["etat_code"] for r in conn.execute(
                    "SELECT id, etat_code FROM methodes"
                )
            }
            # v0.14.6.b.1 — Casser les liaisons FK vers methodes côté v2.
            # La FK objectifs.methode_id → methodes est en
            # ON DELETE SET NULL, donc en théorie on pourrait laisser le
            # DELETE faire le travail. On le fait explicitement pour
            # rester proche du comportement v1 (UPDATE … SET methode_id=NULL).
            conn.execute("UPDATE objectifs SET methode_id=NULL")
            conn.execute("DELETE FROM methode_notions")
            # v0.6.4 — sections universelles : DELETE cascade vers items.
            conn.execute("DELETE FROM atome_sections WHERE entite_type='methode'")
            conn.execute("DELETE FROM methodes")
            for m in liste:
                os_ = "ER" if m.get("ordreExRem", True) else "RE"
                fc  = m.get("finCycle", m.get("fin_cycle", "N"))
                niveau   = m.get("niveau", "")
                sequence = m.get("sequence", "")
                num_meth = m.get("num_methode")
                num_obj  = m.get("num_objectif", "") or ""
                fichier  = m.get("fichier", "")
                etat = (
                    m.get("etat_code")
                    or etats_preexistants.get(m["id"])
                    or "en_cours"
                )

                # v0.6.3e : conserver niveau/sequence/num_methode/num_objectif/fichier
                conn.execute(
                    "INSERT INTO methodes "
                    "(id, titre, corps, fin_cycle, ordre_sections, "
                    " niveau, sequence, num_methode, num_objectif, fichier, "
                    " etat_code) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        m["id"], m.get("titre",""), m.get("corps",""), fc, os_,
                        niveau, sequence,
                        int(num_meth) if num_meth is not None and str(num_meth).isdigit() else None,
                        num_obj, fichier,
                        etat,
                    )
                )
                # v0.6.4 — Sections universelles
                self._ecrire_sections(conn, "methode", m["id"],
                                      m.get("sections", []))
                for i, nid in enumerate(m.get("notions", [])):
                    conn.execute("INSERT OR IGNORE INTO methode_notions VALUES (?,?,?)",
                        (m["id"], nid, i))

                # v0.14.6.b.1 — Lier la méthode à son objectif côté v2.
                # Règle métier inchangée : 1 méthode = 1 objectif, lié par
                # (niveau, sequence, code) du référentiel.
                # Si un objectif v2 existe déjà (créé par ecrire_objectifs
                # depuis referentiel_objectifs), on lui pose methode_id et
                # ses critères. Sinon, on ne crée rien (l'enseignant doit
                # d'abord peupler le référentiel).
                #
                # Cas legacy v1 supprimé : avant, si la méthode n'avait pas
                # de métadonnées et au moins un critère, on créait un
                # objectif orphelin dans v1. Cet artifice servait
                # uniquement aux anciens tests sans pipeline d'import
                # complet. Aucun cas en prod (audit v0.14.5 : 0 orphelin
                # ne provenait de ce chemin). Si besoin réapparaît, on
                # créera un objectif v2 + sa partie via la même logique
                # que ecrire_objectifs.
                crit = m.get("criteres", {})
                crit_F = crit.get("2", crit.get("F", crit.get("fondamental", "")))
                crit_A = crit.get("3", crit.get("A", crit.get("avancé", "")))
                crit_E = crit.get("4", crit.get("E", crit.get("exploration", "")))

                if niveau and sequence and num_obj:
                    # Cas nominal : on cherche l'objectif v2 via le JOIN
                    # partie → sequence_par_niveau.
                    existant = conn.execute(
                        "SELECT ov2.id FROM objectifs ov2 "
                        "JOIN sequence_parties      p  ON p.id  = ov2.partie_id "
                        "JOIN sequences_par_niveau  sn ON sn.id = p.sequence_par_niveau_id "
                        "WHERE sn.niveau=? AND sn.sequence_code=? AND ov2.code=? "
                        "LIMIT 1",
                        (niveau, sequence, num_obj)
                    ).fetchone()
                    if existant:
                        conn.execute(
                            "UPDATE objectifs "
                            "SET methode_id=?, critere_F=?, critere_A=?, critere_E=? "
                            "WHERE id=?",
                            (m["id"], crit_F, crit_A, crit_E, existant["id"])
                        )
                    # Si pas d'objectif existant : on ne crée rien (le
                    # rapport amont signalera l'orphelinat).

    def lire_exercices(self) -> list:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM exercices ORDER BY rowid").fetchall()
            result = []
            for r in rows:
                # IDs des objectifs liés
                # v0.14.6.b.1 — Source des objectifs liés : objectif_exos (v2)
                # au lieu de exercice_objectifs (v1). Les liaisons v2 sont
                # plus riches (avec serie/ordre) ; on les déduplique sur
                # `objectif_id` pour garder la signature de retour.
                ids_obj_uniques = []
                vu = set()
                for ro in conn.execute(
                    "SELECT objectif_id FROM objectif_exos "
                    "WHERE exercice_id=? ORDER BY serie, ordre",
                    (r["id"],)
                ).fetchall():
                    oid = ro["objectif_id"]
                    if oid not in vu:
                        vu.add(oid)
                        ids_obj_uniques.append(oid)
                ids_obj = ids_obj_uniques
                # Fix nettoyage YAML/JSON : aussi renvoyer les CODES des
                # objectifs ('02', '11'…), attendus par build_sequences_from_livrets.
                codes_obj = []
                if ids_obj:
                    rows_codes = conn.execute(
                        "SELECT code FROM objectifs WHERE id IN ({})".format(
                            ",".join("?" * len(ids_obj))
                        ),
                        ids_obj,
                    ).fetchall()
                    codes_obj = [rc["code"] for rc in rows_codes]
                # v0.10.4 — `etat_code` exposé via dict(r) automatiquement
                # puisque la colonne existe en BDD. On le normalise au cas où.
                d = dict(r)
                d["etat_code"] = d.get("etat_code") or "en_cours"
                # v0.13.5.2.3 — type_format est exposé via dict(r) (colonne
                # ajoutée en migration v0.13.5.2). Default 'standard' au cas
                # où la migration n'aurait pas tourné (BDD très ancienne).
                d["type_format"] = d.get("type_format") or "standard"
                result.append({
                    **d,
                    "objectifs":       ids_obj,
                    "objectifs_codes": codes_obj,
                })
            return result

    def ecrire_exercices(self, liste: list) -> None:
        """
        Persiste la liste d'exercices passée en paramètre.

        Stratégie diff-based (v0.6.3e correctif 23 avril 2026) :
        plutôt qu'un DELETE+INSERT complet (qui casse `objectif_exos`
        en RESTRICT FK dès que `peupler_v2_depuis_base` a peuplé la
        table), on calcule la différence entre la base et la liste :

        - Exos à supprimer : ids en base mais pas dans `liste` →
          on supprime d'abord leurs liaisons `objectif_exos`, puis les
          exos eux-mêmes.
        - Exos à mettre à jour : ids présents des deux côtés →
          UPDATE in-place (+ reconstruction des liaisons `objectif_exos`).
        - Exos à insérer : ids dans `liste` mais pas en base → INSERT.

        Cette approche préserve les liaisons v2 (`objectif_exos`) pour
        les exos inchangés, ce qui est critique pour les scans
        séquentiels multi-niveaux (scan N10 puis N11 puis N12 :
        chaque scan ne doit pas invalider les liaisons des niveaux
        précédents).
        """
        with self._conn() as conn:
            ids_cibles = {e["id"] for e in liste if e.get("id")}
            rows_en_base = conn.execute("SELECT id FROM exercices").fetchall()
            ids_en_base = {r["id"] for r in rows_en_base}

            a_supprimer = ids_en_base - ids_cibles
            if a_supprimer:
                placeholders = ",".join("?" * len(a_supprimer))
                params = list(a_supprimer)
                # D'abord les liaisons (RESTRICT pour objectif_exos)
                conn.execute(
                    f"DELETE FROM objectif_exos WHERE exercice_id IN ({placeholders})",
                    params
                )
                # v0.14.6.b.2 — DELETE résiduels sur `exercice_objectifs`
                # et `livret_exercices` retirés (tables supprimées).
                conn.execute(
                    f"DELETE FROM exercices WHERE id IN ({placeholders})",
                    params
                )

            # Pour chaque exercice de la liste : INSERT ou UPDATE selon
            # qu'il est déjà en base ou non.
            for e in liste:
                niveau     = e.get("niveau", "")
                sequence   = e.get("sequence", "")
                num        = e.get("num")
                serie_code = e.get("serie_code", "")
                fichier    = e.get("fichier", "")
                num_val = (int(num) if num is not None and str(num).isdigit()
                           else None)

                if e["id"] in ids_en_base:
                    # UPDATE : conserver les liaisons objectif_exos et
                    # livret_exercices (FK RESTRICT et CASCADE
                    # respectivement).
                    # v0.14.6.b.1 — Plus aucune reconstruction de la table
                    # legacy `exercice_objectifs` ici (Q5=b). Cette table
                    # n'est plus lue par aucun service depuis v0.14.6.b.1
                    # et sera droppée en v0.14.6.b.2. Les liaisons
                    # exercice↔objectif sont gérées exclusivement dans
                    # `objectif_exos` (v2), peuplée par
                    # `peupler_v2_depuis_base` dans la chaîne d'import.
                    # v0.11.6 — Ajout de remed_enonce, remed_corrige,
                    # cadre_reponse_lignes_principal, cadre_reponse_lignes_remed.
                    # Convention : le scanner LaTeX ne fournit PAS ces champs
                    # (ils n'ont pas d'équivalent dans le .tex source) ; on les
                    # préserve donc à NULL/0 pour les exos importés. Ces champs
                    # sont uniquement écrits depuis l'UI atelier exercice
                    # (route PUT /api/exercices/<id>) qui passe par cette
                    # fonction via ecrire_exercices(liste). Si le dict `e`
                    # ne les contient pas, on garde les valeurs par défaut.
                    conn.execute(
                        "UPDATE exercices SET "
                        "  serie=?, titre=?, variables=?, enonce=?, corrige=?, "
                        "  niveau=?, sequence=?, num=?, serie_code=?, fichier=?, "
                        "  remed_enonce=?, remed_corrige=?, "
                        "  cadre_reponse_lignes_principal=?, cadre_reponse_lignes_remed=?, "
                        "  type_format=? "
                        "WHERE id=?",
                        (
                            e.get("serie", ""), e.get("titre", ""),
                            e.get("variables", ""), e.get("enonce", ""),
                            e.get("corrige", ""),
                            niveau, sequence, num_val, serie_code, fichier,
                            e.get("remed_enonce", "") or "",
                            e.get("remed_corrige", "") or "",
                            int(e.get("cadre_reponse_lignes_principal") or 0),
                            int(e.get("cadre_reponse_lignes_remed") or 0),
                            # v0.13.5.2.3 — type_format est dérivé de l'énoncé
                            # par services/atomes.py.modifier_exercice avant
                            # qu'on arrive ici. Sécurité : default 'standard'
                            # si la clé manque (cas du scanner LaTeX qui ne la
                            # fournit pas ; mais le scanner sait peupler `enonce`
                            # donc une seconde sauvegarde via l'UI rectifiera).
                            e.get("type_format") or "standard",
                            e["id"],
                        )
                    )
                else:
                    # v0.10.4 — `etat_code` au moment de l'insertion : si le
                    # client le fournit (rare en INSERT — typiquement valeur
                    # de POST manuel via API), on le respecte. Sinon
                    # 'en_cours' par défaut. Pour les UPDATE, on ne touche
                    # PAS à la colonne, ce qui préserve l'état existant
                    # (cas standard : sauvegarde via PUT depuis l'atelier).
                    etat_code_init = e.get("etat_code") or "en_cours"
                    conn.execute(
                        "INSERT INTO exercices "
                        "(id, serie, titre, variables, enonce, corrige, "
                        " niveau, sequence, num, serie_code, fichier, etat_code, "
                        " remed_enonce, remed_corrige, "
                        " cadre_reponse_lignes_principal, cadre_reponse_lignes_remed, "
                        " type_format) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            e["id"], e.get("serie", ""), e.get("titre", ""),
                            e.get("variables", ""), e.get("enonce", ""),
                            e.get("corrige", ""),
                            niveau, sequence, num_val, serie_code, fichier,
                            etat_code_init,
                            e.get("remed_enonce", "") or "",
                            e.get("remed_corrige", "") or "",
                            int(e.get("cadre_reponse_lignes_principal") or 0),
                            int(e.get("cadre_reponse_lignes_remed") or 0),
                            # v0.13.5.2.3 — type_format dérivé de l'énoncé
                            # (cf. services/atomes.py.creer_exercice). Default
                            # 'standard' pour les imports scanner (qui ne le
                            # fournissent pas) — sera recalculé à la prochaine
                            # sauvegarde via l'UI.
                            e.get("type_format") or "standard",
                        )
                    )

                # v0.14.6.b.1 — Reconstruction de `exercice_objectifs` (v1)
                # retirée (Q5=b). Le scanner LaTeX continue de fournir
                # `objectifs_codes` mais cette information est désormais
                # consommée uniquement par la chaîne d'import v2
                # (`peupler_v2_depuis_base` qui peuple `objectif_exos`).
                # La table legacy `exercice_objectifs` n'est plus
                # alimentée et sera droppée en v0.14.6.b.2.

    def lire_livrets_importes(self) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM livrets_de_sequence ORDER BY rowid"
            ).fetchall()
        return [{"id": r["id"], "niveau": r["niveau"],
                 "sequence": r["sequence"], **_uj(r["contenu"], {})} for r in rows]

    def ecrire_livrets_importes(self, liste: list) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM livrets_de_sequence")
            # v0.14.6.b.2 — Table `livret_exercices` supprimée.
            conn.execute("DELETE FROM livret_revisions")
            for l in liste:
                lid = l.get("id", nouveau_id_livret())
                niveau   = l.get("niveau", "")
                sequence = l.get("sequence", "")
                extra = {k: v for k, v in l.items()
                         if k not in ("id","niveau","sequence")}
                conn.execute("INSERT INTO livrets_de_sequence VALUES (?,?,?,?)",
                    (lid, niveau, sequence, _j(extra)))

                # v0.14.6.b.2 — Peuplement de `livret_exercices` supprimé.
                # Cette table était écrite à partir de `exercice_objectifs`
                # (v1) pour résoudre `objectif_id`. Les deux tables ayant
                # disparu, et l'information « ordre d'apparition d'un
                # exercice dans un livret » étant désormais portée par
                # `objectif_exos.ordre` (v2), il n'y a plus rien à faire
                # ici. Le contenu détaillé du livret reste accessible via
                # le champ JSON `contenu` de `livrets_de_sequence` (extra).

                # v0.6.3e : peupler livret_revisions depuis prerequis.exercices_revision
                prereq = l.get("prerequis") or {}
                revisions = prereq.get("exercices_revision", []) or []
                for ordre, rev in enumerate(revisions):
                    if not isinstance(rev, dict):
                        continue
                    niveau_src = rev.get("niveau", "")
                    seq_src    = rev.get("sequence", "")
                    serie_src  = rev.get("serie", "")
                    num_src    = rev.get("num")
                    if not (niveau_src and seq_src and serie_src and num_src is not None):
                        continue
                    try:
                        num_src_int = int(num_src)
                    except (TypeError, ValueError):
                        continue
                    conn.execute(
                        "INSERT OR IGNORE INTO livret_revisions "
                        "(livret_id, niveau_source, seq_source, serie, num, ordre) "
                        "VALUES (?,?,?,?,?,?)",
                        (lid, niveau_src, seq_src, serie_src, num_src_int, ordre)
                    )

    # ── Référentiels versionnés ──────────────────────────────────────────────

    def lister_seances_par_serie(self, referentiel_id: str) -> list[dict]:
        """v0.19.1.4 — Retourne la matrice des séances par série d'un
        référentiel en mode 'par_serie' (modèle historique), au grain
        (séquence, partie, niveau-cible, série).

        Retour : liste de dicts
          { seq_code, partie_numero, niveau_cible ('TB'|'S'),
            serie ('R'|'F'|'A'|'E'), nb_seances }
        Liste vide si le référentiel n'a pas de données par série
        (mode 'par_objectif', ou référentiel non encore peuplé).
        """
        with self._conn() as conn:
            try:
                rows = conn.execute(
                    "SELECT seq_code, partie_numero, niveau_cible, serie, "
                    "       nb_seances "
                    "FROM referentiel_parties_seances WHERE referentiel_id=? "
                    "ORDER BY seq_code, partie_numero, niveau_cible, serie",
                    (referentiel_id,),
                ).fetchall()
            except Exception:
                return []
            return [
                {"seq_code":      r["seq_code"],
                 "partie_numero": r["partie_numero"],
                 "niveau_cible":  r["niveau_cible"],
                 "serie":         r["serie"],
                 "nb_seances":    r["nb_seances"]}
                for r in rows
            ]

    def lire_referentiel(self, referentiel_id: str) -> dict | None:
        """
        Retourne le référentiel complet (entête + thèmes + séquences + objectifs),
        ou None si introuvable.
        """
        with self._conn() as conn:
            entete = conn.execute(
                "SELECT * FROM referentiel_niveaux WHERE id=?", (referentiel_id,)
            ).fetchone()
            if not entete:
                return None
            themes = [dict(r) for r in conn.execute(
                "SELECT code, nom, couleur FROM referentiel_themes "
                "WHERE referentiel_id=? ORDER BY code", (referentiel_id,)
            ).fetchall()]
            seqs = [dict(r) for r in conn.execute(
                "SELECT code, numero, nom, theme_code FROM referentiel_sequences "
                "WHERE referentiel_id=? ORDER BY numero, code", (referentiel_id,)
            ).fetchall()]
            objs_rows = conn.execute(
                "SELECT seq_code, code, nom, fin_cycle, critere_f, critere_a, critere_e "
                "FROM referentiel_objectifs WHERE referentiel_id=? "
                "ORDER BY seq_code, code", (referentiel_id,)
            ).fetchall()
            objs_by_seq: dict[str, list[dict]] = {}
            for r in objs_rows:
                d = dict(r)
                seq = d.pop("seq_code")
                d["fin_cycle"] = bool(d["fin_cycle"])
                objs_by_seq.setdefault(seq, []).append(d)
            for s in seqs:
                s["objectifs"] = objs_by_seq.get(s["code"], [])
            result = dict(entete)
            # etat peut être 'en_cours', 'valide', 'verrouille'
            # On conserve aussi un boolean "verrouille" pour compat d'usage côté API
            result["verrouille"] = result.get("etat") == "verrouille"
            result["themes"]     = themes
            result["sequences"]  = seqs
            return result

    def lister_parties_referentiel(self, referentiel_id: str) -> list[dict] | None:
        """
        v0.19.1 — Retourne la liste à plat des PARTIES de séquence d'un
        référentiel (figé), pour alimenter la barre latérale de l'atelier
        Progression. Chaque partie posable sur le calendrier correspond à
        une (séquence, partie_numero) du référentiel.

        Retour : liste ordonnée de dicts
          { seq_code, seq_numero, seq_nom, theme_code,
            partie_numero, nb_objectifs, nb_seances_prevues }
        triés par (seq_numero, seq_code, partie_numero).

        None si le référentiel est introuvable.

        Note : on lit le SNAPSHOT figé (`referentiel_sequences` /
        `referentiel_objectifs`), pas les tables actives — une progression
        s'appuie toujours sur un référentiel `verrouille`/`utilise`, donc
        sur des données gelées.
        """
        with self._conn() as conn:
            entete = conn.execute(
                "SELECT id FROM referentiel_niveaux WHERE id=?",
                (referentiel_id,),
            ).fetchone()
            if not entete:
                return None
            seqs = conn.execute(
                "SELECT code, numero, nom, theme_code "
                "FROM referentiel_sequences WHERE referentiel_id=? "
                "ORDER BY numero, code",
                (referentiel_id,),
            ).fetchall()
            # Agrégat des objectifs par (seq_code, partie_numero) : nombre
            # d'objectifs + somme des nb_seances.
            agg = conn.execute(
                "SELECT seq_code, partie_numero, "
                "       COUNT(*) AS nb_objectifs, "
                "       COALESCE(SUM(nb_seances), 0) AS nb_seances_prevues "
                "FROM referentiel_objectifs WHERE referentiel_id=? "
                "GROUP BY seq_code, partie_numero",
                (referentiel_id,),
            ).fetchall()
            agg_by_key: dict[tuple, dict] = {}
            for a in agg:
                agg_by_key[(a["seq_code"], a["partie_numero"])] = {
                    "nb_objectifs":      int(a["nb_objectifs"]),
                    "nb_seances_prevues": int(a["nb_seances_prevues"] or 0),
                }

            # v0.19.1.3 — Source des parties : la table figée
            # `referentiel_parties` (peuplée au verrouillage). C'est la photo
            # autoportante du découpage. Fallback (référentiels figés avant
            # v0.19.1.3, non re-verrouillés, ou données alpha incomplètes) :
            # dériver les parties des partie_numero présents dans les
            # objectifs, sinon une partie 1 par séquence.
            rows_parties = conn.execute(
                "SELECT seq_code, numero FROM referentiel_parties "
                "WHERE referentiel_id=? ORDER BY seq_code, numero",
                (referentiel_id,),
            ).fetchall()
            parties_by_seq: dict[str, list[int]] = {}
            if rows_parties:
                for rp in rows_parties:
                    parties_by_seq.setdefault(rp["seq_code"], []).append(
                        rp["numero"]
                    )
            else:
                # Fallback : parties déduites des objectifs.
                for a in agg:
                    parties_by_seq.setdefault(a["seq_code"], []).append(
                        a["partie_numero"]
                    )
            for k in parties_by_seq:
                parties_by_seq[k] = sorted(set(parties_by_seq[k]))

            result = []
            for s in seqs:
                code = s["code"]
                parties = parties_by_seq.get(code)
                # Séquence sans partie connue → exposer une partie 1 (posable).
                if not parties:
                    parties = [1]
                for pnum in parties:
                    info = agg_by_key.get((code, pnum), {
                        "nb_objectifs": 0, "nb_seances_prevues": 0,
                    })
                    result.append({
                        "seq_code":           code,
                        "seq_numero":         s["numero"],
                        "seq_nom":            s["nom"],
                        "theme_code":         s["theme_code"],
                        "partie_numero":      pnum,
                        "nb_objectifs":       info["nb_objectifs"],
                        "nb_seances_prevues": info["nb_seances_prevues"],
                    })
            return result

    def lister_referentiels(self, niveau: str | None = None) -> list[dict]:
        """Retourne l'entête de tous les référentiels, éventuellement filtrés par niveau."""
        with self._conn() as conn:
            if niveau:
                rows = conn.execute(
                    "SELECT * FROM referentiel_niveaux WHERE niveau=? "
                    "ORDER BY version, id", (niveau,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM referentiel_niveaux ORDER BY niveau, version, id"
                ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["verrouille"] = d.get("etat") == "verrouille"
                result.append(d)
            return result

    def creer_referentiel(self, referentiel: dict) -> str:
        """
        Crée un référentiel complet en une seule transaction.
        Attendu en entrée :
          { id, niveau, version, date_debut?, date_fin?, description?,
            etat?, verrouille?,  # rétrocompat : verrouille=True → etat='verrouille'
            themes: [...], sequences: [{code, numero, nom,
            theme_code, objectifs: [...]}] }
        Retourne l'id créé. Échoue si l'id existe déjà (contrainte UNIQUE).

        État par défaut : 'en_cours'. Si la clé `verrouille=True` est présente
        (compat v0.6.0a), l'état est forcé à 'verrouille'.
        """
        etat = referentiel.get("etat")
        if not etat:
            etat = "verrouille" if referentiel.get("verrouille") else "en_cours"
        if etat not in ("en_cours", "valide", "verrouille"):
            raise ValueError(f"Etat invalide : {etat}")

        with self._conn() as conn:
            conn.execute("""
                INSERT INTO referentiel_niveaux
                  (id, niveau, version, date_debut, date_fin, description, etat)
                VALUES (?,?,?,?,?,?,?)
            """, (
                referentiel["id"],
                referentiel["niveau"],
                referentiel["version"],
                referentiel.get("date_debut"),
                referentiel.get("date_fin"),
                referentiel.get("description", ""),
                etat,
            ))
            for t in referentiel.get("themes", []):
                conn.execute("""
                    INSERT INTO referentiel_themes (referentiel_id, code, nom, couleur)
                    VALUES (?,?,?,?)
                """, (
                    referentiel["id"], t["code"], t["nom"], t.get("couleur", ""),
                ))
            for s in referentiel.get("sequences", []):
                conn.execute("""
                    INSERT INTO referentiel_sequences
                      (referentiel_id, code, numero, nom, theme_code)
                    VALUES (?,?,?,?,?)
                """, (
                    referentiel["id"], s["code"], s["numero"], s["nom"],
                    s.get("theme_code"),
                ))
                for o in s.get("objectifs", []):
                    conn.execute("""
                        INSERT INTO referentiel_objectifs
                          (referentiel_id, seq_code, code, nom, fin_cycle,
                           critere_f, critere_a, critere_e)
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (
                        referentiel["id"], s["code"], o["code"], o["nom"],
                        int(bool(o.get("fin_cycle", False))),
                        o.get("critere_f", "") or o.get("criteres", {}).get("2", ""),
                        o.get("critere_a", "") or o.get("criteres", {}).get("3", ""),
                        o.get("critere_e", "") or o.get("criteres", {}).get("4", ""),
                    ))
        return referentiel["id"]

    def changer_etat_referentiel(self, referentiel_id: str, etat: str) -> None:
        """
        Change l'état d'un référentiel. Les transitions autorisées sont :
          - en_cours → valide        (validation manuelle)
          - valide → verrouille      (auto, dès la 1re évaluation)
          - valide → en_cours        (non prévu mais techniquement autorisé)
          - verrouille → valide      (déverrouillage manuel, à condition d'avoir
                                       supprimé les évaluations au préalable)

        Remarque : cette méthode ne fait aucun contrôle de cohérence et ne
        supprime aucune évaluation. La logique de supervision (interdire le
        déverrouillage si des évaluations existent, effacer les évaluations
        avant de déverrouiller, etc.) est du ressort de la couche service.
        """
        if etat not in ("en_cours", "valide", "verrouille"):
            raise ValueError(f"Etat invalide : {etat}")
        with self._conn() as conn:
            conn.execute(
                "UPDATE referentiel_niveaux SET etat=? WHERE id=?",
                (etat, referentiel_id)
            )

    # Alias de transition auto : valide → verrouille (appelé par les routes
    # qui enregistrent des évaluations). Idempotent : si déjà verrouille, no-op.
    def verrouiller_referentiel(self, referentiel_id: str) -> None:
        """
        Verrouille un référentiel : transition auto depuis valide (ou en_cours)
        dès qu'une évaluation est saisie pour une classe qui l'utilise.
        Idempotent.
        """
        with self._conn() as conn:
            conn.execute("""
                UPDATE referentiel_niveaux
                   SET etat='verrouille'
                 WHERE id=? AND etat != 'verrouille'
            """, (referentiel_id,))

    def trouver_referentiel_equivalent(self, niveau: str, themes: list[dict],
                                        sequences: list[dict]) -> str | None:
        """
        Retourne l'id d'un référentiel déjà existant qui a exactement le même
        contenu (option V1 B : comparaison normalisée par clé canonique).

        La clé canonique ignore :
        - l'ordre des thèmes / séquences / objectifs
        - les variations d'espaces, la casse et les accents sur les noms
        - les critères d'évaluation (facultatifs, souvent différents d'un cycle
          à l'autre sans que la structure pédagogique change).

        Deux référentiels sont équivalents si, pour le même niveau, ils ont :
        - le même ensemble {code thème → nom normalisé}
        - le même ensemble {code séquence → (nom normalisé, theme_code, ensemble d'objectifs {code → nom normalisé})}
        """
        cle_nouvelle = _cle_referentiel(niveau, themes, sequences)
        for r in self.lister_referentiels(niveau):
            existant = self.lire_referentiel(r["id"])
            if not existant:
                continue
            cle_existante = _cle_referentiel(
                existant["niveau"], existant["themes"], existant["sequences"]
            )
            if cle_existante == cle_nouvelle:
                return r["id"]
        return None

    # ── Établissements ───────────────────────────────────────────────────────

    def lire_etablissements(self) -> list[dict]:
        """Retourne tous les établissements, triés par nom."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM etablissements ORDER BY nom"
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["uai"] = d.get("uai") or ""   # normaliser NULL → ""
            out.append(d)
        return out

    def lire_etablissement_par_id(self, etab_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM etablissements WHERE id=?", (etab_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["uai"] = d.get("uai") or ""
        return d

    def lire_etablissement_par_nom(self, nom: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM etablissements WHERE nom=?", (nom,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["uai"] = d.get("uai") or ""
        return d

    def ecrire_etablissement(self, etab: dict) -> None:
        """Upsert par id. Les champs vides sont conservés vides."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO etablissements
                  (id, nom, uai, academie, ville, adresse, etat)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  nom=excluded.nom, uai=excluded.uai,
                  academie=excluded.academie, ville=excluded.ville,
                  adresse=excluded.adresse, etat=excluded.etat
            """, (
                etab["id"], etab["nom"],
                etab.get("uai") or None,
                etab.get("academie",""), etab.get("ville",""),
                etab.get("adresse",""), etab.get("etat","propose"),
            ))

    def supprimer_etablissement(self, etab_id: str) -> None:
        """
        Supprime un établissement. Les progressions/classes référençant cet
        établissement ont un ON DELETE RESTRICT → levée si utilisé.
        """
        with self._conn() as conn:
            conn.execute("DELETE FROM etablissements WHERE id=?", (etab_id,))

    def conn(self):
        """
        Accès public au context manager de connexion (utilisé par les
        services qui ont besoin d'exécuter des requêtes ad hoc,
        notamment le cache_api du service calendrier).
        """
        return self._conn()

    def verrouiller_progression(self, progression_id: str) -> None:
        """
        Transition auto vers 'verrouille'. Idempotent. Appelée quand une
        évaluation est saisie pour une classe qui utilise la progression.
        """
        with self._conn() as conn:
            conn.execute("""
                UPDATE progressions
                   SET etat='verrouille'
                 WHERE id=? AND etat != 'verrouille'
            """, (progression_id,))

    def changer_etat_progression(self, progression_id: str, etat: str) -> None:
        """
        Change explicitement l'état d'une progression. Utilisé pour les
        transitions manuelles en_cours ↔ valide initiées par l'UI. Une fois
        en 'verrouille', l'état ne peut plus être changé que par la couche
        service (logique à venir pour déverrouiller avec suppression des
        évaluations, hors scope v0.6.3c).
        """
        if etat not in ("en_cours", "valide", "verrouille"):
            raise ValueError(f"Etat invalide : {etat}")
        with self._conn() as conn:
            conn.execute(
                "UPDATE progressions SET etat=? WHERE id=?",
                (etat, progression_id)
            )

    # ── Progressions ─────────────────────────────────────────────────────────

    def lire_progression_par_id(self, progression_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("""
                SELECT p.*,
                       e.nom      AS etab_nom,
                       e.academie AS etab_academie
                FROM progressions p
                LEFT JOIN etablissements e ON e.id = p.etablissement_id
                WHERE p.id=?
            """, (progression_id,)).fetchone()
            if not row:
                return None
            prog = dict(row)
            # Dénormalisation : etablissement = nom (compat ascendante)
            prog["etablissement"] = prog.pop("etab_nom") or ""
            prog["etab_academie"] = prog.get("etab_academie") or ""
            rows_cr = conn.execute("""
                SELECT * FROM creneaux WHERE progression_id=? ORDER BY ordre
            """, (progression_id,)).fetchall()
            ref_id = prog.get("referentiel_id")
            creneaux = []
            for r in rows_cr:
                cr = {
                    "id":            r["id"],
                    "sequence":      r["seq_code"],
                    "partie_debut":  r["partie_debut"],
                    "partie_fin":    r["partie_fin"],
                    "partie":        r["partie"],
                    "periode":       r["periode"],
                    "date_debut":    r["date_debut"],
                    "date_fin":      r["date_fin"],
                    "revisions":     r["revisions"] or "",
                    "ordre":         r["ordre"],
                    "objectifs":     [],
                    "objectifs_exos": [],
                }
                # v0.19.0 — Les objectifs du créneau sont lus depuis le
                # référentiel verrouillé lié à la progression (fini SequenceDB).
                # Un créneau couvre une seule partie de séquence (partie_debut
                # == partie_fin) : on prend les objectifs de cette séquence
                # dont partie_numero == la partie du créneau.
                # v0.19.1.5 — IMPORTANT : la partie numérique est portée par
                # `partie_debut` (entier). Le champ `partie` est un LIBELLÉ
                # texte optionnel (ex. « 1ère partie : Pythagore ») — il ne
                # doit jamais servir de numéro de partie (sinon le WHERE
                # partie_numero=<libellé> ne matche rien et les objectifs du
                # créneau ressortent vides).
                if ref_id:
                    partie_creneau = r["partie_debut"] or 1
                    rows_obj = conn.execute("""
                        SELECT code, nom, fin_cycle, critere_f, critere_a,
                               critere_e, partie_numero, nb_seances
                        FROM referentiel_objectifs
                        WHERE referentiel_id=? AND seq_code=? AND partie_numero=?
                        ORDER BY code
                    """, (ref_id, r["seq_code"], partie_creneau)).fetchall()
                    cr["objectifs"] = [
                        {
                            "code":          o["code"],
                            "nom":           o["nom"],
                            "fin_cycle":     bool(o["fin_cycle"]),
                            "critere_f":     o["critere_f"],
                            "critere_a":     o["critere_a"],
                            "critere_e":     o["critere_e"],
                            "partie_numero": o["partie_numero"],
                            "nb_seances":    o["nb_seances"],
                        }
                        for o in rows_obj
                    ]
                rows_exos = conn.execute("""
                    SELECT obj_code, exos_F, exos_A, exos_E
                    FROM creneau_objectifs_exos WHERE creneau_id=?
                    ORDER BY obj_code
                """, (r["id"],)).fetchall()
                cr["objectifs_exos"] = [dict(e) for e in rows_exos]
                creneaux.append(cr)
            prog["creneaux"] = creneaux
            prog["periodes"] = sorted({
                c["periode"] for c in creneaux if c.get("periode")
            })
        return prog

    def lire_progression(self, niveau: str, annee: str | None = None,
                         etablissement: str = "") -> dict | None:
        """
        Retourne la progression correspondant aux critères, ou None.
        Si annee est fourni, cherche (niveau, annee, etablissement).
        etablissement peut être fourni sous forme de nom (texte) ; la
        résolution passe par la table etablissements. Nom vide → fallback
        "Non renseigné" (cohérence avec ecrire_progression).
        Sinon, retourne la plus récente pour ce niveau.
        """
        with self._conn() as conn:
            if annee:
                nom_etab = etablissement or "Non renseigné"
                row = conn.execute("""
                    SELECT p.id
                    FROM progressions p
                    JOIN etablissements e ON e.id = p.etablissement_id
                    WHERE p.niveau=? AND p.annee=? AND e.nom=?
                """, (niveau, annee, nom_etab)).fetchone()
                if not row:
                    return None
                return self.lire_progression_par_id(row["id"])
        toutes = self.lister_progressions(niveau)
        if not toutes:
            return None
        return self.lire_progression_par_id(toutes[-1]["id"])

    def lire_progression_par_triplet(self, niveau: str, annee: str,
                                     etablissement_id: str) -> dict | None:
        """
        Retourne la progression identifiée par la clé métier complète
        (niveau, annee, etablissement_id), ou None.

        Contrairement à lire_progression qui prend le nom d'établissement,
        cette méthode travaille directement avec l'UUID opaque. Utilisée
        par l'endpoint /api/progression/<niveau>/rechercher où l'UI envoie
        l'etablissement_id sélectionné dans la liste déroulante.

        Lève RuntimeError si plus d'une progression est trouvée (impossible
        avec la contrainte UNIQUE (niveau, annee, etablissement_id), mais
        garde défensive en cas d'incohérence).
        """
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT id FROM progressions
                WHERE niveau=? AND annee=? AND etablissement_id=?
                LIMIT 2
            """, (niveau, annee, etablissement_id)).fetchall()
        if not rows:
            return None
        if len(rows) > 1:
            raise RuntimeError(
                f"Incohérence base : {len(rows)} progressions pour "
                f"({niveau!r}, {annee!r}, {etablissement_id!r}) — "
                f"la contrainte UNIQUE devrait l'empêcher."
            )
        return self.lire_progression_par_id(rows[0]["id"])

    def ecrire_progression(self, progression: dict) -> None:
        """
        Upsert d'une progression par sa clé métier (niveau, annee, etablissement_id).
        Si une progression existe déjà pour cette clé, elle est mise à jour
        (ses créneaux sont remplacés par ceux fournis). Son id opaque est
        préservé, peu importe l'id fourni en entrée.
        Sinon, une nouvelle progression est créée avec l'id fourni (ou un
        nouvel UUID si absent).

        Accepte soit etablissement_id (prioritaire) soit etablissement (nom) :
        dans ce 2ème cas, crée l'établissement avec état 'propose' s'il
        n'existe pas encore.
        """
        niv  = progression.get("niveau", "")
        ann  = progression.get("annee", "")
        ref  = progression.get("referentiel_id")  # peut être None
        etat = progression.get("etat", "en_cours")

        with self._conn() as conn:
            # Résoudre etablissement_id
            etab_id = progression.get("etablissement_id") or None
            if not etab_id:
                nom_etab = progression.get("etablissement", "").strip()
                # Pour compatibilité tests/appels legacy sans établissement,
                # on tolère un nom vide → établissement fallback "Non renseigné"
                # avec état 'propose'. L'UI invitera l'enseignant à le compléter.
                if not nom_etab:
                    nom_etab = "Non renseigné"
                row = conn.execute(
                    "SELECT id FROM etablissements WHERE nom=?", (nom_etab,)
                ).fetchone()
                if row:
                    etab_id = row[0]
                else:
                    from persistence.ids import nouveau_id_etablissement
                    etab_id = nouveau_id_etablissement()
                    conn.execute("""
                        INSERT INTO etablissements (id, nom, etat)
                        VALUES (?, ?, 'propose')
                    """, (etab_id, nom_etab))

            # Chercher une progression existante sur la clé métier
            row = conn.execute("""
                SELECT id FROM progressions
                WHERE niveau=? AND annee=? AND etablissement_id=?
            """, (niv, ann, etab_id)).fetchone()

            if row:
                # Existe : on conserve son id, on met à jour le reste
                pid = row["id"]
                conn.execute("""
                    UPDATE progressions
                       SET referentiel_id=?, etat=?
                     WHERE id=?
                """, (ref, etat, pid))
            else:
                # Nouvelle progression : utiliser l'id fourni ou en générer un
                pid = progression.get("id")
                if not pid:
                    from persistence.ids import nouveau_id_progression
                    pid = nouveau_id_progression()
                conn.execute("""
                    INSERT INTO progressions
                      (id, niveau, annee, etablissement_id, referentiel_id, etat)
                    VALUES (?,?,?,?,?,?)
                """, (pid, niv, ann, etab_id, ref, etat))

            # v0.19.0 — Une progression « consomme » son référentiel : si elle
            # est liée à un référentiel `verrouille`, celui-ci passe `utilise`
            # (il devient alors non déverrouillable). Idempotent : un
            # référentiel déjà `utilise` reste `utilise` ; un référentiel
            # `en_cours`/`valide` n'est pas promu (cas anormal, on ne force pas).
            if ref:
                conn.execute(
                    "UPDATE referentiel_niveaux SET etat='utilise' "
                    "WHERE id=? AND (etat='verrouille' OR (source='externe' "
                    "AND etat IN ('en_cours', 'valide')))",
                    (ref,),
                )

            # Mettre à jour l'id dans le dict source pour que l'appelant sache
            # quel id a finalement été utilisé (utile pour les créneaux qui
            # doivent référencer la progression par id).
            progression["id"] = pid
            progression["etablissement_id"] = etab_id

            conn.execute("DELETE FROM creneaux WHERE progression_id=?", (pid,))
            for c in progression.get("creneaux", []):
                rang = c.get("rang", 1) or 1
                # Rétrocompat : accepter les anciennes clés rang_debut / rang_fin
                partie_debut = (c.get("partie_debut") or c.get("rang_debut") or rang) or 1
                partie_fin   = (c.get("partie_fin")   or c.get("rang_fin")   or partie_debut)
                conn.execute("""
                    INSERT INTO creneaux
                      (id, progression_id, seq_code, partie_debut, partie_fin,
                       partie, periode, date_debut, date_fin, revisions, ordre)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (c["id"], pid, c.get("sequence",""),
                      partie_debut, partie_fin,
                      c.get("partie"), c.get("periode"),
                      c.get("date_debut"), c.get("date_fin"),
                      c.get("revisions",""), c.get("ordre",0)))
                # Exercices par objectif (plan de travail)
                for exo in c.get("objectifs_exos", []):
                    conn.execute("""
                        INSERT OR REPLACE INTO creneau_objectifs_exos
                          (creneau_id, obj_code, exos_F, exos_A, exos_E)
                        VALUES (?,?,?,?,?)
                    """, (c["id"], exo["obj_code"],
                          exo.get("exos_F",""), exo.get("exos_A",""),
                          exo.get("exos_E","")))

    def lister_progressions(self, niveau: str) -> list[dict]:
        with self._conn() as conn:
            # v0.19.0 — Les progressions 'annule' (suppression logique) sont
            # exclues de l'affichage.
            rows = conn.execute("""
                SELECT p.id, p.annee, e.nom AS etablissement
                FROM progressions p
                JOIN etablissements e ON e.id = p.etablissement_id
                WHERE p.niveau=? AND p.etat != 'annule'
                ORDER BY p.annee, e.nom
            """, (niveau,)).fetchall()
        return [{"id": r["id"], "annee": r["annee"],
                 "etablissement": r["etablissement"]} for r in rows]

    # ── Multi-années ──────────────────────────────────────────────────────────

    def lire_annees_disponibles(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT annee FROM classes WHERE annee!='' ORDER BY annee DESC"
            ).fetchall()
        return [r["annee"] for r in rows]

    def lire_etablissements_disponibles(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT DISTINCT e.nom
                FROM classes c
                JOIN etablissements e ON e.id = c.etablissement_id
                WHERE e.nom != '' ORDER BY e.nom
            """).fetchall()
        return [r["nom"] for r in rows]

    def lire_classes_par_annee(self, annee: str) -> dict:
        return self.lire_classes(annee=annee)

    def lire_classes_par_annee_etab(self, annee: str, etablissement: str) -> dict:
        return self.lire_classes(annee=annee, etablissement=etablissement)

    # ── Réinitialisation ──────────────────────────────────────────────────────

    def reset_reference(self) -> list[str]:
        """
        Vide toutes les données de référence (atomes pédagogiques
        régénérés par l'import .tex). Préserve les référentiels
        versionnés (cycles, themes, sequences_du_cycle, referentiel_*)
        qui ne dépendent pas du scan.

        Ordre de suppression : tables filles d'abord, pour respecter
        les FK. Certaines FK sont RESTRICT (objectif_exos → exercices)
        ce qui oblige à vider la table fille explicitement, même si
        les tables en CASCADE se videraient automatiquement par
        cascade. On reste explicite partout pour que l'ordre documente
        les dépendances.
        """
        with self._conn() as conn:
            # 1. Tables filles des livrets et exercices
            conn.execute("DELETE FROM livret_revisions")
            # v0.14.6.b.2 — `livret_exercices` et `exercice_objectifs` (v1)
            # supprimées.
            conn.execute("DELETE FROM objectif_exos")        # RESTRICT sur exercices
            # 2. Tables filles des séquences et parties
            conn.execute("DELETE FROM partie_precedences")
            conn.execute("DELETE FROM objectifs")         # SET NULL sur methodes
            conn.execute("DELETE FROM sequence_parties")     # CASCADE sur sequences_par_niveau
            conn.execute("DELETE FROM sequences_par_niveau")
            # 3. Tables filles des méthodes et notions
            conn.execute("DELETE FROM methode_notions")
            # 4. Tables « atomiques » principales
            conn.execute("DELETE FROM exercices")
            # v0.14.6.b.2 — `objectifs` (v1) supprimée.
            conn.execute("DELETE FROM methodes")
            conn.execute("DELETE FROM notions")
            # v0.6.4 — atome_section_items est cascadé via atome_sections
            conn.execute("DELETE FROM atome_sections")
            conn.execute("DELETE FROM annexes")
            conn.execute("DELETE FROM livrets_de_sequence")
        return [
            "livret_revisions",
            "objectif_exos", "partie_precedences", "objectifs",
            "sequence_parties", "sequences_par_niveau", "methode_notions",
            "exercices", "methodes", "notions",
            "atome_sections", "atome_section_items",
            "annexes", "livrets_de_sequence",
        ]

    def reset_suivi(self) -> list[str]:
        """
        Vide toutes les données liées au suivi d'élèves (option A) : classes,
        élèves, progressions, créneaux, versions, niveaux saisis, exercices
        cochés. Les référentiels versionnés restent en base — ils sont
        immuables et peuvent être réutilisés au prochain import.
        """
        with self._conn() as conn:
            # L'ordre respecte les FK : d'abord les tables dépendantes,
            # ensuite les tables de référence. Les DELETE CASCADE couvrent
            # déjà une partie mais on est explicite pour la lisibilité.
            conn.execute("DELETE FROM niveaux")
            conn.execute("DELETE FROM suivi")
            conn.execute("DELETE FROM versions_classes")
            conn.execute("DELETE FROM versions")
            conn.execute("DELETE FROM creneau_objectifs_exos")
            conn.execute("DELETE FROM creneaux")
            conn.execute("DELETE FROM progressions")
            conn.execute("DELETE FROM eleves_classes")
            conn.execute("DELETE FROM eleves")
            conn.execute("DELETE FROM classes")
        return ["niveaux", "suivi", "versions_classes", "versions",
                "creneau_objectifs_exos", "creneaux", "progressions",
                "eleves_classes", "eleves", "classes"]
