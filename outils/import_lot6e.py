#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""outils/import_lot6e.py — v0.52.0, documents en base depuis v0.52.2

Importe les séquences de 6e (lots S01, S02, S03…) dans l'atelier interne
(niveau N09), remplace les séquences du cycle 3 par les treize séquences du
nouveau référentiel et archive, sans rien supprimer, l'ancien découpage.

Ce que fait l'outil (cadrage v0.52.0, `doc/redemarrage_v0_52_0.md`) :

  1. **Archivage** (une seule fois, réversible) — les seize anciennes
     séquences du cycle 3 (`sequences_du_cycle` C03 S01…S16) deviennent
     X01…X16 (numéro 101…116, nom suivi de « (archive) ») ; les anciens
     thèmes A, B, C deviennent XA, XB, XC ; tout ce qui est rattaché aux
     anciens codes en CM1, CM2 et 6e (exercices — dont les 411 de 6e —,
     notions, méthodes, fiches, cartes, séquences-niveaux, précédences des
     séquences du cycle 3) passe du code Snn au code Xnn. Les identifiants
     ne changent pas : les liens existants (objectifs, évaluations,
     révisions du cycle 4) suivent. Le cycle 4 n'est jamais modifié.
  2. **Cycle 3** — six thèmes (A à F) et treize séquences (S01 à S13) d'après
     `outils/objectifs_6e.json`. Depuis le découpage de la géométrie
     (19 octobre 2026, `doc/redemarrage_v0_52_5.md`) : une base qui a déjà
     les dix séquences de la v0.52.0 est mise à jour sur place (S05 à S10
     renommées, thèmes, S11 à S13 créées ; identifiants inchangés). Une
     séquence dont le nom change alors qu'une séquence-niveau du cycle 3
     existe déjà sous ce code (contenu de l'ancien sens) n'est pas renommée :
     anomalie, et son lot n'est pas importé.
  3. **Import N09** — séquence-niveau, parties, objectifs (dont l'objectif
     « Cours » de chaque partie), exercices F/A/E avec remédiations,
     activités d'introduction (série approche AE, rattachées à la partie
     et, depuis v0.52.2, à leur objectif), fiches de résumé (une par
     objectif, sections), liens objectif ↔ exercice et objectif ↔ fiche,
     figures copiées dans `images\`. Tout est créé « en cours ».
  4. **Documents (v0.52.2, en base)** — travaux personnels, activités
     complémentaires, séances d'atelier : un atome par document dans les
     séries TP, AC, AT de l'atelier d'exercices, numérotés par série dans la
     séquence, reliés aux objectifs visés (objectif_exos). Évaluations et
     tests courts : pour chaque paire de sujets A/B, un atome de série EV
     par exercice (sujet A dans l'énoncé, sujet B dans la remédiation) et
     l'évaluation du module Évaluations (note et critères, barème par
     exercice, objectifs évalués). Une évaluation dont le découpage échoue
     est signalée en anomalie et n'est pas importée. Plus aucun `.tex` n'est
     écrit (les `.tex` de la v0.52.0 restent où ils sont).

  5. **Retrait d'évaluations (v0.52.6)** — un lot peut lister, dans
     `evaluations_retirees`, des titres d'évaluations à retirer (une
     évaluation sur 20 par séquence, décision du 19 octobre) : retirées si
     non validées, puis leurs exercices EV devenus orphelins (décisions R1 à
     R4, `doc/redemarrage_v0_52_6.md`). Le journal de --apply garde de quoi
     les restaurer.

  6. **Marqueurs (v0.52.7)** — clés facultatives `ordinateur` (scratch,
     geogebra, tableur, autre) et `calculatrice` (autorisee, interdite) de
     chaque exercice F, A, E, activité AE, document TP, AC, AT ; pour une
     évaluation, sur l'entrée d'évaluation (sujet A, sinon B), appliquées à
     tous ses exercices EV. Écrites dans `exercices.ordinateur` et
     `exercices.calculatrice` comme le reste du contenu : clé absente = non
     marqué (le lot fait foi), mise à jour idempotente, exercice validé non
     touché (signalé). Une valeur inconnue est signalée et ignorée. Les
     marqueurs n'entrent pas dans la comparaison de contenu qui choisit le
     numéro EV (R2).

  7. **v0.52.8** — Calculatrice des évaluations (C1) : la clé `calculatrice`
     de l'entrée d'évaluation est aussi écrite dans
     `evaluations.calculatrice` (évaluation non validée ; clé absente = '' :
     le sujet suit ses exercices). Critères F, A, E d'un objectif existant
     mis à jour d'après `objectifs_6e.json` (déjà le cas), le détail est
     signalé dans le rapport (O1) ; jamais sur une séquence validée (lot non
     importé). Macros `\seq…Six` du lot absentes du module signalées comme
     les `\seqLoc…` (I2) ; astuces `\seqAstuceSix` comptées par séquence.
  8. **v0.52.9** — Sujet en deux parties (D1 à D5) : clé facultative
     `calculatrice_exercices` de l'entrée d'évaluation,
     `{"<position 1-based>": "interdite" | "autorisee"}` ; les positions non
     listées héritent de `calculatrice` ; même table pour A et B (sujet A,
     sinon B ; tables différentes signalées). Le marquage est écrit sur chaque
     exercice EV (idempotent, jamais sur validé). Décision I3 : une évaluation
     que D1 coupe en deux reçoit `evaluations.calculatrice = ''` (les deux
     mentions sont imposées par D2). L'essai à blanc montre la répartition et
     la durée de la partie 1 (D4).

Idempotence : objectifs repérés par (niveau, séquence, code), exercices et
documents par (niveau, séquence, série, num), fiches par leur objectif,
évaluations par (niveau, titre). Une deuxième exécution ne crée rien ; un
contenu modifié dans le lot est mis à jour (sauf élément validé dans
l'atelier, laissé tel quel et signalé).

Usage (Windows, depuis `appli\`) :
    ..\outils\python\python.exe .\outils\import_lot6e.py                 # essai à blanc
    ..\outils\python\python.exe .\outils\import_lot6e.py --apply         # applique (confirmation)
    ..\outils\python\python.exe .\outils\import_lot6e.py --apply --yes   # sans confirmation
Options : --db CHEMIN (base), --lots DOSSIER (défaut ..\reference\lot6e).
v0.52.2 : --sortie et --documents-seulement retirés (les documents vont en
base ; décision O1, doc/redemarrage_v0_52_2.md).

Codes de sortie : 0 succès / essai, 1 annulé, 2 base ou lots introuvables,
3 erreur (rien n'est écrit : transaction annulée).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import uuid
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

RACINE_APPLI = Path(__file__).resolve().parent.parent
if str(RACINE_APPLI) not in sys.path:          # lancement par chemin (Windows)
    sys.path.insert(0, str(RACINE_APPLI))

from services import fiches_resume as svc_fiches          # noqa: E402
from services.atomes import SERIES_DOCUMENTS, _deduire_type_format  # noqa: E402
from services import marqueurs_exercices as mq                     # noqa: E402

NIVEAU = "N09"
CYCLE = "C03"
NIVEAUX_CYCLE3 = ("N07", "N08", "N09")
ANCIENS_CODES = tuple(f"S{i:02d}" for i in range(1, 17))
REFERENTIEL = Path(__file__).resolve().parent / "objectifs_6e.json"
LOTS_DEFAUT = RACINE_APPLI.parent / "reference" / "lot6e"
SUFFIXE_ARCHIVE = " (archive)"

SERIE_TEXTE = {"F": "fondamental", "A": "avancé", "E": "exploration", "AE": "approche",
               **SERIES_DOCUMENTS}                      # v0.52.2 : EV, TP, AC, AT
# v0.52.2 — Documents du lot rangés dans les séries « documents ».
DOCUMENTS_LOT = (("travaux_personnels", "TP", "travail personnel"),
                 ("activites_complementaires", "AC", "activité complémentaire"),
                 ("seances_atelier", "AT", "séance d'atelier"))
RE_GRAPHIQUE = re.compile(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
RE_LOC = re.compile(r"\\(seqLoc[A-Za-z]+)")
# v0.52.8 (I2) — macros du module de 6e appelées par le lot (\seqAstuceSix…).
RE_SIX = re.compile(r"\\(seq[A-Za-z]*Six)(?![A-Za-z])")


class ImportErreur(Exception):
    pass


def _module_mer():
    """v0.53.0 — outils/import_lot6e_mer.py (lots de mise en route), que
    l'outil soit lancé par chemin ou importé comme `outils.import_lot6e`."""
    try:
        from outils import import_lot6e_mer as m
    except ImportError:
        import import_lot6e_mer as m
    return m


# ── Petits outils ────────────────────────────────────────────────────────────

def code_archive(code: str) -> str:
    """S03 → X03 ; A → XA. Code d'archive d'un ancien code du cycle 3."""
    return "X" + code[1:] if code[:1] == "S" else "X" + code


def _table(conn, nom: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (nom,)).fetchone() is not None


def _cols(conn, table: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _maintenant() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _nid(prefixe: str) -> str:
    return f"{prefixe}_{uuid.uuid4().hex[:8]}"


def _accolade(texte: str, debut: int) -> tuple[str, int]:
    """Contenu de l'argument entre accolades qui commence à `debut` ('{')."""
    assert texte[debut] == "{"
    prof, i = 0, debut
    while i < len(texte):
        c = texte[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            prof += 1
        elif c == "}":
            prof -= 1
            if prof == 0:
                return texte[debut + 1:i], i + 1
        i += 1
    raise ImportErreur("accolade non fermée")


def sections_fiche(latex: str) -> list[dict]:
    r"""Découpe une fiche de résumé du lot en sections de l'atelier Fiche.

    Chaque `\seqSectionFicheSix{titre}` ouvre une section (titre = argument,
    un seul item = le texte qui suit) ; le texte placé avant la première
    section forme une section sans titre."""
    out, pos, titre = [], 0, None
    marque = "\\seqSectionFicheSix"
    while True:
        k = latex.find(marque, pos)
        corps = latex[pos:k if k >= 0 else len(latex)].strip()
        if titre is not None or corps:
            out.append({"titre": titre or "", "items": [corps] if corps else []})
        if k < 0:
            break
        j = k + len(marque)
        while j < len(latex) and latex[j].isspace():
            j += 1
        if j >= len(latex) or latex[j] != "{":
            raise ImportErreur("\\seqSectionFicheSix sans argument")
        titre, pos = _accolade(latex, j)
        titre = titre.strip()
    return out or [{"titre": "", "items": [""]}]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ── Chargement des entrées ───────────────────────────────────────────────────

def charger_referentiel(chemin: Path = REFERENTIEL) -> dict:
    ref = json.loads(Path(chemin).read_text(encoding="utf-8"))
    for cle in ("themes", "sequences", "parties", "objectif_cours"):
        if cle not in ref:
            raise ImportErreur(f"{chemin} : clé « {cle} » absente")
    return ref


def charger_lots(dossier: Path) -> list[dict]:
    """Lots S01/S01.json, S02/S02.json… triés par code de séquence, puis
    (v0.53.0) les lots de mise en route M01/M01.json… (outils/import_lot6e_mer.py)."""
    dossier = Path(dossier)
    lots = []
    for d in sorted((p for p in dossier.iterdir()
                     if p.is_dir() and re.fullmatch(r"[SM]\d\d", p.name)),
                    key=lambda p: (p.name[0] != "S", p.name)):
        f = d / f"{d.name}.json"
        if f.is_file():
            lot = json.loads(f.read_text(encoding="utf-8"))
            if lot.get("sequence") != d.name:
                raise ImportErreur(f"{f} : séquence {lot.get('sequence')!r} ≠ dossier {d.name}")
            lot["_dossier"] = d
            lots.append(lot)
    return lots


# ── Rapport ──────────────────────────────────────────────────────────────────

class Rapport:
    """Compteurs par séquence et par objectif, archivage et anomalies."""

    def __init__(self):
        self.archivage: "OrderedDict[str, int]" = OrderedDict()
        self.cycle: list[str] = []
        self.sequences: "OrderedDict[str, dict]" = OrderedDict()
        self.anomalies: list[str] = []
        self.infos: list[str] = []
        self.figures: list[str] = []
        self.documents: list[str] = []
        self.journal: dict = {"archivage": [], "import": []}
        # Découpage de la géométrie : séquences dont le code a changé de sens
        # alors qu'un contenu de l'ancien sens existe (lot non importé).
        self.sequences_bloquees: set = set()

    def seq(self, code: str) -> dict:
        return self.sequences.setdefault(code, {"lignes": [], "objectifs": OrderedDict(),
                                                "ignores": []})

    def obj(self, seq: str, code: str, nom: str = "") -> dict:
        o = self.seq(seq)["objectifs"].setdefault(code, {"nom": nom, "objectif": "",
                                                         "c": {}})
        if nom:
            o["nom"] = nom
        return o

    @staticmethod
    def compter(o: dict, quoi: str, etat: str, n: int = 1) -> None:
        o["c"].setdefault(quoi, {}).setdefault(etat, 0)
        o["c"][quoi][etat] += n

    def anomalie(self, texte: str) -> None:
        self.anomalies.append(texte)

    def texte(self) -> str:
        L = []
        L.append("== Archivage de l'ancien cycle 3 (réversible) ==")
        if not self.archivage:
            L.append("  déjà fait lors d'une exécution précédente : rien à archiver")
        for k, v in self.archivage.items():
            L.append(f"  {k} : {v} archivé(s)")
        L.append("")
        L.append("== Cycle 3 : thèmes et séquences ==")
        L += [f"  {x}" for x in self.cycle]
        for code, s in self.sequences.items():
            L.append("")
            L.append(f"== {code} ==")
            L += [f"  {x}" for x in s["lignes"]]
            for oc, o in s["objectifs"].items():
                det = " ; ".join(
                    f"{quoi} [" + ", ".join(f"{e} : {n}" for e, n in etats.items()) + "]"
                    for quoi, etats in o["c"].items())
                L.append(f"  {oc} {o['nom'][:60]} — objectif {o['objectif']}"
                         + (f" | {det}" if det else ""))
            for x in s["ignores"]:
                L.append(f"  ignoré : {x}")
            if s.get("marqueurs"):                                   # v0.52.7
                L.append("  marqueurs : " + ", ".join(f"{k} {n}" for k, n in
                                                      s["marqueurs"].items()))
        L.append("")
        L.append("== Figures ==")
        L += [f"  {x}" for x in self.figures] or ["  aucune"]
        if self.documents:
            L.append("")
            L.append("== Documents et évaluations (séries TP, AC, AT, EV) ==")
            L += [f"  {x}" for x in self.documents]
        L.append("")
        L.append(f"== Anomalies ({len(self.anomalies)}) ==")
        L += [f"  - {x}" for x in self.anomalies] or ["  aucune"]
        if self.infos:
            L.append("")
            L.append("== Informations ==")
            L += [f"  - {x}" for x in self.infos]
        return "\n".join(L)


# ── 1. Archivage de l'ancien cycle 3 ─────────────────────────────────────────

def archivage_fait(conn) -> bool:
    """L'archivage est fait une fois pour toutes : il laisse au moins une
    séquence d'archive (code Xnn) dans le cycle 3."""
    return conn.execute("SELECT 1 FROM sequences_du_cycle WHERE cycle_code=? AND code LIKE 'X%'",
                        (CYCLE,)).fetchone() is not None


def _noms_csv_c03(racine: Path) -> dict:
    """{code: nom} des anciennes séquences d'après data/C03_sequences.csv
    (sert si la base n'avait pas les séquences du cycle 3)."""
    import csv
    p = racine / "data" / "C03_sequences.csv"
    if not p.is_file():
        return {}
    with open(p, encoding="utf-8-sig", newline="") as f:
        return {r["Code"]: r["Nom"] for r in csv.DictReader(f)}


def archiver_cycle3(conn, rapport: Rapport, racine: Path = RACINE_APPLI) -> None:
    j = rapport.journal["archivage"]
    # Thèmes : A, B, C → XA, XB, XC (nom suivi de « (archive) », après les nouveaux).
    themes = conn.execute("SELECT * FROM themes WHERE cycle_code=? AND code NOT LIKE 'X%'",
                          (CYCLE,)).fetchall()
    for t in themes:
        conn.execute("UPDATE themes SET code=?, nom=?, ordre=? WHERE id=?",
                     (code_archive(t["code"]), t["nom"] + SUFFIXE_ARCHIVE,
                      100 + (t["ordre"] or 0), t["id"]))
        j.append({"table": "themes", "id": t["id"], "code": [t["code"], code_archive(t["code"])],
                  "nom": [t["nom"], t["nom"] + SUFFIXE_ARCHIVE],
                  "ordre": [t["ordre"], 100 + (t["ordre"] or 0)]})
    rapport.archivage["thèmes du cycle 3"] = len(themes)

    # Séquences du cycle : S01…S16 → X01…X16, numéro + 100.
    seqs = conn.execute(
        "SELECT * FROM sequences_du_cycle WHERE cycle_code=? AND code IN (%s)"
        % ",".join("?" * len(ANCIENS_CODES)), (CYCLE, *ANCIENS_CODES)).fetchall()
    for s in seqs:
        conn.execute("UPDATE sequences_du_cycle SET code=?, numero=?, nom=? WHERE id=?",
                     (code_archive(s["code"]), 100 + s["numero"], s["nom"] + SUFFIXE_ARCHIVE,
                      s["id"]))
        j.append({"table": "sequences_du_cycle", "id": s["id"],
                  "code": [s["code"], code_archive(s["code"])],
                  "numero": [s["numero"], 100 + s["numero"]],
                  "nom": [s["nom"], s["nom"] + SUFFIXE_ARCHIVE]})
    if not seqs:
        # Base sans découpage du cycle 3 : on crée quand même les séquences
        # d'archive (noms du CSV historique), pour que les exercices archivés
        # aient une séquence et que l'archivage ne soit jamais refait.
        for code, nom in _noms_csv_c03(racine).items() or {c: c for c in ANCIENS_CODES}.items():
            sid = _nid("sc")
            conn.execute("INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, "
                         "theme_id) VALUES (?,?,?,?,?,NULL)",
                         (sid, CYCLE, code_archive(code), 100 + int(code[1:]),
                          nom + SUFFIXE_ARCHIVE))
            j.append({"table": "sequences_du_cycle", "id": sid, "cree": True})
    rapport.archivage["séquences du cycle 3"] = len(seqs)

    # Données rattachées aux anciens codes (CM1, CM2, 6e).
    marques = ",".join("?" * len(ANCIENS_CODES))
    niveaux = ",".join("?" * len(NIVEAUX_CYCLE3))
    for table, col, libelle in (
            ("sequences_par_niveau", "sequence_code", "séquences-niveaux"),
            ("exercices", "sequence", "exercices"),
            ("notions", "sequence", "notions"),
            ("methodes", "sequence", "méthodes"),
            ("fiches_resume", "sequence", "fiches de résumé"),
            ("cartes_automatisme", "sequence", "cartes d'automatisme")):
        if not _table(conn, table):
            continue
        rows = conn.execute(
            f"SELECT id, niveau, {col} AS seq FROM {table} WHERE niveau IN ({niveaux}) "
            f"AND {col} IN ({marques})", (*NIVEAUX_CYCLE3, *ANCIENS_CODES)).fetchall()
        for r in rows:
            conn.execute(f"UPDATE {table} SET {col}=? WHERE id=?", (code_archive(r["seq"]), r["id"]))
        if rows:
            j.append({"table": table, "colonne": col,
                      "ids": {r["id"]: r["seq"] for r in rows}})
        par_niveau = {}
        for r in rows:
            par_niveau[r["niveau"]] = par_niveau.get(r["niveau"], 0) + 1
        rapport.archivage[libelle] = len(rows)
        for niv, n in sorted(par_niveau.items()):
            if niv != NIVEAU:
                rapport.infos.append(f"{libelle} {niv} : {n} rattaché(s) aux anciennes "
                                     "séquences, archivé(s) avec elles")

    # Précédences portées par les séquences du cycle 3 (archivées avec elles).
    cibles = (*NIVEAUX_CYCLE3, CYCLE)
    for table, cle in (("sequence_par_niveau_precedences", "sequence_par_niveau_id"),
                       ("partie_precedences", "partie_id")):
        if not _table(conn, table):
            continue
        if table == "partie_precedences":
            jointure = ("JOIN sequence_parties p ON p.id = t.partie_id "
                        "JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id")
        else:
            jointure = "JOIN sequences_par_niveau sn ON sn.id = t.sequence_par_niveau_id"
        rows = conn.execute(
            f"SELECT t.rowid AS rid, t.{cle} AS cle, t.precedent_niveau, t.precedent_seq, "
            f"sn.niveau AS niv FROM {table} t {jointure} "
            f"WHERE t.precedent_niveau IN ({','.join('?' * len(cibles))}) "
            f"AND t.precedent_seq IN ({marques})", (*cibles, *ANCIENS_CODES)).fetchall()
        n = 0
        for r in rows:
            if r["niv"] in NIVEAUX_CYCLE3:
                conn.execute(f"UPDATE {table} SET precedent_seq=? WHERE rowid=?",
                             (code_archive(r["precedent_seq"]), r["rid"]))
                j.append({"table": table, "cle": r["cle"],
                          "precedent": [r["precedent_niveau"], r["precedent_seq"]]})
                n += 1
        if n:
            rapport.archivage[f"précédences du cycle 3 ({table})"] = n


def signaler_cycle4(conn, rapport: Rapport) -> None:
    """Le cycle 4 n'est jamais modifié : on signale ce qui y désigne encore
    un ancien code de 6e (à revoir dans l'atelier par l'auteur)."""
    marques = ",".join("?" * len(ANCIENS_CODES))
    for table, jointure in (
            ("sequence_par_niveau_precedences",
             "JOIN sequences_par_niveau sn ON sn.id = t.sequence_par_niveau_id"),
            ("partie_precedences",
             "JOIN sequence_parties p ON p.id = t.partie_id "
             "JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id")):
        if not _table(conn, table):
            continue
        for r in conn.execute(
                f"SELECT sn.niveau AS niv, sn.sequence_code AS seq, t.precedent_niveau AS pn, "
                f"t.precedent_seq AS ps FROM {table} t {jointure} "
                f"WHERE t.precedent_niveau IN ('N09','C03') AND t.precedent_seq IN ({marques}) "
                f"AND sn.niveau NOT IN ('N07','N08','N09') ORDER BY 1, 2, 4",
                ANCIENS_CODES).fetchall():
            rapport.anomalie(
                f"cycle 4 inchangé : {r['niv']}/{r['seq']} a pour prérequis {r['pn']}/{r['ps']} "
                f"(ancien code ; désigne désormais la nouvelle {r['ps']}, l'ancienne est "
                f"{code_archive(r['ps'])}) — à revoir dans l'atelier")
    if _table(conn, "partie_exos_revision_approche"):
        n = conn.execute(
            "SELECT COUNT(*) FROM partie_exos_revision_approche pe "
            "JOIN exercices e ON e.id = pe.exercice_id "
            "WHERE e.niveau='N09' AND e.sequence LIKE 'X%'").fetchone()[0]
        if n:
            rapport.infos.append(f"{n} exercice(s) de révision du cycle 4 viennent d'anciens "
                                 "exercices de 6e : liens gardés (identifiants inchangés)")


# ── 2. Thèmes et séquences du cycle 3 ────────────────────────────────────────

def appliquer_cycle3(conn, ref: dict, rapport: Rapport) -> dict:
    if conn.execute("SELECT 1 FROM cycles WHERE code=?", (CYCLE,)).fetchone() is None:
        conn.execute("INSERT INTO cycles (code, nom, description) VALUES (?,?,?)",
                     (CYCLE, "Cycle 3", "Cycle de consolidation : CM1, CM2 et 6ème."))
        rapport.cycle.append("cycle C03 créé")
    themes = {}
    for t in ref["themes"]:
        r = conn.execute("SELECT * FROM themes WHERE cycle_code=? AND code=?",
                         (CYCLE, t["code"])).fetchone()
        if r is None:
            tid = _nid("th")
            conn.execute("INSERT INTO themes (id, cycle_code, code, nom, code_couleur, "
                         "description, ordre) VALUES (?,?,?,?,?,'',?)",
                         (tid, CYCLE, t["code"], t["nom"], t["code_couleur"], t["ordre"]))
            etat = "créé"
        else:
            tid = r["id"]
            if (r["nom"], r["code_couleur"], r["ordre"]) != (t["nom"], t["code_couleur"], t["ordre"]):
                conn.execute("UPDATE themes SET nom=?, code_couleur=?, ordre=? WHERE id=?",
                             (t["nom"], t["code_couleur"], t["ordre"], tid))
                etat = "mis à jour"
            else:
                etat = "inchangé"
        themes[t["code"]] = tid
        rapport.cycle.append(f"thème {t['code']} {t['nom']} ({t['code_couleur']}) : {etat}")
    for s in ref["sequences"]:
        r = conn.execute("SELECT * FROM sequences_du_cycle WHERE cycle_code=? AND code=?",
                         (CYCLE, s["code"])).fetchone()
        tid = themes[s["theme"]]
        if r is None:
            conn.execute("INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, "
                         "theme_id) VALUES (?,?,?,?,?,?)",
                         (_nid("sc"), CYCLE, s["code"], s["numero"], s["nom"], tid))
            etat = "créée"
        elif (r["numero"], r["nom"], r["theme_id"]) != (s["numero"], s["nom"], tid):
            # Découpage de la géométrie (19 octobre 2026) : S05 à S10 changent
            # de nom (S06 Symétrie axiale → Cercles…). Une séquence-niveau du
            # cycle 3 déjà présente sous ce code porte le contenu de l'ancien
            # sens : renommer la séquence le rattacherait au nouveau sens.
            existantes = _seq_niveaux_cycle3(conn, s["code"]) if r["nom"] != s["nom"] else []
            if existantes:
                rapport.sequences_bloquees.add(s["code"])
                liste = ", ".join(f"{n}/{s['code']} ({e})" for n, e in existantes)
                rapport.anomalie(
                    f"séquence {s['code']} : « {r['nom']} » devient « {s['nom']} » "
                    f"(découpage de la géométrie), mais la séquence-niveau {liste} "
                    "existe déjà avec le contenu de l'ancien sens : séquence non renommée, "
                    "lot non importé — à revoir dans l'atelier")
                etat = "non modifiée (anomalie)"
            else:
                conn.execute("UPDATE sequences_du_cycle SET numero=?, nom=?, theme_id=? "
                             "WHERE id=?", (s["numero"], s["nom"], tid, r["id"]))
                etat = "mise à jour" if r["nom"] == s["nom"] else f"renommée (était « {r['nom']} »)"
        else:
            etat = "inchangée"
        rapport.cycle.append(f"séquence {s['code']} {s['nom']} (thème {s['theme']}) : {etat}")
    return themes


def _seq_niveaux_cycle3(conn, code: str) -> list[tuple[str, str]]:
    """[(niveau, état)] des séquences-niveaux du cycle 3 (CM1, CM2, 6e) au code donné."""
    return [(r[0], r[1] or "") for r in conn.execute(
        "SELECT niveau, etat_code FROM sequences_par_niveau WHERE sequence_code=? AND niveau IN "
        f"({','.join('?' * len(NIVEAUX_CYCLE3))}) ORDER BY niveau", (code, *NIVEAUX_CYCLE3))]


# ── 3. Import d'une séquence de 6e ───────────────────────────────────────────

def _seq_niveau(conn, seq: str, rapport: Rapport) -> sqlite3.Row | None:
    r = conn.execute("SELECT * FROM sequences_par_niveau WHERE niveau=? AND sequence_code=?",
                     (NIVEAU, seq)).fetchone()
    if r is None:
        conn.execute("INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres, "
                     "etat_code) VALUES (?,?,?,'','en_cours')", (_nid("sn"), NIVEAU, seq))
        rapport.seq(seq)["lignes"].append("séquence-niveau N09 : créée")
        return conn.execute("SELECT * FROM sequences_par_niveau WHERE niveau=? AND "
                            "sequence_code=?", (NIVEAU, seq)).fetchone()
    if r["etat_code"] == "valide":
        rapport.anomalie(f"{seq} : séquence-niveau N09 validée dans l'atelier, non modifiée "
                         "(la repasser « en cours » pour importer)")
        return None
    rapport.seq(seq)["lignes"].append("séquence-niveau N09 : existante")
    return r


def _partie(conn, sn_id: str, numero: int, seq: str, rapport: Rapport) -> str:
    r = conn.execute("SELECT id FROM sequence_parties WHERE sequence_par_niveau_id=? AND "
                     "numero=?", (sn_id, numero)).fetchone()
    if r:
        return r["id"]
    pid = _nid("pt")
    conn.execute("INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero, "
                 "nb_seances_R_AE) VALUES (?,?,?,0)", (pid, sn_id, numero))
    rapport.seq(seq)["lignes"].append(f"partie {numero} : créée")
    return pid


def _objectif(conn, sn_id: str, partie_id: str, code: str, d: dict,
              rapport: "Rapport | None" = None, etiquette: str = "") -> tuple[str, str]:
    """(id, état) de l'objectif (niveau, séquence, code).

    v0.52.8 (O1) — Un objectif existant (séquence non validée : une séquence
    validée n'est pas importée) prend l'intitulé et les critères F, A, E du
    référentiel ; ce qui change est détaillé dans les informations du
    rapport, dès l'essai à blanc."""
    r = conn.execute(
        "SELECT o.* FROM objectifs o JOIN sequence_parties p ON p.id = o.partie_id "
        "WHERE p.sequence_par_niveau_id=? AND o.code=?", (sn_id, code)).fetchone()
    vals = (d["nom"], d["critere_F"], d["critere_A"], d["critere_E"])
    if r is None:
        oid = _nid("ob")
        conn.execute("INSERT INTO objectifs (id, partie_id, code, nom, critere_F, critere_A, "
                     "critere_E, fin_cycle, nb_seances) VALUES (?,?,?,?,?,?,?,'N',0)",
                     (oid, partie_id, code, *vals))
        return oid, "créé"
    if (r["partie_id"], r["nom"], r["critere_F"], r["critere_A"], r["critere_E"]) \
            != (partie_id, *vals):
        conn.execute("UPDATE objectifs SET partie_id=?, nom=?, critere_F=?, critere_A=?, "
                     "critere_E=? WHERE id=?", (partie_id, *vals, r["id"]))
        # v0.52.8 (O1) — détail signalé dès l'essai à blanc.
        quoi = [lib for lib, a, b in (("partie", r["partie_id"], partie_id),
                                      ("intitulé", r["nom"], d["nom"]),
                                      ("critère F", r["critere_F"], d["critere_F"]),
                                      ("critère A", r["critere_A"], d["critere_A"]),
                                      ("critère E", r["critere_E"], d["critere_E"])) if a != b]
        if rapport is not None:
            rapport.infos.append(f"{etiquette or code} : objectif mis à jour d'après "
                                 f"objectifs_6e.json ({', '.join(quoi)})")
        return r["id"], "mis à jour"
    return r["id"], "inchangé"


_CHAMPS_EXO = ("titre", "enonce", "corrige", "remed_enonce", "remed_corrige")


def marqueurs_lot(src: dict, quoi: str, rapport: "Rapport | None" = None) -> dict:
    """v0.52.7 — Clés facultatives `ordinateur` et `calculatrice` d'un
    élément du lot ; absente = '' (non marqué) ; valeur inconnue : signalée
    (anomalie) et ignorée."""
    out = {}
    for champ in mq.CHAMPS:
        try:
            out[champ] = mq.valider(champ, src.get(champ))
        except mq.MarqueurInvalide:
            out[champ] = ""
            if rapport is not None:
                rapport.anomalie(f"{quoi} : {champ} {src.get(champ)!r} inconnu "
                                 f"(attendu {', '.join(v for v in mq.VALEURS[champ] if v)}), "
                                 "ignoré")
    return out


def _compter_marqueurs(rapport: "Rapport", seq: str, marques: dict) -> None:
    """Compteurs « marqueurs » de la séquence (aperçu de l'import)."""
    c = rapport.seq(seq).setdefault("marqueurs", OrderedDict())
    if marques.get("ordinateur"):
        k = "ordinateur " + mq.libelle_ordinateur(marques["ordinateur"])
        c[k] = c.get(k, 0) + 1
    if marques.get("calculatrice"):
        k = mq.LIBELLES_CALCULATRICE[marques["calculatrice"]]
        c[k] = c.get(k, 0) + 1


def _exercice(conn, seq: str, serie_code: str, num: int, src: dict,
              marques: dict | None = None) -> tuple[str, str]:
    """(id, état) de l'exercice (N09, séquence, série, num).

    v0.52.7 — `marques` : marqueurs du lot (`marqueurs_lot`), comparés et
    écrits avec le contenu quand la base a les colonnes ; None = non
    marqué."""
    vals = {"titre": src.get("titre", "") or "",
            "enonce": src.get("enonce", src.get("latex", "")) or "",
            "corrige": src.get("corrige", "") or "",
            "remed_enonce": src.get("remed_enonce", "") or "",
            "remed_corrige": src.get("remed_corrige", "") or ""}
    if mq.colonnes_presentes(conn):
        vals.update({c: (marques or {}).get(c, "") or "" for c in mq.CHAMPS})
    rows = conn.execute("SELECT * FROM exercices WHERE niveau=? AND sequence=? AND "
                        "serie_code=? AND num=?", (NIVEAU, seq, serie_code, num)).fetchall()
    if len(rows) > 1:
        raise ImportErreur(f"{seq} {serie_code}{num:02d} : {len(rows)} exercices portent "
                           "cette clé dans la base")
    cols = _cols(conn, "exercices")
    if not rows:
        eid = _nid("ex")
        champs = {"id": eid, "serie": SERIE_TEXTE[serie_code], "niveau": NIVEAU,
                  "sequence": seq, "num": num, "serie_code": serie_code, "fichier": "",
                  "variables": "", **vals}
        if "etat_code" in cols:
            champs["etat_code"] = "en_cours"
        if "type_format" in cols:
            champs["type_format"] = _deduire_type_format(vals["enonce"])
        if "mtime" in cols:
            champs["mtime"] = _maintenant()
        conn.execute(f"INSERT INTO exercices ({', '.join(champs)}) VALUES "
                     f"({', '.join('?' * len(champs))})", tuple(champs.values()))
        return eid, "créé"
    r = rows[0]
    if all((r[k] or "") == v for k, v in vals.items()) and r["serie"] == SERIE_TEXTE[serie_code]:
        return r["id"], "inchangé"
    if "etat_code" in cols and r["etat_code"] == "valide":
        return r["id"], "validé, non modifié"
    sets = dict(vals, serie=SERIE_TEXTE[serie_code])
    if "type_format" in cols:
        sets["type_format"] = _deduire_type_format(vals["enonce"])
    if "mtime" in cols:
        sets["mtime"] = _maintenant()
    conn.execute(f"UPDATE exercices SET {', '.join(k + '=?' for k in sets)} WHERE id=?",
                 (*sets.values(), r["id"]))
    return r["id"], "mis à jour"


def _ordonner(conn, table: str, cle: dict, ids: list[str]) -> int:
    """Pose les liens `ids` (dans cet ordre, en tête) pour la clé donnée
    (objectif + série, ou partie + type), sans toucher aux autres liens de
    l'auteur, qui passent après. Retourne le nombre de liens créés."""
    where = " AND ".join(f"{k}=?" for k in cle)
    actuels = [r[0] for r in conn.execute(
        f"SELECT exercice_id FROM {table} WHERE {where} ORDER BY ordre", tuple(cle.values()))]
    voulu = ids + [i for i in actuels if i not in ids]
    if voulu == actuels:
        return 0
    crees = len([i for i in ids if i not in actuels])
    # Ordres provisoires négatifs (contrainte UNIQUE sur l'ordre), puis 1…n.
    conn.execute(f"UPDATE {table} SET ordre = -ordre - 1000 WHERE {where}", tuple(cle.values()))
    for k, ex_id in enumerate(voulu, start=1):
        if ex_id in actuels:
            conn.execute(f"UPDATE {table} SET ordre=? WHERE {where} AND exercice_id=?",
                         (k, *cle.values(), ex_id))
        else:
            num = conn.execute("SELECT num, niveau, sequence, serie_code FROM exercices "
                               "WHERE id=?", (ex_id,)).fetchone()
            if table == "objectif_exos":
                conn.execute("INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre, "
                             "origin_num) VALUES (?,?,?,?,?)",
                             (cle["objectif_id"], cle["serie"], ex_id, k, num["num"]))
            else:
                conn.execute("INSERT INTO partie_exos_revision_approche (partie_id, type, "
                             "exercice_id, ordre, origin_niveau, origin_seq, origin_serie, "
                             "origin_num) VALUES (?,?,?,?,?,?,?,?)",
                             (cle["partie_id"], cle["type"], ex_id, k, num["niveau"],
                              num["sequence"], num["serie_code"], num["num"]))
    return crees


def _fiche(conn, seq: str, objectif_id: str, cours_id: str, src: dict) -> tuple[str, str]:
    titre = (src.get("titre") or "").strip()
    sections = sections_fiche(src.get("latex") or "")
    r = conn.execute("SELECT * FROM fiches_resume WHERE objectif_id=?", (objectif_id,)).fetchone()
    if r is None:
        f = svc_fiches.creer_fiche(conn, objectif_id=objectif_id, titre=titre, sections=sections)
        fid, etat = f["id"], "créée"
    else:
        fid = r["id"]
        actuelle = svc_fiches.lire_fiche(conn, fid)
        meme = (actuelle["titre"] == titre and
                [(s["titre"], s["items"]) for s in actuelle["sections"]]
                == [(s["titre"], s["items"]) for s in sections])
        if meme:
            etat = "inchangée"
        elif r["etat_code"] == "valide":
            etat = "validée, non modifiée"
        else:
            svc_fiches.modifier_fiche(conn, fid, titre=titre, sections=sections)
            etat = "mise à jour"
    if etat in ("créée", "mise à jour") and "mtime" in _cols(conn, "fiches_resume"):
        conn.execute("UPDATE fiches_resume SET mtime=? WHERE id=?", (_maintenant(), fid))
    if conn.execute("SELECT 1 FROM objectif_fiches WHERE objectif_id=? AND fiche_id=?",
                    (cours_id, fid)).fetchone() is None:
        svc_fiches.attacher_fiche_a_objectif(conn, objectif_id=cours_id, fiche_id=fid)
    return fid, etat


def _figures(lot: dict, element: dict) -> set:
    noms = set(element.get("figures") or [])
    for k in ("enonce", "corrige", "remed_enonce", "remed_corrige", "latex"):
        noms |= {Path(n).name for n in RE_GRAPHIQUE.findall(element.get(k) or "")}
    return {n if Path(n).suffix else n + ".png" for n in noms}


def importer_lot(conn, lot: dict, ref: dict, rapport: Rapport) -> set:
    """Importe une séquence ; retourne les noms de figures utilisées."""
    seq = lot["sequence"]
    figures: set = set()
    s_ref = next((s for s in ref["sequences"] if s["code"] == seq), None)
    parties_ref = ref["parties"].get(seq)
    if s_ref is None or not parties_ref:
        rapport.anomalie(f"{seq} : séquence absente de objectifs_6e.json, lot non importé")
        return figures
    if seq in rapport.sequences_bloquees:          # anomalie déjà signalée (cycle 3)
        rapport.seq(seq)["lignes"].append("lot non importé : la séquence a changé de sens "
                                          "(voir les anomalies)")
        return figures
    sr = rapport.seq(seq)
    sr["lignes"].append(f"{s_ref['nom']} (lot : « {lot.get('titre', '')} »)")
    sn = _seq_niveau(conn, seq, rapport)
    if sn is None:
        return figures
    objs_ref = {f"{seq}-{o['code']}": (p["numero"], o) for p in parties_ref for o in p["objectifs"]}
    cours = ref["objectif_cours"]
    parties, cours_ids = {}, {}
    for p in parties_ref:
        pid = _partie(conn, sn["id"], p["numero"], seq, rapport)
        parties[p["numero"]] = pid
        code_c = f"{p['numero'] - 1}1"
        oid, etat = _objectif(conn, sn["id"], pid, code_c, cours, rapport, f"{seq}-{code_c}")
        cours_ids[p["numero"]] = oid
        rapport.obj(seq, f"{seq}-{code_c}", "Cours — " + cours["nom"])["objectif"] = etat

    approche: dict[int, list] = {n: [] for n in parties}
    vus: dict = {}
    objectifs_ids: dict[str, str] = {}          # « S01-02 » → id (v0.52.2)
    for o in lot.get("objectifs", []):
        code = o.get("code", "")
        if code not in objs_ref:
            rapport.anomalie(f"{seq} : objectif inconnu {code!r} (absent de objectifs_6e.json), "
                             "ignoré avec ses exercices")
            continue
        numero, d = objs_ref[code]
        if o.get("partie") not in (None, numero):
            rapport.anomalie(f"{code} : partie {o.get('partie')} dans le lot, {numero} dans le "
                             "référentiel (référentiel retenu)")
        if (o.get("intitule") or d["nom"]) != d["nom"]:
            rapport.infos.append(f"{code} : intitulé du lot différent du référentiel "
                                 "(référentiel retenu)")
        oid, etat = _objectif(conn, sn["id"], parties[numero], d["code"], d, rapport, code)
        ro = rapport.obj(seq, code, d["nom"])
        ro["objectif"] = etat
        series: dict[str, list] = {"F": [], "A": [], "E": []}
        for e in o.get("exercices", []):
            sc = e.get("serie")
            if sc not in series:
                rapport.anomalie(f"{code} : série inconnue {sc!r} ({e.get('titre', '')}), ignoré")
                continue
            cle = (sc, int(e["num"]))
            if cle in vus:
                rapport.anomalie(f"{seq} {sc}{cle[1]:02d} en double ({vus[cle]} et {code}), "
                                 "second ignoré")
                continue
            vus[cle] = code
            marques = marqueurs_lot(e, f"{seq} {sc}{cle[1]:02d}", rapport)
            _compter_marqueurs(rapport, seq, marques)
            eid, etat_e = _exercice(conn, seq, sc, cle[1], e, marques)
            series[sc].append(eid)
            Rapport.compter(ro, f"exercices {sc}", etat_e)
            if (e.get("remed_enonce") or "").strip():
                Rapport.compter(ro, "remédiations", "présentes")
            figures |= _figures(lot, e)
            rapport.journal["import"].append({"cle": f"{NIVEAU}/{seq}/{sc}{cle[1]:02d}",
                                              "id": eid, "objectif": code,
                                              "origine": e.get("origine", ""),
                                              "remed_origine": e.get("remed_origine", "")})
            if etat_e == "validé, non modifié":
                rapport.anomalie(f"{NIVEAU}/{seq}/{sc}{cle[1]:02d} validé dans l'atelier : "
                                 "contenu du lot non appliqué")
        for sc, ids in series.items():
            if ids:
                n = _ordonner(conn, "objectif_exos", {"objectif_id": oid, "serie": sc}, ids)
                Rapport.compter(ro, "liens objectif-exercice", "créés", n)
        act_obj = []
        for a in o.get("activites", []):
            cle = ("AE", int(a["num"]))
            if cle in vus:
                rapport.anomalie(f"{seq} AE{cle[1]:02d} en double, second ignoré")
                continue
            vus[cle] = code
            marques = marqueurs_lot(a, f"{seq} AE{cle[1]:02d}", rapport)
            _compter_marqueurs(rapport, seq, marques)
            eid, etat_a = _exercice(conn, seq, "AE", cle[1], a, marques)
            approche[numero].append(eid)
            act_obj.append(eid)
            Rapport.compter(ro, "activités AE", etat_a)
            figures |= _figures(lot, a)
            rapport.journal["import"].append({"cle": f"{NIVEAU}/{seq}/AE{cle[1]:02d}",
                                              "id": eid, "objectif": code,
                                              "origine": a.get("origine", "")})
        if act_obj:
            # v0.52.2 (L1) — l'activité est aussi rattachée à son objectif
            # (objectif_exos, série AE) : le livret 6e l'affiche sous le
            # bandeau de l'objectif, et seulement là ; le lien à la partie
            # est gardé (numérotation, plan de travail).
            n = _ordonner(conn, "objectif_exos", {"objectif_id": oid, "serie": "AE"}, act_obj)
            Rapport.compter(ro, "liens activité-objectif", "créés", n)
        objectifs_ids[code] = oid
        if o.get("fiche_resume"):
            fid, etat_f = _fiche(conn, seq, oid, cours_ids[numero], o["fiche_resume"])
            Rapport.compter(ro, "fiche", etat_f)
            if etat_f == "validée, non modifiée":
                rapport.anomalie(f"{code} : fiche validée dans l'atelier, non modifiée")
        else:
            rapport.anomalie(f"{code} : pas de fiche de résumé dans le lot")
    for numero, ids in approche.items():
        if ids:
            n = _ordonner(conn, "partie_exos_revision_approche",
                          {"partie_id": parties[numero], "type": "EA"}, ids)
            sr["lignes"].append(f"partie {numero} : {len(ids)} activité(s) d'approche, "
                                f"{n} lien(s) créé(s)")
    if lot.get("pour_S02"):
        b = lot["pour_S02"]
        sr["ignores"].append(f"bloc pour_S02 ({len(b.get('objectifs', []))} objectif(s)) : "
                             "déjà intégré au lot S02")
    for o in objs_ref:
        if o not in {x.get("code") for x in lot.get("objectifs", [])}:
            rapport.anomalie(f"{o} : objectif du référentiel sans contenu dans le lot")
    # v0.52.2 — Objectifs du référentiel présents en base (pour les liens des
    # documents et des évaluations, y compris un objectif sans contenu).
    for c_obj, (num_p, d) in objs_ref.items():
        if c_obj not in objectifs_ids:
            r = conn.execute("SELECT o.id FROM objectifs o JOIN sequence_parties p ON "
                             "p.id = o.partie_id WHERE p.sequence_par_niveau_id = ? AND "
                             "o.code = ?", (sn["id"], d["code"])).fetchone()
            if r is not None:
                objectifs_ids[c_obj] = r["id"]
    figures |= importer_documents(conn, lot, objectifs_ids, rapport)
    importer_evaluations(conn, lot, objectifs_ids, rapport)
    return figures


def copier_figures(lots: list[dict], noms_par_seq: dict, images: Path, rapport: Rapport,
                   ecrire: bool) -> None:
    for lot in lots:
        d = lot["_dossier"] / "figures"
        for nom in sorted(noms_par_seq.get(lot["sequence"], ())):
            src = d / nom
            if not src.is_file():
                rapport.anomalie(f"{lot['sequence']} : figure manquante {nom}")
                continue
            dst = images / nom
            if dst.is_file():
                if _sha(dst) == _sha(src):
                    rapport.figures.append(f"{nom} : déjà présente")
                else:
                    rapport.anomalie(f"figure {nom} : un fichier différent existe déjà dans "
                                     f"{images}, non remplacé")
                continue
            rapport.figures.append(f"{nom} : copiée dans {images}")
            if ecrire:
                images.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)


def macros_locales(lots: list[dict]) -> dict:
    """{séquence: [\\seqLoc… utilisées]} dans les contenus LaTeX des lots
    (le module seqenseigne-style6e les fournit : v0.4 pour S01 à S03, v0.6
    pour S05)."""
    out = {}
    for lot in lots:
        contenu = {k: v for k, v in lot.items() if k not in ("_dossier", "macros_locales")}
        brut = json.dumps(contenu, ensure_ascii=False).replace("\\\\", "\\")
        out[lot["sequence"]] = sorted(set(RE_LOC.findall(brut)))
    return out


def macros_module(lots: list[dict]) -> dict:
    """v0.52.8 (I2) — {séquence: ([\\seq…Six appelées], nombre de
    \\seqAstuceSix)} dans les contenus LaTeX des lots."""
    out = {}
    for lot in lots:
        contenu = {k: v for k, v in lot.items() if k not in ("_dossier", "macros_locales")}
        brut = json.dumps(contenu, ensure_ascii=False).replace("\\\\", "\\")
        trouvees = RE_SIX.findall(brut)
        out[lot["sequence"]] = (sorted(set(trouvees)), trouvees.count("seqAstuceSix"))
    return out


# ── 4. Documents et évaluations en base (v0.52.2) ───────────────────────────

def _lier_objectifs(conn, liens: "OrderedDict[tuple, list]") -> int:
    """Pose les liens objectif_exos accumulés {(objectif_id, série): [ids]}
    (dans l'ordre du lot, en tête, sans toucher aux liens de l'auteur)."""
    n = 0
    for (oid, serie), ids in liens.items():
        n += _ordonner(conn, "objectif_exos", {"objectif_id": oid, "serie": serie}, ids)
    return n


def importer_documents(conn, lot: dict, objectifs_ids: dict, rapport: Rapport) -> set:
    """Travaux personnels, activités complémentaires, séances d'atelier :
    un atome par document (séries TP, AC, AT), numéroté par série dans la
    séquence (ordre du lot), relié aux objectifs listés dans `objectifs`.
    Retourne les figures utilisées."""
    seq = lot["sequence"]
    figures: set = set()
    liens: "OrderedDict[tuple, list]" = OrderedDict()
    for cle_lot, serie, libelle in DOCUMENTS_LOT:
        for k, src in enumerate(lot.get(cle_lot, []) or [], start=1):
            code = f"{serie}{k:02d}"
            marques = marqueurs_lot(src, f"{seq} {code}", rapport)
            _compter_marqueurs(rapport, seq, marques)
            eid, etat = _exercice(conn, seq, serie, k, {"titre": src.get("titre", ""),
                                                        "enonce": src.get("latex", ""),
                                                        "corrige": src.get("corrige", "")},
                                  marques)
            if etat == "validé, non modifié":
                rapport.anomalie(f"{NIVEAU}/{seq}/{code} validé dans l'atelier : contenu du lot "
                                 "non appliqué")
            cibles = []
            for oc in src.get("objectifs", []) or []:
                if oc in objectifs_ids:
                    liens.setdefault((objectifs_ids[oc], serie), []).append(eid)
                    cibles.append(oc)
                else:
                    rapport.anomalie(f"{seq} {code} : objectif {oc!r} inconnu, lien ignoré")
            figures |= _figures(lot, src)
            info = f" — délai {src['delai_jours']} j (à régler côté classe)" \
                if src.get("delai_jours") else ""
            rapport.documents.append(f"{seq} {code} {libelle} « {src.get('titre', '')} » : "
                                     f"{etat} ; objectifs {', '.join(cibles) or 'aucun'}{info}")
            rapport.journal["import"].append({"cle": f"{NIVEAU}/{seq}/{code}", "id": eid,
                                              "objectifs": cibles,
                                              "origine": src.get("origine", "")})
    n = _lier_objectifs(conn, liens)
    if n:
        rapport.seq(seq)["lignes"].append(f"documents TP/AC/AT : {n} lien(s) objectif créé(s)")
    return figures


# Évaluations : `\seqExoEval{titre}{N pts --- Snn-nn}` ouvre chaque exercice.
MARQUE_EXO_EVAL = "\\seqExoEval"
# v0.53.0 — aussi `Mnn-nn` (tests courts des mises en route).
RE_ETIQUETTE_EVAL = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*pts?\s*---\s*([SM]\d\d-\d\d)\s*$")


def decouper_evaluation(latex: str) -> list[dict]:
    r"""Exercices d'une évaluation du lot : [{titre, points, objectif, corps}].

    Découpe à chaque `\seqExoEval{titre}{N pts --- Snn-nn}` ; l'en-tête
    (identification, titre, barème) qui précède le premier exercice n'est
    pas gardé : le rendu 6e le recalcule depuis la base. Lève ImportErreur
    si un exercice n'a pas cette forme."""
    pos = []
    k = latex.find(MARQUE_EXO_EVAL)
    while k >= 0:
        j = k + len(MARQUE_EXO_EVAL)
        if latex[j:j + 1].isalpha():                     # autre macro (\seqExoEvalX)
            k = latex.find(MARQUE_EXO_EVAL, j)
            continue
        while j < len(latex) and latex[j].isspace():
            j += 1
        if latex[j:j + 1] != "{":
            raise ImportErreur(f"{MARQUE_EXO_EVAL} sans titre")
        titre, j = _accolade(latex, j)
        while j < len(latex) and latex[j].isspace():
            j += 1
        if latex[j:j + 1] != "{":
            raise ImportErreur(f"{MARQUE_EXO_EVAL}{{{titre}}} sans barème")
        etiquette, j = _accolade(latex, j)
        m = RE_ETIQUETTE_EVAL.match(etiquette)
        if not m:
            raise ImportErreur(f"barème illisible « {etiquette} » ({titre})")
        pos.append((k, j, titre.strip(), float(m.group(1).replace(",", ".")), m.group(2)))
        k = latex.find(MARQUE_EXO_EVAL, j)
    if not pos:
        raise ImportErreur(f"aucun {MARQUE_EXO_EVAL}")
    out = []
    for i, (k, fin, titre, pts, obj) in enumerate(pos):
        suite = pos[i + 1][0] if i + 1 < len(pos) else len(latex)
        out.append({"titre": titre, "points": pts, "objectif": obj,
                    "corps": latex[fin:suite].strip()})
    return out


def _est_bonus(exo: dict) -> bool:
    return exo["titre"].lower().startswith("bonus")


def paires_evaluations(lot: dict) -> "OrderedDict[str, dict]":
    """{titre: {"A": évaluation, "B": évaluation}} dans l'ordre du lot."""
    out: "OrderedDict[str, dict]" = OrderedDict()
    for ev in lot.get("evaluations", []) or []:
        out.setdefault(ev.get("titre", ""), {})[(ev.get("sujet") or "A").upper()] = ev
    return out


def preparer_evaluation(titre: str, paire: dict) -> list[dict]:
    """Exercices EV d'une paire A/B, mis en correspondance par position.

    Contrôles (sinon ImportErreur → anomalie, évaluation non importée) :
    sujets A et B présents, même nombre d'exercices, mêmes points et même
    objectif à chaque position ; barème par objectif du lot = somme des
    points des exercices (hors bonus), bonus = exercices « Bonus… »
    (décision B1 : sans objectif)."""
    if set(paire) != {"A", "B"}:
        raise ImportErreur(f"sujets {', '.join(sorted(paire)) or 'aucun'} (A et B attendus)")
    a = decouper_evaluation(paire["A"].get("latex", ""))
    b = decouper_evaluation(paire["B"].get("latex", ""))
    if len(a) != len(b):
        raise ImportErreur(f"{len(a)} exercice(s) au sujet A, {len(b)} au sujet B")
    for i, (x, y) in enumerate(zip(a, b), start=1):
        if (x["points"], x["objectif"]) != (y["points"], y["objectif"]):
            raise ImportErreur(f"exercice {i} : {x['points']:g} pts {x['objectif']} au sujet A, "
                               f"{y['points']:g} pts {y['objectif']} au sujet B")
    attendu: dict = {}
    for oc, pts in paire["A"].get("bareme") or []:
        attendu[oc] = attendu.get(oc, 0) + float(pts)
    calcule: dict = {}
    for x in a:
        cle = "Bonus" if _est_bonus(x) else x["objectif"]
        calcule[cle] = calcule.get(cle, 0) + x["points"]
    if attendu and attendu != calcule:
        raise ImportErreur("barème du lot "
                           + ", ".join(f"{k}/{v:g}" for k, v in attendu.items())
                           + " ≠ exercices " + ", ".join(f"{k}/{v:g}" for k, v in calcule.items()))
    return [{**x, "bonus": _est_bonus(x), "titre_b": y["titre"], "corps_b": y["corps"]}
            for x, y in zip(a, b)]


def _sujet_b(exo: dict) -> str:
    r"""remed_enonce : énoncé du sujet B, précédé de « % titre B : … » quand
    son titre diffère de celui du sujet A (décision E3, lue par le rendu)."""
    from services.render_evaluation import MARQUE_TITRE_B
    entete = f"{MARQUE_TITRE_B} {exo['titre_b']}\n" if exo["titre_b"] != exo["titre"] else ""
    return entete + exo["corps_b"]


def _evaluation(conn, titre: str, rapport: Rapport, seq: str):
    """(id, état) de l'évaluation N09 de ce titre ; état « validée » : rien
    n'y est touché."""
    from services import evaluations as svc_eval
    r = conn.execute("SELECT id, etat_code FROM evaluations WHERE niveau = ? AND titre = ? "
                     "ORDER BY numero LIMIT 1", (NIVEAU, titre)).fetchone()
    if r is None:
        ev = svc_eval.creer_evaluation(conn, niveau=NIVEAU, titre=titre,
                                       mode_notation="note_criteres")
        return ev["id"], "créée"
    if r["etat_code"] == "valide":
        rapport.anomalie(f"{seq} évaluation « {titre} » validée dans le module Évaluations : "
                         "non modifiée")
        return r["id"], "validée, non modifiée"
    return r["id"], "existante"


def _poser_calculatrice(conn, ev_id: str, valeur: str) -> int:
    """v0.52.8 (C1) — `evaluations.calculatrice` = clé `calculatrice` de
    l'entrée d'évaluation du lot ('' si absente : le sujet suit ses
    exercices). Évaluation non validée seulement (l'appelant l'a vérifié).
    Retourne 1 si la valeur change."""
    if not mq.colonne_evaluation_presente(conn):
        mq.migrer_evaluations(conn)
    avant = conn.execute("SELECT calculatrice FROM evaluations WHERE id = ?",
                         (ev_id,)).fetchone()[0] or ""
    if avant == (valeur or ""):
        return 0
    conn.execute("UPDATE evaluations SET calculatrice = ?, mtime = CURRENT_TIMESTAMP "
                 "WHERE id = ?", (valeur or "", ev_id))
    return 1


def calculatrice_exercices_lot(paire: dict, n: int, quoi: str,
                               rapport: "Rapport | None" = None) -> dict:
    """v0.52.9 — Clé facultative `calculatrice_exercices` de l'entrée
    d'évaluation : {position 1-based: 'interdite' | 'autorisee'} (sujet A,
    sinon B ; même table pour les deux sujets, paires par position). Entrée
    invalide (position hors 1..n, valeur inconnue) : signalée et ignorée
    (la position hérite alors de `calculatrice`)."""
    tables = {s: e.get("calculatrice_exercices") for s, e in paire.items()
              if e.get("calculatrice_exercices") not in (None, {}, "")}
    if not tables:
        return {}
    brute = tables.get("A", tables.get("B"))
    if rapport is not None and len(tables) == 2 and tables["A"] != tables["B"]:
        rapport.anomalie(f"{quoi} : calculatrice_exercices différente aux sujets A et B "
                         "(celle du sujet A est retenue)")
    if not isinstance(brute, dict):
        if rapport is not None:
            rapport.anomalie(f"{quoi} : calculatrice_exercices {brute!r} n'est pas une table "
                             "{position: valeur}, ignorée")
        return {}
    out = {}
    for k, v in brute.items():
        try:
            pos = int(str(k).strip())
        except ValueError:
            pos = 0
        if not 1 <= pos <= n:
            if rapport is not None:
                rapport.anomalie(f"{quoi} : calculatrice_exercices, position {k!r} hors du "
                                 f"sujet (1 à {n}), ignorée")
            continue
        if v not in ("interdite", "autorisee"):
            if rapport is not None:
                rapport.anomalie(f"{quoi} : calculatrice_exercices[{k}] = {v!r} inconnue "
                                 "(attendu interdite, autorisee), ignorée")
            continue
        out[pos] = v
    return out


def _resume_deux_parties(conn, ev_id: str | None, exos: list[dict],
                         marques: list[dict]) -> str:
    """v0.52.9 — « en deux parties : partie 1 sans calculatrice ex. 1 et 2
    (8 pts, 20 min), partie 2 ex. 3 à 5 (12 pts) » pour le rapport."""
    parties: list[list[int]] = [[], []]
    points = [0.0, 0.0]
    bonus = [False, False]
    for k, (x, m) in enumerate(zip(exos, marques), start=1):
        i = mq.partie_de(m) - 1
        parties[i].append(k)
        if x["bonus"]:
            bonus[i] = True
        else:
            points[i] += x["points"]
    total = points[0] + points[1]
    duree = mq.duree_partie1_auto(points[0], total)
    reglee = None
    if ev_id is not None and mq.colonne_duree_presente(conn):
        r = conn.execute("SELECT duree_partie1 FROM evaluations WHERE id = ?",
                         (ev_id,)).fetchone()
        reglee = r[0] if r else None
    def ex(nums):
        return "ex. " + (" et ".join([", ".join(map(str, nums[:-1])), str(nums[-1])])
                         if len(nums) > 1 else str(nums[0]))
    def pts(i):
        return f"{points[i]:g} pts" + (" + bonus" if bonus[i] else "")
    d = (f"{reglee} min réglée(s) dans l'atelier, calcul {duree} min" if reglee is not None
         else f"{duree} min")
    return (f"en deux parties : partie 1 sans calculatrice {ex(parties[0])} ({pts(0)}, {d}), "
            f"partie 2 calculatrice autorisée {ex(parties[1])} ({pts(1)})")


def _poser_exercices_evaluation(conn, ev_id: str, voulus: list[tuple]) -> int:
    """Exercices importés (id, points) en tête, dans l'ordre du lot ; ceux
    que l'auteur a ajoutés passent après. Retourne le nombre de changements."""
    actuels = [(r["exercice_id"], r["bareme_points"]) for r in conn.execute(
        "SELECT exercice_id, bareme_points FROM evaluation_exercices WHERE evaluation_id = ? "
        "ORDER BY ordre", (ev_id,))]
    ids = [i for i, _ in voulus]
    ordre = ids + [i for i, _ in actuels if i not in ids]
    pts = dict(actuels)
    pts.update(dict(voulus))
    if [(i, pts[i]) for i in ordre] == actuels:
        return 0
    conn.execute("UPDATE evaluation_exercices SET ordre = -ordre - 1000 WHERE evaluation_id = ?",
                 (ev_id,))
    deja = {i for i, _ in actuels}
    for k, i in enumerate(ordre, start=1):
        if i in deja:
            conn.execute("UPDATE evaluation_exercices SET ordre = ?, bareme_points = ? "
                         "WHERE evaluation_id = ? AND exercice_id = ?", (k, pts[i], ev_id, i))
        else:
            conn.execute("INSERT INTO evaluation_exercices (evaluation_id, exercice_id, ordre, "
                         "bareme_points) VALUES (?,?,?,?)", (ev_id, i, k, pts[i]))
    conn.execute("UPDATE evaluations SET mtime = CURRENT_TIMESTAMP WHERE id = ?", (ev_id,))
    return 1


def _vals_ev(x: dict) -> dict:
    """Contenu d'un atome EV tel que l'import l'écrit (cf. `_exercice`)."""
    return {"titre": x["titre"], "enonce": x["corps"], "corrige": "",
            "remed_enonce": _sujet_b(x), "remed_corrige": ""}


def _meme_contenu(row, vals: dict) -> bool:
    return all((row[k] or "") == v for k, v in vals.items())


def _evaluations_de(conn, exo_id: str) -> list:
    """Évaluations (id, titre, état) qui utilisent cet exercice."""
    return conn.execute("SELECT e.id, e.titre, e.etat_code FROM evaluation_exercices ee JOIN "
                        "evaluations e ON e.id = ee.evaluation_id WHERE ee.exercice_id = ? "
                        "ORDER BY e.numero", (exo_id,)).fetchall()


def _choisir_numero_ev(conn, seq: str, num_nat: int, vals: dict, ev_id: str | None,
                       position: int, pris: set, nums_pris: set) -> tuple[int, str]:
    r"""v0.52.6 — Décision R2 : un numéro EV occupé n'est jamais réattribué.

    La numérotation naturelle reste celle de la v0.52.2 (EV01… dans l'ordre
    du lot, en continu sur toutes les évaluations de la séquence). Un atome
    existant n'est réutilisé (et au besoin réécrit) que s'il est « libre ou à
    nous » : utilisé par aucune autre évaluation que celle-ci, et pas validé
    avec un autre contenu. Sinon le numéro est **occupé** : l'exercice prend
    le premier numéro après le plus grand de la séquence (« numéro de
    queue »), signalé dans le rapport. Ordre des candidats :
      1. l'atome EV de la séquence à la même position dans l'évaluation déjà
         en base (idempotence d'un exercice placé en queue) ;
      2. le numéro naturel ;
      3. le numéro de queue.
    Retourne (numéro, motif) ; motif vide si le numéro naturel est retenu."""
    def libre(row) -> bool:
        if row["id"] in pris:
            return False
        if row["etat_code"] == "valide" and not _meme_contenu(row, vals):
            return False
        return all(u["id"] == ev_id for u in _evaluations_de(conn, row["id"]))

    if ev_id is not None:
        comp = conn.execute(
            "SELECT x.* FROM evaluation_exercices ee JOIN exercices x ON x.id = ee.exercice_id "
            "WHERE ee.evaluation_id = ? AND x.niveau = ? AND x.sequence = ? AND "
            "x.serie_code = 'EV' ORDER BY ee.ordre", (ev_id, NIVEAU, seq)).fetchall()
        if position < len(comp) and libre(comp[position]):
            n = comp[position]["num"]
            return n, ("" if n == num_nat else f"place gardée en EV{n:02d}")
    row = conn.execute("SELECT * FROM exercices WHERE niveau = ? AND sequence = ? AND "
                       "serie_code = 'EV' AND num = ?", (NIVEAU, seq, num_nat)).fetchone()
    if num_nat not in nums_pris and (row is None or libre(row)):
        return num_nat, ""
    if row is None:
        motif = f"EV{num_nat:02d} déjà pris dans cet import"
    elif row["id"] in pris:
        motif = f"EV{num_nat:02d} déjà pris dans cet import"
    else:
        autres = [u["titre"] for u in _evaluations_de(conn, row["id"]) if u["id"] != ev_id]
        motif = (f"EV{num_nat:02d} utilisé par « {autres[0]} »" if autres
                 else f"EV{num_nat:02d} validé avec un autre contenu")
    m = conn.execute("SELECT MAX(num) FROM exercices WHERE niveau = ? AND sequence = ? AND "
                     "serie_code = 'EV'", (NIVEAU, seq)).fetchone()[0] or 0
    return max([m, num_nat, *nums_pris]) + 1, motif


def _plan_evaluations(lot: dict, objectifs_ids: dict, rapport: Rapport | None
                      ) -> "list[tuple[str, dict, list]]":
    """[(titre, paire, exercices préparés)] des évaluations importables du
    lot, dans l'ordre ; les autres sont signalées (si `rapport`)."""
    seq = lot["sequence"]
    plan = []
    for titre, paire in paires_evaluations(lot).items():
        try:
            exos = preparer_evaluation(titre, paire)
            inconnus = sorted({x["objectif"] for x in exos if not x["bonus"]}
                              - set(objectifs_ids))
            if inconnus:
                raise ImportErreur(f"objectif(s) inconnu(s) : {', '.join(inconnus)}")
        except ImportErreur as e:
            if rapport is not None:
                rapport.anomalie(f"{seq} évaluation « {titre} » non importée : découpage "
                                 f"impossible ({e})")
            continue
        plan.append((titre, paire, exos))
    return plan


def importer_evaluations(conn, lot: dict, objectifs_ids: dict, rapport: Rapport) -> None:
    """Évaluations et tests courts : atomes EV (sujet A → enonce, sujet B →
    remed_enonce, corrigés vides : la version corrigée vient des macros de
    réponse) numérotés EV01… dans l'ordre du lot, reliés à leur objectif
    (série EV ; le bonus n'en a pas) ; évaluation « note et critères » du
    module Évaluations avec barème par exercice et objectifs évalués.

    v0.52.6 — Avant l'import, retrait des évaluations listées dans
    `evaluations_retirees` et des exercices EV devenus orphelins (décision
    R1, `retirer_evaluations`) ; numéros EV occupés jamais réattribués (R2,
    `_choisir_numero_ev`) ; liens EV d'un atome réécrit remis à son objectif
    (R3) ; évaluation validée : ses exercices ne sont pas touchés (R4)."""
    seq = lot["sequence"]
    plan = _plan_evaluations(lot, objectifs_ids, rapport)
    voulu_par_num: dict = {}
    k = 0
    for _, _, exos in plan:
        for x in exos:
            k += 1
            voulu_par_num[k] = _vals_ev(x)
    retirer_evaluations(conn, lot, voulu_par_num, rapport)
    num = 0
    pris: set = set()
    nums_pris: set = set()
    liens: "OrderedDict[tuple, list]" = OrderedDict()
    for titre, paire, exos in plan:
        avant = conn.execute("SELECT id, etat_code FROM evaluations WHERE niveau = ? AND "
                             "titre = ? ORDER BY numero LIMIT 1", (NIVEAU, titre)).fetchone()
        if avant is not None and avant["etat_code"] == "valide":
            # R4 — rien n'est touché : ni l'évaluation, ni ses exercices EV.
            _evaluation(conn, titre, rapport, seq)
            num += len(exos)
            rapport.documents.append(f"{seq} évaluation « {titre} » : validée, non modifiée — "
                                     "exercices EV non touchés")
            continue
        ev_avant = avant["id"] if avant is not None else None
        voulus, etats, nums = [], {}, []
        # v0.52.7 — marqueurs de l'entrée d'évaluation (sujet A, sinon B),
        # appliqués à tous ses exercices EV ; hors comparaison R2.
        entree = paire.get("A") or paire.get("B") or {}
        if not any(entree.get(c) for c in mq.CHAMPS):
            entree = paire.get("B") or entree
        marques_ev = marqueurs_lot(entree, f"{seq} évaluation « {titre} »", rapport)
        # v0.52.8 (C1) — l'option « Calculatrice » du sujet suit le marquage :
        # écrite plus bas dans `evaluations.calculatrice` (plus d'information
        # « régler l'option du document »).
        # v0.52.9 — marquage par exercice (`calculatrice_exercices`, positions
        # non listées : `calculatrice` de l'entrée).
        par_position = calculatrice_exercices_lot(paire, len(exos),
                                                  f"{seq} évaluation « {titre} »", rapport)
        marques_exos = [{**marques_ev, "calculatrice": par_position.get(i + 1,
                                                                       marques_ev["calculatrice"])}
                        for i in range(len(exos))]
        coupe = mq.deux_parties(marques_exos)                        # D1
        for i, x in enumerate(exos):
            num += 1
            vals = _vals_ev(x)
            n, motif = _choisir_numero_ev(conn, seq, num, vals, ev_avant, i, pris, nums_pris)
            if motif and n != num:
                rapport.infos.append(f"{NIVEAU}/{seq} évaluation « {titre} », exercice {i + 1} "
                                     f"« {x['titre']} » : {motif} → EV{n:02d}")
            eid, etat = _exercice(conn, seq, "EV", n, vals, marques_exos[i])
            _compter_marqueurs(rapport, seq, marques_exos[i])
            pris.add(eid)
            nums_pris.add(n)
            nums.append(n)
            etats[etat] = etats.get(etat, 0) + 1
            if etat == "validé, non modifié":
                rapport.anomalie(f"{NIVEAU}/{seq}/EV{n:02d} validé dans l'atelier : contenu du "
                                 "lot non appliqué")
            voulu_obj = None if x["bonus"] else objectifs_ids[x["objectif"]]
            if etat == "mis à jour":
                # R3 — l'atome a changé de contenu (numéro réutilisé par la
                # recomposition) : ses liens EV vers un autre objectif sont
                # périmés.
                conn.execute("DELETE FROM objectif_exos WHERE exercice_id = ? AND serie = 'EV' "
                             "AND objectif_id IS NOT ?", (eid, voulu_obj))
            if voulu_obj is not None:
                liens.setdefault((voulu_obj, "EV"), []).append(eid)
            voulus.append((eid, x["points"]))
            rapport.journal["import"].append({
                "cle": f"{NIVEAU}/{seq}/EV{n:02d}", "id": eid, "evaluation": titre,
                "objectif": None if x["bonus"] else x["objectif"],
                "origine": paire["A"].get("origine", "")})
        ev_id, etat_ev = _evaluation(conn, titre, rapport, seq)
        n_obj = 0
        if etat_ev != "validée, non modifiée":
            change = _poser_exercices_evaluation(conn, ev_id, voulus)
            # v0.52.9 (I3) — sujet coupé en deux (D1) : réglage '' (les deux
            # mentions sont imposées par D2, aucun avertissement C3).
            change += _poser_calculatrice(conn, ev_id,
                                          "" if coupe else marques_ev["calculatrice"])
            for oc in dict.fromkeys(x["objectif"] for x in exos if not x["bonus"]):
                if conn.execute("SELECT 1 FROM evaluation_objectifs WHERE evaluation_id = ? AND "
                                "objectif_id = ?", (ev_id, objectifs_ids[oc])).fetchone() is None:
                    conn.execute("INSERT INTO evaluation_objectifs (evaluation_id, objectif_id) "
                                 "VALUES (?,?)", (ev_id, objectifs_ids[oc]))
                    n_obj += 1
            if etat_ev == "existante":
                etat_ev = "mise à jour" if (change or n_obj) else "inchangée"
        bonus = sum(x["points"] for x in exos if x["bonus"])
        total = sum(x["points"] for x in exos if not x["bonus"])
        plage = (f"EV{nums[0]:02d}–EV{nums[-1]:02d}" if nums == list(range(nums[0], nums[-1] + 1))
                 else ", ".join(f"EV{n:02d}" for n in nums))
        rapport.documents.append(
            f"{seq} évaluation « {titre} » : {etat_ev} — {len(exos)} exercice(s) EV "
            f"({plage} : "
            + ", ".join(f"{e} {n}" for e, n in etats.items())
            + f"), total {total:g}" + (f" + bonus {bonus:g}" if bonus else "")
            + (f" — {_resume_deux_parties(conn, ev_id, exos, marques_exos)}" if coupe
               else f" — {mq.LIBELLES_CALCULATRICE[marques_ev['calculatrice']]}"
               if marques_ev["calculatrice"] else ""))
    n = _lier_objectifs(conn, liens)
    if n:
        rapport.seq(seq)["lignes"].append(f"évaluations : {n} lien(s) exercice EV-objectif créé(s)")


# ── 5. Retrait d'évaluations (v0.52.6) ──────────────────────────────────────

def _lignes(conn, sql: str, args: tuple) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, args)]


def retirer_evaluations(conn, lot: dict, voulu_par_num: dict, rapport: Rapport) -> None:
    """v0.52.6 — Décision R1 « retirer avant d'importer » (décision de
    Laurent du 19 octobre : une évaluation sur 20 par séquence, tests courts
    réservés aux mises en route).

    Pour chaque titre de `evaluations_retirees` du lot :
      - évaluation N09 absente → rien (idempotence) ;
      - validée → gardée telle quelle, anomalie ;
      - sinon → retirée : `evaluation_objectifs`, `evaluation_exercices`,
        puis la ligne `evaluations`.
    Puis les exercices EV de la séquence devenus orphelins : ceux qui étaient
    dans une évaluation retirée, qui ne sont plus utilisés par aucune
    évaluation et qui ne sont plus dans le lot (le lot ne pose pas, à leur
    numéro, un exercice de même contenu). Non validés → retirés avec leurs
    liens (`objectif_exos`, `partie_exos_revision_approche`) ; validés →
    gardés, anomalie (leur numéro reste occupé : R2).

    Tout ce qui est retiré est copié, ligne par ligne, dans
    `rapport.journal["retraits"]` (journal JSON de --apply) : de quoi le
    restaurer par de simples INSERT."""
    seq = lot["sequence"]
    titres = [t for t in (lot.get("evaluations_retirees") or []) if t]
    if not titres:
        return
    gardes = {t for t, _ in paires_evaluations(lot).items()}
    liberes: list[str] = []
    for titre in titres:
        if titre in gardes:
            rapport.anomalie(f"{seq} évaluation « {titre} » à la fois retirée et présente dans "
                             "le lot : non retirée")
            continue
        evs = conn.execute("SELECT * FROM evaluations WHERE niveau = ? AND titre = ? "
                           "ORDER BY numero", (NIVEAU, titre)).fetchall()
        if not evs:
            rapport.documents.append(f"{seq} évaluation « {titre} » à retirer : absente "
                                     "(déjà retirée)")
            continue
        for ev in evs:
            if ev["etat_code"] == "valide":
                rapport.anomalie(f"{seq} évaluation « {titre} » à retirer, mais validée dans le "
                                 "module Évaluations : gardée")
                rapport.documents.append(f"{seq} évaluation « {titre} » : validée, gardée")
                continue
            exos = _lignes(conn, "SELECT * FROM evaluation_exercices WHERE evaluation_id = ? "
                                 "ORDER BY ordre", (ev["id"],))
            objs = _lignes(conn, "SELECT * FROM evaluation_objectifs WHERE evaluation_id = ?",
                           (ev["id"],))
            rapport.journal.setdefault("retraits", []).append({
                "quoi": "evaluation", "sequence": seq, "titre": titre,
                "evaluations": dict(ev), "evaluation_exercices": exos,
                "evaluation_objectifs": objs})
            conn.execute("DELETE FROM evaluation_objectifs WHERE evaluation_id = ?", (ev["id"],))
            conn.execute("DELETE FROM evaluation_exercices WHERE evaluation_id = ?", (ev["id"],))
            conn.execute("DELETE FROM evaluations WHERE id = ?", (ev["id"],))
            liberes += [e["exercice_id"] for e in exos]
            rapport.documents.append(f"{seq} évaluation « {titre} » (n° {ev['numero']}) : "
                                     f"retirée ({len(exos)} exercice(s), {len(objs)} objectif(s) "
                                     "évalué(s))")
    for eid in dict.fromkeys(liberes):
        x = conn.execute("SELECT * FROM exercices WHERE id = ?", (eid,)).fetchone()
        if x is None or (x["niveau"], x["sequence"], x["serie_code"]) != (NIVEAU, seq, "EV"):
            continue                    # exercice d'ailleurs ajouté par l'auteur : intouché
        cle = f"{NIVEAU}/{seq}/EV{x['num']:02d}"
        if conn.execute("SELECT 1 FROM evaluation_exercices WHERE exercice_id = ?",
                        (eid,)).fetchone() is not None:
            continue                    # encore utilisé par une autre évaluation
        voulu = voulu_par_num.get(x["num"])
        if voulu is not None and _meme_contenu(x, voulu):
            continue                    # toujours dans le lot, à ce numéro : réutilisé
        if "etat_code" in x.keys() and x["etat_code"] == "valide":
            rapport.anomalie(f"{cle} « {x['titre']} » orphelin mais validé dans l'atelier : "
                             "gardé (numéro occupé)")
            continue
        liens = _lignes(conn, "SELECT * FROM objectif_exos WHERE exercice_id = ?", (eid,))
        parts = _lignes(conn, "SELECT * FROM partie_exos_revision_approche WHERE "
                              "exercice_id = ?", (eid,))
        rapport.journal.setdefault("retraits", []).append({
            "quoi": "exercice", "cle": cle, "exercices": dict(x), "objectif_exos": liens,
            "partie_exos_revision_approche": parts})
        conn.execute("DELETE FROM objectif_exos WHERE exercice_id = ?", (eid,))
        conn.execute("DELETE FROM partie_exos_revision_approche WHERE exercice_id = ?", (eid,))
        conn.execute("DELETE FROM exercices WHERE id = ?", (eid,))
        rapport.documents.append(f"{cle} « {x['titre']} » : orphelin, retiré "
                                 f"({len(liens)} lien(s) objectif)")


# ── Orchestration ────────────────────────────────────────────────────────────

def executer(conn, lots: list[dict], ref: dict, rapport: Rapport, images: Path,
             ecrire_fichiers: bool, racine: Path = RACINE_APPLI,
             data_dir: Path | None = None) -> None:
    """Toutes les opérations de base, dans la transaction de `conn` (le
    commit est fait par l'appelant).

    Exception : la réparation des clés étrangères vers `objectifs_v2`
    (bases d'avant v0.14.7, cf. services.retraits.rediriger_objectifs_v2)
    est validée à part, avant l'import : c'est la même réparation que l'appli
    fait à son démarrage en v0.52.0, et sans elle aucun lien vers un objectif
    nouvellement créé ne passe."""
    conn.row_factory = sqlite3.Row
    from services import retraits
    rep = retraits.rediriger_objectifs_v2(conn, data_dir)
    if rep:
        rapport.infos.append(
            "Réparation de la base : clés étrangères vers l'ancienne table objectifs_v2 "
            f"redirigées vers objectifs ({', '.join(rep['tables'])})"
            + (f" ; liens orphelins retirés : {rep['orphelins']}" if rep["orphelins"] else ""))
    conn.execute("PRAGMA foreign_keys = ON")
    # v0.52.7 — colonnes des marqueurs (migration idempotente de l'appli),
    # pour un import lancé avant le premier démarrage de la nouvelle version.
    if not mq.colonnes_presentes(conn):
        mq.migrer(conn)
        rapport.infos.append("Base complétée : colonnes ordinateur et calculatrice des "
                             "exercices (v0.52.7)")
    if mq.migrer_evaluations(conn):                                  # v0.52.8 (C1)
        rapport.infos.append("Base complétée : colonne calculatrice des évaluations (v0.52.8)")
    if mq.migrer_duree_partie1(conn):                                # v0.52.9 (D4)
        rapport.infos.append("Base complétée : colonne duree_partie1 des évaluations (v0.52.9)")
    if not archivage_fait(conn):
        archiver_cycle3(conn, rapport, racine)
    themes = appliquer_cycle3(conn, ref, rapport)
    figures = {}
    mer_imp = _module_mer()                                           # v0.53.0
    ref_mer = mer_imp.referentiel_mer()
    imp = sys.modules[__name__]
    for lot in lots:
        if mer_imp.est_lot_mer(lot):
            figures[lot["sequence"]] = mer_imp.importer_lot_mer(conn, imp, lot, themes,
                                                                ref_mer, rapport)
        else:
            figures[lot["sequence"]] = importer_lot(conn, lot, ref, rapport)
    copier_figures(lots, figures, images, rapport, ecrire_fichiers)
    signaler_cycle4(conn, rapport)
    from services.style6e import MACROS as MACROS_STYLE6E
    for seq, ms in macros_locales(lots).items():
        if ms:
            rapport.infos.append(f"{seq} : macros locales utilisées (fournies par "
                                 f"seqenseigne-style6e v0.9) : {', '.join(ms)}")
        # v0.52.5 — Une macro \seqLoc… que le module ne fournit pas ferait
        # échouer la compilation de tous les documents de la séquence.
        absentes = [m for m in ms if m not in MACROS_STYLE6E]
        if absentes:
            rapport.anomalie(f"{seq} : macros locales absentes du module seqenseigne-style6e "
                             f"(à verser dans le .dtx) : {', '.join(absentes)}")
    # v0.52.8 (I2) — même contrôle pour les macros \seq…Six du module
    # (\seqAstuceSix, v0.8) ; nombre d'astuces par séquence.
    for seq, (ms, n_astuces) in macros_module(lots).items():
        absentes = [m for m in ms if m not in MACROS_STYLE6E]
        if absentes:
            rapport.anomalie(f"{seq} : macros absentes du module seqenseigne-style6e v0.9 "
                             f"(compilation impossible) : {', '.join(absentes)}")
        if n_astuces:
            rapport.infos.append(f"{seq} : {n_astuces} astuce(s) \\seqAstuceSix (module "
                                 "seqenseigne-style6e v0.9)")


def resoudre_base(db: str | None, racine: Path = RACINE_APPLI) -> Path:
    """Base explicite, sinon celle du profil atelier (data_atelier\\ après la
    bascule, data\\ avant), comme `lancer.bat atelier`."""
    if db:
        return Path(db).resolve()
    from services.bascule import NOM_DB, dossier_par_defaut
    return dossier_par_defaut(racine, "atelier") / NOM_DB


def _nom_libre(p: Path) -> Path:
    """v0.52.6 — Deux exécutions dans la même seconde ne s'écrasent pas : la
    sauvegarde et le journal du premier --apply (retraits compris) restent."""
    k = 1
    q = p
    while q.exists():
        k += 1
        q = p.with_name(f"{p.stem}_{k}{p.suffix}")
    return q


def sauvegarder(db: Path) -> Path:
    d = db.parent / "sauvegardes"
    d.mkdir(parents=True, exist_ok=True)
    cible = _nom_libre(d / f"avant_import_lot6e_{datetime.now():%Y-%m-%d_%H%M%S}.db")
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    dst = sqlite3.connect(cible)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return cible


def essai_a_blanc(db: Path, lots, ref, images: Path) -> Rapport:
    """Exécute tout sur une copie en mémoire de la base : le rapport est
    exactement celui de --apply, et rien n'est écrit."""
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    mem = sqlite3.connect(":memory:")
    try:
        src.backup(mem)
    finally:
        src.close()
    rapport = Rapport()
    try:
        executer(mem, lots, ref, rapport, images, ecrire_fichiers=False)
    finally:
        mem.close()
    return rapport


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Import des séquences de 6e dans l'atelier "
                                             "(v0.52.2)")
    ap.add_argument("--apply", action="store_true", help="applique (sinon essai à blanc)")
    ap.add_argument("--yes", action="store_true", help="sans confirmation")
    ap.add_argument("--db", help="chemin de la base (défaut : base du profil atelier)")
    ap.add_argument("--lots", default=str(LOTS_DEFAUT), help="dossier des lots S01, S02…")
    args = ap.parse_args(argv)
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except Exception:
            pass

    lots_dir = Path(args.lots)
    if not lots_dir.is_dir():
        print(f"Dossier des lots introuvable : {lots_dir}")
        return 2
    ref = charger_referentiel()
    lots = charger_lots(lots_dir)
    if not lots:
        print(f"Aucun lot (S01\\S01.json…, M01\\M01.json…) dans {lots_dir}")
        return 2
    db = resoudre_base(args.db)
    if not db.is_file():
        print(f"Base introuvable : {db}")
        return 2
    from services import repartition
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        role = repartition.role(c)
    finally:
        c.close()
    if role == "classe":
        print(f"{db} est la base de l'appli de classe : l'import se fait dans l'atelier.")
        return 2
    images = db.parent / "images"
    print(f"Base : {db}" + (f" (rôle {role})" if role else ""))
    print(f"Lots : {', '.join(l['sequence'] for l in lots)} ({lots_dir})\n")

    rapport = essai_a_blanc(db, lots, ref, images)
    print(rapport.texte())
    if not args.apply:
        print("\n(essai à blanc : rien n'a été écrit — relancer avec --apply pour appliquer)")
        return 0
    if not args.yes:
        rep = input("\nAppliquer ? [o/N] ").strip().lower()
        if rep not in ("o", "oui", "y", "yes"):
            print("Annulé.")
            return 1

    sauvegarde = sauvegarder(db)
    print(f"\nSauvegarde : {sauvegarde}")
    conn = sqlite3.connect(db)
    rapport = Rapport()
    try:
        executer(conn, lots, ref, rapport, images, ecrire_fichiers=False, data_dir=db.parent)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"\nErreur, rien de l'import n'a été écrit dans la base : {e}")
        return 3
    finally:
        conn.close()
    copier_figures(lots, {l["sequence"]: _figures_du_journal(l) for l in lots}, images,
                   Rapport(), ecrire=True)
    journal = _nom_libre(db.parent / "sauvegardes" /
                         f"journal_import_lot6e_{datetime.now():%Y-%m-%d_%H%M%S}.json")
    journal.write_text(json.dumps({"base": str(db), "sauvegarde": str(sauvegarde),
                                   **rapport.journal}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    (journal.parent / journal.name.replace("journal_", "rapport_").replace(".json", ".txt")
     ).write_text(rapport.texte(), encoding="utf-8")
    print(f"Journal (correspondances, retour arrière) : {journal}")
    print("\nImport appliqué.")
    return 0


def _figures_du_journal(lot: dict) -> set:
    """Figures utilisées par les éléments importés en base d'un lot
    (v0.52.2 : documents TP, AC, AT et évaluations compris ; v0.53.0 : lots
    de mise en route)."""
    mer_imp = _module_mer()
    if mer_imp.est_lot_mer(lot):
        return mer_imp.figures_du_lot(sys.modules[__name__], lot)
    noms: set = set()
    for o in lot.get("objectifs", []):
        for e in o.get("exercices", []) + o.get("activites", []):
            noms |= _figures(lot, e)
    for cle, _, _ in DOCUMENTS_LOT:
        for d in lot.get(cle, []) or []:
            noms |= _figures(lot, d)
    for ev in lot.get("evaluations", []) or []:
        noms |= _figures(lot, ev)
    return noms


if __name__ == "__main__":
    sys.exit(main())
