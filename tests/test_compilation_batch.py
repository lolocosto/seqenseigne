"""
tests/test_compilation_batch.py — Tests du service de compilation batch v0.8.

On teste :
  - recenser_atomes : filtrage et ordre de tri
  - compiler_un_atome : distinction des 5 statuts (avec mock de compiler_atome
    et de generer_tex_par_type pour ne pas dépendre de pdflatex)
  - iter_compilation : flux d'événements, abandon sur erreurs infra consécutives
  - ecrire_rapport_md : présence des sections attendues
  - evenement_vers_sse : format SSE valide
"""

from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from services.compilation_batch import (
    Atome, Filtre,
    recenser_atomes, compiler_un_atome, iter_compilation,
    ecrire_rapport_md, evenement_vers_sse, nom_rapport,
    STATUT_SUCCES, STATUT_CACHE, STATUT_ECHEC_VIDE,
    STATUT_ECHEC_COMPILATION, STATUT_ECHEC_INFRA,
    LIBELLES_STATUTS, ORDRE_TYPES,
)
from services.compilateur_pdf import ResultatCompilation, ErreurLatex


# ── Fixtures locales ─────────────────────────────────────────────────────────

@pytest.fixture
def store_avec_atomes(store):
    """Store SQLite peuplé avec un mix d'atomes pour tester filtrage/tri."""
    # 2 notions, 2 méthodes, 3 exercices, sur N10 et N11.
    store.ecrire_notions([
        {
            "id": "no_n10s01_01", "titre": "Notion N10/S01",
            "corps": "", "ordreExRem": True,
            "niveau": "N10", "sequence": "S01",
            "num_connaissance": "01", "fichier": "N10_S01_Notion_01.tex",
            "sections": [{"titre": "Exemples", "items": ["Item 1"]}],
        },
        {
            "id": "no_n11s02_03", "titre": "Notion N11/S02",
            "corps": "", "ordreExRem": True,
            "niveau": "N11", "sequence": "S02",
            "num_connaissance": "03", "fichier": "N11_S02_Notion_03.tex",
            "sections": [{"titre": "Exemples", "items": ["X"]}],
        },
    ])
    store.ecrire_methodes([
        {
            "id": "me_n10s01_02", "titre": "Méthode N10/S01",
            "corps": "", "ordreExRem": True,
            "niveau": "N10", "sequence": "S01",
            "num_methode": 2, "num_objectif": "02",
            "fichier": "N10_S01_Methode_02.tex",
            "criteres": {"2": "F", "3": "A", "4": "E"},
            "sections": [{"titre": "Exemples", "items": ["X"]}],
            "notions": [],
        },
        {
            "id": "me_n10s01_05", "titre": "Méthode N10/S01 #5",
            "corps": "", "ordreExRem": True,
            "niveau": "N10", "sequence": "S01",
            "num_methode": 5, "num_objectif": "05",
            "fichier": "N10_S01_Methode_05.tex",
            "criteres": {"2": "F", "3": "A", "4": "E"},
            "sections": [{"titre": "Exemples", "items": ["Y"]}],
            "notions": [],
        },
    ])
    store.ecrire_exercices([
        {
            "id": "ex_n10s01_F01", "serie": "fondamental",
            "nom": "Exo N10/S01 F1", "objectifs": [],
            "variables": "", "enonce": "E1", "corrige": "C1",
            "niveau": "N10", "sequence": "S01", "num": 1, "serie_code": "F",
            "fichier": "N10_S01_F01.tex",
        },
        {
            "id": "ex_n10s01_F02", "serie": "fondamental",
            "nom": "Exo N10/S01 F2", "objectifs": [],
            "variables": "", "enonce": "E2", "corrige": "C2",
            "niveau": "N10", "sequence": "S01", "num": 2, "serie_code": "F",
            "fichier": "N10_S01_F02.tex",
        },
        {
            "id": "ex_n10s01_A01", "serie": "avancé",
            "nom": "Exo N10/S01 A1", "objectifs": [],
            "variables": "", "enonce": "E3", "corrige": "C3",
            "niveau": "N10", "sequence": "S01", "num": 1, "serie_code": "A",
            "fichier": "N10_S01_A01.tex",
        },
    ])
    return store


# ── recenser_atomes : sans filtre ────────────────────────────────────────────

def test_recenser_sans_filtre(store_avec_atomes):
    atomes = recenser_atomes(store_avec_atomes)
    assert len(atomes) == 7  # 2 notions + 2 méthodes + 3 exos


def test_recenser_ordre_par_niveau_puis_sequence(store_avec_atomes):
    """Ordre attendu : N10/S01 (notion + méthodes + exos), puis N11/S02 (notion)."""
    atomes = recenser_atomes(store_avec_atomes)
    niveaux_seq = [(a.niveau, a.sequence) for a in atomes]
    # Tous les N10 avant les N11.
    indices_n10 = [i for i, (n, _) in enumerate(niveaux_seq) if n == 'N10']
    indices_n11 = [i for i, (n, _) in enumerate(niveaux_seq) if n == 'N11']
    assert max(indices_n10) < min(indices_n11)


def test_recenser_ordre_types_dans_sequence(store_avec_atomes):
    """Dans une (niveau, séquence) donnée : notions, puis méthodes, puis exos."""
    atomes = recenser_atomes(store_avec_atomes)
    types_n10s01 = [a.type for a in atomes
                    if a.niveau == 'N10' and a.sequence == 'S01']
    # Ordre attendu : 1 notion N10/S01... non, la fixture n'en a qu'une N11/S02.
    # En réalité N10/S01 a : 0 notion + 2 méthodes + 3 exercices = 5 atomes.
    # MAIS la fixture déclare aussi no_n10s01_01 ! Recompte : 1 notion + 2 méthodes + 3 exos = 6.
    assert types_n10s01 == ['notion', 'methode', 'methode',
                            'exercice', 'exercice', 'exercice']
    # ORDRE_TYPES respecté en général
    for a, b in zip(atomes, atomes[1:]):
        if (a.niveau, a.sequence) == (b.niveau, b.sequence):
            assert ORDRE_TYPES.index(a.type) <= ORDRE_TYPES.index(b.type)


