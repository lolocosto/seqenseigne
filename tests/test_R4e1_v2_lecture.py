"""tests/test_R4e1_v2_lecture.py — R4e1.

Tests de la visualisation lecture seule du modèle v2.

Deux axes :
  1. Service services.v2_lecture — tests unitaires purs sur une connexion
     sqlite3 en mémoire peuplée manuellement.
  2. Route /api/v2/sequences-par-niveau/<niveau>/<sequence_code> — tests
     d'intégration via le client Flask (réutilise la fixture `client`
     du conftest global si elle existe, sinon une fixture locale).

Principe : aucune dépendance au peuplement R4b. On peuple la base avec
quelques lignes minimales, suffisantes pour valider la structure du
retour et l'ordre de tri.
"""

from __future__ import annotations
import sqlite3
import pytest


# ── Schéma minimal des 5 tables v2 + tables jointes ──────────────────────────
# On réplique juste ce qu'il faut pour que le service tourne sans dépendre
# du schema.sql complet. Si les colonnes changent en R4f, ces DDL devront
# être mis à jour ici.

_SCHEMA_TEST = """
CREATE TABLE cycles (
    code        TEXT PRIMARY KEY,
    nom         TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE themes (
    id           TEXT PRIMARY KEY,
    cycle_code   TEXT NOT NULL,
    code         TEXT NOT NULL,
    nom          TEXT NOT NULL,
    code_couleur TEXT NOT NULL DEFAULT '',
    description  TEXT NOT NULL DEFAULT '',
    ordre        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE sequences_du_cycle (
    id         TEXT PRIMARY KEY,
    cycle_code TEXT NOT NULL,
    code       TEXT NOT NULL,
    numero     INTEGER NOT NULL,
    nom        TEXT NOT NULL,
    theme_id   TEXT
);

CREATE TABLE methodes (
    id    TEXT PRIMARY KEY,
    titre TEXT NOT NULL DEFAULT '',
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);

CREATE TABLE exercices (
    id         TEXT PRIMARY KEY,
    serie      TEXT NOT NULL,
    titre        TEXT NOT NULL DEFAULT '',
    variables  TEXT NOT NULL DEFAULT '',
    enonce     TEXT NOT NULL DEFAULT '',
    corrige    TEXT NOT NULL DEFAULT '',
    niveau     TEXT NOT NULL DEFAULT '',
    sequence   TEXT NOT NULL DEFAULT '',
    num        INTEGER,
    serie_code TEXT NOT NULL DEFAULT '',
    fichier    TEXT NOT NULL DEFAULT '',
    etat_code  TEXT NOT NULL DEFAULT 'en_cours'
);

CREATE TABLE sequences_par_niveau (
    id            TEXT PRIMARY KEY,
    niveau        TEXT NOT NULL,
    sequence_code TEXT NOT NULL,
    parametres    TEXT NOT NULL DEFAULT '',
    UNIQUE (niveau, sequence_code)
);

CREATE TABLE sequence_parties (
    id                     TEXT PRIMARY KEY,
    sequence_par_niveau_id TEXT NOT NULL,
    numero                 INTEGER NOT NULL,
    UNIQUE (sequence_par_niveau_id, numero)
);

CREATE TABLE partie_precedences (
    partie_id        TEXT NOT NULL,
    precedent_niveau TEXT NOT NULL,
    precedent_seq    TEXT NOT NULL,
    PRIMARY KEY (partie_id, precedent_niveau, precedent_seq)
);

CREATE TABLE objectifs (
    id         TEXT PRIMARY KEY,
    partie_id  TEXT NOT NULL,
    code       TEXT NOT NULL,
    nom        TEXT NOT NULL DEFAULT '',
    methode_id TEXT,
    critere_F  TEXT NOT NULL DEFAULT '',
    critere_A  TEXT NOT NULL DEFAULT '',
    critere_E  TEXT NOT NULL DEFAULT '',
    fin_cycle  TEXT NOT NULL DEFAULT 'N',
    UNIQUE (partie_id, code)
);
CREATE TABLE IF NOT EXISTS notions (
    id     TEXT PRIMARY KEY,
    titre  TEXT NOT NULL DEFAULT '',
    corps  TEXT NOT NULL DEFAULT '',
    niveau TEXT NOT NULL DEFAULT '',
    sequence TEXT NOT NULL DEFAULT '',
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE objectif_notions (
    objectif_id TEXT NOT NULL,
    notion_id   TEXT NOT NULL,
    ordre       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, notion_id)
);


CREATE TABLE objectif_exos (
    objectif_id    TEXT NOT NULL,
    serie          TEXT NOT NULL,
    exercice_id    TEXT NOT NULL,
    ordre          INTEGER NOT NULL DEFAULT 0,
    origin_niveau  TEXT,
    origin_seq     TEXT,
    origin_serie   TEXT,
    origin_num     INTEGER,
    PRIMARY KEY (objectif_id, serie, exercice_id),
    UNIQUE (objectif_id, serie, ordre)
);
"""


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def conn():
    """Connexion sqlite3 en mémoire avec schéma v2 minimal appliqué."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA_TEST)
    yield c
    c.close()


@pytest.fixture
def base_peuplee(conn):
    """Peuple une petite arborescence v2 pour les tests :

        Cycle C04
        Thème A — "Nombres et Calculs" (code_couleur=nombres)
        Séquence du cycle S03 — "Fractions" (thème A)

        sn_n11_s03 : N11 / S03 / parametres="\\xintdefvar A:=5;"
          ├─ partie 1 (pt_p1)
          │    precedences : N10/S01
          │    ├─ objectif 01 — "Connaître le cours" (pas de méthode)
          │    │     exos : F[1,2], A[1], E[1] (triés par ordre)
          │    └─ objectif 02 — "Méthode M1" (liée à me_m1)
          │          exos : R[1] (origin N10/S01/F), EA[1], F[1,2,3]
          └─ partie 2 (pt_p2)
               └─ objectif 03 — "Méthode M2" (liée à me_m2)
                     exos : (vide — toutes les séries à [])
    """
    conn.executescript("""
        INSERT INTO cycles (code, nom) VALUES ('C04', 'Cycle 4');

        INSERT INTO themes (id, cycle_code, code, nom, code_couleur, ordre)
        VALUES ('th_A', 'C04', 'A', 'Nombres et Calculs', 'nombres', 1);

        INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
        VALUES ('sc_s03', 'C04', 'S03', 3, 'Fractions', 'th_A');

        INSERT INTO methodes (id, titre) VALUES
            ('me_m1', 'Simplifier une fraction'),
            ('me_m2', 'Additionner deux fractions');

        INSERT INTO exercices (id, serie, titre, niveau, sequence, num, serie_code, fichier)
        VALUES
            ('ex_f1', 'fondamental', 'Exo F1', 'N11', 'S03', 1, 'F',  'N11S03F01.tex'),
            ('ex_f2', 'fondamental', 'Exo F2', 'N11', 'S03', 2, 'F',  'N11S03F02.tex'),
            ('ex_f3', 'fondamental', 'Exo F3', 'N11', 'S03', 3, 'F',  'N11S03F03.tex'),
            ('ex_a1', 'avancé',      'Exo A1', 'N11', 'S03', 1, 'A',  'N11S03A01.tex'),
            ('ex_e1', 'exploration', 'Exo E1', 'N11', 'S03', 1, 'E',  'N11S03E01.tex'),
            ('ex_ea1','approche',    'Activité 1','N11','S03',1, 'AE', 'N11S03AE01.tex'),
            -- Exo d'origine N10 pour la révision :
            ('ex_r1', 'fondamental', 'Exo N10 S01 F1', 'N10', 'S01', 1, 'F', 'N10S01F01.tex');

        INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
        VALUES
            ('sn_n11_s03', 'N11', 'S03', '\\xintdefvar A:=5;'),
            ('sn_n10_s03', 'N10', 'S03', ''),
            ('sn_n11_s05', 'N11', 'S05', '');

        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
            ('pt_p1', 'sn_n11_s03', 1),
            ('pt_p2', 'sn_n11_s03', 2);

        INSERT INTO partie_precedences (partie_id, precedent_niveau, precedent_seq)
        VALUES
            ('pt_p1', 'N10', 'S01');

        INSERT INTO objectifs (id, partie_id, code, nom, methode_id,
                                  critere_F, critere_A, critere_E)
        VALUES
            ('ob_01', 'pt_p1', '01', 'Connaître le cours', NULL,
             'Notes cahier', 'Fiches résumé', 'Oral prof'),
            ('ob_02', 'pt_p1', '02', 'Simplifier une fraction', 'me_m1',
             'critère F obj02', 'critère A obj02', 'critère E obj02'),
            ('ob_03', 'pt_p2', '03', 'Additionner deux fractions', 'me_m2',
             '', '', '');

        -- Exos obj 01 : F[1,2], A[1], E[1] — pas de R ni EA.
        INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre,
                                   origin_niveau, origin_seq, origin_serie,
                                   origin_num) VALUES
            ('ob_01', 'F', 'ex_f1', 1, NULL, NULL, NULL, 1),
            ('ob_01', 'F', 'ex_f2', 2, NULL, NULL, NULL, 2),
            ('ob_01', 'A', 'ex_a1', 1, NULL, NULL, NULL, 1),
            ('ob_01', 'E', 'ex_e1', 1, NULL, NULL, NULL, 1);

        -- Exos obj 02 : R[1] (origin N10), EA[1], F[3 exos].
        -- R4e4a : la contrainte UNIQUE(objectif_id, serie, ordre) impose
        -- des `ordre` uniques par série — on ne peut plus insérer F à
        -- l'ordre 3 puis 1 puis 2 avec des doublons. On les ordonne donc
        -- directement 1/2/3 ici ; la lecture doit retourner les exos
        -- triés par ordre croissant.
        -- v0.11.2 — La ligne ('ob_02', 'R', 'ex_r1', 1, 'N10', 'S01', 'F', 1)
        -- a été retirée. La série 'R' n'existe plus comme attribut
        -- d'exercice ; les révisions sont gérées via la table
        -- partie_exos_revision_approche, pas objectif_exos.
        INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre,
                                   origin_niveau, origin_seq, origin_serie,
                                   origin_num) VALUES
            ('ob_02', 'AE', 'ex_ea1', 1, NULL,  NULL,  NULL, 1),
            ('ob_02', 'F',  'ex_f1',  1, NULL,  NULL,  NULL, 1),
            ('ob_02', 'F',  'ex_f2',  2, NULL,  NULL,  NULL, 2),
            ('ob_02', 'F',  'ex_f3',  3, NULL,  NULL,  NULL, 3);
        -- obj 03 : aucun exo.
    """)
    conn.commit()
    return conn


# ═════════════════════════════════════════════════════════════════════════════
# 1. Tests du service — unitaires, sans Flask
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_lecture import (
    lire_sequence_par_niveau,
    SequenceParNiveauIntrouvable,
    SERIES_V2,
)


def test_series_v2_ordre_pedagogique():
    """L'ordre AE, F, A, E est garanti par la constante SERIES_V2.
    v0.11.2 — 'R' retiré (cf. partie_exos_revision_approche pour la révision)."""
    assert SERIES_V2 == ("AE", "F", "A", "E")


def test_lecture_sequence_inexistante_leve_exception(conn):
    with pytest.raises(SequenceParNiveauIntrouvable) as ei:
        lire_sequence_par_niveau(conn, "N11", "S99")
    assert ei.value.code == "sequence_par_niveau_introuvable"
    assert ei.value.niveau == "N11"
    assert ei.value.sequence_code == "S99"


def test_lecture_structure_racine(base_peuplee):
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    # v0.10  : la racine inclut "etat_ui"
    # v0.10.2 : la racine inclut aussi "precedences"
    assert set(data.keys()) == {"sequence_par_niveau", "parties", "etat_ui", "precedences"}

    sn = data["sequence_par_niveau"]
    assert sn["id"] == "sn_n11_s03"
    assert sn["niveau"] == "N11"
    assert sn["sequence_code"] == "S03"
    assert sn["sequence_nom"] == "Fractions"
    assert sn["sequence_numero"] == 3
    assert sn["parametres"] == "\\xintdefvar A:=5;"
    assert sn["theme_code"] == "A"
    assert sn["theme_nom"] == "Nombres et Calculs"
    assert sn["theme_code_couleur"] == "nombres"

    # v0.10 : etat_ui présent et neutre par défaut
    assert data["etat_ui"]["objectif_ouvert_id"] is None
    # v0.10.2 : precedences vide par défaut (à câbler manuellement)
    assert data["precedences"] == []


def test_lecture_sans_theme_champs_null(base_peuplee):
    """Si la séquence du cycle n'a pas de thème, les champs theme_* sont None."""
    # On détache le thème de la séquence S03
    base_peuplee.execute(
        "UPDATE sequences_du_cycle SET theme_id = NULL WHERE id = 'sc_s03'")
    base_peuplee.commit()

    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    sn = data["sequence_par_niveau"]
    assert sn["theme_id"] is None
    assert sn["theme_code"] is None
    assert sn["theme_nom"] is None
    assert sn["theme_code_couleur"] is None


