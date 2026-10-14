"""tests/test_v0_51_12_bascule.py — v0.51.12

Bascule de la base partagée (data/) vers data_atelier/ et data_classe/ :
répartition des tables (structures absentes de chaque côté), aperçu sans
écriture, données attendues côté classe (titres des notions et méthodes,
noms et PDF des documents, cases du suivi, classes et élèves), verrous de
l'atelier par le retour d'usage n° 1, identités et séquence des échanges,
boîtes aux lettres croisées, data/ intact, refus (déjà faite, base d'un
autre rôle), dossier par défaut de chaque profil, routes.

Données fictives uniquement.
"""
import hashlib
import json
from datetime import date

import pytest

from app import create_app
from persistence.sqlite_store import SqliteStore
from services import bascule as bsc
from services import echanges as ech
from services import progression_doc as pgd
from services import referentiel_principal_externe as rpe
from services import repartition as rep
from services import synthese_seance as sy

from test_v0_51_1_format_referentiel import _externe, _interne

AUJ = date(2026, 10, 1)

YAML_N11 = """niveau: N11
cycle: C04
sequences:
- code: S01
  numero: 1
  nom: Calcul
  theme: A
  objectifs:
  - code: '02'
    nom: Développer
    fin_cycle: N
    criteres: {'2': '', '3': '', '4': ''}
    exercices:
      fondamental: [1, 2, 3]
      avancé: [1]
      exploration: []
"""


def _empreinte(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def partagee(data_dir):
    """Base partagée d'avant la bascule : un interne verrouillé (atomes, livret
    compilé), un externe (fichiers), un interne non verrouillé non utilisé,
    une classe avec élèves, progression, créneaux, suivi et documents."""
    (data_dir / "N11_sequences.yaml").write_text(YAML_N11, encoding="utf-8")
    app = create_app(data_dir, profil="complet")
    rint = _interne(app)
    rext, seq, fid, _tid = _externe(app)
    st = app.json_store
    st.creer_referentiel({"id": "2027_N10", "niveau": "N10", "version": "2027",
                          "etat": "en_cours", "description": "Brouillon",
                          "themes": [], "sequences": []})
    with st._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('et', 'Collège X', "
                  "'valide')")
        c.execute("INSERT INTO progressions (id, niveau, annee, etablissement_id, "
                  "referentiel_id) VALUES ('pgi', 'N11', '2026-2027', 'et', ?)", (rint,))
        c.execute("INSERT INTO creneaux (id, progression_id, seq_code, partie_debut, "
                  "partie_fin, date_debut) VALUES ('cri', 'pgi', 'S01', 1, 1, '2026-09-07')")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id, "
                  "progression_id) VALUES ('c4a', '4A', 'N11', '2026-2027', 'et', 'pgi')")
        c.execute("INSERT INTO eleves (id, nom, prenom) VALUES ('e1', 'Fictif', 'Alice')")
        c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES ('e1', 'c4a')")
        c.execute("INSERT INTO suivi (classe_id, seq_code, eleve_id, serie, num) VALUES "
                  "('c4a', 'S01', 'e1', 'fondamental', 2)")
        c.execute("INSERT INTO progressions (id, niveau, annee, etablissement_id, "
                  "referentiel_id) VALUES ('pge', 'N11', '2027-2028', 'et', ?)", (rext,))
        c.execute("INSERT INTO creneaux (id, progression_id, seq_code, date_debut) VALUES "
                  "('cre', 'pge', ?, '2026-09-14')", (seq,))
        c.execute("INSERT INTO preferences_items (id, type, valeur, ordre) VALUES "
                  "('pz', 'titre_zone_fiche', 'Zone', 1)")
    return {"app": app, "data": data_dir, "rint": rint, "rext": rext, "seq": seq, "fid": fid}


def _cote(racine, role):
    d = racine / bsc.DOSSIERS[role]
    a = create_app(d, profil=role)
    a.config["TESTING"] = True
    return a


def _basculer(p):
    return bsc.executer(p["app"].json_store)


# ── Répartition ─────────────────────────────────────────────────────────────

def test_repartition_couvre_toutes_les_tables(data_dir):
    st = SqliteStore(data_dir)
    with st._conn() as c:
        connues = set(rep.TABLES_CLASSE) | set(rep.TABLES_ATELIER) | set(rep.TABLES_DEUX)
        assert not (set(rep.TABLES_CLASSE) & set(rep.TABLES_ATELIER))
        assert not ((set(rep.TABLES_CLASSE) | set(rep.TABLES_ATELIER)) & set(rep.TABLES_DEUX))
        inconnues = rep.tables(c) - connues
    # Tables créées à la demande par des services (hors schema.sql) : classées aussi.
    assert not inconnues, inconnues


