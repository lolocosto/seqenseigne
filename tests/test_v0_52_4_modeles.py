"""tests/test_v0_52_4_modeles.py — v0.52.4

Le gabarit de documents devient un **modèle de référentiel**, indépendant du
niveau : « Notions et méthodes » (`cycle4`) ou « Fiches de résumé par
objectif » (`sixieme`). Chaque test nomme la décision qu'il protège
(doc/redemarrage_v0_52_4.md).

Non-régression : le cycle 4 produit exactement le même .tex (fichiers figés
des v0.52.1 et v0.52.2), même quand son référentiel est validé ou verrouillé,
qu'il garde des documents actifs de l'autre modèle, et qu'un autre niveau a
choisi le modèle « Fiches ». Seul écart admis : le nom par défaut de
l'objectif « Cours » des objectifs nouvellement créés (M6).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app  # noqa: E402
from services import gabarits_documents as gd  # noqa: E402
from tests.test_v0_52_1_gabarits_documents import (  # noqa: E402
    DONNEES as DONNEES_0521, GOLDEN, SQL_SIXIEME, peupler_cycle4)
from tests.test_v0_52_2_documents_6e import (  # noqa: E402
    DONNEES as DONNEES_0522, GOLDEN_2, SQL_PARASITES, _golden2, _tex)

RACINE = Path(__file__).parent.parent


def _actifs_autre_modele(conn, ref_id: str, gabarit: str) -> None:
    """Documents ACTIFS (non compilés) de l'autre modèle, restés en base."""
    for i, t in enumerate(gd.types(gabarit), start=1):
        conn.execute("INSERT OR IGNORE INTO referentiel_documents (id, referentiel_id, "
                     "type_document, options, ordre) VALUES (?, ?, ?, ?, ?)",
                     (f"x_{ref_id}_{i}", ref_id, t, json.dumps({"actif": True}), 50 + i))


@pytest.fixture
def app_c4x(data_dir):
    """Cycle 4 (N11) des tests v0.52.1/v0.52.2, mis à l'épreuve : R11 validé,
    R11B verrouillé, documents actifs du modèle « Fiches » dans les deux, un
    référentiel N11 annulé au modèle « Fiches », la 6e au modèle « Fiches »."""
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as c:
        peupler_cycle4(c)
        _golden2(c)
        c.executescript(SQL_PARASITES)
        c.execute("UPDATE referentiel_niveaux SET etat='valide' WHERE id='R11'")
        c.execute("UPDATE referentiel_niveaux SET etat='verrouille' WHERE id='R11B'")
        _actifs_autre_modele(c, "R11", "sixieme")
        _actifs_autre_modele(c, "R11B", "sixieme")
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, gabarit_documents) "
                  "VALUES ('R11Z', 'N11', '2099', 'annule', 'sixieme')")
        c.commit()
    return app


@pytest.fixture
def app_6e(data_dir):
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as c:
        c.executescript(SQL_SIXIEME)
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, gabarit_documents) "
                  "VALUES ('R09', 'N09', '2026', 'en_cours', 'sixieme')")
        c.commit()
    return app


# ── 1. Non-régression : le cycle 4 produit exactement le même .tex ──────────

@pytest.mark.parametrize("dossier,fichier,cible", (
    [(DONNEES_0521, f"cycle4_{t}.tex", ("R11", t, cid)) for t, cid, _ in GOLDEN]
    + [(DONNEES_0522, f"cycle4b_{t}.tex", ("R11B", t, cid)) for t, cid, _ in GOLDEN_2]))
def test_cycle4_meme_tex_referentiel_valide_ou_verrouille_et_documents_actifs_de_l_autre_modele(
        app_c4x, dossier, fichier, cible):
    """R1b, D2 : l'état du référentiel (validé, verrouillé), les documents
    actifs du modèle « Fiches » restés en base, un référentiel annulé au
    modèle « Fiches » ne changent rien au .tex du cycle 4."""
    ref_id, t, cid = cible
    with app_c4x.json_store._conn() as c:
        assert gd.gabarit_atelier_du_niveau(c, "N11") == "cycle4"
        tex = _tex(c, ref_id, t, cid)
    assert tex == (dossier / fichier).read_text(encoding="utf-8")


