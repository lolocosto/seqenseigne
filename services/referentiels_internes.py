"""services/referentiels_internes.py — v0.54.0

Référentiels internes (conçus dans l'atelier) d'un niveau : **périmètre**
selon le type, **instantané** complet au verrouillage, **aperçu** avant la
création. Audit et décisions : doc/redemarrage_v0_54_0.md
(SP/livraison_v0540/audit_referentiels.md).

Décisions :

  - RI1 — Périmètre d'un référentiel interne, selon son type :
      * principal : les séquences du niveau sauf les archives `Xnn` et les
        mises en route `Mnn` (`mises_en_route_6e.hors_principal`, MR7) ;
      * mise en route (`type_ref = 'mer'`) : les séquences `Mnn` seulement.
    Au cycle 4, il n'y a ni `Xnn` ni `Mnn` : le périmètre du principal est
    tout le niveau, comme avant. Tout ce qui énumère le contenu d'un
    référentiel interne (arbre de l'atelier, éligibilité, instantané, trace,
    documents) passe par `sequences_du_perimetre`.
  - RI2 — Instantané complet au verrouillage : thèmes, séquences, parties
    (avec libellé) et objectifs (critères, séances, type) du périmètre sont
    recopiés dans les tables `referentiel_*`, qu'aucun écran ne remplissait
    pour un référentiel créé dans l'appli (sa publication était vide).
    Marqué `referentiel_niveaux.instantane = 'atelier'` : recalculé à chaque
    verrouillage, retiré entier au déverrouillage. Un référentiel dont
    l'instantané vient d'ailleurs (import historique, N11_v2025…) garde le
    mécanisme d'avant (parties seulement).
  - RI3 — Numéro d'une séquence dans l'instantané : celui du cycle pour le
    principal (S01 → 1) ; pour une mise en route, son numéro de mise en
    route (M03 → 3, et non 203).
  - RI4 — Durée d'une partie de mise en route = somme des séances de ses
    objectifs (un bloc de N séances consécutives côté classe) ; au principal,
    la durée saisie sur la partie, comme avant.
"""

from __future__ import annotations

import sqlite3

TYPES_REF = ("principal", "mer")
LIBELLES_TYPES = {"principal": "Référentiel principal",
                  "mer": "Référentiel de mises en route"}
INSTANTANE_ATELIER = "atelier"


# ── Migration ────────────────────────────────────────────────────────────────

def migrer(conn) -> bool:
    """`referentiel_niveaux.instantane` (TEXT, '' par défaut) ; idempotente ;
    True si la colonne vient d'être ajoutée."""
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_niveaux)")}
    except sqlite3.Error:
        return False
    if cols and "instantane" not in cols:
        conn.execute("ALTER TABLE referentiel_niveaux ADD COLUMN instantane "
                     "TEXT NOT NULL DEFAULT ''")
        return True
    return False


def _colonne(conn, table: str, col: str) -> bool:
    try:
        return col in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return False


# ── RI1 Périmètre ────────────────────────────────────────────────────────────

def type_du_referentiel(conn, ref_id: str) -> str:
    r = conn.execute("SELECT type_ref FROM referentiel_niveaux WHERE id = ?",
                     (ref_id,)).fetchone()
    t = (r[0] if r else None) or "principal"
    return t if t in TYPES_REF else "principal"


def dans_perimetre(sequence_code: str | None, type_ref: str | None) -> bool:
    """RI1 — la séquence appartient-elle au périmètre de ce type ?"""
    from services.mises_en_route_6e import est_sequence_mer, hors_principal
    if (type_ref or "principal") == "mer":
        return est_sequence_mer(sequence_code)
    return not hors_principal(sequence_code)


