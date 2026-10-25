"""tests/test_v0_54_0_referentiels_6e.py — v0.54.0

Les deux référentiels internes de 6e (besoin de Laurent du 25 octobre 2026,
doc/redemarrage_v0_54_0.md) : le principal (S01–S13) et celui des mises en
route (M01–M07), créés dans l'appli.

  RI1  périmètre selon le type (principal : ni Xnn ni Mnn ; MER : les Mnn) ;
  RI2  instantané complet au verrouillage d'une coquille, retiré au
       déverrouillage ; l'ancien mécanisme reste pour un instantané importé ;
  RI3  numéro de mise en route (M01 → 1) ; RI4 durée d'une partie MER ;
  RI5  modèle « Fiches » : séquences validées exigées ;
  RI6  catalogue des documents de mise en route, cibles par partie ;
  RI7  documents compilés rattachés à la partie (format 1.4) ;
  RI8  concurrents du même type seulement ;
  RI10 aperçu avant création ; RI11 valider une Mnn = MR6.

Base de test reconstruite à chaque test (jamais de base réelle).
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from app import create_app
from services import format_referentiel as fmt
from services import gabarits_documents as gd
from services import referentiel_figeage as fig
from services import referentiel_validation as val
from services import referentiels as refs
from services import referentiels_internes as ri
from services import v2_edition as v2
from services.referentiel_documents_compilation import lister_cibles_document
from tests.test_v0_53_0_mises_en_route import (_appliquer, _ecrire_lot, _lot,  # noqa: F401
                                               base)


def _c(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")      # comme les connexions de l'appli
    return c


def _principal_minimal(c, avec_archive=True):
    """S01 (une partie : 01 Cours, 02 avec F, A, fiche ; une évaluation) et
    une archive X01 — par l'API SQL de test (pas de base réelle)."""
    c.execute("INSERT INTO sequences_par_niveau (id, niveau, sequence_code, etat_code) "
              "VALUES ('sn_s01', 'N09', 'S01', 'en_cours')")
    c.execute("INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero, nb_seances_R_AE) "
              "VALUES ('p_s01_1', 'sn_s01', 1, 0)")
    c.execute("INSERT INTO objectifs (id, partie_id, code, nom, critere_F, critere_A, nb_seances) "
              "VALUES ('o_s01_01', 'p_s01_1', '01', 'Connaître le cours', 'f', 'a', 0)")
    c.execute("INSERT INTO objectifs (id, partie_id, code, nom, critere_F, critere_A, nb_seances) "
              "VALUES ('o_s01_02', 'p_s01_1', '02', 'Lire un nombre', 'Lit', 'Lit vite', 2)")
    for i, (serie, num) in enumerate((("F", 1), ("A", 1), ("EV", 1))):
        c.execute("INSERT INTO exercices (id, niveau, sequence, serie, serie_code, num, titre, "
                  "enonce, corrige, remed_enonce, etat_code) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (f"e_s01_{serie}", "N09", "S01", serie, serie, num, f"Exo {serie}",
                   "Énoncé", "Corrigé", "Sujet B" if serie == "EV" else "", "en_cours"))
        if serie != "EV":
            c.execute("INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) "
                      "VALUES ('o_s01_02', ?, ?, ?)", (serie, f"e_s01_{serie}", i))
    c.execute("INSERT INTO fiches_resume (id, niveau, sequence, objectif_id, titre, num_fiche, "
              "etat_code) VALUES ('f_s01', 'N09', 'S01', 'o_s01_02', 'Lire', 1, 'en_cours')")
    c.execute("INSERT INTO evaluations (id, niveau, numero, ordre, titre, etat_code) "
              "VALUES ('ev_s01', 'N09', 90, 90, 'Évaluation S01', 'en_cours')")
    c.execute("INSERT INTO evaluation_exercices (evaluation_id, exercice_id, ordre) "
              "VALUES ('ev_s01', 'e_s01_EV', 1)")
    if avec_archive:
        c.execute("INSERT INTO sequences_par_niveau (id, niveau, sequence_code, etat_code) "
                  "VALUES ('sn_x01', 'N09', 'X01', 'en_cours')")
        c.execute("INSERT INTO exercices (id, niveau, sequence, serie, serie_code, num, titre, "
                  "enonce, etat_code) VALUES ('e_x01', 'N09', 'X01', 'F', 'F', 1, 'Ancien', "
                  "'x', 'en_cours')")
    c.commit()