def test_cycle4_routes_de_l_atelier_inchangees_avec_un_referentiel_valide(app_c4x):
    """R1b : livret de séquence et rendu d'atome de l'atelier pour N11
    restent ceux du cycle 4 (plans de travail : comparaison des 42 plans de
    la base de démonstration, doc/redemarrage_v0_52_4.md)."""
    from services.latex_rendu_atome import generer_tex_par_type
    from services.livret_sequence import generer_livret_sequence
    app_c4x.configuration = type("C", (), {"tikz_libraries": lambda s: [],
                                           "tblr_libraries": lambda s: None})()
    cl = app_c4x.test_client()
    tex = cl.post("/api/v2/livret-sequence/N11/S01/rendu-tex",
                  json={"options": {}}).get_data(as_text=True)
    with app_c4x.json_store._conn() as c:
        assert tex == generer_livret_sequence(c, "N11", "S01", options={},
                                              tikz_libraries=[], tblr_libraries=None)
        assert "seqenseigne-style6e" not in generer_tex_par_type(
            c, "exercice", "ex_f1", None, tikz_libraries=None,
            tblr_libraries=["booktabs", "varwidth"])


def test_cycle4_format_d_echange_reste_1_1_a_l_identique_sans_fiches(app_c4x):
    """F2 : un référentiel « Notions et méthodes » ne change pas de version
    déclarée (1.1) ni de contenu : pas de `fiches`, empreinte stable."""
    from services import format_referentiel as fmt
    with app_c4x.json_store._conn() as c:
        doc = fmt.construire(c, "R11")
    assert doc["format_version"] == "1.1"
    assert all("fiches" not in p for s in doc["sequences"] for p in s["parties"])
    assert fmt.valider(doc) == []


def test_cycle4_objectifs_existants_non_renommes_seul_le_nouveau_cours_change_de_nom(app_c4x):
    """M6 : seul écart admis — un objectif « Cours » nouvellement créé
    s'appelle « Connaître le cours » ; les objectifs existants gardent leur
    nom (aucune migration)."""
    from services.v2_edition import activer_objectif_connaitre, creer_partie
    with app_c4x.json_store._conn() as c:
        avant = dict(c.execute("SELECT id, nom FROM objectifs").fetchall())
        p = creer_partie(c, "sn_n11_s01")
        o = activer_objectif_connaitre(c, p["id"])
        assert o["nom"] == "Connaître le cours" and o["code"] == "11"
        apres = dict(c.execute("SELECT id, nom FROM objectifs WHERE id <> ?", (o["id"],)))
    assert apres == avant


# ── 2. R1b : le référentiel de l'atelier, quel que soit son état ────────────

@pytest.mark.parametrize("etat", ["en_cours", "valide", "verrouille", "utilise"])
def test_r1b_atelier_suit_le_referentiel_interne_principal_quel_que_soit_son_etat(app_6e, etat):
    """Avant v0.52.4, un référentiel auto-validé ou verrouillé faisait
    retomber l'atelier sur le défaut du niveau : ici un référentiel N09 au
    modèle « Notions et méthodes » reste suivi dans tous les états."""
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE referentiel_niveaux SET etat=?, gabarit_documents='cycle4' "
                  "WHERE id='R09'", (etat,))
        assert gd.referentiel_atelier_du_niveau(c, "N09") == "R09"
        assert gd.gabarit_atelier_du_niveau(c, "N09") == "cycle4"


def test_r1b_annule_ignore_et_le_plus_recent_gagne(app_6e):
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE referentiel_niveaux SET etat='annule', gabarit_documents='cycle4' "
                  "WHERE id='R09'")
        assert gd.referentiel_atelier_du_niveau(c, "N09") is None
        assert gd.gabarit_atelier_du_niveau(c, "N09") == "sixieme"     # défaut du niveau
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, gabarit_documents) "
                  "VALUES ('R09a', 'N09', '2025', 'utilise', 'cycle4'), "
                  "('R09b', 'N09', '2026b', 'verrouille', 'sixieme')")
        assert gd.referentiel_atelier_du_niveau(c, "N09") == "R09b"
        # un référentiel externe n'est jamais celui de l'atelier
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, source) "
                  "VALUES ('X09', 'N09', '2099', 'en_cours', 'externe')")
        assert gd.referentiel_atelier_du_niveau(c, "N09") == "R09b"