def test_elagage_au_demarrage(data_dir):
    st = SqliteStore(data_dir)
    with st._conn() as c:
        rep.definir_role(c, "classe")
    SqliteStore(data_dir)
    with st._conn() as c:
        t = rep.tables(c)
        assert "notions" not in t and "referentiel_documents" not in t
        assert "classes" in t and "referentiel_niveaux" in t and "publications" not in t


def test_table_non_vide_de_l_autre_cote_gardee(data_dir):
    st = SqliteStore(data_dir)
    with st._conn() as c:
        c.execute("INSERT INTO notions (id, titre) VALUES ('n1', 'T')")
        rep.definir_role(c, "classe")
        r = rep.elaguer(c)
        assert r["gardees"] == {"notions": 1} and "notions" in rep.tables(c)


# ── Aperçu ──────────────────────────────────────────────────────────────────

def test_apercu_sans_ecriture(partagee):
    p = partagee
    avant = _empreinte(p["data"] / "seqenseigne.db")
    ap = bsc.apercu(p["app"].json_store)
    assert ap["possible"] and ap["nb_publies"] == 2
    devenir = {r["id"]: r["devenir"] for r in ap["referentiels"]}
    assert devenir == {p["rint"]: "publie", p["rext"]: "publie", "2027_N10": "atelier"}
    assert ap["tables"]["classe"]["classes"] == 1 and ap["tables"]["atelier"]["notions"] == 1
    assert ap["tables"]["inconnues"] == []
    assert _empreinte(p["data"] / "seqenseigne.db") == avant
    assert not (p["data"].parent / "data_atelier").exists()


def test_apercu_signale_un_non_publiable_utilise(partagee):
    p = partagee
    with p["app"].json_store._conn() as c:
        c.execute("INSERT INTO progressions (id, niveau, annee, etablissement_id, "
                  "referentiel_id) VALUES ('pgb', 'N10', '2026-2027', 'et', '2027_N10')")
    ap = bsc.apercu(p["app"].json_store)
    assert {r["id"]: r["devenir"] for r in ap["referentiels"]}["2027_N10"] == "garde"
    assert any("2027" in a and "utilisé" in a for a in ap["avertissements"])


# ── Exécution ───────────────────────────────────────────────────────────────

def test_bascule_complete(partagee, capsys):
    p = partagee
    racine = p["data"].parent
    avant = _empreinte(p["data"] / "seqenseigne.db")
    rapport = _basculer(p)
    assert _empreinte(p["data"] / "seqenseigne.db") == avant          # data/ intact
    A, C = racine / "data_atelier", racine / "data_classe"
    assert bsc.role_du_dossier(A) == "atelier" and bsc.role_du_dossier(C) == "classe"
    assert json.loads((A / "BASCULE.json").read_text(encoding="utf-8"))["paquet"]["numero"] == 1
    assert {r["statut"] for r in rapport["paquet"]["referentiels"]} == {"mise_a_jour"}
    assert "notions" in rapport["classe"]["tables_retirees"]
    assert "classes" in rapport["atelier"]["tables_retirees"]
    assert "[répartition]" not in capsys.readouterr().out          # v0.51.13
    atelier, classe = _cote(racine, "atelier"), _cote(racine, "classe")
    with atelier.json_store._conn() as ca, classe.json_store._conn() as cc:
        ta, tc = rep.tables(ca), rep.tables(cc)
        # Structures absentes de chaque côté.
        assert not (ta & set(rep.TABLES_CLASSE)) and not (tc & set(rep.TABLES_ATELIER))
        # Identités, rôles, correspondants liés l'un à l'autre.
        ia, ic = ech.instance(ca), ech.instance(cc)
        assert ia["id"] != ic["id"] and (ia["role"], ic["role"]) == ("atelier", "classe")
        assert ech.correspondant(ca, "classe")["id"] == ic["id"]
        assert ech.correspondant(cc, "atelier")["id"] == ia["id"]
        assert ech.entete(ca, "paquet")["numero"] == 2
        assert ech.envois(ca, "paquet")[0]["acquitte_le"]               # accusé par l'usage
        # Boîtes aux lettres croisées.
        sort_a = ca.execute("SELECT valeur FROM depot_reglages WHERE cle='sortants'").fetchone()[0]
        assert sort_a == str(C / "echanges" / "entrants")
        # Référentiels : brouillon resté dans l'atelier seulement.
        refs_c = {r[0] for r in cc.execute("SELECT id FROM referentiel_niveaux")}
        assert refs_c == {p["rint"], p["rext"]}
        assert "2027_N10" in {r[0] for r in ca.execute("SELECT id FROM referentiel_niveaux")}
        assert {r[0] for r in cc.execute("SELECT origine FROM referentiel_niveaux")} == \
            {"publication"}
        # Préférences par côté.
        assert cc.execute("SELECT COUNT(*) FROM preferences_items WHERE "
                          "type='titre_zone_fiche'").fetchone()[0] == 0
        assert ca.execute("SELECT 1 FROM preferences_items WHERE id='pz'").fetchone()
        # Verrous de l'atelier : séquences commencées côté classe.
        assert rpe.est_utilise(ca, p["rext"]) and rpe.sequence_commencee(ca, p["rext"],
                                                                         p["seq"], AUJ)
        assert rpe.est_utilise(ca, p["rint"])


