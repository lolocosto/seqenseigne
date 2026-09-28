"""routes/images.py — Navigateur d'images pour l'éditeur LaTeX (v0.13.7.4).

Deux endpoints :
  - GET /api/images
      Retourne la liste des images de data/images/ (nom + taille).
  - GET /api/images/preview/<nom>
      Sert le fichier image, pour l'affichage des miniatures côté UI.

Sécurité — préoccupation principale de la route preview :
  - Le nom de fichier vient du client → potentiel path traversal.
  - On valide rigoureusement avant de servir : pas de '..', '/', '\\',
    pas de nom commençant par '.', extension dans la whitelist.
  - On résout le chemin et on vérifie qu'il est BIEN dans le dossier
    images attendu (défense en profondeur : si la validation du nom
    laisse passer quelque chose, la résolution attrape le cas).
"""

from pathlib import Path

from flask import Blueprint, jsonify, current_app, send_file, abort

from services.images_navigateur import (
    EXTENSIONS_AUTORISEES,
    lister_images,
)

bp = Blueprint("images", __name__)


def _dossier_images() -> Path:
    """Retourne le chemin du dossier data/images/ pour cette instance."""
    return Path(current_app.json_store.data_dir) / "images"


@bp.route("/api/images", methods=["GET"])
def api_lister_images():
    """v0.13.7.4 — Retourne la liste des images de data/images/.

    Format de retour :
      {
        "images": [
          {"nom": "schema-thales.png",   "taille": 12345},
          {"nom": "triangle-rect.pdf",   "taille": 4567},
          ...
        ]
      }
    """
    images = lister_images(_dossier_images())
    return jsonify({"images": images})


@bp.route("/api/images/preview/<path:nom>", methods=["GET"])
def api_preview_image(nom: str):
    """v0.13.7.4 — Sert le fichier image pour l'affichage des miniatures.

    Validation rigoureuse contre les attaques de type path traversal.
    Retourne 404 si le fichier n'existe pas ou si la validation échoue.
    """
    # ── Validation 1 : caractères interdits dans le nom ─────────────────
    # On refuse explicitement tout ce qui pourrait s'évader du dossier
    # (séparateurs de chemin, '..', début par '.').
    if (not nom
            or '..' in nom
            or '/' in nom
            or '\\' in nom
            or nom.startswith('.')):
        abort(404)

    # ── Validation 2 : extension dans la whitelist ──────────────────────
    if not any(nom.lower().endswith(ext) for ext in EXTENSIONS_AUTORISEES):
        abort(404)

    # ── Validation 3 : le chemin résolu est bien dans dossier_images ────
    # Défense en profondeur. Même si les validations précédentes étaient
    # contournées, un chemin résolu hors du dossier autorisé est refusé.
    dossier = _dossier_images().resolve()
    if not dossier.is_dir():
        abort(404)
    cible = (dossier / nom).resolve()
    try:
        cible.relative_to(dossier)
    except ValueError:
        # cible est en dehors de dossier → refus
        abort(404)

    if not cible.is_file():
        abort(404)

    # send_file met le bon Content-Type automatiquement (mimetypes)
    return send_file(str(cible))
