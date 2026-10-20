r"""services/marqueurs_exercices.py — v0.52.7

Marqueurs « ordinateur » et « calculatrice » des exercices (besoin de
Laurent, 20 octobre 2026) : savoir, dans toutes les séquences, quels
exercices demandent un ordinateur (Scratch, GeoGebra, tableur, autre) et
lesquels autorisent ou interdisent la calculatrice, pour l'afficher à
l'élève (en-tête de l'exercice du livret), à l'enseignant (plan de travail)
et, plus tard, au tableau de bord de l'appli de classe (réserver la salle
informatique, le chariot mobile…).

Deux colonnes de `exercices` (migration idempotente `migrer`) :

  - `ordinateur`   : ''  (aucun) | scratch | geogebra | tableur | autre ;
  - `calculatrice` : ''  (non précisé) | autorisee | interdite.

Décisions (doc/redemarrage_v0_52_7.md) :

  - M1 Le marquage porte sur l'atome, c'est-à-dire sur l'énoncé principal.
    La remédiation et le sujet B d'une évaluation **suivent le même
    marquage** (pas de champ propre) : c'est la solution la plus simple, et
    une remédiation ou un sujet B reprend la consigne de l'exercice.
  - M2 Valeurs fermées ; une valeur inconnue est refusée par l'atelier et
    signalée par l'import.
  - Le rendu n'émet rien pour un exercice non marqué : le cycle 4 sort
    exactement le même `.tex` tant qu'aucun exercice n'est marqué.
"""

from __future__ import annotations

import sqlite3

ORDINATEUR = ("", "scratch", "geogebra", "tableur", "autre")
CALCULATRICE = ("", "autorisee", "interdite")
CHAMPS = ("ordinateur", "calculatrice")

LIBELLES_ORDINATEUR = {"scratch": "Scratch", "geogebra": "GeoGebra",
                       "tableur": "Tableur", "autre": "Autre"}
LIBELLES_CALCULATRICE = {"autorisee": "calculatrice autorisée",
                         "interdite": "calculatrice interdite"}
VALEURS = {"ordinateur": ORDINATEUR, "calculatrice": CALCULATRICE}


class MarqueurInvalide(ValueError):
    pass


# ── Migration ────────────────────────────────────────────────────────────────

def migrer(conn: sqlite3.Connection) -> None:
    """Ajoute les deux colonnes à `exercices` si elles manquent (idempotent :
    rien ne change au second passage)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(exercices)")}
    if not cols:
        return
    for nom in CHAMPS:
        if nom not in cols:
            conn.execute(f"ALTER TABLE exercices ADD COLUMN {nom} TEXT NOT NULL DEFAULT ''")


def colonnes_presentes(conn: sqlite3.Connection) -> bool:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(exercices)")}
    return all(c in cols for c in CHAMPS)


def sql_colonnes(conn: sqlite3.Connection, alias: str = "") -> str:
    """Fragment SELECT `, ordinateur, calculatrice` ; sur une base sans les
    colonnes (schéma minimal de test, base pas encore migrée), des chaînes
    vides : les lecteurs n'ont pas à tester."""
    p = f"{alias}." if alias else ""
    if colonnes_presentes(conn):
        return f", {p}ordinateur, {p}calculatrice"
    return ", '' AS ordinateur, '' AS calculatrice"


# ── Valeurs ──────────────────────────────────────────────────────────────────

def valider(champ: str, valeur) -> str:
    """Valeur normalisée ('' pour None) ; MarqueurInvalide si hors liste."""
    v = (valeur or "").strip() if isinstance(valeur, str) or valeur is None else valeur
    if v not in VALEURS[champ]:
        raise MarqueurInvalide(
            f"{champ} doit être parmi : {', '.join(repr(x) for x in VALEURS[champ])} "
            f"(reçu {valeur!r})")
    return v


def lire(ex) -> dict:
    """{'ordinateur', 'calculatrice'} d'un dict / Row / objet (absent → '')."""
    out = {}
    for c in CHAMPS:
        if isinstance(ex, dict):
            v = ex.get(c)
        elif isinstance(ex, sqlite3.Row):
            v = ex[c] if c in ex.keys() else ""
        else:
            v = getattr(ex, c, "")
        out[c] = v or ""
    return out


def est_marque(ex) -> bool:
    m = lire(ex)
    return bool(m["ordinateur"] or m["calculatrice"])


def libelle_ordinateur(valeur: str) -> str:
    """Nom de l'outil dans les documents (« Autre » → « autre logiciel »)."""
    if valeur == "autre":
        return "autre logiciel"
    return LIBELLES_ORDINATEUR.get(valeur or "", "")


