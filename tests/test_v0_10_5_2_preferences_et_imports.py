"""tests/test_v0_10_5_2_preferences_et_imports.py — v0.10.5.2

Tests pour :
  1. Service preferences (CRUD + valeur unique)
  2. Routes preferences
  3. Service fiches_import (parser + import idempotent)
  4. Route admin/fiches/import
"""

from __future__ import annotations
import io
import sqlite3
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Schéma minimal in-memory ────────────────────────────────────────────────

_SCHEMA_TEST = """
CREATE TABLE preferences_items (
    id     TEXT PRIMARY KEY,
    type   TEXT NOT NULL,
    valeur TEXT NOT NULL DEFAULT '',
    ordre  INTEGER NOT NULL DEFAULT 0
);

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
    num_fiche INTEGER, niveau TEXT, sequence TEXT,
    fichier TEXT, etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA_TEST)
    yield c
    c.close()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Service preferences
# ═══════════════════════════════════════════════════════════════════════════


from services.preferences import (
    lister_items, ajouter_item, modifier_item, supprimer_item,
    reordonner_items, lire_valeur_unique, definir_valeur_unique,
    ItemIntrouvable, ValeurInvalide,
)


class TestPreferencesListe:
    def test_liste_vide(self, conn):
        assert lister_items(conn, 'titre_zone_fiche') == []

    def test_ajouter_simple(self, conn):
        item = ajouter_item(conn, 'titre_zone_fiche', 'Définition')
        assert item['valeur'] == 'Définition'
        assert item['ordre'] == 10  # premier item, ordre 10
        items = lister_items(conn, 'titre_zone_fiche')
        assert len(items) == 1

    def test_ajouter_plusieurs(self, conn):
        ajouter_item(conn, 'titre_zone_fiche', 'Définition')
        ajouter_item(conn, 'titre_zone_fiche', 'Propriété')
        ajouter_item(conn, 'titre_zone_fiche', 'Méthode')
        items = lister_items(conn, 'titre_zone_fiche')
        assert [i['valeur'] for i in items] == ['Définition', 'Propriété', 'Méthode']
        assert [i['ordre'] for i in items] == [10, 20, 30]

    def test_valeur_vide_refusee(self, conn):
        with pytest.raises(ValeurInvalide):
            ajouter_item(conn, 'titre_zone_fiche', '')
        with pytest.raises(ValeurInvalide):
            ajouter_item(conn, 'titre_zone_fiche', '   ')

    def test_valeur_strippee(self, conn):
        item = ajouter_item(conn, 'titre_zone_fiche', '  Démo  ')
        assert item['valeur'] == 'Démo'

    def test_modifier_valeur(self, conn):
        item = ajouter_item(conn, 'titre_zone_fiche', 'Démo')
        modifier_item(conn, item['id'], valeur='Démonstration')
        items = lister_items(conn, 'titre_zone_fiche')
        assert items[0]['valeur'] == 'Démonstration'

    def test_modifier_introuvable(self, conn):
        with pytest.raises(ItemIntrouvable):
            modifier_item(conn, 'inconnu', valeur='X')

    def test_supprimer(self, conn):
        item = ajouter_item(conn, 'titre_zone_fiche', 'X')
        supprimer_item(conn, item['id'])
        assert lister_items(conn, 'titre_zone_fiche') == []

    def test_supprimer_introuvable(self, conn):
        with pytest.raises(ItemIntrouvable):
            supprimer_item(conn, 'inconnu')

    def test_reordonner(self, conn):
        a = ajouter_item(conn, 'titre_zone_fiche', 'A')
        b = ajouter_item(conn, 'titre_zone_fiche', 'B')
        c = ajouter_item(conn, 'titre_zone_fiche', 'C')
        # Inverser : C, B, A
        items = reordonner_items(conn, 'titre_zone_fiche', [c['id'], b['id'], a['id']])
        assert [i['valeur'] for i in items] == ['C', 'B', 'A']
        assert [i['ordre'] for i in items] == [10, 20, 30]


class TestPreferencesValeurUnique:
    def test_lire_absent(self, conn):
        assert lire_valeur_unique(conn, 'chemin_x') is None

    def test_definir_creation(self, conn):
        item = definir_valeur_unique(conn, 'chemin_x', '/foo/bar')
        assert item['valeur'] == '/foo/bar'
        assert lire_valeur_unique(conn, 'chemin_x') == '/foo/bar'

    def test_definir_mise_a_jour(self, conn):
        definir_valeur_unique(conn, 'chemin_x', '/foo')
        definir_valeur_unique(conn, 'chemin_x', '/bar')
        assert lire_valeur_unique(conn, 'chemin_x') == '/bar'
        # Une seule ligne en BDD
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM preferences_items WHERE type = 'chemin_x'"
        ).fetchone()['n']
        assert n == 1


# ═══════════════════════════════════════════════════════════════════════════
# 2. Service fiches_import (parser)
# ═══════════════════════════════════════════════════════════════════════════


from services.fiches_import import parser_tex, importer_fiches, RapportImport


_TEX_SIMPLE = r"""
\seqSetCodeSequence{S01}
\seqBoiteTitreFlashcard{Objectif 02}{}
\begin{seqBoiteContenuFlashcard}[titre=Définition]
Premier contenu.
\end{seqBoiteContenuFlashcard}
\begin{seqBoiteContenuFlashcard}[titre=Propriété]
Deuxième contenu.
\end{seqBoiteContenuFlashcard}
\begin{seqBoiteFillContenuFlashcard}\end{seqBoiteFillContenuFlashcard}
\seqBoiteTitreFlashcard{03}{}
\begin{seqBoiteContenuFlashcard}[titre=Méthode]
Méthode du 03.
\end{seqBoiteContenuFlashcard}
\begin{seqBoiteFillContenuFlashcard}\end{seqBoiteFillContenuFlashcard}
"""


_TEX_DEUX_FICHES_PAR_OBJ = r"""
\seqSetCodeSequence{S04}
\seqBoiteTitreFlashcard{Objectif 04}{1\iere fiche}\seqBoiteTitreFlashcard{Objectif 04}{2\ieme fiche}
\begin{seqBoiteContenuFlashcard}[titre=Définition]
Premier bloc Obj 04.
\end{seqBoiteContenuFlashcard}
\begin{seqBoiteFillContenuFlashcard}\end{seqBoiteFillContenuFlashcard}
\begin{seqBoiteContenuFlashcard}[titre=Méthode]
Deuxième bloc Obj 04.
\end{seqBoiteContenuFlashcard}
\begin{seqBoiteFillContenuFlashcard}\end{seqBoiteFillContenuFlashcard}
"""


class TestParser:
    def test_simple(self):
        fiches = parser_tex(_TEX_SIMPLE, 'N10')
        assert len(fiches) == 2
        f02 = next(f for f in fiches if f.code_objectif == '02')
        assert f02.niveau == 'N10'
        assert f02.sequence == 'S01'
        assert len(f02.zones) == 2
        assert f02.zones[0].titre == 'Définition'
        assert 'Premier contenu' in f02.zones[0].corps
        assert f02.zones[1].titre == 'Propriété'

        f03 = next(f for f in fiches if f.code_objectif == '03')
        assert len(f03.zones) == 1

    def test_format_avec_et_sans_prefixe_objectif(self):
        """Le parser accepte indifféremment {Objectif 02} et {02}."""
        tex = r"""
        \seqSetCodeSequence{S01}
        \seqBoiteTitreFlashcard{Objectif 02}{}
        \begin{seqBoiteContenuFlashcard}[titre=A]X\end{seqBoiteContenuFlashcard}
        \begin{seqBoiteFillContenuFlashcard}\end{seqBoiteFillContenuFlashcard}
        \seqBoiteTitreFlashcard{03}{}
        \begin{seqBoiteContenuFlashcard}[titre=B]Y\end{seqBoiteContenuFlashcard}
        \begin{seqBoiteFillContenuFlashcard}\end{seqBoiteFillContenuFlashcard}
        """
        fiches = parser_tex(tex, 'N10')
        codes = sorted(f.code_objectif for f in fiches)
        assert codes == ['02', '03']

    def test_deux_fiches_meme_objectif_fusionnees(self):
        """Deux flashcards distinctes pour le même objectif → fusion."""
        fiches = parser_tex(_TEX_DEUX_FICHES_PAR_OBJ, 'N10')
        assert len(fiches) == 1  # une seule fiche pour Obj 04
        assert fiches[0].code_objectif == '04'
        assert len(fiches[0].zones) == 2
        assert 'Premier bloc' in fiches[0].zones[0].corps
        assert 'Deuxième bloc' in fiches[0].zones[1].corps

    def test_fichier_vide(self):
        assert parser_tex('', 'N10') == []
        assert parser_tex('\\documentclass{article}\\begin{document}\\end{document}', 'N10') == []

    def test_zone_avant_titre_ignoree(self):
        """Une zone avant tout \\seqBoiteTitreFlashcard est ignorée."""
        tex = r"""
        \seqSetCodeSequence{S01}
        \begin{seqBoiteContenuFlashcard}[titre=Orphelin]Orphelin\end{seqBoiteContenuFlashcard}
        \seqBoiteTitreFlashcard{02}{}
        \begin{seqBoiteContenuFlashcard}[titre=A]X\end{seqBoiteContenuFlashcard}
        \begin{seqBoiteFillContenuFlashcard}\end{seqBoiteFillContenuFlashcard}
        """
        fiches = parser_tex(tex, 'N10')
        # La zone "Orphelin" n'est pas attribuée
        assert len(fiches) == 1
        assert fiches[0].code_objectif == '02'
        assert all('Orphelin' not in z.corps for z in fiches[0].zones)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Service fiches_import (import en BDD)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def base(conn):
    """Setup minimal pour les tests d'import en BDD."""
    conn.executescript("""
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
            ('sn1', 'N10', 'S01');
        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
            ('pt1', 'sn1', 1);
        INSERT INTO objectifs (id, partie_id, code, nom) VALUES
            ('ob02', 'pt1', '02', 'Connaître X'),
            ('ob03', 'pt1', '03', 'Calculer X');
        -- Pas d'objectif 04 : pour tester Q7-d (objectif introuvable)
    """)
    conn.commit()
    return conn


