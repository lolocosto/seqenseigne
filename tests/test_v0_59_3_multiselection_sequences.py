"""tests/test_v0_59_3_multiselection_sequences.py — v0.59.3

Demande de Laurent (17 novembre 2026, 22 h), `doc/redemarrage_v0_59_3.md` :

    « Ajouter la possibilité de sélectionner plusieurs séquences, comme ça je
    les repasse toutes "en cours" en une seule opération. »

L'import des lots (`outils/import_lot6e.py`) ne touche jamais une séquence
validée : 24 séquences l'étaient chez lui (N11 entier, N09 sauf A1), d'où des
livrets sans encarts. L'atelier Séquence (niveau), sans séquence choisie,
liste désormais les séquences du niveau avec la multisélection d'AtelierEditeur
(tests vitest `v0_59_3_multiselection_sequences.test.js`) ; chaque changement
d'état passe par la route UNITAIRE PATCH …/<sn_id>/etat.

Invariants protégés ici (serveur) :
  L  la liste donne chaque séquence avec son état, son périmètre (principal,
     mise en route, archive) et les référentiels internes qu'elle touche :
     « vivants » (en cours / validé, périmètre RI1) et « figés » (verrouillé /
     utilisé, code présent dans l'instantané) — c'est ce qu'annonce
     l'avertissement d'avant « Repasser en cours » ;
  G  un groupe repassé en cours puis revalidé = une suite d'appels unitaires :
     mêmes règles (repasser en cours toujours permis, valider = contrôle
     pédagogique), un refus porte ses raisons (au premier niveau de la réponse,
     où l'interface les lit) et n'empêche pas les autres ;
  R  un référentiel VALIDÉ non verrouillé (comme 2027_N11) retombe « en
     cours » tant que ses séquences ne sont pas revalidées, puis redevient
     « validé » ; un référentiel VERROUILLÉ (comme 2026_N09, 2025_N11b) ne
     bouge pas : état et instantané identiques ; le référentiel de mises en
     route (comme 2026_N09b) n'est pas touché par les séquences principales ;
  D  déverrouiller puis reverrouiller (cas 2026_N09) : l'instantané est retiré
     puis réécrit depuis l'atelier, avec les codes et les séances du moment ;
  P  atelier Référentiel : la liste des référentiels défile (gabarit CSS).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_v0_52_2_documents_6e import app_6e  # noqa: E402,F401

APPLI = Path(__file__).resolve().parent.parent

# S01 (fixture 6e) rendue validable ; S02 validable ; S03 incomplète (refusée) ;
# M01 mise en route ; X02 archive. R09 : principal (Fiches) ; R09B : mises en
# route, validé ; R09L : principal 2025 verrouillé, instantané écrit par l'atelier.
SQL_GROUPE = r"""
UPDATE objectifs SET critere_F = 'cf', critere_A = 'ca', critere_E = 'ce';
INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) VALUES ('o603', 'A', 'aa1', 2);
INSERT OR IGNORE INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id) VALUES
    ('sc6_s02', 'C03', 'S02', 2, 'Comparaison', 'th_6A'),
    ('sc6_s03', 'C03', 'S03', 3, 'Opérations', 'th_6A');
INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres) VALUES
    ('sn62', 'N09', 'S02', ''), ('sn63', 'N09', 'S03', ''), ('sn6m', 'N09', 'M01', '');
INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero, nb_seances_R_AE) VALUES
    ('p621', 'sn62', 1, 0), ('p631', 'sn63', 1, 0);
INSERT INTO objectifs (id, partie_id, code, nom, critere_F, critere_A, critere_E, nb_seances) VALUES
    ('o622', 'p621', '02', 'Comparer deux nombres', 'cf', 'ca', 'ce', 2),
    ('o632', 'p631', '02', 'Poser une addition', 'cf', 'ca', 'ce', 1);
