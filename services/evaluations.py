"""services/evaluations.py — v0.13.5.2.2

Gestion des atomes Évaluation : CRUD bas niveau, gestion des liaisons
exercices et objectifs, validation pédagogique, calcul de couverture.

Modèle (rappel scoping) :
  - Une évaluation = liste ordonnée d'exercices, attachée à un niveau.
  - Identifiée par (niveau, numero) où numero est stable.
  - Ordrée pour l'affichage par le champ ordre (réordonnable).
  - Mode notation : note | criteres | note_criteres | aucun.
  - Item langue française optionnel (JSON {points: int}).
  - État pédagogique : en_cours | valide.
  - L'enseignant déclare manuellement les objectifs couverts par
    l'évaluation (liaison directe via la table evaluation_objectifs).

Périmètre v0.13.5.2.1 :
  - CRUD evaluations (creer, lire, lister_par_niveau, modifier, supprimer)
  - Gestion liaisons exos (ajouter_exo, retirer_exo, reordonner_exos)

Ajouts v0.13.5.2.2 (cette livraison) :
  - Gestion liaisons objectifs (ajouter, retirer, lister)
  - Validation pédagogique en_cours → valide : valider_evaluation()
    contrôle qu'il y a ≥ 1 exo et que tous les exos ont des barèmes
    cohérents avec mode_notation.
  - Dévalidation valide → en_cours : devalider_evaluation() libre
    (cohérent avec le pattern etats_edition des autres atomes).
  - Calcul de couverture pour affichage matrice objectifs × exos :
    calculer_couverture().

Hors périmètre v0.13.5.2.2 :
  - Routes Flask et UI → reportées à v0.13.5.2.3
  - Génération PDF → reportée à v0.13.5.3
  - Mise à jour atelier Exercice pour saisir type_format='qcm' :
    reportée à une version ultérieure (v0.13.5.2.4 ou v0.13.5.3).
    Côté validation pédagogique, tous les exos existants sont en
    type_format='standard' par défaut (cf. migration v0.13.5.2),
    donc le contrôle de cohérence des barèmes QCM ne s'active que
    si type_format='qcm' apparaît un jour en BDD.
"""

from __future__ import annotations
import json
import sqlite3
import uuid
from typing import Any


# ── Erreurs de domaine ───────────────────────────────────────────────────────


class EvaluationErreur(Exception):
    """Erreur domaine pour les opérations sur les évaluations."""
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class EvaluationIntrouvable(EvaluationErreur):
    def __init__(self, evaluation_id):
        super().__init__(
            f"Évaluation {evaluation_id!r} introuvable.",
            "evaluation_introuvable", evaluation_id=evaluation_id,
        )


class NumeroDejaUtilise(EvaluationErreur):
    """Le couple (niveau, numero) est déjà pris par une autre évaluation."""
    def __init__(self, niveau, numero):
        super().__init__(
            f"Le numéro {numero} est déjà utilisé pour le niveau {niveau!r}.",
            "numero_deja_utilise", niveau=niveau, numero=numero,
        )


class ModeNotationInvalide(EvaluationErreur):
    """mode_notation hors {'note', 'criteres', 'note_criteres', 'aucun'}."""
    def __init__(self, valeur):
        super().__init__(
            f"Mode de notation invalide : {valeur!r}.",
            "mode_notation_invalide", valeur=valeur,
        )


class EtatCodeInvalide(EvaluationErreur):
    """etat_code hors {'en_cours', 'valide'}."""
    def __init__(self, valeur):
        super().__init__(
            f"État invalide : {valeur!r}.",
            "etat_code_invalide", valeur=valeur,
        )


class ItemLangueFrancaiseInvalide(EvaluationErreur):
    """item_langue_francaise n'est pas un JSON {points: int} valide."""
    def __init__(self, raison="Format invalide"):
        super().__init__(
            f"item_langue_francaise invalide : {raison}",
            "item_langue_francaise_invalide", raison=raison,
        )


class ExerciceIntrouvable(EvaluationErreur):
    """L'exercice ciblé n'existe pas dans la table exercices."""
    def __init__(self, exercice_id):
        super().__init__(
            f"Exercice {exercice_id!r} introuvable.",
            "exercice_introuvable", exercice_id=exercice_id,
        )


class ExoDejaPresent(EvaluationErreur):
    """L'exercice est déjà attaché à cette évaluation."""
    def __init__(self, evaluation_id, exercice_id):
        super().__init__(
            f"Exercice {exercice_id!r} déjà présent dans l'évaluation "
            f"{evaluation_id!r}.",
            "exo_deja_present",
            evaluation_id=evaluation_id, exercice_id=exercice_id,
        )


class ExoIntrouvableDansEvaluation(EvaluationErreur):
    """L'exercice n'est pas attaché à cette évaluation."""
    def __init__(self, evaluation_id, exercice_id):
        super().__init__(
            f"Exercice {exercice_id!r} non attaché à l'évaluation "
            f"{evaluation_id!r}.",
            "exo_introuvable_dans_evaluation",
            evaluation_id=evaluation_id, exercice_id=exercice_id,
        )


class ReordonnancementInvalide(EvaluationErreur):
    """La liste d'IDs ne correspond pas exactement aux exos de l'éval."""
    def __init__(self, raison):
        super().__init__(
            f"Réordonnancement invalide : {raison}",
            "reordonnancement_invalide", raison=raison,
        )


# ── v0.13.5.2.2 — Exceptions liaisons objectifs et validation ────────────────


class ObjectifIntrouvable(EvaluationErreur):
    """L'objectif n'existe pas en BDD."""
    def __init__(self, objectif_id):
        super().__init__(
            f"Objectif {objectif_id!r} introuvable.",
            "objectif_introuvable", objectif_id=objectif_id,
        )


class ObjectifDejaPresent(EvaluationErreur):
    """L'objectif est déjà attaché à cette évaluation."""
    def __init__(self, evaluation_id, objectif_id):
        super().__init__(
            f"Objectif {objectif_id!r} déjà attaché à l'évaluation "
            f"{evaluation_id!r}.",
            "objectif_deja_present",
            evaluation_id=evaluation_id, objectif_id=objectif_id,
        )


