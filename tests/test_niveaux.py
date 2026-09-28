"""
tests/test_niveaux.py — Tests unitaires de services/niveaux.py

Aucune dépendance Flask ni I/O. Lancer avec :
    pytest tests/test_niveaux.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.niveaux import (
    NIVEAUX, CODES_NOTES, CODES_SANS_NOTE, MIGRATION_CODES,
    est_code_valide,
    code_vers_libelle, code_vers_libelle_court, code_vers_points, code_vers_info,
    migrer_ancien_code, migrer_batch,
    calculer_moyenne,
    deduire_niveau,
    rang_creneau, grouper_objectifs_par_creneau,
    referentiel_api,
)


# ── Cohérence du référentiel ───────────────────────────────────────────────────

class TestReferentiel:

    def test_codes_attendus_presents(self):
        for code in ("0", "1", "2", "3", "4", "A", "D", "NE"):
            assert code in NIVEAUX, f"Code manquant : {code}"

    def test_champs_obligatoires(self):
        for code, info in NIVEAUX.items():
            assert "libelle" in info,       f"{code} : champ 'libelle' manquant"
            assert "libelle_court" in info, f"{code} : champ 'libelle_court' manquant"
            assert "points" in info,        f"{code} : champ 'points' manquant"
            assert "couleur" in info,       f"{code} : champ 'couleur' manquant"
            assert "ordre" in info,         f"{code} : champ 'ordre' manquant"

    def test_points_codes_notes(self):
        assert NIVEAUX["1"]["points"] == 4
        assert NIVEAUX["2"]["points"] == 10
        assert NIVEAUX["3"]["points"] == 16
        assert NIVEAUX["4"]["points"] == 20

    def test_points_codes_sans_note(self):
        for code in ("A", "D", "NE"):
            assert NIVEAUX[code]["points"] is None, f"{code} devrait avoir points=None"

    def test_codes_notes_et_sans_note_disjoints(self):
        assert CODES_NOTES & CODES_SANS_NOTE == set()

    def test_codes_notes_couverts(self):
        assert CODES_NOTES == {"1", "2", "3", "4"}

    def test_ordres_uniques(self):
        ordres = [info["ordre"] for info in NIVEAUX.values()]
        assert len(ordres) == len(set(ordres)), "Les ordres doivent être uniques"

    def test_referentiel_api_trie(self):
        api = referentiel_api()
        ordres = [item["ordre"] for item in api]
        assert ordres == sorted(ordres)

    def test_referentiel_api_contient_code(self):
        api = referentiel_api()
        codes = [item["code"] for item in api]
        for code in ("1", "2", "3", "4", "A", "D", "NE"):
            assert code in codes


# ── est_code_valide ────────────────────────────────────────────────────────────

class TestEstCodeValide:

    def test_codes_valides(self):
        for code in ("1", "2", "3", "4", "A", "D", "NE"):
            assert est_code_valide(code), f"{code} devrait être valide"

    def test_codes_invalides(self):
        for code in ("I", "F", "S", "TB", "E", "-", "5", "", "ne", "abs"):
            assert not est_code_valide(code), f"{code} ne devrait pas être valide"


# ── code_vers_libelle ──────────────────────────────────────────────────────────

class TestCodeVersLibelle:

    def test_libelles_connus(self):
        assert code_vers_libelle("1") == "Insuffisant"
        assert code_vers_libelle("2") == "À consolider"
        assert code_vers_libelle("3") == "Satisfaisant"
        assert code_vers_libelle("4") == "Très bien"
        assert code_vers_libelle("A") == "Absent"
        assert code_vers_libelle("D") == "Dispensé"
        assert code_vers_libelle("NE") == "Non évalué"

    def test_code_inconnu_leve_valuerror(self):
        with pytest.raises(ValueError):
            code_vers_libelle("X")

    def test_code_vide_leve_valuerror(self):
        with pytest.raises(ValueError):
            code_vers_libelle("")


# ── code_vers_libelle_court ────────────────────────────────────────────────────

class TestCodeVersLibelleCourt:

    def test_libelles_courts(self):
        assert code_vers_libelle_court("1")  == "I"
        assert code_vers_libelle_court("2")  == "F"
        assert code_vers_libelle_court("3")  == "A"
        assert code_vers_libelle_court("4")  == "E"
        assert code_vers_libelle_court("A")  == "Abs"
        assert code_vers_libelle_court("D")  == "Disp"
        assert code_vers_libelle_court("NE") == "NE"

    def test_code_inconnu_leve_valuerror(self):
        with pytest.raises(ValueError):
            code_vers_libelle_court("TB")


# ── code_vers_points ───────────────────────────────────────────────────────────

class TestCodeVersPoints:

    def test_points_numeriques(self):
        assert code_vers_points("1") == 4
        assert code_vers_points("2") == 10
        assert code_vers_points("3") == 16
        assert code_vers_points("4") == 20

    def test_points_none(self):
        assert code_vers_points("A")  is None
        assert code_vers_points("D")  is None
        assert code_vers_points("NE") is None

    def test_code_inconnu_leve_valuerror(self):
        with pytest.raises(ValueError):
            code_vers_points("F")


# ── migrer_ancien_code ─────────────────────────────────────────────────────────

class TestMigrerAncienCode:

    # Contexte csv_historique (I/F/A/E/NE/-)
    def test_csv_I_vers_1(self):
        assert migrer_ancien_code("I", "csv_historique") == "1"

    def test_csv_F_vers_2(self):
        assert migrer_ancien_code("F", "csv_historique") == "2"

    def test_csv_A_vers_3(self):
        # "A" dans CSV historique = Satisfaisant (ancien), pas Absent
        assert migrer_ancien_code("A", "csv_historique") == "3"

    def test_csv_E_vers_4(self):
        assert migrer_ancien_code("E", "csv_historique") == "4"

    def test_csv_NE_reste_NE(self):
        assert migrer_ancien_code("NE", "csv_historique") == "NE"

    def test_csv_tiret_vers_0(self):
        assert migrer_ancien_code("-", "csv_historique") == "0"

    # Contexte ancien_IFSATB
    def test_ancien_I_vers_1(self):
        assert migrer_ancien_code("I", "ancien_IFSATB") == "1"

    def test_ancien_F_vers_2(self):
        assert migrer_ancien_code("F", "ancien_IFSATB") == "2"

    def test_ancien_S_vers_3(self):
        assert migrer_ancien_code("S", "ancien_IFSATB") == "3"

    def test_ancien_TB_vers_4(self):
        assert migrer_ancien_code("TB", "ancien_IFSATB") == "4"

    def test_ancien_A_vers_3(self):
        assert migrer_ancien_code("A", "ancien_IFSATB") == "3"

    # Contexte nouveau (idempotent)
    def test_nouveau_codes_valides_idempotents(self):
        for code in ("1", "2", "3", "4", "D", "NE"):
            assert migrer_ancien_code(code, "nouveau") == code

    def test_nouveau_code_inconnu_leve_valuerror(self):
        with pytest.raises(ValueError):
            migrer_ancien_code("TB", "nouveau")

    # Robustesse
    def test_espace_autour_code(self):
        assert migrer_ancien_code(" F ", "csv_historique") == "2"

    def test_code_inconnu_leve_valuerror(self):
        with pytest.raises(ValueError):
            migrer_ancien_code("Z", "csv_historique")


# ── migrer_batch ───────────────────────────────────────────────────────────────

class TestMigrerBatch:

    def test_batch_typique(self):
        codes = {"01": "I", "02": "F", "03": "A", "04": "E", "11": "NE", "12": "-"}
        result = migrer_batch(codes, "csv_historique")
        assert result == {"01": "1", "02": "2", "03": "3", "04": "4", "11": "NE", "12": "0"}

    def test_batch_code_inconnu_marque_interrogation(self):
        result = migrer_batch({"01": "Z"}, "csv_historique")
        assert result["01"] == "?"

    def test_batch_vide(self):
        assert migrer_batch({}) == {}


# ── calculer_moyenne ───────────────────────────────────────────────────────────

class TestCalculerMoyenne:

    def test_moyenne_simple(self):
        assert calculer_moyenne(["1", "2", "3", "4"]) == (4 + 10 + 16 + 20) / 4

    def test_moyenne_ignore_sans_note(self):
        # A, D, NE ne comptent pas
        assert calculer_moyenne(["2", "A", "NE"]) == 10.0

    def test_moyenne_tous_sans_note(self):
        assert calculer_moyenne(["A", "NE", "D"]) is None

    def test_moyenne_liste_vide(self):
        assert calculer_moyenne([]) is None

    def test_moyenne_un_seul(self):
        assert calculer_moyenne(["3"]) == 16.0

    def test_moyenne_arrondie_deux_decimales(self):
        m = calculer_moyenne(["1", "2"])  # (4+10)/2 = 7.0
        assert m == 7.0


# ── deduire_niveau ─────────────────────────────────────────────────────────────

class TestDeduireNiveau:

    def _obj(self, is01=False, F=None, A=None, E=None):
        return {
            "is01": is01,
            "exercices": {
                "fondamental": F or [],
                "avancé":      A or [],
                "exploration": E or [],
            }
        }

    # Objectif 01 (cours)
    def test_obj01_aucun_cours(self):
        suivi = {"cours": []}
        assert deduire_niveau(suivi, self._obj(is01=True)) == "1"

    def test_obj01_notes_seulement(self):
        suivi = {"cours": [1]}
        assert deduire_niveau(suivi, self._obj(is01=True)) == "2"

    def test_obj01_fiches(self):
        suivi = {"cours": [1, 2]}
        assert deduire_niveau(suivi, self._obj(is01=True)) == "3"

    def test_obj01_oral(self):
        suivi = {"cours": [1, 2, 3]}
        assert deduire_niveau(suivi, self._obj(is01=True)) == "4"

    # Objectif sans exercice
    def test_aucun_exercice_retourne_NE(self):
        suivi = {}
        assert deduire_niveau(suivi, self._obj()) == "NE"

    # Objectif avec exercices
    def test_F_non_ok_retourne_1(self):
        suivi = {"F": [], "A": [], "E": []}
        assert deduire_niveau(suivi, self._obj(F=[1, 2])) == "1"

    def test_F_ok_A_non_ok_retourne_2(self):
        suivi = {"F": [1, 2], "A": [], "E": []}
        assert deduire_niveau(suivi, self._obj(F=[1, 2], A=[1])) == "2"

    def test_F_ok_A_ok_E_non_ok_retourne_3(self):
        suivi = {"F": [1, 2], "A": [1], "E": []}
        assert deduire_niveau(suivi, self._obj(F=[1, 2], A=[1], E=[1])) == "3"

    def test_tout_ok_retourne_4(self):
        suivi = {"F": [1, 2], "A": [1], "E": [1]}
        assert deduire_niveau(suivi, self._obj(F=[1, 2], A=[1], E=[1])) == "4"

    def test_serie_vide_ne_bloque_pas(self):
        # Si A est vide dans l'objectif, F ok et E ok → 4
        suivi = {"F": [1], "A": [], "E": [1]}
        assert deduire_niveau(suivi, self._obj(F=[1], A=[], E=[1])) == "4"

    def test_suivi_vide_avec_exercices_retourne_1(self):
        suivi = {}
        assert deduire_niveau(suivi, self._obj(F=[1, 2])) == "1"


# ── rang_creneau ───────────────────────────────────────────────────────────────

class TestRangCreneau:

    def test_objectifs_premier_creneau(self):
        for code in ("01", "02", "09"):
            assert rang_creneau(code) == 1, f"rang_creneau({code!r}) devrait être 1"

    def test_objectifs_deuxieme_creneau(self):
        for code in ("11", "12", "19"):
            assert rang_creneau(code) == 2, f"rang_creneau({code!r}) devrait être 2"

    def test_objectifs_troisieme_creneau(self):
        for code in ("21", "22", "29"):
            assert rang_creneau(code) == 3

    def test_objectif_zero_premier_creneau(self):
        # "00" → 0 // 10 + 1 = 1
        assert rang_creneau("00") == 1

    def test_code_non_numerique_retourne_1(self):
        assert rang_creneau("XX") == 1
        assert rang_creneau("") == 1
        assert rang_creneau(None) == 1


# ── grouper_objectifs_par_creneau ──────────────────────────────────────────────

class TestGrouperObjectifsParCreneau:

    def test_deux_creneaux(self):
        objectifs = [
            {"code": "01", "nom": "A"},
            {"code": "02", "nom": "B"},
            {"code": "11", "nom": "C"},
            {"code": "12", "nom": "D"},
        ]
        groupes = grouper_objectifs_par_creneau(objectifs)
        assert set(groupes.keys()) == {1, 2}
        assert len(groupes[1]) == 2
        assert len(groupes[2]) == 2

    def test_un_seul_creneau(self):
        objectifs = [{"code": "01"}, {"code": "02"}, {"code": "03"}]
        groupes = grouper_objectifs_par_creneau(objectifs)
        assert list(groupes.keys()) == [1]
        assert len(groupes[1]) == 3

    def test_liste_vide(self):
        assert grouper_objectifs_par_creneau([]) == {}

    def test_coherence_avec_rang_creneau(self):
        """Chaque objectif est dans le bon groupe."""
        objectifs = [{"code": "05"}, {"code": "14"}, {"code": "23"}]
        groupes = grouper_objectifs_par_creneau(objectifs)
        assert groupes[1][0]["code"] == "05"
        assert groupes[2][0]["code"] == "14"
        assert groupes[3][0]["code"] == "23"

    def test_csv_historique_4e3_s01(self):
        """Reproduit la structure réelle de 4e3/S01 : 7 objectifs sur 2 créneaux."""
        codes = ["01", "02", "03", "04", "11", "12", "13"]
        objectifs = [{"code": c} for c in codes]
        groupes = grouper_objectifs_par_creneau(objectifs)
        assert len(groupes[1]) == 4   # 01, 02, 03, 04
        assert len(groupes[2]) == 3   # 11, 12, 13
