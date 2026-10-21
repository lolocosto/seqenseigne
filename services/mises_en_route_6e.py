r"""services/mises_en_route_6e.py — v0.53.0

Mises en route de 6e au modèle « Fiches de résumé par objectif » (gabarit
`sixieme`) : séquences M01 à M07 de `outils/ref6e_v2.md` (« Mises en route
(M2026_N09) »), cahier des charges § 4.

Une séance de 55 min commence par environ 10 min de mise en route : un
exercice par séance (série d'environ 5 items avec un score), une fiche de
cours par séquence de mise en route, à coller dans le cahier, des tests
courts sur 10 réservés aux mises en route.

Décisions (doc/redemarrage_v0_53_0.md, audit SP/livraison_v0530/audit_mer.md) :

  - MR1 Où vivent les mises en route : dans l'atelier du niveau (N09),
    comme des séquences de code `Mnn` (sequences_du_cycle C03 Mnn, numéro
    200 + n ; sequences_par_niveau N09/Mnn ; une seule partie ; les
    objectifs Mnn-01… dans `objectifs`). Elles suivent donc le modèle du
    référentiel interne principal du niveau (règle R1b) sans rien de plus,
    et tous les outils de l'atelier les voient (atelier d'exercices, de
    fiches, module Évaluations, rendu par lot). Elles ne font **pas** partie
    du référentiel principal (exclusivité, MR7) : `hors_principal` les
    écarte des documents, des modèles « programme du cycle » et de la
    validation du principal, comme les archives `Xnn`. Côté classe, elles
    seront publiées comme un référentiel de type « mer » (suite prévue) ;
    en attendant, la progression de mise en route de la classe garde le
    référentiel externe M2026_N09.
  - MR1b Pas d'objectif « Cours » dans une séquence Mnn : la fiche de cours
    est rattachée à la séquence (MR3). La convention « objectif (n-1)1 =
    Cours » ne s'applique pas aux Mnn (`est_objectif_cours`), sinon M01-01
    serait pris pour le cours.
  - MR2 Série `MR` (« mise en route ») de l'atelier d'exercices : un atome
    par exercice de séance, numéroté dans l'ordre des séances (MR01 = séance
    1), relié à l'objectif visé (objectif_exos, série MR). Série
    « documents » : dans aucun livret.
  - MR3 Fiche de cours de séquence : une fiche de résumé sans objectif
    (fiches_resume.objectif_id NULL) de la séquence Mnn, la première par
    numéro. Version élève « à compléter », version complète par
    `\seqVersionComplete`, comme les fiches du principal.
  - MR4 Version complète rédigée à part (`latex_corrige` du lot, quand elle
    diffère de `latex`) : seconde fiche sans objectif de la séquence, titrée
    « … (version complète) » (`SUFFIXE_COMPLETE`) ; la version corrigée de
    la fiche de cours l'utilise.
  - MR5 Documents d'une séquence de mise en route (`generer_document_mer`,
    route du livret de séquence, option `mer`) : fiche de cours (1 ou 2 par
    A4), planche des exercices de séance (2, 3 ou 4 par A4, `seqPlancheFiches`
    / `seqBande` ; version corrigée : réponses à leur place, mêmes traits de
    coupe, puis les corrigés rédigés à la suite), test court (module
    Évaluations, rendu 6e ; 1 ou 2 par A4),
    plan de séquence pour l'enseignant (séances, objectif, exercice, tests,
    contrôle de validation). Élève ou corrigé.
  - MR6 Validation d'une séquence de mise en route (`valider_sequence_mer`) :
    fiche de cours, au moins un exercice MR par objectif, chaque exercice MR
    relié à un objectif de la séquence ; nombre d'exercices MR ≠ nombre de
    séances prévu : avertissement seulement.
  - Le cycle 4 (cartes d'automatisme, Leitner) n'est pas touché.
"""

from __future__ import annotations

