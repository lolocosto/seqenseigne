r"""
routes/livret_sequence.py — Génération du Livret de séquence (v0.11.2).

Expose :
  POST /api/v2/livret-sequence/<niveau>/<sequence>/rendu-tex
    body JSON optionnel : {"options": {...}, "gabarit": "cycle4"|"sixieme"}
    v0.52.1 : sans `gabarit`, celui du référentiel interne en cours du
    niveau, sinon celui du niveau (N09 → livret 6e) ; voir _gabarit_demande.
    → renvoie le source .tex (utile pour debug/inspection)

  GET  /api/v2/livret-sequence/<niveau>/<sequence>/mer  (v0.53.1)
    → parties et contrôle MR6 d'une séquence de mise en route (Mnn)

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
    # v0.53.0 (MR5) — et M01…M07 : documents d'une séquence de mise en route.
    from services.mises_en_route_6e import est_sequence_mer
    if not ((sequence.startswith('S') and sequence[1:].isdigit() and len(sequence) <= 4)
            or est_sequence_mer(sequence)):
        return jsonify({
            'error': f"sequence invalide : {sequence!r}",
            'format_attendu': "S<numero> (ex. S01, S14) ou M<numero> (mise en route)",
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


# ── v0.52.1 — Gabarit de documents (livret 6e) ──────────────────────────────

def _gabarit_demande(conn, niveau: str) -> str:
    """Décision R1 (v0.52.1) — gabarit du livret produit par l'atelier :
      1. paramètre explicite `gabarit` (body JSON ou query string) ;
      2. sinon le gabarit du référentiel interne principal « en_cours » le
         plus récent du niveau ;
      3. sinon la valeur proposée pour le niveau (N09 → sixieme, N10 à N12
         → cycle4).
    Sans paramètre, un niveau du cycle 4 dont aucun référentiel en cours
    n'a choisi « sixieme » produit donc le livret du cycle 4, comme avant."""
    from services import gabarits_documents as gd
    payload = request.get_json(silent=True) if request.is_json else None
    explicite = (payload or {}).get('gabarit') if isinstance(payload, dict) else None
    explicite = explicite or request.args.get('gabarit')
    if explicite:
        return gd.valider_gabarit(explicite)
    return gd.gabarit_atelier_du_niveau(conn, niveau)     # v0.52.2 : partagé


def _options_6e_depuis_request() -> dict:
    """Options du livret 6e : `options` du body (clés du cycle 4 ignorées),
    `version` aussi accepté en query string (?version=corrigee)."""
    payload = request.get_json(silent=True) if request.is_json else None
    opts = dict((payload or {}).get('options') or {}) if isinstance(payload, dict) else {}
    if request.args.get('version'):
        opts['version'] = request.args.get('version')
    return opts


def _options_mer_depuis_request() -> dict:
    """v0.53.0 (MR5) — options d'un document de mise en route : `options.mer`
    du body (document, version, par_page, exemplaires, sujet, test), les
    mêmes clés acceptées en query string (?document=planche&par_page=2)."""
    payload = request.get_json(silent=True) if request.is_json else None
    opts = {}
    if isinstance(payload, dict):
        o = payload.get('options') or {}
        if isinstance(o, dict) and isinstance(o.get('mer'), dict):
            opts.update(o['mer'])
    # v0.53.1 (MR5 révisé) — `partie` (absente ou 0 : toute la séquence).
    for k in ('document', 'version', 'par_page', 'exemplaires', 'sujet', 'test', 'partie'):
        if request.args.get(k):
            opts[k] = request.args.get(k)
    return opts


def _generer_tex(conn, niveau: str, sequence: str, config) -> str:
    """.tex du livret selon le gabarit (R1). Lève ValueError si options
    ou gabarit invalides.

    v0.53.0 (MR5) — Séquence de mise en route (Mnn) : le document demandé
    (fiche de cours, exercices de séance, test court, plan de séquence),
    au modèle « Fiches » (services/mises_en_route_6e.py)."""
    from services.mises_en_route_6e import est_sequence_mer, generer_document_mer
    if est_sequence_mer(sequence):
        return generer_document_mer(
            conn, niveau, sequence, options=_options_mer_depuis_request(),
            tikz_libraries=config.tikz_libraries(),
            tblr_libraries=config.tblr_libraries())
    from services.gabarits_documents import GabaritErreur
    try:
        gabarit = _gabarit_demande(conn, niveau)
    except GabaritErreur as e:
        raise ValueError(str(e)) from e
    if gabarit == 'sixieme':
        from services.livret_sequence_6e import generer_livret_sequence_6e
        return generer_livret_sequence_6e(
            conn, niveau, sequence, options=_options_6e_depuis_request(),
            tikz_libraries=config.tikz_libraries(),
            tblr_libraries=config.tblr_libraries())
    return generer_livret_sequence(
        conn, niveau, sequence,
        options=_options_depuis_request(),
        tikz_libraries=config.tikz_libraries(),
        tblr_libraries=config.tblr_libraries(),
    )


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

    config = _configuration()

    try:
        with current_app.json_store._conn() as conn:
            tex = _generer_tex(conn, niveau, sequence, config)
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


# ── v0.53.1 — Route : résumé d'une séquence de mise en route ────────────────

