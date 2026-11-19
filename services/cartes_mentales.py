r"""services/cartes_mentales.py — v0.55.0

Cartes mentales de partie (modèle « Fiches de résumé par objectif »),
demande de Laurent du 12 novembre 2026 : une carte mentale par partie de
séquence principale, à compléter dans le livret élève, complète dans le
livret corrigé, compilable seule (onglet « Rendu PDF », « Tout compiler »).
Format commun : environnement `seqCarteMentaleSix` et `\seqCMBranche` du
module `seqenseigne-style6e` v0.13.

Décisions (doc/redemarrage_v0_55_0.md) :

  - CM-TABLE — Une table dédiée `cartes_mentales`, une ligne par partie
    (`partie_id` UNIQUE → `sequence_parties`, suppression en cascade) :
    titre, source LaTeX (une seule ; les versions élève et complète viennent
    de `\seqVersionACompleter` / `\seqVersionComplete`), état d'édition
    (`en_cours` / `valide`, comme les atomes), `mtime` (péremption des
    documents publiés) et `niveau`, `sequence` dénormalisés (requêtes par
    séquence, comme `fiches_resume`). Pas une fiche de résumé d'un autre type :
    tout ce qui énumère les fiches (livret, fiches de cours, plan de travail,
    synthèse Pronote, format d'échange, contrôle « fiche exigée ») aurait dû
    l'écarter.
  - CM-LIVRET — La carte est émise en fin de partie (après les exercices de
    la partie), sur une nouvelle page ; une séquence sans carte produit
    exactement le même `.tex` qu'avant.
  - CM-CONTROLE — Une source est acceptée si elle contient un et un seul
    environnement `seqCarteMentaleSix`, au moins une branche, et seulement
    des macros `\seq…` connues du module (services/style6e.py) ; de 4 à 8
    branches conseillées (avertissement au-delà).
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone

TABLE = "cartes_mentales"
ENV = "seqCarteMentaleSix"
BRANCHE = "seqCMBranche"
ETATS = ("en_cours", "valide")
BRANCHES_CONSEILLEES = (4, 8)
BRANCHES_MAX = 16                      # limite du module (v0.13)

# v0.56.1 — Modèle proposé pour une partie sans carte (atelier « Carte mentale ») ;
# une seule source, servie par l'API (auparavant dupliqué dans le JS).
MODELE = ("\\begin{seqCarteMentaleSix}{Titre central}\n"
          "  \\seqCMBranche{Branche 1}{contenu avec un \\seqACompleter{trou}}\n"
          "  \\seqCMBranche{Branche 2}{contenu}\n"
          "  \\seqCMBranche{Branche 3}{contenu}\n"
          "  \\seqCMBranche{Branche 4}{contenu}\n"
          "\\end{seqCarteMentaleSix}")

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id         TEXT PRIMARY KEY,                    -- 'cm_xxxxxxxx'
    partie_id  TEXT NOT NULL UNIQUE
               REFERENCES sequence_parties(id) ON DELETE CASCADE,
    niveau     TEXT NOT NULL DEFAULT '',
    sequence   TEXT NOT NULL DEFAULT '',
    titre      TEXT NOT NULL DEFAULT '',
    latex      TEXT NOT NULL DEFAULT '',
    etat_code  TEXT NOT NULL DEFAULT 'en_cours',
    mtime      TEXT NOT NULL DEFAULT ''
)"""


class CarteMentaleErreur(ValueError):
    def __init__(self, message: str, code: str = "carte_invalide"):
        super().__init__(message)
        self.code = code


# ── Migration ────────────────────────────────────────────────────────────────

def table_presente(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (TABLE,)).fetchone() is not None


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


# ── Contrôle de la source (CM-CONTROLE) ─────────────────────────────────────

RE_MACRO_SEQ = re.compile(r"\\(seq[A-Za-z]+)")


def nb_branches(latex: str) -> int:
    return len(re.findall(r"\\" + BRANCHE + r"(?![A-Za-z])", latex or ""))


