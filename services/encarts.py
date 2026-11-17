r"""services/encarts.py — v0.59.2

Encarts du livret d'exercices au modèle « Fiches » (demande de Laurent du
17 novembre 2026 : une collègue trouve le livret « trop uniforme, presque
triste ») : « Le saviez-vous ? », « Point histoire », « Les maths dans la
vraie vie », « Défi », **quand ça a un sens**, sans nombre cible. Format
LaTeX : environnement `seqEncartSix` et `\seqSolutionDefiSix` du module
`seqenseigne-style6e` v0.15 ; format des lots : `lot6e/FORMAT_ENCARTS.md`.

Décisions (doc/redemarrage_v0_59_2.md) :

  - E1 API LaTeX — un seul environnement paramétré
    `\begin{seqEncartSix}[pleine|demi]{type}{titre}` (types `savoir`,
    `histoire`, `vraievie`, `defi`) plutôt que quatre environnements : une
    seule mise en forme à maintenir, le type est une donnée.
  - E2 Stockage — une table dédiée `encarts` (comme `cartes_mentales`) :
    rattachée à une partie (`partie_id`, suppression en cascade) et, pour un
    encart d'objectif, à l'objectif (`objectif_id`) ; position, exercice de
    référence, type, titre, texte, solution (défi), largeur, source (jamais
    imprimée), ordre, `mtime` (péremption du livret et des corrigés), `niveau`
    et `sequence` dénormalisés. Pas un atome : il n'a ni état ni rendu seul.
  - E3 Positions — encart d'objectif : `apres_activite` (après les activités
    d'introduction de l'objectif, avant sa fiche), `apres_exercice` (après
    l'exercice nommé, et sa remédiation si elle le suit), `fin_objectif`
    (après le dernier exercice de l'objectif) ; encart de partie :
    `fin_partie` (après les exercices de la partie, avant la carte mentale).
    Un exercice de référence absent du livret (série E non incluse) : l'encart
    passe en fin d'objectif.
  - E4 Rendu — livret d'exercices élève et corrigé, corrigés enseignant (même
    corps) ; jamais dans les tests courts ni les évaluations (autres
    générateurs). Deux encarts `demi` consécutifs à la même place sont côte à
    côte. Un livret sans encart produit exactement le même `.tex` qu'avant.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone

TABLE = "encarts"
ENV = "seqEncartSix"

TYPES = {
    "savoir": "Le saviez-vous ?",
    "histoire": "Point histoire",
    "vraievie": "Les maths dans la vraie vie",
    "defi": "Défi",
}
POSITIONS_OBJECTIF = ("apres_activite", "apres_exercice", "fin_objectif")
POSITIONS_PARTIE = ("fin_partie",)
POSITIONS = POSITIONS_OBJECTIF + POSITIONS_PARTIE
LIBELLES_POSITIONS = {"apres_activite": "après les activités de l'objectif",
                      "apres_exercice": "après l'exercice",
                      "fin_objectif": "en fin d'objectif",
                      "fin_partie": "en fin de partie"}
LARGEURS = ("pleine", "demi")
# Repère de longueur (« une demi-douzaine de lignes au plus ») : nombre de
# caractères du texte au-delà duquel l'import avertit (sans refuser).
LONGUEUR_CONSEILLEE = {"pleine": 520, "demi": 240}

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id           TEXT PRIMARY KEY,                  -- 'en_xxxxxxxx'
    partie_id    TEXT NOT NULL
                 REFERENCES sequence_parties(id) ON DELETE CASCADE,
    objectif_id  TEXT REFERENCES objectifs(id) ON DELETE CASCADE,
    niveau       TEXT NOT NULL DEFAULT '',
    sequence     TEXT NOT NULL DEFAULT '',
    position     TEXT NOT NULL DEFAULT 'fin_partie',
    exercice_id  TEXT NOT NULL DEFAULT '',
    exercice     TEXT NOT NULL DEFAULT '',          -- code du lot (« F03 »)
    type         TEXT NOT NULL DEFAULT 'savoir',
    titre        TEXT NOT NULL DEFAULT '',
    texte        TEXT NOT NULL DEFAULT '',
    solution     TEXT NOT NULL DEFAULT '',
    largeur      TEXT NOT NULL DEFAULT 'pleine',
    source       TEXT NOT NULL DEFAULT '',
    ordre        INTEGER NOT NULL DEFAULT 0,
    mtime        TEXT NOT NULL DEFAULT ''
)"""

