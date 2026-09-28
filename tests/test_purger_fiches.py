"""tests/test_purger_fiches.py — v0.11.1.x

Couvre le script scripts/purger_fiches.py :
  - Dry-run : compte mais ne supprime rien.
  - Apply : supprime fiches + sections + items + liaisons.
  - Filtres : --niveau, --sequence, et leur combinaison.
  - Sécurités : confirmation requise sans --yes, code retour 1 si refus,
    code retour 2 si BDD absente.
  - Cascade : sections orphelines bien nettoyées (pas de FK fiches→sections),
    items partent via FK section→items, liaisons via FK fiches→liaisons.
"""

from __future__ import annotations
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


# ── Fixture : BDD peuplée avec différents niveaux/séquences ────────────────────

@pytest.fixture
def db_avec_fiches(tmp_path: Path) -> Path:
    """Crée une BDD SQLite peuplée avec :
      - 2 fiches en N10/S01 (fi_a, fi_b)
      - 1 fiche en N10/S02 (fi_c)
      - 1 fiche en N11/S07 (fi_d)
    Chaque fiche a 1 ou 2 sections, chaque section 1 ou 2 items.
    Liaisons obj_fiches : 2 sur fi_a (multi-objectifs), 1 sur fi_d.
    """
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    # FK actives pour la fixture comme pour le script
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE fiches_resume (
            id           TEXT PRIMARY KEY,
            titre        TEXT NOT NULL DEFAULT '',
            objectif_id  TEXT,
            num_fiche    INTEGER,
            niveau       TEXT NOT NULL DEFAULT '',
            sequence     TEXT NOT NULL DEFAULT '',
            fichier      TEXT NOT NULL DEFAULT '',
            etat_code    TEXT NOT NULL DEFAULT 'en_cours'
        );
        CREATE TABLE atome_sections (
            id           TEXT PRIMARY KEY,
            entite_type  TEXT NOT NULL,
            entite_id    TEXT NOT NULL,
            titre        TEXT NOT NULL,
            ordre        INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE atome_section_items (
            id           TEXT PRIMARY KEY,
            section_id   TEXT NOT NULL REFERENCES atome_sections(id) ON DELETE CASCADE,
            ordre        INTEGER NOT NULL DEFAULT 0,
            corps        TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE objectif_fiches (
            objectif_id  TEXT NOT NULL,
            fiche_id     TEXT NOT NULL REFERENCES fiches_resume(id) ON DELETE CASCADE,
            ordre        INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (objectif_id, fiche_id)
        );

        -- 2 fiches en N10/S01
        INSERT INTO fiches_resume (id, niveau, sequence, titre)
            VALUES ('fi_a', 'N10', 'S01', 'Fiche A');
        INSERT INTO fiches_resume (id, niveau, sequence, titre)
            VALUES ('fi_b', 'N10', 'S01', 'Fiche B');
        -- 1 fiche en N10/S02
        INSERT INTO fiches_resume (id, niveau, sequence, titre)
            VALUES ('fi_c', 'N10', 'S02', 'Fiche C');
        -- 1 fiche en N11/S07
        INSERT INTO fiches_resume (id, niveau, sequence, titre)
            VALUES ('fi_d', 'N11', 'S07', 'Fiche D');

        -- Sections : fi_a a 2 sections, les autres 1
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_a1', 'fiche_resume', 'fi_a', 'Définition', 0);
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_a2', 'fiche_resume', 'fi_a', 'Propriété', 1);
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_b1', 'fiche_resume', 'fi_b', 'Définition', 0);
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_c1', 'fiche_resume', 'fi_c', 'Définition', 0);
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_d1', 'fiche_resume', 'fi_d', 'Définition', 0);

        -- Items : fi_a / sec_a1 a 2 items, le reste 1
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_a1_0', 'sec_a1', 0, 'Item 1 sec a1');
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_a1_1', 'sec_a1', 1, 'Item 2 sec a1');
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_a2_0', 'sec_a2', 0, 'Item 1 sec a2');
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_b1_0', 'sec_b1', 0, 'Item 1 sec b1');
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_c1_0', 'sec_c1', 0, 'Item 1 sec c1');
        INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_d1_0', 'sec_d1', 0, 'Item 1 sec d1');

        -- Liaisons : fi_a a 2 obj liés, fi_d en a 1, fi_b et fi_c aucun
        INSERT INTO objectif_fiches (objectif_id, fiche_id, ordre)
            VALUES ('obj_x', 'fi_a', 0);
        INSERT INTO objectif_fiches (objectif_id, fiche_id, ordre)
            VALUES ('obj_y', 'fi_a', 1);
        INSERT INTO objectif_fiches (objectif_id, fiche_id, ordre)
            VALUES ('obj_z', 'fi_d', 0);
    """)
    conn.commit()
    conn.close()
    return db


def _compter(db: Path) -> dict:
    """Helper : retourne les comptes globaux (pas de filtre).

    Permet aux tests de vérifier l'effet d'une exécution du script.
    """
    conn = sqlite3.connect(db)
    out = {
        "fiches":   conn.execute("SELECT COUNT(*) FROM fiches_resume").fetchone()[0],
        "sections": conn.execute(
            "SELECT COUNT(*) FROM atome_sections WHERE entite_type='fiche_resume'"
        ).fetchone()[0],
        "items":    conn.execute(
            """SELECT COUNT(*) FROM atome_section_items
               WHERE section_id IN (
                   SELECT id FROM atome_sections WHERE entite_type='fiche_resume'
               )"""
        ).fetchone()[0],
        "liaisons": conn.execute("SELECT COUNT(*) FROM objectif_fiches").fetchone()[0],
    }
    conn.close()
    return out


def _executer_script(db: Path, *args, input_stdin: str | None = None):
    """Lance le script en subprocess et retourne le CompletedProcess.

    Cohérent avec les tests v0.10.7 (test_v0_10_7_badges_et_orphelins.py) :
    invocation par chemin direct au lieu de `python -m scripts.xxx` pour
    éviter le problème des distributions Python embeddable Windows.
    """
    racine = Path(__file__).resolve().parent.parent
    chemin_script = str(racine / "scripts" / "purger_fiches.py")
    cmd = [sys.executable, chemin_script, "--db", str(db), *args]
    return subprocess.run(
        cmd, cwd=str(racine), capture_output=True, text=True,
        input=input_stdin,
    )


# ── Tests : sanity / dry-run ──────────────────────────────────────────────────

class TestDryRun:
    """Sans --apply, le script doit compter mais ne rien modifier."""

    def test_dry_run_sans_filtre(self, db_avec_fiches):
        avant = _compter(db_avec_fiches)
        assert avant == {"fiches": 4, "sections": 5, "items": 6, "liaisons": 3}

        r = _executer_script(db_avec_fiches)
        assert r.returncode == 0, f"stderr: {r.stderr}"
        assert "DRY-RUN" in r.stdout
        # 4 fiches au total, 5 sections, 6 items, 3 liaisons
        assert "Fiches              :      4" in r.stdout
        assert "Sections            :      5" in r.stdout
        assert "Items de section    :      6" in r.stdout
        assert "Liaisons obj_fiches :      3" in r.stdout

        # Rien n'a bougé
        assert _compter(db_avec_fiches) == avant

    def test_dry_run_avec_filtre_niveau(self, db_avec_fiches):
        r = _executer_script(db_avec_fiches, "--niveau", "N10")
        assert r.returncode == 0
        # 3 fiches en N10 (fi_a, fi_b, fi_c)
        assert "Fiches              :      3" in r.stdout
        # Sections N10 : sec_a1, sec_a2, sec_b1, sec_c1 = 4
        assert "Sections            :      4" in r.stdout
        # Items N10 : 2+1+1+1 = 5
        assert "Items de section    :      5" in r.stdout
        # Liaisons N10 : fi_a en a 2, fi_b et fi_c 0 → 2
        assert "Liaisons obj_fiches :      2" in r.stdout

    def test_dry_run_avec_filtre_combine(self, db_avec_fiches):
        r = _executer_script(db_avec_fiches, "--niveau", "N10",
                             "--sequence", "S01")
        assert r.returncode == 0
        # 2 fiches en N10/S01 (fi_a, fi_b)
        assert "Fiches              :      2" in r.stdout
        # 3 sections (sec_a1, sec_a2, sec_b1)
        assert "Sections            :      3" in r.stdout
        # Items : 2+1+1 = 4
        assert "Items de section    :      4" in r.stdout
        # Liaisons : 2 (toutes sur fi_a)
        assert "Liaisons obj_fiches :      2" in r.stdout

    def test_dry_run_filtre_sans_match(self, db_avec_fiches):
        r = _executer_script(db_avec_fiches, "--niveau", "N12")
        assert r.returncode == 0
        # Aucune fiche en N12
        assert "Fiches              :      0" in r.stdout

    def test_dry_run_message_indicatif(self, db_avec_fiches):
        # Le message rappelle qu'il faut --apply pour exécuter
        r = _executer_script(db_avec_fiches, "--niveau", "N10")
        assert "--apply" in r.stdout


# ── Tests : apply réel ────────────────────────────────────────────────────────

class TestApply:
    """Avec --apply --yes (batch sans confirmation), la purge s'exécute."""

    def test_apply_sans_filtre(self, db_avec_fiches):
        r = _executer_script(db_avec_fiches, "--apply", "--yes")
        assert r.returncode == 0, f"stderr: {r.stderr}"
        assert "APPLIQUÉ" in r.stdout
        # Tout est parti (aussi les liaisons via cascade FK)
        assert _compter(db_avec_fiches) == {
            "fiches": 0, "sections": 0, "items": 0, "liaisons": 0,
        }

    def test_apply_filtre_niveau(self, db_avec_fiches):
        r = _executer_script(db_avec_fiches, "--niveau", "N10",
                             "--apply", "--yes")
        assert r.returncode == 0
        # N10 parti (3 fiches, 4 sections, 5 items, 2 liaisons),
        # N11 préservé (1 fiche, 1 section, 1 item, 1 liaison)
        assert _compter(db_avec_fiches) == {
            "fiches": 1, "sections": 1, "items": 1, "liaisons": 1,
        }
        # Confirmer que c'est bien fi_d qui reste
        conn = sqlite3.connect(db_avec_fiches)
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM fiches_resume").fetchall()]
        conn.close()
        assert ids == ["fi_d"]

    def test_apply_filtre_combine(self, db_avec_fiches):
        r = _executer_script(db_avec_fiches, "--niveau", "N10",
                             "--sequence", "S01", "--apply", "--yes")
        assert r.returncode == 0
        # N10/S01 parti (fi_a + fi_b et leurs sections + 2 liaisons)
        # → reste fi_c (N10/S02), fi_d (N11/S07)
        assert _compter(db_avec_fiches) == {
            "fiches": 2, "sections": 2, "items": 2, "liaisons": 1,
        }
        # Liaison restante = obj_z↔fi_d (obj_x et obj_y partis avec fi_a)
        conn = sqlite3.connect(db_avec_fiches)
        liaisons = conn.execute(
            "SELECT objectif_id, fiche_id FROM objectif_fiches"
        ).fetchall()
        conn.close()
        assert set(liaisons) == {("obj_z", "fi_d")}

    def test_apply_filtre_sans_match(self, db_avec_fiches):
        # Filtre sans fiche : OK, pas de confirmation à demander
        avant = _compter(db_avec_fiches)
        r = _executer_script(db_avec_fiches, "--niveau", "N12",
                             "--apply", "--yes")
        assert r.returncode == 0
        assert "Rien à supprimer" in r.stdout
        assert _compter(db_avec_fiches) == avant


# ── Tests : sécurités (confirmation, BDD absente, etc.) ───────────────────────

class TestSecurites:

    def test_apply_sans_yes_demande_confirmation_OUI(self, db_avec_fiches):
        # Confirmation positive ('OUI') → exécution
        r = _executer_script(db_avec_fiches, "--niveau", "N10",
                             "--apply", input_stdin="OUI\n")
        assert r.returncode == 0, f"stderr: {r.stderr}"
        # N10 parti
        assert _compter(db_avec_fiches)["fiches"] == 1

    def test_apply_sans_yes_refus_oui_minuscule(self, db_avec_fiches):
        # 'oui' en minuscules ne suffit PAS — exigence stricte
        avant = _compter(db_avec_fiches)
        r = _executer_script(db_avec_fiches, "--niveau", "N10",
                             "--apply", input_stdin="oui\n")
        assert r.returncode == 1
        assert "Annulé" in r.stderr
        # Rien n'a bougé
        assert _compter(db_avec_fiches) == avant

    def test_apply_sans_yes_refus_explicite(self, db_avec_fiches):
        avant = _compter(db_avec_fiches)
        r = _executer_script(db_avec_fiches, "--apply", input_stdin="non\n")
        assert r.returncode == 1
        assert _compter(db_avec_fiches) == avant

    def test_apply_sans_yes_refus_eof(self, db_avec_fiches):
        # Stdin fermé immédiatement (EOF) → annulation propre
        avant = _compter(db_avec_fiches)
        r = _executer_script(db_avec_fiches, "--apply", input_stdin="")
        assert r.returncode == 1
        assert _compter(db_avec_fiches) == avant

    def test_db_introuvable(self, tmp_path):
        # BDD inexistante → code 2 et message d'erreur
        r = _executer_script(tmp_path / "nexiste.db", "--apply", "--yes")
        assert r.returncode == 2
        assert "introuvable" in r.stderr


# ── Tests : effets de cascade ─────────────────────────────────────────────────

class TestCascades:
    """Le script doit nettoyer correctement par cascade FK + suppression
    explicite des sections (qui n'ont pas de FK vers fiches_resume).
    """

    def test_items_partent_avec_les_sections(self, db_avec_fiches):
        # Cascade FK : section_id ON DELETE CASCADE → atome_section_items
        # Le script supprime explicitement les sections, les items partent
        # automatiquement.
        r = _executer_script(db_avec_fiches, "--niveau", "N10", "--sequence",
                             "S01", "--apply", "--yes")
        assert r.returncode == 0
        # Vérif directe : aucun item résiduel pointant vers une section
        # supprimée (sec_a1, sec_a2, sec_b1)
        conn = sqlite3.connect(db_avec_fiches)
        n_orph = conn.execute("""
            SELECT COUNT(*) FROM atome_section_items
            WHERE section_id IN ('sec_a1', 'sec_a2', 'sec_b1')
        """).fetchone()[0]
        conn.close()
        assert n_orph == 0

    def test_liaisons_partent_avec_les_fiches(self, db_avec_fiches):
        # Cascade FK : objectif_fiches.fiche_id ON DELETE CASCADE → fiches_resume
        r = _executer_script(db_avec_fiches, "--niveau", "N10", "--sequence",
                             "S01", "--apply", "--yes")
        assert r.returncode == 0
        # fi_a et fi_b ont 2+0 = 2 liaisons → toutes parties
        conn = sqlite3.connect(db_avec_fiches)
        n_orph = conn.execute("""
            SELECT COUNT(*) FROM objectif_fiches
            WHERE fiche_id IN ('fi_a', 'fi_b')
        """).fetchone()[0]
        conn.close()
        assert n_orph == 0

    def test_sections_dautres_atomes_preservees(self, db_avec_fiches):
        # Le filtre entite_type='fiche_resume' protège les sections
        # d'autres atomes (notion, methode) si elles existent.
        # On en ajoute pour le test :
        conn = sqlite3.connect(db_avec_fiches)
        conn.execute("""
            INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_no_x', 'notion', 'no_x', 'Définition notion', 0)
        """)
        conn.commit()
        conn.close()

        r = _executer_script(db_avec_fiches, "--apply", "--yes")
        assert r.returncode == 0
        # La section notion doit être préservée
        conn = sqlite3.connect(db_avec_fiches)
        n_notion = conn.execute(
            "SELECT COUNT(*) FROM atome_sections WHERE entite_type='notion'"
        ).fetchone()[0]
        conn.close()
        assert n_notion == 1
