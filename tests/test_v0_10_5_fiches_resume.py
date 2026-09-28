"""tests/test_v0_10_5_fiches_resume.py — v0.10.5

Tests pour les fiches de résumé : service + routes + helper d'aplatissement.
"""

from __future__ import annotations
import sqlite3
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Schéma de test minimal ───────────────────────────────────────────────────
#
# On réplique le strict minimum pour les tests unitaires : objectifs,
# sequences_par_niveau, sequence_parties, fiches_resume, objectif_fiches,
# atome_sections / atome_section_items (réutilisés pour les sections
# de fiche), notions et methodes (pour le helper d'aplatissement).

_SCHEMA_TEST = """
CREATE TABLE sequences_par_niveau (
    id TEXT PRIMARY KEY, niveau TEXT, sequence_code TEXT
);
CREATE TABLE sequence_parties (
    id TEXT PRIMARY KEY,
    sequence_par_niveau_id TEXT REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    numero INTEGER
);
CREATE TABLE objectifs (
    id TEXT PRIMARY KEY,
    partie_id TEXT REFERENCES sequence_parties(id) ON DELETE CASCADE,
    code TEXT,
    nom TEXT
);
CREATE TABLE notions (
    id TEXT PRIMARY KEY, titre TEXT, corps TEXT,
    niveau TEXT, sequence TEXT, num_connaissance TEXT,
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE methodes (
    id TEXT PRIMARY KEY, titre TEXT, corps TEXT,
    niveau TEXT, sequence TEXT, num_methode INTEGER, num_objectif TEXT,
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE atome_sections (
    id TEXT PRIMARY KEY, entite_type TEXT, entite_id TEXT,
    titre TEXT, ordre INTEGER
);
CREATE TABLE atome_section_items (
    id TEXT PRIMARY KEY,
    section_id TEXT REFERENCES atome_sections(id) ON DELETE CASCADE,
    ordre INTEGER, corps TEXT
);
CREATE TABLE fiches_resume (
    id TEXT PRIMARY KEY, titre TEXT,
    objectif_id TEXT REFERENCES objectifs(id) ON DELETE SET NULL,
    num_fiche INTEGER,
    niveau TEXT, sequence TEXT, fichier TEXT,
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE objectif_fiches (
    objectif_id TEXT REFERENCES objectifs(id) ON DELETE CASCADE,
    fiche_id TEXT REFERENCES fiches_resume(id) ON DELETE CASCADE,
    ordre INTEGER,
    PRIMARY KEY (objectif_id, fiche_id)
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(_SCHEMA_TEST)
    yield c
    c.close()


@pytest.fixture
def base(conn):
    """Base de test minimaliste : 1 séquence-niveau, 2 parties, 4 objectifs,
    1 notion + sections, 1 méthode."""
    conn.executescript("""
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
            ('sn1', 'N10', 'S01');
        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
            ('pt1', 'sn1', 1),
            ('pt2', 'sn1', 2);
        INSERT INTO objectifs (id, partie_id, code, nom) VALUES
            ('ob01', 'pt1', '01', 'Connaître X'),
            ('ob02', 'pt1', '02', 'Calculer X'),
            ('ob11', 'pt2', '11', 'Connaître Y'),
            ('ob12', 'pt2', '12', 'Calculer Y');
        INSERT INTO notions (id, titre, corps, niveau, sequence, num_connaissance) VALUES
            ('n1', 'Définition X', 'X est un truc.',
             'N10', 'S01', '01');
        INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre) VALUES
            ('s1', 'notion', 'n1', 'Exemples', 0),
            ('s2', 'notion', 'n1', 'Remarque', 1);
        INSERT INTO atome_section_items (id, section_id, ordre, corps) VALUES
            ('i1', 's1', 0, 'Soit x = 5...'),
            ('i2', 's2', 0, 'X est unique.');
        INSERT INTO methodes (id, titre, corps, niveau, sequence, num_objectif) VALUES
            ('m1', 'Calculer X', 'Pour calculer X, on procède...',
             'N10', 'S01', '02');
    """)
    conn.commit()
    return conn


# ── Imports du service à tester ─────────────────────────────────────────────

from services.fiches_resume import (
    creer_fiche, lire_fiche, lister_fiches, modifier_fiche, supprimer_fiche,
    attacher_fiche_a_objectif, detacher_fiche_de_objectif,
    lister_fiches_attachees, lister_fiches_de_partie,
    aplatir_atome_pour_initialisation,
    FicheIntrouvable, ObjectifIntrouvable, ObjectifDejaLie,
    FicheDejaPresente,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. CRUD fiche
# ═══════════════════════════════════════════════════════════════════════════


class TestCreerFiche:
    def test_creation_basique(self, base):
        f = creer_fiche(base, objectif_id='ob02', titre='Fiche calcul X')
        assert f["titre"] == 'Fiche calcul X'
        assert f["objectif_id"] == 'ob02'
        assert f["num_fiche"] == 1  # premier de la séquence
        assert f["niveau"] == 'N10'
        assert f["sequence"] == 'S01'
        assert f["etat_code"] == 'en_cours'
        # Une zone vide créée par défaut
        assert len(f["sections"]) == 1

    def test_numerotation_automatique(self, base):
        f1 = creer_fiche(base, objectif_id='ob02', titre='F1')
        f2 = creer_fiche(base, objectif_id='ob12', titre='F2')
        assert f1["num_fiche"] == 1
        assert f2["num_fiche"] == 2

    def test_objectif_inconnu(self, base):
        with pytest.raises(ObjectifIntrouvable):
            creer_fiche(base, objectif_id='ob_inconnu', titre='X')

    def test_cardinalite_1_1(self, base):
        creer_fiche(base, objectif_id='ob02', titre='F1')
        with pytest.raises(ObjectifDejaLie):
            creer_fiche(base, objectif_id='ob02', titre='F2')

    def test_sections_personnalisees(self, base):
        secs = [
            {"titre": "Définition", "items": ["X est..."]},
            {"titre": "Méthode",    "items": ["Pour calculer..."]},
        ]
        f = creer_fiche(base, objectif_id='ob02', titre='F', sections=secs)
        assert len(f["sections"]) == 2
        assert f["sections"][0]["titre"] == "Définition"
        assert f["sections"][1]["titre"] == "Méthode"

    # v0.13.6.14 — Chantier D : creer_fiche sans objectif_id ────────────────

    def test_creation_orpheline_sans_objectif(self, base):
        """v0.13.6.14 : creer_fiche accepte objectif_id=None à condition
        que niveau et sequence soient fournis explicitement. La fiche est
        créée orpheline ; son rattachement à un objectif se fera ensuite
        depuis l'atelier d'assemblage de séquence."""
        f = creer_fiche(base, niveau='N10', sequence='S01',
                        titre='Fiche orpheline')
        assert f["objectif_id"] is None
        assert f["niveau"] == 'N10'
        assert f["sequence"] == 'S01'
        assert f["num_fiche"] == 1
        assert f["etat_code"] == 'en_cours'

    def test_creation_orpheline_sans_niveau_leve(self, base):
        """v0.13.6.14 : sans objectif_id, niveau est obligatoire."""
        with pytest.raises(ValueError):
            creer_fiche(base, sequence='S01', titre='X')

    def test_creation_orpheline_sans_sequence_leve(self, base):
        """v0.13.6.14 : sans objectif_id, sequence est obligatoire."""
        with pytest.raises(ValueError):
            creer_fiche(base, niveau='N10', titre='X')

    def test_creation_orpheline_puis_rattachement(self, base):
        """v0.13.6.14 : fiche créée orpheline puis rattachée à un
        objectif via modifier_fiche. Le scénario nominal du chantier D."""
        from services.fiches_resume import modifier_fiche
        # Étape 1 : créer la fiche orpheline
        f = creer_fiche(base, niveau='N10', sequence='S01',
                        titre='Calcul de proportion')
        assert f["objectif_id"] is None
        # Étape 2 : rattacher à un objectif depuis l'assemblage (PUT
        # objectif_id sur la fiche existante).
        f2 = modifier_fiche(base, f["id"], objectif_id='ob02')
        assert f2["objectif_id"] == 'ob02'
        # Le niveau/sequence restent ceux d'origine (cohérents avec ob02)
        assert f2["niveau"] == 'N10'
        assert f2["sequence"] == 'S01'
        # num_fiche : même séquence, donc inchangé
        assert f2["num_fiche"] == f["num_fiche"]

    def test_numerotation_orpheline_partage_meme_compteur(self, base):
        """v0.13.6.14 : les fiches orphelines partagent la même séquence
        de num_fiche que les fiches rattachées (compteur par niveau+seq)."""
        f1 = creer_fiche(base, objectif_id='ob02', titre='F1')
        f2 = creer_fiche(base, niveau='N10', sequence='S01',
                        titre='F2 orpheline')
        assert f1["num_fiche"] == 1
        assert f2["num_fiche"] == 2


class TestLireFiche:
    def test_lecture_apres_creation(self, base):
        f = creer_fiche(base, objectif_id='ob02', titre='F')
        rep = lire_fiche(base, f["id"])
        assert rep["id"] == f["id"]
        assert rep["titre"] == 'F'

    def test_introuvable(self, base):
        with pytest.raises(FicheIntrouvable):
            lire_fiche(base, 'fiche_inconnue')


class TestModifierFiche:
    def test_changer_titre(self, base):
        f = creer_fiche(base, objectif_id='ob02', titre='Avant')
        rep = modifier_fiche(base, f["id"], titre='Après')
        assert rep["titre"] == 'Après'

    def test_etat_preserve_apres_modification(self, base):
        """Q2-N : modifier le contenu ne fait PAS repasser l'état à 'en_cours'."""
        f = creer_fiche(base, objectif_id='ob02', titre='F')
        # Valider la fiche
        base.execute(
            "UPDATE fiches_resume SET etat_code = 'valide' WHERE id = ?",
            (f["id"],),
        )
        # Modifier le titre
        rep = modifier_fiche(base, f["id"], titre='Modifié')
        assert rep["etat_code"] == 'valide', \
            "L'état doit être préservé à travers modifier_fiche"

    def test_changer_objectif_meme_sequence(self, base):
        f = creer_fiche(base, objectif_id='ob02', titre='F')
        # Bascule sur ob12 (différente partie, même séquence)
        rep = modifier_fiche(base, f["id"], objectif_id='ob12')
        assert rep["objectif_id"] == 'ob12'
        # Pas de renumérotation (même séquence)
        assert rep["num_fiche"] == f["num_fiche"]

    def test_changer_objectif_deja_lie_refuse(self, base):
        creer_fiche(base, objectif_id='ob02', titre='F1')
        f2 = creer_fiche(base, objectif_id='ob12', titre='F2')
        with pytest.raises(ObjectifDejaLie):
            modifier_fiche(base, f2["id"], objectif_id='ob02')


