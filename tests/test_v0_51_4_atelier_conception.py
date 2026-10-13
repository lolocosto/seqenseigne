"""tests/test_v0_51_4_atelier_conception.py — v0.51.4

Atelier de conception des référentiels externes (principal et MER) :
  - codes de séquence recalculés d'après le rang (déplacement, suppression)
    tant que le référentiel est en conception ; conservés une fois utilisé
    ou publié ;
  - durée d'une partie = somme des séances de ses objectifs (lecture seule,
    recalculée à chaque modification, et à la migration) ;
  - déplacement d'un document attaché (annuel, séquence, partie), refusé une
    fois le document marqué distribué.
"""
import json
from datetime import date

import pytest

from app import create_app
from persistence.sqlite_store import SqliteStore
from services import referentiel_principal_externe as rpe

ANNEE = "2026-2027"
AUJ = date(2026, 9, 1)
P = "/api/referentiels-principaux-externes"


@pytest.fixture
def st(tmp_path):
    return SqliteStore(tmp_path / "data")


def _codes(c, rid):
    return [(s["code"], s["nom"]) for s in rpe.lire(c, rid, AUJ)["sequences"]]


def _trois_sequences(c, st, type_ref="principal"):
    rid = rpe.creer(c, "N09", ANNEE, type_ref=type_ref)["id"]
    for nom in ("A", "B", "C"):
        code = rpe.ajouter_sequence(c, rid, nom)["code"]
        rpe.ajouter_partie(c, rid, code, 0, AUJ)
        rpe.ajouter_objectif(c, rid, code, 1, f"Objectif {nom}", 2)
        rpe.ajouter_fichier(c, rid, code, 1, nom_fichier=f"{nom}.pdf", contenu=b"%",
                            mime="application/pdf", data_dir=st.data_dir)
    return rid


# ── Codes de séquence ────────────────────────────────────────────────────────

def test_recodification_en_conception(st):
    with st._conn() as c:
        rid = _trois_sequences(c, st)
        assert rpe.lire(c, rid, AUJ)["en_conception"]
        assert rpe.deplacer_sequence(c, rid, "S03", -1, AUJ) == {"recode": True}
        assert _codes(c, rid) == [("S01", "A"), ("S02", "C"), ("S03", "B")]
        ref = rpe.lire(c, rid, AUJ)
        # Parties, objectifs et documents suivent leur séquence.
        s2 = ref["sequences"][1]
        assert s2["parties"][0]["objectifs"][0]["nom"] == "Objectif C"
        assert s2["parties"][0]["fichiers"][0]["nom_fichier"] == "C.pdf"
        assert s2["parties"][0]["nb_seances_R_AE"] == 2
        # Suppression : les codes se resserrent.
        rpe.supprimer_sequence(c, rid, "S01", AUJ, st.data_dir)
        assert _codes(c, rid) == [("S01", "C"), ("S02", "B")]
        assert rpe.lire(c, rid, AUJ)["sequences"][0]["fichiers"] == []
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
        # La prochaine séquence prend le code suivant.
        assert rpe.ajouter_sequence(c, rid, "D")["code"] == "S03"


def test_recodification_mer(st):
    with st._conn() as c:
        rid = _trois_sequences(c, st, type_ref="mer")
        rpe.deplacer_sequence(c, rid, "M01", 1, AUJ)
        assert _codes(c, rid) == [("M01", "B"), ("M02", "A"), ("M03", "C")]


def test_codes_conserves_si_utilise(st):
    with st._conn() as c:
        rid = _trois_sequences(c, st)
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('et', 'C', 'propose')")
    st.ecrire_progression({"niveau": "N09", "annee": ANNEE, "etablissement_id": "et",
                           "referentiel_id": rid, "creneaux": []})
    with st._conn() as c:
        assert not rpe.lire(c, rid, AUJ)["en_conception"]
        assert rpe.deplacer_sequence(c, rid, "S03", -1, AUJ) == {"recode": False}
        assert _codes(c, rid) == [("S01", "A"), ("S03", "C"), ("S02", "B")]


