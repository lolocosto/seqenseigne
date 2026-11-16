"""tests/test_v0_58_1_couleur_atomes.py — v0.58.1

Correctif : après la migration des codes (v0.58.0), les atomes compilés
(exercices, méthodes, notions, fiches) sortaient en gris. `resoudre_theme`
cherchait la couleur uniquement dans les instantanés `referentiel_*`, où les
séquences gardent leurs codes S… (référentiels figés) ou n'ont pas de ligne
(référentiels en conception) : une séquence vivante A1 n'y est jamais.

Invariants protégés :
  - un atome est un contenu vivant : sa couleur (et les getters de séquence /
    de thème résolus dans son texte) vient des tables vivantes, comme les
    livrets de séquence et les cartes d'automatisme ;
  - repli sur les instantanés seulement si la séquence n'est pas dans les
    tables vivantes (S… d'un référentiel figé) ; « gris » en dernier recours.

Base : celle des tests de l'outil de migration v0.58.0 (appli atelier neuve,
vrais CSV de cycle, cycle 3 de la v0.52, un référentiel interne figé N11_v2025
en S…, un référentiel externe X2026_N09 dont la S01 est « Géométrie »),
complétée d'une fiche, puis migrée.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from outils import migrer_themes_codes_2027 as mig
from services.latex_rendu_atome import (
    generer_tex_par_type,
    resoudre_macros_csv,
    resoudre_theme,
)
from tests.test_v0_52_0_import_lot6e import base as base_v052  # noqa: F401
from tests.test_v0_58_0_migration_themes_codes import (  # noqa: F401
    RECL,
    _ins,
    _migrer,
    base,
)


@pytest.fixture(autouse=True)
def _table_reduite(tmp_path, monkeypatch):
    p = tmp_path / "reclassement_test.json"
    p.write_text(json.dumps(RECL), encoding="utf-8")
    monkeypatch.setattr(mig, "RECLASSEMENT", p)


@pytest.fixture
def migree(base):
    c = sqlite3.connect(base)
    _ins(c, "fiches_resume", id="fi_s03", titre="Fiche S03", niveau="N10", sequence="S03",
         num_fiche=1, etat_code="en_cours")
    _ins(c, "fiches_resume", id="fi_n09", titre="Fiche 6e", niveau="N09", sequence="S01",
         num_fiche=1, etat_code="en_cours")
    c.commit()
    c.close()
    _migrer(base)
    c = sqlite3.connect(base)
    c.row_factory = sqlite3.Row
    # Tables créées par l'import du paquet (vides ici : préambule minimal).
    c.executescript("""
        CREATE TABLE IF NOT EXISTS paquet_definitions (
            nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
            corps TEXT, corps_fin TEXT, texte_complet TEXT,
            fichier_source TEXT, ligne_debut INTEGER,
            macros_appelees TEXT, environnements_utilises TEXT,
            statut_rendu_atome TEXT, contenu_atome TEXT);
        CREATE TABLE IF NOT EXISTS paquet_requirepackage (
            fichier_source TEXT NOT NULL, ordre INTEGER NOT NULL, nom TEXT NOT NULL,
            options TEXT NOT NULL DEFAULT '', PRIMARY KEY (fichier_source, ordre));
    """)
    yield c
    c.close()


def _seq(c, table, ident):
    r = c.execute(f"SELECT niveau, sequence FROM {table} WHERE id=?", (ident,)).fetchone()
    return r["niveau"], r["sequence"]


def _couleur_tex(c, type_atome, ident):
    tex = generer_tex_par_type(c, type_atome, ident)
    ligne = next(l for l in tex.splitlines() if l.startswith("\\seqSetColorsTheme"))
    return ligne[len("\\seqSetColorsTheme{"):-1]


# ── Un atome de chaque type en code de thème a la couleur de son thème ───────

@pytest.mark.parametrize("type_atome, table, ident, code, couleur", [
    ("exercice", "exercices",     "ex_s03_f1",  "A1", "nombres"),     # N10/S03 → A1
    ("methode",  "methodes",      "me_s02_1",   "A2", "nombres"),     # N10/S02 → A2 (reclassée)
    ("notion",   "notions",       "no_s10_1",   "B1", "geometrie"),   # N10/S10 → B1 (reclassée)
    ("fiche",    "fiches_resume", "fi_s03",     "A1", "nombres"),
])
def test_atome_migre_en_code_de_theme_a_la_couleur_de_son_theme_et_non_gris(
        migree, type_atome, table, ident, code, couleur):
    assert _seq(migree, table, ident)[1] == code
    assert _couleur_tex(migree, type_atome, ident) == couleur


def test_atome_de_6e_rendu_classique_a_la_couleur_de_son_theme_vivant(migree):
    """6e : les exercices F/A/E et les fiches au gabarit « sixieme » ont la
    mise en forme de l'équipe, sans couleur de thème (inchangé) ; les autres
    (archives X…, séries hors 6e) passent par le rendu classique et prennent
    la couleur du thème vivant du cycle 3."""
    assert _seq(migree, "exercices", "ex_n09_s01") == ("N09", "A1")
    assert "\\seqSetColorsTheme" not in generer_tex_par_type(migree, "exercice", "ex_n09_s01")
    assert resoudre_theme(migree, "N09", "A1") == "nombres"
    assert resoudre_theme(migree, "N09", "B1") == "geometrie"
    assert resoudre_theme(migree, "N09", "X13") == "geometrie"      # archive du cycle 3
    _ins(migree, "exercices", id="ex_n09_x13", serie="fondamental", titre="t", enonce="e",
         niveau="N09", sequence="X13", num=1, serie_code="F", fichier="", variables="",
         etat_code="en_cours")
    assert _couleur_tex(migree, "exercice", "ex_n09_x13") == "geometrie"


def test_atome_de_6e_suit_le_theme_vivant_et_non_un_referentiel_externe_au_meme_code(migree):
    """Avant v0.58.1, un atome de 6e prenait la couleur de la séquence de même
    code d'un référentiel externe (S01 « Géométrie » de X2026_N09)."""
    migree.execute("INSERT INTO referentiel_sequences (referentiel_id, code, numero, nom, "
                   "theme_code) VALUES ('X2026_N09', 'A1', 9, 'Externe', 'A')")
    assert resoudre_theme(migree, "N09", "A1") == "nombres"


