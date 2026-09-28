#!/usr/bin/env python3
"""outils/migrer_v0_19_0_progressions.py — v0.19.0

Migration de schéma pour le réalignement des progressions sur le référentiel.

Trois opérations, dans une seule transaction :

1. **Table `progressions`** recréée sans la colonne `source` (héritage
   SequenceDB, plus aucune distinction entre progressions — décision v0.19.0)
   et avec l'état `annule` ajouté à la contrainte CHECK (suppression logique
   d'une progression : on ne supprime plus physiquement, on passe `annule`).

   Avant : etat CHECK IN ('en_cours','valide','verrouille')
   Après : etat CHECK IN ('en_cours','valide','verrouille','annule')

2. **Rétroactif** : tout référentiel actuellement référencé par au moins une
   progression passe à l'état `utilise` (cohérence avec la règle v0.19.0 :
   créer une progression sur un référentiel le fait passer verrouille→utilise,
   et un référentiel `utilise` n'est plus déverrouillable).

Sécurités : dry-run par défaut, --apply + confirmation 'OUI' (ou --yes),
vérification post-migration (colonne source absente, CHECK étendu, 0
référentiel verrouillé encore référencé par une progression).

Usage :
    python -m outils.migrer_v0_19_0_progressions            # dry-run
    python -m outils.migrer_v0_19_0_progressions --apply
    python -m outils.migrer_v0_19_0_progressions --apply --yes

Codes de sortie : 0 succès, 1 annulé, 2 base introuvable, 3 erreur.
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

_DDL_PROGRESSIONS_CIBLE = """
CREATE TABLE progressions (
    id               TEXT PRIMARY KEY,
    niveau           TEXT NOT NULL,
    annee            TEXT NOT NULL,
    etablissement_id TEXT NOT NULL REFERENCES etablissements(id) ON DELETE RESTRICT,
    referentiel_id   TEXT REFERENCES referentiel_niveaux(id) ON DELETE RESTRICT,
    etat             TEXT NOT NULL DEFAULT 'en_cours'
                          CHECK (etat IN ('en_cours','valide','verrouille','annule')),
    UNIQUE (niveau, annee, etablissement_id)
)
"""


def _chemin_db_par_defaut() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "seqenseigne.db"


def _colonne_source_presente(conn) -> bool:
    cols = [c[1] for c in conn.execute("PRAGMA table_info(progressions)").fetchall()]
    return "source" in cols


def _refs_a_promouvoir(conn) -> list[tuple[str, str]]:
    """Référentiels référencés par >=1 progression et pas encore 'utilise'."""
    rows = conn.execute(
        """SELECT DISTINCT p.referentiel_id, r.etat
             FROM progressions p
             JOIN referentiel_niveaux r ON r.id = p.referentiel_id
            WHERE p.referentiel_id IS NOT NULL
              AND r.etat != 'utilise'"""
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _migrer(conn) -> dict:
    rapport = {"table_recreee": False, "refs_promus": []}

    # 1. Recréer `progressions` sans `source`, avec CHECK étendu.
    #    Méthode SQLite sûre pour les FK ENTRANTES (creneaux ET classes
    #    référencent progressions.id) : on crée une table neuve sous un nom
    #    temporaire, on copie, on supprime l'ancienne, puis on renomme la
    #    neuve. On NE renomme PAS l'ancienne d'abord (cela ferait suivre les
    #    FK enfants vers le nom temporaire, puis les casserait au DROP).
    #    foreign_keys=OFF pendant la bascule ; réactivé + contrôlé après.
    if _colonne_source_presente(conn):
        conn.execute("PRAGMA foreign_keys = OFF")
        ddl_tmp = _DDL_PROGRESSIONS_CIBLE.replace(
            "CREATE TABLE progressions", "CREATE TABLE _progressions_new")
        conn.executescript(ddl_tmp)
        conn.execute(
            """INSERT INTO _progressions_new
                 (id, niveau, annee, etablissement_id, referentiel_id, etat)
               SELECT id, niveau, annee, etablissement_id, referentiel_id, etat
                 FROM progressions"""
        )
        conn.execute("DROP TABLE progressions")
        conn.execute("ALTER TABLE _progressions_new RENAME TO progressions")
        # Contrôle d'intégrité référentielle avant de réactiver.
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise sqlite3.IntegrityError(
                f"FK cassées après recréation : {violations[:5]}")
        conn.execute("PRAGMA foreign_keys = ON")
        rapport["table_recreee"] = True

    # 2. Rétroactif : promouvoir les référentiels référencés à 'utilise'.
    for ref_id, etat_avant in _refs_a_promouvoir(conn):
        conn.execute(
            "UPDATE referentiel_niveaux SET etat = 'utilise' WHERE id = ?",
            (ref_id,),
        )
        rapport["refs_promus"].append((ref_id, etat_avant))

    return rapport


def _verifier(conn) -> list[str]:
    pbs = []
    if _colonne_source_presente(conn):
        pbs.append("la colonne `source` est toujours présente")
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='progressions'"
    ).fetchone()[0]
    if "annule" not in ddl:
        pbs.append("le CHECK n'inclut pas l'état `annule`")
    # 0 référentiel encore 'verrouille' (ou autre) alors qu'il est référencé.
    restants = _refs_a_promouvoir(conn)
    if restants:
        pbs.append(f"{len(restants)} référentiel(s) référencé(s) pas encore 'utilise'")
    return pbs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Migration progressions v0.19.0.")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    db = args.db or _chemin_db_par_defaut()
    if not db.exists():
        print(f"[ERREUR] Base introuvable : {db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        source_presente = _colonne_source_presente(conn)
        refs = _refs_a_promouvoir(conn)
        print(f"Base : {db}")
        print(f"  colonne `source` à retirer : {'oui' if source_presente else 'non (déjà fait)'}")
        print(f"  référentiels à promouvoir 'utilise' : {len(refs)}")
        for ref_id, etat in refs:
            print(f"    - {ref_id} ({etat} → utilise)")

        if not source_presente and not refs:
            print("Rien à migrer. Base déjà à jour.")
            return 0

        if not args.apply:
            print("\n[DRY-RUN] Aucune modification. Relancer avec --apply.")
            return 0

        if not args.yes:
            if input("\nConfirmer la migration ? Taper 'OUI' : ").strip() != "OUI":
                print("Migration annulée.")
                return 1

        rapport = _migrer(conn)
        conn.commit()
        print("\nMigration appliquée :")
        print(f"  table progressions recréée : {rapport['table_recreee']}")
        print(f"  référentiels promus 'utilise' : {len(rapport['refs_promus'])}")

        pbs = _verifier(conn)
        if pbs:
            print("\n[ERREUR] Vérification post-migration :", file=sys.stderr)
            for p in pbs:
                print(f"  - {p}", file=sys.stderr)
            return 3
        print("\nVérification OK.")
        return 0
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[ERREUR] SQL : {e}", file=sys.stderr)
        return 3
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
