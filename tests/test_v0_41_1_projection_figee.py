"""tests/test_v0_41_1_projection_figee.py — v0.41.1

Non-régression du regroupement de la préparation de la projection
(services/contexte_projection.py). Avant le refactor, la même séquence
« classe → établissement/académie → EdT compté + grille + indisponibilités →
vacances + fériés (hors transaction) → borne du 1er septembre → projeter »
était recopiée dans 9 routes/services.

Ce test fige la sortie de TOUS les consommateurs sur un jeu de données
réaliste (EdT A/B, demi-groupe non compté, changement d'EdT programmé,
indisponibilité, MER, vacances et fériés fictifs) : la capture a été faite
AVANT le refactor (tests/fixtures/snapshot_projection_v0_41_1.json) et doit
rester identique après.

Régénérer la capture (uniquement si un changement de comportement est VOULU) :
    python tests/test_v0_41_1_projection_figee.py --regenerer
"""
import json
import sys
from datetime import date
from pathlib import Path

import pytest

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshot_projection_v0_41_1.json"
ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)

VACANCES = [
    {"description": "Vacances de la Toussaint", "start_date": "2026-10-17", "end_date": "2026-11-02"},
    {"description": "Vacances de Noël", "start_date": "2026-12-19", "end_date": "2027-01-04"},
    {"description": "Vacances d'Hiver", "start_date": "2027-02-06", "end_date": "2027-02-22"},
    {"description": "Vacances de Printemps", "start_date": "2027-04-10", "end_date": "2027-04-26"},
    {"description": "Vacances d'Été", "start_date": "2027-07-03", "end_date": "2027-09-01"},
]
FERIES = {"2026-11-11": "Armistice", "2027-05-01": "Fête du travail",
          "2027-05-08": "Victoire 1945", "2027-05-13": "Ascension"}


def _calendrier_fictif(monkeypatch):
    from services import calendrier_scolaire as cal
    monkeypatch.setattr(cal, "vacances", lambda annee, zone, store, academie=None: [dict(v) for v in VACANCES])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda annee, store: dict(FERIES))


def _donnees(store):
    from services import edt, grille_horaire as gh, indisponibilites as ind
    from services import affectation as aff
    with store._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'Collège', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id, "
                  "mer_active, mer_mode) VALUES ('cl', '4EME3', 'N11', ?, 'et', 1, "
                  "'panachage')", (ANNEE,))
        k1 = edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="cl", aujourd_hui=AUJ)
        edt.ajouter(c, ANNEE, "mar", "M2", "et", semaine="A", classe_id="cl", aujourd_hui=AUJ)
        edt.ajouter(c, ANNEE, "jeu", "M3", "et", semaine="B", classe_id="cl", aujourd_hui=AUJ)
        k4 = edt.ajouter(c, ANNEE, "ven", "M1", "et", classe_id="cl", aujourd_hui=AUJ)
        edt.ajouter(c, ANNEE, "ven", "M2", "et", classe_id="cl",
                    groupe="demi_classe_A", aujourd_hui=AUJ)          # non compté
        aff.definir_affectations(c, "cl", ANNEE, [
            {"edt_creneau_id": k1["id"], "affectation": "automatisme"},
            {"edt_creneau_id": k4["id"], "affectation": "progression"}])
        aff.ajouter_exception(c, "cl", ANNEE, "2026-12-07", "Contrôle commun")
        ind.creer(c, ANNEE, "et", type="journees", date_debut="2026-12-03",
                  motif="Sortie")
        edt.figer(c, ANNEE, "et", AUJ)
        edt.supprimer(c, k4["id"], a_partir_du="2027-01-04", aujourd_hui=AUJ)
    # Progression principale de la classe (chemin « rang dans la partie » du
    # détail de séance, et progression réalisée).
    store.ecrire_progression({
        "niveau": "N11", "annee": ANNEE, "etablissement_id": "et",
        "creneaux": [
            {"id": "cr1", "sequence": "S01", "partie_debut": 1, "partie_fin": 1,
             "partie": "1re partie", "ordre": 1,
             "date_debut": "2026-11-30", "date_fin": "2026-12-18"},
            {"id": "cr2", "sequence": "S02", "partie_debut": 1, "partie_fin": 1,
             "partie": "1re partie", "ordre": 2,
             "date_debut": "2027-01-04", "date_fin": "2027-02-05"},
        ]})


