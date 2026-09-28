"""services/v2_lecture.py — R4e1.

Lecture en lecture seule d'une séquence par niveau dans le modèle v2.

Retourne une structure hiérarchique complète et sérialisable en JSON :
    sequence_par_niveau
        └─ parties (ordonnées par numero)
             ├─ precedences (liste de {precedent_niveau, precedent_seq})
             └─ objectifs (ordonnés par code)
                  └─ exos_par_serie : { R: [...], EA: [...], F: [...], A: [...], E: [...] }

Aucune écriture. Aucune mutation. Pas d'effet de bord.

Usage typique :
    with store._conn() as conn:
        data = lire_sequence_par_niveau(conn, niveau="N11", sequence_code="S03")

Lève SequenceParNiveauIntrouvable si (niveau, sequence_code) n'existe pas
dans sequences_par_niveau.
"""

from __future__ import annotations


# v0.11.2 — Ordre pédagogique des séries d'un exercice. La série 'R' a été
# retirée : la révision est désormais une étiquette d'usage attribuée à
# l'assemblage d'une séquence (table partie_exos_revision_approche), pas
# une catégorie d'exercice. La colonne objectif_exos.serie reste TEXT mais
# les nouvelles écritures n'utiliseront plus 'R' (cf. _SERIES_VALIDES dans
# v2_edition.py). 0 lignes legacy avec serie='R' au moment du nettoyage.
# v0.18.3 — Série « approche » unifiée en 'AE' (était 'EA'). Cf. note dans
# v2_edition._SERIE_CODE_EQUIVALENT. NB : les exos approche transitent par
# partie_exos_revision_approche (rôle 'EA'), pas par objectif_exos ; cette
# clé n'est donc qu'un slot d'initialisation ici.
SERIES_V2 = ("AE", "F", "A", "E")


class V2LectureErreur(Exception):
    """Classe de base pour les erreurs de lecture v2."""
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


class SequenceParNiveauIntrouvable(V2LectureErreur):
    def __init__(self, niveau: str, sequence_code: str):
        super().__init__(
            f"Séquence par niveau introuvable : {niveau} / {sequence_code}",
            "sequence_par_niveau_introuvable",
        )
        self.niveau = niveau
        self.sequence_code = sequence_code


# ── Fonction principale ──────────────────────────────────────────────────────

def lire_sequence_par_niveau(conn, niveau: str, sequence_code: str) -> dict:
    """Retourne la structure v2 hiérarchique d'une séquence par niveau.

    Paramètres :
        conn          — connexion sqlite3 (row_factory=sqlite3.Row recommandé)
        niveau        — 'N10', 'N11' ou 'N12'
        sequence_code — 'S01'..'S14'

    Retour : dict sérialisable JSON (voir doc module).

    v0.10 : la réponse est enrichie avec
      - chaque partie a aussi `exos_revision_approche = {"R": [...], "EA": [...]}`
      - le top-level reçoit `etat_ui = {"objectif_ouvert_id": ..., "derniere_maj": ...}`
        pour permettre à l'atelier d'assemblage de retrouver son état.
    """
    sn = _charger_sequence_par_niveau(conn, niveau, sequence_code)
    if sn is None:
        raise SequenceParNiveauIntrouvable(niveau, sequence_code)

    parties = _charger_parties(conn, sn["id"], niveau, sequence_code)
    etat_ui = _charger_etat_ui(conn, sn["id"])
    precedences = _charger_precedences_sequence(conn, sn["id"])
    return {
        "sequence_par_niveau": sn,
        "parties":             parties,
        "etat_ui":             etat_ui,
        "precedences":         precedences,
    }


# ── Helpers privés ───────────────────────────────────────────────────────────

