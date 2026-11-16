# -*- coding: utf-8 -*-
"""services/codes_sequence.py — v0.57.0 : codes de séquences, anciens et nouveaux.

Une seule source pour reconnaître un code de séquence (plan de migration des
thèmes et des codes, livraison 1 : code tolérant, aucune donnée migrée).

Familles de codes (synthèse du cycle 4, § 5) :

  - **code de thème** `A1` … `F9` : lettre du thème (A à F) + rang dans le
    thème (1 à 9). Codes des référentiels à partir de la rentrée 2027 ;
  - **ancien code** `S01` … : codes actuels du cycle 3 et du cycle 4, et de
    tous les instantanés figés (N11_v2025…) ;
  - **mise en route** `M01` … (6e, référentiel « mer ») ;
  - **archive** `X01` … (séquences retirées du référentiel principal).

Les lettres S, M et X sont réservées : aucun thème ne les prend.

Ce module ne lit ni n'écrit aucune base. La table de correspondance
`outils/correspondance_codes_2027.json` (ancien → nouveau, cycles 3 et 4,
thèmes) est lue par `charger_correspondance` ; elle sert aux outils de lots
de 6e (lire un lot en code S… ou A1) et servira à l'outil de migration
(v0.58.0).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

# ── Motifs ───────────────────────────────────────────────────────────────────

#: Motifs sans ancre, pour composer des expressions (noms de fichiers…).
MOTIF_THEME = r"[A-F][1-9]"
MOTIF_ANCIEN = r"S\d{2}"
MOTIF_MER = r"M\d{2}"
MOTIF_ARCHIVE = r"X\d{2}"
#: Code de séquence dans un nom de fichier LaTeX de l'atelier (`N10S03F01.tex`,
#: `N10A1F01.tex`, `N10_A1_Notion_01.tex`…). Les anciens codes y sont lus
#: comme avant v0.57.0 (`S` suivi de chiffres).
MOTIF_FICHIER = r"(?:S\d+|[A-F][1-9])"

_RE_THEME = re.compile(MOTIF_THEME)
_RE_ANCIEN = re.compile(MOTIF_ANCIEN)
_RE_ANCIEN_LARGE = re.compile(r"S\d{1,3}")
_RE_MER = re.compile(MOTIF_MER)
_RE_ARCHIVE = re.compile(MOTIF_ARCHIVE)
# Recherche dans un texte libre (nom de PDF d'archive…) : le code de thème
# doit être isolé (« 5E2 » ne contient pas le code E2).
_RE_CHERCHE_ANCIEN = re.compile(MOTIF_ANCIEN)
_RE_CHERCHE_THEME = re.compile(r"(?<![A-Za-z0-9])" + MOTIF_THEME + r"(?![0-9])")


def _c(code) -> str:
    return (code or "").strip() if isinstance(code, str) or code is None else str(code)


def est_code_theme(code) -> bool:
    """`A1` … `F9` : code de séquence préfixé par la lettre du thème."""
    return bool(_RE_THEME.fullmatch(_c(code)))


def est_code_ancien(code) -> bool:
    """`S01` … `S99` : ancien code (avant la rentrée 2027)."""
    return bool(_RE_ANCIEN.fullmatch(_c(code)))


def est_code_mer(code) -> bool:
    """`M01` … : séquence de mise en route (6e)."""
    return bool(_RE_MER.fullmatch(_c(code)))


def est_code_archive(code) -> bool:
    """`X01` … : séquence d'archive (hors référentiel principal)."""
    return bool(_RE_ARCHIVE.fullmatch(_c(code)))


def famille(code) -> str | None:
    """'theme', 'ancien', 'mer', 'archive' ou None (code inconnu)."""
    if est_code_theme(code):
        return "theme"
    if est_code_ancien(code):
        return "ancien"
    if est_code_mer(code):
        return "mer"
    if est_code_archive(code):
        return "archive"
    return None


def est_code_principal(code) -> bool:
    """Séquence du référentiel principal : code de thème ou ancien code."""
    return est_code_theme(code) or est_code_ancien(code)


