r"""
tests/test_v0_16_viewer_pdfjs.py — Intégration du viewer pdf.js embarqué.

CONTEXTE (v0.16 — « Affichage PDF en iframe forcé »)
-----------------------------------------------------
Sur poste verrouillé d'établissement, le navigateur peut être configuré pour
ouvrir les PDF dans une nouvelle fenêtre ou les télécharger au lieu de les
afficher inline dans l'iframe de rendu. Pour garantir un rendu inline
identique quel que soit le navigateur, on embarque le viewer pdf.js
(static/vendor/pdfjs) qui dessine le PDF dans un <canvas> : le navigateur ne
voit jamais un content-type application/pdf à « gérer ».

CE QUE CE TEST VERROUILLE
-------------------------
1. Les fichiers runtime essentiels du viewer sont présents dans le dépôt
   (build/pdf.mjs, build/pdf.worker.mjs, web/viewer.html, viewer.mjs,
   viewer.css) — un `git clean` ou un oubli de livraison casserait le rendu.
2. Flask sert ces fichiers (200) et — point critique sur Windows — les
   modules ES `.mjs` sont renvoyés avec un MIME type JavaScript, sans quoi
   le navigateur refuse de les exécuter.
3. Le worker pdf.js est résolu au bon chemin relatif (`../build/...`).
4. Le code de rendu (atelier_editeur.js) route bien l'affichage par le
   viewer embarqué et non par une affectation directe `iframe.src = blob`.
5. Le viewer ne dépend d'aucune ressource externe bloquante (hors-ligne).
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

import pytest

_APPLI = Path(__file__).resolve().parent.parent
_VENDOR = _APPLI / "static" / "vendor" / "pdfjs"

# Fichiers runtime indispensables (chemins relatifs à static/vendor/pdfjs).
_FICHIERS_REQUIS = [
    "build/pdf.mjs",
    "build/pdf.worker.mjs",
    "web/viewer.html",
    "web/viewer.mjs",
    "web/viewer.css",
    "web/locale/locale.json",
    "web/locale/fr/viewer.ftl",
]


class TestFichiersVendorPresents:
    @pytest.mark.parametrize("rel", _FICHIERS_REQUIS)
    def test_fichier_present(self, rel):
        f = _VENDOR / rel
        assert f.is_file(), (
            f"Fichier pdf.js manquant : static/vendor/pdfjs/{rel}. "
            f"Le viewer ne fonctionnera pas. Cf. v0.16."
        )

    def test_worker_chemin_relatif_correct(self):
        # Le viewer attend le worker en ../build/pdf.worker.mjs (relatif à
        # web/). On vérifie que cette résolution mène à un fichier réel.
        viewer = _VENDOR / "web" / "viewer.mjs"
        src = viewer.read_text(encoding="utf-8", errors="replace")
        assert '"../build/pdf.worker.mjs"' in src, (
            "Le workerSrc par défaut du viewer n'est plus "
            "'../build/pdf.worker.mjs' : vérifier la version de pdf.js."
        )
        assert (_VENDOR / "build" / "pdf.worker.mjs").is_file()

    def test_locale_json_reduit(self):
        # On a réduit locale.json à fr + en-US pour éviter 110 requêtes
        # .ftl vers des fichiers absents.
        import json
        data = json.loads((_VENDOR / "web" / "locale" / "locale.json")
                          .read_text(encoding="utf-8"))
        assert set(data.keys()) <= {"fr", "en-us", "en-US"}, (
            f"locale.json devrait être réduit à fr/en-US, trouvé : "
            f"{sorted(data.keys())}"
        )


class TestMimeMjsForce:
    def test_mimetypes_mjs_est_javascript(self):
        # app.py force mimetypes.add_type au niveau module. L'importer
        # applique l'effet de bord.
        import app  # noqa: F401  (effet de bord : add_type)
        typ, _ = mimetypes.guess_type("x.mjs")
        assert typ == "text/javascript", (
            f".mjs devrait être servi en text/javascript, pas {typ!r}. "
            f"Sans quoi les navigateurs refusent d'exécuter les modules ES "
            f"du viewer (piège Windows). Cf. app.py v0.16."
        )


class TestFlaskSertLeViewer:
    @pytest.fixture
    def client(self):
        import app as app_module
        application = app_module.create_app()
        application.config["TESTING"] = True
        return application.test_client()

    def test_viewer_html_servi(self, client):
        r = client.get("/static/vendor/pdfjs/web/viewer.html")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("Content-Type", "")

    @pytest.mark.parametrize("rel", [
        "build/pdf.mjs",
        "build/pdf.worker.mjs",
        "web/viewer.mjs",
    ])
    def test_modules_mjs_servis_en_javascript(self, client, rel):
        r = client.get(f"/static/vendor/pdfjs/{rel}")
        assert r.status_code == 200
        ctype = r.headers.get("Content-Type", "")
        assert "javascript" in ctype, (
            f"{rel} servi en {ctype!r} au lieu d'un type JavaScript. "
            f"Les modules ES ne s'exécuteront pas."
        )


class TestPasDeRessourceExterneBloquante:
    def test_viewer_html_pas_de_script_cdn(self):
        html = (_VENDOR / "web" / "viewer.html").read_text(
            encoding="utf-8", errors="replace")
        # Aucun <script src="http...> ni <link href="http...> externe.
        import re
        for m in re.finditer(r'<(?:script|link)[^>]+(?:src|href)\s*=\s*'
                             r'["\'](https?://[^"\']+)', html):
            pytest.fail(
                f"viewer.html charge une ressource externe : {m.group(1)}. "
                f"Le viewer doit être 100% hors-ligne."
            )


class TestCodeJsRouteParLeViewer:
    def test_atelier_editeur_utilise_le_viewer(self):
        src = (_APPLI / "static" / "atelier_editeur.js").read_text(
            encoding="utf-8")
        # La méthode d'affichage via viewer existe et est appelée.
        assert "_afficherPdfDansViewer" in src
        assert "vendor/pdfjs/web/viewer.html" in src
        # On ne doit plus faire l'affectation directe historique
        # `iframe.src = url;` (remplacée par l'appel au viewer).
        assert "iframe.src = url;" not in src, (
            "Affectation directe `iframe.src = url` encore présente : "
            "l'affichage doit passer par _afficherPdfDansViewer (v0.16)."
        )
