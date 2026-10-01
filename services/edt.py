"""services/edt.py — v0.19.1.17 (v0.38.0 : EdT versionné)

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

v0.38.0 — EdT versionné (cf. doc/cadrage_plans_de_classe.md) :
  - chaque case porte une période [valide_du, valide_au) en lundis ISO
    ('' = début / fin d'année), une salle (`salle_id`) et un nombre d'AESH ;
  - EdT « en saisie » (par année × établissement) : modifications sur place,
    valables toute l'année, aucun changement daté ;
  - EdT « figé » (définitif) : plus de modification sur place, sauf libellé
    et ordre ; tout autre changement prend effet un lundi ≥ semaine
    prochaine (pas de rétroactivité) : la case en cours est scindée, la
    nouvelle période hérite des affectations de séance ;
  - la projection des séances filtre les cases semaine par semaine
    (`valide_a`), d'où une numérotation continue à travers les changements.

API :
  - USAGES, JOURS, SEMAINES (constantes de validation)
  - lister(conn, annee, classe_id=None, *, a_la_date=None,
           etablissement_id=None) -> list[dict]
  - ajouter(conn, annee, jour, creneau_code, etablissement_id, ...,
            a_partir_du=None, aujourd_hui=None) -> dict
  - modifier(conn, edt_id, champs, *, a_partir_du=None, aujourd_hui=None)
  - supprimer(conn, edt_id, *, a_partir_du=None, aujourd_hui=None)
  - etat / figer / changements_programmes / annuler_changement /
    appliquer_salle
  - compter_seances(conn, classe_id, annee, a_la_date=None) -> {"A", "B"}
  - creneau_grille_est_reference(conn, etablissement_id, code) -> bool
"""

from __future__ import annotations
import uuid
from datetime import date, timedelta

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


def lister(conn, annee: str, classe_id: str | None = None, *,
           a_la_date: date | None = None,
           etablissement_id: str | None = None) -> list[dict]:
    """Liste les cases d'EDT d'une année, avec les horaires du créneau
    (jointure grille horaire) et le nom de la salle. Optionnellement filtré
    par classe et/ou établissement.

    v0.38.0 — Sans `a_la_date`, renvoie TOUTES les périodes (chaque case porte
    `valide_du` / `valide_au`) : c'est ce qu'attend la projection, qui filtre
    semaine par semaine. Avec `a_la_date`, ne renvoie que les cases valides la
    semaine de cette date (vues hebdomadaires, comptages « actuels »)."""
    params = [annee]
    where = "e.annee = ?"
    if classe_id is not None:
        where += " AND e.classe_id = ?"
        params.append(classe_id)
    if etablissement_id is not None:
        where += " AND e.etablissement_id = ?"
        params.append(etablissement_id)
    if a_la_date is not None:
        lun = lundi_de(a_la_date).isoformat()
        where += (" AND (e.valide_du = '' OR e.valide_du <= ?)"
                  " AND (e.valide_au = '' OR e.valide_au > ?)")
        params += [lun, lun]
    rows = conn.execute(f"""
        SELECT e.id, e.annee, e.jour, e.creneau_code, e.semaine, e.classe_id,
               e.etablissement_id, e.libelle, e.groupe, e.usage, e.ordre,
               e.valide_du, e.valide_au, e.salle_id, e.nb_aesh,
               s.nom AS salle_nom,
               g.heure_debut, g.heure_fin, g.demi_journee,
               g.ordre AS creneau_ordre
        FROM edt_creneaux e
        LEFT JOIN grille_horaire_creneaux g
               ON g.etablissement_id = e.etablissement_id
              AND g.code = e.creneau_code
        LEFT JOIN salles s ON s.id = e.salle_id
        WHERE {where}
        ORDER BY e.jour, creneau_ordre, e.creneau_code, e.valide_du
    """, params).fetchall()
    jour_rang = {j: i for i, j in enumerate(JOURS)}
    items = [dict(r) for r in rows]
    # Tri stable jour (lun..sam) puis ordre de créneau.
    items.sort(key=lambda r: (jour_rang.get(r["jour"], 99),
                              r["creneau_ordre"] if r["creneau_ordre"] is not None else 99,
                              r["valide_du"]))
    # Signaler les créneaux orphelins (code absent de la grille actuelle).
    for it in items:
        it["creneau_inconnu"] = it["heure_debut"] is None
    return items


