"""services/documents_seance.py — v0.44.0

Documents à distribuer en début de séance (Suivi › Début de séance) et suivi
de leur remise.

Deux origines :
  - **prévus** : associations document ↔ (créneau de progression principale,
    rang de séance) posées dans la planification (`progression_doc`) ; la
    séance cible est calculée comme dans le détail de séance de la
    planification hebdo (même progression, mêmes décalages, même projection) ;
  - **ponctuels** : ajoutés à la volée depuis le début de séance (libellé +
    catégorie), pour la séance affichée ou pour la séance suivante de la
    classe (ex. document confié par le professeur principal, urgent).

Règles (validées) :
  - « Nouveaux documents » d'une séance S : ceux dont la séance cible est S ou
    une séance antérieure et qui ne sont pas encore distribués (report : un
    document prévu non coché revient à la séance suivante), plus ceux
    distribués à S ;
  - cocher « distribué » à S : tous les élèves présents à S l'ont reçu ; les
    élèves absents à S (table `absences`, lue en direct) le doivent ;
  - « À rattraper » à S : pour chaque élève PRÉSENT à S, les documents
    distribués à une séance antérieure où il était absent, pas encore donnés
    (coche « donné » = remise individuelle à S) ;
  - le report des documents prévus ne remonte pas avant la première séance
    où le suivi des documents a été ouvert pour la classe
    (`docs_suivi.depuis`, posé automatiquement) : à la mise en service, les
    documents prévus des semaines passées ne déferlent pas.
"""

from __future__ import annotations
import uuid
from datetime import date, timedelta

CATEGORIES = ("pedagogique", "administratif", "sortie")

SCHEMA = """
CREATE TABLE IF NOT EXISTS seance_documents (
    id                  TEXT PRIMARY KEY,
    classe_id           TEXT NOT NULL,
    annee               TEXT NOT NULL,
    origine             TEXT NOT NULL,          -- 'prevu' | 'ponctuel'
    cle_prevu           TEXT NOT NULL DEFAULT '',
    libelle             TEXT NOT NULL,
    categorie           TEXT NOT NULL DEFAULT 'pedagogique',
    cible_date          TEXT NOT NULL,
    cible_creneau       TEXT NOT NULL,
    distribue_date      TEXT NOT NULL DEFAULT '',
    distribue_creneau   TEXT NOT NULL DEFAULT '',
    ordre               INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_seance_documents_prevu
    ON seance_documents (classe_id, annee, cle_prevu) WHERE cle_prevu <> '';
CREATE TABLE IF NOT EXISTS seance_remises (
    document_id TEXT NOT NULL,
    eleve_id    TEXT NOT NULL,
    date        TEXT NOT NULL,
    creneau     TEXT NOT NULL,
    PRIMARY KEY (document_id, eleve_id)
);
CREATE TABLE IF NOT EXISTS docs_suivi (
    classe_id TEXT NOT NULL,
    annee     TEXT NOT NULL,
    depuis    TEXT NOT NULL,
    PRIMARY KEY (classe_id, annee)
);
"""


class DocumentErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides"):
        super().__init__(message)
        self.code = code


def _cle(d: str, c: str) -> tuple:
    return (d or "", c or "")


# ── Documents prévus (progression principale) ────────────────────────────────

