r"""services/progression_rituels.py — v0.60.0

Document de rituels / planches d'automatismes organisé selon la progression
(décision du 16 novembre, `col4/DECISIONS_CYCLE4.md` point 10) et séances
d'évaluation dans la progression (besoin E8), d'après un **ordre des parties
saisi par l'enseignant** (`doc/redemarrage_v0_60_0.md`).

Audit (décision P0) : l'atelier n'a aucune progression ordonnée. Les
progressions vivent côté classe (`progressions`, `creneaux` : un passage par
séquence, des dates, sans partie ni semaine) et les séances par partie du
référentiel (`objectifs.nb_seances`, `referentiel_parties_seances`) donnent
des durées, pas un ordre. Référentiel et progression sont disjoints (l'ordre
de l'année ne se décide pas dans le référentiel) : le document est donc
calculé à partir d'une **liste ordonnée des parties** rattachée au
référentiel, saisie dans l'atelier (une partie par ligne, « A1-P1 », nombre
de semaines facultatif), et non rangé dans le catalogue des documents du
référentiel (il ne change ni sa validation ni sa publication).

Décisions :

  - **P1 Semaines** — une partie dure le nombre de semaines saisi, sinon
    ⌈séances de la partie / 3⌉ (3 séances d'apprentissage par semaine, jamais
    de demi-semaine), au moins 1. Les parties s'enchaînent sans trou à partir
    de la semaine 1 ; l'année compte 30 semaines (réglable).
  - **P2 Cartes nouvelles** — cartes rattachées aux objectifs de la partie
    dont le niveau de création est le niveau du référentiel (ou vide) :
    rituel la semaine qui suit la fin de la partie.
  - **P3 Rappels espacés** — 1 semaine (J+7) et 4 semaines (J+30) après le
    rituel, puis toutes les 6 semaines jusqu'à la dernière semaine (juin).
  - **P4 Réactivation** — cartes de la partie créées à un niveau inférieur
    (l'année d'avant) : rappelées la première semaine de la partie, puis
    même cycle de rappels. Une carte rattachée à plusieurs parties ne
    compte qu'une fois, à la première partie de l'ordre.
  - **P5 Séances d'évaluation** (E8) — une toutes les deux semaines (semaines
    2, 4, 6…), sur un jour fixe (affiché) ; l'évaluation d'une partie va dans
    la première séance d'évaluation qui suit d'au moins une semaine la fin de
    la partie (semaine de fin + 1 au plus tôt) ; 50 min et 5 objectifs au
    plus par séance (durée de l'évaluation : `evaluations_v2`, 10 min par
    objectif), sinon séance suivante. Les tests courts ne sont pas placés.
  - **P6 Dernière séquence non évaluée** — règle de progression (jamais de
    référentiel) : les évaluations de la séquence de la dernière partie de
    l'ordre ne sont pas placées (réglable).
  - **P7 Cartes validées seulement** dans le document (règle des planches et
    du récap) ; les cartes non validées sont comptées dans les
    avertissements.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from datetime import datetime, timezone

DDL = """
CREATE TABLE IF NOT EXISTS progression_rituels (
    referentiel_id TEXT PRIMARY KEY,
    ordre          TEXT NOT NULL DEFAULT '[]',
    parametres     TEXT NOT NULL DEFAULT '{}',
    mtime          TEXT NOT NULL DEFAULT ''
)"""

PARAMETRES_DEFAUT = {
    "semaines_annee": 30,          # P1
    "seances_par_semaine": 3,      # P1 (séances d'apprentissage)
    "rappels": [1, 4],             # P3 (semaines après le rituel)
    "periode_rappels": 6,          # P3
    "premiere_semaine_evaluation": 2,   # P5
    "intervalle_evaluations": 2,        # P5
    "jour_evaluation": "vendredi",      # P5 (affiché)
    "delai_evaluation": 1,              # P5 (semaines après la fin de la partie)
    "seance_evaluation_minutes": 50,    # E7
    "seance_evaluation_objectifs": 5,   # E7
    "derniere_sequence_non_evaluee": True,  # P6
    "cartes_document": "nouvelles",     # aucune | nouvelles | toutes
}

RE_LIGNE = re.compile(r"^\s*([A-Z]\d{1,2})\s*-\s*P?\s*(\d+)\s*(?:[:;,]?\s*(\d+)\s*(?:sem\w*)?)?\s*$",
                      re.IGNORECASE)


class ProgressionErreur(ValueError):
    def __init__(self, message: str, erreurs: list | None = None):
        super().__init__(message)
        self.erreurs = erreurs or [message]


# ── Schéma ──────────────────────────────────────────────────────────────────

def migrer(conn) -> list[str]:
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                    "name='progression_rituels'").fetchone():
        return []
    conn.execute(DDL)
    return ["progression_rituels"]


def _ref(conn, ref_id: str) -> dict:
    r = conn.execute("SELECT id, niveau FROM referentiel_niveaux WHERE id = ?",
                     (ref_id,)).fetchone()
    if r is None:
        raise ProgressionErreur(f"Référentiel introuvable : {ref_id}")
    return {"id": r[0], "niveau": r[1]}


# ── Parties du référentiel ──────────────────────────────────────────────────

def parties_du_referentiel(conn, ref_id: str) -> list[dict]:
    """Parties du principal du niveau du référentiel, dans l'ordre du cycle :
    [{code « A1-P1 », sequence, numero, libelle, seances, partie_id}]."""
    from services.referentiels_internes import sequences_du_perimetre
    niveau = _ref(conn, ref_id)["niveau"]
    out = []
    for s in sequences_du_perimetre(conn, niveau, "principal"):
        for p in conn.execute("SELECT id, numero, COALESCE(libelle, '') FROM sequence_parties "
                              "WHERE sequence_par_niveau_id = ? ORDER BY numero",
                              (s["sn_id"],)).fetchall():
            seances = conn.execute("SELECT COALESCE(SUM(nb_seances), 0) FROM objectifs WHERE "
                                   "partie_id = ?", (p[0],)).fetchone()[0] or 0
            out.append({"code": f"{s['code']}-P{p[1]}", "sequence": s["code"],
                        "numero": p[1], "libelle": p[2], "seances": float(seances),
                        "partie_id": p[0]})
    return out


# ── Ordre saisi ─────────────────────────────────────────────────────────────

def analyser_saisie(texte: str, parties: list[dict]) -> dict:
    """Texte (une partie par ligne : « A1-P1 », « A1-P1 2 » pour 2 semaines ;
    « # » commente) → {ordre: [{partie, semaines}], erreurs, avertissements}.
    Parties inconnues ou en double : erreurs ; parties non placées :
    avertissement."""
    connues = {p["code"]: p for p in parties}
    ordre, erreurs, vus = [], [], set()
    for k, brute in enumerate((texte or "").splitlines(), start=1):
        ligne = brute.split("#", 1)[0].strip()
        if not ligne:
            continue
        m = RE_LIGNE.match(ligne)
        if not m:
            erreurs.append(f"ligne {k} : « {ligne} » illisible (attendu A1-P1, ou A1-P1 2)")
            continue
        code = f"{m.group(1).upper()}-P{int(m.group(2))}"
        if code not in connues:
            erreurs.append(f"ligne {k} : partie {code} absente du référentiel")
            continue
        if code in vus:
            erreurs.append(f"ligne {k} : partie {code} en double")
            continue
        vus.add(code)
        sem = int(m.group(3)) if m.group(3) else None
        if sem is not None and not 1 <= sem <= 20:
            erreurs.append(f"ligne {k} : {sem} semaines pour {code} (1 à 20)")
            continue
        ordre.append({"partie": code, "semaines": sem})
    manquantes = [p["code"] for p in parties if p["code"] not in vus]
    avert = ([f"parties non placées : {', '.join(manquantes)}"] if manquantes and ordre else [])
    return {"ordre": ordre, "erreurs": erreurs, "avertissements": avert}


def texte_saisie(ordre: list[dict]) -> str:
    return "\n".join(o["partie"] + (f" {o['semaines']}" if o.get("semaines") else "")
                     for o in ordre)


def lire(conn, ref_id: str) -> dict:
    """{referentiel_id, ordre, texte, parametres, mtime, parties}."""
    migrer(conn)
    _ref(conn, ref_id)
    r = conn.execute("SELECT ordre, parametres, mtime FROM progression_rituels WHERE "
                     "referentiel_id = ?", (ref_id,)).fetchone()
    ordre = json.loads(r[0]) if r else []
    params = dict(PARAMETRES_DEFAUT)
    if r:
        params.update(json.loads(r[1] or "{}"))
    return {"referentiel_id": ref_id, "ordre": ordre, "texte": texte_saisie(ordre),
            "parametres": params, "mtime": r[2] if r else "",
            "parties": [{k: p[k] for k in ("code", "libelle", "seances")}
                        for p in parties_du_referentiel(conn, ref_id)]}


def _valider_parametres(p: dict) -> dict:
    out = {}
    for k, v in (p or {}).items():
        if k not in PARAMETRES_DEFAUT:
            raise ProgressionErreur(f"paramètre inconnu : {k}")
        d = PARAMETRES_DEFAUT[k]
        if isinstance(d, bool):
            out[k] = bool(v)
        elif isinstance(d, int):
            try:
                n = int(v)
            except (TypeError, ValueError):
                raise ProgressionErreur(f"{k} : entier attendu ({v!r})") from None
            if not 1 <= n <= 60:
                raise ProgressionErreur(f"{k} : {n} hors de 1 à 60")
            out[k] = n
        elif isinstance(d, list):
            try:
                lst = sorted({int(x) for x in v})
            except (TypeError, ValueError):
                raise ProgressionErreur(f"{k} : liste d'entiers attendue") from None
            if not lst or lst[0] < 1:
                raise ProgressionErreur(f"{k} : entiers ≥ 1 attendus")
            out[k] = lst
        else:
            v = str(v or "").strip()
            if k == "cartes_document" and v not in ("aucune", "nouvelles", "toutes"):
                raise ProgressionErreur(f"{k} : aucune, nouvelles ou toutes")
            out[k] = v
    return out


def enregistrer(conn, ref_id: str, texte: str | None = None, ordre: list | None = None,
                parametres: dict | None = None) -> dict:
    """Enregistre l'ordre (texte saisi ou liste) et les paramètres ;
    ProgressionErreur (avec la liste des erreurs) si la saisie est fausse :
    rien n'est écrit."""
    migrer(conn)
    parties = parties_du_referentiel(conn, ref_id)
    if texte is not None:
        res = analyser_saisie(texte, parties)
    else:
        res = analyser_saisie(texte_saisie(ordre or []), parties)
    if res["erreurs"]:
        raise ProgressionErreur("Ordre des parties invalide", res["erreurs"])
    actuel = lire(conn, ref_id)
    params = {k: v for k, v in actuel["parametres"].items() if PARAMETRES_DEFAUT.get(k) != v}
    params.update(_valider_parametres(parametres or {}))
    maintenant = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO progression_rituels (referentiel_id, ordre, parametres, mtime) "
                 "VALUES (?,?,?,?) ON CONFLICT(referentiel_id) DO UPDATE SET "
                 "ordre = excluded.ordre, parametres = excluded.parametres, "
                 "mtime = excluded.mtime",
                 (ref_id, json.dumps(res["ordre"], ensure_ascii=False),
                  json.dumps(params, ensure_ascii=False), maintenant))
    out = lire(conn, ref_id)
    out["avertissements"] = res["avertissements"]
    return out


