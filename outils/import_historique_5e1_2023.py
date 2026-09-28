#!/usr/bin/env python3
"""outils/import_historique_5e1_2023.py — v0.19.1.13

Import « ad hoc » de la structure historique de la progression 5ᵉ1 2023-24
(Collège des Hautes Ourmes). Mode `par_objectif`.

Cible :
  - référentiel  : N10_v2023  (état `en_cours` — voir note ci-dessous)
  - progression  : pg_ceb1735e (2023-2024, Hautes Ourmes)
  - classes      : cl_2e1073a8 (5e1) ET cl_58d60527 (5e3) — progression
                   partagée.

Particularités 2023-24 (différences avec les imports précédents) :

  - **Référentiel `en_cours`, pas `verrouille`.** Il avait été déverrouillé
    manuellement pour le repasser `utilise`, mais le déverrouillage a re-lié la
    structure de parties au modèle actif (2025) au lieu de 2023. La structure
    des objectifs (codes + noms) est néanmoins restée intacte (vérifié vs ZIP
    2023). Ce script REFIGE les parties directement depuis les codes
    d'objectifs 2023 (sans repasser par `peupler_snapshot_parties`, qui lirait
    le modèle actif 2025), puis force l'état à `utilise`.

  - **Découpage objectif → partie déduit des CODES** : en 2023-24, les codes
    encodent la partie (0x → P1, 1x → P2, 2x → P3 ; 01/11/21 = cours de
    chaque partie). Aucun découpage manuel n'est nécessaire.

  - **Suivi déjà réparti par partie** (codes par partie saisis directement) :
    AUCUNE redistribution de suivi n'est nécessaire (contrairement aux années
    précédentes).

  - **Semestres** : périodes `Sem1` / `Sem2` (et non T1/T2/T3).

Opérations (transaction unique) :

  1. RÉFÉRENTIEL — parties (mode `par_objectif`) : S10→2, S12→3, S14→2 ;
     autres → 1. `partie_numero` de CHAQUE objectif déduit de son code
     (0x→1, 1x→2, 2x→3). `nb_seances_R_AE` depuis les plans (« Révision »).
  2. RÉFÉRENTIEL — `nb_seances` par objectif depuis les plans (présentation →
     cours de la partie 01/11/21). Pour S12, remapping des codes locaux des
     plans (03→12, 04→22, 05→23). Valeurs décimales conservées.
  3. PROGRESSION — créneaux corrigés EN PLACE (IDs préservés) :
     ordre/dates/période Sem1-Sem2/libellés de partie pour S10/S12/S14.
  4. ÉTAT — force `N10_v2023` à `utilise` (référigeage fait, progression liée).

Pas de redistribution de suivi (déjà correct). Hors périmètre : bilans.

Sécurités : dry-run par défaut ; --apply + 'OUI' (ou --yes) ; idempotent ;
transaction unique ; vérification post-import.

Usage :
    python -m outils.import_historique_5e1_2023            # dry-run
    python -m outils.import_historique_5e1_2023 --apply
    python -m outils.import_historique_5e1_2023 --apply --yes

Codes de sortie : 0 succès, 1 annulé, 2 base introuvable, 3 erreur.
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

REF_ID = "N10_v2023"
PROG_ID = "pg_ceb1735e"
CLASSES = ("cl_2e1073a8", "cl_58d60527")  # 5e1, 5e3

# Séquences scindées et nombre de parties.
PARTIES_PAR_SEQ = {f"S{n:02d}": [1] for n in range(1, 15)}
PARTIES_PAR_SEQ["S10"] = [1, 2]
PARTIES_PAR_SEQ["S12"] = [1, 2, 3]
PARTIES_PAR_SEQ["S14"] = [1, 2]

# nb_seances par objectif (codes BASE ; mapping S12 déjà appliqué).
NB_SEANCES_OBJ = {
    "S01": {"01": 1, "02": 1, "03": 1, "04": 1, "05": 1},
    "S02": {"01": 0.5, "02": 1, "03": 1, "04": 1},
    "S03": {"01": 1, "02": 1, "03": 1, "04": 1, "05": 1, "06": 1},
    "S04": {"01": 1.5, "02": 1, "03": 2, "04": 1},
    "S05": {"01": 3, "02": 1, "03": 1, "04": 1, "05": 1},
    "S06": {"01": 0.5},
    "S07": {"01": 2.5, "02": 1.5, "03": 3},
    "S08": {"01": 0.5, "02": 1, "03": 1.5, "04": 1, "05": 1, "06": 1},
    "S09": {},
    "S10": {"01": 1, "02": 1, "03": 2},  # exos P2 (12-16) non renseignés (pas de plan_2)
    "S11": {"01": 1, "02": 1, "03": 1, "04": 1, "05": 1, "06": 1},
    "S12": {"01": 2, "02": 1.5, "11": 3, "12": 3, "21": 0.5, "22": 1.5, "23": 1},
    "S13": {"01": 1},
    "S14": {"01": 1, "02": 2, "11": 1, "12": 2, "13": 2},
}

# nb_seances_R_AE par (séquence, partie), depuis « Révision » des plans.
NB_RAE = {
    ("S01", 1): 2, ("S02", 1): 0.5, ("S03", 1): 1, ("S04", 1): 0.5,
    ("S06", 1): 1.5, ("S07", 1): 1, ("S08", 1): 1, ("S10", 1): 3,
    ("S11", 1): 1, ("S13", 1): 1,
    ("S12", 1): 3.5, ("S12", 2): 1, ("S12", 3): 1,
    ("S14", 1): 1, ("S14", 2): 2,
    # S05, S09 : pas de « Révision » dans leur plan → 0 (défaut).
}

# Créneaux : (code, partie, date_debut, date_fin, periode, libelle)
CRENEAUX = [
    ("S14", 1, "2023-09-04", "2023-09-15", "Sem1", "1ère partie : algorithmique débranchée"),
    ("S01", 1, "2023-09-18", "2023-09-29", "Sem1", ""),
    ("S12", 1, "2023-10-02", "2023-10-13", "Sem1", "1ère partie : angles"),
    ("S08", 1, "2023-10-16", "2023-11-10", "Sem1", ""),
    ("S02", 1, "2023-11-13", "2023-11-17", "Sem1", ""),
    ("S11", 1, "2023-11-20", "2023-12-01", "Sem1", ""),
    ("S03", 1, "2023-12-04", "2023-12-15", "Sem1", ""),
    ("S12", 2, "2023-12-18", "2024-01-12", "Sem1", "2ème partie : triangles"),
    ("S07", 1, "2024-01-15", "2024-01-26", "Sem2", ""),
    ("S04", 1, "2024-01-29", "2024-02-09", "Sem2", ""),
    ("S10", 1, "2024-02-12", "2024-02-23", "Sem2", "1ère partie : longueurs et aires"),
    ("S05", 1, "2024-02-26", "2024-03-22", "Sem2", ""),
    ("S14", 2, "2024-03-25", "2024-04-05", "Sem2", "2ème partie : programmation"),
    ("S12", 3, "2024-04-08", "2024-04-19", "Sem2", "3ème partie : parallélogrammes"),
    ("S06", 1, "2024-04-22", "2024-05-17", "Sem2", ""),
    ("S13", 1, "2024-05-20", "2024-05-31", "Sem2", ""),
    ("S09", 1, "2024-06-03", "2024-06-14", "Sem2", ""),
    ("S10", 2, "2024-06-17", "2024-06-28", "Sem2", "2ème partie : volumes et durées"),
]


def _chemin_db_par_defaut() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "seqenseigne.db"


def _partie_du_code(code: str) -> int:
    """Déduit le numéro de partie du code d'objectif : 0x→1, 1x→2, 2x→3."""
    try:
        return int(code[0]) + 1
    except (ValueError, IndexError):
        return 1