INSERT INTO exercices (id, serie, titre, niveau, sequence, num, serie_code, fichier, enonce,
                       corrige, remed_enonce, remed_corrige) VALUES
    ('f21', 'fondamental', 'Comparer', 'N09', 'S02', 1, 'F', '', 'F', '', '', ''),
    ('a21', 'avancé', 'Ranger', 'N09', 'S02', 1, 'A', '', 'A', '', '', '');
INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) VALUES
    ('o622', 'F', 'f21', 1), ('o622', 'A', 'a21', 1);
INSERT INTO fiches_resume (id, titre, objectif_id, num_fiche, niveau, sequence, fichier) VALUES
    ('fr21', 'Comparer', 'o622', 1, 'N09', 'S02', '');
UPDATE exercices SET etat_code = 'valide' WHERE niveau = 'N09';
UPDATE fiches_resume SET etat_code = 'valide' WHERE niveau = 'N09';
UPDATE evaluations SET etat_code = 'valide' WHERE niveau = 'N09';
INSERT INTO referentiel_niveaux (id, niveau, version, etat, gabarit_documents, type_ref) VALUES
    ('R09B', 'N09', '2026b', 'valide', 'sixieme', 'mer'),
    ('R09L', 'N09', '2025', 'valide', 'sixieme', 'principal');