def controler_latex(latex: str, macros_locales: set | None = None) -> tuple[list, list]:
    r"""(erreurs, avertissements) d'une source de carte mentale.

    Erreurs : pas exactement un `\begin{seqCarteMentaleSix}` et un `\end` ;
    aucune branche ou plus de 16 ; macro `\seq…` inconnue du module (sauf
    `macros_locales`, définies par le lot). Avertissement : hors 4 à 8
    branches."""
    from services import style6e
    erreurs, avert = [], []
    src = latex or ""
    debut = len(re.findall(r"\\begin\s*\{" + ENV + r"\}", src))
    fin = len(re.findall(r"\\end\s*\{" + ENV + r"\}", src))
    if debut != 1 or fin != 1:
        erreurs.append(f"environnement {ENV} : {debut} début(s), {fin} fin(s) (un seul attendu)")
    n = nb_branches(src)
    if n == 0:
        erreurs.append(f"aucune branche (\\{BRANCHE})")
    elif n > BRANCHES_MAX:
        erreurs.append(f"{n} branches ({BRANCHES_MAX} au plus)")
    elif not BRANCHES_CONSEILLEES[0] <= n <= BRANCHES_CONSEILLEES[1]:
        avert.append(f"{n} branches (4 à 8 conseillées)")
    connues = set(style6e.MACROS) | set(style6e.ENVIRONNEMENTS) | set(macros_locales or ())
    inconnues = sorted({m for m in RE_MACRO_SEQ.findall(src)} - connues)
    if inconnues:
        erreurs.append("macros inconnues du module " + style6e.VERSION + " : "
                       + ", ".join("\\" + m for m in inconnues))
    return erreurs, avert


# ── Lecture ──────────────────────────────────────────────────────────────────

def _dict(r) -> dict:
    return {k: r[k] for k in r.keys()}


def lire_partie(conn: sqlite3.Connection, partie_id: str) -> dict | None:
    if not table_presente(conn):
        return None
    r = conn.execute(f"SELECT * FROM {TABLE} WHERE partie_id = ?", (partie_id,)).fetchone()
    return _dict(r) if r else None


def cartes_de_sequence(conn: sqlite3.Connection, niveau: str, sequence: str) -> dict:
    """{numéro de partie: carte} de la séquence-niveau ({} sans table)."""
    if not table_presente(conn):
        return {}
    rows = conn.execute(
        f"SELECT c.*, p.numero AS partie_numero FROM {TABLE} c "
        "JOIN sequence_parties p ON p.id = c.partie_id "
        "JOIN sequences_par_niveau s ON s.id = p.sequence_par_niveau_id "
        "WHERE s.niveau = ? AND s.sequence_code = ? ORDER BY p.numero",
        (niveau, sequence)).fetchall()
    return {int(r["partie_numero"]): _dict(r) for r in rows}


def parties_de_sequence(conn: sqlite3.Connection, niveau: str, sequence: str) -> list[dict]:
    """Pour l'atelier : [{numero, partie_id, libelle, carte|None}] de la
    séquence-niveau, dans l'ordre des parties."""
    sn = conn.execute("SELECT id, etat_code FROM sequences_par_niveau WHERE niveau = ? "
                      "AND sequence_code = ?", (niveau, sequence)).fetchone()
    if sn is None:
        raise CarteMentaleErreur(f"{niveau}/{sequence} : séquence absente de l'atelier",
                                 "sequence_introuvable")
    cartes = cartes_de_sequence(conn, niveau, sequence)
    from services.livret_sequence_6e import libelles_parties
    libelles = libelles_parties(niveau, sequence)
    out = []
    for p in conn.execute("SELECT id, numero FROM sequence_parties WHERE "
                          "sequence_par_niveau_id = ? ORDER BY numero", (sn["id"],)).fetchall():
        c = cartes.get(int(p["numero"]))
        out.append({"numero": int(p["numero"]), "partie_id": p["id"],
                    "libelle": libelles.get(int(p["numero"]), ""),
                    "carte": ({k: c[k] for k in ("id", "titre", "latex", "etat_code", "mtime")}
                              if c else None)})
    return out


