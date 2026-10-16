r"""tests/test_v0_51_18_numerotation_livret.py — Ordre et numéros des
exercices du livret de séquence, concordance avec le plan de travail.

Régression corrigée en v0.51.18 :
  - le livret triait les exercices d'une série par IDENTIFIANT ; depuis
    que les ids sont aléatoires (`ex_xxxxxxxx`), les séries étaient
    mélangées (objectifs 04, 02, 02, 13, 03…) ;
  - le plan de travail affichait le rang de l'exercice DANS SON OBJECTIF
    (repart à 1 à chaque objectif), incohérent avec le livret.

Les fixtures donnent volontairement aux exercices des identifiants dont
l'ordre alphabétique est l'INVERSE de l'ordre pédagogique : un tri par
identifiant échoue à coup sûr.
"""

from __future__ import annotations

import re

import pytest

from app import create_app
from services.livret_plans_de_travail import (
    _lire_objectifs_de_partie,
    _lire_parties_de_sequence,
)
from services.livret_sequence import generer_livret_sequence
from services.numerotation_livret import numeroter_exos_livret


# ── Tests unitaires de la numérotation (sans BDD) ───────────────────────────

def _partie(revisions=None, decouverte=None, objectifs=None):
    return {
        "exos_revision_approche": {
            "R": [{"exercice_id": i} for i in (revisions or [])],
            "EA": [{"exercice_id": i} for i in (decouverte or [])],
        },
        "objectifs": [
            {"exos_par_serie": {s: [{"exercice_id": i} for i in ids]
                                for s, ids in o.items()}}
            for o in (objectifs or [])
        ],
    }


class TestNumeroterExosLivret:

    def test_ordre_partie_objectif_rang_pas_identifiant(self):
        """D1 — L'ordre suit la structure (partie → objectif → rang),
        jamais l'identifiant."""
        parties = [
            _partie(objectifs=[{"F": ["ex_z", "ex_y"]}, {"F": ["ex_x"]}]),
            _partie(objectifs=[{"F": ["ex_a"]}]),
        ]
        n = numeroter_exos_livret(parties)
        assert n.ordre["F"] == ["ex_z", "ex_y", "ex_x", "ex_a"]
        assert [n.numero["F"][i] for i in n.ordre["F"]] == [1, 2, 3, 4]

    def test_serie_0_continue_sur_les_parties(self):
        """D3 — R et EA de toutes les parties, puis AE des objectifs,
        forment une seule série 0 numérotée en continu (le paquet ne
        remet ExoNum à zéro qu'au changement de série)."""
        parties = [
            _partie(revisions=["r1", "r2"], decouverte=["d1"],
                    objectifs=[{"EA": ["ae1"]}]),
            _partie(revisions=["r3"]),
        ]
        n = numeroter_exos_livret(parties)
        assert n.ordre["R"] == ["r1", "r2", "d1", "r3"]
        assert n.numero["R"] == {"r1": 1, "r2": 2, "d1": 3, "r3": 4}
        assert n.numero["AE"] == {"ae1": 5}

    def test_exercice_sur_deux_objectifs_une_seule_fois(self):
        """D4 — Émis au premier objectif ; même numéro pour les deux."""
        parties = [_partie(objectifs=[{"F": ["ex_1", "ex_c"]},
                                      {"F": ["ex_c", "ex_2"]}])]
        n = numeroter_exos_livret(parties)
        assert n.ordre["F"] == ["ex_1", "ex_c", "ex_2"]
        assert n.numeros("F", ["ex_c", "ex_2"]) == [2, 3]

    def test_exercice_de_revision_pas_repris_en_serie(self):
        """D5 — Un exercice de révision n'est pas réémis en série F."""
        parties = [_partie(revisions=["ex_r"], objectifs=[{"F": ["ex_r", "ex_f"]}])]
        n = numeroter_exos_livret(parties)
        assert n.ordre["F"] == ["ex_f"]
        assert n.numeros("F", ["ex_r", "ex_f"]) == [1]

    def test_sans_serie_A_les_autres_series_inchangees(self):
        parties = [_partie(objectifs=[{"F": ["f1"], "A": ["a1"], "E": ["e1"]}])]
        n = numeroter_exos_livret(parties, serie_A=False)
        assert n.ordre["A"] == []
        assert n.numero["F"] == {"f1": 1} and n.numero["E"] == {"e1": 1}


