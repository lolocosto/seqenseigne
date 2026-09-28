r"""
services/livret_sequence.py — Génération du Livret de séquence (v0.11.2).

Produit le source LaTeX d'un livret pour UNE séquence donnée (par opposition
aux livrets annuels recap_cours et recap_exos qui agrègent un niveau entier).

API
---
generer_livret_sequence(conn, niveau, sequence_code, options) -> str
    Retourne le source .tex complet (documentclass + préambule + document).
    Le paramètre `options` est un dict structuré qui pilote l'inclusion
    des sections ; cf. validate_options() pour son format.

Architecture
------------
S'inspire de livret_recap_cours.py et livret_recap_exos.py :
- Composition par inlining BDD (cf. cadrage Q1 — la source de vérité est
  la BDD, pas des fichiers .tex au disque).
- Préambule construit sur mesure via construire_preambule.
- Numérotation continue par retrait du \setcounter local de chaque atome.
- Cycle annexes global pour ne pas saturer la limite de 16 \newwrite TeX.

Différences avec les livrets recap (annuels) :
- Une seule séquence donc pas de structure thèmes×séquences.
- Les fiches de résumé sont incluses (absentes du recap_cours).
- Les exos sont organisés par série, pas par partie/objectif (à la
  différence de ce qu'affiche l'atelier d'assemblage qui groupe par
  partie). Décision de cadrage v0.11.2 : pour le livret de séquence,
  l'enseignant veut un livret « tout en un » lisible, pas une
  reconstruction de la structure d'assemblage.

Toggles disponibles (cadrage v0.11.2 Q2)
----------------------------------------
options = {
  "cours": {
    "inclure": bool,                    # défaut True
    "fiches_resume": {
      "inclure": bool,                  # défaut True
      "a_completer": bool,              # défaut True (mode élève avec trous)
    }
  },
  "exercices": {
    "inclure": bool,                    # défaut True
    "serie_A": bool,                    # défaut True
  }
}

Quand cours.inclure=True : notions+méthodes obligatoires.
Quand exercices.inclure=True : révisions (exos R+EA de partie_exos_revision_approche)
+ série F + corrigés F + série E sont obligatoires. Série A pilotée par exercices.serie_A.

Quand cours.fiches_resume.a_completer=False, on redéfinit \acompleter pour
que les contenus à trou s'affichent en clair (mode prof).
"""

from __future__ import annotations

import re
import sqlite3

from services.latex_rendu_atome import (
    Atome,
    charger_atome,
    detecter_options_paquet,
    detecter_paquets_tex_manquants,
    generer_corps_fiche,
    generer_corps_methode,
    generer_corps_notion,
)
from services.preambule_atome import construire_preambule
from services.paquet_parseur import extraire_utilisations
from services.v2_lecture import lire_sequence_par_niveau
# v0.11.2 — On réutilise la version « continue » du corps d'exercice de
# livret_recap_exos qui produit juste le \begin{seqExercice}...\end{seqExercice}
# (sans seqSerieExos ni seqInitCorriges autour), adapté pour l'agrégation.
# Variables et bloc sont retournés séparément : les variables doivent être
# émises AVANT seqSerieExos (les groupes ouverts par tcolorbox/multicols
# rendent les définitions \newcommand locales).
from services.livret_recap_exos import _generer_corps_exercice_continu
# v0.11.2 — _echapper de livret_recap_cours sert à insérer le nom de
# séquence dans le titre LaTeX (pass-through, ne touche pas aux \ et &
# parce que les noms peuvent contenir du LaTeX intentionnel comme \ieme).
from services.livret_recap_cours import _echapper as _echapper_titre


# ── Conventions séries (alignées sur livret_recap_exos) ──────────────────────

# Mapping serie_code (BDD) → numéro pour seqSerieExos.
# Le paquet attend : 0 = Révisions, 1 = Fondamentale, 2 = Avancée, 3 = Exploration.
# Pour les Activités d'approche (AE), on les mappe vers 0 ('Révisions') —
# convention héritée, voir livret_recap_exos.py.
_NUM_SERIE_PAR_CODE = {
    'R':  0,    # révisions issues de partie_exos_revision_approche
    'AE': 0,    # activités d'approche, sémantiquement révisions
    'F':  1,
    'A':  2,
    'E':  3,
}

# Libellés français pour les sous-titres internes.
LIBELLES_SERIES = {
    'R':  'Révisions',
    'AE': "Activités d'approche",
    'F':  'Série fondamentale',
    'A':  'Série avancée',
    'E':  'Série exploration',
}

# v0.13.1 — Le mapping `_NOM_COURT_NIVEAU` historique a été supprimé.
# Le nom court LaTeX d'un niveau (ex. '5\\ieme' pour N10) est désormais
# obtenu via `services.param_niveaux.lire_nom_court_latex(conn, code)`,
# qui lit la table BDD `param_niveaux` (peuplée à partir de
# `data/param_niveaux.csv`) et applique la conversion 'Xème' → 'X\\ieme'.


# ── Validation et défauts d'options ─────────────────────────────────────────

def options_par_defaut() -> dict:
    """Retourne le dict d'options avec tous les toggles activés (livret
    « tout en un » historique)."""
    return {
        "cours": {
            "inclure": True,
            "fiches_resume": {"inclure": True, "a_completer": True},
        },
        "exercices": {
            "inclure": True,
            "serie_A": True,
        },
    }


def normaliser_options(options: dict | None) -> dict:
    """Fusionne les options fournies avec les valeurs par défaut. Une
    option absente est traitée comme True (toggle actif). Permet aux
    appelants de ne fournir que les toggles à désactiver.

    NB : la structure attendue est nestée — si `options['cours']` est
    absent, on prend le bloc cours par défaut entier. Si `options['cours']`
    est présent mais `options['cours']['fiches_resume']` est absent, on
    prend les défauts du bloc fiches_resume.

    v0.13.6.5.1 : accepte aussi le format plat utilisé par le catalogue
    des documents publiables (cf. services/referentiel_documents.py),
    pour éviter une couche de conversion intermédiaire. Détection sur
    la présence d'une des clés plates `contenu`, `inclure_fiches_resume_en_fin`,
    `inclure_enonces_serie_a`. Conversion en interne vers le format
    imbriqué attendu par le reste du code.
    """
    base = options_par_defaut()
    if not options:
        return base
    if _est_format_plat(options):
        options = _plat_vers_imbrique(options)
    cours = options.get("cours", {}) or {}
    if not isinstance(cours, dict):
        cours = {}
    fiches = cours.get("fiches_resume", {}) or {}
    if not isinstance(fiches, dict):
        fiches = {}
    exos = options.get("exercices", {}) or {}
    if not isinstance(exos, dict):
        exos = {}
    return {
        "cours": {
            "inclure": bool(cours.get("inclure", True)),
            "fiches_resume": {
                "inclure": bool(fiches.get("inclure", True)),
                "a_completer": bool(fiches.get("a_completer", True)),
            },
        },
        "exercices": {
            "inclure": bool(exos.get("inclure", True)),
            "serie_A": bool(exos.get("serie_A", True)),
        },
    }