def parties_du_niveau(conn: sqlite3.Connection, niveau: str) -> list[dict]:
    """v0.56.2 — Atelier en mode « toutes les séquences » : pour chaque séquence
    principale du niveau (sans archives Xnn ni mises en route Mnn, qui n'ont pas
    de carte mentale), dans l'ordre des codes : {sequence, modifiable, parties}
    (parties au format de parties_de_sequence)."""
    from services.livret_sequence_6e import sequences_du_niveau
    out = []
    for code in sequences_du_niveau(conn, niveau):
        sn = conn.execute("SELECT etat_code FROM sequences_par_niveau WHERE niveau = ? "
                          "AND sequence_code = ?", (niveau, code)).fetchone()
        out.append({"sequence": code,
                    "modifiable": bool(sn) and sn["etat_code"] != "valide",
                    "parties": parties_de_sequence(conn, niveau, code)})
    return out


def element_atelier(partie: dict, niveau: str, sequence: str,
                    modifiable: bool = True) -> dict:
    """v0.56.1 — Élément de l'atelier « Carte mentale » (contrat d'AtelierEditeur) :
    une entrée par partie, `id` = numéro de la partie (une partie sans carte a
    aussi un identifiant), `presente`, et pour une partie sans carte le modèle
    proposé (`latex` = MODELE, état « en_cours »)."""
    c = partie.get("carte")
    latex = c["latex"] if c else MODELE
    return {"id": str(partie["numero"]), "numero": partie["numero"],
            "partie_id": partie["partie_id"], "libelle": partie.get("libelle", ""),
            "niveau": niveau, "sequence": sequence, "presente": bool(c),
            "carte_id": c["id"] if c else None, "titre": c["titre"] if c else "",
            "latex": latex, "etat_code": c["etat_code"] if c else "en_cours",
            "branches": nb_branches(latex) if c else 0, "modifiable": modifiable}


def parties_sans_carte(conn: sqlite3.Connection, sn_id: str) -> list[int]:
    """Numéros des parties de la séquence-niveau qui n'ont pas de carte."""
    rows = conn.execute("SELECT id, numero FROM sequence_parties WHERE "
                        "sequence_par_niveau_id = ? ORDER BY numero", (sn_id,)).fetchall()
    if not table_presente(conn):
        return [int(r["numero"]) for r in rows]
    avec = {r[0] for r in conn.execute(
        f"SELECT partie_id FROM {TABLE} WHERE partie_id IN (SELECT id FROM sequence_parties "
        "WHERE sequence_par_niveau_id = ?)", (sn_id,))}
    return [int(r["numero"]) for r in rows if r["id"] not in avec]


# ── Écriture ─────────────────────────────────────────────────────────────────

def _partie(conn, partie_id: str):
    r = conn.execute("SELECT p.id, p.numero, s.niveau, s.sequence_code, s.etat_code "
                     "FROM sequence_parties p JOIN sequences_par_niveau s "
                     "ON s.id = p.sequence_par_niveau_id WHERE p.id = ?",
                     (partie_id,)).fetchone()
    if r is None:
        raise CarteMentaleErreur(f"partie {partie_id!r} introuvable", "partie_introuvable")
    return r


def enregistrer(conn: sqlite3.Connection, partie_id: str, titre: str, latex: str,
                etat_code: str | None = None, *, forcer_valide: bool = False,
                macros_locales: set | None = None) -> tuple[str, str]:
    """Crée ou met à jour la carte de la partie ; (id, état) avec état parmi
    « créée », « mise à jour », « inchangée », « validée, non modifiée ».

    Une carte validée n'est modifiée que si on la repasse en cours
    (`etat_code='en_cours'`) ou avec `forcer_valide` ; l'import ne force
    jamais. La source est contrôlée (CM-CONTROLE) : erreur → CarteMentaleErreur."""
    migrer(conn)
    p = _partie(conn, partie_id)
    titre = (titre or "").strip()
    latex = (latex or "").strip()
    erreurs, _ = controler_latex(latex, macros_locales)
    if erreurs:
        raise CarteMentaleErreur("; ".join(erreurs))
    if etat_code is not None and etat_code not in ETATS:
        raise CarteMentaleErreur(f"état inconnu : {etat_code!r}", "etat_invalide")
    r = conn.execute(f"SELECT * FROM {TABLE} WHERE partie_id = ?", (partie_id,)).fetchone()
    if r is None:
        cid = "cm_" + uuid.uuid4().hex[:8]
        conn.execute(f"INSERT INTO {TABLE} (id, partie_id, niveau, sequence, titre, latex, "
                     "etat_code, mtime) VALUES (?,?,?,?,?,?,?,?)",
                     (cid, partie_id, p["niveau"], p["sequence_code"], titre, latex,
                      etat_code or "en_cours", maintenant()))
        return cid, "créée"
    etat_final = etat_code or r["etat_code"]
    if (r["titre"], r["latex"], r["etat_code"]) == (titre, latex, etat_final):
        return r["id"], "inchangée"
    if r["etat_code"] == "valide" and etat_final == "valide" and not forcer_valide:
        return r["id"], "validée, non modifiée"
    conn.execute(f"UPDATE {TABLE} SET titre = ?, latex = ?, etat_code = ?, niveau = ?, "
                 "sequence = ?, mtime = ? WHERE id = ?",
                 (titre, latex, etat_final, p["niveau"], p["sequence_code"], maintenant(),
                  r["id"]))
    return r["id"], "mise à jour"