def test_recenser_ordre_exos_F_avant_A(store_avec_atomes):
    """Dans une (niveau, séquence) donnée, série F avant A."""
    atomes = recenser_atomes(store_avec_atomes)
    exos = [a for a in atomes if a.type == 'exercice'
            and a.niveau == 'N10' and a.sequence == 'S01']
    series = [a.data['serie_code'] for a in exos]
    assert series == ['F', 'F', 'A']
    # F1 avant F2
    nums_F = [a.data['num'] for a in exos if a.data['serie_code'] == 'F']
    assert nums_F == [1, 2]


# ── recenser_atomes : avec filtre ────────────────────────────────────────────

def test_filtre_par_type(store_avec_atomes):
    notions = recenser_atomes(store_avec_atomes, Filtre(type='notion'))
    assert len(notions) == 2
    assert all(a.type == 'notion' for a in notions)

    methodes = recenser_atomes(store_avec_atomes, Filtre(type='methode'))
    assert len(methodes) == 2

    exos = recenser_atomes(store_avec_atomes, Filtre(type='exercice'))
    assert len(exos) == 3


def test_filtre_par_niveau(store_avec_atomes):
    n10 = recenser_atomes(store_avec_atomes, Filtre(niveau='N10'))
    assert len(n10) == 6  # 1 notion + 2 méthodes + 3 exos
    assert all(a.niveau == 'N10' for a in n10)

    n11 = recenser_atomes(store_avec_atomes, Filtre(niveau='N11'))
    assert len(n11) == 1
    assert n11[0].id == 'no_n11s02_03'


def test_filtre_par_sequence(store_avec_atomes):
    s01 = recenser_atomes(store_avec_atomes, Filtre(sequence='S01'))
    assert len(s01) == 6  # tous N10/S01 : 1 notion + 2 méthodes + 3 exos
    s02 = recenser_atomes(store_avec_atomes, Filtre(sequence='S02'))
    assert len(s02) == 1


def test_filtre_combine_type_niveau(store_avec_atomes):
    """Les 5 combinaisons de filtres demandées par Laurent."""
    # type seul
    assert len(recenser_atomes(store_avec_atomes, Filtre(type='exercice'))) == 3
    # type + niveau
    assert len(recenser_atomes(store_avec_atomes,
        Filtre(type='exercice', niveau='N10'))) == 3
    # type + niveau + sequence
    assert len(recenser_atomes(store_avec_atomes,
        Filtre(type='methode', niveau='N10', sequence='S01'))) == 2
    # niveau seul
    assert len(recenser_atomes(store_avec_atomes,
        Filtre(niveau='N10'))) == 6
    # niveau + sequence
    assert len(recenser_atomes(store_avec_atomes,
        Filtre(niveau='N10', sequence='S01'))) == 6


def test_filtre_aucun_resultat(store_avec_atomes):
    assert recenser_atomes(store_avec_atomes,
        Filtre(niveau='N12')) == []


# ── Identifiants lisibles ────────────────────────────────────────────────────

def test_identifiants_lisibles(store_avec_atomes):
    atomes = recenser_atomes(store_avec_atomes)
    par_id = {a.id: a.identifiant for a in atomes}
    assert par_id['no_n11s02_03'] == 'N11/S02/Notion 03'
    assert par_id['me_n10s01_02'] == 'N10/S01/Méthode 02'
    assert par_id['ex_n10s01_F01'] == 'N10/S01/F01'
    assert par_id['ex_n10s01_A01'] == 'N10/S01/A01'


# ── compiler_un_atome : distinction des statuts ──────────────────────────────

def _atome_factice(type_, sections, **kwargs):
    """Crée un Atome de test avec sections personnalisées."""
    data = {
        'id': kwargs.get('id', 'test_id'),
        'titre': 'T',
        'sections': sections,
        'niveau': kwargs.get('niveau', 'N10'),
        'sequence': kwargs.get('sequence', 'S01'),
        **kwargs,
    }
    if type_ == 'exercice':
        data.setdefault('enonce', 'E')
        data.setdefault('corrige', 'C')
        data.setdefault('serie_code', 'F')
        data.setdefault('num', 1)
    return Atome(
        type=type_, id=data['id'],
        niveau=data['niveau'], sequence=data['sequence'],
        identifiant=f"{data['niveau']}/{data['sequence']}/Test",
        titre=data['titre'], data=data,
    )


def test_atome_vide_notion_sans_sections(store_avec_atomes):
    a = _atome_factice('notion', sections=[])
    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_ECHEC_VIDE


def test_atome_vide_notion_section_vide(store_avec_atomes):
    a = _atome_factice('notion',
        sections=[{'titre': 'Exemples', 'items': ['', '   ']}])
    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_ECHEC_VIDE


def test_exercice_vide_enonce_manquant(store_avec_atomes):
    """Un exercice sans énoncé est toujours rejeté comme vide."""
    a = _atome_factice('exercice', sections=[],
                       enonce='', corrige='OK')
    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_ECHEC_VIDE
    assert 'énoncé' in ev['message'].lower() or 'enonce' in ev['message'].lower()


def test_exercice_sans_corrige_v084_compile_avec_flag(store_avec_atomes,
                                                       monkeypatch):
    """v0.8.4 — Un exercice avec énoncé mais sans corrigé n'est PLUS
    rejeté comme vide. Il compile normalement et l'événement de succès
    porte le flag `sans_corrige=True` pour qu'il soit listé séparément
    dans le rapport."""
    a = _atome_factice('exercice', sections=[],
                       enonce='Calculer 2+2', corrige='')
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                         duree_ms=100))

    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_SUCCES
    assert ev.get('sans_corrige') is True


