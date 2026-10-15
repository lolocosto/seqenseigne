"""services/retour_usage.py — v0.51.8

Retour d'usage (appli en ligne → appli locale), sur le protocole d'échange
(services/echanges.py, type « usage ») :

  - **côté classe** (`creer`) : pour chaque référentiel importé, son
    empreinte de publication, s'il est utilisé (et depuis quand), la date de
    début du premier créneau de chaque séquence planifiée, les parties de
    MER posées — sans aucune donnée d'élève, ni classe, ni établissement.
    Fichier JSON `seqenseigne.usage` v1, numéroté, archivé (renvoi) ; son
    accusé acquitte les paquets reçus ;
  - **côté atelier** (`importer`) : contrôle de séquence (règle stricte),
    lien à l'appli en ligne, acquittement des paquets (retirés de
    l'archive), usage enregistré **sans jamais perdre un verrou** (séquence
    commencée, référentiel utilisé : union avec les retours précédents) ;
    un interne verrouillé utilisé passe « utilisé » ;
  - **états de synchronisation** (`etat_synchro`) de chaque référentiel
    publié : synchronisé, modifié depuis la publication, publication en
    attente, en retard, désynchronisé.

Les verrous de l'atelier (services/referentiel_principal_externe.py)
combinent la base locale et ces retours (`sequences_commencees`,
`utilise`).
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from services import echanges as ech

FORMAT = "seqenseigne.usage"
FORMAT_VERSION = "1.0"

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_recu (
    referentiel_id  TEXT PRIMARY KEY,
    empreinte       TEXT NOT NULL DEFAULT '',  -- empreinte de la publication utilisée en classe
    utilise         INTEGER NOT NULL DEFAULT 0,
    utilise_depuis  TEXT NOT NULL DEFAULT '',
    sequences       TEXT NOT NULL DEFAULT '{}', -- {code: date de début du 1er créneau}
    parties_mer     TEXT NOT NULL DEFAULT '[]', -- ["M01|2", …]
    numero          INTEGER NOT NULL DEFAULT 0, -- n° du dernier retour qui en parle
    recu_le         TEXT NOT NULL DEFAULT ''
);
"""


class UsageErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides", erreurs=None):
        super().__init__(message)
        self.code = code
        self.erreurs = erreurs or []


def migrer(conn) -> None:
    conn.executescript(SCHEMA)
    ech.migrer(conn)


def _table(conn, nom) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (nom,)).fetchone() is not None


# ── Côté classe : construction ───────────────────────────────────────────────

def _usage_referentiel(conn, r: dict) -> dict:
    rid = r["id"]
    debuts: dict[str, str] = {}
    if _table(conn, "creneaux"):
        for c in conn.execute(
                "SELECT c.seq_code, MIN(c.date_debut) AS debut FROM creneaux c JOIN progressions p "
                "ON p.id=c.progression_id WHERE p.referentiel_id=? AND c.date_debut IS NOT NULL "
                "AND c.date_debut<>'' AND c.seq_code IS NOT NULL AND c.seq_code<>'' "
                "GROUP BY c.seq_code", (rid,)).fetchall():
            debuts[c["seq_code"]] = c["debut"]
    parties = []
    if _table(conn, "progression_mer_partie"):
        parties = sorted({x["partie_id"].split("|", 1)[1] for x in conn.execute(
            "SELECT partie_id FROM progression_mer_partie WHERE partie_source='fige' AND "
            "partie_id LIKE ?", (f"{rid}|%",)).fetchall()})
    utilise = conn.execute("SELECT 1 FROM progressions WHERE referentiel_id=? LIMIT 1",
                           (rid,)).fetchone() is not None
    if not utilise and _table(conn, "progression_mer"):
        utilise = conn.execute("SELECT 1 FROM progression_mer WHERE ref_mer_id=? AND "
                               "ref_mer_source='fige' LIMIT 1", (rid,)).fetchone() is not None
    from services.referentiel_principal_externe import nom_calcule
    return {"id": rid, "nom": nom_calcule(r), "empreinte": r.get("publication_empreinte") or "",
            "utilise": bool(utilise or parties),
            "utilise_depuis": min(debuts.values()) if debuts else "",
            "sequences": [{"code": k, "debut": v} for k, v in sorted(debuts.items())],
            "parties_mer": parties}


