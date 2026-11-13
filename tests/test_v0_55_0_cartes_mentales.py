"""tests/test_v0_55_0_cartes_mentales.py — v0.55.0

Cartes mentales de partie (Laurent, 12 novembre 2026 ; doc/redemarrage_v0_55_0.md,
SP/lot6e/FORMAT_CARTE_MENTALE.md) :

1. module seqenseigne-style6e v0.13 : environnement et branche, palette, liste de l'appli ;
2. CM-TABLE — table `cartes_mentales` (migration idempotente, une carte par partie,
   classée côté atelier) ;
3. CM-CONTROLE — source acceptée ou refusée ;
4. CM-LIVRET — fin de partie, nouvelle page, élève / corrigé ; sans carte : même .tex ;
5. document « Cartes mentales », catalogue, « Tout compiler », péremption ;
6. CM-VALID — partie sans carte : avertissement, jamais de blocage ;
7. format d'échange 1.5 — empreinte inchangée sans carte ;
8. import des lots (clé `cartes_mentales`) : idempotent, jamais sur validé, contrôles ;
9. routes de l'atelier (liste, enregistrement, séquence validée en lecture seule).
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import cartes_mentales as cm  # noqa: E402
from services import gabarits_documents as gd  # noqa: E402
from services import style6e  # noqa: E402
from tests.test_v0_52_2_documents_6e import app_6e  # noqa: E402,F401

PAQUET = Path(__file__).parent.parent / "paquet"
TBLR = ["booktabs", "varwidth"]

CARTE = r"""\begin{seqCarteMentaleSix}[Partie 1]{Les nombres entiers}
  \seqCMBranche{Les chiffres}{Il y a \seqACompleter{10} chiffres.}
  \seqCMBranche{Les classes}{unités, \seqACompleter{milliers}, millions}
  \seqCMBranche{Écrire}{On sépare les classes par un \seqACompleter{espace}.}
  \seqCMBranche{Valeur}{$3\,000 = 3 \times \seqACompleter{1\,000}$}
\end{seqCarteMentaleSix}"""


def _carte(n: int = 4) -> str:
    branches = "\n".join(rf"\seqCMBranche{{B{i}}}{{\seqACompleter{{x{i}}}}}" for i in range(n))
    return r"\begin{seqCarteMentaleSix}{T}" + branches + r"\end{seqCarteMentaleSix}"


# ── 1. Module LaTeX v0.13 ───────────────────────────────────────────────────

def test_module_v0_13_definit_la_carte_et_la_liste_de_l_appli_la_connait():
    """Sans la macro dans MACROS, l'analyse des paquets ne chargerait pas le module pour une
    carte seule et l'import refuserait les cartes des lots (« macro inconnue »)."""
    assert style6e.VERSION == "v0.13"
    assert "seqCMBranche" in style6e.MACROS and "seqCarteMentaleSix" in style6e.ENVIRONNEMENTS
    for f in ("seqenseigne-style6e.dtx", "seqenseigne-style6e.sty"):
        src = (PAQUET / f).read_text(encoding="utf-8")
        assert "v0.13 seqenseigne" in src
        assert "\\NewDocumentEnvironment{seqCarteMentaleSix}" in src
        assert "\\NewDocumentCommand{\\seqCMBranche}" in src
        assert all(f"\\definecolor{{seqSixCM{i}}}" in src for i in range(1, 9))


def test_disposition_anti_horaire_cinq_millimetres_et_reduction_a_une_page_dans_le_code():
    """Format commun : colonne de gauche 1…⌈n/2⌉ de haut en bas, puis la droite de bas en haut
    (n…k+1 de haut en bas) ; 5 mm au moins entre deux branches ; jamais agrandie, réduite à la
    largeur de ligne et à la hauteur disponible (une page A4 au plus)."""
    sty = (PAQUET / "seqenseigne-style6e.sty").read_text(encoding="utf-8")
    assert "\\dim_const:Nn \\c__seqsix_cm_ecart_dim { 5mm }" in sty
    assert "\\int_div_truncate:nn { \\l__seqsix_cm_nb_int + 1 } { 2 }" in sty
    assert "\\int_step_function:nnnN { \\l__seqsix_cm_nb_int } { -1 }" in sty
    assert "min ( 1 ," in sty and "\\l__seqsix_cm_dispo_dim" in sty


