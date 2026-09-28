"""services/referentiel_externe.py — v0.25.0

Référentiels externes : conçus hors de l'appli (docs de collègues), intégrés
tels quels. Structure séquences → parties (avec nb de séances) → documents.

Type 'mer' pour l'instant (les référentiels MER sont exclusivement externes).
États : 'en_cours' (éditable) et 'valide' (utilisable en progression). Des
documents peuvent être ajoutés à tout moment, même après validation.

Les fichiers sont stockés sous data/referentiels_externes/<ref_id>/ ; la base
garde le nom d'origine, le chemin relatif, le type MIME et la taille. C'est
l'enseignant qui nomme correctement ses documents.
"""

from __future__ import annotations
import uuid
from pathlib import Path

TYPES = ("principal", "mer")
ETATS = ("en_cours", "valide")

# Formats affichables en ligne (dans le navigateur). Les autres sont proposés
# au téléchargement.
MIMES_AFFICHABLES = ("application/pdf",)


class RefExterneErreur(Exception):
    def __init__(self, message: str, code: str = "erreur", **details):
        super().__init__(message)
        self.code = code
        self.details = details


class DonneesInvalides(RefExterneErreur):
    def __init__(self, message):
        super().__init__(message, "donnees_invalides")


class Introuvable(RefExterneErreur):
    def __init__(self, quoi, id_):
        super().__init__(f"{quoi} {id_!r} introuvable.", "introuvable", id=id_)


def _rid(prefixe: str) -> str:
    return f"{prefixe}_" + uuid.uuid4().hex[:12]


# ── Référentiel ──────────────────────────────────────────────────────────────

def lister(conn, niveau: str | None = None, annee: str | None = None,
           type: str | None = None) -> list:
    q = "SELECT * FROM referentiel_externe WHERE 1=1"
    p: list = []
    if niveau:
        q += " AND niveau=?"; p.append(niveau)
    if annee:
        q += " AND annee=?"; p.append(annee)
    if type:
        q += " AND type=?"; p.append(type)
    q += " ORDER BY annee DESC, nom"
    return [dict(r) for r in conn.execute(q, p).fetchall()]


def creer(conn, *, niveau: str, annee: str = "", type: str = "mer",
          nom: str = "") -> dict:
    if type not in TYPES:
        raise DonneesInvalides(f"Type invalide : {type!r}.")
    if not (niveau or "").strip():
        raise DonneesInvalides("Le niveau est obligatoire.")
    rid = _rid("rxt")
    conn.execute(
        "INSERT INTO referentiel_externe (id, niveau, annee, type, nom, etat) "
        "VALUES (?,?,?,?,?, 'en_cours')",
        (rid, niveau, annee, type, (nom or "").strip()))
    return lire(conn, rid)


def lire(conn, ref_id: str) -> dict:
    r = conn.execute("SELECT * FROM referentiel_externe WHERE id=?",
                     (ref_id,)).fetchone()
    if r is None:
        raise Introuvable("Référentiel externe", ref_id)
    d = dict(r)
    d["sequences"] = _lister_sequences(conn, ref_id)
    d["docs_annuels"] = lister_docs_annuels(conn, ref_id)
    return d


def modifier(conn, ref_id: str, champs: dict) -> dict:
    r = conn.execute("SELECT * FROM referentiel_externe WHERE id=?",
                     (ref_id,)).fetchone()
    if r is None:
        raise Introuvable("Référentiel externe", ref_id)
    c = dict(r)
    for k in ("niveau", "annee", "nom"):
        if k in champs:
            c[k] = champs[k]
    conn.execute(
        "UPDATE referentiel_externe SET niveau=?, annee=?, nom=? WHERE id=?",
        (c["niveau"], c["annee"], (c["nom"] or "").strip(), ref_id))
    return lire(conn, ref_id)


def changer_etat(conn, ref_id: str, etat: str) -> dict:
    if etat not in ETATS:
        raise DonneesInvalides(f"État invalide : {etat!r} (attendu {ETATS}).")
    r = conn.execute("SELECT 1 FROM referentiel_externe WHERE id=?",
                     (ref_id,)).fetchone()
    if r is None:
        raise Introuvable("Référentiel externe", ref_id)
    conn.execute("UPDATE referentiel_externe SET etat=? WHERE id=?",
                 (etat, ref_id))
    return lire(conn, ref_id)


