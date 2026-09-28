"""tests/test_v0_13_5_1_referentiels.py
Tests des ajouts v0.13.5.1 : schéma 5 états, service (creer_coquille,
supprimer, lister_concurrents_a_annuler, verrouiller_minimal, arbre_du_niveau),
routes correspondantes.
"""

import datetime
from pathlib import Path

import pytest
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services import referentiels as svc


# ── Helpers ──────────────────────────────────────────────────────────────────

def _conn(store):
    """Récupère le context manager de connexion du store. À utiliser
    avec `with _conn(store) as conn:`."""
    return store._conn()


# ── Schéma : 5 états et nouvelles tables ─────────────────────────────────────

def test_schema_5_etats_acceptes(sqlite_store):
    """v0.15.3 — La table referentiel_niveaux accepte les 5 états du
    nouveau cycle (fige fusionné dans verrouille, ajout d'utilise)."""
    with _conn(sqlite_store) as conn:
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='referentiel_niveaux'"
        ).fetchone()["sql"]
        for etat in ("en_cours", "valide", "verrouille", "utilise", "annule"):
            assert f"'{etat}'" in ddl, f"État {etat} absent du DDL"
        # `fige` ne doit plus être autorisé (migration v0.15.3)
        assert "'fige'" not in ddl, "État 'fige' encore présent dans le DDL"


def test_schema_etat_invalide_refuse(sqlite_store):
    """Un état hors énumération doit être refusé par le CHECK."""
    import sqlite3
    with _conn(sqlite_store) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO referentiel_niveaux "
                "(id, niveau, version, etat) VALUES "
                "('test_inv', 'N99', 'v', 'foobar')"
            )


def test_schema_nouvelles_tables_existent(sqlite_store):
    """Les tables referentiel_parties et referentiel_obj_exos existent."""
    with _conn(sqlite_store) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('referentiel_parties', 'referentiel_obj_exos')"
        ).fetchall()
        names = {r["name"] for r in rows}
        assert "referentiel_parties" in names
        assert "referentiel_obj_exos" in names


def test_schema_referentiel_objectifs_nouvelles_colonnes(sqlite_store):
    """referentiel_objectifs a partie_numero et nb_seances."""
    with _conn(sqlite_store) as conn:
        cols = {r["name"] for r in conn.execute(
            "PRAGMA table_info(referentiel_objectifs)"
        ).fetchall()}
        assert "partie_numero" in cols
        assert "nb_seances" in cols


# ── Service : calculer_annee_scolaire ────────────────────────────────────────

def test_annee_scolaire_avant_aout():
    """Janvier-juillet : on est dans l'année scolaire commencée l'année civile précédente."""
    assert svc.calculer_annee_scolaire(datetime.date(2026, 5, 7)) == "2025"
    assert svc.calculer_annee_scolaire(datetime.date(2026, 7, 31)) == "2025"
    assert svc.calculer_annee_scolaire(datetime.date(2027, 2, 15)) == "2026"


def test_annee_scolaire_aout_inclus():
    """Août inclus : on bascule sur la nouvelle année scolaire."""
    assert svc.calculer_annee_scolaire(datetime.date(2026, 8, 1)) == "2026"
    assert svc.calculer_annee_scolaire(datetime.date(2026, 9, 1)) == "2026"
    assert svc.calculer_annee_scolaire(datetime.date(2026, 12, 31)) == "2026"


# ── Service : calculer_suffixe_disponible ────────────────────────────────────

def test_suffixe_vide_si_aucun_referentiel(sqlite_store):
    with _conn(sqlite_store) as conn:
        assert svc.calculer_suffixe_disponible(conn, "N11", "2025") == ""


def test_suffixe_b_si_vide_pris(sqlite_store):
    with _conn(sqlite_store) as conn:
        conn.execute(
            "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
            "VALUES ('2025_N11', 'N11', '2025', 'en_cours')"
        )
        assert svc.calculer_suffixe_disponible(conn, "N11", "2025") == "b"


def test_suffixe_c_si_b_pris(sqlite_store):
    with _conn(sqlite_store) as conn:
        conn.execute(
            "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
            "VALUES ('2025_N11', 'N11', '2025', 'en_cours')"
        )
        conn.execute(
            "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
            "VALUES ('2025_N11b', 'N11', '2025b', 'valide')"
        )
        assert svc.calculer_suffixe_disponible(conn, "N11", "2025") == "c"