def test_branche_composee_dans_une_boite_avant_le_dessin_pour_accepter_tikz_sans_imbrication():
    """Une figure tkz-euclide dans une branche ne doit pas être un tikzpicture imbriqué dans
    le nœud : chaque branche est mise en boîte d'abord, le dessin n'utilise que la boîte."""
    sty = (PAQUET / "seqenseigne-style6e.sty").read_text(encoding="utf-8")
    debut = sty.index("\\NewDocumentCommand{\\seqCMBranche}")
    code = sty[debut:sty.index("\\NewDocumentEnvironment{seqCarteMentaleSix}")]
    assert "\\vbox_set:cn" in code and "tikzpicture" not in code


def test_bulle_elargie_au_mot_le_plus_long_du_titre_sans_coupure():
    """Retour des lots S09–S13 : « Proportionnalité » ne tenait pas dans 2,9 cm et devait être
    coupé à la main. Le texte de la bulle prend la largeur du mot le plus long, sans césure,
    et la gouttière (4 cm au moins) s'élargit d'autant."""
    sty = (PAQUET / "seqenseigne-style6e.sty").read_text(encoding="utf-8")
    assert "\\seq_set_split:NnV \\l__seqsix_cm_mots_seq" in sty
    assert "\\hyphenpenalty = 10000" in sty
    assert "\\c__seqsix_cm_goutiere_dim" in sty and "text~width=\\l__seqsix_cm_bulle_dim" in sty


# ── 2. CM-TABLE ─────────────────────────────────────────────────────────────

def test_migration_idempotente_et_table_classee_cote_atelier(app_6e):
    from services import repartition
    with app_6e.json_store._conn() as c:
        assert cm.table_presente(c)                 # créée au démarrage
        assert cm.migrer(c) is False and cm.migrer(c) is False
        cols = {r[1] for r in c.execute("PRAGMA table_info(cartes_mentales)")}
    assert {"id", "partie_id", "niveau", "sequence", "titre", "latex", "etat_code",
            "mtime"} <= cols
    assert "cartes_mentales" in repartition.TABLES_ATELIER


def test_une_seule_carte_par_partie_et_suppression_avec_la_partie(app_6e):
    with app_6e.json_store._conn() as c:
        cid, etat = cm.enregistrer(c, "p61", "Nombres", CARTE)
        assert etat == "créée"
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO cartes_mentales (id, partie_id) VALUES ('cm_x', 'p61')")
        c.execute("INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
                  "VALUES ('p62', 'sn6', 2)")
        cm.enregistrer(c, "p62", "Partie vide", CARTE)
        c.execute("DELETE FROM sequence_parties WHERE id = 'p62'")
        assert [r[0] for r in c.execute("SELECT partie_id FROM cartes_mentales")] == ["p61"]


def test_enregistrer_idempotent_et_carte_validee_jamais_modifiee_sans_le_demander(app_6e):
    """L'import ne doit jamais écraser une carte validée dans l'atelier ; l'atelier la
    modifie en la repassant en cours (ou explicitement, forcer_valide)."""
    with app_6e.json_store._conn() as c:
        cid, _ = cm.enregistrer(c, "p61", "Nombres", CARTE)
        assert cm.enregistrer(c, "p61", "Nombres", CARTE) == (cid, "inchangée")
        assert cm.enregistrer(c, "p61", "Nombres", CARTE, "valide")[1] == "mise à jour"
        assert cm.enregistrer(c, "p61", "Autre", CARTE)[1] == "validée, non modifiée"
        assert cm.lire_partie(c, "p61")["titre"] == "Nombres"
        assert cm.enregistrer(c, "p61", "Autre", CARTE, "en_cours")[1] == "mise à jour"
        r = cm.lire_partie(c, "p61")
    assert (r["titre"], r["etat_code"], r["niveau"], r["sequence"]) == \
        ("Autre", "en_cours", "N09", "S01")
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", r["mtime"])


# ── 3. CM-CONTROLE ──────────────────────────────────────────────────────────

