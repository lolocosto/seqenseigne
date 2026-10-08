"""services/synthese_seance.py — v0.47.1

Synthèse d'une séance à copier dans le cahier de textes de Pronote
(Suivi › Travail › « Synthèse Pronote »).

Deux zones, en texte brut :
  1. **Contenu de la séance**, une information par ligne :
     - mise en route : « Mise en route : <partie de la progression de MER>
       (r/N) » | « Mise en route : automatismes (enveloppe(s) …) » |
       « Pas de mise en route » (classe à MER sans mise en route à cette
       séance, dont « non faite ») ; rien si la classe n'a pas de MER ;
     - séquence principale : « <code> <nom> — <partie> (n/N) » ;
     - « Cours : notions (…) et méthodes (…) » : choix parmi les notions et
       méthodes rattachées aux objectifs de la partie du créneau ;
     - activités cochées, dans l'ordre choisi (Évaluation, Révisions,
       Exercices, Correction… — liste extensible dans Paramétrage) ;
     - texte libre (référentiel externe, ou complément) ;
     - « Documents distribués : … ».
  2. **Travail à faire** : « Pour le jj/mm : <libellé> » (+ « (à rendre) »).

Les choix (notions, méthodes, activités, texte libre) sont enregistrés pour la
séance (`seance_contenu`) : en rouvrant l'écran on les retrouve, et les
notions / méthodes déjà faites aux séances précédentes du même créneau ne
sont plus proposées d'emblée.
"""

from __future__ import annotations
import json
import uuid
from datetime import date

ACTIVITES_DEFAUT = ("Évaluation", "Révisions", "Exercices", "Correction")

SCHEMA = """
CREATE TABLE IF NOT EXISTS seance_contenu (
    classe_id    TEXT NOT NULL,
    date         TEXT NOT NULL,
    creneau_code TEXT NOT NULL,
    notions      TEXT NOT NULL DEFAULT '[]',
    methodes     TEXT NOT NULL DEFAULT '[]',
    activites    TEXT NOT NULL DEFAULT '[]',
    texte_libre  TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (classe_id, date, creneau_code)
);
CREATE TABLE IF NOT EXISTS activites_seance (
    id      TEXT PRIMARY KEY,
    libelle TEXT NOT NULL,
    ordre   INTEGER NOT NULL DEFAULT 0,
    actif   INTEGER NOT NULL DEFAULT 1
);
"""


class SyntheseErreur(Exception):
    def __init__(self, message: str, code: str = "donnees_invalides"):
        super().__init__(message)
        self.code = code


def migrer(conn) -> None:
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM activites_seance").fetchone()[0] == 0:
        for i, lib in enumerate(ACTIVITES_DEFAUT, start=1):
            conn.execute("INSERT INTO activites_seance (id, libelle, ordre) VALUES (?,?,?)",
                         ("ac_" + uuid.uuid4().hex[:12], lib, i * 10))


# ── Activités (paramétrage) ──────────────────────────────────────────────────

def lister_activites(conn, tout: bool = False) -> list[dict]:
    q = "SELECT * FROM activites_seance" + ("" if tout else " WHERE actif=1") + \
        " ORDER BY ordre, libelle"
    return [{**dict(r), "actif": bool(r["actif"])} for r in conn.execute(q).fetchall()]


def ajouter_activite(conn, libelle: str) -> dict:
    lib = (libelle or "").strip()
    if not lib:
        raise SyntheseErreur("Libellé obligatoire.")
    if any(a["libelle"].casefold() == lib.casefold() for a in lister_activites(conn, True)):
        raise SyntheseErreur(f"L'activité « {lib} » existe déjà.")
    n = conn.execute("SELECT COALESCE(MAX(ordre), 0) FROM activites_seance").fetchone()[0]
    aid = "ac_" + uuid.uuid4().hex[:12]
    conn.execute("INSERT INTO activites_seance (id, libelle, ordre) VALUES (?,?,?)",
                 (aid, lib, n + 10))
    return dict(conn.execute("SELECT * FROM activites_seance WHERE id=?", (aid,)).fetchone())


