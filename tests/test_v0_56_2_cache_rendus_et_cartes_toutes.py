"""tests/test_v0_56_2_cache_rendus_et_cartes_toutes.py — v0.56.2

Demandes de Laurent (13 novembre 2026, 16 h 11), doc/redemarrage_v0_56_2.md :
  - invalider le rendu PDF à la main « quand une macro de mise en forme a changé,
    même si le contenu de l'atome est identique » : `?sans_cache=1` sur toutes les
    routes de compilation (Recompiler sans cache, option des « Tout compiler »),
    « Vider le cache des rendus PDF » dans Administration ;
  - la clé du cache contient l'empreinte des `.sty`/`.dtx` du paquet : le cache
    s'invalide tout seul quand le module change ;
  - atelier Carte mentale sans séquence choisie : toutes les séquences du niveau.
"""
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import cache_rendus, compilateur_pdf as cp  # noqa: E402
from tests.test_v0_52_2_documents_6e import app_6e  # noqa: E402,F401
from tests.test_v0_55_0_cartes_mentales import CARTE  # noqa: E402

TEX = "\\documentclass{article}\\begin{document}x\\end{document}"


# ── Clé du cache : empreinte du paquet ──────────────────────────────────────

@pytest.fixture
def paquet(tmp_path, monkeypatch):
    d = tmp_path / "paquet"
    d.mkdir()
    (d / "seqenseigne-style6e.sty").write_text("\\newcommand\\seqA{A}", encoding="utf-8")
    (d / "seqenseigne-style6e.dtx").write_text("% source", encoding="utf-8")
    (d / "README.md").write_text("ignoré", encoding="utf-8")
    monkeypatch.setattr(cp, "dossiers_paquet_empreinte", lambda: [d])
    cp._memo_empreinte.update(signature=None, empreinte="")
    return d


def test_cle_du_cache_change_quand_une_macro_du_paquet_change_meme_tex(paquet):
    avant = cp.hash_tex(TEX)
    sty = paquet / "seqenseigne-style6e.sty"
    sty.write_text("\\newcommand\\seqA{B}", encoding="utf-8")   # même taille
    os.utime(sty, ns=(sty.stat().st_atime_ns, sty.stat().st_mtime_ns + 10**9))
    assert cp.hash_tex(TEX) != avant
    assert len(cp.hash_tex(TEX)) == 16


def test_cle_du_cache_change_aussi_pour_un_dtx_mais_pas_pour_un_autre_fichier(paquet):
    avant = cp.hash_tex(TEX)
    (paquet / "README.md").write_text("autre texte, plus long", encoding="utf-8")
    assert cp.hash_tex(TEX) == avant
    (paquet / "seqenseigne-style6e.dtx").write_text("% source modifiée", encoding="utf-8")
    assert cp.hash_tex(TEX) != avant


def test_cle_stable_tant_que_rien_ne_change_et_differente_selon_le_tex(paquet):
    assert cp.hash_tex(TEX) == cp.hash_tex(TEX)
    assert cp.hash_tex(TEX) != cp.hash_tex(TEX + " ")


def test_sans_paquet_la_cle_reste_celle_d_avant_la_v0_56_2(monkeypatch):
    monkeypatch.setattr(cp, "dossiers_paquet_empreinte", lambda: [])
    assert cp.hash_tex(TEX) == hashlib.sha256(TEX.encode("utf-8")).hexdigest()[:16]


def test_dossiers_de_l_empreinte_sont_ceux_du_paquet_de_l_appli_et_du_texinputs():
    # appli/paquet (sources poussées) et <racine>/reference/paquet (TEXINPUTS,
    # cf. dossier_paquet_effectif) : les deux endroits où pdflatex peut lire le paquet.
    appli = Path(cp.__file__).resolve().parent.parent
    attendus = {appli / "paquet", appli.parent / "reference" / "paquet"}
    assert set(cp.dossiers_paquet_empreinte()) <= attendus
    assert (appli / "paquet") in cp.dossiers_paquet_empreinte()     # présent dans le dépôt