def supprimer(conn, ref_id: str, data_dir: Path | None = None) -> None:
    r = conn.execute("SELECT 1 FROM referentiel_externe WHERE id=?",
                     (ref_id,)).fetchone()
    if r is None:
        raise Introuvable("Référentiel externe", ref_id)
    # Supprimer docs (fichiers + base), parties, séquences, puis le référentiel.
    for seq in _lister_sequences(conn, ref_id):
        for part in seq["parties"]:
            for doc in part["docs"]:
                _supprimer_fichier(doc, data_dir)
    # v0.32.3 — docs annuels (fichiers) rattachés au référentiel.
    for doc in lister_docs_annuels(conn, ref_id):
        _supprimer_fichier(doc, data_dir)
    conn.execute("DELETE FROM referentiel_externe_doc WHERE ref_ext_id=?",
                 (ref_id,))
    conn.execute(
        "DELETE FROM referentiel_externe_doc WHERE partie_id IN "
        "(SELECT p.id FROM referentiel_externe_partie p "
        " JOIN referentiel_externe_sequence s ON s.id=p.sequence_id "
        " WHERE s.ref_ext_id=?)", (ref_id,))
    conn.execute(
        "DELETE FROM referentiel_externe_partie WHERE sequence_id IN "
        "(SELECT id FROM referentiel_externe_sequence WHERE ref_ext_id=?)",
        (ref_id,))
    conn.execute("DELETE FROM referentiel_externe_sequence WHERE ref_ext_id=?",
                 (ref_id,))
    conn.execute("DELETE FROM referentiel_externe WHERE id=?", (ref_id,))
    if data_dir:
        dossier = Path(data_dir) / "referentiels_externes" / ref_id
        if dossier.exists():
            try:
                for f in dossier.iterdir():
                    f.unlink()
                dossier.rmdir()
            except OSError:
                pass


# ── Séquences ────────────────────────────────────────────────────────────────