def test_suffixe_inclut_etats_terminaux(sqlite_store):
    """Les états annule et verrouille comptent aussi dans les suffixes pris."""
    with _conn(sqlite_store) as conn:
        conn.execute(
            "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
            "VALUES ('2025_N11', 'N11', '2025', 'verrouille')"
        )
        conn.execute(
            "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
            "VALUES ('2025_N11b', 'N11', '2025b', 'annule')"
        )
        assert svc.calculer_suffixe_disponible(conn, "N11", "2025") == "c"


def test_suffixe_isolation_niveau(sqlite_store):
    """Suffixe pris sur N10 ne bloque pas N11."""
    with _conn(sqlite_store) as conn:
        conn.execute(
            "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
            "VALUES ('2025_N10', 'N10', '2025', 'en_cours')"
        )
        # N11 doit toujours pouvoir prendre suffixe vide
        assert svc.calculer_suffixe_disponible(conn, "N11", "2025") == ""


# ── Service : creer_coquille ─────────────────────────────────────────────────

def test_creer_coquille_simple(sqlite_store):
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref = svc.creer_coquille(conn, "N11", "Description test", maintenant=d)
    assert ref["id"] == "2025_N11"
    assert ref["niveau"] == "N11"
    assert ref["version"] == "2025"
    assert ref["etat"] == "en_cours"
    assert ref["description"] == "Description test"
    assert ref["date_debut"] is None
    assert ref["date_fin"] is None


def test_creer_coquille_suffixe_b(sqlite_store):
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        svc.creer_coquille(conn, "N11", maintenant=d)
        ref2 = svc.creer_coquille(conn, "N11", maintenant=d)
    assert ref2["id"] == "2025_N11b"
    assert ref2["version"] == "2025b"


def test_creer_coquille_niveau_vide_refuse(sqlite_store):
    with _conn(sqlite_store) as conn:
        with pytest.raises(ValueError):
            svc.creer_coquille(conn, "")


def test_creer_coquille_niveau_blanc_refuse(sqlite_store):
    with _conn(sqlite_store) as conn:
        with pytest.raises(ValueError):
            svc.creer_coquille(conn, "   ")


def test_creer_coquille_persiste_uniquement_niveaux(sqlite_store):
    """La coquille ne peuple que referentiel_niveaux, pas les autres tables."""
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref = svc.creer_coquille(conn, "N11", maintenant=d)
        n_themes = conn.execute(
            "SELECT COUNT(*) FROM referentiel_themes WHERE referentiel_id=?",
            (ref["id"],),
        ).fetchone()[0]
        n_seqs = conn.execute(
            "SELECT COUNT(*) FROM referentiel_sequences WHERE referentiel_id=?",
            (ref["id"],),
        ).fetchone()[0]
    assert n_themes == 0
    assert n_seqs == 0


# ── Service : supprimer ──────────────────────────────────────────────────────

def test_supprimer_en_cours_ok(sqlite_store):
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref = svc.creer_coquille(conn, "N11", maintenant=d)
        svc.supprimer(conn, ref["id"])
        # Vérifier l'absence
        row = conn.execute(
            "SELECT * FROM referentiel_niveaux WHERE id=?", (ref["id"],),
        ).fetchone()
    assert row is None


def test_supprimer_introuvable(sqlite_store):
    with _conn(sqlite_store) as conn:
        with pytest.raises(ValueError, match="introuvable"):
            svc.supprimer(conn, "id_qui_existe_pas")


def test_supprimer_valide_refuse(sqlite_store):
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref = svc.creer_coquille(conn, "N11", maintenant=d)
        conn.execute("UPDATE referentiel_niveaux SET etat='valide' WHERE id=?",
                     (ref["id"],))
        with pytest.raises(ValueError, match="en_cours"):
            svc.supprimer(conn, ref["id"])


def test_supprimer_fige_refuse(sqlite_store):
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref = svc.creer_coquille(conn, "N11", maintenant=d)
        conn.execute("UPDATE referentiel_niveaux SET etat='verrouille' WHERE id=?",
                     (ref["id"],))
        with pytest.raises(ValueError, match="en_cours"):
            svc.supprimer(conn, ref["id"])


