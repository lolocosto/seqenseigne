"""tests/test_v0_59_1_cartes_fiches.py — v0.59.1

Signalement de Laurent du 17 novembre 2026 (14 h 38) : « J'ai créé un
référentiel N11 pour 27-28 en cochant la case "cartes d'automatisme", mais je
ne retrouve ni les récap ni les planches dans les documents à produire. »
(`doc/redemarrage_v0_59_1.md`).

Invariants protégés :
  C1 catalogue : un principal au modèle Fiches AVEC l'option cartes publie, en
     fin de liste, le récap et les planches (clés du cycle 4, inchangées côté
     classe) ; sans l'option, en 6e, au cycle 4 et pour les mises en route,
     le catalogue est exactement celui d'avant ;
  C2 un référentiel créé en v0.59.0 (lignes du modèle déjà en base) reçoit les
     deux lignes à la première lecture ; un référentiel figé, ou du cycle 4,
     garde sa liste ;
  C3 cibles et cartes : comme au cycle 4, planches par séquence et récap
     annuel (plus un récap par séquence) ; les cartes sont celles RATTACHÉES
     AUX OBJECTIFS du principal (pas `cartes_automatisme.sequence`, qui
     donnerait les archives de 2025), validées seulement (règle existante),
     cartes d'un autre niveau comprises avec la couleur de leur thème ; verso
     des planches en miroir (v0.56.1) ;
  C4 « Tout compiler » d'une séquence Fiches avec l'option : récap et planches
     de la séquence ;
  C5 import : le lot fait foi pour les cartes qu'il cite (lien vers un autre
     objectif de la même séquence retiré, signalé par l'essai à blanc, gardé
     pour une carte validée ; liens de l'auteur intouchés) ;
  C6 titre de carte échappé (« Compléter 20 % de 120 » cassait la carte).
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from outils import import_lot6e as imp
from services import fiches_cycle4 as fc4
from services import gabarits_documents as gd
from tests.test_v0_52_0_import_lot6e import base as base_v052  # noqa: F401
from tests.test_v0_58_0_migration_themes_codes import _ins, _q  # noqa: F401
from tests.test_v0_59_0_ref4e_fiches import (  # noqa: F401
    _archiver,
    _importer,
    _lots,
    _table_reduite,
    base,
    base4e,
)

APPLI = Path(__file__).resolve().parent.parent
CARTES = ("livret_cartes_recap", "livret_cartes_planches")


def _conn(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


@pytest.fixture
def base4e_lot(base4e, tmp_path):
    """4e archivée + lot d'essai A1 importé (cartes 1 → A1-02, 2 → A1-03)."""
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, _lots(tmp_path), "--apply", "--yes") == 0
    return base4e


def _ref(c, rid="2027_N11", gabarit="sixieme", cartes=1, etat="en_cours", niveau="N11",
         version="2027", type_ref="principal"):
    _ins(c, "referentiel_niveaux", id=rid, niveau=niveau, version=version, etat=etat,
         source="interne", type_ref=type_ref, gabarit_documents=gabarit,
         cartes_automatisme=cartes)
    c.commit()


def _valider_cartes(c, sequence="A1"):
    c.execute("UPDATE cartes_automatisme SET etat_code='valide' WHERE niveau='N11' AND "
              "sequence=?", (sequence,))
    c.commit()


# ── C1 Catalogue ─────────────────────────────────────────────────────────────

def test_catalogue_fiches_avec_option_cartes_ajoute_recap_et_planches_en_fin():
    avec = gd.catalogue_type("sixieme", "principal", True)
    assert avec[:-2] == gd.catalogue("sixieme")
    assert tuple(t.cle for t in avec[-2:]) == CARTES
    # Mêmes objets que le cycle 4 : clés, options et producteurs inchangés (G3).
    c4 = {t.cle: t for t in gd.catalogue("cycle4")}
    assert all(t == c4[t.cle] for t in avec[-2:])


