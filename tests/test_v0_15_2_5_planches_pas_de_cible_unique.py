"""tests/test_v0_15_2_5_planches_pas_de_cible_unique.py — v0.15.2.5

Décision : retirer la cible 'unique' (toutes séquences) des planches.

Contexte
--------
v0.15.2.4 exposait 1 cible 'unique' + 14 cibles par séquence pour
`livret_cartes_planches`. Test terrain de Laurent : la cible 'unique'
s'exécutait en premier, bloquait la barre de progression à 0/15 pendant
plus de 5 minutes, et finissait par échouer (timeout à 300s). Les cibles
par séquence (~25-30s chacune) fonctionnaient correctement APRÈS.

Décision v0.15.2.5 : ne plus exposer la cible 'unique' dans
`lister_cibles_document`. Le générateur `generer_livret_cartes_planches`
conserve son support de `sequence=None` (utilisable par script ad hoc
ou compilation manuelle hors timeout), mais l'orchestrateur n'expose
plus que les cibles par séquence.

Ces tests nommés protègent cette décision : si quelqu'un réintroduit
plus tard une cible 'unique' sans la cadrer (mode async, timeout
relâché, etc.), ces tests échouent et expliquent pourquoi.
"""
from __future__ import annotations

from pathlib import Path
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import referentiel_documents as svc_cat  # noqa: E402
from services import referentiel_documents_compilation as svc_cmp  # noqa: E402


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


def _ajouter_carte(conn, niveau, sequence, num):
    conn.execute("""
        INSERT INTO cartes_automatisme
            (id, niveau, sequence, num, type_pedago, type_tech,
             titre, lien_type, lien_id, recto, verso, variables,
             etat_code, ordre)
        VALUES (?, ?, ?, ?, 'definition', 'fixe', ?, NULL, NULL,
                '', '', '', 'valide', 0)
    """, (f"c_{uuid.uuid4().hex[:8]}", niveau, sequence, num,
          f"Carte {sequence}/{num}"))


# ── La cible 'unique' ne doit jamais être exposée ───────────────────────────


def test_planches_aucune_cible_unique_meme_avec_cartes(sqlite_store):
    """Avec des cartes valides, AUCUNE cible 'unique' n'est exposée.

    Voir docstring du module : la cible 'unique' (toutes séquences) a été
    retirée en v0.15.2.5 suite à un test terrain (timeout >5min,
    blocage UI à 0/15 puis échec).
    """
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = next(d for d in docs
                   if d['type_document'] == 'livret_cartes_planches')
        _ajouter_carte(conn, 'N10', 'S01', 1)
        _ajouter_carte(conn, 'N10', 'S02', 1)
        _ajouter_carte(conn, 'N10', 'S03', 1)
        conn.commit()
        cibles = svc_cmp.lister_cibles_document(
            conn, doc['id'], ref_id, 'livret_cartes_planches'
        )

    assert len(cibles) == 3
    assert all(c['cible_id'] != 'unique' for c in cibles)
    # Aucune cible n'a le nom_fichier 'livret_cartes_planches.pdf' nu
    # (réservé à un usage hors orchestrateur si réintroduit).
    assert all(c['nom_fichier'] != 'livret_cartes_planches.pdf'
               for c in cibles)
    # Toutes les cibles ont une clé 'sequence' explicite (ce que la
    # cible 'unique' n'aurait pas).
    assert all('sequence' in c and c['sequence'] for c in cibles)


def test_planches_nom_fichier_toujours_suffixe_par_sequence(sqlite_store):
    """Tous les noms de fichier des cibles 'livret_cartes_planches'
    suivent le motif `livret_cartes_planches__<niveau>__<sequence>.pdf`.

    Garantit qu'aucune cible ne réutilise par mégarde le nom de fichier
    historique nu (`livret_cartes_planches.pdf`) qui serait ambigu avec
    une éventuelle compilation manuelle hors orchestrateur.
    """
    import re
    pattern = re.compile(
        r'^livret_cartes_planches__N\d{2}__S\d{2}\.pdf$'
    )
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = next(d for d in docs
                   if d['type_document'] == 'livret_cartes_planches')
        for seq in ['S01', 'S07', 'S14']:
            _ajouter_carte(conn, 'N10', seq, 1)
        conn.commit()
        cibles = svc_cmp.lister_cibles_document(
            conn, doc['id'], ref_id, 'livret_cartes_planches'
        )
    for c in cibles:
        assert pattern.match(c['nom_fichier']), \
            f"nom_fichier {c['nom_fichier']!r} ne suit pas le motif attendu"