import re
import sqlite3

SERIE_MR = "MR"
LIBELLE_MR = "mise en route"
NUMERO_CYCLE_BASE = 200           # sequences_du_cycle.numero = 200 + n (UNIQUE par cycle)
PAR_PAGE = (2, 3, 4)
EXEMPLAIRES = (1, 2)
DOCUMENTS_MER = ("fiche_cours", "planche", "test_court", "plan")
LIBELLES_DOCUMENTS_MER = {"fiche_cours": "Fiche de cours",
                          "planche": "Exercices de séance",
                          "test_court": "Test court",
                          "plan": "Plan de séquence (enseignant)"}
SUFFIXE_COMPLETE = " (version complète)"

_RE_MER = re.compile(r"M\d{2}")


class MiseEnRouteErreur(ValueError):
    pass


# ── Codes ────────────────────────────────────────────────────────────────────

def est_sequence_mer(code: str | None) -> bool:
    """MR1 — séquence de mise en route : code `Mnn`."""
    return bool(_RE_MER.fullmatch((code or "").strip()))


def hors_principal(code: str | None) -> bool:
    """MR7 — séquence écartée du référentiel principal : archive du cycle 3
    (`Xnn`, v0.52.0) ou mise en route (`Mnn`, v0.53.0)."""
    c = (code or "").strip()
    return c.startswith("X") or est_sequence_mer(c)


def est_objectif_cours(code_objectif: str, numero_partie: int,
                       sequence_code: str | None = None) -> bool:
    """MR1b — l'objectif « Cours » d'une partie porte le code (n-1)1, sauf
    dans une séquence de mise en route (aucun objectif Cours)."""
    if est_sequence_mer(sequence_code):
        return False
    return (code_objectif or "").strip() == f"{numero_partie - 1}1"


def numero_mer(code: str) -> int:
    """M03 → 3."""
    if not est_sequence_mer(code):
        raise MiseEnRouteErreur(f"{code!r} n'est pas une séquence de mise en route.")
    return int(code[1:])


def libelle_mer(code: str) -> str:
    """« Mise en route 3 »."""
    return f"Mise en route {numero_mer(code)}"


# ── Lecture ──────────────────────────────────────────────────────────────────

def _exercice(r: dict) -> dict:
    d = {k: (v if v is not None else "") for k, v in r.items()}
    try:
        d["code"] = f"{d['serie_code']}{int(d['num']):02d}"
    except (TypeError, ValueError):
        d["code"] = f"{d['serie_code']}{d['num']}"
    return d


def fiches_de_sequence(conn, niveau: str, sequence: str) -> tuple[dict | None, dict | None]:
    """MR3, MR4 — (fiche de cours, fiche « version complète » ou None) :
    fiches sans objectif de la séquence, par numéro."""
    from services.fiches_resume import FicheIntrouvable, lire_fiche
    cours = complete = None
    for (fid, titre) in conn.execute(
            "SELECT id, titre FROM fiches_resume WHERE niveau = ? AND sequence = ? AND "
            "objectif_id IS NULL ORDER BY num_fiche, id", (niveau, sequence)).fetchall():
        try:
            f = lire_fiche(conn, fid)
        except FicheIntrouvable:
            continue
        if (titre or "").endswith(SUFFIXE_COMPLETE):
            complete = complete or f
        else:
            cours = cours or f
    return cours, complete


def tests_courts(conn, niveau: str, sequence: str) -> list[dict]:
    """Évaluations du niveau dont les exercices sont surtout de la séquence
    (même règle que le rendu 6e : séquence majoritaire de ses exercices)."""
    from collections import Counter
    out = []
    for r in conn.execute("SELECT id, numero, titre, ordre FROM evaluations WHERE niveau = ? "
                          "ORDER BY ordre, numero, id", (niveau,)).fetchall():
        seqs = Counter(x[0] for x in conn.execute(
            "SELECT e.sequence FROM evaluation_exercices ee JOIN exercices e "
            "ON e.id = ee.exercice_id WHERE ee.evaluation_id = ? AND e.sequence <> ''",
            (r[0],)))
        if seqs and seqs.most_common(1)[0][0] == sequence:
            out.append({"id": r[0], "numero": r[1], "titre": r[2] or ""})
    return out


