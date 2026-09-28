#!/usr/bin/env python3
"""outils/verifier_md5.py — Vérification d'intégrité MD5

Compare le MD5 et la taille des fichiers présents sur disque avec un
fichier de référence (MANIFEST.md5 ou appli_inventaire.txt). Signale
les divergences, les manquants et les fichiers tronqués.

Format du fichier de référence
------------------------------
Une ligne par fichier, séparateurs : deux espaces consécutifs (compatible
avec la sortie de `md5sum` Linux et le format historique
`appli_inventaire.txt` généré côté Windows) :

    <md5>  <taille_octets>  <chemin_relatif>

Exemple :
    3588b4247231cf74447f249546de53aa  58461  services\\latex_rendu_atome.py

Les chemins peuvent utiliser `/` ou `\\` indifféremment : la
normalisation est faite au moment de la comparaison.

Encodage attendu : UTF-8, avec ou sans BOM.

Usage
-----
    # Vérifier l'arborescence courante contre MANIFEST.md5 :
    python -m outils.verifier_md5

    # Spécifier un autre fichier de référence :
    python -m outils.verifier_md5 --manifest appli_inventaire.txt

    # Spécifier la racine (par défaut : répertoire courant) :
    python -m outils.verifier_md5 --racine D:\\Enseignement\\seqenseigne\\appli

    # Ne signaler que les divergences (pas la liste des OK) :
    python -m outils.verifier_md5 --silencieux

    # Sortie machine-friendly (une ligne par divergence, format CSV) :
    python -m outils.verifier_md5 --csv > rapport.csv

    # Régénérer le fichier de référence à partir de l'arborescence
    # courante (utile après une livraison validée) :
    python -m outils.verifier_md5 --generer --extensions .py,.js,.css,.html,.sql,.bat

Codes de sortie
---------------
    0  : aucune divergence
    1  : au moins un fichier divergent ou manquant
    2  : fichier de référence introuvable ou illisible
"""

