"""tests/test_v0_15_2_7_log_live_workdir.py — v0.15.2.7

Bugfix : la page courante affichée dans l'UI était FIGÉE sur la dernière
page de la compilation PRÉCÉDENTE (ou rien si premier compile), parce
qu'on lisait l'artefact final `_artefacts/<doc_id>/<cible_key>.log`
qui n'est écrit qu'APRÈS la compilation.

Le fix : pdflatex tourne dans un **workdir persistant** au chemin connu
(`tempfile.gettempdir()/seqenseigne_workdir/<doc_id>/<cible_key>`), et
`lire_statut` lit ce LIVE `atome.log` qui est rempli progressivement
pendant que pdflatex tourne.

Ces tests protègent :
- Le calcul des chemins de workdir et de log live.
- Le fait que `_ouvrir_workdir` nettoie le dossier en début d'appel
  (évite la pollution `.aux`/`Corriges/` d'un run précédent) et le
  PERSISTE après le yield (pour qu'on puisse en relire le log).
- L'option historique `workdir=None` → `tempfile.TemporaryDirectory`
  éphémère (rétrocompat : tests, scripts).
"""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import orchestrateur_compilation as orch  # noqa: E402
from services.compilateur_pdf import _ouvrir_workdir  # noqa: E402


# ── Chemins workdir et log live ─────────────────────────────────────────────


def test_chemin_workdir_cible_est_sous_tempdir():
    """Le workdir doit être sous tempfile.gettempdir(), PAS sous le
    dossier_artefacts : on profite d'un disque rapide (typiquement
    SSD interne) même quand l'app tourne depuis l'USB (cas Laurent).
    """
    artefacts = Path('/quelque/part/sur/usb/_artefacts/doc_abc')
    wd = orch.chemin_workdir_cible(artefacts, 'N10_S03')
    # Sous tempdir
    assert str(wd).startswith(tempfile.gettempdir())
    # Pas sous artefacts
    assert '_artefacts' not in str(wd)


def test_chemin_workdir_cible_discrimine_par_doc_et_cible():
    """Deux documents différents ne doivent pas partager de workdir,
    et deux cibles d'un même document non plus."""
    art1 = Path('/x/_artefacts/doc_001')
    art2 = Path('/x/_artefacts/doc_002')
    wd1a = orch.chemin_workdir_cible(art1, 'N10_S01')
    wd1b = orch.chemin_workdir_cible(art1, 'N10_S02')
    wd2a = orch.chemin_workdir_cible(art2, 'N10_S01')
    assert wd1a != wd1b      # même doc, cibles différentes
    assert wd1a != wd2a      # docs différents, même cible


def test_chemin_log_courant_pointe_sur_atome_log():
    """C'est `atome.log` (nom écrit par pdflatex, cf. compilateur_pdf),
    pas un autre nom calqué sur la cible_key."""
    art = Path('/x/_artefacts/doc_abc')
    log = orch.chemin_log_courant_cible(art, 'N10_S03')
    wd  = orch.chemin_workdir_cible(art, 'N10_S03')
    assert log == wd / 'atome.log'


# ── Context manager : workdir=None vs Path ──────────────────────────────────


def test_ouvrir_workdir_none_est_ephemere():
    """workdir=None : on doit avoir un TemporaryDirectory détruit en
    sortie (rétrocompat avec tous les tests existants qui appellent
    compiler_atome sans workdir)."""
    chemin_yield = None
    with _ouvrir_workdir(None) as d:
        chemin_yield = d
        assert d.is_dir()
    # Après sortie : disparu
    assert not chemin_yield.exists()


def test_ouvrir_workdir_explicit_persiste(tmp_path):
    """workdir explicite : le dossier persiste APRÈS le yield (c'est
    ce qui permet de lire le log post-mortem, même si on n'utilise pas
    ce comportement directement)."""
    target = tmp_path / 'mon_workdir'
    with _ouvrir_workdir(target) as d:
        assert d == target
        assert d.is_dir()
        (d / 'atome.log').write_text('[1] [2] [3]\n')
    # Après sortie : toujours là
    assert target.exists()
    assert (target / 'atome.log').read_text() == '[1] [2] [3]\n'


def test_ouvrir_workdir_nettoie_residus(tmp_path):
    """workdir contenant des résidus d'un run précédent : doivent être
    purgés en début d'appel (sinon le compile actuel verrait des
    .aux/Corriges/ orphelins)."""
    target = tmp_path / 'mon_workdir'
    target.mkdir()
    (target / 'atome.aux').write_text('old aux')
    (target / 'Corriges').mkdir()
    (target / 'Corriges' / 'c1e1.tex').write_text('old corrige')

    with _ouvrir_workdir(target) as d:
        assert d == target
        # Le dossier doit être propre
        assert not (d / 'atome.aux').exists()
        assert not (d / 'Corriges' / 'c1e1.tex').exists()
        # Le dossier lui-même existe (vide)
        assert d.is_dir()
        assert list(d.iterdir()) == []


def test_ouvrir_workdir_chemin_inexistant_est_cree(tmp_path):
    """Le workdir peut ne pas exister au départ : on doit le créer
    (mkdir parents=True)."""
    target = tmp_path / 'pas_la' / 'sub' / 'workdir'
    assert not target.exists()
    with _ouvrir_workdir(target) as d:
        assert d == target
        assert d.is_dir()


# ── Smoke test bout-en-bout : compilation produit un log dans workdir ──────


def test_compiler_atome_avec_workdir_ecrit_log_live(tmp_path):
    """Si pdflatex est disponible, on vérifie qu'avec workdir explicite
    le log apparaît bien à l'emplacement attendu (pas dans un tempdir
    inaccessible). Skip si pdflatex absent (cas CI Docker minimaliste).
    """
    from services.compilateur_pdf import detecter_pdflatex, compiler_atome
    pdflatex = detecter_pdflatex()
    if not pdflatex:
        pytest.skip("pdflatex non détecté dans cet environnement")

    workdir = tmp_path / 'wd'
    tex = (
        r'\documentclass{article}'
        '\n'
        r'\begin{document}'
        '\n'
        r'Test page 1.\newpage Test page 2.'
        '\n'
        r'\end{document}'
        '\n'
    )
    res = compiler_atome(
        tex_source=tex,
        pdflatex=pdflatex,
        workdir=workdir,
        timeout=30,
    )
    # On ne juge pas du succès (selon les paquets installés, ça peut
    # rater) ; on vérifie juste que le log est apparu à l'emplacement
    # attendu, ce qui prouve que le workdir fait son office.
    assert (workdir / 'atome.log').exists(), (
        f"atome.log absent du workdir après compile. "
        f"Compile ok={res.ok}, dossier={list(workdir.iterdir())}"
    )
