"""Tests de outils/verifier_md5.py.

Vérifie :
- la lecture du manifeste (format historique appli_inventaire.txt + variantes)
- la détection des cas de divergence : manquant, taille différente, md5 différent
- la génération inverse (--generer)
- les codes de sortie (0 / 1 / 2)
- la robustesse aux entrées dégradées
"""
from __future__ import annotations
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest


# Le script à tester est dans appli/outils/, les tests sont dans appli/tests/
SCRIPT = Path(__file__).resolve().parent.parent / "outils" / "verifier_md5.py"


# ---------- Fixtures ------------------------------------------------------

@pytest.fixture
def arbo(tmp_path):
    """Crée une mini-arbo de test :

        tmp/
          alpha.py     (10 octets)
          beta.txt     (5 octets)
          sub/
            gamma.js   (15 octets)
    """
    (tmp_path / "alpha.py").write_text("0123456789")
    (tmp_path / "beta.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "gamma.js").write_text("var x = 1;//abc")
    return tmp_path


def _md5(data: str) -> str:
    return hashlib.md5(data.encode()).hexdigest()


def _ecrire_manifest(chemin: Path, *entrees: tuple[str, int, str]) -> None:
    """entrees = (md5, taille, chemin_relatif)+"""
    chemin.write_text(
        "\n".join(f"{m}  {t}  {c}" for m, t, c in entrees) + "\n",
        encoding="utf-8",
    )


def _executer(arbo: Path, *args: str) -> subprocess.CompletedProcess:
    """Lance le script et retourne le résultat capturé."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--racine", str(arbo), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


# ---------- Lecture du manifeste -----------------------------------------

class TestLectureManifest:
    def test_format_standard(self, arbo, tmp_path):
        manifest = tmp_path / "MANIFEST.md5"
        _ecrire_manifest(
            manifest,
            (_md5("0123456789"), 10, "alpha.py"),
            (_md5("hello"), 5, "beta.txt"),
        )
        r = _executer(arbo, "--manifest", str(manifest))
        assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"
        assert "aucune divergence" in r.stdout

    def test_separateurs_backslash_acceptes(self, arbo, tmp_path):
        """Le format historique appli_inventaire.txt utilise des '\\\\'."""
        manifest = tmp_path / "MANIFEST.md5"
        # Note : on écrit "sub\\gamma.js" en Python = un seul backslash dans le fichier
        manifest.write_text(
            f"{_md5('var x = 1;//abc')}  15  sub\\gamma.js\n",
            encoding="utf-8",
        )
        r = _executer(arbo, "--manifest", str(manifest))
        assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"

    def test_bom_utf8_tolere(self, arbo, tmp_path):
        """Le générateur PowerShell historique écrit avec un BOM UTF-8."""
        manifest = tmp_path / "MANIFEST.md5"
        manifest.write_bytes(
            "\ufeff".encode("utf-8") +
            f"{_md5('0123456789')}  10  alpha.py\n".encode("utf-8")
        )
        r = _executer(arbo, "--manifest", str(manifest))
        assert r.returncode == 0, f"stdout: {r.stdout}"

    def test_lignes_vides_et_commentaires_ignorees(self, arbo, tmp_path):
        manifest = tmp_path / "MANIFEST.md5"
        manifest.write_text(
            "# Commentaire en tête\n"
            "\n"
            f"{_md5('0123456789')}  10  alpha.py\n"
            "  # Commentaire indenté\n"
            "\n",
            encoding="utf-8",
        )
        r = _executer(arbo, "--manifest", str(manifest))
        assert r.returncode == 0

    def test_lignes_pourries_signalees_mais_pas_bloquantes(self, arbo, tmp_path):
        manifest = tmp_path / "MANIFEST.md5"
        manifest.write_text(
            "ligne_qui_a_pas_le_format\n"
            "abc  pas_un_nombre  fichier.py\n"
            f"{_md5('0123456789')}  10  alpha.py\n",
            encoding="utf-8",
        )
        r = _executer(arbo, "--manifest", str(manifest))
        assert r.returncode == 0
        assert "ligne 1 ignorée" in r.stderr
        assert "ligne 2 ignorée" in r.stderr


# ---------- Détection des divergences ------------------------------------

class TestDivergences:
    def test_manquant(self, arbo, tmp_path):
        manifest = tmp_path / "MANIFEST.md5"
        _ecrire_manifest(
            manifest,
            (_md5("contenu_imaginaire"), 18, "fichier_inexistant.py"),
        )
        r = _executer(arbo, "--manifest", str(manifest))
        assert r.returncode == 1
        assert "MANQUANT" in r.stdout
        assert "fichier_inexistant.py" in r.stdout

    def test_taille_differente(self, arbo, tmp_path):
        """Cas : fichier tronqué ou augmenté → détection taille."""
        manifest = tmp_path / "MANIFEST.md5"
        _ecrire_manifest(
            manifest,
            (_md5("contenu_imaginaire"), 50, "alpha.py"),  # 50 attendu, 10 réel
        )
        r = _executer(arbo, "--manifest", str(manifest))
        assert r.returncode == 1
        assert "TRONQUÉ" in r.stdout
        assert "(-40 octets)" in r.stdout

    def test_taille_egale_md5_different(self, arbo, tmp_path):
        """Cas : modification de contenu sans changer la taille."""
        # alpha.py a 10 octets, contient "0123456789"
        # On met dans le manifeste le même 10 octets mais un autre MD5
        manifest = tmp_path / "MANIFEST.md5"
        _ecrire_manifest(
            manifest,
            (_md5("autre_chose_meme_taille_xx"), 10, "alpha.py"),
        )
        r = _executer(arbo, "--manifest", str(manifest))
        assert r.returncode == 1
        assert "MODIFIÉ" in r.stdout

    def test_match_complet(self, arbo, tmp_path):
        manifest = tmp_path / "MANIFEST.md5"
        _ecrire_manifest(
            manifest,
            (_md5("0123456789"), 10, "alpha.py"),
            (_md5("hello"), 5, "beta.txt"),
            (_md5("var x = 1;//abc"), 15, "sub/gamma.js"),
        )
        r = _executer(arbo, "--manifest", str(manifest))
        assert r.returncode == 0
        assert "3 fichier(s) vérifié(s)" in r.stdout


# ---------- Génération inverse -------------------------------------------

class TestGeneration:
    def test_genere_manifest_complet(self, arbo, tmp_path):
        """--generer produit un manifeste qui se vérifie ensuite OK."""
        manifest = tmp_path / "MANIFEST.md5"
        # On écrit le manifeste à un endroit hors arbo pour pas qu'il
        # se compte lui-même
        r = _executer(arbo, "--generer", "--manifest", str(manifest),
                      "--extensions", ".py,.txt,.js")
        assert r.returncode == 0
        assert manifest.is_file()
        contenu = manifest.read_text(encoding="utf-8")
        # 3 fichiers attendus : alpha.py, beta.txt, sub/gamma.js
        lignes = [l for l in contenu.splitlines() if l.strip()]
        assert len(lignes) == 3
        # Re-vérifier avec ce manifest doit être OK
        r2 = _executer(arbo, "--manifest", str(manifest))
        assert r2.returncode == 0

    def test_generer_filtre_extensions(self, arbo, tmp_path):
        """--extensions limite ce qui est inclus."""
        manifest = tmp_path / "MANIFEST.md5"
        r = _executer(arbo, "--generer", "--manifest", str(manifest),
                      "--extensions", ".py")
        assert r.returncode == 0
        contenu = manifest.read_text(encoding="utf-8")
        # Seul alpha.py doit être présent
        assert "alpha.py" in contenu
        assert "beta.txt" not in contenu
        assert "gamma.js" not in contenu

    def test_generer_chemins_avec_slash_portable(self, arbo, tmp_path):
        """Les chemins générés utilisent '/' (portable Linux/Windows)."""
        manifest = tmp_path / "MANIFEST.md5"
        r = _executer(arbo, "--generer", "--manifest", str(manifest),
                      "--extensions", ".js")
        assert r.returncode == 0
        contenu = manifest.read_text(encoding="utf-8")
        assert "sub/gamma.js" in contenu
        assert "sub\\gamma.js" not in contenu


# ---------- Codes de sortie ----------------------------------------------

class TestCodesSortie:
    def test_zero_si_tout_ok(self, arbo, tmp_path):
        manifest = tmp_path / "MANIFEST.md5"
        _ecrire_manifest(manifest, (_md5("0123456789"), 10, "alpha.py"))
        r = _executer(arbo, "--manifest", str(manifest))
        assert r.returncode == 0

    def test_un_si_divergence(self, arbo, tmp_path):
        manifest = tmp_path / "MANIFEST.md5"
        _ecrire_manifest(manifest, (_md5("xx"), 10, "alpha.py"))
        r = _executer(arbo, "--manifest", str(manifest))
        assert r.returncode == 1

    def test_deux_si_manifest_introuvable(self, arbo):
        r = _executer(arbo, "--manifest", "/tmp/n_existe_pas.md5")
        assert r.returncode == 2
        assert "introuvable" in r.stderr.lower()

    def test_deux_si_racine_introuvable(self, tmp_path):
        manifest = tmp_path / "M.md5"
        manifest.write_text("\n", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--racine", "/tmp/dossier_qui_existe_pas",
             "--manifest", str(manifest)],
            capture_output=True, text=True, encoding="utf-8",
        )
        assert r.returncode == 2


# ---------- Sortie CSV ---------------------------------------------------

class TestCSV:
    def test_format_csv(self, arbo, tmp_path):
        manifest = tmp_path / "MANIFEST.md5"
        _ecrire_manifest(
            manifest,
            (_md5("xx"), 99, "alpha.py"),
            (_md5("yy"), 100, "fichier_inexistant.py"),
        )
        r = _executer(arbo, "--manifest", str(manifest), "--csv")
        assert r.returncode == 1
        lignes = [l for l in r.stdout.splitlines() if l.strip()]
        # Ligne d'entête + 2 divergences
        assert len(lignes) == 3
        assert lignes[0].startswith("type;chemin;")
        # Chaque ligne de divergence a 6 colonnes (5 séparateurs ';')
        for ligne in lignes[1:]:
            assert ligne.count(";") == 5


# ---------- Mode silencieux ----------------------------------------------

class TestSilencieux:
    def test_silencieux_aucune_sortie_si_ok(self, arbo, tmp_path):
        manifest = tmp_path / "MANIFEST.md5"
        _ecrire_manifest(manifest, (_md5("0123456789"), 10, "alpha.py"))
        r = _executer(arbo, "--manifest", str(manifest), "--silencieux")
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_silencieux_affiche_si_divergence(self, arbo, tmp_path):
        manifest = tmp_path / "MANIFEST.md5"
        _ecrire_manifest(manifest, (_md5("xx"), 10, "alpha.py"))
        r = _executer(arbo, "--manifest", str(manifest), "--silencieux")
        assert r.returncode == 1
        assert "MODIFIÉ" in r.stdout


# ---------- Cas réel : détection d'un fichier tronqué -------------------

class TestCasReelLatexRenduAtome:
    """Reproduit le cas réel diagnostiqué le 10 mai 2026 : un fichier
    Python qui se termine au milieu d'une fonction (pas de return),
    avec une taille inférieure à celle attendue.

    Le script doit le détecter sans avoir besoin que la syntaxe Python
    soit invalide.
    """

    def test_detection_troncature_en_milieu_de_fonction(self, tmp_path):
        # Fichier "complet" de référence
        contenu_complet = (
            b"def foo():\n"
            b"    x = 1\n"
            b"    y = 2\n"
            b"    return x + y\n"
        )
        # Version tronquée : on coupe à la 2e ligne (fonction sans return)
        contenu_tronque = b"def foo():\n    x = 1\n"

        # IMPORTANT : on écrit en write_bytes() pour garder le contrôle
        # exact des octets sur disque. Sur Windows, write_text() applique
        # la conversion \n → \r\n par défaut, ce qui ajoute 2 octets ici
        # et fait diverger la taille calculée par l'OS de la taille
        # attendue par len(contenu).
        chemin = tmp_path / "service.py"
        chemin.write_bytes(contenu_tronque)

        # Le manifeste référence la version complète (taille + md5),
        # calculés sur les octets exacts.
        md5_complet = hashlib.md5(contenu_complet).hexdigest()
        manifest = tmp_path / "MANIFEST.md5"
        manifest.write_text(
            f"{md5_complet}  {len(contenu_complet)}  service.py\n",
            encoding="utf-8",
        )

        r = _executer(tmp_path, "--manifest", str(manifest))
        assert r.returncode == 1
        assert "TRONQUÉ" in r.stdout
        # diff négatif (version courte chez l'utilisateur)
        diff_attendu = len(contenu_tronque) - len(contenu_complet)
        assert f"({diff_attendu} octets)" in r.stdout