def test_codes_conserves_si_publie(st):
    with st._conn() as c:
        rid = _trois_sequences(c, st)
        c.execute("CREATE TABLE IF NOT EXISTS publications (id TEXT PRIMARY KEY, cree_le TEXT, "
                  "nom_paquet TEXT, referentiels TEXT, nb_fichiers INTEGER, taille INTEGER)")
        c.execute("INSERT INTO publications (id, cree_le, nom_paquet, referentiels, nb_fichiers, "
                  "taille) VALUES ('p1', '2026-10-01', 'paquet', ?, 0, 0)",
                  (json.dumps([{"id": rid, "nom": "x", "empreinte": "sha256:0"}]),))
        assert rpe.est_publie(c, rid) and not rpe.en_conception(c, rid)
        rpe.supprimer_sequence(c, rid, "S01", AUJ, st.data_dir)
        assert _codes(c, rid) == [("S02", "B"), ("S03", "C")]


# ── Durée des parties ────────────────────────────────────────────────────────

def test_duree_partie_calculee(st):
    with st._conn() as c:
        rid = rpe.creer(c, "N09", ANNEE, type_ref="mer")["id"]
        rpe.ajouter_sequence(c, rid, "Tables")
        rpe.ajouter_partie(c, rid, "M01", 6, AUJ)          # valeur ignorée
        duree = lambda: rpe.lire(c, rid, AUJ)["sequences"][0]["parties"][0]["nb_seances_R_AE"]  # noqa: E731
        assert duree() == 0
        rpe.ajouter_objectif(c, rid, "M01", 1, "Connaître", 1, type_obj="connaissance")
        rpe.ajouter_objectif(c, rid, "M01", 1, "Tables de 2 à 5", 2.5)
        assert duree() == 3.5
        rpe.modifier_objectif(c, rid, "M01", "02", {"nb_seances": 4}, AUJ)
        assert duree() == 5
        rpe.supprimer_objectif(c, rid, "M01", "01", AUJ)
        assert duree() == 4
        assert rpe.parties_mer(c, rid)[0]["nb_seances"] == 4
        with pytest.raises(rpe.RefExtErreur):
            rpe.modifier_partie(c, rid, "M01", 1, 9, AUJ)


def test_migration_recalcule_les_durees(st):
    with st._conn() as c:
        rid = rpe.creer(c, "N09", ANNEE)["id"]
        rpe.ajouter_sequence(c, rid, "Nombres")
        rpe.ajouter_partie(c, rid, "S01", 0, AUJ)
        rpe.ajouter_partie(c, rid, "S01", 0, AUJ)
        rpe.ajouter_objectif(c, rid, "S01", 1, "Comparer", 3)
        c.execute("UPDATE referentiel_parties SET nb_seances_R_AE=7 WHERE referentiel_id=?",
                  (rid,))                                   # saisies d'avant la v0.51.4
        rpe.migrer(c)
        assert [p["nb_seances_R_AE"] for p in rpe.lire(c, rid, AUJ)["sequences"][0]["parties"]] \
            == [3, 0]


# ── Déplacement des documents ────────────────────────────────────────────────

def _deux_parties(c, st):
    rid = rpe.creer(c, "N09", ANNEE)["id"]
    rpe.ajouter_sequence(c, rid, "Nombres")
    rpe.ajouter_sequence(c, rid, "Géométrie")
    for code, durees in (("S01", (4, 2)), ("S02", (3,))):
        for n, d in enumerate(durees, start=1):
            rpe.ajouter_partie(c, rid, code, 0, AUJ)
            rpe.ajouter_objectif(c, rid, code, n, f"Obj {code}.{n}", d)
    f = rpe.ajouter_fichier(c, rid, "S01", 1, nom_fichier="fiche.pdf", contenu=b"%",
                            mime="application/pdf", data_dir=st.data_dir)
    rpe.placer_fichier(c, f["id"], 3, "rendre", "jours", 7)
    return rid, f["id"]


