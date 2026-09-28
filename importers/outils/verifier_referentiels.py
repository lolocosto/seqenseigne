#!/usr/bin/env python3
"""outils/verifier_referentiels.py — v0.19.1.8

Audit d'alignement entre un référentiel verrouillé et la (les) progression(s)
qui s'appuient dessus, et inventaire des PDF figés (livrets de séquence).

Deux volets :

  A. STRUCTURE (lecture seule). Pour chaque progression liée au référentiel :
     - les parties attendues (déduites des créneaux : couples
       (séquence, partie_debut)) correspondent-elles à `referentiel_parties` ?
     - chaque séquence des créneaux existe-t-elle dans
       `referentiel_sequences` ?
     - chaque créneau résout-il au moins un objectif (referentiel_objectifs
       filtrés par partie_numero) ?

  B. PDF — LIVRETS DE SÉQUENCE. Pour chaque référentiel :
     - 14 livrets `livret_sequence__<niveau>__<seq>.pdf` attendus (un par
       séquence du niveau) ;
     - présents dans `data/referentiels/<ref>/_verrouille/pdfs/` ?
     - les manquants peuvent être COPIÉS depuis un dossier d'archives
       (option `--copier-livrets <dossier>`), où les livrets sont nommés
       `<préfixe> S<NN>_Livret.pdf` (le code séquence S<NN> est extrait du
       nom). Renommage vers la convention figée.

Les PLANS DE TRAVAIL sont seulement INVENTORIÉS (combien trouvés dans les
archives), pas copiés : le modèle ne prévoit pas encore de plan par séquence
(type `livret_plans` = document unitaire agrégé). La copie des plans fera
l'objet d'une livraison ultérieure (« plan de travail par séquence »).

Par défaut : lecture seule (aucune écriture). La copie des livrets n'a lieu
qu'avec `--copier-livrets <dossier_archives>` ET `--apply`.

Usage :
    # Audit complet des deux référentiels 2021 (lecture seule) :
    python -m outils.verifier_referentiels

    # Audit d'un référentiel précis :
    python -m outils.verifier_referentiels --ref N10_v2021

    # Copier les livrets manquants de N10_v2021 depuis les archives 5E2 :
    python -m outils.verifier_referentiels --ref N10_v2021 \
        --copier-livrets /chemin/vers/5E2 --apply

Codes de sortie : 0 = audit ok (aucun écart) ; 1 = écarts détectés
(structure ou PDF manquants) ; 2 = base/paramètre introuvable ; 3 = erreur.
"""

from __future__ import annotations
import argparse
import re
import shutil
import sqlite3
import sys
from pathlib import Path

# Référentiels audités par défaut (progressions 2021-22 déjà traitées).
REFS_DEFAUT = ["N11_v2021", "N10_v2021"]

_RE_SEQ = re.compile(r"S\d{2}")


def _chemin_db_par_defaut() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "seqenseigne.db"


def _dossier_pdfs(db_path: Path, ref_id: str) -> Path:
    return (db_path.parent / "referentiels" / ref_id / "_verrouille" / "pdfs")


# ── Volet A : structure ──────────────────────────────────────────────────────