def test_r1b_numerotation_du_livret_lit_les_options_du_referentiel_verrouille(app_6e):
    """options_livret (numérotation du livret, plan de travail) suit R1b."""
    from services.livret_sequence_6e import options_livret
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document, options, "
                  "ordre) VALUES ('d6', 'R09', 'livret_sequence_6e', ?, 1)",
                  (json.dumps({"actif": True, "inclure_activites": False}),))
        c.execute("UPDATE referentiel_niveaux SET etat='verrouille' WHERE id='R09'")
        assert options_livret(c, "N09")["inclure_activites"] is False


def test_r1b_route_de_l_atelier_suit_le_modele_du_referentiel_valide(app_6e):
    """La 6e au modèle « Notions et méthodes », référentiel validé : le
    livret de l'atelier n'est plus le livret « Fiches »."""
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE referentiel_niveaux SET etat='valide', gabarit_documents='cycle4' "
                  "WHERE id='R09'")
    app_6e.configuration = type("C", (), {"tikz_libraries": lambda s: [],
                                          "tblr_libraries": lambda s: None})()
    tex = app_6e.test_client().post("/api/v2/livret-sequence/N09/S01/rendu-tex",
                                    json={"options": {}}).get_data(as_text=True)
    assert "seqCouvertureLivretSix" not in tex


# ── 3. D2 : seuls les documents du modèle comptent ──────────────────────────

def test_d2_validation_figeage_et_publication_ignorent_les_documents_de_l_autre_modele(
        app_6e, monkeypatch):
    """Des documents actifs du modèle « Notions et méthodes », restés en base
    après un changement de modèle, ne bloquent pas la validation, ne sont
    pas figés et ne sont pas publiés."""
    from services import format_referentiel as fmt
    from services import referentiel_documents_compilation as rdc
    from services.referentiel_figeage import _trace_documents
    from services.referentiel_validation import _statut_documents_du_referentiel
    from services.referentiel_documents import initialiser_documents_defaut
    with app_6e.json_store._conn() as c:
        initialiser_documents_defaut(c, "R09")                  # modèle « Fiches »
        c.execute("UPDATE referentiel_documents SET options='{\"actif\": true}' "
                  "WHERE referentiel_id='R09' AND type_document='livret_sequence_6e'")
        _actifs_autre_modele(c, "R09", "cycle4")
        assert _statut_documents_du_referentiel(c, "R09")["non_compiles"] == 1   # le 6e seul
        c.execute("UPDATE referentiel_documents SET compile_ok=1, compile_date='2099-01-01' "
                  "WHERE referentiel_id='R09'")
        vus = []
        _trace_documents(c, "R09", lambda conn, did, rid, t: vus.append(t) or [])
        assert vus == ["livret_sequence_6e"]
        publies = []
        monkeypatch.setattr(rdc, "lister_cibles_document",
                            lambda conn, did, rid, t: publies.append(t) or [])
        ref = dict(c.execute("SELECT * FROM referentiel_niveaux WHERE id='R09'").fetchone())
        fmt._documents_compiles(c, ref, app_6e.json_store.data_dir, [])
    assert publies and not set(publies) & set(gd.types("cycle4"))


# ── 4. M3 : validation du référentiel au modèle « Fiches » ──────────────────

