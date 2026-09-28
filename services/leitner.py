"""services/leitner.py — v0.22.0

Ordonnancement des automatismes selon la méthode de Leitner.

L'élève range ses cartes d'automatisme dans 4 enveloppes numérotées 1 à 4.
À chaque séance dédiée aux automatismes, on révise certaines enveloppes selon
une cadence géométrique (×2) :

  - enveloppe 1 : chaque séance          (1 séance sur 1)
  - enveloppe 2 : une séance sur 2
  - enveloppe 3 : une séance sur 4
  - enveloppe 4 : une séance sur 8

Une carte « connue » (au-delà de l'enveloppe 4) sort du dispositif : l'élève la
rend à l'enseignant qui la redemandera lors de son tour d'interrogation. Cela se
gère hors logiciel ; l'ordonnancement ne concerne que les enveloppes 1 à 4.

Le compteur avance d'une unité par séance d'automatismes. En mode
« automatismes pur », toutes les séances comptées de la classe sont des séances
d'automatismes, donc le compteur = le numéro de séance de la projection.

`enveloppes_a_reviser(n)` et `planning(seances)` sont purs (testables).
"""

from __future__ import annotations

NB_ENVELOPPES = 4
# Cadence : enveloppe e révisée toutes les 2**(e-1) séances.
#   1 → toutes les 1 ; 2 → toutes les 2 ; 3 → toutes les 4 ; 4 → toutes les 8.


def periode(enveloppe: int) -> int:
    """Périodicité de révision d'une enveloppe (en nombre de séances)."""
    return 2 ** (enveloppe - 1)


def enveloppes_a_reviser(numero_seance: int) -> list[int]:
    """Liste des enveloppes (1..4) à réviser à la n-ième séance d'automatismes.

    numero_seance : rang de la séance d'automatismes (1-based).
    L'enveloppe e est révisée quand numero_seance est multiple de 2**(e-1).
    Exemples :
        1 → [1]           (séance 1 : seule l'enveloppe 1)
        2 → [1, 2]
        3 → [1]
        4 → [1, 2, 3]
        8 → [1, 2, 3, 4]
    """
    if numero_seance < 1:
        return []
    return [e for e in range(1, NB_ENVELOPPES + 1)
            if numero_seance % periode(e) == 0]


def planning(seances: list) -> list:
    """Enrichit chaque séance (déjà projetée/datée) de la liste des enveloppes
    à réviser. En mode automatismes pur, le rang Leitner = le numéro de séance.

    seances : liste de dicts {numero, date, ...} (sortie de la projection).
    Retour : liste de dicts {..., enveloppes: [..]}.
    """
    out = []
    for s in seances:
        s2 = dict(s)
        s2["enveloppes"] = enveloppes_a_reviser(s.get("numero", 0))
        out.append(s2)
    return out
