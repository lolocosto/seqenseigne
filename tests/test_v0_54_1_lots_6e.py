"""tests/test_v0_54_1_lots_6e.py — v0.54.1

Décisions (doc/redemarrage_v0_54_1.md) :

1. D-DOUBLON — l'import signale en anomalie deux documents des lots (TP, AC,
   AT, évaluations, tests courts) qui portent le même titre : deux TP
   s'appelaient « La kermesse du collège » (S04 et S12), ce qui trompe les
   élèves et les collègues ; les évaluations sont en plus repérées par leur
   titre dans le niveau. Les sujets A et B d'une même évaluation ne sont pas
   des doublons.
2. Référentiel ref6e_v2 du 25 octobre 2026 (copie de col6/ref6e_v2.md) :
   19 dépendances des lots M, 3 lignes corrigées, cycle M06-02 / S10-02
   signalé sans être tranché, durée de S12, code AE, récapitulatif à jour ;
   intitulés et critères inchangés (objectifs_6e.json reste la transcription).

Base de test reconstruite à chaque test (jamais de base réelle).
"""

from __future__ import annotations

import json
from pathlib import Path

from outils import import_lot6e as imp
from tests.test_v0_53_0_mises_en_route import _ecrire_lot, _essai, _lot, base  # noqa: F401

APPLI = Path(__file__).resolve().parent.parent
REF = APPLI / "outils" / "ref6e_v2.md"


def _tp(titre):
    return {"titre": titre, "latex": "x", "corrige": "y", "objectifs": []}


def _ev(titre, sujet):
    return {"titre": titre, "sujet": sujet, "latex": "", "bareme": [], "total": 20}


# ── 1. D-DOUBLON ─────────────────────────────────────────────────────────────

def test_deux_tp_de_meme_titre_dans_deux_sequences_signales_car_ils_trompent_les_eleves():
    lots = [{"sequence": "S04", "travaux_personnels": [_tp("La kermesse du collège")]},
            {"sequence": "S12", "travaux_personnels": [_tp("La kermesse du collège")]}]
    assert imp.titres_documents_en_double(lots) == [
        "« La kermesse du collège » : S04 TP01, S12 TP01"]


def test_sujets_a_et_b_d_une_meme_evaluation_ne_sont_pas_des_doublons():
    lots = [{"sequence": "S01", "evaluations": [_ev("Évaluation --- Nombres", "A"),
                                                _ev("Évaluation --- Nombres", "B")]}]
    assert imp.titres_documents_en_double(lots) == []


def test_meme_titre_d_evaluation_dans_deux_sequences_signale_car_l_import_repere_par_titre():
    lots = [{"sequence": "S10", "evaluations": [_ev("Gestion de données", "A"),
                                                _ev("Gestion de données", "B")]},
            {"sequence": "M06", "evaluations": [_ev("Gestion de données", "A")]}]
    (x,) = imp.titres_documents_en_double(lots)
    assert "S10 évaluation sujet A" in x and "M06 évaluation sujet A" in x


def test_doublon_entre_series_et_sans_tenir_compte_de_la_casse_ni_des_espaces():
    lots = [{"sequence": "S02", "activites_complementaires": [_tp("Le  labyrinthe")],
             "seances_atelier": [_tp("le labyrinthe ")]}]
    assert imp.titres_documents_en_double(lots) == ["« Le  labyrinthe » : S02 AC01, S02 AT01"]


def test_evaluation_retiree_n_est_pas_un_document_du_lot():
    lots = [{"sequence": "S01", "evaluations": [_ev("Éval", "A"), _ev("Éval", "B")],
             "evaluations_retirees": ["Éval"]}]
    assert imp.titres_documents_en_double(lots) == []


