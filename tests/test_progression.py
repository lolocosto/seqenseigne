"""tests/test_progression.py — Tests progression et import historique."""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.progression import (
    progression_id, progression_vide, modifier_creneau,
    reordonner_creneaux, valider_progression, snapshot_creneau,
)
from importers.sequencesdb import (
    lire_sequencesdb, lire_suivi_historique, _normaliser_code_obj,
    _date_complete, _rang_creneau_pour_sequence,
)


# ── Fixtures CSV ───────────────────────────────────────────────────────────────

@pytest.fixture
def sequencesdb_dir(tmp_path):
    """Crée un répertoire SequencesDB minimal pour les tests."""
    d = tmp_path / "SequencesDB"
    d.mkdir()

    # cycle4-sequences.csv
    (d / "cycle4-sequences.csv").write_text(
        "Code,Numero,Nom,Theme\n"
        "S01,1,Représentations d'un nombre,A\n"
        "S02,2,Comparaison de nombres,A\n"
        "S03,3,Calcul numérique,A\n",
        encoding="utf-8",
    )

    # Sem1 : S01 (1e partie) + S02
    (d / "Sem1-sequences.csv").write_text(
        "Code,Numero,Nom,Theme,Debut,Fin\n"
        "S01,1,Représentations d'un nombre (1e partie),A,07/09,15/09\n"
        "S02,2,Comparaison de nombres,A,19/09,29/09\n",
        encoding="utf-8",
    )

    # Sem2 : S01 (2e partie) + S03
    (d / "Sem2-sequences.csv").write_text(
        "Code,Numero,Nom,Theme,Debut,Fin\n"
        "S01,1,Représentations d'un nombre (2e partie),A,09/01,19/01\n"
        "S03,3,Calcul numérique,A,23/01,02/02\n",
        encoding="utf-8",
    )

    # Objectifs N11S01 — 2 créneaux : 01-04 + 11-13
    (d / "N11S01Objectifs.csv").write_text(
        "Code,FinCycle,Nom,MaitriseTB,MaitriseS,MaitriseF\n"
        "Objectif 01,O,Connaître le cours,Fiche résumé,Connaît le cours,A recopié le cours\n"
        "Objectif 02,N,Utiliser les puissances,Résout un problème,Utilise les puissances,Utilise exposants positifs\n"
        "Objectif 03,N,Puissances de 10,Résout un problème,Utilise puissances de 10,Positifs seulement\n"
        "Objectif 11,O,Connaître le cours (2),Fiche résumé,Connaît le cours,A recopié le cours\n"
        "Objectif 12,N,Utiliser la racine carrée,Résout un problème,Utilise la racine,Racine des parfaits\n"
        "Objectif 13,N,Repérer un rationnel,Résout un problème,Repère sur droite,Même dénominateur\n",
        encoding="utf-8",
    )

    # Connaissances N11S01
    (d / "N11S01Connaissances.csv").write_text(
        "Code,Nom\n"
        "C01,Puissances d'un nombre.\n"
        "C02,Puissances de 10.\n",
        encoding="utf-8",
    )

    # Objectifs N11S02 — 1 créneau : 01-02
    (d / "N11S02Objectifs.csv").write_text(
        "Code,FinCycle,Nom,MaitriseTB,MaitriseS,MaitriseF\n"
        "Objectif 01,O,Connaître le cours,Fiche résumé,Connaît le cours,A recopié le cours\n"
        "Objectif 02,N,Comparer des rationnels,Résout un problème,Compare toutes repr.,Décimaux seulement\n",
        encoding="utf-8",
    )
    (d / "N11S02Connaissances.csv").write_text(
        "Code,Nom\n"
        "C01,Relation d'ordre.\n",
        encoding="utf-8",
    )

    # Objectifs N11S03
    (d / "N11S03Objectifs.csv").write_text(
        "Code,FinCycle,Nom,MaitriseTB,MaitriseS,MaitriseF\n"
        "Objectif 01,O,Connaître le cours,Fiche résumé,Connaît le cours,A recopié le cours\n"
        "Objectif 02,N,Calculer avec décimaux,Résout un problème,Multiplie et divise,Entiers relatifs\n",
        encoding="utf-8",
    )
    (d / "N11S03Connaissances.csv").write_text("Code,Nom\n", encoding="utf-8")

    return d