def test_controle_refuse_une_source_qui_ferait_echouer_le_livret():
    assert cm.controler_latex(CARTE) == ([], [])
    err, _ = cm.controler_latex(CARTE.replace(r"\end{seqCarteMentaleSix}", ""))
    assert err and "environnement" in err[0]
    err, _ = cm.controler_latex(r"\begin{seqCarteMentaleSix}{T}\end{seqCarteMentaleSix}")
    assert any("aucune branche" in e for e in err)
    err, _ = cm.controler_latex(CARTE.replace("Les chiffres}{", r"Les chiffres}{\seqLocInconnue "))
    assert any("seqLocInconnue" in e for e in err)
    assert cm.controler_latex(_carte(17))[0]


def test_hors_quatre_a_huit_branches_simple_avertissement():
    assert cm.controler_latex(_carte(3)) == ([], ["3 branches (4 à 8 conseillées)"])
    assert cm.controler_latex(_carte(9))[1] and not cm.controler_latex(_carte(9))[0]
    assert cm.controler_latex(_carte(8)) == ([], [])


# ── 4. CM-LIVRET ────────────────────────────────────────────────────────────

def test_sans_carte_le_livret_produit_exactement_le_meme_tex(app_6e):
    """Une séquence sans carte ne change pas (même .tex) : la table vide ou absente ne
    modifie rien."""
    from services.livret_sequence_6e import generer_livret_sequence_6e
    with app_6e.json_store._conn() as c:
        avec_table = generer_livret_sequence_6e(c, "N09", "S01", {"version": "eleve"},
                                                tblr_libraries=TBLR)
        c.execute("DROP TABLE cartes_mentales")
        sans_table = generer_livret_sequence_6e(c, "N09", "S01", {"version": "eleve"},
                                                tblr_libraries=TBLR)
    assert avec_table == sans_table and "seqCarteMentaleSix" not in avec_table


def test_carte_en_fin_de_partie_apres_les_exercices_sur_une_nouvelle_page(app_6e):
    from services.livret_sequence_6e import generer_livret_sequence_6e
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
                  "VALUES ('p62', 'sn6', 2)")
        cm.enregistrer(c, "p61", "Nombres", CARTE)
        eleve = generer_livret_sequence_6e(c, "N09", "S01", {"version": "eleve"},
                                           tblr_libraries=TBLR)
        corr = generer_livret_sequence_6e(c, "N09", "S01", {"version": "corrigee"},
                                          tblr_libraries=TBLR)
    i_carte = eleve.index(r"\begin{seqCarteMentaleSix}")
    assert eleve.rindex(r"\end{seqExoSix}", 0, i_carte) > 0          # après les exercices
    assert eleve.index("Partie 2}") > i_carte                         # avant la partie suivante
    avant = eleve[:i_carte].rstrip().splitlines()
    assert avant[-2] == r"\clearpage" and "Carte mentale --- Partie 1" in avant[-1]
    assert eleve.count("seqCarteMentaleSix") == 2 == corr.count("seqCarteMentaleSix")
    assert r"\seqVersionCorrigee" in corr and r"\seqVersionCorrigee" not in eleve


# ── 5. Document « Cartes mentales », catalogue, Tout compiler ───────────────

def test_document_cartes_mentales_eleve_a_completer_et_complet(app_6e):
    with app_6e.json_store._conn() as c:
        with pytest.raises(ValueError):
            cm.generer_cartes_mentales_6e(c, "N09", "S01")          # aucune carte
        cm.enregistrer(c, "p61", "Nombres", CARTE)
        el = cm.generer_cartes_mentales_6e(c, "N09", "S01", {"version": "eleve"},
                                           tblr_libraries=TBLR)
        co = cm.generer_cartes_mentales_6e(c, "N09", "S01", {"version": "corrigee"},
                                           tblr_libraries=TBLR)
        with pytest.raises(ValueError):
            cm.generer_cartes_mentales_6e(c, "N09", "S01", {"partie": 2})
    assert r"\seqVersionACompleter" in el and r"\seqVersionComplete" in co
    assert "usepackage{seqenseigne-style6e}" in el
    debut = el.index(r"\begin{document}")
    assert r"\clearpage" not in el[debut:el.index(r"\begin{seqCarteMentaleSix}")]