"""

URL_ETAT = "/api/v2/sequences-par-niveau/{}/etat"


@pytest.fixture
def cl(app_6e):
    from services import referentiels_internes as ri
    with app_6e.json_store._conn() as c:
        c.executescript(SQL_GROUPE)
        ri.ecrire_instantane(c, "R09L")
        c.execute("UPDATE referentiel_niveaux SET etat = 'verrouille' WHERE id = 'R09L'")
        c.commit()
    return app_6e.test_client()


def _liste(cl):
    r = cl.get("/api/v2/sequences-par-niveau?niveau=N09")
    assert r.status_code == 200
    return r.get_json()


def _etats(cl):
    return {s["code"]: s["etat_code"] for s in _liste(cl)["sequences"]}


def _groupe(cl, ids, cible):
    """Ce que fait AtelierEditeur.selectionMultiAppliquerEtat : un PATCH par
    séquence, on continue après un refus."""
    return {i: cl.patch(URL_ETAT.format(i), json={"etat_code": cible}) for i in ids}


def _instantane(app, ref_id):
    with app.json_store._conn() as c:
        return {t: sorted(tuple(r) for r in c.execute(
                    f"SELECT * FROM {t} WHERE referentiel_id = ?", (ref_id,)))
                for t in ("referentiel_sequences", "referentiel_parties", "referentiel_objectifs")}


def _etat_ref(app, ref_id):
    from services.referentiel_validation import maj_etat_lazy
    with app.json_store._conn() as c:
        return maj_etat_lazy(c, ref_id)


# ── L Liste ──────────────────────────────────────────────────────────────────

def test_liste_des_sequences_du_niveau_avec_perimetre_et_referentiels_touches(cl):
    """L'avertissement d'avant « Repasser en cours » cite les référentiels
    qu'il faut : un principal ne touche pas le référentiel des mises en route,
    l'archive ne touche rien, un verrouillé n'est cité que pour ses codes."""
    d = _liste(cl)
    assert [s["code"] for s in d["sequences"]] == ["S01", "S02", "S03", "M01", "X02"]
    par = {s["code"]: s for s in d["sequences"]}
    assert par["S01"]["perimetre"] == "principal"
    assert par["S01"]["referentiels_vivants"] == ["R09"]
    assert par["S01"]["referentiels_figes"] == ["R09L"]
    assert par["M01"]["perimetre"] == "mer"
    assert par["M01"]["referentiels_vivants"] == ["R09B"]
    assert par["M01"]["referentiels_figes"] == []
    assert par["X02"] == {**par["X02"], "perimetre": "archive",
                          "referentiels_vivants": [], "referentiels_figes": []}
    assert {r["id"]: (r["etat"], r["fige"]) for r in d["referentiels"]} == {
        "R09": ("en_cours", False), "R09B": ("valide", False), "R09L": ("verrouille", True)}
    assert cl.get("/api/v2/sequences-par-niveau").status_code == 400


# ── G Groupe ─────────────────────────────────────────────────────────────────

def test_groupe_valide_puis_repasse_en_cours_puis_revalide_par_la_route_unitaire(cl):
    rep = _groupe(cl, ["sn6", "sn62", "sn63"], "valide")
    assert rep["sn6"].status_code == 200 and rep["sn62"].status_code == 200
    # S03 refusée : comptée avec sa raison, sans empêcher les autres.
    assert rep["sn63"].status_code == 400
    d = rep["sn63"].get_json()
    assert d["code"] == "validation_pedagogique_echec"
    assert d["raisons"] == d["details"]["raisons"]
    assert any("n'a pas d'exercice" in x for x in d["raisons"])
    assert _etats(cl)["S01"] == "valide" and _etats(cl)["S02"] == "valide"
    assert _etats(cl)["S03"] == "en_cours"

    # Repasser en cours en groupe : toujours permis.
    rep = _groupe(cl, ["sn6", "sn62"], "en_cours")
    assert all(r.status_code == 200 for r in rep.values())
    assert {k: v for k, v in _etats(cl).items() if k in ("S01", "S02")} == \
        {"S01": "en_cours", "S02": "en_cours"}

    # Revalider en groupe : même contrôle qu'une par une.
    rep = _groupe(cl, ["sn6", "sn62"], "valide")
    assert all(r.status_code == 200 for r in rep.values())
    assert _etats(cl)["S01"] == "valide"


def test_une_sequence_validee_est_en_lecture_seule_et_le_redevient_modifiable_en_groupe(cl):
    """C'est la raison de la demande : l'import et la saisie refusent une
    séquence validée ; repassée en cours, elle accepte de nouveau."""
    _groupe(cl, ["sn6"], "valide")
    r = cl.patch("/api/v2/objectifs/o602/nom", json={"nom": "Nouveau nom"})
    assert r.status_code == 409
    _groupe(cl, ["sn6"], "en_cours")
    assert cl.patch("/api/v2/objectifs/o602/nom", json={"nom": "Nouveau nom"}).status_code == 200


# ── R Référentiels ───────────────────────────────────────────────────────────

def test_referentiel_valide_non_verrouille_retombe_en_cours_puis_redevient_valide(cl, app_6e):
    """Comme 2027_N11 : validé tant que ses séquences le sont ; repassées en
    cours, il retombe « en cours » (maj_etat_lazy) ; revalidées, il revient."""
    _groupe(cl, ["sn6", "sn62", "sn63"], "valide")
    # S03 incomplète : on la complète pour que tout le périmètre soit validable.
    with app_6e.json_store._conn() as c:
        c.execute("DELETE FROM sequence_parties WHERE id = 'p631'")
        c.execute("DELETE FROM objectifs WHERE id = 'o632'")
        c.execute("DELETE FROM sequences_par_niveau WHERE id = 'sn63'")
        c.commit()
    assert _etat_ref(app_6e, "R09") == "valide"
    _groupe(cl, ["sn6", "sn62"], "en_cours")
    # La liste de l'atelier annonce l'état à jour (sans attendre l'ouverture
    # du référentiel, qui seule réécrit l'état stocké).
    assert {r["id"]: r["etat"] for r in _liste(cl)["referentiels"]}["R09"] == "en_cours"
    assert _etat_ref(app_6e, "R09") == "en_cours"
    with app_6e.json_store._conn() as c:
        from services.referentiel_validation import evaluer_eligibilite_validation
        assert evaluer_eligibilite_validation(c, "R09")["details"]["sequences_non_validees"] \
            == ["S01", "S02"]
    _groupe(cl, ["sn6", "sn62"], "valide")
    assert _etat_ref(app_6e, "R09") == "valide"


def test_referentiel_verrouille_et_referentiel_de_mises_en_route_ne_bougent_pas(cl, app_6e):
    """Comme 2026_N09 / 2025_N11b (verrouillés) et 2026_N09b (mises en route) :
    repasser les séquences PRINCIPALES en cours ne change ni l'état ni
    l'instantané du verrouillé, ni l'état du référentiel de mises en route."""
    avant = _instantane(app_6e, "R09L")
    assert [s[1] for s in avant["referentiel_sequences"]] == ["S01", "S02", "S03"]
    assert _etat_ref(app_6e, "R09B") == "valide"   # M01 hors périmètre principal
    _groupe(cl, ["sn6", "sn62"], "valide")
    _groupe(cl, ["sn6", "sn62"], "en_cours")
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE objectifs SET nb_seances = 3 WHERE id = 'o602'")
        c.commit()
    assert _etat_ref(app_6e, "R09L") == "verrouille"
    assert _instantane(app_6e, "R09L") == avant
    with app_6e.json_store._conn() as c:
        etat_mer = c.execute("SELECT etat FROM referentiel_niveaux WHERE id='R09B'").fetchone()[0]
    assert etat_mer == "valide"


def test_deverrouiller_puis_reverrouiller_reecrit_l_instantane_depuis_l_atelier(cl, app_6e):
    """Cas 2026_N09 : déverrouillé (aucune progression : état « verrouillé »,
    pas « utilisé »), son instantané est retiré ; au reverrouillage, il est
    réécrit avec les codes et les séances du moment."""
    from services import referentiels as svc_ref
    from services import referentiels_internes as ri
    with app_6e.json_store._conn() as c:
        svc_ref.deverrouiller(c, "R09L")
        assert c.execute("SELECT COUNT(*) FROM referentiel_sequences WHERE "
                         "referentiel_id='R09L'").fetchone()[0] == 0
        c.execute("UPDATE objectifs SET nb_seances = 3 WHERE id = 'o602'")
        res = ri.ecrire_instantane(c, "R09L")
        c.commit()
    assert res["nb_sequences"] == 3
    apres = _instantane(app_6e, "R09L")
    assert [s[1] for s in apres["referentiel_sequences"]] == ["S01", "S02", "S03"]
    o602 = [o for o in apres["referentiel_objectifs"] if o[1] == "S01" and o[2] == "02"]
    assert o602 and 3 in o602[0]
    with app_6e.json_store._conn() as c:
        with pytest.raises(ValueError):          # « utilisé » : pas de déverrouillage
            c.execute("UPDATE referentiel_niveaux SET etat='utilise' WHERE id='R09L'")
            svc_ref.deverrouiller(c, "R09L")


# ── P Atelier Référentiel : défilement de la liste ───────────────────────────

def test_atelier_referentiel_la_liste_des_referentiels_defile():
    """Demande de Laurent (17 novembre, 22 h 15) : les référentiels de 6e ne
    tenaient pas dans le panneau, sans barre de défilement. La liste défile
    seule (comme .atl-list) ; le panneau aussi si le haut prend toute la place."""
    css = (APPLI / "static" / "app.css").read_text(encoding="utf-8")
    regle = re.search(r"#atl-ref-sidebar > \.atl-sidebar-body \{([^}]*)\}", css)
    assert regle and "overflow-y: auto" in regle.group(1) and "flex: 1" in regle.group(1)
    panneau = re.search(r"#atl-ref-sidebar \{([^}]*)\}", css).group(1)
    assert "overflow-y: auto" in panneau and "min-width: 200px" in panneau
    html = (APPLI / "templates" / "index.html").read_text(encoding="utf-8")
    assert '<div class="atl-sidebar-body" id="atl-ref-liste">' in html