def _vue_classe(app, rext_seq):
    """Ce que l'appli de classe affiche : classes, cases du suivi, titres de
    la synthèse, documents proposés (noms), annuels."""
    cl = app.test_client()
    with app.json_store._conn() as c:
        cand = sy.candidats(c, "N11", "S01", 1, 1)
        d_int = pgd.documents_disponibles(c, "N11", "2026-2027", "S01")
        d_ext = pgd.documents_disponibles(c, "N11", "2026-2027", rext_seq)
    seqs = cl.get("/api/classes/c4a/sequences").get_json()
    return {"classes": [(c["nom"], [e["prenom"] for e in c["eleves"]])
                        for c in cl.get("/api/classes").get_json()["classes"]],
            "sequences": seqs["sequences"], "source": seqs["source"],
            "suivi": app.json_store.lire_suivi_classe("c4a"),
            "notions": cand["notions"], "methodes": cand["methodes"],
            "docs": d_int, "docs_ext": d_ext}


def test_donnees_attendues_cote_classe(partagee):
    p = partagee
    avant = _vue_classe(p["app"], p["seq"])                 # base partagée
    _basculer(p)
    classe = _cote(p["data"].parent, "classe")
    apres = _vue_classe(classe, p["seq"])
    # Rien de perdu, rien de changé — sauf les titres LaTeX des séquences, publiés
    # en texte lisible (format d'échange, v0.51.1).
    def _sans_noms(v):
        return {**v, "sequences": [(s["code"], [o["code"] for o in s["objectifs"]])
                                   for s in v["sequences"]]}
    assert _sans_noms(apres) == _sans_noms(avant)
    assert apres["sequences"][0]["nom"] == "Calcul avec 1/2"
    assert apres["classes"] == [("4A", ["Alice"])]
    assert apres["source"] == "referentiel" and \
        [s["code"] for s in apres["sequences"]] == ["S01", "S04"]
    assert apres["suivi"] == {"S01": {"e1": {"fondamental": [2]}}}
    assert [n["titre"] for n in apres["notions"]] == ["Distributivité"]
    assert [m["titre"] for m in apres["methodes"]] == ["Développer k(a+b)"]
    assert [d["libelle"] for d in apres["docs"]["sequence"]] == [
        "Livret de séquence — S01", "Fiche d'activité : activite.pdf (partie 1)"]
    assert [d["libelle"] for d in apres["docs"]["annuels"]] == ["calendrier.pdf"]
    # PDF servis.
    cl = classe.test_client()
    r = cl.get(f"/api/referentiels/{p['rint']}/pdf/livret_sequence__N11__S01.pdf")
    assert r.status_code == 200 and r.data == b"%PDF-1.4 livret S01"
    r = cl.get(f"/api/referentiels-principaux-externes/fichiers/{p['fid']}")
    assert r.status_code == 200 and r.data == b"%PDF activite"
    # Livrets distribués d'une progression (lecture) : ceux du paquet.
    docs = cl.get(f"/api/referentiels/{p['rint']}/documents").get_json()["documents"]
    assert [(d["type_document"], d["etat_effectif"]) for d in docs] == [("livret_sequence", "ok")]


