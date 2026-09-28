r"""
tests/test_configuration.py — Tests du module de configuration.

Couvre :
  - Lecture par défaut (fichier absent)
  - Persistance après écriture
  - Rejet des clés inconnues
  - Robustesse au JSON corrompu
  - Helpers typés (chemin_sources_livrets, timeout_compilation, ...)
"""

from __future__ import annotations
import pytest
from pathlib import Path

from services.configuration import Configuration, CLES_DEFAUT, NOM_FICHIER_CONFIG


class TestLectureParDefaut:

    def test_fichier_absent_retourne_defauts(self, tmp_path):
        config = Configuration(tmp_path)
        assert config.charger() == CLES_DEFAUT

    def test_fichier_corrompu_retourne_defauts(self, tmp_path):
        (tmp_path / NOM_FICHIER_CONFIG).write_text(
            'ceci n est pas du JSON',
            encoding='utf-8',
        )
        config = Configuration(tmp_path)
        assert config.charger() == CLES_DEFAUT

    def test_fichier_liste_retourne_defauts(self, tmp_path):
        """Si JSON valide mais pas un dict, retour aux défauts."""
        (tmp_path / NOM_FICHIER_CONFIG).write_text('[1,2,3]', encoding='utf-8')
        config = Configuration(tmp_path)
        assert config.charger() == CLES_DEFAUT


class TestPersistance:

    def test_ecriture_et_relecture(self, tmp_path):
        config = Configuration(tmp_path)
        config.enregistrer({'timeout_compilation_s': 60})

        # Nouvelle instance → relit depuis le disque
        config2 = Configuration(tmp_path)
        assert config2.charger()['timeout_compilation_s'] == 60

    def test_ecriture_partielle_preserve_autres_cles(self, tmp_path):
        config = Configuration(tmp_path)
        config.enregistrer({'chemin_sources_livrets': '/tmp/src'})
        config.enregistrer({'timeout_compilation_s': 45})

        final = config.charger()
        assert final['chemin_sources_livrets'] == '/tmp/src'
        assert final['timeout_compilation_s'] == 45

    def test_ecriture_atomique_cree_data_dir(self, tmp_path):
        """Si data_dir n'existe pas, il est créé."""
        data_dir = tmp_path / 'sous' / 'dossier'
        config = Configuration(data_dir)
        config.enregistrer({'timeout_compilation_s': 10})
        assert data_dir.is_dir()
        assert (data_dir / NOM_FICHIER_CONFIG).is_file()


class TestRejetClesInconnues:

    def test_cle_inconnue_ignoree(self, tmp_path):
        config = Configuration(tmp_path)
        config.enregistrer({'cle_pirate': 'x'})
        assert 'cle_pirate' not in config.charger()

    def test_cle_inconnue_en_lecture_retourne_defaut(self, tmp_path):
        config = Configuration(tmp_path)
        assert config.get('cle_inexistante', 'ma_valeur_par_defaut') == 'ma_valeur_par_defaut'

    def test_mix_cles_connues_inconnues(self, tmp_path):
        """On enregistre un mix, seules les connues doivent être retenues."""
        config = Configuration(tmp_path)
        result = config.enregistrer({
            'timeout_compilation_s': 99,
            'cle_piratee': 'hack',
        })
        assert result['timeout_compilation_s'] == 99
        assert 'cle_piratee' not in result