@pytest.fixture
def db6e(base, tmp_path):
    """Base d'atelier : M01 (lot de test, 4 parties, tests courts) + S01 + X01."""
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    c = _c(base)
    _principal_minimal(c)
    c.close()
    return base


def _creer(c, type_ref, gabarit="sixieme"):
    r = refs.creer_coquille(c, "N09", "essai", type_ref=type_ref)
    gd.poser_a_la_creation(c, r["id"], "N09", gabarit)
    c.commit()
    return r["id"]


def _tout_valider(c):
    for t in ("exercices", "fiches_resume", "evaluations"):
        c.execute(f"UPDATE {t} SET etat_code='valide' WHERE niveau='N09'")
    c.execute("UPDATE sequences_par_niveau SET etat_code='valide' WHERE niveau='N09'")
    c.commit()


# ── RI1 Périmètre ───────────────────────────────────────────────────────────

def test_ri1_principal_sans_mises_en_route_ni_archives_car_MR7(db6e):
    c = _c(db6e)
    seqs = [s["code"] for s in ri.sequences_du_perimetre(c, "N09", "principal")]
    assert seqs == ["S01"]
    assert [s["code"] for s in ri.sequences_du_perimetre(c, "N09", "mer")] == ["M01"]
    arbre = refs.arbre_du_niveau(c, "N09", "principal")
    assert [s["code"] for s in arbre["sequences"]] == ["S01"]
    assert [e["id"] for e in arbre["evaluations"]] == ["ev_s01"]
    # Sans type (appel d'avant v0.54.0) : tout le niveau, comme avant.
    assert {s["code"] for s in refs.arbre_du_niveau(c, "N09")["sequences"]} >= {"S01", "M01", "X01"}


def test_ri1_les_tests_courts_des_mises_en_route_ne_bloquent_plus_le_principal(db6e):
    c = _c(db6e)
    ev_p = ri.evaluations_du_perimetre(c, "N09", "principal")
    ev_m = ri.evaluations_du_perimetre(c, "N09", "mer")
    assert [e["id"] for e in ev_p] == ["ev_s01"]
    assert ev_m and all(e["sequence"] == "M01" for e in ev_m)
    c.execute("UPDATE evaluations SET etat_code='valide' WHERE id='ev_s01'")
    c.commit()
    assert val._compter_evaluations_non_valides(c, "N09", "principal") == 0
    assert val._compter_evaluations_non_valides(c, "N09", "mer") == len(ev_m)
    # Sans type : toutes (comportement d'avant pour un appelant ancien).
    assert val._compter_evaluations_non_valides(c, "N09") == len(ev_m)


def test_ri1_l_arbre_d_une_mise_en_route_montre_fiche_de_cours_et_exercices_de_seance(db6e):
    c = _c(db6e)
    a = refs.arbre_du_niveau(c, "N09", "mer")
    o = a["sequences"][0]["parties"][0]["objectifs"][0]
    assert o["mer"] is True and o["exos_MR"] and o["fiche"] is not None
    assert not o["exos_F"]


# ── RI5 Éligibilité ─────────────────────────────────────────────────────────

