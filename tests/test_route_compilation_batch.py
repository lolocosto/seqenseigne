"""
tests/test_route_compilation_batch.py — Tests d'intégration des routes v0.8.

On teste :
  - GET /api/admin/compilation-atomes/preview : compteurs + config retournée
  - GET /api/admin/compilation-atomes/run : SSE bien formé, événements parsables
  - GET /api/admin/compilation-atomes/rapport/<nom> : téléchargement
  - Override des paramètres timeout/max_erreurs persistés en config

Le compilateur LaTeX est mocké (compiler_atome) pour ne pas dépendre de
pdflatex installé sur le système de test.
"""

from __future__ import annotations
import json
from pathlib import Path

import pytest

from services.compilateur_pdf import ResultatCompilation, ErreurLatex
from services.compilation_batch import (
    STATUT_SUCCES, STATUT_CACHE, STATUT_ECHEC_VIDE,
    STATUT_ECHEC_COMPILATION, STATUT_ECHEC_INFRA,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _peupler_atomes(store):
    """Quelques atomes pour les tests, sur N10 et N11."""
    store.ecrire_notions([
        {"id": "no_1", "titre": "N1", "corps": "", "ordreExRem": True,
         "niveau": "N10", "sequence": "S01", "num_connaissance": "01",
         "fichier": "f1.tex",
         "sections": [{"titre": "Ex", "items": ["x"]}]},
        {"id": "no_2", "titre": "N2", "corps": "", "ordreExRem": True,
         "niveau": "N11", "sequence": "S02", "num_connaissance": "02",
         "fichier": "f2.tex",
         "sections": [{"titre": "Ex", "items": ["y"]}]},
    ])
    store.ecrire_methodes([])
    store.ecrire_exercices([
        {"id": "ex_1", "serie": "fondamental", "nom": "E1",
         "objectifs": [], "variables": "", "enonce": "E", "corrige": "C",
         "niveau": "N10", "sequence": "S01", "num": 1, "serie_code": "F",
         "fichier": "ex1.tex"},
    ])


def _parser_sse(corps_octets):
    """Décompose un flux SSE en liste de dicts JSON."""
    texte = corps_octets.decode('utf-8') if isinstance(corps_octets, bytes) else corps_octets
    evenements = []
    for bloc in texte.split('\n\n'):
        if not bloc.strip():
            continue
        for ligne in bloc.split('\n'):
            if ligne.startswith('data: '):
                evenements.append(json.loads(ligne[6:]))
    return evenements


# ── Preview ──────────────────────────────────────────────────────────────────

def test_preview_sans_filtre(client, store):
    _peupler_atomes(store)
    r = client.get('/api/admin/compilation-atomes/preview')
    assert r.status_code == 200
    d = r.get_json()
    assert d['total'] == 3
    # v0.18.0 — par_type couvre désormais les 5 types (fiche/carte = 0 ici).
    assert d['par_type'] == {
        'notion': 2, 'methode': 0, 'exercice': 1, 'fiche': 0, 'carte': 0,
    }
    # La config courante est retournée.
    assert 'config' in d
    # v0.10 — Dichotomie de timeouts : court (atomes/batch) vs long
    # (documents agrégés type récap cours).
    assert 'timeout_compilation_court_s' in d['config']
    assert 'timeout_compilation_long_s' in d['config']
    assert 'compilation_batch_max_erreurs_consecutives' in d['config']


def test_preview_filtre_par_niveau(client, store):
    _peupler_atomes(store)
    r = client.get('/api/admin/compilation-atomes/preview?niveau=N10')
    d = r.get_json()
    assert d['total'] == 2  # 1 notion + 1 exo
    assert d['par_type']['notion'] == 1
    assert d['par_type']['exercice'] == 1


def test_preview_filtre_par_type_et_niveau(client, store):
    _peupler_atomes(store)
    r = client.get('/api/admin/compilation-atomes/preview?type=notion&niveau=N10')
    d = r.get_json()
    assert d['total'] == 1


def test_preview_aucun_resultat(client, store):
    _peupler_atomes(store)
    r = client.get('/api/admin/compilation-atomes/preview?niveau=N12')
    d = r.get_json()
    assert d['total'] == 0


def test_preview_filtre_invalide_400(client, store):
    _peupler_atomes(store)
    r = client.get('/api/admin/compilation-atomes/preview?type=foobar')
    assert r.status_code == 400


def test_preview_niveau_invalide_400(client, store):
    _peupler_atomes(store)
    r = client.get('/api/admin/compilation-atomes/preview?niveau=N99')
    assert r.status_code == 400


def test_preview_sequence_invalide_400(client, store):
    _peupler_atomes(store)
    r = client.get('/api/admin/compilation-atomes/preview?sequence=BLA')
    assert r.status_code == 400


# ── Run : SSE ────────────────────────────────────────────────────────────────

def test_run_sse_format(client, store, monkeypatch):
    """Le run produit un flux SSE avec un événement par atome + final + rapport."""
    _peupler_atomes(store)

    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P',
                                         duree_ms=50, depuis_cache=False))

    r = client.get('/api/admin/compilation-atomes/run')
    assert r.status_code == 200
    assert r.mimetype == 'text/event-stream'

    evs = _parser_sse(r.data)
    kinds = [e['kind'] for e in evs]
    assert kinds.count('atome') == 3
    assert 'fin' in kinds
    assert 'rapport' in kinds


