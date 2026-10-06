#!/usr/bin/env python3
"""
seqenseigne — point d'entrée Flask v0.5
Lancer : python app.py  puis ouvrir http://localhost:5000
"""

import sys
import mimetypes
from pathlib import Path

# S'assurer que le dossier de app.py est dans le path Python
sys.path.insert(0, str(Path(__file__).parent))

# v0.16 — Le viewer pdf.js embarqué (static/vendor/pdfjs) est servi en
# modules ES (.mjs). Les navigateurs n'exécutent un module que si le
# serveur le renvoie avec un MIME type JavaScript. Or sur Windows (runtime
# de production sur clé USB), la base de registre peut associer .mjs à un
# type incorrect ou absent, ce qui casserait le chargement du viewer.
# On force donc le mapping ici, avant toute création d'app, pour un
# comportement identique sur Linux/Windows.
mimetypes.add_type("text/javascript", ".mjs")

from flask import Flask, render_template

from persistence.sqlite_store import SqliteStore
from persistence.yaml_store import YamlStore
from persistence.csv_store  import CsvStore

from routes.sequences      import bp as bp_sequences
from routes.classes        import bp as bp_classes
from routes.suivi          import bp as bp_suivi
from routes.versions       import bp as bp_versions
from routes.atomes         import bp as bp_atomes
from routes.admin          import bp as bp_admin
from routes.progression    import bp as bp_progression
from routes.etablissements import bp as bp_etablissements
from routes.grille_horaire  import bp as bp_grille_horaire
from routes.salles          import bp as bp_salles
from routes.plans_classe    import bp as bp_plans_classe
from routes.seance          import bp as bp_seance
from routes.observables     import bp as bp_observables
from routes.observation     import bp as bp_observation
from routes.referentiel_principal_externe import bp as bp_rpe
from routes.edt             import bp as bp_edt
from routes.projection      import bp as bp_projection
from routes.affectation     import bp as bp_affectation
from routes.indisponibilites import bp as bp_indisponibilites
from routes.decalage_progression import bp as bp_decalage_progression
from routes.leitner import bp as bp_leitner
from routes.referentiel_externe import bp as bp_referentiel_externe
from routes.progression_mer import bp as bp_progression_mer
from routes.progression_doc import bp as bp_progression_doc
from routes.tableau_bord import bp as bp_tableau_bord
from routes.planification_hebdo import bp as bp_planification_hebdo
from routes.calendrier     import bp as bp_calendrier
from routes.annees_scolaires import bp as bp_annees_scolaires
from routes.referentiels   import bp as bp_referentiels
from importers.scanner     import bp as bp_scanner
from routes.cycle             import bp_cycle
from routes.themes           import bp_themes
from routes.sequences_du_cycle import bp_sequences_du_cycle
# v0.14.6.b.2 — routes/peuplement_v2.py supprimée : ses 2 endpoints
# (POST /api/admin/v2/peupler, GET /api/admin/v2/statistiques)
# dépendaient de services/scanner_vers_v2.py (lui-même supprimé car
# il lisait v1). Plus aucun frontend ne les appelait.
from routes.v2_lecture        import bp_v2_lecture
from routes.v2_edition        import bp_v2_edition
from routes.rendu_atome       import bp as bp_rendu_atome
# v0.15.1 — Suppression des routes /api/recap-cours/*, /api/recap-exos/*
# et /api/plans-de-travail/*. Les services Python correspondants
# (services/livret_recap_cours.py, livret_recap_exos.py,
# livret_plans_de_travail.py) restent en place car utilisés par
# referentiels.py, orchestrateur_compilation.py, livret_fiches.py et
# latex_rendu_atome.py. Seules les routes HTTP côté frontend ont
# disparu, l'atelier Référentiel > Documents à publier remplaçant
# ces 3 ateliers côté UI.
# v0.16.10 — Réintroduction de /api/plans-de-travail/<niveau>/<seq>/* en
# portée SÉQUENCE uniquement : le bouton « Compiler le plan de travail » de
# l'onglet Rendu PDF de l'atelier d'assemblage en a besoin (le livret annuel
# reste géré par l'atelier Référentiel).
from routes.plans_de_travail   import bp as bp_plans_de_travail
from routes.livret_sequence    import bp as bp_livret_sequence
from routes.etats_edition      import bp_etats_edition
from routes.fiches_resume      import bp_fiches_resume
from routes.preferences        import bp_preferences
from routes.evaluations        import bp as bp_evaluations
from routes.cartes_automatisme import bp as bp_cartes_automatisme
from routes.referentiel_documents import bp as bp_referentiel_documents  # v0.13.6.4
from routes.referentiel_documents_compilation import bp as bp_referentiel_documents_compilation  # v0.13.6.5.1
from routes.paquet import bp as bp_paquet  # v0.13.7.1
from routes.images import bp as bp_images  # v0.13.7.4
from routes.recherche import bp as bp_recherche  # v0.18.1

