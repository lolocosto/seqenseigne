"""tests/test_v0_52_5_renumerotation_cycle3.py — v0.52.5, découpage de la géométrie

Décision de Laurent (19 octobre 2026) : la séquence S05 « Géométrie plane »
est découpée en S05 Points, segments, droites ; S06 Cercles ; S07 Angles ;
S08 Triangles, et les séquences suivantes sont décalées (S06 → S09 …
S10 → S13). Chez Laurent, la v0.52.0 a déjà créé S01 à S10 avec les anciens
noms (`sequences_du_cycle`, C03) : l'outil d'import doit les mettre à jour
sur place, sans rien perdre ni créer en double, et de façon idempotente.
Une séquence-niveau du cycle 3 déjà présente sous un code qui change de sens
porte le contenu de l'ancien sens : anomalie, séquence non renommée, lot
non importé (doc/redemarrage_v0_52_5.md, « Découpage de la géométrie »).
"""

from __future__ import annotations

import copy
import json
import sqlite3

from outils import import_lot6e as imp
from tests.test_v0_52_0_import_lot6e import base  # noqa: F401  (fixture)

ANCIENNES = [("S01", "Nombres entiers et décimaux, fractions", "A"), ("S02", "Comparaison de nombres", "A"),
             ("S03", "Opérations", "A"), ("S04", "Pré-algèbre", "A"), ("S05", "Géométrie plane", "C"),
             ("S06", "Symétrie axiale", "C"), ("S07", "Gestion de données", "D"), ("S08", "Probabilité", "D"),
             ("S09", "Proportionnalité", "E"), ("S10", "Pensée informatique", "F")]
NOUVELLES = [("S05", "Points, segments, droites", "C"), ("S06", "Cercles", "C"), ("S07", "Angles", "C"),
             ("S08", "Triangles", "C"), ("S09", "Symétrie axiale", "C"), ("S10", "Gestion de données", "D"),
             ("S11", "Probabilité", "D"), ("S12", "Proportionnalité", "E"), ("S13", "Pensée informatique", "F")]


def _ref_v0520() -> dict:
    """Référentiel tel que la v0.52.0 l'a appliqué : dix séquences, anciens noms."""
    ref = copy.deepcopy(imp.charger_referentiel())
    ref["sequences"] = [{"code": c, "numero": int(c[1:]), "nom": n, "theme": t} for c, n, t in ANCIENNES]
    return ref


def _executer(db, ref, lots=()):
    c = sqlite3.connect(db)
    r = imp.Rapport()
    imp.executer(c, list(lots), ref, r, db.parent / "images", ecrire_fichiers=False)
    c.commit()
    c.close()
    return r


def _c03(db) -> dict:
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    rows = {r["code"]: dict(r) for r in c.execute(
        "SELECT s.id, s.code, s.numero, s.nom, t.code AS theme FROM sequences_du_cycle s "
        "LEFT JOIN themes t ON t.id = s.theme_id WHERE s.cycle_code='C03'")}
    c.close()
    return rows


def _base_a_dix(db):
    _executer(db, _ref_v0520())
    avant = _c03(db)
    assert [c for c in sorted(avant) if c.startswith("S")] == [c for c, _, _ in ANCIENNES]
    return avant


def test_base_a_dix_sequences_renommees_sur_place_sans_perte_ni_doublon(base):  # noqa: F811
    avant = _base_a_dix(base)
    r = _executer(base, imp.charger_referentiel())
    apres = _c03(base)
    # Rien de perdu : mêmes identifiants pour S01 à S10 et pour les archives X01…X16.
    for code, row in avant.items():
        assert apres[code]["id"] == row["id"], code
    # Rien en double : un seul enregistrement par code, treize séquences S.
    assert sorted(c for c in apres if c.startswith("S")) == [f"S{i:02d}" for i in range(1, 14)]
    for code, nom, theme in NOUVELLES:
        assert (apres[code]["nom"], apres[code]["theme"], apres[code]["numero"]) == (nom, theme, int(code[1:]))
    assert apres["S01"] == avant["S01"]
    assert "séquence S06 Cercles (thème C) : renommée (était « Symétrie axiale »)" in r.cycle
    assert "séquence S11 Probabilité (thème D) : créée" in r.cycle
    assert not any("change" in a or "devient" in a for a in r.anomalies)


