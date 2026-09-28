"""services/edt.py — v0.19.1.17

Emploi du temps de l'enseignant (application mono-utilisateur), ancré sur une
année scolaire.

Une ligne `edt_creneaux` = une case de l'EDT : un créneau horaire (M1..S4,
défini par la grille horaire de l'établissement) un jour donné, en semaine A, B
ou AB (toutes semaines). Le champ `usage` distingue ce qui compte pour les
progressions « à la séance » du reste :

  - classe_entiere            : cours en classe entière (SEUL usage compté
                                pour l'instant dans les progressions)
  - demi_classe_A / _B        : cours en demi-classe (présent dans l'EDT, pas
                                encore compté ; à cadrer : 1 séance pour 2
                                groupes)
  - groupe_option             : groupe d'élèves en horaire aménagé (option)
  - groupe_horaire_ordinaire  : groupe d'élèves à horaire ordinaire
  - autre                     : vie de classe, projets hors discipline,
                                concertation, co-animation… (affiché, jamais
                                compté)

Cohérence (année courante) : `creneau_code` doit exister dans la grille
horaire de l'établissement. La suppression d'un créneau de grille référencé par
l'EDT est refusée (cf. `creneau_grille_est_reference`). L'archivage des années
passées (avec grille figée) sera cadré ultérieurement.

API :
  - USAGES, JOURS, SEMAINES (constantes de validation)
  - lister(conn, annee, classe_id=None) -> list[dict]
  - ajouter(conn, annee, jour, creneau_code, etablissement_id, ...) -> dict
  - modifier(conn, edt_id, champs) -> dict
  - supprimer(conn, edt_id) -> None
  - compter_seances(conn, classe_id, annee) -> {"A": int, "B": int}
  - creneau_grille_est_reference(conn, etablissement_id, code) -> bool
"""

from __future__ import annotations
import uuid

# Le « groupe » indique À QUI on fait cours sur ce créneau.
GROUPES = (
    "classe_entiere",
    "demi_classe_A",
    "demi_classe_B",
    "groupe_option",
    "groupe_horaire_ordinaire",
    "autre",
)
# L'« usage » indique CE QU'ON FAIT sur ce créneau.
USAGES = (
    "cours",
    "vie_de_classe",
    "co_animation",
    "autre",
)
# Compte pour les progressions « à la séance » : un cours en classe entière.
GROUPES_COMPTES = ("classe_entiere",)
USAGES_COMPTES = ("cours",)

JOURS = ("lun", "mar", "mer", "jeu", "ven", "sam")
SEMAINES = ("A", "B", "AB")


class EdtErreur(Exception):
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class CreneauEdtIntrouvable(EdtErreur):
    def __init__(self, edt_id):
        super().__init__(f"Créneau d'EDT {edt_id!r} introuvable.",
                         "edt_introuvable", edt_id=edt_id)


class DonneesInvalides(EdtErreur):
    def __init__(self, message):
        super().__init__(message, "donnees_invalides")


def _rowid() -> str:
    return "edt_" + uuid.uuid4().hex[:12]


def _grille_code_existe(conn, etablissement_id: str, code: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM grille_horaire_creneaux "
        "WHERE etablissement_id=? AND code=?",
        (etablissement_id, code)).fetchone() is not None


def creneau_grille_est_reference(conn, etablissement_id: str, code: str) -> bool:
    """Vrai si un créneau de la grille est référencé par au moins une ligne
    d'EDT (toutes années). Utilisé pour protéger la grille contre une
    suppression qui rendrait l'EDT incohérent."""
    return conn.execute(
        "SELECT 1 FROM edt_creneaux "
        "WHERE etablissement_id=? AND creneau_code=?",
        (etablissement_id, code)).fetchone() is not None