class TestSupprimerFiche:
    def test_suppression_avec_sections(self, base):
        f = creer_fiche(base, objectif_id='ob02', titre='F',
                        sections=[{"titre": "T", "items": ["x"]}])
        supprimer_fiche(base, f["id"])
        # Plus en BDD
        with pytest.raises(FicheIntrouvable):
            lire_fiche(base, f["id"])
        # Sections nettoyées
        n = base.execute(
            "SELECT COUNT(*) AS n FROM atome_sections "
            "WHERE entite_type='fiche_resume' AND entite_id=?",
            (f["id"],),
        ).fetchone()["n"]
        assert n == 0

    def test_introuvable(self, base):
        with pytest.raises(FicheIntrouvable):
            supprimer_fiche(base, 'fiche_inconnue')


class TestListerFiches:
    def test_liste_vide(self, base):
        assert lister_fiches(base) == []

    def test_filtre_par_niveau_sequence(self, base):
        creer_fiche(base, objectif_id='ob02', titre='F1')
        creer_fiche(base, objectif_id='ob12', titre='F2')
        rep = lister_fiches(base, niveau='N10', sequence='S01')
        assert len(rep) == 2
        # Vérifier les champs
        f0 = rep[0]
        assert "objectif_code" in f0
        assert "objectif_nom" in f0


