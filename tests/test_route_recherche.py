"""tests/test_route_recherche.py — v0.18.1

Route GET /api/recherche : on vérifie le câblage (paramètres → service),
le format de réponse groupé, et la traduction des erreurs en HTTP 400.
La logique de recherche elle-même est couverte par
test_v0_18_1_recherche_atomes.py ; ici on teste l'intégration HTTP.
"""

import pytest


@pytest.fixture
def client_avec_atomes(client, app):
    """Insère quelques atomes via le store de l'app (même base que le client)."""
    store = app.json_store
    with store._conn() as conn:
        conn.executemany(
            "INSERT INTO notions (id, titre, corps, num_connaissance, "
            "niveau, sequence, etat_code) VALUES (?,?,?,?,?,?,?)",
            [
                ('no_1', 'Médianes', 'La médiane partage la série.',
                 '01', 'N10', 'S01', 'valide'),
                ('no_2', 'Moyenne', 'somme divisée par effectif',
                 '02', 'N10', 'S01', 'en_cours'),
            ],
        )
        conn.execute(
            "INSERT INTO cartes_automatisme (id, niveau, sequence, num, "
            "titre, recto, verso, ordre, etat_code) VALUES "
            "('ca_1', 'N10', 'S01', 1, 'Stat', 'recto', 'médiane', 0, 'valide')"
        )
        conn.commit()
    return client


def test_recherche_explorateur(client_avec_atomes):
    r = client_avec_atomes.get('/api/recherche?niveau=N10&sequence=S01')
    assert r.status_code == 200
    data = r.get_json()
    assert data['total'] == 3
    # Les 5 clés de type sont toujours présentes.
    for t in ('notion', 'methode', 'exercice', 'fiche', 'carte'):
        assert t in data
    assert len(data['notion']) == 2
    assert len(data['carte']) == 1


def test_recherche_texte(client_avec_atomes):
    r = client_avec_atomes.get('/api/recherche?texte=médiane')
    data = r.get_json()
    # 'médiane' dans le corps de no_1 et le verso de ca_1.
    ids = {a['id'] for v in data.values() if isinstance(v, list) for a in v}
    assert ids == {'no_1', 'ca_1'}


def test_recherche_sensible_accents(client_avec_atomes):
    assert client_avec_atomes.get(
        '/api/recherche?texte=mediane').get_json()['total'] == 0
    assert client_avec_atomes.get(
        '/api/recherche?texte=médiane').get_json()['total'] == 2


def test_recherche_filtre_etat(client_avec_atomes):
    r = client_avec_atomes.get('/api/recherche?etat=en_cours')
    data = r.get_json()
    ids = {a['id'] for v in data.values() if isinstance(v, list) for a in v}
    assert ids == {'no_2'}


def test_recherche_filtre_type(client_avec_atomes):
    r = client_avec_atomes.get('/api/recherche?type=carte')
    data = r.get_json()
    assert data['total'] == 1
    assert data['carte'][0]['id'] == 'ca_1'
    assert data['notion'] == []


def test_recherche_regex(client_avec_atomes):
    r = client_avec_atomes.get('/api/recherche?texte=m.diane&regex=1')
    data = r.get_json()
    ids = {a['id'] for v in data.values() if isinstance(v, list) for a in v}
    assert ids == {'no_1', 'ca_1'}


def test_recherche_regex_invalide_400(client_avec_atomes):
    r = client_avec_atomes.get('/api/recherche?texte=%5B&regex=1')  # '['
    assert r.status_code == 400
    assert r.get_json()['code'] == 'regex_invalide'


def test_recherche_type_invalide_400(client_avec_atomes):
    r = client_avec_atomes.get('/api/recherche?type=inexistant')
    assert r.status_code == 400
    assert r.get_json()['code'] == 'type_invalide'


def test_recherche_casse_sensible(client_avec_atomes):
    # Le corps contient 'médiane' minuscule ; titre 'Médianes' majuscule.
    r = client_avec_atomes.get(
        '/api/recherche?texte=Médiane&casse_sensible=1')
    data = r.get_json()
    # 'Médiane' (M majuscule) matche 'Médianes' (titre no_1) mais pas
    # 'médiane' minuscule du corps/verso. no_1 a le titre → match.
    ids = {a['id'] for v in data.values() if isinstance(v, list) for a in v}
    assert ids == {'no_1'}
