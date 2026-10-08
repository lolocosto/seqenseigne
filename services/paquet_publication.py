"""services/paquet_publication.py — v0.51.2

Paquet de publication (profil atelier) : un fichier zip qui transporte un ou
plusieurs référentiels vers l'appli en ligne (profil classe).

    paquet_AAAA-MM-JJ_HHMM.zip
    ├── paquet.json                 manifeste (format seqenseigne.paquet v1)
    ├── referentiels/<id>.json      un JSON par référentiel (seqenseigne.referentiel v1)
    └── fichiers/<sha256>.<ext>     contenu des documents, nommés par leur empreinte

Règles :
  - publiables : internes verrouillés ou utilisés ; externes (et MER figées)
    non annulés ; l'ancien modèle de MER ne l'est pas ;
  - chaque document du JSON doit avoir son fichier, d'empreinte identique :
    sinon le paquet est refusé (rapport) ;
  - un fichier commun à plusieurs documents ou référentiels n'est stocké
    qu'une fois ;
  - chaque création de paquet est inscrite au journal (table publications).

Description du format : doc/format_paquet.md.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path

from services import format_referentiel as fmt

FORMAT = "seqenseigne.paquet"
FORMAT_VERSION = "1.0"

_EXT = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg",
        "application/vnd.oasis.opendocument.text": ".odt",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx"}


class PaquetErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides", rapport=None):
        super().__init__(message)
        self.code = code
        self.rapport = rapport or {}


def migrer(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS publications (
            id           TEXT PRIMARY KEY,
            cree_le      TEXT NOT NULL,
            nom_paquet   TEXT NOT NULL,
            referentiels TEXT NOT NULL DEFAULT '[]',   -- JSON [{id, nom, empreinte}]
            nb_fichiers  INTEGER NOT NULL DEFAULT 0,
            taille       INTEGER NOT NULL DEFAULT 0
        )""")


# ── Référentiels publiables ──────────────────────────────────────────────────

def _publiable(r: dict) -> bool:
    if (r.get("source") or "interne") == "externe":
        return r.get("etat") != "annule"
    return r.get("etat") in fmt.ETATS_FIGES


def _derniere_publication(conn, rid: str) -> dict | None:
    for p in conn.execute("SELECT * FROM publications ORDER BY cree_le DESC").fetchall():
        for r in json.loads(p["referentiels"] or "[]"):
            if r.get("id") == rid:
                return {"cree_le": p["cree_le"], "nom_paquet": p["nom_paquet"],
                        "empreinte": r.get("empreinte")}
    return None


def lister_publiables(conn, data_dir: Path | None) -> list[dict]:
    """Référentiels publiables, avec l'empreinte actuelle et la dernière
    publication (modifié depuis ?)."""
    migrer(conn)
    from services.referentiel_principal_externe import nom_calcule
    out = []
    for r in conn.execute("SELECT * FROM referentiel_niveaux ORDER BY niveau, "
                          "COALESCE(annee, ''), version").fetchall():
        r = dict(r)
        if not _publiable(r):
            continue
        try:
            doc = fmt.exporter(conn, r["id"], data_dir, figer=False)
            empreinte, erreurs = doc["empreinte"], fmt.valider(doc)
        except fmt.FormatErreur as e:
            empreinte, erreurs = "", [str(e)]
        der = _derniere_publication(conn, r["id"])
        out.append({"id": r["id"], "nom": nom_calcule(r), "niveau": r["niveau"],
                    "type": r.get("type_ref") or "principal",
                    "source": r.get("source") or "interne", "etat": r["etat"],
                    "empreinte": empreinte, "valide": not erreurs, "erreurs": erreurs[:5],
                    "derniere_publication": der,
                    "modifie_depuis": bool(der and der["empreinte"] != empreinte)})
    return out


# ── Localisation des fichiers ────────────────────────────────────────────────

def _documents(doc: dict) -> list[dict]:
    docs = list(doc["documents_annuels"])
    for s in doc["sequences"]:
        docs += s["documents"]
        for p in s["parties"]:
            docs += p["documents"]
    return docs