class TestImporter:
    def test_creation_basique(self, base):
        rapport = importer_fiches(
            base, contenu_tex=_TEX_SIMPLE, niveau='N10',
        )
        assert rapport.fiches_creees == 2  # ob02 + ob03
        assert rapport.fiches_etendues == 0
        assert rapport.zones_ajoutees == 3  # 2 + 1
        assert rapport.objectifs_introuvables == []

        # Vérifier en BDD
        n_fiches = base.execute("SELECT COUNT(*) AS n FROM fiches_resume").fetchone()['n']
        assert n_fiches == 2
        n_sec = base.execute(
            "SELECT COUNT(*) AS n FROM atome_sections WHERE entite_type='fiche_resume'"
        ).fetchone()['n']
        assert n_sec == 3

    def test_objectif_introuvable_ignore(self, base):
        """Q7-d : objectif introuvable → fiche ignorée + log."""
        # _TEX_DEUX_FICHES_PAR_OBJ utilise ob04 qui n'existe pas dans la base
        rapport = importer_fiches(
            base, contenu_tex=_TEX_DEUX_FICHES_PAR_OBJ, niveau='N10',
        )
        assert rapport.fiches_creees == 0
        assert 'N10/S04/04' in rapport.objectifs_introuvables
        assert any('Objectif introuvable' in e for e in rapport.erreurs)

    def test_idempotent_par_extension(self, base):
        """Q7-c : 2e import = ajout des zones, pas de doublons de fiche."""
        # 1er import
        importer_fiches(base, contenu_tex=_TEX_SIMPLE, niveau='N10')
        assert base.execute(
            "SELECT COUNT(*) AS n FROM fiches_resume"
        ).fetchone()['n'] == 2

        # 2e import : mêmes objectifs → fiches étendues, pas dupliquées
        rapport = importer_fiches(base, contenu_tex=_TEX_SIMPLE, niveau='N10')
        assert rapport.fiches_creees == 0
        assert rapport.fiches_etendues == 2
        assert rapport.zones_ajoutees == 3

        # Toujours 2 fiches en BDD
        assert base.execute(
            "SELECT COUNT(*) AS n FROM fiches_resume"
        ).fetchone()['n'] == 2
        # Mais 6 sections (3 + 3)
        assert base.execute(
            "SELECT COUNT(*) AS n FROM atome_sections WHERE entite_type='fiche_resume'"
        ).fetchone()['n'] == 6

    def test_zones_ajoutees_avec_ordre_correct(self, base):
        """Les zones ajoutées en 2e import ont un ordre supérieur aux
        zones déjà présentes."""
        importer_fiches(base, contenu_tex=_TEX_SIMPLE, niveau='N10')
        importer_fiches(base, contenu_tex=_TEX_SIMPLE, niveau='N10')
        # Pour la fiche Obj 02 (qui a 2 zones par import)
        fiche02_id = base.execute(
            "SELECT id FROM fiches_resume WHERE objectif_id = 'ob02'"
        ).fetchone()['id']
        ordres = [r['ordre'] for r in base.execute(
            "SELECT ordre FROM atome_sections "
            "WHERE entite_type = 'fiche_resume' AND entite_id = ? ORDER BY ordre",
            (fiche02_id,),
        )]
        assert ordres == [0, 1, 2, 3]


