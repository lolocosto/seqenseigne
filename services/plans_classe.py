"""services/plans_classe.py — v0.39.0

Plans de classe hebdomadaires : quel élève occupe quelle place d'une salle,
pour une classe et une semaine (cf. doc/cadrage_plans_de_classe.md).

Modèle :
  - `plans_classe(id, classe_id, salle_id, lundi)` : un plan par (classe,
    salle, semaine), créé seulement à la première modification de la semaine ;
  - `plan_placements(plan_id, eleve_id, numero, statut, confirme)` : l'élève
    `eleve_id` est à la place `numero` (numérotation stable de la salle) ;
    `statut` ∈ {'libre', 'impose'} ; `confirme` = 0 pour un placement libre
    repris d'une semaine précédente et pas encore confirmé.

Règles (validées) :
  - semaines passées : consultables, non modifiables ; semaine en cours :
    corrigeable ; semaines futures : préparables ;
  - une semaine sans plan affiche le plan RECONDUIT de la dernière semaine
    saisie pour la même classe ET la même salle : imposés repris tels quels,
    libres repris « à confirmer » ; rien n'est écrit tant qu'on ne modifie pas ;
  - un élève sorti de la classe disparaît du plan, un élève arrivé est « non
    placé » ; un élève dont le numéro de place n'existe plus dans la version de
    la salle de la semaine redevient « non placé » (avertissement) ;
  - places vides et élèves non placés sont autorisés ;
  - un élève placé est « libre » par défaut ; l'aléatoire place en « imposé »
    (c'est l'enseignant qui décide) et ne touche pas aux imposés existants ;
  - seuls les cours en classe entière ouvrent un plan (salles proposées =
    salles des cases comptées de la classe cette semaine-là).
"""

from __future__ import annotations
import random
import unicodedata
import uuid
from datetime import date, timedelta

from services import edt as edt_svc
from services import salles as salles_svc

STATUTS = ("libre", "impose")

SCHEMA = """
CREATE TABLE IF NOT EXISTS plans_classe (
    id        TEXT PRIMARY KEY,
    classe_id TEXT NOT NULL,
    salle_id  TEXT NOT NULL,
    lundi     TEXT NOT NULL,
    UNIQUE (classe_id, salle_id, lundi)
);
CREATE TABLE IF NOT EXISTS plan_placements (
    plan_id  TEXT    NOT NULL REFERENCES plans_classe(id) ON DELETE CASCADE,
    eleve_id TEXT    NOT NULL,
    numero   INTEGER NOT NULL,
    statut   TEXT    NOT NULL DEFAULT 'libre',
    confirme INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (plan_id, eleve_id),
    UNIQUE (plan_id, numero)
);
"""


class PlanErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides"):
        super().__init__(message)
        self.code = code


class SemaineFigee(PlanErreur):
    def __init__(self, message):
        super().__init__(message, "semaine_figee")


# ── Dates ────────────────────────────────────────────────────────────────────

def lundi_iso(valeur) -> str:
    if isinstance(valeur, date):
        d = valeur
    else:
        try:
            d = date.fromisoformat(str(valeur or "").strip())
        except ValueError:
            raise PlanErreur(f"Date invalide : {valeur!r}.")
    return (d - timedelta(days=d.weekday())).isoformat()


def statut_semaine(lundi: str, aujourd_hui: date) -> str:
    cour = lundi_iso(aujourd_hui)
    return "passee" if lundi < cour else ("en_cours" if lundi == cour else "future")


# ── Données de la classe ─────────────────────────────────────────────────────

def _classe(conn, classe_id: str) -> dict:
    r = conn.execute("SELECT id, nom, annee, etablissement_id FROM classes "
                     "WHERE id=?", (classe_id,)).fetchone()
    if r is None:
        raise PlanErreur(f"Classe {classe_id!r} introuvable.", "introuvable")
    return dict(r)


