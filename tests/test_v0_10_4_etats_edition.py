"""tests/test_v0_10_4_etats_edition.py — v0.10.4

Tests pour la gestion de l'état d'édition des atomes.
"""

from __future__ import annotations
import sqlite3
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Schéma de test minimal ───────────────────────────────────────────────────

_SCHEMA_TEST = """
CREATE TABLE etats_edition (
    code TEXT PRIMARY KEY, nom TEXT, ordre INTEGER, est_final INTEGER
);
INSERT INTO etats_edition VALUES
    ('en_cours', 'En cours', 10, 0),
    ('valide',   'Validé',   20, 1);

-- v0.13.6.8.2 : ajout de mtime sur toutes les tables atomes pour aligner
-- avec le mécanisme unifié changer_etat_atome qui met à jour mtime à
-- chaque transition (utile pour le futur figeage des référentiels).
-- Ajout aussi de fiches_resume et cartes_automatisme (5 types d'atomes
-- maintenant dans TABLES_ATOMES).
CREATE TABLE notions (
    id TEXT PRIMARY KEY, titre TEXT,
    etat_code TEXT NOT NULL DEFAULT 'en_cours',
    mtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE methodes (
    id TEXT PRIMARY KEY, titre TEXT,
    etat_code TEXT NOT NULL DEFAULT 'en_cours',
    mtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE exercices (
    id TEXT PRIMARY KEY, titre TEXT,
    etat_code TEXT NOT NULL DEFAULT 'en_cours',
    mtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE fiches_resume (
    id TEXT PRIMARY KEY, titre TEXT,
    etat_code TEXT NOT NULL DEFAULT 'en_cours',
    mtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE cartes_automatisme (
    id TEXT PRIMARY KEY, titre TEXT,
    etat_code TEXT NOT NULL DEFAULT 'en_cours',
    mtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA_TEST)
    yield c
    c.close()


@pytest.fixture
def base(conn):
    # v0.13.6.8.2 : inclut maintenant fiche_resume et carte (TABLES_ATOMES
    # étendu pour supporter le mécanisme unifié de la carte).
    conn.executescript("""
        INSERT INTO notions (id, titre) VALUES
            ('n1', 'Notion 1'), ('n2', 'Notion 2');
        INSERT INTO methodes (id, titre) VALUES ('m1', 'Méthode 1');
        INSERT INTO exercices (id, titre) VALUES ('e1', 'Exo 1');
        INSERT INTO fiches_resume (id, titre) VALUES ('f1', 'Fiche 1');
        INSERT INTO cartes_automatisme (id, titre) VALUES ('c1', 'Carte 1');
    """)
    conn.commit()
    return conn


# ── Tests unitaires service ─────────────────────────────────────────────────

from services.etats_edition import (
    lister_etats,
    lire_etat_atome,
    changer_etat_atome,
    compter_atomes_par_etat,
    TypeAtomeInvalide,
    AtomeIntrouvable,
    EtatInconnu,
    TABLES_ATOMES,
)


class TestListerEtats:
    def test_liste_seed(self, base):
        rep = lister_etats(base)
        assert len(rep) == 2
        codes = [e["code"] for e in rep]
        assert codes == ["en_cours", "valide"]
        # est_final converti en bool
        assert rep[0]["est_final"] is False
        assert rep[1]["est_final"] is True


class TestLireEtatAtome:
    def test_defaut_en_cours(self, base):
        assert lire_etat_atome(base, "notion", "n1") == "en_cours"

    def test_apres_changement(self, base):
        base.execute(
            "UPDATE notions SET etat_code = 'valide' WHERE id = 'n1'"
        )
        assert lire_etat_atome(base, "notion", "n1") == "valide"

    def test_atome_inconnu_404(self, base):
        with pytest.raises(AtomeIntrouvable):
            lire_etat_atome(base, "notion", "n_inexistant")

    def test_type_invalide_400(self, base):
        with pytest.raises(TypeAtomeInvalide):
            lire_etat_atome(base, "objectif", "ob1")  # 'objectif' pas dans TABLES_ATOMES


class TestChangerEtatAtome:
    def test_validation_simple(self, base):
        rep = changer_etat_atome(base, "notion", "n1", "valide")
        assert rep["etat_code"] == "valide"
        assert lire_etat_atome(base, "notion", "n1") == "valide"

    def test_invalidation(self, base):
        base.execute(
            "UPDATE notions SET etat_code = 'valide' WHERE id = 'n1'"
        )
        rep = changer_etat_atome(base, "notion", "n1", "en_cours")
        assert rep["etat_code"] == "en_cours"

    def test_etat_inconnu_404(self, base):
        with pytest.raises(EtatInconnu):
            changer_etat_atome(base, "notion", "n1", "etat_fantome")

    def test_atome_inconnu_404(self, base):
        with pytest.raises(AtomeIntrouvable):
            changer_etat_atome(base, "notion", "n_pasla", "valide")

    def test_type_invalide(self, base):
        with pytest.raises(TypeAtomeInvalide):
            changer_etat_atome(base, "thème", "t1", "valide")

    def test_meme_etat_que_courant_ok(self, base):
        """Pas de garde sur la transition (Q2-N) : passer 'en_cours' → 'en_cours'
        est OK, c'est même un no-op effectif."""
        rep = changer_etat_atome(base, "notion", "n1", "en_cours")
        assert rep["etat_code"] == "en_cours"

    def test_tous_les_types_atomes_supportes(self, base):
        """v0.13.6.8.2 : 5 types supportés (notion, méthode, exercice,
        fiche_resume, carte). On teste juste que le mécanisme accepte
        les 5 types.

        v0.13.6.16 : tous les types ont désormais un hook de validation
        pédagogique au passage en `valide` (avant : seule la carte).
        Comme la fixture crée des atomes minimaux dont le schéma de
        test n'a pas toutes les colonnes (pas d'enonce/corrige sur
        exercice, pas de sections sur fiche), on ne teste plus le
        passage en `valide` ici (couvert par tests spécifiques par
        type). On utilise une transition neutre (en_cours → en_cours)
        qui ne déclenche aucun hook.
        """
        # Idempotent : passe par en_cours → en_cours pour chaque type.
        changer_etat_atome(base, "notion",       "n1", "en_cours")
        changer_etat_atome(base, "methode",      "m1", "en_cours")
        changer_etat_atome(base, "exercice",     "e1", "en_cours")
        changer_etat_atome(base, "fiche_resume", "f1", "en_cours")
        changer_etat_atome(base, "carte",        "c1", "en_cours")
        # Vérification : les 5 types ont bien été acceptés par le
        # mécanisme (pas d'exception levée). L'état reste en_cours
        # pour tous (transition neutre).
        assert lire_etat_atome(base, "notion",       "n1") == "en_cours"
        assert lire_etat_atome(base, "methode",      "m1") == "en_cours"
        assert lire_etat_atome(base, "exercice",     "e1") == "en_cours"
        assert lire_etat_atome(base, "fiche_resume", "f1") == "en_cours"
        assert lire_etat_atome(base, "carte",        "c1") == "en_cours"


