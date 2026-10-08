"""services/format_referentiel.py — v0.51.1

Format d'échange JSON d'un référentiel : `seqenseigne.referentiel` v1.
Description complète : doc/format_referentiel.md ; schéma :
schemas/referentiel-1.json.

Un fichier par référentiel (interne ou externe, principal ou MER), qui se
suffit à lui-même : il décrit la structure qu'il utilise (cycle, niveau,
thèmes, découpage en séquences du niveau), puis le détail des séquences
(parties, objectifs, titres des notions et méthodes, documents).

Règles :
  - identifiants stables = clés déjà utilisées par l'appli (id du
    référentiel, code de séquence, numéro de partie, code d'objectif, `ref`
    des documents : id de fichier externe, ou « type|cible » pour un PDF
    compilé) ;
  - textes en texte lisible (sans LaTeX) ; la source LaTeX est ajoutée dans
    un champ `…_latex` seulement quand elle diffère ;
  - le contenu des fichiers n'est pas dans le JSON (nom, taille, sha256) ;
  - `empreinte` : sha256 du contenu canonique, hors métadonnées d'export et
    hors état — deux publications identiques ont la même empreinte ;
  - un référentiel interne verrouillé (ou utilisé) est publié une fois pour
    toutes : la première publication est conservée dans
    data/referentiels/<id>/_publication/referentiel.json et resservie à
    l'identique (seul l'état est mis à jour).

Seuls les référentiels de la structure figée (table referentiel_niveaux) sont
exportables ; l'ancien modèle de MER (referentiel_externe) ne l'est pas.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from services.texte_latex import vers_texte

FORMAT = "seqenseigne.referentiel"
FORMAT_VERSION = "1.0"
VERSION_APPLI = "0.51.1"

ETATS_FIGES = ("verrouille", "utilise")
_NIVEAUX_DEFAUT = {"N07": ("CM1", "cours moyen 1re année"),
                   "N08": ("CM2", "cours moyen 2e année"),
                   "N09": ("6e", "sixième"), "N10": ("5e", "cinquième"),
                   "N11": ("4e", "quatrième"), "N12": ("3e", "troisième")}
_ANNEE_DANS_CYCLE = {"anneeun": 1, "anneedeux": 2, "anneetrois": 3}

_LIBELLES_COMPILES = {
    "livret_sequence": "Livret de séquence",
    "livret_cours": "Livret de cours",
    "livret_fiches": "Livret de fiches",
    "livret_plans": "Livret de plans de travail",
    "livret_corriges": "Livret de corrigés",
    "livret_exercices": "Livret d'exercices",
    "livret_cartes_planches": "Planches de cartes d'automatisme",
    "livret_cartes_recap": "Récap des cartes d'automatisme",
    "evaluation": "Évaluation",
}


class FormatErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides"):
        super().__init__(message)
        self.code = code


# ── Textes ───────────────────────────────────────────────────────────────────

def _texte(cible: dict, cle: str, valeur) -> None:
    """cible[cle] = texte lisible ; cible[cle_latex] = source si différente."""
    src = valeur or ""
    txt = vers_texte(src)
    cible[cle] = txt
    if re.sub(r"\s+", " ", src).strip() != txt:
        cible[cle + "_latex"] = src


def _nombre(v):
    if v is None:
        return 0
    f = float(v)
    return int(f) if f.is_integer() else f


# ── Empreintes ───────────────────────────────────────────────────────────────

def _canonique(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _sha(obj) -> str:
    return "sha256:" + hashlib.sha256(_canonique(obj)).hexdigest()


def empreinte(doc: dict) -> str:
    """Empreinte du contenu : hors métadonnées d'export, hors état."""
    d = copy.deepcopy(doc)
    for k in ("exporte_le", "exporte_par", "empreinte", "publication_figee"):
        d.pop(k, None)
    d.get("referentiel", {}).pop("etat", None)
    return _sha(d)


def empreinte_structure(structure: dict) -> str:
    d = {k: v for k, v in structure.items() if k != "empreinte"}
    return _sha(d)


def sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 16), b""):
            h.update(bloc)
    return h.hexdigest()


# ── Lecture de la base ───────────────────────────────────────────────────────

def _ref(conn, rid: str) -> dict:
    r = conn.execute("SELECT * FROM referentiel_niveaux WHERE id=?", (rid,)).fetchone()
    if r is None:
        if _table_existe(conn, "referentiel_externe") and conn.execute(
                "SELECT 1 FROM referentiel_externe WHERE id=?", (rid,)).fetchone():
            raise FormatErreur("Ancien modèle de MER : non exportable. Recréez-le "
                               "dans la structure figée (Conception › Référentiel).",
                               "ancien_modele")
        raise FormatErreur(f"Référentiel introuvable : {rid}", "introuvable")
    return dict(r)


