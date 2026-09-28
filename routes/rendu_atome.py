r"""
routes/rendu_atome.py — Compilation PDF d'un atome isolé.

Expose :
  POST /api/atomes/<type_atome>/<atome_id>/rendu-pdf
    → compile l'atome et renvoie le PDF en application/pdf
      ou 422 JSON avec les erreurs de compilation

  GET  /api/atomes/<type_atome>/<atome_id>/rendu-pdf/info
    → v0.14.2 — Indique si un PDF est en cache et valide pour cet
      atome, sans déclencher de compilation. Permet à l'UI de faire
      un auto-chargement quand le cache est à jour.

  GET  /api/atomes/<type_atome>/<atome_id>/rendu-tex
    → renvoie le .tex source (sans compilation) pour debug

  GET  /api/atomes/<type_atome>/<atome_id>/rendu-log
    → renvoie le log pdflatex complet de la dernière compilation (si cache)

  GET  /api/configuration
  POST /api/configuration
    → lecture et écriture de la configuration utilisateur.

v0.14.2 — `type_atome` accepte maintenant 'carte' en plus des 4 types
classiques (exercice, notion, methode, fiche). La carte conserve aussi
ses anciennes routes /api/cartes/<id>/... en alias temporaire dans
routes/cartes_automatisme.py (à supprimer en v0.14.4 quand le client
sera basculé).
"""

from __future__ import annotations
from pathlib import Path

from flask import Blueprint, jsonify, request, current_app, Response

from services.latex_rendu_atome import (
    generer_tex_par_type,
    TABLES_ATOMES,
    TYPES_ATOMES_TOUS,
)
from services.compilateur_pdf import (
    compiler_atome,
    hash_tex,
    chemin_pdf_cache,
    chemin_log_cache,
)
from services.configuration import Configuration