def test_lecture_sans_sequence_du_cycle(base_peuplee):
    """Cas limite : sequences_du_cycle absente pour ce sequence_code.
    La séquence par niveau reste lisible, avec nom et numero vides/None.
    """
    # On efface la séquence du cycle pour ne garder que la version par niveau
    base_peuplee.execute("DELETE FROM sequences_du_cycle WHERE code = 'S03'")
    base_peuplee.commit()

    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    sn = data["sequence_par_niveau"]
    assert sn["sequence_code"] == "S03"
    assert sn["sequence_nom"] == ""
    assert sn["sequence_numero"] is None
    # Le thème est également perdu puisqu'on passe par sequences_du_cycle.theme_id
    assert sn["theme_id"] is None


def test_parties_triees_par_numero(base_peuplee):
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    parties = data["parties"]
    assert [p["numero"] for p in parties] == [1, 2]
    assert [p["id"] for p in parties] == ["pt_p1", "pt_p2"]


def test_partie_sans_objectifs(base_peuplee):
    """Une partie sans objectif → liste vide, pas d'absence de clé."""
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    # partie 2 a un objectif (ob_03) mais sans aucun exo
    partie2 = data["parties"][1]
    assert partie2["numero"] == 2
    assert len(partie2["objectifs"]) == 1
    assert partie2["objectifs"][0]["code"] == "03"


