r"""services/plan_travail_6e.py — v0.52.3

Plan de travail d'une séquence de 6e, au format de l'équipe de 6e (modèles
« 6- S2- Plan de travail 2026 (final) » et « 6- S6- Plan de travail 2026 »),
que Laurent a validé de garder (retour v0.52.3 : l'atelier produisait le
plan de travail du cycle 4 pour la 6e).

Forme (inventaire col6/inv/num_forme.md, « Plans de travail 2026 ») :

    titre vert souligné (nom de la séquence)
    sous-titre bleu : Séquence n — durée — livret ; légende O / ( ) / [ ]
    > S01-02 : objectif                       (gras italique souligné)
    > Activité n : titre                       (bleu gras)
        >> à retenir n : titre de la fiche     (rouge souligné)
        [encadré rouge : fiche de résumé, version complète]
        exercices 1 - 2 - ( 3 - 4 ) - [ 5 ]
    > Travail personnel n°1 : …                (bleu gras)
    > Synthèse et évaluation                   (cours, évaluation, ramassage)

Le contenu vient de l'atelier (même lecture que le livret 6e :
livret_sequence_6e.lire_sequence_6e) ; les numéros des activités et des
exercices sont ceux du livret 6e (livret_sequence_6e.numeros_livret, relevés
pendant l'émission du livret, avec les options du livret publié).

Décisions (doc/redemarrage_v0_52_3.md) :

  - P1 Gabarit : route de l'atelier (/api/plans-de-travail/…) : paramètre
    `gabarit`, sinon règle R1 (gabarit_atelier_du_niveau) ; `sixieme` → ce
    plan, `cycle4` → plan historique inchangé. Catalogue `sixieme` : type
    `plans_travail_6e`, une cible par séquence.
  - P2 Étiquette d'un objectif : `S01-02`, celle du bandeau du livret 6e et
    du barème des évaluations (l'équipe écrit « C1 », numéro propre au plan).
  - P3 Marques : sans marque = F (obligatoire, O) ; ( … ) = A
    (approfondissement) ; [ … ] = remédiation (répétition, R) ; { … } = E
    (expertise, absente des plans de l'équipe ; légende complétée seulement
    si la séquence en a). Activités d'une partie sans objectif : avant le
    premier objectif de la partie, comme dans le livret.
  - P4 Documents TP, AC, AT : placés après le **dernier** objectif auquel
    ils sont reliés (objectif_exos), là où l'équipe les place (après les
    compétences qu'ils mobilisent) ; sans objectif : « Synthèse et
    évaluation ». Évaluations de la séquence (structure_evaluation_6e) :
    barème par compétence, total, bonus.
  - P5 Ce qui n'a pas de donnée en base n'est pas inventé : référence du
    manuel, pages du livret (« livret p x »), nombre de pages du livret,
    déroulé détaillé des activités (sous-puces), durée quand les séances
    ne sont pas renseignées. Option `fiches` : `texte_complet` (encadré,
    comme le modèle, défaut) | `titre`.
"""

from __future__ import annotations

import re
import sqlite3

from services import marqueurs_exercices as _mq
from services.livret_sequence_6e import (
    Livret6eErreur, document, latex_fiche, lire_sequence_6e, normaliser_options,
    numeros_livret, options_livret,
)

FICHES_PLAN = ("texte_complet", "titre")
LIBELLES_DOCS = {"TP": "Travail personnel", "AC": "Activité complémentaire",
                 "AT": "Atelier"}
MARQUES = {"O": ("", ""), "A": ("( ", " )"), "R": ("[ ", " ]"), "E": (r"\{ ", r" \}")}

# Soulignement qui passe à la ligne (ulem n'est pas dans toutes les
# distributions) : chaque mot est souligné, les espaces aussi (leaders).
PREAMBULE_PLAN = (
    r"\newcommand{\seqPlanMot}[1]{\underline{\vphantom{(gpqy}#1}}",
    r"\newcommand{\seqPlanEsp}{\leaders\hbox{\underline{\vphantom{(gpqy}\hspace{0.2pt}}}"
    r"\hskip 0.33em plus 0.15em minus 0.1em\relax}",
)


