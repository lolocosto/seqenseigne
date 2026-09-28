"""
services/resoudre_macros.py — Résolution des macros nommantes du paquet
seqenseigne au moment de l'import d'un dossier `.tex`.

Contexte
--------
Les fichiers sources du paquet seqenseigne utilisent des macros
\\seq...Get... pour référencer des éléments nommés ailleurs dans la
base (cycle, thème, séquence, objectif, connaissance, niveau de
maîtrise). Tant que ces macros ne sont pas développées, les champs
concernés (titres de notions/méthodes, nom d'objectif v2…) stockent
juste le token LaTeX non résolu, peu exploitable dans l'UI.

Ce module applique au texte d'entrée la même résolution que le paquet
LaTeX ferait à la compilation. Il est branché au moment de l'import
(voir `importers/scanner_latex.py`) et ne touche qu'aux champs de
type "nom / libellé". Les champs de saisie libre LaTeX (corps /
corrigé d'un exercice, corps / exemples / remarques d'une notion ou
d'une méthode, critères saisis manuellement…) sont laissés intacts :
leur contenu est de la matière pédagogique et peut légitimement
contenir des macros que seule la compilation doit développer.

Périmètre des macros résolues (17 au total — inventaire figé dans
`seqenseigne-data.dtx`) :

    Niveau                Thème                   Séquence
    ──────────────        ──────────────          ──────────────
    \\seqNiveauGetNomCourt{N}     \\seqThemeGetNom{C}{T}           \\seqSequenceGetNom
    \\seqNiveauGetNomLong{N}      \\seqThemeGetCodeCouleur{C}{T}   \\seqSequenceGetNomOf{N}{S}
    \\seqNiveauGetCodeCycle{N}    \\seqThemeGetDescription{C}{T}   \\seqSequenceGetNumero
                                                                   \\seqSequenceGetTheme

    Objectif                              Connaissance               Maîtrise
    ──────────────                        ──────────────             ──────────────
    \\seqObjectifGetNom{CC}                \\seqConnaissanceGetNom{NN} \\seqMaitriseGetNom{X}
    \\seqObjectifGetFinCycle{CC}
    \\seqObjectifGetMaitriseTB{CC}
    \\seqObjectifGetMaitriseS{CC}
    \\seqObjectifGetMaitriseF{CC}

API publique
------------
- `Contexte` : classe de données regroupant tout ce qui est nécessaire
  pour résoudre les macros (tables C04, séquence courante, objectifs
  et connaissances de la séquence, etc.).
- `construire_contexte(data_scan, niveau, sequence, csv_store)` :
  helper pour construire un contexte à partir du résultat d'un scan.
- `resoudre(texte, contexte)` → `(texte_resolu, incidents)` :
  applique la résolution. Retourne une liste d'incidents (macros
  restées non résolues) au format [{macro, raison}].

Stratégie pour macros irrésolubles
----------------------------------
Si une macro référence un élément introuvable (objectif/connaissance
absent du contexte courant, niveau inconnu, etc.), le texte est
remplacé par `[à saisir]` et un incident est enregistré. Le caller
(scanner) consolide ensuite ces incidents en un rapport destiné à
l'UI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable


# ─────────────────────────────────────────────────────────────────────────────
# Libellé de substitution quand une macro nomme un élément introuvable
# ─────────────────────────────────────────────────────────────────────────────

FALLBACK = "[à saisir]"


# ─────────────────────────────────────────────────────────────────────────────
# Table de secours : codes de niveau → (cycle, nom court, nom long, année)
#
# Source de vérité : `data/param_niveaux.csv`, lu par
# `CsvStore.lire_param_niveaux()` et injecté dans le contexte via
# `construire_contexte_global`. Cette constante n'est utilisée que comme
# **fallback** (CSV absent ou contexte construit sans csv_store — cas
# des tests unitaires autonomes) et pour documenter le format attendu.
#
# Elle doit rester alignée sur param_niveaux.csv et param_niveaux.dbtex.
# ─────────────────────────────────────────────────────────────────────────────

PARAM_NIVEAUX_FALLBACK = {
    # code  (cycle, nom_court, nom_long,                   annee_dans_cycle)
    "N07":  ("C03", "CM1",   "cours moyen (1ère année)",   "anneeun"),
    "N08":  ("C03", "CM2",   "cours moyen (2nde année)",   "anneedeux"),
    "N09":  ("C03", "6ème",  "sixième",                    "anneetrois"),
    "N10":  ("C04", "5ème",  "cinquième",                  "anneeun"),
    "N11":  ("C04", "4ème",  "quatrième",                  "anneedeux"),
    "N12":  ("C04", "3ème",  "troisième",                  "anneetrois"),
}

# Alias rétro-compatible (utilisé par du code test pré-existant).
PARAM_NIVEAUX = PARAM_NIVEAUX_FALLBACK


# ─────────────────────────────────────────────────────────────────────────────
# Table statique : codes de maîtrise → libellés
#
# Mirroir exact de `\seqMaitriseGetNom` dans seqenseigne-data.dtx.
# ─────────────────────────────────────────────────────────────────────────────

LIBELLES_MAITRISE = {
    "I":  "Insuffisant",
    "F":  "À consolider",
    "A":  "Satisfaisant",
    "E":  "Très bon",
    "NE": "Non évalué",
}


# ─────────────────────────────────────────────────────────────────────────────
# Contexte de résolution
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Contexte:
    """
    Tout ce qui est nécessaire pour résoudre les macros nommantes d'un
    morceau de texte donné.

    Attributs
    ---------
    niveau_courant, sequence_courante :
        Codes actifs (ex. "N11", "S01"). Utilisés pour résoudre les
        macros sans argument qui utilisent le contexte : \\seqSequenceGetNom,
        \\seqSequenceGetNumero, \\seqSequenceGetTheme ; et les macros
        à argument qui ne spécifient que le code (\\seqObjectifGetNom{02},
        \\seqConnaissanceGetNom{01}).

    param_niveaux :
        { code_niveau → (code_cycle, nom_court, nom_long, annee_dans_cycle) }
        Chargé depuis `data/param_niveaux.csv`.

    sequences_par_cycle :
        { code_cycle → { code_sequence → {"Nom", "Numero", "Theme"} } }
        Chargé depuis C03_sequences.csv et C04_sequences.csv.

    themes_par_cycle :
        { code_cycle → { code_theme → {"Nom", "CodeCouleur", "Description"} } }
        Chargé depuis C03_themes.csv et C04_themes.csv.

    objectifs :
        { (niveau, seq, code) → {"nom", "fin_cycle", "maitrise_tb",
                                  "maitrise_s", "maitrise_f"} }
        Chargé depuis C03_objectifs.csv et C04_objectifs.csv. Unifié
        sur les deux cycles (les clés sont préfixées par le code
        niveau, donc pas de collision possible entre N09/S01 et N10/S01).

    connaissances :
        { (niveau, seq, code) → nom }
        Chargé depuis C03_connaissances.csv et C04_connaissances.csv.
    """
    niveau_courant:      str  = ""
    sequence_courante:   str  = ""
    param_niveaux:       dict = field(default_factory=dict)
    sequences_par_cycle: dict = field(default_factory=dict)
    themes_par_cycle:    dict = field(default_factory=dict)
    objectifs:           dict = field(default_factory=dict)
    connaissances:       dict = field(default_factory=dict)

    # Helpers de lookup ---------------------------------------------------

    def info_niveau(self, niveau: str) -> tuple | None:
        """Retourne (cycle, nom_court, nom_long, annee) ou None si inconnu."""
        if niveau in self.param_niveaux:
            return self.param_niveaux[niveau]
        return PARAM_NIVEAUX_FALLBACK.get(niveau)

    def cycle_du_niveau(self, niveau: str) -> str | None:
        info = self.info_niveau(niveau)
        return info[0] if info else None

    def sequence_info(self, niveau: str, sequence: str) -> dict | None:
        cycle = self.cycle_du_niveau(niveau)
        if not cycle:
            return None
        seqs = self.sequences_par_cycle.get(cycle, {})
        return seqs.get(sequence)

    def theme_info(self, cycle: str, code_theme: str) -> dict | None:
        themes = self.themes_par_cycle.get(cycle, {})
        return themes.get(code_theme)

    def objectif_info(self, niveau: str, sequence: str, code: str) -> dict | None:
        return self.objectifs.get((niveau, sequence, code))

    def connaissance_nom(self, niveau: str, sequence: str, num: str) -> str | None:
        return self.connaissances.get((niveau, sequence, num))


# ─────────────────────────────────────────────────────────────────────────────
# Construction de contexte depuis les résultats d'un scan
# ─────────────────────────────────────────────────────────────────────────────

def construire_contexte_global(csv_store) -> Contexte:
    """
    Contexte complet pour la résolution des macros. Charge depuis data/ :
      - param_niveaux.csv      → Contexte.param_niveaux
      - C03 et C04 sequences   → Contexte.sequences_par_cycle
      - C03 et C04 themes      → Contexte.themes_par_cycle
      - C03 et C04 objectifs   → Contexte.objectifs
      - C03 et C04 connaissances → Contexte.connaissances

    Les titres des notions et méthodes scannées dans les `.tex` se
    résument très souvent à une simple macro (ex. `\\seqConnaissanceGetNom{01}`).
    Les **noms** correspondants ne sont jamais dans les `.tex` scannés —
    ils viennent de ces CSV de référence, exactement comme le paquet
    LaTeX va les chercher dans une base .dbtex à la compilation.

    Si un CSV est absent, on charge ce qu'on peut et on laisse le reste
    vide. Les macros qui pointeraient vers un référentiel absent
    retourneront alors `[à saisir]` avec un incident explicatif.
    """
    ctx = Contexte()

    # ── Niveaux ──────────────────────────────────────────────────────────
    try:
        niveaux_csv = csv_store.lire_param_niveaux()
    except Exception:
        niveaux_csv = {}
    if isinstance(niveaux_csv, dict) and niveaux_csv:
        ctx.param_niveaux = {
            code: (
                info.get("code_cycle", ""),
                info.get("nom_court", ""),
                info.get("nom_long", ""),
                info.get("annee_dans_cycle", ""),
            )
            for code, info in niveaux_csv.items()
        }
    else:
        # Fallback si param_niveaux.csv absent/illisible : table en dur
        # (6 niveaux collège/élémentaire stables).
        ctx.param_niveaux = dict(PARAM_NIVEAUX_FALLBACK)

    # ── Séquences (C03 + C04) ────────────────────────────────────────────
    ctx.sequences_par_cycle = {
        "C03": _lire_sequences_safe(csv_store, "lire_c03_sequences"),
        "C04": _lire_sequences_safe(csv_store, "lire_c04_sequences"),
    }

    # ── Thèmes (C03 + C04) ───────────────────────────────────────────────
    ctx.themes_par_cycle = {
        "C03": _lire_themes_safe(csv_store, "lire_c03_themes"),
        "C04": _lire_themes_safe(csv_store, "lire_c04_themes"),
    }

    # ── Connaissances (C03 + C04) fusionnées ─────────────────────────────
    ctx.connaissances = {}
    ctx.connaissances.update(_lire_connaissances_safe(csv_store, "lire_c03_connaissances"))
    ctx.connaissances.update(_lire_connaissances_safe(csv_store, "lire_c04_connaissances"))

    # ── Objectifs (C03 + C04) fusionnés ──────────────────────────────────
    ctx.objectifs = {}
    ctx.objectifs.update(_lire_objectifs_safe(csv_store, "lire_c03_objectifs"))
    ctx.objectifs.update(_lire_objectifs_safe(csv_store, "lire_c04_objectifs"))

    return ctx


def _lire_sequences_safe(csv_store, method_name: str) -> dict:
    """Normalise la lecture d'un CSV de séquences en dict indexé par code."""
    if not csv_store or not hasattr(csv_store, method_name):
        return {}
    try:
        data = getattr(csv_store, method_name)()
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        code: {
            "Nom":    info.get("nom", ""),
            "Numero": str(info.get("numero", "")),
            "Theme":  info.get("theme", ""),
        }
        for code, info in data.items()
    }