def test_ri5_modele_fiches_exige_des_sequences_validees_dans_l_atelier(db6e):
    c = _c(db6e)
    rid = _creer(c, "principal")
    c.execute("UPDATE exercices SET etat_code='valide' WHERE niveau='N09'")
    c.execute("UPDATE fiches_resume SET etat_code='valide' WHERE niveau='N09'")
    c.execute("UPDATE evaluations SET etat_code='valide' WHERE niveau='N09'")
    c.commit()
    d = val.evaluer_eligibilite_validation(c, rid)
    assert d["details"]["sequences_non_validees"] == ["S01"]
    assert any("S01" in r and "séquence" in r for r in d["raisons"])
    c.execute("UPDATE sequences_par_niveau SET etat_code='valide' WHERE sequence_code='S01'")
    c.commit()
    d = val.evaluer_eligibilite_validation(c, rid)
    assert d["details"]["sequences_non_validees"] == []
    # Les atomes de l'archive et des mises en route ne comptent pas.
    assert d["details"]["atomes_non_valides"]["exercices"] == 0


def test_ri5_notions_et_methodes_n_exige_pas_les_sequences_comme_avant(db6e):
    c = _c(db6e)
    rid = _creer(c, "principal", gabarit="cycle4")
    d = val.evaluer_eligibilite_validation(c, rid)
    assert d["details"]["sequences_non_validees"] == []


def test_ri5_mise_en_route_ne_compte_que_ses_mnn(db6e):
    c = _c(db6e)
    rid = _creer(c, "mer")
    c.execute("UPDATE exercices SET etat_code='valide' WHERE sequence='M01'")
    c.execute("UPDATE fiches_resume SET etat_code='valide' WHERE sequence='M01'")
    c.commit()
    d = val.evaluer_eligibilite_validation(c, rid)
    assert d["details"]["atomes_non_valides"]["exercices"] == 0     # S01 et X01 ignorés
    assert d["details"]["sequences_non_validees"] == ["M01"]


# ── RI11 Valider une séquence de mise en route ──────────────────────────────

def test_ri11_valider_une_mnn_applique_mr6_et_non_la_regle_F_A(db6e):
    c = _c(db6e)
    sn = c.execute("SELECT id FROM sequences_par_niveau WHERE sequence_code='M01'").fetchone()[0]
    assert v2.valider_sequence_niveau(c, sn)["etat_code"] == "valide"
    v2.devalider_sequence_niveau(c, sn)
    # MR6 : sans fiche de cours, la partie bloque (erreur, pas avertissement).
    c.execute("DELETE FROM objectif_fiches WHERE objectif_id IN (SELECT o.id FROM objectifs o "
              "JOIN sequence_parties p ON p.id=o.partie_id WHERE p.sequence_par_niveau_id=? "
              "AND p.numero=1)", (sn,))
    with pytest.raises(v2.ValidationSequenceErreur) as e:
        v2.valider_sequence_niveau(c, sn)
    assert any("fiche de cours" in r for r in e.value.details["raisons"])


# ── RI2, RI3, RI4 Instantané ────────────────────────────────────────────────

def _verrouiller(c, rid, tmp_path):
    _tout_valider(c)
    assert val.maj_etat_lazy(c, rid) in ("valide", "en_cours")
    c.execute("UPDATE referentiel_niveaux SET etat='valide' WHERE id=?", (rid,))
    c.commit()
    return fig.verrouiller_complet(c, rid, dossier_referentiel=tmp_path / rid,
                                   lister_cibles=lambda *a: [], force_confirme=True)


def test_ri2_le_verrouillage_d_une_coquille_ecrit_l_instantane_complet_car_la_publication_etait_vide(
        db6e, tmp_path):
    c = _c(db6e)
    rid = _creer(c, "principal")
    assert fmt.construire(c, rid)["sequences"] == []          # avant : rien à publier
    res = _verrouiller(c, rid, tmp_path)
    assert res["verrouille"]["instantane"] == {"nb_sequences": 1, "nb_parties": 1,
                                               "nb_objectifs": 2, "nb_themes": 1}
    doc = fmt.construire(c, rid)
    assert [s["code"] for s in doc["sequences"]] == ["S01"]
    objs = doc["sequences"][0]["parties"][0]["objectifs"]
    assert [(o["code"], o["type"]) for o in objs] == [("01", "connaissance"), ("02", "capacite")]
    assert objs[1]["criteres"]["F"] == "Lit"
    assert fmt.valider(doc) == []
    trace = json.loads((tmp_path / rid / "_verrouille" / "trace.json").read_text(encoding="utf-8"))
    assert [s["code"] for s in trace["sequences"]] == ["S01"]
    assert [e["id"] for e in trace["evaluations"]] == ["ev_s01"]
    assert ri.instantane_du_referentiel(c, rid) == "atelier"


