#!/usr/bin/env python3
"""outils/import_historique_4e3_2021.py — v0.19.1.5

Import « ad hoc » de la structure historique de la progression 4ᵉ 2021-22
(classes 4E3/4E4/4E6, Collège des Hautes Ourmes), à partir du répertoire
d'archives de l'époque. Script à USAGE UNIQUE : les valeurs (matrices de
séances, dates, ordre, découpage des parties) sont figées ci-dessous, lues des
fichiers `*_Plan.tex` / `Progression_annuelle.tex` les plus récents (la vérité
est dans les fichiers récents — les plans ont été retouchés en cours d'année
sans répercussion dans la progression de septembre).

Cible :
  - référentiel  : N11_v2021  (verrouillé)
  - progression  : pg_e011c733  (partagée par 4E3 cl_80446c91,
                                  4E4 cl_699b243a, 4E6 cl_93b12b4e)

Opérations (transaction unique) :

  1. RÉFÉRENTIEL — découpage en parties
     - mode_seances = 'par_serie' (decision Q4)
     - referentiel_parties : S12 → {1, 2} ; toutes les autres séquences → {1}
     - referentiel_objectifs.partie_numero : S12 obj 01,02,03 → 1 ;
       obj 04,05,06 → 2 (decision Q3). Les autres séquences restent en 1.

  2. RÉFÉRENTIEL — séances par série (decision Q1.a : on n'insère que les
     matrices réellement présentes dans les plans autoritaires)
     - referentiel_parties_seances : 9 séquences avec matrice
       (S01,S02 sans série R ; les 7 autres complètes R/F/A/E).
       S04,S07,S09,S10,S12 : aucune matrice (plans récents en ancien format).

  3. PROGRESSION — créneaux corrigés EN PLACE (IDs préservés : le suivi de
     classe, table `niveaux`, est rattaché aux creneau_id existants — il ne
     faut surtout pas recréer les créneaux)
     - ordre chronologique (par date de début), date_debut / date_fin,
       libellés de partie pour S12, période T1/T2/T3 (dérivée des dates ;
       les Txbilan.csv sont incohérents et ignorés, decision Q6).

  4. SUIVI — redistribution S12
     - les lignes `niveaux` des objectifs 04,05,06 de S12, actuellement sur le
       créneau partie-1 (cr_4063001c), sont déplacées vers le créneau partie-2
       (cr_f13f3e81), pour les 3 classes. Obj 01,02,03 restent sur la partie 1.

  Hors périmètre : les bilans de fin de trimestre (le modèle de créneau ne les
  porte pas — éval de période à modéliser ultérieurement).

Sécurités : dry-run par défaut ; --apply + confirmation 'OUI' (ou --yes).
Idempotent : ré-exécutable sans dupliquer (DELETE+INSERT pour parties/séances ;
UPDATE pour créneaux ; le déplacement de suivi ne fait rien s'il est déjà fait).
Vérification post-import.

Usage :
    python -m outils.import_historique_4e3_2021            # dry-run
    python -m outils.import_historique_4e3_2021 --apply
    python -m outils.import_historique_4e3_2021 --apply --yes

Codes de sortie : 0 succès, 1 annulé, 2 base introuvable, 3 erreur.
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

# ── Constantes cibles ────────────────────────────────────────────────────────

REF_ID = "N11_v2021"
PROG_ID = "pg_e011c733"
CLASSES = ("cl_80446c91", "cl_699b243a", "cl_93b12b4e")  # 4E3, 4E4, 4E6

# Créneau S12 : IDs existants (audit base). Partie 1 / Partie 2.
CRENEAU_S12_P1 = "cr_4063001c"
CRENEAU_S12_P2 = "cr_f13f3e81"

# Mapping objectif → partie pour S12 (Q3).
S12_OBJ_P1 = ("01", "02", "03")
S12_OBJ_P2 = ("04", "05", "06")

# Parties par séquence : seule S12 a 2 parties.
PARTIES_PAR_SEQ = {f"S{n:02d}": [1] for n in range(1, 15)}
PARTIES_PAR_SEQ["S12"] = [1, 2]

# ── Matrices de séances par série (decision Q1.a) ────────────────────────────
# Lues des plans autoritaires (plus récents). Structure :
#   { seq_code: { partie_numero: { 'TB': {serie: nb}, 'S': {serie: nb} } } }
# Séries : R (auto-éval/révisions), F, A, E. Absence = cellule non renseignée.
# S01/S02 : pas de série R. S04,S07,S09,S10,S12 : aucune matrice.
MATRICES = {
    "S01": {1: {"TB": {"F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"F": 2.5, "A": 3.0}}},
    "S02": {1: {"TB": {"F": 0.5, "A": 1.0, "E": 2.0},
                "S":  {"F": 1.5, "A": 1.5}}},
    "S03": {1: {"TB": {"R": 1.5, "F": 2.0, "A": 3.0, "E": 3.5},
                "S":  {"R": 2.5, "F": 3.5, "A": 4.0}}},
    "S05": {1: {"TB": {"R": 1.0, "F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"R": 1.5, "F": 2.5, "A": 3.0}}},
    "S06": {1: {"TB": {"R": 1.0, "F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"R": 1.5, "F": 2.5, "A": 3.0}}},
    "S08": {1: {"TB": {"R": 1.0, "F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"R": 1.5, "F": 2.5, "A": 3.0}}},
    "S11": {1: {"TB": {"R": 1.0, "F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"R": 1.5, "F": 2.5, "A": 3.0}}},
    "S13": {1: {"TB": {"R": 1.0, "F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"R": 1.5, "F": 2.5, "A": 3.0}}},
    "S14": {1: {"TB": {"R": 1.0, "F": 1.5, "A": 2.0, "E": 2.5},
                "S":  {"R": 1.5, "F": 2.5, "A": 3.0}}},
}

# ── Créneaux : ordre chronologique + dates + période + libellé de partie ─────
# (code, partie, date_debut ISO, date_fin ISO, periode, libelle_partie)
# Dates lues des plans autoritaires ; année déduite (sept-déc 2021, sinon 2022).
# Périodes dérivées des dates (Q6).
CRENEAUX = [
    ("S05", 1, "2021-09-06", "2021-09-17", "T1", ""),
    ("S14", 1, "2021-09-20", "2021-10-01", "T1", ""),
    ("S11", 1, "2021-10-04", "2021-10-15", "T1", ""),
    ("S01", 1, "2021-10-18", "2021-11-10", "T1", ""),
    ("S06", 1, "2021-11-15", "2021-11-26", "T1", ""),
    ("S02", 1, "2021-11-29", "2021-12-03", "T1", ""),
    ("S08", 1, "2021-12-06", "2021-12-17", "T2", ""),
    ("S03", 1, "2022-01-03", "2022-01-21", "T2", ""),
    ("S12", 1, "2022-01-24", "2022-02-24", "T2", "1ère partie : théorème de Pythagore"),
    ("S10", 1, "2022-02-28", "2022-03-11", "T2", ""),
    ("S12", 2, "2022-03-14", "2022-04-01", "T3", "2ème partie : théorème de Thalès et cosinus"),
    ("S04", 1, "2022-04-04", "2022-04-29", "T3", ""),
    ("S07", 1, "2022-05-02", "2022-05-13", "T3", ""),
    ("S09", 1, "2022-05-16", "2022-05-30", "T3", ""),
    ("S13", 1, "2022-05-23", "2022-06-03", "T3", ""),
]


def _chemin_db_par_defaut() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "seqenseigne.db"


# ── Diagnostics pré-import ───────────────────────────────────────────────────

def _verifier_prerequis(conn) -> list[str]:
    """Retourne la liste des problèmes bloquants (vide si tout est ok)."""
    pbs = []
    ref = conn.execute(
        "SELECT id, mode_seances FROM referentiel_niveaux WHERE id=?",
        (REF_ID,)).fetchone()
    if not ref:
        pbs.append(f"référentiel {REF_ID} introuvable")
    prog = conn.execute(
        "SELECT id FROM progressions WHERE id=?", (PROG_ID,)).fetchone()
    if not prog:
        pbs.append(f"progression {PROG_ID} introuvable")
    # Colonnes/tables du modèle v0.19.1.4
    cols = {c[1] for c in conn.execute(
        "PRAGMA table_info(referentiel_niveaux)").fetchall()}
    if "mode_seances" not in cols:
        pbs.append("colonne referentiel_niveaux.mode_seances absente "
                   "(déployer v0.19.1.4 d'abord)")
    t = conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                     "AND name='referentiel_parties_seances'").fetchone()
    if not t:
        pbs.append("table referentiel_parties_seances absente "
                   "(déployer v0.19.1.4 d'abord)")
    # Créneaux S12 attendus
    for cid, part in ((CRENEAU_S12_P1, 1), (CRENEAU_S12_P2, 2)):
        r = conn.execute(
            "SELECT id FROM creneaux WHERE id=? AND progression_id=? "
            "AND seq_code='S12' AND partie_debut=?",
            (cid, PROG_ID, part)).fetchone()
        if not r:
            pbs.append(f"créneau S12 partie {part} ({cid}) introuvable")
    return pbs


# ── Opérations ───────────────────────────────────────────────────────────────

def _appliquer(conn, journal: list[str]) -> None:
    # 1. Mode + parties ------------------------------------------------------
    conn.execute(
        "UPDATE referentiel_niveaux SET mode_seances='par_serie' WHERE id=?",
        (REF_ID,))
    journal.append(f"referentiel_niveaux.mode_seances = 'par_serie' ({REF_ID})")

    conn.execute(
        "DELETE FROM referentiel_parties WHERE referentiel_id=?", (REF_ID,))
    n_parties = 0
    # Ne créer les parties que pour les séquences réellement présentes.
    seqs_presentes = {r[0] for r in conn.execute(
        "SELECT code FROM referentiel_sequences WHERE referentiel_id=?",
        (REF_ID,)).fetchall()}
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
                   f"(dont S12 → 2)")

    # partie_numero des objectifs S12
    for code in S12_OBJ_P1:
        conn.execute(
            "UPDATE referentiel_objectifs SET partie_numero=1 "
            "WHERE referentiel_id=? AND seq_code='S12' AND code=?",
            (REF_ID, code))
    for code in S12_OBJ_P2:
        conn.execute(
            "UPDATE referentiel_objectifs SET partie_numero=2 "
            "WHERE referentiel_id=? AND seq_code='S12' AND code=?",
            (REF_ID, code))
    journal.append("referentiel_objectifs.partie_numero S12 : "
                   "{01,02,03}→1 ; {04,05,06}→2")

    # 2. Matrices de séances par série ---------------------------------------
    conn.execute(
        "DELETE FROM referentiel_parties_seances WHERE referentiel_id=?",
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

    # 3. Créneaux corrigés en place (IDs préservés) --------------------------
    n_maj = 0
    for ordre, (seq, part, deb, fin, per, lib) in enumerate(CRENEAUX, start=1):
        cur = conn.execute(
            "UPDATE creneaux SET ordre=?, date_debut=?, date_fin=?, "
            "periode=?, partie=?, partie_debut=?, partie_fin=? "
            "WHERE progression_id=? AND seq_code=? AND partie_debut=?",
            (ordre, deb, fin, per, lib, part, part, PROG_ID, seq, part))
        if cur.rowcount == 0:
            journal.append(f"  ⚠ créneau {seq} P{part} non trouvé (ignoré)")
        else:
            n_maj += cur.rowcount
    journal.append(f"creneaux : {n_maj} créneaux mis à jour (ordre/dates/"
                   f"période/libellé), IDs préservés")

    # 4. Suivi S12 : déplacer obj 04-06 vers le créneau partie 2 -------------
    n_suivi = 0
    for cl in CLASSES:
        cur = conn.execute(
            "UPDATE niveaux SET creneau_id=? "
            "WHERE classe_id=? AND seq_code='S12' AND creneau_id=? "
            "AND obj_code IN (?,?,?)",
            (CRENEAU_S12_P2, cl, CRENEAU_S12_P1, *S12_OBJ_P2))
        n_suivi += cur.rowcount
    journal.append(f"niveaux : {n_suivi} lignes de suivi S12 (obj 04-06) "
                   f"déplacées vers le créneau partie 2 (3 classes)")


# ── Vérification post-import ─────────────────────────────────────────────────

def _verifier_apres(conn) -> list[str]:
    pbs = []
    mode = conn.execute(
        "SELECT mode_seances FROM referentiel_niveaux WHERE id=?",
        (REF_ID,)).fetchone()[0]
    if mode != "par_serie":
        pbs.append(f"mode_seances attendu 'par_serie', trouvé {mode!r}")
    np = conn.execute(
        "SELECT COUNT(*) FROM referentiel_parties WHERE referentiel_id=? "
        "AND seq_code='S12'", (REF_ID,)).fetchone()[0]
    if np != 2:
        pbs.append(f"S12 devrait avoir 2 parties, trouvé {np}")
    # partie_numero S12
    p2 = {r[0] for r in conn.execute(
        "SELECT code FROM referentiel_objectifs WHERE referentiel_id=? "
        "AND seq_code='S12' AND partie_numero=2", (REF_ID,)).fetchall()}
    if p2 != set(S12_OBJ_P2):
        pbs.append(f"objectifs S12 partie 2 = {sorted(p2)}, "
                   f"attendu {list(S12_OBJ_P2)}")
    # Créneaux datés
    nd = conn.execute(
        "SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
        "AND date_fin IS NOT NULL", (PROG_ID,)).fetchone()[0]
    if nd < len(CRENEAUX):
        pbs.append(f"{nd} créneaux datés, attendu {len(CRENEAUX)}")
    # Suivi : la partie 2 doit avoir du suivi pour obj 04-06
    n_p2 = conn.execute(
        "SELECT COUNT(*) FROM niveaux WHERE classe_id IN (?,?,?) "
        "AND seq_code='S12' AND creneau_id=? AND obj_code IN (?,?,?)",
        (*CLASSES, CRENEAU_S12_P2, *S12_OBJ_P2)).fetchone()[0]
    if n_p2 == 0:
        pbs.append("aucun suivi S12 obj 04-06 sur le créneau partie 2 "
                   "(redistribution échouée ?)")
    return pbs


def _etat_actuel(conn) -> str:
    """Petit résumé avant/après pour le compte-rendu."""
    lignes = []
    mode = conn.execute(
        "SELECT mode_seances FROM referentiel_niveaux WHERE id=?",
        (REF_ID,)).fetchone()
    lignes.append(f"  mode_seances({REF_ID}) = "
                  f"{mode[0] if mode else '—'!r}")
    np = conn.execute(
        "SELECT COUNT(*) FROM referentiel_parties WHERE referentiel_id=?",
        (REF_ID,)).fetchone()[0]
    nc = conn.execute(
        "SELECT COUNT(*) FROM referentiel_parties_seances WHERE referentiel_id=?",
        (REF_ID,)).fetchone()[0]
    nd = conn.execute(
        "SELECT COUNT(*) FROM creneaux WHERE progression_id=? "
        "AND date_fin IS NOT NULL", (PROG_ID,)).fetchone()[0]
    n_p1 = conn.execute(
        "SELECT COUNT(*) FROM niveaux WHERE seq_code='S12' AND creneau_id=? "
        "AND obj_code IN (?,?,?)",
        (CRENEAU_S12_P1, *S12_OBJ_P2)).fetchone()[0]
    lignes.append(f"  referentiel_parties = {np} ; "
                  f"parties_seances = {nc} cellules")
    lignes.append(f"  créneaux datés = {nd}/{len(CRENEAUX)}")
    lignes.append(f"  suivi S12 obj04-06 encore sur partie 1 = {n_p1} lignes")
    return "\n".join(lignes)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=_chemin_db_par_defaut())
    ap.add_argument("--apply", action="store_true",
                    help="applique réellement (sinon dry-run)")
    ap.add_argument("--yes", action="store_true",
                    help="saute la confirmation interactive")
    args = ap.parse_args(argv)

    if not args.db.exists():
        print(f"[import 4e3] base introuvable : {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        pbs = _verifier_prerequis(conn)
        if pbs:
            print("[import 4e3] prérequis non satisfaits :")
            for p in pbs:
                print(f"  ✗ {p}")
            return 3

        print("[import 4e3] ── État AVANT ──")
        print(_etat_actuel(conn))

        journal: list[str] = []
        conn.execute("BEGIN")
        _appliquer(conn, journal)

        print("\n[import 4e3] ── Opérations ──")
        for l in journal:
            print(f"  • {l}")

        verifs = _verifier_apres(conn)
        if verifs:
            print("\n[import 4e3] ✗ vérification post-import échouée :")
            for v in verifs:
                print(f"  ✗ {v}")
            conn.rollback()
            print("[import 4e3] rollback — aucune modification.")
            return 3

        if not args.apply:
            conn.rollback()
            print("\n[import 4e3] DRY-RUN : modifications annulées "
                  "(rejouer avec --apply pour appliquer).")
            return 0

        if not args.yes:
            rep = input("\n[import 4e3] Appliquer définitivement ? "
                        "Tapez 'OUI' : ").strip()
            if rep != "OUI":
                conn.rollback()
                print("[import 4e3] annulé.")
                return 1

        conn.commit()
        print("\n[import 4e3] ── État APRÈS ──")
        print(_etat_actuel(conn))
        print("\n[import 4e3] ✓ import appliqué. 🎉")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"[import 4e3] erreur : {e}", file=sys.stderr)
        return 3
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