def _lire_themes_safe(csv_store, method_name: str) -> dict:
    """Normalise la lecture d'un CSV de thèmes en dict indexé par code."""
    if not csv_store or not hasattr(csv_store, method_name):
        return {}
    try:
        data = getattr(csv_store, method_name)()
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        code: {
            "Nom":         info.get("nom", ""),
            "CodeCouleur": info.get("code_couleur", ""),
            "Description": info.get("description", ""),
        }
        for code, info in data.items()
    }


def _lire_connaissances_safe(csv_store, method_name: str) -> dict:
    """
    Lecture tolérante des CSV de connaissances. Retourne {(niveau, seq, code): nom}.
    """
    if not csv_store or not hasattr(csv_store, method_name):
        return {}
    try:
        data = getattr(csv_store, method_name)()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _lire_objectifs_safe(csv_store, method_name: str) -> dict:
    """
    Lecture tolérante des CSV d'objectifs. Retourne
    {(niveau, seq, code): {nom, fin_cycle, maitrise_tb, maitrise_s, maitrise_f}}.
    """
    if not csv_store or not hasattr(csv_store, method_name):
        return {}
    try:
        data = getattr(csv_store, method_name)()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


# ─────────────────────────────────────────────────────────────────────────────
# Résolveur
# ─────────────────────────────────────────────────────────────────────────────

