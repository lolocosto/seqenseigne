r"""services/mises_en_route_6e.py — v0.53.0, v0.53.1, v0.53.2

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

Révisions v0.53.1 (décisions de Laurent du 22 octobre 2026,
doc/redemarrage_v0_53_1.md) :

  - MR1 révisé — Une séquence Mnn a **autant de parties que ref6e_v2**
    (« — partie n » en fin de ligne d'objectif) ; objectifs codés comme au
    principal : partie p à partir de (p − 1) × 10 + 2 (M01-02, M01-12…).
    Chaque partie peut être placée à un autre moment de l'année.
  - P1 — Libellé d'une partie : colonne `sequence_parties.libelle`
    (`migrer`, idempotente ; '' par défaut, rien ne change ailleurs),
    remplie par l'import (`parties[].titre` du lot).
  - MR3 révisé (P2) — Une fiche de cours **par partie** : fiche de résumé
    sans objectif de la séquence, attachée (`objectif_fiches`, comme la
    fiche de cours du principal l'est au « Cours ») aux objectifs de sa
    partie. Une fiche sans objectif attachée à aucun objectif est une
    ancienne fiche de séquence (v0.53.0) : signalée par la validation.
  - P3 — Partie d'un test court : celle de ses objectifs évalués
    (`evaluation_objectifs`), un test court par partie.
  - MR5 révisé — Documents par partie (option `partie`, absente ou 0 :
    toute la séquence ; le test court se choisit par partie).
  - MR6 révisé — Validation par partie : fiche de cours et au moins un
    exercice MR par objectif ; nombre d'exercices ≠ séances, partie sans
    test court : avertissements.

Révisions v0.53.2 (25 octobre 2026, doc/redemarrage_v0_53_2.md) :

  - E1 — Les chaînes de la base insérées en texte (intitulés, critères,
    titres, libellés, messages du contrôle) passent par l'échappement LaTeX
    commun `services.latex_texte.texte_latex` (& % # _ et caractères Unicode
    inconnus de pdfLaTeX : π, ≈, ≤…) ; tout le corps passe en plus par
    `unicode_latex` dans `livret_sequence_6e.document` (cas réel : critère F
    de M04-22 « … avec π ≈ 3,14 », plan de la partie 3 non compilé).
  - D-DOS — **Dossier enseignant** (document `dossier`, par partie ou toute
    la séquence partie par partie) : un seul document A4, version corrigée,
    pages numérotées (en-tête « … — dossier enseignant — page n »), chaque
    bloc sur une nouvelle page : le plan de la partie, la fiche de cours
    complète, les corrigés rédigés des exercices de séance dans l'ordre des
    séances (un exercice sans corrigé rédigé le dit : réponses sur la
    planche corrigée), les tests courts corrigés (sujet A puis sujet B),
    puis les activités complémentaires corrigées. Les documents existants
    restent.
  - D-AC — **Activités complémentaires** (série AC, comme au principal) dans
    une Mnn : rattachées à un objectif (objectif_exos, série AC), donc à sa
    partie ; listées dans le plan de la partie, corrigées dans le dossier,
    compilables seules (document `activite` de l'onglet « Rendu PDF », par
    partie ou toute la séquence, élève ou corrigé ; même rendu que le
    document AC du principal, `documents_6e.corps_document`) ; hors du
    contrôle MR6 (qui ne compte que la série MR).
"""

from __future__ import annotations

import re
import sqlite3

SERIE_MR = "MR"
LIBELLE_MR = "mise en route"
NUMERO_CYCLE_BASE = 200           # sequences_du_cycle.numero = 200 + n (UNIQUE par cycle)
PAR_PAGE = (2, 3, 4)
EXEMPLAIRES = (1, 2)
DOCUMENTS_MER = ("fiche_cours", "planche", "test_court", "plan", "dossier", "activite")
LIBELLES_DOCUMENTS_MER = {"fiche_cours": "Fiche de cours",
                          "planche": "Exercices de séance",
                          "test_court": "Test court",
                          "plan": "Plan de séquence (enseignant)",
                          "dossier": "Dossier enseignant",                 # v0.53.2 (D-DOS)
                          "activite": "Activités complémentaires"}         # v0.53.2 (D-AC)
SERIE_AC = "AC"
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


# ── Migration (P1) ───────────────────────────────────────────────────────────

def colonne_libelle_presente(conn) -> bool:
    try:
        return "libelle" in {r[1] for r in conn.execute("PRAGMA table_info(sequence_parties)")}
    except sqlite3.Error:
        return False


def colonne_format_presente(conn) -> bool:
    try:
        return "format_planche" in {r[1] for r in conn.execute("PRAGMA table_info(exercices)")}
    except sqlite3.Error:
        return False


def migrer(conn) -> bool:
    """P1 (v0.53.1) — `sequence_parties.libelle` (TEXT, '' par défaut) ; F1 —
    `exercices.format_planche` (TEXT, '' = quart d'A4) ; idempotente ; True si
    une colonne vient d'être ajoutée."""
    fait = False
    for table, col in (("sequence_parties", "libelle"), ("exercices", "format_planche")):
        try:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        except sqlite3.Error:
            continue
        if cols and col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
            fait = True
    return fait


# ── F1 Format d'un exercice de séance sur la planche ────────────────────────

FORMATS_PLANCHE = ("quart", "demi")
_RE_DEMI = re.compile(r"demi[- ]?(?:page\s+)?A4|demi[- ]page", re.IGNORECASE)


