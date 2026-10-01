"""tests/test_annees_scolaires.py — Tests du service + route annees_scolaires."""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services import annees_scolaires as svc


# ── Helpers ────────────────────────────────────────────────────────────────────

@pytest.fixture
def annees_file(tmp_path):
    """Crée un JSON d'années scolaires minimal dans tmp_path et retourne le chemin."""
    p = tmp_path / "annees.json"
    p.write_text(json.dumps({
        "annee_courante": "2025-2026",
        "annees_scolaires": [
            {"code": "2022-2023", "libelle": "2022-2023", "archive": True},
            {"code": "2023-2024", "libelle": "2023-2024", "archive": True},
            {"code": "2024-2025", "libelle": "2024-2025", "archive": True},
            {"code": "2025-2026", "libelle": "2025-2026", "archive": False},
            {"code": "2026-2027", "libelle": "2026-2027", "archive": False},
        ],
    }), encoding="utf-8")
    return p


# ── Service ────────────────────────────────────────────────────────────────────

def test_courante_retourne_le_code_du_json(annees_file):
    assert svc.courante(annees_file) == "2025-2026"


def test_courante_repli_sur_la_date_si_fichier_absent(tmp_path):
    """v0.41.0 — Sans fichier, `courante` se replie sur l'année scolaire
    calculée depuis la date du jour (comportement voulu : une valeur vide
    laissait l'UI sans présélection). Le test ne code plus l'année en dur."""
    assert svc.courante(tmp_path / "inexistant.json") == svc.annee_scolaire_de_date()


@pytest.mark.parametrize("jour, attendu", [
    ("2026-09-01", "2026-2027"),   # rentrée : nouvelle année
    ("2026-12-31", "2026-2027"),
    ("2027-01-01", "2026-2027"),
    ("2027-08-31", "2026-2027"),   # fin août : encore l'année précédente
    ("2027-09-01", "2027-2028"),
])
def test_annee_scolaire_de_date_bascule_en_septembre(jour, attendu):
    from datetime import date
    assert svc.annee_scolaire_de_date(date.fromisoformat(jour)) == attendu


def test_lister_met_les_actives_avant_les_archivees(annees_file):
    codes = [a["code"] for a in svc.lister(annees_file)]
    # Actives en premier (par code croissant), puis archivées (plus récentes d'abord)
    assert codes == [
        "2025-2026", "2026-2027",                # actives
        "2024-2025", "2023-2024", "2022-2023",   # archivées, plus récent d'abord
    ]


def test_lister_vide_si_fichier_absent(tmp_path):
    assert svc.lister(tmp_path / "inexistant.json") == []


def test_existe_vrai_pour_annee_active(annees_file):
    assert svc.existe("2025-2026", annees_file) is True


def test_existe_vrai_pour_annee_archivee(annees_file):
    assert svc.existe("2022-2023", annees_file) is True


def test_existe_faux_pour_annee_inconnue(annees_file):
    assert svc.existe("2099-2100", annees_file) is False


def test_lister_structure_complete(annees_file):
    """Chaque entrée retourne au moins code, libelle, archive."""
    for a in svc.lister(annees_file):
        assert "code" in a
        assert "libelle" in a
        assert "archive" in a


# ── Route ──────────────────────────────────────────────────────────────────────

def test_route_annees_scolaires_retourne_json(client):
    """La route existe et retourne la structure attendue."""
    r = client.get("/api/annees-scolaires")
    assert r.status_code == 200
    data = r.get_json()
    assert "annee_courante" in data
    assert "annees_scolaires" in data
    assert isinstance(data["annees_scolaires"], list)


def test_route_annees_scolaires_charge_le_fichier_livre(client):
    """La route charge le JSON livré dans appli/config/.

    v0.41.0 — On compare au contenu du fichier livré au lieu de coder une
    année en dur : le fichier est mis à jour à chaque rentrée, le test ne doit
    pas se périmer avec lui."""
    livre = json.loads((Path(__file__).resolve().parent.parent / "config" /
                        "annees_scolaires.json").read_text(encoding="utf-8"))
    r = client.get("/api/annees-scolaires")
    data = r.get_json()
    codes = [a["code"] for a in data["annees_scolaires"]]
    assert data["annee_courante"] == livre["annee_courante"]
    assert data["annee_courante"] in codes
    assert sorted(codes) == sorted(a["code"] for a in livre["annees_scolaires"])
