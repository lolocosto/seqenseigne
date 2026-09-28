"""
tests/test_etablissements.py — Tests du service établissements.

Couvre CRUD, unicité par nom, et validation par UAI (mockée).
"""

import json
import pytest
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence.sqlite_store import SqliteStore
from services import etablissements as svc


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path)


class TestCreer:

    def test_creer_avec_nom_minimal(self, store):
        etab = svc.creer(store, nom="Collège Victor Hugo")
        assert etab["nom"] == "Collège Victor Hugo"
        assert etab["id"].startswith("et_")
        assert etab["etat"] == "propose"
        assert etab["academie"] == ""

    def test_creer_avec_meta(self, store):
        etab = svc.creer(store, nom="Collège Les Hautes Ourmes",
                         academie="Rennes", ville="Rennes")
        assert etab["academie"] == "Rennes"
        assert etab["ville"] == "Rennes"
        assert etab["etat"] == "propose"

    def test_creer_meme_nom_retourne_existant(self, store):
        """La création d'un établissement existant renvoie l'ancien (pas d'écrasement)."""
        e1 = svc.creer(store, nom="Collège X", academie="Rennes")
        e2 = svc.creer(store, nom="Collège X", academie="Paris")
        assert e2["id"] == e1["id"]
        assert e2["academie"] == "Rennes"  # pas écrasé


class TestLister:

    def test_lister_vide(self, store):
        assert svc.lister(store) == []

    def test_lister_tri_par_nom(self, store):
        svc.creer(store, nom="Collège B")
        svc.creer(store, nom="Collège A")
        svc.creer(store, nom="Collège C")
        noms = [e["nom"] for e in svc.lister(store)]
        assert noms == ["Collège A", "Collège B", "Collège C"]


class TestMettreAJour:

    def test_mettre_a_jour_academie(self, store):
        e = svc.creer(store, nom="Collège X")
        e2 = svc.mettre_a_jour(store, e["id"], {"academie": "Rennes"})
        assert e2["academie"] == "Rennes"
        assert e2["etat"] == "propose"  # l'état ne change pas sans validation

    def test_mettre_a_jour_introuvable(self, store):
        assert svc.mettre_a_jour(store, "et_inexistant", {"academie": "X"}) is None

    def test_mettre_a_jour_champs_multiples(self, store):
        e = svc.creer(store, nom="Collège X")
        e2 = svc.mettre_a_jour(store, e["id"], {
            "academie": "Rennes",
            "ville":    "Rennes",
            "adresse":  "1 rue de la paix",
        })
        assert e2["academie"] == "Rennes"
        assert e2["ville"] == "Rennes"
        assert e2["adresse"] == "1 rue de la paix"