def test_m3_modele_fiches_ne_compte_ni_notions_ni_methodes_ni_cartes(app_6e):
    from services.referentiel_validation import _compter_atomes_non_valides
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO notions (id, niveau, sequence, fichier, titre) "
                  "VALUES ('n9', 'N09', 'S01', '', 'Notion')")
        c.execute("INSERT INTO methodes (id, niveau, sequence, fichier, titre) "
                  "VALUES ('m9', 'N09', 'S01', '', 'Méthode')")
        c.execute("INSERT INTO cartes_automatisme (id, niveau, sequence, num, titre) "
                  "VALUES ('c9', 'N09', 'S01', 1, 'Carte')")
        fiches = _compter_atomes_non_valides(c, "N09", "sixieme")
        notions = _compter_atomes_non_valides(c, "N09", "cycle4")
    assert fiches["notions"] == fiches["methodes"] == fiches["cartes_automatisme"] == 0
    assert notions["notions"] == notions["methodes"] == notions["cartes_automatisme"] == 1


def test_m3_archives_x_jamais_comptees_quel_que_soit_le_modele(app_6e):
    """Anciens exercices N09 (séquences Xnn) : pas des atomes du référentiel."""
    from services.referentiel_validation import _compter_atomes_non_valides
    with app_6e.json_store._conn() as c:
        avant = _compter_atomes_non_valides(c, "N09", "cycle4")["exercices"]
        c.execute("INSERT INTO exercices (id, serie, titre, niveau, sequence, num, serie_code, "
                  "fichier, enonce) VALUES ('x1', 'fondamental', 'Vieux', 'N09', 'X02', 1, 'F', "
                  "'', 'x')")
        for g in ("cycle4", "sixieme"):
            assert _compter_atomes_non_valides(c, "N09", g)["exercices"] == avant


# ── 5. M2 : validation d'une séquence au modèle « Fiches » ──────────────────

def _valider(c, sn_id):
    from services.v2_edition import ValidationSequenceErreur, _valider_sequence_hook
    try:
        _valider_sequence_hook(c, sn_id)
        return []
    except ValidationSequenceErreur as e:
        return e.details.get("raisons") or list(e.args[1:]) or [str(e)]


def test_m2_modele_fiches_serie_e_facultative_mais_fiche_de_l_objectif_exigee(app_6e):
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE objectifs SET critere_F='f', critere_A='a', critere_E='' "
                  "WHERE partie_id='p61'")
        c.execute("DELETE FROM objectif_exos WHERE serie='E'")
        c.execute("INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) "
                  "VALUES ('o603', 'A', 'aa1', 1)")
        raisons = " | ".join(map(str, _valider(c, "sn6")))
        assert "série E" not in raisons and "critère E" not in raisons
        assert "fiche" not in raisons                           # o602 et o603 en ont une
        c.execute("UPDATE fiches_resume SET objectif_id=NULL WHERE id='fr2'")
        raisons = " | ".join(map(str, _valider(c, "sn6")))
        assert "L'objectif 03 n'a pas de fiche de résumé." in raisons
        # un objectif qui a des exercices E doit avoir son critère E
        c.execute("INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) "
                  "VALUES ('o602', 'E', 'e1', 1)")
        assert "L'objectif 02 n'a pas de critère E." in " | ".join(map(str, _valider(c, "sn6")))


def test_m2_modele_notions_et_methodes_garde_la_regle_f_a_e(app_6e):
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE referentiel_niveaux SET gabarit_documents='cycle4' WHERE id='R09'")
        c.execute("UPDATE objectifs SET critere_F='f', critere_A='a', critere_E='e' "
                  "WHERE partie_id='p61'")
        raisons = " | ".join(map(str, _valider(c, "sn6")))
    assert "L'objectif 03 n'a pas d'exercice dans la série A, E." in raisons
    assert "fiche" not in raisons


# ── 6. M4 : synthèse Pronote et format d'échange au modèle « Fiches » ───────

def test_m4_synthese_propose_les_fiches_de_la_partie_au_lieu_des_notions(app_6e):
    from services.synthese_seance import candidats
    with app_6e.json_store._conn() as c:
        cand = candidats(c, "N09", "S01", 1, 1)
        assert cand["notions"] == [] and cand["methodes"] == []
        assert [f["titre"] for f in cand["fiches"]] == ["La valeur d'un chiffre",
                                                         "Les grands nombres"]
        c.execute("UPDATE referentiel_niveaux SET gabarit_documents='cycle4' WHERE id='R09'")
        assert "fiches" not in candidats(c, "N09", "S01", 1, 1)


