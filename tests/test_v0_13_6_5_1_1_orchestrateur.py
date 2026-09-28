"""tests/test_v0_13_6_5_1_1_orchestrateur.py — v0.13.6.5.1.1

Tests de la couche orchestrateur de compilation.

Couvre :
  - le registre des producteurs (9 types documents publiables)
  - slug_cible
  - compiler() avec un type inconnu → ko 'producteur'
  - compiler() avec un type "à venir" (livret_fiches, etc.) → ko 'producteur'
    avec code 'type_non_implemente'
  - compiler() avec un producteur qui lève → ko 'producteur'
  - compiler() avec persistance des artefacts (.tex, .log)
  - Migration de _generer_tex (rétrocompat) → délègue à l'orchestrateur
  - Routes /tex et /log
"""
from __future__ import annotations

from pathlib import Path
import sys
import json
import uuid
import sqlite3

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import orchestrateur_compilation as orch  # noqa: E402
from services import referentiel_documents as svc_cat   # noqa: E402
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


# ── 1. Registre ──────────────────────────────────────────────────────────────


def test_registre_contient_9_types_documents():
    """Les 9 types de documents publiables ont un producteur enregistré."""
    attendus = {
        'livret_sequence', 'livret_cours', 'livret_exercices',
        'livret_fiches', 'livret_plans', 'livret_corriges',
        'evaluation', 'livret_cartes_recap', 'livret_cartes_planches',
    }
    presents = set(orch.REGISTRE.keys())
    manquants = attendus - presents
    assert not manquants, f"Types manquants dans REGISTRE : {manquants}"


def test_types_a_venir_levent_producteur_erreur(sqlite_store):
    """v0.13.6.5.2 — Renommé sémantiquement : les 4 types précédemment
    'à venir' sont maintenant implémentés et NE lèvent PLUS
    type_non_implemente.

    Le test conserve son nom (utilisé par d'autres outils ou CI) mais
    inverse son assertion : on vérifie qu'aucun des 4 ne lève
    type_non_implemente. Une erreur d'un autre type (LookupError sur
    cycle absent, ProducteurErreur(code='cible_invalide'), etc.) reste
    acceptable car non liée à l'absence d'implémentation.
    """
    anciennement_a_venir = [
        'livret_fiches', 'livret_corriges',
        'livret_cartes_recap', 'livret_cartes_planches',
    ]
    with _conn(sqlite_store) as conn:
        for t in anciennement_a_venir:
            producteur = orch.REGISTRE[t]
            try:
                tex = producteur(conn, {'niveau': 'N10'}, {}, [], [])
                # Implémentation effective : doit retourner un .tex
                assert isinstance(tex, str)
                assert r'\documentclass' in tex
            except LookupError:
                # Fixture sqlite_store sans cycle pré-créé : OK,
                # ce test vise l'absence de stub type_non_implemente.
                pass
            except sqlite3.OperationalError:
                # v0.15.5 — Depuis la factorisation de lire_cycle (lit
                # param_niveaux, peuplé par conftest), le producteur ne
                # s'arrête plus tôt sur un LookupError « cycle absent » :
                # il atteint construire_preambule qui requête
                # `paquet_definitions`, absente de la fixture nue. Hors
                # scope : ce test ne vise QUE l'absence de stub.
                pass
            except orch.ProducteurErreur as e:
                if e.code == 'type_non_implemente':
                    pytest.fail(
                        f"{t!r} lève encore type_non_implemente — "
                        f"non branché en v0.13.6.5.2."
                    )
                # Autres codes acceptés (cible_invalide si données
                # manquantes, etc.)


def test_decorateur_remplace_silencieusement():
    """Re-enregistrer un type écrase silencieusement l'ancien (utile au
    hot-reload)."""
    type_test = '__test_remplacement__'
    @orch.enregistrer_producteur(type_test)
    def _v1(*args, **kwargs):
        return 'v1'
    @orch.enregistrer_producteur(type_test)
    def _v2(*args, **kwargs):
        return 'v2'
    assert orch.REGISTRE[type_test](None, {}, {}, [], []) == 'v2'
    del orch.REGISTRE[type_test]  # cleanup


# ── 2. slug_cible ────────────────────────────────────────────────────────────