def eleves_de_la_semaine(conn, classe_id: str, lundi: str) -> list[dict]:
    """Élèves présents dans la classe au moins un jour de la semaine :
    entrés au plus tard le dimanche, pas sortis avant le lundi."""
    dimanche = (date.fromisoformat(lundi) + timedelta(days=6)).isoformat()
    rows = conn.execute(
        "SELECT e.id, e.nom, e.prenom FROM eleves e "
        "JOIN eleves_classes ec ON ec.eleve_id = e.id "
        "WHERE ec.classe_id = ? "
        "AND (ec.date_entree IS NULL OR ec.date_entree = '' OR ec.date_entree <= ?) "
        "AND (ec.date_sortie IS NULL OR ec.date_sortie = '' OR ec.date_sortie > ?) "
        "ORDER BY e.nom COLLATE NOCASE, e.prenom COLLATE NOCASE",
        (classe_id, dimanche, lundi)).fetchall()
    eleves = [dict(r) for r in rows]
    for e, lib in zip(eleves, etiquettes(eleves)):
        e["etiquette"] = lib
    return eleves


def _sans_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn")


def etiquettes(eleves: list[dict]) -> list[str]:
    """« Prénom N. », avec plus de lettres du nom tant que deux élèves de même
    prénom restent indiscernables (au pire le nom entier)."""
    def prenom(e):
        return (e.get("prenom") or "").strip()

    def nom(e):
        return (e.get("nom") or "").strip()
    sortie = []
    for e in eleves:
        homonymes = [x for x in eleves if x is not e and
                     _sans_accents(prenom(x)).lower() == _sans_accents(prenom(e)).lower()]
        n = 1
        while n < len(nom(e)) and any(
                _sans_accents(nom(x))[:n].lower() == _sans_accents(nom(e))[:n].lower()
                for x in homonymes):
            n += 1
        debut = nom(e)[:n].capitalize() if nom(e) else ""
        if not debut:
            sortie.append(prenom(e))
        elif n >= len(nom(e)):
            sortie.append(f"{prenom(e)} {nom(e).capitalize()}")
        else:
            sortie.append(f"{prenom(e)} {debut}.")
    return sortie


def salles_de_la_semaine(conn, classe_id: str, lundi: str) -> list[dict]:
    """Salles des cours en classe entière de la classe cette semaine-là."""
    cl = _classe(conn, classe_id)
    cases = edt_svc.lister(conn, cl["annee"], classe_id=classe_id,
                           a_la_date=date.fromisoformat(lundi))
    vues, sortie = set(), []
    for c in cases:
        if edt_svc.est_compte(c) and c.get("salle_id") and c["salle_id"] not in vues:
            vues.add(c["salle_id"])
            sortie.append({"id": c["salle_id"], "nom": c.get("salle_nom") or "?"})
    return sorted(sortie, key=lambda s: s["nom"])


# ── Lecture ──────────────────────────────────────────────────────────────────

def _places_salle(conn, salle_id: str, lundi: str, aujourd_hui: date) -> list[dict]:
    plan = salles_svc.lire_plan(conn, salle_id, aujourd_hui,
                                d=date.fromisoformat(lundi))
    return plan["places"]


def _plan_saisi(conn, classe_id, salle_id, lundi):
    r = conn.execute("SELECT id FROM plans_classe WHERE classe_id=? AND "
                     "salle_id=? AND lundi=?", (classe_id, salle_id, lundi)).fetchone()
    return r["id"] if r else None


def _dernier_plan_avant(conn, classe_id, salle_id, lundi):
    r = conn.execute("SELECT id, lundi FROM plans_classe WHERE classe_id=? AND "
                     "salle_id=? AND lundi < ? ORDER BY lundi DESC LIMIT 1",
                     (classe_id, salle_id, lundi)).fetchone()
    return (r["id"], r["lundi"]) if r else (None, None)