def test_m4_choix_des_fiches_enregistres_et_deja_faits(app_6e):
    from services import synthese_seance as sy
    with app_6e.json_store._conn() as c:
        sy.migrer(c)
        sy.migrer(c)                                                # idempotent
        assert "fiches" in {r[1] for r in c.execute("PRAGMA table_info(seance_contenu)")}
        sy.enregistrer_contenu(c, "cl", "2026-09-07", "M1", {"fiches": ["fr1"]})
        assert sy.lire_contenu(c, "cl", "2026-09-07", "M1")["fiches"] == ["fr1"]
        assert sy.deja_faits(c, "cl", "2026-09-08", "M1", "2026-09-01", "2026-09-30")[
            "fiches"] == ["fr1"]


def test_m4_format_1_2_exporte_les_titres_des_fiches_de_la_partie(app_6e):
    from services import format_referentiel as fmt
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO referentiel_sequences (referentiel_id, code, numero, nom) "
                  "VALUES ('R09', 'S01', 1, 'Nombres')")
        c.execute("INSERT INTO referentiel_parties (referentiel_id, seq_code, numero) "
                  "VALUES ('R09', 'S01', 1)")
        doc = fmt.construire(c, "R09")
    assert doc["format_version"] == "1.2"
    p = doc["sequences"][0]["parties"][0]
    assert p["notions"] == [] and p["methodes"] == []
    assert [f["titre"] for f in p["fiches"]] == ["La valeur d'un chiffre", "Les grands nombres"]
    assert fmt.valider(doc) == []
    assert fmt.schema()["$defs"]["partie"]["properties"]["fiches"]


def test_m4_base_de_classe_lit_les_fiches_publiees():
    """Appli en ligne (pas d'objectifs) : les titres importés de nature
    « fiche » forment la partie « cours » de la synthèse."""
    from services import import_publication as ip
    from services.synthese_seance import candidats
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("CREATE TABLE referentiel_niveaux (id TEXT, niveau TEXT, version TEXT, "
                    "etat TEXT, origine TEXT, publication_importe_le TEXT, "
                    "gabarit_documents TEXT);")
    ip.migrer(c)
    c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, origine, "
              "publication_importe_le, gabarit_documents) VALUES ('R', 'N10', '2026', "
              "'utilise', 'publication', '2026-09-01', 'sixieme')")
    c.execute("INSERT INTO referentiel_titres_publies VALUES ('R', 'S01', 1, 'fiche', 'fr1', "
              "'Fiche A', 0)")
    cand = candidats(c, "N10", "S01", 1, 1)
    assert cand["fiches"] == [{"id": "fr1", "titre": "Fiche A"}]


def test_m5_type_connaissance_selon_le_code_du_cours_et_non_le_rang(app_6e):
    """Une partie sans objectif « Cours » : son premier objectif est une
    capacité (l'ancien calcul par rang en faisait une connaissance)."""
    from services import format_referentiel as fmt
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO referentiel_sequences (referentiel_id, code, numero, nom) "
                  "VALUES ('R09', 'S01', 1, 'Nombres')")
        c.execute("INSERT INTO referentiel_parties (referentiel_id, seq_code, numero) "
                  "VALUES ('R09', 'S01', 1)")
        for code, nom in (("01", "Connaître le cours"), ("02", "Capacité")):
            c.execute("INSERT INTO referentiel_objectifs (referentiel_id, seq_code, partie_numero, "
                      "code, nom) VALUES ('R09', 'S01', 1, ?, ?)", (code, nom))
        types = lambda: {o["code"]: o["type"] for o in  # noqa: E731
                         fmt.construire(c, "R09")["sequences"][0]["parties"][0]["objectifs"]}
        assert types() == {"01": "connaissance", "02": "capacite"}
        c.execute("DELETE FROM referentiel_objectifs WHERE code='01'")
        assert types() == {"02": "capacite"}


# ── 7. M6 : nom par défaut de l'objectif Cours ──────────────────────────────