# ═══════════════════════════════════════════════════════════════════════════
# 2. Liens fiche ↔ objectif (drop sur Connaître)
# ═══════════════════════════════════════════════════════════════════════════


class TestAttacherFiche:
    def test_attache_simple(self, base):
        f = creer_fiche(base, objectif_id='ob02', titre='F')
        # Attacher au Connaître ob01
        rep = attacher_fiche_a_objectif(
            base, objectif_id='ob01', fiche_id=f["id"],
        )
        assert rep["objectif_id"] == 'ob01'
        assert rep["fiche_id"] == f["id"]
        assert rep["ordre"] == 0

    def test_doublon_refuse(self, base):
        f = creer_fiche(base, objectif_id='ob02', titre='F')
        attacher_fiche_a_objectif(base, objectif_id='ob01', fiche_id=f["id"])
        with pytest.raises(FicheDejaPresente):
            attacher_fiche_a_objectif(
                base, objectif_id='ob01', fiche_id=f["id"],
            )

    def test_objectif_inconnu(self, base):
        f = creer_fiche(base, objectif_id='ob02', titre='F')
        with pytest.raises(ObjectifIntrouvable):
            attacher_fiche_a_objectif(
                base, objectif_id='inconnu', fiche_id=f["id"],
            )

    def test_fiche_inconnue(self, base):
        with pytest.raises(FicheIntrouvable):
            attacher_fiche_a_objectif(
                base, objectif_id='ob01', fiche_id='inconnue',
            )

    def test_ordre_incrementiel(self, base):
        f1 = creer_fiche(base, objectif_id='ob02', titre='F1')
        f2 = creer_fiche(base, objectif_id='ob12', titre='F2')
        r1 = attacher_fiche_a_objectif(base, objectif_id='ob01', fiche_id=f1["id"])
        r2 = attacher_fiche_a_objectif(base, objectif_id='ob01', fiche_id=f2["id"])
        assert r1["ordre"] == 0
        assert r2["ordre"] == 1


