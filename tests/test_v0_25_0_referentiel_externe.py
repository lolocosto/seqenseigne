"""tests/test_v0_25_0_referentiel_externe.py — v0.25.0

Référentiels externes : migration, CRUD référentiel/séquence/partie/doc,
validation, formats affichables.
"""
import sqlite3
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore
from services import referentiel_externe as rx


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def test_tables_creees(store, tmp_path):
    con = sqlite3.connect(tmp_path / "data" / "seqenseigne.db")
    noms = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name LIKE 'referentiel_externe%'")}
    assert {"referentiel_externe", "referentiel_externe_sequence",
            "referentiel_externe_partie", "referentiel_externe_doc"} <= noms


def test_structure_sequence_partie(store):
    with store._conn() as conn:
        ref = rx.creer(conn, niveau="N09", annee="2026-2027", nom="MER 6e")
        assert ref["etat"] == "en_cours"
        assert ref["type"] == "mer"
        seq = rx.ajouter_sequence(conn, ref["id"], code="MER1",
                                  nom="Calcul mental")
        p1 = rx.ajouter_partie(conn, seq["id"],
                               libelle="Tables de multiplication", nb_seances=6)
        p2 = rx.ajouter_partie(conn, seq["id"],
                               libelle="Compléments à 10", nb_seances=4)
        assert p1["numero"] == 1 and p1["nb_seances"] == 6
        assert p2["numero"] == 2 and p2["nb_seances"] == 4
        full = rx.lire(conn, ref["id"])
        assert len(full["sequences"]) == 1
        assert len(full["sequences"][0]["parties"]) == 2


def test_validation(store):
    with store._conn() as conn:
        ref = rx.creer(conn, niveau="N09")
        r = rx.changer_etat(conn, ref["id"], "valide")
        assert r["etat"] == "valide"
        with pytest.raises(rx.DonneesInvalides):
            rx.changer_etat(conn, ref["id"], "verrouille")  # état interdit


def test_doc_affichable_selon_mime(store, tmp_path):
    with store._conn() as conn:
        ref = rx.creer(conn, niveau="N09")
        seq = rx.ajouter_sequence(conn, ref["id"], code="S1")
        p = rx.ajouter_partie(conn, seq["id"], libelle="P1")
        pdf = rx.ajouter_doc(conn, p["id"], nom_fichier="fiche.pdf",
                             contenu=b"%PDF-1.4", mime="application/pdf",
                             data_dir=tmp_path / "data")
        odt = rx.ajouter_doc(conn, p["id"], nom_fichier="fiche.odt",
                             contenu=b"PK...", mime="application/vnd.oasis.opendocument.text",
                             data_dir=tmp_path / "data")
        assert pdf["affichable"] is True     # PDF → affichable en ligne
        assert odt["affichable"] is False    # ODT → téléchargement
        # fichier réellement écrit
        assert (tmp_path / "data" / pdf["chemin"]).exists()


def test_creer_niveau_obligatoire(store):
    with store._conn() as conn:
        with pytest.raises(rx.DonneesInvalides):
            rx.creer(conn, niveau="")