def _est_format_plat(options: dict) -> bool:
    """Détecte si `options` est au format plat (catalogue documents)
    plutôt qu'au format imbriqué historique.

    Heuristique : présence d'au moins une clé plate connue.
    """
    cles_plates = {
        'contenu', 'inclure_fiches_resume_en_fin',
        'inclure_enonces_serie_a', 'inclure_plan_travail_en_tete',
        'actif',
    }
    return any(k in options for k in cles_plates)


def _plat_vers_imbrique(plat: dict) -> dict:
    """Convertit le dict d'options plat (catalogue) vers le format
    imbriqué qu'attend le reste du module.

    Mapping :
      - `contenu` ∈ {cours_seul, exercices_seul, cours_et_exercices}
        → `cours.inclure` et `exercices.inclure`
      - `inclure_fiches_resume_en_fin` ∈ {non, completes, a_completer}
        → `cours.fiches_resume.inclure` et `.a_completer`
      - `inclure_enonces_serie_a` → `exercices.serie_A`

    Les options additionnelles du catalogue (`inclure_plan_travail_en_tete`,
    `inclure_corriges_serie_*`, `inclure_corriges_remediation`) sont
    ignorées par cette session. Elles seront prises en compte quand
    `generer_livret_sequence` sera étendu pour les exploiter.
    """
    contenu = plat.get('contenu', 'cours_et_exercices')
    cours_inclus = contenu in ('cours_seul', 'cours_et_exercices')
    exos_inclus = contenu in ('exercices_seul', 'cours_et_exercices')

    fiches_choix = plat.get('inclure_fiches_resume_en_fin', 'non')
    fiches_inclues = fiches_choix in ('completes', 'a_completer')
    fiches_a_completer = (fiches_choix == 'a_completer')

    return {
        "cours": {
            "inclure": cours_inclus,
            "fiches_resume": {
                "inclure": fiches_inclues,
                "a_completer": fiches_a_completer,
            },
        },
        "exercices": {
            "inclure": exos_inclus,
            "serie_A": bool(plat.get('inclure_enonces_serie_a', True)),
        },
    }


def valider_options(options: dict) -> None:
    """Vérifie l'invariant métier : au moins un des deux blocs principaux
    (cours ou exercices) doit être actif. Un livret sans cours ni exercices
    serait vide et n'a pas de sens — on lève ValueError plutôt que de
    générer un .tex avec juste la boîte de titre.

    L'argument est supposé être déjà passé par normaliser_options().
    """
    if not options["cours"]["inclure"] and not options["exercices"]["inclure"]:
        raise ValueError(
            "Au moins un des deux blocs principaux (cours ou exercices) "
            "doit être inclus dans le livret."
        )


# ── Lecture des atomes liés à la séquence ────────────────────────────────────

def _lire_notions_de_sequence(conn: sqlite3.Connection,
                               niveau: str,
                               sequence: str) -> list[str]:
    """Retourne les ids de notions de la séquence, dédupliqués et triés
    par leur numéro de connaissance (puis titre pour stabilité).

    Les notions sont collectées via objectif_notions (jointure avec
    objectifs pour ne garder que celles des objectifs de la
    séquence-niveau). Une notion peut être liée à plusieurs objectifs ;
    on la prend une seule fois.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT n.id        AS id,
               n.num_connaissance   AS num_c,
               n.titre              AS titre
        FROM notions n
        JOIN objectif_notions onv ON onv.notion_id = n.id
        JOIN objectifs obv     ON obv.id = onv.objectif_id
        JOIN sequence_parties sp  ON sp.id = obv.partie_id
        JOIN sequences_par_niveau sn ON sn.id = sp.sequence_par_niveau_id
        WHERE sn.niveau = ? AND sn.sequence_code = ?
        ORDER BY
          CASE WHEN n.num_connaissance IS NULL OR n.num_connaissance = ''
               THEN 1 ELSE 0 END,
          n.num_connaissance,
          n.titre
        """,
        (niveau, sequence),
    ).fetchall()
    return [r["id"] for r in rows]


def _lire_methodes_de_sequence(conn: sqlite3.Connection,
                                niveau: str,
                                sequence: str) -> list[str]:
    """Retourne les ids de méthodes de la séquence, triées par num_methode.

    v0.11.2 — Stratégie tolérante : on prend les méthodes qui ont
    niveau+sequence dénormalisés correspondants, indépendamment de la
    liaison objectifs.methode_id. Cette liaison peut être absente en
    pratique (cas rencontré chez Laurent N10/S01 : méthodes en BDD mais
    aucun objectif ne pointe vers elles). Comme les méthodes sont créées
    en étant rattachées à une (niveau, sequence), le filtrage dénormalisé
    est plus robuste.

    Si plus tard les méthodes sont correctement liées via methode_id, le
    résultat est identique : on retourne l'union des deux ensembles, mais
    en pratique l'ensemble dénormalisé contient déjà l'autre.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT m.id          AS id,
               m.num_methode          AS num,
               m.num_objectif         AS num_obj,
               m.titre                AS titre
        FROM methodes m
        WHERE m.niveau = ? AND m.sequence = ?
        ORDER BY
          CASE WHEN m.num_methode IS NULL THEN 1 ELSE 0 END,
          m.num_methode,
          m.num_objectif,
          m.titre
        """,
        (niveau, sequence),
    ).fetchall()
    return [r["id"] for r in rows]


def _lire_fiches_de_sequence(conn: sqlite3.Connection,
                              niveau: str,
                              sequence: str) -> list[str]:
    """Retourne les ids de fiches de résumé de la séquence, triées par
    num_fiche. La FK objectif_id sur objectifs permet le filtrage
    par séquence, mais on s'appuie sur les colonnes dénormalisées
    fiches_resume.niveau / .sequence pour rester simple.
    """
    rows = conn.execute(
        """
        SELECT id
        FROM fiches_resume
        WHERE niveau = ? AND sequence = ?
        ORDER BY
          CASE WHEN num_fiche IS NULL THEN 1 ELSE 0 END,
          num_fiche,
          titre
        """,
        (niveau, sequence),
    ).fetchall()
    return [r["id"] for r in rows]


# ── Génération du corps des atomes (versions « continues ») ──────────────────

# Ces patterns suppriment les \setcounter locaux qu'émettent generer_corps_notion
# et generer_corps_methode (cf. livret_recap_cours.py pour la justification :
# numérotation continue à l'échelle du livret).
_RE_SETCOUNTER_NOTION  = re.compile(r'\\setcounter\{NotionNum\}\{[^}]*\}\s*\n?')
_RE_SETCOUNTER_METHODE = re.compile(r'\\setcounter\{MethodeNum\}\{[^}]*\}\s*\n?')


def _generer_corps_notion_continu(atome: Atome) -> str:
    """Comme generer_corps_notion mais sans \\setcounter local et sans
    cycle init/affiche annexes (le livret en a un global)."""
    tex = generer_corps_notion(atome, inclure_init_annexes=False)
    return _RE_SETCOUNTER_NOTION.sub('', tex)


