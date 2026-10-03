"""services/observables.py — v0.45.0

Observables de séance (Paramétrage › Observables) : comportements à
« Valoriser » ou à « Sanctionner », **par niveau** (SEGPA = niveau séparé).

Modèle (validé) :
  - `observables(id, niveau, section, libelle, ordre, actif, portee, du, au)` :
    section ∈ {valoriser, sanctionner} ; portee ∈ {commun, individuel} ;
    période facultative [du, au] (dates ISO incluses, '' = sans borne) ;
    désactivé plutôt que supprimé (l'historique d'observation y renverra) ;
    renommable même après usage.
  - `observable_exceptions(id, observable_id, eleve_id, type, du, au,
    commentaire)` : type = « masquer » pour un observable commun (ne pas
    l'utiliser pour cet élève, ex. aménagement), « attribuer » pour un
    observable individuel (seuls les élèves désignés l'ont, ex. fiche de
    suivi temporaire) ; période et commentaire facultatifs.

Liste effective d'un élève à une date : observables communs actifs et en
période, moins ceux qui lui sont masqués (en période), plus les observables
individuels actifs et en période qui lui sont attribués (en période).
"""

from __future__ import annotations
import uuid
from datetime import date

SECTIONS = ("valoriser", "sanctionner")
PORTEES = ("commun", "individuel")

SCHEMA = """
CREATE TABLE IF NOT EXISTS observables (
    id       TEXT    PRIMARY KEY,
    niveau   TEXT    NOT NULL,
    section  TEXT    NOT NULL,
    libelle  TEXT    NOT NULL,
    ordre    INTEGER NOT NULL DEFAULT 0,
    actif    INTEGER NOT NULL DEFAULT 1,
    portee   TEXT    NOT NULL DEFAULT 'commun',
    du       TEXT    NOT NULL DEFAULT '',
    au       TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_observables_niveau ON observables (niveau, section, ordre);
CREATE TABLE IF NOT EXISTS observable_exceptions (
    id            TEXT PRIMARY KEY,
    observable_id TEXT NOT NULL REFERENCES observables(id) ON DELETE CASCADE,
    eleve_id      TEXT NOT NULL,
    type          TEXT NOT NULL,
    du            TEXT NOT NULL DEFAULT '',
    au            TEXT NOT NULL DEFAULT '',
    commentaire   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_obs_exc_obs ON observable_exceptions (observable_id);
CREATE INDEX IF NOT EXISTS idx_obs_exc_eleve ON observable_exceptions (eleve_id);
"""


class ObservableErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides"):
        super().__init__(message)
        self.code = code


def _id(p: str) -> str:
    return p + uuid.uuid4().hex[:12]


def _periode(du, au) -> tuple[str, str]:
    sortie = []
    for v in (du, au):
        v = (v or "").strip()
        if v:
            try:
                v = date.fromisoformat(v).isoformat()
            except ValueError:
                raise ObservableErreur(f"Date invalide : {v!r} (AAAA-MM-JJ).")
        sortie.append(v)
    if sortie[0] and sortie[1] and sortie[0] > sortie[1]:
        raise ObservableErreur("La date de début est après la date de fin.")
    return sortie[0], sortie[1]


def en_periode(du: str, au: str, jour: str) -> bool:
    return (not du or du <= jour) and (not au or jour <= au)


# ── Observables ──────────────────────────────────────────────────────────────

def _lire(conn, obs_id: str) -> dict:
    r = conn.execute("SELECT * FROM observables WHERE id=?", (obs_id,)).fetchone()
    if r is None:
        raise ObservableErreur("Observable introuvable.", "introuvable")
    return dict(r)


def lister(conn, niveau: str) -> list[dict]:
    rows = conn.execute(
        "SELECT o.*, (SELECT COUNT(*) FROM observable_exceptions e "
        "WHERE e.observable_id=o.id) AS nb_exceptions FROM observables o "
        "WHERE o.niveau=? ORDER BY o.section, o.actif DESC, o.ordre, o.libelle",
        (niveau,)).fetchall()
    return [{**dict(r), "actif": bool(r["actif"])} for r in rows]


