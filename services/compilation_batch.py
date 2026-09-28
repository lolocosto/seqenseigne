r"""
services/compilation_batch.py — Compilation en série de tous les atomes
filtrés selon (type, niveau, séquence).

Conçu comme une bibliothèque pure : pas d'import Flask, pas d'I/O HTTP.
La route SSE (`routes/admin.py`) appelle simplement `iter_compilation`
et formate chaque événement en `data: {json}\n\n`.

API
---
- recenser_atomes(store, type, niveau, sequence) -> list[Atome]
    Liste les atomes éligibles avec leur identifiant lisible. Lecture seule.

- iter_compilation(store, racine_sources, dossier_images, cache_dir,
                   pdflatex, racine_appli, timeout, max_erreurs_consecutives,
                   filtre, annule=lambda: False)
    -> Iterator[Evenement]
    Générateur qui produit un événement par atome traité, plus un événement
    final récapitulatif. Conçu pour être consommé par un EventStream SSE.

- ecrire_rapport_md(evenements, chemin) -> Path
    Écrit un rapport Markdown. Appelé par la route une fois le run terminé.

Statuts d'un atome
------------------
- 'succes'             : compilation OK, PDF produit
- 'cache'              : PDF déjà en cache (hash inchangé), rien à recompiler
- 'echec_vide'         : atome sans aucune section non vide (refusé en amont)
- 'echec_compilation'  : pdflatex a planté avec un message d'erreur LaTeX
- 'echec_infra'        : pdflatex introuvable, timeout, ou exception Python.
                         C'est ce qui peut déclencher l'abandon global.

L'abandon global se déclenche après `max_erreurs_consecutives` erreurs
'echec_infra' consécutives. Tout autre statut (y compris echec_compilation)
réinitialise le compteur.
"""

from __future__ import annotations
import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator

from services.atomes import _a_des_items
from services.compilateur_pdf import (
    ResultatCompilation, compiler_atome,
)
from services.latex_rendu_atome import generer_tex_par_type
from services.fiches_resume import lister_fiches
from services.cartes_automatisme import lister_cartes


# ── Constantes ────────────────────────────────────────────────────────────────

TYPES_VALIDES = ('notion', 'methode', 'exercice', 'fiche', 'carte')

# Ordre de traitement à l'intérieur d'une (niveau, séquence)
# v0.18.0 — fiche et carte ajoutées (même mécanisme : generer_tex_par_type +
# compiler_atome avec cache). Cours d'abord, puis fiches, puis cartes.
ORDRE_TYPES = ('notion', 'methode', 'exercice', 'fiche', 'carte')

# Statuts retournés par iter_compilation pour chaque atome
STATUT_SUCCES = 'succes'
STATUT_CACHE = 'cache'
STATUT_ECHEC_VIDE = 'echec_vide'
STATUT_ECHEC_COMPILATION = 'echec_compilation'
STATUT_ECHEC_INFRA = 'echec_infra'


# ── Modèles ──────────────────────────────────────────────────────────────────

@dataclass
class Atome:
    """Atome éligible à la compilation, avec identifiant lisible.

    Les champs sont remplis par `recenser_atomes` à partir des tables
    notions/methodes/exercices. `data` contient le dict brut tel que retourné
    par les `lire_*` du store, utile pour vérifier la présence de sections
    sans recharger la BDD.
    """
    type: str               # 'notion' | 'methode' | 'exercice'
    id: str
    niveau: str             # 'N10' | 'N11' | 'N12' | ''
    sequence: str           # 'S01' | … | 'S14' | ''
    identifiant: str        # ex. 'N10/S01/F02', 'N10/S01/Notion 03'
    titre: str
    data: dict = field(default_factory=dict)


@dataclass
class Filtre:
    """Filtre de sélection. Une chaîne vide signifie « pas de filtre »."""
    type: str = ''       # '' | 'notion' | 'methode' | 'exercice'
    niveau: str = ''     # '' | 'N10' | 'N11' | 'N12'
    sequence: str = ''   # '' | 'S01' | … | 'S14'

    def correspond(self, atome: Atome) -> bool:
        if self.type and atome.type != self.type:
            return False
        if self.niveau and atome.niveau != self.niveau:
            return False
        if self.sequence and atome.sequence != self.sequence:
            return False
        return True