def test_catalogue_inchange_sans_option_en_6e_au_cycle_4_et_pour_les_mises_en_route():
    """« Sans l'option cartes, et pour la 6e, rien ne change. »"""
    assert gd.catalogue_type("sixieme", "principal") == gd.catalogue("sixieme")
    assert gd.catalogue_type("sixieme", "principal", False) == gd.catalogue("sixieme")
    assert gd.catalogue_type("cycle4", "principal", True) == gd.catalogue("cycle4")
    assert gd.catalogue_type("sixieme", "mer", True) == gd.catalogue_type("sixieme", "mer")


def test_types_du_referentiel_suivent_l_option(base4e):
    c = _conn(base4e)
    _ref(c, "2027_N11", cartes=1)
    _ref(c, "2027_N11b", cartes=0, version="2027b")
    _ref(c, "2026_N09", cartes=0, niveau="N09", version="2026")
    avec = gd.types_du_referentiel(c, "2027_N11")
    assert avec[-2:] == CARTES
    assert gd.types_du_referentiel(c, "2027_N11b") == gd.types("sixieme")
    assert gd.types_du_referentiel(c, "2026_N09") == gd.types("sixieme")
    c.close()


def test_apercu_de_creation_annonce_les_documents_de_cartes(base4e_lot):
    from services.referentiels_internes import contenu
    c = _conn(base4e_lot)
    a = contenu(c, "N11", "principal", "sixieme", cartes=True)
    b = contenu(c, "N11", "principal", "sixieme", cartes=False)
    c.close()
    assert [d["cle"] for d in a["documents"]][-2:] == list(CARTES)
    assert not any(d["cle"] in CARTES for d in b["documents"])


# ── C2 Liste des documents ───────────────────────────────────────────────────

def test_referentiel_cree_en_v0590_recoit_recap_et_planches_a_la_lecture(base4e):
    """Cas de Laurent : 2027_N11 créé hier, lignes 6e déjà en base. Avant la
    correction, l'initialisation ne se faisait que pour une liste vide."""
    from services.referentiel_documents import lister_documents
    c = _conn(base4e)
    _ref(c)
    # v0.59.2 : les lignes de la v0.59.0 = le catalogue Fiches d'alors (sans la vue
    # d'ensemble, ajoutée elle aussi à la lecture, en tête : ordre 0).
    for i, t in enumerate(gd._CATALOGUE_SIXIEME, start=1):
        _ins(c, "referentiel_documents", id=f"rd_{i}", referentiel_id="2027_N11",
             type_document=t.cle, options='{"actif": true}', ordre=i)
    c.commit()
    docs = lister_documents(c, "2027_N11")
    assert [d["type_document"] for d in docs][-2:] == list(CARTES)
    assert [d["ordre"] for d in docs][-2:] == [10, 11]
    assert all(d["options"]["actif"] is False for d in docs[-2:])
    assert (docs[0]["type_document"], docs[0]["ordre"]) == ("vue_ensemble", 0)
    # Les lignes du modèle sont intactes (options gardées).
    assert all(d["options"]["actif"] is True for d in docs[1:-2])
    c.close()


def test_referentiel_fige_ou_du_cycle_4_garde_sa_liste(base4e):
    from services.referentiel_documents import lister_documents
    c = _conn(base4e)
    _ref(c, "2027_N11", etat="verrouille")
    _ref(c, "2026_N11", gabarit="cycle4", cartes=0, version="2026")
    for rid, cat in (("2027_N11", gd.catalogue("sixieme")),
                     ("2026_N11", gd.catalogue("cycle4")[:7])):
        for i, t in enumerate(cat, start=1):
            _ins(c, "referentiel_documents", id=f"rd_{rid}_{i}", referentiel_id=rid,
                 type_document=t.cle, options="{}", ordre=i)
    c.commit()
    assert not any(d["type_document"] in CARTES for d in lister_documents(c, "2027_N11"))
    assert len(lister_documents(c, "2026_N11")) == 7
    c.close()


# ── C3 Cibles, cartes, générateurs ───────────────────────────────────────────

