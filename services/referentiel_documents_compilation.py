"""services/referentiel_documents_compilation.py — v0.13.6.5.1

Compilation des documents publiables d'un référentiel.

Pipeline
--------

Un document publiable du catalogue (cf. services/referentiel_documents.py)
peut être :
  - **Unitaire** (un seul PDF) : livret_cours, livret_exercices,
    livret_fiches, livret_plans, livret_corriges, livret_cartes_recap,
    livret_cartes_planches
  - **Multi-cible** (N PDFs) :
    - `livret_sequence` : 14 PDFs (un par séquence du niveau)
    - `evaluation` : N PDFs (un par évaluation déclarée pour le niveau)

Pour chaque cible :
  1. Le service de génération métier produit un .tex
     (ex: services.livret_sequence.generer_livret_sequence)
  2. compilateur_pdf.compiler_atome compile en PDF
  3. Le PDF est écrit dans data/referentiels/<ref_id>/<nom>.pdf
  4. Le log pdflatex (tronqué) est conservé

À la fin :
  - compile_ok = 1 si toutes les cibles ont compilé OK, 0 sinon
  - compile_date = maintenant
  - compile_log = log textuel tronqué (~5000 char)
  - compile_en_cours = 0

Statut de progression
---------------------

Un dict global `_STATUTS_COMPILATION` indexé par doc_id permet à l'UI
de poller `/api/.../compiler/statut` pour récupérer l'avancement
(cible courante, nb cibles faites, nb total).

Compilation asynchrone (thread)
-------------------------------

`compiler_document_async(store, doc_id)` lance la compilation dans un
thread daemon et retourne immédiatement. L'UI poll ensuite.

État effectif d'un document
---------------------------

`etat_effectif_document(doc, conn) → str` parmi :
  - 'non_compile' : compile_date est NULL
  - 'en_cours'    : compile_en_cours = 1
  - 'ko'          : compile_ok = 0
  - 'perime'      : compile_ok = 1 mais des atomes ont été modifiés depuis
  - 'ok'          : compile_ok = 1 et aucun atome modifié depuis

Pour v0.13.6.5.1, le calcul de péremption est **large** : on compare
compile_date avec le max des mtime de tous les atomes du niveau. Une
finesse atome→documents sera ajoutée plus tard.

Types non implémentés
---------------------

Les 4 services métier suivants n'existent pas encore et seront créés
en v0.13.6.5.2 :
  - livret_fiches
  - livret_corriges
  - livret_cartes_recap
  - livret_cartes_planches

Une tentative de compilation sur ces types renvoie une erreur claire
('type_non_implemente') et pose compile_ok=0 avec un log explicite.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from services.compilateur_pdf import compiler_atome, detecter_pdflatex

logger = logging.getLogger(__name__)


# ── Statut de progression en mémoire ────────────────────────────────────────
#
# Clé : doc_id. Valeur : dict {en_cours, total, fait, etape_courante,
# erreur_globale (str|None)}.
#
# Le statut est créé à l'entrée de compiler_document_async, mis à jour à
# chaque cible compilée, et finalisé à la sortie. L'UI poll ce dict via
# l'API.

_STATUTS_COMPILATION: dict[str, dict[str, Any]] = {}
_LOCK_STATUTS = threading.Lock()


_TOTAL_PASSES_PDFLATEX = 2  # cf. _lancer_pdflatex appelé 2 fois (compilateur_pdf.py)


def _statut_initial(doc_id: str, total: int, type_document: str) -> dict:
    return {
        'doc_id':           doc_id,
        'type_document':    type_document,
        'en_cours':         True,
        'total':            total,
        'fait':             0,
        'etape_courante':   f"Préparation de {type_document}",
        'erreur_globale':   None,
        # v0.15.2.6 + v0.15.2.7 — compteur de pages pdflatex.
        # `chemin_log_courant` pointe sur le LIVE log dans le workdir
        # pdflatex (cf. orch.chemin_log_courant_cible), pas sur
        # l'artefact final qui n'est écrit qu'APRÈS la compilation.
        'cible_en_cours_key':  None,
        'chemin_log_courant':  None,
        'page_courante':       None,
        # v0.15.2.8 — numéro de passe pdflatex en cours (1 ou 2) +
        # nombre total de passes (constant, exposé pour affichage UI
        # `passe N/2`).
        'passe_courante':      None,
        'passes_total':        _TOTAL_PASSES_PDFLATEX,
    }


def _maj_statut(doc_id: str, **kwargs) -> None:
    """Met à jour le statut courant d'une compilation."""
    with _LOCK_STATUTS:
        s = _STATUTS_COMPILATION.get(doc_id)
        if s is None:
            return
        s.update(kwargs)


