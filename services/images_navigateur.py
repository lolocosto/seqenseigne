"""services/images_navigateur.py — Liste les images de data/images/.

Service utilisé par le navigateur d'images de l'éditeur LaTeX (v0.13.7.4).

Conventions
-----------
- Dossier scanné : <data_dir>/images/ (flat, pas de récursion).
- Extensions reconnues : .png, .jpg, .jpeg, .pdf (cohérent avec ce que
  le paquet seqenseigne accepte dans \\includegraphics).
- Le pipeline d'import (migration_images.py) convertit les JPG en PNG,
  mais on accepte malgré tout les JPG résiduels qui pourraient avoir
  été ajoutés à la main.
- Les fichiers cachés (commençant par '.') et les non-images sont
  silencieusement ignorés.

Sécurité : aucune écriture ni accès en dehors du dossier scanné. Le
service ne consomme ni ne valide de chemin venu du client (il se limite
au scan du dossier configuré côté serveur).
"""

from __future__ import annotations
from pathlib import Path

EXTENSIONS_AUTORISEES: frozenset[str] = frozenset({
    '.png', '.jpg', '.jpeg', '.pdf',
})


def lister_images(dossier_images: Path) -> list[dict]:
    """Liste les fichiers image de `dossier_images`, triés par nom.

    Args:
      dossier_images: chemin absolu vers le dossier `data/images/`.
        Si le dossier n'existe pas (ex. installation fraîche), retourne
        une liste vide.

    Returns:
      Liste d'objets `{"nom": str, "taille": int}` triés par `nom`
      (ordre lexicographique standard, sensible à la casse). `taille`
      est en octets, utile pour l'affichage UI (« 124 ko »).

      Les fichiers cachés (commençant par '.') et les fichiers dont
      l'extension n'est pas dans EXTENSIONS_AUTORISEES sont exclus.
    """
    if not dossier_images.is_dir():
        return []

    images: list[dict] = []
    for chemin in dossier_images.iterdir():
        if not chemin.is_file():
            continue
        if chemin.name.startswith('.'):
            continue
        if chemin.suffix.lower() not in EXTENSIONS_AUTORISEES:
            continue
        images.append({
            "nom": chemin.name,
            "taille": chemin.stat().st_size,
        })

    images.sort(key=lambda i: i["nom"])
    return images
