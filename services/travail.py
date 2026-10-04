"""services/travail.py — v0.47.0

Travail à faire / à rendre et documents à rapporter (Suivi › Travail, même
séance que le Début de séance et l'Observation).

Un travail est un document de séance (`seance_documents`, origine
« travail ») distribué à la séance où il est donné : les élèves absents ce
jour-là le reçoivent ensuite par le rattrapage du Début de séance, exactement
comme un document. Un document distribué peut aussi être marqué « à
rapporter » (autorisation signée…). Champs ajoutés à `seance_documents` :
  - `retour` ∈ {'', 'faire', 'rendre', 'rapporter'} ;
  - `delai_jours` : délai de réalisation ; l'ÉCHÉANCE DE CHAQUE ÉLÈVE est la
    première séance de la classe au moins `delai_jours` jours après la date
    où IL a reçu le document (distribution, ou rattrapage s'il était absent) ;
  - `clos` : fenêtre close explicitement par l'enseignant.

Règles (validées) :
  - « à faire » : vérifié à la séance d'échéance de chaque élève ; on coche
    ceux qui ne l'ont pas fait (constat), avec en option « à rattraper » qui
    lui fixe une nouvelle échéance à la séance suivante (pour lui seul) ;
    les absents ne sont pas concernés ce jour-là ;
  - « à rendre » / « à rapporter » : coche « rendu » élève par élève, à
    n'importe quelle séance ; reste ouvert tant qu'un élève qui l'a reçu ne
    l'a pas rendu, sauf clôture ; après son échéance, l'élève est EN RETARD ;
  - récapitulatif de la classe : élèves ayant quelque chose en retard
    (à rendre / à rapporter non rendus après leur échéance). Un « à faire »
    non fait est un constat du jour (mot aux parents, hors appli) ; s'il est
    « à rattraper », il revient à vérifier à la séance suivante.
"""

from __future__ import annotations
import uuid
from datetime import date, timedelta

RETOURS = ("faire", "rendre", "rapporter")

