"""services/depot.py — v0.51.9

Boîte aux lettres : échange **asynchrone** entre l'appli locale (atelier) et
l'appli en ligne (classe), sans exiger qu'elles tournent en même temps.

  - **dossier d'entrée** (par instance ; défaut `data/echanges/entrants/`) :
    l'appli le relève au démarrage, puis périodiquement (5 min par défaut,
    paramétrable) et à la demande ; elle y prend les envois qui lui sont
    destinés (paquets pour la classe, retours d'usage pour l'atelier) ;
  - **dossier de sortie** (facultatif) : chaque envoi créé y est aussi copié
    (par ex. le dossier d'entrée de l'autre appli, ou un dossier
    synchronisé) ;
  - **mode** : « confirmation » (défaut ; la tuile liste les envois en
    attente, « Traiter ») ou « automatique » (appliqués dès la relève, mêmes
    règles qu'à la main) ;
  - **tampon de réception** : les envois sont traités dans l'ordre des
    numéros ; un envoi hors séquence reste dans le dossier (« en attente du
    n° k ») jusqu'à l'arrivée du manquant ; un doublon (déjà reçu) va dans
    `traites/` sans rien appliquer ; un envoi refusé (autre instance,
    illisible, type non attendu ici) va dans `refuses/` avec sa raison.

L'import manuel par fichier reste possible (règle stricte).
"""

from __future__ import annotations

import io
import json
import shutil
import threading
import zipfile
from datetime import datetime
from pathlib import Path

from services import echanges as ech

MODES = ("confirmation", "automatique")
PERIODE_DEFAUT = 5            # minutes
RECOIT = {"atelier": ("usage",), "classe": ("paquet",), "complet": ("paquet", "usage")}

SCHEMA = """
CREATE TABLE IF NOT EXISTS depot_reglages (
    cle    TEXT PRIMARY KEY,
    valeur TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS depot_journal (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    le          TEXT NOT NULL,
    fichier     TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT '',
    numero      INTEGER,
    issue       TEXT NOT NULL,           -- traite | doublon | refuse
    message     TEXT NOT NULL DEFAULT ''
);
"""


class DepotErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides"):
        super().__init__(message)
        self.code = code


def _maintenant() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def migrer(conn) -> None:
    conn.executescript(SCHEMA)


# ── Réglages ─────────────────────────────────────────────────────────────────

def _lire(conn, cle: str, defaut: str = "") -> str:
    migrer(conn)
    r = conn.execute("SELECT valeur FROM depot_reglages WHERE cle=?", (cle,)).fetchone()
    return r["valeur"] if r else defaut


def reglages(conn, data_dir: Path) -> dict:
    entrants = _lire(conn, "entrants")
    try:
        periode = max(1, int(_lire(conn, "periode_min", str(PERIODE_DEFAUT))))
    except ValueError:
        periode = PERIODE_DEFAUT
    mode = _lire(conn, "mode", "confirmation")
    return {"entrants": entrants, "sortants": _lire(conn, "sortants"),
            "mode": mode if mode in MODES else "confirmation", "periode_min": periode,
            "entrants_effectif": str(dossier_entrants(conn, data_dir))}


def definir(conn, data_dir: Path, champs: dict) -> dict:
    migrer(conn)
    if "mode" in champs and champs["mode"] not in MODES:
        raise DepotErreur(f"Mode inconnu : {champs['mode']!r}.")
    if "periode_min" in champs:
        try:
            p = int(champs["periode_min"])
        except (TypeError, ValueError):
            raise DepotErreur("Période invalide (minutes).")
        if not 1 <= p <= 1440:
            raise DepotErreur("La période doit être comprise entre 1 et 1440 minutes.")
        champs = {**champs, "periode_min": str(p)}
    for cle in ("entrants", "sortants"):
        if cle in champs:
            v = (champs[cle] or "").strip()
            if v and not Path(v).is_absolute():
                raise DepotErreur(f"Le dossier {cle} doit être un chemin complet "
                                  "(ex. C:\\Echanges\\atelier).")
            champs = {**champs, cle: v}
    for cle in ("entrants", "sortants", "mode", "periode_min"):
        if cle in champs:
            conn.execute("INSERT INTO depot_reglages (cle, valeur) VALUES (?,?) ON CONFLICT(cle) "
                         "DO UPDATE SET valeur=excluded.valeur", (cle, str(champs[cle])))
    return reglages(conn, data_dir)


def dossier_entrants(conn, data_dir: Path) -> Path:
    v = _lire(conn, "entrants")
    return Path(v) if v else Path(data_dir) / "echanges" / "entrants"


