"""
tests/test_referentiels.py — Tests du stockage et de l'import de référentiels.

Couvre :
- La création, la lecture, le verrouillage d'un référentiel en base.
- La détection d'équivalence par clé canonique normalisée (V1 B).
- L'import multi-classes qui partage un référentiel commun ou en crée
  de nouveaux selon que les contenus sont équivalents ou non.
"""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence.sqlite_store import SqliteStore


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    return SqliteStore(tmp_path / "data")


def _ref_basique(ref_id="N11_v2024", niveau="N11", version="2024",
                 etat="verrouille"):
    """Construit un référentiel de test minimal : 2 thèmes, 2 séquences, 3 objectifs."""
    return {
        "id":          ref_id,
        "niveau":      niveau,
        "version":     version,
        "description": "Test",
        "etat":        etat,
        "themes": [
            {"code": "A", "nom": "Nombres et Calculs", "couleur": "nombres"},
            {"code": "B", "nom": "Géométrie", "couleur": "geom"},
        ],
        "sequences": [
            {
                "code": "S01", "numero": 1, "nom": "Fractions",
                "theme_code": "A",
                "objectifs": [
                    {"code": "01", "nom": "Cours et méthodes", "fin_cycle": True,
                     "critere_f": "f", "critere_a": "a", "critere_e": "e"},
                    {"code": "02", "nom": "Simplifier des fractions", "fin_cycle": False,
                     "critere_f": "", "critere_a": "", "critere_e": ""},
                ],
            },
            {
                "code": "S03", "numero": 3, "nom": "Géométrie plane",
                "theme_code": "B",
                "objectifs": [
                    {"code": "01", "nom": "Cours", "fin_cycle": True},
                ],
            },
        ],
    }


# ── Tests CRUD ───────────────────────────────────────────────────────────────

class TestReferentielCRUD:

    def test_creer_et_lire(self, db):
        db.creer_referentiel(_ref_basique())
        r = db.lire_referentiel("N11_v2024")
        assert r is not None
        assert r["niveau"] == "N11"
        assert r["verrouille"] is True
        assert len(r["themes"]) == 2
        assert len(r["sequences"]) == 2
        # Vérifier qu'on retrouve bien les objectifs par séquence
        s01 = next(s for s in r["sequences"] if s["code"] == "S01")
        assert len(s01["objectifs"]) == 2
        assert s01["objectifs"][0]["code"] == "01"
        assert s01["objectifs"][0]["fin_cycle"] is True

    def test_lire_inexistant_retourne_none(self, db):
        assert db.lire_referentiel("N11_v9999") is None

    def test_lister_par_niveau(self, db):
        db.creer_referentiel(_ref_basique("N11_v2021", "N11", "2021"))
        db.creer_referentiel(_ref_basique("N11_v2024", "N11", "2024"))
        db.creer_referentiel(_ref_basique("N10_v2024", "N10", "2024"))
        n11 = db.lister_referentiels(niveau="N11")
        assert {r["id"] for r in n11} == {"N11_v2021", "N11_v2024"}
        tous = db.lister_referentiels()
        assert len(tous) == 3

    def test_verrouiller(self, db):
        """Compatibilité : verrouiller_referentiel passe l'état à 'verrouille'."""
        ref = _ref_basique(etat="valide")
        db.creer_referentiel(ref)
        assert db.lire_referentiel(ref["id"])["etat"] == "valide"
        assert db.lire_referentiel(ref["id"])["verrouille"] is False
        db.verrouiller_referentiel(ref["id"])
        assert db.lire_referentiel(ref["id"])["etat"] == "verrouille"
        assert db.lire_referentiel(ref["id"])["verrouille"] is True

    def test_verrouiller_idempotent(self, db):
        """verrouiller_referentiel ne fait rien si déjà verrouillé."""
        db.creer_referentiel(_ref_basique(etat="verrouille"))
        db.verrouiller_referentiel("N11_v2024")
        assert db.lire_referentiel("N11_v2024")["etat"] == "verrouille"

    def test_changer_etat(self, db):
        """Transitions d'état libres via changer_etat_referentiel."""
        db.creer_referentiel(_ref_basique(etat="en_cours"))
        assert db.lire_referentiel("N11_v2024")["etat"] == "en_cours"
        db.changer_etat_referentiel("N11_v2024", "valide")
        assert db.lire_referentiel("N11_v2024")["etat"] == "valide"
        db.changer_etat_referentiel("N11_v2024", "verrouille")
        assert db.lire_referentiel("N11_v2024")["etat"] == "verrouille"
        # Déverrouillage
        db.changer_etat_referentiel("N11_v2024", "valide")
        assert db.lire_referentiel("N11_v2024")["etat"] == "valide"

    def test_etat_invalide_leve(self, db):
        """Un état hors de l'énumération est refusé."""
        with pytest.raises(ValueError):
            db.creer_referentiel(_ref_basique(etat="zombie"))

    def test_etat_par_defaut_en_cours(self, db):
        """Si ni etat ni verrouille n'est fourni, le référentiel est 'en_cours'."""
        ref = _ref_basique()
        del ref["etat"]
        db.creer_referentiel(ref)
        assert db.lire_referentiel(ref["id"])["etat"] == "en_cours"

    def test_creer_id_deja_pris_leve(self, db):
        db.creer_referentiel(_ref_basique())
        with pytest.raises(Exception):
            db.creer_referentiel(_ref_basique())


