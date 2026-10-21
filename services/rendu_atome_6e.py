r"""services/rendu_atome_6e.py — v0.52.3

Rendu d'un exercice de 6e dans l'onglet « Rendu PDF » de l'atelier
d'exercices, à la mise en forme de l'équipe de 6e (module
`seqenseigne-style6e`), au lieu du rendu d'atome du cycle 4.

Retour de Laurent (v0.52.3) : les TP, activités complémentaires et séances
d'atelier se compilaient au format du cycle 4 dans l'atelier, alors que le
catalogue (`documents_6e`) les produisait déjà au format 6e. Cause :
`latex_rendu_atome.generer_tex_par_type` ne connaissait qu'un rendu, celui du
cycle 4, quel que soit le niveau.

Décisions (doc/redemarrage_v0_52_3.md) :

  - A1 Gabarit : celui de la règle R1 (v0.52.1, partagée en v0.52.2 avec le
    module Évaluations) : `gabarit_atelier_du_niveau` — référentiel interne
    principal « en cours » du niveau, sinon N09 → sixieme. Les séquences
    d'archive `Xnn` et les séries hors 6e gardent le rendu du cycle 4. Le
    cycle 4 ne change pas (même .tex).
  - A2 (outil de réparation, cf. outils/reparer_series_approche.py).
  - A3 Options du rendu (query string de l'atelier) : `version` eleve |
    corrigee (défaut eleve, comme le catalogue) ; `sujet` A | B pour la
    série EV (défaut A).
  - A4 Ce que l'on rend :
      * TP, AC, AT : le document entier, comme le catalogue
        (`documents_6e.generer_document_6e`) ;
      * EV : l'exercice d'évaluation (`\seqExoEval`), sujet A (énoncé) ou B
        (remédiation, ligne « % titre B : »), avec son barème et sa
        compétence quand il est dans une évaluation ;
      * F, A, E : `seqExoSix[O|A|E]` suivi de sa remédiation ; AE :
        `seqActiviteSix`. Le numéro est celui du livret 6e de la séquence
        (compteurs posés avant l'exercice) quand l'exercice y figure.
"""

from __future__ import annotations

import sqlite3

from services.gabarits_documents import SUJETS_6E, VERSIONS_6E

SERIES_LIVRET = ("F", "A", "E", "AE")
SERIES_DOCUMENTS = ("TP", "AC", "AT")
# v0.53.0 (MR2) — exercice de séance d'une mise en route : une fiche à la
# taille réelle (quart de A4, `seqPlancheFiches{4}`).
SERIES_6E = SERIES_LIVRET + SERIES_DOCUMENTS + ("EV", "MR")


class RenduAtome6eErreur(ValueError):
    pass


def _lire(conn, exercice_id: str) -> dict | None:
    from services.marqueurs_exercices import sql_colonnes          # v0.52.7
    cur = conn.execute("SELECT id, titre, enonce, corrige, remed_enonce, remed_corrige, "
                       "variables, niveau, sequence, serie_code, num" + sql_colonnes(conn)
                       + " FROM exercices WHERE id = ?", (exercice_id,))
    r = cur.fetchone()
    if r is None:
        return None
    noms = [d[0] for d in cur.description]
    return {k: (v if v is not None else "") for k, v in zip(noms, tuple(r))}


def est_au_gabarit_6e(conn: sqlite3.Connection, ex: dict | None) -> bool:
    """A1 — l'exercice se rend au format 6e."""
    if not ex or ex["serie_code"] not in SERIES_6E:
        return False
    if (ex["sequence"] or "").startswith("X") or not ex["niveau"]:
        return False
    from services.gabarits_documents import gabarit_atelier_du_niveau
    return gabarit_atelier_du_niveau(conn, ex["niveau"]) == "sixieme"


def options_rendu(options: dict | None) -> dict:
    """A3 — options validées (clés inconnues ignorées)."""
    o = {"version": "eleve", "sujet": "A"}
    for k in o:
        v = (options or {}).get(k)
        if v not in (None, ""):
            o[k] = v
    if o["version"] not in VERSIONS_6E:
        raise RenduAtome6eErreur(f"version invalide : {o['version']!r}")
    if o["sujet"] not in SUJETS_6E:
        raise RenduAtome6eErreur(f"sujet invalide : {o['sujet']!r}")
    return o


def _exercice_livret(ex: dict) -> dict:
    """Exercice au format attendu par les émetteurs du livret 6e."""
    d = dict(ex)
    try:
        d["code"] = f"{d['serie_code']}{int(d['num']):02d}"
    except (TypeError, ValueError):
        d["code"] = f"{d['serie_code']}{d['num']}"
    return d