class TestHelpersTypes:

    def test_chemin_sources_livrets_vide(self, tmp_path):
        config = Configuration(tmp_path)
        assert config.chemin_sources_livrets() is None

    def test_chemin_sources_livrets_valide(self, tmp_path):
        # Un dossier qui existe vraiment
        sources = tmp_path / 'sources'
        sources.mkdir()
        config = Configuration(tmp_path)
        config.enregistrer({'chemin_sources_livrets': str(sources)})
        assert config.chemin_sources_livrets() == sources

    def test_chemin_sources_livrets_inexistant(self, tmp_path):
        """Un chemin configuré mais qui n'existe pas → None (défensif)."""
        config = Configuration(tmp_path)
        config.enregistrer({'chemin_sources_livrets': '/chemin/qui/nexiste/pas'})
        assert config.chemin_sources_livrets() is None

    def test_chemin_pdflatex_par_defaut(self, tmp_path):
        assert Configuration(tmp_path).chemin_pdflatex() is None

    def test_chemin_pdflatex_defini(self, tmp_path):
        config = Configuration(tmp_path)
        config.enregistrer({'chemin_pdflatex': '/usr/bin/pdflatex'})
        assert config.chemin_pdflatex() == '/usr/bin/pdflatex'

    def test_timeout_par_defaut(self, tmp_path):
        # v0.10 — Les défauts sont 30 (court) et 300 (long).
        config = Configuration(tmp_path)
        assert config.timeout_compilation_court() == 30
        assert config.timeout_compilation_long() == 300
        # Alias rétrocompatible
        assert config.timeout_compilation() == 30

    def test_timeout_court_configure(self, tmp_path):
        # v0.10 — Nouvelle clé timeout_compilation_court_s.
        config = Configuration(tmp_path)
        config.enregistrer({'timeout_compilation_court_s': 60})
        assert config.timeout_compilation_court() == 60
        assert config.timeout_compilation() == 60   # alias

    def test_timeout_long_configure(self, tmp_path):
        config = Configuration(tmp_path)
        config.enregistrer({'timeout_compilation_long_s': 600})
        assert config.timeout_compilation_long() == 600

    def test_timeout_migration_ancienne_cle(self, tmp_path):
        """v0.10 — Une config écrite par une version antérieure ne contient
        que `timeout_compilation_s`. La méthode `timeout_compilation_court()`
        doit retomber sur cette ancienne clé. On simule en écrivant le JSON
        à la main (pas via enregistrer, qui matérialiserait les défauts)."""
        import json
        (tmp_path / NOM_FICHIER_CONFIG).write_text(
            json.dumps({'timeout_compilation_s': 60}),
            encoding='utf-8',
        )
        assert Configuration(tmp_path).timeout_compilation_court() == 60

    def test_timeout_court_prioritaire_sur_ancienne_cle(self, tmp_path):
        """Quand les deux clés coexistent, la nouvelle prime."""
        import json
        (tmp_path / NOM_FICHIER_CONFIG).write_text(
            json.dumps({
                'timeout_compilation_s': 60,
                'timeout_compilation_court_s': 90,
            }),
            encoding='utf-8',
        )
        assert Configuration(tmp_path).timeout_compilation_court() == 90

    def test_timeout_valeur_invalide_retombe_sur_defaut(self, tmp_path):
        """Si la valeur est non convertible en int, retour à 30."""
        import json
        (tmp_path / NOM_FICHIER_CONFIG).write_text(
            json.dumps({'timeout_compilation_court_s': 'pas_un_int'}),
            encoding='utf-8',
        )
        assert Configuration(tmp_path).timeout_compilation_court() == 30

    def test_timeout_minimum_1(self, tmp_path):
        """Un timeout ≤ 0 est remonté à 1 seconde."""
        config = Configuration(tmp_path)
        config.enregistrer({'timeout_compilation_court_s': 0})
        assert config.timeout_compilation_court() == 1
        config.enregistrer({'timeout_compilation_long_s': 0})
        assert config.timeout_compilation_long() == 1


# ── v0.9 — Résolution depuis chemin_racine_seqenseigne ──────────────────────

