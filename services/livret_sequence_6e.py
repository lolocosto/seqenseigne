r"""services/livret_sequence_6e.py — v0.52.1

Documents du gabarit « sixieme » (services/gabarits_documents.py), au style
de l'équipe de 6e (module LaTeX `seqenseigne-style6e`) :

  - `generer_livret_sequence_6e` : livret de séquence ;
  - `generer_fiches_cours_6e`    : fiches de cours (fiches de résumé en
                                   version complète) ;
  - `generer_corriges_6e`        : corrigés enseignant (le livret en version
                                   corrigée, remédiations comprises).

Rendu visé : les aperçus validés du lot S01 (`apercu_eleve.tex`,
`apercu_corrige.tex`), sur une seule colonne :

    \seqCouvertureLivretSix{séquence}{S01-02/{intitulé},…}
    pour chaque partie : « Partie n » ;
      pour chaque objectif (hors objectif « Cours ») :
        \seqBandeauCapacite{S01-02}{intitulé}
        activités d'introduction           (seqActiviteSix)
        fiche de résumé à compléter         (seqFicheResumeSix)
        exercices F, A, E                   (seqExoSix[O|A|E]) et remédiations

Le contenu vient de la base de l'atelier (sequences_par_niveau,
sequence_parties, objectifs, objectif_exos, partie_exos_revision_approche,
exercices, fiches_resume et leurs sections) — jamais des lots.

Décisions (doc/redemarrage_v0_52_1.md) :

  - L1 Activités d'introduction. Une activité rattachée à un objectif
    (`objectif_exos`, série AE ; l'import 6e le fait depuis v0.52.2)
    s'affiche sous son bandeau, comme dans l'aperçu, et seulement là ; une
    activité rattachée à la seule **partie** (`partie_exos_revision_approche`,
    type EA) ouvre la partie, avant le premier objectif. v0.52.2 : le lien à
    la partie est gardé (numérotation, plan de travail) sans doublon.
  - L2 Fiche d'un objectif : `fiches_resume.objectif_id` ; une fiche
    attachée au « Cours » de la partie (`objectif_fiches`) sans objectif de
    la partie s'affiche en tête de partie, après les activités.
  - L3 Objectif « Cours » : code `01`, `11`, `21`… (partie n → `(n-1)1`,
    convention du cycle 4 et de l'import 6e, D5) ; ni bandeau ni ligne de
    couverture.
  - L4 Un exercice rattaché à plusieurs objectifs n'est émis qu'une fois,
    au premier (comme services/numerotation_livret.py, D4).
  - L5 Une seule géométrie : celle que le paquet pose pour les documents de
    l'équipe (`seqenseigne-theme`, chargé par `\usepackage[sixieme]{…}` dans
    les aperçus), passée à `construire_preambule` à la place de sa ligne
    `\newgeometry` ; aucun `\geometry` de plus (le livret du cycle 4 en émet
    un second, ce qui est le conflit relevé à l'audit).
  - L6 Titre courant et couverture : nom de la séquence du cycle
    (`sequences_du_cycle.nom`) ; « Partie n » sans libellé (l'atelier
    interne n'a pas de libellé de partie).
  - L7 Séquences d'archive `Xnn` (v0.52.0, D1) : jamais générées.
"""

from __future__ import annotations

import sqlite3

from services.gabarits_documents import REMEDIATIONS_6E, VERSIONS_6E
from services.latex_rendu_atome import (
    Atome, detecter_options_paquet, detecter_paquets_tex_manquants,
)
from services.paquet_parseur import extraire_utilisations
from services.preambule_atome import construire_preambule

# L5 — Géométrie des documents de l'équipe de 6e : celle que pose
# `seqenseigne-theme` (option docstd, défaut) quand le paquet est chargé en
# entier, comme dans les aperçus validés du lot S01.
GEOMETRIE_6E = r"\geometry{left=35pt,right=35pt,top=50pt,bottom=70pt,head=30pt,foot=10pt}"