def est_code_sequence(code, *, mer: bool = False, archive: bool = False,
                      ancien_large: bool = False) -> bool:
    """Code de séquence accepté.

    Toujours : code de thème (`A1`) et ancien code (`S01`). `ancien_large` :
    l'ancien code est accepté comme avant v0.57.0 dans les routes (`S` suivi
    de 1 à 3 chiffres : S1, S01, S101). `mer` : aussi `Mnn`. `archive` :
    aussi `Xnn`."""
    c = _c(code)
    if est_code_theme(c):
        return True
    if (_RE_ANCIEN_LARGE if ancien_large else _RE_ANCIEN).fullmatch(c):
        return True
    if mer and est_code_mer(c):
        return True
    return bool(archive and est_code_archive(c))


def chercher_code(texte) -> str | None:
    """Premier code de séquence d'un texte libre (nom de fichier d'archive,
    nom de PDF figé…) : ancien code `Snn` d'abord (comme avant v0.57.0),
    sinon un code de thème isolé (`livret_sequence__N10__A1.pdf` → A1 ;
    « 5E2 S03_Livret.pdf » → S03). None si aucun."""
    t = texte or ""
    m = _RE_CHERCHE_ANCIEN.search(t)
    if m:
        return m.group(0)
    m = _RE_CHERCHE_THEME.search(t)
    return m.group(0) if m else None


def libelle_numero(code, numero, largeur: int = 0) -> str:
    """Ce qui suit « Séquence » dans un titre de document.

    Code de thème : le code lui-même (« Séquence A1 », jamais « Séquence 11 »).
    Sinon (anciens codes) : le numéro, comme avant v0.57.0, sur `largeur`
    chiffres (`largeur=2` : « Séquence 03 »). '' si rien à afficher."""
    if est_code_theme(code):
        return _c(code)
    if numero is None or numero == "":
        return ""
    if isinstance(numero, int) and largeur:
        return f"{numero:0{largeur}d}"
    return str(numero)


def cle_tri(code) -> tuple:
    """Clé de tri d'une liste qui peut mêler anciens et nouveaux codes.

    Garantie : pour une liste sans code de thème, l'ordre est exactement celui
    du tri alphabétique d'avant v0.57.0 (M… < S… < X…). Les codes de thème
    se rangent juste après les anciens codes et avant les archives (au plus
    9 séquences par thème : A1 < A2 < … < B1). Équivaut, quand anciens et
    nouveaux coexistent (instantané figé et tables vivantes), au tri « par
    numéro » de la synthèse (§ 5, point 14) : anciens d'abord, puis A1 à F9."""
    c = _c(code)
    if est_code_theme(c):
        return ("S\U0010ffff", c)
    return (c, "")


def trier(codes) -> list:
    """Liste triée par `cle_tri` (sans doublon, ordre stable)."""
    return sorted(dict.fromkeys(codes), key=cle_tri)


# ── Table de correspondance (outils/correspondance_codes_2027.json) ─────────

CHEMIN_CORRESPONDANCE = (Path(__file__).resolve().parent.parent / "outils"
                         / "correspondance_codes_2027.json")


class CorrespondanceErreur(ValueError):
    pass


