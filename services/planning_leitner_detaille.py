"""services/planning_leitner_detaille.py — v0.24.0

Assemble un planning d'automatismes « frise chronologique » : pour chaque
période de cours (entre deux vacances), la suite des jours de séance avec, sous
chaque date, soit les enveloppes Leitner à réviser, soit un marqueur « férié »
ou « indisponible ». Les périodes de vacances servent de séparateurs.

Structure de sortie : liste ordonnée de « blocs » :
  {"type": "periode", "jours": [ {date, jour_court, kind, enveloppes} , … ]}
  {"type": "vacances", "nom": "Vacances d'automne"}

où kind ∈ {"seance", "ferie", "indispo"}.

Fonction pure (reçoit séances projetées + vacances + fériés + indispos déjà
récupérés). L'orchestration (récupération) est faite dans la route.
"""

from __future__ import annotations
from datetime import date, timedelta

from services import leitner
from services import indisponibilites as ind_svc

_JOURS_FR = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]


def _iso(d: date) -> str:
    return d.isoformat()


def _jour_court(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
        return f"{_JOURS_FR[d.weekday()]} {d.day:02d}/{d.month:02d}"
    except ValueError:
        return iso


def _nom_vacances(periode: dict) -> str:
    """Nom lisible d'une période de vacances (depuis sa description)."""
    return (periode.get("description") or "Vacances").strip()


def _en_vacances(jour: date, vacances: list) -> tuple[bool, dict | None]:
    iso = _iso(jour)
    for p in vacances:
        deb = p.get("start_date") or ""
        fin = p.get("end_date") or ""
        if deb and fin and deb <= iso < fin:
            return True, p
    return False, None


def assembler(seances: list, vacances: list, feries: dict,
              indispos: list, grille: list, classe_id: str,
              annee: str) -> list:
    """Construit la liste de blocs (périodes de cours + séparateurs vacances).

    seances : séances projetées (mode auto pur) — {numero, date, ...}. Elles
              portent déjà les enveloppes via leitner.planning.
    vacances: périodes {description, start_date, end_date}.
    feries  : {date_iso: nom}.
    indispos: indisponibilités (pour marquer les dates concernées).
    """
    # 1. Séances datées, avec enveloppes. Plusieurs séances peuvent tomber le
    #    MÊME jour (créneaux différents, ex. mardi M1 et mardi M4) : on indexe
    #    par date en LISTE, triée par ordre de créneau dans la journée.
    seances_env = leitner.planning(seances)
    ordre_creneau = {g["code"]: g.get("ordre", 0) for g in grille}
    par_date: dict = {}
    for s in seances_env:
        par_date.setdefault(s["date"], []).append(s)
    for d_iso in par_date:
        par_date[d_iso].sort(key=lambda x: ordre_creneau.get(
            x.get("creneau_code"), 0))

    # 2. Dates d'indisponibilité qui concernent cette classe.
    dates_indispo = set()
    for jiso in _lister_jours_annee(annee):
        j = date.fromisoformat(jiso)
        for ind in indispos:
            faux_seance = {"date": jiso, "creneau_code": ""}
            if ind_svc.concerne_seance(ind, faux_seance, classe_id,
                                       ordre_creneau) and \
                    ind.get("type") == "journees":
                dates_indispo.add(jiso)

    # 3. Construire les blocs période/vacances en parcourant l'année.
    blocs: list = []
    periode_courante: list = []
    vac_en_cours: str | None = None

    for jiso in _lister_jours_annee(annee):
        j = date.fromisoformat(jiso)
        est_vac, pvac = _en_vacances(j, vacances)
        if est_vac:
            if periode_courante:
                blocs.append({"type": "periode", "jours": periode_courante})
                periode_courante = []
            nom = _nom_vacances(pvac)
            if vac_en_cours != nom:
                blocs.append({"type": "vacances", "nom": nom})
                vac_en_cours = nom
            continue
        vac_en_cours = None
        seances_jour = par_date.get(jiso)
        if seances_jour:
            # Une entrée par séance du jour (plusieurs créneaux possibles).
            for s in seances_jour:
                periode_courante.append({
                    "date": jiso, "jour_court": _jour_court(jiso),
                    "creneau_code": s.get("creneau_code", ""),
                    "kind": "seance", "enveloppes": s.get("enveloppes", []),
                })
        elif jiso in feries:
            if _jour_de_cours_classe(j, seances_env):
                periode_courante.append({
                    "date": jiso, "jour_court": _jour_court(jiso),
                    "kind": "ferie", "enveloppes": [],
                })
        elif jiso in dates_indispo:
            if _jour_de_cours_classe(j, seances_env):
                periode_courante.append({
                    "date": jiso, "jour_court": _jour_court(jiso),
                    "kind": "indispo", "enveloppes": [],
                })

    if periode_courante:
        blocs.append({"type": "periode", "jours": periode_courante})
    return blocs


def _jour_de_cours_classe(j: date, seances_env: list) -> bool:
    """Vrai si le jour de la semaine de `j` correspond à un jour où la classe a
    au moins une séance (déduit des séances projetées)."""
    jours = {_JOURS_FR[date.fromisoformat(s["date"]).weekday()]
             for s in seances_env}
    return _JOURS_FR[j.weekday()] in jours


def _lister_jours_annee(annee: str):
    """Itère les jours (ISO) de l'année scolaire, 1er sept → 31 juillet."""
    d0 = int(annee.split("-")[0])
    cur = date(d0, 9, 1)
    fin = date(d0 + 1, 7, 31)
    while cur <= fin:
        yield _iso(cur)
        cur += timedelta(days=1)