def _cibles(c, rid, type_doc):
    from services.referentiel_documents import initialiser_documents_defaut
    from services.referentiel_documents_compilation import lister_cibles_document
    initialiser_documents_defaut(c, rid)
    did = c.execute("SELECT id FROM referentiel_documents WHERE referentiel_id=? AND "
                    "type_document=?", (rid, type_doc)).fetchone()[0]
    return lister_cibles_document(c, did, rid, type_doc)


def test_cibles_fiches_par_sequence_et_recap_annuel_cartes_validees_rattachees(base4e_lot):
    """Comme au cycle 4 (planches par séquence, récap annuel) + un récap par
    séquence ; seules les séquences qui ont une carte VALIDÉE rattachée."""
    c = _conn(base4e_lot)
    _ref(c)
    assert _cibles(c, "2027_N11", "livret_cartes_planches") == []    # cartes « en cours »
    _valider_cartes(c)
    pl = _cibles(c, "2027_N11", "livret_cartes_planches")
    rc = _cibles(c, "2027_N11", "livret_cartes_recap")
    c.close()
    assert [x["cible_id"] for x in pl] == ["N11/A1"]
    assert [x["cible_id"] for x in rc] == ["unique", "N11/A1"]
    assert pl[0]["nom_fichier"] == "livret_cartes_planches__N11__A1.pdf"
    assert {x["perimetre"] for x in pl + rc} == {"objectifs"}


def test_cibles_du_cycle_4_inchangees_meme_niveau(base4e_lot):
    """Un référentiel « Notions et méthodes » de N11 garde la règle historique
    (cartes validées du niveau par `cartes_automatisme.sequence`) : ici
    l'archive X03 (carte de 2025 validée)."""
    c = _conn(base4e_lot)
    c.execute("UPDATE cartes_automatisme SET etat_code='valide'")
    c.commit()
    _ref(c, "2026_N11", gabarit="cycle4", cartes=0, version="2026")
    pl = _cibles(c, "2026_N11", "livret_cartes_planches")
    rc = _cibles(c, "2026_N11", "livret_cartes_recap")
    c.close()
    assert [x["cible_id"] for x in pl] == ["N11/A1", "N11/X03"]
    assert all("perimetre" not in x for x in pl)
    assert [x["cible_id"] for x in rc] == ["unique"] and "perimetre" not in rc[0]


def test_cartes_du_perimetre_rattachement_et_non_sequence_de_la_carte(base4e_lot):
    """Une carte de 5e rattachée par l'auteur à A1-03 entre dans les planches
    de A1 (avec SA couleur et son code) ; l'archive X03 et une carte sans
    objectif n'y entrent pas ; une carte non validée non plus."""
    c = _conn(base4e_lot)
    _valider_cartes(c)
    _ins(c, "cartes_automatisme", id="crt_n10", niveau="N10", sequence="A1", num=7,
         titre="carte de 5e", recto="r5", verso="v5", ordre=7, etat_code="valide")
    _ins(c, "cartes_automatisme", id="crt_libre", niveau="N11", sequence="A1", num=50,
         titre="sans objectif", recto="r", verso="v", ordre=50, etat_code="valide")
    oid = c.execute("SELECT o.id FROM objectifs o JOIN sequence_parties p ON p.id=o.partie_id "
                    "JOIN sequences_par_niveau sn ON sn.id=p.sequence_par_niveau_id WHERE "
                    "sn.niveau='N11' AND sn.sequence_code='A1' AND o.code='03'").fetchone()[0]
    _ins(c, "objectif_cartes", objectif_id=oid, carte_id="crt_n10", ordre=9)
    c.commit()
    cartes = fc4.cartes_du_perimetre(c, "N11", "A1")
    assert [(x["niveau"], x["num"], x["objectif"]) for x in cartes] == [
        ("N11", 1, "A1-02"), ("N11", 2, "A1-03"), ("N10", 7, "A1-03")]
    from services.livret_cartes_planches import generer_livret_cartes_planches
    tex = generer_livret_cartes_planches(c, "N11", sequence="A1", perimetre="objectifs")
    c.close()
    assert "%% Planche N10/A1/CA07" in tex and "CA50" not in tex
    assert "%% Planche N11/X03" not in tex