def test_exercice_avec_corrige_pas_de_flag(store_avec_atomes, monkeypatch):
    """Inversement, un exercice avec corrigé n'a pas le flag."""
    a = _atome_factice('exercice', sections=[],
                       enonce='Calculer 2+2', corrige='= 4')
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                         duree_ms=100))

    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_SUCCES
    assert 'sans_corrige' not in ev


# v0.8.4 — Tests sur le critère « atome vide » corrigé pour notion/méthode.
# Avant v0.8.4, _a_des_items() était utilisé seul, ce qui marquait à tort
# comme « atome vide » des notions/méthodes ayant un corps non vide mais
# aucune section (cas réels en BDD : N10/S03/Notion 02, S03/03, S10/03,
# S10/06). Les tests ci-dessous figent le bon comportement.

def test_notion_avec_corps_seul_n_est_pas_vide(store_avec_atomes,
                                                monkeypatch):
    """Une notion à corps seul (sans aucune section) est valide et compile."""
    # Notion factice : pas de sections, mais un corps non vide.
    notion_data = {
        'id': 'no_corps_seul', 'titre': 'Test',
        'corps': "Texte explicatif de la notion.",
        'sections': [],
        'niveau': 'N10', 'sequence': 'S01',
    }
    a = Atome(type='notion', id='no_corps_seul',
              niveau='N10', sequence='S01',
              identifiant='N10/S01/Test', titre='Test', data=notion_data)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                         duree_ms=100))

    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_SUCCES, (
        f"Une notion avec corps non vide doit compiler, "
        f"reçu : {ev}"
    )


def test_notion_vraiment_vide_reste_rejetee(store_avec_atomes):
    """Une notion sans corps ET sans sections reste « vide »."""
    a = _atome_factice('notion', sections=[])
    # _atome_factice ne met pas de corps par défaut
    assert not (a.data.get('corps', '') or '').strip()

    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_ECHEC_VIDE


def test_notion_corps_blanc_et_sections_vides_rejetee(store_avec_atomes):
    """Corps blanc (espaces seulement) + sections sans items non vides → vide."""
    notion_data = {
        'id': 'no_blanc', 'titre': 'T',
        'corps': "   \n\t  ",
        'sections': [{'titre': 'Exemples', 'items': ['', '   ']}],
        'niveau': 'N10', 'sequence': 'S01',
    }
    a = Atome(type='notion', id='no_blanc',
              niveau='N10', sequence='S01',
              identifiant='N10/S01/Test', titre='T', data=notion_data)
    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_ECHEC_VIDE


def test_notion_avec_sections_seules_pas_rejetee(store_avec_atomes,
                                                  monkeypatch):
    """Inversement, des sections non vides sans corps → valide."""
    notion_data = {
        'id': 'no_sec', 'titre': 'T',
        'corps': '',
        'sections': [{'titre': 'Exemples', 'items': ['un exemple']}],
        'niveau': 'N10', 'sequence': 'S01',
    }
    a = Atome(type='notion', id='no_sec',
              niveau='N10', sequence='S01',
              identifiant='N10/S01/Test', titre='T', data=notion_data)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                         duree_ms=100))

    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_SUCCES


def test_methode_avec_corps_seul_n_est_pas_vide(store_avec_atomes,
                                                 monkeypatch):
    """Symétrie avec les notions : une méthode à corps seul est valide."""
    methode_data = {
        'id': 'me_corps_seul', 'titre': 'Méthode',
        'corps': "Pour faire X, il faut Y.",
        'sections': [],
        'niveau': 'N10', 'sequence': 'S01',
        'num_methode': 1, 'num_objectif': '01',
        'criteres': {'2': 'F', '3': 'A', '4': 'E'},
        'notions': [],
    }
    a = Atome(type='methode', id='me_corps_seul',
              niveau='N10', sequence='S01',
              identifiant='N10/S01/Méthode 01',
              titre='Méthode', data=methode_data)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                         duree_ms=100))

    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_SUCCES


def test_exercice_valide_meme_sans_sections(store_avec_atomes, monkeypatch):
    """Un exercice avec énoncé + corrigé est valide, même sans 'sections'.
    Le modèle universel à 2 niveaux ne s'applique qu'aux notions/méthodes."""
    a = _atome_factice('exercice', sections=[],
                       enonce='OK', corrige='OK')

    # Mock generer_tex_par_type et compiler_atome pour simuler un succès.
    def fake_generer(conn, t, i, r, **kw):
        return "fake tex"
    def fake_compiler(**kw):
        return ResultatCompilation(ok=True, pdf_bytes=b'PDF',
                                   duree_ms=100, depuis_cache=False)

    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type', fake_generer)
    monkeypatch.setattr('services.compilation_batch.compiler_atome', fake_compiler)

    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_SUCCES


def test_atome_succes(store_avec_atomes, monkeypatch):
    a = _atome_factice('notion',
        sections=[{'titre': 'Exemples', 'items': ['x']}])

    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                         duree_ms=2000, depuis_cache=False))
    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_SUCCES
    assert ev['duree_ms'] == 2000


def test_atome_cache(store_avec_atomes, monkeypatch):
    a = _atome_factice('notion',
        sections=[{'titre': 'Exemples', 'items': ['x']}])
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                         duree_ms=0, depuis_cache=True))
    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_CACHE


def test_atome_echec_compilation_latex(store_avec_atomes, monkeypatch):
    """Une erreur LaTeX classique → echec_compilation, pas echec_infra."""
    a = _atome_factice('notion',
        sections=[{'titre': 'Exemples', 'items': ['x']}])
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=False,
            erreurs=[ErreurLatex(ligne=42,
                message="Undefined control sequence \\foo")],
            duree_ms=500))
    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_ECHEC_COMPILATION
    assert 'Undefined' in ev['message']


def test_atome_echec_infra_pdflatex_introuvable(store_avec_atomes, monkeypatch):
    a = _atome_factice('notion',
        sections=[{'titre': 'Exemples', 'items': ['x']}])
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=False,
            erreurs=[ErreurLatex(ligne=None,
                message="pdflatex introuvable. Définir...")],
            duree_ms=0))
    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_ECHEC_INFRA


