"""
tests/test_import_arborescence.py — Tests du script d'import en lot.

Le principal écueil couvert ici : plusieurs classes avec le même nom sur
des années différentes (4e3 de 2023-2024, 4e3 de 2024-2025…) doivent
produire des identifiants distincts pour ne pas s'écraser mutuellement
en base.
"""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence.sqlite_store import SqliteStore


def _creer_sdb_minimal(dest: Path, niveau: str = "N11"):
    """Crée une arborescence Suivi_eleves/ + SequencesDB/ minimale."""
    dest.mkdir(parents=True, exist_ok=True)
    suivi = dest / "Suivi_eleves"
    sdb   = dest / "SequencesDB"
    suivi.mkdir()
    sdb.mkdir()

    # Liste d'élèves
    (suivi / "liste_eleves.csv").write_text(
        "Nom,Prenom\nDUPONT,Alice\nMARTIN,Bob\n", encoding="utf-8",
    )
    # Periodes.CSV
    (suivi / "Periodes.CSV").write_text(
        "Periode\nSem1\n", encoding="utf-8",
    )
    # cycle4-themes + cycle4-sequences
    (sdb / "cycle4-themes.csv").write_text(
        "Code,Nom,CodeCouleur\nA,Nombres et Calculs,nombres\n",
        encoding="utf-8",
    )
    (sdb / "cycle4-sequences.csv").write_text(
        "Code,Numero,Nom,Theme\nS01,01,Fractions,A\n",
        encoding="utf-8",
    )
    # Sem1-sequences.csv
    (sdb / "Sem1-sequences.csv").write_text(
        "Code,Numero,Nom,Theme\nS01,01,Fractions,A\n",
        encoding="utf-8",
    )
    # N11S01Objectifs.csv
    (sdb / f"{niveau}S01Objectifs.csv").write_text(
        "Code,FinCycle,Nom,MaitriseTB,MaitriseS,MaitriseF\n"
        "01,O,Cours,tb,s,f\n",
        encoding="utf-8",
    )


def _creer_arbo_test(racine: Path, classes: list[tuple]):
    """
    classes : liste de (annee, nom_classe, niveau)
    Crée racine/<annee>/<etab>/<classe>/Suivi_eleves + SequencesDB.
    """
    etab = "Collège Test"
    for annee, nom, niveau in classes:
        _creer_sdb_minimal(racine / annee / etab / nom, niveau=niveau)