def test_couleur_d_un_atome_identique_a_celle_des_cartes_et_des_livrets(migree):
    from services.render_carte_centralise import resoudre_code_couleur
    from services.v2_lecture import _charger_sequence_par_niveau
    for niv, seq in migree.execute("SELECT niveau, sequence_code FROM sequences_par_niveau"
                                   ).fetchall():
        sn = _charger_sequence_par_niveau(migree, niv, seq)
        attendu = sn["theme_code_couleur"] or "gris"
        assert resoudre_theme(migree, niv, seq) == attendu, (niv, seq)
        if sn["theme_code_couleur"]:
            assert resoudre_code_couleur(migree, niv, seq) == attendu, (niv, seq)


# ── Repli sur les référentiels figés, puis gris ─────────────────────────────

def test_sequence_en_S_d_un_referentiel_fige_garde_son_rendu_par_l_instantane(migree):
    """N11/S03 n'existe plus dans les tables vivantes (devenue A1) : le
    référentiel figé N11_v2025 donne toujours sa couleur, son nom, son numéro."""
    assert not migree.execute("SELECT 1 FROM sequences_du_cycle WHERE cycle_code='C04' "
                              "AND code='S03'").fetchone()
    assert resoudre_theme(migree, "N11", "S03") == "nombres"
    texte = r"\seqSequenceGetNom{} \seqSequenceGetNumero{} \seqSequenceGetTheme{}"
    assert resoudre_macros_csv(migree, texte, "N11", "S03") == "Calcul numérique 3 A"


def test_instantane_du_referentiel_fige_non_modifie_par_le_rendu(migree):
    avant = migree.execute("SELECT * FROM referentiel_sequences ORDER BY referentiel_id, code"
                           ).fetchall()
    generer_tex_par_type(migree, "exercice", "ex_s03_f1")
    resoudre_theme(migree, "N11", "S03")
    assert migree.execute("SELECT * FROM referentiel_sequences ORDER BY referentiel_id, code"
                          ).fetchall() == avant
    assert {r[0] for r in migree.execute("SELECT code FROM referentiel_sequences WHERE "
                                         "referentiel_id='N11_v2025'")} == {"S03"}


def test_code_inconnu_ou_niveau_inconnu_donne_gris(migree):
    assert resoudre_theme(migree, "N10", "Z9") == "gris"
    assert resoudre_theme(migree, "N99", "A1") == "gris"
    assert resoudre_theme(migree, "N10", "") == "gris"


def test_theme_vivant_sans_couleur_valide_se_replie_sur_les_referentiels_puis_gris(migree):
    migree.execute("UPDATE themes SET code_couleur='' WHERE cycle_code='C04' AND code='A'")
    assert resoudre_theme(migree, "N10", "A1") == "gris"          # aucun instantané en A1
    migree.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
                   "VALUES ('T_N10', 'N10', '2099', 'utilise')")
    migree.execute("INSERT INTO referentiel_themes (referentiel_id, code, nom, couleur) "
                   "VALUES ('T_N10', 'A', 'Nombres', 'nombres')")
    migree.execute("INSERT INTO referentiel_sequences (referentiel_id, code, numero, nom, "
                   "theme_code) VALUES ('T_N10', 'A1', 1, 'Calcul', 'A')")
    assert resoudre_theme(migree, "N10", "A1") == "nombres"
    migree.execute("UPDATE themes SET code_couleur='violet' WHERE cycle_code='C04' AND code='B'")
    migree.execute("DELETE FROM referentiel_sequences WHERE referentiel_id='T_N10'")
    assert resoudre_theme(migree, "N10", "B1") == "gris"


# ── Getters de séquence et de thème dans le texte d'un atome ────────────────

def test_getters_de_sequence_lisent_les_tables_vivantes_pour_un_code_de_theme(migree):
    nom = migree.execute("SELECT nom FROM sequences_du_cycle WHERE cycle_code='C04' "
                         "AND code='A1'").fetchone()[0]
    theme = migree.execute("SELECT nom FROM themes WHERE cycle_code='C04' AND code='A'"
                           ).fetchone()[0]
    texte = (r"\seqSequenceGetNom{} | \seqSequenceGetNumero{} | \seqSequenceGetTheme{} | "
             r"\seqThemeGetNom{A}")
    assert resoudre_macros_csv(migree, texte, "N10", "A1") == f"{nom} | A1 | A | {theme}"


def test_numero_d_une_sequence_en_code_de_theme_affiche_le_code_comme_le_titre_des_livrets(migree):
    """Règle L1 (v0.57.0) : « Séquence A1 », jamais « Séquence 11 »."""
    assert resoudre_macros_csv(migree, r"\seqSequenceGetNumero{B1}", "N11", "A1") == "B1"


def test_getter_de_sequence_inconnue_garde_son_placeholder(migree):
    assert resoudre_macros_csv(migree, r"\seqSequenceGetNom{Z9}", "N10", "A1") == "[SEQ-Z9]"
    assert resoudre_macros_csv(migree, r"\seqThemeGetNom{Q}", "N10", "A1") == "[TH-Q]"
