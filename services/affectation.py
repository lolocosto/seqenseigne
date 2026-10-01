"""services/affectation.py — v0.19.1.19

Affectation d'une activité de démarrage à chaque séance projetée.

Deux modes par classe/année :
  - 'par_seance'      : affectation case par case de l'EDT (défaut « neutre »,
                        tout à 'aucun' tant que rien n'est saisi). L'UI
                        permettra une multi-sélection de créneaux.
  - 'par_repartition' : un motif cyclique s'applique aux séances dans l'ordre
                        chronologique global.

Valeurs d'affectation :
  - 'automatisme'  : fil Leitner (le calendrier des enveloppes à réviser sera
                     produit en L7).
  - 'progression'  : séquences de mise en route (dates début/fin calées sur le
                     nombre de séances, en L6).
  - 'aucun'        : pas d'activité de démarrage.
  - 'mer:<id>'     : étiquette personnalisée, réf. un preferences_items de type
                     'type_mise_en_route' (le contenu est géré hors logiciel).

Des exceptions (dates) forcent 'aucun' quel que soit le mode.

La fonction `affecter` est pure (testable sans base/réseau).
"""

from __future__ import annotations
import json
import uuid

MODES = ("par_seance", "par_repartition")
RESERVES = ("automatisme", "progression", "aucun")


class AffectationErreur(Exception):
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class DonneesInvalides(AffectationErreur):
    def __init__(self, message):
        super().__init__(message, "donnees_invalides")


def _rowid(prefixe: str) -> str:
    return prefixe + uuid.uuid4().hex[:12]


def affectation_valide(valeur: str) -> bool:
    """Vrai si `valeur` est une affectation acceptée."""
    if valeur in RESERVES:
        return True
    return isinstance(valeur, str) and valeur.startswith("mer:") \
        and len(valeur) > 4


# ── Fonction pure ────────────────────────────────────────────────────────────

def affecter(seances: list, mode: str,
             affectations_par_edt: dict | None = None,
             motif: list | None = None,
             exceptions: set | None = None) -> list:
    """Enrichit chaque séance projetée d'un champ `affectation`.

    seances              : sortie de projection_seances.projeter (chaque dict a
                           edt_creneau_id, date, numero…).
    mode                 : 'par_seance' | 'par_repartition'.
    affectations_par_edt : {edt_creneau_id: affectation} (mode par_seance).
    motif                : liste cyclique d'affectations (mode par_repartition).
    exceptions           : ensemble de dates ISO à forcer à 'aucun'.

    Retour : nouvelle liste de séances (copies) avec `affectation`.
    """
    affectations_par_edt = affectations_par_edt or {}
    exceptions = exceptions or set()
    motif = [m for m in (motif or []) if affectation_valide(m)]

    out = []
    i_motif = 0
    for s in seances:
        s2 = dict(s)
        if s2.get("date") in exceptions:
            s2["affectation"] = "aucun"
        elif mode == "par_repartition":
            if motif:
                s2["affectation"] = motif[i_motif % len(motif)]
                i_motif += 1
            else:
                s2["affectation"] = "aucun"
        else:  # par_seance
            s2["affectation"] = affectations_par_edt.get(
                s2.get("edt_creneau_id"), "aucun")
        out.append(s2)
    return out


