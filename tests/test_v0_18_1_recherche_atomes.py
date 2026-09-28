"""tests/test_v0_18_1_recherche_atomes.py — v0.18.1

Outil Recherche (Outils généraux). On vérifie les décisions de cadrage :

  D1 — périmètre du texte cherché par type (titre + corps + sections +
       items_texte selon le type) ;
  D2 — explorateur : texte vide => filtre texte inactif ;
  D4 — SENSIBLE aux accents (« médiane » ne trouve pas « mediane ») ;
       INSENSIBLE à la casse par défaut, sensible si casse_sensible=True ;
  D5 — regex (re.search, IGNORECASE selon casse) ; regex invalide => erreur ;
  D6 — agrégation Python des 3 sources de texte.

Atomes insérés directement en BDD (pas de helper ecrire_* pour tous ces
types), couvrant chaque source de texte.
"""

import pytest

from services.recherche_atomes import (
    rechercher, RechercheRegexInvalide, RechercheErreur,
    TYPES_RECHERCHE,
)


@pytest.fixture
def store_recherche(store):
    """Peuple la base avec un atome de chaque type, dont le texte
    discriminant vit dans des sources différentes :

      - notion no_1 : mot « MÉDIANE » dans le CORPS (accent + majuscule)
      - notion no_2 : mot « kurtosis » dans une SECTION (atome_sections /
                      atome_section_items) — pas dans le titre ni le corps
      - notion no_3 : mot « contrexemple » dans une SECTION titrée
                      « Exemples » (les exemples sont des sections, pas
                      l'ancienne table items_texte)
      - methode me_1 : mot « barycentre » dans le titre
      - exercice ex_1 : mot « hypoténuse » dans l'énoncé
      - fiche fi_1 : mot « réciproque » dans une SECTION (entite='fiche_resume')
      - carte ca_1 : mot « tangente » dans le verso
    """
    with store._conn() as conn:
        # notions
        conn.executemany(
            "INSERT INTO notions (id, titre, corps, num_connaissance, "
            "niveau, sequence, etat_code) VALUES (?,?,?,?,?,?,?)",
            [
                ('no_1', 'Statistiques', 'On calcule la MÉDIANE de la série.',
                 '01', 'N10', 'S01', 'valide'),
                ('no_2', 'Forme', '', '02', 'N10', 'S01', 'en_cours'),
                ('no_3', 'Exemples', 'corps neutre', '03', 'N11', 'S02',
                 'valide'),
            ],
        )
        # methode
        conn.execute(
            "INSERT INTO methodes (id, titre, corps, num_methode, niveau, "
            "sequence, etat_code) VALUES "
            "('me_1', 'Calcul du barycentre', 'texte', 1, 'N10', 'S01', "
            "'en_cours')"
        )
        # exercice
        conn.execute(
            "INSERT INTO exercices (id, titre, serie, enonce, corrige, num, "
            "serie_code, niveau, sequence, etat_code) VALUES "
            "('ex_1', 'Triangle', 'fondamental', 'Calculer l''hypoténuse.', "
            "'', 1, 'F', 'N10', 'S01', 'valide')"
        )
        # fiche
        conn.execute(
            "INSERT INTO fiches_resume (id, titre, num_fiche, niveau, "
            "sequence, etat_code) VALUES "
            "('fi_1', 'Théorèmes', 1, 'N10', 'S01', 'valide')"
        )
        # carte
        conn.execute(
            "INSERT INTO cartes_automatisme (id, niveau, sequence, num, "
            "titre, recto, verso, ordre, etat_code) VALUES "
            "('ca_1', 'N10', 'S01', 1, 'Trigo', 'recto', "
            "'La tangente vaut...', 0, 'en_cours')"
        )

        # Sections : no_2 (notion), fi_1 (fiche_resume), no_3 (notion, Exemples)
        conn.executemany(
            "INSERT INTO atome_sections (id, entite_type, entite_id, titre, "
            "ordre) VALUES (?,?,?,?,?)",
            [
                ('sec_1', 'notion', 'no_2', 'Propriété', 0),
                ('sec_2', 'fiche_resume', 'fi_1', 'Réciproque de Pythagore', 0),
                ('sec_3', 'notion', 'no_3', 'Exemples', 0),
            ],
        )
        conn.executemany(
            "INSERT INTO atome_section_items (id, section_id, ordre, corps) "
            "VALUES (?,?,?,?)",
            [
                ('it_1', 'sec_1', 0, 'Le kurtosis mesure l''aplatissement.'),
                ('it_2', 'sec_2', 0, 'Si le carré du plus grand côté...'),
                ('it_3', 'sec_3', 0, 'Voici un contrexemple éclairant.'),
            ],
        )
        conn.commit()
    return store


# ── D2 — explorateur ─────────────────────────────────────────────────────────

def test_explorateur_texte_vide_liste_tout(store_recherche):
    r = rechercher(store_recherche, niveau='N10', sequence='S01')
    # no_1, no_2, me_1, ex_1, fi_1, ca_1 → 6 atomes (no_3 est N11/S02)
    assert r['total'] == 6
    assert len(r['notion']) == 2
    assert len(r['methode']) == 1
    assert len(r['exercice']) == 1
    assert len(r['fiche']) == 1
    assert len(r['carte']) == 1


def test_explorateur_filtre_etat(store_recherche):
    valides = rechercher(store_recherche, etat='valide')
    en_cours = rechercher(store_recherche, etat='en_cours')
    ids_valides = {a['id'] for v in valides.values()
                   if isinstance(v, list) for a in v}
    assert 'no_1' in ids_valides and 'ex_1' in ids_valides
    assert 'no_2' not in ids_valides  # en_cours
    # 'tous' équivaut à pas de filtre
    tous = rechercher(store_recherche, etat='tous')
    assert tous['total'] == valides['total'] + en_cours['total']


