"""services/api_boite.py — v0.51.16

Côté appli de classe : la **boîte aux lettres par API**, que l'atelier
appelle (l'atelier est toujours le client : l'appli en ligne ne peut pas
joindre le PC de l'enseignant).

  - **jeton d'accès** : généré ici, montré une seule fois, copié dans les
    préférences de l'atelier ; date d'expiration obligatoire (défaut : le
    1er août qui suit, une année scolaire) ; en générer un nouveau révoque
    l'actuel ; seule son empreinte (SHA-256) est conservée ;
  - **portée minimale** : déposer un paquet de publication (rangé dans le
    dossier d'entrée, puis traité selon le mode réglé — confirmation ou
    automatique), lister et télécharger les retours d'usage ; jamais de
    donnée d'élève ;
  - **retour d'usage automatique** : quand l'atelier relève, un nouveau
    retour est produit si l'usage a changé depuis le dernier envoi.

Les contrôles du protocole d'échange (numéro attendu, émetteur lié, contenu)
restent ceux de la boîte aux lettres (services/depot.py).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from collections import deque
from datetime import date, datetime
from pathlib import Path

PREFIXE = "seqj_"
TAILLE_MAX = 512 * 1024 * 1024          # paquet de publication (PDF compris)
APPELS_PAR_MINUTE = 120
ECHECS_MAX = 10                          # jetons refusés par adresse, sur 10 min

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_jetons (
    id             TEXT PRIMARY KEY,
    empreinte      TEXT NOT NULL,
    cree_le        TEXT NOT NULL,
    expire_le      TEXT NOT NULL,            -- AAAA-MM-JJ : refusé à partir de ce jour
    revoque_le     TEXT NOT NULL DEFAULT '',
    dernier_usage  TEXT NOT NULL DEFAULT ''
);
"""


class ApiErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides", statut: int = 400):
        super().__init__(message)
        self.code = code
        self.statut = statut


def _maintenant() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def migrer(conn) -> None:
    conn.executescript(SCHEMA)


def _empreinte(jeton: str) -> str:
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def expiration_par_defaut(aujourd_hui: date | None = None) -> str:
    """Le 1er août qui suit (fin de l'année scolaire)."""
    d = aujourd_hui or date.today()
    an = d.year if d < date(d.year, 8, 1) else d.year + 1
    return date(an, 8, 1).isoformat()


# ── Jeton ────────────────────────────────────────────────────────────────────

def _actif(conn):
    migrer(conn)
    return conn.execute("SELECT * FROM api_jetons WHERE revoque_le='' ORDER BY cree_le DESC "
                        "LIMIT 1").fetchone()


def etat_jeton(conn, aujourd_hui: date | None = None) -> dict:
    d = aujourd_hui or date.today()
    r = _actif(conn)
    if r is None:
        return {"actif": False, "expire_le": "", "cree_le": "", "dernier_usage": "",
                "expire": False, "jours_restants": None,
                "expiration_defaut": expiration_par_defaut(d)}
    jours = (date.fromisoformat(r["expire_le"]) - d).days
    return {"actif": jours > 0, "expire_le": r["expire_le"], "cree_le": r["cree_le"],
            "dernier_usage": r["dernier_usage"], "expire": jours <= 0,
            "jours_restants": jours, "expire_bientot": 0 < jours <= 15,
            "expiration_defaut": expiration_par_defaut(d)}


def generer(conn, expire_le: str, aujourd_hui: date | None = None) -> dict:
    """Nouveau jeton (renvoyé une seule fois) ; l'actuel est révoqué."""
    d = aujourd_hui or date.today()
    try:
        fin = date.fromisoformat((expire_le or "").strip())
    except ValueError:
        raise ApiErreur("Date d'expiration invalide (AAAA-MM-JJ).")
    if fin <= d:
        raise ApiErreur("La date d'expiration doit être dans le futur.")
    if (fin - d).days > 2 * 366:
        raise ApiErreur("Date d'expiration trop lointaine (deux ans au plus).")
    migrer(conn)
    conn.execute("UPDATE api_jetons SET revoque_le=? WHERE revoque_le=''", (_maintenant(),))
    jeton = PREFIXE + secrets.token_urlsafe(32)
    conn.execute("INSERT INTO api_jetons (id, empreinte, cree_le, expire_le) VALUES (?,?,?,?)",
                 ("jt_" + secrets.token_hex(6), _empreinte(jeton), _maintenant(), fin.isoformat()))
    return {"jeton": jeton, **etat_jeton(conn, d)}


def revoquer(conn) -> None:
    migrer(conn)
    conn.execute("UPDATE api_jetons SET revoque_le=? WHERE revoque_le=''", (_maintenant(),))


def verifier(conn, jeton: str, aujourd_hui: date | None = None) -> None:
    """Lève ApiErreur (401) si le jeton n'est pas l'actuel ou a expiré."""
    d = aujourd_hui or date.today()
    r = _actif(conn)
    if not jeton or r is None or not hmac.compare_digest(_empreinte(jeton), r["empreinte"]):
        raise ApiErreur("Jeton d'accès refusé.", "jeton_refuse", 401)
    if date.fromisoformat(r["expire_le"]) <= d:
        raise ApiErreur(f"Jeton d'accès expiré le {r['expire_le']} : générez-en un nouveau "
                        "dans l'appli de classe.", "jeton_expire", 401)
    conn.execute("UPDATE api_jetons SET dernier_usage=? WHERE id=?", (_maintenant(), r["id"]))