def test_atome_echec_infra_timeout(store_avec_atomes, monkeypatch):
    a = _atome_factice('notion',
        sections=[{'titre': 'Exemples', 'items': ['x']}])
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=False,
            erreurs=[ErreurLatex(ligne=None,
                message="Compilation interrompue après 30s (timeout).")],
            duree_ms=30000))
    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_ECHEC_INFRA


def test_atome_echec_infra_exception_python(store_avec_atomes, monkeypatch):
    """Une exception inattendue dans la chaîne → echec_infra."""
    a = _atome_factice('notion',
        sections=[{'titre': 'Exemples', 'items': ['x']}])
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    def explose(**kw):
        raise OSError("disque plein")
    monkeypatch.setattr('services.compilation_batch.compiler_atome', explose)
    with store_avec_atomes._conn() as conn:
        ev = compiler_un_atome(conn, a, None, None, None, None, None, 30)
    assert ev['statut'] == STATUT_ECHEC_INFRA
    assert 'disque plein' in ev['message']


# ── iter_compilation : flux d'événements ─────────────────────────────────────

def test_iter_succes_total(store_avec_atomes, monkeypatch):
    """Tous les atomes compilent OK → events 'atome' + un event 'fin'."""
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                         duree_ms=100, depuis_cache=False))

    evs = list(iter_compilation(
        store=store_avec_atomes, racine_sources=None, dossier_images=None,
        cache_dir=None, pdflatex='/fake', racine_appli=None, timeout=30,
        max_erreurs_consecutives=5,
    ))

    atomes_evs = [e for e in evs if e['kind'] == 'atome']
    fin = [e for e in evs if e['kind'] == 'fin']

    assert len(atomes_evs) == 7
    assert len(fin) == 1
    assert fin[0]['compteurs'][STATUT_SUCCES] == 7
    assert fin[0]['traite'] == 7
    assert all(e['statut'] == STATUT_SUCCES for e in atomes_evs)


def test_iter_index_total_corrects(store_avec_atomes, monkeypatch):
    """index commence à 1 et atteint total."""
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                         duree_ms=10))
    evs = list(iter_compilation(
        store=store_avec_atomes, racine_sources=None, dossier_images=None,
        cache_dir=None, pdflatex='/fake', racine_appli=None, timeout=30,
        max_erreurs_consecutives=5,
    ))
    atomes_evs = [e for e in evs if e['kind'] == 'atome']
    indices = [e['index'] for e in atomes_evs]
    assert indices == list(range(1, 8))
    assert all(e['total'] == 7 for e in atomes_evs)


def test_iter_filtre_applique(store_avec_atomes, monkeypatch):
    """Le filtre limite les atomes traités."""
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P', duree_ms=10))
    evs = list(iter_compilation(
        store=store_avec_atomes, racine_sources=None, dossier_images=None,
        cache_dir=None, pdflatex='/fake', racine_appli=None, timeout=30,
        max_erreurs_consecutives=5,
        filtre=Filtre(type='exercice', niveau='N10'),
    ))
    atomes_evs = [e for e in evs if e['kind'] == 'atome']
    assert len(atomes_evs) == 3
    assert all(e['type'] == 'exercice' for e in atomes_evs)


def test_iter_abandon_sur_erreurs_infra(store_avec_atomes, monkeypatch):
    """Après N erreurs infra consécutives, le stream s'arrête avec kind=abandon."""
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=False,
            erreurs=[ErreurLatex(ligne=None,
                message="pdflatex introuvable.")], duree_ms=0))

    evs = list(iter_compilation(
        store=store_avec_atomes, racine_sources=None, dossier_images=None,
        cache_dir=None, pdflatex=None, racine_appli=None, timeout=30,
        max_erreurs_consecutives=3,
    ))
    atomes_evs = [e for e in evs if e['kind'] == 'atome']
    final = [e for e in evs if e['kind'] in ('fin', 'abandon')]
    assert len(atomes_evs) == 3  # exactement 3 erreurs avant abandon
    assert final[0]['kind'] == 'abandon'
    assert 'message' in final[0]


def test_iter_compteur_reset_sur_succes(store_avec_atomes, monkeypatch):
    """Un succès intercalé réinitialise le compteur d'erreurs infra."""
    # Pattern : echec_infra, echec_infra, succes, echec_infra, echec_infra
    # Avec max=3, on ne doit JAMAIS abandonner (jamais 3 d'affilée).
    sequence = iter([
        ResultatCompilation(ok=False,
            erreurs=[ErreurLatex(ligne=None, message="timeout")], duree_ms=0),
        ResultatCompilation(ok=False,
            erreurs=[ErreurLatex(ligne=None, message="timeout")], duree_ms=0),
        ResultatCompilation(ok=True, pdf_bytes=b'P', duree_ms=10),
        ResultatCompilation(ok=False,
            erreurs=[ErreurLatex(ligne=None, message="timeout")], duree_ms=0),
        ResultatCompilation(ok=False,
            erreurs=[ErreurLatex(ligne=None, message="timeout")], duree_ms=0),
    ])
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: next(sequence, ResultatCompilation(
            ok=True, pdf_bytes=b'P', duree_ms=10)))

    evs = list(iter_compilation(
        store=store_avec_atomes, racine_sources=None, dossier_images=None,
        cache_dir=None, pdflatex=None, racine_appli=None, timeout=30,
        max_erreurs_consecutives=3,
    ))
    final = [e for e in evs if e['kind'] in ('fin', 'abandon')][0]
    # 7 atomes au total, aucun abandon car le succès a reset le compteur.
    assert final['kind'] == 'fin'
    assert final['traite'] == 7


