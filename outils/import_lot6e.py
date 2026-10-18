#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""outils/import_lot6e.py — v0.52.0

Importe les séquences de 6e (lots S01, S02, S03…) dans l'atelier interne
(niveau N09), remplace les séquences du cycle 3 par les dix séquences du
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
  2. **Cycle 3** — six thèmes (A à F) et dix séquences (S01 à S10) d'après
     `outils/objectifs_6e.json`.
  3. **Import N09** — séquence-niveau, parties, objectifs (dont l'objectif
     « Cours » de chaque partie), exercices F/A/E avec remédiations,
     activités d'introduction (série approche AE, rattachées à la partie),
     fiches de résumé (une par objectif, sections), liens objectif ↔
     exercice et objectif ↔ fiche, figures copiées dans `images\`.
     Tout est créé « en cours ».
  4. **Documents hors base** — travaux personnels, activités
     complémentaires, séances d'atelier et évaluations : fichiers `.tex`
     compilables (version élève et version corrigée) dans un dossier de
     sortie.

Idempotence : objectifs repérés par (niveau, séquence, code), exercices par
(niveau, séquence, série, num), fiches par leur objectif. Une deuxième
exécution ne crée rien ; un contenu modifié dans le lot est mis à jour (sauf
élément validé dans l'atelier, laissé tel quel et signalé).

Usage (Windows, depuis `appli\`) :
    ..\outils\python\python.exe .\outils\import_lot6e.py                 # essai à blanc
    ..\outils\python\python.exe .\outils\import_lot6e.py --apply         # applique (confirmation)
    ..\outils\python\python.exe .\outils\import_lot6e.py --apply --yes   # sans confirmation
Options : --db CHEMIN (base), --lots DOSSIER (défaut ..\reference\lot6e),
--sortie DOSSIER (défaut ..\reference\lot6e\documents_tex),
--documents-seulement (écrit les .tex, ne touche pas à la base).

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
from services.atomes import _deduire_type_format          # noqa: E402

NIVEAU = "N09"
CYCLE = "C03"
NIVEAUX_CYCLE3 = ("N07", "N08", "N09")
ANCIENS_CODES = tuple(f"S{i:02d}" for i in range(1, 17))
REFERENTIEL = Path(__file__).resolve().parent / "objectifs_6e.json"
LOTS_DEFAUT = RACINE_APPLI.parent / "reference" / "lot6e"
SUFFIXE_ARCHIVE = " (archive)"

SERIE_TEXTE = {"F": "fondamental", "A": "avancé", "E": "exploration", "AE": "approche"}
RE_GRAPHIQUE = re.compile(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
RE_LOC = re.compile(r"\\(seqLoc[A-Za-z]+)")


class ImportErreur(Exception):
    pass


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
    """Lots S01/S01.json, S02/S02.json… triés par code de séquence."""
    dossier = Path(dossier)
    lots = []
    for d in sorted(p for p in dossier.iterdir() if p.is_dir() and re.fullmatch(r"S\d\d", p.name)):
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
        L.append("")
        L.append("== Figures ==")
        L += [f"  {x}" for x in self.figures] or ["  aucune"]
        if self.documents:
            L.append("")
            L.append("== Documents hors base (.tex) ==")
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
            conn.execute("UPDATE sequences_du_cycle SET numero=?, nom=?, theme_id=? WHERE id=?",
                         (s["numero"], s["nom"], tid, r["id"]))
            etat = "mise à jour"
        else:
            etat = "inchangée"
        rapport.cycle.append(f"séquence {s['code']} {s['nom']} (thème {s['theme']}) : {etat}")
    return themes


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


def _objectif(conn, sn_id: str, partie_id: str, code: str, d: dict) -> tuple[str, str]:
    """(id, état) de l'objectif (niveau, séquence, code)."""
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
        return r["id"], "mis à jour"
    return r["id"], "inchangé"


_CHAMPS_EXO = ("titre", "enonce", "corrige", "remed_enonce", "remed_corrige")


def _exercice(conn, seq: str, serie_code: str, num: int, src: dict) -> tuple[str, str]:
    """(id, état) de l'exercice (N09, séquence, série, num)."""
    vals = {"titre": src.get("titre", "") or "",
            "enonce": src.get("enonce", src.get("latex", "")) or "",
            "corrige": src.get("corrige", "") or "",
            "remed_enonce": src.get("remed_enonce", "") or "",
            "remed_corrige": src.get("remed_corrige", "") or ""}
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
        oid, etat = _objectif(conn, sn["id"], pid, code_c, cours)
        cours_ids[p["numero"]] = oid
        rapport.obj(seq, f"{seq}-{code_c}", "Cours — " + cours["nom"])["objectif"] = etat

    approche: dict[int, list] = {n: [] for n in parties}
    vus: dict = {}
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
        oid, etat = _objectif(conn, sn["id"], parties[numero], d["code"], d)
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
            eid, etat_e = _exercice(conn, seq, sc, cle[1], e)
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
        for a in o.get("activites", []):
            cle = ("AE", int(a["num"]))
            if cle in vus:
                rapport.anomalie(f"{seq} AE{cle[1]:02d} en double, second ignoré")
                continue
            vus[cle] = code
            eid, etat_a = _exercice(conn, seq, "AE", cle[1], a)
            approche[numero].append(eid)
            Rapport.compter(ro, "activités AE", etat_a)
            figures |= _figures(lot, a)
            rapport.journal["import"].append({"cle": f"{NIVEAU}/{seq}/AE{cle[1]:02d}",
                                              "id": eid, "objectif": code,
                                              "origine": a.get("origine", "")})
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
    (le module seqenseigne-style6e v0.4 les fournit)."""
    out = {}
    for lot in lots:
        contenu = {k: v for k, v in lot.items() if k not in ("_dossier", "macros_locales")}
        brut = json.dumps(contenu, ensure_ascii=False).replace("\\\\", "\\")
        out[lot["sequence"]] = sorted(set(RE_LOC.findall(brut)))
    return out


# ── 4. Documents hors base (.tex) ────────────────────────────────────────────

PREAMBULE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amssymb}
\usepackage{needspace}
\usepackage[sixieme,geometrie]{seqenseigne}
\graphicspath{{figures/}}
\renewcommand{\familydefault}{\sfdefault}
\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}
\fancyhead[R]{\small\bfseries %(entete)s -- page \thepage}
\setlength{\parindent}{0pt}
\setlength{\parskip}{2pt}\setlength{\emergencystretch}{3em}
\setlist{itemsep=1pt,topsep=2pt,parsep=0pt}
"""


def _document_tex(entete: str, corps: str, corrige: bool, source: str) -> str:
    return ("%% Généré par outils/import_lot6e.py (seqenseigne v0.52.0) — " + source + "\n"
            + PREAMBULE % {"entete": entete}
            + "\\begin{document}\n"
            + ("\\seqVersionCorrigee\n" if corrige else "")
            + corps.strip() + "\n\\end{document}\n")


def documents_hors_base(lot: dict, ref: dict) -> list[dict]:
    """Liste des documents hors base d'un lot : {nom, type, titre, latex, meta}."""
    seq = lot["sequence"]
    s_ref = next((s for s in ref["sequences"] if s["code"] == seq), {"nom": lot.get("titre", seq)})
    docs = []
    for k, tp in enumerate(lot.get("travaux_personnels", []), start=1):
        docs.append({"nom": f"{seq}_TP{k}", "type": "travail_personnel", "src": tp})
    for k, ac in enumerate(lot.get("activites_complementaires", []), start=1):
        docs.append({"nom": f"{seq}_AC{k}", "type": "activite_complementaire", "src": ac})
    for k, at in enumerate(lot.get("seances_atelier", []), start=1):
        docs.append({"nom": f"{seq}_ATELIER{k}", "type": "seance_atelier", "src": at})
    n, titres = 0, {}
    for ev in lot.get("evaluations", []):
        t = ev.get("titre", "")
        if t not in titres:
            n += 1
            titres[t] = n
        docs.append({"nom": f"{seq}_EV{titres[t]}{ev.get('sujet', '') or ''}",
                     "type": "evaluation", "src": ev})
    for d in docs:
        d["titre"] = d["src"].get("titre", "")
        d["entete"] = s_ref["nom"]
    return docs


def ecrire_documents(lots: list[dict], ref: dict, sortie: Path, rapport: Rapport,
                     ecrire: bool) -> None:
    for lot in lots:
        seq = lot["sequence"]
        docs = documents_hors_base(lot, ref)
        if not docs:
            continue
        dossier = Path(sortie) / seq
        index = []
        for d in docs:
            src = d["src"]
            meta = {k: v for k, v in src.items() if k != "latex"}
            index.append({"fichier": d["nom"], "type": d["type"], **meta})
            rapport.documents.append(f"{d['nom']}_eleve.tex / _corrige.tex — {d['type']} — "
                                     f"{d['titre']}")
            if ecrire:
                dossier.mkdir(parents=True, exist_ok=True)
                for corr, suff in ((False, "eleve"), (True, "corrige")):
                    (dossier / f"{d['nom']}_{suff}.tex").write_text(
                        _document_tex(d["entete"], src.get("latex", ""), corr,
                                      f"{seq} {d['type']} : {d['titre']}"),
                        encoding="utf-8")
        if ecrire:
            figs = lot["_dossier"] / "figures"
            if figs.is_dir() and any(figs.iterdir()):
                shutil.copytree(figs, dossier / "figures", dirs_exist_ok=True)
            (dossier / "documents.json").write_text(
                json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


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
    if not archivage_fait(conn):
        archiver_cycle3(conn, rapport, racine)
    appliquer_cycle3(conn, ref, rapport)
    figures = {}
    for lot in lots:
        figures[lot["sequence"]] = importer_lot(conn, lot, ref, rapport)
    copier_figures(lots, figures, images, rapport, ecrire_fichiers)
    signaler_cycle4(conn, rapport)
    for seq, ms in macros_locales(lots).items():
        if ms:
            rapport.infos.append(f"{seq} : macros locales utilisées (fournies par "
                                 f"seqenseigne-style6e v0.4) : {', '.join(ms)}")


def resoudre_base(db: str | None, racine: Path = RACINE_APPLI) -> Path:
    """Base explicite, sinon celle du profil atelier (data_atelier\\ après la
    bascule, data\\ avant), comme `lancer.bat atelier`."""
    if db:
        return Path(db).resolve()
    from services.bascule import NOM_DB, dossier_par_defaut
    return dossier_par_defaut(racine, "atelier") / NOM_DB


def sauvegarder(db: Path) -> Path:
    d = db.parent / "sauvegardes"
    d.mkdir(parents=True, exist_ok=True)
    cible = d / f"avant_import_lot6e_{datetime.now():%Y-%m-%d_%H%M%S}.db"
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
    ap = argparse.ArgumentParser(description="Import des séquences de 6e dans l'atelier (v0.52.0)")
    ap.add_argument("--apply", action="store_true", help="applique (sinon essai à blanc)")
    ap.add_argument("--yes", action="store_true", help="sans confirmation")
    ap.add_argument("--db", help="chemin de la base (défaut : base du profil atelier)")
    ap.add_argument("--lots", default=str(LOTS_DEFAUT), help="dossier des lots S01, S02…")
    ap.add_argument("--sortie", help="dossier des .tex hors base (défaut : <lots>\\documents_tex)")
    ap.add_argument("--documents-seulement", action="store_true",
                    help="écrit seulement les .tex hors base (ne touche pas à la base)")
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
        print(f"Aucun lot (S01\\S01.json…) dans {lots_dir}")
        return 2
    sortie = Path(args.sortie) if args.sortie else lots_dir / "documents_tex"

    if args.documents_seulement:
        r = Rapport()
        ecrire_documents(lots, ref, sortie, r, ecrire=True)
        print("\n".join(r.documents))
        print(f"\nDocuments écrits dans {sortie}")
        return 0

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
    ecrire_documents(lots, ref, sortie, rapport, ecrire=False)
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
    ecrire_documents(lots, ref, sortie, rapport, ecrire=True)
    journal = db.parent / "sauvegardes" / f"journal_import_lot6e_{datetime.now():%Y-%m-%d_%H%M%S}.json"
    journal.write_text(json.dumps({"base": str(db), "sauvegarde": str(sauvegarde),
                                   **rapport.journal}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    (journal.parent / journal.name.replace("journal_", "rapport_").replace(".json", ".txt")
     ).write_text(rapport.texte(), encoding="utf-8")
    print(f"Journal (correspondances, retour arrière) : {journal}")
    print(f"Documents hors base : {sortie}")
    print("\nImport appliqué.")
    return 0


def _figures_du_journal(lot: dict) -> set:
    """Figures utilisées par les éléments importés en base d'un lot."""
    noms: set = set()
    for o in lot.get("objectifs", []):
        for e in o.get("exercices", []) + o.get("activites", []):
            noms |= _figures(lot, e)
    return noms


if __name__ == "__main__":
    sys.exit(main())
