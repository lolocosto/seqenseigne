"""
tests/test_ecrire_exercices_fk.py — Non-régression du crash FK du
23 avril 2026.

Symptôme côté Laurent :
  POST /api/scanner/lancer → 500
  sqlite3.IntegrityError: FOREIGN KEY constraint failed
  File ".../sqlite_store.py", line 1088, in ecrire_exercices
    conn.execute("DELETE FROM exercices")

Cause :
  Après nettoyage_6, `scanner_vers_bdd` appelle `peupler_v2_depuis_base`
  à la fin de chaque scan, ce qui peuple `objectif_exos` (FK RESTRICT
  vers exercices). Au scan suivant, `ecrire_exercices` faisait un
  `DELETE FROM exercices` brutal sans vider `objectif_exos` d'abord
  → la FK RESTRICT bloque.

  Aggravation : les 3 scans (N10, N11, N12) étaient lancés en parallèle
  côté UI via `Promise.all`. Les écritures concurrentes mettaient la
  cohérence en vrac.

Correctifs :
  - `ecrire_exercices` est maintenant diff-based (INSERT/UPDATE/DELETE
    ciblés au lieu de DELETE+INSERT complet). Les liaisons
    `objectif_exos` des exos inchangés sont préservées, seules les
    liaisons des exos vraiment supprimés sont nettoyées en amont.
  - `static/app.js` sérialise les 3 scans (boucle `for ... of` au lieu
    de `Promise.all`).

Ce test couvre les deux propriétés :
  1. Pas d'IntegrityError FK quand `objectif_exos` a été peuplé
     avant un appel à `ecrire_exercices`.
  2. Les liaisons `objectif_exos` d'un niveau ne sont pas invalidées
     par un scan d'un autre niveau.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        yield SqliteStore(Path(tmp))


def _exo(id_, niveau, seq, num):
    return {
        "id": id_, "serie": "fondamental", "titre": f"Exo {id_}",
        "variables": "", "enonce": "E", "corrige": "C",
        "niveau": niveau, "sequence": seq, "num": num,
        "serie_code": "F", "fichier": f"{niveau}{seq}F{num:02d}.tex",
    }


def _creer_v2_et_liaison(conn, niveau, seq, exo_id, obj_code="02"):
    """
    Peuple suffisamment la v2 pour créer une ligne `objectif_exos`
    qui référence `exo_id`. Simule ce que fait peupler_v2_depuis_base
    à la fin d'un scan (avant v0.14.6.b.2).

    v0.14.6.b.2 — Step 1 (INSERT dans `objectifs` v1) retirée : la
    table v1 a été supprimée. La pile v2 suffit pour produire des
    liaisons `objectif_exos`.
    """
    obj_id = f"obj_{niveau}_{seq}_{obj_code}"
    # 1. Chaîne v2 : sequence_par_niveau → partie → objectif_v2
    sn_id = f"sn_{niveau}_{seq}"
    pt_id = f"pt_{niveau}_{seq}_1"
    conn.execute(
        "INSERT OR IGNORE INTO sequences_par_niveau "
        "(id, niveau, sequence_code, parametres) VALUES (?,?,?,?)",
        (sn_id, niveau, seq, "")
    )
    conn.execute(
        "INSERT OR IGNORE INTO sequence_parties "
        "(id, sequence_par_niveau_id, numero) VALUES (?,?,?)",
        (pt_id, sn_id, 1)
    )
    conn.execute(
        "INSERT OR IGNORE INTO objectifs "
        "(id, partie_id, code, nom, methode_id, critere_F, critere_A, critere_E) "
        "VALUES (?,?,?,?,NULL,'','','')",
        (obj_id, pt_id, obj_code, "nom")
    )
    # 2. La liaison qui nous intéresse (PK = objectif_id+serie+exercice_id)
    conn.execute(
        "INSERT INTO objectif_exos "
        "(objectif_id, serie, exercice_id, ordre) VALUES (?, 'F', ?, 1)",
        (obj_id, exo_id)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Bug principal : FK RESTRICT objectif_exos → exercices
# ─────────────────────────────────────────────────────────────────────────────

class TestEcrireExercicesNeCassePasFkRestrict:
    """
    Quand `objectif_exos` a des lignes qui référencent des exos déjà
    en base, un nouvel appel à `ecrire_exercices` (avec les mêmes exos
    ou de nouveaux) ne doit PAS provoquer d'IntegrityError FK.
    """

    def test_preserve_exo_existant_avec_liaison_v2(self, store):
        # 1er import : on pose un exo N10/S01/F01
        exo1 = _exo("exo_abc", "N10", "S01", 1)
        store.ecrire_exercices([exo1])

        # Simuler peupler_v2_depuis_base : pose une liaison objectif_exos
        with store._conn() as conn:
            _creer_v2_et_liaison(conn, "N10", "S01", "exo_abc")

        # 2e import : mêmes exos (même IDs via dédup par fichier)
        # → ne doit PAS lever et doit conserver la liaison
        store.ecrire_exercices([exo1])

        with store._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM objectif_exos "
                "WHERE exercice_id=?", ("exo_abc",)
            ).fetchone()[0]
            assert count == 1, (
                "La liaison objectif_exos doit être préservée pour un "
                "exo inchangé"
            )

    def test_scan_autre_niveau_preserve_liaisons_existantes(self, store):
        """
        Scénario Laurent du 23 avril 2026 : scan N10, puis scan N11,
        puis scan N12 (séquentiels après correctif UI). Les liaisons
        posées au scan N10 ne doivent pas disparaître au scan N11 ni
        au scan N12.
        """
        # Simule scan N10
        exo_n10 = _exo("exo_n10", "N10", "S01", 1)
        store.ecrire_exercices([exo_n10])
        with store._conn() as conn:
            _creer_v2_et_liaison(conn, "N10", "S01", "exo_n10")

        # Simule scan N11 : on passe la liste combinée N10+N11 (comme
        # le fait scanner_vers_bdd qui lit lire_exercices() avant d'ajouter)
        exo_n11 = _exo("exo_n11", "N11", "S02", 1)
        store.ecrire_exercices([exo_n10, exo_n11])
        with store._conn() as conn:
            _creer_v2_et_liaison(conn, "N11", "S02", "exo_n11")

        # Simule scan N12
        exo_n12 = _exo("exo_n12", "N12", "S03", 1)
        store.ecrire_exercices([exo_n10, exo_n11, exo_n12])

        with store._conn() as conn:
            # Les 3 liaisons doivent toutes survivre
            liaisons = {r["exercice_id"] for r in conn.execute(
                "SELECT exercice_id FROM objectif_exos"
            ).fetchall()}
            assert liaisons == {"exo_n10", "exo_n11"}, (
                f"Les liaisons objectif_exos des niveaux précédemment "
                f"scannés doivent survivre aux scans ultérieurs, "
                f"trouvé {liaisons}"
            )

    def test_suppression_exo_nettoie_sa_liaison(self, store):
        """
        Si un exo est supprimé (sort de la liste), sa liaison
        objectif_exos doit être nettoyée — sinon RESTRICT bloquerait
        le DELETE.
        """
        exo1 = _exo("exo_a", "N10", "S01", 1)
        exo2 = _exo("exo_b", "N10", "S01", 2)
        store.ecrire_exercices([exo1, exo2])
        with store._conn() as conn:
            _creer_v2_et_liaison(conn, "N10", "S01", "exo_a")
            _creer_v2_et_liaison(conn, "N10", "S01", "exo_b", obj_code="03")

        # Nouveau scan : exo_b disparaît
        store.ecrire_exercices([exo1])

        with store._conn() as conn:
            liaisons = [r["exercice_id"] for r in conn.execute(
                "SELECT exercice_id FROM objectif_exos"
            ).fetchall()]
            assert liaisons == ["exo_a"], (
                f"La liaison de exo_b devrait avoir été supprimée, "
                f"trouvé {liaisons}"
            )


class TestEcrireExercicesComportementGeneral:
    """Non-régression des propriétés essentielles de ecrire_exercices."""

    def test_insert_nouvel_exo(self, store):
        store.ecrire_exercices([_exo("e1", "N10", "S01", 1)])
        exos = store.lire_exercices()
        assert len(exos) == 1
        assert exos[0]["id"] == "e1"
        assert exos[0]["niveau"] == "N10"

    def test_update_exo_existant(self, store):
        store.ecrire_exercices([_exo("e1", "N10", "S01", 1)])
        modif = _exo("e1", "N10", "S01", 1)
        modif["titre"] = "Nom modifié"
        store.ecrire_exercices([modif])
        exos = store.lire_exercices()
        assert len(exos) == 1
        assert exos[0]["titre"] == "Nom modifié"

    def test_liste_vide_supprime_tout(self, store):
        store.ecrire_exercices([_exo("e1", "N10", "S01", 1)])
        assert len(store.lire_exercices()) == 1
        store.ecrire_exercices([])
        assert len(store.lire_exercices()) == 0

    # v0.14.6.b.2 — test_liaisons_exercice_objectifs_via_codes supprimé :
    # les tables `objectifs` et `exercice_objectifs` (v1) n'existent plus.
