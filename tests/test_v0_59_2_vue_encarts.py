"""tests/test_v0_59_2_vue_encarts.py — v0.59.2

Demandes de Laurent du 17 novembre 2026 (`doc/redemarrage_v0_59_2.md`) :

  1. « Un document chapeau pour le référentiel, à destination de l'enseignant,
     qui récapitule par domaine les différentes séquences avec les objectifs
     de chaque séquence et le nombre de semaines qu'on met sur chaque partie
     de séquence », généré automatiquement pour tous les référentiels, à
     partir du nombre de séances par objectif (pas de nouveau champ).
  2. Encarts du livret (« Le saviez-vous ? », « Point histoire », « Les maths
     dans la vraie vie », « Défi ») « quand ça a un sens, pas de nombre cible ».
  3. L'import horodatait en heure locale : un document compilé moins d'une
     heure après un import s'affichait « périmé ».

Invariants protégés :
  V1 la vue d'ensemble est en tête de TOUS les catalogues (ordre 0 : les autres
     documents gardent leur ordre) ; un référentiel modifiable déjà créé la
     reçoit à la première lecture ; un référentiel figé garde sa liste ;
  V2 source : tables de l'atelier (modifiable) ou instantané (figé, externe) ;
  V3 durée d'une partie = somme des séances de ses objectifs, « Cours »
     compris ; jamais doublée par le champ de durée d'un externe ou d'une Mnn ;
  V4 3 séances = 1 semaine, arrondi au plus proche, non-multiple signalé ;
  V5 référentiel figé : calculée à la volée, rien n'est écrit ;
  S  clés de lot `seances`, `seances_cours` : écrites si présentes, gardées si
     absentes (saisie de l'atelier), idempotent ;
  E  encarts : contrôle, import idempotent où le lot fait foi (sans clé : rien
     ne bouge), rendu à la bonne place, défi corrigé seulement, livret sans
     encart identique, module v0.15 ;
  H  horodatage de l'import en UTC, même référence que la péremption.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from outils import import_lot6e as imp
from services import encarts as enc
from services import gabarits_documents as gd
from services import vue_ensemble_referentiel as ve
from tests.test_v0_52_0_import_lot6e import base as base_v052  # noqa: F401
from tests.test_v0_58_0_migration_themes_codes import _ins  # noqa: F401
from tests.test_v0_59_0_ref4e_fiches import (  # noqa: F401
    LOT_ESSAI,
    _archiver,
    _importer,
    _table_reduite,
    base,
    base4e,
)

APPLI = Path(__file__).resolve().parent.parent
DTX = APPLI / "paquet" / "seqenseigne-style6e.dtx"
STY = APPLI / "paquet" / "seqenseigne-style6e.sty"


def _conn(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


def _lot(tmp_path, modif=None) -> Path:
    """Copie du lot d'essai A1 (objectifs A1-02 : F01, F02, A01, E01 ; A1-03 :
    F03, A02 ; une carte mentale en partie 1), modifiée par `modif(lot)`."""
    d = tmp_path / "lot4e"
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(LOT_ESSAI, d)
    f = d / "A1" / "A1.json"
    lot = json.loads(f.read_text(encoding="utf-8"))
    if modif:
        modif(lot)
    f.write_text(json.dumps(lot, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def _seances(lot):
    lot["seances_cours"] = {"1": 1}
    for o, n in zip(lot["objectifs"], (2, 1)):
        o["seances"] = n


ENCARTS = {
    "A1-02": [
        {"type": "savoir", "titre": "Signes", "position": "apres_exercice", "exercice": "F01",
         "texte": "Texte après F01.", "source": "Calcul."},
        {"type": "defi", "titre": "Énigme", "position": "fin_objectif",
         "texte": "Trouve deux relatifs.", "solution": "$-2$ et $3$."},
    ],
    "A1-03": [
        {"type": "histoire", "titre": "Brahmagupta", "position": "apres_activite",
         "texte": "En 628, Brahmagupta énonce la règle des signes.",
         "source": "Brahmasphutasiddhanta (628)."},
    ],
}
ENCARTS_PARTIE = [
    {"partie": 1, "type": "vraievie", "titre": "Températures", "largeur": "demi",
     "texte": "Il fait $-3$\\,°C.", "source": "Exemple."},
    {"partie": 1, "type": "savoir", "titre": "Mer Morte", "largeur": "demi",
     "texte": "Ses rives sont à plus de 430\\,m sous le niveau de la mer.", "source": "Atlas."},
]


def _encarts(lot):
    for o in lot["objectifs"]:
        if o["code"] in ENCARTS:
            o["encarts"] = json.loads(json.dumps(ENCARTS[o["code"]]))
    lot["encarts"] = json.loads(json.dumps(ENCARTS_PARTIE))


@pytest.fixture
def base4e_imp(base4e, tmp_path):
    """4e archivée + lot A1 importé avec séances (Cours 1, A1-02 : 2, A1-03 : 1)
    et encarts ; référentiel « 2027_N11 » en cours (Fiches)."""
    assert _archiver(base4e, "--apply", "--yes") == 0
    lots = _lot(tmp_path, lambda l: (_seances(l), _encarts(l)))
    assert _importer(base4e, lots, "--apply", "--yes") == 0
    c = sqlite3.connect(base4e)
    _ins(c, "referentiel_niveaux", id="2027_N11", niveau="N11", version="2027",
         etat="en_cours", source="interne", type_ref="principal",
         gabarit_documents="sixieme", cartes_automatisme=0)
    c.commit()
    c.close()
    return base4e


# ── V4 Règle des semaines ────────────────────────────────────────────────────

def test_regle_de_laurent_trois_seances_font_une_semaine_arrondi_au_plus_proche():
    assert [ve.semaines(x) for x in (3, 6, 9)] == [1, 2, 3]
    assert ve.semaines(7) == 2 and ve.semaines(8) == 3      # arrondi au plus proche
    assert ve.semaines(4.5) == 2                            # demi : au-dessus
    assert ve.semaines(0) == 0
    assert ve.multiple_de_3(6) and not ve.multiple_de_3(7) and not ve.multiple_de_3(4.5)


# ── V1 Catalogue ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("gabarit,type_ref,cartes", [
    ("cycle4", "principal", False), ("sixieme", "principal", False),
    ("sixieme", "principal", True), ("sixieme", "mer", False), ("cycle4", "mer", False)])
def test_vue_ensemble_en_tete_de_tous_les_catalogues_le_reste_inchange(gabarit, type_ref,
                                                                        cartes):
    """« généré automatiquement pour tous les référentiels » : cycle 4, Fiches
    (avec ou sans cartes), mises en route ; les autres types gardent leur ordre."""
    cat = gd.catalogue_type(gabarit, type_ref, cartes)
    assert cat[0].cle == "vue_ensemble" and cat[0].options == {"actif": False}
    assert [t.cle for t in cat].count("vue_ensemble") == 1
    if type_ref == "mer" and gabarit == "sixieme":
        reste = gd._CATALOGUE_MER_FICHES
    elif cartes:
        reste = gd._CATALOGUE_SIXIEME + gd._types_cartes() + (gd.TYPE_TESTS_COURTS,)  # v0.60.1
    else:
        reste = gd._catalogue_cycle4() if gabarit == "cycle4" else gd._CATALOGUE_SIXIEME
    assert tuple(t.cle for t in cat[1:]) == tuple(t.cle for t in reste)


def test_vue_ensemble_hors_des_9_types_historiques_interface_generique_et_jamais_perimee():
    from services import peremption_atomes as pa
    from services import referentiel_documents as rd
    assert "vue_ensemble" not in rd.TYPES_DOCUMENT
    assert pa.tables_atomes_pertinentes("vue_ensemble") == []
    assert gd.description_interface("vue_ensemble")["libelle"] == "Vue d'ensemble du référentiel"


def test_referentiel_modifiable_deja_cree_recoit_la_vue_en_ordre_0_sans_decaler(base4e_imp):
    from services.referentiel_documents import lister_documents
    c = _conn(base4e_imp)
    for i, t in enumerate(gd._CATALOGUE_SIXIEME, start=1):        # liste d'avant v0.59.2
        _ins(c, "referentiel_documents", id=f"rd_{i}", referentiel_id="2027_N11",
             type_document=t.cle, options='{"actif": false}', ordre=i)
    c.commit()
    docs = lister_documents(c, "2027_N11")
    assert [(d["type_document"], d["ordre"]) for d in docs][0] == ("vue_ensemble", 0)
    assert [(d["type_document"], d["ordre"]) for d in docs[1:]] == \
        [(t.cle, i) for i, t in enumerate(gd._CATALOGUE_SIXIEME, start=1)]


def test_referentiel_fige_garde_sa_liste_sa_vue_se_calcule_a_la_volee(base4e_imp):
    """V5 : 2025_N11b verrouillé — pas de ligne ajoutée (documents figés et
    empreinte intacts), vue tirée de son instantané."""
    from services.referentiel_documents import lister_documents
    c = _conn(base4e_imp)
    _ins(c, "referentiel_documents", id="rd_f1", referentiel_id="2025_N11b",
         type_document="livret_sequence", options='{"actif": true}', ordre=1)
    c.commit()
    avant = [tuple(r) for r in c.execute("SELECT * FROM referentiel_documents WHERE "
                                         "referentiel_id='2025_N11b'")]
    docs = lister_documents(c, "2025_N11b")
    assert "vue_ensemble" not in [d["type_document"] for d in docs]
    assert [tuple(r) for r in c.execute("SELECT * FROM referentiel_documents WHERE "
                                        "referentiel_id='2025_N11b'")] == avant
    st = ve.structure(c, "2025_N11b")
    assert st["source"] == "instantane"
    assert [s["code"] for d in st["domaines"] for s in d["sequences"]] == ["S03"]
    assert "Figé" in ve.generer_vue_ensemble(c, "2025_N11b")


def test_referentiel_fige_jamais_initialise_avec_la_vue(base4e_imp):
    """Externe utilisé jamais ouvert : ses documents s'initialisent à la première
    lecture (règle d'avant), mais sans la vue d'ensemble (calculée à la volée)."""
    from services.referentiel_documents import lister_documents
    c = _conn(base4e_imp)
    _ins(c, "referentiel_niveaux", id="X2026_N11", niveau="N11", version="X2026",
         etat="utilise", source="externe", type_ref="principal", annee="2026-2027")
    c.commit()
    types = [d["type_document"] for d in lister_documents(c, "X2026_N11")]
    assert types and "vue_ensemble" not in types


def test_route_a_la_volee_rend_le_tex_sans_rien_ecrire(base4e_imp):
    from app import create_app
    data = base4e_imp.parent
    avant = sorted(p.relative_to(data) for p in data.rglob("*") if p.is_file()
                   and p.suffix != ".db" and "-journal" not in p.name)
    app = create_app(data, profil="atelier")
    r = app.test_client().get("/api/v2/referentiel/2025_N11b/vue-ensemble/rendu-tex")
    assert r.status_code == 200 and "Vue d'ensemble du référentiel" in r.get_data(as_text=True)
    assert app.test_client().get("/api/v2/referentiel/inconnu/vue-ensemble/rendu-tex"
                                 ).status_code == 404
    apres = sorted(p.relative_to(data) for p in data.rglob("*") if p.is_file()
                   and p.suffix != ".db" and "-journal" not in p.name)
    assert [p for p in apres if "referentiels" in str(p)] == \
        [p for p in avant if "referentiels" in str(p)]


# ── V2, V3 Structure et séances ──────────────────────────────────────────────

def test_partie_somme_des_seances_cours_compris_et_totaux(base4e_imp):
    c = _conn(base4e_imp)
    st = ve.structure(c, "2027_N11")
    assert st["source"] == "atelier"
    a1 = next(s for d in st["domaines"] for s in d["sequences"] if s["code"] == "A1")
    p1 = a1["parties"][0]
    assert [(o["code"], o["seances"], o["cours"]) for o in p1["objectifs"]] == \
        [("01", 1.0, True), ("02", 2.0, False), ("03", 1.0, False)]
    assert (p1["seances"], p1["semaines"], p1["multiple"]) == (4.0, 1, False)
    assert a1["nb_objectifs"] == 2 and st["seances"] == 4.0 and st["semaines"] == 1
    assert st["parties_non_multiples"] == 1
    tex = ve.generer_vue_ensemble(c, "2027_N11")
    assert r"\textbf{1\,\textbf{*}}" in tex          # 4 séances : pas un multiple de 3
    assert "Domaine A" in tex and r"\colorlet{themeAVif}{red!85!black}" in tex


def test_externe_le_champ_de_duree_de_partie_ne_double_pas_les_seances(base4e_imp):
    """Instantané d'un externe : `nb_seances_R_AE` = somme des objectifs (v0.51.4)."""
    c = _conn(base4e_imp)
    _ins(c, "referentiel_niveaux", id="X2026_N11", niveau="N11", version="X2026",
         etat="utilise", source="externe", type_ref="principal", annee="2026-2027")
    _ins(c, "referentiel_sequences", referentiel_id="X2026_N11", code="S01", numero=1,
         nom="Nombres", theme_code=None)
    _ins(c, "referentiel_parties", referentiel_id="X2026_N11", seq_code="S01", numero=1,
         nb_seances_R_AE=6)
    for code, n in (("02", 4), ("03", 2)):
        _ins(c, "referentiel_objectifs", referentiel_id="X2026_N11", seq_code="S01",
             code=code, nom=f"obj {code}", partie_numero=1, nb_seances=n)
    c.commit()
    st = ve.structure(c, "X2026_N11")
    assert (st["seances"], st["semaines"]) == (6.0, 2)


def test_partie_sans_seance_signalee(base4e, tmp_path):
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, _lot(tmp_path), "--apply", "--yes") == 0
    c = _conn(base4e)
    _ins(c, "referentiel_niveaux", id="2027_N11", niveau="N11", version="2027",
         etat="en_cours", source="interne", type_ref="principal", gabarit_documents="sixieme")
    c.commit()
    st = ve.structure(c, "2027_N11")
    assert st["parties_sans_seance"] == 1 and st["seances"] == 0
    assert "sans séance saisie" in ve.generer_vue_ensemble(c, "2027_N11")


