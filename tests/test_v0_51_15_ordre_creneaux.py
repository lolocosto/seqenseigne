"""tests/test_v0_51_15_ordre_creneaux.py — v0.51.15

Ordre des créneaux de la grille horaire = position dans la journée (heure de
début) : un créneau ajouté après coup (M5 créé après S4) prend sa place ; une
indisponibilité « de M4 à M5 » ne retire que M4 et M5 (et plus toute
l'après-midi) ; migration au démarrage des grilles existantes.
Données fictives.
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import calendrier_scolaire as cal
from services import contexte_projection as ctx
from services import edt, grille_horaire as gh
from services import indisponibilites as ind

ANNEE = "2026-2027"


@pytest.fixture
def st(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    st = SqliteStore(tmp_path / "data")
    with st._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")                     # M1..M4, S1..S4
        gh.creer(c, "et", "M5", heure_debut="11:35", heure_fin="12:30")   # ajouté après
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('c1', '4E3', 'N11', ?, 'et')", (ANNEE,))
        for cr in ("M4", "M5", "S2", "S3"):
            edt.ajouter(c, ANNEE, "jeu", cr, "et", classe_id="c1", aujourd_hui=date(2026, 8, 25))
    return st


def _codes(st):
    with st._conn() as c:
        return [g["code"] for g in gh.lister(c, "et")]


def test_creneau_ajoute_apres_coup_a_sa_place(st):
    assert _codes(st) == ["M1", "M2", "M3", "M4", "M5", "S1", "S2", "S3", "S4"]
    with st._conn() as c:
        ordres = [g["ordre"] for g in gh.lister(c, "et")]
    assert ordres == sorted(ordres) and len(set(ordres)) == 9


def test_indisponibilite_limitee_a_ses_creneaux(st):
    with st._conn() as c:
        ind.creer(c, ANNEE, "et", type="seances", date_debut="2026-10-01",
                  creneau_debut="M4", creneau_fin="M5", portee="moi",
                  motif="Élection des délégués")
        sem = ctx.seances_de_la_semaine(c, st, ANNEE, "2026-09-28")
    jeudi = {s["creneau"]: s["indispo"] for s in sem if s["date"] == "2026-10-01"}
    assert jeudi == {"M4": True, "M5": True, "S2": False, "S3": False}


def test_modification_d_heure_replace_le_creneau(st):
    with st._conn() as c:
        m5 = next(g for g in gh.lister(c, "et") if g["code"] == "M5")
        gh.modifier(c, m5["id"], {"heure_debut": "17:05", "heure_fin": "18:00"})
    assert _codes(st)[-1] == "M5"


def test_migration_des_grilles_existantes(st, tmp_path):
    with st._conn() as c:                     # état d'avant : M5 en fin d'ordre
        c.execute("UPDATE grille_horaire_creneaux SET ordre=90 WHERE code='M5'")
        c.execute("UPDATE grille_horaire_creneaux SET ordre=50 WHERE code='S1'")
    SqliteStore(tmp_path / "data")            # redémarrage
    with st._conn() as c:
        o = {g["code"]: g["ordre"] for g in gh.lister(c, "et")}
    assert o["M4"] < o["M5"] < o["S1"]


def test_concerne_seance_avec_l_ordre_de_la_grille(st):
    with st._conn() as c:
        grille = gh.lister(c, "et")
    ordre = {g["code"]: g["ordre"] for g in grille}
    i = {"type": "seances", "date_debut": "2026-10-01", "creneau_debut": "M4",
         "creneau_fin": "M5", "portee": "moi"}
    concernes = [g["code"] for g in grille
                 if ind.concerne_seance(i, {"date": "2026-10-01", "creneau_code": g["code"]},
                                        "c1", ordre)]
    assert concernes == ["M4", "M5"]


def test_rang_dans_le_creneau_sur_les_seances_effectives(st):
    """Rang de la séance (n/N) : séances réellement faites dans le créneau,
    indisponibilités retirées."""
    from services import seances_resume as sr
    st.ecrire_progression({"niveau": "N11", "annee": ANNEE, "etablissement_id": "et",
                           "creneaux": [{"id": "cr1", "sequence": "S01", "partie_debut": 1,
                                         "partie_fin": 1, "ordre": 1,
                                         "date_debut": "2026-09-24", "date_fin": "2026-10-08"}]})
    cases = [{"classe_id": "c1", "date": "2026-10-01", "creneau": cr} for cr in ("S2", "S3")]
    with st._conn() as c:
        avant = sr.resumer(c, st, ANNEE, cases)
        ind.creer(c, ANNEE, "et", type="seances", date_debut="2026-10-01",
                  creneau_debut="M4", creneau_fin="M5", portee="moi")
        apres = sr.resumer(c, st, ANNEE, cases)
    s2_avant = avant[("c1", "2026-10-01", "S2")]["principale"]
    s2 = apres[("c1", "2026-10-01", "S2")]["principale"]
    assert (s2_avant["rang"], s2_avant["nb"]) == (7, 12)        # 3 jeudis × 4 séances
    assert (s2["rang"], s2["nb"]) == (5, 10)                    # M4 et M5 du 01/10 retirées
