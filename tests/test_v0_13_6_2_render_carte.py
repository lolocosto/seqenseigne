"""tests/test_v0_13_6_2_render_carte.py — v0.13.6.2

Tests de la génération du .tex d'une carte d'automatisme.

Tests :
- Lookup du code_couleur via JOIN BDD
- Résolution du libellé du type pédagogique
- Génération du .tex pour carte fixe
- Génération du .tex pour carte paramétrée (avec variables en préambule)
- Route /api/cartes/<id>/rendu-tex
"""
from __future__ import annotations
import sqlite3

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Schéma BDD minimal
# ─────────────────────────────────────────────────────────────────────────────

_SCHEMA_TEST = """
CREATE TABLE param_niveaux (
    code         TEXT PRIMARY KEY,
    cycle_code   TEXT NOT NULL,
    nom_court    TEXT,
    nom_long     TEXT,
    annee        TEXT,
    ordre        INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE themes (
    id           TEXT PRIMARY KEY,
    cycle_code   TEXT NOT NULL,
    code         TEXT NOT NULL,
    nom          TEXT,
    code_couleur TEXT,
    description  TEXT,
    ordre        INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE sequences_du_cycle (
    id          TEXT PRIMARY KEY,
    cycle_code  TEXT NOT NULL,
    code        TEXT NOT NULL,
    numero      INTEGER,
    nom         TEXT,
    theme_id    TEXT REFERENCES themes(id)
);
CREATE TABLE notions (
    id               TEXT PRIMARY KEY,
    titre            TEXT NOT NULL DEFAULT '',
    corps            TEXT NOT NULL DEFAULT '',
    niveau           TEXT NOT NULL,
    sequence         TEXT NOT NULL,
    num_connaissance TEXT,
    etat_code        TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE methodes (
    id           TEXT PRIMARY KEY,
    titre        TEXT NOT NULL DEFAULT '',
    corps        TEXT NOT NULL DEFAULT '',
    niveau       TEXT NOT NULL,
    sequence     TEXT NOT NULL,
    num_methode  INTEGER,
    num_objectif TEXT,
    etat_code    TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE cartes_automatisme (
    id            TEXT PRIMARY KEY,
    niveau        TEXT NOT NULL,
    sequence      TEXT NOT NULL,
    num           INTEGER NOT NULL,
    type_pedago   TEXT NOT NULL DEFAULT 'definition',
    type_tech     TEXT NOT NULL DEFAULT 'fixe',
    titre         TEXT NOT NULL DEFAULT '',
    lien_type     TEXT,
    lien_id       TEXT,
    recto         TEXT NOT NULL DEFAULT '',
    verso         TEXT NOT NULL DEFAULT '',
    variables     TEXT NOT NULL DEFAULT '',
    etat_code     TEXT NOT NULL DEFAULT 'en_cours',
    ordre         INTEGER NOT NULL DEFAULT 1,
    mtime         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (niveau, sequence, num),
    CHECK  (type_pedago IN ('definition', 'propriete', 'reconnaissance',
                            'calcul', 'procedure')),
    CHECK  (type_tech IN ('fixe', 'parametree')),
    CHECK  (etat_code IN ('en_cours', 'valide')),
    CHECK  (num > 0 AND num < 100),
    CHECK  ((lien_type IS NULL AND lien_id IS NULL)
            OR (lien_type IN ('notion', 'methode')
                AND lien_id IS NOT NULL))
);
-- v0.13.6.13 : tables pour le nouveau modèle de lien carte → objectif
CREATE TABLE objectifs (
    id          TEXT PRIMARY KEY,
    methode_id  TEXT REFERENCES methodes(id) ON DELETE CASCADE,
    partie_id   TEXT,
    code        TEXT,
    nom         TEXT
);
CREATE TABLE objectif_notions (
    objectif_id TEXT NOT NULL
                REFERENCES objectifs(id) ON DELETE CASCADE,
    notion_id   TEXT NOT NULL
                REFERENCES notions(id) ON DELETE CASCADE,
    PRIMARY KEY (objectif_id, notion_id)
);
CREATE TABLE objectif_cartes (
    objectif_id TEXT NOT NULL
                REFERENCES objectifs(id) ON DELETE CASCADE,
    carte_id    TEXT NOT NULL
                REFERENCES cartes_automatisme(id) ON DELETE CASCADE,
    ordre       INTEGER NOT NULL DEFAULT 0,
    mtime       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (objectif_id, carte_id)
);
CREATE TABLE cartes_atelier_config (
    cle    TEXT PRIMARY KEY,
    valeur TEXT NOT NULL DEFAULT ''
);
"""