def creer(conn, niveau: str, section: str, libelle: str) -> dict:
    niveau = (niveau or "").strip()
    libelle = (libelle or "").strip()
    if not niveau:
        raise ObservableErreur("Niveau obligatoire.")
    if section not in SECTIONS:
        raise ObservableErreur(f"Section invalide : {section!r}.")
    if not libelle:
        raise ObservableErreur("Le libellé est obligatoire.")
    n = conn.execute("SELECT COALESCE(MAX(ordre), 0) FROM observables WHERE "
                     "niveau=? AND section=?", (niveau, section)).fetchone()[0]
    oid = _id("ob_")
    conn.execute("INSERT INTO observables (id, niveau, section, libelle, ordre) "
                 "VALUES (?,?,?,?,?)", (oid, niveau, section, libelle, n + 10))
    return _lire(conn, oid)


def modifier(conn, obs_id: str, champs: dict) -> dict:
    o = _lire(conn, obs_id)
    if "libelle" in champs:
        lib = (champs["libelle"] or "").strip()
        if not lib:
            raise ObservableErreur("Le libellé est obligatoire.")
        o["libelle"] = lib
    if "portee" in champs and champs["portee"] != o["portee"]:
        if champs["portee"] not in PORTEES:
            raise ObservableErreur(f"Portée invalide : {champs['portee']!r}.")
        n = conn.execute("SELECT COUNT(*) FROM observable_exceptions WHERE "
                         "observable_id=?", (obs_id,)).fetchone()[0]
        if n:
            raise ObservableErreur(
                "Retirer d'abord les élèves concernés : « masqué pour » et "
                "« attribué à » n'ont pas le même sens.")
        o["portee"] = champs["portee"]
    if "du" in champs or "au" in champs:
        o["du"], o["au"] = _periode(champs.get("du", o["du"]), champs.get("au", o["au"]))
    if "actif" in champs:
        o["actif"] = 1 if champs["actif"] else 0
    conn.execute("UPDATE observables SET libelle=?, portee=?, du=?, au=?, actif=? "
                 "WHERE id=?", (o["libelle"], o["portee"], o["du"], o["au"],
                                o["actif"], obs_id))
    return _lire(conn, obs_id)


def deplacer(conn, obs_id: str, sens: int) -> None:
    """Échange l'ordre avec le voisin (actifs de la même section)."""
    o = _lire(conn, obs_id)
    voisins = [dict(r) for r in conn.execute(
        "SELECT id, ordre FROM observables WHERE niveau=? AND section=? AND actif=1 "
        "ORDER BY ordre, libelle", (o["niveau"], o["section"])).fetchall()]
    ids = [v["id"] for v in voisins]
    if obs_id not in ids:
        return
    i = ids.index(obs_id)
    j = i + (1 if sens > 0 else -1)
    if not 0 <= j < len(ids):
        return
    ids[i], ids[j] = ids[j], ids[i]
    for k, oid in enumerate(ids):
        conn.execute("UPDATE observables SET ordre=? WHERE id=?", ((k + 1) * 10, oid))


def copier_depuis(conn, niveau_source: str, niveau_cible: str) -> int:
    """Copie les observables COMMUNS actifs d'un niveau vers un autre (sans
    exceptions, propres aux élèves) ; un libellé déjà présent dans la même
    section n'est pas dupliqué. Retourne le nombre d'observables créés."""
    if niveau_source == niveau_cible:
        raise ObservableErreur("Choisir un autre niveau à copier.")
    existants = {(r["section"], r["libelle"].casefold()) for r in conn.execute(
        "SELECT section, libelle FROM observables WHERE niveau=?", (niveau_cible,))}
    n = 0
    for r in conn.execute(
            "SELECT * FROM observables WHERE niveau=? AND actif=1 AND portee='commun' "
            "ORDER BY section, ordre", (niveau_source,)).fetchall():
        if (r["section"], r["libelle"].casefold()) in existants:
            continue
        o = creer(conn, niveau_cible, r["section"], r["libelle"])
        if r["du"] or r["au"]:
            modifier(conn, o["id"], {"du": r["du"], "au": r["au"]})
        n += 1
    return n


# ── Exceptions par élève ─────────────────────────────────────────────────────

