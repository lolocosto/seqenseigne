"""tests/test_v0_15_2_11_trace_v2.py — v0.15.2.11

Restructuration de la trace JSON :
- Les `objectifs` sont SOUS chaque `partie` (et non plus au niveau séquence).
- Chaque `partie` porte : `cartes_automatisme`, `nb_seances_R_AE`,
  `exercices_R` (révisions), `exercices_AE` (approche), `objectifs`.
- Chaque `objectif` porte ses propres : `methodes`, `notions`,
  `exercices`, `fiches_resume`. Sauf l'objectif "Cours" (code 01/11/21)
  qui n'a pas ces sections.
- `version_schema` passe de 1 à 2.
- Séries traduites en labels : F→fondamental, A→avancé, E→exploration.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.referentiel_figeage import (  # noqa: E402
    generer_trace, VERSION_SCHEMA_TRACE,
    _serie_label,
)


def _conn(store):
    return store._conn()


# ── Helpers de fixture minimale ────────────────────────────────────────────


def _ref(conn, niveau='N11'):
    rid = f"ref_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO referentiel_niveaux
        (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES (?, ?, '2025', NULL, NULL, 'Test', 'valide')""",
        (rid, niveau))
    return rid


def _seq_referentiel(conn, ref_id, code='S01', numero=1, theme_code='A'):
    conn.execute("""INSERT INTO referentiel_themes
        (referentiel_id, code, nom, couleur)
        VALUES (?, ?, 'Nombres', 'nombres')
        ON CONFLICT DO NOTHING""", (ref_id, theme_code))
    conn.execute("""INSERT INTO referentiel_sequences
        (referentiel_id, code, numero, nom, theme_code)
        VALUES (?, ?, ?, 'Test', ?)""",
        (ref_id, code, numero, theme_code))


def _seq_par_niveau(conn, niveau, seq_code):
    sid = f"sn_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO sequences_par_niveau
        (id, niveau, sequence_code, parametres) VALUES (?, ?, ?, '')""",
        (sid, niveau, seq_code))
    return sid


def _partie(conn, sn_id, numero, nb_seances=1.0):
    pid = f"pt_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO sequence_parties
        (id, sequence_par_niveau_id, numero, nb_seances_R_AE)
        VALUES (?, ?, ?, ?)""", (pid, sn_id, numero, nb_seances))
    return pid


def _objectif(conn, partie_id, code, nom, methode_id=None,
              fin_cycle=0, nb_seances=1.0):
    oid = f"ob_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO objectifs
        (id, partie_id, code, nom, methode_id,
         critere_F, critere_A, critere_E, fin_cycle, nb_seances)
        VALUES (?, ?, ?, ?, ?, '', '', '', ?, ?)""",
        (oid, partie_id, code, nom, methode_id, fin_cycle, nb_seances))
    return oid


def _methode(conn, niveau, sequence, num, titre):
    mid = f"me_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO methodes
        (id, titre, corps, niveau, sequence, num_methode, etat_code, mtime)
        VALUES (?, ?, '', ?, ?, ?, 'valide', '2026-01-01 00:00:00')""",
        (mid, titre, niveau, sequence, num))
    return mid


def _notion(conn, niveau, sequence, num, titre):
    nid = f"no_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO notions
        (id, titre, corps, niveau, sequence, num_connaissance,
         etat_code, mtime)
        VALUES (?, ?, '', ?, ?, ?, 'valide', '2026-01-01 00:00:00')""",
        (nid, titre, niveau, sequence, num))
    return nid


def _exo(conn, niveau, sequence, num, serie_code, serie_label, titre=''):
    eid = f"ex_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO exercices
        (id, niveau, sequence, num, serie, serie_code, titre, enonce,
         corrige, etat_code, mtime)
        VALUES (?, ?, ?, ?, ?, ?, ?, '', '', 'valide',
                '2026-01-01 00:00:00')""",
        (eid, niveau, sequence, num, serie_label, serie_code, titre))
    return eid


def _fiche(conn, niveau, sequence, num, titre, objectif_id):
    fid = uuid.uuid4().hex
    conn.execute("""INSERT INTO fiches_resume
        (id, titre, objectif_id, num_fiche, niveau, sequence,
         etat_code, mtime)
        VALUES (?, ?, ?, ?, ?, ?, 'valide', '2026-01-01 00:00:00')""",
        (fid, titre, objectif_id, num, niveau, sequence))
    return fid