def test_precedences_presentes(base_peuplee):
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    partie1 = data["parties"][0]
    assert partie1["precedences"] == [
        {"precedent_niveau": "N10", "precedent_seq": "S01"},
    ]


def test_precedences_vides(base_peuplee):
    """Partie sans précédence → liste vide."""
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    partie2 = data["parties"][1]
    assert partie2["precedences"] == []


def test_objectifs_tries_par_code(base_peuplee):
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    partie1 = data["parties"][0]
    assert [o["code"] for o in partie1["objectifs"]] == ["01", "02"]


def test_objectif_sans_methode_titre_none(base_peuplee):
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    obj01 = data["parties"][0]["objectifs"][0]
    assert obj01["code"] == "01"
    assert obj01["methode_id"] is None
    assert obj01["methode_titre"] is None


def test_objectif_avec_methode(base_peuplee):
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    obj02 = data["parties"][0]["objectifs"][1]
    assert obj02["code"] == "02"
    assert obj02["methode_id"] == "me_m1"
    assert obj02["methode_titre"] == "Simplifier une fraction"
    assert obj02["critere_F"] == "critère F obj02"
    assert obj02["critere_A"] == "critère A obj02"
    assert obj02["critere_E"] == "critère E obj02"


def test_exos_par_serie_toutes_series_presentes(base_peuplee):
    """Toutes les séries EA/F/A/E sont des clés présentes, même vides.
    v0.11.2 — 'R' retiré (cf. SERIES_V2)."""
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    obj01 = data["parties"][0]["objectifs"][0]
    assert set(obj01["exos_par_serie"].keys()) == {"AE", "F", "A", "E"}
    # obj 01 n'a pas d'EA
    assert obj01["exos_par_serie"]["AE"] == []