def sequences_du_perimetre(conn, niveau: str, type_ref: str | None) -> list[dict]:
    """[{sn_id, code, numero, numero_cycle, nom, theme_code, theme_nom,
    theme_couleur, etat_code}] des séquences du niveau dans le périmètre, dans
    l'ordre du cycle (RI3 : `numero` = numéro de mise en route pour une Mnn)."""
    from services.mises_en_route_6e import est_sequence_mer, numero_mer
    rows = conn.execute("""
        SELECT sn.id AS sn_id, sn.sequence_code AS code, sn.etat_code,
               sdc.numero, sdc.nom, t.code AS theme_code, t.nom AS theme_nom,
               t.code_couleur AS theme_couleur
          FROM sequences_par_niveau sn
          JOIN param_niveaux pn ON pn.code = sn.niveau
          JOIN sequences_du_cycle sdc
            ON sdc.code = sn.sequence_code AND sdc.cycle_code = pn.cycle_code
          LEFT JOIN themes t ON t.id = sdc.theme_id
         WHERE sn.niveau = ?
         ORDER BY sdc.numero, sn.sequence_code
    """, (niveau,)).fetchall()
    out = []
    for r in rows:
        if not dans_perimetre(r["code"], type_ref):
            continue
        num = numero_mer(r["code"]) if est_sequence_mer(r["code"]) else int(r["numero"] or 0)
        out.append({"sn_id": r["sn_id"], "code": r["code"], "numero": num,
                    "numero_cycle": r["numero"], "nom": r["nom"] or "",
                    "theme_code": r["theme_code"], "theme_nom": r["theme_nom"] or "",
                    "theme_couleur": r["theme_couleur"] or "",
                    "etat_code": r["etat_code"] or "en_cours"})
    return out


def sequence_majoritaire_evaluation(conn, eval_id: str) -> str:
    """Séquence majoritaire des exercices d'une évaluation ('' sans exercice) —
    même règle que le rendu 6e et les tests courts."""
    from collections import Counter
    seqs = Counter(x[0] for x in conn.execute(
        "SELECT e.sequence FROM evaluation_exercices ee JOIN exercices e "
        "ON e.id = ee.exercice_id WHERE ee.evaluation_id = ? AND e.sequence <> ''",
        (eval_id,)))
    return seqs.most_common(1)[0][0] if seqs else ""


def evaluations_du_perimetre(conn, niveau: str, type_ref: str | None) -> list[dict]:
    """[{id, numero, titre, etat_code, sequence}] — RI1 : au principal, toutes
    les évaluations du niveau sauf celles des archives et des mises en route
    (tests courts) ; à la mise en route, ses tests courts seulement. Une
    évaluation sans exercice reste au principal (comme avant)."""
    out = []
    for r in conn.execute("SELECT id, numero, titre, etat_code FROM evaluations "
                          "WHERE niveau = ? ORDER BY ordre, numero, id", (niveau,)).fetchall():
        seq = sequence_majoritaire_evaluation(conn, r["id"])
        if (type_ref or "principal") == "mer":
            garder = dans_perimetre(seq, "mer")
        else:
            garder = (seq == "") or dans_perimetre(seq, "principal")
        if garder:
            out.append({"id": r["id"], "numero": r["numero"], "titre": r["titre"] or "",
                        "etat_code": r["etat_code"] or "en_cours", "sequence": seq})
    return out


# ── Contenu (aperçu avant création, détail du référentiel) ──────────────────

def contenu(conn, niveau: str, type_ref: str | None, gabarit: str | None = None) -> dict:
    """Ce qu'un référentiel interne de ce type contiendra : séquences, parties,
    objectifs (hors objectif « Cours »), documents du catalogue, et l'état de
    préparation (séquences validées, atomes et évaluations non validés)."""
    from services import gabarits_documents as gd
    from services.mises_en_route_6e import est_objectif_cours
    type_ref = type_ref if type_ref in TYPES_REF else "principal"
    g = gd.normaliser(gabarit) if gabarit else gd.gabarit_par_defaut(niveau)
    seqs = sequences_du_perimetre(conn, niveau, type_ref)
    nb_parties = nb_obj = nb_cours = 0
    seances = 0.0
    lignes = []
    for s in seqs:
        parties = conn.execute("SELECT id, numero FROM sequence_parties WHERE "
                               "sequence_par_niveau_id = ? ORDER BY numero",
                               (s["sn_id"],)).fetchall()
        n_obj = 0
        for p in parties:
            for o in conn.execute("SELECT code, nb_seances FROM objectifs WHERE partie_id = ?",
                                  (p["id"],)).fetchall():
                if est_objectif_cours(o["code"], p["numero"], s["code"]):
                    nb_cours += 1
                else:
                    n_obj += 1
                seances += float(o["nb_seances"] or 0)
        nb_parties += len(parties)
        nb_obj += n_obj
        lignes.append({"code": s["code"], "nom": s["nom"], "parties": len(parties),
                       "objectifs": n_obj, "validee": s["etat_code"] == "valide"})
    from services.referentiel_validation import compter_atomes_perimetre
    atomes = compter_atomes_perimetre(conn, niveau, g, type_ref)
    evals = evaluations_du_perimetre(conn, niveau, type_ref)
    catalogue = gd.catalogue_type(g, type_ref)
    return {
        "niveau": niveau, "type_ref": type_ref, "libelle_type": LIBELLES_TYPES[type_ref],
        "gabarit": g, "libelle_modele": gd.LIBELLES_GABARITS.get(g, g),
        "nb_sequences": len(seqs), "nb_parties": nb_parties, "nb_objectifs": nb_obj,
        "nb_objectifs_cours": nb_cours, "nb_seances": seances,
        "nb_sequences_validees": sum(1 for x in lignes if x["validee"]),
        "sequences": lignes,
        "atomes_non_valides": sum(atomes["non_valides"].values()),
        "atomes_total": sum(atomes["total"].values()),
        "nb_evaluations": len(evals),
        "evaluations_non_valides": sum(1 for e in evals if e["etat_code"] != "valide"),
        "documents": [{"cle": t.cle, "libelle": t.libelle} for t in catalogue],
    }


