r"""services/mise_en_route_referentiel.py — v0.60.1 (décision 18 du 18 novembre)

Mode de mise en route d'un **référentiel principal** (`doc/redemarrage_v0_60_1.md`) :
au collège, on n'a pas le temps de faire deux mises en route ; soit des cartes
d'automatisme tirées du cours principal (révisées par Leitner ou évaluées à
l'écrit), soit une progression de mise en route séparée (6e : référentiel de
MER), soit aucune.

  - Colonnes `referentiel_niveaux.mise_en_route` ('' = non renseigné,
    `aucune`, `cartes`, `progression`) et `mer_referentiel` (id du
    référentiel de MER, pour `progression` seulement). Table « structure »
    (atelier et classe).
  - **D18a Déduction** — une seule fois, à l'ajout des colonnes, et seulement
    quand elle est sûre : principal avec l'option « cartes d'automatisme »
    (v0.59.0) → `cartes` ; principal interne de version `V` et référentiel
    de MER interne **unique** du même niveau de version `Vb` →
    `progression` + ce référentiel (2026_N09 ↔ 2026_N09b) ; sinon non
    renseigné. Les instantanés (`referentiel_niveaux.instantane`, tables
    `referentiel_*`) et les publications figées ne sont jamais réécrits.
  - **D18b Saisie** — à la création (principal) et dans l'onglet du
    référentiel tant qu'il n'est pas figé (verrouillé, utilisé : lecture
    seule ; annulé : refusé aussi). Une MER désignée doit être un référentiel
    de type « mer » du même niveau, non annulé.
  - **D18c Affichage** — vue d'ensemble (ligne « Mise en route ») et document
    de rituels ; rien quand le mode n'est pas renseigné (documents inchangés).
  - **D18d Format d'échange** — `referentiel.mise_en_route` = {"mode",
    "mer"?} seulement si renseigné (version 1.7) ; absent : document et
    empreinte inchangés (`format_referentiel.construire`).
"""
from __future__ import annotations

import sqlite3

MODES = ("aucune", "cartes", "progression")
LIBELLES = {"": "non renseigné", "aucune": "aucune mise en route",
            "cartes": "cartes d'automatisme",
            "progression": "progression de mise en route"}
ETATS_FIGES = ("verrouille", "utilise")


class MiseEnRouteErreur(ValueError):
    def __init__(self, message: str, code: str = "mise_en_route_invalide", statut: int = 400):
        super().__init__(message)
        self.code = code
        self.statut = statut


def _cols(conn) -> set:
    try:
        return {r[1] for r in conn.execute("PRAGMA table_info(referentiel_niveaux)")}
    except sqlite3.Error:
        return set()


def colonnes_presentes(conn) -> bool:
    return {"mise_en_route", "mer_referentiel"} <= _cols(conn)


def migrer(conn) -> list[str]:
    """Ajouts idempotents ; la déduction (D18a) n'a lieu qu'à l'ajout."""
    cols = _cols(conn)
    if not cols:
        return []
    faits = []
    ajout = "mise_en_route" not in cols
    if ajout:
        conn.execute("ALTER TABLE referentiel_niveaux ADD COLUMN mise_en_route TEXT NOT NULL "
                     "DEFAULT ''")
        faits.append("referentiel_niveaux.mise_en_route")
    if "mer_referentiel" not in cols:
        conn.execute("ALTER TABLE referentiel_niveaux ADD COLUMN mer_referentiel TEXT NOT NULL "
                     "DEFAULT ''")
        faits.append("referentiel_niveaux.mer_referentiel")
    if ajout:
        n = len(deduire(conn, appliquer=True))
        faits.append(f"modes de mise en route déduits : {n}")
    return faits


def deduire(conn, appliquer: bool = False) -> list[dict]:
    """D18a — [{id, mode, mer}] des principaux dont le mode se déduit sûrement
    (et encore non renseigné)."""
    cols = _cols(conn)
    lignes = [dict(zip(("id", "niveau", "version", "source", "type_ref", "etat", "cartes",
                        "mode"), r)) for r in conn.execute(
        "SELECT id, niveau, version, COALESCE(source, 'interne'), "
        "COALESCE(type_ref, 'principal'), etat, "
        + ("COALESCE(cartes_automatisme, 0)" if "cartes_automatisme" in cols else "0") + ", "
        + ("COALESCE(mise_en_route, '')" if "mise_en_route" in cols else "''")
        + " FROM referentiel_niveaux")]
    out = []
    for r in lignes:
        if r["type_ref"] != "principal" or r["mode"] or r["etat"] == "annule":
            continue
        if r["cartes"]:
            out.append({"id": r["id"], "mode": "cartes", "mer": ""})
            continue
        if r["source"] != "interne" or not r["version"]:
            continue
        mers = [m for m in lignes if m["type_ref"] == "mer" and m["source"] == "interne"
                and m["niveau"] == r["niveau"] and m["etat"] != "annule"
                and m["version"] == r["version"] + "b"]
        if len(mers) == 1:
            out.append({"id": r["id"], "mode": "progression", "mer": mers[0]["id"]})
    if appliquer and colonnes_presentes(conn):
        for d in out:
            conn.execute("UPDATE referentiel_niveaux SET mise_en_route = ?, mer_referentiel = ? "
                         "WHERE id = ?", (d["mode"], d["mer"], d["id"]))
    return out