STATUT_SERIE = {"F": "O", "A": "A", "E": "E"}
TITRES_SERIES = (("F", "Exercices fondamentaux"),
                 ("A", "Exercices d'approfondissement"),
                 ("E", "Exercices d'expertise"))

# Contenus volumineux : on réserve plus de place avant l'exercice (aperçu).
_MARQUEURS_GRANDS = ("tabular", "tikzpicture", "\\seqLocTableau", "includegraphics")


class Livret6eErreur(ValueError):
    pass


# ── Options ──────────────────────────────────────────────────────────────────

def options_par_defaut() -> dict:
    return {"version": "eleve", "inclure_activites": True, "inclure_serie_E": True,
            "remediations": "apres_exercice"}


def normaliser_options(options: dict | None) -> dict:
    """Options du livret 6e. Les clés inconnues (dont `actif` et les options
    du livret du cycle 4 qu'envoie l'atelier) sont ignorées ; une valeur
    hors liste lève Livret6eErreur."""
    o = options_par_defaut()
    for cle, val in (options or {}).items():
        if cle in ("inclure_activites", "inclure_serie_E"):
            o[cle] = bool(val)
        elif cle in ("version", "remediations"):
            o[cle] = val
    if o["version"] not in VERSIONS_6E:
        raise Livret6eErreur(f"version invalide : {o['version']!r}")
    if o["remediations"] not in REMEDIATIONS_6E:
        raise Livret6eErreur(f"remediations invalide : {o['remediations']!r}")
    return o


# ── Lecture de la base de l'atelier ─────────────────────────────────────────

def _est_objectif_cours(code: str, numero_partie: int) -> bool:
    """L3 — l'objectif « Cours » de la partie n porte le code (n-1)1."""
    return (code or "").strip() == f"{numero_partie - 1}1"


def _exercice(conn, ex_id: str) -> dict | None:
    r = conn.execute("SELECT id, titre, enonce, corrige, remed_enonce, remed_corrige, "
                     "variables, serie_code, num FROM exercices WHERE id = ?",
                     (ex_id,)).fetchone()
    if r is None:
        return None
    d = {k: (r[k] if r[k] is not None else "") for k in r.keys()}
    try:
        d["code"] = f"{d['serie_code']}{int(d['num']):02d}"
    except (TypeError, ValueError):
        d["code"] = f"{d['serie_code']}{d['num']}"
    return d


def _fiche(conn, fiche_id: str) -> dict | None:
    from services.fiches_resume import FicheIntrouvable, lire_fiche
    try:
        return lire_fiche(conn, fiche_id)
    except FicheIntrouvable:
        return None


