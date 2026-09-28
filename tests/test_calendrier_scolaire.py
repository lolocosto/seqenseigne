"""
tests/test_calendrier_scolaire.py — Tests du service calendrier scolaire.

Les appels API externes sont mockés. Pour les tests d'intégration (vraie
API), voir test_calendrier_live.py (non présent par défaut, à créer
manuellement pour des vérifications ponctuelles).
"""

import json
import pytest
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence.sqlite_store import SqliteStore
from services import calendrier_scolaire as cal


@pytest.fixture
def store(tmp_path):
    """SqliteStore vide."""
    return SqliteStore(tmp_path)


class TestZoneAcademie:
    """Mapping académie → zone de vacances."""

    def test_rennes_est_zone_b(self):
        assert cal.zone_academie("Rennes") == "B"

    def test_paris_est_zone_c(self):
        assert cal.zone_academie("Paris") == "C"

    def test_lyon_est_zone_a(self):
        assert cal.zone_academie("Lyon") == "A"

    def test_academie_inconnue_retourne_none(self):
        assert cal.zone_academie("Académie inexistante") is None

    def test_academie_vide_retourne_none(self):
        assert cal.zone_academie("") is None
        assert cal.zone_academie(None) is None

    def test_toutes_les_academies_metropolitaines_ont_une_zone(self):
        """Toutes les académies principales doivent avoir un mapping."""
        principales = [
            "Rennes", "Paris", "Lyon", "Versailles", "Créteil",
            "Nantes", "Bordeaux", "Toulouse", "Lille",
            "Aix-Marseille", "Strasbourg", "Montpellier",
        ]
        for a in principales:
            assert cal.zone_academie(a) in ("A", "B", "C"), f"{a} sans zone"