def test_exos_objectif_vide_toutes_series_vides(base_peuplee):
    """Objectif sans aucun exo → 4 tableaux vides, pas de None.
    v0.11.2 — 'R' retiré."""
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    obj03 = data["parties"][1]["objectifs"][0]
    assert obj03["code"] == "03"
    assert obj03["exos_par_serie"] == {"AE": [], "F": [], "A": [], "E": []}


def test_exos_tries_par_ordre(base_peuplee):
    """Pour obj02 série F : 3 exos à ordre 1, 2, 3 → retournés dans cet ordre.

    R4e4a : la contrainte UNIQUE(objectif_id, serie, ordre) empêche
    désormais d'insérer plusieurs exos d'une même série avec le même
    ordre. On vérifie donc simplement que le tri par `ordre` est correct,
    et que `origin_num` (ex-`num`) est bien remonté.
    """
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    obj02 = data["parties"][0]["objectifs"][1]
    f = obj02["exos_par_serie"]["F"]
    assert [e["origin_num"] for e in f] == [1, 2, 3]
    assert [e["ordre"] for e in f] == [1, 2, 3]


def test_exo_metadonnees_exercice_jointes(base_peuplee):
    """Les métadonnées de exercices (titre, fichier, niveau, sequence, num,
    serie_code) sont jointes dans chaque exo sous la clé `exercice`."""
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    obj01 = data["parties"][0]["objectifs"][0]
    f1 = obj01["exos_par_serie"]["F"][0]
    assert f1["exercice_id"] == "ex_f1"
    assert f1["exercice"]["titre"] == "Exo F1"
    assert f1["exercice"]["fichier"] == "N11S03F01.tex"
    assert f1["exercice"]["niveau"] == "N11"
    assert f1["exercice"]["sequence"] == "S03"
    assert f1["exercice"]["num"] == 1
    assert f1["exercice"]["serie_code"] == "F"