def eleves_du_niveau(conn, niveau: str, annee: str) -> list[dict]:
    """Élèves (encore dans leur classe) des classes du niveau pour l'année."""
    rows = conn.execute(
        "SELECT DISTINCT e.id, e.nom, e.prenom, c.nom AS classe FROM eleves e "
        "JOIN eleves_classes ec ON ec.eleve_id=e.id "
        "JOIN classes c ON c.id=ec.classe_id "
        "WHERE c.niveau=? AND c.annee=? AND (ec.date_sortie IS NULL OR ec.date_sortie='') "
        "ORDER BY e.nom COLLATE NOCASE, e.prenom COLLATE NOCASE",
        (niveau, annee)).fetchall()
    return [dict(r) for r in rows]


def lister_exceptions(conn, obs_id: str) -> list[dict]:
    _lire(conn, obs_id)
    return [dict(r) for r in conn.execute(
        "SELECT x.*, e.nom, e.prenom FROM observable_exceptions x "
        "LEFT JOIN eleves e ON e.id=x.eleve_id WHERE x.observable_id=? "
        "ORDER BY e.nom COLLATE NOCASE, e.prenom COLLATE NOCASE, x.du",
        (obs_id,)).fetchall()]


def ajouter_exception(conn, obs_id: str, eleve_id: str, du: str = "", au: str = "",
                      commentaire: str = "") -> dict:
    o = _lire(conn, obs_id)
    if conn.execute("SELECT 1 FROM eleves WHERE id=?", (eleve_id,)).fetchone() is None:
        raise ObservableErreur("Élève introuvable.")
    du, au = _periode(du, au)
    typ = "masquer" if o["portee"] == "commun" else "attribuer"
    xid = _id("ox_")
    conn.execute("INSERT INTO observable_exceptions (id, observable_id, eleve_id, type, "
                 "du, au, commentaire) VALUES (?,?,?,?,?,?,?)",
                 (xid, obs_id, eleve_id, typ, du, au, (commentaire or "").strip()))
    return dict(conn.execute("SELECT * FROM observable_exceptions WHERE id=?",
                             (xid,)).fetchone())


def modifier_exception(conn, exc_id: str, champs: dict) -> dict:
    r = conn.execute("SELECT * FROM observable_exceptions WHERE id=?", (exc_id,)).fetchone()
    if r is None:
        raise ObservableErreur("Exception introuvable.", "introuvable")
    x = dict(r)
    if "du" in champs or "au" in champs:
        x["du"], x["au"] = _periode(champs.get("du", x["du"]), champs.get("au", x["au"]))
    if "commentaire" in champs:
        x["commentaire"] = (champs["commentaire"] or "").strip()
    conn.execute("UPDATE observable_exceptions SET du=?, au=?, commentaire=? WHERE id=?",
                 (x["du"], x["au"], x["commentaire"], exc_id))
    return x


def supprimer_exception(conn, exc_id: str) -> None:
    conn.execute("DELETE FROM observable_exceptions WHERE id=?", (exc_id,))


def eleves_avec_exceptions(conn, niveau: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT DISTINCT e.id, e.nom, e.prenom FROM observable_exceptions x "
        "JOIN observables o ON o.id=x.observable_id JOIN eleves e ON e.id=x.eleve_id "
        "WHERE o.niveau=? ORDER BY e.nom COLLATE NOCASE, e.prenom COLLATE NOCASE",
        (niveau,)).fetchall()]


# ── Liste effective ──────────────────────────────────────────────────────────

def liste_effective(conn, niveau: str, eleve_id: str, jour: str) -> dict:
    """{valoriser: [...], sanctionner: [...]} pour l'élève ce jour-là."""
    excs = {}
    for r in conn.execute(
            "SELECT x.* FROM observable_exceptions x JOIN observables o "
            "ON o.id=x.observable_id WHERE o.niveau=? AND x.eleve_id=?",
            (niveau, eleve_id)).fetchall():
        if en_periode(r["du"], r["au"], jour):
            excs.setdefault(r["observable_id"], []).append(dict(r))
    sortie = {"valoriser": [], "sanctionner": []}
    for o in conn.execute("SELECT * FROM observables WHERE niveau=? AND actif=1 "
                          "ORDER BY ordre, libelle", (niveau,)).fetchall():
        if not en_periode(o["du"], o["au"], jour):
            continue
        mes = excs.get(o["id"], [])
        if o["portee"] == "commun":
            if any(x["type"] == "masquer" for x in mes):
                continue
        elif not any(x["type"] == "attribuer" for x in mes):
            continue
        sortie[o["section"]].append({"id": o["id"], "libelle": o["libelle"],
                                     "portee": o["portee"]})
    return sortie
