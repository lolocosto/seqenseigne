"""services/referentiel_figeage.py — v0.15.2.9 (partie B2)

Action de figeage complète d'un référentiel.

Différence avec `figer_minimal` (v0.13.5.1, dans services.referentiels)
qui ne fait que la transition d'état BDD :

    `figer_complet` fait en plus, AVANT la transition :
      1. Vérification de l'éligibilité (atomes/évals/docs).
      2. Génération de la trace JSON dans `<ref>/_fige/trace.json`.
      3. Copie des PDF actifs dans `<ref>/_fige/pdfs/`.
      4. Puis appelle `figer_minimal` pour la transition d'état
         et l'annulation des concurrents (logique inchangée).

Après figeage, le référentiel devient *immuable* (du point de vue
métier — par convention, pas par verrou BDD). Les PDF figés et la trace
JSON garantissent qu'on peut :
  - Servir à l'utilisateur le contenu tel qu'il était au figeage,
    même si les atomes actifs changent ultérieurement ;
  - Construire des progressions annuelles sur cette base figée
    (chantier futur).

Layout des fichiers figés
-------------------------
    data/referentiels/<ref_id>/
        _artefacts/<doc_id>/<cible_key>.{tex,log,pdf}   (sources actives)
        <nom_fichier>.pdf                                (PDF métier actif)
        _fige/                                            ← NOUVEAU
            trace.json                                    structure complète
            pdfs/<nom_fichier>.pdf                        copies figées

Les chemins PDF dans trace.json sont RELATIFS au dossier `_fige`
(ex. `pdfs/livret_sequence__N10__S01.pdf`) — le dossier est déplaçable
sans casser les liens.

Trace JSON — schéma v1
----------------------
::

    {
      "version_schema": 1,
      "date_figeage": "2026-05-30T14:23:45Z",
      "referentiel": {"id","niveau","version",
                       "date_debut","date_fin","description"},

      "themes":    [{"code","nom","couleur"}],
      "sequences": [{
          "code","numero","nom","theme_code",
          "parties":      [{"numero","nb_seances_R_AE"}],
          "objectifs":    [{"code","nom","fin_cycle",
                            "critere_f","critere_a","critere_e",
                            "partie_numero","nb_seances"}],
          "precedents":   [{"niveau","sequence","ordre"}],
          "atomes_utilises": {
              "notions":           [{"id","num_connaissance","titre"}],
              "methodes":          [{"id","num_methode","titre"}],
              "exercices":         [{"id","num","serie","titre"}],
              "fiches_resume":     [{"id","num_fiche","titre"}],
              "cartes_automatisme":[{"id","num","type_pedago","titre"}]
          }
      }],
      "evaluations": [{
          "id","numero","ordre","titre","mode_notation",
          "exercices":  [{"exercice_id","ordre","bareme_points"}],
          "objectifs":  [{"objectif_id"}]
      }],
      "documents": [{
          "id","type_document","options","compile_date",
          "cibles": [{"cible_id","libelle","nom_fichier",
                      "chemin_pdf"}]   # relatif au dossier _fige
      }]
    }

Principe : identité (ids + métadonnées clés pour le suivi annuel),
PAS le contenu (texte des énoncés, démos, etc.). Ce dernier vit dans
les PDF figés.
"""
from __future__ import annotations

import datetime
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Callable

from services import referentiels as svc_ref
from services.referentiel_validation import evaluer_eligibilite_validation


VERSION_SCHEMA_TRACE = 2


# Traduction des codes série BDD vers les labels métier utilisés dans la
# trace JSON (cf. retour Laurent v0.15.2.11). Les codes F/A/E vivent dans
# `objectif_exos.serie` ; les labels existent aussi sur `exercices.serie`
# pour des raisons historiques.
_SERIE_LABEL = {
    'F': 'fondamental',
    'A': 'avancé',
    'E': 'exploration',
    # Tolérance : si la valeur est déjà un label, on la laisse passer.
    'fondamental': 'fondamental',
    'avancé':      'avancé',
    'exploration': 'exploration',
}


def _serie_label(code: str | None) -> str | None:
    if code is None:
        return None
    return _SERIE_LABEL.get(code, code)


def _now_iso_utc() -> str:
    # v0.15.2.9 — timezone-aware (datetime.utcnow() est déprécié py3.12+)
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%SZ'
    )


def _dict_row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


# ── Construction de la trace JSON ──────────────────────────────────────────