def format_depuis_lot(e: dict) -> tuple[str, str]:
    """F1 — (format, origine) d'un exercice de séance du lot : clé `format`
    ('quart' | 'demi') ; à défaut, « demi-A4 » dans `notes` (lots M04, M05,
    M06 du 22 octobre) ; sinon 'quart'. Valeur de `format` inconnue :
    ('quart', 'invalide')."""
    v = (e.get("format") or "").strip().lower() if isinstance(e.get("format"), str) else ""
    if v:
        return (v, "lot") if v in FORMATS_PLANCHE else ("quart", "invalide")
    if _RE_DEMI.search(e.get("notes") or ""):
        return "demi", "notes"
    return "quart", "défaut"


def format_exercice(ex: dict) -> str:
    return "demi" if (ex.get("format_planche") or "") == "demi" else "quart"


def titre_bandeau(sequence: str) -> str | None:
    r"""P5 — titre du bandeau `seqCalculMental` des exercices de séance :
    « CALCUL MENTAL » (défaut du module) pour M01 « Calcul mental », « MISE EN
    ROUTE » pour les autres (`\seqDefinirTitreCM`, module v0.10). Un énoncé
    qui redéfinit `\seqTitreCM` dans un groupe garde son titre."""
    return None if sequence == "M01" else "MISE EN ROUTE"


# ── Lecture ──────────────────────────────────────────────────────────────────

def _exercice(r: dict) -> dict:
    d = {k: (v if v is not None else "") for k, v in r.items()}
    try:
        d["code"] = f"{d['serie_code']}{int(d['num']):02d}"
    except (TypeError, ValueError):
        d["code"] = f"{d['serie_code']}{d['num']}"
    return d


def _sn_id(conn, niveau: str, sequence: str) -> str | None:
    r = conn.execute("SELECT id FROM sequences_par_niveau WHERE niveau = ? AND "
                     "sequence_code = ?", (niveau, sequence)).fetchone()
    return r[0] if r else None


def parties_en_base(conn, sn_id: str) -> list[dict]:
    """[{id, numero, libelle}] des parties d'une séquence-niveau."""
    lib = "libelle" if colonne_libelle_presente(conn) else "''"
    return [{"id": r[0], "numero": r[1], "libelle": (r[2] or "").strip()}
            for r in conn.execute(f"SELECT id, numero, {lib} FROM sequence_parties WHERE "
                                  "sequence_par_niveau_id = ? ORDER BY numero", (sn_id,))]


def parties_de_fiche(conn, fiche_id: str) -> list[int]:
    """P2 — numéros des parties des objectifs auxquels la fiche est attachée."""
    return sorted({r[0] for r in conn.execute(
        "SELECT p.numero FROM objectif_fiches x JOIN objectifs o ON o.id = x.objectif_id "
        "JOIN sequence_parties p ON p.id = o.partie_id WHERE x.fiche_id = ?", (fiche_id,))})


def fiches_de_sequence(conn, niveau: str, sequence: str) -> dict:
    """MR3 révisé, MR4 — {"parties": {numero: (fiche de cours, version
    complète ou None)}, "sans_partie": [fiches sans objectif attachées à
    aucun objectif : anciennes fiches de séquence]} ; fiches sans objectif
    de la séquence, par numéro de fiche."""
    from services.fiches_resume import FicheIntrouvable, lire_fiche
    parties: dict = {}
    sans: list = []
    for (fid, titre) in conn.execute(
            "SELECT id, titre FROM fiches_resume WHERE niveau = ? AND sequence = ? AND "
            "objectif_id IS NULL ORDER BY num_fiche, id", (niveau, sequence)).fetchall():
        try:
            f = lire_fiche(conn, fid)
        except FicheIntrouvable:
            continue
        nums = parties_de_fiche(conn, fid)
        if not nums:
            sans.append(f)
            continue
        cours, complete = parties.get(nums[0], (None, None))
        if (titre or "").endswith(SUFFIXE_COMPLETE):
            complete = complete or f
        else:
            cours = cours or f
        parties[nums[0]] = (cours, complete)
    return {"parties": parties, "sans_partie": sans}


def partie_des_objectifs(conn, objectif_ids) -> int | None:
    """P3 — partie (la plus petite) d'un ensemble d'objectifs ; None sans."""
    ids = [x for x in objectif_ids if x]
    if not ids:
        return None
    r = conn.execute("SELECT MIN(p.numero) FROM objectifs o JOIN sequence_parties p ON "
                     f"p.id = o.partie_id WHERE o.id IN ({','.join('?' * len(ids))})",
                     ids).fetchone()
    return r[0] if r and r[0] is not None else None


def nombre_de_parties(conn, niveau: str, sequence: str) -> int:
    sn = _sn_id(conn, niveau, sequence)
    if sn is None:
        return 0
    return conn.execute("SELECT COUNT(*) FROM sequence_parties WHERE "
                        "sequence_par_niveau_id = ?", (sn,)).fetchone()[0]


def tests_courts(conn, niveau: str, sequence: str) -> list[dict]:
    """Évaluations du niveau dont les exercices sont surtout de la séquence
    (même règle que le rendu 6e : séquence majoritaire de ses exercices) ;
    `partie` (P3, v0.53.1) : partie de ses objectifs évalués."""
    from collections import Counter
    out = []
    for r in conn.execute("SELECT id, numero, titre, ordre FROM evaluations WHERE niveau = ? "
                          "ORDER BY ordre, numero, id", (niveau,)).fetchall():
        seqs = Counter(x[0] for x in conn.execute(
            "SELECT e.sequence FROM evaluation_exercices ee JOIN exercices e "
            "ON e.id = ee.exercice_id WHERE ee.evaluation_id = ? AND e.sequence <> ''",
            (r[0],)))
        if seqs and seqs.most_common(1)[0][0] == sequence:
            objs = [x[0] for x in conn.execute("SELECT objectif_id FROM evaluation_objectifs "
                                               "WHERE evaluation_id = ?", (r[0],))]
            out.append({"id": r[0], "numero": r[1], "titre": r[2] or "",
                        "partie": partie_des_objectifs(conn, objs)})
    return out


