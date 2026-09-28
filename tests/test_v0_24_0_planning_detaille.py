"""tests/test_v0_24_0_planning_detaille.py — v0.24.0

Assemblage du planning Leitner détaillé (frise) : blocs période / vacances,
enveloppes sous les séances, séparateurs de vacances.
"""
from services.planning_leitner_detaille import assembler


def test_periodes_separees_par_vacances():
    seances = [
        {"numero": 1, "date": "2026-09-14"},
        {"numero": 2, "date": "2026-09-17"},
        {"numero": 3, "date": "2026-11-03"},
    ]
    vacances = [{"description": "Vacances de la Toussaint",
                 "start_date": "2026-10-17", "end_date": "2026-11-02"}]
    blocs = assembler(seances, vacances, {}, [], [{"code": "M1", "ordre": 10}],
                      "cl_x", "2026-2027")
    types = [b["type"] for b in blocs]
    assert "vacances" in types
    # une période, puis vacances, puis une période
    idx_vac = types.index("vacances")
    assert "periode" in types[:idx_vac]
    assert "periode" in types[idx_vac + 1:]
    vac = [b for b in blocs if b["type"] == "vacances"][0]
    assert "Toussaint" in vac["nom"]


def test_enveloppes_sous_seances():
    seances = [{"numero": 1, "date": "2026-09-14"},
               {"numero": 4, "date": "2026-09-24"}]
    blocs = assembler(seances, [], {}, [], [{"code": "M1", "ordre": 10}],
                      "cl_x", "2026-2027")
    jours = [j for b in blocs if b["type"] == "periode" for j in b["jours"]]
    d = {j["date"]: j for j in jours}
    assert d["2026-09-14"]["enveloppes"] == [1]
    assert d["2026-09-24"]["enveloppes"] == [1, 2, 3]
    assert all(j["kind"] == "seance" for j in jours)


def test_ferie_marque_si_jour_de_cours():
    # séances le lundi ; un férié un lundi doit apparaître (kind=ferie).
    seances = [{"numero": 1, "date": "2026-09-14"},  # lundi
               {"numero": 2, "date": "2026-09-21"}]  # lundi
    # 2026-11-16 est un lundi (jour de cours de la classe)
    blocs = assembler(seances, [], {"2026-11-16": "Test férié"}, [],
                      [{"code": "M1", "ordre": 10}], "cl_x", "2026-2027")
    jours = [j for b in blocs if b["type"] == "periode" for j in b["jours"]]
    feries = [j for j in jours if j["kind"] == "ferie"]
    assert any(j["date"] == "2026-11-16" for j in feries)
