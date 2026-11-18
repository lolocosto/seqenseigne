r"""services/vue_ensemble_referentiel.py — v0.59.2

Document « Vue d'ensemble du référentiel » (demande de Laurent du 17
novembre 2026) : un document chapeau, pour l'enseignant, qui récapitule
**par domaine** (thème A à F, avec sa couleur) les séquences, leurs
**parties** avec leur **durée en semaines**, et sous chaque partie ses
**objectifs** (code, intitulé, nombre de séances). Totaux par séquence, par
domaine et pour l'année. Généré automatiquement pour tous les référentiels.

Décisions (doc/redemarrage_v0_59_2.md) :

  - V1 Catalogue — un type `vue_ensemble` ajouté à **tous** les catalogues
    (Notions et méthodes, Fiches, Fiches + cartes, mises en route), en tête
    de liste (ordre 0), décoché, une seule version (enseignant), sans option.
  - V2 Source — même règle que les autres documents : référentiel figé
    (verrouillé, utilisé) ou externe → son **instantané** (`referentiel_*`) ;
    référentiel en cours ou validé → les **tables de l'atelier**
    (`sequence_parties`, `objectifs`), dans le périmètre de son type.
  - V3 Séances — aucun nouveau champ : `objectifs.nb_seances` (atelier) ou
    `referentiel_objectifs.nb_seances` (instantané), objectif « Cours »
    compris. Durée d'une partie = somme des séances de ses objectifs, plus
    ses séances de révision et d'approche (`nb_seances_R_AE`, modèle
    « Notions et méthodes » ; jamais pour une mise en route, dont
    l'instantané range la somme de ses objectifs dans ce champ : RI4 ; ni
    pour un référentiel externe, même raison : v0.51.4).
  - V4 Semaines — règle de Laurent : 3 séances = 1 semaine (6 = 2, 9 = 3).
    Semaine arrondie au plus proche (demi au-dessus) ; une partie dont la
    somme n'est pas un multiple de 3 est signalée (« * »), une partie sans
    séance aussi (« séances à saisir »). Totaux en semaines = somme des
    semaines des parties (une partie dure des semaines entières).
  - V5 Référentiel figé — le document est **calculé à la volée** (route
    `…/vue-ensemble/rendu-pdf`, cache du compilateur) : aucun document figé,
    aucun fichier de `_verrouille/`, aucune empreinte ne change ; la ligne
    `vue_ensemble` n'est ajoutée qu'aux référentiels modifiables
    (`referentiel_documents.lister_documents`).
"""

from __future__ import annotations

import sqlite3
from decimal import ROUND_HALF_UP, Decimal

TYPE_DOCUMENT = "vue_ensemble"
SEANCES_PAR_SEMAINE = 3
ETATS_FIGES = ("verrouille", "utilise")

# Couleurs des thèmes : celles du module seqenseigne-theme (vif, pâle), par
# code de couleur (`themes.code_couleur`, `referentiel_themes.couleur`).
COULEURS = {
    "nombres": ("red!85!black", "red!10!white"),
    "donnees": ("blue!85!black", "blue!10!white"),
    "grandeurs": ("brown!85!black", "brown!10!white"),
    "geometrie": ("violet!85!black", "violet!10!white"),
    "algorithmique": ("magenta!85!black", "magenta!10!white"),
    "proportionnalite": ("teal!85!black", "teal!10!white"),
}
COULEUR_DEFAUT = ("black!75", "black!6")


class VueEnsembleErreur(ValueError):
    pass


# ── Règle des semaines ───────────────────────────────────────────────────────

def semaines(seances: float) -> int:
    """3 séances = 1 semaine, arrondi au plus proche (demi au-dessus)."""
    return int((Decimal(str(seances or 0)) / SEANCES_PAR_SEMAINE)
               .quantize(Decimal(1), rounding=ROUND_HALF_UP))


def multiple_de_3(seances: float) -> bool:
    s = Decimal(str(seances or 0))
    return s == s.to_integral_value() and int(s) % SEANCES_PAR_SEMAINE == 0