def test_planches_fiches_verso_en_miroir_et_couleur_du_theme(base4e_lot):
    from services.livret_cartes_planches import generer_livret_cartes_planches
    from services.render_carte_centralise import resoudre_code_couleur
    c = _conn(base4e_lot)
    _valider_cartes(c)
    c.execute("UPDATE cartes_automatisme SET type_tech='fixe', variables='', "
              "verso='\\seqLocV' WHERE niveau='N11' AND sequence='A1' AND num=1")
    c.commit()
    tex = generer_livret_cartes_planches(c, "N11", sequence="A1", perimetre="objectifs")
    couleur = resoudre_code_couleur(c, "N11", "A1")
    c.close()
    assert f"codecouleur={{{couleur}}}" in tex
    # Carte paramétrée (n° 2) : 16 tirages suffixés ; ligne 1 du verso = 4,3,2,1.
    bloc = tex.split("%% Planche N11/A1/CA02")[1]
    verso = bloc.split("\\seqCelluleVerso")[1:5]
    rangs = [v.split("_")[1][:2] for v in verso if "_" in v]
    assert rangs and rangs == sorted(rangs, reverse=True), verso


def test_recap_fiches_par_sequence_et_annuel(base4e_lot):
    from services.livret_cartes_recap import generer_livret_cartes_recap
    c = _conn(base4e_lot)
    _valider_cartes(c)
    seq = generer_livret_cartes_recap(c, "N11", sequence="A1", perimetre="objectifs")
    an = generer_livret_cartes_recap(c, "N11", perimetre="objectifs")
    c.close()
    assert "Séquence A1" in seq and "2 cartes au total" in seq
    assert "2 cartes au total" in an and "Séquence A1" not in an
    assert "X03" not in seq + an


def test_generateurs_sans_perimetre_rendent_le_meme_tex(base4e_lot):
    """Cycle 4 et référentiels figés : même .tex qu'avant (appel historique)."""
    from services import livret_cartes_planches as lp
    from services import livret_cartes_recap as lr
    from services import orchestrateur_compilation as orch
    c = _conn(base4e_lot)
    c.execute("UPDATE cartes_automatisme SET etat_code='valide'")
    c.commit()
    assert lr.generer_livret_cartes_recap(c, "N11") == \
        orch.REGISTRE["livret_cartes_recap"](c, {"niveau": "N11"}, {}, [], [])
    assert lp.generer_livret_cartes_planches(c, "N11", sequence="X03") == \
        orch.REGISTRE["livret_cartes_planches"](c, {"niveau": "N11", "sequence": "X03"},
                                                {}, [], [])
    # Règle historique : toutes les cartes validées du niveau, archive comprise.
    assert "=X03" in lr.generer_livret_cartes_recap(c, "N11")
    c.close()


# ── C4 Tout compiler ─────────────────────────────────────────────────────────

def test_tout_compiler_fiches_avec_option_compile_recap_et_planches(base4e_lot):
    from services import sequence_tout_compiler as stc
    c = _conn(base4e_lot)
    _valider_cartes(c)
    sans = stc.documents_a_compiler(c, "N11", "A1", "sixieme")
    _ref(c)
    avec = stc.documents_a_compiler(c, "N11", "A1", "sixieme")
    c.close()
    assert not any(d["type_document"] in CARTES for d in sans)
    assert avec[:len(sans)] == sans
    cartes = avec[len(sans):]
    assert [d["nom"] for d in cartes] == ["N11_A1_cartes_recap.pdf",
                                          "N11_A1_cartes_planches.pdf"]
    assert all(d["cible"]["perimetre"] == "objectifs" for d in cartes)


