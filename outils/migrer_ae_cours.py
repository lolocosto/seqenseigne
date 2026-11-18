#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""outils/migrer_ae_cours.py — v0.60.0

Range sous l'objectif « Cours » de leur partie les activités de découverte
(AE) que les lots de 4e ont dû mettre sous le premier objectif de la partie
(correctif B6, `doc/redemarrage_v0_60_0.md`) : jusqu'à la v0.59.3, l'import
refusait tout contenu sous « Cours ». Depuis la v0.60.0, un lot peut écrire
ses activités sous l'objectif « Cours » (`"code": "A1-01"`, ou `"code":
"Cours", "partie": 1`) ; cet outil fait la même chose pour les activités déjà
importées, sans réimporter les lots.

Règle (décision B6b) : dans chaque partie d'une séquence du principal du
niveau (ni archive Xnn, ni mise en route Mnn), les activités AE rattachées au
**premier objectif de capacité** de la partie (code le plus petit après le
« Cours ») et à la partie (activité d'approche EA) passent sous l'objectif
« Cours » (lien `objectif_exos`, série AE) et quittent le premier objectif.
Le livret les place alors en ouverture de partie, avant le premier objectif.
Une activité rattachée à un autre objectif ne bouge pas.

  - **6e exclue** (N09) : les lots de 6e rangent leurs activités sous leur
    objectif à dessein (S01-02 a quatre activités sur S01-02) ;
  - **séquence validée** : rien n'est touché (lecture seule ; la repasser
    « en cours », lancer l'outil, la revalider) — l'essai à blanc montre
    quand même ce qui bougerait ;
  - le `mtime` des activités déplacées est rafraîchi (contenu inchangé) :
    livret et corrigés de la séquence deviennent « périmés » et sont à
    recompiler ;
  - idempotent : une deuxième exécution ne trouve plus rien.

Modes : essai à blanc (défaut, copie en mémoire) ; --apply (sauvegarde .db
dans `sauvegardes\`, une transaction, journal JSON).

Usage (Windows, depuis `appli\`) :
    ..\outils\python\python.exe .\outils\migrer_ae_cours.py --niveau N11
    ..\outils\python\python.exe .\outils\migrer_ae_cours.py --niveau N11 --apply
Options : --db CHEMIN, --sequences A1,A2 (défaut : toutes), --yes.

Codes de sortie : 0 succès / essai / rien à faire, 1 annulé, 2 refus (base,
niveau), 3 erreur (rien n'est écrit).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

RACINE_APPLI = Path(__file__).resolve().parent.parent
if str(RACINE_APPLI) not in sys.path:
    sys.path.insert(0, str(RACINE_APPLI))

NIVEAUX_EXCLUS = ("N09",)


def _maintenant() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def candidats(conn, niveau: str, sequences: list[str] | None = None) -> list[dict]:
    """Activités à déplacer : [{sequence, partie, etat_sequence, exercice_id,
    code_ae, titre, objectif_depart, objectif_id_depart, cours_id}]."""
    conn.row_factory = sqlite3.Row
    out = []
    for sn in conn.execute("SELECT id, sequence_code, etat_code FROM sequences_par_niveau "
                           "WHERE niveau = ? AND sequence_code NOT LIKE 'X%' AND "
                           "sequence_code NOT GLOB 'M[0-9][0-9]' ORDER BY sequence_code",
                           (niveau,)).fetchall():
        if sequences and sn["sequence_code"] not in sequences:
            continue
        for p in conn.execute("SELECT id, numero FROM sequence_parties WHERE "
                              "sequence_par_niveau_id = ? ORDER BY numero", (sn["id"],)):
            code_c = f"{p['numero'] - 1}1"
            objs = conn.execute("SELECT id, code FROM objectifs WHERE partie_id = ? "
                                "ORDER BY code", (p["id"],)).fetchall()
            cours = [o for o in objs if o["code"] == code_c]
            capa = [o for o in objs if o["code"] != code_c]
            if not cours or not capa:
                continue
            premier = capa[0]
            for e in conn.execute(
                    "SELECT e.id, e.num, e.titre FROM objectif_exos oe JOIN exercices e ON "
                    "e.id = oe.exercice_id WHERE oe.objectif_id = ? AND oe.serie = 'AE' AND "
                    "e.serie_code = 'AE' AND EXISTS (SELECT 1 FROM "
                    "partie_exos_revision_approche pa WHERE pa.partie_id = ? AND "
                    "pa.type = 'EA' AND pa.exercice_id = e.id) ORDER BY oe.ordre",
                    (premier["id"], p["id"])):
                out.append({"sequence": sn["sequence_code"], "partie": p["numero"],
                            "etat_sequence": sn["etat_code"], "exercice_id": e["id"],
                            "code_ae": f"AE{int(e['num'] or 0):02d}", "titre": e["titre"] or "",
                            "objectif_depart": f"{sn['sequence_code']}-{premier['code']}",
                            "objectif_id_depart": premier["id"], "cours_id": cours[0]["id"],
                            "cours": f"{sn['sequence_code']}-{code_c}"})
    return out


def appliquer(conn, liste: list[dict]) -> list[dict]:
    """Déplace les activités des séquences non validées ; journal des
    opérations (pour un retour arrière manuel)."""
    ops = []
    for c in liste:
        if c["etat_sequence"] == "valide":
            continue
        r = conn.execute("SELECT ordre FROM objectif_exos WHERE objectif_id = ? AND "
                         "serie = 'AE' AND exercice_id = ?",
                         (c["objectif_id_depart"], c["exercice_id"])).fetchone()
        conn.execute("DELETE FROM objectif_exos WHERE objectif_id = ? AND serie = 'AE' AND "
                     "exercice_id = ?", (c["objectif_id_depart"], c["exercice_id"]))
        deja = conn.execute("SELECT 1 FROM objectif_exos WHERE objectif_id = ? AND "
                            "serie = 'AE' AND exercice_id = ?",
                            (c["cours_id"], c["exercice_id"])).fetchone()
        if deja is None:
            k = conn.execute("SELECT COALESCE(MAX(ordre), 0) + 1 FROM objectif_exos WHERE "
                             "objectif_id = ? AND serie = 'AE'", (c["cours_id"],)).fetchone()[0]
            conn.execute("INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) "
                         "VALUES (?, 'AE', ?, ?)", (c["cours_id"], c["exercice_id"], k))
        conn.execute("UPDATE exercices SET mtime = ? WHERE id = ?",
                     (_maintenant(), c["exercice_id"]))
        ops.append({**{k: c[k] for k in ("sequence", "partie", "exercice_id", "code_ae",
                                          "objectif_depart", "cours")},
                    "ordre_depart": r[0] if r else None, "lien_cours_existait": deja is not None})
    return ops


def rapport_texte(niveau: str, liste: list[dict], ops: list[dict] | None) -> str:
    L = [f"== Activités de découverte à ranger sous « Cours » ({niveau}) =="]
    if not liste:
        return "\n".join(L + ["  rien à faire (aucune activité sous le premier objectif "
                              "d'une partie)"])
    for c in liste:
        etat = " — séquence validée : non déplacée (la repasser en cours)" \
            if c["etat_sequence"] == "valide" else ""
        L.append(f"  {c['sequence']} partie {c['partie']} : {c['code_ae']} « {c['titre']} » "
                 f"{c['objectif_depart']} → {c['cours']}{etat}")
    bloquees = sorted({c["sequence"] for c in liste if c["etat_sequence"] == "valide"})
    L.append(f"  {len(liste)} activité(s), dont {len(liste) - sum(c['etat_sequence'] == 'valide' for c in liste)} "
             "déplaçable(s)")
    if bloquees:
        L.append(f"  séquences validées (lecture seule) : {', '.join(bloquees)}")
    if ops is not None:
        L.append(f"  appliqué : {len(ops)} activité(s) déplacée(s) ; livret et corrigés des "
                 "séquences concernées à recompiler")
    return "\n".join(L)


def resoudre_base(db: str | None) -> Path:
    if db:
        return Path(db).resolve()
    from services.bascule import NOM_DB, dossier_par_defaut
    return dossier_par_defaut(RACINE_APPLI, "atelier") / NOM_DB


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Activités de découverte → objectif « Cours ».")
    ap.add_argument("--niveau", default="N11")
    ap.add_argument("--db")
    ap.add_argument("--sequences", default="")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args(argv)
    if a.niveau in NIVEAUX_EXCLUS:
        print(f"Refus : {a.niveau} exclu (les lots de 6e rangent leurs activités sous leur "
              "objectif à dessein).")
        return 2
    db = resoudre_base(a.db)
    if not db.is_file():
        print(f"Base introuvable : {db}")
        return 2
    seqs = [s.strip() for s in a.sequences.split(",") if s.strip()] or None
    if not a.apply:
        src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            liste = candidats(src, a.niveau, seqs)
        finally:
            src.close()
        print(rapport_texte(a.niveau, liste, None))
        print("\nEssai à blanc : rien n'est écrit. Relancer avec --apply pour appliquer.")
        return 0
    conn = sqlite3.connect(db)
    try:
        liste = candidats(conn, a.niveau, seqs)
        if not any(c["etat_sequence"] != "valide" for c in liste):
            print(rapport_texte(a.niveau, liste, []))
            return 0
        print(rapport_texte(a.niveau, liste, None))
        if not a.yes and input("Appliquer ? (o/N) ").strip().lower() not in ("o", "oui"):
            return 1
        d = db.parent / "sauvegardes"
        d.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        cible = d / f"avant_ae_cours_{a.niveau}_{stamp}.db"
        dst = sqlite3.connect(cible)
        conn.backup(dst)
        dst.close()
        try:
            ops = appliquer(conn, liste)
            conn.commit()
        except Exception as e:                                  # pragma: no cover
            conn.rollback()
            print(f"Erreur, rien n'est écrit : {e}")
            return 3
        (d / f"journal_ae_cours_{a.niveau}_{stamp}.json").write_text(
            json.dumps({"niveau": a.niveau, "sauvegarde": str(cible), "operations": ops},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        print(rapport_texte(a.niveau, liste, ops))
        print(f"Sauvegarde : {cible}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
