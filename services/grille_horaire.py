"""services/grille_horaire.py — v0.19.1.16

Grille horaire des créneaux de cours d'un établissement (collège).

Un établissement a une liste de créneaux M1..M4 (matin) et S1..S4
(après-midi), avec leurs horaires. C'est un paramétrage permanent, éditable
(les horaires varient d'un collège à l'autre, certains ont des séances de
90 min l'après-midi). Ces créneaux sont le socle de la saisie d'emploi du
temps (à venir) et de la projection des progressions « à la séance » sur des
dates/heures réelles.

Table `grille_horaire_creneaux(id, etablissement_id, code, libelle,
heure_debut, heure_fin, demi_journee, ordre)`, unique par
(etablissement_id, code).

API :
  - defauts() -> liste des 8 créneaux par défaut (modèle Hautes Ourmes)
  - peupler_defauts_si_vide(conn, etablissement_id) -> int (nb créés)
  - lister(conn, etablissement_id) -> list[dict]
  - creer(conn, etablissement_id, code, ...) -> dict
  - modifier(conn, creneau_id, champs) -> dict
  - supprimer(conn, creneau_id) -> None
"""

from __future__ import annotations
import uuid


class GrilleHoraireErreur(Exception):
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class CreneauIntrouvable(GrilleHoraireErreur):
    def __init__(self, creneau_id):
        super().__init__(f"Créneau {creneau_id!r} introuvable.",
                         "creneau_introuvable", creneau_id=creneau_id)


class DonneesInvalides(GrilleHoraireErreur):
    def __init__(self, message):
        super().__init__(message, "donnees_invalides")


def _rowid() -> str:
    return "gh_" + uuid.uuid4().hex[:12]


# Modèle par défaut : Collège les Hautes Ourmes.
# Matin : M1 8h25-9h20, M2 9h25-10h20, [pause], M3 10h35-11h30, M4 11h35-12h30
# Après-midi : S1 12h55-13h50, S2 13h55-14h50, [pause], S3 15h05-16h00,
#              S4 16h05-17h00.
_DEFAUTS = [
    ("M1", "08:25", "09:20", "M"),
    ("M2", "09:25", "10:20", "M"),
    ("M3", "10:35", "11:30", "M"),
    ("M4", "11:35", "12:30", "M"),
    ("S1", "12:55", "13:50", "S"),
    ("S2", "13:55", "14:50", "S"),
    ("S3", "15:05", "16:00", "S"),
    ("S4", "16:05", "17:00", "S"),
]


def defauts() -> list[dict]:
    """Liste des 8 créneaux par défaut (sans id ni établissement)."""
    return [
        {"code": code, "libelle": code, "heure_debut": hd,
         "heure_fin": hf, "demi_journee": dj, "ordre": (i + 1) * 10}
        for i, (code, hd, hf, dj) in enumerate(_DEFAUTS)
    ]


def peupler_defauts_si_vide(conn, etablissement_id: str) -> int:
    """Crée les créneaux par défaut pour un établissement s'il n'en a aucun.

    Idempotent : ne fait rien si l'établissement a déjà au moins un créneau.
    Retourne le nombre de créneaux créés.
    """
    n = conn.execute(
        "SELECT COUNT(*) FROM grille_horaire_creneaux WHERE etablissement_id=?",
        (etablissement_id,)).fetchone()[0]
    if n > 0:
        return 0
    crees = 0
    for d in defauts():
        conn.execute(
            "INSERT INTO grille_horaire_creneaux "
            "(id, etablissement_id, code, libelle, heure_debut, heure_fin, "
            " demi_journee, ordre) VALUES (?,?,?,?,?,?,?,?)",
            (_rowid(), etablissement_id, d["code"], d["libelle"],
             d["heure_debut"], d["heure_fin"], d["demi_journee"], d["ordre"]))
        crees += 1
    return crees


def lister(conn, etablissement_id: str) -> list[dict]:
    """Liste les créneaux d'un établissement, triés par ordre."""
    rows = conn.execute(
        "SELECT id, etablissement_id, code, libelle, heure_debut, heure_fin, "
        "demi_journee, ordre FROM grille_horaire_creneaux "
        "WHERE etablissement_id=? ORDER BY heure_debut, ordre, code",
        (etablissement_id,)).fetchall()
    return [dict(r) for r in rows]