def test_tout_compiler_table_avec_cartes_couvre_le_catalogue_avec_option():
    """Même garde que D-LISTE (v0.54.2) : tout type du catalogue Fiches avec
    l'option est dans la table ou exclu avec sa raison."""
    from services import sequence_tout_compiler as stc
    cat = {t.cle for t in gd.catalogue_type("sixieme", "principal", True)}
    table = {d.type_document for d in stc.table("sixieme", True)}
    assert table | set(stc.EXCLUS_FICHES) == cat
    assert stc.table("sixieme") == stc.DOCUMENTS_SEQUENCE_FICHES
    assert stc.table("cycle4", True) == stc.DOCUMENTS_SEQUENCE_NOTIONS


# ── C5 Import : alignement des rattachements ─────────────────────────────────

def _deplacer_carte_1_sous_a1_03(lots: Path):
    p = lots / "A1" / "A1.json"
    lot = json.loads(p.read_text(encoding="utf-8"))
    c1 = lot["objectifs"][0]["cartes_automatisme"].pop(0)
    lot["objectifs"][1]["cartes_automatisme"].insert(0, c1)
    p.write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")


def _liens_a1(db):
    return _q(db, "SELECT o.code, c.num FROM objectif_cartes oc JOIN objectifs o ON "
                  "o.id=oc.objectif_id JOIN cartes_automatisme c ON c.id=oc.carte_id JOIN "
                  "sequence_parties p ON p.id=o.partie_id JOIN sequences_par_niveau sn ON "
                  "sn.id=p.sequence_par_niveau_id WHERE sn.niveau='N11' AND "
                  "sn.sequence_code='A1' ORDER BY o.code, oc.ordre")


def test_reimport_retire_le_lien_vers_l_ancien_objectif_de_la_sequence(base4e, tmp_path,
                                                                       capsys):
    """Cas réel (D1-02 → D1-05) rejoué sur A1 : la carte 1 passe de A1-02 à
    A1-03 dans le lot ; sans alignement elle restait aussi sous A1-02."""
    lots = _lots(tmp_path)
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, lots, "--apply", "--yes") == 0
    assert _liens_a1(base4e) == [("02", 1), ("03", 2)]
    _deplacer_carte_1_sous_a1_03(lots)
    avant = base4e.read_bytes()
    capsys.readouterr()
    assert _importer(base4e, lots) == 0                                  # essai à blanc
    out = capsys.readouterr().out
    assert base4e.read_bytes() == avant
    assert "1 lien(s) retiré(s)" in out
    assert "N11/A1/CA1 « Signe d'un produit de relatifs » : lien vers A1-02 retiré" in out
    assert _importer(base4e, lots, "--apply", "--yes") == 0
    assert _liens_a1(base4e) == [("03", 1), ("03", 2)]
    j = sorted((base4e.parent / "sauvegardes").glob("journal_import_lot6e_*.json"))[-1]
    retraits = json.loads(j.read_text(encoding="utf-8"))["retraits"]
    assert [r["objectif"] for r in retraits if r["quoi"] == "lien_objectif_carte"] == ["A1-02"]
    capsys.readouterr()
    assert _importer(base4e, lots) == 0                                  # second passage nul
    assert "0 lien(s) retiré(s)" in capsys.readouterr().out