class TestValiderParUAI:

    def _mock_api(self, annuaire_data):
        """Crée un mock pour urllib.request.urlopen retournant l'annuaire."""
        def fake_urlopen(req, **_):
            resp = MagicMock()
            resp.__enter__.return_value = resp
            resp.read.return_value = json.dumps({"results": [annuaire_data]}
                                                if annuaire_data else
                                                {"results": []}).encode()
            return resp
        return fake_urlopen

    def test_valider_par_uai_met_a_jour_champs(self, store):
        e = svc.creer(store, nom="nom approximatif")
        annuaire = {
            "identifiant_de_l_etablissement": "0351234A",
            "nom_etablissement":  "COLLEGE LES HAUTES OURMES",
            "libelle_academie":   "Rennes",
            "nom_commune":        "RENNES",
            "adresse_1":          "6 Rue du Bourbonnais",
        }
        with patch("services.etablissements.urllib.request.urlopen",
                   side_effect=self._mock_api(annuaire)):
            e2 = svc.valider_par_uai(store, e["id"], "0351234A")

        assert e2["etat"]     == "valide"
        assert e2["uai"]      == "0351234A"
        assert e2["nom"]      == "COLLEGE LES HAUTES OURMES"  # corrigé depuis l'annuaire
        assert e2["academie"] == "Rennes"
        assert e2["ville"]    == "RENNES"

    def test_valider_uai_inconnu_leve_erreur(self, store):
        e = svc.creer(store, nom="X")
        with patch("services.etablissements.urllib.request.urlopen",
                   side_effect=self._mock_api(None)):
            with pytest.raises(ValueError, match="introuvable"):
                svc.valider_par_uai(store, e["id"], "0000000A")

        # L'établissement reste à 'propose'
        e2 = svc.lire(store, e["id"])
        assert e2["etat"] == "propose"

    def test_rechercher_uai_met_en_cache(self, store):
        """Un deuxième appel pour le même UAI n'atteint pas l'API."""
        annuaire = {
            "identifiant_de_l_etablissement": "0351234A",
            "nom_etablissement": "X",
            "libelle_academie":  "Rennes",
        }
        with patch("services.etablissements.urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.read.return_value = json.dumps({"results": [annuaire]}).encode()
            mock_url.return_value = mock_resp

            svc.rechercher_uai(store, "0351234A")
            svc.rechercher_uai(store, "0351234A")
            assert mock_url.call_count == 1


class TestFusionner:
    """Tests de la fusion d'établissements."""

    def test_fusion_simple_migre_classes_et_progressions(self, store):
        """Cas nominal : source non validée, pas de conflit."""
        # Deux établissements, même nom approximatif
        src = svc.creer(store, nom="Collège des Hautes Ourmes")
        cib = svc.creer(store, nom="Collège Les Hautes Ourmes", academie="Rennes")

        # Classe liée à source + progression liée à source
        from persistence.ids import nouveau_id_classe
        store.ecrire_classes({"classes": [{
            "id":    nouveau_id_classe(),
            "nom":   "4e6",
            "niveau": "N11",
            "annee": "2021-2022",
            "etablissement": "Collège des Hautes Ourmes",
            "eleves": [],
        }]})
        store.ecrire_progression({
            "niveau":        "N11",
            "annee":         "2021-2022",
            "etablissement": "Collège des Hautes Ourmes",
            "creneaux":      [],
        })

        result = svc.fusionner(store, src["id"], cib["id"])

        assert result["id"]   == cib["id"]
        assert result["nom"]  == "Collège Les Hautes Ourmes"  # cible conservée
        assert result["classes_migrees"]      == 1
        assert result["progressions_migrees"] == 1

        # Source supprimée
        assert svc.lire(store, src["id"]) is None
        # Tous pointent sur cible
        c = store.lire_classes()["classes"][0]
        assert c["etablissement"] == "Collège Les Hautes Ourmes"

    def test_fusion_refuse_si_source_validee(self, store):
        """Interdiction absolue : ne jamais supprimer un établissement validé."""
        src = svc.creer(store, nom="Collège X")
        # Marquer source comme validée manuellement
        src["etat"] = "valide"
        store.ecrire_etablissement(src)

        cib = svc.creer(store, nom="Collège Y")

        with pytest.raises(svc.ConflitFusion) as exc:
            svc.fusionner(store, src["id"], cib["id"])
        assert exc.value.code == "source_validee"

        # Rien n'a bougé
        assert svc.lire(store, src["id"]) is not None
        assert svc.lire(store, cib["id"]) is not None

    def test_fusion_autorisee_quand_cible_validee(self, store):
        """Fusion dans le sens propose → validé est bienvenue."""
        src = svc.creer(store, nom="Collège des Hautes Ourmes")  # propose
        cib = svc.creer(store, nom="Collège Les Hautes Ourmes")
        cib["etat"] = "valide"
        cib["academie"] = "Rennes"
        store.ecrire_etablissement(cib)

        result = svc.fusionner(store, src["id"], cib["id"])
        assert result["etat"]     == "valide"
        assert result["academie"] == "Rennes"
        assert svc.lire(store, src["id"]) is None

    def test_fusion_refuse_si_conflit_progression(self, store):
        """Conflit : même (niveau, annee) sur source ET cible."""
        src = svc.creer(store, nom="Collège des Hautes Ourmes")
        cib = svc.creer(store, nom="Collège Les Hautes Ourmes")

        # Les 2 ont une progression N11 2021-2022 (conflit)
        store.ecrire_progression({
            "niveau":        "N11",
            "annee":         "2021-2022",
            "etablissement": "Collège des Hautes Ourmes",
            "creneaux":      [],
        })
        store.ecrire_progression({
            "niveau":        "N11",
            "annee":         "2021-2022",
            "etablissement": "Collège Les Hautes Ourmes",
            "creneaux":      [],
        })

        with pytest.raises(svc.ConflitFusion) as exc:
            svc.fusionner(store, src["id"], cib["id"])
        assert exc.value.code == "conflit_progression"
        # Détails utiles côté UI
        assert len(exc.value.details["conflits"]) == 1

        # Rien n'a été supprimé
        assert svc.lire(store, src["id"]) is not None

    def test_fusion_source_et_cible_identiques_refuse(self, store):
        e = svc.creer(store, nom="X")
        with pytest.raises(ValueError, match="identiques"):
            svc.fusionner(store, e["id"], e["id"])


class TestValiderDetecteDoublon:
    """Quand la validation UAI remonte un nom déjà porté par un autre établissement."""

    def _mock_annuaire(self, data):
        def fake(req, **_):
            r = MagicMock()
            r.__enter__.return_value = r
            r.read.return_value = json.dumps({"results": [data] if data else []}).encode()
            return r
        return fake

    def test_validation_leve_doublon_si_nom_officiel_deja_pris(self, store):
        """Collège 'des' Hautes Ourmes validé → l'annuaire dit 'Les' → un autre
        établissement porte déjà ce nom → refus avec DoublonEtablissement."""
        # Établissement déjà bien nommé (sans validation)
        cible = svc.creer(store, nom="Collège Les Hautes Ourmes")
        # Établissement avec coquille
        source = svc.creer(store, nom="Collège des Hautes Ourmes")

        annuaire = {
            "identifiant_de_l_etablissement": "0351234A",
            "nom_etablissement":  "Collège Les Hautes Ourmes",
            "libelle_academie":   "Rennes",
        }

        with patch("services.etablissements.urllib.request.urlopen",
                   side_effect=self._mock_annuaire(annuaire)):
            with pytest.raises(svc.DoublonEtablissement) as exc:
                svc.valider_par_uai(store, source["id"], "0351234A")

        assert exc.value.etab_cible_id == cible["id"]
        assert exc.value.nom == "Collège Les Hautes Ourmes"

        # source reste à 'propose'
        src2 = svc.lire(store, source["id"])
        assert src2["etat"] == "propose"
        assert src2["nom"]  == "Collège des Hautes Ourmes"  # pas renommé

    def test_validation_sur_soi_meme_autorisee(self, store):
        """Si le nom officiel est déjà celui de l'établissement qui se valide,
        pas de doublon, ça passe."""
        e = svc.creer(store, nom="Collège Les Hautes Ourmes")

        annuaire = {
            "identifiant_de_l_etablissement": "0351234A",
            "nom_etablissement":  "Collège Les Hautes Ourmes",
            "libelle_academie":   "Rennes",
        }

        with patch("services.etablissements.urllib.request.urlopen",
                   side_effect=self._mock_annuaire(annuaire)):
            result = svc.valider_par_uai(store, e["id"], "0351234A")

        assert result["etat"]     == "valide"
        assert result["academie"] == "Rennes"