def test_m6_nom_par_defaut_connaitre_le_cours_et_ancien_defaut_de_la_configuration(tmp_path):
    from services.configuration import Configuration, NOM_CONNAITRE
    assert NOM_CONNAITRE == "Connaître le cours"
    cfg = Configuration(tmp_path)
    assert cfg.atelier_assemblage_criteres_connaitre()["nom"] == "Connaître le cours"
    cfg.enregistrer({"atelier_assemblage_criteres_connaitre": {
        "nom": "Connaître les notions et les méthodes", "critere_F": "x"}})
    assert cfg.charger()["atelier_assemblage_criteres_connaitre"]["nom"] == "Connaître le cours"
    cfg.enregistrer({"atelier_assemblage_criteres_connaitre": {"nom": "Mon cours"}})
    assert cfg.atelier_assemblage_criteres_connaitre()["nom"] == "Mon cours"


def test_m6_import_6e_renomme_le_cours_des_sequences_non_validees(app_6e):
    from outils import import_lot6e as imp
    cours = imp.charger_referentiel()["objectif_cours"]
    assert cours["nom"] == "Connaître le cours"
    with app_6e.json_store._conn() as c:
        oid, etat = imp._objectif(c, "sn6", "p61", "01", cours)
        assert (oid, etat) == ("o601", "mis à jour")
        assert c.execute("SELECT nom FROM objectifs WHERE id='o601'").fetchone()[0] == \
            "Connaître le cours"
        c.execute("UPDATE sequences_par_niveau SET etat_code='valide' WHERE id='sn6'")
        rapport = imp.Rapport()
        assert imp._seq_niveau(c, "S01", rapport) is None           # validée : non touchée
        assert any("validée" in a for a in rapport.anomalies)


def test_m6_plus_aucun_ancien_nom_par_defaut_a_la_creation():
    for f in ("static/app.js", "static/atelier_seqniv_assemblage.js", "templates/index.html",
              "routes/v2_edition.py", "routes/referentiel_principal_externe.py",
              "outils/objectifs_6e.json", "static/referentiel_pe.js"):
        assert "Connaître les notions et les méthodes" not in (RACINE / f).read_text(
            encoding="utf-8"), f


# ── 8. T1 : niveau paramétrable dans le module LaTeX ────────────────────────

def test_t1_livret_n10_au_modele_fiches_affiche_5e_et_la_6e_reste_6e(app_6e):
    from services.livret_sequence_6e import generer_livret_sequence_6e
    with app_6e.json_store._conn() as c:
        tex9 = generer_livret_sequence_6e(c, "N09", "S01", {})
        c.execute("UPDATE sequences_par_niveau SET niveau='N10' WHERE id='sn6'")
        tex10 = generer_livret_sequence_6e(c, "N10", "S01", {})
    assert r"\renewcommand{\seqNiveauCourt}{6e}" in tex9
    assert r"\renewcommand{\seqNiveauExposant}{6\textsuperscript{e}}" in tex9
    assert r"\renewcommand{\seqNiveauCourt}{5e}" in tex10
    assert r"\renewcommand{\seqNiveauExposant}{5\textsuperscript{e}}" in tex10
    assert "{6e}" not in tex10.split(r"\begin{document}")[1]


def test_t1_module_style6e_v0_5_sans_6e_en_dur_dans_les_en_tetes():
    """Le .sty livré est celui que `tex seqenseigne.ins` produit du .dtx."""
    dtx = (RACINE / "paquet" / "seqenseigne-style6e.dtx").read_text(encoding="utf-8")
    sty = (RACINE / "paquet" / "seqenseigne-style6e.sty").read_text(encoding="utf-8")
    # v0.52.5 : module en v0.6 (macros du lot S05) ; v0.52.7 : v0.7
    # (marqueurs de l'exercice) ; T1 reste en place.
    assert "v0.7 seqenseigne" in dtx and "v0.7 seqenseigne" in sty
    assert r"\changes{v0.5}" in dtx
    for src in (dtx, sty):
        assert r"\newcommand{\seqNiveauCourt}{6e}" in src
        assert r"\newcommand{\seqNiveauExposant}{6\textsuperscript{e}}" in src
        assert r"\newcommand{\seqIdentEleve}[1][\seqNiveauCourt]" in src
        assert "Niveau 6\\textsuperscript{e}" not in src
        assert "  6e \\seqTrous" not in src
    from services.style6e import MACROS
    assert {"seqNiveauCourt", "seqNiveauExposant"} <= set(MACROS)