class TestRoutesPreferences:
    """Tests d'intégration via le client Flask global (conftest.py)."""

    def test_lister_seed(self, client):
        """Le seed du schéma pose 3 titres de zone par défaut."""
        rep = client.get('/api/preferences/titre_zone_fiche')
        assert rep.status_code == 200
        items = rep.get_json()['items']
        valeurs = [i['valeur'] for i in items]
        assert 'Définition' in valeurs
        assert 'Propriété' in valeurs
        assert 'Méthode' in valeurs

    def test_ajouter_modifier_supprimer(self, client):
        # POST
        r = client.post('/api/preferences/titre_zone_fiche',
                        json={'valeur': 'Démo'})
        assert r.status_code == 201
        item_id = r.get_json()['id']
        # PUT
        r = client.put(f'/api/preferences/items/{item_id}',
                       json={'valeur': 'Démonstration'})
        assert r.status_code == 200
        assert r.get_json()['valeur'] == 'Démonstration'
        # DELETE
        r = client.delete(f'/api/preferences/items/{item_id}')
        assert r.status_code == 200

    def test_valeur_unique(self, client):
        r = client.put('/api/preferences/valeur/test_unique',
                       json={'valeur': '/path/x'})
        assert r.status_code == 200
        r = client.get('/api/preferences/valeur/test_unique')
        assert r.status_code == 200
        assert r.get_json()['valeur'] == '/path/x'

    def test_ajouter_valeur_vide_400(self, client):
        r = client.post('/api/preferences/titre_zone_fiche',
                        json={'valeur': '   '})
        assert r.status_code == 400