# ── S Clés de lot `seances`, `seances_cours` ─────────────────────────────────

def _seances_base(db) -> dict:
    c = _conn(db)
    return {r[0]: r[1] for r in c.execute(
        "SELECT o.code, o.nb_seances FROM objectifs o JOIN sequence_parties p ON "
        "p.id = o.partie_id JOIN sequences_par_niveau s ON s.id = p.sequence_par_niveau_id "
        "WHERE s.niveau='N11' AND s.sequence_code='A1'")}


def test_seances_ecrites_si_presentes_gardees_si_absentes_idempotent(base4e, tmp_path,
                                                                      capsys):
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, _lot(tmp_path, _seances), "--apply", "--yes") == 0
    assert _seances_base(base4e) == {"01": 1.0, "02": 2.0, "03": 1.0}
    # Laurent corrige une valeur dans l'atelier ; un lot SANS la clé la garde.
    c = sqlite3.connect(base4e)
    c.execute("UPDATE objectifs SET nb_seances=3 WHERE code='02' AND nom LIKE 'Multiplier%'")
    c.commit()
    c.close()
    assert _importer(base4e, _lot(tmp_path), "--apply", "--yes") == 0
    assert _seances_base(base4e)["02"] == 3.0
    # Avec la clé : le lot fait foi ; relance : rien ne change.
    capsys.readouterr()
    assert _importer(base4e, _lot(tmp_path, _seances)) == 0
    assert "A1-02 : 3 → 2 séance(s)" in capsys.readouterr().out
    assert _importer(base4e, _lot(tmp_path, _seances), "--apply", "--yes") == 0
    capsys.readouterr()
    assert _importer(base4e, _lot(tmp_path, _seances)) == 0
    assert "0 objectif(s) dont les séances changent" in capsys.readouterr().out


