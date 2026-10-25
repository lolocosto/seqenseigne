"""tests/test_v0_53_3_rendu_mer.py — v0.53.3

Onglet « Rendu PDF » d'une mise en route (demandes de Laurent du 25 octobre 2026,
doc/redemarrage_v0_53_3.md) :

1. D-SEL — seuls les sélecteurs qui ont un sens pour le document sont affichés :
   la table du navigateur (static/seqniv_pur.js) est celle du serveur ;
2. Test n° borné : de 1 au nombre de tests de la partie (ou de la séquence),
   la route refuse aussi (400 et message qui dit les bornes) ;
3. D-TOUT — « Tout compiler » : liste des documents, noms des PDF, flux SSE,
   archive ZIP, log d'un échec, abandon sur erreurs d'infrastructure.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

from app import create_app
from services import mer_tout_compiler as tc
from services import mises_en_route_6e as mer
from services.compilateur_pdf import ErreurLatex, ResultatCompilation
from tests.test_v0_53_0_mises_en_route import (_appliquer, _conn, _ecrire_lot, _lot,  # noqa: F401
                                               base)

APPLI = Path(__file__).resolve().parent.parent


def _client(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    return create_app(base.parent, profil="atelier").test_client()


# ── 1. D-SEL ────────────────────────────────────────────────────────────────

def test_table_des_selecteurs_du_navigateur_identique_a_celle_du_serveur():
    """Une seule vérité : un sélecteur masqué dans l'atelier ne doit pas être
    une option que le serveur lit pour ce document (et inversement)."""
    js = (APPLI / "static" / "seqniv_pur.js").read_text(encoding="utf-8")
    bloc = js[js.index("const SELECTEURS_DOCUMENT_MER = {"):]
    bloc = bloc[:bloc.index("};")]
    table = {m.group(1): tuple(re.findall(r"'(\w+)'", m.group(2)))
             for m in re.finditer(r"(\w+):\s*\[([^\]]*)\]", bloc)}
    assert table == mer.SELECTEURS_DOCUMENT_MER
    assert set(table) == set(mer.DOCUMENTS_MER)


def test_plan_et_dossier_n_ont_qu_une_version_donc_aucun_selecteur():
    assert mer.SELECTEURS_DOCUMENT_MER["plan"] == () == mer.SELECTEURS_DOCUMENT_MER["dossier"]
    assert "test" in mer.SELECTEURS_DOCUMENT_MER["test_court"]
    assert "par_page" in mer.SELECTEURS_DOCUMENT_MER["planche"]


# ── 2. Test n° borné ────────────────────────────────────────────────────────

def test_route_refuse_un_test_hors_bornes_avec_les_bornes_dans_le_message(base, tmp_path):
    c = _client(base, tmp_path)
    url = "/api/v2/livret-sequence/N09/M01/rendu-tex?document=test_court&partie=1&test="
    assert c.get(url + "1").status_code == 200
    r = c.get(url + "2")
    assert r.status_code == 400 and "hors bornes, de 1 à 1" in r.get_json()["message"]
    r = c.get(url + "0")
    assert r.status_code == 400 and "le premier test court est le n° 1" in r.get_json()["message"]
    r = c.post("/api/v2/livret-sequence/N09/M01/rendu-pdf",
               json={"options": {"mer": {"document": "test_court", "test": 9}}})
    assert r.status_code == 400 and "de 1 à 4" in r.get_json()["message"]


# ── 3. D-TOUT ───────────────────────────────────────────────────────────────

def test_liste_des_documents_d_une_partie_et_noms_clairs(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    s = mer.lire_sequence_mer(_conn(base), "N09", "M01")
    noms = [n for n, _ in tc.documents_a_compiler(s, 1)]
    assert noms == ["M01_p1_fiche_eleve.pdf", "M01_p1_fiche_complete.pdf",
                    "M01_p1_seances_4parA4_eleve.pdf", "M01_p1_seances_4parA4_corrige.pdf",
                    "M01_p1_test1_A_eleve.pdf", "M01_p1_test1_A_corrige.pdf",
                    "M01_p1_test1_B_eleve.pdf", "M01_p1_test1_B_corrige.pdf",
                    "M01_p1_plan.pdf", "M01_p1_dossier_enseignant.pdf"]
    tout = tc.documents_a_compiler(s, None)
    assert len(tout) == 4 * 10 and len({n for n, _ in tout}) == 40
    for _, o in tout:                                   # chaque option est valide
        mer.options_mer(o)


def _faux_compilateur(echec=None, infra=False):
    def compiler(tex):
        if echec and echec in tex:
            msg = "pdflatex introuvable" if infra else "Undefined control sequence."
            return ResultatCompilation(ok=False, erreurs=[ErreurLatex(ligne=1, message=msg)],
                                       log_complet="LOG " + msg)
        return ResultatCompilation(ok=True, pdf_bytes=b"%PDF-1.4 " + tex[:20].encode())
    return compiler


def test_tout_compiler_donne_statuts_log_d_echec_et_archive_des_pdf(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    evs = list(tc.iter_tout_compiler(
        lambda: _conn(base), "N09", "M01", 2, compiler=_faux_compilateur(echec="dossier enseignant"),
        dossier_echecs=tmp_path / "e", dossier_archives=tmp_path / "a"))
    assert evs[0]["kind"] == "debut" and evs[0]["total"] == 10
    docs = [e for e in evs if e["kind"] == "document"]
    echecs = [e for e in docs if e["statut"] == "echec"]
    assert len(docs) == 10 and [e["nom"] for e in echecs] == ["M01_p2_dossier_enseignant.pdf"]
    assert (tmp_path / "e" / echecs[0]["log"]).read_text() == "LOG Undefined control sequence."
    fin = evs[-1]
    assert fin["kind"] == "fin" and fin["ok"] == 9 and fin["echecs"] == 1
    with zipfile.ZipFile(tmp_path / "a" / fin["archive"]) as z:
        assert len(z.namelist()) == 9 and "M01_p2_plan.pdf" in z.namelist()


def test_tout_compiler_abandonne_apres_erreurs_d_infrastructure_consecutives(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    evs = list(tc.iter_tout_compiler(
        lambda: _conn(base), "N09", "M01", 1, compiler=_faux_compilateur(echec="\\", infra=True),
        dossier_echecs=tmp_path / "e", dossier_archives=tmp_path / "a",
        max_erreurs_consecutives=2))
    assert evs[-1]["kind"] == "abandon" and len([e for e in evs if e["kind"] == "document"]) == 2
    assert not (tmp_path / "a").exists()


def test_route_tout_compiler_flux_sse_puis_archive_telechargeable(base, tmp_path, monkeypatch):
    c = _client(base, tmp_path)
    import routes.livret_sequence as rl
    monkeypatch.setattr(rl, "compiler_atome", lambda tex_source, **kw: _faux_compilateur()(tex_source))
    r = c.get("/api/v2/livret-sequence/N09/M01/mer/tout-compiler?partie=3")
    assert r.status_code == 200 and r.mimetype == "text/event-stream"
    evs = [json.loads(l[6:]) for l in r.get_data(as_text=True).splitlines() if l.startswith("data: ")]
    fin = evs[-1]
    assert fin["kind"] == "fin" and fin["ok"] == 10 and fin["url"].endswith(fin["archive"])
    z = c.get(fin["url"])
    assert z.status_code == 200 and z.mimetype == "application/zip"
    assert "M01_p3_test1_B_corrige.pdf" in zipfile.ZipFile(io.BytesIO(z.data)).namelist()
    assert c.get("/api/v2/livret-sequence/mer/archive/..%2Fx.zip").status_code in (400, 404)
    assert c.get("/api/v2/livret-sequence/mer/echec/x.pdf").status_code == 400
    assert c.get("/api/v2/livret-sequence/N09/M01/mer/tout-compiler?partie=9").status_code == 400
    assert c.get("/api/v2/livret-sequence/N09/S01/mer/tout-compiler").status_code == 400


def test_routes_tout_compiler_sont_de_l_atelier_absentes_du_profil_classe(base, tmp_path):
    c = create_app(base.parent, profil="classe").test_client()
    assert c.get("/api/v2/livret-sequence/N09/M01/mer/tout-compiler").status_code == 404
