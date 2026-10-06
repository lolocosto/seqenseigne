"""services/referentiel_principal_externe.py — v0.48.2

Référentiel PRINCIPAL EXTERNE : même structure qu'un référentiel interne figé
(tables `referentiel_niveaux`, `referentiel_sequences`, `referentiel_parties`,
`referentiel_objectifs`), avec `source = 'externe'` ; seuls les documents
diffèrent : ce sont des FICHIERS déposés (tous formats ; les PDF s'affichent
dans l'appli, les autres se téléchargent), rattachés à une séquence ou à une
partie (`referentiel_fichiers`).

Conséquence : progression principale, début de séance, travail et compétences
l'utilisent sans rien savoir de sa source.

Règles (validées) :
  - nom calculé : niveau, année scolaire, « Principal », plus une lettre si
    plusieurs (b, c…) ; description libre facultative (ex. « Manuel X ») ;
  - utilisable dès sa création, même incomplet (pas de figeage intégral) ;
  - ajouts toujours possibles (séquences, parties, objectifs, fichiers) ;
  - une séquence COMMENCÉE (un créneau d'une progression qui utilise ce
    référentiel a démarré : date de début ≤ aujourd'hui) ne se modifie plus
    et ne se supprime plus — seuls restent la correction des libellés et
    l'ajout de fichiers ;
  - objectifs numérotés automatiquement (01, 02…) dans la séquence,
    renumérotés au réordonnancement ;
  - les codes de séquence (S01, S02…) sont attribués à la création et ne
    changent jamais (les créneaux de progression s'y réfèrent).
"""

from __future__ import annotations
import uuid
from datetime import date
from pathlib import Path

MIMES_AFFICHABLES = ("application/pdf",)
NIVEAUX = {"N09": "6e", "N10": "5e", "N11": "4e", "N12": "3e"}

SCHEMA_FICHIERS = """
CREATE TABLE IF NOT EXISTS referentiel_fichiers (
    id             TEXT PRIMARY KEY,
    referentiel_id TEXT NOT NULL,
    seq_code       TEXT NOT NULL,
    partie_numero  INTEGER NOT NULL DEFAULT 0,     -- 0 = rattaché à la séquence
    nom_fichier    TEXT NOT NULL,
    chemin         TEXT NOT NULL,
    mime           TEXT NOT NULL DEFAULT '',
    taille         INTEGER NOT NULL DEFAULT 0,
    ordre          INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ref_fichiers ON referentiel_fichiers (referentiel_id, seq_code);
-- v0.48.3 — Types de documents (liste extensible dans Système › Préférences)
CREATE TABLE IF NOT EXISTS types_documents (
    id      TEXT PRIMARY KEY,
    libelle TEXT NOT NULL,
    ordre   INTEGER NOT NULL DEFAULT 0,
    actif   INTEGER NOT NULL DEFAULT 1
);
"""

TYPES_DEFAUT = ("Livret d'exercices", "Livret de séquence", "Livret de cours",
                "Évaluation", "Travail personnel", "Activité complémentaire")


def migrer(conn) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_niveaux)")}
    for nom, decl in (("source", "TEXT NOT NULL DEFAULT 'interne'"),
                      ("type_ref", "TEXT NOT NULL DEFAULT 'principal'"),
                      ("annee", "TEXT NOT NULL DEFAULT ''")):
        if cols and nom not in cols:
            conn.execute(f"ALTER TABLE referentiel_niveaux ADD COLUMN {nom} {decl}")
    conn.executescript(SCHEMA_FICHIERS)
    # v0.48.3 — type d'un fichier ; types par défaut.
    cols_f = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_fichiers)")}
    if "type_id" not in cols_f:
        conn.execute("ALTER TABLE referentiel_fichiers ADD COLUMN type_id TEXT NOT NULL DEFAULT ''")
    if conn.execute("SELECT COUNT(*) FROM types_documents").fetchone()[0] == 0:
        for i, lib in enumerate(TYPES_DEFAUT, start=1):
            conn.execute("INSERT INTO types_documents (id, libelle, ordre) VALUES (?,?,?)",
                         (_id("tdoc_"), lib, i * 10))


class RefExtErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides"):
        super().__init__(message)
        self.code = code


def _id(p: str) -> str:
    return p + uuid.uuid4().hex[:12]