def _valeur(nom, p, ref):
    nom = nom.lower()
    if "fid" in nom or "fichier" in nom:
        return p["fid"]
    if nom in ("rid", "ref_id", "referentiel_id", "id_ref") or "referentiel" in nom:
        return ref
    if "classe" in nom or nom == "cid":
        return "c4a"
    if "seq" in nom or nom == "code":
        return "S01"
    if "niveau" in nom:
        return "N11"
    if "annee" in nom:
        return "2026-2027"
    return "1"


def _balayer(app, role, p):
    import re
    from services import profils
    app.config["TESTING"] = False
    cl = app.test_client()
    erreurs = set()
    for regle in app.url_map.iter_rules():
        if "GET" not in regle.methods or not regle.rule.startswith("/api/") or \
                regle.rule.endswith("/run") or \
                not profils.autorise(role, regle.endpoint, "GET")[0]:
            continue                                    # /run : compilation en flux
        for ref in (p["rint"], p["rext"]):
            url = re.sub(r"<(?:[a-z]+:)?([a-z_]+)>",
                         lambda m: _valeur(m.group(1), p, ref), regle.rule)
            r = cl.get(url, query_string={"niveau": "N11", "annee": "2026-2027",
                                          "classe_id": "c4a", "sequence": "S01",
                                          "referentiel_id": ref, "date": "2026-09-07"})
            if r.status_code >= 500:
                erreurs.add(url)
    return erreurs


def test_balayage_des_routes_sans_erreur(partagee):
    """Toutes les routes GET de chaque appli, avec des identifiants réels :
    pas d'erreur 500 de plus qu'avec la base partagée (table absente lue sans
    garde)."""
    p = partagee
    avant = _balayer(p["app"], "complet", p)        # ex. rendu LaTeX sans paquet importé
    _basculer(p)
    for role in ("atelier", "classe"):
        apres = _balayer(_cote(p["data"].parent, role), role, p)
        assert apres - avant == set(), role


def test_bascule_refusee_si_deja_faite(partagee):
    p = partagee
    _basculer(p)
    with pytest.raises(bsc.BasculeErreur, match="déjà faite"):
        _basculer(p)


def test_dossier_d_essai_renomme(partagee):
    p = partagee
    essai = p["data"].parent / "data_classe"
    essai.mkdir()
    (essai / "x.txt").write_text("essai")
    rapport = _basculer(p)
    ancien = p["data"].parent / rapport["renommes"]["data_classe"]
    assert (ancien / "x.txt").read_text() == "essai"


def test_paquet_suivant_si_publications_anterieures(partagee):
    p = partagee
    from services import paquet_publication as pqt
    with p["app"].json_store._conn() as c:
        pqt.creer(c, p["data"], [p["rext"]])                    # paquet n° 1 (base partagée)
    rapport = _basculer(p)
    assert rapport["paquet"]["numero"] == 2
    classe = _cote(p["data"].parent, "classe")
    with classe.json_store._conn() as c:
        assert ech.controler(c, "paquet", None)["attendu"] == 3


def test_profil_et_base_d_un_autre_role(partagee):
    p = partagee
    _basculer(p)
    racine = p["data"].parent
    with pytest.raises(bsc.BasculeErreur, match="profil classe"):
        create_app(racine / "data_classe", profil="atelier")
    with pytest.raises(bsc.BasculeErreur, match="profil atelier"):
        create_app(racine / "data_atelier", profil="complet")
    assert bsc.dossier_par_defaut(racine, "atelier") == racine / "data_atelier"
    assert bsc.dossier_par_defaut(racine, "classe") == racine / "data_classe"
    assert bsc.dossier_par_defaut(racine, "complet") == racine / "data"


def test_dossier_par_defaut_avant_bascule(tmp_path):
    (tmp_path / "data_classe").mkdir()                        # base d'essai sans rôle
    SqliteStore(tmp_path / "data_classe")
    assert bsc.dossier_par_defaut(tmp_path, "classe") == tmp_path / "data"


def test_routes(partagee):
    p = partagee
    cl = p["app"].test_client()
    ap = cl.get("/api/bascule/apercu").get_json()
    assert ap["possible"] and ap["nb_publies"] == 2
    assert cl.post("/api/bascule", json={}).status_code == 400          # confirmation
    r = cl.post("/api/bascule", json={"confirmer": True})
    assert r.status_code == 200 and r.get_json()["paquet"]["numero"] == 1
    assert cl.post("/api/bascule", json={"confirmer": True}).status_code == 409
    # Hors profil complet : indisponible.
    atelier = _cote(p["data"].parent, "atelier")
    assert atelier.test_client().get("/api/bascule/apercu").status_code == 404
