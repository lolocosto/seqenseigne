"""tests/test_v0_56_0_series_mention.py — v0.56.0

Décisions de Laurent (13 novembre 2026, 12 h 12 ; doc/redemarrage_v0_56_0.md) :

1. SERIES — modèle Fiches : séries F, A, E affichées « Entraînement », « Approfondissement »,
   « Expertise », codes affichés EN06 / AP05 / EX02 ; codes internes F, A, E inchangés (base,
   lots, format d'échange) ; AE, EV, TP, AC, AT, MR et le cycle 4 inchangés ;
2. MENTION — `exercices.mention` O (défaut) / F : migration idempotente, atelier, clé de lot
   `mention` (idempotente, jamais sur un exercice validé, signalée), format d'échange 1.6
   (empreinte inchangée quand tout est O), en-tête (O) / (F) du livret, (R) pour la remédiation ;
3. page de garde : colonnes « Je me suis entraîné », « J'ai approfondi », « Je suis expert »,
   consigne « Coche une case seulement quand tu as fini toute la série. », légende O / R / F.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import series_fiches as sf  # noqa: E402
from tests.test_v0_52_0_import_lot6e import (  # noqa: E402,F401
    _conn, _dump, _lot_s01, base, imp)
from tests.test_v0_52_7_marqueurs import _appliquer, _marquer, app_6e  # noqa: E402,F401

PAQUET = Path(__file__).parent.parent / "paquet"
TBLR = ["booktabs", "varwidth"]


# ── 1. Codes affichés ───────────────────────────────────────────────────────

def test_codes_affiches_en_ap_ex_et_autres_series_inchangees():
    assert sf.code_affiche("F", 6) == "EN06"
    assert sf.code_affiche("A", 5) == "AP05"
    assert sf.code_affiche("E", "2") == "EX02"
    for s in ("AE", "EV", "TP", "AC", "AT", "MR"):
        assert sf.code_affiche(s, 3) == f"{s}03"
    assert sf.code_interne_vers_affiche("F12") == "EN12"
    assert sf.code_interne_vers_affiche("AE01") == "AE01"
    assert [sf.TITRES[s] for s in "FAE"] == ["Entraînement", "Approfondissement", "Expertise"]


def test_livret_series_renommees_codes_affiches_et_mention_dans_l_en_tete(app_6e):
    """« Les titres de série du livret deviennent simplement Entraînement, Approfondissement,
    Expertise » ; l'en-tête affiche (O) ou (F) dans toutes les séries, (R) pour une remédiation."""
    from services.livret_sequence_6e import generer_livret_sequence_6e
    with app_6e.json_store._conn() as c:
        tex = generer_livret_sequence_6e(c, "N09", "S01", {}, tblr_libraries=TBLR)
        c.execute("UPDATE exercices SET mention='F' WHERE id='e1'")
        tex_f = generer_livret_sequence_6e(c, "N09", "S01", {}, tblr_libraries=TBLR)
    for titre in ("Entraînement", "Approfondissement", "Expertise"):
        assert r"\seqPartieSix{" + titre + "}" in tex
    assert "Exercices fondamentaux" not in tex
    assert "seqSixGrisTexte}EN01}]" in tex and "seqSixGrisTexte}AP01}]" in tex \
        and "seqSixGrisTexte}EX01}]" in tex
    assert "seqSixGrisTexte}F01}" not in tex
    assert r"\begin{seqExoSix}[R][Remédiation -- Former" in tex
    assert r"[A][" not in tex and r"[E][" not in tex
    assert r"\begin{seqExoSix}[O][Défi" in tex and r"\begin{seqExoSix}[F][Défi" in tex_f


def test_message_de_validation_nomme_la_serie_affichee_au_modele_fiches(app_6e):
    from services.v2_edition import _valider_sequence_hook, ValidationSequenceErreur
    with app_6e.json_store._conn() as c:
        c.execute("DELETE FROM objectif_exos WHERE serie='A'")
        sn = c.execute("SELECT id FROM sequences_par_niveau WHERE niveau='N09' "
                       "AND sequence_code='S01'").fetchone()[0]
        with pytest.raises(ValidationSequenceErreur) as e:
            _valider_sequence_hook(c, sn)
    assert "dans la série Approfondissement (AP)." in " | ".join(map(str, e.value.raisons))


# ── 2. Mention : données et atelier ─────────────────────────────────────────

def test_migration_idempotente_mention_o_par_defaut_car_tout_est_obligatoire_aujourd_hui():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE exercices (id TEXT PRIMARY KEY, titre TEXT)")
    c.execute("INSERT INTO exercices VALUES ('x', 't')")
    assert sf.migrer(c) is True and sf.migrer(c) is False
    cols = {r[1]: r for r in c.execute("PRAGMA table_info(exercices)")}
    assert cols["mention"][3] == 1                                   # NOT NULL
    assert c.execute("SELECT mention FROM exercices").fetchone() == ("O",)


def test_valeurs_de_mention_fermees():
    assert sf.valider(None) == sf.valider("") == sf.valider("o") == "O"
    assert sf.valider("F") == "F"
    with pytest.raises(sf.MentionInvalide):
        sf.valider("R")              # R reste le statut de la remédiation, pas une mention


