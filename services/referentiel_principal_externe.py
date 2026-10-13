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
  - v0.51.4 — les codes de séquence (S01, S02… / M01…) suivent le rang tant
    que le référentiel est EN CONCEPTION (utilisé par aucune progression,
    jamais publié) : recalculés au réordonnancement et à la suppression ;
    ensuite ils ne changent plus (les créneaux, les parties posées en MER et
    l'appli en ligne s'y réfèrent) ;
  - v0.51.4 — la durée d'une partie (nb_seances_R_AE) est calculée : somme
    des nombres de séances de ses objectifs (lecture seule) ;
  - v0.51.5 — thèmes (code, nom, couleur, ordre) : les séquences d'un même
    thème sont regroupées, dans l'ordre des thèmes (séquences sans thème en
    dernier) ; codes A, B… recalculés d'après le rang tant que le référentiel
    est en conception ; une séquence sans thème est signalée (non bloquant) ;
  - v0.51.4 — un document attaché se déplace (annuel, séquence, partie) tant
    qu'il n'a pas été marqué distribué dans le suivi de séance.
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
    # v0.48.4 — description des référentiels externes de MER (le nom est
    # désormais calculé).
    cols_x = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_externe)")}
    if cols_x and "description" not in cols_x:
        conn.execute("ALTER TABLE referentiel_externe ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    # v0.48.3 — type d'un fichier ; types par défaut.
    cols_f = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_fichiers)")}
    if "type_id" not in cols_f:
        conn.execute("ALTER TABLE referentiel_fichiers ADD COLUMN type_id TEXT NOT NULL DEFAULT ''")
    # v0.48.5 — Placement par défaut : séance de distribution dans la partie,
    # retour attendu et délai.
    for nom, decl in (("seance_n", "INTEGER NOT NULL DEFAULT 0"),
                      ("retour", "TEXT NOT NULL DEFAULT ''"),
                      ("delai_type", "TEXT NOT NULL DEFAULT ''"),
                      ("delai_n", "INTEGER NOT NULL DEFAULT 1")):
        if nom not in cols_f:
            conn.execute(f"ALTER TABLE referentiel_fichiers ADD COLUMN {nom} {decl}")
    # v0.48.6 — Type d'objectif : connaissance (« Connaître les notions et
    # les méthodes », un seul par partie, toujours en 1re position) ou
    # capacité (maîtrise d'une capacité) — modèle des référentiels internes.
    cols_o = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_objectifs)")}
    if cols_o and "type_obj" not in cols_o:
        conn.execute("ALTER TABLE referentiel_objectifs ADD COLUMN type_obj TEXT NOT NULL "
                     "DEFAULT 'capacite'")
    # v0.49.0 — Libellé de partie (facultatif ; affiché s'il existe).
    cols_p = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_parties)")}
    if cols_p and "libelle" not in cols_p:
        conn.execute("ALTER TABLE referentiel_parties ADD COLUMN libelle TEXT NOT NULL DEFAULT ''")
    # v0.48.5 — Type des documents des référentiels externes de MER.
    cols_xd = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_externe_doc)")}
    if cols_xd and "type_id" not in cols_xd:
        conn.execute("ALTER TABLE referentiel_externe_doc ADD COLUMN type_id TEXT NOT NULL DEFAULT ''")
    # v0.51.6 — Modèle de départ (libellé) ; empreinte des fichiers.
    cols_n = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_niveaux)")}
    if cols_n and "cree_depuis" not in cols_n:
        conn.execute("ALTER TABLE referentiel_niveaux ADD COLUMN cree_depuis TEXT NOT NULL "
                     "DEFAULT ''")
    if "sha256" not in {r[1] for r in conn.execute("PRAGMA table_info(referentiel_fichiers)")}:
        conn.execute("ALTER TABLE referentiel_fichiers ADD COLUMN sha256 TEXT NOT NULL DEFAULT ''")
    # v0.51.5 — Ordre des thèmes d'un référentiel.
    cols_t = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_themes)")}
    if cols_t and "ordre" not in cols_t:
        conn.execute("ALTER TABLE referentiel_themes ADD COLUMN ordre INTEGER NOT NULL DEFAULT 0")
    # v0.51.4 — Durée des parties = somme des objectifs (référentiels conçus
    # localement ; les référentiels importés l'ont déjà).
    if cols_p:
        cols_n = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_niveaux)")}
        q = "SELECT id FROM referentiel_niveaux WHERE source='externe'"
        if "origine" in cols_n:
            q += " AND COALESCE(origine, '')<>'publication'"
        for r in conn.execute(q).fetchall():
            recalculer_parties(conn, r[0])
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
    """v0.48.4 — Nom calculé de TOUT référentiel figé (interne ou externe) :
    « 4e — 2026-2027 — Principal » (ou « MER »), plus la lettre de version
    (b, c…) si plusieurs. Interne : version '2025b' → année 2025-2026, lettre
    b ; externe : version 'X2026b', année scolaire stockée."""
    version = r.get("version") or ""
    if (r.get("source") or "interne") == "externe":
        lettre = version[5:]
        annee = r.get("annee") or ""
    else:
        lettre = version[4:]
        try:
            y = int(version[:4])
            annee = f"{y}-{y + 1}"
        except ValueError:
            annee = version
    niv = NIVEAUX.get(r.get("niveau"), r.get("niveau") or "")
    type_ = "MER" if (r.get("type_ref") or "principal") == "mer" else "Principal"
    return f"{niv} — {annee} — {type_}{(' ' + lettre) if lettre else ''}"