def test_pas_de_serie_R(base_peuplee):
    """v0.11.2 — Vérifie qu'aucun exo n'est retourné en série R.
    Avant v0.11.2, ob_02 avait un exo en série R avec origin_* renseignés.
    Cet exo a été retiré de la fixture car la série R n'existe plus.
    Si une donnée legacy avec serie='R' existait en BDD, le service
    `_charger_exos_par_serie` l'ignorerait silencieusement (cf. la garde
    `if serie not in resultat: continue`)."""
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    obj02 = data["parties"][0]["objectifs"][1]
    # 'R' n'est plus une clé du dict
    assert "R" not in obj02["exos_par_serie"]


def test_exo_origin_null_par_defaut(base_peuplee):
    """Exo sans origine (créé nativement) → origin_* à None."""
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    obj01 = data["parties"][0]["objectifs"][0]
    f1 = obj01["exos_par_serie"]["F"][0]
    assert f1["origin_niveau"] is None
    assert f1["origin_seq"] is None
    assert f1["origin_serie"] is None


def test_sequence_sans_parties(conn):
    """Une séquence par niveau sans aucune partie → parties = []."""
    conn.executescript("""
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
        VALUES ('sn_x', 'N12', 'S07', '');
    """)
    conn.commit()
    data = lire_sequence_par_niveau(conn, "N12", "S07")
    assert data["parties"] == []


# ═════════════════════════════════════════════════════════════════════════════
# 2. Tests de la route — via client Flask (fixtures du conftest global)
# ═════════════════════════════════════════════════════════════════════════════
#
# La fixture `client` (conftest global) crée une app Flask sur tmp_path avec
# SqliteStore et le schéma complet appliqué. Les tables v2 sont créées mais
# vides. On utilise le même pattern que test_R4b_routes.py pour peupler
# quelques lignes directement via sqlite3.connect(store.db_path).