# ── 9. L6b : nom de séquence dans le cycle du niveau ────────────────────────

def test_l6b_nom_de_sequence_du_cycle_du_niveau_c03_et_c04(data_dir):
    from services.v2_lecture import lire_sequence_par_niveau
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as c:
        peupler_cycle4(c)
        # 6e : S01 existe aussi en C03 (nom différent de celui du cycle 4).
        c.executescript(SQL_SIXIEME[SQL_SIXIEME.index(
            "INSERT OR IGNORE INTO cycles (code, nom) VALUES ('C03'"):])
        n09 = lire_sequence_par_niveau(c, "N09", "S01")["sequence_par_niveau"]["sequence_nom"]
        n11 = lire_sequence_par_niveau(c, "N11", "S01")["sequence_par_niveau"]["sequence_nom"]
    assert n09 == "Nombres entiers et décimaux"
    assert n11 == "Représentations d'un nombre"


# ── 10. G2b, M1, I2 : modèle modifiable, routes ─────────────────────────────

def test_g2b_modele_modifiable_en_cours_et_valide_fige_au_verrouillage(app_6e):
    cl = app_6e.test_client()
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE referentiel_niveaux SET etat='valide' WHERE id='R09'")
    r = cl.put("/api/referentiels/R09/gabarit-documents", json={"gabarit": "cycle4"})
    d = r.get_json()
    assert r.status_code == 200 and d["gabarit"] == "cycle4"
    assert d["etat"] == "en_cours"            # documents du nouveau modèle non compilés
    assert d["documents_actifs_hors_modele"] == 0
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE referentiel_documents SET options='{\"actif\": true}' "
                  "WHERE referentiel_id='R09' AND type_document='livret_sequence'")
    d = cl.put("/api/referentiels/R09/gabarit-documents", json={"gabarit": "sixieme"}).get_json()
    assert d["documents_actifs_hors_modele"] == 1
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE referentiel_niveaux SET etat='verrouille' WHERE id='R09'")
    assert cl.put("/api/referentiels/R09/gabarit-documents",
                  json={"gabarit": "cycle4"}).status_code == 409


def test_m1_route_des_modeles_libelles_descriptions_et_modele_de_chaque_niveau(app_6e):
    from services import profils
    d = app_6e.test_client().get("/api/gabarits-documents").get_json()
    assert [m["libelle"] for m in d["modeles"]] == ["Notions et méthodes",
                                                    "Fiches de résumé par objectif"]
    assert all(m["documents"] and m["series"] and m["completude"] for m in d["modeles"])
    assert d["niveaux"]["N09"] == "sixieme" and d["niveaux"]["N11"] == "cycle4"
    assert profils.categorie("referentiel_documents.api_gabarits_catalogue") == "structure"
    assert not any("(6e)" in t.libelle for t in gd.catalogue("sixieme"))


def test_i2_modele_du_niveau_ne_depend_pas_du_code_n09(app_6e):
    """Un référentiel N10 au modèle « Fiches », un N09 au modèle « Notions » :
    le serveur le dit à l'interface (plus aucun test « N09 »)."""
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE referentiel_niveaux SET gabarit_documents='cycle4' WHERE id='R09'")
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, gabarit_documents) "
                  "VALUES ('R10', 'N10', '2026', 'en_cours', 'sixieme')")
    d = app_6e.test_client().get("/api/gabarits-documents").get_json()
    assert d["niveaux"]["N09"] == "cycle4" and d["niveaux"]["N10"] == "sixieme"


# ── 11. A5 : assemblage au modèle « Fiches » ────────────────────────────────

