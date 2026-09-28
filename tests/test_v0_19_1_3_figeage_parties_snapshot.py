"""tests/test_v0_19_1_3_figeage_parties_snapshot.py — v0.19.1.3

Le verrouillage d'un référentiel doit FIGER le découpage en parties dans le
snapshot en base (tables `referentiel_*`), depuis le modèle actif :
  - `referentiel_parties` peuplée (1 ligne par partie de séquence) ;
  - `referentiel_objectifs.partie_numero` corrigé (partie réelle de chaque
    objectif via objectifs.partie_id → sequence_parties.numero) ;
  - `referentiel_objectifs.nb_seances` repris du modèle actif.

Le déverrouillage doit PURGER ce snapshot (un référentiel `valide` n'a pas de
photo en base — sa structure repart vivre dans le modèle actif).

Conséquence côté progression : `lister_parties_referentiel` voit alors les
parties multiples, et les objectifs d'un créneau de partie 2 ne sont plus
vides.

Pourquoi ce test : avant v0.19.1.3, le figeage ne produisait qu'une trace JSON
(jamais relue) ; les tables `referentiel_*` gardaient partie_numero=1 partout,
d'où la perte des 2es parties dans l'atelier Progression.
"""

from __future__ import annotations

from pathlib import Path
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.referentiel_figeage import (  # noqa: E402
    peupler_snapshot_parties, purger_snapshot_referentiel,
)
from services.referentiels import deverrouiller  # noqa: E402


# ── Helpers : modèle ACTIF (sequence_parties + objectifs.partie_id) ─────────

def _ref(conn, etat='verrouille', niveau='N11', version='2025_test'):
    rid = f"ref_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO referentiel_niveaux
        (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES (?, ?, ?, '2025-09-01', '2026-08-31', 'Test', ?)""",
        (rid, niveau, version, etat))
    return rid


def _seq_ref(conn, ref_id, code, numero, theme='A'):
    conn.execute("""INSERT INTO referentiel_sequences
        (referentiel_id, code, numero, nom, theme_code)
        VALUES (?, ?, ?, ?, ?)""",
        (ref_id, code, numero, f"Séquence {code}", theme))


def _sn(conn, niveau, sequence_code):
    sid = f"sn_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO sequences_par_niveau
        (id, niveau, sequence_code, parametres) VALUES (?, ?, ?, '')""",
        (sid, niveau, sequence_code))
    return sid


def _partie(conn, sn_id, numero, nb_seances_R_AE=0.0):
    pid = f"pt_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO sequence_parties
        (id, sequence_par_niveau_id, numero, nb_seances_R_AE)
        VALUES (?, ?, ?, ?)""", (pid, sn_id, numero, nb_seances_R_AE))
    return pid


def _obj_actif(conn, partie_id, code, nb_seances=1.0):
    oid = f"ob_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO objectifs
        (id, partie_id, code, nom, methode_id,
         critere_F, critere_A, critere_E, fin_cycle, nb_seances)
        VALUES (?, ?, ?, ?, NULL, '', '', '', 'N', ?)""",
        (oid, partie_id, code, f"Objectif {code}", nb_seances))
    return oid


def _obj_ref(conn, ref_id, seq_code, code, partie_numero=1, nb_seances=0.0):
    conn.execute("""INSERT INTO referentiel_objectifs
        (referentiel_id, seq_code, code, nom, fin_cycle,
         critere_f, critere_a, critere_e, partie_numero, nb_seances)
        VALUES (?, ?, ?, ?, 0, '', '', '', ?, ?)""",
        (ref_id, seq_code, code, f"Objectif {code}", partie_numero, nb_seances))


def _monter_referentiel_2_parties(conn, niveau='N11'):
    """Référentiel avec S12 en 2 parties (P1: 01-03 ; P2: 11-13) et S02 en
    1 partie (01). Snapshot referentiel_objectifs initialement à plat
    (partie_numero=1 partout, nb_seances=0), comme à l'import historique."""
    ref = _ref(conn, niveau=niveau)
    conn.execute("""INSERT INTO referentiel_themes
        (referentiel_id, code, nom, couleur) VALUES (?, 'A', 'Nombres', 'nombres')""",
        (ref,))
    _seq_ref(conn, ref, 'S12', 12)
    _seq_ref(conn, ref, 'S02', 2)

    # Modèle actif S12 : 2 parties.
    sn12 = _sn(conn, niveau, 'S12')
    p12_1 = _partie(conn, sn12, 1, nb_seances_R_AE=1.5)
    p12_2 = _partie(conn, sn12, 2, nb_seances_R_AE=2.0)
    for code in ('01', '02', '03'):
        _obj_actif(conn, p12_1, code, nb_seances=1.0)
    for code in ('11', '12', '13'):
        _obj_actif(conn, p12_2, code, nb_seances=0.5)
    # Modèle actif S02 : 1 partie.
    sn02 = _sn(conn, niveau, 'S02')
    p02_1 = _partie(conn, sn02, 1)
    _obj_actif(conn, p02_1, '01', nb_seances=2.0)

    # Snapshot objectifs (à plat, tel qu'à l'import).
    for code in ('01', '02', '03', '11', '12', '13'):
        _obj_ref(conn, ref, 'S12', code, partie_numero=1, nb_seances=0.0)
    _obj_ref(conn, ref, 'S02', '01', partie_numero=1, nb_seances=0.0)
    return ref