def documents_prevus(conn, store, annee: str, classe_id: str) -> list[dict]:  # noqa: C901
    """[{cle, libelle, date, creneau}] : chaque association document de la
    progression principale, placée sur sa séance (rang dans la partie)."""
    from services import contexte_projection as ctx
    from services import decalage_progression as dec_svc
    from services import progression_doc as pgd
    row = conn.execute("SELECT niveau FROM classes WHERE id=?", (classe_id,)).fetchone()
    infos = ctx.infos_classe(conn, classe_id)
    if row is None or infos is None or not infos["etablissement_id"]:
        return []
    eid = infos["etablissement_id"]
    prog = store.lire_progression_par_triplet(row["niveau"], annee, eid)
    if not prog:
        # v0.49.1 — Pas de progression principale : les documents de MER
        # restent placés.
        return _prevus_mer(conn, store, annee, classe_id, None)
    cal = ctx.calendrier(store, annee, infos["academie"])
    res = dec_svc.calculer_pour_classe(prog.get("creneaux", []),
                                       dec_svc.lister(conn, classe_id, annee),
                                       annee, cal["vacances"])
    seances = ctx.projeter_classe(conn, annee, classe_id, eid, cal)
    sortie = []
    for cr in res.get("creneaux", []):
        deb = cr.get("date_debut") or ""
        fin = cr.get("date_fin") or deb
        if not deb:
            continue
        dans = [s for s in seances if deb <= (s.get("date") or "") <= fin]
        try:
            assocs = pgd.lister(conn, "principale", prog.get("id", ""), cr.get("id", ""))
        except Exception:
            assocs = []
        for a in assocs:
            rang = int(a.get("rang_seance") or 0)
            if 1 <= rang <= len(dans):
                s = dans[rang - 1]
                # v0.48.0 — Retour attendu (à faire / à rendre) et délai ; « fin
                # du créneau » = dernière séance du créneau (même date pour tous).
                retour = a.get("retour") or ""
                dtype = a.get("delai_type") or ""
                fin = dans[-1] if (retour and dtype == "fin_creneau") else None
                sortie.append({"cle": f"{a.get('id')}", "date": s["date"],
                               "creneau": s["creneau_code"],
                               "libelle": a.get("doc_libelle") or a.get("doc_ref") or "Document",
                               "ordre": int(a.get("ordre") or 0),
                               "retour": retour,
                               "delai_jours": pgd.delai_en_jours(dtype, a.get("delai_n") or 1)
                               if retour else 0,
                               "echeance": (fin["date"], fin["creneau_code"]) if fin else None})
    sortie.extend(_placements_auto(conn, prog, res.get("creneaux", []), seances))
    sortie.extend(_prevus_mer(conn, store, annee, classe_id, seances))      # v0.49.1
    return sortie


def seances_mer(conn, store, annee: str, classe_id: str, seances: list | None = None):
    """v0.49.1 — (progression de MER, séances de MER « progression » de la
    classe enrichies de leur partie) ; None si la classe n'a pas de MER sur un
    référentiel de la structure figée."""
    from services import contexte_projection as ctx
    from services import affectation as aff_svc
    from services import progression_mer as pm
    row = conn.execute("SELECT niveau, mer_active, mer_mode FROM classes WHERE id=?",
                       (classe_id,)).fetchone()
    if row is None or not row["mer_active"]:
        return None
    prog = pm.lire_par_niveau(conn, row["niveau"], annee)
    if not prog or prog.get("ref_mer_source") != "fige" or not prog.get("ref_mer_id"):
        return None
    if seances is None:
        infos = ctx.infos_classe(conn, classe_id)
        cal = ctx.calendrier(store, annee, infos["academie"])
        seances = ctx.projeter_classe(conn, annee, classe_id, infos["etablissement_id"], cal)
    rep = aff_svc.repartir_mer([dict(s) for s in seances], row["mer_mode"] or "automatismes",
                               aff_svc.lire_affectations(conn, classe_id, annee),
                               aff_svc.dates_exceptions(conn, classe_id, annee))
    prog_s = rep["progression"]
    for i, s in enumerate(prog_s, start=1):
        s["numero"] = i
    pose_vers_partie = {p["id"]: p["partie_id"] for p in prog.get("parties", [])}
    sortie = []
    for s in pm.projeter_mer(prog_s, prog.get("parties", [])):
        if s.get("mer_partie_id"):
            s["partie_ref"] = pose_vers_partie.get(s["mer_partie_id"])
            sortie.append(s)
    return prog, sortie