# ── Référentiel ──────────────────────────────────────────────────────────────

def nom_calcule(r: dict) -> str:
    lettre = (r.get("version") or "")[5:]           # 'X2026b' → 'b'
    niv = NIVEAUX.get(r["niveau"], r["niveau"])
    return f"{niv} — {r.get('annee') or ''} — Principal{(' ' + lettre) if lettre else ''}"


def _lire_ref(conn, rid: str) -> dict:
    r = conn.execute("SELECT * FROM referentiel_niveaux WHERE id=? AND source='externe'",
                     (rid,)).fetchone()
    if r is None:
        raise RefExtErreur("Référentiel externe introuvable.", "introuvable")
    return dict(r)


def lister(conn, niveau: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM referentiel_niveaux WHERE source='externe' AND "
                        "type_ref='principal' AND niveau=? AND etat<>'annule' "
                        "ORDER BY annee DESC, version", (niveau,)).fetchall()
    return [{**dict(r), "nom": nom_calcule(dict(r))} for r in rows]


def creer(conn, niveau: str, annee: str, description: str = "") -> dict:
    if niveau not in NIVEAUX:
        raise RefExtErreur(f"Niveau invalide : {niveau!r}.")
    if not annee or len(annee) != 9:
        raise RefExtErreur("Année scolaire invalide (AAAA-AAAA).")
    base = "X" + annee[:4]
    pris = {r["version"] for r in conn.execute(
        "SELECT version FROM referentiel_niveaux WHERE niveau=? AND version LIKE ?",
        (niveau, base + "%")).fetchall()}
    lettre = ""
    if base in pris:
        lettre = next(c for c in "bcdefghijklmnopqrstuvwxyz" if base + c not in pris)
    version = base + lettre
    rid = f"{base}_{niveau}{lettre}"      # convention interne : <annee>_<niveau><suffixe>
    conn.execute("INSERT INTO referentiel_niveaux (id, niveau, version, description, etat, "
                 "source, type_ref, annee) VALUES (?,?,?,?, 'en_cours', 'externe', "
                 "'principal', ?)", (rid, niveau, version, (description or "").strip(), annee))
    return lire(conn, rid)


def modifier(conn, rid: str, description: str) -> dict:
    _lire_ref(conn, rid)
    conn.execute("UPDATE referentiel_niveaux SET description=? WHERE id=?",
                 ((description or "").strip(), rid))
    return lire(conn, rid)


def est_utilise(conn, rid: str) -> bool:
    return conn.execute("SELECT 1 FROM progressions WHERE referentiel_id=? LIMIT 1",
                        (rid,)).fetchone() is not None


def supprimer(conn, rid: str, data_dir: Path | None = None) -> None:
    _lire_ref(conn, rid)
    if est_utilise(conn, rid):
        raise RefExtErreur("Ce référentiel est utilisé par une progression : "
                           "il ne peut pas être supprimé.")
    for f in conn.execute("SELECT chemin FROM referentiel_fichiers WHERE referentiel_id=?",
                          (rid,)).fetchall():
        if data_dir:
            try:
                (Path(data_dir) / f["chemin"]).unlink()
            except OSError:
                pass
    for t in ("referentiel_fichiers", "referentiel_objectifs", "referentiel_parties",
              "referentiel_sequences"):
        conn.execute(f"DELETE FROM {t} WHERE referentiel_id=?", (rid,))
    conn.execute("DELETE FROM referentiel_niveaux WHERE id=?", (rid,))


# ── Séquence commencée ───────────────────────────────────────────────────────

def sequence_commencee(conn, rid: str, seq_code: str, aujourd_hui: date) -> bool:
    """Vrai si un créneau d'une progression utilisant ce référentiel, sur
    cette séquence, a une date de début passée (ou aujourd'hui)."""
    r = conn.execute(
        "SELECT 1 FROM creneaux c JOIN progressions p ON p.id=c.progression_id "
        "WHERE p.referentiel_id=? AND c.seq_code=? AND c.date_debut IS NOT NULL "
        "AND c.date_debut<>'' AND c.date_debut<=? LIMIT 1",
        (rid, seq_code, aujourd_hui.isoformat())).fetchone()
    return r is not None