def _nb(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


# ── Lecture de la structure ──────────────────────────────────────────────────

def _ref(conn, ref_id: str) -> dict:
    r = conn.execute("SELECT * FROM referentiel_niveaux WHERE id = ?", (ref_id,)).fetchone()
    if r is None:
        raise VueEnsembleErreur(f"Référentiel introuvable : {ref_id}")
    return dict(r)


def depuis_instantane(ref: dict) -> bool:
    """V2 — figé (verrouillé, utilisé) ou externe : instantané."""
    return (ref.get("etat") in ETATS_FIGES
            or (ref.get("source") or "interne") == "externe")


def _cols(conn, table: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _lire_atelier(conn, ref: dict) -> tuple[list, list]:
    from services.mises_en_route_6e import est_objectif_cours, est_sequence_mer
    from services.referentiels_internes import sequences_du_perimetre
    type_ref = ref.get("type_ref") or "principal"
    seqs = sequences_du_perimetre(conn, ref["niveau"], type_ref)
    themes: dict = {}
    for code, nom, couleur, ordre in conn.execute(
            "SELECT t.code, t.nom, t.code_couleur, t.ordre FROM themes t "
            "JOIN param_niveaux pn ON pn.cycle_code = t.cycle_code WHERE pn.code = ?",
            (ref["niveau"],)).fetchall():
        themes[code] = {"code": code, "nom": nom or "", "couleur": couleur or "",
                        "ordre": ordre or 0}
    lib = "libelle" in _cols(conn, "sequence_parties")
    titre_court = "titre_court" in _cols(conn, "sequences_par_niveau")
    sortie = []
    for s in seqs:
        tc = ""
        if titre_court:
            r = conn.execute("SELECT titre_court FROM sequences_par_niveau WHERE id = ?",
                             (s["sn_id"],)).fetchone()
            tc = (r[0] if r else "") or ""
        parties = []
        # 6e : libellés de parties dans objectifs_6e.json (comme le livret, C1).
        from services.livret_sequence_6e import libelles_parties
        libs_json = libelles_parties(ref["niveau"], s["code"])
        for p in conn.execute("SELECT id, numero, nb_seances_R_AE"
                              + (", libelle" if lib else ", '' AS libelle")
                              + " FROM sequence_parties WHERE sequence_par_niveau_id = ? "
                              "ORDER BY numero", (s["sn_id"],)).fetchall():
            objs = [{"code": o["code"], "nom": o["nom"] or "", "seances": _nb(o["nb_seances"]),
                     "cours": est_objectif_cours(o["code"], p["numero"], s["code"])}
                    for o in conn.execute("SELECT code, nom, nb_seances FROM objectifs "
                                          "WHERE partie_id = ? ORDER BY code", (p["id"],))]
            rae = 0.0 if est_sequence_mer(s["code"]) else _nb(p["nb_seances_R_AE"])
            parties.append({"numero": p["numero"],
                            "libelle": p["libelle"] or libs_json.get(p["numero"], ""),
                            "rae": rae, "objectifs": objs})
        sortie.append({"code": s["code"], "nom": tc or s["nom"], "nom_cycle": s["nom"],
                       "theme": s["theme_code"] or "", "parties": parties})
        if s["theme_code"] and s["theme_code"] not in themes:
            themes[s["theme_code"]] = {"code": s["theme_code"], "nom": s["theme_nom"],
                                       "couleur": s["theme_couleur"], "ordre": 99}
    return list(themes.values()), sortie


def _lire_instantane(conn, ref: dict) -> tuple[list, list]:
    from services.mises_en_route_6e import est_objectif_cours, est_sequence_mer
    rid = ref["id"]
    ordre_th = "ordre" in _cols(conn, "referentiel_themes")
    themes = [{"code": t["code"], "nom": t["nom"] or "", "couleur": t["couleur"] or "",
               "ordre": (t["ordre"] if ordre_th else 0) or 0}
              for t in conn.execute("SELECT * FROM referentiel_themes WHERE referentiel_id = ?",
                                    (rid,)).fetchall()]
    lib = "libelle" in _cols(conn, "referentiel_parties")
    type_obj = "type_obj" in _cols(conn, "referentiel_objectifs")
    sortie = []
    for s in conn.execute("SELECT * FROM referentiel_sequences WHERE referentiel_id = ? "
                          "ORDER BY numero, code", (rid,)).fetchall():
        parties = []
        objs_seq = conn.execute("SELECT * FROM referentiel_objectifs WHERE referentiel_id = ? "
                                "AND seq_code = ? ORDER BY code", (rid, s["code"])).fetchall()
        numeros = sorted({o["partie_numero"] for o in objs_seq} | {
            p["numero"] for p in conn.execute("SELECT numero FROM referentiel_parties WHERE "
                                              "referentiel_id = ? AND seq_code = ?",
                                              (rid, s["code"]))})
        for n in numeros:
            p = conn.execute("SELECT * FROM referentiel_parties WHERE referentiel_id = ? AND "
                             "seq_code = ? AND numero = ?", (rid, s["code"], n)).fetchone()
            objs = [{"code": o["code"], "nom": o["nom"] or "", "seances": _nb(o["nb_seances"]),
                     "cours": (type_obj and o["type_obj"] == "connaissance")
                     or est_objectif_cours(o["code"], n, s["code"])}
                    for o in objs_seq if o["partie_numero"] == n]
            rae = 0.0
            # V3 — référentiel externe et mise en route : ce champ contient la
            # somme des objectifs (durée calculée), jamais des séances de plus.
            if (p is not None and not est_sequence_mer(s["code"])
                    and (ref.get("source") or "interne") != "externe"):
                rae = _nb(p["nb_seances_R_AE"])
            parties.append({"numero": n, "libelle": (p["libelle"] if (p is not None and lib)
                                                     else "") or "",
                            "rae": rae, "objectifs": objs})
        sortie.append({"code": s["code"], "nom": s["nom"] or "", "nom_cycle": s["nom"] or "",
                       "theme": s["theme_code"] or "", "parties": parties})
    return themes, sortie


def structure(conn: sqlite3.Connection, ref_id: str) -> dict:
    """Structure complète, totaux et signalements (sans LaTeX)."""
    from services import codes_sequence as cs
    from services.referentiel_principal_externe import nom_calcule
    ref = _ref(conn, ref_id)
    instantane = depuis_instantane(ref)
    themes, seqs = (_lire_instantane if instantane else _lire_atelier)(conn, ref)
    seqs.sort(key=lambda s: cs.cle_tri(s["code"]))
    for s in seqs:
        for p in s["parties"]:
            p["seances"] = sum(o["seances"] for o in p["objectifs"]) + p["rae"]
            p["semaines"] = semaines(p["seances"])
            p["multiple"] = multiple_de_3(p["seances"])
        s["seances"] = sum(p["seances"] for p in s["parties"])
        s["semaines"] = sum(p["semaines"] for p in s["parties"])
        s["nb_objectifs"] = sum(1 for p in s["parties"] for o in p["objectifs"]
                                if not o["cours"])
    par_code = {t["code"]: t for t in themes}
    domaines = []
    codes = sorted({s["theme"] for s in seqs},
                   key=lambda c: ((par_code.get(c) or {}).get("ordre", 99) or 99, c or "~"))
    for c in codes:
        t = par_code.get(c) or {"code": c, "nom": "", "couleur": ""}
        ss = [s for s in seqs if s["theme"] == c]
        domaines.append({"code": c, "nom": t["nom"] if c else "Sans domaine",
                         "couleur": t.get("couleur") or "", "sequences": ss,
                         "seances": sum(s["seances"] for s in ss),
                         "semaines": sum(s["semaines"] for s in ss),
                         "nb_parties": sum(len(s["parties"]) for s in ss),
                         "nb_objectifs": sum(s["nb_objectifs"] for s in ss)})
    parties = [p for s in seqs for p in s["parties"]]
    return {
        "referentiel": ref_id, "nom": nom_calcule(ref), "niveau": ref["niveau"],
        "annee": _annee(ref), "etat": ref.get("etat") or "", "source":
            "instantane" if instantane else "atelier",
        "type_ref": ref.get("type_ref") or "principal",
        "gabarit": ref.get("gabarit_documents") or "cycle4",
        # v0.60.1 (D18c) — mode de mise en route ('' : non renseigné, pas de ligne).
        "mise_en_route": _mise_en_route(conn, ref_id, ref),
        "domaines": domaines,
        "nb_sequences": len(seqs), "nb_parties": len(parties),
        "nb_objectifs": sum(s["nb_objectifs"] for s in seqs),
        "seances": sum(s["seances"] for s in seqs),
        "semaines": sum(s["semaines"] for s in seqs),
        "parties_non_multiples": sum(1 for p in parties if p["seances"] and not p["multiple"]),
        "parties_sans_seance": sum(1 for p in parties if not p["seances"]),
    }


def _mise_en_route(conn, ref_id: str, ref: dict) -> str:
    if (ref.get("type_ref") or "principal") != "principal":
        return ""
    from services.mise_en_route_referentiel import lire
    m = lire(conn, ref_id)
    return m["libelle"] if m["mode"] else ""


def _annee(ref: dict) -> str:
    if (ref.get("source") or "interne") == "externe" and ref.get("annee"):
        return ref["annee"]
    try:
        y = int(str(ref.get("version") or "")[:4])
        return f"{y}-{y + 1}"
    except ValueError:
        return ref.get("annee") or ""


# ── LaTeX ────────────────────────────────────────────────────────────────────

def _fmt(x: float) -> str:
    x = float(x or 0)
    return str(int(x)) if x.is_integer() else f"{x:.1f}".replace(".", "{,}")


def _t(s: str) -> str:
    from services.latex_texte import texte_latex
    return texte_latex(s or "")


_ETATS = {"en_cours": "en cours", "valide": "validé", "verrouille": "verrouillé",
          "utilise": "utilisé", "annule": "annulé"}
_MODELES = {"cycle4": "Notions et méthodes", "sixieme": "Fiches de résumé par objectif"}


def generer_vue_ensemble(conn: sqlite3.Connection, ref_id: str) -> str:
    """Document complet (A4 portrait, tableau sobre)."""
    from services.referentiel_principal_externe import NIVEAUX
    st = structure(conn, ref_id)
    L = [r"%% Vue d'ensemble du référentiel " + ref_id + " (seqenseigne v0.59.2).",
         r"\documentclass[10pt,a4paper]{article}",
         r"\usepackage[utf8]{inputenc}", r"\usepackage[T1]{fontenc}",
         r"\usepackage[french]{babel}", r"\usepackage{lmodern}",
         r"\usepackage[a4paper,margin=1.6cm,top=1.5cm,bottom=1.6cm]{geometry}",
         r"\usepackage[table]{xcolor}", r"\usepackage{longtable,array,booktabs}",
         r"\usepackage{textcomp,amssymb,fancyhdr}",
         r"\renewcommand{\familydefault}{\sfdefault}",
         r"\setlength{\parindent}{0pt}\setlength{\LTpre}{2pt}\setlength{\LTpost}{6pt}",
         r"\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}",
         r"\fancyfoot[C]{\footnotesize " + _t(st["nom"]) + r" -- vue d'ensemble -- page \thepage}",
         r"\newcolumntype{C}{>{\raggedright\arraybackslash}p{1.45cm}}",
         r"\newcolumntype{I}{>{\raggedright\arraybackslash}p{11.8cm}}",
         r"\newcolumntype{N}{>{\raggedleft\arraybackslash}p{1.45cm}}"]
    for d in st["domaines"]:
        vif, pale = COULEURS.get(d["couleur"], COULEUR_DEFAUT)
        nom = "theme" + (d["code"] or "Aucun")
        L.append(r"\colorlet{%sVif}{%s}\colorlet{%sPale}{%s}" % (nom, vif, nom, pale))
    L.append(r"\begin{document}")
    niv = NIVEAUX.get(st["niveau"], st["niveau"])
    source = ("instantané du référentiel (figé)" if st["source"] == "instantane"
              else "structure de l'atelier (référentiel modifiable)")
    L += [r"{\LARGE\bfseries Vue d'ensemble du référentiel}\par\smallskip",
          r"{\large " + _t(st["nom"]) + r"}\par\medskip",
          r"\begin{tabular}{@{}ll@{}}",
          r"Niveau & " + _t(niv) + r" \\",
          r"Année & " + _t(st["annee"] or "—") + r" \\",
          r"Modèle & " + _t(_MODELES.get(st["gabarit"], st["gabarit"]))
          + (" (mises en route)" if st["type_ref"] == "mer" else "") + r" \\"]
    if st.get("mise_en_route"):                                     # v0.60.1 (D18c)
        L.append(r"Mise en route & " + _t(st["mise_en_route"]) + r" \\")
    L += [
          r"État & " + _t(_ETATS.get(st["etat"], st["etat"])) + " ; " + source + r" \\",
          r"Contenu & %d séquence(s), %d partie(s), %d objectif(s) \\"
          % (st["nb_sequences"], st["nb_parties"], st["nb_objectifs"]),
          r"\textbf{Total} & \textbf{%s séance(s), %d semaine(s)} \\"
          % (_fmt(st["seances"]), st["semaines"]),
          r"\end{tabular}\par\medskip",
          r"{\small Durée d'une partie : somme des séances de ses objectifs (objectif "
          r"« Cours » compris), convertie en semaines à raison de 3 séances par semaine "
          r"(3 = 1, 6 = 2, 9 = 3), arrondie à la semaine la plus proche. "
          r"\textbf{*} : nombre de séances qui n'est pas un multiple de 3. "
          r"Les séances se saisissent par objectif (onglet Séquence de l'atelier, ou clé "
          r"\texttt{seances} des lots).}\par"]
    if st["parties_sans_seance"]:
        L.append(r"\medskip{\small\color{red!70!black}\textbf{Attention :} %d partie(s) "
                 r"sans séance saisie (durée affichée « --- »).}\par"
                 % st["parties_sans_seance"])
    # Récapitulatif annuel par domaine
    L += [r"\medskip", r"\begin{longtable}{@{}p{8.4cm}>{\raggedleft\arraybackslash}p{1.3cm}"
          r">{\raggedleft\arraybackslash}p{1.3cm}>{\raggedleft\arraybackslash}p{1.4cm}"
          r">{\raggedleft\arraybackslash}p{1.3cm}>{\raggedleft\arraybackslash}p{1.4cm}@{}}",
          r"\toprule \textbf{Domaine} & \textbf{Séq.} & \textbf{Parties} & \textbf{Objectifs}"
          r" & \textbf{Séances} & \textbf{Semaines} \\ \midrule"]
    for d in st["domaines"]:
        nom = "theme" + (d["code"] or "Aucun")
        L.append(r"\textcolor{%sVif}{\rule{0.8em}{0.8em}}\ %s & %d & %d & %d & %s & %d \\"
                 % (nom, _t((d["code"] + " — " if d["code"] else "") + d["nom"]),
                    len(d["sequences"]), d["nb_parties"], d["nb_objectifs"],
                    _fmt(d["seances"]), d["semaines"]))
    L += [r"\midrule \textbf{Année} & \textbf{%d} & \textbf{%d} & \textbf{%d} & \textbf{%s} & "
          r"\textbf{%d} \\ \bottomrule" % (st["nb_sequences"], st["nb_parties"],
                                           st["nb_objectifs"], _fmt(st["seances"]),
                                           st["semaines"]),
          r"\end{longtable}"]
    # Une section par domaine
    for d in st["domaines"]:
        nom = "theme" + (d["code"] or "Aucun")
        titre = (f"Domaine {d['code']} — " if d["code"] else "") + (d["nom"] or "")
        L += [r"\bigskip",
              r"{\setlength{\fboxsep}{4pt}\colorbox{%sVif}{\parbox{\dimexpr\linewidth-8pt"
              r"\relax}{\color{white}\large\bfseries %s\hfill %s séance(s), %d semaine(s)}}}"
              r"\par\nopagebreak" % (nom, _t(titre), _fmt(d["seances"]), d["semaines"]),
              r"\begin{longtable}{@{}CINN@{}}",
              r"\textbf{Code} & \textbf{Séquence, partie, objectif} & \textbf{Séances} & "
              r"\textbf{Semaines} \\ \midrule \endhead"]
        for s in d["sequences"]:
            L.append(r"\rowcolor{%sPale}\textbf{%s} & \textbf{%s} & \textbf{%s} & \textbf{%d}"
                     r" \\*" % (nom, _t(s["code"]), _t(s["nom"]), _fmt(s["seances"]),
                                s["semaines"]))
            if not s["parties"]:
                L.append(r" & \textit{aucune partie} & & \\")
            for p in s["parties"]:
                lib = f"Partie {p['numero']}" + (f" — {p['libelle']}" if p["libelle"] else "")
                if not p["seances"]:
                    sem = r"---"
                else:
                    sem = str(p["semaines"]) + ("" if p["multiple"] else r"\,\textbf{*}")
                L.append(r"\textit{P%d} & \textit{%s} & \textit{%s} & \textbf{%s} \\*"
                         % (p["numero"], _t(lib), _fmt(p["seances"]), sem))
                for o in p["objectifs"]:
                    code = f"{s['code']}-{o['code']}"
                    intitule = _t(o["nom"])
                    if o["cours"]:
                        intitule = r"\textcolor{black!60}{\textit{" + intitule + r"}}"
                    L.append(r"\hspace{0.6em}{\small %s} & \hspace{0.8em}%s & %s & \\"
                             % (_t(code), intitule, _fmt(o["seances"]) if o["seances"]
                                else r"\textcolor{black!45}{0}"))
                if p["rae"]:
                    L.append(r" & \hspace{0.8em}\textit{Révisions et activités d'approche} & "
                             r"%s & \\" % _fmt(p["rae"]))
            L.append(r"\midrule")
        L += [r"\textbf{Total %s} & & \textbf{%s} & \textbf{%d} \\ \bottomrule"
              % (_t(d["code"] or ""), _fmt(d["seances"]), d["semaines"]),
              r"\end{longtable}"]
    L.append(r"\end{document}")
    return "\n".join(L) + "\n"