def test_alignement_jamais_sur_une_carte_validee_ni_sur_les_liens_de_l_auteur(base4e,
                                                                             tmp_path):
    lots = _lots(tmp_path)
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, lots, "--apply", "--yes") == 0
    c = _conn(base4e)
    # Lien de l'auteur : carte que le lot ne cite pas, sous A1-02 → reste.
    _ins(c, "cartes_automatisme", id="crt_auteur", niveau="N11", sequence="A1", num=40,
         titre="carte de l'auteur", recto="r", verso="v", ordre=40)
    oid02 = c.execute("SELECT oc.objectif_id FROM objectif_cartes oc JOIN cartes_automatisme "
                      "ca ON ca.id=oc.carte_id WHERE ca.niveau='N11' AND ca.sequence='A1' "
                      "AND ca.num=1").fetchone()[0]
    _ins(c, "objectif_cartes", objectif_id=oid02, carte_id="crt_auteur", ordre=5)
    # Carte 2 citée sous A1-03 aussi liée à A1-02 mais VALIDÉE → lien gardé.
    cid2 = c.execute("SELECT id FROM cartes_automatisme WHERE niveau='N11' AND "
                     "sequence='A1' AND num=2").fetchone()[0]
    _ins(c, "objectif_cartes", objectif_id=oid02, carte_id=cid2, ordre=6)
    c.execute("UPDATE cartes_automatisme SET etat_code='valide' WHERE id=?", (cid2,))
    c.commit()
    r = imp.Rapport()
    ref = json.loads((APPLI / "outils" / "objectifs_4e.json").read_text(encoding="utf-8"))
    imp.executer(c, imp.charger_lots(lots), ref, r, base4e.parent / "images",
                 ecrire_fichiers=False, niveau="N11")
    liens = c.execute("SELECT ca.num FROM objectif_cartes oc JOIN cartes_automatisme ca ON "
                      "ca.id=oc.carte_id WHERE oc.objectif_id=? ORDER BY ca.num",
                      (oid02,)).fetchall()
    c.rollback()
    c.close()
    assert [x[0] for x in liens] == [1, 2, 40]
    assert any("CA2" in a and "carte validée : lien gardé" in a for a in r.anomalies)
    assert r.cartes_alignement == []


# ── C6 Titre de carte échappé ────────────────────────────────────────────────

def _carte(titre):
    return {"niveau": "N11", "sequence": "D2", "num": 3, "type_pedago": "calcul",
            "type_tech": "fixe", "titre": titre, "recto": "Calcule 20\\,\\% de 120.",
            "verso": "24", "variables": ""}


def test_titre_de_carte_echappe_dans_l_apercu_isole(base4e):
    from services.render_carte_centralise import rendre_carte_isole
    c = _conn(base4e)
    corps = rendre_carte_isole(c, _carte("Compléter 20 % de 120 & co #1 x_1"))["corps"]
    simple = rendre_carte_isole(c, _carte("Produit de décimaux"))["corps"]
    maths = rendre_carte_isole(c, _carte("Indice $x_1$"))["corps"]
    uni = rendre_carte_isole(c, _carte("Conversion litres ↔ dm³"))["corps"]
    c.close()
    assert "nom={Compléter 20 \\% de 120 \\& co \\#1 x\\_1}" in corps
    assert "nom={Produit de décimaux}" in simple                      # inchangé
    assert "nom={Indice $x_1$}" in maths                              # formule gardée
    # La clé `nom` n'est pas composée par le paquet : pas de conversion Unicode,
    # le .tex des cartes de 5e (« ↔ », « ⊥ ») reste identique.
    assert "nom={Conversion litres ↔ dm³}" in uni


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex absent")
def test_carte_au_titre_avec_pourcent_compile(base4e, tmp_path):
    """Avant v0.59.1 le « % » commentait la fin des options de
    \\seqCarteAutomatisme : la carte ne compilait pas."""
    from services.render_carte import _construire_preambule_carte
    from services.render_carte_centralise import rendre_carte_isole
    c = _conn(base4e)
    corps = rendre_carte_isole(c, _carte("Compléter 20 % de 120"))["corps"]
    c.close()
    tex = (_construire_preambule_carte() + "\n\\begin{document}\n\\seqInitCartes\n" + corps
           + "\\end{document}\n")
    (tmp_path / "t.tex").write_text(tex, encoding="utf-8")
    env = dict(os.environ, TEXINPUTS=f".:{APPLI / 'paquet'}//:")
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "t.tex"],
                       cwd=tmp_path, capture_output=True, env=env, timeout=300)
    log = (tmp_path / "t.log").read_text(encoding="latin-1")
    assert r.returncode == 0 and "\n! " not in log, log[-2000:]