class TestDetacherFiche:
    def test_detacher(self, base):
        f = creer_fiche(base, objectif_id='ob02', titre='F')
        attacher_fiche_a_objectif(base, objectif_id='ob01', fiche_id=f["id"])
        detacher_fiche_de_objectif(base, objectif_id='ob01', fiche_id=f["id"])
        rep = lister_fiches_attachees(base, 'ob01')
        assert rep == []

    def test_no_op_si_pas_attache(self, base):
        # Ne lève pas
        detacher_fiche_de_objectif(
            base, objectif_id='ob01', fiche_id='fiche_pas_la',
        )


class TestListerFichesDePartie:
    """Le cas typique : on ouvre l'obj Connaître ob01 (partie pt1), on
    veut voir les fiches des autres obj de la partie pt1."""

    def test_voit_fiches_de_la_partie(self, base):
        # Une fiche sur ob02 (même partie pt1)
        f1 = creer_fiche(base, objectif_id='ob02', titre='F1')
        # Une fiche sur ob12 (partie pt2 — ne doit pas remonter)
        creer_fiche(base, objectif_id='ob12', titre='F2')
        rep = lister_fiches_de_partie(base, 'pt1')
        assert len(rep) == 1
        assert rep[0]["id"] == f1["id"]
        assert rep[0]["objectif_code"] == '02'

    def test_partie_sans_fiches(self, base):
        rep = lister_fiches_de_partie(base, 'pt1')
        assert rep == []


# ═══════════════════════════════════════════════════════════════════════════
# 3. Aplatissement « hors Exemples » (helper QE.2 / QF)
# ═══════════════════════════════════════════════════════════════════════════