class TestVacancesCache:
    """Cache des appels API vacances en base."""

    def test_vacances_met_en_cache_premier_appel(self, store):
        """Un seul appel réseau si on demande deux fois les mêmes vacances."""
        fake_data = {
            "results": [
                {
                    "description":    "Vacances de la Toussaint",
                    "start_date":     "2021-10-23T00:00:00+00:00",
                    "end_date":       "2021-11-08T00:00:00+00:00",
                    "zones":          "Zone B",
                    "location":       "Rennes",
                    "annee_scolaire": "2021-2022",
                }
            ]
        }

        with patch("services.calendrier_scolaire.urllib.request.urlopen") as mock_url:
            # Premier appel : API sollicitée
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(fake_data).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            r1 = cal.vacances("2021-2022", "B", store)
            # 1 vraie période (Toussaint) + 1 synthétique (Vacances d'été)
            assert len(r1) == 2
            assert r1[0]["description"] == "Vacances de la Toussaint"
            assert r1[0]["start_date"] == "2021-10-23"  # coupé à la date
            assert r1[1]["description"] == "Vacances d'été"
            assert r1[1].get("synthetique") is True
            assert mock_url.call_count == 1

            # Deuxième appel : servi depuis le cache, pas d'appel réseau
            r2 = cal.vacances("2021-2022", "B", store)
            assert r2 == r1
            assert mock_url.call_count == 1

    def test_force_refresh_rappelle_api(self, store):
        fake_data = {"results": []}
        with patch("services.calendrier_scolaire.urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(fake_data).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            cal.vacances("2021-2022", "B", store)
            cal.vacances("2021-2022", "B", store, force_refresh=True)
            assert mock_url.call_count == 2


class TestJoursFeries:
    """Cache et agrégation des jours fériés."""

    def test_jours_feries_cachent_en_base(self, store):
        fake = {"2024-01-01": "Jour de l'an", "2024-05-01": "Fête du Travail"}
        with patch("services.calendrier_scolaire.urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(fake).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            r1 = cal.jours_feries(2024, store)
            r2 = cal.jours_feries(2024, store)
            assert r1 == r2 == fake
            assert mock_url.call_count == 1

    def test_jours_feries_annee_scolaire_agrege_deux_annees(self, store):
        """2021-2022 doit combiner les jours fériés 2021 + 2022, filtré sept→août."""
        feries_2021 = {
            "2021-07-14": "Fête Nationale",   # avant septembre, exclu
            "2021-11-01": "Toussaint",         # dans 2021-2022, inclus
            "2021-12-25": "Noël",
        }
        feries_2022 = {
            "2022-01-01": "Jour de l'an",     # dans 2021-2022
            "2022-05-01": "Fête du Travail",
            "2022-09-01": "Inventé",          # après août, exclu
        }

        def fake_urlopen(req, **_):
            url = req.full_url
            resp = MagicMock()
            resp.__enter__.return_value = resp
            if "2021.json" in url:
                resp.read.return_value = json.dumps(feries_2021).encode()
            elif "2022.json" in url:
                resp.read.return_value = json.dumps(feries_2022).encode()
            else:
                raise AssertionError(f"URL inattendue : {url}")
            return resp

        with patch("services.calendrier_scolaire.urllib.request.urlopen",
                   side_effect=fake_urlopen):
            result = cal.jours_feries_annee_scolaire("2021-2022", store)

        assert "2021-07-14" not in result
        assert "2021-11-01" in result
        assert "2021-12-25" in result
        assert "2022-01-01" in result
        assert "2022-05-01" in result
        assert "2022-09-01" not in result

    def test_jours_feries_annee_scolaire_tolere_une_api_indisponible(self, store):
        """Si une des deux années d'API échoue, retourne les jours de l'autre."""
        feries_2022 = {"2022-01-01": "Jour de l'an"}

        def fake_urlopen(req, **_):
            url = req.full_url
            if "2021.json" in url:
                raise ConnectionError("API down")
            resp = MagicMock()
            resp.__enter__.return_value = resp
            resp.read.return_value = json.dumps(feries_2022).encode()
            return resp

        with patch("services.calendrier_scolaire.urllib.request.urlopen",
                   side_effect=fake_urlopen):
            result = cal.jours_feries_annee_scolaire("2021-2022", store)

        # L'année 2021 a échoué mais 2022 a réussi → on récupère au moins ça
        assert result == {"2022-01-01": "Jour de l'an"}


class TestVacancesEteSynthetisees:
    """L'API ne renvoie pas les grandes vacances ni le pont d'Ascension — on les synthétise."""

    def test_ete_utilise_table_officielle_zone_B(self, store):
        """Zone B 2025-2026 : les vacances d'été commencent officiellement
        le samedi 4 juillet 2026 (arrêté du 7 décembre 2022).
        On doit utiliser cette date, pas un calcul depuis end_date."""
        fake = {"results": [
            {"description":"Vacances de la Toussaint", "start_date":"2025-10-18T00:00:00+00:00",
             "end_date":"2025-11-03T00:00:00+00:00", "zones":"Zone B",
             "location":"Rennes", "annee_scolaire":"2025-2026"},
            {"description":"Vacances de Printemps",   "start_date":"2026-04-11T00:00:00+00:00",
             "end_date":"2026-04-27T00:00:00+00:00", "zones":"Zone B",
             "location":"Rennes", "annee_scolaire":"2025-2026"},
        ]}
        with patch("services.calendrier_scolaire.urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(fake).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            r = cal.vacances("2025-2026", "B", store)

        # Toussaint + Printemps + Pont Ascension + Été
        assert len(r) == 4
        ete = [v for v in r if "été" in v["description"].lower()][0]
        assert ete["description"] == "Vacances d'été"
        assert ete["start_date"]  == "2026-07-04"  # officiel, pas 28 avril
        assert ete["end_date"]    == "2026-08-31"
        assert ete["zones"]       == "Zone B"
        assert ete["synthetique"] is True

    def test_pont_ascension_synthetise(self, store):
        """Le pont de l'Ascension est ajouté pour Zone B 2025-2026."""
        fake = {"results": []}
        with patch("services.calendrier_scolaire.urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(fake).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            r = cal.vacances("2025-2026", "B", store)

        pont = [v for v in r if "ascension" in v["description"].lower()]
        assert len(pont) == 1
        assert pont[0]["start_date"] == "2026-05-14"  # jeudi Ascension
        assert pont[0]["end_date"]   == "2026-05-18"  # lundi reprise

    def test_pas_de_doublon_si_ete_deja_present(self, store):
        """Si l'API renvoie (hypothétiquement) une entrée 'été', on ne
        synthétise pas par-dessus."""
        fake = {"results": [
            {"description":"Vacances d'Été", "start_date":"2026-07-04T00:00:00+00:00",
             "end_date":"2026-08-31T00:00:00+00:00", "zones":"Zone B",
             "location":"Rennes", "annee_scolaire":"2025-2026"},
        ]}
        with patch("services.calendrier_scolaire.urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(fake).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            r = cal.vacances("2025-2026", "B", store)

        # Été de l'API + Pont Ascension synthétisé (pas de doublon été)
        etes = [v for v in r if "été" in v["description"].lower()]
        assert len(etes) == 1
        assert etes[0].get("synthetique") is not True

    def test_fallback_annee_inconnue(self, store):
        """Si l'année n'est pas dans la table VACANCES_ETE_DEBUT,
        fallback sur le 1er samedi ≥ 4 juillet."""
        fake = {"results": []}
        with patch("services.calendrier_scolaire.urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(fake).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            # 2030-2031 n'est pas dans la table
            r = cal.vacances("2030-2031", "B", store)

        ete = [v for v in r if "été" in v["description"].lower()][0]
        # Le 4 juillet 2031 est un vendredi → 1er samedi = 5 juillet
        assert ete["start_date"] == "2031-07-05"
        assert ete["end_date"]   == "2031-08-31"


class TestConversionHeureParis:
    """
    L'API Éducation renvoie les dates avec l'heure UTC 22:00 (hiver) ou 23:00,
    qui correspondent à minuit heure de Paris le lendemain. Sans conversion,
    les dates étaient décalées d'un jour vers le passé.
    """

    def test_22h_utc_devient_lendemain(self):
        from services.calendrier_scolaire import _iso_date
        # 13 mai 22h UTC = 14 mai 00h Paris (heure d'été)
        assert _iso_date("2026-05-13T22:00:00+00:00") == "2026-05-14"

    def test_23h_utc_hiver_devient_lendemain(self):
        from services.calendrier_scolaire import _iso_date
        # 2 nov 23h UTC = 3 nov 00h Paris (heure d'hiver)
        assert _iso_date("2025-11-02T23:00:00+00:00") == "2025-11-03"

    def test_date_simple_preservee(self):
        from services.calendrier_scolaire import _iso_date
        # Quand on nous passe déjà une date simple (cas de nos tables dures),
        # on ne la modifie pas
        assert _iso_date("2026-07-04") == "2026-07-04"

    def test_none_preserve(self):
        from services.calendrier_scolaire import _iso_date
        assert _iso_date(None) is None
        assert _iso_date("") is None
