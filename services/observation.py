"""services/observation.py — v0.46.0

Observation de l'activité en séance (Suivi › Observation), sur la même séance
que le début de séance.

Une occurrence = (classe, élève, date, créneau, observable, heure). Plusieurs
occurrences possibles par élève et par observable ; correction par
suppression d'une occurrence ou « annuler la dernière » de l'élève.

Règles : l'élève doit être présent (pas absent à la séance) ; l'observable
doit figurer dans SA liste effective ce jour-là (observables du niveau de la
classe, exceptions comprises — services/observables.liste_effective).
Le libellé affiché est celui de l'observable (renommage → nouveau libellé).

Données de mineurs (sanctions comprises) : base locale, jamais poussée ; à
intégrer au futur processus de conservation de fin d'année.
"""

from __future__ import annotations
import uuid
from datetime import date, datetime

from services import observables as obs_svc

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id            TEXT PRIMARY KEY,
    classe_id     TEXT NOT NULL,
    eleve_id      TEXT NOT NULL,
    date          TEXT NOT NULL,
    creneau_code  TEXT NOT NULL,
    observable_id TEXT NOT NULL,
    horodatage    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_observations_seance
    ON observations (classe_id, date, creneau_code);
CREATE INDEX IF NOT EXISTS idx_observations_eleve ON observations (eleve_id, date);
"""


class ObservationErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides"):
        super().__init__(message)
        self.code = code


def _niveau(conn, classe_id: str) -> str:
    r = conn.execute("SELECT niveau FROM classes WHERE id=?", (classe_id,)).fetchone()
    if r is None:
        raise ObservationErreur("Classe introuvable.", "introuvable")
    return r["niveau"] or ""


def lire(conn, classe_id: str, date_iso: str, creneau: str) -> dict:
    """{niveau, occurrences: [...], compteurs: {eleve_id: {valoriser, sanctionner}}}."""
    niveau = _niveau(conn, classe_id)
    occ = [dict(r) for r in conn.execute(
        "SELECT o.id, o.eleve_id, o.observable_id, o.horodatage, b.libelle, b.section "
        "FROM observations o LEFT JOIN observables b ON b.id=o.observable_id "
        "WHERE o.classe_id=? AND o.date=? AND o.creneau_code=? ORDER BY o.horodatage, o.rowid",
        (classe_id, date_iso, creneau)).fetchall()]
    compteurs: dict[str, dict] = {}
    for o in occ:
        c = compteurs.setdefault(o["eleve_id"], {"valoriser": 0, "sanctionner": 0})
        if o["section"] in c:
            c[o["section"]] += 1
    return {"niveau": niveau, "occurrences": occ, "compteurs": compteurs}


def ajouter(conn, store, annee: str, classe_id: str, eleve_id: str, date_iso: str,
            creneau: str, observable_id: str, maintenant: datetime | None = None) -> dict:
    from services import seance as sc
    from services import plans_classe as pc
    try:
        sc._seance(conn, store, annee, classe_id, date_iso, creneau)
    except sc.SeanceErreur as e:
        raise ObservationErreur(str(e), e.code)
    lundi = sc._lundi(date.fromisoformat(date_iso)).isoformat()
    if eleve_id not in {e["id"] for e in pc.eleves_de_la_semaine(conn, classe_id, lundi)}:
        raise ObservationErreur("Élève absent de la classe cette semaine-là.")
    if eleve_id in sc.absents(conn, classe_id, date_iso, creneau):
        raise ObservationErreur("Élève noté absent à cette séance.")
    eff = obs_svc.liste_effective(conn, _niveau(conn, classe_id), eleve_id, date_iso)
    if observable_id not in {o["id"] for sec in eff.values() for o in sec}:
        raise ObservationErreur("Cet observable ne s'applique pas à cet élève ce jour-là.")
    horo = (maintenant or datetime.now()).isoformat(timespec="seconds")
    conn.execute("INSERT INTO observations (id, classe_id, eleve_id, date, creneau_code, "
                 "observable_id, horodatage) VALUES (?,?,?,?,?,?,?)",
                 ("ov_" + uuid.uuid4().hex[:12], classe_id, eleve_id, date_iso, creneau,
                  observable_id, horo))
    return lire(conn, classe_id, date_iso, creneau)


def supprimer(conn, occurrence_id: str) -> dict:
    r = conn.execute("SELECT classe_id, date, creneau_code FROM observations WHERE id=?",
                     (occurrence_id,)).fetchone()
    if r is None:
        raise ObservationErreur("Occurrence introuvable.", "introuvable")
    conn.execute("DELETE FROM observations WHERE id=?", (occurrence_id,))
    return lire(conn, r["classe_id"], r["date"], r["creneau_code"])


def annuler_derniere(conn, classe_id: str, date_iso: str, creneau: str,
                     eleve_id: str) -> dict:
    r = conn.execute("SELECT id FROM observations WHERE classe_id=? AND date=? AND "
                     "creneau_code=? AND eleve_id=? ORDER BY horodatage DESC, rowid DESC "
                     "LIMIT 1", (classe_id, date_iso, creneau, eleve_id)).fetchone()
    if r:
        conn.execute("DELETE FROM observations WHERE id=?", (r["id"],))
    return lire(conn, classe_id, date_iso, creneau)