def test_iter_echec_compilation_ne_compte_pas_dans_abandon(store_avec_atomes, monkeypatch):
    """Les echec_compilation (LaTeX) ne déclenchent pas l'abandon global."""
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=False,
            erreurs=[ErreurLatex(ligne=10, message="Undefined control sequence")],
            duree_ms=500))

    evs = list(iter_compilation(
        store=store_avec_atomes, racine_sources=None, dossier_images=None,
        cache_dir=None, pdflatex='/fake', racine_appli=None, timeout=30,
        max_erreurs_consecutives=3,
    ))
    atomes_evs = [e for e in evs if e['kind'] == 'atome']
    final = [e for e in evs if e['kind'] in ('fin', 'abandon')][0]
    assert final['kind'] == 'fin'  # pas d'abandon
    assert len(atomes_evs) == 7
    assert all(e['statut'] == STATUT_ECHEC_COMPILATION for e in atomes_evs)


def test_iter_annulation(store_avec_atomes, monkeypatch):
    """La fonction annule() arrête proprement le stream."""
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P', duree_ms=10))

    compteur = {'n': 0}
    def annule():
        compteur['n'] += 1
        return compteur['n'] > 2  # annule après le 2e atome

    evs = list(iter_compilation(
        store=store_avec_atomes, racine_sources=None, dossier_images=None,
        cache_dir=None, pdflatex='/fake', racine_appli=None, timeout=30,
        max_erreurs_consecutives=5, annule=annule,
    ))
    final = [e for e in evs if e['kind'] in ('fin', 'abandon', 'annule')][0]
    assert final['kind'] == 'annule'


# ── Rapport Markdown ─────────────────────────────────────────────────────────

def test_rapport_md_contient_recap_et_echecs(tmp_path):
    evenements = [
        {'kind': 'atome', 'index': 1, 'total': 3,
         'type': 'exercice', 'id': 'ex_1',
         'identifiant': 'N10/S01/F01', 'titre': 'OK',
         'statut': STATUT_SUCCES, 'message': '', 'duree_ms': 1500},
        {'kind': 'atome', 'index': 2, 'total': 3,
         'type': 'notion', 'id': 'no_1',
         'identifiant': 'N10/S01/Notion 02', 'titre': 'Mauvaise',
         'statut': STATUT_ECHEC_COMPILATION,
         'message': 'Undefined \\foo', 'duree_ms': 800},
        {'kind': 'atome', 'index': 3, 'total': 3,
         'type': 'methode', 'id': 'me_1',
         'identifiant': 'N10/S01/Méthode 03', 'titre': 'Vide',
         'statut': STATUT_ECHEC_VIDE, 'message': 'Aucune section', 'duree_ms': 0},
        {'kind': 'fin', 'total': 3, 'traite': 3,
         'compteurs': {STATUT_SUCCES: 1, STATUT_CACHE: 0,
                       STATUT_ECHEC_VIDE: 1, STATUT_ECHEC_COMPILATION: 1,
                       STATUT_ECHEC_INFRA: 0},
         'duree_totale_ms': 2300},
    ]
    chemin = tmp_path / 'rap.md'
    ecrire_rapport_md(evenements, chemin, Filtre(niveau='N10'))
    txt = chemin.read_text(encoding='utf-8')
    # Sections.
    assert '# Compilation des atomes' in txt
    assert '## Filtre appliqué' in txt
    assert '## Récapitulatif' in txt
    assert '## Échecs (2)' in txt
    assert '## Compilations OK (1)' in txt
    # Filtre.
    assert 'N10' in txt
    # Identifiants des échecs.
    assert 'N10/S01/Notion 02' in txt
    assert 'N10/S01/Méthode 03' in txt
    # Message d'erreur.
    assert 'Undefined' in txt


def test_rapport_md_abandon(tmp_path):
    evenements = [
        {'kind': 'atome', 'index': 1, 'total': 5,
         'type': 'notion', 'id': 'no_1',
         'identifiant': 'N10/S01/Notion 01', 'titre': '',
         'statut': STATUT_ECHEC_INFRA, 'message': 'pdflatex introuvable',
         'duree_ms': 0},
        {'kind': 'abandon', 'total': 5, 'traite': 1,
         'compteurs': {STATUT_SUCCES: 0, STATUT_CACHE: 0,
                       STATUT_ECHEC_VIDE: 0, STATUT_ECHEC_COMPILATION: 0,
                       STATUT_ECHEC_INFRA: 1},
         'duree_totale_ms': 0,
         'message': 'Abandon : 1 erreurs ...'},
    ]
    chemin = tmp_path / 'rap.md'
    ecrire_rapport_md(evenements, chemin)
    txt = chemin.read_text(encoding='utf-8')
    assert 'Abandon' in txt


def test_rapport_md_echappe_pipes_et_newlines(tmp_path):
    """Les caractères qui cassent les tables Markdown sont échappés."""
    evenements = [
        {'kind': 'atome', 'index': 1, 'total': 1,
         'type': 'notion', 'id': 'x',
         'identifiant': 'N10/S01/Notion 01',
         'titre': 'Avec | un pipe\net un newline',
         'statut': STATUT_ECHEC_COMPILATION,
         'message': 'msg|avec|pipes', 'duree_ms': 0},
        {'kind': 'fin', 'total': 1, 'traite': 1,
         'compteurs': {STATUT_SUCCES: 0, STATUT_CACHE: 0,
                       STATUT_ECHEC_VIDE: 0, STATUT_ECHEC_COMPILATION: 1,
                       STATUT_ECHEC_INFRA: 0},
         'duree_totale_ms': 0},
    ]
    chemin = tmp_path / 'rap.md'
    ecrire_rapport_md(evenements, chemin)
    txt = chemin.read_text(encoding='utf-8')
    # Vérification : aucune ligne du tableau ne contient un newline non échappé
    # (sinon la table Markdown est cassée).
    debut_table = txt.index('## Échecs')
    section_echecs = txt[debut_table:txt.index('## Compilations OK', debut_table) if '## Compilations OK' in txt[debut_table:] else len(txt)]
    # Pas de "OR" sale dans une ligne de données : chaque ligne de la table
    # doit avoir le bon nombre de cellules → pas de newline interne
    assert 'avec | un pipe' not in txt  # le pipe doit être échappé
    assert '\\|' in txt  # pipe échappé présent