def _lire_ref(conn, rid: str) -> dict:
    r = conn.execute("SELECT * FROM referentiel_niveaux WHERE id=? AND source='externe'",
                     (rid,)).fetchone()
    if r is None:
        raise RefExtErreur("Référentiel externe introuvable.", "introuvable")
    return dict(r)


def lister(conn, niveau: str, type_ref: str | None = "principal") -> list[dict]:
    """Référentiels externes de la structure figée (principal par défaut)."""
    q = ("SELECT * FROM referentiel_niveaux WHERE source='externe' AND niveau=? "
         "AND etat<>'annule'")
    p = [niveau]
    if type_ref:
        q += " AND type_ref=?"
        p.append(type_ref)
    rows = conn.execute(q + " ORDER BY annee DESC, version", p).fetchall()
    return [{**dict(r), "nom": nom_calcule(dict(r))} for r in rows]


def creer(conn, niveau: str, annee: str, description: str = "",
          type_ref: str = "principal") -> dict:
    """v0.49.0 — `type_ref` : 'principal' (progression principale) ou 'mer'
    (progression de MER) ; même structure, même éditeur."""
    if niveau not in NIVEAUX:
        raise RefExtErreur(f"Niveau invalide : {niveau!r}.")
    if not annee or len(annee) != 9:
        raise RefExtErreur("Année scolaire invalide (AAAA-AAAA).")
    if type_ref not in ("principal", "mer"):
        raise RefExtErreur(f"Type invalide : {type_ref!r}.")
    base = ("M" if type_ref == "mer" else "X") + annee[:4]
    pris = {r["version"] for r in conn.execute(
        "SELECT version FROM referentiel_niveaux WHERE niveau=? AND version LIKE ?",
        (niveau, base + "%")).fetchall()}
    lettre = ""
    if base in pris:
        lettre = next(c for c in "bcdefghijklmnopqrstuvwxyz" if base + c not in pris)
    version = base + lettre
    rid = f"{base}_{niveau}{lettre}"      # convention interne : <annee>_<niveau><suffixe>
    conn.execute("INSERT INTO referentiel_niveaux (id, niveau, version, description, etat, "
                 "source, type_ref, annee) VALUES (?,?,?,?, 'en_cours', 'externe', ?, ?)",
                 (rid, niveau, version, (description or "").strip(), type_ref, annee))
    return lire(conn, rid)


def modifier(conn, rid: str, description: str) -> dict:
    _lire_ref(conn, rid)
    conn.execute("UPDATE referentiel_niveaux SET description=? WHERE id=?",
                 ((description or "").strip(), rid))
    return lire(conn, rid)


