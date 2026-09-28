"""scripts/peupler_cartes_n10.py — v0.13.6.2.3

Peuple la table cartes_automatisme avec les ~135 cartes définies dans
`cartes_n10_data.py` pour le niveau N10, séquences S01 à S14.

Stratégie :
  - Chaque carte est créée via `services.cartes_automatisme.creer_carte`,
    PUIS validée via `valider_carte` (ce qui réutilise la validation
    pédagogique métier : recto/verso/lien/variables si paramétrée).
  - Le `lien_id` est résolu dynamiquement par (niveau, sequence, num)
    plutôt que codé en dur, pour rester robuste si le paquet est
    réimporté avec de nouveaux IDs no_xxx/me_xxx.
  - Si une carte avec le même `nom` existe déjà dans la séquence, elle
    est ignorée (idempotence — relancer le script ne crée pas de doublons).
  - Les `num` sont attribués automatiquement par `creer_carte` (max+1).
  - À la fin : compte-rendu détaillé par séquence + total.

Usage :
  cd appli
  python scripts/peupler_cartes_n10.py [--dry-run] [--force]

Options :
  --dry-run : affiche ce qui serait créé sans toucher à la BDD.
  --force   : recrée même les cartes déjà présentes (par défaut : skip
              sur collision de `nom`).

Discipline alpha : la BDD peut être wipée librement, mais ce script
reste idempotent par sécurité.
"""
from __future__ import annotations

import argparse
import os
import sys
import sqlite3
from pathlib import Path

# v0.13.6.3.1 — Forcer UTF-8 sur stdout/stderr.
# Sans ça, sur Windows quand un capteur (pytest, redirection) hérite
# de l'encodage cp1252, les caractères non-ASCII utilisés dans les
# logs ('—', '→', '⚠') font planter le script avec UnicodeEncodeError.
# Pattern repris de outils/verifier_md5.py.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Permettre l'import des services depuis n'importe où dans appli/
HERE = Path(__file__).resolve().parent
APPLI_ROOT = HERE.parent
sys.path.insert(0, str(APPLI_ROOT))

from services import cartes_automatisme as cartes  # noqa: E402
from scripts.cartes_n10_data import (  # noqa: E402
    TOUTES_CARTES_N10,
    COMPTE_PAR_SEQUENCE,
)


NIVEAU = 'N10'
DEFAULT_DB_PATH = APPLI_ROOT / 'data' / 'seqenseigne.db'


# ─────────────────────────────────────────────────────────────────────
# Résolution des liens
# ─────────────────────────────────────────────────────────────────────


def resoudre_lien_id(conn: sqlite3.Connection, niveau: str, sequence: str,
                     lien_type: str, lien_num: int) -> str | None:
    """Résout l'ID d'une notion ou méthode à partir de son numéro
    dans la séquence. Renvoie None si introuvable.
    """
    if lien_type == 'notion':
        # num_connaissance peut être stocké en TEXT zero-padded ('01')
        # ou en INTEGER selon les imports. On essaie les deux formats.
        row = conn.execute(
            "SELECT id FROM notions "
            "WHERE niveau = ? AND sequence = ? "
            "  AND (num_connaissance = ? OR num_connaissance = ?)",
            (niveau, sequence, lien_num, f"{lien_num:02d}"),
        ).fetchone()
    elif lien_type == 'methode':
        # num_methode peut aussi varier en format selon les imports.
        row = conn.execute(
            "SELECT id FROM methodes "
            "WHERE niveau = ? AND sequence = ? "
            "  AND (num_methode = ? OR num_methode = ?)",
            (niveau, sequence, lien_num, f"{lien_num:02d}"),
        ).fetchone()
    else:
        return None
    return row[0] if row else None


# ─────────────────────────────────────────────────────────────────────
# Vérification de doublon
# ─────────────────────────────────────────────────────────────────────


def carte_existe_par_nom(conn: sqlite3.Connection, niveau: str,
                         sequence: str, nom: str) -> str | None:
    """Si une carte avec ce titre existe déjà dans la séquence, renvoie
    son ID. Sinon None.

    v0.13.6.15 : la colonne BdD `nom` a été renommée en `titre`. La
    fonction garde son nom historique et la variable locale `nom` (c'est
    le `nom` du dict de définition des cartes à peupler), seule la
    requête SQL est adaptée à la nouvelle colonne.
    """
    row = conn.execute(
        "SELECT id FROM cartes_automatisme "
        "WHERE niveau = ? AND sequence = ? AND titre = ?",
        (niveau, sequence, nom),
    ).fetchone()
    return row[0] if row else None


# ─────────────────────────────────────────────────────────────────────
# Boucle de peuplement
# ─────────────────────────────────────────────────────────────────────