def repartir_mer(seances: list, mer_mode: str, affectations: dict,
                 exceptions_dates: set | None = None) -> dict:
    """v0.28.0 — Répartit les séances datées d'une classe par TYPE de MER, selon
    l'affectation de leur créneau EDT et le mode MER de la classe.

    seances      : séances projetées et datées, portant `edt_creneau_id` et
                   `date` (sortie de projection_seances.projeter).
    mer_mode     : mode MER de la classe : 'automatismes' | 'progression' |
                   'panache'. Détermine le DÉFAUT d'un créneau non affecté :
                     - 'automatismes' → 'automatisme' ;
                     - 'progression'  → 'progression' ;
                     - 'panache'      → 'aucun' (à définir créneau par créneau).
    affectations : {edt_creneau_id: 'automatisme'|'progression'} — surcharge par
                   créneau. Un créneau absent prend le défaut du mode ; un
                   créneau à 'aucun' est retiré (pas de MER — neutralisation
                   régulière).
    exceptions_dates : dates ISO neutralisées ponctuellement (aucune MER ce
                   jour-là, quel que soit le type). Neutralisation exceptionnelle.

    Retour : {"automatisme": [séances...], "progression": [séances...]}.
    Les séances non-MER (aucun / exception) ne figurent dans aucune liste.
    """
    exc = exceptions_dates or set()
    defaut = {"automatismes": "automatisme",
              "progression": "progression"}.get(mer_mode, "aucun")
    auto, prog = [], []
    for s in seances:
        if s.get("date") in exc:
            continue  # neutralisation exceptionnelle
        eid = s.get("edt_creneau_id")
        typ = affectations.get(eid, defaut)
        if typ == "automatisme":
            auto.append(s)
        elif typ == "progression":
            prog.append(s)
        # 'aucun' → la séance ne porte pas de MER, ignorée.
    return {"automatisme": auto, "progression": prog}


# ── Persistance : mode ───────────────────────────────────────────────────────

def lire_mode(conn, classe_id: str, annee: str) -> str:
    row = conn.execute(
        "SELECT mode FROM affectation_config WHERE classe_id=? AND annee=?",
        (classe_id, annee)).fetchone()
    return row["mode"] if row else "par_seance"


def definir_mode(conn, classe_id: str, annee: str, mode: str) -> str:
    if mode not in MODES:
        raise DonneesInvalides(f"Mode invalide : {mode!r} (attendu {MODES}).")
    conn.execute(
        "INSERT INTO affectation_config (classe_id, annee, mode) "
        "VALUES (?,?,?) ON CONFLICT(classe_id, annee) "
        "DO UPDATE SET mode=excluded.mode",
        (classe_id, annee, mode))
    return mode


# ── Persistance : affectations par créneau (mode par_seance) ─────────────────

def lire_affectations(conn, classe_id: str, annee: str) -> dict:
    rows = conn.execute(
        "SELECT edt_creneau_id, affectation FROM affectation_seance "
        "WHERE classe_id=? AND annee=?", (classe_id, annee)).fetchall()
    return {r["edt_creneau_id"]: r["affectation"] for r in rows}


def _lire_une(conn, classe_id: str, annee: str, edt_id: str):
    r = conn.execute("SELECT affectation FROM affectation_seance WHERE "
                     "classe_id=? AND annee=? AND edt_creneau_id=?",
                     (classe_id, annee, edt_id)).fetchone()
    return r["affectation"] if r else None


def _ecrire_une(conn, classe_id: str, annee: str, edt_id: str, aff: str) -> None:
    if aff == "aucun":
        conn.execute(
            "DELETE FROM affectation_seance "
            "WHERE classe_id=? AND annee=? AND edt_creneau_id=?",
            (classe_id, annee, edt_id))
    else:
        conn.execute(
            "INSERT INTO affectation_seance "
            "(id, classe_id, annee, edt_creneau_id, affectation) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(classe_id, annee, edt_creneau_id) "
            "DO UPDATE SET affectation=excluded.affectation",
            (_rowid("aff_"), classe_id, annee, edt_id, aff))


def cases_suivantes(conn, classe_id: str, edt_id: str) -> list[str]:
    """v0.41.2 — Cases d'EdT qui prennent la suite de `edt_id` après un
    changement d'EdT programmé : même année, établissement, classe, jour et
    créneau, commençant à la fin (ou après la fin) de la case. Vide si la case
    n'a pas de fin (`valide_au` vide)."""
    c = conn.execute("SELECT * FROM edt_creneaux WHERE id=?", (edt_id,)).fetchone()
    if c is None or not c["valide_au"]:
        return []
    return [r["id"] for r in conn.execute(
        "SELECT id FROM edt_creneaux WHERE annee=? AND etablissement_id=? "
        "AND classe_id=? AND jour=? AND creneau_code=? AND valide_du >= ? "
        "ORDER BY valide_du",
        (c["annee"], c["etablissement_id"], classe_id, c["jour"],
         c["creneau_code"], c["valide_au"])).fetchall()]


