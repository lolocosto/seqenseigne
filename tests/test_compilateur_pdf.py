r"""
tests/test_compilateur_pdf.py — Tests du service de compilation PDF.

Couvre :
  - hash_tex : stabilité, unicité
  - detecter_pdflatex : env var, PATH, MiKTeX portable
  - extraire_erreurs : formats "! ..." et "fichier.tex:N:"
  - compiler_atome : succès, erreur LaTeX, cache, timeout, pdflatex absent

Les tests de compilation réelle nécessitent pdflatex — ils sont skipped
automatiquement si l'exécutable n'est pas trouvé.
"""

from __future__ import annotations
import os
import pytest
import shutil
import sys
from pathlib import Path

from services.compilateur_pdf import (
    hash_tex,
    detecter_pdflatex,
    extraire_erreurs,
    compiler_atome,
    chemin_pdf_cache,
    chemin_log_cache,
    ErreurLatex,
    ResultatCompilation,
    ENV_PDFLATEX,
)


PDFLATEX_DISPO = shutil.which('pdflatex') is not None


# ── hash_tex ──────────────────────────────────────────────────────────────────

class TestHashTex:

    def test_hash_stable(self):
        assert hash_tex('abc') == hash_tex('abc')

    def test_hash_different_pour_sources_differentes(self):
        assert hash_tex('abc') != hash_tex('abd')

    def test_longueur_fixe(self):
        assert len(hash_tex('')) == 16
        assert len(hash_tex('a' * 10000)) == 16

    def test_utf8_gere(self):
        # Caractères français / mathématiques
        h1 = hash_tex('Équation : α + β')
        h2 = hash_tex('Équation : α + β')
        assert h1 == h2


# ── detecter_pdflatex ────────────────────────────────────────────────────────

class TestDetecterPdflatex:

    def test_env_var_prioritaire(self, tmp_path, monkeypatch):
        """Si SEQENSEIGNE_PDFLATEX est défini et valide, il prime."""
        # Créer un faux exécutable
        faux = tmp_path / 'faux_pdflatex'
        faux.write_text('#!/bin/sh\nexit 0\n')
        faux.chmod(0o755)

        monkeypatch.setenv(ENV_PDFLATEX, str(faux))
        assert detecter_pdflatex() == str(faux)

    def test_env_var_inexistante_ignoree(self, monkeypatch):
        """Si la variable pointe vers un fichier inexistant, on passe au fallback."""
        monkeypatch.setenv(ENV_PDFLATEX, '/chemin/inexistant/pdflatex')
        result = detecter_pdflatex()
        # Peut trouver via PATH si pdflatex y est, ou None
        if PDFLATEX_DISPO:
            assert result is not None
            assert '/chemin/inexistant' not in result

    def test_fallback_path(self, monkeypatch):
        """Sans variable d'environnement, fallback sur PATH."""
        monkeypatch.delenv(ENV_PDFLATEX, raising=False)
        result = detecter_pdflatex()
        if PDFLATEX_DISPO:
            assert result is not None
            assert 'pdflatex' in result.lower()

    def test_miktex_portable(self, tmp_path, monkeypatch):
        """Structure classique racine/../outils/MiKTeX/miktex/bin/x64/pdflatex.exe"""
        monkeypatch.delenv(ENV_PDFLATEX, raising=False)
        monkeypatch.setenv('PATH', '/nexistepas')

        racine_appli = tmp_path / 'appli'
        racine_appli.mkdir()
        bin_dir = tmp_path / 'outils' / 'MiKTeX' / 'miktex' / 'bin' / 'x64'
        bin_dir.mkdir(parents=True)
        faux = bin_dir / 'pdflatex.exe'
        faux.write_text('')

        result = detecter_pdflatex(racine_appli=racine_appli)
        assert result == str(faux)

    def test_miktex_portable_convention_texmfs(self, tmp_path, monkeypatch):
        """Structure MiKTeX portable moderne : outils/MikTex/texmfs/install/miktex/bin/x64
        (c'est la structure qu'impose MiKTeX portable depuis 2022)."""
        monkeypatch.delenv(ENV_PDFLATEX, raising=False)
        monkeypatch.setenv('PATH', '/nexistepas')

        racine_appli = tmp_path / 'appli'
        racine_appli.mkdir()
        bin_dir = (tmp_path / 'outils' / 'MikTex' / 'texmfs'
                   / 'install' / 'miktex' / 'bin' / 'x64')
        bin_dir.mkdir(parents=True)
        faux = bin_dir / 'pdflatex.exe'
        faux.write_text('')

        result = detecter_pdflatex(racine_appli=racine_appli)
        assert result == str(faux)

    def test_miktex_portable_prioritaire_sur_path(self, tmp_path, monkeypatch):
        """Si MiKTeX portable est à côté de l'appli, il prime sur le pdflatex
        éventuellement trouvé dans le PATH système."""
        monkeypatch.delenv(ENV_PDFLATEX, raising=False)
        # Laisser le PATH tel quel : s'il y a un pdflatex système, il ne doit
        # pas être retenu.

        racine_appli = tmp_path / 'appli'
        racine_appli.mkdir()
        bin_dir = tmp_path / 'outils' / 'MiKTeX' / 'miktex' / 'bin' / 'x64'
        bin_dir.mkdir(parents=True)
        faux = bin_dir / 'pdflatex.exe'
        faux.write_text('')

        result = detecter_pdflatex(racine_appli=racine_appli)
        assert result == str(faux), (
            "Le MiKTeX portable doit être prioritaire sur le PATH système."
        )

    def test_miktex_fallback_rglob(self, tmp_path, monkeypatch):
        """Si la structure du portable ne correspond à aucun chemin connu,
        le glob récursif doit quand même trouver le pdflatex."""
        monkeypatch.delenv(ENV_PDFLATEX, raising=False)
        monkeypatch.setenv('PATH', '/nexistepas')

        racine_appli = tmp_path / 'appli'
        racine_appli.mkdir()
        # Chemin exotique non listé dans _CHEMINS_MIKTEX_RELATIFS
        bin_dir = tmp_path / 'outils' / 'une' / 'autre' / 'arbo'
        bin_dir.mkdir(parents=True)
        faux = bin_dir / 'pdflatex.exe'
        faux.write_text('')

        result = detecter_pdflatex(racine_appli=racine_appli)
        assert result == str(faux)

    def test_aucun_pdflatex(self, monkeypatch, tmp_path):
        monkeypatch.delenv(ENV_PDFLATEX, raising=False)
        monkeypatch.setenv('PATH', '/nexistepas')
        racine = tmp_path / 'appli'
        racine.mkdir()
        assert detecter_pdflatex(racine_appli=racine) is None