def test_document_annuel_en_tete_de_chaque_sequence_apres_son_saut_de_page(app_6e):
    """Sinon la dernière carte d'une séquence porterait le nom de la séquence suivante."""
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id) "
                  "VALUES ('sc6_s02', 'C03', 'S02', 2, 'Comparaison', 'th_6A')")
        c.execute("INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres) "
                  "VALUES ('sn62', 'N09', 'S02', '')")
        c.execute("INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
                  "VALUES ('p621', 'sn62', 1)")
        cm.enregistrer(c, "p61", "Nombres", CARTE)
        cm.enregistrer(c, "p621", "Comparer", CARTE)
        tex = cm.generer_cartes_mentales_6e(c, "N09", None, tblr_libraries=TBLR)
    corps = tex[tex.index(r"\begin{document}"):].splitlines()
    i = next(k for k, l in enumerate(corps) if "Comparaison -- page" in l)
    assert corps[i - 1] == r"\clearpage" and corps.count(r"\clearpage") == 1


def test_catalogue_producteur_peremption_et_tout_compiler_seulement_avec_des_cartes(app_6e):
    from services import orchestrateur_compilation as orch
    from services import peremption_atomes as pa
    from services import sequence_tout_compiler as stc
    assert "cartes_mentales_6e" in gd.types("sixieme")
    assert "cartes_mentales_6e" not in gd.types("cycle4")
    assert "cartes_mentales_6e" in orch.REGISTRE
    assert "cartes_mentales" in pa.tables_atomes_pertinentes("livret_sequence_6e")
    assert pa.tables_atomes_pertinentes("cartes_mentales_6e") == ["cartes_mentales"]
    with app_6e.json_store._conn() as c:
        noms = [d["nom"] for d in stc.documents_a_compiler(c, "N09", "S01", "sixieme")]
        assert not any("cartes_mentales" in n for n in noms)
        cm.enregistrer(c, "p61", "Nombres", CARTE)
        noms = [d["nom"] for d in stc.documents_a_compiler(c, "N09", "S01", "sixieme")]
    assert {"S01_cartes_mentales_eleve.pdf", "S01_cartes_mentales_complete.pdf"} <= set(noms)


def test_cibles_du_document_publie_par_sequence_ayant_des_cartes(app_6e):
    from services.referentiel_documents_compilation import lister_cibles_document
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document, "
                  "options, ordre) VALUES ('rdcm', 'R09', 'cartes_mentales_6e', '{}', 1)")
        assert lister_cibles_document(c, "rdcm", "R09", "cartes_mentales_6e") == []
        cm.enregistrer(c, "p61", "Nombres", CARTE)
        cibles = lister_cibles_document(c, "rdcm", "R09", "cartes_mentales_6e")
    assert [x["cible_id"] for x in cibles] == ["N09/S01"]


# ── 6. CM-VALID ─────────────────────────────────────────────────────────────

def test_partie_sans_carte_avertit_sans_bloquer_la_validation(app_6e):
    from services import v2_edition as ve
    with app_6e.json_store._conn() as c:
        assert ve.avertissements_validation(c, "sn6") == ["La partie 1 n'a pas de carte mentale."]
        cm.enregistrer(c, "p61", "Nombres", CARTE)
        assert ve.avertissements_validation(c, "sn6") == []


# ── 7. Format d'échange ─────────────────────────────────────────────────────

def test_format_1_5_seulement_avec_une_carte_et_empreinte_inchangee_sans(app_6e):
    from services import format_referentiel as fr
    from services import referentiels_internes as ri
    with app_6e.json_store._conn() as c:
        ri.ecrire_instantane(c, "R09")
        avant = fr.construire(c, "R09", None)
        c.execute("DROP TABLE cartes_mentales")
        sans_table = fr.construire(c, "R09", None)
        cm.migrer(c)
        cm.enregistrer(c, "p61", "Les nombres", CARTE)
        apres = fr.construire(c, "R09", None)
    assert avant["empreinte"] == sans_table["empreinte"]
    assert avant["format_version"] == fr.FORMAT_VERSION_FICHES
    assert apres["format_version"] == fr.FORMAT_VERSION == "1.5"
    partie = apres["sequences"][0]["parties"][0]
    assert partie["carte_mentale"]["titre"] == "Les nombres"
    assert fr.valider(apres) == []


# ── 8. Import des lots ──────────────────────────────────────────────────────

def _rapport():
    from outils.import_lot6e import Rapport
    return Rapport()