# ── Identifiants lisibles ────────────────────────────────────────────────────

def _identifiant_exercice(data: dict) -> str:
    """'N10/S01/F02' ou variante dégradée si métadonnées partielles."""
    niv = data.get('niveau') or ''
    seq = data.get('sequence') or ''
    serie_code = data.get('serie_code') or ''
    num = data.get('num')
    code = ''
    if serie_code:
        code = serie_code
        if num is not None:
            code += str(num).zfill(2)
    parts = [p for p in (niv, seq, code) if p]
    return '/'.join(parts) if parts else f"exercice {data.get('id', '')}"


def _identifiant_notion(data: dict) -> str:
    """'N10/S01/Notion 03' ou dégradé."""
    niv = data.get('niveau') or ''
    seq = data.get('sequence') or ''
    num = data.get('num_connaissance') or ''
    suffixe = f'Notion {num}' if num else 'Notion'
    parts = [p for p in (niv, seq, suffixe) if p]
    return '/'.join(parts) if parts else f"notion {data.get('id', '')}"


def _identifiant_methode(data: dict) -> str:
    """'N10/S01/Méthode 02' ou dégradé."""
    niv = data.get('niveau') or ''
    seq = data.get('sequence') or ''
    num = data.get('num_methode')
    if num is not None:
        suffixe = f'Méthode {str(num).zfill(2)}'
    else:
        suffixe = 'Méthode'
    parts = [p for p in (niv, seq, suffixe) if p]
    return '/'.join(parts) if parts else f"méthode {data.get('id', '')}"


def _identifiant_fiche(data: dict) -> str:
    """'N10/S01/Fiche 02' ou dégradé."""
    niv = data.get('niveau') or ''
    seq = data.get('sequence') or ''
    num = data.get('num_fiche')
    suffixe = f'Fiche {str(num).zfill(2)}' if num is not None else 'Fiche'
    parts = [p for p in (niv, seq, suffixe) if p]
    return '/'.join(parts) if parts else f"fiche {data.get('id', '')}"


def _identifiant_carte(data: dict) -> str:
    """'N10/S01/Carte 02' ou dégradé."""
    niv = data.get('niveau') or ''
    seq = data.get('sequence') or ''
    num = data.get('num')
    suffixe = f'Carte {str(num).zfill(2)}' if num is not None else 'Carte'
    parts = [p for p in (niv, seq, suffixe) if p]
    return '/'.join(parts) if parts else f"carte {data.get('id', '')}"


# ── Recensement des atomes ───────────────────────────────────────────────────