def _charger_sequence_par_niveau(conn, niveau, sequence_code):
    """Charge la séquence par niveau + enrichit avec nom et thème depuis
    sequences_du_cycle et themes. Retourne None si introuvable.

    On joint sur sequences_du_cycle.code = sequences_par_niveau.sequence_code
    sans contraindre sur cycle_code (un seul cycle par code de séquence en
    pratique — la jointure est suffisante).

    v0.16.9 — La colonne sn.etat_code (état validable) n'existe que sur les
    bases migrées. On la sélectionne seulement si présente ; sinon on retombe
    sur 'en_cours' (tolérance aux bases anciennes et aux DDL de test minimaux).
    """
    cols_spn = {r["name"] for r in conn.execute(
        "PRAGMA table_info(sequences_par_niveau)"
    ).fetchall()}
    select_etat = ("sn.etat_code AS etat_code"
                   if "etat_code" in cols_spn
                   else "'en_cours' AS etat_code")
    row = conn.execute(
        f"""
        SELECT
            sn.id                  AS id,
            sn.niveau              AS niveau,
            sn.sequence_code       AS sequence_code,
            sn.parametres          AS parametres,
            {select_etat},
            sc.nom                 AS sequence_nom,
            sc.numero              AS sequence_numero,
            th.id                  AS theme_id,
            th.code                AS theme_code,
            th.nom                 AS theme_nom,
            th.code_couleur        AS theme_code_couleur
        FROM sequences_par_niveau sn
        LEFT JOIN sequences_du_cycle sc
               ON sc.code = sn.sequence_code
        LEFT JOIN themes th
               ON th.id = sc.theme_id
        WHERE sn.niveau = ? AND sn.sequence_code = ?
        """,
        (niveau, sequence_code),
    ).fetchone()

    if row is None:
        return None

    return {
        "id":                 row["id"],
        "niveau":             row["niveau"],
        "sequence_code":      row["sequence_code"],
        "sequence_numero":    row["sequence_numero"],
        "sequence_nom":       row["sequence_nom"] or "",
        "parametres":         row["parametres"] or "",
        "etat_code":          row["etat_code"] or "en_cours",
        "theme_id":           row["theme_id"],
        "theme_code":         row["theme_code"],
        "theme_nom":          row["theme_nom"],
        "theme_code_couleur": row["theme_code_couleur"],
    }


def _charger_parties(conn, sequence_par_niveau_id,
                     niveau: str | None = None,
                     sequence_code: str | None = None):
    """Charge toutes les parties d'une séquence par niveau, ordonnées par
    numero, chacune enrichie avec ses objectifs et ses précédences.

    v0.10 : ajoute aussi `exos_revision_approche` = {"R": [...], "EA": [...]}
    pour chaque partie, alimenté par la table partie_exos_revision_approche.

    v0.12.0 : expose `nb_seances_R_AE` (séances prévues pour les exos
    Révision + Approche dans le plan de travail générique).

    v0.13.6.3.2 : ajoute `cartes` (liste des cartes d'automatisme rattachées
    à la partie, via leur méthode ou notion liée à un objectif). Pour
    rétrocompatibilité, `niveau` et `sequence_code` sont optionnels — si
    absents, `cartes` reste une liste vide (pas de KeyError, pas de
    plantage). Les helpers privés appelés ailleurs (référentiels,
    progression) qui n'ont pas le contexte niveau/séquence continuent à
    fonctionner sans modification.
    """
    # v0.12.0 — sélection défensive de la colonne nb_seances_R_AE :
    # certains tests créent une base avec un schéma minimal antérieur où
    # la colonne n'existe pas. On détecte sa présence via PRAGMA table_info
    # et on bascule sur 0 par défaut sinon.
    try:
        cols = {r["name"] for r in conn.execute(
            "PRAGMA table_info(sequence_parties)"
        ).fetchall()}
    except Exception:
        cols = set()
    expr_seances_ra = (
        "COALESCE(nb_seances_R_AE, 0) AS nb_seances_R_AE"
        if "nb_seances_R_AE" in cols else "0 AS nb_seances_R_AE"
    )
    rows = conn.execute(
        f"""
        SELECT id, numero, {expr_seances_ra}
        FROM sequence_parties
        WHERE sequence_par_niveau_id = ?
        ORDER BY numero
        """,
        (sequence_par_niveau_id,),
    ).fetchall()

    return [
        {
            "id":          r["id"],
            "numero":      r["numero"],
            "nb_seances_R_AE": r["nb_seances_R_AE"],
            "precedences": _charger_precedences(conn, r["id"]),
            "objectifs":   _charger_objectifs(conn, r["id"]),
            "exos_revision_approche": _charger_exos_revision_approche(conn, r["id"]),
            "cartes":      _charger_cartes_de_partie(
                conn, niveau, sequence_code, r["id"]
            ),
        }
        for r in rows
    ]


