"""services/api_client.py — v0.51.16

Côté atelier : le **client** de la boîte aux lettres par API de l'appli de
classe (services/api_boite.py). L'atelier appelle toujours l'appli de classe
(elle ne peut pas joindre le PC de l'enseignant).

  - **destination** : adresse de l'appli de classe et jeton d'accès (copié
    depuis l'appli de classe), dans une liste qui n'a qu'une ligne pour
    l'instant (plusieurs appli de classe possibles plus tard) ; en ligne,
    HTTPS obligatoire (http seulement pour localhost) ;
  - **synchroniser** (au démarrage, à chaque relève, à la demande, et dès la
    création d'un paquet) : envoie les paquets pas encore livrés ni acquittés,
    rapatrie les nouveaux retours d'usage dans le dossier d'entrée, puis
    relève la boîte aux lettres (traitement selon le mode réglé) ;
  - l'appli de classe injoignable n'empêche rien : les envois attendent la
    synchronisation suivante ; la boîte aux lettres par dossiers et l'import
    à la main restent possibles ; l'état (dernier contact, erreur, expiration
    du jeton) est affiché.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

ID = "principale"
DELAI = 10            # secondes (appels courts)
DELAI_ENVOI = 300     # secondes (dépôt d'un paquet)
PREVENIR_JOURS = 15

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_destinations (
    id                  TEXT PRIMARY KEY,
    nom                 TEXT NOT NULL DEFAULT '',
    url                 TEXT NOT NULL DEFAULT '',
    jeton               TEXT NOT NULL DEFAULT '',
    expire_le           TEXT NOT NULL DEFAULT '',
    derniere_tentative  TEXT NOT NULL DEFAULT '',
    derniere_reussite   TEXT NOT NULL DEFAULT '',
    derniere_erreur     TEXT NOT NULL DEFAULT '',
    erreur_depuis       TEXT NOT NULL DEFAULT ''
);
"""

_VERROU = threading.Lock()


class ClientErreur(Exception):
    def __init__(self, message: str, code: str = "injoignable"):
        super().__init__(message)
        self.code = code


