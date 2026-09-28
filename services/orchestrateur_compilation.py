"""services/orchestrateur_compilation.py — v0.13.6.5.1.1

Couche d'orchestration entre les routes/services métier et le compilateur
LaTeX bas niveau (`services.compilateur_pdf`).

But
---

Avant cette couche, chaque type de cible compilable (atome individuel,
livret de séquence, récap cours/exos, évaluation, …) avait son propre
code de compilation, dupliqué ~70 lignes à chaque fois dans une route
Flask. Cette duplication rendait coûteuse l'ajout de nouvelles cibles
et l'ajout de fonctionnalités transverses (logs, .tex brut, métriques).

Cette couche introduit :
  - un **registre** de producteurs `.tex` (un par type de cible)
  - une **façade** `compiler(...)` qui orchestre : génération .tex,
    compilation, persistance log/.tex sur disque, et retour d'un
    `ResultatCompilation` enrichi
  - le stockage **sur disque** des logs et .tex compilés, pour que l'UI
    puisse les afficher après-coup (panneau d'erreurs)

Périmètre v0.13.6.5.1.1
-----------------------

Cette session enregistre les producteurs **uniquement pour les
documents publiables du référentiel** (types `livret_sequence`,
`livret_cours`, `livret_exercices`, `livret_plans`, `evaluation`).

Le service `referentiel_documents_compilation.py` est migré pour
utiliser cette couche. Les routes atomes/recap/eval existantes
(rendu_atome.py, recap_cours.py, etc.) ne sont **pas migrées** cette
session — elles continuent d'appeler directement `compiler_atome`.
Migration progressive dans les sessions ultérieures.

Stockage des artefacts
----------------------

Pour chaque compilation d'une cible, on stocke :
  - le .tex source       → `<dossier_artefacts>/<cible_key>.tex`
  - le log complet       → `<dossier_artefacts>/<cible_key>.log`
  - le PDF (si OK)       → `<dossier_artefacts>/<cible_key>.pdf`

Où `<cible_key>` est un identifiant déterministe et sûr pour le
filesystem (slug de l'identifiant fonctionnel de la cible).

Le caller fournit le dossier où poser ces artefacts (typiquement
`data/referentiels/<ref_id>/` pour les documents publiables).
"""
from __future__ import annotations

import re
import sqlite3
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from services.compilateur_pdf import (
    compiler_atome, ErreurLatex, ResultatCompilation,
    detecter_pdflatex,
)


# ── Interface producteur .tex ───────────────────────────────────────────────


class ProducteurTex(Protocol):
    """Interface d'un producteur de .tex.

    Chaque type de cible compilable (atome, livret_sequence, evaluation…)
    implémente cette interface et s'enregistre dans le REGISTRE via
    `enregistrer_producteur`.

    Le producteur reçoit la cible (dict opaque, contenu spécifique au type)
    et les options de compilation, et renvoie le source LaTeX prêt à
    compiler. Il peut lever `ProducteurErreur` si la génération échoue
    (atome introuvable, données incohérentes, etc.).
    """
    def __call__(self, conn: sqlite3.Connection, cible: dict,
                 options: dict, tikz_libraries: list[str],
                 tblr_libraries: list[str]) -> str: ...


REGISTRE: dict[str, ProducteurTex] = {}


def enregistrer_producteur(type_cible: str
                            ) -> Callable[[ProducteurTex], ProducteurTex]:
    """Décorateur d'enregistrement d'un producteur dans le registre.

    Usage :
        @enregistrer_producteur('livret_cours')
        def _produire_livret_cours(conn, cible, options, tikz, tblr):
            from services.livret_recap_cours import generer_recap_cours
            return generer_recap_cours(conn, cible['niveau'],
                                       tikz_libraries=tikz,
                                       tblr_libraries=tblr)
    """
    def deco(fn: ProducteurTex) -> ProducteurTex:
        if type_cible in REGISTRE:
            # En cas de double enregistrement (ex: rechargement à chaud),
            # on remplace silencieusement. Inoffensif.
            pass
        REGISTRE[type_cible] = fn
        return fn
    return deco


