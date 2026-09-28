"""tests/test_services.py — Tests des services métier (sans Flask, sans I/O)."""

import pytest

# v0.7 — Tests adaptés au modèle universel à 2 niveaux
# (atome_sections + atome_section_items remplacent items_texte).
from services import classes as svc_cls
from services import suivi as svc_suivi
from services import atomes as svc_atomes
from services import versions as svc_ver
from services.sequences import (
    _normaliser_criteres, _normaliser_exercices,
    trouver_sequence, build_sequences,
)


# ── services/classes.py ────────────────────────────────────────────────────────

class TestSlug:
    def test_nom_simple(self):
        assert svc_cls.slug("5e1") == "5E1"

    def test_nom_avec_espaces(self):
        assert svc_cls.slug("4ème 3") == "4ME3"

    def test_chaine_vide(self):
        assert svc_cls.slug("") == ""


class TestGenererIdClasse:
    """
    Les cid sont désormais des UUID opaques 'cl_xxxxxxxx' — plus de
    sémantique sur le nom. La contrainte d'unicité métier (nom, année,
    établissement) est portée par la base via un index UNIQUE séparé.
    """
    def test_format(self):
        cid = svc_cls.generer_id_classe("5e1", set())
        assert cid.startswith("cl_")
        assert len(cid) == 11  # 'cl_' + 8 hex

    def test_ids_uniques_meme_nom(self):
        # Deux classes de même nom → ids distincts (l'unicité est assurée par la
        # contrainte SQL, pas par le nom)
        id1 = svc_cls.generer_id_classe("5e1", set())
        id2 = svc_cls.generer_id_classe("5e1", set())
        assert id1 != id2

    def test_accepte_parametres_retrocompat(self):
        # Ancienne signature tolérée mais ignorée
        cid = svc_cls.generer_id_classe("5e1", {"cl_abcdef01"})
        assert cid.startswith("cl_")


class TestGenererIdEleve:
    """
    Les eid sont désormais des UUID opaques 'el_xxxxxxxx'.
    """
    def test_format(self):
        eid = svc_cls.generer_id_eleve()
        assert eid.startswith("el_")
        assert len(eid) == 11  # 'el_' + 8 hex
        # Tous les caractères après 'el_' sont hex
        assert all(c in "0123456789abcdef" for c in eid[3:])

    def test_ids_uniques_sur_nombreuses_generations(self):
        ids = {svc_cls.generer_id_eleve() for _ in range(1000)}
        assert len(ids) == 1000  # aucune collision sur 1000 tirages

    def test_accepte_argument_existants_pour_retrocompat(self):
        # L'ancienne signature exigeait un set ; on tolère encore cet argument
        # mais il n'est plus utilisé (UUID garantit déjà l'unicité).
        eid = svc_cls.generer_id_eleve({"el_12345678"})
        assert eid.startswith("el_")


class TestCreerClasse:
    def test_creer_ajoute_classe(self):
        data = {"classes": []}
        data, nouvelle = svc_cls.creer_classe(data, "5e1", "N10", "2024-2025", "Collège Test")
        assert len(data["classes"]) == 1
        assert nouvelle["nom"] == "5e1"
        assert nouvelle["niveau"] == "N10"

    def test_id_unique_si_doublon(self):
        data = {"classes": [{"id": "5E1", "nom": "5e1", "niveau": "N10",
                              "annee": "", "etablissement": "", "eleves": [],
                              "versions_actives": {}, "sequences_verouillees": []}]}
        data, nouvelle = svc_cls.creer_classe(data, "5e1", "N10", "", "")
        assert nouvelle["id"] != "5E1"

    def test_champs_par_defaut(self):
        data = {"classes": []}
        _, nouvelle = svc_cls.creer_classe(data, "5e1", "N10", "", "")
        assert "eleves" in nouvelle
        assert "versions_actives" in nouvelle
        assert "sequences_verouillees" in nouvelle


