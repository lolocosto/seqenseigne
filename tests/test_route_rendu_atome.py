r"""
tests/test_route_rendu_atome.py — Tests des routes de rendu atomique.

Couvre :
  - /api/atomes/<type>/<id>/rendu-tex (succès, type invalide, atome absent)
  - /api/atomes/<type>/<id>/rendu-pdf (réponse structurée sur échec)
  - /api/atomes/<type>/<id>/rendu-log (404 si pas de cache)
  - /api/configuration (GET, POST, clés inconnues)

Les tests de rendu PDF réel utilisent une app Flask avec un exercice
simple ; ils sont skipped si pdflatex est absent.
"""

from __future__ import annotations
import json
import pytest
import shutil
import sys
from pathlib import Path

from app import create_app


PDFLATEX_DISPO = shutil.which('pdflatex') is not None


# ── Fixture : app avec un atome en BDD ────────────────────────────────────────

@pytest.fixture
def app_avec_atome(data_dir):
    """App Flask avec un exercice simple déjà en BDD."""
    app = create_app(data_dir=data_dir)

    # Créer les tables minimales du rendu + insérer un atome
    with app.json_store._conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS referentiel_niveaux (
                id TEXT PRIMARY KEY, niveau TEXT, version TEXT,
                date_debut TEXT, date_fin TEXT,
                description TEXT DEFAULT '', etat TEXT DEFAULT 'en_cours'
            );
            CREATE TABLE IF NOT EXISTS referentiel_themes (
                referentiel_id TEXT, code TEXT,
                nom TEXT, couleur TEXT DEFAULT '',
                PRIMARY KEY (referentiel_id, code)
            );
            CREATE TABLE IF NOT EXISTS referentiel_sequences (
                referentiel_id TEXT, code TEXT, numero INTEGER,
                nom TEXT, theme_code TEXT,
                PRIMARY KEY (referentiel_id, code)
            );
            CREATE TABLE IF NOT EXISTS exercices (
                id TEXT PRIMARY KEY, serie TEXT, titre TEXT DEFAULT '',
                variables TEXT DEFAULT '', enonce TEXT DEFAULT '',
                corrige TEXT DEFAULT '',
                niveau TEXT DEFAULT '', sequence TEXT DEFAULT '',
                num INTEGER, serie_code TEXT DEFAULT '',
                fichier TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS notions (
                id TEXT PRIMARY KEY, titre TEXT DEFAULT '', corps TEXT DEFAULT '',
                ordre_sections TEXT DEFAULT 'ER',
                niveau TEXT DEFAULT '', sequence TEXT DEFAULT '',
                num_connaissance TEXT DEFAULT '', fichier TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS methodes (
                id TEXT PRIMARY KEY, titre TEXT DEFAULT '', corps TEXT DEFAULT '',
                fin_cycle TEXT DEFAULT 'N', ordre_sections TEXT DEFAULT 'ER',
                niveau TEXT DEFAULT '', sequence TEXT DEFAULT '',
                num_methode INTEGER, num_objectif TEXT DEFAULT '',
                fichier TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS objectifs (
                id TEXT PRIMARY KEY, methode_id TEXT, code TEXT,
                critere_F TEXT DEFAULT '', critere_A TEXT DEFAULT '',
                critere_E TEXT DEFAULT '',
                niveau TEXT DEFAULT '', sequence TEXT DEFAULT '',
                nom TEXT DEFAULT '', est_nouveau INTEGER DEFAULT 0,
                obj_precedent_id TEXT
            );
            -- v0.11.1 — Tables nécessaires au rendu d'une fiche.
            CREATE TABLE IF NOT EXISTS fiches_resume (
                id TEXT PRIMARY KEY,
                titre TEXT NOT NULL DEFAULT '',
                objectif_id TEXT,
                num_fiche INTEGER,
                niveau TEXT NOT NULL DEFAULT '',
                sequence TEXT NOT NULL DEFAULT '',
                fichier TEXT NOT NULL DEFAULT '',
                etat_code TEXT NOT NULL DEFAULT 'en_cours'
            );
            CREATE TABLE IF NOT EXISTS atome_sections (
                id TEXT PRIMARY KEY,
                entite_type TEXT NOT NULL,
                entite_id TEXT NOT NULL,
                titre TEXT NOT NULL,
                ordre INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS atome_section_items (
                id TEXT PRIMARY KEY,
                section_id TEXT NOT NULL,
                ordre INTEGER NOT NULL DEFAULT 0,
                corps TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS paquet_definitions (
                nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
                corps TEXT, corps_fin TEXT, texte_complet TEXT,
                fichier_source TEXT, ligne_debut INTEGER,
                macros_appelees TEXT, environnements_utilises TEXT,
                statut_rendu_atome TEXT DEFAULT 'reutilise',
                contenu_atome TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS paquet_requirepackage (
                fichier_source TEXT NOT NULL,
                ordre INTEGER NOT NULL,
                nom TEXT NOT NULL,
                options TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (fichier_source, ordre)
            );
        """)
        conn.execute("""
            INSERT INTO referentiel_niveaux (id, niveau, version, date_fin)
            VALUES ('ref1', 'N10', '2021', NULL)
        """)
        conn.execute("""
            INSERT INTO referentiel_themes VALUES
            ('ref1', 'A', 'Nombres et Calculs', 'nombres')
        """)
        conn.execute("""
            INSERT INTO referentiel_sequences VALUES
            ('ref1', 'S01', 1, 'Séq 1', 'A')
        """)
        conn.execute("""
            INSERT INTO exercices (id, niveau, sequence, fichier, titre,
                                   serie, num, enonce, corrige)
            VALUES ('ex1', 'N10', 'S01', 'N10S01F01.tex',
                    'Test', 'fondamental', 1,
                    'Question simple.', 'Réponse.')
        """)
        # v0.11.1 — Une fiche minimale avec une section pour tester la
        # route /api/atomes/fiche/<id>/rendu-tex.
        conn.execute("""
            INSERT INTO fiches_resume (id, niveau, sequence, fichier, titre)
            VALUES ('fi1', 'N10', 'S01', 'N10_S01_Fiche_01.tex',
                    'Calculer une proportion.')
        """)
        conn.execute("""
            INSERT INTO atome_sections (id, entite_type, entite_id, titre, ordre)
            VALUES ('sec_fi1_d', 'fiche_resume', 'fi1', 'Définition', 0)
        """)
        conn.execute("""
            INSERT INTO atome_section_items (id, section_id, ordre, corps)
            VALUES ('it_fi1_d0', 'sec_fi1_d', 0,
                    'Une proportion est \\\\acompleter{une fraction}.')
        """)
        # Le commit est géré par le context manager _conn

    return app


@pytest.fixture
def client_avec_atome(app_avec_atome):
    return app_avec_atome.test_client()


# ── /api/atomes/<type>/<id>/rendu-tex ─────────────────────────────────────────

class TestRenduTex:

    def test_succes_renvoie_tex(self, client_avec_atome):
        r = client_avec_atome.get('/api/atomes/exercice/ex1/rendu-tex')
        assert r.status_code == 200
        assert r.mimetype == 'text/plain'
        body = r.get_data(as_text=True)
        assert r'\documentclass' in body
        assert r'\usepackage' in body
        assert r'\begin{seqExercice}' in body

    def test_succes_fiche(self, client_avec_atome):
        # v0.11.1 — La route accepte type_atome='fiche'.
        r = client_avec_atome.get('/api/atomes/fiche/fi1/rendu-tex')
        assert r.status_code == 200
        assert r.mimetype == 'text/plain'
        body = r.get_data(as_text=True)
        # Structure du document
        assert r'\documentclass' in body
        assert r'\begin{document}' in body
        # Corps fiche : titre via \seqTitreSection, section Définition,
        # fill final, et \acompleter défini dans le préambule.
        assert r'\seqTitreSection{Calculer une proportion.}' in body
        assert '\\begin{seqBoiteContenuFlashcard}[titre=Définition]' in body
        assert '\\begin{seqBoiteFillContenuFlashcard}' in body
        assert r'\providecommand{\acompleter}' in body

    def test_type_invalide(self, client_avec_atome):
        r = client_avec_atome.get('/api/atomes/batate/ex1/rendu-tex')
        assert r.status_code == 400
        data = r.get_json()
        assert 'error' in data

    def test_atome_introuvable(self, client_avec_atome):
        r = client_avec_atome.get('/api/atomes/exercice/xxx/rendu-tex')
        assert r.status_code == 404


# ── /api/atomes/<type>/<id>/rendu-pdf ─────────────────────────────────────────

class TestRenduPdf:

    def test_type_invalide(self, client_avec_atome):
        r = client_avec_atome.post('/api/atomes/batate/ex1/rendu-pdf')
        assert r.status_code == 400

    def test_atome_introuvable(self, client_avec_atome):
        r = client_avec_atome.post('/api/atomes/exercice/xxx/rendu-pdf')
        assert r.status_code == 404

    def test_pdflatex_absent_retourne_503(self, client_avec_atome, monkeypatch,
                                           tmp_path):
        """Si aucun pdflatex, réponse 503 JSON structurée."""
        # Simuler l'absence de pdflatex
        from services import compilateur_pdf
        monkeypatch.setattr(compilateur_pdf, 'detecter_pdflatex',
                             lambda racine_appli=None: None)

        r = client_avec_atome.post('/api/atomes/exercice/ex1/rendu-pdf')
        assert r.status_code == 503
        data = r.get_json()
        assert data['error'] == 'compilation_echouee'
        assert 'pdflatex' in data['message'].lower()


# ── /api/atomes/<type>/<id>/rendu-log ─────────────────────────────────────────

class TestRenduLog:

    def test_404_si_jamais_compile(self, client_avec_atome):
        r = client_avec_atome.get('/api/atomes/exercice/ex1/rendu-log')
        assert r.status_code == 404


# ── /api/configuration ────────────────────────────────────────────────────────

class TestConfigurationRoute:

    def test_get_retourne_defauts(self, client_avec_atome):
        r = client_avec_atome.get('/api/configuration')
        assert r.status_code == 200
        data = r.get_json()
        assert 'chemin_sources_livrets' in data
        assert 'timeout_compilation_s' in data
        assert data['chemin_sources_livrets'] == ''

    def test_post_met_a_jour(self, client_avec_atome):
        r = client_avec_atome.post(
            '/api/configuration',
            data=json.dumps({'timeout_compilation_s': 60}),
            content_type='application/json',
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data['timeout_compilation_s'] == 60

        # GET après POST retourne la valeur mise à jour
        r2 = client_avec_atome.get('/api/configuration')
        assert r2.get_json()['timeout_compilation_s'] == 60

    def test_post_cle_inconnue_ignoree(self, client_avec_atome):
        r = client_avec_atome.post(
            '/api/configuration',
            data=json.dumps({'pirate': 'x'}),
            content_type='application/json',
        )
        assert r.status_code == 200
        assert 'pirate' not in r.get_json()

    def test_post_payload_non_dict(self, client_avec_atome):
        r = client_avec_atome.post(
            '/api/configuration',
            data=json.dumps([1, 2, 3]),
            content_type='application/json',
        )
        assert r.status_code == 400


# ── v0.9 — /api/configuration/chemins-resolus ────────────────────────────────

class TestApiCheminsResolus:
    """v0.9 — Endpoint qui applique la dérivation depuis la racine.

    Ce endpoint existe pour éviter de dupliquer la règle override → dérivé
    côté frontend. Il garantit que le pré-remplissage des champs Admin
    utilise exactement la même logique que la résolution Python interne
    (chemin_sources_livrets, chemin_pdflatex, ...).
    """

    def test_sans_racine_tout_vide(self, client_avec_atome):
        r = client_avec_atome.get('/api/configuration/chemins-resolus')
        assert r.status_code == 200
        data = r.get_json()
        # Les 5 clés sont présentes
        for cle in ('racine', 'chemin_sources_livrets', 'chemin_pdflatex',
                    'chemin_paquet', 'chemin_reference_sequences'):
            assert cle in data, f"clé manquante : {cle}"
        # Toutes vides (pas de config initiale)
        assert data['racine'] == ''
        assert data['chemin_paquet'] == ''
        assert data['chemin_reference_sequences'] == ''

    def test_avec_racine_les_4_chemins_derives(self, client_avec_atome):
        """Une racine seule suffit à dériver les 4 chemins."""
        client_avec_atome.post(
            '/api/configuration',
            data=json.dumps({'chemin_racine_seqenseigne': '/home/laurent/seq'}),
            content_type='application/json',
        )
        r = client_avec_atome.get('/api/configuration/chemins-resolus')
        data = r.get_json()
        assert data['racine'] == '/home/laurent/seq'
        # Les 4 dérivés sont présents
        assert data['chemin_sources_livrets'].endswith('sequences')
        assert data['chemin_pdflatex'].endswith('pdflatex.exe')
        assert data['chemin_paquet'].endswith('paquet')
        assert data['chemin_reference_sequences'].endswith('sequences')
        # Chacun contient bien la racine
        for cle in ('chemin_sources_livrets', 'chemin_pdflatex',
                    'chemin_paquet', 'chemin_reference_sequences'):
            assert '/home/laurent/seq' in data[cle], \
                f"{cle} ne contient pas la racine : {data[cle]!r}"

    def test_override_individuel_prime_sur_derive(self, client_avec_atome):
        """Override par champ : seule la valeur explicite est retournée."""
        client_avec_atome.post(
            '/api/configuration',
            data=json.dumps({
                'chemin_racine_seqenseigne': '/home/laurent/seq',
                'chemin_paquet':             '/explicit/paquet',
            }),
            content_type='application/json',
        )
        r = client_avec_atome.get('/api/configuration/chemins-resolus')
        data = r.get_json()
        # Override gagne pour chemin_paquet
        assert data['chemin_paquet'] == '/explicit/paquet'
        # Les autres restent dérivés de la racine
        assert '/home/laurent/seq' in data['chemin_reference_sequences']

    def test_changement_racine_repercute_sur_derives(self, client_avec_atome):
        """Scénario clé USB D: → E: : changer juste la racine."""
        # Premier réglage
        client_avec_atome.post(
            '/api/configuration',
            data=json.dumps({'chemin_racine_seqenseigne': '/d/seq'}),
            content_type='application/json',
        )
        r1 = client_avec_atome.get('/api/configuration/chemins-resolus').get_json()
        assert '/d/seq' in r1['chemin_paquet']

        # Bascule vers une autre racine
        client_avec_atome.post(
            '/api/configuration',
            data=json.dumps({'chemin_racine_seqenseigne': '/e/seq'}),
            content_type='application/json',
        )
        r2 = client_avec_atome.get('/api/configuration/chemins-resolus').get_json()
        assert '/e/seq' in r2['chemin_paquet']
        assert '/d/seq' not in r2['chemin_paquet']


# ── Test de bout en bout avec pdflatex ───────────────────────────────────────

@pytest.mark.skipif(not PDFLATEX_DISPO,
                    reason='pdflatex non disponible')
class TestRenduPdfReel:

    def test_rendu_pdf_echec_structure_422(self, client_avec_atome):
        """Sans les .sty de seqenseigne dans TEXINPUTS, la compilation échoue.
        On vérifie que la structure de réponse est correcte."""
        r = client_avec_atome.post('/api/atomes/exercice/ex1/rendu-pdf')
        # 422 = compilation échouée (erreur de LaTeX, pas d'infra)
        # ou 503 si pdflatex absent (exclu par le skip)
        assert r.status_code in (200, 422), (
            f"Status inattendu {r.status_code} : {r.get_data(as_text=True)[:300]}"
        )
        if r.status_code == 422:
            data = r.get_json()
            assert data['error'] == 'compilation_echouee'
            assert 'erreurs' in data
