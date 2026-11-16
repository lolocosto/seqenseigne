#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""outils/migrer_themes_codes_2027.py — v0.58.0

Migration des thèmes et des codes de séquences (rentrée 2027, cycles 3 et 4),
livraison 2 du plan de migration (`doc/redemarrage_v0_58_0.md`). La table de
correspondance est `outils/correspondance_codes_2027.json` (v0.57.0) ; le
reclassement des séquences retirées du cycle 4 est
`outils/reclassement_2027.json`.

Ce que fait l'outil, sur la base de l'atelier :

  1. **Cycle 3** — thèmes permutés (B → F, C → B, D → C, E → D, F → E ; noms
     et couleurs inchangés, ordre et descriptions réécrits) ; S01…S13 →
     A1…E1 (numéros 11…51) ; M01…M07 gardent leur code (leur thème suit) ;
     X01…X16 et XA…XC ne bougent pas.
  2. **Cycle 4** — thèmes A (renommé), D → B, B → C (renommé), D
     « Proportionnalité, fonctions » créé, E (renommé), C → F ; S03 → A1,
     A2 « Nombres rationnels et arithmétique » créée, S01 → A3 … S14 → E1 ;
     S02, S04, S10 → X02, X04, X10 (102, 104, 110, « (archive) »), puis
     reclassement de leurs contenus d'atelier (`reclassement_2027.json`).
  3. **Tables vivantes** recodées (niveaux du cycle) : séquences-niveaux,
     précédences (y compris de 5e vers la 6e), notions, méthodes,
     exercices, fiches, cartes d'automatisme, cartes mentales, `origin_seq`
     des liens d'exercices ; colonne `fichier` des atomes du cycle 4
     (`N10S03F01.tex` → `N10A1F01.tex`). Les identifiants ne changent pas.
     Les champs de contenu (énoncés, variables xint `N10S03A01_…`, noms
     d'images) ne sont jamais réécrits.
  4. **Fichiers LaTeX du cycle 4** (arborescences N10\, N11\, N12\ trouvées
     d'après `configuration.json` et `..\reference\sequences`, ou `--latex`) :
     renommage des `.tex` (et `Objectifs.csv`), des dossiers `Snn`,
     réécriture de `\seqSetCodeSequence{…}` et des `\input{…}` qui visent
     un fichier renommé. Les images ne sont jamais renommées.

Ce qui n'est jamais touché (vérifié par empreinte avant validation : toute
différence annule la transaction) : toutes les tables autres que les tables
vivantes ci-dessus (instantanés `referentiel_*`, référentiels externes,
publications, retours d'usage, évaluations, tout ce qui est côté classe…),
les archives X01…X16 du cycle 3 et leurs contenus, les fichiers de
`referentiels\` (`_verrouille\`, `_publication\`) et de
`referentiels_fichiers\`. Une base de rôle `classe` est refusée.

Modes :
  essai à blanc (défaut) : tout est exécuté sur une copie en mémoire, le
      rapport est exactement celui de --apply, rien n'est écrit ;
  --apply : sauvegarde .db automatique (`sauvegardes\`), une transaction par
      cycle, puis fichiers LaTeX ; journal `sauvegardes\journal_migration_
      2027_<date>.json` (et rapport `.txt`) ;
  --annuler [JOURNAL] : retour arrière d'après le journal (le dernier par
      défaut) ; refusé si une donnée migrée a été modifiée depuis.

Idempotence : un cycle déjà en codes de thème est sauté (« rien à faire ») ;
une base qui mêle anciens codes et codes de thème est refusée.
v0.58.2 (Q1) : même sur un cycle déjà migré, crée (journalisée) la
séquence-niveau des séquences en code de thème qui ont des contenus dans un
niveau sans y en avoir (A2 en N10, N11, N12 après le reclassement).

Usage (Windows, depuis `appli\`) :
    ..\outils\python\python.exe .\outils\migrer_themes_codes_2027.py
    ..\outils\python\python.exe .\outils\migrer_themes_codes_2027.py --apply
    ..\outils\python\python.exe .\outils\migrer_themes_codes_2027.py --annuler
Options : --db CHEMIN, --cycle C03|C04, --latex DOSSIER (répétable),
--sans-fichiers, --sans-publication, --yes.

Codes de sortie : 0 succès / essai / rien à faire, 1 annulé par
l'utilisateur, 2 refus (base, rôle, prérequis, conflit), 3 erreur (rien
n'est écrit : transaction annulée, fichiers remis en place).
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

from services import codes_sequence as cs     # noqa: E402

VERSION = "0.58.2"
CORRESPONDANCE = Path(__file__).resolve().parent / "correspondance_codes_2027.json"
RECLASSEMENT = Path(__file__).resolve().parent / "reclassement_2027.json"
NIVEAUX = OrderedDict([("C03", ("N07", "N08", "N09")), ("C04", ("N10", "N11", "N12"))])
SUFFIXE_ARCHIVE = " (archive)"
PREFIXE_JOURNAL = "journal_migration_2027_"

# Tables que la migration modifie (lignes des niveaux du cycle seulement).
# Toute autre table est vérifiée identique, octet pour octet, avant validation.
TABLES_VIVANTES = ("themes", "sequences_du_cycle", "sequences_par_niveau",
                   "sequence_par_niveau_precedences", "partie_precedences",
                   "notions", "methodes", "exercices", "fiches_resume",
                   "cartes_automatisme", "cartes_mentales", "objectif_exos",
                   "partie_exos_revision_approche", "atome_sections",
                   "atome_section_items")
ATOMES = ("notions", "methodes", "exercices", "fiches_resume", "cartes_automatisme",
          "cartes_mentales")
TABLES_FICHIER = ("notions", "methodes", "exercices")

# Descriptions des thèmes (préambules des programmes : cycle 3, 2025 ; cycle 4,
# annexe 2 de l'arrêté du 18 février 2026). F au cycle 4 garde la sienne.
DESCRIPTIONS = {
    "C03": {
        "A": r"Selon le programme, \og au cycle 3, l'objectif est de poursuivre la compréhension de notre système de numération et de mobiliser ses propriétés lors de calculs. L’apprentissage des techniques opératoires et la compréhension des nombres se développent alors conjointement. Les problèmes arithmétiques proposés au cycle 3 permettent d’enrichir le sens des opérations déjà abordées au cycle 2 et d’en étudier de nouvelles. \fg{}",
        "B": r"Selon le programme, \og dans la continuité des apprentissages du cycle 2, l’acquisition des connaissances sur les figures de référence et sur les relations géométriques se poursuit lors de descriptions, de constructions et de résolutions de problèmes. \fg{} Le travail sur les mesures d’angle est intégré au champ de la géométrie.",
        "C": r"Selon le programme, \og les élèves résolvent des problèmes dont les données peuvent être prélevées dans des tableaux, dans des diagrammes en barres ou sur des courbes. \fg{} Ils abordent aussi les probabilités.",
        "D": r"Selon le programme, \og la notion de proportionnalité entre deux grandeurs est explicitement introduite dans le cadre de la résolution de problèmes : les élèves apprennent à identifier des situations relevant de la proportionnalité et à mettre en œuvre dans ce cadre des raisonnements fondés sur la propriété de la linéarité. \fg{}",
        "E": r"Selon le programme, \og le mode de pensée informatique est une approche universelle permettant de résoudre des problèmes complexes en exploitant des processus de calcul, qu’ils soient réalisés par des humains ou par des machines. \fg{} C'est un domaine spécifique en 6e.",
        "F": r"Selon le programme, \og le travail sur les grandeurs et les mesures est mené dans la continuité de ce qui a été fait au cycle 2. Les longueurs, les masses et les contenances permettent de nourrir le travail mené sur les fractions et les nombres décimaux. \fg{}",
    },
    "C04": {
        "A": r"Selon le programme, \og au cycle 4, la partie nombres et calculs du programme s’enrichit de nombreuses nouvelles notions. Les élèves découvrent ainsi de nouvelles catégories de nombres avec lesquels ils réalisent des calculs et qu’ils mobilisent pour résoudre des problèmes. \fg{}",
        "B": r"Selon le programme, \og l’enseignement de la Géométrie au cycle 4 a pour objectif majeur d’amener les élèves à mener des raisonnements et à s’initier à la preuve. Cette transition vers une géométrie du raisonnement, entamée en 6e, se fait progressivement, en s’appuyant sur la géométrie perceptive et sur la géométrie instrumentée étudiées précédemment. \fg{}",
        "C": r"Selon le programme, \og au cycle 4, les élèves sont confrontés à diverses situations de travail sur des données : les utiliser, les représenter, les interpréter. Ils sont amenés à analyser et à comparer, en particulier pour dégager des informations pertinentes. \fg{} Ils abordent aussi les probabilités.",
        "D": r"Selon le programme, \og cette partie du programme regroupe les notions de proportionnalité et de fonction pour répondre à un double objectif : introduire progressivement la notion de fonction, pour décrire une dépendance entre deux grandeurs, dont la proportionnalité est un cas particulier ; affermir la maitrise des raisonnements liés à la proportionnalité. \fg{}",
        "E": r"Selon le programme, \og la pensée informatique est présentée sous l’angle de l’algorithmique. Les concepts sous-jacents de la programmation impérative par blocs sont présentés de manière progressive tout au long du cycle. \fg{}",
    },
}


class MigrationErreur(Exception):
    """Refus (prérequis, conflit) : rien n'est écrit."""


# ── Utilitaires ──────────────────────────────────────────────────────────────

def _table(conn, nom: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (nom,)).fetchone() is not None


def _cols(conn, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def _sha_fichier(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def charger_json(chemin: Path) -> dict:
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


def _nom_libre(p: Path) -> Path:
    k, q = 1, p
    while q.exists():
        k += 1
        q = p.with_name(f"{p.stem}_{k}{p.suffix}")
    return q


class Journal:
    """Chaque écriture élémentaire en base est notée (valeurs avant / après) :
    --annuler les rejoue à l'envers, en vérifiant que rien n'a changé depuis."""

    def __init__(self):
        self.ops: list[dict] = []
        self.fichiers: list[dict] = []

    def maj(self, conn, table: str, cle: dict, valeurs: dict) -> bool:
        cols = list(valeurs)
        where = " AND ".join(f'"{k}"=?' for k in cle)
        r = conn.execute(f'SELECT {", ".join(chr(34) + c + chr(34) for c in cols)} FROM "{table}" '
                         f'WHERE {where}', tuple(cle.values())).fetchone()
        if r is None:
            raise MigrationErreur(f"{table} {cle} introuvable")
        avant = dict(zip(cols, r))
        apres = {c: valeurs[c] for c in cols}
        if avant == apres:
            return False
        conn.execute(f'UPDATE "{table}" SET {", ".join(chr(34) + c + chr(34) + "=?" for c in cols)} '
                     f'WHERE {where}', (*apres.values(), *cle.values()))
        self.ops.append({"op": "maj", "table": table, "cle": cle, "avant": avant, "apres": apres})
        return True

    def ins(self, conn, table: str, ligne: dict, cle: dict) -> None:
        conn.execute(f'INSERT INTO "{table}" ({", ".join(chr(34) + c + chr(34) for c in ligne)}) '
                     f'VALUES ({", ".join("?" * len(ligne))})', tuple(ligne.values()))
        self.ops.append({"op": "ins", "table": table, "cle": cle, "ligne": ligne})


class Rapport:
    def __init__(self):
        self.sections: "OrderedDict[str, list[str]]" = OrderedDict()
        self.comptes: "OrderedDict[str, int]" = OrderedDict()
        self.anomalies: list[str] = []
        self.infos: list[str] = []

    def ligne(self, section: str, texte: str) -> None:
        self.sections.setdefault(section, []).append(texte)

    def compter(self, cle: str, n: int = 1) -> None:
        if n:
            self.comptes[cle] = self.comptes.get(cle, 0) + n

    def texte(self) -> str:
        out = [f"Migration des thèmes et des codes (rentrée 2027) — seqenseigne {VERSION}", ""]
        for s, lignes in self.sections.items():
            out.append(f"== {s}")
            out += [f"  {x}" for x in lignes]
            out.append("")
        if self.comptes:
            out.append("== Lignes modifiées ou créées, par table et par cycle")
            out += [f"  {k} : {v}" for k, v in self.comptes.items()]
            out.append(f"  total : {sum(self.comptes.values())}")
            out.append("")
        if self.infos:
            out.append("== Informations")
            out += [f"  - {x}" for x in self.infos]
            out.append("")
        out.append("== Anomalies" + ("" if self.anomalies else " : aucune"))
        out += [f"  ! {x}" for x in self.anomalies]
        return "\n".join(out)


# ── Empreinte de ce qui n'est jamais touché ─────────────────────────────────

def _sha_requete(conn, sql: str, params=()) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    for r in conn.execute(sql, params):
        h.update(repr(tuple(r)).encode("utf-8"))
        n += 1
    return h.hexdigest(), n


def empreinte_protegee(conn, data_dir: Path | None) -> "OrderedDict[str, str]":
    """SHA-256 de tout ce que la migration ne doit jamais modifier :
    - chaque table hors tables vivantes (contenu complet, trié) ;
    - les archives X01…X16 du cycle 3 (séquences, thèmes XA…XC, contenus) ;
    - les fichiers de `referentiels\\` et `referentiels_fichiers\\`."""
    e: "OrderedDict[str, str]" = OrderedDict()
    for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                             "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
        if t in TABLES_VIVANTES:
            continue
        cols = ", ".join(f'"{c}"' for c in _cols(conn, t))
        sha, n = _sha_requete(conn, f'SELECT {cols} FROM "{t}" ORDER BY {cols}')
        e[f"table {t} ({n} lignes)"] = sha
    sha, n = _sha_requete(conn, "SELECT * FROM sequences_du_cycle WHERE cycle_code='C03' "
                                "AND code LIKE 'X%' ORDER BY id")
    e[f"archives du cycle 3 : séquences X ({n})"] = sha
    sha, n = _sha_requete(conn, "SELECT * FROM themes WHERE cycle_code='C03' AND code LIKE 'X%' "
                                "ORDER BY id")
    e[f"archives du cycle 3 : thèmes XA… ({n})"] = sha
    for t in ATOMES:
        if _table(conn, t):
            sha, n = _sha_requete(conn, f"SELECT * FROM {t} WHERE niveau IN ('N07','N08','N09') "
                                        "AND sequence LIKE 'X%' ORDER BY id")
            e[f"archives du cycle 3 : {t} ({n})"] = sha
    if data_dir is not None:
        for sous in ("referentiels", "referentiels_fichiers"):
            d = Path(data_dir) / sous
            h = hashlib.sha256()
            n = 0
            if d.is_dir():
                for p in sorted(x for x in d.rglob("*") if x.is_file()):
                    h.update(str(p.relative_to(d)).replace("\\", "/").encode("utf-8"))
                    h.update(_sha_fichier(p).encode())
                    n += 1
            e[f"fichiers {sous}\\ ({n})"] = h.hexdigest()
    return e


# ── État et prérequis ───────────────────────────────────────────────────────

def etat_cycle(conn, cycle: str) -> str:
    """'ancien' (S…), 'nouveau' (A1…), 'vide' ; MigrationErreur si mêlés."""
    codes = [r[0] for r in conn.execute("SELECT code FROM sequences_du_cycle WHERE cycle_code=?",
                                        (cycle,))]
    try:
        conv = cs.convention_codes(codes)
    except cs.CorrespondanceErreur as e:
        raise MigrationErreur(f"cycle {cycle} : {e}") from e
    return conv or "vide"


def precontroles(conn, data_dir: Path | None, sans_publication: bool,
                 rapport: Rapport) -> list[str]:
    """Refus bloquants (liste vide = on peut migrer)."""
    from services import repartition
    refus = []
    if repartition.role(conn) == "classe":
        refus.append("base de l'appli de classe (rôle « classe ») : la migration se fait dans "
                     "l'atelier, jamais dans la base de classe")
    for cy in NIVEAUX:
        try:
            etat_cycle(conn, cy)
        except MigrationErreur as e:
            refus.append(str(e))
    # Risque 4 du plan : un référentiel interne figé jamais publié serait
    # exporté plus tard à partir des tables migrées (notions et méthodes vides).
    if _table(conn, "referentiel_niveaux"):
        from services.format_referentiel import EXPORTEURS_PERIMES, ETATS_FIGES
        manquants, perimes = [], []
        for rid, etat in conn.execute(
                "SELECT id, etat FROM referentiel_niveaux WHERE COALESCE(source,'interne')="
                "'interne' ORDER BY id").fetchall():
            if etat not in ETATS_FIGES:
                continue
            p = (Path(data_dir) / "referentiels" / rid / "_publication" / "referentiel.json"
                 if data_dir else None)
            if p is None or not p.is_file():
                manquants.append(rid)
                continue
            try:
                par = str(json.loads(p.read_text(encoding="utf-8")).get("exporte_par", ""))
            except (OSError, ValueError):
                par = "illisible"
            if par == "illisible" or par.startswith(EXPORTEURS_PERIMES):
                perimes.append(rid)
        if manquants or perimes:
            txt = []
            if manquants:
                txt.append("sans première publication (`_publication\\referentiel.json`) : "
                           + ", ".join(manquants))
            if perimes:
                txt.append("publication périmée ou illisible : " + ", ".join(perimes))
            msg = ("référentiels internes figés " + " ; ".join(txt)
                   + " — publier d'abord (Échanges › publication), sinon leur export serait "
                     "reconstruit à partir des tables migrées")
            if sans_publication:
                rapport.anomalies.append(msg + " (--sans-publication : migration autorisée)")
            else:
                refus.append(msg + " ; ou relancer avec --sans-publication")
        # Référentiels internes non figés qui auraient un instantané : non pris
        # en charge (décision M5) ; aucun dans la base d'atelier du 16 novembre.
        for rid, etat in conn.execute(
                "SELECT id, etat FROM referentiel_niveaux WHERE COALESCE(source,'interne')="
                "'interne' AND etat NOT IN ('verrouille','utilise','annule') ORDER BY id"):
            if conn.execute("SELECT 1 FROM referentiel_sequences WHERE referentiel_id=?",
                            (rid,)).fetchone():
                refus.append(f"référentiel {rid} ({etat}) : instantané présent alors qu'il n'est "
                             "pas figé — cas non pris en charge, à verrouiller ou à revoir")
    return refus


# ── Thèmes et séquences du cycle ────────────────────────────────────────────

def _themes(conn, cycle: str) -> dict:
    conn.row_factory = sqlite3.Row
    return {r["code"]: dict(r) for r in conn.execute(
        "SELECT * FROM themes WHERE cycle_code=?", (cycle,))}


def migrer_themes(conn, cycle: str, corr: dict, j: Journal, rapport: Rapport) -> dict:
    """Retourne {nouvelle lettre: id du thème}. Codes temporaires (`~`) pour
    respecter UNIQUE (cycle_code, code) pendant la permutation."""
    sec = f"Cycle {cycle[-1]} — thèmes"
    existants = _themes(conn, cycle)
    table = corr["cycles"][cycle]["themes"]
    for t in table:
        if t.get("ancien") and t["ancien"] not in existants:
            raise MigrationErreur(f"{cycle} : thème {t['ancien']} absent de la base")
    # 1. codes temporaires
    for t in table:
        if t.get("ancien") and t["ancien"] != t["nouveau"]:
            j.maj(conn, "themes", {"id": existants[t["ancien"]]["id"]},
                  {"code": "~" + t["ancien"]})
    # 2. codes, noms, ordre, descriptions définitifs
    ids = {}
    for t in table:
        desc = DESCRIPTIONS.get(cycle, {}).get(t["nouveau"])
        if t.get("ancien"):
            r = existants[t["ancien"]]
            valeurs = {"code": t["nouveau"], "nom": t["nom"], "ordre": t["ordre_nouveau"],
                       "code_couleur": t["code_couleur"]}
            if desc is not None:
                valeurs["description"] = desc
            j.maj(conn, "themes", {"id": r["id"]}, valeurs)
            ids[t["nouveau"]] = r["id"]
            quoi = (f"{t['ancien']} → {t['nouveau']}" if t["ancien"] != t["nouveau"]
                    else f"{t['nouveau']} (même lettre)")
            nom = f"« {r['nom']} » → « {t['nom']} »" if r["nom"] != t["nom"] else f"« {t['nom']} »"
            rapport.ligne(sec, f"{quoi} : {nom}, ordre {r['ordre']} → {t['ordre_nouveau']}, "
                               f"couleur {t['code_couleur']}")
        else:
            tid = "th_" + uuid.uuid4().hex[:8]
            j.ins(conn, "themes", {"id": tid, "cycle_code": cycle, "code": t["nouveau"],
                                   "nom": t["nom"], "code_couleur": t["code_couleur"],
                                   "description": desc or "", "ordre": t["ordre_nouveau"]},
                  {"id": tid})
            ids[t["nouveau"]] = tid
            rapport.ligne(sec, f"{t['nouveau']} créé : « {t['nom']} », ordre {t['ordre_nouveau']}, "
                               f"couleur {t['code_couleur']}")
    rapport.compter(f"themes ({cycle})", len(table))
    return ids


def migrer_sequences(conn, cycle: str, corr: dict, ids_themes: dict, j: Journal,
                     rapport: Rapport) -> dict:
    """Retourne la table {ancien code: nouveau code} appliquée aux tables vivantes."""
    sec = f"Cycle {cycle[-1]} — séquences du cycle"
    conn.row_factory = sqlite3.Row
    existantes = {r["code"]: dict(r) for r in conn.execute(
        "SELECT * FROM sequences_du_cycle WHERE cycle_code=?", (cycle,))}
    table = corr["cycles"][cycle]["sequences"]
    carte = {}
    # 1. codes et numéros temporaires (UNIQUE (cycle_code, code), (cycle_code, numero))
    for s in table:
        r = existantes.get(s["ancien"])
        if r is not None:
            j.maj(conn, "sequences_du_cycle", {"id": r["id"]},
                  {"code": "~" + s["ancien"], "numero": -1000 - (r["numero"] or 0)})
    # 2. valeurs définitives
    n_crees = 0
    for s in table:
        r = existantes.get(s["ancien"])
        tid = ids_themes.get(s["theme_nouveau"])
        if r is not None:
            nom = r["nom"] + SUFFIXE_ARCHIVE if s.get("archive") else (
                s["nom"] if cycle == "C04" else r["nom"])
            j.maj(conn, "sequences_du_cycle", {"id": r["id"]},
                  {"code": s["nouveau"], "numero": s["numero_nouveau"], "nom": nom,
                   "theme_id": tid})
            carte[s["ancien"]] = s["nouveau"]
            ch_theme = (f", thème {s['theme_ancien']} → {s['theme_nouveau']}"
                        if s["theme_ancien"] != s["theme_nouveau"] else
                        f", thème {s['theme_nouveau']}")
            ch_nom = f" « {r['nom']} » → « {nom} »" if nom != r["nom"] else f" « {nom} »"
            rapport.ligne(sec, f"{s['ancien']} → {s['nouveau']} (numéro {r['numero']} → "
                               f"{s['numero_nouveau']}){ch_nom}{ch_theme}")
        elif s.get("nouvelle"):
            sid = "sc_" + uuid.uuid4().hex[:8]
            j.ins(conn, "sequences_du_cycle", {"id": sid, "cycle_code": cycle,
                                               "code": s["nouveau"], "numero": s["numero_nouveau"],
                                               "nom": s["nom"], "theme_id": tid}, {"id": sid})
            n_crees += 1
            rapport.ligne(sec, f"{s['nouveau']} créée (numéro {s['numero_nouveau']}) « {s['nom']} », "
                               f"thème {s['theme_nouveau']} (ancien code provisoire {s['ancien']})")
        else:
            raise MigrationErreur(f"{cycle} : séquence {s['ancien']} absente de la base")
    for m in corr["cycles"][cycle].get("mises_en_route", []):
        r = existantes.get(m["code"])
        if r is not None and m["theme_ancien"] != m["theme_nouveau"]:
            rapport.ligne(sec, f"{m['code']} (mise en route) : code inchangé, thème "
                               f"{m['theme_ancien']} → {m['theme_nouveau']} (suit son thème)")
    rapport.compter(f"sequences_du_cycle ({cycle})", len(carte) + n_crees)
    return carte


# ── Tables vivantes ─────────────────────────────────────────────────────────

_RE_FICHIERS = (
    re.compile(r"^(N\d\d)_(S\d\d)_(Notion|Methode)_(\d+)\.tex$"),
    re.compile(r"^(N\d\d)(S\d\d)((?:AE|[FAE])\d+(?:_enonce)?\.tex)$"),
)


def nouveau_fichier(nom: str, niveau: str, carte: dict) -> str:
    """`N10S03F01.tex` → `N10A1F01.tex`, `N10_S03_Notion_01.tex` →
    `N10_A1_Notion_01.tex` (code du nom = ancien code de l'atome)."""
    if not nom:
        return nom
    m = _RE_FICHIERS[0].match(nom)
    if m and m.group(1) == niveau and m.group(2) in carte:
        return f"{m.group(1)}_{carte[m.group(2)]}_{m.group(3)}_{m.group(4)}.tex"
    m = _RE_FICHIERS[1].match(nom)
    if m and m.group(1) == niveau and m.group(2) in carte:
        return f"{m.group(1)}{carte[m.group(2)]}{m.group(3)}"
    return nom


def recoder_tables_vivantes(conn, cycle: str, carte: dict, j: Journal, rapport: Rapport) -> None:
    niveaux = NIVEAUX[cycle]
    marq_n = ",".join("?" * len(niveaux))
    marq_c = ",".join("?" * len(carte))
    anciens = tuple(carte)
    for table, col in (("sequences_par_niveau", "sequence_code"), *((t, "sequence") for t in ATOMES)):
        if not _table(conn, table):
            continue
        avec_fichier = cycle == "C04" and table in TABLES_FICHIER
        rows = conn.execute(
            f"SELECT id, niveau, {col}{', fichier' if avec_fichier else ''} FROM {table} "
            f"WHERE niveau IN ({marq_n}) AND {col} IN ({marq_c})", (*niveaux, *anciens)).fetchall()
        for r in rows:
            v = {col: carte[r[2]]}
            if avec_fichier:
                v["fichier"] = nouveau_fichier(r[3], r[1], carte)
            j.maj(conn, table, {"id": r[0]}, v)
        rapport.compter(f"{table} ({cycle})", len(rows))
    # Précédences : le code visé est recodé d'après le cycle du niveau visé
    # (une séquence de 5e qui vise N09/S01 vise désormais N09/A1).
    for table in ("sequence_par_niveau_precedences", "partie_precedences"):
        if not _table(conn, table):
            continue
        rows = conn.execute(
            f"SELECT rowid, precedent_seq FROM {table} WHERE precedent_niveau IN ({marq_n}, ?) "
            f"AND precedent_seq IN ({marq_c})", (*niveaux, cycle, *anciens)).fetchall()
        for r in rows:
            j.maj(conn, table, {"rowid": r[0]}, {"precedent_seq": carte[r[1]]})
        rapport.compter(f"{table} ({cycle})", len(rows))
    for table in ("objectif_exos", "partie_exos_revision_approche"):
        if not _table(conn, table):
            continue
        rows = conn.execute(
            f"SELECT rowid, origin_seq FROM {table} WHERE origin_niveau IN ({marq_n}) "
            f"AND origin_seq IN ({marq_c})", (*niveaux, *anciens)).fetchall()
        for r in rows:
            j.maj(conn, table, {"rowid": r[0]}, {"origin_seq": carte[r[1]]})
        rapport.compter(f"{table} ({cycle})", len(rows))


# ── Reclassement des séquences retirées (cycle 4) ───────────────────────────

def _fichier_canonique(table: str, niveau: str, code: str, num, serie: str = "") -> str:
    if table == "notions":
        return f"{niveau}_{code}_Notion_{int(num):02d}.tex"
    if table == "methodes":
        return f"{niveau}_{code}_Methode_{int(num):02d}.tex"
    if table == "exercices":
        return f"{niveau}{code}{serie}{int(num):02d}.tex"
    return ""


def _suivant(conn, table: str, colnum: str, niveau: str, seq: str, serie: str | None = None) -> int:
    sql = f"SELECT {colnum} FROM {table} WHERE niveau=? AND sequence=?"
    params = [niveau, seq]
    if serie is not None:
        sql += " AND serie_code=?"
        params.append(serie)
    nums = []
    for (v,) in conn.execute(sql, params):
        try:
            nums.append(int(v))
        except (TypeError, ValueError):
            pass
    return max(nums, default=0) + 1


_RE_EXO = re.compile(r"^(AE|[FAE])(\d+)$")


def _trouver(conn, table: str, niveau: str, seq: str, ref) -> sqlite3.Row:
    conn.row_factory = sqlite3.Row
    if table == "notions":
        r = conn.execute("SELECT * FROM notions WHERE niveau=? AND sequence=? AND "
                         "CAST(num_connaissance AS INTEGER)=?", (niveau, seq, int(ref))).fetchall()
    elif table == "methodes":
        r = conn.execute("SELECT * FROM methodes WHERE niveau=? AND sequence=? AND num_methode=?",
                         (niveau, seq, int(ref))).fetchall()
    elif table == "fiches_resume":
        r = conn.execute("SELECT * FROM fiches_resume WHERE niveau=? AND sequence=? AND num_fiche=?",
                         (niveau, seq, int(ref))).fetchall()
    elif table == "cartes_automatisme":
        r = conn.execute("SELECT * FROM cartes_automatisme WHERE niveau=? AND sequence=? AND num=?",
                         (niveau, seq, int(ref))).fetchall()
    else:
        m = _RE_EXO.match(str(ref))
        if not m:
            raise MigrationErreur(f"reclassement : exercice {ref!r} mal écrit")
        r = conn.execute("SELECT * FROM exercices WHERE niveau=? AND sequence=? AND serie_code=? "
                         "AND num=?", (niveau, seq, m.group(1), int(m.group(2)))).fetchall()
    if len(r) != 1:
        raise MigrationErreur(f"reclassement : {table} {niveau}/{seq} {ref} "
                              f"{'introuvable' if not r else 'en double'}")
    return r[0]


_LIBELLE = {"notions": "C", "methodes": "M", "fiches_resume": "FR", "cartes_automatisme": "CA"}


def _ref_lisible(table: str, ref) -> str:
    if table == "exercices":
        return str(ref)
    if table == "notions":
        return f"C{int(ref):02d}"
    return f"{_LIBELLE[table]}{ref}"


def _copier_sections(conn, j: Journal, entite_type: str, ancien_id: str, nouvel_id: str) -> int:
    if not _table(conn, "atome_sections"):
        return 0
    conn.row_factory = sqlite3.Row
    n = 0
    for s in conn.execute("SELECT * FROM atome_sections WHERE entite_type=? AND entite_id=? "
                          "ORDER BY ordre", (entite_type, ancien_id)).fetchall():
        sid = "sec_" + uuid.uuid4().hex[:12]
        ligne = {**dict(s), "id": sid, "entite_id": nouvel_id}
        j.ins(conn, "atome_sections", ligne, {"id": sid})
        n += 1
        for it in conn.execute("SELECT * FROM atome_section_items WHERE section_id=? ORDER BY ordre",
                               (s["id"],)).fetchall():
            iid = "itm_" + uuid.uuid4().hex[:12]
            j.ins(conn, "atome_section_items", {**dict(it), "id": iid, "section_id": sid},
                  {"id": iid})
    return n


def reclasser(conn, carte: dict, recl: dict, j: Journal, rapport: Rapport,
              etat_avant: dict) -> list[dict]:
    """Déplace (ou copie) les contenus repris des séquences d'archive vers leur
    séquence d'arrivée. Retourne les mouvements de fichiers .tex (pour l'étape
    des fichiers) : {niveau, ancien, nouveau, copie}."""
    sec = "Cycle 4 — reclassement de S02, S04, S10"
    mouvements = []
    maintenant = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for cle, d in recl["sequences"].items():
        niv, ancien = cle.split("/")
        arch = d["archive"]
        if carte.get(ancien) != arch:
            raise MigrationErreur(f"reclassement : {ancien} devrait devenir {arch}")
        n_dep, n_cop = 0, 0
        deplaces: dict = {}      # (table, ref) → id : une copie retrouve l'original parti
        for dest in d["destinations"]:
            vniv, vcode = dest["vers"].split("/")
            copie = bool(dest.get("copie"))
            faits = []
            for table, cle_liste in (("notions", "notions"), ("methodes", "methodes"),
                                     ("fiches_resume", "fiches"), ("cartes_automatisme", "cartes"),
                                     ("exercices", "exercices")):
                for ref in dest.get(cle_liste, []):
                    if copie and (table, str(ref)) in deplaces:
                        conn.row_factory = sqlite3.Row
                        r = conn.execute(f"SELECT * FROM {table} WHERE id=?",
                                         (deplaces[(table, str(ref))],)).fetchone()
                    else:
                        r = _trouver(conn, table, niv, arch, ref)
                        deplaces[(table, str(ref))] = r["id"]
                    faits.append(_ref_lisible(table, ref))
                    serie = r["serie_code"] if table == "exercices" else None
                    colnum = {"notions": "num_connaissance", "methodes": "num_methode",
                              "fiches_resume": "num_fiche", "cartes_automatisme": "num",
                              "exercices": "num"}[table]
                    num = _suivant(conn, table, colnum, vniv, vcode, serie)
                    v = {"niveau": vniv, "sequence": vcode,
                         colnum: f"{num:02d}" if table == "notions" else num}
                    if table in TABLES_FICHIER:
                        v["fichier"] = _fichier_canonique(table, vniv, vcode, num, serie or "")
                    if table == "cartes_automatisme":
                        v["ordre"] = (conn.execute(
                            "SELECT COALESCE(MAX(ordre),0) FROM cartes_automatisme WHERE niveau=? "
                            "AND sequence=?", (vniv, vcode)).fetchone()[0] or 0) + 1
                    ancien_fichier = etat_avant.get((table, r["id"]))
                    if copie:
                        nid = {"notions": "no_", "methodes": "me_", "exercices": "ex_",
                               "cartes_automatisme": "crt_"}.get(table, "") + uuid.uuid4().hex[:
                               12 if table == "cartes_automatisme" else 8]
                        if table == "fiches_resume":
                            nid = uuid.uuid4().hex
                        ligne = {**dict(r), **v, "id": nid}
                        if "mtime" in ligne:
                            ligne["mtime"] = maintenant
                        if table == "fiches_resume":
                            ligne["objectif_id"] = None
                        j.ins(conn, table, ligne, {"id": nid})
                        et = {"notions": "notion", "methodes": "methode",
                              "fiches_resume": "fiche_resume"}.get(table)
                        if et:
                            _copier_sections(conn, j, et, r["id"], nid)
                        n_cop += 1
                        rapport.compter(f"{table} (C04, copies)")
                        if ancien_fichier and table in TABLES_FICHIER:
                            mouvements.append({"niveau": niv, "ancien": ancien_fichier,
                                               "nouveau": v["fichier"], "copie": True,
                                               "niveau_cible": vniv})
                    else:
                        j.maj(conn, table, {"id": r["id"]}, v)
                        n_dep += 1
                        rapport.compter(f"{table} (C04, reclassement)")
                        if ancien_fichier and table in TABLES_FICHIER:
                            mouvements.append({"niveau": niv, "ancien": ancien_fichier,
                                               "nouveau": v["fichier"], "copie": False,
                                               "niveau_cible": vniv, "id": r["id"],
                                               "table": table})
                        if table == "exercices":
                            for t2 in ("partie_exos_revision_approche", "objectif_exos"):
                                if not _table(conn, t2):
                                    continue
                                for x in conn.execute(
                                        f"SELECT rowid FROM {t2} WHERE exercice_id=? AND "
                                        "origin_niveau=? AND origin_seq=? AND origin_num=?",
                                        (r["id"], niv, arch, r["num"])).fetchall():
                                    j.maj(conn, t2, {"rowid": x[0]},
                                          {"origin_niveau": vniv, "origin_seq": vcode,
                                           "origin_num": num})
                                    rapport.compter(f"{t2} (C04, reclassement)")
            if faits:
                rapport.ligne(sec, f"{niv}/{ancien} → {vniv}/{vcode}{' (copie)' if copie else ''} "
                                   f"[{dest.get('objectif_vise', '')}] : {', '.join(faits)}")
        reste = {t: conn.execute(f"SELECT COUNT(*) FROM {t} WHERE niveau=? AND sequence=?",
                                 (niv, arch)).fetchone()[0]
                 for t in ("notions", "methodes", "fiches_resume", "cartes_automatisme", "exercices")}
        rapport.ligne(sec, f"{niv}/{arch} (archive) garde : notions {reste['notions']}, méthodes "
                           f"{reste['methodes']}, fiches {reste['fiches_resume']}, cartes "
                           f"{reste['cartes_automatisme']}, exercices {reste['exercices']} — "
                           f"{n_dep} déplacé(s), {n_cop} copié(s)")
    # Évaluations dont un exercice change de niveau ou de séquence : signalées.
    deplaces = {m["id"] for m in mouvements if not m["copie"] and m.get("table") == "exercices"}
    if deplaces and _table(conn, "evaluation_exercices"):
        marq = ",".join("?" * len(deplaces))
        for titre, niveau, n in conn.execute(
                f"SELECT e.titre, e.niveau, COUNT(*) FROM evaluation_exercices ee JOIN evaluations e "
                f"ON e.id=ee.evaluation_id WHERE ee.exercice_id IN ({marq}) GROUP BY e.id "
                "ORDER BY e.niveau, e.titre", tuple(deplaces)):
            rapport.infos.append(f"évaluation {niveau} « {titre} » : {n} exercice(s) reclassé(s) "
                                 "(lien gardé, identifiants inchangés)")
    return mouvements


# ── Migration d'un cycle ────────────────────────────────────────────────────

def migrer_cycle(conn, cycle: str, corr: dict, recl: dict, j: Journal,
                 rapport: Rapport) -> tuple[dict, list[dict]]:
    """Retourne (table ancien → nouveau, mouvements de fichiers du reclassement)."""
    etat = etat_cycle(conn, cycle)
    if etat == "nouveau":
        rapport.ligne(f"Cycle {cycle[-1]}", "déjà en codes de thème : rien à faire")
        _signaler_restes(conn, cycle, corr, rapport)
        creer_sequences_niveau_manquantes(conn, cycle, j, rapport)
        return {}, []
    if etat == "vide":
        rapport.ligne(f"Cycle {cycle[-1]}", "aucune séquence du cycle dans la base : rien à faire")
        return {}, []
    etat_avant = {}
    if cycle == "C04":
        for t in TABLES_FICHIER:
            for i, f in conn.execute(f"SELECT id, fichier FROM {t} WHERE niveau IN "
                                     "('N10','N11','N12')"):
                etat_avant[(t, i)] = f
    ids = migrer_themes(conn, cycle, corr, j, rapport)
    carte = migrer_sequences(conn, cycle, corr, ids, j, rapport)
    recoder_tables_vivantes(conn, cycle, carte, j, rapport)
    mouvements = reclasser(conn, carte, recl, j, rapport, etat_avant) if cycle == "C04" else []
    creer_sequences_niveau_manquantes(conn, cycle, j, rapport)
    return carte, mouvements


def creer_sequences_niveau_manquantes(conn, cycle: str, j: Journal, rapport: Rapport) -> int:
    """v0.58.2 (Q1) — Séquence-niveau des séquences en code de thème qui ont des
    contenus dans un niveau sans y avoir de séquence-niveau.

    Le reclassement range des contenus en A2 (« Nombres rationnels et
    arithmétique ») dans N10, N11 et N12 ; la v0.58.0 ne créait pas la
    séquence-niveau A2 (M6) et l'atelier n'a aucun moyen de la créer : les
    atomes restaient visibles dans leurs ateliers mais l'atelier Séquence
    répondait « introuvable » (pas de parties, d'objectifs, de liens). Création
    en état « en cours », sans partie ni objectif, journalisée (--annuler la
    retire tant qu'aucune partie n'y a été créée). Idempotent ; s'applique aussi
    à une base déjà migrée (le cycle est alors « rien à faire »). Archives
    (X…), mises en route (M…) et anciens codes : jamais."""
    from services.codes_sequence import est_code_theme
    if not _table(conn, "sequences_par_niveau"):
        return 0
    niveaux = NIVEAUX[cycle]
    du_cycle = {c for (c,) in conn.execute(
        "SELECT code FROM sequences_du_cycle WHERE cycle_code=?", (cycle,))}
    existantes = {(n, c) for n, c in conn.execute(
        "SELECT niveau, sequence_code FROM sequences_par_niveau")}
    contenus: dict = {}
    for t in ATOMES:
        if not _table(conn, t):
            continue
        for niv, seq, n in conn.execute(
                f"SELECT niveau, sequence, COUNT(*) FROM {t} WHERE niveau IN "
                f"({','.join('?' * len(niveaux))}) GROUP BY niveau, sequence", niveaux):
            if est_code_theme(seq) and seq in du_cycle and (niv, seq) not in existantes:
                contenus.setdefault((niv, seq), []).append(f"{t} {n}")
    for (niv, seq) in sorted(contenus):
        ident = f"sn_{uuid.uuid4().hex[:8]}"
        j.ins(conn, "sequences_par_niveau",
              {"id": ident, "niveau": niv, "sequence_code": seq, "parametres": "",
               "etat_code": "en_cours"}, {"id": ident})
        rapport.ligne(f"Cycle {cycle[-1]} — séquences-niveaux créées",
                      f"{niv}/{seq} (en cours, sans partie ni objectif) : contenus "
                      + ", ".join(contenus[(niv, seq)]))
        rapport.compter(f"sequences_par_niveau ({cycle}, créées)")
    return len(contenus)


def _signaler_restes(conn, cycle: str, corr: dict, rapport: Rapport) -> None:
    anciens = [s["ancien"] for s in corr["cycles"][cycle]["sequences"]]
    niveaux = NIVEAUX[cycle]
    for table, col in (("sequences_par_niveau", "sequence_code"), *((t, "sequence") for t in ATOMES)):
        if not _table(conn, table):
            continue
        n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE niveau IN ({','.join('?' * len(niveaux))}) "
                         f"AND {col} IN ({','.join('?' * len(anciens))})",
                         (*niveaux, *anciens)).fetchone()[0]
        if n:
            rapport.anomalies.append(f"{table} : {n} ligne(s) du cycle {cycle[-1]} encore en ancien "
                                     "code alors que le cycle est migré — à revoir dans l'atelier")


# ── Fichiers LaTeX ──────────────────────────────────────────────────────────

_RE_GENERIQUES = (
    re.compile(r"^(N1[012])_(S\d\d)_(Notion|Methode)_(\d+\.tex)$"),
    re.compile(r"^(N1[012])(S\d\d)((?:AE|[FAE])\d+(?:_enonce)?\.tex)$"),
    re.compile(r"^(N1[012])(S\d\d)(_param\.tex)$"),
    re.compile(r"^(N1[012])_(S\d\d)(_Livret\.tex)$"),
    re.compile(r"^(N1[012])(S\d\d)(Objectifs\.csv)$"),
)
_RE_INPUT = re.compile(r"(\\(?:input|include|InputIfFileExists)\s*\{)([^{}]*)(\})")
_RE_SETCODE = re.compile(r"(\\seqSetCodeSequence\s*\{)\s*([A-Z]\d{1,2})\s*(\})")
_RE_CODE_NOM = re.compile(r"^N1[012]_?([A-FX]\d{1,2})(?=[_A-Z]|$)")


def renommage_generique(nom: str, cartes: dict) -> str:
    """Nom d'un fichier du cycle 4 d'après la table de son niveau (sans base)."""
    for i, rx in enumerate(_RE_GENERIQUES):
        m = rx.match(nom)
        if m and m.group(2) in cartes.get(m.group(1), {}):
            n = cartes[m.group(1)][m.group(2)]
            if i == 0:
                return f"{m.group(1)}_{n}_{m.group(3)}_{m.group(4)}"
            if i == 3:
                return f"{m.group(1)}_{n}{m.group(3)}"
            return f"{m.group(1)}{n}{m.group(3)}"
    return nom


def racines_latex(db: Path, explicites: list[str] | None) -> list[Path]:
    """Dossiers qui contiennent N10\\, N11\\ ou N12\\ : ceux de --latex, sinon
    `chemin_reference_sequences` et `chemin_sources_livrets` de la
    configuration (data\\configuration.json), `..\\reference\\sequences` et
    `..\\sequences` à côté d'`appli\\`."""
    if explicites:
        return [Path(x).resolve() for x in explicites]
    cands = []
    try:
        from services.configuration import Configuration
        conf = Configuration(db.parent)
        for cle in ("chemin_reference_sequences", "chemin_sources_livrets"):
            v = conf._resoudre_chemin(cle)
            if v:
                cands.append(Path(v))
    except Exception:
        pass
    cands += [RACINE_APPLI.parent / "reference" / "sequences", RACINE_APPLI.parent / "sequences"]
    vus, res = set(), []
    for c in cands:
        try:
            if not c.is_dir() or not any((c / n).is_dir() for n in ("N10", "N11", "N12")):
                continue
            k = c.resolve()
        except OSError:
            continue
        if k not in vus:
            vus.add(k)
            res.append(k)
    return res


def plan_fichiers(racines: list[Path], cartes: dict, j: Journal, mouvements: list[dict],
                  rapport: Rapport) -> dict:
    """Prépare (sans rien écrire) les renommages, copies et réécritures."""
    # Noms exacts : les atomes recodés (journal) dont le fichier ne porte que
    # cet atome ; un fichier partagé prend le nom générique (archive).
    portes: dict = {}
    for op in j.ops:
        if op["op"] == "maj" and op["table"] in TABLES_FICHIER and "fichier" in op["avant"]:
            portes.setdefault(op["avant"]["fichier"], set()).add(op["cle"]["id"])
    exacts: dict = {}
    niveau_cible: dict = {}
    for m in mouvements:
        if m["copie"]:
            continue
        exacts[m["ancien"]] = m["nouveau"]
        if m["niveau_cible"] != m["niveau"]:
            niveau_cible[m["ancien"]] = (m["niveau"], m["niveau_cible"])
    partages = set()
    for m in mouvements:
        if not m["copie"] and m["ancien"] in exacts:
            # Un fichier qui portait plusieurs atomes ne suit aucun d'eux.
            n = sum(1 for x in mouvements if not x["copie"] and x["ancien"] == m["ancien"])
            if n > 1 or len(portes.get(m["ancien"], ())) > 1:
                partages.add(m["ancien"])
    for p in partages:
        exacts.pop(p, None)

    def cible(nom: str) -> str:
        if nom in exacts:
            return exacts[nom]
        if nom.endswith("_enonce.tex") and nom.replace("_enonce.tex", ".tex") in exacts:
            return exacts[nom.replace("_enonce.tex", ".tex")].replace(".tex", "_enonce.tex")
        return renommage_generique(nom, cartes)

    plan = {"racines": [str(r) for r in racines], "renommages": [], "copies": [],
            "dossiers": [], "reecritures": [], "conflits": []}
    noms = {}
    for rac in racines:
        for niv in ("N10", "N11", "N12"):
            base = rac / niv
            if not base.is_dir():
                continue
            for p in sorted(base.rglob("*")):
                if p.is_file() and p.suffix.lower() in (".tex", ".csv"):
                    n = cible(p.name)
                    if n != p.name:
                        noms[p.name] = n
                        dst = p.with_name(n)
                        cle_nc = p.name.replace("_enonce.tex", ".tex")
                        if cle_nc in niveau_cible and cle_nc in exacts:
                            # contenu reclassé à un autre niveau : le fichier va
                            # dans le dossier du niveau d'arrivée (même sous-dossier)
                            de, vers = niveau_cible[cle_nc]
                            dst = rac / vers / p.parent.relative_to(rac / de) / n
                        plan["renommages"].append((p, dst))
            for d in sorted((x for x in base.rglob("*") if x.is_dir()), key=lambda x: -len(x.parts)):
                if d.name in cartes.get(niv, {}):
                    plan["dossiers"].append((d, d.with_name(cartes[niv][d.name])))
        for m in mouvements:
            if not m["copie"]:
                continue
            for p in (rac / m["niveau"]).rglob(m["ancien"]) if (rac / m["niveau"]).is_dir() else []:
                # la copie va au même endroit relatif, dans le dossier du niveau d'arrivée
                rel = p.relative_to(rac / m["niveau"])
                dst = rac / m["niveau_cible"] / rel.parent / m["nouveau"]
                plan["copies"].append((p, dst))
    # Réécritures (après renommage) : \seqSetCodeSequence et \input visés.
    def code_de(nom: str) -> str | None:
        m = _RE_CODE_NOM.match(nom)
        return m.group(1) if m else None

    renommes = {src: dst for src, dst in plan["renommages"]}
    for rac in racines:
        for niv in ("N10", "N11", "N12"):
            base = rac / niv
            if not base.is_dir():
                continue
            for p in sorted(base.rglob("*.tex")):
                final = renommes.get(p, p)
                texte, enc = _lire_tex(p)
                nv = _reecrire(texte, final.name, noms, cartes.get(niv, {}), code_de)
                if nv != texte:
                    plan["reecritures"].append((p, final, nv, enc))
    for src, dst in plan["copies"]:
        texte, enc = _lire_tex(src)
        plan["reecritures_copies"] = plan.get("reecritures_copies", []) + [
            (dst, _reecrire(texte, dst.name, noms, {}, code_de), enc)]
    # Conflits : une cible qui existe déjà et qui n'est pas elle-même renommée.
    sources = {src for src, _ in plan["renommages"]}
    for src, dst in plan["renommages"] + plan["copies"]:
        if dst.exists() and dst not in sources:
            plan["conflits"].append(f"{dst} existe déjà (renommage de {src.name})")
    cibles = [dst for _, dst in plan["renommages"] + plan["copies"]]
    for c in {c for c in cibles if cibles.count(c) > 1}:
        plan["conflits"].append(f"{c} : plusieurs fichiers recevraient ce nom")
    sec = "Fichiers LaTeX du cycle 4"
    if not racines:
        rapport.ligne(sec, "aucune arborescence N10\\, N11\\, N12\\ trouvée (configuration, "
                           "..\\reference\\sequences, ..\\sequences) : seule la colonne « fichier » "
                           "des atomes est recodée en base — indiquer le dossier avec --latex")
    for r in racines:
        rapport.ligne(sec, f"arborescence : {r}")
    rapport.ligne(sec, f"{len(plan['renommages'])} fichier(s) renommé(s), {len(plan['copies'])} "
                       f"copié(s), {len(plan['dossiers'])} dossier(s) renommé(s), "
                       f"{len(plan['reecritures'])} fichier(s) réécrit(s) "
                       "(\\seqSetCodeSequence, \\input)")
    for src, dst in plan["renommages"]:
        rapport.ligne(sec, f"  {src.relative_to(_racine_de(src, racines))} → {dst.name}")
    for src, dst in plan["copies"]:
        rapport.ligne(sec, f"  copie {src.name} → {dst.relative_to(_racine_de(dst, racines))}")
    for src, dst in plan["dossiers"]:
        rapport.ligne(sec, f"  dossier {src.relative_to(_racine_de(src, racines))} → {dst.name}")
    for c in plan["conflits"]:
        rapport.anomalies.append(f"fichiers : {c}")
    return plan


def _lire_tex(p: Path) -> tuple[str, str]:
    """Texte et encodage d'un .tex, fins de ligne gardées telles quelles (CRLF
    sous Windows) : seuls les codes réécrits changent dans le fichier."""
    brut = p.read_bytes()
    try:
        return brut.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return brut.decode("latin-1"), "latin-1"


def _racine_de(p: Path, racines: list[Path]) -> Path:
    for r in racines:
        try:
            p.relative_to(r)
            return r
        except ValueError:
            pass
    return p.parent


def _reecrire(texte: str, nom_final: str, noms: dict, carte_niv: dict, code_de) -> str:
    def inp(m):
        arg = m.group(2)
        tete, sep, queue = arg.rpartition("/")
        if not sep:
            tete, sep, queue = arg.rpartition("\\")
        base = queue
        ext = "" if base.endswith(".tex") else ".tex"
        nv = noms.get(base + ext)
        if nv is None:
            return m.group(0)
        if ext:
            nv = nv[:-4]
        return m.group(1) + (tete + sep if sep else "") + nv + m.group(3)

    texte2 = _RE_INPUT.sub(inp, texte)
    code = code_de(nom_final)

    def setc(m):
        ancien = m.group(2)
        nouveau = code or carte_niv.get(ancien) or ancien
        return m.group(1) + nouveau + m.group(3)

    return _RE_SETCODE.sub(setc, texte2)


def appliquer_fichiers(plan: dict, j: Journal, dossier_originaux: Path) -> None:
    """Écrit le plan ; chaque opération est notée dans le journal au fur et à
    mesure (retour arrière possible même après une erreur)."""
    # 1. originaux des fichiers réécrits
    for src, final, nv, enc in plan["reecritures"]:
        dossier_originaux.mkdir(parents=True, exist_ok=True)
        sauve = _nom_libre(dossier_originaux / src.name)
        shutil.copy2(src, sauve)
        src.write_bytes(nv.encode(enc))
        j.fichiers.append({"op": "reecrire", "fichier": str(src), "original": str(sauve),
                           "sha_apres": _sha_fichier(src)})
    # 2. copies
    for (src, dst), (dst2, nv, enc) in zip(plan["copies"], plan.get("reecritures_copies", [])):
        _creer_dossiers(dst.parent, j)
        dst.write_bytes(nv.encode(enc))
        j.fichiers.append({"op": "creer", "fichier": str(dst), "source": str(src),
                           "sha": _sha_fichier(dst)})
    # 3. renommages de fichiers, puis dossiers (les plus profonds d'abord)
    for src, dst in plan["renommages"]:
        _creer_dossiers(dst.parent, j)
        src.rename(dst)
        j.fichiers.append({"op": "renommer", "de": str(src), "vers": str(dst)})
        for op in j.fichiers:
            if op["op"] == "reecrire" and op["fichier"] == str(src):
                op["fichier"] = str(dst)
    for src, dst in plan["dossiers"]:
        src.rename(dst)
        j.fichiers.append({"op": "renommer_dossier", "de": str(src), "vers": str(dst)})


def _creer_dossiers(d: Path, j: Journal) -> None:
    manquants = []
    while not d.exists():
        manquants.append(d)
        d = d.parent
    for x in reversed(manquants):
        x.mkdir()
        j.fichiers.append({"op": "creer_dossier", "dossier": str(x)})


def chemin_actuel(chemin: str, ops_suivantes: list[dict]) -> str:
    """Chemin d'un fichier après les renommages de dossiers qui l'ont suivi."""
    c = chemin
    for op in ops_suivantes:
        if op["op"] == "renommer_dossier":
            de = op["de"].rstrip("/\\")
            if c == de or c.startswith(de + "/") or c.startswith(de + "\\"):
                c = op["vers"] + c[len(de):]
    return c


def verifier_fichiers(ops: list[dict]) -> list[str]:
    """Conflits qui empêchent le retour arrière des fichiers (liste vide = possible)."""
    conflits = []
    for i, op in enumerate(ops):
        suite = ops[i + 1:]
        if op["op"] in ("renommer", "renommer_dossier"):
            if not Path(chemin_actuel(op["vers"], suite)).exists():
                conflits.append(f"{chemin_actuel(op['vers'], suite)} absent")
        elif op["op"] == "creer":
            p = Path(chemin_actuel(op["fichier"], suite))
            if p.is_file() and _sha_fichier(p) != op["sha"]:
                conflits.append(f"{p} modifié depuis la migration (copie créée par l'outil)")
        elif op["op"] == "reecrire":
            p = Path(chemin_actuel(op["fichier"], suite))
            if not Path(op["original"]).is_file():
                conflits.append(f"original introuvable : {op['original']}")
            elif p.is_file() and _sha_fichier(p) != op["sha_apres"]:
                conflits.append(f"{p} modifié depuis la migration")
    return conflits


def annuler_fichiers(ops: list[dict], rapport: Rapport, verifier: bool = True) -> list[str]:
    """Rejoue à l'envers les opérations de fichiers ; renvoie les conflits."""
    if verifier:
        conflits = verifier_fichiers(ops)
        if conflits:
            return conflits
    # Chemins à remettre : on suit les renommages de dossiers à l'envers.
    for op in reversed(ops):
        if op["op"] in ("renommer", "renommer_dossier"):
            Path(op["vers"]).rename(op["de"])
            rapport.compter("fichiers remis à leur ancien nom")
        elif op["op"] == "creer":
            p = Path(op["fichier"])
            if p.is_file():
                p.unlink()
                rapport.compter("fichiers copiés retirés")
        elif op["op"] == "creer_dossier":
            p = Path(op["dossier"])
            if p.is_dir() and not any(p.iterdir()):
                p.rmdir()
        elif op["op"] == "reecrire":
            p = Path(_chemin_avant_renommage(op["fichier"], ops))
            shutil.copy2(op["original"], p)
            rapport.compter("fichiers remis dans leur contenu d'origine")
    return []


def _chemin_avant_renommage(chemin: str, ops: list[dict]) -> str:
    """Le fichier réécrit a pu être renommé ensuite : à l'étape de sa
    restauration (ordre inverse), il a déjà repris son ancien nom."""
    c = chemin
    for op in reversed(ops):
        if op["op"] == "renommer" and op["vers"] == c:
            c = op["de"]
    return c


# ── Retour arrière en base ──────────────────────────────────────────────────

def annuler_base(conn, ops: list[dict]) -> list[str]:
    """Rejoue à l'envers ; chaque ligne doit être dans l'état laissé par la
    migration (sinon : conflit, rien n'est fait). Appelant : transaction."""
    conflits = []
    for op in reversed(ops):
        t, cle = op["table"], op["cle"]
        where = " AND ".join(f'"{k}"=?' for k in cle)
        if op["op"] == "maj":
            cols = list(op["apres"])
            r = conn.execute(f'SELECT {", ".join(chr(34) + c + chr(34) for c in cols)} FROM "{t}" '
                             f'WHERE {where}', tuple(cle.values())).fetchone()
            if r is None or dict(zip(cols, r)) != op["apres"]:
                conflits.append(f"{t} {cle} : modifié depuis la migration "
                                f"(attendu {op['apres']}, trouvé {dict(zip(cols, r)) if r else 'rien'})")
                continue
            conn.execute(f'UPDATE "{t}" SET {", ".join(chr(34) + c + chr(34) + "=?" for c in cols)} '
                         f'WHERE {where}', (*op["avant"].values(), *cle.values()))
        else:
            cols = list(op["ligne"])
            r = conn.execute(f'SELECT {", ".join(chr(34) + c + chr(34) for c in cols)} FROM "{t}" '
                             f'WHERE {where}', tuple(cle.values())).fetchone()
            if r is None:
                conflits.append(f"{t} {cle} : ligne créée par la migration introuvable")
                continue
            if dict(zip(cols, r)) != op["ligne"]:
                conflits.append(f"{t} {cle} : ligne créée par la migration modifiée depuis")
                continue
            if t == "sequences_par_niveau" and conn.execute(
                    "SELECT 1 FROM sequence_parties WHERE sequence_par_niveau_id=? LIMIT 1",
                    (op["ligne"]["id"],)).fetchone():
                # v0.58.2 — la suppression emporterait (cascade) ce qui y a été créé.
                conflits.append(f"{t} {cle} : des parties y ont été créées depuis la migration")
                continue
            conn.execute(f'DELETE FROM "{t}" WHERE {where}', tuple(cle.values()))
    return conflits


# ── Exécution ───────────────────────────────────────────────────────────────

def executer(conn, cycles: list[str], corr: dict, recl: dict, rapport: Rapport,
             data_dir: Path | None, racines: list[Path], j: Journal,
             commit_par_cycle: bool = False) -> dict:
    """Migre les cycles demandés sur `conn` ; vérifie l'empreinte protégée ;
    prépare le plan des fichiers. Retourne {cartes, plan}."""
    avant = empreinte_protegee(conn, data_dir)
    cartes, mouvements = {}, []
    for cy in cycles:
        carte, mvts = migrer_cycle(conn, cy, corr, recl, j, rapport)
        for niv in NIVEAUX[cy]:
            if carte:
                cartes[niv] = carte
        mouvements += mvts
        apres = empreinte_protegee(conn, data_dir)
        diff = [k for k in avant if avant[k] != apres.get(k)] + [k for k in apres if k not in avant]
        if diff:
            raise MigrationErreur("ce qui ne doit jamais être touché a changé : " + ", ".join(diff))
        if commit_par_cycle:
            conn.commit()
    rapport.ligne("Jamais touché (empreintes identiques avant et après)",
                  f"{len(avant)} empreintes vérifiées : tables hors tables vivantes, archives du "
                  "cycle 3, fichiers referentiels\\ et referentiels_fichiers\\")
    for k, v in avant.items():
        rapport.ligne("Jamais touché (empreintes identiques avant et après)", f"{k} : {v[:16]}…")
    plan = plan_fichiers(racines, {n: c for n, c in cartes.items() if n.startswith("N1")}, j,
                         mouvements, rapport) if "C04" in cycles and cartes.get("N10") else None
    creees = sum(1 for op in j.ops if op["op"] == "ins" and op["table"] == "sequences_par_niveau")
    return {"cartes": cartes, "plan": plan, "empreinte": avant, "creees": creees}


def resoudre_base(db: str | None) -> Path:
    if db:
        return Path(db).resolve()
    from services.bascule import NOM_DB, dossier_par_defaut
    return dossier_par_defaut(RACINE_APPLI, "atelier") / NOM_DB


def sauvegarder(db: Path) -> Path:
    d = db.parent / "sauvegardes"
    d.mkdir(parents=True, exist_ok=True)
    cible = _nom_libre(d / f"avant_migration_2027_{datetime.now():%Y-%m-%d_%H%M%S}.db")
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    dst = sqlite3.connect(cible)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return cible


def dernier_journal(db: Path) -> Path | None:
    d = db.parent / "sauvegardes"
    js = sorted(d.glob(PREFIXE_JOURNAL + "*.json")) if d.is_dir() else []
    js = [p for p in js if not json.loads(p.read_text(encoding="utf-8")).get("annule_le")]
    return js[-1] if js else None


def _role(db: Path) -> str:
    from services import repartition
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return repartition.role(c)
    finally:
        c.close()


def commande_annuler(db: Path, chemin_journal: str | None, oui: bool) -> int:
    p = Path(chemin_journal) if chemin_journal else dernier_journal(db)
    if p is None or not p.is_file():
        print("Aucun journal de migration à annuler (sauvegardes\\journal_migration_2027_*.json).")
        return 2
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("annule_le"):
        print(f"Journal déjà annulé le {doc['annule_le']} : {p}")
        return 2
    print(f"Base : {db}\nJournal : {p} ({len(doc['ops'])} écritures en base, "
          f"{len(doc.get('fichiers', []))} opérations sur les fichiers)")
    conn = sqlite3.connect(db)
    try:
        conflits = annuler_base(conn, doc["ops"])
        conn.rollback()
    finally:
        conn.close()
    rapport = Rapport()
    if conflits:
        print("\nRetour arrière refusé, rien n'a été fait :")
        for c in conflits[:50]:
            print(f"  ! {c}")
        if len(conflits) > 50:
            print(f"  … et {len(conflits) - 50} autre(s)")
        print("Restaurer plutôt la sauvegarde : " + str(doc.get("sauvegarde", "")))
        return 2
    if not oui:
        rep = input("\nAnnuler la migration ? [o/N] ").strip().lower()
        if rep not in ("o", "oui", "y", "yes"):
            print("Abandon.")
            return 1
    verif = verifier_fichiers(doc.get("fichiers", []))
    if verif:
        print("\nRetour arrière refusé (fichiers déplacés ou modifiés depuis la migration) :")
        for c in verif[:30]:
            print(f"  ! {c}")
        return 2
    conn = sqlite3.connect(db)
    try:
        annuler_base(conn, doc["ops"])
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erreur, base inchangée : {e}")
        return 3
    finally:
        conn.close()
    annuler_fichiers(doc.get("fichiers", []), rapport, verifier=False)
    doc["annule_le"] = datetime.now().astimezone().isoformat(timespec="seconds")
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nMigration annulée : {len(doc['ops'])} écritures en base remises dans leur état "
          f"d'avant ; fichiers : {dict(rapport.comptes) or 'aucun'}.")
    return 0


def essai_a_blanc(db: Path, cycles, corr, recl, racines) -> tuple[Rapport, dict, Journal]:
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    mem = sqlite3.connect(":memory:")
    try:
        src.backup(mem)
    finally:
        src.close()
    rapport, j = Rapport(), Journal()
    try:
        res = executer(mem, cycles, corr, recl, rapport, db.parent, racines, j)
    finally:
        mem.close()
    return rapport, res, j


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Migration des thèmes et des codes A1 (rentrée 2027)")
    ap.add_argument("--apply", action="store_true", help="applique (sinon essai à blanc)")
    ap.add_argument("--annuler", nargs="?", const="", default=None, metavar="JOURNAL",
                    help="retour arrière d'après le journal (le dernier par défaut)")
    ap.add_argument("--yes", action="store_true", help="sans confirmation")
    ap.add_argument("--db", help="chemin de la base (défaut : base du profil atelier)")
    ap.add_argument("--cycle", choices=list(NIVEAUX), help="un seul cycle (défaut : les deux)")
    ap.add_argument("--latex", action="append", help="dossier qui contient N10\\, N11\\, N12\\")
    ap.add_argument("--sans-fichiers", action="store_true", help="ne touche à aucun fichier .tex")
    ap.add_argument("--reclassement", help="table de reclassement (défaut : outils\\reclassement_2027.json)")
    ap.add_argument("--sans-publication", action="store_true",
                    help="migre même si un référentiel figé n'a pas de première publication")
    args = ap.parse_args(argv)
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except Exception:
            pass
    db = resoudre_base(args.db)
    if not db.is_file():
        print(f"Base introuvable : {db}")
        return 2
    role = _role(db)
    if role == "classe":
        print(f"{db} est la base de l'appli de classe : la migration se fait dans l'atelier.")
        return 2
    if args.annuler is not None:
        return commande_annuler(db, args.annuler or None, args.yes)
    corr = charger_json(CORRESPONDANCE)
    recl = charger_json(Path(args.reclassement) if args.reclassement else RECLASSEMENT)
    cycles = [args.cycle] if args.cycle else list(NIVEAUX)
    racines = [] if args.sans_fichiers else racines_latex(db, args.latex)
    print(f"Base : {db}" + (f" (rôle {role})" if role else ""))
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    pre = Rapport()
    try:
        refus = precontroles(c, db.parent, args.sans_publication, pre)
    finally:
        c.close()
    if refus:
        print("\nMigration refusée :")
        for r in refus:
            print(f"  ! {r}")
        return 2
    try:
        rapport, res, _ = essai_a_blanc(db, cycles, corr, recl, racines)
    except MigrationErreur as e:
        print(f"\nMigration refusée : {e}")
        return 2
    rapport.anomalies = pre.anomalies + rapport.anomalies
    print(rapport.texte())
    rien = not res["cartes"] and not res.get("creees")
    plan = res["plan"]
    if plan and plan["conflits"]:
        print("\nConflits de fichiers : rien ne sera appliqué (voir les anomalies).")
        return 2
    if not args.apply:
        print("\n(essai à blanc : rien n'a été écrit — relancer avec --apply pour appliquer)"
              if not rien else "\nRien à faire.")
        return 0
    if rien:
        print("\nRien à faire : la base est déjà migrée.")
        return 0
    if not args.yes:
        rep = input("\nAppliquer la migration ? [o/N] ").strip().lower()
        if rep not in ("o", "oui", "y", "yes"):
            print("Annulé.")
            return 1
    sauvegarde = sauvegarder(db)
    print(f"\nSauvegarde : {sauvegarde}")
    horo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    journal_p = _nom_libre(db.parent / "sauvegardes" / f"{PREFIXE_JOURNAL}{horo}.json")
    j = Journal()
    rapport = Rapport()
    conn = sqlite3.connect(db)
    try:
        res = executer(conn, cycles, corr, recl, rapport, db.parent, racines, j,
                       commit_par_cycle=False)
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"\nErreur, rien n'a été écrit dans la base : {e}")
        return 3
    conn.close()
    rapport.anomalies = pre.anomalies + rapport.anomalies

    def ecrire_journal():
        journal_p.write_text(json.dumps({
            "outil": f"migrer_themes_codes_2027 {VERSION}", "base": str(db),
            "sauvegarde": str(sauvegarde), "cycles": cycles,
            "le": datetime.now().astimezone().isoformat(timespec="seconds"),
            "cartes": res["cartes"], "ops": j.ops, "fichiers": j.fichiers},
            ensure_ascii=False, indent=1), encoding="utf-8")

    ecrire_journal()
    if res["plan"]:
        try:
            appliquer_fichiers(res["plan"], j, db.parent / "sauvegardes" /
                               f"migration_2027_{horo}_tex_originaux")
        except Exception as e:
            print(f"\nErreur sur les fichiers ({e}) : retour arrière des fichiers et de la base.")
            annuler_fichiers(j.fichiers, Rapport(), verifier=False)
            c2 = sqlite3.connect(db)
            try:
                annuler_base(c2, j.ops)
                c2.commit()
            finally:
                c2.close()
            j.fichiers = []
            ecrire_journal()
            d = json.loads(journal_p.read_text(encoding="utf-8"))
            d["annule_le"] = datetime.now().astimezone().isoformat(timespec="seconds")
            journal_p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            return 3
        ecrire_journal()
    journal_p.with_name(journal_p.name.replace("journal_", "rapport_").replace(".json", ".txt")
                        ).write_text(rapport.texte(), encoding="utf-8")
    print(f"Journal (retour arrière : --annuler) : {journal_p}")
    print("\nMigration appliquée. Contrôles : relancer l'outil (« rien à faire »), ouvrir "
          "l'atelier, scanner une fois les sources LaTeX, recompiler quelques livrets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
