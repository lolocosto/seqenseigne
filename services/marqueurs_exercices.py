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

v0.52.8 — Calculatrice des évaluations (décisions C1 à C3,
doc/redemarrage_v0_52_8.md) : colonne `evaluations.calculatrice`
('' = selon les exercices | interdite | autorisee | non_precisee), règle
`calculatrice_selon_exercices`, réglage et avertissement
`calculatrice_evaluation` ; travaux personnels hors « Matériel à prévoir »
(décision T1, `hors_materiel`).

v0.52.9 — Sujet en deux parties, façon DNB (décisions D1 à D5,
doc/redemarrage_v0_52_9.md) : règle de déclenchement `deux_parties` (D1),
répartition `partie_de` (D2), durée de la partie 1 `duree_partie1_auto` et
colonne `evaluations.duree_partie1` (D4, NULL = calcul automatique).
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
    """Ajoute les deux colonnes à `exercices` si elles manquent, et (v0.52.8)
    la colonne `calculatrice` à `evaluations` (idempotent : rien ne change
    au second passage)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(exercices)")}
    if cols:
        for nom in CHAMPS:
            if nom not in cols:
                conn.execute(f"ALTER TABLE exercices ADD COLUMN {nom} TEXT NOT NULL DEFAULT ''")
    migrer_evaluations(conn)
    migrer_duree_partie1(conn)


def colonne_duree_presente(conn: sqlite3.Connection) -> bool:
    return "duree_partie1" in {r[1] for r in conn.execute("PRAGMA table_info(evaluations)")}


def migrer_duree_partie1(conn: sqlite3.Connection) -> bool:
    """v0.52.9 (D4) — Colonne `evaluations.duree_partie1` (minutes ; NULL =
    calcul automatique). Idempotent ; retourne True si elle vient d'être
    ajoutée."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(evaluations)")}
    if not cols or "duree_partie1" in cols:
        return False
    conn.execute("ALTER TABLE evaluations ADD COLUMN duree_partie1 INTEGER")
    return True


def colonne_evaluation_presente(conn: sqlite3.Connection) -> bool:
    return "calculatrice" in {r[1] for r in conn.execute("PRAGMA table_info(evaluations)")}