def titre_partie(p: dict) -> str:
    """« Partie n --- libellé » ; à défaut de libellé, l'intitulé de
    l'objectif quand la partie n'en a qu'un."""
    lib = p.get("libelle") or ""
    if not lib and len(p.get("objectifs") or []) == 1:
        lib = p["objectifs"][0]["nom"]
    return f"Partie {p['numero']}" + (f" --- {lib}" if lib else "")


def lire_sequence_mer(conn: sqlite3.Connection, niveau: str, sequence: str) -> dict:
    """{code, nom, numero, theme_couleur, objectifs: [{id, code, etiquette,
    nom, critere_F, critere_A, nb_seances, partie}], exercices: [MR dans
    l'ordre des séances, avec `seance`, `objectif` (étiquette) et `partie`],
    parties: [{id, numero, libelle, objectifs, exercices, fiche,
    fiche_complete, tests}], fiches_sans_partie, tests: [{id, numero, titre,
    partie}], fiche / fiche_complete (celles de la première partie)}."""
    if not est_sequence_mer(sequence):
        raise MiseEnRouteErreur(f"{sequence!r} n'est pas une séquence de mise en route.")
    sn = _sn_id(conn, niveau, sequence)
    if sn is None:
        raise MiseEnRouteErreur(f"{niveau}/{sequence} : séquence de mise en route absente "
                                "de l'atelier (importer le lot).")
    from services.livret_sequence_6e import _nom_sequence
    nom, _ = _nom_sequence(conn, niveau, sequence)
    th = conn.execute(
        "SELECT t.code_couleur FROM sequences_du_cycle s JOIN param_niveaux pn ON "
        "pn.cycle_code = s.cycle_code LEFT JOIN themes t ON t.id = s.theme_id "
        "WHERE pn.code = ? AND s.code = ?", (niveau, sequence)).fetchone()
    parties = parties_en_base(conn, sn)
    num_partie = {p["id"]: p["numero"] for p in parties}
    objectifs = []
    for o in conn.execute(
            "SELECT o.id, o.code, o.nom, o.critere_F, o.critere_A, o.nb_seances, o.partie_id "
            "FROM objectifs o JOIN sequence_parties p ON p.id = o.partie_id "
            "WHERE p.sequence_par_niveau_id = ? ORDER BY p.numero, o.code", (sn,)):
        objectifs.append({"id": o[0], "code": o[1], "etiquette": f"{sequence}-{o[1]}",
                          "nom": o[2] or "", "critere_F": o[3] or "", "critere_A": o[4] or "",
                          "nb_seances": float(o[5] or 0), "partie": num_partie.get(o[6])})
    par_id = {o["id"]: o for o in objectifs}
    from services.marqueurs_exercices import sql_colonnes
    cur = conn.execute(
        "SELECT id, titre, enonce, corrige, remed_enonce, remed_corrige, variables, niveau, "
        "sequence, serie_code, num, etat_code" + sql_colonnes(conn)
        + (", format_planche" if colonne_format_presente(conn) else ", '' AS format_planche")
        + " FROM exercices "
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
        ex["partie"] = o["partie"] if o else None
        exercices.append(ex)
    activites = activites_complementaires(conn, niveau, sequence, par_id)   # v0.53.2
    fiches = fiches_de_sequence(conn, niveau, sequence)
    tests = tests_courts(conn, niveau, sequence)
    for p in parties:
        p["objectifs"] = [o for o in objectifs if o["partie"] == p["numero"]]
        p["exercices"] = [e for e in exercices if e["partie"] == p["numero"]]
        p["activites"] = [a for a in activites if a["partie"] == p["numero"]]
        p["fiche"], p["fiche_complete"] = fiches["parties"].get(p["numero"], (None, None))
        p["tests"] = [t for t in tests if t["partie"] == p["numero"]]
        p["titre"] = titre_partie(p)
    premiere = parties[0] if parties else {"fiche": None, "fiche_complete": None}
    return {"code": sequence, "niveau": niveau, "nom": nom or sequence,
            "numero": numero_mer(sequence), "theme_couleur": (th[0] if th else "") or "",
            "objectifs": objectifs, "exercices": exercices, "parties": parties,
            "activites": activites,
            "fiches_sans_partie": fiches["sans_partie"],
            "fiche": premiere["fiche"], "fiche_complete": premiere["fiche_complete"],
            "tests": tests}


def activites_complementaires(conn, niveau: str, sequence: str, par_id: dict) -> list[dict]:
    """D-AC (v0.53.2) — activités complémentaires (série AC) de la séquence,
    par numéro : {id, code, titre, num, objectifs: [étiquettes], partie
    (celle du premier objectif relié ; None sans objectif), …}."""
    out = []
    for r in conn.execute("SELECT id, titre, num FROM exercices WHERE niveau = ? AND "
                          "sequence = ? AND serie_code = ? ORDER BY num, id",
                          (niveau, sequence, SERIE_AC)).fetchall():
        objs = [par_id[x[0]] for x in conn.execute(
            "SELECT objectif_id FROM objectif_exos WHERE exercice_id = ? AND serie = ? "
            "ORDER BY ordre", (r[0], SERIE_AC)) if x[0] in par_id]
        out.append({"id": r[0], "titre": r[1] or "", "num": r[2],
                    "code": f"{SERIE_AC}{int(r[2] or 0):02d}",
                    "objectifs": [o["etiquette"] for o in objs],
                    "partie": objs[0]["partie"] if objs else None})
    return out


def partie_de(s: dict, numero) -> dict:
    """La partie `numero` de la séquence lue (MiseEnRouteErreur sinon)."""
    for p in s["parties"]:
        if p["numero"] == numero:
            return p
    raise MiseEnRouteErreur(f"{s['code']} : pas de partie {numero} "
                            f"({len(s['parties'])} partie(s)).")


def resume_mer(conn, niveau: str, sequence: str) -> dict:
    """Pour l'onglet « Rendu PDF » de l'atelier (choix de la partie, contrôle
    MR6 affiché) : {code, nom, parties: [{numero, titre, objectifs:
    [étiquette], exercices, tests: [{numero, titre}], fiche}], validation}."""
    s = lire_sequence_mer(conn, niveau, sequence)
    return {"code": s["code"], "nom": s["nom"], "libelle": libelle_mer(sequence),
            "parties": [{"numero": p["numero"], "titre": p["titre"],
                         "objectifs": [o["etiquette"] for o in p["objectifs"]],
                         "exercices": len(p["exercices"]),
                         "seances": sum(o["nb_seances"] for o in p["objectifs"]),
                         "tests": [{"numero": t["numero"], "titre": t["titre"]}
                                   for t in p["tests"]],
                         "activites": [{"code": a["code"], "titre": a["titre"]}
                                       for a in p.get("activites") or []],
                         "fiche": (p["fiche"] or {}).get("titre") or ""}
                        for p in s["parties"]],
            "validation": valider_sequence_mer(conn, niveau, sequence, s)}


# ── MR6 Validation ───────────────────────────────────────────────────────────

def _fmt(n: float) -> str:
    return str(int(n)) if float(n) == int(n) else f"{n:g}".replace(".", ",")


def valider_sequence_mer(conn: sqlite3.Connection, niveau: str, sequence: str,
                         seq: dict | None = None) -> dict:
    """MR6 révisé (v0.53.1) — {"valide", "erreurs", "avertissements",
    "parties": {numero: {"erreurs", "avertissements"}}}.

    Exigé, partie par partie : la fiche de cours de la partie, au moins un
    exercice MR par objectif ; et chaque exercice MR relié à un objectif de
    la séquence. Avertissements : nombre d'exercices MR différent du nombre
    de séances prévu (séquence, partie, objectif), partie sans test court,
    ancienne fiche de séquence (attachée à aucune partie), partie sans
    objectif."""
    s = seq or lire_sequence_mer(conn, niveau, sequence)
    erreurs, avert = [], []
    par_partie: dict = {p["numero"]: {"erreurs": [], "avertissements": []}
                        for p in s["parties"]}
    multi = len(s["parties"]) > 1

    def err(p, texte):
        erreurs.append(texte)
        if p in par_partie:
            par_partie[p]["erreurs"].append(texte)

    def avt(p, texte):
        avert.append(texte)
        if p in par_partie:
            par_partie[p]["avertissements"].append(texte)

    if not s["objectifs"]:
        err(None, "aucun objectif")
    par_obj: dict = {o["etiquette"]: 0 for o in s["objectifs"]}
    for ex in s["exercices"]:
        if ex["objectif"]:
            par_obj[ex["objectif"]] += 1
        else:
            err(None, f"{ex['code']} relié à aucun objectif de la séquence")
    prevu = sum(o["nb_seances"] for o in s["objectifs"])
    if prevu and len(s["exercices"]) != prevu:
        avt(None, f"{len(s['exercices'])} exercice(s) de séance pour {_fmt(prevu)} "
                  "séance(s) prévue(s)")
    for p in s["parties"]:
        n = p["numero"]
        pref = f"partie {n} : " if multi else ""
        if not p["objectifs"]:
            avt(n, f"partie {n} sans objectif")
            continue
        if p["fiche"] is None:
            err(n, f"{pref}pas de fiche de cours" if multi else "pas de fiche de cours")
        for o in p["objectifs"]:
            if not par_obj[o["etiquette"]]:
                err(n, f"{o['etiquette']} sans exercice de séance")
        prevu_p = sum(o["nb_seances"] for o in p["objectifs"])
        if multi and prevu_p and len(p["exercices"]) != prevu_p:
            avt(n, f"{pref}{len(p['exercices'])} exercice(s) de séance pour "
                   f"{_fmt(prevu_p)} séance(s) prévue(s)")
        for o in p["objectifs"]:
            k = par_obj[o["etiquette"]]
            if o["nb_seances"] and k and k != o["nb_seances"]:
                avt(n, f"{o['etiquette']} : {k} exercice(s) pour {_fmt(o['nb_seances'])} "
                       "séance(s)")
        if not p["tests"]:
            avt(n, f"{pref}aucun test court" if multi else "aucun test court")
    for f in s.get("fiches_sans_partie") or []:
        avt(None, f"fiche « {f.get('titre') or ''} » attachée à aucune partie (ancienne "
                  "fiche de séquence)")
    if not s["parties"] and not s["tests"]:
        avt(None, "aucun test court")
    return {"valide": not erreurs, "erreurs": erreurs, "avertissements": avert,
            "parties": par_partie}


# ── Rendu LaTeX ──────────────────────────────────────────────────────────────

def _partie_option(v):
    """MR5 révisé — `partie` : absente, '', 0, « tout » ou « toute » : toute
    la séquence (None) ; sinon un numéro ≥ 1."""
    if v in (None, "", 0, "0", "tout", "toute", "toutes"):
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise MiseEnRouteErreur(f"partie invalide : {v!r}")
    if n < 1:
        raise MiseEnRouteErreur(f"partie invalide : {v!r}")
    return n


def options_mer(options: dict | None) -> dict:
    """MR5 — options d'un document de mise en route (clés inconnues ignorées).
    v0.53.1 : `partie` (None = toute la séquence)."""
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
    o["partie"] = _partie_option((options or {}).get("partie"))
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


def _titre_seq(s: dict, partie: int | None = None) -> str:
    """« Mise en route n --- nom » (+ « --- partie p » quand la séquence a
    plusieurs parties)."""
    t = f"{libelle_mer(s['code'])} --- {_echapper(s['nom'])}"
    if partie is not None and len(s.get("parties") or []) > 1:
        t += f" --- partie {partie}"
    return t


def _entete(s: dict, corrige: bool) -> str:
    from services.livret_sequence_6e import entete
    return entete({"nom": f"{libelle_mer(s['code'])} --- {_echapper(s['nom'])}"}, corrige)


def _copies(corps: list[str], exemplaires: int) -> list[str]:
    r"""1 exemplaire : tel quel ; 2 : `seqCopies{2}` (deux demi-pages A5 à
    découper, compteurs du module rétablis pour chaque copie)."""
    if exemplaires == 1:
        return corps
    return [r"\begin{seqCopies}{%d}" % exemplaires, *corps, r"\end{seqCopies}"]


def _parties_voulues(s: dict, partie: int | None) -> list[dict]:
    return [partie_de(s, partie)] if partie is not None else list(s["parties"])


def corps_fiche_cours(s: dict, version: str, exemplaires: int = 1,
                      partie: int | None = None) -> list[str]:
    """MR3, MR4 (révisés v0.53.1) — fiche de cours d'une partie (toutes les
    parties à la suite, une par page, sans `partie`) : titre « Mise en route
    n --- nom --- partie p », puis la fiche (à compléter ; complète en
    version corrigée)."""
    from services.livret_sequence_6e import _emettre_fiche
    complete = version == "corrigee"
    blocs = []
    for p in _parties_voulues(s, partie):
        fiche = p["fiche"]
        if fiche is None:
            if partie is None and len(s["parties"]) > 1:
                continue
            raise MiseEnRouteErreur(f"{s['code']} partie {p['numero']} : pas de fiche de "
                                    "cours.")
        if complete and p.get("fiche_complete") is not None:
            fiche = dict(p["fiche_complete"],
                         titre=p["fiche_complete"]["titre"][:-len(SUFFIXE_COMPLETE)])
        corps: list[str] = [r"\seqTitreFicheSix{" + _titre_seq(s, p["numero"]) + "}"]
        _emettre_fiche(corps, fiche)
        blocs.append(_copies(corps, exemplaires))
    if not blocs:
        raise MiseEnRouteErreur(f"{s['code']} : pas de fiche de cours.")
    L = [_entete(s, False)]
    if complete:
        L.append(r"\seqVersionComplete")
    for i, b in enumerate(blocs):
        if i:
            L.append(r"\clearpage")
        L += b
    return L


def _ligne_reference(s: dict, ex: dict) -> str:
    from services.marqueurs_exercices import latex_6e
    marques = latex_6e(ex)
    ref = " --- ".join(x for x in (f"{libelle_mer(s['code'])}",
                                    f"séance {ex['seance']}" if ex.get("seance") else "",
                                    ex.get("objectif") or "") if x)
    # v0.53.1 — « \hfill{} » : sans marqueur (exercice de géométrie, calculatrice
    # non précisée), « \hfillMR07 » était une macro inconnue (lots M04, M05).
    return (r"{\footnotesize\color{seqSixGrisTexte}" + ref + r"\hfill{}"
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
        # v0.53.2 (E1) — titre échappé (cas réel : « Passer par 10 % ou 1 % », M02).
        L.append(r"{\bfseries\color{seqSixBleu}" + _echapper(ex["titre"].strip())
                 + r"}\par\smallskip")
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
                                         _echapper((ex.get("titre") or "").strip()),
                                         ex["code"]) if x)
        L.append(r"\needspace{5\baselineskip}")
        L.append(r"\seqPartieSix{" + titre + "}")
        L.append(r"\seqLocExplication{" + ex["corrige"].strip() + "}")


