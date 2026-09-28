"""Tests v0.14.6.b.1 — Réécriture des services pour lire/écrire v2
au lieu de v1.

Cette livraison réécrit 4 services pour qu'ils n'utilisent plus la
table `objectifs` (v1) ni `exercice_objectifs` (v1) :

  - services/latex_rendu_atome.py    (macros seqObjectifGetNom / FinCycle)
  - services/sequences_du_cycle.py   (compteurs d'atomes)
  - persistence/sqlite_store.py      (ecrire_objectifs, ecrire_methodes,
                                       lire_methodes, lire_exercices,
                                       ecrire_exercices, _objectif_id_pour)
  - services/edition_progression.py  (vidé en stub : code mort)

Côté UI :
  - Route GET /api/objectifs supprimée
  - Variable JS ATL_OBJ_CAT supprimée
  - Fonction JS atelChargerObjectifs supprimée
  - Appel à atelChargerObjectifs() retiré de initAteliers()

Ces tests vérifient explicitement le **nouveau comportement v2** sur
les chemins critiques. Ils complètent les tests existants qui ont été
adaptés (Q3=c, mixte : suppression / adaptation au cas par cas).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────

def _creer_pile_v2(conn: sqlite3.Connection, niveau: str, seq_code: str,
                   num_partie: int, obj_code: str, obj_nom: str = "Obj test",
                   methode_id: str | None = None) -> str:
    """Crée la pile sequence_par_niveau → sequence_parties → objectifs.

    Retourne l'id du nouvel objectif v2.
    """
    sn_id = f"sn_{niveau}{seq_code}"
    pt_id = f"pt_{niveau}{seq_code}_{num_partie}"
    ov2_id = f"ov2_{niveau}{seq_code}_{obj_code}"

    # INSERT OR IGNORE pour idempotence (plusieurs objectifs même sn/partie).
    conn.execute(
        "INSERT OR IGNORE INTO sequences_par_niveau "
        "(id, niveau, sequence_code) VALUES (?, ?, ?)",
        (sn_id, niveau, seq_code)
    )
    conn.execute(
        "INSERT OR IGNORE INTO sequence_parties "
        "(id, sequence_par_niveau_id, numero) VALUES (?, ?, ?)",
        (pt_id, sn_id, num_partie)
    )
    conn.execute(
        "INSERT INTO objectifs "
        "(id, partie_id, code, nom, methode_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (ov2_id, pt_id, obj_code, obj_nom, methode_id)
    )
    return ov2_id


@pytest.fixture
def store_migre(tmp_path):
    """Store SQLite avec schéma post-R4e4 appliqué."""
    from persistence.sqlite_store import SqliteStore
    from scripts.peuplement_01_migrer_schema import migrer

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    store = SqliteStore(data_dir)
    migrer(data_dir / "seqenseigne.db")
    return store


# ── 1. latex_rendu_atome : seqObjectifGetNom / GetFinCycle ────────────

class TestMacrosObjectifLisentV2:
    """v0.14.6.b.1 — Les macros LaTeX `seqObjectifGetNom` et
    `seqObjectifGetFinCycle` lisent désormais `objectifs` au lieu
    de `objectifs` v1.
    """

    def _resoudre_macro(self, conn, niveau, sequence, texte):
        """Helper qui invoque resoudre_macros_csv depuis latex_rendu_atome."""
        from services.latex_rendu_atome import resoudre_macros_csv
        return resoudre_macros_csv(conn, texte, niveau, sequence)

    def test_seq_objectif_get_nom_lit_v2(self, store_migre):
        """Insertion en v2 uniquement → la macro doit trouver le nom."""
        with store_migre._conn() as conn:
            _creer_pile_v2(conn, "N10", "S01", 1, "02", "Utiliser les fractions")
            conn.commit()
            res = self._resoudre_macro(
                conn, "N10", "S01", r"\seqObjectifGetNom{02}"
            )
        assert res == "Utiliser les fractions"

    # v0.14.6.b.2 — test_seq_objectif_get_nom_ignore_v1 supprimé : la
    # table `objectifs` (v1) n'existe plus, le test devient sans objet.

    def test_seq_objectif_get_fin_cycle_toujours_N(self, store_migre):
        """v0.14.6.b.1 — Concept est_nouveau abandonné en v2. La macro
        retourne toujours 'N' indépendamment de l'objectif.
        """
        with store_migre._conn() as conn:
            _creer_pile_v2(conn, "N10", "S01", 1, "02", "Obj")
            conn.commit()
            res = self._resoudre_macro(
                conn, "N10", "S01", r"\seqObjectifGetFinCycle{02}"
            )
        assert res == "N"


# ── 2. sequences_du_cycle : compteurs lisent v2 ───────────────────────

class TestCompteurObjectifsLitV2:
    """v0.14.6.b.1 — La fonction _compter_objectifs dans
    services/sequences_du_cycle.py utilise objectifs + JOIN partie.
    """

    def test_count_via_v2(self, store_migre):
        """3 objectifs en v2 sur S01 (2 sur N10, 1 sur N11) → COUNT=3.
        Une séquence du cycle est partagée entre niveaux.
        """
        with store_migre._conn() as conn:
            _creer_pile_v2(conn, "N10", "S01", 1, "02", "A")
            _creer_pile_v2(conn, "N10", "S01", 1, "03", "B")
            _creer_pile_v2(conn, "N11", "S01", 1, "02", "C")
            conn.commit()
            from services.sequences_du_cycle import _compter_atomes_rattaches
            res = _compter_atomes_rattaches(conn, "S01")
        assert res["objectifs"] == 3, (
            "3 objectifs créés en v2 sous sequence_code=S01 → COUNT=3"
        )

    # v0.14.6.b.2 — test_count_v1_ignore supprimé : la table `objectifs`
    # (v1) n'existe plus.


# ── 3. _objectif_id_pour : lit v2 ─────────────────────────────────────

class TestObjectifIdPourLitV2:
    """v0.14.6.b.1 — _objectif_id_pour (helper du store) lit v2."""

    def test_retourne_id_v2_si_methode_liee(self, store_migre):
        with store_migre._conn() as conn:
            conn.execute("INSERT INTO methodes (id, titre) "
                         "VALUES ('me_001', 'M')")
            ov2_id = _creer_pile_v2(conn, "N10", "S01", 1, "02",
                                    methode_id="me_001")
            conn.commit()
            result = store_migre._objectif_id_pour(
                conn, classe_id="", seq_code="S01", obj_code="02"
            )
        assert result == ov2_id

    def test_retourne_id_v2_sans_methode_en_fallback(self, store_migre):
        """Si aucun objectif n'a methode_id pour ce code, fallback sur
        n'importe lequel matchant le code.
        """
        with store_migre._conn() as conn:
            ov2_id = _creer_pile_v2(conn, "N10", "S01", 1, "02")  # pas de methode
            conn.commit()
            result = store_migre._objectif_id_pour(
                conn, classe_id="", seq_code="S01", obj_code="02"
            )
        assert result == ov2_id

    def test_retourne_none_si_absent(self, store_migre):
        with store_migre._conn() as conn:
            result = store_migre._objectif_id_pour(
                conn, classe_id="", seq_code="S01", obj_code="99"
            )
        assert result is None


# ── 4. ecrire_objectifs : écrit dans v2 ───────────────────────────────

class TestEcrireObjectifsEcritV2:
    """v0.14.6.b.1 — ecrire_objectifs écrit dans objectifs et crée
    sequence_parties à la volée.
    """

    def _setup_referentiel(self, store):
        store.creer_referentiel({
            "id": "ref_test", "niveau": "N10", "version": "2024",
            "description": "", "etat": "verrouille",
            "themes": [{"code": "A", "nom": "T", "couleur": ""}],
            "sequences": [{
                "code": "S01", "numero": 1, "nom": "Seq", "theme_code": "A",
                "objectifs": [
                    {"code": "01", "nom": "Obj 01", "fin_cycle": False,
                     "critere_f": "F1", "critere_a": "A1", "critere_e": "E1"},
                    {"code": "11", "nom": "Obj 11", "fin_cycle": False,
                     "critere_f": "", "critere_a": "", "critere_e": ""},
                ],
            }],
        })

    # v0.14.6.b.2 — test_n_ecrit_rien_dans_v1 supprimé : la table
    # `objectifs` (v1) n'existe plus.

    def test_ecrit_dans_v2(self, store_migre):
        self._setup_referentiel(store_migre)
        store_migre.ecrire_objectifs()
        with store_migre._conn() as conn:
            n = conn.execute("SELECT COUNT(*) FROM objectifs").fetchone()[0]
        assert n == 2

    def test_partie_creee_automatiquement(self, store_migre):
        """Le code '11' → partie 2 doit être créée automatiquement."""
        self._setup_referentiel(store_migre)
        store_migre.ecrire_objectifs()
        with store_migre._conn() as conn:
            parties = conn.execute(
                "SELECT numero FROM sequence_parties "
                "ORDER BY numero"
            ).fetchall()
        nums = [r[0] for r in parties]
        assert 1 in nums  # créée pour code '01'
        assert 2 in nums  # créée pour code '11'

    def test_sequence_par_niveau_creee_automatiquement(self, store_migre):
        """La sequence_par_niveau est créée à la volée si absente
        (chaîne d'import autonome).
        """
        self._setup_referentiel(store_migre)
        # AVANT : pas de sequence_par_niveau
        with store_migre._conn() as conn:
            n_avant = conn.execute(
                "SELECT COUNT(*) FROM sequences_par_niveau"
            ).fetchone()[0]
        assert n_avant == 0

        store_migre.ecrire_objectifs()

        # APRÈS : la sequence_par_niveau a été créée
        with store_migre._conn() as conn:
            n_apres = conn.execute(
                "SELECT COUNT(*) FROM sequences_par_niveau "
                "WHERE niveau='N10' AND sequence_code='S01'"
            ).fetchone()[0]
        assert n_apres == 1

    def test_idempotent(self, store_migre):
        """2 appels successifs → 2e fait UPDATE et non INSERT."""
        self._setup_referentiel(store_migre)
        store_migre.ecrire_objectifs()
        rapport2 = store_migre.ecrire_objectifs()
        with store_migre._conn() as conn:
            n = conn.execute("SELECT COUNT(*) FROM objectifs").fetchone()[0]
        assert n == 2  # toujours 2, pas de doublon
        assert rapport2["objectifs_crees"] == 0
        assert rapport2["objectifs_maj"] == 2


# ── 5. ecrire_methodes : pose methode_id en v2 ────────────────────────

class TestEcrireMethodesLieV2:
    """v0.14.6.b.1 — ecrire_methodes pose methode_id sur l'objectif v2
    correspondant, plus sur v1.
    """

    def test_methode_liee_a_objectif_v2(self, store_migre):
        # 1. Créer un objectif v2 préexistant
        with store_migre._conn() as conn:
            ov2_id = _creer_pile_v2(conn, "N10", "S01", 1, "02", "Obj 02")
            conn.commit()
        # 2. Écrire une méthode rattachée à cet objectif
        store_migre.ecrire_methodes([{
            "id": "m_01", "titre": "M", "corps": "",
            "niveau": "N10", "sequence": "S01",
            "num_methode": "1", "num_objectif": "02",
            "fichier": "test.tex",
            "criteres": {"2": "F2", "3": "A2", "4": "E2"},
        }])
        # 3. L'objectif v2 doit avoir methode_id='m_01' et ses critères
        with store_migre._conn() as conn:
            r = conn.execute(
                "SELECT methode_id, critere_F, critere_A, critere_E "
                "FROM objectifs WHERE id=?", (ov2_id,)
            ).fetchone()
        assert r["methode_id"] == "m_01"
        assert r["critere_F"] == "F2"
        assert r["critere_A"] == "A2"
        assert r["critere_E"] == "E2"

    def test_pas_de_creation_orpheline(self, store_migre):
        """v0.14.6.b.1 — Le cas legacy v1 (création d'objectif orphelin
        sans métadonnées) a été supprimé.
        v0.14.6.b.2 — La requête sur la table `objectifs` (v1) a été
        retirée, la table n'existant plus.
        """
        # Méthode sans niveau/sequence/num_objectif → cas legacy
        store_migre.ecrire_methodes([{
            "id": "m_orphan", "titre": "M", "corps": "",
            "fichier": "x.tex",
            "criteres": {"2": "F", "3": "A", "4": "E"},
        }])
        with store_migre._conn() as conn:
            n_v2 = conn.execute(
                "SELECT COUNT(*) FROM objectifs"
            ).fetchone()[0]
        # Plus aucun objectif créé (cas legacy supprimé)
        assert n_v2 == 0


# ── 6. lire_methodes : critères depuis v2 ─────────────────────────────

class TestLireMethodesLitV2:
    """v0.14.6.b.1 — lire_methodes lit les critères depuis v2."""

    def test_criteres_lus_de_v2(self, store_migre):
        with store_migre._conn() as conn:
            conn.execute(
                "INSERT INTO methodes (id, titre, corps, niveau, sequence, "
                "                       num_methode, num_objectif, fichier) "
                "VALUES ('m_01', 'M', '', 'N10', 'S01', 1, '02', 'x.tex')"
            )
            _creer_pile_v2(conn, "N10", "S01", 1, "02", "Obj",
                           methode_id="m_01")
            # Mettre les critères en v2 directement
            conn.execute(
                "UPDATE objectifs SET critere_F=?, critere_A=?, critere_E=? "
                "WHERE methode_id='m_01'",
                ("F_v2", "A_v2", "E_v2")
            )
            conn.commit()
        methodes = store_migre.lire_methodes()
        m = next((x for x in methodes if x["id"] == "m_01"), None)
        assert m is not None
        # Critères lus depuis v2
        assert m["criteres"]["F"] == "F_v2"
        assert m["criteres"]["A"] == "A_v2"
        assert m["criteres"]["E"] == "E_v2"


# ── 7. lire_exercices : objectifs liés depuis objectif_exos (v2) ──────

class TestLireExercicesViaV2:
    """v0.14.6.b.1 — lire_exercices lit les objectifs liés via
    objectif_exos (v2) au lieu de exercice_objectifs (v1).
    """

    def test_objectifs_lus_via_v2(self, store_migre):
        with store_migre._conn() as conn:
            ov2_id = _creer_pile_v2(conn, "N10", "S01", 1, "02", "Obj")
            conn.execute(
                "INSERT INTO exercices "
                "(id, serie, serie_code, niveau, sequence, num, fichier) "
                "VALUES ('ex_001', 'F', 'F', 'N10', 'S01', 1, 'x.tex')"
            )
            # Liaison v2 uniquement
            conn.execute(
                "INSERT INTO objectif_exos "
                "(objectif_id, serie, exercice_id, ordre) "
                "VALUES (?, 'F', 'ex_001', 1)",
                (ov2_id,)
            )
            conn.commit()
        exos = store_migre.lire_exercices()
        ex = next((x for x in exos if x["id"] == "ex_001"), None)
        assert ex is not None
        assert ov2_id in ex["objectifs"]
        assert "02" in ex["objectifs_codes"]

    # v0.14.6.b.2 — test_objectifs_v1_non_lus supprimé : les tables
    # `objectifs` et `exercice_objectifs` (v1) n'existent plus.


# v0.14.6.b.2 — Classe TestEcrireExercicesQ5b retirée : la table
# `exercice_objectifs` (v1) n'existe plus, le test devient sans objet.


# ── 9. Route /api/objectifs supprimée ─────────────────────────────────

class TestRouteApiObjectifsSupprimee:
    """v0.14.6.b.1 — La route GET /api/objectifs est retirée. Toute
    requête vers cet endpoint doit retourner 404.
    """

    @pytest.fixture
    def client(self, tmp_path):
        """Client Flask de test."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        # Données minimales pour que create_app n'échoue pas
        for f in ["notions.json", "methodes.json", "exercices.json",
                  "livrets_importes.json"]:
            (data_dir / f).write_text(
                '{"' + f.replace('.json', '').replace('importes', 's') + '": []}',
                encoding="utf-8"
            )
        from app import create_app
        app = create_app(data_dir=data_dir)
        app.config["TESTING"] = True
        return app.test_client()

    def test_get_api_objectifs_renvoie_404(self, client):
        r = client.get("/api/objectifs")
        assert r.status_code == 404


# ── 10. edition_progression.py supprimé ───────────────────────────────

class TestEditionProgressionSupprime:
    """v0.14.6.b.2 — services/edition_progression.py a été supprimé
    complètement (était un stub en b.1). L'import doit échouer.
    """

    def test_module_non_importable(self):
        """Le module doit avoir disparu."""
        with pytest.raises(ImportError):
            import services.edition_progression  # noqa: F401


# ── 11. JS : ATL_OBJ_CAT et atelChargerObjectifs supprimés ───────────

class TestNettoyageJS:
    """v0.14.6.b.1 — Le JS static/app.js ne doit plus contenir ATL_OBJ_CAT
    ni atelChargerObjectifs en tant que code actif.
    """

    @pytest.fixture
    def app_js(self):
        return Path(__file__).resolve().parent.parent / "static" / "app.js"

    def test_pas_de_declaration_atl_obj_cat(self, app_js):
        """Plus de `let ATL_OBJ_CAT = []` ni de `ATL_OBJ_CAT =`
        comme assignation effective.
        """
        contenu = app_js.read_text(encoding="utf-8")
        # Seuls les commentaires explicatifs peuvent mentionner le nom
        for ligne in contenu.split("\n"):
            stripped = ligne.lstrip()
            # Ignorer les lignes en commentaire
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            assert "ATL_OBJ_CAT" not in ligne, (
                f"v0.14.6.b.1 — ATL_OBJ_CAT doit avoir disparu du code "
                f"actif (seuls les commentaires explicatifs peuvent le "
                f"mentionner). Ligne fautive : {ligne!r}"
            )

    def test_pas_dappel_a_atel_charger_objectifs(self, app_js):
        """Plus aucun appel `atelChargerObjectifs(`."""
        contenu = app_js.read_text(encoding="utf-8")
        for ligne in contenu.split("\n"):
            stripped = ligne.lstrip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            assert "atelChargerObjectifs(" not in ligne, (
                f"v0.14.6.b.1 — atelChargerObjectifs() doit avoir "
                f"disparu du code actif. Ligne : {ligne!r}"
            )

    def test_pas_de_definition_atel_charger_objectifs(self, app_js):
        """La fonction `async function atelChargerObjectifs` ne doit
        plus exister.
        """
        contenu = app_js.read_text(encoding="utf-8")
        assert "async function atelChargerObjectifs" not in contenu
        assert "function atelChargerObjectifs(" not in contenu
