"""
tests/test_resoudre_macros.py — Tests du résolveur de macros nommantes.

Couverture :
  - Résolution des 17 macros individuellement (chemin nominal)
  - Stratégie de fallback `[à saisir]` quand une référence est introuvable
  - Accumulation des incidents (macro + raison)
  - Garde-fou critique : les champs de saisie LaTeX (corps, exemples,
    remarques, énoncés, corrigés) ne sont pas touchés
  - Chargement du contexte depuis les CSV (via un CsvStore fake)
  - Symétrie C03 / C04
  - Intégration avec scanner_vers_bdd
"""

from __future__ import annotations

import pytest

# v0.7 — Tests adaptés au modèle universel à 2 niveaux
# (atome_sections + atome_section_items remplacent items_texte).

from services.resoudre_macros import (
    Contexte,
    FALLBACK,
    LIBELLES_MAITRISE,
    PARAM_NIVEAUX_FALLBACK,
    construire_contexte_global,
    contient_macro_nommante,
    resoudre,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fake CsvStore — imite la vraie forme retournée par persistence/csv_store.py
# ─────────────────────────────────────────────────────────────────────────────

class _CsvStoreFake:
    """
    Reproduit les méthodes de `CsvStore` utilisées par le résolveur,
    avec un jeu minimaliste mais représentatif pour C03 + C04.
    """
    def lire_param_niveaux(self):
        return {
            "N09": {"code": "N09", "code_cycle": "C03",
                    "annee_dans_cycle": "anneetrois",
                    "nom_court": "6ème", "nom_long": "sixième"},
            "N10": {"code": "N10", "code_cycle": "C04",
                    "annee_dans_cycle": "anneeun",
                    "nom_court": "5ème", "nom_long": "cinquième"},
            "N11": {"code": "N11", "code_cycle": "C04",
                    "annee_dans_cycle": "anneedeux",
                    "nom_court": "4ème", "nom_long": "quatrième"},
        }
    def lire_c04_sequences(self):
        return {
            "S01": {"code": "S01", "numero": 1, "nom": "Séq A", "theme": "A"},
            "S02": {"code": "S02", "numero": 2, "nom": "Séq B", "theme": "D"},
            "S03": {"code": "S03", "numero": 3, "nom": "Séq C", "theme": "A"},
        }
    def lire_c04_themes(self):
        return {
            "A": {"code": "A", "nom": "Nombres",   "code_couleur": "nombres",
                  "description": "desc C04/A"},
            "D": {"code": "D", "nom": "Géométrie", "code_couleur": "geometrie",
                  "description": ""},
        }
    def lire_c03_sequences(self):
        return {
            "S01": {"code": "S01", "numero": 1, "nom": "Nombres entiers", "theme": "A"},
        }
    def lire_c03_themes(self):
        return {
            "A": {"code": "A", "nom": "Nombres et Calculs",
                  "code_couleur": "nombres", "description": "desc C03/A"},
        }
    def lire_c04_connaissances(self):
        return {
            ("N11", "S01", "01"): "Écriture fractionnaire",
            ("N11", "S01", "02"): "Écriture décimale",
            ("N10", "S01", "01"): "Proportion.",
        }
    def lire_c03_connaissances(self):
        return {
            ("N09", "S01", "01"): "Nombres relatifs",
        }
    def lire_c04_objectifs(self):
        return {
            ("N11", "S01", "02"): {
                "nom": "Utiliser la notation scientifique",
                "fin_cycle": "O",
                "maitrise_tb": "Critère E",
                "maitrise_s":  "Critère A",
                "maitrise_f":  "Critère F",
            },
            ("N11", "S01", "03"): {
                "nom": "Autre méthode",
                "fin_cycle": "N",  # valeur valide, pas à confondre avec absent
                "maitrise_tb": "",  # explicitement vide = pas une erreur
                "maitrise_s":  "",
                "maitrise_f":  "",
            },
        }
    def lire_c03_objectifs(self):
        return {
            ("N09", "S01", "02"): {
                "nom": "Objectif 6ème",
                "fin_cycle": "N",
                "maitrise_tb": "", "maitrise_s": "", "maitrise_f": "",
            },
        }


def _ctx_c04():
    """Contexte peuplé (C04) pour les tests."""
    ctx = construire_contexte_global(_CsvStoreFake())
    ctx.niveau_courant = "N11"
    ctx.sequence_courante = "S01"
    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# Tests par famille de macros
# ─────────────────────────────────────────────────────────────────────────────

class TestMacrosNiveau:

    def test_nomcourt(self):
        out, inc = resoudre("\\seqNiveauGetNomCourt{N11}", _ctx_c04())
        assert out == "4ème"
        assert inc == []

    def test_nomlong(self):
        out, _ = resoudre("\\seqNiveauGetNomLong{N10}", _ctx_c04())
        assert out == "cinquième"

    def test_codecycle(self):
        out, _ = resoudre("\\seqNiveauGetCodeCycle{N11}", _ctx_c04())
        assert out == "C04"

    def test_niveau_inconnu_fallback(self):
        out, inc = resoudre("\\seqNiveauGetNomCourt{N99}", _ctx_c04())
        assert out == FALLBACK
        assert len(inc) == 1
        assert "N99" in inc[0]["raison"]

    def test_niveau_c03_fallback_si_absent_du_csv(self):
        """
        N07 n'est pas dans le fake CsvStore. Il doit quand même être
        résolu grâce à PARAM_NIVEAUX_FALLBACK (table en dur).
        """
        out, inc = resoudre("\\seqNiveauGetNomCourt{N07}", _ctx_c04())
        assert out == "CM1"
        assert inc == []


class TestMacrosTheme:

    def test_nom(self):
        out, _ = resoudre("\\seqThemeGetNom{C04}{A}", _ctx_c04())
        assert out == "Nombres"

    def test_codecouleur(self):
        out, _ = resoudre("\\seqThemeGetCodeCouleur{C04}{D}", _ctx_c04())
        assert out == "geometrie"

    def test_description_presente(self):
        out, inc = resoudre("\\seqThemeGetDescription{C04}{A}", _ctx_c04())
        assert out == "desc C04/A"
        assert inc == []

    def test_description_vide_nest_pas_une_erreur(self):
        """
        Un thème existe mais sans description : c'est valide, on renvoie
        la chaîne vide sans incident.
        """
        out, inc = resoudre("\\seqThemeGetDescription{C04}{D}", _ctx_c04())
        assert out == ""
        assert inc == []

    def test_theme_inconnu(self):
        out, inc = resoudre("\\seqThemeGetNom{C04}{Z}", _ctx_c04())
        assert out == FALLBACK
        assert inc[0]["macro"] == "\\seqThemeGetNom{C04}{Z}"


class TestMacrosSequence:

    def test_nom_contexte(self):
        ctx = _ctx_c04()
        out, _ = resoudre("Séquence : \\seqSequenceGetNom.", ctx)
        assert out == "Séquence : Séq A."

    def test_nomof_explicite(self):
        out, _ = resoudre("Cf. \\seqSequenceGetNomOf{N11}{S03}.", _ctx_c04())
        assert out == "Cf. Séq C."

    def test_numero(self):
        out, _ = resoudre("num=\\seqSequenceGetNumero", _ctx_c04())
        assert out == "num=1"

    def test_theme_code(self):
        # \seqSequenceGetTheme renvoie le CODE du thème
        out, _ = resoudre("\\seqSequenceGetTheme", _ctx_c04())
        assert out == "A"

    def test_garde_fou_nom_vs_nomof(self):
        """
        Garde-fou : \\seqSequenceGetNom ne doit pas matcher à l'intérieur
        de \\seqSequenceGetNomOf{...}{...}.
        """
        out, _ = resoudre("\\seqSequenceGetNomOf{N11}{S01}", _ctx_c04())
        assert out == "Séq A"

    def test_sequence_courante_absente(self):
        ctx = _ctx_c04()
        ctx.sequence_courante = "S99"
        out, inc = resoudre("\\seqSequenceGetNom", ctx)
        assert out == FALLBACK
        assert len(inc) == 1


class TestMacrosObjectif:

    def test_nom(self):
        out, _ = resoudre("\\seqObjectifGetNom{02}", _ctx_c04())
        assert out == "Utiliser la notation scientifique"

    def test_fincycle_O(self):
        out, _ = resoudre("\\seqObjectifGetFinCycle{02}", _ctx_c04())
        assert out == "O"

    def test_fincycle_N_est_une_valeur_valide(self):
        """
        Cas spécifique : FinCycle="N" est une valeur valide. Le résolveur
        ne doit PAS considérer cette chaîne comme une absence et ne
        doit PAS signaler d'incident.
        """
        out, inc = resoudre("\\seqObjectifGetFinCycle{03}", _ctx_c04())
        assert out == "N"
        assert inc == []

    def test_maitrise_tb(self):
        out, _ = resoudre("\\seqObjectifGetMaitriseTB{02}", _ctx_c04())
        assert out == "Critère E"

    def test_maitrise_vide_nest_pas_incident(self):
        """
        MaitriseTB explicitement vide pour l'objectif 03 : on renvoie
        la chaîne vide sans incident.
        """
        out, inc = resoudre("\\seqObjectifGetMaitriseTB{03}", _ctx_c04())
        assert out == ""
        assert inc == []

    def test_objectif_inconnu(self):
        out, inc = resoudre("\\seqObjectifGetNom{99}", _ctx_c04())
        assert out == FALLBACK
        assert "99" in inc[0]["raison"]
        assert "N11/S01" in inc[0]["raison"]


class TestMacrosConnaissance:

    def test_nom(self):
        out, _ = resoudre("\\seqConnaissanceGetNom{01}", _ctx_c04())
        assert out == "Écriture fractionnaire"

    def test_connaissance_inconnue(self):
        out, inc = resoudre("\\seqConnaissanceGetNom{99}", _ctx_c04())
        assert out == FALLBACK
        assert "99" in inc[0]["raison"]

    def test_plusieurs_connaissances_dans_texte(self):
        out, _ = resoudre(
            "Voir \\seqConnaissanceGetNom{01} et \\seqConnaissanceGetNom{02}.",
            _ctx_c04())
        assert out == "Voir Écriture fractionnaire et Écriture décimale."


class TestMacrosMaitrise:

    def test_tous_codes_connus(self):
        ctx = _ctx_c04()
        for code, libelle in LIBELLES_MAITRISE.items():
            out, inc = resoudre(f"\\seqMaitriseGetNom{{{code}}}", ctx)
            assert out == libelle
            assert inc == []

    def test_code_inconnu(self):
        out, inc = resoudre("\\seqMaitriseGetNom{X}", _ctx_c04())
        assert out == FALLBACK
        assert len(inc) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Résolution multi-macros et hors périmètre
# ─────────────────────────────────────────────────────────────────────────────

class TestMultiMacros:

    def test_plusieurs_macros_dans_meme_texte(self):
        texte = ("\\seqNiveauGetNomCourt{N11} · "
                 "\\seqSequenceGetNom · "
                 "\\seqObjectifGetNom{02}")
        out, inc = resoudre(texte, _ctx_c04())
        assert out == "4ème · Séq A · Utiliser la notation scientifique"
        assert inc == []

    def test_melange_ok_et_ko(self):
        out, inc = resoudre(
            "\\seqObjectifGetNom{02} / \\seqObjectifGetNom{99}",
            _ctx_c04())
        assert out == f"Utiliser la notation scientifique / {FALLBACK}"
        assert len(inc) == 1
        assert inc[0]["macro"] == "\\seqObjectifGetNom{99}"

    def test_texte_sans_macro_inchange(self):
        texte = "Titre simple sans aucune macro"
        out, inc = resoudre(texte, _ctx_c04())
        assert out == texte
        assert inc == []

    def test_texte_vide(self):
        assert resoudre("", _ctx_c04()) == ("", [])

    def test_texte_none(self):
        assert resoudre(None, _ctx_c04()) == ("", [])


class TestHorsPerimetre:
    """
    Macros `\\seq*` qui NE sont PAS nommantes : elles doivent être laissées
    intactes et ne pas déclencher d'incidents.
    """

    def test_seqcorrige_intact(self):
        texte = "\\seqCorrige{réponse}"
        out, inc = resoudre(texte, _ctx_c04())
        assert out == texte
        assert inc == []

    def test_seqplanobjectif_intact(self):
        texte = "\\seqPlanObjectif{02}{notions}{1,2}{3,4}{5,6}"
        out, inc = resoudre(texte, _ctx_c04())
        assert out == texte
        assert inc == []

    def test_seqcolitem_intact(self):
        texte = "\\begin{seqColItem}[2]\\item exo\\end{seqColItem}"
        out, inc = resoudre(texte, _ctx_c04())
        assert out == texte
        assert inc == []

    def test_macro_get_hors_inventaire_signalee_preservee(self):
        texte = "\\seqInconnuGetChose{42}"
        out, inc = resoudre(texte, _ctx_c04())
        assert "\\seqInconnuGetChose" in out  # non remplacée
        assert any("non prise en charge" in i["raison"] for i in inc)


class TestContientMacroNommante:

    def test_texte_avec_macro(self):
        assert contient_macro_nommante("\\seqObjectifGetNom{02}")
        assert contient_macro_nommante("prefix \\seqConnaissanceGetNom{01} suffix")

    def test_texte_sans_macro(self):
        assert not contient_macro_nommante("Titre normal")
        assert not contient_macro_nommante("")
        assert not contient_macro_nommante(None)

    def test_macro_non_get(self):
        assert not contient_macro_nommante("\\seqCorrige{x}")


# ─────────────────────────────────────────────────────────────────────────────
# Construction de contexte depuis les CSV
# ─────────────────────────────────────────────────────────────────────────────

class TestConstruireContexteGlobal:

    def test_depuis_csv_store_complet(self):
        ctx = construire_contexte_global(_CsvStoreFake())
        # Séquences
        assert ctx.sequences_par_cycle["C04"]["S01"]["Nom"] == "Séq A"
        assert ctx.sequences_par_cycle["C03"]["S01"]["Nom"] == "Nombres entiers"
        # Thèmes
        assert ctx.themes_par_cycle["C04"]["D"]["CodeCouleur"] == "geometrie"
        # Niveaux
        assert ctx.param_niveaux["N11"][0] == "C04"
        # Connaissances (clé composite)
        assert ctx.connaissance_nom("N11", "S01", "01") == "Écriture fractionnaire"
        assert ctx.connaissance_nom("N09", "S01", "01") == "Nombres relatifs"
        # Objectifs (clé composite)
        info = ctx.objectif_info("N11", "S01", "02")
        assert info is not None
        assert info["nom"] == "Utiliser la notation scientifique"
        assert info["fin_cycle"] == "O"

    def test_csv_store_en_erreur_renvoie_fallback(self):
        class Buggy:
            def lire_param_niveaux(self):    raise RuntimeError("boom")
            def lire_c03_sequences(self):    raise RuntimeError("boom")
            def lire_c04_sequences(self):    raise RuntimeError("boom")
            def lire_c03_themes(self):       raise RuntimeError("boom")
            def lire_c04_themes(self):       raise RuntimeError("boom")
            def lire_c03_connaissances(self): raise RuntimeError("boom")
            def lire_c04_connaissances(self): raise RuntimeError("boom")
            def lire_c03_objectifs(self):     raise RuntimeError("boom")
            def lire_c04_objectifs(self):     raise RuntimeError("boom")
        ctx = construire_contexte_global(Buggy())
        # Les niveaux sont repris du fallback en dur
        assert "N11" in ctx.param_niveaux
        # Le reste est vide, mais construire_contexte_global n'a pas planté
        assert ctx.sequences_par_cycle.get("C04") == {}
        assert ctx.connaissances == {}
        assert ctx.objectifs == {}


class TestCycleC03:
    """Symétrie C03 / C04 : la résolution fonctionne uniformément."""

    def test_sequence_nom_c03(self):
        ctx = construire_contexte_global(_CsvStoreFake())
        ctx.niveau_courant = "N09"
        ctx.sequence_courante = "S01"
        out, inc = resoudre("\\seqSequenceGetNom", ctx)
        assert out == "Nombres entiers"
        assert inc == []

    def test_connaissance_c03(self):
        ctx = construire_contexte_global(_CsvStoreFake())
        ctx.niveau_courant = "N09"
        ctx.sequence_courante = "S01"
        out, inc = resoudre("\\seqConnaissanceGetNom{01}", ctx)
        assert out == "Nombres relatifs"
        assert inc == []

    def test_objectif_c03(self):
        ctx = construire_contexte_global(_CsvStoreFake())
        ctx.niveau_courant = "N09"
        ctx.sequence_courante = "S01"
        out, inc = resoudre("\\seqObjectifGetNom{02}", ctx)
        assert out == "Objectif 6ème"
        assert inc == []

    def test_pas_de_collision_c03_c04_pour_meme_code(self):
        """
        Important : (N09, S01, "01") et (N10/N11, S01, "01") sont des
        clés distinctes, la fusion C03+C04 ne doit pas écraser l'une
        par l'autre.
        """
        ctx = construire_contexte_global(_CsvStoreFake())
        # N09/S01/01 = Nombres relatifs (C03)
        assert ctx.connaissance_nom("N09", "S01", "01") == "Nombres relatifs"
        # N10/S01/01 = Proportion. (C04)
        assert ctx.connaissance_nom("N10", "S01", "01") == "Proportion."


# ─────────────────────────────────────────────────────────────────────────────
# Intégration avec scanner_vers_bdd
# ─────────────────────────────────────────────────────────────────────────────

class _JsonStoreInMem:
    """SqliteStore-like minimal pour les tests d'intégration."""
    def __init__(self):
        self.n, self.m, self.e, self.l = [], [], [], []
    def lire_notions(self):          return list(self.n)
    def lire_methodes(self):         return list(self.m)
    def lire_exercices(self):        return list(self.e)
    def lire_livrets_importes(self): return list(self.l)
    def ecrire_notions(self, x):          self.n = list(x)
    def ecrire_methodes(self, x):         self.m = list(x)
    def ecrire_exercices(self, x):        self.e = list(x)
    def ecrire_livrets_importes(self, x): self.l = list(x)
    # _conn() n'est utilisé que pour le peuplement v2, qui est sauté
    # si on passe plans_dir=None.


class TestIntegrationScannerVersBdd:

    def test_titres_resolus_depuis_csv(self):
        """
        La résolution fonctionne depuis les CSV, sans dépendre du scan :
        même un fichier dont le titre est uniquement \\seqConnaissanceGetNom{01}
        est résolu correctement.
        """
        from importers.scanner_latex import scanner_vers_bdd
        data = {
            "niveau": "",   # inhibe le peuplement v2 dans le test
            "notions": [
                {"id": "n1", "niveau": "N11", "sequence": "S01",
                 "num_connaissance": "01",
                 "titre": "\\seqConnaissanceGetNom{01}",
                 "fichier": "N11_S01_Notion_01.tex"},
            ],
            "methodes": [
                {"id": "m1", "niveau": "N11", "sequence": "S01",
                 "num_methode": "02", "num_objectif": "02",
                 "titre": "\\seqObjectifGetNom{02}",
                 "fichier": "N11_S01_Methode_02.tex"},
            ],
            "exercices": [], "livrets": [], "erreurs": [],
        }
        js = _JsonStoreInMem()
        resume = scanner_vers_bdd(data, js, _CsvStoreFake(), plans_dir=None)

        assert js.n[0]["titre"] == "Écriture fractionnaire"
        assert js.m[0]["titre"] == "Utiliser la notation scientifique"
        assert resume["incidents_macros"] == []

    def test_incidents_remontent_pour_references_absentes(self):
        from importers.scanner_latex import scanner_vers_bdd
        data = {
            "niveau": "",
            "notions": [
                {"id": "n1", "niveau": "N11", "sequence": "S05",
                 "num_connaissance": "01",
                 "titre": "\\seqConnaissanceGetNom{01}",
                 "fichier": "N11_S05_Notion_01.tex"},
            ],
            "methodes": [],
            "exercices": [], "livrets": [], "erreurs": [],
        }
        js = _JsonStoreInMem()
        resume = scanner_vers_bdd(data, js, _CsvStoreFake(), plans_dir=None)

        # S05 n'est pas dans le fake → la connaissance n'est pas trouvée
        assert js.n[0]["titre"] == FALLBACK
        assert len(resume["incidents_macros"]) == 1
        inc = resume["incidents_macros"][0]
        assert inc["fichier"] == "N11_S05_Notion_01.tex"
        assert inc["champ"] == "titre"
        assert inc["macro"] == "\\seqConnaissanceGetNom{01}"
        assert "N11/S05" in inc["raison"]

    def test_champs_libres_non_touches(self):
        """
        Garde-fou critique (règle Laurent) : corps, exemples, remarques,
        énoncé, corrigé restent intacts, même s'ils contiennent des macros.
        """
        from importers.scanner_latex import scanner_vers_bdd

        corps_avec_macros = ("Pour \\seqConnaissanceGetNom{01}, "
                             "voir \\seqObjectifGetNom{02}.")
        data = {
            "niveau": "",
            "notions": [
                {"id": "n1", "niveau": "N11", "sequence": "S01",
                 "num_connaissance": "01",
                 "titre": "Proportion",
                 "corps": corps_avec_macros,
                 "exemples": [corps_avec_macros],
                 "remarques": [corps_avec_macros],
                 "fichier": "N11_S01_Notion_01.tex"},
            ],
            "methodes": [], "exercices": [], "livrets": [], "erreurs": [],
        }
        js = _JsonStoreInMem()
        scanner_vers_bdd(data, js, _CsvStoreFake(), plans_dir=None)

        assert js.n[0]["titre"] == "Proportion"           # résolu (trivial)
        assert js.n[0]["corps"] == corps_avec_macros       # intact
        assert js.n[0]["exemples"] == [corps_avec_macros]  # intact
        assert js.n[0]["remarques"] == [corps_avec_macros] # intact

    # v0.14.6.b.2 — test_peuplement_v2_saute_si_niveau_vide supprimé :
    # l'étape v2 (helper `_peupler_v2`) a été retirée de scanner_vers_bdd ;
    # le rapport ne contient plus la clé "v2".