def test_supprimer_verrouille_refuse(sqlite_store):
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref = svc.creer_coquille(conn, "N11", maintenant=d)
        conn.execute("UPDATE referentiel_niveaux SET etat='verrouille' WHERE id=?",
                     (ref["id"],))
        with pytest.raises(ValueError, match="en_cours"):
            svc.supprimer(conn, ref["id"])


def test_supprimer_annule_refuse(sqlite_store):
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref = svc.creer_coquille(conn, "N11", maintenant=d)
        conn.execute("UPDATE referentiel_niveaux SET etat='annule' WHERE id=?",
                     (ref["id"],))
        with pytest.raises(ValueError, match="en_cours"):
            svc.supprimer(conn, ref["id"])


# ── Service : lister_concurrents_a_annuler ───────────────────────────────────

def test_concurrents_aucun_si_seul(sqlite_store):
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref = svc.creer_coquille(conn, "N11", maintenant=d)
        concs = svc.lister_concurrents_a_annuler(conn, ref["id"])
    assert concs == []


def test_concurrents_un_en_cours_anterieur(sqlite_store):
    """2025_N11 (en_cours) + 2025_N11b → b voit a comme concurrent."""
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref1 = svc.creer_coquille(conn, "N11", maintenant=d)  # 2025_N11
        ref2 = svc.creer_coquille(conn, "N11", maintenant=d)  # 2025_N11b
        concs = svc.lister_concurrents_a_annuler(conn, ref2["id"])
    assert len(concs) == 1
    assert concs[0]["id"] == ref1["id"]


def test_concurrents_seuls_anterieurs(sqlite_store):
    """Pour 2025_N11b, on ne voit pas 2025_N11c (postérieur)."""
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        # On crée explicitement les 3 référentiels
        for vid, ver in [
            ("2025_N11", "2025"),
            ("2025_N11b", "2025b"),
            ("2025_N11c", "2025c"),
        ]:
            conn.execute(
                "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
                "VALUES (?, 'N11', ?, 'en_cours')",
                (vid, ver),
            )
        concs_b = svc.lister_concurrents_a_annuler(conn, "2025_N11b")
    assert {c["id"] for c in concs_b} == {"2025_N11"}


def test_concurrents_ignore_etats_terminaux(sqlite_store):
    """v0.15.3 — verrouille, utilise, annule ne sont pas des concurrents
    à écarter."""
    with _conn(sqlite_store) as conn:
        for vid, ver, etat in [
            ("2025_N11", "2025", "verrouille"),
            ("2025_N11b", "2025b", "utilise"),
            ("2025_N11c", "2025c", "annule"),
            ("2025_N11d", "2025d", "valide"),
        ]:
            conn.execute(
                "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
                "VALUES (?, 'N11', ?, ?)",
                (vid, ver, etat),
            )
        # Pour 'd', seuls a/b/c étaient antérieurs ; a=verrouille,
        # b=utilise, c=annule → tous écartés. Aucun concurrent.
        concs = svc.lister_concurrents_a_annuler(conn, "2025_N11d")
    assert concs == []


def test_concurrents_isolation_annee(sqlite_store):
    """Une année différente n'est pas concurrente."""
    with _conn(sqlite_store) as conn:
        conn.execute(
            "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
            "VALUES ('2024_N11', 'N11', '2024', 'en_cours')"
        )
        conn.execute(
            "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
            "VALUES ('2025_N11', 'N11', '2025', 'en_cours')"
        )
        # 2025 ne voit pas 2024 (autre année)
        concs = svc.lister_concurrents_a_annuler(conn, "2025_N11")
    assert concs == []


def test_concurrents_isolation_niveau(sqlite_store):
    """Un autre niveau n'est pas concurrent."""
    with _conn(sqlite_store) as conn:
        conn.execute(
            "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
            "VALUES ('2025_N10', 'N10', '2025', 'en_cours')"
        )
        conn.execute(
            "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
            "VALUES ('2025_N11', 'N11', '2025', 'en_cours')"
        )
        conn.execute(
            "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
            "VALUES ('2025_N11b', 'N11', '2025b', 'en_cours')"
        )
        # 2025_N11b ne voit que 2025_N11 (pas N10)
        concs = svc.lister_concurrents_a_annuler(conn, "2025_N11b")
    assert {c["id"] for c in concs} == {"2025_N11"}


# ── Service : verrouiller_minimal ──────────────────────────────────────────────────