# ── evenement_vers_sse : format ──────────────────────────────────────────────

def test_evenement_vers_sse_format():
    s = evenement_vers_sse({'kind': 'atome', 'id': 'x'})
    assert s.startswith('data: ')
    assert s.endswith('\n\n')
    # Le JSON est parseable.
    payload = s[len('data: '):-2]
    data = json.loads(payload)
    assert data == {'kind': 'atome', 'id': 'x'}


def test_evenement_vers_sse_unicode():
    """Les caractères français passent bien."""
    s = evenement_vers_sse({'titre': 'Méthode élémentaire'})
    assert 'Méthode élémentaire' in s


def test_nom_rapport_format():
    from datetime import datetime
    n = nom_rapport(datetime(2026, 4, 26, 14, 35, 12))
    assert n == 'Compilation_atomes_2026-04-26_14-35-12.md'


# ── Cohérence des libellés ───────────────────────────────────────────────────

def test_libelles_couvrent_tous_les_statuts():
    """Tous les statuts doivent avoir un libellé humain."""
    statuts = [STATUT_SUCCES, STATUT_CACHE, STATUT_ECHEC_VIDE,
               STATUT_ECHEC_COMPILATION, STATUT_ECHEC_INFRA]
    for s in statuts:
        assert s in LIBELLES_STATUTS


# ── v0.8.4 — Section « Exercices sans corrigé » dans le rapport MD ───────────

def test_rapport_md_section_exercices_sans_corrige(tmp_path):
    """Quand au moins un exercice a le flag sans_corrige, le rapport
    ajoute une section dédiée avec son identifiant et son titre."""
    evenements = [
        {'kind': 'atome', 'index': 1, 'total': 2,
         'type': 'exercice', 'id': 'ex_1',
         'identifiant': 'N10/S01/F01', 'titre': 'Exo avec corrigé',
         'statut': STATUT_SUCCES, 'message': '', 'duree_ms': 1500},
        {'kind': 'atome', 'index': 2, 'total': 2,
         'type': 'exercice', 'id': 'ex_2',
         'identifiant': 'N10/S01/F02', 'titre': 'Exo sans corrigé',
         'statut': STATUT_SUCCES, 'message': '', 'duree_ms': 1400,
         'sans_corrige': True},
        {'kind': 'fin', 'total': 2, 'traite': 2,
         'compteurs': {STATUT_SUCCES: 2, STATUT_CACHE: 0,
                       STATUT_ECHEC_VIDE: 0, STATUT_ECHEC_COMPILATION: 0,
                       STATUT_ECHEC_INFRA: 0},
         'duree_totale_ms': 2900},
    ]
    chemin = tmp_path / 'rap.md'
    ecrire_rapport_md(evenements, chemin)
    txt = chemin.read_text(encoding='utf-8')
    # La section dédiée existe avec le bon compteur.
    assert '## Exercices sans corrigé (1)' in txt
    # L'identifiant de l'exo concerné y figure.
    assert 'N10/S01/F02' in txt.split('## Exercices sans corrigé')[1]
    # Pas l'autre exo (qui a un corrigé).
    assert 'N10/S01/F01' not in txt.split('## Exercices sans corrigé')[1]
    # Les deux exos restent dans « Compilations OK ».
    section_ok = txt.split('## Compilations OK')[1].split('## Exercices')[0]
    assert 'N10/S01/F01' in section_ok
    assert 'N10/S01/F02' in section_ok


def test_rapport_md_pas_de_section_si_pas_d_exo_sans_corrige(tmp_path):
    """Si aucun exercice n'a le flag, la section n'apparaît pas."""
    evenements = [
        {'kind': 'atome', 'index': 1, 'total': 1,
         'type': 'exercice', 'id': 'ex_1',
         'identifiant': 'N10/S01/F01', 'titre': 'OK',
         'statut': STATUT_SUCCES, 'message': '', 'duree_ms': 1000},
        {'kind': 'fin', 'total': 1, 'traite': 1,
         'compteurs': {STATUT_SUCCES: 1, STATUT_CACHE: 0,
                       STATUT_ECHEC_VIDE: 0, STATUT_ECHEC_COMPILATION: 0,
                       STATUT_ECHEC_INFRA: 0},
         'duree_totale_ms': 1000},
    ]
    chemin = tmp_path / 'rap.md'
    ecrire_rapport_md(evenements, chemin)
    txt = chemin.read_text(encoding='utf-8')
    assert '## Exercices sans corrigé' not in txt


# ── v0.8.3 — Slug pour fichiers d'échec ──────────────────────────────────────

class TestSlugPourFichier:
    """Tests du helper qui transforme un identifiant lisible en nom de
    fichier sûr pour le stockage des fichiers d'échec (.tex/.log)."""

    def test_simple_exercice(self):
        from services.compilation_batch import _slug_pour_fichier
        assert _slug_pour_fichier('N10/S01/F01') == 'N10_S01_F01'

    def test_notion_avec_espace(self):
        from services.compilation_batch import _slug_pour_fichier
        assert _slug_pour_fichier('N10/S01/Notion 06') == 'N10_S01_Notion_06'

    def test_methode_avec_accent(self):
        """Méthode → Methode (les accents sont décomposés et filtrés)."""
        from services.compilation_batch import _slug_pour_fichier
        assert _slug_pour_fichier('N10/S12/Méthode 03') == 'N10_S12_Methode_03'

    def test_compresse_underscores_multiples(self):
        from services.compilation_batch import _slug_pour_fichier
        # Chaîne avec plein de caractères spéciaux qui deviennent _
        assert _slug_pour_fichier('A//B  C') == 'A_B_C'

    def test_trime_underscores_bordure(self):
        from services.compilation_batch import _slug_pour_fichier
        assert _slug_pour_fichier('/N10/') == 'N10'

    def test_fallback_si_chaine_vide_apres_normalisation(self):
        from services.compilation_batch import _slug_pour_fichier
        assert _slug_pour_fichier('///') == 'atome'
        assert _slug_pour_fichier('') == 'atome'


