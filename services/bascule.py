"""services/bascule.py — v0.51.12

Bascule de la base partagée (`data\\`, profil complet) vers deux bases
séparées, une par appli :

  - `data_atelier\\` : conception (atomes, référentiels, LaTeX) — profil atelier ;
  - `data_classe\\`  : planification et suivi — profil classe.

Principes (répartition validée table par table, voir services/repartition.py) :

  - **non destructive** : `data\\` n'est jamais modifié (il reste la
    sauvegarde d'avant la bascule) ; tout se fait sur des copies ; en cas
    d'échec, les deux dossiers créés sont retirés ;
  - **par le protocole d'échange** : les référentiels publiables (internes
    verrouillés, externes non annulés) partent de l'atelier dans un paquet de
    publication (n° suivant de l'atelier), importé par la classe — titres des
    notions et méthodes, noms et PDF des documents compris ; la classe renvoie
    aussitôt son retour d'usage n° 1, importé par l'atelier (séquences
    commencées, verrous) ;
  - **identités** : l'atelier garde l'identité de la base partagée (ses
    publications continuent leur numérotation) ; la classe reçoit une
    nouvelle identité ; chaque base est marquée de son rôle
    (`instance_locale.role`), ce qui retire au démarrage les tables de
    l'autre côté ;
  - **référentiels non publiables** (interne non verrouillé, externe annulé)
    utilisés par une progression : gardés côté classe (structure seule, sans
    documents) et signalés ; non utilisés : atelier seulement ;
  - **boîtes aux lettres croisées** : le dossier de sortie de chaque appli est
    le dossier d'entrée de l'autre (à changer à la mise en ligne).
"""

from __future__ import annotations

import json
import shutil
import socket
import sqlite3
from datetime import datetime
from pathlib import Path

from services import repartition as rep

NOM_DB = "seqenseigne.db"
DOSSIERS = {"atelier": "data_atelier", "classe": "data_classe"}
# Sous-dossiers de data\ copiés côté atelier (tout sauf les caches, les
# sauvegardes de la base et les fichiers en attente de la boîte aux lettres).
_IGNORES_ATELIER = {"cache_rendus", "backups"}
# Côté classe : seulement les fichiers de premier niveau (CSV, YAML des cases
# du suivi, configuration) ; les documents arrivent par le paquet.