def test_import_controle_partie_et_macros_et_reste_idempotent(app_6e):
    from outils.import_lot6e import importer_cartes_mentales
    lot = {"sequence": "S01", "_dossier": Path("."), "cartes_mentales": [
        {"partie": 1, "titre": "Nombres", "latex": CARTE},
        {"partie": 7, "titre": "?", "latex": CARTE},
        {"partie": 1, "titre": "doublon", "latex": CARTE}]}
    with app_6e.json_store._conn() as c:
        r = _rapport()
        importer_cartes_mentales(c, lot, {1: "p61"}, r)
        assert any("partie 7 : partie absente" in a for a in r.anomalies)
        assert any("en double" in a for a in r.anomalies)
        assert r.cartes_mentales["S01"] == {"créée": 1}
        r2 = _rapport()
        importer_cartes_mentales(c, lot, {1: "p61"}, r2)
        assert r2.cartes_mentales["S01"] == {"inchangée": 1}
        c.execute("UPDATE cartes_mentales SET etat_code = 'valide'")
        lot["cartes_mentales"][0]["titre"] = "Nouveau"
        r3 = _rapport()
        importer_cartes_mentales(c, lot, {1: "p61"}, r3)
        assert r3.cartes_mentales["S01"] == {"validée, non modifiée": 1}
        assert any("validée dans l'atelier" in a for a in r3.anomalies)
        assert cm.lire_partie(c, "p61")["titre"] == "Nombres"


def test_import_refuse_une_carte_aux_macros_inconnues_et_signale_les_parties_sans_carte(app_6e):
    from outils.import_lot6e import importer_cartes_mentales
    mauvaise = CARTE.replace("Les chiffres}{", r"Les chiffres}{\seqLocAbsente ")
    with app_6e.json_store._conn() as c:
        r = _rapport()
        importer_cartes_mentales(c, {"sequence": "S01", "cartes_mentales": [
            {"partie": 1, "titre": "x", "latex": mauvaise}]}, {1: "p61", 2: "p62"}, r)
        assert cm.lire_partie(c, "p61") is None
    assert any("non importée" in a and "seqLocAbsente" in a for a in r.anomalies)
    assert any("sans carte mentale dans le lot : 2" in i for i in r.infos)


def test_resume_de_l_essai_a_blanc_signale_les_fiches_mises_a_jour_et_validees():
    """Brief §7 : l'import met déjà à jour les fiches non validées ; l'essai à blanc le dit,
    et signale les fiches validées non mises à jour."""
    r = _rapport()
    o = r.obj("S01", "S01-02", "x")
    r.compter(o, "fiche", "mise à jour")
    r.compter(r.obj("S01", "S01-03", "y"), "fiche", "validée, non modifiée")
    r.fiches_cours["inchangée"] = 2
    texte = "\n".join(r.texte_resume())
    assert "fiches de résumé (lots S) : mise à jour 1, validée, non modifiée 1" in texte
    assert "fiches de cours de partie (lots M) : inchangée 2" in texte
    assert "ATTENTION" in texte


# ── 9. Routes de l'atelier ──────────────────────────────────────────────────

def test_routes_liste_enregistrement_et_sequence_validee_en_lecture_seule(app_6e):
    cl = app_6e.test_client()
    url = "/api/v2/livret-sequence/N09/S01/cartes-mentales"
    rep = cl.get(url).get_json()
    assert rep["modifiable"] and rep["parties"][0]["carte"] is None
    assert cl.put(url + "/1", json={"titre": "N", "latex": "pas une carte"}).status_code == 400
    r = cl.put(url + "/1", json={"titre": "N", "latex": _carte(3)})
    assert r.status_code == 200 and r.get_json()["etat"] == "créée"
    assert r.get_json()["avertissements"]
    assert cl.get(url).get_json()["parties"][0]["carte"]["titre"] == "N"
    assert cl.put(url + "/9", json={"titre": "N", "latex": CARTE}).status_code == 404
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE sequences_par_niveau SET etat_code = 'valide' WHERE id = 'sn6'")
    assert cl.put(url + "/1", json={"titre": "M", "latex": CARTE}).status_code == 409
    assert cl.get(url).get_json()["modifiable"] is False