@bp.route('/api/v2/livret-sequence/<niveau>/<sequence>/mer', methods=['GET'])
def api_livret_sequence_mer(niveau: str, sequence: str):
    """v0.53.1 (MR5, MR6 révisés) — Pour l'onglet « Rendu PDF » d'une
    séquence de mise en route : ses parties (choix de la partie du document)
    et son contrôle MR6 par partie (affiché dans l'atelier). Catégorie
    « atelier » (blueprint livret_sequence, services/profils.py).

    Réponses : 200 JSON (services.mises_en_route_6e.resume_mer) ; 400 si la
    séquence n'est pas une mise en route ; 404 si elle est absente de
    l'atelier."""
    from services.mises_en_route_6e import MiseEnRouteErreur, est_sequence_mer, resume_mer
    erreur = _valider_niveau_sequence(niveau, sequence)
    if erreur:
        return erreur
    if not est_sequence_mer(sequence):
        return jsonify({'error': 'pas_une_mise_en_route',
                        'message': f"{sequence} n'est pas une séquence de mise en route"}), 400
    try:
        with current_app.json_store._conn() as conn:
            return jsonify(resume_mer(conn, niveau, sequence))
    except MiseEnRouteErreur as e:
        return jsonify({'error': 'mise_en_route_absente', 'message': str(e)}), 404


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

    config = _configuration()
    racine_sources = config.chemin_sources_livrets()
    dossier_images = Path(current_app.json_store.data_dir) / 'images'

    # 1. Génération du .tex (v0.52.1 : selon le gabarit, cf. _gabarit_demande)
    try:
        with current_app.json_store._conn() as conn:
            tex = _generer_tex(conn, niveau, sequence, config)
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


# ── v0.53.3 (D-TOUT) — « Tout compiler » d'une séquence de mise en route ─────
#
# GET /api/v2/livret-sequence/<niveau>/<Mnn>/mer/tout-compiler?partie=n
#     → text/event-stream (EventSource) : debut, un événement par document,
#       puis fin (archive ZIP) ou abandon ; la fermeture de la connexion par
#       le navigateur annule (comme le rendu par lot, routes/admin.py).
# GET /api/v2/livret-sequence/mer/archive/<nom>.zip → l'archive des PDF.
# GET /api/v2/livret-sequence/mer/echec/<nom>.log|.tex → log d'un échec.
# Catégorie « atelier » (blueprint livret_sequence, services/profils.py).

@bp.route('/api/v2/livret-sequence/<niveau>/<sequence>/mer/tout-compiler', methods=['GET'])
def api_livret_sequence_mer_tout_compiler(niveau: str, sequence: str):
    from services.mer_tout_compiler import iter_tout_compiler
    from services.mises_en_route_6e import (MiseEnRouteErreur, _partie_option,
                                            est_sequence_mer, lire_sequence_mer, partie_de)
    from services.compilation_batch import evenement_vers_sse
    from flask import stream_with_context
    erreur = _valider_niveau_sequence(niveau, sequence)
    if erreur:
        return erreur
    if not est_sequence_mer(sequence):
        return jsonify({'error': 'pas_une_mise_en_route',
                        'message': f"{sequence} n'est pas une séquence de mise en route"}), 400
    js = current_app.json_store
    try:
        partie = _partie_option(request.args.get('partie'))
        with js._conn() as conn:
            s = lire_sequence_mer(conn, niveau, sequence)
            if partie is not None:
                partie_de(s, partie)
    except MiseEnRouteErreur as e:
        return jsonify({'error': 'options_invalides', 'message': str(e)}), 400
    config = _configuration()
    dossier_images = Path(js.data_dir) / 'images'
    racine_sources = config.chemin_sources_livrets()
    pdflatex = config.chemin_pdflatex()
    timeout = config.timeout_compilation_long()
    cache_dir = _cache_dir()
    racine_appli = _racine_appli()

    def compiler(tex):
        return compiler_atome(tex_source=tex, racine_sources=racine_sources,
                              cache_dir=cache_dir, pdflatex=pdflatex,
                              racine_appli=racine_appli, timeout=timeout,
                              dossier_images=dossier_images if dossier_images.is_dir() else None)

    def generateur():
        try:
            for ev in iter_tout_compiler(
                    js._conn, niveau, sequence, partie, compiler=compiler,
                    tikz_libraries=config.tikz_libraries(),
                    tblr_libraries=config.tblr_libraries(),
                    dossier_echecs=cache_dir / 'echecs_mer',
                    dossier_archives=Path(js.data_dir) / 'rapports',
                    max_erreurs_consecutives=config.compilation_batch_max_erreurs_consecutives()):
                yield evenement_vers_sse(ev)
        except GeneratorExit:                       # annulation depuis l'interface
            raise
        except Exception as e:
            yield evenement_vers_sse({'kind': 'erreur_serveur',
                                      'message': f"{type(e).__name__}: {e}"})

    return Response(stream_with_context(generateur()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@bp.route('/api/v2/livret-sequence/mer/archive/<nom>', methods=['GET'])
def api_livret_sequence_mer_archive(nom: str):
    from flask import send_file
    from services.mer_tout_compiler import nom_sur
    if not nom_sur(nom, ('.zip',)):
        return jsonify({'error': 'Nom d\'archive invalide.'}), 400
    chemin = Path(current_app.json_store.data_dir) / 'rapports' / nom
    if not chemin.is_file():
        return jsonify({'error': 'Archive introuvable.'}), 404
    return send_file(chemin, mimetype='application/zip', as_attachment=True, download_name=nom)


@bp.route('/api/v2/livret-sequence/mer/echec/<nom>', methods=['GET'])
def api_livret_sequence_mer_echec(nom: str):
    from flask import send_file
    from services.mer_tout_compiler import nom_sur
    if not nom_sur(nom, ('.log', '.tex')):
        return jsonify({'error': 'Nom de fichier invalide.'}), 400
    chemin = _cache_dir() / 'echecs_mer' / nom
    if not chemin.is_file():
        return jsonify({'error': 'Fichier introuvable.'}), 404
    return send_file(chemin, mimetype='text/plain; charset=utf-8', as_attachment=False,
                     download_name=nom)