class ObjectifIntrouvableDansEvaluation(EvaluationErreur):
    """L'objectif n'est pas attaché à cette évaluation."""
    def __init__(self, evaluation_id, objectif_id):
        super().__init__(
            f"Objectif {objectif_id!r} non attaché à l'évaluation "
            f"{evaluation_id!r}.",
            "objectif_introuvable_dans_evaluation",
            evaluation_id=evaluation_id, objectif_id=objectif_id,
        )


class ObjectifNiveauIncoherent(EvaluationErreur):
    """L'objectif appartient à un niveau différent de celui de l'évaluation.

    Empêche de lier un objectif N10 à une éval N11 (cohérence
    pédagogique : une éval porte un niveau, ses objectifs aussi).
    """
    def __init__(self, evaluation_id, objectif_id,
                 niveau_eval, niveau_obj):
        super().__init__(
            f"Objectif {objectif_id!r} appartient au niveau "
            f"{niveau_obj!r}, incompatible avec le niveau {niveau_eval!r} "
            f"de l'évaluation {evaluation_id!r}.",
            "objectif_niveau_incoherent",
            evaluation_id=evaluation_id, objectif_id=objectif_id,
            niveau_eval=niveau_eval, niveau_obj=niveau_obj,
        )


class DejaValide(EvaluationErreur):
    """L'évaluation est déjà à l'état 'valide'."""
    def __init__(self, evaluation_id):
        super().__init__(
            f"Évaluation {evaluation_id!r} déjà à l'état 'valide'.",
            "deja_valide", evaluation_id=evaluation_id,
        )


class DejaEnCours(EvaluationErreur):
    """L'évaluation est déjà à l'état 'en_cours'."""
    def __init__(self, evaluation_id):
        super().__init__(
            f"Évaluation {evaluation_id!r} déjà à l'état 'en_cours'.",
            "deja_en_cours", evaluation_id=evaluation_id,
        )


class ValidationPedagogiqueErreur(EvaluationErreur):
    """La validation pédagogique a échoué : critères non remplis.

    Le champ `details['raisons']` contient une liste de motifs
    structurés permettant à l'UI de cibler les éléments fautifs.
    Chaque raison est un dict avec au moins une clé `code` :
      - {'code': 'aucun_exercice'}
      - {'code': 'bareme_manquant', 'exercice_id': 'EX...',
         'mode_notation': '...'}
      - {'code': 'bareme_qcm_manquant', 'exercice_id': 'EX...',
         'mode_notation': '...', 'champs': ['ok', 'partiel', 'ko']}
      - {'code': 'bareme_negatif', 'exercice_id': 'EX...'}
      - {'code': 'bareme_zero', 'exercice_id': 'EX...'}  (v0.16.3 : exo à 0 pt)
    """
    def __init__(self, evaluation_id, raisons):
        nb = len(raisons)
        super().__init__(
            f"Validation pédagogique échouée pour l'évaluation "
            f"{evaluation_id!r} : {nb} manquement(s).",
            "validation_pedagogique_echouee",
            evaluation_id=evaluation_id, raisons=raisons,
        )


# ── Constantes / helpers internes ────────────────────────────────────────────


MODES_NOTATION_VALIDES = ("note", "criteres", "note_criteres", "aucun")
ETATS_CODE_VALIDES     = ("en_cours", "valide")


def _rowid() -> str:
    """Génère un ID texte (cohérent avec le pattern utilisé partout)."""
    return uuid.uuid4().hex


