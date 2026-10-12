"""tests/test_v0_51_6_modeles.py — v0.51.6

Structures modèles à la création d'un référentiel externe :
  - programme du cycle (principal) : thèmes, séquences, objectifs du niveau
    (une partie par séquence, 0 séance) ; parties de l'atelier quand elles
    existent ;
  - référentiels existants du même type (principal ↔ principal, MER ↔ MER),
    internes et externes, sauf annulés et vides ;
  - création : structure recopiée (thèmes, séquences, parties, objectifs :
    type, critères, séances), documents jamais copiés, « créé à partir de » ;
  - doublons : contenu identique (structure + documents) signalé ;
  - routes.
"""
import csv
import shutil
from datetime import date
from pathlib import Path

import pytest

from app import create_app
from services import modeles_referentiel as mdl
from services import referentiel_principal_externe as rpe

ANNEE = "2026-2027"
AUJ = date(2026, 9, 1)
P = "/api/referentiels-principaux-externes"
DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def app(tmp_path):
    """Appli atelier avec les vrais fichiers de cycle (C03, C04) et niveaux."""
    d = tmp_path / "data"
    d.mkdir()
    for f in list(DATA.glob("C0*_*.csv")) + [DATA / "param_niveaux.csv"]:
        shutil.copy(f, d)
    a = create_app(d, profil="atelier")
    a.config["TESTING"] = True
    return a


def _conn(app):
    return app.json_store._conn()


def _csv_n09():
    with open(DATA / "C03_objectifs.csv", encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r["CodeNiveau"] == "N09"]


def _externe(c, dd, type_ref="principal", desc=""):
    rid = rpe.creer(c, "N09", ANNEE, desc, type_ref=type_ref)["id"]
    rpe.ajouter_theme(c, rid, "Nombres et calculs", "nombres")
    s = rpe.ajouter_sequence(c, rid, "Tables", "A")["code"]
    rpe.ajouter_partie(c, rid, s, 0, AUJ, libelle="Série 1")
    rpe.ajouter_objectif(c, rid, s, 1, "Connaître les tables", 1, AUJ, type_obj="connaissance",
                         criteres={"f": "table de 2", "a": "", "e": ""})
    rpe.ajouter_objectif(c, rid, s, 1, "Calculer vite", 2.5, AUJ)
    rpe.ajouter_fichier(c, rid, s, 1, nom_fichier="serie1.pdf", contenu=b"%PDF serie",
                        mime="application/pdf", data_dir=dd)
    return rid


def test_programme_du_cycle(app):
    with _conn(app) as c:
        ms = mdl.lister(c, app.json_store.data_dir, "N09", "principal")
        assert ms[0]["cle"] == "cycle" and ms[0]["nom"].startswith("Programme du cycle")
        m = ms[0]["modele"]
    assert [t["code"] for t in m["themes"]] == ["A", "B", "C"]
    assert m["themes"][0]["couleur"] == "nombres"
    lignes = _csv_n09()
    seqs_csv = sorted({r["CodeSequence"] for r in lignes})
    assert len(m["sequences"]) == len(seqs_csv)
    assert all(len(s["parties"]) == 1 for s in m["sequences"])
    objs = [o for s in m["sequences"] for o in s["parties"][0]["objectifs"]]
    assert len(objs) == len(lignes) and all(o["nb_seances"] == 0 for o in objs)
    s1 = m["sequences"][0]
    assert s1["theme"] == "A"
    o1, o2 = s1["parties"][0]["objectifs"][:2]
    assert o1["type"] == "connaissance" and o2["type"] == "capacite"
    ref = next(r for r in lignes if r["CodeSequence"] == "S01" and r["CodeObjectif"] == "02")
    from services.texte_latex import vers_texte
    assert o2["nom"] == vers_texte(ref["Nom"]).strip()
    assert o2["criteres"]["f"] == ("" if ref["MaitriseF"] == "-" else vers_texte(ref["MaitriseF"]).strip())
    assert o2["criteres"]["e"] == vers_texte(ref["MaitriseTB"]).strip()
    assert not any("\\" in o["nom"] for s in m["sequences"] for o in s["parties"][0]["objectifs"])
    # Pas de programme du cycle pour une MER.
    with _conn(app) as c:
        assert all(x["cle"] != "cycle" for x in mdl.lister(c, None, "N09", "mer"))


def test_creer_depuis_le_programme(app):
    with _conn(app) as c:
        r = mdl.creer(c, app.json_store.data_dir, "N09", ANNEE, "Manuel X", "principal",
                      "cycle", AUJ)
        assert r["cree_depuis"].startswith("Programme du cycle")
        assert [t["nom"] for t in r["themes"]][:1] == ["Nombres et Calculs"]
        assert r["en_conception"] and r["sequences"][0]["code"] == "S01"
        assert r["sequences"][0]["theme_code"] == "A"
        p = r["sequences"][0]["parties"][0]
        assert p["objectifs"][0]["type_obj"] == "connaissance"
        assert p["nb_seances_R_AE"] == 0
        assert len([o for s in r["sequences"] for pp in s["parties"] for o in pp["objectifs"]]) \
            == len(_csv_n09())