class PlanTravail6eErreur(ValueError):
    pass


def options_par_defaut() -> dict:
    return {"fiches": "texte_complet"}


def normaliser(options: dict | None) -> dict:
    o = options_par_defaut()
    if (options or {}).get("fiches"):
        o["fiches"] = options["fiches"]
    if o["fiches"] not in FICHES_PLAN:
        raise PlanTravail6eErreur(f"fiches invalide : {o['fiches']!r}")
    return o


# ── Soulignement ─────────────────────────────────────────────────────────────

def _mots(texte: str) -> list[str]:
    """Découpe aux espaces de premier niveau (hors accolades et hors $…$),
    pour ne jamais couper une formule ni un argument de macro."""
    mots, cour, prof, maths, i = [], "", 0, False, 0
    while i < len(texte):
        ch = texte[i]
        if ch == "\\" and i + 1 < len(texte):
            cour += texte[i:i + 2]
            i += 2
            continue
        if ch == "{":
            prof += 1
        elif ch == "}":
            prof = max(0, prof - 1)
        elif ch == "$":
            maths = not maths
        if ch.isspace() and prof == 0 and not maths:
            if cour:
                mots.append(cour)
            cour = ""
        else:
            cour += ch
        i += 1
    if cour:
        mots.append(cour)
    return mots


def souligner(texte: str) -> str:
    return r"\seqPlanEsp ".join(r"\seqPlanMot{" + m + "}" for m in _mots(texte or ""))


# ── Lecture ──────────────────────────────────────────────────────────────────

def _objectifs_ids(conn, niveau: str, sequence: str) -> dict[str, str]:
    """code d'objectif → id (séquence-niveau donnée)."""
    return {r[1]: r[0] for r in conn.execute(
        "SELECT o.id, o.code FROM objectifs o "
        "JOIN sequence_parties p ON p.id = o.partie_id "
        "JOIN sequences_par_niveau s ON s.id = p.sequence_par_niveau_id "
        "WHERE s.niveau = ? AND s.sequence_code = ?", (niveau, sequence))}


def _documents(conn, niveau: str, sequence: str) -> list[dict]:
    """Atomes TP, AC, AT de la séquence avec les codes des objectifs reliés
    (et leurs marqueurs, v0.52.7)."""
    docs = []
    for r in conn.execute("SELECT id, serie_code, num, titre" + _mq.sql_colonnes(conn)
                          + " FROM exercices WHERE niveau = ? "
                          "AND sequence = ? AND serie_code IN ('TP', 'AC', 'AT') "
                          "ORDER BY serie_code DESC, num, id", (niveau, sequence)):
        codes = [x[0] for x in conn.execute(
            "SELECT o.code FROM objectif_exos oe JOIN objectifs o ON o.id = oe.objectif_id "
            "WHERE oe.exercice_id = ?", (r[0],))]
        docs.append({"id": r[0], "serie": r[1], "num": r[2], "titre": r[3] or "",
                     "objectifs": codes, "ordinateur": r[4] or "", "calculatrice": r[5] or ""})
    return docs


def _evaluations(conn, niveau: str, sequence: str) -> list[dict]:
    from services.render_evaluation import structure_evaluation_6e
    sortie = []
    for (eid,) in conn.execute("SELECT id FROM evaluations WHERE niveau = ? "
                               "ORDER BY ordre, numero, id", (niveau,)).fetchall():
        try:
            st = structure_evaluation_6e(conn, eid)
        except Exception:
            continue
        if st["sequence"] == sequence and st["exercices"]:
            st["sujet_b"] = any((x[0] or "").strip() for x in conn.execute(
                "SELECT e.remed_enonce FROM evaluation_exercices ee JOIN exercices e "
                "ON e.id = ee.exercice_id WHERE ee.evaluation_id = ?", (eid,)))
            # v0.52.7 — marquage de l'évaluation : celui de ses exercices EV
            # (l'import le pose sur chacun depuis l'entrée d'évaluation).
            st["marqueurs"] = _mq.combiner([dict(x) for x in conn.execute(
                "SELECT '' AS _" + _mq.sql_colonnes(conn, "e") + " FROM evaluation_exercices ee "
                "JOIN exercices e ON e.id = ee.exercice_id WHERE ee.evaluation_id = ?", (eid,))])
            sortie.append(st)
    return sortie