bp = Blueprint('rendu_atome', __name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _configuration() -> Configuration:
    """Accès à la configuration utilisateur (mis en cache sur app)."""
    if not hasattr(current_app, 'configuration'):
        current_app.configuration = Configuration(
            current_app.json_store.data_dir
        )
    return current_app.configuration


def _cache_dir() -> Path:
    """Dossier de cache des PDFs rendus."""
    return current_app.json_store.data_dir / 'cache_rendus'


def _racine_appli() -> Path:
    """Racine de l'appli (pour détection MiKTeX portable)."""
    return Path(current_app.root_path)


def _valider_type(type_atome: str):
    """Lève 400 si type_atome n'est pas dans TYPES_ATOMES_TOUS.

    v0.14.2 — Élargi pour inclure 'carte' à côté des 4 types classiques
    (exercice, notion, methode, fiche). La validation reste basée sur
    un set explicite pour rejeter clairement les types inconnus
    (typo, ancienne version cliente, etc.).
    """
    if type_atome not in TYPES_ATOMES_TOUS:
        return jsonify({
            'error': f"type_atome invalide : {type_atome!r}",
            'valeurs_attendues': sorted(TYPES_ATOMES_TOUS),
        }), 400
    return None


# ── Rendu .tex (pour debug / inspection) ─────────────────────────────────────

@bp.route('/api/atomes/<type_atome>/<atome_id>/rendu-tex', methods=['GET'])
def api_rendu_tex(type_atome: str, atome_id: str):
    """Renvoie le .tex source qui serait compilé pour cet atome.

    Utile pour debug : voir exactement ce qui est envoyé à pdflatex.
    """
    erreur = _valider_type(type_atome)
    if erreur:
        return erreur

    config = _configuration()
    racine_sources = config.chemin_sources_livrets()

    try:
        with current_app.json_store._conn() as conn:
            tex = generer_tex_par_type(conn, type_atome, atome_id, racine_sources,
                                            tikz_libraries=config.tikz_libraries(),
                                            tblr_libraries=config.tblr_libraries())
    except LookupError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    return Response(tex, mimetype='text/plain; charset=utf-8')


# ── Information de cache (v0.14.2) ───────────────────────────────────────────

@bp.route('/api/atomes/<type_atome>/<atome_id>/rendu-pdf/info', methods=['GET'])
def api_rendu_pdf_info(type_atome: str, atome_id: str):
    """v0.14.2 — Indique si un PDF est en cache et valide pour cet atome.

    Permet à l'UI de savoir, AVANT de cliquer « Compiler », s'il existe
    déjà un PDF à jour pour cet atome. Si oui, l'UI peut faire un
    POST /rendu-pdf qui sera servi instantanément depuis le cache
    (X-Seq-Depuis-Cache=1).

    Coût côté serveur : génération du .tex (rapide, ms) + hashage +
    vérification d'existence du fichier. **Aucune compilation pdflatex.**

    Réponses :
      200 JSON {cache_valide: bool}                : OK
      400 JSON                                     : type_atome invalide
      404 JSON                                     : atome introuvable
      200 JSON {cache_valide: false, raison, msg}  : la génération du .tex
                                                      a échoué (cas rare,
                                                      ex. carte mal formée).
                                                      On renvoie 200 pour que
                                                      le client fallback
                                                      proprement sur le bouton
                                                      Compiler.

    Pourquoi cette route :
      Avant v0.14.2, seul l'atelier Carte avait son endpoint /info
      (dans cartes_automatisme.py), introduit en v0.13.7.6.1. Les 4
      autres ateliers (exercice, notion, méthode, fiche) ne pouvaient
      pas auto-charger leur PDF en cache : l'utilisateur devait
      systématiquement cliquer Compiler. Cette route généralise la
      mécanique aux 5 ateliers via l'URL unifiée /api/atomes/<type>/...
    """
    erreur = _valider_type(type_atome)
    if erreur:
        return erreur

    config = _configuration()
    racine_sources = config.chemin_sources_livrets()

    try:
        with current_app.json_store._conn() as conn:
            tex = generer_tex_par_type(
                conn, type_atome, atome_id, racine_sources,
                tikz_libraries=config.tikz_libraries(),
                tblr_libraries=config.tblr_libraries(),
            )
    except LookupError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        # Cas pathologique : la génération du .tex elle-même a échoué
        # (atome présent mais corpus invalide, dépendance manquante, etc.).
        # On renvoie cache_valide=false pour que le client passe en mode
        # « cliquer Compiler » qui produira un message d'erreur explicite
        # à la compilation. Pas de propagation en 5xx ici : c'est une route
        # d'introspection, son rôle est d'être robuste.
        return jsonify({
            'cache_valide': False,
            'raison': 'tex_indisponible',
            'message': str(e),
        }), 200

    h = hash_tex(tex)
    pdf = chemin_pdf_cache(_cache_dir(), h)
    return jsonify({'cache_valide': pdf.is_file()}), 200


# ── Compilation PDF ──────────────────────────────────────────────────────────

@bp.route('/api/atomes/<type_atome>/<atome_id>/rendu-pdf', methods=['POST'])
def api_rendu_pdf(type_atome: str, atome_id: str):
    """Compile l'atome et renvoie le PDF.

    Réponses :
      200 application/pdf    : PDF compilé (ou servi depuis le cache)
      404 JSON               : atome introuvable
      400 JSON               : type_atome invalide
      422 JSON               : compilation échouée, détail des erreurs
      503 JSON               : pdflatex introuvable ou timeout
    """
    erreur = _valider_type(type_atome)
    if erreur:
        return erreur

    config = _configuration()
    racine_sources = config.chemin_sources_livrets()
    # v0.7 : dossier centralisé d'images, ajouté au TEXINPUTS pour que les
    # \includegraphics trouvent les images migrées (cf. scripts/migration_images.py).
    dossier_images = Path(current_app.json_store.data_dir) / 'images'

    # 1. Génération du .tex
    try:
        with current_app.json_store._conn() as conn:
            tex = generer_tex_par_type(conn, type_atome, atome_id, racine_sources,
                                            tikz_libraries=config.tikz_libraries(),
                                            tblr_libraries=config.tblr_libraries())
    except LookupError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    # 2. Compilation
    resultat = compiler_atome(
        tex_source=tex,
        racine_sources=racine_sources,
        cache_dir=_cache_dir(),
        pdflatex=config.chemin_pdflatex(),
        racine_appli=_racine_appli(),
        timeout=config.timeout_compilation_court(),
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

    # 3. Échec : distinguer infrastructure vs erreur de code LaTeX
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
            {
                'ligne': e.ligne,
                'message': e.message,
                'contexte': e.contexte,
            }
            for e in resultat.erreurs
        ],
        'duree_ms': resultat.duree_ms,
    }), code_http