def lire_sequence_6e(conn: sqlite3.Connection, niveau: str, sequence_code: str) -> dict:
    """Structure du livret : {code, nom, numero, parties: [{numero,
    activites: [ex], fiches: [fiche], objectifs: [{code, nom, activites,
    fiches, series: {F,A,E: [ex]}}]}]}."""
    if (sequence_code or "").startswith("X"):
        raise Livret6eErreur(f"{sequence_code} est une séquence d'archive (cycle 3).")
    from services.v2_lecture import lire_sequence_par_niveau
    data = lire_sequence_par_niveau(conn, niveau, sequence_code)
    sn = data["sequence_par_niveau"]
    vus: set[str] = set()                      # L4
    fiches_vues: set[str] = set()
    parties = []
    for p in data["parties"]:
        numero = p["numero"]
        # L1 (v0.52.2) — Une activité rattachée à un objectif de la partie
        # (objectif_exos, série AE) s'affiche sous le bandeau de cet objectif
        # et seulement là, même si elle reste aussi rattachée à la partie
        # (lien gardé pour la numérotation et le plan de travail).
        sous_objectif = {e.get("exercice_id")
                         for o in p.get("objectifs", [])
                         if not _est_objectif_cours(o["code"], numero)
                         for e in ((o.get("exos_par_serie") or {}).get("AE") or [])}
        activites = []
        for e in (p.get("exos_revision_approche") or {}).get("EA", []) or []:
            if e.get("exercice_id") in sous_objectif:
                continue
            ex = _exercice(conn, e["exercice_id"]) if e.get("exercice_id") else None
            if ex and ex["id"] not in vus:
                vus.add(ex["id"])
                activites.append(ex)
        cours_ids, objectifs = [], []
        for o in p.get("objectifs", []):
            if _est_objectif_cours(o["code"], numero):
                cours_ids.append(o["id"])
                continue
            eps = o.get("exos_par_serie") or {}
            act_obj = []
            for e in eps.get("AE", []) or []:
                ex = _exercice(conn, e["exercice_id"]) if e.get("exercice_id") else None
                if ex and ex["id"] not in vus:
                    vus.add(ex["id"])
                    act_obj.append(ex)
            series = {}
            for s, _ in TITRES_SERIES:
                lst = []
                for e in eps.get(s, []) or []:
                    ex = _exercice(conn, e["exercice_id"]) if e.get("exercice_id") else None
                    if ex and ex["id"] not in vus:
                        vus.add(ex["id"])
                        lst.append(ex)
                series[s] = lst
            fiches = []
            for (fid,) in conn.execute("SELECT id FROM fiches_resume WHERE objectif_id = ? "
                                       "ORDER BY num_fiche, id", (o["id"],)).fetchall():
                f = _fiche(conn, fid)
                if f and fid not in fiches_vues:
                    fiches_vues.add(fid)
                    fiches.append(f)
            objectifs.append({"code": o["code"], "nom": o["nom"] or "", "activites": act_obj,
                              "fiches": fiches, "series": series})
        fiches_partie = []                     # L2 — fiches du Cours sans objectif
        for cid in cours_ids:
            for (fid,) in conn.execute("SELECT fiche_id FROM objectif_fiches WHERE "
                                       "objectif_id = ? ORDER BY ordre", (cid,)).fetchall():
                f = _fiche(conn, fid)
                if f and fid not in fiches_vues and f.get("objectif_id") not in \
                        {x["id"] for x in p.get("objectifs", [])}:
                    fiches_vues.add(fid)
                    fiches_partie.append(f)
        parties.append({"numero": numero, "activites": activites, "fiches": fiches_partie,
                        "objectifs": objectifs})
    nom, numero = _nom_sequence(conn, niveau, sequence_code)
    return {"code": sequence_code, "nom": nom or sn.get("sequence_nom") or sequence_code,
            "numero": numero, "niveau": niveau, "parties": parties}


def _nom_sequence(conn, niveau: str, sequence_code: str) -> tuple[str, int | None]:
    """L6 — Nom et numéro de la séquence dans le cycle **du niveau**.

    `v2_lecture` joint `sequences_du_cycle` sur le seul code : depuis
    v0.52.0, S01…S10 existent en C03 et en C04, et la 6e y reçoit le nom de
    la séquence du cycle 4. On lit donc le cycle du niveau (param_niveaux)."""
    from services.param_niveaux import lire_cycle
    try:
        cycle = lire_cycle(conn, niveau)
    except Exception:
        cycle = ""
    r = conn.execute("SELECT nom, numero FROM sequences_du_cycle WHERE cycle_code = ? "
                     "AND code = ?", (cycle, sequence_code)).fetchone() if cycle else None
    return (r[0], r[1]) if r else ("", None)


def sequences_du_niveau(conn, niveau: str) -> list[str]:
    """Séquences du niveau (L7 : sans les archives Xnn)."""
    return [r[0] for r in conn.execute(
        "SELECT sequence_code FROM sequences_par_niveau WHERE niveau = ? "
        "ORDER BY sequence_code", (niveau,)).fetchall() if not r[0].startswith("X")]


# ── Rendu LaTeX ──────────────────────────────────────────────────────────────