def est_utilise(conn, rid: str) -> bool:
    if conn.execute("SELECT 1 FROM progressions WHERE referentiel_id=? LIMIT 1",
                    (rid,)).fetchone() is not None:
        return True
    try:                                            # v0.49.0 — progression de MER
        if conn.execute("SELECT 1 FROM progression_mer WHERE ref_mer_id=? AND "
                        "ref_mer_source='fige' LIMIT 1", (rid,)).fetchone() is not None:
            return True
    except Exception:
        pass
    # v0.51.8 — Retour d'usage de l'appli en ligne (jamais perdu).
    from services import retour_usage as ru
    return ru.utilise(conn, rid)


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
    cette séquence, a une date de début passée (ou aujourd'hui).

    v0.49.0 — Référentiel de MER : la séquence est verrouillée dès qu'une de
    ses parties est posée dans une progression de MER (les parties posées y
    sont désignées par leur numéro)."""
    try:
        if conn.execute("SELECT 1 FROM progression_mer_partie WHERE partie_source='fige' "
                        "AND partie_id LIKE ? LIMIT 1",
                        (f"{rid}|{seq_code}|%",)).fetchone():
            return True
    except Exception:
        pass
    r = conn.execute(
        "SELECT 1 FROM creneaux c JOIN progressions p ON p.id=c.progression_id "
        "WHERE p.referentiel_id=? AND c.seq_code=? AND c.date_debut IS NOT NULL "
        "AND c.date_debut<>'' AND c.date_debut<=? LIMIT 1",
        (rid, seq_code, aujourd_hui.isoformat())).fetchone()
    if r is not None:
        return True
    # v0.51.8 — Retour d'usage de l'appli en ligne : premier créneau passé
    # (à la date de l'atelier) ou partie de MER posée.
    from services import retour_usage as ru
    return ru.sequence_commencee(conn, rid, seq_code, aujourd_hui)


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
    # v0.49.0 — Chaque partie doit avoir au moins un objectif « capacité »
    # (ce qu'on évalue à la fin) : alerte visible, non bloquante (un
    # référentiel externe est utilisable incomplet).
    alertes = []
    for s in seqs:
        for p in s["parties"]:
            p["sans_capacite"] = not any(o.get("type_obj") != "connaissance"
                                         for o in p["objectifs"])
            if p["sans_capacite"]:
                alertes.append(f"{s['code']} partie {p['numero']} : aucun objectif « capacité ».")
    themes = lister_themes(conn, rid)
    if not themes:
        alertes_themes = ["Aucun thème : définissez les thèmes du référentiel."]
    else:
        alertes_themes = [f"{s['code']} « {s['nom']} » : sans thème." for s in seqs
                          if not s.get("theme_code")]
    return {**ref, "nom": nom_calcule(ref), "utilise": est_utilise(conn, rid),
            "en_conception": en_conception(conn, rid),
            "themes": themes, "alertes_themes": alertes_themes,
            "couleurs_themes": [{"code": c, "libelle": l} for c, l in COULEURS_THEMES],
            "sequences": seqs, "documents_annuels": _fichiers(conn, rid, "", 0),
            "alertes": alertes}


def _fichiers(conn, rid, seq_code, partie_numero) -> list[dict]:
    return [{**dict(f), "affichable": f["mime"] in MIMES_AFFICHABLES,
             "distribue": fichier_distribue(conn, f["id"])} for f in conn.execute(
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


def placer_fichier(conn, fid: str, seance_n, retour: str = "", delai_type: str = "",
                   delai_n=1) -> dict:
    """v0.48.5 — Séance de distribution dans la partie (0 = aucune : à
    associer à la main), retour attendu et délai par défaut. Modifiable à tout
    moment (planification des documents, pas structure)."""
    from services import progression_doc as pgd
    f = lire_fichier(conn, fid)
    try:
        n = max(0, int(seance_n or 0))
    except (TypeError, ValueError):
        raise RefExtErreur(f"Séance invalide : {seance_n!r}.")
    if n and not f["partie_numero"]:
        raise RefExtErreur("Seul un fichier de partie peut avoir une séance de distribution.")
    try:
        retour, delai_type, delai_n = pgd._valider_retour(retour, delai_type, delai_n)
    except ValueError as e:
        raise RefExtErreur(str(e))
    conn.execute("UPDATE referentiel_fichiers SET seance_n=?, retour=?, delai_type=?, delai_n=? "
                 "WHERE id=?", (n, retour, delai_type, delai_n, fid))
    return lire_fichier(conn, fid)


def placements_automatiques(conn, referentiel_id: str) -> list[dict]:
    """Fichiers de partie ayant une séance de distribution (placement
    automatique dans la progression principale)."""
    return [dict(r) for r in conn.execute(
        "SELECT f.*, p.nb_seances_R_AE FROM referentiel_fichiers f "
        "JOIN referentiel_parties p ON p.referentiel_id=f.referentiel_id AND "
        "p.seq_code=f.seq_code AND p.numero=f.partie_numero "
        "WHERE f.referentiel_id=? AND f.partie_numero>0 AND f.seance_n>0",
        (referentiel_id,)).fetchall()]


def typer_doc_mer(conn, doc_id: str, type_id: str) -> None:
    """v0.48.5 — Type d'un document de référentiel externe de MER."""
    if conn.execute("SELECT 1 FROM referentiel_externe_doc WHERE id=?", (doc_id,)).fetchone() is None:
        raise RefExtErreur("Document introuvable.", "introuvable")
    if type_id and conn.execute("SELECT 1 FROM types_documents WHERE id=?",
                                (type_id,)).fetchone() is None:
        raise RefExtErreur("Type inconnu.")
    conn.execute("UPDATE referentiel_externe_doc SET type_id=? WHERE id=?", (type_id or "", doc_id))


def typer_fichier(conn, fid: str, type_id: str) -> dict:
    """Le type se modifie toujours (classement, même séquence commencée)."""
    lire_fichier(conn, fid)
    if type_id and conn.execute("SELECT 1 FROM types_documents WHERE id=?",
                                (type_id,)).fetchone() is None:
        raise RefExtErreur("Type inconnu.")
    conn.execute("UPDATE referentiel_fichiers SET type_id=? WHERE id=?", (type_id or "", fid))
    return lire_fichier(conn, fid)


# ── Séquences ────────────────────────────────────────────────────────────────

def ajouter_sequence(conn, rid: str, nom: str, theme_code: str | None = None) -> dict:
    """v0.51.5 — `theme_code` : la séquence se place à la fin de son thème."""
    _lire_ref(conn, rid)
    theme_code = (theme_code or "").strip() or None
    if theme_code:
        _theme(conn, rid, theme_code)
    nom = (nom or "").strip()
    if not nom:
        raise RefExtErreur("Le nom de la séquence est obligatoire.")
    ref = _lire_ref(conn, rid)
    pref = "M" if ref.get("type_ref") == "mer" else "S"      # v0.49.0
    codes = [r["code"] for r in conn.execute(
        "SELECT code FROM referentiel_sequences WHERE referentiel_id=?", (rid,)).fetchall()]
    nums = [int(c[1:]) for c in codes if c[:1] == pref and c[1:].isdigit()]
    code = f"{pref}{(max(nums) + 1) if nums else 1:02d}"
    numero = (conn.execute("SELECT COALESCE(MAX(numero), 0) FROM referentiel_sequences "
                           "WHERE referentiel_id=?", (rid,)).fetchone()[0]) + 1
    conn.execute("INSERT INTO referentiel_sequences (referentiel_id, code, numero, nom, "
                 "theme_code) VALUES (?,?,?,?,?)", (rid, code, numero, nom, theme_code))
    _ordonner_sequences(conn, rid)
    code = _recoder_sequences(conn, rid).get(code, code)
    numero = conn.execute("SELECT numero FROM referentiel_sequences WHERE referentiel_id=? "
                          "AND code=?", (rid, code)).fetchone()[0]
    return {"code": code, "numero": numero, "nom": nom, "theme_code": theme_code}


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
        return {"recode": False}
    # v0.51.5 — Une séquence se déplace à l'intérieur de son thème.
    themes = {r["code"]: r["theme_code"] for r in conn.execute(
        "SELECT code, theme_code FROM referentiel_sequences WHERE referentiel_id=?",
        (rid,)).fetchall()}
    if themes[codes[i]] != themes[codes[j]]:
        return {"recode": False}
    for c in (codes[i], codes[j]):
        _verifier_modifiable(conn, rid, c, aujourd_hui)
    codes[i], codes[j] = codes[j], codes[i]
    for k, c in enumerate(codes, start=1):
        conn.execute("UPDATE referentiel_sequences SET numero=? WHERE referentiel_id=? AND "
                     "code=?", (k, rid, c))
    return {"recode": recoder_sequences(conn, rid)}


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
    recoder_sequences(conn, rid)


def est_publie(conn, rid: str) -> bool:
    """v0.51.4 — Vrai si le référentiel figure dans un paquet de publication."""
    try:
        rows = conn.execute("SELECT referentiels FROM publications").fetchall()
    except Exception:
        return False
    import json
    for r in rows:
        try:
            if any(x.get("id") == rid for x in json.loads(r[0] or "[]")):
                return True
        except ValueError:
            continue
    return False


def en_conception(conn, rid: str) -> bool:
    """v0.51.4 — Référentiel en conception : conçu ici, utilisé par aucune
    progression et jamais publié. Ses codes de séquence suivent le rang."""
    ref = _lire_ref(conn, rid)
    if (ref.get("origine") or "") == "publication":
        return False
    return not est_utilise(conn, rid) and not est_publie(conn, rid)


def _tables_seq_code(conn) -> list[str]:
    """Tables portant (referentiel_id, seq_code)."""
    tables = []
    for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
        if {"referentiel_id", "seq_code"} <= cols:
            tables.append(t)
    return tables


def recoder_sequences(conn, rid: str) -> bool:
    """v0.51.4 — Codes de séquence recalculés d'après le rang (S01…Sn, M01…
    pour une MER), dans toutes les tables du référentiel, si le référentiel
    est en conception. Renvoie vrai si des codes ont changé."""
    return bool(_recoder_sequences(conn, rid))


def _recoder_sequences(conn, rid: str) -> dict:
    """Correspondance {ancien code: nouveau code} des séquences recodées."""
    if not en_conception(conn, rid):
        return {}
    pref = "M" if _lire_ref(conn, rid).get("type_ref") == "mer" else "S"
    rows = conn.execute("SELECT code FROM referentiel_sequences WHERE referentiel_id=? "
                        "ORDER BY numero", (rid,)).fetchall()
    corresp = {r["code"]: f"{pref}{k:02d}" for k, r in enumerate(rows, start=1)}
    corresp = {a: b for a, b in corresp.items() if a != b}
    if not corresp:
        return {}
    tables = _tables_seq_code(conn)
    # Clés étrangères (parties, objectifs… → séquence) vérifiées à la fin de
    # la transaction seulement.
    conn.execute("PRAGMA defer_foreign_keys = ON")
    # Deux temps (codes provisoires) : les nouveaux codes peuvent être des
    # anciens codes d'autres séquences.
    for etape in (0, 1):
        for ancien, nouveau in corresp.items():
            de, vers = (ancien, "~" + nouveau) if etape == 0 else ("~" + nouveau, nouveau)
            conn.execute("UPDATE referentiel_sequences SET code=? WHERE referentiel_id=? "
                         "AND code=?", (vers, rid, de))
            for t in tables:
                conn.execute(f"UPDATE {t} SET seq_code=? WHERE referentiel_id=? AND "
                             "seq_code=?", (vers, rid, de))
    return corresp


def _renumeroter_sequences(conn, rid):
    for k, r in enumerate(conn.execute(
            "SELECT code FROM referentiel_sequences WHERE referentiel_id=? ORDER BY numero",
            (rid,)).fetchall(), start=1):
        conn.execute("UPDATE referentiel_sequences SET numero=? WHERE referentiel_id=? AND "
                     "code=?", (k, rid, r["code"]))


# ── v0.51.5 — Thèmes ─────────────────────────────────────────────────────────

# Couleurs des thèmes (slugs partagés avec les référentiels internes).
COULEURS_THEMES = (("nombres", "Nombres et calculs"), ("grandeurs", "Grandeurs et mesures"),
                   ("geometrie", "Espace et géométrie"), ("donnees", "Organisation et gestion "
                   "des données"), ("algorithmique", "Algorithmique et programmation"),
                   ("noir_gris", "Neutre"))


def lister_themes(conn, rid: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM referentiel_themes WHERE referentiel_id=? "
                        "ORDER BY ordre, code", (rid,)).fetchall()
    out = []
    for t in rows:
        t = dict(t)
        t["nb_sequences"] = conn.execute(
            "SELECT COUNT(*) FROM referentiel_sequences WHERE referentiel_id=? AND "
            "theme_code=?", (rid, t["code"])).fetchone()[0]
        out.append(t)
    return out


def _theme(conn, rid: str, code: str) -> dict:
    r = conn.execute("SELECT * FROM referentiel_themes WHERE referentiel_id=? AND code=?",
                     (rid, code)).fetchone()
    if r is None:
        raise RefExtErreur("Thème introuvable.", "introuvable")
    return dict(r)


def _lettre(k: int) -> str:
    """1 → A, 26 → Z, 27 → AA…"""
    s = ""
    while k > 0:
        k, r = divmod(k - 1, 26)
        s = chr(65 + r) + s
    return s


def _couleur(couleur: str) -> str:
    couleur = (couleur or "").strip()
    if couleur and couleur not in dict(COULEURS_THEMES):
        raise RefExtErreur(f"Couleur de thème inconnue : {couleur!r}.")
    return couleur


def ajouter_theme(conn, rid: str, nom: str, couleur: str = "") -> dict:
    _lire_ref(conn, rid)
    nom = (nom or "").strip()
    if not nom:
        raise RefExtErreur("Le nom du thème est obligatoire.")
    couleur = _couleur(couleur)
    existants = {t["code"] for t in lister_themes(conn, rid)}
    if any(t["nom"].lower() == nom.lower() for t in lister_themes(conn, rid)):
        raise RefExtErreur(f"Le thème « {nom} » existe déjà.")
    k = 1
    while _lettre(k) in existants:
        k += 1
    code = _lettre(k)
    ordre = conn.execute("SELECT COALESCE(MAX(ordre), 0) FROM referentiel_themes WHERE "
                         "referentiel_id=?", (rid,)).fetchone()[0] + 1
    conn.execute("INSERT INTO referentiel_themes (referentiel_id, code, nom, couleur, ordre) "
                 "VALUES (?,?,?,?,?)", (rid, code, nom, couleur, ordre))
    _ordonner_themes(conn, rid)
    code = _recoder_themes(conn, rid).get(code, code)
    return _theme(conn, rid, code)


def modifier_theme(conn, rid: str, code: str, champs: dict) -> dict:
    """Nom et couleur : toujours modifiables."""
    t = _theme(conn, rid, code)
    if "nom" in champs:
        t["nom"] = (champs["nom"] or "").strip()
        if not t["nom"]:
            raise RefExtErreur("Le nom du thème est obligatoire.")
    if "couleur" in champs:
        t["couleur"] = _couleur(champs["couleur"])
    conn.execute("UPDATE referentiel_themes SET nom=?, couleur=? WHERE referentiel_id=? AND "
                 "code=?", (t["nom"], t["couleur"], rid, code))
    return t


def deplacer_theme(conn, rid: str, code: str, sens: int) -> dict:
    """Le thème et toutes ses séquences changent de place."""
    codes = [t["code"] for t in lister_themes(conn, rid)]
    if code not in codes:
        raise RefExtErreur("Thème introuvable.", "introuvable")
    i = codes.index(code)
    j = i + (1 if sens > 0 else -1)
    if not 0 <= j < len(codes):
        return {"recode": False}
    codes[i], codes[j] = codes[j], codes[i]
    for k, c in enumerate(codes, start=1):
        conn.execute("UPDATE referentiel_themes SET ordre=? WHERE referentiel_id=? AND code=?",
                     (k, rid, c))
    _ordonner_sequences(conn, rid)
    a = bool(_recoder_themes(conn, rid))
    b = bool(_recoder_sequences(conn, rid))
    return {"recode": a or b}


def supprimer_theme(conn, rid: str, code: str) -> None:
    """Ses séquences deviennent « sans thème » (signalées)."""
    _theme(conn, rid, code)
    conn.execute("UPDATE referentiel_sequences SET theme_code=NULL WHERE referentiel_id=? AND "
                 "theme_code=?", (rid, code))
    conn.execute("DELETE FROM referentiel_themes WHERE referentiel_id=? AND code=?", (rid, code))
    _ordonner_themes(conn, rid)
    _ordonner_sequences(conn, rid)
    _recoder_themes(conn, rid)
    _recoder_sequences(conn, rid)


def affecter_theme(conn, rid: str, seq_code: str, theme_code: str | None,
                   aujourd_hui: date) -> dict:
    """Change le thème d'une séquence : elle passe à la fin de son nouveau
    thème. Refusé pour une séquence commencée."""
    theme_code = (theme_code or "").strip() or None
    r = conn.execute("SELECT theme_code FROM referentiel_sequences WHERE referentiel_id=? AND "
                     "code=?", (rid, seq_code)).fetchone()
    if r is None:
        raise RefExtErreur("Séquence introuvable.", "introuvable")
    if r["theme_code"] == theme_code:
        return {"code": seq_code}
    _verifier_modifiable(conn, rid, seq_code, aujourd_hui)
    if theme_code:
        _theme(conn, rid, theme_code)
    fin = conn.execute("SELECT COALESCE(MAX(numero), 0) FROM referentiel_sequences WHERE "
                       "referentiel_id=?", (rid,)).fetchone()[0] + 1
    conn.execute("UPDATE referentiel_sequences SET theme_code=?, numero=? WHERE "
                 "referentiel_id=? AND code=?", (theme_code, fin, rid, seq_code))
    _ordonner_sequences(conn, rid)
    return {"code": _recoder_sequences(conn, rid).get(seq_code, seq_code)}


def _ordonner_themes(conn, rid):
    for k, t in enumerate(lister_themes(conn, rid), start=1):
        conn.execute("UPDATE referentiel_themes SET ordre=? WHERE referentiel_id=? AND code=?",
                     (k, rid, t["code"]))


def _ordonner_sequences(conn, rid):
    """Séquences regroupées par thème, dans l'ordre des thèmes (sans thème
    en dernier), en gardant leur ordre relatif."""
    rang = {t["code"]: t["ordre"] for t in lister_themes(conn, rid)}
    rows = conn.execute("SELECT code, numero, theme_code FROM referentiel_sequences WHERE "
                        "referentiel_id=?", (rid,)).fetchall()
    tri = sorted(rows, key=lambda r: (rang.get(r["theme_code"], 10 ** 6), r["numero"]))
    for k, r in enumerate(tri, start=1):
        conn.execute("UPDATE referentiel_sequences SET numero=? WHERE referentiel_id=? AND "
                     "code=?", (-k, rid, r["code"]))
    conn.execute("UPDATE referentiel_sequences SET numero=-numero WHERE referentiel_id=? AND "
                 "numero<0", (rid,))


def _recoder_themes(conn, rid) -> dict:
    """Codes de thème A, B… d'après le rang, si le référentiel est en conception."""
    if not en_conception(conn, rid):
        return {}
    corresp = {t["code"]: _lettre(k) for k, t in enumerate(lister_themes(conn, rid), start=1)}
    corresp = {a: b for a, b in corresp.items() if a != b}
    if not corresp:
        return {}
    conn.execute("PRAGMA defer_foreign_keys = ON")
    for etape in (0, 1):
        for ancien, nouveau in corresp.items():
            de, vers = (ancien, "~" + nouveau) if etape == 0 else ("~" + nouveau, nouveau)
            conn.execute("UPDATE referentiel_themes SET code=? WHERE referentiel_id=? AND "
                         "code=?", (vers, rid, de))
            conn.execute("UPDATE referentiel_sequences SET theme_code=? WHERE referentiel_id=? "
                         "AND theme_code=?", (vers, rid, de))
    return corresp


# ── Parties ──────────────────────────────────────────────────────────────────

def _nb(v, nom="nombre de séances") -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise RefExtErreur(f"{nom.capitalize()} invalide : {v!r}.")
    if f < 0:
        raise RefExtErreur(f"{nom.capitalize()} négatif.")
    return f


def recalculer_parties(conn, rid: str) -> None:
    """v0.51.4 — Durée de chaque partie = somme des séances de ses objectifs."""
    conn.execute(
        "UPDATE referentiel_parties SET nb_seances_R_AE=(SELECT COALESCE(SUM(o.nb_seances), 0) "
        "FROM referentiel_objectifs o WHERE o.referentiel_id=referentiel_parties.referentiel_id "
        "AND o.seq_code=referentiel_parties.seq_code AND "
        "o.partie_numero=referentiel_parties.numero) WHERE referentiel_id=?", (rid,))


def ajouter_partie(conn, rid: str, code: str, nb_seances=0, aujourd_hui: date | None = None,
                   libelle: str = "") -> dict:
    """v0.51.4 — `nb_seances` est ignoré : la durée est calculée (objectifs)."""
    aujourd_hui = aujourd_hui or date.today()
    _verifier_modifiable(conn, rid, code, aujourd_hui)
    if conn.execute("SELECT 1 FROM referentiel_sequences WHERE referentiel_id=? AND code=?",
                    (rid, code)).fetchone() is None:
        raise RefExtErreur("Séquence introuvable.", "introuvable")
    n = (conn.execute("SELECT COALESCE(MAX(numero), 0) FROM referentiel_parties WHERE "
                      "referentiel_id=? AND seq_code=?", (rid, code)).fetchone()[0]) + 1
    conn.execute("INSERT INTO referentiel_parties (referentiel_id, seq_code, numero, "
                 "nb_seances_R_AE, libelle) VALUES (?,?,?,?,?)",
                 (rid, code, n, 0, (libelle or "").strip()))
    return {"seq_code": code, "numero": n}


def libeller_partie(conn, rid: str, code: str, numero: int, libelle: str) -> None:
    """v0.49.0 — Libellé de partie : correction toujours permise."""
    n = conn.execute("UPDATE referentiel_parties SET libelle=? WHERE referentiel_id=? AND "
                     "seq_code=? AND numero=?", ((libelle or "").strip(), rid, code,
                                                 int(numero))).rowcount
    if not n:
        raise RefExtErreur("Partie introuvable.", "introuvable")


def modifier_partie(conn, rid: str, code: str, numero: int, nb_seances,
                    aujourd_hui: date) -> None:
    """v0.51.4 — Plus de saisie : la durée d'une partie est calculée."""
    raise RefExtErreur("La durée d'une partie est la somme des séances de ses objectifs : "
                       "modifiez les objectifs.")


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
    """Codes 01, 02… dans l'ordre (partie, objectif « connaissance » en tête,
    code actuel). Deux passes pour éviter les collisions de clé primaire."""
    rows = [dict(r) for r in conn.execute(
        "SELECT code FROM referentiel_objectifs WHERE referentiel_id=? AND seq_code=? "
        "ORDER BY partie_numero, CASE WHEN type_obj='connaissance' THEN 0 ELSE 1 END, code",
        (rid, code)).fetchall()]
    for k, r in enumerate(rows, start=1):
        conn.execute("UPDATE referentiel_objectifs SET code=? WHERE referentiel_id=? AND "
                     "seq_code=? AND code=?", (f"~{k:02d}", rid, code, r["code"]))
    for k in range(1, len(rows) + 1):
        conn.execute("UPDATE referentiel_objectifs SET code=? WHERE referentiel_id=? AND "
                     "seq_code=? AND code=?", (f"{k:02d}", rid, code, f"~{k:02d}"))


TYPES_OBJ = ("connaissance", "capacite")


def ajouter_objectif(conn, rid: str, code: str, partie_numero: int, nom: str,
                     nb_seances=0, aujourd_hui: date | None = None,
                     type_obj: str = "capacite", criteres: dict | None = None) -> None:
    _verifier_modifiable(conn, rid, code, aujourd_hui or date.today())
    nom = (nom or "").strip()
    if not nom:
        raise RefExtErreur("Le nom de l'objectif est obligatoire.")
    if type_obj not in TYPES_OBJ:
        raise RefExtErreur(f"Type d'objectif invalide : {type_obj!r}.")
    if type_obj == "connaissance" and conn.execute(
            "SELECT 1 FROM referentiel_objectifs WHERE referentiel_id=? AND seq_code=? AND "
            "partie_numero=? AND type_obj='connaissance'",
            (rid, code, int(partie_numero))).fetchone():
        raise RefExtErreur("Cette partie a déjà son objectif de connaissance du cours.")
    if conn.execute("SELECT 1 FROM referentiel_parties WHERE referentiel_id=? AND seq_code=? "
                    "AND numero=?", (rid, code, int(partie_numero))).fetchone() is None:
        raise RefExtErreur("Partie introuvable.", "introuvable")
    # Code provisoire en fin de partie, puis renumérotation globale.
    der = conn.execute("SELECT MAX(code) FROM referentiel_objectifs WHERE referentiel_id=? "
                       "AND seq_code=? AND partie_numero=?",
                       (rid, code, int(partie_numero))).fetchone()[0]
    prov = (der or f"{int(partie_numero):02d}") + "z"
    cr = criteres or {}
    conn.execute("INSERT INTO referentiel_objectifs (referentiel_id, seq_code, code, nom, "
                 "partie_numero, nb_seances, type_obj, critere_f, critere_a, critere_e) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (rid, code, prov, nom, int(partie_numero), _nb(nb_seances), type_obj,
                  cr.get("f", ""), cr.get("a", ""), cr.get("e", "")))
    _renumeroter_objectifs(conn, rid, code)
    recalculer_parties(conn, rid)


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
    recalculer_parties(conn, rid)