def _verifier_modifiable(conn, rid, seq_code, aujourd_hui):
    if sequence_commencee(conn, rid, seq_code, aujourd_hui):
        raise RefExtErreur(f"La séquence {seq_code} a commencé : sa structure ne se "
                           "modifie plus (seuls les libellés et l'ajout de fichiers "
                           "restent possibles).", "sequence_commencee")


# ── Lecture complète ─────────────────────────────────────────────────────────

def lire(conn, rid: str, aujourd_hui: date | None = None) -> dict:
    aujourd_hui = aujourd_hui or date.today()
    ref = _lire_ref(conn, rid)
    seqs = []
    for s in conn.execute("SELECT * FROM referentiel_sequences WHERE referentiel_id=? "
                          "ORDER BY numero", (rid,)).fetchall():
        s = dict(s)
        parties = []
        for p in conn.execute("SELECT * FROM referentiel_parties WHERE referentiel_id=? "
                              "AND seq_code=? ORDER BY numero", (rid, s["code"])).fetchall():
            p = dict(p)
            p["objectifs"] = [dict(o) for o in conn.execute(
                "SELECT * FROM referentiel_objectifs WHERE referentiel_id=? AND seq_code=? "
                "AND partie_numero=? ORDER BY code", (rid, s["code"], p["numero"])).fetchall()]
            p["fichiers"] = _fichiers(conn, rid, s["code"], p["numero"])
            parties.append(p)
        s["parties"] = parties
        s["fichiers"] = _fichiers(conn, rid, s["code"], 0)
        s["commencee"] = sequence_commencee(conn, rid, s["code"], aujourd_hui)
        seqs.append(s)
    return {**ref, "nom": nom_calcule(ref), "utilise": est_utilise(conn, rid),
            "sequences": seqs}


def _fichiers(conn, rid, seq_code, partie_numero) -> list[dict]:
    return [{**dict(f), "affichable": f["mime"] in MIMES_AFFICHABLES} for f in conn.execute(
        "SELECT f.*, COALESCE(t.libelle, '') AS type_libelle FROM referentiel_fichiers f "
        "LEFT JOIN types_documents t ON t.id=f.type_id WHERE f.referentiel_id=? AND "
        "f.seq_code=? AND f.partie_numero=? ORDER BY f.ordre, f.nom_fichier",
        (rid, seq_code, partie_numero)).fetchall()]


# ── v0.48.3 — Types de documents ─────────────────────────────────────────────

def lister_types(conn, tout: bool = False) -> list[dict]:
    q = "SELECT * FROM types_documents" + ("" if tout else " WHERE actif=1") + \
        " ORDER BY ordre, libelle"
    return [{**dict(r), "actif": bool(r["actif"])} for r in conn.execute(q).fetchall()]


def ajouter_type(conn, libelle: str) -> dict:
    lib = (libelle or "").strip()
    if not lib:
        raise RefExtErreur("Libellé obligatoire.")
    if any(t["libelle"].casefold() == lib.casefold() for t in lister_types(conn, True)):
        raise RefExtErreur(f"Le type « {lib} » existe déjà.")
    n = conn.execute("SELECT COALESCE(MAX(ordre), 0) FROM types_documents").fetchone()[0]
    tid = _id("tdoc_")
    conn.execute("INSERT INTO types_documents (id, libelle, ordre) VALUES (?,?,?)",
                 (tid, lib, n + 10))
    return dict(conn.execute("SELECT * FROM types_documents WHERE id=?", (tid,)).fetchone())


def modifier_type(conn, tid: str, champs: dict) -> None:
    r = conn.execute("SELECT * FROM types_documents WHERE id=?", (tid,)).fetchone()
    if r is None:
        raise RefExtErreur("Type introuvable.", "introuvable")
    lib = (champs.get("libelle", r["libelle"]) or "").strip()
    if not lib:
        raise RefExtErreur("Libellé obligatoire.")
    conn.execute("UPDATE types_documents SET libelle=?, actif=? WHERE id=?",
                 (lib, 1 if champs.get("actif", bool(r["actif"])) else 0, tid))


def deplacer_type(conn, tid: str, sens: int) -> None:
    ids = [t["id"] for t in lister_types(conn, True)]
    if tid not in ids:
        raise RefExtErreur("Type introuvable.", "introuvable")
    i = ids.index(tid)
    j = i + (1 if sens > 0 else -1)
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
        for k, x in enumerate(ids, start=1):
            conn.execute("UPDATE types_documents SET ordre=? WHERE id=?", (k * 10, x))