def _charger_cartes_de_partie(conn, niveau, sequence_code, partie_id):
    """v0.13.6.3.2 — Liste les cartes d'automatisme rattachées à une
    partie d'une séquence par niveau.

    Une carte est rattachée à une partie si elle est :
      - dans la séquence demandée (niveau + sequence_code)
      - ET liée à au moins un objectif de la partie via la table
        de liaison `objectif_cartes` (v0.13.6.13).

    Avant v0.13.6.13 : on déduisait l'appartenance d'une carte à une
    partie en passant par lien_type/lien_id (notion → objectif_notions →
    objectif → partie, ou méthode → objectifs.methode_id → objectif →
    partie). Cette logique avait deux limites : elle ne supportait pas le
    1:N côté carte, et une carte liée à une notion orpheline (sans
    objectif) restait invisible. Désormais, la jointure passe par
    `objectif_cartes` qui matérialise explicitement les liens, ce qui
    rend le code beaucoup plus simple.

    Si `niveau` ou `sequence_code` sont None (rétrocompat, helper appelé
    sans contexte), on renvoie une liste vide.

    Si la table `objectif_cartes` n'existe pas (schéma minimal antérieur
    à v0.13.6.13), on renvoie aussi une liste vide.

    Tri : par num croissant. Code affiché : 'CA<num>'.

    Forme du dict cohérente avec celle attendue par l'atelier d'assemblage
    de séquence (clés id/nom/etat_code/code/type_pedago/type_tech), à
    distinguer de `_lister_cartes_de_partie` côté atelier référentiel qui
    expose 'titre' à la place de 'nom'.
    """
    if niveau is None or sequence_code is None:
        return []
    try:
        rows = conn.execute("""
            SELECT DISTINCT c.id, c.num, c.titre, c.type_pedago, c.type_tech,
                            c.etat_code
              FROM cartes_automatisme c
              JOIN objectif_cartes oc
                ON oc.carte_id = c.id
              JOIN objectifs o
                ON o.id = oc.objectif_id
             WHERE c.niveau = ?
               AND c.sequence = ?
               AND o.partie_id = ?
          ORDER BY c.num, c.id
        """, (niveau, sequence_code, partie_id)).fetchall()
    except Exception:
        return []

    cartes = []
    for r in rows:
        num = r["num"]
        code = f"CA{int(num):02d}" if num is not None else "CA??"
        cartes.append({
            "id":          r["id"],
            "titre":       r["titre"] or "",
            "code":        code,
            "type_pedago": r["type_pedago"] or "",
            "type_tech":   r["type_tech"] or "",
            "etat_code":   r["etat_code"] or "en_cours",
        })
    return cartes


def _charger_exos_revision_approche(conn, partie_id):
    """v0.10 : charge les exos R/EA d'une partie (table
    partie_exos_revision_approche), avec métadonnées de l'exercice
    (nom, fichier, niveau, sequence, num, serie_code).

    Retourne {"R": [...], "EA": [...]} avec chaque liste triée par ordre.

    Robustesse : si la table n'existe pas (cas dans les tests qui ne
    chargent que le schéma minimal v2 antérieur à v0.10), retourne un
    résultat vide. Côté production, la table existe toujours puisque
    schema.sql la crée à l'init.
    """
    try:
        rows = conn.execute(
            """
            SELECT
                pe.type           AS type,
                pe.ordre          AS ordre,
                pe.exercice_id    AS exercice_id,
                pe.origin_niveau  AS origin_niveau,
                pe.origin_seq     AS origin_seq,
                pe.origin_serie   AS origin_serie,
                pe.origin_num     AS origin_num,
                ex.titre          AS exercice_titre,
                ex.fichier        AS exercice_fichier,
                ex.niveau         AS exercice_niveau,
                ex.sequence       AS exercice_sequence,
                ex.num            AS exercice_num,
                ex.serie_code     AS exercice_serie_code,
                ex.etat_code      AS exercice_etat_code
            FROM partie_exos_revision_approche pe
            LEFT JOIN exercices ex ON ex.id = pe.exercice_id
            WHERE pe.partie_id = ?
            ORDER BY pe.type, pe.ordre
            """,
            (partie_id,),
        ).fetchall()
    except Exception:
        return {"R": [], "EA": []}

    resultat = {"R": [], "EA": []}
    for r in rows:
        t = r["type"]
        if t not in resultat:
            continue
        resultat[t].append({
            "ordre":         r["ordre"],
            "exercice_id":   r["exercice_id"],
            "origin_niveau": r["origin_niveau"],
            "origin_seq":    r["origin_seq"],
            "origin_serie":  r["origin_serie"],
            "origin_num":    r["origin_num"],
            "exercice": {
                "titre":      r["exercice_titre"] or "",
                "fichier":    r["exercice_fichier"] or "",
                "niveau":     r["exercice_niveau"] or "",
                "sequence":   r["exercice_sequence"] or "",
                "num":        r["exercice_num"],
                "serie_code": r["exercice_serie_code"] or "",
                "etat_code":  r["exercice_etat_code"] or "en_cours",
            },
        })
    return resultat


