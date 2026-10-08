"""tests/test_v0_51_1_format_referentiel.py — v0.51.1

Format d'échange JSON d'un référentiel (`seqenseigne.referentiel` v1) :
structure complète (cycle, niveau, thèmes, découpage), parties, objectifs,
titres des notions et méthodes, documents ; textes sans LaTeX ; empreintes ;
publication figée des référentiels internes verrouillés ; validation par le
schéma (validateur interne et, si présente, bibliothèque jsonschema).
"""
import copy
import json
from datetime import date

import pytest

from services import format_referentiel as fmt
from services import referentiel_principal_externe as rpe
from services.texte_latex import vers_texte

AUJ = date(2026, 9, 1)


# ── Jeux de données ──────────────────────────────────────────────────────────

def _interne(app):
    """Référentiel interne 4e verrouillé, avec atomes vivants (notion,
    méthode) et un livret de séquence compilé figé."""
    store = app.json_store
    store.creer_referentiel({
        "id": "2025_N11", "niveau": "N11", "version": "2025", "etat": "verrouille",
        "description": "Référentiel 2025",
        "themes": [{"code": "A", "nom": r"Nombres et calculs", "couleur": "nombres"},
                   {"code": "B", "nom": r"Données \og et \fg{} fonctions", "couleur": "donnees"}],
        "sequences": [
            {"code": "S01", "numero": 1, "nom": r"Calcul avec $\frac{1}{2}$",
             "theme_code": "A",
             "objectifs": [
                 {"code": "01", "nom": "Connaître les notions et les méthodes",
                  "critere_f": r"Sait calculer $a\times b$"},
                 {"code": "02", "nom": "Développer", "fin_cycle": True}]},
            {"code": "S04", "numero": 4, "nom": "Statistiques", "theme_code": "B",
             "objectifs": []}]})
    with store._conn() as c:
        c.execute("UPDATE referentiel_objectifs SET type_obj='connaissance', nb_seances=1 "
                  "WHERE referentiel_id='2025_N11' AND code='01'")
        c.execute("UPDATE referentiel_objectifs SET nb_seances=2.5 "
                  "WHERE referentiel_id='2025_N11' AND code='02'")
        c.execute("INSERT INTO referentiel_parties (referentiel_id, seq_code, numero, "
                  "nb_seances_R_AE, libelle) VALUES ('2025_N11', 'S01', 1, 2, 'Développer')")
        # Atomes vivants (synthèse Pronote).
        c.execute("INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
                  "VALUES ('sn1', 'N11', 'S01')")
        c.execute("INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
                  "VALUES ('pt1', 'sn1', 1)")
        c.execute("INSERT INTO methodes (id, titre) VALUES ('m1', 'Développer $k(a+b)$')")
        c.execute("INSERT INTO notions (id, titre) VALUES ('n1', 'Distributivité')")
        c.execute("INSERT INTO objectifs (id, partie_id, code, nom, methode_id) "
                  "VALUES ('o1', 'pt1', '01', 'x', 'm1')")
        c.execute("INSERT INTO objectif_notions (objectif_id, notion_id, ordre) "
                  "VALUES ('o1', 'n1', 1)")
        c.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document) "
                  "VALUES ('rd1', '2025_N11', 'livret_sequence')")
    pdfs = store.data_dir / "referentiels" / "2025_N11" / "_verrouille" / "pdfs"
    pdfs.mkdir(parents=True)
    (pdfs / "livret_sequence__N11__S01.pdf").write_bytes(b"%PDF-1.4 livret S01")
    return "2025_N11"


