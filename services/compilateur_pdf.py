r"""
services/compilateur_pdf.py — Compilation PDF d'un atome isolé.

Prend un fichier .tex généré par services/latex_rendu_atome.py et le
compile via pdflatex dans un dossier temporaire, avec :
  - détection automatique du pdflatex disponible (env var, PATH, MiKTeX portable)
  - timeout pour éviter les boucles infinies
  - cache PDF par hash(tex) pour éviter les recompilations inutiles
  - extraction structurée des erreurs de compilation

API principale :

    compiler_atome(tex_source, racine_sources, cache_dir) -> ResultatCompilation

Aucune dépendance externe (sauf pdflatex bien sûr). Importable par Flask
et par les scripts.
"""

from __future__ import annotations
import contextlib
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


# ── Résultat d'une compilation ────────────────────────────────────────────────

@dataclass
class ErreurLatex:
    """Erreur extraite du log pdflatex."""
    ligne: int | None         # Numéro de ligne dans le .tex, None si indéterminé
    message: str              # Message d'erreur nettoyé
    contexte: str = ''        # Ligne de code qui a déclenché, si disponible


@dataclass
class ResultatCompilation:
    """Retour structuré de compiler_atome()."""
    ok: bool                   # True si PDF produit
    pdf_bytes: bytes = b''     # Contenu du PDF si ok
    pdf_path: Path | None = None  # Chemin du PDF en cache, si servi depuis le cache
    erreurs: list[ErreurLatex] = field(default_factory=list)
    log_complet: str = ''      # Log pdflatex intégral (pour debug)
    duree_ms: int = 0          # Durée de compilation en millisecondes
    depuis_cache: bool = False # True si servi sans recompiler
    pdflatex_utilise: str = '' # Chemin du pdflatex effectivement appelé


# ── Détection de pdflatex ─────────────────────────────────────────────────────

# Variable d'environnement qui peut imposer un chemin explicite
ENV_PDFLATEX = 'SEQENSEIGNE_PDFLATEX'


def detecter_pdflatex(racine_appli: Path | None = None) -> str | None:
    """Cherche un exécutable pdflatex utilisable.

    Ordre de priorité :
      1. Variable d'environnement SEQENSEIGNE_PDFLATEX
      2. MiKTeX portable relatif à la racine de l'appli (voir _chercher_miktex_portable)
      3. `pdflatex` dans le PATH système

    Le MiKTeX portable est prioritaire sur le PATH parce que c'est un choix
    d'installation délibéré : si l'utilisateur a pris la peine de fournir
    MiKTeX à côté de l'appli, c'est qu'il veut que ce soit celui-là qui
    serve — pas un TeX Live système qui traînerait par accident dans le PATH
    et n'a pas forcément les mêmes paquets installés.

    Retourne le chemin absolu du binaire, ou None si rien n'est trouvé.
    """
    # 1. Variable d'environnement (override explicite)
    env_path = os.environ.get(ENV_PDFLATEX)
    if env_path:
        p = Path(env_path)
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)

    # 2. MiKTeX portable dans outils/ (prioritaire sur PATH)
    if racine_appli is not None:
        trouve = _chercher_miktex_portable(racine_appli)
        if trouve:
            return trouve

    # 3. PATH système (TeX Live, MiKTeX installé système, etc.)
    found = shutil.which('pdflatex')
    if found:
        return found

    return None


# Sous-dossiers typiques où on peut trouver un MiKTeX portable installé
# à côté de l'appli. Les deux premiers couvrent MiKTeX ≥ 2.9 (structure
# `texmfs/install/miktex/bin/x64/` imposée par le mode portable).
# Les deux derniers couvrent les installations plus anciennes ou plus simples.
_CHEMINS_MIKTEX_RELATIFS = [
    ('MikTex', 'texmfs', 'install', 'miktex', 'bin', 'x64'),
    ('MiKTeX', 'texmfs', 'install', 'miktex', 'bin', 'x64'),
    ('miktex', 'texmfs', 'install', 'miktex', 'bin', 'x64'),
    ('MiKTeX', 'miktex', 'bin', 'x64'),
    ('MiKTeX', 'miktex', 'bin'),
    ('miktex', 'miktex', 'bin', 'x64'),
]