def _trace_referentiel(conn: sqlite3.Connection, ref_id: str) -> dict:
    r = conn.execute(
        "SELECT id, niveau, version, date_debut, date_fin, description "
        "FROM referentiel_niveaux WHERE id = ?", (ref_id,)
    ).fetchone()
    if r is None:
        raise ValueError(f"Référentiel introuvable : {ref_id}")
    return dict(r)


def _trace_themes(conn: sqlite3.Connection, ref_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT code, nom, couleur FROM referentiel_themes "
        "WHERE referentiel_id = ? ORDER BY code", (ref_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _trace_methode_de_objectif(conn: sqlite3.Connection,
                                  methode_id: str | None) -> list[dict]:
    """Méthode liée à un objectif (au plus 1, via `objectifs.methode_id`).

    Émise en LISTE — même cardinalité 0/1 — pour rester homogène avec les
    autres relations (notions, exercices, fiches) et faciliter le rendu
    JSON.
    """
    if not methode_id:
        return []
    r = conn.execute(
        "SELECT num_methode, titre FROM methodes WHERE id = ?",
        (methode_id,)
    ).fetchone()
    return [dict(r)] if r else []


def _trace_notions_de_objectif(conn: sqlite3.Connection,
                                 objectif_id: str) -> list[dict]:
    """Notions liées à un objectif via `objectif_notions`.

    ⚠ En BDD de production (mai 2026) cette table est très peu peuplée
    (8 lignes au total). La trace reflète la réalité BDD : si la relation
    n'existe pas pour cet objectif, on émet une liste vide. La
    réintégration plus fidèle viendra par parsing du plan de travail
    .tex (chantier séparé).
    """
    rows = conn.execute("""
        SELECT n.num_connaissance, n.titre
          FROM objectif_notions onx
          JOIN notions n ON n.id = onx.notion_id
         WHERE onx.objectif_id = ?
         ORDER BY onx.ordre, n.num_connaissance
    """, (objectif_id,)).fetchall()
    return [dict(r) for r in rows]


def _trace_exos_de_objectif(conn: sqlite3.Connection,
                              objectif_id: str) -> list[dict]:
    """Exercices liés à un objectif via `objectif_exos`.

    `objectif_exos.serie` (F/A/E) prime sur `exercices.serie` (label) car
    c'est la liaison qui définit dans QUELLE série l'exercice intervient
    pour CET objectif (un même exo peut potentiellement servir dans
    plusieurs séries pour différents objectifs).
    """
    rows = conn.execute("""
        SELECT e.num, oe.serie AS oe_serie, e.titre
          FROM objectif_exos oe
          JOIN exercices e ON e.id = oe.exercice_id
         WHERE oe.objectif_id = ?
         ORDER BY oe.ordre, e.num
    """, (objectif_id,)).fetchall()
    out = []
    for r in rows:
        out.append({
            'num':   r['num'],
            'serie': _serie_label(r['oe_serie']),
            'titre': r['titre'] or '',
        })
    return out


def _trace_cartes_de_partie(conn: sqlite3.Connection,
                               partie_id: str) -> list[dict]:
    """Cartes d'automatisme d'une partie : union des cartes liées à
    chaque objectif de la partie (via `objectif_cartes`)."""
    rows = conn.execute("""
        SELECT DISTINCT ca.num, ca.type_pedago, ca.titre
          FROM objectif_cartes oc
          JOIN cartes_automatisme ca ON ca.id = oc.carte_id
          JOIN objectifs o ON o.id = oc.objectif_id
         WHERE o.partie_id = ?
         ORDER BY ca.num
    """, (partie_id,)).fetchall()
    return [dict(r) for r in rows]


def _trace_exos_partie_par_type(conn: sqlite3.Connection,
                                   partie_id: str,
                                   type_: str) -> list[dict]:
    """Exercices de révision (type='R') ou d'approche (type='EA') d'une
    partie. Les références utilisent les colonnes `origin_*` car ces
    exercices viennent typiquement d'une autre séquence (révisions de
    l'année précédente, par exemple).
    """
    rows = conn.execute("""
        SELECT origin_niveau, origin_seq, origin_serie, origin_num,
               exercice_id
          FROM partie_exos_revision_approche
         WHERE partie_id = ? AND type = ?
         ORDER BY ordre
    """, (partie_id, type_)).fetchall()
    out = []
    for r in rows:
        # Tenter d'enrichir avec le titre de l'exercice s'il existe
        # encore dans la BDD active. Pas bloquant si absent.
        titre = ''
        if r['exercice_id']:
            t = conn.execute(
                "SELECT titre FROM exercices WHERE id = ?",
                (r['exercice_id'],)
            ).fetchone()
            if t:
                titre = t['titre'] or ''
        out.append({
            'niveau':   r['origin_niveau'],
            'sequence': r['origin_seq'],
            'num':      r['origin_num'],
            'serie':    _serie_label(r['origin_serie']),
            'titre':    titre,
        })
    return out


def _trace_fiches_de_partie(conn: sqlite3.Connection,
                                partie_id: str) -> list[dict]:
    """v0.15.2.12 — Fiches de résumé d'une PARTIE.

    Source : table `fiches_resume`, jointe sur les objectifs de la
    partie via `fiches_resume.objectif_id`. Conformément au retour de
    Laurent (mai 2026), les fiches sont émises sous l'objectif « Cours »
    de la partie (code 01/11/21), pas sous chaque objectif ordinaire.

    Cela reflète l'usage métier : la fiche de résumé est un OUTIL
    d'apprentissage du cours dans son ensemble pour cette partie ; sa
    liaison BDD à un objectif ordinaire (`fiches_resume.objectif_id`)
    est un détail d'organisation interne.
    """
    rows = conn.execute("""
        SELECT fr.num_fiche, fr.titre
          FROM fiches_resume fr
          JOIN objectifs o ON o.id = fr.objectif_id
         WHERE o.partie_id = ?
         ORDER BY fr.num_fiche
    """, (partie_id,)).fetchall()
    return [dict(r) for r in rows]


def _trace_objectifs_de_partie(conn: sqlite3.Connection,
                                  ref_id: str,
                                  seq_code: str,
                                  partie_id: str,
                                  partie_numero: int) -> list[dict]:
    """Objectifs d'une partie, avec leurs atomes liés.

    Source pour le contenu de l'objectif : table `objectifs` (BDD active)
    car c'est elle qui porte `partie_id` et les liens vers la méthode.

    L'objectif « Cours » (codes 01/11/21 selon partie 1/2/3) porte
    UNIQUEMENT la section `fiches_resume` (aggregée depuis toute la
    partie). Les objectifs ordinaires portent `methodes`, `notions`,
    `exercices` mais PAS `fiches_resume` (cf. correction Laurent
    v0.15.2.12 : la fiche est un outil de cours de la partie, pas une
    propriété d'un objectif ordinaire).
    """
    code_cours = f"{(partie_numero - 1) * 10 + 1:02d}"

    obj_rows = conn.execute("""
        SELECT id, code, nom, methode_id,
               critere_F, critere_A, critere_E, fin_cycle, nb_seances
          FROM objectifs
         WHERE partie_id = ?
         ORDER BY code
    """, (partie_id,)).fetchall()

    objectifs = []
    for o in obj_rows:
        obj = {
            'code':       o['code'],
            'nom':        o['nom'],
            'fin_cycle':  o['fin_cycle'],
            'critere_f':  o['critere_F'] or '',
            'critere_a':  o['critere_A'] or '',
            'critere_e':  o['critere_E'] or '',
            'nb_seances': o['nb_seances'],
        }
        if o['code'] == code_cours:
            # Objectif « Cours » : porte UNIQUEMENT les fiches de résumé
            # agrégées de toute la partie (pas de méthode/notion/exercice
            # spécifique).
            obj['fiches_resume'] = _trace_fiches_de_partie(conn, partie_id)
        else:
            # Objectif ordinaire : méthode + notions + exercices liés
            # (pas de fiches_resume — cf. correction Laurent v0.15.2.12).
            obj['methodes']  = _trace_methode_de_objectif(conn, o['methode_id'])
            obj['notions']   = _trace_notions_de_objectif(conn, o['id'])
            obj['exercices'] = _trace_exos_de_objectif(conn, o['id'])
        objectifs.append(obj)
    return objectifs


def _trace_parties_avec_objectifs(conn: sqlite3.Connection,
                                     ref_id: str,
                                     niveau: str,
                                     seq_code: str) -> list[dict]:
    """v2 — Parties d'une séquence avec leurs objectifs et atomes liés
    nichés à l'intérieur.

    Structure : chaque partie porte ses `cartes_automatisme`, ses
    `exercices_R` (révisions), `exercices_AE` (approche), et ses
    `objectifs`. Chaque objectif porte ses propres `methodes`, `notions`,
    `exercices`, `fiches_resume`.
    """
    sn_row = conn.execute(
        "SELECT id FROM sequences_par_niveau "
        "WHERE niveau = ? AND sequence_code = ?",
        (niveau, seq_code)
    ).fetchone()
    if sn_row is None:
        return []
    sn_id = sn_row['id']

    parties_rows = conn.execute("""
        SELECT id, numero, nb_seances_R_AE
          FROM sequence_parties
         WHERE sequence_par_niveau_id = ?
         ORDER BY numero
    """, (sn_id,)).fetchall()

    parties = []
    for p in parties_rows:
        parties.append({
            'numero':              p['numero'],
            'nb_seances_R_AE':     p['nb_seances_R_AE'],
            'cartes_automatisme':  _trace_cartes_de_partie(conn, p['id']),
            'exercices_R':         _trace_exos_partie_par_type(
                                      conn, p['id'], 'R'),
            'exercices_AE':        _trace_exos_partie_par_type(
                                      conn, p['id'], 'EA'),
            'objectifs':           _trace_objectifs_de_partie(
                                      conn, ref_id, seq_code,
                                      p['id'], p['numero']),
        })
    return parties


def _trace_precedents_de_sequence(conn: sqlite3.Connection,
                                    niveau: str,
                                    sequence: str) -> list[dict]:
    """Séquences prérequises (depuis sequence_par_niveau_precedences)."""
    rows = conn.execute("""
        SELECT p.precedent_niveau AS niveau,
               p.precedent_seq    AS sequence,
               p.ordre
          FROM sequence_par_niveau_precedences p
          JOIN sequences_par_niveau sn
            ON sn.id = p.sequence_par_niveau_id
         WHERE sn.niveau = ? AND sn.sequence_code = ?
         ORDER BY p.ordre
    """, (niveau, sequence)).fetchall()
    return [dict(r) for r in rows]


def _trace_sequences(conn: sqlite3.Connection, ref_id: str,
                      niveau: str) -> list[dict]:
    """v2 — structure : séquence → parties (avec atomes contextuels) →
    objectifs (avec atomes liés)."""
    sequences = []
    rows = conn.execute(
        "SELECT code, numero, nom, theme_code FROM referentiel_sequences "
        "WHERE referentiel_id = ? ORDER BY numero", (ref_id,)
    ).fetchall()
    for r in rows:
        seq = dict(r)
        seq_code = seq['code']
        seq['parties']    = _trace_parties_avec_objectifs(
                              conn, ref_id, niveau, seq_code)
        seq['precedents'] = _trace_precedents_de_sequence(
                              conn, niveau, seq_code)
        sequences.append(seq)
    return sequences


def _trace_evaluations(conn: sqlite3.Connection, niveau: str) -> list[dict]:
    evals = []
    rows = conn.execute("""
        SELECT id, numero, ordre, titre, mode_notation
          FROM evaluations
         WHERE niveau = ?
         ORDER BY ordre, numero
    """, (niveau,)).fetchall()
    for r in rows:
        ev = dict(r)
        ev_id = ev['id']
        exos = conn.execute("""
            SELECT exercice_id, ordre, bareme_points
              FROM evaluation_exercices
             WHERE evaluation_id = ?
             ORDER BY ordre
        """, (ev_id,)).fetchall()
        ev['exercices'] = [dict(e) for e in exos]
        objs = conn.execute("""
            SELECT objectif_id FROM evaluation_objectifs
             WHERE evaluation_id = ?
        """, (ev_id,)).fetchall()
        ev['objectifs'] = [dict(o) for o in objs]
        evals.append(ev)
    return evals


def _trace_documents(conn: sqlite3.Connection, ref_id: str,
                      lister_cibles: Callable) -> list[dict]:
    """Documents actifs du référentiel + leurs cibles figées.

    `lister_cibles` : fonction (conn, doc_id, ref_id, type_doc) → list[cible]
    Injectée pour permettre les tests sans dépendre du service réel.
    """
    docs = []
    rows = conn.execute("""
        SELECT id, type_document, options, compile_date, compile_ok
          FROM referentiel_documents
         WHERE referentiel_id = ?
         ORDER BY ordre
    """, (ref_id,)).fetchall()
    for r in rows:
        try:
            options = json.loads(r['options'] or '{}')
        except (json.JSONDecodeError, TypeError):
            options = {}
        if not options.get('actif', False):
            continue
        if not r['compile_ok']:
            # Ne devrait pas arriver si éligibilité passée, mais robuste.
            continue
        try:
            cibles = lister_cibles(conn, r['id'], ref_id, r['type_document'])
        except Exception:
            cibles = []
        doc = {
            'id':            r['id'],
            'type_document': r['type_document'],
            'options':       options,
            'compile_date':  r['compile_date'],
            'cibles':        [],
        }
        for c in cibles:
            doc['cibles'].append({
                'cible_id':    c.get('cible_id'),
                'libelle':     c.get('libelle'),
                'nom_fichier': c.get('nom_fichier'),
                # Chemin relatif au dossier _fige
                'chemin_pdf':  f"pdfs/{c.get('nom_fichier')}" if c.get('nom_fichier') else None,
            })
        docs.append(doc)
    return docs


def generer_trace(conn: sqlite3.Connection, ref_id: str,
                   lister_cibles: Callable) -> dict:
    """Construit la trace JSON complète d'un référentiel au moment du
    figeage.

    Parameters
    ----------
    conn : sqlite3.Connection
    ref_id : str
    lister_cibles : Callable(conn, doc_id, ref_id, type_doc) → list[cible]
        Injectée pour découpler ce service de
        ``services.referentiel_documents_compilation.lister_cibles_document``
        (qui fait l'inverse en important `referentiel_documents` qui
        importerait ce module → boucle d'import).

    Returns
    -------
    dict
        Trace complète (cf. docstring du module pour le schéma).
    """
    ref = _trace_referentiel(conn, ref_id)
    niveau = ref['niveau']
    return {
        'version_schema': VERSION_SCHEMA_TRACE,
        'date_figeage':   _now_iso_utc(),
        'referentiel':    ref,
        'themes':         _trace_themes(conn, ref_id),
        'sequences':      _trace_sequences(conn, ref_id, niveau),
        'evaluations':    _trace_evaluations(conn, niveau),
        'documents':      _trace_documents(conn, ref_id, lister_cibles),
    }


# ── Copie des PDF ──────────────────────────────────────────────────────────


def copier_pdfs(trace: dict, dossier_source: Path,
                 dossier_cible: Path) -> dict:
    """Copie les PDF référencés dans la trace.

    Pour chaque cible de chaque document : copie
    ``dossier_source/<nom_fichier>`` vers
    ``dossier_cible/pdfs/<nom_fichier>``.

    `dossier_source` = ``data/referentiels/<ref_id>/`` (PDF métier actifs).
    `dossier_cible`  = ``data/referentiels/<ref_id>/_fige/``.

    Retourne ``{copies: [...], echecs: [...]}`` où chaque entrée est un
    dict ``{nom_fichier, raison?}``.
    """
    dossier_pdfs = dossier_cible / 'pdfs'
    dossier_pdfs.mkdir(parents=True, exist_ok=True)

    copies: list[dict] = []
    echecs: list[dict] = []
    for doc in trace.get('documents', []):
        for cible in doc.get('cibles', []):
            nom = cible.get('nom_fichier')
            if not nom:
                continue
            src = dossier_source / nom
            if not src.is_file():
                echecs.append({'nom_fichier': nom,
                                'raison': f"source absente : {src}"})
                continue
            try:
                shutil.copy2(src, dossier_pdfs / nom)
                copies.append({'nom_fichier': nom})
            except Exception as e:
                echecs.append({'nom_fichier': nom, 'raison': str(e)})
    return {'copies': copies, 'echecs': echecs}


# ── Action figeage complète ────────────────────────────────────────────────


def peupler_snapshot_parties(conn: sqlite3.Connection, ref_id: str,
                              niveau: str) -> dict:
    """v0.19.1.3 — (Ré)écrit le snapshot du découpage en parties d'un
    référentiel, depuis le modèle actif (sequence_parties / objectifs).

    Tables réécrites pour CE référentiel (idempotent : DELETE puis INSERT) :
      - `referentiel_parties` (referentiel_id, seq_code, numero,
        nb_seances_R_AE) : une ligne par partie de chaque séquence du niveau ;
      - `referentiel_objectifs.partie_numero` et `.nb_seances` : mis à jour
        pour refléter la partie réelle de chaque objectif (via
        objectifs.partie_id → sequence_parties.numero) et son nombre de
        séances.

    Les objectifs eux-mêmes (lignes de referentiel_objectifs) ne sont PAS
    recréés ici : ils existent déjà (peuplés à la construction du
    référentiel). On ne corrige que leur rattachement à une partie et leur
    nb_seances. Les objectifs sans correspondance dans le modèle actif (cas
    de données alpha incomplètes) conservent leur partie_numero existant.

    `fin_cycle` est stocké en TEXTE 'O'/'N' dans le modèle actif et en
    INTEGER dans referentiel_objectifs : non touché ici (déjà figé à la
    construction).

    Retourne un petit rapport : {nb_parties, nb_objectifs_rattaches}.
    """
    # 1. referentiel_parties : purge + réécriture depuis sequence_parties.
    conn.execute(
        "DELETE FROM referentiel_parties WHERE referentiel_id = ?", (ref_id,)
    )
    parties = conn.execute("""
        SELECT spn.sequence_code AS seq_code,
               sp.numero          AS numero,
               sp.nb_seances_R_AE AS nb_seances_R_AE
          FROM sequence_parties sp
          JOIN sequences_par_niveau spn ON spn.id = sp.sequence_par_niveau_id
         WHERE spn.niveau = ?
         ORDER BY spn.sequence_code, sp.numero
    """, (niveau,)).fetchall()
    for p in parties:
        conn.execute("""
            INSERT INTO referentiel_parties
              (referentiel_id, seq_code, numero, nb_seances_R_AE)
            VALUES (?,?,?,?)
        """, (ref_id, p['seq_code'], p['numero'], p['nb_seances_R_AE']))

    # 2. referentiel_objectifs : mettre à jour partie_numero + nb_seances
    #    depuis le modèle actif, apparié par (seq_code, code).
    objs = conn.execute("""
        SELECT spn.sequence_code AS seq_code,
               o.code            AS code,
               sp.numero         AS partie_numero,
               o.nb_seances      AS nb_seances
          FROM objectifs o
          JOIN sequence_parties sp ON sp.id = o.partie_id
          JOIN sequences_par_niveau spn ON spn.id = sp.sequence_par_niveau_id
         WHERE spn.niveau = ?
    """, (niveau,)).fetchall()
    nb_rattaches = 0
    for o in objs:
        cur = conn.execute("""
            UPDATE referentiel_objectifs
               SET partie_numero = ?, nb_seances = ?
             WHERE referentiel_id = ? AND seq_code = ? AND code = ?
        """, (o['partie_numero'], o['nb_seances'],
              ref_id, o['seq_code'], o['code']))
        nb_rattaches += cur.rowcount

    return {'nb_parties': len(parties),
            'nb_objectifs_rattaches': nb_rattaches}


def purger_snapshot_referentiel(conn: sqlite3.Connection, ref_id: str) -> None:
    """v0.19.1.3 — Purge le snapshot en base d'un référentiel (appelé au
    déverrouillage). Sémantique : un référentiel `valide`/`en_cours` n'a PAS
    de photo en base — sa structure vit dans le modèle actif, éditable. Seul
    un référentiel verrouillé/utilisé porte un snapshot referentiel_*.

    On purge UNIQUEMENT le découpage en parties (referentiel_parties) et on
    réinitialise referentiel_objectifs.partie_numero à 1. On NE supprime PAS
    les lignes de referentiel_objectifs / referentiel_sequences elles-mêmes
    (elles sont peuplées à la construction du référentiel, pas au gel, et
    restent nécessaires tant que le référentiel existe). Le déverrouillage
    n'est possible que si le référentiel n'est pas `utilise` (aucune
    progression liée), donc cette purge est sans risque pour les progressions.

    Le dossier _verrouille/ (trace JSON + PDF) est conservé par l'appelant.
    """
    conn.execute(
        "DELETE FROM referentiel_parties WHERE referentiel_id = ?", (ref_id,)
    )
    conn.execute(
        "UPDATE referentiel_objectifs SET partie_numero = 1 "
        "WHERE referentiel_id = ?", (ref_id,)
    )


def verrouiller_complet(conn: sqlite3.Connection, ref_id: str,
                   dossier_referentiel: Path,
                   lister_cibles: Callable,
                   *,
                   force_confirme: bool = False,
                   maintenant: datetime.date | None = None) -> dict:
    """Action complète de figeage.

    Étapes :
      1. Vérification éligibilité (atomes/évals/docs).
         Refus si non éligible (`ValueError`).
      2. Vérification état == 'valide' (`ValueError` sinon).
      3. Lister concurrents : si non vide ET `force_confirme=False`,
         retourne `{confirmation_requise: True, concurrents: [...]}`
         sans rien modifier.
      4. Générer la trace JSON dans `<dossier>/_fige/trace.json`.
      5. Copier les PDF actifs dans `<dossier>/_fige/pdfs/`.
      6. Appliquer la transition d'état via
         `services.referentiels.figer_minimal` (qui annule les
         concurrents et passe à `fige` + pose date_debut).

    Retour en succès : ::

        {
          'confirmation_requise': False,
          'ref': {...},
          'concurrents_annules': [...],
          'fige': {
              'dossier':   str,        # `<dossier>/_fige`
              'trace':     str,        # chemin trace.json
              'nb_pdfs_copies': int,
              'echecs_copie':   [...], # vide si tout OK
          },
        }

    Lève :
      ValueError — référentiel introuvable, état != valide, ou non éligible.
    """
    # 1. Eligibilité
    diag = evaluer_eligibilite_validation(conn, ref_id)
    if not diag['eligible']:
        raise ValueError(
            "Référentiel non éligible au figeage : "
            + " ; ".join(diag['raisons'])
        )

    # 2. État
    row = conn.execute(
        "SELECT etat FROM referentiel_niveaux WHERE id = ?", (ref_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Référentiel introuvable : {ref_id}")
    if row['etat'] != 'valide':
        raise ValueError(
            f"Le référentiel doit être à l'état `valide` pour être figé. "
            f"État actuel : {row['etat']}."
        )

    # 3. Concurrents
    concurrents = svc_ref.lister_concurrents_a_annuler(conn, ref_id)
    if concurrents and not force_confirme:
        return {
            'confirmation_requise': True,
            'concurrents':          concurrents,
        }

    # 4. Génération trace
    # v0.15.3 — dossier renommé `_verrouille/` (anciennement `_fige/`).
    # Le migrer_schema_post_ddl renomme automatiquement au boot.
    dossier_verrouille = dossier_referentiel / '_verrouille'
    dossier_verrouille.mkdir(parents=True, exist_ok=True)
    trace = generer_trace(conn, ref_id, lister_cibles)
    chemin_trace = dossier_verrouille / 'trace.json'
    chemin_trace.write_text(
        json.dumps(trace, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    # 5. Copie PDF
    rapport_copie = copier_pdfs(trace, dossier_referentiel, dossier_verrouille)

    # 5bis. v0.19.1.3 — Peuplement du SNAPSHOT en base (tables referentiel_*).
    #   La photo figée du référentiel doit être autoportante : la progression
    #   (et les autres consommateurs) lisent les tables referentiel_*, pas la
    #   trace JSON (qui reste un artefact d'archive). On (ré)écrit donc, depuis
    #   le modèle actif et dans la même transaction, le découpage en parties
    #   (referentiel_parties) et le rattachement réel des objectifs à leur
    #   partie (referentiel_objectifs.partie_numero) + le nombre de séances.
    #   Idempotent (DELETE puis INSERT pour ce référentiel) → ré-exécutable au
    #   re-verrouillage.
    niveau = conn.execute(
        "SELECT niveau FROM referentiel_niveaux WHERE id = ?", (ref_id,)
    ).fetchone()['niveau']
    peupler_snapshot_parties(conn, ref_id, niveau)

    # 6. Transition d'état + annulation des concurrents.
    #    `verrouiller_minimal` recalcule lui-même les concurrents et
    #    commit en BDD. On lui passe `force_confirme=True` car on a
    #    déjà fait le contrôle au-dessus.
    res_verrouille = svc_ref.verrouiller_minimal(
        conn, ref_id, force_confirme=True, maintenant=maintenant
    )

    return {
        'confirmation_requise': False,
        'ref':                 res_verrouille.get('ref'),
        'concurrents_annules': res_verrouille.get('concurrents_annules', []),
        'verrouille': {
            'dossier':        str(dossier_verrouille),
            'trace':          str(chemin_trace),
            'nb_pdfs_copies': len(rapport_copie['copies']),
            'echecs_copie':   rapport_copie['echecs'],
        },
    }


# v0.15.3 — Alias rétro-compat (à retirer en v0.16).
figer_complet = verrouiller_complet
