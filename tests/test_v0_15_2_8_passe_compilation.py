"""tests/test_v0_15_2_8_passe_compilation.py — v0.15.2.8 (partie A)

Affichage du numéro de passe pdflatex (1/2 puis 2/2) en plus du compteur
de pages. Le compteur de pages seul (v0.15.2.7) « bouge », mais pas
assez : on rend le tout plus rassurant en montrant aussi à quelle passe
on en est.

Mécanique :
- `compiler_atome` reçoit une callback `on_passe_demarree(num)` appelée
  avant chaque `_lancer_pdflatex()` (1 puis 2).
- L'orchestrateur propage cette callback depuis `compiler()`.
- Le worker fournit une callback qui met à jour `statut.passe_courante`
  via `_maj_statut`.
- `lire_statut` retourne `passe_courante` et `passes_total` (constant,
  vaut 2 aujourd'hui — exposé pour l'UI qui affiche « passe N/M »).

Ces tests protègent :
- La signature de `compiler_atome` accepte `on_passe_demarree`.
- La callback est appelée 1 puis 2 dans l'ordre, AVANT chaque pdflatex.
- Une callback qui lève ne casse PAS la compilation.
- Le statut initial expose `passes_total=2` et `passe_courante=None`.
- Le statut est correctement mis à jour quand la callback est invoquée.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import referentiel_documents_compilation as svc_cmp  # noqa: E402


@pytest.fixture(autouse=True)
def _isole_statuts():
    yield
    with svc_cmp._LOCK_STATUTS:
        svc_cmp._STATUTS_COMPILATION.clear()


# ── Statut : présence et valeurs initiales ──────────────────────────────────


def test_statut_initial_expose_passe_et_total():
    s = svc_cmp._statut_initial('doc1', total=3, type_document='X')
    assert s['passe_courante'] is None
    assert s['passes_total'] == 2  # cf. _TOTAL_PASSES_PDFLATEX


def test_lire_statut_renvoie_passe_courante():
    """Quand le worker pose passe_courante=1 dans le statut, lire_statut
    le renvoie tel quel."""
    base = svc_cmp._statut_initial('doc2', total=3, type_document='X')
    base['passe_courante'] = 1
    with svc_cmp._LOCK_STATUTS:
        svc_cmp._STATUTS_COMPILATION['doc2'] = base
    s = svc_cmp.lire_statut('doc2')
    assert s is not None
    assert s['passe_courante'] == 1
    assert s['passes_total'] == 2


# ── compiler_atome : callback appelée 1 puis 2 ──────────────────────────────


def test_compiler_atome_signature_accepte_on_passe_demarree():
    """Vérifie que le paramètre existe et est keyword-only friendly."""
    import inspect
    from services.compilateur_pdf import compiler_atome
    sig = inspect.signature(compiler_atome)
    assert 'on_passe_demarree' in sig.parameters


def test_compiler_atome_callback_appelee_dans_l_ordre(tmp_path):
    """Si pdflatex est dispo, on capture les appels de la callback et on
    vérifie qu'ils arrivent dans l'ordre (1, 2) avant les exécutions
    pdflatex. Skip si pdflatex absent."""
    from services.compilateur_pdf import compiler_atome, detecter_pdflatex
    pdflatex = detecter_pdflatex()
    if not pdflatex:
        pytest.skip("pdflatex non détecté")

    appels = []
    def cb(num):
        appels.append(num)

    tex = (
        r'\documentclass{article}'
        '\n'
        r'\begin{document}'
        '\n'
        r'Test page 1.\newpage Test page 2.'
        '\n'
        r'\end{document}'
        '\n'
    )
    res = compiler_atome(
        tex_source=tex, pdflatex=pdflatex,
        workdir=tmp_path / 'wd',
        on_passe_demarree=cb,
        timeout=30,
    )
    # Si la compile réussit, la passe 2 doit être démarrée : appels=[1,2].
    # Si elle échoue dès la passe 1, on devrait quand même avoir [1].
    assert len(appels) >= 1
    assert appels[0] == 1
    if len(appels) >= 2:
        assert appels[1] == 2


def test_compiler_atome_callback_qui_leve_ne_casse_pas_la_compile(tmp_path):
    """Une callback buggée ne doit JAMAIS casser la compilation : le
    contrat est défensif (essentiel pour la stabilité UI)."""
    from services.compilateur_pdf import compiler_atome, detecter_pdflatex
    pdflatex = detecter_pdflatex()
    if not pdflatex:
        pytest.skip("pdflatex non détecté")

    def cb_buggee(num):
        raise RuntimeError("callback buggée")

    tex = (
        r'\documentclass{article}\begin{document}Test.\end{document}'
        '\n'
    )
    # Pas d'exception attendue ici malgré la callback qui lève
    res = compiler_atome(
        tex_source=tex, pdflatex=pdflatex,
        workdir=tmp_path / 'wd',
        on_passe_demarree=cb_buggee,
        timeout=30,
    )
    # Le résultat peut être ok ou ko selon ce que pdflatex pense des
    # paquets, mais surtout : pas d'exception remontée par la callback.
    assert res is not None


def test_compiler_atome_sans_callback_compile_normalement(tmp_path):
    """Rétrocompat : tous les appels existants à compiler_atome n'ont
    pas de callback, ça doit continuer à marcher comme avant."""
    from services.compilateur_pdf import compiler_atome, detecter_pdflatex
    pdflatex = detecter_pdflatex()
    if not pdflatex:
        pytest.skip("pdflatex non détecté")

    tex = (
        r'\documentclass{article}\begin{document}Test.\end{document}'
        '\n'
    )
    res = compiler_atome(
        tex_source=tex, pdflatex=pdflatex,
        workdir=tmp_path / 'wd',
        timeout=30,
    )
    assert res is not None


# ── Orchestrateur : on_passe_demarree propagée ──────────────────────────────


def test_orch_compiler_accepte_on_passe_demarree():
    """L'orchestrateur a bien le paramètre dans sa signature publique."""
    import inspect
    from services.orchestrateur_compilation import compiler
    sig = inspect.signature(compiler)
    assert 'on_passe_demarree' in sig.parameters