def corps_planche(s: dict, par_page: int, version: str,
                  exercices: list[dict] | None = None,
                  partie: int | None = None) -> list[str]:
    """MR5 — planche des exercices de séance, `par_page` fiches par A4 à
    découper au massicot (dans l'ordre des séances) ; v0.53.1 : ceux d'une
    partie (`partie`) ou de toute la séquence ; F1 : les exercices en demi-A4
    (`format_planche`) sur une planche à 2 par A4, après les quarts ; P5 :
    titre du bandeau (`titre_bandeau`)."""
    if exercices is not None:
        exos = exercices
    elif partie is not None:
        exos = partie_de(s, partie)["exercices"]
    else:
        exos = s["exercices"]
    if not exos:
        raise MiseEnRouteErreur(f"{s['code']}"
                                + (f" partie {partie}" if partie is not None else "")
                                + " : aucun exercice de séance (série MR).")
    L = [_entete(s, version == "corrigee")]
    titre = titre_bandeau(s["code"])
    if titre:
        L.append(r"\seqDefinirTitreCM{" + titre + "}")
    # F1 — les quarts d'A4 à `par_page` par feuille, puis les demi-A4 (exercices
    # à figure) à 2 par feuille : jamais deux formats sur une même feuille ;
    # dans chaque planche, l'ordre des séances.
    for fmt, n in (("quart", par_page), ("demi", 2)):
        groupe = [ex for ex in exos if format_exercice(ex) == fmt]
        if not groupe:
            continue
        L.append(r"\begin{seqPlancheFiches}{%d}" % n)
        for ex in groupe:
            emettre_bande(L, s, ex)
        L.append(r"\end{seqPlancheFiches}")
    if version == "corrigee":
        emettre_corriges_rediges(L, s, exos)
    return L


