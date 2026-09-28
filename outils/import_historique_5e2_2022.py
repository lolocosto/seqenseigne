#!/usr/bin/env python3
"""outils/import_historique_5e2_2022.py — v0.19.1.9

Import « ad hoc » de la structure historique de la progression 5ᵉ2 2022-23
(Collège des Hautes Ourmes), à partir du répertoire d'archives de l'époque.
Même principe que les imports 4e3/5e2 2021-22 ; valeurs figées, lues des
fichiers les plus récents.

Cible :
  - référentiel  : N10_v2022  (verrouillé)
  - progression  : pg_c8f8d9e1 (2022-2023, Hautes Ourmes)
  - classes      : cl_5a37f150 (5E2) ET cl_1ab4d097 (5E4) — la progression est
                   partagée par ces deux classes.

DIFFÉRENCES vs les imports 2021-22 :
  - Mode de séances = 'par_objectif' (modèle COURANT, on NE bascule PAS en
    'par_serie'). Les plans 2022-23 donnent les séances par objectif + une
    auto-évaluation par partie, exploitables directement par le modèle natif.
  - TROIS séquences scindées, dont une en TROIS parties : S10 (2), S12 (3),
    S14 (2).
  - RÉCONCILIATION des créneaux existants avec la vérité de la progression :
      * S14 : la base a 3 parties, la progression en veut 2 → SUPPRESSION du
        créneau S14 partie 3 (cr_9d873874, sans aucun suivi — vérifié).
      * S10 : la base a 1 partie, la progression en veut 2 → CRÉATION du
        créneau S10 partie 2.
      * S12 : 3 parties déjà présentes → conservées.

Opérations (transaction unique) :

  1. RÉFÉRENTIEL — parties (mode_seances reste 'par_objectif')
     - referentiel_parties : S10→2, S12→3, S14→2 ; autres → 1
     - referentiel_objectifs.partie_numero :
         S10 P1={01,04,05,07} P2={02,03,06,08}
         S12 P1={01,02} P2={03} P3={04,05}
         S14 P1={01,02} P2={03,04}

  2. RÉFÉRENTIEL — séances par objectif (modèle 'par_objectif')
     - referentiel_objectifs.nb_seances : depuis les « Repères temporels » des
       plans. La « Présentation de la séquence » est rattachée à l'objectif
       « cours » 01 (decision Q-B.a : seule la présentation de la partie où
       vit l'obj 01 est retenue). Un objectif cité dans plusieurs parties est
       compté dans SA partie d'appartenance (decision Q-A).
     - referentiel_parties.nb_seances_R_AE : depuis l'« Auto-évaluation » de
       chaque partie.

  3. PROGRESSION — réconciliation des créneaux (IDs préservés ; le suivi
     `niveaux` y est rattaché)
     - SUPPRIMER le créneau S14 P3 (sans suivi).
     - CRÉER le créneau S10 P2.
     - ordre chronologique, date_debut/date_fin, période T1/T2/T3 (dérivée des
       dates), libellés de partie pour S10/S12/S14.

  4. SUIVI — redistribution sur les parties 2/3 (pour LES DEUX classes)
     - S10 : obj {02,03,06,08} → nouveau créneau S10 P2
     - S12 : obj {03} → P2, obj {04,05} → P3
     - S14 : obj {03,04} → P2

  Hors périmètre : bilans de fin de trimestre et devoirs communs (DC1/DC2/DC3).

Sécurités : dry-run par défaut ; --apply + 'OUI' (ou --yes) ; idempotent ;
transaction unique ; vérification post-import.

Usage :
    python -m outils.import_historique_5e2_2022            # dry-run
    python -m outils.import_historique_5e2_2022 --apply
    python -m outils.import_historique_5e2_2022 --apply --yes

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

REF_ID = "N10_v2022"
PROG_ID = "pg_c8f8d9e1"
CLASSES = ("cl_5a37f150", "cl_1ab4d097")  # 5E2, 5E4

# Créneaux existants des séquences scindées (audit base).
CRENEAU = {
    ("S10", 1): "cr_d2e94526",   # S10 P2 sera créé
    ("S12", 1): "cr_2da17d78",
    ("S12", 2): "cr_492ef0f0",
    ("S12", 3): "cr_8ac7d267",
    ("S14", 1): "cr_40e8095c",
    ("S14", 2): "cr_97942209",
}
# Créneau surnuméraire à supprimer (S14 partie 3, sans suivi — vérifié).
CRENEAU_A_SUPPRIMER = "cr_9d873874"

# Découpage objectif → partie (validé).
DECOUPAGE = {
    "S10": {1: ("01", "04", "05", "07"), 2: ("02", "03", "06", "08")},
    "S12": {1: ("01", "02"), 2: ("03",), 3: ("04", "05")},
    "S14": {1: ("01", "02"), 2: ("03", "04")},
}

# Parties par séquence.
PARTIES_PAR_SEQ = {f"S{n:02d}": [1] for n in range(1, 15)}
PARTIES_PAR_SEQ["S10"] = [1, 2]
PARTIES_PAR_SEQ["S12"] = [1, 2, 3]
PARTIES_PAR_SEQ["S14"] = [1, 2]

# ── Séances par objectif (modèle 'par_objectif'), consolidées des plans ──────
# nb_seances[seq][code] = nombre de séances de l'objectif. L'objectif 01 porte
# la « Présentation » de sa partie d'appartenance (decision Q-B.a).
NB_SEANCES_OBJ = {
    "S01": {"01": 1, "02": 1, "03": 1, "04": 1, "05": 1},
    "S02": {"01": 0, "02": 1, "03": 1, "04": 1},
    "S03": {},  # plan sans repères exploitables
    "S04": {"01": 1, "02": 1, "03": 2, "04": 2},
    "S05": {"01": 2, "02": 2, "03": 1, "04": 1, "05": 1},
    "S06": {"01": 1, "02": 1, "03": 0, "04": 0, "05": 2, "06": 1},
    "S07": {"01": 0, "02": 1, "03": 1, "04": 1},
    "S08": {"01": 0, "02": 1, "03": 2, "04": 0, "05": 0, "06": 1},
    "S09": {"01": 1, "02": 3},
    "S10": {"01": 1, "02": 1, "03": 1, "04": 1, "05": 1, "06": 1, "07": 1, "08": 0},
    "S11": {"01": 1, "02": 1, "03": 1, "04": 1, "05": 1, "06": 1},
    "S12": {"01": 3, "02": 2, "03": 3, "04": 1, "05": 1},
    "S13": {"01": 1, "02": 1, "03": 0, "04": 0, "05": 1, "06": 2},
    "S14": {"01": 1, "02": 2, "03": 3, "04": 3},
}

# Auto-évaluation par (séquence, partie) → referentiel_parties.nb_seances_R_AE.
NB_RAE = {
    ("S01", 1): 2, ("S02", 1): 0, ("S04", 1): 0, ("S06", 1): 1, ("S07", 1): 0,
    ("S08", 1): 0, ("S09", 1): 1, ("S11", 1): 1, ("S13", 1): 1,
    ("S10", 1): 2, ("S10", 2): 1,
    ("S12", 1): 2, ("S12", 2): 1,
    ("S14", 1): 1,
    # S03, S05, S12 P3, S14 P2 : pas d'auto-éval exploitable → 0 (défaut).
}

# ── Créneaux : ordre + dates + période + libellé ────────────────────────────
# (code, partie, date_debut, date_fin, periode, libelle)
CRENEAUX = [
    ("S14", 1, "2022-09-06", "2022-09-09", "T1", "1ère partie : algorithmique débranchée"),
    ("S01", 1, "2022-09-12", "2022-09-23", "T1", ""),
    ("S12", 1, "2022-09-26", "2022-10-07", "T1", "1ère partie : angles"),
    ("S08", 1, "2022-10-10", "2022-10-21", "T1", ""),
    ("S02", 1, "2022-10-24", "2022-11-17", "T1", ""),
    ("S11", 1, "2022-11-18", "2022-12-02", "T2", ""),
    ("S03", 1, "2022-12-05", "2022-12-16", "T2", ""),
    ("S12", 2, "2022-12-19", "2023-01-13", "T2", "2ème partie : triangles"),
    ("S07", 1, "2023-01-16", "2023-01-27", "T2", ""),
    ("S04", 1, "2023-01-30", "2023-02-10", "T2", ""),
    ("S10", 1, "2023-02-13", "2023-03-10", "T2", "1ère partie : longueurs et aires"),
    ("S05", 1, "2023-03-13", "2023-03-24", "T3", ""),
    ("S14", 2, "2023-03-27", "2023-03-31", "T3", "2ème partie : programmation"),
    ("S12", 3, "2023-04-03", "2023-04-07", "T3", "3ème partie : parallélogrammes"),
    ("S06", 1, "2023-04-10", "2023-05-05", "T3", ""),
    ("S13", 1, "2023-05-08", "2023-05-17", "T3", ""),
    ("S09", 1, "2023-05-18", "2023-06-01", "T3", ""),
    ("S10", 2, "2023-06-02", "2023-06-16", "T3", "2ème partie : volumes et durées"),
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
    # Créneaux existants attendus (sauf S10 P2 qui sera créé).
    for (seq, part), cid in CRENEAU.items():
        if (seq, part) == ("S10", 2):
            continue
        if not conn.execute(
                "SELECT 1 FROM creneaux WHERE id=? AND progression_id=? "
                "AND seq_code=? AND partie_debut=?",
                (cid, PROG_ID, seq, part)).fetchone():
            pbs.append(f"créneau {seq} P{part} ({cid}) introuvable")
    # Le créneau S14 P3 à supprimer ne doit porter aucun suivi.
    n = conn.execute("SELECT COUNT(*) FROM niveaux WHERE creneau_id=?",
                     (CRENEAU_A_SUPPRIMER,)).fetchone()[0]
    if n > 0:
        pbs.append(f"le créneau S14 P3 ({CRENEAU_A_SUPPRIMER}) porte {n} "
                   f"lignes de suivi : suppression refusée")
    return pbs


def _id_creneau_s10_p2(conn) -> str:
    r = conn.execute(
        "SELECT id FROM creneaux WHERE progression_id=? AND seq_code='S10' "
        "AND partie_debut=2", (PROG_ID,)).fetchone()
    return r["id"] if r else nouveau_id_creneau()


def _appliquer(conn, journal: list[str]) -> None:
    # 1. Mode (reste par_objectif) + parties ---------------------------------
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
            rae = NB_RAE.get((seq, p), 0)
            conn.execute(
                "INSERT INTO referentiel_parties "
                "(referentiel_id, seq_code, numero, nb_seances_R_AE) "
                "VALUES (?,?,?,?)", (REF_ID, seq, p, rae))
            n_parties += 1
    journal.append(f"referentiel_parties : {n_parties} parties "
                   "(S10→2, S12→3, S14→2) + nb_seances_R_AE")

    # partie_numero des objectifs scindés
    for seq, parts in DECOUPAGE.items():
        for pnum, codes in parts.items():
            for code in codes:
                conn.execute(
                    "UPDATE referentiel_objectifs SET partie_numero=? "
                    "WHERE referentiel_id=? AND seq_code=? AND code=?",
                    (pnum, REF_ID, seq, code))
    journal.append("referentiel_objectifs.partie_numero : "
                   "S10 {01,04,05,07}/{02,03,06,08} ; "
                   "S12 {01,02}/{03}/{04,05} ; S14 {01,02}/{03,04}")

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

    # 3. Créneaux : supprimer S14 P3, créer S10 P2, corriger en place --------
    cur = conn.execute("DELETE FROM creneaux WHERE id=?", (CRENEAU_A_SUPPRIMER,))
    journal.append(f"creneaux : créneau S14 P3 supprimé "
                   f"({CRENEAU_A_SUPPRIMER}) — {cur.rowcount} ligne")

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

    # 4. Suivi : redistribuer vers parties 2/3 (les 2 classes) ---------------
    n_suivi = 0
    deplacements = [
        ("S12", CRENEAU[("S12", 1)], CRENEAU[("S12", 2)], DECOUPAGE["S12"][2]),
        ("S12", CRENEAU[("S12", 1)], CRENEAU[("S12", 3)], DECOUPAGE["S12"][3]),
        ("S14", CRENEAU[("S14", 1)], CRENEAU[("S14", 2)], DECOUPAGE["S14"][2]),
        ("S10", CRENEAU[("S10", 1)], CRENEAU[("S10", 2)], DECOUPAGE["S10"][2]),
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
                   "parties 2/3 (S10, S12, S14 ; 2 classes)")


def _verifier_apres(conn) -> list[str]:
    pbs = []
    for seq, n in (("S10", 2), ("S12", 3), ("S14", 2)):
        k = conn.execute("SELECT COUNT(*) FROM referentiel_parties "
                         "WHERE referentiel_id=? AND seq_code=?",
                         (REF_ID, seq)).fetchone()[0]
        if k != n:
            pbs.append(f"{seq} devrait avoir {n} parties, trouvé {k}")
    # S14 ne doit plus avoir de partie 3
    if conn.execute("SELECT 1 FROM creneaux WHERE progression_id=? "
                    "AND seq_code='S14' AND partie_debut=3",
                    (PROG_ID,)).fetchone():
        pbs.append("S14 partie 3 encore présente (suppression échouée)")
    # S10 P2 existe + daté
    r = conn.execute("SELECT date_fin FROM creneaux WHERE progression_id=? "
                     "AND seq_code='S10' AND partie_debut=2",
                     (PROG_ID,)).fetchone()
    if not r or not r["date_fin"]:
        pbs.append("créneau S10 P2 absent ou non daté")
    # Découpage S12 P3
    p3 = {x[0] for x in conn.execute(
        "SELECT code FROM referentiel_objectifs WHERE referentiel_id=? "
        "AND seq_code='S12' AND partie_numero=3", (REF_ID,)).fetchall()}
    if p3 != set(DECOUPAGE["S12"][3]):
        pbs.append(f"S12 P3 = {sorted(p3)}, attendu {list(DECOUPAGE['S12'][3])}")
    # Créneaux datés (18)
    nd = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
                      "AND date_fin IS NOT NULL", (PROG_ID,)).fetchone()[0]
    if nd < len(CRENEAUX):
        pbs.append(f"{nd} créneaux datés, attendu {len(CRENEAUX)}")
    # Suivi S12 P3 présent (pour les 2 classes)
    cr_p3 = CRENEAU.get(("S12", 3))
    n_p3 = conn.execute(
        "SELECT COUNT(*) FROM niveaux WHERE classe_id IN (?,?) "
        "AND seq_code='S12' AND creneau_id=? AND obj_code IN (?,?)",
        (*CLASSES, cr_p3, *DECOUPAGE["S12"][3])).fetchone()[0]
    if n_p3 == 0:
        pbs.append("aucun suivi S12 obj P3 sur le créneau partie 3")
    return pbs


def _etat(conn) -> str:
    mode = conn.execute("SELECT mode_seances FROM referentiel_niveaux WHERE id=?",
                        (REF_ID,)).fetchone()
    np = conn.execute("SELECT COUNT(*) FROM referentiel_parties WHERE referentiel_id=?",
                      (REF_ID,)).fetchone()[0]
    nobj = conn.execute("SELECT COUNT(*) FROM referentiel_objectifs "
                        "WHERE referentiel_id=? AND nb_seances>0",
                        (REF_ID,)).fetchone()[0]
    ncr = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=?",
                       (PROG_ID,)).fetchone()[0]
    nd = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
                      "AND date_fin IS NOT NULL", (PROG_ID,)).fetchone()[0]
    s14p3 = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
                         "AND seq_code='S14' AND partie_debut=3",
                         (PROG_ID,)).fetchone()[0]
    s10p2 = conn.execute("SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
                         "AND seq_code='S10' AND partie_debut=2",
                         (PROG_ID,)).fetchone()[0]
    return (f"  mode_seances({REF_ID}) = {mode[0] if mode else '—'!r}\n"
            f"  referentiel_parties = {np} ; objectifs avec nb_seances>0 = {nobj}\n"
            f"  créneaux = {ncr} (datés {nd}/{len(CRENEAUX)}) ; "
            f"S14 P3 présent = {'oui' if s14p3 else 'non'} ; "
            f"S10 P2 présent = {'oui' if s10p2 else 'non'}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=_chemin_db_par_defaut())
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    if not args.db.exists():
        print(f"[import 5e2-2022] base introuvable : {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        pbs = _verifier_prerequis(conn)
        if pbs:
            print("[import 5e2-2022] prérequis non satisfaits :")
            for p in pbs:
                print(f"  ✗ {p}")
            return 3

        print("[import 5e2-2022] ── État AVANT ──")
        print(_etat(conn))

        journal: list[str] = []
        conn.execute("BEGIN")
        _appliquer(conn, journal)

        print("\n[import 5e2-2022] ── Opérations ──")
        for l in journal:
            print(f"  • {l}")

        verifs = _verifier_apres(conn)
        if verifs:
            print("\n[import 5e2-2022] ✗ vérification post-import échouée :")
            for v in verifs:
                print(f"  ✗ {v}")
            conn.rollback()
            print("[import 5e2-2022] rollback — aucune modification.")
            return 3

        if not args.apply:
            conn.rollback()
            print("\n[import 5e2-2022] DRY-RUN : modifications annulées "
                  "(rejouer avec --apply pour appliquer).")
            return 0

        if not args.yes:
            rep = input("\n[import 5e2-2022] Appliquer définitivement ? "
                        "Tapez 'OUI' : ").strip()
            if rep != "OUI":
                conn.rollback()
                print("[import 5e2-2022] annulé.")
                return 1

        conn.commit()
        print("\n[import 5e2-2022] ── État APRÈS ──")
        print(_etat(conn))
        print("\n[import 5e2-2022] ✓ import appliqué. 🎉")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"[import 5e2-2022] erreur : {e}", file=sys.stderr)
        return 3
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