def test_doublon_signale_dans_l_essai_a_blanc_sans_bloquer_l_import(base, tmp_path):
    lot = _lot()
    lot["activites_complementaires"] = [
        {"titre": "Le tour de la roue", "objectif": "M01-22", "latex": "a", "corrige": "b",
         "origine": "création"},
        {"titre": "Le tour de la roue", "objectif": "M01-22", "latex": "c", "corrige": "d",
         "origine": "création"}]
    r = _essai(base, _ecrire_lot(tmp_path / "l", lot))
    signales = [a for a in r.anomalies if a.startswith("titre de document en double")]
    assert signales == ["titre de document en double « Le tour de la roue » : M01 AC01, "
                        "M01 AC02 — renommer l'un des documents dans son lot (risque de "
                        "confusion pour les élèves et les collègues)"]
    assert "M01" in r.sequences                                  # le lot est importé quand même


# ── 2. Référentiel ref6e_v2 du 25 octobre 2026 ───────────────────────────────

DEPENDANCES_M = ["M01-22 → S01-02", "M02-02 → S03-03", "M02-12 → S01-04", "M02-12 → S01-13",
                 "M02-22 → S01-13", "M02-32 → S03-24", "M03-12 → M03-02", "M03-22 → S03-22",
                 "M04-02 → M03-02", "M04-12 → S03-13", "M04-22 → S06-02", "M04-22 → S03-12",
                 "M05-02 → S05-02", "M05-02 → S05-03", "M06-02 → S10-02", "M07-12 → S12-02",
                 "M07-12 → S12-04", "S03-34 → M02-22", "S03-35 → M02-22"]


def _contraintes() -> str:
    t = REF.read_text(encoding="utf-8")
    return t[t.index("### Contraintes de progression"):t.index("\n## S01 — ")]


def test_ref6e_v2_porte_les_19_dependances_des_lots_m_une_ligne_chacune():
    c = _contraintes()
    assert len(DEPENDANCES_M) == 19
    for d in DEPENDANCES_M:
        assert c.count(f"- {d} :") == 1, d


def test_cycle_m06_s10_signale_a_trancher_sans_retirer_aucune_des_deux_dependances():
    c = _contraintes()
    assert "- S10-02 → M06-02 :" in c and "- M06-02 → S10-02 :" in c
    assert "- Cycle M06-02 ↔ S10-02 : **à trancher** (question 9 du rapport de cohérence du " \
           "25 octobre 2026)" in c


def test_trois_lignes_erronees_corrigees():
    t = REF.read_text(encoding="utf-8")
    assert "- S12-02 → M04 : 1 min = 60 s" not in t and "- S12-02 → M03-22 : 1 min = 60 s" in t
    assert "- S12-02 → M03 : 1 kg" not in t
    assert "« Pourcentage » (N10/S01/C02, fiche M02)" not in t


def test_duree_de_s12_et_code_ae_corriges_et_recapitulatif_a_jour():
    t = REF.read_text(encoding="utf-8")
    assert "environ 4 séances" not in t and "courte (4 séances)" not in t
    assert "EA = activité d'approche" not in t and "AE = activité d'approche" in t
    assert "## Récapitulatif : ce qui est à créer" not in t
    recap = t[t.index("## Récapitulatif : état au 25 octobre 2026"):]
    for chiffre in ("185 F, 194 A, 104 E et 69 activités d'approche", "52 fiches de résumé",
                    "18 évaluations sur 20", "24 travaux personnels (TP), 23 activités "
                    "complémentaires (AC) et 1 séance d'atelier", "131 exercices de séance",
                    "22 tests courts"):
        assert chiffre in recap, chiffre


def test_objectifs_6e_json_note_la_recopie_du_25_octobre_sans_changer_la_transcription():
    # La transcription exacte (intitulés, critères, parties) est vérifiée par
    # test_v0_52_5_objectifs_s05 ; ici, la source dit ce qui a changé.
    ref = json.loads((APPLI / "outils" / "objectifs_6e.json").read_text(encoding="utf-8"))
    assert "recopie du 25 octobre 2026 (v0.54.1) : sections S01 à S13 inchangées" in ref["source"]