def supprimer(conn: sqlite3.Connection, partie_id: str) -> bool:
    if not table_presente(conn):
        return False
    return conn.execute(f"DELETE FROM {TABLE} WHERE partie_id = ?",
                        (partie_id,)).rowcount > 0


# ── Rendu LaTeX ──────────────────────────────────────────────────────────────

def titre_page(numero: int, libelle: str = "") -> str:
    r"""Titre de la page de la carte : « Carte mentale --- Partie n »."""
    return (r"\begin{center}{\Large\bfseries\color{seqSixVert}Carte mentale --- Partie "
            + str(numero) + "}\\end{center}")


def emettre(L: list, carte: dict, numero: int) -> None:
    """CM-LIVRET — page de la carte : nouvelle page, titre, source."""
    L.append(r"\clearpage")
    L.append(titre_page(numero))
    L.append(carte.get("latex") or "")


def generer_cartes_mentales_6e(conn: sqlite3.Connection, niveau: str,
                               sequence: str | None = None, options: dict | None = None,
                               tikz_libraries=None, tblr_libraries=None) -> str:
    r"""Document « Cartes mentales » : les cartes d'une séquence (ou de toutes
    les séquences du niveau, `sequence=None`), une par page. Option `version` :
    `eleve` (à compléter, défaut) ou `corrigee` / `complete` (complète) ;
    option `partie` (numéro) : la carte de cette partie seulement."""
    from services.livret_sequence_6e import (Livret6eErreur, _nom_sequence, _sequences_cible,
                                             document)
    o = options or {}
    version = o.get("version") or "eleve"
    if version not in ("eleve", "corrigee", "complete"):
        raise Livret6eErreur(f"version invalide : {version!r}")
    partie = int(o["partie"]) if str(o.get("partie") or "").strip() not in ("", "0") else None
    corps: list[str] = []
    for code in _sequences_cible(conn, niveau, sequence):
        cartes = cartes_de_sequence(conn, niveau, code)
        if not cartes:
            continue
        # v0.55.0 — tout modèle de référentiel (Fiches et Notions et méthodes) :
        # nom de la séquence dans le cycle du niveau, cartes dans l'ordre des parties.
        nom = _nom_sequence(conn, niveau, code)[0] or code
        lignes = []
        for numero, c in sorted(cartes.items()):
            if partie is not None and numero != partie:
                continue
            emettre(lignes, c, numero)
        if lignes:
            # lignes[0] = \clearpage : l'en-tête de la séquence est posé après le
            # saut de page (sinon la dernière page de la séquence précédente le
            # prendrait) ; pas de page blanche en tête du document.
            if corps:
                corps.append(lignes[0])
            corps.append(r"\fancyhead[R]{\small\bfseries " + nom
                         + r" -- page \thepage}")
            corps += lignes[1:]
    if not corps:
        raise Livret6eErreur(f"Aucune carte mentale pour {niveau} {sequence or ''}"
                             + (f" partie {partie}" if partie else "") + ".")
    corps.insert(0, r"\seqVersionComplete" if version != "eleve" else r"\seqVersionACompleter")
    from services.livret_sequence_6e import niveau_court
    titre = f"Cartes mentales {niveau_court(conn, niveau)} — {sequence or 'annuel'}"
    return document(conn, niveau, titre, corps, False, tikz_libraries, tblr_libraries)
