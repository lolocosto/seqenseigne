"""tests/test_v0_28_0_panachage_mer.py — v0.28.0

Panachage des MER : répartition des séances par type (automatisme/progression)
selon l'affectation des créneaux EDT et le mode de la classe, + neutralisations
(régulière par créneau 'aucun' ; exceptionnelle par date).
"""
from services.affectation import repartir_mer


SEANCES = [
    {"date": "2026-09-08", "edt_creneau_id": "M1", "jour": "mar"},
    {"date": "2026-09-08", "edt_creneau_id": "M4", "jour": "mar"},
    {"date": "2026-09-15", "edt_creneau_id": "M1", "jour": "mar"},
    {"date": "2026-09-15", "edt_creneau_id": "M4", "jour": "mar"},
]


def test_panache_par_creneau():
    # M1 = automatisme, M4 = progression (cas 6e3 mardi M1/M4)
    aff = {"M1": "automatisme", "M4": "progression"}
    r = repartir_mer(SEANCES, "panache", aff)
    assert [s["date"] for s in r["automatisme"]] == ["2026-09-08", "2026-09-15"]
    assert all(s["edt_creneau_id"] == "M1" for s in r["automatisme"])
    assert all(s["edt_creneau_id"] == "M4" for s in r["progression"])


def test_automatismes_pur_defaut():
    r = repartir_mer(SEANCES, "automatismes", {})
    assert len(r["automatisme"]) == 4
    assert len(r["progression"]) == 0


def test_progression_pur_defaut():
    r = repartir_mer(SEANCES, "progression", {})
    assert len(r["progression"]) == 4
    assert len(r["automatisme"]) == 0


def test_neutralisation_reguliere_par_creneau():
    # Automatismes, mais le créneau M4 est neutralisé ('aucun').
    r = repartir_mer(SEANCES, "automatismes", {"M4": "aucun"})
    assert len(r["automatisme"]) == 2   # seuls les M1
    assert all(s["edt_creneau_id"] == "M1" for s in r["automatisme"])


def test_neutralisation_exceptionnelle_par_date():
    r = repartir_mer(SEANCES, "automatismes", {},
                     exceptions_dates={"2026-09-15"})
    dates = {s["date"] for s in r["automatisme"]}
    assert dates == {"2026-09-08"}       # le 15 est neutralisé


def test_panache_partiel_un_seul_creneau():
    # 6e8 M1/M2 : une seule MER en M1, M2 sans MER.
    seances = [
        {"date": "2026-09-07", "edt_creneau_id": "M1"},
        {"date": "2026-09-07", "edt_creneau_id": "M2"},
    ]
    r = repartir_mer(seances, "panache", {"M1": "automatisme"})
    assert len(r["automatisme"]) == 1
    assert len(r["progression"]) == 0    # M2 non affecté (défaut panache=aucun)
