"""tests/test_R2_themes_service.py — Tests du service CRUD des thèmes."""

import pytest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.themes import (
    creer_theme,
    modifier_theme,
    supprimer_theme,
    lire_theme,
    lister_themes_avec_compteurs,
    ThemeIntrouvable,
    ThemeDoublonCode,
    ThemeDoublonNom,
    ThemeCouleurInvalide,
    ThemeEnUsage,
    CycleIntrouvable,
    ThemeErreur,
)
from persistence.sqlite_store import SqliteStore


# ── Fixture : base avec cycle C04 ────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    s = SqliteStore(data_dir)
    conn = sqlite3.connect(str(s.db_path))
    conn.execute("INSERT INTO cycles (code, nom) VALUES ('C04', 'Cycle 4')")
    conn.commit()
    conn.close()
    return s


# ── Création ─────────────────────────────────────────────────────────────────

class TestCreation:
    def test_creer_theme_simple(self, store):
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Nombres et Calculs")
        assert t["code"] == "A"
        assert t["nom"] == "Nombres et Calculs"
        assert t["cycle_code"] == "C04"
        assert t["id"].startswith("th_")
        assert t["ordre"] == 1

    def test_creer_theme_avec_couleur_et_description(self, store):
        with store._conn() as conn:
            t = creer_theme(
                conn, "C04", "A", "Nombres",
                code_couleur="nombres",
                description="Description \\og LaTeX \\fg"
            )
        assert t["code_couleur"] == "nombres"
        assert t["description"] == "Description \\og LaTeX \\fg"

    def test_ordre_auto_incremente(self, store):
        with store._conn() as conn:
            t1 = creer_theme(conn, "C04", "A", "Nombres")
            t2 = creer_theme(conn, "C04", "B", "Données")
            t3 = creer_theme(conn, "C04", "C", "Grandeurs")
        assert t1["ordre"] == 1
        assert t2["ordre"] == 2
        assert t3["ordre"] == 3

    def test_ordre_explicite_respecte(self, store):
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Nombres", ordre=42)
        assert t["ordre"] == 42

    def test_creer_theme_refuse_doublon_code(self, store):
        with store._conn() as conn:
            creer_theme(conn, "C04", "A", "Nombres")
            with pytest.raises(ThemeDoublonCode):
                creer_theme(conn, "C04", "A", "Autre")

    def test_creer_theme_refuse_doublon_nom(self, store):
        with store._conn() as conn:
            creer_theme(conn, "C04", "A", "Nombres")
            with pytest.raises(ThemeDoublonNom):
                creer_theme(conn, "C04", "B", "Nombres")

    def test_creer_theme_refuse_code_vide(self, store):
        with store._conn() as conn:
            with pytest.raises(ThemeErreur) as exc:
                creer_theme(conn, "C04", "", "Test")
        assert exc.value.code == "code_vide"

    def test_creer_theme_refuse_nom_vide(self, store):
        with store._conn() as conn:
            with pytest.raises(ThemeErreur) as exc:
                creer_theme(conn, "C04", "A", "")
        assert exc.value.code == "nom_vide"

    def test_creer_theme_refuse_couleur_invalide(self, store):
        with store._conn() as conn:
            with pytest.raises(ThemeCouleurInvalide):
                creer_theme(conn, "C04", "A", "Nombres",
                            code_couleur="n_existe_pas")

    def test_couleur_vide_acceptee(self, store):
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Nombres", code_couleur="")
        assert t["code_couleur"] == ""

    def test_creer_theme_refuse_cycle_inconnu(self, store):
        with store._conn() as conn:
            with pytest.raises(CycleIntrouvable):
                creer_theme(conn, "CZZ", "A", "Test")

    def test_meme_code_deux_cycles_ok(self, store):
        with store._conn() as conn:
            conn.execute("INSERT INTO cycles (code, nom) VALUES ('C03', 'Cycle 3')")
            conn.commit()
            t1 = creer_theme(conn, "C04", "A", "Nombres C04")
            t2 = creer_theme(conn, "C03", "A", "Nombres C03")
        assert t1["code"] == t2["code"] == "A"
        assert t1["id"] != t2["id"]


# ── Lecture ──────────────────────────────────────────────────────────────────