def _lier_objectif_exo(conn, objectif_id, exercice_id, serie_code, ordre):
    conn.execute("""INSERT INTO objectif_exos
        (objectif_id, serie, exercice_id, ordre)
        VALUES (?, ?, ?, ?)""",
        (objectif_id, serie_code, exercice_id, ordre))


def _lister_cibles_factice(conn, doc_id, ref_id, type_doc):
    return []


# ── Schema version + structure top-level ───────────────────────────────────


def test_version_schema_est_2(sqlite_store):
    """v0.15.2.11 — bump à 2 (structure profondément remaniée)."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    assert trace['version_schema'] == 2
    assert VERSION_SCHEMA_TRACE == 2


def test_trace_sequences_n_a_plus_objectifs_au_niveau_sequence(sqlite_store):
    """Les `objectifs` ne sont plus au niveau séquence — ils sont
    désormais SOUS chaque `partie`."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _seq_referentiel(conn, rid, 'S01', 1)
        sn = _seq_par_niveau(conn, 'N11', 'S01')
        _partie(conn, sn, 1)
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    seq = trace['sequences'][0]
    assert 'objectifs' not in seq
    assert 'atomes_utilises' not in seq  # supprimée en v2


def test_trace_sequences_n_a_plus_atomes_utilises(sqlite_store):
    """La section `atomes_utilises` au niveau séquence est supprimée
    en v2 (les atomes sont sous les objectifs ou la partie)."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _seq_referentiel(conn, rid, 'S01', 1)
        sn = _seq_par_niveau(conn, 'N11', 'S01')
        _partie(conn, sn, 1)
        # Atome présent en BDD active
        _notion(conn, 'N11', 'S01', 1, 'Une notion')
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    assert 'atomes_utilises' not in trace['sequences'][0]


# ── Structure des parties ──────────────────────────────────────────────────


def test_partie_contient_les_champs_attendus(sqlite_store):
    """Chaque partie a : numero, nb_seances_R_AE, cartes_automatisme,
    exercices_R, exercices_AE, objectifs."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _seq_referentiel(conn, rid, 'S01', 1)
        sn = _seq_par_niveau(conn, 'N11', 'S01')
        _partie(conn, sn, 1, nb_seances=1.5)
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    p = trace['sequences'][0]['parties'][0]
    assert p['numero'] == 1
    assert p['nb_seances_R_AE'] == 1.5
    assert isinstance(p['cartes_automatisme'], list)
    assert isinstance(p['exercices_R'],         list)
    assert isinstance(p['exercices_AE'],        list)
    assert isinstance(p['objectifs'],           list)


def test_partie_revisions_listees_via_partie_exos_revision_approche(
        sqlite_store):
    """Les exercices de révision (type='R') alimentent `exercices_R`."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _seq_referentiel(conn, rid, 'S01', 1)
        sn = _seq_par_niveau(conn, 'N11', 'S01')
        pid = _partie(conn, sn, 1)
        # Un exo de révision pointant vers N10/S01/A/2
        eid = _exo(conn, 'N10', 'S01', 2, 'A', 'avancé', 'Exo revision')
        conn.execute("""INSERT INTO partie_exos_revision_approche
            (partie_id, type, exercice_id, ordre,
             origin_niveau, origin_seq, origin_serie, origin_num)
            VALUES (?, 'R', ?, 1, 'N10', 'S01', 'A', 2)""",
            (pid, eid))
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    p = trace['sequences'][0]['parties'][0]
    assert len(p['exercices_R']) == 1
    rev = p['exercices_R'][0]
    assert rev['niveau']   == 'N10'
    assert rev['sequence'] == 'S01'
    assert rev['num']      == 2
    assert rev['serie']    == 'avancé'   # traduit depuis 'A'
    assert rev['titre']    == 'Exo revision'


def test_partie_exos_approche_listes_via_type_EA(sqlite_store):
    """Les exos d'approche (type='EA') vont dans `exercices_AE`."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _seq_referentiel(conn, rid, 'S01', 1)
        sn = _seq_par_niveau(conn, 'N11', 'S01')
        pid = _partie(conn, sn, 1)
        eid = _exo(conn, 'N11', 'S01', 1, 'F', 'fondamental')
        conn.execute("""INSERT INTO partie_exos_revision_approche
            (partie_id, type, exercice_id, ordre,
             origin_niveau, origin_seq, origin_serie, origin_num)
            VALUES (?, 'EA', ?, 1, 'N11', 'S01', 'F', 1)""",
            (pid, eid))
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    p = trace['sequences'][0]['parties'][0]
    assert len(p['exercices_AE']) == 1
    assert p['exercices_AE'][0]['serie'] == 'fondamental'


