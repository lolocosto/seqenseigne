#!/usr/bin/env python3
"""
migrer.py — migration des données de l'ancienne structure vers seqenseigne/

Usage :
  python migrer.py --source "E:\\Enseignement_new\\appli de suivi\\data" \
                   --dest   "E:\\Enseignement\\seqenseigne" \
                   --annee  "2024-2025"

Ce script convertit :
  classes.json  → annees/{annee}/classes.json
  suivi.json    → annees/{annee}/suivi_{classe_id}.json  (un par classe)
  niveaux.json  → annees/{annee}/niveaux_{classe_id}.json (un par classe)
"""

import argparse
import json
from pathlib import Path


def migrer(source_dir: Path, dest_dir: Path, annee: str):
    annee_dir = dest_dir / "annees" / annee
    annee_dir.mkdir(parents=True, exist_ok=True)

    erreurs = []

    # ── 1. classes.json ──────────────────────────────────────────────────────
    src_classes = source_dir / "classes.json"
    if not src_classes.exists():
        print(f"⚠  classes.json introuvable dans {source_dir}")
        erreurs.append("classes.json manquant")
    else:
        old = json.loads(src_classes.read_text(encoding="utf-8"))

        # Ancienne structure : {"classes": [...]}
        # ou encore plus ancienne : {"niveau":"N10","eleves":[...]} (fichier unique)
        if "classes" in old:
            classes_list = old["classes"]
        elif "eleves" in old:
            # Cas d'une seule classe (très ancien format)
            classes_list = [{
                "id":             "CLASSE",
                "nom":            old.get("classe", "Classe"),
                "niveau":         old.get("niveau", "N11"),
                "annee":          annee,
                "etablissement":  old.get("etablissement", ""),
                "eleves":         old.get("eleves", []),
                "versions_actives":    {},
                "sequences_verouillees": [],
            }]
        else:
            print(f"⚠  Format classes.json non reconnu")
            classes_list = []
            erreurs.append("format classes.json inconnu")

        new_classes = {"annee": annee, "classes": classes_list}
        dest_f = annee_dir / "classes.json"
        dest_f.write_text(json.dumps(new_classes, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓  classes.json → {dest_f} ({len(classes_list)} classe(s))")

    # ── 2. suivi.json ─────────────────────────────────────────────────────────
    src_suivi = source_dir / "suivi.json"
    if not src_suivi.exists():
        print(f"⚠  suivi.json introuvable")
    else:
        old_suivi = json.loads(src_suivi.read_text(encoding="utf-8"))

        # Ancienne structure : { classe_id: { seq: { eleve_id: {F,A,E,cours} } } }
        # Nouvelle structure : un fichier suivi_{classe_id}.json par classe
        #                      contenu : { seq: { eleve_id: {F,A,E,cours} } }
        for classe_id, data in old_suivi.items():
            dest_f = annee_dir / f"suivi_{classe_id.lower()}.json"
            dest_f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            nb_seqs = len(data)
            print(f"✓  suivi {classe_id} → {dest_f.name} ({nb_seqs} séquences)")

    # ── 3. niveaux.json ───────────────────────────────────────────────────────
    src_niveaux = source_dir / "niveaux.json"
    if not src_niveaux.exists():
        print(f"⚠  niveaux.json introuvable")
    else:
        old_niveaux = json.loads(src_niveaux.read_text(encoding="utf-8"))

        # Même logique que suivi
        for classe_id, data in old_niveaux.items():
            dest_f = annee_dir / f"niveaux_{classe_id.lower()}.json"
            dest_f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            nb_seqs = len(data)
            print(f"✓  niveaux {classe_id} → {dest_f.name} ({nb_seqs} séquences)")

    # ── 4. versions.json (reste dans appli/data/) ────────────────────────────
    src_versions = source_dir / "versions.json"
    dest_versions = dest_dir / "appli" / "data" / "versions.json"
    if src_versions.exists():
        dest_versions.parent.mkdir(parents=True, exist_ok=True)
        dest_versions.write_text(src_versions.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"✓  versions.json → {dest_versions}")
    else:
        if not dest_versions.exists():
            dest_versions.write_text("{}", encoding="utf-8")
            print(f"✓  versions.json créé vide")

    # ── Résumé ────────────────────────────────────────────────────────────────
    print()
    if erreurs:
        print(f"Migration terminée avec {len(erreurs)} avertissement(s) :")
        for e in erreurs:
            print(f"  ⚠  {e}")
    else:
        print("Migration terminée sans erreur.")
    print(f"\nFichiers dans : {annee_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migration données seqenseigne")
    parser.add_argument("--source", required=True,
                        help="Dossier data/ de l'ancienne appli")
    parser.add_argument("--dest",   required=True,
                        help="Dossier racine seqenseigne/")
    parser.add_argument("--annee",  default="2024-2025",
                        help="Année scolaire à associer aux données (ex: 2024-2025)")
    args = parser.parse_args()

    migrer(
        source_dir=Path(args.source),
        dest_dir=Path(args.dest),
        annee=args.annee,
    )