def modifier_activite(conn, aid: str, champs: dict) -> None:
    r = conn.execute("SELECT * FROM activites_seance WHERE id=?", (aid,)).fetchone()
    if r is None:
        raise SyntheseErreur("Activité introuvable.", "introuvable")
    lib = (champs.get("libelle", r["libelle"]) or "").strip()
    if not lib:
        raise SyntheseErreur("Libellé obligatoire.")
    actif = 1 if champs.get("actif", bool(r["actif"])) else 0
    conn.execute("UPDATE activites_seance SET libelle=?, actif=? WHERE id=?", (lib, actif, aid))


# ── Notions et méthodes de la partie ─────────────────────────────────────────

def _texte(s: str) -> str:
    """Titre LaTeX → texte lisible. v0.51.1 : conversion commune avec le
    format d'échange des référentiels (services/texte_latex.py)."""
    from services.texte_latex import vers_texte
    return vers_texte(s)


def candidats(conn, niveau: str, seq_code: str, partie_debut: int, partie_fin: int) -> dict:
    """{notions: [{id, titre}], methodes: [{id, titre}]} rattachées aux
    objectifs des parties [partie_debut, partie_fin] de la séquence."""
    rows = conn.execute(
        "SELECT o.id, o.methode_id FROM objectifs o "
        "JOIN sequence_parties p ON p.id=o.partie_id "
        "JOIN sequences_par_niveau s ON s.id=p.sequence_par_niveau_id "
        "WHERE s.niveau=? AND s.sequence_code=? AND p.numero BETWEEN ? AND ? "
        "ORDER BY p.numero, o.code", (niveau, seq_code, partie_debut, partie_fin)).fetchall()
    notions, methodes, vus_n, vus_m = [], [], set(), set()
    for r in rows:
        for n in conn.execute(
                "SELECT n.id, n.titre FROM objectif_notions x JOIN notions n ON n.id=x.notion_id "
                "WHERE x.objectif_id=? ORDER BY x.ordre", (r["id"],)).fetchall():
            if n["id"] not in vus_n:
                vus_n.add(n["id"])
                notions.append({"id": n["id"], "titre": _texte(n["titre"]) or n["id"]})
        if r["methode_id"] and r["methode_id"] not in vus_m:
            m = conn.execute("SELECT id, titre FROM methodes WHERE id=?",
                             (r["methode_id"],)).fetchone()
            if m:
                vus_m.add(m["id"])
                methodes.append({"id": m["id"], "titre": _texte(m["titre"]) or m["id"]})
    return {"notions": notions, "methodes": methodes}


# ── Contenu enregistré d'une séance ──────────────────────────────────────────

def lire_contenu(conn, classe_id: str, date_iso: str, creneau: str) -> dict:
    r = conn.execute("SELECT * FROM seance_contenu WHERE classe_id=? AND date=? AND "
                     "creneau_code=?", (classe_id, date_iso, creneau)).fetchone()
    if r is None:
        return {"notions": [], "methodes": [], "activites": [], "texte_libre": ""}
    return {"notions": json.loads(r["notions"]), "methodes": json.loads(r["methodes"]),
            "activites": json.loads(r["activites"]), "texte_libre": r["texte_libre"]}


def enregistrer_contenu(conn, classe_id: str, date_iso: str, creneau: str,
                        champs: dict) -> dict:
    c = lire_contenu(conn, classe_id, date_iso, creneau)
    for k in ("notions", "methodes", "activites"):
        if k in champs:
            if not isinstance(champs[k], list):
                raise SyntheseErreur(f"`{k}` doit être une liste.")
            c[k] = [str(x) for x in champs[k]]
    if "texte_libre" in champs:
        c["texte_libre"] = str(champs["texte_libre"] or "")
    conn.execute(
        "INSERT INTO seance_contenu (classe_id, date, creneau_code, notions, methodes, "
        "activites, texte_libre) VALUES (?,?,?,?,?,?,?) ON CONFLICT(classe_id, date, "
        "creneau_code) DO UPDATE SET notions=excluded.notions, methodes=excluded.methodes, "
        "activites=excluded.activites, texte_libre=excluded.texte_libre",
        (classe_id, date_iso, creneau, json.dumps(c["notions"]), json.dumps(c["methodes"]),
         json.dumps(c["activites"]), c["texte_libre"]))
    return c


