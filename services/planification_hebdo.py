"""services/planification_hebdo.py — v0.32.0

Vue « Planification hebdo » : une semaine calendaire (toutes classes), avec pour
chaque séance son créneau, sa classe, son type de MER et l'indisponibilité
éventuelle. Le détail riche d'une séance (séquence principale en cours) est
calculé à la demande (au clic), pas pour toute la grille.

Le service ne fait qu'assembler des données déjà produites ailleurs (EdT,
affectation MER, indisponibilités, progression réalisée) ; le client se contente
d'afficher.
"""

from __future__ import annotations
from datetime import date, timedelta

_JOURS = ["lun", "mar", "mer", "jeu", "ven"]


def _lundi_de(d: date) -> date:
    return d - timedelta(days=d.weekday())


def semaine_de(annee: str, lundi_iso: str | None) -> dict:
    """Bornes de la semaine à afficher (lundi..vendredi ISO). Si lundi_iso est
    None, on prend la semaine de la date du jour, bornée à l'année scolaire."""
    if lundi_iso:
        try:
            lundi = _lundi_de(date.fromisoformat(lundi_iso))
        except ValueError:
            lundi = _lundi_de(date.today())
    else:
        lundi = _lundi_de(date.today())
    return {"lundi": lundi.isoformat(),
            "vendredi": (lundi + timedelta(days=4)).isoformat(),
            "jours": [(lundi + timedelta(days=i)).isoformat() for i in range(5)]}


def grille_semaine(conn, store, annee: str, lundi_iso: str | None,
                   etablissement_id: str | None = None) -> dict:
    """Grille légère de la semaine : toutes les classes, séances comptées
    (classe entière, cours), avec créneau, type MER et indisponibilité.

    Retour : {
      "lundi", "vendredi", "jours": [iso...],
      "creneaux": [codes de la grille horaire, ordonnés],
      "cases": [ {jour, date, creneau, classe_id, classe, niveau,
                  type_mer, indispo} ]
    }
    """
    from services import edt as edt_svc
    from services import affectation as aff_svc
    from services import grille_horaire as gh_svc
    from services import indisponibilites as ind_svc
    from services import contexte_projection as ctx

    sem = semaine_de(annee, lundi_iso)
    dates = sem["jours"]
    date_par_jour = dict(zip(_JOURS, dates))

    # Grille horaire (codes de créneaux), depuis l'établissement de référence.
    creneaux_grille = []
    ordre_creneau = {}
    row_etab = conn.execute(
        "SELECT id FROM etablissements" + (" WHERE id=?" if etablissement_id
                                           else " LIMIT 1"),
        (etablissement_id,) if etablissement_id else ()).fetchone()
    eid = row_etab["id"] if row_etab else None
    if eid:
        for g in gh_svc.lister(conn, eid):
            creneaux_grille.append(g["code"])
            ordre_creneau[g["code"]] = g.get("ordre", 0)

    indispos = ind_svc.lister(conn, annee, etablissement_id=eid) if eid else []

    # v0.32.3 — Statut de chaque jour de la semaine : en vacances (avec le nom
    # de la période) et/ou férié, pour afficher les jours/semaines non
    # travaillés comme tels.
    r_aca = conn.execute(
        "SELECT academie FROM etablissements WHERE id=?", (eid,)).fetchone() \
        if eid else None
    academie = (r_aca["academie"] if r_aca else "") or ""
    cal_s = ctx.calendrier(store, annee, academie)
    vacances_periodes, feries = cal_s["vacances"], cal_s["feries"]

    def _vac_du_jour(iso):
        for p in vacances_periodes:
            deb = p.get("start_date") or ""
            fin = p.get("end_date") or ""
            if deb and fin and deb <= iso < fin:
                return (p.get("description") or "Vacances").strip()
        return None

    jours_info = []
    for i, j in enumerate(_JOURS):
        iso = dates[i]
        jours_info.append({
            "jour": j, "date": iso,
            "vacances": _vac_du_jour(iso),
            "ferie": feries.get(iso) or None,
        })
    semaine_vacances = all(ji["vacances"] for ji in jours_info)

    classes = conn.execute(
        "SELECT id, nom, niveau, mer_active, mer_mode FROM classes "
        "WHERE annee=?", (annee,)).fetchall()

    cases = []
    for cl in classes:
        cid = cl["id"]
        # v0.38.0 — cases valides la semaine affichée (EdT versionné).
        edt_cases = edt_svc.lister(conn, annee, classe_id=cid,
                                   a_la_date=date.fromisoformat(sem["lundi"]))
        comptees = [x for x in edt_cases if edt_svc.est_compte(x)]
        affectations = aff_svc.lire_affectations(conn, cid, annee)
        mer_mode = cl["mer_mode"] or "automatismes"
        mer_on = bool(cl["mer_active"])
        for case in comptees:
            j = case.get("jour")
            if j not in date_par_jour:
                continue
            d_iso = date_par_jour[j]
            # Type MER du créneau.
            type_mer = None
            if mer_on:
                aff = affectations.get(case.get("id"))
                if aff is None:
                    aff = ("aucun" if mer_mode == "panache"
                           else ("progression" if mer_mode == "progression"
                                 else "automatisme"))
                if aff == "automatisme":
                    type_mer = "mer_auto"
                elif aff == "progression":
                    type_mer = "mer_prog"
            # Indisponibilité sur cette séance ?
            seance = {"date": d_iso, "creneau_code": case.get("creneau_code", "")}
            indispo = any(
                ind_svc.concerne_seance(ind, seance, cid, ordre_creneau)
                for ind in indispos)
            cases.append({
                "jour": j, "date": d_iso,
                "creneau": case.get("creneau_code", ""),
                "classe_id": cid, "classe": cl["nom"], "niveau": cl["niveau"],
                "type_mer": type_mer or "principale",
                "indispo": indispo,
                "edt_creneau_id": case.get("id"),
            })
    cases.sort(key=lambda c: (c["date"], ordre_creneau.get(c["creneau"], 0),
                              c["classe"]))
    return {**sem, "creneaux": creneaux_grille, "cases": cases,
            "jours_info": jours_info, "semaine_vacances": semaine_vacances}


