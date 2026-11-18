r"""services/cartes_partie.py — v0.60.1

Cartes d'automatisme d'une partie de séquence, au modèle « Fiches de résumé
par objectif » avec l'option « cartes d'automatisme » (v0.59.0, D4) :
`doc/redemarrage_v0_60_1.md`.

  - **E9** — rubrique « Cartes d'automatisme de la partie » du plan de
    travail Fiches (`plan_travail_6e.corps_plan`), en tête de la partie : la
    planche de la partie se distribue au début de la partie. Cartes
    **validées** rattachées (`objectif_cartes`) aux objectifs de la partie
    (règle P7 des rituels, des planches et du récap). Rien sans l'option :
    plans de 6e et du cycle 4 inchangés au caractère près.
  - **F4** — propriété d'objectif `objectifs.sans_carte` (0/1, défaut 0) :
    « pas de carte voulue » (objectif de problème ou de programmation, rien à
    mémoriser). Lue dans les lots (clé `"sans_carte": true` de l'objectif ;
    clé absente : valeur gardée, comme `seances`). Elle remplace la liste de
    codes A3-04, B2-04, C1-05, E1-05 de la v0.60 (en 5e, ces codes désignent
    d'autres objectifs).
  - **F4b** — avertissement (non bloquant) à la validation d'une séquence du
    principal Fiches avec l'option cartes : « L'objectif A3-04 n'a pas de
    carte d'automatisme. » pour chaque objectif d'exercices (l'objectif
    « Cours » est exclu) sans carte rattachée et sans `sans_carte`.
  - **D17** — cartes évaluées par le test court d'une partie (document
    « Tests courts », version corrigée).

Colonne à valeur neutre : aucune ligne existante ne change.
"""
from __future__ import annotations

import sqlite3


def _cols(conn, table: str) -> set:
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def migrer(conn) -> list[str]:
    """Ajout idempotent de `objectifs.sans_carte`."""
    cols = _cols(conn, "objectifs")
    if cols and "sans_carte" not in cols:
        conn.execute("ALTER TABLE objectifs ADD COLUMN sans_carte INTEGER NOT NULL DEFAULT 0")
        return ["objectifs.sans_carte"]
    return []


def sans_carte(conn, objectif_id: str) -> bool:
    if "sans_carte" not in _cols(conn, "objectifs"):
        return False
    r = conn.execute("SELECT sans_carte FROM objectifs WHERE id = ?", (objectif_id,)).fetchone()
    return bool(r and r[0])


def poser_sans_carte(conn, objectif_id: str, valeur: bool) -> bool:
    """Écrit la propriété ; True si elle a changé."""
    migrer(conn)
    avant = sans_carte(conn, objectif_id)
    if avant == bool(valeur):
        return False
    conn.execute("UPDATE objectifs SET sans_carte = ? WHERE id = ?",
                 (1 if valeur else 0, objectif_id))
    return True


# ── Référentiel concerné ─────────────────────────────────────────────────────

def option_cartes_active(conn, niveau: str, referentiel_id: str | None = None) -> bool:
    """Le principal Fiches du niveau (celui donné, sinon celui de l'atelier,
    règle R1b) a-t-il l'option cartes ? (`fiches_cycle4.perimetre_cartes_objectifs`)."""
    from services.fiches_cycle4 import perimetre_cartes_objectifs
    from services.gabarits_documents import referentiel_atelier_du_niveau
    ref = referentiel_id or referentiel_atelier_du_niveau(conn, niveau)
    return bool(ref) and perimetre_cartes_objectifs(conn, ref)


# ── Cartes d'une partie ──────────────────────────────────────────────────────

def partie_id(conn, niveau: str, sequence: str, numero: int) -> str | None:
    r = conn.execute(
        "SELECT p.id FROM sequence_parties p JOIN sequences_par_niveau sn "
        "ON sn.id = p.sequence_par_niveau_id WHERE sn.niveau = ? AND sn.sequence_code = ? "
        "AND p.numero = ?", (niveau, sequence, int(numero))).fetchone()
    return r[0] if r else None