class TestModifierClasse:
    def _data(self):
        return {"classes": [
            {"id": "5E1", "nom": "5e1", "niveau": "N10",
             "annee": "2024-2025", "etablissement": "Test",
             "eleves": [], "versions_actives": {}, "sequences_verouillees": []}
        ]}

    def test_modifier_nom(self):
        data = self._data()
        c = svc_cls.modifier_classe(data, "5E1", {"nom": "5e2"})
        assert c["nom"] == "5e2"

    def test_classe_introuvable_retourne_none(self):
        data = self._data()
        assert svc_cls.modifier_classe(data, "INCONNU", {"nom": "x"}) is None


class TestAjouterEleve:
    def _data(self):
        return {"classes": [
            {"id": "5E1", "nom": "5e1", "niveau": "N10",
             "annee": "", "etablissement": "", "eleves": [],
             "versions_actives": {}, "sequences_verouillees": []}
        ]}

    def test_ajouter_eleve(self):
        data, eleve = svc_cls.ajouter_eleve(self._data(), "5E1", "dupont", "alice")
        assert eleve["nom"] == "DUPONT"
        assert eleve["prenom"] == "alice"
        assert eleve["id"].startswith("el_")  # UUID opaque

    def test_eleves_tries_alphabetiquement(self):
        data = self._data()
        data, _ = svc_cls.ajouter_eleve(data, "5E1", "martin", "Bob")
        data, _ = svc_cls.ajouter_eleve(data, "5E1", "dupont", "Alice")
        eleves = next(c for c in data["classes"] if c["id"] == "5E1")["eleves"]
        assert eleves[0]["nom"] == "DUPONT"
        assert eleves[1]["nom"] == "MARTIN"

    def test_classe_introuvable(self):
        data, eleve = svc_cls.ajouter_eleve(self._data(), "INCONNU", "x", "y")
        assert eleve is None


class TestImporterElevesCSV:
    def _data(self):
        return {"classes": [
            {"id": "5E1", "nom": "5e1", "niveau": "N10",
             "annee": "", "etablissement": "", "eleves": [],
             "versions_actives": {}, "sequences_verouillees": []}
        ]}

    def test_import_simple(self):
        rows = [{"Nom": "DUPONT", "Prenom": "Alice"},
                {"Nom": "MARTIN", "Prenom": "Bob"}]
        data, resume = svc_cls.importer_eleves_csv(
            self._data(), "5E1", rows, "Nom", "Prenom"
        )
        assert resume["ajouts"] == 2
        assert resume["ignores"] == 0

    def test_doublons_ignores(self):
        data = self._data()
        rows = [{"Nom": "DUPONT", "Prenom": "Alice"}]
        data, _ = svc_cls.importer_eleves_csv(data, "5E1", rows, "Nom", "Prenom")
        data, resume = svc_cls.importer_eleves_csv(data, "5E1", rows, "Nom", "Prenom")
        assert resume["ignores"] == 1
        assert resume["ajouts"] == 0


class TestVerrouillage:
    def _classe(self):
        return {"classes": [
            {"id": "5E1", "nom": "5e1", "niveau": "N10",
             "annee": "", "etablissement": "", "eleves": [],
             "versions_actives": {}, "sequences_verouillees": []}
        ]}

    def test_verrouiller(self):
        data = svc_cls.verrouiller_sequence(self._classe(), "5E1", "N10", "S01")
        c = svc_cls.trouver_classe(data, "5E1")
        assert "N10_S01" in c["sequences_verouillees"]

    def test_pas_de_doublon(self):
        data = self._classe()
        data = svc_cls.verrouiller_sequence(data, "5E1", "N10", "S01")
        data = svc_cls.verrouiller_sequence(data, "5E1", "N10", "S01")
        c = svc_cls.trouver_classe(data, "5E1")
        assert c["sequences_verouillees"].count("N10_S01") == 1

    def test_est_verrouille(self):
        data = self._classe()
        data = svc_cls.verrouiller_sequence(data, "5E1", "N10", "S01")
        c = svc_cls.trouver_classe(data, "5E1")
        assert svc_cls.est_verrouille(c, "N10", "S01")
        assert not svc_cls.est_verrouille(c, "N10", "S02")

    def test_definir_version_refuse_si_verrou(self):
        data = self._classe()
        data = svc_cls.verrouiller_sequence(data, "5E1", "N10", "S01")
        _, erreur = svc_cls.definir_version_active(data, "5E1", "N10", "S01", "v1")
        assert erreur is not None
        assert "verrouillée" in erreur