def migrer_evaluations(conn: sqlite3.Connection) -> bool:
    """v0.52.8 (C1) — Colonne `evaluations.calculatrice` (défaut '' : selon
    les exercices). Décision C2 : au moment où la colonne est ajoutée — une
    seule fois par base, donc jamais sur un choix fait ensuite par
    l'enseignant —, l'option « Calculatrice » du document « Évaluations »
    (catalogue 6e) restée à l'ancien défaut « interdite » passe au nouveau
    défaut « selon l'évaluation », pour les référentiels en cours seulement
    (un référentiel verrouillé ou utilisé garde ses documents). Retourne
    True si la colonne vient d'être ajoutée."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(evaluations)")}
    if not cols or "calculatrice" in cols:
        return False
    conn.execute("ALTER TABLE evaluations ADD COLUMN calculatrice TEXT NOT NULL DEFAULT ''")
    _options_documents_selon_evaluation(conn)
    return True


def _options_documents_selon_evaluation(conn: sqlite3.Connection) -> int:
    import json
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"referentiel_documents", "referentiel_niveaux"} <= tables:
        return 0
    n = 0
    for doc_id, opts in conn.execute(
            "SELECT d.id, d.options FROM referentiel_documents d "
            "JOIN referentiel_niveaux r ON r.id = d.referentiel_id "
            "WHERE d.type_document = 'evaluation_6e' AND r.etat = 'en_cours'").fetchall():
        try:
            o = json.loads(opts) if opts else {}
        except (TypeError, ValueError):
            continue
        if isinstance(o, dict) and o.get("calculatrice") == "interdite":
            o["calculatrice"] = "selon_evaluation"
            conn.execute("UPDATE referentiel_documents SET options = ? WHERE id = ?",
                         (json.dumps(o, ensure_ascii=False), doc_id))
            n += 1
    return n


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


# ── Évaluations : mention « calculatrice » du sujet (v0.52.8) ────────────────

# '' : le sujet suit les exercices (C1) ; sinon réglage de l'enseignant.
CALCULATRICE_EVALUATION = ("", "interdite", "autorisee", "non_precisee")
LIBELLES_CALCULATRICE_EVALUATION = {"": "selon les exercices", "interdite": "interdite",
                                    "autorisee": "autorisée", "non_precisee": "non précisée"}


def calculatrice_selon_exercices(marques: list) -> str:
    """Décision C1 (Laurent, 20 octobre) — Une évaluation dont un exercice
    EV est marqué « calculatrice autorisée » sort « calculatrice
    autorisée » ; sinon (un exercice l'interdit, ou rien n'est marqué) :
    « calculatrice interdite », comme avant la v0.52.8."""
    return "autorisee" if any(lire(m)["calculatrice"] == "autorisee" for m in marques) \
        else "interdite"


def calculatrice_evaluation(conn: sqlite3.Connection, evaluation_id: str) -> dict:
    """Mention « calculatrice » d'une évaluation :

    - `reglage` : `evaluations.calculatrice` ('' = selon les exercices) ;
    - `selon_exercices` : règle C1 sur ses exercices EV ;
    - `valeur` : celle du sujet (le réglage s'il est posé, sinon C1) ;
    - `avertissement` : décision C3 — réglage posé à la main en
      contradiction avec des exercices marqués (texte, '' sinon). Le
      réglage n'est jamais écrasé par l'atelier ; l'import le réécrit (le
      lot fait foi) pour une évaluation non validée."""
    reglage = ""
    if colonne_evaluation_presente(conn):
        r = conn.execute("SELECT calculatrice FROM evaluations WHERE id = ?",
                         (evaluation_id,)).fetchone()
        reglage = (r[0] if r else "") or ""
    marques = [{"calculatrice": x[0] or ""} for x in conn.execute(
        "SELECT e.calculatrice FROM evaluation_exercices ee JOIN exercices e "
        "ON e.id = ee.exercice_id WHERE ee.evaluation_id = ? AND e.serie_code = 'EV'",
        (evaluation_id,))] if colonnes_presentes(conn) else []
    selon = calculatrice_selon_exercices(marques)
    marque = any(m["calculatrice"] for m in marques)
    coupe = deux_parties(marques)                                 # v0.52.9 (D1)
    avert = ""
    # v0.52.9 (D1) — sujet en deux parties : les deux mentions sont imposées
    # (D2) et le réglage ne s'applique pas ; rien n'est « contraire ».
    if reglage and marque and reglage != selon and not coupe:
        avert = (f"Calculatrice réglée « {LIBELLES_CALCULATRICE_EVALUATION[reglage]} » à la "
                 f"main, mais les exercices de l'évaluation la marquent "
                 f"« {LIBELLES_CALCULATRICE_EVALUATION[selon]} » : le sujet suit le réglage.")
    return {"reglage": reglage, "selon_exercices": selon, "exercices_marques": marque,
            "valeur": reglage or selon, "avertissement": avert, "deux_parties": coupe}


# ── Évaluations : sujet en deux parties, façon DNB (v0.52.9) ─────────────────
#
# Besoin de Laurent (20 octobre) : « Si certains exercices interdisent
# explicitement la calculatrice et d'autres non, il faut faire comme pour le
# DNB : 2 sous-sujets. Le premier sans calculatrice, à ramasser après une
# durée en fonction du nombre d'exercices à faire, et le second sur une autre
# feuille qui est donnée en échange de la première. »

DUREE_SEANCE = 55            # minutes (D4)
DUREE_PARTIE1_MINIMUM = 10   # minutes (D4)
DUREE_PARTIE1_MAXIMUM = 240  # garde-fou de la saisie (D4)


def deux_parties(marques_ev: list) -> bool:
    """Décision D1 — Le sujet est coupé en deux **seulement** si l'évaluation
    contient au moins un exercice EV marqué `interdite` **et** au moins un
    marqué `autorisee` (mêmes exercices que la règle C1). Sinon : sujet d'un
    seul tenant, comportement v0.52.8 inchangé (mention C1 comprise)."""
    vals = {lire(m)["calculatrice"] for m in marques_ev}
    return {"interdite", "autorisee"} <= vals


def partie_de(ex) -> int:
    """Décision D2 — Partie 1 « Sans calculatrice » : les exercices marqués
    `interdite` ; partie 2 « Calculatrice autorisée » : tous les autres
    (autorisés et non marqués). Le bonus suit son propre marquage (non marqué
    → partie 2)."""
    return 1 if lire(ex)["calculatrice"] == "interdite" else 2


def duree_partie1_auto(points_partie1: float, total: float) -> int:
    """Décision D4 — N = durée de la séance (55 min) × points de la partie 1
    / total du barème (hors bonus, comme la colonne « Total »), arrondie aux
    5 min (la moitié vers le haut), au moins 10 min, au plus la séance."""
    if not total or total <= 0:
        return DUREE_PARTIE1_MINIMUM
    n = DUREE_SEANCE * float(points_partie1) / float(total)
    n = int(n / 5 + 0.5) * 5
    return max(DUREE_PARTIE1_MINIMUM, min(DUREE_SEANCE, n))


def valider_duree_partie1(valeur):
    """D4 — Saisie de la durée : None / '' = calcul automatique ; sinon un
    nombre entier de minutes entre 1 et 240. MarqueurInvalide sinon."""
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        return None
    if isinstance(valeur, bool):
        raise MarqueurInvalide(f"durée de la partie 1 invalide : {valeur!r}")
    try:
        f = float(str(valeur).strip().replace(",", "."))
    except ValueError:
        raise MarqueurInvalide(f"durée de la partie 1 invalide : {valeur!r}") from None
    if f != int(f) or not 1 <= f <= DUREE_PARTIE1_MAXIMUM:
        raise MarqueurInvalide(f"durée de la partie 1 invalide : {valeur!r} "
                               f"(minutes entières, 1 à {DUREE_PARTIE1_MAXIMUM})")
    return int(f)


# ── Plans de travail : encadré « Matériel à prévoir » ────────────────────────

# v0.52.8 (décision T1, Laurent, 20 octobre) — « Les TP sont à faire sur le
# temps personnel, donc l'enseignant n'a pas à réserver de matériel. » Les
# travaux personnels (série TP) gardent leur marqueur (fiche élève, ligne du
# plan de travail) mais n'entrent ni dans l'encadré « Matériel à prévoir » ni
# dans les données du tableau de bord (`partie.materiel` du format
# d'échange, `referentiel_materiel_publie`). Les autres séries (F, A, E, AE,
# AC, AT, EV, R, EA) restent comptées.
SERIES_HORS_MATERIEL = ("TP",)


def hors_materiel(serie: str | None, code_exercice: str | None = None) -> bool:
    """Vrai pour un travail personnel (série TP, ou code « TP03 ») : pas de
    matériel à réserver (T1)."""
    if (serie or "") in SERIES_HORS_MATERIEL:
        return True
    return any((code_exercice or "").startswith(s) for s in SERIES_HORS_MATERIEL)


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
