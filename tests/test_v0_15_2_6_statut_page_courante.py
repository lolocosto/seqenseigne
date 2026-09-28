"""tests/test_v0_15_2_6_statut_page_courante.py — v0.15.2.6 + v0.15.2.7

Enrichissement de `lire_statut(doc_id)` avec `page_courante` lu depuis
le `.log` pdflatex de la cible en cours.

C'est ce qui transforme un signal toutes les 25-30s (une cible compilée)
en un signal toutes les 1s (une page shippée), suffisant pour rassurer
l'utilisateur que "quelque chose bouge" (cf. retour terrain Laurent
v0.15.2.5).

v0.15.2.7 : `chemin_log_courant` pointe sur le LIVE log dans le workdir
pdflatex (atome.log), pas sur l'artefact final qui n'est écrit qu'APRÈS
la compilation.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import referentiel_documents_compilation as svc_cmp  # noqa: E402


@pytest.fixture(autouse=True)
def _isole_statuts():
    """Chaque test démarre avec un dict de statuts vierge et le nettoie
    en sortie : on évite la pollution croisée."""
    yield
    with svc_cmp._LOCK_STATUTS:
        svc_cmp._STATUTS_COMPILATION.clear()


def _placer_statut(doc_id, **kwargs):
    """Helper : place un statut en mémoire pour ce test."""
    base = svc_cmp._statut_initial(doc_id, total=3, type_document='X')
    base.update(kwargs)
    with svc_cmp._LOCK_STATUTS:
        svc_cmp._STATUTS_COMPILATION[doc_id] = base


def test_lire_statut_renvoie_none_si_inconnu():
    assert svc_cmp.lire_statut('doc_inexistant') is None


def test_lire_statut_sans_chemin_log_pas_de_page():
    """Statut au tout début, avant la première cible : pas de
    chemin_log_courant → pas d'enrichissement, pas de page_courante."""
    _placer_statut('doc1', en_cours=True, chemin_log_courant=None)
    s = svc_cmp.lire_statut('doc1')
    assert s is not None
    assert s.get('page_courante') is None


def test_lire_statut_log_inexistant_page_reste_none(tmp_path):
    """Cible démarrée mais pdflatex n'a pas encore créé atome.log :
    pas de page renvoyée, pas d'exception."""
    _placer_statut('doc2', en_cours=True,
                   chemin_log_courant=str(tmp_path / 'atome.log'))
    s = svc_cmp.lire_statut('doc2')
    assert s is not None
    assert s.get('page_courante') is None


def test_lire_statut_page_courante_lue_du_log_live(tmp_path):
    """v0.15.2.7 : on lit le LIVE log (workdir/atome.log), pas
    l'artefact final. Le test reflète ce contrat : chemin_log_courant
    pointe DIRECTEMENT sur le fichier que pdflatex écrit.
    """
    log = tmp_path / 'atome.log'
    log.write_text('intro... [1] [2] [3] some Warning [4] [5] [6] [7]\n')
    _placer_statut('doc3', en_cours=True, chemin_log_courant=str(log))
    s = svc_cmp.lire_statut('doc3')
    assert s is not None
    assert s.get('page_courante') == 7


def test_lire_statut_compilation_terminee_pas_d_enrichissement(tmp_path):
    """Une fois en_cours=False, on n'enrichit plus (économie d'I/O et
    affichage cohérent avec la fin de compilation). Garantit qu'on ne
    voit pas surgir un nb final de pages après que la compilation est
    finie."""
    log = tmp_path / 'atome.log'
    log.write_text('[1] [2] [3]\n')
    _placer_statut('doc4', en_cours=False,
                   chemin_log_courant=str(log),
                   page_courante=None)
    s = svc_cmp.lire_statut('doc4')
    assert s is not None
    assert s.get('page_courante') is None


def test_lire_statut_dict_retourne_est_une_copie():
    """Modifier le dict renvoyé ne doit pas polluer l'état interne :
    `lire_statut` doit faire une copie défensive."""
    _placer_statut('doc5', en_cours=True)
    s1 = svc_cmp.lire_statut('doc5')
    s1['fait'] = 999  # modification locale
    s2 = svc_cmp.lire_statut('doc5')
    assert s2['fait'] != 999, (
        "lire_statut doit renvoyer une copie, pas la référence interne"
    )


def test_lire_statut_evolution_page_au_fil_compilation(tmp_path):
    """Simulation d'une compilation qui avance : la page renvoyée doit
    suivre les ajouts au log (modèle d'usage côté UI qui poll à 700ms).
    Test critique du fix v0.15.2.7 : sans persistance du workdir, ce
    test ne pourrait pas être écrit car le log n'existerait pas avant
    la fin de compile."""
    log = tmp_path / 'atome.log'
    log.write_text('start [1]\n')
    _placer_statut('doc6', en_cours=True, chemin_log_courant=str(log))

    assert svc_cmp.lire_statut('doc6').get('page_courante') == 1
    log.write_text('start [1] [2] [3] [4]\n')
    assert svc_cmp.lire_statut('doc6').get('page_courante') == 4
    log.write_text('start [1] [2] [3] [4] [5] [6] [7] [8]\n')
    assert svc_cmp.lire_statut('doc6').get('page_courante') == 8


def test_lire_statut_changement_de_cible_met_a_jour_le_log_source(tmp_path):
    """v0.15.2.7 : à chaque cible le worker pose un nouveau
    `chemin_log_courant` (workdir différent par cible). La page
    affichée doit refléter le NOUVEAU log, pas l'ancien."""
    log1 = tmp_path / 's01' / 'atome.log'
    log2 = tmp_path / 's02' / 'atome.log'
    log1.parent.mkdir(parents=True)
    log2.parent.mkdir(parents=True)
    log1.write_text('[1] [2] [3] [4]\n')
    log2.write_text('[1] [2]\n')

    # Cible 1 : page 4
    _placer_statut('doc7', en_cours=True, chemin_log_courant=str(log1))
    assert svc_cmp.lire_statut('doc7').get('page_courante') == 4

    # Le worker passe à la cible suivante : nouveau chemin_log_courant
    svc_cmp._maj_statut('doc7',
                        chemin_log_courant=str(log2),
                        page_courante=None)
    assert svc_cmp.lire_statut('doc7').get('page_courante') == 2