def _verifier_prerequis(conn) -> list[str]:
    pbs = []
    r = conn.execute("SELECT etat FROM referentiel_niveaux WHERE id=?",
                     (REF_ID,)).fetchone()
    if not r:
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
    # Créneaux des séquences scindées présents
    for seq, parts in (("S10", [1, 2]), ("S12", [1, 2, 3]), ("S14", [1, 2])):
        for p in parts:
            if not conn.execute(
                    "SELECT 1 FROM creneaux WHERE progression_id=? "
                    "AND seq_code=? AND partie_debut=?",
                    (PROG_ID, seq, p)).fetchone():
                pbs.append(f"créneau {seq} P{p} introuvable")
    return pbs


def _appliquer(conn, journal: list[str]) -> None:
    # 1. Mode + parties + partie_numero (déduit des codes) -------------------
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
                   "(S10→2, S12→3, S14→2) + nb_seances_R_AE")

    # partie_numero : déduit du code de CHAQUE objectif des séquences scindées
    n_pn = 0
    for seq in ("S10", "S12", "S14"):
        for (code,) in conn.execute(
                "SELECT code FROM referentiel_objectifs "
                "WHERE referentiel_id=? AND seq_code=?", (REF_ID, seq)).fetchall():
            cur = conn.execute(
                "UPDATE referentiel_objectifs SET partie_numero=? "
                "WHERE referentiel_id=? AND seq_code=? AND code=?",
                (_partie_du_code(code), REF_ID, seq, code))
            n_pn += cur.rowcount
    journal.append(f"referentiel_objectifs.partie_numero : {n_pn} objectifs "
                   "(déduit des codes 0x/1x/2x)")

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
                   "renseignés (présentation → cours de partie)")

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
                   "(ordre/dates/période Sem1-Sem2/libellé), IDs préservés")

    # 4. État : forcer en_cours → utilise (référigeage fait, progression liée)
    cur = conn.execute(
        "UPDATE referentiel_niveaux SET etat='utilise' "
        "WHERE id=? AND etat IN ('en_cours','verrouille')", (REF_ID,))
    journal.append(f"referentiel_niveaux.etat → 'utilise' ({REF_ID}) — "
                   f"{cur.rowcount} ligne")