# ── Limitation des appels (mémoire du processus) ─────────────────────────────

_VERROU = threading.Lock()
_APPELS: dict[str, deque] = {}
_ECHECS: dict[str, deque] = {}


def limiter(adresse: str, echec: bool = False, maintenant: float | None = None) -> bool:
    """Vrai si l'appel est permis (et le compte). `echec` : enregistre un jeton
    refusé."""
    t = maintenant if maintenant is not None else time.monotonic()
    with _VERROU:
        if echec:
            q = _ECHECS.setdefault(adresse, deque())
            q.append(t)
            return True
        e = _ECHECS.setdefault(adresse, deque())
        while e and t - e[0] > 600:
            e.popleft()
        if len(e) >= ECHECS_MAX:
            return False
        q = _APPELS.setdefault(adresse, deque())
        while q and t - q[0] > 60:
            q.popleft()
        if len(q) >= APPELS_PAR_MINUTE:
            return False
        q.append(t)
        return True


def remettre_a_zero() -> None:                       # tests
    with _VERROU:
        _APPELS.clear()
        _ECHECS.clear()


# ── Boîte aux lettres ────────────────────────────────────────────────────────

_NOM_SUR = re.compile(r"[^A-Za-z0-9_.\-]")


def etat_boite(conn, data_dir: Path) -> dict:
    from services import echanges as ech
    i = ech.instance(conn)
    return {"instance": {"id": i["id"], "nom": i["nom"], "role": i.get("role", "")},
            "attendu": {"paquet": ech._dernier_recu(conn, "paquet") + 1},
            "jeton": {k: v for k, v in etat_jeton(conn).items()
                      if k in ("expire_le", "jours_restants")}}


def deposer_paquet(store, contenu: bytes, nom: str) -> dict:
    """Range le paquet dans le dossier d'entrée puis relève (mode réglé)."""
    from services import depot
    import io
    import zipfile
    if len(contenu) > TAILLE_MAX:
        raise ApiErreur("Paquet trop volumineux.", "trop_gros", 413)
    try:
        with zipfile.ZipFile(io.BytesIO(contenu)) as z:
            m = json.loads(z.read("paquet.json").decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, ValueError):
        raise ApiErreur("Ce fichier n'est pas un paquet de publication.")
    if m.get("format") != "seqenseigne.paquet":
        raise ApiErreur("Ce fichier n'est pas un paquet de publication.")
    nom = _NOM_SUR.sub("_", Path(nom or m.get("nom") or "paquet.zip").name)
    if not nom.lower().endswith(".zip"):
        nom += ".zip"
    with store._conn() as conn:
        dossier = depot.dossier_entrants(conn, store.data_dir)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / nom).write_bytes(contenu)
    rapport = depot.relever(store, "classe")
    for cle, issue in (("traites", "traite"), ("doublons", "doublon"), ("refuses", "refuse")):
        for x in rapport[cle]:
            if x["fichier"] == nom:
                return {"fichier": nom, "issue": issue, "message": x.get("message", "")}
    attente = next((x for x in rapport["en_attente"] if x["fichier"] == nom), None)
    return {"fichier": nom, "issue": "en_attente",
            "message": (attente or {}).get("message", "") or
            ("En attente de confirmation dans l'appli de classe."
             if rapport["mode"] != "automatique" else "")}


def _refs_usage(doc: dict) -> str:
    return hashlib.sha256(json.dumps(doc.get("referentiels") or [], sort_keys=True,
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def usages_disponibles(store, apres: int) -> list[dict]:
    """Retours d'usage archivés de n° > `apres` ; en produit un nouveau si
    l'usage a changé depuis le dernier envoi."""
    from services import depot
    from services import echanges as ech
    from services import retour_usage as ru
    with store._conn() as conn:
        doc = ru.construire(conn)
        if doc["referentiels"]:
            emp = _refs_usage(doc)
            if depot._lire(conn, "usage_empreinte") != emp:
                ru.creer(conn, store.data_dir)          # note l'empreinte
        ech.migrer(conn)
        return [{"numero": r["numero"], "nom": r["nom_fichier"], "taille": r["taille"],
                 "cree_le": r["cree_le"]}
                for r in conn.execute(
                    "SELECT * FROM echanges_envoyes WHERE type='usage' AND numero>? AND "
                    "archive<>'' ORDER BY numero", (int(apres or 0),)).fetchall()]


def lire_usage(store, numero: int) -> tuple[str, bytes]:
    from services import echanges as ech
    with store._conn() as conn:
        try:
            return ech.lire_archive(conn, store.data_dir, "usage", numero)
        except ech.EchangeErreur as e:
            raise ApiErreur(str(e), "introuvable", 404)


def noter_usage_cree(conn, doc: dict) -> None:
    """Après un retour d'usage créé à la main : même empreinte que l'automatique
    (évite un doublon à la relève suivante)."""
    from services import depot
    depot.migrer(conn)
    conn.execute("INSERT INTO depot_reglages (cle, valeur) VALUES ('usage_empreinte', ?) "
                 "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur", (_refs_usage(doc),))
