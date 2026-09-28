"""
tests/conftest.py — Fixtures pytest partagées entre tous les fichiers de test.

Principes :
- Chaque test reçoit un dossier data/ temporaire isolé (tmp_path de pytest).
- L'app Flask est créée via create_app(data_dir=...) pour injecter ce dossier.
- Aucun test ne touche aux fichiers réels de l'application.
"""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from persistence.sqlite_store import SqliteStore
from persistence.yaml_store import YamlStore
from persistence.csv_store  import CsvStore


# ── App Flask de test ─────────────────────────────────────────────────────────

@pytest.fixture
def data_dir(tmp_path):
    """Dossier data/ temporaire, pré-peuplé avec le minimum.

    Contenu :
      - Référentiel C04 minimal (sequences + themes) utilisé par CsvStore
      - SqliteStore créera automatiquement seqenseigne.db au premier accès
    """
    d = tmp_path / "data"
    d.mkdir()

    # Référentiel C04 minimal (3 séquences, 1 thème) — nécessaire pour CsvStore
    # et pour l'auto-import des cycles au démarrage de l'app (v0.10.2).
    # Note : la colonne Description est obligatoire pour cycle_import — on
    # peut la laisser vide mais elle doit exister.
    (d / "C04_sequences.csv").write_text(
        "Code,Numero,Nom,Theme\n"
        "S01,1,Représentations d'un nombre,A\n"
        "S02,2,Comparaison de nombres,A\n"
        "S03,3,Calcul numérique,A\n",
        encoding="utf-8",
    )
    (d / "C04_themes.csv").write_text(
        "Code,Nom,CodeCouleur,Description\n"
        "A,Nombres et Calculs,nombres,\n",
        encoding="utf-8",
    )

    # v0.13.1 — Référentiel des niveaux scolaires. Le SqliteStore amorce
    # `param_niveaux` depuis ce CSV au premier démarrage. Sans ce fichier,
    # la table reste vide et les services qui appellent
    # `services.param_niveaux.lire_cycle()` lèvent NiveauInconnu →
    # 500 dans les routes au lieu des codes HTTP attendus.
    (d / "param_niveaux.csv").write_text(
        "Code,CodeCycle,AnneeDansCycle,NomCourt,NomLong\n"
        "N07,C03,anneeun,CM1,cours moyen (1ère année)\n"
        "N08,C03,anneedeux,CM2,cours moyen (2nde année)\n"
        "N09,C03,anneetrois,6ème,sixième\n"
        "N10,C04,anneeun,5ème,cinquième\n"
        "N11,C04,anneedeux,4ème,quatrième\n"
        "N12,C04,anneetrois,3ème,troisième\n",
        encoding="utf-8",
    )

    return d


@pytest.fixture
def app(data_dir):
    """App Flask configurée avec le dossier data/ temporaire."""
    application = create_app(data_dir=data_dir)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    """Client de test Flask."""
    return app.test_client()


# ── Stores isolés (sans Flask) ────────────────────────────────────────────────

@pytest.fixture
def sqlite_store(data_dir):
    return SqliteStore(data_dir)


# Alias : 'store' désigne le SqliteStore (historiquement fixture paramétrée
# JsonStore/SqliteStore, simplifiée après suppression de JsonStore).
@pytest.fixture
def store(data_dir):
    return SqliteStore(data_dir)


@pytest.fixture
def yaml_store(data_dir):
    return YamlStore(data_dir)


@pytest.fixture
def csv_store(data_dir):
    return CsvStore(data_dir)


# ── Données de test réutilisables ─────────────────────────────────────────────

@pytest.fixture
def classes_avec_eleves(data_dir):
    """Pré-peuple data/ avec une classe et deux élèves, via SqliteStore."""
    data = {
        "classes": [{
            "id": "5E1",
            "nom": "5e1",
            "niveau": "N10",
            "annee": "2024-2025",
            "etablissement": "Collège Test",
            "eleves": [
                {"id": "e01", "nom": "DUPONT", "prenom": "Alice"},
                {"id": "e02", "nom": "MARTIN", "prenom": "Bob"},
            ],
            "versions_actives": {},
            "sequences_verouillees": [],
        }]
    }
    db = SqliteStore(data_dir)
    db.ecrire_classes(data)
    return data_dir


@pytest.fixture
def yaml_n10_minimal(data_dir):
    """Écrit un YAML N10 minimal avec 2 séquences."""
    import yaml
    payload = {
        "niveau": "N10", "cycle": "C04",
        "sequences": [
            {
                "code": "S01", "numero": 1,
                "nom": "Représentations d'un nombre", "theme": "A",
                "objectifs": [
                    {
                        "code": "02", "nom": "Utiliser les fractions",
                        "fin_cycle": False,
                        "criteres": {"2": "crit F", "3": "crit A", "4": "crit E"},
                        "exercices": {
                            "fondamental": [1, 2],
                            "avancé": [1],
                            "exploration": [],
                        },
                    }
                ],
            },
            {
                "code": "S02", "numero": 2,
                "nom": "Comparaison de nombres", "theme": "A",
                "objectifs": [
                    {
                        "code": "02", "nom": "Comparer des rationnels",
                        "fin_cycle": False,
                        "criteres": {"2": "", "3": "", "4": ""},
                        "exercices": {
                            "fondamental": [1],
                            "avancé": [],
                            "exploration": [],
                        },
                    }
                ],
            },
        ],
    }
    p = data_dir / "N10_sequences.yaml"
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, allow_unicode=True, sort_keys=False)
    return data_dir
