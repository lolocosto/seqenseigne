"""services/indisponibilites.py — v0.21.0

Indisponibilités : périodes où des séances prévues à l'EDT n'ont pas lieu
(surveillance d'examen, sortie, journée de cohésion…). Elles retirent des
séances du planning projeté, ce qui décale mécaniquement la suite.

Deux granularités (type) :
  - 'seances'  : une plage de créneaux dans UNE journée (ex. M2 → S3 le 08/09).
  - 'journees' : une plage de journées entières (ex. du 09/09 au 11/09).

Deux portées (portee) :
  - 'moi'     : l'enseignant est indisponible → toutes ses séances du moment
                sautent (toutes classes).
  - 'classes' : seules les séances des classes listées (classes_ids) sautent.

La fonction `concerne_seance` / `filtrer_seances` est pure (testable sans base).

Table `indisponibilites(id, annee, etablissement_id, type, date_debut,
date_fin, creneau_debut, creneau_fin, portee, classes_ids, motif)`.
"""

from __future__ import annotations
import json
import uuid

TYPES = ("seances", "journees")
PORTEES = ("moi", "classes")


class IndispoErreur(Exception):
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class DonneesInvalides(IndispoErreur):
    def __init__(self, message):
        super().__init__(message, "donnees_invalides")


class Introuvable(IndispoErreur):
    def __init__(self, iid):
        super().__init__(f"Indisponibilité {iid!r} introuvable.",
                         "introuvable", id=iid)


def _rowid() -> str:
    return "ind_" + uuid.uuid4().hex[:12]


# ── Fonction pure : une indispo concerne-t-elle une séance ? ──────────────────

def concerne_seance(indispo: dict, seance: dict, classe_id: str | None,
                    ordre_creneau: dict) -> bool:
    """Vrai si `indispo` retire `seance` (pour la classe `classe_id`).

    seance        : dict projeté {date, creneau_code, ...}.
    classe_id     : la classe dont on projette le planning.
    ordre_creneau : {code: ordre} pour situer un créneau dans la journée.
    """
    # Portée : 'moi' concerne toutes les classes ; 'classes' seulement les
    # classes listées.
    if indispo.get("portee") == "classes":
        ids = indispo.get("classes_ids") or []
        if classe_id not in ids:
            return False

    d = seance.get("date", "")
    deb = indispo.get("date_debut") or ""
    fin = indispo.get("date_fin") or deb

    if indispo.get("type") == "journees":
        # Toute séance dont la date est dans [date_debut, date_fin].
        return bool(deb) and deb <= d <= fin

    # type 'seances' : même journée (date_debut), créneau dans la plage.
    if d != deb:
        return False
    o = ordre_creneau.get(seance.get("creneau_code"))
    o_deb = ordre_creneau.get(indispo.get("creneau_debut"))
    o_fin = ordre_creneau.get(indispo.get("creneau_fin"))
    if o is None or o_deb is None or o_fin is None:
        return False
    lo, hi = min(o_deb, o_fin), max(o_deb, o_fin)
    return lo <= o <= hi


def filtrer_seances(seances: list, indispos: list, classe_id: str | None,
                    grille: list) -> list:
    """Retire des `seances` celles couvertes par une indisponibilité.

    Ne renumérote pas ici : l'appelant (projeter) filtre AVANT de numéroter,
    pour que le décalage soit intrinsèque.
    """
    if not indispos:
        return list(seances)
    ordre_creneau = {g["code"]: g.get("ordre", 0) for g in grille}
    out = []
    for s in seances:
        if any(concerne_seance(ind, s, classe_id, ordre_creneau)
               for ind in indispos):
            continue
        out.append(s)
    return out


# ── Persistance ──────────────────────────────────────────────────────────────

def semaines_touchees(indispo: dict) -> int:
    """Nombre de semaines civiles (lundi→dimanche) touchées par une
    indisponibilité — sert de valeur par défaut d'un décalage. Règle métier
    (calendrier), calculée côté serveur.
    """
    from datetime import date, timedelta
    deb = indispo.get("date_debut") or ""
    fin = indispo.get("date_fin") or deb
    if not deb:
        return 1
    try:
        d1 = date.fromisoformat(deb)
        d2 = date.fromisoformat(fin)
    except ValueError:
        return 1
    l1 = d1 - timedelta(days=d1.weekday())   # lundi de la semaine de début
    l2 = d2 - timedelta(days=d2.weekday())   # lundi de la semaine de fin
    n = round((l2 - l1).days / 7) + 1
    return max(1, n)


