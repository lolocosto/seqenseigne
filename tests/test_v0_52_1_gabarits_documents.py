"""tests/test_v0_52_1_gabarits_documents.py — v0.52.1

Gabarit de documents par référentiel (cycle4 / sixieme), livret 6e, fiches
de cours et corrigés 6e, format d'échange 1.1, documents proposés côté
classe. Chaque test nomme la décision qu'il protège
(doc/redemarrage_v0_52_1.md).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app  # noqa: E402
from persistence.sqlite_store import SqliteStore  # noqa: E402
from services import gabarits_documents as gd  # noqa: E402
from services import referentiel_documents as rd  # noqa: E402

DONNEES = Path(__file__).parent / "donnees_v0_52_1"


# ── Données ──────────────────────────────────────────────────────────────────

SQL_CYCLE4 = r"""
CREATE TABLE IF NOT EXISTS paquet_definitions (
    nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
    corps TEXT, corps_fin TEXT, texte_complet TEXT,
    fichier_source TEXT, ligne_debut INTEGER,
    macros_appelees TEXT, environnements_utilises TEXT,
    statut_rendu_atome TEXT DEFAULT 'reutilise',
    contenu_atome TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS paquet_requirepackage (
    fichier_source TEXT NOT NULL, ordre INTEGER NOT NULL, nom TEXT NOT NULL,
    options TEXT NOT NULL DEFAULT '', PRIMARY KEY (fichier_source, ordre));
INSERT OR IGNORE INTO cycles (code, nom) VALUES ('C04', 'Cycle 4');
INSERT OR IGNORE INTO themes (id, cycle_code, code, nom, code_couleur)
    VALUES ('th_A', 'C04', 'A', 'Nombres', 'nombres');
INSERT OR IGNORE INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
    VALUES ('sc_s01', 'C04', 'S01', 1, 'Représentations d''un nombre', 'th_A');
INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
    VALUES ('sn_n11_s01', 'N11', 'S01', '');
INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES ('pt_p1', 'sn_n11_s01', 1);
INSERT INTO notions (id, niveau, sequence, fichier, titre, num_connaissance, corps)
    VALUES ('no1', 'N11', 'S01', 'N11_S01_C01.tex', 'Notion 1', '01', 'La fréquence est ...');
INSERT INTO methodes (id, niveau, sequence, fichier, titre, num_methode, num_objectif, corps)
    VALUES ('me1', 'N11', 'S01', 'N11_S01_M01.tex', 'Calculer une fréquence', 1, '02', 'On compte ...');
INSERT INTO exercices (id, serie, titre, niveau, sequence, num, serie_code, fichier, enonce, corrige,
                       remed_enonce, remed_corrige)
    VALUES
    ('ex_f1', 'fondamental', 'F1', 'N11', 'S01', 1, 'F', 'f.tex', 'Énoncé F1', 'Corrigé F1', 'Remède F1', 'Corr R F1'),
    ('ex_a1', 'avancé', 'A1', 'N11', 'S01', 1, 'A', 'a.tex', 'Énoncé A1', 'Corrigé A1', '', ''),
    ('ex_e1', 'exploration', 'E1', 'N11', 'S01', 1, 'E', 'e.tex', 'Énoncé E1', 'Corrigé E1', '', ''),
    ('ex_ea1', 'approche', 'EA1', 'N11', 'S01', 1, 'AE', 'ae.tex', 'Énoncé EA1', 'Corrigé EA1', '', '');
INSERT INTO objectifs (id, partie_id, code, nom, methode_id) VALUES
    ('ob_01', 'pt_p1', '01', 'Connaître le cours', NULL),
    ('ob_02', 'pt_p1', '02', 'Calculer une fréquence', 'me1');
INSERT INTO objectif_notions (objectif_id, notion_id, ordre) VALUES ('ob_01', 'no1', 1);
INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) VALUES
    ('ob_02', 'F', 'ex_f1', 1), ('ob_02', 'A', 'ex_a1', 1), ('ob_02', 'E', 'ex_e1', 1);
INSERT INTO partie_exos_revision_approche (partie_id, type, exercice_id, ordre)
    VALUES ('pt_p1', 'EA', 'ex_ea1', 1);
INSERT INTO fiches_resume (id, titre, objectif_id, num_fiche, niveau, sequence, fichier)
    VALUES ('fi1', 'Fiche fréquence', 'ob_02', 1, 'N11', 'S01', 'fr.tex');