def _maintenant() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def migrer(conn) -> None:
    from services import echanges as ech
    conn.executescript(SCHEMA)
    ech.migrer(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(echanges_envoyes)")}
    if "livre_le" not in cols:
        conn.execute("ALTER TABLE echanges_envoyes ADD COLUMN livre_le TEXT NOT NULL DEFAULT ''")


def valider_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ClientErreur("Adresse invalide (ex. https://classe.exemple.fr).", "donnees_invalides")
    if p.scheme == "http" and p.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ClientErreur("HTTPS obligatoire pour une appli en ligne (http seulement pour "
                           "localhost).", "donnees_invalides")
    return url


def destination(conn) -> dict:
    migrer(conn)
    r = conn.execute("SELECT * FROM api_destinations WHERE id=?", (ID,)).fetchone()
    return dict(r) if r else {"id": ID, "nom": "", "url": "", "jeton": "", "expire_le": "",
                               "derniere_tentative": "", "derniere_reussite": "",
                               "derniere_erreur": "", "erreur_depuis": ""}


def definir(conn, url: str | None = None, jeton: str | None = None) -> dict:
    """Enregistre l'adresse et/ou le jeton (un jeton vide garde l'actuel ;
    une adresse vide désactive l'API)."""
    d = destination(conn)
    if url is not None:
        d["url"] = valider_url(url)
    if jeton:
        d["jeton"] = jeton.strip()
        d["expire_le"] = ""
    conn.execute(
        "INSERT INTO api_destinations (id, url, jeton, expire_le) VALUES (?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET url=excluded.url, jeton=excluded.jeton, "
        "expire_le=excluded.expire_le", (ID, d["url"], d["jeton"], d["expire_le"]))
    return etat(conn)


def configuree(d: dict) -> bool:
    return bool(d.get("url") and d.get("jeton"))


def etat(conn, aujourd_hui: date | None = None) -> dict:
    """État affiché (le jeton n'est jamais renvoyé)."""
    d = destination(conn)
    jours = None
    if d["expire_le"]:
        jours = (date.fromisoformat(d["expire_le"]) - (aujourd_hui or date.today())).days
    return {"configuree": configuree(d), "url": d["url"], "jeton_enregistre": bool(d["jeton"]),
            "nom": d["nom"], "expire_le": d["expire_le"], "jours_restants": jours,
            "expire_bientot": jours is not None and 0 < jours <= PREVENIR_JOURS,
            "expire": jours is not None and jours <= 0,
            "derniere_tentative": d["derniere_tentative"],
            "derniere_reussite": d["derniere_reussite"],
            "derniere_erreur": d["derniere_erreur"], "erreur_depuis": d["erreur_depuis"],
            "injoignable": bool(d["derniere_erreur"])}


# ── HTTP ─────────────────────────────────────────────────────────────────────

def _appel(d: dict, methode: str, chemin: str, corps: bytes | None = None,
           entetes: dict | None = None, delai: int = DELAI) -> tuple[bytes, dict]:
    url = d["url"].rstrip("/") + "/api/boite/v1" + chemin
    h = {"Authorization": f"Bearer {d['jeton']}", "Accept": "application/json"}
    h.update(entetes or {})
    req = urllib.request.Request(url, data=corps, method=methode, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=delai) as r:
            return r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error") or ""
        except Exception:
            msg = ""
        code = "jeton" if e.code == 401 else ("limite" if e.code == 429 else "refuse")
        raise ClientErreur(msg or f"Refus de l'appli de classe (HTTP {e.code}).", code)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ClientErreur(f"Appli de classe injoignable ({getattr(e, 'reason', e)}).")


def _json(d, methode, chemin, **kw) -> dict:
    corps, _ = _appel(d, methode, chemin, **kw)
    return json.loads(corps.decode("utf-8") or "{}")


# ── Synchronisation ──────────────────────────────────────────────────────────

def _noter(store, ok: bool, erreur: str = "", expire_le: str | None = None,
           nom: str | None = None) -> None:
    with store._conn() as conn:
        d = destination(conn)
        t = _maintenant()
        conn.execute(
            "INSERT INTO api_destinations (id, url, jeton) VALUES (?,?,?) ON CONFLICT(id) "
            "DO NOTHING", (ID, d["url"], d["jeton"]))
        conn.execute(
            "UPDATE api_destinations SET derniere_tentative=?, derniere_reussite=?, "
            "derniere_erreur=?, erreur_depuis=?, expire_le=?, nom=? WHERE id=?",
            (t, t if ok else d["derniere_reussite"], "" if ok else erreur,
             "" if ok else (d["erreur_depuis"] or t),
             expire_le if expire_le is not None else d["expire_le"],
             nom if nom is not None else d["nom"], ID))


def tester(store) -> dict:
    with store._conn() as conn:
        d = destination(conn)
    if not configuree(d):
        return {"ok": False, "message": "Adresse et jeton à renseigner."}
    try:
        e = _json(d, "GET", "/etat")
    except ClientErreur as err:
        _noter(store, False, str(err))
        return {"ok": False, "message": str(err)}
    _noter(store, True, expire_le=(e.get("jeton") or {}).get("expire_le", ""),
           nom=(e.get("instance") or {}).get("nom", ""))
    return {"ok": True, "message": f"Connexion à « {e['instance']['nom']} » réussie.",
            "etat": e}


def _envoyer(store, d: dict, attendu: int) -> list[int]:
    """Paquets non acquittés pas encore livrés (n° ≥ attendu par la classe)."""
    with store._conn() as conn:
        migrer(conn)
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM echanges_envoyes WHERE type='paquet' AND acquitte_le='' AND "
            "archive<>'' AND livre_le='' ORDER BY numero").fetchall()]
    livres = []
    for r in rows:
        if r["numero"] < attendu:                     # déjà reçu par la classe
            with store._conn() as conn:
                conn.execute("UPDATE echanges_envoyes SET livre_le=? WHERE type='paquet' AND "
                             "numero=?", (_maintenant(), r["numero"]))
            continue
        chemin = Path(store.data_dir) / r["archive"]
        if not chemin.is_file():
            continue
        rep = _json(d, "POST", "/paquets", corps=chemin.read_bytes(), delai=DELAI_ENVOI,
                    entetes={"Content-Type": "application/zip",
                             "X-Nom-Fichier": urllib.parse.quote(r["nom_fichier"])})
        if rep.get("issue") == "refuse":
            raise ClientErreur(f"Paquet n° {r['numero']} refusé par l'appli de classe : "
                               f"{rep.get('message', '')}", "refuse")
        with store._conn() as conn:
            conn.execute("UPDATE echanges_envoyes SET livre_le=? WHERE type='paquet' AND "
                         "numero=?", (_maintenant(), r["numero"]))
        livres.append(r["numero"])
    return livres


def _recevoir(store, d: dict) -> list[str]:
    """Retours d'usage nouveaux → dossier d'entrée de l'atelier."""
    from services import depot
    from services import echanges as ech
    with store._conn() as conn:
        apres = ech._dernier_recu(conn, "usage")
        dossier = depot.dossier_entrants(conn, store.data_dir)
    dispo = _json(d, "GET", f"/usages?apres={apres}").get("usages", [])
    dossier.mkdir(parents=True, exist_ok=True)
    recus = []
    for u in dispo:
        nom = Path(u["nom"]).name
        if (dossier / nom).exists():
            continue
        corps, _ = _appel(d, "GET", f"/usages/{int(u['numero'])}")
        (dossier / nom).write_bytes(corps)
        recus.append(nom)
    return recus


def synchroniser(store, profil: str = "atelier", envoyer: bool = True,
                 recevoir: bool = True, relever: bool = True) -> dict:
    """Un passage complet ; ne lève pas (l'erreur est notée et renvoyée)."""
    from services import depot
    with store._conn() as conn:
        d = destination(conn)
    res = {"configuree": configuree(d), "ok": False, "livres": [], "recus": [], "erreur": "",
           "releve": None}
    if not res["configuree"]:
        return res
    with _VERROU:
        try:
            e = _json(d, "GET", "/etat")
            if envoyer:
                res["livres"] = _envoyer(store, d, int((e.get("attendu") or {}).get("paquet") or 1))
            if recevoir:
                res["recus"] = _recevoir(store, d)
            res["ok"] = True
            _noter(store, True, expire_le=(e.get("jeton") or {}).get("expire_le", ""),
                   nom=(e.get("instance") or {}).get("nom", ""))
        except ClientErreur as err:
            res["erreur"] = str(err)
            _noter(store, False, str(err))
    if relever and res["recus"]:
        res["releve"] = depot.relever(store, profil)
    return res
