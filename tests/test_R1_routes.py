"""tests/test_R1_routes.py — Tests des routes Flask R1."""

import pytest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence.sqlite_store import SqliteStore


CSV_THEMES = """Code,Nom,CodeCouleur,Description
"A","Nombres et Calculs","nombres","Description A"
"B","Données et fonctions","donnees","Description B"
"""

CSV_SEQUENCES = """Code,Numero,Nom,Theme
S01,01,"Représentations d'un nombre","A"
S07,07,"Proportionnalité","B"
"""


@pytest.fixture
def client(tmp_path):
    """Client Flask avec le blueprint cycle enregistré."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Seeder les JSON minimaux (l'app en attend certains)
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

    # Créer les CSV dans data/
    (data_dir / "C04_themes.csv").write_text(CSV_THEMES, encoding="utf-8")
    (data_dir / "C04_sequences.csv").write_text(CSV_SEQUENCES, encoding="utf-8")

    from app import create_app
    from routes.cycle import bp_cycle
    app = create_app(data_dir=data_dir)
    if "cycle" not in app.blueprints:
        app.register_blueprint(bp_cycle)
    app.config["TESTING"] = True
    return app.test_client()


class TestImportViaApi:
    def test_importer_cycle_basique(self, client):
        # v0.10.2 : C04 est déjà auto-importé au démarrage de l'app.
        # L'appel manuel POST /api/admin/cycle/importer trouve donc le
        # cycle déjà en BDD et fait des UPDATE plutôt que des INSERT.
        r = client.post("/api/admin/cycle/importer",
                        json={"cycle_code": "C04"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        # crees=0 (déjà fait) ; mis_a_jour=2 (UPDATE des 2 thèmes existants)
        assert data["rapport"]["themes"]["crees"] == 0
        assert data["rapport"]["themes"]["mis_a_jour"] == 2
        assert data["rapport"]["sequences"]["mis_a_jour"] == 2

    def test_importer_sans_cycle_code_400(self, client):
        r = client.post("/api/admin/cycle/importer", json={})
        assert r.status_code == 400
        assert r.get_json()["code"] == "champ_manquant"

    def test_importer_fichier_inexistant(self, client):
        r = client.post("/api/admin/cycle/importer", json={
            "cycle_code": "C99",  # pas de CSV avec ce prefix
        })
        assert r.status_code == 400
        assert r.get_json()["code"] == "themes_absent"

    def test_importer_idempotent(self, client):
        # v0.10.2 : C04 est auto-importé au démarrage. Les deux POST
        # successifs sont donc tous les deux idempotents (UPDATE only).
        r1 = client.post("/api/admin/cycle/importer", json={"cycle_code": "C04"})
        r2 = client.post("/api/admin/cycle/importer", json={"cycle_code": "C04"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        r1_rapp = r1.get_json()["rapport"]
        r2_rapp = r2.get_json()["rapport"]
        assert r1_rapp["themes"]["crees"] == 0
        assert r1_rapp["themes"]["mis_a_jour"] == 2
        assert r2_rapp["themes"]["crees"] == 0
        assert r2_rapp["themes"]["mis_a_jour"] == 2


class TestLectures:
    def test_lister_cycles_apres_demarrage(self, client):
        # v0.10.2 : C04 est auto-importé au démarrage, donc la liste
        # n'est plus vide à l'ouverture de l'app.
        r = client.get("/api/cycles")
        assert r.status_code == 200
        cycles = r.get_json()["cycles"]
        assert len(cycles) == 1
        assert cycles[0]["code"] == "C04"

    def test_lister_cycles_apres_import(self, client):
        client.post("/api/admin/cycle/importer", json={"cycle_code": "C04"})
        r = client.get("/api/cycles")
        cycles = r.get_json()["cycles"]
        assert len(cycles) == 1
        assert cycles[0]["code"] == "C04"

    def test_lister_themes(self, client):
        client.post("/api/admin/cycle/importer", json={"cycle_code": "C04"})
        r = client.get("/api/cycles/C04/themes")
        themes = r.get_json()["themes"]
        assert len(themes) == 2
        codes = {t["code"] for t in themes}
        assert codes == {"A", "B"}

    def test_lister_sequences(self, client):
        client.post("/api/admin/cycle/importer", json={"cycle_code": "C04"})
        r = client.get("/api/cycles/C04/sequences")
        seqs = r.get_json()["sequences"]
        assert len(seqs) == 2
        codes = {s["code"] for s in seqs}
        assert codes == {"S01", "S07"}

    def test_sequences_avec_theme_code(self, client):
        """La réponse lister_sequences joint le thème pour afficher son code."""
        client.post("/api/admin/cycle/importer", json={"cycle_code": "C04"})
        r = client.get("/api/cycles/C04/sequences")
        seqs = r.get_json()["sequences"]
        par_code = {s["code"]: s for s in seqs}
        assert par_code["S01"]["theme_code"] == "A"
        assert par_code["S07"]["theme_code"] == "B"


class TestCyclesMultiples:
    def test_importer_deux_cycles(self, client, tmp_path):
        # On a C04_* déjà dans la fixture, on ajoute C03
        # en réutilisant les mêmes CSV sous un autre code
        # Pas pratique via l'API : on passe les chemins explicitement
        from flask import current_app
        # Récupérer le data_dir
        from app import create_app
        # En réalité, on va juste tester qu'un import via chemins explicites marche
        r = client.post("/api/admin/cycle/importer", json={
            "cycle_code":       "C03",
            "cycle_nom":        "Cycle 3",
            "chemin_themes":    "C04_themes.csv",     # réutilisation
            "chemin_sequences": "C04_sequences.csv",
        })
        assert r.status_code == 200, r.get_json()

        # Les deux cycles doivent coexister
        client.post("/api/admin/cycle/importer", json={"cycle_code": "C04"})
        r = client.get("/api/cycles")
        cycles = r.get_json()["cycles"]
        assert {c["code"] for c in cycles} == {"C03", "C04"}