INSERT INTO objectif_fiches (objectif_id, fiche_id, ordre) VALUES ('ob_01', 'fi1', 1);
INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
    VALUES ('sec_fi1', 'fiche_resume', 'fi1', 'Définition', 0);
INSERT INTO atome_section_items (id, section_id, ordre, corps)
    VALUES ('it_fi1', 'sec_fi1', 0, 'La fréquence est \acompleter{n/N}.');
INSERT INTO evaluations (id, niveau, numero, ordre, titre, mode_notation)
    VALUES ('ev1', 'N11', 1, 1, 'Bilan T1', 'note');
INSERT INTO evaluation_exercices (evaluation_id, exercice_id, ordre, bareme_points)
    VALUES ('ev1', 'ex_f1', 1, 4.0), ('ev1', 'ex_a1', 2, 6.0);
INSERT INTO referentiel_niveaux (id, niveau, version, etat) VALUES ('R11', 'N11', '2026', 'en_cours');
"""

# Documents du cycle 4 dont le .tex est figé (fichiers produits par le code
# de la v0.52.0 correctif 2, c412a70, sur ces mêmes données).
GOLDEN = (("livret_sequence", "N11/S01", {"actif": True}),
          ("livret_fiches", "unique", {"actif": True}),
          ("evaluation", "ev1", {"actif": True}))


def peupler_cycle4(conn) -> None:
    conn.executescript(SQL_CYCLE4)
    for i, (t, _, opts) in enumerate(GOLDEN, start=1):
        conn.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document, "
                     "options, ordre) VALUES (?, 'R11', ?, ?, ?)",
                     (f"rd{i}", t, json.dumps(opts), i))
    conn.commit()


def tex_cycle4(conn, type_doc: str, cible_id: str, avec_referentiel: bool = True) -> str:
    """.tex par le chemin réel de la compilation : cibles du document, puis
    producteur enregistré (avec le référentiel et son gabarit, v0.52.1)."""
    from services import orchestrateur_compilation as orch
    from services.referentiel_documents_compilation import lister_cibles_document
    doc_id = conn.execute("SELECT id FROM referentiel_documents WHERE referentiel_id='R11' "
                          "AND type_document=?", (type_doc,)).fetchone()[0]
    cible = next(c for c in lister_cibles_document(conn, doc_id, "R11", type_doc)
                 if c["cible_id"] == cible_id)
    if avec_referentiel:
        cible = {**cible, "referentiel_id": "R11",
                 "gabarit": gd.gabarit_du_referentiel(conn, "R11")}
    opts = json.loads(conn.execute("SELECT options FROM referentiel_documents WHERE id=?",
                                   (doc_id,)).fetchone()[0])
    return orch.REGISTRE[type_doc](conn, cible, opts, [], ["booktabs", "varwidth"])


SQL_PAQUET = SQL_CYCLE4.split("INSERT OR IGNORE INTO cycles")[0]

SQL_SIXIEME = SQL_PAQUET + r"""
INSERT OR IGNORE INTO cycles (code, nom) VALUES ('C03', 'Cycle 3');
INSERT OR IGNORE INTO themes (id, cycle_code, code, nom, code_couleur)
    VALUES ('th_6A', 'C03', 'A', 'Nombres, calcul', 'nombres');
INSERT OR IGNORE INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
    VALUES ('sc6_s01', 'C03', 'S01', 1, 'Nombres entiers et décimaux', 'th_6A');
INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
    VALUES ('sn6', 'N09', 'S01', ''), ('sn6x', 'N09', 'X02', '');
INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES ('p61', 'sn6', 1);
INSERT INTO objectifs (id, partie_id, code, nom) VALUES
    ('o601', 'p61', '01', 'Connaître les notions et les méthodes.'),
    ('o602', 'p61', '02', 'Utiliser la valeur des chiffres'),
    ('o603', 'p61', '03', 'Écrire un grand nombre');
