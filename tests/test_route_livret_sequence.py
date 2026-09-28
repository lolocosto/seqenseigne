r"""tests/test_route_livret_sequence.py — v0.11.2.

Tests des routes /api/v2/livret-sequence/<niveau>/<sequence>/...

Couvre :
  - rendu-tex : succès (200), validation niveau (400), validation sequence
    (400), génération qui plante (500).
  - rendu-pdf : succès (200) si pdflatex disponible, échec compilation
    (422), validation (400). Les tests PDF sont skipped si pdflatex
    n'est pas dans le PATH.
  - format des options : envoi via JSON, prise en compte des toggles.

Stratégie : reprend la fixture app_avec_seq de test_livret_sequence.py
(via une copie locale légèrement adaptée). Plutôt que d'importer la
fixture, on la duplique parce que pytest ne facilite pas le partage
de fixtures complexes entre fichiers et qu'une duplication ciblée
est plus lisible que des conftest acrobatiques.
"""

from __future__ import annotations
import json
import shutil
import pytest

from app import create_app


PDFLATEX_DISPO = shutil.which('pdflatex') is not None


# ── Fixture : app peuplée avec une séquence minimale ────────────────────────

@pytest.fixture
def app_avec_seq(data_dir):
    """App Flask avec N11/S01 peuplée d'1 notion + 1 méthode + 1 exo F.
    Plus minimal que test_livret_sequence pour rester focalisé sur
    les routes (les tests métier sont déjà dans test_livret_sequence)."""
    app = create_app(data_dir=data_dir)

    with app.json_store._conn() as conn:
        conn.executescript("""
            -- Tables paquet_* nécessaires à construire_preambule.
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
            INSERT INTO paquet_requirepackage VALUES
                ('seqenseigne-core.sty', 0, 'amsmath', ''),
                ('seqenseigne-core.sty', 1, 'tikz', '');

            -- Données de séquence
            INSERT OR IGNORE INTO cycles (code, nom)
                VALUES ('C04', 'Cycle 4');
            INSERT OR IGNORE INTO themes (id, cycle_code, code, nom, code_couleur)
                VALUES ('th_A', 'C04', 'A', 'Nombres', 'nombres');
            INSERT OR IGNORE INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
                VALUES ('sc_s01', 'C04', 'S01', 1, 'Représentations', 'th_A');

            INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
                VALUES ('sn1', 'N11', 'S01', '');
            INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                VALUES ('p1', 'sn1', 1);

            INSERT INTO notions (id, niveau, sequence, fichier, titre, num_connaissance, corps)
                VALUES ('no1', 'N11', 'S01', 'fic.tex', 'Notion 1', '01', 'Définition...');
            INSERT INTO methodes (id, niveau, sequence, fichier, titre, num_methode, num_objectif, corps)
                VALUES ('me1', 'N11', 'S01', 'fic.tex', 'Méthode 1', 1, '02', 'On compte...');

            INSERT INTO objectifs (id, partie_id, code, nom)
                VALUES ('ob1', 'p1', '01', 'O1');
            INSERT INTO objectif_notions (objectif_id, notion_id, ordre)
                VALUES ('ob1', 'no1', 1);

            INSERT INTO exercices (id, serie, titre, niveau, sequence, num, serie_code, fichier, enonce, corrige)
                VALUES ('ex_f1', 'fondamental', 'F1', 'N11', 'S01', 1, 'F', 'fic.tex',
                        'Énoncé F1', 'Corrigé F1');
            INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre)
                VALUES ('ob1', 'F', 'ex_f1', 1);
        """)
        conn.commit()

    yield app


@pytest.fixture
def client(app_avec_seq):
    return app_avec_seq.test_client()


# ── Route rendu-tex ──────────────────────────────────────────────────────────

