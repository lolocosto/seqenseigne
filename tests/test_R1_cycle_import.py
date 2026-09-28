"""tests/test_R1_cycle_import.py — Tests du service d'import cycle."""

import sqlite3
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.cycle_import import (
    importer_cycle,
    lister_cycles,
    lister_themes,
    lister_sequences_du_cycle,
    ImportCycleErreur,
)
from persistence.sqlite_store import SqliteStore


# ── Fixtures ─────────────────────────────────────────────────────────────────

CSV_THEMES_MINIMAL = """Code,Nom,CodeCouleur,Description
"A","Nombres et Calculs","nombres","Au cycle 4, les élèves..."
"B","Données et fonctions","donnees","Les élèves travaillent..."
"C","Grandeurs et mesures","grandeurs","Ce thème se prête..."
"D","Espace et géométrie","geometrie","Les élèves valident..."
"E","Algorithmique et programmation","algorithmique","Au cycle 4, les élèves s'initient..."
"""

CSV_SEQUENCES_MINIMAL = """Code,Numero,Nom,Theme
S01,01,"Représentations d'un nombre","A"
S02,02,"Comparaison de nombres","A"
S03,03,"Calcul numérique","A"
S07,07,"Proportionnalité","B"
S10,10,"Triangles","D"
"""


