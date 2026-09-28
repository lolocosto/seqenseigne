"""
services/admin.py — Logique métier des fonctions d'administration.

Nettoyage post-R4e4b :
  - Suppression de generer_yaml_niveaux() et niveaux_yaml_vides() :
    la génération YAML depuis les livrets importés n'est plus exposée
    dans l'UI Admin (elle était un palliatif hérité du temps où les
    YAML étaient la source de vérité des séquences). La génération
    automatique reste en place comme fallback interne dans
    services.sequences.build_sequences() jusqu'à l'Option C.
  - Suppression du champ "yaml" dans statut_bdd() : l'écran Admin ne
    montre plus l'état des fichiers YAML, qui ne sont plus qu'un
    cache dérivé.
  - Le paramètre yaml_store est conservé dans la signature pour
    compatibilité avec l'appelant routes/admin.py::api_admin_statut,
    mais il n'est plus utilisé dans le corps de la fonction.
"""

from __future__ import annotations


def statut_bdd(json_store, yaml_store, csv_store) -> dict:
    """Retourne un état synthétique de la base (compteurs SQLite + C04)."""
    # Référentiels versionnés (SqliteStore uniquement)
    referentiels = []
    if hasattr(json_store, "lister_referentiels"):
        try:
            referentiels = json_store.lister_referentiels()
        except Exception:
            pass

    # Progressions et créneaux (via lister_progressions → on itère tous niveaux)
    progressions = []
    creneaux_total = 0
    try:
        for niveau in ("N09", "N10", "N11", "N12"):
            if hasattr(json_store, "lister_progressions"):
                for p_entete in json_store.lister_progressions(niveau):
                    prog_complete = json_store.lire_progression_par_id(p_entete["id"])
                    if prog_complete:
                        progressions.append(p_entete)
                        creneaux_total += len(prog_complete.get("creneaux", []))
    except Exception:
        pass

    # Classes + élèves
    classes = json_store.lire_classes().get("classes", [])
    nb_classes = len(classes)
    nb_eleves_total = sum(len(c.get("eleves", [])) for c in classes)

    # Suivi : compter les niveaux saisis et les exercices cochés
    nb_niveaux_saisis = 0
    nb_exos_coches    = 0
    try:
        niveaux_data = json_store.lire_niveaux()
        for _cid, seqs in niveaux_data.items():
            for _seq, eleves_niv in seqs.items():
                for _eid, objs in eleves_niv.items():
                    nb_niveaux_saisis += len(objs)
        suivi_data = json_store.lire_suivi()
        for _cid, seqs in suivi_data.items():
            for _seq, eleves_s in seqs.items():
                for _eid, series in eleves_s.items():
                    for _serie, liste in series.items():
                        if isinstance(liste, list):
                            nb_exos_coches += len(liste)
    except Exception:
        pass

    # v0.6.4 — Statistiques de la mise en forme LaTeX (paquet seqenseigne
    # importé en BDD via scripts/peuplement_14_paquet_vers_base.py).
    # Les tables paquet_definitions et paquet_requirepackage peuvent ne
    # pas exister si le peuplement n'a jamais été lancé — c'est OK,
    # on retourne un dict vide qui le frontend interprète comme « non
    # affiché ».
    paquet = {}
    try:
        with json_store._conn() as conn:
            # Totaux
            macros = conn.execute(
                "SELECT COUNT(*) FROM paquet_definitions WHERE type_latex='command'"
            ).fetchone()[0]
            envs = conn.execute(
                "SELECT COUNT(*) FROM paquet_definitions WHERE type_latex='environment'"
            ).fetchone()[0]
            req  = conn.execute(
                "SELECT COUNT(*) FROM paquet_requirepackage"
            ).fetchone()[0]
            fichiers = conn.execute(
                "SELECT COUNT(DISTINCT fichier_source) FROM paquet_definitions"
            ).fetchone()[0]
            # Détail par type LaTeX (command, environment, tcolorbox, counter, ...)
            detail_rows = conn.execute(
                "SELECT type_latex, COUNT(*) FROM paquet_definitions "
                "GROUP BY type_latex ORDER BY COUNT(*) DESC"
            ).fetchall()
            detail = {row[0]: row[1] for row in detail_rows}
            # Détail par fichier (pour visualiser les .sty)
            par_fichier_rows = conn.execute(
                "SELECT fichier_source, COUNT(*) FROM paquet_definitions "
                "GROUP BY fichier_source ORDER BY COUNT(*) DESC"
            ).fetchall()
            for fn, n in par_fichier_rows:
                detail[fn] = n
            paquet = {
                "macros": macros,
                "environnements": envs,
                "requirepackage": req,
                "fichiers_sty": fichiers,
                "detail": detail,
            }
    except Exception:
        paquet = {}

    return {
        "reference": {
            "notions":      len(json_store.lire_notions()),
            "methodes":     len(json_store.lire_methodes()),
            "exercices":    len(json_store.lire_exercices()),
            "livrets":      len(json_store.lire_livrets_importes()),
            "referentiels": len(referentiels),
        },
        "paquet": paquet,
        "suivi": {
            "classes":          nb_classes,
            "eleves":           nb_eleves_total,
            "progressions":     len(progressions),
            "creneaux":         creneaux_total,
            "niveaux_saisis":   nb_niveaux_saisis,
            "exercices_coches": nb_exos_coches,
        },
        "referentiels": [
            {
                "id":         r.get("id"),
                "niveau":     r.get("niveau"),
                "version":    r.get("version"),
                "verrouille": r.get("verrouille", False),
            }
            for r in referentiels
        ],
        "c04": {
            "sequences": len(csv_store.lire_c04_sequences()),
            "themes":    len(csv_store.lire_c04_themes()),
        },
    }