def _externe(app, type_ref="principal"):
    store = app.json_store
    with store._conn() as c:
        r = rpe.creer(c, "N11", "2026-2027", "Manuel", type_ref=type_ref)
        rid = r["id"]
        s = rpe.ajouter_sequence(c, rid, "Fractions")
        rpe.ajouter_partie(c, rid, s["code"], 3, AUJ, libelle="Comparer")
        rpe.ajouter_objectif(c, rid, s["code"], 1, "Connaître le cours", 1, AUJ,
                             type_obj="connaissance")
        rpe.ajouter_objectif(c, rid, s["code"], 1, r"Comparer $\frac{a}{b}$", 2, AUJ,
                             criteres={"F": "Compare", "A": "", "E": ""})
        t = rpe.ajouter_type(c, "Fiche d'activité")
        f = rpe.ajouter_fichier(c, rid, s["code"], 1, nom_fichier="activite.pdf",
                                contenu=b"%PDF activite", mime="application/pdf",
                                data_dir=store.data_dir)
        rpe.typer_fichier(c, f["id"], t["id"])
        rpe.placer_fichier(c, f["id"], 2, "rendre", "semaines", 1)
        rpe.ajouter_fichier(c, rid, "", 0, nom_fichier="calendrier.pdf",
                            contenu=b"%PDF cal", mime="application/pdf",
                            data_dir=store.data_dir)
    return rid, s["code"], f["id"], t["id"]


def _exporter(app, rid):
    store = app.json_store
    with store._conn() as c:
        return fmt.exporter(c, rid, store.data_dir)


# ── Conversion des textes ────────────────────────────────────────────────────

@pytest.mark.parametrize("src,attendu", [
    (r"Développer \textbf{une expression}", "Développer une expression"),
    (r"Calculer $\frac{1}{2}+\frac{3}{4}$", "Calculer 1/2+3/4"),
    (r"Puissances $10^{-3}$ et $a^2$", "Puissances 10⁻³ et a²"),
    (r"$x \leqslant 3$", "x ⩽ 3"),
    (r"$x\neq0$ et $a\times b$", "x ≠ 0 et a × b"),
    (r"20~\% de réduction", "20 % de réduction"),
    (r"\og citation \fg{}", "« citation »"),
    (r"$\sqrt{2}$", "√(2)"),
    ("Texte simple", "Texte simple"),
])
def test_vers_texte(src, attendu):
    assert vers_texte(src) == attendu


# ── Référentiel interne ──────────────────────────────────────────────────────

def test_interne_structure_complete(app):
    rid = _interne(app)
    doc = _exporter(app, rid)
    assert fmt.valider(doc) == []
    assert doc["format"] == "seqenseigne.referentiel" and doc["format_version"] == "1.0"
    r = doc["referentiel"]
    assert (r["id"], r["niveau"], r["annee"], r["type"], r["source"], r["etat"]) == \
        ("2025_N11", "N11", "2025-2026", "principal", "interne", "verrouille")
    st = doc["structure"]
    assert st["cycle"] == {"code": "C04", "nom": st["cycle"]["nom"]}
    assert st["niveau"]["code"] == "N11" and st["niveau"]["annee_dans_cycle"] == 2
    assert [t["code"] for t in st["themes"]] == ["A", "B"]
    assert st["themes"][1]["nom"] == "Données « et » fonctions"
    assert "nom_latex" in st["themes"][1] and "nom_latex" not in st["themes"][0]
    assert [(s["code"], s["numero"], s["theme"]) for s in st["decoupage"]] == \
        [("S01", 1, "A"), ("S04", 4, "B")]
    assert st["decoupage"][0]["nom"] == "Calcul avec 1/2"
    assert st["empreinte"].startswith("sha256:")


def test_interne_parties_objectifs_titres_documents(app):
    rid = _interne(app)
    doc = _exporter(app, rid)
    s1 = doc["sequences"][0]
    p = s1["parties"][0]
    assert (p["numero"], p["libelle"], p["nb_seances"], p["nb_seances_objectifs"]) == \
        (1, "Développer", 2, 3.5)
    o1, o2 = p["objectifs"]
    assert (o1["code"], o1["type"]) == ("01", "connaissance")
    assert o1["criteres"]["F"] == "Sait calculer a × b"
    assert o1["criteres_latex"] == {"F": r"Sait calculer $a\times b$"}
    assert o2["fin_cycle"] is True and o2["nb_seances"] == 2.5
    assert p["notions"] == [{"id": "n1", "titre": "Distributivité"}]
    assert p["methodes"] == [{"id": "m1", "titre": "Développer k(a+b)"}]
    livret, = s1["documents"]
    assert livret["ref"] == "livret_sequence|N11/S01"           # clé de progression_doc
    assert livret["origine"] == "compile" and livret["fichier"]["sha256"]
    assert livret["fichier"]["taille"] == len(b"%PDF-1.4 livret S01")
    # La séquence S04 n'a pas de livret compilé ni de partie.
    assert doc["sequences"][1] == {"code": "S04", "parties": [], "documents": []}