# ── compiler_atome(ignorer_cache=True) ──────────────────────────────────────

@pytest.fixture
def faux_pdflatex(tmp_path):
    """Exécutable qui écrit un atome.pdf (contenu « NOUVEAU »)."""
    f = tmp_path / "faux_pdflatex"
    f.write_text("#!/bin/sh\nprintf 'NOUVEAU' > atome.pdf\nprintf 'log' > atome.log\n", encoding="utf-8")
    f.chmod(f.stat().st_mode | stat.S_IEXEC)
    return str(f)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="script shell")
def test_sans_cache_le_pdf_en_cache_est_ignore_et_remplace(tmp_path, faux_pdflatex):
    cache = tmp_path / "cache"
    cache.mkdir()
    cp.chemin_pdf_cache(cache, cp.hash_tex(TEX)).write_bytes(b"ANCIEN")
    r = cp.compiler_atome(TEX, cache_dir=cache, pdflatex=faux_pdflatex)
    assert r.depuis_cache and r.pdf_bytes == b"ANCIEN"          # comportement par défaut
    r = cp.compiler_atome(TEX, cache_dir=cache, pdflatex=faux_pdflatex, ignorer_cache=True)
    assert not r.depuis_cache and r.pdf_bytes == b"NOUVEAU"
    assert cp.chemin_pdf_cache(cache, cp.hash_tex(TEX)).read_bytes() == b"NOUVEAU"
    r = cp.compiler_atome(TEX, cache_dir=cache, pdflatex=faux_pdflatex)
    assert r.depuis_cache and r.pdf_bytes == b"NOUVEAU"


def test_sans_cache_un_echec_ne_laisse_pas_revenir_le_pdf_perime(tmp_path):
    # « Ignore et remplace » : le PDF périmé est retiré avant la compilation, pour
    # qu'il ne soit plus jamais resservi même si la recompilation échoue.
    cache = tmp_path / "cache"
    cache.mkdir()
    pdf = cp.chemin_pdf_cache(cache, cp.hash_tex(TEX))
    pdf.write_bytes(b"ANCIEN")
    r = cp.compiler_atome(TEX, cache_dir=cache, pdflatex=str(tmp_path / "absent"),
                          ignorer_cache=True)
    assert not r.ok
    assert not pdf.exists()


def test_parametre_sans_cache_de_la_requete():
    for v in ("1", "true", "oui", "on", "TRUE"):
        assert cache_rendus.sans_cache_demande({"sans_cache": v})
    for v in ("", "0", "non", None):
        assert not cache_rendus.sans_cache_demande({"sans_cache": v})
    assert not cache_rendus.sans_cache_demande({})


# ── Vider le cache ──────────────────────────────────────────────────────────

def test_vider_le_cache_compte_les_fichiers_et_garde_les_logs_d_echec(tmp_path):
    cache = tmp_path / "cache_rendus"
    (cache / "echecs").mkdir(parents=True)
    (cache / "echecs_mer").mkdir()
    (cache / "a.pdf").write_bytes(b"12345")
    (cache / "a.log").write_text("log")
    (cache / "b.pdf").write_bytes(b"1")
    (cache / "echecs" / "x.log").write_text("échec gardé")
    assert cache_rendus.etat_cache(cache) == {"nb_pdf": 2, "nb_log": 1, "octets": 9}
    r = cache_rendus.vider_cache(cache)
    assert r == {"nb_pdf": 2, "nb_log": 1, "nb_fichiers": 3, "octets": 9}
    assert not list(cache.glob("*.pdf")) and (cache / "echecs" / "x.log").is_file()
    assert cache_rendus.vider_cache(tmp_path / "absent")["nb_fichiers"] == 0


