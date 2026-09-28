"""Tests dédiés v0.8.5 — fix paquets externes (xltabular) + tikz_libraries
paramétrable.

Ces tests ciblent spécifiquement les changements introduits par v0.8.5 :

1. `_paquets_deja_charges_par_seqenseigne()` doit refléter ce que NOTRE
   préambule reconstruit charge réellement (PAQUETS_NOYAU + options), pas
   ce que `\\usepackage{seqenseigne}` chargerait s'il était utilisé en
   entier (table `paquet_requirepackage`). C'est ce qui empêche `xltabular`
   d'être chargé alors qu'il est correctement mappé dans
   MACROS_PAQUETS_EXTERNES.

2. `Configuration.tikz_libraries()` parse correctement la chaîne CSV en
   liste, déduplique, élimine les vides.

3. La route `/run` lit/persiste la valeur, la route `/preview` la retourne.

Les tests d'intégration sur `construire_preambule(tikz_libraries=...)` sont
dans test_preambule_atome.py (classe TestInitialisationsBibliotheques).
"""
import json
import sqlite3
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.configuration import Configuration, CLES_DEFAUT


# ── Configuration.tikz_libraries() ────────────────────────────────────────────

class TestConfigurationTikzLibraries:
    """Parsing de la chaîne CSV en liste."""

    def _config(self, tmp_path: Path, valeur=None) -> Configuration:
        """Crée une Configuration avec un fichier dédié."""
        if valeur is not None:
            (tmp_path / 'configuration.json').write_text(
                json.dumps({'tikz_libraries': valeur}), encoding='utf-8'
            )
        return Configuration(tmp_path)

    def test_defaut_couvre_usages_courants(self, tmp_path):
        """Sans config explicite, les libs courantes pour pédagogie collège
        sont chargées : babel (compat babel-french), shapes.geometric
        (diamond et autres), arrows.meta (flèches modernes), positioning
        (placement relatif), calc (coordonnées calculées)."""
        cfg = self._config(tmp_path)  # pas de fichier → défauts
        libs = cfg.tikz_libraries()
        for attendu in ('babel', 'shapes.geometric', 'arrows.meta',
                        'positioning', 'calc'):
            assert attendu in libs

    def test_chaine_simple_csv(self, tmp_path):
        cfg = self._config(tmp_path, 'babel,calc,positioning')
        assert cfg.tikz_libraries() == ['babel', 'calc', 'positioning']

    def test_espaces_trimés(self, tmp_path):
        cfg = self._config(tmp_path, '  babel ,  calc  ,positioning  ')
        assert cfg.tikz_libraries() == ['babel', 'calc', 'positioning']

    def test_entrees_vides_ignorees(self, tmp_path):
        cfg = self._config(tmp_path, 'babel,,calc, ,positioning,')
        assert cfg.tikz_libraries() == ['babel', 'calc', 'positioning']

    def test_doublons_dédoublonnés_ordre_preserve(self, tmp_path):
        cfg = self._config(tmp_path, 'babel,calc,babel,positioning,calc')
        assert cfg.tikz_libraries() == ['babel', 'calc', 'positioning']

    def test_chaine_vide_donne_liste_vide(self, tmp_path):
        cfg = self._config(tmp_path, '')
        assert cfg.tikz_libraries() == []

    def test_que_des_virgules_donne_liste_vide(self, tmp_path):
        cfg = self._config(tmp_path, ',,,, ,')
        assert cfg.tikz_libraries() == []

    def test_un_seul_element(self, tmp_path):
        cfg = self._config(tmp_path, 'babel')
        assert cfg.tikz_libraries() == ['babel']

    def test_valeur_non_chaine_donne_liste_vide(self, tmp_path):
        """Si la config est corrompue et stocke autre chose qu'une chaîne,
        on ne plante pas — on retourne juste []."""
        # Manipulation directe pour simuler une corruption
        (tmp_path / 'configuration.json').write_text(
            json.dumps({'tikz_libraries': ['déjà', 'une', 'liste']}),
            encoding='utf-8'
        )
        cfg = Configuration(tmp_path)
        assert cfg.tikz_libraries() == []


# ── _paquets_deja_charges_par_seqenseigne (fix structurel) ────────────────────

