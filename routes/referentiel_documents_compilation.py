"""routes/referentiel_documents_compilation.py — v0.13.6.5.1

API REST de compilation des documents publiables d'un référentiel.

Endpoints :
  POST /api/referentiels/<ref_id>/documents/<doc_id>/compiler
      → lance la compilation en thread daemon, retourne 202
  GET  /api/referentiels/<ref_id>/documents/<doc_id>/compiler/statut
      → état d'avancement (polling de progression)
  GET  /api/referentiels/<ref_id>/documents/<doc_id>/pdf
      → renvoie le PDF compilé (200 application/pdf, 404 sinon)
      query param `cible` = nom du sous-fichier pour les types multi-cible
"""

from pathlib import Path

from flask import Blueprint, request, jsonify, current_app, send_file

from services import referentiel_documents as svc_cat
from services import referentiel_documents_compilation as svc_cmp

bp = Blueprint("referentiel_documents_compilation", __name__)


def _store():
    return current_app.json_store


def _verifier_appartenance(conn, ref_id: str, doc_id: str):
    """Renvoie (None, None) si OK, sinon (response, status_code) à
    renvoyer par la route."""
    row = conn.execute(
        "SELECT id FROM referentiel_niveaux WHERE id = ?",
        (ref_id,),
    ).fetchone()
    if row is None:
        return jsonify({
            "error": "referentiel_introuvable",
            "message": f"Référentiel {ref_id} introuvable",
        }), 404
    row = conn.execute(
        "SELECT id FROM referentiel_documents "
        "WHERE id = ? AND referentiel_id = ?",
        (doc_id, ref_id),
    ).fetchone()
    if row is None:
        return jsonify({
            "error": "document_introuvable",
            "message": f"Document {doc_id} introuvable dans ce référentiel",
        }), 404
    return None, None


# ── POST /compiler ──────────────────────────────────────────────────────────


@bp.route(
    "/api/referentiels/<ref_id>/documents/<doc_id>/compiler",
    methods=["POST"],
)
def api_compiler(ref_id: str, doc_id: str):
    """Lance la compilation en arrière-plan (thread daemon).

    Retourne immédiatement avec 202 Accepted. L'UI doit ensuite poller
    /compiler/statut pour suivre l'avancement.
    """
    store = _store()
    with store._conn() as conn:
        err, code = _verifier_appartenance(conn, ref_id, doc_id)
        if err is not None:
            return err, code

        # Pré-validations : doc actif ? pas déjà en cours ?
        row = conn.execute("""
            SELECT options, compile_en_cours
              FROM referentiel_documents WHERE id = ?
        """, (doc_id,)).fetchone()
        import json as _json
        try:
            options = _json.loads(row['options']) if row['options'] else {}
        except Exception:
            options = {}
        if not options.get('actif', False):
            return jsonify({
                "error": "document_inactif",
                "message": "Le document doit être actif pour être compilé.",
            }), 400
        if row['compile_en_cours']:
            return jsonify({
                "error": "compilation_en_cours",
                "message": "Une compilation est déjà en cours pour ce document.",
            }), 409

    # Récupérer la configuration du compilateur (TikZ/tblr libs, chemins).
    # On reprend le pattern de routes/livret_sequence.py via Configuration.
    # v0.13.6.5.1.2 — fix : avant on hardcodait tikz=[] et tblr=[booktabs,
    # varwidth], ce qui faisait diverger la compilation depuis le
    # référentiel vs celle depuis l'atelier d'assemblage.
    racine_appli = Path(current_app.root_path)
    dossier_images = Path(store.data_dir) / 'images'
    config = _configuration()
    racine_sources = config.chemin_sources_livrets()
    tikz = config.tikz_libraries()
    tblr = config.tblr_libraries()

    # Lancer le thread
    svc_cmp.compiler_document_async(
        store, doc_id,
        racine_sources=racine_sources,
        dossier_images=dossier_images,
        racine_appli=racine_appli,
        tikz_libraries=tikz,
        tblr_libraries=tblr,
    )
    return jsonify({
        "compile_en_cours": True,
        "doc_id": doc_id,
    }), 202


def _configuration():
    """Retourne l'instance Configuration partagée (cf. autres routes).

    v0.13.6.5.1.2 : centralise la lecture des paramètres compilation
    (TikZ libs, tblr libs, racine sources livrets) au même endroit que
    les autres routes de compilation, pour garantir un comportement
    identique entre l'atelier d'assemblage et l'orchestrateur.
    """
    from services.configuration import Configuration
    if not hasattr(current_app, 'configuration'):
        current_app.configuration = Configuration(
            current_app.json_store.data_dir
        )
    return current_app.configuration