# ── extraire_erreurs ─────────────────────────────────────────────────────────

class TestExtraireErreurs:

    def test_erreur_exclamation_avec_ligne(self):
        log = """
This is pdfTeX
! Undefined control sequence.
l.42 Calculer \\seqInconnu
"""
        erreurs = extraire_erreurs(log)
        assert len(erreurs) >= 1
        e = erreurs[0]
        assert e.ligne == 42
        assert 'Undefined control sequence' in e.message
        assert 'seqInconnu' in e.contexte

    def test_erreur_sans_ligne(self):
        log = "! Emergency stop.\n!  ==> Fatal error"
        erreurs = extraire_erreurs(log)
        # Au moins une erreur sans numéro de ligne
        sans_ligne = [e for e in erreurs if e.ligne is None]
        assert sans_ligne

    def test_format_colon(self):
        log = "./atome.tex:17: Missing $ inserted."
        erreurs = extraire_erreurs(log)
        assert any(e.ligne == 17 for e in erreurs)

    def test_log_vide(self):
        assert extraire_erreurs('') == []

    def test_log_sans_erreur(self):
        log = """
This is pdfTeX, Version 3.14
LaTeX2e <2023>
(./atome.tex [1] (./atome.aux))
Output written on atome.pdf (1 page).
"""
        assert extraire_erreurs(log) == []


# ── compiler_atome : erreurs sans pdflatex ───────────────────────────────────