def _chemin_document(conn, data_dir: Path, rid: str, d: dict) -> Path | None:
    nom = (d.get("fichier") or {}).get("nom") or ""
    if d["origine"] == "fichier":
        r = conn.execute("SELECT chemin FROM referentiel_fichiers WHERE id=?",
                         (d["ref"],)).fetchone()
        return (Path(data_dir) / r["chemin"]) if r and r["chemin"] else None
    base = Path(data_dir) / "referentiels" / rid
    for p in (base / "_verrouille" / "pdfs" / nom, base / nom):
        if nom and p.is_file():
            return p
    return None


# ── Création ─────────────────────────────────────────────────────────────────

def creer(conn, data_dir: Path, rids: list[str], profil: str = "atelier",
          maintenant: datetime | None = None) -> tuple[bytes, dict]:
    """Construit le paquet (contenu zip, manifeste). Lève PaquetErreur (avec
    son rapport) si un référentiel n'est pas publiable ou incohérent, ou si un
    fichier manque ou a changé."""
    migrer(conn)
    rids = list(dict.fromkeys(r for r in rids if r))
    if not rids:
        raise PaquetErreur("Aucun référentiel choisi.")
    maintenant = maintenant or datetime.now().astimezone()
    erreurs: list[str] = []
    refs, fichiers = [], {}           # sha256 -> {chemin_zip, taille, mime, source}
    sans_pdf, ecarts = [], []
    jsons = {}
    for rid in rids:
        r = conn.execute("SELECT * FROM referentiel_niveaux WHERE id=?", (rid,)).fetchone()
        if r is None or not _publiable(dict(r)):
            erreurs.append(f"{rid} : référentiel introuvable ou non publiable "
                           "(interne non verrouillé, ou annulé).")
            continue
        omis: list = []
        try:
            doc = fmt.exporter(conn, rid, data_dir, profil, figer=True, omis=omis)
        except fmt.FormatErreur as e:
            erreurs.append(f"{rid} : {e}")
            continue
        for e in fmt.valider(doc):
            erreurs.append(f"{rid} : {e}")
        b = fmt.bilan(doc, omis)
        sans_pdf += [f"{doc['referentiel']['nom']} : {x}" for x in b["documents_sans_pdf"]]
        ecarts += [f"{doc['referentiel']['nom']} : {x}" for x in b["parties_ecart"]]
        for d in _documents(doc):
            f = d.get("fichier") or {}
            sha = f.get("sha256")
            chemin = _chemin_document(conn, data_dir, rid, d)
            if not sha or chemin is None or not chemin.is_file():
                erreurs.append(f"{doc['referentiel']['nom']} : fichier introuvable — "
                               f"{d['libelle']}")
                continue
            if sha not in fichiers:
                reel = fmt.sha256_fichier(chemin)
                if reel != sha:
                    erreurs.append(f"{doc['referentiel']['nom']} : fichier modifié depuis "
                                   f"la publication — {d['libelle']}")
                    continue
                ext = _EXT.get(f.get("mime") or "", Path(f["nom"]).suffix.lower())
                fichiers[sha] = {"sha256": sha, "chemin": f"fichiers/{sha}{ext}",
                                 "taille": chemin.stat().st_size,
                                 "mime": f.get("mime") or "", "_source": chemin}
        doc.pop("publication_figee", None)
        jsons[rid] = doc
        refs.append({"id": rid, "nom": doc["referentiel"]["nom"],
                     "niveau": doc["referentiel"]["niveau"],
                     "type": doc["referentiel"]["type"],
                     "empreinte": doc["empreinte"],
                     "chemin": f"referentiels/{rid}.json"})
    rapport = {"documents_sans_pdf": sans_pdf, "parties_ecart": ecarts,
               "erreurs": erreurs,
               "taille_totale": sum(f["taille"] for f in fichiers.values())}
    if erreurs:
        raise PaquetErreur("Le paquet ne peut pas être créé.", "paquet_invalide", rapport)
    nom = f"paquet_{maintenant:%Y-%m-%d_%H%M}.zip"
    manifeste = {"format": FORMAT, "format_version": FORMAT_VERSION,
                 "cree_le": maintenant.isoformat(timespec="seconds"),
                 "cree_par": f"seqenseigne {fmt.VERSION_APPLI} ({profil})",
                 "nom": nom, "referentiels": refs,
                 "fichiers": [{k: v for k, v in f.items() if k != "_source"}
                              for f in sorted(fichiers.values(), key=lambda x: x["chemin"])],
                 "rapport": rapport}
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("paquet.json", json.dumps(manifeste, ensure_ascii=False, indent=1))
        for rid, doc in jsons.items():
            z.writestr(f"referentiels/{rid}.json", json.dumps(doc, ensure_ascii=False, indent=1))
        for f in fichiers.values():
            # Les PDF sont déjà compressés : stockés tels quels.
            z.write(f["_source"], f["chemin"], compress_type=zipfile.ZIP_STORED)
    contenu = tampon.getvalue()
    import uuid
    conn.execute("INSERT INTO publications (id, cree_le, nom_paquet, referentiels, "
                 "nb_fichiers, taille) VALUES (?,?,?,?,?,?)",
                 ("pub_" + uuid.uuid4().hex[:10], manifeste["cree_le"], nom,
                  json.dumps([{k: r[k] for k in ("id", "nom", "empreinte")} for r in refs],
                             ensure_ascii=False), len(fichiers), len(contenu)))
    return contenu, manifeste