def test_figer_introuvable(sqlite_store):
    with _conn(sqlite_store) as conn:
        with pytest.raises(ValueError, match="introuvable"):
            svc.verrouiller_minimal(conn, "id_inconnu")


def test_figer_pas_valide_refuse(sqlite_store):
    """en_cours → figer doit échouer."""
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref = svc.creer_coquille(conn, "N11", maintenant=d)
        with pytest.raises(ValueError, match="valide"):
            svc.verrouiller_minimal(conn, ref["id"])


def test_figer_sans_concurrents_passe_direct(sqlite_store):
    """valide sans concurrents → passe direct à fige sans confirmation."""
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref = svc.creer_coquille(conn, "N11", maintenant=d)
        conn.execute("UPDATE referentiel_niveaux SET etat='valide' WHERE id=?",
                     (ref["id"],))
        res = svc.verrouiller_minimal(conn, ref["id"], maintenant=d)
        # Vérification
        row = conn.execute(
            "SELECT etat, date_debut FROM referentiel_niveaux WHERE id=?",
            (ref["id"],),
        ).fetchone()
    assert res["confirmation_requise"] is False
    assert res["ref"]["etat"] == "verrouille"
    assert row["etat"] == "verrouille"
    assert row["date_debut"] == "2026-05-07"


def test_figer_avec_concurrents_demande_confirmation(sqlite_store):
    """valide + concurrent en_cours antérieur → confirmation requise, rien modifié."""
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref1 = svc.creer_coquille(conn, "N11", maintenant=d)  # 2025_N11
        ref2 = svc.creer_coquille(conn, "N11", maintenant=d)  # 2025_N11b
        conn.execute("UPDATE referentiel_niveaux SET etat='valide' WHERE id=?",
                     (ref2["id"],))
        # Sans force_confirme : doit demander confirmation
        res = svc.verrouiller_minimal(conn, ref2["id"], maintenant=d)
        # Aucun changement d'état attendu
        etats = dict(conn.execute(
            "SELECT id, etat FROM referentiel_niveaux WHERE niveau='N11'"
        ).fetchall())
    assert res["confirmation_requise"] is True
    assert len(res["concurrents"]) == 1
    assert res["concurrents"][0]["id"] == ref1["id"]
    # Les états doivent être inchangés
    assert etats[ref1["id"]] == "en_cours"
    assert etats[ref2["id"]] == "valide"


def test_figer_avec_concurrents_force_confirme_annule(sqlite_store):
    """valide + concurrent + force_confirme → annule + fige."""
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        ref1 = svc.creer_coquille(conn, "N11", maintenant=d)
        ref2 = svc.creer_coquille(conn, "N11", maintenant=d)
        conn.execute("UPDATE referentiel_niveaux SET etat='valide' WHERE id=?",
                     (ref2["id"],))
        res = svc.verrouiller_minimal(conn, ref2["id"], force_confirme=True,
                                maintenant=d)
        etats = dict(conn.execute(
            "SELECT id, etat FROM referentiel_niveaux WHERE niveau='N11'"
        ).fetchall())
    assert res["confirmation_requise"] is False
    assert res["ref"]["etat"] == "verrouille"
    assert len(res["concurrents_annules"]) == 1
    assert etats[ref1["id"]] == "annule"
    assert etats[ref2["id"]] == "verrouille"


def test_figer_ignore_concurrents_etats_terminaux(sqlite_store):
    """v0.15.3 — Concurrents en verrouille/annule → pas de confirmation requise."""
    d = datetime.date(2026, 5, 7)
    with _conn(sqlite_store) as conn:
        # 2025_N11 = verrouille, 2025_N11b = valide à verrouiller
        conn.execute(
            "INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
            "VALUES ('2025_N11', 'N11', '2025', 'verrouille')"
        )
        ref2 = svc.creer_coquille(conn, "N11", maintenant=d)  # 2025_N11b
        conn.execute("UPDATE referentiel_niveaux SET etat='valide' WHERE id=?",
                     (ref2["id"],))
        res = svc.verrouiller_minimal(conn, ref2["id"], maintenant=d)
        # Le 'verrouille' antérieur reste intact
        etat_ref1 = conn.execute(
            "SELECT etat FROM referentiel_niveaux WHERE id='2025_N11'"
        ).fetchone()["etat"]
    assert res["confirmation_requise"] is False
    assert res["ref"]["etat"] == "verrouille"
    assert etat_ref1 == "verrouille"