def lire_statut(doc_id: str) -> dict | None:
    """API de lecture du statut courant. Renvoie None si aucune compilation
    en cours ou tracée pour ce doc.

    v0.15.2.6 — Enrichit avec `page_courante` lu depuis le `.log` pdflatex
    pour donner à l'UI un signal de vie quasi-temps-réel (polling 700ms).

    v0.15.2.7 — Bugfix : on lit le LIVE log dans le workdir
    (`chemin_log_courant`) et plus l'artefact final qui n'est écrit
    qu'APRÈS la compilation. Sans ce correctif, on parsait toujours le
    log de la compilation PRÉCÉDENTE de la même cible (d'où l'affichage
    figé sur « la page totale » du précédent compile, ou rien si c'était
    le premier compile).
    """
    with _LOCK_STATUTS:
        s = _STATUTS_COMPILATION.get(doc_id)
        if s is None:
            return None
        s = dict(s)  # copie défensive avant de relâcher le lock

    # Enrichissement hors lock : I/O sur le fichier .log live.
    if s.get('en_cours') and s.get('chemin_log_courant'):
        from services.log_pdflatex_parser import progression_courante
        prog = progression_courante(Path(s['chemin_log_courant']))
        if prog and 'page_courante' in prog:
            s['page_courante'] = prog['page_courante']
    return s


def _finaliser_statut(doc_id: str, erreur: str | None = None) -> None:
    """Marque la compilation comme terminée mais garde l'état accessible
    quelques secondes pour que l'UI puisse récupérer le résultat final
    avant d'arrêter le polling.

    On n'efface pas tout de suite : l'UI a besoin de voir un dernier
    `en_cours=false` pour stopper son polling. On compte sur l'écriture
    en BDD (compile_ok, compile_date) pour la persistance — le statut
    en mémoire est purement transitoire.
    """
    with _LOCK_STATUTS:
        s = _STATUTS_COMPILATION.get(doc_id)
        if s is None:
            return
        s['en_cours'] = False
        if erreur:
            s['erreur_globale'] = erreur


# ── Cibles d'un document : pour les types multi-cible ───────────────────────