def _echapper(t: str) -> str:
    """Texte simple venu de la base (intitulés, critères, titres, messages) :
    échappement LaTeX commun (v0.53.2, E1 : & % # _ hors formules, et π, ≈,
    ≤… en commandes sûres)."""
    from services.latex_texte import texte_latex
    return texte_latex(t)


def _plan_partie(L: list, s: dict, p: dict, v: dict, multi: bool) -> None:
    if multi:
        L.append(r"\seqPartieSix{" + _echapper(p["titre"]) + "}")
    L.append(r"\textbf{Objectifs}")
    L.append(r"\begin{itemize}")
    for o in p["objectifs"]:
        # v0.53.2 (E1) — intitulé et critères : échappement commun (cas réel :
        # « π ≈ 3,14 » dans le critère F de M04-22).
        L.append(r"\item \textbf{" + o["etiquette"] + "} " + _echapper(o["nom"])
                 + f" ({_fmt(o['nb_seances'])} séance" + ("s" if o["nb_seances"] > 1 else "")
                 + ")" + (r"\\{\footnotesize F : " + _echapper(o["critere_F"]) + "}"
                          if o["critere_F"] else "")
                 + (r"\\{\footnotesize A : " + _echapper(o["critere_A"]) + "}"
                    if o["critere_A"] else ""))
    L.append(r"\end{itemize}")
    f = p["fiche"]
    L.append(r"\textbf{Fiche de cours} : "
             + ((r"au début de la partie, « " + _echapper(f.get("titre") or "") + " », à coller "
                 r"dans le cahier.") if f else r"\emph{pas de fiche de cours.}") + r"\par")
    L.append(r"\medskip\textbf{Séances}\par")
    if p["exercices"]:
        L.append(r"{\small\begin{longtable}{|r|l|p{0.62\linewidth}|l|}\hline")
        L.append(r"\textbf{Séance} & \textbf{Objectif} & \textbf{Exercice} & \textbf{Code}"
                 r"\\\hline\endhead")
        for ex in p["exercices"]:
            L.append(f"{ex.get('seance') or ''} & {ex.get('objectif') or '?'} & "
                     + _echapper(ex.get("titre") or "") + f" & {ex['code']}" + r"\\\hline")
        L.append(r"\end{longtable}}")
    else:
        L.append(r"\emph{Aucun exercice de séance.}\par")
    L.append(r"\textbf{Test court sur 10}\par")
    if p["tests"]:
        L.append(r"\begin{itemize}")
        for t in p["tests"]:
            L.append(r"\item " + _echapper(t["titre"]) + f" (évaluation n\\textsuperscript{{o}} "
                     f"{t['numero']})")
        L.append(r"\end{itemize}")
    else:
        L.append(r"\emph{Aucun test court.}\par")
    if p.get("activites"):                                            # v0.53.2 (D-AC)
        L.append(r"\textbf{Activités complémentaires} {\small (élèves en avance ; hors "
                 r"contrôle de la séquence)}\par")
        L.append(r"\begin{itemize}")
        for a in p["activites"]:
            L.append(r"\item " + a["code"] + " --- " + _echapper(a["titre"])
                     + (f" ({', '.join(a['objectifs'])})" if a["objectifs"] else ""))
        L.append(r"\end{itemize}")
    vp = v["parties"].get(p["numero"]) or {"erreurs": [], "avertissements": []}
    if multi and (vp["erreurs"] or vp["avertissements"]):
        L.append(r"\begin{itemize}")
        for e in vp["erreurs"]:
            L.append(r"\item {\color{seqSixRouge}À compléter : " + _echapper(e) + "}")
        for a in vp["avertissements"]:
            L.append(r"\item Attention : " + _echapper(a))
        L.append(r"\end{itemize}")