def recenser_atomes(store, filtre: Filtre | None = None) -> list[Atome]:
    """Liste les atomes éligibles à la compilation, dans l'ordre de traitement.

    Ordre : par niveau (N10 → N11 → N12), puis par séquence (S01 → S14),
    puis par type (notion → methode → exercice), puis par numéro.

    Les atomes sans niveau ou sans séquence sont placés en fin de liste
    (tri stable, leur ordre interne reflète l'ordre de la BDD).

    Le filtre, s'il est fourni, est appliqué pendant le recensement pour
    éviter de matérialiser des atomes qui seront jetés.
    """
    f = filtre or Filtre()

    atomes: list[Atome] = []

    # Notions
    if not f.type or f.type == 'notion':
        for n in store.lire_notions():
            niveau = n.get('niveau', '') or ''
            sequence = n.get('sequence', '') or ''
            if f.niveau and niveau != f.niveau:
                continue
            if f.sequence and sequence != f.sequence:
                continue
            atomes.append(Atome(
                type='notion',
                id=n['id'],
                niveau=niveau,
                sequence=sequence,
                identifiant=_identifiant_notion(n),
                titre=n.get('titre', '') or '',
                data=n,
            ))

    # Méthodes
    if not f.type or f.type == 'methode':
        for m in store.lire_methodes():
            niveau = m.get('niveau', '') or ''
            sequence = m.get('sequence', '') or ''
            if f.niveau and niveau != f.niveau:
                continue
            if f.sequence and sequence != f.sequence:
                continue
            atomes.append(Atome(
                type='methode',
                id=m['id'],
                niveau=niveau,
                sequence=sequence,
                identifiant=_identifiant_methode(m),
                titre=m.get('titre', '') or '',
                data=m,
            ))

    # Exercices
    if not f.type or f.type == 'exercice':
        for e in store.lire_exercices():
            niveau = e.get('niveau', '') or ''
            sequence = e.get('sequence', '') or ''
            if f.niveau and niveau != f.niveau:
                continue
            if f.sequence and sequence != f.sequence:
                continue
            atomes.append(Atome(
                type='exercice',
                id=e['id'],
                niveau=niveau,
                sequence=sequence,
                identifiant=_identifiant_exercice(e),
                titre=e.get('nom', '') or '',
                data=e,
            ))

    # Fiches de résumé (v0.18.0)
    if not f.type or f.type == 'fiche':
        with store._conn() as conn:
            fiches = lister_fiches(
                conn,
                niveau=f.niveau or None,
                sequence=f.sequence or None,
            )
        for fi in fiches:
            atomes.append(Atome(
                type='fiche',
                id=fi['id'],
                niveau=fi.get('niveau', '') or '',
                sequence=fi.get('sequence', '') or '',
                identifiant=_identifiant_fiche(fi),
                titre=fi.get('titre', '') or '',
                data=fi,
            ))

    # Cartes d'automatisme (v0.18.0)
    # lister_cartes exige (niveau, sequence) ; pour un recensement global ou
    # partiel, on requête directement la table en respectant le filtre.
    if not f.type or f.type == 'carte':
        with store._conn() as conn:
            sql = "SELECT id, titre, num, niveau, sequence FROM cartes_automatisme"
            params: list = []
            where = []
            if f.niveau:
                where.append("niveau = ?"); params.append(f.niveau)
            if f.sequence:
                where.append("sequence = ?"); params.append(f.sequence)
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY niveau, sequence, ordre, num"
            rows = conn.execute(sql, params).fetchall()
        for r in rows:
            data = {
                'id': r['id'], 'titre': r['titre'] or '',
                'num': r['num'],
                'niveau': r['niveau'] or '', 'sequence': r['sequence'] or '',
            }
            atomes.append(Atome(
                type='carte',
                id=r['id'],
                niveau=data['niveau'],
                sequence=data['sequence'],
                identifiant=_identifiant_carte(data),
                titre=data['titre'],
                data=data,
            ))

    # Tri global : (niveau_zzz, sequence_zzz, ordre_type, num)
    # Les chaînes vides triées en fin via remplacement par '\uffff' (max str).
    def cle(a: Atome):
        niv = a.niveau if a.niveau else '\uffff'
        seq = a.sequence if a.sequence else '\uffff'
        ordre_type = ORDRE_TYPES.index(a.type) if a.type in ORDRE_TYPES else len(ORDRE_TYPES)
        # num_secondaire : extrait selon le type pour ordonner à l'intérieur d'un type
        if a.type == 'exercice':
            num = a.data.get('num') or 0
            serie_code = a.data.get('serie_code') or ''
            # Ordre des séries cohérent avec l'identifiant : F, A, E, AE, autres
            ordre_serie = {'F': 0, 'A': 1, 'E': 2, 'AE': 3}.get(serie_code, 99)
            return (niv, seq, ordre_type, ordre_serie, num)
        if a.type == 'methode':
            num = a.data.get('num_methode') or 0
            return (niv, seq, ordre_type, 0, num)
        if a.type == 'fiche':
            num = a.data.get('num_fiche') or 0
            return (niv, seq, ordre_type, 0, num)
        if a.type == 'carte':
            num = a.data.get('num') or 0
            return (niv, seq, ordre_type, 0, num)
        # notion
        num_str = a.data.get('num_connaissance') or ''
        try:
            num = int(num_str)
        except (TypeError, ValueError):
            num = 99
        return (niv, seq, ordre_type, 0, num)

    atomes.sort(key=cle)
    return atomes


# ── Compilation d'un atome unique ────────────────────────────────────────────