def peupler(db_path: Path, dry_run: bool = False,
            force: bool = False) -> dict:
    """Itère sur TOUTES_CARTES_N10 et insère + valide.

    Retourne un dict de stats par séquence :
      {'S01': {'crees': N, 'sautes': N, 'erreurs': [...]}, ...}
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    stats: dict[str, dict] = {}

    for carte_def in TOUTES_CARTES_N10:
        seq = carte_def['sequence']
        nom = carte_def['nom']
        stats.setdefault(seq, {'crees': 0, 'sautes': 0,
                               'erreurs': [], 'ids': []})

        # 1. Idempotence : skip si un nom identique existe déjà
        existant_id = carte_existe_par_nom(conn, NIVEAU, seq, nom)
        if existant_id and not force:
            stats[seq]['sautes'] += 1
            print(f"  [SKIP] {NIVEAU}/{seq} — {nom!r} déjà présente "
                  f"({existant_id})")
            continue

        # 2. Résolution du lien
        lien_type_attendu, lien_num = carte_def['lien']
        lien_id = resoudre_lien_id(conn, NIVEAU, seq,
                                   lien_type_attendu, lien_num)
        if lien_id is None:
            err = (f"Lien introuvable : {lien_type_attendu} #{lien_num} "
                   f"dans {NIVEAU}/{seq}")
            stats[seq]['erreurs'].append((nom, err))
            print(f"  [ERR ] {NIVEAU}/{seq} — {nom!r} : {err}")
            continue

        if dry_run:
            stats[seq]['crees'] += 1
            print(f"  [DRY ] {NIVEAU}/{seq} — {nom!r} "
                  f"({carte_def['type_pedago']}/{carte_def['type_tech']}) "
                  f"→ lien {lien_type_attendu}#{lien_num}")
            continue

        # 3. Création
        try:
            carte_creee = cartes.creer_carte(
                conn,
                niveau=NIVEAU,
                sequence=seq,
                type_pedago=carte_def['type_pedago'],
                type_tech=carte_def['type_tech'],
                titre=nom,
                recto=carte_def['recto'],
                verso=carte_def['verso'],
                variables=carte_def['variables'],
                lien_type=lien_type_attendu,
                lien_id=lien_id,
            )
        except cartes.CarteErreur as exc:
            stats[seq]['erreurs'].append((nom, f"création: {exc}"))
            print(f"  [ERR ] {NIVEAU}/{seq} — {nom!r} : "
                  f"création échouée : {exc}")
            continue

        # 4. Validation pédagogique
        try:
            cartes.valider_carte(conn, carte_creee['id'])
        except cartes.CarteErreur as exc:
            details = ""
            if hasattr(exc, 'details') and exc.details.get('raisons'):
                details = " | " + " ; ".join(exc.details['raisons'])
            stats[seq]['erreurs'].append((nom, f"validation: {exc}{details}"))
            print(f"  [ERR ] {NIVEAU}/{seq} — {nom!r} : "
                  f"validation échouée : {exc}{details}")
            # On laisse la carte en BDD à l'état 'en_cours' pour que Laurent
            # puisse l'éditer dans l'UI plutôt que de la perdre.
            continue
        except Exception as exc:
            # v0.13.6.13 — valider_carte délègue à etats_edition.changer_etat_atome
            # qui peut lever ValidationPedagogiqueErreur (depuis le module
            # etats_edition, pas CarteErreur). Avant v0.13.6.13, toutes les
            # cartes peuplées avaient un lien notion/méthode valide ce qui
            # suffisait à la validation. Depuis v0.13.6.13, la validation
            # exige aussi une liaison objectif_cartes non vide ; or le script
            # de peuplement ne crée pas d'objectifs. On laisse alors la
            # carte en 'en_cours' (cohérent avec le comportement CarteErreur
            # ci-dessus).
            details = ""
            if hasattr(exc, 'details') and getattr(exc, 'details', {}).get('raisons'):
                details = " | " + " ; ".join(exc.details['raisons'])
            stats[seq]['erreurs'].append((nom, f"validation: {exc}{details}"))
            print(f"  [ERR ] {NIVEAU}/{seq} — {nom!r} : "
                  f"validation échouée : {exc}{details}")
            continue

        stats[seq]['crees'] += 1
        stats[seq]['ids'].append(carte_creee['id'])
        print(f"  [ OK ] {NIVEAU}/{seq}/C{carte_creee['num']:02d} — "
              f"{nom!r} ({carte_creee['id']})")

    conn.close()
    return stats


def imprimer_rapport(stats: dict, dry_run: bool) -> int:
    """Affiche le compte-rendu final. Renvoie 0 si tout va bien,
    sinon le nombre d'erreurs.
    """
    print()
    print("=" * 70)
    print("RAPPORT FINAL" + (" (DRY-RUN)" if dry_run else ""))
    print("=" * 70)

    total_crees = 0
    total_sautes = 0
    total_erreurs = 0

    for seq in sorted(COMPTE_PAR_SEQUENCE):
        attendu = COMPTE_PAR_SEQUENCE[seq]
        s = stats.get(seq, {'crees': 0, 'sautes': 0, 'erreurs': []})
        crees = s['crees']
        sautes = s['sautes']
        erreurs = len(s['erreurs'])
        total_crees += crees
        total_sautes += sautes
        total_erreurs += erreurs
        marqueur = "OK " if erreurs == 0 else "ERR"
        print(f"  [{marqueur}] {seq} : attendu={attendu} | créées={crees}"
              f" | sautées={sautes} | erreurs={erreurs}")
        for nom, err in s['erreurs']:
            print(f"         └─ {nom!r}  : {err}")

    print()
    print(f"  TOTAL : créées={total_crees} | sautées={total_sautes} "
          f"| erreurs={total_erreurs}")
    print()
    return total_erreurs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Peuple les cartes d'automatisme N10."
    )
    parser.add_argument('--dry-run', action='store_true',
                        help="Affiche sans insérer.")
    parser.add_argument('--force', action='store_true',
                        help="Recrée même si un nom de carte existe déjà.")
    parser.add_argument('--db', default=str(DEFAULT_DB_PATH),
                        help=f"Chemin BDD (def: {DEFAULT_DB_PATH}).")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[FATAL] BDD introuvable : {db_path}", file=sys.stderr)
        return 2

    print(f"BDD       : {db_path}")
    print(f"Dry-run   : {args.dry_run}")
    print(f"Force     : {args.force}")
    print(f"Total def : {len(TOUTES_CARTES_N10)} cartes à traiter")
    print()

    stats = peupler(db_path, dry_run=args.dry_run, force=args.force)
    nb_err = imprimer_rapport(stats, args.dry_run)
    return 1 if nb_err else 0


if __name__ == '__main__':
    raise SystemExit(main())