# ── v0.38.0 — Dates, états, périodes ─────────────────────────────────────────

def lundi_de(d: date) -> date:
    return d - timedelta(days=d.weekday())


def prochain_lundi(aujourd_hui: date) -> date:
    """Premier lundi STRICTEMENT après la semaine en cours."""
    return lundi_de(aujourd_hui) + timedelta(days=7)


def valide_a(case: dict, lundi_iso: str) -> bool:
    """Vrai si la case est valide la semaine commençant à `lundi_iso`."""
    du, au = case.get("valide_du") or "", case.get("valide_au") or ""
    return (not du or du <= lundi_iso) and (not au or lundi_iso < au)


def _periodes_chevauchent(du1, au1, du2, au2) -> bool:
    d1, f1 = du1 or "0000-00-00", au1 or "9999-99-99"
    d2, f2 = du2 or "0000-00-00", au2 or "9999-99-99"
    return d1 < f2 and d2 < f1


def _semaines_chevauchent(s1: str, s2: str) -> bool:
    return s1 == s2 or "AB" in (s1, s2)


def etat(conn, annee: str, etablissement_id: str) -> dict:
    """État de l'EdT d'une année pour un établissement : 'en_saisie'
    (modifications sur place, pas de changement daté) ou 'fige' (plus de
    modification sur place hors libellé, changements datés à partir d'un
    lundi ≥ semaine prochaine). Le figeage est définitif."""
    r = conn.execute("SELECT etat, date_figeage FROM edt_etats "
                     "WHERE annee=? AND etablissement_id=?",
                     (annee, etablissement_id)).fetchone()
    if r is None:
        return {"etat": "en_saisie", "date_figeage": ""}
    return {"etat": r["etat"], "date_figeage": r["date_figeage"]}


def figer(conn, annee: str, etablissement_id: str, aujourd_hui: date) -> dict:
    if etat(conn, annee, etablissement_id)["etat"] == "fige":
        raise DonneesInvalides("L'emploi du temps est déjà figé.")
    conn.execute(
        "INSERT INTO edt_etats (annee, etablissement_id, etat, date_figeage) "
        "VALUES (?,?, 'fige', ?) ON CONFLICT(annee, etablissement_id) "
        "DO UPDATE SET etat='fige', date_figeage=excluded.date_figeage",
        (annee, etablissement_id, aujourd_hui.isoformat()))
    return etat(conn, annee, etablissement_id)


def _est_fige(conn, annee, etablissement_id) -> bool:
    return etat(conn, annee, etablissement_id)["etat"] == "fige"


def _date_effet(a_partir_du, aujourd_hui: date) -> str:
    """Valide une date d'effet (lundi ≥ semaine prochaine) pour un EdT figé."""
    if not a_partir_du:
        raise DonneesInvalides(
            "L'emploi du temps est figé : indiquer le lundi à partir duquel "
            "le changement s'applique.")
    try:
        d = date.fromisoformat(str(a_partir_du).strip())
    except ValueError:
        raise DonneesInvalides(f"Date d'effet invalide : {a_partir_du!r}.")
    if d.weekday() != 0:
        raise DonneesInvalides(f"La date d'effet {d.isoformat()} n'est pas un lundi.")
    mini = prochain_lundi(aujourd_hui)
    if d < mini:
        raise DonneesInvalides(
            f"Pas de modification rétroactive : le changement prend effet au "
            f"plus tôt le {mini.isoformat()}.")
    return d.isoformat()


