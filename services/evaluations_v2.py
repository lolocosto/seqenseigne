"""services/evaluations_v2.py — v0.60.0

Version 2 du modèle Fiches avec cartes (`doc/redemarrage_v0_60_0.md`,
besoins E6 et E7 de `col4/besoins_appli_fiches_4e.md`) : type d'évaluation
(« évaluation » ou « test court ») et durée d'une évaluation.

Décisions :

  - **T1 Type** — colonne `evaluations.type_evaluation` ('evaluation' par
    défaut, ou 'test_court'). À l'ajout de la colonne (une seule fois), les
    évaluations dont le titre commence par « Test court » (lots de 6e et de
    4e, mises en route) sont reconnues comme tests courts ; ensuite seuls
    l'import des lots et le module Évaluations écrivent le type. La
    reconnaissance ne touche pas `mtime` : aucun document ne devient périmé,
    aucun .tex ne change.
  - **T2 Durée d'une évaluation** (E7) — colonne `evaluations.duree`
    (minutes, NULL = automatique) ; automatique = 10 min × objectifs évalués
    (bonus exclu) pour une évaluation, 10 min pour un test court (sur les
    cartes de la partie, /10 + bonus 1 : à confirmer). Une séance d'évaluation
    dure 50 min utiles et réunit au plus 5 objectifs.
  - **T3 Partie sans calculatrice** (correctif B8) — la partie 1 d'un sujet en
    deux parties dure la part de la durée de l'évaluation qui revient à ses
    objectifs : chaque objectif pèse 1/n de la durée, un objectif partagé
    entre les deux parties compte au prorata de ses points ; arrondi aux
    5 min, au moins 10 min, au plus la durée. Remplace « 55 min × points de
    la partie 1 / total » (v0.52.9, D4), qui donnait 40 min de partie 1 pour
    une évaluation de 30 min. La durée réglée dans l'atelier
    (`duree_partie1`) prime toujours.
"""
from __future__ import annotations

import sqlite3

TYPES_EVALUATION = ("evaluation", "test_court")
LIBELLES_TYPES = {"evaluation": "Évaluation", "test_court": "Test court"}
DUREE_PAR_OBJECTIF = 10      # minutes (E7)
DUREE_TEST_COURT = 10        # minutes (T2, à confirmer)
SEANCE_EVAL_MINUTES = 50     # minutes utiles (E7)
SEANCE_EVAL_OBJECTIFS = 5    # objectifs au plus (E7)
DUREE_MINIMUM_PARTIE1 = 10
DUREE_MAXIMUM = 240


class DureeInvalide(ValueError):
    pass


class TypeEvaluationInvalide(ValueError):
    pass


def _cols(conn) -> set:
    try:
        return {r[1] for r in conn.execute("PRAGMA table_info(evaluations)")}
    except sqlite3.Error:
        return set()


def colonnes_presentes(conn) -> bool:
    return {"type_evaluation", "duree"} <= _cols(conn)


def est_titre_test_court(titre: str | None) -> bool:
    """« Test court --- Translation » → True (casse et espaces ignorés)."""
    return " ".join((titre or "").split()).lower().startswith("test court")


def migrer(conn) -> list[str]:
    """Ajouts idempotents (T1, T2) ; retourne ce qui vient d'être fait.
    La reconnaissance des tests courts par leur titre n'a lieu qu'à l'ajout
    de la colonne (une seule fois), sans toucher `mtime`."""
    cols = _cols(conn)
    if not cols:
        return []
    faits = []
    if "type_evaluation" not in cols:
        conn.execute("ALTER TABLE evaluations ADD COLUMN type_evaluation TEXT NOT NULL "
                     "DEFAULT 'evaluation'")
        faits.append("evaluations.type_evaluation")
        n = reconnaitre_tests_courts(conn)
        faits.append(f"tests courts reconnus : {n}")
    if "duree" not in cols:
        conn.execute("ALTER TABLE evaluations ADD COLUMN duree INTEGER")
        faits.append("evaluations.duree")
    return faits


def reconnaitre_tests_courts(conn, appliquer: bool = True) -> int:
    """T1 — Évaluations « Test court … » encore typées 'evaluation' :
    passées en 'test_court' (sans toucher `mtime`). Idempotent ; retourne le
    nombre d'évaluations concernées (à passer, ou passées)."""
    ids = [r[0] for r in conn.execute("SELECT id, titre FROM evaluations WHERE "
                                      "type_evaluation = 'evaluation'").fetchall()
           if est_titre_test_court(r[1])]
    if appliquer:
        for i in ids:
            conn.execute("UPDATE evaluations SET type_evaluation = 'test_court' WHERE id = ?",
                         (i,))
    return len(ids)