def typer_fichier(conn, fid: str, type_id: str) -> dict:
    """Le type se modifie toujours (classement, même séquence commencée)."""
    lire_fichier(conn, fid)
    if type_id and conn.execute("SELECT 1 FROM types_documents WHERE id=?",
                                (type_id,)).fetchone() is None:
        raise RefExtErreur("Type inconnu.")
    conn.execute("UPDATE referentiel_fichiers SET type_id=? WHERE id=?", (type_id or "", fid))
    return lire_fichier(conn, fid)


# ── Séquences ────────────────────────────────────────────────────────────────

def ajouter_sequence(conn, rid: str, nom: str) -> dict:
    _lire_ref(conn, rid)
    nom = (nom or "").strip()
    if not nom:
        raise RefExtErreur("Le nom de la séquence est obligatoire.")
    codes = [r["code"] for r in conn.execute(
        "SELECT code FROM referentiel_sequences WHERE referentiel_id=?", (rid,)).fetchall()]
    nums = [int(c[1:]) for c in codes if c[:1] == "S" and c[1:].isdigit()]
    code = f"S{(max(nums) + 1) if nums else 1:02d}"
    numero = (conn.execute("SELECT COALESCE(MAX(numero), 0) FROM referentiel_sequences "
                           "WHERE referentiel_id=?", (rid,)).fetchone()[0]) + 1
    conn.execute("INSERT INTO referentiel_sequences (referentiel_id, code, numero, nom) "
                 "VALUES (?,?,?,?)", (rid, code, numero, nom))
    return {"code": code, "numero": numero, "nom": nom}


def modifier_sequence(conn, rid: str, code: str, nom: str) -> None:
    """Correction du nom : toujours permise."""
    nom = (nom or "").strip()
    if not nom:
        raise RefExtErreur("Le nom de la séquence est obligatoire.")
    n = conn.execute("UPDATE referentiel_sequences SET nom=? WHERE referentiel_id=? AND "
                     "code=?", (nom, rid, code)).rowcount
    if not n:
        raise RefExtErreur("Séquence introuvable.", "introuvable")


def deplacer_sequence(conn, rid: str, code: str, sens: int, aujourd_hui: date) -> None:
    rows = [dict(r) for r in conn.execute(
        "SELECT code, numero FROM referentiel_sequences WHERE referentiel_id=? "
        "ORDER BY numero", (rid,)).fetchall()]
    codes = [r["code"] for r in rows]
    if code not in codes:
        raise RefExtErreur("Séquence introuvable.", "introuvable")
    i = codes.index(code)
    j = i + (1 if sens > 0 else -1)
    if not 0 <= j < len(codes):
        return
    for c in (codes[i], codes[j]):
        _verifier_modifiable(conn, rid, c, aujourd_hui)
    codes[i], codes[j] = codes[j], codes[i]
    for k, c in enumerate(codes, start=1):
        conn.execute("UPDATE referentiel_sequences SET numero=? WHERE referentiel_id=? AND "
                     "code=?", (k, rid, c))


def supprimer_sequence(conn, rid: str, code: str, aujourd_hui: date,
                       data_dir: Path | None = None) -> None:
    _verifier_modifiable(conn, rid, code, aujourd_hui)
    if conn.execute("SELECT 1 FROM creneaux c JOIN progressions p ON p.id=c.progression_id "
                    "WHERE p.referentiel_id=? AND c.seq_code=? LIMIT 1",
                    (rid, code)).fetchone():
        raise RefExtErreur(f"La séquence {code} est placée dans une progression : "
                           "retirez d'abord ses créneaux.")
    for f in conn.execute("SELECT id FROM referentiel_fichiers WHERE referentiel_id=? AND "
                          "seq_code=?", (rid, code)).fetchall():
        supprimer_fichier(conn, f["id"], data_dir)
    for t in ("referentiel_objectifs", "referentiel_parties"):
        conn.execute(f"DELETE FROM {t} WHERE referentiel_id=? AND seq_code=?", (rid, code))
    conn.execute("DELETE FROM referentiel_sequences WHERE referentiel_id=? AND code=?",
                 (rid, code))
    _renumeroter_sequences(conn, rid)