def _charger_etat_ui(conn, sequence_par_niveau_id):
    """v0.10 : lit l'état UI persistant (objectif ouvert) pour une séquence.

    Si la table n'existe pas (cas dans certains tests qui ne chargent que
    le schéma minimal v2), retourne un état neutre. Si la ligne n'existe
    pas encore, idem.
    """
    try:
        row = conn.execute(
            """
            SELECT objectif_ouvert_id, derniere_maj
            FROM ui_etat_atelier_sequence
            WHERE sequence_par_niveau_id = ?
            """,
            (sequence_par_niveau_id,),
        ).fetchone()
    except Exception:
        # Robustesse : si la table n'existe pas (vieille base, test partiel)
        return {"objectif_ouvert_id": None, "derniere_maj": None}

    if row is None:
        return {"objectif_ouvert_id": None, "derniere_maj": None}
    return {
        "objectif_ouvert_id": row["objectif_ouvert_id"],
        "derniere_maj":       row["derniere_maj"],
    }


def _charger_precedences_sequence(conn, sequence_par_niveau_id):
    """v0.10.2 : précédences au niveau séquence-niveau.

    Robustesse : table absente (tests anciens) → liste vide.
    """
    try:
        rows = conn.execute(
            """
            SELECT precedent_niveau, precedent_seq, ordre
            FROM sequence_par_niveau_precedences
            WHERE sequence_par_niveau_id = ?
            ORDER BY ordre, precedent_niveau, precedent_seq
            """,
            (sequence_par_niveau_id,),
        ).fetchall()
    except Exception:
        return []
    return [
        {
            "precedent_niveau": r["precedent_niveau"],
            "precedent_seq":    r["precedent_seq"],
            "ordre":            r["ordre"],
        }
        for r in rows
    ]


def _charger_precedences(conn, partie_id):
    """Précédences d'une partie, triées pour un rendu stable."""
    rows = conn.execute(
        """
        SELECT precedent_niveau, precedent_seq
        FROM partie_precedences
        WHERE partie_id = ?
        ORDER BY precedent_niveau, precedent_seq
        """,
        (partie_id,),
    ).fetchall()
    return [
        {"precedent_niveau": r["precedent_niveau"],
         "precedent_seq":    r["precedent_seq"]}
        for r in rows
    ]


def _charger_objectifs(conn, partie_id):
    """Objectifs d'une partie, ordonnés par code, avec leurs exos par série.

    L'ordre par code fait que '01' < '02' < ... < '11' (comparaison de chaînes,
    qui marche ici parce que les codes sont typiquement 2 caractères
    zéro-paddés). Si des codes non numériques ou de longueur variable
    apparaissent, l'ordre reste stable mais peut ne plus être naturel — à
    revoir avec R4e3 quand l'édition des codes sera possible.

    Depuis v0.6.4, on inclut aussi `fin_cycle` (caractéristique du programme
    officiel : compétence attendue de fin de cycle) et `notions` (notions
    associées à l'objectif via objectif_notions).

    v0.12.0 : expose `nb_seances` (séances prévues pour cet objectif dans
    le plan de travail générique : explication du cours pour les codes
    01/11/21, réalisation des exercices F/A/E pour les autres).
    """
    # v0.12.0 — sélection défensive de la colonne nb_seances : voir
    # _charger_parties pour le motif.
    try:
        cols = {r["name"] for r in conn.execute(
            "PRAGMA table_info(objectifs)"
        ).fetchall()}
    except Exception:
        cols = set()
    expr_seances = (
        "COALESCE(ob.nb_seances, 0) AS nb_seances"
        if "nb_seances" in cols else "0 AS nb_seances"
    )
    rows = conn.execute(
        f"""
        SELECT
            ob.id         AS id,
            ob.code       AS code,
            ob.nom        AS nom,
            ob.methode_id AS methode_id,
            ob.critere_F  AS critere_F,
            ob.critere_A  AS critere_A,
            ob.critere_E  AS critere_E,
            ob.fin_cycle  AS fin_cycle,
            {expr_seances},
            me.titre      AS methode_titre,
            me.etat_code  AS methode_etat_code
        FROM objectifs ob
        LEFT JOIN methodes me ON me.id = ob.methode_id
        WHERE ob.partie_id = ?
        ORDER BY ob.code
        """,
        (partie_id,),
    ).fetchall()

    return [
        {
            "id":             r["id"],
            "code":           r["code"],
            "nom":            r["nom"],
            "methode_id":     r["methode_id"],
            "methode_titre":  r["methode_titre"],   # None si méthode non liée
            "methode_etat_code": r["methode_etat_code"] or "en_cours",
            "critere_F":      r["critere_F"],
            "critere_A":      r["critere_A"],
            "critere_E":      r["critere_E"],
            "fin_cycle":      r["fin_cycle"] or "N",
            "nb_seances":     r["nb_seances"],
            "notions":        _charger_notions_objectif(conn, r["id"]),
            "exos_par_serie": _charger_exos_par_serie(conn, r["id"]),
        }
        for r in rows
    ]