# ── services/suivi.py ──────────────────────────────────────────────────────────

class TestCocherExercice:
    def test_cocher(self):
        suivi = svc_suivi.cocher_exercice({}, "5E1", "S01", "e01", "F", 1, True)
        assert 1 in suivi["5E1"]["S01"]["e01"]["F"]

    def test_decocher(self):
        suivi = {"5E1": {"S01": {"e01": {"F": [1, 2], "A": [], "E": [], "cours": []}}}}
        suivi = svc_suivi.cocher_exercice(suivi, "5E1", "S01", "e01", "F", 1, False)
        assert 1 not in suivi["5E1"]["S01"]["e01"]["F"]

    def test_pas_de_doublon(self):
        suivi = svc_suivi.cocher_exercice({}, "5E1", "S01", "e01", "F", 1, True)
        suivi = svc_suivi.cocher_exercice(suivi, "5E1", "S01", "e01", "F", 1, True)
        assert suivi["5E1"]["S01"]["e01"]["F"].count(1) == 1

    def test_liste_triee(self):
        suivi = svc_suivi.cocher_exercice({}, "5E1", "S01", "e01", "F", 3, True)
        suivi = svc_suivi.cocher_exercice(suivi, "5E1", "S01", "e01", "F", 1, True)
        assert suivi["5E1"]["S01"]["e01"]["F"] == [1, 3]


class TestCalculerNiveauxSequence:
    def _objectif(self, code, F=None, A=None, E=None, is01=False):
        return {
            "code": code, "is01": is01,
            "exercices": {
                "fondamental": F or [],
                "avancé":      A or [],
                "exploration": E or [],
            }
        }

    def test_calcul_simple(self):
        suivi = {"5E1": {"S01": {"e01": {"F": [1], "A": [], "E": [], "cours": []}}}}
        objectifs = [self._objectif("02", F=[1], A=[1])]
        eleves = [{"id": "e01"}]
        niveaux = svc_suivi.calculer_niveaux_sequence(
            suivi, {}, "5E1", "S01", eleves, objectifs
        )
        # F ok, A pas ok → niveau 2
        assert niveaux["5E1"]["S01"]["e01"]["02"] == "2"

    def test_tout_ok_niveau_4(self):
        suivi = {"5E1": {"S01": {"e01": {"F": [1], "A": [1], "E": [1], "cours": []}}}}
        objectifs = [self._objectif("02", F=[1], A=[1], E=[1])]
        eleves = [{"id": "e01"}]
        niveaux = svc_suivi.calculer_niveaux_sequence(
            suivi, {}, "5E1", "S01", eleves, objectifs
        )
        assert niveaux["5E1"]["S01"]["e01"]["02"] == "4"


# ── services/atomes.py ─────────────────────────────────────────────────────────

class TestCreerNotion:
    def test_creer_valide(self):
        _, notion, err = svc_atomes.creer_notion([], {"titre": "Proportion"})
        assert err is None
        assert notion["titre"] == "Proportion"
        assert notion["id"].startswith("no_")
        assert len(notion["id"]) == 11  # 'no_' + 8 hex

    def test_titre_manquant_ok_a_la_creation(self):
        """v0.13.6.16 — Le titre n'est plus obligatoire à la création
        (modèle « en cours »). La règle est appliquée par le hook de
        validation pédagogique au passage en `valide` (cf.
        test_v0_10_4_etats_edition pour le test du hook)."""
        _, notion, err = svc_atomes.creer_notion([], {})
        assert err is None
        assert notion["titre"] == ""

    def test_titre_vide_ok_a_la_creation(self):
        """v0.13.6.16 — Idem ci-dessus pour titre = '   '."""
        _, notion, err = svc_atomes.creer_notion([], {"titre": "   "})
        assert err is None
        assert notion["titre"] == ""