def _valider_heure(h: str) -> str:
    """Normalise une heure 'HH:MM'. Chaîne vide autorisée (non renseignée)."""
    h = (h or "").strip()
    if not h:
        return ""
    parts = h.replace("h", ":").split(":")
    try:
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 and parts[1] != "" else 0
    except (ValueError, IndexError):
        raise DonneesInvalides(f"Heure invalide : {h!r}")
    if not (0 <= hh < 24 and 0 <= mm < 60):
        raise DonneesInvalides(f"Heure hors bornes : {h!r}")
    return f"{hh:02d}:{mm:02d}"


def creer(conn, etablissement_id: str, code: str, *,
          libelle: str = "", heure_debut: str = "", heure_fin: str = "",
          demi_journee: str = "M", ordre: int | None = None) -> dict:
    """Crée un créneau. Lève DonneesInvalides si code vide ou déjà présent."""
    code = (code or "").strip()
    if not code:
        raise DonneesInvalides("Le code du créneau est obligatoire.")
    exists = conn.execute(
        "SELECT 1 FROM grille_horaire_creneaux WHERE etablissement_id=? "
        "AND code=?", (etablissement_id, code)).fetchone()
    if exists:
        raise DonneesInvalides(f"Le créneau {code!r} existe déjà.")
    dj = demi_journee if demi_journee in ("M", "S") else "M"
    if ordre is None:
        r = conn.execute(
            "SELECT MAX(ordre) AS m FROM grille_horaire_creneaux "
            "WHERE etablissement_id=?", (etablissement_id,)).fetchone()
        ordre = ((r["m"] if r and r["m"] is not None else 0)) + 10
    new_id = _rowid()
    conn.execute(
        "INSERT INTO grille_horaire_creneaux "
        "(id, etablissement_id, code, libelle, heure_debut, heure_fin, "
        " demi_journee, ordre) VALUES (?,?,?,?,?,?,?,?)",
        (new_id, etablissement_id, code, (libelle or code).strip(),
         _valider_heure(heure_debut), _valider_heure(heure_fin), dj, ordre))
    return {"id": new_id, "etablissement_id": etablissement_id, "code": code,
            "libelle": (libelle or code).strip(),
            "heure_debut": _valider_heure(heure_debut),
            "heure_fin": _valider_heure(heure_fin),
            "demi_journee": dj, "ordre": ordre}


def modifier(conn, creneau_id: str, champs: dict) -> dict:
    """Modifie un créneau existant (libelle, heures, demi_journee, ordre)."""
    row = conn.execute(
        "SELECT * FROM grille_horaire_creneaux WHERE id=?",
        (creneau_id,)).fetchone()
    if row is None:
        raise CreneauIntrouvable(creneau_id)
    c = dict(row)
    if "libelle" in champs:
        c["libelle"] = (champs["libelle"] or "").strip()
    if "heure_debut" in champs:
        c["heure_debut"] = _valider_heure(champs["heure_debut"])
    if "heure_fin" in champs:
        c["heure_fin"] = _valider_heure(champs["heure_fin"])
    if "demi_journee" in champs and champs["demi_journee"] in ("M", "S"):
        c["demi_journee"] = champs["demi_journee"]
    if "ordre" in champs:
        try:
            c["ordre"] = int(champs["ordre"])
        except (TypeError, ValueError):
            pass
    conn.execute(
        "UPDATE grille_horaire_creneaux SET libelle=?, heure_debut=?, "
        "heure_fin=?, demi_journee=?, ordre=? WHERE id=?",
        (c["libelle"], c["heure_debut"], c["heure_fin"], c["demi_journee"],
         c["ordre"], creneau_id))
    return c


def supprimer(conn, creneau_id: str) -> None:
    """Supprime un créneau. Lève CreneauIntrouvable si absent.

    Refuse la suppression si le créneau est référencé par au moins une case
    d'emploi du temps (cohérence de l'EDT sur l'année courante) : lève
    DonneesInvalides avec un message explicite.
    """
    row = conn.execute(
        "SELECT etablissement_id, code FROM grille_horaire_creneaux WHERE id=?",
        (creneau_id,)).fetchone()
    if row is None:
        raise CreneauIntrouvable(creneau_id)
    # Garde de cohérence : un créneau utilisé dans l'EDT ne peut être supprimé.
    try:
        from services import edt as _edt
        if _edt.creneau_grille_est_reference(
                conn, row["etablissement_id"], row["code"]):
            raise DonneesInvalides(
                f"Le créneau {row['code']!r} est utilisé dans l'emploi du "
                f"temps ; retirez-le d'abord de l'EDT.")
    except ImportError:
        pass
    conn.execute("DELETE FROM grille_horaire_creneaux WHERE id=?",
                 (creneau_id,))
