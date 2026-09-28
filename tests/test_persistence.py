"""tests/test_persistence.py — Tests de la couche persistence."""

import pytest


# ── YamlStore ─────────────────────────────────────────────────────────────────

class TestYamlStore:

    def test_existe_faux_si_absent(self, yaml_store):
        assert not yaml_store.existe("N10")

    def test_lire_brut_absent_retourne_none(self, yaml_store):
        assert yaml_store.lire_brut("N10") is None

    def test_ecrire_et_lire_brut(self, yaml_store):
        payload = {"niveau": "N10", "sequences": [{"code": "S01", "nom": "Test"}]}
        yaml_store.ecrire("N10", payload)
        result = yaml_store.lire_brut("N10")
        assert result["niveau"] == "N10"
        assert result["sequences"][0]["code"] == "S01"

    def test_lire_brut_yaml_vide_retourne_none(self, yaml_store, data_dir):
        # Fichier présent mais sans clé "sequences"
        (data_dir / "N10_sequences.yaml").write_text("niveau: N10\n", encoding="utf-8")
        assert yaml_store.lire_brut("N10") is None

    def test_statut_tous_absents(self, yaml_store):
        statut = yaml_store.statut()
        for niveau in ("N09", "N10", "N11", "N12"):
            assert statut[niveau]["present"] is False
            assert statut[niveau]["sequences"] == 0

    def test_statut_apres_ecriture(self, yaml_store):
        payload = {
            "niveau": "N10",
            "sequences": [{"code": "S01"}, {"code": "S02"}],
        }
        yaml_store.ecrire("N10", payload)
        statut = yaml_store.statut()
        assert statut["N10"]["present"] is True
        assert statut["N10"]["sequences"] == 2


# ── CsvStore ──────────────────────────────────────────────────────────────────

class TestCsvStore:

    def test_lire_c04_sequences(self, csv_store):
        seqs = csv_store.lire_c04_sequences()
        assert "S01" in seqs
        assert seqs["S01"]["nom"] == "Représentations d'un nombre"
        assert seqs["S01"]["numero"] == 1

    def test_lire_c04_themes(self, csv_store):
        themes = csv_store.lire_c04_themes()
        assert "A" in themes
        assert themes["A"]["nom"] == "Nombres et Calculs"

    def test_c04_disponible(self, csv_store):
        assert csv_store.c04_disponible()

    def test_c04_indisponible(self, data_dir):
        from persistence.csv_store import CsvStore
        (data_dir / "C04_sequences.csv").unlink()
        cs = CsvStore(data_dir)
        assert not cs.c04_disponible()
        assert cs.lire_c04_sequences() == {}

    def test_sequences_avec_themes(self, csv_store):
        result = csv_store.sequences_avec_themes()
        assert len(result) == 3
        assert result[0]["code"] == "S01"
        assert result[0]["theme_nom"] == "Nombres et Calculs"

    def test_sequences_avec_themes_triees_par_numero(self, csv_store):
        result = csv_store.sequences_avec_themes()
        numeros = [r["numero"] for r in result]
        assert numeros == sorted(numeros)