# Pré-compilation des regex. On capture la macro entière (avec ses
# arguments en `{...}`) pour pouvoir la remplacer d'un coup.
#
# Chaque macro a sa propre regex car le nombre d'arguments varie
# (0, 1 ou 2) et on veut typer précisément ce qu'on en extrait.
# On interdit les arguments qui contiennent `{` ou `}` — nos codes
# et identifiants sont tous ASCII simples (N10, S01, 02, C04, E…).

_RE_NIVEAU_NOMCOURT     = re.compile(r"\\seqNiveauGetNomCourt\{([^{}]+)\}")
_RE_NIVEAU_NOMLONG      = re.compile(r"\\seqNiveauGetNomLong\{([^{}]+)\}")
_RE_NIVEAU_CODECYCLE    = re.compile(r"\\seqNiveauGetCodeCycle\{([^{}]+)\}")

_RE_THEME_NOM           = re.compile(r"\\seqThemeGetNom\{([^{}]+)\}\{([^{}]+)\}")
_RE_THEME_CODECOULEUR   = re.compile(r"\\seqThemeGetCodeCouleur\{([^{}]+)\}\{([^{}]+)\}")
_RE_THEME_DESCRIPTION   = re.compile(r"\\seqThemeGetDescription\{([^{}]+)\}\{([^{}]+)\}")