class TestLecture:
    def test_lire_theme_existant(self, store):
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Nombres")
            lu = lire_theme(conn, t["id"])
        assert lu["code"] == "A"
        assert lu["nb_sequences"] == 0

    def test_lire_theme_inexistant(self, store):
        with store._conn() as conn:
            with pytest.raises(ThemeIntrouvable):
                lire_theme(conn, "th_inexistant")

    def test_compteur_sequences(self, store):
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Nombres")
            # Ajouter 2 séquences
            conn.execute(
                "INSERT INTO sequences_du_cycle "
                "(id, cycle_code, code, numero, nom, theme_id) "
                "VALUES ('sc_1', 'C04', 'S01', 1, 'S1', ?)",
                (t["id"],)
            )
            conn.execute(
                "INSERT INTO sequences_du_cycle "
                "(id, cycle_code, code, numero, nom, theme_id) "
                "VALUES ('sc_2', 'C04', 'S02', 2, 'S2', ?)",
                (t["id"],)
            )
            conn.commit()
            lu = lire_theme(conn, t["id"])
        assert lu["nb_sequences"] == 2

    def test_lister_themes(self, store):
        with store._conn() as conn:
            creer_theme(conn, "C04", "A", "Nombres")
            creer_theme(conn, "C04", "B", "Données")
            themes = lister_themes_avec_compteurs(conn, "C04")
        assert len(themes) == 2
        assert themes[0]["code"] == "A"  # ordre 1
        assert themes[1]["code"] == "B"  # ordre 2

    def test_lister_themes_cycle_vide(self, store):
        with store._conn() as conn:
            themes = lister_themes_avec_compteurs(conn, "C04")
        assert themes == []


# ── Modification ─────────────────────────────────────────────────────────────

class TestModification:
    def test_modifier_nom(self, store):
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Ancien nom")
            t2 = modifier_theme(conn, t["id"], nom="Nouveau nom")
        assert t2["nom"] == "Nouveau nom"
        assert t2["code"] == "A"  # inchangé

    def test_modifier_code(self, store):
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Nombres")
            t2 = modifier_theme(conn, t["id"], code="AA")
        assert t2["code"] == "AA"

    def test_modifier_couleur(self, store):
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Nombres")
            t2 = modifier_theme(conn, t["id"], code_couleur="donnees")
        assert t2["code_couleur"] == "donnees"

    def test_modifier_description(self, store):
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Nombres")
            t2 = modifier_theme(conn, t["id"], description="Nouvelle desc")
        assert t2["description"] == "Nouvelle desc"

    def test_modifier_refuse_doublon_code(self, store):
        with store._conn() as conn:
            creer_theme(conn, "C04", "A", "Nombres")
            t2 = creer_theme(conn, "C04", "B", "Données")
            with pytest.raises(ThemeDoublonCode):
                modifier_theme(conn, t2["id"], code="A")

    def test_modifier_garder_code_ok(self, store):
        """Modifier un thème sans changer son code ne doit pas lever
        'doublon_code' alors que le code existe bien... pour lui-même."""
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Nombres")
            t2 = modifier_theme(conn, t["id"], nom="Autre nom")
        assert t2["code"] == "A"

    def test_modifier_theme_inexistant(self, store):
        with store._conn() as conn:
            with pytest.raises(ThemeIntrouvable):
                modifier_theme(conn, "th_inexistant", nom="Test")

    def test_modifier_couleur_invalide(self, store):
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Nombres")
            with pytest.raises(ThemeCouleurInvalide):
                modifier_theme(conn, t["id"], code_couleur="invalide")


# ── Suppression ──────────────────────────────────────────────────────────────

class TestSuppression:
    def test_supprimer_sans_sequences(self, store):
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Nombres")
            rapport = supprimer_theme(conn, t["id"])
            assert rapport["supprime"] is True
            with pytest.raises(ThemeIntrouvable):
                lire_theme(conn, t["id"])

    def test_supprimer_refuse_si_sequences(self, store):
        with store._conn() as conn:
            t = creer_theme(conn, "C04", "A", "Nombres")
            conn.execute(
                "INSERT INTO sequences_du_cycle "
                "(id, cycle_code, code, numero, nom, theme_id) "
                "VALUES ('sc_1', 'C04', 'S01', 1, 'S1', ?)",
                (t["id"],)
            )
            conn.commit()
            with pytest.raises(ThemeEnUsage) as exc:
                supprimer_theme(conn, t["id"])
        assert "1 séquence" in str(exc.value)

    def test_supprimer_inexistant(self, store):
        with store._conn() as conn:
            with pytest.raises(ThemeIntrouvable):
                supprimer_theme(conn, "th_inexistant")
