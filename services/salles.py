"""services/salles.py — v0.37.0

Salles d'un établissement et leurs plans (emplacements des personnes),
versionnés par date d'effet.

Modèle (cf. doc/cadrage_plans_de_classe.md) :
  - `salles(id, etablissement_id, nom, archivee, prochain_numero)` ; nom
    unique par établissement. `archivee` = « non utilisée cette année »
    (réversible). `prochain_numero` = compteur de numérotation des places :
    un numéro de place n'est JAMAIS réattribué, pour que les plans de classe
    (v0.39) restent cohérents d'une version de salle à l'autre.
  - `salle_versions(id, salle_id, date_effet)` : la version initiale a une
    date d'effet vide (« depuis toujours »), les autres un lundi ISO.
  - `salle_places(id, version_id, numero, x, y, angle, ilot)` : un
    emplacement d'une personne, centre (x, y) en cm (repère écran, y vers le
    bas, tableau en haut), angle en degrés (sens horaire, [0, 360)), `ilot`
    identifiant de regroupement ('' = place isolée).

Règles :
  - Salle NON utilisée : son plan s'édite en place (pas de nouvelle version),
    elle peut être supprimée.
  - Salle utilisée (référencée par l'EdT, v0.38) : toute modification se fait
    dans une version datée d'un lundi au plus tôt la semaine prochaine ; les
    versions futures restent modifiables/supprimables, les versions en
    vigueur et passées sont figées ; suppression interdite (archivage
    possible).

`salle_est_utilisee` regarde la colonne `edt_creneaux.salle_id` si elle
existe (ajoutée en v0.38). En v0.37.0 elle n'existe pas : aucune salle n'est
utilisée, toutes restent librement éditables.

Les dates « aujourd'hui » sont injectées (paramètre `aujourd_hui`) pour la
testabilité ; les routes passent `date.today()`.
"""

from __future__ import annotations
import math
import uuid
from datetime import date, timedelta


class SalleErreur(Exception):
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class SalleIntrouvable(SalleErreur):
    def __init__(self, salle_id):
        super().__init__(f"Salle {salle_id!r} introuvable.",
                         "salle_introuvable", salle_id=salle_id)


class VersionIntrouvable(SalleErreur):
    def __init__(self, version_id):
        super().__init__(f"Version de plan {version_id!r} introuvable.",
                         "version_introuvable", version_id=version_id)


class DonneesInvalides(SalleErreur):
    def __init__(self, message):
        super().__init__(message, "donnees_invalides")


class SalleUtilisee(SalleErreur):
    def __init__(self, message):
        super().__init__(message, "salle_utilisee")


class VersionFigee(SalleErreur):
    def __init__(self, message):
        super().__init__(message, "version_figee")


def _id(prefixe: str) -> str:
    return prefixe + uuid.uuid4().hex[:12]


# ── Dates ────────────────────────────────────────────────────────────────────

def lundi_de(d: date) -> date:
    return d - timedelta(days=d.weekday())


def prochain_lundi(aujourd_hui: date) -> date:
    """Premier lundi STRICTEMENT après la semaine en cours."""
    return lundi_de(aujourd_hui) + timedelta(days=7)


def _valider_lundi(s: str) -> str:
    try:
        d = date.fromisoformat((s or "").strip())
    except ValueError:
        raise DonneesInvalides(f"Date d'effet invalide : {s!r} (AAAA-MM-JJ).")
    if d.weekday() != 0:
        raise DonneesInvalides(f"La date d'effet {s} n'est pas un lundi.")
    return d.isoformat()


# ── Schéma ───────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS salles (
    id               TEXT    PRIMARY KEY,
    etablissement_id TEXT    NOT NULL,
    nom              TEXT    NOT NULL,
    archivee         INTEGER NOT NULL DEFAULT 0,
    prochain_numero  INTEGER NOT NULL DEFAULT 1,
    UNIQUE (etablissement_id, nom)
);
CREATE TABLE IF NOT EXISTS salle_versions (
    id         TEXT PRIMARY KEY,
    salle_id   TEXT NOT NULL REFERENCES salles(id) ON DELETE CASCADE,
    date_effet TEXT NOT NULL DEFAULT '',
    UNIQUE (salle_id, date_effet)
);
CREATE TABLE IF NOT EXISTS salle_places (
    id         TEXT    PRIMARY KEY,
    version_id TEXT    NOT NULL REFERENCES salle_versions(id) ON DELETE CASCADE,
    numero     INTEGER NOT NULL,
    x          REAL    NOT NULL DEFAULT 0,
    y          REAL    NOT NULL DEFAULT 0,
    angle      REAL    NOT NULL DEFAULT 0,
    ilot       TEXT    NOT NULL DEFAULT '',
    UNIQUE (version_id, numero)
);
"""


# ── Utilisation ──────────────────────────────────────────────────────────────

def salle_est_utilisee(conn, salle_id: str) -> bool:
    """Vrai si la salle est affectée à au moins une case d'EdT.

    La colonne `edt_creneaux.salle_id` arrive en v0.38 : tant qu'elle
    n'existe pas, aucune salle n'est utilisée."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(edt_creneaux)")}
    if "salle_id" not in cols:
        return False
    r = conn.execute("SELECT 1 FROM edt_creneaux WHERE salle_id=? LIMIT 1",
                     (salle_id,)).fetchone()
    return r is not None


