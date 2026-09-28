"""Tests v0.13.7.4 — Service `images_navigateur` et routes /api/images.

Couvre :
  - lister_images : filtres extension, fichiers cachés, dossier absent
  - GET /api/images : structure de la réponse
  - GET /api/images/preview/<nom> : sécurité (path traversal),
    extensions, fichiers cachés, fichiers inexistants
"""
from pathlib import Path

import pytest

from services.images_navigateur import (
    EXTENSIONS_AUTORISEES,
    lister_images,
)


@pytest.fixture
def dossier_images_peuple(tmp_path):
    """Crée un dossier images/ avec quelques fichiers de test."""
    images = tmp_path / "images"
    images.mkdir()
    # Fichiers valides (PNG, JPG, PDF)
    (images / "schema-thales.png").write_bytes(b'fake png content')
    (images / "triangle.jpg").write_bytes(b'fake jpg content')
    (images / "graphique.pdf").write_bytes(b'%PDF-1.4 fake')
    # Fichiers à ignorer
    (images / ".hidden.png").write_bytes(b'hidden')
    (images / "readme.txt").write_text("not an image")
    (images / "script.py").write_text("# python")
    # Sous-dossier (doit être ignoré)
    (images / "sous_dossier").mkdir()
    (images / "sous_dossier" / "image-cachee.png").write_bytes(b'pas vu')
    return images


# ── Service lister_images ──────────────────────────────────────────────────

class TestListerImages:

    def test_constantes_publiques(self):
        # Extensions reconnues — ne pas changer sans révision UI.
        assert '.png' in EXTENSIONS_AUTORISEES
        assert '.jpg' in EXTENSIONS_AUTORISEES
        assert '.jpeg' in EXTENSIONS_AUTORISEES
        assert '.pdf' in EXTENSIONS_AUTORISEES
        # Pas d'extension non-image
        assert '.txt' not in EXTENSIONS_AUTORISEES
        assert '.py' not in EXTENSIONS_AUTORISEES

    def test_dossier_inexistant(self, tmp_path):
        """Si data/images/ n'existe pas, retourne liste vide (pas d'erreur)."""
        absent = tmp_path / "pas_la"
        assert lister_images(absent) == []

    def test_dossier_vide(self, tmp_path):
        vide = tmp_path / "images"
        vide.mkdir()
        assert lister_images(vide) == []

    def test_liste_filtree_et_triee(self, dossier_images_peuple):
        images = lister_images(dossier_images_peuple)
        noms = [i["nom"] for i in images]
        # 3 fichiers valides (PNG, JPG, PDF)
        assert noms == ["graphique.pdf", "schema-thales.png", "triangle.jpg"]
        # Vérifications individuelles
        assert ".hidden.png" not in noms, "fichiers cachés exclus"
        assert "readme.txt" not in noms, "extensions non-image exclues"
        assert "script.py" not in noms, "extensions non-image exclues"
        assert "sous_dossier" not in noms, "sous-dossiers exclus"

    def test_format_objet_image(self, dossier_images_peuple):
        images = lister_images(dossier_images_peuple)
        thales = next(i for i in images if i["nom"] == "schema-thales.png")
        assert "nom" in thales
        assert "taille" in thales
        assert thales["taille"] == len(b'fake png content')

    def test_jpeg_aussi_accepte(self, tmp_path):
        """L'extension .jpeg (en plus de .jpg) est dans la whitelist.

        v0.13.7.4 hotfix : ce test ne doit PAS poser deux fichiers qui ne
        diffèrent que par la casse, parce que les systèmes de fichiers
        Windows (NTFS) et macOS (HFS+/APFS par défaut) sont insensibles
        à la casse : le second `write_bytes` écraserait le premier.
        On utilise donc deux noms de base distincts.
        """
        d = tmp_path / "images"
        d.mkdir()
        (d / "photo1.jpeg").write_bytes(b'fake')
        (d / "photo2.JPEG").write_bytes(b'fake')
        noms = [i["nom"] for i in lister_images(d)]
        assert "photo1.jpeg" in noms
        assert "photo2.JPEG" in noms

    def test_extension_casse_insensible(self, tmp_path):
        d = tmp_path / "images"
        d.mkdir()
        (d / "MAJ.PNG").write_bytes(b'fake')
        (d / "min.png").write_bytes(b'fake')
        noms = [i["nom"] for i in lister_images(d)]
        assert "MAJ.PNG" in noms
        assert "min.png" in noms


