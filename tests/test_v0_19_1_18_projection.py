"""tests/test_v0_19_1_18_projection.py — v0.19.1.18

Projection des séances sur le calendrier (fonction pure, sans réseau).
Vérifie : bornes d'année, convention A/B (rentrée ignorée, 1re comptée = B),
saut des semaines entièrement en vacances (l'alternance ne progresse pas),
saut des jours fériés / vacances individuels, numérotation continue.
"""
from datetime import date

from services.projection_seances import projeter, bornes_annee


GRILLE = [
    {"code": "M1", "heure_debut": "08:25", "heure_fin": "09:20", "ordre": 10},
    {"code": "M2", "heure_debut": "09:25", "heure_fin": "10:20", "ordre": 20},
]
# Vacances d'été jusqu'au 1er sept (reprise le 01/09/2025).
VAC_ETE = [{"start_date": "2025-08-01", "end_date": "2025-09-01"}]


def test_bornes_1er_aout():
    assert bornes_annee("2025-2026") == (date(2025, 8, 1), date(2026, 7, 31))


def test_rentree_ignoree_et_premiere_semaine_B():
    edt = [{"jour": "lun", "creneau_code": "M1", "semaine": "AB"}]
    s = projeter("2025-2026", edt, GRILLE, VAC_ETE, {})
    # Semaine du 1er sept = rentrée ignorée ; 1re comptée = 8 sept, sem B.
    assert s[0]["date"] == "2025-09-08"
    assert s[0]["semaine_label"] == "B"
    assert s[0]["numero"] == 1
    # Alternance : la séance suivante (semaine du 15) est A.
    assert s[1]["date"] == "2025-09-15"
    assert s[1]["semaine_label"] == "A"


def test_cases_A_et_B_filtrees_par_semaine():
    edt = [
        {"jour": "mar", "creneau_code": "M1", "semaine": "A"},
        {"jour": "ven", "creneau_code": "M2", "semaine": "B"},
    ]
    s = projeter("2025-2026", edt, GRILLE, VAC_ETE, {})
    # 1re semaine comptée = B (8 sept) : seul le vendredi B doit apparaître.
    sem1 = [x for x in s if "2025-09-08" <= x["date"] <= "2025-09-14"]
    assert len(sem1) == 1 and sem1[0]["jour"] == "ven"
    # 2e semaine comptée = A (15 sept) : seul le mardi A.
    sem2 = [x for x in s if "2025-09-15" <= x["date"] <= "2025-09-21"]
    assert len(sem2) == 1 and sem2[0]["jour"] == "mar"


def test_semaine_entierement_en_vacances_ne_progresse_pas():
    # Toussaint : 18 oct → 3 nov 2025 (reprise 3 nov).
    vac = VAC_ETE + [{"start_date": "2025-10-18", "end_date": "2025-11-03"}]
    edt = [{"jour": "lun", "creneau_code": "M1", "semaine": "AB"}]
    s = projeter("2025-2026", edt, GRILLE, vac, {})
    # Aucune séance pendant la Toussaint.
    assert not any("2025-10-18" <= x["date"] < "2025-11-03" for x in s)
    # L'alternance ne saute pas : la séance juste avant et juste après la
    # Toussaint doivent respecter la continuité B/A/B/A (pas de double saut).
    labels = [x["semaine_label"] for x in s]
    # Vérifie qu'on n'a jamais deux mêmes labels consécutifs.
    assert all(labels[i] != labels[i + 1] for i in range(len(labels) - 1))


def test_jour_ferie_saute():
    # 11 novembre 2025 = mardi férié.
    edt = [{"jour": "mar", "creneau_code": "M1", "semaine": "AB"}]
    s = projeter("2025-2026", edt, GRILLE, VAC_ETE, {"2025-11-11": "Armistice"})
    assert not any(x["date"] == "2025-11-11" for x in s)


def test_numerotation_continue():
    edt = [
        {"jour": "lun", "creneau_code": "M1", "semaine": "AB"},
        {"jour": "ven", "creneau_code": "M2", "semaine": "AB"},
    ]
    s = projeter("2025-2026", edt, GRILLE, VAC_ETE, {})
    nums = [x["numero"] for x in s]
    assert nums == list(range(1, len(s) + 1))  # 1..N sans trou


def test_date_min_borne_le_demarrage():
    # Sans vacances d'été (cas dégradé), date_min='2025-09-01' empêche toute
    # séance en août.
    edt = [{"jour": "lun", "creneau_code": "M1", "semaine": "AB"}]
    s = projeter("2025-2026", edt, GRILLE, [], {}, date_min="2025-09-01")
    assert all(x["date"] >= "2025-09-01" for x in s)
    # La 1re semaine de septembre reste la rentrée (ignorée) : 1re séance le 8.
    assert s[0]["date"] == "2025-09-08"


def test_date_min_sans_effet_si_vacances_ete_presentes():
    # Avec vacances d'été, ajouter date_min ne change rien (l'été est déjà
    # couvert par les vacances).
    edt = [{"jour": "lun", "creneau_code": "M1", "semaine": "AB"}]
    s_sans = projeter("2025-2026", edt, GRILLE, VAC_ETE, {})
    s_avec = projeter("2025-2026", edt, GRILLE, VAC_ETE, {},
                      date_min="2025-09-01")
    assert s_sans == s_avec