def deplacer_objectif(conn, rid: str, code: str, obj_code: str, sens: int,
                      aujourd_hui: date) -> None:
    _verifier_modifiable(conn, rid, code, aujourd_hui)
    rows = [dict(r) for r in conn.execute(
        "SELECT code, partie_numero, type_obj FROM referentiel_objectifs WHERE referentiel_id=? "
        "AND seq_code=? ORDER BY partie_numero, code", (rid, code)).fetchall()]
    codes = [r["code"] for r in rows]
    if obj_code not in codes:
        raise RefExtErreur("Objectif introuvable.", "introuvable")
    i = codes.index(obj_code)
    j = i + (1 if sens > 0 else -1)
    if not 0 <= j < len(rows) or rows[i]["partie_numero"] != rows[j]["partie_numero"]:
        return          # on ne change pas de partie par déplacement
    if "connaissance" in (rows[i]["type_obj"], rows[j]["type_obj"]):
        return          # l'objectif de connaissance reste en tête de sa partie
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
    recalculer_parties(conn, rid)


# ── Fichiers ─────────────────────────────────────────────────────────────────

def fichier_distribue(conn, fid: str) -> bool:
    """v0.51.4 — Vrai si le document a été marqué distribué dans le suivi de
    séance d'une classe (placement automatique, ou association manuelle dans
    une progression principale ou de MER)."""
    try:
        manuels = [r[0] for r in conn.execute(
            "SELECT id FROM progression_doc WHERE doc_ref=?", (fid,)).fetchall()]
    except Exception:
        manuels = []
    cles = [f"automer:{fid}"] + manuels + [f"mer:{m}" for m in manuels]
    try:
        q = ("SELECT 1 FROM seance_documents WHERE distribue_date<>'' AND (cle_prevu LIKE ? "
             f"OR cle_prevu IN ({','.join('?' * len(cles))})) LIMIT 1")
        return conn.execute(q, [f"auto:{fid}:%", *cles]).fetchone() is not None
    except Exception:
        return False