def _corps_livret(conn, ex: dict) -> list[str]:
    from services import livret_sequence_6e as l6
    nom, _ = l6._nom_sequence(conn, ex["niveau"], ex["sequence"])
    L: list[str] = []
    numeros = None
    try:
        seq = l6.lire_sequence_6e(conn, ex["niveau"], ex["sequence"])
        numeros = l6.numeros_livret(seq, l6.normaliser_options(
            l6.options_livret(conn, ex["niveau"])))
    except Exception:
        seq = None                               # séquence non assemblée : pas de numéro
    e = _exercice_livret(ex)
    if ex["serie_code"] == "AE":
        n = numeros.activites.get(ex["id"]) if numeros else None
        if n:
            L.append(r"\setcounter{seqActiviteSix}{%d}" % (n - 1))
        l6._emettre_activite(L, e)
    else:
        n = numeros.exercices.get(ex["id"]) if numeros else None
        if n:
            L.append(r"\setcounter{seqExoSix}{%d}" % (n - 1))
        l6._emettre_exercice(L, e, ex["serie_code"], {"remediations": "apres_exercice"}, [])
    return [l6.entete({"nom": nom or ex["sequence"]}, False)] + L


def _corps_evaluation(conn, ex: dict, opts: dict) -> tuple[list[str], str]:
    """A4 — exercice d'évaluation, sujet A ou B. Retourne (lignes, nom)."""
    from services import render_evaluation as rev
    from services.livret_sequence_6e import entete
    ev = conn.execute("SELECT ee.evaluation_id FROM evaluation_exercices ee "
                      "JOIN evaluations e ON e.id = ee.evaluation_id "
                      "WHERE ee.exercice_id = ? ORDER BY e.ordre, e.id LIMIT 1",
                      (ex["id"],)).fetchone()
    rang, tag, nom = None, "", ""
    if ev is not None:
        st = rev.structure_evaluation_6e(conn, ev[0])
        nom = st["titre"]
        # v0.52.9 (D2, N1) — numéro affiché dans le sujet (partie 1 puis
        # partie 2 quand le sujet est coupé en deux ; sinon ordre de l'évaluation).
        for k, e in rev.exercices_affiches_6e(st, rev.parties_evaluation_6e(conn, ev[0], st)):
            if e["exercice_id"] == ex["id"]:
                rang = k
                tag = f"{rev._points(e['points'])} pts --- {e['objectif'] or 'bonus'}"
                break
    if not tag:
        o = conn.execute("SELECT o.code, sp.sequence_code FROM objectif_exos oe "
                         "JOIN objectifs o ON o.id = oe.objectif_id "
                         "JOIN sequence_parties p ON p.id = o.partie_id "
                         "JOIN sequences_par_niveau sp ON sp.id = p.sequence_par_niveau_id "
                         "WHERE oe.exercice_id = ? ORDER BY (oe.serie = 'EV') DESC, oe.ordre "
                         "LIMIT 1", (ex["id"],)).fetchone()
        tag = f"{o[1]}-{o[0]}" if o else ""
    titre = ex["titre"] or ""
    if opts["sujet"] == "B":
        titre, enonce = rev._sujet_b(ex["remed_enonce"], titre)
        corrige = ex["remed_corrige"]
        if not enonce.strip():
            enonce = r"\emph{Sujet B non rédigé.}"
    else:
        enonce, corrige = ex["enonce"], ex["corrige"]
    L = [entete({"nom": (nom or ex["sequence"]) + f" --- sujet {opts['sujet']}"},
                opts["version"] == "corrigee")]
    L.append(r"\setcounter{seqExoEval}{%d}" % ((rang or 1) - 1))
    if (ex["variables"] or "").strip():
        L.append(ex["variables"].rstrip())
    L.append(r"\seqExoEval{" + titre + "}{" + tag + "}")
    L.append((enonce or "").strip())
    if (corrige or "").strip():
        L.append(r"\seqLocExplication{" + corrige.strip() + "}")
    return L, nom


def _corps_mise_en_route(conn, ex: dict, opts: dict) -> list[str]:
    """v0.53.0 (MR2) — l'exercice de séance seul, sur une planche à 4 par A4
    (taille réelle de la fiche découpée) ; sa séquence de mise en route
    donne la ligne de référence (séance, objectif)."""
    from services import mises_en_route_6e as mer
    try:
        s = mer.lire_sequence_mer(conn, ex["niveau"], ex["sequence"])
        e = next((x for x in s["exercices"] if x["id"] == ex["id"]), None)
    except mer.MiseEnRouteErreur:
        s, e = None, None
    if s is None:
        s = {"code": ex["sequence"], "nom": ex["sequence"], "exercices": []}
    if e is None:
        e = dict(_exercice_livret(ex), seance=ex.get("num"), objectif="")
    return mer.corps_planche(s, 4, opts["version"], [e])