def _titre_exo(ex: dict, prefixe: str = "") -> str:
    return (prefixe + (ex.get("titre") or "")
            + r"\hfill{\footnotesize\color{seqSixGrisTexte}" + ex["code"] + "}")


def latex_fiche(fiche: dict) -> str:
    r"""Corps de la fiche au format du lot : chaque section de l'atelier
    Fiche redevient `\seqSectionFicheSix{titre}` suivi de ses items (inverse
    de outils/import_lot6e.sections_fiche)."""
    morceaux = []
    for sec in fiche.get("sections", []):
        titre = (sec.get("titre") or "").strip()
        if titre:
            morceaux.append(r"\seqSectionFicheSix{" + titre + "}")
        for item in sec.get("items", []) or []:
            if (item or "").strip():
                morceaux.append(item.strip())
    return "\n".join(morceaux)


def _emettre_fiche(L: list, fiche: dict) -> None:
    L.append(r"\needspace{10\baselineskip}")
    L.append(r"\begin{seqFicheResumeSix}{" + (fiche.get("titre") or "") + "}")
    L.append(latex_fiche(fiche))
    L.append(r"\end{seqFicheResumeSix}")


def _emettre_activite(L: list, ex: dict) -> None:
    if (ex.get("variables") or "").strip():
        L.append(ex["variables"])
    L.append(r"\needspace{10\baselineskip}")
    L.append(r"\begin{seqActiviteSix}{" + _titre_exo(ex) + "}")
    L.append(ex.get("enonce") or "")
    if (ex.get("corrige") or "").strip():
        L.append(r"\seqLocExplication{" + ex["corrige"] + "}")
    L.append(r"\end{seqActiviteSix}")


def _emettre_remediation(L: list, ex: dict) -> None:
    L.append(r"\needspace{6\baselineskip}")
    L.append(r"\begin{seqExoSix}[R][" + _titre_exo(ex, "Remédiation -- ") + "]")
    L.append(ex["remed_enonce"])
    if (ex.get("remed_corrige") or "").strip():
        L.append(r"\seqLocExplication{" + ex["remed_corrige"] + "}")
    L.append(r"\end{seqExoSix}")


def _emettre_exercice(L: list, ex: dict, serie: str, opts: dict, remeds_fin: list) -> None:
    enonce = ex.get("enonce") or ""
    if (ex.get("variables") or "").strip():
        L.append(ex["variables"])
    grand = any(m in enonce for m in _MARQUEURS_GRANDS)
    L.append(r"\needspace{%d\baselineskip}" % (14 if grand else 6))
    L.append(r"\begin{seqExoSix}[" + STATUT_SERIE[serie] + "][" + _titre_exo(ex) + "]")
    L.append(enonce)
    if (ex.get("corrige") or "").strip():
        L.append(r"\seqLocExplication{" + ex["corrige"] + "}")
    L.append(r"\end{seqExoSix}")
    if (ex.get("remed_enonce") or "").strip():
        if opts["remediations"] == "apres_exercice":
            _emettre_remediation(L, ex)
        elif opts["remediations"] == "en_fin":
            remeds_fin.append(ex)


def couverture(seq: dict) -> str:
    liste = ",".join(f"{seq['code']}-{o['code']}/{{{o['nom']}}}"
                     for p in seq["parties"] for o in p["objectifs"])
    return r"\seqCouvertureLivretSix{" + seq["nom"] + "}{" + liste + "}"


def entete(seq: dict, corrige: bool) -> str:
    return (r"\fancyhead[R]{\small\bfseries " + seq["nom"] + r" -- page \thepage"
            + (r" -- \textcolor{seqSixRouge}{corrigé}" if corrige else "") + "}")