def _prevus_mer(conn, store, annee, classe_id, seances) -> list[dict]:
    """v0.49.1 — Documents de MER : fichiers d'un référentiel de MER (structure
    figée) portant leur séance dans la partie (placement automatique à la
    séance de MER de ce rang dans la partie), et associations manuelles de la
    progression de MER (par partie et rang), qui remplacent le placement
    automatique du même fichier."""
    from services import progression_doc as pgd
    from services import referentiel_principal_externe as rpe
    try:
        r = seances_mer(conn, store, annee, classe_id, seances)
    except Exception:
        return []
    if not r:
        return []
    prog, smer = r
    rid = prog["ref_mer_id"]
    par_partie: dict[str, list] = {}
    for s in smer:
        par_partie.setdefault(s["partie_ref"], []).append(s)
    manuels = []
    for pref in par_partie:
        manuels.extend(pgd.lister(conn, "mer", prog["id"], pref))
    deja = {a["doc_ref"] for a in manuels}
    types = {t["id"]: t["libelle"] for t in conn.execute("SELECT id, libelle FROM types_documents")}
    fichiers = {f["id"]: f for f in conn.execute(
        "SELECT * FROM referentiel_fichiers WHERE referentiel_id=?", (rid,)).fetchall()}

    def _entree(cle, partie_ref, rang, libelle, retour, dtype, dn, ordre):
        dans = par_partie.get(partie_ref) or []
        if not 1 <= rang <= len(dans):
            return None
        s = dans[rang - 1]
        fin = dans[-1] if (retour and dtype in ("fin_partie", "fin_creneau")) else None
        return {"cle": cle, "date": s["date"], "creneau": s["creneau_code"],
                "libelle": libelle, "ordre": ordre, "retour": retour,
                "delai_jours": pgd.delai_en_jours(dtype, dn) if retour else 0,
                "echeance": (fin["date"], fin["creneau_code"]) if fin else None}

    sortie = []
    for a in manuels:
        e = _entree(f"mer:{a['id']}", a["creneau_ref"], int(a.get("rang_seance") or 0),
                    a.get("doc_libelle") or a.get("doc_ref") or "Document", a.get("retour") or "",
                    a.get("delai_type") or "", a.get("delai_n") or 1, int(a.get("ordre") or 0))
        if e:
            sortie.append(e)
    for f in rpe.placements_automatiques(conn, rid):
        if f["id"] in deja:
            continue
        pref = f"{rid}|{f['seq_code']}|{f['partie_numero']}"
        lib = (f"{types[f['type_id']]} : " if types.get(f["type_id"]) else "") + f["nom_fichier"]
        e = _entree(f"automer:{f['id']}", pref, int(f["seance_n"]), lib, f["retour"] or "",
                    f["delai_type"] or "", f["delai_n"] or 1, 500)
        if e:
            sortie.append(e)
    return sortie


def _placements_auto(conn, prog: dict, creneaux: list, seances: list) -> list[dict]:
    """v0.48.5 — Fichiers d'un référentiel principal externe portant leur
    séance de distribution dans la partie : placés à la séance de rang
    (séances des parties précédentes du créneau) + n du créneau qui couvre
    leur partie. Une association manuelle du même fichier dans la progression
    remplace ce placement."""
    from services import progression_doc as pgd
    from services import referentiel_principal_externe as rpe
    rid = prog.get("referentiel_id") or ""
    if not rid:
        return []
    try:
        fichiers = rpe.placements_automatiques(conn, rid)
    except Exception:
        return []
    if not fichiers:
        return []
    manuels = {r["doc_ref"] for r in conn.execute(
        "SELECT doc_ref FROM progression_doc WHERE prog_kind='principale' AND prog_ref=?",
        (prog.get("id", ""),)).fetchall()}
    nb_parties = {(r["seq_code"], r["numero"]): float(r["nb_seances_R_AE"] or 0)
                  for r in conn.execute("SELECT seq_code, numero, nb_seances_R_AE FROM "
                                        "referentiel_parties WHERE referentiel_id=?", (rid,))}
    types = {r["id"]: r["libelle"] for r in conn.execute("SELECT id, libelle FROM types_documents")}
    sortie = []
    for f in fichiers:
        if f["id"] in manuels:
            continue
        for cr in creneaux:
            seq = cr.get("seq_code") or cr.get("sequence")
            p0, p1 = int(cr.get("partie_debut") or 1), int(cr.get("partie_fin") or 1)
            if seq != f["seq_code"] or not (p0 <= f["partie_numero"] <= p1):
                continue
            deb = cr.get("date_debut") or ""
            fin = cr.get("date_fin") or deb
            if not deb:
                continue
            dans = [s for s in seances if deb <= (s.get("date") or "") <= fin]
            avant = int(round(sum(nb_parties.get((seq, k), 0) for k in range(p0, f["partie_numero"]))))
            rang = avant + int(f["seance_n"])
            if not 1 <= rang <= len(dans):
                continue
            s = dans[rang - 1]
            retour = f.get("retour") or ""
            dtype = f.get("delai_type") or ""
            ech = dans[-1] if (retour and dtype == "fin_creneau") else None
            lib = (f"{types[f['type_id']]} : " if types.get(f.get("type_id")) else "") + f["nom_fichier"]
            sortie.append({"cle": f"auto:{f['id']}:{cr.get('id', '')}", "date": s["date"],
                           "creneau": s["creneau_code"], "libelle": lib, "ordre": 500,
                           "retour": retour,
                           "delai_jours": pgd.delai_en_jours(dtype, f.get("delai_n") or 1)
                           if retour else 0,
                           "echeance": (ech["date"], ech["creneau_code"]) if ech else None})
            break
    return sortie