def cartes_de_partie(conn, partie: str, valides: bool = True) -> list[dict]:
    """Cartes rattachées aux objectifs de la partie (ordre des objectifs et
    des liens, une fois chacune) ; `code` « A3-CA03 » (niveau entre
    parenthèses pour une carte d'un autre niveau, comme les rituels)."""
    from services.progression_rituels import cartes_de_partie as _cartes
    niveau = conn.execute(
        "SELECT sn.niveau FROM sequence_parties p JOIN sequences_par_niveau sn "
        "ON sn.id = p.sequence_par_niveau_id WHERE p.id = ?", (partie,)).fetchone()
    niveau = niveau[0] if niveau else ""
    out = []
    for c in _cartes(conn, partie):
        if valides and c["etat_code"] != "valide":
            continue
        c["code"] = f"{c['sequence']}-CA{c['num']:02d}" + (
            f" ({c['niveau']})" if c["niveau"] != niveau else "")
        out.append(c)
    return out


def liste_latex(cartes: list[dict]) -> str:
    """« \textbf{A3-CA01} titre ; … » (titres échappés)."""
    from services.latex_texte import texte_latex
    return " ; ".join(rf"\textbf{{{texte_latex(c['code'])}}} {texte_latex(c['titre'])}"
                      for c in cartes)


# ── E9 — Plan de travail Fiches ──────────────────────────────────────────────

def lignes_plan_partie(conn, niveau: str, sequence: str, numero: int,
                       nb_parties: int) -> list[str]:
    """Lignes LaTeX de la rubrique « Cartes d'automatisme » d'une partie (liste
    vide sans carte validée). L'appelant vérifie l'option du référentiel."""
    pid = partie_id(conn, niveau, sequence, numero)
    cartes = cartes_de_partie(conn, pid) if pid else []
    if not cartes:
        return []
    titre = ("Cartes d'automatisme" + (f" de la partie {numero}" if nb_parties > 1 else "")
             + f" ({len(cartes)})")
    return [r"\medskip\noindent{\color{seqSixBleu}\bfseries\textgreater{} " + titre + "}"
            r" {\small (planche à distribuer au début de la partie)}\par",
            r"\noindent\hspace*{2em}{\small " + liste_latex(cartes) + r"}\par"]


# ── F4b — Avertissement « objectif sans carte » ──────────────────────────────

def objectifs_sans_carte(conn, sn_id: str) -> list[str]:
    """Étiquettes « A3-04 » des objectifs d'exercices de la séquence sans
    carte rattachée (validée ou non) ni propriété `sans_carte`."""
    from services.mises_en_route_6e import est_objectif_cours
    row = conn.execute("SELECT sequence_code FROM sequences_par_niveau WHERE id = ?",
                       (sn_id,)).fetchone()
    if row is None:
        return []
    seq = row[0]
    a_table = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                           "name='objectif_cartes'").fetchone() is not None
    col = "o.sans_carte" if "sans_carte" in _cols(conn, "objectifs") else "0"
    out = []
    for oid, code, numero, sc in conn.execute(
            f"SELECT o.id, o.code, p.numero, {col} FROM objectifs o JOIN sequence_parties p "
            "ON p.id = o.partie_id WHERE p.sequence_par_niveau_id = ? ORDER BY p.numero, o.code",
            (sn_id,)):
        if est_objectif_cours(str(code), int(numero), seq) or sc:
            continue
        n = conn.execute("SELECT COUNT(*) FROM objectif_cartes WHERE objectif_id = ?",
                         (oid,)).fetchone()[0] if a_table else 0
        if not n:
            out.append(f"{seq}-{code}")
    return out


def avertissements_validation(conn, sn_id: str, niveau: str) -> list[str]:
    """F4b — Messages pour la validation (principal Fiches avec option cartes)."""
    if not option_cartes_active(conn, niveau):
        return []
    return [f"L'objectif {e} n'a pas de carte d'automatisme (si c'est voulu : "
            "« sans_carte »: true dans le lot)." for e in objectifs_sans_carte(conn, sn_id)]