class _Numeros:
    """v0.52.3 — Numéros que le livret donne aux activités (compteur
    `seqActiviteSix`) et aux exercices (compteur `seqExoSix`, remédiations
    comprises), relevés pendant l'émission même du livret : le plan de
    travail et le rendu d'un atome affichent exactement ces numéros."""

    def __init__(self):
        self.activite = 0
        self.exo = 0
        self.activites: dict[str, int] = {}
        self.exercices: dict[str, int] = {}
        self.remediations: dict[str, int] = {}

    def noter_activite(self, ex: dict) -> None:
        self.activite += 1
        self.activites.setdefault(ex["id"], self.activite)

    def noter_exercice(self, ex: dict) -> None:
        self.exo += 1
        self.exercices.setdefault(ex["id"], self.exo)

    def noter_remediation(self, ex: dict) -> None:
        self.exo += 1
        self.remediations.setdefault(ex["id"], self.exo)


def corps_livret(seq: dict, opts: dict, numeros: "_Numeros | None" = None) -> list[str]:
    """Lignes LaTeX du livret d'une séquence (sans préambule).

    v0.52.3 — `numeros` (facultatif) reçoit les numéros des activités et des
    exercices ; le texte produit n'en dépend pas."""
    N = numeros if numeros is not None else _Numeros()
    L = [entete(seq, opts["version"] == "corrigee"), couverture(seq)]
    remeds_fin: list = []
    for p in seq["parties"]:
        premier = True
        L.append(r"\clearpage")
        L.append(r"\begin{center}{\Large\bfseries\color{seqSixVert}Partie %d}\end{center}"
                 % p["numero"])
        if opts["inclure_activites"]:
            for ex in p["activites"]:
                _emettre_activite(L, ex)
                N.noter_activite(ex)
        for f in p["fiches"]:
            _emettre_fiche(L, f)
        # Le premier objectif suit le titre de partie (et ses activités, L1)
        # sur la même page ; chaque objectif suivant ouvre une page.
        for o in p["objectifs"]:
            if not premier:
                L.append(r"\clearpage")
            else:
                L.append(r"\needspace{15\baselineskip}")
            premier = False
            L.append(r"\seqBandeauCapacite{%s-%s}{%s}" % (seq["code"], o["code"], o["nom"]))
            if opts["inclure_activites"]:
                for ex in o["activites"]:
                    _emettre_activite(L, ex)
                    N.noter_activite(ex)
            for f in o["fiches"]:
                _emettre_fiche(L, f)
            for serie, titre in TITRES_SERIES:
                if serie == "E" and not opts["inclure_serie_E"]:
                    continue
                exos = o["series"].get(serie) or []
                if not exos:
                    continue
                L.append(r"\needspace{8\baselineskip}")
                L.append(r"\seqPartieSix{" + titre + "}")
                for ex in exos:
                    _emettre_exercice(L, ex, serie, opts, remeds_fin)
                    N.noter_exercice(ex)
                    if ((ex.get("remed_enonce") or "").strip()
                            and opts["remediations"] == "apres_exercice"):
                        N.noter_remediation(ex)
    if remeds_fin:
        L.append(r"\clearpage")
        L.append(r"\begin{center}{\Large\bfseries\color{seqSixVert}Remédiations}\end{center}")
        for ex in remeds_fin:
            _emettre_remediation(L, ex)
            N.noter_remediation(ex)
    return L


def numeros_livret(seq: dict, opts: dict) -> _Numeros:
    """v0.52.3 — Numéros du livret de la séquence `seq` (lire_sequence_6e)
    avec les options `opts` du livret (normaliser_options)."""
    N = _Numeros()
    corps_livret(seq, opts, N)
    return N


def corps_fiches(seq: dict) -> list[str]:
    """Lignes LaTeX des fiches de cours d'une séquence (version complète)."""
    fiches = []
    for p in seq["parties"]:
        fiches += p["fiches"]
        for o in p["objectifs"]:
            fiches += o["fiches"]
    if not fiches:
        return []
    L = [r"\fancyhead[R]{\small\bfseries " + seq["nom"] + r" -- page \thepage}",
         r"\seqTitreFicheSix{" + seq["nom"] + "}"]
    for f in fiches:
        _emettre_fiche(L, f)
    return L