# ── Salles ───────────────────────────────────────────────────────────────────

def _lire_salle(conn, salle_id: str) -> dict:
    r = conn.execute("SELECT * FROM salles WHERE id=?", (salle_id,)).fetchone()
    if r is None:
        raise SalleIntrouvable(salle_id)
    return dict(r)


def _nom_valide(conn, etablissement_id: str, nom: str,
                sauf_id: str | None = None) -> str:
    nom = (nom or "").strip()
    if not nom:
        raise DonneesInvalides("Le nom de la salle est obligatoire.")
    r = conn.execute(
        "SELECT id FROM salles WHERE etablissement_id=? AND nom=? COLLATE NOCASE",
        (etablissement_id, nom)).fetchone()
    if r is not None and r["id"] != sauf_id:
        raise DonneesInvalides(f"La salle {nom!r} existe déjà.")
    return nom


def _resume(conn, s: dict, aujourd_hui: date) -> dict:
    v = version_en_vigueur(conn, s["id"], aujourd_hui)
    nb = conn.execute("SELECT COUNT(*) FROM salle_places WHERE version_id=?",
                      (v["id"],)).fetchone()[0] if v else 0
    nv = conn.execute("SELECT COUNT(*) FROM salle_versions WHERE salle_id=?",
                      (s["id"],)).fetchone()[0]
    return {"id": s["id"], "etablissement_id": s["etablissement_id"],
            "nom": s["nom"], "archivee": bool(s["archivee"]),
            "utilisee": salle_est_utilisee(conn, s["id"]),
            "nb_places": nb, "nb_versions": nv}


def lister(conn, etablissement_id: str, aujourd_hui: date) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM salles WHERE etablissement_id=? "
        "ORDER BY archivee, nom COLLATE NOCASE", (etablissement_id,)).fetchall()
    return [_resume(conn, dict(r), aujourd_hui) for r in rows]


def lire(conn, salle_id: str, aujourd_hui: date) -> dict:
    return _resume(conn, _lire_salle(conn, salle_id), aujourd_hui)


def creer(conn, etablissement_id: str, nom: str, aujourd_hui: date) -> dict:
    if conn.execute("SELECT 1 FROM etablissements WHERE id=?",
                    (etablissement_id,)).fetchone() is None:
        raise DonneesInvalides(f"Établissement {etablissement_id!r} introuvable.")
    nom = _nom_valide(conn, etablissement_id, nom)
    sid = _id("sa_")
    conn.execute("INSERT INTO salles (id, etablissement_id, nom) VALUES (?,?,?)",
                 (sid, etablissement_id, nom))
    conn.execute("INSERT INTO salle_versions (id, salle_id, date_effet) "
                 "VALUES (?,?, '')", (_id("sv_"), sid))
    return lire(conn, sid, aujourd_hui)


def modifier(conn, salle_id: str, champs: dict, aujourd_hui: date) -> dict:
    """Renommer (`nom`) et/ou archiver/réactiver (`archivee`)."""
    s = _lire_salle(conn, salle_id)
    if "nom" in champs:
        nom = _nom_valide(conn, s["etablissement_id"], champs["nom"], salle_id)
        conn.execute("UPDATE salles SET nom=? WHERE id=?", (nom, salle_id))
    if "archivee" in champs:
        conn.execute("UPDATE salles SET archivee=? WHERE id=?",
                     (1 if champs["archivee"] else 0, salle_id))
    return lire(conn, salle_id, aujourd_hui)


def supprimer(conn, salle_id: str) -> None:
    s = _lire_salle(conn, salle_id)
    if salle_est_utilisee(conn, salle_id):
        raise SalleUtilisee(
            f"La salle {s['nom']!r} est utilisée dans l'emploi du temps : "
            f"elle ne peut pas être supprimée (elle peut être archivée).")
    conn.execute("DELETE FROM salle_places WHERE version_id IN "
                 "(SELECT id FROM salle_versions WHERE salle_id=?)", (salle_id,))
    conn.execute("DELETE FROM salle_versions WHERE salle_id=?", (salle_id,))
    conn.execute("DELETE FROM salles WHERE id=?", (salle_id,))