class TestAplatirAtome:
    def test_notion_exclut_section_exemples(self, base):
        rep = aplatir_atome_pour_initialisation(
            base, type_atome='notion', atome_id='n1',
        )
        # Le corps est inclus
        assert "X est un truc" in rep
        # La section "Exemples" est exclue
        assert "Soit x = 5" not in rep
        # La section "Remarque" est incluse
        assert "X est unique" in rep
        assert "Remarque" in rep  # titre conservé

    def test_methode_sans_sections(self, base):
        rep = aplatir_atome_pour_initialisation(
            base, type_atome='methode', atome_id='m1',
        )
        assert "Pour calculer X" in rep

    def test_atome_inexistant_renvoie_vide(self, base):
        rep = aplatir_atome_pour_initialisation(
            base, type_atome='notion', atome_id='n_inconnue',
        )
        assert rep == ""

    def test_filtre_case_insensitive(self, base):
        # Ajouter des sections avec variantes : "EXEMPLE", "ex.", "Ex"
        base.executescript("""
            INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre) VALUES
                ('s_a', 'notion', 'n1', 'EXEMPLE', 2),
                ('s_b', 'notion', 'n1', 'ex.',     3),
                ('s_c', 'notion', 'n1', 'Ex',      4);
            INSERT INTO atome_section_items (id, section_id, ordre, corps) VALUES
                ('it_a', 's_a', 0, 'AAA'),
                ('it_b', 's_b', 0, 'BBB'),
                ('it_c', 's_c', 0, 'CCC');
        """)
        base.commit()
        rep = aplatir_atome_pour_initialisation(
            base, type_atome='notion', atome_id='n1',
        )
        # Aucun de AAA/BBB/CCC ne doit apparaître
        assert "AAA" not in rep
        assert "BBB" not in rep
        assert "CCC" not in rep
        # Mais "Remarque" toujours là
        assert "X est unique" in rep

    def test_inclut_remarques_demonstrations(self, base):
        """Seul "Exemples" est exclu — "Démonstration", "Remarque",
        "Conséquence" passent."""
        base.executescript("""
            INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre) VALUES
                ('s_d', 'methode', 'm1', 'Démonstration', 0),
                ('s_e', 'methode', 'm1', 'Conséquence',   1);
            INSERT INTO atome_section_items (id, section_id, ordre, corps) VALUES
                ('it_d', 's_d', 0, 'Preuve : ...'),
                ('it_e', 's_e', 0, 'Donc Y suit X.');
        """)
        base.commit()
        rep = aplatir_atome_pour_initialisation(
            base, type_atome='methode', atome_id='m1',
        )
        assert "Preuve" in rep
        assert "Donc Y suit X" in rep

    def test_type_atome_invalide_leve(self, base):
        from services.fiches_resume import FicheErreur
        with pytest.raises(FicheErreur):
            aplatir_atome_pour_initialisation(
                base, type_atome='exercice', atome_id='e1',
            )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Routes Flask (intégration)
# ═══════════════════════════════════════════════════════════════════════════


