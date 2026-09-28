"""tests/test_v0_13_6_2_3_peuplement_cartes_n10.py — v0.13.6.2.3

Tests autour du peuplement des cartes d'automatisme N10.

Couverture :
  - Le module de données charge et tous les champs requis sont présents.
  - Chaque carte respecte les contraintes métier (types valides,
    paramétrée ⇒ variables non vide, recto/verso non vides).
  - Les noms internes sont uniques au sein d'une séquence.
  - Sur une BDD test peuplée, le script crée bien le bon nombre de
    cartes et toutes finissent en état 'valide'.
  - Idempotence : relancer le script ne crée pas de doublons.
"""
from __future__ import annotations

import sqlite3
import sys
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
APPLI_ROOT = HERE.parent
sys.path.insert(0, str(APPLI_ROOT))

from scripts.cartes_n10_data import (  # noqa: E402
    TOUTES_CARTES_N10, COMPTE_PAR_SEQUENCE,
    CARTES_S01, CARTES_S02, CARTES_S03, CARTES_S04,
    CARTES_S05, CARTES_S06, CARTES_S07, CARTES_S08,
    CARTES_S09, CARTES_S10, CARTES_S11, CARTES_S12,
    CARTES_S13, CARTES_S14,
)
from services import cartes_automatisme as cartes  # noqa: E402


CHAMPS_REQUIS = {
    'sequence', 'nom', 'type_pedago', 'type_tech',
    'lien', 'recto', 'verso', 'variables',
}


# ─────────────────────────────────────────────────────────────────────
# 1. Sanity du module de données
# ─────────────────────────────────────────────────────────────────────


def test_module_charge_et_compte_total():
    assert len(TOUTES_CARTES_N10) == sum(COMPTE_PAR_SEQUENCE.values())
    assert len(TOUTES_CARTES_N10) > 100, "Attendu plus de 100 cartes"


def test_les_14_sequences_sont_couvertes():
    sequences_attendues = {f"S{i:02d}" for i in range(1, 15)}
    sequences_couvertes = {c['sequence'] for c in TOUTES_CARTES_N10}
    assert sequences_couvertes == sequences_attendues


@pytest.mark.parametrize("carte", TOUTES_CARTES_N10,
                         ids=lambda c: f"{c['sequence']}/{c['nom']}")
def test_chaque_carte_a_tous_les_champs(carte):
    manquants = CHAMPS_REQUIS - set(carte.keys())
    assert not manquants, f"Champs manquants : {manquants}"


@pytest.mark.parametrize("carte", TOUTES_CARTES_N10,
                         ids=lambda c: f"{c['sequence']}/{c['nom']}")
def test_type_pedago_valide(carte):
    assert carte['type_pedago'] in cartes.TYPES_PEDAGO


@pytest.mark.parametrize("carte", TOUTES_CARTES_N10,
                         ids=lambda c: f"{c['sequence']}/{c['nom']}")
def test_type_tech_valide(carte):
    assert carte['type_tech'] in cartes.TYPES_TECH


@pytest.mark.parametrize("carte", TOUTES_CARTES_N10,
                         ids=lambda c: f"{c['sequence']}/{c['nom']}")
def test_recto_et_verso_non_vides(carte):
    assert carte['recto'].strip(), "Recto vide"
    assert carte['verso'].strip(), "Verso vide"


@pytest.mark.parametrize("carte", TOUTES_CARTES_N10,
                         ids=lambda c: f"{c['sequence']}/{c['nom']}")
def test_parametree_implique_variables(carte):
    if carte['type_tech'] == 'parametree':
        assert carte['variables'].strip(), (
            f"Carte paramétrée {carte['sequence']}/{carte['nom']!r} "
            f"avec variables vide"
        )


@pytest.mark.parametrize("carte", TOUTES_CARTES_N10,
                         ids=lambda c: f"{c['sequence']}/{c['nom']}")
def test_lien_format(carte):
    """Le lien doit être un tuple ('notion'|'methode', int)."""
    assert isinstance(carte['lien'], tuple) and len(carte['lien']) == 2
    lien_type, lien_num = carte['lien']
    assert lien_type in ('notion', 'methode')
    assert isinstance(lien_num, int) and lien_num > 0


def test_noms_uniques_par_sequence():
    """Au sein d'une séquence, deux cartes ne doivent pas avoir le même
    nom (le script utilise ça comme clé d'idempotence).
    """
    par_seq: dict[str, set[str]] = {}
    for c in TOUTES_CARTES_N10:
        seq = c['sequence']
        par_seq.setdefault(seq, set())
        assert c['nom'] not in par_seq[seq], (
            f"Doublon de nom dans {seq} : {c['nom']!r}"
        )
        par_seq[seq].add(c['nom'])


