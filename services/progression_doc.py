"""services/progression_doc.py — v0.32.5

Association de documents à distribuer à un point de la progression, au NIVEAU
(pas par classe). Un doc est rattaché à (type de progression, progression,
créneau/partie, rang de séance). Toutes les classes du niveau en héritent ;
les décalages réels restent gérés par les indisponibilités.

Sources de documents (toutes existantes) :
  - interne (référentiel principal) : documents compilés par cible séquence, ou
    annuels (cible « unique ») — cartes d'automatisme incluses via le type
    `livret_cartes_planches`.
  - externe (référentiel principal OU MER) : docs de partie (séquence) et docs
    annuels.

Les référentiels MER internes n'existent pas encore (cf. ROADMAP).
"""

from __future__ import annotations
import uuid


def _rid() -> str:
    return "pgd_" + uuid.uuid4().hex[:12]


# ── Associations : CRUD ──────────────────────────────────────────────────────

def lister(conn, prog_kind: str, prog_ref: str,
           creneau_ref: str | None = None) -> list:
    """Associations d'une progression (optionnellement filtrées par créneau)."""
    if creneau_ref is None:
        rows = conn.execute(
            "SELECT * FROM progression_doc WHERE prog_kind=? AND prog_ref=? "
            "ORDER BY creneau_ref, rang_seance, ordre", (prog_kind, prog_ref)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM progression_doc WHERE prog_kind=? AND prog_ref=? "
            "AND creneau_ref=? ORDER BY rang_seance, ordre",
            (prog_kind, prog_ref, creneau_ref)).fetchall()
    return [dict(r) for r in rows]


# v0.48.0 — Retour attendu d'un document associé et délai de réalisation.
RETOURS = ("", "faire", "rendre")
DELAIS = ("", "prochaine", "jours", "semaines", "fin_creneau")


def migrer_v0_48(conn) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(progression_doc)")}
    for nom, decl in (("retour", "TEXT NOT NULL DEFAULT ''"),
                      ("delai_type", "TEXT NOT NULL DEFAULT ''"),
                      ("delai_n", "INTEGER NOT NULL DEFAULT 1")):
        if cols and nom not in cols:
            conn.execute(f"ALTER TABLE progression_doc ADD COLUMN {nom} {decl}")


def _valider_retour(retour: str, delai_type: str, delai_n) -> tuple:
    retour = retour or ""
    if retour not in RETOURS:
        raise ValueError(f"retour invalide : {retour!r}")
    if not retour:
        return "", "", 1
    delai_type = delai_type or "prochaine"
    if delai_type not in DELAIS[1:]:
        raise ValueError(f"délai invalide : {delai_type!r}")
    try:
        n = max(1, int(delai_n or 1))
    except (TypeError, ValueError):
        raise ValueError(f"nombre invalide : {delai_n!r}")
    return retour, delai_type, n


def delai_en_jours(delai_type: str, delai_n: int) -> int:
    """Délai en jours (prochaine séance = 1) ; 0 pour « fin du créneau »
    (échéance fixe, calculée à part)."""
    return {"prochaine": 1, "jours": int(delai_n or 1),
            "semaines": 7 * int(delai_n or 1)}.get(delai_type, 0)


def modifier_retour(conn, assoc_id: str, retour: str, delai_type: str = "",
                    delai_n: int = 1) -> dict:
    r = conn.execute("SELECT * FROM progression_doc WHERE id=?", (assoc_id,)).fetchone()
    if r is None:
        raise ValueError("Association introuvable.")
    retour, delai_type, n = _valider_retour(retour, delai_type, delai_n)
    conn.execute("UPDATE progression_doc SET retour=?, delai_type=?, delai_n=? WHERE id=?",
                 (retour, delai_type, n, assoc_id))
    return dict(conn.execute("SELECT * FROM progression_doc WHERE id=?",
                             (assoc_id,)).fetchone())


def ajouter(conn, *, prog_kind: str, prog_ref: str, creneau_ref: str,
            rang_seance: int, doc_source: str, doc_ref: str,
            doc_libelle: str = "", retour: str = "", delai_type: str = "",
            delai_n: int = 1) -> dict:
    if prog_kind not in ("principale", "mer"):
        raise ValueError(f"prog_kind invalide : {prog_kind!r}")
    if doc_source not in ("interne", "externe"):
        raise ValueError(f"doc_source invalide : {doc_source!r}")
    retour, delai_type, delai_n = _valider_retour(retour, delai_type, delai_n)
    did = _rid()
    n = conn.execute(
        "SELECT COALESCE(MAX(ordre), -1) + 1 FROM progression_doc "
        "WHERE prog_kind=? AND prog_ref=? AND creneau_ref=?",
        (prog_kind, prog_ref, creneau_ref)).fetchone()[0]
    conn.execute(
        "INSERT INTO progression_doc (id, prog_kind, prog_ref, creneau_ref, "
        "rang_seance, doc_source, doc_ref, doc_libelle, ordre, retour, delai_type, "
        "delai_n) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (did, prog_kind, prog_ref, creneau_ref, int(rang_seance or 1),
         doc_source, doc_ref, doc_libelle, n, retour, delai_type, delai_n))
    return dict(conn.execute("SELECT * FROM progression_doc WHERE id=?",
                             (did,)).fetchone())


def supprimer(conn, assoc_id: str) -> None:
    conn.execute("DELETE FROM progression_doc WHERE id=?", (assoc_id,))


# ── Documents disponibles pour une séquence (les sources) ────────────────────