def lire_sequence_mer(conn: sqlite3.Connection, niveau: str, sequence: str) -> dict:
    """{code, nom, numero, theme_couleur, objectifs: [{id, code, etiquette,
    nom, critere_F, critere_A, nb_seances}], exercices: [MR dans l'ordre des
    séances, avec `seance` et `objectif` (étiquette)], fiche, fiche_complete,
    tests: [{id, numero, titre}]}."""
    if not est_sequence_mer(sequence):
        raise MiseEnRouteErreur(f"{sequence!r} n'est pas une séquence de mise en route.")
    sn = conn.execute("SELECT id FROM sequences_par_niveau WHERE niveau = ? AND "
                      "sequence_code = ?", (niveau, sequence)).fetchone()
    if sn is None:
        raise MiseEnRouteErreur(f"{niveau}/{sequence} : séquence de mise en route absente "
                                "de l'atelier (importer le lot).")
    from services.livret_sequence_6e import _nom_sequence
    nom, _ = _nom_sequence(conn, niveau, sequence)
    th = conn.execute(
        "SELECT t.code_couleur FROM sequences_du_cycle s JOIN param_niveaux pn ON "
        "pn.cycle_code = s.cycle_code LEFT JOIN themes t ON t.id = s.theme_id "
        "WHERE pn.code = ? AND s.code = ?", (niveau, sequence)).fetchone()
    objectifs = []
    for o in conn.execute(
            "SELECT o.id, o.code, o.nom, o.critere_F, o.critere_A, o.nb_seances "
            "FROM objectifs o JOIN sequence_parties p ON p.id = o.partie_id "
            "WHERE p.sequence_par_niveau_id = ? ORDER BY p.numero, o.code", (sn[0],)):
        objectifs.append({"id": o[0], "code": o[1], "etiquette": f"{sequence}-{o[1]}",
                          "nom": o[2] or "", "critere_F": o[3] or "", "critere_A": o[4] or "",
                          "nb_seances": float(o[5] or 0)})
    par_id = {o["id"]: o for o in objectifs}
    from services.marqueurs_exercices import sql_colonnes
    cur = conn.execute(
        "SELECT id, titre, enonce, corrige, remed_enonce, remed_corrige, variables, niveau, "
        "sequence, serie_code, num, etat_code" + sql_colonnes(conn) + " FROM exercices "
        "WHERE niveau = ? AND sequence = ? AND serie_code = ? ORDER BY num, id",
        (niveau, sequence, SERIE_MR))
    noms = [d[0] for d in cur.description]
    exercices = []
    for r in cur.fetchall():
        ex = _exercice(dict(zip(noms, tuple(r))))
        ex["seance"] = ex.get("num")
        lien = conn.execute("SELECT objectif_id FROM objectif_exos WHERE exercice_id = ? "
                            "AND serie = ? ORDER BY ordre", (ex["id"], SERIE_MR)).fetchall()
        o = next((par_id[x[0]] for x in lien if x[0] in par_id), None)
        ex["objectif"] = o["etiquette"] if o else ""
        ex["objectif_nom"] = o["nom"] if o else ""
        exercices.append(ex)
    fiche, complete = fiches_de_sequence(conn, niveau, sequence)
    return {"code": sequence, "niveau": niveau, "nom": nom or sequence,
            "numero": numero_mer(sequence), "theme_couleur": (th[0] if th else "") or "",
            "objectifs": objectifs, "exercices": exercices, "fiche": fiche,
            "fiche_complete": complete, "tests": tests_courts(conn, niveau, sequence)}


