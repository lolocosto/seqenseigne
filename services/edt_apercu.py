"""services/edt_apercu.py — v0.38.0

Aperçu, avant enregistrement, de l'effet d'un changement d'emploi du temps sur
le nombre de séances restantes de chaque classe (de la date d'effet à la fin
de l'année scolaire).

Principe : on calcule la projection de chaque classe de l'établissement, on
joue l'opération dans un SAVEPOINT, on recalcule, puis on annule. Les
vacances et fériés sont récupérés AVANT d'ouvrir la transaction : leur
récupération peut écrire dans le cache de la base (sinon verrou SQLite).

Préparation de la projection : services/contexte_projection.py (v0.41.1).
"""

from __future__ import annotations
from datetime import date

from services import edt as edt_svc
from services import contexte_projection as ctx

OPERATIONS = ("ajouter", "modifier", "supprimer", "appliquer_salle")


def _calendrier(store, annee: str, academie: str) -> tuple[list, dict]:
    cal = ctx.calendrier(store, annee, academie)
    return cal["vacances"], cal["feries"]


def _compter(conn, annee, classe_id, etab_id, vacances, feries,
             depuis: str) -> int:
    seances = ctx.projeter_classe(conn, annee, classe_id, etab_id,
                                  {"vacances": vacances, "feries": feries})
    return sum(1 for s in seances if s["date"] >= depuis)


def _jouer(conn, annee, etab_id, body, aujourd_hui):
    op = body.get("operation")
    a_partir_du = body.get("a_partir_du") or None
    if op == "ajouter":
        c = body.get("champs") or {}
        edt_svc.ajouter(conn, annee, c.get("jour", ""), c.get("creneau_code", ""),
                        etab_id, semaine=c.get("semaine", "AB"),
                        classe_id=c.get("classe_id"), libelle=c.get("libelle", ""),
                        groupe=c.get("groupe", "classe_entiere"),
                        usage=c.get("usage", "cours"),
                        salle_id=c.get("salle_id") or None,
                        nb_aesh=c.get("nb_aesh", 0),
                        a_partir_du=a_partir_du, aujourd_hui=aujourd_hui)
    elif op == "modifier":
        edt_svc.modifier(conn, body.get("edt_id", ""), body.get("champs") or {},
                         a_partir_du=a_partir_du, aujourd_hui=aujourd_hui)
    elif op == "supprimer":
        edt_svc.supprimer(conn, body.get("edt_id", ""), a_partir_du=a_partir_du,
                          aujourd_hui=aujourd_hui)
    elif op == "appliquer_salle":
        edt_svc.appliquer_salle(conn, annee, etab_id, body.get("salle_id", ""),
                                a_partir_du=a_partir_du, aujourd_hui=aujourd_hui)
    else:
        raise edt_svc.DonneesInvalides(f"Opération inconnue : {op!r}.")


def apercu(store, annee: str, body: dict, aujourd_hui: date) -> list[dict]:
    """[{classe_id, nom, avant, apres}] pour chaque classe de l'établissement,
    séances comptées à partir de la date d'effet (ou d'aujourd'hui si l'EdT
    est en saisie)."""
    etab_id = body.get("etablissement_id", "")
    with store._conn() as conn:
        r = conn.execute("SELECT academie FROM etablissements WHERE id=?",
                         (etab_id,)).fetchone()
        if r is None:
            raise edt_svc.DonneesInvalides("Établissement inconnu.")
        academie = r["academie"] or ""
        classes = [dict(x) for x in conn.execute(
            "SELECT id, nom FROM classes WHERE annee=? AND etablissement_id=? "
            "ORDER BY nom", (annee, etab_id)).fetchall()]
    vacances, feries = _calendrier(store, annee, academie)
    depuis = body.get("a_partir_du") or aujourd_hui.isoformat()
    with store._conn() as conn:
        avant = {c["id"]: _compter(conn, annee, c["id"], etab_id, vacances,
                                   feries, depuis) for c in classes}
        conn.execute("SAVEPOINT edt_apercu")
        try:
            _jouer(conn, annee, etab_id, body, aujourd_hui)
            apres = {c["id"]: _compter(conn, annee, c["id"], etab_id, vacances,
                                       feries, depuis) for c in classes}
        finally:
            conn.execute("ROLLBACK TO edt_apercu")
            conn.execute("RELEASE edt_apercu")
    return [{"classe_id": c["id"], "nom": c["nom"],
             "avant": avant[c["id"]], "apres": apres[c["id"]]} for c in classes]