def _charger_notions_objectif(conn, objectif_id):
    """Notions associées à un objectif, ordonnées par `ordre` puis titre.

    Retourne une liste possiblement vide. Chaque entrée contient id, titre,
    ordre. Source : table objectif_notions (v0.6.4).
    """
    rows = conn.execute(
        """
        SELECT n.id, n.titre, on_.ordre, n.etat_code
        FROM objectif_notions on_
        JOIN notions n ON n.id = on_.notion_id
        WHERE on_.objectif_id = ?
        ORDER BY on_.ordre, n.titre
        """,
        (objectif_id,),
    ).fetchall()
    return [
        {"id": r["id"], "titre": r["titre"] or "", "ordre": r["ordre"],
         "etat_code": r["etat_code"] or "en_cours"}
        for r in rows
    ]


def _charger_exos_par_serie(conn, objectif_id):
    """Charge les exos d'un objectif classés par série, chaque série triée
    par ordre. Toutes les 5 séries sont présentes dans le dict (tableaux
    vides si aucun exo).

    R4e4a : la colonne `num` de `objectif_exos` a été renommée `origin_num`
    (= numéro de l'exercice dans sa série d'origine, pertinent surtout
    pour la série R). Le tri principal se fait sur `ordre` désormais —
    la nouvelle contrainte UNIQUE(objectif_id, serie, ordre) garantit
    qu'il n'y a pas de doublons et qu'un tie-breaker est inutile.

    On enrichit chaque exo avec des métadonnées d'affichage venues de la
    table exercices : nom, fichier, niveau, sequence, num, serie_code.
    Ces données sont en lecture seule (facultatives : tableaux vides si
    l'exo n'existe plus dans exercices, cas théorique puisque la FK est
    ON DELETE RESTRICT mais on reste défensif).
    """
    rows = conn.execute(
        """
        SELECT
            oe.serie          AS serie,
            oe.origin_num     AS origin_num,
            oe.ordre          AS ordre,
            oe.exercice_id    AS exercice_id,
            oe.origin_niveau  AS origin_niveau,
            oe.origin_seq     AS origin_seq,
            oe.origin_serie   AS origin_serie,
            ex.titre          AS exercice_titre,
            ex.fichier        AS exercice_fichier,
            ex.niveau         AS exercice_niveau,
            ex.sequence       AS exercice_sequence,
            ex.num            AS exercice_num,
            ex.serie_code     AS exercice_serie_code,
            ex.etat_code      AS exercice_etat_code
        FROM objectif_exos oe
        LEFT JOIN exercices ex ON ex.id = oe.exercice_id
        WHERE oe.objectif_id = ?
        ORDER BY oe.serie, oe.ordre
        """,
        (objectif_id,),
    ).fetchall()

    # Initialise toutes les séries à vide (ordre pédagogique R, EA, F, A, E).
    resultat = {s: [] for s in SERIES_V2}

    for r in rows:
        serie = r["serie"]
        if serie not in resultat:
            # Série inconnue (robustesse). On l'ignore silencieusement —
            # R4b garantit que seules R/EA/F/A/E sont peuplées.
            continue
        resultat[serie].append({
            "origin_num":    r["origin_num"],
            "ordre":         r["ordre"],
            "exercice_id":   r["exercice_id"],
            "origin_niveau": r["origin_niveau"],
            "origin_seq":    r["origin_seq"],
            "origin_serie":  r["origin_serie"],
            "exercice": {
                "titre":      r["exercice_titre"] or "",
                "fichier":    r["exercice_fichier"] or "",
                "niveau":     r["exercice_niveau"] or "",
                "sequence":   r["exercice_sequence"] or "",
                "num":        r["exercice_num"],
                "serie_code": r["exercice_serie_code"] or "",
                "etat_code":  r["exercice_etat_code"] or "en_cours",
            },
        })

    return resultat
