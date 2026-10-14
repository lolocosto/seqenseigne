"""services/repartition.py — v0.51.12

Répartition des tables entre l'appli locale (atelier) et l'appli en ligne
(classe), validée table par table (document « Répartition des tables entre
atelier et classe », v0.51.11) :

  - TABLES_CLASSE  : planification et suivi — structure dans la base classe
    seulement ;
  - TABLES_ATELIER : conception — structure dans la base atelier seulement ;
  - TABLES_DEUX    : référentiels, nomenclatures, échanges — structure des
    deux côtés, données qui peuvent différer.

**Rôle d'une base** (`instance_locale.role`) : '' (base partagée d'avant la
bascule, profil complet), 'atelier' ou 'classe' (posé par la bascule). Dans
une base qui a un rôle, les tables de l'autre côté sont **retirées** au
démarrage (`elaguer`) — seulement si elles sont vides : une table de l'autre
côté qui contient des données est gardée et signalée (jamais de perte).

Le code d'un côté qui lit une table de l'autre côté doit le faire sous garde
(`table_existe`) : voir les lectures croisées du document de répartition.
"""

from __future__ import annotations

ROLES = ("atelier", "classe")

TABLES_CLASSE = (
    # Établissements et organisation
    "etablissements", "grille_horaire_creneaux", "salles", "salle_versions", "salle_places",
    "indisponibilites", "cache_api",
    # Classes, élèves, plans
    "classes", "eleves", "eleves_classes", "plans_classe", "plan_placements",
    "plan_reservations",
    # Emplois du temps, répartition des séances
    "edt_creneaux", "edt_etats", "affectation_config", "affectation_seance",
    "affectation_exception", "regle_repartition", "decalage_progression",
    # Progressions
    "progressions", "creneaux", "creneau_objectifs_exos", "creneau_objectifs_seances",
    "progression_doc", "progression_mer", "progression_mer_partie",
    # Suivi et séances
    "suivi", "niveaux", "absences", "observables", "observable_exceptions", "observations",
    "seance_contenu", "activites_seance", "seance_documents", "seance_remises", "docs_suivi",
    "retours", "echeances_individuelles",
    # Référentiels reçus, journal des imports
    "referentiel_docs_publies", "referentiel_titres_publies", "imports_publication",
)

TABLES_ATELIER = (
    "referentiel_documents",
    # Conception (ateliers atomiques et d'assemblage)
    "themes", "sequences_du_cycle", "sequences_par_niveau", "sequence_parties",
    "sequence_par_niveau_precedences", "partie_precedences", "objectifs", "objectif_notions",
    "objectif_exos", "objectif_fiches", "objectif_cartes", "partie_exos_revision_approche",
    "notions", "methodes", "methode_notions", "exercices", "annexes", "fiches_resume",
    "atome_sections", "atome_section_items", "cartes_automatisme", "cartes_atelier_config",
    "evaluations", "evaluation_exercices", "evaluation_objectifs", "etats_edition", "images",
    "ui_etat_atelier_sequence",
    # Mise en forme LaTeX (tables créées par l'import du paquet)
    "paquet_definitions", "paquet_requirepackage",
    # Échanges propres à l'atelier
    "publications", "usage_recu",
)

TABLES_DEUX = (
    "referentiel_niveaux", "referentiel_themes", "referentiel_sequences", "referentiel_parties",
    "referentiel_objectifs", "referentiel_obj_exos", "referentiel_parties_seances",
    "referentiel_fichiers", "types_documents", "cycles", "param_niveaux", "preferences_items",
    "instance_locale", "correspondants", "echanges_envoyes", "echanges_recus",
    "depot_reglages", "depot_journal",
)

# Tables remplies de valeurs par défaut à leur création (amorce) : retirées
# de l'autre côté même non vides (elles ne portent aucune donnée saisie).
AMORCEES = {"activites_seance", "etats_edition"}

# Préférences (preferences_items) : par type.
PREFERENCES = {"titre_zone_fiche": "atelier", "type_mise_en_route": "classe"}


def autre(role: str) -> str:
    return "classe" if role == "atelier" else "atelier"


def tables_de(role: str) -> tuple:
    return TABLES_ATELIER if role == "atelier" else TABLES_CLASSE


def tables(conn) -> set:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def table_existe(conn, nom: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (nom,)).fetchone() is not None


def role(conn) -> str:
    """Rôle de la base ('' tant qu'elle n'a pas été basculée)."""
    if not table_existe(conn, "instance_locale"):
        return ""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(instance_locale)")}
    if "role" not in cols:
        return ""
    r = conn.execute("SELECT role FROM instance_locale LIMIT 1").fetchone()
    return (r[0] or "") if r else ""


def definir_role(conn, valeur: str) -> None:
    from services import echanges as ech
    if valeur not in ROLES:
        raise ValueError(f"Rôle inconnu : {valeur!r}")
    ech.instance(conn)                         # crée l'identité au besoin
    conn.execute("UPDATE instance_locale SET role=?", (valeur,))


def vider(conn, noms) -> dict:
    """Vide les tables (bascule) ; clés étrangères suspendues."""
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        faits = {}
        existantes = tables(conn)
        for t in noms:
            if t in existantes:
                faits[t] = conn.execute(f"DELETE FROM {t}").rowcount
        conn.commit()
        return faits
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def elaguer(conn, valeur: str | None = None) -> dict:
    """Retire les tables de l'autre côté (vides seulement). Renvoie
    {retirees: [...], gardees: {table: lignes}} ; rien si la base n'a pas de
    rôle."""
    valeur = role(conn) if valeur is None else valeur
    if valeur not in ROLES:
        return {"retirees": [], "gardees": {}}
    existantes = tables(conn)
    retirees, gardees = [], {}
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        for t in tables_de(autre(valeur)):
            if t not in existantes:
                continue
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            if n and t not in AMORCEES:
                gardees[t] = n
                continue
            conn.execute(f"DROP TABLE {t}")
            retirees.append(t)
        # Préférences de l'autre côté (dont les valeurs amorcées par le schéma,
        # réinsérées à chaque démarrage).
        if "preferences_items" in existantes:
            for type_, cote in PREFERENCES.items():
                if cote != valeur:
                    conn.execute("DELETE FROM preferences_items WHERE type=?", (type_,))
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    if gardees:
        print(f"  [répartition] base « {valeur} » : tables de l'autre côté non vides, "
              f"gardées : {', '.join(f'{t} ({n})' for t, n in gardees.items())}")
    return {"retirees": retirees, "gardees": gardees}
