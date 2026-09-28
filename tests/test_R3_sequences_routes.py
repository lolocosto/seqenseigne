"""tests/test_R3_sequences_routes.py — Tests des routes R3."""

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
    from routes.sequences_du_cycle import bp_sequences_du_cycle
    app = create_app(data_dir=data_dir)
    if "sequences_du_cycle" not in app.blueprints:
        app.register_blueprint(bp_sequences_du_cycle)
    app.config["TESTING"] = True

    # Créer cycle + thèmes
    store = app.json_store
    conn = sqlite3.connect(str(store.db_path))
    conn.execute("INSERT INTO cycles (code, nom) VALUES ('C04', 'Cycle 4')")
    conn.execute(
        "INSERT INTO themes (id, cycle_code, code, nom) "
        "VALUES ('th_A', 'C04', 'A', 'Nombres')"
    )
    conn.commit()
    conn.close()

    return app.test_client()


class TestCreation:
    def test_creer_ok(self, client):
        r = client.post("/api/cycles/C04/sequences", json={
            "code": "S01", "numero": 1, "nom": "Test"
        })
        assert r.status_code == 201
        assert r.get_json()["sequence"]["code"] == "S01"

    def test_creer_avec_theme(self, client):
        r = client.post("/api/cycles/C04/sequences", json={
            "code": "S01", "numero": 1, "nom": "Test", "theme_id": "th_A"
        })
        assert r.status_code == 201
        assert r.get_json()["sequence"]["theme_id"] == "th_A"

    def test_creer_code_vide_400(self, client):
        r = client.post("/api/cycles/C04/sequences", json={
            "numero": 1, "nom": "Test"
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "code_vide"

    def test_creer_numero_vide_400(self, client):
        r = client.post("/api/cycles/C04/sequences", json={
            "code": "S01", "nom": "Test"
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "numero_vide"

    def test_creer_doublon_code_409(self, client):
        client.post("/api/cycles/C04/sequences", json={
            "code": "S01", "numero": 1, "nom": "X"
        })
        r = client.post("/api/cycles/C04/sequences", json={
            "code": "S01", "numero": 2, "nom": "Y"
        })
        assert r.status_code == 409
        assert r.get_json()["code"] == "doublon_code"

    def test_creer_doublon_numero_409(self, client):
        client.post("/api/cycles/C04/sequences", json={
            "code": "S01", "numero": 1, "nom": "X"
        })
        r = client.post("/api/cycles/C04/sequences", json={
            "code": "S02", "numero": 1, "nom": "Y"
        })
        assert r.status_code == 409
        assert r.get_json()["code"] == "doublon_numero"

    def test_creer_theme_invalide_400(self, client):
        r = client.post("/api/cycles/C04/sequences", json={
            "code": "S01", "numero": 1, "nom": "X", "theme_id": "th_zzz"
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "theme_invalide"

    def test_creer_cycle_inexistant_404(self, client):
        r = client.post("/api/cycles/CZZ/sequences", json={
            "code": "S01", "numero": 1, "nom": "X"
        })
        assert r.status_code == 404


class TestLecture:
    def test_lister_detail(self, client):
        client.post("/api/cycles/C04/sequences",
                    json={"code": "S01", "numero": 1, "nom": "A"})
        client.post("/api/cycles/C04/sequences",
                    json={"code": "S02", "numero": 2, "nom": "B", "theme_id": "th_A"})
        r = client.get("/api/cycles/C04/sequences/detail")
        seqs = r.get_json()["sequences"]
        assert len(seqs) == 2
        assert seqs[0]["numero"] == 1
        assert seqs[1]["theme_code"] == "A"

    def test_lire_sequence(self, client):
        post = client.post("/api/cycles/C04/sequences",
                           json={"code": "S01", "numero": 1, "nom": "X",
                                 "theme_id": "th_A"})
        s_id = post.get_json()["sequence"]["id"]
        r = client.get(f"/api/sequences_du_cycle/{s_id}")
        assert r.status_code == 200
        assert r.get_json()["sequence"]["theme_couleur"] == ""  # pas de couleur sur th_A

    def test_lire_inexistante_404(self, client):
        r = client.get("/api/sequences_du_cycle/sc_zzz")
        assert r.status_code == 404


class TestModification:
    def test_modifier_nom(self, client):
        post = client.post("/api/cycles/C04/sequences",
                           json={"code": "S01", "numero": 1, "nom": "Ancien"})
        s_id = post.get_json()["sequence"]["id"]
        r = client.put(f"/api/sequences_du_cycle/{s_id}",
                       json={"nom": "Nouveau"})
        assert r.status_code == 200
        assert r.get_json()["sequence"]["nom"] == "Nouveau"

    def test_changer_theme(self, client):
        post = client.post("/api/cycles/C04/sequences",
                           json={"code": "S01", "numero": 1, "nom": "X"})
        s_id = post.get_json()["sequence"]["id"]
        r = client.patch(f"/api/sequences_du_cycle/{s_id}",
                         json={"theme_id": "th_A"})
        assert r.status_code == 200
        assert r.get_json()["sequence"]["theme_id"] == "th_A"

    def test_detacher_theme(self, client):
        post = client.post("/api/cycles/C04/sequences",
                           json={"code": "S01", "numero": 1, "nom": "X",
                                 "theme_id": "th_A"})
        s_id = post.get_json()["sequence"]["id"]
        r = client.patch(f"/api/sequences_du_cycle/{s_id}",
                         json={"detacher_theme": True})
        assert r.status_code == 200
        assert r.get_json()["sequence"]["theme_id"] is None


class TestSuppression:
    def test_supprimer_ok(self, client):
        post = client.post("/api/cycles/C04/sequences",
                           json={"code": "S01", "numero": 1, "nom": "X"})
        s_id = post.get_json()["sequence"]["id"]
        r = client.delete(f"/api/sequences_du_cycle/{s_id}")
        assert r.status_code == 200
        assert r.get_json()["supprime"] is True

    def test_refus_si_atomes(self, client):
        post = client.post("/api/cycles/C04/sequences",
                           json={"code": "S01", "numero": 1, "nom": "X"})
        s_id = post.get_json()["sequence"]["id"]

        store = client.application.json_store
        with store._conn() as conn:
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

        r = client.delete(f"/api/sequences_du_cycle/{s_id}")
        assert r.status_code == 409
        data = r.get_json()
        assert data["code"] == "en_usage"
        assert "details" in data
        assert data["details"]["objectifs"] == 1

    def test_supprimer_inexistante_404(self, client):
        r = client.delete("/api/sequences_du_cycle/sc_zzz")
        assert r.status_code == 404