# Macros sans argument : utilisent le contexte courant. Attention au bord
# droit : `\seqSequenceGetNom` ne doit pas matcher `\seqSequenceGetNomOf`,
# d'où la négative lookahead sur `[A-Za-z]`.
_RE_SEQUENCE_NOM        = re.compile(r"\\seqSequenceGetNom(?![A-Za-z])")
_RE_SEQUENCE_NOMOF      = re.compile(r"\\seqSequenceGetNomOf\{([^{}]+)\}\{([^{}]+)\}")
_RE_SEQUENCE_NUMERO     = re.compile(r"\\seqSequenceGetNumero(?![A-Za-z])")
_RE_SEQUENCE_THEME      = re.compile(r"\\seqSequenceGetTheme(?![A-Za-z])")

_RE_OBJECTIF_NOM        = re.compile(r"\\seqObjectifGetNom\{([^{}]+)\}")
_RE_OBJECTIF_FINCYCLE   = re.compile(r"\\seqObjectifGetFinCycle\{([^{}]+)\}")
_RE_OBJECTIF_MAITRISETB = re.compile(r"\\seqObjectifGetMaitriseTB\{([^{}]+)\}")
_RE_OBJECTIF_MAITRISES  = re.compile(r"\\seqObjectifGetMaitriseS\{([^{}]+)\}")
_RE_OBJECTIF_MAITRISEF  = re.compile(r"\\seqObjectifGetMaitriseF\{([^{}]+)\}")