def _refuser_date_en_saisie(a_partir_du):
    if a_partir_du:
        raise DonneesInvalides(
            "L'emploi du temps est en saisie : les modifications valent pour "
            "toute l'année. Le figer pour programmer des changements datés.")


def _controle_conflit(conn, annee, etablissement_id, jour, code, semaine,
                      du, au, exclure=()) -> None:
    rows = conn.execute(
        "SELECT id, semaine, valide_du, valide_au FROM edt_creneaux "
        "WHERE annee=? AND etablissement_id=? AND jour=? AND creneau_code=?",
        (annee, etablissement_id, jour, code)).fetchall()
    for r in rows:
        if r["id"] in exclure:
            continue
        if (_semaines_chevauchent(semaine, r["semaine"])
                and _periodes_chevauchent(du, au, r["valide_du"], r["valide_au"])):
            if semaine == r["semaine"]:
                msg = f"Une case existe déjà pour {jour} {code} (semaine {semaine})"
            elif semaine == "AB":
                msg = (f"Le créneau {jour} {code} a déjà une saisie en semaine "
                       f"A ou B ; impossible d'ajouter « toutes semaines » (AB)")
            else:
                msg = (f"Le créneau {jour} {code} est déjà saisi en « toutes "
                       f"semaines » (AB) ; retirez-le d'abord pour différencier "
                       f"A et B")
            if r["valide_du"] or r["valide_au"] or du or au:
                msg += " sur cette période"
            raise DonneesInvalides(msg + ".")


def _valider_salle(conn, salle_id, etablissement_id):
    if not salle_id:
        return None
    r = conn.execute("SELECT etablissement_id, archivee, nom FROM salles "
                     "WHERE id=?", (salle_id,)).fetchone()
    if r is None or r["etablissement_id"] != etablissement_id:
        raise DonneesInvalides("Salle inconnue pour cet établissement.")
    return salle_id


def _valider_aesh(n) -> int:
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        raise DonneesInvalides(f"Nombre d'AESH invalide : {n!r}.")
    if not 0 <= n <= 5:
        raise DonneesInvalides("Nombre d'AESH attendu entre 0 et 5.")
    return n


_COLS = ("id, annee, jour, creneau_code, semaine, classe_id, etablissement_id, "
         "libelle, groupe, usage, ordre, valide_du, valide_au, salle_id, nb_aesh")