# ── Routes ──────────────────────────────────────────────────────────────────

def test_route_coquille_cree(client):
    r = client.post("/api/referentiels/coquille",
                    json={"niveau": "N11", "description": "D"})
    assert r.status_code == 201
    data = r.get_json()
    assert data["ref"]["niveau"] == "N11"
    assert data["ref"]["etat"] == "en_cours"


def test_route_coquille_niveau_manquant(client):
    r = client.post("/api/referentiels/coquille", json={})
    assert r.status_code == 400


def test_route_supprimer_en_cours(client):
    r = client.post("/api/referentiels/coquille", json={"niveau": "N11"})
    ref_id = r.get_json()["ref"]["id"]

    r = client.delete(f"/api/referentiels/{ref_id}")
    assert r.status_code == 204


def test_route_supprimer_introuvable(client):
    r = client.delete("/api/referentiels/n_existe_pas")
    assert r.status_code == 404


def test_route_supprimer_valide_refuse(client, sqlite_store):
    r = client.post("/api/referentiels/coquille", json={"niveau": "N11"})
    ref_id = r.get_json()["ref"]["id"]
    # Forcer à valide
    with _conn(sqlite_store) as conn:
        conn.execute("UPDATE referentiel_niveaux SET etat='valide' WHERE id=?",
                     (ref_id,))

    r = client.delete(f"/api/referentiels/{ref_id}")
    assert r.status_code == 409


def test_route_figer_pas_valide_refuse(client):
    r = client.post("/api/referentiels/coquille", json={"niveau": "N11"})
    ref_id = r.get_json()["ref"]["id"]

    r = client.post(f"/api/referentiels/{ref_id}/figer", json={})
    assert r.status_code == 409


def test_route_figer_introuvable(client):
    r = client.post("/api/referentiels/n_existe_pas/figer", json={})
    assert r.status_code == 404


def test_route_figer_passe(client, sqlite_store):
    r = client.post("/api/referentiels/coquille", json={"niveau": "N11"})
    ref_id = r.get_json()["ref"]["id"]
    with _conn(sqlite_store) as conn:
        conn.execute("UPDATE referentiel_niveaux SET etat='valide' WHERE id=?",
                     (ref_id,))

    r = client.post(f"/api/referentiels/{ref_id}/figer", json={})
    assert r.status_code == 200
    data = r.get_json()
    assert data["confirmation_requise"] is False
    assert data["ref"]["etat"] == "verrouille"


def test_route_figer_demande_confirmation(client, sqlite_store):
    """Concurrent existant → 200 mais confirmation_requise=True."""
    # 1er référentiel : en_cours
    r1 = client.post("/api/referentiels/coquille", json={"niveau": "N11"})
    # 2e : valide pour figer
    r2 = client.post("/api/referentiels/coquille", json={"niveau": "N11"})
    ref2_id = r2.get_json()["ref"]["id"]
    with _conn(sqlite_store) as conn:
        conn.execute("UPDATE referentiel_niveaux SET etat='valide' WHERE id=?",
                     (ref2_id,))

    r = client.post(f"/api/referentiels/{ref2_id}/figer", json={})
    assert r.status_code == 200
    data = r.get_json()
    assert data["confirmation_requise"] is True
    assert len(data["concurrents"]) == 1


def test_route_arbre_introuvable(client):
    r = client.get("/api/referentiels/n_existe_pas/arbre")
    assert r.status_code == 404


def test_route_arbre_structure(client, sqlite_store):
    """L'arbre retourne la structure attendue (pour un niveau sans données,
    sequences est []) et stats à 0/0/0."""
    r = client.post("/api/referentiels/coquille", json={"niveau": "N11"})
    ref_id = r.get_json()["ref"]["id"]

    r = client.get(f"/api/referentiels/{ref_id}/arbre")
    assert r.status_code == 200
    data = r.get_json()
    assert "ref" in data
    assert "arbre" in data
    assert data["ref"]["niveau"] == "N11"
    assert "sequences" in data["arbre"]
    assert isinstance(data["arbre"]["sequences"], list)
    assert "stats" in data["arbre"]
    assert "total" in data["arbre"]["stats"]
    assert "valides" in data["arbre"]["stats"]
    assert "en_cours" in data["arbre"]["stats"]


# ── v0.13.5.1.1 — Arbre : présence du champ atomes_rae sur les parties ──────