def test_ri3_ri4_mise_en_route_numero_de_mise_en_route_et_duree_somme_des_objectifs(db6e, tmp_path):
    c = _c(db6e)
    rid = _creer(c, "mer")
    _verrouiller(c, rid, tmp_path)
    s = c.execute("SELECT numero, theme_code FROM referentiel_sequences WHERE referentiel_id=?",
                  (rid,)).fetchall()
    assert [tuple(x) for x in s] == [(1, "A")]                  # M01 → 1 (et non 201)
    for p in c.execute("SELECT numero, nb_seances_R_AE, libelle FROM referentiel_parties "
                       "WHERE referentiel_id=? ORDER BY numero", (rid,)):
        somme = c.execute("SELECT SUM(nb_seances) FROM referentiel_objectifs WHERE "
                          "referentiel_id=? AND partie_numero=?", (rid, p["numero"])).fetchone()[0]
        assert p["nb_seances_R_AE"] == somme and somme > 0
        assert p["libelle"]
    doc = fmt.construire(c, rid)
    assert doc["referentiel"]["type"] == "mer"
    # La version complète d'une fiche de cours (MR4) n'est pas une fiche de plus.
    assert not any(f["titre"].endswith("(version complète)") for s in doc["sequences"]
                   for p in s["parties"] for f in p.get("fiches", []))
    assert all(o["type"] == "capacite" for s in doc["sequences"] for p in s["parties"]
               for o in p["objectifs"])                          # MR1b : pas d'objectif Cours


def test_ri2_deverrouiller_retire_l_instantane_de_l_atelier(db6e, tmp_path):
    c = _c(db6e)
    rid = _creer(c, "principal")
    _verrouiller(c, rid, tmp_path)
    refs.deverrouiller(c, rid)
    for t in ri._TABLES_INSTANTANE:
        assert c.execute(f"SELECT COUNT(*) FROM {t} WHERE referentiel_id=?", (rid,)).fetchone()[0] == 0
    _verrouiller(c, rid, tmp_path)                                # recalculé
    assert c.execute("SELECT COUNT(*) FROM referentiel_objectifs WHERE referentiel_id=?",
                     (rid,)).fetchone()[0] == 2


def test_ri2_un_instantane_importe_garde_l_ancien_mecanisme_car_n11_v2025_ne_doit_pas_bouger(
        db6e, tmp_path):
    c = _c(db6e)
    rid = _creer(c, "principal")
    c.execute("INSERT INTO referentiel_sequences (referentiel_id, code, numero, nom) "
              "VALUES (?, 'S01', 1, 'Nom historique')", (rid,))
    c.execute("INSERT INTO referentiel_objectifs (referentiel_id, seq_code, code, nom, "
              "partie_numero) VALUES (?, 'S01', '99', 'Objectif historique', 1)", (rid,))
    c.commit()
    assert not ri.instantane_par_atelier(c, rid)
    _verrouiller(c, rid, tmp_path)
    assert c.execute("SELECT nom FROM referentiel_sequences WHERE referentiel_id=?",
                     (rid,)).fetchone()[0] == "Nom historique"
    assert c.execute("SELECT COUNT(*) FROM referentiel_objectifs WHERE referentiel_id=? AND "
                     "code='99'", (rid,)).fetchone()[0] == 1
    assert ri.instantane_du_referentiel(c, rid) == ""


# ── RI8 Concurrents du même type ────────────────────────────────────────────