@pytest.fixture
def suivi_csv_dir(tmp_path):
    """Crée des fichiers SXXsuivi.csv pour les tests."""
    d = tmp_path / "suivi"
    d.mkdir()

    # S01suivi.csv avec objectifs 01-03 et 11-13 (2 créneaux)
    (d / "S01suivi.csv").write_text(
        "Numero,Nom,Prenom,Objectif 01,Objectif 02,Objectif 03,Objectif 11,Objectif 12,Objectif 13\n"
        '1,DUPONT,Alice,F,A,F,I,NE,-\n'
        '2,MARTIN,Bob,I,I,I,F,F,F\n',
        encoding="utf-8",
    )

    # S02suivi.csv avec objectifs 01-02 (1 créneau)
    (d / "S02suivi.csv").write_text(
        "Numero,Nom,Prenom,Objectif 01,Objectif 02\n"
        '1,DUPONT,Alice,A,E\n'
        '2,MARTIN,Bob,F,F\n',
        encoding="utf-8",
    )

    return d


# ── services/progression.py ────────────────────────────────────────────────────

class TestProgressionId:
    """
    Les ids de progression sont désormais des UUID opaques 'pg_xxx'.
    Ils ne portent plus de sémantique niveau/année/établissement ; la clé
    métier (niveau, annee, etablissement) est portée par les colonnes via
    un index UNIQUE.
    """
    def test_format(self):
        pid = progression_id("N11", "2023-2024")
        assert pid.startswith("pg_")
        assert len(pid) == 11

    def test_ids_distincts_meme_parametres(self):
        # Deux appels → deux ids différents (aléatoire, pas déterministe)
        p1 = progression_id("N10", "2025-2026")
        p2 = progression_id("N10", "2025-2026")
        assert p1 != p2


class TestProgressionVide:
    def _seqs(self):
        return [
            {"code": "S01", "numero": 1, "nom": "Seq 1", "theme": "A"},
            {"code": "S02", "numero": 2, "nom": "Seq 2", "theme": "A"},
            {"code": "S03", "numero": 3, "nom": "Seq 3", "theme": "B"},
        ]

    def test_structure(self):
        prog = progression_vide("N11", "2023-2024", self._seqs())
        assert prog["niveau"] == "N11"
        assert prog["annee"] == "2023-2024"
        assert prog["id"].startswith("pg_")  # UUID opaque
        # v0.19.0 — plus de champ `source` (aucune distinction entre
        # progressions ; la colonne a été supprimée du schéma).
        assert "source" not in prog

    def test_creneaux_dans_ordre(self):
        prog = progression_vide("N11", "2023-2024", self._seqs())
        codes = [c["sequence"] for c in prog["creneaux"]]
        assert codes == ["S01", "S02", "S03"]

    def test_creneaux_ordre_numerique(self):
        # Séquences désordonnées en entrée → triées par numéro
        seqs = [
            {"code": "S03", "numero": 3, "nom": "C", "theme": "A"},
            {"code": "S01", "numero": 1, "nom": "A", "theme": "A"},
            {"code": "S02", "numero": 2, "nom": "B", "theme": "A"},
        ]
        prog = progression_vide("N11", "2023-2024", seqs)
        codes = [c["sequence"] for c in prog["creneaux"]]
        assert codes == ["S01", "S02", "S03"]

    def test_champs_vides(self):
        prog = progression_vide("N11", "2023-2024", self._seqs())
        for c in prog["creneaux"]:
            assert c["date_debut"] is None
            assert c["periode"] is None
            assert c["objectifs"] == []


