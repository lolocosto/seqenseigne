"""services/contexte_projection.py — v0.41.1

Préparation commune de la projection des séances d'une classe. Avant v0.41.1,
cette séquence était recopiée dans 9 routes/services (projection, Leitner,
affectation, MER ×2, décalage de progression, aperçu d'EdT, planification
hebdo ×2) — toutes identiques à l'audit, figées par
tests/test_v0_41_1_projection_figee.py.

Deux temps, à respecter :

1. `calendrier(store, annee, academie)` — vacances (zone de l'académie) et
   jours fériés. Récupération réseau + cache en base : à appeler HORS d'une
   transaction d'écriture ouverte (sinon verrou SQLite, cf. v0.38).
   Une erreur réseau donne une liste de vacances vide (`vacances_absentes`).

2. `projeter_classe(conn, annee, classe_id, etablissement_id, cal)` — EdT
   compté (cours en classe entière), grille horaire et indisponibilités de
   l'établissement, borne basse au 1er septembre, puis
   `projection_seances.projeter`.

`infos_classe(conn, classe_id)` lit l'établissement et l'académie d'une
classe (None si la classe n'existe pas).
"""

from __future__ import annotations

from services import edt as edt_svc
from services import grille_horaire as gh_svc
from services import indisponibilites as ind_svc
from services import projection_seances as proj
from services import calendrier_scolaire as cal_svc


def infos_classe(conn, classe_id: str) -> dict | None:
    """{etablissement_id, academie} de la classe, ou None si introuvable."""
    r = conn.execute(
        "SELECT c.etablissement_id AS eid, e.academie AS academie "
        "FROM classes c LEFT JOIN etablissements e ON e.id = c.etablissement_id "
        "WHERE c.id=?", (classe_id,)).fetchone()
    if r is None:
        return None
    return {"etablissement_id": r["eid"], "academie": r["academie"] or ""}


def calendrier(store, annee: str, academie: str, *, feries: bool = True) -> dict:
    """{zone, vacances, feries, vacances_absentes}. `feries=False` évite la
    récupération des fériés pour les appelants qui n'en ont pas besoin."""
    zone = cal_svc.zone_academie(academie) if academie else None
    vacances = []
    if zone:
        try:
            vacances = cal_svc.vacances(annee, zone, store, academie=academie)
        except Exception:
            vacances = []
    jours_feries = {}
    if feries:
        try:
            jours_feries = cal_svc.jours_feries_annee_scolaire(annee, store)
        except Exception:
            jours_feries = {}
    return {"zone": zone, "vacances": vacances, "feries": jours_feries,
            "vacances_absentes": not vacances}


def date_min(annee: str) -> str:
    """Borne basse SYSTÉMATIQUE au 1er septembre : les données officielles ne
    contiennent jamais les vacances d'été de DÉBUT d'année scolaire (elles
    relèvent de l'année précédente) ; la rentrée étant toujours en septembre,
    borner au 1er septembre évite des séances fantômes en août."""
    return f"{int(annee.split('-')[0])}-09-01"


def donnees_classe(conn, annee: str, classe_id: str,
                   etablissement_id: str | None) -> dict:
    """{edt_comptees, grille, indispos} : entrées de la projection."""
    toutes = edt_svc.lister(conn, annee, classe_id=classe_id)
    return {
        "edt_comptees": [c for c in toutes if edt_svc.est_compte(c)],
        "grille": gh_svc.lister(conn, etablissement_id) if etablissement_id else [],
        "indispos": ind_svc.lister(conn, annee, etablissement_id=etablissement_id)
        if etablissement_id else [],
    }


def projeter_donnees(annee: str, classe_id: str, donnees: dict, cal: dict) -> list:
    """Projection à partir de données déjà lues (utile quand l'appelant a dû
    fermer sa connexion avant de récupérer le calendrier)."""
    return proj.projeter(annee, donnees["edt_comptees"], donnees["grille"],
                         cal["vacances"], cal["feries"], date_min=date_min(annee),
                         indisponibilites=donnees["indispos"], classe_id=classe_id)