def test_routes_d_administration_du_cache(app_6e):
    cl = app_6e.test_client()
    cache = Path(app_6e.json_store.data_dir) / "cache_rendus"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "x.pdf").write_bytes(b"pdf")
    (cache / "x.log").write_text("log")
    etat = cl.get("/api/admin/cache-rendus").get_json()
    assert etat["nb_pdf"] == 1 and etat["nb_log"] == 1 and "empreinte_paquet" in etat
    r = cl.post("/api/admin/cache-rendus/vider").get_json()
    assert r["ok"] and r["nb_fichiers"] == 2 and r["nb_pdf"] == 1
    assert cl.get("/api/admin/cache-rendus").get_json()["nb_pdf"] == 0


def test_routes_du_cache_classees_atelier():
    from services import profils
    for e in ("admin.api_cache_rendus_etat", "admin.api_cache_rendus_vider"):
        assert profils.categorie(e) == "atelier"


# ── Toutes les routes de compilation transmettent ?sans_cache=1 ─────────────

def test_route_de_compilation_transmet_sans_cache_au_compilateur(app_6e, monkeypatch):
    vus = []

    def faux(tex_source, **kw):
        vus.append(kw.get("ignorer_cache"))
        return cp.ResultatCompilation(ok=True, pdf_bytes=b"%PDF")
    import routes.livret_sequence as rl
    monkeypatch.setattr(rl, "compiler_atome", faux)
    cl = app_6e.test_client()
    url = "/api/v2/livret-sequence/N09/S01/cartes-mentales"
    cl.put(url + "/1", json={"titre": "N", "latex": CARTE})
    assert cl.post(url + "/1/rendu-pdf").status_code == 200
    assert cl.post(url + "/1/rendu-pdf?version=eleve&sans_cache=1").status_code == 200
    assert vus == [False, True]


def test_chaque_route_qui_compile_avec_le_cache_lit_sans_cache():
    # Atomes, évaluations, livret / cartes mentales / documents de séquence, plan de
    # travail, et les deux « Tout compiler » (séquence et mise en route).
    racine = Path(__file__).parent.parent / "routes"
    attendus = {"rendu_atome.py": 1, "evaluations.py": 1, "plans_de_travail.py": 1,
                "livret_sequence.py": 3}
    for nom, n in attendus.items():
        src = (racine / nom).read_text(encoding="utf-8")
        assert src.count("ignorer_cache=sans_cache") == n, nom


# ── Atelier Carte mentale : toutes les séquences du niveau ──────────────────

def test_liste_du_niveau_toutes_les_sequences_principales_sans_mise_en_route_ni_archive(app_6e):
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres, etat_code) "
                  "VALUES ('sn62', 'N09', 'S02', '', 'valide'), ('snm1', 'N09', 'M01', '', 'en_cours')")
        c.execute("INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
                  "VALUES ('p621', 'sn62', 1), ('p622', 'sn62', 2), ('pm11', 'snm1', 1)")
        c.commit()
    cl = app_6e.test_client()
    cl.put("/api/v2/livret-sequence/N09/S01/cartes-mentales/1", json={"titre": "N", "latex": CARTE})
    r = cl.get("/api/v2/livret-sequence/N09/cartes-mentales")
    assert r.status_code == 200
    seqs = r.get_json()["sequences"]
    assert [s["sequence"] for s in seqs] == ["S01", "S02"]        # ni M01 ni X02
    assert seqs[0]["modifiable"] is True and seqs[1]["modifiable"] is False
    assert seqs[0]["parties"][0]["carte"]["titre"] == "N"
    assert [p["numero"] for p in seqs[1]["parties"]] == [1, 2]
    assert all(p["carte"] is None for p in seqs[1]["parties"])
    assert cl.get("/api/v2/livret-sequence/N99/cartes-mentales").status_code == 400


def test_liste_du_niveau_classee_atelier(app_6e):
    from services import profils
    regle = [r for r in app_6e.url_map.iter_rules()
             if r.rule == "/api/v2/livret-sequence/<niveau>/cartes-mentales"]
    assert len(regle) == 1 and profils.categorie(regle[0].endpoint) == "atelier"