def _duree(conn, niveau: str, sequence: str) -> float:
    r = conn.execute(
        "SELECT COALESCE((SELECT SUM(COALESCE(p.nb_seances_R_AE, 0)) FROM sequence_parties p "
        "  JOIN sequences_par_niveau s ON s.id = p.sequence_par_niveau_id "
        "  WHERE s.niveau = ? AND s.sequence_code = ?), 0) + "
        "COALESCE((SELECT SUM(COALESCE(o.nb_seances, 0)) FROM objectifs o "
        "  JOIN sequence_parties p ON p.id = o.partie_id "
        "  JOIN sequences_par_niveau s ON s.id = p.sequence_par_niveau_id "
        "  WHERE s.niveau = ? AND s.sequence_code = ?), 0)",
        (niveau, sequence, niveau, sequence)).fetchone()
    return float(r[0] or 0)


# ── Rendu ────────────────────────────────────────────────────────────────────

def _fmt(x: float) -> str:
    return str(int(x)) if x == int(x) else f"{x:g}".replace(".", ",")


def ligne_exercices(jetons: list[tuple]) -> str:
    """[('O',1),('O',2),('A',3),('A',4),('R',5)] → '1 - 2 - ( 3 - 4 ) - [ 5 ]'
    (P3 : marques regroupées par suites de même nature).

    v0.52.7 — Un jeton peut porter une mention en 3e position
    (« ordinateur~: Scratch ») : '1 - 2 {\\small (ordinateur~: Scratch)} - 3'."""
    groupes: list[tuple[str, list]] = []
    for jeton in jetons:
        nature, n = jeton[0], jeton[1]
        if len(jeton) > 2 and jeton[2]:
            n = f"{n} {{\\small ({jeton[2]})}}"
        if nature == "O" or not groupes or groupes[-1][0] != nature:
            groupes.append((nature, [n]))
        else:
            groupes[-1][1].append(n)
    morceaux = []
    for nature, ns in groupes:
        a, b = MARQUES[nature]
        morceaux.append(a + " - ".join(str(n) for n in ns) + b)
    return " - ".join(morceaux)


def _jetons_objectif(o: dict, N, materiel: "_mq.Materiel | None" = None,
                     etiquette: str = "") -> list[tuple]:
    """Jetons de la ligne « exercices » ; v0.52.7 : mention des marqueurs sur
    l'exercice principal (pas sur sa remédiation, qui suit le même marquage,
    M1), et l'exercice noté pour l'encadré « Matériel à prévoir »."""
    jetons = []
    for serie, nature in (("F", "O"), ("A", "A"), ("E", "E")):
        for ex in o["series"].get(serie) or []:
            n = N.exercices.get(ex["id"])
            if n is None:
                continue                          # hors livret (série E exclue…)
            mention = _mq.mention_texte(ex)
            jetons.append((nature, n, mention) if mention else (nature, n))
            if mention and materiel is not None:
                materiel.noter(f"exercice {n}" + (f" ({etiquette})" if etiquette else ""), ex)
            r = N.remediations.get(ex["id"])
            if r is not None:
                jetons.append(("R", r))
    return jetons


def _titre_doc(d: dict) -> str:
    lib = LIBELLES_DOCS[d["serie"]]
    titre = d["titre"].replace("---", ":").strip()
    if titre.lower().startswith(("travail personnel", "atelier", "activité complémentaire")):
        return titre
    num = f" n°{int(d['num'])}" if d["num"] else ""
    return f"{lib}{num} : {titre}" if titre else f"{lib}{num}"


def _puce(texte: str, retrait: bool = False) -> str:
    return ((r"\hspace*{2em}" if retrait else "") + r"\textgreater{} " + texte)


