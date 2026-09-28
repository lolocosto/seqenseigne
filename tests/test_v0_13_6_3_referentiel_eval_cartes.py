"""tests/test_v0_13_6_3_referentiel_eval_cartes.py — v0.13.6.3

Tests de l'extension de `services.referentiels.arbre_du_niveau` pour
faire remonter dans l'arbre :

  1. Les évaluations rattachées au niveau (avec leurs exos),
     au top-level de la structure retournée.
  2. Les cartes d'automatisme rattachées à chaque partie de séquence,
     via la chaîne carte → notion/méthode → objectif → partie.

Ces deux ajouts servent à enrichir le rendu de l'atelier Référentiel
côté UI ; côté service, c'est de l'agrégation pure (pas de mutation
de BDD).
"""
from __future__ import annotations

from pathlib import Path
import sys
import sqlite3
import uuid

import pytest

# Insertion du path pour pouvoir importer services
sys.path.insert(0, str(Path(__file__).parent.parent))

from services import referentiels as svc
from services import cartes_automatisme as cartes_svc


# ── Helpers : construction d'une BDD de test riche ──────────────────────────


def _conn(store):
    """Récupère le context manager de connexion du store."""
    return store._conn()


def _peupler_minimal_n10(conn: sqlite3.Connection) -> dict:
    """Peuple une BDD vierge avec le minimum pour tester arbre_du_niveau
    sur N10/S01 :
      - séquence S01 du cycle C04
      - sequences_par_niveau pour N10/S01
      - 1 partie avec 1 objectif
      - 1 méthode liée à cet objectif
      - 1 notion liée à cet objectif
      - 1 exercice rattaché à l'objectif (série F)

    Retourne un dict d'IDs utiles pour les tests qui veulent ajouter
    des cartes ou évaluations ensuite.
    """
    cur = conn.cursor()
    ids = {}

    # 1. Cycle (param_niveaux est déjà peuplé par la fixture, ce qui
    # alimente cycles via auto-amorçage). On utilise C04 qui est censé
    # exister.
    cur.execute("INSERT OR IGNORE INTO cycles(code, nom) VALUES (?, ?)",
                ('C04', 'Cycle 4'))

    # 2. Thème (id obligatoire = PRIMARY KEY ; cycle_code NOT NULL FK)
    ids['theme'] = 'theme_test_A'
    cur.execute("""
        INSERT OR IGNORE INTO themes(id, code, nom, code_couleur, cycle_code)
        VALUES (?, 'A', 'Nombres et Calculs', 'nombres', 'C04')
    """, (ids['theme'],))

    # 3. Séquence S01 dans le cycle C04 (id obligatoire = PRIMARY KEY)
    ids['sdc'] = 'sc_test_C04_S01'
    cur.execute("""
        INSERT OR IGNORE INTO sequences_du_cycle
            (id, cycle_code, code, numero, nom, theme_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ids['sdc'], 'C04', 'S01', 1, "Représentations d'un nombre",
          ids['theme']))

    # 4. Séquence par niveau (rattachement N10/S01)
    ids['sn'] = 'sn_test_N10_S01'
    cur.execute("""
        INSERT OR IGNORE INTO sequences_par_niveau(id, niveau, sequence_code)
        VALUES (?, 'N10', 'S01')
    """, (ids['sn'],))

    # 5. Partie de séquence
    ids['partie'] = 'partie_test_1'
    cur.execute("""
        INSERT OR IGNORE INTO sequence_parties
            (id, sequence_par_niveau_id, numero, nb_seances_R_AE)
        VALUES (?, ?, 1, 2)
    """, (ids['partie'], ids['sn']))

    # 6. Méthode + notion (atomes de la séquence)
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

    # 7. Objectif lié à la méthode (1-1) + à la notion (N-N)
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

    # 8. Un exercice F01 rattaché à cet objectif (utilisé pour les évals)
    # Note : serie + serie_code sont deux colonnes distinctes (NOT NULL),
    # historiques du modèle exercices.
    ids['exo'] = 'ex_test_F01'
    cur.execute("""
        INSERT OR IGNORE INTO exercices
            (id, serie, serie_code, niveau, sequence, num, titre, etat_code)
        VALUES (?, 'F', 'F', 'N10', 'S01', 1, 'Exo test F01', 'valide')
    """, (ids['exo'],))
    cur.execute("""
        INSERT OR IGNORE INTO objectif_exos
            (objectif_id, exercice_id, serie, ordre)
        VALUES (?, ?, 'F', 1)
    """, (ids['obj'], ids['exo']))

    conn.commit()
    return ids


# ── 1) Tests de la nouvelle clé top-level "evaluations" ──────────────────────


def test_arbre_a_cle_evaluations(sqlite_store):
    """L'arbre retourne toujours la clé 'evaluations' (liste, éventuellement
    vide)."""
    with _conn(sqlite_store) as conn:
        arbre = svc.arbre_du_niveau(conn, 'N10')
    assert 'evaluations' in arbre
    assert isinstance(arbre['evaluations'], list)


def test_evaluations_vide_si_aucune(sqlite_store):
    """Niveau sans évaluation : liste vide, pas une erreur."""
    with _conn(sqlite_store) as conn:
        arbre = svc.arbre_du_niveau(conn, 'N10')
    assert arbre['evaluations'] == []


def test_evaluations_remonte_avec_exos(sqlite_store):
    """Une évaluation avec 2 exos rattachés remonte avec sa structure
    complète (id, titre, exos[] avec code court, état, nav_niveau)."""
    with _conn(sqlite_store) as conn:
        ids = _peupler_minimal_n10(conn)
        # Créer un 2e exo (A01)
        ex2 = 'ex_test_A01'
        conn.execute("""
            INSERT INTO exercices
                (id, serie, serie_code, niveau, sequence, num, titre, etat_code)
            VALUES (?, 'A', 'A', 'N10', 'S01', 1, 'Exo test A01', 'en_cours')
        """, (ex2,))

        # Une éval avec les 2 exos
        eval_id = 'eval_test_001'
        conn.execute("""
            INSERT INTO evaluations
                (id, niveau, numero, ordre, titre, etat_code)
            VALUES (?, 'N10', 1, 1, 'Évaluation test', 'valide')
        """, (eval_id,))
        conn.execute("""
            INSERT INTO evaluation_exercices
                (evaluation_id, exercice_id, ordre, bareme_points)
            VALUES (?, ?, 1, 4)
        """, (eval_id, ids['exo']))
        conn.execute("""
            INSERT INTO evaluation_exercices
                (evaluation_id, exercice_id, ordre, bareme_points)
            VALUES (?, ?, 2, 4)
        """, (eval_id, ex2))
        conn.commit()

        arbre = svc.arbre_du_niveau(conn, 'N10')

    assert len(arbre['evaluations']) == 1
    ev = arbre['evaluations'][0]
    assert ev['id'] == 'eval_test_001'
    assert ev['titre'] == 'Évaluation test'
    assert ev['etat_code'] == 'valide'
    assert ev['numero'] == 1
    # Les exos remontent dans l'ordre
    assert len(ev['exos']) == 2
    codes = [e['code'] for e in ev['exos']]
    assert codes == ['F01', 'A01']
    # Le champ etat_code est propagé
    etats = {e['code']: e['etat_code'] for e in ev['exos']}
    assert etats['F01'] == 'valide'
    assert etats['A01'] == 'en_cours'
    # nav_niveau / nav_seq sont posés
    for e in ev['exos']:
        assert e['nav_niveau'] == 'N10'
        assert e['nav_seq'] == 'S01'
        assert e['type'] == 'exo'


def test_evaluations_isolees_par_niveau(sqlite_store):
    """Une éval N10 ne doit pas remonter dans l'arbre N11."""
    with _conn(sqlite_store) as conn:
        _peupler_minimal_n10(conn)
        conn.execute("""
            INSERT INTO evaluations
                (id, niveau, numero, ordre, titre, etat_code)
            VALUES ('eval_n10', 'N10', 1, 1, 'Éval N10', 'valide')
        """)
        conn.commit()

        arbre_n11 = svc.arbre_du_niveau(conn, 'N11')

    assert arbre_n11['evaluations'] == []