def test_publication_figee_des_internes_verrouilles(app):
    rid = _interne(app)
    doc1 = _exporter(app, rid)
    stocke = app.json_store.data_dir / "referentiels" / rid / "_publication" / "referentiel.json"
    assert stocke.is_file() and doc1["publication_figee"]
    # Les atomes changent (nouveau référentiel en cours) : la publication du
    # référentiel verrouillé ne bouge pas.
    with app.json_store._conn() as c:
        c.execute("UPDATE notions SET titre='Autre titre' WHERE id='n1'")
        c.execute("UPDATE referentiel_niveaux SET etat='utilise' WHERE id=?", (rid,))
    doc2 = _exporter(app, rid)
    assert doc2["sequences"][0]["parties"][0]["notions"][0]["titre"] == "Distributivité"
    assert doc2["empreinte"] == doc1["empreinte"]
    assert doc2["referentiel"]["etat"] == "utilise"             # l'état suit
    assert fmt.valider(doc2) == []


def test_interne_en_cours_non_fige(app):
    rid = _interne(app)
    with app.json_store._conn() as c:
        c.execute("UPDATE referentiel_niveaux SET etat='en_cours' WHERE id=?", (rid,))
    doc = _exporter(app, rid)
    assert not doc.get("publication_figee")
    assert not (app.json_store.data_dir / "referentiels" / rid / "_publication").exists()


# ── Référentiel externe et MER ───────────────────────────────────────────────

def test_externe_documents_types_et_placement(app):
    rid, seq, fid, tid = _externe(app)
    doc = _exporter(app, rid)
    assert fmt.valider(doc) == []
    assert doc["referentiel"]["source"] == "externe"
    assert doc["referentiel"]["annee"] == "2026-2027"
    assert doc["structure"]["themes"] == []
    assert doc["structure"]["decoupage"][0]["theme"] is None
    p = doc["sequences"][0]["parties"][0]
    assert p["nb_seances"] == 3 and p["notions"] == [] and p["methodes"] == []
    assert p["objectifs"][1]["nom"] == "Comparer a/b"
    d, = p["documents"]
    assert d["ref"] == fid and d["type"] == tid and d["origine"] == "fichier"
    assert d["libelle"] == "Fiche d'activité : activite.pdf"
    assert d["placement"] == {"seance": 2, "retour": "rendre",
                              "delai": {"type": "semaines", "n": 1}}
    assert len(d["fichier"]["sha256"]) == 64
    assert doc["types_documents"] == [{"id": tid, "libelle": "Fiche d'activité"}]
    annuel, = doc["documents_annuels"]
    assert annuel["fichier"]["nom"] == "calendrier.pdf" and annuel["placement"] is None


def test_externe_suit_les_modifications(app):
    rid, seq, fid, tid = _externe(app)
    e1 = _exporter(app, rid)["empreinte"]
    assert _exporter(app, rid)["empreinte"] == e1               # stable
    with app.json_store._conn() as c:
        rpe.modifier(c, rid, "Manuel 2e édition")
    doc = _exporter(app, rid)
    assert doc["empreinte"] != e1 and not doc.get("publication_figee")


def test_mer(app):
    rid, *_ = _externe(app, type_ref="mer")
    doc = _exporter(app, rid)
    assert fmt.valider(doc) == []
    assert doc["referentiel"]["type"] == "mer"
    assert doc["structure"]["decoupage"][0]["code"].startswith("M")


def test_ancien_modele_de_mer_refuse(app):
    from services import referentiel_externe as rx
    with app.json_store._conn() as c:
        r = rx.creer(c, niveau="N11", annee="2026-2027", type="mer", nom="Ancien")
        with pytest.raises(fmt.FormatErreur) as e:
            fmt.exporter(c, r["id"], app.json_store.data_dir)
    assert e.value.code == "ancien_modele"