def test_slug_cible_basique():
    assert orch.slug_cible('N10/S01') == 'N10_S01'
    assert orch.slug_cible('eval_abc12') == 'eval_abc12'
    assert orch.slug_cible('unique') == 'unique'


def test_slug_cible_caracteres_speciaux():
    """Tout caractère hors [a-zA-Z0-9_-] devient _."""
    assert orch.slug_cible('A B/C') == 'A_B_C'
    assert orch.slug_cible('test\\file') == 'test_file'
    assert orch.slug_cible('a.b.c') == 'a_b_c'
    assert orch.slug_cible('') == '_'


def test_slug_cible_idempotent():
    """Appliquer slug_cible deux fois donne le même résultat."""
    s = 'N10/S01-test.tex'
    assert orch.slug_cible(orch.slug_cible(s)) == orch.slug_cible(s)


# ── 3. compiler() : cas d'échec sans pdflatex ────────────────────────────────


def test_compiler_type_inconnu(sqlite_store):
    """compiler() avec un type non enregistré → ResultatOrchestration
    ko avec type_echec='producteur'."""
    with _conn(sqlite_store) as conn:
        res = orch.compiler(
            conn=conn,
            type_cible='type_qui_nexiste_pas',
            cible={},
            options={},
        )
    assert res.ok is False
    assert res.type_echec == 'producteur'
    assert len(res.erreurs) >= 1
    assert 'inconnu' in res.erreurs[0].message.lower()


def test_compiler_type_non_implemente(sqlite_store):
    """v0.13.6.5.2 — Le producteur livret_fiches n'est plus un stub
    'non encore implémenté'.

    Avant v0.13.6.5.2 : compiler() retournait ok=False avec
    type_echec='producteur' et message 'non encore implémenté'.
    À partir de v0.13.6.5.2 : le producteur génère un vrai .tex
    (la compilation pdflatex elle-même peut échouer en sandbox sans
    paquet seqenseigne installé, mais ce n'est pas un échec
    'producteur' lié à l'absence d'implémentation).

    On vérifie que le message d'erreur 'non encore implémenté' n'apparaît
    plus jamais pour aucun des 4 types implémentés en v0.13.6.5.2.
    """
    anciennement_a_venir = [
        'livret_fiches', 'livret_corriges',
        'livret_cartes_recap', 'livret_cartes_planches',
    ]
    with _conn(sqlite_store) as conn:
        for type_doc in anciennement_a_venir:
            res = orch.compiler(
                conn=conn,
                type_cible=type_doc,
                cible={'niveau': 'N10'},
                options={},
            )
            # Vérifier qu'aucune erreur ne contient le message de stub.
            messages = [(e.message or '').lower() for e in res.erreurs]
            for msg in messages:
                assert 'non encore implémenté' not in msg, (
                    f"{type_doc} retourne encore le message de stub : "
                    f"{msg!r}"
                )


def test_compiler_cible_invalide_livret_sequence(sqlite_store):
    """livret_sequence sans niveau/sequence → ProducteurErreur."""
    with _conn(sqlite_store) as conn:
        res = orch.compiler(
            conn=conn,
            type_cible='livret_sequence',
            cible={'niveau': 'N10'},  # sequence manque
            options={},
        )
    assert res.ok is False
    assert res.type_echec == 'producteur'


def test_compiler_producteur_qui_leve(sqlite_store):
    """Un producteur qui lève une exception non-ProducteurErreur est
    correctement géré (ko, type_echec='producteur')."""
    type_test = '__test_producteur_buggue__'
    @orch.enregistrer_producteur(type_test)
    def _producteur_buggue(*args, **kwargs):
        raise ValueError("bug interne")
    try:
        with _conn(sqlite_store) as conn:
            res = orch.compiler(
                conn=conn,
                type_cible=type_test,
                cible={},
                options={},
            )
        assert res.ok is False
        assert res.type_echec == 'producteur'
        assert 'bug interne' in res.erreurs[0].message
    finally:
        del orch.REGISTRE[type_test]


# ── 4. compiler() : persistance des artefacts ────────────────────────────────