CHAMPS_CONTENU = ("position", "exercice_id", "exercice", "type", "titre", "texte",
                  "solution", "largeur", "source")


class EncartErreur(ValueError):
    pass


# ── Migration ────────────────────────────────────────────────────────────────

def table_presente(conn: sqlite3.Connection) -> bool:
    try:
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                            (TABLE,)).fetchone() is not None
    except sqlite3.Error:
        return False


def migrer(conn: sqlite3.Connection) -> bool:
    """Crée la table et son index (idempotent). True si elle vient d'être créée."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='sequence_parties'").fetchone():
        return False
    neuve = not table_presente(conn)
    conn.execute(DDL)
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_niveau_seq "
                 f"ON {TABLE} (niveau, sequence)")
    return neuve


def maintenant() -> str:
    """mtime au format des atomes (UTC, « AAAA-MM-JJ HH:MM:SS »)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def nid() -> str:
    return f"en_{uuid.uuid4().hex[:8]}"


# ── Contrôle d'une entrée de lot ─────────────────────────────────────────────

_RE_SEQ_MACRO = re.compile(r"\\(seq[A-Za-z]+)")
_RE_EXO = re.compile(r"^(F|A|E)(\d{1,2})$")


def normaliser_exercice(code) -> str:
    """« F3 », « f03 », « F03 » → « F03 » ; '' si invalide."""
    m = _RE_EXO.match(str(code or "").strip().upper())
    return f"{m.group(1)}{int(m.group(2)):02d}" if m else ""


def controler(src: dict, niveau_objectif: bool) -> tuple[dict, list[str], list[str]]:
    """(entrée normalisée, erreurs, avertissements) d'une entrée de lot.

    Erreurs (encart non importé) : type inconnu, texte vide, position
    inconnue ou d'un autre niveau (objectif / partie), exercice manquant ou
    invalide pour `apres_exercice`, largeur inconnue, solution hors défi,
    environnement `seqEncartSix` écrit dans le texte (l'appli l'ajoute),
    macro `\seq…` inconnue du module. Avertissements : texte long (repère
    d'une demi-douzaine de lignes), défi sans solution, encart sans source
    (sauf défi)."""
    from services import style6e
    err, av = [], []
    t = str(src.get("type") or "").strip()
    if t not in TYPES:
        err.append(f"type {t!r} inconnu (attendu : {', '.join(TYPES)})")
    texte = (src.get("texte") or "").strip()
    if not texte:
        err.append("texte vide")
    defaut = "fin_objectif" if niveau_objectif else "fin_partie"
    pos = str(src.get("position") or defaut).strip()
    permises = POSITIONS_OBJECTIF if niveau_objectif else POSITIONS_PARTIE
    if pos not in permises:
        err.append(f"position {pos!r} impossible ici (attendu : {', '.join(permises)})")
    exo = ""
    if pos == "apres_exercice":
        exo = normaliser_exercice(src.get("exercice"))
        if not exo:
            err.append(f"exercice {src.get('exercice')!r} invalide (attendu « F03 », « A01 »…)")
    larg = str(src.get("largeur") or "pleine").strip()
    if larg not in LARGEURS:
        err.append(f"largeur {larg!r} inconnue (attendu : pleine, demi)")
    sol = (src.get("solution") or "").strip()
    if sol and t != "defi":
        err.append("solution réservée au type defi")
    tout = texte + "\n" + sol + "\n" + str(src.get("titre") or "")
    if "\\begin{" + ENV + "}" in tout or "\\end{" + ENV + "}" in tout:
        err.append("le texte ne doit pas contenir l'environnement seqEncartSix (l'appli l'ajoute)")
    connues = set(style6e.MACROS) | {"seqLocSiCorrige"}
    inconnues = sorted({m for m in _RE_SEQ_MACRO.findall(tout)
                        if m not in connues and not m.startswith("seqLoc")})
    if inconnues:
        err.append("macro(s) inconnue(s) du module : " + ", ".join("\\" + m for m in inconnues))
    if t == "defi" and not sol:
        av.append("défi sans solution (le corrigé n'en donnera pas)")
    if t in TYPES and t != "defi" and not (src.get("source") or "").strip():
        av.append("encart sans source (faits à vérifier et à sourcer)")
    if larg in LONGUEUR_CONSEILLEE and len(texte) > LONGUEUR_CONSEILLEE[larg]:
        av.append(f"texte long ({len(texte)} caractères, repère {LONGUEUR_CONSEILLEE[larg]} "
                  f"en {larg} largeur : une demi-douzaine de lignes au plus)")
    entree = {"type": t, "titre": str(src.get("titre") or "").strip(), "texte": texte,
              "position": pos, "exercice": exo, "largeur": larg, "solution": sol,
              "source": str(src.get("source") or "").strip()}
    return entree, err, av