def copier_sortant(conn, nom: str, contenu: bytes) -> str | None:
    """Copie un envoi dans le dossier de sortie, s'il est réglé."""
    try:
        v = _lire(conn, "sortants")
    except Exception:                                   # pragma: no cover
        return None
    if not v:
        return None
    try:
        d = Path(v)
        d.mkdir(parents=True, exist_ok=True)
        (d / nom).write_bytes(contenu)
        return str(d / nom)
    except OSError:
        return None


# ── Lecture d'un envoi déposé ────────────────────────────────────────────────

def _identifier(chemin: Path) -> tuple[str | None, dict | None, str]:
    """(type, en-tête, erreur) d'un fichier déposé."""
    try:
        contenu = chemin.read_bytes()
    except OSError as e:
        return None, None, f"Lecture impossible : {e}"
    if chemin.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(io.BytesIO(contenu)) as z:
                m = json.loads(z.read("paquet.json").decode("utf-8"))
        except (zipfile.BadZipFile, KeyError, ValueError):
            return None, None, "Zip illisible ou sans paquet.json."
        if m.get("format") != "seqenseigne.paquet":
            return None, None, "Ce zip n'est pas un paquet de publication."
        return "paquet", m.get("echange"), ""
    if chemin.suffix.lower() == ".json":
        try:
            d = json.loads(contenu.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None, None, "JSON illisible."
        if not isinstance(d, dict) or d.get("format") != "seqenseigne.usage":
            return None, None, "Ce JSON n'est pas un retour d'usage."
        return "usage", d.get("echange"), ""
    return None, None, "Fichier ignoré (ni .zip ni .json)."


def _fichiers(dossier: Path) -> list[Path]:
    if not dossier.is_dir():
        return []
    return sorted(p for p in dossier.iterdir()
                  if p.is_file() and not p.name.startswith((".", "~"))
                  and not p.name.endswith((".raison.txt", ".tmp", ".part")))


def lister(conn, data_dir: Path, profil: str) -> list[dict]:
    """Envois présents dans le dossier d'entrée, avec leur situation (sans
    rien écrire)."""
    ech.migrer(conn)
    out = []
    for p in _fichiers(dossier_entrants(conn, data_dir)):
        type_, en_tete, err = _identifier(p)
        item = {"fichier": p.name, "type": type_, "numero": (en_tete or {}).get("numero")}
        if err:
            item.update(statut="illisible", message=err)
        elif type_ not in RECOIT.get(profil, ()):
            item.update(statut="non_attendu",
                        message=f"Envoi « {type_} » : il ne se traite pas dans cette appli.")
        else:
            c = ech.controler(conn, type_, en_tete)
            item.update(statut=c["statut"], message=c["message"],
                        manquants=c.get("manquants", []))
        out.append(item)
    out.sort(key=lambda x: (x["type"] or "", x["numero"] or 0, x["fichier"]))
    return out


# ── Traitement ───────────────────────────────────────────────────────────────

def _ranger(dossier: Path, chemin: Path, sous: str, raison: str = "") -> None:
    cible = dossier / sous
    cible.mkdir(parents=True, exist_ok=True)
    dest = cible / chemin.name
    if dest.exists():
        dest = cible / f"{chemin.stem}_{datetime.now():%Y%m%d%H%M%S}{chemin.suffix}"
    shutil.move(str(chemin), str(dest))
    if raison:
        (cible / (dest.name + ".raison.txt")).write_text(raison, encoding="utf-8")


def _appliquer(store, data_dir: Path, type_: str, contenu: bytes) -> str:
    """Applique un envoi ; renvoie un résumé lisible."""
    if type_ == "paquet":
        from services import import_publication as imp
        a = imp.importer(store._conn, data_dir, contenu)
        n = sum(1 for r in a["referentiels"] if r.get("importe"))
        ref = sum(1 for r in a["referentiels"] if r["statut"] == "refuse")
        return (f"{n} référentiel(s) importé(s)" + (f", {ref} refusé(s)" if ref else "")
                + f" sur {len(a['referentiels'])}")
    from services import retour_usage as ru
    with store._conn() as conn:
        r = ru.importer(conn, data_dir, contenu)
    acq = r.get("paquets_acquittes") or []
    return (f"{len(r['referentiels'])} référentiel(s) mis à jour"
            + (f", paquet(s) n° {', '.join(map(str, acq))} acquitté(s)" if acq else ""))


def _journal(store, fichier, type_, numero, issue, message):
    with store._conn() as conn:
        migrer(conn)
        conn.execute("INSERT INTO depot_journal (le, fichier, type, numero, issue, message) "
                     "VALUES (?,?,?,?,?,?)", (_maintenant(), fichier, type_ or "", numero,
                                              issue, message))


_VERROU = threading.Lock()


def relever(store, profil: str, appliquer: bool | None = None) -> dict:
    """Relève le dossier d'entrée. `appliquer` : None = selon le mode réglé ;
    True = traiter ; False = lister seulement. Les envois attendus sont
    traités dans l'ordre (un envoi traité peut rendre le suivant attendu)."""
    data_dir = store.data_dir
    with _VERROU:
        with store._conn() as conn:
            r = reglages(conn, data_dir)
            dossier = dossier_entrants(conn, data_dir)
        if appliquer is None:
            appliquer = r["mode"] == "automatique"
        dossier.mkdir(parents=True, exist_ok=True)
        rapport = {"releve_le": _maintenant(), "dossier": str(dossier), "mode": r["mode"],
                   "applique": bool(appliquer), "traites": [], "doublons": [], "refuses": [],
                   "en_attente": []}
        if appliquer:
            progres = True
            while progres:
                progres = False
                with store._conn() as conn:
                    items = lister(conn, data_dir, profil)
                for it in items:
                    p = dossier / it["fichier"]
                    if it["statut"] in ("illisible", "non_attendu", "autre_instance",
                                        "refuse_sans_numero"):
                        _ranger(dossier, p, "refuses", it["message"])
                        _journal(store, it["fichier"], it["type"], it["numero"], "refuse",
                                 it["message"])
                        rapport["refuses"].append({**it})
                    elif it["statut"] == "deja_recu":
                        _ranger(dossier, p, "traites")
                        _journal(store, it["fichier"], it["type"], it["numero"], "doublon",
                                 it["message"])
                        rapport["doublons"].append({**it})
                    elif it["statut"] in ech.ACCEPTES:
                        try:
                            resume = _appliquer(store, data_dir, it["type"], p.read_bytes())
                        except Exception as e:      # contenu refusé (paquet invalide…)
                            msg = str(e) or e.__class__.__name__
                            _ranger(dossier, p, "refuses", msg)
                            _journal(store, it["fichier"], it["type"], it["numero"], "refuse", msg)
                            rapport["refuses"].append({**it, "message": msg})
                        else:
                            _ranger(dossier, p, "traites")
                            _journal(store, it["fichier"], it["type"], it["numero"], "traite",
                                     resume)
                            rapport["traites"].append({**it, "message": resume})
                        progres = True
                        break               # relire : le suivant est peut-être attendu
        with store._conn() as conn:
            rapport["en_attente"] = lister(conn, data_dir, profil)
            conn.execute("INSERT INTO depot_reglages (cle, valeur) VALUES ('derniere_releve', ?) "
                         "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
                         (json.dumps({k: rapport[k] for k in ("releve_le", "applique")}
                                     | {"nb_traites": len(rapport["traites"]),
                                        "nb_refuses": len(rapport["refuses"])}),))
        return rapport


def etat(store, profil: str) -> dict:
    with store._conn() as conn:
        r = reglages(conn, store.data_dir)
        d = _lire(conn, "derniere_releve")
        journal = [dict(x) for x in conn.execute(
            "SELECT * FROM depot_journal ORDER BY id DESC LIMIT 15").fetchall()]
        attente = lister(conn, store.data_dir, profil)
    return {"reglages": r, "derniere_releve": json.loads(d) if d else None,
            "en_attente": attente, "journal": journal}


# ── Relève au démarrage, puis périodique ─────────────────────────────────────

def demarrer(app) -> threading.Thread | None:
    """Relève au démarrage puis toutes les `periode_min` minutes (lancement
    réel seulement, pas en test). En mode confirmation, la relève ne fait
    que lister : rien n'est appliqué sans « Traiter »."""
    store = app.json_store
    profil = app.config.get("SEQ_PROFIL", "complet")
    arret = threading.Event()

    def boucle():
        while not arret.is_set():
            try:
                rapport = relever(store, profil)
                n = len(rapport["traites"])
                attente = [x for x in rapport["en_attente"]]
                if n or attente:
                    print(f"  [boîte aux lettres] {n} envoi(s) traité(s), "
                          f"{len(attente)} en attente")
            except Exception as e:                      # pragma: no cover
                print(f"  [boîte aux lettres] relève impossible : {e}")
            try:
                with store._conn() as conn:
                    periode = reglages(conn, store.data_dir)["periode_min"]
            except Exception:                           # pragma: no cover
                periode = PERIODE_DEFAUT
            arret.wait(periode * 60)

    t = threading.Thread(target=boucle, name="releve-depot", daemon=True)
    t.arret = arret
    t.start()
    return t