@pytest.fixture
def conn(tmp_path):
    """BDD vierge avec schéma minimal + données de référence
    (niveaux, thèmes, séquences)."""
    db = tmp_path / "test.db"
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(_SCHEMA_TEST)
    # Référentiel minimal
    c.execute("INSERT INTO param_niveaux (code, cycle_code) VALUES ('N10', 'C04')")
    c.execute("INSERT INTO param_niveaux (code, cycle_code) VALUES ('N11', 'C04')")
    c.execute("INSERT INTO themes (id, cycle_code, code, nom, code_couleur) "
              "VALUES ('th_n', 'C04', 'A', 'Nombres et Calculs', 'nombres')")
    c.execute("INSERT INTO themes (id, cycle_code, code, nom, code_couleur) "
              "VALUES ('th_g', 'C04', 'D', 'Espace et géométrie', 'geometrie')")
    c.execute("INSERT INTO sequences_du_cycle (id, cycle_code, code, nom, theme_id) "
              "VALUES ('sdc_1', 'C04', 'S01', 'Nombres', 'th_n')")
    c.execute("INSERT INTO sequences_du_cycle (id, cycle_code, code, nom, theme_id) "
              "VALUES ('sdc_5', 'C04', 'S05', 'Symétries', 'th_g')")
    c.execute("INSERT INTO notions (id, niveau, sequence, num_connaissance, titre) "
              "VALUES ('no_a', 'N10', 'S01', '01', 'Notion A')")
    c.commit()
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Lookups
# ─────────────────────────────────────────────────────────────────────────────


class TestResoudreCodeCouleur:
    def test_sequence_existante(self, conn):
        from services.render_carte import resoudre_code_couleur
        assert resoudre_code_couleur(conn, 'N10', 'S01') == 'nombres'

    def test_autre_sequence_autre_theme(self, conn):
        from services.render_carte import resoudre_code_couleur
        assert resoudre_code_couleur(conn, 'N10', 'S05') == 'geometrie'

    def test_sequence_inconnue_renvoie_defaut(self, conn):
        from services.render_carte import (
            resoudre_code_couleur, CODE_COULEUR_DEFAUT
        )
        # S99 n'existe pas
        assert resoudre_code_couleur(conn, 'N10', 'S99') == CODE_COULEUR_DEFAUT

    def test_niveau_inconnu_renvoie_defaut(self, conn):
        from services.render_carte import (
            resoudre_code_couleur, CODE_COULEUR_DEFAUT
        )
        assert resoudre_code_couleur(conn, 'N99', 'S01') == CODE_COULEUR_DEFAUT


class TestResoudreLibelle:
    def test_definitions_connues(self):
        from services.render_carte import resoudre_libelle_type_pedago
        assert resoudre_libelle_type_pedago('definition') == 'Définition'
        assert resoudre_libelle_type_pedago('propriete') == 'Propriété'
        assert resoudre_libelle_type_pedago('reconnaissance') == 'Reconnaissance'
        assert resoudre_libelle_type_pedago('calcul') == 'Calcul'
        assert resoudre_libelle_type_pedago('procedure') == 'Procédure'

    def test_code_inconnu_capitalise(self):
        from services.render_carte import resoudre_libelle_type_pedago
        assert resoudre_libelle_type_pedago('xyz') == 'Xyz'

    def test_vide_renvoie_fallback(self):
        from services.render_carte import resoudre_libelle_type_pedago
        assert resoudre_libelle_type_pedago('') == 'Carte'


