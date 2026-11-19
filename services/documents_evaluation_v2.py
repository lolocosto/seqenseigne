r"""services/documents_evaluation_v2.py — v0.60.1

Documents de la version 2 du modèle Fiches restés pour la v0.60.1
(`doc/redemarrage_v0_60_1.md`, besoins E6 et E7, décisions 17 du 18 novembre) :

  - **D17a « Tests courts »** — type `tests_courts_6e` du catalogue d'un
    référentiel principal au modèle Fiches **avec l'option cartes** (comme le
    récap et les planches, v0.59.1) : une cible par test court du principal
    (partie = celle de ses objectifs), sujet A ou B, version élève ou corrigée.
    La version corrigée (document enseignant) ajoute, après le sujet, l'encadré
    « Cartes d'automatisme évaluées » : cartes validées rattachées aux objectifs
    de la partie (`cartes_partie`). Le sujet lui-même est celui du document
    « Évaluations » (même générateur) : ses cibles ne changent pas.
  - **D-SE « Séance d'évaluation »** — hors catalogue, comme le document de
    rituels dont il dépend : pour une semaine du calendrier
    (`progression_rituels.calendrier`), une page d'en-tête (jour, sujets et
    durées, total) puis chaque sujet sur sa page (A ou B, élève ou corrigé).
    Refus au-delà de 50 min ou de 5 objectifs (paramètres de la séance), sauf
    pour une évaluation seule (déjà signalée par le calendrier). La durée
    figure dans l'en-tête de la séance ; les sujets isolés ne changent pas.
"""
from __future__ import annotations

import sqlite3


class DocumentEvaluationErreur(ValueError):
    pass


# ── D17a — Tests courts ──────────────────────────────────────────────────────

def cibles_tests_courts(conn: sqlite3.Connection, niveau: str) -> list[dict]:
    """Une cible par test court du principal du niveau, dans l'ordre des
    séquences et des parties : « TC/N11/A3/p1 » (« …/p1/T2 » au-delà du
    premier test de la partie) ; `sequence` et `partie` rattachent le document."""
    from services.progression_rituels import tests_courts_par_partie
    from services.referentiels_internes import sequences_du_perimetre
    from services.referentiel_documents_compilation import niveau_fichier, noms_cible
    tests = tests_courts_par_partie(conn, niveau)
    nf = niveau_fichier(conn, niveau)          # v0.60.3 (N1) : niveau réel dans le nom
    cibles = []
    for s in sequences_du_perimetre(conn, niveau, "principal"):
        for pid, num, lib in conn.execute(
                "SELECT id, numero, COALESCE(libelle, '') FROM sequence_parties WHERE "
                "sequence_par_niveau_id = ? ORDER BY numero", (s["sn_id"],)).fetchall():
            for rang, t in enumerate(tests.get(pid, []), start=1):
                suffixe = "" if rang == 1 else f"/T{rang}"
                cibles.append({
                    "cible_id": f"TC/{niveau}/{s['code']}/p{num}{suffixe}",
                    "libelle": f"Test court {s['code']} p{num}" + (f" n° {rang}" if rang > 1
                                                                   else ""),
                    **noms_cible("tests_courts_6e", nf, f"__{niveau}__{s['code']}__p{num}"
                                 + (f"__T{rang}" if rang > 1 else "")),
                    "niveau": niveau, "sequence": s["code"], "partie": num,
                    "eval_id": t["id"], "titre_doc": t["titre"] or lib})
    return cibles


def encadre_cartes(conn, evaluation_id: str) -> list[str]:
    """Encadré enseignant « Cartes d'automatisme évaluées » (liste vide si la
    partie n'a pas de carte validée)."""
    from services.cartes_partie import cartes_de_partie, liste_latex
    from services.progression_rituels import partie_d_evaluation
    pid = partie_d_evaluation(conn, evaluation_id)
    cartes = cartes_de_partie(conn, pid) if pid else []
    if not cartes:
        return []
    num = conn.execute("SELECT numero FROM sequence_parties WHERE id = ?", (pid,)).fetchone()[0]
    return [r"\par\bigskip\noindent\fbox{\parbox{\dimexpr\linewidth-2\fboxsep-2\fboxrule}{",
            r"\textbf{Cartes d'automatisme évaluées (partie " + str(num) + ", "
            + str(len(cartes)) + r" cartes)}\par\smallskip\small ",
            liste_latex(cartes) + r"}}\par"]