def _chercher_miktex_portable(racine_appli: Path) -> str | None:
    """Cherche pdflatex.exe dans outils/ selon les conventions MiKTeX portable.

    Stratégie :
      1. Essayer les chemins classiques (liste _CHEMINS_MIKTEX_RELATIFS).
      2. Si rien trouvé, fallback par glob récursif sous outils/ pour
         récupérer n'importe quel pdflatex placé ailleurs.
    """
    outils = racine_appli.parent / 'outils'
    if not outils.is_dir():
        return None

    # 1. Chemins connus (rapide, déterministe)
    noms_exe = ['pdflatex.exe', 'pdflatex']
    for chemin_relatif in _CHEMINS_MIKTEX_RELATIFS:
        base = outils.joinpath(*chemin_relatif)
        for nom in noms_exe:
            candidat = base / nom
            if candidat.is_file():
                return str(candidat)

    # 2. Glob récursif en dernier ressort (couvre une convention exotique
    # qu'on n'aurait pas prévue). Les noms de dossiers peuvent varier :
    # MikTex / MiKTeX / miktex / ... et la profondeur aussi.
    for nom in noms_exe:
        for candidat in outils.rglob(nom):
            if candidat.is_file():
                return str(candidat)

    return None


# ── Cache par hash ────────────────────────────────────────────────────────────

def hash_tex(tex_source: str) -> str:
    """Hash court d'un .tex source, utilisé comme clé de cache."""
    return hashlib.sha256(tex_source.encode('utf-8')).hexdigest()[:16]


def chemin_pdf_cache(cache_dir: Path, hash_source: str) -> Path:
    """Chemin attendu d'un PDF en cache."""
    return cache_dir / f'{hash_source}.pdf'


def chemin_log_cache(cache_dir: Path, hash_source: str) -> Path:
    """Chemin du log associé (conservé pour debug)."""
    return cache_dir / f'{hash_source}.log'


# ── Extraction des erreurs du log pdflatex ────────────────────────────────────

# pdflatex utilise le format :
#   ! LaTeX Error: Something happened.
#   l.42  some context
#
# Ou parfois :
#   ./atome.tex:42: Some message
#
# On extrait les deux formats principaux.

_RE_ERREUR_EXCLAMATION = re.compile(
    r'^!\s*(?P<msg>.+?)$', re.MULTILINE,
)
_RE_LIGNE_LATEX = re.compile(
    r'^l\.(?P<ligne>\d+)\s*(?P<ctx>.*)$', re.MULTILINE,
)
_RE_ERREUR_COLON = re.compile(
    r'^.+?\.tex:(?P<ligne>\d+):\s*(?P<msg>.+?)$', re.MULTILINE,
)


def extraire_erreurs(log: str) -> list[ErreurLatex]:
    """Parse un log pdflatex et retourne les erreurs détectées.

    Gère les deux formats courants :
      - "! LaTeX Error: …" suivi de "l.N  contexte"
      - "fichier.tex:N: message"

    Les warnings ne sont pas remontés (seulement les erreurs fatales).
    """
    erreurs = []

    # Format "! …" : on apparie avec le "l.N" qui suit le plus proche
    positions_exclam = [
        (m.start(), m.group('msg').strip())
        for m in _RE_ERREUR_EXCLAMATION.finditer(log)
    ]
    positions_lignes = [
        (m.start(), int(m.group('ligne')), m.group('ctx').strip())
        for m in _RE_LIGNE_LATEX.finditer(log)
    ]

    for pos_msg, msg in positions_exclam:
        # Trouver le "l.N" le plus proche après cette erreur
        lignes_apres = [p for p in positions_lignes if p[0] > pos_msg]
        if lignes_apres:
            _, ligne, ctx = lignes_apres[0]
            erreurs.append(ErreurLatex(ligne=ligne, message=msg, contexte=ctx))
        else:
            erreurs.append(ErreurLatex(ligne=None, message=msg))

    # Format colon : "fichier.tex:42: message"
    for m in _RE_ERREUR_COLON.finditer(log):
        ligne = int(m.group('ligne'))
        msg = m.group('msg').strip()
        # Éviter les doublons avec le format !
        if not any(e.ligne == ligne for e in erreurs):
            erreurs.append(ErreurLatex(ligne=ligne, message=msg))

    return erreurs