_RE_CONNAISSANCE_NOM    = re.compile(r"\\seqConnaissanceGetNom\{([^{}]+)\}")

_RE_MAITRISE_NOM        = re.compile(r"\\seqMaitriseGetNom\{([^{}]+)\}")

# Fallback qui détecte une macro \\seq...Get... non listée ci-dessus.
# Utile pour signaler les macros hors périmètre sans planter.
_RE_MACRO_SEQ_GET       = re.compile(r"\\seq[A-Z][A-Za-z]*Get[A-Za-z]+(?:\{[^{}]*\})*")


def resoudre(texte: str, ctx: Contexte) -> tuple[str, list[dict]]:
    """
    Résout toutes les macros nommantes connues dans `texte`.

    Retourne
    --------
    (texte_resolu, incidents)
        - texte_resolu : la chaîne après substitution
        - incidents    : liste de dicts {macro, raison}, une entrée par
                         macro restée non résolue (référence introuvable
                         ou macro hors périmètre).
    """
    if not texte:
        return texte or "", []

    incidents: list[dict] = []

    # On travaille par substitutions successives. Chaque `_sub_*` retourne
    # le texte modifié et empile les incidents éventuels.
    out = texte

    # Macros à argument (niveau / thème / objectif / connaissance / maîtrise)
    out = _sub_niveau_nomcourt(out, ctx, incidents)
    out = _sub_niveau_nomlong(out, ctx, incidents)
    out = _sub_niveau_codecycle(out, ctx, incidents)

    out = _sub_theme_nom(out, ctx, incidents)
    out = _sub_theme_codecouleur(out, ctx, incidents)
    out = _sub_theme_description(out, ctx, incidents)

    out = _sub_sequence_nomof(out, ctx, incidents)

    out = _sub_objectif(out, ctx, incidents, _RE_OBJECTIF_NOM,        "nom",         "\\seqObjectifGetNom")
    out = _sub_objectif(out, ctx, incidents, _RE_OBJECTIF_FINCYCLE,   "fin_cycle",   "\\seqObjectifGetFinCycle")
    out = _sub_objectif(out, ctx, incidents, _RE_OBJECTIF_MAITRISETB, "maitrise_tb", "\\seqObjectifGetMaitriseTB")
    out = _sub_objectif(out, ctx, incidents, _RE_OBJECTIF_MAITRISES,  "maitrise_s",  "\\seqObjectifGetMaitriseS")
    out = _sub_objectif(out, ctx, incidents, _RE_OBJECTIF_MAITRISEF,  "maitrise_f",  "\\seqObjectifGetMaitriseF")

    out = _sub_connaissance(out, ctx, incidents)
    out = _sub_maitrise(out, ctx, incidents)

    # Macros contextuelles (sans argument) — à faire après les variantes
    # explicites pour ne pas re-matcher des préfixes.
    out = _sub_sequence_nom(out, ctx, incidents)
    out = _sub_sequence_numero(out, ctx, incidents)
    out = _sub_sequence_theme(out, ctx, incidents)

    # Tout \seq...Get... restant est hors périmètre connu : on signale
    # sans le remplacer (il sera visible dans l'UI pour information).
    for m in _RE_MACRO_SEQ_GET.finditer(out):
        incidents.append({
            "macro":  m.group(0),
            "raison": "macro non prise en charge par le résolveur",
        })

    return out, incidents