def compiler_un_atome(
    conn: sqlite3.Connection,
    atome: Atome,
    racine_sources: Path | None,
    dossier_images: Path | None,
    cache_dir: Path | None,
    pdflatex: str | None,
    racine_appli: Path | None,
    timeout: int,
    tikz_libraries: list[str] | None = None,
    tblr_libraries: list[str] | None = None,
) -> dict:
    """Compile un atome unique et retourne le dict d'événement à émettre.

    Distingue les 5 statuts. Les exceptions Python (BDD inaccessible, etc.)
    sont attrapées et reclassées en `echec_infra`.

    Le dict retourné contient en plus, pour les échecs uniquement, les clés
    privées `_tex_source` et `_log_complet` (préfixées par `_` pour signaler
    qu'elles ne doivent pas être sérialisées en SSE — usage interne pour
    l'écriture des fichiers d'échec). Elles sont retirées par
    `iter_compilation` après écriture sur disque.
    """
    base = {
        'type': atome.type,
        'id': atome.id,
        'niveau': atome.niveau,        # v0.18.2 — pour le deeplink nouvel onglet
        'sequence': atome.sequence,    # v0.18.2 — idem
        'identifiant': atome.identifiant,
        'titre': atome.titre,
    }

    # 1. Atome vide ? Court-circuit avant la génération .tex.
    #
    # Sémantique v0.8.4 : un atome est « vide » si on n'aurait littéralement
    # rien à compiler. C'est différent de « atome incomplet pour le rapport
    # de couverture pédagogique » (qui est ce que `_a_des_items` mesure :
    # une notion sans aucune section avec items est signalée comme manquant
    # d'exemples, mais elle peut très bien avoir un corps non vide et donc
    # produire un PDF parfaitement valide).
    #
    # Critères réels :
    #   - exercice  : énoncé requis. Le corrigé est optionnel mais signalé.
    #   - notion    : corps non vide OU au moins une section avec items.
    #   - méthode   : idem.
    #
    # Avant v0.8.4, on utilisait `_a_des_items` partout, ce qui marquait à
    # tort comme « atome vide » des notions à corps seul (4 cas N10 réels :
    # S03/02, S03/03, S10/03, S10/06).
    sans_corrige = False
    if atome.type == 'exercice':
        if not (atome.data.get('enonce', '') or '').strip():
            return {**base, 'statut': STATUT_ECHEC_VIDE,
                    'message': "Énoncé vide.", 'duree_ms': 0}
        # v0.8.4 : un exercice sans corrigé n'est plus rejeté ; il est
        # compilé normalement et signalé via le flag `sans_corrige` sur
        # l'événement de succès. Le rapport MD liste séparément ces cas
        # pour qu'ils soient identifiables sans bloquer la compilation.
        if not (atome.data.get('corrige', '') or '').strip():
            sans_corrige = True
    elif atome.type in ('notion', 'methode'):
        corps_non_vide = bool((atome.data.get('corps', '') or '').strip())
        a_des_items = _a_des_items(atome.data)
        if not corps_non_vide and not a_des_items:
            return {**base, 'statut': STATUT_ECHEC_VIDE,
                    'message': "Ni corps ni section avec contenu.",
                    'duree_ms': 0}
    # v0.18.0 — fiche et carte : pas de court-circuit « vide » ici. Le data de
    # recensement ne contient pas leur contenu complet (sections / recto-verso) ;
    # on délègue à generer_tex_par_type (le serveur produit le .tex, et une erreur
    # LaTeX éventuelle est classée normalement). Cohérent avec le rendu unitaire.

    # 2. Génération du .tex.
    try:
        tex = generer_tex_par_type(conn, atome.type, atome.id, racine_sources,
                                   tikz_libraries=tikz_libraries,
                                   tblr_libraries=tblr_libraries)
    except (LookupError, ValueError) as e:
        return {**base, 'statut': STATUT_ECHEC_VIDE,
                'message': f"Données incomplètes : {e}", 'duree_ms': 0}
    except Exception as e:
        return {
            **base, 'statut': STATUT_ECHEC_INFRA,
            'message': f"Erreur génération .tex : {type(e).__name__}: {e}",
            'duree_ms': 0,
            # Pas de tex à conserver : la génération a planté avant.
            '_log_complet': f"Exception lors de la génération du .tex :\n"
                            f"{type(e).__name__}: {e}",
        }

    # 3. Compilation.
    try:
        resultat: ResultatCompilation = compiler_atome(
            tex_source=tex,
            racine_sources=racine_sources,
            cache_dir=cache_dir,
            pdflatex=pdflatex,
            racine_appli=racine_appli,
            timeout=timeout,
            dossier_images=dossier_images,
        )
    except Exception as e:
        return {
            **base, 'statut': STATUT_ECHEC_INFRA,
            'message': f"Erreur compilation : {type(e).__name__}: {e}",
            'duree_ms': 0,
            '_tex_source': tex,
            '_log_complet': f"Exception lors de l'appel à compiler_atome :\n"
                            f"{type(e).__name__}: {e}",
        }

    if resultat.ok:
        ev = {
            **base,
            'statut': STATUT_CACHE if resultat.depuis_cache else STATUT_SUCCES,
            'message': '',
            'duree_ms': resultat.duree_ms,
        }
        # v0.8.4 : flag informatif pour les exercices compilés sans corrigé.
        # N'affecte pas le statut (l'exercice compile bien) — sert juste à
        # alimenter une section dédiée dans le rapport MD.
        if sans_corrige:
            ev['sans_corrige'] = True
        return ev

    # Échec : distinguer infra vs LaTeX.
    msg = (resultat.erreurs[0].message if resultat.erreurs
           else 'Erreur inconnue de compilation.')
    msg_lower = msg.lower()
    if 'pdflatex introuvable' in msg_lower or 'timeout' in msg_lower:
        statut = STATUT_ECHEC_INFRA
    else:
        statut = STATUT_ECHEC_COMPILATION

    # On tronque un peu le message pour l'affichage en liste.
    message_court = msg
    if len(message_court) > 200:
        message_court = message_court[:197] + '…'

    return {
        **base, 'statut': statut, 'message': message_court,
        'duree_ms': resultat.duree_ms,
        '_tex_source': tex,
        '_log_complet': resultat.log_complet,
    }