class TestModifierCreneau:
    def _prog(self):
        seqs = [{"code": "S01", "numero": 1, "nom": "S", "theme": "A"}]
        prog = progression_vide("N11", "2023-2024", seqs)
        return prog

    def test_modifier_date(self):
        prog = self._prog()
        cid = prog["creneaux"][0]["id"]
        prog, err = modifier_creneau(prog, cid, {"date_debut": "2023-09-07"})
        assert err is None
        assert prog["creneaux"][0]["date_debut"] == "2023-09-07"

    def test_modifier_periode(self):
        prog = self._prog()
        cid = prog["creneaux"][0]["id"]
        prog, err = modifier_creneau(prog, cid, {"periode": "Sem1"})
        assert err is None
        assert prog["creneaux"][0]["periode"] == "Sem1"

    def test_creneau_inconnu(self):
        prog = self._prog()
        prog, err = modifier_creneau(prog, "INCONNU", {"periode": "Sem1"})
        assert err is not None

    def test_champ_non_editable_ignore(self):
        prog = self._prog()
        cid = prog["creneaux"][0]["id"]
        prog, err = modifier_creneau(prog, cid, {"sequence": "S99", "periode": "Sem1"})
        assert prog["creneaux"][0]["sequence"] == "S01"  # non modifié
        assert prog["creneaux"][0]["periode"] == "Sem1"   # modifié


class TestReordonnerCreneaux:
    def _prog_3(self):
        seqs = [
            {"code": f"S0{i}", "numero": i, "nom": f"S{i}", "theme": "A"}
            for i in range(1, 4)
        ]
        return progression_vide("N11", "2023-2024", seqs)

    def test_reordonner(self):
        prog = self._prog_3()
        ids = [c["id"] for c in prog["creneaux"]]
        # Inverser l'ordre
        nouveau_ordre = list(reversed(ids))
        prog = reordonner_creneaux(prog, nouveau_ordre)
        seqs_apres = [c["sequence"] for c in prog["creneaux"]]
        assert seqs_apres == ["S03", "S02", "S01"]

    def test_ordres_mis_a_jour(self):
        prog = self._prog_3()
        ids = [c["id"] for c in prog["creneaux"]]
        prog = reordonner_creneaux(prog, ids)
        ordres = [c["ordre"] for c in prog["creneaux"]]
        assert ordres == [1, 2, 3]


class TestValiderProgression:
    def test_progression_valide(self):
        seqs = [{"code": "S01", "numero": 1, "nom": "S", "theme": "A"}]
        prog = progression_vide("N11", "2023-2024", seqs)
        assert valider_progression(prog) == []

    def test_sequence_manquante(self):
        prog = {
            "creneaux": [{"id": "x", "sequence": "", "partie": None,
                          "objectifs": [], "date_debut": None}]
        }
        avertissements = valider_progression(prog)
        assert any("séquence manquante" in w for w in avertissements)


class TestSnapshotCreneau:
    def test_champs_retenus(self):
        creneau = {
            "id": "abc", "sequence": "S01", "partie": "1e partie",
            "periode": "Sem1", "date_debut": "2023-09-07", "date_fin": "2023-09-15",
            "ordre": 1,
            "objectifs": [{"code": "01", "nom": "Cours", "criteres": {}}],
            "connaissances": [{"code": "C01", "nom": "Puissances"}],
        }
        snap = snapshot_creneau(creneau)
        assert snap["id"] == "abc"
        assert snap["sequence"] == "S01"
        assert snap["partie"] == "1e partie"
        assert snap["objectifs"][0] == {"code": "01", "nom": "Cours"}
        # connaissances et critères ne doivent pas apparaître dans le snapshot
        assert "connaissances" not in snap


# ── importers/sequencesdb.py ───────────────────────────────────────────────────

class TestNormaliserCodeObj:
    def test_objectif_01(self):
        assert _normaliser_code_obj("Objectif 01") == "01"

    def test_objectif_11(self):
        assert _normaliser_code_obj("Objectif 11") == "11"

    def test_chiffre_seul(self):
        assert _normaliser_code_obj("02") == "02"

    def test_chiffre_simple(self):
        assert _normaliser_code_obj("2") == "02"