def corps_plan(conn, s: dict, partie: int | None = None) -> list[str]:
    """MR5 — plan de séquence pour l'enseignant, partie par partie (ou la
    seule partie demandée) : objectifs (critères, séances), fiche de cours,
    séances (objectif, exercice), test court, contrôle MR6."""
    v = valider_sequence_mer(conn, s["niveau"], s["code"], s)
    parties = _parties_voulues(s, partie)
    multi = len(s["parties"]) > 1
    L = [_entete(s, False),
         r"\begin{center}{\Large\bfseries\color{seqSixVert}" + _titre_seq(s, partie)
         + r"}\\[2pt]{\small\itshape\color{seqSixGrisTexte}"
         r"Plan de séquence (enseignant) --- un exercice au début de chaque séance"
         + (r" --- chaque partie peut être placée à un autre moment de l'année"
            if multi and partie is None else "")
         + r"}\end{center}"]
    for p in parties:
        _plan_partie(L, s, p, v, multi)
    if partie is None:
        globales = ([e for e in v["erreurs"]
                     if not any(e in x["erreurs"] for x in v["parties"].values())]
                    if multi else v["erreurs"])
        avert = ([a for a in v["avertissements"]
                  if not any(a in x["avertissements"] for x in v["parties"].values())]
                 if multi else v["avertissements"])
        if globales or avert:
            L.append(r"\seqPartieSix{Contrôle de la séquence}")
            L.append(r"\begin{itemize}")
            for e in globales:
                L.append(r"\item {\color{seqSixRouge}À compléter : " + _echapper(e) + "}")
            for a in avert:
                L.append(r"\item Attention : " + _echapper(a))
            L.append(r"\end{itemize}")
    elif not multi:
        vp = v
        if vp["erreurs"] or vp["avertissements"]:
            L.append(r"\seqPartieSix{Contrôle de la séquence}")
            L.append(r"\begin{itemize}")
            for e in vp["erreurs"]:
                L.append(r"\item {\color{seqSixRouge}À compléter : " + _echapper(e) + "}")
            for a in vp["avertissements"]:
                L.append(r"\item Attention : " + _echapper(a))
            L.append(r"\end{itemize}")
    return L