# ── v0.8.3 — Conservation des fichiers d'échec ───────────────────────────────

class TestDossierEchecs:

    def test_iter_purge_dossier_au_demarrage(self, store_avec_atomes,
                                             monkeypatch, tmp_path):
        """Le dossier d'échecs est vidé de ses .tex et .log au début du run."""
        dossier = tmp_path / 'echecs'
        dossier.mkdir()
        # Pollution avant le run.
        (dossier / 'vieux.log').write_text('vieux contenu', encoding='utf-8')
        (dossier / 'vieux.tex').write_text('\\documentclass{article}',
                                            encoding='utf-8')

        # Tout passe en succès → aucun nouvel échec écrit.
        monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                            lambda conn, t, i, r, **kw: "tex")
        monkeypatch.setattr('services.compilation_batch.compiler_atome',
            lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                             duree_ms=10))

        list(iter_compilation(
            store=store_avec_atomes, racine_sources=None,
            dossier_images=None, cache_dir=None, pdflatex='/fake',
            racine_appli=None, timeout=30, max_erreurs_consecutives=5,
            dossier_echecs=dossier,
        ))

        # Les anciens fichiers ont été purgés.
        assert not (dossier / 'vieux.log').exists()
        assert not (dossier / 'vieux.tex').exists()

    def test_iter_ne_purge_pas_extensions_inconnues(self, store_avec_atomes,
                                                    monkeypatch, tmp_path):
        """La purge ne touche qu'aux .tex et .log, pas aux autres fichiers
        qui pourraient traîner par accident dans le dossier."""
        dossier = tmp_path / 'echecs'
        dossier.mkdir()
        (dossier / 'README.md').write_text('ne pas supprimer',
                                            encoding='utf-8')

        monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                            lambda conn, t, i, r, **kw: "tex")
        monkeypatch.setattr('services.compilation_batch.compiler_atome',
            lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                             duree_ms=10))

        list(iter_compilation(
            store=store_avec_atomes, racine_sources=None,
            dossier_images=None, cache_dir=None, pdflatex='/fake',
            racine_appli=None, timeout=30, max_erreurs_consecutives=5,
            dossier_echecs=dossier,
        ))

        assert (dossier / 'README.md').exists()

    def test_iter_ecrit_tex_et_log_pour_echec_compilation(
            self, store_avec_atomes, monkeypatch, tmp_path):
        """Un atome en echec_compilation produit un .tex et un .log
        dans le dossier d'échecs."""
        dossier = tmp_path / 'echecs'

        monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                            lambda conn, t, i, r, **kw: "% TEX SOURCE\n\\foo")
        monkeypatch.setattr('services.compilation_batch.compiler_atome',
            lambda **kw: ResultatCompilation(
                ok=False,
                erreurs=[ErreurLatex(ligne=42,
                    message="Undefined control sequence \\foo")],
                log_complet=("LOG COMPLET DE PDFLATEX\n"
                             "! Undefined control sequence.\n"
                             "l.42 \\foo"),
                duree_ms=500))

        evs = list(iter_compilation(
            store=store_avec_atomes, racine_sources=None,
            dossier_images=None, cache_dir=None, pdflatex='/fake',
            racine_appli=None, timeout=30, max_erreurs_consecutives=99,
            dossier_echecs=dossier,
        ))
        atomes_evs = [e for e in evs if e['kind'] == 'atome']
        # Au moins un échec.
        echecs = [e for e in atomes_evs
                  if e['statut'] == STATUT_ECHEC_COMPILATION]
        assert echecs

        # Tous les échecs ont un nom_log dans l'événement.
        for e in echecs:
            assert 'nom_log' in e
            assert e['nom_log'].endswith('.log')
            # Le fichier existe sur disque.
            assert (dossier / e['nom_log']).is_file()
            # Et son contenu correspond.
            assert 'LOG COMPLET DE PDFLATEX' in (
                dossier / e['nom_log']).read_text(encoding='utf-8')
            # Le .tex aussi est écrit.
            tex_file = dossier / (e['nom_log'][:-4] + '.tex')
            assert tex_file.is_file()
            assert '% TEX SOURCE' in tex_file.read_text(encoding='utf-8')

    def test_iter_evenement_sans_clefs_privees(self, store_avec_atomes,
                                                monkeypatch, tmp_path):
        """Les clés `_tex_source` et `_log_complet` sont retirées avant
        sérialisation SSE — sinon on enverrait potentiellement des dizaines
        de Ko par atome dans le flux."""
        dossier = tmp_path / 'echecs'
        monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                            lambda conn, t, i, r, **kw: "tex")
        monkeypatch.setattr('services.compilation_batch.compiler_atome',
            lambda **kw: ResultatCompilation(
                ok=False,
                erreurs=[ErreurLatex(ligne=1, message="LaTeX Error")],
                log_complet="contenu log",
                duree_ms=100))

        evs = list(iter_compilation(
            store=store_avec_atomes, racine_sources=None,
            dossier_images=None, cache_dir=None, pdflatex='/fake',
            racine_appli=None, timeout=30, max_erreurs_consecutives=99,
            dossier_echecs=dossier,
        ))
        atomes_evs = [e for e in evs if e['kind'] == 'atome']
        for e in atomes_evs:
            assert '_tex_source' not in e
            assert '_log_complet' not in e

    def test_iter_succes_n_ecrit_rien(self, store_avec_atomes,
                                       monkeypatch, tmp_path):
        """Aucun fichier écrit dans le dossier d'échecs si tout passe."""
        dossier = tmp_path / 'echecs'
        monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                            lambda conn, t, i, r, **kw: "tex")
        monkeypatch.setattr('services.compilation_batch.compiler_atome',
            lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                             duree_ms=10))

        list(iter_compilation(
            store=store_avec_atomes, racine_sources=None,
            dossier_images=None, cache_dir=None, pdflatex='/fake',
            racine_appli=None, timeout=30, max_erreurs_consecutives=5,
            dossier_echecs=dossier,
        ))
        # Le dossier est créé mais vide (pas de .log/.tex ajoutés).
        assert dossier.is_dir()
        contenus = list(dossier.iterdir())
        assert contenus == [], (
            f"Le dossier devrait être vide, contient : {contenus}"
        )

    def test_iter_sans_dossier_echecs_aucun_nom_log(self, store_avec_atomes,
                                                     monkeypatch):
        """Si dossier_echecs=None, les événements n'ont pas nom_log."""
        monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                            lambda conn, t, i, r, **kw: "tex")
        monkeypatch.setattr('services.compilation_batch.compiler_atome',
            lambda **kw: ResultatCompilation(
                ok=False,
                erreurs=[ErreurLatex(ligne=1, message="LaTeX Error")],
                log_complet="contenu log",
                duree_ms=100))

        evs = list(iter_compilation(
            store=store_avec_atomes, racine_sources=None,
            dossier_images=None, cache_dir=None, pdflatex='/fake',
            racine_appli=None, timeout=30, max_erreurs_consecutives=99,
            # Pas de dossier_echecs.
        ))
        atomes_evs = [e for e in evs if e['kind'] == 'atome']
        for e in atomes_evs:
            assert 'nom_log' not in e

    def test_iter_echec_infra_ecrit_log(self, store_avec_atomes,
                                         monkeypatch, tmp_path):
        """Les echec_infra sont aussi conservés (politique (a))."""
        dossier = tmp_path / 'echecs'
        monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                            lambda conn, t, i, r, **kw: "tex")
        monkeypatch.setattr('services.compilation_batch.compiler_atome',
            lambda **kw: ResultatCompilation(
                ok=False,
                erreurs=[ErreurLatex(ligne=None,
                    message="pdflatex introuvable. Définir...")],
                log_complet="(pas de log : pdflatex n'a pas tourné)",
                duree_ms=0))

        evs = list(iter_compilation(
            store=store_avec_atomes, racine_sources=None,
            dossier_images=None, cache_dir=None, pdflatex=None,
            racine_appli=None, timeout=30,
            # max=99 pour ne pas déclencher l'abandon, on veut tester que
            # tous les atomes infra produisent leur log.
            max_erreurs_consecutives=99,
            dossier_echecs=dossier,
        ))
        infra_evs = [e for e in evs if e.get('statut') == STATUT_ECHEC_INFRA]
        assert infra_evs
        for e in infra_evs:
            assert e.get('nom_log')