def test_filtre_type_unique(store_recherche):
    r = rechercher(store_recherche, type='carte')
    assert r['total'] == 1
    assert r['carte'][0]['id'] == 'ca_1'
    assert r['notion'] == []  # clé présente mais vide


# ── D1 — périmètre du texte (3 sources) ──────────────────────────────────────

def test_texte_dans_corps(store_recherche):
    r = rechercher(store_recherche, texte='médiane')
    assert {a['id'] for a in r['notion']} == {'no_1'}


def test_texte_dans_section(store_recherche):
    # 'kurtosis' n'est ni dans le titre ni dans le corps de no_2 : seulement
    # dans atome_section_items.
    r = rechercher(store_recherche, texte='kurtosis')
    assert {a['id'] for a in r['notion']} == {'no_2'}


def test_texte_dans_section_exemples(store_recherche):
    # 'contrexemple' vit dans une section titrée 'Exemples' (notion no_3) —
    # c'est la source vivante des exemples (pas l'ancienne table items_texte).
    r = rechercher(store_recherche, texte='contrexemple')
    assert {a['id'] for a in r['notion']} == {'no_3'}


def test_texte_fiche_dans_section(store_recherche):
    # Les fiches n'ont pas de colonne corps : 'réciproque' est dans une
    # section (entite_type='fiche_resume').
    r = rechercher(store_recherche, texte='Réciproque')
    assert {a['id'] for a in r['fiche']} == {'fi_1'}


def test_texte_exercice_dans_enonce(store_recherche):
    r = rechercher(store_recherche, texte='hypoténuse')
    assert {a['id'] for a in r['exercice']} == {'ex_1'}


def test_texte_carte_dans_verso(store_recherche):
    r = rechercher(store_recherche, texte='tangente')
    assert {a['id'] for a in r['carte']} == {'ca_1'}


# ── D4 — accents et casse ────────────────────────────────────────────────────

def test_sensible_aux_accents(store_recherche):
    # 'médiane' trouve ; 'mediane' (sans accent) ne trouve pas.
    assert rechercher(store_recherche, texte='médiane')['total'] == 1
    assert rechercher(store_recherche, texte='mediane')['total'] == 0


def test_insensible_casse_par_defaut(store_recherche):
    # Le corps contient 'MÉDIANE' en majuscules ; on cherche en minuscules.
    assert rechercher(store_recherche, texte='médiane')['total'] == 1
    assert rechercher(store_recherche, texte='MÉDIANE')['total'] == 1


def test_casse_sensible(store_recherche):
    # casse_sensible=True : 'médiane' (minuscule) ne matche pas 'MÉDIANE'.
    assert rechercher(store_recherche, texte='médiane',
                      casse_sensible=True)['total'] == 0
    assert rechercher(store_recherche, texte='MÉDIANE',
                      casse_sensible=True)['total'] == 1


# ── D5 — regex ───────────────────────────────────────────────────────────────

def test_regex_simple(store_recherche):
    # 'm.diane' matche 'médiane' (le . matche 'é'), insensible casse.
    r = rechercher(store_recherche, texte='m.diane', regex=True)
    assert {a['id'] for a in r['notion']} == {'no_1'}


def test_regex_ancrage(store_recherche):
    # ancrage : 'barycentre$' matche le titre de me_1.
    r = rechercher(store_recherche, texte='barycentre$', regex=True)
    assert {a['id'] for a in r['methode']} == {'me_1'}


def test_regex_casse_sensible(store_recherche):
    assert rechercher(store_recherche, texte='médiane', regex=True,
                      casse_sensible=True)['total'] == 0
    assert rechercher(store_recherche, texte='MÉDIANE', regex=True,
                      casse_sensible=True)['total'] == 1


def test_regex_invalide_leve(store_recherche):
    with pytest.raises(RechercheRegexInvalide) as exc:
        rechercher(store_recherche, texte='[', regex=True)
    assert exc.value.code == 'regex_invalide'


# ── Robustesse / contrat ─────────────────────────────────────────────────────

def test_type_invalide_leve(store_recherche):
    with pytest.raises(RechercheErreur) as exc:
        rechercher(store_recherche, type='inexistant')
    assert exc.value.code == 'type_invalide'


def test_clefs_de_sortie_completes(store_recherche):
    r = rechercher(store_recherche, niveau='N10', sequence='S01')
    for t in TYPES_RECHERCHE:
        assert t in r and isinstance(r[t], list)
    assert 'total' in r
    # Pas de champ interne _texte qui fuite.
    for t in TYPES_RECHERCHE:
        for a in r[t]:
            assert '_texte' not in a
            assert set(a.keys()) == {
                'id', 'type', 'niveau', 'sequence', 'num',
                'identifiant', 'titre', 'etat_code',
            }


def test_tri_par_niveau_sequence_num(store_recherche):
    # no_1 (num 01) et no_2 (num 02) en N10/S01 → ordre 01 puis 02.
    r = rechercher(store_recherche, type='notion', niveau='N10')
    ids = [a['id'] for a in r['notion']]
    assert ids == ['no_1', 'no_2']


def test_identifiant_lisible(store_recherche):
    r = rechercher(store_recherche, type='notion', niveau='N10', sequence='S01')
    idents = {a['id']: a['identifiant'] for a in r['notion']}
    assert idents['no_1'] == 'N10/S01/Notion 01'