@pytest.fixture
def client_peuple_v2(app):
    """Client Flask avec 1 séquence par niveau peuplée (N11/S03) : 2 parties,
    3 objectifs, quelques exos, 1 précédence, 1 thème, 1 méthode."""
    import sqlite3 as _sq3
    store = app.json_store
    db = _sq3.connect(str(store.db_path))
    try:
        # v0.10.2 : avec l'auto-import des cycles au démarrage, le cycle C04
        # et son thème A peuvent déjà exister. On utilise alors l'id existant
        # plutôt que d'en créer un nouveau (sinon le UPDATE plus bas pointe
        # vers un id orphelin qui casse le LEFT JOIN).
        db.row_factory = _sq3.Row
        db.execute("INSERT OR IGNORE INTO cycles (code, nom) VALUES (?, ?)",
                   ("C04", "Cycle 4"))
        # Récupérer l'id du thème A s'il existe déjà
        r = db.execute(
            "SELECT id FROM themes WHERE cycle_code = ? AND code = ?",
            ("C04", "A"),
        ).fetchone()
        if r is not None:
            theme_a_id = r["id"]
        else:
            theme_a_id = "th_A_rt"
            db.execute(
                "INSERT INTO themes (id, cycle_code, code, nom, "
                "code_couleur, description, ordre) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (theme_a_id, "C04", "A", "Nombres et Calculs",
                 "nombres", "", 1),
            )
        # Idem pour la séquence S03
        r = db.execute(
            "SELECT id FROM sequences_du_cycle "
            "WHERE cycle_code = ? AND code = ?",
            ("C04", "S03"),
        ).fetchone()
        if r is None:
            db.execute(
                "INSERT INTO sequences_du_cycle "
                "(id, cycle_code, code, numero, nom, theme_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("sc_s03_rt", "C04", "S03", 3, "Fractions", theme_a_id),
            )
        else:
            # Force le nom à "Fractions" pour les assertions du test
            # (l'auto-import peut avoir mis "Calcul numérique" depuis le CSV
            # de la fixture data_dir, qui est volontairement différent du
            # nom historique pour distinguer C04 conftest et C04 R1).
            db.execute(
                "UPDATE sequences_du_cycle "
                "SET nom = ?, theme_id = ? WHERE id = ?",
                ("Fractions", theme_a_id, r["id"]),
            )

        # Méthode + exercices (dont un exo N10 pour la série R).
        db.execute("INSERT INTO methodes (id, titre) VALUES (?, ?)",
                   ("me_m1_rt", "Simplifier une fraction"))
        db.executemany(
            "INSERT INTO exercices (id, serie, titre, niveau, sequence, num, "
            "serie_code, fichier) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("ex_f1_rt", "fondamental", "Exo F1", "N11", "S03", 1, "F",
                 "N11S03F01.tex"),
                ("ex_f2_rt", "fondamental", "Exo F2", "N11", "S03", 2, "F",
                 "N11S03F02.tex"),
                ("ex_a1_rt", "avancé",      "Exo A1", "N11", "S03", 1, "A",
                 "N11S03A01.tex"),
                ("ex_r1_rt", "fondamental", "Exo N10/S01/F1", "N10", "S01", 1,
                 "F", "N10S01F01.tex"),
            ],
        )

        # Structure v2.
        db.execute(
            "INSERT INTO sequences_par_niveau (id, niveau, sequence_code, "
            "parametres) VALUES (?, ?, ?, ?)",
            ("sn_rt", "N11", "S03", "\\xintdefvar A:=5;"),
        )
        db.executemany(
            "INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
            "VALUES (?, ?, ?)",
            [("pt_p1_rt", "sn_rt", 1), ("pt_p2_rt", "sn_rt", 2)],
        )
        db.execute(
            "INSERT INTO partie_precedences (partie_id, precedent_niveau, "
            "precedent_seq) VALUES (?, ?, ?)",
            ("pt_p1_rt", "N10", "S01"),
        )
        db.executemany(
            "INSERT INTO objectifs (id, partie_id, code, nom, methode_id, "
            "critere_F, critere_A, critere_E) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("ob_01_rt", "pt_p1_rt", "01", "Connaître le cours", None,
                 "Notes cahier", "Fiches résumé", "Oral prof"),
                ("ob_02_rt", "pt_p1_rt", "02", "Simplifier une fraction",
                 "me_m1_rt", "crit F", "crit A", "crit E"),
                ("ob_03_rt", "pt_p2_rt", "03", "Partie 2 obj 03", None,
                 "", "", ""),
            ],
        )
        db.executemany(
            "INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre, "
            "origin_niveau, origin_seq, origin_serie, origin_num) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("ob_01_rt", "F", "ex_f1_rt", 1, None, None, None, 1),
                ("ob_01_rt", "F", "ex_f2_rt", 2, None, None, None, 2),
                ("ob_01_rt", "A", "ex_a1_rt", 1, None, None, None, 1),
                ("ob_02_rt", "R", "ex_r1_rt", 1, "N10", "S01", "F", 1),
                ("ob_02_rt", "F", "ex_f1_rt", 1, None, None, None, 1),
            ],
        )
        db.commit()
    finally:
        db.close()
    return app.test_client()