# ── Tests de détection d'équivalence ─────────────────────────────────────────

class TestReferentielEquivalence:

    def test_meme_contenu_detecte(self, db):
        db.creer_referentiel(_ref_basique("N11_v2024"))
        # Contenu identique, variations superficielles
        ref2 = _ref_basique("N11_v2024b")
        eq = db.trouver_referentiel_equivalent(
            niveau="N11",
            themes=ref2["themes"],
            sequences=ref2["sequences"],
        )
        assert eq == "N11_v2024"

    def test_casse_accents_ponctuation_ignores(self, db):
        db.creer_referentiel(_ref_basique("N11_v2024"))
        # Mêmes objectifs mais avec variantes dans les noms
        themes = [
            {"code": "A", "nom": "NOMBRES ET CALCULS"},   # casse
            {"code": "B", "nom": "Geometrie."},           # accent supprimé + point
        ]
        sequences = [
            {"code": "S01", "nom": "fractions", "theme_code": "A",
             "objectifs": [
                 {"code": "01", "nom": "cours et méthodes."},
                 {"code": "02", "nom": "  Simplifier des Fractions  "},
             ]},
            {"code": "S03", "nom": "Géométrie Plane", "theme_code": "B",
             "objectifs": [{"code": "01", "nom": "Cours"}]},
        ]
        eq = db.trouver_referentiel_equivalent("N11", themes, sequences)
        assert eq == "N11_v2024"

    def test_objectif_ajoute_non_equivalent(self, db):
        db.creer_referentiel(_ref_basique("N11_v2024"))
        ref = _ref_basique("tmp")
        ref["sequences"][0]["objectifs"].append(
            {"code": "03", "nom": "Nouveau objectif"}
        )
        eq = db.trouver_referentiel_equivalent("N11", ref["themes"], ref["sequences"])
        assert eq is None

    def test_code_objectif_different_non_equivalent(self, db):
        """Si le code change (05 → 12) sans que le nom change : non équivalent."""
        db.creer_referentiel(_ref_basique("N11_v2024"))
        ref = _ref_basique("tmp")
        # Changer '02' en '12' pour le même nom
        ref["sequences"][0]["objectifs"][1]["code"] = "12"
        eq = db.trouver_referentiel_equivalent("N11", ref["themes"], ref["sequences"])
        assert eq is None, "Un changement de code d'objectif doit créer un nouveau référentiel"

    def test_niveau_different_non_equivalent(self, db):
        db.creer_referentiel(_ref_basique("N11_v2024", niveau="N11"))
        ref = _ref_basique("tmp", niveau="N10")
        eq = db.trouver_referentiel_equivalent("N10", ref["themes"], ref["sequences"])
        assert eq is None


# ── Tests du builder (extraction depuis SequencesDB) ────────────────────────