INSERT INTO exercices (id, serie, titre, niveau, sequence, num, serie_code, fichier, enonce,
                       corrige, remed_enonce, remed_corrige) VALUES
    ('a1', 'approche', 'Un sudoku', 'N09', 'S01', 1, 'AE', '', 'Activité \seqReponse{x}', '', '', ''),
    ('a2', 'approche', 'Les grands nombres', 'N09', 'S01', 2, 'AE', '', 'Activité 2', '', '', ''),
    ('f1', 'fondamental', 'Former des nombres', 'N09', 'S01', 1, 'F', '', 'Énoncé F1',
     'Explication F1', 'Remède F1', ''),
    ('f2', 'fondamental', 'Placer les espaces', 'N09', 'S01', 2, 'F', '', 'Énoncé F2', '', '', ''),
    ('aa1', 'avancé', 'Devinettes', 'N09', 'S01', 1, 'A', '', 'Énoncé A1', '', '', ''),
    ('e1', 'exploration', 'Défi', 'N09', 'S01', 1, 'E', '', 'Énoncé E1', '', '', '');
INSERT INTO partie_exos_revision_approche (partie_id, type, exercice_id, ordre)
    VALUES ('p61', 'EA', 'a1', 1);
INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) VALUES
    ('o602', 'F', 'f1', 1), ('o602', 'A', 'aa1', 1), ('o602', 'E', 'e1', 1),
    ('o603', 'AE', 'a2', 1), ('o603', 'F', 'f2', 1), ('o603', 'F', 'f1', 2);
INSERT INTO fiches_resume (id, titre, objectif_id, num_fiche, niveau, sequence, fichier) VALUES
    ('fr1', 'La valeur d''un chiffre', 'o602', 1, 'N09', 'S01', ''),
    ('fr2', 'Les grands nombres', 'o603', 2, 'N09', 'S01', '');
INSERT INTO objectif_fiches (objectif_id, fiche_id, ordre) VALUES ('o601', 'fr1', 0), ('o601', 'fr2', 1);
INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre) VALUES
    ('s1', 'fiche_resume', 'fr1', '', 0), ('s2', 'fiche_resume', 'fr1', '1. Chiffres et nombres', 1),
    ('s3', 'fiche_resume', 'fr2', '1. Les classes', 0);
INSERT INTO atome_section_items (id, section_id, ordre, corps) VALUES
    ('i1', 's1', 0, 'Introduction'), ('i2', 's2', 0, 'On écrit avec \seqACompleter{dix chiffres}.'),
    ('i3', 's3', 0, 'Par classes de trois.');
"""


@pytest.fixture
def app_c4(data_dir):
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as c:
        peupler_cycle4(c)
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


# ── 1. Cycle 4 : exactement le même .tex qu'avant ────────────────────────────

@pytest.mark.parametrize("type_doc,cible_id,_opts", GOLDEN)
def test_cycle4_meme_tex_qu_avant_car_rien_ne_change_pour_le_cycle4(app_c4, type_doc,
                                                                      cible_id, _opts):
    """G1 : le gabarit cycle4 (défaut de tous les référentiels) produit au
    caractère près le .tex de la v0.52.0 — livret de séquence, livret de
    fiches et une évaluation, par le chemin réel de la compilation (qui
    passe désormais le référentiel et son gabarit au producteur)."""
    attendu = (DONNEES / f"cycle4_{type_doc}.tex").read_text(encoding="utf-8")
    with app_c4.json_store._conn() as c:
        assert gd.gabarit_du_referentiel(c, "R11") == "cycle4"
        assert tex_cycle4(c, type_doc, cible_id) == attendu


def test_preambule_sans_marges_explicites_inchange_pour_le_cycle4():
    """L5 : `marges` absent → la ligne \\newgeometry historique."""
    import inspect
    from services import preambule_atome as pa
    assert inspect.signature(pa.construire_preambule).parameters["marges"].default is None


# ── 2. Catalogue ─────────────────────────────────────────────────────────────

def test_catalogue_cycle4_reprend_les_9_cles_et_options_car_les_chaines_type_cible_sont_enregistrees():
    """G3 : mêmes clés, mêmes options, même ordre que referentiel_documents."""
    cat = gd.catalogue("cycle4")
    assert [t.cle for t in cat] == list(rd.TYPES_DOCUMENT)
    for t in cat:
        assert t.options == rd.OPTIONS_PAR_DEFAUT[t.cle]
    # v0.52.2 : + évaluations, travaux personnels, activités complémentaires,
    # séances d'atelier (clés nouvelles, aucune renommée).
    assert set(gd.types("sixieme")) == {"livret_sequence_6e", "fiches_cours_6e", "corriges_6e",
                                        "evaluation_6e", "travaux_personnels_6e",
                                        "activites_complementaires_6e", "seances_atelier_6e",
                                        "plans_travail_6e"}   # v0.52.3
    assert not set(gd.types("sixieme")) & set(rd.TYPES_DOCUMENT)


def test_options_6e_par_defaut_du_cadrage():
    t = gd.type_document("livret_sequence_6e")
    assert t.options == {"actif": False, "version": "eleve", "inclure_activites": True,
                         "inclure_serie_E": True, "remediations": "apres_exercice"}
    assert t.valeurs["remediations"] == ("apres_exercice", "en_fin", "aucune")


def test_gabarit_propose_selon_le_niveau_6e_sixieme_cycle4_ailleurs():
    """G1 : N09 → sixieme ; N10 à N12 → cycle4 ; valeur absente → cycle4."""
    assert gd.gabarit_par_defaut("N09") == "sixieme"
    assert [gd.gabarit_par_defaut(n) for n in ("N10", "N11", "N12")] == ["cycle4"] * 3
    assert gd.normaliser(None) == gd.normaliser("") == gd.normaliser("autre") == "cycle4"


def test_validation_en_python_refuse_cle_et_valeur_hors_catalogue():
    """G4 : plus de CHECK en base, la validation suit le catalogue du type."""
    with pytest.raises(rd.DocumentErreur):
        rd._valider_options("livret_sequence_6e", {"remediations": "partout"})
    with pytest.raises(rd.DocumentErreur):
        rd._valider_options("livret_sequence_6e", {"contenu": "cours_seul"})
    with pytest.raises(rd.DocumentErreur) as e:
        rd._valider_options("type_inconnu", {})
    assert e.value.code == "type_inconnu"
    assert rd._valider_options("corriges_6e", {"decoupage": "les_deux"}) == {"decoupage": "les_deux"}


# ── 3. Migration ─────────────────────────────────────────────────────────────

ANCIEN_DDL = """
CREATE TABLE referentiel_niveaux (id TEXT PRIMARY KEY, niveau TEXT NOT NULL,
    version TEXT NOT NULL, etat TEXT NOT NULL DEFAULT 'en_cours');