def journal(conn, limite: int = 20) -> list[dict]:
    migrer(conn)
    return [{**dict(r), "referentiels": json.loads(r["referentiels"] or "[]")}
            for r in conn.execute("SELECT * FROM publications ORDER BY cree_le DESC "
                                  "LIMIT ?", (limite,)).fetchall()]


# ── Lecture / vérification (utilisée par l'import, v0.51.3) ──────────────────

def verifier(contenu: bytes) -> tuple[dict, list[str]]:
    """(manifeste, erreurs) d'un paquet : structure, formats, empreintes de
    tous les fichiers et de tous les référentiels."""
    erreurs: list[str] = []
    try:
        z = zipfile.ZipFile(io.BytesIO(contenu))
    except zipfile.BadZipFile:
        return {}, ["Ce fichier n'est pas un paquet (zip illisible)."]
    with z:
        noms = set(z.namelist())
        if "paquet.json" not in noms:
            return {}, ["paquet.json absent."]
        m = json.loads(z.read("paquet.json").decode("utf-8"))
        if m.get("format") != FORMAT:
            return m, [f"Format inconnu : {m.get('format')!r}."]
        if str(m.get("format_version", "")).split(".")[0] != FORMAT_VERSION.split(".")[0]:
            erreurs.append(f"Version de paquet {m.get('format_version')} non prise en charge.")
        shas = set()
        for f in m.get("fichiers", []):
            if f["chemin"] not in noms:
                erreurs.append(f"Fichier absent du paquet : {f['chemin']}")
                continue
            import hashlib
            h = hashlib.sha256(z.read(f["chemin"])).hexdigest()
            if h != f["sha256"]:
                erreurs.append(f"Empreinte incorrecte : {f['chemin']}")
            shas.add(f["sha256"])
        for r in m.get("referentiels", []):
            if r["chemin"] not in noms:
                erreurs.append(f"Référentiel absent du paquet : {r['chemin']}")
                continue
            doc = json.loads(z.read(r["chemin"]).decode("utf-8"))
            erreurs += [f"{r['id']} : {e}" for e in fmt.valider(doc)]
            if doc.get("empreinte") != r.get("empreinte"):
                erreurs.append(f"{r['id']} : empreinte différente du manifeste")
            for d in _documents(doc):
                sha = (d.get("fichier") or {}).get("sha256")
                if sha not in shas:
                    erreurs.append(f"{r['id']} : fichier manquant pour {d['libelle']}")
    return m, erreurs
