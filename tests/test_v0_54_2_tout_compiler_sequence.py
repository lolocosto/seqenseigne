"""tests/test_v0_54_2_tout_compiler_sequence.py — v0.54.2

« Tout compiler » pour toute séquence de l'atelier (Laurent, 26 octobre 2026,
doc/redemarrage_v0_54_2.md) :

1. D-LISTE — une table par modèle, rattachée au catalogue du modèle : tout
   type du catalogue est compilé ou exclu avec sa raison (un type ajouté plus
   tard ne peut pas être oublié) ;
2. noms de fichiers clairs ; une évaluation appartient à la séquence de la
   majorité de ses exercices ; les archives Xnn n'en font pas partie ;
3. même .tex que les boutons de l'onglet (livret, plan de travail) ;
4. un document en échec n'arrête pas les autres ; archive ZIP ; aucune
   écriture en base ; route SSE de l'atelier seulement ; les mises en route
   gardent leur route.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app  # noqa: E402
from services import gabarits_documents as gd  # noqa: E402
from services import orchestrateur_compilation as orch  # noqa: E402
from services import sequence_tout_compiler as stc  # noqa: E402
from services.compilateur_pdf import ErreurLatex, ResultatCompilation  # noqa: E402
from tests.test_v0_52_1_gabarits_documents import app_c4  # noqa: E402,F401
from tests.test_v0_52_2_documents_6e import app_6e  # noqa: E402,F401

TBLR = ["booktabs", "varwidth"]


def _docs(app, niveau, sequence):
    with app.json_store._conn() as c:
        g = gd.gabarit_atelier_du_niveau(c, niveau)
        return g, stc.documents_a_compiler(c, niveau, sequence, g)


def _faux_compilateur(echec=None):
    def compiler(tex):
        if echec and echec in tex:
            return ResultatCompilation(ok=False, erreurs=[ErreurLatex(ligne=1, message="Undefined control sequence.")],
                                       log_complet="LOG KO")
        return ResultatCompilation(ok=True, pdf_bytes=b"%PDF-1.4 " + tex[-30:].encode())
    return compiler


# ── 1. D-LISTE ──────────────────────────────────────────────────────────────

def test_chaque_type_du_catalogue_est_compile_ou_exclu_avec_sa_raison_pour_ne_rien_oublier():
    """Un document ajouté plus tard au catalogue d'un modèle doit être rangé
    dans la table (donc compilé par « Tout compiler ») ou exclu avec une
    raison : sinon ce test échoue."""
    for g in gd.GABARITS:
        lignes, exclus = stc.TABLES[g]
        dans_table = {l.type_document for l in lignes}
        assert dans_table.isdisjoint(exclus)
        assert dans_table | set(exclus) == set(gd.types(g)), g
        assert all(r.strip() for r in exclus.values())


def test_chaque_ligne_a_un_producteur_et_des_declinaisons_valides_pour_le_catalogue():
    for g in gd.GABARITS:
        for l in stc.table(g):
            assert l.cle_producteur in orch.REGISTRE or l.cle_producteur == "plan_sequence_cycle4"
            t = gd.type_document(l.type_document)
            for _suf, _lib, options in l.declinaisons:
                for k, v in options.items():          # options connues du type, valeurs permises
                    assert k in t.options
                    if k in t.valeurs:
                        assert v in t.valeurs[k]


def test_corriges_enseignant_exclus_car_identiques_au_livret_corrige_pour_une_sequence(app_6e):
    """Pour une séquence, « Corrigés enseignant » = le livret corrigé (seul le
    titre interne change) : le compiler deux fois n'apporterait rien."""
    from services.livret_sequence_6e import generer_corriges_6e, generer_livret_sequence_6e
    with app_6e.json_store._conn() as c:
        a = generer_corriges_6e(c, "N09", sequence="S01", tblr_libraries=TBLR)
        b = generer_livret_sequence_6e(c, "N09", "S01", {"version": "corrigee"}, tblr_libraries=TBLR)
    garder = lambda t: [x for x in t.splitlines() if "6e —" not in x]   # noqa: E731
    assert a != b and garder(a) == garder(b)
    assert "corriges_6e" in stc.EXCLUS_FICHES


# ── 2. Noms, rattachement à la séquence ─────────────────────────────────────