# Anciens helpers conservés en fallback au cas où Configuration n'est
# pas dispo (cas d'erreur ou tests minimaux). Ne sont plus appelés par
# api_compiler en chemin nominal.

def _racine_sources(racine_appli: Path) -> Path:
    """[DEPRECATED v0.13.6.5.1.2] Fallback historique : cherche un
    dossier `paquet/` ou `latex/` à côté de appli/. Remplacé en chemin
    nominal par `_configuration().chemin_sources_livrets()`.
    """
    for nom in ('paquet', 'latex'):
        candidat = racine_appli.parent / nom
        if candidat.is_dir():
            return candidat
    return racine_appli


def _libraries_compilation(racine_appli: Path) -> tuple[list[str], list[str]]:
    """[DEPRECATED v0.13.6.5.1.2] Fallback historique : valeurs codées
    en dur. Remplacé en chemin nominal par
    `_configuration().tikz_libraries()` et `tblr_libraries()`.
    """
    tikz = []
    tblr = ['booktabs', 'varwidth']
    return tikz, tblr


# ── GET /compiler/statut ────────────────────────────────────────────────────


@bp.route(
    "/api/referentiels/<ref_id>/documents/<doc_id>/compiler/statut",
    methods=["GET"],
)
def api_statut(ref_id: str, doc_id: str):
    """Renvoie l'état d'avancement courant.

    Si une compilation est ou a été en cours récemment, renvoie le statut
    en mémoire ({en_cours, total, fait, etape_courante, erreur_globale}).
    Sinon, renvoie l'état persistant en BDD (compile_ok, compile_date).
    """
    store = _store()
    with store._conn() as conn:
        err, code = _verifier_appartenance(conn, ref_id, doc_id)
        if err is not None:
            return err, code

        statut_mem = svc_cmp.lire_statut(doc_id)

        # Toujours renvoyer aussi les colonnes BDD finalisées
        row = conn.execute("""
            SELECT compile_ok, compile_date, compile_log, compile_en_cours
              FROM referentiel_documents WHERE id = ?
        """, (doc_id,)).fetchone()
        bdd = {
            'compile_ok':    row['compile_ok'] if row else None,
            'compile_date':  row['compile_date'] if row else None,
            'compile_log':   row['compile_log'] if row else None,
            'compile_en_cours': bool(row['compile_en_cours']) if row and row['compile_en_cours'] else False,
        }

    return jsonify({
        'statut': statut_mem,  # None si aucun statut courant en mémoire
        'bdd':    bdd,
    })


# ── GET /pdf ────────────────────────────────────────────────────────────────