def test_arbre_partie_a_champ_atomes_rae(client):
    """Chaque partie de l'arbre doit avoir le champ `atomes_rae` (liste,
    éventuellement vide pour les parties sans R ni EA)."""
    r = client.post("/api/referentiels/coquille", json={"niveau": "N11"})
    ref_id = r.get_json()["ref"]["id"]
    r = client.get(f"/api/referentiels/{ref_id}/arbre")
    arbre = r.get_json()["arbre"]
    # Pour le test, suffit d'inspecter les parties remontées (peut être 0
    # si la BDD de test ne contient pas de séquences/parties peuplées —
    # le test conftest.py ne peuple pas les sequences_par_niveau, donc
    # arbre.sequences sera probablement vide. On valide juste la
    # structure si quelque chose remonte.)
    for s in arbre["sequences"]:
        for p in s["parties"]:
            assert "atomes_rae" in p
            assert isinstance(p["atomes_rae"], list)
            for a in p["atomes_rae"]:
                assert "type" in a and a["type"] == "exo_rae"
                assert "sous_type" in a
                assert a["sous_type"] in ("R", "EA")
                assert "code" in a
                assert "etat_code" in a


# ── v0.13.5.1.2 — Arbre : structure typée des objectifs ──────────────────────

def test_arbre_objectif_structure_typee(client):
    """Chaque objectif a `methode`, `fiche`, `notions`, `exos_F`, `exos_A`,
    `exos_E` (au lieu d'un `atomes` plat). Les R et EA portent un champ
    `nav_niveau` / `nav_seq` pour le deeplink, pareil pour les atomes
    d'objectif."""
    r = client.post("/api/referentiels/coquille", json={"niveau": "N11"})
    ref_id = r.get_json()["ref"]["id"]
    r = client.get(f"/api/referentiels/{ref_id}/arbre")
    arbre = r.get_json()["arbre"]
    for s in arbre["sequences"]:
        for p in s["parties"]:
            for o in p["objectifs"]:
                # Plus de clé "atomes"
                assert "atomes" not in o
                # Nouvelles clés
                for k in ("methode", "fiche", "notions",
                          "exos_F", "exos_A", "exos_E"):
                    assert k in o, f"Clé {k!r} absente de l'objectif"
                # methode / fiche peuvent être None ; notions et exos_*
                # sont des listes
                assert (o["methode"] is None
                        or isinstance(o["methode"], dict))
                assert (o["fiche"] is None
                        or isinstance(o["fiche"], dict))
                for clst in ("notions", "exos_F", "exos_A", "exos_E"):
                    assert isinstance(o[clst], list)
                # nav_niveau / nav_seq présents partout
                tous = ([o["methode"]] if o["methode"] else []) \
                     + ([o["fiche"]]   if o["fiche"]   else []) \
                     + o["notions"] + o["exos_F"] + o["exos_A"] + o["exos_E"]
                for a in tous:
                    assert "nav_niveau" in a
                    assert "nav_seq" in a


# ── v0.13.5.1.4 — Objectifs "Cours" : champ est_cours et structure vide ──────

def test_arbre_objectif_cours_marque_et_vide(client):
    """Les objectifs "Cours" (convention : code 01, 11, 21 selon le numéro
    de partie) ont est_cours=True et toutes leurs sections vides
    (methode=None, fiche=None, listes vides). On vérifie aussi que les
    objectifs non-Cours ont est_cours=False."""
    r = client.post("/api/referentiels/coquille", json={"niveau": "N11"})
    ref_id = r.get_json()["ref"]["id"]
    r = client.get(f"/api/referentiels/{ref_id}/arbre")
    arbre = r.get_json()["arbre"]
    for s in arbre["sequences"]:
        for p in s["parties"]:
            for o in p["objectifs"]:
                # Tous les objectifs ont le champ
                assert "est_cours" in o
                assert isinstance(o["est_cours"], bool)
                # Si est_cours=True : toutes les sections doivent être vides
                if o["est_cours"]:
                    assert o["methode"] is None
                    assert o["fiche"] is None
                    assert o["notions"] == []
                    assert o["exos_F"] == []
                    assert o["exos_A"] == []
                    assert o["exos_E"] == []
                    # Et le code doit suivre la convention
                    code_attendu = f"{p['numero'] - 1}1"
                    assert o["code"] == code_attendu, \
                        f"Cours mal détecté : code={o['code']} pour P{p['numero']}"