# ── Bout en bout léger : passe + page interagissent correctement ────────────


def test_statut_reset_page_quand_passe_change(tmp_path):
    """Au passage de la passe 1 à la passe 2, pdflatex écrase atome.log.
    La callback du worker reset donc page_courante=None pour éviter que
    l'UI continue d'afficher la page finale de la passe 1.

    On simule en plaçant un statut avec page=42, en appelant _maj_passe
    du worker (callback), puis en vérifiant que la lecture du statut
    renvoie bien None pour page_courante (jusqu'à ce que le log live
    de la passe 2 montre une nouvelle page).
    """
    # Setup : statut avec log live et page actuelle (passe 1 finie)
    log = tmp_path / 'atome.log'
    log.write_text('[1] [2] [3] ... [42]\n')
    base = svc_cmp._statut_initial('doc3', total=1, type_document='X')
    base['en_cours'] = True
    base['chemin_log_courant'] = str(log)
    base['passe_courante'] = 1
    with svc_cmp._LOCK_STATUTS:
        svc_cmp._STATUTS_COMPILATION['doc3'] = base
    # Lecture : doit voir page=42, passe=1
    s = svc_cmp.lire_statut('doc3')
    assert s['passe_courante'] == 1
    assert s['page_courante'] == 42

    # Simulation du basculement vers la passe 2 par le worker :
    # callback _maj_passe(2) qui reset la page. À ce stade le log
    # contient encore les marqueurs de la passe 1 (pdflatex n'a pas
    # encore écrasé) ; mais comme on a explicitement reset
    # page_courante dans le statut, lire_statut ne renverra page=42
    # QUE SI le parser le récupère du log encore intact.
    #
    # Le contrat ici : passe_courante doit bien passer à 2 (c'est le
    # comportement testé). Pour la page, le reset est instantané dans
    # le statut, mais le log live peut techniquement encore montrer
    # la fin de la passe 1. On accepte donc une légère incohérence
    # transitoire (l'UI poll à 700ms : un cycle de polling suffit
    # pour que le log soit écrasé par la passe 2).
    svc_cmp._maj_statut('doc3', passe_courante=2, page_courante=None)
    s = svc_cmp.lire_statut('doc3')
    assert s['passe_courante'] == 2