def _evaluation_par_id(conn: sqlite3.Connection,
                        evaluation_id: str) -> dict | None:
    """Lookup simple. Retourne un dict ou None."""
    row = conn.execute(
        "SELECT id, niveau, numero, ordre, titre, mode_notation, "
        "       afficher_bareme_dans_exos, item_langue_francaise, "
        "       etat_code, mtime "
        "FROM evaluations WHERE id = ?",
        (evaluation_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_vers_dict_evaluation(row)


def _row_vers_dict_evaluation(row) -> dict:
    """Convertit une row en dict, avec parsing du JSON
    item_langue_francaise."""
    item_lf_raw = row["item_langue_francaise"]
    if item_lf_raw:
        try:
            item_lf = json.loads(item_lf_raw)
        except (ValueError, TypeError):
            item_lf = None
    else:
        item_lf = None
    return {
        "id":                          row["id"],
        "niveau":                      row["niveau"],
        "numero":                      row["numero"],
        "ordre":                       row["ordre"],
        "titre":                       row["titre"],
        "mode_notation":               row["mode_notation"],
        "afficher_bareme_dans_exos":   bool(row["afficher_bareme_dans_exos"]),
        "item_langue_francaise":       item_lf,
        "etat_code":                   row["etat_code"],
        "mtime":                       row["mtime"],
    }


def _valider_mode_notation(mode: str) -> None:
    if mode not in MODES_NOTATION_VALIDES:
        raise ModeNotationInvalide(mode)


def _valider_etat_code(etat: str) -> None:
    if etat not in ETATS_CODE_VALIDES:
        raise EtatCodeInvalide(etat)


def _valider_item_langue_francaise(valeur: Any) -> str:
    """Valide et sérialise item_langue_francaise.

    Accepte :
      - None ou '' → stocké comme '' en BDD
      - dict {'points': int} → sérialisé en JSON

    Retourne la chaîne à stocker en BDD.
    """
    if valeur is None or valeur == "":
        return ""
    if not isinstance(valeur, dict):
        raise ItemLangueFrancaiseInvalide(
            f"attendu dict, reçu {type(valeur).__name__}"
        )
    if "points" not in valeur:
        raise ItemLangueFrancaiseInvalide("clé 'points' manquante")
    points = valeur["points"]
    if not isinstance(points, (int, float)):
        raise ItemLangueFrancaiseInvalide(
            f"'points' doit être un nombre, reçu {type(points).__name__}"
        )
    return json.dumps({"points": points}, ensure_ascii=False)


def _exercice_existe(conn: sqlite3.Connection, exercice_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM exercices WHERE id = ?",
        (exercice_id,),
    ).fetchone()
    return row is not None


def _prochain_numero(conn: sqlite3.Connection, niveau: str) -> int:
    """Retourne le prochain numero libre pour ce niveau (max + 1)."""
    row = conn.execute(
        "SELECT COALESCE(MAX(numero), 0) AS m FROM evaluations "
        "WHERE niveau = ?",
        (niveau,),
    ).fetchone()
    return int(row["m"]) + 1


def _prochain_ordre(conn: sqlite3.Connection, niveau: str) -> int:
    """Retourne le prochain ordre libre pour ce niveau (max + 1)."""
    row = conn.execute(
        "SELECT COALESCE(MAX(ordre), 0) AS m FROM evaluations "
        "WHERE niveau = ?",
        (niveau,),
    ).fetchone()
    return int(row["m"]) + 1


def _prochain_ordre_exo(conn: sqlite3.Connection,
                          evaluation_id: str) -> int:
    """Retourne le prochain ordre libre dans l'éval."""
    row = conn.execute(
        "SELECT COALESCE(MAX(ordre), 0) AS m FROM evaluation_exercices "
        "WHERE evaluation_id = ?",
        (evaluation_id,),
    ).fetchone()
    return int(row["m"]) + 1


# ── CRUD evaluations ─────────────────────────────────────────────────────────


def creer_evaluation(
    conn: sqlite3.Connection,
    *,
    niveau: str,
    titre: str = "",
    mode_notation: str = "note",
    afficher_bareme_dans_exos: bool = True,
    item_langue_francaise: dict | None = None,
    numero: int | None = None,
    ordre: int | None = None,
) -> dict:
    """Crée une nouvelle évaluation.

    - niveau : N09..N12 (pas validé ici, c'est l'appelant qui s'assure).
    - titre : libre, défaut ''.
    - mode_notation : 'note' (défaut), 'criteres', 'note_criteres', 'aucun'.
    - afficher_bareme_dans_exos : True par défaut.
    - item_langue_francaise : None (pas d'item) ou {'points': N}.
    - numero : si None, calculé automatiquement (max+1).
    - ordre : si None, calculé automatiquement (max+1).

    Retourne l'évaluation créée (dict).
    Lève NumeroDejaUtilise, ModeNotationInvalide, ItemLangueFrancaiseInvalide.
    """
    _valider_mode_notation(mode_notation)
    item_lf_str = _valider_item_langue_francaise(item_langue_francaise)
    if numero is None:
        numero = _prochain_numero(conn, niveau)
    if ordre is None:
        ordre = _prochain_ordre(conn, niveau)
    eval_id = _rowid()
    try:
        conn.execute(
            "INSERT INTO evaluations "
            "(id, niveau, numero, ordre, titre, mode_notation, "
            " afficher_bareme_dans_exos, item_langue_francaise, "
            " etat_code, mtime) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'en_cours', "
            "        CURRENT_TIMESTAMP)",
            (eval_id, niveau, numero, ordre, titre, mode_notation,
             1 if afficher_bareme_dans_exos else 0, item_lf_str),
        )
    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if "unique" in msg and "niveau" in msg and "numero" in msg:
            raise NumeroDejaUtilise(niveau, numero)
        raise
    return _evaluation_par_id(conn, eval_id)


def lire_evaluation(conn: sqlite3.Connection,
                      evaluation_id: str) -> dict:
    """Retourne l'évaluation. Lève EvaluationIntrouvable si absente."""
    res = _evaluation_par_id(conn, evaluation_id)
    if res is None:
        raise EvaluationIntrouvable(evaluation_id)
    return res


def lister_evaluations(conn: sqlite3.Connection,
                         niveau: str | None = None) -> list[dict]:
    """Liste toutes les évaluations (ou celles d'un niveau).

    Triées par (niveau, ordre).
    """
    if niveau is not None:
        rows = conn.execute(
            "SELECT id, niveau, numero, ordre, titre, mode_notation, "
            "       afficher_bareme_dans_exos, item_langue_francaise, "
            "       etat_code, mtime "
            "FROM evaluations WHERE niveau = ? ORDER BY ordre",
            (niveau,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, niveau, numero, ordre, titre, mode_notation, "
            "       afficher_bareme_dans_exos, item_langue_francaise, "
            "       etat_code, mtime "
            "FROM evaluations ORDER BY niveau, ordre"
        ).fetchall()
    return [_row_vers_dict_evaluation(r) for r in rows]


def modifier_evaluation(
    conn: sqlite3.Connection,
    evaluation_id: str,
    *,
    titre: str | None = None,
    mode_notation: str | None = None,
    afficher_bareme_dans_exos: bool | None = None,
    item_langue_francaise: dict | None | str = "__no_change__",
    etat_code: str | None = None,
) -> dict:
    """Modification partielle d'une évaluation (PATCH-like).

    Tous les paramètres sont optionnels : seuls ceux explicitement
    passés (non None) sont modifiés. Pour effacer item_langue_francaise,
    passer item_langue_francaise=None explicitement (la sentinelle
    '__no_change__' distingue 'pas modifié' de 'effacé').

    Met à jour mtime à CURRENT_TIMESTAMP.

    Retourne l'évaluation modifiée. Lève EvaluationIntrouvable.
    """
    # Vérifie l'existence
    if _evaluation_par_id(conn, evaluation_id) is None:
        raise EvaluationIntrouvable(evaluation_id)

    sets = []
    args: list[Any] = []
    if titre is not None:
        sets.append("titre = ?")
        args.append(titre)
    if mode_notation is not None:
        _valider_mode_notation(mode_notation)
        sets.append("mode_notation = ?")
        args.append(mode_notation)
    if afficher_bareme_dans_exos is not None:
        sets.append("afficher_bareme_dans_exos = ?")
        args.append(1 if afficher_bareme_dans_exos else 0)
    if item_langue_francaise != "__no_change__":
        item_lf_str = _valider_item_langue_francaise(item_langue_francaise)
        sets.append("item_langue_francaise = ?")
        args.append(item_lf_str)
    if etat_code is not None:
        _valider_etat_code(etat_code)
        sets.append("etat_code = ?")
        args.append(etat_code)

    if sets:
        # Toujours rafraîchir le mtime
        sets.append("mtime = CURRENT_TIMESTAMP")
        args.append(evaluation_id)
        conn.execute(
            f"UPDATE evaluations SET {', '.join(sets)} WHERE id = ?",
            args,
        )

    return _evaluation_par_id(conn, evaluation_id)


def supprimer_evaluation(conn: sqlite3.Connection,
                            evaluation_id: str) -> None:
    """Supprime une évaluation (et ses liaisons via CASCADE).

    Lève EvaluationIntrouvable.
    """
    if _evaluation_par_id(conn, evaluation_id) is None:
        raise EvaluationIntrouvable(evaluation_id)
    conn.execute("DELETE FROM evaluations WHERE id = ?", (evaluation_id,))


# ── Liaisons evaluation ↔ exercices ──────────────────────────────────────────


def lister_exos_evaluation(conn: sqlite3.Connection,
                              evaluation_id: str) -> list[dict]:
    """Liste les exercices liés à une évaluation, triés par ordre.

    Retourne une liste de dicts incluant les paramètres de barème ET
    les champs descriptifs des exercices (nom métier, type_format,
    niveau, sequence, serie_code, num) nécessaires à l'UI pour
    construire un libellé lisible (ex. ``N10/S01/F01``).

    v0.13.5.2.5 — Enrichissement par JOIN avec ``exercices``. Avant,
    seuls les champs de la table de liaison étaient exposés, ce qui
    forçait l'UI à n'afficher que l'``exercice_id`` opaque.

    Lève EvaluationIntrouvable.
    """
    if _evaluation_par_id(conn, evaluation_id) is None:
        raise EvaluationIntrouvable(evaluation_id)
    rows = conn.execute(
        "SELECT ee.exercice_id, ee.ordre, "
        "       ee.bareme_points, ee.bareme_qcm_ok, "
        "       ee.bareme_qcm_partiel, ee.bareme_qcm_ko, "
        "       e.titre, e.serie, e.type_format, "
        "       e.niveau, e.sequence, e.serie_code, e.num "
        "FROM evaluation_exercices AS ee "
        "JOIN exercices AS e ON e.id = ee.exercice_id "
        "WHERE ee.evaluation_id = ? "
        "ORDER BY ee.ordre",
        (evaluation_id,),
    ).fetchall()
    return [{
        "exercice_id":        r["exercice_id"],
        "ordre":              r["ordre"],
        "bareme_points":      r["bareme_points"],
        "bareme_qcm_ok":      r["bareme_qcm_ok"],
        "bareme_qcm_partiel": r["bareme_qcm_partiel"],
        "bareme_qcm_ko":      r["bareme_qcm_ko"],
        # v0.13.5.2.5 — Champs descriptifs de l'exo, exposés pour
        # permettre à l'UI de construire un label métier lisible.
        # v0.13.6.12 — `nom` → `titre`.
        "titre":       r["titre"]       or "",
        "serie":       r["serie"]       or "",
        "type_format": r["type_format"] or "standard",
        "niveau":      r["niveau"]      or "",
        "sequence":    r["sequence"]    or "",
        "serie_code":  r["serie_code"]  or "",
        "num":         r["num"],
    } for r in rows]


def ajouter_exo_a_evaluation(
    conn: sqlite3.Connection,
    evaluation_id: str,
    exercice_id: str,
    *,
    bareme_points: float | None = None,
    bareme_qcm_ok: float | None = None,
    bareme_qcm_partiel: float | None = None,
    bareme_qcm_ko: float | None = None,
    ordre: int | None = None,
) -> None:
    """Attache un exercice à une évaluation.

    - ordre : si None, l'exercice est ajouté en fin (max+1).
    - bareme_* : tous optionnels. La cohérence métier
      (point requis si mode_notation in note/note_criteres) est
      vérifiée par la validation pédagogique en .2, pas ici.

    Met à jour mtime de l'évaluation.

    Lève EvaluationIntrouvable, ExerciceIntrouvable, ExoDejaPresent.
    """
    if _evaluation_par_id(conn, evaluation_id) is None:
        raise EvaluationIntrouvable(evaluation_id)
    if not _exercice_existe(conn, exercice_id):
        raise ExerciceIntrouvable(exercice_id)
    if ordre is None:
        ordre = _prochain_ordre_exo(conn, evaluation_id)
    try:
        conn.execute(
            "INSERT INTO evaluation_exercices "
            "(evaluation_id, exercice_id, ordre, "
            " bareme_points, bareme_qcm_ok, bareme_qcm_partiel, "
            " bareme_qcm_ko) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (evaluation_id, exercice_id, ordre,
             bareme_points, bareme_qcm_ok, bareme_qcm_partiel,
             bareme_qcm_ko),
        )
    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        # PK violation : (evaluation_id, exercice_id) déjà présent
        if "unique" in msg or "primary" in msg:
            raise ExoDejaPresent(evaluation_id, exercice_id)
        raise
    # Mise à jour mtime
    conn.execute(
        "UPDATE evaluations SET mtime = CURRENT_TIMESTAMP WHERE id = ?",
        (evaluation_id,),
    )


def retirer_exo_de_evaluation(conn: sqlite3.Connection,
                                evaluation_id: str,
                                exercice_id: str) -> None:
    """Détache un exercice d'une évaluation.

    Met à jour mtime de l'évaluation.

    Lève EvaluationIntrouvable, ExoIntrouvableDansEvaluation.
    """
    if _evaluation_par_id(conn, evaluation_id) is None:
        raise EvaluationIntrouvable(evaluation_id)
    cur = conn.execute(
        "DELETE FROM evaluation_exercices "
        "WHERE evaluation_id = ? AND exercice_id = ?",
        (evaluation_id, exercice_id),
    )
    if cur.rowcount == 0:
        raise ExoIntrouvableDansEvaluation(evaluation_id, exercice_id)
    # Mise à jour mtime
    conn.execute(
        "UPDATE evaluations SET mtime = CURRENT_TIMESTAMP WHERE id = ?",
        (evaluation_id,),
    )


def reordonner_exos_evaluation(conn: sqlite3.Connection,
                                  evaluation_id: str,
                                  ordre_exercices: list[str]) -> None:
    """Réordonne les exercices d'une évaluation.

    `ordre_exercices` doit contenir exactement et uniquement les ids
    des exercices actuellement liés à l'évaluation, dans l'ordre
    souhaité.

    Met à jour mtime de l'évaluation.

    Lève EvaluationIntrouvable, ReordonnancementInvalide.
    """
    if _evaluation_par_id(conn, evaluation_id) is None:
        raise EvaluationIntrouvable(evaluation_id)
    rows = conn.execute(
        "SELECT exercice_id FROM evaluation_exercices "
        "WHERE evaluation_id = ?",
        (evaluation_id,),
    ).fetchall()
    actuels = {r["exercice_id"] for r in rows}
    demandes = set(ordre_exercices)

    if len(ordre_exercices) != len(demandes):
        raise ReordonnancementInvalide("doublons dans la liste fournie")
    if actuels != demandes:
        manquants = actuels - demandes
        en_trop = demandes - actuels
        details = []
        if manquants:
            details.append(f"manquants: {sorted(manquants)}")
        if en_trop:
            details.append(f"non liés: {sorted(en_trop)}")
        raise ReordonnancementInvalide(", ".join(details))

    # SQLite ne permet pas une UPDATE qui violerait UNIQUE même
    # transitoirement. On contourne via valeurs négatives temporaires.
    # Étape 1 : déplacer tout le monde dans des ordres < 0 sans collision.
    for i, exo_id in enumerate(ordre_exercices, start=1):
        conn.execute(
            "UPDATE evaluation_exercices SET ordre = ? "
            "WHERE evaluation_id = ? AND exercice_id = ?",
            (-i, evaluation_id, exo_id),
        )
    # Étape 2 : remettre dans l'ordre positif final.
    for i, exo_id in enumerate(ordre_exercices, start=1):
        conn.execute(
            "UPDATE evaluation_exercices SET ordre = ? "
            "WHERE evaluation_id = ? AND exercice_id = ?",
            (i, evaluation_id, exo_id),
        )
    # Mise à jour mtime
    conn.execute(
        "UPDATE evaluations SET mtime = CURRENT_TIMESTAMP WHERE id = ?",
        (evaluation_id,),
    )


def modifier_bareme_exo(
    conn: sqlite3.Connection,
    evaluation_id: str,
    exercice_id: str,
    *,
    bareme_points: float | None | str = "__no_change__",
    bareme_qcm_ok: float | None | str = "__no_change__",
    bareme_qcm_partiel: float | None | str = "__no_change__",
    bareme_qcm_ko: float | None | str = "__no_change__",
) -> None:
    """Modifie le barème d'un exercice dans une évaluation.

    Tous les paramètres sont optionnels (PATCH-like) :
    - sentinelle '__no_change__' = pas de modification
    - None = effacer la valeur (mettre NULL en BDD)
    - nombre = nouvelle valeur

    Met à jour mtime de l'évaluation.

    Lève EvaluationIntrouvable, ExoIntrouvableDansEvaluation.
    """
    if _evaluation_par_id(conn, evaluation_id) is None:
        raise EvaluationIntrouvable(evaluation_id)
    # Vérifie que la liaison existe
    row = conn.execute(
        "SELECT 1 FROM evaluation_exercices "
        "WHERE evaluation_id = ? AND exercice_id = ?",
        (evaluation_id, exercice_id),
    ).fetchone()
    if row is None:
        raise ExoIntrouvableDansEvaluation(evaluation_id, exercice_id)

    sets = []
    args: list[Any] = []
    if bareme_points != "__no_change__":
        sets.append("bareme_points = ?")
        args.append(bareme_points)
    if bareme_qcm_ok != "__no_change__":
        sets.append("bareme_qcm_ok = ?")
        args.append(bareme_qcm_ok)
    if bareme_qcm_partiel != "__no_change__":
        sets.append("bareme_qcm_partiel = ?")
        args.append(bareme_qcm_partiel)
    if bareme_qcm_ko != "__no_change__":
        sets.append("bareme_qcm_ko = ?")
        args.append(bareme_qcm_ko)

    if sets:
        args.extend([evaluation_id, exercice_id])
        conn.execute(
            f"UPDATE evaluation_exercices SET {', '.join(sets)} "
            f"WHERE evaluation_id = ? AND exercice_id = ?",
            args,
        )
        conn.execute(
            "UPDATE evaluations SET mtime = CURRENT_TIMESTAMP WHERE id = ?",
            (evaluation_id,),
        )


def reordonner_evaluations(conn: sqlite3.Connection,
                              niveau: str,
                              ordre_evaluations: list[str]) -> None:
    """Réordonne les évaluations d'un niveau (drag-and-drop côté UI).

    `ordre_evaluations` doit contenir exactement et uniquement les ids
    des évaluations du niveau dans l'ordre souhaité.

    Met à jour ordre. Ne touche pas aux mtime des évaluations (le
    réordonnancement n'est pas une modification du contenu).

    Lève ReordonnancementInvalide.
    """
    rows = conn.execute(
        "SELECT id FROM evaluations WHERE niveau = ?",
        (niveau,),
    ).fetchall()
    actuels = {r["id"] for r in rows}
    demandes = set(ordre_evaluations)

    if len(ordre_evaluations) != len(demandes):
        raise ReordonnancementInvalide("doublons dans la liste fournie")
    if actuels != demandes:
        manquants = actuels - demandes
        en_trop = demandes - actuels
        details = []
        if manquants:
            details.append(f"manquants: {sorted(manquants)}")
        if en_trop:
            details.append(f"non liés: {sorted(en_trop)}")
        raise ReordonnancementInvalide(", ".join(details))

    # Pas de contrainte UNIQUE sur (niveau, ordre), donc pas besoin
    # du contournement par valeurs négatives. Mais on en met une dans
    # un index pour la performance, donc on peut écraser sans souci.
    for i, eval_id in enumerate(ordre_evaluations, start=1):
        conn.execute(
            "UPDATE evaluations SET ordre = ? WHERE id = ?",
            (i, eval_id),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# v0.13.5.2.2 — Liaisons objectifs, validation pédagogique, couverture
# ═══════════════════════════════════════════════════════════════════════════════


# ── Helpers internes v0.13.5.2.2 ─────────────────────────────────────────────


def _niveau_de_objectif(conn: sqlite3.Connection,
                        objectif_id: str) -> str | None:
    """Retourne le niveau ('N10', 'N11', ...) auquel appartient
    l'objectif, ou None s'il n'existe pas.

    Suit la chaîne : objectifs → sequence_parties →
    sequences_par_niveau.niveau.
    """
    row = conn.execute(
        "SELECT spn.niveau "
        "FROM objectifs AS o "
        "JOIN sequence_parties AS sp ON sp.id = o.partie_id "
        "JOIN sequences_par_niveau AS spn "
        "       ON spn.id = sp.sequence_par_niveau_id "
        "WHERE o.id = ?",
        (objectif_id,),
    ).fetchone()
    return row["niveau"] if row else None


def _row_vers_dict_objectif_lie(row) -> dict:
    """Vue 'objectif lié à une évaluation' pour les retours d'API.

    Combine les champs de l'objectif avec le contexte de séquence.
    """
    return {
        "id":             row["id"],
        "code":           row["code"],
        "nom":            row["nom"],
        "methode_id":     row["methode_id"],
        "fin_cycle":      row["fin_cycle"],
        "partie_id":      row["partie_id"],
        "partie_numero":  row["partie_numero"],
        "sequence_code":  row["sequence_code"],
    }


# ── Liaisons évaluation ↔ objectifs ──────────────────────────────────────────


def lister_objectifs_evaluation(conn: sqlite3.Connection,
                                evaluation_id: str) -> list[dict]:
    """Liste les objectifs liés à une évaluation.

    Triés par code de séquence puis par numéro de partie puis par code
    d'objectif — ordre stable et lisible pour l'enseignant.

    Raises:
        EvaluationIntrouvable
    """
    lire_evaluation(conn, evaluation_id)  # raise si introuvable

    rows = conn.execute(
        "SELECT o.id, o.code, o.nom, o.methode_id, o.fin_cycle, "
        "       o.partie_id, sp.numero AS partie_numero, "
        "       spn.sequence_code "
        "FROM evaluation_objectifs AS eo "
        "JOIN objectifs AS o ON o.id = eo.objectif_id "
        "JOIN sequence_parties AS sp ON sp.id = o.partie_id "
        "JOIN sequences_par_niveau AS spn "
        "       ON spn.id = sp.sequence_par_niveau_id "
        "WHERE eo.evaluation_id = ? "
        "ORDER BY spn.sequence_code, sp.numero, o.code",
        (evaluation_id,),
    ).fetchall()

    return [_row_vers_dict_objectif_lie(r) for r in rows]


def ajouter_objectif_a_evaluation(
    conn: sqlite3.Connection,
    evaluation_id: str,
    objectif_id: str,
) -> dict:
    """Ajoute un objectif à la couverture déclarée d'une évaluation.

    Contrôles :
      - L'évaluation existe
      - L'objectif existe
      - L'objectif n'est pas déjà attaché
      - L'objectif est du même niveau que l'évaluation

    Touche aussi le mtime de l'évaluation.

    Returns :
        dict de l'objectif lié (cf. _row_vers_dict_objectif_lie).

    Raises:
        EvaluationIntrouvable
        ObjectifIntrouvable
        ObjectifDejaPresent
        ObjectifNiveauIncoherent
    """
    evaluation = lire_evaluation(conn, evaluation_id)
    niveau_obj = _niveau_de_objectif(conn, objectif_id)
    if niveau_obj is None:
        raise ObjectifIntrouvable(objectif_id)

    if niveau_obj != evaluation["niveau"]:
        raise ObjectifNiveauIncoherent(
            evaluation_id, objectif_id,
            niveau_eval=evaluation["niveau"], niveau_obj=niveau_obj,
        )

    # Test de présence préalable pour retourner une erreur métier propre
    # plutôt que de laisser SQLite remonter IntegrityError.
    deja_la = conn.execute(
        "SELECT 1 FROM evaluation_objectifs "
        "WHERE evaluation_id = ? AND objectif_id = ?",
        (evaluation_id, objectif_id),
    ).fetchone()
    if deja_la:
        raise ObjectifDejaPresent(evaluation_id, objectif_id)

    conn.execute(
        "INSERT INTO evaluation_objectifs (evaluation_id, objectif_id) "
        "VALUES (?, ?)",
        (evaluation_id, objectif_id),
    )
    conn.execute(
        "UPDATE evaluations SET mtime = CURRENT_TIMESTAMP WHERE id = ?",
        (evaluation_id,),
    )

    # Retourner la vue enrichie de l'objectif que l'UI affichera.
    row = conn.execute(
        "SELECT o.id, o.code, o.nom, o.methode_id, o.fin_cycle, "
        "       o.partie_id, sp.numero AS partie_numero, "
        "       spn.sequence_code "
        "FROM objectifs AS o "
        "JOIN sequence_parties AS sp ON sp.id = o.partie_id "
        "JOIN sequences_par_niveau AS spn "
        "       ON spn.id = sp.sequence_par_niveau_id "
        "WHERE o.id = ?",
        (objectif_id,),
    ).fetchone()
    return _row_vers_dict_objectif_lie(row)


def retirer_objectif_de_evaluation(conn: sqlite3.Connection,
                                   evaluation_id: str,
                                   objectif_id: str) -> None:
    """Retire un objectif de la couverture déclarée d'une évaluation.

    Touche le mtime.

    Raises:
        EvaluationIntrouvable
        ObjectifIntrouvableDansEvaluation
    """
    lire_evaluation(conn, evaluation_id)  # raise si introuvable

    cur = conn.execute(
        "DELETE FROM evaluation_objectifs "
        "WHERE evaluation_id = ? AND objectif_id = ?",
        (evaluation_id, objectif_id),
    )
    if cur.rowcount == 0:
        raise ObjectifIntrouvableDansEvaluation(evaluation_id, objectif_id)

    conn.execute(
        "UPDATE evaluations SET mtime = CURRENT_TIMESTAMP WHERE id = ?",
        (evaluation_id,),
    )


# ── Validation pédagogique : en_cours → valide ───────────────────────────────


# Modes de notation qui imposent un barème non NULL :
#  - 'note'           : note seule sur 20, bareme_points obligatoire
#  - 'note_criteres'  : note + critères, bareme_points obligatoire
# Modes où le barème_points est facultatif :
#  - 'criteres'       : critères seuls (pas de note → pas de barème en
#                       points obligatoire)
#  - 'aucun'          : aucun barème
_MODES_AVEC_BAREME_OBLIGATOIRE = frozenset({"note", "note_criteres"})


def _evaluer_critere_bareme(exo_row, mode_notation: str) -> list[dict]:
    """Pour un exercice attaché à une évaluation, vérifie si son barème
    est cohérent avec le mode_notation.

    Retourne une liste (possiblement vide) de raisons de non-conformité,
    chacune sous forme de dict prêt à être inclus dans
    ValidationPedagogiqueErreur.details['raisons'].

    `exo_row` est attendu avec les champs : exercice_id, type_format,
    bareme_points, bareme_qcm_ok, bareme_qcm_partiel, bareme_qcm_ko.
    """
    raisons = []
    type_format = exo_row["type_format"] or "standard"
    exo_id = exo_row["exercice_id"]

    if mode_notation not in _MODES_AVEC_BAREME_OBLIGATOIRE:
        # Pas de barème obligatoire pour 'criteres' ou 'aucun'.
        # On valide tout de même qu'un barème renseigné n'est pas négatif.
        for champ in ("bareme_points", "bareme_qcm_ok",
                      "bareme_qcm_partiel", "bareme_qcm_ko"):
            valeur = exo_row[champ]
            if valeur is not None and valeur < 0:
                raisons.append({
                    "code": "bareme_negatif",
                    "exercice_id": exo_id,
                    "champ": champ,
                    "valeur": valeur,
                })
        return raisons

    # Mode 'note' ou 'note_criteres' : barème obligatoire.
    if type_format == "qcm":
        manquants = []
        for champ_court, champ in (
            ("ok",      "bareme_qcm_ok"),
            ("partiel", "bareme_qcm_partiel"),
            ("ko",      "bareme_qcm_ko"),
        ):
            if exo_row[champ] is None:
                manquants.append(champ_court)
        if manquants:
            raisons.append({
                "code": "bareme_qcm_manquant",
                "exercice_id": exo_id,
                "mode_notation": mode_notation,
                "champs": manquants,
            })
        else:
            # v0.16.3 — Tous les champs QCM renseignés : on vérifie que la note
            # « bonne réponse » (ok) n'est pas à 0 (un QCM noté doit rapporter
            # des points). partiel/ko peuvent légitimement valoir 0.
            ok = exo_row["bareme_qcm_ok"]
            if ok is not None and abs(float(ok)) < 1e-9:
                raisons.append({
                    "code": "bareme_zero",
                    "exercice_id": exo_id,
                    "champ": "bareme_qcm_ok",
                    "mode_notation": mode_notation,
                })
    else:
        # type_format == 'standard' (ou autre valeur future : on traite
        # comme standard par défaut, conservateur).
        if exo_row["bareme_points"] is None:
            raisons.append({
                "code": "bareme_manquant",
                "exercice_id": exo_id,
                "mode_notation": mode_notation,
            })
        elif exo_row["bareme_points"] < 0:
            raisons.append({
                "code": "bareme_negatif",
                "exercice_id": exo_id,
                "champ": "bareme_points",
                "valeur": exo_row["bareme_points"],
            })
        elif abs(float(exo_row["bareme_points"])) < 1e-9:
            # v0.16.3 — Un exercice est explicitement ajouté à l'évaluation :
            # il DOIT être noté. Un barème à 0 point est une erreur (à la
            # différence de l'item « langue française », optionnel, où 0 = item
            # désactivé). Cf. _bareme_langue_str.
            raisons.append({
                "code": "bareme_zero",
                "exercice_id": exo_id,
                "champ": "bareme_points",
                "mode_notation": mode_notation,
            })

    return raisons


def valider_evaluation(conn: sqlite3.Connection,
                       evaluation_id: str) -> dict:
    """Tente de faire passer l'évaluation en état 'valide'.

    Contrôles (décision Laurent v0.13.5.2.2) :
      1. Au moins 1 exercice attaché
      2. TOUS les exos attachés ont un barème cohérent avec le
         mode_notation de l'évaluation (cf. _evaluer_critere_bareme).

    Si tout passe : etat_code='valide', mtime touché, retour de l'éval
    rafraîchie.

    Raises:
        EvaluationIntrouvable
        DejaValide (si déjà à 'valide', signal informatif pour l'UX)
        ValidationPedagogiqueErreur (raisons détaillées dans details)
    """
    evaluation = lire_evaluation(conn, evaluation_id)

    if evaluation["etat_code"] == "valide":
        raise DejaValide(evaluation_id)

    raisons = []

    # Contrôle 1 : au moins 1 exo
    exos = conn.execute(
        "SELECT ee.exercice_id, ee.bareme_points, "
        "       ee.bareme_qcm_ok, ee.bareme_qcm_partiel, ee.bareme_qcm_ko, "
        "       e.type_format "
        "FROM evaluation_exercices AS ee "
        "JOIN exercices AS e ON e.id = ee.exercice_id "
        "WHERE ee.evaluation_id = ? "
        "ORDER BY ee.ordre",
        (evaluation_id,),
    ).fetchall()

    if not exos:
        raisons.append({"code": "aucun_exercice"})
    else:
        # Contrôle 2 : barèmes cohérents pour chaque exo
        mode = evaluation["mode_notation"]
        for exo_row in exos:
            raisons.extend(_evaluer_critere_bareme(exo_row, mode))

    if raisons:
        raise ValidationPedagogiqueErreur(evaluation_id, raisons)

    # Tous les contrôles passent : transition d'état.
    conn.execute(
        "UPDATE evaluations SET etat_code = 'valide', "
        "       mtime = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (evaluation_id,),
    )

    return lire_evaluation(conn, evaluation_id)


# ── Dévalidation : valide → en_cours ─────────────────────────────────────────


def devalider_evaluation(conn: sqlite3.Connection,
                         evaluation_id: str) -> dict:
    """Repasse l'évaluation en état 'en_cours'.

    Aucun contrôle métier (cohérent avec le pattern etats_edition des
    autres atomes : « transitions manuelles libres, l'enseignant
    assume »). L'asymétrie avec valider_evaluation est volontaire et
    documentée dans le scoping.

    Raises:
        EvaluationIntrouvable
        DejaEnCours
    """
    evaluation = lire_evaluation(conn, evaluation_id)

    if evaluation["etat_code"] == "en_cours":
        raise DejaEnCours(evaluation_id)

    conn.execute(
        "UPDATE evaluations SET etat_code = 'en_cours', "
        "       mtime = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (evaluation_id,),
    )

    return lire_evaluation(conn, evaluation_id)


# ── Calcul de couverture (matrice objectifs × exos) ──────────────────────────


def calculer_couverture(conn: sqlite3.Connection,
                        evaluation_id: str) -> dict:
    """Construit la matrice de couverture objectifs × exos d'une éval.

    Pour chaque objectif déclaré couvert par l'éval, indique quels exos
    de l'éval sont effectivement rattachés à cet objectif (via la table
    objectif_exos qui décrit la liaison exos ↔ objectifs au niveau
    métier).

    Permet à l'UI d'afficher un tableau croisé montrant :
      - les objectifs déclarés mais sans exo correspondant (couverture
        nominale mais pas pédagogique)
      - les exos qui contribuent à plusieurs objectifs (cellules
        multiples)
      - les objectifs sans aucun exo rattaché (potentiellement à
        renforcer ou à retirer)

    Returns :
      {
        'objectifs':  [ {id, code, nom, sequence_code, partie_numero}, ...]
                       triés comme lister_objectifs_evaluation
        'exercices':  [ {id, nom, type_format, ordre}, ... ]
                       triés par ordre dans l'éval
        'cellules':   [ {objectif_id, exercice_id}, ... ]
                       (présence = lien direct via objectif_exos)
      }

    Raises:
        EvaluationIntrouvable
    """
    lire_evaluation(conn, evaluation_id)  # raise si introuvable

    # Objectifs liés (mêmes méta que lister_objectifs_evaluation)
    objectifs = lister_objectifs_evaluation(conn, evaluation_id)

    # Exercices
    # v0.13.5.3 — Enrichissement du SELECT et du dict de sortie pour
    # permettre à l'UI d'afficher les entêtes de colonnes en label
    # métier (N10/S01/F01) au lieu de '?' (correction du résidu v25).
    exos_rows = conn.execute(
        "SELECT e.id, e.titre, e.type_format, ee.ordre, "
        "       e.niveau, e.sequence, e.serie_code, e.num "
        "FROM evaluation_exercices AS ee "
        "JOIN exercices AS e ON e.id = ee.exercice_id "
        "WHERE ee.evaluation_id = ? "
        "ORDER BY ee.ordre",
        (evaluation_id,),
    ).fetchall()
    exercices = [
        {
            "id":          r["id"],
            "titre":       r["titre"],
            "type_format": r["type_format"] or "standard",
            "ordre":       r["ordre"],
            # v0.13.5.3 — Champs pour le label métier N10/S01/F01.
            "niveau":      r["niveau"]     or "",
            "sequence":    r["sequence"]   or "",
            "serie_code":  r["serie_code"] or "",
            "num":         r["num"],
        }
        for r in exos_rows
    ]

    # Cellules : intersection {exos de l'éval} × {objectifs liés à l'éval}
    # via la table objectif_exos. Cellules présentes uniquement (matrice
    # creuse) — l'UI complète avec des cellules vides au rendu.
    cellules = []
    if objectifs and exercices:
        obj_ids = [o["id"] for o in objectifs]
        exo_ids = [e["id"] for e in exercices]
        # SQLite ne paramètre pas les IN directement : on construit la
        # clause avec placeholders.
        placeholders_obj = ",".join("?" for _ in obj_ids)
        placeholders_exo = ",".join("?" for _ in exo_ids)
        cellules_rows = conn.execute(
            f"SELECT DISTINCT objectif_id, exercice_id "
            f"FROM objectif_exos "
            f"WHERE objectif_id IN ({placeholders_obj}) "
            f"  AND exercice_id IN ({placeholders_exo})",
            (*obj_ids, *exo_ids),
        ).fetchall()
        cellules = [
            {"objectif_id": r["objectif_id"], "exercice_id": r["exercice_id"]}
            for r in cellules_rows
        ]

    return {
        "objectifs": objectifs,
        "exercices": exercices,
        "cellules":  cellules,
    }
