"""
importer_arborescence.py — Scanne une arborescence de suivi et importe
toutes les classes trouvées en base.

ARBORESCENCE ATTENDUE
---------------------
<racine>/
  <annee>/                         ex: 2024-2025
    <etablissement>/               ex: Collège Les Hautes Ourmes
      <classe>/                    ex: 5e2
        Suivi_eleves/              (obligatoire)
          liste_eleves.csv
          S01suivi.csv … S14suivi.csv
          Sem1-sequences.csv, Sem2-sequences.csv, FinAnnee-sequences.csv
          Periodes.CSV (ignoré par l'import)
          …
        SequencesDB/               (obligatoire)
          N10S01Objectifs.csv …
          N10S01Connaissances.csv …
          FinAnnee-sequences.csv (éventuel doublon de Suivi_eleves, ignoré)
        autres fichiers/dossiers ignorés (plans de travail, Blason, etc.)

Un sous-dossier de <etablissement>/ est considéré comme une classe SI
et seulement si il contient à la fois Suivi_eleves/ ET SequencesDB/.
Les autres (Club Espace, Découverte des métiers, etc.) sont ignorés.

Le NIVEAU (N09/N10/N11/N12) est déduit des fichiers SequencesDB (préfixe
des *Objectifs.csv), pas du nom de classe — plus fiable.

UTILISATION
-----------
Depuis le dossier appli/ :

  # Dry-run : scanne et affiche ce qui serait importé, sans toucher à la DB
  python importer_arborescence.py --racine F:/Suivi --dry-run

  # Import réel (skip les classes déjà en base)
  python importer_arborescence.py --racine F:/Suivi

  # Forcer la réimport : supprime d'abord les classes déjà en base
  # (pour le même triplet nom+étab+année)
  python importer_arborescence.py --racine F:/Suivi --force

  # N'importer qu'une année précise
  python importer_arborescence.py --racine F:/Suivi --annee 2024-2025

Utilise la configuration actuelle de l'appli (USE_SQLITE, data/).
"""

from __future__ import annotations
import argparse
import os
import sys
import re
from pathlib import Path


# Injecter le dossier appli/ dans le path pour importer les modules internes
_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))


# ── Détection ─────────────────────────────────────────────────────────────────

def est_dossier_classe(dossier: Path) -> bool:
    """Une classe a à la fois Suivi_eleves/ et SequencesDB/ comme sous-dossiers."""
    return (dossier / "Suivi_eleves").is_dir() and (dossier / "SequencesDB").is_dir()


def deduire_niveau(sequencesdb: Path) -> str | None:
    """
    Déduit le niveau (N09/N10/N11/N12) depuis les fichiers N1XS*Objectifs.csv
    du dossier SequencesDB. Retourne None si aucun fichier reconnu.
    """
    prefixes = set()
    for f in sequencesdb.glob("N[01][0-9]S*Objectifs.csv"):
        m = re.match(r"(N\d{2})S\d+Objectifs\.csv", f.name)
        if m:
            prefixes.add(m.group(1))
    if len(prefixes) == 1:
        return prefixes.pop()
    if len(prefixes) > 1:
        # Incohérence : plusieurs niveaux dans le même SequencesDB, on prend
        # le plus fréquent
        compteur: dict[str, int] = {}
        for f in sequencesdb.glob("N[01][0-9]S*Objectifs.csv"):
            m = re.match(r"(N\d{2})S", f.name)
            if m:
                compteur[m.group(1)] = compteur.get(m.group(1), 0) + 1
        return max(compteur, key=compteur.get) if compteur else None
    return None


def scanner_arborescence(racine: Path, annee_filtre: str | None = None) -> list[dict]:
    """
    Parcourt la racine et retourne la liste des classes détectées.
    Chaque entrée : {annee, etablissement, nom_classe, niveau, chemin_classe,
                     chemin_suivi, chemin_sequencesdb}.
    """
    classes = []
    if not racine.is_dir():
        raise FileNotFoundError(f"Racine introuvable : {racine}")

    for dossier_annee in sorted(racine.iterdir()):
        if not dossier_annee.is_dir():
            continue
        annee = dossier_annee.name
        # Filtre sur format AAAA-AAAA (4 chiffres + tiret + 4 chiffres)
        if not re.match(r"\d{4}-\d{4}$", annee):
            continue
        if annee_filtre and annee != annee_filtre:
            continue

        for dossier_etab in sorted(dossier_annee.iterdir()):
            if not dossier_etab.is_dir():
                continue
            etablissement = dossier_etab.name

            for dossier_cls in sorted(dossier_etab.iterdir()):
                if not dossier_cls.is_dir():
                    continue
                if not est_dossier_classe(dossier_cls):
                    continue

                niveau = deduire_niveau(dossier_cls / "SequencesDB")
                if not niveau:
                    # Impossible de déterminer le niveau : on note l'info
                    # mais on marque comme "non importable"
                    classes.append({
                        "annee":          annee,
                        "etablissement":  etablissement,
                        "nom_classe":     dossier_cls.name,
                        "niveau":         None,
                        "chemin_classe":  dossier_cls,
                        "chemin_suivi":   dossier_cls / "Suivi_eleves",
                        "chemin_sequencesdb": dossier_cls / "SequencesDB",
                        "erreur_detection": "niveau indéterminé (pas de N1XS*Objectifs.csv)",
                    })
                    continue

                classes.append({
                    "annee":          annee,
                    "etablissement":  etablissement,
                    "nom_classe":     dossier_cls.name,
                    "niveau":         niveau,
                    "chemin_classe":  dossier_cls,
                    "chemin_suivi":   dossier_cls / "Suivi_eleves",
                    "chemin_sequencesdb": dossier_cls / "SequencesDB",
                })

    return classes