def _renumeroter_sequences(conn, rid):
    for k, r in enumerate(conn.execute(
            "SELECT code FROM referentiel_sequences WHERE referentiel_id=? ORDER BY numero",
            (rid,)).fetchall(), start=1):
        conn.execute("UPDATE referentiel_sequences SET numero=? WHERE referentiel_id=? AND "
                     "code=?", (k, rid, r["code"]))


# ── Parties ──────────────────────────────────────────────────────────────────

def _nb(v, nom="nombre de séances") -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise RefExtErreur(f"{nom.capitalize()} invalide : {v!r}.")
    if f < 0:
        raise RefExtErreur(f"{nom.capitalize()} négatif.")
    return f


def ajouter_partie(conn, rid: str, code: str, nb_seances, aujourd_hui: date) -> dict:
    _verifier_modifiable(conn, rid, code, aujourd_hui)
    if conn.execute("SELECT 1 FROM referentiel_sequences WHERE referentiel_id=? AND code=?",
                    (rid, code)).fetchone() is None:
        raise RefExtErreur("Séquence introuvable.", "introuvable")
    n = (conn.execute("SELECT COALESCE(MAX(numero), 0) FROM referentiel_parties WHERE "
                      "referentiel_id=? AND seq_code=?", (rid, code)).fetchone()[0]) + 1
    conn.execute("INSERT INTO referentiel_parties (referentiel_id, seq_code, numero, "
                 "nb_seances_R_AE) VALUES (?,?,?,?)", (rid, code, n, _nb(nb_seances)))
    return {"seq_code": code, "numero": n}


def modifier_partie(conn, rid: str, code: str, numero: int, nb_seances,
                    aujourd_hui: date) -> None:
    _verifier_modifiable(conn, rid, code, aujourd_hui)
    conn.execute("UPDATE referentiel_parties SET nb_seances_R_AE=? WHERE referentiel_id=? "
                 "AND seq_code=? AND numero=?", (_nb(nb_seances), rid, code, int(numero)))


def supprimer_partie(conn, rid: str, code: str, numero: int, aujourd_hui: date,
                     data_dir: Path | None = None) -> None:
    _verifier_modifiable(conn, rid, code, aujourd_hui)
    numero = int(numero)
    for f in conn.execute("SELECT id FROM referentiel_fichiers WHERE referentiel_id=? AND "
                          "seq_code=? AND partie_numero=?", (rid, code, numero)).fetchall():
        supprimer_fichier(conn, f["id"], data_dir)
    conn.execute("DELETE FROM referentiel_objectifs WHERE referentiel_id=? AND seq_code=? "
                 "AND partie_numero=?", (rid, code, numero))
    conn.execute("DELETE FROM referentiel_parties WHERE referentiel_id=? AND seq_code=? AND "
                 "numero=?", (rid, code, numero))
    # Renuméroter les parties suivantes (et leurs objectifs, fichiers).
    for p in conn.execute("SELECT numero FROM referentiel_parties WHERE referentiel_id=? AND "
                          "seq_code=? AND numero>? ORDER BY numero", (rid, code, numero)).fetchall():
        _changer_numero_partie(conn, rid, code, p["numero"], p["numero"] - 1)
    _renumeroter_objectifs(conn, rid, code)


def _changer_numero_partie(conn, rid, code, ancien, nouveau):
    conn.execute("UPDATE referentiel_parties SET numero=? WHERE referentiel_id=? AND "
                 "seq_code=? AND numero=?", (nouveau, rid, code, ancien))
    conn.execute("UPDATE referentiel_objectifs SET partie_numero=? WHERE referentiel_id=? "
                 "AND seq_code=? AND partie_numero=?", (nouveau, rid, code, ancien))
    conn.execute("UPDATE referentiel_fichiers SET partie_numero=? WHERE referentiel_id=? "
                 "AND seq_code=? AND partie_numero=?", (nouveau, rid, code, ancien))


def deplacer_partie(conn, rid: str, code: str, numero: int, sens: int,
                    aujourd_hui: date) -> None:
    _verifier_modifiable(conn, rid, code, aujourd_hui)
    numero = int(numero)
    autre = numero + (1 if sens > 0 else -1)
    if conn.execute("SELECT 1 FROM referentiel_parties WHERE referentiel_id=? AND seq_code=? "
                    "AND numero=?", (rid, code, autre)).fetchone() is None:
        return
    _changer_numero_partie(conn, rid, code, numero, -1)
    _changer_numero_partie(conn, rid, code, autre, numero)
    _changer_numero_partie(conn, rid, code, -1, autre)
    _renumeroter_objectifs(conn, rid, code)