def deplacer_fichier(conn, fid: str, seq_code: str, partie_numero: int) -> dict:
    """v0.51.4 — Change le point d'attache d'un document : annuel (seq_code
    vide), séquence (partie 0) ou partie. Refusé une fois le document marqué
    distribué. La séance de distribution (placement automatique) n'a de sens
    que dans une partie : effacée ailleurs, conservée d'une partie à l'autre
    (alerte si elle dépasse la durée de la nouvelle partie)."""
    f = lire_fichier(conn, fid)
    rid = f["referentiel_id"]
    seq_code = (seq_code or "").strip()
    partie_numero = int(partie_numero or 0) if seq_code else 0
    if (f["seq_code"], int(f["partie_numero"] or 0)) == (seq_code, partie_numero):
        return {**f, "alerte": ""}
    if fichier_distribue(conn, fid):
        raise RefExtErreur("Ce document a déjà été distribué à une classe : il ne se "
                           "déplace plus.")
    if seq_code and conn.execute("SELECT 1 FROM referentiel_sequences WHERE referentiel_id=? "
                                 "AND code=?", (rid, seq_code)).fetchone() is None:
        raise RefExtErreur("Séquence introuvable.", "introuvable")
    duree = None
    if partie_numero:
        p = conn.execute("SELECT nb_seances_R_AE FROM referentiel_parties WHERE "
                         "referentiel_id=? AND seq_code=? AND numero=?",
                         (rid, seq_code, partie_numero)).fetchone()
        if p is None:
            raise RefExtErreur("Partie introuvable.", "introuvable")
        duree = float(p[0] or 0)
    seance_n = int(f["seance_n"] or 0) if partie_numero else 0
    n = conn.execute("SELECT COALESCE(MAX(ordre), 0) FROM referentiel_fichiers WHERE "
                     "referentiel_id=? AND seq_code=?", (rid, seq_code)).fetchone()[0]
    conn.execute("UPDATE referentiel_fichiers SET seq_code=?, partie_numero=?, seance_n=?, "
                 "ordre=? WHERE id=?", (seq_code, partie_numero, seance_n, n + 10, fid))
    alerte = ""
    if seance_n and duree is not None and seance_n > duree:
        alerte = (f"Séance de distribution {seance_n} au-delà de la durée de la partie "
                  f"({duree:g} séance(s)) : à corriger.")
    return {**lire_fichier(conn, fid), "alerte": alerte}

