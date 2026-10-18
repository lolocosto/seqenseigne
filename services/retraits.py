"""services/retraits.py — v0.51.11

Retrait de structures abandonnées, au démarrage (idempotent) :

  - **ancien modèle de MER** (`referentiel_externe`, `_sequence`, `_partie`,
    `_doc`), remplacé par les référentiels de MER de la structure figée
    (v0.49.0) ; les progressions de MER qui s'y appuyaient perdent leur
    référentiel (à choisir de nouveau) et leurs parties posées ;
  - **anciens livrets** (`livrets_de_sequence`, `livret_revisions`, `versions`,
    `versions_classes`) : instantanés et versions de livrets d'avant les
    ateliers, plus lus ni écrits ;
  - v0.51.13 — **résidus** d'anciennes migrations : `items_texte` (remplacée
    par `atome_sections` / `atome_section_items` en v0.6.4) et `objectifs_v2`
    (remplacée par `objectifs` en v0.14.7). Une table encore référencée par
    une clé étrangère d'une autre table n'est pas retirée (signalé).
  - v0.52.0 — **clés étrangères vers `objectifs_v2`** redirigées vers
    `objectifs` (bases d'avant v0.14.7) ; `objectifs_v2` n'est alors plus
    référencée et part avec les résidus.

Avant toute suppression, le contenu des tables est sauvegardé en JSON dans
`data/sauvegardes/retrait_<nom>_<date>.json` (lisible, réimportable à la
main au besoin). Rien n'est fait si les tables n'existent plus.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ANCIEN_MODELE_MER = ("referentiel_externe", "referentiel_externe_sequence",
                     "referentiel_externe_partie", "referentiel_externe_doc")
ANCIENS_LIVRETS = ("livret_revisions", "livrets_de_sequence", "versions_classes", "versions")
RESIDUS = ("items_texte", "objectifs_v2")


def _tables(conn) -> set:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _sauvegarder(conn, data_dir: Path, nom: str, tables: tuple, extra: dict | None = None) -> Path:
    existantes = _tables(conn)
    contenu = {"retrait": nom, "le": datetime.now().astimezone().isoformat(timespec="seconds"),
               "tables": {t: [dict(r) for r in conn.execute(f"SELECT * FROM {t}").fetchall()]
                          for t in tables if t in existantes}}
    if extra:
        contenu.update(extra)
    d = Path(data_dir) / "sauvegardes"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"retrait_{nom}_{datetime.now():%Y-%m-%d_%H%M%S}.json"
    p.write_text(json.dumps(contenu, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return p


def retirer_ancien_modele_mer(conn, data_dir: Path) -> dict | None:
    existantes = _tables(conn)
    if not any(t in existantes for t in ANCIEN_MODELE_MER):
        return None
    extra = {}
    if "progression_mer" in existantes:
        extra["progressions_mer"] = [dict(r) for r in conn.execute(
            "SELECT * FROM progression_mer WHERE ref_mer_source='externe'").fetchall()]
    if "progression_mer_partie" in existantes:
        extra["parties_posees"] = [dict(r) for r in conn.execute(
            "SELECT * FROM progression_mer_partie WHERE partie_source='externe'").fetchall()]
    p = _sauvegarder(conn, data_dir, "ancien_modele_mer", ANCIEN_MODELE_MER, extra)
    if "progression_mer_partie" in existantes:
        conn.execute("DELETE FROM progression_mer_partie WHERE partie_source='externe'")
    if "progression_mer" in existantes:
        conn.execute("UPDATE progression_mer SET ref_mer_id=NULL, ref_mer_source='fige' "
                     "WHERE ref_mer_source='externe'")
    if "progression_doc" in existantes:
        # Associations de documents de l'ancien modèle (identifiants rxd_…).
        conn.execute("DELETE FROM progression_doc WHERE doc_source='externe' AND doc_ref IN "
                     "(SELECT id FROM referentiel_externe_doc)"
                     if "referentiel_externe_doc" in existantes else "SELECT 1")
    for t in ANCIEN_MODELE_MER:
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    return {"sauvegarde": str(p), "progressions_mer": len(extra.get("progressions_mer", [])),
            "parties_posees": len(extra.get("parties_posees", []))}


def retirer_anciens_livrets(conn, data_dir: Path) -> dict | None:
    existantes = _tables(conn)
    if not any(t in existantes for t in ANCIENS_LIVRETS):
        return None
    p = _sauvegarder(conn, data_dir, "anciens_livrets", ANCIENS_LIVRETS)
    for t in ANCIENS_LIVRETS:
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    return {"sauvegarde": str(p)}


def _references(conn, cible: str) -> list[str]:
    """Tables (autres que `cible`) dont une clé étrangère vise `cible`."""
    out = []
    for t in sorted(_tables(conn) - {cible}):
        if t.startswith("sqlite_"):
            continue
        if any(r[2] == cible for r in conn.execute(f"PRAGMA foreign_key_list({t})")):
            out.append(t)
    return out


def retirer_residus(conn, data_dir: Path) -> dict | None:
    existantes = _tables(conn)
    presentes = [t for t in RESIDUS if t in existantes]
    if not presentes:
        return None
    gardees = {t: _references(conn, t) for t in presentes}
    gardees = {t: refs for t, refs in gardees.items() if refs}
    a_retirer = tuple(t for t in presentes if t not in gardees)
    res = {"retirees": list(a_retirer), "gardees": gardees, "sauvegarde": ""}
    if a_retirer:
        res["sauvegarde"] = str(_sauvegarder(conn, data_dir, "residus", a_retirer))
        conn.commit()
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            for t in a_retirer:
                conn.execute(f"DROP TABLE IF EXISTS {t}")
            conn.commit()
        finally:
            conn.execute("PRAGMA foreign_keys = ON")
    for t, refs in gardees.items():
        print(f"  [retraits] {t} gardée : référencée par {', '.join(refs)}")
    return res


# Tables de l'appli dont la clé vers les objectifs a pu rester sur
# objectifs_v2. Une table inconnue qui la référence n'est pas touchée (et
# objectifs_v2 est alors gardée, comme avant).
LIENS_OBJECTIFS = ("evaluation_objectifs", "fiches_resume", "objectif_cartes", "objectif_exos",
                   "objectif_fiches", "objectif_notions", "ui_etat_atelier_sequence")

_RE_REF_V2 = re.compile(r'REFERENCES\s+(?:"objectifs_v2"|\[objectifs_v2\]|`objectifs_v2`|objectifs_v2)\s*\(',
                        re.IGNORECASE)


def rediriger_objectifs_v2(conn, data_dir: Path | None) -> dict | None:
    """v0.52.0 — Répare les bases antérieures à v0.14.7 dont des tables
    (objectif_exos, objectif_notions, objectif_fiches, objectif_cartes,
    fiches_resume, evaluation_objectifs, ui_etat_atelier_sequence) ont gardé
    une clé étrangère vers `objectifs_v2` au lieu de `objectifs` : le
    renommage de v0.14.7 n'a pas réécrit ces références. Tant que la
    réconciliation objectifs ← objectifs_v2 existait (retirée en v0.51.13),
    cela passait inaperçu ; depuis, tout lien vers un objectif créé après
    coup échoue (FOREIGN KEY constraint failed).

    Seule la contrainte change (pas le format des lignes) : on réécrit le
    `CREATE TABLE` dans sqlite_master (procédure documentée par SQLite pour
    les changements de contraintes), en incrémentant schema_version.
    Les lignes qui ne visent aucun objectif de `objectifs` sont d'abord
    sauvegardées en JSON (si `data_dir`) puis retirées (ou mises à NULL pour
    ui_etat_atelier_sequence), sans quoi la contrainte serait violée.
    Idempotent : rien n'est fait s'il ne reste aucune référence à objectifs_v2."""
    existantes = _tables(conn)
    if "objectifs" not in existantes:
        return None
    cibles = []
    for t in LIENS_OBJECTIFS:
        if t not in existantes:
            continue
        cols = [r[3] for r in conn.execute(f'PRAGMA foreign_key_list("{t}")')
                if r[2] == "objectifs_v2"]
        if cols:
            cibles.append((t, cols))
    if not cibles:
        return None
    orphelins = {}
    for t, cols in cibles:
        for c in cols:
            rows = [dict(zip([d[0] for d in cur.description], r)) for cur in
                    [conn.execute(f'SELECT * FROM "{t}" WHERE "{c}" IS NOT NULL AND "{c}" NOT IN '
                                  '(SELECT id FROM objectifs)')] for r in cur.fetchall()]
            if rows:
                orphelins[f"{t}.{c}"] = rows
    sauvegarde = ""
    if orphelins and data_dir is not None:
        sauvegarde = str(_sauvegarder(conn, data_dir, "liens_objectifs_v2", (),
                                      {"orphelins": orphelins}))
    conn.commit()
    for t, cols in cibles:
        for c in cols:
            if f"{t}.{c}" not in orphelins:
                continue
            notnull = any(r[1] == c and r[3] for r in conn.execute(f'PRAGMA table_info("{t}")'))
            if notnull:
                conn.execute(f'DELETE FROM "{t}" WHERE "{c}" NOT IN (SELECT id FROM objectifs)')
            else:
                conn.execute(f'UPDATE "{t}" SET "{c}" = NULL WHERE "{c}" IS NOT NULL AND "{c}" '
                             'NOT IN (SELECT id FROM objectifs)')
    conn.commit()
    version = conn.execute("PRAGMA schema_version").fetchone()[0]
    conn.execute("PRAGMA writable_schema = ON")
    try:
        for t, _ in cibles:
            sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                               (t,)).fetchone()[0]
            conn.execute("UPDATE sqlite_master SET sql=? WHERE type='table' AND name=?",
                         (_RE_REF_V2.sub("REFERENCES objectifs(", sql), t))
        conn.execute(f"PRAGMA schema_version = {version + 1}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA writable_schema = OFF")
    restantes = [t for t, _ in cibles
                 if any(r[2] == "objectifs_v2" for r in conn.execute(f'PRAGMA foreign_key_list("{t}")'))]
    ok = conn.execute("PRAGMA quick_check").fetchone()[0]
    if restantes or ok != "ok":
        raise RuntimeError(f"redirection objectifs_v2 incomplète : {restantes} / {ok}")
    return {"tables": [t for t, _ in cibles],
            "orphelins": {k: len(v) for k, v in orphelins.items()},
            "sauvegarde": sauvegarde}


def appliquer(conn, data_dir: Path) -> dict:
    return {"ancien_modele_mer": retirer_ancien_modele_mer(conn, data_dir),
            "anciens_livrets": retirer_anciens_livrets(conn, data_dir),
            "liens_objectifs_v2": rediriger_objectifs_v2(conn, data_dir),
            "residus": retirer_residus(conn, data_dir)}