def test_ri8_verrouiller_la_mise_en_route_n_annule_pas_le_principal_de_la_meme_annee(db6e, tmp_path):
    c = _c(db6e)
    principal = _creer(c, "principal")           # 2026_N09 (ou année courante)
    mer = _creer(c, "mer")                       # même année, suffixe b
    assert ri.type_du_referentiel(c, mer) == "mer"
    assert refs.lister_concurrents_a_annuler(c, mer) == []
    _verrouiller(c, mer, tmp_path)
    assert c.execute("SELECT etat FROM referentiel_niveaux WHERE id=?",
                     (principal,)).fetchone()[0] != "annule"
    # Deux principaux de la même année restent concurrents (comme avant).
    autre = _creer(c, "principal")
    assert [x["id"] for x in refs.lister_concurrents_a_annuler(c, autre)] == [principal]


# ── RI6 Catalogue et cibles des mises en route ──────────────────────────────

def test_ri6_un_referentiel_de_mises_en_route_publie_ses_documents_par_partie(db6e):
    c = _c(db6e)
    rid = _creer(c, "mer")
    assert gd.types_du_referentiel(c, rid) == ("mer_fiches_cours_6e", "mer_seances_6e",
                                               "mer_tests_courts_6e", "mer_activites_6e",
                                               "mer_dossiers_6e")
    from services import referentiel_documents as rd
    docs = {d["type_document"]: d for d in rd.lister_documents(c, rid)}
    assert set(docs) == set(gd.types_du_referentiel(c, rid))
    cib = lister_cibles_document(c, docs["mer_seances_6e"]["id"], rid, "mer_seances_6e")
    assert [x["cible_id"] for x in cib] == [f"N09/M01/p{n}" for n in (1, 2, 3, 4)]
    assert all(x["partie"] and x["sequence"] == "M01" for x in cib)
    tests = lister_cibles_document(c, docs["mer_tests_courts_6e"]["id"], rid, "mer_tests_courts_6e")
    assert tests and all(x["cible_id"].endswith("/T1") for x in tests)
    # Le principal et le cycle 4 gardent leur catalogue.
    assert gd.catalogue_type("sixieme", "principal") == gd.catalogue("sixieme")
    assert gd.catalogue_type("cycle4", "mer") == gd.catalogue("cycle4")


def test_ri6_le_producteur_rend_le_meme_tex_que_l_onglet_rendu_pdf(db6e):
    from services import mises_en_route_6e as m
    from services import orchestrateur_compilation as orch
    c = _c(db6e)
    cible = {"niveau": "N09", "sequence": "M01", "partie": 2}
    tex = orch.REGISTRE["mer_seances_6e"](c, cible, {"version": "corrigee", "par_page": "3"}, [], [])
    assert tex == m.generer_document_mer(c, "N09", "M01", {"document": "planche", "partie": 2,
                                                           "version": "corrigee", "par_page": 3},
                                         [], [])
    dos = orch.REGISTRE["mer_dossiers_6e"](c, cible, {}, [], [])
    assert dos == m.generer_document_mer(c, "N09", "M01", {"document": "dossier", "partie": 2},
                                         [], [])


def test_ri6_options_des_documents_de_mise_en_route_sont_validees(db6e):
    from services.referentiel_documents import DocumentErreur
    assert gd.valider_options("mer_seances_6e", {"par_page": "2"}) == {"par_page": "2"}
    with pytest.raises(DocumentErreur):
        gd.valider_options("mer_seances_6e", {"par_page": "5"})


# ── RI7 Documents compilés rattachés à la partie, format 1.4 ────────────────

def test_ri7_documents_de_mise_en_route_rattaches_a_leur_partie_en_format_1_4(db6e, tmp_path):
    c = _c(db6e)
    rid = _creer(c, "mer")
    _verrouiller(c, rid, tmp_path)
    from services import referentiel_documents as rd
    doc_id = next(d["id"] for d in rd.lister_documents(c, rid)
                  if d["type_document"] == "mer_fiches_cours_6e")
    c.execute("UPDATE referentiel_documents SET options=? WHERE id=?",
              (json.dumps({"actif": True}), doc_id))
    c.commit()
    data = tmp_path / "data"
    dossier = data / "referentiels" / rid
    dossier.mkdir(parents=True)
    for x in lister_cibles_document(c, doc_id, rid, "mer_fiches_cours_6e"):
        (dossier / x["nom_fichier"]).write_bytes(b"%PDF-1.4 essai")
    doc = fmt.construire(c, rid, data)
    assert doc["format_version"] == "1.4" and fmt.valider(doc) == []
    s = doc["sequences"][0]
    assert s["documents"] == []
    assert [p["documents"][0]["ref"] for p in s["parties"]] == \
        [f"mer_fiches_cours_6e|N09/M01/p{n}" for n in (1, 2, 3, 4)]


