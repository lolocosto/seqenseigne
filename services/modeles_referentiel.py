"""services/modeles_referentiel.py — v0.51.6

Structures modèles pour créer un référentiel externe (principal ou MER) :

  - **programme du cycle** (principal seulement) : thèmes et séquences du
    cycle du niveau, objectifs du niveau — parties de l'atelier de conception
    quand elles existent (tables `sequences_par_niveau` / `sequence_parties` /
    `objectifs`), sinon une partie par séquence avec tous ses objectifs
    (`<cycle>_objectifs.csv`), 0 séance ;
  - **référentiels existants** du niveau et du même type (principal ↔
    principal, MER ↔ MER ; internes et externes, toutes années), sauf
    annulés et vides.

Un modèle recopie la structure (thèmes, séquences, parties, objectifs :
nom, type, critères F/A/E, séances), jamais les documents ; les codes sont
recalculés. Textes convertis sans LaTeX (`texte_latex.vers_texte`).

Doublons : `doublons(conn, rid)` liste les référentiels externes du même
niveau et du même type dont le contenu est identique (structure + documents
: empreinte de chaque fichier, point d'attache, type, placement). Un nouveau
référentiel ne se justifie que si quelque chose change : pour reconduire,
la progression de l'année suivante se base sur le même référentiel.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path

from services import referentiel_principal_externe as rpe
from services.texte_latex import vers_texte


class ModeleErreur(rpe.RefExtErreur):
    pass


def _table(conn, nom: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (nom,)).fetchone() is not None


def _cols(conn, table: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _t(s) -> str:
    return vers_texte(s or "").strip()


def _resume(m: dict) -> str:
    nseq = len(m["sequences"])
    npar = sum(len(s["parties"]) for s in m["sequences"])
    nobj = sum(len(p["objectifs"]) for s in m["sequences"] for p in s["parties"])
    return (f"{len(m['themes'])} thème(s), {nseq} séquence(s), {npar} partie(s), "
            f"{nobj} objectif(s)")


# ── Modèle tiré d'un référentiel ─────────────────────────────────────────────

def _depuis_referentiel(conn, rid: str) -> dict:
    ref = dict(conn.execute("SELECT * FROM referentiel_niveaux WHERE id=?", (rid,)).fetchone())
    interne = (ref.get("source") or "interne") == "interne"
    ordre_t = "ordre, code" if "ordre" in _cols(conn, "referentiel_themes") else "code"
    themes = [{"code": t["code"], "nom": _t(t["nom"]), "couleur": t["couleur"] or ""}
              for t in conn.execute(f"SELECT * FROM referentiel_themes WHERE referentiel_id=? "
                                    f"ORDER BY {ordre_t}", (rid,)).fetchall()]
    cols_p = _cols(conn, "referentiel_parties")
    cols_o = _cols(conn, "referentiel_objectifs")
    seqs = []
    for s in conn.execute("SELECT * FROM referentiel_sequences WHERE referentiel_id=? "
                          "ORDER BY numero, code", (rid,)).fetchall():
        parties = []
        for p in conn.execute("SELECT * FROM referentiel_parties WHERE referentiel_id=? AND "
                              "seq_code=? ORDER BY numero", (rid, s["code"])).fetchall():
            objs = []
            for k, o in enumerate(conn.execute(
                    "SELECT * FROM referentiel_objectifs WHERE referentiel_id=? AND seq_code=? "
                    "AND partie_numero=? ORDER BY code", (rid, s["code"], p["numero"])).fetchall()):
                if interne:
                    type_obj = "connaissance" if k == 0 else "capacite"
                else:
                    type_obj = (o["type_obj"] if "type_obj" in cols_o else "") or "capacite"
                objs.append({"nom": _t(o["nom"]), "type": type_obj,
                             "nb_seances": float(o["nb_seances"] or 0),
                             "criteres": {x: _t(o["critere_" + x]) for x in ("f", "a", "e")}})
            parties.append({"libelle": _t(p["libelle"]) if "libelle" in cols_p else "",
                            "objectifs": objs})
        seqs.append({"nom": _t(s["nom"]), "theme": s["theme_code"], "parties": parties})
    return {"themes": themes, "sequences": seqs}


# ── Modèle « programme du cycle » ────────────────────────────────────────────

def _objectifs_csv(data_dir: Path | None, cycle: str, niveau: str) -> dict:
    """{seq_code: [objectif…]} depuis <cycle>_objectifs.csv."""
    out: dict[str, list] = {}
    if not data_dir:
        return out
    p = Path(data_dir) / f"{cycle}_objectifs.csv"
    if not p.is_file():
        return out
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("CodeNiveau") != niveau:
                continue
            out.setdefault(row["CodeSequence"], []).append({
                "code": row["CodeObjectif"], "nom": _t(row["Nom"]),
                # Critères : F ← maîtrise fragile, A ← satisfaisante, E ← très bonne.
                "criteres": {"f": _t(_tiret(row.get("MaitriseF"))),
                             "a": _t(_tiret(row.get("MaitriseS"))),
                             "e": _t(_tiret(row.get("MaitriseTB")))}})
    for objs in out.values():
        objs.sort(key=lambda o: o["code"])
    return out


def _tiret(v):
    v = (v or "").strip()
    return "" if v == "-" else v


def _cycle_csv(data_dir: Path | None, cycle: str) -> tuple[list, list]:
    themes, seqs = [], []
    if not data_dir:
        return themes, seqs
    pt, ps = Path(data_dir) / f"{cycle}_themes.csv", Path(data_dir) / f"{cycle}_sequences.csv"
    if pt.is_file():
        with open(pt, encoding="utf-8-sig", newline="") as f:
            themes = [{"code": r["Code"], "nom": _t(r["Nom"]), "couleur": r.get("CodeCouleur") or ""}
                      for r in csv.DictReader(f)]
    if ps.is_file():
        with open(ps, encoding="utf-8-sig", newline="") as f:
            seqs = [{"code": r["Code"], "numero": int(r["Numero"]), "nom": r["Nom"],
                     "theme_id": r.get("Theme") or None} for r in csv.DictReader(f)]
        seqs.sort(key=lambda r: r["numero"])
    return themes, seqs


def _parties_atelier(conn, niveau: str, seq_code: str) -> list | None:
    """Parties et objectifs de l'atelier de conception, s'il y en a."""
    if not all(_table(conn, t) for t in ("sequences_par_niveau", "sequence_parties", "objectifs")):
        return None
    sn = conn.execute("SELECT id FROM sequences_par_niveau WHERE niveau=? AND sequence_code=?",
                      (niveau, seq_code)).fetchone()
    if sn is None:
        return None
    parties = []
    for p in conn.execute("SELECT * FROM sequence_parties WHERE sequence_par_niveau_id=? "
                          "ORDER BY numero", (sn["id"],)).fetchall():
        objs = [dict(o) for o in conn.execute(
            "SELECT * FROM objectifs WHERE partie_id=? ORDER BY code", (p["id"],)).fetchall()]
        parties.append({"libelle": "", "objectifs": [
            {"code": o["code"], "nom": o["nom"], "nb_seances": float(o["nb_seances"] or 0),
             "criteres": {"f": o["critere_F"], "a": o["critere_A"], "e": o["critere_E"]}}
            for o in objs]})
    return parties if any(p["objectifs"] for p in parties) else None


def _cycle(conn, data_dir: Path | None, niveau: str) -> dict | None:
    if not (_table(conn, "param_niveaux") and _table(conn, "sequences_du_cycle")):
        return None
    n = conn.execute("SELECT cycle_code FROM param_niveaux WHERE code=?", (niveau,)).fetchone()
    if n is None:
        return None
    cycle = n["cycle_code"]
    themes_id = {}
    themes = []
    if _table(conn, "themes"):
        for t in conn.execute("SELECT * FROM themes WHERE cycle_code=? AND code NOT LIKE 'X%' "
                              "ORDER BY ordre, code", (cycle,)).fetchall():
            themes_id[t["id"]] = t["code"]
            themes.append({"code": t["code"], "nom": _t(t["nom"]),
                           "couleur": t["code_couleur"] or ""})
    csv_objs = _objectifs_csv(data_dir, cycle, niveau)
    # v0.52.0 — Les séquences d'archive (codes X01…, ancien découpage du
    # cycle 3 remplacé par l'import des séquences de 6e) ne sont pas proposées.
    sequences_cycle = [dict(r) for r in conn.execute(
        "SELECT * FROM sequences_du_cycle WHERE cycle_code=? AND code NOT LIKE 'X%' "
        "ORDER BY numero", (cycle,)).fetchall()]
    noms_csv = {s["code"]: s["nom"] for s in _cycle_csv(data_dir, cycle)[1]}
    if not sequences_cycle:
        # Repli : découpage du cycle d'après <cycle>_themes.csv / _sequences.csv.
        themes, sequences_cycle = _cycle_csv(data_dir, cycle)
        themes_id = {t["code"]: t["code"] for t in themes}
    seqs = []
    for s in sequences_cycle:
        parties = _parties_atelier(conn, niveau, s["code"])
        # v0.52.0 — Les objectifs du CSV ne valent que pour la séquence du CSV
        # (même code ET même nom) : après le remplacement du découpage du
        # cycle 3, S04 « Pré-algèbre » ne reçoit pas les objectifs de l'ancienne
        # S04 « Calcul mental et en ligne ».
        csv_valide = noms_csv.get(s["code"], "").strip() == (s["nom"] or "").strip()
        par_code = ({o["code"]: o for o in csv_objs.get(s["code"], [])}
                    if csv_valide else {})
        if parties:
            for p in parties:
                for o in p["objectifs"]:
                    c = par_code.get(o["code"], {})
                    nom = o["nom"] or ""
                    if not nom.strip() or nom.lstrip().startswith("\\seq"):
                        nom = c.get("nom", "")       # macro non résolue : nom du CSV
                    o["nom"] = _t(nom)
                    o["criteres"] = {x: _t(o["criteres"][x]) or c.get("criteres", {}).get(x, "")
                                     for x in ("f", "a", "e")}
        elif par_code:
            parties = [{"libelle": "", "objectifs": [
                {"code": o["code"], "nom": o["nom"], "nb_seances": 0.0,
                 "criteres": o["criteres"]} for o in csv_objs[s["code"]]]}]
        else:
            continue                                  # séquence absente de ce niveau
        for p in parties:
            for k, o in enumerate(p["objectifs"]):
                o["type"] = "connaissance" if k == 0 else "capacite"
                o.pop("code", None)
            p["objectifs"] = [o for o in p["objectifs"] if o["nom"]]
        seqs.append({"nom": _t(s["nom"]), "theme": themes_id.get(s["theme_id"]),
                     "parties": parties})
    if not seqs:
        return None
    nom_cycle = cycle
    if _table(conn, "cycles"):
        r = conn.execute("SELECT nom FROM cycles WHERE code=?", (cycle,)).fetchone()
        nom_cycle = (r["nom"] if r and r["nom"] else cycle)
    return {"themes": themes, "sequences": seqs, "nom": f"Programme du cycle ({nom_cycle})"}


# ── Liste des modèles ────────────────────────────────────────────────────────

def lister(conn, data_dir: Path | None, niveau: str, type_ref: str = "principal") -> list[dict]:
    if type_ref not in ("principal", "mer"):
        raise ModeleErreur(f"Type invalide : {type_ref!r}.")
    out = []
    if type_ref == "principal":
        c = _cycle(conn, data_dir, niveau)
        if c:
            nom = c.pop("nom")
            out.append({"cle": "cycle", "origine": "cycle", "nom": nom, "description": "",
                        "modele": c, "resume": _resume(c)})
    cols = _cols(conn, "referentiel_niveaux")
    q = "SELECT * FROM referentiel_niveaux WHERE niveau=? AND etat<>'annule'"
    if "type_ref" in cols:
        q += " AND COALESCE(type_ref, 'principal')=?"
        params = (niveau, type_ref)
    else:
        params = (niveau,)
        if type_ref == "mer":
            return out
    for r in conn.execute(q + " ORDER BY id", params).fetchall():
        r = dict(r)
        m = _depuis_referentiel(conn, r["id"])
        if not m["sequences"]:
            continue
        out.append({"cle": "ref:" + r["id"], "origine": r.get("source") or "interne",
                    "nom": rpe.nom_calcule(r), "description": r.get("description") or "",
                    "id": r["id"], "modele": m, "resume": _resume(m)})
    return out


def modele(conn, data_dir: Path | None, niveau: str, type_ref: str, cle: str) -> dict:
    for m in lister(conn, data_dir, niveau, type_ref):
        if m["cle"] == cle:
            return m
    raise ModeleErreur("Modèle introuvable pour ce niveau et ce type.", "introuvable")


# ── Création depuis un modèle ────────────────────────────────────────────────

def appliquer(conn, rid: str, m: dict, aujourd_hui: date | None = None) -> None:
    """Recopie la structure d'un modèle dans un référentiel externe vide."""
    aujourd_hui = aujourd_hui or date.today()
    if conn.execute("SELECT 1 FROM referentiel_sequences WHERE referentiel_id=? LIMIT 1",
                    (rid,)).fetchone():
        raise ModeleErreur("Le référentiel a déjà des séquences.")
    couleurs = dict(rpe.COULEURS_THEMES)
    codes = {}
    for t in m.get("themes", []):
        nom = t.get("nom") or t.get("code") or "Thème"
        if any(x["nom"].lower() == nom.lower() for x in rpe.lister_themes(conn, rid)):
            continue
        codes[t.get("code")] = rpe.ajouter_theme(
            conn, rid, nom, t.get("couleur") if t.get("couleur") in couleurs else "")["code"]
    for s in m.get("sequences", []):
        code = rpe.ajouter_sequence(conn, rid, s.get("nom") or "Séquence",
                                    codes.get(s.get("theme")))["code"]
        for p in s.get("parties", []):
            num = rpe.ajouter_partie(conn, rid, code, 0, aujourd_hui,
                                     libelle=p.get("libelle") or "")["numero"]
            for o in p.get("objectifs", []):
                rpe.ajouter_objectif(conn, rid, code, num, o["nom"], o.get("nb_seances") or 0,
                                     aujourd_hui, type_obj=o.get("type") or "capacite",
                                     criteres=o.get("criteres") or {})


