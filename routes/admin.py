"""routes/admin.py — Administration : statut, reset, qualité, export/import SQLite.

Nettoyage post-R4e4b :
  - Suppression de la route /api/admin/generer-yaml (la génération YAML
    depuis les livrets importés n'est plus exposée dans l'UI).
  - La route /api/admin/migrer-sqlite avait déjà disparu lors du nettoyage
    A+B (le bouton UI qui l'appelait est supprimé dans la présente
    livraison).
"""

from flask import Blueprint, jsonify, request, current_app
from services import admin as svc
from services import atomes as svc_atomes

bp = Blueprint("admin", __name__)


def _stores():
    a = current_app
    return a.json_store, a.yaml_store, a.csv_store


@bp.route("/api/admin/statut", methods=["GET"])
def api_admin_statut():
    js, ys, cs = _stores()
    return jsonify(svc.statut_bdd(js, ys, cs))


@bp.route("/api/admin/reset/reference", methods=["POST"])
def api_admin_reset_reference():
    js, _, _ = _stores()
    try:
        vides = js.reset_reference()
        return jsonify({"ok": True, "vides": vides})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/admin/reset/suivi", methods=["POST"])
def api_admin_reset_suivi():
    js, _, _ = _stores()
    try:
        vides = js.reset_suivi()
        return jsonify({"ok": True, "vides": vides})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# v0.6.4 — Reset des tables paquet (mise en forme LaTeX importée en BDD)