def test_seances_invalides_signalees_et_ignorees(base4e, tmp_path, capsys):
    assert _archiver(base4e, "--apply", "--yes") == 0

    def faux(lot):
        lot["objectifs"][0]["seances"] = "beaucoup"
    capsys.readouterr()
    assert _importer(base4e, _lot(tmp_path, faux)) == 0
    assert "A1-02 : séances 'beaucoup' invalides" in capsys.readouterr().out


# ── E Encarts ────────────────────────────────────────────────────────────────

def test_controle_refuse_ce_qui_ne_peut_pas_s_imprimer_et_avertit_sans_bloquer():
    ok, err, av = enc.controler({"type": "savoir", "texte": "x", "source": "s"}, True)
    assert not err and not av and ok["position"] == "fin_objectif"
    for src, attendu in (
            ({"type": "anecdote", "texte": "x"}, "type 'anecdote' inconnu"),
            ({"type": "savoir", "texte": ""}, "texte vide"),
            ({"type": "savoir", "texte": "x", "position": "fin_partie"}, "position"),
            ({"type": "savoir", "texte": "x", "position": "apres_exercice"}, "exercice"),
            ({"type": "savoir", "texte": "x", "solution": "y"}, "solution réservée"),
            ({"type": "savoir", "texte": "\\begin{seqEncartSix}"}, "environnement"),
            ({"type": "savoir", "texte": "\\seqInventee{x}"}, "macro(s) inconnue(s)"),
            ({"type": "savoir", "texte": "x", "largeur": "tiers"}, "largeur")):
        _, err, _ = enc.controler(src, True)
        assert any(attendu in e for e in err), (src, err)
    _, err, av = enc.controler({"type": "defi", "texte": "x" * 600}, True)
    assert not err and any("sans solution" in a for a in av) and any("long" in a for a in av)
    assert enc.normaliser_exercice("f3") == "F03" and enc.normaliser_exercice("Z1") == ""