def test_run_genere_rapport(client, store, monkeypatch, data_dir):
    """Le rapport Markdown est créé sous data/rapports/."""
    _peupler_atomes(store)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P', duree_ms=10))

    r = client.get('/api/admin/compilation-atomes/run')
    evs = _parser_sse(r.data)
    rapport_ev = next(e for e in evs if e['kind'] == 'rapport')

    chemin = data_dir / 'rapports' / rapport_ev['nom']
    assert chemin.is_file()
    txt = chemin.read_text(encoding='utf-8')
    assert '# Compilation des atomes' in txt


def test_run_filtre_applique(client, store, monkeypatch):
    """Le filtre limite les atomes traités dans le run."""
    _peupler_atomes(store)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P', duree_ms=10))

    r = client.get('/api/admin/compilation-atomes/run?niveau=N10')
    evs = _parser_sse(r.data)
    atomes = [e for e in evs if e['kind'] == 'atome']
    assert len(atomes) == 2  # N10 seulement
    assert all('N10' in e['identifiant'] for e in atomes)


def test_run_persistance_config(client, store, monkeypatch, data_dir):
    """Les paramètres timeout et max_erreurs en query string sont persistés.

    v0.10 — On vérifie ici la rétrocompatibilité : le paramètre `timeout`
    (ancien nom) doit toujours être accepté et persisté dans la nouvelle
    clé `timeout_compilation_court_s`.
    """
    _peupler_atomes(store)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P', duree_ms=10))

    # Run avec params custom (utilise l'ancien nom `timeout` pour valider
    # la rétrocompatibilité).
    r = client.get(
        '/api/admin/compilation-atomes/run?timeout=42&max_erreurs=7')
    assert r.status_code == 200
    list(_parser_sse(r.data))  # consommer le flux

    # Vérifier que la config est bien à jour.
    config = json.loads((data_dir / 'configuration.json').read_text())
    assert config['timeout_compilation_court_s'] == 42
    assert config['compilation_batch_max_erreurs_consecutives'] == 7

    # Et un nouveau preview retourne ces valeurs.
    r2 = client.get('/api/admin/compilation-atomes/preview')
    d = r2.get_json()
    assert d['config']['timeout_compilation_court_s'] == 42
    assert d['config']['compilation_batch_max_erreurs_consecutives'] == 7


def test_run_persistance_timeout_court_et_long(client, store, monkeypatch, data_dir):
    """v0.10 — Les deux timeouts sont persistés indépendamment."""
    _peupler_atomes(store)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P', duree_ms=10))

    r = client.get(
        '/api/admin/compilation-atomes/run?timeout_court=45&timeout_long=600')
    assert r.status_code == 200
    list(_parser_sse(r.data))

    config = json.loads((data_dir / 'configuration.json').read_text())
    assert config['timeout_compilation_court_s'] == 45
    assert config['timeout_compilation_long_s'] == 600

    r2 = client.get('/api/admin/compilation-atomes/preview')
    d = r2.get_json()
    assert d['config']['timeout_compilation_court_s'] == 45
    assert d['config']['timeout_compilation_long_s'] == 600


def test_run_timeout_court_prioritaire_sur_alias(client, store, monkeypatch, data_dir):
    """v0.10 — Si les deux noms sont fournis, `timeout_court` (nouveau)
    prime sur `timeout` (alias rétrocompatible)."""
    _peupler_atomes(store)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P', duree_ms=10))

    r = client.get(
        '/api/admin/compilation-atomes/run?timeout=10&timeout_court=99')
    assert r.status_code == 200
    list(_parser_sse(r.data))

    config = json.loads((data_dir / 'configuration.json').read_text())
    assert config['timeout_compilation_court_s'] == 99


