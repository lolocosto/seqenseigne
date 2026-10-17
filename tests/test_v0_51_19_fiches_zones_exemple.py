r"""tests/test_v0_51_19_fiches_zones_exemple.py — Zones d'exemple des fiches.

Besoin (Laurent, v0.51.19) : quand une fiche est trop chargée, la seule
boîte « Exemples » finale (qui remplit le bas de la page) n'a plus de
place. Plutôt que couper la fiche en deux (une fiche par objectif, à
garder), chaque zone de texte peut avoir sa propre zone d'exemple de N
lignes, et la fiche peut s'étendre sur plusieurs pages. La boîte finale
devient optionnelle (cochée par défaut = rendu historique inchangé).
"""

from __future__ import annotations

import sqlite3

import pytest

from app import create_app
from services.fiches_resume import (
    EXEMPLE_LIGNES_MAX,
    ZoneExempleInvalide,
    creer_fiche,
    lire_fiche,
    migrer,
    modifier_fiche,
)
from services.latex_rendu_atome import Atome, charger_atome, generer_corps_fiche

FILL = r"\begin{seqBoiteFillContenuFlashcard}\end{seqBoiteFillContenuFlashcard}"


def _fiche(sections, fin_page=True):
    return Atome(id="f", type_atome="fiche", niveau="N11", sequence="S02",
                 fichier="", titre="Puissances", sections=sections,
                 exemple_fin_page=fin_page)


# ── Rendu LaTeX ──────────────────────────────────────────────────────────────

class TestRendu:

    def test_sans_zone_rendu_historique_inchange(self):
        """Une fiche sans zone d'exemple et avec la case par défaut sort
        exactement comme avant v0.51.19 (non-régression des fiches
        existantes et de tous les livrets déjà produits)."""
        tex = generer_corps_fiche(_fiche([
            {"titre": "Définition", "items": ["Texte A"]},
            {"titre": "Propriété", "items": ["Texte B"]},
        ]))
        assert tex == "\n".join([
            r"\seqTitreSection{Puissances}",
            r"\begin{seqBoiteContenuFlashcard}[titre=Définition]",
            "Texte A",
            r"\end{seqBoiteContenuFlashcard}",
            r"\begin{seqBoiteContenuFlashcard}[titre=Propriété]",
            "Texte B",
            r"\end{seqBoiteContenuFlashcard}",
            FILL,
        ])

    def test_zone_d_exemple_sous_la_bonne_zone(self):
        tex = generer_corps_fiche(_fiche([
            {"titre": "Définition", "items": ["Texte A"], "exemple_lignes": 8},
            {"titre": "Propriété", "items": ["Texte B"]},
        ]))
        i_def = tex.index("[titre=Définition]")
        i_ex = tex.index(r"\begin{seqBoiteContenuFlashcard}[titre=Exemples]")
        i_prop = tex.index("[titre=Propriété]")
        assert i_def < i_ex < i_prop
        assert r"\vspace*{8\baselineskip}" in tex[i_ex:i_prop]
        assert tex.count("[titre=Exemples]") == 1

    def test_case_fin_de_page_decochee(self):
        """Sans boîte finale, un \\newpage garantit que la fiche suivante
        (livret) commence sur une nouvelle page, comme le faisait la boîte
        (qui contient son propre \\newpage)."""
        tex = generer_corps_fiche(_fiche(
            [{"titre": "Définition", "items": ["A"], "exemple_lignes": 5}],
            fin_page=False))
        assert FILL not in tex
        assert tex.rstrip().endswith(r"\newpage")

    def test_zones_et_boite_finale_cumulables(self):
        tex = generer_corps_fiche(_fiche(
            [{"titre": "Définition", "items": ["A"], "exemple_lignes": 5}]))
        assert tex.rstrip().endswith(FILL)
        assert "[titre=Exemples]" in tex


# ── Service (base complète) ──────────────────────────────────────────────────

@pytest.fixture
def app_seq(data_dir):
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as conn:
        conn.executescript("""
            INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
                VALUES ('sn_1', 'N11', 'S02', '');
            INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                VALUES ('pt_1', 'sn_1', 1);
            INSERT INTO objectifs (id, partie_id, code, nom, methode_id)
                VALUES ('ob_02', 'pt_1', '02', 'Utiliser les puissances', NULL);
        """)
        conn.commit()
    yield app