def migrer_etablissement(conn, source_id: str, cible_id: str) -> int:
    """Rattache les salles de `source` à `cible` (fusion d'établissements).
    Lève DonneesInvalides si un nom de salle existe des deux côtés."""
    doublons = conn.execute(
        "SELECT s.nom FROM salles s JOIN salles c ON c.nom = s.nom "
        "COLLATE NOCASE AND c.etablissement_id=? WHERE s.etablissement_id=?",
        (cible_id, source_id)).fetchall()
    if doublons:
        noms = ", ".join(r["nom"] for r in doublons)
        raise DonneesInvalides(
            f"Salle(s) présente(s) dans les deux établissements : {noms}. "
            f"Renommer ou supprimer avant la fusion.")
    n = conn.execute("SELECT COUNT(*) FROM salles WHERE etablissement_id=?",
                     (source_id,)).fetchone()[0]
    conn.execute("UPDATE salles SET etablissement_id=? WHERE etablissement_id=?",
                 (cible_id, source_id))
    return n


# ── Versions ─────────────────────────────────────────────────────────────────

def _statut(date_effet: str, suivante: str | None, aujourd_hui: date) -> str:
    lundi = lundi_de(aujourd_hui).isoformat()
    if date_effet and date_effet > lundi:
        return "future"
    if suivante is None or suivante > lundi:
        return "en_vigueur"
    return "passee"


def lister_versions(conn, salle_id: str, aujourd_hui: date) -> list[dict]:
    _lire_salle(conn, salle_id)
    rows = [dict(r) for r in conn.execute(
        "SELECT v.id, v.date_effet, "
        " (SELECT COUNT(*) FROM salle_places p WHERE p.version_id=v.id) AS nb_places "
        "FROM salle_versions v WHERE v.salle_id=? ORDER BY v.date_effet",
        (salle_id,)).fetchall()]
    for i, v in enumerate(rows):
        suiv = rows[i + 1]["date_effet"] if i + 1 < len(rows) else None
        v["statut"] = _statut(v["date_effet"], suiv, aujourd_hui)
    return rows


def version_en_vigueur(conn, salle_id: str, d: date) -> dict | None:
    """Version applicable la semaine de `d` (date_effet ≤ lundi de d ; la
    version initiale '' précède toutes les autres)."""
    r = conn.execute(
        "SELECT * FROM salle_versions WHERE salle_id=? AND date_effet <= ? "
        "ORDER BY date_effet DESC LIMIT 1",
        (salle_id, lundi_de(d).isoformat())).fetchone()
    return dict(r) if r else None


def _places(conn, version_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT numero, x, y, angle, ilot FROM salle_places "
        "WHERE version_id=? ORDER BY numero", (version_id,)).fetchall()]


def lire_plan(conn, salle_id: str, aujourd_hui: date, *,
              version_id: str | None = None, d: date | None = None) -> dict:
    """Plan d'une version : par id, ou celle en vigueur à la date `d`
    (défaut : aujourd'hui)."""
    s = _lire_salle(conn, salle_id)
    if version_id:
        r = conn.execute("SELECT * FROM salle_versions WHERE id=? AND salle_id=?",
                         (version_id, salle_id)).fetchone()
        if r is None:
            raise VersionIntrouvable(version_id)
        v = dict(r)
    else:
        v = version_en_vigueur(conn, salle_id, d or aujourd_hui)
    versions = lister_versions(conn, salle_id, aujourd_hui)
    statut = next(x["statut"] for x in versions if x["id"] == v["id"])
    utilisee = salle_est_utilisee(conn, salle_id)
    return {"salle": _resume(conn, s, aujourd_hui),
            "version": {"id": v["id"], "date_effet": v["date_effet"],
                        "statut": statut,
                        "modifiable": (not utilisee) or statut == "future"},
            "places": _places(conn, v["id"]),
            "prochain_numero": s["prochain_numero"],
            "date_effet_min": prochain_lundi(aujourd_hui).isoformat()}


def _num(v, nom: str) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise DonneesInvalides(f"Valeur numérique attendue pour {nom} : {v!r}.")
    if math.isnan(f) or math.isinf(f):
        raise DonneesInvalides(f"Valeur numérique invalide pour {nom}.")
    return f


