"""services/progression_mer.py — v0.26.0

Progressions de mise en route « à la séance » : pendant, en séances, de la
progression principale (en semaines). Une progression MER par classe/année,
adossée à UN référentiel MER. On y pose des parties du référentiel, dans
l'ordre ; chaque partie consomme son nombre de séances (lu dans le référentiel).

Le référentiel MER est générique : `ref_mer_source` indique où lire sa
structure (« externe » aujourd'hui ; « interne » plus tard). La résolution des
parties (libellé, nb de séances) délègue selon la source.

`projeter_mer(seances, parties)` est pure (testable sans base).
"""

from __future__ import annotations
import uuid

ETATS = ("en_cours", "valide")
SOURCES = ("externe",)  # 'interne' viendra plus tard


class ProgMerErreur(Exception):
    def __init__(self, message: str, code: str = "erreur", **details):
        super().__init__(message)
        self.code = code
        self.details = details


class DonneesInvalides(ProgMerErreur):
    def __init__(self, message):
        super().__init__(message, "donnees_invalides")


class Introuvable(ProgMerErreur):
    def __init__(self, quoi, id_):
        super().__init__(f"{quoi} {id_!r} introuvable.", "introuvable", id=id_)


def _rid(prefixe: str) -> str:
    return f"{prefixe}_" + uuid.uuid4().hex[:12]


# ── Fonction pure : projection des parties sur les séances datées ─────────────

def projeter_mer(seances: list, parties: list) -> list:
    """Affecte à chaque séance datée la partie en cours, en consommant le
    nombre de séances de chaque partie dans l'ordre.

    seances : séances projetées et datées (déjà numérotées), ex. sortie de
              projection_seances.projeter — {numero, date, ...}.
    parties : parties posées dans l'ordre, chacune avec au moins
              {id, libelle, nb_seances, sequence_code, sequence_nom}.

    Retour : copie des séances enrichies de :
      {..., mer_partie_id, mer_libelle, mer_sequence, mer_rang_partie}
    où mer_rang_partie est le rang (1..nb) de la séance dans sa partie.
    Les séances au-delà de la dernière partie posée n'ont pas de partie
    (mer_partie_id = None) — la progression est « épuisée ».
    """
    out = []
    idx_partie = 0
    reste = parties[0]["nb_seances"] if parties else 0
    rang = 0
    for s in seances:
        s2 = dict(s)
        # Avancer à la prochaine partie non épuisée.
        while parties and idx_partie < len(parties) and reste <= 0:
            idx_partie += 1
            rang = 0
            if idx_partie < len(parties):
                reste = parties[idx_partie]["nb_seances"]
        if parties and idx_partie < len(parties):
            p = parties[idx_partie]
            rang += 1
            s2["mer_partie_id"] = p["id"]
            s2["mer_libelle"] = p.get("libelle", "")
            s2["mer_sequence"] = p.get("sequence_nom", "") or p.get("sequence_code", "")
            s2["mer_rang_partie"] = rang
            s2["mer_nb_partie"] = p["nb_seances"]
            reste -= 1
        else:
            s2["mer_partie_id"] = None
            s2["mer_libelle"] = ""
            s2["mer_sequence"] = ""
            s2["mer_rang_partie"] = 0
        out.append(s2)
    return out


# ── Résolution des parties selon la source du référentiel ─────────────────────

def resoudre_partie(conn, partie_id: str, source: str) -> dict | None:
    """Retourne {id, libelle, nb_seances, sequence_code, sequence_nom} pour une
    partie du référentiel MER, selon sa source. None si introuvable."""
    if source == "externe":
        r = conn.execute(
            "SELECT p.id, p.libelle, p.nb_seances, p.numero, "
            "s.code AS seq_code, s.nom AS seq_nom "
            "FROM referentiel_externe_partie p "
            "JOIN referentiel_externe_sequence s ON s.id = p.sequence_id "
            "WHERE p.id=?", (partie_id,)).fetchone()
        if r is None:
            return None
        return {"id": r["id"], "libelle": r["libelle"],
                "nb_seances": r["nb_seances"], "numero": r["numero"],
                "sequence_code": r["seq_code"], "sequence_nom": r["seq_nom"]}
    return None


def lister_parties_disponibles(conn, ref_mer_id: str, source: str) -> list:
    """Toutes les parties d'un référentiel MER (pour le choix), dans l'ordre du
    référentiel."""
    if source == "externe":
        rows = conn.execute(
            "SELECT p.id, p.libelle, p.nb_seances, p.numero, "
            "s.code AS seq_code, s.nom AS seq_nom, s.ordre AS seq_ordre, "
            "p.ordre AS p_ordre "
            "FROM referentiel_externe_partie p "
            "JOIN referentiel_externe_sequence s ON s.id = p.sequence_id "
            "WHERE s.ref_ext_id=? ORDER BY s.ordre, s.code, p.ordre, p.numero",
            (ref_mer_id,)).fetchall()
        return [{"id": r["id"], "libelle": r["libelle"],
                 "nb_seances": r["nb_seances"], "numero": r["numero"],
                 "sequence_code": r["seq_code"], "sequence_nom": r["seq_nom"]}
                for r in rows]
    return []


# ── Persistance : progression MER ─────────────────────────────────────────────

def lire_par_niveau(conn, niveau: str, annee: str) -> dict | None:
    r = conn.execute(
        "SELECT * FROM progression_mer WHERE niveau=? AND annee=?",
        (niveau, annee)).fetchone()
    if r is None:
        return None
    d = dict(r)
    d["parties"] = _lister_parties_posees(conn, d["id"])
    return d