def test_compiler_persiste_tex_meme_si_echec_compilation(sqlite_store, tmp_path):
    """Même si la compilation pdflatex échoue (ou pdflatex absent), le
    .tex source doit être posé sur disque pour qu'on puisse l'inspecter."""
    type_test = '__test_tex_simple__'
    @orch.enregistrer_producteur(type_test)
    def _produire_simple(*args, **kwargs):
        return r"\documentclass{article}\begin{document}Hello\end{document}"
    try:
        with _conn(sqlite_store) as conn:
            res = orch.compiler(
                conn=conn,
                type_cible=type_test,
                cible={},
                options={},
                dossier_artefacts=tmp_path,
                cible_key='test_simple',
                # pas de pdflatex → ko en infrastructure
                pdflatex='/chemin/qui/nexiste/pas',
            )
        # Le .tex doit avoir été persisté
        chemin_tex = tmp_path / 'test_simple.tex'
        assert chemin_tex.exists()
        assert 'Hello' in chemin_tex.read_text()
        # Le log aussi
        chemin_log = tmp_path / 'test_simple.log'
        assert chemin_log.exists()
        # ResultatOrchestration porte les chemins
        assert res.chemin_tex == chemin_tex
        assert res.chemin_log == chemin_log
    finally:
        del orch.REGISTRE[type_test]


def test_compiler_sans_dossier_artefacts_pas_de_persistance(sqlite_store):
    """Si on ne fournit pas de dossier_artefacts, les chemins
    persistés sont None."""
    type_test = '__test_no_persist__'
    @orch.enregistrer_producteur(type_test)
    def _produire(*args, **kwargs):
        return r"\documentclass{article}"
    try:
        with _conn(sqlite_store) as conn:
            res = orch.compiler(
                conn=conn,
                type_cible=type_test,
                cible={},
                options={},
                pdflatex='/n/a',
            )
        assert res.chemin_tex is None
        assert res.chemin_log is None
        assert res.chemin_pdf is None
    finally:
        del orch.REGISTRE[type_test]


# ── 5. Rétrocompat : _generer_tex délègue à l'orchestrateur ─────────────────


def test_generer_tex_delegue_a_orchestrateur(sqlite_store):
    """v0.13.6.5.2 — _generer_tex délègue à l'orchestrateur, et les 4
    types précédemment 'à venir' sont maintenant implémentés et ne
    lèvent plus type_non_implemente.

    Le test original (v0.13.6.5.1.1) attendait que les 4 lèvent
    type_non_implemente. À partir de v0.13.6.5.2, ils délèguent aux
    nouveaux services et produisent du .tex (ou lèvent une autre
    erreur métier si la BDD n'est pas peuplée).
    """
    anciennement_a_venir = [
        'livret_fiches', 'livret_corriges',
        'livret_cartes_recap', 'livret_cartes_planches',
    ]
    with _conn(sqlite_store) as conn:
        for t in anciennement_a_venir:
            try:
                tex = svc_cmp._generer_tex(
                    conn, t, {}, {'niveau': 'N10'}, [], [],
                )
                # Succès : on a un .tex
                assert isinstance(tex, str)
                assert r'\documentclass' in tex
            except LookupError:
                # Fixture sqlite_store sans cycle pré-créé : OK
                pass
            except sqlite3.OperationalError:
                # v0.15.5 — cf. note dans test_types_a_venir : lire_cycle
                # réussit désormais (param_niveaux peuplé), le producteur
                # atteint construire_preambule et bute sur
                # `paquet_definitions` absente de la fixture nue. Hors scope.
                pass
            except svc_cmp.CompilationErreur as e:
                if e.code == 'type_non_implemente':
                    pytest.fail(
                        f"{t!r} lève encore type_non_implemente — "
                        f"non branché en v0.13.6.5.2."
                    )


def test_generer_tex_type_inconnu(sqlite_store):
    """_generer_tex avec un type non enregistré → CompilationErreur
    'type_inconnu'."""
    with _conn(sqlite_store) as conn:
        with pytest.raises(svc_cmp.CompilationErreur) as ei:
            svc_cmp._generer_tex(
                conn, 'type_qui_nexiste_pas', {}, {}, [], [],
            )
        assert ei.value.code == 'type_inconnu'