def documents_disponibles(conn, niveau: str, annee: str, sequence: str,
                          sequence_suivante: str | None = None) -> dict:
    """Documents proposables pour un créneau dont la séquence est `sequence`.

    Retour : {
      "sequence":   [ {source, doc_ref, libelle, categorie:'sequence'}, ... ],
      "suivante":   [ ... ]  (docs de la séquence suivante, si fournie),
      "annuels":    [ ... ],
    }
    Couvre : interne (réf. principal, par cible), externe (réf. principal ET
    MER, docs de partie + annuels).
    """
    seq = _docs_pour_sequence(conn, niveau, annee, sequence)
    suiv = (_docs_pour_sequence(conn, niveau, annee, sequence_suivante)
            if sequence_suivante else [])
    annuels = _docs_annuels(conn, niveau, annee)
    return {"sequence": seq, "suivante": suiv, "annuels": annuels}


def _docs_pour_sequence(conn, niveau: str, annee: str, sequence: str) -> list:
    docs = []
    docs.extend(_docs_internes(conn, niveau, sequence, annuels=False))
    docs.extend(_docs_externes(conn, niveau, annee, sequence, annuels=False))
    docs.extend(_docs_principal_externe(conn, niveau, annee, sequence))   # v0.48.2
    return docs


def _docs_principal_externe(conn, niveau: str, annee: str, sequence: str) -> list:
    """v0.48.2 — Fichiers déposés dans un référentiel principal externe
    (structure figée, source externe) pour cette séquence."""
    from services import referentiel_principal_externe as rpe
    try:
        fichiers = rpe.fichiers_de_sequence(conn, niveau, annee, sequence)
    except Exception:
        return []
    return [{"source": "externe", "doc_ref": f["id"],
             "libelle": f["nom_fichier"] + (f" (partie {f['partie_numero']})"
                                            if f["partie_numero"] else ""),
             "categorie": "sequence"} for f in fichiers]


def _docs_annuels(conn, niveau: str, annee: str) -> list:
    docs = []
    docs.extend(_docs_internes(conn, niveau, "", annuels=True))
    docs.extend(_docs_externes(conn, niveau, annee, "", annuels=True))
    return docs


# ── Source interne (référentiel principal) ───────────────────────────────────

def _docs_internes(conn, niveau: str, sequence: str, annuels: bool) -> list:
    """Documents du référentiel principal INTERNE du niveau. Chaque document
    compilable a des cibles : soit par séquence (cible_id = 'N11/S05'), soit
    unique (annuel). On expose une entrée par (document, cible pertinente)."""
    from services import referentiel_documents as rd
    from services.referentiel_documents_compilation import (
        lister_cibles_document)
    # Référentiel principal interne du niveau (le plus récent non archivé).
    ref = conn.execute(
        "SELECT id FROM referentiel_niveaux WHERE niveau=? "
        "AND COALESCE(source, 'interne') <> 'externe' "
        "ORDER BY id DESC LIMIT 1", (niveau,)).fetchone()
    if ref is None:
        return []
    ref_id = ref["id"]
    out = []
    try:
        documents = rd.lister_documents(conn, ref_id)
    except Exception:
        documents = []
    for doc in documents:
        type_doc = doc.get("type_document", "")
        try:
            cibles = lister_cibles_document(conn, doc["id"], ref_id, type_doc)
        except Exception:
            cibles = []
        for c in cibles:
            cid = c.get("cible_id", "")
            est_annuel = (cid == "unique")
            if annuels and not est_annuel:
                continue
            if not annuels:
                # ne garder que la cible de la séquence demandée
                if est_annuel or not cid.endswith("/" + sequence):
                    continue
            libelle = _libelle_type_doc(type_doc)
            if not est_annuel:
                libelle += f" — {sequence}"
            out.append({
                "source": "interne",
                "doc_ref": f"{type_doc}|{cid}",
                "libelle": libelle,
                "categorie": "annuel" if est_annuel else "sequence",
            })
    return out


_LIBELLES_TYPE_DOC = {
    "livret_sequence": "Livret de séquence",
    "livret_cours": "Livret de cours",
    "livret_fiches": "Livret de fiches",
    "livret_plans": "Livret de plans de travail",
    "livret_corriges": "Livret de corrigés",
    "livret_exercices": "Livret d'exercices",
    "livret_cartes_planches": "Planches de cartes d'automatisme",
    "livret_cartes_recap": "Récap des cartes d'automatisme",
    "evaluation": "Évaluation",
}


def _libelle_type_doc(type_doc: str) -> str:
    return _LIBELLES_TYPE_DOC.get(type_doc, type_doc)


# ── Source externe (référentiel principal OU MER) ────────────────────────────

def _docs_externes(conn, niveau: str, annee: str, sequence: str,
                   annuels: bool) -> list:
    """Documents des référentiels externes du niveau (principal et MER)."""
    from services import referentiel_externe as rx
    refs = conn.execute(
        "SELECT id, nom, type FROM referentiel_externe WHERE niveau=?",
        (niveau,)).fetchall()
    out = []
    for r in refs:
        ref_id = r["id"]
        try:
            full = rx.lire(conn, ref_id)
        except Exception:
            continue
        if annuels:
            for d in full.get("docs_annuels", []):
                out.append({
                    "source": "externe",
                    "doc_ref": d["id"],
                    "libelle": f"{r['nom']} — {d['nom_fichier']}",
                    "categorie": "annuel",
                })
        else:
            # docs des parties dont la séquence correspond
            for seqx in full.get("sequences", []):
                if (seqx.get("code") or "") != sequence:
                    continue
                for part in seqx.get("parties", []):
                    for d in part.get("docs", []):
                        out.append({
                            "source": "externe",
                            "doc_ref": d["id"],
                            "libelle": f"{r['nom']} — {d['nom_fichier']}",
                            "categorie": "sequence",
                        })
    return out
