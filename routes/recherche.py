"""routes/recherche.py — v0.18.1 — Outil Recherche (Outils généraux).

Endpoint unique :

  GET /api/recherche
      Recherche transversale sur les cinq types d'atomes.
      Paramètres (query string, tous optionnels) :
        - type            '' | notion | methode | exercice | fiche | carte
        - niveau          '' | N09 | N10 | N11 | N12 | …
        - sequence        '' | S01 | … | S14
        - etat            '' | tous | en_cours | valide
        - texte           motif recherché ('' = explorateur)
        - regex           '1'/'true' pour interpréter `texte` comme regex
        - casse_sensible  '1'/'true' pour une recherche sensible à la casse

      Réponse 200 : dict groupé par type + clé `total` (voir
      services.recherche_atomes.rechercher).
      Réponse 400 : {error, code} si regex invalide ou type invalide.

On reste en GET malgré la présence d'un motif regex dans l'URL : à l'échelle
d'usage (saisie manuelle), les motifs sont courts et l'encodage d'URL gère les
caractères spéciaux. Pas de donnée personnelle en query string (D6/privacy).
"""

from flask import Blueprint, jsonify, request, current_app

from services.recherche_atomes import (
    rechercher,
    RechercheErreur,
    RechercheRegexInvalide,
)

bp = Blueprint("recherche", __name__)

# Codes d'erreur → statut HTTP.
_CODE_HTTP = {
    "regex_invalide": 400,
    "type_invalide": 400,
}


def _bool_param(nom: str) -> bool:
    """Lit un paramètre booléen tolérant ('1', 'true', 'on', 'oui')."""
    v = (request.args.get(nom) or "").strip().lower()
    return v in ("1", "true", "on", "oui", "yes")


@bp.route("/api/recherche")
def api_recherche():
    store = current_app.json_store  # SqliteStore (nom historique)

    type_ = request.args.get("type", "") or ""
    niveau = request.args.get("niveau", "") or ""
    sequence = request.args.get("sequence", "") or ""
    etat = request.args.get("etat", "") or ""
    texte = request.args.get("texte", "") or ""
    regex = _bool_param("regex")
    casse_sensible = _bool_param("casse_sensible")

    try:
        resultat = rechercher(
            store,
            type=type_,
            niveau=niveau,
            sequence=sequence,
            etat=etat,
            texte=texte,
            regex=regex,
            casse_sensible=casse_sensible,
        )
    except RechercheRegexInvalide as e:
        return jsonify({"error": str(e), "code": e.code, **e.details}), 400
    except RechercheErreur as e:
        return (
            jsonify({"error": str(e), "code": e.code, **e.details}),
            _CODE_HTTP.get(e.code, 500),
        )

    return jsonify(resultat)