def _table_existe(conn, nom: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (nom,)).fetchone() is not None


def _colonnes(conn, table: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _annee(ref: dict) -> str:
    if (ref.get("source") or "interne") == "externe" and ref.get("annee"):
        return ref["annee"]
    try:
        y = int(str(ref.get("version") or "")[:4])
        return f"{y}-{y + 1}"
    except ValueError:
        return ref.get("annee") or ""


def _structure(conn, ref: dict) -> dict:
    rid, niveau = ref["id"], ref["niveau"]
    niv = None
    if _table_existe(conn, "param_niveaux"):
        niv = conn.execute("SELECT * FROM param_niveaux WHERE code=?", (niveau,)).fetchone()
    court, long_ = _NIVEAUX_DEFAUT.get(niveau, (niveau, ""))
    cycle_code = niv["cycle_code"] if niv else ""
    cycle_nom = ""
    if cycle_code and _table_existe(conn, "cycles"):
        c = conn.execute("SELECT nom FROM cycles WHERE code=?", (cycle_code,)).fetchone()
        cycle_nom = c["nom"] if c else ""
    niveau_bloc = {"code": niveau,
                   "nom_court": (niv["nom_court"] if niv else court) or court,
                   "nom_long": (niv["nom_long"] if niv else long_) or long_}
    if niv and niv["annee_dans_cycle"] in _ANNEE_DANS_CYCLE:
        niveau_bloc["annee_dans_cycle"] = _ANNEE_DANS_CYCLE[niv["annee_dans_cycle"]]
    themes = []
    for i, t in enumerate(conn.execute(
            "SELECT * FROM referentiel_themes WHERE referentiel_id=? ORDER BY code",
            (rid,)).fetchall(), start=1):
        th = {"code": t["code"]}
        _texte(th, "nom", t["nom"])
        th["couleur"] = t["couleur"] or ""
        th["ordre"] = i
        themes.append(th)
    decoupage = []
    for s in conn.execute("SELECT * FROM referentiel_sequences WHERE referentiel_id=? "
                          "ORDER BY numero, code", (rid,)).fetchall():
        d = {"code": s["code"], "numero": int(s["numero"])}
        _texte(d, "nom", s["nom"])
        d["theme"] = s["theme_code"] or None
        decoupage.append(d)
    st = {"cycle": {"code": cycle_code, "nom": cycle_nom} if cycle_code else None,
          "niveau": niveau_bloc, "themes": themes, "decoupage": decoupage}
    st["empreinte"] = empreinte_structure(st)
    return st


def _notions_methodes(conn, niveau: str, seq: str, numero: int) -> tuple[list, list]:
    """Titres des notions et méthodes rattachées aux objectifs de la partie
    (mêmes règles que la synthèse Pronote). Vide pour un référentiel externe."""
    if not (_table_existe(conn, "objectifs") and _table_existe(conn, "sequence_parties")):
        return [], []
    from services.synthese_seance import candidats
    try:
        c = candidats(conn, niveau, seq, numero, numero)
    except Exception:
        return [], []
    notions = [{"id": n["id"], "titre": n["titre"]} for n in c["notions"]]
    methodes = [{"id": m["id"], "titre": m["titre"]} for m in c["methodes"]]
    return notions, methodes


def _doc_fichier(f: dict, data_dir: Path | None) -> dict:
    d = {"ref": f["id"], "origine": "fichier", "type": f.get("type_id") or None}
    lib = (f"{f['type_libelle']} : " if f.get("type_libelle") else "") + f["nom_fichier"]
    d["libelle"] = lib
    fich = {"nom": f["nom_fichier"], "mime": f.get("mime") or "",
            "taille": int(f.get("taille") or 0)}
    if data_dir is not None and f.get("chemin"):
        p = Path(data_dir) / f["chemin"]
        if p.is_file():
            fich["taille"] = p.stat().st_size
            fich["sha256"] = sha256_fichier(p)
    d["fichier"] = fich
    seance = int(f.get("seance_n") or 0)
    retour = f.get("retour") or ""
    if seance or retour:
        pl = {"seance": seance or None, "retour": retour or None, "delai": None}
        if f.get("delai_type"):
            pl["delai"] = {"type": f["delai_type"], "n": int(f.get("delai_n") or 1)}
        d["placement"] = pl
    else:
        d["placement"] = None
    return d


def _fichiers(conn, rid: str, seq: str, partie: int) -> list[dict]:
    if not _table_existe(conn, "referentiel_fichiers"):
        return []
    jointure = _table_existe(conn, "types_documents")
    q = ("SELECT f.*" + (", COALESCE(t.libelle, '') AS type_libelle" if jointure else "")
         + " FROM referentiel_fichiers f"
         + (" LEFT JOIN types_documents t ON t.id=f.type_id" if jointure else "")
         + " WHERE f.referentiel_id=? AND f.seq_code=? AND f.partie_numero=?"
           " ORDER BY f.ordre, f.nom_fichier")
    return [dict(r) for r in conn.execute(q, (rid, seq, partie)).fetchall()]


def _pdf_compile(data_dir: Path | None, rid: str, nom: str, fige: bool) -> dict | None:
    if data_dir is None:
        return None
    base = Path(data_dir) / "referentiels" / rid
    for p in ((base / "_verrouille" / "pdfs" / nom) if fige else None, base / nom,
              base / "_verrouille" / "pdfs" / nom):
        if p is not None and p.is_file():
            return {"nom": nom, "mime": "application/pdf", "taille": p.stat().st_size,
                    "sha256": sha256_fichier(p)}
    return None


def _documents_compiles(conn, ref: dict, data_dir: Path | None) -> dict:
    """{(seq_code or ''): [doc, ...]} — PDF compilés d'un référentiel interne."""
    out: dict[str, list] = {}
    if (ref.get("source") or "interne") == "externe" or \
            not _table_existe(conn, "referentiel_documents"):
        return out
    from services.referentiel_documents_compilation import lister_cibles_document
    fige = ref.get("etat") in ETATS_FIGES
    for doc in conn.execute("SELECT * FROM referentiel_documents WHERE referentiel_id=? "
                            "ORDER BY ordre, type_document", (ref["id"],)).fetchall():
        type_doc = doc["type_document"]
        try:
            cibles = lister_cibles_document(conn, doc["id"], ref["id"], type_doc)
        except Exception:
            cibles = []
        for c in cibles:
            cid = c.get("cible_id", "")
            seq = c.get("sequence") or (cid.split("/", 1)[1] if "/" in cid else "")
            lib = _LIBELLES_COMPILES.get(type_doc, type_doc)
            if seq:
                lib += f" — {seq}"
            elif type_doc == "evaluation":
                lib = c.get("libelle") or lib
            out.setdefault(seq, []).append({
                "ref": f"{type_doc}|{cid}", "origine": "compile", "type": type_doc,
                "libelle": lib,
                "fichier": _pdf_compile(data_dir, ref["id"], c.get("nom_fichier", ""), fige),
                "placement": None})
    return out


def _types_utilises(conn, doc: dict) -> list[dict]:
    ids = set()

    def _parcourir(docs):
        for d in docs:
            if d["origine"] == "fichier" and d.get("type"):
                ids.add(d["type"])
    _parcourir(doc["documents_annuels"])
    for s in doc["sequences"]:
        _parcourir(s["documents"])
        for p in s["parties"]:
            _parcourir(p["documents"])
    if not ids or not _table_existe(conn, "types_documents"):
        return []
    q = "SELECT * FROM types_documents WHERE id IN (%s) ORDER BY ordre, libelle" % \
        ",".join("?" * len(ids))
    return [{"id": t["id"], "libelle": t["libelle"]}
            for t in conn.execute(q, sorted(ids)).fetchall()]


def construire(conn, rid: str, data_dir: Path | None = None) -> dict:
    """Document JSON d'un référentiel, calculé depuis la base (sans tenir
    compte d'une publication figée)."""
    ref = _ref(conn, rid)
    from services.referentiel_principal_externe import nom_calcule
    source = ref.get("source") or "interne"
    entete = {"id": rid, "nom": nom_calcule(ref), "niveau": ref["niveau"],
              "annee": _annee(ref), "type": ref.get("type_ref") or "principal",
              "source": source, "version": ref.get("version") or "",
              "etat": ref.get("etat") or "en_cours",
              "description": ref.get("description") or ""}
    if ref.get("mode_seances"):
        entete["mode_seances"] = ref["mode_seances"]
    structure = _structure(conn, ref)
    compiles = _documents_compiles(conn, ref, data_dir)
    cols_obj = _colonnes(conn, "referentiel_objectifs")
    par_serie = _table_existe(conn, "referentiel_parties_seances")
    sequences = []
    for s in structure["decoupage"]:
        code = s["code"]
        parties = []
        for p in conn.execute("SELECT * FROM referentiel_parties WHERE referentiel_id=? "
                              "AND seq_code=? ORDER BY numero", (rid, code)).fetchall():
            p = dict(p)
            num = int(p["numero"])
            partie = {"numero": num}
            _texte(partie, "libelle", p.get("libelle") or "")
            partie["nb_seances"] = _nombre(p.get("nb_seances_R_AE"))
            objectifs = []
            for o in conn.execute(
                    "SELECT * FROM referentiel_objectifs WHERE referentiel_id=? AND "
                    "seq_code=? AND partie_numero=? ORDER BY code", (rid, code, num)).fetchall():
                o = dict(o)
                ob = {"code": o["code"],
                      "type": (o.get("type_obj") if "type_obj" in cols_obj else None)
                      or "capacite"}
                _texte(ob, "nom", o["nom"])
                ob["nb_seances"] = _nombre(o.get("nb_seances"))
                ob["fin_cycle"] = bool(o.get("fin_cycle"))
                crit, crit_src = {}, {}
                for lettre in ("F", "A", "E"):
                    src = o.get("critere_" + lettre.lower()) or ""
                    crit[lettre] = vers_texte(src)
                    if re.sub(r"\s+", " ", src).strip() != crit[lettre]:
                        crit_src[lettre] = src
                ob["criteres"] = crit
                if crit_src:
                    ob["criteres_latex"] = crit_src
                objectifs.append(ob)
            partie["nb_seances_objectifs"] = _nombre(sum(o["nb_seances"] for o in objectifs))
            partie["objectifs"] = objectifs
            if par_serie and ref.get("mode_seances") == "par_serie":
                partie["seances_par_serie"] = [
                    {"niveau_cible": r["niveau_cible"], "serie": r["serie"],
                     "nb_seances": _nombre(r["nb_seances"])}
                    for r in conn.execute(
                        "SELECT * FROM referentiel_parties_seances WHERE referentiel_id=? "
                        "AND seq_code=? AND partie_numero=? ORDER BY niveau_cible, serie",
                        (rid, code, num)).fetchall()]
            notions, methodes = ((_notions_methodes(conn, ref["niveau"], code, num))
                                 if source == "interne" else ([], []))
            partie["notions"] = notions
            partie["methodes"] = methodes
            partie["documents"] = [_doc_fichier(f, data_dir)
                                   for f in _fichiers(conn, rid, code, num)]
            parties.append(partie)
        sequences.append({
            "code": code, "parties": parties,
            "documents": [_doc_fichier(f, data_dir) for f in _fichiers(conn, rid, code, 0)]
            + compiles.get(code, [])})
    annuels = [_doc_fichier(f, data_dir) for f in _fichiers(conn, rid, "", 0)]
    annuels += compiles.get("", [])
    for code, docs in compiles.items():          # séquence hors découpage
        if code and code not in {s["code"] for s in sequences}:
            annuels += docs
    doc = {"format": FORMAT, "format_version": FORMAT_VERSION,
           "exporte_le": datetime.now().astimezone().isoformat(timespec="seconds"),
           "exporte_par": f"seqenseigne {VERSION_APPLI}",
           "empreinte": "", "referentiel": entete, "structure": structure,
           "types_documents": [], "sequences": sequences,
           "documents_annuels": annuels}
    doc["types_documents"] = _types_utilises(conn, doc)
    doc["empreinte"] = empreinte(doc)
    return doc


# ── Publication figée (référentiels internes verrouillés) ────────────────────

def _chemin_publication(data_dir: Path, rid: str) -> Path:
    return Path(data_dir) / "referentiels" / rid / "_publication" / "referentiel.json"


def exporter(conn, rid: str, data_dir: Path | None = None,
             profil: str = "atelier", figer: bool = True) -> dict:
    """Document à publier. Un référentiel interne verrouillé ou utilisé est
    publié une fois pour toutes : sa première publication est conservée et
    resservie (état et métadonnées d'export mis à jour). `figer=False`
    (simple vérification) : ne conserve rien."""
    ref = _ref(conn, rid)
    fige = (ref.get("source") or "interne") == "interne" and ref.get("etat") in ETATS_FIGES
    chemin = _chemin_publication(data_dir, rid) if (fige and data_dir) else None
    if chemin is not None and chemin.is_file():
        doc = json.loads(chemin.read_text(encoding="utf-8"))
        doc["referentiel"]["etat"] = ref.get("etat")
        doc["exporte_le"] = datetime.now().astimezone().isoformat(timespec="seconds")
        doc["exporte_par"] = f"seqenseigne {VERSION_APPLI} ({profil})"
        doc["publication_figee"] = True
        return doc
    doc = construire(conn, rid, data_dir)
    doc["exporte_par"] = f"seqenseigne {VERSION_APPLI} ({profil})"
    if chemin is not None and figer:
        erreurs = valider(doc)
        if not erreurs:
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                              encoding="utf-8")
            doc["publication_figee"] = True
    return doc


