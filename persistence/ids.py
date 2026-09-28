"""
persistence/ids.py — Générateurs d'identifiants pour toutes les entités.

Principe : tous les ids de la base sont des UUID opaques préfixés par
un code de type (deux lettres) pour lisibilité lors du débogage :

  cl_a1b2c3d4    classe
  el_a1b2c3d4    élève
  pg_a1b2c3d4    progression
  cr_a1b2c3d4    créneau
  rf_a1b2c3d4    référentiel
  no_a1b2c3d4    notion
  me_a1b2c3d4    méthode
  ex_a1b2c3d4    exercice
  lv_a1b2c3d4    livret
  im_a1b2c3d4    image
  et_a1b2c3d4    établissement

Les préfixes n'ont aucune valeur sémantique à l'exécution (les ids sont
traités comme des chaînes opaques par la base). Ils servent uniquement à
lire la base à l'œil nu et à repérer visuellement un id mal collé.

Les contraintes d'unicité métier (ex: une seule classe (nom, année,
établissement) à la fois) sont portées par les tables via des index
UNIQUE séparés — pas par l'id.

Largeur : 8 hex = 2^32 ≈ 4 milliards de valeurs. À l'échelle d'un
enseignant sur une carrière, la probabilité de collision est inférieure
au seuil de précision du calcul. Pour un usage multi-utilisateurs avec
des millions d'entités, passer à 12 hex (paramètre `largeur`) serait
prudent ; ce n'est pas le cas aujourd'hui.
"""

from __future__ import annotations
import uuid


def _uuid(prefixe: str, largeur: int = 8) -> str:
    """Retourne un id opaque : préfixe + '_' + hex aléatoire."""
    return f"{prefixe}_{uuid.uuid4().hex[:largeur]}"


def nouveau_id_classe() -> str:       return _uuid("cl")
def nouveau_id_eleve() -> str:        return _uuid("el")
def nouveau_id_progression() -> str:  return _uuid("pg")
def nouveau_id_creneau() -> str:      return _uuid("cr")
def nouveau_id_referentiel() -> str:  return _uuid("rf")
def nouveau_id_notion() -> str:       return _uuid("no")
def nouveau_id_methode() -> str:      return _uuid("me")
def nouveau_id_objectif() -> str:     return _uuid("ob")
def nouveau_id_exercice() -> str:     return _uuid("ex")
def nouveau_id_livret() -> str:       return _uuid("lv")
def nouveau_id_image() -> str:        return _uuid("im")
def nouveau_id_etablissement() -> str: return _uuid("et")

# ── R1 — Structure du cycle ──────────────────────────────────────────────────
def nouveau_id_theme() -> str:             return _uuid("th")
def nouveau_id_sequence_du_cycle() -> str: return _uuid("sc")

# ── R4 — Séquences par niveau et parties ─────────────────────────────────────
def nouveau_id_sequence_par_niveau() -> str: return _uuid("sn")
def nouveau_id_partie() -> str:              return _uuid("pt")