def creer(conn, data_dir: Path | None, niveau: str, annee: str, description: str = "",
          type_ref: str = "principal", cle: str | None = None,
          aujourd_hui: date | None = None) -> dict:
    """Crée un référentiel externe, vide ou prérempli depuis le modèle `cle`."""
    m = modele(conn, data_dir, niveau, type_ref, cle) if cle else None
    r = rpe.creer(conn, niveau, annee, description, type_ref=type_ref)
    if m:
        appliquer(conn, r["id"], m["modele"], aujourd_hui)
        conn.execute("UPDATE referentiel_niveaux SET cree_depuis=? WHERE id=?",
                     (m["nom"], r["id"]))
    return rpe.lire(conn, r["id"], aujourd_hui)


# ── Doublons ─────────────────────────────────────────────────────────────────

def _sha_fichier(conn, data_dir: Path | None, f: dict) -> str:
    if f.get("sha256"):
        return f["sha256"]
    if not data_dir:
        return f"{f['nom_fichier']}|{f['taille']}"
    try:
        h = hashlib.sha256((Path(data_dir) / f["chemin"]).read_bytes()).hexdigest()
    except OSError:
        return f"{f['nom_fichier']}|{f['taille']}"
    conn.execute("UPDATE referentiel_fichiers SET sha256=? WHERE id=?", (h, f["id"]))
    return h