def choisir_test(s: dict, partie: int | None, rang: int) -> dict:
    """Test court demandé : le `rang`-ième de la partie (v0.53.1, un test par
    partie : rang 1), ou sans partie le `rang`-ième de la séquence."""
    tests = partie_de(s, partie)["tests"] if partie is not None else s["tests"]
    if not tests:
        raise MiseEnRouteErreur(f"{s['code']}" + (f" partie {partie}" if partie else "")
                                + " : aucun test court.")
    if rang > len(tests):
        raise MiseEnRouteErreur(f"{s['code']} : test {rang} demandé, "
                                f"{len(tests)} test(s) court(s)"
                                + (f" dans la partie {partie}." if partie else "."))
    return tests[rang - 1]


def generer_test_court(conn, niveau: str, sequence: str, options: dict | None = None,
                       tikz_libraries=None, tblr_libraries=None) -> str:
    """Test court de la partie `partie` (v0.53.1 ; sans partie : n° `test` de
    la séquence) — rendu 6e du module Évaluations : sujet A ou B, élève ou
    corrigé, marqueur calculatrice ; `exemplaires` = 2 : deux sujets par A4
    (A5), sauf sujet en deux parties."""
    from services import render_evaluation as rev
    from services.livret_sequence_6e import document
    o = options_mer(options)
    s = lire_sequence_mer(conn, niveau, sequence)
    ev_id = choisir_test(s, o["partie"], o["test"])["id"]
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


def sous_titre_test(conn, niveau: str, sequence: str, objectif_ids) -> str:
    """« Mise en route n » (+ « , partie p » quand la séquence a plusieurs
    parties) : sous-titre d'un test court (rendu 6e des évaluations)."""
    t = libelle_mer(sequence)
    p = partie_des_objectifs(conn, objectif_ids)
    if p is not None and nombre_de_parties(conn, niveau, sequence) > 1:
        t += f", partie {p}"
    return t


PREAMBULE_MER = (r"\usepackage{longtable}",)


# ── D-AC Activités complémentaires, D-DOS Dossier enseignant (v0.53.2) ─────

def _activites_voulues(s: dict, partie: int | None) -> list[dict]:
    """Activités complémentaires d'une partie, ou de toute la séquence (celles
    sans objectif comprises, à la fin)."""
    if partie is not None:
        return list(partie_de(s, partie).get("activites") or [])
    return list(s.get("activites") or [])


def _corps_activite(conn, a: dict, corrige: bool) -> list[str]:
    """Une activité complémentaire, rendue comme le document AC du principal
    (`documents_6e.corps_document`, numéro du titre = numéro AC), sans son
    en-tête de page."""
    from services.documents_6e import corps_document, lire_atome
    return corps_document(conn, lire_atome(conn, a["id"]), corrige)[1:]


def corps_activites(conn, s: dict, version: str, partie: int | None = None) -> list[str]:
    """D-AC — les activités complémentaires d'une partie (ou de toute la
    séquence), une par page, élève ou corrigé."""
    acs = _activites_voulues(s, partie)
    if not acs:
        raise MiseEnRouteErreur(f"{s['code']}" + (f" partie {partie}" if partie else "")
                                + " : aucune activité complémentaire (série AC).")
    L = [_entete(s, version == "corrigee")]
    for i, a in enumerate(acs):
        if i:
            L.append(r"\clearpage")
        L += _corps_activite(conn, a, version == "corrigee")
    return L


def _entete_dossier(s: dict) -> str:
    return (r"\fancyhead[R]{\small\bfseries " + libelle_mer(s["code"]) + " --- "
            + _echapper(s["nom"]) + r" -- dossier enseignant -- page \thepage}")


def _titre_bloc(texte: str) -> str:
    return (r"\begin{center}{\Large\bfseries\color{seqSixVert}" + texte
            + r"}\end{center}")


def _corriges_seances(L: list, s: dict, exos: list[dict]) -> None:
    """D-DOS — corrigés rédigés des exercices de séance, dans l'ordre des
    séances (variables de l'exercice émises avant son corrigé) ; un exercice
    sans corrigé rédigé le dit."""
    for ex in exos:
        titre = " --- ".join(x for x in (
            f"Séance {ex['seance']}" if ex.get("seance") else "",
            _echapper((ex.get("titre") or "").strip()), ex["code"],
            ex.get("objectif") or "") if x)
        L.append(r"\needspace{5\baselineskip}")
        L.append(r"\seqPartieSix{" + titre + "}")
        if (ex.get("corrige") or "").strip():
            if (ex.get("variables") or "").strip():
                L.append(ex["variables"].rstrip())
            L.append(r"\seqLocExplication{" + ex["corrige"].strip() + "}")
        else:
            L.append(r"{\small\itshape Pas de corrigé rédigé : réponses sur la planche "
                     r"corrigée.}\par")