def test_evaluations_stats_comptent_les_exos(sqlite_store):
    """Les exos d'une éval entrent dans les stats globales (total/valides)."""
    with _conn(sqlite_store) as conn:
        ids = _peupler_minimal_n10(conn)
        total_avant = svc.arbre_du_niveau(conn, 'N10')['stats']['total']

        eval_id = 'eval_compte'
        conn.execute("""
            INSERT INTO evaluations
                (id, niveau, numero, ordre, titre, etat_code)
            VALUES (?, 'N10', 1, 1, 'Éval', 'valide')
        """, (eval_id,))
        conn.execute("""
            INSERT INTO evaluation_exercices
                (evaluation_id, exercice_id, ordre, bareme_points)
            VALUES (?, ?, 1, 4)
        """, (eval_id, ids['exo']))
        conn.commit()

        arbre_apres = svc.arbre_du_niveau(conn, 'N10')

    # 1 exo d'éval ajouté → total +1
    assert arbre_apres['stats']['total'] == total_avant + 1
    # L'exo est 'valide' → valides +1
    assert arbre_apres['stats']['valides'] >= 1


# ── 2) Tests de la nouvelle clé "atomes_cartes" sur chaque partie ───────────


def test_partie_a_cle_atomes_cartes(sqlite_store):
    """Chaque partie a une clé 'atomes_cartes' (liste, éventuellement vide)."""
    with _conn(sqlite_store) as conn:
        _peupler_minimal_n10(conn)
        arbre = svc.arbre_du_niveau(conn, 'N10')

    assert len(arbre['sequences']) == 1
    for s in arbre['sequences']:
        for p in s['parties']:
            assert 'atomes_cartes' in p
            assert isinstance(p['atomes_cartes'], list)