# ── MR6 Validation ───────────────────────────────────────────────────────────

def _fmt(n: float) -> str:
    return str(int(n)) if float(n) == int(n) else f"{n:g}".replace(".", ",")


def valider_sequence_mer(conn: sqlite3.Connection, niveau: str, sequence: str,
                         seq: dict | None = None) -> dict:
    """MR6 — {"valide": bool, "erreurs": [...], "avertissements": [...]}.

    Exigé : la fiche de cours, au moins un exercice MR par objectif, chaque
    exercice MR relié à un objectif de la séquence. Avertissements : nombre
    d'exercices MR différent du nombre de séances prévu (séquence, puis
    objectif par objectif), aucun test court."""
    s = seq or lire_sequence_mer(conn, niveau, sequence)
    erreurs, avert = [], []
    if s["fiche"] is None:
        erreurs.append("pas de fiche de cours de séquence")
    if not s["objectifs"]:
        erreurs.append("aucun objectif")
    par_obj: dict = {o["etiquette"]: 0 for o in s["objectifs"]}
    for ex in s["exercices"]:
        if ex["objectif"]:
            par_obj[ex["objectif"]] += 1
        else:
            erreurs.append(f"{ex['code']} relié à aucun objectif de la séquence")
    for o in s["objectifs"]:
        if not par_obj[o["etiquette"]]:
            erreurs.append(f"{o['etiquette']} sans exercice de séance")
    prevu = sum(o["nb_seances"] for o in s["objectifs"])
    if prevu and len(s["exercices"]) != prevu:
        avert.append(f"{len(s['exercices'])} exercice(s) de séance pour {_fmt(prevu)} "
                     "séance(s) prévue(s)")
    for o in s["objectifs"]:
        n = par_obj[o["etiquette"]]
        if o["nb_seances"] and n and n != o["nb_seances"]:
            avert.append(f"{o['etiquette']} : {n} exercice(s) pour {_fmt(o['nb_seances'])} "
                         "séance(s)")
    if not s["tests"]:
        avert.append("aucun test court")
    return {"valide": not erreurs, "erreurs": erreurs, "avertissements": avert}


# ── Rendu LaTeX ──────────────────────────────────────────────────────────────

def options_mer(options: dict | None) -> dict:
    """MR5 — options d'un document de mise en route (clés inconnues ignorées)."""
    from services.gabarits_documents import SUJETS_6E, VERSIONS_6E
    o = {"document": "planche", "version": "eleve", "par_page": 4, "exemplaires": 1,
         "sujet": "A", "test": 1}
    for k in o:
        v = (options or {}).get(k)
        if v not in (None, ""):
            o[k] = v
    for k in ("par_page", "exemplaires", "test"):
        try:
            o[k] = int(o[k])
        except (TypeError, ValueError):
            raise MiseEnRouteErreur(f"{k} invalide : {o[k]!r}")
    if o["document"] not in DOCUMENTS_MER:
        raise MiseEnRouteErreur(f"document invalide : {o['document']!r} "
                                f"(attendu : {', '.join(DOCUMENTS_MER)})")
    if o["version"] not in VERSIONS_6E:
        raise MiseEnRouteErreur(f"version invalide : {o['version']!r}")
    if o["par_page"] not in PAR_PAGE:
        raise MiseEnRouteErreur(f"par_page invalide : {o['par_page']!r} (2, 3 ou 4)")
    if o["exemplaires"] not in EXEMPLAIRES:
        raise MiseEnRouteErreur(f"exemplaires invalide : {o['exemplaires']!r} (1 ou 2)")
    if o["sujet"] not in SUJETS_6E:
        raise MiseEnRouteErreur(f"sujet invalide : {o['sujet']!r}")
    if o["test"] < 1:
        raise MiseEnRouteErreur(f"test invalide : {o['test']!r}")
    return o