def test_deplacer_document(st):
    with st._conn() as c:
        rid, fid = _deux_parties(c, st)
        # Partie → autre partie (séance conservée ; alerte : 3 > 2 séances).
        r = rpe.deplacer_fichier(c, fid, "S01", 2)
        assert (r["seq_code"], r["partie_numero"], r["seance_n"]) == ("S01", 2, 3)
        assert "au-delà" in r["alerte"]
        # Partie → partie d'une autre séquence, assez longue : pas d'alerte.
        r = rpe.deplacer_fichier(c, fid, "S02", 1)
        assert (r["seq_code"], r["partie_numero"], r["seance_n"], r["alerte"]) == \
            ("S02", 1, 3, "")
        # → séquence : la séance de distribution est effacée.
        r = rpe.deplacer_fichier(c, fid, "S01", 0)
        assert (r["seq_code"], r["partie_numero"], r["seance_n"]) == ("S01", 0, 0)
        assert r["retour"] == "rendre"
        # → annuel.
        r = rpe.deplacer_fichier(c, fid, "", 5)
        assert (r["seq_code"], r["partie_numero"]) == ("", 0)
        assert [f["id"] for f in rpe.lire(c, rid, AUJ)["documents_annuels"]] == [fid]
        for cible in (("S09", 0), ("S01", 9)):
            with pytest.raises(rpe.RefExtErreur):
                rpe.deplacer_fichier(c, fid, *cible)


@pytest.mark.parametrize("cle", ["auto:{fid}:cr1", "automer:{fid}", "pd1", "mer:pd1"])
def test_document_distribue_ne_se_deplace_plus(st, cle):
    with st._conn() as c:
        rid, fid = _deux_parties(c, st)
        c.execute("INSERT INTO progression_doc (id, prog_kind, prog_ref, creneau_ref, "
                  "doc_source, doc_ref, doc_libelle) VALUES ('pd1', 'principale', 'pg', 'cr1', "
                  "'externe', ?, 'Fiche')", (fid,))
        c.execute("INSERT INTO seance_documents (id, classe_id, annee, origine, cle_prevu, "
                  "libelle, cible_date, cible_creneau) VALUES ('sd1', 'c1', ?, 'prevu', ?, "
                  "'Fiche', '2026-09-14', 'M1')", (ANNEE, cle.format(fid=fid)))
        assert not rpe.fichier_distribue(c, fid)                # prévu, pas distribué
        rpe.deplacer_fichier(c, fid, "S01", 2)
        c.execute("UPDATE seance_documents SET distribue_date='2026-09-14', "
                  "distribue_creneau='M1'")
        assert rpe.fichier_distribue(c, fid)
        assert rpe.lire(c, rid, AUJ)["sequences"][0]["parties"][1]["fichiers"][0]["distribue"]
        with pytest.raises(rpe.RefExtErreur, match="distribué"):
            rpe.deplacer_fichier(c, fid, "S01", 1)


# ── Routes et profils ────────────────────────────────────────────────────────

def test_routes(data_dir):
    app = create_app(data_dir, profil="atelier")
    app.config["TESTING"] = True
    cl = app.test_client()
    rid = cl.post(P, json={"niveau": "N09", "annee": ANNEE}).get_json()["id"]
    for nom in ("A", "B"):
        cl.post(f"{P}/{rid}/sequences", json={"nom": nom})
    cl.post(f"{P}/{rid}/sequences/S01/parties", json={})
    assert cl.put(f"{P}/{rid}/sequences/S01/parties/1", json={"nb_seances": 3}).status_code == 400
    with app.json_store._conn() as c:
        fid = rpe.ajouter_fichier(c, rid, "S01", 1, nom_fichier="x.pdf", contenu=b"%",
                                  mime="application/pdf", data_dir=app.json_store.data_dir)["id"]
    r = cl.put(f"{P}/fichiers/{fid}/rattachement", json={"seq_code": "S02", "partie_numero": 0})
    assert r.status_code == 200 and r.get_json()["seq_code"] == "S02"
    assert cl.post(f"{P}/{rid}/sequences/S02/deplacer", json={"sens": -1}).get_json() == \
        {"recode": True}
    l = cl.get(f"{P}/{rid}").get_json()
    assert [(s["code"], s["nom"]) for s in l["sequences"]] == [("S01", "B"), ("S02", "A")]
    assert l["sequences"][0]["fichiers"][0]["id"] == fid
    classe = create_app(data_dir, profil="classe")
    assert classe.test_client().put(f"{P}/fichiers/{fid}/rattachement",
                                    json={"seq_code": ""}).status_code == 403