def lister_cibles_document(conn: sqlite3.Connection, doc_id: str,
                           ref_id: str, type_document: str
                           ) -> list[dict]:
    """Liste les cibles à compiler pour ce document.

    Retourne une liste de dicts avec au moins :
      - 'cible_id'  : identifiant unique de la cible (ex: 'N10/S01' ou eval_id)
      - 'libelle'   : texte court pour l'UI
      - 'nom_fichier' : nom du PDF dans le dossier référentiel
                        (ex: 'livret_sequence__N10__S01.pdf')

    Pour les types unitaires, renvoie une liste à 1 élément avec cible_id
    = 'unique' et nom_fichier = '<type>.pdf'.
    """
    niveau = _niveau_du_referentiel(conn, ref_id)

    if type_document == 'livret_sequence':
        # 14 séquences du niveau (codes S01..S14 réellement présents)
        rows = conn.execute("""
            SELECT DISTINCT sequence_code FROM sequences_par_niveau
             WHERE niveau = ?
             ORDER BY sequence_code
        """, (niveau,)).fetchall()
        cibles = []
        for r in rows:
            seq = r['sequence_code']
            cibles.append({
                'cible_id':    f"{niveau}/{seq}",
                'libelle':     f"Livret {niveau}/{seq}",
                'nom_fichier': f"livret_sequence__{niveau}__{seq}.pdf",
                'niveau':      niveau,
                'sequence':    seq,
            })
        return cibles

    if type_document == 'livret_fiches':
        # v0.48.1 — Découpage : un livret annuel (cible 'unique'), un livret
        # par séquence ayant des fiches (cible 'N11/S05'), ou les deux.
        import json as _json
        r = conn.execute("SELECT options FROM referentiel_documents WHERE id = ?",
                         (doc_id,)).fetchone()
        try:
            opts = _json.loads(r['options']) if r and r['options'] else {}
        except (TypeError, ValueError):
            opts = {}
        decoupage = opts.get('decoupage_fiches') or 'annuel'
        cibles = []
        if decoupage in ('annuel', 'les_deux'):
            cibles.append({'cible_id': 'unique', 'libelle': 'Livret Fiches',
                           'nom_fichier': 'livret_fiches.pdf', 'niveau': niveau})
        if decoupage in ('par_sequence', 'les_deux'):
            for row in conn.execute("""
                SELECT DISTINCT sequence FROM fiches_resume
                 WHERE niveau = ? ORDER BY sequence
            """, (niveau,)).fetchall():
                seq = row['sequence']
                cibles.append({
                    'cible_id':    f"{niveau}/{seq}",
                    'libelle':     f"Fiches {niveau}/{seq}",
                    'nom_fichier': f"livret_fiches__{niveau}__{seq}.pdf",
                    'niveau':      niveau,
                    'sequence':    seq,
                })
        return cibles

    if type_document == 'livret_cartes_planches':
        # v0.15.2.5 — uniquement des cibles par séquence.
        #
        # Historique :
        # - v0.15.2.3 : 1 unique cible (toutes planches) — 5min40 sur N10,
        #   dépassait le timeout (300s) et échouait.
        # - v0.15.2.4 : ajout d'une cible 'unique' + 14 cibles par séquence.
        #   Test terrain : la cible 'unique' s'exécutait en premier, bloquait
        #   la barre de progression à 0/15 pendant >5min, puis échouait.
        #   Les cibles par séquence (~25-30s chacune) fonctionnent.
        # - v0.15.2.5 : suppression de la cible 'unique'. Le générateur garde
        #   son support de `sequence=None` (utilisable via script si besoin),
        #   mais l'orchestrateur n'expose plus que les cibles par séquence.
        rows = conn.execute("""
            SELECT DISTINCT sequence FROM cartes_automatisme
             WHERE niveau = ? AND etat_code = 'valide'
             ORDER BY sequence
        """, (niveau,)).fetchall()
        cibles = []
        for r in rows:
            seq = r['sequence']
            cibles.append({
                'cible_id':    f"{niveau}/{seq}",
                'libelle':     f"Planches {niveau}/{seq}",
                'nom_fichier': f"livret_cartes_planches__{niveau}__{seq}.pdf",
                'niveau':      niveau,
                'sequence':    seq,
            })
        return cibles

    if type_document == 'evaluation':
        # Toutes les évaluations du niveau
        rows = conn.execute("""
            SELECT id, numero, titre FROM evaluations
             WHERE niveau = ?
             ORDER BY ordre, numero, id
        """, (niveau,)).fetchall()
        cibles = []
        for r in rows:
            cibles.append({
                'cible_id':    r['id'],
                'libelle':     f"Éval {r['numero']:02d} : {r['titre'] or '(sans titre)'}",
                'nom_fichier': f"evaluation__{r['id']}.pdf",
                'niveau':      niveau,
                'eval_id':     r['id'],
            })
        return cibles

    # Types unitaires
    return [{
        'cible_id':    'unique',
        'libelle':     type_document.replace('_', ' ').title(),
        'nom_fichier': f"{type_document}.pdf",
        'niveau':      niveau,
    }]


def _niveau_du_referentiel(conn: sqlite3.Connection, ref_id: str) -> str:
    row = conn.execute(
        "SELECT niveau FROM referentiel_niveaux WHERE id = ?",
        (ref_id,),
    ).fetchone()
    if row is None:
        raise CompilationErreur(
            f"Référentiel introuvable : {ref_id}",
            code='referentiel_introuvable',
        )
    return row['niveau']


# ── Erreurs métier ──────────────────────────────────────────────────────────