def ajouter_fichier(conn, rid: str, code: str, partie_numero: int, *, nom_fichier: str,
                    contenu: bytes, mime: str, data_dir: Path) -> dict:
    """Ajout toujours permis (même séquence commencée). v0.49.0 — `code` vide :
    document annuel (rattaché au référentiel, pas à une séquence)."""
    _lire_ref(conn, rid)
    if code and conn.execute("SELECT 1 FROM referentiel_sequences WHERE referentiel_id=? "
                             "AND code=?", (rid, code)).fetchone() is None:
        raise RefExtErreur("Séquence introuvable.", "introuvable")
    if not code:
        partie_numero = 0
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
    # v0.51.6 — Empreinte du contenu (détection des référentiels en double).
    import hashlib
    conn.execute("UPDATE referentiel_fichiers SET sha256=? WHERE id=?",
                 (hashlib.sha256(contenu).hexdigest(), fid))
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


def parties_mer(conn, rid: str) -> list[dict]:
    """v0.49.0 — Parties d'un référentiel de MER (structure figée) pour la
    progression de MER : id stable `<référentiel>|<séquence>|<numéro>`."""
    return [{"id": f"{rid}|{r['seq_code']}|{r['numero']}",
             "libelle": r["libelle"] or f"Partie {r['numero']}",
             "nb_seances": r["nb_seances_R_AE"], "numero": r["numero"],
             "sequence_code": r["seq_code"], "sequence_nom": r["seq_nom"]}
            for r in conn.execute(
                "SELECT p.*, s.nom AS seq_nom FROM referentiel_parties p "
                "JOIN referentiel_sequences s ON s.referentiel_id=p.referentiel_id AND "
                "s.code=p.seq_code WHERE p.referentiel_id=? ORDER BY s.numero, p.numero",
                (rid,)).fetchall()]


def partie_mer(conn, partie_id: str) -> dict | None:
    try:
        rid, code, num = partie_id.rsplit("|", 2)
    except ValueError:
        return None
    return next((p for p in parties_mer(conn, rid)
                 if p["sequence_code"] == code and str(p["numero"]) == num), None)


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
