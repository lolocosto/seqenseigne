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
  9. **v0.54.1** — Titres de documents en double (décision D-DOUBLON,
     `doc/redemarrage_v0_54_1.md`) : deux documents des lots importés (TP, AC,
     AT, évaluations et tests courts, lots S et M) qui portent le même titre
     sont signalés en anomalie, sauf les sujets A et B d'une même évaluation
     (même séquence, un seul A et un seul B). Comparaison sans tenir compte des
     majuscules ni des espaces en trop. Rien n'est bloqué : le titre sert aux
     élèves et aux collègues, et les évaluations sont repérées par leur titre
     dans le niveau.
 10. **v0.57.0 — codes S… ou A1** (plan de migration des thèmes et des
     codes, livraison 1 ; décision D6, `doc/redemarrage_v0_57_0.md`) : un
     lot, `objectifs_6e.json` et la section « Mises en route » de
     `ref6e_v2.md` peuvent être écrits en anciens codes (S01, thème B
     « Grandeurs et mesures ») ou en codes de thème (A1, thème F). Tout est
     ramené aux codes **de la base** (cycle 3 en S… : avant la migration ;
     en A1… : après) au moyen de `outils/correspondance_codes_2027.json` :
     après la migration, un lot S01 est importé en A1 et aucune séquence
     S01… n'est jamais recréée. Une base qui mêle les deux familles est
     refusée. Un lot de code inconnu n'est pas importé (anomalie).

 11. **v0.59.0 — autres niveaux au modèle Fiches** (décisions D2 et D3,
     `doc/redemarrage_v0_59_0.md`) : `--niveau N11` importe les lots de 4e
     (`..\reference\lot4e\A1\A1.json`…) d'après `outils/objectifs_4e.json`
     (transcription de `outils/ref4e_v1.md`, codes A1). Hors 6e : ni
     archivage du cycle 3, ni écriture dans les thèmes et séquences du cycle
     (ceux de la base font foi ; séquence absente : lot non importé), ni
     mises en route ; l'import **refuse** de s'appliquer tant que la
     structure de 2025 du niveau n'est pas archivée
     (`outils/archiver_structure_niveau.py --niveau N11 --apply`). Le
     libellé de chaque partie est écrit dans `sequence_parties.libelle`, le
     titre court de la séquence dans `sequences_par_niveau.titre_court`.
     Clé `cartes_automatisme` d'un objectif (tous niveaux) : cartes créées ou
     mises à jour par (niveau, séquence, num), rattachées à l'objectif
     (`objectif_cartes`), niveau de création gardé (`niveau_creation`) ;
     carte validée jamais réécrite.

 12. **v0.59.1 — alignement des rattachements de cartes** : le lot fait foi
     pour les cartes qu'il cite ; une carte citée sous un objectif perd ses
     liens vers les autres objectifs de la même séquence (sauf carte validée
     ou séquence validée : signalé) ; liens vers d'autres séquences et cartes
     non citées intouchés. L'essai à blanc liste les liens retirés.
 13. **v0.59.2 — séances et encarts** (`doc/redemarrage_v0_59_2.md`) :
     - clé facultative `seances` d'un objectif (nombre de séances, ≥ 0) et
       `seances_cours` du lot (séances de l'objectif « Cours » : un nombre pour
       chaque partie, ou `{"1": 1, "2": 1}`) → `objectifs.nb_seances`, que lit
       le référentiel (vue d'ensemble, durée des parties). Clé absente : valeur
       en base gardée (saisie dans l'atelier) ; valeur invalide : anomalie,
       ignorée. Idempotent ;
     - clé facultative `encarts` (`lot6e/FORMAT_ENCARTS.md`) d'un objectif
       (positions `apres_activite`, `apres_exercice` + `exercice`,
       `fin_objectif`) et du lot (encarts de partie : `partie`, position
       `fin_partie`) → table `encarts` (services/encarts.py). Dès qu'un lot
       porte une clé `encarts`, il fait foi pour les encarts de sa séquence
       (créés, mis à jour, retirés ; retraits dans le journal) ; un lot sans
       la clé ne touche à rien. Encart refusé (type, position, exercice
       inconnus…) : anomalie, non importé. Jamais sur une séquence validée
       (lot non importé).

 14. **v0.60.0 — version 2 du modèle Fiches** (`doc/redemarrage_v0_60_0.md`) :
     - clé `tests_courts` du lot (même format que `evaluations`) et titres
       « Test court --- … » : `evaluations.type_evaluation = 'test_court'`
       (décision T1) ; contrôles non bloquants (section « Avertissements ») :
       un test court par partie, test court sur 10 avec bonus de 1, bonus de
       1 point des évaluations (B10) ; v0.60.2 : plus de contrôle « sur 10 » ni
       de bonus pour un test court (voir 15) ;
     - activités de découverte sous l'objectif « Cours » d'une partie
       (`"code": "A1-01"`, ou `"code": "Cours", "partie": 1`) : rattachées à
       la partie et au « Cours », elles ouvrent la partie dans le livret (B6) ;
     - clé facultative `variables` des exercices, activités et documents TP,
       AC, AT (bloc xint ; absente : valeur en base gardée) ; deux exercices
       qui déclarent la même variable sont signalés (B7) ;
     - durée de la partie sans calculatrice annoncée d'après la durée de
       l'évaluation (10 min par objectif ; décision T3, correctif B8).
     - `--niveau N10` : lots de 5e (`outils/objectifs_5e.json`, F1) ;
     - `niveau_creation` d'une carte **validée** corrigé quand c'est le seul
       champ qui change (avertissement, mtime gardé : rendu inchangé ; F3).

 15. **v0.60.2 — tests courts en QCM** (`doc/redemarrage_v0_60_2.md`) :
     - exercice QCM d'une évaluation ou d'un test court (énoncé avec
       `\begin{seqQcm}`) : barème QCM posé (bonne réponse = points d'une
       question, soit points de l'exercice / nombre de `\seqQcmQuestion`,
       1 pt par défaut ; partielle 0 ; mauvaise 0), exigé par la validation
       d'une évaluation notée ; un réimport sur une évaluation en cours pose
       les champs manquants (rien d'autre ne change) ;
     - test court : plus d'avertissement « sur 10 » ni « bonus » (décisions 16
       et 17) ; total = somme des points de ses questions ; bonus de 1 pt
       contrôlé pour les évaluations du cycle 4 seulement ;
     - figure citée par un lot mais absente de son dossier `figures/` : déjà
       présente dans `images\` de l'appli (image d'origine d'un exercice
       repris) → signalée « déjà présente dans images (non fournie par le
       lot) », pas une anomalie ; introuvable partout : anomalie (inchangé).

Idempotence : objectifs repérés par (niveau, séquence, code), exercices et
documents par (niveau, séquence, série, num), fiches par leur objectif,
évaluations par (niveau, titre). Une deuxième exécution ne crée rien ; un
contenu modifié dans le lot est mis à jour (sauf élément validé dans
l'atelier, laissé tel quel et signalé).

Usage (Windows, depuis `appli\`) :
    ..\outils\python\python.exe .\outils\import_lot6e.py                 # essai à blanc
    ..\outils\python\python.exe .\outils\import_lot6e.py --apply         # applique (confirmation)
    ..\outils\python\python.exe .\outils\import_lot6e.py --apply --yes   # sans confirmation
    ..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11    # 4e (v0.59.0)
Options : --db CHEMIN (base), --lots DOSSIER (défaut ..\reference\lot6e ;
..\reference\lot4e pour N11, ..\reference\lot5e pour N10), --niveau N09 | N10 | N11
(défaut N09 ; N10 depuis la v0.60.0).
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
from datetime import datetime, timezone
from pathlib import Path

RACINE_APPLI = Path(__file__).resolve().parent.parent
if str(RACINE_APPLI) not in sys.path:          # lancement par chemin (Windows)
    sys.path.insert(0, str(RACINE_APPLI))

from services import fiches_resume as svc_fiches          # noqa: E402
from services.atomes import SERIES_DOCUMENTS, _deduire_type_format  # noqa: E402
from services import marqueurs_exercices as mq                     # noqa: E402
from services import series_fiches as sf                         # noqa: E402  (v0.56.0)
from services import codes_sequence as cs                         # noqa: E402  (v0.57.0)

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
# v0.59.0 (D2) — niveaux dont les lots s'importent au modèle Fiches : cycle,
# référentiel transcrit, dossier des lots par défaut. Les fonctions lisent les
# globaux NIVEAU, CYCLE, REFERENTIEL, LOTS_DEFAUT, posés par `niveau_actif`.
NIVEAUX_LOTS = {
    "N09": {"cycle": "C03", "referentiel": Path(__file__).resolve().parent / "objectifs_6e.json",
            "lots": RACINE_APPLI.parent / "reference" / "lot6e"},
    # v0.60.0 (F1) — 5e : référentiel transcrit de col4/5e/ref5e_v1.md.
    "N10": {"cycle": "C04", "referentiel": Path(__file__).resolve().parent / "objectifs_5e.json",
            "lots": RACINE_APPLI.parent / "reference" / "lot5e"},
    "N11": {"cycle": "C04", "referentiel": Path(__file__).resolve().parent / "objectifs_4e.json",
            "lots": RACINE_APPLI.parent / "reference" / "lot4e"},
}
COMMANDE_ARCHIVAGE = ("..\\outils\\python\\python.exe .\\outils\\archiver_structure_niveau.py "
                      "--niveau {niveau} --apply")
RE_GRAPHIQUE = re.compile(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
RE_LOC = re.compile(r"\\(seqLoc[A-Za-z]+)")
# v0.52.8 (I2) — macros du module de 6e appelées par le lot (\seqAstuceSix…).
RE_SIX = re.compile(r"\\(seq[A-Za-z]*Six)(?![A-Za-z])")


class ImportErreur(Exception):
    pass


class niveau_actif:
    """v0.59.0 (D2) — Pose les globaux du module (NIVEAU, CYCLE, REFERENTIEL,
    LOTS_DEFAUT) pour un niveau de `NIVEAUX_LOTS` le temps d'un bloc `with`,
    puis les remet (tests, appels successifs). Niveau inconnu : ImportErreur."""

    def __init__(self, niveau: str | None):
        self.niveau = (niveau or "N09").strip().upper()
        if self.niveau not in NIVEAUX_LOTS:
            raise ImportErreur(f"niveau {self.niveau} : lots non pris en charge (niveaux : "
                               f"{', '.join(NIVEAUX_LOTS)})")

    def __enter__(self):
        g = globals()
        self._avant = {k: g[k] for k in ("NIVEAU", "CYCLE", "REFERENTIEL", "LOTS_DEFAUT")}
        c = NIVEAUX_LOTS[self.niveau]
        g.update(NIVEAU=self.niveau, CYCLE=c["cycle"], REFERENTIEL=c["referentiel"],
                 LOTS_DEFAUT=c["lots"])
        return self

    def __exit__(self, *exc):
        globals().update(self._avant)
        return False


# v0.60.1 (D16) — niveaux où toute évaluation a un bonus de 1 point (cycle 4).
NIVEAUX_BONUS_1 = ("N10", "N11", "N12")


def est_sixieme() -> bool:
    """Niveau actif = 6e (archivage du cycle 3, cycle 3 écrit, mises en route)."""
    return NIVEAU == "N09"


def message_archivage_manquant(niveau: str) -> str:
    return (f"structure de 2025 de {niveau} non archivée : l'import des lots de {niveau} "
            "réécrirait les objectifs et les exercices de 2025 (mêmes codes A1-02, F01…). "
            "Archivez-la d'abord, depuis appli\\ : "
            + COMMANDE_ARCHIVAGE.format(niveau=niveau) + " — puis relancez l'import.")


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
    """Horodatage des `mtime` écrits par l'import, en **UTC** comme le reste de
    l'appli (`CURRENT_TIMESTAMP` de SQLite, `compile_date` des documents) :
    `peremption_atomes` compare ces chaînes telles quelles. v0.59.2 — avant,
    heure locale : un document compilé moins d'une heure (deux en été) après
    un import s'affichait « périmé »."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


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

def charger_referentiel(chemin: Path | None = None) -> dict:
    """`objectifs_6e.json` (ou, v0.59.0, celui du niveau actif)."""
    chemin = chemin or REFERENTIEL
    ref = json.loads(Path(chemin).read_text(encoding="utf-8"))
    for cle in ("themes", "sequences", "parties", "objectif_cours"):
        if cle not in ref:
            raise ImportErreur(f"{chemin} : clé « {cle} » absente")
    return ref


def charger_lots(dossier: Path) -> list[dict]:
    """Lots S01/S01.json, S02/S02.json… triés par code de séquence, puis
    (v0.53.0) les lots de mise en route M01/M01.json… (outils/import_lot6e_mer.py).
    v0.57.0 : aussi les lots en codes de thème (A1/A1.json…)."""
    dossier = Path(dossier)
    lots = []
    for d in sorted((p for p in dossier.iterdir()
                     if p.is_dir() and (re.fullmatch(r"[SM]\d\d", p.name)
                                        or cs.est_code_theme(p.name))),
                    key=lambda p: (cs.est_code_mer(p.name), cs.cle_tri(p.name))):
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
        self.cartes_mentales: "OrderedDict[str, dict]" = OrderedDict()   # v0.55.0
        self.fiches_cours: "OrderedDict[str, int]" = OrderedDict()       # v0.55.0 (lots M)
        self.journal: dict = {"archivage": [], "import": []}
        # Découpage de la géométrie : séquences dont le code a changé de sens
        # alors qu'un contenu de l'ancien sens existe (lot non importé).
        self.sequences_bloquees: set = set()
        self.cartes_automatisme: "OrderedDict[str, dict]" = OrderedDict()  # v0.59.0
        self.cartes_alignement: list[str] = []                  # v0.59.1 (liens retirés)
        self.niveau = NIVEAU                                   # v0.59.0 (en-tête)
        self.archivage_niveau: dict | None = None              # v0.59.0 (hors 6e)
        self.seances: list[str] = []                          # v0.59.2
        self.encarts: "OrderedDict[str, dict]" = OrderedDict()  # v0.59.2
        self.avertissements: list[str] = []                   # v0.60.0 (non bloquants)
        # v0.60.1 (R7) — à repasser en cours pour que le réimport s'applique.
        self.a_repasser: dict = {"sequences": [], "evaluations": [], "exercices": []}

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

    def resume_fiches(self) -> "OrderedDict[str, int]":
        """v0.55.0 — fiches de résumé de toutes les séquences, par état
        (compteurs « fiche » des objectifs, lots S et M)."""
        tot: "OrderedDict[str, int]" = OrderedDict()
        for s in self.sequences.values():
            for o in s["objectifs"].values():
                for quoi, etats in o["c"].items():
                    if quoi in ("fiche", "fiche de cours"):
                        for e, n in etats.items():
                            tot[e] = tot.get(e, 0) + n
        return tot

    def texte_resume(self) -> list[str]:
        """v0.55.0 — Résumé des fiches de résumé et des cartes mentales, en
        tête de lecture de l'essai à blanc : les fiches non validées sont mises
        à jour d'après le lot, les fiches validées dans l'atelier ne le sont
        jamais (signalées)."""
        L = ["== Fiches de résumé et cartes mentales (v0.55.0) =="]
        f = self.resume_fiches()
        L.append("  fiches de résumé (lots S) : "
                 + (", ".join(f"{e} {n}" for e, n in f.items()) or "aucune"))
        L.append("  fiches de cours de partie (lots M) : "
                 + (", ".join(f"{e} {n}" for e, n in self.fiches_cours.items()) or "aucune"))
        if f.get("validée, non modifiée") or self.fiches_cours.get("validée, non modifiée"):
            L.append("  ATTENTION : des fiches validées dans l'atelier ne sont pas mises à "
                     "jour (les repasser « en cours » puis relancer l'import)")
        tot: dict = {}
        for seq, c in self.cartes_mentales.items():
            L.append(f"  cartes mentales {seq} : " + ", ".join(f"{e} {n}" for e, n in c.items()))
            for e, n in c.items():
                tot[e] = tot.get(e, 0) + n
        L.append("  cartes mentales (total) : "
                 + (", ".join(f"{e} {n}" for e, n in tot.items()) or "aucune"))
        return L

    def texte_cartes(self) -> list[str]:
        """v0.59.0 (D3) — cartes d'automatisme des lots, par séquence et état."""
        L = ["== Cartes d'automatisme rattachées aux objectifs (v0.59.0) =="]
        if not self.cartes_automatisme:
            return L + ["  aucune"]
        tot: dict = {}
        for seq, c in self.cartes_automatisme.items():
            L.append(f"  {seq} : " + ", ".join(f"{e} {n}" for e, n in c.items()))
            for e, n in c.items():
                tot[e] = tot.get(e, 0) + n
        L.append("  total : " + ", ".join(f"{e} {n}" for e, n in tot.items()))
        # v0.59.1 — alignement sur le lot : liens vers un autre objectif de la
        # séquence retirés (le lot fait foi pour les cartes qu'il cite).
        L.append(f"  rattachements alignés sur le lot : {len(self.cartes_alignement)} "
                 "lien(s) retiré(s)")
        L += [f"    - {x}" for x in self.cartes_alignement]
        return L

    def texte_seances_encarts(self) -> list[str]:
        """v0.59.2 — séances écrites (clés `seances`, `seances_cours`) et encarts."""
        L = ["== Séances des objectifs (v0.59.2) =="]
        L.append(f"  {len(self.seances)} objectif(s) dont les séances changent"
                 + ("" if self.seances else " (clé absente ou valeurs déjà en base)"))
        L += [f"    - {x}" for x in self.seances]
        L.append("")
        L.append("== Encarts du livret (v0.59.2) ==")
        if not self.encarts:
            L.append("  aucun lot ne porte de clé « encarts » : rien n'est touché")
        for seq, c in self.encarts.items():
            L.append(f"  {seq} : créés {c['crees']}, mis à jour {c['maj']}, inchangés "
                     f"{c['inchanges']}, retirés {c['retires']}")
        return L

    def texte_a_repasser(self) -> list[str]:
        """v0.60.1 (R7) — Ce qui bloque un réimport, et comment le débloquer."""
        a = self.a_repasser
        if not any(a.values()):
            return []
        L = ["== À repasser en cours avant l'import (sinon non réimporté) =="]
        if a["sequences"]:
            L += [f"  Séquences validées (lot non importé) : {', '.join(a['sequences'])}",
                  "    → Ateliers › portée Séquence › niveau › « — Toutes les séquences — » : "
                  "clic sur la première, Maj+clic sur la dernière, « ⟲ En cours »."]
        if a["evaluations"]:
            L.append(f"  Évaluations et tests courts validés que le lot modifie "
                     f"({len(a['evaluations'])}) :")
            L += [f"    {x}" for x in a["evaluations"]]
            L.append("    → Ateliers › portée Niveau › Évaluation : clic sur la première, "
                     "Maj+clic sur la dernière (ou Ctrl+clic), « ⟲ En cours » ; leurs exercices "
                     "EV propres repassent en cours avec elles (v0.60.1).")
        if a["exercices"]:
            L.append(f"  Exercices EV validés d'évaluations en cours ({len(a['exercices'])}) :")
            L += [f"    {x}" for x in a["exercices"]]
            L.append("    → Ateliers › portée Séquence › Exercice › série EV : sélection, "
                     "« ⟲ En cours » ; ou, dans Évaluation : « ✓ Valider » puis « ⟲ En cours » "
                     "sur l'évaluation.")
        L += ["  Puis relancer l'essai à blanc, appliquer (--apply) et revalider (« ✓ Valider "
              "» des mêmes listes).", ""]
        return L

    def texte(self) -> str:
        L = []
        if self.niveau == "N09":
            L.append("== Archivage de l'ancien cycle 3 (réversible) ==")
            if not self.archivage:
                L.append("  déjà fait lors d'une exécution précédente : rien à archiver")
            for k, v in self.archivage.items():
                L.append(f"  {k} : {v} archivé(s)")
            L.append("")
            L.append("== Cycle 3 : thèmes et séquences ==")
        else:                                                    # v0.59.0 (D2)
            a = self.archivage_niveau
            L.append(f"== Structure de 2025 de {self.niveau} ==")
            L.append(f"  archivée le {a['fait_le']} ({a['resume'] or 'aucune séquence'})" if a
                     else "  NON archivée : import refusé")
            L.append("")
            L.append("== Séquences du cycle (lues en base, jamais écrites) ==")
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
            if s.get("mentions"):                                    # v0.56.0
                L.append("  mentions (séries F, A, E) : " + ", ".join(
                    f"{k} {n}" for k, n in s["mentions"].items()))
        L.append("")
        L.append("== Figures ==")
        L += [f"  {x}" for x in self.figures] or ["  aucune"]
        if self.documents:
            L.append("")
            L.append("== Documents et évaluations (séries TP, AC, AT, EV) ==")
            L += [f"  {x}" for x in self.documents]
        L.append("")
        L += self.texte_resume()                                     # v0.55.0
        L.append("")
        L += self.texte_cartes()                                     # v0.59.0
        L.append("")
        L += self.texte_seances_encarts()                            # v0.59.2
        L.append("")
        L += self.texte_a_repasser()                                 # v0.60.1 (R7)
        L.append(f"== Anomalies ({len(self.anomalies)}) ==")
        L += [f"  - {x}" for x in self.anomalies] or ["  aucune"]
        if self.avertissements:                                      # v0.60.0
            L.append("")
            L.append(f"== Avertissements ({len(self.avertissements)}, non bloquants) ==")
            L += [f"  - {x}" for x in self.avertissements]
        if self.infos:
            L.append("")
            L.append("== Informations ==")
            L += [f"  - {x}" for x in self.infos]
        return "\n".join(L)


# ── 0. Codes S… ou A1 (v0.57.0, décision D6) ────────────────────────────────

# Clés d'un lot dont la valeur (ou les éléments, pour une liste) est un code
# de séquence (« S01 ») ou d'objectif (« S01-02 ») ; ailleurs, seules les
# étiquettes d'évaluation « N pts --- S01-02 » sont traduites.
_CLES_CODES_LOT = ("sequence", "code", "objectif", "objectifs", "bareme")
_RE_CODE_OBJ = re.compile(r"^(" + cs.MOTIF_ANCIEN + "|" + cs.MOTIF_THEME + r")(-\d\d)?$")
# v0.58.0 — l'étiquette est « N pts --- S01-02 » : sans « pts », un titre de
# document (« Séquence 1 : Nombres --- S01-02, S01-03 ») est du texte libre,
# jamais traduit (sinon, après la migration, 12 documents des lots de 6e
# seraient « mis à jour » avec un titre à moitié traduit).
_RE_ETIQ_LOT = re.compile(r"(\d+(?:[.,]\d+)?\s*pts?\s*---\s*)(" + cs.MOTIF_ANCIEN + "|"
                          + cs.MOTIF_THEME + r")-(\d\d)")


_LIBELLE_CONV = {"ancien": "anciens codes (S…)", "nouveau": "codes de thème (A1…)"}


def convention_base(conn) -> str | None:
    """Codes des séquences principales du cycle 3 en base : 'ancien' (S01…,
    avant la migration), 'nouveau' (A1…, après) ou None (aucune). Mnn et
    Xnn ne comptent pas. ImportErreur si les deux familles se mêlent."""
    try:
        return cs.convention_codes(r[0] for r in conn.execute(
            "SELECT code FROM sequences_du_cycle WHERE cycle_code=?", (CYCLE,)))
    except cs.CorrespondanceErreur as e:
        raise ImportErreur(f"base : cycle 3 en codes mêlés ({e}) — migration incomplète, "
                           "import refusé") from e


def _traduire_code(table, code: str, source: str, cible: str) -> str:
    """S01 ↔ A1, S01-02 ↔ A1-02 (codes de la convention `source` seulement)."""
    m = _RE_CODE_OBJ.match(code or "")
    if not m or cs.convention_codes([m.group(1)]) != source:
        return code
    return table.vers(CYCLE, m.group(1), cible) + (m.group(2) or "")


def traduire_lot(lot: dict, table, cible: str | None) -> dict:
    """Copie du lot exprimée dans la convention `cible` ('ancien' ou
    'nouveau') ; le lot lui-même si rien ne change. La convention du lot est
    celle de son code de séquence ; un lot de mise en route garde son code
    (seule sa lettre de thème est traduite)."""
    seq = lot.get("sequence") or ""
    if cs.est_code_mer(seq):
        theme = lot.get("theme")
        if theme and cible:
            t = table.theme_mer(CYCLE, seq, theme, cible)
            if t != theme:
                return {**lot, "theme": t, "_theme_lot": theme}
        return lot
    source = cs.convention_codes([seq])
    if not source or not cible or source == cible:
        return lot
    if table.sequence(CYCLE, seq) is None:
        return lot                                    # code inconnu : lot non importé

    def etiquettes(texte: str) -> str:
        return _RE_ETIQ_LOT.sub(
            lambda m: m.group(1) + _traduire_code(table, f"{m.group(2)}-{m.group(3)}",
                                                  source, cible), texte)

    def parcourir(x, cle=None):
        if isinstance(x, dict):
            return {k: (v if k.startswith("_") else parcourir(v, k)) for k, v in x.items()}
        if isinstance(x, list):
            return [parcourir(v, cle) for v in x]
        if isinstance(x, str):
            if cle in _CLES_CODES_LOT:
                x = _traduire_code(table, x, source, cible)
            return etiquettes(x)
        return x

    out = parcourir(lot)
    out["_sequence_lot"] = seq
    return out


def traduire_referentiel(ref: dict, table, cible: str | None) -> dict:
    """Copie de `objectifs_6e.json` dans la convention `cible` : codes,
    numéros et thèmes des séquences, codes et ordre des thèmes, clés de
    `parties`. Le référentiel lui-même si rien ne change."""
    try:
        source = cs.convention_codes(s["code"] for s in ref["sequences"])
    except cs.CorrespondanceErreur as e:
        raise ImportErreur(f"objectifs_6e.json : {e}") from e
    if not source or not cible or source == cible:
        return ref
    out = dict(ref)
    themes = []
    for t in ref["themes"]:
        e = table.theme(CYCLE, t["code"], source)
        if e is None:
            raise ImportErreur(f"objectifs_6e.json : thème {t['code']} absent de la table de "
                               "correspondance")
        themes.append({**t, "code": table.theme_vers(CYCLE, t["code"], source, cible),
                       "ordre": e["ordre_nouveau"] if cible == "nouveau" else e["ordre_ancien"]})
    out["themes"] = themes
    seqs = []
    for s in ref["sequences"]:
        e = table.sequence(CYCLE, s["code"])
        if e is None:
            raise ImportErreur(f"objectifs_6e.json : séquence {s['code']} absente de la table "
                               "de correspondance")
        seqs.append({**s, "code": table.vers(CYCLE, s["code"], cible),
                     "numero": e["numero_nouveau"] if cible == "nouveau" else e["numero_ancien"],
                     "theme": table.theme_vers(CYCLE, s["theme"], source, cible)})
    out["sequences"] = seqs
    out["parties"] = {table.vers(CYCLE, k, cible): v for k, v in ref["parties"].items()}
    out["_convention_source"] = source
    return out


def traduire_ref_mer(ref_mer: dict, table, cible: str | None) -> dict:
    """Lettres de thème des mises en route (ref6e_v2.md) dans la convention
    `cible` (M03 : B ↔ F) ; codes Mnn inchangés."""
    if not cible:
        return ref_mer
    return {code: ({**r, "theme": table.theme_mer(CYCLE, code, r.get("theme") or "", cible)}
                   if r.get("theme") else r)
            for code, r in ref_mer.items()}


def normaliser_codes(conn, ref: dict, lots: list[dict], ref_mer: dict,
                     rapport: "Rapport", table=None):
    """(ref, lots, ref_mer, convention) ramenés aux codes de la base (D6).
    Base sans séquence principale au cycle 3 : convention du référentiel."""
    table = table or cs.charger_correspondance()
    base = convention_base(conn)
    try:
        conv_ref = cs.convention_codes(s["code"] for s in ref["sequences"])
    except cs.CorrespondanceErreur as e:
        raise ImportErreur(f"objectifs_6e.json : {e}") from e
    cible = base or conv_ref
    ref2 = traduire_referentiel(ref, table, cible)
    if ref2 is not ref:
        rapport.infos.append(f"objectifs_6e.json écrit en {_LIBELLE_CONV[conv_ref]}, ramené "
                             f"aux {_LIBELLE_CONV[cible]} de la base (table de correspondance)")
    if cible == "nouveau" and any(cs.est_code_ancien(s["code"]) for s in ref2["sequences"]):
        raise ImportErreur("base en codes de thème : le référentiel recréerait des séquences "
                           "S… (import refusé)")
    lots2 = []
    for lot in lots:
        l2 = traduire_lot(lot, table, cible)
        if l2 is not lot and "_sequence_lot" in l2:
            rapport.infos.append(f"lot {lot['sequence']} lu en {l2['sequence']} (table de "
                                 "correspondance)")
        elif l2 is not lot and "_theme_lot" in l2:
            rapport.infos.append(f"lot {lot['sequence']} : thème {l2['_theme_lot']} lu "
                                 f"{l2['theme']} (table de correspondance)")
        lots2.append(l2)
    return ref2, lots2, traduire_ref_mer(ref_mer, table, cible), cible


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
        rapport.seq(seq)["lignes"].append(f"séquence-niveau {NIVEAU} : créée")
        return conn.execute("SELECT * FROM sequences_par_niveau WHERE niveau=? AND "
                            "sequence_code=?", (NIVEAU, seq)).fetchone()
    if r["etat_code"] == "valide":
        rapport.anomalie(f"{seq} : séquence-niveau {NIVEAU} validée dans l'atelier, non modifiée "
                         "(la repasser « en cours » pour importer)")
        return None
    rapport.seq(seq)["lignes"].append(f"séquence-niveau {NIVEAU} : existante")
    return r


def _partie(conn, sn_id: str, numero: int, seq: str, rapport: Rapport,
           libelle: str | None = None) -> str:
    """v0.59.0 (D6) — `libelle` (hors 6e) : écrit dans `sequence_parties.libelle`
    (le livret Fiches hors 6e le lit) ; None = colonne non touchée (6e : les
    libellés viennent d'objectifs_6e.json)."""
    r = conn.execute("SELECT id FROM sequence_parties WHERE sequence_par_niveau_id=? AND "
                     "numero=?", (sn_id, numero)).fetchone()
    if r:
        if libelle is not None:
            avant = conn.execute("SELECT libelle FROM sequence_parties WHERE id=?",
                                 (r["id"],)).fetchone()[0] or ""
            if avant != libelle:
                conn.execute("UPDATE sequence_parties SET libelle=? WHERE id=?",
                             (libelle, r["id"]))
                rapport.seq(seq)["lignes"].append(f"partie {numero} : libellé « {libelle} » "
                                                  "écrit")
        return r["id"]
    pid = _nid("pt")
    conn.execute("INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero, "
                 "nb_seances_R_AE) VALUES (?,?,?,0)", (pid, sn_id, numero))
    if libelle is not None:
        conn.execute("UPDATE sequence_parties SET libelle=? WHERE id=?", (libelle, pid))
    rapport.seq(seq)["lignes"].append(f"partie {numero} : créée"
                                      + (f" (« {libelle} »)" if libelle else ""))
    return pid


def _titre_court(conn, sn_id: str, seq: str, titre: str, rapport: Rapport) -> None:
    """v0.59.0 (D5) — titre court de la séquence-niveau (hors 6e)."""
    from services import fiches_cycle4 as fc4
    fc4.migrer(conn)
    avant = conn.execute("SELECT titre_court FROM sequences_par_niveau WHERE id=?",
                         (sn_id,)).fetchone()[0] or ""
    if avant != titre:
        conn.execute("UPDATE sequences_par_niveau SET titre_court=? WHERE id=?", (titre, sn_id))
        rapport.seq(seq)["lignes"].append(f"titre court « {titre} » : "
                                          + ("écrit" if not avant else f"remplace « {avant} »"))


def _objectif(conn, sn_id: str, partie_id: str, code: str, d: dict,
              rapport: "Rapport | None" = None, etiquette: str = "",
              source: str | None = None) -> tuple[str, str]:
    """(id, état) de l'objectif (niveau, séquence, code).

    v0.52.8 (O1) — Un objectif existant (séquence non validée : une séquence
    validée n'est pas importée) prend l'intitulé et les critères F, A, E du
    référentiel ; ce qui change est détaillé dans les informations du
    rapport, dès l'essai à blanc."""
    r = conn.execute(
        "SELECT o.* FROM objectifs o JOIN sequence_parties p ON p.id = o.partie_id "
        "WHERE p.sequence_par_niveau_id=? AND o.code=?", (sn_id, code)).fetchone()
    vals = (d["nom"], d["critere_F"], d["critere_A"], d["critere_E"])
    source = source or Path(REFERENTIEL).name                   # v0.59.0
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
                                 f"{source} ({', '.join(quoi)})")
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


def mention_lot(src: dict, quoi: str, rapport: "Rapport | None" = None) -> str:
    """v0.56.0 — Clé facultative `mention` d'un exercice de série F, A ou E :
    absente = 'O' (obligatoire), 'F' = facultatif ; valeur inconnue : signalée
    (anomalie) et lue 'O'."""
    try:
        return sf.valider(src.get("mention"))
    except sf.MentionInvalide:
        if rapport is not None:
            rapport.anomalie(f"{quoi} : mention {src.get('mention')!r} inconnue "
                             "(attendu O ou F), lue O")
        return sf.MENTION_DEFAUT


def _compter_mention(rapport: "Rapport", seq: str, mention: str) -> None:
    c = rapport.seq(seq).setdefault("mentions", OrderedDict([("obligatoire", 0),
                                                           ("facultatif", 0)]))
    k = sf.LIBELLES_MENTIONS[mention]
    c[k] = c.get(k, 0) + 1


def _exercice(conn, seq: str, serie_code: str, num: int, src: dict,
              marques: dict | None = None, mention: str | None = None) -> tuple[str, str]:
    """(id, état) de l'exercice (N09, séquence, série, num).

    v0.52.7 — `marques` : marqueurs du lot (`marqueurs_lot`), comparés et
    écrits avec le contenu quand la base a les colonnes ; None = non
    marqué.

    v0.56.0 — `mention` (séries F, A, E : 'O' ou 'F', `mention_lot`) : comparée
    et écrite comme le contenu (jamais sur un exercice validé) ; None (autres
    séries) : la colonne n'est pas touchée."""
    vals = {"titre": src.get("titre", "") or "",
            "enonce": src.get("enonce", src.get("latex", "")) or "",
            "corrige": src.get("corrige", "") or "",
            "remed_enonce": src.get("remed_enonce", "") or "",
            "remed_corrige": src.get("remed_corrige", "") or ""}
    if "variables" in src:
        # v0.60.0 (B7) — clé facultative `variables` (bloc xint, comme les
        # exercices paramétrés de la base) ; clé absente : valeur en base
        # gardée (saisie dans l'atelier).
        vals["variables"] = src.get("variables") or ""
    if mq.colonnes_presentes(conn):
        vals.update({c: (marques or {}).get(c, "") or "" for c in mq.CHAMPS})
    if mention is not None and sf.colonne_presente(conn):
        vals["mention"] = mention
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
        rapport.anomalie(f"{seq} : séquence absente de {Path(REFERENTIEL).name}, lot non importé")
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
    if not est_sixieme() and s_ref.get("titre_court"):            # v0.59.0 (D5)
        _titre_court(conn, sn["id"], seq, s_ref["titre_court"], rapport)
    objs_ref = {f"{seq}-{o['code']}": (p["numero"], o) for p in parties_ref for o in p["objectifs"]}
    cours = ref["objectif_cours"]
    parties, cours_ids = {}, {}
    for p in parties_ref:
        pid = _partie(conn, sn["id"], p["numero"], seq, rapport,
                      None if est_sixieme() else (p.get("libelle") or "").strip())
        parties[p["numero"]] = pid
        code_c = f"{p['numero'] - 1}1"
        oid, etat = _objectif(conn, sn["id"], pid, code_c, cours, rapport, f"{seq}-{code_c}")
        cours_ids[p["numero"]] = oid
        etat = _seances(conn, oid, _seances_cours(lot, p["numero"]), etat,
                        f"{seq}-{code_c}", rapport)                      # v0.59.2
        rapport.obj(seq, f"{seq}-{code_c}", "Cours — " + cours["nom"])["objectif"] = etat

    approche: dict[int, list] = {n: [] for n in parties}
    vus: dict = {}
    cartes_vues: dict = {}                      # num de carte → objectif (v0.59.0)
    cartes_lot: dict = {}                       # id de carte → objectif du lot (v0.59.1)
    objectifs_ids: dict[str, str] = {}          # « S01-02 » → id (v0.52.2)
    codes_cours = {f"{seq}-{p['numero'] - 1}1": p["numero"] for p in parties_ref}
    for o in lot.get("objectifs", []):
        code = o.get("code", "")
        n_cours = numero_partie_cours(o, codes_cours)                 # v0.60.0 (B6)
        if n_cours is not None:
            importer_activites_cours(conn, lot, seq, o, n_cours, cours_ids[n_cours], vus,
                                     approche, rapport, figures)
            continue
        if code not in objs_ref:
            rapport.anomalie(f"{seq} : objectif inconnu {code!r} (absent de "
                             f"{Path(REFERENTIEL).name}), ignoré avec ses exercices")
            continue
        numero, d = objs_ref[code]
        if o.get("partie") not in (None, numero):
            rapport.anomalie(f"{code} : partie {o.get('partie')} dans le lot, {numero} dans le "
                             "référentiel (référentiel retenu)")
        if (o.get("intitule") or d["nom"]) != d["nom"]:
            rapport.infos.append(f"{code} : intitulé du lot différent du référentiel "
                                 "(référentiel retenu)")
        oid, etat = _objectif(conn, sn["id"], parties[numero], d["code"], d, rapport, code)
        etat = _seances(conn, oid, o.get("seances"), etat, code, rapport)   # v0.59.2
        etat = _sans_carte(conn, oid, o, etat, code, rapport)              # v0.60.1 (F4)
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
            mention = mention_lot(e, f"{seq} {sc}{cle[1]:02d}", rapport)   # v0.56.0
            _compter_mention(rapport, seq, mention)
            eid, etat_e = _exercice(conn, seq, sc, cle[1], e, marques, mention)
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
        importer_cartes_objectif(conn, seq, code, oid, o, rapport, cartes_vues,  # v0.59.0
                                 cartes_lot)
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
    figures |= importer_cartes_mentales(conn, lot, parties, rapport)     # v0.55.0
    aligner_rattachements_cartes(conn, seq, sn["id"], cartes_lot, rapport)  # v0.59.1
    figures |= importer_encarts(conn, lot, sn["id"], parties,             # v0.59.2
                                {c: (objs_ref[c][0], objectifs_ids.get(c)) for c in objs_ref},
                                rapport)
    return figures


# ── v0.60.0 (B6) — Activités de découverte sous l'objectif « Cours » ───────

def numero_partie_cours(o: dict, codes_cours: dict):
    """Numéro de partie si l'entrée d'objectif du lot désigne l'objectif
    « Cours » d'une partie : son code (« A1-01 », « A2-11 ») ou
    `"code": "Cours"` avec `"partie": n` ; None sinon."""
    code = (o.get("code") or "").strip()
    if code in codes_cours:
        return codes_cours[code]
    if code.lower() == "cours":
        try:
            n = int(o.get("partie"))
        except (TypeError, ValueError):
            return None
        return n if n in codes_cours.values() else None
    return None


def importer_activites_cours(conn, lot: dict, seq: str, o: dict, numero: int, cours_id: str,
                             vus: dict, approche: dict, rapport: "Rapport",
                             figures: set) -> None:
    """v0.60.0 (B6) — Activités de découverte (AE) rangées sous l'objectif
    « Cours » de la partie : rattachées à la partie (EA) et à l'objectif
    « Cours » (objectif_exos, série AE) ; le livret les place en ouverture de
    partie, avant le premier objectif (L1 : une activité qui n'est sous
    aucun objectif de capacité ouvre la partie). Seules les activités sont
    reçues sous « Cours » : exercices, fiche, cartes y sont signalés et
    ignorés."""
    code_c = f"{seq}-{numero - 1}1"
    for cle in ("exercices", "fiche_resume", "cartes_automatisme", "encarts"):
        if o.get(cle):
            rapport.anomalie(f"{code_c} (Cours) : clé « {cle} » ignorée (seules les activités "
                             "de découverte vont sous l'objectif « Cours »)")
    ro = rapport.obj(seq, code_c)
    act = []
    for a in o.get("activites", []) or []:
        cle = ("AE", int(a["num"]))
        if cle in vus:
            rapport.anomalie(f"{seq} AE{cle[1]:02d} en double, second ignoré")
            continue
        vus[cle] = code_c
        marques = marqueurs_lot(a, f"{seq} AE{cle[1]:02d}", rapport)
        _compter_marqueurs(rapport, seq, marques)
        eid, etat_a = _exercice(conn, seq, "AE", cle[1], a, marques)
        approche[numero].append(eid)
        act.append(eid)
        Rapport.compter(ro, "activités AE", etat_a)
        figures |= _figures(lot, a)
        rapport.journal["import"].append({"cle": f"{NIVEAU}/{seq}/AE{cle[1]:02d}", "id": eid,
                                          "objectif": code_c, "origine": a.get("origine", "")})
    if act:
        n = _ordonner(conn, "objectif_exos", {"objectif_id": cours_id, "serie": "AE"}, act)
        Rapport.compter(ro, "liens activité-Cours", "créés", n)
        # Une activité passée sous « Cours » quitte les objectifs de capacité
        # de la partie (sinon le livret l'afficherait encore sous leur bandeau).
        # Le contenu ne change pas : `mtime` rafraîchi pour que livret et
        # corrigés deviennent « périmés » (la péremption suit les atomes).
        for eid in act:
            cur = conn.execute("DELETE FROM objectif_exos WHERE exercice_id = ? AND serie = 'AE' "
                               "AND objectif_id <> ? AND objectif_id IN (SELECT o.id FROM "
                               "objectifs o WHERE o.partie_id = (SELECT partie_id FROM "
                               "objectifs WHERE id = ?))", (eid, cours_id, cours_id))
            if cur.rowcount and "mtime" in _cols(conn, "exercices"):
                conn.execute("UPDATE exercices SET mtime = ? WHERE id = ?", (_maintenant(), eid))
                Rapport.compter(ro, "activités passées sous « Cours »", "déplacées", 1)


# ── v0.60.0 (B7) — Variables des exercices paramétrés (clé `variables`) ─────

RE_VARIABLE_XINT = re.compile(r"\\xintdef(?:ii|float)?var\s*([A-Za-z_][A-Za-z0-9_]*)")


def controler_variables(lots: list[dict], rapport: "Rapport") -> None:
    """Variables xint déclarées par deux exercices des lots (même nom) :
    avertissement (les blocs sont émis avant chaque exercice ; un nom commun
    écraserait le tirage d'un autre exercice dans les corrigés). Un bloc
    `variables` sans déclaration xint est signalé aussi."""
    vus: dict = {}
    for lot in lots:
        seq = lot.get("sequence", "?")
        elements = []
        for o in lot.get("objectifs", []) or []:
            for e in (o.get("exercices", []) or []) + (o.get("activites", []) or []):
                elements.append((f"{seq} {e.get('serie', 'AE')}{int(e.get('num', 0)):02d}", e))
        for cle_lot, serie, _ in DOCUMENTS_LOT:
            for k, d in enumerate(lot.get(cle_lot, []) or [], start=1):
                elements.append((f"{seq} {serie}{k:02d}", d))
        for quoi, e in elements:
            v = e.get("variables") or ""
            if not v.strip():
                continue
            noms = RE_VARIABLE_XINT.findall(v)
            if not noms:
                rapport.avertissements.append(f"{quoi} : bloc « variables » sans déclaration "
                                              "\\xintdef…var")
            for nom in dict.fromkeys(noms):
                if nom in vus and vus[nom] != quoi:
                    rapport.avertissements.append(f"{quoi} : variable {nom} déjà déclarée par "
                                                  f"{vus[nom]}")
                vus.setdefault(nom, quoi)


# ── v0.59.2 — Séances d'un objectif (clés `seances`, `seances_cours`) ───────

_ABSENT = object()


def _seances_cours(lot: dict, numero: int):
    """Séances de l'objectif « Cours » de la partie `numero` d'après la clé
    `seances_cours` du lot (nombre pour toutes les parties, ou dictionnaire
    par numéro de partie) ; _ABSENT sans clé (ou partie non citée)."""
    if "seances_cours" not in lot:
        return _ABSENT
    v = lot["seances_cours"]
    if isinstance(v, dict):
        return v.get(str(numero), v.get(numero, _ABSENT))
    return v


def _seances(conn, oid: str, valeur, etat: str, etiquette: str, rapport: "Rapport") -> str:
    """Écrit `objectifs.nb_seances` si le lot donne une valeur (clé `seances`).
    Clé absente (None ou _ABSENT) : rien ne change (saisie de l'atelier gardée).
    Retourne l'état de l'objectif (« mis à jour » si les séances changent)."""
    if valeur is None or valeur is _ABSENT:
        return etat
    try:
        nb = float(str(valeur).replace(",", "."))
        if nb < 0 or nb != nb:
            raise ValueError
    except (TypeError, ValueError):
        rapport.anomalie(f"{etiquette} : séances {valeur!r} invalides (nombre ≥ 0 attendu), "
                         "ignorées")
        return etat
    avant = float(conn.execute("SELECT nb_seances FROM objectifs WHERE id=?",
                               (oid,)).fetchone()[0] or 0)
    if avant == nb:
        return etat
    conn.execute("UPDATE objectifs SET nb_seances=? WHERE id=?", (nb, oid))
    rapport.seances.append(f"{etiquette} : {_fmt_nb(avant)} → {_fmt_nb(nb)} séance(s)")
    return "mis à jour" if etat == "inchangé" else etat


def _sans_carte(conn, oid: str, o: dict, etat: str, etiquette: str,
                rapport: "Rapport") -> str:
    """v0.60.1 (F4) — Propriété « pas de carte voulue » de l'objectif (clé
    `"sans_carte": true` de l'objectif du lot ; clé absente : valeur gardée).
    Elle lève l'avertissement « objectif sans carte » de la validation."""
    if "sans_carte" not in o:
        return etat
    v = o["sans_carte"]
    if not isinstance(v, bool):
        rapport.anomalie(f"{etiquette} : sans_carte {v!r} invalide (true ou false attendu), "
                         "ignoré")
        return etat
    from services.cartes_partie import poser_sans_carte
    if not poser_sans_carte(conn, oid, v):
        return etat
    rapport.seq(etiquette.split("-")[0])["lignes"].append(
        f"{etiquette} : " + ("sans carte voulue" if v else "carte attendue (sans_carte retiré)"))
    return "mis à jour" if etat == "inchangé" else etat


def _fmt_nb(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x).replace(".", ",")


# ── v0.59.2 — Encarts du livret (clé `encarts`) ─────────────────────────────

def importer_encarts(conn, lot: dict, sn_id: str, parties: dict, objectifs: dict,
                     rapport: "Rapport") -> set:
    """Clé facultative `encarts` d'un objectif et du lot (encarts de partie),
    format `lot6e/FORMAT_ENCARTS.md`. `parties` : {numéro: partie_id} ;
    `objectifs` : {« A1-02 »: (numéro de partie, objectif_id)}. Le lot fait
    foi dès qu'il porte la clé quelque part (services/encarts.aligner) ; sans
    clé, rien n'est touché. Retourne les figures utilisées (aucune attendue)."""
    from services import encarts as enc
    seq = lot["sequence"]
    porte = "encarts" in lot or any("encarts" in o for o in lot.get("objectifs", []))
    if not porte:
        return set()
    voulus, compte, figures = [], {}, set()
    rangs: dict = {}

    def _ajouter(src: dict, partie_id: str, objectif_id, quoi: str):
        entree, err, av = enc.controler(src, objectif_id is not None)
        if err:
            rapport.anomalie(f"{quoi} non importé : {'; '.join(err)}")
            return
        for a in av:
            rapport.infos.append(f"{quoi} : {a}")
        exo_id = ""
        if entree["position"] == "apres_exercice":
            m = enc._RE_EXO.match(entree["exercice"])
            r = conn.execute("SELECT id FROM exercices WHERE niveau=? AND sequence=? AND "
                             "serie_code=? AND num=?",
                             (NIVEAU, seq, m.group(1), int(m.group(2)))).fetchone()
            if r is None:
                rapport.anomalie(f"{quoi} non importé : exercice {entree['exercice']} absent "
                                 f"de {NIVEAU}/{seq}")
                return
            exo_id = r["id"]
        place = (partie_id, objectif_id or "", entree["position"], entree["exercice"])
        rangs[place] = rangs.get(place, 0) + 1
        voulus.append({**entree, "partie_id": partie_id, "objectif_id": objectif_id,
                       "exercice_id": exo_id, "ordre": rangs[place]})
        compte[entree["type"]] = compte.get(entree["type"], 0) + 1
        figures.update(_figures(lot, {"latex": entree["texte"] + entree["solution"]}))

    for o in lot.get("objectifs", []):
        code = o.get("code", "")
        if code not in objectifs or not o.get("encarts"):
            continue
        numero, oid = objectifs[code]
        if oid is None or numero not in parties:
            continue
        for k, src in enumerate(o["encarts"], start=1):
            _ajouter(src if isinstance(src, dict) else {}, parties[numero], oid,
                     f"{code} encart n°{k}")
    for k, src in enumerate(lot.get("encarts") or [], start=1):
        src = src if isinstance(src, dict) else {}
        try:
            numero = int(src.get("partie"))
        except (TypeError, ValueError):
            rapport.anomalie(f"{seq} encart de partie n°{k} : partie {src.get('partie')!r} "
                             "invalide, non importé")
            continue
        if numero not in parties:
            rapport.anomalie(f"{seq} encart de partie n°{k} : partie {numero} absente du "
                             "référentiel, non importé")
            continue
        _ajouter(src, parties[numero], None, f"{seq} encart de partie {numero} n°{k}")
    res = enc.aligner(conn, sn_id, NIVEAU, seq, voulus)
    for e in res["retires"]:
        rapport.journal.setdefault("retraits", []).append(
            {"quoi": "encart", "table": enc.TABLE, "ligne": e})
    rapport.seq(seq)["lignes"].append(
        "encarts : " + (", ".join(f"{enc.TYPES[t]} {n}" for t, n in compte.items()) or "aucun")
        + f" — créés {res['crees']}, mis à jour {res['maj']}, inchangés {res['inchanges']}, "
          f"retirés {len(res['retires'])}")
    rapport.encarts[seq] = {"crees": res["crees"], "maj": res["maj"],
                            "inchanges": res["inchanges"], "retires": len(res["retires"])}
    return figures


# ── v0.55.0 — Cartes mentales de partie (clé `cartes_mentales`) ─────────────

def importer_cartes_mentales(conn, lot: dict, parties: dict, rapport: Rapport) -> set:
    r"""Clé facultative `cartes_mentales` d'un lot S :
    `[{"partie": n, "titre": "…", "latex": "\begin{seqCarteMentaleSix}…"}]`
    (SP/lot6e/FORMAT_CARTE_MENTALE.md). Une carte par partie, rangée dans
    `cartes_mentales` (services/cartes_mentales.py). Contrôles : partie
    existante (référentiel), un seul environnement `seqCarteMentaleSix`, au
    moins une branche, macros `\seq…` connues du module ; une carte refusée
    est signalée en anomalie et n'est pas importée. Idempotent ; une carte
    validée dans l'atelier n'est jamais modifiée (signalé). Une partie sans
    carte est signalée en information. Retourne les figures utilisées."""
    from services import cartes_mentales as cm
    seq = lot["sequence"]
    sr = rapport.seq(seq)
    figures: set = set()
    entrees = lot.get("cartes_mentales") or []
    vues: set = set()
    compte: "OrderedDict[str, int]" = OrderedDict()
    for k, src in enumerate(entrees, start=1):
        try:
            numero = int(src.get("partie"))
        except (TypeError, ValueError):
            rapport.anomalie(f"{seq} carte mentale n°{k} : partie {src.get('partie')!r} "
                             "invalide, ignorée")
            continue
        quoi = f"{seq} carte mentale de la partie {numero}"
        if numero not in parties:
            rapport.anomalie(f"{quoi} : partie absente du référentiel "
                             f"(parties {', '.join(map(str, sorted(parties)))}), ignorée")
            continue
        if numero in vues:
            rapport.anomalie(f"{quoi} en double, seconde ignorée")
            continue
        vues.add(numero)
        latex = src.get("latex") or ""
        erreurs, avert = cm.controler_latex(latex)
        if erreurs:
            rapport.anomalie(f"{quoi} non importée : {'; '.join(erreurs)}")
            continue
        for a in avert:
            rapport.infos.append(f"{quoi} : {a}")
        cm.migrer(conn)
        _cid, etat = cm.enregistrer(conn, parties[numero], src.get("titre") or "", latex)
        compte[etat] = compte.get(etat, 0) + 1
        sr["lignes"].append(f"carte mentale partie {numero} « {(src.get('titre') or '')[:50]} »"
                            f" : {etat} ({cm.nb_branches(latex)} branches, "
                            f"{latex.count(chr(92) + 'seqACompleter')} trous)")
        if etat == "validée, non modifiée":
            rapport.anomalie(f"{quoi} validée dans l'atelier, non modifiée")
        figures |= _figures(lot, {"latex": latex})
    sans = sorted(n for n in parties if n not in vues)
    if sans and not lot.get("_mer"):
        rapport.infos.append(f"{seq} : partie(s) sans carte mentale dans le lot : "
                             + ", ".join(map(str, sans)))
    if compte:
        rapport.cartes_mentales[seq] = compte
    return figures


# ── v0.59.0 — Cartes d'automatisme d'un objectif (clé `cartes_automatisme`) ──

NIVEAUX_CREATION = ("N09", "N10", "N11", "N12")
_CHAMPS_CARTE = ("titre", "type_pedago", "type_tech", "recto", "verso", "variables",
                 "niveau_creation")


def _valeurs_carte(src: dict, quoi: str, rapport: Rapport) -> dict | None:
    """Valeurs d'une carte du lot, contrôlées ; None = carte refusée (signalée)."""
    from services.cartes_automatisme import TYPES_PEDAGO, TYPES_TECH
    try:
        num = int(src.get("num"))
    except (TypeError, ValueError):
        rapport.anomalie(f"{quoi} : numéro {src.get('num')!r} invalide, carte ignorée")
        return None
    if not 0 < num < 100:
        rapport.anomalie(f"{quoi} : numéro {num} hors de 1 à 99, carte ignorée")
        return None
    v = {"num": num,
         "titre": (src.get("titre") or "").strip(),
         "type_pedago": src.get("type_pedago") or "definition",
         "type_tech": src.get("type_tech") or "fixe",
         "recto": src.get("recto") or "", "verso": src.get("verso") or "",
         "variables": src.get("variables") or "",
         "niveau_creation": (src.get("niveau_creation") or NIVEAU).strip().upper()}
    if v["type_pedago"] not in TYPES_PEDAGO:
        rapport.anomalie(f"{quoi} : type pédagogique {v['type_pedago']!r} inconnu (attendu "
                         f"{', '.join(TYPES_PEDAGO)}), carte ignorée")
        return None
    if v["type_tech"] not in TYPES_TECH:
        rapport.anomalie(f"{quoi} : type technique {v['type_tech']!r} inconnu (attendu "
                         f"{', '.join(TYPES_TECH)}), carte ignorée")
        return None
    if v["niveau_creation"] not in NIVEAUX_CREATION:
        rapport.anomalie(f"{quoi} : niveau de création {v['niveau_creation']!r} inconnu "
                         f"(attendu {', '.join(NIVEAUX_CREATION)}), lu {NIVEAU}")
        v["niveau_creation"] = NIVEAU
    # Mêmes règles que la validation d'une carte (services/cartes_automatisme) :
    # signalées dès l'import, la carte est gardée « en cours ».
    if not v["recto"].strip() or not v["verso"].strip():
        rapport.anomalie(f"{quoi} : recto ou verso vide (la carte ne pourra pas être validée)")
    if v["type_tech"] == "parametree" and not v["variables"].strip():
        rapport.anomalie(f"{quoi} : carte paramétrée sans variables (la carte ne pourra pas "
                         "être validée)")
    return v


def importer_cartes_objectif(conn, seq: str, code: str, objectif_id: str, o: dict,
                             rapport: Rapport, vues: dict, lot_cartes: dict | None = None
                             ) -> None:
    """v0.59.0 (D3) — Clé facultative `cartes_automatisme` d'un objectif du lot :
    `[{"num": 1, "titre": "…", "type_pedago": "calcul", "type_tech": "fixe",
    "recto": "…", "verso": "…", "variables": "", "niveau_creation": "N11",
    "origine": "N11/A1/CA8"}]`.

    Carte repérée par (niveau, séquence, num) : créée « en cours », mise à jour
    si elle a changé (jamais une carte validée : signalé), rattachée à
    l'objectif par `objectif_cartes` (en tête, dans l'ordre du lot ; les liens
    de l'auteur restent). `niveau_creation` : niveau où la notion est un
    objectif (N11 : carte de 4e ; N10 : automatisme de 5e écrit en 4e) ; la
    partie se déduit de l'objectif. Aucune carte n'entre dans le livret de
    séquence (décision du 16 novembre) ; le document de rituels viendra en
    v0.60. `origine` : rapportée dans le journal.

    v0.59.1 — `lot_cartes` (facultatif) reçoit {id de carte: (objectif_id,
    code)} des cartes citées, pour `aligner_rattachements_cartes`."""
    entrees = o.get("cartes_automatisme") or []
    if not entrees:
        return
    from services import fiches_cycle4 as fc4
    fc4.migrer(conn)
    compte = rapport.cartes_automatisme.setdefault(seq, OrderedDict())
    ids = []
    for k, src in enumerate(entrees, start=1):
        quoi = f"{seq} carte d'automatisme n°{src.get('num', k)} ({code})"
        v = _valeurs_carte(src, quoi, rapport)
        if v is None:
            continue
        if v["num"] in vues:
            rapport.anomalie(f"{NIVEAU}/{seq}/CA{v['num']} en double ({vues[v['num']]} et "
                             f"{code}), seconde ignorée")
            continue
        vues[v["num"]] = code
        r = conn.execute("SELECT * FROM cartes_automatisme WHERE niveau=? AND sequence=? AND "
                         "num=?", (NIVEAU, seq, v["num"])).fetchone()
        vals = {c: v[c] for c in _CHAMPS_CARTE}
        if r is None:
            cid = f"ca_{uuid.uuid4().hex[:12]}"
            conn.execute("INSERT INTO cartes_automatisme (id, niveau, sequence, num, type_pedago, "
                         "type_tech, titre, recto, verso, variables, niveau_creation, etat_code, "
                         "ordre, mtime) VALUES (?,?,?,?,?,?,?,?,?,?,?,'en_cours',?,?)",
                         (cid, NIVEAU, seq, v["num"], v["type_pedago"], v["type_tech"],
                          v["titre"], v["recto"], v["verso"], v["variables"],
                          v["niveau_creation"], v["num"], _maintenant()))
            etat = "créée"
        else:
            cid = r["id"]
            if all((r[c] or "") == (vals[c] or "") for c in _CHAMPS_CARTE):
                etat = "inchangée"
            elif r["etat_code"] == "valide":
                autres = [c for c in _CHAMPS_CARTE if c != "niveau_creation"
                          and (r[c] or "") != (vals[c] or "")]
                if (r["niveau_creation"] or "") != v["niveau_creation"]:
                    # v0.60.0 (F3) — le niveau de création se corrige même sur une
                    # carte validée : il ne change pas le rendu de la carte (mtime
                    # gardé, aucun document périmé) mais décide « nouvelle » ou
                    # « réactivée » dans le document de rituels.
                    conn.execute("UPDATE cartes_automatisme SET niveau_creation=? WHERE id=?",
                                 (v["niveau_creation"], cid))
                    rapport.avertissements.append(
                        f"{NIVEAU}/{seq}/CA{v['num']} (validée) : niveau de création corrigé "
                        f"{r['niveau_creation'] or '(vide)'} → {v['niveau_creation']}")
                    etat = "niveau de création corrigé"
                else:
                    etat = "validée, non modifiée"
                if autres:
                    etat = "validée, non modifiée"
                    rapport.anomalie(f"{NIVEAU}/{seq}/CA{v['num']} validée dans l'atelier : contenu "
                                     "du lot non appliqué")
            else:
                conn.execute("UPDATE cartes_automatisme SET type_pedago=?, type_tech=?, titre=?, "
                             "recto=?, verso=?, variables=?, niveau_creation=?, mtime=? "
                             "WHERE id=?", (v["type_pedago"], v["type_tech"], v["titre"],
                                            v["recto"], v["verso"], v["variables"],
                                            v["niveau_creation"], _maintenant(), cid))
                etat = "mise à jour"
        compte[etat] = compte.get(etat, 0) + 1
        ids.append(cid)
        if lot_cartes is not None:
            lot_cartes[cid] = (objectif_id, code)
        rapport.journal["import"].append({"cle": f"{NIVEAU}/{seq}/CA{v['num']}", "id": cid,
                                          "objectif": code, "carte": True,
                                          "niveau_creation": v["niveau_creation"],
                                          "origine": src.get("origine", "")})
    if ids:
        n = _lier_cartes(conn, objectif_id, ids)
        ro = rapport.obj(seq, code)
        Rapport.compter(ro, "cartes d'automatisme", "liées", len(ids))
        if n:
            Rapport.compter(ro, "liens objectif-carte", "créés", n)


def aligner_rattachements_cartes(conn, seq: str, sn_id: str, lot_cartes: dict,
                                 rapport: Rapport) -> None:
    """v0.59.1 — Alignement des rattachements (signalement du 17 novembre :
    6 cartes de coordonnées de D1 déplacées de D1-02 vers D1-05 dans le lot
    restaient aussi sur D1-02 après réimport, `_lier_cartes` n'ajoutant que
    des liens).

    Le lot fait foi pour les cartes qu'il cite : une carte citée sous
    l'objectif O perd son lien vers tout **autre objectif de la même
    séquence-niveau** que le lot ne lui donne pas. Restent intouchés : les
    liens vers des objectifs d'autres séquences, les liens des cartes que le
    lot ne cite pas (ajoutés par l'auteur), et tout lien d'une carte validée
    ou d'un objectif validé (séquence-niveau validée ; les objectifs n'ont pas
    d'état propre) — signalés en anomalie. L'essai à blanc liste les retraits
    (même code, base en mémoire) ; chaque lien retiré est copié dans
    `rapport.journal["retraits"]` (restauration par simple INSERT)."""
    if not lot_cartes:
        return
    sn_valide = (conn.execute("SELECT etat_code FROM sequences_par_niveau WHERE id = ?",
                              (sn_id,)).fetchone() or [""])[0] == "valide"
    for cid, (oid_lot, code_lot) in lot_cartes.items():
        autres = conn.execute(
            "SELECT oc.*, o.code AS code_obj, c.num AS num_carte, c.titre AS titre_carte, "
            "c.etat_code AS etat_carte FROM objectif_cartes oc "
            "JOIN objectifs o ON o.id = oc.objectif_id "
            "JOIN sequence_parties p ON p.id = o.partie_id "
            "JOIN cartes_automatisme c ON c.id = oc.carte_id "
            "WHERE oc.carte_id = ? AND p.sequence_par_niveau_id = ? AND oc.objectif_id <> ? "
            "ORDER BY o.code", (cid, sn_id, oid_lot)).fetchall()
        for r in autres:
            quoi = (f"{NIVEAU}/{seq}/CA{r['num_carte']} « {r['titre_carte']} » : lien vers "
                    f"{seq}-{r['code_obj']}")
            if r["etat_carte"] == "valide" or sn_valide:
                rapport.anomalie(f"{quoi} absent du lot (carte sous {code_lot}) mais "
                                 + ("carte validée" if r["etat_carte"] == "valide"
                                    else "séquence validée") + " : lien gardé")
                continue
            ligne = {k: r[k] for k in ("objectif_id", "carte_id", "ordre", "mtime")}
            rapport.journal.setdefault("retraits", []).append({
                "quoi": "lien_objectif_carte", "cle": f"{NIVEAU}/{seq}/CA{r['num_carte']}",
                "objectif": f"{seq}-{r['code_obj']}", "objectif_cartes": ligne})
            conn.execute("DELETE FROM objectif_cartes WHERE objectif_id = ? AND carte_id = ?",
                         (r["objectif_id"], cid))
            rapport.cartes_alignement.append(f"{quoi} retiré (le lot la place sous "
                                             f"{code_lot})")
            Rapport.compter(rapport.obj(seq, f"{seq}-{r['code_obj']}"),
                            "liens objectif-carte", "retirés (alignement sur le lot)", 1)


def _lier_cartes(conn, objectif_id: str, ids: list[str]) -> int:
    """Liens objectif_cartes : cartes du lot en tête (ordre du lot), celles de
    l'auteur ensuite. Retourne le nombre de liens créés."""
    actuels = [r[0] for r in conn.execute("SELECT carte_id FROM objectif_cartes WHERE "
                                          "objectif_id=? ORDER BY ordre, carte_id",
                                          (objectif_id,))]
    voulu = ids + [i for i in actuels if i not in ids]
    crees = 0
    for k, cid in enumerate(voulu, start=1):
        if cid in actuels:
            conn.execute("UPDATE objectif_cartes SET ordre=? WHERE objectif_id=? AND carte_id=? "
                         "AND ordre<>?", (k, objectif_id, cid, k))
        else:
            conn.execute("INSERT INTO objectif_cartes (objectif_id, carte_id, ordre) "
                         "VALUES (?,?,?)", (objectif_id, cid, k))
            crees += 1
    return crees


def copier_figures(lots: list[dict], noms_par_seq: dict, images: Path, rapport: Rapport,
                   ecrire: bool) -> None:
    for lot in lots:
        d = lot["_dossier"] / "figures"
        for nom in sorted(noms_par_seq.get(lot["sequence"], ())):
            src = d / nom
            dst = images / nom
            if not src.is_file():
                # v0.60.2 — image d'origine d'un exercice repris de la base
                # (\includegraphics avec son nom de fichier, ex.
                # N11S04E07_enonce.png) : le lot ne la fournit pas, elle est
                # déjà dans images\ de l'appli → signalée, pas une anomalie.
                if dst.is_file():
                    rapport.figures.append(f"{nom} : déjà présente dans images "
                                           "(non fournie par le lot)")
                else:
                    rapport.anomalie(f"{lot['sequence']} : figure manquante {nom}")
                continue
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


def _cle_titre(titre: str) -> str:
    """v0.54.1 (D-DOUBLON) — titre comparé sans casse ni espaces en trop."""
    return re.sub(r"\s+", " ", (titre or "").replace("\\,", " ")).strip().casefold()


def titres_documents_en_double(lots: list[dict]) -> list[str]:
    """v0.54.1 (D-DOUBLON) — titres portés par plusieurs documents des lots
    (TP, AC, AT, évaluations et tests courts, lots S et M), une ligne par
    titre : « titre » : S04 TP01, S12 TP01. Les sujets A et B d'une même
    évaluation (même séquence, un A et un B au plus) ne sont pas des doublons.
    Une entrée `evaluations_retirees` n'est pas un document du lot."""
    vus: "OrderedDict[str, list]" = OrderedDict()
    for lot in lots:
        seq = lot.get("sequence", "?")
        for cle_lot, serie, _ in DOCUMENTS_LOT:
            for k, src in enumerate(lot.get(cle_lot, []) or [], start=1):
                vus.setdefault(_cle_titre(src.get("titre", "")), []).append(
                    (seq, f"{serie}{k:02d}", src.get("titre", "")))
        for ev in (lot.get("evaluations", []) or []) + (lot.get("tests_courts", []) or []):
            sujet = (ev.get("sujet") or "").strip().upper()
            vus.setdefault(_cle_titre(ev.get("titre", "")), []).append(
                (seq, f"évaluation{' sujet ' + sujet if sujet else ''}", ev.get("titre", "")))
    out = []
    for cle, liste in vus.items():
        if not cle or len(liste) < 2:
            continue
        sujets = [q for _, q, _ in liste]
        paire = (len({s for s, _, _ in liste}) == 1 and len(liste) == 2
                 and sorted(sujets) == ["évaluation sujet A", "évaluation sujet B"])
        if not paire:
            out.append(f"« {liste[0][2]} » : " + ", ".join(f"{s} {q}" for s, q, _ in liste))
    return out


# v0.53.2 — `\foreach \x in {…} corps;` sans accolades autour du corps : dans
# l'argument d'une macro (corrigé rendu dans \seqLocExplication{…}), le « ; »
# est déjà lu actif (babel français) et pgffor ne trouve plus la fin du corps
# (« Paragraph ended before \pgffor@next was complete »). Cas réel : M04 AC02.
RE_FOREACH_SANS_ACCOLADES = re.compile(
    r"\\foreach\s*\\\w+(?:\s*/\s*\\\w+)*\s+in\s*\{[^{}]*\}(?!\s*\{)")
CHAMPS_EN_ARGUMENT = ("corrige", "remed_corrige")


def foreach_en_argument(lots: list[dict]) -> list[str]:
    r"""v0.53.2 — éléments dont un corrigé (rendu dans l'argument de
    \seqLocExplication) a un \foreach sans accolades autour de son corps."""
    out = []

    def parcourir(o, chemin):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in CHAMPS_EN_ARGUMENT and isinstance(v, str) \
                        and RE_FOREACH_SANS_ACCOLADES.search(v):
                    out.append(f"{chemin} {o.get('titre') or ''} ({k})".strip())
                elif k != "_dossier":
                    parcourir(v, chemin)
        elif isinstance(o, list):
            for v in o:
                parcourir(v, chemin)

    for lot in lots:
        parcourir(lot, lot.get("sequence", "?"))
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
            contenu = {"titre": src.get("titre", ""), "enonce": src.get("latex", ""),
                       "corrige": src.get("corrige", "")}
            if "variables" in src:                                   # v0.60.0 (B7)
                contenu["variables"] = src.get("variables") or ""
            eid, etat = _exercice(conn, seq, serie, k, contenu, marques)
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
# v0.57.0 — aussi `A1-nn` (codes de thème).
RE_ETIQUETTE_EVAL = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*pts?\s*---\s*([SM]\d\d-\d\d|"
                               + cs.MOTIF_THEME + r"-\d\d)\s*$")


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
    """{titre: {"A": évaluation, "B": évaluation}} dans l'ordre du lot.

    v0.60.0 (E6) — aussi les entrées de la clé `tests_courts` (même format
    que `evaluations`), après les évaluations."""
    out: "OrderedDict[str, dict]" = OrderedDict()
    for cle in ("evaluations", "tests_courts"):
        for ev in lot.get(cle, []) or []:
            out.setdefault(ev.get("titre", ""), {})[(ev.get("sujet") or "A").upper()] = ev
    return out


def type_evaluation_lot(lot: dict, titre: str) -> str:
    """v0.60.0 (E6, décision T1) — 'test_court' pour une entrée de la clé
    `tests_courts` ou une évaluation dont le titre commence par « Test
    court » ; 'evaluation' sinon."""
    from services.evaluations_v2 import est_titre_test_court
    if any(ev.get("titre", "") == titre for ev in lot.get("tests_courts", []) or []):
        return "test_court"
    return "test_court" if est_titre_test_court(titre) else "evaluation"


def controler_evaluation(seq: str, titre: str, type_ev: str, exos: list[dict],
                         rapport: "Rapport") -> None:
    """v0.60.0 — Règles du barème, avertissements seulement (B10, E6) :
    bonus de 1 point des évaluations du cycle 4 (une évaluation qui a un
    bonus d'un autre montant, ou pas de bonus, est signalée).

    v0.60.2 (décisions 16 et 17) — plus aucun contrôle pour un test court :
    son total est la somme des points de ses questions (QCM, 1 pt par carte
    d'automatisme), sans bonus ; rien n'est signalé en 6e (bonus de 2 pts)."""
    if type_ev == "test_court":
        return
    bonus = sum(x["points"] for x in exos if x["bonus"])
    quoi = f"{seq} évaluation « {titre} »"
    if bonus != 1 and NIVEAU in NIVEAUX_BONUS_1:
        # B10b, v0.60.1 (D16, décision du 18 novembre) — bonus de 2 pts en 6e
        # (accepté, rien n'est signalé) ; 1 pt sur tout le cycle 4 : une
        # évaluation de 5e, 4e ou 3e dont le bonus n'est pas 1 (bonus absent
        # compris) est signalée.
        rapport.avertissements.append(
            f"{quoi} : " + (f"bonus de {bonus:g} pt{'s' if bonus >= 2 else ''}" if bonus
                            else "pas de bonus")
            + " (règle : 1 pt)")


def controler_tests_courts_parties(conn, seq: str, sn_id: str | None, lot: dict,
                                   plan: list, rapport: "Rapport") -> None:
    """v0.60.0 (E6) — Un test court par partie : avertissement pour une
    partie sans test court ou qui en a plusieurs (seulement quand le lot
    porte au moins un test court ; la partie d'un test court est celle de ses
    objectifs)."""
    tests = [(t, exos) for t, _, exos in plan if type_evaluation_lot(lot, t) == "test_court"]
    if not tests or sn_id is None:
        return
    num_partie = {}
    for code, numero in conn.execute(
            "SELECT o.code, p.numero FROM objectifs o JOIN sequence_parties p ON "
            "p.id = o.partie_id WHERE p.sequence_par_niveau_id = ?", (sn_id,)):
        num_partie[f"{seq}-{code}"] = numero
    par_partie: dict = {}
    for t, exos in tests:
        nums = sorted({num_partie.get(x["objectif"]) for x in exos if not x["bonus"]}
                      - {None})
        if len(nums) > 1:
            rapport.avertissements.append(f"{seq} test court « {t} » : objectifs de plusieurs "
                                          f"parties ({', '.join(map(str, nums))})")
        for n in nums[:1]:
            par_partie.setdefault(n, []).append(t)
    for (n,) in conn.execute("SELECT numero FROM sequence_parties WHERE "
                             "sequence_par_niveau_id = ? ORDER BY numero", (sn_id,)):
        if n not in par_partie:
            rapport.avertissements.append(f"{seq} partie {n} : pas de test court dans le lot")
        elif len(par_partie[n]) > 1:
            rapport.avertissements.append(f"{seq} partie {n} : {len(par_partie[n])} tests "
                                          "courts (un par partie)")


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
    # v0.60.0 (T3, correctif B8) — part de la durée de l'évaluation (10 min
    # par objectif, ou durée réglée) des objectifs de la partie 1.
    from services import evaluations_v2 as ev2
    par = [[], []]
    for x, m in zip(exos, marques):
        par[mq.partie_de(m) - 1].append({"objectif": "" if x["bonus"] else x["objectif"],
                                         "points": x["points"]})
    n_obj = len({x["objectif"] for x in exos if not x["bonus"]})
    duree_ev = ev2.DUREE_PAR_OBJECTIF * max(1, n_obj)
    if ev_id is not None and ev2.colonnes_presentes(conn) and \
            ev2.duree_reglee(conn, ev_id) is not None:
        duree_ev = int(ev2.duree_reglee(conn, ev_id))
    duree = ev2.duree_partie1_par_objectifs(par, duree_ev)
    reglee = None
    if ev_id is not None and mq.colonne_duree_presente(conn):
        r = conn.execute("SELECT duree_partie1 FROM evaluations WHERE id = ?",
                         (ev_id,)).fetchone()
        reglee = r[0] if r else None
    def ex(nums):
        return "ex. " + (" et ".join([", ".join(map(str, nums[:-1])), str(nums[-1])])
                         if len(nums) > 1 else str(nums[0]))
    def pts(i):
        return f"{points[i]:g} pt{'s' if points[i] >= 2 else ''}" + (" + bonus" if bonus[i] else "")
    d = (f"{reglee} min réglée(s) dans l'atelier, calcul {duree} min" if reglee is not None
         else f"{duree} min")
    return (f"en deux parties ({duree_ev} min) : partie 1 sans calculatrice {ex(parties[0])} "
            f"({pts(0)}, {d}), partie 2 calculatrice autorisée {ex(parties[1])} ({pts(1)}, "
            f"{max(0, duree_ev - (reglee if reglee is not None else duree))} min)")


# v0.60.2 — Barème QCM d'un exercice d'évaluation importé. La validation d'une
# évaluation notée exige, pour un exercice QCM (`type_format = 'qcm'`, énoncé
# avec `\begin{seqQcm}`), les trois champs bonne réponse / réponse partielle /
# mauvaise réponse (services/evaluations.py, `bareme_qcm_manquant`) ; l'import
# ne posait que `bareme_points`. Bonne réponse = points d'une question (points
# de l'exercice / nombre de `\seqQcmQuestion`, 1 pt par défaut), partielle et
# mauvaise = 0. `bareme_points` (total de l'exercice) reste celui du lot : c'est
# lui que lisent les sujets, le barème par objectif et les totaux.
RE_QCM_QUESTION = re.compile(r"\\seqQcmQuestion(?![A-Za-z@])")
PAS_BAREME_QCM = 0.5                     # pas des champs QCM du module Évaluations


def bareme_qcm(enonce: str, points: float) -> tuple[tuple[float, float, float], str]:
    """((bonne réponse, partielle, mauvaise), motif) pour un exercice QCM de
    `points` points. Motif non vide quand le défaut (1 pt par question) est
    pris faute de pouvoir répartir les points sur les questions."""
    n = len(RE_QCM_QUESTION.findall(enonce or ""))
    if n:
        q = float(points) / n
        if abs(q / PAS_BAREME_QCM - round(q / PAS_BAREME_QCM)) < 1e-9 and q > 0:
            return (q, 0.0, 0.0), ""
        return (1.0, 0.0, 0.0), f"{points:g} pts pour {n} question(s) : 1 pt par question"
    return (1.0, 0.0, 0.0), "questions non repérées (\\seqQcmQuestion) : 1 pt par question"


def bareme_qcm_exercice(conn, eid: str, points: float) -> "tuple[tuple, str] | tuple[None, str]":
    """Barème QCM de l'exercice `eid` tel qu'il est en base (type et énoncé
    lus en base : un exercice validé non réécrit garde les siens) ; (None, '')
    pour un exercice standard."""
    cols = _cols(conn, "exercices")
    r = conn.execute("SELECT * FROM exercices WHERE id = ?", (eid,)).fetchone()
    if r is None:
        return None, ""
    tf = r["type_format"] if "type_format" in cols else _deduire_type_format(r["enonce"] or "")
    if (tf or "standard") != "qcm":
        return None, ""
    return bareme_qcm(r["enonce"] or "", points)


CHAMPS_QCM = ("bareme_qcm_ok", "bareme_qcm_partiel", "bareme_qcm_ko")


def _poser_exercices_evaluation(conn, ev_id: str, voulus: list[tuple]) -> int:
    """Exercices importés (id, points[, barème QCM]) en tête, dans l'ordre du
    lot ; ceux que l'auteur a ajoutés passent après. Retourne le nombre de
    changements.

    v0.60.2 — troisième élément facultatif : (bonne, partielle, mauvaise)
    pour un exercice QCM, écrit dans `bareme_qcm_ok/partiel/ko` et comparé
    comme les points (un réimport pose les champs manquants) ; None ou
    absent : ces champs ne sont pas touchés (exercice standard)."""
    lignes = conn.execute(
        "SELECT exercice_id, bareme_points, " + ", ".join(CHAMPS_QCM) + " FROM "
        "evaluation_exercices WHERE evaluation_id = ? ORDER BY ordre", (ev_id,)).fetchall()
    actuels = [(r["exercice_id"], r["bareme_points"]) for r in lignes]
    qcm_actuels = {r["exercice_id"]: tuple(r[c] for c in CHAMPS_QCM) for r in lignes}
    voulus = [tuple(v) + (None,) * (3 - len(v)) for v in voulus]
    ids = [i for i, _, _ in voulus]
    ordre = ids + [i for i, _ in actuels if i not in ids]
    pts = dict(actuels)
    pts.update({i: p for i, p, _ in voulus})
    qcm = dict(qcm_actuels)
    qcm.update({i: tuple(b) for i, _, b in voulus if b is not None})
    if [(i, pts[i]) for i in ordre] == actuels and all(
            qcm.get(i) == qcm_actuels.get(i) for i in ordre):
        return 0
    conn.execute("UPDATE evaluation_exercices SET ordre = -ordre - 1000 WHERE evaluation_id = ?",
                 (ev_id,))
    deja = {i for i, _ in actuels}
    for k, i in enumerate(ordre, start=1):
        b = qcm.get(i) or (None, None, None)
        if i in deja:
            conn.execute("UPDATE evaluation_exercices SET ordre = ?, bareme_points = ?, "
                         + ", ".join(c + " = ?" for c in CHAMPS_QCM)
                         + " WHERE evaluation_id = ? AND exercice_id = ?",
                         (k, pts[i], *b, ev_id, i))
        else:
            conn.execute("INSERT INTO evaluation_exercices (evaluation_id, exercice_id, ordre, "
                         "bareme_points, " + ", ".join(CHAMPS_QCM) + ") VALUES (?,?,?,?,?,?,?)",
                         (ev_id, i, k, pts[i], *b))
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
    retires_ev: list = []                                           # v0.60.1 (R6)
    liens: "OrderedDict[tuple, list]" = OrderedDict()
    for titre, paire, exos in plan:
        type_ev = type_evaluation_lot(lot, titre)                    # v0.60.0 (E6)
        controler_evaluation(seq, titre, type_ev, exos, rapport)     # v0.60.0 (B10)
        avant = conn.execute("SELECT id, etat_code FROM evaluations WHERE niveau = ? AND "
                             "titre = ? ORDER BY numero LIMIT 1", (NIVEAU, titre)).fetchone()
        if avant is not None and avant["etat_code"] == "valide":
            # R4 — rien n'est touché : ni l'évaluation, ni ses exercices EV.
            # v0.60.2 — évaluation validée déjà identique au lot : pas
            # d'anomalie (un réimport des mêmes lots ne signale que ce qui
            # diffère) ; ses liens EV gardent leur rang parmi ceux du lot
            # (sinon les exercices des évaluations suivantes passaient devant).
            meme, actuels = evaluation_comme_le_lot(conn, lot, titre, exos, avant["id"])
            if meme:
                rapport.documents.append(f"{seq} évaluation « {titre} » : validée, identique "
                                         "au lot — non modifiée")
            else:
                _evaluation(conn, titre, rapport, seq)
                rapport.documents.append(f"{seq} évaluation « {titre} » : validée, non "
                                         "modifiée — exercices EV non touchés")
            for a in actuels:
                pris.add(a["id"])
                for (oid,) in conn.execute("SELECT objectif_id FROM objectif_exos WHERE "
                                           "exercice_id = ? AND serie = 'EV'", (a["id"],)):
                    liens.setdefault((oid, "EV"), []).append(a["id"])
            num += len(exos)
            continue
        ev_avant = avant["id"] if avant is not None else None
        voulus, etats, nums = [], {}, []
        n_qcm = 0                                                    # v0.60.2
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
            bq, motif_qcm = bareme_qcm_exercice(conn, eid, x["points"])   # v0.60.2
            if bq is not None:
                n_qcm += 1
                if motif_qcm:
                    rapport.avertissements.append(
                        f"{seq} évaluation « {titre} », exercice {i + 1} (QCM) : {motif_qcm}")
            voulus.append((eid, x["points"], bq))
            rapport.journal["import"].append({
                "cle": f"{NIVEAU}/{seq}/EV{n:02d}", "id": eid, "evaluation": titre,
                "objectif": None if x["bonus"] else x["objectif"],
                "origine": paire["A"].get("origine", "")})
        ev_id, etat_ev = _evaluation(conn, titre, rapport, seq)
        n_obj = 0
        if etat_ev != "validée, non modifiée":
            # v0.60.1 (R6) — le lot fait foi pour une évaluation en cours : ses
            # exercices EV de la séquence qui ne sont plus dans le lot la
            # quittent (retirés ensuite s'ils deviennent orphelins).
            change = _retirer_ev_absents(conn, ev_id, seq, [v[0] for v in voulus], titre,
                                         retires_ev, rapport)
            change += _retirer_objectifs_absents(
                conn, ev_id, {objectifs_ids[x["objectif"]] for x in exos if not x["bonus"]},
                titre, seq, rapport)
            change += _poser_exercices_evaluation(conn, ev_id, voulus)
            change += _poser_type_evaluation(conn, ev_id, type_ev)   # v0.60.0 (E6)
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
            + (f" — QCM : {n_qcm} exercice(s), barème bonne/partielle/mauvaise posé"
               if n_qcm else "")
            + (f" — {_resume_deux_parties(conn, ev_id, exos, marques_exos)}" if coupe
               else f" — {mq.LIBELLES_CALCULATRICE[marques_ev['calculatrice']]}"
               if marques_ev["calculatrice"] else ""))
    _retirer_ev_orphelins(conn, seq, [e for e in dict.fromkeys(retires_ev) if e not in pris],
                          {}, rapport)                               # v0.60.1 (R6)
    n = _lier_objectifs(conn, liens)
    if n:
        rapport.seq(seq)["lignes"].append(f"évaluations : {n} lien(s) exercice EV-objectif créé(s)")
    sn = conn.execute("SELECT id FROM sequences_par_niveau WHERE niveau = ? AND "
                      "sequence_code = ?", (NIVEAU, seq)).fetchone()
    controler_tests_courts_parties(conn, seq, sn[0] if sn else None, lot, plan,
                                   rapport)                          # v0.60.0 (E6)


def _retirer_ev_absents(conn, ev_id: str, seq: str, voulus: list, titre: str,
                       retires: list, rapport: Rapport) -> int:
    """v0.60.1 (R6) — Une évaluation en cours prend exactement les exercices EV
    du lot : ceux de la séquence (série EV) qu'elle contient encore et que le
    lot ne cite plus en sortent (ligne d'`evaluation_exercices` copiée dans le
    journal). Les exercices d'autres séries, ajoutés par l'auteur, restent.
    Retourne 1 si quelque chose a changé ; les ids retirés vont dans `retires`
    (orphelins retirés en fin d'import des évaluations)."""
    sortants = _lignes(conn,
        "SELECT ee.* FROM evaluation_exercices ee JOIN exercices x ON x.id = ee.exercice_id "
        "WHERE ee.evaluation_id = ? AND x.niveau = ? AND x.sequence = ? AND "
        "x.serie_code = 'EV' ORDER BY ee.ordre", (ev_id, NIVEAU, seq))
    sortants = [r for r in sortants if r["exercice_id"] not in voulus]
    for r in sortants:
        conn.execute("DELETE FROM evaluation_exercices WHERE evaluation_id = ? AND "
                     "exercice_id = ?", (ev_id, r["exercice_id"]))
        retires.append(r["exercice_id"])
    if sortants:
        rapport.journal.setdefault("retraits", []).append({
            "quoi": "exercices d'évaluation", "sequence": seq, "titre": titre,
            "evaluation_exercices": sortants})
        rapport.documents.append(f"{seq} évaluation « {titre} » : {len(sortants)} ancien(s) "
                                 "exercice(s) EV retiré(s) de l'évaluation (remplacée par le lot)")
    return 1 if sortants else 0


def _retirer_objectifs_absents(conn, ev_id: str, voulus: set, titre: str, seq: str,
                               rapport: Rapport) -> int:
    """v0.60.1 (R6) — Objectifs évalués : ceux du barème du lot seulement."""
    sortants = [r for r in _lignes(conn, "SELECT * FROM evaluation_objectifs WHERE "
                                         "evaluation_id = ?", (ev_id,))
                if r["objectif_id"] not in voulus]
    for r in sortants:
        conn.execute("DELETE FROM evaluation_objectifs WHERE evaluation_id = ? AND "
                     "objectif_id = ?", (ev_id, r["objectif_id"]))
    if sortants:
        rapport.journal.setdefault("retraits", []).append({
            "quoi": "objectifs d'évaluation", "sequence": seq, "titre": titre,
            "evaluation_objectifs": sortants})
    return 1 if sortants else 0


# ── v0.60.1 (R7) — Réimport : ce qu'il faut repasser en cours ───────────────

def evaluation_comme_le_lot(conn, lot: dict, titre: str, exos: list[dict], ev_id: str
                            ) -> "tuple[bool, list]":
    """(identique, exercices EV actuels) : l'évaluation `ev_id` a-t-elle déjà
    exactement le contenu du lot (exercices EV de la séquence dans l'ordre,
    contenu, points, type d'évaluation, objectifs évalués ; v0.60.2 : barème
    QCM attendu d'un exercice QCM) ? Utilisé par le diagnostic R7 et par R4."""
    seq = lot["sequence"]
    actuels = conn.execute(
        "SELECT x.*, ee.bareme_points, ee.bareme_qcm_ok, ee.bareme_qcm_partiel, "
        "ee.bareme_qcm_ko FROM evaluation_exercices ee JOIN exercices x ON "
        "x.id = ee.exercice_id WHERE ee.evaluation_id = ? AND x.niveau = ? AND "
        "x.sequence = ? AND x.serie_code = 'EV' ORDER BY ee.ordre",
        (ev_id, NIVEAU, seq)).fetchall()
    voulus = [(_vals_ev(x), float(x["points"])) for x in exos]

    def meme_qcm(a, p) -> bool:
        if (a["type_format"] if "type_format" in a.keys() else "standard") != "qcm":
            return True
        return tuple(a[c] for c in CHAMPS_QCM) == bareme_qcm(a["enonce"] or "", p)[0]
    meme = len(actuels) == len(voulus) and all(
        _meme_contenu(a, v) and float(a["bareme_points"] or 0) == p and meme_qcm(a, p)
        for a, (v, p) in zip(actuels, voulus))
    from services import evaluations_v2 as ev2
    if ev2.colonnes_presentes(conn) and ev2.type_evaluation(conn, ev_id) \
            != type_evaluation_lot(lot, titre):
        meme = False
    # Objectifs évalués : ceux du barème du lot (R6). Codes comparés sans
    # le préfixe de séquence (« A1-02 » dans le lot, « 02 » en base).
    def court(code) -> str:
        return str(code or "").rsplit("-", 1)[-1]
    evalues = {court(r[0]) for r in conn.execute(
        "SELECT o.code FROM evaluation_objectifs eo JOIN objectifs o ON o.id = eo.objectif_id "
        "WHERE eo.evaluation_id = ?", (ev_id,))}
    if evalues != {court(x["objectif"]) for x in exos if not x["bonus"]}:
        meme = False
    return meme, actuels


def diagnostiquer_reimport(conn, lot: dict, rapport: Rapport) -> None:
    """Avant l'import d'un lot (essai à blanc compris) : séquence validée,
    évaluations validées dont le lot change le contenu, exercices EV validés
    d'évaluations en cours que le lot réécrit. Rangés dans `rapport.a_repasser`
    (section « À repasser en cours avant l'import » du rapport)."""
    seq = lot["sequence"]
    sn = conn.execute("SELECT etat_code FROM sequences_par_niveau WHERE niveau = ? AND "
                      "sequence_code = ?", (NIVEAU, seq)).fetchone()
    if sn is not None and sn[0] == "valide":
        rapport.a_repasser["sequences"].append(seq)
    for titre, paire in paires_evaluations(lot).items():
        try:
            exos = preparer_evaluation(titre, paire)
        except ImportErreur:
            continue
        ev = conn.execute("SELECT id, etat_code FROM evaluations WHERE niveau = ? AND "
                          "titre = ? ORDER BY numero LIMIT 1", (NIVEAU, titre)).fetchone()
        if ev is None:
            continue
        meme, actuels = evaluation_comme_le_lot(conn, lot, titre, exos, ev["id"])
        if meme:
            continue
        if ev["etat_code"] == "valide":
            rapport.a_repasser["evaluations"].append(f"{seq} « {titre} »")
            continue
        for a in actuels:
            if a["etat_code"] == "valide" and len(_evaluations_de(conn, a["id"])) == 1:
                rapport.a_repasser["exercices"].append(
                    f"{NIVEAU}/{seq}/EV{a['num']:02d} (« {titre} »)")


def _poser_type_evaluation(conn, ev_id: str, type_ev: str) -> int:
    """v0.60.0 (E6) — `evaluations.type_evaluation` d'après le lot
    (évaluation non validée : l'appelant l'a vérifié). Retourne 1 si la
    valeur change."""
    from services import evaluations_v2 as ev2
    if not ev2.colonnes_presentes(conn):
        ev2.migrer(conn)
    avant = conn.execute("SELECT type_evaluation FROM evaluations WHERE id = ?",
                         (ev_id,)).fetchone()[0]
    if avant == type_ev:
        return 0
    conn.execute("UPDATE evaluations SET type_evaluation = ?, mtime = CURRENT_TIMESTAMP "
                 "WHERE id = ?", (type_ev, ev_id))
    return 1


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
    _retirer_ev_orphelins(conn, seq, list(dict.fromkeys(liberes)), voulu_par_num, rapport)


def _retirer_ev_orphelins(conn, seq: str, ids: list, voulu_par_num: dict,
                          rapport: Rapport) -> None:
    """Exercices EV de la séquence qui ne sont plus utilisés par aucune
    évaluation (R1, v0.52.6 ; v0.60.1 : aussi ceux qu'une évaluation en cours
    a quittés, R6) : non validés → retirés avec leurs liens (journal de
    restauration) ; validés → gardés, anomalie."""
    for eid in ids:
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
             data_dir: Path | None = None, niveau: str | None = None) -> None:
    """v0.59.0 — `niveau` donné : exécution sous `niveau_actif(niveau)`."""
    if niveau is not None:
        with niveau_actif(niveau):
            rapport.niveau = NIVEAU
            return executer(conn, lots, ref, rapport, images, ecrire_fichiers, racine,
                            data_dir)
    return _executer(conn, lots, ref, rapport, images, ecrire_fichiers, racine, data_dir)


def verifier_sequences_cycle(conn, ref: dict, rapport: Rapport) -> None:
    """v0.59.0 (D2) — Hors 6e, les thèmes et séquences du cycle sont ceux de la
    base (migration v0.58) : rien n'est écrit. Une séquence du référentiel
    absente du cycle bloque son lot ; un nom ou un numéro différent est signalé."""
    for s in ref["sequences"]:
        r = conn.execute("SELECT numero, nom FROM sequences_du_cycle WHERE cycle_code=? AND "
                         "code=?", (CYCLE, s["code"])).fetchone()
        if r is None:
            rapport.sequences_bloquees.add(s["code"])
            rapport.anomalie(f"séquence {s['code']} « {s['nom']} » absente du cycle {CYCLE} en "
                             "base : lot non importé (appliquer d'abord la migration des codes)")
            rapport.cycle.append(f"séquence {s['code']} : absente (lot non importé)")
            continue
        ecarts = [x for x, a, b in (("numéro", r["numero"], s.get("numero")),
                                     ("nom", r["nom"], s.get("nom"))) if b is not None and a != b]
        if ecarts:
            rapport.infos.append(f"séquence {s['code']} : {', '.join(ecarts)} du référentiel "
                                 f"différent(s) de la base (« {r['nom']} », n° {r['numero']}) — "
                                 "la base fait foi")
        rapport.cycle.append(f"séquence {s['code']} {r['nom']} (n° {r['numero']})"
                             + (f" — titre court « {s['titre_court']} »"
                                if s.get("titre_court") else ""))


def _executer(conn, lots: list[dict], ref: dict, rapport: Rapport, images: Path,
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
    rapport.niveau = NIVEAU                                            # v0.59.0
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
    if sf.migrer(conn):                                              # v0.56.0
        rapport.infos.append("Base complétée : colonne mention des exercices (v0.56.0)")
    from services import cartes_mentales as _cm                         # v0.55.0
    if _cm.migrer(conn):
        rapport.infos.append("Base complétée : table cartes_mentales (v0.55.0)")
    from services import encarts as _enc                                # v0.59.2
    if _enc.migrer(conn):
        rapport.infos.append("Base complétée : table encarts (v0.59.2)")
    from services import mises_en_route_6e as mer                      # v0.53.1 (P1)
    if mer.migrer(conn):
        rapport.infos.append("Base complétée : colonne libelle des parties de séquence "
                             "(v0.53.1)")
    mer_imp = _module_mer()                                           # v0.53.0
    from services import fiches_cycle4 as fc4                          # v0.59.0
    fc4.migrer(conn)
    from services import evaluations_v2 as ev2                         # v0.60.0
    for x in ev2.migrer(conn):
        rapport.infos.append(f"Base complétée (v0.60.0) : {x}")
    if not est_sixieme():
        # v0.59.0 (D1, D2) — refus net tant que la structure de 2025 du niveau
        # n'est pas archivée (sinon l'import réécrit A1-02, F01… de 2025).
        rapport.archivage_niveau = fc4.archivage(conn, NIVEAU)
        if rapport.archivage_niveau is None:
            raise ImportErreur(message_archivage_manquant(NIVEAU))
        if ref.get("niveau") not in (None, NIVEAU):
            raise ImportErreur(f"{Path(REFERENTIEL).name} décrit le niveau {ref.get('niveau')}, "
                               f"pas {NIVEAU}")
    # v0.57.0 (D6) — référentiel, lots et mises en route ramenés aux codes de
    # la base (S… avant la migration, A1… après) : jamais de S01… recréé.
    ref, lots, ref_mer, _conv = normaliser_codes(
        conn, ref, lots, mer_imp.referentiel_mer() if est_sixieme() else {}, rapport)
    if est_sixieme():
        if not archivage_fait(conn):
            archiver_cycle3(conn, rapport, racine)
        themes = appliquer_cycle3(conn, ref, rapport)
    else:
        verifier_sequences_cycle(conn, ref, rapport)
        themes = {}
    figures = {}
    imp = sys.modules[__name__]
    # v0.53.1 (I-MR7) — mises en route importées avec l'ancienne structure.
    if est_sixieme():
        mer_imp.restructurer_anciennes_mer(conn, imp, ref_mer, rapport)
    for lot in lots:
        if mer_imp.est_lot_mer(lot) and not est_sixieme():
            rapport.anomalie(f"lot {lot['sequence']} : mise en route hors 6e (au modèle Fiches "
                             f"de {NIVEAU}, les cartes d'automatisme sont rattachées aux "
                             "objectifs du principal) — lot ignoré")
            figures[lot["sequence"]] = set()
        elif mer_imp.est_lot_mer(lot):
            figures[lot["sequence"]] = mer_imp.importer_lot_mer(conn, imp, lot, themes,
                                                                ref_mer, rapport)
        else:
            diagnostiquer_reimport(conn, lot, rapport)                # v0.60.1 (R7)
            figures[lot["sequence"]] = importer_lot(conn, lot, ref, rapport)
    copier_figures(lots, figures, images, rapport, ecrire_fichiers)
    if est_sixieme():
        signaler_cycle4(conn, rapport)
    from services.style6e import MACROS as MACROS_STYLE6E, VERSION as VERSION_STYLE6E
    for seq, ms in macros_locales(lots).items():
        if ms:
            rapport.infos.append(f"{seq} : macros locales utilisées (fournies par "
                                 f"seqenseigne-style6e {VERSION_STYLE6E}) : {', '.join(ms)}")
        # v0.52.5 — Une macro \seqLoc… que le module ne fournit pas ferait
        # échouer la compilation de tous les documents de la séquence.
        absentes = [m for m in ms if m not in MACROS_STYLE6E]
        if absentes:
            rapport.anomalie(f"{seq} : macros locales absentes du module seqenseigne-style6e "
                             f"(à verser dans le .dtx) : {', '.join(absentes)}")
    for x in foreach_en_argument(lots):                              # v0.53.2
        rapport.anomalie(f"{x} : \\foreach sans accolades autour de son corps dans un corrigé "
                         "(rendu en argument de \\seqLocExplication : compilation impossible) — "
                         "écrire \\foreach \\x in {…} {…} dans le lot")
    controler_variables(lots, rapport)                               # v0.60.0 (B7)
    for x in titres_documents_en_double(lots):                       # v0.54.1 (D-DOUBLON)
        rapport.anomalie(f"titre de document en double {x} — renommer l'un des documents "
                         "dans son lot (risque de confusion pour les élèves et les collègues)")
    # v0.52.8 (I2) — même contrôle pour les macros \seq…Six du module
    # (\seqAstuceSix, v0.8) ; nombre d'astuces par séquence.
    for seq, (ms, n_astuces) in macros_module(lots).items():
        absentes = [m for m in ms if m not in MACROS_STYLE6E]
        if absentes:
            rapport.anomalie(f"{seq} : macros absentes du module seqenseigne-style6e {VERSION_STYLE6E} "
                             f"(compilation impossible) : {', '.join(absentes)}")
        if n_astuces:
            rapport.infos.append(f"{seq} : {n_astuces} astuce(s) \\seqAstuceSix (module "
                                 f"seqenseigne-style6e {VERSION_STYLE6E})")


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
    ap = argparse.ArgumentParser(description="Import des lots au modèle Fiches dans l'atelier "
                                             "(6e ; 4e depuis v0.59.0)")
    ap.add_argument("--apply", action="store_true", help="applique (sinon essai à blanc)")
    ap.add_argument("--yes", action="store_true", help="sans confirmation")
    ap.add_argument("--db", help="chemin de la base (défaut : base du profil atelier)")
    ap.add_argument("--lots", default=None, help="dossier des lots (défaut : ..\\reference\\"
                                                 "lot6e, lot5e pour N10, lot4e pour N11)")
    ap.add_argument("--niveau", default="N09",
                    help="N09 (6e, défaut), N10 (5e, v0.60.0) ou N11 (4e)")
    args = ap.parse_args(argv)
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        contexte = niveau_actif(args.niveau)
    except ImportErreur as e:
        print(str(e))
        return 2
    with contexte:
        return _main(args)


def _main(args) -> int:
    lots_dir = Path(args.lots or LOTS_DEFAUT)
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
    print(f"Niveau : {NIVEAU} — référentiel {Path(REFERENTIEL).name}")
    print(f"Lots : {', '.join(l['sequence'] for l in lots)} ({lots_dir})\n")

    try:
        rapport = essai_a_blanc(db, lots, ref, images)
    except ImportErreur as e:                                          # v0.59.0
        print(f"Import refusé : {e}")
        return 2
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
    for ev in (lot.get("evaluations", []) or []) + (lot.get("tests_courts", []) or []):
        noms |= _figures(lot, ev)
    return noms


if __name__ == "__main__":
    sys.exit(main())
