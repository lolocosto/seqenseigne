"""services/seances_resume.py — v0.51.14

Résumé de chaque séance d'un ensemble de cases (planification hebdo, tuile
Journée du tableau de bord) : MER, principale, documents à distribuer.

    {
      "mer": {"type": "auto", "enveloppes": [1, 3]}
           | {"type": "prog", "partie": {"libelle", "rang", "nb"} | None}
           | None,
      "principale": {"code", "nom", "partie": "2" | "1–2" | "" (une seule
                     partie dans la séquence), "rang", "nb"} | None,
      "docs": [libellé, ...],
    }

Les calculs coûteux (projection des séances de l'année, répartition des
MER, progression décalée, documents prévus) sont faits une fois par classe,
quel que soit le nombre de séances de la classe dans les cases demandées.
Mêmes règles que le détail d'une séance (services/planification_hebdo.py).
"""

from __future__ import annotations


def _contexte_classe(conn, store, annee: str, classe_id: str, calendriers: dict) -> dict | None:
    from services import affectation as aff_svc
    from services import contexte_projection as ctx
    from services import decalage_progression as dec_svc
    from services import documents_seance as ds
    from services import leitner
    from services import progression_mer as pm

    row = conn.execute(
        "SELECT c.niveau AS niveau, c.etablissement_id AS eid, c.mer_active AS mer_active, "
        "c.mer_mode AS mer_mode, e.academie AS aca FROM classes c LEFT JOIN etablissements e "
        "ON e.id=c.etablissement_id WHERE c.id=?", (classe_id,)).fetchone()
    if row is None:
        return None
    eid, aca = row["eid"], row["aca"] or ""
    if aca not in calendriers:
        calendriers[aca] = ctx.calendrier(store, annee, aca)
    cal = calendriers[aca]
    seances = ctx.projeter_classe(conn, annee, classe_id, eid, cal) if eid else []

    # MER : séance d'automatismes (enveloppes) ou de progression (partie).
    mer = {}
    if row["mer_active"] and seances:
        rep = aff_svc.repartir_mer([dict(s) for s in seances], row["mer_mode"] or "automatismes",
                                   aff_svc.lire_affectations(conn, classe_id, annee),
                                   aff_svc.dates_exceptions(conn, classe_id, annee))
        for i, s in enumerate(rep["automatisme"], start=1):
            mer[(s.get("date"), s.get("creneau_code"))] = {
                "type": "auto", "enveloppes": leitner.enveloppes_a_reviser(i)}
        prog_s = rep["progression"]
        for i, s in enumerate(prog_s, start=1):
            s["numero"] = i
        prog_mer = pm.lire_par_niveau(conn, row["niveau"], annee)
        parties = (prog_mer or {}).get("parties", [])
        for s in (pm.projeter_mer(prog_s, parties) if parties else prog_s):
            nb = s.get("mer_nb_partie") or 0
            partie = ({"libelle": s.get("mer_libelle") or s.get("mer_sequence") or "",
                       "rang": s.get("mer_rang_partie") or 0,
                       "nb": int(nb) if float(nb).is_integer() else nb}
                      if s.get("mer_partie_id") else None)
            mer[(s.get("date"), s.get("creneau_code"))] = {"type": "prog", "partie": partie}

    # Principale : créneaux de la progression décalée pour la classe.
    creneaux, ref_id = [], None
    prog = store.lire_progression_par_triplet(row["niveau"], annee, eid) if eid else None
    if prog:
        res = dec_svc.calculer_pour_classe(prog.get("creneaux", []),
                                           dec_svc.lister(conn, classe_id, annee),
                                           annee, cal["vacances"])
        creneaux = [c for c in res.get("creneaux", []) if c.get("date_debut")]
        ref_id = prog.get("referentiel_id")

    # Documents prévus (principale, placements automatiques, MER).
    docs: dict = {}
    try:
        for d in ds.documents_prevus(conn, store, annee, classe_id):
            docs.setdefault((d["date"], d["creneau"]), []).append(d)
    except Exception:
        docs = {}
    return {"seances": seances, "mer": mer, "creneaux": creneaux, "ref_id": ref_id,
            "docs": docs, "noms": {}, "nb_parties": {}}


def _sequence(conn, cx: dict, code: str) -> tuple[str, int]:
    """(nom, nombre de parties) d'une séquence du référentiel de la progression."""
    if code not in cx["noms"]:
        nom, nb = "", 0
        if cx["ref_id"] and code:
            r = conn.execute("SELECT nom FROM referentiel_sequences WHERE referentiel_id=? "
                             "AND code=?", (cx["ref_id"], code)).fetchone()
            nom = (r["nom"] if r else "") or ""
            nb = conn.execute("SELECT COUNT(*) FROM referentiel_parties WHERE "
                              "referentiel_id=? AND seq_code=?", (cx["ref_id"], code)).fetchone()[0]
        cx["noms"][code], cx["nb_parties"][code] = nom, nb
    return cx["noms"][code], cx["nb_parties"][code]


def _principale(conn, cx: dict, date_iso: str, creneau: str) -> dict | None:
    cr = next((c for c in cx["creneaux"]
               if c["date_debut"] <= date_iso <= (c.get("date_fin") or c["date_debut"])), None)
    if cr is None:
        return None
    code = cr.get("sequence") or cr.get("seq_code") or ""
    if not code:
        return None
    nom, nb_parties = _sequence(conn, cx, code)
    deb, fin = cr["date_debut"], cr.get("date_fin") or cr["date_debut"]
    dans = [s for s in cx["seances"] if deb <= (s.get("date") or "") <= fin]
    rang = next((i for i, s in enumerate(dans, start=1)
                 if s.get("date") == date_iso and s.get("creneau_code") == creneau), 0)
    pd, pf = int(cr.get("partie_debut") or 1), int(cr.get("partie_fin") or cr.get("partie_debut") or 1)
    partie = "" if nb_parties <= 1 else (str(pd) if pd == pf else f"{pd}–{pf}")
    return {"code": code, "nom": nom, "partie": partie, "rang": rang, "nb": len(dans)}


def resumer(conn, store, annee: str, cases: list) -> dict:
    """{(classe_id, date, creneau): résumé} pour les cases données
    ([{classe_id, date, creneau}])."""
    calendriers: dict = {}
    contextes: dict = {}
    out = {}
    for c in cases:
        cid, d, cr = c["classe_id"], c["date"], c["creneau"]
        if cid not in contextes:
            contextes[cid] = _contexte_classe(conn, store, annee, cid, calendriers)
        cx = contextes[cid]
        if cx is None:
            continue
        out[(cid, d, cr)] = {
            "mer": cx["mer"].get((d, cr)),
            "principale": _principale(conn, cx, d, cr),
            "docs": [x["libelle"] for x in sorted(cx["docs"].get((d, cr), []),
                                                   key=lambda x: x.get("ordre", 0))],
        }
    return out
