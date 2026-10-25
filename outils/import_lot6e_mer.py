#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""outils/import_lot6e_mer.py — v0.53.0, v0.53.1, v0.53.2

Import des lots de **mise en route** de 6e (`reference\lot6e\Mnn\Mnn.json`),
appelé par `outils/import_lot6e.py` (même commande, même essai à blanc, même
`--apply`, même sauvegarde et même journal que les séquences S01 à S13).

Format du lot — **version 2** (22 octobre 2026, `FORMAT_LOT_MER_v2.md`) :
une partie par objectif (ou paire liée), une fiche de cours et un test court
sur 10 par partie.

    {"sequence": "M01", "titre": "Calcul mental", "theme": "A",
     "type": "mise_en_route", "macros_locales": "",
     "parties": [{"numero": 1, "titre": "Tables de multiplication",
                  "fiche_cours": {"titre": "...", "latex": "...",
                                  "latex_corrige": "..."}}],
     "objectifs": [{"code": "M01-02", "partie": 1, "intitule": "...",
                    "criteres": {"F": "...", "A": "..."}, "seances": 6}],
     "exercices_seance": [{"seance": 1, "objectif": "M01-02", "titre": "...",
                           "enonce": "...", "corrige": "...", "remed_enonce": "",
                           "remed_corrige": "", "calculatrice": "interdite",
                           "ordinateur": "", "origine": "...", "notes": "..."}],
     "evaluations": [{"titre": "Test court --- ...", "partie": 1, "sujet": "A",
                      "calculatrice": "interdite",
                      "bareme": [["M01-02", 8], ["Bonus", 2]], "total": 10,
                      "latex": "...", "bareme_detail": "...", "origine": "..."}],
     "evaluations_retirees": []}

Clés facultatives : `format` d'un exercice de séance (v0.53.1, F1 : « quart »,
défaut, ou « demi » pour un exercice à figure ; à défaut, « demi-A4 » dans
`notes`), `figures` d'un élément (comme les lots S),
`calculatrice_exercices` d'une évaluation (v0.52.9),
`activites_complementaires` (v0.53.2, I-MR8). Un lot au format de la
v0.53.0 (`fiche_cours` au premier niveau, sans `parties`) est refusé.

Décisions v0.53.0 (doc/redemarrage_v0_53_0.md, services/mises_en_route_6e.py) :

  - I-MR1 Référentiel : la section « Mises en route (M2026_N09) » de
    `outils/ref6e_v2.md` (nom, thème, objectifs, séances ; v0.53.1 : partie)
    fait foi, comme `objectifs_6e.json` pour les séquences S ; un intitulé,
    un nombre de séances ou une partie différents dans le lot sont signalés
    (référentiel retenu). Les critères F et A viennent du lot. Séquence
    absente du référentiel : le lot est retenu (signalé).
  - I-MR2 Séquence du cycle 3 `Mnn` (numéro 200 + n), séquence-niveau
    N09/Mnn, objectifs sans objectif « Cours » (MR1b), nombre de séances de
    chaque objectif. v0.53.1 : autant de parties que le référentiel, codes
    de la règle du principal (M01-02, M01-12…), libellé de partie
    (`parties[].titre`, colonne `sequence_parties.libelle`).
  - I-MR3 Fiche de cours — v0.53.1 : **une par partie**, fiche sans objectif
    de la séquence attachée (`objectif_fiches`) aux objectifs de sa partie
    (MR3 révisé), version complète par `\seqACompleter` comme au principal.
    `latex_corrige` (MR4) : vide ou égal à `latex` : rien ; fiche entière
    (elle a ses `\seqSectionFicheSix`) : seconde fiche « … (version
    complète) » de la partie ; sinon note de corrigé : dernière section de
    la fiche, sans titre, dans `\seqLocExplication{…}`. Une version complète
    que le lot n'a plus est retirée (sauf validée : signalé). Une ancienne
    fiche de séquence (attachée à aucun objectif, v0.53.0) est retirée si
    elle n'est pas validée (signalé sinon).
  - I-MR4 Exercices de séance : série MR, numéro = séance (MR01 = séance 1),
    reliés à leur objectif (série MR ; un lien MR vers un autre objectif est
    retiré quand l'exercice change d'objectif). Un exercice validé n'est
    jamais réécrit ; un MR de la base sans séance dans le lot est signalé,
    jamais supprimé.
  - I-MR5 Tests courts : comme les évaluations des lots S (sujets A et B,
    numéros EV jamais réattribués R2, retrait R1, évaluation validée
    intouchée R4) ; total attendu : 10 (signalé sinon). v0.53.1 : un test
    court par partie ; la partie d'un test est celle des objectifs de son
    barème (la clé `partie` du lot est contrôlée, écart signalé) ; partie
    sans test : signalé.
  - I-MR6 `macros_locales` : les macros qu'il définit doivent être fournies
    par le module `seqenseigne-style6e` (les définitions du lot ne sont pas
    importées) ; une macro absente du module est signalée (anomalie), une
    macro déjà fournie est notée (information).
  - Le contrôle MR6 (`mises_en_route_6e.valider_sequence_mer`, par partie en
    v0.53.1) termine le compte rendu de la séquence (dès l'essai à blanc).

Décision v0.53.1 :

  - I-MR7 **Restructuration des mises en route importées avec l'ancienne
    structure** (`restructurer_anciennes_mer`, avant les lots, pour toute
    séquence N09/Mnn de la base, qu'un lot l'accompagne ou non) : une
    séquence dont les objectifs sont exactement 01…0k (une partie, codes de
    la v0.53.0) alors que ref6e_v2 en donne k à la nouvelle règle reçoit ses
    parties et ses nouveaux codes, au rang (M01-01 → M01-02, 02 → 12,
    03 → 22, 04 → 32, table « Anciens codes » de ref6e_v2) : **mêmes
    objectifs** (identifiants gardés), donc exercices MR, liens, fiche et
    tests rattachés gardés, aucun numéro changé (R2). Rien n'est touché, et
    c'est signalé, si un élément de la séquence est validé (séquence-niveau,
    exercice MR ou EV, fiche, test court). Correspondances dans le journal
    (`restructuration`). Idempotente : une fois recodée, la séquence n'a
    plus l'ancienne structure.

