"""services/decalage_progression.py — v0.21.4

Décalages de progression par classe.

La progression est commune à un niveau/année (partagée par plusieurs classes).
Un décalage matérialise un glissement de dates propre à UNE classe : « à partir
de `a_partir_de`, tout glisse de `nb_semaines` semaines ». Non destructif : la
progression commune n'est pas modifiée ; les décalages sont appliqués à la volée
pour produire la « progression annuelle réalisée » d'une classe (par opposition
à la « progression annuelle commune prévue », sans décalage).

`appliquer_decalages` est pure (testable sans base/réseau).

Table `decalage_progression(id, classe_id, annee, a_partir_de, nb_semaines,
motif, indispo_id)`.
"""

from __future__ import annotations
from datetime import date, timedelta
import uuid


class DecalageErreur(Exception):
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class DonneesInvalides(DecalageErreur):
    def __init__(self, message):
        super().__init__(message, "donnees_invalides")


class Introuvable(DecalageErreur):
    def __init__(self, did):
        super().__init__(f"Décalage {did!r} introuvable.", "introuvable", id=did)


def _rowid() -> str:
    return "dcl_" + uuid.uuid4().hex[:12]


# ── Fonction pure ────────────────────────────────────────────────────────────

def _lundi_de(iso: str) -> str:
    d = date.fromisoformat(iso)
    return (d - timedelta(days=d.weekday())).isoformat()


def semaines_neutralisees(decalages: list, lundis: list,
                          est_vacances) -> set:
    """Ensemble des semaines (lundis ISO) neutralisées par les décalages.

    lundis : liste ordonnée des lundis (ISO) de l'année scolaire.
    est_vacances(lundiISO) -> bool : la semaine est-elle entièrement en vacances.
    Pour chaque décalage : la semaine de cours contenant `a_partir_de` + les
    (nb_semaines-1) semaines de cours suivantes (en sautant les vacances).
    """
    neutr = set()
    for dec in decalages:
        seuil = dec.get("a_partir_de") or ""
        n = int(dec.get("nb_semaines", 0) or 0)
        if not seuil or n <= 0:
            continue
        cible = _lundi_de(seuil)
        idx = next((i for i, l in enumerate(lundis) if l >= cible), -1)
        if idx < 0:
            continue
        pris = 0
        while idx < len(lundis) and pris < n:
            l = lundis[idx]
            if not est_vacances(l):
                neutr.add(l)
                pris += 1
            idx += 1
    return neutr


def appliquer_decalages(creneaux: list, decalages: list,
                        lundis: list | None = None,
                        est_vacances=None) -> list:
    """Retourne une COPIE des créneaux aux dates recalculées selon les
    « semaines neutralisées » (algorithme §9 de la spec).

    lundis / est_vacances : contexte calendaire. Si absents (appel simplifié),
    on construit un calendrier sans vacances autour des créneaux — utile pour
    les tests unitaires qui ne fournissent pas de vacances.
    """
    if not decalages:
        return [dict(c) for c in creneaux]

    # Calendrier par défaut (sans vacances) si non fourni : plage large de lundis.
    if lundis is None:
        toutes = [c.get("date_debut") for c in creneaux] \
            + [c.get("date_fin") for c in creneaux] \
            + [d.get("a_partir_de") for d in decalages]
        toutes = [x for x in toutes if x]
        if not toutes:
            return [dict(c) for c in creneaux]
        d0 = _lundi_de(min(toutes))
        cur = date.fromisoformat(d0)
        lundis = []
        for _ in range(80):  # ~80 semaines de marge
            lundis.append(cur.isoformat())
            cur += timedelta(days=7)
    if est_vacances is None:
        est_vacances = lambda l: False  # noqa: E731

    N = semaines_neutralisees(decalages, lundis, est_vacances)
    if not N:
        return [dict(c) for c in creneaux]
    idx_de = {l: i for i, l in enumerate(lundis)}

    def est_cours(l):
        return not est_vacances(l)

    def avancer_cours(depart, k):
        i = idx_de.get(depart, -1)
        if i < 0:
            return depart
        c = 0
        while i < len(lundis):
            if est_cours(lundis[i]):
                if c == k:
                    return lundis[i]
                c += 1
            i += 1
        return lundis[-1]

    def etaler(depart, long):
        i = idx_de.get(depart, -1)
        if i < 0:
            return depart
        c, der = 0, depart
        while i < len(lundis) and c < long:
            l = lundis[i]
            if est_cours(l) and l not in N:
                der = l
                c += 1
            i += 1
        return der

    def nb_cours_entre(a, b):
        return max(1, sum(1 for l in lundis if a <= l <= b and est_cours(l)))

    def nb_neutr_avant(L):
        return sum(1 for l in N if l <= L)

    def jours_entre(a, b):
        return (date.fromisoformat(b) - date.fromisoformat(a)).days

    out = []
    for c in creneaux:
        c2 = dict(c)
        dd, df = c2.get("date_debut"), c2.get("date_fin")
        if not dd or not df:
            out.append(c2)
            continue
        Sd, Sf = _lundi_de(dd), _lundi_de(df)
        nouv_sd = avancer_cours(Sd, nb_neutr_avant(Sd))
        long = nb_cours_entre(Sd, Sf)
        nouv_sf = etaler(nouv_sd, long)
        decal_deb = jours_entre(Sd, nouv_sd)
        decal_fin = jours_entre(Sf, nouv_sf)
        if decal_deb:
            c2["date_debut"] = (date.fromisoformat(dd)
                                + timedelta(days=decal_deb)).isoformat()
        if decal_fin:
            c2["date_fin"] = (date.fromisoformat(df)
                              + timedelta(days=decal_fin)).isoformat()
        if decal_deb or decal_fin:
            c2["decale"] = True
        out.append(c2)
    return out