def _row_to_dict(r) -> dict:
    d = dict(r)
    try:
        d["classes_ids"] = json.loads(d.get("classes_ids") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["classes_ids"] = []
    d["semaines_touchees"] = semaines_touchees(d)
    return d


def lister(conn, annee: str, etablissement_id: str | None = None) -> list:
    params = [annee]
    where = "annee = ?"
    if etablissement_id:
        where += " AND etablissement_id = ?"
        params.append(etablissement_id)
    rows = conn.execute(
        f"SELECT * FROM indisponibilites WHERE {where} "
        f"ORDER BY date_debut, creneau_debut", params).fetchall()
    return [_row_to_dict(r) for r in rows]


def _valider(type_, portee, date_debut, date_fin, creneau_debut, creneau_fin,
             classes_ids):
    if type_ not in TYPES:
        raise DonneesInvalides(f"Type invalide : {type_!r} (attendu {TYPES}).")
    if portee not in PORTEES:
        raise DonneesInvalides(
            f"Portée invalide : {portee!r} (attendu {PORTEES}).")
    if not (date_debut or "").strip():
        raise DonneesInvalides("La date de début est obligatoire.")
    if type_ == "seances":
        if not (creneau_debut or "").strip() or not (creneau_fin or "").strip():
            raise DonneesInvalides(
                "Les créneaux de début et de fin sont obligatoires pour une "
                "indisponibilité de type « séances ».")
    if type_ == "journees":
        df = (date_fin or date_debut)
        if df < date_debut:
            raise DonneesInvalides(
                "La date de fin doit être postérieure ou égale au début.")
    if portee == "classes" and not classes_ids:
        raise DonneesInvalides(
            "Sélectionnez au moins une classe pour la portée « classes ».")


def creer(conn, annee: str, etablissement_id: str, *, type: str,
          date_debut: str, date_fin: str = "", creneau_debut: str = "",
          creneau_fin: str = "", portee: str = "moi",
          classes_ids: list | None = None, motif: str = "") -> dict:
    classes_ids = classes_ids or []
    _valider(type, portee, date_debut, date_fin, creneau_debut, creneau_fin,
             classes_ids)
    if type == "seances":
        date_fin = date_debut  # une seule journée
    elif not date_fin:
        date_fin = date_debut
    new_id = _rowid()
    conn.execute(
        "INSERT INTO indisponibilites "
        "(id, annee, etablissement_id, type, date_debut, date_fin, "
        " creneau_debut, creneau_fin, portee, classes_ids, motif) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (new_id, annee, etablissement_id, type, date_debut, date_fin,
         creneau_debut, creneau_fin, portee, json.dumps(classes_ids),
         (motif or "").strip()))
    return _row_to_dict(conn.execute(
        "SELECT * FROM indisponibilites WHERE id=?", (new_id,)).fetchone())


def modifier(conn, iid: str, champs: dict) -> dict:
    row = conn.execute("SELECT * FROM indisponibilites WHERE id=?",
                       (iid,)).fetchone()
    if row is None:
        raise Introuvable(iid)
    c = _row_to_dict(row)
    for k in ("type", "date_debut", "date_fin", "creneau_debut", "creneau_fin",
              "portee", "motif"):
        if k in champs:
            c[k] = champs[k]
    if "classes_ids" in champs:
        c["classes_ids"] = champs["classes_ids"] or []
    _valider(c["type"], c["portee"], c["date_debut"], c["date_fin"],
             c["creneau_debut"], c["creneau_fin"], c["classes_ids"])
    if c["type"] == "seances":
        c["date_fin"] = c["date_debut"]
    elif not c["date_fin"]:
        c["date_fin"] = c["date_debut"]
    conn.execute(
        "UPDATE indisponibilites SET type=?, date_debut=?, date_fin=?, "
        "creneau_debut=?, creneau_fin=?, portee=?, classes_ids=?, motif=? "
        "WHERE id=?",
        (c["type"], c["date_debut"], c["date_fin"], c["creneau_debut"],
         c["creneau_fin"], c["portee"], json.dumps(c["classes_ids"]),
         (c["motif"] or "").strip(), iid))
    return c


def supprimer(conn, iid: str) -> None:
    row = conn.execute("SELECT 1 FROM indisponibilites WHERE id=?",
                       (iid,)).fetchone()
    if row is None:
        raise Introuvable(iid)
    conn.execute("DELETE FROM indisponibilites WHERE id=?", (iid,))