def options_livret(conn, niveau: str, referentiel_id: str | None = None) -> dict:
    """Options du livret 6e publié (numérotation) : celles du type
    `livret_sequence_6e` du référentiel donné, sinon du référentiel de
    l'atelier du niveau (règle R1b, v0.52.4 : interne principal hors
    « annule », le plus récent), sinon celles par défaut."""
    import json
    ref = referentiel_id
    if not ref:
        from services.gabarits_documents import referentiel_atelier_du_niveau
        ref = referentiel_atelier_du_niveau(conn, niveau)
    if not ref:
        return {}
    try:
        r = conn.execute("SELECT options FROM referentiel_documents WHERE referentiel_id = ? "
                         "AND type_document = 'livret_sequence_6e'", (ref,)).fetchone()
        return json.loads(r[0]) if r and r[0] else {}
    except (sqlite3.Error, TypeError, ValueError):
        return {}


# ── Préambule et document ────────────────────────────────────────────────────

def noms_niveau(conn, niveau: str) -> tuple[str, str]:
    r"""T1 (v0.52.4) — Nom court du niveau pour le module style6e v0.5 :
    (texte simple, avec exposant), d'après `param_niveaux.nom_court`
    (« 5ème » → « 5e », « 5\textsuperscript{e} »). Un nom qui n'est pas de la
    forme « Nème » est repris tel quel ; niveau inconnu → défaut du module
    (6e)."""
    import re
    try:
        from services.param_niveaux import lire_nom_court
        nc = (lire_nom_court(conn, niveau) or "").strip()
    except Exception:
        nc = ""
    if not nc or nc == niveau:
        nc = {"N09": "6ème", "N10": "5ème", "N11": "4ème", "N12": "3ème"}.get(niveau, "6ème")
    m = re.fullmatch(r"(\d+)\s*(?:ème|e|eme)", nc)
    if m:
        return f"{m.group(1)}e", f"{m.group(1)}\\textsuperscript{{e}}"
    return nc, nc


def macros_niveau(conn, niveau: str) -> list[str]:
    r"""T1 (v0.52.4) — Le modèle « Fiches de résumé par objectif » ne dépend
    pas du niveau : chaque document redéfinit \seqNiveauCourt et
    \seqNiveauExposant (module style6e v0.5, « 6e » par défaut) avec le nom
    court du niveau du référentiel. Rendu de la 6e inchangé."""
    court, expo = noms_niveau(conn, niveau)
    return [r"\renewcommand{\seqNiveauCourt}{" + court + "}",
            r"\renewcommand{\seqNiveauExposant}{" + expo + "}"]


def document(conn: sqlite3.Connection, niveau: str, titre: str, corps: list[str],
             version_corrigee: bool, tikz_libraries=None, tblr_libraries=None,
             preambule_sup: tuple | list = ()) -> str:
    r"""Document complet : préambule sur mesure (macros du cœur recopiées
    par `construire_preambule`, module `seqenseigne-style6e` chargé en
    entier par \usepackage, une seule géométrie — L5)."""
    texte = "\n".join(corps)
    macros, envs = extraire_utilisations(texte)
    atome = Atome(id="_livret_6e_", type_atome="exercice", niveau=niveau, sequence="",
                  fichier="", corps=texte)
    options_paquet = detecter_options_paquet(conn, atome)
    paquets = list(dict.fromkeys(list(detecter_paquets_tex_manquants(conn, atome))
                                 + ["seqenseigne-style6e", "needspace", "fancyhdr"]))
    preambule = construire_preambule(
        conn, "exercice", macros, envs,
        options_atome=options_paquet,
        paquets_tex_supplementaires=paquets,
        tikz_libraries=tikz_libraries,
        tblr_libraries=(tblr_libraries if tblr_libraries is not None
                        else ["booktabs", "varwidth"]),
        marges=GEOMETRIE_6E,
    )
    L = [r"%% " + titre + " — gabarit de documents « sixieme » (seqenseigne v0.52.1).",
         r"%% Niveau : " + niveau, "",
         r"\documentclass[11pt,a4paper]{article}", "",
         preambule.texte, "",
         r"\graphicspath{{data/images/}{./images/}{./}}",
         r"\renewcommand{\familydefault}{\sfdefault}",
         r"\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}",
         r"\setlength{\parindent}{0pt}",
         r"\setlength{\parskip}{2pt}\setlength{\emergencystretch}{3em}",
         r"\setlist{itemsep=1pt,topsep=2pt,parsep=0pt}",
         *macros_niveau(conn, niveau),         # v0.52.4 (T1)
         *preambule_sup,                       # v0.52.3 (plan de travail 6e)
         r"\begin{document}"]
    if version_corrigee:
        L.append(r"\seqVersionCorrigee")
    L += corps
    L.append(r"\end{document}")
    return "\n".join(L) + "\n"