def test_route_404_si_sequence_inexistante(client):
    """La route renvoie 404 avec un corps d'erreur structuré."""
    rep = client.get("/api/v2/sequences-par-niveau/N11/S99")
    assert rep.status_code == 404
    data = rep.get_json()
    assert data["code"] == "sequence_par_niveau_introuvable"
    assert data["niveau"] == "N11"
    assert data["sequence_code"] == "S99"


def test_route_404_si_niveau_inexistant(client):
    """Niveau non migré (N09) → 404 strict."""
    rep = client.get("/api/v2/sequences-par-niveau/N09/S01")
    assert rep.status_code == 404
    data = rep.get_json()
    assert data["code"] == "sequence_par_niveau_introuvable"


def test_route_200_structure_complete(client_peuple_v2):
    """N11/S03 peuplé → 200 + JSON hiérarchique complet conforme au contrat."""
    rep = client_peuple_v2.get("/api/v2/sequences-par-niveau/N11/S03")
    assert rep.status_code == 200
    data = rep.get_json()

    sn = data["sequence_par_niveau"]
    assert sn["niveau"] == "N11"
    assert sn["sequence_code"] == "S03"
    assert sn["sequence_nom"] == "Fractions"
    assert sn["theme_code"] == "A"
    assert sn["theme_code_couleur"] == "nombres"
    assert sn["parametres"] == "\\xintdefvar A:=5;"

    parties = data["parties"]
    assert [p["numero"] for p in parties] == [1, 2]
    assert parties[0]["precedences"] == [
        {"precedent_niveau": "N10", "precedent_seq": "S01"},
    ]
    assert parties[1]["precedences"] == []

    objs_p1 = parties[0]["objectifs"]
    assert [o["code"] for o in objs_p1] == ["01", "02"]
    assert objs_p1[0]["methode_titre"] is None
    assert objs_p1[1]["methode_titre"] == "Simplifier une fraction"

    # Les 4 séries sont toujours présentes (v0.11.2 — 'R' retiré).
    for o in objs_p1 + parties[1]["objectifs"]:
        assert set(o["exos_par_serie"].keys()) == {"AE", "F", "A", "E"}

    # v0.11.2 — La série R n'existe plus comme attribut d'exercice.
    # Pour les révisions, voir partie_exos_revision_approche.


def test_route_est_strictement_lecture_seule():
    """La règle Flask n'accepte que GET (+ HEAD/OPTIONS automatiques).
    Aucun POST/PUT/DELETE/PATCH : R4e1 est read-only par construction."""
    from flask import Flask
    from routes.v2_lecture import bp_v2_lecture

    app = Flask(__name__)
    app.register_blueprint(bp_v2_lecture)
    rules = [
        r for r in app.url_map.iter_rules()
        if r.endpoint.endswith("api_lire_sequence_par_niveau")
    ]
    assert len(rules) == 1
    autorisees = rules[0].methods
    assert "GET" in autorisees
    assert "POST"   not in autorisees
    assert "PUT"    not in autorisees
    assert "DELETE" not in autorisees
    assert "PATCH"  not in autorisees


# ═════════════════════════════════════════════════════════════════════════════
# v0.6.4 — Lecture de fin_cycle et notions associées
# ═════════════════════════════════════════════════════════════════════════════