def deja_faits(conn, classe_id: str, date_iso: str, creneau: str,
               debut: str, fin: str) -> dict:
    """Notions / méthodes cochées aux séances PRÉCÉDENTES du même créneau de
    progression (dates [debut, séance[) pour la classe."""
    n, m = set(), set()
    for r in conn.execute(
            "SELECT * FROM seance_contenu WHERE classe_id=? AND date>=? AND date<=? "
            "AND (date<? OR (date=? AND creneau_code<?))",
            (classe_id, debut or "0000", fin or "9999", date_iso, date_iso, creneau)).fetchall():
        n.update(json.loads(r["notions"]))
        m.update(json.loads(r["methodes"]))
    return {"notions": sorted(n), "methodes": sorted(m)}


# ── Mise en route : partie de la progression de MER ──────────────────────────

def _partie_mer(conn, store, annee: str, classe_id: str, date_iso: str,
                creneau: str) -> dict | None:
    from services import contexte_projection as ctx
    from services import affectation as aff_svc
    from services import progression_mer as pm
    row = conn.execute("SELECT niveau, mer_mode FROM classes WHERE id=?", (classe_id,)).fetchone()
    infos = ctx.infos_classe(conn, classe_id)
    if row is None or infos is None:
        return None
    prog = pm.lire_par_niveau(conn, row["niveau"], annee)     # sans la créer
    if not prog:
        return None
    cal = ctx.calendrier(store, annee, infos["academie"])
    seances = ctx.projeter_classe(conn, annee, classe_id, infos["etablissement_id"], cal)
    rep = aff_svc.repartir_mer(seances, row["mer_mode"] or "automatismes",
                               aff_svc.lire_affectations(conn, classe_id, annee),
                               aff_svc.dates_exceptions(conn, classe_id, annee))
    prog_s = rep["progression"]
    for i, s in enumerate(prog_s, start=1):
        s["numero"] = i
    for s in pm.projeter_mer(prog_s, prog.get("parties", [])):
        if s["date"] == date_iso and s["creneau_code"] == creneau and s.get("mer_partie_id"):
            return {"libelle": s.get("mer_libelle") or s.get("mer_sequence") or "",
                    "rang": s["mer_rang_partie"], "nb": s.get("mer_nb_partie") or 0}
    return None


# ── Synthèse ─────────────────────────────────────────────────────────────────

def _date_fr(iso: str) -> str:
    a, m, j = iso.split("-")
    return f"{j}/{m}"


def _liste(xs: list[str]) -> str:
    return ", ".join(xs)