class BasculeErreur(Exception):
    def __init__(self, message: str, code: str = "bascule_refusee", details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _maintenant() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _taille(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else 0


# ── Dossier de données par défaut d'un profil ────────────────────────────────

def role_du_dossier(dossier: Path) -> str:
    """Rôle de la base du dossier ('' si absente ou non basculée)."""
    db = Path(dossier) / NOM_DB
    if not db.is_file():
        return ""
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            return rep.role(conn)
        finally:
            conn.close()
    except sqlite3.Error:
        return ""


def dossier_par_defaut(racine: Path, profil: str) -> Path:
    """`data_atelier\\` (resp. `data_classe\\`) pour le profil atelier (resp.
    classe) une fois la bascule faite ; `data\\` sinon (et en profil complet)."""
    racine = Path(racine)
    if profil in DOSSIERS:
        d = racine / DOSSIERS[profil]
        if role_du_dossier(d) == profil:
            return d
    return racine / "data"


def verifier_profil(conn, profil: str) -> None:
    """Refuse d'ouvrir une base basculée avec un autre profil que le sien."""
    r = rep.role(conn)
    if r and profil != r:
        raise BasculeErreur(
            f"Cette base est celle de l'appli « {r} » : lancez-la avec le profil {r} "
            f"(lancer.bat {r}).", "profil")


# ── Référentiels ─────────────────────────────────────────────────────────────

def _utilise(conn, rid: str) -> bool:
    if rep.table_existe(conn, "progressions") and conn.execute(
            "SELECT 1 FROM progressions WHERE referentiel_id=? LIMIT 1", (rid,)).fetchone():
        return True
    return rep.table_existe(conn, "progression_mer") and conn.execute(
        "SELECT 1 FROM progression_mer WHERE ref_mer_id=? AND ref_mer_source='fige' LIMIT 1",
        (rid,)).fetchone() is not None


def _controle(conn, data_dir: Path, r: dict) -> dict:
    """Ce que la bascule fera de ce référentiel (sans rien écrire)."""
    from services import format_referentiel as fmt
    from services import paquet_publication as pp
    from services.referentiel_principal_externe import nom_calcule
    rid = r["id"]
    res = {"id": rid, "nom": nom_calcule(r), "niveau": r["niveau"],
           "type": r.get("type_ref") or "principal", "source": r.get("source") or "interne",
           "etat": r.get("etat") or "", "publiable": pp._publiable(r), "erreurs": [],
           "sans_pdf": [], "utilise": _utilise(conn, rid), "devenir": ""}
    if res["publiable"]:
        omis: list = []
        try:
            doc = fmt.exporter(conn, rid, data_dir, figer=False, omis=omis)
            res["erreurs"] = list(fmt.valider(doc))
            res["sans_pdf"] = fmt.bilan(doc, omis)["documents_sans_pdf"]
            for d in pp._documents(doc):
                f = d.get("fichier") or {}
                chemin = pp._chemin_document(conn, data_dir, rid, d)
                if not f.get("sha256") or chemin is None or not chemin.is_file():
                    res["erreurs"].append(f"fichier introuvable — {d['libelle']}")
                elif fmt.sha256_fichier(chemin) != f["sha256"]:
                    res["erreurs"].append(f"fichier modifié — {d['libelle']}")
        except fmt.FormatErreur as e:
            res["erreurs"].append(str(e))
    if res["publiable"] and not res["erreurs"]:
        res["devenir"] = "publie"
    elif res["utilise"]:
        res["devenir"] = "garde"
    else:
        res["devenir"] = "atelier"
    return res


def _referentiels(conn, data_dir: Path) -> list[dict]:
    return [_controle(conn, data_dir, dict(r)) for r in conn.execute(
        "SELECT * FROM referentiel_niveaux ORDER BY niveau, COALESCE(annee, ''), version")]


# ── Aperçu ───────────────────────────────────────────────────────────────────

def _comptes(conn) -> dict:
    existantes = rep.tables(conn)
    out = {}
    for cote, noms in (("classe", rep.TABLES_CLASSE), ("atelier", rep.TABLES_ATELIER),
                       ("deux", rep.TABLES_DEUX)):
        out[cote] = {t: n for t in noms if t in existantes
                     for n in [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]] if n}
    connues = set(rep.TABLES_CLASSE) | set(rep.TABLES_ATELIER) | set(rep.TABLES_DEUX)
    out["inconnues"] = sorted(existantes - connues)
    return out


def _cibles(data_dir: Path) -> dict:
    racine = Path(data_dir).parent
    out = {}
    for role, nom in DOSSIERS.items():
        d = racine / nom
        out[role] = {"dossier": str(d), "existe": d.exists(), "role": role_du_dossier(d)}
    return out


def apercu(store) -> dict:
    """Ce que fera la bascule, sans rien écrire."""
    data_dir = Path(store.data_dir)
    refus, avert = [], []
    with store._conn() as conn:
        role = rep.role(conn)
        if role:
            refus.append(f"Cette base est déjà celle de l'appli « {role} » : la bascule se "
                         "fait depuis la base partagée (data\\, profil complet).")
        cibles = _cibles(data_dir)
        for r, c in cibles.items():
            if c["role"]:
                refus.append(f"La bascule est déjà faite : {c['dossier']} contient la base "
                             f"de l'appli « {c['role']} ».")
            elif c["existe"]:
                avert.append(f"Le dossier {Path(c['dossier']).name} existe déjà (base "
                             "d'essai) : il sera renommé, pas supprimé.")
        comptes = _comptes(conn)
        refs = _referentiels(conn, data_dir)
    for r in refs:
        if r["devenir"] == "garde":
            pourquoi = ("non verrouillé" if r["source"] == "interne" and not r["publiable"]
                        else "annulé" if not r["publiable"] else
                        "non publiable : " + "; ".join(r["erreurs"][:3]))
            avert.append(f"{r['nom']} ({pourquoi}) est utilisé par une progression : "
                         "côté classe, il garde sa structure mais aucun document ne sera "
                         "proposé tant qu'il n'est pas publié depuis l'atelier.")
        elif r["publiable"] and r["erreurs"]:
            avert.append(f"{r['nom']} n'est pas publiable en l'état "
                         f"({'; '.join(r['erreurs'][:3])}) : il restera dans l'atelier.")
        if r["devenir"] == "publie" and r["sans_pdf"]:
            avert.append(f"{r['nom']} : {len(r['sans_pdf'])} document(s) sans PDF compilé, "
                         "non transmis à l'appli de classe.")
    tailles = {"base": _taille(data_dir / NOM_DB),
               "atelier": sum(_taille(p) for p in data_dir.iterdir()
                              if p.name not in _IGNORES_ATELIER and p.name != NOM_DB)
               if data_dir.is_dir() else 0}
    return {"possible": not refus, "refus": refus, "avertissements": avert,
            "cibles": cibles, "tables": comptes, "referentiels": refs, "tailles": tailles,
            "nb_publies": sum(r["devenir"] == "publie" for r in refs)}


# ── Exécution ────────────────────────────────────────────────────────────────

def _copier_base(source: Path, cible: Path) -> None:
    cible.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(source)
    dst = sqlite3.connect(cible)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _ignorer_atelier(racine: Path):
    def ignorer(dossier, noms):
        d = Path(dossier)
        if d == racine:
            return [n for n in noms if n in _IGNORES_ATELIER or n.startswith(NOM_DB)]
        if d == racine / "echanges":
            return [n for n in noms if n != "envoyes"]       # pas de fichiers en attente
        return []
    return ignorer


def _reglage(conn, cle: str, valeur: str) -> None:
    from services import depot
    depot.migrer(conn)
    conn.execute("INSERT INTO depot_reglages (cle, valeur) VALUES (?,?) ON CONFLICT(cle) "
                 "DO UPDATE SET valeur=excluded.valeur", (cle, valeur))


def _vider_si(conn, *noms) -> None:
    from services import depot
    ech_migrer(conn)
    depot.migrer(conn)
    for t in noms:
        if rep.table_existe(conn, t):
            conn.execute(f"DELETE FROM {t}")


def ech_migrer(conn) -> None:
    from services import echanges as ech
    ech.migrer(conn)


def _nom_instance(role: str) -> str:
    try:
        hote = socket.gethostname()
    except OSError:                                          # pragma: no cover
        hote = ""
    return f"seqenseigne {role}" + (f" — {hote}" if hote else "")


def _tables_avec(conn, colonne: str) -> list[str]:
    return [t for t in sorted(rep.tables(conn))
            if colonne in {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}]


def _retirer_referentiels(conn, data_dir: Path, rids: list[str]) -> None:
    if not rids:
        return
    marque = ",".join("?" * len(rids))
    conn.execute("PRAGMA defer_foreign_keys = ON")
    for t in _tables_avec(conn, "referentiel_id"):
        conn.execute(f"DELETE FROM {t} WHERE referentiel_id IN ({marque})", rids)
    conn.execute(f"DELETE FROM referentiel_niveaux WHERE id IN ({marque})", rids)
    for rid in rids:
        shutil.rmtree(Path(data_dir) / "referentiels_fichiers" / rid, ignore_errors=True)


def _finir(store_cls, dossier: Path, role: str, avant: set) -> dict:
    """Vide puis retire les tables de l'autre côté (`avant` : tables de la
    base partagée), préférences comprises."""
    # v0.51.13 — Connexion directe : rouvrir la base par le store relancerait
    # l'élagage du démarrage avant le vidage (faux message « gardées »).
    conn = sqlite3.connect(dossier / NOM_DB)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        faits = rep.vider(conn, rep.tables_de(rep.autre(role)))
        elague = rep.elaguer(conn, role)
        restantes = rep.tables(conn)
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()
    autres = set(rep.tables_de(rep.autre(role)))
    return {"lignes_retirees": sum(faits.values()),
            "tables_retirees": sorted((avant & autres) - restantes),
            "tables_gardees": elague["gardees"]}


def executer(store, maintenant: datetime | None = None) -> dict:
    """Fait la bascule. Renvoie le rapport (aussi écrit dans BASCULE.json des
    deux dossiers). Lève BasculeErreur si elle est refusée ou échoue."""
    from persistence.sqlite_store import SqliteStore
    from services import echanges as ech
    from services import import_publication as imp
    from services import paquet_publication as pp
    from services import retour_usage as ru

    ap = apercu(store)
    if not ap["possible"]:
        raise BasculeErreur(" ".join(ap["refus"]), "bascule_refusee", ap)
    maintenant = maintenant or datetime.now().astimezone()
    source = Path(store.data_dir)
    racine = source.parent
    A, C = racine / DOSSIERS["atelier"], racine / DOSSIERS["classe"]
    renommes = {}
    for d in (A, C):
        if d.exists():
            ancien = d.with_name(f"{d.name}_essai_{maintenant:%Y%m%d_%H%M%S}")
            d.rename(ancien)
            renommes[d.name] = ancien.name
    rapport = {"faite_le": maintenant.isoformat(timespec="seconds"), "source": str(source),
               "dossiers": {"atelier": str(A), "classe": str(C)}, "renommes": renommes,
               "referentiels": ap["referentiels"], "avertissements": ap["avertissements"]}
    try:
        # 1. Copies (data\ n'est jamais modifié).
        shutil.copytree(source, A, ignore=_ignorer_atelier(source))
        _copier_base(source / NOM_DB, A / NOM_DB)
        C.mkdir()
        for f in source.iterdir():
            if f.is_file() and not f.name.startswith(NOM_DB) and f.suffix.lower() in (
                    ".csv", ".yaml", ".yml", ".json"):
                shutil.copy2(f, C / f.name)
        _copier_base(source / NOM_DB, C / NOM_DB)

        # 2. Atelier : rôle, échanges remis à zéro côté réception, paquet.
        sa = SqliteStore(A)
        a_publier = [r["id"] for r in ap["referentiels"] if r["devenir"] == "publie"]
        with sa._conn() as conn:
            rep.definir_role(conn, "atelier")
            conn.execute("UPDATE instance_locale SET nom=?", (_nom_instance("atelier"),))
            _vider_si(conn, "correspondants", "echanges_recus", "depot_journal")
            conn.execute("DELETE FROM echanges_envoyes WHERE type='usage'")
            for cle in ("entrants", "sortants", "derniere_releve"):
                _reglage(conn, cle, "")
            id_atelier = ech.instance(conn)["id"]
            paquet = None
            if a_publier:
                try:
                    contenu, manifeste = pp.creer(conn, A, a_publier, "atelier", maintenant)
                except pp.PaquetErreur as e:
                    raise BasculeErreur(f"Paquet de publication impossible : {e}",
                                        "paquet", {"rapport": e.rapport})
                paquet = {"nom": manifeste["nom"], "numero": manifeste["echange"]["numero"],
                          "contenu": contenu}

        # 3. Classe : nouvelle identité, référentiels, import du paquet.
        sc = SqliteStore(C)
        gardes = [r["id"] for r in ap["referentiels"] if r["devenir"] in ("publie", "garde")]
        with sc._conn() as conn:
            rep.vider(conn, rep.TABLES_ATELIER)      # conception : rien côté classe
            _vider_si(conn, "instance_locale")
            rep.definir_role(conn, "classe")
            conn.execute("UPDATE instance_locale SET nom=?", (_nom_instance("classe"),))
            _vider_si(conn, "correspondants", "echanges_envoyes", "echanges_recus",
                      "depot_journal")
            for cle in ("entrants", "sortants", "derniere_releve"):
                _reglage(conn, cle, "")
            tous = [r["id"] for r in conn.execute("SELECT id FROM referentiel_niveaux")]
            _retirer_referentiels(conn, C, [x for x in tous if x not in gardes])
            if gardes:
                conn.execute("UPDATE referentiel_niveaux SET origine='publication', "
                             "publication_empreinte='' WHERE id IN (%s)"
                             % ",".join("?" * len(gardes)), gardes)
            if paquet and paquet["numero"] > 1:
                # Repère : la classe attend le paquet de la bascule.
                conn.execute("INSERT INTO echanges_recus (type, numero, emetteur, nom_fichier, "
                             "recu_le) VALUES ('paquet', ?, ?, 'repère de la bascule', ?)",
                             (paquet["numero"] - 1, id_atelier, _maintenant()))
        import_ = None
        if paquet:
            res = imp.importer(sc._conn, C, paquet["contenu"])
            refuses = [x for x in res["referentiels"] if not x.get("importe")]
            if refuses:
                raise BasculeErreur(
                    "Import du paquet refusé côté classe : " + "; ".join(
                        f"{x['nom']} — {' '.join(x['raisons']) or x['statut']}"
                        for x in refuses), "import", res)
            import_ = {"nom": paquet["nom"], "numero": paquet["numero"],
                       "referentiels": [{"id": x["id"], "nom": x["nom"], "statut": x["statut"]}
                                        for x in res["referentiels"]]}
        with sc._conn() as conn:
            nom_usage, contenu_usage, _doc = ru.creer(conn, C)

        # 4. Atelier : retour d'usage n° 1 (séquences commencées, verrous).
        with sa._conn() as conn:
            usage = ru.importer(conn, A, contenu_usage)

        # 5. Boîtes aux lettres croisées.
        with sa._conn() as conn:
            _reglage(conn, "sortants", str(C / "echanges" / "entrants"))
        with sc._conn() as conn:
            _reglage(conn, "sortants", str(A / "echanges" / "entrants"))
        for d in (A, C):
            (d / "echanges" / "entrants").mkdir(parents=True, exist_ok=True)

        # 6. Tables de l'autre côté : vidées puis retirées.
        with store._conn() as conn:
            avant = rep.tables(conn)
        rapport["atelier"] = _finir(SqliteStore, A, "atelier", avant)
        rapport["classe"] = _finir(SqliteStore, C, "classe", avant)
        rapport["paquet"] = import_
        rapport["usage"] = {"nom": nom_usage,
                            "referentiels": [{"id": x["id"], "nom": x["nom"],
                                              "utilise": x["utilise"]}
                                             for x in usage["referentiels"]],
                            "paquets_acquittes": usage["paquets_acquittes"]}
        rapport["tailles"] = {"atelier": _taille(A), "classe": _taille(C)}
    except Exception as e:
        for d in (A, C):
            shutil.rmtree(d, ignore_errors=True)
        for nom, ancien in renommes.items():
            (racine / ancien).rename(racine / nom)
        if isinstance(e, BasculeErreur):
            raise
        raise BasculeErreur(f"La bascule a échoué (rien n'a changé dans data\\) : {e}",
                            "echec") from e
    texte = json.dumps(rapport, ensure_ascii=False, indent=1)
    for d in (A, C):
        (d / "BASCULE.json").write_text(texte, encoding="utf-8")
    return rapport