# ── Empreintes et validation ─────────────────────────────────────────────────

def test_empreinte_hors_metadonnees_et_etat(app):
    rid, *_ = _externe(app)
    doc = _exporter(app, rid)
    autre = copy.deepcopy(doc)
    autre["exporte_le"] = "2030-01-01T00:00:00+01:00"
    autre["referentiel"]["etat"] = "valide"
    assert fmt.empreinte(autre) == doc["empreinte"]
    autre["referentiel"]["description"] = "x"
    assert fmt.empreinte(autre) != doc["empreinte"]


def test_validation_detecte_les_erreurs(app):
    rid = _interne(app)
    doc = _exporter(app, rid)
    d = copy.deepcopy(doc)
    d["structure"]["decoupage"][0]["theme"] = "Z"
    d["structure"]["empreinte"] = fmt.empreinte_structure(d["structure"])
    d["empreinte"] = fmt.empreinte(d)
    assert any("thème Z inconnu" in e for e in fmt.valider(d))
    d = copy.deepcopy(doc)
    d["sequences"][0]["parties"][0]["objectifs"][0]["nom"] = "modifié"
    assert any("empreinte ne correspond" in e for e in fmt.valider(d))
    d = copy.deepcopy(doc)
    d["champ_inconnu"] = 1
    assert any("champ inconnu" in e for e in fmt.valider(d))
    d = copy.deepcopy(doc)
    d["format_version"] = "2.0"
    assert fmt.valider(d)
    d = copy.deepcopy(doc)
    del d["sequences"][0]["parties"][0]["objectifs"][0]["criteres"]
    assert any("criteres" in e for e in fmt.valider(d))


def test_conforme_au_schema_officiel(app):
    jsonschema = pytest.importorskip("jsonschema")
    rid = _interne(app)
    rid2, *_ = _externe(app)
    for r in (rid, rid2):
        doc = _exporter(app, r)
        jsonschema.Draft202012Validator(fmt.schema()).validate(doc)


def test_schema_officiel_refuse_comme_le_validateur_interne(app):
    jsonschema = pytest.importorskip("jsonschema")
    rid, *_ = _externe(app)
    doc = _exporter(app, rid)
    doc["sequences"][0]["parties"][0]["documents"][0]["placement"]["retour"] = "oui"
    from services.schema_json import valider
    assert valider(doc, fmt.schema())
    assert list(jsonschema.Draft202012Validator(fmt.schema()).iter_errors(doc))


# ── Routes ───────────────────────────────────────────────────────────────────

def test_route_export_et_verification(app, client):
    rid, *_ = _externe(app)
    r = client.get(f"/api/publication/referentiels/{rid}.json")
    assert r.status_code == 200 and r.mimetype == "application/json"
    assert "attachment" in r.headers["Content-Disposition"]
    doc = json.loads(r.get_data(as_text=True))
    assert fmt.valider(doc) == [] and doc["exporte_par"].endswith("(complet)")
    v = client.get(f"/api/publication/referentiels/{rid}/verification").get_json()
    assert v["valide"] and v["bilan"]["nb_sequences"] == 1
    assert v["bilan"]["documents_sans_fichier"] == []
    assert client.get("/api/publication/referentiels/inconnu.json").status_code == 404


def test_route_absente_du_profil_classe(data_dir):
    from app import create_app
    app = create_app(data_dir, profil="classe")
    assert app.test_client().get("/api/publication/referentiels/x.json").status_code == 404


def test_verification_ne_fige_pas(app, client):
    rid = _interne(app)
    v = client.get(f"/api/publication/referentiels/{rid}/verification").get_json()
    assert v["valide"] and not v["bilan"]["publication_figee"]
    pub = app.json_store.data_dir / "referentiels" / rid / "_publication" / "referentiel.json"
    assert not pub.exists()
    client.get(f"/api/publication/referentiels/{rid}.json")
    assert pub.is_file()
    v = client.get(f"/api/publication/referentiels/{rid}/verification").get_json()
    assert v["bilan"]["publication_figee"]