def detail_seance(conn, store, annee: str, classe_id: str, date_iso: str,
                  creneau: str) -> dict:
    """Détail (lecture) enrichi d'une séance :
      - MER : type (automatismes / progression) ; en auto, enveloppes à réviser
        (numéros) à cette séance ;
      - Principal : code + nom de séquence, partie (1ère/2ème…), et rang de la
        séance dans la partie.
    """
    from services import contexte_projection as ctx
    from services import decalage_progression as dec_svc
    from services import affectation as aff_svc
    from services import leitner

    row = conn.execute(
        "SELECT c.nom AS nom, c.niveau AS niveau, c.etablissement_id AS eid, "
        "c.mer_active AS mer_active, c.mer_mode AS mer_mode, "
        "e.academie AS aca FROM classes c LEFT JOIN etablissements e "
        "ON e.id=c.etablissement_id WHERE c.id=?", (classe_id,)).fetchone()
    if row is None:
        return {}
    eid = row["eid"]
    academie = row["aca"] or ""
    # Calendrier commun.
    cal_s = ctx.calendrier(store, annee, academie)
    vacances = cal_s["vacances"]

    # ── MER : type + enveloppes (si automatismes) ────────────────────────────
    mer_type = None       # 'mer_auto' | 'mer_prog' | None
    mer_enveloppes = []
    if row["mer_active"]:
        affectations = aff_svc.lire_affectations(conn, classe_id, annee)
        exceptions = aff_svc.dates_exceptions(conn, classe_id, annee)
        mer_mode = row["mer_mode"] or "automatismes"
        seances = ctx.projeter_classe(conn, annee, classe_id, eid, cal_s)
        reparties = aff_svc.repartir_mer(seances, mer_mode, affectations,
                                         exceptions)
        # La séance de MER auto qui correspond à (date, créneau) ?
        auto = reparties["automatisme"]
        for i, s in enumerate(auto, start=1):
            if s.get("date") == date_iso and s.get("creneau_code") == creneau:
                mer_type = "mer_auto"
                mer_enveloppes = leitner.enveloppes_a_reviser(i)
                break
        if mer_type is None:
            prog_seances = reparties["progression"]
            if any(s.get("date") == date_iso and s.get("creneau_code") == creneau
                   for s in prog_seances):
                mer_type = "mer_prog"

    # ── Principal : séquence (code + nom), partie, rang dans la partie ───────
    seq_code, seq_nom, partie_lib = "", "", ""
    rang_dans_partie = 0
    nb_partie = 0
    prog = store.lire_progression_par_triplet(row["niveau"], annee, eid) \
        if eid else None
    if prog:
        decalages = dec_svc.lister(conn, classe_id, annee)
        res = dec_svc.calculer_pour_classe(prog.get("creneaux", []),
                                           decalages, annee, vacances)
        creneau_courant = None
        for cr in res.get("creneaux", []):
            deb = cr.get("date_debut") or ""
            fin = cr.get("date_fin") or deb
            if deb and deb <= date_iso <= fin:
                creneau_courant = cr
                break
        if creneau_courant:
            seq_code = creneau_courant.get("sequence") or ""
            partie_lib = (creneau_courant.get("partie") or "").strip()
            # Nom de séquence via le référentiel de la progression.
            ref_id = prog.get("referentiel_id")
            if ref_id and seq_code:
                r = conn.execute(
                    "SELECT nom FROM referentiel_sequences WHERE "
                    "referentiel_id=? AND code=?", (ref_id, seq_code)).fetchone()
                if r:
                    seq_nom = r["nom"] or ""
            # Rang de la séance dans la partie : nb de séances comptées
            # (principale) de la classe depuis le début du créneau jusqu'à
            # cette date incluse. On réutilise l'EdT principal.
            seances = ctx.projeter_classe(conn, annee, classe_id, eid, cal_s)
            deb_cr = creneau_courant.get("date_debut") or ""
            rang = 0
            for s in seances:
                sd = s.get("date") or ""
                if deb_cr <= sd <= date_iso:
                    rang += 1
                    if sd == date_iso and s.get("creneau_code") == creneau:
                        rang_dans_partie = rang
            # nb total de séances de la partie (dans sa plage de dates)
            fin_cr = creneau_courant.get("date_fin") or deb_cr
            nb_partie = sum(1 for s in seances
                            if deb_cr <= (s.get("date") or "") <= fin_cr)

    # v0.32.6 — Documents à distribuer à cette séance : associations posées au
    # niveau (progression principale), pour ce créneau et ce rang de séance.
    docs_a_distribuer = []
    if prog and creneau_courant and rang_dans_partie:
        from services import progression_doc as pgd
        try:
            assocs = pgd.lister(conn, "principale", prog.get("id", ""),
                                creneau_courant.get("id", ""))
            docs_a_distribuer = [
                {"libelle": a.get("doc_libelle") or a.get("doc_ref"),
                 "doc_source": a.get("doc_source"), "doc_ref": a.get("doc_ref")}
                for a in assocs
                if int(a.get("rang_seance") or 0) == rang_dans_partie]
        except Exception:
            docs_a_distribuer = []

    return {
        "classe_id": classe_id, "classe": row["nom"], "niveau": row["niveau"],
        "date": date_iso, "creneau": creneau,
        "mer_type": mer_type, "mer_enveloppes": mer_enveloppes,
        "sequence_code": seq_code, "sequence_nom": seq_nom,
        "partie": partie_lib,
        "rang_dans_partie": rang_dans_partie, "nb_partie": nb_partie,
        "docs_a_distribuer": docs_a_distribuer,
    }