def test_a5_route_de_l_assemblage_donne_modele_fiche_et_series_documents(app_6e):
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO exercices (id, serie, titre, niveau, sequence, num, serie_code, "
                  "fichier, enonce) VALUES ('tp1', 'travail personnel', 'TP', 'N09', 'S01', 1, "
                  "'TP', '', 'x')")
        c.execute("INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) "
                  "VALUES ('o602', 'TP', 'tp1', 1)")
    d = app_6e.test_client().get("/api/v2/sequences-par-niveau/N09/S01").get_json()
    assert d["modele"] == {"gabarit": "sixieme", "libelle": "Fiches de résumé par objectif"}
    o = {x["code"]: x for p in d["parties"] for x in p["objectifs"]}
    assert o["02"]["fiche"]["id"] == "fr1" and o["01"]["fiche"] is None
    assert [e["exercice_id"] for e in o["02"]["exos_documents"]["TP"]] == ["tp1"]
    assert "TP" not in o["02"]["exos_par_serie"]       # livrets : listes fermées


def test_a5_fiche_de_l_objectif_liee_remplacee_detachee(app_6e):
    cl = app_6e.test_client()
    r = cl.put("/api/v2/objectifs/o603/fiche", json={"fiche_id": "fr1"})
    assert r.status_code == 200 and r.get_json()["fiche"]["id"] == "fr1"
    with app_6e.json_store._conn() as c:
        lien = dict(c.execute("SELECT id, objectif_id FROM fiches_resume").fetchall())
    assert lien == {"fr1": "o603", "fr2": None}         # une seule fiche par objectif
    assert cl.put("/api/v2/objectifs/o603/fiche", json={"fiche_id": None}).status_code == 200
    with app_6e.json_store._conn() as c:
        assert c.execute("SELECT objectif_id FROM fiches_resume WHERE id='fr1'").fetchone()[0] \
            is None
        c.execute("INSERT INTO fiches_resume (id, titre, niveau, sequence, fichier) "
                  "VALUES ('frx', 'Ailleurs', 'N09', 'S02', '')")
    assert cl.put("/api/v2/objectifs/o603/fiche", json={"fiche_id": "frx"}).status_code == 409
    assert cl.put("/api/v2/objectifs/o603/fiche", json={"fiche_id": "nope"}).status_code == 404


def test_a5_objectif_sans_methode_ne_prend_pas_le_code_du_cours(app_6e):
    cl = app_6e.test_client()
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
                  "VALUES ('p62', 'sn6', 2)")
    r = cl.post("/api/v2/parties/p62/objectif", json={"nom": "", "reserver_cours": True})
    assert r.status_code == 201 and r.get_json()["code"] == "12"
    r = cl.post("/api/v2/parties/p62/objectif", json={"nom": "x"})
    assert r.get_json()["code"] == "11"                  # comportement historique


# ── 12. M4 : ligne Pronote d'une classe dont le niveau est au modèle « Fiches »

def test_m4_ligne_pronote_cours_fiches_de_resume_pour_un_niveau_au_modele_fiches(
        tmp_path, monkeypatch):
    """Une 4e (N11) conçue au modèle « Fiches » : la ligne « Cours » donne les
    fiches de résumé choisies, pas les notions ni les méthodes."""
    from tests.test_v0_47_1_synthese_pronote import _lire, st as _st
    from services import synthese_seance as sy
    s = _st.__wrapped__(tmp_path, monkeypatch)
    with s._conn() as c:
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, gabarit_documents) "
                  "VALUES ('R11', 'N11', '2026', 'valide', 'sixieme')")
        c.execute("INSERT INTO fiches_resume (id, titre, objectif_id, num_fiche, niveau, sequence, "
                  "fichier) VALUES ('fr1', 'Lire un \\emph{script}', 'ob2', 1, 'N11', 'S14', '')")
    r = _lire(s)
    assert r["candidats"]["fiches"] == [{"id": "fr1", "titre": "Lire un script"}]
    assert r["candidats"]["notions"] == [] and not r["externe"]
    with s._conn() as c:
        sy.enregistrer_contenu(c, "c1", "2026-10-05", "M1", {"fiches": ["fr1"],
                                                              "notions": ["no1"]})
    assert _lire(s)["contenu"].splitlines()[2] == "Cours : fiche de résumé (Lire un script)"