def _placements(conn, plan_id) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT eleve_id, numero, statut, confirme FROM plan_placements "
        "WHERE plan_id=? ORDER BY numero", (plan_id,)).fetchall()]


def lire(conn, classe_id: str, salle_id: str, lundi, aujourd_hui: date) -> dict:
    """Plan de la classe dans la salle pour la semaine du `lundi` : saisi,
    reconduit (dernière semaine saisie, libres à confirmer) ou vide."""
    lundi = lundi_iso(lundi)
    cl = _classe(conn, classe_id)
    salle = salles_svc.lire(conn, salle_id, aujourd_hui)
    places = _places_salle(conn, salle_id, lundi, aujourd_hui)
    eleves = eleves_de_la_semaine(conn, classe_id, lundi)
    ids_eleves = {e["id"] for e in eleves}
    numeros = {p["numero"] for p in places}

    pid = _plan_saisi(conn, classe_id, salle_id, lundi)
    source, reconduit_de = "saisi", None
    if pid:
        brut = _placements(conn, pid)
    else:
        prec, reconduit_de = _dernier_plan_avant(conn, classe_id, salle_id, lundi)
        if prec:
            source = "reconduit"
            brut = [{**p, "confirme": 1 if p["statut"] == "impose" else 0}
                    for p in _placements(conn, prec)]
        else:
            source, brut = "vide", []

    avertissements, placements = [], []
    noms = {e["id"]: e["etiquette"] for e in eleves}
    for p in brut:
        if p["eleve_id"] not in ids_eleves:
            continue                      # élève sorti : disparaît sans bruit
        if p["numero"] not in numeros:
            avertissements.append(
                f"{noms[p['eleve_id']]} : la place {p['numero']} n'existe plus "
                f"dans cette version de la salle, à replacer.")
            continue
        placements.append(p)
    places_ids = {p["eleve_id"] for p in placements}
    st = statut_semaine(lundi, aujourd_hui)
    return {
        "classe": {"id": cl["id"], "nom": cl["nom"]},
        "salle": {"id": salle["id"], "nom": salle["nom"]},
        "lundi": lundi,
        "statut_semaine": st,
        "modifiable": st != "passee",
        "source": source,
        "reconduit_de": reconduit_de,
        "places": places,
        "eleves": eleves,
        "placements": placements,
        "non_places": [e["id"] for e in eleves if e["id"] not in places_ids],
        "avertissements": avertissements,
    }


# ── Écriture ─────────────────────────────────────────────────────────────────

def enregistrer(conn, classe_id: str, salle_id: str, lundi, placements,
                aujourd_hui: date) -> dict:
    """Remplace le plan de la semaine par `placements`
    ([{eleve_id, numero, statut, confirme}]). Crée le plan de la semaine s'il
    n'existait pas (fin de la reconduction implicite)."""
    lundi = lundi_iso(lundi)
    if statut_semaine(lundi, aujourd_hui) == "passee":
        raise SemaineFigee("Semaine passée : le plan de classe ne se modifie plus.")
    _classe(conn, classe_id)
    places = _places_salle(conn, salle_id, lundi, aujourd_hui)
    numeros = {p["numero"] for p in places}
    ids_eleves = {e["id"] for e in eleves_de_la_semaine(conn, classe_id, lundi)}
    if not isinstance(placements, list):
        raise PlanErreur("`placements` doit être une liste.")
    vus_e, vus_n, propres = set(), set(), []
    for p in placements:
        eid = (p or {}).get("eleve_id")
        try:
            num = int((p or {}).get("numero"))
        except (TypeError, ValueError):
            raise PlanErreur(f"Numéro de place invalide : {p!r}.")
        statut = (p or {}).get("statut") or "libre"
        if eid not in ids_eleves:
            raise PlanErreur(f"Élève {eid!r} absent de la classe cette semaine.")
        if num not in numeros:
            raise PlanErreur(f"La place {num} n'existe pas dans la salle.")
        if statut not in STATUTS:
            raise PlanErreur(f"Statut invalide : {statut!r}.")
        if eid in vus_e:
            raise PlanErreur("Un élève est placé deux fois.")
        if num in vus_n:
            raise PlanErreur(f"La place {num} est attribuée deux fois.")
        vus_e.add(eid)
        vus_n.add(num)
        confirme = 1 if statut == "impose" else (0 if p.get("confirme") in (0, False) else 1)
        propres.append((eid, num, statut, confirme))
    pid = _plan_saisi(conn, classe_id, salle_id, lundi)
    if pid is None:
        pid = "pc_" + uuid.uuid4().hex[:12]
        conn.execute("INSERT INTO plans_classe (id, classe_id, salle_id, lundi) "
                     "VALUES (?,?,?,?)", (pid, classe_id, salle_id, lundi))
    conn.execute("DELETE FROM plan_placements WHERE plan_id=?", (pid,))
    conn.executemany(
        "INSERT INTO plan_placements (plan_id, eleve_id, numero, statut, confirme) "
        "VALUES (?,?,?,?,?)", [(pid, *t) for t in propres])
    return lire(conn, classe_id, salle_id, lundi, aujourd_hui)