class TestDateComplete:
    def test_debut_annee(self):
        # Septembre → première année
        assert _date_complete("07/09", "2023-2024") == "2023-09-07"

    def test_fin_annee(self):
        # Janvier → deuxième année
        assert _date_complete("09/01", "2023-2024") == "2024-01-09"

    def test_juillet_pivot(self):
        assert _date_complete("15/07", "2023-2024") == "2023-07-15"

    def test_vide(self):
        assert _date_complete("", "2023-2024") is None

    def test_tiret(self):
        assert _date_complete("-", "2023-2024") is None


class TestRangCreneauPourSequence:
    def test_premiere_occurrence(self):
        assert _rang_creneau_pour_sequence([], "S01") == 1

    def test_deuxieme_occurrence(self):
        creneaux = [{"sequence": "S01"}]
        assert _rang_creneau_pour_sequence(creneaux, "S01") == 2

    def test_autre_sequence_ne_compte_pas(self):
        creneaux = [{"sequence": "S02"}]
        assert _rang_creneau_pour_sequence(creneaux, "S01") == 1


class TestLireSequencesDB:
    def test_structure_base(self, sequencesdb_dir):
        prog = lire_sequencesdb(str(sequencesdb_dir), "N11", "2023-2024")
        assert prog["niveau"] == "N11"
        assert prog["annee"] == "2023-2024"
        assert prog["id"].startswith("pg_")
        assert prog["source"] == "sequencesdb"

    def test_creneaux_created(self, sequencesdb_dir):
        prog = lire_sequencesdb(str(sequencesdb_dir), "N11", "2023-2024")
        # Sem1: S01 (1e partie) + S02 = 2 créneaux
        # Sem2: S01 (2e partie) + S03 = 2 créneaux
        assert len(prog["creneaux"]) == 4

    def test_s01_deux_creneaux(self, sequencesdb_dir):
        prog = lire_sequencesdb(str(sequencesdb_dir), "N11", "2023-2024")
        s01_creneaux = [c for c in prog["creneaux"] if c["sequence"] == "S01"]
        assert len(s01_creneaux) == 2

    def test_parties_detectees(self, sequencesdb_dir):
        prog = lire_sequencesdb(str(sequencesdb_dir), "N11", "2023-2024")
        s01_creneaux = [c for c in prog["creneaux"] if c["sequence"] == "S01"]
        parties = [c["partie"] for c in s01_creneaux]
        assert any("partie" in (p or "").lower() for p in parties)

    def test_dates_converties(self, sequencesdb_dir):
        prog = lire_sequencesdb(str(sequencesdb_dir), "N11", "2023-2024")
        cr_s01_sem1 = next(
            c for c in prog["creneaux"]
            if c["sequence"] == "S01" and c["periode"] == "Sem1"
        )
        assert cr_s01_sem1["date_debut"] == "2023-09-07"
        assert cr_s01_sem1["date_fin"]   == "2023-09-15"

    def test_objectifs_creneau_1(self, sequencesdb_dir):
        prog = lire_sequencesdb(str(sequencesdb_dir), "N11", "2023-2024")
        cr_s01_sem1 = next(
            c for c in prog["creneaux"]
            if c["sequence"] == "S01" and c["periode"] == "Sem1"
        )
        codes = [o["code"] for o in cr_s01_sem1["objectifs"]]
        # Le 1er créneau contient les objectifs 01–09
        assert "01" in codes
        assert "02" in codes
        assert "11" not in codes  # le 11 va dans le 2e créneau

    def test_objectifs_creneau_2(self, sequencesdb_dir):
        prog = lire_sequencesdb(str(sequencesdb_dir), "N11", "2023-2024")
        cr_s01_sem2 = next(
            c for c in prog["creneaux"]
            if c["sequence"] == "S01" and c["periode"] == "Sem2"
        )
        codes = [o["code"] for o in cr_s01_sem2["objectifs"]]
        assert "11" in codes
        assert "12" in codes
        assert "01" not in codes  # le 01 est dans le 1er créneau

    def test_criteres_migres(self, sequencesdb_dir):
        prog = lire_sequencesdb(str(sequencesdb_dir), "N11", "2023-2024")
        cr = next(c for c in prog["creneaux"] if c["sequence"] == "S01" and c["periode"] == "Sem1")
        obj02 = next(o for o in cr["objectifs"] if o["code"] == "02")
        assert "4" in obj02["criteres"]
        assert "3" in obj02["criteres"]
        assert "2" in obj02["criteres"]

    def test_connaissances_creneau_1(self, sequencesdb_dir):
        prog = lire_sequencesdb(str(sequencesdb_dir), "N11", "2023-2024")
        cr_sem1 = next(
            c for c in prog["creneaux"]
            if c["sequence"] == "S01" and c["periode"] == "Sem1"
        )
        assert len(cr_sem1["connaissances"]) == 2

    def test_periodes_detectees(self, sequencesdb_dir):
        prog = lire_sequencesdb(str(sequencesdb_dir), "N11", "2023-2024")
        assert "Sem1" in prog["periodes"]
        assert "Sem2" in prog["periodes"]