def _suivi_depuis(conn, classe_id: str, annee: str, date_iso: str) -> str:
    r = conn.execute("SELECT depuis FROM docs_suivi WHERE classe_id=? AND annee=?",
                     (classe_id, annee)).fetchone()
    if r:
        return r["depuis"]
    conn.execute("INSERT INTO docs_suivi (classe_id, annee, depuis) VALUES (?,?,?)",
                 (classe_id, annee, date_iso))
    return date_iso


def _materialiser_prevus(conn, store, annee, classe_id, date_iso, creneau) -> None:
    """Crée (une fois) les lignes des documents prévus dont la séance cible est
    la séance affichée ou antérieure, depuis l'ouverture du suivi."""
    depuis = _suivi_depuis(conn, classe_id, annee, date_iso)
    for p in documents_prevus(conn, store, annee, classe_id):
        if not (depuis <= p["date"] and _cle(p["date"], p["creneau"]) <= _cle(date_iso, creneau)):
            continue
        ech = p.get("echeance") or ("", "")
        conn.execute(
            "INSERT OR IGNORE INTO seance_documents (id, classe_id, annee, origine, "
            "cle_prevu, libelle, categorie, cible_date, cible_creneau, ordre, retour, "
            "delai_jours, echeance_date, echeance_creneau) "
            "VALUES (?,?,?, 'prevu', ?,?, 'pedagogique', ?,?,?,?,?,?,?)",
            ("sd_" + uuid.uuid4().hex[:12], classe_id, annee, p["cle"], p["libelle"],
             p["date"], p["creneau"], p["ordre"], p.get("retour", ""),
             p.get("delai_jours", 0), ech[0], ech[1]))
        # v0.48.0 — Tant qu'il n'est pas distribué, un document prévu suit les
        # changements de son association (libellé, retour, délai).
        conn.execute(
            "UPDATE seance_documents SET libelle=?, retour=?, delai_jours=?, "
            "echeance_date=?, echeance_creneau=? WHERE classe_id=? AND annee=? "
            "AND cle_prevu=? AND distribue_date=''",
            (p["libelle"], p.get("retour", ""), p.get("delai_jours", 0), ech[0], ech[1],
             classe_id, annee, p["cle"]))


# ── Lecture pour une séance ──────────────────────────────────────────────────

def _absents(conn, classe_id, d, c) -> set:
    return {r["eleve_id"] for r in conn.execute(
        "SELECT eleve_id FROM absences WHERE classe_id=? AND date=? AND creneau_code=?",
        (classe_id, d, c)).fetchall()}


