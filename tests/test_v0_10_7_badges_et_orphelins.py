"""tests/test_v0_10_7_badges_et_orphelins.py — v0.10.7

Tests pour :
  1. services/liaisons_atomes.py — calcul des liaisons obj_lies
     (notions, méthodes, exercices)
  2. scripts/lister_atomes_orphelins.py — détection SANS_SCOPE / SANS_LIEN
"""

from __future__ import annotations
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Schéma minimal ──────────────────────────────────────────────────────────


_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE sequences_par_niveau (
    id TEXT PRIMARY KEY, niveau TEXT, sequence_code TEXT
);
CREATE TABLE sequence_parties (
    id TEXT PRIMARY KEY,
    sequence_par_niveau_id TEXT REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    numero INTEGER
);
CREATE TABLE methodes (
    id TEXT PRIMARY KEY, titre TEXT,
    niveau TEXT NOT NULL DEFAULT '',
    sequence TEXT NOT NULL DEFAULT '',
    fichier TEXT NOT NULL DEFAULT ''
);
CREATE TABLE notions (
    id TEXT PRIMARY KEY, titre TEXT,
    niveau TEXT NOT NULL DEFAULT '',
    sequence TEXT NOT NULL DEFAULT '',
    fichier TEXT NOT NULL DEFAULT ''
);
CREATE TABLE exercices (
    id TEXT PRIMARY KEY, serie TEXT,
    niveau TEXT NOT NULL DEFAULT '',
    sequence TEXT NOT NULL DEFAULT ''
);
CREATE TABLE objectifs (
    id TEXT PRIMARY KEY,
    partie_id TEXT REFERENCES sequence_parties(id) ON DELETE CASCADE,
    code TEXT,
    nom TEXT,
    methode_id TEXT REFERENCES methodes(id) ON DELETE SET NULL
);
CREATE TABLE objectif_notions (
    objectif_id TEXT REFERENCES objectifs(id) ON DELETE CASCADE,
    notion_id TEXT REFERENCES notions(id) ON DELETE CASCADE,
    ordre INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, notion_id)
);
CREATE TABLE objectif_exos (
    objectif_id TEXT REFERENCES objectifs(id) ON DELETE CASCADE,
    serie TEXT,
    exercice_id TEXT REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, serie, ordre)
);