def lister(conn, annee: str, classe_id: str | None = None) -> list[dict]:
    """Liste les cases d'EDT d'une année, avec les horaires du créneau
    (jointure grille horaire). Optionnellement filtré par classe."""
    params = [annee]
    where = "e.annee = ?"
    if classe_id is not None:
        where += " AND e.classe_id = ?"
        params.append(classe_id)
    rows = conn.execute(f"""
        SELECT e.id, e.annee, e.jour, e.creneau_code, e.semaine, e.classe_id,
               e.etablissement_id, e.libelle, e.groupe, e.usage, e.ordre,
               g.heure_debut, g.heure_fin, g.demi_journee,
               g.ordre AS creneau_ordre
        FROM edt_creneaux e
        LEFT JOIN grille_horaire_creneaux g
               ON g.etablissement_id = e.etablissement_id
              AND g.code = e.creneau_code
        WHERE {where}
        ORDER BY e.jour, creneau_ordre, e.creneau_code
    """, params).fetchall()
    jour_rang = {j: i for i, j in enumerate(JOURS)}
    items = [dict(r) for r in rows]
    # Tri stable jour (lun..sam) puis ordre de créneau.
    items.sort(key=lambda r: (jour_rang.get(r["jour"], 99),
                              r["creneau_ordre"] if r["creneau_ordre"] is not None else 99))
    # Signaler les créneaux orphelins (code absent de la grille actuelle).
    for it in items:
        it["creneau_inconnu"] = it["heure_debut"] is None
    return items


def ajouter(conn, annee: str, jour: str, creneau_code: str,
            etablissement_id: str, *, semaine: str = "AB",
            classe_id: str | None = None, libelle: str = "",
            groupe: str = "classe_entiere", usage: str = "cours",
            ordre: int | None = None) -> dict:
    """Ajoute une case d'EDT. Valide jour/semaine/groupe/usage et l'existence
    du créneau dans la grille horaire de l'établissement. Refuse les doublons
    (même annee/jour/creneau/semaine/établissement)."""
    jour = (jour or "").strip().lower()
    if jour not in JOURS:
        raise DonneesInvalides(f"Jour invalide : {jour!r} (attendu {JOURS}).")
    if semaine not in SEMAINES:
        raise DonneesInvalides(
            f"Semaine invalide : {semaine!r} (attendu {SEMAINES}).")
    if groupe not in GROUPES:
        raise DonneesInvalides(f"Groupe invalide : {groupe!r}.")
    if usage not in USAGES:
        raise DonneesInvalides(f"Usage invalide : {usage!r}.")
    code = (creneau_code or "").strip()
    if not code:
        raise DonneesInvalides("Le code de créneau est obligatoire.")
    if not _grille_code_existe(conn, etablissement_id, code):
        raise DonneesInvalides(
            f"Le créneau {code!r} n'existe pas dans la grille horaire de "
            f"l'établissement.")
    # Doublon ?
    exists = conn.execute(
        "SELECT 1 FROM edt_creneaux WHERE annee=? AND jour=? AND "
        "creneau_code=? AND semaine=? AND etablissement_id=?",
        (annee, jour, code, semaine, etablissement_id)).fetchone()
    if exists:
        raise DonneesInvalides(
            f"Une case existe déjà pour {jour} {code} (semaine {semaine}).")
    # Cohérence AB vs A/B : un même créneau ne peut porter à la fois une case
    # « toutes semaines » (AB) et une case propre à la semaine A ou B — ce
    # serait contradictoire. On refuse le mélange.
    autres = [r["semaine"] for r in conn.execute(
        "SELECT semaine FROM edt_creneaux WHERE annee=? AND jour=? AND "
        "creneau_code=? AND etablissement_id=?",
        (annee, jour, code, etablissement_id)).fetchall()]
    if semaine == "AB" and any(s in ("A", "B") for s in autres):
        raise DonneesInvalides(
            f"Le créneau {jour} {code} a déjà une saisie en semaine A ou B ; "
            f"impossible d'ajouter « toutes semaines » (AB).")
    if semaine in ("A", "B") and "AB" in autres:
        raise DonneesInvalides(
            f"Le créneau {jour} {code} est déjà saisi en « toutes semaines » "
            f"(AB) ; retirez-le d'abord pour différencier A et B.")
    if ordre is None:
        r = conn.execute(
            "SELECT MAX(ordre) AS m FROM edt_creneaux WHERE annee=?",
            (annee,)).fetchone()
        ordre = ((r["m"] if r and r["m"] is not None else 0)) + 10
    new_id = _rowid()
    conn.execute(
        "INSERT INTO edt_creneaux "
        "(id, annee, jour, creneau_code, semaine, classe_id, "
        " etablissement_id, libelle, groupe, usage, ordre) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (new_id, annee, jour, code, semaine, classe_id, etablissement_id,
         (libelle or "").strip(), groupe, usage, ordre))
    return {"id": new_id, "annee": annee, "jour": jour, "creneau_code": code,
            "semaine": semaine, "classe_id": classe_id,
            "etablissement_id": etablissement_id,
            "libelle": (libelle or "").strip(), "groupe": groupe,
            "usage": usage, "ordre": ordre}


