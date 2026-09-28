#!/usr/bin/env python3
"""outils/import_historique_5e2_2021.py — v0.19.1.7

Import « ad hoc » de la structure historique de la progression 5ᵉ2 2021-22
(Collège des Hautes Ourmes), à partir du répertoire d'archives de l'époque.
Même principe que `import_historique_4e3_2021.py` ; valeurs figées, lues des
fichiers `*_Plan.tex` / `Progression_annuelle.tex` les plus récents (la vérité
est dans les fichiers récents).

Cible :
  - référentiel  : N10_v2021  (verrouillé)
  - progression  : pg_85a0bf3a (2021-2022, Hautes Ourmes)
  - classe       : cl_e4005346 (5E2 — une SEULE classe sur cette progression,
                                 contrairement à la 4e3 qui en partageait 3)

Spécificités vs 4e3 :
  - TROIS séquences scindées en 2 parties : S10, S12, S14 (la 4e3 n'avait que
    S12).
  - Le créneau S10 partie 2 N'EXISTE PAS encore en base : il faut le CRÉER
    (les créneaux P2 de S12 et S14 existent déjà). On y déplace ensuite le
    suivi des objectifs de la partie 2.

Opérations (transaction unique) :

  1. RÉFÉRENTIEL — parties + mode
     - mode_seances = 'par_serie'
     - referentiel_parties : S10, S12, S14 → {1, 2} ; autres → {1}
     - referentiel_objectifs.partie_numero :
         S10 P1={01,04,05,07} P2={02,03,06,08}
         S12 P1={01,04}       P2={02,03}
         S14 P1={01,02}       P2={03,04}

  2. RÉFÉRENTIEL — séances par série (on n'insère que les matrices présentes
     dans les plans autoritaires). Séquences AVEC matrice : S01, S02, S03,
     S07, S08, S11, S12 (P1+P2), S14 (P1). Sans matrice : S04, S05, S06, S09,
     S10 (P1+P2), S13, S14 (P2).

  3. PROGRESSION — créneaux corrigés EN PLACE (IDs préservés) + CRÉATION du
     créneau S10 P2 :
     - ordre chronologique, date_debut/date_fin, période T1/T2/T3 (dérivée des
       dates), libellés de partie pour S10/S12/S14.

  4. SUIVI — redistribution sur les parties 2 :
     - S12 : obj {02,03} déplacés du créneau P1 (cr_4843b058) vers P2
       (cr_1aa33a7b).
     - S14 : obj {03,04} déplacés du créneau P1 (cr_cf0bfc61) vers P2
       (cr_1a3ae909).
     - S10 : obj {02,03,06,08} déplacés du créneau P1 (cr_f84719bc) vers le
       NOUVEAU créneau P2 (créé à l'étape 3).

  Hors périmètre : les bilans de fin de trimestre.

Sécurités : dry-run par défaut ; --apply + 'OUI' (ou --yes) ; idempotent ;
transaction unique ; vérification post-import.

Usage :
    python -m outils.import_historique_5e2_2021            # dry-run
    python -m outils.import_historique_5e2_2021 --apply
    python -m outils.import_historique_5e2_2021 --apply --yes

Codes de sortie : 0 succès, 1 annulé, 2 base introuvable, 3 erreur.
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from persistence.ids import nouveau_id_creneau  # noqa: E402

# ── Constantes cibles ────────────────────────────────────────────────────────

REF_ID = "N10_v2021"
PROG_ID = "pg_85a0bf3a"
CLASSE = "cl_e4005346"  # 5E2 (une seule classe)

# Créneaux existants des séquences scindées (audit base).
CRENEAU = {
    ("S10", 1): "cr_f84719bc",   # S10 P2 sera créé
    ("S12", 1): "cr_4843b058",
    ("S12", 2): "cr_1aa33a7b",
    ("S14", 1): "cr_cf0bfc61",
    ("S14", 2): "cr_1a3ae909",
}

# Découpage objectif → partie (Q1, validé).
DECOUPAGE = {
    "S10": {1: ("01", "04", "05", "07"), 2: ("02", "03", "06", "08")},
    "S12": {1: ("01", "04"),             2: ("02", "03")},
    "S14": {1: ("01", "02"),             2: ("03", "04")},
}

# Parties par séquence : S10, S12, S14 → 2 ; autres → 1.
PARTIES_PAR_SEQ = {f"S{n:02d}": [1] for n in range(1, 15)}
for s in ("S10", "S12", "S14"):
    PARTIES_PAR_SEQ[s] = [1, 2]

# ── Matrices de séances par série (Q4 : seules les présentes) ────────────────
# { seq: { partie: { 'TB': {serie: nb}, 'S': {serie: nb} } } }
MATRICES = {
    "S01": {1: {"TB": {"R": 1.0, "F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"R": 1.5, "F": 2.5, "A": 3.0}}},
    "S02": {1: {"TB": {"R": 0.5, "F": 0.5, "A": 1.5, "E": 1.5},
                "S":  {"R": 1.0, "F": 1.5, "A": 1.5}}},
    "S03": {1: {"TB": {"R": 1.0, "F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"R": 1.5, "F": 2.5, "A": 3.0}}},
    "S07": {1: {"TB": {"R": 1.0, "F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"R": 1.5, "F": 2.5, "A": 3.0}}},
    "S08": {1: {"TB": {"R": 1.5, "F": 2.0, "A": 3.0, "E": 3.5},
                "S":  {"R": 2.5, "F": 3.5, "A": 4.0}}},
    "S11": {1: {"TB": {"R": 1.0, "F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"R": 1.5, "F": 2.5, "A": 3.0}}},
    "S12": {1: {"TB": {"R": 1.0, "F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"R": 1.5, "F": 2.5, "A": 3.0}},
            2: {"TB": {"R": 1.0, "F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"R": 1.5, "F": 2.5, "A": 3.0}}},
    "S14": {1: {"TB": {"R": 0.5, "F": 1.0, "A": 1.0, "E": 1.5},
                "S":  {"R": 1.0, "F": 1.5, "A": 1.5}}},
}

# ── Créneaux : ordre + dates + période + libellé de partie ──────────────────
# (code, partie, date_debut ISO, date_fin ISO, periode, libelle)
# Dates des plans autoritaires ; périodes dérivées des dates.
CRENEAUX = [
    ("S14", 1, "2021-09-06", "2021-09-10", "T1", "1ère partie : algorithmique débranchée"),
    ("S03", 1, "2021-09-13", "2021-09-24", "T1", ""),
    ("S12", 1, "2021-09-27", "2021-10-08", "T1", "1ère partie : angles"),
    ("S08", 1, "2021-10-11", "2021-11-09", "T1", ""),
    ("S01", 1, "2021-11-15", "2021-11-26", "T1", ""),
    ("S11", 1, "2021-11-29", "2021-12-10", "T2", ""),
    ("S02", 1, "2021-12-13", "2021-12-17", "T2", ""),
    ("S12", 2, "2022-01-03", "2022-01-14", "T2", "2ème partie : triangles et parallélogrammes"),
    ("S07", 1, "2022-01-17", "2022-01-28", "T2", ""),
    ("S04", 1, "2022-01-31", "2022-02-23", "T2", ""),
    ("S10", 1, "2022-02-28", "2022-03-11", "T2", "1ère partie : longueurs et aires"),
    ("S05", 1, "2022-03-14", "2022-03-25", "T3", ""),
    ("S14", 2, "2022-03-28", "2022-04-08", "T3", "2ème partie : programmation"),
    ("S06", 1, "2022-04-25", "2022-05-06", "T3", ""),
    ("S10", 2, "2022-05-09", "2022-05-20", "T3", "2ème partie : volumes et durées"),
    ("S09", 1, "2022-05-23", "2022-05-30", "T3", ""),
    ("S13", 1, "2022-05-31", "2022-06-17", "T3", ""),
]


def _chemin_db_par_defaut() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "seqenseigne.db"


def _verifier_prerequis(conn) -> list[str]:
    pbs = []
    if not conn.execute("SELECT 1 FROM referentiel_niveaux WHERE id=?",
                        (REF_ID,)).fetchone():
        pbs.append(f"référentiel {REF_ID} introuvable")
    if not conn.execute("SELECT 1 FROM progressions WHERE id=?",
                        (PROG_ID,)).fetchone():
        pbs.append(f"progression {PROG_ID} introuvable")
    if not conn.execute("SELECT 1 FROM classes WHERE id=?",
                        (CLASSE,)).fetchone():
        pbs.append(f"classe {CLASSE} introuvable")
    cols = {c[1] for c in conn.execute(
        "PRAGMA table_info(referentiel_niveaux)").fetchall()}
    if "mode_seances" not in cols:
        pbs.append("colonne mode_seances absente (déployer v0.19.1.4)")
    if not conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name='referentiel_parties_seances'").fetchone():
        pbs.append("table referentiel_parties_seances absente (v0.19.1.4)")
    # Créneaux existants attendus (sauf S10 P2 qui sera créé)
    for (seq, part), cid in CRENEAU.items():
        if (seq, part) == ("S10", 2):
            continue
        if not conn.execute(
                "SELECT 1 FROM creneaux WHERE id=? AND progression_id=? "
                "AND seq_code=? AND partie_debut=?",
                (cid, PROG_ID, seq, part)).fetchone():
            pbs.append(f"créneau {seq} P{part} ({cid}) introuvable")
    return pbs


def _id_creneau_s10_p2(conn) -> str:
    """ID du créneau S10 P2 : réutilise celui déjà présent s'il existe
    (idempotence), sinon en génère un nouveau."""
    r = conn.execute(
        "SELECT id FROM creneaux WHERE progression_id=? AND seq_code='S10' "
        "AND partie_debut=2", (PROG_ID,)).fetchone()
    return r["id"] if r else nouveau_id_creneau()


def _appliquer(conn, journal: list[str]) -> None:
    # 1. Mode + parties ------------------------------------------------------
    conn.execute("UPDATE referentiel_niveaux SET mode_seances='par_serie' "
                 "WHERE id=?", (REF_ID,))
    journal.append(f"mode_seances = 'par_serie' ({REF_ID})")

    conn.execute("DELETE FROM referentiel_parties WHERE referentiel_id=?",
                 (REF_ID,))
    seqs_presentes = {r[0] for r in conn.execute(
        "SELECT code FROM referentiel_sequences WHERE referentiel_id=?",
        (REF_ID,)).fetchall()}
    n_parties = 0
    for seq, parties in PARTIES_PAR_SEQ.items():
        if seq not in seqs_presentes:
            continue
        for p in parties:
            conn.execute(
                "INSERT INTO referentiel_parties "
                "(referentiel_id, seq_code, numero, nb_seances_R_AE) "
                "VALUES (?,?,?,0)", (REF_ID, seq, p))
            n_parties += 1
    journal.append(f"referentiel_parties : {n_parties} parties "
                   "(S10, S12, S14 → 2)")

    # partie_numero des objectifs des séquences scindées
    for seq, parts in DECOUPAGE.items():
        for pnum, codes in parts.items():
            for code in codes:
                conn.execute(
                    "UPDATE referentiel_objectifs SET partie_numero=? "
                    "WHERE referentiel_id=? AND seq_code=? AND code=?",
                    (pnum, REF_ID, seq, code))
    journal.append("referentiel_objectifs.partie_numero : "
                   "S10 {01,04,05,07}/{02,03,06,08} ; "
                   "S12 {01,04}/{02,03} ; S14 {01,02}/{03,04}")

    # 2. Matrices de séances par série ---------------------------------------
    conn.execute("DELETE FROM referentiel_parties_seances WHERE referentiel_id=?",
                 (REF_ID,))
    n_cells = 0
    for seq, parts in MATRICES.items():
        for pnum, cibles in parts.items():
            for cible, series in cibles.items():
                for serie, nb in series.items():
                    conn.execute(
                        "INSERT INTO referentiel_parties_seances "
                        "(referentiel_id, seq_code, partie_numero, "
                        " niveau_cible, serie, nb_seances) VALUES (?,?,?,?,?,?)",
                        (REF_ID, seq, pnum, cible, serie, nb))
                    n_cells += 1
    journal.append(f"referentiel_parties_seances : {n_cells} cellules "
                   f"({len(MATRICES)} séquences avec matrice)")

    # 3. Créneaux : créer S10 P2 puis corriger tout en place -----------------
    id_s10_p2 = _id_creneau_s10_p2(conn)
    if not conn.execute("SELECT 1 FROM creneaux WHERE id=?",
                        (id_s10_p2,)).fetchone():
        conn.execute(
            "INSERT INTO creneaux (id, progression_id, seq_code, partie_debut,"
            " partie_fin, partie, periode, date_debut, date_fin, revisions, "
            " ordre) VALUES (?,?, 'S10', 2, 2, '', 'T3', NULL, NULL, '', 0)",
            (id_s10_p2, PROG_ID))
        journal.append(f"creneaux : créneau S10 P2 créé ({id_s10_p2})")
    else:
        journal.append(f"creneaux : créneau S10 P2 déjà présent ({id_s10_p2})")
    CRENEAU[("S10", 2)] = id_s10_p2

    n_maj = 0
    for ordre, (seq, part, deb, fin, per, lib) in enumerate(CRENEAUX, start=1):
        cur = conn.execute(
            "UPDATE creneaux SET ordre=?, date_debut=?, date_fin=?, periode=?, "
            "partie=?, partie_debut=?, partie_fin=? "
            "WHERE progression_id=? AND seq_code=? AND partie_debut=?",
            (ordre, deb, fin, per, lib, part, part, PROG_ID, seq, part))
        if cur.rowcount == 0:
            journal.append(f"  ⚠ créneau {seq} P{part} non trouvé")
        else:
            n_maj += cur.rowcount
    journal.append(f"creneaux : {n_maj} créneaux mis à jour "
                   "(ordre/dates/période/libellé), IDs préservés")

    # 4. Suivi : redistribuer vers les parties 2 -----------------------------
    n_suivi = 0
    deplacements = [
        ("S12", CRENEAU[("S12", 1)], CRENEAU[("S12", 2)], DECOUPAGE["S12"][2]),
        ("S14", CRENEAU[("S14", 1)], CRENEAU[("S14", 2)], DECOUPAGE["S14"][2]),
        ("S10", CRENEAU[("S10", 1)], CRENEAU[("S10", 2)], DECOUPAGE["S10"][2]),
    ]
    for seq, cr_src, cr_dst, objs in deplacements:
        ph = ",".join("?" * len(objs))
        cur = conn.execute(
            f"UPDATE niveaux SET creneau_id=? "
            f"WHERE classe_id=? AND seq_code=? AND creneau_id=? "
            f"AND obj_code IN ({ph})",
            (cr_dst, CLASSE, seq, cr_src, *objs))
        n_suivi += cur.rowcount
    journal.append(f"niveaux : {n_suivi} lignes de suivi déplacées vers les "
                   "parties 2 (S10, S12, S14)")


def _verifier_apres(conn) -> list[str]:
    pbs = []
    mode = conn.execute("SELECT mode_seances FROM referentiel_niveaux WHERE id=?",
                        (REF_ID,)).fetchone()[0]
    if mode != "par_serie":
        pbs.append(f"mode_seances = {mode!r}")
    for seq in ("S10", "S12", "S14"):
        n = conn.execute("SELECT COUNT(*) FROM referentiel_parties "
                         "WHERE referentiel_id=? AND seq_code=?",
                         (REF_ID, seq)).fetchone()[0]
        if n != 2:
            pbs.append(f"{seq} devrait avoir 2 parties, trouvé {n}")
    # Découpage S10 P2
    p2 = {r[0] for r in conn.execute(
        "SELECT code FROM referentiel_objectifs WHERE referentiel_id=? "
        "AND seq_code='S10' AND partie_numero=2", (REF_ID,)).fetchall()}
    if p2 != set(DECOUPAGE["S10"][2]):
        pbs.append(f"S10 P2 = {sorted(p2)}, attendu {list(DECOUPAGE['S10'][2])}")
    # Créneau S10 P2 existe + daté
    r = conn.execute("SELECT date_fin FROM creneaux WHERE progression_id=? "
                     "AND seq_code='S10' AND partie_debut=2", (PROG_ID,)).fetchone()
    if not r or not r["date_fin"]:
        pbs.append("créneau S10 P2 absent ou non daté")
    # Créneaux datés (17 attendus)
    nd = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
                      "AND date_fin IS NOT NULL", (PROG_ID,)).fetchone()[0]
    if nd < len(CRENEAUX):
        pbs.append(f"{nd} créneaux datés, attendu {len(CRENEAUX)}")
    # Suivi S10 P2 présent
    cr_p2 = conn.execute("SELECT id FROM creneaux WHERE progression_id=? "
                         "AND seq_code='S10' AND partie_debut=2",
                         (PROG_ID,)).fetchone()
    if cr_p2:
        n10 = conn.execute(
            "SELECT COUNT(*) FROM niveaux WHERE classe_id=? AND seq_code='S10' "
            "AND creneau_id=? AND obj_code IN (?,?,?,?)",
            (CLASSE, cr_p2["id"], *DECOUPAGE["S10"][2])).fetchone()[0]
        if n10 == 0:
            pbs.append("aucun suivi S10 obj P2 sur le créneau partie 2")
    return pbs


def _etat(conn) -> str:
    mode = conn.execute("SELECT mode_seances FROM referentiel_niveaux WHERE id=?",
                        (REF_ID,)).fetchone()
    np = conn.execute("SELECT COUNT(*) FROM referentiel_parties WHERE referentiel_id=?",
                      (REF_ID,)).fetchone()[0]
    nc = conn.execute("SELECT COUNT(*) FROM referentiel_parties_seances "
                      "WHERE referentiel_id=?", (REF_ID,)).fetchone()[0]
    ncr = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=?",
                       (PROG_ID,)).fetchone()[0]
    nd = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
                      "AND date_fin IS NOT NULL", (PROG_ID,)).fetchone()[0]
    s10p2 = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
                         "AND seq_code='S10' AND partie_debut=2",
                         (PROG_ID,)).fetchone()[0]
    return (f"  mode_seances({REF_ID}) = {mode[0] if mode else '—'!r}\n"
            f"  referentiel_parties = {np} ; parties_seances = {nc} cellules\n"
            f"  créneaux = {ncr} (dont datés {nd}/{len(CRENEAUX)}) ; "
            f"S10 P2 présent = {'oui' if s10p2 else 'non'}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=_chemin_db_par_defaut())
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    if not args.db.exists():
        print(f"[import 5e2] base introuvable : {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        pbs = _verifier_prerequis(conn)
        if pbs:
            print("[import 5e2] prérequis non satisfaits :")
            for p in pbs:
                print(f"  ✗ {p}")
            return 3

        print("[import 5e2] ── État AVANT ──")
        print(_etat(conn))

        journal: list[str] = []
        conn.execute("BEGIN")
        _appliquer(conn, journal)

        print("\n[import 5e2] ── Opérations ──")
        for l in journal:
            print(f"  • {l}")

        verifs = _verifier_apres(conn)
        if verifs:
            print("\n[import 5e2] ✗ vérification post-import échouée :")
            for v in verifs:
                print(f"  ✗ {v}")
            conn.rollback()
            print("[import 5e2] rollback — aucune modification.")
            return 3

        if not args.apply:
            conn.rollback()
            print("\n[import 5e2] DRY-RUN : modifications annulées "
                  "(rejouer avec --apply pour appliquer).")
            return 0

        if not args.yes:
            rep = input("\n[import 5e2] Appliquer définitivement ? "
                        "Tapez 'OUI' : ").strip()
            if rep != "OUI":
                conn.rollback()
                print("[import 5e2] annulé.")
                return 1

        conn.commit()
        print("\n[import 5e2] ── État APRÈS ──")
        print(_etat(conn))
        print("\n[import 5e2] ✓ import appliqué. 🎉")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"[import 5e2] erreur : {e}", file=sys.stderr)
        return 3
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