# Migration : colonnes ajoutées à seance_documents + tables des retours.
COLONNES = (("retour", "TEXT NOT NULL DEFAULT ''"),
            ("delai_jours", "INTEGER NOT NULL DEFAULT 0"),
            ("clos", "INTEGER NOT NULL DEFAULT 0"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS retours (
    document_id TEXT NOT NULL,
    eleve_id    TEXT NOT NULL,
    statut      TEXT NOT NULL,            -- 'rendu' | 'non_fait'
    date        TEXT NOT NULL,
    creneau     TEXT NOT NULL,
    PRIMARY KEY (document_id, eleve_id, statut, date, creneau)
);
CREATE TABLE IF NOT EXISTS echeances_individuelles (
    document_id TEXT NOT NULL,
    eleve_id    TEXT NOT NULL,
    date        TEXT NOT NULL,
    creneau     TEXT NOT NULL,
    PRIMARY KEY (document_id, eleve_id)
);
"""


def migrer(conn) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(seance_documents)")}
    for nom, decl in COLONNES:
        if cols and nom not in cols:
            conn.execute(f"ALTER TABLE seance_documents ADD COLUMN {nom} {decl}")
    conn.executescript(SCHEMA)


class TravailErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides"):
        super().__init__(message)
        self.code = code


def _cle(d, c) -> tuple:
    return (d or "", c or "")


# ── Séances de la classe (pour les échéances) ────────────────────────────────

def seances_classe(conn, store, annee: str, classe_id: str) -> list[tuple]:
    """[(date, créneau)] des séances projetées de la classe, triées."""
    from services import contexte_projection as ctx
    infos = ctx.infos_classe(conn, classe_id)
    if infos is None:
        return []
    cal = ctx.calendrier(store, annee, infos["academie"])
    return sorted((s["date"], s["creneau_code"]) for s in
                  ctx.projeter_classe(conn, annee, classe_id, infos["etablissement_id"], cal))


def premiere_seance_apres(seances: list[tuple], depuis: str, jours: int,
                          strictement_apres: tuple | None = None) -> tuple | None:
    """Première séance dont la date est au moins `jours` jours après `depuis`
    (et, si donné, strictement après la séance `strictement_apres`)."""
    borne = (date.fromisoformat(depuis) + timedelta(days=max(jours, 0))).isoformat()
    for s in seances:
        if s[0] >= borne and (strictement_apres is None or s > strictement_apres):
            return s
    return None


def delai_vers(seances, depuis_seance: tuple, cible: tuple) -> int:
    """Délai (jours) correspondant à une échéance choisie explicitement."""
    return (date.fromisoformat(cible[0]) - date.fromisoformat(depuis_seance[0])).days


# ── Remises et échéances individuelles ───────────────────────────────────────

def _absents(conn, classe_id, d, c) -> set:
    return {r["eleve_id"] for r in conn.execute(
        "SELECT eleve_id FROM absences WHERE classe_id=? AND date=? AND creneau_code=?",
        (classe_id, d, c)).fetchall()}


def remises(conn, doc: dict, eleves_ids: list[str]) -> dict:
    """{eleve_id: (date, créneau)} : quand chaque élève a reçu le document."""
    if not doc["distribue_date"]:
        return {}
    abs_d = _absents(conn, doc["classe_id"], doc["distribue_date"], doc["distribue_creneau"])
    rattrap = {r["eleve_id"]: (r["date"], r["creneau"]) for r in conn.execute(
        "SELECT eleve_id, date, creneau FROM seance_remises WHERE document_id=?",
        (doc["id"],)).fetchall()}
    sortie = {}
    for eid in eleves_ids:
        if eid not in abs_d:
            sortie[eid] = (doc["distribue_date"], doc["distribue_creneau"])
        elif eid in rattrap:
            sortie[eid] = rattrap[eid]
    return sortie


def echeances(conn, doc: dict, remis: dict, seances: list[tuple]) -> dict:
    """{eleve_id: (date, créneau) | None} — échéance individuelle."""
    surcharges = {r["eleve_id"]: (r["date"], r["creneau"]) for r in conn.execute(
        "SELECT eleve_id, date, creneau FROM echeances_individuelles WHERE document_id=?",
        (doc["id"],)).fetchall()}
    sortie = {}
    for eid, rem in remis.items():
        if eid in surcharges:
            sortie[eid] = surcharges[eid]
        else:
            sortie[eid] = premiere_seance_apres(seances, rem[0], doc["delai_jours"],
                                                strictement_apres=rem)
    return sortie


def _statuts(conn, doc_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM retours WHERE document_id=?", (doc_id,)).fetchall()]


# ── Actions ──────────────────────────────────────────────────────────────────

def donner(conn, store, annee: str, classe_id: str, date_iso: str, creneau: str,
           libelle: str, retour: str, delai_jours: int | None = None,
           echeance: tuple | None = None) -> dict:
    """Donne un travail (à faire / à rendre) à la séance : distribué aussitôt
    aux présents ; les absents le recevront par le rattrapage."""
    libelle = (libelle or "").strip()
    if not libelle:
        raise TravailErreur("Le libellé du travail est obligatoire.")
    if retour not in ("faire", "rendre"):
        raise TravailErreur(f"Type de travail invalide : {retour!r}.")
    ici = (date_iso, creneau)
    if echeance:
        seances = seances_classe(conn, store, annee, classe_id)
        if tuple(echeance) not in seances or tuple(echeance) <= ici:
            raise TravailErreur("L'échéance doit être une séance à venir de la classe.")
        delai = delai_vers(seances, ici, tuple(echeance))
    else:
        delai = int(delai_jours if delai_jours is not None else 1)
    did = "sd_" + uuid.uuid4().hex[:12]
    conn.execute(
        "INSERT INTO seance_documents (id, classe_id, annee, origine, libelle, categorie, "
        "cible_date, cible_creneau, distribue_date, distribue_creneau, ordre, retour, "
        "delai_jours) VALUES (?,?,?, 'travail', ?, 'pedagogique', ?,?,?,?, 999, ?,?)",
        (did, classe_id, annee, libelle, date_iso, creneau, date_iso, creneau, retour, delai))
    return dict(conn.execute("SELECT * FROM seance_documents WHERE id=?", (did,)).fetchone())


def _doc(conn, doc_id: str) -> dict:
    r = conn.execute("SELECT * FROM seance_documents WHERE id=?", (doc_id,)).fetchone()
    if r is None:
        raise TravailErreur("Document ou travail introuvable.", "introuvable")
    return dict(r)


def definir_retour(conn, doc_id: str, retour: str, delai_jours: int = 7) -> dict:
    """Marque un document distribué comme « à rapporter » (ou l'en retire :
    `retour` = '')."""
    d = _doc(conn, doc_id)
    if d["origine"] == "travail":
        raise TravailErreur("Un travail se règle dans l'onglet Travail.")
    if retour not in ("", "rapporter"):
        raise TravailErreur(f"Retour invalide : {retour!r}.")
    conn.execute("UPDATE seance_documents SET retour=?, delai_jours=? WHERE id=?",
                 (retour, int(delai_jours or 0), doc_id))
    return _doc(conn, doc_id)


def supprimer_travail(conn, doc_id: str) -> None:
    d = _doc(conn, doc_id)
    if d["origine"] != "travail":
        raise TravailErreur("Ce n'est pas un travail.")
    for t in ("retours", "echeances_individuelles", "seance_remises"):
        conn.execute(f"DELETE FROM {t} WHERE document_id=?", (doc_id,))
    conn.execute("DELETE FROM seance_documents WHERE id=?", (doc_id,))


def clore(conn, doc_id: str, clos: bool) -> None:
    _doc(conn, doc_id)
    conn.execute("UPDATE seance_documents SET clos=? WHERE id=?", (1 if clos else 0, doc_id))


def marquer_rendu(conn, doc_id: str, eleve_id: str, date_iso: str, creneau: str,
                  rendu: bool) -> None:
    d = _doc(conn, doc_id)
    if d["retour"] not in ("rendre", "rapporter"):
        raise TravailErreur("Rien à rendre pour ce document.")
    conn.execute("DELETE FROM retours WHERE document_id=? AND eleve_id=? AND statut='rendu'",
                 (doc_id, eleve_id))
    if rendu:
        conn.execute("INSERT INTO retours (document_id, eleve_id, statut, date, creneau) "
                     "VALUES (?,?, 'rendu', ?,?)", (doc_id, eleve_id, date_iso, creneau))


def marquer_non_fait(conn, store, annee: str, doc_id: str, eleve_id: str,
                     date_iso: str, creneau: str, non_fait: bool,
                     a_rattraper: bool = False) -> None:
    """« à faire » vérifié à cette séance : non fait (constat) et, en option,
    à rattraper pour la séance suivante (échéance individuelle)."""
    d = _doc(conn, doc_id)
    if d["retour"] != "faire":
        raise TravailErreur("Ce travail n'est pas « à faire ».")
    conn.execute("DELETE FROM retours WHERE document_id=? AND eleve_id=? AND statut='non_fait' "
                 "AND date=? AND creneau=?", (doc_id, eleve_id, date_iso, creneau))
    ici = (date_iso, creneau)
    ech = conn.execute("SELECT date, creneau FROM echeances_individuelles WHERE "
                       "document_id=? AND eleve_id=?", (doc_id, eleve_id)).fetchone()
    # Retirer un rattrapage posé à CETTE séance (on recalcule ci-dessous).
    if ech and (ech["date"], ech["creneau"]) > ici:
        conn.execute("DELETE FROM echeances_individuelles WHERE document_id=? AND eleve_id=?",
                     (doc_id, eleve_id))
    if not non_fait:
        return
    conn.execute("INSERT INTO retours (document_id, eleve_id, statut, date, creneau) "
                 "VALUES (?,?, 'non_fait', ?,?)", (doc_id, eleve_id, date_iso, creneau))
    if a_rattraper:
        suiv = premiere_seance_apres(seances_classe(conn, store, annee, d["classe_id"]),
                                     date_iso, 0, strictement_apres=ici)
        if suiv is None:
            raise TravailErreur("Pas de séance suivante pour le rattrapage.")
        conn.execute("INSERT OR REPLACE INTO echeances_individuelles (document_id, eleve_id, "
                     "date, creneau) VALUES (?,?,?,?)", (doc_id, eleve_id, suiv[0], suiv[1]))


# ── Vue d'une séance ─────────────────────────────────────────────────────────

def pour_seance(conn, store, annee: str, classe_id: str, date_iso: str, creneau: str,
                eleves_ids: list[str]) -> dict:
    """{donnes_ici, a_verifier, a_ramasser, en_retard}."""
    ici = (date_iso, creneau)
    seances = seances_classe(conn, store, annee, classe_id)
    absents_ici = _absents(conn, classe_id, date_iso, creneau)
    docs = [dict(r) for r in conn.execute(
        "SELECT * FROM seance_documents WHERE classe_id=? AND annee=? AND retour<>'' "
        "AND distribue_date<>'' ORDER BY distribue_date, distribue_creneau, libelle",
        (classe_id, annee)).fetchall()]
    donnes_ici, a_verifier, a_ramasser = [], [], []
    retards: dict[str, list] = {}
    for d in docs:
        remis = remises(conn, d, eleves_ids)
        ech = echeances(conn, d, remis, seances)
        st = _statuts(conn, d["id"])
        rendus = {s["eleve_id"]: (s["date"], s["creneau"]) for s in st if s["statut"] == "rendu"}
        base = {"id": d["id"], "libelle": d["libelle"], "retour": d["retour"],
                "origine": d["origine"], "delai_jours": d["delai_jours"],
                "donne_date": d["distribue_date"], "clos": bool(d["clos"])}
        if d["origine"] == "travail" and _cle(d["distribue_date"], d["distribue_creneau"]) == ici:
            donnes_ici.append({**base, "echeance_classe": premiere_seance_apres(
                seances, date_iso, d["delai_jours"], strictement_apres=ici)})
        if d["retour"] == "faire":
            nf = {s["eleve_id"] for s in st if s["statut"] == "non_fait"
                  and (s["date"], s["creneau"]) == ici}
            # À vérifier ici : échéance à cette séance, ou déjà constaté non
            # fait ici (son échéance a pu glisser à la séance suivante).
            dus = [eid for eid in eleves_ids if eid in remis and eid not in absents_ici
                   and (ech.get(eid) == ici or eid in nf)]
            if dus:
                surch = {r["eleve_id"]: (r["date"], r["creneau"]) for r in conn.execute(
                    "SELECT * FROM echeances_individuelles WHERE document_id=?", (d["id"],))}
                a_verifier.append({**base, "eleves": [
                    {"eleve_id": eid, "non_fait": eid in nf,
                     "a_rattraper": eid in nf and eid in surch and surch[eid] > ici,
                     "rattrapage": eid in surch and surch[eid] == ici}
                    for eid in dus]})
        else:
            if d["clos"]:
                continue
            attendus = [eid for eid in remis if eid not in rendus]
            rendus_ici = [eid for eid, s in rendus.items() if s == ici]
            if attendus or rendus_ici:
                a_ramasser.append({**base, "eleves": [
                    {"eleve_id": eid, "rendu": eid in rendus,
                     "echeance": ech.get(eid),
                     "en_retard": bool(ech.get(eid)) and ech[eid] < ici}
                    for eid in eleves_ids if eid in set(attendus) | set(rendus_ici)]})
            for eid in attendus:
                if ech.get(eid) and ech[eid] < ici:
                    retards.setdefault(eid, []).append(
                        {"id": d["id"], "libelle": d["libelle"], "retour": d["retour"],
                         "echeance": ech[eid]})
    en_retard = [{"eleve_id": eid, "elements": retards[eid]}
                 for eid in eleves_ids if eid in retards]
    return {"donnes_ici": donnes_ici, "a_verifier": a_verifier,
            "a_ramasser": a_ramasser, "en_retard": en_retard}