class TestResolutionRacineV09:
    """v0.9 — La racine `chemin_racine_seqenseigne` sert d'ancrage à tous
    les chemins applicatifs. Si un chemin spécifique (chemin_pdflatex,
    chemin_sources_livrets, chemin_paquet, chemin_reference_sequences) est
    défini explicitement, il a priorité (override). Sinon il est dérivé.

    Cas d'usage concret testé : passer du PC maison (D:) au PC du travail
    (E:) en ne touchant qu'à la racine, sans réécrire les 4 chemins.
    """

    def test_racine_seule_derive_les_4_chemins(self, tmp_path):
        """Avec la racine seule définie, les 4 chemins dérivés sont calculés."""
        config = Configuration(tmp_path)
        config.enregistrer({'chemin_racine_seqenseigne': str(tmp_path)})
        # Sources : <racine>/sequences
        assert config._resoudre_chemin('chemin_sources_livrets') == \
            str(tmp_path / 'sequences')
        # pdflatex : <racine>/outils/MikTex/.../pdflatex.exe
        pdf = config._resoudre_chemin('chemin_pdflatex')
        assert pdf.startswith(str(tmp_path))
        assert pdf.endswith('pdflatex.exe')
        # Paquet : <racine>/reference/paquet
        assert config._resoudre_chemin('chemin_paquet') == \
            str(tmp_path / 'reference' / 'paquet')
        # Référence séquences : <racine>/reference/sequences
        assert config._resoudre_chemin('chemin_reference_sequences') == \
            str(tmp_path / 'reference' / 'sequences')

    def test_override_individuel_prime_sur_derivation(self, tmp_path):
        """Quand un chemin spécifique est défini, il l'emporte sur la dérivation."""
        config = Configuration(tmp_path)
        custom = '/opt/seqenseigne-custom/sources'
        config.enregistrer({
            'chemin_racine_seqenseigne': str(tmp_path),
            'chemin_sources_livrets':    custom,
        })
        # Le sources spécifique gagne
        assert config._resoudre_chemin('chemin_sources_livrets') == custom
        # Les autres restent dérivés
        assert config._resoudre_chemin('chemin_paquet') == \
            str(tmp_path / 'reference' / 'paquet')

    def test_pas_de_racine_pas_d_override_renvoie_vide(self, tmp_path):
        """Sans racine ni override : chaîne vide (= comportement v0.8.x)."""
        config = Configuration(tmp_path)
        assert config._resoudre_chemin('chemin_sources_livrets') == ''
        assert config._resoudre_chemin('chemin_pdflatex') == ''
        assert config._resoudre_chemin('chemin_paquet') == ''
        assert config._resoudre_chemin('chemin_reference_sequences') == ''

    def test_changement_de_racine_repercute_partout(self, tmp_path):
        """Scénario PC maison → PC du travail : changer juste la racine."""
        # Simulation maison
        (tmp_path / 'maison').mkdir()
        (tmp_path / 'maison' / 'sequences').mkdir()
        (tmp_path / 'travail').mkdir()
        (tmp_path / 'travail' / 'sequences').mkdir()

        config = Configuration(tmp_path)
        config.enregistrer({'chemin_racine_seqenseigne': str(tmp_path / 'maison')})
        assert config.chemin_sources_livrets() == tmp_path / 'maison' / 'sequences'

        # Bascule vers le travail : on change juste la racine
        config.enregistrer({'chemin_racine_seqenseigne': str(tmp_path / 'travail')})
        assert config.chemin_sources_livrets() == tmp_path / 'travail' / 'sequences'

    def test_chemin_racine_seqenseigne_helper(self, tmp_path):
        """Le helper renvoie un Path validé (None si dossier inexistant)."""
        config = Configuration(tmp_path)
        # Pas de racine
        assert config.chemin_racine_seqenseigne() is None
        # Racine vers chemin inexistant : None
        config.enregistrer({'chemin_racine_seqenseigne': '/nope/nope'})
        assert config.chemin_racine_seqenseigne() is None
        # Racine valide
        config.enregistrer({'chemin_racine_seqenseigne': str(tmp_path)})
        assert config.chemin_racine_seqenseigne() == tmp_path

    def test_chemin_paquet_helper(self, tmp_path):
        """Le helper chemin_paquet() renvoie une chaîne (vide ou résolue)."""
        config = Configuration(tmp_path)
        assert config.chemin_paquet() == ''
        config.enregistrer({'chemin_racine_seqenseigne': str(tmp_path)})
        assert config.chemin_paquet() == str(tmp_path / 'reference' / 'paquet')
        # Override par champ
        config.enregistrer({'chemin_paquet': '/explicit/paquet'})
        assert config.chemin_paquet() == '/explicit/paquet'

    def test_chemin_reference_sequences_helper(self, tmp_path):
        """Idem pour chemin_reference_sequences()."""
        config = Configuration(tmp_path)
        assert config.chemin_reference_sequences() == ''
        config.enregistrer({'chemin_racine_seqenseigne': str(tmp_path)})
        assert config.chemin_reference_sequences() == \
            str(tmp_path / 'reference' / 'sequences')
        config.enregistrer({'chemin_reference_sequences': '/explicit/ref'})
        assert config.chemin_reference_sequences() == '/explicit/ref'

    def test_chemin_pdflatex_derive_de_la_racine(self, tmp_path):
        """Le pdflatex est dérivé sans validation d'existence (cas USB
        non branchée → on retourne quand même la chaîne et c'est le
        compilateur qui détectera l'absence)."""
        config = Configuration(tmp_path)
        config.enregistrer({'chemin_racine_seqenseigne': str(tmp_path)})
        pdf = config.chemin_pdflatex()
        assert pdf is not None
        assert pdf.endswith('pdflatex.exe')

    def test_override_vide_explicite_retombe_sur_derivation(self, tmp_path):
        """Une chaîne vide enregistrée explicitement n'est pas un override
        (sinon impossible de revenir à la dérivation depuis l'UI)."""
        config = Configuration(tmp_path)
        config.enregistrer({
            'chemin_racine_seqenseigne': str(tmp_path),
            'chemin_paquet':             '',  # override "désactivé"
        })
        assert config.chemin_paquet() == str(tmp_path / 'reference' / 'paquet')

    def test_persistance_des_5_cles_v09(self, tmp_path):
        """Les 5 clés v0.9 sont persistées et relues correctement."""
        config = Configuration(tmp_path)
        config.enregistrer({
            'chemin_racine_seqenseigne':    '/racine',
            'chemin_sources_livrets':       '/explicit/sources',
            'chemin_pdflatex':              '/explicit/pdflatex',
            'chemin_paquet':                '/explicit/paquet',
            'chemin_reference_sequences':   '/explicit/ref',
        })
        # Relecture via une nouvelle instance
        config2 = Configuration(tmp_path)
        cfg = config2.charger()
        assert cfg['chemin_racine_seqenseigne']  == '/racine'
        assert cfg['chemin_sources_livrets']     == '/explicit/sources'
        assert cfg['chemin_pdflatex']            == '/explicit/pdflatex'
        assert cfg['chemin_paquet']              == '/explicit/paquet'
        assert cfg['chemin_reference_sequences'] == '/explicit/ref'