class TestService:

    def test_aller_retour_et_rendu(self, app_seq):
        with app_seq.json_store._conn() as conn:
            f = creer_fiche(conn, objectif_id="ob_02", titre="Puissances",
                            sections=[
                                {"titre": "Définition", "items": ["A"],
                                 "exemple_lignes": 10},
                                {"titre": "Propriété", "items": ["B"]},
                            ], exemple_fin_page=False)
            lu = lire_fiche(conn, f["id"])
            assert [s["exemple_lignes"] for s in lu["sections"]] == [10, None]
            assert lu["exemple_fin_page"] is False
            # Le rendu (atelier, livret de séquence, livret de fiches)
            # passe par charger_atome : il doit voir les mêmes réglages.
            atome = charger_atome(conn, "fiche", f["id"])
            assert atome.exemple_fin_page is False
            assert atome.sections[0]["exemple_lignes"] == 10
            assert "exemple_lignes" not in atome.sections[1]

    def test_par_defaut_case_fin_de_page_cochee(self, app_seq):
        with app_seq.json_store._conn() as conn:
            f = creer_fiche(conn, objectif_id="ob_02", titre="T")
            assert lire_fiche(conn, f["id"])["exemple_fin_page"] is True

    def test_modification_partielle(self, app_seq):
        with app_seq.json_store._conn() as conn:
            f = creer_fiche(conn, objectif_id="ob_02", titre="T",
                            sections=[{"titre": "D", "items": ["A"],
                                       "exemple_lignes": 4}])
            # Changer seulement la case : les zones restent.
            lu = modifier_fiche(conn, f["id"], exemple_fin_page=False)
            assert lu["exemple_fin_page"] is False
            assert lu["sections"][0]["exemple_lignes"] == 4
            # Retirer la zone (0 = décoché).
            lu = modifier_fiche(conn, f["id"], sections=[
                {"titre": "D", "items": ["A"], "exemple_lignes": 0}])
            assert lu["sections"][0]["exemple_lignes"] is None

    @pytest.mark.parametrize("valeur", [EXEMPLE_LIGNES_MAX + 1, -2, "abc", 2.5, True])
    def test_valeur_invalide_refusee_sans_rien_ecrire(self, app_seq, valeur):
        """La validation a lieu AVANT le remplacement des sections : une
        valeur invalide ne doit pas effacer les zones existantes."""
        with app_seq.json_store._conn() as conn:
            f = creer_fiche(conn, objectif_id="ob_02", titre="T",
                            sections=[{"titre": "D", "items": ["A"]}])
            with pytest.raises(ZoneExempleInvalide):
                modifier_fiche(conn, f["id"], sections=[
                    {"titre": "D", "items": ["nouveau"], "exemple_lignes": valeur}])
            assert lire_fiche(conn, f["id"])["sections"][0]["items"] == ["A"]


class TestRoute:

    def test_patch_400_hors_bornes_et_patch_case(self, app_seq):
        client = app_seq.test_client()
        r = client.post("/api/fiches-resume", json={
            "objectif_id": "ob_02", "titre": "T",
            "sections": [{"titre": "D", "items": ["A"]}]})
        assert r.status_code == 201
        fid = r.get_json()["id"]
        r = client.patch(f"/api/fiches-resume/{fid}", json={
            "sections": [{"titre": "D", "items": ["A"], "exemple_lignes": 99}]})
        assert r.status_code == 400
        assert r.get_json()["code"] == "zone_exemple_invalide"
        r = client.patch(f"/api/fiches-resume/{fid}", json={
            "exemple_fin_page": False,
            "sections": [{"titre": "D", "items": ["A"], "exemple_lignes": 7}]})
        assert r.status_code == 200
        corps = r.get_json()
        assert corps["exemple_fin_page"] is False
        assert corps["sections"][0]["exemple_lignes"] == 7


# ── Migration d'une base existante ───────────────────────────────────────────

class TestMigration:

    def test_base_ancienne_colonnes_ajoutees_et_fiches_inchangees(self):
        """Une base d'avant v0.51.19 : les fiches existantes gardent leur
        boîte de fin de page (défaut 1) et n'ont aucune zone d'exemple."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE atome_sections (id TEXT PRIMARY KEY, entite_type TEXT,
                entite_id TEXT, titre TEXT, ordre INTEGER);
            CREATE TABLE fiches_resume (id TEXT PRIMARY KEY, titre TEXT,
                objectif_id TEXT, num_fiche INTEGER, niveau TEXT, sequence TEXT,
                fichier TEXT, etat_code TEXT);
            INSERT INTO fiches_resume VALUES ('f1','T',NULL,1,'N11','S02','','en_cours');
            INSERT INTO atome_sections VALUES ('s1','fiche_resume','f1','D',0);
        """)
        migrer(conn)
        migrer(conn)  # idempotent
        assert conn.execute(
            "SELECT exemple_fin_page FROM fiches_resume WHERE id='f1'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT exemple_lignes FROM atome_sections WHERE id='s1'"
        ).fetchone()[0] is None
