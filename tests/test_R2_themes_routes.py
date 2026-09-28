"""tests/test_R2_themes_routes.py — Tests des routes Flask pour R2."""

import pytest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def client(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for f in ["classes.json", "suivi.json", "niveaux.json", "versions.json"]:
        (data_dir / f).write_text(
            '{"classes": []}' if f == "classes.json" else '{}',
            encoding="utf-8"
        )
    for f in ["notions.json", "methodes.json", "exercices.json",
              "livrets_importes.json"]:
        (data_dir / f).write_text(
            '{"' + f.replace('.json', '').replace('importes', 's') + '": []}',
            encoding="utf-8"
        )

    from app import create_app
    from routes.themes import bp_themes
    app = create_app(data_dir=data_dir)
    if "themes" not in app.blueprints:
        app.register_blueprint(bp_themes)
    app.config["TESTING"] = True

    # Créer le cycle C04
    store = app.json_store
    conn = sqlite3.connect(str(store.db_path))
    conn.execute("INSERT INTO cycles (code, nom) VALUES ('C04', 'Cycle 4')")
    conn.commit()
    conn.close()

    return app.test_client()


# ── Couleurs disponibles ─────────────────────────────────────────────────────

class TestCouleurs:
    def test_lister_familles_couleurs(self, client):
        r = client.get("/api/couleurs_themes")
        assert r.status_code == 200
        data = r.get_json()
        assert "familles" in data
        assert len(data["familles"]) == 6

    def test_famille_a_les_champs(self, client):
        r = client.get("/api/couleurs_themes")
        f = r.get_json()["familles"][0]
        assert set(f.keys()) == {"slug", "libelle", "hex_principal"}

    def test_noir_gris_present(self, client):
        """Vérifie que la 6e famille Noir/Gris est bien exposée."""
        r = client.get("/api/couleurs_themes")
        slugs = [f["slug"] for f in r.get_json()["familles"]]
        assert "noir_gris" in slugs


# ── Création ─────────────────────────────────────────────────────────────────

class TestCreation:
    def test_creer_theme_ok(self, client):
        r = client.post("/api/cycles/C04/themes", json={
            "code": "A", "nom": "Nombres", "code_couleur": "nombres",
            "description": "Une description"
        })
        assert r.status_code == 201
        t = r.get_json()["theme"]
        assert t["code"] == "A"
        assert t["cycle_code"] == "C04"

    def test_creer_theme_minimal(self, client):
        r = client.post("/api/cycles/C04/themes", json={
            "code": "A", "nom": "Nombres"
        })
        assert r.status_code == 201

    def test_creer_theme_sans_code_400(self, client):
        r = client.post("/api/cycles/C04/themes", json={"nom": "Test"})
        assert r.status_code == 400
        assert r.get_json()["code"] == "code_vide"

    def test_creer_theme_sans_nom_400(self, client):
        r = client.post("/api/cycles/C04/themes", json={"code": "A"})
        assert r.status_code == 400
        assert r.get_json()["code"] == "nom_vide"

    def test_creer_theme_doublon_code_409(self, client):
        client.post("/api/cycles/C04/themes", json={"code": "A", "nom": "N1"})
        r = client.post("/api/cycles/C04/themes", json={"code": "A", "nom": "N2"})
        assert r.status_code == 409
        assert r.get_json()["code"] == "doublon_code"

    def test_creer_theme_doublon_nom_409(self, client):
        client.post("/api/cycles/C04/themes", json={"code": "A", "nom": "N"})
        r = client.post("/api/cycles/C04/themes", json={"code": "B", "nom": "N"})
        assert r.status_code == 409
        assert r.get_json()["code"] == "doublon_nom"

    def test_creer_theme_couleur_invalide_400(self, client):
        r = client.post("/api/cycles/C04/themes", json={
            "code": "A", "nom": "N", "code_couleur": "ZZZ"
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "couleur_invalide"

    def test_creer_theme_cycle_inexistant(self, client):
        r = client.post("/api/cycles/CZZ/themes", json={"code": "A", "nom": "N"})
        assert r.status_code == 404
        assert r.get_json()["code"] == "cycle_introuvable"


# ── Lecture ──────────────────────────────────────────────────────────────────

class TestLecture:
    def test_lire_theme(self, client):
        post = client.post("/api/cycles/C04/themes",
                           json={"code": "A", "nom": "N"})
        t = post.get_json()["theme"]
        r = client.get(f"/api/themes/{t['id']}")
        assert r.status_code == 200
        assert r.get_json()["theme"]["code"] == "A"

    def test_lire_theme_inexistant_404(self, client):
        r = client.get("/api/themes/th_inexistant")
        assert r.status_code == 404

    def test_lister_themes_detail(self, client):
        client.post("/api/cycles/C04/themes", json={"code": "A", "nom": "N1"})
        client.post("/api/cycles/C04/themes", json={"code": "B", "nom": "N2"})
        r = client.get("/api/cycles/C04/themes/detail")
        assert r.status_code == 200
        themes = r.get_json()["themes"]
        assert len(themes) == 2
        assert themes[0]["nb_sequences"] == 0


# ── Modification ─────────────────────────────────────────────────────────────

class TestModification:
    def test_modifier_nom(self, client):
        post = client.post("/api/cycles/C04/themes",
                           json={"code": "A", "nom": "Ancien"})
        t_id = post.get_json()["theme"]["id"]
        r = client.put(f"/api/themes/{t_id}", json={"nom": "Nouveau"})
        assert r.status_code == 200
        assert r.get_json()["theme"]["nom"] == "Nouveau"

    def test_patch_aussi_supporte(self, client):
        post = client.post("/api/cycles/C04/themes",
                           json={"code": "A", "nom": "N"})
        t_id = post.get_json()["theme"]["id"]
        r = client.patch(f"/api/themes/{t_id}", json={"code_couleur": "nombres"})
        assert r.status_code == 200

    def test_modifier_code_doublon_409(self, client):
        client.post("/api/cycles/C04/themes", json={"code": "A", "nom": "N1"})
        post = client.post("/api/cycles/C04/themes",
                           json={"code": "B", "nom": "N2"})
        t2_id = post.get_json()["theme"]["id"]
        r = client.put(f"/api/themes/{t2_id}", json={"code": "A"})
        assert r.status_code == 409

    def test_modifier_theme_inexistant_404(self, client):
        r = client.put("/api/themes/th_inexistant", json={"nom": "N"})
        assert r.status_code == 404


# ── Suppression ──────────────────────────────────────────────────────────────

class TestSuppression:
    def test_supprimer_ok(self, client):
        post = client.post("/api/cycles/C04/themes",
                           json={"code": "A", "nom": "N"})
        t_id = post.get_json()["theme"]["id"]
        r = client.delete(f"/api/themes/{t_id}")
        assert r.status_code == 200
        assert r.get_json()["supprime"] is True

        r = client.get(f"/api/themes/{t_id}")
        assert r.status_code == 404

    def test_supprimer_refuse_si_sequences_rattachees(self, client):
        post = client.post("/api/cycles/C04/themes",
                           json={"code": "A", "nom": "N"})
        t_id = post.get_json()["theme"]["id"]

        # Ajouter une séquence rattachée (côté SQL direct)
        store = client.application.json_store
        with store._conn() as conn:
            conn.execute(
                "INSERT INTO sequences_du_cycle "
                "(id, cycle_code, code, numero, nom, theme_id) "
                "VALUES ('sc_1', 'C04', 'S01', 1, 'S1', ?)",
                (t_id,)
            )
            conn.commit()

        r = client.delete(f"/api/themes/{t_id}")
        assert r.status_code == 409
        assert r.get_json()["code"] == "en_usage"

    def test_supprimer_inexistant_404(self, client):
        r = client.delete("/api/themes/th_inexistant")
        assert r.status_code == 404