# ── v0.9.1 — tblr_libraries (pendant frontal de tikz_libraries) ─────────────

class TestTblrLibrariesV091:
    """v0.9.1 — Bibliothèques tabularray à charger systématiquement.

    Pendant frontal exact de tikz_libraries (v0.8.5) : même format CSV
    en config, même parsing (trim + dédup + ordre préservé).

    Cas d'usage qui a motivé l'ajout : depuis tabularray v2025A, la clé
    `measure=vbox` requiert `\\UseTblrLibrary{varwidth}` ; détecté sur
    N11/S11/Méthode 05 lors du batch méthodes du 27/04/26.
    """

    def test_tblr_libraries_par_defaut(self, tmp_path):
        """Le défaut couvre booktabs (\\toprule etc.) et varwidth (measure=)."""
        config = Configuration(tmp_path)
        libs = config.tblr_libraries()
        assert 'booktabs' in libs
        assert 'varwidth' in libs

    def test_tblr_libraries_persiste_csv(self, tmp_path):
        """La valeur stockée est une chaîne CSV, parsée à la lecture."""
        config = Configuration(tmp_path)
        config.enregistrer({'tblr_libraries': 'booktabs,varwidth,counter'})
        libs = config.tblr_libraries()
        assert libs == ['booktabs', 'varwidth', 'counter']

    def test_tblr_libraries_dedup_avec_ordre_preserve(self, tmp_path):
        """Dédup en conservant l'ordre de la première occurrence."""
        config = Configuration(tmp_path)
        config.enregistrer({
            'tblr_libraries': 'varwidth,booktabs,varwidth,counter,booktabs',
        })
        assert config.tblr_libraries() == ['varwidth', 'booktabs', 'counter']

    def test_tblr_libraries_trim_et_filtre_vides(self, tmp_path):
        """Espaces parasites trimés, entrées vides éliminées."""
        config = Configuration(tmp_path)
        config.enregistrer({
            'tblr_libraries': '  booktabs , , varwidth ,,',
        })
        assert config.tblr_libraries() == ['booktabs', 'varwidth']

    def test_tblr_libraries_chaine_vide(self, tmp_path):
        """Chaîne vide → liste vide (aucune lib chargée)."""
        config = Configuration(tmp_path)
        config.enregistrer({'tblr_libraries': ''})
        assert config.tblr_libraries() == []

    def test_tblr_libraries_valeur_non_string_retombe_sur_vide(self, tmp_path):
        """Valeur non string en config → liste vide (robustesse)."""
        import json
        (tmp_path / NOM_FICHIER_CONFIG).write_text(
            json.dumps({'tblr_libraries': 123}),  # entier corrompu
            encoding='utf-8',
        )
        assert Configuration(tmp_path).tblr_libraries() == []

    def test_tblr_independant_de_tikz(self, tmp_path):
        """Modifier l'un ne touche pas l'autre."""
        config = Configuration(tmp_path)
        config.enregistrer({'tikz_libraries': 'babel'})
        assert config.tblr_libraries() == ['booktabs', 'varwidth']  # défaut
        assert config.tikz_libraries() == ['babel']
        config.enregistrer({'tblr_libraries': 'siunitx'})
        assert config.tblr_libraries() == ['siunitx']
        assert config.tikz_libraries() == ['babel']  # inchangé