def test_ri7_un_principal_sans_document_de_partie_garde_sa_version_et_son_empreinte(db6e, tmp_path):
    """La version 1.4 ne sert qu'aux documents de partie : rien ne change
    pour les référentiels existants (N11_v2025 en classe)."""
    c = _c(db6e)
    rid = _creer(c, "principal")
    _verrouiller(c, rid, tmp_path)
    doc = fmt.construire(c, rid)
    assert doc["format_version"] == fmt.FORMAT_VERSION_FICHES
    assert fmt.FORMAT_VERSION == "1.4" and fmt.FORMAT_VERSION_MATERIEL == "1.3"


# ── RI10 Aperçu avant création, migration, profils ──────────────────────────

def test_ri10_apercu_avant_creation_dit_le_contenu_et_ne_cree_rien(db6e):
    app = create_app(db6e.parent, profil="atelier")
    cl = app.test_client()
    r = cl.get("/api/referentiels/apercu-creation?niveau=N09&type_ref=mer&gabarit=sixieme")
    a = r.get_json()["apercu"]
    assert r.status_code == 200 and a["nb_sequences"] == 1 and a["nb_parties"] == 4
    assert a["libelle_type"] == "Référentiel de mises en route"
    assert [d["cle"] for d in a["documents"]][0] == "mer_fiches_cours_6e"
    p = cl.get("/api/referentiels/apercu-creation?niveau=N09&type_ref=principal").get_json()["apercu"]
    assert p["nb_sequences"] == 1 and p["nb_objectifs"] == 1 and p["nb_objectifs_cours"] == 1
    assert cl.get("/api/referentiels/apercu-creation?niveau=N09&type_ref=x").status_code == 400
    assert cl.get("/api/referentiels?niveau=N09").get_json()["referentiels"] == []


def test_migration_instantane_idempotente(db6e):
    c = _c(db6e)
    assert ri.migrer(c) is False                  # déjà faite au démarrage
    assert "instantane" in {r[1] for r in c.execute("PRAGMA table_info(referentiel_niveaux)")}


def test_route_d_apercu_classee_atelier():
    from services.profils import ENDPOINTS
    assert ENDPOINTS["referentiels.api_apercu_creation"] == "atelier"


# ── RI13 Déverrouiller met de côté la publication figée ─────────────────────

def test_ri13_deverrouiller_met_de_cote_la_publication_sinon_l_ancien_contenu_serait_resservi(
        db6e, tmp_path):
    app = create_app(db6e.parent, profil="atelier")
    cl = app.test_client()
    with app.json_store._conn() as c:
        rid = _creer(c, "principal")
        _tout_valider(c)
        c.execute("UPDATE referentiel_niveaux SET etat='valide' WHERE id=?", (rid,))
        c.commit()
        from services.referentiel_documents_compilation import _dossier_du_referentiel
        fig.verrouiller_complet(c, rid, dossier_referentiel=_dossier_du_referentiel(
            app.json_store, rid), lister_cibles=lambda *a: [], force_confirme=True)
    assert cl.get(f"/api/publication/referentiels/{rid}.json").status_code == 200
    pub = db6e.parent / "referentiels" / rid / "_publication" / "referentiel.json"
    assert pub.is_file()
    r = cl.post(f"/api/referentiels/{rid}/deverrouiller")
    assert r.status_code == 200
    assert r.get_json()["publication_mise_de_cote"].startswith("_publication_avant_")
    assert not pub.exists()
