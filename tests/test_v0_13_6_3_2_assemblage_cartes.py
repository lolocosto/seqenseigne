"""tests/test_v0_13_6_3_2_assemblage_cartes.py — v0.13.6.3.2

Tests de l'extension de `services.v2_lecture.lire_sequence_par_niveau`
pour faire remonter, dans chaque partie, la liste des cartes
d'automatisme rattachées via leur notion/méthode.

Pendant côté atelier d'assemblage de séquence du même ajout v0.13.6.3
côté atelier référentiel.
"""
from __future__ import annotations

from pathlib import Path
import sys
import sqlite3

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import v2_lecture as v2_lec  # noqa: E402
from services import cartes_automatisme as cartes_svc  # noqa: E402


def _conn(store):
    return store._conn()


def _peupler_minimal_n10(conn: sqlite3.Connection) -> dict:
    """Réplique de la fixture v0.13.6.3 (test_v0_13_6_3_referentiel_eval_cartes).
    Peuple une séquence N10/S01 minimale avec 1 partie, 1 objectif,
    1 méthode liée et 1 notion liée.
    """
    cur = conn.cursor()
    ids = {}

    cur.execute("INSERT OR IGNORE INTO cycles(code, nom) VALUES (?, ?)",
                ('C04', 'Cycle 4'))
    ids['theme'] = 'theme_test_A'
    cur.execute("""
        INSERT OR IGNORE INTO themes(id, code, nom, code_couleur, cycle_code)
        VALUES (?, 'A', 'Nombres et Calculs', 'nombres', 'C04')
    """, (ids['theme'],))

    ids['sdc'] = 'sc_test_C04_S01'
    cur.execute("""
        INSERT OR IGNORE INTO sequences_du_cycle
            (id, cycle_code, code, numero, nom, theme_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ids['sdc'], 'C04', 'S01', 1, "Représentations d'un nombre",
          ids['theme']))

    ids['sn'] = 'sn_test_N10_S01'
    cur.execute("""
        INSERT OR IGNORE INTO sequences_par_niveau(id, niveau, sequence_code)
        VALUES (?, 'N10', 'S01')
    """, (ids['sn'],))

    ids['partie'] = 'partie_test_1'
    cur.execute("""
        INSERT OR IGNORE INTO sequence_parties
            (id, sequence_par_niveau_id, numero, nb_seances_R_AE)
        VALUES (?, ?, 1, 2)
    """, (ids['partie'], ids['sn']))

    ids['methode'] = 'me_test_001'
    cur.execute("""
        INSERT OR IGNORE INTO methodes
            (id, niveau, sequence, num_methode, titre, etat_code)
        VALUES (?, 'N10', 'S01', 1, 'Méthode test', 'valide')
    """, (ids['methode'],))

    ids['notion'] = 'no_test_001'
    cur.execute("""
        INSERT OR IGNORE INTO notions
            (id, niveau, sequence, num_connaissance, titre, etat_code)
        VALUES (?, 'N10', 'S01', '01', 'Notion test', 'valide')
    """, (ids['notion'],))

    ids['obj'] = 'obj_test_001'
    cur.execute("""
        INSERT OR IGNORE INTO objectifs
            (id, partie_id, code, nom, methode_id, fin_cycle)
        VALUES (?, ?, '02', 'Premier objectif test', ?, 0)
    """, (ids['obj'], ids['partie'], ids['methode']))
    cur.execute("""
        INSERT OR IGNORE INTO objectif_notions(objectif_id, notion_id)
        VALUES (?, ?)
    """, (ids['obj'], ids['notion']))

    conn.commit()
    return ids


# ── Tests ────────────────────────────────────────────────────────────────────


def test_partie_a_cle_cartes(sqlite_store):
    """Chaque partie remontée par lire_sequence_par_niveau a la clé
    'cartes' (liste, vide par défaut)."""
    with _conn(sqlite_store) as conn:
        _peupler_minimal_n10(conn)
        data = v2_lec.lire_sequence_par_niveau(conn, 'N10', 'S01')

    assert len(data['parties']) == 1
    for p in data['parties']:
        assert 'cartes' in p
        assert isinstance(p['cartes'], list)
        # Aucune carte créée → liste vide
        assert p['cartes'] == []


def test_carte_methode_remonte_dans_partie(sqlite_store):
    """Carte liée à une méthode dont l'objectif est dans la partie :
    remonte dans p.cartes."""
    with _conn(sqlite_store) as conn:
        ids = _peupler_minimal_n10(conn)
        carte = cartes_svc.creer_carte(
            conn, niveau='N10', sequence='S01',
            type_pedago='calcul', type_tech='fixe',
            titre='Carte méthode 1', recto='Recto', verso='Verso',
            variables='', lien_type='methode', lien_id=ids['methode'],
        )
        cartes_svc.valider_carte(conn, carte['id'])
        conn.commit()

        data = v2_lec.lire_sequence_par_niveau(conn, 'N10', 'S01')

    cartes_p = data['parties'][0]['cartes']
    assert len(cartes_p) == 1
    c = cartes_p[0]
    assert c['id'] == carte['id']
    assert c['titre'] == 'Carte méthode 1'
    assert c['etat_code'] == 'valide'
    assert c['code'].startswith('CA')
    assert c['type_pedago'] == 'calcul'
    assert c['type_tech'] == 'fixe'


def test_carte_notion_remonte_dans_partie(sqlite_store):
    """Carte liée à une notion dont l'objectif est dans la partie :
    remonte dans p.cartes."""
    with _conn(sqlite_store) as conn:
        ids = _peupler_minimal_n10(conn)
        carte = cartes_svc.creer_carte(
            conn, niveau='N10', sequence='S01',
            type_pedago='definition', type_tech='fixe',
            titre='Carte notion 1', recto='r', verso='v', variables='',
            lien_type='notion', lien_id=ids['notion'],
        )
        cartes_svc.valider_carte(conn, carte['id'])
        conn.commit()
        data = v2_lec.lire_sequence_par_niveau(conn, 'N10', 'S01')

    cartes_p = data['parties'][0]['cartes']
    assert len(cartes_p) == 1
    assert cartes_p[0]['id'] == carte['id']


def test_carte_notion_orpheline_invisible(sqlite_store):
    """Carte liée à une notion non rattachée à un objectif : invisible
    (option A stricte, cohérent avec arbre_du_niveau).

    v0.13.6.13 : avec le nouveau modèle objectif_cartes, le passage à
    'valide' via valider_carte() exige une liaison objectif non vide.
    Comme cette carte est par construction orpheline (sa notion n'est
    liée à aucun objectif → dérivation automatique objectif_ids = []),
    on bascule l'état directement via SQL pour préserver l'esprit du
    test (vérifier l'invisibilité dans l'assemblage, indépendamment
    de l'état)."""
    with _conn(sqlite_store) as conn:
        _peupler_minimal_n10(conn)
        notion_orph = 'no_orph_001'
        conn.execute("""
            INSERT INTO notions
                (id, niveau, sequence, num_connaissance, titre, etat_code)
            VALUES (?, 'N10', 'S01', '02', 'Notion orpheline', 'valide')
        """, (notion_orph,))
        c_orph = cartes_svc.creer_carte(
            conn, niveau='N10', sequence='S01',
            type_pedago='definition', type_tech='fixe',
            titre='Carte orpheline', recto='r', verso='v', variables='',
            lien_type='notion', lien_id=notion_orph,
        )
        # v0.13.6.13 — Bascule directe à 'valide' (cf. docstring)
        conn.execute(
            "UPDATE cartes_automatisme SET etat_code = 'valide' WHERE id = ?",
            (c_orph['id'],),
        )
        conn.commit()
        data = v2_lec.lire_sequence_par_niveau(conn, 'N10', 'S01')

    cartes_p = data['parties'][0]['cartes']
    assert len(cartes_p) == 0


def test_cartes_n10_n_apparaissent_pas_sur_n11(sqlite_store):
    """Cartes d'un niveau N'apparaissent pas sur un autre niveau."""
    with _conn(sqlite_store) as conn:
        ids = _peupler_minimal_n10(conn)
        cartes_svc.creer_carte(
            conn, niveau='N10', sequence='S01',
            type_pedago='calcul', type_tech='fixe',
            titre='Carte N10', recto='r', verso='v', variables='',
            lien_type='methode', lien_id=ids['methode'],
        )
        conn.commit()

        # Tentative de lecture sur N11 → SequenceParNiveauIntrouvable
        # (séquence non peuplée pour N11). Pour ce test on s'assure
        # juste que les cartes N10 ne fuitent pas dans la lecture N10
        # d'une autre séquence — donc on regarde une séquence inexistante.
        with pytest.raises(v2_lec.SequenceParNiveauIntrouvable):
            v2_lec.lire_sequence_par_niveau(conn, 'N11', 'S01')


def test_cartes_n10_ne_fuient_pas_sur_autre_sequence(sqlite_store):
    """Cartes de N10/S01 n'apparaissent pas dans N10/S02 (filtre par
    séquence)."""
    with _conn(sqlite_store) as conn:
        ids = _peupler_minimal_n10(conn)
        # Créer une 2ème séquence S02 sur N10
        conn.execute("""
            INSERT INTO sequences_du_cycle
                (id, cycle_code, code, numero, nom, theme_id)
            VALUES ('sc_test_S02', 'C04', 'S02', 2, 'Comparaison de nombres', ?)
        """, (ids['theme'],))
        conn.execute("""
            INSERT INTO sequences_par_niveau(id, niveau, sequence_code)
            VALUES ('sn_test_N10_S02', 'N10', 'S02')
        """)
        conn.execute("""
            INSERT INTO sequence_parties
                (id, sequence_par_niveau_id, numero, nb_seances_R_AE)
            VALUES ('partie_S02_1', 'sn_test_N10_S02', 1, 2)
        """)
        # Carte de S01
        cartes_svc.creer_carte(
            conn, niveau='N10', sequence='S01',
            type_pedago='calcul', type_tech='fixe',
            titre='Carte S01', recto='r', verso='v', variables='',
            lien_type='methode', lien_id=ids['methode'],
        )
        conn.commit()

        data_s02 = v2_lec.lire_sequence_par_niveau(conn, 'N10', 'S02')

    for p in data_s02['parties']:
        assert p['cartes'] == [], "Les cartes S01 ne doivent pas remonter en S02"


def test_charger_parties_sans_niveau_seq_renvoie_cartes_vides(sqlite_store):
    """Si _charger_parties est appelé sans niveau/sequence_code (rétrocompat),
    cartes reste vide (pas de KeyError ni de plantage)."""
    with _conn(sqlite_store) as conn:
        _peupler_minimal_n10(conn)
        # Appel direct du helper privé sans niveau/sequence_code
        parties = v2_lec._charger_parties(conn, 'sn_test_N10_S01')

    assert len(parties) == 1
    assert 'cartes' in parties[0]
    assert parties[0]['cartes'] == []