# ── v0.9.3 — atl_textarea_lignes (hauteur des textareas LaTeX) ──────────────

class TestAtlTextareaLignesV093:
    """v0.9.3 — Hauteur des textareas LaTeX dans les ateliers, en lignes.

    Remplace l'autosize sur les zones de saisie volumineuses (variables,
    énoncé, corrigé, items de section) qui faisait défiler tout le
    formulaire à chaque saut de ligne. Hauteur fixe + scroll est plus
    prévisible.

    Plancher défensif à 5 lignes pour éviter des textareas inutilisables
    si la config est mal saisie.
    """

    def test_defaut_25(self, tmp_path):
        """La valeur par défaut est 25 lignes."""
        config = Configuration(tmp_path)
        assert config.atl_textarea_lignes() == 25

    def test_persistance(self, tmp_path):
        """Une valeur enregistrée est relue par une nouvelle instance."""
        config = Configuration(tmp_path)
        config.enregistrer({'atl_textarea_lignes': 30})
        config2 = Configuration(tmp_path)
        assert config2.atl_textarea_lignes() == 30

    def test_plancher_5_lignes(self, tmp_path):
        """Une valeur trop petite est remontée au plancher."""
        config = Configuration(tmp_path)
        config.enregistrer({'atl_textarea_lignes': 2})
        assert config.atl_textarea_lignes() == 5
        config.enregistrer({'atl_textarea_lignes': 0})
        assert config.atl_textarea_lignes() == 5
        config.enregistrer({'atl_textarea_lignes': -10})
        assert config.atl_textarea_lignes() == 5

    def test_valeur_non_int_retombe_sur_defaut(self, tmp_path):
        """Une valeur non convertible en int retourne le défaut."""
        import json
        (tmp_path / NOM_FICHIER_CONFIG).write_text(
            json.dumps({'atl_textarea_lignes': 'beaucoup'}),
            encoding='utf-8',
        )
        assert Configuration(tmp_path).atl_textarea_lignes() == 25

    def test_valeur_none_retombe_sur_defaut(self, tmp_path):
        """Une valeur null en config retourne le défaut."""
        import json
        (tmp_path / NOM_FICHIER_CONFIG).write_text(
            json.dumps({'atl_textarea_lignes': None}),
            encoding='utf-8',
        )
        assert Configuration(tmp_path).atl_textarea_lignes() == 25

    def test_valeur_string_numerique_acceptee(self, tmp_path):
        """Une chaîne représentant un entier est acceptée (cas POST API
        où une valeur sérialisée comme string pourrait arriver)."""
        config = Configuration(tmp_path)
        config.enregistrer({'atl_textarea_lignes': '40'})
        assert config.atl_textarea_lignes() == 40