CREATE TABLE referentiel_documents (
    id TEXT PRIMARY KEY,
    referentiel_id TEXT NOT NULL REFERENCES referentiel_niveaux(id) ON DELETE CASCADE,
    type_document TEXT NOT NULL, options TEXT NOT NULL DEFAULT '{}',
    ordre INTEGER NOT NULL DEFAULT 0, mtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    compile_ok INTEGER, compile_date DATETIME, compile_log TEXT,
    compile_en_cours INTEGER NOT NULL DEFAULT 0,
    UNIQUE (referentiel_id, type_document),
    CHECK (type_document IN (
        'livret_sequence', 'livret_exercices', 'livret_cours',
        'livret_fiches', 'livret_plans', 'livret_corriges',
        'evaluation', 'livret_cartes_recap', 'livret_cartes_planches')));
INSERT INTO referentiel_niveaux VALUES ('N11_v2025', 'N11', '2025', 'utilise');
INSERT INTO referentiel_documents (id, referentiel_id, type_document, options, ordre, compile_ok)
    VALUES ('rdx', 'N11_v2025', 'livret_sequence', '{"actif": false}', 1, 1);
"""


def test_migration_unique_avec_sauvegarde_et_contenu_intact(tmp_path):
    """G4 : contrainte levée une seule fois, après sauvegarde JSON ; le
    référentiel validé en classe (N11_v2025) ne reçoit que `cycle4`."""
    c = sqlite3.connect(tmp_path / "b.db")
    c.row_factory = sqlite3.Row
    c.executescript(ANCIEN_DDL)
    r1 = gd.migrer(c, tmp_path)
    assert r1["colonne"] and r1["reconstruction"] and Path(r1["sauvegarde"]).is_file()
    sauve = json.loads(Path(r1["sauvegarde"]).read_text(encoding="utf-8"))
    assert sauve["tables"]["referentiel_documents"][0]["id"] == "rdx"
    assert not gd.contrainte_types_presente(c)
    assert dict(c.execute("SELECT id, type_document, options, compile_ok FROM "
                          "referentiel_documents").fetchone()) == \
        {"id": "rdx", "type_document": "livret_sequence", "options": '{"actif": false}',
         "compile_ok": 1}
    assert dict(c.execute("SELECT * FROM referentiel_niveaux").fetchone()) == \
        {"id": "N11_v2025", "niveau": "N11", "version": "2025", "etat": "utilise",
         "gabarit_documents": "cycle4"}
    c.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document) "
              "VALUES ('rd6', 'N11_v2025', 'livret_sequence_6e')")       # plus de CHECK
    r2 = gd.migrer(c, tmp_path)                                          # idempotente
    assert r2 == {"colonne": False, "reconstruction": False, "sauvegarde": ""}
    assert len(list((tmp_path / "sauvegardes").iterdir())) == 1
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []


def test_base_neuve_sans_contrainte_et_colonne_presente(data_dir):
    st = SqliteStore(data_dir)
    with st._conn() as c:
        assert not gd.contrainte_types_presente(c)
        assert "gabarit_documents" in {r[1] for r in c.execute(
            "PRAGMA table_info(referentiel_niveaux)")}


# ── 4. Documents à publier : seuls les types du gabarit ──────────────────────

def test_onglet_documents_ne_liste_que_le_gabarit_et_garde_l_autre_en_base(app_6e):
    """G5 : changer de gabarit ne supprime rien ; l'onglet ne montre que le
    gabarit courant ; les 6e portent libellé et champs (interface générique)."""
    with app_6e.json_store._conn() as c:
        docs = rd.lister_documents(c, "R09")
        assert [d["type_document"] for d in docs] == list(gd.types("sixieme"))
        # v0.52.4 (M1) : les libellés du catalogue perdent « (6e) ».
        assert docs[0]["libelle"] == "Livret de séquence" and docs[0]["champs"]
        gd.modifier(c, "R09", "cycle4")
        assert [d["type_document"] for d in rd.lister_documents(c, "R09")] == \
            list(rd.TYPES_DOCUMENT)
        assert c.execute("SELECT COUNT(*) FROM referentiel_documents WHERE referentiel_id="
                         "'R09'").fetchone()[0] == 9 + len(gd.types("sixieme"))
        assert "libelle" not in rd.lister_documents(c, "R09")[0]       # cycle 4 inchangé


def test_gabarit_fige_hors_en_cours_car_il_est_fige_au_verrouillage(app_6e):
    """G2."""
    cl = app_6e.test_client()
    r = cl.put("/api/referentiels/R09/gabarit-documents", json={"gabarit": "cycle4"})
    assert r.status_code == 200 and r.get_json()["gabarit"] == "cycle4"
    assert cl.put("/api/referentiels/R09/gabarit-documents",
                  json={"gabarit": "inconnu"}).status_code == 400
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE referentiel_niveaux SET etat='verrouille' WHERE id='R09'")
    assert cl.put("/api/referentiels/R09/gabarit-documents",
                  json={"gabarit": "sixieme"}).status_code == 409


def test_creation_interne_et_externe_preremplie_selon_le_niveau(client):
    """G1 : sans choix, le gabarit du niveau ; un choix explicite est gardé."""
    r = client.post("/api/referentiels/coquille", json={"niveau": "N09"})
    assert r.status_code == 201 and r.get_json()["ref"]["gabarit_documents"] == "sixieme"
    r = client.post("/api/referentiels/coquille", json={"niveau": "N11"})
    assert r.get_json()["ref"]["gabarit_documents"] == "cycle4"
    r = client.post("/api/referentiels/coquille", json={"niveau": "N09", "gabarit": "cycle4"})
    assert r.get_json()["ref"]["gabarit_documents"] == "cycle4"
    assert client.post("/api/referentiels/coquille",
                       json={"niveau": "N10", "gabarit": "x"}).status_code == 400
    r = client.post("/api/referentiels-principaux-externes",
                    json={"niveau": "N09", "annee": "2026-2027"})
    assert r.status_code == 201 and r.get_json()["gabarit_documents"] == "sixieme"
    liste = client.get("/api/referentiels?niveau=N11").get_json()["referentiels"]
    assert liste[0]["gabarit_documents"] == "cycle4"


def test_route_gabarit_classee_structure():
    from services.profils import categorie
    assert categorie("referentiel_documents.api_gabarit") == "structure"


# ── 5. Compilation : le producteur reçoit le référentiel ─────────────────────

def test_cibles_6e_par_sequence_sans_les_archives_x(app_6e):
    """L7 : les séquences d'archive Xnn ne sont jamais des cibles."""
    from services.referentiel_documents_compilation import lister_cibles_document
    with app_6e.json_store._conn() as c:
        docs = {d["type_document"]: d["id"] for d in rd.lister_documents(c, "R09")}
        cl = lister_cibles_document(c, docs["livret_sequence_6e"], "R09", "livret_sequence_6e")
        assert [x["cible_id"] for x in cl] == ["N09/S01"]
        assert cl[0]["nom_fichier"] == "livret_sequence_6e__N09__S01.pdf"
        rd.maj_options(c, docs["corriges_6e"], {"decoupage": "les_deux"})
        assert [x["cible_id"] for x in lister_cibles_document(
            c, docs["corriges_6e"], "R09", "corriges_6e")] == ["unique", "N09/S01"]