@pytest.fixture
def store(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return SqliteStore(data_dir)


@pytest.fixture
def csv_themes(tmp_path):
    p = tmp_path / "C04_themes.csv"
    p.write_text(CSV_THEMES_MINIMAL, encoding="utf-8")
    return p


@pytest.fixture
def csv_sequences(tmp_path):
    p = tmp_path / "C04_sequences.csv"
    p.write_text(CSV_SEQUENCES_MINIMAL, encoding="utf-8")
    return p


# ── Tests — import simple ────────────────────────────────────────────────────

class TestImportSimple:
    def test_import_cree_cycle(self, store, csv_themes, csv_sequences):
        with store._conn() as conn:
            rapport = importer_cycle(
                conn, "C04", "Cycle 4", csv_themes, csv_sequences
            )
        assert rapport["cycle"]["cree"] is True
        assert rapport["cycle"]["maj"] is False

    def test_import_cree_5_themes(self, store, csv_themes, csv_sequences):
        with store._conn() as conn:
            rapport = importer_cycle(
                conn, "C04", "Cycle 4", csv_themes, csv_sequences
            )
        assert rapport["themes"]["crees"] == 5
        assert rapport["themes"]["mis_a_jour"] == 0

    def test_import_cree_5_sequences(self, store, csv_themes, csv_sequences):
        with store._conn() as conn:
            rapport = importer_cycle(
                conn, "C04", "Cycle 4", csv_themes, csv_sequences
            )
        assert rapport["sequences"]["crees"] == 5
        assert rapport["sequences"]["mis_a_jour"] == 0

    def test_themes_lisibles_apres_import(self, store, csv_themes, csv_sequences):
        with store._conn() as conn:
            importer_cycle(conn, "C04", "Cycle 4", csv_themes, csv_sequences)
            themes = lister_themes(conn, "C04")
        assert len(themes) == 5
        codes = {t["code"] for t in themes}
        assert codes == {"A", "B", "C", "D", "E"}

    def test_sequences_rattachees_aux_themes(self, store, csv_themes, csv_sequences):
        with store._conn() as conn:
            importer_cycle(conn, "C04", "Cycle 4", csv_themes, csv_sequences)
            seqs = lister_sequences_du_cycle(conn, "C04")
        par_code = {s["code"]: s for s in seqs}
        assert par_code["S01"]["theme_code"] == "A"
        assert par_code["S07"]["theme_code"] == "B"
        assert par_code["S10"]["theme_code"] == "D"

    def test_sequences_triees_par_numero(self, store, csv_themes, csv_sequences):
        with store._conn() as conn:
            importer_cycle(conn, "C04", "Cycle 4", csv_themes, csv_sequences)
            seqs = lister_sequences_du_cycle(conn, "C04")
        numeros = [s["numero"] for s in seqs]
        assert numeros == sorted(numeros)

    def test_description_theme_preservee(self, store, csv_themes, csv_sequences):
        with store._conn() as conn:
            importer_cycle(conn, "C04", "Cycle 4", csv_themes, csv_sequences)
            themes = lister_themes(conn, "C04")
        theme_a = next(t for t in themes if t["code"] == "A")
        assert theme_a["description"] == "Au cycle 4, les élèves..."


# ── Tests — idempotence ──────────────────────────────────────────────────────

class TestIdempotence:
    def test_import_deux_fois_aucun_doublon(self, store, csv_themes, csv_sequences):
        with store._conn() as conn:
            importer_cycle(conn, "C04", "Cycle 4", csv_themes, csv_sequences)
            rapport2 = importer_cycle(conn, "C04", "Cycle 4", csv_themes, csv_sequences)
        assert rapport2["cycle"]["maj"] is True
        assert rapport2["themes"]["crees"] == 0
        assert rapport2["themes"]["mis_a_jour"] == 5
        assert rapport2["sequences"]["crees"] == 0
        assert rapport2["sequences"]["mis_a_jour"] == 5

    def test_modification_csv_maj_en_base(self, store, tmp_path):
        """Après import, si on change le CSV et qu'on réimporte,
        les valeurs sont mises à jour."""
        themes_v1 = tmp_path / "themes_v1.csv"
        themes_v1.write_text(
            'Code,Nom,CodeCouleur,Description\n'
            '"A","Ancien nom","nombres","Ancienne desc"\n',
            encoding="utf-8"
        )
        seqs_vide = tmp_path / "seqs_vide.csv"
        seqs_vide.write_text("Code,Numero,Nom,Theme\n", encoding="utf-8")

        with store._conn() as conn:
            importer_cycle(conn, "C04", "Cycle 4", themes_v1, seqs_vide)

        themes_v2 = tmp_path / "themes_v2.csv"
        themes_v2.write_text(
            'Code,Nom,CodeCouleur,Description\n'
            '"A","Nouveau nom","nombres","Nouvelle desc"\n',
            encoding="utf-8"
        )
        with store._conn() as conn:
            importer_cycle(conn, "C04", "Cycle 4", themes_v2, seqs_vide)
            themes = lister_themes(conn, "C04")

        theme_a = next(t for t in themes if t["code"] == "A")
        assert theme_a["nom"] == "Nouveau nom"
        assert theme_a["description"] == "Nouvelle desc"


# ── Tests — erreurs ──────────────────────────────────────────────────────────

class TestErreurs:
    def test_fichier_themes_absent(self, store, csv_sequences, tmp_path):
        inexistant = tmp_path / "nexiste_pas.csv"
        with store._conn() as conn:
            with pytest.raises(ImportCycleErreur) as exc:
                importer_cycle(conn, "C04", "Cycle 4", inexistant, csv_sequences)
        assert exc.value.code == "themes_absent"

    def test_fichier_sequences_absent(self, store, csv_themes, tmp_path):
        inexistant = tmp_path / "nexiste_pas.csv"
        with store._conn() as conn:
            with pytest.raises(ImportCycleErreur) as exc:
                importer_cycle(conn, "C04", "Cycle 4", csv_themes, inexistant)
        assert exc.value.code == "sequences_absent"

    def test_colonnes_manquantes_themes(self, store, csv_sequences, tmp_path):
        bad = tmp_path / "bad_themes.csv"
        bad.write_text('Code,Nom\n"A","Test"\n', encoding="utf-8")
        with store._conn() as conn:
            with pytest.raises(ImportCycleErreur) as exc:
                importer_cycle(conn, "C04", "Cycle 4", bad, csv_sequences)
        assert exc.value.code == "themes_colonnes"


# ── Tests — cas edge ─────────────────────────────────────────────────────────

class TestCasEdge:
    def test_sequence_theme_inconnu_avertissement(self, store, csv_themes, tmp_path):
        """Une séquence qui référence un thème absent → avertissement
        mais import continue, theme_id à NULL."""
        seqs = tmp_path / "seqs.csv"
        seqs.write_text(
            'Code,Numero,Nom,Theme\n'
            'S01,01,"Test","Z"\n',  # thème Z n'existe pas
            encoding="utf-8"
        )
        with store._conn() as conn:
            rapport = importer_cycle(conn, "C04", "Cycle 4", csv_themes, seqs)
            seqs_lues = lister_sequences_du_cycle(conn, "C04")

        assert len(rapport["avertissements"]) == 1
        assert "Z" in rapport["avertissements"][0]
        assert seqs_lues[0]["theme_id"] is None

    def test_sequence_sans_theme(self, store, csv_themes, tmp_path):
        """Une séquence avec champ Theme vide → theme_id NULL sans warning."""
        seqs = tmp_path / "seqs.csv"
        seqs.write_text(
            'Code,Numero,Nom,Theme\n'
            'S01,01,"Test",""\n',
            encoding="utf-8"
        )
        with store._conn() as conn:
            rapport = importer_cycle(conn, "C04", "Cycle 4", csv_themes, seqs)
            seqs_lues = lister_sequences_du_cycle(conn, "C04")

        assert len(rapport["avertissements"]) == 0
        assert seqs_lues[0]["theme_id"] is None

    def test_ligne_theme_vide_ignoree(self, store, csv_sequences, tmp_path):
        bad = tmp_path / "themes.csv"
        bad.write_text(
            'Code,Nom,CodeCouleur,Description\n'
            '"","","",""\n'            # ligne vide : ignorée
            '"A","Nombres","nombres",""\n',
            encoding="utf-8"
        )
        with store._conn() as conn:
            rapport = importer_cycle(conn, "C04", "Cycle 4", bad, csv_sequences)
        assert rapport["themes"]["crees"] == 1
        assert len(rapport["avertissements"]) >= 1

    def test_sequence_numero_non_numerique(self, store, csv_themes, tmp_path):
        seqs = tmp_path / "seqs.csv"
        seqs.write_text(
            'Code,Numero,Nom,Theme\n'
            'S01,abc,"Test","A"\n'
            'S02,02,"OK","A"\n',
            encoding="utf-8"
        )
        with store._conn() as conn:
            rapport = importer_cycle(conn, "C04", "Cycle 4", csv_themes, seqs)
        assert rapport["sequences"]["crees"] == 1  # seule S02 est créée
        assert any("abc" in w for w in rapport["avertissements"])

    def test_deux_cycles_coexistent(self, store, tmp_path):
        """On peut importer deux cycles côte à côte (C03, C04)."""
        th_c03 = tmp_path / "c03_themes.csv"
        th_c03.write_text(
            'Code,Nom,CodeCouleur,Description\n'
            '"X","Thème C3","x",""\n',
            encoding="utf-8"
        )
        sq_c03 = tmp_path / "c03_seqs.csv"
        sq_c03.write_text('Code,Numero,Nom,Theme\nS01,01,"C3",""\n', encoding="utf-8")

        th_c04 = tmp_path / "c04_themes.csv"
        th_c04.write_text(
            'Code,Nom,CodeCouleur,Description\n'
            '"A","Thème C4","a",""\n',
            encoding="utf-8"
        )
        sq_c04 = tmp_path / "c04_seqs.csv"
        sq_c04.write_text('Code,Numero,Nom,Theme\nS01,01,"C4","A"\n', encoding="utf-8")

        with store._conn() as conn:
            importer_cycle(conn, "C03", "Cycle 3", th_c03, sq_c03)
            importer_cycle(conn, "C04", "Cycle 4", th_c04, sq_c04)
            cycles = lister_cycles(conn)

        assert len(cycles) == 2
        codes = {c["code"] for c in cycles}
        assert codes == {"C03", "C04"}

    def test_meme_code_theme_dans_deux_cycles(self, store, tmp_path):
        """Le code 'A' peut être utilisé dans C03 ET C04 (unicité par cycle)."""
        th = tmp_path / "themes.csv"
        th.write_text(
            'Code,Nom,CodeCouleur,Description\n'
            '"A","Test","a",""\n',
            encoding="utf-8"
        )
        sq = tmp_path / "seqs.csv"
        sq.write_text('Code,Numero,Nom,Theme\n', encoding="utf-8")

        with store._conn() as conn:
            importer_cycle(conn, "C03", "Cycle 3", th, sq)
            importer_cycle(conn, "C04", "Cycle 4", th, sq)
            themes_c03 = lister_themes(conn, "C03")
            themes_c04 = lister_themes(conn, "C04")

        assert len(themes_c03) == 1
        assert len(themes_c04) == 1
        assert themes_c03[0]["code"] == themes_c04[0]["code"] == "A"
        # Mais ids différents
        assert themes_c03[0]["id"] != themes_c04[0]["id"]


# ── Tests — import depuis les vrais CSV ──────────────────────────────────────

class TestCSVReels:
    """Test sur les vrais CSV C04_themes.csv et C04_sequences.csv
    si présents dans le dossier data/ du projet."""

    @pytest.fixture
    def csv_reels(self):
        root = Path(__file__).parent.parent
        p_themes = root / "data" / "C04_themes.csv"
        p_seqs = root / "data" / "C04_sequences.csv"
        if not p_themes.exists() or not p_seqs.exists():
            pytest.skip("CSV réels absents du dépôt de test")
        return p_themes, p_seqs

    def test_import_csv_reels(self, store, csv_reels):
        p_themes, p_seqs = csv_reels
        with store._conn() as conn:
            rapport = importer_cycle(
                conn, "C04", "Cycle 4", p_themes, p_seqs
            )
        assert rapport["cycle"]["cree"] is True
        assert rapport["themes"]["crees"] == 5
        assert rapport["sequences"]["crees"] == 14
        assert rapport["avertissements"] == []