class TestRenduTex:

    def test_succes_get(self, client):
        """GET sans body renvoie le .tex avec options par défaut."""
        r = client.get('/api/v2/livret-sequence/N11/S01/rendu-tex')
        assert r.status_code == 200
        assert r.mimetype == 'text/plain'
        body = r.get_data(as_text=True)
        assert r'\documentclass' in body
        assert r'\begin{document}' in body
        # Les notions et méthodes doivent être présentes par défaut.
        assert 'seqNotion' in body
        assert 'seqMethode' in body

    def test_succes_post_avec_options(self, client):
        """POST avec body JSON {options: {cours: {inclure: false}}} doit
        désactiver le bloc Cours."""
        r = client.post(
            '/api/v2/livret-sequence/N11/S01/rendu-tex',
            json={'options': {'cours': {'inclure': False}}},
        )
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        # Cours désactivé : pas de bloc Cours, pas de seqNotion/seqMethode.
        assert r'\seqTitreSection{Cours}' not in body
        # Mais les exercices restent.
        assert r'\begin{seqSerieExos}' in body

    def test_post_body_vide_equivalent_a_get(self, client):
        """POST sans body JSON → comportement identique au GET (defaults)."""
        r1 = client.get('/api/v2/livret-sequence/N11/S01/rendu-tex')
        r2 = client.post('/api/v2/livret-sequence/N11/S01/rendu-tex')
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Même contenu — les deux passent par les mêmes options par défaut.
        assert r1.get_data(as_text=True) == r2.get_data(as_text=True)

    def test_options_partielles_completees_avec_defauts(self, client):
        """Si on envoie {options: {exercices: {serie_A: false}}},
        les autres toggles gardent leurs défauts (True)."""
        r = client.post(
            '/api/v2/livret-sequence/N11/S01/rendu-tex',
            json={'options': {'exercices': {'serie_A': False}}},
        )
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        # cours.inclure=True par défaut → bloc Cours présent.
        # v0.11.6.2 : le titre « Cours » a été supprimé, on prend
        # \seqTitreSection{Connaissances} comme marqueur du bloc cours.
        assert r'\seqTitreSection{Connaissances}' in body
        # serie_A=false → pas de seqSerieExos{2}.
        assert r'\begin{seqSerieExos}{2}' not in body

    def test_niveau_invalide(self, client):
        r = client.get('/api/v2/livret-sequence/N99/S01/rendu-tex')
        assert r.status_code == 400
        assert r.is_json
        data = r.get_json()
        assert 'error' in data
        assert 'niveau invalide' in data['error']

    def test_sequence_invalide(self, client):
        r = client.get('/api/v2/livret-sequence/N11/XYZ/rendu-tex')
        assert r.status_code == 400
        data = r.get_json()
        assert 'sequence invalide' in data['error']

    def test_sequence_inexistante_en_bdd(self, client):
        """Niveau/sequence valides syntaxiquement mais pas en BDD →
        500 avec message d'erreur. Le service lève une exception sur
        une séquence introuvable, on la remonte en 500 (pas 404 :
        c'est une erreur d'intégrité plutôt qu'une ressource
        manquante au sens HTTP)."""
        r = client.get('/api/v2/livret-sequence/N11/S99/rendu-tex')
        assert r.status_code == 500
        data = r.get_json()
        assert data['error'] == 'erreur_generation_tex'

    def test_methodes_GET_POST_acceptees(self, client):
        """Les deux verbes sont équivalents pour /rendu-tex."""
        r_get = client.get('/api/v2/livret-sequence/N11/S01/rendu-tex')
        r_post = client.post('/api/v2/livret-sequence/N11/S01/rendu-tex')
        assert r_get.status_code == 200
        assert r_post.status_code == 200


# ── Route rendu-pdf ──────────────────────────────────────────────────────────