# ── RI2 Instantané complet ───────────────────────────────────────────────────

def instantane_du_referentiel(conn, ref_id: str) -> str:
    if not _colonne(conn, "referentiel_niveaux", "instantane"):
        return ""
    r = conn.execute("SELECT instantane FROM referentiel_niveaux WHERE id = ?",
                     (ref_id,)).fetchone()
    return (r[0] if r else "") or ""


def instantane_par_atelier(conn, ref_id: str) -> bool:
    """RI2 — l'instantané de ce référentiel est-il (ou sera-t-il) écrit par
    l'atelier au verrouillage ? Oui s'il a déjà été écrit ainsi, ou si le
    référentiel n'a encore aucune séquence figée (coquille créée dans
    l'appli). Non pour un référentiel construit autrement (import historique :
    son instantané est gardé, seules les parties sont recalculées)."""
    if instantane_du_referentiel(conn, ref_id) == INSTANTANE_ATELIER:
        return True
    r = conn.execute("SELECT source FROM referentiel_niveaux WHERE id = ?", (ref_id,)).fetchone()
    if r is None or (r[0] or "interne") == "externe":
        return False
    return conn.execute("SELECT 1 FROM referentiel_sequences WHERE referentiel_id = ? LIMIT 1",
                        (ref_id,)).fetchone() is None


_TABLES_INSTANTANE = ("referentiel_objectifs", "referentiel_parties",
                      "referentiel_sequences", "referentiel_themes")


def purger_instantane(conn, ref_id: str) -> None:
    for t in _TABLES_INSTANTANE:
        conn.execute(f"DELETE FROM {t} WHERE referentiel_id = ?", (ref_id,))