def auditer_structure(conn, ref_id: str) -> list[str]:
    """Retourne la liste des écarts structure (vide si aligné)."""
    ecarts = []
    niveau_row = conn.execute(
        "SELECT niveau FROM referentiel_niveaux WHERE id=?", (ref_id,)).fetchone()
    if not niveau_row:
        return [f"référentiel {ref_id} introuvable"]
    niveau = niveau_row["niveau"]

    # Séquences du référentiel
    seqs_ref = {r["code"] for r in conn.execute(
        "SELECT code FROM referentiel_sequences WHERE referentiel_id=?",
        (ref_id,)).fetchall()}

    # Parties du référentiel : {seq: {numeros}}
    parties_ref: dict[str, set] = {}
    for r in conn.execute(
            "SELECT seq_code, numero FROM referentiel_parties WHERE referentiel_id=?",
            (ref_id,)).fetchall():
        parties_ref.setdefault(r["seq_code"], set()).add(r["numero"])

    # Progressions liées
    progs = conn.execute(
        "SELECT id, annee FROM progressions WHERE referentiel_id=?",
        (ref_id,)).fetchall()
    if not progs:
        ecarts.append("aucune progression ne s'appuie sur ce référentiel")

    for pg in progs:
        pid = pg["id"]
        # Parties attendues d'après les créneaux : {seq: {partie_debut}}
        att: dict[str, set] = {}
        for r in conn.execute(
                "SELECT seq_code, partie_debut FROM creneaux WHERE progression_id=?",
                (pid,)).fetchall():
            att.setdefault(r["seq_code"], set()).add(r["partie_debut"] or 1)

        for seq, parts_att in sorted(att.items()):
            if seq not in seqs_ref:
                ecarts.append(
                    f"[{pid}] séquence {seq} des créneaux absente du "
                    f"référentiel")
                continue
            parts_ref = parties_ref.get(seq, {1})
            if parts_att != parts_ref:
                ecarts.append(
                    f"[{pid}] {seq} : parties créneaux={sorted(parts_att)} "
                    f"≠ référentiel={sorted(parts_ref)}")
            # Chaque partie attendue doit résoudre des objectifs
            for pnum in parts_att:
                n = conn.execute(
                    "SELECT COUNT(*) FROM referentiel_objectifs "
                    "WHERE referentiel_id=? AND seq_code=? AND partie_numero=?",
                    (ref_id, seq, pnum)).fetchone()[0]
                if n == 0:
                    ecarts.append(
                        f"[{pid}] {seq} partie {pnum} : aucun objectif "
                        f"résolu dans le référentiel")
    return ecarts


# ── Volet B : PDF livrets ────────────────────────────────────────────────────

def _sequences_du_niveau(conn, niveau: str) -> list[str]:
    return [r["sequence_code"] for r in conn.execute(
        "SELECT DISTINCT sequence_code FROM sequences_par_niveau "
        "WHERE niveau=? ORDER BY sequence_code", (niveau,)).fetchall()]


def auditer_livrets(conn, db_path: Path, ref_id: str) -> dict:
    """Retourne {attendus, presents, manquants, niveau, dossier}."""
    niveau = conn.execute(
        "SELECT niveau FROM referentiel_niveaux WHERE id=?",
        (ref_id,)).fetchone()["niveau"]
    seqs = _sequences_du_niveau(conn, niveau)
    attendus = {f"livret_sequence__{niveau}__{s}.pdf" for s in seqs}
    dossier = _dossier_pdfs(db_path, ref_id)
    presents = set()
    if dossier.is_dir():
        presents = {p.name for p in dossier.iterdir() if p.is_file()}
    manquants = sorted(attendus - presents)
    return {
        "niveau":    niveau,
        "dossier":   dossier,
        "attendus":  sorted(attendus),
        "presents":  sorted(a for a in attendus if a in presents),
        "manquants": manquants,
    }


def _index_archives(dossier: Path, motif_suffixe: str) -> dict[str, Path]:
    """Indexe les fichiers d'archives par code séquence.

    `motif_suffixe` : ex. '_Livret.pdf' ou 'Plan'. On retient, pour chaque
    code S<NN>, le fichier le plus récemment modifié (cohérent avec « la
    vérité est dans les fichiers récents »).
    """
    index: dict[str, Path] = {}
    if not dossier.is_dir():
        return index
    for f in dossier.rglob("*.pdf"):
        if motif_suffixe.lower() not in f.name.lower():
            continue
        m = _RE_SEQ.search(f.name)
        if not m:
            continue
        seq = m.group(0)
        if seq not in index or f.stat().st_mtime > index[seq].stat().st_mtime:
            index[seq] = f
    return index


def copier_livrets_manquants(conn, db_path: Path, ref_id: str,
                              dossier_archives: Path, apply: bool) -> dict:
    """Copie les livrets de séquence manquants depuis les archives.

    Retourne {copies: [...], introuvables: [...]}.
    """
    audit = auditer_livrets(conn, db_path, ref_id)
    niveau = audit["niveau"]
    dossier_cible = audit["dossier"]
    index = _index_archives(dossier_archives, "_Livret.pdf")

    copies, introuvables = [], []
    for nom_cible in audit["manquants"]:
        m = _RE_SEQ.search(nom_cible)
        seq = m.group(0) if m else None
        src = index.get(seq)
        if not src:
            introuvables.append(nom_cible)
            continue
        dst = dossier_cible / nom_cible
        if apply:
            dossier_cible.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        copies.append((src.name, nom_cible))
    return {"copies": copies, "introuvables": introuvables}