class TestPaquetsDejaChargesParSeqenseigne:
    """Le set de « paquets considérés déjà chargés » doit refléter ce que
    NOTRE préambule reconstruit charge, pas ce que seqenseigne complet
    chargerait. C'est ce qui empêche xltabular d'être marqué « déjà
    chargé » à tort et donc filtré du set des paquets à ajouter au
    préambule."""

    def test_xltabular_pas_dans_les_charges(self, tmp_path):
        """Cas central : xltabular est dans paquet_requirepackage (chargé
        par seqenseigne complet) mais PAS dans notre préambule reconstruit.
        Il ne doit donc pas être considéré comme déjà chargé."""
        from services.latex_rendu_atome import _paquets_deja_charges_par_seqenseigne
        # On donne une connexion qui SIMULE qu'xltabular est dans
        # paquet_requirepackage (cas réel en prod). Si la fonction se
        # basait toujours sur cette table, le test échouerait. Comme elle
        # se base désormais sur PAQUETS_NOYAU & co., elle ignore la table.
        conn = sqlite3.connect(':memory:')
        conn.execute("""CREATE TABLE paquet_requirepackage (
                            nom TEXT, options TEXT)""")
        conn.execute(
            "INSERT INTO paquet_requirepackage(nom, options) VALUES (?, '')",
            ('xltabular',)
        )
        conn.commit()
        charges = _paquets_deja_charges_par_seqenseigne(conn)
        assert 'xltabular' not in charges, (
            "xltabular ne doit PAS être considéré comme déjà chargé : "
            "il est dans paquet_requirepackage mais notre préambule "
            "reconstruit ne le charge pas."
        )

    def test_paquets_noyau_consideres_charges(self, tmp_path):
        """Inversement, les paquets que NOUS chargeons (ex. amsmath,
        babel, tikz, tabularray) sont bien marqués comme déjà chargés."""
        from services.latex_rendu_atome import _paquets_deja_charges_par_seqenseigne
        conn = sqlite3.connect(':memory:')
        conn.execute("""CREATE TABLE paquet_requirepackage (
                            nom TEXT, options TEXT)""")
        # Pas d'insertion : on vérifie que le résultat ne dépend PAS
        # de cette table.
        conn.commit()
        charges = _paquets_deja_charges_par_seqenseigne(conn)
        for attendu in ('amsmath', 'babel', 'tikz', 'tabularray',
                        'tcolorbox'):
            assert attendu in charges, (
                f"{attendu} fait partie de PAQUETS_NOYAU et doit être "
                "marqué comme déjà chargé."
            )

    def test_equivalences_graphics_graphicx(self):
        """Si graphics est chargé (ou graphicx), l'autre doit l'être aussi
        car ils sont fournis par le même paquet LaTeX."""
        from services.latex_rendu_atome import _paquets_deja_charges_par_seqenseigne
        conn = sqlite3.connect(':memory:')
        conn.execute("""CREATE TABLE paquet_requirepackage (
                            nom TEXT, options TEXT)""")
        conn.commit()
        charges = _paquets_deja_charges_par_seqenseigne(conn)
        # graphicx est dans PAQUETS_NOYAU, donc graphics doit être ajouté
        # par équivalence.
        assert 'graphicx' in charges
        assert 'graphics' in charges

    def test_tikz_tire_pgf_xcolor(self):
        """tikz importe automatiquement pgf, graphics, graphicx, xcolor :
        ils doivent être marqués chargés même s'ils ne sont pas dans
        PAQUETS_NOYAU explicitement."""
        from services.latex_rendu_atome import _paquets_deja_charges_par_seqenseigne
        conn = sqlite3.connect(':memory:')
        conn.execute("""CREATE TABLE paquet_requirepackage (
                            nom TEXT, options TEXT)""")
        conn.commit()
        charges = _paquets_deja_charges_par_seqenseigne(conn)
        assert 'tikz' in charges  # sanity check : tikz est noyau
        assert 'pgf' in charges
        assert 'xcolor' in charges
        assert 'graphics' in charges
        assert 'graphicx' in charges

    def test_pas_de_dependance_a_paquet_requirepackage(self):
        """Test régression : la fonction ne lit plus la table
        `paquet_requirepackage`. Pour le vérifier, on lui passe une
        connexion à une BDD qui n'a PAS cette table — elle ne doit
        pas planter."""
        from services.latex_rendu_atome import _paquets_deja_charges_par_seqenseigne
        conn = sqlite3.connect(':memory:')
        # Pas de création de paquet_requirepackage
        charges = _paquets_deja_charges_par_seqenseigne(conn)
        assert isinstance(charges, set)
        assert len(charges) > 0  # PAQUETS_NOYAU n'est pas vide

    def test_paquets_externes_pas_consideres_charges(self):
        """Les paquets qu'on n'inline PAS dans le préambule (ex.
        booktabs, hyperref, datetime, lastpage, fancyhdr) ne doivent
        PAS être marqués chargés : ils seront ajoutés à la demande
        si l'atome les utilise."""
        from services.latex_rendu_atome import _paquets_deja_charges_par_seqenseigne
        conn = sqlite3.connect(':memory:')
        conn.execute("""CREATE TABLE paquet_requirepackage (nom TEXT, options TEXT)""")
        conn.commit()
        charges = _paquets_deja_charges_par_seqenseigne(conn)
        # Ces paquets sont dans paquet_requirepackage en prod (chargés par
        # seqenseigne complet) mais NOUS ne les chargeons pas dans notre
        # préambule reconstruit. Ils doivent donc rester « non chargés »
        # pour que le mécanisme de paquets externes les ajoute à la demande.
        for non_charge in ('xltabular', 'hyperref', 'fancyhdr',
                           'lastpage', 'datetime', 'eurosym', 'booktabs'):
            assert non_charge not in charges, (
                f"{non_charge} ne doit PAS être considéré comme déjà "
                "chargé : il faut qu'il soit ajouté à la demande."
            )


# ── tikz_libraries dans CLES_DEFAUT ───────────────────────────────────────────

class TestTikzLibrariesParDefaut:
    """La clé `tikz_libraries` doit être déclarée dans CLES_DEFAUT avec
    une valeur par défaut sensée (couvrant les usages courants)."""

    def test_cle_dans_cles_defaut(self):
        assert 'tikz_libraries' in CLES_DEFAUT

    def test_defaut_est_chaine(self):
        assert isinstance(CLES_DEFAUT['tikz_libraries'], str)

    def test_defaut_contient_babel(self):
        """`babel` (anciennement v0.8.4 codée en dur) doit toujours
        être chargée par défaut pour conserver la compatibilité avec
        les notions tkz-euclide qui plantaient avec « + or - expected »."""
        assert 'babel' in CLES_DEFAUT['tikz_libraries'].split(',')

    def test_defaut_contient_shapes_geometric(self):
        """`shapes.geometric` est nécessaire pour les `\\node[decision]`
        des notions S14 (et d'autres notions à diagrammes avec des
        formes géométriques)."""
        assert 'shapes.geometric' in CLES_DEFAUT['tikz_libraries'].split(',')