# ── Import ────────────────────────────────────────────────────────────────────

def cle_norm(nom, etab, annee):
    """Clé de doublon normalisée (même logique que la route d'import)."""
    def _n(s): return (s or "").strip().casefold()
    return (_n(nom), _n(etab), _n(annee))


def importer_toutes(classes: list[dict], store, force: bool = False,
                     verbose: bool = False) -> dict:
    """
    Importe chaque classe détectée dans la base.

    Retourne un dict de résumé : {importees, ignorees_doublons,
    ignorees_erreur_detection, echecs}.
    """
    from importers.sequencesdb import (
        importer_classe_historique,
        suivi_historique_vers_niveaux,
    )

    rapport = {
        "importees": [],
        "ignorees_doublons": [],
        "ignorees_erreur_detection": [],
        "echecs": [],
    }

    # Index des classes existantes par clé normalisée
    classes_existantes = store.lire_classes().get("classes", [])
    index_existantes = {
        cle_norm(c.get("nom"), c.get("etablissement"), c.get("annee")): c
        for c in classes_existantes
    }

    for entry in classes:
        label = f"{entry['annee']} / {entry['etablissement']} / {entry['nom_classe']}"

        if entry.get("erreur_detection"):
            rapport["ignorees_erreur_detection"].append({
                **entry,
                "raison": entry["erreur_detection"],
            })
            print(f"  ⊘ {label} — {entry['erreur_detection']}")
            continue

        cle = cle_norm(entry["nom_classe"], entry["etablissement"], entry["annee"])
        if cle in index_existantes:
            if not force:
                rapport["ignorees_doublons"].append(entry)
                print(f"  = {label} — déjà en base (skip)")
                continue
            # Mode --force : supprimer la classe existante avant réimport
            ancienne = index_existantes[cle]
            cid_ancien = ancienne["id"]
            print(f"  ⟳ {label} — suppression de l'existant ({cid_ancien})")
            _supprimer_classe(store, cid_ancien)

        try:
            result = importer_classe_historique(
                chemin_classe=str(entry["chemin_suivi"]),
                chemin_sequencesdb=str(entry["chemin_sequencesdb"]),
                niveau=entry["niveau"],
                annee=entry["annee"],
                nom_classe=entry["nom_classe"],
                etablissement=entry["etablissement"],
                store=store,
            )
        except Exception as e:
            rapport["echecs"].append({**entry, "erreur": str(e)})
            print(f"  ✗ {label} — ERREUR : {e}")
            continue

        # Persister — même séquence que /api/import/historique
        prog = result["progression"]
        store.ecrire_progression(prog)
        # IMPORTANT : ecrire_progression fait un upsert par clé métier
        # (niveau, annee, etablissement). Si une progression existe déjà pour
        # cette clé, son id opaque est préservé et `prog["id"]` est mis à jour
        # pour refléter l'id réel en base. La classe a été construite avec
        # l'id pré-upsert, il faut donc resynchroniser son progression_id.
        classe = result["classe"]
        classe["progression_id"] = prog["id"]
        classes_data = store.lire_classes()
        classes_data["classes"].append(classe)
        store.ecrire_classes(classes_data)

        # Note : on ne persiste plus le fichier JSON d'archive
        # suivi_historique_<classe_id>_<annee>.json — il n'était jamais
        # relu par l'application. Les niveaux sont directement injectés
        # dans niveaux.json ci-dessous, ce qui est suffisant.

        niveaux_convertis = suivi_historique_vers_niveaux(result["suivi"])
        niveaux_existants = store.lire_niveaux()
        cid = classe["id"]
        niveaux_existants.setdefault(cid, {})
        for seq_code, eleves_niv in niveaux_convertis.items():
            niveaux_existants[cid].setdefault(seq_code, {})
            for eid, objs in eleves_niv.items():
                niveaux_existants[cid][seq_code].setdefault(eid, {})
                niveaux_existants[cid][seq_code][eid].update(objs)
        store.ecrire_niveaux(niveaux_existants)

        nb_eleves = len(result["eleves"])
        nb_creneaux = len(prog["creneaux"])
        nb_erreurs = len(result["erreurs"])
        ref_id = result.get("referentiel_id") or ""
        tag = f"{nb_eleves} élèves · {nb_creneaux} créneaux"
        if ref_id:
            tag += f" · ref={ref_id}"
        if nb_erreurs:
            tag += f" · {nb_erreurs} avert."
        print(f"  ✓ {label} — {tag}")

        # Afficher le détail des avertissements si demandé, OU automatiquement
        # quand l'import aboutit à 0 créneaux (indicateur probable d'un problème).
        if nb_erreurs and (verbose or nb_creneaux == 0):
            for e in result["erreurs"]:
                print(f"      ⚠ {e}")

        rapport["importees"].append({
            **entry,
            "classe_id": classe["id"],
            "eleves":    nb_eleves,
            "creneaux":  nb_creneaux,
            "erreurs":   nb_erreurs,
            "avertissements": list(result["erreurs"]),
            "referentiel_id": ref_id,
        })

    return rapport