def lire(conn, store, annee: str, classe_id: str, date_iso: str, creneau: str) -> dict:
    """Écran de synthèse : candidats, déjà faits, choix enregistrés, textes."""
    from services import planification_hebdo as ph
    from services import seance as sc
    from services import plans_classe as pc
    from services import documents_seance as docs
    from services import travail as tr
    try:
        sc._seance(conn, store, annee, classe_id, date_iso, creneau)
    except sc.SeanceErreur as e:
        raise SyntheseErreur(str(e), e.code)
    detail = ph.detail_seance(conn, store, annee, classe_id, date_iso, creneau)
    cl = conn.execute("SELECT niveau, mer_active FROM classes WHERE id=?",
                      (classe_id,)).fetchone()
    cand, faits = {"notions": [], "methodes": []}, {"notions": [], "methodes": []}
    crp = detail.get("creneau_prog")
    if crp and detail.get("sequence_code"):
        cand = candidats(conn, cl["niveau"], detail["sequence_code"],
                         int(crp["partie_debut"] or 1), int(crp["partie_fin"] or 1))
        faits = deja_faits(conn, classe_id, date_iso, creneau,
                           crp["date_debut"], crp["date_fin"])
    choix = lire_contenu(conn, classe_id, date_iso, creneau)

    lignes = []
    # 1. Mise en route
    if cl and cl["mer_active"]:
        ex = conn.execute("SELECT 1 FROM affectation_exception WHERE classe_id=? AND "
                          "annee=? AND date=?", (classe_id, annee, date_iso)).fetchone()
        if detail.get("mer_type") == "mer_auto" and not ex:
            env = detail.get("mer_enveloppes") or []
            mot = "enveloppes" if len(env) > 1 else "enveloppe"
            lignes.append(f"Mise en route : automatismes ({mot} {_liste([str(e) for e in env])})")
        elif detail.get("mer_type") == "mer_prog" and not ex:
            p = _partie_mer(conn, store, annee, classe_id, date_iso, creneau)
            if p:
                lignes.append(f"Mise en route : {p['libelle']} ({p['rang']}/{p['nb']})")
            else:
                lignes.append(f"Mise en route : séance {detail.get('mer_rang') or ''}".strip())
        else:
            lignes.append("Pas de mise en route")
    # 2. Séquence principale
    if detail.get("sequence_code"):
        tete = " ".join(x for x in (detail["sequence_code"], detail.get("sequence_nom") or "") if x)
        part = detail.get("partie") or ""
        rn = (f" ({detail['rang_dans_partie']}/{detail['nb_partie']})"
              if detail.get("rang_dans_partie") else "")
        lignes.append(f"{tete}{' — ' + part if part else ''}{rn}")
    # 3. Cours
    noms_n = {x["id"]: x["titre"] for x in cand["notions"]}
    noms_m = {x["id"]: x["titre"] for x in cand["methodes"]}
    sel_n = [noms_n[i] for i in choix["notions"] if i in noms_n]
    sel_m = [noms_m[i] for i in choix["methodes"] if i in noms_m]
    if sel_n or sel_m:
        parts = []
        if sel_n:
            parts.append(f"notion{'s' if len(sel_n) > 1 else ''} ({_liste(sel_n)})")
        if sel_m:
            parts.append(f"méthode{'s' if len(sel_m) > 1 else ''} ({_liste(sel_m)})")
        lignes.append("Cours : " + " et ".join(parts))
    # 4. Activités (ordre choisi)
    lignes.extend(choix["activites"])
    # 5. Texte libre
    lignes.extend(l.strip() for l in choix["texte_libre"].splitlines() if l.strip())
    # 6. Documents distribués à cette séance (hors travaux)
    eleves = [e["id"] for e in pc.eleves_de_la_semaine(
        conn, classe_id, sc._lundi(date.fromisoformat(date_iso)).isoformat())]
    distribues = [d["libelle"] for d in
                  docs.pour_seance(conn, store, annee, classe_id, date_iso, creneau, eleves)["nouveaux"]
                  if d["distribue"]]
    if distribues:
        lignes.append("Documents distribués : " + _liste(distribues))
    # Travail à faire
    t = tr.pour_seance(conn, store, annee, classe_id, date_iso, creneau, eleves)
    travail = []
    for x in sorted(t["donnes_ici"], key=lambda x: tuple(x.get("echeance_classe") or ("9999", ""))):
        ech = x.get("echeance_classe")
        quand = f"Pour le {_date_fr(ech[0])} : " if ech else ""
        travail.append(f"{quand}{x['libelle']}{' (à rendre)' if x['retour'] == 'rendre' else ''}")
    return {
        "candidats": cand, "deja_faits": faits, "choix": choix,
        "activites": lister_activites(conn),
        "externe": not (cand["notions"] or cand["methodes"]),
        "contenu": "\n".join(lignes), "travail": "\n".join(travail),
    }