# ── Tests : peuplement du snapshot ──────────────────────────────────────────

class TestPeuplementSnapshot:
    def test_referentiel_parties_peuplee(self, sqlite_store):
        with sqlite_store._conn() as conn:
            ref = _monter_referentiel_2_parties(conn)
            rapport = peupler_snapshot_parties(conn, ref, 'N11')
            assert rapport['nb_parties'] == 3  # S12:2 + S02:1
            rows = conn.execute(
                "SELECT seq_code, numero, nb_seances_R_AE FROM referentiel_parties "
                "WHERE referentiel_id=? ORDER BY seq_code, numero", (ref,)
            ).fetchall()
            triplets = [(r['seq_code'], r['numero']) for r in rows]
            assert triplets == [('S02', 1), ('S12', 1), ('S12', 2)]
            # nb_seances_R_AE figé.
            s12p2 = next(r for r in rows
                         if r['seq_code'] == 'S12' and r['numero'] == 2)
            assert s12p2['nb_seances_R_AE'] == 2.0

    def test_partie_numero_objectifs_corrige(self, sqlite_store):
        with sqlite_store._conn() as conn:
            ref = _monter_referentiel_2_parties(conn)
            peupler_snapshot_parties(conn, ref, 'N11')
            # S12 : 01-03 en partie 1, 11-13 en partie 2.
            rows = conn.execute(
                "SELECT code, partie_numero, nb_seances FROM referentiel_objectifs "
                "WHERE referentiel_id=? AND seq_code='S12' ORDER BY code", (ref,)
            ).fetchall()
            parmap = {r['code']: r['partie_numero'] for r in rows}
            assert parmap == {'01': 1, '02': 1, '03': 1,
                              '11': 2, '12': 2, '13': 2}
            # nb_seances repris du modèle actif (P1=1.0, P2=0.5).
            nbmap = {r['code']: r['nb_seances'] for r in rows}
            assert nbmap['01'] == 1.0 and nbmap['11'] == 0.5

    def test_idempotent_re_execution(self, sqlite_store):
        with sqlite_store._conn() as conn:
            ref = _monter_referentiel_2_parties(conn)
            peupler_snapshot_parties(conn, ref, 'N11')
            peupler_snapshot_parties(conn, ref, 'N11')  # 2e passe
            n = conn.execute(
                "SELECT COUNT(*) FROM referentiel_parties WHERE referentiel_id=?",
                (ref,)
            ).fetchone()[0]
            assert n == 3  # pas de doublon

    def test_lister_parties_voit_les_2_parties(self, sqlite_store):
        with sqlite_store._conn() as conn:
            ref = _monter_referentiel_2_parties(conn)
            peupler_snapshot_parties(conn, ref, 'N11')
        # Hors transaction : lecture via l'API du store.
        parties = sqlite_store.lister_parties_referentiel(ref)
        cles = [(p['seq_code'], p['partie_numero']) for p in parties]
        assert ('S12', 1) in cles and ('S12', 2) in cles
        s12p2 = next(p for p in parties
                     if p['seq_code'] == 'S12' and p['partie_numero'] == 2)
        # 3 objectifs en P2 (11,12,13).
        assert s12p2['nb_objectifs'] == 3


# ── Tests : purge au déverrouillage ─────────────────────────────────────────

class TestPurgeAuDeverrouillage:
    def test_deverrouiller_purge_le_snapshot(self, sqlite_store):
        with sqlite_store._conn() as conn:
            ref = _monter_referentiel_2_parties(conn)
            peupler_snapshot_parties(conn, ref, 'N11')
            conn.commit()
        # Déverrouiller (verrouille → valide) doit purger referentiel_parties
        # et remettre partie_numero=1.
        with sqlite_store._conn() as conn:
            deverrouiller(conn, ref)
        with sqlite_store._conn() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM referentiel_parties WHERE referentiel_id=?",
                (ref,)
            ).fetchone()[0]
            assert n == 0
            parties_distinctes = conn.execute(
                "SELECT DISTINCT partie_numero FROM referentiel_objectifs "
                "WHERE referentiel_id=?", (ref,)
            ).fetchall()
            assert [r['partie_numero'] for r in parties_distinctes] == [1]

    def test_purge_directe(self, sqlite_store):
        with sqlite_store._conn() as conn:
            ref = _monter_referentiel_2_parties(conn)
            peupler_snapshot_parties(conn, ref, 'N11')
            purger_snapshot_referentiel(conn, ref)
            n = conn.execute(
                "SELECT COUNT(*) FROM referentiel_parties WHERE referentiel_id=?",
                (ref,)
            ).fetchone()[0]
            assert n == 0


# ── Test : fallback lister_parties quand snapshot vide (vieux gels) ─────────

class TestFallbackSnapshotVide:
    def test_fallback_une_partie_si_referentiel_parties_vide(self, sqlite_store):
        with sqlite_store._conn() as conn:
            ref = _monter_referentiel_2_parties(conn)
            # PAS de peuplement → referentiel_parties vide, objectifs à plat.
            conn.commit()
        parties = sqlite_store.lister_parties_referentiel(ref)
        # Sans snapshot, on retombe sur les partie_numero des objectifs
        # (tous à 1) → une partie par séquence.
        cles = sorted((p['seq_code'], p['partie_numero']) for p in parties)
        assert cles == [('S02', 1), ('S12', 1)]