# ── Lecture ──────────────────────────────────────────────────────────────────

def _cols_lecture() -> str:
    return ("e.id, e.partie_id, e.objectif_id, e.position, e.exercice_id, e.exercice, "
            "e.type, e.titre, e.texte, e.solution, e.largeur, e.source, e.ordre, e.mtime")


def encarts_de_sequence(conn: sqlite3.Connection, niveau: str, sequence: str) -> list[dict]:
    """Encarts d'une séquence-niveau, dans l'ordre (partie, objectif, position,
    ordre), avec le numéro de partie et le code d'objectif. [] sans table."""
    if not table_presente(conn):
        return []
    rows = conn.execute(
        f"SELECT {_cols_lecture()}, p.numero AS partie_numero, "
        "COALESCE(o.code, '') AS objectif_code "
        f"FROM {TABLE} e JOIN sequence_parties p ON p.id = e.partie_id "
        "JOIN sequences_par_niveau s ON s.id = p.sequence_par_niveau_id "
        "LEFT JOIN objectifs o ON o.id = e.objectif_id "
        "WHERE s.niveau = ? AND s.sequence_code = ? "
        "ORDER BY p.numero, COALESCE(o.code, 'zz'), e.position, e.ordre, e.id",
        (niveau, sequence)).fetchall()
    return [dict(r) for r in rows]


def repartir(encarts: list[dict]) -> dict:
    """{'partie': {numero: [encarts fin_partie]}, 'objectif': {(numero, code):
    {position: [...]}}} pour le livret."""
    out: dict = {"partie": {}, "objectif": {}}
    for e in encarts:
        if e.get("objectif_id"):
            d = out["objectif"].setdefault((e["partie_numero"], e["objectif_code"]), {})
            d.setdefault(e["position"], []).append(e)
        else:
            out["partie"].setdefault(e["partie_numero"], []).append(e)
    return out


# ── Rendu LaTeX ──────────────────────────────────────────────────────────────

def latex_encart(e: dict) -> str:
    opt = "[demi]" if e.get("largeur") == "demi" else ""
    corps = (e.get("texte") or "").strip()
    if e.get("type") == "defi" and (e.get("solution") or "").strip():
        corps += "\n\\seqSolutionDefiSix{" + e["solution"].strip() + "}"
    return ("\\begin{" + ENV + "}" + opt + "{" + e.get("type", "savoir") + "}{"
            + (e.get("titre") or "") + "}\n" + corps + "\n\\end{" + ENV + "}")


