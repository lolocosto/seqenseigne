"""services/profils.py — v0.51.0

Profils de lancement de l'application (séparation en deux outils) :

  - « complet » (défaut) : tout, comme avant la v0.51 ;
  - « atelier » : conception des référentiels (local, avec LaTeX) ;
  - « classe »  : suivi des classes (destiné à la mise en ligne, sans LaTeX).

Le profil est lu dans la variable d'environnement SEQ_PROFIL (posée par
`lancer.bat atelier|classe`), ou passé à create_app(profil=...).

Chaque route du serveur appartient à une catégorie :
  - « atelier »   : conception (atomes, compilation, livrets…) ;
  - « classe »    : élèves, EdT, planification, séances, suivi ;
  - « structure » : référentiels (internes et externes) — lecture partout,
                    écriture dans l'atelier seulement ;
  - « commun »    : années, niveaux, préférences, base de données… ;
  - « complet »   : outils de transition (import de classes historiques),
                    visibles uniquement en profil complet.

Deux mécanismes complémentaires :
  1. les blueprints entièrement étrangers à un profil ne sont pas enregistrés
     (aucune route de compilation dans le profil classe) ;
  2. un garde (before_request) refuse les routes restantes hors profil :
     404 si la fonction n'existe pas dans ce profil, 403 pour une écriture sur
     la structure depuis le profil classe.
"""

from __future__ import annotations

import os

from flask import jsonify, request

PROFILS = ("complet", "atelier", "classe")
PROFIL_DEFAUT = "complet"

# ── Catégorie de chaque blueprint ────────────────────────────────────────────

BP_ATELIER = frozenset({
    "sequences", "versions", "atomes", "scanner", "admin", "cycle", "themes",
    "sequences_du_cycle", "v2_lecture", "v2_edition", "rendu_atome",
    "livret_sequence", "plans_de_travail", "etats_edition", "fiches_resume",
    "evaluations", "cartes_automatisme", "referentiel_documents_compilation",
    "paquet", "images", "recherche",
    "publication",          # v0.51.1 — format d'échange des référentiels
})
BP_STRUCTURE = frozenset({
    "referentiels", "referentiel_principal_externe", "referentiel_externe",
    "referentiel_documents",
})
BP_CLASSE = frozenset({
    "classes", "suivi", "progression", "etablissements", "grille_horaire",
    "salles", "plans_classe", "seance", "observables", "observation", "edt",
    "projection", "affectation", "indisponibilites", "decalage_progression",
    "leitner", "progression_mer", "progression_doc", "planification_hebdo",
    "calendrier",
})
BP_COMMUN = frozenset({"annees_scolaires", "preferences", "tableau_bord"})

# Exceptions, route par route (prioritaires sur la catégorie du blueprint).
ENDPOINTS = {
    # Administration : base de données, années, niveaux → communs.
    "admin.api_annees": "commun",
    "admin.api_referentiel_niveaux": "commun",
    "admin.api_admin_statut": "commun",
    "admin.api_export_sqlite": "commun",
    "admin.api_import_sqlite": "commun",
    "admin.api_etablissements": "classe",
    "admin.api_admin_reset_suivi": "classe",
    "admin.api_admin_reset_tout": "complet",
    # Import de classes historiques (SequencesDB) : profil complet seulement
    # (il crée à la fois un référentiel et une classe).
    "progression.api_import_historique": "complet",
    "progression.api_progression_importer_sequencesdb": "complet",
    # Tableau de bord : une tuile par côté.
    "tableau_bord.api_atomes_en_cours": "atelier",
    "tableau_bord.api_atomes_non_rattaches": "atelier",
    "tableau_bord.api_seances_semaine": "classe",
}

_LECTURE = frozenset({"GET", "HEAD", "OPTIONS"})


def profil_courant(valeur: str | None = None) -> str:
    """Profil demandé (argument, sinon SEQ_PROFIL), validé."""
    p = (valeur if valeur is not None else os.environ.get("SEQ_PROFIL", "")) or ""
    p = p.strip().lower() or PROFIL_DEFAUT
    if p not in PROFILS:
        raise ValueError(f"Profil inconnu : {p!r} (attendu : {', '.join(PROFILS)})")
    return p


def categorie_blueprint(nom: str) -> str:
    if nom in BP_ATELIER:
        return "atelier"
    if nom in BP_STRUCTURE:
        return "structure"
    if nom in BP_CLASSE:
        return "classe"
    return "commun"            # BP_COMMUN et routes de l'app (index, static, login)


def categorie(endpoint: str | None) -> str:
    if not endpoint:
        return "commun"
    if endpoint in ENDPOINTS:
        return ENDPOINTS[endpoint]
    return categorie_blueprint(endpoint.split(".", 1)[0]) if "." in endpoint else "commun"


def blueprint_enregistre(nom: str, profil: str) -> bool:
    """Un blueprint dont aucune route ne sert au profil n'est pas enregistré."""
    if profil == "complet":
        return True
    cat = categorie_blueprint(nom)
    if profil == "classe" and cat == "atelier":
        # admin garde des routes communes (base de données, années, niveaux).
        return any(e.startswith(nom + ".") and c in ("commun", "classe")
                   for e, c in ENDPOINTS.items())
    if profil == "atelier" and cat == "classe":
        return any(e.startswith(nom + ".") and c in ("commun", "atelier")
                   for e, c in ENDPOINTS.items())
    return True


def autorise(profil: str, endpoint: str | None, methode: str) -> tuple[bool, int]:
    """(autorisé ?, code d'erreur sinon : 404 absent / 403 structure)."""
    if profil == "complet":
        return True, 0
    cat = categorie(endpoint)
    if cat == "commun" or cat == profil:
        return True, 0
    if cat == "structure":
        if profil == "atelier" or methode.upper() in _LECTURE:
            return True, 0
        return False, 403
    return False, 404


def installer_garde(app, profil: str) -> None:
    """Enregistre le garde de profil (no-op en profil complet)."""
    app.config["SEQ_PROFIL"] = profil

    @app.context_processor
    def _profil_dans_les_gabarits():
        return {"profil": profil}

    if profil == "complet":
        return

    @app.before_request
    def _garde_profil():
        ok, code = autorise(profil, request.endpoint, request.method)
        if ok:
            return None
        if code == 403:
            msg = ("La structure des référentiels se modifie dans l'appli "
                   "locale (profil atelier).")
        else:
            msg = f"Fonction indisponible dans le profil « {profil} »."
        return jsonify({"error": msg, "code": "profil"}), code