def modifier(conn, edt_id: str, champs: dict) -> dict:
    """Modifie une case d'EDT (semaine, classe_id, libelle, usage, ordre).
    Le couple jour/creneau_code n'est pas modifiable ici (supprimer/rajouter)."""
    row = conn.execute("SELECT * FROM edt_creneaux WHERE id=?",
                       (edt_id,)).fetchone()
    if row is None:
        raise CreneauEdtIntrouvable(edt_id)
    c = dict(row)
    if "semaine" in champs:
        if champs["semaine"] not in SEMAINES:
            raise DonneesInvalides(f"Semaine invalide : {champs['semaine']!r}.")
        c["semaine"] = champs["semaine"]
    if "groupe" in champs:
        if champs["groupe"] not in GROUPES:
            raise DonneesInvalides(f"Groupe invalide : {champs['groupe']!r}.")
        c["groupe"] = champs["groupe"]
    if "usage" in champs:
        if champs["usage"] not in USAGES:
            raise DonneesInvalides(f"Usage invalide : {champs['usage']!r}.")
        c["usage"] = champs["usage"]
    if "classe_id" in champs:
        c["classe_id"] = champs["classe_id"] or None
    if "libelle" in champs:
        c["libelle"] = (champs["libelle"] or "").strip()
    if "ordre" in champs:
        try:
            c["ordre"] = int(champs["ordre"])
        except (TypeError, ValueError):
            pass
    # Contrôle d'unicité si la semaine change (le reste de la clé est fixe).
    dup = conn.execute(
        "SELECT 1 FROM edt_creneaux WHERE annee=? AND jour=? AND "
        "creneau_code=? AND semaine=? AND etablissement_id=? AND id<>?",
        (c["annee"], c["jour"], c["creneau_code"], c["semaine"],
         c["etablissement_id"], edt_id)).fetchone()
    if dup:
        raise DonneesInvalides(
            f"Une autre case existe déjà pour {c['jour']} {c['creneau_code']} "
            f"(semaine {c['semaine']}).")
    conn.execute(
        "UPDATE edt_creneaux SET semaine=?, classe_id=?, libelle=?, groupe=?, "
        "usage=?, ordre=? WHERE id=?",
        (c["semaine"], c["classe_id"], c["libelle"], c.get("groupe",
         "classe_entiere"), c["usage"], c["ordre"], edt_id))
    return c


def supprimer(conn, edt_id: str) -> None:
    """Supprime une case d'EDT. Lève CreneauEdtIntrouvable si absente."""
    row = conn.execute("SELECT 1 FROM edt_creneaux WHERE id=?",
                       (edt_id,)).fetchone()
    if row is None:
        raise CreneauEdtIntrouvable(edt_id)
    conn.execute("DELETE FROM edt_creneaux WHERE id=?", (edt_id,))


def est_compte(case: dict) -> bool:
    """Vrai si une case d'EDT compte pour les progressions : cours en classe
    entière (groupe ∈ GROUPES_COMPTES ET usage ∈ USAGES_COMPTES)."""
    return (case.get("groupe", "classe_entiere") in GROUPES_COMPTES
            and case.get("usage", "cours") in USAGES_COMPTES)


def compter_seances(conn, classe_id: str, annee: str) -> dict:
    """Nombre de séances par type de semaine pour une classe, dérivé de l'EDT.

    Ne compte que les cours en classe entière : groupe ∈ GROUPES_COMPTES
    (classe_entiere) ET usage ∈ USAGES_COMPTES (cours).
    Semaine A = (semaine 'A') + (semaine 'AB') ; idem pour B.
    """
    pg = ",".join("?" * len(GROUPES_COMPTES))
    pu = ",".join("?" * len(USAGES_COMPTES))
    rows = conn.execute(
        f"SELECT semaine, COUNT(*) AS n FROM edt_creneaux "
        f"WHERE classe_id=? AND annee=? AND groupe IN ({pg}) "
        f"AND usage IN ({pu}) GROUP BY semaine",
        (classe_id, annee, *GROUPES_COMPTES, *USAGES_COMPTES)).fetchall()
    par_sem = {r["semaine"]: r["n"] for r in rows}
    ab = par_sem.get("AB", 0)
    return {"A": par_sem.get("A", 0) + ab, "B": par_sem.get("B", 0) + ab}
