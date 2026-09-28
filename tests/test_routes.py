"""tests/test_routes.py — Tests des routes Flask (couche HTTP)."""

import json
import pytest


# ── /api/classes ───────────────────────────────────────────────────────────────

class TestRoutesClasses:

    def test_get_classes_vide(self, client):
        r = client.get("/api/classes")
        assert r.status_code == 200
        assert r.get_json() == {"classes": []}

    def test_creer_classe(self, client):
        r = client.post("/api/classes", json={
            "nom": "5e1", "niveau": "N10",
            "annee": "2024-2025", "etablissement": "Collège Test"
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data["nom"] == "5e1"
        assert data["niveau"] == "N10"
        assert "id" in data

    def test_creer_classe_sans_nom_retourne_400(self, client):
        r = client.post("/api/classes", json={"niveau": "N10"})
        assert r.status_code == 400

    def test_modifier_classe(self, client):
        r = client.post("/api/classes", json={"nom": "5e1", "niveau": "N10"})
        cid = r.get_json()["id"]
        r2 = client.put(f"/api/classes/{cid}", json={"nom": "5e2"})
        assert r2.status_code == 200
        assert r2.get_json()["nom"] == "5e2"

    def test_modifier_classe_introuvable(self, client):
        r = client.put("/api/classes/INCONNU", json={"nom": "x"})
        assert r.status_code == 404

    def test_supprimer_classe(self, client):
        r = client.post("/api/classes", json={"nom": "5e1", "niveau": "N10"})
        cid = r.get_json()["id"]
        r2 = client.delete(f"/api/classes/{cid}")
        assert r2.status_code == 200
        classes = client.get("/api/classes").get_json()["classes"]
        assert not any(c["id"] == cid for c in classes)

    def test_ajouter_eleve(self, client):
        r = client.post("/api/classes", json={"nom": "5e1", "niveau": "N10"})
        cid = r.get_json()["id"]
        r2 = client.post(f"/api/classes/{cid}/eleves",
                         json={"nom": "dupont", "prenom": "alice"})
        assert r2.status_code == 200
        e = r2.get_json()
        assert e["nom"] == "DUPONT"
        assert e["id"].startswith("el_")  # UUID opaque (cf. TestGenererIdEleve)

    def test_ajouter_eleve_classe_introuvable(self, client):
        r = client.post("/api/classes/INCONNU/eleves",
                        json={"nom": "x", "prenom": "y"})
        assert r.status_code == 404

    def test_supprimer_eleve(self, client, classes_avec_eleves):
        r = client.delete("/api/classes/5E1/eleves/e01")
        assert r.status_code == 200
        classes = client.get("/api/classes").get_json()["classes"]
        eleves = next(c for c in classes if c["id"] == "5E1")["eleves"]
        assert not any(e["id"] == "e01" for e in eleves)

    def test_version_active_refus_si_verrou(self, client):
        # Créer classe
        r = client.post("/api/classes", json={"nom": "5e1", "niveau": "N10"})
        cid = r.get_json()["id"]
        # Cocher un exercice pour verrouiller
        client.post("/api/suivi/exo", json={
            "classe": cid, "seq": "S01", "eleve_id": "e01",
            "serie": "F", "num": 1, "checked": True,
        })
        # Tenter de changer la version → refus
        r2 = client.post(f"/api/classes/{cid}/version",
                         json={"niveau": "N10", "seq": "S01", "tag": "v1"})
        assert r2.status_code == 409


# ── /api/suivi ─────────────────────────────────────────────────────────────────

class TestRoutesSuivi:

    def test_get_suivi_vide(self, client):
        r = client.get("/api/suivi?classe=5E1")
        assert r.status_code == 200
        assert r.get_json() == {}

    def test_cocher_exercice(self, client, classes_avec_eleves):
        r = client.post("/api/suivi/exo", json={
            "classe": "5E1", "seq": "S01", "eleve_id": "e01",
            "serie": "F", "num": 1, "checked": True,
        })
        assert r.status_code == 200
        suivi = client.get("/api/suivi?classe=5E1").get_json()
        assert 1 in suivi["S01"]["e01"]["F"]

    def test_decocher_exercice(self, client, classes_avec_eleves):
        client.post("/api/suivi/exo", json={
            "classe": "5E1", "seq": "S01", "eleve_id": "e01",
            "serie": "F", "num": 1, "checked": True,
        })
        client.post("/api/suivi/exo", json={
            "classe": "5E1", "seq": "S01", "eleve_id": "e01",
            "serie": "F", "num": 1, "checked": False,
        })
        suivi = client.get("/api/suivi?classe=5E1").get_json()
        # Après décocher le seul exercice, S01 peut ne plus exister dans le suivi
        f_list = suivi.get("S01", {}).get("e01", {}).get("F", [])
        assert 1 not in f_list

    def test_set_niveau_valide(self, client, classes_avec_eleves):
        r = client.post("/api/niveaux/set", json={
            "classe": "5E1", "seq": "S01", "eleve_id": "e01",
            "obj_code": "02", "niveau": "3",
        })
        assert r.status_code == 200
        niveaux = client.get("/api/niveaux?classe=5E1").get_json()
        assert niveaux["S01"]["e01"]["02"] == "3"

    def test_set_niveau_invalide_retourne_400(self, client, classes_avec_eleves):
        r = client.post("/api/niveaux/set", json={
            "classe": "5E1", "seq": "S01", "eleve_id": "e01",
            "obj_code": "02", "niveau": "TB",  # ancien code → invalide
        })
        assert r.status_code == 400

    def test_calculer_niveaux(self, client, classes_avec_eleves, yaml_n10_minimal):
        # Cocher tous les F de S01/obj02
        client.post("/api/suivi/exo", json={
            "classe": "5E1", "seq": "S01", "eleve_id": "e01",
            "serie": "F", "num": 1, "checked": True,
        })
        client.post("/api/suivi/exo", json={
            "classe": "5E1", "seq": "S01", "eleve_id": "e01",
            "serie": "F", "num": 2, "checked": True,
        })
        r = client.post("/api/niveaux/calculer", json={
            "classe": "5E1", "seq": "S01", "niveau_code": "N10",
        })
        assert r.status_code == 200
        result = r.get_json()
        # F ok, A pas ok → niveau "2"
        assert result["niveaux"]["e01"]["02"] == "2"


# ── /api/notions ───────────────────────────────────────────────────────────────

class TestRoutesNotions:

    def test_get_notions_vide(self, client):
        # v0.13.6.15 — niveau et sequence désormais obligatoires.
        r = client.get("/api/notions?niveau=N10&sequence=S01")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_creer_notion(self, client):
        r = client.post("/api/notions", json={"titre": "Proportion"})
        assert r.status_code == 201
        data = r.get_json()
        assert data["titre"] == "Proportion"
        assert "id" in data

    def test_creer_notion_sans_titre_201(self, client):
        """v0.13.6.16 — Titre relâché à la création (pattern POST-direct
        unifié). Reste exigé à la validation par le hook."""
        r = client.post("/api/notions", json={})
        assert r.status_code == 201

    def test_modifier_notion(self, client):
        r = client.post("/api/notions", json={"titre": "T1"})
        nid = r.get_json()["id"]
        # v0.13.7.0e — Route en strict PATCH (était en PUT historiquement,
        # bien que la sémantique côté backend était déjà partial update).
        r2 = client.patch(f"/api/notions/{nid}", json={"titre": "T2"})
        assert r2.status_code == 200
        assert r2.get_json()["titre"] == "T2"

    def test_supprimer_notion(self, client):
        r = client.post("/api/notions", json={"titre": "T1"})
        nid = r.get_json()["id"]
        r2 = client.delete(f"/api/notions/{nid}")
        assert r2.status_code == 200
        # v0.13.6.15 — niveau et sequence obligatoires côté GET liste.
        assert client.get("/api/notions?niveau=N10&sequence=S01").get_json() == []


# ── /api/exercices ─────────────────────────────────────────────────────────────

class TestRoutesExercices:

    def test_creer_exercice_valide(self, client):
        r = client.post("/api/exercices", json={
            "serie": "fondamental", "enonce": "Q?", "corrige": "R."
        })
        assert r.status_code == 201
        assert r.get_json()["serie"] == "fondamental"

    def test_creer_exercice_corrige_vide_201(self, client):
        """v0.13.6.16 — Corrigé relâché à la création (modèle en cours)."""
        r = client.post("/api/exercices", json={
            "serie": "fondamental", "enonce": "Q?", "corrige": ""
        })
        assert r.status_code == 201

    def test_filtrer_par_serie(self, client):
        """v0.13.6.15 — Le param `serie` n'est plus interprété côté
        serveur (le contrat liste expose `code` préfixé `E01`/`A03`/…
        qui contient déjà l'info série, le frontend filtre dessus si
        besoin). Le test vérifie maintenant juste que /api/exercices
        avec niveau/sequence retourne le contrat à 6 clés."""
        client.post("/api/exercices", json={
            "serie": "fondamental", "enonce": "Q1", "corrige": "R1",
            "niveau": "N10", "sequence": "S01"
        })
        client.post("/api/exercices", json={
            "serie": "avancé", "enonce": "Q2", "corrige": "R2",
            "niveau": "N10", "sequence": "S01"
        })
        r = client.get("/api/exercices?niveau=N10&sequence=S01")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)
        # Chaque atome porte les 6 clés du contrat
        for a in data:
            assert set(a.keys()) == {'id', 'titre', 'num', 'code',
                                     'etat_code', 'liens', 'sequence'}

    def test_supprimer_exercice(self, client):
        r = client.post("/api/exercices", json={
            "serie": "fondamental", "enonce": "Q?", "corrige": "R."
        })
        eid = r.get_json()["id"]
        r2 = client.delete(f"/api/exercices/{eid}")
        assert r2.status_code == 200
        # v0.13.6.15 — niveau/sequence obligatoires côté GET liste.
        assert client.get(
            "/api/exercices?niveau=N10&sequence=S01"
        ).get_json() == []


# ── /api/admin ─────────────────────────────────────────────────────────────────

class TestRoutesAdmin:

    def test_statut(self, client):
        r = client.get("/api/admin/statut")
        assert r.status_code == 200
        data = r.get_json()
        # Post-R4e4b : le champ "yaml" a disparu, il ne contenait plus qu'un
        # état de cache dérivé. On vérifie à la place la présence des blocs
        # utiles (reference / suivi / c04 / referentiels).
        assert "reference" in data
        assert "suivi" in data
        assert "c04" in data
        assert "referentiels" in data
        assert "yaml" not in data
        # Les sous-compteurs attendus sont bien présents.
        for k in ("notions", "methodes", "exercices", "livrets", "referentiels"):
            assert k in data["reference"]
        for k in ("classes", "eleves", "progressions", "creneaux",
                  "niveaux_saisis", "exercices_coches"):
            assert k in data["suivi"]

    def test_reset_reference(self, client):
        client.post("/api/notions", json={"titre": "T"})
        r = client.post("/api/admin/reset/reference")
        assert r.status_code == 200
        # v0.13.6.15 — niveau/sequence obligatoires côté GET liste.
        assert client.get(
            "/api/notions?niveau=N10&sequence=S01"
        ).get_json() == []

    def test_reset_suivi(self, client, classes_avec_eleves):
        r = client.post("/api/admin/reset/suivi")
        assert r.status_code == 200
        assert client.get("/api/classes").get_json() == {"classes": []}

    def test_qualite_exercices_sans_corrige(self, client):
        client.post("/api/exercices", json={
            "serie": "fondamental", "enonce": "Q?", "corrige": ""
        })
        # L'exercice avec corrigé vide est bloqué à 400 en création,
        # mais on peut tester la route directement avec des données en base
        r = client.get("/api/admin/qualite/exercices-sans-corrige")
        assert r.status_code == 200

    def test_referentiel_niveaux(self, client):
        r = client.get("/api/referentiel/niveaux")
        assert r.status_code == 200
        codes = [item["code"] for item in r.get_json()]
        for code in ("1", "2", "3", "4", "A", "D", "NE"):
            assert code in codes

    def test_referentiel_sequences(self, client):
        r = client.get("/api/referentiel/sequences")
        assert r.status_code == 200
        assert len(r.get_json()) == 3   # 3 séquences dans le CSV de test


# ── /api/sequences ─────────────────────────────────────────────────────────────

class TestRoutesSequences:

    def test_sequences_yaml_absent_retourne_liste_vide(self, client):
        r = client.get("/api/sequences?niveau=N10")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_sequences_depuis_yaml(self, client, yaml_n10_minimal):
        r = client.get("/api/sequences?niveau=N10")
        assert r.status_code == 200
        seqs = r.get_json()
        assert len(seqs) == 2
        # obj01 toujours présent
        codes = [o["code"] for o in seqs[0]["objectifs"]]
        assert "01" in codes


# ── /api/versions ──────────────────────────────────────────────────────────────

class TestRoutesVersions:

    def test_creer_version(self, client, yaml_n10_minimal):
        r = client.post("/api/versions/creer", json={
            "niveau": "N10", "seq": "S01",
            "tag": "2025-09-01", "label": "Rentrée"
        })
        assert r.status_code == 200
        snap = r.get_json()
        assert snap["tag"] == "2025-09-01"

    def test_tag_duplique_409(self, client, yaml_n10_minimal):
        body = {"niveau": "N10", "seq": "S01", "tag": "v1", "label": ""}
        client.post("/api/versions/creer", json=body)
        r = client.post("/api/versions/creer", json=body)
        assert r.status_code == 409

    def test_get_versions(self, client, yaml_n10_minimal):
        client.post("/api/versions/creer", json={
            "niveau": "N10", "seq": "S01", "tag": "v1", "label": ""
        })
        r = client.get("/api/versions?niveau=N10&seq=S01")
        assert r.status_code == 200
        assert len(r.get_json()) == 1