def definir_affectations(conn, classe_id: str, annee: str,
                         items: list) -> int:
    """Écrit (upsert) un lot d'affectations. Chaque item :
    {edt_creneau_id, affectation}. Une affectation 'aucun' supprime la ligne
    (retour à l'état neutre). Retourne le nombre d'items traités.

    v0.41.2 — L'affectation se reporte sur les cases futures issues d'un
    changement d'EdT (`cases_suivantes`) qui avaient ENCORE l'ancienne valeur
    de la case modifiée : un choix fait exprès pour une période future n'est
    jamais écrasé."""
    n = 0
    for it in items:
        eid = it.get("edt_creneau_id")
        aff = it.get("affectation", "aucun")
        if not eid:
            continue
        if not affectation_valide(aff):
            raise DonneesInvalides(f"Affectation invalide : {aff!r}.")
        avant = _lire_une(conn, classe_id, annee, eid)
        _ecrire_une(conn, classe_id, annee, eid, aff)
        try:
            suivantes = cases_suivantes(conn, classe_id, eid)
        except Exception:
            suivantes = []          # base sans EdT versionné
        for sid in suivantes:
            if _lire_une(conn, classe_id, annee, sid) == avant:
                _ecrire_une(conn, classe_id, annee, sid, aff)
        n += 1
    return n


# ── Persistance : motif de répartition (mode par_repartition) ────────────────

def lire_motif(conn, classe_id: str, annee: str) -> list:
    row = conn.execute(
        "SELECT motif FROM regle_repartition WHERE classe_id=? AND annee=?",
        (classe_id, annee)).fetchone()
    if not row:
        return []
    try:
        return json.loads(row["motif"])
    except (json.JSONDecodeError, TypeError):
        return []


def definir_motif(conn, classe_id: str, annee: str, motif: list) -> list:
    if not isinstance(motif, list):
        raise DonneesInvalides("Le motif doit être une liste.")
    for m in motif:
        if not affectation_valide(m):
            raise DonneesInvalides(f"Élément de motif invalide : {m!r}.")
    conn.execute(
        "INSERT INTO regle_repartition (classe_id, annee, motif) "
        "VALUES (?,?,?) ON CONFLICT(classe_id, annee) "
        "DO UPDATE SET motif=excluded.motif",
        (classe_id, annee, json.dumps(motif)))
    return motif


# ── Persistance : exceptions ─────────────────────────────────────────────────

def lister_exceptions(conn, classe_id: str, annee: str) -> list:
    rows = conn.execute(
        "SELECT id, date, motif FROM affectation_exception "
        "WHERE classe_id=? AND annee=? ORDER BY date", (classe_id, annee)
    ).fetchall()
    return [dict(r) for r in rows]


def ajouter_exception(conn, classe_id: str, annee: str, date: str,
                      motif: str = "") -> dict:
    date = (date or "").strip()
    if not date:
        raise DonneesInvalides("La date de l'exception est obligatoire.")
    new_id = _rowid("exc_")
    conn.execute(
        "INSERT INTO affectation_exception (id, classe_id, annee, date, motif) "
        "VALUES (?,?,?,?,?) ON CONFLICT(classe_id, annee, date) "
        "DO UPDATE SET motif=excluded.motif",
        (new_id, classe_id, annee, date, (motif or "").strip()))
    return {"id": new_id, "classe_id": classe_id, "annee": annee,
            "date": date, "motif": (motif or "").strip()}


def supprimer_exception(conn, exception_id: str) -> None:
    conn.execute("DELETE FROM affectation_exception WHERE id=?",
                 (exception_id,))


def dates_exceptions(conn, classe_id: str, annee: str) -> set:
    return {r["date"] for r in conn.execute(
        "SELECT date FROM affectation_exception WHERE classe_id=? AND annee=?",
        (classe_id, annee)).fetchall()}