class TestRouteImportFiches:
    """Tests d'intégration de la route POST /api/admin/fiches/import."""

    @pytest.fixture
    def setup_obj(self, sqlite_store):
        """Crée une séquence + parties + objectifs pour permettre l'import."""
        with sqlite3.connect(sqlite_store.db_path) as c:
            c.executescript("""
                INSERT INTO sequences_par_niveau (id, niveau, sequence_code)
                VALUES ('sn_imp', 'N10', 'S01');
                INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                VALUES ('pt_imp', 'sn_imp', 1);
                INSERT INTO objectifs (id, partie_id, code, nom)
                VALUES
                    ('ob_imp_02', 'pt_imp', '02', 'Connaître'),
                    ('ob_imp_03', 'pt_imp', '03', 'Calculer');
            """)
            c.commit()
        return None

    def test_import_succes(self, client, setup_obj):
        data = {
            'fichier': (io.BytesIO(_TEX_SIMPLE.encode('utf-8')), 'test.tex'),
            'niveau': 'N10',
        }
        r = client.post('/api/admin/fiches/import',
                        data=data, content_type='multipart/form-data')
        assert r.status_code == 200
        rep = r.get_json()
        assert rep['ok'] is True
        rap = rep['rapport']
        assert rap['fiches_creees'] == 2
        assert rap['zones_ajoutees'] == 3

    def test_fichier_manquant(self, client):
        r = client.post('/api/admin/fiches/import',
                        data={'niveau': 'N10'},
                        content_type='multipart/form-data')
        assert r.status_code == 400
        assert r.get_json()['code'] == 'fichier_manquant'

    def test_niveau_invalide(self, client):
        data = {
            'fichier': (io.BytesIO(b'\\seqSetCodeSequence{S01}'), 't.tex'),
            'niveau': 'X',
        }
        r = client.post('/api/admin/fiches/import',
                        data=data, content_type='multipart/form-data')
        assert r.status_code == 400
        assert r.get_json()['code'] == 'niveau_invalide'