def test_compilation_refuse_un_document_hors_gabarit(app_6e):
    from services.referentiel_documents_compilation import CompilationErreur, compiler_document
    with app_6e.json_store._conn() as c:
        rd.lister_documents(c, "R09")
        gd.modifier(c, "R09", "cycle4")
        did = c.execute("SELECT id FROM referentiel_documents WHERE type_document="
                        "'livret_sequence_6e'").fetchone()[0]
        rd.maj_options(c, did, {"actif": True})
    with pytest.raises(CompilationErreur) as e:
        compiler_document(app_6e.json_store, did)
    assert e.value.code == "hors_gabarit"


def test_producteurs_6e_enregistres_et_recoivent_le_referentiel(app_6e):
    from services import orchestrateur_compilation as orch
    with app_6e.json_store._conn() as c:
        tex = orch.REGISTRE["livret_sequence_6e"](
            c, {"niveau": "N09", "sequence": "S01", "referentiel_id": "R09",
                "gabarit": "sixieme"}, {"actif": True, "version": "corrigee"}, [], [])
    assert r"\seqVersionCorrigee" in tex and r"\seqCouvertureLivretSix" in tex


# ── 6. Livret 6e ─────────────────────────────────────────────────────────────

def _livret(app, **opts):
    from services.livret_sequence_6e import generer_livret_sequence_6e
    with app.json_store._conn() as c:
        return generer_livret_sequence_6e(c, "N09", "S01", options=opts)