def test_atelier_enregistre_relit_et_refuse_une_mention_inconnue(app_6e):
    cl = app_6e.test_client()
    eid = cl.post("/api/exercices", json={"serie": "fondamental", "niveau": "N09",
                                          "sequence": "S01"}).get_json()["id"]
    assert cl.get(f"/api/exercices/{eid}").get_json()["mention"] == "O"
    assert cl.patch(f"/api/exercices/{eid}", json={"mention": "F"}).status_code == 200
    assert cl.get(f"/api/exercices/{eid}").get_json()["mention"] == "F"
    assert cl.patch(f"/api/exercices/{eid}", json={"mention": "X"}).status_code == 400
    # un enregistrement sans la clé (scanner, appel partiel) garde la mention
    assert cl.patch(f"/api/exercices/{eid}", json={"titre": "T"}).status_code == 200
    assert cl.get(f"/api/exercices/{eid}").get_json()["mention"] == "F"


# ── 2. Mention : import des lots ────────────────────────────────────────────

def _mentions(db):
    c = _conn(db)
    return {f"{r['serie_code']}{r['num']:02d}": r["mention"]
            for r in c.execute("SELECT * FROM exercices WHERE niveau='N09' AND sequence='S01' "
                               "AND serie_code IN ('F', 'A', 'E')")}


def test_import_lit_la_cle_mention_absente_o_et_reste_idempotent(base, tmp_path):
    lots = _lot_s01(tmp_path / "lots")
    _appliquer(base, lots)
    assert set(_mentions(base).values()) == {"O"}
    _marquer(lots, exos={("S01-02", "exercices", 2): {"mention": "F"}})
    rapport = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                                base.parent / "images").texte()
    assert "mentions (séries F, A, E) : obligatoire 4, facultatif 1" in rapport
    _appliquer(base, lots)
    assert _mentions(base)["F02"] == "F" and _mentions(base)["F01"] == "O"
    etat = _dump(base, ("exercices",))
    _appliquer(base, lots)
    assert _dump(base, ("exercices",)) == etat
    # clé retirée du lot : le lot fait foi (retour à O)
    _marquer(lots, exos={("S01-02", "exercices", 2): {"mention": "O"}})
    _appliquer(base, lots)
    assert _mentions(base)["F02"] == "O"


def test_import_jamais_sur_un_exercice_valide_et_mention_inconnue_signalee(base, tmp_path):
    lots = _lot_s01(tmp_path / "lots")
    _appliquer(base, lots)
    c = _conn(base)
    c.execute("UPDATE exercices SET etat_code='valide' WHERE niveau='N09' AND sequence='S01' "
              "AND serie_code='F' AND num=1")
    c.commit()
    c.close()
    _marquer(lots, exos={("S01-02", "exercices", 1): {"mention": "F"},
                         ("S01-02", "exercices", 2): {"mention": "Z"}})
    r = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                          base.parent / "images")
    assert any("F01 validé dans l'atelier" in a for a in r.anomalies)
    assert any("mention 'Z' inconnue" in a for a in r.anomalies)
    _appliquer(base, lots)
    assert _mentions(base)["F01"] == "O" and _mentions(base)["F02"] == "O"


# ── 2. Mention : format d'échange ───────────────────────────────────────────

def test_format_1_6_seulement_avec_un_facultatif_empreinte_inchangee_sinon(app_6e):
    from services import format_referentiel as fr
    from services import referentiels_internes as ri
    with app_6e.json_store._conn() as c:
        ri.ecrire_instantane(c, "R09")
        avant = fr.construire(c, "R09", None)
        assert all("facultatifs" not in p for s in avant["sequences"] for p in s["parties"])
        c.execute("UPDATE exercices SET mention='F' WHERE id='e1'")
        apres = fr.construire(c, "R09", None)
        c.execute("UPDATE exercices SET mention='O' WHERE id='e1'")
        retour = fr.construire(c, "R09", None)
    assert avant["format_version"] != "1.6" and retour["empreinte"] == avant["empreinte"]
    # v0.60.1 : 1.7 = mode de mise en route ; 1.6 reste la version des facultatifs.
    assert apres["format_version"] == fr.FORMAT_VERSION_FACULTATIFS == "1.6"
    fac = [x for s in apres["sequences"] for p in s["parties"] for x in p.get("facultatifs", [])]
    assert fac == [{"objectif": "02", "serie": "E", "exercice": "E01", "titre": "Défi"}]
    assert fr.valider(apres) == []
    schema = json.loads((Path(__file__).parent.parent / "schemas" / "referentiel-1.json")
                        .read_text(encoding="utf-8"))
    assert "facultatif" in schema["$defs"]


# ── 3. Page de garde ────────────────────────────────────────────────────────

def test_page_de_garde_consigne_et_legende_des_mentions():
    sty = (PAQUET / "seqenseigne-style6e.sty").read_text(encoding="utf-8")
    assert "Coche~une~case~seulement~quand~tu~as~fini~toute~la~série." in sty
    assert (r"\textbf{O}~:~obligatoire~---~\textbf{R}~:~remédiation~---~"
            r"\textbf{F}~:~facultatif") in sty
    for ancien in ("découvre", "Je~sais \\newline faire"):
        assert ancien not in sty