def _entete(s: dict, corrige: bool) -> str:
    from services.livret_sequence_6e import entete
    return entete({"nom": f"{libelle_mer(s['code'])} --- {s['nom']}"}, corrige)


def _copies(corps: list[str], exemplaires: int) -> list[str]:
    r"""1 exemplaire : tel quel ; 2 : `seqCopies{2}` (deux demi-pages A5 à
    découper, compteurs du module rétablis pour chaque copie)."""
    if exemplaires == 1:
        return corps
    return [r"\begin{seqCopies}{%d}" % exemplaires, *corps, r"\end{seqCopies}"]


def corps_fiche_cours(s: dict, version: str, exemplaires: int = 1) -> list[str]:
    """MR3, MR4 — fiche de cours de la séquence : titre « Mise en route n
    --- nom », puis la fiche (à compléter ; complète en version corrigée)."""
    from services.livret_sequence_6e import _emettre_fiche
    fiche = s["fiche"]
    if fiche is None:
        raise MiseEnRouteErreur(f"{s['code']} : pas de fiche de cours de séquence.")
    complete = version == "corrigee"
    if complete and s.get("fiche_complete") is not None:
        fiche = dict(s["fiche_complete"],
                     titre=s["fiche_complete"]["titre"][:-len(SUFFIXE_COMPLETE)])
    corps: list[str] = [r"\seqTitreFicheSix{" + libelle_mer(s["code"]) + " --- "
                        + s["nom"] + "}"]
    _emettre_fiche(corps, fiche)
    L = [_entete(s, False)]
    if complete:
        L.append(r"\seqVersionComplete")
    return L + _copies(corps, exemplaires)


def _ligne_reference(s: dict, ex: dict) -> str:
    from services.marqueurs_exercices import latex_6e
    marques = latex_6e(ex)
    ref = " --- ".join(x for x in (f"{libelle_mer(s['code'])}",
                                    f"séance {ex['seance']}" if ex.get("seance") else "",
                                    ex.get("objectif") or "") if x)
    return (r"{\footnotesize\color{seqSixGrisTexte}" + ref + r"\hfill"
            + (marques + r"\quad{}" if marques else "") + ex["code"] + r"}\par")


def emettre_bande(L: list, s: dict, ex: dict) -> None:
    r"""Une fiche de séance (`seqBande`) : ligne de référence (mise en route,
    séance, objectif, marqueurs, code), titre si l'énoncé n'a pas son propre
    bandeau (`seqCalculMental`), énoncé. Les items de calcul mental repartent
    à 1 à chaque fiche. Le corrigé rédigé n'est pas dans la bande (il ne
    tient pas dans un quart de page) : voir `emettre_corriges_rediges`."""
    L.append(r"\begin{seqBande}")
    L.append(r"\setcounter{seqItemCM}{0}")
    L.append(_ligne_reference(s, ex))
    enonce = (ex.get("enonce") or "").strip()
    if "seqCalculMental" not in enonce and (ex.get("titre") or "").strip():
        L.append(r"{\bfseries\color{seqSixBleu}" + ex["titre"].strip() + r"}\par\smallskip")
    if (ex.get("variables") or "").strip():
        L.append(ex["variables"].rstrip())
    L.append(enonce)
    L.append(r"\end{seqBande}")


def emettre_corriges_rediges(L: list, s: dict, exos: list[dict]) -> None:
    r"""MR5 — Version corrigée : les fiches gardent la mise en page de la
    version élève (réponses en rouge à leur place, mêmes traits de coupe) ;
    les corrigés rédigés suivent, à la suite, après la planche."""
    avec = [ex for ex in exos if (ex.get("corrige") or "").strip()]
    if not avec:
        return
    L.append(r"\begin{center}{\Large\bfseries\color{seqSixVert}Corrigés rédigés}\end{center}")
    for ex in avec:
        titre = " --- ".join(x for x in (f"Séance {ex['seance']}" if ex.get("seance") else "",
                                         (ex.get("titre") or "").strip(), ex["code"]) if x)
        L.append(r"\needspace{5\baselineskip}")
        L.append(r"\seqPartieSix{" + titre + "}")
        L.append(r"\seqLocExplication{" + ex["corrige"].strip() + "}")