def _encarts_base(db) -> list:
    c = _conn(db)
    return [(r["partie_numero"], r["objectif_code"], r["position"], r["exercice"], r["type"],
             r["titre"]) for r in enc.encarts_de_sequence(c, "N11", "A1")]


def test_import_encarts_le_lot_fait_foi_idempotent_sans_cle_rien_ne_bouge(base4e_imp,
                                                                          tmp_path, capsys):
    assert _encarts_base(base4e_imp) == [
        (1, "02", "apres_exercice", "F01", "savoir", "Signes"),
        (1, "02", "fin_objectif", "", "defi", "Énigme"),
        (1, "03", "apres_activite", "", "histoire", "Brahmagupta"),
        (1, "", "fin_partie", "", "vraievie", "Températures"),
        (1, "", "fin_partie", "", "savoir", "Mer Morte")]
    capsys.readouterr()
    assert _importer(base4e_imp, _lot(tmp_path, lambda l: (_seances(l), _encarts(l)))) == 0
    assert "A1 : créés 0, mis à jour 0, inchangés 5, retirés 0" in capsys.readouterr().out
    # Lot sans clé « encarts » : rien n'est retiré.
    assert _importer(base4e_imp, _lot(tmp_path), "--apply", "--yes") == 0
    assert len(_encarts_base(base4e_imp)) == 5

    # Le lot retire un encart et en modifie un : retrait journalisé.
    def moins(lot):
        _encarts(lot)
        lot["encarts"] = lot["encarts"][:1]
        lot["encarts"][0]["texte"] = "Il fait $-5$\\,°C."
    assert _importer(base4e_imp, _lot(tmp_path, moins), "--apply", "--yes") == 0
    assert len(_encarts_base(base4e_imp)) == 4
    journal = max((base4e_imp.parent / "sauvegardes").glob("journal_import_lot6e_*.json"),
                  key=lambda f: f.stat().st_mtime_ns)
    dernier = json.loads(journal.read_text(encoding="utf-8"))
    assert [r["ligne"]["titre"] for r in dernier.get("retraits", [])
            if r.get("quoi") == "encart"] == ["Mer Morte"]