def test_modele_fiches_liste_livret_fiches_plan_evaluations_tp_ac_at_avec_noms_clairs(app_6e):
    g, docs = _docs(app_6e, "N09", "S01")
    assert g == "sixieme"
    assert [d["nom"] for d in docs] == [
        "S01_livret_eleve.pdf", "S01_livret_corrige.pdf", "S01_fiches_cours.pdf",
        "S01_plan_de_travail.pdf",
        "S01_eval1_A_eleve.pdf", "S01_eval1_A_corrige.pdf",
        "S01_eval1_B_eleve.pdf", "S01_eval1_B_corrige.pdf",
        "S01_TP01_eleve.pdf", "S01_TP01_corrige.pdf",
        "S01_AC02_eleve.pdf", "S01_AC02_corrige.pdf",
        "S01_AT01_eleve.pdf", "S01_AT01_corrige.pdf"]
    ev = next(d for d in docs if d["nom"] == "S01_eval1_B_corrige.pdf")
    assert ev["options"] == {"sujet": "B", "version": "corrigee"} and ev["cible"]["eval_id"] == "E6"
    assert "Évaluation 1 : Évaluation — Nombres — sujet B, corrigé" == ev["libelle"]
    assert all("X02" not in d["nom"] and "Archive" not in d["libelle"] for d in docs)


def test_prefixe_sequence_seule_en_6e_niveau_et_sequence_ailleurs():
    assert stc.prefixe("N09", "S03") == "S03"
    assert stc.prefixe("N11", "S04") == "N11_S04"


def test_modele_notions_et_methodes_liste_livret_notions_methodes_plan_fiches_cartes(app_c4):
    g, docs = _docs(app_c4, "N11", "S01")
    assert g == "cycle4"
    noms = [d["nom"] for d in docs]
    assert noms[:3] == ["N11_S01_livret.pdf", "N11_S01_notions_methodes.pdf",
                        "N11_S01_plan_de_travail.pdf"]
    assert all(n.startswith("N11_S01_") for n in noms)
    nm = docs[1]
    assert nm["producteur"] == "livret_sequence" and nm["options"] == {"contenu": "cours_seul"}


def test_une_evaluation_appartient_a_la_sequence_de_la_majorite_de_ses_exercices(app_6e):
    _, docs = _docs(app_6e, "N09", "S02")
    assert not [d for d in docs if "_eval" in d["nom"]]


# ── 3. Même .tex que les boutons de l'onglet ────────────────────────────────

def _tex_liste(app, niveau, sequence, nom):
    _, docs = _docs(app, niveau, sequence)
    d = next(x for x in docs if x["nom"] == nom)
    with app.json_store._conn() as c:
        return stc.generer_tex(c, d, [], TBLR)


def _tex_bouton(app, url, payload=None):
    r = app.test_client().post(url, json=payload) if payload is not None \
        else app.test_client().post(url)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    return r.get_data(as_text=True)


# Options que l'onglet envoie pour « Compiler le livret » (cases absentes : vrai).
OPTIONS_ONGLET = {"cours": {"inclure": True, "fiches_resume": {"inclure": True, "a_completer": True}},
                  "exercices": {"inclure": True, "serie_A": True}}


def _avec_tblr(app):
    """La configuration que lisent les routes (bibliothèques TikZ et tblr)."""
    from services.configuration import Configuration
    app.configuration = Configuration(app.json_store.data_dir)
    return app.configuration


def test_livret_et_plan_de_travail_6e_meme_tex_que_les_boutons_de_l_onglet(app_6e):
    cfg = _avec_tblr(app_6e)
    t, b = cfg.tikz_libraries(), cfg.tblr_libraries()
    for nom, url, payload in (
            ("S01_livret_eleve.pdf", "/api/v2/livret-sequence/N09/S01/rendu-tex",
             {"options": OPTIONS_ONGLET}),
            ("S01_plan_de_travail.pdf", "/api/plans-de-travail/N09/S01/tex", None)):
        _, docs = _docs(app_6e, "N09", "S01")
        d = next(x for x in docs if x["nom"] == nom)
        with app_6e.json_store._conn() as c:
            assert stc.generer_tex(c, d, t, b) == _tex_bouton(app_6e, url, payload), nom