class TestLireSuiviHistorique:
    def _progression_avec_creneaux(self):
        """Progression avec 2 créneaux pour S01 et 1 pour S02."""
        return {
            "id": "N11-2023-2024",
            "creneaux": [
                {
                    "id": "cr_s01_1",
                    "sequence": "S01",
                    "objectifs": [
                        {"code": "01"}, {"code": "02"}, {"code": "03"}
                    ],
                },
                {
                    "id": "cr_s01_2",
                    "sequence": "S01",
                    "objectifs": [
                        {"code": "11"}, {"code": "12"}, {"code": "13"}
                    ],
                },
                {
                    "id": "cr_s02_1",
                    "sequence": "S02",
                    "objectifs": [
                        {"code": "01"}, {"code": "02"}
                    ],
                },
            ],
        }

    def _eleves(self):
        return [
            {"id": "e01", "nom": "DUPONT", "prenom": "Alice"},
            {"id": "e02", "nom": "MARTIN", "prenom": "Bob"},
        ]

    def test_structure_suivi(self, suivi_csv_dir):
        prog = self._progression_avec_creneaux()
        suivi = lire_suivi_historique(str(suivi_csv_dir), prog, self._eleves())
        assert suivi["progression_id"] == "N11-2023-2024"
        assert "e01" in suivi["eleves"]
        assert "e02" in suivi["eleves"]

    def test_migration_codes(self, suivi_csv_dir):
        prog = self._progression_avec_creneaux()
        suivi = lire_suivi_historique(str(suivi_csv_dir), prog, self._eleves())
        # Alice : Objectif 01 = F → 2, Objectif 02 = A → 3
        e01 = suivi["eleves"]["e01"]
        niv_01 = e01["cr_s01_1"]["S01"]["01"]["niveau"]
        niv_02 = e01["cr_s01_1"]["S01"]["02"]["niveau"]
        assert niv_01 == "2"   # F → 2
        assert niv_02 == "3"   # A → 3

    def test_tiret_devient_0_legacy(self, suivi_csv_dir):
        prog = self._progression_avec_creneaux()
        suivi = lire_suivi_historique(str(suivi_csv_dir), prog, self._eleves())
        # Alice : Objectif 13 = - → A (absent)
        e01 = suivi["eleves"]["e01"]
        niv_13 = e01["cr_s01_2"]["S01"]["13"]["niveau"]
        assert niv_13 == "0"

    def test_NE_reste_NE(self, suivi_csv_dir):
        prog = self._progression_avec_creneaux()
        suivi = lire_suivi_historique(str(suivi_csv_dir), prog, self._eleves())
        # Alice : Objectif 12 = NE → NE
        e01 = suivi["eleves"]["e01"]
        niv_12 = e01["cr_s01_2"]["S01"]["12"]["niveau"]
        assert niv_12 == "NE"

    def test_objectifs_bon_creneau(self, suivi_csv_dir):
        """Les objectifs 11-13 vont dans le 2e créneau, pas le 1er."""
        prog = self._progression_avec_creneaux()
        suivi = lire_suivi_historique(str(suivi_csv_dir), prog, self._eleves())
        e01 = suivi["eleves"]["e01"]
        assert "11" in e01.get("cr_s01_2", {}).get("S01", {})
        assert "11" not in e01.get("cr_s01_1", {}).get("S01", {})

    def test_source_csv_historique(self, suivi_csv_dir):
        prog = self._progression_avec_creneaux()
        suivi = lire_suivi_historique(str(suivi_csv_dir), prog, self._eleves())
        e01 = suivi["eleves"]["e01"]
        source = e01["cr_s01_1"]["S01"]["01"]["source"]
        assert source == "csv_historique"

    def test_eleve_inconnu_ignore(self, suivi_csv_dir):
        """Un élève présent dans le CSV mais pas dans la liste est ignoré."""
        eleves_reduits = [{"id": "e01", "nom": "DUPONT", "prenom": "Alice"}]
        prog = self._progression_avec_creneaux()
        suivi = lire_suivi_historique(str(suivi_csv_dir), prog, eleves_reduits)
        assert "e02" not in suivi["eleves"]

    def test_s02_creneau_correct(self, suivi_csv_dir):
        prog = self._progression_avec_creneaux()
        suivi = lire_suivi_historique(str(suivi_csv_dir), prog, self._eleves())
        e01 = suivi["eleves"]["e01"]
        # S02 obj 01 = A → 3
        niv = e01["cr_s02_1"]["S02"]["01"]["niveau"]
        assert niv == "3"