def test_import_encart_refuse_si_l_exercice_n_existe_pas(base4e, tmp_path, capsys):
    assert _archiver(base4e, "--apply", "--yes") == 0

    def faux(lot):
        lot["objectifs"][0]["encarts"] = [{"type": "savoir", "texte": "x",
                                           "position": "apres_exercice", "exercice": "F09"}]
    capsys.readouterr()
    assert _importer(base4e, _lot(tmp_path, faux), "--apply", "--yes") == 0
    assert "exercice F09 absent de N11/A1" in capsys.readouterr().out
    assert _encarts_base(base4e) == []


def _livret(db, version="eleve", seq="A1"):
    """Corps du livret (sans préambule : la base d'essai n'a pas le paquet importé)."""
    from services import livret_sequence_6e as l6
    return "\n".join(l6.corps_livret(l6.lire_sequence_6e(_conn(db), "N11", seq),
                                     l6.normaliser_options({"version": version})))


def test_livret_place_chaque_encart_a_sa_place(base4e_imp):
    tex = _livret(base4e_imp)
    i_f01 = tex.index("\\end{seqExoSix}")                       # F01 : premier exercice
    i_remed = tex.index("\\begin{seqExoSix}[R]", i_f01)           # sa remédiation le suit
    i_signes = tex.index("{savoir}{Signes}")
    i_f02 = tex.index("\\begin{seqExoSix}[O]", i_f01)
    assert i_f01 < i_remed < i_signes < i_f02
    i_defi = tex.index("{defi}{Énigme}")
    i_band03 = tex.index("\\seqBandeauCapacite{A1-03}")
    assert i_defi < i_band03 < tex.index("{histoire}{Brahmagupta}")
    # Fin de partie : paire de demi-largeur côte à côte, avant la carte mentale.
    i_paire = tex.index("[demi]{vraievie}{Températures}")
    assert tex[i_paire:].index("\\hfill\\begin{seqEncartSix}[demi]{savoir}{Mer Morte}") < 400
    assert i_paire < tex.index("seqCarteMentaleSix")
    # Défi : la solution est dans le .tex, le module ne l'imprime qu'au corrigé.
    assert "\\seqSolutionDefiSix{$-2$ et $3$.}" in tex
    assert "\\seqSolutionDefiSix{$-2$ et $3$.}" in _livret(base4e_imp, "corrigee")