class ProducteurErreur(Exception):
    """Erreur métier dans la génération du .tex (avant compilation)."""
    def __init__(self, message: str, code: str = 'producteur_erreur',
                 details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


# ── Résultat enrichi ────────────────────────────────────────────────────────


@dataclass
class ResultatOrchestration:
    """Résultat d'une orchestration de compilation pour une cible.

    Enrichit `ResultatCompilation` du compilateur bas niveau avec :
      - le .tex source effectivement compilé
      - le type d'échec global (latex / infrastructure / producteur / aucun)
      - les chemins des artefacts persistés
    """
    ok: bool
    pdf_bytes: bytes = b''
    log_complet: str = ''
    tex_source: str = ''
    erreurs: list[ErreurLatex] = field(default_factory=list)
    duree_ms: int = 0
    type_echec: str | None = None  # 'producteur' | 'latex' | 'infrastructure'
    depuis_cache: bool = False
    # Chemins des artefacts persistés (None si non persistés)
    chemin_pdf: Path | None = None
    chemin_log: Path | None = None
    chemin_tex: Path | None = None


# ── Façade : compiler() ─────────────────────────────────────────────────────


def compiler(conn: sqlite3.Connection,
             type_cible: str,
             cible: dict,
             options: dict,
             *,
             dossier_artefacts: Path | None = None,
             cible_key: str | None = None,
             racine_sources: Path | None = None,
             dossier_images: Path | None = None,
             racine_appli: Path | None = None,
             pdflatex: str | None = None,
             timeout: int = 300,
             tikz_libraries: list[str] | None = None,
             tblr_libraries: list[str] | None = None,
             on_passe_demarree=None,
             ) -> ResultatOrchestration:
    """Compile une cible via la couche orchestration.

    1. Cherche le producteur dans REGISTRE
    2. Produit le .tex (peut lever ProducteurErreur → ko 'producteur')
    3. Compile via compilateur_pdf.compiler_atome
    4. Persiste les artefacts (.tex, .log, .pdf) dans dossier_artefacts
       sous le nom cible_key, si fournis
    5. Détermine le type_echec global et renvoie

    Paramètres :
      conn             : connexion BDD ouverte (pour le producteur)
      type_cible       : clé d'entrée dans REGISTRE
      cible            : dict opaque, contenu spécifique au type
                         (ex: {niveau:N10, sequence:S01} pour livret_sequence)
      options          : dict d'options de compilation (passé au producteur)
      dossier_artefacts: où persister .tex/.log/.pdf (None = pas de persistance)
      cible_key        : nom de fichier (sans extension) pour les artefacts ;
                         doit être un slug filesystem-safe. Si None, on dérive
                         de cible_id ou on génère un timestamp.
      racine_sources   : passé tel quel à compiler_atome
      dossier_images   : idem
      racine_appli     : idem
      pdflatex         : chemin pdflatex (détecté si None)
      timeout          : en secondes
      tikz_libraries   : libraries TikZ pour le producteur
      tblr_libraries   : libraries tblr pour le producteur

    Retourne un `ResultatOrchestration` (jamais d'exception en cas
    d'échec — le type_echec est positionné).
    """
    t_debut = time.monotonic()

    # 1. Cherche le producteur
    producteur = REGISTRE.get(type_cible)
    if producteur is None:
        return ResultatOrchestration(
            ok=False,
            type_echec='producteur',
            erreurs=[ErreurLatex(
                ligne=None,
                message=f"Type de cible inconnu : {type_cible!r}",
            )],
            duree_ms=int((time.monotonic() - t_debut) * 1000),
        )

    # 2. Producteur du .tex
    try:
        tex_source = producteur(
            conn, cible, options,
            tikz_libraries or [], tblr_libraries or [],
        )
    except ProducteurErreur as e:
        return ResultatOrchestration(
            ok=False,
            type_echec='producteur',
            erreurs=[ErreurLatex(
                ligne=None,
                message=f"{e.code}: {e}",
            )],
            duree_ms=int((time.monotonic() - t_debut) * 1000),
        )
    except Exception as e:
        return ResultatOrchestration(
            ok=False,
            type_echec='producteur',
            erreurs=[ErreurLatex(
                ligne=None,
                message=f"Exception du producteur {type_cible!r} : {e}",
            )],
            duree_ms=int((time.monotonic() - t_debut) * 1000),
        )

    # 3. Compilation bas niveau
    if pdflatex is None:
        pdflatex = detecter_pdflatex(racine_appli)

    # v0.15.2.7 — Workdir explicite quand on est en mode "orchestré
    # avec artefacts" (cas UI/compilation persistée). Permet à
    # lire_statut() de tailer le LIVE log et donc d'afficher la page
    # courante en temps réel. Sans dossier_artefacts/cible_key (cas
    # rare : tests, scripts), workdir=None → tempfile éphémère comme
    # avant (le compteur de pages n'aurait pas d'usage de toute façon).
    workdir = None
    if dossier_artefacts is not None and cible_key:
        workdir = chemin_workdir_cible(dossier_artefacts, cible_key)

    try:
        res: ResultatCompilation = compiler_atome(
            tex_source=tex_source,
            racine_sources=racine_sources,
            cache_dir=None,  # pas de cache au niveau orchestrateur
            pdflatex=pdflatex,
            racine_appli=racine_appli,
            timeout=timeout,
            dossier_images=dossier_images,
            workdir=workdir,
            on_passe_demarree=on_passe_demarree,
        )
    except Exception as e:
        # Exception inattendue du compilateur — on remonte en
        # infrastructure pour ne pas perdre l'info.
        return ResultatOrchestration(
            ok=False,
            tex_source=tex_source,
            type_echec='infrastructure',
            erreurs=[ErreurLatex(
                ligne=None,
                message=f"Exception du compilateur : {e}",
            )],
            duree_ms=int((time.monotonic() - t_debut) * 1000),
        )

    # 4. Type d'échec
    type_echec = None
    if not res.ok:
        # Heuristique : si "pdflatex introuvable" ou "timeout" → infra
        msg = (res.erreurs[0].message if res.erreurs else '').lower()
        if 'pdflatex introuvable' in msg or 'timeout' in msg:
            type_echec = 'infrastructure'
        else:
            type_echec = 'latex'

    # 5. Persistance des artefacts
    chemin_tex = chemin_log = chemin_pdf = None
    if dossier_artefacts is not None and cible_key:
        dossier_artefacts.mkdir(parents=True, exist_ok=True)
        try:
            chemin_tex = dossier_artefacts / f"{cible_key}.tex"
            chemin_tex.write_text(tex_source, encoding='utf-8')
        except Exception:
            chemin_tex = None
        try:
            chemin_log = dossier_artefacts / f"{cible_key}.log"
            chemin_log.write_text(res.log_complet or '', encoding='utf-8',
                                  errors='replace')
        except Exception:
            chemin_log = None
        if res.ok and res.pdf_bytes:
            try:
                chemin_pdf = dossier_artefacts / f"{cible_key}.pdf"
                chemin_pdf.write_bytes(res.pdf_bytes)
            except Exception:
                chemin_pdf = None

    return ResultatOrchestration(
        ok=res.ok,
        pdf_bytes=res.pdf_bytes,
        log_complet=res.log_complet,
        tex_source=tex_source,
        erreurs=list(res.erreurs),
        duree_ms=res.duree_ms,
        type_echec=type_echec,
        depuis_cache=res.depuis_cache,
        chemin_pdf=chemin_pdf,
        chemin_log=chemin_log,
        chemin_tex=chemin_tex,
    )


# ── Helper : slug filesystem-safe ───────────────────────────────────────────


_SLUG_INVALIDE = re.compile(r'[^a-zA-Z0-9_-]+')


def slug_cible(s: str) -> str:
    """Convertit une string arbitraire en identifiant filesystem-safe.

    Remplace tout caractère hors `[a-zA-Z0-9_-]` par `_`. Idempotent.

    Exemples :
      'N10/S01'    → 'N10_S01'
      'eval_abc12' → 'eval_abc12'
      'C03 → C04'  → 'C03_C04'
    """
    s = str(s).strip()
    return _SLUG_INVALIDE.sub('_', s) or '_'


# ── Workdir live pour pdflatex (v0.15.2.7) ──────────────────────────────────


def chemin_workdir_cible(dossier_artefacts: Path, cible_key: str) -> Path:
    """v0.15.2.7 — Dossier de travail pdflatex (persistant) pour une cible.

    Ce dossier sert de cwd à pdflatex pendant la compilation : c'est
    là qu'``atome.log`` est écrit progressivement, donc lisible en
    direct par le compteur de pages UI.

    Placement sous ``tempfile.gettempdir()`` (typiquement ``/tmp`` ou
    ``C:\\Users\\...\\Temp``) et **non** sous ``dossier_artefacts`` :
    on profite d'un disque rapide même quand l'app tourne depuis un
    USB (cas Laurent — `dossier_artefacts` est alors sur clé USB,
    50-100× plus lent qu'un SSD interne).

    Discrimination par ``dossier_artefacts.name`` (= ``doc_id``)
    et ``cible_key`` : pas de collision entre documents ni entre
    cibles d'un même document.

    Le dossier est nettoyé/recréé au début de chaque ``compiler_atome``
    (cf. ``_ouvrir_workdir`` côté compilateur). Pas d'accumulation
    inter-runs.
    """
    return (Path(tempfile.gettempdir())
            / 'seqenseigne_workdir'
            / dossier_artefacts.name
            / cible_key)


def chemin_log_courant_cible(dossier_artefacts: Path, cible_key: str) -> Path:
    """v0.15.2.7 — Chemin du ``atome.log`` LIVE pour une cible en cours.

    C'est le log que pdflatex écrit progressivement. À NE PAS confondre
    avec ``chemin_artefact(..., 'log')`` côté compilation (defaultdict
    de ``services.referentiel_documents_compilation``) qui pointe sur
    le log final, écrit APRÈS la fin de la compilation par
    l'orchestrateur.

    C'est ce chemin que ``lire_statut`` doit lire pour enrichir le
    statut avec ``page_courante`` en temps réel.
    """
    return chemin_workdir_cible(dossier_artefacts, cible_key) / 'atome.log'


# ── Enregistrement des producteurs documents publiables ─────────────────────
#
# Ces enregistrements doivent être effectués au chargement du module
# (idempotent par construction : le décorateur écrase). On les place ici
# pour garantir qu'ils sont disponibles dès l'import de l'orchestrateur,
# sans avoir à importer manuellement les services métier.


@enregistrer_producteur('livret_sequence')
def _produire_livret_sequence(conn, cible, options, tikz, tblr):
    """Producteur du livret de séquence.

    Cible attendue : {'niveau': 'N10', 'sequence': 'S01'} (au minimum).
    Options : dict format plat du catalogue (cf. service livret_sequence
    qui sait convertir).
    """
    from services.livret_sequence import generer_livret_sequence
    niveau = cible.get('niveau')
    sequence = cible.get('sequence')
    if not niveau or not sequence:
        raise ProducteurErreur(
            f"livret_sequence requiert niveau et sequence : reçu {cible!r}",
            code='cible_invalide',
        )
    return generer_livret_sequence(
        conn, niveau, sequence,
        options=options,
        tikz_libraries=tikz,
        tblr_libraries=tblr,
    )


@enregistrer_producteur('livret_cours')
def _produire_livret_cours(conn, cible, options, tikz, tblr):
    """Producteur du livret de cours (récap au niveau)."""
    from services.livret_recap_cours import generer_recap_cours
    niveau = cible.get('niveau')
    if not niveau:
        raise ProducteurErreur(
            f"livret_cours requiert niveau : reçu {cible!r}",
            code='cible_invalide',
        )
    return generer_recap_cours(
        conn, niveau,
        tikz_libraries=tikz,
        tblr_libraries=tblr,
    )


@enregistrer_producteur('livret_exercices')
def _produire_livret_exercices(conn, cible, options, tikz, tblr):
    """Producteur du livret d'exercices (récap au niveau)."""
    from services.livret_recap_exos import generer_recap_exos
    niveau = cible.get('niveau')
    if not niveau:
        raise ProducteurErreur(
            f"livret_exercices requiert niveau : reçu {cible!r}",
            code='cible_invalide',
        )
    return generer_recap_exos(
        conn, niveau,
        tikz_libraries=tikz,
        tblr_libraries=tblr,
    )


@enregistrer_producteur('livret_plans')
def _produire_livret_plans(conn, cible, options, tikz, tblr):
    """Producteur du livret de plans de travail."""
    from services.livret_plans_de_travail import (
        generer_livret_plans_de_travail
    )
    niveau = cible.get('niveau')
    if not niveau:
        raise ProducteurErreur(
            f"livret_plans requiert niveau : reçu {cible!r}",
            code='cible_invalide',
        )
    return generer_livret_plans_de_travail(
        conn, niveau,
        tikz_libraries=tikz,
        tblr_libraries=tblr,
    )


@enregistrer_producteur('evaluation')
def _produire_evaluation(conn, cible, options, tikz, tblr):
    """Producteur d'une évaluation."""
    from services.render_evaluation import generer_tex_evaluation
    eval_id = cible.get('eval_id')
    if not eval_id:
        raise ProducteurErreur(
            f"evaluation requiert eval_id : reçu {cible!r}",
            code='cible_invalide',
        )
    return generer_tex_evaluation(
        conn, eval_id,
        tikz_libraries=tikz,
        tblr_libraries=tblr,
    )


# ── v0.13.6.5.2 — Producteurs des 4 types précédemment "à venir" ────────────


@enregistrer_producteur('livret_fiches')
def _produire_livret_fiches(conn, cible, options, tikz, tblr):
    """Producteur du livret de fiches de résumé."""
    from services.livret_fiches import generer_livret_fiches
    niveau = cible.get('niveau')
    if not niveau:
        raise ProducteurErreur(
            f"livret_fiches requiert niveau : reçu {cible!r}",
            code='cible_invalide',
        )
    return generer_livret_fiches(
        conn, niveau,
        options=options,
        tikz_libraries=tikz,
        tblr_libraries=tblr,
    )


@enregistrer_producteur('livret_corriges')
def _produire_livret_corriges(conn, cible, options, tikz, tblr):
    """Producteur du livret de corrigés d'exercices."""
    from services.livret_corriges import generer_livret_corriges
    niveau = cible.get('niveau')
    if not niveau:
        raise ProducteurErreur(
            f"livret_corriges requiert niveau : reçu {cible!r}",
            code='cible_invalide',
        )
    return generer_livret_corriges(
        conn, niveau,
        options=options,
        tikz_libraries=tikz,
        tblr_libraries=tblr,
    )


@enregistrer_producteur('livret_cartes_recap')
def _produire_livret_cartes_recap(conn, cible, options, tikz, tblr):
    """Producteur du récap cartes (enseignant)."""
    from services.livret_cartes_recap import generer_livret_cartes_recap
    niveau = cible.get('niveau')
    if not niveau:
        raise ProducteurErreur(
            f"livret_cartes_recap requiert niveau : reçu {cible!r}",
            code='cible_invalide',
        )
    return generer_livret_cartes_recap(
        conn, niveau,
        options=options,
        tikz_libraries=tikz,
        tblr_libraries=tblr,
    )


@enregistrer_producteur('livret_cartes_planches')
def _produire_livret_cartes_planches(conn, cible, options, tikz, tblr):
    """Producteur des planches cartes (élèves).

    v0.15.2.4 : cible.get('sequence') optionnel. Si présent, ne produit
    que les planches de cette séquence (découpage par séquence). Absent
    (cible 'unique') → toutes les planches du niveau.
    """
    from services.livret_cartes_planches import generer_livret_cartes_planches
    niveau = cible.get('niveau')
    if not niveau:
        raise ProducteurErreur(
            f"livret_cartes_planches requiert niveau : reçu {cible!r}",
            code='cible_invalide',
        )
    return generer_livret_cartes_planches(
        conn, niveau,
        options=options,
        sequence=cible.get('sequence'),
        tikz_libraries=tikz,
        tblr_libraries=tblr,
    )


# Note v0.13.6.5.2 : `_TYPES_A_VENIR` était une liste de types
# précédemment stubbed (livret_fiches, livret_corriges, livret_cartes_recap,
# livret_cartes_planches). Tous sont désormais implémentés par les
# producteurs ci-dessus. La constante et le bloc d'enregistrement
# automatique ont été retirés.