# ── Itérateur principal ──────────────────────────────────────────────────────

def iter_compilation(
    store,
    racine_sources: Path | None,
    dossier_images: Path | None,
    cache_dir: Path | None,
    pdflatex: str | None,
    racine_appli: Path | None,
    timeout: int,
    max_erreurs_consecutives: int,
    filtre: Filtre | None = None,
    annule: Callable[[], bool] = lambda: False,
    dossier_echecs: Path | None = None,
    tikz_libraries: list[str] | None = None,
    tblr_libraries: list[str] | None = None,
) -> Iterator[dict]:
    """Itère sur tous les atomes filtrés et yield un événement par compilation.

    Emet un événement par atome (statut + métadonnées), puis un événement
    final {kind: 'fin', ...} avec les compteurs récapitulatifs.

    Si `annule()` retourne True à un moment donné, l'itération s'arrête
    proprement et émet `{kind: 'annule', ...}`.

    Si plus de `max_erreurs_consecutives` `echec_infra` se produisent
    d'affilée, l'itération s'arrête et émet `{kind: 'abandon', ...}`.

    Si `dossier_echecs` est fourni, le dossier est purgé au début du run
    (politique « un dossier propre = ce qui plante dans le run en cours »)
    puis chaque atome en échec (LaTeX ou infra) y voit son `.tex` source
    et son `.log` pdflatex écrits, nommés d'après son identifiant lisible.
    L'événement émis pour ces atomes contient alors le champ `nom_log`,
    qui permet à l'UI et au rapport Markdown d'afficher un lien vers
    le fichier.
    """
    atomes = recenser_atomes(store, filtre)
    total = len(atomes)

    # v0.8.3 : purge du dossier d'échecs au début du run (politique (c)).
    # On ne touche qu'aux fichiers .tex et .log directement présents : on
    # ne descend pas dans des sous-dossiers, on ne touche pas à d'autres
    # extensions. Si le dossier n'existe pas, on le crée. Si l'effacement
    # d'un fichier échoue, on continue (un fichier de plus ne casse rien).
    if dossier_echecs is not None:
        dossier_echecs.mkdir(parents=True, exist_ok=True)
        for f in dossier_echecs.iterdir():
            if f.is_file() and f.suffix in ('.tex', '.log'):
                try:
                    f.unlink()
                except OSError:
                    pass

    # Compteurs.
    compteurs = {
        STATUT_SUCCES: 0,
        STATUT_CACHE: 0,
        STATUT_ECHEC_VIDE: 0,
        STATUT_ECHEC_COMPILATION: 0,
        STATUT_ECHEC_INFRA: 0,
    }
    erreurs_infra_consecutives = 0
    duree_totale_ms = 0
    motif_arret: str | None = None

    # On ouvre une seule connexion pour tout le run (lecture seule).
    with store._conn() as conn:
        for index, atome in enumerate(atomes):
            if annule():
                motif_arret = 'annule'
                break

            ev = compiler_un_atome(
                conn=conn,
                atome=atome,
                racine_sources=racine_sources,
                dossier_images=dossier_images,
                cache_dir=cache_dir,
                pdflatex=pdflatex,
                racine_appli=racine_appli,
                timeout=timeout,
                tikz_libraries=tikz_libraries,
                tblr_libraries=tblr_libraries,
            )
            ev['kind'] = 'atome'
            ev['index'] = index + 1
            ev['total'] = total
            compteurs[ev['statut']] += 1
            duree_totale_ms += ev.get('duree_ms', 0) or 0

            # v0.8.3 : pour les échecs, écrire le .tex et le .log si on a
            # un dossier d'écriture. On retire ensuite les clés privées
            # `_tex_source` et `_log_complet` du dict pour qu'elles ne
            # soient pas sérialisées en SSE (potentiellement plusieurs
            # dizaines de Ko par atome → on ne veut pas surcharger le flux).
            if dossier_echecs is not None and ev['statut'] in (
                STATUT_ECHEC_COMPILATION, STATUT_ECHEC_INFRA,
            ):
                nom_log = _ecrire_fichiers_echec(
                    dossier_echecs,
                    ev.get('identifiant', ev.get('id', 'inconnu')),
                    ev.pop('_tex_source', None),
                    ev.pop('_log_complet', None),
                )
                if nom_log:
                    ev['nom_log'] = nom_log
            else:
                # Atomes qui ne sont pas en échec ou pas de dossier : on
                # retire quand même les clés privées si elles sont là (pour
                # echec_vide elles n'y sont pas, mais par sécurité).
                ev.pop('_tex_source', None)
                ev.pop('_log_complet', None)

            # Mise à jour du compteur d'erreurs infra consécutives.
            if ev['statut'] == STATUT_ECHEC_INFRA:
                erreurs_infra_consecutives += 1
            else:
                erreurs_infra_consecutives = 0

            yield ev

            if erreurs_infra_consecutives >= max_erreurs_consecutives:
                motif_arret = 'abandon'
                break

    # Événement final.
    final = {
        'kind': motif_arret if motif_arret else 'fin',
        'total': total,
        'traite': sum(compteurs.values()),
        'compteurs': compteurs,
        'duree_totale_ms': duree_totale_ms,
    }
    if motif_arret == 'abandon':
        final['message'] = (
            f"Abandon : {max_erreurs_consecutives} erreurs d'infrastructure "
            f"consécutives (pdflatex introuvable, timeout, ou exception). "
            f"Vérifiez l'installation de pdflatex et le timeout configuré."
        )
    yield final