def _inserer(conn, c: dict) -> None:
    conn.execute(
        f"INSERT INTO edt_creneaux ({_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        tuple(c[k.strip()] for k in _COLS.split(",")))


def _lire(conn, edt_id: str) -> dict:
    row = conn.execute("SELECT * FROM edt_creneaux WHERE id=?",
                       (edt_id,)).fetchone()
    if row is None:
        raise CreneauEdtIntrouvable(edt_id)
    return dict(row)


def ajouter(conn, annee: str, jour: str, creneau_code: str,
            etablissement_id: str, *, semaine: str = "AB",
            classe_id: str | None = None, libelle: str = "",
            groupe: str = "classe_entiere", usage: str = "cours",
            ordre: int | None = None, salle_id: str | None = None,
            nb_aesh: int = 0, a_partir_du: str | None = None,
            aujourd_hui: date | None = None) -> dict:
    """Ajoute une case d'EDT. Valide jour/semaine/groupe/usage, l'existence
    du créneau dans la grille horaire, la salle, et l'absence de chevauchement
    avec une autre case du même créneau sur la même période.

    EdT en saisie : la case vaut toute l'année (pas de date d'effet).
    EdT figé : `a_partir_du` obligatoire (lundi ≥ semaine prochaine)."""
    aujourd_hui = aujourd_hui or date.today()
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
    if _est_fige(conn, annee, etablissement_id):
        du = _date_effet(a_partir_du, aujourd_hui)
    else:
        _refuser_date_en_saisie(a_partir_du)
        du = ""
    _controle_conflit(conn, annee, etablissement_id, jour, code, semaine, du, "")
    if ordre is None:
        r = conn.execute(
            "SELECT MAX(ordre) AS m FROM edt_creneaux WHERE annee=?",
            (annee,)).fetchone()
        ordre = ((r["m"] if r and r["m"] is not None else 0)) + 10
    c = {"id": _rowid(), "annee": annee, "jour": jour, "creneau_code": code,
         "semaine": semaine, "classe_id": classe_id,
         "etablissement_id": etablissement_id,
         "libelle": (libelle or "").strip(), "groupe": groupe, "usage": usage,
         "ordre": ordre, "valide_du": du, "valide_au": "",
         "salle_id": _valider_salle(conn, salle_id, etablissement_id),
         "nb_aesh": _valider_aesh(nb_aesh)}
    _inserer(conn, c)
    return c


# Champs modifiables « sur place » même quand l'EdT est figé (cosmétiques).
CHAMPS_SUR_PLACE = ("libelle", "ordre")


def _appliquer_champs(conn, c: dict, champs: dict) -> dict:
    c = dict(c)
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
    if "salle_id" in champs:
        c["salle_id"] = _valider_salle(conn, champs["salle_id"] or None,
                                       c["etablissement_id"])
    if "nb_aesh" in champs:
        c["nb_aesh"] = _valider_aesh(champs["nb_aesh"])
    return c


def _ecrire(conn, c: dict) -> None:
    conn.execute(
        "UPDATE edt_creneaux SET semaine=?, classe_id=?, libelle=?, groupe=?, "
        "usage=?, ordre=?, salle_id=?, nb_aesh=?, valide_du=?, valide_au=? "
        "WHERE id=?",
        (c["semaine"], c["classe_id"], c["libelle"], c["groupe"], c["usage"],
         c["ordre"], c["salle_id"], c["nb_aesh"], c["valide_du"],
         c["valide_au"], c["id"]))


def _structurel(avant: dict, apres: dict) -> bool:
    return any(avant.get(k) != apres.get(k) for k in
               ("semaine", "classe_id", "groupe", "usage", "salle_id", "nb_aesh"))


def _est_future(c: dict, aujourd_hui: date) -> bool:
    """Case qui ne commence qu'à partir de la semaine prochaine (ou après)."""
    return bool(c["valide_du"]) and c["valide_du"] >= prochain_lundi(aujourd_hui).isoformat()


def _copier_affectations(conn, source_id: str, cible_id: str) -> None:
    try:
        for r in conn.execute(
                "SELECT classe_id, annee, affectation FROM affectation_seance "
                "WHERE edt_creneau_id=?", (source_id,)).fetchall():
            conn.execute(
                "INSERT OR IGNORE INTO affectation_seance "
                "(id, classe_id, annee, edt_creneau_id, affectation) "
                "VALUES (?,?,?,?,?)",
                ("as_" + uuid.uuid4().hex[:12], r["classe_id"], r["annee"],
                 cible_id, r["affectation"]))
    except Exception:
        # Table absente (base très ancienne) : rien à hériter.
        pass


def _supprimer_ligne(conn, edt_id: str) -> None:
    try:
        conn.execute("DELETE FROM affectation_seance WHERE edt_creneau_id=?",
                     (edt_id,))
    except Exception:
        pass
    conn.execute("DELETE FROM edt_creneaux WHERE id=?", (edt_id,))


def modifier(conn, edt_id: str, champs: dict, *,
             a_partir_du: str | None = None,
             aujourd_hui: date | None = None) -> dict:
    """Modifie une case d'EDT (semaine, classe_id, groupe, usage, salle_id,
    nb_aesh, libelle, ordre). Le couple jour/creneau_code n'est pas
    modifiable ici (supprimer/rajouter).

    - EdT en saisie, ou changement cosmétique seul (libellé, ordre), ou case
      future : modification sur place.
    - EdT figé, case en cours : la case est scindée au lundi `a_partir_du`
      (l'ancienne période se termine, une nouvelle commence avec les nouvelles
      valeurs et hérite des affectations de séance). Retour : la nouvelle case,
      avec `scindee_de` = id de l'ancienne."""
    aujourd_hui = aujourd_hui or date.today()
    c = _lire(conn, edt_id)
    n = _appliquer_champs(conn, c, champs)
    fige = _est_fige(conn, c["annee"], c["etablissement_id"])
    if not fige:
        _refuser_date_en_saisie(a_partir_du)
    if not fige or not _structurel(c, n) or _est_future(c, aujourd_hui):
        _controle_conflit(conn, n["annee"], n["etablissement_id"], n["jour"],
                          n["creneau_code"], n["semaine"], n["valide_du"],
                          n["valide_au"], exclure=(edt_id,))
        _ecrire(conn, n)
        return n
    d = _date_effet(a_partir_du, aujourd_hui)
    if c["valide_au"] and d >= c["valide_au"]:
        raise DonneesInvalides(
            f"Cette case n'existe plus le {d} : rien à modifier à cette date.")
    nouvelle = {**n, "id": _rowid(), "valide_du": d, "valide_au": c["valide_au"]}
    _controle_conflit(conn, n["annee"], n["etablissement_id"], n["jour"],
                      n["creneau_code"], n["semaine"], d, c["valide_au"],
                      exclure=(edt_id,))
    conn.execute("UPDATE edt_creneaux SET valide_au=? WHERE id=?", (d, edt_id))
    _inserer(conn, nouvelle)
    _copier_affectations(conn, edt_id, nouvelle["id"])
    return {**nouvelle, "scindee_de": edt_id}


def supprimer(conn, edt_id: str, *, a_partir_du: str | None = None,
              aujourd_hui: date | None = None) -> None:
    """Supprime une case d'EDT. Lève CreneauEdtIntrouvable si absente.

    EdT en saisie, ou case future : suppression réelle. EdT figé, case en
    cours : la case se termine au lundi `a_partir_du`."""
    aujourd_hui = aujourd_hui or date.today()
    c = _lire(conn, edt_id)
    fige = _est_fige(conn, c["annee"], c["etablissement_id"])
    if not fige:
        _refuser_date_en_saisie(a_partir_du)
        _supprimer_ligne(conn, edt_id)
        return
    if _est_future(c, aujourd_hui):
        _supprimer_ligne(conn, edt_id)
        return
    d = _date_effet(a_partir_du, aujourd_hui)
    if c["valide_au"] and d >= c["valide_au"]:
        raise DonneesInvalides(f"Cette case n'existe déjà plus le {d}.")
    conn.execute("UPDATE edt_creneaux SET valide_au=? WHERE id=?", (d, edt_id))


def changements_programmes(conn, annee: str, etablissement_id: str,
                           aujourd_hui: date) -> list[dict]:
    """Lundis à venir où l'EdT change : [{lundi, debuts, fins}] (nombre de
    cases qui commencent / se terminent ce lundi-là)."""
    mini = prochain_lundi(aujourd_hui).isoformat()
    par_lundi: dict[str, dict] = {}
    for r in conn.execute(
            "SELECT valide_du, valide_au FROM edt_creneaux "
            "WHERE annee=? AND etablissement_id=?",
            (annee, etablissement_id)).fetchall():
        for cle, champ in (("debuts", "valide_du"), ("fins", "valide_au")):
            l = r[champ]
            if l and l >= mini:
                par_lundi.setdefault(l, {"lundi": l, "debuts": 0, "fins": 0})
                par_lundi[l][cle] += 1
    return [par_lundi[k] for k in sorted(par_lundi)]


def annuler_changement(conn, annee: str, etablissement_id: str, lundi: str,
                       aujourd_hui: date) -> None:
    """Annule tout ce qui était programmé pour le lundi donné (à venir) :
    les cases qui commencent ce lundi disparaissent, celles qui se terminaient
    ce lundi-là reprennent jusqu'à la fin de la case qui les remplaçait (ou
    jusqu'à la fin de l'année)."""
    if lundi < prochain_lundi(aujourd_hui).isoformat():
        raise DonneesInvalides("Seul un changement à venir peut être annulé.")
    base = ("SELECT * FROM edt_creneaux WHERE annee=? AND etablissement_id=? "
            "AND {} = ?")
    debuts = [dict(r) for r in conn.execute(
        base.format("valide_du"), (annee, etablissement_id, lundi)).fetchall()]
    fins = [dict(r) for r in conn.execute(
        base.format("valide_au"), (annee, etablissement_id, lundi)).fetchall()]
    if not debuts and not fins:
        raise DonneesInvalides(f"Aucun changement programmé le {lundi}.")
    for p in fins:
        succ = [s for s in debuts
                if s["jour"] == p["jour"] and s["creneau_code"] == p["creneau_code"]]
        aus = [s["valide_au"] for s in succ]
        nouvel_au = "" if (not succ or "" in aus) else max(aus)
        conn.execute("UPDATE edt_creneaux SET valide_au=? WHERE id=?",
                     (nouvel_au, p["id"]))
    for s in debuts:
        _supprimer_ligne(conn, s["id"])


def appliquer_salle(conn, annee: str, etablissement_id: str, salle_id: str, *,
                    a_partir_du: str | None = None,
                    aujourd_hui: date | None = None) -> int:
    """Met la salle sur toutes les cases de cours avec une classe (valides à
    la date d'effet, ou toute l'année si l'EdT est en saisie). Retourne le
    nombre de cases modifiées."""
    aujourd_hui = aujourd_hui or date.today()
    _valider_salle(conn, salle_id, etablissement_id)
    if _est_fige(conn, annee, etablissement_id):
        ref = date.fromisoformat(_date_effet(a_partir_du, aujourd_hui))
        cases = lister(conn, annee, etablissement_id=etablissement_id,
                       a_la_date=ref)
    else:
        _refuser_date_en_saisie(a_partir_du)
        cases = lister(conn, annee, etablissement_id=etablissement_id)
    n = 0
    for c in cases:
        if not c["classe_id"] or c["salle_id"] == salle_id:
            continue
        modifier(conn, c["id"], {"salle_id": salle_id},
                 a_partir_du=a_partir_du, aujourd_hui=aujourd_hui)
        n += 1
    return n


def est_compte(case: dict) -> bool:
    """Vrai si une case d'EDT compte pour les progressions : cours en classe
    entière (groupe ∈ GROUPES_COMPTES ET usage ∈ USAGES_COMPTES)."""
    return (case.get("groupe", "classe_entiere") in GROUPES_COMPTES
            and case.get("usage", "cours") in USAGES_COMPTES)


def compter_seances(conn, classe_id: str, annee: str,
                    a_la_date: date | None = None) -> dict:
    """Nombre de séances par type de semaine pour une classe, dérivé de l'EDT
    en vigueur la semaine de `a_la_date` (défaut : aujourd'hui).

    Ne compte que les cours en classe entière : groupe ∈ GROUPES_COMPTES
    (classe_entiere) ET usage ∈ USAGES_COMPTES (cours).
    Semaine A = (semaine 'A') + (semaine 'AB') ; idem pour B.
    """
    cases = [c for c in lister(conn, annee, classe_id=classe_id,
                               a_la_date=a_la_date or date.today())
             if est_compte(c)]
    par_sem: dict[str, int] = {}
    for c in cases:
        par_sem[c["semaine"]] = par_sem.get(c["semaine"], 0) + 1
    ab = par_sem.get("AB", 0)
    return {"A": par_sem.get("A", 0) + ab, "B": par_sem.get("B", 0) + ab}