def corps_planche(s: dict, par_page: int, version: str,
                  exercices: list[dict] | None = None) -> list[str]:
    """MR5 — planche des exercices de séance, `par_page` fiches par A4 à
    découper au massicot (dans l'ordre des séances)."""
    exos = s["exercices"] if exercices is None else exercices
    if not exos:
        raise MiseEnRouteErreur(f"{s['code']} : aucun exercice de séance (série MR).")
    L = [_entete(s, version == "corrigee"), r"\begin{seqPlancheFiches}{%d}" % par_page]
    for ex in exos:
        emettre_bande(L, s, ex)
    L.append(r"\end{seqPlancheFiches}")
    if version == "corrigee":
        emettre_corriges_rediges(L, s, exos)
    return L


def _echapper(t: str) -> str:
    """Texte simple (intitulés) dans un tableau : & % # _ échappés."""
    return re.sub(r"(?<!\\)([&%#_])", r"\\\1", t or "")


def corps_plan(conn, s: dict) -> list[str]:
    """MR5 — plan de séquence pour l'enseignant : objectifs (critères,
    séances), séances (objectif, exercice), tests courts, contrôle MR6."""
    v = valider_sequence_mer(conn, s["niveau"], s["code"], s)
    L = [_entete(s, False),
         r"\begin{center}{\Large\bfseries\color{seqSixVert}" + libelle_mer(s["code"])
         + " --- " + s["nom"] + r"}\\[2pt]{\small\itshape\color{seqSixGrisTexte}"
         r"Plan de séquence (enseignant) --- un exercice au début de chaque séance}"
         r"\end{center}",
         r"\seqPartieSix{Objectifs}",
         r"\begin{itemize}"]
    for o in s["objectifs"]:
        L.append(r"\item \textbf{" + o["etiquette"] + "} " + o["nom"]
                 + f" ({_fmt(o['nb_seances'])} séance" + ("s" if o["nb_seances"] > 1 else "")
                 + ")" + (r"\\{\footnotesize F : " + o["critere_F"] + "}"
                          if o["critere_F"] else "")
                 + (r"\\{\footnotesize A : " + o["critere_A"] + "}" if o["critere_A"] else ""))
    L.append(r"\end{itemize}")
    f = s["fiche"]
    L.append(r"\seqPartieSix{Fiche de cours}")
    L.append((r"Au début de la séquence : « " + (f.get("titre") or "") + " », à coller "
              r"dans le cahier.") if f else r"\emph{Pas de fiche de cours.}")
    L.append(r"\seqPartieSix{Séances}")
    if s["exercices"]:
        L.append(r"{\small\begin{longtable}{|r|l|p{0.62\linewidth}|l|}\hline")
        L.append(r"\textbf{Séance} & \textbf{Objectif} & \textbf{Exercice} & \textbf{Code}"
                 r"\\\hline\endhead")
        for ex in s["exercices"]:
            L.append(f"{ex.get('seance') or ''} & {ex.get('objectif') or '?'} & "
                     + _echapper(ex.get("titre") or "") + f" & {ex['code']}" + r"\\\hline")
        L.append(r"\end{longtable}}")
    else:
        L.append(r"\emph{Aucun exercice de séance.}")
    L.append(r"\seqPartieSix{Tests courts sur 10}")
    if s["tests"]:
        L.append(r"\begin{itemize}")
        for t in s["tests"]:
            L.append(r"\item " + _echapper(t["titre"]) + f" (évaluation n\\textsuperscript{{o}} "
                     f"{t['numero']})")
        L.append(r"\end{itemize}")
    else:
        L.append(r"\emph{Aucun test court.}")
    if v["erreurs"] or v["avertissements"]:
        L.append(r"\seqPartieSix{Contrôle de la séquence}")
        L.append(r"\begin{itemize}")
        for e in v["erreurs"]:
            L.append(r"\item {\color{seqSixRouge}À compléter : " + _echapper(e) + "}")
        for a in v["avertissements"]:
            L.append(r"\item Attention : " + _echapper(a))
        L.append(r"\end{itemize}")
    return L