def type_evaluation(conn, evaluation_id: str) -> str:
    """'evaluation' | 'test_court' (repli sur le titre sans la colonne)."""
    if "type_evaluation" in _cols(conn):
        r = conn.execute("SELECT type_evaluation FROM evaluations WHERE id = ?",
                         (evaluation_id,)).fetchone()
        return (r[0] if r else "") or "evaluation"
    r = conn.execute("SELECT titre FROM evaluations WHERE id = ?", (evaluation_id,)).fetchone()
    return "test_court" if r and est_titre_test_court(r[0]) else "evaluation"


def valider_type(valeur) -> str:
    if valeur not in TYPES_EVALUATION:
        raise TypeEvaluationInvalide(f"type d'évaluation inconnu : {valeur!r} "
                                     f"(attendu {', '.join(TYPES_EVALUATION)})")
    return valeur


def valider_duree(valeur):
    """None / '' = automatique ; sinon minutes entières de 1 à 240."""
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        return None
    if isinstance(valeur, bool):
        raise DureeInvalide(f"durée invalide : {valeur!r}")
    try:
        f = float(str(valeur).strip().replace(",", "."))
    except ValueError:
        raise DureeInvalide(f"durée invalide : {valeur!r}") from None
    if f != int(f) or not 1 <= f <= DUREE_MAXIMUM:
        raise DureeInvalide(f"durée invalide : {valeur!r} (minutes entières, 1 à "
                            f"{DUREE_MAXIMUM})")
    return int(f)


def nb_objectifs_evalues(conn, evaluation_id: str) -> int:
    """Objectifs évalués : liens `evaluation_objectifs`, sinon objectifs
    distincts des exercices (barème)."""
    n = conn.execute("SELECT COUNT(*) FROM evaluation_objectifs WHERE evaluation_id = ?",
                     (evaluation_id,)).fetchone()[0]
    if not n:
        try:
            n = conn.execute(
                "SELECT COUNT(DISTINCT oe.objectif_id) FROM evaluation_exercices ee JOIN "
                "objectif_exos oe ON oe.exercice_id = ee.exercice_id AND oe.serie = 'EV' "
                "WHERE ee.evaluation_id = ?", (evaluation_id,)).fetchone()[0]
        except sqlite3.Error:
            n = 0
    return int(n or 0)


def duree_auto(conn, evaluation_id: str, type_ev: str | None = None,
               nb_objectifs: int | None = None) -> int:
    """T2 — 10 min × objectifs évalués (au moins 10) ; test court : 10 min."""
    t = type_ev or type_evaluation(conn, evaluation_id)
    if t == "test_court":
        return DUREE_TEST_COURT
    n = nb_objectifs if nb_objectifs is not None else nb_objectifs_evalues(conn, evaluation_id)
    return DUREE_PAR_OBJECTIF * max(1, n)


def duree_reglee(conn, evaluation_id: str):
    if "duree" not in _cols(conn):
        return None
    r = conn.execute("SELECT duree FROM evaluations WHERE id = ?", (evaluation_id,)).fetchone()
    return r[0] if r and r[0] not in (None, "") else None


def duree(conn, evaluation_id: str, type_ev: str | None = None) -> int:
    """Durée retenue : réglée, sinon automatique."""
    d = duree_reglee(conn, evaluation_id)
    return int(d) if d is not None else duree_auto(conn, evaluation_id, type_ev)


def _arrondi5(x: float) -> int:
    return int(x / 5 + 0.5) * 5


def duree_partie1_par_objectifs(parties: list, duree_totale: int) -> int:
    """T3 — Durée de la partie 1 d'un sujet en deux parties.

    `parties` = [[exercices partie 1], [exercices partie 2]], chaque exercice
    portant `objectif` (étiquette, '' pour un bonus) et `points`. Chaque
    objectif pèse 1/n de `duree_totale` ; sa part dans la partie 1 est la
    part de ses points qui y figure. Arrondi aux 5 min, au moins 10 min, au
    plus la durée totale."""
    pts: dict = {}
    for i, p in enumerate(parties[:2]):
        for e in p:
            if not e.get("objectif"):
                continue
            d = pts.setdefault(e["objectif"], [0.0, 0.0])
            d[i] += float(e.get("points") or 0)
    if not pts:
        return DUREE_MINIMUM_PARTIE1
    part = 0.0
    for p1, p2 in pts.values():
        tot = p1 + p2
        part += (p1 / tot) if tot > 0 else 0.0
    n = _arrondi5(duree_totale * part / len(pts))
    return max(DUREE_MINIMUM_PARTIE1, min(int(duree_totale), n))


def resume(conn, evaluation_id: str) -> dict:
    """{type_evaluation, duree, duree_auto, duree_reglee} pour le module et
    les routes."""
    t = type_evaluation(conn, evaluation_id)
    auto = duree_auto(conn, evaluation_id, t)
    reg = duree_reglee(conn, evaluation_id)
    return {"type_evaluation": t, "duree_auto": auto, "duree": reg,
            "duree_retenue": int(reg) if reg is not None else auto}