def creer_ou_lire(conn, niveau: str, annee: str) -> dict:
    """Retourne la progression MER du niveau/année, en la créant si besoin."""
    ex = lire_par_niveau(conn, niveau, annee)
    if ex:
        return ex
    pid = _rid("pmr")
    conn.execute(
        "INSERT INTO progression_mer (id, niveau, annee, ref_mer_source, "
        "etat) VALUES (?,?,?, 'externe', 'en_cours')",
        (pid, niveau, annee))
    return lire_par_niveau(conn, niveau, annee)


def definir_referentiel(conn, prog_id: str, ref_mer_id: str,
                        ref_mer_source: str = "externe") -> dict:
    """Associe un référentiel MER à la progression. Change de référentiel PURGE
    les parties posées (elles référencent l'ancien référentiel)."""
    if ref_mer_source not in SOURCES:
        raise DonneesInvalides(f"Source invalide : {ref_mer_source!r}.")
    r = conn.execute("SELECT ref_mer_id FROM progression_mer WHERE id=?",
                     (prog_id,)).fetchone()
    if r is None:
        raise Introuvable("Progression MER", prog_id)
    if r["ref_mer_id"] and r["ref_mer_id"] != ref_mer_id:
        conn.execute("DELETE FROM progression_mer_partie WHERE "
                     "progression_mer_id=?", (prog_id,))
    conn.execute(
        "UPDATE progression_mer SET ref_mer_id=?, ref_mer_source=? WHERE id=?",
        (ref_mer_id, ref_mer_source, prog_id))
    return _lire(conn, prog_id)


def changer_etat(conn, prog_id: str, etat: str) -> dict:
    if etat not in ETATS:
        raise DonneesInvalides(f"État invalide : {etat!r}.")
    r = conn.execute("SELECT 1 FROM progression_mer WHERE id=?",
                     (prog_id,)).fetchone()
    if r is None:
        raise Introuvable("Progression MER", prog_id)
    conn.execute("UPDATE progression_mer SET etat=? WHERE id=?", (etat, prog_id))
    return _lire(conn, prog_id)


def _lire(conn, prog_id: str) -> dict:
    r = conn.execute("SELECT * FROM progression_mer WHERE id=?",
                     (prog_id,)).fetchone()
    if r is None:
        raise Introuvable("Progression MER", prog_id)
    d = dict(r)
    d["parties"] = _lister_parties_posees(conn, prog_id)
    return d


# ── Parties posées ────────────────────────────────────────────────────────────

def _lister_parties_posees(conn, prog_id: str) -> list:
    rows = conn.execute(
        "SELECT * FROM progression_mer_partie WHERE progression_mer_id=? "
        "ORDER BY ordre", (prog_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        info = resoudre_partie(conn, d["partie_id"], d["partie_source"])
        if info:
            d.update({"libelle": info["libelle"],
                      "nb_seances": info["nb_seances"],
                      "sequence_code": info["sequence_code"],
                      "sequence_nom": info["sequence_nom"]})
        else:
            # Partie disparue du référentiel (supprimée) : marquée orpheline.
            d.update({"libelle": "(partie supprimée)", "nb_seances": 0,
                      "sequence_code": "", "sequence_nom": "", "orpheline": True})
        out.append(d)
    return out


def poser_partie(conn, prog_id: str, partie_id: str,
                 partie_source: str = "externe") -> dict:
    """Ajoute une partie à la fin de la progression. Refuse un doublon (une
    partie est atomique, posée une seule fois)."""
    r = conn.execute("SELECT 1 FROM progression_mer WHERE id=?",
                     (prog_id,)).fetchone()
    if r is None:
        raise Introuvable("Progression MER", prog_id)
    if resoudre_partie(conn, partie_id, partie_source) is None:
        raise DonneesInvalides("Partie introuvable dans le référentiel.")
    deja = conn.execute(
        "SELECT 1 FROM progression_mer_partie WHERE progression_mer_id=? "
        "AND partie_id=?", (prog_id, partie_id)).fetchone()
    if deja:
        raise DonneesInvalides("Cette partie est déjà posée dans la progression.")
    ordre = conn.execute(
        "SELECT COALESCE(MAX(ordre),0)+10 FROM progression_mer_partie "
        "WHERE progression_mer_id=?", (prog_id,)).fetchone()[0]
    pid = _rid("pmp")
    conn.execute(
        "INSERT INTO progression_mer_partie (id, progression_mer_id, "
        "partie_id, partie_source, ordre) VALUES (?,?,?,?,?)",
        (pid, prog_id, partie_id, partie_source, ordre))
    return _lire(conn, prog_id)


def retirer_partie(conn, pose_id: str) -> None:
    r = conn.execute("SELECT 1 FROM progression_mer_partie WHERE id=?",
                     (pose_id,)).fetchone()
    if r is None:
        raise Introuvable("Partie posée", pose_id)
    conn.execute("DELETE FROM progression_mer_partie WHERE id=?", (pose_id,))


def deplacer_partie(conn, pose_id: str, sens: int) -> dict:
    """Monte/descend une partie posée dans l'ordre de la progression."""
    r = conn.execute("SELECT progression_mer_id FROM progression_mer_partie "
                     "WHERE id=?", (pose_id,)).fetchone()
    if r is None:
        raise Introuvable("Partie posée", pose_id)
    prog_id = r["progression_mer_id"]
    ids = [x["id"] for x in conn.execute(
        "SELECT id FROM progression_mer_partie WHERE progression_mer_id=? "
        "ORDER BY ordre", (prog_id,)).fetchall()]
    i = ids.index(pose_id)
    j = i + (1 if sens > 0 else -1)
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
        for k, x in enumerate(ids):
            conn.execute("UPDATE progression_mer_partie SET ordre=? WHERE id=?",
                         ((k + 1) * 10, x))
    return _lire(conn, prog_id)
