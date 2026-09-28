#!/usr/bin/env python3
"""outils/import_historique_3e3_2022.py — v0.19.1.10

Import « ad hoc » de la structure historique de la progression 3ᵉ3 2022-23
(Collège des Hautes Ourmes). Même principe que l'import 5e2 2022-23 (mode
`par_objectif`). Valeurs figées, lues des fichiers les plus récents.

Cible :
  - référentiel  : N12_v2022  (verrouillé)
  - progression  : pg_ed218842 (2022-2023, Hautes Ourmes)
  - classes      : cl_9ee1805d (3E3) ET cl_3fbda8f5 (3E8) — progression
                   partagée.

Spécificités vs 5e2 2022-23 :
  - TROIS séquences scindées en 2 parties : S05, S09, S12.
  - Les créneaux des deux parties EXISTENT DÉJÀ pour les trois (S05 P1/P2,
    S09 P1/P2, S12 P1/P2) → AUCUNE création ni suppression de créneau, on
    corrige tout en place.
  - Le niveau N12 a des créneaux DC1/DC2/DC3 (devoirs communs) : HORS PÉRIMÈTRE
    (comme les bilans) — on n'y touche pas.
  - S13 n'a pas de plan dans les archives → aucune séance récupérable pour
    S13 (reste à 0).

Opérations (transaction unique) :

  1. RÉFÉRENTIEL — parties (mode reste 'par_objectif')
     - referentiel_parties : S05→2, S09→2, S12→2 ; autres → 1
     - referentiel_objectifs.partie_numero :
         S05 P1={01,02} P2={03,04,05}
         S09 P1={01,02,03} P2={04,05,06}
         S12 P1={01,02,03} P2={04,05}

  2. RÉFÉRENTIEL — séances par objectif (présentation → obj 01 ;
     auto-évaluation → nb_seances_R_AE de la partie).

  3. PROGRESSION — créneaux corrigés EN PLACE (IDs préservés) :
     ordre/dates/période/libellés de partie pour S05/S09/S12. DC1/DC2/DC3 et
     bilans non touchés.

  4. SUIVI — redistribution des objectifs de partie 2 vers le créneau P2
     (les deux classes) :
       S05 : {03,04,05} → P2
       S09 : {04,05,06} → P2
       S12 : {04,05}    → P2

  Hors périmètre : bilans, devoirs communs.

Sécurités : dry-run par défaut ; --apply + 'OUI' (ou --yes) ; idempotent ;
transaction unique ; vérification post-import.

Usage :
    python -m outils.import_historique_3e3_2022            # dry-run
    python -m outils.import_historique_3e3_2022 --apply
    python -m outils.import_historique_3e3_2022 --apply --yes

Codes de sortie : 0 succès, 1 annulé, 2 base introuvable, 3 erreur.
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

REF_ID = "N12_v2022"
PROG_ID = "pg_ed218842"
CLASSES = ("cl_9ee1805d", "cl_3fbda8f5")  # 3E3, 3E8

# Créneaux existants des séquences scindées (audit base) — tous présents.
CRENEAU = {
    ("S05", 1): "cr_fe003016", ("S05", 2): "cr_709979f8",
    ("S09", 1): "cr_d8ef4c6b", ("S09", 2): "cr_d1686c15",
    ("S12", 1): "cr_e26b61f2", ("S12", 2): "cr_cbbb5346",
}

DECOUPAGE = {
    "S05": {1: ("01", "02"),       2: ("03", "04", "05")},
    "S09": {1: ("01", "02", "03"), 2: ("04", "05", "06")},
    "S12": {1: ("01", "02", "03"), 2: ("04", "05")},
}

PARTIES_PAR_SEQ = {f"S{n:02d}": [1] for n in range(1, 15)}
for s in ("S05", "S09", "S12"):
    PARTIES_PAR_SEQ[s] = [1, 2]

# Séances par objectif (présentation → obj 01). S13 absent (pas de plan).
NB_SEANCES_OBJ = {
    "S01": {"01": 1, "02": 2, "03": 2},
    "S02": {"01": 0, "02": 3},
    "S03": {"01": 0, "02": 5},
    "S04": {"01": 1, "02": 1, "03": 2},
    "S05": {"01": 0, "02": 3, "03": 1, "04": 1, "05": 2},
    "S06": {"01": 1, "02": 2, "03": 0, "04": 2},
    "S07": {"01": 1, "02": 2, "03": 1, "04": 2},
    "S08": {"01": 0, "02": 1, "03": 1, "04": 2},
    "S09": {"01": 1, "02": 1, "03": 1, "04": 2, "05": 2, "06": 2},
    "S10": {"01": 1, "02": 1, "03": 3},
    "S11": {"01": 1, "02": 1, "03": 1, "04": 0, "05": 0, "06": 2},
    "S12": {"01": 1, "02": 2, "03": 2, "04": 3, "05": 1},
    # S13 : pas de plan dans les archives → aucune séance.
    "S14": {"01": 1, "02": 2, "03": 2, "04": 2},
}

# Auto-évaluation par (séquence, partie) → nb_seances_R_AE.
NB_RAE = {
    ("S01", 1): 1, ("S02", 1): 0, ("S03", 1): 0, ("S04", 1): 1,
    ("S06", 1): 0, ("S07", 1): 1, ("S08", 1): 0, ("S10", 1): 1,
    ("S11", 1): 1, ("S14", 1): 1,
    ("S05", 1): 0, ("S05", 2): 1,
    ("S09", 1): 1,  # S09 P2 sans auto-éval → 0 (défaut)
    ("S12", 1): 2, ("S12", 2): 0,
}

# Créneaux : (code, partie, date_debut, date_fin, periode, libelle)
CRENEAUX = [
    ("S01", 1, "2022-09-05", "2022-09-16", "T1", ""),
    ("S12", 1, "2022-09-19", "2022-09-30", "T1", "1ère partie : théorème de Thalès"),
    ("S09", 1, "2022-10-03", "2022-10-07", "T1", "1ère partie : notion de fonction"),
    ("S08", 1, "2022-10-10", "2022-10-21", "T1", ""),
    ("S05", 1, "2022-10-24", "2022-11-17", "T1", "1ère partie : double distributivité"),
    ("S02", 1, "2022-11-18", "2022-11-25", "T2", ""),
    ("S09", 2, "2022-11-28", "2022-12-09", "T2", "2ème partie : fonctions linéaires et affines"),
    ("S03", 1, "2022-12-12", "2023-01-06", "T2", ""),
    ("S07", 1, "2023-01-09", "2023-01-20", "T2", ""),
    ("S04", 1, "2023-01-23", "2023-02-01", "T2", ""),
    ("S10", 1, "2023-02-02", "2023-03-03", "T3", ""),
    ("S05", 2, "2023-03-06", "2023-03-10", "T3", "2ème partie : équations"),
    ("S14", 1, "2023-03-13", "2023-03-24", "T3", ""),
    ("S06", 1, "2023-03-27", "2023-04-07", "T3", ""),
    ("S12", 2, "2023-04-10", "2023-05-10", "T3", "2ème partie : trigonométrie"),
    ("S11", 1, "2023-05-11", "2023-06-02", "T3", ""),
    ("S13", 1, "2023-06-05", "2023-06-16", "T3", ""),
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
    for cl in CLASSES:
        if not conn.execute("SELECT 1 FROM classes WHERE id=?", (cl,)).fetchone():
            pbs.append(f"classe {cl} introuvable")
    cols = {c[1] for c in conn.execute(
        "PRAGMA table_info(referentiel_niveaux)").fetchall()}
    if "mode_seances" not in cols:
        pbs.append("colonne mode_seances absente (déployer v0.19.1.4)")
    for (seq, part), cid in CRENEAU.items():
        if not conn.execute(
                "SELECT 1 FROM creneaux WHERE id=? AND progression_id=? "
                "AND seq_code=? AND partie_debut=?",
                (cid, PROG_ID, seq, part)).fetchone():
            pbs.append(f"créneau {seq} P{part} ({cid}) introuvable")
    return pbs


def _appliquer(conn, journal: list[str]) -> None:
    # 1. Mode (par_objectif) + parties ---------------------------------------
    conn.execute("UPDATE referentiel_niveaux SET mode_seances='par_objectif' "
                 "WHERE id=?", (REF_ID,))
    journal.append(f"mode_seances = 'par_objectif' ({REF_ID})")

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
                "VALUES (?,?,?,?)", (REF_ID, seq, p, NB_RAE.get((seq, p), 0)))
            n_parties += 1
    journal.append(f"referentiel_parties : {n_parties} parties "
                   "(S05, S09, S12 → 2) + nb_seances_R_AE")

    for seq, parts in DECOUPAGE.items():
        for pnum, codes in parts.items():
            for code in codes:
                conn.execute(
                    "UPDATE referentiel_objectifs SET partie_numero=? "
                    "WHERE referentiel_id=? AND seq_code=? AND code=?",
                    (pnum, REF_ID, seq, code))
    journal.append("referentiel_objectifs.partie_numero : "
                   "S05 {01,02}/{03,04,05} ; S09 {01,02,03}/{04,05,06} ; "
                   "S12 {01,02,03}/{04,05}")

    # 2. nb_seances par objectif ---------------------------------------------
    n_obj = 0
    for seq, objs in NB_SEANCES_OBJ.items():
        for code, nb in objs.items():
            cur = conn.execute(
                "UPDATE referentiel_objectifs SET nb_seances=? "
                "WHERE referentiel_id=? AND seq_code=? AND code=?",
                (nb, REF_ID, seq, code))
            n_obj += cur.rowcount
    journal.append(f"referentiel_objectifs.nb_seances : {n_obj} objectifs "
                   "renseignés (présentation → obj 01)")

    # 3. Créneaux corrigés en place ------------------------------------------
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
                   "(ordre/dates/période/libellé), IDs préservés ; "
                   "DC1/DC2/DC3 et bilans non touchés")

    # 4. Suivi : redistribuer vers parties 2 (les 2 classes) -----------------
    n_suivi = 0
    deplacements = [
        ("S05", CRENEAU[("S05", 1)], CRENEAU[("S05", 2)], DECOUPAGE["S05"][2]),
        ("S09", CRENEAU[("S09", 1)], CRENEAU[("S09", 2)], DECOUPAGE["S09"][2]),
        ("S12", CRENEAU[("S12", 1)], CRENEAU[("S12", 2)], DECOUPAGE["S12"][2]),
    ]
    for cl in CLASSES:
        for seq, cr_src, cr_dst, objs in deplacements:
            ph = ",".join("?" * len(objs))
            cur = conn.execute(
                f"UPDATE niveaux SET creneau_id=? "
                f"WHERE classe_id=? AND seq_code=? AND creneau_id=? "
                f"AND obj_code IN ({ph})",
                (cr_dst, cl, seq, cr_src, *objs))
            n_suivi += cur.rowcount
    journal.append(f"niveaux : {n_suivi} lignes de suivi déplacées vers les "
                   "parties 2 (S05, S09, S12 ; 2 classes)")


def _verifier_apres(conn) -> list[str]:
    pbs = []
    for seq in ("S05", "S09", "S12"):
        k = conn.execute("SELECT COUNT(*) FROM referentiel_parties "
                         "WHERE referentiel_id=? AND seq_code=?",
                         (REF_ID, seq)).fetchone()[0]
        if k != 2:
            pbs.append(f"{seq} devrait avoir 2 parties, trouvé {k}")
    # Découpage S09 P2
    p2 = {x[0] for x in conn.execute(
        "SELECT code FROM referentiel_objectifs WHERE referentiel_id=? "
        "AND seq_code='S09' AND partie_numero=2", (REF_ID,)).fetchall()}
    if p2 != set(DECOUPAGE["S09"][2]):
        pbs.append(f"S09 P2 = {sorted(p2)}, attendu {list(DECOUPAGE['S09'][2])}")
    nd = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
                      "AND date_fin IS NOT NULL", (PROG_ID,)).fetchone()[0]
    if nd < len(CRENEAUX):
        pbs.append(f"{nd} créneaux datés, attendu ≥ {len(CRENEAUX)}")
    # Suivi S09 P2
    n_p2 = conn.execute(
        "SELECT COUNT(*) FROM niveaux WHERE classe_id IN (?,?) "
        "AND seq_code='S09' AND creneau_id=? AND obj_code IN (?,?,?)",
        (*CLASSES, CRENEAU[("S09", 2)], *DECOUPAGE["S09"][2])).fetchone()[0]
    if n_p2 == 0:
        pbs.append("aucun suivi S09 obj P2 sur le créneau partie 2")
    # DC non touchés (toujours présents, sans date)
    ndc = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
                       "AND seq_code LIKE 'DC%'", (PROG_ID,)).fetchone()[0]
    if ndc != 3:
        pbs.append(f"DC1/DC2/DC3 : {ndc} trouvés (attendu 3, ne pas toucher)")
    return pbs


def _etat(conn) -> str:
    mode = conn.execute("SELECT mode_seances FROM referentiel_niveaux WHERE id=?",
                        (REF_ID,)).fetchone()
    np = conn.execute("SELECT COUNT(*) FROM referentiel_parties WHERE referentiel_id=?",
                      (REF_ID,)).fetchone()[0]
    nobj = conn.execute("SELECT COUNT(*) FROM referentiel_objectifs "
                        "WHERE referentiel_id=? AND nb_seances>0",
                        (REF_ID,)).fetchone()[0]
    nd = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
                      "AND date_fin IS NOT NULL AND seq_code NOT LIKE 'DC%'",
                      (PROG_ID,)).fetchone()[0]
    return (f"  mode_seances({REF_ID}) = {mode[0] if mode else '—'!r}\n"
            f"  referentiel_parties = {np} ; objectifs avec nb_seances>0 = {nobj}\n"
            f"  créneaux séquences datés = {nd}/{len(CRENEAUX)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=_chemin_db_par_defaut())
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    if not args.db.exists():
        print(f"[import 3e3-2022] base introuvable : {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        pbs = _verifier_prerequis(conn)
        if pbs:
            print("[import 3e3-2022] prérequis non satisfaits :")
            for p in pbs:
                print(f"  ✗ {p}")
            return 3

        print("[import 3e3-2022] ── État AVANT ──")
        print(_etat(conn))

        journal: list[str] = []
        conn.execute("BEGIN")
        _appliquer(conn, journal)

        print("\n[import 3e3-2022] ── Opérations ──")
        for l in journal:
            print(f"  • {l}")

        verifs = _verifier_apres(conn)
        if verifs:
            print("\n[import 3e3-2022] ✗ vérification post-import échouée :")
            for v in verifs:
                print(f"  ✗ {v}")
            conn.rollback()
            print("[import 3e3-2022] rollback — aucune modification.")
            return 3

        if not args.apply:
            conn.rollback()
            print("\n[import 3e3-2022] DRY-RUN : modifications annulées "
                  "(rejouer avec --apply pour appliquer).")
            return 0

        if not args.yes:
            rep = input("\n[import 3e3-2022] Appliquer définitivement ? "
                        "Tapez 'OUI' : ").strip()
            if rep != "OUI":
                conn.rollback()
                print("[import 3e3-2022] annulé.")
                return 1

        conn.commit()
        print("\n[import 3e3-2022] ── État APRÈS ──")
        print(_etat(conn))
        print("\n[import 3e3-2022] ✓ import appliqué. 🎉")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"[import 3e3-2022] erreur : {e}", file=sys.stderr)
        return 3
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