def test_livret_sans_encart_meme_tex_et_plan_de_travail_memes_numeros(base4e_imp):
    from services.livret_sequence_6e import (lire_sequence_6e, normaliser_options,
                                             numeros_livret)
    c = _conn(base4e_imp)
    avec = numeros_livret(lire_sequence_6e(c, "N11", "A1"), normaliser_options({}))
    tex_avec = _livret(base4e_imp)
    c.execute("DELETE FROM encarts")
    c.commit()
    sans = numeros_livret(lire_sequence_6e(c, "N11", "A1"), normaliser_options({}))
    assert (avec.exercices, avec.activites) == (sans.exercices, sans.activites)
    tex_sans = _livret(base4e_imp)
    assert "seqEncartSix" not in tex_sans and tex_sans != tex_avec
    c.execute("DROP TABLE encarts")                     # base d'avant v0.59.2
    c.commit()
    assert _livret(base4e_imp) == tex_sans


def test_encarts_perimeent_le_livret_et_les_corriges_seulement():
    from services import peremption_atomes as pa
    assert "encarts" in pa.tables_atomes_pertinentes("livret_sequence_6e")
    assert "encarts" in pa.tables_atomes_pertinentes("corriges_6e")
    for t in ("evaluation_6e", "plans_travail_6e", "fiches_cours_6e", "mer_tests_courts_6e"):
        assert "encarts" not in pa.tables_atomes_pertinentes(t)


def test_route_encarts_en_lecture_seule(base4e_imp):
    from app import create_app
    app = create_app(base4e_imp.parent, profil="atelier")
    r = app.test_client().get("/api/v2/livret-sequence/N11/A1/encarts")
    assert r.status_code == 200
    d = r.get_json()
    assert len(d["encarts"]) == 5 and d["types"]["defi"] == "Défi"