class TestCompterParEtat:
    def test_recap_initial(self, base):
        rep = compter_atomes_par_etat(base)
        # v0.13.6.8.2 : 5 types maintenant (ajout de fiche_resume et carte)
        assert "notion" in rep
        assert "methode" in rep
        assert "exercice" in rep
        assert "fiche_resume" in rep
        assert "carte" in rep
        assert rep["notion"] == {"en_cours": 2}
        assert rep["methode"] == {"en_cours": 1}
        assert rep["exercice"] == {"en_cours": 1}
        assert rep["fiche_resume"] == {"en_cours": 1}
        assert rep["carte"] == {"en_cours": 1}

    def test_recap_apres_validations(self, base):
        changer_etat_atome(base, "notion", "n1", "valide")
        rep = compter_atomes_par_etat(base)
        assert rep["notion"] == {"en_cours": 1, "valide": 1}


class TestPersistanceViaStore:
    """Vérifie que la modification d'état d'une notion via les méthodes
    haut-niveau du SqliteStore est bien préservée à travers
    ecrire_notions/ecrire_methodes/ecrire_exercices.

    Ce test garantit qu'on n'introduit pas de régression : les routes
    /api/notions, /api/methodes, /api/exercices passent par ces
    méthodes lors de chaque PUT/POST/DELETE. Sans la préservation de
    etat_code, l'état serait remis à 'en_cours' à chaque sauvegarde.
    """

    @pytest.fixture
    def store(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        # Conftest minimal pour SqliteStore
        (d / "C04_themes.csv").write_text(
            "Code,Nom,CodeCouleur,Description\nA,X,nombres,\n",
            encoding="utf-8",
        )
        (d / "C04_sequences.csv").write_text(
            "Code,Numero,Nom,Theme\nS01,1,X,A\n",
            encoding="utf-8",
        )
        from persistence.sqlite_store import SqliteStore
        return SqliteStore(d)

    def test_etat_notion_preserve_via_ecrire(self, store):
        """Après changement d'état + ré-écriture par ecrire_notions, l'état
        ne doit pas être perdu."""
        store.ecrire_notions([
            {"id": "n_test", "titre": "T1", "corps": "", "ordreExRem": True,
             "niveau": "N10", "sequence": "S01", "sections": []},
        ])
        # Changer l'état directement en SQL (simule la route PATCH /etat)
        with sqlite3.connect(store.db_path) as c:
            c.execute("UPDATE notions SET etat_code='valide' WHERE id='n_test'")
            c.commit()
        # Simuler une sauvegarde de la notion (ecrire_notions = full rewrite)
        notions = store.lire_notions()
        # L'état doit être lu correctement
        n_test = next(n for n in notions if n["id"] == "n_test")
        assert n_test["etat_code"] == "valide"
        # Ré-écrire SANS passer etat_code dans le payload → doit être préservé
        for n in notions:
            n.pop("etat_code", None)  # simule un client legacy
        store.ecrire_notions(notions)
        notions2 = store.lire_notions()
        n_test2 = next(n for n in notions2 if n["id"] == "n_test")
        assert n_test2["etat_code"] == "valide", \
            "L'état d'édition aurait dû être préservé à travers ecrire_notions"

    def test_etat_methode_preserve_via_ecrire(self, store):
        store.ecrire_methodes([
            {"id": "m_test", "titre": "M1", "corps": "", "ordreExRem": True,
             "finCycle": "N", "niveau": "N10", "sequence": "S01",
             "num_methode": 1, "num_objectif": "02",
             "fichier": "test.tex", "notions": [], "sections": [],
             "criteres": {"F": "", "A": "", "E": ""}},
        ])
        with sqlite3.connect(store.db_path) as c:
            c.execute("UPDATE methodes SET etat_code='valide' WHERE id='m_test'")
            c.commit()
        methodes = store.lire_methodes()
        m_test = next(m for m in methodes if m["id"] == "m_test")
        assert m_test["etat_code"] == "valide"
        # Ré-écrire sans etat_code
        for m in methodes:
            m.pop("etat_code", None)
        store.ecrire_methodes(methodes)
        methodes2 = store.lire_methodes()
        m_test2 = next(m for m in methodes2 if m["id"] == "m_test")
        assert m_test2["etat_code"] == "valide"


# ── Tests routes Flask ───────────────────────────────────────────────────────


class TestRoutes:
    @pytest.fixture
    def populated(self, app, sqlite_store):
        """Insère 3 atomes via SQL direct."""
        with sqlite3.connect(sqlite_store.db_path) as c:
            c.executescript("""
                INSERT INTO notions (id, titre) VALUES ('n_R', 'NR');
                INSERT INTO methodes (id, titre) VALUES ('m_R', 'MR');
                INSERT INTO exercices (id, serie, titre) VALUES
                    ('e_R', 'fond', 'ER');
            """)
            c.commit()
        return {"n": "n_R", "m": "m_R", "e": "e_R"}

    def test_get_etats_edition(self, client):
        rep = client.get("/api/etats-edition")
        assert rep.status_code == 200
        data = rep.get_json()
        assert "etats" in data
        codes = [e["code"] for e in data["etats"]]
        assert "en_cours" in codes
        assert "valide" in codes

    def test_get_etat_atome(self, client, populated):
        rep = client.get(f"/api/atomes/notion/{populated['n']}/etat")
        assert rep.status_code == 200
        data = rep.get_json()
        assert data["etat_code"] == "en_cours"

    def test_patch_etat_atome(self, client, populated):
        rep = client.patch(
            f"/api/atomes/notion/{populated['n']}/etat",
            json={"etat_code": "valide"},
        )
        assert rep.status_code == 200
        # Vérifier persistance
        rep2 = client.get(f"/api/atomes/notion/{populated['n']}/etat")
        assert rep2.get_json()["etat_code"] == "valide"

    def test_patch_etat_inconnu_404(self, client, populated):
        rep = client.patch(
            f"/api/atomes/notion/{populated['n']}/etat",
            json={"etat_code": "fantome"},
        )
        assert rep.status_code == 404
        assert rep.get_json()["code"] == "etat_inconnu"

    def test_patch_atome_inconnu_404(self, client):
        rep = client.patch(
            "/api/atomes/notion/n_pasla/etat",
            json={"etat_code": "valide"},
        )
        assert rep.status_code == 404
        assert rep.get_json()["code"] == "atome_introuvable"

    def test_patch_type_invalide_400(self, client, populated):
        rep = client.patch(
            f"/api/atomes/objectif/{populated['n']}/etat",
            json={"etat_code": "valide"},
        )
        assert rep.status_code == 400
        assert rep.get_json()["code"] == "type_atome_invalide"

    def test_patch_sans_payload_400(self, client, populated):
        rep = client.patch(f"/api/atomes/notion/{populated['n']}/etat", json={})
        assert rep.status_code == 400
        assert rep.get_json()["code"] == "champ_manquant"

    def test_recap_par_etat(self, client, populated):
        # Valider la notion
        client.patch(
            f"/api/atomes/notion/{populated['n']}/etat",
            json={"etat_code": "valide"},
        )
        rep = client.get("/api/etats-edition/recap")
        assert rep.status_code == 200
        data = rep.get_json()
        assert "recap" in data
        assert data["recap"]["notion"] == {"valide": 1}
        assert data["recap"]["methode"] == {"en_cours": 1}
        assert data["recap"]["exercice"] == {"en_cours": 1}


# ── Tests d'intégration via /api/notions etc. ────────────────────────────────


class TestIntegrationApiAtomes:
    """v0.10.4 : la route /api/notions et consorts doivent retourner
    etat_code dans leur réponse, et préserver l'état lors d'un PUT."""

    def test_get_notions_inclut_etat(self, client):
        # Créer une notion via POST
        rep = client.post("/api/notions", json={
            "titre": "Test",
            "corps": "",
            "ordreExRem": True,
            "niveau": "N10",
            "sequence": "S01",
            "sections": [],
        })
        assert rep.status_code == 201
        data = rep.get_json()
        notion_id = data["id"]
        # GET /api/notions
        # v0.13.6.15 — niveau/sequence obligatoires.
        rep2 = client.get("/api/notions?niveau=N10&sequence=S01")
        assert rep2.status_code == 200
        notions = rep2.get_json()
        n = next((x for x in notions if x["id"] == notion_id), None)
        assert n is not None
        assert n["etat_code"] == "en_cours"  # défaut

    def test_modif_notion_validee_refusee(self, client):
        # v0.16.4 — CHANGEMENT DE RÈGLE. Avant, modifier une notion validée
        # était autorisé et préservait l'état ('test_put_notion_preserve_etat',
        # Q2-N). Désormais, un item validé est en LECTURE SEULE : toute
        # modification de contenu est refusée (409 'item_verrouille') tant
        # qu'on ne l'a pas repassé en cours. Ce test encode la nouvelle règle.
        rep = client.post("/api/notions", json={
            "titre": "Test",
            "corps": "",
            "ordreExRem": True,
            "niveau": "N10",
            "sequence": "S01",
            "sections": [],
        })
        notion_id = rep.get_json()["id"]
        client.patch(
            f"/api/atomes/notion/{notion_id}/etat",
            json={"etat_code": "valide"},
        )
        # Tenter de modifier le titre d'une notion validée → 409.
        rep_mod = client.patch(f"/api/notions/{notion_id}", json={
            "titre": "Modifié",
            "corps": "",
            "ordreExRem": True,
            "niveau": "N10",
            "sequence": "S01",
            "sections": [],
        })
        assert rep_mod.status_code == 409
        assert rep_mod.get_json().get("code") == "item_verrouille"
        # L'état reste 'valide' et le titre est INCHANGÉ (modif rejetée).
        rep_etat = client.get(f"/api/atomes/notion/{notion_id}/etat")
        assert rep_etat.get_json()["etat_code"] == "valide"

    def test_modif_notion_apres_devalidation_ok(self, client):
        # v0.16.4 — Le chemin normal : repasser en cours, PUIS modifier.
        rep = client.post("/api/notions", json={
            "titre": "Test", "corps": "", "ordreExRem": True,
            "niveau": "N10", "sequence": "S01", "sections": [],
        })
        notion_id = rep.get_json()["id"]
        client.patch(f"/api/atomes/notion/{notion_id}/etat",
                     json={"etat_code": "valide"})
        # Repasser en cours.
        client.patch(f"/api/atomes/notion/{notion_id}/etat",
                     json={"etat_code": "en_cours"})
        # Maintenant la modification passe.
        rep_mod = client.patch(f"/api/notions/{notion_id}", json={
            "titre": "Modifié", "corps": "", "ordreExRem": True,
            "niveau": "N10", "sequence": "S01", "sections": [],
        })
        assert rep_mod.status_code == 200