# ── Objectifs ────────────────────────────────────────────────────────────────

def _renumeroter_objectifs(conn, rid, code):
    """Codes 01, 02… dans l'ordre (partie, code actuel). Deux passes pour
    éviter les collisions de clé primaire."""
    rows = [dict(r) for r in conn.execute(
        "SELECT code FROM referentiel_objectifs WHERE referentiel_id=? AND seq_code=? "
        "ORDER BY partie_numero, code", (rid, code)).fetchall()]
    for k, r in enumerate(rows, start=1):
        conn.execute("UPDATE referentiel_objectifs SET code=? WHERE referentiel_id=? AND "
                     "seq_code=? AND code=?", (f"~{k:02d}", rid, code, r["code"]))
    for k in range(1, len(rows) + 1):
        conn.execute("UPDATE referentiel_objectifs SET code=? WHERE referentiel_id=? AND "
                     "seq_code=? AND code=?", (f"{k:02d}", rid, code, f"~{k:02d}"))


def ajouter_objectif(conn, rid: str, code: str, partie_numero: int, nom: str,
                     nb_seances=0, aujourd_hui: date | None = None) -> None:
    _verifier_modifiable(conn, rid, code, aujourd_hui or date.today())
    nom = (nom or "").strip()
    if not nom:
        raise RefExtErreur("Le nom de l'objectif est obligatoire.")
    if conn.execute("SELECT 1 FROM referentiel_parties WHERE referentiel_id=? AND seq_code=? "
                    "AND numero=?", (rid, code, int(partie_numero))).fetchone() is None:
        raise RefExtErreur("Partie introuvable.", "introuvable")
    # Code provisoire en fin de partie, puis renumérotation globale.
    der = conn.execute("SELECT MAX(code) FROM referentiel_objectifs WHERE referentiel_id=? "
                       "AND seq_code=? AND partie_numero=?",
                       (rid, code, int(partie_numero))).fetchone()[0]
    prov = (der or f"{int(partie_numero):02d}") + "z"
    conn.execute("INSERT INTO referentiel_objectifs (referentiel_id, seq_code, code, nom, "
                 "partie_numero, nb_seances) VALUES (?,?,?,?,?,?)",
                 (rid, code, prov, nom, int(partie_numero), _nb(nb_seances)))
    _renumeroter_objectifs(conn, rid, code)


def modifier_objectif(conn, rid: str, code: str, obj_code: str, champs: dict,
                      aujourd_hui: date) -> None:
    """Le nom et les critères se corrigent toujours (libellés) ; le nombre de
    séances seulement si la séquence n'a pas commencé."""
    r = conn.execute("SELECT * FROM referentiel_objectifs WHERE referentiel_id=? AND "
                     "seq_code=? AND code=?", (rid, code, obj_code)).fetchone()
    if r is None:
        raise RefExtErreur("Objectif introuvable.", "introuvable")
    o = dict(r)
    for k in ("nom", "critere_f", "critere_a", "critere_e"):
        if k in champs:
            o[k] = (champs[k] or "").strip()
    if not o["nom"]:
        raise RefExtErreur("Le nom de l'objectif est obligatoire.")
    if "nb_seances" in champs:
        _verifier_modifiable(conn, rid, code, aujourd_hui)
        o["nb_seances"] = _nb(champs["nb_seances"])
    conn.execute("UPDATE referentiel_objectifs SET nom=?, critere_f=?, critere_a=?, "
                 "critere_e=?, nb_seances=? WHERE referentiel_id=? AND seq_code=? AND code=?",
                 (o["nom"], o["critere_f"], o["critere_a"], o["critere_e"], o["nb_seances"],
                  rid, code, obj_code))


