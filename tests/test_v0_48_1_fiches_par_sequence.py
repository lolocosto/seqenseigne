"""tests/test_v0_48_1_fiches_par_sequence.py — v0.48.1

Livret de fiches de résumé découpé par séquence : option `decoupage_fiches`
(annuel / par séquence / les deux), cibles de compilation, génération filtrée
sur une séquence (en-tête de séquence, pas de table des matières), exposition
dans les documents associables de la progression.
"""
import json
import uuid
from types import SimpleNamespace

import pytest

from services import livret_fiches as lf
from services import referentiel_documents as rd
from services.referentiel_documents_compilation import lister_cibles_document
from tests.test_v0_13_6_5_2_livrets_manquants import (   # noqa: F401
    store_avec_paquet, _conn, _setup_minimal_niveau)


def _deux_sequences_avec_fiches(conn, niveau="N10"):
    _setup_minimal_niveau(conn, niveau)                      # S01, thème TH99
    from services.param_niveaux import lire_cycle
    cycle = lire_cycle(conn, niveau)
    theme_id = conn.execute("SELECT theme_id FROM sequences_du_cycle WHERE code='S01' "
                            "AND cycle_code=?", (cycle,)).fetchone()[0]
    conn.execute("INSERT INTO sequences_du_cycle (code, theme_id, cycle_code, numero, nom) "
                 "VALUES ('S02', ?, ?, 2, 'Deuxième séquence')", (theme_id, cycle))
    conn.execute("INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES (?,?,'S02')",
                 (f"sn_{uuid.uuid4().hex[:8]}", niveau))
    for seq in ("S01", "S02"):
        conn.execute("INSERT INTO fiches_resume (id, titre, niveau, sequence) VALUES (?,?,?,?)",
                     (f"f_{seq}", f"Fiche {seq}", niveau, seq))
    conn.commit()


@pytest.fixture
def atomes_simules(monkeypatch):
    monkeypatch.setattr(lf, "charger_atome", lambda conn, t, fid: SimpleNamespace(
        id=fid, corps=f"corps {fid}", niveau="N10", sequence=fid[2:], variables=""))
    monkeypatch.setattr(lf, "resoudre_macros_csv", lambda conn, corps, n, s: corps)
    monkeypatch.setattr(lf, "generer_corps_fiche", lambda a: f"FICHE[{a.id}]")


def test_generation_filtree_sur_une_sequence(store_avec_paquet, atomes_simules):
    with _conn(store_avec_paquet) as conn:
        _deux_sequences_avec_fiches(conn)
        annuel = lf.generer_livret_fiches(conn, "N10", options={})
        s02 = lf.generer_livret_fiches(conn, "N10", options={}, sequence="S02")
    assert "FICHE[f_S01]" in annuel and "FICHE[f_S02]" in annuel
    assert r"\tableofcontents" in annuel and "Livret de fiches" in annuel
    assert "FICHE[f_S02]" in s02 and "FICHE[f_S01]" not in s02
    assert r"\tableofcontents" not in s02 and "Deuxième séquence" in s02
    assert "Fiches de résumé" in s02 and s02.count("{") == s02.count("}")


@pytest.mark.parametrize("decoupage, attendu", [
    ("annuel", ["unique"]),
    ("par_sequence", ["N10/S01", "N10/S02"]),
    ("les_deux", ["unique", "N10/S01", "N10/S02"]),
])
def test_cibles_selon_decoupage(store_avec_paquet, decoupage, attendu):
    with _conn(store_avec_paquet) as conn:
        _deux_sequences_avec_fiches(conn)
        conn.execute("INSERT INTO referentiel_niveaux (id, niveau, version) "
                     "VALUES ('R10', 'N10', '2026')")
        conn.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document, "
                     "options) VALUES ('d1', 'R10', 'livret_fiches', ?)",
                     (json.dumps({"actif": True, "decoupage_fiches": decoupage}),))
        cibles = lister_cibles_document(conn, "d1", "R10", "livret_fiches")
    assert [c["cible_id"] for c in cibles] == attendu
    noms = {c["cible_id"]: c["nom_fichier"] for c in cibles}
    if "N10/S02" in noms:
        assert noms["N10/S02"] == "livret_fiches__N10__S02.pdf"


def test_option_validee():
    assert "decoupage_fiches" in rd.OPTIONS_PAR_DEFAUT["livret_fiches"]
    assert rd.ENUMS["decoupage_fiches"] == ("annuel", "par_sequence", "les_deux")


def test_expose_dans_les_documents_associables(store_avec_paquet):
    from services import progression_doc as pgd
    with _conn(store_avec_paquet) as conn:
        _deux_sequences_avec_fiches(conn)
        conn.execute("INSERT INTO referentiel_niveaux (id, niveau, version) "
                     "VALUES ('R10', 'N10', '2026')")
        conn.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document, "
                     "options) VALUES ('d1', 'R10', 'livret_fiches', ?)",
                     (json.dumps({"actif": True, "decoupage_fiches": "les_deux"}),))
        dispo = pgd.documents_disponibles(conn, "N10", "2026-2027", "S02")
    seq = [d for d in dispo["sequence"] if d["doc_ref"].startswith("livret_fiches|")]
    ann = [d for d in dispo["annuels"] if d["doc_ref"].startswith("livret_fiches|")]
    assert [d["doc_ref"] for d in seq] == ["livret_fiches|N10/S02"]
    assert seq[0]["libelle"].endswith("S02")
    assert [d["doc_ref"] for d in ann] == ["livret_fiches|unique"]