def test_carte_methode_remonte_dans_partie(sqlite_store):
    """Une carte liée à une méthode (qui est dans un objectif d'une partie)
    apparaît dans atomes_cartes de cette partie."""
    with _conn(sqlite_store) as conn:
        ids = _peupler_minimal_n10(conn)
        # Créer une carte qui pointe vers la méthode
        carte = cartes_svc.creer_carte(
            conn,
            niveau='N10', sequence='S01',
            type_pedago='calcul', type_tech='fixe',
            titre='Carte méthode 1',
            recto='Recto test', verso='Verso test', variables='',
            lien_type='methode', lien_id=ids['methode'],
        )
        cartes_svc.valider_carte(conn, carte['id'])
        conn.commit()

        arbre = svc.arbre_du_niveau(conn, 'N10')

    partie = arbre['sequences'][0]['parties'][0]
    cartes_partie = partie['atomes_cartes']
    assert len(cartes_partie) == 1
    c = cartes_partie[0]
    assert c['id'] == carte['id']
    assert c['type'] == 'carte'
    assert c['titre'] == 'Carte méthode 1'
    assert c['etat_code'] == 'valide'
    assert c['code'].startswith('CA')
    assert c['nav_niveau'] == 'N10'
    assert c['nav_seq'] == 'S01'


def test_carte_notion_remonte_dans_partie(sqlite_store):
    """Carte liée à une notion (via objectif_notions → objectif → partie)
    apparaît également."""
    with _conn(sqlite_store) as conn:
        ids = _peupler_minimal_n10(conn)
        carte = cartes_svc.creer_carte(
            conn,
            niveau='N10', sequence='S01',
            type_pedago='definition', type_tech='fixe',
            titre='Carte notion 1',
            recto='Recto', verso='Verso', variables='',
            lien_type='notion', lien_id=ids['notion'],
        )
        cartes_svc.valider_carte(conn, carte['id'])
        conn.commit()

        arbre = svc.arbre_du_niveau(conn, 'N10')

    partie = arbre['sequences'][0]['parties'][0]
    cartes_partie = partie['atomes_cartes']
    assert len(cartes_partie) == 1
    assert cartes_partie[0]['id'] == carte['id']