class TestCompilerAtomeSansPdflatex:

    def test_pdflatex_introuvable(self, monkeypatch, tmp_path):
        """Si aucun pdflatex, on retourne une erreur structurée (pas d'exception)."""
        monkeypatch.delenv(ENV_PDFLATEX, raising=False)
        monkeypatch.setenv('PATH', '/nexistepas')

        res = compiler_atome(
            r'\documentclass{article}\begin{document}x\end{document}',
            racine_appli=tmp_path,   # pas de MiKTeX portable
        )
        assert res.ok is False
        assert any('pdflatex' in e.message.lower() for e in res.erreurs)

    def test_pdflatex_chemin_invalide(self, tmp_path):
        """pdflatex= pointant vers un fichier inexistant."""
        res = compiler_atome(
            r'\documentclass{article}\begin{document}x\end{document}',
            pdflatex='/chemin/nexistepas/pdflatex',
        )
        assert res.ok is False


# ── compiler_atome : vraie compilation ───────────────────────────────────────

@pytest.mark.skipif(not PDFLATEX_DISPO,
                    reason='pdflatex non disponible')
class TestCompilerAtomeReel:

    def test_compilation_simple_reussit(self):
        tex = r"""
\documentclass{article}
\begin{document}
Bonjour, monde.
\end{document}
"""
        res = compiler_atome(tex)
        assert res.ok is True
        assert res.pdf_bytes.startswith(b'%PDF')
        assert res.duree_ms > 0
        assert res.erreurs == []

    def test_compilation_echouee_macro_inconnue(self):
        tex = r"""
\documentclass{article}
\begin{document}
\macroInconnueQuiNExistePas{x}
\end{document}
"""
        res = compiler_atome(tex)
        assert res.ok is False
        assert res.erreurs
        # La ligne de l'erreur doit être identifiée
        assert any(e.ligne is not None for e in res.erreurs)

    def test_cache_hit(self, tmp_path):
        tex = r"""
\documentclass{article}
\begin{document}
Test cache.
\end{document}
"""
        cache = tmp_path / 'cache'

        # 1er appel : compile
        r1 = compiler_atome(tex, cache_dir=cache)
        assert r1.ok
        assert r1.depuis_cache is False

        # 2e appel : cache
        r2 = compiler_atome(tex, cache_dir=cache)
        assert r2.ok
        assert r2.depuis_cache is True
        assert r2.duree_ms == 0
        # Même PDF
        assert r2.pdf_bytes == r1.pdf_bytes

    def test_cache_invalide_par_changement(self, tmp_path):
        """Un changement de .tex invalide le cache automatiquement."""
        cache = tmp_path / 'cache'
        tex1 = r'\documentclass{article}\begin{document}A\end{document}'
        tex2 = r'\documentclass{article}\begin{document}B\end{document}'

        compiler_atome(tex1, cache_dir=cache)
        r = compiler_atome(tex2, cache_dir=cache)
        assert r.depuis_cache is False
        # Deux PDF en cache
        pdfs = list(cache.glob('*.pdf'))
        assert len(pdfs) == 2

    def test_pdf_ecrit_sur_disque_si_cache(self, tmp_path):
        cache = tmp_path / 'cache'
        tex = r'\documentclass{article}\begin{document}X\end{document}'
        r = compiler_atome(tex, cache_dir=cache)
        assert r.pdf_path is not None
        assert r.pdf_path.is_file()
        # Log aussi
        log_path = chemin_log_cache(cache, hash_tex(tex))
        assert log_path.is_file()

    def test_timeout(self):
        """Un .tex qui boucle se fait tuer."""
        # Boucle infinie en TeX : \loop ... \repeat sans condition d'arrêt
        tex = r"""
\documentclass{article}
\begin{document}
\newcount\c
\loop\advance\c by 1
\ifnum\c<1000000000 \repeat
\end{document}
"""
        res = compiler_atome(tex, timeout=2)
        assert res.ok is False
        assert any('timeout' in e.message.lower() for e in res.erreurs)
        assert res.duree_ms >= 2000

    def test_racine_sources_dans_texinputs(self, tmp_path):
        """Un .tex qui \\input un fichier dans racine_sources doit le trouver."""
        sources = tmp_path / 'sources'
        sources.mkdir()
        (sources / 'inclus.tex').write_text(
            r'Contenu inclus.',
            encoding='utf-8',
        )
        tex = r"""
\documentclass{article}
\begin{document}
\input{inclus}
\end{document}
"""
        res = compiler_atome(tex, racine_sources=sources)
        assert res.ok, (
            f"Échec alors que inclus.tex est dans racine_sources. "
            f"Erreurs : {res.erreurs}"
        )
