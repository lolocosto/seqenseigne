"""routes/plans_de_travail.py — Plan de travail d'une séquence (PDF / .tex)

v0.16.10 — Réintroduction de la route, portée SÉQUENCE uniquement.

Historique : les routes /api/plans-de-travail/* avaient été supprimées en
v0.15.1 (l'atelier « Référentiel > Documents à publier » couvrait alors la
compilation du livret annuel des plans de travail). Mais l'onglet « Rendu
PDF » de l'atelier d'assemblage de séquence-niveau conserve un bouton
« Compiler le plan de travail » qui compile le plan de travail de LA séquence
courante (une page par partie, sans page de titre) — pratique pour vérifier
le rendu pendant l'édition. Ce bouton pointait vers une route disparue (404).

On réintroduit donc UNIQUEMENT la portée séquence (le livret annuel reste géré
par l'atelier Référentiel). Le service `generer_plan_de_travail_sequence` n'a
jamais été supprimé ; seule la couche HTTP manquait.

Routes :
    POST/GET /api/plans-de-travail/<niveau>/<sequence_code>/pdf
    POST/GET /api/plans-de-travail/<niveau>/<sequence_code>/tex

Pattern aligné sur routes/livret_sequence.py (helpers config/cache, validation
de surface, compilation via services.compilateur_pdf.compiler_atome).
"""

from __future__ import annotations
from pathlib import Path

from flask import Blueprint, jsonify, request, current_app, Response

from services.livret_plans_de_travail import (
    generer_plan_de_travail_sequence,
    SequenceParNiveauIntrouvable,
)
from services.compilateur_pdf import compiler_atome
from services.configuration import Configuration

bp = Blueprint('plans_de_travail', __name__)


# ── Helpers (alignés sur routes/livret_sequence.py) ──────────────────────────

def _configuration() -> Configuration:
    if not hasattr(current_app, 'configuration'):
        current_app.configuration = Configuration(
            current_app.json_store.data_dir
        )
    return current_app.configuration


def _cache_dir() -> Path:
    return current_app.json_store.data_dir / 'cache_rendus'


def _racine_appli() -> Path:
    return Path(current_app.root_path)


_NIVEAUX_VALIDES = ('N09', 'N10', 'N11', 'N12')


def _valider_niveau_sequence(niveau: str, sequence: str):
    if niveau not in _NIVEAUX_VALIDES:
        return jsonify({
            'error': f"niveau invalide : {niveau!r}",
            'valeurs_attendues': list(_NIVEAUX_VALIDES),
        }), 400
    if not (sequence.startswith('S') and sequence[1:].isdigit()
            and len(sequence) <= 4):
        return jsonify({
            'error': f"sequence invalide : {sequence!r}",
            'format_attendu': "S<numero> (ex. S01, S14)",
        }), 400
    return None


def _generer_tex(niveau: str, sequence: str) -> str:
    """Génère le .tex du plan de travail de la séquence. Peut lever
    SequenceParNiveauIntrouvable (→ 404) ou une autre exception (→ 500)."""
    config = _configuration()
    with current_app.json_store._conn() as conn:
        return generer_plan_de_travail_sequence(
            conn, niveau, sequence,
            tikz_libraries=config.tikz_libraries(),
            tblr_libraries=config.tblr_libraries(),
        )


# ── Route : .tex source ──────────────────────────────────────────────────────

@bp.route('/api/plans-de-travail/<niveau>/<sequence_code>/tex',
          methods=['POST', 'GET'])
def api_plan_travail_sequence_tex(niveau: str, sequence_code: str):
    erreur = _valider_niveau_sequence(niveau, sequence_code)
    if erreur:
        return erreur
    try:
        tex = _generer_tex(niveau, sequence_code)
    except SequenceParNiveauIntrouvable as e:
        return jsonify({'error': 'sequence_introuvable', 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'error': 'erreur_generation_tex', 'message': str(e)}), 500
    return Response(tex, mimetype='text/plain; charset=utf-8')


# ── Route : PDF compilé ──────────────────────────────────────────────────────

@bp.route('/api/plans-de-travail/<niveau>/<sequence_code>/pdf',
          methods=['POST', 'GET'])
def api_plan_travail_sequence_pdf(niveau: str, sequence_code: str):
    """Compile le plan de travail de la séquence et renvoie le PDF.

    Réponses :
      200 application/pdf : PDF compilé (ou servi depuis le cache)
      400 JSON           : niveau/sequence invalide
      404 JSON           : séquence inconnue ou sans partie assemblée
      422 JSON           : compilation LaTeX échouée (détail des erreurs)
      500 JSON           : erreur lors de la génération du .tex
      503 JSON           : pdflatex introuvable ou timeout
    """
    erreur = _valider_niveau_sequence(niveau, sequence_code)
    if erreur:
        return erreur

    # 1. Génération du .tex
    try:
        tex = _generer_tex(niveau, sequence_code)
    except SequenceParNiveauIntrouvable as e:
        return jsonify({'error': 'sequence_introuvable', 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'error': 'erreur_generation_tex', 'message': str(e)}), 500

    # 2. Compilation (réutilise le cache de compilateur_pdf). Timeout long :
    # le plan de travail d'une séquence reste modeste mais peut contenir du
    # TikZ (repères) — on s'aligne sur le livret de séquence par prudence.
    config = _configuration()
    dossier_images = Path(current_app.json_store.data_dir) / 'images'
    resultat = compiler_atome(
        tex_source=tex,
        racine_sources=config.chemin_sources_livrets(),
        cache_dir=_cache_dir(),
        pdflatex=config.chemin_pdflatex(),
        racine_appli=_racine_appli(),
        timeout=config.timeout_compilation_long(),
        dossier_images=dossier_images if dossier_images.is_dir() else None,
    )

    if resultat.ok:
        return Response(
            resultat.pdf_bytes,
            mimetype='application/pdf',
            headers={
                'X-Seq-Depuis-Cache': '1' if resultat.depuis_cache else '0',
                'X-Seq-Duree-Ms': str(resultat.duree_ms),
            },
        )

    # 3. Échec compilation : 503 si infrastructure, 422 si erreur LaTeX.
    msg_principal = (
        resultat.erreurs[0].message if resultat.erreurs
        else 'Erreur inconnue de compilation.'
    )
    code_http = 422
    if 'pdflatex introuvable' in msg_principal.lower():
        code_http = 503
    elif 'timeout' in msg_principal.lower():
        code_http = 503
    return jsonify({
        'error': 'compilation_echouee',
        'message': msg_principal,
        'erreurs': [
            {'ligne': e.ligne, 'message': e.message, 'contexte': e.contexte}
            for e in resultat.erreurs
        ],
        'log_complet': resultat.log_complet,
        'duree_ms': resultat.duree_ms,
    }), code_http