# ── Helpers de substitution ───────────────────────────────────────────────────

def _sub_avec_lookup(
    texte: str,
    regex: re.Pattern,
    incidents: list[dict],
    lookup: Callable[[tuple], tuple[str | None, str]],
) -> str:
    """
    Applique une substitution basée sur `regex` + une fonction `lookup`
    qui reçoit les groupes capturés et retourne `(valeur, raison_si_echec)`.

    Si `valeur` est None : on substitue par `FALLBACK` et on enregistre
    un incident avec la macro source et la raison donnée.
    """
    def _remplacer(m):
        valeur, raison = lookup(m.groups())
        if valeur is None:
            incidents.append({"macro": m.group(0), "raison": raison})
            return FALLBACK
        return valeur
    return regex.sub(_remplacer, texte)


def _sub_niveau_nomcourt(texte: str, ctx: Contexte, incidents: list[dict]) -> str:
    def lk(g):
        info = ctx.info_niveau(g[0])
        return (info[1], "") if info else (None, f"niveau inconnu : {g[0]}")
    return _sub_avec_lookup(texte, _RE_NIVEAU_NOMCOURT, incidents, lk)


def _sub_niveau_nomlong(texte: str, ctx: Contexte, incidents: list[dict]) -> str:
    def lk(g):
        info = ctx.info_niveau(g[0])
        return (info[2], "") if info else (None, f"niveau inconnu : {g[0]}")
    return _sub_avec_lookup(texte, _RE_NIVEAU_NOMLONG, incidents, lk)


def _sub_niveau_codecycle(texte: str, ctx: Contexte, incidents: list[dict]) -> str:
    def lk(g):
        info = ctx.info_niveau(g[0])
        return (info[0], "") if info else (None, f"niveau inconnu : {g[0]}")
    return _sub_avec_lookup(texte, _RE_NIVEAU_CODECYCLE, incidents, lk)


def _sub_theme_nom(texte: str, ctx: Contexte, incidents: list[dict]) -> str:
    def lk(g):
        info = ctx.theme_info(g[0], g[1])
        return (info["Nom"], "") if info else (None, f"thème inconnu : {g[0]}/{g[1]}")
    return _sub_avec_lookup(texte, _RE_THEME_NOM, incidents, lk)


def _sub_theme_codecouleur(texte: str, ctx: Contexte, incidents: list[dict]) -> str:
    def lk(g):
        info = ctx.theme_info(g[0], g[1])
        return (info["CodeCouleur"], "") if info else (None, f"thème inconnu : {g[0]}/{g[1]}")
    return _sub_avec_lookup(texte, _RE_THEME_CODECOULEUR, incidents, lk)


def _sub_theme_description(texte: str, ctx: Contexte, incidents: list[dict]) -> str:
    def lk(g):
        info = ctx.theme_info(g[0], g[1])
        return (info["Description"], "") if info else (None, f"thème inconnu : {g[0]}/{g[1]}")
    return _sub_avec_lookup(texte, _RE_THEME_DESCRIPTION, incidents, lk)


def _sub_sequence_nomof(texte: str, ctx: Contexte, incidents: list[dict]) -> str:
    def lk(g):
        info = ctx.sequence_info(g[0], g[1])
        return (info["Nom"], "") if info else (None, f"séquence inconnue : {g[0]}/{g[1]}")
    return _sub_avec_lookup(texte, _RE_SEQUENCE_NOMOF, incidents, lk)


