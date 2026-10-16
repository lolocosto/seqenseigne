r"""
services/numerotation_livret.py — Ordre et numéros des exercices du livret
de séquence (v0.51.18).

Source unique de vérité pour :
  - l'ordre dans lequel le livret de séquence émet les exercices de
    chaque série (services/livret_sequence.py) ;
  - les numéros affichés par le plan de travail
    (services/livret_plans_de_travail.py).

Avant v0.51.18, chacun calculait de son côté : le livret triait les
exercices d'une série par IDENTIFIANT (aléatoire depuis que les ids sont
des `ex_xxxxxxxx`, donc ordre mélangé), et le plan affichait le rang de
l'exercice DANS SON OBJECTIF (qui repart à 1 à chaque objectif). Les deux
ne concordaient que par hasard.

Règles (cadrage v0.51.18, validé) :
  D1 — Séries AE, F, A, E : partie (numéro) → objectif (code) → rang dans
       l'objectif. Révisions : partie → R puis EA → rang. C'est l'ordre
       que fournit déjà `v2_lecture.lire_sequence_par_niveau`.
  D3 — Numéros continus sur toute la séquence, par série du paquet :
       série 0 (« Révisions ») = R/EA des parties puis AE des objectifs ;
       séries 1/2/3 = F/A/E. (\seqSerieExos ne remet ExoNum à zéro qu'au
       changement de série.)
  D4 — Un exercice rattaché à plusieurs objectifs d'une même série n'est
       émis qu'une fois (au premier objectif) ; il garde ce numéro partout.
  D5 — Un exercice de révision n'est pas repris dans les séries.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Ordre d'émission dans le livret. « R » regroupe les R et EA de partie
# (révisions et découverte), « AE » les activités d'approche rattachées
# aux objectifs ; tous deux vont dans la série 0 du paquet.
CODES_SERIES = ("R", "AE", "F", "A", "E")

# Série v2 (objectif_exos.serie) → code livret.
_SERIE_V2_VERS_CODE = (("EA", "AE"), ("F", "F"), ("A", "A"), ("E", "E"))


@dataclass
class NumerotationLivret:
    """Ordre des exercices par code de série, et numéro affiché."""
    ordre: dict[str, list[str]] = field(
        default_factory=lambda: {c: [] for c in CODES_SERIES})
    # numero[code][exercice_id] -> numéro (ExoNum) dans le livret
    numero: dict[str, dict[str, int]] = field(
        default_factory=lambda: {c: {} for c in CODES_SERIES})

    def numeros(self, code: str, exercice_ids) -> list[int]:
        """Numéros (triés, sans doublon) des exercices donnés dans la
        série `code` ; les exercices absents de cette série du livret
        (ex. repris en révision, D5) sont ignorés."""
        table = self.numero.get(code, {})
        return sorted({table[i] for i in exercice_ids if i in table})


def numeroter_exos_livret(parties: list[dict],
                          serie_A: bool = True) -> NumerotationLivret:
    """Calcule l'ordre d'émission et les numéros des exercices du livret.

    `parties` : structure de `v2_lecture.lire_sequence_par_niveau(...)
    ["parties"]` (parties triées par numéro, objectifs par code, exercices
    par rang).
    `serie_A` : option du livret ; sans série A, ses exercices ne sont ni
    émis ni numérotés (les autres séries ne bougent pas).
    """
    n = NumerotationLivret()

    # Révisions et découverte de partie.
    vus_revision: set[str] = set()
    for partie in parties:
        era = partie.get("exos_revision_approche", {}) or {}
        for typ in ("R", "EA"):
            for entry in era.get(typ, []) or []:
                ex_id = entry.get("exercice_id")
                if not ex_id or ex_id in vus_revision:
                    continue
                vus_revision.add(ex_id)
                n.ordre["R"].append(ex_id)

    # Séries rattachées aux objectifs.
    for partie in parties:
        for obj in partie.get("objectifs", []) or []:
            eps = obj.get("exos_par_serie", {}) or {}
            for serie_v2, code in _SERIE_V2_VERS_CODE:
                if code == "A" and not serie_A:
                    continue
                for entry in eps.get(serie_v2, []) or []:
                    ex_id = entry.get("exercice_id")
                    if (not ex_id or ex_id in vus_revision
                            or ex_id in n.ordre[code]):
                        continue
                    n.ordre[code].append(ex_id)

    # Numéros : série 0 = R puis AE, à la suite ; F, A, E chacune de 1.
    for i, ex_id in enumerate(n.ordre["R"] + n.ordre["AE"], start=1):
        code = "R" if i <= len(n.ordre["R"]) else "AE"
        n.numero[code][ex_id] = i
    for code in ("F", "A", "E"):
        for i, ex_id in enumerate(n.ordre[code], start=1):
            n.numero[code][ex_id] = i
    return n


def lire_structure_exos(conn, sequence_par_niveau_id: str) -> list[dict]:
    """Lecture minimale (parties → objectifs → exercices) d'une
    séquence-niveau, au format attendu par `numeroter_exos_livret`.

    Mêmes tris que `v2_lecture` : parties par numéro, objectifs par code,
    exercices par (série, rang) et révisions par (type, rang). N'utilise
    que sequence_parties, objectifs, objectif_exos et
    partie_exos_revision_approche, pour servir aussi au plan de travail.
    """
    parties: list[dict] = []
    for p in conn.execute(
        "SELECT id FROM sequence_parties "
        "WHERE sequence_par_niveau_id = ? ORDER BY numero",
        (sequence_par_niveau_id,),
    ).fetchall():
        partie_id = p[0]
        era: dict[str, list[dict]] = {"R": [], "EA": []}
        for typ, ex_id in conn.execute(
            "SELECT type, exercice_id FROM partie_exos_revision_approche "
            "WHERE partie_id = ? ORDER BY type, ordre",
            (partie_id,),
        ).fetchall():
            if typ in era:
                era[typ].append({"exercice_id": ex_id})
        objectifs: list[dict] = []
        for (obj_id,) in conn.execute(
            "SELECT id FROM objectifs WHERE partie_id = ? ORDER BY code",
            (partie_id,),
        ).fetchall():
            eps: dict[str, list[dict]] = {}
            for serie, ex_id in conn.execute(
                "SELECT serie, exercice_id FROM objectif_exos "
                "WHERE objectif_id = ? ORDER BY serie, ordre",
                (obj_id,),
            ).fetchall():
                eps.setdefault(serie, []).append({"exercice_id": ex_id})
            objectifs.append({"exos_par_serie": eps})
        parties.append({"exos_revision_approche": era,
                        "objectifs": objectifs})
    return parties


def numeroter_sequence(conn, sequence_par_niveau_id: str,
                       serie_A: bool = True) -> NumerotationLivret:
    """Raccourci : lecture minimale + numérotation d'une séquence-niveau."""
    return numeroter_exos_livret(
        lire_structure_exos(conn, sequence_par_niveau_id), serie_A=serie_A)