def test_livret_6e_structure_par_objectif(app_6e):
    tex = _livret(app_6e)
    corps = tex.split(r"\begin{document}")[1]
    i = corps.index
    # Couverture : capacités seulement (L3), nom de séquence du cycle 3 (L6).
    # v0.52.5 (C2, changement voulu) : objectifs rangés par partie, libellé
    # de outils/objectifs_6e.json, trait de la couleur du thème.
    assert (r"\seqCouvertureLivretSix*{Nombres entiers et décimaux}{%" "\n"
            r"\seqPartieCouvertureSix{Partie 1 --- Entiers et décimaux}"
            r"{S01-02/{Utiliser la valeur des chiffres},S01-03/{Écrire un grand nombre}}}") in corps
    assert "S01-01" not in corps
    # Partie → activité de partie (L1) → objectif 02 : fiche puis F, A, E.
    assert i("Partie 1") < i("Un sudoku") < i(r"\seqBandeauCapacite{S01-02}") \
        < i(r"\begin{seqFicheResumeSix}{La valeur d'un chiffre}") \
        < i(r"\begin{seqExoSix}[O][Former des nombres") < i("[R][Remédiation -- Former") \
        < i(r"\begin{seqExoSix}[A][Devinettes") < i(r"\begin{seqExoSix}[E][Défi") \
        < i(r"\seqBandeauCapacite{S01-03}")
    # Objectif 03 : activité rattachée à l'objectif sous son bandeau (L1).
    assert i(r"\seqBandeauCapacite{S01-03}") < i("Les grands nombres\\hfill") \
        < i(r"\begin{seqFicheResumeSix}{Les grands nombres}")
    # L4 : f1, aussi rattaché à 03, n'est émis qu'une fois.
    assert corps.count("[O][Former des nombres") == 1
    assert r"\seqLocExplication{Explication F1}" in corps
    assert r"\seqSectionFicheSix{1. Chiffres et nombres}" in corps
    assert r"\seqVersionCorrigee" not in tex


def test_livret_6e_une_seule_geometrie_celle_du_module_6e(app_6e):
    """L5 : pas de \\newgeometry du préambule d'atome ni de second \\geometry."""
    from services.livret_sequence_6e import GEOMETRIE_6E
    tex = _livret(app_6e)
    assert tex.count(r"\geometry{") + tex.count(r"\newgeometry{") == 1
    assert GEOMETRIE_6E in tex
    assert r"\usepackage{seqenseigne-style6e}" in tex