def mention_texte(ex, sans_calculatrice_interdite: bool = False) -> str:
    """« ordinateur : Scratch ; calculatrice autorisée » ('' si non marqué).
    Texte simple (sans LaTeX actif autre que `~`), réutilisé par les plans
    de travail et le cycle 4."""
    m = lire(ex)
    morceaux = []
    outils = (ex.get("ordinateurs") if isinstance(ex, dict) else None) or \
        ([m["ordinateur"]] if m["ordinateur"] else [])
    if outils:
        morceaux.append("ordinateur~: " + ", ".join(libelle_ordinateur(o) for o in outils))
    if m["calculatrice"] and not (sans_calculatrice_interdite
                                  and m["calculatrice"] == "interdite"):
        morceaux.append(LIBELLES_CALCULATRICE[m["calculatrice"]])
    return " ; ".join(morceaux)


# ── LaTeX ────────────────────────────────────────────────────────────────────

def latex_6e(ex) -> str:
    r"""Pictogrammes du module `seqenseigne-style6e` v0.7 pour l'en-tête
    `seqExoSix` / `seqActiviteSix` : `\seqMaterielSix{Scratch}{interdite}`
    ('' si non marqué)."""
    m = lire(ex)
    if not (m["ordinateur"] or m["calculatrice"]):
        return ""
    # « Ordinateur --- Autre » ne dirait rien à l'élève : « autre logiciel ».
    return (r"\seqMaterielSix{" + libelle_ordinateur(m["ordinateur"]) + "}{"
            + m["calculatrice"] + "}")


def nom_cycle4(nom: str, ex) -> str:
    r"""Décision M4 — Cycle 4 : la mention est ajoutée à la valeur `nom=` de
    `seqExercice` (ligne 2 de la boîte de titre, et des en-têtes de corrigé
    et de remédiation écrits par le paquet), poussée à droite, en texte
    simple : aucun changement du paquet du cycle 4. Exercice non marqué :
    `nom` rendu tel quel (même `.tex`)."""
    mention = mention_texte(ex)
    if not mention:
        return nom
    return (nom or "") + r"\hfill{\small\upshape (" + mention + ")}"


# ── Plans de travail : encadré « Matériel à prévoir » ────────────────────────

def combiner(marques: list) -> dict:
    """Marquage d'un ensemble d'exercices (une évaluation) : les outils
    rencontrés (dans l'ordre de la liste fermée, séparés par « , ») et la
    calculatrice autorisée si un exercice l'autorise, sinon interdite si un
    exercice l'interdit."""
    ms = [lire(m) for m in marques]
    outils = [o for o in ORDINATEUR if o and any(m["ordinateur"] == o for m in ms)]
    calc = ("autorisee" if any(m["calculatrice"] == "autorisee" for m in ms)
            else "interdite" if any(m["calculatrice"] == "interdite" for m in ms) else "")
    return {"ordinateur": outils[0] if len(outils) == 1 else "",
            "ordinateurs": outils, "calculatrice": calc}


class Materiel:
    """Recense les exercices marqués d'un plan de travail, pour l'encadré
    « Matériel à prévoir » : un groupe par outil (ordinateur — Scratch,
    GeoGebra…), puis la calculatrice autorisée. La calculatrice interdite
    n'est pas du matériel à prévoir : elle reste dans la ligne de
    l'exercice."""

    def __init__(self):
        self.groupes: dict = {}

    def noter(self, libelle: str, ex) -> None:
        m = lire(ex)
        outils = (ex.get("ordinateurs") if isinstance(ex, dict) else None) or \
            ([m["ordinateur"]] if m["ordinateur"] else [])
        for o in outils:
            self.groupes.setdefault(("ordinateur", o), []).append(libelle)
        if m["calculatrice"] == "autorisee":
            self.groupes.setdefault(("calculatrice", "autorisee"), []).append(libelle)

    def __bool__(self) -> bool:
        return bool(self.groupes)

    def lignes(self) -> list[tuple[str, list[str]]]:
        """[(« Ordinateur --- Scratch », [libellés])…] dans l'ordre des listes
        fermées."""
        out = []
        for o in ORDINATEUR[1:]:
            if ("ordinateur", o) in self.groupes:
                out.append(("Ordinateur --- " + libelle_ordinateur(o),
                            self.groupes[("ordinateur", o)]))
        if ("calculatrice", "autorisee") in self.groupes:
            out.append(("Calculatrice (autorisée)", self.groupes[("calculatrice", "autorisee")]))
        return out