def test_renumerotation_idempotente_le_second_passage_ne_change_rien(base):  # noqa: F811
    _base_a_dix(base)
    _executer(base, imp.charger_referentiel())
    une = _c03(base)
    r = _executer(base, imp.charger_referentiel())
    assert _c03(base) == une
    assert all(l.endswith(": inchangée") for l in r.cycle if l.startswith("séquence "))


def test_base_neuve_recoit_directement_les_treize_sequences(base):  # noqa: F811
    r = _executer(base, imp.charger_referentiel())
    rows = _c03(base)
    assert sorted(c for c in rows if c.startswith("S")) == [f"S{i:02d}" for i in range(1, 14)]
    assert sum(1 for c in rows if c.startswith("X")) == 16            # anciennes séquences archivées
    for code, nom, theme in NOUVELLES:
        assert (rows[code]["nom"], rows[code]["theme"]) == (nom, theme)
    assert all(l.endswith(": créée") for l in r.cycle if l.startswith("séquence "))


def _lot(dossier, seq, titre, code, partie, intitule):
    d = dossier / seq
    (d / "figures").mkdir(parents=True)
    lot = {"sequence": seq, "titre": titre, "theme": "C", "objectifs": [
        {"code": code, "partie": partie, "intitule": intitule, "activites": [],
         "fiche_resume": {"titre": "Fiche", "latex": "Texte."},
         "exercices": [{"num": 1, "serie": "F", "titre": "Ex", "enonce": "E", "corrige": "C",
                        "remed_enonce": "", "remed_corrige": "", "figures": []}]}]}
    (d / f"{seq}.json").write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")


def test_sequence_niveau_sous_un_code_qui_change_de_sens_signalee_et_lot_non_importe(base, tmp_path):  # noqa: F811
    """Une N09/S06 « Symétrie axiale » déjà importée : renommer S06 en
    « Cercles » rattacherait son contenu au nouveau sens."""
    _base_a_dix(base)
    c = sqlite3.connect(base)
    c.execute("INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres, etat_code) "
              "VALUES ('sn_sym', 'N09', 'S06', '', 'valide')")
    c.commit()
    c.close()
    lots = tmp_path / "lots"
    _lot(lots, "S06", "Cercles", "S06-02", 1, "Placer des points à une distance donnée à l'aide d'un cercle")
    _lot(lots, "S07", "Angles", "S07-03", 1, "Mesurer un angle")
    r = _executer(base, imp.charger_referentiel(), imp.charger_lots(lots))
    rows = _c03(base)
    assert rows["S06"]["nom"] == "Symétrie axiale"                    # non renommée
    assert rows["S07"]["nom"] == "Angles"                             # les autres suivent
    assert any("séquence S06" in a and "N09/S06 (valide)" in a and "lot non importé" in a
               for a in r.anomalies)
    c = sqlite3.connect(base)
    n06 = c.execute("SELECT COUNT(*) FROM exercices WHERE niveau='N09' AND sequence='S06'").fetchone()[0]
    n07 = c.execute("SELECT COUNT(*) FROM exercices WHERE niveau='N09' AND sequence='S07'").fetchone()[0]
    sn = c.execute("SELECT COUNT(*) FROM sequences_par_niveau WHERE niveau='N09' AND sequence_code='S06'"
                   ).fetchone()[0]
    c.close()
    assert (n06, n07, sn) == (0, 1, 1)                                # rien créé en S06, ni en double


def test_sequence_niveau_deja_au_nouveau_sens_n_est_pas_une_anomalie(base, tmp_path):  # noqa: F811
    """Après le découpage, N09/S06 Cercles existe : un nouvel import n'y voit
    plus de changement de sens (le nom est déjà le bon)."""
    lots = tmp_path / "lots"
    _lot(lots, "S06", "Cercles", "S06-02", 1, "Placer des points à une distance donnée à l'aide d'un cercle")
    _executer(base, imp.charger_referentiel(), imp.charger_lots(lots))
    r = _executer(base, imp.charger_referentiel(), imp.charger_lots(lots))
    assert not any("devient" in a for a in r.anomalies)
    assert not r.sequences_bloquees
