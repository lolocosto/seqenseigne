r"""
routes/livret_sequence.py — Génération du Livret de séquence (v0.11.2).

Expose :
  POST /api/v2/livret-sequence/<niveau>/<sequence>/rendu-tex
    body JSON optionnel : {"options": {...}}
    → renvoie le source .tex (utile pour debug/inspection)

  POST /api/v2/livret-sequence/<niveau>/<sequence>/rendu-pdf
    body JSON optionnel : {"options": {...}}
    → compile et renvoie le PDF en application/pdf
      ou 422 JSON avec les erreurs de compilation
      ou 503 JSON si pdflatex introuvable / timeout

Le format `options` est piloté par services.livret_sequence.normaliser_options.
Cf. options_par_defaut() pour la structure complète. Une option absente vaut
True (toggle actif) — le caller peut donc envoyer juste `{}` pour le livret
« tout en un ».

Le mécanisme de cache de compilation (services/compilateur_pdf.py) est
réutilisé tel quel : la clé étant le hash sha256 du .tex, deux générations
identiques renverront le PDF depuis le cache. NB : le hash inclut les
options puisqu'elles font partie du .tex généré.
"""

from __future__ import annotations
from pathlib import Path

from flask import Blueprint, jsonify, request, current_app, Response

from services.livret_sequence import generer_livret_sequence, normaliser_options
from services.compilateur_pdf import compiler_atome
from services.configuration import Configuration


bp = Blueprint('livret_sequence', __name__)


# ── Helpers (alignés sur routes/recap_cours.py) ──────────────────────────────

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
    """Validation de surface : niveau dans la liste connue, sequence au
    format S01..S14. Le service lève une erreur si la combinaison
    niveau/sequence n'existe pas en BDD ; on laisse cette responsabilité
    au service plutôt que de re-vérifier ici (DRY).
    """
    if niveau not in _NIVEAUX_VALIDES:
        return jsonify({
            'error': f"niveau invalide : {niveau!r}",
            'valeurs_attendues': list(_NIVEAUX_VALIDES),
        }), 400
    # Format S01..S14 : on accepte un peu plus large pour ne pas avoir
    # à mettre à jour ici à chaque ajout de séquence en BDD.
    if not (sequence.startswith('S') and sequence[1:].isdigit() and len(sequence) <= 4):
        return jsonify({
            'error': f"sequence invalide : {sequence!r}",
            'format_attendu': "S<numero> (ex. S01, S14)",
        }), 400
    return None


def _options_depuis_request() -> dict:
    """Lit les options depuis le body JSON de la requête.

    Tolérant : si pas de body, body vide, ou pas de clé 'options', on
    retombe sur les défauts (livret « tout en un »). Si options est mal
    formé, normaliser_options absorbera les valeurs malformées.
    """
    if not request.is_json:
        return normaliser_options(None)
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return normaliser_options(None)
    return normaliser_options(payload.get('options'))


# ── Route : .tex source ──────────────────────────────────────────────────────

@bp.route('/api/v2/livret-sequence/<niveau>/<sequence>/rendu-tex',
          methods=['POST', 'GET'])
def api_livret_sequence_tex(niveau: str, sequence: str):
    """Renvoie le .tex source qui serait compilé pour le livret de la séquence.

    Réponses :
      200 text/plain         : source .tex
      400 JSON               : niveau/sequence invalide
      500 JSON               : erreur lors de la génération

    On accepte GET pour faciliter l'inspection rapide depuis un navigateur.
    """
    erreur = _valider_niveau_sequence(niveau, sequence)
    if erreur:
        return erreur

    options = _options_depuis_request()
    config = _configuration()

    try:
        with current_app.json_store._conn() as conn:
            tex = generer_livret_sequence(
                conn, niveau, sequence,
                options=options,
                tikz_libraries=config.tikz_libraries(),
                tblr_libraries=config.tblr_libraries(),
            )
    except ValueError as e:
        # v0.11.3 — Options invalides (ex : ni cours ni exercices à inclure).
        # Cas distinct des erreurs internes : c'est l'appelant qui a tort.
        return jsonify({
            'error': 'options_invalides',
            'message': str(e),
        }), 400
    except Exception as e:
        return jsonify({
            'error': 'erreur_generation_tex',
            'message': str(e),
        }), 500

    return Response(tex, mimetype='text/plain; charset=utf-8')


# ── Route : compilation PDF ──────────────────────────────────────────────────

@bp.route('/api/v2/livret-sequence/<niveau>/<sequence>/rendu-pdf',
          methods=['POST', 'GET'])
def api_livret_sequence_pdf(niveau: str, sequence: str):
    """Compile le livret de la séquence et renvoie le PDF.

    Réponses :
      200 application/pdf    : PDF compilé (ou servi depuis le cache)
      400 JSON               : niveau/sequence invalide
      422 JSON               : compilation échouée, détail des erreurs
      500 JSON               : erreur lors de la génération du .tex
      503 JSON               : pdflatex introuvable ou timeout

    Pattern aligné sur routes/recap_cours.py : timeout long (un livret de
    séquence peut agréger ~15-30 atomes, dont du TikZ). Le cache de
    compilation côté compilateur_pdf est réutilisé tel quel.
    """
    erreur = _valider_niveau_sequence(niveau, sequence)
    if erreur:
        return erreur

    options = _options_depuis_request()
    config = _configuration()
    racine_sources = config.chemin_sources_livrets()
    dossier_images = Path(current_app.json_store.data_dir) / 'images'

    # 1. Génération du .tex
    try:
        with current_app.json_store._conn() as conn:
            tex = generer_livret_sequence(
                conn, niveau, sequence,
                options=options,
                tikz_libraries=config.tikz_libraries(),
                tblr_libraries=config.tblr_libraries(),
            )
    except ValueError as e:
        return jsonify({
            'error': 'options_invalides',
            'message': str(e),
        }), 400
    except Exception as e:
        return jsonify({
            'error': 'erreur_generation_tex',
            'message': str(e),
        }), 500

    # 2. Compilation (réutilise le cache de compilateur_pdf).
    # Timeout long : un livret de séquence agrège de nombreux atomes.
    # Pas autant qu'un récap annuel mais largement plus qu'un atome
    # isolé — le timeout court (~30s) ne suffit pas en pratique.
    resultat = compiler_atome(
        tex_source=tex,
        racine_sources=racine_sources,
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

    # 3. Échec : distinguer infrastructure vs erreur LaTeX.
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
        # Log complet exposé pour faciliter le diagnostic des erreurs LaTeX
        # qui se manifestent uniquement en mode agrégé (cf. recap_cours.py).
        'log_complet': resultat.log_complet,
        'duree_ms': resultat.duree_ms,
    }), code_http