def _corps_test_corrige(conn, ev_id: str, sujet: str) -> list[str]:
    """Test court corrigé (rendu 6e du module Évaluations), sans en-tête de
    page."""
    from services import render_evaluation as rev
    from services.marqueurs_exercices import calculatrice_evaluation
    opts = rev.options_evaluation_6e({"sujet": sujet, "version": "corrigee"})
    opts["calculatrice"] = calculatrice_evaluation(conn, ev_id)["valeur"]
    st = rev.structure_evaluation_6e(conn, ev_id)
    decoupage = rev.parties_evaluation_6e(conn, ev_id, st)
    return [x for x in rev.corps_evaluation_6e(conn, st, opts, decoupage)
            if not x.startswith(r"\fancyhead")]


def corps_dossier(conn, s: dict, partie: int | None = None) -> list[str]:
    """D-DOS — dossier enseignant d'une partie (ou de toute la séquence,
    partie par partie) : plan de la partie, fiche de cours complète,
    corrigés rédigés des exercices de séance, tests courts corrigés A et B,
    activités complémentaires corrigées ; chaque bloc sur une nouvelle page."""
    L = [_entete_dossier(s)]
    for k, p in enumerate(_parties_voulues(s, partie)):
        n = p["numero"]
        if k:
            L.append(r"\clearpage")
        # 1. Plan de la partie (sans son en-tête de page).
        L += [x for x in corps_plan(conn, s, n) if not x.startswith(r"\fancyhead")]
        # 2. Fiche de cours complète.
        L.append(r"\clearpage")
        try:
            fiche = corps_fiche_cours(s, "corrigee", 1, n)[1:]
        except MiseEnRouteErreur:
            fiche = [_titre_bloc("Fiche de cours"), r"\emph{Pas de fiche de cours.}\par"]
        L += fiche
        # 3. Corrigés rédigés des exercices de séance.
        L.append(r"\clearpage")
        L.append(_titre_bloc("Corrigés des exercices de séance --- "
                             + _echapper(p["titre"])))
        if p["exercices"]:
            _corriges_seances(L, s, p["exercices"])
        else:
            L.append(r"\emph{Aucun exercice de séance.}\par")
        # 4. Tests courts corrigés, sujet A puis sujet B.
        for t in p["tests"]:
            for sujet in ("A", "B"):
                L.append(r"\clearpage")
                L += _corps_test_corrige(conn, t["id"], sujet)
        # 5. Activités complémentaires corrigées.
        for a in p.get("activites") or []:
            L.append(r"\clearpage")
            L += _corps_activite(conn, a, True)
    if partie is None:
        sans = [a for a in s.get("activites") or [] if a["partie"] is None]
        for a in sans:
            L.append(r"\clearpage")
            L += _corps_activite(conn, a, True)
    return L


def generer_document_mer(conn: sqlite3.Connection, niveau: str, sequence: str,
                         options: dict | None = None, tikz_libraries=None,
                         tblr_libraries=None) -> str:
    """MR5 — .tex d'un document de la séquence de mise en route (option
    `document` : fiche_cours | planche | test_court | plan ; v0.53.1 :
    `partie`, sans elle toute la séquence ; v0.53.2 : dossier, activite)."""
    from services.livret_sequence_6e import document
    o = options_mer(options)
    if o["document"] == "test_court":
        return generer_test_court(conn, niveau, sequence, o, tikz_libraries, tblr_libraries)
    s = lire_sequence_mer(conn, niveau, sequence)
    if o["partie"] is not None:
        partie_de(s, o["partie"])
    corrige = o["version"] == "corrigee"
    titre = f"{LIBELLES_DOCUMENTS_MER[o['document']]} — {sequence} — {s['nom']}" \
        + (f" — partie {o['partie']}" if o["partie"] is not None else "")
    if o["document"] == "fiche_cours":
        # La version complète est posée par \seqVersionComplete dans le corps.
        return document(conn, niveau, titre, corps_fiche_cours(s, o["version"],
                                                               o["exemplaires"], o["partie"]),
                        False, tikz_libraries, tblr_libraries)
    if o["document"] == "planche":
        titre += f" — {o['par_page']} par A4"
        return document(conn, niveau, titre, corps_planche(s, o["par_page"], o["version"],
                                                           partie=o["partie"]),
                        corrige, tikz_libraries, tblr_libraries)
    if o["document"] == "activite":                                   # v0.53.2 (D-AC)
        return document(conn, niveau, titre, corps_activites(conn, s, o["version"],
                                                             o["partie"]),
                        corrige, tikz_libraries, tblr_libraries)
    if o["document"] == "dossier":                                    # v0.53.2 (D-DOS)
        # Tout le dossier est en version corrigée (fiche complète, corrigés).
        return document(conn, niveau, titre, corps_dossier(conn, s, o["partie"]), True,
                        tikz_libraries, tblr_libraries, preambule_sup=PREAMBULE_MER)
    return document(conn, niveau, titre, corps_plan(conn, s, o["partie"]), False,
                    tikz_libraries, tblr_libraries, preambule_sup=PREAMBULE_MER)
