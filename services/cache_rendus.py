"""services/cache_rendus.py — v0.56.2 : invalidation manuelle du cache des rendus PDF.

Audit (v0.56.2) — le cache des rendus PDF :
  - emplacement : `data/cache_rendus/` (dossier plat) : `<clé>.pdf` et
    `<clé>.log` ; les sous-dossiers `echecs/` et `echecs_mer/` gardent les
    logs des échecs du rendu par lot et de « Tout compiler » (ce ne sont pas
    des PDF en cache : ils ne sont pas vidés ici) ;
  - clé : `compilateur_pdf.hash_tex` = sha256 du `.tex` complet (16 car.),
    plus depuis la v0.56.2 l'empreinte des `.sty`/`.dtx` du paquet ;
  - utilisateurs : `compiler_atome(cache_dir=…)` appelé par le rendu d'atome
    (notion, méthode, exercice, fiche, carte d'automatisme), le rendu d'une
    évaluation, le livret / les documents de séquence et les cartes
    mentales, le plan de travail, « Tout compiler » (séquence, mise en
    route) et le rendu par lot ; les routes `…/rendu-pdf/info` lisent la
    même clé.

Le cache ne garde aucune trace du niveau d'un PDF (clé = empreinte du .tex) :
le vidage porte donc sur tout le cache.

Paramètre de requête commun : `sans_cache=1` sur une route de compilation
(« Recompiler sans cache » de l'onglet Rendu PDF, option « sans cache » de
l'atelier Séquence et de « Tout compiler »).
"""

from __future__ import annotations

from pathlib import Path

_VRAI = {'1', 'true', 'oui', 'on'}
EXTENSIONS_CACHE = ('.pdf', '.log')


def sans_cache_demande(args) -> bool:
    """`?sans_cache=1` (ou true / oui / on) : ignorer et remplacer le PDF en cache."""
    return str((args or {}).get('sans_cache', '') or '').strip().lower() in _VRAI


def _fichiers(cache_dir: Path) -> list[Path]:
    if not cache_dir.is_dir():
        return []
    return [p for p in cache_dir.iterdir()
            if p.is_file() and p.suffix.lower() in EXTENSIONS_CACHE]


def etat_cache(cache_dir: Path) -> dict:
    """Nombre de PDF, de logs et taille totale (octets) du cache."""
    fichiers = _fichiers(cache_dir)
    return {
        'nb_pdf': sum(1 for p in fichiers if p.suffix.lower() == '.pdf'),
        'nb_log': sum(1 for p in fichiers if p.suffix.lower() == '.log'),
        'octets': sum(p.stat().st_size for p in fichiers),
    }


def vider_cache(cache_dir: Path) -> dict:
    """Supprime les PDF et logs en cache (pas les sous-dossiers d'échecs).

    Retour : {'nb_pdf', 'nb_log', 'nb_fichiers', 'octets'} des fichiers supprimés."""
    nb_pdf = nb_log = octets = 0
    for p in _fichiers(cache_dir):
        try:
            taille = p.stat().st_size
            p.unlink()
        except OSError:
            continue
        octets += taille
        if p.suffix.lower() == '.pdf':
            nb_pdf += 1
        else:
            nb_log += 1
    return {'nb_pdf': nb_pdf, 'nb_log': nb_log, 'nb_fichiers': nb_pdf + nb_log,
            'octets': octets}