from __future__ import annotations
import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Forcer UTF-8 sur stdout/stderr — robustesse cross-platform (cf. fix
# sur scripts/migrer_methodes_objectifs.py)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ---------- Modèle ---------------------------------------------------------

@dataclass(frozen=True)
class EntreeManifest:
    """Une ligne du manifeste : md5 + taille attendue + chemin relatif."""
    md5: str
    taille: int
    chemin: str  # relatif à la racine, séparateur normalisé en '/'


@dataclass
class Divergence:
    """Décrit un écart entre le manifeste et l'arborescence."""
    chemin: str
    type_: str  # 'manquant', 'taille', 'md5', 'inattendu'
    md5_attendu: str | None = None
    md5_reel: str | None = None
    taille_attendue: int | None = None
    taille_reelle: int | None = None


# ---------- Lecture du manifeste ------------------------------------------

def charger_manifest(chemin_manifest: Path) -> list[EntreeManifest]:
    """Lit le fichier de référence et retourne la liste des entrées.

    Tolère :
    - BOM UTF-8 en tête
    - Séparateurs '/' ou '\\\\' dans les chemins
    - Lignes vides ou commençant par '#' (commentaires)
    """
    if not chemin_manifest.is_file():
        raise FileNotFoundError(f"Manifeste introuvable : {chemin_manifest}")

    entrees: list[EntreeManifest] = []
    contenu = chemin_manifest.read_text(encoding="utf-8-sig")  # gère le BOM

    for num, ligne in enumerate(contenu.splitlines(), 1):
        ligne = ligne.rstrip()
        if not ligne or ligne.lstrip().startswith("#"):
            continue
        # Format : md5 + 2 espaces + taille + 2 espaces + chemin
        # Mais on tolère 1 ou plusieurs espaces pour robustesse.
        parties = ligne.split(maxsplit=2)
        if len(parties) != 3:
            print(f"⚠ ligne {num} ignorée (format invalide) : {ligne!r}",
                  file=sys.stderr)
            continue
        md5_str, taille_str, chemin_brut = parties
        try:
            taille = int(taille_str)
        except ValueError:
            print(f"⚠ ligne {num} ignorée (taille non numérique) : {ligne!r}",
                  file=sys.stderr)
            continue
        # Normaliser séparateur de chemin
        chemin = chemin_brut.replace("\\", "/")
        entrees.append(EntreeManifest(
            md5=md5_str.lower(), taille=taille, chemin=chemin
        ))

    return entrees


# ---------- Calcul des MD5 ------------------------------------------------

def calculer_md5(chemin: Path, taille_bloc: int = 65536) -> str:
    """Calcule le MD5 d'un fichier en streaming (gère les gros fichiers)."""
    h = hashlib.md5()
    with chemin.open("rb") as f:
        while True:
            bloc = f.read(taille_bloc)
            if not bloc:
                break
            h.update(bloc)
    return h.hexdigest()


# ---------- Vérification --------------------------------------------------

def verifier(racine: Path,
             entrees: list[EntreeManifest]) -> list[Divergence]:
    """Compare chaque entrée du manifeste à l'état réel sur disque.

    Ne détecte PAS les fichiers en trop (sur disque mais hors manifeste) —
    voir `lister_inattendus()` pour ça.
    """
    divergences: list[Divergence] = []
    for entree in entrees:
        chemin_disque = racine / entree.chemin

        if not chemin_disque.is_file():
            divergences.append(Divergence(
                chemin=entree.chemin,
                type_="manquant",
                md5_attendu=entree.md5,
                taille_attendue=entree.taille,
            ))
            continue

        taille_reelle = chemin_disque.stat().st_size

        if taille_reelle != entree.taille:
            # Optimisation : si la taille diffère, le MD5 va forcément
            # différer aussi, on ne le calcule pas.
            divergences.append(Divergence(
                chemin=entree.chemin,
                type_="taille",
                md5_attendu=entree.md5,
                taille_attendue=entree.taille,
                taille_reelle=taille_reelle,
            ))
            continue

        md5_reel = calculer_md5(chemin_disque)
        if md5_reel != entree.md5:
            divergences.append(Divergence(
                chemin=entree.chemin,
                type_="md5",
                md5_attendu=entree.md5,
                md5_reel=md5_reel,
                taille_attendue=entree.taille,
                taille_reelle=taille_reelle,
            ))

    return divergences


# ---------- Génération d'un manifeste -------------------------------------

def generer_manifest(racine: Path,
                     extensions: Iterable[str],
                     exclure: Iterable[str] = (
                         "__pycache__", ".pytest_cache", ".git", "data",
                     )) -> str:
    """Parcourt récursivement la racine et produit un manifeste au
    format attendu par `charger_manifest`. Les chemins sont relatifs
    à la racine, avec '/' comme séparateur (portable).
    """
    extensions_norm = {
        e.lower() if e.startswith(".") else f".{e.lower()}"
        for e in extensions
    }
    exclure_set = set(exclure)

    lignes: list[str] = []
    for chemin in sorted(racine.rglob("*")):
        if not chemin.is_file():
            continue
        if chemin.suffix.lower() not in extensions_norm:
            continue
        # Exclure si l'un des composants du chemin est dans exclure_set
        rel = chemin.relative_to(racine)
        if any(p in exclure_set for p in rel.parts):
            continue

        md5 = calculer_md5(chemin)
        taille = chemin.stat().st_size
        # Forcer '/' pour la portabilité
        chemin_str = str(rel).replace("\\", "/")
        lignes.append(f"{md5}  {taille}  {chemin_str}")

    return "\n".join(lignes) + "\n"


# ---------- Affichage -----------------------------------------------------

def afficher_rapport(divergences: list[Divergence],
                     total_verifies: int,
                     csv: bool = False) -> None:
    """Affiche le rapport des divergences (lisible ou CSV)."""
    if csv:
        print("type;chemin;taille_attendue;taille_reelle;md5_attendu;md5_reel")
        for d in divergences:
            print(";".join([
                d.type_,
                d.chemin,
                str(d.taille_attendue) if d.taille_attendue is not None else "",
                str(d.taille_reelle) if d.taille_reelle is not None else "",
                d.md5_attendu or "",
                d.md5_reel or "",
            ]))
        return

    if not divergences:
        print(f"✅ {total_verifies} fichier(s) vérifié(s) — aucune divergence.")
        return

    nb_manquants = sum(1 for d in divergences if d.type_ == "manquant")
    nb_taille = sum(1 for d in divergences if d.type_ == "taille")
    nb_md5 = sum(1 for d in divergences if d.type_ == "md5")

    print(f"❌ {len(divergences)} divergence(s) sur {total_verifies} fichier(s) :")
    print(f"     {nb_manquants} manquant(s), {nb_taille} taille différente, "
          f"{nb_md5} contenu modifié à taille égale")
    print()

    for d in divergences:
        if d.type_ == "manquant":
            print(f"  MANQUANT  {d.chemin}")
            print(f"            (attendu {d.taille_attendue} octets, "
                  f"md5 {d.md5_attendu})")
        elif d.type_ == "taille":
            diff = (d.taille_reelle or 0) - (d.taille_attendue or 0)
            signe = "+" if diff > 0 else ""
            print(f"  TRONQUÉ?  {d.chemin}")
            print(f"            attendu {d.taille_attendue}, "
                  f"trouvé {d.taille_reelle} ({signe}{diff} octets)")
        elif d.type_ == "md5":
            print(f"  MODIFIÉ   {d.chemin}")
            print(f"            md5 attendu  {d.md5_attendu}")
            print(f"            md5 trouvé   {d.md5_reel}")
        print()


# ---------- CLI -----------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vérification d'intégrité MD5 d'une arborescence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("MANIFEST.md5"),
        help="Fichier de référence (par défaut : MANIFEST.md5 dans la racine)",
    )
    parser.add_argument(
        "--racine", type=Path, default=Path("."),
        help="Racine de l'arborescence à vérifier (par défaut : répertoire courant)",
    )
    parser.add_argument(
        "--silencieux", action="store_true",
        help="Ne pas afficher la ligne de bilan si tout est OK (utile pour scripts)",
    )
    parser.add_argument(
        "--csv", action="store_true",
        help="Sortie CSV (une ligne par divergence)",
    )
    parser.add_argument(
        "--generer", action="store_true",
        help="Générer un manifeste à partir de l'arborescence (mode inverse)",
    )
    parser.add_argument(
        "--extensions", default=".py,.js,.css,.html,.sql,.bat",
        help="(--generer uniquement) extensions à inclure, séparées par des virgules",
    )
    args = parser.parse_args()

    racine = args.racine.resolve()
    if not racine.is_dir():
        print(f"❌ Racine introuvable : {racine}", file=sys.stderr)
        return 2

    # Mode génération
    if args.generer:
        extensions = [e.strip() for e in args.extensions.split(",") if e.strip()]
        manifest_str = generer_manifest(racine, extensions)
        chemin_sortie = racine / args.manifest.name \
            if not args.manifest.is_absolute() else args.manifest
        chemin_sortie.write_text(manifest_str, encoding="utf-8")
        nb_lignes = manifest_str.count("\n")
        print(f"✅ Manifeste généré : {chemin_sortie} ({nb_lignes} entrées)")
        return 0

    # Mode vérification
    chemin_manifest = args.manifest if args.manifest.is_absolute() \
        else racine / args.manifest

    try:
        entrees = charger_manifest(chemin_manifest)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    if not entrees:
        print(f"⚠ Manifeste vide ou illisible : {chemin_manifest}", file=sys.stderr)
        return 2

    divergences = verifier(racine, entrees)

    if args.silencieux and not divergences:
        return 0

    afficher_rapport(divergences, len(entrees), csv=args.csv)
    return 1 if divergences else 0


if __name__ == "__main__":
    sys.exit(main())