def _generer_corps_methode_continu(atome: Atome) -> str:
    """Comme generer_corps_methode mais sans \\setcounter local et sans
    cycle init/affiche annexes."""
    tex = generer_corps_methode(atome, inclure_init_annexes=False)
    return _RE_SETCOUNTER_METHODE.sub('', tex)


# ── v0.11.3 — Génération des tableaux Prérequis et Objectifs depuis BDD ─────
#
# Historique : le paquet seqenseigne fournissait \seqRenduTableauPrerequis et
# \seqRenduTableauObjectifs qui s'appuyaient sur les fichiers .dbtex du
# référentiel. En mode atomique (génération depuis la BDD), ces macros sont
# marquées STATUT_IGNORE dans paquet_regles_atome.py — on doit donc inliner
# directement le tableau LaTeX, en lisant les données depuis la BDD.
#
# Pour Prérequis : on parcourt les précédences (table
# sequence_par_niveau_precedences), et pour chaque séquence prérequise on
# liste les libellés de ses objectifs (objectifs.nom). Affichage groupé
# par séquence prérequise.
#
# Pour Objectifs : on parcourt les parties → objectifs de la séquence
# courante, et on émet un tableau avec colonnes
# Objectif | À consolider (=critere_F) | Satisfaisant (=critere_A) | Très bon (=critere_E).
# Mapping critères → niveaux de maîtrise validé v0.11.3 :
#   critere_F → "À consolider"   (niveau de base)
#   critere_A → "Satisfaisant"   (niveau attendu)
#   critere_E → "Très bon"       (niveau d'expertise)


def _echapper_simple(s: str) -> str:
    """Échappement minimaliste pour insertion dans une cellule tabularray.
    On ne touche PAS aux \\ et { } parce que les libellés peuvent contenir
    intentionnellement du LaTeX (ex : \\ieme, $x^2$, etc.). On échappe
    seulement les & qui briseraient le tableau, et on protège les # rares.
    """
    if not s:
        return ""
    return s.replace("&", r"\&").replace("#", r"\#").replace("%", r"\%")


def _lire_nom_court_latex_local(conn: sqlite3.Connection, niveau: str) -> str:
    """Wrapper local autour de `services.param_niveaux.lire_nom_court_latex`.

    Existe uniquement pour différer l'import (éviter un import en tête de
    module qui créerait une dépendance cyclique potentielle si jamais
    `param_niveaux` venait à importer du contenu de ce module).

    Substitue l'ancien `_NOM_COURT_NIVEAU.get(niveau, niveau)` (v0.13.1).
    """
    from services.param_niveaux import lire_nom_court_latex
    return lire_nom_court_latex(conn, niveau)


def _lire_objectifs_de_sequence(conn: sqlite3.Connection,
                                 niveau: str,
                                 sequence: str) -> list[dict]:
    """Retourne la liste ordonnée des objectifs d'une séquence-niveau,
    avec le numéro de partie et le code d'objectif pour le tri.

    Format de retour : [{partie_numero, code, nom, critere_F, critere_A,
    critere_E}, ...]
    """
    rows = conn.execute(
        """
        SELECT sp.numero    AS partie_numero,
               ov.code      AS code,
               ov.nom       AS nom,
               ov.critere_F AS critere_F,
               ov.critere_A AS critere_A,
               ov.critere_E AS critere_E
        FROM sequences_par_niveau sn
        JOIN sequence_parties sp ON sp.sequence_par_niveau_id = sn.id
        JOIN objectifs ov ON ov.partie_id = sp.id
        WHERE sn.niveau = ? AND sn.sequence_code = ?
        ORDER BY sp.numero, ov.code
        """,
        (niveau, sequence),
    ).fetchall()
    return [
        {
            "partie_numero": r["partie_numero"],
            "code":          r["code"] or "",
            "nom":           r["nom"] or "",
            "critere_F":     r["critere_F"] or "",
            "critere_A":     r["critere_A"] or "",
            "critere_E":     r["critere_E"] or "",
        }
        for r in rows
    ]


def _lire_objectifs_dune_sequence_pour_prerequis(
        conn: sqlite3.Connection,
        precedent_niveau: str,
        precedent_seq: str,
) -> list[dict]:
    """Pour les prérequis : retourne la liste des libellés d'objectifs
    d'une séquence référencée comme précédence. On ne récupère que ce
    qu'il faut afficher (partie_numero, code, nom).

    v0.13.3 — Fallback sur les CSV des cycles si la séquence prérequise
    n'est pas peuplée dans la BDD applicative. Cas typique : N09/S01
    référencé depuis N10/S01 alors que N09 (cycle 3) n'a jamais été
    importé en BDD applicative — les objectifs sont disponibles dans
    `data/C03_objectifs.csv` qui est un référentiel de fait.

    Stratégie :
      1. On essaie d'abord la BDD applicative (objectifs). Si la
         séquence y est, on retourne ses objectifs (cas standard, C04).
      2. Sinon, on charge le CSV correspondant au cycle du niveau
         précédent (C03 pour N07/N08/N09, C04 pour N10/N11/N12) et on
         filtre par (niveau, séquence).

    Retourne [] uniquement si NI la BDD NI le CSV n'ont d'objectif.
    """
    # ── 1. Essai BDD applicative (cas C04 standard) ───────────────────────
    rows = conn.execute(
        """
        SELECT sp.numero AS partie_numero,
               ov.code   AS code,
               ov.nom    AS nom
        FROM sequences_par_niveau sn
        JOIN sequence_parties sp ON sp.sequence_par_niveau_id = sn.id
        JOIN objectifs ov ON ov.partie_id = sp.id
        WHERE sn.niveau = ? AND sn.sequence_code = ?
        ORDER BY sp.numero, ov.code
        """,
        (precedent_niveau, precedent_seq),
    ).fetchall()
    if rows:
        return [
            {
                "partie_numero": r["partie_numero"],
                "code":          r["code"] or "",
                "nom":           r["nom"] or "",
            }
            for r in rows
        ]

    # ── 2. Fallback CSV (typiquement pour N09/N08/N07 = cycle 3) ──────────
    # On infère le dossier `data/` à partir du chemin du fichier BDD,
    # puis on lit le CSV approprié au cycle. Solution sans dépendance
    # à Flask (le service doit rester utilisable hors contexte web).
    return _lire_objectifs_prerequis_depuis_csv(
        conn, precedent_niveau, precedent_seq,
    )