def _normaliser_places(places, prochain: int) -> tuple[list[dict], int]:
    """Valide les places reçues, attribue un numéro aux nouvelles (sans
    numéro) et renvoie (places, nouveau prochain_numero)."""
    if not isinstance(places, list):
        raise DonneesInvalides("`places` doit être une liste.")
    vus, sortie = set(), []
    for p in places:
        if not isinstance(p, dict):
            raise DonneesInvalides("Place invalide.")
        n = p.get("numero")
        if n is not None:
            try:
                n = int(n)
            except (TypeError, ValueError):
                raise DonneesInvalides(f"Numéro de place invalide : {n!r}.")
            if n < 1 or n >= prochain:
                raise DonneesInvalides(
                    f"Numéro de place {n} inconnu : les nouvelles places "
                    f"doivent être envoyées sans numéro.")
            if n in vus:
                raise DonneesInvalides(f"Numéro de place {n} en double.")
            vus.add(n)
        sortie.append({"numero": n,
                       "x": round(_num(p.get("x", 0), "x"), 1),
                       "y": round(_num(p.get("y", 0), "y"), 1),
                       "angle": round(_num(p.get("angle", 0), "angle") % 360.0, 1),
                       "ilot": str(p.get("ilot") or "")[:40]})
    for p in sortie:
        if p["numero"] is None:
            p["numero"] = prochain
            prochain += 1
    return sortie, prochain


def _ecrire_places(conn, version_id: str, places: list[dict]) -> None:
    conn.execute("DELETE FROM salle_places WHERE version_id=?", (version_id,))
    conn.executemany(
        "INSERT INTO salle_places (id, version_id, numero, x, y, angle, ilot) "
        "VALUES (?,?,?,?,?,?,?)",
        [(_id("sp_"), version_id, p["numero"], p["x"], p["y"], p["angle"],
          p["ilot"]) for p in places])


def enregistrer_plan(conn, salle_id: str, places, aujourd_hui: date, *,
                     version_id: str | None = None,
                     date_effet: str | None = None) -> dict:
    """Enregistre un plan.

    - `date_effet` (lundi ≥ semaine prochaine) : crée la version à cette date,
      ou remplace la version future qui y existe déjà.
    - `version_id` : remplace cette version, si elle est modifiable.
    - ni l'un ni l'autre : salle non utilisée → version en vigueur, en place ;
      salle utilisée → refusé (il faut une date d'effet).
    """
    s = _lire_salle(conn, salle_id)
    utilisee = salle_est_utilisee(conn, salle_id)
    if date_effet:
        de = _valider_lundi(date_effet)
        if de < prochain_lundi(aujourd_hui).isoformat():
            raise VersionFigee(
                f"Une nouvelle version ne peut prendre effet qu'à partir du "
                f"{prochain_lundi(aujourd_hui).isoformat()}.")
        r = conn.execute("SELECT id FROM salle_versions WHERE salle_id=? AND "
                         "date_effet=?", (salle_id, de)).fetchone()
        if r:
            vid = r["id"]
        else:
            vid = _id("sv_")
            conn.execute("INSERT INTO salle_versions (id, salle_id, date_effet) "
                         "VALUES (?,?,?)", (vid, salle_id, de))
    elif version_id:
        r = conn.execute("SELECT * FROM salle_versions WHERE id=? AND salle_id=?",
                         (version_id, salle_id)).fetchone()
        if r is None:
            raise VersionIntrouvable(version_id)
        vid = r["id"]
        if utilisee and _statut_version(conn, salle_id, vid, aujourd_hui) != "future":
            raise VersionFigee(
                "Cette version du plan est en vigueur ou passée et la salle est "
                "utilisée : créer une nouvelle version avec une date d'effet.")
    else:
        if utilisee:
            raise VersionFigee(
                "La salle est utilisée : la modification doit porter une date "
                "d'effet (lundi à partir de la semaine prochaine).")
        vid = version_en_vigueur(conn, salle_id, aujourd_hui)["id"]
    norm, prochain = _normaliser_places(places, s["prochain_numero"])
    _ecrire_places(conn, vid, norm)
    conn.execute("UPDATE salles SET prochain_numero=? WHERE id=?",
                 (prochain, salle_id))
    return lire_plan(conn, salle_id, aujourd_hui, version_id=vid)


def _statut_version(conn, salle_id, version_id, aujourd_hui) -> str:
    for v in lister_versions(conn, salle_id, aujourd_hui):
        if v["id"] == version_id:
            return v["statut"]
    raise VersionIntrouvable(version_id)


def supprimer_version(conn, version_id: str, aujourd_hui: date) -> None:
    r = conn.execute("SELECT * FROM salle_versions WHERE id=?",
                     (version_id,)).fetchone()
    if r is None:
        raise VersionIntrouvable(version_id)
    salle_id = r["salle_id"]
    if r["date_effet"] == "":
        raise DonneesInvalides("La version initiale du plan ne se supprime pas.")
    if (salle_est_utilisee(conn, salle_id)
            and _statut_version(conn, salle_id, version_id, aujourd_hui) != "future"):
        raise VersionFigee("Seule une version future peut être supprimée.")
    conn.execute("DELETE FROM salle_places WHERE version_id=?", (version_id,))
    conn.execute("DELETE FROM salle_versions WHERE id=?", (version_id,))