class TestImportArborescenceMultiAnnees:

    def test_meme_nom_classe_annees_differentes(self, tmp_path):
        """
        Le bug historique : plusieurs '4e3' à travers les années se retrouvaient
        avec le même id à cause d'une logique anti-collision simpliste (un seul
        suffixe _hist réutilisé). Résultat : les classes s'écrasaient.
        """
        racine = tmp_path / "arbo"
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "C04_sequences.csv").write_text(
            "Code,Numero,Nom,Theme\nS01,1,Fractions,A\n", encoding="utf-8",
        )
        (data_dir / "C04_themes.csv").write_text(
            "Code,Nom,CodeCouleur\nA,Nombres et Calculs,nombres\n",
            encoding="utf-8",
        )

        # 3 classes avec le MÊME nom à 3 années différentes (le scénario
        # problématique observé : 4e3 de 2023, 2024 et 2025).
        _creer_arbo_test(racine, [
            ("2023-2024", "4e3", "N11"),
            ("2024-2025", "4e3", "N11"),
            ("2025-2026", "4e3", "N11"),
        ])

        # Lancer l'import (en appel direct, pas via subprocess)
        from importer_arborescence import scanner_arborescence, importer_toutes
        store = SqliteStore(data_dir)
        classes_scan = scanner_arborescence(racine)
        rapport = importer_toutes(classes_scan, store)

        # Vérification : les 3 classes doivent être importées et persistées
        assert len(rapport["importees"]) == 3
        assert len(rapport["echecs"]) == 0

        classes_en_base = store.lire_classes()["classes"]
        assert len(classes_en_base) == 3, (
            f"Attendu 3 classes distinctes, trouvé {len(classes_en_base)} : "
            f"{[c['id'] for c in classes_en_base]}"
        )

        # Chaque classe doit garder ses propres élèves (pas de fusion)
        for c in classes_en_base:
            assert len(c["eleves"]) == 2, (
                f"Classe {c['id']} ({c['annee']}) : {len(c['eleves'])} élèves "
                f"au lieu de 2 — écrasement partiel détecté"
            )

        # Les ids doivent inclure l'année pour être lisibles et uniques
        ids = {c["id"] for c in classes_en_base}
        annees_couvertes = {c["annee"] for c in classes_en_base}
        assert annees_couvertes == {"2023-2024", "2024-2025", "2025-2026"}
        # Format attendu : 4E3_2023-2024, 4E3_2024-2025, 4E3_2025-2026
        for cid in ids:
            assert "_" in cid, f"L'id {cid} ne contient pas l'année"

    def test_classes_differentes_meme_annee(self, tmp_path):
        """
        Classes de noms différents la même année → chaque id est unique,
        pas de problème de collision (cas nominal).
        """
        racine = tmp_path / "arbo"
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "C04_sequences.csv").write_text(
            "Code,Numero,Nom,Theme\nS01,1,Fractions,A\n", encoding="utf-8",
        )
        (data_dir / "C04_themes.csv").write_text(
            "Code,Nom,CodeCouleur\nA,Nombres et Calculs,nombres\n",
            encoding="utf-8",
        )

        _creer_arbo_test(racine, [
            ("2024-2025", "4e3", "N11"),
            ("2024-2025", "4e8", "N11"),
            ("2024-2025", "5e1", "N10"),
        ])

        from importer_arborescence import scanner_arborescence, importer_toutes
        store = SqliteStore(data_dir)
        classes_scan = scanner_arborescence(racine)
        rapport = importer_toutes(classes_scan, store)

        assert len(rapport["importees"]) == 3
        classes_en_base = store.lire_classes()["classes"]
        assert len(classes_en_base) == 3
        # Chaque classe a bien ses 2 élèves
        for c in classes_en_base:
            assert len(c["eleves"]) == 2

    def test_meme_nom_meme_annee_est_detecte_comme_doublon(self, tmp_path):
        """
        Si on lance 2 fois l'import avec la même arborescence, la 2ème
        détection doit signaler un doublon (cle nom+annee+etab existe).
        Sans flag --force, la classe existante est ignorée.
        """
        racine = tmp_path / "arbo"
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "C04_sequences.csv").write_text(
            "Code,Numero,Nom,Theme\nS01,1,Fractions,A\n", encoding="utf-8",
        )
        (data_dir / "C04_themes.csv").write_text(
            "Code,Nom,CodeCouleur\nA,Nombres et Calculs,nombres\n",
            encoding="utf-8",
        )

        _creer_arbo_test(racine, [("2024-2025", "4e3", "N11")])

        from importer_arborescence import scanner_arborescence, importer_toutes
        store = SqliteStore(data_dir)
        classes_scan = scanner_arborescence(racine)

        # 1er import : OK
        rapport1 = importer_toutes(classes_scan, store)
        assert len(rapport1["importees"]) == 1

        # 2ème import sans --force : la classe doit être ignorée (doublon)
        rapport2 = importer_toutes(classes_scan, store, force=False)
        assert len(rapport2["ignorees_doublons"]) == 1
        assert len(rapport2["importees"]) == 0

        # Base inchangée
        classes = store.lire_classes()["classes"]
        assert len(classes) == 1

    def test_meme_nom_meme_annee_etablissements_differents(self, tmp_path):
        """
        Cas métier : une 4e1 dans le collège A et une 4e1 dans le collège B,
        même année scolaire. Les deux doivent coexister avec des ids distincts.
        """
        racine = tmp_path / "arbo"
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "C04_sequences.csv").write_text(
            "Code,Numero,Nom,Theme\nS01,1,Fractions,A\n", encoding="utf-8",
        )
        (data_dir / "C04_themes.csv").write_text(
            "Code,Nom,CodeCouleur\nA,Nombres et Calculs,nombres\n",
            encoding="utf-8",
        )

        # Construire manuellement l'arbo avec 2 établissements
        for etab in ("Collège Les Hautes Ourmes", "Collège Jean Moulin"):
            _creer_sdb_minimal(
                racine / "2024-2025" / etab / "4e1", niveau="N11",
            )

        from importer_arborescence import scanner_arborescence, importer_toutes
        store = SqliteStore(data_dir)
        classes_scan = scanner_arborescence(racine)
        rapport = importer_toutes(classes_scan, store)

        assert len(rapport["importees"]) == 2
        classes_en_base = store.lire_classes()["classes"]
        assert len(classes_en_base) == 2, (
            f"Attendu 2 classes (une par établissement), "
            f"trouvé {len(classes_en_base)} : {[c['id'] for c in classes_en_base]}"
        )

        # Les ids doivent être distincts et refléter l'établissement
        ids = [c["id"] for c in classes_en_base]
        assert len(set(ids)) == 2, f"ids collisionnés : {ids}"
        # Les deux classes gardent leur propre contenu
        for c in classes_en_base:
            assert len(c["eleves"]) == 2

    def test_progression_id_synchronise_entre_classes_memes_cle_metier(self, tmp_path):
        """
        Bug v0.6.2 : plusieurs classes pour (niveau, annee, etablissement) identique
        partageant la même progression. La 1ère classe écrit la progression avec un
        id pg_X ; la 2e génère un pg_Y qui collisionne au niveau UNIQUE SQL, et
        `ecrire_progression` (upsert par clé métier) réutilise pg_X. Mais
        classe.progression_id restait figé à pg_Y → NULL en base.

        Après le fix : toutes les classes du groupe doivent avoir
        progression_id == l'id de la progression réellement créée.
        """
        racine = tmp_path / "arbo"
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "C04_sequences.csv").write_text(
            "Code,Numero,Nom,Theme\nS01,1,Fractions,A\n", encoding="utf-8",
        )
        (data_dir / "C04_themes.csv").write_text(
            "Code,Nom,CodeCouleur\nA,Nombres et Calculs,nombres\n",
            encoding="utf-8",
        )
        # 3 classes de N11 2024-2025, même établissement → partagent la progression
        _creer_arbo_test(racine, [
            ("2024-2025", "4e3", "N11"),
            ("2024-2025", "4e4", "N11"),
            ("2024-2025", "4e8", "N11"),
        ])

        from importer_arborescence import scanner_arborescence, importer_toutes
        store = SqliteStore(data_dir)
        rapport = importer_toutes(scanner_arborescence(racine), store)
        assert len(rapport["importees"]) == 3

        # Toutes les classes doivent avoir progression_id non NULL et identique
        import sqlite3
        conn = sqlite3.connect(data_dir / "seqenseigne.db")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT nom, progression_id FROM classes ORDER BY nom").fetchall()
        prog_ids = {r["progression_id"] for r in rows}

        assert None not in prog_ids, (
            f"Au moins une classe a progression_id=NULL : "
            f"{[(r['nom'], r['progression_id']) for r in rows]}"
        )
        assert len(prog_ids) == 1, (
            f"Toutes les classes devraient pointer sur la même progression, "
            f"trouvé {len(prog_ids)} progressions distinctes : {prog_ids}"
        )