@bp.route(
    "/api/referentiels/<ref_id>/documents/<doc_id>/pdf",
    methods=["GET"],
)
def api_pdf(ref_id: str, doc_id: str):
    """Renvoie le PDF compilé.

    Query string :
      - `cible` : pour les types multi-cible, identifie le sous-fichier
                  (ex: 'N10/S01' pour livret_sequence, eval_id pour
                  evaluation). Pour les types unitaires, ignoré.

    Réponses :
      200 application/pdf : le PDF en flux
      404                 : doc introuvable, ou PDF non trouvé sur disque
                            (pas compilé ou supprimé)
    """
    store = _store()
    with store._conn() as conn:
        err, code = _verifier_appartenance(conn, ref_id, doc_id)
        if err is not None:
            return err, code

        row = conn.execute(
            "SELECT type_document FROM referentiel_documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        type_document = row['type_document']

        # Calculer le nom_fichier attendu via lister_cibles_document
        cibles = svc_cmp.lister_cibles_document(conn, doc_id, ref_id,
                                                  type_document)

    cible_demandee = request.args.get('cible', '')
    nom_fichier = None
    if not cibles:
        return jsonify({
            "error": "aucune_cible",
            "message": "Aucune cible compilable pour ce document.",
        }), 404
    if cible_demandee:
        for c in cibles:
            if c['cible_id'] == cible_demandee:
                nom_fichier = c['nom_fichier']
                break
        if nom_fichier is None:
            return jsonify({
                "error": "cible_inconnue",
                "message": f"Cible {cible_demandee!r} inconnue pour ce document.",
            }), 404
    else:
        # Pas de cible précisée : si type unitaire, on prend la seule
        # cible. Si multi-cible, on refuse.
        if len(cibles) == 1:
            nom_fichier = cibles[0]['nom_fichier']
        else:
            return jsonify({
                "error": "cible_requise",
                "message": (
                    "Ce document a plusieurs cibles. "
                    "Précisez ?cible=... dans la requête."
                ),
                "cibles": [c['cible_id'] for c in cibles],
            }), 400

    chemin = svc_cmp.chemin_pdf(store, ref_id, nom_fichier)
    if not chemin.exists():
        return jsonify({
            "error": "pdf_non_trouve",
            "message": (
                f"Le PDF n'a pas encore été compilé ou est introuvable "
                f"({nom_fichier})."
            ),
        }), 404

    return send_file(str(chemin), mimetype='application/pdf',
                     as_attachment=False,
                     download_name=nom_fichier)


# ── v0.13.6.5.1.1 — Accès au .tex source et au log complet ─────────────────


@bp.route(
    "/api/referentiels/<ref_id>/documents/<doc_id>/tex",
    methods=["GET"],
)
def api_tex(ref_id: str, doc_id: str):
    """Renvoie le .tex source effectivement compilé pour une cible.

    Query string :
      - `cible` : pour les types multi-cible, identifie le sous-fichier
                  (ex: 'N10/S01'). Optionnel pour les types unitaires.

    Réponses :
      200 text/plain : le source LaTeX
      404            : document ou .tex introuvable (pas compilé)
    """
    return _servir_artefact(ref_id, doc_id, 'tex', 'text/plain; charset=utf-8')


@bp.route(
    "/api/referentiels/<ref_id>/documents/<doc_id>/log",
    methods=["GET"],
)
def api_log(ref_id: str, doc_id: str):
    """Renvoie le log complet pdflatex d'une compilation.

    Query string :
      - `cible` : pour les types multi-cible, identifie le sous-fichier.
                  Optionnel pour les types unitaires.

    Réponses :
      200 text/plain : log pdflatex
      404            : document ou log introuvable (pas compilé)
    """
    return _servir_artefact(ref_id, doc_id, 'log', 'text/plain; charset=utf-8')


def _servir_artefact(ref_id: str, doc_id: str,
                     extension: str, mimetype: str):
    """Logique commune aux endpoints /tex et /log : résout la cible
    demandée et sert l'artefact correspondant depuis le dossier
    `_artefacts/` du référentiel."""
    from services import orchestrateur_compilation as orch

    store = _store()
    with store._conn() as conn:
        err, code = _verifier_appartenance(conn, ref_id, doc_id)
        if err is not None:
            return err, code
        row = conn.execute(
            "SELECT type_document FROM referentiel_documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        type_document = row['type_document']
        cibles = svc_cmp.lister_cibles_document(conn, doc_id, ref_id,
                                                  type_document)

    if not cibles:
        return jsonify({
            "error": "aucune_cible",
            "message": "Aucune cible pour ce document.",
        }), 404

    # Sélection de la cible
    cible_demandee = request.args.get('cible', '')
    cible_choisie = None
    if cible_demandee:
        for c in cibles:
            if c['cible_id'] == cible_demandee:
                cible_choisie = c
                break
        if cible_choisie is None:
            return jsonify({
                "error": "cible_inconnue",
                "message": f"Cible {cible_demandee!r} inconnue.",
            }), 404
    elif len(cibles) == 1:
        cible_choisie = cibles[0]
    else:
        return jsonify({
            "error": "cible_requise",
            "message": (
                "Ce document a plusieurs cibles. "
                "Précisez ?cible=... dans la requête."
            ),
            "cibles": [c['cible_id'] for c in cibles],
        }), 400

    cible_key = orch.slug_cible(cible_choisie['cible_id'])
    chemin = svc_cmp.chemin_artefact(store, ref_id, doc_id, cible_key,
                                       extension)
    if not chemin.exists():
        return jsonify({
            "error": "artefact_non_trouve",
            "message": (
                f"Pas de {extension} pour cette cible "
                f"({cible_choisie['libelle']}). "
                f"Le document n'a peut-être pas encore été compilé."
            ),
        }), 404

    contenu = chemin.read_text(encoding='utf-8', errors='replace')
    return contenu, 200, {'Content-Type': mimetype}