def lire(conn, ref_id: str) -> dict:
    """{mode, mer, libelle} ('' si non renseigné ou colonnes absentes)."""
    if not colonnes_presentes(conn):
        return {"mode": "", "mer": "", "libelle": LIBELLES[""]}
    r = conn.execute("SELECT mise_en_route, mer_referentiel FROM referentiel_niveaux "
                     "WHERE id = ?", (ref_id,)).fetchone()
    mode = (r[0] if r else "") or ""
    mer = (r[1] if r else "") or ""
    return {"mode": mode, "mer": mer if mode == "progression" else "",
            "libelle": libelle(mode, mer)}


def libelle(mode: str, mer: str = "") -> str:
    lib = LIBELLES.get(mode or "", mode or "")
    return lib + (f" ({mer})" if mode == "progression" and mer else "")


def valider(conn, ref_id: str | None, mode, mer, niveau: str | None = None) -> tuple[str, str]:
    """(mode, mer) normalisés ; MiseEnRouteErreur sinon. `niveau` : celui du
    référentiel (lu d'après `ref_id` s'il n'est pas donné ; avant la création,
    l'appelant le donne)."""
    mode = (mode or "").strip() if isinstance(mode, str) or mode is None else mode
    if mode not in ("",) + MODES:
        raise MiseEnRouteErreur(f"mode de mise en route inconnu : {mode!r} "
                                f"(attendu : {', '.join(MODES)} ou vide)")
    mer = (mer or "").strip() if isinstance(mer, str) or mer is None else ""
    if mode != "progression":
        return mode, ""
    if not mer:
        raise MiseEnRouteErreur("progression de mise en route : choisir le référentiel de "
                                "mise en route")
    niv = (niveau,) if niveau else conn.execute(
        "SELECT niveau FROM referentiel_niveaux WHERE id = ?", (ref_id,)).fetchone()
    m = conn.execute("SELECT niveau, COALESCE(type_ref, 'principal'), etat FROM "
                     "referentiel_niveaux WHERE id = ?", (mer,)).fetchone()
    if m is None or m[1] != "mer" or m[2] == "annule" or (niv and m[0] != niv[0]):
        raise MiseEnRouteErreur(f"{mer} n'est pas un référentiel de mise en route du même "
                                "niveau")
    return mode, mer


def poser(conn, ref_id: str, mode, mer=None, creation: bool = False) -> dict:
    """D18b — Écrit le mode d'un référentiel principal non figé (à la création :
    sans contrôle d'état). Retourne `lire`."""
    migrer(conn)
    r = conn.execute("SELECT COALESCE(type_ref, 'principal'), etat FROM referentiel_niveaux "
                     "WHERE id = ?", (ref_id,)).fetchone()
    if r is None:
        raise MiseEnRouteErreur(f"Référentiel introuvable : {ref_id}", "introuvable", 404)
    if r[0] != "principal":
        raise MiseEnRouteErreur("le mode de mise en route ne concerne que les référentiels "
                                "principaux", "type_ref_invalide")
    if not creation and (r[1] in ETATS_FIGES or r[1] == "annule"):
        raise MiseEnRouteErreur("référentiel figé : mode de mise en route en lecture seule",
                                "referentiel_fige", 409)
    mode, mer = valider(conn, ref_id, mode, mer)
    conn.execute("UPDATE referentiel_niveaux SET mise_en_route = ?, mer_referentiel = ? "
                 "WHERE id = ?", (mode, mer, ref_id))
    return lire(conn, ref_id)


def pour_echange(conn, ref_id: str) -> dict | None:
    """D18d — {"mode", "mer"?} pour le format d'échange ; None si non renseigné."""
    m = lire(conn, ref_id)
    if not m["mode"]:
        return None
    return {"mode": m["mode"], **({"mer": m["mer"]} if m["mer"] else {})}


def referentiels_mer(conn, niveau: str) -> list[dict]:
    """Référentiels de MER du niveau (choix de la saisie)."""
    return [{"id": r[0], "version": r[1], "source": r[2], "etat": r[3]} for r in conn.execute(
        "SELECT id, version, COALESCE(source, 'interne'), etat FROM referentiel_niveaux WHERE "
        "niveau = ? AND COALESCE(type_ref, 'principal') = 'mer' AND etat <> 'annule' "
        "ORDER BY version, id", (niveau,))]