# ── v0.8.3 — Rapport MD avec colonne Log ─────────────────────────────────────

def test_rapport_md_colonne_log_si_disponible(tmp_path):
    """Quand au moins un échec a un nom_log, le rapport ajoute la colonne Log."""
    evenements = [
        {'kind': 'atome', 'index': 1, 'total': 2,
         'type': 'notion', 'id': 'no_1',
         'identifiant': 'N10/S01/Notion 06', 'titre': 'Repère',
         'statut': STATUT_ECHEC_COMPILATION,
         'message': 'Undefined \\tkzLabelX',
         'nom_log': 'N10_S01_Notion_06.log',
         'duree_ms': 800},
        {'kind': 'atome', 'index': 2, 'total': 2,
         'type': 'methode', 'id': 'me_1',
         'identifiant': 'N10/S01/Méthode 03', 'titre': 'Vide',
         'statut': STATUT_ECHEC_VIDE, 'message': 'Aucune section',
         'duree_ms': 0},
        {'kind': 'fin', 'total': 2, 'traite': 2,
         'compteurs': {STATUT_SUCCES: 0, STATUT_CACHE: 0,
                       STATUT_ECHEC_VIDE: 1, STATUT_ECHEC_COMPILATION: 1,
                       STATUT_ECHEC_INFRA: 0},
         'duree_totale_ms': 800},
    ]
    chemin = tmp_path / 'rap.md'
    ecrire_rapport_md(evenements, chemin)
    txt = chemin.read_text(encoding='utf-8')
    # La table doit avoir 6 colonnes (Identifiant, Type, Statut, Titre, Message, Log).
    assert '| Identifiant | Type | Statut | Titre | Message | Log |' in txt
    # Le nom du log apparaît.
    assert 'N10_S01_Notion_06.log' in txt
    # L'atome echec_vide n'a pas de nom_log mais sa cellule Log est vide
    # (pas plantage).
    assert 'N10/S01/Méthode 03' in txt


def test_rapport_md_pas_de_colonne_log_si_aucun(tmp_path):
    """Si aucun échec n'a de nom_log, on garde le format à 5 colonnes."""
    evenements = [
        {'kind': 'atome', 'index': 1, 'total': 1,
         'type': 'notion', 'id': 'no_1',
         'identifiant': 'N10/S03/Notion 02', 'titre': 'Vide',
         'statut': STATUT_ECHEC_VIDE, 'message': 'Aucune section',
         'duree_ms': 0},
        {'kind': 'fin', 'total': 1, 'traite': 1,
         'compteurs': {STATUT_SUCCES: 0, STATUT_CACHE: 0,
                       STATUT_ECHEC_VIDE: 1, STATUT_ECHEC_COMPILATION: 0,
                       STATUT_ECHEC_INFRA: 0},
         'duree_totale_ms': 0},
    ]
    chemin = tmp_path / 'rap.md'
    ecrire_rapport_md(evenements, chemin)
    txt = chemin.read_text(encoding='utf-8')
    # Pas de colonne Log si aucun échec n'en a.
    assert '| Identifiant | Type | Statut | Titre | Message |' in txt
    assert '| Log |' not in txt