def encadre_materiel(materiel: "_mq.Materiel") -> list[str]:
    r"""v0.52.7 (M8) — Encadré « Matériel à prévoir » : une ligne par outil
    (ordinateur --- Scratch…), puis la calculatrice autorisée, avec les
    exercices concernés. Noir et gris : lisible photocopié."""
    L = [r"\begin{tcolorbox}[enhanced, colback=white, colframe=black!60, boxrule=0.6pt,"
         r" sharp corners, left=4pt, right=4pt, top=2pt, bottom=2pt,"
         r" title={Matériel à prévoir}, coltitle=black, colbacktitle=black!10,"
         r" fonttitle=\bfseries\small]", r"\small"]
    for titre, libelles in materiel.lignes():
        L.append(r"\textbf{" + titre + "} : " + " ; ".join(libelles) + r"\par")
    L.append(r"\end{tcolorbox}")
    return L


def corps_plan(seq: dict, N, docs: list[dict], evals: list[dict], duree: float,
               opts: dict) -> list[str]:
    a_E = any(x["id"] in N.exercices for p in seq["parties"] for o in p["objectifs"]
              for x in (o["series"].get("E") or []))
    legende = (r"exercices sans marque : obligatoires (O) --- ( \ldots{} ) : approfondissement (A)"
               r" --- [ \ldots{} ] : répétition (R)"
               + (r" --- \{ \ldots{} \} : expertise (E)" if a_E else ""))
    sous_titre = " --- ".join(x for x in (
        f"Séquence {seq['numero']}" if seq.get("numero") else "",
        f"{_fmt(duree)} séances" if duree else "",
        r"Livret de séquence \seqNiveauCourt") if x)      # v0.52.4 (T1)
    L = [r"\begin{center}{\Large\bfseries\color{seqSixVert}" + souligner(seq["nom"]) + r"}\\[3pt]",
         r"{\small\color{seqSixBleu}" + sous_titre + r"\\" + legende + "}",
         r"\end{center}", r"\setlength{\parskip}{4pt}"]
    # P4 — dernier objectif relié (ordre du livret) de chaque document.
    ordre = [o["code"] for p in seq["parties"] for o in p["objectifs"]]
    apres: dict[str, list[dict]] = {}
    sans_objectif = []
    for d in docs:
        codes = [c for c in ordre if c in d["objectifs"]]
        if codes:
            apres.setdefault(codes[-1], []).append(d)
        else:
            sans_objectif.append(d)
    n_retenir = 0
    fiches_cours = 0
    materiel = _mq.Materiel()                     # v0.52.7 (M8)

    def activite(ex):
        n = N.activites.get(ex["id"])
        lib = f"Activité {n}" if n else "Activité"
        mention = _mq.mention_texte(ex)
        if mention:
            materiel.noter(lib.lower() if n else f"activité {ex['code']}", ex)
        L.append(r"\noindent{\color{seqSixBleu}\bfseries " + _puce(lib + " : " + (ex.get("titre") or "")) + "}"
                 + (r" {\small (" + mention + ")}" if mention else "")
                 + r"\hfill{\scriptsize\color{seqSixGrisTexte}" + ex["code"] + "}\\par")

    def fiche(f):
        nonlocal n_retenir, fiches_cours
        n_retenir += 1
        fiches_cours += 1
        L.append(r"\noindent\hspace*{2em}{\color{seqSixRouge}\bfseries\textgreater\textgreater{} "
                 r"\underline{à retenir " + str(n_retenir) + "}} : " + (f.get("titre") or "") + r"\par")
        if opts["fiches"] == "texte_complet":
            L.append(r"\begin{tcolorbox}[enhanced, breakable, colback=white, colframe=seqSixRouge,"
                     r" boxrule=1pt, sharp corners, left=3pt, right=3pt, top=2pt, bottom=2pt]")
            L.append(latex_fiche(f))
            L.append(r"\end{tcolorbox}")

    for p in seq["parties"]:
        for ex in p["activites"]:
            activite(ex)
        for f in p["fiches"]:
            fiche(f)
        for o in p["objectifs"]:
            L.append(r"\medskip\noindent{\bfseries\itshape "
                     + souligner(r"\textgreater{} " + f"{seq['code']}-{o['code']} : {o['nom']}")
                     + r"}\par")
            for ex in o["activites"]:
                activite(ex)
            for f in o["fiches"]:
                fiche(f)
            jetons = _jetons_objectif(o, N, materiel, f"{seq['code']}-{o['code']}")
            if jetons:
                L.append(r"\noindent\hspace*{2em}exercices " + ligne_exercices(jetons) + r"\par")
            for d in apres.get(o["code"], []):
                mention = _mq.mention_texte(d)
                L.append(r"\noindent{\color{seqSixBleu}\bfseries " + _puce(_titre_doc(d)) + "}"
                         + (r" {\small (à la maison)}" if d["serie"] == "TP" else "")
                         + (r" {\small (" + mention + ")}" if mention else "") + r"\par")
    # Synthèse et évaluation
    synthese = []
    if fiches_cours:
        synthese.append(r"cours : fiches de cours «~" + seq["nom"] + r"~» (fiches de résumé "
                        r"en version complète)")
    for d in sans_objectif:
        mention = _mq.mention_texte(d)
        synthese.append(_titre_doc(d) + (r" {\small (" + mention + ")}" if mention else ""))
    for st in evals:
        colonnes = [f"{o['etiquette']} /{_fmt(o['points'])}" for o in st["objectifs"]]
        if st["bonus"]:
            colonnes.append(f"bonus /{_fmt(st['bonus'])}")
        synthese.append(r"évaluation «~" + st["titre"].replace("---", ":") + r"~» : "
                        + ("sujets A et B" if st["sujet_b"] else "sujet A")
                        + (" --- " + ", ".join(colonnes) if colonnes else "")
                        + f" --- total /{_fmt(st['total'])}"
                        + (r" {\small (" + _mq.mention_texte(st["marqueurs"]) + ")}"
                           if _mq.mention_texte(st.get("marqueurs") or {}) else ""))
    tps = [d for d in docs if d["serie"] == "TP"]
    if tps:
        nums = [f"n°{int(d['num'])}" for d in tps if d["num"]]
        synthese.append("ramassage et correction des travaux personnels"
                        + (" " + " et ".join([", ".join(nums[:-1]), nums[-1]] if len(nums) > 1
                                             else nums) if nums else ""))
    # v0.52.7 (M8) — Documents marqués (TP, AC, AT, évaluations) dans
    # l'encadré « Matériel à prévoir », placé en tête du plan.
    for d in docs:
        if _mq.mention_texte(d):
            materiel.noter(_titre_doc(d).split(" : ")[0].lower()
                           if d["num"] else _titre_doc(d), d)
    for st in evals:
        if _mq.mention_texte(st.get("marqueurs") or {}):
            materiel.noter(r"évaluation «~" + st["titre"].replace("---", ":") + r"~»",
                           st["marqueurs"])
    if materiel:
        L[4:4] = encadre_materiel(materiel)
    if synthese:
        L.append(r"\medskip\noindent{\bfseries\itshape "
                 + souligner(r"\textgreater{} Synthèse et évaluation") + r"}\par")
        for s in synthese:
            L.append(r"\noindent" + _puce(s, retrait=True) + r"\par")
    return L


# ── API publique ─────────────────────────────────────────────────────────────

def generer_plan_travail_6e(conn: sqlite3.Connection, niveau: str, sequence_code: str,
                            options: dict | None = None, tikz_libraries=None,
                            tblr_libraries=None, referentiel_id: str | None = None) -> str:
    """Plan de travail 6e d'une séquence (option `fiches`)."""
    opts = normaliser(options)
    seq = lire_sequence_6e(conn, niveau, sequence_code)
    if not seq["parties"]:
        raise Livret6eErreur(f"{niveau}/{sequence_code} : aucune partie assemblée.")
    N = numeros_livret(seq, normaliser_options(options_livret(conn, niveau, referentiel_id)))
    corps = corps_plan(seq, N, _documents(conn, niveau, sequence_code),
                       _evaluations(conn, niveau, sequence_code),
                       _duree(conn, niveau, sequence_code), opts)
    if opts["fiches"] == "texte_complet":
        corps.insert(0, r"\seqVersionComplete")
    return document(conn, niveau, f"Plan de travail 6e — {sequence_code} — {seq['nom']}",
                    corps, False, tikz_libraries, tblr_libraries,
                    preambule_sup=PREAMBULE_PLAN)