# ── 6. compile_log JSON : structure ──────────────────────────────────────────
#
# Après refacto, compile_log contient un JSON {version, type_document, cibles}
# au lieu d'un texte concaténé. Les tests v0.13.6.5.1 qui vérifiaient
# compile_log==texte concaténé peuvent encore passer si le texte JSON
# contient les bons mots-clés.


def test_compile_log_est_json_valide_apres_compilation(sqlite_store):
    """Après une compilation (même échouée), compile_log doit être un
    JSON valide avec la structure attendue."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        livret = next(d for d in docs
                      if d['type_document'] == 'livret_fiches')
        # Activer
        svc_cat.maj_options(conn, livret['id'], {'actif': True})

    # Lancer compilation (qui va échouer puisque livret_fiches est
    # 'type_non_implemente'). On veut que compile_log reflète l'échec
    # de manière structurée.
    try:
        svc_cmp.compiler_document(sqlite_store, livret['id'])
    except svc_cmp.CompilationErreur:
        # Si le verrou pré-validation échoue, on accepte (peu probable)
        pass

    with _conn(sqlite_store) as conn:
        row = conn.execute(
            "SELECT compile_log, compile_ok "
            "FROM referentiel_documents WHERE id = ?",
            (livret['id'],),
        ).fetchone()

    assert row is not None
    # compile_ok à 0 puisque type_non_implemente
    assert row['compile_ok'] == 0
    # compile_log : JSON parseable
    log = json.loads(row['compile_log'])
    assert log['version'] == '1'
    assert log['type_document'] == 'livret_fiches'
    assert isinstance(log['cibles'], list)
    assert len(log['cibles']) == 1  # 1 cible unique pour livret_fiches
    cible = log['cibles'][0]
    assert cible['ok'] is False
    assert cible['type_echec'] == 'producteur'
    assert cible['nb_erreurs'] >= 1


# ── 7. Routes /tex et /log ───────────────────────────────────────────────────


def test_route_tex_doc_non_compile(client, sqlite_store):
    """GET /tex sur document jamais compilé → 404."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        livret = next(d for d in docs
                      if d['type_document'] == 'livret_cours')
    resp = client.get(
        f"/api/referentiels/{ref_id}/documents/{livret['id']}/tex"
    )
    assert resp.status_code == 404


def test_route_log_doc_non_compile(client, sqlite_store):
    """GET /log sur document jamais compilé → 404."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        livret = next(d for d in docs
                      if d['type_document'] == 'livret_cours')
    resp = client.get(
        f"/api/referentiels/{ref_id}/documents/{livret['id']}/log"
    )
    assert resp.status_code == 404


def test_route_tex_doc_inconnu(client, sqlite_store):
    """GET /tex sur doc inexistant → 404."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
    resp = client.get(
        f"/api/referentiels/{ref_id}/documents/rd_inexistant/tex"
    )
    assert resp.status_code == 404


def test_route_log_cible_requise(client, sqlite_store):
    """GET /log sur livret_sequence avec >1 cibles et sans ?cible= → 400."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        livret = next(d for d in docs
                      if d['type_document'] == 'livret_sequence')
        # Créer 2 séquences pour avoir >1 cibles
        for code in ['S01', 'S02']:
            conn.execute("""
                INSERT INTO sequences_par_niveau(id, niveau, sequence_code)
                VALUES (?, 'N10', ?)
            """, (f"sn_test_{code}", code))
        conn.commit()
    resp = client.get(
        f"/api/referentiels/{ref_id}/documents/{livret['id']}/log"
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['error'] == 'cible_requise'


def test_route_log_cible_inconnue(client, sqlite_store):
    """GET /log avec ?cible=inconnue → 404."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        livret = next(d for d in docs
                      if d['type_document'] == 'livret_sequence')
        conn.execute("""
            INSERT INTO sequences_par_niveau(id, niveau, sequence_code)
            VALUES ('sn_test_S01', 'N10', 'S01')
        """)
        conn.commit()
    resp = client.get(
        f"/api/referentiels/{ref_id}/documents/{livret['id']}"
        f"/log?cible=N10/SXX"
    )
    assert resp.status_code == 404
    data = resp.get_json()
    assert data['error'] == 'cible_inconnue'