# ── Routes progression ────────────────────────────────────────────────────────

class TestRoutesProgression:

    def test_get_progression_inexistante(self, client):
        r = client.get("/api/progression/N11")
        assert r.status_code == 404

    def test_reset_cree_progression_vide(self, client):
        r = client.post("/api/progression/N10/reset",
                        json={"annee": "2025-2026"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["niveau"] == "N10"
        assert data["annee"] == "2025-2026"
        assert len(data["creneaux"]) == 3  # 3 séquences dans le CSV de test

    def test_get_apres_reset(self, client):
        client.post("/api/progression/N10/reset", json={"annee": "2025-2026"})
        r = client.get("/api/progression/N10")
        assert r.status_code == 200
        data = r.get_json()
        # L'id est désormais un UUID opaque 'pg_xxx' ; le niveau et l'année
        # sont portés par les champs dédiés, pas par l'id.
        assert data["id"].startswith("pg_")
        assert data["niveau"] == "N10"
        assert data["annee"] == "2025-2026"

    def test_save_progression(self, client):
        prog = {
            "id": "N10-2025-2026", "niveau": "N10", "annee": "2025-2026",
            "etablissement": "",
            "source": "manuel", "periodes": [], "creneaux": [],
        }
        r = client.post("/api/progression/N10", json=prog)
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_modifier_creneau(self, client):
        # Créer progression d'abord
        client.post("/api/progression/N10/reset", json={"annee": "2025-2026"})
        prog = client.get("/api/progression/N10").get_json()
        cid = prog["creneaux"][0]["id"]

        r = client.patch(
            f"/api/progression/N10/creneau/{cid}",
            json={"date_debut": "2025-09-08", "periode": "Sem1"},
        )
        assert r.status_code == 200

        prog2 = client.get("/api/progression/N10").get_json()
        cr = next(c for c in prog2["creneaux"] if c["id"] == cid)
        assert cr["date_debut"] == "2025-09-08"
        assert cr["periode"] == "Sem1"

    def test_modifier_creneau_inconnu(self, client):
        client.post("/api/progression/N10/reset", json={"annee": "2025-2026"})
        r = client.patch("/api/progression/N10/creneau/INCONNU",
                         json={"periode": "Sem1"})
        assert r.status_code == 404

    def test_reordonner(self, client):
        client.post("/api/progression/N10/reset", json={"annee": "2025-2026"})
        prog = client.get("/api/progression/N10").get_json()
        ids = [c["id"] for c in prog["creneaux"]]
        # Inverser
        r = client.post("/api/progression/N10/reordonner",
                        json={"ordre": list(reversed(ids))})
        assert r.status_code == 200
        prog2 = client.get("/api/progression/N10").get_json()
        seqs = [c["sequence"] for c in prog2["creneaux"]]
        assert seqs == ["S03", "S02", "S01"]

    def test_liste_progressions(self, client):
        client.post("/api/progression/N10/reset", json={"annee": "2025-2026"})
        client.post("/api/progression/N10/reset", json={"annee": "2024-2025"})
        r = client.get("/api/progression/N10/liste")
        assert r.status_code == 200
        data = r.get_json()
        annees = [p["annee"] for p in data]
        assert "2024-2025" in annees
        assert "2025-2026" in annees

    def test_reset_sans_annee_400(self, client):
        r = client.post("/api/progression/N10/reset", json={})
        assert r.status_code == 400

    def test_importer_sequencesdb(self, client, sequencesdb_dir):
        r = client.post(
            "/api/progression/N11/importer-sequencesdb",
            json={
                "chemin": str(sequencesdb_dir),
                "annee":  "2023-2024",
            },
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["creneaux"] == 4  # S01×2 + S02 + S03

    def test_import_historique_refuse_doublon(self, client, classes_avec_eleves):
        """
        Une classe déjà présente avec (même nom, même établissement, même année)
        doit être rejetée avec 409, même si casse/espaces diffèrent.
        """
        # classes_avec_eleves pose : nom='5e1', niveau='N10', annee='2024-2025',
        # etab='Collège Test'. On tente de la réimporter avec des variations.
        r = client.post(
            "/api/import/historique",
            json={
                "chemin_classe":      "/tmp/inexistant",
                "chemin_sequencesdb": "/tmp/inexistant",
                "niveau":             "N10",
                "annee":              "2024-2025",
                "nom_classe":         "  5E1  ",        # casse + espaces
                "etablissement":      "COLLÈGE TEST",   # casse différente
            },
        )
        assert r.status_code == 409
        data = r.get_json()
        assert "existe déjà" in data["error"]
        assert "5E1" in data["error"]  # le nom tel que saisi est ressorti

    def test_import_historique_autorise_meme_nom_annee_differente(
        self, client, classes_avec_eleves
    ):
        """
        Même nom + même établissement mais année différente : non-doublon.
        On vérifie juste que la vérif anti-doublon ne rejette pas (réponse != 409).
        L'import lui-même peut échouer avec 500 (chemins bidon) : acceptable.
        """
        r = client.post(
            "/api/import/historique",
            json={
                "chemin_classe":      "/tmp/inexistant",
                "chemin_sequencesdb": "/tmp/inexistant",
                "niveau":             "N10",
                "annee":              "2025-2026",     # ≠ 2024-2025 de la fixture
                "nom_classe":         "5e1",
                "etablissement":      "Collège Test",
            },
        )
        assert r.status_code != 409


# ── Tests nouvelles routes : rangs-disponibles et creneau-ajouter ─────────────

class TestRangsDisponibles:
    """Tests de la route GET /api/progression/<niveau>/rangs-disponibles."""

    def _setup(self, client):
        """Crée une progression N10 avec un créneau S01 rang 1 déjà placé."""
        client.post("/api/progression/N10/reset", json={"annee": "2025-2026"})
        client.post("/api/progression/N10", json={
            "annee": "2025-2026", "etablissement": "Test",
        })
        # Ajouter S01 rang 1
        client.post("/api/progression/N10/creneau-ajouter", json={
            "annee": "2025-2026",
            "sequence": "S01", "partie_debut": 1, "partie_fin": 1,
            "date_debut": "2025-09-01", "date_fin": "2025-09-15",
        })

    def test_rangs_disponibles_premiere_sequence(self, client, yaml_n10_minimal):
        """Séquence sans aucun créneau → rang 1 disponible."""
        client.post("/api/progression/N10/reset", json={"annee": "2025-2026"})
        client.post("/api/progression/N10", json={"annee": "2025-2026"})
        r = client.get("/api/progression/N10/rangs-disponibles?seq=S01&annee=2025-2026")
        assert r.status_code == 200
        d = r.get_json()
        assert d["prochain_rang"] == 1
        assert 1 in d["rangs_disponibles"]
        assert d["rangs_places"] == []

    def test_rangs_disponibles_apres_rang1(self, client, yaml_n10_minimal):
        """Après rang 1 placé → rang 2 disponible (si la séquence a 2 rangs)."""
        self._setup(client)
        r = client.get("/api/progression/N10/rangs-disponibles?seq=S01&annee=2025-2026")
        assert r.status_code == 200
        d = r.get_json()
        assert 1 in d["rangs_places"]
        # Si S01 a objectifs 01-09 seulement → rangs_max=1 → pas de rang 2
        # Vérifier cohérence
        assert d["prochain_rang"] is None or d["prochain_rang"] >= 2

    def test_rangs_disponibles_seq_inconnue(self, client):
        """Séquence inexistante → progression introuvable ou rangs_max=1."""
        client.post("/api/progression/N10/reset", json={"annee": "2025-2026"})
        client.post("/api/progression/N10", json={"annee": "2025-2026"})
        r = client.get("/api/progression/N10/rangs-disponibles?seq=S99&annee=2025-2026")
        assert r.status_code in (200, 404)


class TestCreneauAjouter:
    """Tests de la route POST /api/progression/<niveau>/creneau-ajouter."""

    def _prog(self, client):
        client.post("/api/progression/N10/reset", json={"annee": "2025-2026"})
        client.post("/api/progression/N10", json={"annee": "2025-2026"})

    def test_ajouter_creneau_simple(self, client):
        self._prog(client)
        r = client.post("/api/progression/N10/creneau-ajouter", json={
            "annee": "2025-2026",
            "sequence": "S01", "partie_debut": 1, "partie_fin": 1,
            "date_debut": "2025-09-01", "date_fin": "2025-09-15",
            "periode": "Sem1",
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["creneau"]["sequence"] == "S01"
        assert d["creneau"]["partie_debut"] == 1

    def test_ajouter_creneau_multi_rangs(self, client):
        """Regrouper rang 1 et rang 2 dans un seul créneau."""
        self._prog(client)
        r = client.post("/api/progression/N10/creneau-ajouter", json={
            "annee": "2025-2026",
            "sequence": "S03", "partie_debut": 1, "partie_fin": 2,
            "date_debut": "2025-09-01", "date_fin": "2025-10-15",
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["creneau"]["partie_debut"] == 1
        assert d["creneau"]["partie_fin"] == 2

    def test_conflit_rang_deja_place(self, client):
        """Tenter d'ajouter un rang déjà placé → 409."""
        self._prog(client)
        client.post("/api/progression/N10/creneau-ajouter", json={
            "annee": "2025-2026",
            "sequence": "S01", "partie_debut": 1, "partie_fin": 1,
            "date_debut": "2025-09-01", "date_fin": "2025-09-15",
        })
        r = client.post("/api/progression/N10/creneau-ajouter", json={
            "annee": "2025-2026",
            "sequence": "S01", "partie_debut": 1, "partie_fin": 1,
            "date_debut": "2025-09-16", "date_fin": "2025-09-30",
        })
        assert r.status_code == 409

    def test_supprimer_creneau(self, client):
        """Ajouter puis supprimer un créneau."""
        self._prog(client)
        r = client.post("/api/progression/N10/creneau-ajouter", json={
            "annee": "2025-2026",
            "sequence": "S01", "partie_debut": 1, "partie_fin": 1,
            "date_debut": "2025-09-01", "date_fin": "2025-09-15",
        })
        cid = r.get_json()["creneau"]["id"]
        r2 = client.delete(f"/api/progression/N10/creneau/{cid}",
                           json={"annee": "2025-2026"})
        assert r2.status_code == 200
        # Vérifier que le créneau n'est plus là
        prog = client.get("/api/progression/N10?annee=2025-2026").get_json()
        ids = [c["id"] for c in prog.get("creneaux", [])]
        assert cid not in ids

    def test_supprimer_creneau_inexistant(self, client):
        """Supprimer un id inexistant → 404."""
        self._prog(client)
        r = client.delete("/api/progression/N10/creneau/inexistant",
                          json={"annee": "2025-2026"})
        assert r.status_code == 404