# ── Validation ───────────────────────────────────────────────────────────────

_SCHEMA = None


def schema() -> dict:
    global _SCHEMA
    if _SCHEMA is None:
        p = Path(__file__).resolve().parent.parent / "schemas" / "referentiel-1.json"
        _SCHEMA = json.loads(p.read_text(encoding="utf-8"))
    return _SCHEMA


def valider(doc: dict) -> list[str]:
    """Erreurs (liste vide = valide) : schéma + cohérence interne."""
    from services.schema_json import valider as valider_schema
    d = {k: v for k, v in doc.items() if k != "publication_figee"}
    erreurs = valider_schema(d, schema())
    if erreurs:
        return erreurs
    major = str(doc["format_version"]).split(".")[0]
    if major != FORMAT_VERSION.split(".")[0]:
        erreurs.append(f"format_version {doc['format_version']} non pris en charge "
                       f"(attendu {FORMAT_VERSION.split('.')[0]}.x)")
    st = doc["structure"]
    themes = {t["code"] for t in st["themes"]}
    if len(themes) != len(st["themes"]):
        erreurs.append("structure.themes : codes en double")
    codes = [s["code"] for s in st["decoupage"]]
    if len(set(codes)) != len(codes):
        erreurs.append("structure.decoupage : codes de séquence en double")
    for s in st["decoupage"]:
        if s["theme"] is not None and s["theme"] not in themes:
            erreurs.append(f"structure.decoupage {s['code']} : thème {s['theme']} inconnu")
    if st.get("empreinte") != empreinte_structure(st):
        erreurs.append("structure.empreinte ne correspond pas au contenu")
    vus_seq = set()
    refs = []
    types = {t["id"] for t in doc["types_documents"]}

    def _docs(chemin, docs):
        for d in docs:
            refs.append(d["ref"])
            if d["origine"] == "fichier" and d.get("type") and d["type"] not in types:
                erreurs.append(f"{chemin} : type de document {d['type']} absent de "
                               "types_documents")
    for s in doc["sequences"]:
        if s["code"] not in codes:
            erreurs.append(f"sequences {s['code']} : absente du découpage")
        if s["code"] in vus_seq:
            erreurs.append(f"sequences {s['code']} : en double")
        vus_seq.add(s["code"])
        nums = [p["numero"] for p in s["parties"]]
        if len(set(nums)) != len(nums):
            erreurs.append(f"sequences {s['code']} : numéros de partie en double")
        _docs(f"sequences {s['code']}", s["documents"])
        for p in s["parties"]:
            obj = [o["code"] for o in p["objectifs"]]
            if len(set(obj)) != len(obj):
                erreurs.append(f"{s['code']} partie {p['numero']} : codes d'objectif en double")
            _docs(f"{s['code']} partie {p['numero']}", p["documents"])
    _docs("documents_annuels", doc["documents_annuels"])
    doublons = sorted({r for r in refs if refs.count(r) > 1})
    if doublons:
        erreurs.append("documents : ref en double : " + ", ".join(doublons))
    if doc.get("empreinte") != empreinte(doc):
        erreurs.append("empreinte ne correspond pas au contenu")
    return erreurs


def bilan(doc: dict) -> dict:
    """Résumé lisible (vérification avant publication)."""
    nb_parties = sum(len(s["parties"]) for s in doc["sequences"])
    docs = list(doc["documents_annuels"])
    for s in doc["sequences"]:
        docs += s["documents"]
        for p in s["parties"]:
            docs += p["documents"]
    return {"empreinte": doc["empreinte"],
            "structure_empreinte": doc["structure"]["empreinte"],
            "nb_sequences": len(doc["sequences"]), "nb_parties": nb_parties,
            "nb_documents": len(docs),
            "documents_sans_fichier": [d["libelle"] for d in docs if not d.get("fichier")],
            "publication_figee": bool(doc.get("publication_figee"))}
