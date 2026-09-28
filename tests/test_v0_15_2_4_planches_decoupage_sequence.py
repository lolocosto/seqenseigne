"""tests/test_v0_15_2_4_planches_decoupage_sequence.py — v0.15.2.4

Découpage des planches de cartes d'automatisme par séquence (performance).

Contexte
--------
Compiler les 119 planches d'un niveau en un seul .tex prend ~5min40,
au-delà du timeout appli (300s). Décision actée avec Laurent : produire
1 PDF par séquence (≈8-9 planches), TOUT EN conservant une cible 'unique'
(toutes les planches du niveau dans un seul PDF). Le récap des cartes
(`livret_cartes_recap`) reste unitaire (rapide).

Ce module protège, par des tests nommés :
  1. `lister_cibles_document('livret_cartes_planches')` renvoie
     1 cible 'unique' + 1 cible par séquence présente au niveau, dans
     l'ordre des séquences, avec les bons `nom_fichier` (unique
     rétrocompatible).
  2. La cible 'unique' n'a PAS de clé 'sequence' (→ toutes séquences) ;
     les cibles par séquence ont la bonne clé 'sequence'.
  3. `generer_livret_cartes_planches(..., sequence='Sxx')` ne génère
     que les planches de cette séquence (filtrage SQL), tandis que
     `sequence=None` génère toutes les planches (rétrocompatibilité).
  4. La page de garde mentionne la séquence quand elle est filtrée.
  5. `_produire_livret_cartes_planches` propage `cible.get('sequence')`.

Tous les non-évidents (double famille de cibles, rétrocompat du
paramètre optionnel) sont protégés ici, conformément à la discipline
test-driven du projet.
"""
from __future__ import annotations

from pathlib import Path
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import referentiel_documents as svc_cat  # noqa: E402
from services import referentiel_documents_compilation as svc_cmp  # noqa: E402
from services.livret_cartes_planches import (  # noqa: E402
    generer_livret_cartes_planches,
    _lire_cartes_du_niveau,
)


def _conn(store):
    return store._conn()