def generer_test_court(conn, niveau: str, sequence: str, options: dict | None = None,
                       tikz_libraries=None, tblr_libraries=None) -> str:
    """Test court n° `test` de la séquence (rendu 6e du module Évaluations :
    sujet A ou B, élève ou corrigé, marqueur calculatrice) ; `exemplaires`
    = 2 : deux sujets par A4 (A5), sauf sujet en deux parties."""
    from services import render_evaluation as rev
    from services.livret_sequence_6e import document
    o = options_mer(options)
    s = lire_sequence_mer(conn, niveau, sequence)
    if not s["tests"]:
        raise MiseEnRouteErreur(f"{sequence} : aucun test court.")
    if o["test"] > len(s["tests"]):
        raise MiseEnRouteErreur(f"{sequence} : test {o['test']} demandé, "
                                f"{len(s['tests'])} test(s) court(s).")
    ev_id = s["tests"][o["test"] - 1]["id"]
    opts_ev = {"sujet": o["sujet"], "version": o["version"]}
    if o["exemplaires"] == 1:
        return rev.generer_tex_evaluation_6e(conn, ev_id, opts_ev, tikz_libraries,
                                             tblr_libraries)
    opts = rev.options_evaluation_6e(opts_ev)
    from services.marqueurs_exercices import calculatrice_evaluation
    opts["calculatrice"] = calculatrice_evaluation(conn, ev_id)["valeur"]
    st = rev.structure_evaluation_6e(conn, ev_id)
    decoupage = rev.parties_evaluation_6e(conn, ev_id, st)
    corps = rev.corps_evaluation_6e(conn, st, opts, decoupage)
    if decoupage is None:
        corps = [corps[0], *_copies(corps[1:], o["exemplaires"])]
    return document(conn, niveau, f"Test court 6e — {st['titre']} — sujet {o['sujet']}",
                    corps, o["version"] == "corrigee", tikz_libraries, tblr_libraries)


PREAMBULE_MER = (r"\usepackage{longtable}",)


def generer_document_mer(conn: sqlite3.Connection, niveau: str, sequence: str,
                         options: dict | None = None, tikz_libraries=None,
                         tblr_libraries=None) -> str:
    """MR5 — .tex d'un document de la séquence de mise en route (option
    `document` : fiche_cours | planche | test_court | plan)."""
    from services.livret_sequence_6e import document
    o = options_mer(options)
    if o["document"] == "test_court":
        return generer_test_court(conn, niveau, sequence, o, tikz_libraries, tblr_libraries)
    s = lire_sequence_mer(conn, niveau, sequence)
    corrige = o["version"] == "corrigee"
    titre = f"{LIBELLES_DOCUMENTS_MER[o['document']]} — {sequence} — {s['nom']}"
    if o["document"] == "fiche_cours":
        # La version complète est posée par \seqVersionComplete dans le corps.
        return document(conn, niveau, titre, corps_fiche_cours(s, o["version"],
                                                               o["exemplaires"]),
                        False, tikz_libraries, tblr_libraries)
    if o["document"] == "planche":
        titre += f" — {o['par_page']} par A4"
        return document(conn, niveau, titre, corps_planche(s, o["par_page"], o["version"]),
                        corrige, tikz_libraries, tblr_libraries)
    return document(conn, niveau, titre, corps_plan(conn, s), False, tikz_libraries,
                    tblr_libraries, preambule_sup=PREAMBULE_MER)
