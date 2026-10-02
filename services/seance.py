"""services/seance.py — v0.43.0

Début de séance (onglet Suivi › Début de séance) :
  - séance en cours (ou prochaine, ou dernière de la journée) d'après l'heure,
    à partir de la projection (alternance A/B, fériés, versions d'EdT) ;
  - séances du jour d'une classe ;
  - mise en route de la séance (reprise du détail de séance de la
    planification hebdo) ;
  - absences : une ligne par (classe, élève, date, créneau), enregistrées à
    chaque clic, modifiables après la séance.

Seuls les cours en classe entière (séances projetées) sont concernés ; les
séances touchées par une indisponibilité sont écartées.

Données de mineurs : la table `absences` reste dans la base locale (jamais
poussée) ; à intégrer au futur processus de conservation en fin d'année.
"""

from __future__ import annotations
from datetime import date, datetime, timedelta

from services import contexte_projection as ctx
from services import plans_classe as pc_svc

SCHEMA = """
CREATE TABLE IF NOT EXISTS absences (
    classe_id    TEXT NOT NULL,
    eleve_id     TEXT NOT NULL,
    date         TEXT NOT NULL,
    creneau_code TEXT NOT NULL,
    PRIMARY KEY (classe_id, eleve_id, date, creneau_code)
);
CREATE INDEX IF NOT EXISTS idx_absences_seance
    ON absences (classe_id, date, creneau_code);
"""


class SeanceErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides"):
        super().__init__(message)
        self.code = code


def _lundi(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _classes_annee(conn, annee: str, classe_id: str | None = None) -> list[dict]:
    q = ("SELECT id, nom, niveau, mer_active, mer_mode FROM classes "
         "WHERE annee=?")
    params = [annee]
    if classe_id:
        q += " AND id=?"
        params.append(classe_id)
    return [dict(r) for r in conn.execute(q, params).fetchall()]


def seances_du_jour(conn, store, annee: str, jour: date,
                    classe_id: str | None = None) -> list[dict]:
    """Séances du jour (une classe ou toutes), sans celles touchées par une
    indisponibilité, triées par heure de début."""
    classes = _classes_annee(conn, annee, classe_id)
    if not classes:
        return []
    sem = ctx.seances_de_la_semaine(conn, store, annee, _lundi(jour).isoformat(),
                                    classes=classes)
    iso = jour.isoformat()
    jour_s = [x for x in sem if x["date"] == iso and not x["indispo"]]
    return sorted(jour_s, key=lambda x: (x["heure_debut"] or "99", x["classe"]))


def statut(seance: dict, maintenant: datetime) -> str:
    """'en_cours' | 'a_venir' | 'terminee' (par rapport à `maintenant`)."""
    if seance["date"] != maintenant.date().isoformat():
        return "a_venir" if seance["date"] > maintenant.date().isoformat() else "terminee"
    hm = maintenant.strftime("%H:%M")
    if seance["heure_debut"] and hm < seance["heure_debut"]:
        return "a_venir"
    if seance["heure_fin"] and hm >= seance["heure_fin"]:
        return "terminee"
    return "en_cours"


def seance_en_cours(conn, store, annee: str, maintenant: datetime,
                    classe_id: str | None = None) -> dict | None:
    """La séance dont le créneau contient l'heure ; sinon la prochaine de la
    journée (« pas encore commencée ») ; sinon la dernière de la journée
    (« terminée »). None si aucune séance ce jour-là."""
    jour = seances_du_jour(conn, store, annee, maintenant.date(), classe_id)
    if not jour:
        return None
    for s in jour:
        s["statut"] = statut(s, maintenant)
    for cible in ("en_cours", "a_venir"):
        trouvees = [s for s in jour if s["statut"] == cible]
        if trouvees:
            return trouvees[0]
    return jour[-1]


def _salle_de_la_case(conn, edt_creneau_id: str | None):
    if not edt_creneau_id:
        return None
    r = conn.execute("SELECT salle_id FROM edt_creneaux WHERE id=?",
                     (edt_creneau_id,)).fetchone()
    return r["salle_id"] if r and r["salle_id"] else None


def absents(conn, classe_id: str, date_iso: str, creneau: str) -> list[str]:
    return [r["eleve_id"] for r in conn.execute(
        "SELECT eleve_id FROM absences WHERE classe_id=? AND date=? AND "
        "creneau_code=? ORDER BY eleve_id", (classe_id, date_iso, creneau)).fetchall()]


def _seance(conn, store, annee, classe_id, date_iso, creneau) -> dict:
    try:
        jour = date.fromisoformat(date_iso)
    except (TypeError, ValueError):
        raise SeanceErreur(f"Date invalide : {date_iso!r}.")
    for s in seances_du_jour(conn, store, annee, jour, classe_id):
        if s["creneau"] == creneau:
            return s
    raise SeanceErreur(f"Pas de séance de cette classe le {date_iso} en {creneau}.",
                       "introuvable")


def lire(conn, store, annee: str, classe_id: str, date_iso: str, creneau: str,
         maintenant: datetime) -> dict:
    """Tout ce qu'il faut pour le début de séance."""
    from services import planification_hebdo as ph
    s = _seance(conn, store, annee, classe_id, date_iso, creneau)
    s["statut"] = statut(s, maintenant)
    detail = ph.detail_seance(conn, store, annee, classe_id, date_iso, creneau)
    lundi = _lundi(date.fromisoformat(date_iso)).isoformat()
    eleves = pc_svc.eleves_de_la_semaine(conn, classe_id, lundi)
    plan = None
    salle_id = _salle_de_la_case(conn, s.get("edt_creneau_id"))
    if salle_id:
        p = pc_svc.lire(conn, classe_id, salle_id, lundi, maintenant.date())
        if p["places"] and p["placements"]:
            plan = {"salle": p["salle"], "places": p["places"],
                    "placements": p["placements"], "reservations": p["reservations"],
                    "source": p["source"]}
    return {
        "seance": s,
        "mise_en_route": {
            "type": detail.get("mer_type"),
            "enveloppes": detail.get("mer_enveloppes") or [],
            "rang": detail.get("mer_rang") or 0,
        },
        "eleves": eleves,
        "plan": plan,
        "absents": absents(conn, classe_id, date_iso, creneau),
        "seances_du_jour": seances_du_jour(conn, store, annee,
                                           date.fromisoformat(date_iso), classe_id),
    }


def definir_absence(conn, store, annee: str, classe_id: str, eleve_id: str,
                    date_iso: str, creneau: str, absent: bool) -> list[str]:
    """Marque (ou retire) l'absence d'un élève pour la séance ; renvoie la
    liste des absents de la séance."""
    _seance(conn, store, annee, classe_id, date_iso, creneau)
    lundi = _lundi(date.fromisoformat(date_iso)).isoformat()
    if eleve_id not in {e["id"] for e in pc_svc.eleves_de_la_semaine(conn, classe_id, lundi)}:
        raise SeanceErreur("Élève absent de la classe cette semaine-là.")
    if absent:
        conn.execute("INSERT OR IGNORE INTO absences (classe_id, eleve_id, date, "
                     "creneau_code) VALUES (?,?,?,?)",
                     (classe_id, eleve_id, date_iso, creneau))
    else:
        conn.execute("DELETE FROM absences WHERE classe_id=? AND eleve_id=? AND "
                     "date=? AND creneau_code=?",
                     (classe_id, eleve_id, date_iso, creneau))
    return absents(conn, classe_id, date_iso, creneau)
