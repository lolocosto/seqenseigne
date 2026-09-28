"""tests/test_v0_15_3_etats_referentiel.py — v0.15.3

Tests du modèle d'état révisé :

  en_cours → valide → verrouille → utilise
                      └─ annule (concurrents écartés)

Couvre :
- Migration BDD : `fige` → `verrouille` au boot.
- Renommage `figer_minimal` → `verrouiller_minimal` (alias rétrocompat).
- Renommage `figer_complet` → `verrouiller_complet` (alias rétrocompat).
- Nouveau `services.referentiels.deverrouiller` : verrouille → valide.
- Endpoint POST /api/referentiels/<id>/verrouiller (+ alias /figer).
- Endpoint POST /api/referentiels/<id>/deverrouiller.
- Endpoint GET /api/referentiels/<id>/trace (lecture JSON verrouillé).
- Endpoint GET /api/referentiels/<id>/pdf/<nom_fichier> (PDF verrouillé).
- États terminaux étendus : {verrouille, utilise, annule}.
- Dossier renommé `_fige/` → `_verrouille/`.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def _conn(store):
    return store._conn()


def _ref(conn, etat='valide', niveau='N10', version='2025_v1'):
    rid = f"ref_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO referentiel_niveaux
        (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES (?, ?, ?, '2025-09-01', '2026-08-31', 'T', ?)""",
        (rid, niveau, version, etat))
    return rid


# ── Migration BDD : fige → verrouille au boot ─────────────────────────────