def test_module_v0_15_definit_les_encarts_et_l_appli_les_connait():
    from services import style6e
    # v0.60.3 : v0.16 (filets du suivi) garde les encarts ; la version citée suit le .dtx.
    assert tuple(int(x) for x in style6e.VERSION[1:].split(".")) >= (0, 15)
    assert "seqEncartSix" in style6e.ENVIRONNEMENTS
    assert {"seqSolutionDefiSix", "seqPictoEncartSix"} <= set(style6e.MACROS)
    for f in (DTX, STY):
        src = f.read_text(encoding="utf-8")
        assert style6e.VERSION + " seqenseigne" in src
        assert "\\NewDocumentEnvironment{seqEncartSix}{O{pleine} m m}" in src
        for t in enc.TYPES:
            assert f"\\seq@encart@nom@{t}" in src
    assert "\\changes{v0.15}" in DTX.read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex absent")
def test_compilation_des_quatre_encarts_et_type_inconnu_refuse(tmp_path):
    def compiler(corps):
        (tmp_path / "t.tex").write_text(
            "\\documentclass{article}\\usepackage[utf8]{inputenc}\\usepackage[T1]{fontenc}"
            "\\usepackage{seqenseigne-style6e}\\begin{document}" + corps + "\\end{document}",
            encoding="utf-8")
        env = dict(os.environ, TEXINPUTS=f"{APPLI / 'paquet'}//:")
        return subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                               "t.tex"], cwd=tmp_path, env=env, capture_output=True,
                              timeout=120).returncode
    corps = "".join(enc.latex_encart({"type": t, "titre": "T", "texte": "x",
                                      "solution": "s" if t == "defi" else "",
                                      "largeur": "pleine"}) for t in enc.TYPES)
    assert compiler("\\seqVersionCorrigee " + corps) == 0
    assert compiler(enc.latex_encart({"type": "anecdote", "titre": "", "texte": "x"})) != 0


# ── H Horodatage de l'import ─────────────────────────────────────────────────

def test_import_horodate_en_utc_comme_la_peremption_meme_a_paris(monkeypatch):
    """Constat v0.59.1 : `_maintenant()` écrivait l'heure locale (CET) alors que
    `compile_date` et `CURRENT_TIMESTAMP` sont en UTC : un document compilé
    juste après un import paraissait périmé pendant une heure (deux en été)."""
    if not hasattr(time, "tzset"):
        pytest.skip("tzset indisponible")
    monkeypatch.setenv("TZ", "Europe/Paris")
    time.tzset()
    try:
        ecrit = datetime.strptime(imp._maintenant(), "%Y-%m-%d %H:%M:%S")
        utc = datetime.now(timezone.utc).replace(tzinfo=None)
        assert abs((utc - ecrit).total_seconds()) < 5
        sqlite_utc = sqlite3.connect(":memory:").execute(
            "SELECT CURRENT_TIMESTAMP").fetchone()[0]
        assert imp._maintenant() >= sqlite_utc[:16]          # même référence
    finally:
        monkeypatch.delenv("TZ", raising=False)
        time.tzset()


def test_document_compile_juste_apres_un_import_n_est_pas_perime(base4e_imp, monkeypatch):
    from services.referentiel_documents_compilation import etat_effectif_document
    if hasattr(time, "tzset"):
        monkeypatch.setenv("TZ", "Europe/Paris")
        time.tzset()
    try:
        c = _conn(base4e_imp)
        c.execute("UPDATE exercices SET mtime=? WHERE niveau='N11' AND sequence='A1'",
                  (imp._maintenant(),))                       # import de 19 h (Paris)
        compile_date = c.execute("SELECT CURRENT_TIMESTAMP").fetchone()[0]   # compilé après
        doc = {"id": "d", "referentiel_id": "2027_N11", "type_document": "livret_sequence_6e",
               "compile_ok": 1, "compile_date": compile_date}
        assert etat_effectif_document(c, doc) == "ok"
    finally:
        monkeypatch.delenv("TZ", raising=False)
        if hasattr(time, "tzset"):
            time.tzset()