def test_run_timeout_invalide_400(client, store, monkeypatch):
    _peupler_atomes(store)
    r = client.get('/api/admin/compilation-atomes/run?timeout=abc')
    assert r.status_code == 400


def test_run_distingue_succes_cache(client, store, monkeypatch):
    """L'événement utilise STATUT_SUCCES ou STATUT_CACHE selon depuis_cache."""
    _peupler_atomes(store)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")

    appels = {'n': 0}
    def alterne(**kw):
        appels['n'] += 1
        # 1er depuis cache, 2e succès, 3e depuis cache.
        depuis_cache = (appels['n'] % 2 == 1)
        return ResultatCompilation(ok=True, pdf_bytes=b'P',
                                   duree_ms=0 if depuis_cache else 100,
                                   depuis_cache=depuis_cache)
    monkeypatch.setattr('services.compilation_batch.compiler_atome', alterne)

    r = client.get('/api/admin/compilation-atomes/run')
    evs = _parser_sse(r.data)
    atomes = [e for e in evs if e['kind'] == 'atome']
    statuts = [e['statut'] for e in atomes]
    assert STATUT_CACHE in statuts
    assert STATUT_SUCCES in statuts


def test_run_atome_vide_remonte(client, store, monkeypatch):
    """Un atome sans sections est marqué echec_vide sans appeler pdflatex."""
    # Notion sans aucune section.
    store.ecrire_notions([
        {"id": "no_vide", "titre": "Vide", "corps": "", "ordreExRem": True,
         "niveau": "N10", "sequence": "S01", "num_connaissance": "01",
         "fichier": "v.tex", "sections": []},
    ])
    store.ecrire_methodes([])
    store.ecrire_exercices([])

    # Mock qui plante si appelé : l'atome vide ne doit jamais y arriver.
    def doit_pas_etre_appele(**kw):
        raise AssertionError("compiler_atome ne devrait pas être appelé "
                             "pour un atome vide")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
                        doit_pas_etre_appele)

    r = client.get('/api/admin/compilation-atomes/run')
    evs = _parser_sse(r.data)
    atomes = [e for e in evs if e['kind'] == 'atome']
    assert len(atomes) == 1
    assert atomes[0]['statut'] == STATUT_ECHEC_VIDE


# ── Téléchargement du rapport ────────────────────────────────────────────────

def test_telecharger_rapport_existant(client, store, monkeypatch, data_dir):
    _peupler_atomes(store)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P', duree_ms=10))

    r = client.get('/api/admin/compilation-atomes/run')
    evs = _parser_sse(r.data)
    rapport_ev = next(e for e in evs if e['kind'] == 'rapport')

    r2 = client.get(rapport_ev['url'])
    assert r2.status_code == 200
    assert r2.mimetype == 'text/markdown'
    assert b'# Compilation des atomes' in r2.data


def test_telecharger_rapport_inexistant_404(client):
    r = client.get('/api/admin/compilation-atomes/rapport/inexistant.md')
    assert r.status_code == 404


def test_telecharger_rapport_chemin_invalide(client):
    """Sécurité : pas de path traversal."""
    r = client.get('/api/admin/compilation-atomes/rapport/..%2Fconfig.json')
    # Soit 404 (chemin valide mais introuvable), soit 400 (rejeté).
    # On accepte les deux : ce qui compte c'est qu'on ne lise PAS configuration.json.
    assert r.status_code in (400, 404)
    # Et surtout, pas de fuite du contenu de configuration.json.
    assert b'timeout_compilation_s' not in r.data


# ── Ordre des événements émis (régression v0.8.1) ────────────────────────────

def test_run_rapport_est_le_dernier_evenement(client, store, monkeypatch):
    """Le serveur DOIT émettre 'rapport' après 'fin'/'abandon'/'annule'.

    Le client utilise cet invariant pour fermer l'EventSource immédiatement
    à la réception de 'rapport' : sans ça, EventSource se reconnecte tout
    seul à la fermeture du stream serveur et le run redémarre en boucle.
    """
    _peupler_atomes(store)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P', duree_ms=10))

    r = client.get('/api/admin/compilation-atomes/run')
    evs = _parser_sse(r.data)
    kinds = [e['kind'] for e in evs]

    # 'fin' apparaît avant 'rapport'.
    assert 'fin' in kinds and 'rapport' in kinds
    assert kinds.index('fin') < kinds.index('rapport')
    # Et 'rapport' est bien le DERNIER événement.
    assert kinds[-1] == 'rapport'