# ── Routes ────────────────────────────────────────────────────────────────

@pytest.fixture
def app_avec_images(app, tmp_path, monkeypatch):
    """L'app standard, avec data_dir/images/ peuplé.

    On utilise monkeypatch pour rediriger data_dir vers tmp_path.
    """
    # Crée le dossier images dans tmp_path
    images = tmp_path / "images"
    images.mkdir()
    (images / "schema.png").write_bytes(b'fake png')
    (images / "graphique.pdf").write_bytes(b'%PDF-1.4 fake')
    # Redirige data_dir
    monkeypatch.setattr(app.json_store, 'data_dir', str(tmp_path))
    return app


@pytest.fixture
def client_avec_images(app_avec_images):
    return app_avec_images.test_client()


class TestRouteListerImages:

    def test_status_200(self, client_avec_images):
        rep = client_avec_images.get('/api/images')
        assert rep.status_code == 200

    def test_format(self, client_avec_images):
        rep = client_avec_images.get('/api/images')
        data = rep.get_json()
        assert "images" in data
        assert isinstance(data["images"], list)
        noms = [i["nom"] for i in data["images"]]
        assert "schema.png" in noms
        assert "graphique.pdf" in noms

    def test_dossier_absent_retourne_liste_vide(self, app, client):
        """Si le dossier images n'existe pas, retourne 200 avec [] (pas 500)."""
        rep = client.get('/api/images')
        assert rep.status_code == 200
        assert rep.get_json() == {"images": []}


class TestRoutePreview:

    def test_image_existante_servie(self, client_avec_images):
        rep = client_avec_images.get('/api/images/preview/schema.png')
        assert rep.status_code == 200
        assert rep.data == b'fake png'

    def test_pdf_aussi_servi(self, client_avec_images):
        rep = client_avec_images.get('/api/images/preview/graphique.pdf')
        assert rep.status_code == 200
        assert rep.data.startswith(b'%PDF')

    def test_image_inexistante_404(self, client_avec_images):
        rep = client_avec_images.get('/api/images/preview/n-existe-pas.png')
        assert rep.status_code == 404

    # ── Sécurité : path traversal ─────────────────────────────────────────

    def test_path_traversal_avec_dotdot_refuse(self, client_avec_images, tmp_path):
        """`../../etc/passwd` ne doit jamais permettre de lire un fichier
        en dehors du dossier images."""
        # Crée un fichier sensible à côté
        (tmp_path / "secret.png").write_bytes(b'top secret')
        rep = client_avec_images.get('/api/images/preview/..%2Fsecret.png')
        assert rep.status_code == 404
        # Et le contenu ne doit JAMAIS apparaître dans la réponse
        assert b'top secret' not in rep.data

    def test_path_traversal_double_dotdot_refuse(self, client_avec_images):
        rep = client_avec_images.get('/api/images/preview/..%2F..%2Fetc%2Fpasswd')
        assert rep.status_code == 404

    def test_fichier_cache_refuse(self, app_avec_images, client_avec_images, tmp_path):
        """Un fichier commençant par '.' ne doit pas être servi."""
        (tmp_path / "images" / ".cache.png").write_bytes(b'cache')
        rep = client_avec_images.get('/api/images/preview/.cache.png')
        assert rep.status_code == 404

    def test_extension_non_image_refuse(self, app_avec_images, client_avec_images, tmp_path):
        """Même si un .txt existe dans le dossier images, on refuse de
        le servir (whitelist d'extensions)."""
        (tmp_path / "images" / "readme.txt").write_bytes(b'docs')
        rep = client_avec_images.get('/api/images/preview/readme.txt')
        assert rep.status_code == 404

    def test_caractere_separateur_dans_le_nom_refuse(self, client_avec_images):
        """Un slash dans le nom est refusé même si le chemin résolu serait valide."""
        # Flask peut interpréter %2F différemment selon les versions, on teste
        # plusieurs encodages.
        for encodage in ['sous%2Ffichier.png', 'sous%5Cfichier.png']:
            rep = client_avec_images.get(f'/api/images/preview/{encodage}')
            assert rep.status_code == 404, f"Échec pour {encodage}"