def _creer_referentiel_minimal(conn, niveau='N10'):
    ref_id = f"ref_test_{uuid.uuid4().hex[:8]}"
    conn.execute("""
        INSERT INTO referentiel_niveaux
            (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ref_id, niveau, '2025_test', '2025-09-01', '2026-08-31',
          'Test', 'en_cours'))
    conn.commit()
    return ref_id


def _ajouter_carte(conn, niveau, sequence, num, *, etat='valide',
                   recto='', verso='', variables=''):
    conn.execute("""
        INSERT INTO cartes_automatisme
            (id, niveau, sequence, num, type_pedago, type_tech,
             titre, lien_type, lien_id, recto, verso, variables,
             etat_code, ordre)
        VALUES (?, ?, ?, ?, 'definition', 'fixe', ?, NULL, NULL,
                ?, ?, ?, ?, 0)
    """, (f"c_{uuid.uuid4().hex[:8]}", niveau, sequence, num,
          f"Carte {sequence}/{num}", recto, verso, variables, etat))


# ── 1. lister_cibles_document : double famille (unique + par séquence) ───────


def test_cibles_planches_vide_aucune_cible(sqlite_store):
    """Sans aucune carte valide, aucune cible exposée.

    v0.15.2.5 : la cible 'unique' a été retirée (timeout en pratique).
    Le générateur garde son support `sequence=None`, mais l'orchestrateur
    n'expose plus que les cibles par séquence — donc 0 cible si aucune
    carte valide.
    """
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = next(d for d in docs
                   if d['type_document'] == 'livret_cartes_planches')
        cibles = svc_cmp.lister_cibles_document(
            conn, doc['id'], ref_id, 'livret_cartes_planches'
        )
    assert cibles == []


def test_cibles_planches_une_par_sequence(sqlite_store):
    """Avec 3 séquences ayant des cartes valides : 3 cibles, une par
    séquence, dans l'ordre des séquences. Pas de cible 'unique'
    (cf. v0.15.2.5).
    """
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = next(d for d in docs
                   if d['type_document'] == 'livret_cartes_planches')
        # S01 (2 cartes), S03 (1), S02 (1) — insérées dans le désordre
        _ajouter_carte(conn, 'N10', 'S01', 1)
        _ajouter_carte(conn, 'N10', 'S03', 1)
        _ajouter_carte(conn, 'N10', 'S01', 2)
        _ajouter_carte(conn, 'N10', 'S02', 1)
        conn.commit()
        cibles = svc_cmp.lister_cibles_document(
            conn, doc['id'], ref_id, 'livret_cartes_planches'
        )

    # 3 séquences distinctes (S01, S02, S03), aucune cible 'unique'
    assert len(cibles) == 3
    assert all(c['cible_id'] != 'unique' for c in cibles)
    seqs = [c['sequence'] for c in cibles]
    assert seqs == ['S01', 'S02', 'S03']  # triées
    assert cibles[0]['cible_id'] == 'N10/S01'
    assert cibles[0]['nom_fichier'] == 'livret_cartes_planches__N10__S01.pdf'
    assert cibles[1]['nom_fichier'] == 'livret_cartes_planches__N10__S02.pdf'
    assert cibles[2]['nom_fichier'] == 'livret_cartes_planches__N10__S03.pdf'


def test_cibles_planches_ignore_cartes_non_valides(sqlite_store):
    """Une séquence dont toutes les cartes sont non-valides n'engendre
    pas de cible (v0.15.2.5 : seules les séquences avec au moins une
    carte 'valide' produisent une cible).
    """
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = next(d for d in docs
                   if d['type_document'] == 'livret_cartes_planches')
        _ajouter_carte(conn, 'N10', 'S01', 1, etat='valide')
        _ajouter_carte(conn, 'N10', 'S05', 1, etat='en_cours')  # ignorée
        conn.commit()
        cibles = svc_cmp.lister_cibles_document(
            conn, doc['id'], ref_id, 'livret_cartes_planches'
        )
    seqs = [c['sequence'] for c in cibles]
    assert 'S01' in seqs
    assert 'S05' not in seqs
    assert len(cibles) == 1


# ── 2. Générateur : filtrage par séquence ────────────────────────────────────


def test_lire_cartes_filtre_sequence(sqlite_store):
    """_lire_cartes_du_niveau(sequence='S02') ne retourne que S02 ;
    sans séquence, retourne tout.
    """
    with _conn(sqlite_store) as conn:
        _ajouter_carte(conn, 'N10', 'S01', 1)
        _ajouter_carte(conn, 'N10', 'S02', 1)
        _ajouter_carte(conn, 'N10', 'S02', 2)
        conn.commit()
        toutes = _lire_cartes_du_niveau(conn, 'N10')
        s02 = _lire_cartes_du_niveau(conn, 'N10', sequence='S02')
    assert len(toutes) == 3
    assert len(s02) == 2
    assert {c['sequence'] for c in s02} == {'S02'}


def test_generer_sequence_ne_contient_que_la_sequence(sqlite_store):
    """generer_livret_cartes_planches(sequence='S02') ne produit que les
    planches S02 (commentaires de planche %% .../Sxx/...).
    """
    with _conn(sqlite_store) as conn:
        _ajouter_carte(conn, 'N10', 'S01', 1)
        _ajouter_carte(conn, 'N10', 'S02', 1)
        _ajouter_carte(conn, 'N10', 'S02', 2)
        conn.commit()
        tex = generer_livret_cartes_planches(conn, 'N10', sequence='S02')
    assert '%% Planche N10/S02/CA01' in tex
    assert '%% Planche N10/S02/CA02' in tex
    assert '%% Planche N10/S01/' not in tex
    # commentaire de découpage présent
    assert 'Séquence : S02' in tex


def test_generer_sans_sequence_contient_tout(sqlite_store):
    """Rétrocompat : generer_livret_cartes_planches sans 'sequence'
    produit toutes les planches du niveau.
    """
    with _conn(sqlite_store) as conn:
        _ajouter_carte(conn, 'N10', 'S01', 1)
        _ajouter_carte(conn, 'N10', 'S02', 1)
        conn.commit()
        tex = generer_livret_cartes_planches(conn, 'N10')
    assert '%% Planche N10/S01/CA01' in tex
    assert '%% Planche N10/S02/CA01' in tex
    assert 'Séquence :' not in tex  # pas de ligne de découpage


def test_page_de_garde_mentionne_sequence(sqlite_store):
    """La page de garde affiche la séquence quand on filtre."""
    with _conn(sqlite_store) as conn:
        _ajouter_carte(conn, 'N10', 'S03', 1)
        conn.commit()
        tex_seq = generer_livret_cartes_planches(conn, 'N10', sequence='S03')
        tex_all = generer_livret_cartes_planches(conn, 'N10')
    assert 'séquence S03' in tex_seq
    assert 'séquence' not in tex_all.split(r'\clearpage')[0]


def test_generer_sequence_vide_message_dedie(sqlite_store):
    """Séquence sans carte valide → message dédié, .tex équilibré."""
    with _conn(sqlite_store) as conn:
        tex = generer_livret_cartes_planches(conn, 'N10', sequence='S07')
    assert 'Aucune carte pour N10/S07' in tex
    assert tex.count('{') == tex.count('}')
    assert r'\end{document}' in tex


# ── 3. Orchestrateur : propagation de cible.get('sequence') ──────────────────


def test_producteur_propage_sequence(sqlite_store):
    """`_produire_livret_cartes_planches` propage `cible.get('sequence')`
    au générateur.

    Cible avec 'sequence' → filtrage ; cible sans 'sequence' → toutes les
    séquences (rétrocompat du générateur, utilisable par script même si
    l'orchestrateur n'expose plus cette cible depuis v0.15.2.5).
    """
    from services import orchestrateur_compilation as orch
    with _conn(sqlite_store) as conn:
        _ajouter_carte(conn, 'N10', 'S01', 1)
        _ajouter_carte(conn, 'N10', 'S02', 1)
        conn.commit()
        prod = orch.REGISTRE['livret_cartes_planches']

        tex_seq = prod(
            conn,
            {'niveau': 'N10', 'sequence': 'S02', 'cible_id': 'N10/S02'},
            {}, None, None,
        )
        # Cible synthétique sans 'sequence' : contrat interne du générateur.
        tex_toutes = prod(
            conn,
            {'niveau': 'N10', 'cible_id': 'synthetique_toutes_sequences'},
            {}, None, None,
        )
    assert '%% Planche N10/S02/CA01' in tex_seq
    assert '%% Planche N10/S01/' not in tex_seq
    # sans 'sequence' → les deux séquences
    assert '%% Planche N10/S01/CA01' in tex_toutes
    assert '%% Planche N10/S02/CA01' in tex_toutes
