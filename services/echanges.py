"""services/echanges.py — v0.51.7

Protocole d'échange entre l'appli locale (atelier) et l'appli en ligne
(classe), sur le modèle des datagrammes acquittés :

  - **identité** : chaque base a un identifiant unique (créé à la première
    utilisation) et un nom modifiable ; au premier échange reçu, la base se
    lie à son correspondant (un atelier ↔ une appli en ligne) ; un fichier
    d'une autre instance est refusé ;
  - **en-tête** de chaque fichier échangé (`echange` dans le manifeste) :
    type, émetteur {id, nom, role}, destinataire (id du correspondant connu,
    sinon null), numéro d'ordre propre à l'émetteur et au type (1, 2, 3…),
    accusé (dernier numéro reçu de l'autre côté) ;
  - **réception dans l'ordre** : on attend le n° suivant ; un numéro déjà
    reçu est ignoré ; un trou est refusé avec la liste des numéros à
    redemander ; un fichier sans en-tête (antérieur à la v0.51.7) n'est
    accepté que tant qu'aucun fichier numéroté n'a été reçu ;
  - **archive** des envois (`data/echanges/envoyes/`) pour pouvoir les
    renvoyer ; un envoi acquitté par l'autre côté est retiré de l'archive.

Types : « paquet » (atelier → classe) ; « usage » (classe → atelier, retour
d'usage, v0.51.8). En base partagée (même identifiant des deux côtés), pas
de contrôle de séquence.
"""

from __future__ import annotations

import socket
import uuid
from datetime import datetime
from pathlib import Path