@bp.route("/api/admin/reset/paquet", methods=["POST"])
def api_admin_reset_paquet():
    js, _, _ = _stores()
    try:
        with js._conn() as conn:
            # Les 2 tables peuvent ne pas exister si le peuplement n'a
            # jamais été lancé — IF EXISTS évite l'erreur.
            try:
                conn.execute("DELETE FROM paquet_definitions")
            except Exception:
                pass
            try:
                conn.execute("DELETE FROM paquet_requirepackage")
            except Exception:
                pass
        return jsonify({"ok": True, "vides": ["paquet_definitions",
                                              "paquet_requirepackage"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# v0.6.4 — Import du paquet seqenseigne depuis un dossier de fichiers .sty.
@bp.route("/api/admin/paquet/import", methods=["POST"])
def api_admin_paquet_import():
    """Importe les fichiers .sty du paquet seqenseigne dans les tables
    paquet_definitions et paquet_requirepackage. Réutilise la fonction
    `peupler` du script peuplement_14, qui parse les .sty et applique
    les règles de rendu atomique.

    Body JSON : {"chemin": "../reference/paquet"}
      chemin est relatif au dossier de l'application (cwd), ou absolu.
    """
    from pathlib import Path
    import sys

    js, _, _ = _stores()
    data = request.get_json(silent=True) or {}
    chemin = (data.get("chemin") or "").strip()
    if not chemin:
        return jsonify({"error": "Chemin du dossier paquet requis."}), 400

    # Importer la fonction peupler depuis le script.
    # Note : le script attend des FICHIERS_ORDRE précis (core, theme, data,
    # legacy). Si le dossier ne les contient pas tous, peupler() lève
    # FileNotFoundError, ce qu'on relaie comme erreur 400.
    try:
        # Le script est dans scripts/, il est listé dans sys.path par
        # certains contextes mais pas tous — on l'ajoute au besoin.
        scripts_dir = str(Path(__file__).parent.parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from peuplement_14_paquet_vers_base import peupler, formatter_rapport

        rapport = peupler(Path(js.db_path), Path(chemin))

        # Re-calcul des stats pour la réponse
        with js._conn() as conn:
            macros = conn.execute(
                "SELECT COUNT(*) FROM paquet_definitions WHERE type_latex='command'"
            ).fetchone()[0]
            envs = conn.execute(
                "SELECT COUNT(*) FROM paquet_definitions WHERE type_latex='environment'"
            ).fetchone()[0]
            req = conn.execute(
                "SELECT COUNT(*) FROM paquet_requirepackage"
            ).fetchone()[0]

        return jsonify({
            "ok": True,
            "macros": macros,
            "environnements": envs,
            "requirepackage": req,
            "log": formatter_rapport(rapport),
        })
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500


# v0.7 — Migration des images vers appli/data/images/
#
# Deux endpoints jumeaux :
#   POST /api/admin/images/preview  — analyse + simulation, sans toucher au disque
#   POST /api/admin/images/apply    — exécute réellement la migration
#
# Body JSON commun : {"chemin_reference": "../reference/sequences"}
#   Le chemin est relatif au dossier de l'application (cwd), ou absolu.
#   La cible est toujours data/images/ relativement au data_dir du store.

def _executer_migration_images(dry_run: bool):
    """Helper commun aux deux endpoints. Retourne un tuple (response, code_http)."""
    from pathlib import Path
    import sys

    js, _, _ = _stores()
    data = request.get_json(silent=True) or {}
    chemin_reference = (data.get("chemin_reference") or "").strip()
    if not chemin_reference:
        return jsonify({
            "error": "Chemin de l'arborescence de référence requis."
        }), 400

    racine = Path(chemin_reference)
    if not racine.is_dir():
        return jsonify({
            "error": f"Dossier introuvable : {chemin_reference}"
        }), 400

    # Le dossier images est toujours <data_dir>/images.
    dossier_images = Path(js.data_dir) / "images"

    # Importer le module migration_images depuis scripts/.
    scripts_dir = str(Path(__file__).parent.parent / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        from migration_images import (
            analyser, appliquer, formatter_rapport,
        )
    except ImportError as e:
        return jsonify({
            "error": f"Module migration_images introuvable : {e}"
        }), 500

    try:
        plan = analyser(racine, dossier_images)
        rapport = appliquer(plan, dry_run=dry_run)
        log = formatter_rapport(plan, rapport, dry_run=dry_run)
        return jsonify({
            "ok": True,
            "dry_run": dry_run,
            "images_copiees":     rapport["images_copiees"],
            "images_converties":  rapport["images_converties"],
            "images_skip":        rapport["images_skip"],
            "conflits":           rapport["conflits"],
            "tex_modifies":       rapport["tex_modifies"],
            "reecritures":        rapport["reecritures"],
            "introuvables":       rapport["introuvables"],
            "orphelines":         rapport["orphelines"],
            "log":                log,
        })
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500


@bp.route("/api/admin/images/preview", methods=["POST"])
def api_admin_images_preview():
    """Analyse + simulation sans rien écrire sur le disque.

    Body : {"chemin_reference": "../reference/sequences"}
    """
    return _executer_migration_images(dry_run=True)


@bp.route("/api/admin/images/apply", methods=["POST"])
def api_admin_images_apply():
    """Exécute réellement la migration : copie/conversion/réécriture .tex.

    Body : {"chemin_reference": "../reference/sequences"}
    """
    return _executer_migration_images(dry_run=False)


# ── v0.8 — Compilateur batch des atomes ──────────────────────────────────────
#
# Trois endpoints :
#   GET /api/admin/compilation-atomes/preview?type=&niveau=&sequence=
#       → JSON : nombre d'atomes éligibles + valeurs de configuration courantes
#   GET /api/admin/compilation-atomes/run?type=&niveau=&sequence=&timeout=&max_erreurs=
#       → text/event-stream : un événement SSE par atome compilé,
#         puis un événement final (kind=fin|abandon|annule).
#         GET parce que EventSource côté navigateur est GET-only.
#         Le rapport Markdown est écrit à la fin sous data/rapports/.
#   GET /api/admin/compilation-atomes/rapport/<nom>
#       → télécharge un rapport généré.
#
# Pourquoi pas de POST/SSE asynchrone séparé : le serveur Flask dev est
# mono-utilisateur, le job est lancé dans le thread de la requête SSE et
# se termine quand le client ferme la connexion (ou que le run se finit).

def _filtre_depuis_query():
    """Construit un Filtre depuis les paramètres GET, en validant les valeurs."""
    from services.compilation_batch import Filtre, TYPES_VALIDES
    type_ = (request.args.get('type') or '').strip().lower()
    niveau = (request.args.get('niveau') or '').strip().upper()
    sequence = (request.args.get('sequence') or '').strip().upper()
    if type_ and type_ not in TYPES_VALIDES:
        return None, f"type invalide : {type_!r}"
    if niveau and niveau not in ('N10', 'N11', 'N12'):
        return None, f"niveau invalide : {niveau!r}"
    if sequence and not (
        len(sequence) == 3 and sequence[0] == 'S' and sequence[1:].isdigit()
    ):
        return None, f"séquence invalide : {sequence!r}"
    return Filtre(type=type_, niveau=niveau, sequence=sequence), None


@bp.route("/api/admin/compilation-atomes/preview", methods=["GET"])
def api_compilation_atomes_preview():
    """Compte les atomes éligibles et renvoie la configuration courante.

    Query : type, niveau, sequence (chacun optionnel ; '' = tous)
    Réponse JSON :
      {
        "total": int,
        "par_type": {"notion": n, "methode": n, "exercice": n},
        "config": {
            "timeout_compilation_court_s": int,  # v0.10
            "timeout_compilation_long_s":  int,  # v0.10
            "compilation_batch_max_erreurs_consecutives": int,
            "tikz_libraries": str,
            "tblr_libraries": str
        }
      }
    """
    from services.compilation_batch import recenser_atomes, ORDRE_TYPES
    js, _, _ = _stores()

    filtre, err = _filtre_depuis_query()
    if err:
        return jsonify({"error": err}), 400

    atomes = recenser_atomes(js, filtre)
    # v0.18.0 — par_type couvre désormais les 5 types (fiche/carte inclus).
    par_type = {t: 0 for t in ORDRE_TYPES}
    for a in atomes:
        if a.type in par_type:
            par_type[a.type] += 1

    config = _configuration_admin().charger()
    # v0.10 — Migration douce : si timeout_compilation_court_s n'est pas
    # encore en config (ex. utilisateur n'ayant pas ouvert l'UI Admin
    # depuis la mise à jour), on retombe sur l'ancienne clé
    # timeout_compilation_s, sinon sur le défaut 30.
    timeout_court = config.get('timeout_compilation_court_s')
    if timeout_court is None:
        timeout_court = config.get('timeout_compilation_s', 30)
    return jsonify({
        "total": len(atomes),
        "par_type": par_type,
        "config": {
            "timeout_compilation_court_s": int(timeout_court),
            "timeout_compilation_long_s": int(config.get(
                "timeout_compilation_long_s", 300)),
            "compilation_batch_max_erreurs_consecutives": int(config.get(
                "compilation_batch_max_erreurs_consecutives", 5)),
            # v0.8.5 — Bibliothèques tikz à charger systématiquement.
            # On expose la valeur brute (chaîne CSV) au front-end qui
            # l'affiche telle quelle dans son input texte.
            "tikz_libraries": str(config.get(
                "tikz_libraries",
                "babel,shapes.geometric,arrows.meta,positioning,calc")),
            # v0.9.1 — Bibliothèques tabularray à charger systématiquement.
            # Même mécanisme que tikz_libraries.
            "tblr_libraries": str(config.get(
                "tblr_libraries",
                "booktabs,varwidth")),
        },
    })


@bp.route("/api/admin/compilation-atomes/run", methods=["GET"])
def api_compilation_atomes_run():
    """Compile en batch et streame les événements en SSE.

    Query :
      type, niveau, sequence : filtre (optionnel)
      timeout                : timeout pdflatex en secondes (optionnel,
                               override de la config). Si fourni, met aussi
                               à jour la config persistée pour les runs futurs.
      max_erreurs            : nombre d'erreurs infra consécutives avant
                               abandon (optionnel, idem timeout).
      tikz_libraries         : v0.8.5 — chaîne CSV des bibliothèques tikz
                               à charger systématiquement (optionnel ;
                               persiste dans la config si fourni). Une
                               chaîne vide est interprétée comme « aucune
                               lib » et persistée telle quelle.

    Réponse : text/event-stream, un événement par atome plus un final.
    """
    from pathlib import Path
    from services.compilation_batch import (
        iter_compilation, evenement_vers_sse,
        ecrire_rapport_md, nom_rapport,
    )
    from flask import Response, stream_with_context

    js, _, _ = _stores()

    filtre, err = _filtre_depuis_query()
    if err:
        return jsonify({"error": err}), 400

    # Override + persistance de la config si paramètres fournis.
    config = _configuration_admin()
    updates = {}
    # v0.10 — Accepte le paramètre `timeout_court` (nouveau nom) et,
    # par compat ascendante, l'ancien nom `timeout` qui désigne désormais
    # la même chose (timeout pour compilation d'atomes individuels — ce
    # que fait le batch).
    timeout_qs = (request.args.get('timeout_court')
                  or request.args.get('timeout') or '').strip()
    if timeout_qs:
        try:
            t = max(1, int(timeout_qs))
            updates['timeout_compilation_court_s'] = t
        except ValueError:
            return jsonify({"error": f"timeout_court invalide : {timeout_qs!r}"}), 400
    # v0.10 — Timeout pour compilations longues (récap cours, etc.).
    # Persisté ici car la page Admin > Rendu par lot expose les deux
    # timeouts dans la même UI pour la cohérence (les pourquoi sont
    # documentés dans l'aide accessible depuis l'UI).
    timeout_long_qs = (request.args.get('timeout_long') or '').strip()
    if timeout_long_qs:
        try:
            t = max(1, int(timeout_long_qs))
            updates['timeout_compilation_long_s'] = t
        except ValueError:
            return jsonify({
                "error": f"timeout_long invalide : {timeout_long_qs!r}"}), 400
    max_err_qs = (request.args.get('max_erreurs') or '').strip()
    if max_err_qs:
        try:
            n = max(1, int(max_err_qs))
            updates['compilation_batch_max_erreurs_consecutives'] = n
        except ValueError:
            return jsonify({
                "error": f"max_erreurs invalide : {max_err_qs!r}"}), 400
    # v0.8.5 — tikz_libraries (chaîne CSV).
    # On accepte tel quel, modulo un trim global. La validation fine
    # (parsing, dédup, élimination des vides) est faite par
    # Configuration.tikz_libraries() côté lecture, pas ici à l'écriture :
    # on veut conserver la chaîne saisie par l'utilisateur quasi telle
    # quelle pour qu'il la retrouve à l'identique au prochain affichage.
    # Valeur vide → on n'écrit rien (la valeur précédente est conservée).
    # Si l'utilisateur veut vider, il peut mettre un espace.
    tikz_libs_qs = request.args.get('tikz_libraries')
    if tikz_libs_qs is not None:
        # tikz_libs_qs peut être '' explicitement (utilisateur a vidé le
        # champ), on persiste alors une chaîne vide (= aucune lib chargée).
        updates['tikz_libraries'] = tikz_libs_qs.strip()
    # v0.9.1 — tblr_libraries (chaîne CSV). Même logique que tikz_libraries.
    tblr_libs_qs = request.args.get('tblr_libraries')
    if tblr_libs_qs is not None:
        updates['tblr_libraries'] = tblr_libs_qs.strip()
    if updates:
        config.enregistrer(updates)

    # v0.10 — Le batch compile des atomes individuels en boucle, donc
    # timeout court (typiquement 30s/atome).
    timeout = config.timeout_compilation_court()
    max_err = config.compilation_batch_max_erreurs_consecutives()
    racine_sources = config.chemin_sources_livrets()
    pdflatex = config.chemin_pdflatex()
    # v0.8.5 — Bibliothèques tikz à charger systématiquement.
    tikz_libraries = config.tikz_libraries()
    # v0.9.1 — Bibliothèques tabularray à charger systématiquement.
    tblr_libraries = config.tblr_libraries()

    # Dossier centralisé d'images (v0.7).
    dossier_images = Path(js.data_dir) / "images"
    if not dossier_images.is_dir():
        dossier_images = None

    cache_dir = Path(js.data_dir) / "cache_rendus"
    racine_appli = Path(current_app.root_path)

    # v0.8.3 — Dossier de conservation des fichiers d'échec (.tex + .log).
    # Le service `iter_compilation` purge ce dossier au début du run et y
    # écrit les .tex + .log de chaque atome qui plante (LaTeX ou infra).
    # Ça permet à l'utilisateur de récupérer le log complet de pdflatex
    # depuis l'UI au lieu d'avoir à fouiller dans un dossier temporaire
    # qui n'existe plus à la fin du run.
    dossier_echecs = cache_dir / "echecs"

    # Dossier de rapports v0.8.
    dossier_rapports = Path(js.data_dir) / "rapports"
    dossier_rapports.mkdir(parents=True, exist_ok=True)
    chemin_rapport = dossier_rapports / nom_rapport()

    def generateur():
        """Stream SSE : compile chaque atome, accumule les événements,
        écrit le rapport Markdown à la fin, et émet un dernier événement
        SSE 'rapport' avec le nom du fichier produit."""
        evenements: list[dict] = []
        try:
            for ev in iter_compilation(
                store=js,
                racine_sources=racine_sources,
                dossier_images=dossier_images,
                cache_dir=cache_dir,
                pdflatex=pdflatex,
                racine_appli=racine_appli,
                timeout=timeout,
                max_erreurs_consecutives=max_err,
                filtre=filtre,
                dossier_echecs=dossier_echecs,
                tikz_libraries=tikz_libraries,
                tblr_libraries=tblr_libraries,
            ):
                evenements.append(ev)
                yield evenement_vers_sse(ev)
        except GeneratorExit:
            # Le client a fermé la connexion (annulation depuis l'UI).
            # On ne yield plus rien, mais on tente quand même d'écrire le
            # rapport partiel pour ne pas perdre le travail déjà fait.
            try:
                ecrire_rapport_md(evenements, chemin_rapport, filtre)
            except Exception:
                pass
            raise
        except Exception as e:
            ev = {
                'kind': 'erreur_serveur',
                'message': f"{type(e).__name__}: {e}",
            }
            evenements.append(ev)
            yield evenement_vers_sse(ev)

        # Écriture du rapport Markdown.
        try:
            ecrire_rapport_md(evenements, chemin_rapport, filtre)
            yield evenement_vers_sse({
                'kind': 'rapport',
                'nom':  chemin_rapport.name,
                'url':  f"/api/admin/compilation-atomes/rapport/"
                        f"{chemin_rapport.name}",
            })
        except Exception as e:
            yield evenement_vers_sse({
                'kind': 'erreur_serveur',
                'message': f"Échec écriture rapport : "
                           f"{type(e).__name__}: {e}",
            })

    return Response(
        stream_with_context(generateur()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # désactive le buffering nginx si proxy
        },
    )


@bp.route("/api/admin/compilation-atomes/rapport/<nom>", methods=["GET"])
def api_compilation_atomes_rapport(nom):
    """Télécharge un rapport généré (sécurisé : nom uniquement, pas de chemin)."""
    from pathlib import Path
    from flask import send_file
    js, _, _ = _stores()
    # Sécurité : pas de slash, pas de '..', extension .md uniquement.
    if '/' in nom or '\\' in nom or '..' in nom or not nom.endswith('.md'):
        return jsonify({"error": "Nom de rapport invalide."}), 400
    chemin = Path(js.data_dir) / "rapports" / nom
    if not chemin.is_file():
        return jsonify({"error": "Rapport introuvable."}), 404
    return send_file(
        chemin,
        mimetype='text/markdown; charset=utf-8',
        as_attachment=True,
        download_name=nom,
    )


@bp.route("/api/admin/compilation-atomes/echec/<nom>", methods=["GET"])
def api_compilation_atomes_echec(nom):
    """v0.8.3 — Télécharge un fichier d'échec (.tex ou .log) du dernier run.

    Mêmes vérifications de sécurité que pour les rapports : nom uniquement,
    extension whitelistée, pas de path traversal.
    """
    from pathlib import Path
    from flask import send_file
    js, _, _ = _stores()
    # Sécurité : pas de slash, pas de '..', extension .tex ou .log
    # uniquement (pas de PDF ni d'autre fichier qui pourrait traîner).
    if '/' in nom or '\\' in nom or '..' in nom:
        return jsonify({"error": "Nom de fichier invalide."}), 400
    if not (nom.endswith('.log') or nom.endswith('.tex')):
        return jsonify({"error": "Seules les extensions .log et .tex "
                                  "sont acceptées."}), 400
    chemin = Path(js.data_dir) / "cache_rendus" / "echecs" / nom
    if not chemin.is_file():
        return jsonify({"error": "Fichier introuvable."}), 404
    # text/plain pour qu'il s'affiche dans le navigateur sans téléchargement
    # (plus pratique pour examiner rapidement un log).
    return send_file(
        chemin,
        mimetype='text/plain; charset=utf-8',
        as_attachment=False,
        download_name=nom,
    )


def _configuration_admin():
    """Accès à la configuration utilisateur (réutilisé par /run et /preview).

    On instancie à chaque appel : la classe Configuration n'a pas d'état,
    et la fonction _configuration() de routes/rendu_atome.py fait pareil.
    """
    from services.configuration import Configuration
    return Configuration(current_app.json_store.data_dir)


@bp.route("/api/admin/reset/tout", methods=["POST"])
def api_admin_reset_tout():
    js, _, _ = _stores()
    try:
        vides = js.reset_reference() + js.reset_suivi()
        return jsonify({"ok": True, "vides": vides})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Diagnostics qualité ────────────────────────────────────────────────────────

@bp.route("/api/admin/qualite/exercices-sans-corrige", methods=["GET"])
def api_qualite_exercices_sans_corrige():
    js, _, _ = _stores()
    return jsonify(svc_atomes.exercices_sans_corrige(js.lire_exercices()))


@bp.route("/api/admin/qualite/notions-sans-exemple", methods=["GET"])
def api_qualite_notions_sans_exemple():
    js, _, _ = _stores()
    return jsonify(svc_atomes.notions_sans_exemple(js.lire_notions()))


@bp.route("/api/admin/qualite/methodes-sans-exemple", methods=["GET"])
def api_qualite_methodes_sans_exemple():
    js, _, _ = _stores()
    return jsonify(svc_atomes.methodes_sans_exemple(js.lire_methodes()))


@bp.route("/api/admin/qualite/atomes-non-affectes", methods=["GET"])
def api_qualite_atomes_non_affectes():
    js, _, _ = _stores()
    return jsonify(svc_atomes.atomes_non_affectes(
        js.lire_notions(),
        js.lire_methodes(),
        js.lire_exercices(),
        js.lire_livrets_importes(),
    ))


@bp.route("/api/referentiel/niveaux", methods=["GET"])
def api_referentiel_niveaux():
    from services.niveaux import referentiel_api
    return jsonify(referentiel_api())


# ── Années et établissements disponibles ──────────────────────────────────────

@bp.route("/api/admin/annees", methods=["GET"])
def api_annees():
    """Retourne la liste des années scolaires présentes dans la base."""
    from flask import current_app
    js = current_app.json_store
    return jsonify(js.lire_annees_disponibles())


@bp.route("/api/admin/etablissements", methods=["GET"])
def api_etablissements():
    """Retourne la liste des établissements présents dans la base."""
    from flask import current_app
    js = current_app.json_store
    return jsonify(js.lire_etablissements_disponibles())


# ── Export / Import SQLite ─────────────────────────────────────────────────────

@bp.route("/api/admin/export-sqlite", methods=["GET"])
def api_export_sqlite():
    """Télécharge la base SQLite complète."""
    from flask import current_app, send_file
    from persistence.sqlite_store import SqliteStore
    import io, datetime
    js = current_app.json_store
    if not isinstance(js, SqliteStore):
        return jsonify({"error": "L'application n'utilise pas SQLite"}), 400
    db_path = js.db_path
    if not db_path.exists():
        return jsonify({"error": "Base SQLite introuvable"}), 404
    # Lire le fichier en mémoire pour éviter les verrous
    data = db_path.read_bytes()
    buf = io.BytesIO(data)
    buf.seek(0)
    date = datetime.date.today().isoformat()
    return send_file(
        buf,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=f"seqenseigne_{date}.db",
    )


@bp.route("/api/admin/import-sqlite", methods=["POST"])
def api_import_sqlite():
    """Remplace la base SQLite par un fichier uploadé."""
    from flask import current_app, request
    from persistence.sqlite_store import SqliteStore
    import shutil
    js = current_app.json_store
    if not isinstance(js, SqliteStore):
        return jsonify({"error": "L'application n'utilise pas SQLite"}), 400
    if "file" not in request.files:
        return jsonify({"error": "Fichier requis"}), 400
    f = request.files["file"]
    if not f.filename.endswith(".db"):
        return jsonify({"error": "Extension .db requise"}), 400
    # Sauvegarder l'ancienne base en backup
    db_path = js.db_path
    backup = db_path.with_suffix(".db.bak")
    if db_path.exists():
        shutil.copy2(db_path, backup)
    try:
        data = f.read()
        db_path.write_bytes(data)
        # Vérifier que la DB est valide en réinitialisant le store
        SqliteStore(js.data_dir)
        return jsonify({"ok": True})
    except Exception as e:
        # Restaurer le backup en cas d'erreur
        if backup.exists():
            shutil.copy2(backup, db_path)
        return jsonify({"error": str(e)}), 500


# ── v0.10.5.2 — Import des fiches de résumé depuis fichier .tex ─────────────


@bp.route("/api/admin/fiches/import", methods=["POST"])
def api_admin_fiches_import():
    """Importe les fiches de résumé depuis un fichier .tex au format
    « Flashcards année complète » (cf. uploads de Laurent : 5e/4e/3e).

    Modalité : multipart/form-data avec :
      - fichier (file) : le .tex à parser
      - niveau (str)  : 'N09'/'N10'/'N11'/'N12' — niveau cible

    Réponse :
      200 + {"ok": true, "rapport": {...}}  — succès, rapport détaillé
      400 + {"error": ...}                 — entrée invalide
      500 + {"error": ...}                 — exception serveur
    """
    from services.fiches_import import importer_fiches

    js, _, _ = _stores()
    if "fichier" not in request.files:
        return jsonify({
            "error": "Champ 'fichier' (multipart) requis.",
            "code":  "fichier_manquant",
        }), 400
    f = request.files["fichier"]
    if not f.filename:
        return jsonify({"error": "Fichier vide."}), 400

    niveau = (request.form.get("niveau") or "").strip()
    if niveau not in ("N09", "N10", "N11", "N12"):
        return jsonify({
            "error": f"Niveau invalide : {niveau!r}. "
                     "Attendu : N09, N10, N11 ou N12.",
            "code":  "niveau_invalide",
        }), 400

    # Lire le contenu en mémoire (les fichiers .tex font ~80-100 Ko, OK)
    try:
        contenu = f.read().decode("utf-8")
    except UnicodeDecodeError as e:
        return jsonify({
            "error": f"Le fichier doit être encodé en UTF-8 : {e}",
            "code":  "encodage_invalide",
        }), 400

    try:
        with js._conn() as conn:
            rapport = importer_fiches(
                conn, contenu_tex=contenu, niveau=niveau,
            )
        return jsonify({
            "ok":      True,
            "fichier": f.filename,
            "niveau":  niveau,
            "rapport": rapport.to_dict(),
        })
    except Exception as e:
        return jsonify({
            "error": f"{type(e).__name__}: {e}",
            "code":  "exception_serveur",
        }), 500