def _lire_objectifs_prerequis_depuis_csv(
        conn: sqlite3.Connection,
        precedent_niveau: str,
        precedent_seq: str,
) -> list[dict]:
    """Fallback : charge les objectifs d'une séquence depuis le CSV de
    son cycle (C03_objectifs.csv ou C04_objectifs.csv selon le niveau).

    Retourne [] si :
      - le niveau est inconnu de `param_niveaux`
      - le CSV correspondant au cycle n'existe pas dans `data/`
      - aucun objectif n'est trouvé pour (niveau, séquence)
    """
    # Déterminer le cycle du niveau prérequis
    from services.param_niveaux import lire_cycle, NiveauInconnu
    try:
        cycle = lire_cycle(conn, precedent_niveau)
    except NiveauInconnu:
        return []

    # Inférer le dossier data/ depuis le chemin de la BDD ouverte
    # (PRAGMA database_list retourne (seq, name, file) pour chaque BDD attachée).
    from pathlib import Path
    db_path = None
    for row in conn.execute("PRAGMA database_list"):
        # row[1] = 'main', row[2] = chemin du fichier
        if row[1] == "main" and row[2]:
            db_path = Path(row[2])
            break
    if db_path is None or not db_path.is_file():
        return []
    data_dir = db_path.parent

    # Charger le CSV via CsvStore (logique de lecture déjà partagée)
    from persistence.csv_store import CsvStore
    cs = CsvStore(data_dir)
    nom_csv = f"{cycle}_objectifs.csv"
    csv_path = data_dir / nom_csv
    if not csv_path.is_file():
        return []

    # CsvStore expose lire_c03_objectifs / lire_c04_objectifs ; on prend
    # celui qui correspond au cycle. Si le cycle n'est ni C03 ni C04,
    # on ne sait pas faire (cas non observé en pratique).
    if cycle == "C03":
        objs_csv = cs.lire_c03_objectifs()
    elif cycle == "C04":
        objs_csv = cs.lire_c04_objectifs()
    else:
        return []

    # Filtrer par (niveau, séquence) et trier par code
    items = [
        (code, attrs)
        for (niv, seq, code), attrs in objs_csv.items()
        if niv == precedent_niveau and seq == precedent_seq
    ]
    items.sort(key=lambda t: t[0])

    # Format de retour identique à celui de la BDD : on ne dispose pas
    # du partie_numero dans le CSV (la notion de partie n'existe pas
    # dans le modèle CSV historique). On émet partie_numero=0 par
    # défaut, ce qui n'a pas d'incidence sur le rendu (les blocs
    # Prérequis trient par code uniquement, pas par partie).
    return [
        {
            "partie_numero": 0,
            "code":          code,
            "nom":           attrs.get("nom", ""),
        }
        for code, attrs in items
    ]


def _lire_nom_sequence_du_cycle(conn: sqlite3.Connection,
                                  niveau: str,
                                  sequence: str) -> tuple[int | None, str]:
    """Retourne (numero, nom) de la séquence du cycle correspondant à
    (niveau, sequence).

    v0.13.1 : la résolution niveau → cycle se fait via la table BDD
    `param_niveaux` (lire le helper `services.param_niveaux.lire_cycle`),
    qui remplace les anciens dicts hardcodés `_CYCLE_PAR_NIVEAU`.

    Si le niveau n'est pas dans `param_niveaux` ou si la séquence du
    cycle correspondant est introuvable : retourne (None, "").
    Robuste : ne lève pas, c'est un cas légitime (séquence non
    référencée pour ce niveau).
    """
    from services.param_niveaux import lire_cycle, NiveauInconnu
    try:
        cycle = lire_cycle(conn, niveau)
    except NiveauInconnu:
        return (None, "")
    row = conn.execute(
        """
        SELECT numero, nom
        FROM sequences_du_cycle
        WHERE cycle_code = ? AND code = ?
        """,
        (cycle, sequence),
    ).fetchone()
    if not row:
        return (None, "")
    return (row["numero"], row["nom"] or "")


def _generer_tableau_prerequis(conn: sqlite3.Connection,
                                niveau: str,
                                sequence_code: str,
                                precedences: list[dict]) -> str:
    """Produit le bloc LaTeX « Prérequis » à inliner après la boîte de titre.

    Format (v0.11.3) : groupé par séquence de précédence. Pour chaque
    précédence, un sous-titre indique « Séquence S01 — Représentations
    d'un nombre (5ème) » puis la liste des libellés d'objectifs.

    v0.13.3 — Si une précédence pointe vers une séquence absente de la
    BDD applicative (cas typique : N09 non importé), on tente un
    fallback CSV (cf. _lire_objectifs_dune_sequence_pour_prerequis).
    Le bloc Prérequis n'est silencieusement omis que si NI la BDD NI
    le CSV n'a d'objectifs pour aucune des précédences.
    """
    if not precedences:
        return ""

    # Pour chaque précédence : nom + numéro de la séquence prérequise +
    # liste de ses objectifs.
    blocs: list[tuple[str, str, list[dict]]] = []
    # (titre_seq, niveau_court, objectifs)
    for prec in precedences:
        prec_niveau = prec.get("precedent_niveau") or ""
        prec_seq    = prec.get("precedent_seq") or ""
        if not prec_niveau or not prec_seq:
            continue
        objs = _lire_objectifs_dune_sequence_pour_prerequis(
            conn, prec_niveau, prec_seq,
        )
        if not objs:
            # Séquence référencée mais aucun objectif trouvé (ni en BDD,
            # ni en CSV de fallback). On n'affiche rien pour cette
            # précédence.
            continue
        num, nom = _lire_nom_sequence_du_cycle(conn, prec_niveau, prec_seq)
        nom_court = _lire_nom_court_latex_local(conn, prec_niveau)
        if num is not None:
            titre = f"Séquence {num:02d} — {nom}"
        else:
            titre = f"{prec_seq} — {nom}" if nom else prec_seq
        blocs.append((titre, nom_court, objs))

    if not blocs:
        return ""

    L: list[str] = []
    # v0.13.2 — Le bloc Prérequis est désormais émis via la commande
    # `\seqRenduTableauPrerequis{...}` du paquet seqenseigne-theme. La
    # commande encapsule le contenu dans une boîte tcolorbox dédiée
    # avec le titre « Prérequis » et les couleurs du thème courant.
    # Le titre de section `\seqTitreSection{Prérequis}` n'est plus émis
    # (porté par la boîte elle-même).
    L.append(r"%% Prérequis générés depuis la BDD (v0.11.3) — remplace "
             r"\seqRenduTableauPrerequis du paquet legacy.")
    L.append(r"%% v0.13.2 — Émis comme argument de la commande paquet "
             r"\seqRenduTableauPrerequis (boîte tcolorbox avec titre).")
    L.append(r"\seqRenduTableauPrerequis{%")
    for titre, niveau_court, objs in blocs:
        L.append(r"\subsection*{" + _echapper_simple(titre)
                 + " \\hfill {\\normalsize\\itshape "
                 + _echapper_simple(niveau_court) + "}}")
        L.append(r"\begin{itemize}[leftmargin=*,nosep]")
        for o in objs:
            code = o["code"]
            nom  = o["nom"]
            ligne = (f"\\textbf{{{_echapper_simple(code)}.}} "
                     if code else "")
            ligne += _echapper_simple(nom)
            L.append(r"  \item " + ligne)
        L.append(r"\end{itemize}")
        L.append("")
    L.append(r"}")
    return "\n".join(L)