class TestRoutes:
    """Tests d'intégration via le client Flask du conftest global.

    Pas de fixture base ici : le conftest.py crée son propre store ; on
    crée les objectifs directement via SQL.
    """

    @pytest.fixture
    def setup_objectifs(self, sqlite_store):
        """Crée 2 objectifs v2 dans la BDD globale du test."""
        with sqlite3.connect(sqlite_store.db_path) as c:
            c.executescript("""
                INSERT INTO sequences_par_niveau (id, niveau, sequence_code)
                VALUES ('sn_R', 'N11', 'S01');
                INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                VALUES ('pt_R', 'sn_R', 1);
                INSERT INTO objectifs (id, partie_id, code, nom)
                VALUES
                    ('ob_R01', 'pt_R', '01', 'Connaître'),
                    ('ob_R02', 'pt_R', '02', 'Calculer');
            """)
            c.commit()
        return {"connaitre": "ob_R01", "calc": "ob_R02"}

    def test_creer_lire_fiche(self, client, setup_objectifs):
        rep = client.post("/api/fiches-resume", json={
            "objectif_id": setup_objectifs["calc"],
            "titre": "Ma fiche",
        })
        assert rep.status_code == 201
        f = rep.get_json()
        assert f["titre"] == "Ma fiche"
        # Lecture
        rep2 = client.get(f"/api/fiches-resume/{f['id']}")
        assert rep2.status_code == 200

    def test_creer_objectif_inconnu_404(self, client):
        rep = client.post("/api/fiches-resume", json={
            "objectif_id": "ob_inexistant",
            "titre": "X",
        })
        assert rep.status_code == 404
        assert rep.get_json()["code"] == "objectif_introuvable"

    def test_creer_doublon_409(self, client, setup_objectifs):
        client.post("/api/fiches-resume", json={
            "objectif_id": setup_objectifs["calc"], "titre": "F1",
        })
        rep = client.post("/api/fiches-resume", json={
            "objectif_id": setup_objectifs["calc"], "titre": "F2",
        })
        assert rep.status_code == 409
        assert rep.get_json()["code"] == "objectif_deja_lie"

    def test_modifier_fiche(self, client, setup_objectifs):
        rep = client.post("/api/fiches-resume", json={
            "objectif_id": setup_objectifs["calc"], "titre": "Avant",
        })
        f = rep.get_json()
        # v0.13.7.0e — Route passée en strict PATCH.
        rep2 = client.patch(f"/api/fiches-resume/{f['id']}", json={
            "titre": "Après",
        })
        assert rep2.status_code == 200
        assert rep2.get_json()["titre"] == "Après"

    def test_supprimer_fiche(self, client, setup_objectifs):
        rep = client.post("/api/fiches-resume", json={
            "objectif_id": setup_objectifs["calc"], "titre": "F",
        })
        f = rep.get_json()
        rep2 = client.delete(f"/api/fiches-resume/{f['id']}")
        assert rep2.status_code == 200
        # Plus accessible
        rep3 = client.get(f"/api/fiches-resume/{f['id']}")
        assert rep3.status_code == 404

    def test_attacher_detacher_fiche(self, client, setup_objectifs):
        rep = client.post("/api/fiches-resume", json={
            "objectif_id": setup_objectifs["calc"], "titre": "F",
        })
        f = rep.get_json()
        # Attacher au Connaître
        rep2 = client.post(
            f"/api/objectifs-v2/{setup_objectifs['connaitre']}/fiches",
            json={"fiche_id": f["id"]},
        )
        assert rep2.status_code == 201
        # Lister
        rep3 = client.get(
            f"/api/objectifs-v2/{setup_objectifs['connaitre']}/fiches",
        )
        assert len(rep3.get_json()["fiches"]) == 1
        # Détacher
        rep4 = client.delete(
            f"/api/objectifs-v2/{setup_objectifs['connaitre']}/fiches/{f['id']}",
        )
        assert rep4.status_code == 200
        rep5 = client.get(
            f"/api/objectifs-v2/{setup_objectifs['connaitre']}/fiches",
        )
        assert rep5.get_json()["fiches"] == []

    def test_fiches_de_partie(self, client, setup_objectifs):
        client.post("/api/fiches-resume", json={
            "objectif_id": setup_objectifs["calc"], "titre": "F",
        })
        rep = client.get("/api/parties/pt_R/fiches-disponibles")
        assert rep.status_code == 200
        assert len(rep.get_json()["fiches"]) == 1

    def test_aplatir_payload_manquant(self, client):
        rep = client.post("/api/fiches-resume/aplatir-atome", json={})
        assert rep.status_code == 400

    def test_aplatir_type_invalide(self, client):
        rep = client.post("/api/fiches-resume/aplatir-atome", json={
            "type_atome": "exercice",
            "atome_id": "x",
        })
        assert rep.status_code == 400

    def test_etat_code_persiste_via_route(self, client, setup_objectifs):
        """La route PUT doit préserver etat_code (Q2-N).

        v0.13.6.16 : la fiche doit maintenant avoir au moins une
        section avec contenu pour passer le hook de validation
        pédagogique (titre seul ne suffit plus pour atteindre l'état
        `valide`).
        """
        rep = client.post("/api/fiches-resume", json={
            "objectif_id": setup_objectifs["calc"], "titre": "F",
            "sections": [{"titre": "Z1", "items": ["item 1"]}],
        })
        f = rep.get_json()
        # Valider via la route états_edition
        client.patch(
            f"/api/atomes/fiche_resume/{f['id']}/etat",
            json={"etat_code": "valide"},
        )
        # Modifier le titre
        # v0.13.7.0e — Route passée en strict PATCH.
        client.patch(f"/api/fiches-resume/{f['id']}", json={
            "titre": "Modifié",
        })
        # L'état doit toujours être 'valide'
        rep_etat = client.get(
            f"/api/atomes/fiche_resume/{f['id']}/etat",
        )
        assert rep_etat.get_json()["etat_code"] == "valide"