def _sub_objectif(
    texte: str, ctx: Contexte, incidents: list[dict],
    regex: re.Pattern, champ: str, macro_nom: str,
) -> str:
    """Substitution générique pour les macros \\seqObjectifGet{Nom,FinCycle,Maitrise*}.

    Signale `[à saisir]` + incident si (a) l'objectif est introuvable ou
    (b) le champ est explicitement manquant (clé absente). Une valeur
    vide `""` est considérée comme intentionnelle (ex. MaitriseF non
    renseigné). Une valeur comme "N" (pour FinCycle) est évidemment valide.
    """
    def lk(g):
        info = ctx.objectif_info(ctx.niveau_courant, ctx.sequence_courante, g[0])
        if not info:
            return (None,
                    f"objectif {g[0]} introuvable pour {ctx.niveau_courant}/{ctx.sequence_courante}")
        if champ not in info:
            return (None,
                    f"{champ} non renseigné pour l'objectif {g[0]} "
                    f"({ctx.niveau_courant}/{ctx.sequence_courante})")
        return (info[champ], "")
    return _sub_avec_lookup(texte, regex, incidents, lk)


def _sub_connaissance(texte: str, ctx: Contexte, incidents: list[dict]) -> str:
    def lk(g):
        nom = ctx.connaissance_nom(ctx.niveau_courant, ctx.sequence_courante, g[0])
        if not nom:
            return (None,
                    f"connaissance {g[0]} introuvable pour "
                    f"{ctx.niveau_courant}/{ctx.sequence_courante}")
        return (nom, "")
    return _sub_avec_lookup(texte, _RE_CONNAISSANCE_NOM, incidents, lk)


def _sub_maitrise(texte: str, ctx: Contexte, incidents: list[dict]) -> str:
    def lk(g):
        lib = LIBELLES_MAITRISE.get(g[0])
        if not lib:
            return (None, f"code de maîtrise inconnu : {g[0]}")
        return (lib, "")
    return _sub_avec_lookup(texte, _RE_MAITRISE_NOM, incidents, lk)


def _sub_sequence_nom(texte: str, ctx: Contexte, incidents: list[dict]) -> str:
    if _RE_SEQUENCE_NOM.search(texte) is None:
        return texte
    info = ctx.sequence_info(ctx.niveau_courant, ctx.sequence_courante)
    def _remplacer(m):
        if info:
            return info["Nom"]
        incidents.append({
            "macro":  m.group(0),
            "raison": (f"séquence courante introuvable : "
                       f"{ctx.niveau_courant}/{ctx.sequence_courante}"),
        })
        return FALLBACK
    return _RE_SEQUENCE_NOM.sub(_remplacer, texte)


def _sub_sequence_numero(texte: str, ctx: Contexte, incidents: list[dict]) -> str:
    if _RE_SEQUENCE_NUMERO.search(texte) is None:
        return texte
    info = ctx.sequence_info(ctx.niveau_courant, ctx.sequence_courante)
    def _remplacer(m):
        if info:
            return info["Numero"]
        incidents.append({
            "macro":  m.group(0),
            "raison": (f"séquence courante introuvable : "
                       f"{ctx.niveau_courant}/{ctx.sequence_courante}"),
        })
        return FALLBACK
    return _RE_SEQUENCE_NUMERO.sub(_remplacer, texte)


def _sub_sequence_theme(texte: str, ctx: Contexte, incidents: list[dict]) -> str:
    if _RE_SEQUENCE_THEME.search(texte) is None:
        return texte
    info = ctx.sequence_info(ctx.niveau_courant, ctx.sequence_courante)
    def _remplacer(m):
        if info:
            return info["Theme"]
        incidents.append({
            "macro":  m.group(0),
            "raison": (f"séquence courante introuvable : "
                       f"{ctx.niveau_courant}/{ctx.sequence_courante}"),
        })
        return FALLBACK
    return _RE_SEQUENCE_THEME.sub(_remplacer, texte)


# ─────────────────────────────────────────────────────────────────────────────
# Utilitaire : contient-il une macro nommante ?
# ─────────────────────────────────────────────────────────────────────────────

def contient_macro_nommante(texte: str) -> bool:
    """
    Test rapide : le texte contient-il une macro \\seq...Get... ?
    Utile pour décider s'il faut invoquer le résolveur sur un champ
    donné (optimisation, car les titres sans macro sont majoritaires
    à terme).
    """
    return bool(texte) and _RE_MACRO_SEQ_GET.search(texte) is not None