def test_rendu_tex_de_la_carte_par_la_route_du_livret(app_6e):
    cl = app_6e.test_client()
    cl.put("/api/v2/livret-sequence/N09/S01/cartes-mentales/1", json={"titre": "N", "latex": CARTE})
    r = cl.get("/api/v2/livret-sequence/N09/S01/rendu-tex?document=cartes_mentales"
               "&version=corrigee&partie=1")
    assert r.status_code == 200
    tex = r.get_data(as_text=True)
    assert r"\seqVersionComplete" in tex and "Carte mentale --- Partie 1" in tex
    livret = cl.get("/api/v2/livret-sequence/N09/S01/rendu-tex").get_data(as_text=True)
    assert r"\seqCouvertureLivretSix" in livret


# ── 10. v0.55.0 révisée : modèle Notions et méthodes, taille, atelier ───────

from tests.test_v0_52_1_gabarits_documents import app_c4  # noqa: E402,F401


def test_cycle4_sans_carte_le_livret_produit_exactement_le_meme_tex(app_c4):
    from services.livret_sequence import generer_livret_sequence
    with app_c4.json_store._conn() as c:
        avec_table = generer_livret_sequence(c, "N11", "S01", None, tblr_libraries=TBLR)
        c.execute("DROP TABLE cartes_mentales")
        sans_table = generer_livret_sequence(c, "N11", "S01", None, tblr_libraries=TBLR)
    assert avec_table == sans_table and "seqCarteMentaleSix" not in avec_table


def test_cycle4_carte_apres_le_cours_avant_les_exercices_et_complete_apres_les_corriges(app_c4):
    """Décision de Laurent (12 novembre) : au modèle Notions et méthodes, la carte est la
    synthèse du cours : après les notions et méthodes, avant les exercices, sur une nouvelle
    page, à compléter ; la version complète suit les corrigés."""
    from services.livret_sequence import generer_livret_sequence
    with app_c4.json_store._conn() as c:
        cm.enregistrer(c, "pt_p1", "Synthèse", CARTE)
        tex = generer_livret_sequence(c, "N11", "S01", None, tblr_libraries=TBLR)
        cours_seul = generer_livret_sequence(c, "N11", "S01", {"contenu": "cours_seul"},
                                             tblr_libraries=TBLR)
        exos_seuls = generer_livret_sequence(c, "N11", "S01", {"cours": {"inclure": False}},
                                             tblr_libraries=TBLR)
    debut = tex.index(r"\begin{document}")
    i1 = tex.index(r"\begin{seqCarteMentaleSix}", debut)
    assert tex.rindex(r"\seqTitreSection{Savoir-faire}", 0, i1) > 0
    assert tex.index(r"\begin{seqSerieExos}{1}", debut) > i1
    assert tex.rindex(r"\seqVersionACompleter", 0, i1) > tex.rindex(r"\seqTitreSection", 0, i1)
    i2 = tex.index(r"\begin{seqCarteMentaleSix}", i1 + 10)
    assert tex.rindex(r"\seqAfficheCorriges", 0, i2) > i1
    assert tex.rindex(r"\seqVersionComplete", 0, i2) > tex.rindex(r"\seqAfficheCorriges", 0, i2)
    assert "usepackage{seqenseigne-style6e}" in tex
    assert "seqCarteMentaleSix" in cours_seul and "seqCarteMentaleSix" not in exos_seuls


def test_cycle4_document_cartes_mentales_par_la_route(app_c4):
    cl = app_c4.test_client()
    r = cl.put("/api/v2/livret-sequence/N11/S01/cartes-mentales/1",
               json={"titre": "Synthèse", "latex": CARTE})
    assert r.status_code == 200
    tex = cl.get("/api/v2/livret-sequence/N11/S01/rendu-tex?document=cartes_mentales"
                 "&version=corrigee").get_data(as_text=True)
    assert r"\seqVersionComplete" in tex and "Carte mentale --- Partie 1" in tex


def test_carte_etiree_sur_la_hauteur_disponible_pour_remplir_la_page():
    """Retour des lots : réduite à la largeur, une carte n'occupait que le haut de la page ;
    elle est étirée à (hauteur disponible) / s, les branches se répartissent sur la page."""
    sty = (PAQUET / "seqenseigne-style6e.sty").read_text(encoding="utf-8")
    assert "\\l__seqsix_cm_dispo_dim - 1pt } / \\l_tmpb_fp" in sty
    assert "ecart_max" not in sty