class TestModifierNotion:
    def _liste(self):
        return [{"id": "abc12345", "titre": "Proportion",
                 "corps": "", "exemples": [], "remarques": [], "ordreExRem": True}]

    def test_modifier_titre(self):
        _, notion, err = svc_atomes.modifier_notion(
            self._liste(), "abc12345", {"titre": "Nouveau titre"}
        )
        assert err is None
        assert notion["titre"] == "Nouveau titre"

    def test_notion_introuvable(self):
        _, notion, err = svc_atomes.modifier_notion(self._liste(), "INCONNU", {})
        assert err is not None
        assert notion is None


class TestSupprimerNotion:
    def test_supprimer(self):
        liste = [{"id": "abc12345", "titre": "T"}]
        liste, err = svc_atomes.supprimer_notion(liste, "abc12345")
        assert err is None
        assert len(liste) == 0

    def test_introuvable(self):
        _, err = svc_atomes.supprimer_notion([], "INCONNU")
        assert err is not None


class TestValiderExercice:
    def test_valide(self):
        assert svc_atomes.valider_exercice({
            "serie": "fondamental", "enonce": "Q?", "corrige": "R."
        }) is None

    def test_serie_invalide(self):
        err = svc_atomes.valider_exercice({
            "serie": "mauvais", "enonce": "Q?", "corrige": "R."
        })
        assert err is not None

    def test_corrige_optionnel_a_la_creation(self):
        """v0.13.6.16 — Le corrigé n'est plus obligatoire à la création
        (modèle « en cours »). Refusé à la validation par le hook
        pédagogique."""
        err = svc_atomes.valider_exercice({
            "serie": "fondamental", "enonce": "Q?", "corrige": ""
        })
        assert err is None


class TestDiagnosticsQualite:
    def test_exercices_sans_corrige(self):
        exos = [
            {"id": "a", "serie": "fondamental", "nom": "", "corrige": ""},
            {"id": "b", "serie": "fondamental", "nom": "", "corrige": "R."},
        ]
        result = svc_atomes.exercices_sans_corrige(exos)
        assert len(result) == 1
        assert result[0]["id"] == "a"

    def test_notions_sans_exemple(self):
        # v0.7 : modèle universel à 2 niveaux. Une notion est « sans
        # exemple » si elle n'a aucune section avec au moins un item.
        notions = [
            {"id": "a", "titre": "T1", "sections": []},
            {"id": "b", "titre": "T2", "sections": [
                {"titre": "Exemples", "items": ["ex"]},
            ]},
        ]
        result = svc_atomes.notions_sans_exemple(notions)
        assert len(result) == 1
        assert result[0]["id"] == "a"

    def test_methodes_sans_exemple(self):
        # v0.7 : la méthode "a" a une section "Remarques" non vide → elle
        # n'est PAS « sans exemple » (le critère est : au moins une section
        # avec au moins un item, indépendamment du titre). La méthode "b"
        # n'a aucune section → elle est sans exemple.
        methodes = [
            {"id": "a", "titre": "M1", "sections": [
                {"titre": "Remarques", "items": ["rem"]},
            ]},
            {"id": "b", "titre": "M2", "sections": []},
        ]
        result = svc_atomes.methodes_sans_exemple(methodes)
        assert len(result) == 1
        assert result[0]["id"] == "b"

    def test_atomes_non_affectes_tous_orphelins(self):
        notions   = [{"id": "n1", "titre": "N", "fichier": "f_notion.tex"}]
        methodes  = [{"id": "m1", "titre": "M", "fichier": "f_methode.tex"}]
        exercices = [{"id": "e1", "serie": "fondamental", "fichier": "e.tex",
                      "niveau": "N10", "sequence": "S01",
                      "serie_code": "F", "num": 1}]
        livrets   = []  # aucun livret → tout est orphelin
        result = svc_atomes.atomes_non_affectes(notions, methodes, exercices, livrets)
        assert len(result["notions"]) == 1
        assert len(result["methodes"]) == 1
        assert len(result["exercices"]) == 1


# ── services/versions.py ───────────────────────────────────────────────────────