Décisions v0.53.2 (doc/redemarrage_v0_53_2.md) :

  - I-MR8 **Activités complémentaires** (série AC, comme au principal) :
    clé `activites_complementaires` au niveau du lot, même format que les
    lots S (`titre`, `latex`, `corrige`, `origine`, `notes`, marqueurs),
    rattachées à un objectif de la séquence par `objectif` (code) ou
    `objectifs` (liste, comme les lots S). Import commun
    (`import_lot6e.importer_documents` : AC01, AC02… dans l'ordre du lot,
    jamais un AC validé réécrit, liens objectif_exos série AC). Une AC sans
    objectif, ou d'objectif inconnu, est signalée. Elles ne comptent pas
    dans le contrôle MR6 (série MR seule). `travaux_personnels` et
    `seances_atelier` n'existent pas dans une mise en route (signalés,
    ignorés).
  - I-MR5 révisé — **bonus de 1 point** (décision du 25 octobre 2026) : un
    bonus d'une autre valeur (barème du lot ou exercices « Bonus… » du
    sujet) est une anomalie « à corriger dans le lot » (et non plus une
    information).
"""

from __future__ import annotations

import re
from pathlib import Path

REF6E_V2 = Path(__file__).resolve().parent / "ref6e_v2.md"
TOTAL_TEST_COURT = 10
BONUS_TEST_COURT = 1          # v0.53.2 — décision du 25 octobre 2026
CLES_OBLIGATOIRES = ("sequence", "titre", "parties", "objectifs", "exercices_seance")

_RE_TITRE = re.compile(r"^### (M\d\d) — (.+?) \((\d+) exercices?")
_RE_THEME = re.compile(r"^\*Thème ([A-Z]) — ")
_RE_OBJ = re.compile(r"^- (M\d\d-\d\d) · (.+?) \((\d+(?:[.,]\d+)?) séances?\)")
_RE_PARTIE = re.compile(r"— partie (\d+)\s*$")


def referentiel_mer(chemin: Path = REF6E_V2) -> dict:
    """{Mnn: {code, nom, theme, exercices, objectifs: [{code, intitule,
    seances, partie}], parties: [numéros]}} d'après la section « Mises en
    route » de ref6e_v2.md ; {} si le fichier manque. v0.53.1 : la partie
    est lue en fin de ligne d'objectif (« — partie n ») ; sans elle, 1
    (référentiel d'avant le 22 octobre)."""
    try:
        lignes = Path(chemin).read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    out, cur, dedans = {}, None, False
    for ligne in lignes:
        if ligne.startswith("## "):
            dedans = ligne.startswith("## Mises en route")
            cur = None
            continue
        if not dedans:
            continue
        m = _RE_TITRE.match(ligne)
        if m:
            cur = out.setdefault(m.group(1), {"code": m.group(1), "nom": m.group(2).strip(),
                                              "theme": "", "exercices": int(m.group(3)),
                                              "objectifs": [], "parties": []})
            continue
        if cur is None:
            continue
        m = _RE_THEME.match(ligne)
        if m:
            cur["theme"] = m.group(1)
            continue
        m = _RE_OBJ.match(ligne)
        if m:
            mp = _RE_PARTIE.search(ligne)
            partie = int(mp.group(1)) if mp else 1
            cur["objectifs"].append({"code": m.group(1), "intitule": m.group(2).strip(),
                                     "seances": float(m.group(3).replace(",", ".")),
                                     "partie": partie})
            if partie not in cur["parties"]:
                cur["parties"].append(partie)
    for s in out.values():
        s["parties"].sort()
    return out


def code_attendu(partie: int, rang: int) -> str:
    """Règle du principal (MR1 révisé) : objectifs de la partie p numérotés à
    partir de (p − 1) × 10 + 2 ; `rang` = 0 pour le premier de la partie."""
    return f"{(partie - 1) * 10 + 2 + rang:02d}"


def anciens_codes(ref_seq: dict) -> dict:
    """I-MR7 — {ancien code (« 01 »…), nouveau code (« 02 »…)} : rang de
    l'objectif dans la séquence (structure de la v0.53.0, une partie,
    objectifs 01…0k) → code au référentiel (table « Anciens codes » de
    ref6e_v2, décision du 22 octobre 2026)."""
    return {f"{i:02d}": o["code"][-2:]
            for i, o in enumerate(ref_seq.get("objectifs") or [], start=1)}


_RE_DEF = re.compile(r"\\(?:newcommand|providecommand|renewcommand|DeclareRobustCommand)\*?"
                     r"\s*\{?\s*\\([A-Za-z@]+)|\\def\s*\\([A-Za-z@]+)|"
                     r"\\(?:newenvironment|NewDocumentEnvironment)\s*\{([A-Za-z@]+)\}|"
                     r"\\NewDocumentCommand\s*\{?\s*\\([A-Za-z@]+)")


def macros_definies(texte: str) -> list[str]:
    """Noms (sans barre oblique) des macros et environnements définis par
    `macros_locales` (commentaires ignorés)."""
    sans = "\n".join(l.split("%", 1)[0] if not l.lstrip().startswith("%") else ""
                     for l in (texte or "").splitlines())
    out = []
    for m in _RE_DEF.finditer(sans):
        nom = next(g for g in m.groups() if g)
        if nom not in out:
            out.append(nom)
    return out


def est_lot_mer(lot: dict) -> bool:
    from services.mises_en_route_6e import est_sequence_mer
    return est_sequence_mer(lot.get("sequence"))


def controler_format(lot: dict) -> list[str]:
    """Écarts au format v2 (clés obligatoires, types) ; [] si conforme."""
    if "fiche_cours" in lot and "parties" not in lot:
        return ["format de la v0.53.0 (fiche_cours au premier niveau, sans « parties ») : "
                "attendu le format v2 du 22 octobre 2026 (une fiche de cours par partie)"]
    err = [f"clé « {k} » absente" for k in CLES_OBLIGATOIRES if k not in lot]
    if lot.get("type") not in (None, "mise_en_route"):
        err.append(f"type {lot.get('type')!r} (attendu « mise_en_route »)")
    for k in ("parties", "objectifs", "exercices_seance", "evaluations",
              "evaluations_retirees", "activites_complementaires"):
        if k in lot and not isinstance(lot[k], list):
            err.append(f"« {k} » n'est pas une liste")
    for i, p in enumerate(lot.get("parties") or [] if isinstance(lot.get("parties"), list)
                          else [], start=1):
        if not isinstance(p, dict) or not isinstance(p.get("numero"), int):
            err.append(f"partie n° {i} sans « numero » entier")
        elif "fiche_cours" in p and not isinstance(p["fiche_cours"], dict):
            err.append(f"partie {p['numero']} : « fiche_cours » n'est pas un objet")
    for o in lot.get("objectifs") or [] if isinstance(lot.get("objectifs"), list) else []:
        if not isinstance(o, dict) or not isinstance(o.get("partie"), int):
            err.append(f"objectif {(o or {}).get('code', '?')} sans « partie » entière")
    for i, e in enumerate(lot.get("exercices_seance") or []
                          if isinstance(lot.get("exercices_seance"), list) else [], start=1):
        if not isinstance(e, dict) or "seance" not in e or "objectif" not in e:
            err.append(f"exercice de séance n° {i} sans « seance » ou « objectif »")
    return err


def _sequence_cycle(conn, imp, code: str, nom: str, theme_id: str | None, rapport) -> None:
    """I-MR2 — séquence du cycle 3 `Mnn` (numéro 200 + n)."""
    from services.mises_en_route_6e import NUMERO_CYCLE_BASE, numero_mer
    numero = NUMERO_CYCLE_BASE + numero_mer(code)
    r = conn.execute("SELECT * FROM sequences_du_cycle WHERE cycle_code=? AND code=?",
                     (imp.CYCLE, code)).fetchone()
    if r is None:
        conn.execute("INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, "
                     "theme_id) VALUES (?,?,?,?,?,?)",
                     (imp._nid("sc"), imp.CYCLE, code, numero, nom, theme_id))
        etat = "créée"
    elif (r["numero"], r["nom"], r["theme_id"]) != (numero, nom, theme_id):
        conn.execute("UPDATE sequences_du_cycle SET numero=?, nom=?, theme_id=? WHERE id=?",
                     (numero, nom, theme_id, r["id"]))
        etat = "mise à jour"
    else:
        etat = "inchangée"
    rapport.cycle.append(f"mise en route {code} {nom} : {etat}")


def _libelle_partie(conn, pid: str, libelle: str) -> str:
    """P1 — libellé d'une partie ; '' si inchangé, sinon « libellé … »."""
    r = conn.execute("SELECT libelle FROM sequence_parties WHERE id=?", (pid,)).fetchone()
    if r is None or (r[0] or "") == libelle:
        return ""
    conn.execute("UPDATE sequence_parties SET libelle=? WHERE id=?", (libelle, pid))
    return "libellé " + ("posé" if not r[0] else "mis à jour")


# ── I-MR7 Restructuration des séquences importées avec l'ancienne structure ──

def _elements_valides(conn, imp, seq: str, sn_id: str) -> list[str]:
    """Ce qui est validé dans une séquence Mnn (I-MR7 : rien n'est alors
    touché)."""
    out = []
    r = conn.execute("SELECT etat_code FROM sequences_par_niveau WHERE id=?", (sn_id,)).fetchone()
    if r and r[0] == "valide":
        out.append("séquence-niveau")
    for (serie, num) in conn.execute(
            "SELECT serie_code, num FROM exercices WHERE niveau=? AND sequence=? AND "
            "serie_code IN ('MR', 'EV') AND etat_code='valide' ORDER BY serie_code, num",
            (imp.NIVEAU, seq)):
        out.append(f"{serie}{int(num):02d}")
    for (titre,) in conn.execute("SELECT titre FROM fiches_resume WHERE niveau=? AND "
                                 "sequence=? AND etat_code='valide'", (imp.NIVEAU, seq)):
        out.append(f"fiche « {titre} »")
    from services.mises_en_route_6e import tests_courts
    for t in tests_courts(conn, imp.NIVEAU, seq):
        r = conn.execute("SELECT etat_code FROM evaluations WHERE id=?", (t["id"],)).fetchone()
        if r and r[0] == "valide":
            out.append(f"test « {t['titre']} »")
    return out


def restructurer_anciennes_mer(conn, imp, ref_mer: dict, rapport) -> list[str]:
    """I-MR7 — Séquences N09/Mnn importées avec la structure de la v0.53.0
    (une partie, objectifs 01…0k) : parties et codes de ref6e_v2, en gardant
    les objectifs (donc exercices MR, liens, fiche, tests). Retourne les
    séquences restructurées."""
    from services import mises_en_route_6e as mer
    faites = []
    for r in conn.execute("SELECT id, sequence_code FROM sequences_par_niveau WHERE niveau=? "
                          "ORDER BY sequence_code", (imp.NIVEAU,)).fetchall():
        sn_id, seq = r[0], r[1]
        if not mer.est_sequence_mer(seq) or seq not in ref_mer:
            continue
        ref = ref_mer[seq]
        objs = conn.execute(
            "SELECT o.id, o.code, o.partie_id, p.numero FROM objectifs o JOIN sequence_parties p "
            "ON p.id = o.partie_id WHERE p.sequence_par_niveau_id=? ORDER BY o.code",
            (sn_id,)).fetchall()
        codes = [o[1] for o in objs]
        table = anciens_codes(ref)
        nouveaux = [o["code"][-2:] for o in ref["objectifs"]]
        if not codes or codes == sorted(nouveaux) or "01" not in codes:
            continue                                    # déjà à la nouvelle structure
        if codes != sorted(table) or set(table.values()) == set(table):
            rapport.anomalie(f"{seq} : objectifs {', '.join(codes)} en base, ni l'ancienne "
                             f"structure ({', '.join(sorted(table))}) ni la nouvelle "
                             f"({', '.join(nouveaux)}) : non restructurée, à vérifier")
            continue
        valides = _elements_valides(conn, imp, seq, sn_id)
        if valides:
            rapport.anomalie(f"{seq} : ancienne structure (une partie, {seq}-01 à "
                             f"{seq}-{codes[-1]}) mais élément(s) validé(s) "
                             f"({', '.join(valides)}) : rien n'est touché ; repasser « en "
                             "cours » pour restructurer")
            continue
        partie_de_code = {o["code"][-2:]: o["partie"] for o in ref["objectifs"]}
        pids = {}
        for n in ref["parties"]:
            pids[n] = imp._partie(conn, sn_id, n, seq, rapport)
        # Deux temps (contrainte UNIQUE (partie_id, code)) : codes provisoires,
        # puis codes et parties définitifs ; identifiants inchangés.
        for o in objs:
            conn.execute("UPDATE objectifs SET code=? WHERE id=?", ("~" + o[1], o[0]))
        corresp = []
        for o in objs:
            nouveau = table[o[1]]
            p = partie_de_code[nouveau]
            conn.execute("UPDATE objectifs SET code=?, partie_id=? WHERE id=?",
                         (nouveau, pids[p], o[0]))
            corresp.append({"objectif_id": o[0], "ancien_code": o[1], "nouveau_code": nouveau,
                            "ancienne_partie_id": o[2], "nouvelle_partie": p})
        vides = [p for (p,) in conn.execute(
            "SELECT p.id FROM sequence_parties p WHERE p.sequence_par_niveau_id=? AND NOT "
            "EXISTS (SELECT 1 FROM objectifs o WHERE o.partie_id = p.id)", (sn_id,))]
        rapport.journal.setdefault("restructuration", []).append(
            {"sequence": f"{imp.NIVEAU}/{seq}", "objectifs": corresp,
             "parties": {str(n): pid for n, pid in pids.items()}, "parties_vides": vides})
        rapport.seq(seq)["lignes"].append(
            f"ancienne structure (une partie, {seq}-01 à {seq}-{codes[-1]}) restructurée en "
            f"{len(ref['parties'])} partie(s) : "
            + ", ".join(f"{seq}-{c['ancien_code']} → {seq}-{c['nouveau_code']} (partie "
                        f"{c['nouvelle_partie']})" for c in corresp)
            + " ; mêmes objectifs : exercices MR, liens, fiche et tests gardés")
        rapport.infos.append(f"{seq} : restructurée (I-MR7), correspondances dans le journal "
                             "(« restructuration »)")
        faites.append(seq)
    return faites


# ── Fiches de cours par partie (I-MR3) ──────────────────────────────────────

MARQUE_SECTION = "\\seqSectionFicheSix"


def est_fiche_entiere(latex: str) -> bool:
    """MR4 — `latex_corrige` est une fiche entière (sections) plutôt qu'une
    note de corrigé."""
    return MARQUE_SECTION in (latex or "")


def sections_fiche_cours(imp, latex: str, note: str = "") -> list[dict]:
    r"""Sections de la fiche de cours ; `note` (MR4, note de corrigé) : une
    dernière section sans titre, `\seqLocExplication{note}`."""
    sections = imp.sections_fiche(latex or "")
    if (note or "").strip():
        sections.append({"titre": "", "items": ["\\seqLocExplication{" + note.strip() + "}"]})
    return sections


def _fiches_de_partie(conn, imp, seq: str, objectif_ids: list[str]) -> list:
    """Fiches sans objectif de la séquence attachées à un objectif de la
    partie (P2)."""
    if not objectif_ids:
        return []
    q = ",".join("?" * len(objectif_ids))
    return conn.execute(
        "SELECT DISTINCT f.id, f.titre, f.etat_code, f.num_fiche FROM fiches_resume f JOIN "
        f"objectif_fiches x ON x.fiche_id = f.id WHERE f.niveau=? AND f.sequence=? AND "
        f"f.objectif_id IS NULL AND x.objectif_id IN ({q}) ORDER BY f.num_fiche, f.id",
        (imp.NIVEAU, seq, *objectif_ids)).fetchall()


def _attacher(conn, fid: str, objectif_ids: list[str]) -> int:
    """P2 — la fiche attachée exactement aux objectifs de sa partie ; nombre
    de liens changés."""
    from services import fiches_resume as svc
    avant = {r[0] for r in conn.execute("SELECT objectif_id FROM objectif_fiches WHERE "
                                        "fiche_id=?", (fid,))}
    n = 0
    for oid in objectif_ids:
        if oid not in avant:
            svc.attacher_fiche_a_objectif(conn, objectif_id=oid, fiche_id=fid)
            n += 1
    for oid in avant - set(objectif_ids):
        svc.detacher_fiche_de_objectif(conn, objectif_id=oid, fiche_id=fid)
        n += 1
    return n


def _fiche_de_partie(conn, imp, seq: str, objectif_ids: list[str], titre: str, latex: str,
                     complete: bool, note: str = ""):
    """(id, état) de la fiche de cours de la partie (complete=False) ou de sa
    version complète (MR4)."""
    from services import fiches_resume as svc
    from services.mises_en_route_6e import SUFFIXE_COMPLETE
    sections = sections_fiche_cours(imp, latex, note)
    titre = titre + (SUFFIXE_COMPLETE if complete else "")
    cible = next((r for r in _fiches_de_partie(conn, imp, seq, objectif_ids)
                  if (r["titre"] or "").endswith(SUFFIXE_COMPLETE) == complete), None)
    if cible is None:
        f = svc.creer_fiche(conn, niveau=imp.NIVEAU, sequence=seq, titre=titre,
                            sections=sections)
        fid, etat = f["id"], "créée"
        _attacher(conn, fid, objectif_ids)
    else:
        fid = cible["id"]
        actuelle = svc.lire_fiche(conn, fid)
        meme = (actuelle["titre"] == titre and [(s["titre"], s["items"])
                                                 for s in actuelle["sections"]]
                == [(s["titre"], s["items"]) for s in sections])
        liens = _attacher(conn, fid, objectif_ids)
        if meme:
            return fid, ("inchangée" if not liens else "rattachée à sa partie")
        if cible["etat_code"] == "valide":
            return fid, "validée, non modifiée"
        svc.modifier_fiche(conn, fid, titre=titre, sections=sections)
        etat = "mise à jour"
    if "mtime" in imp._cols(conn, "fiches_resume"):
        conn.execute("UPDATE fiches_resume SET mtime=? WHERE id=?", (imp._maintenant(), fid))
    return fid, etat


def _retirer_fiche(conn, imp, seq: str, r, motif: str, rapport) -> None:
    from services import fiches_resume as svc
    if r["etat_code"] == "valide":
        rapport.anomalie(f"{seq} : fiche « {r['titre']} » validée, gardée ({motif})")
        return
    rapport.journal["import"].append({"cle": f"{imp.NIVEAU}/{seq}/fiche", "id": r["id"],
                                      "titre": r["titre"], "retiree": True, "motif": motif})
    svc.supprimer_fiche(conn, r["id"])
    rapport.seq(seq)["lignes"].append(f"fiche « {r['titre']} » retirée ({motif})")


def _retirer_fiche_complete(conn, imp, seq: str, objectif_ids: list[str], rapport) -> None:
    """I-MR3 — plus de `latex_corrige` distinct pour la partie : sa fiche
    « version complète » est retirée (sauf validée)."""
    from services.mises_en_route_6e import SUFFIXE_COMPLETE
    for r in _fiches_de_partie(conn, imp, seq, objectif_ids):
        if (r["titre"] or "").endswith(SUFFIXE_COMPLETE):
            _retirer_fiche(conn, imp, seq, r, "le lot n'a plus de version complète distincte",
                           rapport)


def _retirer_fiches_de_sequence(conn, imp, seq: str, rapport) -> None:
    """I-MR3 — anciennes fiches de séquence (sans objectif, attachées à aucun
    objectif : v0.53.0) : retirées, le lot v2 donne une fiche par partie."""
    for r in conn.execute(
            "SELECT id, titre, etat_code FROM fiches_resume f WHERE niveau=? AND sequence=? AND "
            "objectif_id IS NULL AND NOT EXISTS (SELECT 1 FROM objectif_fiches x WHERE "
            "x.fiche_id = f.id) ORDER BY num_fiche, id", (imp.NIVEAU, seq)).fetchall():
        _retirer_fiche(conn, imp, seq, r, "ancienne fiche de séquence : une fiche de cours "
                       "par partie désormais", rapport)


_RE_ENV = re.compile(r"\\(begin|end)\s*\{([^}]+)\}")


def _bonus_du_sujet(imp, latex: str) -> float:
    """v0.53.2 — points des exercices « Bonus… » du sujet (0 si illisible)."""
    try:
        return sum(x["points"] for x in imp.decouper_evaluation(latex) if imp._est_bonus(x))
    except Exception:
        return 0.0


def exercices_desequilibres(imp, latex: str) -> list[tuple[str, str]]:
    r"""I-MR5 (v0.53.1) — [(titre, environnements)] des exercices d'un test
    dont le corps n'équilibre pas ses \begin / \end : le rendu découpe le
    sujet à chaque \seqExoEval et rend chaque exercice seul (cas réel : deux
    exercices côte à côte dans des minipage ouvertes avant le premier)."""
    try:
        exos = imp.decouper_evaluation(latex)
    except Exception:
        return []
    out = []
    for x in exos:
        pile, mauvais = [], []
        for m in _RE_ENV.finditer(x["corps"]):
            if m.group(1) == "begin":
                pile.append(m.group(2))
            elif pile and pile[-1] == m.group(2):
                pile.pop()
            else:
                mauvais.append(m.group(2))
        if pile or mauvais:
            out.append((x["titre"], ", ".join(dict.fromkeys(mauvais + pile))))
    return out


def _sequence_de_l_evaluation(conn, ev_id: str) -> str:
    """Séquence majoritaire des exercices d'une évaluation ('' sans exercice)."""
    from collections import Counter
    c = Counter(r[0] for r in conn.execute(
        "SELECT e.sequence FROM evaluation_exercices ee JOIN exercices e ON "
        "e.id = ee.exercice_id WHERE ee.evaluation_id = ? AND e.sequence <> ''", (ev_id,)))
    return c.most_common(1)[0][0] if c else ""


def _sans_titres_d_autres_sequences(conn, imp, lot: dict, rapport) -> dict:
    """I-MR5 (v0.53.1) — Une évaluation est retrouvée par son titre dans le
    niveau : un test court dont le titre est déjà celui d'une évaluation d'une
    autre séquence (cas réel : « Test court --- Aires » en M03 et en M04)
    réécrirait celle-ci à chaque import (import non idempotent). Il n'est pas
    importé (signalé : renommer dans le lot) ; de même, un titre de
    `evaluations_retirees` qui désigne l'évaluation d'une autre séquence
    n'est pas retiré."""
    seq = lot["sequence"]

    def autre(titre: str) -> str:
        for (ev_id,) in conn.execute("SELECT id FROM evaluations WHERE niveau = ? AND "
                                     "titre = ?", (imp.NIVEAU, titre)):
            s = _sequence_de_l_evaluation(conn, ev_id)
            if s and s != seq:
                return s
        return ""

    garde, refuses = [], {}
    for ev in lot.get("evaluations") or []:
        t = ev.get("titre", "")
        if t not in refuses:
            refuses[t] = autre(t)
        if refuses[t]:
            continue
        garde.append(ev)
    for t, s in refuses.items():
        if s:
            rapport.anomalie(f"{seq} test court « {t} » non importé : ce titre est celui d'une "
                             f"évaluation de {s} (une évaluation est retrouvée par son titre) — "
                             "renommer le test dans le lot")
    retirees = []
    for t in lot.get("evaluations_retirees") or []:
        s = autre(t)
        if s:
            rapport.anomalie(f"{seq} évaluation à retirer « {t} » : c'est une évaluation de {s}, "
                             "gardée")
        else:
            retirees.append(t)
    return dict(lot, evaluations=garde, evaluations_retirees=retirees)


# ── Import d'un lot ──────────────────────────────────────────────────────────

def importer_lot_mer(conn, imp, lot: dict, themes: dict, ref_mer: dict, rapport) -> set:
    """Importe un lot de mise en route (format v2) ; retourne les figures
    utilisées. `imp` : le module outils/import_lot6e (fonctions communes)."""
    from services import mises_en_route_6e as mer
    seq = lot["sequence"]
    figures: set = set()
    sr = rapport.seq(seq)
    ecarts = controler_format(lot)
    if ecarts:
        rapport.anomalie(f"{seq} : lot non conforme au format des mises en route "
                         f"({' ; '.join(ecarts)}), non importé")
        return figures
    ref = ref_mer.get(seq)
    if ref is None:
        rapport.infos.append(f"{seq} : mise en route absente de ref6e_v2.md, le lot fait foi")
    nom = (ref or {}).get("nom") or lot.get("titre") or seq
    theme = (ref or {}).get("theme") or lot.get("theme") or ""
    if ref and lot.get("titre") and lot["titre"] != nom:
        rapport.infos.append(f"{seq} : titre du lot « {lot['titre']} » ≠ référentiel « {nom} » "
                             "(référentiel retenu)")
    if ref and lot.get("theme") and lot["theme"] != theme:
        rapport.anomalie(f"{seq} : thème {lot['theme']} dans le lot, {theme} dans le "
                         "référentiel (référentiel retenu)")
    if theme not in themes:
        rapport.anomalie(f"{seq} : thème {theme!r} inconnu du cycle 3, séquence sans thème")
    sr["lignes"].append(f"mise en route {nom} (lot : « {lot.get('titre', '')} »)")
    definies = macros_definies(lot.get("macros_locales") or "")       # I-MR6
    if definies:
        from services.style6e import MACROS as MACROS_STYLE6E
        absentes = [m for m in definies if m not in MACROS_STYLE6E]
        if absentes:
            rapport.anomalie(f"{seq} : macros_locales définit {', '.join(absentes)}, absente(s) "
                             "du module seqenseigne-style6e (non importées : à verser dans le "
                             "module)")
        fournies = [m for m in definies if m in MACROS_STYLE6E]
        if fournies:
            rapport.infos.append(f"{seq} : macros_locales du lot fournies par le module "
                                 f"seqenseigne-style6e : {', '.join(fournies)}")
    elif (lot.get("macros_locales") or "").strip() and \
            re.search(r"\\(?:newcommand|providecommand|def)\b", lot["macros_locales"]):
        rapport.anomalie(f"{seq} : macros_locales illisible, à vérifier")
    _sequence_cycle(conn, imp, seq, nom, themes.get(theme), rapport)
    sn = imp._seq_niveau(conn, seq, rapport)
    if sn is None:
        return figures

    # Parties (MR1 révisé, P1) : celles du référentiel, libellés du lot.
    lot_parties = {p["numero"]: p for p in lot.get("parties") or []}
    numeros = list((ref or {}).get("parties") or []) or sorted(
        {o["partie"] for o in lot.get("objectifs") or []} | set(lot_parties))
    for n in sorted(set(lot_parties) - set(numeros)):
        rapport.anomalie(f"{seq} : partie {n} du lot absente du référentiel, ignorée")
    pids: dict = {}
    for n in numeros:
        pids[n] = imp._partie(conn, sn["id"], n, seq, rapport)
        lib = (lot_parties.get(n, {}).get("titre") or "").strip()
        etat = _libelle_partie(conn, pids[n], lib)
        if etat:
            sr["lignes"].append(f"partie {n} « {lib} » : {etat}")
        if n not in lot_parties:
            rapport.anomalie(f"{seq} : partie {n} du référentiel absente du lot (ni libellé ni "
                             "fiche de cours)")

    # Objectifs (I-MR1, I-MR2).
    ref_objs = {o["code"]: o for o in (ref or {}).get("objectifs", [])}
    objectifs_ids: dict = {}
    partie_obj: dict = {}
    vus_obj = set()
    for o in lot.get("objectifs") or []:
        code = (o.get("code") or "").strip()
        if not re.fullmatch(rf"{seq}-\d\d", code):
            rapport.anomalie(f"{seq} : code d'objectif {code!r} invalide (attendu {seq}-nn), "
                             "ignoré")
            continue
        if ref and code not in ref_objs:
            rapport.anomalie(f"{seq} : objectif {code} absent de ref6e_v2.md, ignoré avec ses "
                             "exercices")
            continue
        r = ref_objs.get(code, {})
        partie = r.get("partie") or o.get("partie")
        if r and o.get("partie") != r["partie"]:
            rapport.anomalie(f"{code} : partie {o.get('partie')} dans le lot, {r['partie']} "
                             "dans le référentiel (référentiel retenu)")
        if partie not in pids:
            rapport.anomalie(f"{code} : partie {partie!r} inconnue, objectif ignoré")
            continue
        intitule = r.get("intitule") or (o.get("intitule") or "").strip()
        seances = r.get("seances") if r else o.get("seances")
        if r and (o.get("intitule") or intitule) != intitule:
            rapport.infos.append(f"{code} : intitulé du lot différent du référentiel "
                                 "(référentiel retenu)")
        if r and o.get("seances") not in (None, "") and float(o["seances"]) != r["seances"]:
            rapport.anomalie(f"{code} : {o['seances']} séance(s) dans le lot, "
                             f"{mer._fmt(r['seances'])} dans le référentiel (référentiel retenu)")
        crit = o.get("criteres") or {}
        d = {"nom": intitule, "critere_F": (crit.get("F") or "").strip(),
             "critere_A": (crit.get("A") or "").strip(), "critere_E": ""}
        oid, etat = imp._objectif(conn, sn["id"], pids[partie], code[-2:], d, rapport, code,
                                  source="ref6e_v2.md et le lot")
        try:
            nb = float(seances or 0)
        except (TypeError, ValueError):
            nb = 0.0
        if float(conn.execute("SELECT nb_seances FROM objectifs WHERE id=?",
                              (oid,)).fetchone()[0] or 0) != nb:
            conn.execute("UPDATE objectifs SET nb_seances=? WHERE id=?", (nb, oid))
            if etat == "inchangé":
                etat = "mis à jour"
        ro = rapport.obj(seq, code, intitule)
        ro["objectif"] = etat + (f" (partie {partie})" if len(numeros) > 1 else "")
        objectifs_ids[code] = oid
        partie_obj[code] = partie
        vus_obj.add(code)
    for code in ref_objs:
        if code not in vus_obj:
            rapport.anomalie(f"{code} : objectif du référentiel sans contenu dans le lot")
    obj_de_partie = {n: [objectifs_ids[c] for c in objectifs_ids if partie_obj[c] == n]
                     for n in numeros}

    # Fiches de cours, une par partie (I-MR3).
    _retirer_fiches_de_sequence(conn, imp, seq, rapport)
    for n in numeros:
        fc = (lot_parties.get(n) or {}).get("fiche_cours") or {}
        ids = obj_de_partie.get(n) or []
        if not (fc.get("latex") or "").strip():
            if n in lot_parties:
                rapport.anomalie(f"{seq} partie {n} : pas de fiche de cours dans le lot")
            continue
        if not ids:
            rapport.anomalie(f"{seq} partie {n} : fiche de cours sans objectif importé, non "
                             "importée")
            continue
        titre_fc = ((fc.get("titre") or "").strip()
                    or (lot_parties.get(n) or {}).get("titre") or f"{nom} --- partie {n}")
        corr = (fc.get("latex_corrige") or "").strip()
        if corr == fc["latex"].strip():
            corr = ""
        entiere = bool(corr) and est_fiche_entiere(corr)
        note = "" if entiere else corr
        fid, etat = _fiche_de_partie(conn, imp, seq, ids, titre_fc, fc["latex"], False, note)
        sr["lignes"].append(f"partie {n}, fiche de cours « {titre_fc} » : {etat}"
                            + (" (note de corrigé en version complète)" if note else ""))
        if etat == "validée, non modifiée":
            rapport.anomalie(f"{seq} partie {n} : fiche de cours validée dans l'atelier, non "
                             "modifiée")
        if entiere:
            _, etat2 = _fiche_de_partie(conn, imp, seq, ids, titre_fc, corr, True)
            sr["lignes"].append(f"partie {n}, version complète rédigée à part : {etat2}")
        else:
            _retirer_fiche_complete(conn, imp, seq, ids, rapport)
        figures |= imp._figures(lot, fc) | imp._figures(lot, {"latex": corr})

    # Exercices de séance (I-MR4).
    liens: dict = {}
    seances_vues: dict = {}
    formats: dict = {}
    formats_notes: list = []
    for e in lot.get("exercices_seance") or []:
        try:
            n = int(e.get("seance"))
        except (TypeError, ValueError):
            rapport.anomalie(f"{seq} : exercice « {e.get('titre', '')} » sans numéro de séance, "
                             "ignoré")
            continue
        oc = (e.get("objectif") or "").strip()
        if n in seances_vues:
            rapport.anomalie(f"{seq} séance {n} en double ({e.get('titre', '')}), second ignoré")
            continue
        if oc not in objectifs_ids:
            rapport.anomalie(f"{seq} séance {n} : objectif {oc!r} inconnu, exercice ignoré")
            continue
        seances_vues[n] = oc
        marques = imp.marqueurs_lot(e, f"{seq} MR{n:02d}", rapport)
        imp._compter_marqueurs(rapport, seq, marques)
        eid, etat = imp._exercice(conn, seq, mer.SERIE_MR, n, e, marques)
        fmt, origine_fmt = mer.format_depuis_lot(e)                    # F1 (v0.53.1)
        if origine_fmt == "invalide":
            rapport.anomalie(f"{seq} MR{n:02d} : format {e.get('format')!r} inconnu (attendu "
                             "« quart » ou « demi ») : quart d'A4")
        if etat != "validé, non modifié" and mer.colonne_format_presente(conn):
            voulu = "" if fmt == "quart" else fmt
            if (conn.execute("SELECT format_planche FROM exercices WHERE id=?",
                             (eid,)).fetchone()[0] or "") != voulu:
                conn.execute("UPDATE exercices SET format_planche=? WHERE id=?", (voulu, eid))
                if etat == "inchangé":
                    etat = "mis à jour"
        formats[fmt] = formats.get(fmt, 0) + 1
        if origine_fmt == "notes":
            formats_notes.append(n)
        Rapport = type(rapport)
        Rapport.compter(rapport.obj(seq, oc), "exercices de séance MR", etat)
        if etat == "validé, non modifié":
            rapport.anomalie(f"{imp.NIVEAU}/{seq}/MR{n:02d} validé dans l'atelier : contenu du "
                             "lot non appliqué")
        oid = objectifs_ids[oc]
        conn.execute("DELETE FROM objectif_exos WHERE exercice_id=? AND serie=? AND "
                     "objectif_id<>?", (eid, mer.SERIE_MR, oid))
        liens.setdefault((oid, mer.SERIE_MR), []).append(eid)
        figures |= imp._figures(lot, e)
        rapport.journal["import"].append({"cle": f"{imp.NIVEAU}/{seq}/MR{n:02d}", "id": eid,
                                          "objectif": oc, "seance": n,
                                          "origine": e.get("origine", ""),
                                          "notes": e.get("notes", "")})
    if seances_vues:
        attendu = set(range(1, max(seances_vues) + 1))
        trous = sorted(attendu - set(seances_vues))
        if trous:
            rapport.anomalie(f"{seq} : séance(s) sans exercice : {', '.join(map(str, trous))}")
        rangs = [partie_obj[seances_vues[k]] for k in sorted(seances_vues)]
        if rangs != sorted(rangs):
            rapport.infos.append(f"{seq} : séances numérotées hors de l'ordre des parties "
                                 "(format v2 : dans l'ordre des parties puis des séances)")
    n_liens = imp._lier_objectifs(conn, liens)
    if n_liens:
        sr["lignes"].append(f"exercices de séance : {n_liens} lien(s) objectif créé(s)")
    for (num,) in conn.execute("SELECT num FROM exercices WHERE niveau=? AND sequence=? AND "
                               "serie_code=? ORDER BY num", (imp.NIVEAU, seq, mer.SERIE_MR)):
        if num not in seances_vues:
            rapport.anomalie(f"{imp.NIVEAU}/{seq}/MR{int(num):02d} en base sans séance dans le "
                             "lot (gardé)")
    sr["lignes"].append(f"exercices de séance : {len(seances_vues)} (MR01 à "
                        f"MR{max(seances_vues or [0]):02d})"
                        + (f" — format : {formats.get('quart', 0)} quart(s) d'A4, "
                           f"{formats.get('demi', 0)} demi-A4" if formats.get("demi") else ""))
    if formats_notes:
        rapport.infos.append(f"{seq} : format demi-A4 déduit des notes (clé « format » absente) "
                             f"pour les séances {', '.join(map(str, formats_notes))}")

    # Tests courts, un par partie (I-MR5).
    parties_testees = set()
    for ev in lot.get("evaluations") or []:
        tot = ev.get("total")
        if tot not in (None, "") and float(tot) != TOTAL_TEST_COURT:
            rapport.anomalie(f"{seq} « {ev.get('titre', '')} » sujet {ev.get('sujet', '?')} : "
                             f"total {tot}, un test court est sur {TOTAL_TEST_COURT}")
        hors_bonus = sum(float(pts) for oc, pts in (ev.get("bareme") or []) if oc != "Bonus")
        bonus = sum(float(pts) for oc, pts in (ev.get("bareme") or []) if oc == "Bonus")
        if ev.get("bareme") and hors_bonus != TOTAL_TEST_COURT:
            rapport.anomalie(f"{seq} « {ev.get('titre', '')} » sujet {ev.get('sujet', '?')} : "
                             f"barème {hors_bonus:g} points hors bonus, un test court est sur "
                             f"{TOTAL_TEST_COURT}")
        for b in sorted({x for x in (bonus, _bonus_du_sujet(imp, ev.get("latex") or ""))
                         if x and x != BONUS_TEST_COURT}):
            rapport.anomalie(f"{seq} « {ev.get('titre', '')} » sujet {ev.get('sujet', '?')} : "
                             f"bonus de {b:g} point(s), un test court a un bonus de "
                             f"{BONUS_TEST_COURT} point (décision du 25 octobre 2026) — à "
                             "corriger dans le lot")
        ps = {partie_obj.get(oc) for oc, _ in (ev.get("bareme") or [])
              if oc != "Bonus" and oc in partie_obj}
        if len(ps) > 1:
            rapport.anomalie(f"{seq} « {ev.get('titre', '')} » sujet {ev.get('sujet', '?')} : "
                             f"objectifs de plusieurs parties ({', '.join(map(str, sorted(ps)))}) "
                             "— un test court par partie")
        elif ps and ev.get("partie") not in (None, "") and ev["partie"] not in ps:
            rapport.anomalie(f"{seq} « {ev.get('titre', '')} » sujet {ev.get('sujet', '?')} : "
                             f"partie {ev['partie']} dans le lot, mais barème de la partie "
                             f"{next(iter(ps))} (la partie suit le barème)")
        parties_testees |= ps
        figures |= imp._figures(lot, ev)
        for x in exercices_desequilibres(imp, ev.get("latex") or ""):    # I-MR5 (v0.53.1)
            rapport.anomalie(f"{seq} « {ev.get('titre', '')} » sujet {ev.get('sujet', '?')}, "
                             f"exercice « {x[0]} » : environnement(s) {x[1]} ouvert(s) ou fermé(s) "
                             "hors de l'exercice (chaque exercice est rendu seul : compilation "
                             "impossible) — mise en page à revoir dans le lot")
    sans_test = [n for n in numeros if obj_de_partie.get(n) and n not in parties_testees]
    if sans_test and lot.get("evaluations"):
        rapport.anomalie(f"{seq} : partie(s) sans test court dans le lot : "
                         f"{', '.join(map(str, sans_test))}")
    imp.importer_evaluations(conn, _sans_titres_d_autres_sequences(conn, imp, lot, rapport),
                             objectifs_ids, rapport)
    figures |= importer_activites_complementaires(conn, imp, lot, objectifs_ids, rapport)

    # Contrôle MR6 (par partie).
    v = mer.valider_sequence_mer(conn, imp.NIVEAU, seq)
    sr["lignes"].append("contrôle de la séquence : "
                        + ("complète" if v["valide"] else "à compléter — "
                           + " ; ".join(v["erreurs"]))
                        + ("" if not v["avertissements"]
                           else " (attention : " + " ; ".join(v["avertissements"]) + ")"))
    return figures


def activites_du_lot(lot: dict) -> list[dict]:
    """I-MR8 — activités complémentaires du lot, `objectif` (code) ramené à
    `objectifs` (liste, format des lots S)."""
    out = []
    for a in lot.get("activites_complementaires") or []:
        if not isinstance(a, dict):
            continue
        objs = list(a.get("objectifs") or [])
        if isinstance(a.get("objectif"), str) and a["objectif"].strip():
            objs = [a["objectif"].strip()] + [o for o in objs if o != a["objectif"].strip()]
        out.append(dict(a, objectifs=objs))
    return out


def importer_activites_complementaires(conn, imp, lot: dict, objectifs_ids: dict,
                                       rapport) -> set:
    """I-MR8 — série AC d'une mise en route (import commun des documents des
    lots S) ; retourne les figures utilisées."""
    seq = lot["sequence"]
    for cle in ("travaux_personnels", "seances_atelier"):
        if lot.get(cle):
            rapport.anomalie(f"{seq} : « {cle} » n'existe pas dans une mise en route (seules les "
                             "activités complémentaires, série AC), ignoré")
    acs = activites_du_lot(lot)
    if not acs:
        return set()
    for k, a in enumerate(acs, start=1):
        if not a["objectifs"]:
            rapport.anomalie(f"{seq} AC{k:02d} « {a.get('titre', '')} » : sans objectif (clé "
                             "« objectif ») — une activité complémentaire est rattachée à un "
                             "objectif de la séquence")
    figures = imp.importer_documents(conn, {"sequence": seq, "activites_complementaires": acs},
                                     objectifs_ids, rapport)
    rapport.seq(seq)["lignes"].append(
        f"activités complémentaires : {len(acs)} (AC01 à AC{len(acs):02d}) — "
        + ", ".join(f"AC{k:02d} → {', '.join(a['objectifs']) or 'aucun objectif'}"
                    for k, a in enumerate(acs, start=1))
        + " ; hors contrôle de la séquence")
    return figures


def figures_du_lot(imp, lot: dict) -> set:
    """Figures des éléments d'un lot de mise en route (pour --apply)."""
    noms: set = set()
    for p in lot.get("parties") or []:
        fc = (p or {}).get("fiche_cours") or {}
        noms |= imp._figures(lot, fc) | imp._figures(lot, {"latex": fc.get("latex_corrige")
                                                            or ""})
    for e in lot.get("exercices_seance") or []:
        noms |= imp._figures(lot, e)
    for ev in lot.get("evaluations") or []:
        noms |= imp._figures(lot, ev)
    for a in activites_du_lot(lot):                                   # v0.53.2 (I-MR8)
        noms |= imp._figures(lot, a)
    return noms