def _lister_sequences(conn, ref_id: str) -> list:
    rows = conn.execute(
        "SELECT * FROM referentiel_externe_sequence WHERE ref_ext_id=? "
        "ORDER BY ordre, code", (ref_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["parties"] = _lister_parties(conn, d["id"])
        out.append(d)
    return out


def ajouter_sequence(conn, ref_id: str, *, code: str = "", nom: str = "") -> dict:
    r = conn.execute("SELECT 1 FROM referentiel_externe WHERE id=?",
                     (ref_id,)).fetchone()
    if r is None:
        raise Introuvable("Référentiel externe", ref_id)
    ordre = (conn.execute(
        "SELECT COALESCE(MAX(ordre),0)+10 FROM referentiel_externe_sequence "
        "WHERE ref_ext_id=?", (ref_id,)).fetchone()[0])
    sid = _rid("rxs")
    conn.execute(
        "INSERT INTO referentiel_externe_sequence (id, ref_ext_id, code, nom, "
        "ordre) VALUES (?,?,?,?,?)",
        (sid, ref_id, (code or "").strip(), (nom or "").strip(), ordre))
    return dict(conn.execute(
        "SELECT * FROM referentiel_externe_sequence WHERE id=?",
        (sid,)).fetchone())


def modifier_sequence(conn, seq_id: str, champs: dict) -> dict:
    r = conn.execute("SELECT * FROM referentiel_externe_sequence WHERE id=?",
                     (seq_id,)).fetchone()
    if r is None:
        raise Introuvable("Séquence", seq_id)
    c = dict(r)
    for k in ("code", "nom"):
        if k in champs:
            c[k] = (champs[k] or "").strip()
    conn.execute(
        "UPDATE referentiel_externe_sequence SET code=?, nom=? WHERE id=?",
        (c["code"], c["nom"], seq_id))
    return dict(conn.execute(
        "SELECT * FROM referentiel_externe_sequence WHERE id=?",
        (seq_id,)).fetchone())


def deplacer_sequence(conn, seq_id: str, sens: int) -> list:
    """Monte (sens<0) ou descend (sens>0) une séquence en échangeant sa
    position avec le voisin. Renormalise les `ordre`. Retourne la liste
    réordonnée des séquences (avec parties)."""
    r = conn.execute("SELECT ref_ext_id FROM referentiel_externe_sequence "
                     "WHERE id=?", (seq_id,)).fetchone()
    if r is None:
        raise Introuvable("Séquence", seq_id)
    ref_id = r["ref_ext_id"]
    ids = [s["id"] for s in conn.execute(
        "SELECT id FROM referentiel_externe_sequence WHERE ref_ext_id=? "
        "ORDER BY ordre, code", (ref_id,)).fetchall()]
    i = ids.index(seq_id)
    j = i + (1 if sens > 0 else -1)
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
        for k, sid in enumerate(ids):
            conn.execute("UPDATE referentiel_externe_sequence SET ordre=? "
                         "WHERE id=?", ((k + 1) * 10, sid))
    return _lister_sequences(conn, ref_id)


def supprimer_sequence(conn, seq_id: str, data_dir: Path | None = None) -> None:
    r = conn.execute("SELECT 1 FROM referentiel_externe_sequence WHERE id=?",
                     (seq_id,)).fetchone()
    if r is None:
        raise Introuvable("Séquence", seq_id)
    for part in _lister_parties(conn, seq_id):
        for doc in part["docs"]:
            _supprimer_fichier(doc, data_dir)
    conn.execute(
        "DELETE FROM referentiel_externe_doc WHERE partie_id IN "
        "(SELECT id FROM referentiel_externe_partie WHERE sequence_id=?)",
        (seq_id,))
    conn.execute("DELETE FROM referentiel_externe_partie WHERE sequence_id=?",
                 (seq_id,))
    conn.execute("DELETE FROM referentiel_externe_sequence WHERE id=?",
                 (seq_id,))


# ── Parties ──────────────────────────────────────────────────────────────────

def _lister_parties(conn, seq_id: str) -> list:
    rows = conn.execute(
        "SELECT * FROM referentiel_externe_partie WHERE sequence_id=? "
        "ORDER BY ordre, numero", (seq_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["docs"] = _lister_docs(conn, d["id"])
        out.append(d)
    return out


def ajouter_partie(conn, seq_id: str, *, libelle: str = "",
                   nb_seances: int = 1) -> dict:
    r = conn.execute("SELECT 1 FROM referentiel_externe_sequence WHERE id=?",
                     (seq_id,)).fetchone()
    if r is None:
        raise Introuvable("Séquence", seq_id)
    try:
        nb = max(1, int(nb_seances))
    except (TypeError, ValueError):
        nb = 1
    numero = (conn.execute(
        "SELECT COALESCE(MAX(numero),0)+1 FROM referentiel_externe_partie "
        "WHERE sequence_id=?", (seq_id,)).fetchone()[0])
    ordre = numero * 10
    pid = _rid("rxp")
    conn.execute(
        "INSERT INTO referentiel_externe_partie (id, sequence_id, numero, "
        "libelle, nb_seances, ordre) VALUES (?,?,?,?,?,?)",
        (pid, seq_id, numero, (libelle or "").strip(), nb, ordre))
    return dict(conn.execute(
        "SELECT * FROM referentiel_externe_partie WHERE id=?",
        (pid,)).fetchone())


def modifier_partie(conn, partie_id: str, champs: dict) -> dict:
    r = conn.execute("SELECT * FROM referentiel_externe_partie WHERE id=?",
                     (partie_id,)).fetchone()
    if r is None:
        raise Introuvable("Partie", partie_id)
    c = dict(r)
    if "libelle" in champs:
        c["libelle"] = (champs["libelle"] or "").strip()
    if "nb_seances" in champs:
        try:
            c["nb_seances"] = max(1, int(champs["nb_seances"]))
        except (TypeError, ValueError):
            pass
    conn.execute(
        "UPDATE referentiel_externe_partie SET libelle=?, nb_seances=? "
        "WHERE id=?", (c["libelle"], c["nb_seances"], partie_id))
    return dict(conn.execute(
        "SELECT * FROM referentiel_externe_partie WHERE id=?",
        (partie_id,)).fetchone())


def deplacer_partie(conn, partie_id: str, sens: int) -> list:
    """Monte/descend une partie dans sa séquence. Renormalise `ordre` (et le
    numéro affiché suit l'ordre). Retourne la liste des parties de la séquence."""
    r = conn.execute("SELECT sequence_id FROM referentiel_externe_partie "
                     "WHERE id=?", (partie_id,)).fetchone()
    if r is None:
        raise Introuvable("Partie", partie_id)
    seq_id = r["sequence_id"]
    ids = [p["id"] for p in conn.execute(
        "SELECT id FROM referentiel_externe_partie WHERE sequence_id=? "
        "ORDER BY ordre, numero", (seq_id,)).fetchall()]
    i = ids.index(partie_id)
    j = i + (1 if sens > 0 else -1)
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
        # Renormaliser ordre ET numero pour que P1, P2… suivent l'ordre affiché.
        for k, pid in enumerate(ids):
            conn.execute("UPDATE referentiel_externe_partie SET ordre=?, "
                         "numero=? WHERE id=?", ((k + 1) * 10, k + 1, pid))
    return _lister_parties(conn, seq_id)


def supprimer_partie(conn, partie_id: str, data_dir: Path | None = None) -> None:
    r = conn.execute("SELECT 1 FROM referentiel_externe_partie WHERE id=?",
                     (partie_id,)).fetchone()
    if r is None:
        raise Introuvable("Partie", partie_id)
    for doc in _lister_docs(conn, partie_id):
        _supprimer_fichier(doc, data_dir)
    conn.execute("DELETE FROM referentiel_externe_doc WHERE partie_id=?",
                 (partie_id,))
    conn.execute("DELETE FROM referentiel_externe_partie WHERE id=?",
                 (partie_id,))


# ── Documents ────────────────────────────────────────────────────────────────

def _lister_docs(conn, partie_id: str) -> list:
    rows = conn.execute(
        "SELECT * FROM referentiel_externe_doc WHERE partie_id=? "
        "ORDER BY nom_fichier", (partie_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["affichable"] = d.get("mime") in MIMES_AFFICHABLES
        out.append(d)
    return out


def ajouter_doc(conn, partie_id: str, *, nom_fichier: str, contenu: bytes,
                mime: str, data_dir: Path) -> dict:
    """Enregistre un document : écrit le fichier sous
    data/referentiels_externes/<ref_id>/<doc_id>_<nom>, et l'enregistre en base.
    """
    r = conn.execute(
        "SELECT p.id, s.ref_ext_id AS ref FROM referentiel_externe_partie p "
        "JOIN referentiel_externe_sequence s ON s.id=p.sequence_id "
        "WHERE p.id=?", (partie_id,)).fetchone()
    if r is None:
        raise Introuvable("Partie", partie_id)
    ref_id = r["ref"]
    nom = (nom_fichier or "document").strip().replace("/", "_").replace("\\", "_")
    did = _rid("rxd")
    dossier = Path(data_dir) / "referentiels_externes" / ref_id
    dossier.mkdir(parents=True, exist_ok=True)
    chemin_abs = dossier / f"{did}_{nom}"
    chemin_abs.write_bytes(contenu)
    chemin_rel = f"referentiels_externes/{ref_id}/{did}_{nom}"
    conn.execute(
        "INSERT INTO referentiel_externe_doc (id, partie_id, nom_fichier, "
        "chemin, mime, taille) VALUES (?,?,?,?,?,?)",
        (did, partie_id, nom, chemin_rel, mime or "", len(contenu)))
    d = dict(conn.execute(
        "SELECT * FROM referentiel_externe_doc WHERE id=?", (did,)).fetchone())
    d["affichable"] = d.get("mime") in MIMES_AFFICHABLES
    return d


def lister_docs_annuels(conn, ref_id: str) -> list:
    """v0.32.3 — Documents ANNUELS d'un référentiel externe (rattachés au
    référentiel, pas à une partie)."""
    rows = conn.execute(
        "SELECT * FROM referentiel_externe_doc WHERE ref_ext_id=? "
        "ORDER BY nom_fichier", (ref_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["affichable"] = d.get("mime") in MIMES_AFFICHABLES
        out.append(d)
    return out


def ajouter_doc_annuel(conn, ref_id: str, *, nom_fichier: str, contenu: bytes,
                       mime: str, data_dir: Path) -> dict:
    """Enregistre un document ANNUEL rattaché au référentiel externe."""
    r = conn.execute("SELECT 1 FROM referentiel_externe WHERE id=?",
                     (ref_id,)).fetchone()
    if r is None:
        raise Introuvable("Référentiel externe", ref_id)
    nom = (nom_fichier or "document").strip().replace("/", "_").replace("\\", "_")
    did = _rid("rxd")
    dossier = Path(data_dir) / "referentiels_externes" / ref_id
    dossier.mkdir(parents=True, exist_ok=True)
    chemin_abs = dossier / f"{did}_{nom}"
    chemin_abs.write_bytes(contenu)
    chemin_rel = f"referentiels_externes/{ref_id}/{did}_{nom}"
    conn.execute(
        "INSERT INTO referentiel_externe_doc (id, partie_id, ref_ext_id, "
        "nom_fichier, chemin, mime, taille) VALUES (?,?,?,?,?,?,?)",
        (did, "", ref_id, nom, chemin_rel, mime or "", len(contenu)))
    d = dict(conn.execute(
        "SELECT * FROM referentiel_externe_doc WHERE id=?", (did,)).fetchone())
    d["affichable"] = d.get("mime") in MIMES_AFFICHABLES
    return d


def lire_doc(conn, doc_id: str) -> dict:
    r = conn.execute("SELECT * FROM referentiel_externe_doc WHERE id=?",
                     (doc_id,)).fetchone()
    if r is None:
        raise Introuvable("Document", doc_id)
    return dict(r)


def supprimer_doc(conn, doc_id: str, data_dir: Path | None = None) -> None:
    doc = conn.execute("SELECT * FROM referentiel_externe_doc WHERE id=?",
                       (doc_id,)).fetchone()
    if doc is None:
        raise Introuvable("Document", doc_id)
    _supprimer_fichier(dict(doc), data_dir)
    conn.execute("DELETE FROM referentiel_externe_doc WHERE id=?", (doc_id,))


def _supprimer_fichier(doc: dict, data_dir: Path | None) -> None:
    if not data_dir:
        return
    chemin = doc.get("chemin")
    if not chemin:
        return
    f = Path(data_dir) / chemin
    if f.exists():
        try:
            f.unlink()
        except OSError:
            pass
