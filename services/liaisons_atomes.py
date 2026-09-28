"""services/liaisons_atomes.py — v0.13.6.10

Calcule les liens des atomes (objectifs et parties) pour l'affichage en
sidebar des ateliers d'atomes.

v0.13.6.10 — Refonte du format :
  - Renommé : `obj_lies` → `liens`
  - Plus de strings au format 'N10·S04·02' : maintenant objets typés :
      {type: 'obj', niveau, sequence, code}    # lien vers un objectif
      {type: 'part', niveau, sequence, numero} # lien vers une partie (R/EA)
  - Pour l'exercice, on inclut désormais les liens parties (table
    partie_exos_revision_approche). Avant, on ne consultait que
    objectif_exos, donc les exos utilisés en révision/approche dans
    une autre séquence n'étaient pas visibles dans leur sidebar.

Conventions :
  - Une notion peut être liée à plusieurs objectifs (M-N).
  - Une méthode est liée à au plus un objectif (1-1).
  - Un exercice peut être lié à plusieurs objectifs (M-N) ET à plusieurs
    parties (M-N) pour les rôles R (révision) / EA (approche).
  - Une fiche est liée à exactement un objectif (1-1), toujours dans
    la même séquence/niveau qu'elle.

Sources des liens :
  - notion : table objectif_notions
  - methode : objectifs.methode_id
  - exercice : tables objectif_exos + partie_exos_revision_approche
  - fiche : fiches_resume.objectif_id
"""

from __future__ import annotations
import sqlite3


def _lien_obj(niveau: str, sequence: str, code: str, nom: str = "") -> dict:
    """Construit un objet lien vers un objectif.

    v0.13.6.11 — Ajout du champ `nom` (= nom de l'objectif), utilisé par
    le bouton « reprendre titre objectif » côté UI (chantier B).
    Default '' pour permettre les appels sans nom (cas où l'objectif
    n'a pas encore de libellé renseigné).
    """
    return {
        "type":     "obj",
        "niveau":   niveau,
        "sequence": sequence,
        "code":     code,
        "nom":      nom,
    }


def _lien_part(niveau: str, sequence: str, numero: int) -> dict:
    """Construit un objet lien vers une partie (R/EA)."""
    return {
        "type":     "part",
        "niveau":   niveau,
        "sequence": sequence,
        "numero":   numero,
    }


def lister_liens_par_notion(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Retourne {notion_id: [lien_obj, ...]}."""
    rows = conn.execute("""
        SELECT
            on_.notion_id     AS atome_id,
            sn.niveau         AS niveau,
            sn.sequence_code  AS sequence,
            ob.code           AS code,
            ob.nom            AS nom
        FROM objectif_notions on_
        JOIN objectifs ob ON ob.id = on_.objectif_id
        JOIN sequence_parties p ON p.id = ob.partie_id
        JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id
        ORDER BY sn.niveau, sn.sequence_code, ob.code
    """).fetchall()
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["atome_id"], []).append(
            _lien_obj(r["niveau"], r["sequence"], r["code"], r["nom"] or "")
        )
    return out


def lister_liens_par_methode(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Retourne {methode_id: [lien_obj]} (au plus 1)."""
    rows = conn.execute("""
        SELECT
            ob.methode_id     AS atome_id,
            sn.niveau         AS niveau,
            sn.sequence_code  AS sequence,
            ob.code           AS code,
            ob.nom            AS nom
        FROM objectifs ob
        JOIN sequence_parties p ON p.id = ob.partie_id
        JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id
        WHERE ob.methode_id IS NOT NULL
        ORDER BY sn.niveau, sn.sequence_code, ob.code
    """).fetchall()
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["atome_id"], []).append(
            _lien_obj(r["niveau"], r["sequence"], r["code"], r["nom"] or "")
        )
    return out