# ── v0.8.3 — Conservation et téléchargement des logs d'échec ─────────────────

def test_run_ecrit_logs_echec_dans_dossier(client, store, monkeypatch,
                                            data_dir):
    """Un run avec des échecs LaTeX écrit les .tex et .log dans
    data/cache_rendus/echecs/."""
    _peupler_atomes(store)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "% TEX SOURCE\n\\foo")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(
            ok=False,
            erreurs=[ErreurLatex(ligne=42, message="Undefined \\foo")],
            log_complet="LOG COMPLET\n! Undefined control sequence.\nl.42 \\foo",
            duree_ms=500))

    r = client.get('/api/admin/compilation-atomes/run')
    evs = _parser_sse(r.data)
    atomes = [e for e in evs if e['kind'] == 'atome']

    # Tous les échecs ont nom_log et le fichier existe.
    dossier = data_dir / 'cache_rendus' / 'echecs'
    assert dossier.is_dir()
    for e in atomes:
        assert e['statut'] == STATUT_ECHEC_COMPILATION
        assert 'nom_log' in e
        assert (dossier / e['nom_log']).is_file()


def test_run_purge_dossier_echecs_au_demarrage(client, store, monkeypatch,
                                                data_dir):
    """Politique (c) : le dossier d'échecs est vidé au début de chaque run."""
    _peupler_atomes(store)
    dossier = data_dir / 'cache_rendus' / 'echecs'
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / 'ancien.log').write_text('vieux log',
                                         encoding='utf-8')

    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(ok=True, pdf_bytes=b'P', duree_ms=10))

    client.get('/api/admin/compilation-atomes/run')

    # Le vieux log a été purgé (run sans erreur → dossier vide).
    assert not (dossier / 'ancien.log').exists()


def test_telecharger_echec_log(client, store, monkeypatch, data_dir):
    """La route /echec/<nom> sert un .log existant."""
    _peupler_atomes(store)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "tex")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(
            ok=False,
            erreurs=[ErreurLatex(ligne=1, message="LaTeX Error")],
            log_complet="contenu du log à servir",
            duree_ms=100))

    # Run pour générer les fichiers d'échec.
    r = client.get('/api/admin/compilation-atomes/run')
    evs = _parser_sse(r.data)
    atomes = [e for e in evs if e['kind'] == 'atome']
    nom_log = atomes[0]['nom_log']

    # Téléchargement.
    r2 = client.get(f'/api/admin/compilation-atomes/echec/{nom_log}')
    assert r2.status_code == 200
    assert r2.mimetype == 'text/plain'
    assert b'contenu du log' in r2.data


def test_telecharger_echec_tex(client, store, monkeypatch, data_dir):
    """La route /echec/ sert aussi les .tex correspondants."""
    _peupler_atomes(store)
    monkeypatch.setattr('services.compilation_batch.generer_tex_par_type',
                        lambda conn, t, i, r, **kw: "% MON TEX SOURCE\n\\foo")
    monkeypatch.setattr('services.compilation_batch.compiler_atome',
        lambda **kw: ResultatCompilation(
            ok=False,
            erreurs=[ErreurLatex(ligne=1, message="Err")],
            log_complet="log",
            duree_ms=10))

    r = client.get('/api/admin/compilation-atomes/run')
    evs = _parser_sse(r.data)
    atomes = [e for e in evs if e['kind'] == 'atome']
    # Reconstituer le nom .tex à partir du nom .log.
    nom_tex = atomes[0]['nom_log'][:-4] + '.tex'

    r2 = client.get(f'/api/admin/compilation-atomes/echec/{nom_tex}')
    assert r2.status_code == 200
    assert b'% MON TEX SOURCE' in r2.data


def test_telecharger_echec_inexistant_404(client):
    r = client.get('/api/admin/compilation-atomes/echec/inexistant.log')
    assert r.status_code == 404


def test_telecharger_echec_extension_non_autorisee_400(client):
    """Pas de .pdf, .py, .json etc."""
    r = client.get('/api/admin/compilation-atomes/echec/secret.json')
    assert r.status_code == 400
    r = client.get('/api/admin/compilation-atomes/echec/binaire.pdf')
    assert r.status_code == 400


def test_telecharger_echec_path_traversal_rejete(client):
    """Sécurité : pas de path traversal."""
    r = client.get('/api/admin/compilation-atomes/echec/..%2Fconfig.json')
    assert r.status_code in (400, 404)
    assert b'timeout_compilation_s' not in r.data