# ── API publique ─────────────────────────────────────────────────────────────

def generer_livret_sequence_6e(conn: sqlite3.Connection, niveau: str, sequence_code: str,
                               options: dict | None = None, tikz_libraries=None,
                               tblr_libraries=None) -> str:
    """Livret de séquence 6e (options : version, inclure_activites,
    inclure_serie_E, remediations)."""
    opts = normaliser_options(options)
    seq = lire_sequence_6e(conn, niveau, sequence_code)
    return document(conn, niveau, f"Livret de séquence 6e — {sequence_code} — {seq['nom']}",
                    corps_livret(seq, opts), opts["version"] == "corrigee",
                    tikz_libraries, tblr_libraries)


def _sequences_cible(conn, niveau: str, sequence: str | None) -> list[str]:
    return [sequence] if sequence else sequences_du_niveau(conn, niveau)


def generer_corriges_6e(conn: sqlite3.Connection, niveau: str, sequence: str | None = None,
                        options: dict | None = None, tikz_libraries=None,
                        tblr_libraries=None) -> str:
    """Corrigés enseignant : le livret en version corrigée, remédiations
    comprises (après chaque exercice), d'une séquence ou de toutes
    (`sequence=None` : recueil annuel, une couverture par séquence)."""
    o = options or {}
    opts = normaliser_options({"version": "corrigee", "remediations": "apres_exercice",
                               "inclure_activites": o.get("inclure_activites", True),
                               "inclure_serie_E": o.get("inclure_serie_E", True)})
    corps: list[str] = []
    for code in _sequences_cible(conn, niveau, sequence):
        seq = lire_sequence_6e(conn, niveau, code)
        if corps:
            corps.append(r"\clearpage")
        corps += corps_livret(seq, opts)
    if not corps:
        raise Livret6eErreur(f"Aucune séquence pour {niveau}.")
    titre = f"Corrigés enseignant 6e — {sequence or 'annuel'}"
    return document(conn, niveau, titre, corps, True, tikz_libraries, tblr_libraries)


def generer_fiches_cours_6e(conn: sqlite3.Connection, niveau: str,
                            sequence: str | None = None, options: dict | None = None,
                            tikz_libraries=None, tblr_libraries=None) -> str:
    r"""Fiches de cours : les fiches de résumé en version complète
    (\seqVersionComplete), d'une séquence ou de toutes."""
    corps: list[str] = []
    for code in _sequences_cible(conn, niveau, sequence):
        lignes = corps_fiches(lire_sequence_6e(conn, niveau, code))
        if lignes:
            if corps:
                corps.append(r"\clearpage")
            corps += lignes
    if not corps:
        raise Livret6eErreur(f"Aucune fiche de résumé pour {niveau} {sequence or ''}.")
    corps.insert(0, r"\seqVersionComplete")
    titre = f"Fiches de cours 6e — {sequence or 'annuel'}"
    return document(conn, niveau, titre, corps, False, tikz_libraries, tblr_libraries)

