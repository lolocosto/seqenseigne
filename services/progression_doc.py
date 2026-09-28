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


def ajouter(conn, *, prog_kind: str, prog_ref: str, creneau_ref: str,
            rang_seance: int, doc_source: str, doc_ref: str,
            doc_libelle: str = "") -> dict:
    if prog_kind not in ("principale", "mer"):
        raise ValueError(f"prog_kind invalide : {prog_kind!r}")
    if doc_source not in ("interne", "externe"):
        raise ValueError(f"doc_source invalide : {doc_source!r}")
    did = _rid()
    n = conn.execute(
        "SELECT COALESCE(MAX(ordre), -1) + 1 FROM progression_doc "
        "WHERE prog_kind=? AND prog_ref=? AND creneau_ref=?",
        (prog_kind, prog_ref, creneau_ref)).fetchone()[0]
    conn.execute(
        "INSERT INTO progression_doc (id, prog_kind, prog_ref, creneau_ref, "
        "rang_seance, doc_source, doc_ref, doc_libelle, ordre) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (did, prog_kind, prog_ref, creneau_ref, int(rang_seance or 1),
         doc_source, doc_ref, doc_libelle, n))
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
    return docs


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