def test_decompte_par_sequence_coherent():
    """COMPTE_PAR_SEQUENCE doit refléter les vraies listes."""
    listes = {
        'S01': CARTES_S01, 'S02': CARTES_S02, 'S03': CARTES_S03,
        'S04': CARTES_S04, 'S05': CARTES_S05, 'S06': CARTES_S06,
        'S07': CARTES_S07, 'S08': CARTES_S08, 'S09': CARTES_S09,
        'S10': CARTES_S10, 'S11': CARTES_S11, 'S12': CARTES_S12,
        'S13': CARTES_S13, 'S14': CARTES_S14,
    }
    for seq, lst in listes.items():
        assert COMPTE_PAR_SEQUENCE[seq] == len(lst)


# ─────────────────────────────────────────────────────────────────────
# 2. Test d'intégration : peuplement sur BDD jetable
# ─────────────────────────────────────────────────────────────────────


def _creer_bdd_minimale(tmp_path: Path) -> Path:
    """Crée une BDD jetable avec juste les tables nécessaires + des
    notions/méthodes N10 factices couvrant tous les numéros utilisés.

    v0.13.6.8.2.2 : ajout de la table etats_edition (peuplée) et de la
    colonne mtime sur notions/methodes. Nécessaire depuis l'unification
    du mécanisme de validation d'état (le wrapper valider_carte délègue
    maintenant à etats_edition.changer_etat_atome qui consulte
    etats_edition et met à jour mtime sur la table cible).
    """
    db = tmp_path / "test_seqenseigne.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE etats_edition (
            code TEXT PRIMARY KEY,
            nom TEXT,
            ordre INTEGER,
            est_final INTEGER
        );
        INSERT INTO etats_edition VALUES
            ('en_cours', 'En cours', 10, 0),
            ('valide',   'Validé',   20, 1);

        CREATE TABLE notions (
            id TEXT PRIMARY KEY,
            niveau TEXT,
            sequence TEXT,
            num_connaissance TEXT,
            titre TEXT,
            etat_code TEXT DEFAULT 'en_cours',
            mtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE methodes (
            id TEXT PRIMARY KEY,
            niveau TEXT,
            sequence TEXT,
            num_methode INTEGER,
            num_objectif INTEGER,
            titre TEXT,
            etat_code TEXT DEFAULT 'en_cours',
            mtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE cartes_automatisme (
            id TEXT PRIMARY KEY,
            niveau TEXT NOT NULL,
            sequence TEXT NOT NULL,
            num INTEGER NOT NULL,
            type_pedago TEXT NOT NULL DEFAULT 'definition',
            type_tech TEXT NOT NULL DEFAULT 'fixe',
            titre TEXT NOT NULL DEFAULT '',
            lien_type TEXT,
            lien_id TEXT,
            recto TEXT NOT NULL DEFAULT '',
            verso TEXT NOT NULL DEFAULT '',
            variables TEXT NOT NULL DEFAULT '',
            etat_code TEXT NOT NULL DEFAULT 'en_cours',
            ordre INTEGER NOT NULL DEFAULT 1,
            mtime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        -- v0.13.6.13 : tables pour le nouveau modèle objectif_cartes.
        -- Le script de peuplement utilise creer_carte() qui dérive
        -- automatiquement les objectif_ids depuis lien_type/lien_id ;
        -- ces tables doivent exister même si aucun objectif n'est
        -- inséré (le script ne crée pas d'objectifs, donc la dérivation
        -- retournera [] partout et les cartes seront orphelines en
        -- objectif_cartes — ce qui est cohérent : le test vérifie
        -- uniquement le peuplement des cartes elles-mêmes).
        CREATE TABLE objectifs (
            id          TEXT PRIMARY KEY,
            methode_id  TEXT REFERENCES methodes(id) ON DELETE CASCADE,
            partie_id   TEXT,
            code        TEXT,
            nom         TEXT
        );
        CREATE TABLE objectif_notions (
            objectif_id TEXT NOT NULL
                        REFERENCES objectifs(id) ON DELETE CASCADE,
            notion_id   TEXT NOT NULL
                        REFERENCES notions(id) ON DELETE CASCADE,
            PRIMARY KEY (objectif_id, notion_id)
        );
        CREATE TABLE objectif_cartes (
            objectif_id TEXT NOT NULL
                        REFERENCES objectifs(id) ON DELETE CASCADE,
            carte_id    TEXT NOT NULL
                        REFERENCES cartes_automatisme(id) ON DELETE CASCADE,
            ordre       INTEGER NOT NULL DEFAULT 0,
            mtime       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (objectif_id, carte_id)
        );
        CREATE TABLE cartes_atelier_config (
            cle TEXT PRIMARY KEY,
            valeur TEXT NOT NULL DEFAULT ''
        );
    """)

    # Pré-créer tous les liens nécessaires
    # v0.13.6.13 — En plus des notions/méthodes, on pré-crée un objectif
    # par notion et par méthode, lié via objectif_notions ou
    # objectifs.methode_id. C'est nécessaire pour que la validation
    # pédagogique des cartes passe (depuis v0.13.6.13, elle exige une
    # liaison non vide dans objectif_cartes, alimentée automatiquement
    # par dérivation depuis lien_type/lien_id à la création de la carte).
    notions_seen = set()
    methodes_seen = set()
    obj_counter = 0
    for c in TOUTES_CARTES_N10:
        lien_type, lien_num = c['lien']
        key = (c['sequence'], lien_num)
        if lien_type == 'notion' and key not in notions_seen:
            notions_seen.add(key)
            notion_id = f"no_test_{c['sequence']}_{lien_num}"
            conn.execute(
                "INSERT INTO notions(id, niveau, sequence, "
                "num_connaissance, titre) VALUES (?,?,?,?,?)",
                (notion_id, 'N10',
                 c['sequence'], f"{lien_num:02d}", f"Notion {lien_num}"),
            )
            obj_counter += 1
            obj_id = f"ob_n_{obj_counter}"
            conn.execute(
                "INSERT INTO objectifs "
                "(id, methode_id, partie_id, code, nom) "
                "VALUES (?, NULL, NULL, ?, ?)",
                (obj_id, f"{lien_num:02d}", f"Objectif {lien_num}"),
            )
            conn.execute(
                "INSERT INTO objectif_notions (objectif_id, notion_id) "
                "VALUES (?, ?)",
                (obj_id, notion_id),
            )
        elif lien_type == 'methode' and key not in methodes_seen:
            methodes_seen.add(key)
            methode_id = f"me_test_{c['sequence']}_{lien_num}"
            conn.execute(
                "INSERT INTO methodes(id, niveau, sequence, num_methode, "
                "num_objectif, titre) VALUES (?,?,?,?,?,?)",
                (methode_id, 'N10',
                 c['sequence'], lien_num, lien_num,
                 f"Méthode {lien_num}"),
            )
            obj_counter += 1
            obj_id = f"ob_m_{obj_counter}"
            conn.execute(
                "INSERT INTO objectifs "
                "(id, methode_id, partie_id, code, nom) "
                "VALUES (?, ?, NULL, ?, ?)",
                (obj_id, methode_id, f"{lien_num:02d}",
                 f"Objectif {lien_num}"),
            )
    conn.commit()
    conn.close()
    return db


def test_peuplement_complet_sur_bdd_jetable(tmp_path):
    db = _creer_bdd_minimale(tmp_path)
    script = APPLI_ROOT / 'scripts' / 'peupler_cartes_n10.py'
    res = subprocess.run(
        [sys.executable, str(script), '--db', str(db)],
        capture_output=True, text=True, encoding='utf-8',
        cwd=str(APPLI_ROOT),
    )
    assert res.returncode == 0, (
        f"Script en erreur :\nstdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )

    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM cartes_automatisme WHERE niveau='N10'"
    )
    assert cur.fetchone()[0] == len(TOUTES_CARTES_N10)

    # Toutes validées
    cur.execute(
        "SELECT COUNT(*) FROM cartes_automatisme "
        "WHERE niveau='N10' AND etat_code != 'valide'"
    )
    assert cur.fetchone()[0] == 0
    conn.close()


def test_peuplement_idempotent(tmp_path):
    """Lancer le script deux fois ne crée pas de doublons."""
    db = _creer_bdd_minimale(tmp_path)
    script = APPLI_ROOT / 'scripts' / 'peupler_cartes_n10.py'

    subprocess.run([sys.executable, str(script), '--db', str(db)],
                   capture_output=True, text=True, encoding='utf-8',
                   cwd=str(APPLI_ROOT), check=True)
    subprocess.run([sys.executable, str(script), '--db', str(db)],
                   capture_output=True, text=True, encoding='utf-8',
                   cwd=str(APPLI_ROOT), check=True)

    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM cartes_automatisme WHERE niveau='N10'"
    )
    # Une seule fois la quantité, pas le double.
    assert cur.fetchone()[0] == len(TOUTES_CARTES_N10)
    conn.close()


def test_dry_run_ne_modifie_pas_la_bdd(tmp_path):
    db = _creer_bdd_minimale(tmp_path)
    script = APPLI_ROOT / 'scripts' / 'peupler_cartes_n10.py'
    subprocess.run(
        [sys.executable, str(script), '--db', str(db), '--dry-run'],
        capture_output=True, text=True, encoding='utf-8',
        cwd=str(APPLI_ROOT), check=True,
    )
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM cartes_automatisme")
    assert cur.fetchone()[0] == 0
    conn.close()