def create_app(data_dir: Path | None = None) -> Flask:
    """
    Fabrique de l'application Flask.
    data_dir : chemin du dossier data/ (défaut : <dossier de app.py>/data)
    Utilisé tel quel en production et injecté avec un dossier temporaire dans les tests.
    """
    root = Path(__file__).parent
    data_dir = data_dir or (root / "data")

    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )

    # ── Stores injectés comme attributs de l'app ──────────────────────────────
    # Les routes y accèdent via current_app.json_store (nom historique,
    # c'est en fait une instance de SqliteStore) et current_app.yaml_store,
    # current_app.csv_store.
    app.json_store = SqliteStore(data_dir)
    app.yaml_store = YamlStore(data_dir)
    app.csv_store  = CsvStore(data_dir)

    # ── v0.10.2 — Auto-import des cycles depuis CSV ──────────────────────────
    # Si data/<code>_themes.csv et data/<code>_sequences.csv sont présents
    # et que le cycle n'est pas encore en BDD, l'importer automatiquement.
    # Idempotent : ne refait rien si déjà fait. Pour C03 et C04.
    from services.cycle_auto_import import auto_importer_cycles
    auto_importer_cycles(data_dir, app.json_store.db_path)

    # ── Blueprints ────────────────────────────────────────────────────────────
    for bp in (bp_sequences, bp_classes, bp_suivi, bp_versions,
               bp_atomes, bp_scanner, bp_admin, bp_progression,
               bp_etablissements, bp_calendrier,
               bp_grille_horaire, bp_salles, bp_plans_classe, bp_seance, bp_observables, bp_observation, bp_rpe, bp_edt, bp_projection, bp_affectation,
               bp_indisponibilites, bp_decalage_progression, bp_leitner,
               bp_referentiel_externe, bp_progression_mer, bp_tableau_bord,
               bp_progression_doc,
               bp_planification_hebdo,
               bp_annees_scolaires, bp_referentiels, bp_cycle, bp_themes,
               bp_sequences_du_cycle, bp_v2_lecture,
               bp_v2_edition, bp_rendu_atome,
               bp_livret_sequence, bp_plans_de_travail,
               bp_etats_edition, bp_fiches_resume, bp_preferences,
               bp_evaluations, bp_cartes_automatisme,
               bp_referentiel_documents,  # v0.13.6.4
               bp_referentiel_documents_compilation,  # v0.13.6.5.1
               bp_paquet,  # v0.13.7.1
               bp_images,  # v0.13.7.4
               bp_recherche):  # v0.18.1
        app.register_blueprint(bp)

    # ── Page principale ───────────────────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template("index.html")

    # ── v0.23.0 — Authentification OPTIONNELLE (désactivée par défaut) ─────────
    # Protège l'accès si la variable d'environnement SEQ_MDP est définie.
    # Sans elle, aucun changement (usage local mono-poste).
    from services.auth import init_auth
    init_auth(app)

    # ── v0.23.0 — Gestion des exceptions non capturées ────────────────────────
    # Hors mode debug, une exception non gérée ne doit pas exposer de trace ni
    # de détail interne au client. On renvoie un message générique (JSON pour
    # les appels API, court sinon) et on logge le détail côté serveur.
    # Les erreurs métier volontaires (abort/jsonify 4xx explicites dans les
    # routes) ne passent pas par ici : elles gardent leurs messages utiles.
    import logging as _logging
    from werkzeug.exceptions import HTTPException as _HTTPException

    @app.errorhandler(Exception)
    def _erreur_non_geree(e):
        # Laisser les erreurs HTTP explicites (404, 400, 405…) suivre leur cours.
        if isinstance(e, _HTTPException):
            return e
        # En debug, relancer pour bénéficier du traceback Werkzeug local.
        if app.debug:
            raise e
        _logging.getLogger("seqenseigne").exception("Exception non gérée")
        from flask import request as _rq, jsonify as _js
        if _rq.path.startswith("/api/"):
            return _js({"error": "Erreur interne du serveur."}), 500
        return "Erreur interne du serveur.", 500

    return app


if __name__ == "__main__":
    import os
    # v0.23.0 — Le mode debug n'est plus activé en dur : il expose le débogueur
    # interactif Werkzeug (exécution de code arbitraire depuis le navigateur en
    # cas d'erreur), inacceptable hors poste local isolé. Il est désormais piloté
    # par la variable d'environnement SEQ_DEBUG (défaut : OFF).
    #   - usage local classique : rien à faire (debug désactivé, plus sûr) ;
    #   - pour déboguer ponctuellement : SEQ_DEBUG=1 python app.py
    debug = os.environ.get("SEQ_DEBUG", "") == "1"
    print("\n  seqenseigne — suivi de progression")
    print("  Ouvrir : http://localhost:5000")
    if debug:
        print("  (mode debug ACTIVÉ via SEQ_DEBUG=1 — ne pas exposer)")
    print()
    create_app().run(debug=debug, port=5000)
