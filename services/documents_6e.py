r"""services/documents_6e.py — v0.52.2

Documents de 6e rangés dans l'atelier d'exercices, un atome par document
(séries « documents », services/atomes.SERIES_DOCUMENTS) :

  - TP  travaux personnels          (type `travaux_personnels_6e`)
  - AC  activités complémentaires   (type `activites_complementaires_6e`)
  - AT  séances d'atelier           (type `seances_atelier_6e`)

L'énoncé de l'atome contient tout le document (titre compris :
`\seqTitreTravailSix`, `\seqTitreComplementSix`…, comme les `.tex` écrits
par l'import v0.52.0) ; la version corrigée s'obtient par
`\seqVersionCorrigee` (macros de réponse). Un corrigé non vide est une
explication, affichée en version corrigée seulement (`\seqLocExplication`).

Décisions (doc/redemarrage_v0_52_2.md) :
  - D1 Une seule géométrie, celle du module de 6e : même préambule que le
    livret 6e (livret_sequence_6e.document).
  - D2 Activité complémentaire : son numéro dans la série (AC01 → 1) est
    celui du titre « Activité complémentaire n » (`\seqTitreComplementSix`
    numérote par un compteur ; un document isolé afficherait toujours 1).
  - Les séquences d'archive `Xnn` ne produisent jamais de document.
"""

from __future__ import annotations

import sqlite3

TYPES_SERIES = {
    "travaux_personnels_6e": "TP",
    "activites_complementaires_6e": "AC",
    "seances_atelier_6e": "AT",
}
LIBELLES_COURTS = {"TP": "Travail personnel", "AC": "Activité complémentaire",
                   "AT": "Séance d'atelier"}


class Document6eErreur(ValueError):
    pass


def lire_atome(conn: sqlite3.Connection, exercice_id: str) -> dict:
    r = conn.execute("SELECT id, titre, enonce, corrige, variables, niveau, sequence, "
                     "serie_code, num FROM exercices WHERE id = ?", (exercice_id,)).fetchone()
    if r is None:
        raise Document6eErreur(f"Document introuvable : {exercice_id}")
    d = {k: (r[k] if r[k] is not None else "") for k in r.keys()}
    if d["serie_code"] not in LIBELLES_COURTS:
        raise Document6eErreur(f"{exercice_id} n'est pas un document de 6e "
                               f"(série {d['serie_code']!r}).")
    if (d["sequence"] or "").startswith("X"):
        raise Document6eErreur(f"{d['sequence']} est une séquence d'archive (cycle 3).")
    return d


def atomes_de_la_serie(conn: sqlite3.Connection, niveau: str, serie_code: str) -> list[dict]:
    """Atomes d'une série documents du niveau, par séquence puis numéro
    (sans les archives Xnn)."""
    return [dict(r) for r in conn.execute(
        "SELECT id, titre, sequence, num FROM exercices WHERE niveau = ? AND serie_code = ? "
        "AND sequence NOT LIKE 'X%' ORDER BY sequence, num, id", (niveau, serie_code))]


def corps_document(conn: sqlite3.Connection, atome: dict, corrige: bool) -> list[str]:
    from services.livret_sequence_6e import _nom_sequence, entete
    nom, _ = _nom_sequence(conn, atome["niveau"], atome["sequence"])
    L = [entete({"nom": nom or atome["titre"] or atome["sequence"]}, corrige)]
    if atome["serie_code"] == "AC":                                   # D2
        try:
            L.append(r"\setcounter{seqComplSix}{%d}" % (int(atome["num"]) - 1))
        except (TypeError, ValueError):
            pass
    if (atome.get("variables") or "").strip():
        L.append(atome["variables"].rstrip())
    L.append((atome.get("enonce") or "").strip())
    if (atome.get("corrige") or "").strip():
        L.append(r"\seqLocExplication{" + atome["corrige"].strip() + "}")
    return L


def generer_document_6e(conn: sqlite3.Connection, exercice_id: str,
                        options: dict | None = None, tikz_libraries=None,
                        tblr_libraries=None) -> str:
    """Document d'un atome TP, AC ou AT (option `version` : eleve | corrigee)."""
    from services.gabarits_documents import VERSIONS_6E
    from services.livret_sequence_6e import document
    version = (options or {}).get("version") or "eleve"
    if version not in VERSIONS_6E:
        raise Document6eErreur(f"version invalide : {version!r}")
    atome = lire_atome(conn, exercice_id)
    code = f"{atome['serie_code']}{int(atome['num'] or 0):02d}"
    titre = f"{LIBELLES_COURTS[atome['serie_code']]} 6e — {atome['sequence']} {code} — " \
            f"{atome['titre']}"
    return document(conn, atome["niveau"], titre,
                    corps_document(conn, atome, version == "corrigee"),
                    version == "corrigee", tikz_libraries, tblr_libraries)