def ecrire_instantane(conn, ref_id: str) -> dict:
    """RI2 — (Ré)écrit l'instantané complet du référentiel depuis l'atelier
    (DELETE puis INSERT, idempotent). Retourne {nb_sequences, nb_parties,
    nb_objectifs, nb_themes}."""
    from services.mises_en_route_6e import est_objectif_cours, est_sequence_mer
    ref = conn.execute("SELECT niveau, type_ref FROM referentiel_niveaux WHERE id = ?",
                       (ref_id,)).fetchone()
    if ref is None:
        raise ValueError(f"Référentiel introuvable : {ref_id}")
    niveau, type_ref = ref["niveau"], (ref["type_ref"] or "principal")
    purger_instantane(conn, ref_id)
    seqs = sequences_du_perimetre(conn, niveau, type_ref)
    lib_partie = _colonne(conn, "sequence_parties", "libelle")
    col_lib_ref = _colonne(conn, "referentiel_parties", "libelle")
    col_type_obj = _colonne(conn, "referentiel_objectifs", "type_obj")
    col_ordre_th = _colonne(conn, "referentiel_themes", "ordre")
    # Thèmes d'abord : referentiel_sequences.theme_code les référence (clé
    # étrangère composite, contrôlée par les connexions de l'appli).
    themes: dict = {}
    for s in seqs:
        if s["theme_code"] and s["theme_code"] not in themes:
            themes[s["theme_code"]] = (s["theme_nom"], s["theme_couleur"])
    for i, (code, (nom, couleur)) in enumerate(sorted(themes.items()), start=1):
        if col_ordre_th:
            conn.execute("INSERT INTO referentiel_themes (referentiel_id, code, nom, couleur, "
                         "ordre) VALUES (?,?,?,?,?)", (ref_id, code, nom, couleur, i))
        else:
            conn.execute("INSERT INTO referentiel_themes (referentiel_id, code, nom, couleur) "
                         "VALUES (?,?,?,?)", (ref_id, code, nom, couleur))
    nb_p = nb_o = 0
    for s in seqs:
        conn.execute("INSERT INTO referentiel_sequences (referentiel_id, code, numero, nom, "
                     "theme_code) VALUES (?,?,?,?,?)",
                     (ref_id, s["code"], s["numero"], s["nom"], s["theme_code"]))
        for p in conn.execute("SELECT id, numero, nb_seances_R_AE"
                              + (", libelle" if lib_partie else ", '' AS libelle")
                              + " FROM sequence_parties WHERE sequence_par_niveau_id = ? "
                              "ORDER BY numero", (s["sn_id"],)).fetchall():
            objs = conn.execute("SELECT code, nom, fin_cycle, critere_F, critere_A, critere_E, "
                                "nb_seances FROM objectifs WHERE partie_id = ? ORDER BY code",
                                (p["id"],)).fetchall()
            # RI4 — durée d'une partie de mise en route = somme de ses objectifs.
            duree = (sum(float(o["nb_seances"] or 0) for o in objs)
                     if est_sequence_mer(s["code"]) else p["nb_seances_R_AE"])
            if col_lib_ref:
                conn.execute("INSERT INTO referentiel_parties (referentiel_id, seq_code, numero, "
                             "nb_seances_R_AE, libelle) VALUES (?,?,?,?,?)",
                             (ref_id, s["code"], p["numero"], duree, p["libelle"] or ""))
            else:
                conn.execute("INSERT INTO referentiel_parties (referentiel_id, seq_code, numero, "
                             "nb_seances_R_AE) VALUES (?,?,?,?)",
                             (ref_id, s["code"], p["numero"], duree))
            nb_p += 1
            for o in objs:
                fin = str(o["fin_cycle"] or "").strip().upper() in ("O", "1", "OUI", "TRUE")
                valeurs = [ref_id, s["code"], o["code"], o["nom"] or "", int(fin),
                           o["critere_F"] or "", o["critere_A"] or "", o["critere_E"] or "",
                           p["numero"], o["nb_seances"] or 0]
                cols = ("referentiel_id, seq_code, code, nom, fin_cycle, critere_f, critere_a, "
                        "critere_e, partie_numero, nb_seances")
                if col_type_obj:
                    cols += ", type_obj"
                    valeurs.append("connaissance" if est_objectif_cours(o["code"], p["numero"],
                                                                        s["code"])
                                   else "capacite")
                conn.execute(f"INSERT INTO referentiel_objectifs ({cols}) VALUES "
                             f"({','.join('?' * len(valeurs))})", valeurs)
                nb_o += 1
    if _colonne(conn, "referentiel_niveaux", "instantane"):
        conn.execute("UPDATE referentiel_niveaux SET instantane = ? WHERE id = ?",
                     (INSTANTANE_ATELIER, ref_id))
    return {"nb_sequences": len(seqs), "nb_parties": nb_p, "nb_objectifs": nb_o,
            "nb_themes": len(themes)}


# ── RI13 Publication figée au déverrouillage ─────────────────────────────────

def mettre_de_cote_publication(dossier_referentiel) -> str | None:
    """RI13 — Au déverrouillage d'un référentiel créé dans l'atelier, sa
    publication figée (`_publication/`, resservie à l'identique tant que le
    référentiel est verrouillé) est renommée `_publication_avant_<date>/` :
    le prochain verrouillage publiera le contenu corrigé (côté classe : une
    mise à jour). Retourne le nouveau nom, ou None s'il n'y avait rien."""
    import datetime
    from pathlib import Path
    d = Path(dossier_referentiel) / "_publication"
    if not d.is_dir():
        return None
    cible = d.with_name("_publication_avant_"
                        + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    d.rename(cible)
    return cible.name
