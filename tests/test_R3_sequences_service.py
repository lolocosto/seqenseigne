"""tests/test_R3_sequences_service.py — Tests du service CRUD séquences."""

import pytest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.sequences_du_cycle import (
    creer_sequence,
    modifier_sequence,
    supprimer_sequence,
    lire_sequence,
    lister_sequences,
    SequenceIntrouvable,
    SequenceDoublonCode,
    SequenceDoublonNumero,
    SequenceThemeInvalide,
    SequenceEnUsage,
    CycleIntrouvable,
    SequenceErreur,
)
from persistence.sqlite_store import SqliteStore


@pytest.fixture
def store(tmp_path):
    """Base avec C04 et un thème 'A' créé."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    s = SqliteStore(data_dir)
    conn = sqlite3.connect(str(s.db_path))
    conn.execute("INSERT INTO cycles (code, nom) VALUES ('C04', 'Cycle 4')")
    conn.execute(
        "INSERT INTO themes (id, cycle_code, code, nom) "
        "VALUES ('th_A', 'C04', 'A', 'Nombres')"
    )
    conn.execute(
        "INSERT INTO themes (id, cycle_code, code, nom) "
        "VALUES ('th_B', 'C04', 'B', 'Données')"
    )
    conn.commit()
    conn.close()
    return s


# ── Création ─────────────────────────────────────────────────────────────────

class TestCreation:
    def test_creer_sequence_simple(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "Représentations")
        assert s["code"] == "S01"
        assert s["numero"] == 1
        assert s["cycle_code"] == "C04"
        assert s["theme_id"] is None
        assert s["id"].startswith("sc_")

    def test_creer_avec_theme(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "Test", theme_id="th_A")
        assert s["theme_id"] == "th_A"

    def test_refus_doublon_code(self, store):
        with store._conn() as conn:
            creer_sequence(conn, "C04", "S01", 1, "X")
            with pytest.raises(SequenceDoublonCode):
                creer_sequence(conn, "C04", "S01", 2, "Y")

    def test_refus_doublon_numero(self, store):
        with store._conn() as conn:
            creer_sequence(conn, "C04", "S01", 1, "X")
            with pytest.raises(SequenceDoublonNumero):
                creer_sequence(conn, "C04", "S02", 1, "Y")

    def test_refus_code_vide(self, store):
        with store._conn() as conn:
            with pytest.raises(SequenceErreur) as exc:
                creer_sequence(conn, "C04", "", 1, "Test")
        assert exc.value.code == "code_vide"

    def test_refus_numero_vide(self, store):
        with store._conn() as conn:
            with pytest.raises(SequenceErreur) as exc:
                creer_sequence(conn, "C04", "S01", None, "Test")
        assert exc.value.code == "numero_vide"

    def test_refus_numero_negatif(self, store):
        with store._conn() as conn:
            with pytest.raises(SequenceErreur) as exc:
                creer_sequence(conn, "C04", "S01", -1, "Test")
        assert exc.value.code == "numero_invalide"

    def test_refus_numero_zero(self, store):
        with store._conn() as conn:
            with pytest.raises(SequenceErreur) as exc:
                creer_sequence(conn, "C04", "S01", 0, "Test")
        assert exc.value.code == "numero_invalide"

    def test_refus_nom_vide(self, store):
        with store._conn() as conn:
            with pytest.raises(SequenceErreur) as exc:
                creer_sequence(conn, "C04", "S01", 1, "")
        assert exc.value.code == "nom_vide"

    def test_refus_theme_inexistant(self, store):
        with store._conn() as conn:
            with pytest.raises(SequenceThemeInvalide):
                creer_sequence(conn, "C04", "S01", 1, "X", theme_id="th_ZZZ")

    def test_refus_theme_autre_cycle(self, store):
        """Un thème du cycle C03 ne peut pas être attaché à une séquence C04."""
        with store._conn() as conn:
            conn.execute("INSERT INTO cycles (code, nom) VALUES ('C03', 'Cycle 3')")
            conn.execute(
                "INSERT INTO themes (id, cycle_code, code, nom) "
                "VALUES ('th_c03_X', 'C03', 'X', 'Autre')"
            )
            conn.commit()
            with pytest.raises(SequenceThemeInvalide):
                creer_sequence(conn, "C04", "S99", 99, "X",
                               theme_id="th_c03_X")

    def test_refus_cycle_inexistant(self, store):
        with store._conn() as conn:
            with pytest.raises(CycleIntrouvable):
                creer_sequence(conn, "CZZ", "S01", 1, "X")

    def test_meme_code_deux_cycles_ok(self, store):
        with store._conn() as conn:
            conn.execute("INSERT INTO cycles (code, nom) VALUES ('C03', 'Cycle 3')")
            conn.commit()
            s1 = creer_sequence(conn, "C04", "S01", 1, "Seq C04")
            s2 = creer_sequence(conn, "C03", "S01", 1, "Seq C03")
        assert s1["id"] != s2["id"]


# ── Lecture ──────────────────────────────────────────────────────────────────

class TestLecture:
    def test_lire_sequence(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "Test", theme_id="th_A")
            lu = lire_sequence(conn, s["id"])
        assert lu["code"] == "S01"
        assert lu["theme_code"] == "A"
        assert lu["theme_nom"] == "Nombres"
        assert lu["nb_atomes_total"] == 0

    def test_lire_sans_theme(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X")
            lu = lire_sequence(conn, s["id"])
        assert lu["theme_id"] is None
        assert lu["theme_code"] is None

    def test_lire_inexistante(self, store):
        with store._conn() as conn:
            with pytest.raises(SequenceIntrouvable):
                lire_sequence(conn, "sc_zzz")

    def test_lister_triees_par_numero(self, store):
        with store._conn() as conn:
            creer_sequence(conn, "C04", "S03", 3, "Trois")
            creer_sequence(conn, "C04", "S01", 1, "Un")
            creer_sequence(conn, "C04", "S02", 2, "Deux")
            seqs = lister_sequences(conn, "C04")
        assert [s["numero"] for s in seqs] == [1, 2, 3]

    def test_lister_vide(self, store):
        with store._conn() as conn:
            seqs = lister_sequences(conn, "C04")
        assert seqs == []

    def test_compteurs_atomes(self, store):
        """Si des atomes référencent la séquence, les compteurs le reflètent."""
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X")
            # v0.14.6.b.1 — Insertion dans objectifs (la table v1 n'est
            # plus lue par _compter_objectifs). On crée la pile complète :
            # sequence_par_niveau → sequence_parties → objectifs.
            conn.execute(
                "INSERT INTO sequences_par_niveau "
                "(id, niveau, sequence_code) VALUES ('sn_n11s01', 'N11', 'S01')"
            )
            conn.execute(
                "INSERT INTO sequence_parties "
                "(id, sequence_par_niveau_id, numero) "
                "VALUES ('pt_n11s01_1', 'sn_n11s01', 1)"
            )
            conn.execute(
                "INSERT INTO objectifs "
                "(id, partie_id, code, nom) "
                "VALUES ('ov2_1', 'pt_n11s01_1', '02', 'Obj test')"
            )
            conn.execute(
                "INSERT INTO notions "
                "(id, titre, niveau, sequence, num_connaissance, fichier) "
                "VALUES ('no_1', 'N1', 'N11', 'S01', '01', 'N11_S01_N01.tex')"
            )
            conn.commit()
            lu = lire_sequence(conn, s["id"])
        assert lu["atomes"]["objectifs"] == 1
        assert lu["atomes"]["notions"] == 1
        assert lu["atomes"]["methodes"] == 0
        assert lu["atomes"]["exercices"] == 0
        assert lu["nb_atomes_total"] == 2


# ── Modification ─────────────────────────────────────────────────────────────

class TestModification:
    def test_modifier_nom(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "Ancien")
            m = modifier_sequence(conn, s["id"], nom="Nouveau")
        assert m["nom"] == "Nouveau"

    def test_modifier_code(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X")
            m = modifier_sequence(conn, s["id"], code="S99")
        assert m["code"] == "S99"

    def test_modifier_numero(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X")
            m = modifier_sequence(conn, s["id"], numero=42)
        assert m["numero"] == 42

    def test_attacher_theme(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X")
            m = modifier_sequence(conn, s["id"], theme_id="th_A")
        assert m["theme_id"] == "th_A"

    def test_changer_theme(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X", theme_id="th_A")
            m = modifier_sequence(conn, s["id"], theme_id="th_B")
        assert m["theme_id"] == "th_B"

    def test_detacher_theme(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X", theme_id="th_A")
            m = modifier_sequence(conn, s["id"], detacher_theme=True)
        assert m["theme_id"] is None

    def test_refus_doublon_code_modif(self, store):
        with store._conn() as conn:
            creer_sequence(conn, "C04", "S01", 1, "X")
            s2 = creer_sequence(conn, "C04", "S02", 2, "Y")
            with pytest.raises(SequenceDoublonCode):
                modifier_sequence(conn, s2["id"], code="S01")

    def test_refus_doublon_numero_modif(self, store):
        with store._conn() as conn:
            creer_sequence(conn, "C04", "S01", 1, "X")
            s2 = creer_sequence(conn, "C04", "S02", 2, "Y")
            with pytest.raises(SequenceDoublonNumero):
                modifier_sequence(conn, s2["id"], numero=1)

    def test_modifier_inexistante(self, store):
        with store._conn() as conn:
            with pytest.raises(SequenceIntrouvable):
                modifier_sequence(conn, "sc_zzz", nom="X")

    def test_refus_theme_invalide_modif(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X")
            with pytest.raises(SequenceThemeInvalide):
                modifier_sequence(conn, s["id"], theme_id="th_zzz")


# ── Suppression ──────────────────────────────────────────────────────────────

class TestSuppression:
    def test_supprimer_sans_atomes(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X")
            r = supprimer_sequence(conn, s["id"])
            assert r["supprime"] is True
            with pytest.raises(SequenceIntrouvable):
                lire_sequence(conn, s["id"])

    def test_refus_si_objectif_rattache(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X")
            # v0.14.6.b.1 — Insertion via la pile v2.
            conn.execute(
                "INSERT INTO sequences_par_niveau "
                "(id, niveau, sequence_code) VALUES ('sn_n11s01', 'N11', 'S01')"
            )
            conn.execute(
                "INSERT INTO sequence_parties "
                "(id, sequence_par_niveau_id, numero) "
                "VALUES ('pt_n11s01_1', 'sn_n11s01', 1)"
            )
            conn.execute(
                "INSERT INTO objectifs "
                "(id, partie_id, code, nom) "
                "VALUES ('ov2_1', 'pt_n11s01_1', '02', 'Obj')"
            )
            conn.commit()
            with pytest.raises(SequenceEnUsage) as exc:
                supprimer_sequence(conn, s["id"])
        assert exc.value.details["objectifs"] == 1

    def test_refus_si_methode_rattachee(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X")
            conn.execute(
                "INSERT INTO methodes "
                "(id, titre, niveau, sequence, num_methode, num_objectif, fichier) "
                "VALUES ('me_1', 'M1', 'N11', 'S01', 1, '02', 'f.tex')"
            )
            conn.commit()
            with pytest.raises(SequenceEnUsage) as exc:
                supprimer_sequence(conn, s["id"])
        assert exc.value.details["methodes"] == 1

    def test_refus_si_notion_rattachee(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X")
            conn.execute(
                "INSERT INTO notions "
                "(id, titre, niveau, sequence, num_connaissance, fichier) "
                "VALUES ('no_1', 'N1', 'N11', 'S01', '01', 'f.tex')"
            )
            conn.commit()
            with pytest.raises(SequenceEnUsage):
                supprimer_sequence(conn, s["id"])

    def test_refus_si_exercice_rattache(self, store):
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X")
            conn.execute(
                "INSERT INTO exercices "
                "(id, serie, serie_code, niveau, sequence, num, fichier) "
                "VALUES ('ex_1', 'fondamental', 'F', 'N11', 'S01', 1, 'f.tex')"
            )
            conn.commit()
            with pytest.raises(SequenceEnUsage):
                supprimer_sequence(conn, s["id"])

    def test_details_dans_exception(self, store):
        """Le dict `details` de l'exception contient les 4 compteurs."""
        with store._conn() as conn:
            s = creer_sequence(conn, "C04", "S01", 1, "X")
            # v0.14.6.b.1 — Insertion via la pile v2. Note : on rattache
            # 2 objectifs (N11/S01 et N12/S01) à la même séquence
            # `sequences_du_cycle` via le sequence_code='S01' partagé.
            for niv, code_obj, sn_id, pt_id, ov2_id in [
                ("N11", "02", "sn_n11s01", "pt_n11s01_1", "ov2_n11"),
                ("N12", "03", "sn_n12s01", "pt_n12s01_1", "ov2_n12"),
            ]:
                conn.execute(
                    "INSERT INTO sequences_par_niveau "
                    "(id, niveau, sequence_code) VALUES (?, ?, 'S01')",
                    (sn_id, niv)
                )
                conn.execute(
                    "INSERT INTO sequence_parties "
                    "(id, sequence_par_niveau_id, numero) "
                    "VALUES (?, ?, 1)",
                    (pt_id, sn_id)
                )
                conn.execute(
                    "INSERT INTO objectifs "
                    "(id, partie_id, code, nom) "
                    "VALUES (?, ?, ?, 'O')",
                    (ov2_id, pt_id, code_obj)
                )
            conn.execute(
                "INSERT INTO notions "
                "(id, titre, niveau, sequence, num_connaissance, fichier) "
                "VALUES ('no_1', 'N1', 'N11', 'S01', '01', 'f.tex')"
            )
            conn.commit()
            try:
                supprimer_sequence(conn, s["id"])
            except SequenceEnUsage as e:
                assert e.details == {
                    "objectifs": 2, "methodes": 0, "notions": 1, "exercices": 0
                }

    def test_supprimer_inexistante(self, store):
        with store._conn() as conn:
            with pytest.raises(SequenceIntrouvable):
                supprimer_sequence(conn, "sc_zzz")
