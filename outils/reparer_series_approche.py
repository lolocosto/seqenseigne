#!/usr/bin/env python3
"""outils/reparer_series_approche.py — v0.52.3

Remet en état les activités d'approche abîmées par un enregistrement dans
l'atelier d'exercices avant la v0.52.3.

Cause (corrigée en v0.52.3)
---------------------------
`services/atomes._SERIE_VERS_CODE` faisait correspondre la série
« approche » au code 'EA', alors que la base, l'import 6e, les livrets et la
liste de l'atelier utilisent 'AE' depuis la v0.18.3. Enregistrer une activité
d'approche réécrivait donc son code en 'EA' et lui donnait le prochain numéro
libre de cette « série » (AE03 → EA01). L'activité quittait la section
« Approche » de la liste (le code EA01 était lu comme une Exploration) et
l'import 6e, qui retrouve un exercice par (niveau, séquence, code, numéro), ne
la retrouvait plus (il en aurait créé un doublon).

Ce que fait l'outil
-------------------
Décision A2 : un outil (essai à blanc, puis --apply avec sauvegarde) plutôt
qu'une migration au démarrage, parce que le numéro d'origine se déduit des
liens et peut être déjà pris (doublon créé par un import fait entre-temps) :
Laurent doit voir chaque correspondance avant qu'elle soit écrite.

Un exercice est à réparer quand :
  - son code est 'EA' ;
  - sa série est « approche » et son code n'est pas 'AE' ;
  - son code est 'AE' et sa série n'est pas « approche » ;
  - il est relié comme activité (partie_exos_revision_approche type 'EA', ou
    objectif_exos série 'AE'/'EA') et n'a ni série ni code.
Il reçoit la série « approche », le code 'AE' et son numéro d'origine, lu
dans ses liens (origin_num de partie_exos_revision_approche, puis de
objectif_exos), s'il est libre ; sinon le prochain numéro AE libre de sa
séquence (signalé). Les liens objectif_exos de série 'EA' passent en 'AE'.
Le contenu (énoncé, corrigé…) n'est jamais touché.

Un exercice relié comme activité mais rangé dans une autre série cohérente
(F, A, E…) est seulement signalé : la série a pu être changée exprès.

Idempotent : une seconde exécution ne trouve plus rien.

Usage (Windows, depuis appli\\)
-------------------------------
    ..\\outils\\python\\python.exe .\\outils\\reparer_series_approche.py
    ..\\outils\\python\\python.exe .\\outils\\reparer_series_approche.py --apply

Options : --db CHEMIN (défaut : base du profil atelier), --yes (sans
confirmation). Codes de sortie : 0 succès ; 1 annulé ; 2 base introuvable
ou base de classe ; 3 erreur.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

RACINE_APPLI = Path(__file__).resolve().parent.parent
if str(RACINE_APPLI) not in sys.path:          # lancement par chemin (Windows)
    sys.path.insert(0, str(RACINE_APPLI))

SERIE = "approche"
CODE = "AE"


def resoudre_base(db: str | None) -> Path:
    """Base explicite, sinon celle du profil atelier (comme lancer.bat atelier)."""
    if db:
        return Path(db).resolve()
    from services.bascule import NOM_DB, dossier_par_defaut
    return dossier_par_defaut(RACINE_APPLI, "atelier") / NOM_DB


def _cols(conn, table: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _liens(conn, ex_id: str) -> list[tuple[str, object]]:
    """(description, origin_num) des liens « activité » de l'exercice, dans
    l'ordre de confiance : partie (rôle EA), puis objectif (série AE/EA)."""
    sortie = []
    for r in conn.execute(
            "SELECT partie_id, origin_serie, origin_num FROM partie_exos_revision_approche "
            "WHERE exercice_id = ? AND type = 'EA' ORDER BY partie_id", (ex_id,)):
        if (r[1] or CODE) in (CODE, "EA"):
            sortie.append((f"partie {r[0]}", r[2]))
    for r in conn.execute(
            "SELECT objectif_id, serie, origin_num FROM objectif_exos "
            "WHERE exercice_id = ? AND serie IN ('AE', 'EA') ORDER BY objectif_id", (ex_id,)):
        sortie.append((f"objectif {r[0]} ({r[1]})", r[2]))
    return sortie