-- v0.13.6.10 : table des liens parties (R/EA) pour les exos.
-- Nécessaire car lister_liens_par_exercice consulte cette table en plus
-- de objectif_exos pour produire le champ `liens` complet.
CREATE TABLE partie_exos_revision_approche (
    partie_id    TEXT REFERENCES sequence_parties(id) ON DELETE CASCADE,
    exercice_id  TEXT REFERENCES exercices(id) ON DELETE RESTRICT,
    type         TEXT NOT NULL CHECK (type IN ('R', 'EA')),
    ordre        INTEGER NOT NULL DEFAULT 1,
    origin_niveau TEXT,
    origin_seq    TEXT,
    origin_serie  TEXT,
    origin_num    INTEGER,
    PRIMARY KEY (partie_id, exercice_id, type)
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    c.executescript("""
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
            ('sn_S03', 'N11', 'S03'),
            ('sn_S05', 'N11', 'S05'),
            ('sn_N10S04', 'N10', 'S04');
        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
            ('pt_S03_1', 'sn_S03', 1),
            ('pt_S05_1', 'sn_S05', 1),
            ('pt_N10S04_1', 'sn_N10S04', 1);
        INSERT INTO methodes (id, titre, niveau, sequence) VALUES
            ('me_a', 'Méthode A', 'N11', 'S03'),
            ('me_b', 'Méthode B', 'N11', 'S03');
        INSERT INTO notions (id, titre, niveau, sequence) VALUES
            ('no_a', 'Notion A', 'N11', 'S03'),
            ('no_b', 'Notion B', 'N11', 'S03');
        INSERT INTO exercices (id, serie, niveau, sequence) VALUES
            ('ex_local', 'avancé', 'N11', 'S03'),
            ('ex_n10',   'avancé', 'N10', 'S04');
        INSERT INTO objectifs (id, partie_id, code, nom, methode_id) VALUES
            ('ob_S03_02', 'pt_S03_1', '02', 'Calculer A', 'me_a'),
            ('ob_S03_12', 'pt_S03_1', '12', 'Calculer B', NULL),
            ('ob_S05_02', 'pt_S05_1', '02', 'Autre',      NULL);
        INSERT INTO objectif_notions (objectif_id, notion_id) VALUES
            ('ob_S03_02', 'no_a'),
            ('ob_S03_12', 'no_a');
        INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) VALUES
            ('ob_S03_02', 'A', 'ex_local', 1),
            ('ob_S03_02', 'R', 'ex_n10', 1);
    """)
    c.commit()
    yield c
    c.close()


# ═══════════════════════════════════════════════════════════════════════════
# 1. liaisons_atomes — calcul des obj_lies
# ═══════════════════════════════════════════════════════════════════════════


from services.liaisons_atomes import (
    lister_liens_par_notion,
    lister_liens_par_methode,
    lister_liens_par_exercice,
    enrichir_liste_atomes,
)


class TestLiensNotion:
    def test_notion_liee_a_plusieurs_obj(self, conn):
        """no_a est liée à 2 obj de S03.

        v0.13.6.10 — Le format est maintenant un objet structuré
        {type:'obj', niveau, sequence, code} au lieu d'une string
        'N11·S03·02'.
        """
        liens = lister_liens_par_notion(conn)
        assert 'no_a' in liens
        codes = sorted(l['code'] for l in liens['no_a'])
        assert codes == ['02', '12']
        # Tous les liens d'une notion ont le même type 'obj'
        assert all(l['type'] == 'obj' for l in liens['no_a'])
        assert all(l['niveau'] == 'N11' and l['sequence'] == 'S03'
                   for l in liens['no_a'])

    def test_notion_non_liee_absente(self, conn):
        """no_b n'est liée à aucun obj → non présente dans le dict."""
        liens = lister_liens_par_notion(conn)
        assert 'no_b' not in liens


class TestLiensMethode:
    def test_methode_liee_format_objet(self, conn):
        liens = lister_liens_par_methode(conn)
        assert len(liens['me_a']) == 1
        l = liens['me_a'][0]
        # v0.13.6.11 — Le champ `nom` (libellé objectif) est inclus.
        assert l == {'type': 'obj', 'niveau': 'N11',
                     'sequence': 'S03', 'code': '02',
                     'nom': 'Calculer A'}

    def test_methode_non_liee_absente(self, conn):
        liens = lister_liens_par_methode(conn)
        assert 'me_b' not in liens


class TestLiensExercice:
    def test_exo_local(self, conn):
        liens = lister_liens_par_exercice(conn)
        assert len(liens['ex_local']) == 1
        l = liens['ex_local'][0]
        assert l == {'type': 'obj', 'niveau': 'N11',
                     'sequence': 'S03', 'code': '02',
                     'nom': 'Calculer A'}

    def test_exo_revision_format_complet(self, conn):
        """ex_n10 est utilisé en révision dans S03 → lien obj
        avec niveau/séquence de l'OBJ qui le référence."""
        liens = lister_liens_par_exercice(conn)
        assert len(liens['ex_n10']) == 1
        l = liens['ex_n10'][0]
        # L'exo vient de N10/S04 mais est UTILISÉ par un obj de N11/S03.
        # Le lien renvoyé est celui de l'OBJ qui le référence.
        assert l == {'type': 'obj', 'niveau': 'N11',
                     'sequence': 'S03', 'code': '02',
                     'nom': 'Calculer A'}

    def test_exo_lien_partie(self, conn):
        """v0.13.6.10 — Un exo rattaché à une partie via la table
        partie_exos_revision_approche apparaît avec type='part'."""
        # Insert un lien R via partie_exos_revision_approche
        conn.execute("""
            INSERT INTO partie_exos_revision_approche
                (partie_id, exercice_id, type, ordre,
                 origin_niveau, origin_seq, origin_serie, origin_num)
            VALUES ('pt_S05_1', 'ex_n10', 'R', 1, 'N10', 'S04', 'A', 1)
        """)
        liens = lister_liens_par_exercice(conn)
        # ex_n10 a maintenant 2 liens : 1 obj (existait avant) + 1 part
        parts = [l for l in liens['ex_n10'] if l['type'] == 'part']
        assert len(parts) == 1
        assert parts[0] == {'type': 'part', 'niveau': 'N11',
                            'sequence': 'S05', 'numero': 1}


class TestEnrichirListe:
    def test_enrichit_notions(self, conn):
        """v0.13.6.10 — Le champ ajouté est `liens` (et non `obj_lies`)."""
        liste = [{'id': 'no_a', 'titre': 'Notion A'},
                 {'id': 'no_b', 'titre': 'Notion B'}]
        enrichir_liste_atomes(conn, liste, 'notion')
        # no_a a 2 liens
        codes_a = sorted(l['code'] for l in liste[0]['liens'])
        assert codes_a == ['02', '12']
        # no_b n'en a aucun
        assert liste[1]['liens'] == []

    def test_enrichit_methodes(self, conn):
        liste = [{'id': 'me_a'}, {'id': 'me_b'}]
        enrichir_liste_atomes(conn, liste, 'methode')
        # v0.13.6.11 — `nom` est inclus dans les liens obj
        assert liste[0]['liens'] == [
            {'type': 'obj', 'niveau': 'N11', 'sequence': 'S03',
             'code': '02', 'nom': 'Calculer A'}
        ]
        assert liste[1]['liens'] == []

    def test_type_inconnu_leve(self, conn):
        with pytest.raises(ValueError):
            enrichir_liste_atomes(conn, [], 'inconnu')


class TestCardinaliteUnObjAvecNom:
    """v0.13.6.11 (chantier B) — Pour le bouton « reprendre titre objectif »,
    le frontend a besoin de :
    - savoir si l'atome a EXACTEMENT 1 lien de type='obj' (cardinalité 1:1)
    - récupérer le `nom` de l'objectif lié

    Ces tests vérifient que ces deux informations sont bien fournies par
    `liens` côté serveur, sans calcul côté client.
    """

    def test_methode_a_un_seul_obj_avec_nom(self, conn):
        liens = lister_liens_par_methode(conn)
        obj_liens = [l for l in liens['me_a'] if l['type'] == 'obj']
        assert len(obj_liens) == 1
        assert obj_liens[0]['nom'] == 'Calculer A'

    def test_notion_a_plusieurs_obj_pas_de_reprise(self, conn):
        """no_a est liée à 2 obj — le frontend doit voir qu'il n'y a
        PAS exactement 1 lien obj et donc ne pas proposer la reprise."""
        liens = lister_liens_par_notion(conn)
        obj_liens = [l for l in liens['no_a'] if l['type'] == 'obj']
        assert len(obj_liens) == 2  # cardinalité > 1 : pas de reprise

    def test_nom_chaine_vide_si_obj_sans_libelle(self, conn):
        """Si l'objectif lié n'a pas de nom renseigné, on récupère ''
        (le frontend décide de ne pas proposer la reprise)."""
        # On modifie l'obj ob_S03_02 pour avoir nom = NULL
        conn.execute("UPDATE objectifs SET nom = NULL WHERE id = 'ob_S03_02'")
        liens = lister_liens_par_methode(conn)
        assert liens['me_a'][0]['nom'] == ''


# ═══════════════════════════════════════════════════════════════════════════
# 2. Script lister_atomes_orphelins
# ═══════════════════════════════════════════════════════════════════════════


def _chemin_script_orphelins(racine: Path) -> str:
    """Chemin absolu du script lister_atomes_orphelins.py.

    On invoque par chemin direct plutôt que par `python -m
    scripts.lister_atomes_orphelins` parce que les distributions Python
    embeddable (cas de outils\\python\\ sur la clé USB) utilisent un
    fichier `._pth` qui fige sys.path et ignore à la fois le CWD du
    subprocess et la variable PYTHONPATH. Conséquence : `python -m
    scripts.xxx` ne trouve pas le package depuis un subprocess, même
    avec `cwd=racine` et `env={'PYTHONPATH': racine}`. L'invocation par
    chemin de fichier shunte entièrement la résolution de package.
    """
    return str(racine / "scripts" / "lister_atomes_orphelins.py")


class TestScriptOrphelins:
    @pytest.fixture
    def db_test(self, tmp_path):
        """Crée une base de test minimale et retourne son chemin."""
        db = tmp_path / "test.db"
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        c.executescript(_SCHEMA)
        c.executescript("""
            INSERT INTO notions (id, titre, niveau, sequence) VALUES
                ('n_orph',  'Sans scope',          '',    ''),
                ('n_iso',   'Avec scope sans lien','N11', 'S03'),
                ('n_liee',  'Liée correctement',   'N11', 'S03');
            INSERT INTO methodes (id, titre, niveau, sequence) VALUES
                ('m_orph',  'Sans scope',          '',    ''),
                ('m_iso',   'Avec scope sans lien','N11', 'S03'),
                ('m_liee',  'Liée',                'N11', 'S03');
            INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
                ('sn1', 'N11', 'S03');
            INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
                ('pt1', 'sn1', 1);
            INSERT INTO objectifs (id, partie_id, code, nom, methode_id) VALUES
                ('ob1', 'pt1', '02', 'X', 'm_liee');
            INSERT INTO objectif_notions (objectif_id, notion_id) VALUES
                ('ob1', 'n_liee');
        """)
        c.commit()
        c.close()
        return db

    def test_script_execute(self, db_test):
        """Le script s'exécute, sort un texte non vide, code retour 0."""
        racine = Path(__file__).parent.parent
        r = subprocess.run(
            [sys.executable, _chemin_script_orphelins(racine),
             "--db", str(db_test)],
            cwd=str(racine), capture_output=True, text=True,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        assert "Notions orphelines" in r.stdout
        assert "Méthodes orphelines" in r.stdout

    def test_script_detecte_orphelins(self, db_test):
        """Vérifie que les bons atomes sont signalés."""
        racine = Path(__file__).parent.parent
        r = subprocess.run(
            [sys.executable, _chemin_script_orphelins(racine),
             "--db", str(db_test)],
            cwd=str(racine), capture_output=True, text=True,
        )
        # Atomes orphelins (SANS_SCOPE ou SANS_LIEN)
        assert "n_orph" in r.stdout
        assert "n_iso" in r.stdout
        assert "m_orph" in r.stdout
        assert "m_iso" in r.stdout
        # Atomes corrects (présents en BDD mais pas dans le rapport)
        assert "n_liee" not in r.stdout
        assert "m_liee" not in r.stdout

    def test_script_db_introuvable(self, tmp_path):
        racine = Path(__file__).parent.parent
        r = subprocess.run(
            [sys.executable, _chemin_script_orphelins(racine),
             "--db", str(tmp_path / "nexiste.db")],
            cwd=str(racine), capture_output=True, text=True,
        )
        assert r.returncode == 2
        assert "introuvable" in r.stderr