def pour_seance(conn, store, annee: str, classe_id: str, date_iso: str,
                creneau: str, eleves_ids: list[str]) -> dict:
    """{nouveaux: [...], a_rattraper: [{eleve_id, documents: [...]}]}."""
    _materialiser_prevus(conn, store, annee, classe_id, date_iso, creneau)
    ici = _cle(date_iso, creneau)
    docs = [dict(r) for r in conn.execute(
        "SELECT * FROM seance_documents WHERE classe_id=? AND annee=? "
        "ORDER BY cible_date, cible_creneau, ordre, libelle", (classe_id, annee)).fetchall()]
    nouveaux = []
    for d in docs:
        if d.get("origine") == "travail":
            continue          # v0.47.0 — géré dans Suivi › Travail
        distrib = _cle(d["distribue_date"], d["distribue_creneau"])
        cible = _cle(d["cible_date"], d["cible_creneau"])
        if (d["distribue_date"] and distrib == ici) or (not d["distribue_date"] and cible <= ici):
            nouveaux.append({**d, "distribue": bool(d["distribue_date"]),
                             "reporte": cible < ici})
    absents_ici = _absents(conn, classe_id, date_iso, creneau)
    remises = {(r["document_id"], r["eleve_id"]): (r["date"], r["creneau"])
               for r in conn.execute(
                   "SELECT r.* FROM seance_remises r JOIN seance_documents d "
                   "ON d.id = r.document_id WHERE d.classe_id=? AND d.annee=?",
                   (classe_id, annee)).fetchall()}
    cache_abs: dict[tuple, set] = {}
    a_rattraper = []
    for eid in eleves_ids:
        if eid in absents_ici:
            continue
        dus = []
        for d in docs:
            distrib = _cle(d["distribue_date"], d["distribue_creneau"])
            if not d["distribue_date"] or distrib >= ici:
                continue
            if distrib not in cache_abs:
                cache_abs[distrib] = _absents(conn, classe_id, *distrib)
            if eid not in cache_abs[distrib]:
                continue
            r = remises.get((d["id"], eid))
            if r is None or _cle(*r) == ici:
                dus.append({"id": d["id"], "libelle": d["libelle"],
                            "categorie": d["categorie"], "origine": d["origine"],
                            "retour": d.get("retour", ""),
                            "distribue_date": d["distribue_date"],
                            "donne": r is not None})
        if dus:
            a_rattraper.append({"eleve_id": eid, "documents": dus})
    return {"nouveaux": nouveaux, "a_rattraper": a_rattraper}


# ── Actions ──────────────────────────────────────────────────────────────────

def _doc(conn, document_id: str) -> dict:
    r = conn.execute("SELECT * FROM seance_documents WHERE id=?", (document_id,)).fetchone()
    if r is None:
        raise DocumentErreur("Document introuvable.", "introuvable")
    return dict(r)


def marquer_distribue(conn, document_id: str, date_iso: str, creneau: str,
                      distribue: bool) -> None:
    d = _doc(conn, document_id)
    if distribue:
        if _cle(d["cible_date"], d["cible_creneau"]) > _cle(date_iso, creneau):
            raise DocumentErreur("Ce document est prévu pour une séance à venir.")
        conn.execute("UPDATE seance_documents SET distribue_date=?, distribue_creneau=? "
                     "WHERE id=?", (date_iso, creneau, document_id))
    else:
        if d["distribue_date"] and _cle(d["distribue_date"], d["distribue_creneau"]) != _cle(date_iso, creneau):
            raise DocumentErreur("Ce document a été distribué à une autre séance.")
        conn.execute("UPDATE seance_documents SET distribue_date='', distribue_creneau='' "
                     "WHERE id=?", (document_id,))
        conn.execute("DELETE FROM seance_remises WHERE document_id=?", (document_id,))


def ajouter_ponctuel(conn, annee: str, classe_id: str, libelle: str, categorie: str,
                     cible_date: str, cible_creneau: str) -> dict:
    libelle = (libelle or "").strip()
    if not libelle:
        raise DocumentErreur("Le libellé du document est obligatoire.")
    if categorie not in CATEGORIES:
        raise DocumentErreur(f"Catégorie invalide : {categorie!r}.")
    did = "sd_" + uuid.uuid4().hex[:12]
    conn.execute(
        "INSERT INTO seance_documents (id, classe_id, annee, origine, libelle, "
        "categorie, cible_date, cible_creneau, ordre) VALUES (?,?,?, 'ponctuel', ?,?,?,?, 999)",
        (did, classe_id, annee, libelle, categorie, cible_date, cible_creneau))
    return _doc(conn, did)


def supprimer_ponctuel(conn, document_id: str) -> None:
    d = _doc(conn, document_id)
    if d["origine"] != "ponctuel":
        raise DocumentErreur("Seuls les documents ajoutés à la volée se suppriment ici.")
    conn.execute("DELETE FROM seance_remises WHERE document_id=?", (document_id,))
    conn.execute("DELETE FROM seance_documents WHERE id=?", (document_id,))


def marquer_donne(conn, document_id: str, eleve_id: str, date_iso: str,
                  creneau: str, donne: bool) -> None:
    _doc(conn, document_id)
    if donne:
        conn.execute("INSERT OR REPLACE INTO seance_remises (document_id, eleve_id, "
                     "date, creneau) VALUES (?,?,?,?)",
                     (document_id, eleve_id, date_iso, creneau))
    else:
        conn.execute("DELETE FROM seance_remises WHERE document_id=? AND eleve_id=?",
                     (document_id, eleve_id))