def _verifier_apres(conn) -> list[str]:
    pbs = []
    etat = conn.execute("SELECT etat FROM referentiel_niveaux WHERE id=?",
                        (REF_ID,)).fetchone()[0]
    if etat != "utilise":
        pbs.append(f"état attendu 'utilise', trouvé {etat!r}")
    for seq, n in (("S10", 2), ("S12", 3), ("S14", 2)):
        k = conn.execute("SELECT COUNT(*) FROM referentiel_parties "
                         "WHERE referentiel_id=? AND seq_code=?",
                         (REF_ID, seq)).fetchone()[0]
        if k != n:
            pbs.append(f"{seq} devrait avoir {n} parties, trouvé {k}")
    # partie_numero cohérent avec les codes (ex. S12 : 11/12→2, 21/22/23→3)
    for code, attendu in (("11", 2), ("12", 2), ("21", 3), ("22", 3), ("23", 3)):
        r = conn.execute("SELECT partie_numero FROM referentiel_objectifs "
                         "WHERE referentiel_id=? AND seq_code='S12' AND code=?",
                         (REF_ID, code)).fetchone()
        if r and r[0] != attendu:
            pbs.append(f"S12 obj {code} : partie_numero={r[0]}, attendu {attendu}")
    nd = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
                      "AND date_fin IS NOT NULL", (PROG_ID,)).fetchone()[0]
    if nd < len(CRENEAUX):
        pbs.append(f"{nd} créneaux datés, attendu {len(CRENEAUX)}")
    return pbs


def _etat(conn) -> str:
    r = conn.execute("SELECT etat, mode_seances FROM referentiel_niveaux "
                     "WHERE id=?", (REF_ID,)).fetchone()
    np = conn.execute("SELECT COUNT(*) FROM referentiel_parties WHERE referentiel_id=?",
                      (REF_ID,)).fetchone()[0]
    nobj = conn.execute("SELECT COUNT(*) FROM referentiel_objectifs "
                        "WHERE referentiel_id=? AND nb_seances>0",
                        (REF_ID,)).fetchone()[0]
    nd = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
                      "AND date_fin IS NOT NULL", (PROG_ID,)).fetchone()[0]
    return (f"  {REF_ID} : etat={r[0]!r} mode={r[1]!r}\n"
            f"  referentiel_parties = {np} ; objectifs avec nb_seances>0 = {nobj}\n"
            f"  créneaux datés = {nd}/{len(CRENEAUX)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=_chemin_db_par_defaut())
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    if not args.db.exists():
        print(f"[import 5e1-2023] base introuvable : {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        pbs = _verifier_prerequis(conn)
        if pbs:
            print("[import 5e1-2023] prérequis non satisfaits :")
            for p in pbs:
                print(f"  ✗ {p}")
            return 3

        print("[import 5e1-2023] ── État AVANT ──")
        print(_etat(conn))

        journal: list[str] = []
        conn.execute("BEGIN")
        _appliquer(conn, journal)

        print("\n[import 5e1-2023] ── Opérations ──")
        for l in journal:
            print(f"  • {l}")

        verifs = _verifier_apres(conn)
        if verifs:
            print("\n[import 5e1-2023] ✗ vérification post-import échouée :")
            for v in verifs:
                print(f"  ✗ {v}")
            conn.rollback()
            print("[import 5e1-2023] rollback — aucune modification.")
            return 3

        if not args.apply:
            conn.rollback()
            print("\n[import 5e1-2023] DRY-RUN : modifications annulées "
                  "(rejouer avec --apply pour appliquer).")
            return 0

        if not args.yes:
            rep = input("\n[import 5e1-2023] Appliquer définitivement ? "
                        "Tapez 'OUI' : ").strip()
            if rep != "OUI":
                conn.rollback()
                print("[import 5e1-2023] annulé.")
                return 1

        conn.commit()
        print("\n[import 5e1-2023] ── État APRÈS ──")
        print(_etat(conn))
        print("\n[import 5e1-2023] ✓ import appliqué. 🎉")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"[import 5e1-2023] erreur : {e}", file=sys.stderr)
        return 3
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