def test_migration_fige_vers_verrouille_au_boot(tmp_path):
    """À l'instanciation du SqliteStore sur une BDD existante en schéma
    v0.13.5.1 (CHECK autorisant 'fige'), la migration v0.15.3 renomme
    `fige` en `verrouille` et recrée la table avec le nouveau CHECK.
    """
    from persistence.sqlite_store import SqliteStore
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # 1) Créer manuellement une BDD avec le schéma v0.13.5.1 (CHECK qui
    #    autorise encore 'fige'). On ne passe PAS par SqliteStore ici
    #    pour pouvoir insérer des lignes 'fige'.
    db = data_dir / "seqenseigne.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE referentiel_niveaux (
            id           TEXT PRIMARY KEY,
            niveau       TEXT NOT NULL,
            version      TEXT NOT NULL,
            date_debut   TEXT,
            date_fin     TEXT,
            description  TEXT NOT NULL DEFAULT '',
            etat         TEXT NOT NULL DEFAULT 'en_cours'
                         CHECK (etat IN ('en_cours', 'valide', 'fige',
                                         'verrouille', 'annule')),
            UNIQUE (niveau, version)
        )
    """)
    conn.execute("""INSERT INTO referentiel_niveaux
        (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES ('ref_old1', 'N10', '2024_v1', NULL, NULL, '', 'fige'),
               ('ref_old2', 'N11', '2024_v1', NULL, NULL, '', 'fige'),
               ('ref_ok',   'N12', '2024_v1', NULL, NULL, '', 'verrouille')""")
    conn.commit()
    conn.close()

    # 2) Instancier le SqliteStore → migration v0.15.3 doit s'exécuter
    store = SqliteStore(str(data_dir))

    # 3) Tous les `fige` doivent être devenus `verrouille`
    with store._conn() as conn:
        rows = conn.execute(
            "SELECT id, etat FROM referentiel_niveaux ORDER BY id"
        ).fetchall()
    etats = {r["id"]: r["etat"] for r in rows}
    assert etats["ref_old1"] == "verrouille"
    assert etats["ref_old2"] == "verrouille"
    assert etats["ref_ok"]   == "verrouille"

    # 4) Le nouveau CHECK doit refuser 'fige' désormais
    with store._conn() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conn.execute("""INSERT INTO referentiel_niveaux
                (id, niveau, version, etat) VALUES ('z', 'N10', 'x', 'fige')""")


def test_migration_dossier_fige_renomme_en_verrouille(tmp_path):
    """Si un dossier `_fige/` existe sous un référentiel, il est
    renommé en `_verrouille/` au boot. Idempotent : si `_verrouille/`
    existe déjà, le `_fige/` n'est PAS renommé (on ne casse pas)."""
    from persistence.sqlite_store import SqliteStore
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Pré-existence d'un dossier _fige/ pour un ref
    ref_dir = data_dir / "referentiels" / "ref_test"
    (ref_dir / "_fige" / "pdfs").mkdir(parents=True)
    (ref_dir / "_fige" / "trace.json").write_text("{}", encoding="utf-8")
    # Boot
    SqliteStore(str(data_dir))
    # Renommage attendu
    assert not (ref_dir / "_fige").exists()
    assert (ref_dir / "_verrouille" / "trace.json").is_file()


# ── Services : verrouiller_minimal + alias ────────────────────────────────


def test_verrouiller_minimal_existe_et_alias_figer_minimal(sqlite_store):
    """L'API publique a verrouiller_minimal ; figer_minimal reste comme
    alias rétrocompat."""
    from services import referentiels as svc
    assert callable(svc.verrouiller_minimal)
    # Alias
    assert svc.figer_minimal is svc.verrouiller_minimal


def test_verrouiller_minimal_valide_passe_a_verrouille(sqlite_store):
    from services import referentiels as svc
    with _conn(sqlite_store) as conn:
        rid = _ref(conn, etat='valide')
        conn.commit()
        res = svc.verrouiller_minimal(conn, rid, force_confirme=True)
    assert res["ref"]["etat"] == "verrouille"


def test_verrouiller_minimal_refuse_si_pas_valide(sqlite_store):
    from services import referentiels as svc
    with _conn(sqlite_store) as conn:
        rid = _ref(conn, etat='en_cours')
        conn.commit()
        with pytest.raises(ValueError, match="valide"):
            svc.verrouiller_minimal(conn, rid)


# ── Services : deverrouiller ──────────────────────────────────────────────


def test_deverrouiller_revient_a_valide(sqlite_store):
    from services import referentiels as svc
    with _conn(sqlite_store) as conn:
        rid = _ref(conn, etat='verrouille')
        conn.commit()
        res = svc.deverrouiller(conn, rid)
    assert res["ref"]["etat"] == "valide"


def test_deverrouiller_refuse_si_pas_verrouille(sqlite_store):
    from services import referentiels as svc
    with _conn(sqlite_store) as conn:
        rid = _ref(conn, etat='valide')
        conn.commit()
        with pytest.raises(ValueError, match="verrouille"):
            svc.deverrouiller(conn, rid)


def test_deverrouiller_inconnu_leve(sqlite_store):
    from services import referentiels as svc
    with _conn(sqlite_store) as conn:
        with pytest.raises(ValueError, match="introuvable"):
            svc.deverrouiller(conn, "ref_inexistant")


def test_deverrouiller_refuse_etats_terminaux_autres(sqlite_store):
    """utilise et annule : non déverrouillables (pas verrouille)."""
    from services import referentiels as svc
    with _conn(sqlite_store) as conn:
        for i, etat in enumerate(('utilise', 'annule', 'en_cours')):
            rid = _ref(conn, etat=etat, version=f'2025_v{i}')
            conn.commit()
            with pytest.raises(ValueError, match="verrouille"):
                svc.deverrouiller(conn, rid)


# ── Lazy : verrouille/utilise/annule sont terminaux ──────────────────────


def test_lazy_ne_touche_pas_verrouille(sqlite_store):
    from services.referentiel_validation import maj_etat_lazy
    with _conn(sqlite_store) as conn:
        rid = _ref(conn, etat='verrouille')
        # Ajout d'un atome non valide qui rendrait non-éligible
        conn.execute("""INSERT INTO exercices
            (id, niveau, sequence, num, serie, titre, enonce, corrige,
             etat_code, mtime)
            VALUES ('ex1','N10','S01',1,'F','t','','',
                    'en_cours','2026-01-01 00:00:00')""")
        conn.commit()
        nouvel = maj_etat_lazy(conn, rid)
    assert nouvel == "verrouille"   # inchangé


def test_lazy_ne_touche_pas_utilise(sqlite_store):
    from services.referentiel_validation import maj_etat_lazy
    with _conn(sqlite_store) as conn:
        rid = _ref(conn, etat='utilise')
        conn.commit()
        nouvel = maj_etat_lazy(conn, rid)
    assert nouvel == "utilise"


# ── Routes ─────────────────────────────────────────────────────────────────


def test_route_verrouiller_disponible(client, app):
    """POST /api/referentiels/<id>/verrouiller fonctionne (nouvelle URL)."""
    with app.json_store._conn() as conn:
        rid = _ref(conn, etat='valide')
        conn.commit()
    rep = client.post(f"/api/referentiels/{rid}/verrouiller",
                       json={"force_confirme": True})
    assert rep.status_code == 200
    data = rep.get_json()
    assert data["ref"]["etat"] == "verrouille"


def test_route_figer_reste_en_alias(client, app):
    """POST /api/referentiels/<id>/figer reste disponible comme alias
    rétrocompat (mêmes effets que /verrouiller)."""
    with app.json_store._conn() as conn:
        rid = _ref(conn, etat='valide')
        conn.commit()
    rep = client.post(f"/api/referentiels/{rid}/figer",
                       json={"force_confirme": True})
    assert rep.status_code == 200
    assert rep.get_json()["ref"]["etat"] == "verrouille"


def test_route_deverrouiller_passe_a_valide(client, app):
    """POST /api/referentiels/<id>/deverrouiller fait verrouille → valide."""
    with app.json_store._conn() as conn:
        rid = _ref(conn, etat='verrouille')
        conn.commit()
    rep = client.post(f"/api/referentiels/{rid}/deverrouiller")
    assert rep.status_code == 200
    assert rep.get_json()["ref"]["etat"] == "valide"


def test_route_deverrouiller_404_si_inconnu(client):
    rep = client.post("/api/referentiels/inexistant/deverrouiller")
    assert rep.status_code == 404


def test_route_deverrouiller_409_si_pas_verrouille(client, app):
    with app.json_store._conn() as conn:
        rid = _ref(conn, etat='valide')
        conn.commit()
    rep = client.post(f"/api/referentiels/{rid}/deverrouiller")
    assert rep.status_code == 409


# ── Routes lecture données verrouillées ──────────────────────────────────


def test_route_trace_404_si_pas_verrouille(client, app):
    """GET /trace → 404 si pas de dossier _verrouille/ sur disque."""
    with app.json_store._conn() as conn:
        rid = _ref(conn, etat='valide')
        conn.commit()
    rep = client.get(f"/api/referentiels/{rid}/trace")
    assert rep.status_code == 404


def test_route_trace_404_si_inconnu(client):
    rep = client.get("/api/referentiels/inexistant/trace")
    assert rep.status_code == 404


def test_route_trace_sert_le_json_si_verrouille(client, app, tmp_path):
    """GET /trace lit `<ref>/_verrouille/trace.json` et le renvoie tel quel."""
    with app.json_store._conn() as conn:
        rid = _ref(conn, etat='verrouille')
        conn.commit()
    # Poser un trace.json sur disque
    from services.referentiel_documents_compilation import (
        _dossier_du_referentiel)
    fige = _dossier_du_referentiel(app.json_store, rid) / "_verrouille"
    fige.mkdir(parents=True)
    payload = {"version_schema": 2, "referentiel": {"id": rid}}
    (fige / "trace.json").write_text(json.dumps(payload), encoding="utf-8")

    rep = client.get(f"/api/referentiels/{rid}/trace")
    assert rep.status_code == 200
    assert rep.get_json() == payload


def test_route_pdf_404_si_absent(client, app):
    with app.json_store._conn() as conn:
        rid = _ref(conn, etat='verrouille')
        conn.commit()
    rep = client.get(f"/api/referentiels/{rid}/pdf/inexistant.pdf")
    assert rep.status_code == 404


def test_route_pdf_400_si_nom_invalide(client, app):
    """Refuse les chemins relatifs / caractères dangereux."""
    with app.json_store._conn() as conn:
        rid = _ref(conn, etat='verrouille')
        conn.commit()
    for nom in ['../etc/passwd', '..\\windows\\system32.pdf',
                 'foo/bar.pdf', 'foo bar.pdf']:
        rep = client.get(f"/api/referentiels/{rid}/pdf/{nom}")
        assert rep.status_code in (400, 404), \
            f"Nom dangereux {nom} accepté (status={rep.status_code})"


def test_route_pdf_sert_le_fichier_si_present(client, app):
    """GET /pdf/<nom> sert le fichier `_verrouille/pdfs/<nom>` si présent."""
    with app.json_store._conn() as conn:
        rid = _ref(conn, etat='verrouille')
        conn.commit()
    from services.referentiel_documents_compilation import (
        _dossier_du_referentiel)
    fige = _dossier_du_referentiel(app.json_store, rid) / "_verrouille" / "pdfs"
    fige.mkdir(parents=True)
    (fige / "livret_test.pdf").write_bytes(b"%PDF-1.4 contenu test\n")

    rep = client.get(f"/api/referentiels/{rid}/pdf/livret_test.pdf")
    assert rep.status_code == 200
    assert rep.mimetype == "application/pdf"
    assert b"%PDF-1.4" in rep.data
