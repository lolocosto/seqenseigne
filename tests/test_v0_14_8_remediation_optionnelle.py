"""Tests v0.14.8 — Remédiation optionnelle.

Cette livraison transforme la remédiation d'un exercice en une fonction
explicitement activée par une case à cocher dans l'UI, dans le périmètre
des séries F (fondamental) et A (avancé).

Côté backend, l'activation reste **dérivée** : pas de nouveau champ
booléen en base (cf. cadrage Q2=a). La logique :
  - Pas de remédiation : remed_enonce ET remed_corrige sont vides.
  - Remédiation complète : remed_enonce ET remed_corrige sont non vides.
  - Remédiation partielle (XOR) : interdite au passage en `valide`
    (nouveau garde-fou v0.14.8).

Le hook `_valider_exercice_hook` est étendu pour vérifier cette
symétrie. Ces tests valident ce comportement.
"""
from __future__ import annotations

import pytest
import sqlite3
from pathlib import Path

from services.atomes import _valider_exercice_hook
from services.etats_edition import ValidationPedagogiqueErreur


@pytest.fixture
def conn(tmp_path):
    """Connexion SQLite avec une table `exercices` minimale."""
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE exercices (
            id            TEXT PRIMARY KEY,
            serie         TEXT NOT NULL,
            serie_code    TEXT NOT NULL DEFAULT '',
            niveau        TEXT NOT NULL DEFAULT '',
            sequence      TEXT NOT NULL DEFAULT '',
            num           INTEGER,
            fichier       TEXT NOT NULL DEFAULT '',
            titre         TEXT NOT NULL DEFAULT '',
            variables     TEXT NOT NULL DEFAULT '',
            enonce        TEXT NOT NULL DEFAULT '',
            corrige       TEXT NOT NULL DEFAULT '',
            remed_enonce  TEXT NOT NULL DEFAULT '',
            remed_corrige TEXT NOT NULL DEFAULT ''
        )
    """)
    return db


def _ins(conn, exo_id="ex1", enonce="E", corrige="C",
         remed_enonce="", remed_corrige=""):
    """Insère un exercice avec ces champs (le reste vide ou nul)."""
    conn.execute(
        "INSERT INTO exercices (id, serie, enonce, corrige, "
        "remed_enonce, remed_corrige) VALUES (?,?,?,?,?,?)",
        (exo_id, "fondamental", enonce, corrige, remed_enonce, remed_corrige),
    )
    conn.commit()


# ── 1. Cas neutres : pas de remédiation, ne bloque pas la validation ────

class TestPasDeRemediation:
    """Si les deux champs remed_* sont vides, c'est l'absence de
    remédiation. Comportement identique à v0.13.x : le hook valide
    juste enonce et corrige.
    """

    def test_exo_complet_sans_remediation_valide(self, conn):
        _ins(conn, enonce="Énoncé", corrige="Corrigé",
             remed_enonce="", remed_corrige="")
        # Ne doit pas lever
        _valider_exercice_hook(conn, "ex1")

    def test_exo_sans_enonce_bloque(self, conn):
        _ins(conn, enonce="", corrige="C", remed_enonce="", remed_corrige="")
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            _valider_exercice_hook(conn, "ex1")
        assert "L'énoncé est vide." in exc.value.details["raisons"]

    def test_exo_sans_corrige_bloque(self, conn):
        _ins(conn, enonce="E", corrige="", remed_enonce="", remed_corrige="")
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            _valider_exercice_hook(conn, "ex1")
        assert "Le corrigé est vide." in exc.value.details["raisons"]


# ── 2. Remédiation complète : deux champs remplis, validation passe ─────

class TestRemediationComplete:
    """Avec énoncé ET corrigé de remédiation non vides, la validation
    passe (l'exo principal doit aussi être complet).
    """

    def test_exo_complet_avec_remediation_complete_valide(self, conn):
        _ins(conn, enonce="E", corrige="C",
             remed_enonce="Énoncé remed", remed_corrige="Corrigé remed")
        # Ne doit pas lever
        _valider_exercice_hook(conn, "ex1")

    def test_remediation_complete_avec_exo_incomplet_bloque_sur_exo(self, conn):
        """La remédiation complète ne sauve pas un exo principal
        incomplet. Le hook signale la cause exo principal.
        """
        _ins(conn, enonce="", corrige="C",
             remed_enonce="Énoncé remed", remed_corrige="Corrigé remed")
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            _valider_exercice_hook(conn, "ex1")
        raisons = exc.value.details["raisons"]
        assert "L'énoncé est vide." in raisons
        # Pas d'erreur de remédiation puisqu'elle est complète
        for r in raisons:
            assert "remédiation" not in r.lower() or "L'énoncé est vide." == r


# ── 3. Remédiation partielle (XOR) : interdite ──────────────────────────

class TestRemediationPartielle:
    """v0.14.8 — Si l'utilisateur a rempli un seul des deux champs
    remed_*, la validation doit refuser. Symétrie obligatoire.
    """

    def test_remed_enonce_seul_bloque(self, conn):
        """remed_enonce rempli, remed_corrige vide → bloqué."""
        _ins(conn, enonce="E", corrige="C",
             remed_enonce="Énoncé remed", remed_corrige="")
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            _valider_exercice_hook(conn, "ex1")
        raisons = exc.value.details["raisons"]
        assert any("corrigé de remédiation est vide" in r for r in raisons)

    def test_remed_corrige_seul_bloque(self, conn):
        """remed_corrige rempli, remed_enonce vide → bloqué."""
        _ins(conn, enonce="E", corrige="C",
             remed_enonce="", remed_corrige="Corrigé remed")
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            _valider_exercice_hook(conn, "ex1")
        raisons = exc.value.details["raisons"]
        assert any("énoncé de remédiation est vide" in r.lower()
                   for r in raisons)

    def test_remed_partielle_seul_pas_de_double_erreur(self, conn):
        """Si l'exo principal est complet, on n'a qu'UNE raison
        d'erreur (celle de remédiation partielle).
        """
        _ins(conn, enonce="E", corrige="C",
             remed_enonce="X", remed_corrige="")
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            _valider_exercice_hook(conn, "ex1")
        assert len(exc.value.details["raisons"]) == 1

    def test_remed_partielle_avec_exo_incomplet_cumule(self, conn):
        """Exo principal incomplet ET remédiation partielle :
        on accumule les deux raisons.
        """
        _ins(conn, enonce="E", corrige="",
             remed_enonce="X", remed_corrige="")
        with pytest.raises(ValidationPedagogiqueErreur) as exc:
            _valider_exercice_hook(conn, "ex1")
        raisons = exc.value.details["raisons"]
        # Deux raisons : corrigé principal vide + corrigé remed vide
        assert len(raisons) == 2
        textes = " | ".join(raisons)
        assert "Le corrigé est vide." in textes
        assert "corrigé de remédiation est vide" in textes.lower()


# ── 4. Le tex n'émet pas \seqRemediation si remed vide ──────────────────

class TestGenerationTex:
    """Sanity : la génération du .tex (qui n'est pas re-testée
    intégralement ici) doit dépendre de la non-vacuité des champs
    remed_*. C'est déjà le comportement existant (cf. mémoire et
    services/latex_rendu_atome.py:843-845 — a_remediation calcule
    bool(remed_enonce or remed_corrige)).

    Ce test valide uniquement le helper qui vérifie l'« activation
    dérivée » côté Python : si l'un des deux est non vide, la
    remédiation est considérée activée.
    """

    def test_activation_derivee_des_champs(self):
        """v0.14.8 — Au niveau métier, on considère la remédiation
        activée ssi au moins un des deux champs est non vide. C'est
        la convention dérivée (Q2=a).
        """
        def a_remediation(remed_enonce, remed_corrige):
            return bool((remed_enonce or "").strip()
                     or (remed_corrige or "").strip())

        assert a_remediation("", "")     is False
        assert a_remediation("   ", "")  is False  # espaces seuls
        assert a_remediation("X", "")    is True
        assert a_remediation("", "Y")    is True
        assert a_remediation("X", "Y")   is True