class TestVersions:
    def _seq(self):
        return {
            "objectifs": [
                {"code": "01", "nom": "Cours", "exercices": {"fondamental": [], "avancé": [], "exploration": []}},
                {"code": "02", "nom": "Obj 2", "exercices": {"fondamental": [1], "avancé": [], "exploration": []}},
            ],
            "connaissances": [],
        }

    def test_creer_snapshot(self):
        versions, snap, err = svc_ver.creer_snapshot(
            {}, "N10", "S01", "2025-09-01", "Rentrée", self._seq()
        )
        assert err is None
        assert snap["tag"] == "2025-09-01"
        assert len(snap["objectifs"]) == 2
        assert len(versions["N10"]["S01"]) == 1

    def test_tag_duplique_retourne_erreur(self):
        versions = {"N10": {"S01": [{"tag": "2025-09-01"}]}}
        _, _, err = svc_ver.creer_snapshot(
            versions, "N10", "S01", "2025-09-01", "", self._seq()
        )
        assert err is not None

    def test_supprimer_snapshot(self):
        versions = {"N10": {"S01": [{"tag": "v1"}, {"tag": "v2"}]}}
        classes  = {"classes": []}
        versions, err = svc_ver.supprimer_snapshot(versions, classes, "N10", "S01", "v1")
        assert err is None
        assert len(versions["N10"]["S01"]) == 1
        assert versions["N10"]["S01"][0]["tag"] == "v2"

    def test_supprimer_refuse_si_classe_utilise(self):
        versions = {"N10": {"S01": [{"tag": "v1"}]}}
        classes  = {"classes": [{"nom": "5e1", "versions_actives": {"N10_S01": "v1"}}]}
        _, err = svc_ver.supprimer_snapshot(versions, classes, "N10", "S01", "v1")
        assert err is not None


# ── services/sequences.py ─────────────────────────────────────────────────────

class TestNormaliserCriteres:
    def test_nouvelle_convention(self):
        obj = {"criteres": {"2": "a", "3": "b", "4": "c"}}
        assert _normaliser_criteres(obj) == {"2": "a", "3": "b", "4": "c"}

    def test_ancienne_convention_FAE(self):
        obj = {"criteres": {"F": "f", "A": "a", "E": "e"}}
        result = _normaliser_criteres(obj)
        assert result == {"2": "f", "3": "a", "4": "e"}

    def test_tres_ancienne_convention_maitrise(self):
        obj = {"maitrise": {"F": "f", "S": "s", "TB": "tb"}}
        result = _normaliser_criteres(obj)
        assert result == {"2": "f", "3": "s", "4": "tb"}


class TestNormaliserExercices:
    def test_nouvelle_cle(self):
        src = {"fondamental": [1], "avancé": [2], "exploration": [3]}
        assert _normaliser_exercices(src) == src

    def test_ancienne_cle(self):
        src = {"fondamentaux": [1], "autonomes": [2], "enrichissement": [3]}
        result = _normaliser_exercices(src)
        assert result["fondamental"] == [1]
        assert result["avancé"] == [2]
        assert result["exploration"] == [3]


class TestTrouverSequence:
    def test_trouvee(self):
        seqs = [{"code": "S01"}, {"code": "S02"}]
        assert trouver_sequence(seqs, "S01")["code"] == "S01"

    def test_introuvable(self):
        assert trouver_sequence([], "S01") is None


class TestBuildSequences:
    def test_depuis_yaml(self, yaml_n10_minimal, store, yaml_store, csv_store):
        seqs = build_sequences("N10", yaml_store, store, csv_store)
        assert len(seqs) == 2
        # obj01 injecté
        codes = [o["code"] for o in seqs[0]["objectifs"]]
        assert "01" in codes
        assert "02" in codes

    def test_obj01_toujours_present(self, yaml_n10_minimal, store, yaml_store, csv_store):
        seqs = build_sequences("N10", yaml_store, store, csv_store)
        for seq in seqs:
            assert any(o["code"] == "01" for o in seq["objectifs"])

    def test_yaml_absent_retourne_liste_vide(self, store, yaml_store, csv_store):
        # Aucun YAML, aucun livret importé → liste vide
        seqs = build_sequences("N10", yaml_store, store, csv_store)
        assert seqs == []