def inventorier_plans(dossier_archives: Path) -> int:
    """Nombre de plans de travail trouvés dans les archives (informatif)."""
    if not dossier_archives.is_dir():
        return 0
    return sum(1 for f in dossier_archives.rglob("*.pdf")
               if "plan" in f.name.lower())


# ── Orchestration ────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=_chemin_db_par_defaut())
    ap.add_argument("--ref", action="append",
                    help="référentiel à auditer (répétable ; défaut : "
                         "N11_v2021 et N10_v2021)")
    ap.add_argument("--copier-livrets", type=Path, metavar="DOSSIER_ARCHIVES",
                    help="copie les livrets manquants depuis ce dossier "
                         "d'archives (nécessite --apply pour écrire)")
    ap.add_argument("--apply", action="store_true",
                    help="autorise l'écriture (copie des livrets)")
    args = ap.parse_args(argv)

    if not args.db.exists():
        print(f"[verif ref] base introuvable : {args.db}", file=sys.stderr)
        return 2
    if args.copier_livrets and not args.copier_livrets.is_dir():
        print(f"[verif ref] dossier d'archives introuvable : "
              f"{args.copier_livrets}", file=sys.stderr)
        return 2

    refs = args.ref or REFS_DEFAUT
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    code_sortie = 0
    try:
        for ref_id in refs:
            print(f"\n══════ {ref_id} ══════")
            if not conn.execute("SELECT 1 FROM referentiel_niveaux WHERE id=?",
                                (ref_id,)).fetchone():
                print("  ✗ référentiel introuvable en base")
                code_sortie = max(code_sortie, 2)
                continue

            # A. Structure
            ecarts = auditer_structure(conn, ref_id)
            print("  ── Structure (référentiel ↔ progression) ──")
            if ecarts:
                code_sortie = max(code_sortie, 1)
                for e in ecarts:
                    print(f"    ⚠ {e}")
            else:
                print("    ✓ aligné (parties, séquences et objectifs)")

            # B. PDF livrets
            audit = auditer_livrets(conn, args.db, ref_id)
            print("  ── Livrets de séquence (PDF figés) ──")
            print(f"    présents : {len(audit['presents'])}/"
                  f"{len(audit['attendus'])}")
            if audit["manquants"]:
                code_sortie = max(code_sortie, 1)
                print(f"    manquants : {len(audit['manquants'])}")
                for m in audit["manquants"]:
                    print(f"      • {m}")

            # Copie éventuelle
            if args.copier_livrets and audit["manquants"]:
                res = copier_livrets_manquants(
                    conn, args.db, ref_id, args.copier_livrets, args.apply)
                verbe = "copiés" if args.apply else "à copier (dry-run)"
                print(f"    ── Copie depuis {args.copier_livrets} ──")
                for src, dst in res["copies"]:
                    print(f"      {verbe} : {src}  →  {dst}")
                for nf in res["introuvables"]:
                    print(f"      ✗ source introuvable pour {nf}")
                if res["copies"] and args.apply:
                    # Recompter après copie
                    audit2 = auditer_livrets(conn, args.db, ref_id)
                    print(f"    après copie : {len(audit2['presents'])}/"
                          f"{len(audit2['attendus'])} présents")
                    if not audit2["manquants"]:
                        code_sortie = 0 if code_sortie == 1 and not ecarts \
                            else code_sortie

            # Inventaire plans (informatif)
            if args.copier_livrets:
                nplans = inventorier_plans(args.copier_livrets)
                print(f"  ── Plans de travail (informatif) ──")
                print(f"    {nplans} plan(s) trouvé(s) dans les archives — "
                      f"non copiés (modèle « plan par séquence » à venir).")

        print()
        if code_sortie == 0:
            print("[verif ref] ✓ tout est aligné.")
        else:
            print("[verif ref] ⚠ des écarts subsistent (voir ci-dessus).")
        return code_sortie
    except Exception as e:
        print(f"[verif ref] erreur : {e}", file=sys.stderr)
        return 3
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