# ── Fixture BDD : 2 parties, 4 objectifs, ids « à l'envers » ────────────────

_EXOS = [
    # (id, partie, objectif, série, rang)  — ids décroissants dans l'ordre
    ("ex_z9", "pt_1", "ob_02", "F", 1),
    ("ex_z8", "pt_1", "ob_02", "F", 2),
    ("ex_z7", "pt_1", "ob_03", "F", 1),
    ("ex_z6", "pt_1", "ob_03", "A", 1),
    ("ex_z5", "pt_1", "ob_04", "F", 1),
    ("ex_z4", "pt_2", "ob_12", "F", 1),
    ("ex_z3", "pt_2", "ob_12", "E", 1),
    ("ex_z2", "pt_2", "ob_13", "F", 1),
]
_REVISIONS = [("ex_r2", "pt_1", "R", 1), ("ex_r1", "pt_2", "R", 1)]


@pytest.fixture
def app_deux_parties(data_dir):
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS paquet_definitions (
                nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
                corps TEXT, corps_fin TEXT, texte_complet TEXT,
                fichier_source TEXT, ligne_debut INTEGER,
                macros_appelees TEXT, environnements_utilises TEXT,
                statut_rendu_atome TEXT DEFAULT 'reutilise',
                contenu_atome TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS paquet_requirepackage (
                fichier_source TEXT NOT NULL, ordre INTEGER NOT NULL,
                nom TEXT NOT NULL, options TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (fichier_source, ordre)
            );
            INSERT OR IGNORE INTO cycles (code, nom) VALUES ('C04', 'Cycle 4');
            INSERT OR IGNORE INTO themes (id, cycle_code, code, nom, code_couleur)
                VALUES ('th_A', 'C04', 'A', 'Nombres', 'nombres');
            INSERT OR IGNORE INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
                VALUES ('sc_s01', 'C04', 'S01', 1, 'Représentations', 'th_A');
            INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
                VALUES ('sn_1', 'N11', 'S01', '');
            INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                VALUES ('pt_1', 'sn_1', 1), ('pt_2', 'sn_1', 2);
            INSERT INTO objectifs (id, partie_id, code, nom, methode_id) VALUES
                ('ob_02', 'pt_1', '02', 'Obj 02', NULL),
                ('ob_03', 'pt_1', '03', 'Obj 03', NULL),
                ('ob_04', 'pt_1', '04', 'Obj 04', NULL),
                ('ob_12', 'pt_2', '12', 'Obj 12', NULL),
                ('ob_13', 'pt_2', '13', 'Obj 13', NULL);
        """)
        serie_nom = {"F": "fondamental", "A": "avancé", "E": "exploration"}
        for i, (ex_id, _pt, ob, serie, rang) in enumerate(_EXOS, start=1):
            conn.execute(
                "INSERT INTO exercices (id, serie, titre, niveau, sequence, num, "
                "serie_code, fichier, enonce, corrige) VALUES "
                "(?, ?, ?, 'N11', 'S01', ?, ?, ?, ?, 'Corrigé')",
                (ex_id, serie_nom[serie], ex_id, i, serie, f"{ex_id}.tex",
                 f"ENONCE-{ex_id}"))
            conn.execute(
                "INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) "
                "VALUES (?, ?, ?, ?)", (ob, serie, ex_id, rang))
        for i, (ex_id, pt, typ, rang) in enumerate(_REVISIONS, start=1):
            conn.execute(
                "INSERT INTO exercices (id, serie, titre, niveau, sequence, num, "
                "serie_code, fichier, enonce, corrige) VALUES "
                "(?, 'fondamental', ?, 'N10', 'S01', ?, 'F', ?, ?, 'Corrigé')",
                (ex_id, ex_id, 50 + i, f"{ex_id}.tex", f"ENONCE-{ex_id}"))
            conn.execute(
                "INSERT INTO partie_exos_revision_approche "
                "(partie_id, type, exercice_id, ordre, origin_niveau, origin_seq, "
                " origin_serie, origin_num) VALUES (?, ?, ?, ?, 'N10', 'S01', 'F', ?)",
                (pt, typ, ex_id, rang, rang))
        conn.commit()
    yield app


def _ordre_dans_le_livret(tex: str, num_serie: int) -> list[str]:
    """Ids des exercices dans l'ordre où le livret les émet, pour une
    série du paquet (0 Révisions, 1 F, 2 A, 3 E)."""
    m = re.search(r"\\begin\{seqSerieExos\}\{" + str(num_serie) + r"\}(.*?)"
                  r"\\end\{seqSerieExos\}", tex, re.S)
    return re.findall(r"ENONCE-(ex_\w+)", m.group(1)) if m else []


class TestOrdreLivret:

    def test_serie_F_dans_l_ordre_des_objectifs(self, app_deux_parties):
        """D1 — Objectifs 02, 02, 03, 04 (partie 1) puis 12, 13 (partie
        2), alors que l'ordre alphabétique des ids est l'inverse."""
        with app_deux_parties.json_store._conn() as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert _ordre_dans_le_livret(tex, 1) == [
            "ex_z9", "ex_z8", "ex_z7", "ex_z5", "ex_z4", "ex_z2"]

    def test_revisions_par_partie(self, app_deux_parties):
        with app_deux_parties.json_store._conn() as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
        assert _ordre_dans_le_livret(tex, 0) == ["ex_r2", "ex_r1"]


class TestPlanDeTravail:

    def test_numeros_continus_sur_la_sequence(self, app_deux_parties):
        """D3 — Le plan affiche les numéros du livret : la série F
        continue d'une partie à l'autre (objectif 12 → 5, pas 1)."""
        with app_deux_parties.json_store._conn() as conn:
            p1 = {o["code"]: o for o in _lire_objectifs_de_partie(conn, "pt_1")}
            p2 = {o["code"]: o for o in _lire_objectifs_de_partie(conn, "pt_2")}
            parties = _lire_parties_de_sequence(conn, "sn_1")
        assert p1["02"]["exos_F"] == [1, 2]
        assert p1["03"]["exos_F"] == [3]
        assert p1["04"]["exos_F"] == [4]
        assert p2["12"]["exos_F"] == [5]
        assert p2["13"]["exos_F"] == [6]
        assert p1["03"]["exos_A"] == [1]
        assert p2["12"]["exos_E"] == [1]
        assert [p["exos_R"] for p in parties] == [[1], [2]]


class TestConcordanceLivretPlan:

    def test_chaque_numero_du_plan_designe_le_bon_exercice(self, app_deux_parties):
        """D2 — Pour chaque objectif et chaque série, le n-ième exercice
        de la série dans le livret est bien un exercice de cet objectif.
        Protège contre toute dérive future entre les deux documents."""
        with app_deux_parties.json_store._conn() as conn:
            tex = generer_livret_sequence(conn, "N11", "S01")
            objectifs = (_lire_objectifs_de_partie(conn, "pt_1")
                         + _lire_objectifs_de_partie(conn, "pt_2"))
        attendus = {}
        for ex_id, _pt, ob, serie, _r in _EXOS:
            attendus.setdefault((ob, serie), set()).add(ex_id)
        for serie, num_paquet in (("F", 1), ("A", 2), ("E", 3)):
            ordre = _ordre_dans_le_livret(tex, num_paquet)
            for o in objectifs:
                ob = "ob_" + o["code"]
                designes = {ordre[n - 1] for n in o[f"exos_{serie}"]}
                assert designes == attendus.get((ob, serie), set()), (ob, serie)