# ── Compilation principale ────────────────────────────────────────────────────

# Durée max d'une compilation en secondes. pdflatex d'un atome simple prend
# 2-5 s sur une machine moderne ; 30 s laisse une marge confortable sans
# bloquer l'UI sur un atome pathologique.
TIMEOUT_DEFAUT = 30


@contextlib.contextmanager
def _ouvrir_workdir(workdir: Path | None):
    """v0.15.2.7 — Context manager qui fournit le dossier de travail pour
    pdflatex.

    - workdir=None : ``tempfile.TemporaryDirectory`` éphémère (comportement
      historique). Détruit en sortie. À utiliser hors UI (tests, scripts) :
      l'invisibilité du log pendant la compile est sans impact.

    - workdir=Path : on utilise CE chemin. Le dossier est nettoyé puis
      recréé en début d'appel pour éviter qu'un run précédent (résidus
      .aux, Corriges/, etc.) ne biaise la compilation actuelle. Il
      PERSISTE après le yield (intentionnel) — c'est ce qui rend
      ``atome.log`` accessible à un lecteur externe pendant la
      compilation. Sera nettoyé/recréé au prochain appel sur le même
      workdir, donc pas d'accumulation entre runs.
    """
    if workdir is None:
        with tempfile.TemporaryDirectory(prefix='seqenseigne_rendu_') as t:
            yield Path(t)
    else:
        if workdir.exists():
            shutil.rmtree(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        yield workdir


def compiler_atome(
    tex_source: str,
    racine_sources: Path | None = None,
    cache_dir: Path | None = None,
    pdflatex: str | None = None,
    racine_appli: Path | None = None,
    timeout: int = TIMEOUT_DEFAUT,
    dossier_images: Path | None = None,
    workdir: Path | None = None,
    on_passe_demarree=None,
) -> ResultatCompilation:
    """Compile un .tex d'atome et retourne le résultat.

    Parameters
    ----------
    tex_source : str
        Contenu complet du .tex à compiler (produit par generer_tex_atome).
    racine_sources : Path, optional
        Dossier racine des sources (pour \\input des _params.tex notamment).
        Ajouté à TEXINPUTS pour que pdflatex trouve les fichiers relatifs.
    cache_dir : Path, optional
        Dossier où stocker les PDF compilés. Si fourni, active le cache :
        un PDF déjà compilé avec le même hash est renvoyé sans recompiler.
    pdflatex : str, optional
        Chemin explicite de l'exécutable pdflatex. Si None, détection auto
        via detecter_pdflatex(racine_appli).
    racine_appli : Path, optional
        Racine de l'appli Flask (utilisée pour chercher MiKTeX portable).
    timeout : int
        Durée max en secondes avant kill de pdflatex.
    dossier_images : Path, optional
        Dossier centralisé d'images (typiquement ``appli/data/images/``).
        Ajouté à TEXINPUTS récursivement pour que les ``\\includegraphics``
        trouvent les images migrées par v0.7. Si None, le comportement
        d'avant v0.7 est conservé (recherche uniquement via racine_sources).
    workdir : Path, optional
        v0.15.2.7 — Dossier de travail explicite pour pdflatex.

        - Sans (défaut) : ``tempfile.TemporaryDirectory`` éphémère, détruit
          en sortie. Comportement historique. À utiliser hors contexte
          UI (tests, scripts) — invisibilité du log pendant la compile
          est sans impact.
        - Avec : ce chemin sert de cwd à pdflatex. Le ``atome.log`` y
          est écrit progressivement par pdflatex et est donc lisible
          par un observateur externe (compteur de pages UI) pendant
          que la compilation tourne. Le dossier est nettoyé/recréé
          en début d'appel pour éviter toute pollution par un run
          précédent (.aux, Corriges/, etc.).
    on_passe_demarree : callable(int), optional
        v0.15.2.8 — Callback notifié au démarrage de chaque passe
        pdflatex (1 puis 2). Permet à l'appelant (typiquement le worker
        de compilation) de mettre à jour un statut affiché à l'UI pour
        que l'utilisateur voie « passe 1/2 » puis « passe 2/2 » pendant
        la compile. Si la callback lève, l'exception est avalée :
        elle ne doit jamais casser la compilation.

    Returns
    -------
    ResultatCompilation
        Structure avec le PDF (si succès) ou les erreurs (si échec).
    """
    import time

    h = hash_tex(tex_source)

    # ── Cache : si le PDF existe déjà, on le renvoie ─────────────────────────
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = chemin_pdf_cache(cache_dir, h)
        log_path = chemin_log_cache(cache_dir, h)
        if pdf_path.is_file():
            return ResultatCompilation(
                ok=True,
                pdf_bytes=pdf_path.read_bytes(),
                pdf_path=pdf_path,
                log_complet=log_path.read_text(encoding='utf-8', errors='replace')
                             if log_path.is_file() else '',
                duree_ms=0,
                depuis_cache=True,
            )

    # ── Détection de pdflatex ────────────────────────────────────────────────
    if pdflatex is None:
        pdflatex = detecter_pdflatex(racine_appli)
    if pdflatex is None:
        return ResultatCompilation(
            ok=False,
            erreurs=[ErreurLatex(
                ligne=None,
                message=(
                    "pdflatex introuvable. Définir la variable d'environnement "
                    f"{ENV_PDFLATEX}, ou installer MiKTeX/TeX Live dans le PATH, "
                    "ou placer MiKTeX portable dans outils/MiKTeX/."
                ),
            )],
        )

    # ── Compilation dans un dossier de travail ──────────────────────────────
    # v0.15.2.7 : si workdir fourni → cwd explicite et persistant pour
    # exposer atome.log à un lecteur externe (compteur de pages UI).
    # Sinon : tempfile.TemporaryDirectory éphémère, comportement historique.
    t0 = time.monotonic()
    with _ouvrir_workdir(workdir) as tmpdir:
        tex_path = tmpdir / 'atome.tex'
        tex_path.write_text(tex_source, encoding='utf-8')

        # Le paquet seqenseigne utilise tcbverbatimwrite pour écrire les
        # corrigés et annexes dans Corriges/ et Annexes/ pendant la compilation,
        # via \seqCorrige et \seqAnnexe. Ces dossiers doivent exister avant
        # que pdflatex ne les ouvre : tcbverbatimwrite ne les crée pas.
        (tmpdir / 'Corriges').mkdir(exist_ok=True)
        (tmpdir / 'Annexes').mkdir(exist_ok=True)

        # TEXINPUTS : permet à pdflatex de trouver les .sty et les fichiers
        # inclus via \input, y compris depuis la racine des sources.
        # v0.7 : on ajoute aussi le dossier centralisé des images.
        texinputs_parts = []
        if racine_sources is not None and racine_sources.is_dir():
            # Ajout récursif : // signifie "cette arborescence à toutes profondeurs"
            texinputs_parts.append(str(racine_sources) + os.sep + os.sep)
        if dossier_images is not None and dossier_images.is_dir():
            # Le dossier images est plat, mais on garde le // par robustesse
            # au cas où Laurent organise plus tard des sous-dossiers.
            texinputs_parts.append(str(dossier_images) + os.sep + os.sep)
        texinputs_parts.append('')  # conserve le TEXINPUTS par défaut
        env = os.environ.copy()
        env['TEXINPUTS'] = os.pathsep.join(texinputs_parts) + (
            os.pathsep + env.get('TEXINPUTS', '')
        )

        # 2 passes pdflatex. Raison : le paquet seqenseigne écrit les corrigés
        # dans Corriges/cNeM.tex pendant la compilation, puis \seqAfficheCorriges
        # les inclut via CorrList.tex. Au premier passage, CorrList.tex est
        # ouvert en écriture mais n'est refermé qu'à \seqAfficheCorriges — il
        # faut donc un second passage pour que \input{CorrList.tex} en fin de
        # document voit les corrigés. Idem pour les annexes et les références
        # croisées (\pageref des corrigés dans l'en-tête de série).
        def _lancer_pdflatex() -> subprocess.CompletedProcess:
            return subprocess.run(
                [
                    pdflatex,
                    '-interaction=nonstopmode',
                    '-halt-on-error',
                    'atome.tex',
                ],
                cwd=tmpdir,
                env=env,
                capture_output=True,
                timeout=timeout,
                check=False,
            )

        try:
            if on_passe_demarree is not None:
                try:
                    on_passe_demarree(1)
                except Exception:
                    # Callback ne doit jamais casser la compile
                    pass
            proc = _lancer_pdflatex()
            # Ne tenter la seconde passe que si la première a produit un PDF.
            if proc.returncode == 0 and (tmpdir / 'atome.pdf').is_file():
                if on_passe_demarree is not None:
                    try:
                        on_passe_demarree(2)
                    except Exception:
                        pass
                proc = _lancer_pdflatex()
        except subprocess.TimeoutExpired:
            duree_ms = int((time.monotonic() - t0) * 1000)
            return ResultatCompilation(
                ok=False,
                erreurs=[ErreurLatex(
                    ligne=None,
                    message=f'Compilation interrompue après {timeout}s (timeout).',
                )],
                duree_ms=duree_ms,
                pdflatex_utilise=pdflatex,
            )
        except FileNotFoundError:
            return ResultatCompilation(
                ok=False,
                erreurs=[ErreurLatex(
                    ligne=None,
                    message=f'Exécutable pdflatex introuvable : {pdflatex}',
                )],
                pdflatex_utilise=pdflatex,
            )

        duree_ms = int((time.monotonic() - t0) * 1000)

        # Lire le log (généralement `.log`, à côté du .tex)
        log_path_src = tmpdir / 'atome.log'
        log_complet = log_path_src.read_text(
            encoding='utf-8', errors='replace',
        ) if log_path_src.is_file() else ''
        # Si pas de log, au pire on prend stdout/stderr
        if not log_complet:
            log_complet = (
                (proc.stdout or b'').decode('utf-8', errors='replace')
                + (proc.stderr or b'').decode('utf-8', errors='replace')
            )

        # PDF produit ?
        pdf_src = tmpdir / 'atome.pdf'
        if pdf_src.is_file():
            pdf_bytes = pdf_src.read_bytes()

            # Mise en cache si demandé
            pdf_final = None
            if cache_dir is not None:
                cache_dir.mkdir(parents=True, exist_ok=True)
                pdf_final = chemin_pdf_cache(cache_dir, h)
                pdf_final.write_bytes(pdf_bytes)
                chemin_log_cache(cache_dir, h).write_text(
                    log_complet, encoding='utf-8',
                )

            return ResultatCompilation(
                ok=True,
                pdf_bytes=pdf_bytes,
                pdf_path=pdf_final,
                log_complet=log_complet,
                duree_ms=duree_ms,
                depuis_cache=False,
                pdflatex_utilise=pdflatex,
            )

        # Échec : extraire les erreurs
        erreurs = extraire_erreurs(log_complet)
        if not erreurs:
            # pdflatex a planté sans produire de log structuré
            erreurs.append(ErreurLatex(
                ligne=None,
                message=f'Compilation échouée (code retour {proc.returncode}) '
                        f'sans message d\'erreur identifiable.',
            ))
        return ResultatCompilation(
            ok=False,
            erreurs=erreurs,
            log_complet=log_complet,
            duree_ms=duree_ms,
            depuis_cache=False,
            pdflatex_utilise=pdflatex,
        )