def emettre(L: list, encarts: list[dict]) -> None:
    """Ajoute les encarts à L (lignes LaTeX). Deux encarts `demi` qui se
    suivent sont placés côte à côte ; un `demi` seul est centré."""
    i = 0
    while i < len(encarts):
        e = encarts[i]
        if e.get("largeur") == "demi":
            suivant = encarts[i + 1] if i + 1 < len(encarts) else None
            L.append(r"\par\addvspace{6pt}\needspace{8\baselineskip}")
            if suivant is not None and suivant.get("largeur") == "demi":
                L.append(r"\noindent" + latex_encart(e) + r"\hfill" + latex_encart(suivant)
                         + r"\par\addvspace{6pt}")
                i += 2
                continue
            L.append(r"{\centering" + latex_encart(e) + r"\par}\addvspace{6pt}")
            i += 1
            continue
        L.append(latex_encart(e))
        i += 1


# ── Écriture (import des lots) ───────────────────────────────────────────────

def lire_existants(conn: sqlite3.Connection, sn_id: str) -> list[dict]:
    if not table_presente(conn):
        return []
    return [dict(r) for r in conn.execute(
        f"SELECT e.* FROM {TABLE} e JOIN sequence_parties p ON p.id = e.partie_id "
        "WHERE p.sequence_par_niveau_id = ? ORDER BY e.id", (sn_id,)).fetchall()]


def cle(e: dict) -> tuple:
    """Repère d'un encart pour l'idempotence : place (partie, objectif,
    position, exercice) et rang à cette place."""
    return (e["partie_id"], e.get("objectif_id") or "", e["position"],
            e.get("exercice") or "", int(e.get("ordre") or 0))


def aligner(conn: sqlite3.Connection, sn_id: str, niveau: str, sequence: str,
            voulus: list[dict]) -> dict:
    """Le lot fait foi pour les encarts de la séquence : crée, met à jour,
    retire. `voulus` : entrées complètes (partie_id, objectif_id, ordre et
    CHAMPS_CONTENU). Retourne {'crees', 'maj', 'inchanges', 'retires':
    [lignes retirées]}."""
    migrer(conn)
    existants = {cle(e): e for e in lire_existants(conn, sn_id)}
    res = {"crees": 0, "maj": 0, "inchanges": 0, "retires": []}
    vus = set()
    for v in voulus:
        k = cle(v)
        vus.add(k)
        e = existants.get(k)
        if e is None:
            conn.execute(
                f"INSERT INTO {TABLE} (id, partie_id, objectif_id, niveau, sequence, position, "
                "exercice_id, exercice, type, titre, texte, solution, largeur, source, ordre, "
                "mtime) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (nid(), v["partie_id"], v.get("objectif_id") or None, niveau, sequence,
                 v["position"], v.get("exercice_id") or "", v.get("exercice") or "", v["type"],
                 v["titre"], v["texte"], v["solution"], v["largeur"], v["source"],
                 int(v.get("ordre") or 0), maintenant()))
            res["crees"] += 1
        elif any((e.get(c) or "") != (v.get(c) or "") for c in CHAMPS_CONTENU):
            conn.execute(
                f"UPDATE {TABLE} SET " + ", ".join(f"{c}=?" for c in CHAMPS_CONTENU)
                + ", mtime=? WHERE id=?",
                (*[(v.get(c) or "") for c in CHAMPS_CONTENU], maintenant(), e["id"]))
            res["maj"] += 1
        else:
            res["inchanges"] += 1
    for k, e in existants.items():
        if k not in vus:
            conn.execute(f"DELETE FROM {TABLE} WHERE id=?", (e["id"],))
            res["retires"].append(e)
    return res


def max_mtime(conn: sqlite3.Connection, niveau: str) -> str | None:
    if not table_presente(conn):
        return None
    r = conn.execute(f"SELECT MAX(mtime) FROM {TABLE} WHERE niveau=?", (niveau,)).fetchone()
    return r[0] if r and r[0] else None