def test_livret_6e_options(app_6e):
    sans = _livret(app_6e, inclure_activites=False, inclure_serie_E=False, remediations="aucune")
    assert "Un sudoku" not in sans and "[E][Défi" not in sans and "Remédiation" not in sans
    fin = _livret(app_6e, remediations="en_fin")
    assert fin.index("[E][Défi") < fin.index("[R][Remédiation -- Former")
    corr = _livret(app_6e, version="corrigee")
    assert r"\seqVersionCorrigee" in corr and "corrigé}" in corr
    from services.livret_sequence_6e import Livret6eErreur
    with pytest.raises(Livret6eErreur):
        _livret(app_6e, version="prof")
    # Les options du livret du cycle 4 envoyées par l'atelier sont ignorées.
    assert _livret(app_6e, cours={"inclure": False}) == _livret(app_6e)


def test_fiches_de_cours_6e_version_complete_seules(app_6e):
    from services.livret_sequence_6e import generer_fiches_cours_6e
    with app_6e.json_store._conn() as c:
        tex = generer_fiches_cours_6e(c, "N09", "S01")
    assert r"\seqVersionComplete" in tex and tex.count(r"\begin{seqFicheResumeSix}") == 2
    assert "seqExoSix" not in tex.split(r"\begin{document}")[1]


def test_corriges_6e_version_corrigee_remediations_comprises(app_6e):
    from services.livret_sequence_6e import generer_corriges_6e
    with app_6e.json_store._conn() as c:
        tex = generer_corriges_6e(c, "N09", None, {"remediations": "aucune"})
    assert r"\seqVersionCorrigee" in tex and "[R][Remédiation -- Former" in tex


def test_archive_x_refusee(app_6e):
    from services.livret_sequence_6e import Livret6eErreur, lire_sequence_6e
    with app_6e.json_store._conn() as c, pytest.raises(Livret6eErreur):
        lire_sequence_6e(c, "N09", "X02")


# ── 7. Route de l'atelier ────────────────────────────────────────────────────

def test_route_atelier_n09_produit_le_livret_6e_par_defaut(app_6e):
    """R1 : sans paramètre, gabarit du référentiel interne en cours du niveau,
    sinon celui du niveau ; un paramètre explicite l'emporte."""
    cl = app_6e.test_client()
    tex = cl.post("/api/v2/livret-sequence/N09/S01/rendu-tex", json={"options": {}}).get_data(
        as_text=True)
    assert r"\seqCouvertureLivretSix" in tex
    tex = cl.post("/api/v2/livret-sequence/N09/S01/rendu-tex?version=corrigee").get_data(
        as_text=True)
    assert r"\seqVersionCorrigee" in tex
    tex = cl.post("/api/v2/livret-sequence/N09/S01/rendu-tex",
                  json={"gabarit": "cycle4"}).get_data(as_text=True)
    assert r"\seqCouvertureLivretSix" not in tex and "boiteTitreGen" in tex
    assert cl.post("/api/v2/livret-sequence/N09/S01/rendu-tex",
                   json={"gabarit": "x"}).status_code == 400


def test_route_atelier_cycle4_inchangee(app_c4):
    """R1 : un niveau du cycle 4 sans référentiel « sixieme » en cours garde
    le livret du cycle 4, identique au service historique."""
    from services.livret_sequence import generer_livret_sequence
    app_c4.configuration = type("C", (), {"tikz_libraries": lambda s: [],
                                          "tblr_libraries": lambda s: None})()
    tex = app_c4.test_client().post("/api/v2/livret-sequence/N11/S01/rendu-tex",
                                    json={"options": {}}).get_data(as_text=True)
    with app_c4.json_store._conn() as c:
        assert tex == generer_livret_sequence(c, "N11", "S01", options={},
                                              tikz_libraries=[], tblr_libraries=None)


# ── 8. Format d'échange 1.1 ──────────────────────────────────────────────────