class CompilationErreur(Exception):
    def __init__(self, message: str, code: str = 'compilation_erreur',
                 details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


# ── Producteur .tex selon type_document (DÉPRÉCIÉ v0.13.6.5.1.1) ────────────
#
# Cette fonction est conservée pour compatibilité avec les tests
# existants, mais elle délègue désormais à l'orchestrateur centralisé
# (services/orchestrateur_compilation.py). Les producteurs spécifiques
# y sont enregistrés via le décorateur @enregistrer_producteur.


def _generer_tex(conn: sqlite3.Connection, type_document: str,
                 options: dict, cible: dict,
                 tikz_libraries: list[str],
                 tblr_libraries: list[str]) -> str:
    """[DÉPRÉCIÉ v0.13.6.5.1.1] Aiguille vers le producteur enregistré
    dans l'orchestrateur de compilation.

    Conservé tel quel pour la rétrocompatibilité avec les tests
    v0.13.6.5.1 qui appellent directement cette fonction. La logique
    réelle de production est désormais dans
    services.orchestrateur_compilation.

    Lève CompilationErreur si le type n'est pas implémenté (mapping
    direct depuis ProducteurErreur).
    """
    from services import orchestrateur_compilation as orch

    producteur = orch.REGISTRE.get(type_document)
    if producteur is None:
        raise CompilationErreur(
            f"Type de document inconnu : {type_document}",
            code='type_inconnu',
        )
    try:
        return producteur(
            conn, cible, options,
            tikz_libraries or [], tblr_libraries or [],
        )
    except orch.ProducteurErreur as e:
        # Mapping ProducteurErreur → CompilationErreur (rétrocompat).
        raise CompilationErreur(str(e), code=e.code, details=e.details) from e


# ── Compilation orchestrée ──────────────────────────────────────────────────


def compiler_document(store, doc_id: str,
                      racine_sources: Path | None = None,
                      dossier_images: Path | None = None,
                      racine_appli: Path | None = None,
                      tikz_libraries: list[str] | None = None,
                      tblr_libraries: list[str] | None = None
                      ) -> dict:
    """Compile un document publiable et tous ses sous-fichiers.

    Workflow (v0.13.6.5.1.1 — refonte via orchestrateur) :
      1. Lit le document, vérifie qu'il est `actif=true`, pose
         `compile_en_cours=1` (verrou)
      2. Détermine les cibles (1 ou plusieurs PDFs)
      3. Pour chaque cible :
         - Appelle `orchestrateur_compilation.compiler(...)` qui :
           * génère le .tex via le producteur enregistré
           * compile via compilateur_pdf.compiler_atome
           * persiste sur disque : .tex, .log, .pdf
         - Accumule l'info de cibles dans une structure JSON
      4. Pose `compile_ok`, `compile_date`, `compile_log` (JSON), `compile_en_cours=0`
      5. Met à jour le statut de progression à chaque étape

    Le PDF final est posé sous deux noms :
      - `<dossier_ref>/<nom_fichier>` (nom métier ; cf. lister_cibles)
        — c'est le chemin retourné par chemin_pdf()
      - `<dossier_ref>/_artefacts/<cible_key>.pdf` (nom orchestrateur ;
        cohérent avec .tex/.log dans le même dossier)
    On garde les deux pour ne pas casser l'API GET /pdf existante.

    Cette fonction est **synchrone** — elle bloque jusqu'à la fin de la
    compilation. Utiliser `compiler_document_async` pour un thread.
    """
    from services import orchestrateur_compilation as orch

    # Chargement initial via une connexion dédiée (on aura une autre
    # connexion à chaque étape pour ne pas tenir la BDD verrouillée).
    with store._conn() as conn:
        row = conn.execute("""
            SELECT id, referentiel_id, type_document, options
              FROM referentiel_documents WHERE id = ?
        """, (doc_id,)).fetchone()
        if row is None:
            raise CompilationErreur(
                f"Document introuvable : {doc_id}",
                code='document_introuvable',
            )
        doc_dict = dict(row)
        try:
            options = json.loads(doc_dict['options']) if doc_dict['options'] else {}
        except (TypeError, json.JSONDecodeError):
            options = {}

        if not options.get('actif', False):
            raise CompilationErreur(
                "Le document doit être actif (`actif=true`) pour être compilé.",
                code='document_inactif',
            )

        ref_id = doc_dict['referentiel_id']
        type_document = doc_dict['type_document']

        # Verrou
        en_cours = conn.execute(
            "SELECT compile_en_cours FROM referentiel_documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        if en_cours and en_cours['compile_en_cours']:
            raise CompilationErreur(
                "Compilation déjà en cours pour ce document.",
                code='compilation_en_cours',
            )
        conn.execute(
            "UPDATE referentiel_documents SET compile_en_cours = 1 WHERE id = ?",
            (doc_id,),
        )
        conn.commit()

        cibles = lister_cibles_document(conn, doc_id, ref_id, type_document)

    # Initialiser le statut
    with _LOCK_STATUTS:
        _STATUTS_COMPILATION[doc_id] = _statut_initial(
            doc_id, len(cibles), type_document
        )

    # Détecter pdflatex une seule fois
    pdflatex = detecter_pdflatex(racine_appli)

    # Dossier de stockage : structure (v0.13.6.5.2.1) :
    #   data/referentiels/<ref_id>/<nom_metier>.pdf
    #   data/referentiels/<ref_id>/_artefacts/<doc_id>/<cible_key>.tex
    #   data/referentiels/<ref_id>/_artefacts/<doc_id>/<cible_key>.log
    #   data/referentiels/<ref_id>/_artefacts/<doc_id>/<cible_key>.pdf
    #
    # v0.13.6.5.2.1 — Bugfix : les types unitaires (livret_fiches,
    # livret_corriges, livret_cartes_recap, livret_cartes_planches,
    # livret_cours, etc.) avaient tous un cible_id='unique' et donc
    # tous leurs artefacts s'écrasaient mutuellement dans
    # _artefacts/unique.{tex,log,pdf}. On isole maintenant par doc_id.
    dossier_ref = _dossier_du_referentiel(store, ref_id)
    dossier_ref.mkdir(parents=True, exist_ok=True)
    dossier_artefacts = dossier_ref / '_artefacts' / doc_id
    dossier_artefacts.mkdir(parents=True, exist_ok=True)

    # Accumulateur structuré du résultat (sera sérialisé en JSON).
    # Format : {'cibles': [{cible_id, libelle, ok, type_echec, duree_ms,
    #                       nb_erreurs, premieres_erreurs, cible_key}, ...]}
    resume_cibles = []
    ok_global = True

    try:
        for i, cible in enumerate(cibles, start=1):
            # cible_key = identifiant filesystem-safe pour les artefacts.
            # Calculé AVANT _maj_statut pour pouvoir le stocker.
            cible_key = orch.slug_cible(cible['cible_id'])

            # v0.15.2.7 — chemin du LIVE log que pdflatex va écrire pendant
            # cette cible (dans le workdir, pas dans l'artefact final).
            # C'est CE chemin que lire_statut() doit lire pour extraire
            # page_courante en temps réel. page_courante=None remet à
            # zéro entre deux cibles (évite l'affichage de la page de la
            # cible précédente sur celle qui démarre).
            chemin_log_courant = orch.chemin_log_courant_cible(
                dossier_artefacts, cible_key
            )
            _maj_statut(doc_id, fait=i - 1,
                        etape_courante=f"Compilation : {cible['libelle']}",
                        cible_en_cours_key=cible_key,
                        chemin_log_courant=str(chemin_log_courant),
                        page_courante=None,
                        passe_courante=None)

            # v0.15.2.8 — callback pour propager le numéro de passe
            # pdflatex au statut. lambda capture doc_id par défaut (sinon
            # cellule fermée sur la variable de boucle, classique piège
            # Python).
            def _maj_passe(num: int, _doc=doc_id):
                _maj_statut(_doc, passe_courante=num, page_courante=None)

            # Compilation orchestrée
            try:
                with store._conn() as conn:
                    res = orch.compiler(
                        conn=conn,
                        type_cible=type_document,
                        cible=cible,
                        options=options,
                        dossier_artefacts=dossier_artefacts,
                        cible_key=cible_key,
                        racine_sources=racine_sources,
                        dossier_images=dossier_images,
                        racine_appli=racine_appli,
                        pdflatex=pdflatex,
                        timeout=300,
                        tikz_libraries=tikz_libraries or [],
                        tblr_libraries=tblr_libraries or [],
                        on_passe_demarree=_maj_passe,
                    )
            except Exception as e:
                # L'orchestrateur ne devrait pas lever (il renvoie un
                # ResultatOrchestration avec ko), mais ceinture+bretelles.
                ok_global = False
                resume_cibles.append({
                    'cible_id':  cible['cible_id'],
                    'libelle':   cible['libelle'],
                    'cible_key': cible_key,
                    'ok':        False,
                    'type_echec': 'orchestration',
                    'duree_ms':  0,
                    'nb_erreurs': 1,
                    'premieres_erreurs': [{
                        'ligne': None,
                        'message': f"Exception inattendue : {e}",
                    }],
                })
                continue

            if not res.ok:
                ok_global = False

            # Si OK, copier le PDF au nom métier (compatibilité API GET /pdf).
            # v0.15.2.2.3 — Bugfix : auparavant une exception ici était
            # avalée silencieusement (ok_global=False mais aucun message),
            # produisant un « toast rouge sans détail » côté UI alors que
            # le PDF existait sur disque. On capture désormais le message
            # pour le remonter dans premieres_erreurs.
            erreur_copie = None
            if res.ok:
                if not res.chemin_pdf:
                    # res.ok mais pas de chemin PDF : l'écriture de
                    # l'artefact a échoué côté orchestrateur. Anomalie à
                    # signaler explicitement.
                    erreur_copie = (
                        "Compilation réussie mais aucun PDF d'artefact "
                        "produit (échec d'écriture côté orchestrateur)."
                    )
                    ok_global = False
                else:
                    try:
                        nom_metier = dossier_ref / cible['nom_fichier']
                        nom_metier.write_bytes(res.chemin_pdf.read_bytes())
                    except Exception as e:
                        erreur_copie = (
                            f"PDF compilé mais copie vers le nom métier "
                            f"« {cible['nom_fichier']} » échouée : "
                            f"{type(e).__name__}: {e}"
                        )
                        ok_global = False
                        logger.warning(
                            "Copie PDF nom métier échouée (doc=%s, cible=%s): %s",
                            doc_id, cible.get('cible_id'), e,
                        )

            # Format compact des erreurs pour stockage en BDD
            premieres_erreurs = [
                {
                    'ligne':    e.ligne,
                    'message':  (e.message or '')[:500],
                    'contexte': (e.contexte or '')[:200],
                }
                for e in res.erreurs[:10]
            ]
            # v0.15.2.2.3 : injecter l'erreur de copie dans les erreurs
            # remontées à l'UI (sinon « toast rouge sans détail »).
            if erreur_copie:
                premieres_erreurs.append({
                    'ligne':    None,
                    'message':  erreur_copie[:500],
                    'contexte': '',
                })

            # La cible est « ok » seulement si la compilation ET la copie
            # ont réussi (cohérence avec ok_global).
            cible_ok = res.ok and (erreur_copie is None)

            resume_cibles.append({
                'cible_id':         cible['cible_id'],
                'libelle':          cible['libelle'],
                'cible_key':        cible_key,
                'ok':               cible_ok,
                'type_echec':       res.type_echec or (
                    'copie_pdf' if erreur_copie else None),
                'duree_ms':         res.duree_ms,
                'nb_erreurs':       len(premieres_erreurs),
                'premieres_erreurs': premieres_erreurs,
            })

    finally:
        # Sérialisation JSON du résumé. Stocké en clair dans
        # compile_log (la colonne est TEXT, le contenu peut être lu
        # comme JSON par l'UI).
        log_json = json.dumps({
            'version': '1',
            'type_document': type_document,
            'cibles': resume_cibles,
        }, ensure_ascii=False)

        # Garde-fou taille
        if len(log_json) > 50000:
            # Tronquer les contextes/messages si nécessaire (pathologique)
            log_json = log_json[:48000] + '... [log tronqué]"}'

        with store._conn() as conn:
            conn.execute("""
                UPDATE referentiel_documents
                   SET compile_ok       = ?,
                       compile_date     = CURRENT_TIMESTAMP,
                       compile_log      = ?,
                       compile_en_cours = 0
                 WHERE id = ?
            """, (1 if ok_global else 0, log_json, doc_id))
            conn.commit()

        _maj_statut(doc_id, fait=len(cibles),
                    etape_courante='Terminé')
        _finaliser_statut(
            doc_id,
            erreur=None if ok_global else "Erreurs de compilation (voir log)",
        )

    return {
        'doc_id':    doc_id,
        'compile_ok': ok_global,
        'log_json':  log_json,
        'nb_cibles': len(cibles),
    }


def compiler_document_async(store, doc_id: str,
                            racine_sources: Path | None = None,
                            dossier_images: Path | None = None,
                            racine_appli: Path | None = None,
                            tikz_libraries: list[str] | None = None,
                            tblr_libraries: list[str] | None = None
                            ) -> None:
    """Lance compiler_document dans un thread daemon. Retourne immédiatement.

    Pour suivre la progression, poller `lire_statut(doc_id)`. À la fin,
    relire le document via lister_documents pour récupérer le compile_ok
    persistant.
    """
    def _worker():
        try:
            compiler_document(
                store, doc_id,
                racine_sources=racine_sources,
                dossier_images=dossier_images,
                racine_appli=racine_appli,
                tikz_libraries=tikz_libraries,
                tblr_libraries=tblr_libraries,
            )
        except CompilationErreur as e:
            # Le verrou compile_en_cours peut être resté à 1 si l'erreur
            # est survenue très tôt. On le réinitialise par sécurité.
            try:
                with store._conn() as conn:
                    conn.execute("""
                        UPDATE referentiel_documents
                           SET compile_en_cours = 0,
                               compile_log = ?
                         WHERE id = ?
                    """, (f"{e.code}: {e}", doc_id))
                    conn.commit()
            except Exception:
                pass
            _finaliser_statut(doc_id, erreur=str(e))
        except Exception as e:
            try:
                with store._conn() as conn:
                    conn.execute("""
                        UPDATE referentiel_documents
                           SET compile_en_cours = 0,
                               compile_log = ?
                         WHERE id = ?
                    """, (f"Erreur inattendue: {e}\n{traceback.format_exc()}",
                          doc_id))
                    conn.commit()
            except Exception:
                pass
            _finaliser_statut(doc_id, erreur=f"Erreur inattendue : {e}")

    t = threading.Thread(target=_worker, daemon=True,
                         name=f"compile-{doc_id}")
    t.start()


def _dossier_du_referentiel(store, ref_id: str) -> Path:
    """Retourne le dossier où sont stockés les PDFs d'un référentiel."""
    return Path(store.data_dir) / 'referentiels' / ref_id


def chemin_pdf(store, ref_id: str, nom_fichier: str) -> Path:
    """Retourne le chemin attendu d'un PDF compilé pour ce référentiel."""
    return _dossier_du_referentiel(store, ref_id) / nom_fichier


def chemin_artefact(store, ref_id: str, doc_id: str, cible_key: str,
                    extension: str) -> Path:
    """v0.13.6.5.2.1 — Retourne le chemin d'un artefact de compilation.

    Les artefacts sont posés par l'orchestrateur de compilation dans
    `data/referentiels/<ref_id>/_artefacts/<doc_id>/<cible_key>.<extension>` :
      - extension='tex' : source LaTeX effectivement compilé
      - extension='log' : log pdflatex complet
      - extension='pdf' : PDF compilé (doublon avec le chemin métier)

    Le sous-dossier par doc_id (ajouté en v0.13.6.5.2.1) évite que
    plusieurs documents partageant le même cible_key (typiquement les
    types unitaires qui utilisent tous cible_id='unique') ne s'écrasent
    mutuellement.

    Utilisé par les routes GET /compilation/.../tex et /log pour
    récupérer ces artefacts après-coup et les afficher dans l'UI.
    """
    return (_dossier_du_referentiel(store, ref_id) / '_artefacts' / doc_id
            / f"{cible_key}.{extension}")


# ── État effectif ───────────────────────────────────────────────────────────


def _pdfs_figes_presents(conn: sqlite3.Connection, doc: dict, data_dir) -> bool:
    """v0.32.7 — True si le référentiel du document est verrouillé/utilisé et
    que TOUTES les cibles du document ont leur PDF figé dans
    `<data_dir>/referentiels/<ref_id>/_verrouille/pdfs/<nom_fichier>`.
    """
    from pathlib import Path
    ref_id = doc.get('referentiel_id')
    if not ref_id:
        return False
    row = conn.execute(
        "SELECT etat FROM referentiel_niveaux WHERE id=?", (ref_id,)).fetchone()
    if row is None or row["etat"] not in ("verrouille", "utilise"):
        return False
    dossier = Path(data_dir) / "referentiels" / ref_id / "_verrouille" / "pdfs"
    if not dossier.is_dir():
        return False
    try:
        cibles = lister_cibles_document(conn, doc["id"], ref_id,
                                        doc.get("type_document", ""))
    except Exception:
        return False
    if not cibles:
        return False
    for c in cibles:
        nom = c.get("nom_fichier")
        if not nom or not (dossier / nom).is_file():
            return False
    return True


def etat_effectif_document(conn: sqlite3.Connection, doc: dict,
                           data_dir=None) -> str:
    """Calcule l'état effectif d'un document selon ses colonnes
    compile_* et les mtime des atomes du niveau.

    Renvoie une string parmi :
      'non_compile' | 'en_cours' | 'ko' | 'perime' | 'ok'

    `doc` est le dict tel que retourné par services.referentiel_documents
    .lister_documents, étendu par les colonnes compile_* lues directement
    en BDD (cf. service appelant qui injecte ces colonnes).

    v0.15.2.6 — Péremption ciblée par type de document : on ne consulte
    que les mtime des tables d'atomes pertinentes (cf.
    services.peremption_atomes). Modifier une notion ne périme plus le
    livret de cartes.

    v0.32.7 — Cas des référentiels importés (verrouille/utilise) : leurs PDF
    ont été FIGÉS dans `_verrouille/pdfs/` sans passer par la compilation, donc
    `compile_ok`/`compile_date` sont vides alors que les PDF existent. Si le
    référentiel est verrouillé/utilisé et que les PDF figés du document sont
    présents sur disque, on considère l'état « ok » (verrouillé) plutôt que
    « non_compile ». Nécessite `data_dir`.
    """
    if doc.get('compile_en_cours'):
        return 'en_cours'
    compile_date = doc.get('compile_date')
    if not compile_date:
        # Référentiel verrouillé/utilisé avec PDF figés présents → « ok ».
        if data_dir is not None and _pdfs_figes_presents(conn, doc, data_dir):
            return 'ok'
        return 'non_compile'
    if not doc.get('compile_ok'):
        return 'ko'

    # Périmé si un atome PERTINENT du niveau a été modifié après
    # compile_date. La pertinence dépend du type de document
    # (cf. services.peremption_atomes).
    ref_id = doc.get('referentiel_id')
    if not ref_id:
        return 'ok'  # sécurité : pas de quoi vérifier
    from services.peremption_atomes import max_mtime_atomes_pertinents
    niveau = _niveau_du_referentiel(conn, ref_id)
    max_mtime = max_mtime_atomes_pertinents(
        conn, doc.get('type_document', ''), niveau
    )
    if max_mtime is None:
        # Soit aucun atome pertinent défini (livret_plans), soit niveau
        # vide. Dans les deux cas, pas de péremption par atome.
        return 'ok'

    # compile_date est en UTC stocké en string SQLite "YYYY-MM-DD HH:MM:SS".
    # Les mtime des atomes le sont aussi. Comparaison string fonctionne
    # tant que les deux sont au même format.
    if max_mtime > compile_date:
        return 'perime'
    return 'ok'


def _max_mtime_atomes_du_niveau(conn: sqlite3.Connection,
                                 niveau: str) -> str | None:
    """Retourne le max(mtime) parmi tous les atomes du niveau.

    .. deprecated:: v0.15.2.6
       Remplacé par
       `services.peremption_atomes.max_mtime_atomes_pertinents` qui cible
       les tables pertinentes par type de document. Conservé pour
       rétrocompat (scripts d'audit éventuels) mais n'est plus appelé
       par `etat_effectif_document`.

    Atomes pris en compte :
      - notions, methodes, exercices, fiches_resume, cartes_automatisme
      - tous filtrés par niveau

    None si aucun atome trouvé (cas pathologique).
    """
    tables = ['notions', 'methodes', 'exercices', 'fiches_resume',
              'cartes_automatisme']
    maxima = []
    for t in tables:
        try:
            row = conn.execute(
                f"SELECT MAX(mtime) FROM {t} WHERE niveau = ?",
                (niveau,),
            ).fetchone()
            if row and row[0]:
                maxima.append(row[0])
        except sqlite3.OperationalError:
            # Table absente : on ignore (rétrocompat tests minimalistes)
            continue
    return max(maxima) if maxima else None