def lister_liens_par_exercice(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Retourne {exercice_id: [lien_obj | lien_part, ...]}.

    Inclut DEUX sources :
      1. objectif_exos : liens objectifs directs (séries F/A/E)
      2. partie_exos_revision_approche : liens parties (rôles R/EA)
    """
    out: dict[str, list[dict]] = {}

    # 1. Liens objectifs
    rows = conn.execute("""
        SELECT
            oe.exercice_id    AS atome_id,
            sn.niveau         AS niveau,
            sn.sequence_code  AS sequence,
            ob.code           AS code,
            ob.nom            AS nom
        FROM objectif_exos oe
        JOIN objectifs ob ON ob.id = oe.objectif_id
        JOIN sequence_parties p ON p.id = ob.partie_id
        JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id
        ORDER BY sn.niveau, sn.sequence_code, ob.code
    """).fetchall()
    for r in rows:
        out.setdefault(r["atome_id"], []).append(
            _lien_obj(r["niveau"], r["sequence"], r["code"], r["nom"] or "")
        )

    # 2. Liens parties (R/EA) — v0.13.6.10
    rows = conn.execute("""
        SELECT
            pa.exercice_id    AS atome_id,
            sn.niveau         AS niveau,
            sn.sequence_code  AS sequence,
            p.numero          AS numero
        FROM partie_exos_revision_approche pa
        JOIN sequence_parties p ON p.id = pa.partie_id
        JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id
        ORDER BY sn.niveau, sn.sequence_code, p.numero
    """).fetchall()
    for r in rows:
        out.setdefault(r["atome_id"], []).append(
            _lien_part(r["niveau"], r["sequence"], r["numero"])
        )

    return out


def lister_liens_par_fiche(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Retourne {fiche_id: [lien_obj]} (1 par fiche)."""
    rows = conn.execute("""
        SELECT
            f.id              AS atome_id,
            sn.niveau         AS niveau,
            sn.sequence_code  AS sequence,
            ob.code           AS code,
            ob.nom            AS nom
        FROM fiches_resume f
        JOIN objectifs ob ON ob.id = f.objectif_id
        JOIN sequence_parties p ON p.id = ob.partie_id
        JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id
    """).fetchall()
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["atome_id"], []).append(
            _lien_obj(r["niveau"], r["sequence"], r["code"], r["nom"] or "")
        )
    return out


def lister_liens_par_carte(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """v0.13.6.13 — Retourne {carte_id: [lien_obj, ...]}.

    Une carte peut être liée à 0..N objectifs via la table de liaison
    objectif_cartes (introduite en v0.13.6.13 pour remplacer le couple
    legacy lien_type/lien_id). En pratique, l'usage métier de Laurent
    est 1:1 (une carte = un objectif), mais le modèle supporte le 1:N.

    Tri par niveau, séquence, code objectif pour un résultat stable et
    cohérent avec les autres atomes."""
    rows = conn.execute("""
        SELECT
            oc.carte_id       AS atome_id,
            sn.niveau         AS niveau,
            sn.sequence_code  AS sequence,
            ob.code           AS code,
            ob.nom            AS nom
        FROM objectif_cartes oc
        JOIN objectifs ob ON ob.id = oc.objectif_id
        JOIN sequence_parties p ON p.id = ob.partie_id
        JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id
        ORDER BY sn.niveau, sn.sequence_code, ob.code
    """).fetchall()
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["atome_id"], []).append(
            _lien_obj(r["niveau"], r["sequence"], r["code"], r["nom"] or "")
        )
    return out


def enrichir_liste_atomes(
    conn: sqlite3.Connection,
    liste: list[dict],
    type_atome: str,
) -> list[dict]:
    """Ajoute le champ `liens: [dict, ...]` à chaque atome de la liste.

    `type_atome` ∈ {'notion', 'methode', 'exercice', 'fiche', 'carte'}.
    Mute la liste sur place ET la retourne pour fluidité d'usage.

    v0.13.6.10 — Remplace `obj_lies` (strings) par `liens` (objets typés).
    v0.13.6.13 — Ajout du type 'carte' (alimenté par objectif_cartes).
    """
    if type_atome == 'notion':
        liens = lister_liens_par_notion(conn)
    elif type_atome == 'methode':
        liens = lister_liens_par_methode(conn)
    elif type_atome == 'exercice':
        liens = lister_liens_par_exercice(conn)
    elif type_atome == 'fiche':
        liens = lister_liens_par_fiche(conn)
    elif type_atome == 'carte':
        liens = lister_liens_par_carte(conn)
    else:
        raise ValueError(f"type_atome inconnu : {type_atome!r}")

    for atome in liste:
        atome['liens'] = liens.get(atome.get('id'), [])
    return liste