def test_format_1_1_porte_le_gabarit_et_un_1_0_sans_champ_est_lu_cycle4(app_6e):
    from services import format_referentiel as fmt
    # v0.52.4 : format 1.2 (partie.fiches) ; un référentiel « Notions et
    # méthodes » reste déclaré 1.1 (FORMAT_VERSION_SANS_FICHES).
    assert fmt.FORMAT_VERSION == "1.2" and fmt.FORMAT_VERSION_SANS_FICHES == "1.1"
    prop = fmt.schema()["properties"]["referentiel"]["properties"]["gabarit_documents"]
    assert prop == {"enum": ["cycle4", "sixieme"]}
    with app_6e.json_store._conn() as c:
        doc = fmt.construire(c, "R09")
    assert doc["referentiel"]["gabarit_documents"] == "sixieme"
    assert fmt.valider(doc) == []
    doc10 = json.loads(json.dumps(doc))
    doc10["format_version"] = "1.0"
    del doc10["referentiel"]["gabarit_documents"]
    doc10["empreinte"] = fmt.empreinte(doc10)
    assert fmt.valider(doc10) == []
    assert gd.normaliser(doc10["referentiel"].get("gabarit_documents")) == "cycle4"


# ── 9. Côté classe : documents proposés (progression_doc) ────────────────────

def _classe(app, gabarit="cycle4", etat="en_cours"):
    with app.json_store._conn() as c:
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, gabarit_documents) "
                  "VALUES ('RA', 'N11', '2025', ?, ?), ('RB', 'N11', '2027', 'en_cours', 'cycle4')",
                  (etat, gabarit))
        for rid in ("RA", "RB"):
            for i, t in enumerate(("livret_sequence", "livret_fiches", "livret_sequence_6e"), 1):
                actif = not (rid == "RA" and t == "livret_fiches")
                c.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document, "
                          "options, ordre) VALUES (?, ?, ?, ?, ?)",
                          (f"{rid}{i}", rid, t, json.dumps({"actif": actif}), i))
        c.execute("INSERT INTO etablissements (id, nom) VALUES ('et', 'Collège')")
        c.execute("INSERT INTO progressions (id, niveau, annee, etablissement_id, referentiel_id) "
                  "VALUES ('pgA', 'N11', '2026-2027', 'et', 'RA')")


def _proposes(app, prog_ref):
    from services import progression_doc as pgd
    with app.json_store._conn() as c:
        d = pgd.documents_disponibles(c, "N11", "2026-2027", "S01", prog_ref=prog_ref)
    return sorted(x["doc_ref"] for x in d["sequence"] + d["annuels"] if x["source"] == "interne")


def test_classe_prend_le_referentiel_de_la_progression_pas_le_plus_recent(app_c4):
    _classe(app_c4)
    with app_c4.json_store._conn() as c:
        c.execute("DELETE FROM referentiel_documents WHERE referentiel_id='RA' "
                  "AND type_document='livret_sequence'")
        c.execute("UPDATE referentiel_documents SET options='{\"actif\": true}' WHERE id='RB2'")
    # RB (plus récent) proposerait le livret de fiches ; RA (celui de la
    # progression) n'a plus que des documents inactifs ou hors gabarit.
    assert _proposes(app_c4, "pgA") == []
    assert _proposes(app_c4, None) != []          # appel sans progression : comme avant


def test_classe_ne_propose_que_les_documents_actifs(app_c4):
    _classe(app_c4)
    assert _proposes(app_c4, "pgA") == ["livret_sequence|N11/S01"]   # fiches inactives


def test_classe_ne_propose_que_les_types_du_gabarit(app_c4):
    _classe(app_c4, gabarit="sixieme")
    with app_c4.json_store._conn() as c:
        c.execute("INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
                  "VALUES ('sn11b', 'N11', 'S02')")
    refs = _proposes(app_c4, "pgA")
    assert refs and all(r.startswith("livret_sequence_6e|") for r in refs)


def test_classe_referentiel_fige_propose_comme_avant_car_ses_cases_actif_ne_sont_pas_tenues(app_c4):
    """N11_v2025 (en classe cette année) a été importé avec toutes ses cases
    « actif » décochées : un référentiel verrouillé / utilisé propose ses
    documents comme avant v0.52.1."""
    _classe(app_c4, etat="utilise")
    assert "livret_fiches|unique" in _proposes(app_c4, "pgA")


def test_route_disponibles_transmet_la_progression(app_c4):
    _classe(app_c4)
    r = app_c4.test_client().get("/api/progression-doc/disponibles?niveau=N11&annee=2026-2027"
                                 "&sequence=S01&prog_ref=pgA").get_json()
    assert [d["doc_ref"] for d in r["sequence"] if d["source"] == "interne"] == \
        ["livret_sequence|N11/S01"]