def generer_tex_atome_6e(conn: sqlite3.Connection, exercice_id: str,
                         options: dict | None = None, tikz_libraries=None,
                         tblr_libraries=None) -> str:
    """Rendu 6e d'un exercice (A4), sans tester le gabarit."""
    ex = _lire(conn, exercice_id)
    if ex is None:
        raise LookupError(f"Exercice introuvable : {exercice_id}")
    opts = options_rendu(options)
    code = ex["serie_code"]
    if code in SERIES_DOCUMENTS:
        from services.documents_6e import generer_document_6e
        return generer_document_6e(conn, exercice_id, {"version": opts["version"]},
                                   tikz_libraries, tblr_libraries)
    from services.livret_sequence_6e import document
    try:
        etiquette = f"{code}{int(ex['num']):02d}"
    except (TypeError, ValueError):
        etiquette = code
    if code == "EV":
        corps, _ = _corps_evaluation(conn, ex, opts)
        titre = f"Exercice d'évaluation 6e — {ex['sequence']} {etiquette} — sujet {opts['sujet']}"
    elif code == "MR":
        corps = _corps_mise_en_route(conn, ex, opts)
        titre = f"Exercice de séance 6e — {ex['sequence']} {etiquette}"
    elif code in SERIES_LIVRET:
        corps = _corps_livret(conn, ex)
        titre = f"Exercice 6e — {ex['sequence']} {etiquette}"
    else:
        raise RenduAtome6eErreur(f"série {code!r} sans rendu 6e")
    return document(conn, ex["niveau"], titre, corps, opts["version"] == "corrigee",
                    tikz_libraries, tblr_libraries)


def generer_tex_atome_6e_si_gabarit(conn: sqlite3.Connection, exercice_id: str,
                                    options: dict | None = None, tikz_libraries=None,
                                    tblr_libraries=None) -> str | None:
    """Point d'entrée de `latex_rendu_atome.generer_tex_par_type` : le .tex
    6e si l'exercice relève du gabarit « sixieme » (A1), sinon None (rendu
    du cycle 4, inchangé)."""
    ex = _lire(conn, exercice_id)
    if not est_au_gabarit_6e(conn, ex):
        return None
    return generer_tex_atome_6e(conn, exercice_id, options, tikz_libraries, tblr_libraries)


# ── v0.53.0 (B2) — Fiche de résumé au modèle « Fiches » ─────────────────────

def generer_tex_fiche_6e_si_gabarit(conn: sqlite3.Connection, fiche_id: str,
                                    options: dict | None = None, tikz_libraries=None,
                                    tblr_libraries=None) -> str | None:
    r"""Rendu d'une fiche de résumé (ou d'une fiche de cours de mise en route)
    au modèle « Fiches » : `seqFicheResumeSix`, comme les fiches de cours du
    catalogue. Version complète par défaut (`\seqVersionComplete`) ;
    `version=eleve` : à compléter. None (rendu du cycle 4, inchangé) si le
    niveau n'est pas au modèle « Fiches », pour une archive `Xnn` ou une
    fiche sans niveau."""
    from services.fiches_resume import FicheIntrouvable, lire_fiche
    from services.gabarits_documents import gabarit_atelier_du_niveau
    try:
        fiche = lire_fiche(conn, fiche_id)
    except FicheIntrouvable:
        return None
    niveau, sequence = fiche.get("niveau") or "", fiche.get("sequence") or ""
    if not niveau or sequence.startswith("X"):
        return None
    if gabarit_atelier_du_niveau(conn, niveau) != "sixieme":
        return None
    version = (options or {}).get("version") or "corrigee"
    if version not in VERSIONS_6E:
        raise RenduAtome6eErreur(f"version invalide : {version!r}")
    from services import livret_sequence_6e as l6
    from services.mises_en_route_6e import est_sequence_mer, libelle_mer
    nom, _ = l6._nom_sequence(conn, niveau, sequence)
    if est_sequence_mer(sequence):
        nom = f"{libelle_mer(sequence)} --- {nom or sequence}"
    corps = [l6.entete({"nom": nom or sequence or fiche.get("titre") or "Fiche"}, False)]
    if version == "corrigee":
        corps.append(r"\seqVersionComplete")
    l6._emettre_fiche(corps, fiche)
    titre = f"Fiche de résumé 6e — {sequence} — {fiche.get('titre') or ''}"
    return l6.document(conn, niveau, titre, corps, False, tikz_libraries, tblr_libraries)