def construire(conn) -> dict:
    """Document du prochain retour d'usage (sans l'archiver)."""
    migrer(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_niveaux)")}
    refs = []
    if "origine" in cols:
        refs = [_usage_referentiel(conn, dict(r)) for r in conn.execute(
            "SELECT * FROM referentiel_niveaux WHERE origine='publication' ORDER BY id").fetchall()]
    return {"format": FORMAT, "format_version": FORMAT_VERSION,
            "echange": ech.entete(conn, "usage"),
            "cree_le": datetime.now().astimezone().isoformat(timespec="seconds"),
            "referentiels": refs}


def creer(conn, data_dir: Path) -> tuple[str, bytes, dict]:
    """(nom de fichier, contenu, document) d'un nouveau retour, archivé."""
    doc = construire(conn)
    n = doc["echange"]["numero"]
    nom = f"usage_{n:04d}_{datetime.now():%Y-%m-%d_%H%M}.json"
    doc["nom"] = nom
    contenu = json.dumps(doc, ensure_ascii=False, indent=1).encode("utf-8")
    ech.archiver(conn, data_dir, doc["echange"], nom, contenu)
    # v0.51.16 — Empreinte de l'usage envoyé (retour automatique par l'API).
    from services import api_boite
    api_boite.noter_usage_cree(conn, doc)
    return nom, contenu, doc


# ── Côté atelier : import ────────────────────────────────────────────────────