def _numero(v) -> int | None:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def diagnostiquer(conn) -> dict:
    """Plan de réparation, sans rien écrire.

    Retour : {"reparations": [{id, niveau, sequence, avant, apres, num,
    origine, conflit, etat}], "signales": [str]}."""
    conn.row_factory = sqlite3.Row
    lies = {r[0] for r in conn.execute(
        "SELECT exercice_id FROM partie_exos_revision_approche WHERE type = 'EA' "
        "UNION SELECT exercice_id FROM objectif_exos WHERE serie IN ('AE', 'EA')")}
    candidats, signales = [], []
    for r in conn.execute("SELECT id, niveau, sequence, serie, serie_code, num, etat_code "
                          "FROM exercices ORDER BY niveau, sequence, id"):
        serie, code = r["serie"] or "", r["serie_code"] or ""
        abime = (code == "EA"
                 or (serie == SERIE and code != CODE)
                 or (code == CODE and serie != SERIE)
                 or (r["id"] in lies and not serie and not code))
        if abime:
            candidats.append(dict(r))
        elif r["id"] in lies and code != CODE:
            signales.append(f"{r['niveau']}/{r['sequence']} {code}{r['num'] or ''} ({r['id']}, "
                            f"série « {serie} ») : relié comme activité d'approche mais rangé "
                            "dans une autre série — non modifié, à vérifier dans l'atelier")
    # Numéros AE déjà pris par des exercices sains, par (niveau, séquence).
    pris: dict[tuple, dict[int, str]] = {}
    ids_candidats = {c["id"] for c in candidats}
    for r in conn.execute("SELECT id, niveau, sequence, num FROM exercices "
                          "WHERE serie_code = ?", (CODE,)):
        if r["id"] in ids_candidats:
            continue
        n = _numero(r["num"])
        if n is not None:
            pris.setdefault((r["niveau"] or "", r["sequence"] or ""), {})[n] = r["id"]
    for c in candidats:
        c["_liens"] = _liens(conn, c["id"])
        if c["serie_code"] == CODE and _numero(c["num"]) is not None:
            c["_voulus"] = [(_numero(c["num"]), "numéro actuel")]
        else:
            c["_voulus"] = [(_numero(n), d) for d, n in c["_liens"] if _numero(n) is not None]
    candidats.sort(key=lambda c: (0 if c["_voulus"] else 1, c["niveau"] or "",
                                  c["sequence"] or "", c["_voulus"][0][0] if c["_voulus"] else 0,
                                  c["id"]))
    # Deux passes : d'abord chaque numéro d'origine encore libre (il est
    # réservé), ensuite les numéros pris ou inconnus reçoivent le prochain
    # numéro libre, pour qu'aucun ne prenne le numéro d'origine d'un autre.
    choix: dict[str, tuple] = {}
    for c in candidats:
        occupes = pris.setdefault((c["niveau"] or "", c["sequence"] or ""), {})
        for n, d in c["_voulus"]:
            if n not in occupes:
                occupes[n] = c["id"]
                choix[c["id"]] = (n, d, "")
                break
    for c in candidats:
        if c["id"] in choix:
            continue
        occupes = pris[(c["niveau"] or "", c["sequence"] or "")]
        conflit = ""
        if c["_voulus"]:
            n0 = c["_voulus"][0][0]
            conflit = (f"{CODE}{n0:02d} déjà porté par {occupes.get(n0, '?')} (doublon "
                       "probable créé par un import fait après l'enregistrement)")
        num = max(occupes, default=0) + 1
        occupes[num] = c["id"]
        choix[c["id"]] = (num, "prochain numéro libre" + ("" if c["_voulus"] else
                                                           ", numéro d'origine inconnu"), conflit)
    reparations = []
    for c in candidats:
        num, origine, conflit = choix[c["id"]]
        reparations.append({
            "id": c["id"], "niveau": c["niveau"], "sequence": c["sequence"],
            "avant": f"{c['serie'] or '∅'} / {c['serie_code'] or '∅'}{_numero(c['num']) or ''}",
            "apres": f"{SERIE} / {CODE}{num:02d}", "num": num, "origine": origine,
            "conflit": conflit, "etat": c["etat_code"] or "",
        })
    return {"reparations": reparations, "signales": signales}