def _supprimer_classe(store, cid: str):
    """Supprime une classe et ses suivis, compatible JsonStore et SqliteStore."""
    if hasattr(store, "supprimer_donnees_classe"):
        store.supprimer_donnees_classe(cid)
    else:
        data = store.lire_classes()
        data["classes"] = [c for c in data.get("classes", []) if c["id"] != cid]
        store.ecrire_classes(data)
        suivi = store.lire_suivi()
        suivi.pop(cid, None)
        store.ecrire_suivi(suivi)
        niveaux = store.lire_niveaux()
        niveaux.pop(cid, None)
        store.ecrire_niveaux(niveaux)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import en lot d'une arborescence de suivi.",
    )
    parser.add_argument("--racine", required=True,
                        help="Dossier racine contenant les années.")
    parser.add_argument("--annee",
                        help="Filtrer sur une année précise (ex: 2024-2025).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Lister ce qui serait importé sans rien modifier.")
    parser.add_argument("--force", action="store_true",
                        help="Supprimer les classes déjà en base avant de réimporter.")
    parser.add_argument("--data-dir", default="data",
                        help="Dossier data de l'appli (défaut : ./data).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Afficher le détail des avertissements pour "
                             "toutes les classes (pas seulement celles à 0 créneaux).")
    args = parser.parse_args()

    racine = Path(args.racine).resolve()
    if not racine.is_dir():
        print(f"✗ Racine introuvable : {racine}")
        return 2

    # Scan
    print(f"Scan de {racine}…")
    try:
        classes = scanner_arborescence(racine, annee_filtre=args.annee)
    except FileNotFoundError as e:
        print(f"✗ {e}")
        return 2

    if not classes:
        print("Aucune classe détectée.")
        return 0

    print(f"{len(classes)} classe(s) détectée(s) :")
    for c in classes:
        niv = c.get("niveau") or "???"
        suffix = f"  ⚠ {c['erreur_detection']}" if c.get("erreur_detection") else ""
        print(f"  [{niv}] {c['annee']} / {c['etablissement']} / {c['nom_classe']}{suffix}")

    if args.dry_run:
        print("\n[dry-run] Aucune modification apportée.")
        return 0

    # Charger le store
    data_dir = Path(args.data_dir).resolve()
    from persistence.sqlite_store import SqliteStore
    store = SqliteStore(data_dir)
    print(f"\nMode : SQLite ({data_dir / 'seqenseigne.db'})")

    print(f"Import{' (avec --force)' if args.force else ''} :")
    rapport = importer_toutes(classes, store, force=args.force, verbose=args.verbose)

    print()
    print(f"=== Résumé ===")
    print(f"  Importées             : {len(rapport['importees'])}")
    print(f"  Ignorées (doublons)   : {len(rapport['ignorees_doublons'])}")
    print(f"  Ignorées (détection)  : {len(rapport['ignorees_erreur_detection'])}")
    print(f"  Échecs                : {len(rapport['echecs'])}")

    # Récap par référentiel : combien de classes se sont partagé chacun ?
    refs = {}
    for c in rapport["importees"]:
        rid = c.get("referentiel_id") or "(aucun)"
        refs.setdefault(rid, []).append(f"{c['annee']}/{c['nom_classe']}")
    if refs:
        print(f"\n  Référentiels utilisés : {len(refs)}")
        for rid, classes_list in sorted(refs.items()):
            print(f"    {rid} ← {len(classes_list)} classe(s)")
            if args.verbose:
                for cl in classes_list:
                    print(f"        · {cl}")

    if rapport["echecs"]:
        print("\nÉchecs détaillés :")
        for e in rapport["echecs"]:
            print(f"  - {e['annee']}/{e['etablissement']}/{e['nom_classe']} : {e['erreur']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