# ── Écriture des fichiers d'échec ────────────────────────────────────────────

def _slug_pour_fichier(identifiant: str) -> str:
    """Transforme un identifiant lisible en nom de fichier sûr.

    `N10/S01/Notion 06` → `N10_S01_Notion_06`
    `N10/S12/Méthode 03` → `N10_S12_Methode_03`

    Conserve les chiffres, lettres ASCII et `_`. Remplace les autres
    caractères (slash, espace, accents…) par `_`. Compresse les `_`
    consécutifs et trime les `_` en bordure.
    """
    import unicodedata
    # Normalisation : décompose les accents (é → e + ◌́) puis filtre les
    # combinings.
    norm = unicodedata.normalize('NFD', identifiant)
    norm = ''.join(c for c in norm if not unicodedata.combining(c))
    # Remplace tout ce qui n'est pas [A-Za-z0-9_] par _
    out = []
    for c in norm:
        if c.isascii() and (c.isalnum() or c == '_'):
            out.append(c)
        else:
            out.append('_')
    s = ''.join(out)
    # Compresse les _ multiples.
    while '__' in s:
        s = s.replace('__', '_')
    s = s.strip('_')
    return s or 'atome'


def _ecrire_fichiers_echec(dossier: Path, identifiant: str,
                           tex_source: str | None,
                           log_complet: str | None) -> str | None:
    """Écrit le .tex et le .log d'un atome en échec dans `dossier`.

    Retourne le nom du fichier .log (sans le chemin) si écrit, None sinon.
    Échoue silencieusement en cas de problème d'écriture (un échec n'est
    pas une raison de casser le run en cours).
    """
    slug = _slug_pour_fichier(identifiant)
    nom_log = f'{slug}.log'
    try:
        if tex_source:
            (dossier / f'{slug}.tex').write_text(tex_source, encoding='utf-8')
        if log_complet:
            (dossier / nom_log).write_text(log_complet, encoding='utf-8')
        elif tex_source:
            # Pas de log mais on a écrit le .tex : on retourne quand même le
            # nom du log attendu pour cohérence (le fichier peut être absent,
            # le UI le gérera).
            pass
        return nom_log if log_complet else None
    except OSError:
        return None


