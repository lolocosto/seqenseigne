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

def documents_prevus(conn, store, annee: str, classe_id: str) -> list[dict]:
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
        return []
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
                sortie.append({"cle": f"{a.get('id')}", "date": s["date"],
                               "creneau": s["creneau_code"],
                               "libelle": a.get("doc_libelle") or a.get("doc_ref") or "Document",
                               "ordre": int(a.get("ordre") or 0)})
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
        conn.execute(
            "INSERT OR IGNORE INTO seance_documents (id, classe_id, annee, origine, "
            "cle_prevu, libelle, categorie, cible_date, cible_creneau, ordre) "
            "VALUES (?,?,?, 'prevu', ?,?, 'pedagogique', ?,?,?)",
            ("sd_" + uuid.uuid4().hex[:12], classe_id, annee, p["cle"], p["libelle"],
             p["date"], p["creneau"], p["ordre"]))


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