def deplacer_objectif(conn, rid: str, code: str, obj_code: str, sens: int,
                      aujourd_hui: date) -> None:
    _verifier_modifiable(conn, rid, code, aujourd_hui)
    rows = [dict(r) for r in conn.execute(
        "SELECT code, partie_numero FROM referentiel_objectifs WHERE referentiel_id=? AND "
        "seq_code=? ORDER BY partie_numero, code", (rid, code)).fetchall()]
    codes = [r["code"] for r in rows]
    if obj_code not in codes:
        raise RefExtErreur("Objectif introuvable.", "introuvable")
    i = codes.index(obj_code)
    j = i + (1 if sens > 0 else -1)
    if not 0 <= j < len(rows) or rows[i]["partie_numero"] != rows[j]["partie_numero"]:
        return          # on ne change pas de partie par déplacement
    a, b = codes[i], codes[j]
    conn.execute("UPDATE referentiel_objectifs SET code='~tmp' WHERE referentiel_id=? AND "
                 "seq_code=? AND code=?", (rid, code, a))
    conn.execute("UPDATE referentiel_objectifs SET code=? WHERE referentiel_id=? AND "
                 "seq_code=? AND code=?", (a, rid, code, b))
    conn.execute("UPDATE referentiel_objectifs SET code=? WHERE referentiel_id=? AND "
                 "seq_code=? AND code='~tmp'", (b, rid, code))


def supprimer_objectif(conn, rid: str, code: str, obj_code: str, aujourd_hui: date) -> None:
    _verifier_modifiable(conn, rid, code, aujourd_hui)
    conn.execute("DELETE FROM referentiel_objectifs WHERE referentiel_id=? AND seq_code=? "
                 "AND code=?", (rid, code, obj_code))
    _renumeroter_objectifs(conn, rid, code)


# ── Fichiers ─────────────────────────────────────────────────────────────────

def ajouter_fichier(conn, rid: str, code: str, partie_numero: int, *, nom_fichier: str,
                    contenu: bytes, mime: str, data_dir: Path) -> dict:
    """Ajout toujours permis (même séquence commencée)."""
    _lire_ref(conn, rid)
    if conn.execute("SELECT 1 FROM referentiel_sequences WHERE referentiel_id=? AND code=?",
                    (rid, code)).fetchone() is None:
        raise RefExtErreur("Séquence introuvable.", "introuvable")
    nom = (nom_fichier or "document").strip().replace("/", "_").replace("\\", "_")
    fid = _id("rnf_")
    dossier = Path(data_dir) / "referentiels_fichiers" / rid
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / f"{fid}_{nom}").write_bytes(contenu)
    chemin = f"referentiels_fichiers/{rid}/{fid}_{nom}"
    n = conn.execute("SELECT COALESCE(MAX(ordre), 0) FROM referentiel_fichiers WHERE "
                     "referentiel_id=? AND seq_code=?", (rid, code)).fetchone()[0]
    conn.execute("INSERT INTO referentiel_fichiers (id, referentiel_id, seq_code, partie_numero, "
                 "nom_fichier, chemin, mime, taille, ordre) VALUES (?,?,?,?,?,?,?,?,?)",
                 (fid, rid, code, int(partie_numero or 0), nom, chemin, mime or "",
                  len(contenu), n + 10))
    return lire_fichier(conn, fid)


def lire_fichier(conn, fid: str) -> dict:
    r = conn.execute("SELECT * FROM referentiel_fichiers WHERE id=?", (fid,)).fetchone()
    if r is None:
        raise RefExtErreur("Fichier introuvable.", "introuvable")
    return {**dict(r), "affichable": r["mime"] in MIMES_AFFICHABLES}


def supprimer_fichier(conn, fid: str, data_dir: Path | None = None) -> None:
    f = lire_fichier(conn, fid)
    if data_dir:
        try:
            (Path(data_dir) / f["chemin"]).unlink()
        except OSError:
            pass
    conn.execute("DELETE FROM referentiel_fichiers WHERE id=?", (fid,))


def fichiers_de_sequence(conn, niveau: str, annee: str, seq_code: str) -> list[dict]:
    """Fichiers des référentiels principaux externes du niveau et de l'année,
    pour une séquence (pour les documents associables de la progression)."""
    return [dict(r) for r in conn.execute(
        "SELECT f.*, n.version, COALESCE(t.libelle, '') AS type_libelle "
        "FROM referentiel_fichiers f JOIN referentiel_niveaux n "
        "ON n.id=f.referentiel_id LEFT JOIN types_documents t ON t.id=f.type_id "
        "WHERE n.source='externe' AND n.niveau=? AND "
        "(n.annee=? OR ?='') AND f.seq_code=? ORDER BY f.partie_numero, f.ordre",
        (niveau, annee, annee, seq_code)).fetchall()]