def test_livret_et_plan_de_travail_du_cycle_4_meme_tex_que_les_boutons_de_l_onglet(app_c4, monkeypatch):
    """Livret : même .tex que « Compiler le livret ». Plan de travail : le même
    générateur, avec les mêmes arguments, que « Compiler le plan de travail »
    (les données de test n'ont pas le paquet complet qu'il lui faut)."""
    cfg = _avec_tblr(app_c4)
    t, b = cfg.tikz_libraries(), cfg.tblr_libraries()
    _, docs = _docs(app_c4, "N11", "S01")
    d = next(x for x in docs if x["nom"] == "N11_S01_livret.pdf")
    with app_c4.json_store._conn() as c:
        assert stc.generer_tex(c, d, t, b) == _tex_bouton(
            app_c4, "/api/v2/livret-sequence/N11/S01/rendu-tex", {"options": OPTIONS_ONGLET})
    import routes.plans_de_travail as rp
    import services.livret_plans_de_travail as lp
    faux = lambda conn, n, s, tikz_libraries=None, tblr_libraries=None: f"PLAN {n} {s} {tikz_libraries} {tblr_libraries}"  # noqa: E731,E501
    monkeypatch.setattr(rp, "generer_plan_de_travail_sequence", faux)
    monkeypatch.setattr(lp, "generer_plan_de_travail_sequence", faux)
    d = next(x for x in docs if x["nom"] == "N11_S01_plan_de_travail.pdf")
    with app_c4.json_store._conn() as c:
        assert stc.generer_tex(c, d, t, b) == _tex_bouton(
            app_c4, "/api/plans-de-travail/N11/S01/tex") == f"PLAN N11 S01 {t} {b}"


def test_notions_et_methodes_est_le_livret_sans_ses_exercices(app_c4):
    complet = _tex_liste(app_c4, "N11", "S01", "N11_S01_livret.pdf")
    cours = _tex_liste(app_c4, "N11", "S01", "N11_S01_notions_methodes.pdf")
    assert cours != complet and "seqSerieExos" in complet and "seqSerieExos" not in cours


# ── 4. Compilation en série ─────────────────────────────────────────────────

def _dump(app):
    with app.json_store._conn() as c:
        return list(c.iterdump())


def test_un_document_en_echec_n_arrete_pas_les_autres_et_le_rapport_le_dit(app_6e, tmp_path):
    avant = _dump(app_6e)
    evs = list(stc.iter_tout_compiler(
        app_6e.json_store._conn, "N09", "S01", "sixieme",
        compiler=_faux_compilateur(echec="Séance."), tblr_libraries=TBLR,
        dossier_echecs=tmp_path / "e", dossier_archives=tmp_path / "a"))
    assert evs[0]["kind"] == "debut" and evs[0]["total"] == 14
    docs = [e for e in evs if e["kind"] == "document"]
    echecs = [e["nom"] for e in docs if e["statut"] == "echec"]
    assert len(docs) == 14 and echecs == ["S01_AT01_eleve.pdf", "S01_AT01_corrige.pdf"]
    assert all("duree_ms" in e for e in docs)
    assert (tmp_path / "e" / "S01_AT01_eleve.log").read_text() == "LOG KO"
    fin = evs[-1]
    assert fin["kind"] == "fin" and fin["ok"] == 12 and fin["echecs"] == 2
    assert fin["archive"].startswith("S01_sequence_documents_")
    with zipfile.ZipFile(tmp_path / "a" / fin["archive"]) as z:
        assert len(z.namelist()) == 12 and "S01_eval1_B_corrige.pdf" in z.namelist()
    assert _dump(app_6e) == avant                      # aucune écriture en base


def test_route_sse_d_une_snn_puis_archive_et_mise_en_route_renvoyee_a_sa_route(app_6e, monkeypatch):
    import routes.livret_sequence as rl
    monkeypatch.setattr(rl, "compiler_atome", lambda tex_source, **kw: _faux_compilateur()(tex_source))
    c = app_6e.test_client()
    r = c.get("/api/v2/livret-sequence/N09/S01/tout-compiler")
    assert r.status_code == 200 and r.mimetype == "text/event-stream"
    evs = [json.loads(l[6:]) for l in r.get_data(as_text=True).splitlines() if l.startswith("data: ")]
    fin = evs[-1]
    assert fin["kind"] == "fin" and fin["ok"] == 14 and fin["echecs"] == 0
    z = c.get(fin["url"])
    assert z.status_code == 200
    assert "S01_TP01_corrige.pdf" in zipfile.ZipFile(io.BytesIO(z.data)).namelist()
    assert c.get("/api/v2/livret-sequence/N09/M01/tout-compiler").status_code == 400
    assert c.get("/api/v2/livret-sequence/N09/S77/tout-compiler").status_code == 404
    assert c.get("/api/v2/livret-sequence/N09/S01/tout-compiler?gabarit=xx").status_code == 400


def test_route_tout_compiler_d_une_sequence_absente_du_profil_classe(app_6e):
    c = create_app(app_6e.json_store.data_dir, profil="classe").test_client()
    assert c.get("/api/v2/livret-sequence/N09/S01/tout-compiler").status_code == 404