TYPES = ("paquet", "usage")
ROLE_EMETTEUR = {"paquet": "atelier", "usage": "classe"}
_INVERSE = {"paquet": "usage", "usage": "paquet"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS instance_locale (
    id       TEXT PRIMARY KEY,
    nom      TEXT NOT NULL DEFAULT '',
    cree_le  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS correspondants (
    role     TEXT PRIMARY KEY,           -- 'atelier' | 'classe'
    id       TEXT NOT NULL,
    nom      TEXT NOT NULL DEFAULT '',
    lie_le   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS echanges_envoyes (
    type          TEXT NOT NULL,         -- 'paquet' | 'usage'
    numero        INTEGER NOT NULL,
    cree_le       TEXT NOT NULL,
    nom_fichier   TEXT NOT NULL,
    archive       TEXT NOT NULL DEFAULT '',   -- chemin relatif à data/ ('' = retiré)
    taille        INTEGER NOT NULL DEFAULT 0,
    destinataire  TEXT NOT NULL DEFAULT '',
    acquitte_le   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (type, numero)
);
CREATE TABLE IF NOT EXISTS echanges_recus (
    type       TEXT NOT NULL,
    numero     INTEGER NOT NULL,         -- 0 = fichier sans en-tête (antérieur)
    emetteur   TEXT NOT NULL DEFAULT '',
    nom_fichier TEXT NOT NULL DEFAULT '',
    recu_le    TEXT NOT NULL
);
"""


class EchangeErreur(Exception):
    def __init__(self, message: str, code: str = "echange_refuse", details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _maintenant() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def migrer(conn) -> None:
    conn.executescript(SCHEMA)
    # v0.51.12 — Rôle de la base ('' avant la bascule ; 'atelier' | 'classe').
    if "role" not in {r[1] for r in conn.execute("PRAGMA table_info(instance_locale)")}:
        conn.execute("ALTER TABLE instance_locale ADD COLUMN role TEXT NOT NULL DEFAULT ''")


# ── Identité ─────────────────────────────────────────────────────────────────

def instance(conn) -> dict:
    """Identité de cette base (créée à la première demande)."""
    migrer(conn)
    r = conn.execute("SELECT * FROM instance_locale LIMIT 1").fetchone()
    if r is None:
        try:
            hote = socket.gethostname()
        except OSError:                                    # pragma: no cover
            hote = ""
        iid = "inst_" + uuid.uuid4().hex
        conn.execute("INSERT INTO instance_locale (id, nom, cree_le) VALUES (?,?,?)",
                     (iid, f"seqenseigne — {hote}" if hote else "seqenseigne", _maintenant()))
        r = conn.execute("SELECT * FROM instance_locale LIMIT 1").fetchone()
    return dict(r)


def renommer(conn, nom: str) -> dict:
    nom = (nom or "").strip()
    if not nom:
        raise EchangeErreur("Le nom de l'instance est obligatoire.", "donnees_invalides")
    i = instance(conn)
    conn.execute("UPDATE instance_locale SET nom=? WHERE id=?", (nom[:80], i["id"]))
    return instance(conn)


def correspondant(conn, role: str) -> dict | None:
    migrer(conn)
    r = conn.execute("SELECT * FROM correspondants WHERE role=?", (role,)).fetchone()
    return dict(r) if r else None


def _lier(conn, role: str, emetteur: dict) -> None:
    if correspondant(conn, role) is None:
        conn.execute("INSERT INTO correspondants (role, id, nom, lie_le) VALUES (?,?,?,?)",
                     (role, emetteur["id"], emetteur.get("nom") or "", _maintenant()))
    else:
        conn.execute("UPDATE correspondants SET nom=? WHERE role=? AND id=?",
                     (emetteur.get("nom") or "", role, emetteur["id"]))


def delier(conn, role: str) -> None:
    """Oublie le correspondant (changement d'instance, base recréée…)."""
    migrer(conn)
    conn.execute("DELETE FROM correspondants WHERE role=?", (role,))


# ── Envoi ────────────────────────────────────────────────────────────────────

def _dernier_recu(conn, type_: str) -> int:
    return conn.execute("SELECT COALESCE(MAX(numero), 0) FROM echanges_recus WHERE type=?",
                        (type_,)).fetchone()[0]


def prochain_numero(conn, type_: str) -> int:
    migrer(conn)
    return conn.execute("SELECT COALESCE(MAX(numero), 0) FROM echanges_envoyes WHERE type=?",
                        (type_,)).fetchone()[0] + 1


def entete(conn, type_: str) -> dict:
    """En-tête du prochain envoi de ce type (le numéro n'est réservé qu'à
    l'archivage, voir `archiver`)."""
    if type_ not in TYPES:
        raise EchangeErreur(f"Type d'échange inconnu : {type_!r}.", "donnees_invalides")
    moi = instance(conn)
    role_dest = ROLE_EMETTEUR[_INVERSE[type_]]
    dest = correspondant(conn, role_dest)
    return {"type": type_, "numero": prochain_numero(conn, type_),
            "emetteur": {"id": moi["id"], "nom": moi["nom"], "role": ROLE_EMETTEUR[type_]},
            "destinataire": dest["id"] if dest else None,
            "accuse": _dernier_recu(conn, _INVERSE[type_]) or None}


def archiver(conn, data_dir: Path, en_tete: dict, nom_fichier: str, contenu: bytes) -> None:
    """Inscrit l'envoi et garde une copie pour pouvoir le renvoyer."""
    rel = f"echanges/envoyes/{en_tete['type']}_{en_tete['numero']:04d}_{nom_fichier}"
    chemin = Path(data_dir) / rel
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(contenu)
    conn.execute("INSERT INTO echanges_envoyes (type, numero, cree_le, nom_fichier, archive, "
                 "taille, destinataire) VALUES (?,?,?,?,?,?,?)",
                 (en_tete["type"], en_tete["numero"], _maintenant(), nom_fichier, rel,
                  len(contenu), en_tete.get("destinataire") or ""))
    # v0.51.9 — Copie dans le dossier de sortie de la boîte aux lettres.
    from services import depot
    depot.copier_sortant(conn, nom_fichier, contenu)


def envois(conn, type_: str, limite: int = 30) -> list[dict]:
    migrer(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM echanges_envoyes WHERE type=? ORDER BY numero DESC LIMIT ?",
        (type_, limite)).fetchall()]


def lire_archive(conn, data_dir: Path, type_: str, numero: int) -> tuple[str, bytes]:
    """(nom de fichier, contenu) d'un envoi archivé, pour le renvoyer."""
    migrer(conn)
    r = conn.execute("SELECT * FROM echanges_envoyes WHERE type=? AND numero=?",
                     (type_, int(numero))).fetchone()
    if r is None:
        raise EchangeErreur(f"Envoi n° {numero} inconnu.", "introuvable")
    if not r["archive"]:
        raise EchangeErreur(f"L'envoi n° {numero} a été acquitté : il n'est plus archivé.",
                            "introuvable")
    p = Path(data_dir) / r["archive"]
    if not p.is_file():
        raise EchangeErreur(f"Archive de l'envoi n° {numero} introuvable.", "introuvable")
    return r["nom_fichier"], p.read_bytes()


def acquitter(conn, data_dir: Path, type_: str, jusqu_a: int | None) -> list[int]:
    """Marque acquittés les envois ≤ `jusqu_a` et retire leur archive."""
    if not jusqu_a:
        return []
    migrer(conn)
    faits = []
    for r in conn.execute("SELECT * FROM echanges_envoyes WHERE type=? AND numero<=? AND "
                          "acquitte_le=''", (type_, int(jusqu_a))).fetchall():
        if r["archive"]:
            try:
                (Path(data_dir) / r["archive"]).unlink()
            except OSError:
                pass
        conn.execute("UPDATE echanges_envoyes SET acquitte_le=?, archive='' WHERE type=? AND "
                     "numero=?", (_maintenant(), type_, r["numero"]))
        faits.append(r["numero"])
    return faits


# ── Réception ────────────────────────────────────────────────────────────────

def controler(conn, type_: str, en_tete: dict | None) -> dict:
    """État d'un fichier reçu au regard de la séquence (sans rien écrire) :
    {statut, message, numero, attendu, manquants}. Statuts : 'attendu',
    'deja_recu', 'manquants', 'autre_instance', 'sans_numero', 'meme_base',
    'refuse_sans_numero'."""
    migrer(conn)
    moi = instance(conn)
    role_emetteur = ROLE_EMETTEUR[type_]
    dernier = _dernier_recu(conn, type_)
    attendu = dernier + 1
    base = {"numero": None, "attendu": attendu, "manquants": [], "accuse": None}
    if not en_tete:
        if dernier:
            return {**base, "statut": "refuse_sans_numero",
                    "message": "Fichier sans numéro d'ordre (antérieur à la v0.51.7), alors "
                               "que la séquence numérotée a commencé : produisez un nouvel envoi."}
        return {**base, "statut": "sans_numero",
                "message": "Fichier sans numéro d'ordre (antérieur à la v0.51.7) : accepté "
                           "tant que la séquence numérotée n'a pas commencé."}
    em = en_tete.get("emetteur") or {}
    n = int(en_tete.get("numero") or 0)
    base.update(numero=n, accuse=en_tete.get("accuse"), emetteur=em)
    if en_tete.get("type") != type_ or em.get("role") != role_emetteur:
        return {**base, "statut": "autre_instance",
                "message": f"Ce fichier n'est pas un envoi « {type_} » d'un {role_emetteur}."}
    if em.get("id") == moi["id"]:
        return {**base, "statut": "meme_base",
                "message": "Envoi produit par cette même base (base partagée) : pas de "
                           "contrôle de séquence."}
    lie = correspondant(conn, role_emetteur)
    if lie and lie["id"] != em.get("id"):
        return {**base, "statut": "autre_instance",
                "message": f"Envoi de « {em.get('nom') or em.get('id')} », alors que cette "
                           f"base est liée à « {lie['nom'] or lie['id']} » : refusé."}
    dest = en_tete.get("destinataire")
    if dest and dest != moi["id"]:
        return {**base, "statut": "autre_instance",
                "message": "Cet envoi est destiné à une autre instance : refusé."}
    if n < attendu:
        return {**base, "statut": "deja_recu",
                "message": f"Envoi n° {n} déjà reçu (on attend le n° {attendu}) : ignoré."}
    if n > attendu:
        manquants = list(range(attendu, n))
        return {**base, "statut": "manquants", "manquants": manquants,
                "message": f"Envoi n° {n} reçu, mais il manque "
                           f"{'le n° ' if len(manquants) == 1 else 'les n° '}"
                           f"{', '.join(map(str, manquants))} : demandez-"
                           f"{'le' if len(manquants) == 1 else 'les'} (« Renvoyer ») "
                           f"et importez-{'le' if len(manquants) == 1 else 'les'} d'abord."}
    return {**base, "statut": "attendu", "message": f"Envoi n° {n}, attendu."}


ACCEPTES = ("attendu", "sans_numero", "meme_base")


def enregistrer_reception(conn, type_: str, en_tete: dict | None, nom_fichier: str) -> None:
    """Après traitement d'un fichier accepté : lie l'émetteur, inscrit le
    numéro reçu."""
    migrer(conn)
    em = (en_tete or {}).get("emetteur") or {}
    moi = instance(conn)
    if em.get("id") and em["id"] != moi["id"]:
        _lier(conn, ROLE_EMETTEUR[type_], em)
    numero = int((en_tete or {}).get("numero") or 0) if em.get("id") != moi["id"] else 0
    conn.execute("INSERT INTO echanges_recus (type, numero, emetteur, nom_fichier, recu_le) "
                 "VALUES (?,?,?,?,?)", (type_, numero, em.get("id") or "", nom_fichier,
                                        _maintenant()))


def recus(conn, type_: str, limite: int = 30) -> list[dict]:
    migrer(conn)
    return [dict(r) for r in conn.execute(
        "SELECT * FROM echanges_recus WHERE type=? ORDER BY recu_le DESC, rowid DESC LIMIT ?",
        (type_, limite)).fetchall()]


def etat(conn) -> dict:
    """Identité, correspondants, derniers envois et réceptions."""
    return {"instance": instance(conn),
            "correspondants": {r: correspondant(conn, r) for r in ("atelier", "classe")},
            "envois": {t: envois(conn, t, 10) for t in TYPES},
            "recus": {t: recus(conn, t, 10) for t in TYPES},
            "prochain": {t: prochain_numero(conn, t) for t in TYPES},
            # v0.51.10 — Un envoi de cette même base a été reçu : atelier et
            # appli en ligne partagent la base (pas de vrai échange).
            "base_partagee": conn.execute(
                "SELECT 1 FROM echanges_recus WHERE emetteur=? LIMIT 1",
                (instance(conn)["id"],)).fetchone() is not None,
            "attendu": {t: _dernier_recu(conn, t) + 1 for t in TYPES}}