# ── Rapport Markdown ─────────────────────────────────────────────────────────

# Libellés humains des statuts (pour le rapport et l'UI).
LIBELLES_STATUTS = {
    STATUT_SUCCES:             'Succès',
    STATUT_CACHE:              'Cache',
    STATUT_ECHEC_VIDE:         'Atome vide',
    STATUT_ECHEC_COMPILATION:  'Échec LaTeX',
    STATUT_ECHEC_INFRA:        'Erreur infrastructure',
}


def ecrire_rapport_md(evenements: list[dict], chemin: Path,
                      filtre: Filtre | None = None) -> Path:
    """Écrit un rapport Markdown récapitulatif. Retourne le chemin écrit.

    `evenements` est la liste des événements yieldés par iter_compilation,
    incluant l'événement final.
    """
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)

    atomes = [e for e in evenements if e.get('kind') == 'atome']
    final = next((e for e in evenements
                  if e.get('kind') in ('fin', 'abandon', 'annule')), None)

    f = filtre or Filtre()
    lignes: list[str] = []
    lignes.append(f"# Compilation des atomes — {datetime.now():%Y-%m-%d %H:%M:%S}")
    lignes.append("")

    # En-tête : filtre appliqué + récap.
    lignes.append("## Filtre appliqué")
    lignes.append("")
    lignes.append(f"- Type : `{f.type or 'tous'}`")
    lignes.append(f"- Niveau : `{f.niveau or 'tous'}`")
    lignes.append(f"- Séquence : `{f.sequence or 'toutes'}`")
    lignes.append("")

    if final is not None:
        lignes.append("## Récapitulatif")
        lignes.append("")
        lignes.append(f"- Atomes traités : **{final.get('traite', 0)}** "
                      f"sur {final.get('total', 0)}")
        c = final.get('compteurs', {})
        for statut in (STATUT_SUCCES, STATUT_CACHE, STATUT_ECHEC_VIDE,
                       STATUT_ECHEC_COMPILATION, STATUT_ECHEC_INFRA):
            lignes.append(f"- {LIBELLES_STATUTS[statut]} : "
                          f"**{c.get(statut, 0)}**")
        duree_s = final.get('duree_totale_ms', 0) / 1000.0
        lignes.append(f"- Durée totale de compilation : "
                      f"**{duree_s:.1f} s** "
                      f"(hors cache, hors temps réseau)")
        if final.get('kind') == 'abandon':
            lignes.append("")
            lignes.append(f"> **Abandon** : {final.get('message', '')}")
        elif final.get('kind') == 'annule':
            lignes.append("")
            lignes.append("> **Annulé** par l'utilisateur.")
        lignes.append("")

    # Tableau des échecs en premier (le plus utile).
    echecs = [e for e in atomes if e['statut'] in (
        STATUT_ECHEC_VIDE, STATUT_ECHEC_COMPILATION, STATUT_ECHEC_INFRA,
    )]
    if echecs:
        lignes.append(f"## Échecs ({len(echecs)})")
        lignes.append("")
        # v0.8.3 : si au moins un échec a un log associé, on ajoute la
        # colonne Log au tableau pour pointer vers le fichier de debug.
        # On ne l'affiche pas si aucun log n'est dispo (cas d'un run sans
        # dossier_echecs configuré, ou que des echec_vide).
        a_des_logs = any(e.get('nom_log') for e in echecs)
        if a_des_logs:
            lignes.append("| Identifiant | Type | Statut | Titre | Message | Log |")
            lignes.append("|---|---|---|---|---|---|")
            for e in echecs:
                log_cell = f"`{_md_cell(e['nom_log'])}`" if e.get('nom_log') else ''
                lignes.append(
                    f"| `{_md_cell(e['identifiant'])}` "
                    f"| {e['type']} "
                    f"| {LIBELLES_STATUTS.get(e['statut'], e['statut'])} "
                    f"| {_md_cell(e.get('titre', ''))} "
                    f"| {_md_cell(e.get('message', ''))} "
                    f"| {log_cell} |"
                )
            lignes.append("")
            lignes.append("Les fichiers `.tex` et `.log` listés sont dans "
                          "`data/cache_rendus/echecs/` côté serveur — "
                          "à ouvrir pour voir le détail complet de l'erreur "
                          "pdflatex (les messages de cette table sont "
                          "tronqués au premier mot du message d'erreur).")
            lignes.append("")
        else:
            lignes.append("| Identifiant | Type | Statut | Titre | Message |")
            lignes.append("|---|---|---|---|---|")
            for e in echecs:
                lignes.append(
                    f"| `{_md_cell(e['identifiant'])}` "
                    f"| {e['type']} "
                    f"| {LIBELLES_STATUTS.get(e['statut'], e['statut'])} "
                    f"| {_md_cell(e.get('titre', ''))} "
                    f"| {_md_cell(e.get('message', ''))} |"
                )
            lignes.append("")

    # Tableau succès / cache (compact).
    ok = [e for e in atomes if e['statut'] in (STATUT_SUCCES, STATUT_CACHE)]
    if ok:
        lignes.append(f"## Compilations OK ({len(ok)})")
        lignes.append("")
        lignes.append("| Identifiant | Type | Statut | Durée (ms) |")
        lignes.append("|---|---|---|---|")
        for e in ok:
            lignes.append(
                f"| `{_md_cell(e['identifiant'])}` "
                f"| {e['type']} "
                f"| {LIBELLES_STATUTS.get(e['statut'], e['statut'])} "
                f"| {e.get('duree_ms', 0)} |"
            )
        lignes.append("")

    # v0.8.4 — Section informative : exercices compilés OK mais sans corrigé.
    # Ces exercices ne sont PAS des échecs (ils figurent normalement dans
    # « Compilations OK » ci-dessus), mais le manque de corrigé est une
    # incomplétude pédagogique qu'on liste séparément pour qu'elle soit
    # visible dans le rapport sans bloquer la compilation.
    sans_corrige = [e for e in atomes if e.get('sans_corrige')]
    if sans_corrige:
        lignes.append(f"## Exercices sans corrigé ({len(sans_corrige)})")
        lignes.append("")
        lignes.append("Ces exercices ont compilé sans erreur mais leur "
                      "corrigé est vide. À compléter quand l'occasion se "
                      "présente — ils sont déjà comptabilisés dans "
                      "« Compilations OK » plus haut.")
        lignes.append("")
        lignes.append("| Identifiant | Titre |")
        lignes.append("|---|---|")
        for e in sans_corrige:
            lignes.append(
                f"| `{_md_cell(e['identifiant'])}` "
                f"| {_md_cell(e.get('titre', ''))} |"
            )
        lignes.append("")

    chemin.write_text('\n'.join(lignes), encoding='utf-8')
    return chemin


def _md_cell(texte: str) -> str:
    """Échappe les caractères qui casseraient une cellule de table Markdown."""
    if texte is None:
        return ''
    return (
        str(texte)
        .replace('\\', '\\\\')
        .replace('|', '\\|')
        .replace('\n', ' ')
        .replace('\r', ' ')
        .strip()
    )


# ── Sérialisation SSE ────────────────────────────────────────────────────────

def evenement_vers_sse(evenement: dict) -> str:
    """Sérialise un événement en frame SSE (UTF-8, JSON, double newline final).

    Format : ``data: {json}\\n\\n``. Pas de champ ``event:`` ni ``id:`` :
    le ``kind`` interne au JSON suffit pour le routage côté frontend.
    """
    return f"data: {json.dumps(evenement, ensure_ascii=False)}\n\n"


def nom_rapport(maintenant: datetime | None = None) -> str:
    """Nom de fichier rapport conventionnel : `Compilation_atomes_<date>_<heure>.md`."""
    m = maintenant or datetime.now()
    return f"Compilation_atomes_{m:%Y-%m-%d_%H-%M-%S}.md"
