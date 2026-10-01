"""services/eleves_sexe.py — v0.40.0

Sexe des élèves (M, F ou '' = non renseigné), utilisé par le placement
aléatoire mixte des plans de classe.

- Import Pronote : la colonne `Sexe` (M/F) complète AUSSI les élèves déjà
  présents (repérés par nom + prénom, sans tenir compte de la casse), sans rien
  changer d'autre chez eux. Les autres colonnes sensibles de l'export
  (date de naissance, projet d'accompagnement) ne sont jamais lues.
- Saisie manuelle dans la liste des élèves de la classe.
"""

from __future__ import annotations

SEXES = ("M", "F", "")

_ALIAS = {"m": "M", "masculin": "M", "garçon": "M", "garcon": "M", "h": "M",
          "homme": "M", "f": "F", "féminin": "F", "feminin": "F", "fille": "F",
          "femme": "F", "": ""}


class SexeErreur(ValueError):
    pass


def normaliser(valeur) -> str:
    v = str(valeur or "").strip().lower()
    if v not in _ALIAS:
        raise SexeErreur(f"Sexe non reconnu : {valeur!r} (attendu M, F ou vide).")
    return _ALIAS[v]


def definir(conn, eleve_id: str, sexe) -> str:
    s = normaliser(sexe)
    n = conn.execute("UPDATE eleves SET sexe=? WHERE id=?", (s, eleve_id)).rowcount
    if not n:
        raise SexeErreur(f"Élève {eleve_id!r} introuvable.")
    return s


def maj_depuis_import(conn, classe_id: str, rows: list[dict], col_nom: str,
                      col_prenom: str, col_sexe: str) -> int:
    """Renseigne le sexe des élèves de la classe à partir des lignes CSV.
    Retourne le nombre d'élèves dont le sexe a changé. Les valeurs non
    reconnues sont ignorées (le sexe existant est conservé)."""
    par_nom = {}
    for r in conn.execute(
            "SELECT e.id, e.nom, e.prenom, e.sexe FROM eleves e "
            "JOIN eleves_classes ec ON ec.eleve_id = e.id WHERE ec.classe_id=?",
            (classe_id,)).fetchall():
        par_nom[(r["nom"].strip().upper(), r["prenom"].strip().upper())] = dict(r)
    n = 0
    for row in rows:
        cle = ((row.get(col_nom) or "").strip().upper(),
               (row.get(col_prenom) or "").strip().upper())
        e = par_nom.get(cle)
        if not e:
            continue
        try:
            s = normaliser(row.get(col_sexe))
        except SexeErreur:
            continue
        if s and s != e["sexe"]:
            conn.execute("UPDATE eleves SET sexe=? WHERE id=?", (s, e["id"]))
            e["sexe"] = s
            n += 1
    return n