def reinitialiser(conn, classe_id: str, salle_id: str, lundi,
                  aujourd_hui: date) -> dict:
    """Supprime le plan saisi de la semaine (retour à la reconduction)."""
    lundi = lundi_iso(lundi)
    if statut_semaine(lundi, aujourd_hui) == "passee":
        raise SemaineFigee("Semaine passée : le plan de classe ne se modifie plus.")
    pid = _plan_saisi(conn, classe_id, salle_id, lundi)
    if pid:
        conn.execute("DELETE FROM plan_placements WHERE plan_id=?", (pid,))
        conn.execute("DELETE FROM plans_classe WHERE id=?", (pid,))
    return lire(conn, classe_id, salle_id, lundi, aujourd_hui)


# ── Aléatoire (fonction pure) ────────────────────────────────────────────────

def aleatoire(placements: list[dict], numeros: list[int], eleves: list[str],
              rng: random.Random | None = None) -> list[dict]:
    """Garde les placements imposés ; répartit tous les autres élèves au hasard
    sur les places restantes, en « imposé » (c'est l'enseignant qui place).
    S'il y a plus d'élèves que de places, les derniers restent non placés."""
    rng = rng or random.Random()
    gardes = [dict(p) for p in placements if p.get("statut") == "impose"]
    pris_e = {p["eleve_id"] for p in gardes}
    pris_n = {p["numero"] for p in gardes}
    libres_n = [n for n in numeros if n not in pris_n]
    a_placer = [e for e in eleves if e not in pris_e]
    rng.shuffle(libres_n)
    rng.shuffle(a_placer)
    for eid, num in zip(a_placer, libres_n):
        gardes.append({"eleve_id": eid, "numero": num, "statut": "impose",
                       "confirme": 1})
    return sorted(gardes, key=lambda p: p["numero"])


# ── Impression : plans d'une salle pour une semaine ──────────────────────────

def plans_de_la_salle(conn, salle_id: str, lundi, aujourd_hui: date) -> list[dict]:
    """Pour l'impression : un plan par classe ayant cours en classe entière
    dans cette salle cette semaine-là (saisi ou reconduit)."""
    lundi = lundi_iso(lundi)
    rows = conn.execute(
        "SELECT DISTINCT e.classe_id FROM edt_creneaux e "
        "JOIN classes c ON c.id = e.classe_id WHERE e.salle_id=?",
        (salle_id,)).fetchall()
    plans = []
    for r in rows:
        cid = r["classe_id"]
        if any(s["id"] == salle_id for s in salles_de_la_semaine(conn, cid, lundi)):
            plans.append(lire(conn, cid, salle_id, lundi, aujourd_hui))
    return sorted(plans, key=lambda p: p["classe"]["nom"])