def _capturer(client, app):
    from services import edt_apercu
    sorties = {}
    for nom, url in [
        ("projection", f"/api/classes/cl/projection?annee={ANNEE}"),
        ("planning_automatismes", f"/api/classes/cl/planning-automatismes?annee={ANNEE}"),
        ("planning_affecte", f"/api/classes/cl/planning-affecte?annee={ANNEE}"),
        ("planning_mer", f"/api/classes/cl/planning-mer?annee={ANNEE}"),
        ("progression_realisee", f"/api/classes/cl/progression-realisee?annee={ANNEE}"),
        ("planif_hebdo", f"/api/planification-hebdo?annee={ANNEE}&lundi=2026-11-30&etablissement_id=et"),
        ("planif_seance", f"/api/planification-hebdo/seance?annee={ANNEE}&classe_id=cl&date=2026-12-07&creneau=M1"),
        ("planif_seance_auto", f"/api/planification-hebdo/seance?annee={ANNEE}&classe_id=cl&date=2026-12-14&creneau=M1"),
        ("planif_seance_prog", f"/api/planification-hebdo/seance?annee={ANNEE}&classe_id=cl&date=2026-12-11&creneau=M1"),
    ]:
        r = client.get(url)
        sorties[nom] = {"statut": r.status_code, "json": r.get_json()}
    # Routes PDF : on capture le .tex généré (la compilation est court-circuitée).
    from services import compilateur_pdf
    capture_tex = {}

    class _Faux:
        ok, erreurs = False, []

    origine = compilateur_pdf.compiler_atome

    def _capture(tex_source, **kw):
        capture_tex["tex"] = tex_source
        return _Faux()
    compilateur_pdf.compiler_atome = _capture
    try:
        for nom, url in [
            ("tex_planning_mer", f"/api/classes/cl/planning-mer.pdf?annee={ANNEE}"),
            ("tex_planning_automatismes", f"/api/classes/cl/planning-automatismes.pdf?annee={ANNEE}"),
        ]:
            capture_tex.clear()
            client.get(url)
            sorties[nom] = capture_tex.get("tex", "")
    finally:
        compilateur_pdf.compiler_atome = origine
    sorties["apercu_edt"] = edt_apercu.apercu(
        app.json_store, ANNEE, {"etablissement_id": "et", "operation": "supprimer",
                                "edt_id": _id_case(app, "lun", "M1"),
                                "a_partir_du": "2026-10-05"}, AUJ)
    return json.loads(json.dumps(sorties, sort_keys=True, default=str))


def _id_case(app, jour, code):
    with app.json_store._conn() as c:
        return c.execute("SELECT id FROM edt_creneaux WHERE jour=? AND creneau_code=? "
                         "ORDER BY valide_du LIMIT 1", (jour, code)).fetchone()["id"]


def _normaliser(obj, ids):
    """Remplace les identifiants aléatoires (cases, plans…) par des repères
    stables pour comparer deux bases construites séparément."""
    if isinstance(obj, dict):
        return {k: _normaliser(v, ids) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normaliser(v, ids) for v in obj]
    if isinstance(obj, str) and obj in ids:
        return ids[obj]
    return obj


def _ids_stables(app):
    ids = {}
    with app.json_store._conn() as c:
        for r in c.execute("SELECT id, jour, creneau_code, valide_du FROM edt_creneaux"):
            ids[r["id"]] = f"edt:{r['jour']}:{r['creneau_code']}:{r['valide_du']}"
        for t in ("progressions_mer", "indisponibilites", "affectation_exception",
                  "progression_mer", "progressions"):
            try:
                for i, r in enumerate(c.execute(f"SELECT id FROM {t} ORDER BY id")):
                    ids[r["id"]] = f"{t}:{i}"
            except Exception:
                pass
    return ids