def lire(contenu: bytes) -> dict:
    try:
        doc = json.loads(contenu.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise UsageErreur("Ce fichier n'est pas un retour d'usage (JSON illisible).")
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise UsageErreur("Ce fichier n'est pas un retour d'usage (format inconnu).")
    if str(doc.get("format_version", "")).split(".")[0] != FORMAT_VERSION.split(".")[0]:
        raise UsageErreur(f"Version de retour d'usage {doc.get('format_version')} non prise "
                          "en charge.")
    if not isinstance(doc.get("referentiels"), list):
        raise UsageErreur("Retour d'usage incomplet (liste des référentiels absente).")
    return doc


def _fusionner(conn, r: dict, numero: int, maintenant: str) -> dict:
    """Usage d'un référentiel, réuni aux retours précédents (verrous jamais
    perdus). Renvoie {nouvelles séquences, nouvelles parties}."""
    ancien = conn.execute("SELECT * FROM usage_recu WHERE referentiel_id=?",
                          (r["id"],)).fetchone()
    seqs = json.loads(ancien["sequences"]) if ancien else {}
    parties = set(json.loads(ancien["parties_mer"])) if ancien else set()
    nouvelles = []
    for s in r.get("sequences") or []:
        code, debut = s.get("code"), s.get("debut") or ""
        if not code or not debut:
            continue
        if code not in seqs:
            nouvelles.append(code)
        if code not in seqs or debut < seqs[code]:
            seqs[code] = debut
    np = [p for p in (r.get("parties_mer") or []) if p not in parties]
    parties |= set(r.get("parties_mer") or [])
    utilise = bool(r.get("utilise")) or bool(ancien and ancien["utilise"])
    depuis = [d for d in (r.get("utilise_depuis") or "", ancien["utilise_depuis"] if ancien else "")
              if d]
    conn.execute(
        "INSERT INTO usage_recu (referentiel_id, empreinte, utilise, utilise_depuis, sequences, "
        "parties_mer, numero, recu_le) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(referentiel_id) DO "
        "UPDATE SET empreinte=excluded.empreinte, utilise=excluded.utilise, "
        "utilise_depuis=excluded.utilise_depuis, sequences=excluded.sequences, "
        "parties_mer=excluded.parties_mer, numero=excluded.numero, recu_le=excluded.recu_le",
        (r["id"], r.get("empreinte") or "", int(utilise), min(depuis) if depuis else "",
         json.dumps(seqs, sort_keys=True), json.dumps(sorted(parties)), numero, maintenant))
    if utilise:
        # Comme une progression locale : un interne verrouillé devient utilisé.
        conn.execute("UPDATE referentiel_niveaux SET etat='utilise' WHERE id=? AND "
                     "(etat='verrouille' OR (source='externe' AND etat IN ('en_cours', 'valide')))",
                     (r["id"],))
    return {"sequences": nouvelles, "parties_mer": np}


def analyser(conn, contenu: bytes) -> dict:
    migrer(conn)
    doc = lire(contenu)
    controle = ech.controler(conn, "usage", doc.get("echange"))
    connus = {r["id"] for r in conn.execute("SELECT id FROM referentiel_niveaux").fetchall()}
    return {"echange": controle, "nom": doc.get("nom", ""), "cree_le": doc.get("cree_le", ""),
            "referentiels": [{"id": r.get("id"), "connu": r.get("id") in connus,
                              "utilise": bool(r.get("utilise")),
                              "nb_sequences": len(r.get("sequences") or []),
                              "nb_parties_mer": len(r.get("parties_mer") or [])}
                             for r in doc["referentiels"]]}


def importer(conn, data_dir: Path, contenu: bytes) -> dict:
    """Applique un retour d'usage (numéro attendu seulement)."""
    migrer(conn)
    doc = lire(contenu)
    en_tete = doc.get("echange")
    if not en_tete:
        raise UsageErreur("Retour d'usage sans en-tête d'échange.", "sequence")
    controle = ech.controler(conn, "usage", en_tete)
    if controle["statut"] not in ech.ACCEPTES:
        raise UsageErreur(controle["message"], "sequence", [controle["message"]])
    maintenant = datetime.now().astimezone().isoformat(timespec="seconds")
    from services.referentiel_principal_externe import nom_calcule
    numero = int(en_tete.get("numero") or 0)
    lignes, inconnus = [], []
    for r in doc["referentiels"]:
        ref = conn.execute("SELECT * FROM referentiel_niveaux WHERE id=?",
                           (r.get("id"),)).fetchone()
        if ref is None:
            inconnus.append(r.get("id"))
            continue
        nouveau = _fusionner(conn, r, numero, maintenant)
        lignes.append({"id": r["id"], "nom": nom_calcule(dict(ref)),
                       "utilise": bool(r.get("utilise")),
                       "nouvelles_sequences": nouveau["sequences"],
                       "nouvelles_parties_mer": nouveau["parties_mer"]})
    acquittes = ech.acquitter(conn, data_dir, "paquet", en_tete.get("accuse"))
    ech.enregistrer_reception(conn, "usage", en_tete, doc.get("nom", ""))
    for l in lignes:
        l["synchro"] = etat_synchro(conn, data_dir, l["id"])
    return {"echange": controle, "nom": doc.get("nom", ""), "referentiels": lignes,
            "inconnus": inconnus, "paquets_acquittes": acquittes}


# ── Verrous (lus par l'éditeur de l'atelier) ─────────────────────────────────

def usage(conn, rid: str) -> dict | None:
    if not _table(conn, "usage_recu"):
        return None
    r = conn.execute("SELECT * FROM usage_recu WHERE referentiel_id=?", (rid,)).fetchone()
    if r is None:
        return None
    return {**dict(r), "sequences": json.loads(r["sequences"] or "{}"),
            "parties_mer": json.loads(r["parties_mer"] or "[]")}


def sequence_commencee(conn, rid: str, seq_code: str, aujourd_hui: date) -> bool:
    """Commencée d'après les retours : premier créneau passé (à la date de
    l'atelier) ou partie de MER posée."""
    u = usage(conn, rid)
    if not u:
        return False
    debut = u["sequences"].get(seq_code)
    if debut and debut <= aujourd_hui.isoformat():
        return True
    return any(p.split("|", 1)[0] == seq_code for p in u["parties_mer"])


def utilise(conn, rid: str) -> bool:
    u = usage(conn, rid)
    return bool(u and u["utilise"])


# ── États de synchronisation ─────────────────────────────────────────────────

ETATS_SYNCHRO = {
    "non_publie": "jamais publié",
    "synchronise": "synchronisé",
    "modifie": "modifié depuis la publication",
    "en_attente": "publication en attente",
    "en_retard": "en retard",
    "desynchronise": "désynchronisé",
}


def etat_synchro(conn, data_dir: Path | None, rid: str, empreinte_actuelle: str | None = None,
                 publications: list | None = None) -> dict:
    """État d'un référentiel publié au regard de l'appli en ligne.

    - jamais publié ;
    - **désynchronisé** : l'appli en ligne utilise une version que l'atelier
      n'a jamais publiée ;
    - **en retard** : elle utilise une version publiée plus ancienne, alors
      que le paquet de la dernière version lui est parvenu (acquitté) ;
    - **publication en attente** : la dernière version publiée n'est pas
      encore arrivée (paquet non acquitté, ou aucun retour) ;
    - **modifié depuis la publication** : l'appli en ligne a la dernière
      version publiée, mais le référentiel a changé depuis (à republier) ;
    - **synchronisé** : l'appli en ligne a la dernière version publiée, rien
      n'a changé depuis.
    """
    migrer(conn)
    if publications is None:
        publications = _publications(conn, rid)
    if not publications:
        return {"etat": "non_publie", "libelle": ETATS_SYNCHRO["non_publie"]}
    if empreinte_actuelle is None:
        from services import format_referentiel as fmt
        try:
            empreinte_actuelle = fmt.exporter(conn, rid, data_dir, figer=False)["empreinte"]
        except Exception:
            empreinte_actuelle = ""
    derniere = publications[-1]
    publiees = {p["empreinte"] for p in publications}
    u = usage(conn, rid)
    distant = (u or {}).get("empreinte") or ""
    modifie = bool(empreinte_actuelle) and empreinte_actuelle != derniere["empreinte"]
    if distant and distant not in publiees:
        etat = "desynchronise"
    elif distant == derniere["empreinte"]:
        etat = "modifie" if modifie else "synchronise"
    elif derniere["acquitte"] and distant:
        etat = "en_retard"
    elif derniere["acquitte"] and not distant:
        etat = "en_retard"            # paquet reçu, référentiel non importé (refusé)
    else:
        etat = "en_attente"
    return {"etat": etat, "libelle": ETATS_SYNCHRO[etat], "modifie_depuis": modifie,
            "publie_numero": derniere["numero"], "publie_le": derniere["cree_le"],
            "empreinte_distante": distant, "usage_recu_le": (u or {}).get("recu_le", "")}


def _publications(conn, rid: str) -> list[dict]:
    """Publications de ce référentiel, dans l'ordre, avec leur acquittement."""
    try:
        rows = conn.execute("SELECT * FROM publications ORDER BY cree_le, rowid").fetchall()
    except Exception:
        return []
    acq = {r["numero"]: bool(r["acquitte_le"]) for r in conn.execute(
        "SELECT numero, acquitte_le FROM echanges_envoyes WHERE type='paquet'").fetchall()}
    out = []
    for p in rows:
        for r in json.loads(p["referentiels"] or "[]"):
            if r.get("id") == rid:
                n = p["numero"] if "numero" in p.keys() else 0
                out.append({"numero": n, "cree_le": p["cree_le"], "empreinte": r.get("empreinte"),
                            "acquitte": acq.get(n, False)})
    return out


def journal(conn, limite: int = 20) -> list[dict]:
    """Référentiels connus par les retours (atelier)."""
    migrer(conn)
    return [usage(conn, r["referentiel_id"]) for r in conn.execute(
        "SELECT referentiel_id FROM usage_recu ORDER BY recu_le DESC LIMIT ?",
        (limite,)).fetchall()]
