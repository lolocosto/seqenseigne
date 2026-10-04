"""routes/seance.py — v0.43.0

API du début de séance (services/seance.py).
"""

from datetime import datetime

from flask import Blueprint, jsonify, request, current_app

from services import seance as svc
from services import annees_scolaires
from services.seance import SeanceErreur

bp = Blueprint("seance", __name__)


def _store():
    return current_app.json_store


def _erreur(e: SeanceErreur):
    return jsonify({"error": str(e), "code": e.code}), (404 if e.code == "introuvable" else 400)


def _maintenant() -> datetime:
    return datetime.now()


@bp.route("/api/seance/en-cours", methods=["GET"])
def api_en_cours():
    """Séance en cours (ou prochaine, ou dernière) du jour ; `classe_id`
    facultatif (sinon toutes les classes de l'année)."""
    annee = request.args.get("annee") or annees_scolaires.courante()
    with _store()._conn() as conn:
        s = svc.seance_en_cours(conn, _store(), annee, _maintenant(),
                                request.args.get("classe_id") or None)
    return jsonify({"seance": s})


@bp.route("/api/seance/jour", methods=["GET"])
def api_jour():
    """Séances d'une classe un jour donné (pour choisir après coup)."""
    from datetime import date
    a = request.args
    annee = a.get("annee") or annees_scolaires.courante()
    try:
        jour = date.fromisoformat(a.get("date", ""))
    except ValueError:
        return jsonify({"error": "date invalide"}), 400
    with _store()._conn() as conn:
        liste = svc.seances_du_jour(conn, _store(), annee, jour,
                                    a.get("classe_id") or None)
    for x in liste:
        x["statut"] = svc.statut(x, _maintenant())
    return jsonify({"seances": liste})


@bp.route("/api/seance", methods=["GET"])
def api_lire():
    a = request.args
    annee = a.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            return jsonify(svc.lire(conn, _store(), annee, a.get("classe_id", ""),
                                    a.get("date", ""), a.get("creneau", ""),
                                    _maintenant()))
    except SeanceErreur as e:
        return _erreur(e)


@bp.route("/api/seance/absence", methods=["PUT"])
def api_absence():
    b = request.get_json() or {}
    annee = b.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            liste = svc.definir_absence(conn, _store(), annee, b.get("classe_id", ""),
                                        b.get("eleve_id", ""), b.get("date", ""),
                                        b.get("creneau", ""), bool(b.get("absent")))
        return jsonify({"absents": liste})
    except SeanceErreur as e:
        return _erreur(e)


@bp.route("/api/seance/mer-non-faite", methods=["PUT"])
def api_mer_non_faite():
    """v0.43.2 — Mise en route non faite (case + commentaire facultatif)."""
    b = request.get_json() or {}
    annee = b.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            return jsonify(svc.marquer_mer_non_faite(
                conn, _store(), annee, b.get("classe_id", ""), b.get("date", ""),
                b.get("creneau", ""), bool(b.get("non_faite")),
                b.get("commentaire", "")))
    except SeanceErreur as e:
        return _erreur(e)


# ── v0.44.0 — Documents ──────────────────────────────────────────────────────

def _docs():
    from services import documents_seance
    return documents_seance


@bp.route("/api/seance/document", methods=["POST"])
def api_document_ajouter():
    """Document ajouté à la volée : pour cette séance (`pour`='cette') ou pour
    la séance suivante de la classe (`pour`='prochaine')."""
    b = request.get_json() or {}
    annee = b.get("annee") or annees_scolaires.courante()
    docs = _docs()
    try:
        with _store()._conn() as conn:
            svc._seance(conn, _store(), annee, b.get("classe_id", ""), b.get("date", ""),
                        b.get("creneau", ""))
            cible = {"date": b.get("date"), "creneau": b.get("creneau")}
            if b.get("pour") == "prochaine":
                cible = svc.seance_suivante(conn, _store(), annee, b.get("classe_id", ""),
                                            b.get("date", ""), b.get("creneau", ""))
                if cible is None:
                    return jsonify({"error": "Pas de séance suivante cette année."}), 400
            d = docs.ajouter_ponctuel(conn, annee, b.get("classe_id", ""),
                                      b.get("libelle", ""), b.get("categorie", "pedagogique"),
                                      cible["date"], cible["creneau"])
        return jsonify(d), 201
    except (SeanceErreur, docs.DocumentErreur) as e:
        return _erreur(e)


@bp.route("/api/seance/document/<document_id>", methods=["DELETE"])
def api_document_supprimer(document_id):
    docs = _docs()
    try:
        with _store()._conn() as conn:
            docs.supprimer_ponctuel(conn, document_id)
        return jsonify({"ok": True})
    except docs.DocumentErreur as e:
        return _erreur(e)