def capture_complete(client, app):
    _donnees(app.json_store)
    brut = _capturer(client, app)
    return _normaliser(brut, _ids_stables(app))


def test_sorties_identiques_a_la_capture(client, app, monkeypatch):
    _calendrier_fictif(monkeypatch)
    actuel = capture_complete(client, app)
    attendu = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for cle in attendu:
        assert actuel[cle] == attendu[cle], f"Sortie modifiée : {cle}"
    assert set(actuel) == set(attendu)


def test_capture_significative():
    """La capture doit exercer les cas délicats (sinon elle ne protège rien)."""
    a = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    proj = a["projection"]["json"]
    assert a["projection"]["statut"] == 200 and proj["nb_seances"] > 80
    dates = [s["date"] for s in proj["seances"]]
    assert "2026-11-11" not in dates and "2026-12-03" not in dates     # férié, indispo
    assert not any("2026-10-19" <= d < "2026-11-02" for d in dates)    # Toussaint
    # Le vendredi M1 disparaît à partir du 04/01/2027 (changement d'EdT).
    vend = [s for s in proj["seances"] if s.get("jour") == "ven"]
    assert vend and max(s["date"] for s in vend) < "2027-01-04"
    assert any(x["avant"] != x["apres"] for x in a["apercu_edt"])


if __name__ == "__main__" and "--regenerer" in sys.argv:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import tempfile
    from app import create_app
    from services import calendrier_scolaire as cal
    cal.vacances = lambda annee, zone, store, academie=None: [dict(v) for v in VACANCES]
    cal.jours_feries_annee_scolaire = lambda annee, store: dict(FERIES)
    app = create_app(Path(tempfile.mkdtemp()) / "data")
    app.config["TESTING"] = True
    with app.test_client() as client:
        res = capture_complete(client, app)
    SNAPSHOT.write_text(json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True),
                        encoding="utf-8")
    print("Capture écrite :", SNAPSHOT, {k: v.get("statut") if isinstance(v, dict) else len(v)
                                          for k, v in res.items()})


# ── Module commun : cas limites ──────────────────────────────────────────────

def test_date_min_premier_septembre():
    from services import contexte_projection as ctx
    assert ctx.date_min("2026-2027") == "2026-09-01"


def test_calendrier_reseau_en_panne_et_zone_inconnue(monkeypatch):
    """Une erreur réseau ne doit jamais faire tomber la projection : vacances
    vides, signalées par `vacances_absentes` (avertissement de l'UI)."""
    from services import calendrier_scolaire as cal
    from services import contexte_projection as ctx

    def panne(*a, **k):
        raise OSError("réseau")
    monkeypatch.setattr(cal, "vacances", panne)
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", panne)
    c = ctx.calendrier(None, ANNEE, "Rennes")
    assert c["zone"] and c["vacances"] == [] and c["feries"] == {}
    assert c["vacances_absentes"] is True
    c = ctx.calendrier(None, ANNEE, "")
    assert c["zone"] is None and c["vacances_absentes"] is True


def test_calendrier_sans_feries(monkeypatch):
    from services import calendrier_scolaire as cal
    from services import contexte_projection as ctx
    _calendrier_fictif(monkeypatch)
    appels = []
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire",
                        lambda *a: appels.append(1) or {})
    c = ctx.calendrier(None, ANNEE, "Rennes", feries=False)
    assert c["vacances"] and appels == []


def test_classe_sans_academie_et_donnees_sans_etablissement(app):
    """Établissement sans académie : académie vide (zone inconnue). Sans
    identifiant d'établissement : ni grille ni indisponibilités, sans erreur."""
    from services import contexte_projection as ctx
    with app.json_store._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('e0', 'E', 'propose')")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('k', 'X', 'N11', ?, 'e0')", (ANNEE,))
        assert ctx.infos_classe(c, "k") == {"etablissement_id": "e0", "academie": ""}
        assert ctx.infos_classe(c, "absente") is None
        d = ctx.donnees_classe(c, ANNEE, "k", None)
        assert d == {"edt_comptees": [], "grille": [], "indispos": []}