def _generer_tableau_objectifs(conn: sqlite3.Connection,
                                niveau: str,
                                sequence_code: str) -> str:
    """Produit le bloc LaTeX « Objectifs » à inliner après les Prérequis.

    Format (v0.11.3) : un tableau tabularray avec 4 colonnes :
        Objectif | À consolider | Satisfaisant | Très bon
    soit, en termes de critères saisis :
        nom      | critere_F     | critere_A    | critere_E

    On regroupe par partie (sous-titre) si la séquence en a plusieurs,
    sinon on rend un tableau unique. Si aucun objectif n'a de critère
    saisi, on n'affiche pas la table — c'est le cas où ça n'apporterait
    rien à l'élève.
    """
    objs = _lire_objectifs_de_sequence(conn, niveau, sequence_code)
    if not objs:
        return ""

    # On n'affiche le tableau que s'il y a au moins un objectif avec au
    # moins un critère renseigné. Sinon le tableau serait vide et inutile.
    if not any(o["critere_F"] or o["critere_A"] or o["critere_E"] for o in objs):
        return ""

    L: list[str] = []
    # v0.13.2 — Le tableau d'objectifs est désormais émis via la commande
    # `\seqRenduTableauObjectifs{...}` du paquet seqenseigne-theme. La
    # commande encapsule les lignes dans une boîte tcolorbox avec
    # le titre « Objectifs », gère elle-même le tabularx (via la clé
    # tcolorbox `tabularx*={}{X|X|X|X}`) et insère un en-tête à 2
    # niveaux fixe (« Niveau de maîtrise » couvrant les 3 colonnes
    # critères, puis « À consolider | Satisfaisant | Très bien »).
    #
    # Côté Python, on n'émet plus que les lignes de données :
    #   Objectif & critère_F & critère_A & critère_E \\\hline
    # La dernière ligne ne porte PAS de \hline final (sinon trait
    # redondant avec la frame de la boîte).
    L.append(r"%% Objectifs générés depuis la BDD (v0.11.3) — remplace "
             r"\seqRenduTableauObjectifs du paquet legacy.")
    L.append(r"%% v0.13.2 — Émis comme argument de la commande paquet "
             r"\seqRenduTableauObjectifs (boîte tcolorbox + tabularx intégré).")
    # Construire les lignes (séparées par \\\hline sauf la dernière)
    lignes_data: list[str] = []
    for o in objs:
        code = o["code"]
        nom  = o["nom"]
        cf, ca, ce = o["critere_F"], o["critere_A"], o["critere_E"]
        prefixe = f"\\textbf{{{_echapper_simple(code)}.}} " if code else ""
        cellule_obj = prefixe + _echapper_simple(nom)
        lignes_data.append(
            cellule_obj + " & "
            + _echapper_simple(cf) + " & "
            + _echapper_simple(ca) + " & "
            + _echapper_simple(ce)
        )
    # Joindre avec \\\hline entre lignes (pas après la dernière, pour
    # éviter un trait redondant avec la frame de la boîte tcolorbox).
    contenu_tableau = " \\\\\\hline\n  ".join(lignes_data)
    L.append(r"\seqRenduTableauObjectifs{%")
    L.append("  " + contenu_tableau)
    L.append(r"}")
    return "\n".join(L)


# ── Génération principale ────────────────────────────────────────────────────