@bp.route("/api/seance/document/<document_id>/distribue", methods=["PUT"])
def api_document_distribue(document_id):
    b = request.get_json() or {}
    docs = _docs()
    try:
        with _store()._conn() as conn:
            docs.marquer_distribue(conn, document_id, b.get("date", ""),
                                   b.get("creneau", ""), bool(b.get("distribue")))
        return jsonify({"ok": True})
    except docs.DocumentErreur as e:
        return _erreur(e)


@bp.route("/api/seance/document/<document_id>/donne", methods=["PUT"])
def api_document_donne(document_id):
    b = request.get_json() or {}
    docs = _docs()
    try:
        with _store()._conn() as conn:
            docs.marquer_donne(conn, document_id, b.get("eleve_id", ""), b.get("date", ""),
                               b.get("creneau", ""), bool(b.get("donne")))
        return jsonify({"ok": True})
    except docs.DocumentErreur as e:
        return _erreur(e)


# ── v0.47.0 — Travail à faire / à rendre, documents à rapporter ─────────────

def _tr():
    from services import travail
    return travail


def _eleves_ids(conn, classe_id, date_iso):
    from datetime import date as _date
    from services import plans_classe as pc
    try:
        lundi = svc._lundi(_date.fromisoformat(date_iso)).isoformat()
    except ValueError:
        raise SeanceErreur(f"Date invalide : {date_iso!r}.")
    return [e["id"] for e in pc.eleves_de_la_semaine(conn, classe_id, lundi)]


@bp.route("/api/travail", methods=["GET"])
def api_travail():
    a = request.args
    annee = a.get("annee") or annees_scolaires.courante()
    tr = _tr()
    try:
        with _store()._conn() as conn:
            svc._seance(conn, _store(), annee, a.get("classe_id", ""), a.get("date", ""),
                        a.get("creneau", ""))
            return jsonify(tr.pour_seance(conn, _store(), annee, a.get("classe_id", ""),
                                          a.get("date", ""), a.get("creneau", ""),
                                          _eleves_ids(conn, a.get("classe_id", ""), a.get("date", ""))))
    except (SeanceErreur, tr.TravailErreur) as e:
        return _erreur(e)


@bp.route("/api/travail", methods=["POST"])
def api_travail_donner():
    b = request.get_json() or {}
    annee = b.get("annee") or annees_scolaires.courante()
    tr = _tr()
    try:
        with _store()._conn() as conn:
            svc._seance(conn, _store(), annee, b.get("classe_id", ""), b.get("date", ""),
                        b.get("creneau", ""))
            ech = b.get("echeance")
            d = tr.donner(conn, _store(), annee, b.get("classe_id", ""), b.get("date", ""),
                          b.get("creneau", ""), b.get("libelle", ""), b.get("retour", "faire"),
                          delai_jours=b.get("delai_jours"),
                          echeance=(ech["date"], ech["creneau"]) if ech else None)
        return jsonify(d), 201
    except (SeanceErreur, tr.TravailErreur) as e:
        return _erreur(e)


def _tr_action(fn):
    tr = _tr()
    try:
        with _store()._conn() as conn:
            fn(conn, tr)
        return jsonify({"ok": True})
    except tr.TravailErreur as e:
        return _erreur(e)


@bp.route("/api/travail/<doc_id>", methods=["DELETE"])
def api_travail_supprimer(doc_id):
    return _tr_action(lambda c, tr: tr.supprimer_travail(c, doc_id))


@bp.route("/api/travail/<doc_id>/clos", methods=["PUT"])
def api_travail_clos(doc_id):
    b = request.get_json() or {}
    return _tr_action(lambda c, tr: tr.clore(c, doc_id, bool(b.get("clos"))))


@bp.route("/api/travail/<doc_id>/rendu", methods=["PUT"])
def api_travail_rendu(doc_id):
    b = request.get_json() or {}
    return _tr_action(lambda c, tr: tr.marquer_rendu(c, doc_id, b.get("eleve_id", ""),
                                                     b.get("date", ""), b.get("creneau", ""),
                                                     bool(b.get("rendu"))))


@bp.route("/api/travail/<doc_id>/non-fait", methods=["PUT"])
def api_travail_non_fait(doc_id):
    b = request.get_json() or {}
    annee = b.get("annee") or annees_scolaires.courante()
    return _tr_action(lambda c, tr: tr.marquer_non_fait(
        c, _store(), annee, doc_id, b.get("eleve_id", ""), b.get("date", ""),
        b.get("creneau", ""), bool(b.get("non_fait")), bool(b.get("a_rattraper"))))


@bp.route("/api/seance/document/<doc_id>/retour", methods=["PUT"])
def api_document_retour(doc_id):
    b = request.get_json() or {}
    return _tr_action(lambda c, tr: tr.definir_retour(c, doc_id, b.get("retour", ""),
                                                      int(b.get("delai_jours") or 7)))