# ── Persistance ──────────────────────────────────────────────────────────────

def lundis_annee(annee_scolaire):
    """Liste ordonnee des lundis (ISO) de l'annee scolaire (1er sept -> 31 juil)."""
    d0 = int(annee_scolaire.split("-")[0])
    debut = date(d0, 9, 1)
    fin = date(d0 + 1, 7, 31)
    lundi = debut - timedelta(days=debut.weekday())
    if lundi < debut:
        lundi += timedelta(days=7)
    out = []
    cur = lundi
    while cur <= fin:
        out.append(cur.isoformat())
        cur += timedelta(days=7)
    return out


def calculer_pour_classe(creneaux, decalages, annee, periodes_vacances):
    """Applique les decalages aux creneaux d'une classe (semaines neutralisees)
    et renvoie ce que l'affichage doit savoir, sans calcul metier cote client :
      {"creneaux": [...decales...],
       "semaines_neutralisees": [{"lundi","motif"}, ...]}
    """
    lundis = lundis_annee(annee)

    def est_vacances(lundi_iso):
        d = date.fromisoformat(lundi_iso)
        for i in range(5):
            j = (d + timedelta(days=i)).isoformat()
            en_vac = any((p.get("start_date") or "") <= j < (p.get("end_date") or "")
                         for p in periodes_vacances)
            if not en_vac:
                return False
        return True

    creneaux_decales = appliquer_decalages(creneaux, decalages, lundis, est_vacances)
    N = semaines_neutralisees(decalages, lundis, est_vacances)

    def motif_de(lundi_iso):
        motifs = []
        for dec in decalages:
            seuil = dec.get("a_partir_de") or ""
            n = int(dec.get("nb_semaines", 0) or 0)
            if not seuil or n <= 0:
                continue
            cible = _lundi_de(seuil)
            idx = next((i for i, l in enumerate(lundis) if l >= cible), -1)
            if idx < 0:
                continue
            pris = 0
            while idx < len(lundis) and pris < n:
                l = lundis[idx]
                if not est_vacances(l):
                    if l == lundi_iso:
                        motifs.append(dec.get("motif") or "Indisponibilite")
                    pris += 1
                idx += 1
        return " . ".join(motifs) if motifs else "Decalage"

    neutralisees = [{"lundi": l, "motif": motif_de(l)} for l in sorted(N)]
    return {"creneaux": creneaux_decales, "semaines_neutralisees": neutralisees}


def lister(conn, classe_id: str, annee: str) -> list:
    rows = conn.execute(
        "SELECT id, classe_id, annee, a_partir_de, nb_semaines, motif, "
        "indispo_id FROM decalage_progression WHERE classe_id=? AND annee=? "
        "ORDER BY a_partir_de", (classe_id, annee)).fetchall()
    return [dict(r) for r in rows]


def _valider(a_partir_de, nb_semaines):
    if not (a_partir_de or "").strip():
        raise DonneesInvalides("La date « à partir de » est obligatoire.")
    try:
        date.fromisoformat(a_partir_de)
    except ValueError:
        raise DonneesInvalides(f"Date invalide : {a_partir_de!r}.")
    try:
        n = int(nb_semaines)
    except (TypeError, ValueError):
        raise DonneesInvalides("Le nombre de semaines doit être un entier.")
    if n < 1:
        raise DonneesInvalides("Le nombre de semaines doit être au moins 1.")
    return n


def creer(conn, classe_id: str, annee: str, *, a_partir_de: str,
          nb_semaines: int = 1, motif: str = "",
          indispo_id: str | None = None) -> dict:
    n = _valider(a_partir_de, nb_semaines)
    new_id = _rowid()
    conn.execute(
        "INSERT INTO decalage_progression "
        "(id, classe_id, annee, a_partir_de, nb_semaines, motif, indispo_id) "
        "VALUES (?,?,?,?,?,?,?)",
        (new_id, classe_id, annee, a_partir_de, n, (motif or "").strip(),
         indispo_id))
    return {"id": new_id, "classe_id": classe_id, "annee": annee,
            "a_partir_de": a_partir_de, "nb_semaines": n,
            "motif": (motif or "").strip(), "indispo_id": indispo_id}


def modifier(conn, did: str, champs: dict) -> dict:
    row = conn.execute("SELECT * FROM decalage_progression WHERE id=?",
                       (did,)).fetchone()
    if row is None:
        raise Introuvable(did)
    c = dict(row)
    if "a_partir_de" in champs:
        c["a_partir_de"] = champs["a_partir_de"]
    if "nb_semaines" in champs:
        c["nb_semaines"] = champs["nb_semaines"]
    if "motif" in champs:
        c["motif"] = (champs["motif"] or "").strip()
    n = _valider(c["a_partir_de"], c["nb_semaines"])
    conn.execute(
        "UPDATE decalage_progression SET a_partir_de=?, nb_semaines=?, motif=? "
        "WHERE id=?", (c["a_partir_de"], n, c["motif"], did))
    c["nb_semaines"] = n
    return c


def supprimer(conn, did: str) -> None:
    row = conn.execute("SELECT 1 FROM decalage_progression WHERE id=?",
                       (did,)).fetchone()
    if row is None:
        raise Introuvable(did)
    conn.execute("DELETE FROM decalage_progression WHERE id=?", (did,))