# ── Log de compilation (pour debug) ──────────────────────────────────────────

@bp.route('/api/atomes/<type_atome>/<atome_id>/rendu-log', methods=['GET'])
def api_rendu_log(type_atome: str, atome_id: str):
    """Renvoie le log pdflatex de la dernière compilation en cache.

    404 si l'atome n'a jamais été compilé (pas de log en cache).
    """
    erreur = _valider_type(type_atome)
    if erreur:
        return erreur

    config = _configuration()
    racine_sources = config.chemin_sources_livrets()

    try:
        with current_app.json_store._conn() as conn:
            tex = generer_tex_par_type(conn, type_atome, atome_id, racine_sources,
                                            tikz_libraries=config.tikz_libraries(),
                                            tblr_libraries=config.tblr_libraries())
    except LookupError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    log_path = chemin_log_cache(_cache_dir(), hash_tex(tex))
    if not log_path.is_file():
        return jsonify({
            'error': 'pas_de_log',
            'message': "Cet atome n'a pas encore été compilé.",
        }), 404

    return Response(
        log_path.read_text(encoding='utf-8', errors='replace'),
        mimetype='text/plain; charset=utf-8',
    )


# ── Configuration utilisateur ────────────────────────────────────────────────

@bp.route('/api/configuration', methods=['GET'])
def api_get_configuration():
    """Lit la configuration courante (avec défauts appliqués)."""
    return jsonify(_configuration().charger())


@bp.route('/api/configuration', methods=['POST'])
def api_set_configuration():
    """Met à jour une ou plusieurs clés de configuration.

    Seules les clés connues sont retenues (voir services.configuration.CLES_DEFAUT).
    Renvoie la configuration après mise à jour.
    """
    payload = request.get_json(force=True, silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({'error': 'payload attendu : objet JSON'}), 400
    updated = _configuration().enregistrer(payload)
    return jsonify(updated)


# v0.9 — Endpoint de résolution des chemins.
#
# Pourquoi distinct de /api/configuration : ce dernier renvoie les valeurs
# *brutes* stockées (un chemin vide reste vide), ce qui est le contrat
# attendu pour un éditeur de configuration (l'UI Préférences distingue
# « override actif » de « dérivé » via la présence/absence de valeur).
# Cet endpoint applique en plus la règle de dérivation depuis la racine,
# ce qui évite de la dupliquer côté frontend pour les usages de
# pré-remplissage (Admin > Import...) où on veut les valeurs effectives.
@bp.route('/api/configuration/chemins-resolus', methods=['GET'])
def api_chemins_resolus():
    """Retourne les chemins applicatifs avec dérivation depuis la racine
    appliquée. Inchangés côté UI Préférences : ce endpoint est destiné
    aux composants qui veulent juste « la valeur à utiliser » sans avoir
    à se soucier d'override/dérivation.

    Retour :
      {
        "racine":                       str,  // chaîne brute (peut être vide)
        "chemin_sources_livrets":       str,  // résolu (override sinon dérivé sinon "")
        "chemin_pdflatex":              str,  // idem
        "chemin_paquet":                str,  // idem
        "chemin_reference_sequences":   str,  // idem
      }
    """
    config = _configuration()
    return jsonify({
        'racine':                     config.get('chemin_racine_seqenseigne', '') or '',
        'chemin_sources_livrets':     config._resoudre_chemin('chemin_sources_livrets'),
        'chemin_pdflatex':            config._resoudre_chemin('chemin_pdflatex'),
        'chemin_paquet':              config._resoudre_chemin('chemin_paquet'),
        'chemin_reference_sequences': config._resoudre_chemin('chemin_reference_sequences'),
    })