class TestRenduPdf:

    def test_niveau_invalide(self, client):
        """Validation des paramètres avant tentative de compilation."""
        r = client.post('/api/v2/livret-sequence/N99/S01/rendu-pdf')
        assert r.status_code == 400
        data = r.get_json()
        assert 'niveau invalide' in data['error']

    def test_sequence_invalide(self, client):
        r = client.post('/api/v2/livret-sequence/N11/XYZ/rendu-pdf')
        assert r.status_code == 400

    def test_sequence_inexistante_en_bdd(self, client):
        """Avant même de tenter pdflatex, la génération du .tex doit
        échouer avec 500 (pas 422 — c'est l'étape génération qui
        plante, pas la compilation)."""
        r = client.post('/api/v2/livret-sequence/N11/S99/rendu-pdf')
        assert r.status_code == 500
        data = r.get_json()
        assert data['error'] == 'erreur_generation_tex'

    @pytest.mark.skipif(not PDFLATEX_DISPO,
                        reason="pdflatex non disponible")
    def test_succes_renvoie_pdf(self, client):
        """Avec pdflatex disponible, la compilation doit produire
        un PDF (ou échouer en 422 avec un message clair)."""
        r = client.post('/api/v2/livret-sequence/N11/S01/rendu-pdf')
        # 200 = PDF, 422 = erreur LaTeX (acceptable pour ce test : on
        # ne peut pas garantir que la compilation réussit toujours
        # avec une mini-BDD test sans toutes les ressources).
        assert r.status_code in (200, 422)
        if r.status_code == 200:
            assert r.mimetype == 'application/pdf'
            # Vérification minimale : signature PDF.
            assert r.data.startswith(b'%PDF-')
            # Headers de diag.
            assert 'X-Seq-Depuis-Cache' in r.headers
            assert 'X-Seq-Duree-Ms' in r.headers
        else:
            # 422 : structure d'erreur attendue.
            data = r.get_json()
            assert data['error'] == 'compilation_echouee'
            assert 'message' in data
            assert 'erreurs' in data
            assert 'log_complet' in data

    @pytest.mark.skipif(not PDFLATEX_DISPO,
                        reason="pdflatex non disponible")
    def test_cache_actif_sur_appels_repetes(self, client):
        """Deux appels successifs avec les mêmes options doivent
        produire le même résultat. Si le premier réussit, le second
        doit servir depuis le cache."""
        r1 = client.post('/api/v2/livret-sequence/N11/S01/rendu-pdf')
        r2 = client.post('/api/v2/livret-sequence/N11/S01/rendu-pdf')
        assert r1.status_code == r2.status_code
        if r1.status_code == 200:
            # Le second appel doit venir du cache.
            assert r2.headers.get('X-Seq-Depuis-Cache') == '1'

    @pytest.mark.skipif(not PDFLATEX_DISPO,
                        reason="pdflatex non disponible")
    def test_options_differentes_invalident_le_cache(self, client):
        """Deux appels avec des options différentes ne doivent PAS
        partager le cache (les options changent le .tex donc le hash)."""
        r1 = client.post('/api/v2/livret-sequence/N11/S01/rendu-pdf')
        r2 = client.post(
            '/api/v2/livret-sequence/N11/S01/rendu-pdf',
            json={'options': {'cours': {'inclure': False}}},
        )
        if r1.status_code == 200 and r2.status_code == 200:
            # Le second peut être en cache (run précédent du même test
            # ou cache_dir partagé), mais s'il vient du cache, c'est
            # un cache différent du premier. On vérifie juste que les
            # PDFs ne sont pas identiques.
            assert r1.data != r2.data


# ── v0.11.3 — Validation des options : refuser les deux blocs à False ─────

class TestRouteValidationOptions:

    def test_route_tex_400_si_les_deux_blocs_a_false(self, client):
        """Route .tex : si options désactivent à la fois cours et exercices,
        le service lève ValueError → la route renvoie 400."""
        r = client.post(
            '/api/v2/livret-sequence/N11/S01/rendu-tex',
            json={'options': {
                'cours':     {'inclure': False},
                'exercices': {'inclure': False},
            }},
        )
        assert r.status_code == 400
        body = r.get_json()
        assert body['error'] == 'options_invalides'
        assert 'cours ou exercices' in body['message']

    def test_route_pdf_400_si_les_deux_blocs_a_false(self, client):
        """Idem côté route PDF : refus en 400 avant compilation."""
        r = client.post(
            '/api/v2/livret-sequence/N11/S01/rendu-pdf',
            json={'options': {
                'cours':     {'inclure': False},
                'exercices': {'inclure': False},
            }},
        )
        assert r.status_code == 400
        body = r.get_json()
        assert body['error'] == 'options_invalides'

    def test_route_tex_200_si_un_seul_bloc_actif(self, client):
        """Cours seul (sans exercices) : valide, génération OK."""
        r = client.post(
            '/api/v2/livret-sequence/N11/S01/rendu-tex',
            json={'options': {'exercices': {'inclure': False}}},
        )
        assert r.status_code == 200
        # Pas d'exos → pas de seqSerieExos émis
        tex = r.data.decode('utf-8')
        assert r"\begin{seqSerieExos}" not in tex
        # Mais le bloc Cours est là (v0.11.6.2 : titre Cours supprimé,
        # Connaissances/Savoir-faire deviennent les marqueurs).
        assert r"\seqTitreSection{Connaissances}" in tex