def test_objectif_fin_cycle_par_defaut_N(base_peuplee):
    """Un objectif sans valeur fin_cycle explicite remonte 'N' (le DEFAULT
    du schéma). Pas de None ni de chaîne vide dans le retour utilisateur."""
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    for partie in data["parties"]:
        for obj in partie["objectifs"]:
            assert obj["fin_cycle"] == "N"


def test_objectif_fin_cycle_O_remonte(base_peuplee):
    """Si on marque fin_cycle='O' en BDD, la lecture le retourne tel quel."""
    base_peuplee.execute(
        "UPDATE objectifs SET fin_cycle = 'O' WHERE code = '02'"
    )
    base_peuplee.commit()
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    obj02 = data["parties"][0]["objectifs"][1]
    assert obj02["code"] == "02"
    assert obj02["fin_cycle"] == "O"


def test_objectif_notions_vide_par_defaut(base_peuplee):
    """Un objectif sans notion associée a une liste vide, pas None."""
    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    for partie in data["parties"]:
        for obj in partie["objectifs"]:
            assert obj["notions"] == []


def test_objectif_notions_remontees_dans_lordre(base_peuplee):
    """Les notions associées sont retournées triées par `ordre`, avec leur
    titre joint depuis la table notions."""
    base_peuplee.executemany(
        "INSERT INTO notions (id, titre) VALUES (?, ?)",
        [
            ("no_x1", "Première notion"),
            ("no_x2", "Deuxième notion"),
        ],
    )
    # Insertion intentionnellement dans le désordre des codes pour vérifier
    # que c'est bien `ordre` qui tranche, pas l'ordre d'insertion ou l'id.
    base_peuplee.executemany(
        "INSERT INTO objectif_notions (objectif_id, notion_id, ordre) "
        "VALUES (?, ?, ?)",
        [
            ("ob_02", "no_x2", 0),  # ordre 0 → en premier
            ("ob_02", "no_x1", 1),  # ordre 1 → en second
        ],
    )
    base_peuplee.commit()

    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    obj02 = data["parties"][0]["objectifs"][1]
    assert len(obj02["notions"]) == 2
    assert obj02["notions"][0]["id"] == "no_x2"
    assert obj02["notions"][0]["titre"] == "Deuxième notion"
    assert obj02["notions"][1]["id"] == "no_x1"
    assert obj02["notions"][1]["titre"] == "Première notion"


def test_etat_code_atomes_expose_v0_17_5(base_peuplee):
    """v0.17.5 — Le coloriage de l'état des atomes dans le panneau central
    d'assemblage (en cours → transparent ; validé → vert pâle) s'appuie sur
    l'etat_code exposé par la lecture v2. On vérifie qu'il remonte bien pour
    les notions et la méthode liée (défaut 'en_cours', et 'valide' propagé)."""
    # Notion validée + notion en cours
    base_peuplee.executemany(
        "INSERT INTO notions (id, titre, etat_code) VALUES (?, ?, ?)",
        [("no_v", "Notion validée", "valide"),
         ("no_c", "Notion en cours", "en_cours")],
    )
    base_peuplee.executemany(
        "INSERT INTO objectif_notions (objectif_id, notion_id, ordre) VALUES (?, ?, ?)",
        [("ob_02", "no_v", 0), ("ob_02", "no_c", 1)],
    )
    # Méthode validée liée à l'objectif
    base_peuplee.execute(
        "INSERT INTO methodes (id, titre, etat_code) VALUES ('me_v', 'M', 'valide')")
    base_peuplee.execute(
        "UPDATE objectifs SET methode_id = 'me_v' WHERE id = 'ob_02'")
    base_peuplee.commit()

    data = lire_sequence_par_niveau(base_peuplee, "N11", "S03")
    obj02 = data["parties"][0]["objectifs"][1]
    etats = {n["id"]: n["etat_code"] for n in obj02["notions"]}
    assert etats["no_v"] == "valide"
    assert etats["no_c"] == "en_cours"
    assert obj02["methode_etat_code"] == "valide"