class Correspondance:
    """Table ancien ↔ nouveau d'un fichier `correspondance_codes_2027.json`."""

    def __init__(self, doc: dict):
        if not isinstance(doc, dict) or "cycles" not in doc:
            raise CorrespondanceErreur("table de correspondance sans clé « cycles »")
        self.doc = doc
        self._seq_n: dict[str, dict[str, dict]] = {}
        self._seq_a: dict[str, dict[str, dict]] = {}
        self._th_n: dict[str, dict[str, dict]] = {}
        self._th_a: dict[str, dict[str, dict]] = {}
        self._mer: dict[str, dict[str, dict]] = {}
        for cycle, d in doc["cycles"].items():
            self._seq_n[cycle] = {s["ancien"]: s for s in d.get("sequences", [])}
            self._seq_a[cycle] = {s["nouveau"]: s for s in d.get("sequences", [])}
            self._th_n[cycle] = {t["ancien"]: t for t in d.get("themes", []) if t.get("ancien")}
            self._th_a[cycle] = {t["nouveau"]: t for t in d.get("themes", [])}
            self._mer[cycle] = {m["code"]: m for m in d.get("mises_en_route", [])}
            for s in d.get("sequences", []):
                n = s["nouveau"]
                if not (est_code_theme(n) or est_code_archive(n)):
                    raise CorrespondanceErreur(f"{cycle} : nouveau code {n!r} invalide")
                if not est_code_ancien(s["ancien"]):
                    raise CorrespondanceErreur(f"{cycle} : ancien code {s['ancien']!r} invalide")

    # Séquences
    def sequence(self, cycle: str, code: str) -> dict | None:
        """Entrée de la table pour un code, ancien ou nouveau."""
        return self._seq_n.get(cycle, {}).get(code) or self._seq_a.get(cycle, {}).get(code)

    def vers_nouveau(self, cycle: str, code: str) -> str:
        """S01 → A1 (cycle donné) ; tout autre code inchangé."""
        s = self._seq_n.get(cycle, {}).get(code)
        return s["nouveau"] if s else code

    def vers_ancien(self, cycle: str, code: str) -> str:
        """A1 → S01 (cycle donné) ; tout autre code inchangé."""
        s = self._seq_a.get(cycle, {}).get(code)
        return s["ancien"] if s else code

    def vers(self, cycle: str, code: str, convention: str | None) -> str:
        """Code exprimé dans la convention voulue ('ancien' ou 'nouveau') ;
        inchangé si `convention` est None ou si le code n'est pas dans la table."""
        if convention == "nouveau":
            return self.vers_nouveau(cycle, code)
        if convention == "ancien":
            return self.vers_ancien(cycle, code)
        return code

    # Thèmes
    def theme(self, cycle: str, lettre: str, convention_source: str) -> dict | None:
        """Entrée de thème d'après une lettre exprimée dans `convention_source`."""
        if convention_source == "ancien":
            return self._th_n.get(cycle, {}).get(lettre)
        return self._th_a.get(cycle, {}).get(lettre)

    def theme_vers(self, cycle: str, lettre: str, source: str | None,
                   cible: str | None) -> str:
        """Lettre de thème de la convention `source` vers `cible`."""
        if not source or not cible or source == cible:
            return lettre
        t = self.theme(cycle, lettre, source)
        if t is None:
            return lettre
        return t["nouveau"] if cible == "nouveau" else (t.get("ancien") or lettre)

    def theme_mer(self, cycle: str, code: str, lettre: str, cible: str | None) -> str:
        """Lettre de thème d'une mise en route dans la convention `cible`.
        Sans ambiguïté : pour chaque Mnn, l'ancienne et la nouvelle lettre sont
        dans la table (M03 : B → F)."""
        m = self._mer.get(cycle, {}).get(code)
        if not m or not cible:
            return lettre
        if cible == "nouveau" and lettre == m["theme_ancien"]:
            return m["theme_nouveau"]
        if cible == "ancien" and lettre == m["theme_nouveau"]:
            return m["theme_ancien"]
        return lettre


@lru_cache(maxsize=4)
def _charger(chemin: str) -> Correspondance:
    try:
        doc = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except OSError as e:
        raise CorrespondanceErreur(f"table de correspondance illisible : {chemin} ({e})") from e
    except ValueError as e:
        raise CorrespondanceErreur(f"table de correspondance invalide : {chemin} ({e})") from e
    return Correspondance(doc)


def charger_correspondance(chemin: Path | str | None = None) -> Correspondance:
    """Table de correspondance (mise en cache par chemin)."""
    return _charger(str(chemin or CHEMIN_CORRESPONDANCE))


def convention_codes(codes) -> str | None:
    """'ancien' si les codes principaux sont tous `Snn`, 'nouveau' s'ils sont
    tous des codes de thème, None s'il n'y en a pas ; lève
    CorrespondanceErreur si les deux familles se mêlent (Mnn et Xnn ne
    comptent pas)."""
    fam = {famille(c) for c in codes} & {"ancien", "theme"}
    if fam == {"ancien", "theme"}:
        raise CorrespondanceErreur("anciens codes (S…) et codes de thème (A1…) mêlés : "
                                   + ", ".join(trier(c for c in codes if est_code_principal(c))))
    if fam == {"ancien"}:
        return "ancien"
    if fam == {"theme"}:
        return "nouveau"
    return None