class TestBuilderMinimal:
    """Tests rapides sans arborescence réelle — juste la structure renvoyée."""

    def _creer_sdb(self, tmp_path, niveau="N11"):
        """Crée un SequencesDB/ minimal dans tmp_path avec 2 séquences."""
        tmp_path.mkdir(parents=True, exist_ok=True)
        sdb = tmp_path / "SequencesDB"
        sdb.mkdir()
        (sdb / "cycle4-themes.csv").write_text(
            "Code,Nom,CodeCouleur\n"
            "A,Nombres et Calculs,nombres\n"
            "B,Géométrie,geom\n",
            encoding="utf-8",
        )
        (sdb / "cycle4-sequences.csv").write_text(
            "Code,Numero,Nom,Theme\n"
            "S01,01,Fractions,A\n"
            "S03,03,Triangles,B\n",
            encoding="utf-8",
        )
        (sdb / f"{niveau}S01Objectifs.csv").write_text(
            "Code,FinCycle,Nom,MaitriseTB,MaitriseS,MaitriseF\n"
            "01,O,Cours et méthodes,tb,s,f\n"
            "02,N,Simplifier des fractions,tb,s,f\n",
            encoding="utf-8",
        )
        (sdb / f"{niveau}S03Objectifs.csv").write_text(
            "Code,FinCycle,Nom,MaitriseTB,MaitriseS,MaitriseF\n"
            "01,O,Cours,tb,s,f\n",
            encoding="utf-8",
        )
        return sdb

    def test_construire_referentiel(self, tmp_path):
        from importers.referentiel_builder import construire_referentiel
        sdb = self._creer_sdb(tmp_path)
        r = construire_referentiel(sdb, niveau="N11", version="2024")
        assert r["id"] == "N11_v2024"
        assert r["etat"] == "verrouille"
        assert len(r["themes"]) == 2
        assert len(r["sequences"]) == 2
        s01 = next(s for s in r["sequences"] if s["code"] == "S01")
        assert len(s01["objectifs"]) == 2
        assert s01["objectifs"][0]["nom"] == "Cours et méthodes"
        assert s01["objectifs"][0]["fin_cycle"] is True
        # Vérifier la correspondance MaitriseTB/S/F → critere_e/a/f
        assert s01["objectifs"][0]["critere_e"] == "tb"
        assert s01["objectifs"][0]["critere_a"] == "s"
        assert s01["objectifs"][0]["critere_f"] == "f"

    def test_retrouver_ou_creer_reutilise(self, db, tmp_path):
        """Deux classes du même niveau/année → un seul référentiel."""
        from importers.referentiel_builder import retrouver_ou_creer_referentiel
        sdb1 = self._creer_sdb(tmp_path / "c1")
        sdb2 = self._creer_sdb(tmp_path / "c2")
        rid1 = retrouver_ou_creer_referentiel(db, sdb1, "N11", "2024-2025")
        rid2 = retrouver_ou_creer_referentiel(db, sdb2, "N11", "2024-2025")
        assert rid1 == rid2
        # L'id doit utiliser l'année civile de rentrée, pas l'année scolaire complète
        assert rid1 == "N11_v2024"
        assert len(db.lister_referentiels()) == 1

    def test_retrouver_ou_creer_contenus_differents(self, db, tmp_path):
        """Deux SequencesDB avec contenus différents → 2 référentiels distincts."""
        from importers.referentiel_builder import retrouver_ou_creer_referentiel
        sdb1 = self._creer_sdb(tmp_path / "c1")
        sdb2 = self._creer_sdb(tmp_path / "c2")
        # Modifier un objectif dans sdb2 pour casser l'équivalence
        (sdb2 / "N11S01Objectifs.csv").write_text(
            "Code,FinCycle,Nom,MaitriseTB,MaitriseS,MaitriseF\n"
            "01,O,Cours différent,tb,s,f\n",  # nom et moins d'objectifs
            encoding="utf-8",
        )
        rid1 = retrouver_ou_creer_referentiel(db, sdb1, "N11", "2024-2025")
        # Même année → 2ème tentera le même id → collision → suffixe
        rid2 = retrouver_ou_creer_referentiel(db, sdb2, "N11", "2024-2025")
        assert rid1 == "N11_v2024"
        assert rid2 == "N11_v2024b"
        assert len(db.lister_referentiels()) == 2

    def test_annees_scolaires_distinctes_meme_contenu(self, db, tmp_path):
        """
        Même contenu importé depuis 2 années scolaires différentes → un seul
        référentiel (celui créé en premier, nommé d'après l'année de rentrée
        initiale). La 2ème année "réutilise" le référentiel existant.
        """
        from importers.referentiel_builder import retrouver_ou_creer_referentiel
        sdb_2023 = self._creer_sdb(tmp_path / "y2023")
        sdb_2024 = self._creer_sdb(tmp_path / "y2024")
        rid_2023 = retrouver_ou_creer_referentiel(db, sdb_2023, "N11", "2023-2024")
        rid_2024 = retrouver_ou_creer_referentiel(db, sdb_2024, "N11", "2024-2025")
        assert rid_2023 == rid_2024 == "N11_v2023"
        assert len(db.lister_referentiels()) == 1
