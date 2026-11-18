#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""outils/archiver_structure_niveau.py — v0.59.0

Archive la structure de 2025 d'un niveau du cycle 4 (4e d'abord : N11) avant
l'import des lots du nouveau référentiel (décision D1, `doc/redemarrage_v0_
59_0.md` ; besoins `col4/besoins_appli_fiches_4e.md`, évolution E3 ; point 15
de l'inventaire de l'étape 3, réponse par défaut acceptée le 16 novembre 2026).

Pourquoi : l'atelier N11 garde, sous les codes A1…E1, les séquences-niveaux,
parties, objectifs (codes 01 à 15) et atomes de la 4e de 2025. L'import d'un
lot de 4e repère les objectifs par (niveau, séquence, code) et les exercices
par (niveau, séquence, série, numéro) : sans archivage, il réécrirait l'ancien
A1-02 en gardant ses liens d'exercices de 2025, et l'exercice EN01 du lot
écraserait l'ancien F01. Les contenus repris sont **copiés** dans les lots
(point 1 de l'inventaire) : rien n'est perdu, l'archive garde la 4e de 2025
entière.

Ce que fait l'outil, pour le niveau demandé :

  1. chaque séquence-niveau vivante en code de thème (A1…E1, A2 comprise)
     devient la séquence d'archive « X + numéro de l'ancien code » d'après
     `outils/correspondance_codes_2027.json` (A1 ← S03 → X03, A2 ← S15 → X15,
     A3 ← S01 → X01…), avec ses parties, objectifs, liens objectif ↔ atome,
     cartes mentales et précédences propres (identifiants inchangés) ;
  2. la séquence du cycle d'archive est créée si elle manque (numéro 100 + n,
     nom du cycle suivi de « (archive) », thème de la séquence vivante :
     comme X02, X04, X10 de la migration) ; elle sert aux trois niveaux ;
  3. les atomes du niveau rangés sous ces codes (notions, méthodes,
     exercices, fiches de résumé, cartes d'automatisme, cartes mentales)
     passent sous le code d'archive ; la colonne `fichier` ne change pas
     (les fichiers LaTeX ne sont pas renommés et un nouveau scan ne recrée
     rien : le scanner n'ajoute que les fichiers absents de la base) ;
  4. les précédences et les `origin_seq` des liens d'exercices qui visent
     <niveau>/<code> visent <niveau>/<archive> (c'est le contenu de 2025) ;
  5. la marque `archivages_structure` est posée : l'import des lots du
     niveau (`outils/import_lot6e.py --niveau N11`) la réclame.

Ce qui n'est jamais touché, vérifié avant validation (toute différence annule
la transaction) : toutes les autres tables (instantanés `referentiel_*` des
référentiels figés N11_v2025 « utilisé » et 2025_N11b « verrouillé »,
publications, évaluations, partie classe…), les lignes des autres niveaux et
toute ligne que le journal ne nomme pas, les fichiers de `referentiels\`
(`_verrouille\`, `_publication\`) et de `referentiels_fichiers\`. Les séquences
d'archive X02, X04, X10 de la migration ne bougent pas.

Modes :
  essai à blanc (défaut) : tout est exécuté sur une copie en mémoire ;
  --apply : sauvegarde .db (`sauvegardes\avant_archivage_<niveau>_<date>.db`),
      une transaction, journal `sauvegardes\journal_archivage_<niveau>_<date>
      .json` et rapport `.txt` ;
  --annuler [JOURNAL] : retour arrière d'après le journal (le dernier du
      niveau par défaut) ; refusé si un contenu a été créé depuis sous un code
      archivé (lot importé : restaurer plutôt la sauvegarde) ou si une ligne
      archivée a été modifiée.

Idempotent : un niveau déjà archivé répond « rien à faire ».

Usage (Windows, depuis `appli\`) :
    ..\outils\python\python.exe .\outils\archiver_structure_niveau.py --niveau N11
    ..\outils\python\python.exe .\outils\archiver_structure_niveau.py --niveau N11 --apply
    ..\outils\python\python.exe .\outils\archiver_structure_niveau.py --niveau N11 --annuler
Options : --db CHEMIN, --yes.

Codes de sortie : 0 succès / essai / rien à faire, 1 annulé par
l'utilisateur, 2 refus (base, rôle, niveau, conflit), 3 erreur (rien n'est
écrit).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

RACINE_APPLI = Path(__file__).resolve().parent.parent
if str(RACINE_APPLI) not in sys.path:          # lancement par chemin (Windows)
    sys.path.insert(0, str(RACINE_APPLI))

from services import codes_sequence as cs     # noqa: E402
from services import fiches_cycle4 as fc4     # noqa: E402

VERSION = "0.59.0"
CYCLE = "C04"
NIVEAUX = ("N10", "N11", "N12")
CORRESPONDANCE = Path(__file__).resolve().parent / "correspondance_codes_2027.json"
SUFFIXE_ARCHIVE = " (archive)"
PREFIXE_JOURNAL = "journal_archivage_"
ATOMES = ("notions", "methodes", "exercices", "fiches_resume", "cartes_automatisme",
          "cartes_mentales")
# Tables où l'outil écrit ; toute autre table est vérifiée identique.
TABLES_TOUCHEES = ("sequences_du_cycle", "sequences_par_niveau",
                   "sequence_par_niveau_precedences", "partie_precedences",
                   "objectif_exos", "partie_exos_revision_approche",
                   "archivages_structure", *ATOMES)


class ArchivageErreur(Exception):
    """Refus (prérequis, conflit) : rien n'est écrit."""


def _mig():
    """Journal et retour arrière de l'outil de migration v0.58 (mêmes
    garanties), que l'outil soit lancé par chemin ou importé."""
    try:
        from outils import migrer_themes_codes_2027 as m
    except ImportError:                                   # pragma: no cover
        import migrer_themes_codes_2027 as m
    return m


def _table(conn, nom: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (nom,)).fetchone() is not None


def _cols(conn, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]


# ── Table de correspondance ─────────────────────────────────────────────────

def codes_archive(chemin: Path = CORRESPONDANCE) -> "OrderedDict[str, dict]":
    """{code vivant: {archive, numero, ancien}} des séquences du cycle 4 :
    A1 (ancien S03) → X03, numéro 103 ; A2 (S15, nouvelle) → X15, 115."""
    corr = json.loads(Path(chemin).read_text(encoding="utf-8"))
    out: "OrderedDict[str, dict]" = OrderedDict()
    for s in corr["cycles"][CYCLE]["sequences"]:
        ancien, nouveau = s.get("ancien") or "", s.get("nouveau") or ""
        if not (cs.est_code_ancien(ancien) and cs.est_code_theme(nouveau)):
            continue
        n = int(ancien[1:])
        out[nouveau] = {"archive": f"X{n:02d}", "numero": 100 + n, "ancien": ancien}
    return out


# ── Rapport ──────────────────────────────────────────────────────────────────

class Rapport:
    def __init__(self, niveau: str):
        self.niveau = niveau
        self.sequences: "OrderedDict[str, list[str]]" = OrderedDict()
        self.lignes: list[str] = []
        self.jamais: list[str] = []
        self.anomalies: list[str] = []
        self.infos: list[str] = []
        self.avertissements: list[str] = []          # v0.60.0 (F2)

    def texte(self) -> str:
        L = [f"Archivage de la structure de 2025 — {self.niveau} — seqenseigne {VERSION}", ""]
        if self.sequences:
            L.append("== Séquences archivées (code vivant → archive)")
            for k, v in self.sequences.items():
                L.append(f"  {k}")
                L += [f"    {x}" for x in v]
            L.append("")
        if self.lignes:
            L.append("== Autres écritures")
            L += [f"  {x}" for x in self.lignes]
            L.append("")
        if self.jamais:
            L.append("== Jamais touché (vérifié avant validation)")
            L += [f"  {x}" for x in self.jamais]
            L.append("")
        if self.infos:
            L.append("== Informations")
            L += [f"  - {x}" for x in self.infos]
            L.append("")
        if self.avertissements:                                      # v0.60.0 (F2)
            L.append("== Avertissements (non bloquants)")
            L += [f"  ⚠ {x}" for x in self.avertissements]
            L.append("")
        L.append("== Anomalies" + ("" if self.anomalies else " : aucune"))
        L += [f"  ! {x}" for x in self.anomalies]
        return "\n".join(L)


# ── Empreintes ──────────────────────────────────────────────────────────────

def _sha_requete(conn, sql: str) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    for r in conn.execute(sql):
        h.update(repr(tuple(r)).encode("utf-8"))
        n += 1
    return h.hexdigest(), n


def empreinte_hors_tables_touchees(conn, data_dir: Path | None) -> "OrderedDict[str, str]":
    """SHA-256 de chaque table où l'outil n'écrit pas et des fichiers de
    `referentiels\\` et `referentiels_fichiers\\`."""
    m = _mig()
    e: "OrderedDict[str, str]" = OrderedDict()
    for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                             "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
        if t in TABLES_TOUCHEES:
            continue
        cols = ", ".join(f'"{c}"' for c in _cols(conn, t))
        sha, n = _sha_requete(conn, f'SELECT {cols} FROM "{t}" ORDER BY {cols}')
        e[f"table {t} ({n} lignes)"] = sha
    if data_dir is not None:
        for sous in ("referentiels", "referentiels_fichiers"):
            d = Path(data_dir) / sous
            h = hashlib.sha256()
            n = 0
            if d.is_dir():
                for p in sorted(x for x in d.rglob("*") if x.is_file()):
                    h.update(str(p.relative_to(d)).replace("\\", "/").encode("utf-8"))
                    h.update(m._sha_fichier(p).encode())
                    n += 1
            e[f"fichiers {sous}\\ ({n})"] = h.hexdigest()
    return e


def lignes_touchables(conn) -> dict:
    """{table: {rowid: ligne}} des tables où l'outil écrit."""
    out = {}
    for t in TABLES_TOUCHEES:
        if _table(conn, t):
            out[t] = {r[0]: tuple(r[1:]) for r in conn.execute(f'SELECT rowid, * FROM "{t}"')}
    return out


def ecarts_hors_journal(avant: dict, apres: dict, conn, ops: list[dict]) -> list[str]:
    """Lignes des tables touchées qui ont changé sans que le journal les nomme."""
    nommees: dict = {}
    for op in ops:
        cle = op["cle"]
        where = " AND ".join(f'"{k}"=?' for k in cle)
        r = conn.execute(f'SELECT rowid FROM "{op["table"]}" WHERE {where}',
                         tuple(cle.values())).fetchone()
        if r is not None:
            nommees.setdefault(op["table"], set()).add(r[0])
    ecarts = []
    for t in set(avant) | set(apres):
        a, b = avant.get(t, {}), apres.get(t, {})
        for rid in set(a) | set(b):
            if a.get(rid) != b.get(rid) and rid not in nommees.get(t, set()):
                ecarts.append(f"{t} (rowid {rid})")
    return sorted(ecarts)


# ── Archivage ───────────────────────────────────────────────────────────────

def precontroles(conn, niveau: str) -> list[str]:
    from services import repartition
    refus = []
    if niveau not in NIVEAUX:
        refus.append(f"niveau {niveau!r} : seuls les niveaux du cycle 4 ({', '.join(NIVEAUX)}) "
                     "ont une structure de 2025 à archiver")
    if repartition.role(conn) == "classe":
        refus.append("base de l'appli de classe (rôle « classe ») : l'archivage se fait dans "
                     "l'atelier")
    codes = [r[0] for r in conn.execute("SELECT code FROM sequences_du_cycle WHERE "
                                        "cycle_code=?", (CYCLE,))]
    try:
        conv = cs.convention_codes(codes)
    except cs.CorrespondanceErreur as e:
        conv = None
        refus.append(f"cycle 4 en codes mêlés ({e})")
    if conv == "ancien":
        refus.append("cycle 4 encore en anciens codes (S…) : appliquer d'abord la migration "
                     "des codes (outils\\migrer_themes_codes_2027.py --apply)")
    return refus


def referentiels_non_figes(conn, niveau: str) -> list[tuple[str, str]]:
    """v0.60.0 (F2) — Référentiels internes du niveau qui lisent la structure
    vivante de l'atelier (ni verrouillés, ni utilisés, ni annulés : aucun
    instantané) : [(id, état)]. Après l'archivage, ils afficheraient le
    nouveau contenu (archives exclues), au fil des imports de lots."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_niveaux)")}
    if not cols:
        return []
    filtre = " AND COALESCE(source, 'interne') = 'interne'" if "source" in cols else ""
    return [(r[0], r[1]) for r in conn.execute(
        "SELECT id, etat FROM referentiel_niveaux WHERE niveau = ? AND etat IN "
        "('en_cours', 'valide')" + filtre + " ORDER BY id", (niveau,))]


def avertir_referentiels_non_figes(conn, niveau: str, rapport: Rapport) -> None:
    for rid, etat in referentiels_non_figes(conn, niveau):
        rapport.avertissements.append(
            f"référentiel {rid} « {etat} », sans instantané : il lit la structure vivante de "
            f"{niveau} et montrera le nouveau contenu après l'archivage — le valider puis le "
            "verrouiller avant (il garde alors la structure de 2025), ou l'annuler")


def archiver(conn, niveau: str, j, rapport: Rapport, codes: dict | None = None) -> dict:
    """Écritures journalisées (dans la transaction de `conn`). Retourne
    {code vivant: code d'archive} des séquences archivées."""
    codes = codes or codes_archive()
    fc4.migrer(conn)
    themes = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT code, theme_id, nom FROM sequences_du_cycle WHERE cycle_code=?", (CYCLE,))}
    # Codes vivants du niveau : séquences-niveaux et atomes (A2 a des atomes
    # reclassés par la migration, avec ou sans séquence-niveau).
    vivants = set()
    for (c,) in conn.execute("SELECT sequence_code FROM sequences_par_niveau WHERE niveau=?",
                             (niveau,)):
        vivants.add(c)
    for t in ATOMES:
        if _table(conn, t):
            for (c,) in conn.execute(f"SELECT DISTINCT sequence FROM {t} WHERE niveau=?",
                                     (niveau,)):
                vivants.add(c)
    carte = OrderedDict((c, codes[c]["archive"]) for c in codes if c in vivants)
    sans = sorted(c for c in vivants if cs.est_code_theme(c) and c not in codes)
    if sans:
        raise ArchivageErreur(f"code(s) de thème sans ancien code dans la table de "
                              f"correspondance : {', '.join(sans)}")
    for code, arch in carte.items():
        if conn.execute("SELECT 1 FROM sequences_par_niveau WHERE niveau=? AND sequence_code=?",
                        (niveau, arch)).fetchone():
            raise ArchivageErreur(f"{niveau}/{arch} existe déjà : archive de {code} impossible "
                                  "sans écraser")
        for t in ATOMES:
            if _table(conn, t) and conn.execute(f"SELECT 1 FROM {t} WHERE niveau=? AND "
                                                "sequence=? LIMIT 1", (niveau, arch)).fetchone():
                raise ArchivageErreur(f"{t} : des contenus {niveau}/{arch} existent déjà")
    for code, arch in carte.items():
        lignes = rapport.sequences.setdefault(f"{niveau}/{code} → {niveau}/{arch}", [])
        if arch not in themes:
            theme_id, nom = themes.get(code, (None, code))
            ident = f"sc_{uuid.uuid4().hex[:8]}"
            ligne = {"id": ident, "cycle_code": CYCLE, "code": arch,
                     "numero": codes[code]["numero"], "nom": (nom or code) + SUFFIXE_ARCHIVE,
                     "theme_id": theme_id}
            j.ins(conn, "sequences_du_cycle", ligne, {"id": ident})
            themes[arch] = (theme_id, ligne["nom"])
            lignes.append(f"séquence du cycle {arch} « {ligne['nom']} » (n° {ligne['numero']}) : "
                          "créée")
        sn = conn.execute("SELECT id FROM sequences_par_niveau WHERE niveau=? AND "
                          "sequence_code=?", (niveau, code)).fetchone()
        if sn is not None:
            j.maj(conn, "sequences_par_niveau", {"id": sn[0]}, {"sequence_code": arch})
            np_, no_ = conn.execute(
                "SELECT COUNT(DISTINCT p.id), COUNT(o.id) FROM sequence_parties p LEFT JOIN "
                "objectifs o ON o.partie_id = p.id WHERE p.sequence_par_niveau_id=?",
                (sn[0],)).fetchone()
            lignes.append(f"séquence-niveau : {np_} partie(s), {no_} objectif(s) (avec leurs liens)")
        else:
            lignes.append("pas de séquence-niveau (contenus seulement)")
        for t in ATOMES:
            if not _table(conn, t):
                continue
            ids = [r[0] for r in conn.execute(f"SELECT id FROM {t} WHERE niveau=? AND sequence=? "
                                              "ORDER BY id", (niveau, code))]
            for i in ids:
                j.maj(conn, t, {"id": i}, {"sequence": arch})
            if ids:
                lignes.append(f"{t} : {len(ids)}")
    # Précédences et origines visant <niveau>/<code> (contenu de 2025).
    for table in ("sequence_par_niveau_precedences", "partie_precedences"):
        if not _table(conn, table):
            continue
        n = 0
        for rid, seq in conn.execute(f"SELECT rowid, precedent_seq FROM {table} WHERE "
                                     "precedent_niveau=?", (niveau,)).fetchall():
            if seq in carte:
                j.maj(conn, table, {"rowid": rid}, {"precedent_seq": carte[seq]})
                n += 1
        if n:
            rapport.lignes.append(f"{table} : {n} précédence(s) visant {niveau}/<code> → archive")
    for table in ("objectif_exos", "partie_exos_revision_approche"):
        if not _table(conn, table):
            continue
        n = 0
        for rid, seq in conn.execute(f"SELECT rowid, origin_seq FROM {table} WHERE "
                                     "origin_niveau=?", (niveau,)).fetchall():
            if seq in carte:
                j.maj(conn, table, {"rowid": rid}, {"origin_seq": carte[seq]})
                n += 1
        if n:
            rapport.lignes.append(f"{table} : {n} origine(s) {niveau}/<code> → archive")
    resume = ", ".join(f"{c}→{a}" for c, a in carte.items())
    j.ins(conn, "archivages_structure",
          {"niveau": niveau, "fait_le": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "journal": "", "resume": resume}, {"niveau": niveau})
    rapport.lignes.append(f"marque archivages_structure posée pour {niveau} ({resume})")
    if not carte:
        rapport.infos.append(f"aucune séquence vivante en code de thème dans {niveau} : seule la "
                             "marque est posée")
    return dict(carte)


def executer(conn, niveau: str, rapport: Rapport, data_dir: Path | None, j) -> dict:
    """Archive dans la transaction de `conn` et vérifie que rien d'autre n'a
    changé (sinon ArchivageErreur : l'appelant annule)."""
    conn.row_factory = None
    fc4.migrer(conn)
    avertir_referentiels_non_figes(conn, niveau, rapport)            # v0.60.0 (F2)
    avant_e = empreinte_hors_tables_touchees(conn, data_dir)
    avant_l = lignes_touchables(conn)
    carte = archiver(conn, niveau, j, rapport)
    apres_e = empreinte_hors_tables_touchees(conn, data_dir)
    diff = [k for k in avant_e if avant_e[k] != apres_e.get(k)] + \
        [k for k in apres_e if k not in avant_e]
    if diff:
        raise ArchivageErreur("ce qui ne doit jamais être touché a changé : " + ", ".join(diff))
    ecarts = ecarts_hors_journal(avant_l, lignes_touchables(conn), conn, j.ops)
    if ecarts:
        raise ArchivageErreur("lignes modifiées hors journal : " + ", ".join(ecarts[:20]))
    rapport.jamais.append(f"{len(avant_e)} empreintes identiques : tables hors tables "
                          "touchées (dont les instantanés referentiel_*), fichiers referentiels\\ "
                          "et referentiels_fichiers\\")
    rapport.jamais.append(f"tables touchées : seules les {len(j.ops)} lignes du journal ont "
                          "changé (autres niveaux, X02/X04/X10, référentiels intacts)")
    for k, v in avant_e.items():
        if k.startswith(("table referentiel", "fichiers")):
            rapport.jamais.append(f"{k} : {v[:16]}…")
    return carte


# ── Retour arrière ──────────────────────────────────────────────────────────

def conflits_annulation(conn, doc: dict) -> list[str]:
    """Contenus créés depuis l'archivage sous un code archivé (un lot importé
    les y a mis) : l'annulation les mêlerait à la structure de 2025."""
    niveau = doc["niveau"]
    out = []
    for code in doc.get("carte", {}):
        if conn.execute("SELECT 1 FROM sequences_par_niveau WHERE niveau=? AND sequence_code=?",
                        (niveau, code)).fetchone():
            out.append(f"{niveau}/{code} : une séquence-niveau a été créée depuis l'archivage "
                       "(lot importé ?)")
        for t in ATOMES:
            if _table(conn, t):
                n = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE niveau=? AND sequence=?",
                                 (niveau, code)).fetchone()[0]
                if n:
                    out.append(f"{t} : {n} contenu(s) {niveau}/{code} créé(s) depuis l'archivage")
    return out


def dernier_journal(db: Path, niveau: str) -> Path | None:
    d = db.parent / "sauvegardes"
    js = sorted(d.glob(f"{PREFIXE_JOURNAL}{niveau}_*.json")) if d.is_dir() else []
    js = [p for p in js if not json.loads(p.read_text(encoding="utf-8")).get("annule_le")]
    return js[-1] if js else None


def annuler(conn, doc: dict) -> list[str]:
    """Retour arrière dans la transaction de `conn` ; liste des conflits
    (vide = fait ; non vide = rien n'est fait, l'appelant annule)."""
    conflits = conflits_annulation(conn, doc)
    if conflits:
        return conflits
    return _mig().annuler_base(conn, doc["ops"])


def commande_annuler(db: Path, niveau: str, chemin: str | None, oui: bool) -> int:
    p = Path(chemin) if chemin else dernier_journal(db, niveau)
    if p is None or not p.is_file():
        print(f"Aucun journal d'archivage de {niveau} à annuler "
              f"(sauvegardes\\{PREFIXE_JOURNAL}{niveau}_*.json).")
        return 2
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("annule_le"):
        print(f"Journal déjà annulé le {doc['annule_le']} : {p}")
        return 2
    conn = sqlite3.connect(db)
    try:
        conflits = annuler(conn, doc)
        conn.rollback()
    finally:
        conn.close()
    if conflits:
        print("Retour arrière refusé, rien n'a été fait :")
        for c in conflits[:50]:
            print(f"  ! {c}")
        print("Restaurer plutôt la sauvegarde : " + str(doc.get("sauvegarde", "")))
        return 2
    if not oui:
        rep = input(f"\nAnnuler l'archivage de {niveau} ({len(doc['ops'])} écritures) ? [o/N] "
                    ).strip().lower()
        if rep not in ("o", "oui", "y", "yes"):
            print("Abandon.")
            return 1
    conn = sqlite3.connect(db)
    try:
        conflits = annuler(conn, doc)
        if conflits:
            conn.rollback()
            print("Retour arrière refusé : " + "; ".join(conflits[:5]))
            return 2
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erreur, base inchangée : {e}")
        return 3
    finally:
        conn.close()
    doc["annule_le"] = datetime.now().astimezone().isoformat(timespec="seconds")
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Archivage de {niveau} annulé : {len(doc['ops'])} écritures remises dans leur état "
          "d'avant.")
    return 0


# ── Entrée ──────────────────────────────────────────────────────────────────

def resoudre_base(db: str | None) -> Path:
    if db:
        return Path(db).resolve()
    from services.bascule import NOM_DB, dossier_par_defaut
    return dossier_par_defaut(RACINE_APPLI, "atelier") / NOM_DB


def _nom_libre(p: Path) -> Path:
    k, q = 1, p
    while q.exists():
        k += 1
        q = p.with_name(f"{p.stem}_{k}{p.suffix}")
    return q


def sauvegarder(db: Path, niveau: str) -> Path:
    d = db.parent / "sauvegardes"
    d.mkdir(parents=True, exist_ok=True)
    cible = _nom_libre(d / f"avant_archivage_{niveau}_{datetime.now():%Y-%m-%d_%H%M%S}.db")
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    dst = sqlite3.connect(cible)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return cible


def essai_a_blanc(db: Path, niveau: str):
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    mem = sqlite3.connect(":memory:")
    try:
        src.backup(mem)
    finally:
        src.close()
    rapport, j = Rapport(niveau), _mig().Journal()
    try:
        carte = executer(mem, niveau, rapport, db.parent, j)
    finally:
        mem.close()
    return rapport, carte, j


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Archivage de la structure de 2025 d'un niveau "
                                             "du cycle 4 (v0.59.0)")
    ap.add_argument("--niveau", required=True, help="N11 (4e), plus tard N10, N12")
    ap.add_argument("--apply", action="store_true", help="applique (sinon essai à blanc)")
    ap.add_argument("--annuler", nargs="?", const="", default=None, metavar="JOURNAL",
                    help="retour arrière (dernier journal du niveau par défaut)")
    ap.add_argument("--yes", action="store_true", help="sans confirmation")
    ap.add_argument("--db", help="chemin de la base (défaut : base du profil atelier)")
    args = ap.parse_args(argv)
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except Exception:
            pass
    niveau = args.niveau.strip().upper()
    db = resoudre_base(args.db)
    if not db.is_file():
        print(f"Base introuvable : {db}")
        return 2
    print(f"Base : {db}")
    if args.annuler is not None:
        return commande_annuler(db, niveau, args.annuler or None, args.yes)
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        refus = precontroles(c, niveau)
        deja = None if refus else _archivage_ro(c, niveau)
    finally:
        c.close()
    if refus:
        print("\nArchivage refusé :")
        for r in refus:
            print(f"  ! {r}")
        return 2
    if deja:
        print(f"\nStructure de 2025 de {niveau} déjà archivée le {deja['fait_le']} "
              f"({deja['resume'] or 'aucune séquence'}) : rien à faire.")
        return 0
    try:
        rapport, carte, j = essai_a_blanc(db, niveau)
    except ArchivageErreur as e:
        print(f"\nArchivage refusé : {e}")
        return 2
    print(rapport.texte())
    if not args.apply:
        print("\n(essai à blanc : rien n'a été écrit — relancer avec --apply pour appliquer)")
        return 0
    if not args.yes:
        rep = input(f"\nArchiver la structure de 2025 de {niveau} ? [o/N] ").strip().lower()
        if rep not in ("o", "oui", "y", "yes"):
            print("Annulé.")
            return 1
    sauvegarde = sauvegarder(db, niveau)
    print(f"\nSauvegarde : {sauvegarde}")
    journal = _nom_libre(db.parent / "sauvegardes" /
                         f"{PREFIXE_JOURNAL}{niveau}_{datetime.now():%Y-%m-%d_%H%M%S}.json")
    conn = sqlite3.connect(db)
    rapport, j = Rapport(niveau), _mig().Journal()
    try:
        carte = executer(conn, niveau, rapport, db.parent, j)
        conn.execute("UPDATE archivages_structure SET journal=? WHERE niveau=?",
                     (journal.name, niveau))
        for op in j.ops:                         # la marque garde le nom du journal
            if op["table"] == "archivages_structure":
                op["ligne"]["journal"] = journal.name
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"\nErreur, rien n'a été écrit dans la base : {e}")
        return 3
    finally:
        conn.close()
    journal.write_text(json.dumps({"outil": f"archiver_structure_niveau {VERSION}",
                                   "base": str(db), "niveau": niveau,
                                   "sauvegarde": str(sauvegarde), "carte": carte,
                                   "ops": j.ops}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    journal.with_suffix(".txt").write_text(rapport.texte(), encoding="utf-8")
    print(f"Journal (retour arrière : --annuler) : {journal}")
    print(f"\nArchivage appliqué. Suite : importer les lots de {niveau} "
          f"(..\\outils\\python\\python.exe .\\outils\\import_lot6e.py --niveau {niveau}).")
    return 0


def _archivage_ro(conn, niveau: str) -> dict | None:
    try:
        return fc4.archivage(conn, niveau)
    except sqlite3.Error:
        return None


if __name__ == "__main__":
    sys.exit(main())
