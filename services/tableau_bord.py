"""services/tableau_bord.py — v0.30.0

Agrège les données des tuiles du tableau de bord (écran d'accueil). Chaque
fonction est autonome et renvoie une structure prête à afficher. Le tableau de
bord ne fait que présenter ces agrégats (pas de calcul métier côté client).

Tuiles de cette version :
  - atomes_en_cours_par_niveau  (T1 — conception : ce qui reste à finir)
  - seances_de_la_semaine       (T3 — suivi : séances MER + principale)
"""

from __future__ import annotations
from datetime import date, timedelta

# Types d'atomes portant un état de conception (etat_code) et un niveau.
# Les fiches ont une structure différente (ni etat_code ni niveau) : hors T1.
_TYPES_ETAT = [
    ("notion", "notions", "Notions"),
    ("methode", "methodes", "Méthodes"),
    ("exercice", "exercices", "Exercices"),
    ("carte", "cartes_automatisme", "Cartes"),
]

_NIVEAU_LABEL = {"N09": "6ème", "N10": "5ème", "N11": "4ème", "N12": "3ème"}


def atomes_en_cours_par_niveau(conn) -> list:
    """T1 — Pour chaque niveau ayant des atomes « en cours », le nombre
    d'atomes en cours par type. Représente le travail de conception qui reste
    à finaliser.

    Retour : [ {niveau, niveau_label, total, par_type: {type: n}}, ... ]
             trié par total décroissant (le plus de travail restant en tête).
    """
    par_niveau: dict = {}
    for type_code, table, _lbl in _TYPES_ETAT:
        try:
            rows = conn.execute(
                f"SELECT niveau, COUNT(*) AS n FROM {table} "
                f"WHERE etat_code = 'en_cours' AND niveau IS NOT NULL "
                f"AND niveau != '' GROUP BY niveau").fetchall()
        except Exception:
            rows = []
        for r in rows:
            niv = r["niveau"]
            d = par_niveau.setdefault(
                niv, {"niveau": niv,
                      "niveau_label": _NIVEAU_LABEL.get(niv, niv),
                      "total": 0, "par_type": {}})
            d["par_type"][type_code] = r["n"]
            d["total"] += r["n"]
    return sorted(par_niveau.values(), key=lambda x: -x["total"])


def atomes_non_rattaches_par_niveau(conn) -> list:
    """T2 — Pour chaque niveau ayant des atomes non rattachés (liés à aucun
    objectif), le nombre par type. Concerne les 5 types (exercice, notion,
    méthode, fiche, carte). Représente le travail de rattachement restant.

    Retour : [ {niveau, niveau_label, total, par_type: {type: n}}, ... ]
             trié par total décroissant.
    """
    from services.atomes_liste import (lister_atomes_sequence,
                                        TYPES_ATOMES_SUPPORTES)
    # type interne (tuile) : notion, methode, exercice, carte, fiche
    types = ["notion", "methode", "exercice", "carte", "fiche"]
    niveaux = [r["niveau"] for r in conn.execute(
        "SELECT DISTINCT niveau FROM notions WHERE niveau IS NOT NULL "
        "AND niveau != '' UNION SELECT DISTINCT niveau FROM exercices "
        "WHERE niveau IS NOT NULL AND niveau != ''").fetchall()]
    # Élargir aux niveaux connus (au cas où un type n'a pas de notion/exo).
    for extra in ("SELECT DISTINCT niveau FROM cartes_automatisme",
                  "SELECT DISTINCT niveau FROM methodes"):
        try:
            for r in conn.execute(extra).fetchall():
                if r[0] and r[0] not in niveaux:
                    niveaux.append(r[0])
        except Exception:
            pass

    par_niveau: dict = {}
    for niv in niveaux:
        for t in types:
            if t not in TYPES_ATOMES_SUPPORTES:
                continue
            try:
                atomes = lister_atomes_sequence(conn, t, niv, "")
            except Exception:
                atomes = []
            nb = sum(1 for a in atomes if not a.get("liens"))
            if nb:
                d = par_niveau.setdefault(
                    niv, {"niveau": niv,
                          "niveau_label": _NIVEAU_LABEL.get(niv, niv),
                          "total": 0, "par_type": {}})
                d["par_type"][t] = nb
                d["total"] += nb
    return sorted(par_niveau.values(), key=lambda x: -x["total"])


def _lundi_de(d: date) -> date:
    return d - timedelta(days=d.weekday())


def seances_de_la_semaine(conn, store, annee: str,
                          jour_reference: date | None = None) -> dict:
    """T3 — Les séances de la semaine en cours (MER + progression principale),
    toutes classes confondues, regroupées par jour.

    Retour : {
      "lundi": iso, "vendredi": iso,
      "jours": [ {jour, date, seances: [ {classe, creneau, type, libelle} ]} ]
    }
    où type ∈ {"principale", "mer_auto", "mer_prog"}.

    Réutilise la projection existante (EdT × calendrier × indisponibilités) via
    les services déjà en place ; ici on se limite à un agrégat léger basé sur
    l'EdT de la semaine (les plannings détaillés restent dans leurs onglets).
    """
    ref = jour_reference or date.today()
    lundi = _lundi_de(ref)
    vendredi = lundi + timedelta(days=4)

    jours_codes = ["lun", "mar", "mer", "jeu", "ven"]
    jours = [{"jour": j,
              "date": (lundi + timedelta(days=i)).isoformat(),
              "seances": []}
             for i, j in enumerate(jours_codes)]
    idx_jour = {j["jour"]: j for j in jours}

    # v0.41.2 — Séances de la semaine telles que la projection les voit
    # (alternance A/B, versions d'EdT, fériés, rentrée, exceptions MER).
    from services import contexte_projection as ctx
    with store._conn() as c2:
        for x in ctx.seances_de_la_semaine(c2, store, annee, lundi.isoformat()):
            if x["jour"] not in idx_jour:
                continue
            idx_jour[x["jour"]]["seances"].append({
                "classe": x["classe"],
                "creneau": x["creneau"],
                "type": x["type_mer"] or "principale",
                "libelle": x["libelle"],
            })
    # Trier les séances de chaque jour par créneau puis classe.
    for j in jours:
        j["seances"].sort(key=lambda s: (s["creneau"], s["classe"]))
    return {"lundi": lundi.isoformat(), "vendredi": vendredi.isoformat(),
            "jours": jours}