def projeter_classe(conn, annee: str, classe_id: str,
                    etablissement_id: str | None, cal: dict) -> list:
    """Séances projetées de la classe pour l'année (numérotées)."""
    return projeter_donnees(annee, classe_id,
                            donnees_classe(conn, annee, classe_id, etablissement_id),
                            cal)


# ── v0.41.2 — Séances d'une semaine (vues hebdomadaires) ─────────────────────

def seances_de_la_semaine(conn, store, annee: str, lundi_iso: str,
                          classes: list[dict] | None = None) -> list[dict]:
    """Séances comptées de la semaine du `lundi_iso`, pour toutes les classes
    de l'année (ou celles de `classes` : lignes {id, nom, niveau, mer_active,
    mer_mode}), telles que la projection les voit : alternance A/B, versions
    d'EdT, vacances, fériés, semaine de rentrée ignorée.

    Différence voulue avec la projection : les séances touchées par une
    indisponibilité sont GARDÉES, marquées `indispo` (les vues hebdomadaires
    les affichent barrées). Type MER selon `affectation.repartir_mer`
    (exceptions comprises).

    Retour : [{classe_id, classe, niveau, etablissement_id, date, jour,
               creneau, edt_creneau_id, libelle, type_mer, indispo}].
    """
    from datetime import date, timedelta
    from services import affectation as aff_svc

    lundi = date.fromisoformat(lundi_iso)
    dimanche = (lundi + timedelta(days=6)).isoformat()
    if classes is None:
        classes = [dict(r) for r in conn.execute(
            "SELECT id, nom, niveau, mer_active, mer_mode FROM classes "
            "WHERE annee=?", (annee,)).fetchall()]
    calendriers: dict[str, dict] = {}
    sortie = []
    for cl in classes:
        cid = cl["id"]
        infos = infos_classe(conn, cid)
        if infos is None:
            continue
        aca = infos["academie"]
        if aca not in calendriers:
            calendriers[aca] = calendrier(store, annee, aca)
        cal = calendriers[aca]
        donnees = donnees_classe(conn, annee, cid, infos["etablissement_id"])
        libelles = {c["id"]: c.get("libelle") or "" for c in donnees["edt_comptees"]}
        ordre = {g["code"]: g.get("ordre", 0) for g in donnees["grille"]}
        toutes = proj.projeter(annee, donnees["edt_comptees"], donnees["grille"],
                               cal["vacances"], cal["feries"],
                               date_min=date_min(annee), indisponibilites=[],
                               classe_id=cid)
        semaine = [s for s in toutes if lundi_iso <= s["date"] <= dimanche]
        types = {}
        if cl.get("mer_active"):
            rep = aff_svc.repartir_mer(
                semaine, cl.get("mer_mode") or "automatismes",
                aff_svc.lire_affectations(conn, cid, annee),
                aff_svc.dates_exceptions(conn, cid, annee))
            for cle, typ in (("automatisme", "mer_auto"), ("progression", "mer_prog")):
                for s in rep[cle]:
                    types[(s["date"], s["creneau_code"])] = typ
        for s in semaine:
            sortie.append({
                "classe_id": cid, "classe": cl["nom"], "niveau": cl.get("niveau"),
                "etablissement_id": infos["etablissement_id"],
                "date": s["date"], "jour": s["jour"], "creneau": s["creneau_code"],
                "heure_debut": s.get("heure_debut", ""),     # v0.43.0
                "heure_fin": s.get("heure_fin", ""),
                "edt_creneau_id": s.get("edt_creneau_id"),
                "libelle": libelles.get(s.get("edt_creneau_id"), ""),
                "type_mer": types.get((s["date"], s["creneau_code"])),
                "indispo": any(ind_svc.concerne_seance(ind, s, cid, ordre)
                               for ind in donnees["indispos"]),
            })
    return sortie