def test_modeles_du_meme_type_et_creation(app):
    dd = app.json_store.data_dir
    with _conn(app) as c:
        mer = _externe(c, dd, "mer", "Calcul mental")
        princ = _externe(c, dd, "principal")
        vide = rpe.creer(c, "N09", ANNEE, type_ref="mer")["id"]         # vide : ignoré
        cles_mer = [m["cle"] for m in mdl.lister(c, dd, "N09", "mer")]
        assert cles_mer == [f"ref:{mer}"] and f"ref:{vide}" not in cles_mer
        assert f"ref:{princ}" in [m["cle"] for m in mdl.lister(c, dd, "N09", "principal")]
        with pytest.raises(rpe.RefExtErreur):
            mdl.creer(c, dd, "N09", ANNEE, "", "mer", f"ref:{princ}")   # autre type
        n = mdl.creer(c, dd, "N09", "2027-2028", "", "mer", f"ref:{mer}", AUJ)
        assert n["cree_depuis"].endswith("MER") and n["type_ref"] == "mer"
        s = n["sequences"][0]
        assert (s["code"], s["nom"], s["theme_code"]) == ("M01", "Tables", "A")
        p = s["parties"][0]
        assert p["libelle"] == "Série 1" and p["nb_seances_R_AE"] == 3.5
        assert [(o["nom"], o["type_obj"], o["nb_seances"]) for o in p["objectifs"]] == \
            [("Connaître les tables", "connaissance", 1), ("Calculer vite", "capacite", 2.5)]
        assert p["objectifs"][0]["critere_f"] == "table de 2"
        assert p["fichiers"] == []                                    # documents non copiés


def test_modele_interne(app):
    with _conn(app) as c:
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat) VALUES "
                  "('2025_N09', 'N09', '2025', 'verrouille')")
        c.execute("INSERT INTO referentiel_themes (referentiel_id, code, nom, couleur) "
                  "VALUES ('2025_N09', 'A', 'Nombres', 'nombres')")
        c.execute("INSERT INTO referentiel_sequences (referentiel_id, code, numero, nom, "
                  "theme_code) VALUES ('2025_N09', 'S01', 1, 'Entiers', 'A')")
        c.execute("INSERT INTO referentiel_parties (referentiel_id, seq_code, numero, "
                  "nb_seances_R_AE) VALUES ('2025_N09', 'S01', 1, 9)")
        for code, nom, nb in (("01", r"Conna\^itre le cours", 1), ("02", "Comparer", 2)):
            c.execute("INSERT INTO referentiel_objectifs (referentiel_id, seq_code, code, nom, "
                      "partie_numero, nb_seances) VALUES ('2025_N09', 'S01', ?, ?, 1, ?)",
                      (code, nom, nb))
        m = mdl.modele(c, None, "N09", "principal", "ref:2025_N09")
        objs = m["modele"]["sequences"][0]["parties"][0]["objectifs"]
        assert [(o["nom"], o["type"]) for o in objs] == \
            [("Connaître le cours", "connaissance"), ("Comparer", "capacite")]
        r = mdl.creer(c, None, "N09", ANNEE, "", "principal", "ref:2025_N09", AUJ)
        assert r["sequences"][0]["parties"][0]["nb_seances_R_AE"] == 3
        c.execute("UPDATE referentiel_niveaux SET etat='annule' WHERE id='2025_N09'")
        assert "ref:2025_N09" not in [x["cle"] for x in mdl.lister(c, None, "N09", "principal")]


def test_doublons(app):
    dd = app.json_store.data_dir
    with _conn(app) as c:
        a = _externe(c, dd, "mer")
        b = mdl.creer(c, dd, "N09", "2027-2028", "copie", "mer", f"ref:{a}", AUJ)["id"]
        # Même structure, documents différents (aucun) : pas un doublon.
        assert mdl.doublons(c, dd, b) == []
        rpe.ajouter_fichier(c, b, "M01", 1, nom_fichier="autre_nom.pdf", contenu=b"%PDF serie",
                            mime="application/pdf", data_dir=dd)
        assert [d["id"] for d in mdl.doublons(c, dd, b)] == [a]       # même contenu
        assert [d["id"] for d in mdl.doublons(c, dd, a)] == [b]
        rpe.modifier_objectif(c, b, "M01", "02", {"nb_seances": 3}, AUJ)
        assert mdl.doublons(c, dd, b) == []
        # Un principal identique n'est pas un doublon d'une MER.
        p = _externe(c, dd, "principal")
        assert mdl.doublons(c, dd, p) == []


def test_routes(app):
    cl = app.test_client()
    l = cl.get(f"{P}/modeles?niveau=N09&type=principal").get_json()["modeles"]
    assert l[0]["cle"] == "cycle" and "séquence(s)" in l[0]["resume"]
    r = cl.post(P, json={"niveau": "N09", "annee": ANNEE, "type_ref": "principal",
                         "modele": "cycle"})
    assert r.status_code == 201 and r.get_json()["sequences"]
    rid = r.get_json()["id"]
    d = cl.get(f"{P}/{rid}").get_json()
    assert d["doublons"] == [] and d["cree_depuis"]
    assert cl.post(P, json={"niveau": "N09", "annee": ANNEE, "modele": "ref:inconnu"}).status_code == 404
    assert cl.get(f"{P}/modeles?niveau=N09&type=autre").status_code == 400
    v = cl.post(P, json={"niveau": "N09", "annee": ANNEE, "type_ref": "mer"}).get_json()
    assert v["sequences"] == [] and v["cree_depuis"] == ""