def generer_livret_sequence(conn: sqlite3.Connection,
                              niveau: str,
                              sequence_code: str,
                              options: dict | None = None,
                              tikz_libraries: list[str] | None = None,
                              tblr_libraries: list[str] | None = None) -> str:
    """Génère le source .tex complet du livret pour une séquence.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion à la BDD.
    niveau : str
        Code niveau ('N09'..'N12').
    sequence_code : str
        Code séquence ('S01'..'S14').
    options : dict, optional
        Toggles d'inclusion. Cf. options_par_defaut() et normaliser_options().
        Si None, livret « tout en un » par défaut.
    tikz_libraries, tblr_libraries : list[str], optional
        Bibliothèques à charger inconditionnellement (transmises à
        construire_preambule).

    Returns
    -------
    str
        Source .tex complet.
    """
    opts = normaliser_options(options)
    valider_options(opts)

    # ── 1. Charger la structure v2 de la séquence ───────────────────────────
    data = lire_sequence_par_niveau(conn, niveau, sequence_code)
    sn = data["sequence_par_niveau"]
    parties = data["parties"]
    seq_nom = sn.get("sequence_nom") or ""
    seq_num = sn.get("sequence_numero")
    theme_code_couleur = sn.get("theme_code_couleur") or ""

    # ── 2. Pré-calcul des atomes inclus selon les toggles ──────────────────

    # Cours : notions et méthodes
    notions_tex: list[tuple[str, str]] = []   # (atome_titre, tex_corps)
    methodes_tex: list[tuple[str, str]] = []
    if opts["cours"]["inclure"]:
        for nid in _lire_notions_de_sequence(conn, niveau, sequence_code):
            atome = charger_atome(conn, "notion", nid)
            notions_tex.append((atome.titre, _generer_corps_notion_continu(atome)))
        for mid in _lire_methodes_de_sequence(conn, niveau, sequence_code):
            atome = charger_atome(conn, "methode", mid)
            methodes_tex.append((atome.titre, _generer_corps_methode_continu(atome)))

    # v0.11.6 — Détection et accumulation de la remédiation.
    # On note les exos qui ont une remédiation non vide pour pouvoir
    # décider en fin de fonction d'émettre \seqInitRemediation (en tête)
    # et \seqAfficheRemediations + \seqAfficheCorrigesRemediation (en
    # fin). Si aucun exo de la séquence n'a de remédiation, on n'émet
    # rien — le PDF reste épuré.
    a_au_moins_une_remediation = False

    def _atome_a_remediation(atome) -> bool:
        return bool(
            (getattr(atome, 'remed_enonce', '') or '').strip()
            or (getattr(atome, 'remed_corrige', '') or '').strip()
        )

    # Exercices : par série, en partant des objectifs des parties.
    # On organise par série pour le livret (pas par partie/objectif),
    # cf. décision de cadrage v0.11.2.
    # Chaque entrée est un tuple (variables, bloc_seqExercice) :
    # les variables doivent être émises AU NIVEAU TOP du document (avant
    # le \begin{seqSerieExos} qui ouvre des groupes multicols+tcolorbox
    # rendant les \newcommand locales). Cf. livret_recap_exos pour le détail.
    exos_par_serie: dict[str, list[tuple[str, str]]] = {
        "R": [], "AE": [], "F": [], "A": [], "E": [],
    }
    if opts["exercices"]["inclure"]:
        # Révisions : exos extraits de partie_exos_revision_approche (R + EA).
        # On agrège l'ordre par partie puis par ordre dans la partie.
        ids_vus: set[str] = set()
        for partie in parties:
            era = partie.get("exos_revision_approche", {}) or {}
            for typ in ("R", "EA"):
                for entry in era.get(typ, []):
                    ex_id = entry.get("exercice_id")
                    if not ex_id or ex_id in ids_vus:
                        continue
                    ids_vus.add(ex_id)
                    atome = charger_atome(conn, "exercice", ex_id)
                    if _atome_a_remediation(atome):
                        a_au_moins_une_remediation = True
                    exos_par_serie["R"].append(
                        _generer_corps_exercice_continu(
                            atome, inclure_remediation=True, conn=conn))

        # Séries pédagogiques : EA, F, (A si activé), E.
        # On prend les exos liés via objectif_exos (objectif → série).
        # AE est mappée comme "AE" en BDD mais "EA" dans v2_lecture.
        ids_par_serie: dict[str, set[str]] = {"AE": set(), "F": set(), "A": set(), "E": set()}
        for partie in parties:
            for obj in partie.get("objectifs", []):
                eps = obj.get("exos_par_serie", {}) or {}
                # eps a les clés EA, F, A, E (cf. SERIES_V2 post-3-light).
                # On mappe EA → AE pour l'ordre d'affichage du paquet.
                for serie_v2, mots in (("EA", "AE"), ("F", "F"), ("A", "A"), ("E", "E")):
                    for entry in eps.get(serie_v2, []):
                        ex_id = entry.get("exercice_id")
                        if ex_id:
                            ids_par_serie[mots].add(ex_id)

        # Toggle série A
        if not opts["exercices"]["serie_A"]:
            ids_par_serie["A"] = set()

        # Charger les corps des exos pour les séries ouvertes
        for code in ("AE", "F", "A", "E"):
            for ex_id in sorted(ids_par_serie[code]):
                if ex_id in ids_vus:
                    # déjà inclus en révision — ne pas dupliquer
                    continue
                atome = charger_atome(conn, "exercice", ex_id)
                if _atome_a_remediation(atome):
                    a_au_moins_une_remediation = True
                exos_par_serie[code].append(
                    _generer_corps_exercice_continu(
                        atome, inclure_remediation=True, conn=conn))

    # Fiches de résumé
    fiches_tex: list[tuple[str, str]] = []   # (titre, tex_corps)
    if opts["cours"]["inclure"] and opts["cours"]["fiches_resume"]["inclure"]:
        for fid in _lire_fiches_de_sequence(conn, niveau, sequence_code):
            atome = charger_atome(conn, "fiche", fid)
            fiches_tex.append((atome.titre or atome.objectif_nom, generer_corps_fiche(atome)))

    # ── 3. Préambule sur mesure ────────────────────────────────────────────

    # On agrège tous les textes pour analyse macros/envs.
    tous_textes = []
    for _, t in notions_tex:  tous_textes.append(t)
    for _, t in methodes_tex: tous_textes.append(t)
    for serie_exos in exos_par_serie.values():
        # Chaque entrée est un tuple (variables, bloc) — on agrège les deux.
        for variables, bloc in serie_exos:
            if variables:
                tous_textes.append(variables)
            tous_textes.append(bloc)
    for _, t in fiches_tex:   tous_textes.append(t)

    # Macros et environnements émis par le squelette du livret lui-même
    # (en plus des corps d'atomes). Sans cet ajout, `construire_preambule`
    # n'inlinerait pas les définitions de \seqTitreLivret, \seqTitreSection,
    # \seqAfficheCorriges, \seqInitAnnexes, etc., et la compilation
    # planterait avec « Undefined control sequence ».
    #
    # NB : cette liste doit rester synchronisée avec les macros que
    # generer_livret_sequence émet effectivement (cf. assemblage du .tex
    # plus bas). On peut sans risque inclure des macros qui ne seraient
    # finalement pas émises (selon les toggles) — `construire_preambule`
    # se contentera d'inliner leur définition, ce qui est gratuit.
    fragment_squelette_livret = r"""
\seqCreeCompteurs
\seqSetCodeNiveau{X}\seqSetCodeSequence{X}\seqSetColorsTheme{X}
\seqInitCorriges\seqInitAnnexes\seqAfficheAnnexes\seqAfficheCorriges
\seqInitRemediation\seqAfficheRemediations\seqAfficheCorrigesRemediation
\seqRemediation{X}{X}\seqCadreReponse{1}
\seqTitreSection{X}
\seqStyleObjectifsHeader{X}
\seqRenduTableauPrerequis{X}\seqRenduTableauObjectifs{X}
\begin{seqSerieExos}{0}\end{seqSerieExos}
\begin{boiteTitreGen}{X}\end{boiteTitreGen}
"""
    tous_textes.append(fragment_squelette_livret)
    texte_global = "\n".join(tous_textes)

    macros_utilisees, envs_utilises = extraire_utilisations(texte_global)

    # Atome simulé pour réutiliser detecter_options_paquet et detecter_paquets_tex_manquants.
    # Le type 'exercice' est arbitraire (cf. recap_cours/exos qui font pareil).
    atome_global = Atome(
        id="_livret_seq_",
        type_atome="exercice",
        niveau=niveau,
        sequence=sequence_code,
        fichier="",
        corps=texte_global,
    )
    options_paquet = detecter_options_paquet(conn, atome_global)
    paquets_manquants = detecter_paquets_tex_manquants(conn, atome_global)
    # v0.11.2 — Ajout du paquet `datetime` qui fournit \newdateformat,
    # \monthname et \THEYEAR. Utilisé pour définir \datemoisannee dans la
    # boîte de titre (cf. ci-dessous). Ce paquet est normalement chargé
    # par \usepackage{seqenseigne} mais pas par construire_preambule en
    # mode atomique (économie de paquets).
    #
    # v0.13.2 — Ajout du paquet `tabularx`. Requis par la commande
    # `\seqRenduTableauObjectifs` (paquet seqenseigne-theme.dtx) qui
    # passe `tabularx*={}{X|X|X|X}` en option de son tcolorbox interne.
    # tcolorbox lit cette clé et déclenche un `\tabularx{...}` à
    # l'intérieur de la boîte. Or `\tabularx` n'apparaît jamais dans
    # le source LaTeX généré par Python — c'est tcolorbox qui le crée
    # via la clé. Du coup `extraire_utilisations` ne peut pas le
    # détecter, et la détection automatique de paquets ne charge pas
    # `tabularx`. On l'ajoute explicitement ici.
    paquets_manquants_etendus = list(dict.fromkeys(
        list(paquets_manquants) + ["datetime", "tabularx"]
    ))

    # v0.11.2 — Bibliothèques tabularray par défaut. Aligné sur
    # configuration.py 'tblr_libraries': 'booktabs,varwidth'. Sans
    # `booktabs`, les \toprule / \midrule / \bottomrule à l'intérieur
    # d'un environnement tblr font « Misplaced \noalign ». Sans
    # `varwidth`, la clé `measure=vbox` plante. Les agrégations de
    # plusieurs atomes (cas du livret de séquence) ont une probabilité
    # élevée de contenir au moins un tableau booktabs, donc on charge
    # par défaut. Le caller peut surcharger en passant une liste
    # explicite (y compris [] pour ne rien charger).
    tblr_libs_effectives = (
        tblr_libraries if tblr_libraries is not None
        else ['booktabs', 'varwidth']
    )

    preambule = construire_preambule(
        conn, "exercice",
        macros_utilisees, envs_utilises,
        options_atome=options_paquet,
        paquets_tex_supplementaires=paquets_manquants_etendus,
        tikz_libraries=tikz_libraries,
        tblr_libraries=tblr_libs_effectives,
    )

    # ── 4. Assemblage du .tex ──────────────────────────────────────────────
    L: list[str] = []
    L.append(r"%% Livret de séquence — généré pour rendu agrégé.")
    L.append(f"%% Niveau : {niveau} — Séquence : {sequence_code} — {seq_nom}")
    L.append("")
    L.append(r"\documentclass[a4paper,11pt]{article}")
    L.append("")
    L.append(preambule.texte)
    L.append("")
    L.append(r"\usepackage{titlesec}")
    L.append(r"\usepackage{fancyhdr}")
    L.append(r"\usepackage{lastpage}")
    L.append("")
    L.append(r"\geometry{vmargin=70pt,hmargin=50pt,headheight=50pt,"
             r"headsep=15pt,footskip=20pt}")
    L.append("")
    L.append(r"\pagestyle{fancy}")
    L.append(r"\fancyhf{}")
    # v0.13.3 — Suppression du trait horizontal en haut de chaque page.
    # Par défaut, fancyhdr trace une fine ligne sous l'en-tête via
    # \headrule (épaisseur 0.4pt). Laurent veut un livret sans trait
    # de séparation. Pas besoin de toucher à \footrulewidth (qui vaut
    # déjà 0pt par défaut).
    L.append(r"\renewcommand{\headrulewidth}{0pt}")
    L.append(r"\rhead{\rightmark}")
    L.append(r"\rfoot{Page \thepage/\pageref{LastPage}}")
    L.append(r"\lfoot{" + niveau + " — " + sequence_code + r"}")
    L.append("")
    # v0.11.2 — Chemin de recherche des images (\includegraphics, etc.).
    # On couvre les deux usages :
    #  1. Compilation à la main du .tex depuis la racine appli/ : on
    #     pointe vers data/images/ (où Laurent stocke ses PNG).
    #  2. Compilation via le compilateur PDF de l'appli (services/
    #     compilateur_pdf.py) : il définit TEXINPUTS pour pointer
    #     vers le dossier d'images, et \graphicspath ne casse rien
    #     (les deux mécanismes coexistent).
    # Trailing slash obligatoire dans \graphicspath, accolades
    # imbriquées par chemin.
    L.append(r"\graphicspath{{data/images/}{./images/}{./}}")
    L.append("")
    # v0.11.2 — Format de date français utilisé dans la boîte de titre.
    # Définition reproduite ici parce que \datemoisannee est normalement
    # définie côté paquet seqenseigne (probablement dans un .dbtex chargé
    # par seqLoadData), ressources qui ne sont pas tirées en mode atomique.
    # Le paquet `datetime` (qui fournit \newdateformat, \monthname, \THEYEAR)
    # est ajouté à paquets_manquants_etendus plus haut.
    L.append(r"\newdateformat{datemoisannee}{\monthname\;\THEYEAR}")
    L.append("")
    L.append(r"\begin{document}")
    L.append("")
    # Fallbacks pour \theHxxx (hyperref non chargé).
    L.append(r"\providecommand{\theHExoNum}{\theExoNum}")
    L.append(r"\providecommand{\theHNotionNum}{\theNotionNum}")
    L.append(r"\providecommand{\theHMethodeNum}{\theMethodeNum}")
    L.append("")
    # Mode prof pour les fiches (si demandé) : redéfinir \acompleter
    # pour qu'il affiche la valeur en clair au lieu d'un trait souligné.
    # Cf. cadrage Q2b — la redéfinition est globale et touche toutes les
    # fiches du livret simultanément ; c'est cohérent (un livret « élève »
    # ou un livret « prof » entier).
    if (opts["cours"]["inclure"]
            and opts["cours"]["fiches_resume"]["inclure"]
            and not opts["cours"]["fiches_resume"]["a_completer"]):
        L.append(r"%% Mode prof : \acompleter affiche la valeur en clair.")
        L.append(r"\renewcommand{\acompleter}[1]{#1}")
        L.append("")
    L.append(r"\seqCreeCompteurs")
    L.append(f"\\seqSetCodeNiveau{{{niveau}}}")
    L.append(f"\\seqSetCodeSequence{{{sequence_code}}}")
    if theme_code_couleur:
        L.append(f"\\seqSetColorsTheme{{{theme_code_couleur}}}")
    # v0.11.2 — ouverture des fichiers de corrigés et d'annexes en début de
    # document. Une seule fois pour tout le livret (la limite TeX de 16
    # \newwrite simultanés impose ce singleton). Les corps d'atomes sont
    # générés via les versions « continues » qui n'émettent ni
    # \seqInitCorriges ni \seqInitAnnexes (cf. livret_recap_*).
    L.append(r"\seqInitCorriges")
    L.append(r"\seqInitAnnexes")
    # v0.11.6 — Ouverture conditionnelle des flux de remédiation.
    # On n'émet \seqInitRemediation que si la séquence a au moins un
    # exercice avec une remédiation non vide (sinon le PDF reste épuré
    # et on évite d'ouvrir 2 \newwrite supplémentaires inutiles, dans la
    # limite des 16 simultanés autorisés par TeX).
    # Côté paquet seqenseigne ≥ 1.0.5-dev, l'absence de
    # \seqInitRemediation rend silencieuses les macros \seqRemediation,
    # \seqAfficheRemediations et \seqAfficheCorrigesRemediation, ce qui
    # nous garantit qu'un livret sans remédiation compile à l'identique
    # de v0.11.5.
    if a_au_moins_une_remediation:
        L.append(r"\seqInitRemediation")
    L.append("")

    # v0.11.2 — Boîte de titre du livret. Reproduction du contenu de
    # \seqTitreLivret du paquet, mais sans appel à cette macro (marquée
    # STATUT_IGNORE dans paquet_regles_atome.py). Trois infos paramétrées :
    #   - numéro de séquence (depuis sequences_du_cycle.numero)
    #   - nom de séquence (depuis sequences_du_cycle.nom)
    #   - nom court du niveau (en forme LaTeX, via param_niveaux helper v0.13.1)
    nom_court = _lire_nom_court_latex_local(conn, niveau)
    seq_num_str = f"{seq_num:02d}" if isinstance(seq_num, int) else (str(seq_num) if seq_num else "")
    L.append(r"%% Boîte de titre (faite à la main).")
    if seq_num_str:
        L.append(r"\begin{boiteTitreGen}{Séquence " + seq_num_str + "}")
    else:
        L.append(r"\begin{boiteTitreGen}{Séquence}")
    L.append(r"  \begin{minipage}[c][100pt][c]{\linewidth}")
    L.append(r"    \vfill \textit{Livret de séquence} \hfill")
    L.append(r"    \vfill \centering {\Huge \textbf{" + _echapper_titre(seq_nom) + r"}}")
    L.append(r"    \vfill Version de \datemoisannee\today \hfill "
             r"\textit{Classe de " + nom_court + "}")
    L.append(r"  \end{minipage}")
    L.append(r"\end{boiteTitreGen}")
    L.append("")

    # ── v0.11.3 — Bloc « Prérequis » ───────────────────────────────────────
    # Inliné depuis la BDD (table sequence_par_niveau_precedences +
    # objectifs.nom des séquences référencées). Remplace la macro
    # \seqRenduTableauPrerequis du paquet seqenseigne (marquée STATUT_IGNORE).
    # Si pas de précédence enregistrée, ou que toutes pointent vers des
    # séquences vides en BDD, le bloc est silencieusement omis.
    precedences = data.get("precedences") or []
    bloc_prereq = _generer_tableau_prerequis(
        conn, niveau, sequence_code, precedences,
    )
    if bloc_prereq:
        L.append(bloc_prereq)
        L.append("")

    # v0.13.3 — Le bloc « Objectifs » a été DÉPLACÉ ci-dessous,
    # après les Révisions/Activités d'approche (cadrage Laurent
    # v0.13.3 : ordre pédagogique modifié → Prérequis, Révisions,
    # puis Objectifs, puis Cours, puis Exos F/A/E).

    # Helper : émet un seqSerieExos pour les exos d'un code donné.
    # Variables au top-level avant \begin{seqSerieExos} (cf.
    # _generer_corps_exercice_continu : tcolorbox+multicols rendraient les
    # \newcommand locales).
    # v0.11.3 — Insertion d'un \clearpage en tête : chaque série
    # d'exercices commence sur une nouvelle page (cadrage Laurent v0.11.3).
    def _emettre_serie(code: str) -> None:
        entries = exos_par_serie.get(code, [])
        if not entries:
            return
        num_paquet = _NUM_SERIE_PAR_CODE[code]
        L.append(r"\clearpage")
        for variables, _ in entries:
            if variables:
                L.append(variables)
                L.append("")
        L.append(f"\\begin{{seqSerieExos}}{{{num_paquet}}}")
        for _, bloc in entries:
            L.append(bloc)
        L.append(r"\end{seqSerieExos}")
        L.append("")

    # ── 5. Révisions et Activités d'approche (numéro 0 du paquet) ──────────
    # Doivent venir AVANT le bloc Cours (cf. cadrage Laurent v0.11.2 :
    # ordre pédagogique = on commence par les révisions/AP, puis on
    # introduit le cours, puis on enchaîne sur les exercices F/A/E).
    if opts["exercices"]["inclure"]:
        # R et AE partagent le même numéro de série paquet (0 = Révisions)
        # mais sont stockés séparément côté Python pour faciliter la
        # désactivation indépendante future. Pour l'émission, on les
        # fusionne dans un seul \begin{seqSerieExos}{0}.
        entries_rev = exos_par_serie.get("R", []) + exos_par_serie.get("AE", [])
        if entries_rev:
            # v0.11.3 — \clearpage avant chaque série d'exercices.
            L.append(r"\clearpage")
            for variables, _ in entries_rev:
                if variables:
                    L.append(variables)
                    L.append("")
            L.append(r"\begin{seqSerieExos}{0}")
            for _, bloc in entries_rev:
                L.append(bloc)
            L.append(r"\end{seqSerieExos}")
            L.append("")

    # ── v0.11.3 / déplacé v0.13.3 — Bloc « Objectifs » ─────────────────────
    # Inliné depuis la BDD (objectifs + critère_F/A/E). Remplace la
    # macro \seqRenduTableauObjectifs du paquet (marquée STATUT_IGNORE).
    # Mapping critères → niveaux de maîtrise affichés :
    #   critere_F → "À consolider"
    #   critere_A → "Satisfaisant"
    #   critere_E → "Très bien"
    # Le bloc est omis si aucun objectif n'a de critère renseigné.
    #
    # v0.13.3 : déplacé APRÈS les Révisions/AE (cadrage Laurent : on
    # introduit la séquence par ses prérequis et révisions avant
    # d'annoncer ses objectifs concrets, puis le cours et les
    # exercices d'application).
    bloc_objs = _generer_tableau_objectifs(conn, niveau, sequence_code)
    if bloc_objs:
        L.append(bloc_objs)
        L.append("")

    # ── 6. Bloc Cours ──────────────────────────────────────────────────────
    # v0.11.6.2 — Suppression du titre « Cours » et de son \clearpage : il
    # créait un saut de page intempestif. « Connaissances » et
    # « Savoir-faire » sont désormais des \seqTitreSection (pas des
    # \subsection*), donc ils portent eux-mêmes la séparation visuelle.
    if opts["cours"]["inclure"] and (notions_tex or methodes_tex):
        if notions_tex:
            L.append(r"\clearpage")
            L.append(r"\seqTitreSection{Connaissances}")
            L.append("")
            for _, tex in notions_tex:
                L.append(tex)
                L.append("")
        if methodes_tex:
            L.append(r"\clearpage")
            L.append(r"\seqTitreSection{Savoir-faire}")
            L.append("")
            for _, tex in methodes_tex:
                L.append(tex)
                L.append("")

    # ── 7. Bloc Exercices F / A / E (après le cours) ───────────────────────
    if opts["exercices"]["inclure"]:
        # Émission des séries pédagogiques F (1), A (2), E (3) dans l'ordre.
        # Pas de \seqTitreSection{Exercices} en tête : la séparation visuelle
        # est portée par les boîtes seqSerieExos elles-mêmes (titre + couleur
        # par série). Si tu veux un titre global, l'ajouter ici.
        # _emettre_serie insère un \clearpage en tête de chaque série.
        for code in ("F", "A", "E"):
            _emettre_serie(code)

    # ── 8. Annexes et corrigés ─────────────────────────────────────────────
    # v0.11.3 — \clearpage avant les annexes (et donc avant le bloc des
    # corrigés qui suit).
    # v0.11.5 — Le patch D4 côté paquet seqenseigne.dtx a ajouté un
    # \clearpage entre chaque série de corrigés F/A/E (cf. mémoire #26
    # point 5 résolu). Donc côté appli on n'a plus rien de spécial à
    # faire — \seqAfficheCorriges fait le bon découpage.
    L.append(r"\clearpage")
    L.append(r"\seqAfficheAnnexes")
    if opts["exercices"]["inclure"] and any(exos_par_serie[c] for c in ("R", "AE", "F", "A", "E")):
        L.append(r"\clearpage")
        L.append(r"\seqAfficheCorriges")
    L.append("")

    # v0.11.6 — Sections de remédiation, à la suite des corrigés principaux.
    # Émises uniquement si au moins un exo de la séquence a une
    # remédiation (auquel cas \seqInitRemediation a été émis en début de
    # doc et les flux sont ouverts). Ordre validé v0.11.5 :
    #   \seqAfficheCorriges
    #   \seqAfficheRemediations            ← exos de remédiation
    #   \seqAfficheCorrigesRemediation     ← corrigés de remédiation
    if a_au_moins_une_remediation:
        L.append(r"\seqAfficheRemediations")
        L.append(r"\seqAfficheCorrigesRemediation")
        L.append("")

    # ── 8. Fiches de résumé en fin de livret (cleardoublepage pour découpe) ──
    if (opts["cours"]["inclure"]
            and opts["cours"]["fiches_resume"]["inclure"]
            and fiches_tex):
        L.append(r"\cleardoublepage")
        L.append(r"%% Fiches de résumé — découpables individuellement.")
        for _, tex in fiches_tex:
            L.append(tex)
            L.append(r"\cleardoublepage")
        L.append("")

    L.append(r"\end{document}")
    return "\n".join(L)