# ── Cartes et évaluations des parties ───────────────────────────────────────

def _rang_niveau(code: str) -> int:
    try:
        return int((code or "").lstrip("N"))
    except ValueError:
        return 0


def cartes_de_partie(conn, partie_id: str) -> list[dict]:
    """Cartes rattachées (objectif_cartes) aux objectifs de la partie, dans
    l'ordre des objectifs et des liens."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                        "name='objectif_cartes'").fetchone():
        return []
    cols = {r[1] for r in conn.execute("PRAGMA table_info(cartes_automatisme)")}
    nc = "c.niveau_creation" if "niveau_creation" in cols else "''"
    out, vus = [], set()
    for r in conn.execute(
            "SELECT c.id, c.niveau, c.sequence, c.num, c.titre, c.etat_code, "
            f"{nc}, o.code FROM objectif_cartes oc JOIN cartes_automatisme c "
            "ON c.id = oc.carte_id JOIN objectifs o ON o.id = oc.objectif_id "
            "WHERE o.partie_id = ? ORDER BY o.code, oc.ordre, CAST(c.num AS INTEGER), c.id",
            (partie_id,)):
        if r[0] in vus:
            continue
        vus.add(r[0])
        out.append({"id": r[0], "niveau": r[1], "sequence": r[2], "num": int(r[3] or 0),
                    "titre": r[4] or "", "etat_code": r[5] or "", "niveau_creation": r[6] or "",
                    "objectif": r[7]})
    return out


def evaluations_par_partie(conn, niveau: str) -> dict:
    """{partie_id: [{id, titre, duree, objectifs}]} — évaluations (type
    « évaluation », hors tests courts) du niveau rattachées par leurs
    objectifs ; une évaluation à cheval sur plusieurs parties va à la partie
    de son dernier objectif (ordre des parties dans la séquence)."""
    from services import evaluations_v2 as ev2
    out: dict = {}
    for (eid, titre) in conn.execute("SELECT id, titre FROM evaluations WHERE niveau = ? "
                                     "ORDER BY ordre, numero", (niveau,)).fetchall():
        if ev2.type_evaluation(conn, eid) != "evaluation":
            continue
        parts = conn.execute(
            "SELECT p.id, p.numero, COUNT(*) FROM evaluation_objectifs eo JOIN objectifs o "
            "ON o.id = eo.objectif_id JOIN sequence_parties p ON p.id = o.partie_id "
            "WHERE eo.evaluation_id = ? GROUP BY p.id ORDER BY p.numero", (eid,)).fetchall()
        if not parts:
            continue
        n_obj = sum(x[2] for x in parts)
        duree = ev2.duree_reglee(conn, eid) if ev2.colonnes_presentes(conn) else None
        duree = int(duree) if duree is not None else ev2.duree_auto(conn, eid, "evaluation",
                                                                     n_obj)
        out.setdefault(parts[-1][0], []).append({"id": eid, "titre": titre or "",
                                                 "duree": duree, "objectifs": n_obj})
    return out


# ── Calendrier ──────────────────────────────────────────────────────────────

def _code_carte(c: dict) -> str:
    return f"{c['sequence']}-CA{c['num']:02d}" + (f" ({c['niveau']})" if c.get("autre_niveau")
                                                  else "")


def calendrier(conn, ref_id: str, ordre: list | None = None,
               parametres: dict | None = None) -> dict:
    """Calendrier de la progression : semaines (parties en cours, cartes
    nouvelles, à revoir, réactivées, séance d'évaluation), parties (début,
    fin) et avertissements. `ordre`/`parametres` : ceux enregistrés si
    absents."""
    ref = _ref(conn, ref_id)
    niveau = ref["niveau"]
    enr = lire(conn, ref_id)
    ordre = enr["ordre"] if ordre is None else ordre
    P = dict(enr["parametres"])
    P.update(_valider_parametres(parametres or {}))
    nb_sem = P["semaines_annee"]
    parties = {p["code"]: p for p in parties_du_referentiel(conn, ref_id)}
    avert: list[str] = []
    semaines = {w: {"numero": w, "parties": [], "nouvelles": [], "rappels": [],
                    "reactivation": [], "evaluations": [], "seance_evaluation": False}
                for w in range(1, nb_sem + 1)}
    hors_annee: dict = {"nouvelles": [], "reactivation": [], "evaluations": []}

    # P1 — semaines des parties.
    deroule, w = [], 1
    for o in ordre:
        p = parties.get(o["partie"])
        if p is None:
            avert.append(f"partie {o['partie']} absente du référentiel : ignorée")
            continue
        n = o.get("semaines") or max(1, math.ceil(p["seances"] / P["seances_par_semaine"]))
        d = {**p, "debut": w, "fin": w + n - 1, "semaines": n,
             "semaines_saisies": bool(o.get("semaines"))}
        deroule.append(d)
        for k in range(d["debut"], d["fin"] + 1):
            if k in semaines:
                semaines[k]["parties"].append(p["code"])
        w += n
    if deroule and deroule[-1]["fin"] > nb_sem:
        avert.append(f"la progression dure {deroule[-1]['fin']} semaines, plus que les "
                     f"{nb_sem} semaines de l'année")
    sans_seances = [d["code"] for d in deroule if not d["semaines_saisies"] and not d["seances"]]
    if sans_seances:
        avert.append("parties sans séances dans le référentiel (comptées 1 semaine) : "
                     + ", ".join(sans_seances))

    # P2 à P4 — cartes.
    def rappels(depart: int, carte: dict):
        etapes = list(P["rappels"])
        t = depart + max(etapes) + P["periode_rappels"]
        while t <= nb_sem:
            etapes.append(t - depart)
            t += P["periode_rappels"]
        for k in etapes:
            if depart + k in semaines:
                semaines[depart + k]["rappels"].append(carte)

    vues: set = set()
    non_valides = 0
    for d in deroule:
        for c in cartes_de_partie(conn, d["partie_id"]):
            if c["id"] in vues:
                continue
            vues.add(c["id"])
            if c["etat_code"] != "valide":                         # P7
                non_valides += 1
                continue
            nc = c["niveau_creation"] or c["niveau"]
            c["autre_niveau"] = c["niveau"] != niveau
            c["code"] = _code_carte(c)
            if nc and _rang_niveau(nc) < _rang_niveau(niveau):     # P4
                c["genre"] = "reactivation"
                depart = d["debut"]
            else:                                                  # P2
                c["genre"] = "nouvelle"
                depart = d["fin"] + 1
            cle = "reactivation" if c["genre"] == "reactivation" else "nouvelles"
            if depart in semaines:
                semaines[depart][cle].append(c)
                rappels(depart, c)
            else:
                hors_annee[cle].append(c)
    if non_valides:
        avert.append(f"{non_valides} carte(s) rattachée(s) non validée(s) : absentes du "
                     "document")

    # P5, P6 — séances d'évaluation.
    seances = [w for w in range(P["premiere_semaine_evaluation"], nb_sem + 1,
                                P["intervalle_evaluations"])]
    for w in seances:
        semaines[w]["seance_evaluation"] = True
    charge = {w: {"minutes": 0, "objectifs": 0} for w in seances}
    evals = evaluations_par_partie(conn, niveau)
    derniere_seq = deroule[-1]["sequence"] if deroule else None
    non_evaluees = []
    for d in deroule:
        for ev in evals.get(d["partie_id"], []):
            if P["derniere_sequence_non_evaluee"] and d["sequence"] == derniere_seq:
                non_evaluees.append(ev["titre"])
                continue
            place = None
            for w in seances:
                if w < d["fin"] + P["delai_evaluation"]:
                    continue
                c = charge[w]
                vide = c["minutes"] == 0
                tient = (c["minutes"] + ev["duree"] <= P["seance_evaluation_minutes"]
                         and c["objectifs"] + ev["objectifs"] <= P["seance_evaluation_objectifs"])
                if tient or (vide and (ev["duree"] > P["seance_evaluation_minutes"]
                                       or ev["objectifs"] > P["seance_evaluation_objectifs"])):
                    place = w
                    break
            item = {**ev, "partie": d["code"]}
            if place is None:
                hors_annee["evaluations"].append(item)
                continue
            if ev["duree"] > P["seance_evaluation_minutes"] or \
                    ev["objectifs"] > P["seance_evaluation_objectifs"]:
                avert.append(f"« {ev['titre']} » : {ev['duree']} min, {ev['objectifs']} "
                             f"objectifs — dépasse une séance d'évaluation "
                             f"({P['seance_evaluation_minutes']} min, "
                             f"{P['seance_evaluation_objectifs']} objectifs), seule en semaine "
                             f"{place}")
            charge[place]["minutes"] += ev["duree"]
            charge[place]["objectifs"] += ev["objectifs"]
            semaines[place]["evaluations"].append(item)
    for k in ("nouvelles", "reactivation"):
        if hors_annee[k]:
            avert.append(f"{len(hors_annee[k])} carte(s) {'nouvelle(s)' if k == 'nouvelles' else 'à réactiver'} "
                         "au-delà de la dernière semaine")
    if hors_annee["evaluations"]:
        avert.append("évaluations sans séance avant la fin de l'année : "
                     + ", ".join(f"« {e['titre']} »" for e in hors_annee["evaluations"]))
    for w in seances:
        semaines[w]["charge_evaluation"] = charge[w]
    return {"referentiel_id": ref_id, "niveau": niveau, "parametres": P,
            "parties": [{k: d[k] for k in ("code", "libelle", "seances", "debut", "fin",
                                           "semaines")} for d in deroule],
            "semaines": [semaines[w] for w in sorted(semaines)],
            "seances_evaluation": seances, "non_evaluees": non_evaluees,
            "derniere_sequence": derniere_seq, "hors_annee": hors_annee,
            "avertissements": avert}


# ── Document LaTeX ──────────────────────────────────────────────────────────

def _liste_cartes(cartes: list[dict]) -> str:
    from services.latex_texte import texte_latex
    return ", ".join(rf"\textbf{{{texte_latex(c['code'])}}} {texte_latex(c['titre'])}"
                     for c in cartes)


def generer_tex(conn, ref_id: str, options: dict | None = None) -> str:
    """Document enseignant : calendrier (parties, séances d'évaluation),
    puis une section par semaine (cartes nouvelles, à réactiver, à revoir ;
    évaluations de la séance) et, selon `cartes_document`, la grille des
    cartes de la semaine (recto puis verso, environnement `seqCarteRecap`)."""
    from services.latex_texte import texte_latex
    from services.render_carte_centralise import rendre_ligne_recap
    from services.param_niveaux import LIBELLES_NIVEAUX_LATEX
    cal = calendrier(conn, ref_id, parametres=(options or {}).get("parametres"))
    P = cal["parametres"]
    mode = (options or {}).get("cartes_document") or P["cartes_document"]
    lib = LIBELLES_NIVEAUX_LATEX.get(cal["niveau"], cal["niveau"])
    L = [r"%% Rituels d'automatismes et séances d'évaluation selon la progression (v0.60.0).",
         f"%% Référentiel : {ref_id} — {len(cal['parties'])} partie(s) dans l'ordre saisi.",
         r"\documentclass[10pt]{article}", r"\usepackage[utf8]{inputenc}",
         r"\usepackage[T1]{fontenc}", r"\usepackage[french]{babel}", r"\usepackage{lmodern}",
         r"\usepackage{amsmath}", r"\usepackage{amssymb}", r"\usepackage{xcolor}",
         r"\usepackage{siunitx}", r"\usepackage{seqenseigne-core}",
         r"\usepackage{seqenseigne-theme}", r"\usepackage{seqenseigne-carte-automatisme}",
         r"\setlength{\parindent}{0pt}", r"\pagestyle{empty}", r"\begin{document}",
         r"\seqInitCartes", r"\begin{center}",
         r"{\Huge\bfseries Rituels d'automatismes}\\[1em]",
         rf"{{\Large Classe de {lib} --- selon la progression saisie}}\\[0.5em]",
         rf"{{\large Référentiel {texte_latex(ref_id)} --- "
         rf"{len(cal['parties'])} parties, {P['semaines_annee']} semaines}}",
         r"\end{center}", r"\bigskip"]
    if not cal["parties"]:
        L += [r"\textit{Aucune partie dans l'ordre de la progression : saisir l'ordre des "
              r"parties dans l'atelier.}", r"\end{document}"]
        return "\n".join(L)
    L += [r"\section*{Progression}", r"\begin{tabular}{llll}",
          r"\textbf{Partie} & \textbf{Semaines} & \textbf{Séances} & \textbf{Libellé}\\\hline"]
    for d in cal["parties"]:
        sem = f"{d['debut']}" if d["debut"] == d["fin"] else f"{d['debut']} à {d['fin']}"
        L.append(rf"{d['code']} & {sem} & {d['seances']:g} & {texte_latex(d['libelle'])}\\")
    L.append(r"\end{tabular}")
    L += [r"\par\medskip", rf"Séances d'évaluation : semaines "
          + ", ".join(map(str, cal["seances_evaluation"]))
          + rf" ({texte_latex(P['jour_evaluation'])}, {P['seance_evaluation_minutes']} min et "
          rf"{P['seance_evaluation_objectifs']} objectifs au plus)."]
    if cal["non_evaluees"]:
        L.append(r"\par Non évaluées (dernière séquence de la progression) : "
                 + ", ".join(texte_latex(t) for t in cal["non_evaluees"]) + ".")
    if cal["avertissements"]:
        L += [r"\par\medskip\textbf{À vérifier :}", r"\begin{itemize}"]
        L += [r"\item " + texte_latex(a) for a in cal["avertissements"]]
        L.append(r"\end{itemize}")
    idx = 0
    for s in cal["semaines"]:
        if not (s["parties"] or s["nouvelles"] or s["rappels"] or s["reactivation"]
                or s["evaluations"]):
            continue
        L += [r"\clearpage", rf"\section*{{Semaine {s['numero']}"
              + (r" --- " + ", ".join(s["parties"]) if s["parties"] else "") + "}"]
        if s["nouvelles"]:
            L.append(r"\textbf{Cartes nouvelles (rituel après la partie) :} "
                     + _liste_cartes(s["nouvelles"]) + r"\par")
        if s["reactivation"]:
            L.append(r"\textbf{Réactivation (cartes des années précédentes) :} "
                     + _liste_cartes(s["reactivation"]) + r"\par")
        if s["rappels"]:
            L.append(r"\textbf{À revoir (rappels espacés) :} " + _liste_cartes(s["rappels"])
                     + r"\par")
        if s["seance_evaluation"]:
            if s["evaluations"]:
                ch = s.get("charge_evaluation") or {}
                L.append(rf"\textbf{{Séance d'évaluation ({texte_latex(P['jour_evaluation'])}, "
                         rf"{ch.get('minutes', 0)} min, {ch.get('objectifs', 0)} objectifs) :}} "
                         + " ; ".join(rf"{texte_latex(e['titre'])} ({e['duree']} min)"
                                      for e in s["evaluations"]) + r"\par")
            else:
                L.append(r"\textit{Séance d'évaluation : aucune évaluation à placer.}\par")
        cartes = []
        if mode in ("nouvelles", "toutes"):
            cartes = s["reactivation"] + s["nouvelles"]
        if mode == "toutes":
            cartes = cartes + [c for c in s["rappels"] if c not in cartes]
        for k in range(0, len(cartes), 16):
            bloc = cartes[k:k + 16]
            L.append(r"\begin{seqCarteRecap}")
            for j in range(0, len(bloc), 4):
                L.append("  " + rendre_ligne_recap(conn, _cartes_completes(conn, bloc[j:j + 4]),
                                                   idx_ligne=idx)["appel"])
                idx += 1
            L.append(r"\end{seqCarteRecap}")
    L.append(r"\end{document}")
    return "\n".join(L)


def _cartes_completes(conn, cartes: list[dict]) -> list[dict]:
    """Champs que lit le rendu des cartes (recto, verso, variables…)."""
    out = []
    for c in cartes:
        r = conn.execute("SELECT id, niveau, sequence, num, type_pedago, type_tech, titre, "
                         "recto, verso, variables, ordre FROM cartes_automatisme WHERE id = ?",
                         (c["id"],)).fetchone()
        if r is not None:
            out.append(dict(zip(("id", "niveau", "sequence", "num", "type_pedago",
                                 "type_tech", "titre", "recto", "verso", "variables",
                                 "ordre"), r)))
    return out