def appliquer(conn, plan: dict) -> int:
    """Écrit le plan (transaction ouverte par l'appelant). Retourne le nombre
    d'exercices réparés."""
    avec_mtime = "mtime" in _cols(conn, "exercices")
    maintenant = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in plan["reparations"]:
        if avec_mtime:
            conn.execute("UPDATE exercices SET serie=?, serie_code=?, num=?, mtime=? WHERE id=?",
                         (SERIE, CODE, r["num"], maintenant, r["id"]))
        else:
            conn.execute("UPDATE exercices SET serie=?, serie_code=?, num=? WHERE id=?",
                         (SERIE, CODE, r["num"], r["id"]))
        conn.execute("UPDATE OR IGNORE objectif_exos SET serie=? WHERE exercice_id=? AND serie='EA'",
                     (CODE, r["id"]))
        conn.execute("DELETE FROM objectif_exos WHERE exercice_id=? AND serie='EA'", (r["id"],))
    return len(plan["reparations"])


def texte(plan: dict) -> str:
    L = []
    reps = plan["reparations"]
    if not reps:
        L.append("Aucune activité d'approche à réparer.")
    else:
        L.append(f"{len(reps)} exercice(s) à remettre en série « {SERIE} » ({CODE}) :")
        for r in reps:
            L.append(f"  - {r['niveau']}/{r['sequence']} {r['id']} : {r['avant']} → {r['apres']}"
                     f" ({r['origine']})" + (" [validé]" if r["etat"] == "valide" else ""))
            if r["conflit"]:
                L.append(f"      ! {r['conflit']} : à arbitrer dans l'atelier")
    for s in plan["signales"]:
        L.append(f"  ? {s}")
    return "\n".join(L)


def sauvegarder(db: Path) -> Path:
    d = db.parent / "sauvegardes"
    d.mkdir(parents=True, exist_ok=True)
    cible = d / f"avant_reparation_approche_{datetime.now():%Y-%m-%d_%H%M%S}.db"
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    dst = sqlite3.connect(cible)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return cible


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Répare les activités d'approche enregistrées "
                                             "avant v0.52.3 (code EA → AE, numéro d'origine).")
    ap.add_argument("--apply", action="store_true", help="applique (sinon essai à blanc)")
    ap.add_argument("--yes", action="store_true", help="sans confirmation")
    ap.add_argument("--db", help="chemin de la base (défaut : base du profil atelier)")
    args = ap.parse_args(argv)
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except Exception:
            pass
    db = resoudre_base(args.db)
    if not db.is_file():
        print(f"Base introuvable : {db}")
        return 2
    from services import repartition
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        if repartition.role(conn) == "classe":
            print(f"{db} est la base de l'appli de classe : la réparation se fait dans l'atelier.")
            return 2
        plan = diagnostiquer(conn)
    finally:
        conn.close()
    print(f"Base : {db}\n")
    print(texte(plan))
    if not plan["reparations"]:
        return 0
    if not args.apply:
        print("\n(essai à blanc : rien n'a été écrit — relancer avec --apply pour appliquer)")
        return 0
    if not args.yes:
        rep = input("\nAppliquer ? [o/N] ").strip().lower()
        if rep not in ("o", "oui", "y", "yes"):
            print("Annulé.")
            return 1
    sauvegarde = sauvegarder(db)
    print(f"\nSauvegarde : {sauvegarde}")
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        plan = diagnostiquer(conn)            # recalculé sous le verrou d'écriture
        n = appliquer(conn, plan)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"\nErreur, rien n'a été écrit : {e}")
        return 3
    finally:
        conn.close()
    journal = sauvegarde.parent / f"journal_reparation_approche_{datetime.now():%Y-%m-%d_%H%M%S}.json"
    journal.write_text(json.dumps({"base": str(db), "sauvegarde": str(sauvegarde), **plan},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Journal : {journal}")
    print(f"\n{n} exercice(s) réparé(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