# ── Structure des objectifs ────────────────────────────────────────────────


def test_objectif_cours_porte_fiches_de_la_partie_pas_atomes(sqlite_store):
    """v0.15.2.12 — L'objectif Cours (codes 01/11/21) porte UNIQUEMENT
    les fiches_resume de la partie (agrégées de tous ses objectifs
    ordinaires). Pas de methodes/notions/exercices.

    Inversement, les objectifs ordinaires n'ont PAS de section
    fiches_resume.
    """
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _seq_referentiel(conn, rid, 'S01', 1)
        sn = _seq_par_niveau(conn, 'N11', 'S01')
        pid1 = _partie(conn, sn, 1)
        pid2 = _partie(conn, sn, 2)
        # Objectif cours partie 1
        o_cours1 = _objectif(conn, pid1, '01', 'Connaître (1ère partie)',
                             fin_cycle=1)
        # Objectif ordinaire partie 1 avec une fiche liée
        o_ord1 = _objectif(conn, pid1, '02', 'Ordinaire 02')
        _fiche(conn, 'N11', 'S01', num=1,
                titre='Fiche 1', objectif_id=o_ord1)
        # Objectif cours partie 2
        o_cours2 = _objectif(conn, pid2, '11', 'Connaître (2nde partie)',
                             fin_cycle=1)
        # Objectif ordinaire partie 2 avec deux fiches liées
        o_ord2 = _objectif(conn, pid2, '12', 'Ordinaire 12')
        _fiche(conn, 'N11', 'S01', num=4,
                titre='Fiche 4', objectif_id=o_ord2)
        _fiche(conn, 'N11', 'S01', num=5,
                titre='Fiche 5', objectif_id=o_ord2)
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)

    parties = trace['sequences'][0]['parties']
    p1, p2 = parties[0], parties[1]
    cours1 = next(o for o in p1['objectifs'] if o['code'] == '01')
    ord1   = next(o for o in p1['objectifs'] if o['code'] == '02')
    cours2 = next(o for o in p2['objectifs'] if o['code'] == '11')
    ord2   = next(o for o in p2['objectifs'] if o['code'] == '12')

    # Objectif Cours : porte fiches_resume agrégées de la partie,
    # PAS methodes/notions/exercices.
    for cours in (cours1, cours2):
        assert 'methodes'  not in cours
        assert 'notions'   not in cours
        assert 'exercices' not in cours
        assert 'fiches_resume' in cours

    assert len(cours1['fiches_resume']) == 1
    assert cours1['fiches_resume'][0]['num_fiche'] == 1
    assert len(cours2['fiches_resume']) == 2
    assert [f['num_fiche'] for f in cours2['fiches_resume']] == [4, 5]

    # Objectifs ordinaires : pas de fiches_resume.
    for ordinaire in (ord1, ord2):
        assert 'methodes'  in ordinaire
        assert 'notions'   in ordinaire
        assert 'exercices' in ordinaire
        assert 'fiches_resume' not in ordinaire


def test_objectif_ordinaire_a_methode_liee(sqlite_store):
    """Un objectif "ordinaire" (02, 03, …) avec methode_id porte sa
    méthode liée dans la section `methodes` (cardinalité 1)."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _seq_referentiel(conn, rid, 'S01', 1)
        sn = _seq_par_niveau(conn, 'N11', 'S01')
        pid1 = _partie(conn, sn, 1)
        mid = _methode(conn, 'N11', 'S01', 1, 'Méthode 1')
        _objectif(conn, pid1, '02', 'Objectif 02', methode_id=mid)
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    obj02 = trace['sequences'][0]['parties'][0]['objectifs'][0]
    assert len(obj02['methodes']) == 1
    assert obj02['methodes'][0]['num_methode'] == 1
    assert obj02['methodes'][0]['titre'] == 'Méthode 1'


def test_objectif_ordinaire_sans_methode_a_section_vide(sqlite_store):
    """Si methode_id est NULL, `methodes` est une liste vide."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _seq_referentiel(conn, rid, 'S01', 1)
        sn = _seq_par_niveau(conn, 'N11', 'S01')
        pid1 = _partie(conn, sn, 1)
        _objectif(conn, pid1, '02', 'Sans méthode', methode_id=None)
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    obj02 = trace['sequences'][0]['parties'][0]['objectifs'][0]
    assert obj02['methodes'] == []