def test_carte_notion_non_rattachee_invisible(sqlite_store):
    """Carte liée à une notion qui n'est rattachée à AUCUN objectif :
    invisible dans l'arbre (comportement strict option A décidé en session)."""
    with _conn(sqlite_store) as conn:
        ids = _peupler_minimal_n10(conn)
        # Notion orpheline : pas dans objectif_notions
        notion_orph = 'no_orph_001'
        conn.execute("""
            INSERT INTO notions
                (id, niveau, sequence, num_connaissance, titre, etat_code)
            VALUES (?, 'N10', 'S01', '02', 'Notion orpheline', 'valide')
        """, (notion_orph,))
        carte_orph = cartes_svc.creer_carte(
            conn,
            niveau='N10', sequence='S01',
            type_pedago='definition', type_tech='fixe',
            titre='Carte orpheline',
            recto='Recto', verso='Verso', variables='',
            lien_type='notion', lien_id=notion_orph,
        )
        # v0.13.6.13 — Bascule directe à 'valide' (la validation via
        # valider_carte échoue désormais car la carte est orpheline en
        # objectif_cartes ; le test vérifie l'invisibilité dans l'arbre,
        # indépendamment de l'état).
        conn.execute(
            "UPDATE cartes_automatisme SET etat_code = 'valide' WHERE id = ?",
            (carte_orph['id'],),
        )
        conn.commit()

        arbre = svc.arbre_du_niveau(conn, 'N10')

    partie = arbre['sequences'][0]['parties'][0]
    # 0 carte dans la partie (la notion n'est pas attachée à un objectif)
    cartes_partie = partie['atomes_cartes']
    assert len(cartes_partie) == 0


def test_carte_cumul_methode_et_notion_pas_doublon(sqlite_store):
    """Si deux cartes différentes pointent l'une vers la méthode et
    l'autre vers la notion de la même partie, on en voit 2 (pas de
    déduplication entre deux IDs distincts)."""
    with _conn(sqlite_store) as conn:
        ids = _peupler_minimal_n10(conn)
        c1 = cartes_svc.creer_carte(
            conn, niveau='N10', sequence='S01',
            type_pedago='calcul', type_tech='fixe',
            titre='Carte méthode', recto='r', verso='v', variables='',
            lien_type='methode', lien_id=ids['methode'],
        )
        c2 = cartes_svc.creer_carte(
            conn, niveau='N10', sequence='S01',
            type_pedago='definition', type_tech='fixe',
            titre='Carte notion', recto='r', verso='v', variables='',
            lien_type='notion', lien_id=ids['notion'],
        )
        cartes_svc.valider_carte(conn, c1['id'])
        cartes_svc.valider_carte(conn, c2['id'])
        conn.commit()

        arbre = svc.arbre_du_niveau(conn, 'N10')

    cartes_partie = arbre['sequences'][0]['parties'][0]['atomes_cartes']
    assert len(cartes_partie) == 2
    ids_partie = {c['id'] for c in cartes_partie}
    assert ids_partie == {c1['id'], c2['id']}


def test_cartes_stats_comptent(sqlite_store):
    """Les cartes rattachées à une partie entrent dans les stats globales."""
    with _conn(sqlite_store) as conn:
        ids = _peupler_minimal_n10(conn)
        total_avant = svc.arbre_du_niveau(conn, 'N10')['stats']['total']

        carte = cartes_svc.creer_carte(
            conn, niveau='N10', sequence='S01',
            type_pedago='calcul', type_tech='fixe',
            titre='C', recto='r', verso='v', variables='',
            lien_type='methode', lien_id=ids['methode'],
        )
        cartes_svc.valider_carte(conn, carte['id'])
        conn.commit()

        arbre = svc.arbre_du_niveau(conn, 'N10')

    assert arbre['stats']['total'] == total_avant + 1


def test_cartes_isolees_par_niveau(sqlite_store):
    """Les cartes d'un niveau ne fuitent pas vers un autre niveau."""
    with _conn(sqlite_store) as conn:
        ids = _peupler_minimal_n10(conn)
        cartes_svc.creer_carte(
            conn, niveau='N10', sequence='S01',
            type_pedago='calcul', type_tech='fixe',
            titre='C', recto='r', verso='v', variables='',
            lien_type='methode', lien_id=ids['methode'],
        )
        conn.commit()
        arbre_n11 = svc.arbre_du_niveau(conn, 'N11')

    for s in arbre_n11['sequences']:
        for p in s['parties']:
            assert p['atomes_cartes'] == []