# ─────────────────────────────────────────────────────────────────────────────
# Génération du .tex
# ─────────────────────────────────────────────────────────────────────────────


class TestGenererTexCarte:
    def test_carte_fixe_basique(self, conn):
        from services.cartes_automatisme import creer_carte
        from services.render_carte import generer_tex_carte
        c = creer_carte(conn, niveau='N10', sequence='S01',
                        type_pedago='propriete',
                        recto='Combien font $20\\%$ de $100$?',
                        verso='$20$')
        tex = generer_tex_carte(conn, c['id'])
        # Préambule attendu
        assert '\\documentclass' in tex
        assert 'seqenseigne-carte-automatisme' in tex
        # v0.13.6.2.2 : on ne charge plus tcolorbox dans le préambule
        # (déjà chargé par seqenseigne-theme avec ses options
        # [theorems,breakable,skins]). Le charger ici produit
        # « Option clash for package tcolorbox ».
        assert '\\usepackage{tcolorbox}' not in tex
        assert '\\tcbuselibrary' not in tex
        # En revanche, seqenseigne-theme est bien chargé (dépendance)
        assert 'seqenseigne-theme' in tex
        # Appel \seqCarteAuto avec options correctes
        assert '\\seqCarteAuto' in tex
        assert 'niveau=N10' in tex
        assert 'sequence=S01' in tex
        assert 'num=1' in tex
        assert 'typepedagolibelle={Propriété}' in tex
        assert 'codecouleur={nombres}' in tex
        # Contenu recto/verso
        assert 'Combien font $20\\%$ de $100$?' in tex
        assert '{$20$}' in tex
        # Pas de variables xint en préambule pour carte fixe
        assert '\\xintdefiivar' not in tex

    def test_carte_parametree_variables_dans_groupe_du_corps(self, conn):
        """v0.15.2.2 — Les variables xint sont placées dans un groupe LaTeX
        `{...}` à l'intérieur de \\begin{document}, avant l'appel à
        \\seqCarteAutomatisme (pas en préambule comme avant).

        Cohérent avec la stratégie « variables avant l'environnement »
        appliquée à toutes les macros publiques v0.15.2.2 du paquet
        seqenseigne-carte-automatisme.
        """
        from services.cartes_automatisme import creer_carte
        from services.render_carte import generer_tex_carte
        c = creer_carte(conn, niveau='N10', sequence='S01',
                        type_pedago='calcul',
                        type_tech='parametree',
                        recto='Combien font $\\xinttheiiexpr p\\relax\\%$?',
                        verso='$\\xinttheiiexpr p\\relax$',
                        variables='\\xintdefiivar p := 25;')
        tex = generer_tex_carte(conn, c['id'])
        # Variables APRÈS \begin{document} (dans un groupe avec l'appel)
        debut_doc = tex.find('\\begin{document}')
        pos_var = tex.find('\\xintdefiivar p := 25;')
        assert pos_var > 0
        assert pos_var > debut_doc, (
            "v0.15.2.2 : les variables xint doivent être dans un groupe "
            "à l'intérieur du document, pas en préambule."
        )
        # Et avant l'appel \seqCarteAutomatisme (dans le groupe englobant)
        pos_macro = tex.find('\\seqCarteAutomatisme')
        assert pos_var < pos_macro

    def test_code_couleur_recupere_via_join(self, conn):
        """Le tex doit contenir le code_couleur correct selon la séquence."""
        from services.cartes_automatisme import creer_carte
        from services.render_carte import generer_tex_carte
        c_n = creer_carte(conn, niveau='N10', sequence='S01',
                          type_pedago='definition',
                          recto='Q', verso='R')
        c_g = creer_carte(conn, niveau='N10', sequence='S05',
                          type_pedago='definition',
                          recto='Q', verso='R')
        tex_n = generer_tex_carte(conn, c_n['id'])
        tex_g = generer_tex_carte(conn, c_g['id'])
        assert 'codecouleur={nombres}' in tex_n
        assert 'codecouleur={geometrie}' in tex_g

    def test_carte_inexistante_leve(self, conn):
        from services.render_carte import generer_tex_carte
        from services.cartes_automatisme import CarteIntrouvable
        with pytest.raises(CarteIntrouvable):
            generer_tex_carte(conn, 'crt_inexistant')

    def test_nom_avec_caracteres_speciaux_echappe(self, conn):
        """Les valeurs d'options sont entourées d'accolades, donc des
        virgules dans le nom ne devraient pas casser le parsing xkeyval."""
        from services.cartes_automatisme import creer_carte
        from services.render_carte import generer_tex_carte
        c = creer_carte(conn, niveau='N10', sequence='S01',
                        titre='Test, avec virgule')
        tex = generer_tex_carte(conn, c['id'])
        # L'option LaTeX reste nommée `nom` côté .tex (cf. paquet
        # seqenseigne). Renommage de l'option hors scope v0.13.6.15.
        assert 'nom={Test, avec virgule}' in tex


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def app_test(tmp_path):
    """App Flask de test avec data_dir temporaire."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "param_niveaux.csv").write_text(
        "Code,CodeCycle,AnneeDansCycle,NomCourt,NomLong\n"
        "N10,C04,anneeun,5e,cinquième\n", encoding="utf-8"
    )
    (data / "C04_themes.csv").write_text(
        "Code,Nom,CodeCouleur,Description\nA,Nombres,nombres,desc\n",
        encoding="utf-8"
    )
    (data / "C04_sequences.csv").write_text(
        "Code,Numero,Nom,Theme\nS01,1,Nombres,A\n", encoding="utf-8"
    )
    from app import create_app
    app = create_app(data_dir=data)
    return app


class TestRouteRenduTex:
    """v0.14.4 — Les routes /api/cartes/<id>/rendu-tex et /rendu-pdf
    ont été supprimées (cf. routes/cartes_automatisme.py). La carte
    utilise désormais l'API unifiée /api/atomes/carte/<id>/...
    portée par routes/rendu_atome.py (dispatch via generer_tex_par_type
    ajouté en v0.14.2). Les tests valident la même fonctionnalité au
    nouvel emplacement.
    """

    def test_get_rendu_tex_ok(self, app_test):
        """200 + Content-Type text/plain pour une carte existante."""
        client = app_test.test_client()
        # Créer une carte
        r = client.post('/api/cartes', json={
            'niveau': 'N10', 'sequence': 'S01',
            'type_pedago': 'definition',
            'recto': 'Q', 'verso': 'R',
        })
        assert r.status_code == 201
        carte_id = r.get_json()['id']
        # v0.14.4 — Récupération du .tex via l'API unifiée.
        r = client.get(f'/api/atomes/carte/{carte_id}/rendu-tex')
        assert r.status_code == 200
        assert r.mimetype.startswith('text/plain')
        tex = r.data.decode('utf-8')
        assert '\\documentclass' in tex
        assert '\\seqCarteAuto' in tex

    def test_get_rendu_tex_404(self, app_test):
        """404 pour une carte inexistante."""
        client = app_test.test_client()
        # v0.14.4 — Route unifiée. Le dispatch generer_tex_par_type
        # convertit CarteIntrouvable en LookupError, qui devient 404
        # côté route (vs l'ancien code 'carte_introuvable' qui était
        # spécifique à l'ancienne route /api/cartes/<id>/rendu-tex).
        r = client.get('/api/atomes/carte/crt_inexistant/rendu-tex')
        assert r.status_code == 404
        data = r.get_json()
        # Le payload d'erreur a changé : routes/rendu_atome.py renvoie
        # juste {'error': str(LookupError)} sans code métier spécifique.
        assert 'error' in data
