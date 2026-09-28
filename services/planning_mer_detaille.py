"""services/planning_mer_detaille.py — v0.26.1

Assemble le planning de progression MER en « frise chronologique », sur le même
modèle que le planning des automatismes : blocs période (jours de séance) /
vacances, avec sous chaque date la PARTIE MER travaillée ce jour-là (au lieu des
enveloppes Leitner).

Réutilise les helpers de planning_leitner_detaille (jours de l'année, vacances,
jour de cours de la classe) pour rester cohérent.
"""

from __future__ import annotations
from datetime import date

from services import indisponibilites as ind_svc
from services import planning_leitner_detaille as pld
from services import progression_mer as pm


def assembler(seances: list, parties: list, vacances: list, feries: dict,
              indispos: list, grille: list, classe_id: str,
              annee: str) -> list:
    """Construit les blocs période/vacances. Chaque jour de séance porte la
    partie MER en cours (kind='seance' + mer_libelle/mer_rang…), ou 'ferie' /
    'indispo'.

    seances : séances projetées et datées (non encore enrichies MER).
    parties : parties posées (ordre), pour la projection MER.
    """
    # Enrichir les séances de la partie MER en cours (projection à la séance).
    seances_mer = pm.projeter_mer(seances, parties)
    ordre_creneau = {g["code"]: g.get("ordre", 0) for g in grille}
    # Plusieurs séances peuvent tomber le même jour (créneaux différents) :
    # indexer par date en LISTE, triée par ordre de créneau.
    par_date: dict = {}
    for s in seances_mer:
        par_date.setdefault(s["date"], []).append(s)
    for d_iso in par_date:
        par_date[d_iso].sort(key=lambda x: ordre_creneau.get(
            x.get("creneau_code"), 0))

    dates_indispo = set()
    for jiso in pld._lister_jours_annee(annee):
        for ind in indispos:
            faux = {"date": jiso, "creneau_code": ""}
            if ind_svc.concerne_seance(ind, faux, classe_id, ordre_creneau) \
                    and ind.get("type") == "journees":
                dates_indispo.add(jiso)

    blocs: list = []
    periode: list = []
    vac_en_cours = None
    for jiso in pld._lister_jours_annee(annee):
        j = date.fromisoformat(jiso)
        est_vac, pvac = pld._en_vacances(j, vacances)
        if est_vac:
            if periode:
                blocs.append({"type": "periode", "jours": periode})
                periode = []
            nom = pld._nom_vacances(pvac)
            if vac_en_cours != nom:
                blocs.append({"type": "vacances", "nom": nom})
                vac_en_cours = nom
            continue
        vac_en_cours = None
        seances_jour = par_date.get(jiso)
        if seances_jour:
            for s in seances_jour:
                periode.append({
                    "date": jiso, "jour_court": pld._jour_court(jiso),
                    "creneau_code": s.get("creneau_code", ""),
                    "kind": "seance",
                    "mer_libelle": s.get("mer_libelle", ""),
                    "mer_sequence": s.get("mer_sequence", ""),
                    "mer_rang": s.get("mer_rang_partie", 0),
                    "mer_nb": s.get("mer_nb_partie", 0),
                    "epuise": s.get("mer_partie_id") is None,
                })
        elif jiso in feries:
            if pld._jour_de_cours_classe(j, seances_mer):
                periode.append({"date": jiso, "jour_court": pld._jour_court(jiso),
                                "kind": "ferie"})
        elif jiso in dates_indispo:
            if pld._jour_de_cours_classe(j, seances_mer):
                periode.append({"date": jiso, "jour_court": pld._jour_court(jiso),
                                "kind": "indispo"})
    if periode:
        blocs.append({"type": "periode", "jours": periode})
    return blocs