def empreinte_contenu(conn, data_dir: Path | None, rid: str) -> str | None:
    """Empreinte du contenu d'un référentiel externe (structure + documents),
    sans ses métadonnées (année, description…). None s'il n'a pas de séquence."""
    m = _depuis_referentiel(conn, rid)
    if not m["sequences"]:
        return None
    rang_seq = {s["code"]: k for k, s in enumerate(conn.execute(
        "SELECT code FROM referentiel_sequences WHERE referentiel_id=? ORDER BY numero",
        (rid,)).fetchall())}
    types = {t["id"]: t["libelle"] for t in conn.execute("SELECT id, libelle FROM types_documents")}
    docs = sorted(
        (rang_seq.get(f["seq_code"], -1), int(f["partie_numero"] or 0),
         _sha_fichier(conn, data_dir, dict(f)), types.get(f["type_id"], ""),
         int(f["seance_n"] or 0), f["retour"] or "", f["delai_type"] or "", int(f["delai_n"] or 1))
        for f in conn.execute("SELECT * FROM referentiel_fichiers WHERE referentiel_id=?",
                              (rid,)).fetchall())
    contenu = {"structure": m, "documents": docs}
    return hashlib.sha256(json.dumps(contenu, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


def doublons(conn, data_dir: Path | None, rid: str) -> list[dict]:
    """Référentiels externes du même niveau et du même type au contenu identique."""
    ref = rpe._lire_ref(conn, rid)
    e = empreinte_contenu(conn, data_dir, rid)
    if e is None:
        return []
    out = []
    for r in conn.execute("SELECT * FROM referentiel_niveaux WHERE source='externe' AND "
                          "niveau=? AND type_ref=? AND etat<>'annule' AND id<>? ORDER BY id",
                          (ref["niveau"], ref.get("type_ref") or "principal", rid)).fetchall():
        if empreinte_contenu(conn, data_dir, r["id"]) == e:
            out.append({"id": r["id"], "nom": rpe.nom_calcule(dict(r))})
    return out