def generer_test_court(conn: sqlite3.Connection, evaluation_id: str,
                       options: dict | None = None, tikz_libraries=None,
                       tblr_libraries=None) -> str:
    """Sujet du test court (générateur des évaluations au modèle Fiches) ;
    version corrigée : + cartes évaluées."""
    from services.livret_sequence_6e import document
    from services import render_evaluation as rev
    opts = rev.options_evaluation_6e(options)
    if opts["calculatrice"] == "selon_evaluation":
        from services.marqueurs_exercices import calculatrice_evaluation
        opts["calculatrice"] = calculatrice_evaluation(conn, evaluation_id)["valeur"]
    st = rev.structure_evaluation_6e(conn, evaluation_id)
    decoupage = rev.parties_evaluation_6e(conn, evaluation_id, st)
    corps = rev.corps_evaluation_6e(conn, st, opts, decoupage)
    if opts["version"] == "corrigee":
        corps += encadre_cartes(conn, evaluation_id)
    return document(conn, st["niveau"], f"Test court — {st['titre']} — sujet {opts['sujet']}",
                    corps, opts["version"] == "corrigee", tikz_libraries, tblr_libraries)


# ── D-SE — Séance d'évaluation ───────────────────────────────────────────────

def seance(conn, ref_id: str, semaine: int) -> dict:
    """{semaine, jour, evaluations: [{id, titre, duree, objectifs,
    test_court?}], minutes, objectifs, limites} d'après le calendrier."""
    from services.progression_rituels import calendrier
    cal = calendrier(conn, ref_id)
    P = cal["parametres"]
    s = next((x for x in cal["semaines"] if x["numero"] == int(semaine)), None)
    if s is None or not s["seance_evaluation"]:
        raise DocumentEvaluationErreur(f"pas de séance d'évaluation en semaine {semaine}")
    evs = s["evaluations"]
    return {"semaine": int(semaine), "jour": P["jour_evaluation"], "evaluations": evs,
            "minutes": sum(e["duree"] for e in evs),
            "objectifs": sum(e["objectifs"] for e in evs),
            "limites": (P["seance_evaluation_minutes"], P["seance_evaluation_objectifs"]),
            "niveau": cal["niveau"]}


def controler_seance(se: dict) -> list[str]:
    """Refus (liste des motifs) au-delà des limites, sauf évaluation seule."""
    if len(se["evaluations"]) <= 1:
        return []
    m, o = se["limites"]
    motifs = []
    if se["minutes"] > m:
        motifs.append(f"{se['minutes']} min pour une séance de {m} min")
    if se["objectifs"] > o:
        motifs.append(f"{se['objectifs']} objectifs pour {o} au plus")
    return motifs


def generer_seance_evaluation(conn: sqlite3.Connection, ref_id: str, semaine: int,
                              options: dict | None = None, tikz_libraries=None,
                              tblr_libraries=None) -> str:
    """Document de la séance : en-tête puis les sujets (options sujet, version)."""
    from services.latex_texte import texte_latex
    from services.livret_sequence_6e import document
    from services import render_evaluation as rev
    se = seance(conn, ref_id, semaine)
    if not se["evaluations"]:
        raise DocumentEvaluationErreur(f"semaine {semaine} : aucune évaluation dans la séance")
    motifs = controler_seance(se)
    if motifs:
        raise DocumentEvaluationErreur("séance trop chargée : " + " ; ".join(motifs))
    opts = rev.options_evaluation_6e(options)
    corrigee = opts["version"] == "corrigee"
    lignes = [rf"\item {texte_latex(e['titre'])} --- {e['duree']} min"
              + (" (test court)" if e.get("test_court") else
                 f", {e['objectifs']} objectif{'s' if e['objectifs'] > 1 else ''}")
              for e in se["evaluations"]]
    m, o = se["limites"]
    corps = [r"\begin{center}{\Large\bfseries Séance d'évaluation --- semaine "
             + str(se["semaine"]) + r"}\\[4pt]"
             + texte_latex(se["jour"]) + f" --- sujet {opts['sujet']}"
             + (" --- corrigé" if corrigee else "") + r"\end{center}",
             r"\begin{itemize}"] + lignes + [r"\end{itemize}",
             rf"\textbf{{Durée totale : {se['minutes']} min}} (séance de {m} min, "
             rf"{o} objectifs au plus)." + (r" \textit{Évaluation seule plus longue qu'une "
                                            r"séance.}" if se["minutes"] > m else "")]
    for e in se["evaluations"]:
        o_ev = dict(opts)
        if o_ev["calculatrice"] == "selon_evaluation":
            from services.marqueurs_exercices import calculatrice_evaluation
            o_ev["calculatrice"] = calculatrice_evaluation(conn, e["id"])["valeur"]
        st = rev.structure_evaluation_6e(conn, e["id"])
        dec = rev.parties_evaluation_6e(conn, e["id"], st)
        corps.append(r"\clearpage\setcounter{page}{1}")
        corps += rev.corps_evaluation_6e(conn, st, o_ev, dec)
        if corrigee and e.get("test_court"):
            corps += encadre_cartes(conn, e["id"])
    return document(conn, se["niveau"], f"Séance d'évaluation — semaine {semaine}", corps,
                    corrigee, tikz_libraries, tblr_libraries)