def test_objectif_ordinaire_a_exercices_lies_via_objectif_exos(
        sqlite_store):
    """Exercices liés via `objectif_exos`. La série provient de
    `objectif_exos.serie` (codes F/A/E) traduite en label."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _seq_referentiel(conn, rid, 'S01', 1)
        sn = _seq_par_niveau(conn, 'N11', 'S01')
        pid1 = _partie(conn, sn, 1)
        oid = _objectif(conn, pid1, '02', 'Test')
        e1 = _exo(conn, 'N11', 'S01', 1, 'F', 'fondamental', 'Exo F1')
        e2 = _exo(conn, 'N11', 'S01', 1, 'A', 'avancé',      'Exo A1')
        _lier_objectif_exo(conn, oid, e1, 'F', 1)
        _lier_objectif_exo(conn, oid, e2, 'A', 2)
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    obj = trace['sequences'][0]['parties'][0]['objectifs'][0]
    assert len(obj['exercices']) == 2
    series = [e['serie'] for e in obj['exercices']]
    assert 'fondamental' in series
    assert 'avancé'      in series


def test_objectif_ordinaire_n_a_pas_section_fiches_resume(sqlite_store):
    """v0.15.2.12 — Les objectifs ordinaires NE PORTENT PAS de section
    `fiches_resume`. Les fiches sont émises sous l'objectif Cours de
    la partie (cf. test_objectif_cours_porte_fiches_de_la_partie…)."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _seq_referentiel(conn, rid, 'S01', 1)
        sn = _seq_par_niveau(conn, 'N11', 'S01')
        pid1 = _partie(conn, sn, 1)
        oid = _objectif(conn, pid1, '02', 'Test')
        _fiche(conn, 'N11', 'S01', num=1, titre='Fiche 1', objectif_id=oid)
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    obj = next(o for o in trace['sequences'][0]['parties'][0]['objectifs']
               if o['code'] == '02')
    assert 'fiches_resume' not in obj
    # En revanche, les autres sections atomes sont présentes
    assert 'methodes'  in obj
    assert 'exercices' in obj
    assert 'notions'   in obj


# ── Traduction des codes série ─────────────────────────────────────────────


def test_serie_label_traduction():
    """Codes BDD F/A/E → labels métier fondamental/avancé/exploration."""
    assert _serie_label('F') == 'fondamental'
    assert _serie_label('A') == 'avancé'
    assert _serie_label('E') == 'exploration'
    # Tolérance : labels déjà conformes passent identiques
    assert _serie_label('fondamental') == 'fondamental'
    assert _serie_label('avancé')      == 'avancé'
    # None reste None
    assert _serie_label(None) is None


# ── Test bout-en-bout sur N11/S01 si BDD de référence présente ─────────────


def test_n11_s01_a_structure_riche_si_bdd_de_reference(sqlite_store):
    """Smoke test sur la BDD de référence (la fixture sqlite_store
    devrait inclure N11_v2025 si la BDD principale est utilisée).
    Skip si N11_v2025 absent.
    """
    with _conn(sqlite_store) as conn:
        row = conn.execute(
            "SELECT id FROM referentiel_niveaux WHERE id='N11_v2025'"
        ).fetchone()
        if not row:
            pytest.skip("N11_v2025 absent de la BDD test")
        trace = generer_trace(conn, 'N11_v2025', _lister_cibles_factice)
    # 14 séquences attendues
    assert len(trace['sequences']) == 14
    # S01 doit avoir 2 parties
    s01 = next(s for s in trace['sequences'] if s['code'] == 'S01')
    assert len(s01['parties']) == 2
    # Partie 1 doit avoir des objectifs 01, 02, 03, 04 …
    codes_p1 = [o['code'] for o in s01['parties'][0]['objectifs']]
    assert '01' in codes_p1
    assert '02' in codes_p1
    # L'objectif Cours (01) porte les fiches_resume aggregées de la partie.
    obj01 = next(o for o in s01['parties'][0]['objectifs']
                 if o['code'] == '01')
    assert 'fiches_resume' in obj01
    assert len(obj01['fiches_resume']) >= 1  # plusieurs fiches dans partie 1
    # L'objectif ordinaire 02 doit avoir méthode + exos, mais PAS de
    # section fiches_resume (cf. v0.15.2.12).
    obj02 = next(o for o in s01['parties'][0]['objectifs']
                 if o['code'] == '02')
    assert len(obj02['methodes'])  >= 1
    assert len(obj02['exercices']) >= 1
    assert 'fiches_resume' not in obj02
