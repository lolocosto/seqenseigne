"""services/import_publication.py — v0.51.3

Import d'un paquet de publication (profil classe) : les référentiels conçus
dans l'appli locale arrivent en lecture seule dans l'appli en ligne.

Étapes :
  1. vérification complète du paquet (paquet_publication.verifier : formats,
     empreintes de tous les fichiers et référentiels) — rien n'est importé si
     elle échoue ;
  2. analyse, référentiel par référentiel :
       - « nouveau », « mise à jour » (rapport des changements), « identique »
         (même empreinte : rien à faire) ;
       - « refusé » : référentiel d'origine locale (base partagée avec
         l'atelier) différent du paquet, conflit niveau/version, ou mise à
         jour qui supprimerait une séquence ou une partie déjà commencée ;
       - documents orphelins : associations de documents (progression) dont
         le document disparaît — signalées, jamais supprimées ;
  3. import des référentiels acceptés, chacun dans sa transaction : fichiers
     écrits là où l'appli les lit, structure figée remplacée (tables
     referentiel_*), documents compilés et titres des notions / méthodes dans
     des tables dédiées, journal.

Un référentiel importé porte origine='publication' (table
referentiel_niveaux) ; il ne se modifie que par un nouvel import.
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import date, datetime
from pathlib import Path

from services import format_referentiel as fmt
from services import paquet_publication as pqt


class ImportErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides", erreurs=None):
        super().__init__(message)
        self.code = code
        self.erreurs = erreurs or []


SCHEMA = """
CREATE TABLE IF NOT EXISTS referentiel_docs_publies (
    referentiel_id TEXT NOT NULL,
    ref            TEXT NOT NULL,        -- « type|cible » (PDF compilé)
    type_document  TEXT NOT NULL DEFAULT '',
    seq_code       TEXT NOT NULL DEFAULT '',   -- '' = document annuel
    partie_numero  INTEGER NOT NULL DEFAULT 0,
    libelle        TEXT NOT NULL DEFAULT '',
    nom_fichier    TEXT NOT NULL DEFAULT '',
    chemin         TEXT NOT NULL DEFAULT '',
    mime           TEXT NOT NULL DEFAULT '',
    taille         INTEGER NOT NULL DEFAULT 0,
    sha256         TEXT NOT NULL DEFAULT '',
    ordre          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (referentiel_id, ref)
);
CREATE TABLE IF NOT EXISTS referentiel_titres_publies (
    referentiel_id TEXT NOT NULL,
    seq_code       TEXT NOT NULL,
    partie_numero  INTEGER NOT NULL,
    nature         TEXT NOT NULL,        -- 'notion' | 'methode'
    atome_id       TEXT NOT NULL,
    titre          TEXT NOT NULL DEFAULT '',
    ordre          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (referentiel_id, seq_code, partie_numero, nature, atome_id)
);
CREATE TABLE IF NOT EXISTS imports_publication (
    id             TEXT PRIMARY KEY,
    importe_le     TEXT NOT NULL,
    nom_paquet     TEXT NOT NULL DEFAULT '',
    referentiel_id TEXT NOT NULL,
    nom            TEXT NOT NULL DEFAULT '',
    empreinte      TEXT NOT NULL DEFAULT '',
    statut         TEXT NOT NULL,        -- nouveau | mise_a_jour | identique | refuse
    rapport        TEXT NOT NULL DEFAULT '{}'
);
"""


def migrer(conn) -> None:
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_niveaux)")}
    for nom, decl in (("origine", "TEXT NOT NULL DEFAULT 'locale'"),
                      ("publication_empreinte", "TEXT NOT NULL DEFAULT ''"),
                      ("publication_importe_le", "TEXT NOT NULL DEFAULT ''")):
        if cols and nom not in cols:
            conn.execute(f"ALTER TABLE referentiel_niveaux ADD COLUMN {nom} {decl}")


# ── Lecture du paquet ────────────────────────────────────────────────────────

def _lire(contenu: bytes) -> tuple[dict, dict, zipfile.ZipFile]:
    manifeste, erreurs = pqt.verifier(contenu)
    if erreurs:
        raise ImportErreur("Le paquet est invalide : rien n'a été importé.",
                           "paquet_invalide", erreurs)
    z = zipfile.ZipFile(io.BytesIO(contenu))
    docs = {r["id"]: json.loads(z.read(r["chemin"]).decode("utf-8"))
            for r in manifeste["referentiels"]}
    return manifeste, docs, z


def _documents(doc: dict) -> list[tuple[str, int, dict]]:
    """[(seq_code, partie_numero, document)] ('' / 0 : annuel ou séquence)."""
    out = [("", 0, d) for d in doc["documents_annuels"]]
    for s in doc["sequences"]:
        out += [(s["code"], 0, d) for d in s["documents"]]
        for p in s["parties"]:
            out += [(s["code"], p["numero"], d) for d in p["documents"]]
    return out


# ── Analyse ──────────────────────────────────────────────────────────────────

def _refs_actuelles(conn, rid: str) -> set:
    refs = {r["id"] for r in conn.execute(
        "SELECT id FROM referentiel_fichiers WHERE referentiel_id=?", (rid,))}
    refs |= {r["ref"] for r in conn.execute(
        "SELECT ref FROM referentiel_docs_publies WHERE referentiel_id=?", (rid,))}
    return refs


def _structure_actuelle(conn, rid: str) -> dict:
    seqs = {}
    for s in conn.execute("SELECT code, nom FROM referentiel_sequences WHERE "
                          "referentiel_id=?", (rid,)):
        seqs[s["code"]] = {"nom": s["nom"], "parties": {}}
    for p in conn.execute("SELECT seq_code, numero, nb_seances_R_AE FROM referentiel_parties "
                          "WHERE referentiel_id=?", (rid,)):
        if p["seq_code"] in seqs:
            seqs[p["seq_code"]]["parties"][p["numero"]] = p["nb_seances_R_AE"]
    return seqs


def _analyser_un(conn, data_dir: Path, rid: str, doc: dict, aujourd_hui: date) -> dict:
    from services.referentiel_principal_externe import sequence_commencee
    nom = doc["referentiel"]["nom"]
    res = {"id": rid, "nom": nom, "empreinte": doc["empreinte"], "statut": "",
           "raisons": [], "changements": [], "orphelins": []}
    r = conn.execute("SELECT * FROM referentiel_niveaux WHERE id=?", (rid,)).fetchone()
    autre = conn.execute("SELECT id FROM referentiel_niveaux WHERE niveau=? AND version=? "
                         "AND id<>?", (doc["referentiel"]["niveau"],
                                       doc["referentiel"]["version"], rid)).fetchone()
    if autre is not None:
        res["statut"] = "refuse"
        res["raisons"].append(f"Un autre référentiel ({autre['id']}) a déjà le niveau "
                              f"{doc['referentiel']['niveau']} et la version "
                              f"{doc['referentiel']['version']}.")
        return res
    if r is None:
        res["statut"] = "nouveau"
        nb_s = len(doc["sequences"])
        res["changements"].append(f"{nb_s} séquence(s), "
                                  f"{sum(len(s['parties']) for s in doc['sequences'])} partie(s), "
                                  f"{len(_documents(doc))} document(s).")
        return res
    r = dict(r)
    if (r.get("origine") or "locale") != "publication":
        # Base partagée avec l'atelier : le référentiel local est la source.
        try:
            local = fmt.exporter(conn, rid, data_dir, figer=False)["empreinte"]
        except fmt.FormatErreur:
            local = ""
        if local == doc["empreinte"]:
            res["statut"] = "identique"
            res["raisons"].append("Référentiel déjà présent dans cette base (conçu ici), "
                                  "identique au paquet.")
        else:
            res["statut"] = "refuse"
            res["raisons"].append("Référentiel conçu dans cette base (base partagée avec "
                                  "l'atelier) : il n'est pas remplacé par le paquet.")
        return res
    if r.get("publication_empreinte") == doc["empreinte"]:
        res["statut"] = "identique"
        return res
    res["statut"] = "mise_a_jour"
    avant = _structure_actuelle(conn, rid)
    apres = {s["code"]: s for s in doc["sequences"]}
    noms = {d["code"]: d["nom"] for d in doc["structure"]["decoupage"]}
    for code in avant:
        commencee = sequence_commencee(conn, rid, code, aujourd_hui)
        if code not in apres:
            if commencee:
                res["raisons"].append(f"La séquence {code} a commencé : elle ne peut pas "
                                      "être retirée.")
            res["changements"].append(f"Séquence {code} retirée.")
            continue
        nums_avant = set(avant[code]["parties"])
        nums_apres = {p["numero"] for p in apres[code]["parties"]}
        for n in sorted(nums_avant - nums_apres):
            if commencee:
                res["raisons"].append(f"La séquence {code} a commencé : sa partie {n} ne "
                                      "peut pas être retirée.")
            res["changements"].append(f"{code} : partie {n} retirée.")
        for n in sorted(nums_apres - nums_avant):
            res["changements"].append(f"{code} : partie {n} ajoutée.")
        for p in apres[code]["parties"]:
            if p["numero"] in avant[code]["parties"] and \
                    float(avant[code]["parties"][p["numero"]] or 0) != float(p["nb_seances"]):
                res["changements"].append(f"{code} partie {p['numero']} : durée "
                                          f"{_fmt(avant[code]['parties'][p['numero']])} → "
                                          f"{_fmt(p['nb_seances'])} séance(s).")
        if avant[code]["nom"] != noms.get(code, avant[code]["nom"]):
            res["changements"].append(f"{code} renommée : {noms[code]}.")
    for code in apres:
        if code not in avant:
            res["changements"].append(f"Séquence {code} ajoutée ({noms.get(code, '')}).")
    refs_avant = _refs_actuelles(conn, rid)
    refs_apres = {d["ref"] for _, _, d in _documents(doc)}
    nb_plus, nb_moins = len(refs_apres - refs_avant), len(refs_avant - refs_apres)
    if nb_plus or nb_moins:
        res["changements"].append(f"Documents : {nb_plus} ajouté(s), {nb_moins} retiré(s).")
    disparus = refs_avant - refs_apres
    if disparus:
        q = "SELECT DISTINCT doc_ref, doc_libelle FROM progression_doc WHERE doc_ref IN (%s)" % \
            ",".join("?" * len(disparus))
        try:
            res["orphelins"] = [f"{x['doc_libelle'] or x['doc_ref']}"
                                for x in conn.execute(q, sorted(disparus)).fetchall()]
        except Exception:
            res["orphelins"] = []
    if res["raisons"]:
        res["statut"] = "refuse"
    return res


def _fmt(v) -> str:
    f = float(v or 0)
    return str(int(f)) if f.is_integer() else str(f)


def analyser(conn, data_dir: Path, contenu: bytes,
             aujourd_hui: date | None = None) -> dict:
    migrer(conn)
    manifeste, docs, z = _lire(contenu)
    z.close()
    aujourd_hui = aujourd_hui or date.today()
    return {"paquet": {"nom": manifeste.get("nom", ""), "cree_le": manifeste.get("cree_le", ""),
                       "cree_par": manifeste.get("cree_par", ""),
                       "nb_fichiers": len(manifeste.get("fichiers", [])),
                       "rapport": manifeste.get("rapport", {})},
            "referentiels": [_analyser_un(conn, data_dir, rid, doc, aujourd_hui)
                             for rid, doc in docs.items()]}


# ── Import ───────────────────────────────────────────────────────────────────

def _nom_sur(nom: str) -> str:
    return (nom or "document").strip().replace("/", "_").replace("\\", "_")


def _appliquer(conn, data_dir: Path, rid: str, doc: dict, z: zipfile.ZipFile,
               chemins: dict, maintenant: str) -> None:
    ref = doc["referentiel"]
    st = doc["structure"]
    data_dir = Path(data_dir)
    # Fichiers d'abord (si l'écriture échoue, la base n'est pas touchée).
    fichiers_ext, docs_compiles = [], []
    for seq, partie, d in _documents(doc):
        f = d["fichier"]
        contenu = z.read(chemins[f["sha256"]])
        if d["origine"] == "fichier":
            rel = f"referentiels_fichiers/{rid}/{d['ref']}_{_nom_sur(f['nom'])}"
            fichiers_ext.append((seq, partie, d, rel))
        else:
            rel = f"referentiels/{rid}/_verrouille/pdfs/{_nom_sur(f['nom'])}"
            docs_compiles.append((seq, partie, d, rel))
        cible = data_dir / rel
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(contenu)
    # Structure figée : remplacée en entier pour ce référentiel.
    for t in ("referentiel_objectifs", "referentiel_parties", "referentiel_sequences",
              "referentiel_themes", "referentiel_fichiers", "referentiel_docs_publies",
              "referentiel_titres_publies"):
        conn.execute(f"DELETE FROM {t} WHERE referentiel_id=?", (rid,))
    existe = conn.execute("SELECT 1 FROM referentiel_niveaux WHERE id=?", (rid,)).fetchone()
    valeurs = (ref["niveau"], ref["version"], ref["description"], ref["etat"], ref["source"],
               ref["type"], ref["annee"] if ref["source"] == "externe" else "",
               ref.get("mode_seances") or "par_objectif", doc["empreinte"], maintenant)
    if existe:
        conn.execute("UPDATE referentiel_niveaux SET niveau=?, version=?, description=?, "
                     "etat=?, source=?, type_ref=?, annee=?, mode_seances=?, "
                     "origine='publication', publication_empreinte=?, "
                     "publication_importe_le=? WHERE id=?", valeurs + (rid,))
    else:
        conn.execute("INSERT INTO referentiel_niveaux (niveau, version, description, etat, "
                     "source, type_ref, annee, mode_seances, origine, publication_empreinte, "
                     "publication_importe_le, id) VALUES (?,?,?,?,?,?,?,?,'publication',?,?,?)",
                     valeurs + (rid,))
    for t in st["themes"]:
        conn.execute("INSERT INTO referentiel_themes (referentiel_id, code, nom, couleur) "
                     "VALUES (?,?,?,?)", (rid, t["code"], t["nom"], t["couleur"]))
    for s in st["decoupage"]:
        conn.execute("INSERT INTO referentiel_sequences (referentiel_id, code, numero, nom, "
                     "theme_code) VALUES (?,?,?,?,?)",
                     (rid, s["code"], s["numero"], s["nom"], s["theme"]))
    for s in doc["sequences"]:
        for p in s["parties"]:
            conn.execute("INSERT INTO referentiel_parties (referentiel_id, seq_code, numero, "
                         "nb_seances_R_AE, libelle) VALUES (?,?,?,?,?)",
                         (rid, s["code"], p["numero"], p["nb_seances"], p["libelle"]))
            for o in p["objectifs"]:
                c = o["criteres"]
                conn.execute(
                    "INSERT INTO referentiel_objectifs (referentiel_id, seq_code, code, nom, "
                    "fin_cycle, critere_f, critere_a, critere_e, partie_numero, nb_seances, "
                    "type_obj) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (rid, s["code"], o["code"], o["nom"], int(o["fin_cycle"]), c["F"], c["A"],
                     c["E"], p["numero"], o["nb_seances"], o["type"]))
            for nature, liste in (("notion", p["notions"]), ("methode", p["methodes"])):
                for i, a in enumerate(liste):
                    conn.execute(
                        "INSERT OR IGNORE INTO referentiel_titres_publies (referentiel_id, "
                        "seq_code, partie_numero, nature, atome_id, titre, ordre) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (rid, s["code"], p["numero"], nature, a["id"], a["titre"], i))
    for t in doc["types_documents"]:
        conn.execute("INSERT INTO types_documents (id, libelle, ordre, actif) VALUES "
                     "(?, ?, (SELECT COALESCE(MAX(ordre), 0) + 10 FROM types_documents), 1) "
                     "ON CONFLICT(id) DO UPDATE SET libelle=excluded.libelle", (t["id"], t["libelle"]))
    for i, (seq, partie, d, rel) in enumerate(fichiers_ext):
        f, pl = d["fichier"], d.get("placement") or {}
        delai = pl.get("delai") or {}
        conn.execute(
            "INSERT INTO referentiel_fichiers (id, referentiel_id, seq_code, partie_numero, "
            "nom_fichier, chemin, mime, taille, ordre, type_id, seance_n, retour, "
            "delai_type, delai_n) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d["ref"], rid, seq, partie, f["nom"], rel, f["mime"], f["taille"], (i + 1) * 10,
             d.get("type") or "", int(pl.get("seance") or 0), pl.get("retour") or "",
             delai.get("type") or "", int(delai.get("n") or 1)))
    for i, (seq, partie, d, rel) in enumerate(docs_compiles):
        f = d["fichier"]
        conn.execute(
            "INSERT INTO referentiel_docs_publies (referentiel_id, ref, type_document, seq_code, "
            "partie_numero, libelle, nom_fichier, chemin, mime, taille, sha256, ordre) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, d["ref"], d.get("type") or "", seq, partie, d["libelle"], f["nom"], rel,
             f.get("mime") or "", f["taille"], f["sha256"], i))
    # Fichiers d'un import précédent qui ne servent plus.
    gardes = {rel for *_, rel in fichiers_ext}
    dossier = data_dir / "referentiels_fichiers" / rid
    if dossier.is_dir():
        for p in dossier.iterdir():
            if p.is_file() and f"referentiels_fichiers/{rid}/{p.name}" not in gardes:
                p.unlink()


def importer(conn_fabrique, data_dir: Path, contenu: bytes,
             aujourd_hui: date | None = None) -> dict:
    """Importe les référentiels acceptés du paquet. `conn_fabrique` : appelable
    qui ouvre une connexion transactionnelle (store._conn) ; un référentiel =
    une transaction. Retourne l'analyse complétée (statut final, erreurs)."""
    with conn_fabrique() as conn:
        migrer(conn)
        manifeste, docs, z = _lire(contenu)
        analyse = {"paquet": {"nom": manifeste.get("nom", ""),
                              "cree_le": manifeste.get("cree_le", "")},
                   "referentiels": [_analyser_un(conn, data_dir, rid, doc,
                                                 aujourd_hui or date.today())
                                    for rid, doc in docs.items()]}
    chemins = {f["sha256"]: f["chemin"] for f in manifeste["fichiers"]}
    maintenant = datetime.now().astimezone().isoformat(timespec="seconds")
    with z:
        for res in analyse["referentiels"]:
            rid = res["id"]
            res["importe"] = False
            if res["statut"] in ("nouveau", "mise_a_jour"):
                try:
                    with conn_fabrique() as conn:
                        _appliquer(conn, data_dir, rid, docs[rid], z, chemins, maintenant)
                    res["importe"] = True
                except Exception as e:                       # pragma: no cover
                    res["statut"] = "refuse"
                    res["raisons"].append(f"Échec de l'import : {e}")
            with conn_fabrique() as conn:
                conn.execute(
                    "INSERT INTO imports_publication (id, importe_le, nom_paquet, "
                    "referentiel_id, nom, empreinte, statut, rapport) VALUES (?,?,?,?,?,?,?,?)",
                    ("imp_" + uuid.uuid4().hex[:10], maintenant, analyse["paquet"]["nom"], rid,
                     res["nom"], res["empreinte"], res["statut"],
                     json.dumps({k: res[k] for k in ("raisons", "changements", "orphelins")},
                                ensure_ascii=False)))
    return analyse


def journal(conn, limite: int = 30) -> list[dict]:
    migrer(conn)
    return [{**dict(r), "rapport": json.loads(r["rapport"] or "{}")}
            for r in conn.execute("SELECT * FROM imports_publication ORDER BY importe_le DESC, "
                                  "rowid DESC LIMIT ?", (limite,)).fetchall()]


def importes(conn) -> list[dict]:
    """Référentiels présents issus d'une publication."""
    migrer(conn)
    from services.referentiel_principal_externe import nom_calcule
    return [{"id": r["id"], "nom": nom_calcule(dict(r)), "niveau": r["niveau"],
             "type": r["type_ref"], "source": r["source"], "etat": r["etat"],
             "empreinte": r["publication_empreinte"], "importe_le": r["publication_importe_le"]}
            for r in conn.execute("SELECT * FROM referentiel_niveaux WHERE origine='publication' "
                                  "ORDER BY niveau, annee, version").fetchall()]
