"""services/v2_edition.py — R4e2 + R4e3.

Édition du modèle v2 : parties, précédences, objectif (réassignation et
édition granulaire).

Périmètre :
  - CRUD partie : creer / supprimer / renumeroter                  (R4e2)
  - Précédences : ajouter / supprimer                              (R4e2)
  - Objectif : reassigner_a_partie (inter-partie, même séquence)   (R4e2)
  - Objectif : modifier_code / modifier_nom / modifier_methode /
    modifier_criteres (édition granulaire, 1 endpoint par champ)   (R4e3)
  - Catalogue : lister_methodes_de_sequence (lecture seule, utilisé
    par l'UI pour peupler le <select> de méthode)                  (R4e3)

Aucune Flask. Fonctions pures prenant une `conn` sqlite3 avec
row_factory = sqlite3.Row. Chaque opération est dans une transaction
implicite (le commit se fait au niveau appelant, côté route, ou via
`with store._conn() as conn`).

Invariants respectés (contraintes DB + invariants métier) :
  1. UNIQUE (sequence_par_niveau_id, numero) sur sequence_parties
  2. UNIQUE (partie_id, code) sur objectifs
  3. PRIMARY KEY (partie_id, precedent_niveau, precedent_seq) sur
     partie_precedences
  4. Suppression d'une partie non vide : refusée (409 PartieNonVide)
  5. Réassignation : refusée si la cible appartient à une autre séquence
     par niveau, ou si un objectif avec le même code existe déjà dans la
     partie cible (conflit UNIQUE).
  6. Renommage d'un code d'objectif : refusé si un autre objectif de la
     même partie porte déjà ce code (conflit UNIQUE).
  7. Affectation d'une méthode inexistante : 404.

La cohérence « code premier chiffre == partie - 1 » est une convention
pédagogique, PAS un invariant technique. On la vérifie avec
`code_coherent_avec_partie()` qui sert au frontend pour afficher un
badge d'alerte, mais le service n'empêche jamais une réassignation qui
casse la convention — c'est un choix assumé (la convention ne couvre
pas tous les cas : objectif 'Cours' hérité, cas pédagogiques atypiques).
"""

from __future__ import annotations
import sqlite3

from persistence.ids import nouveau_id_partie, nouveau_id_objectif


# ── Hiérarchie d'exceptions ──────────────────────────────────────────────────

class V2EditionErreur(Exception):
    """Classe de base. Chaque sous-classe porte un `code` unique pour
    faciliter le mapping HTTP et le message UI côté frontend."""
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class SequenceParNiveauIntrouvable(V2EditionErreur):
    def __init__(self, sn_id: str):
        super().__init__(
            f"Séquence par niveau introuvable : {sn_id}",
            "sequence_par_niveau_introuvable",
            sequence_par_niveau_id=sn_id,
        )


class PartieIntrouvable(V2EditionErreur):
    def __init__(self, partie_id: str):
        super().__init__(
            f"Partie introuvable : {partie_id}",
            "partie_introuvable",
            partie_id=partie_id,
        )


class ObjectifIntrouvable(V2EditionErreur):
    def __init__(self, objectif_id: str):
        super().__init__(
            f"Objectif introuvable : {objectif_id}",
            "objectif_introuvable",
            objectif_id=objectif_id,
        )


class NumeroPartieInvalide(V2EditionErreur):
    def __init__(self, numero):
        super().__init__(
            f"Numéro de partie invalide : {numero!r} (attendu entier ≥ 1)",
            "numero_invalide",
            numero=numero,
        )


class NumeroPartieDejaUtilise(V2EditionErreur):
    def __init__(self, numero: int):
        super().__init__(
            f"Le numéro {numero} est déjà utilisé par une autre partie "
            f"dans cette séquence",
            "numero_deja_utilise",
            numero=numero,
        )


class PartieNonVide(V2EditionErreur):
    def __init__(self, partie_id: str, nb_objectifs: int):
        super().__init__(
            f"Impossible de supprimer la partie : elle contient encore "
            f"{nb_objectifs} objectif(s). Réassigner ou supprimer les "
            f"objectifs d'abord.",
            "partie_non_vide",
            partie_id=partie_id,
            nb_objectifs=nb_objectifs,
        )


class PrecedenceDejaPresente(V2EditionErreur):
    def __init__(self, partie_id, precedent_niveau, precedent_seq):
        super().__init__(
            f"La précédence {precedent_niveau}/{precedent_seq} existe "
            f"déjà pour cette partie",
            "precedence_deja_presente",
            partie_id=partie_id,
            precedent_niveau=precedent_niveau,
            precedent_seq=precedent_seq,
        )


class PrecedenceInvalide(V2EditionErreur):
    def __init__(self, message, **details):
        super().__init__(message, "precedence_invalide", **details)


class PrecedenceIntrouvable(V2EditionErreur):
    def __init__(self, partie_id, precedent_niveau, precedent_seq):
        super().__init__(
            f"Précédence introuvable : {precedent_niveau}/{precedent_seq} "
            f"sur la partie {partie_id}",
            "precedence_introuvable",
            partie_id=partie_id,
            precedent_niveau=precedent_niveau,
            precedent_seq=precedent_seq,
        )


class ReassignationImpossible(V2EditionErreur):
    """Conflit : l'objectif cible d'un déplacement est en conflit avec
    la partie cible (autre séquence, ou code déjà présent)."""
    def __init__(self, message, code, **details):
        super().__init__(message, code, **details)


# ── R4e3 : exceptions pour l'édition d'objectif ──────────────────────────────

class CodeObjectifInvalide(V2EditionErreur):
    def __init__(self, code):
        super().__init__(
            f"Code d'objectif invalide : {code!r} (attendu chaîne non vide, "
            f"sans espaces, 1 à 4 caractères)",
            "code_objectif_invalide",
            code_invalide=code,
        )


class CodeObjectifDejaUtilise(V2EditionErreur):
    """Le code demandé est déjà porté par un autre objectif de la même
    partie (viole UNIQUE(partie_id, code))."""
    def __init__(self, code, partie_id):
        super().__init__(
            f"Le code {code!r} est déjà utilisé par un autre objectif de "
            f"cette partie",
            "code_objectif_deja_utilise",
            code_demande=code,
            partie_id=partie_id,
        )


class MethodeIntrouvable(V2EditionErreur):
    def __init__(self, methode_id):
        super().__init__(
            f"Méthode introuvable : {methode_id}",
            "methode_introuvable",
            methode_id=methode_id,
        )


# ── R4e4b : exceptions pour l'édition des exos ───────────────────────────────

class ExerciceIntrouvable(V2EditionErreur):
    def __init__(self, exercice_id):
        super().__init__(
            f"Exercice introuvable : {exercice_id}",
            "exercice_introuvable",
            exercice_id=exercice_id,
        )


class SerieInvalide(V2EditionErreur):
    """Série d'exo demandée n'est pas dans EA/F/A/E."""
    def __init__(self, serie):
        super().__init__(
            f"Série invalide : {serie!r} (attendu EA, F, A ou E)",
            "serie_invalide",
            serie=serie,
        )


class ExoDejaPresent(V2EditionErreur):
    """L'exercice est déjà dans cette (objectif, série). On peut
    toutefois l'avoir dans une autre série du même objectif."""
    def __init__(self, objectif_id, serie, exercice_id):
        super().__init__(
            f"L'exercice {exercice_id!r} est déjà présent dans la série "
            f"{serie!r} de cet objectif",
            "exo_deja_present",
            objectif_id=objectif_id,
            serie=serie,
            exercice_id=exercice_id,
        )


class ExoIntrouvableDansObjectif(V2EditionErreur):
    """L'exo qu'on veut retirer/déplacer n'est pas dans l'objectif."""
    def __init__(self, objectif_id, serie, exercice_id):
        super().__init__(
            f"Exercice {exercice_id!r} absent de la série {serie!r} "
            f"de l'objectif",
            "exo_introuvable_dans_objectif",
            objectif_id=objectif_id,
            serie=serie,
            exercice_id=exercice_id,
        )


class OriginInvalide(V2EditionErreur):
    """Les champs origin_* sont incohérents avec la série choisie :
    obligatoires pour la série R, interdits pour les autres."""
    def __init__(self, message, **details):
        super().__init__(message, "origin_invalide", **details)


class ReordonnancementInvalide(V2EditionErreur):
    """La liste passée à reordonner_exos ne correspond pas exactement
    à l'ensemble actuel."""
    def __init__(self, message, **details):
        super().__init__(message, "reordonnancement_invalide", **details)


# ── v0.10 — Atelier d'assemblage ─────────────────────────────────────────────

class TypeRevisionApprocheInvalide(V2EditionErreur):
    """Le type d'exo « début de partie » doit être 'R' ou 'EA'."""
    def __init__(self, recu):
        super().__init__(
            f"Type invalide : {recu!r} (attendu 'R' ou 'EA').",
            "type_revision_approche_invalide",
            recu=recu,
        )


class ExoRevisionApprocheDejaPresent(V2EditionErreur):
    def __init__(self, partie_id, type_, exercice_id):
        super().__init__(
            f"L'exo {exercice_id} est déjà dans la partie {partie_id} "
            f"comme {type_}.",
            "exo_revision_approche_deja_present",
            partie_id=partie_id, type=type_, exercice_id=exercice_id,
        )


class ExoRevisionApprocheIntrouvable(V2EditionErreur):
    def __init__(self, partie_id, type_, exercice_id):
        super().__init__(
            f"Exo {exercice_id} introuvable dans la partie {partie_id} "
            f"comme {type_}.",
            "exo_revision_approche_introuvable",
            partie_id=partie_id, type=type_, exercice_id=exercice_id,
        )


class ObjectifConnaitreDejaPresent(V2EditionErreur):
    """L'objectif « Connaître » (code '0X') existe déjà dans la partie.

    Le X dépend du numéro de partie : '01' en partie 1, '11' en partie 2,
    '21' en partie 3, etc.
    """
    def __init__(self, partie_id, code_existant):
        super().__init__(
            f"L'objectif Connaître ({code_existant}) existe déjà dans la "
            f"partie {partie_id}.",
            "objectif_connaitre_deja_present",
            partie_id=partie_id, code_existant=code_existant,
        )


# ── v0.10.2 — Précédences au niveau séquence ────────────────────────────────

class PrecedenceSeqDejaPresente(V2EditionErreur):
    """La précédence (precedent_niveau, precedent_seq) existe déjà pour
    la séquence-niveau cible."""
    def __init__(self, sequence_par_niveau_id, precedent_niveau, precedent_seq):
        super().__init__(
            f"La précédence {precedent_niveau}/{precedent_seq} existe "
            f"déjà pour cette séquence-niveau.",
            "precedence_seq_deja_presente",
            sequence_par_niveau_id=sequence_par_niveau_id,
            precedent_niveau=precedent_niveau,
            precedent_seq=precedent_seq,
        )


class PrecedenceSeqIntrouvable(V2EditionErreur):
    def __init__(self, sequence_par_niveau_id, precedent_niveau, precedent_seq):
        super().__init__(
            f"Précédence introuvable : {precedent_niveau}/{precedent_seq} "
            f"sur la séquence {sequence_par_niveau_id}",
            "precedence_seq_introuvable",
            sequence_par_niveau_id=sequence_par_niveau_id,
            precedent_niveau=precedent_niveau,
            precedent_seq=precedent_seq,
        )


class ExoRevisionHorsPrecedences(V2EditionErreur):
    """v0.10.2 — Tentative d'ajout d'un exo R dont la séquence d'origine
    ne figure pas parmi les précédences de la séquence-niveau courante.

    C'est une règle métier strict : un exo de révision DOIT venir d'une
    séquence-niveau précédente déclarée."""
    def __init__(self, partie_id, exercice_id, exo_niveau, exo_sequence):
        super().__init__(
            f"L'exercice {exercice_id} (de {exo_niveau}/{exo_sequence}) ne "
            f"peut pas être placé en révision : sa séquence d'origine ne "
            f"figure pas dans les précédences de la séquence-niveau.",
            "exo_revision_hors_precedences",
            partie_id=partie_id,
            exercice_id=exercice_id,
            exo_niveau=exo_niveau,
            exo_sequence=exo_sequence,
        )


class ExoRevisionMauvaiseSerie(V2EditionErreur):
    """v0.10.2 — L'exo proposé en R n'est pas de la série A (convention :
    on tire les exos de révision parmi les exos d'évaluation A du n-1)."""
    def __init__(self, partie_id, exercice_id, serie_code):
        super().__init__(
            f"L'exercice {exercice_id} (série {serie_code or '?'}) ne peut "
            f"pas être placé en révision : seuls les exos de la série A "
            f"sont éligibles à la révision.",
            "exo_revision_mauvaise_serie",
            partie_id=partie_id,
            exercice_id=exercice_id,
            serie_code=serie_code,
        )


class ExoApprocheHorsSequence(V2EditionErreur):
    """v0.10.2 — L'exo proposé en EA n'appartient pas à la séquence-niveau
    courante. Convention : les exos d'approche sont dans la série EA de la
    séquence elle-même."""
    def __init__(self, partie_id, exercice_id, exo_niveau, exo_sequence):
        super().__init__(
            f"L'exercice {exercice_id} (de {exo_niveau}/{exo_sequence}) ne "
            f"peut pas être placé en approche : il n'appartient pas à la "
            f"séquence-niveau courante.",
            "exo_approche_hors_sequence",
            partie_id=partie_id,
            exercice_id=exercice_id,
            exo_niveau=exo_niveau,
            exo_sequence=exo_sequence,
        )


class ExoApprocheMauvaiseSerie(V2EditionErreur):
    """v0.10.2 — L'exo proposé en approche n'est pas de la série approche.
    v0.18.3 — La série approche a pour serie_code 'AE'.
    """
    def __init__(self, partie_id, exercice_id, serie_code):
        super().__init__(
            f"L'exercice {exercice_id} (série {serie_code or '?'}) ne peut "
            f"pas être placé en approche : seuls les exos de la série AE "
            f"sont éligibles à l'approche.",
            "exo_approche_mauvaise_serie",
            partie_id=partie_id,
            exercice_id=exercice_id,
            serie_code=serie_code,
        )


class NotionHorsSequence(V2EditionErreur):
    """v0.10.7 — Tentative de lier une notion à un objectif d'une autre
    séquence-niveau que celle d'origine de la notion. Règle métier :
    une notion n'est utilisable que dans sa séquence d'origine.

    Tolérance legacy : si la notion n'a pas de (niveau, sequence)
    posés (champ vide), la liaison est autorisée — fallback pour les
    données historiques importées sans ces métadonnées.
    """
    def __init__(self, notion_id, notion_niveau, notion_sequence,
                 objectif_id, obj_niveau, obj_sequence):
        super().__init__(
            f"La notion {notion_id} (de {notion_niveau}/{notion_sequence}) "
            f"ne peut pas être liée à un objectif de "
            f"{obj_niveau}/{obj_sequence} : une notion ne peut être "
            f"utilisée que dans sa séquence d'origine.",
            "notion_hors_sequence",
            notion_id=notion_id,
            notion_niveau=notion_niveau,
            notion_sequence=notion_sequence,
            objectif_id=objectif_id,
            obj_niveau=obj_niveau,
            obj_sequence=obj_sequence,
        )


class MethodeHorsSequence(V2EditionErreur):
    """v0.10.7 — Tentative de lier une méthode à un objectif d'une autre
    séquence-niveau que celle d'origine de la méthode. Règle métier :
    une méthode n'est utilisable que dans sa séquence d'origine.

    Tolérance legacy : idem `NotionHorsSequence`.
    """
    def __init__(self, methode_id, methode_niveau, methode_sequence,
                 objectif_id, obj_niveau, obj_sequence):
        super().__init__(
            f"La méthode {methode_id} (de {methode_niveau}/{methode_sequence}) "
            f"ne peut pas être liée à un objectif de "
            f"{obj_niveau}/{obj_sequence} : une méthode ne peut être "
            f"utilisée que dans sa séquence d'origine.",
            "methode_hors_sequence",
            methode_id=methode_id,
            methode_niveau=methode_niveau,
            methode_sequence=methode_sequence,
            objectif_id=objectif_id,
            obj_niveau=obj_niveau,
            obj_sequence=obj_sequence,
        )


class MethodeDejaLiee(V2EditionErreur):
    """v0.10.7 — Tentative de lier une méthode déjà attachée à un autre
    objectif. Règle métier : une méthode est rattachée à un seul
    objectif (cardinalité 1-1 méthode → objectif).
    """
    def __init__(self, methode_id, objectif_actuel_id, objectif_demande_id):
        super().__init__(
            f"La méthode {methode_id} est déjà liée à l'objectif "
            f"{objectif_actuel_id}. Une méthode ne peut être liée qu'à "
            f"un seul objectif. Détacher d'abord la méthode de "
            f"l'objectif {objectif_actuel_id}, puis l'attacher à "
            f"{objectif_demande_id}.",
            "methode_deja_liee",
            methode_id=methode_id,
            objectif_actuel_id=objectif_actuel_id,
            objectif_demande_id=objectif_demande_id,
        )


# ── v0.12.0 — Plan de travail générique : nb de séances ──────────────────────

class SeancesInvalides(V2EditionErreur):
    """v0.12.0 — Valeur de nb_seances invalide.

    Règles : doit être un nombre (int ou float), ≥ 0 et raisonnablement
    fini (≤ 999, garde-fou contre les saisies aberrantes). Les
    demi-séances sont autorisées (multiples de 0,5), mais on n'impose pas
    la contrainte au service : c'est une convention pédagogique, pas une
    invariant de stockage.
    """
    def __init__(self, valeur):
        super().__init__(
            f"Valeur de nb_seances invalide : {valeur!r}. Attendu : un "
            f"nombre ≥ 0 et ≤ 999.",
            "seances_invalides",
            valeur=valeur,
        )
        self.valeur = valeur


class EtatSequenceInvalide(V2EditionErreur):
    """v0.16.9 — Code d'état hors {'en_cours', 'valide'}."""
    def __init__(self, valeur):
        super().__init__(
            f"État de séquence invalide : {valeur!r}. "
            f"Attendu : 'en_cours' ou 'valide'.",
            "etat_sequence_invalide",
            valeur=valeur,
        )


class SequenceVerrouillee(V2EditionErreur):
    """v0.16.9 — La séquence-niveau est validée (lecture seule).

    Levée par `assert_sequence_modifiable` au début de toute opération qui
    modifie le CONTENU de la séquence (saisie ou structure) alors qu'elle
    est en état 'valide'. Traduite en HTTP 409 Conflict (code
    'item_verrouille', homogène avec le verrou des atomes).

    NB : la route de changement d'état (qui doit pouvoir dévalider) ne pose
    PAS cette garde. La lecture et la compilation restent autorisées.
    """
    def __init__(self, sn_id: str):
        super().__init__(
            f"La séquence-niveau {sn_id} est validée (lecture seule). "
            f"Repassez-la en cours pour la modifier.",
            "item_verrouille",
            type_item="sequence_par_niveau", item_id=sn_id,
        )


class ValidationSequenceErreur(V2EditionErreur):
    """v0.16.9 — Échec du hook de validation pédagogique d'une séquence.

    `raisons` est la liste des contrôles non satisfaits. Traduite en HTTP
    400 (code 'validation_pedagogique_echec', homogène avec les atomes et
    les évaluations) avec details.raisons.
    """
    def __init__(self, sn_id: str, raisons: list[str]):
        super().__init__(
            "La séquence ne peut pas être validée en l'état.",
            "validation_pedagogique_echec",
            type_item="sequence_par_niveau", item_id=sn_id,
            raisons=list(raisons),
        )
        self.raisons = list(raisons)


# ── Helper métier : cohérence code / partie ─────────────────────────────────

def code_coherent_avec_partie(code: str, numero_partie: int) -> bool:
    """Vérifie la convention canonique : le premier chiffre du code doit
    valoir `numero_partie - 1` (code '0x' en partie 1, '1x' en partie 2…).

    Retourne True si la convention est respectée OU si elle n'est pas
    applicable (code non-numérique ou de longueur ≠ 2). Cette tolérance
    évite de signaler à tort un objectif 'Cours' ou un code atypique.
    """
    if not code or len(code) != 2 or not code.isdigit():
        return True  # convention non applicable
    return int(code[0]) + 1 == numero_partie


# ── Récupérations de base ────────────────────────────────────────────────────

def _lire_sequence_par_niveau(conn, sn_id):
    row = conn.execute(
        "SELECT id, niveau, sequence_code FROM sequences_par_niveau "
        "WHERE id = ?",
        (sn_id,),
    ).fetchone()
    if row is None:
        raise SequenceParNiveauIntrouvable(sn_id)
    return row


def _lire_partie(conn, partie_id):
    row = conn.execute(
        "SELECT id, sequence_par_niveau_id, numero FROM sequence_parties "
        "WHERE id = ?",
        (partie_id,),
    ).fetchone()
    if row is None:
        raise PartieIntrouvable(partie_id)
    return row


def _lire_objectif(conn, objectif_id):
    row = conn.execute(
        "SELECT id, partie_id, code, nom FROM objectifs WHERE id = ?",
        (objectif_id,),
    ).fetchone()
    if row is None:
        raise ObjectifIntrouvable(objectif_id)
    return row


def _lire_niv_seq_objectif(conn, objectif_id):
    """v0.10.7 — Retourne le couple (niveau, sequence) d'un objectif via la
    chaîne objectif → partie → sequence_par_niveau. Utilisé par les règles
    métier de scope (notion/méthode liée à la même séquence que l'objectif).

    Lève ObjectifIntrouvable si l'objectif n'existe pas.
    """
    row = conn.execute(
        """
        SELECT sn.niveau AS niveau, sn.sequence_code AS sequence
        FROM objectifs ob
        JOIN sequence_parties p ON p.id = ob.partie_id
        JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id
        WHERE ob.id = ?
        """,
        (objectif_id,),
    ).fetchone()
    if row is None:
        raise ObjectifIntrouvable(objectif_id)
    return row["niveau"], row["sequence"]


# ═════════════════════════════════════════════════════════════════════════════
# CRUD partie
# ═════════════════════════════════════════════════════════════════════════════

def creer_partie(conn, sequence_par_niveau_id: str, numero: int | None = None) -> dict:
    """Crée une nouvelle partie dans une séquence par niveau.

    Si `numero` est fourni : l'utilise (409 NumeroPartieDejaUtilise si
    conflit). Si None : attribue le prochain numéro libre (max + 1, ou 1
    si aucune partie).

    Retourne un dict {id, sequence_par_niveau_id, numero}.
    """
    _lire_sequence_par_niveau(conn, sequence_par_niveau_id)  # 404 si absente

    if numero is None:
        max_row = conn.execute(
            "SELECT COALESCE(MAX(numero), 0) AS m FROM sequence_parties "
            "WHERE sequence_par_niveau_id = ?",
            (sequence_par_niveau_id,),
        ).fetchone()
        numero = (max_row["m"] or 0) + 1
    else:
        numero = _valider_numero(numero)
        # Vérifier unicité (plus propre qu'attraper IntegrityError
        # parce qu'on peut distinguer 409 d'erreurs techniques)
        conflit = conn.execute(
            "SELECT 1 FROM sequence_parties "
            "WHERE sequence_par_niveau_id = ? AND numero = ?",
            (sequence_par_niveau_id, numero),
        ).fetchone()
        if conflit:
            raise NumeroPartieDejaUtilise(numero)

    pt_id = nouveau_id_partie()
    conn.execute(
        "INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
        "VALUES (?, ?, ?)",
        (pt_id, sequence_par_niveau_id, numero),
    )
    return {
        "id": pt_id,
        "sequence_par_niveau_id": sequence_par_niveau_id,
        "numero": numero,
    }


def supprimer_partie(conn, partie_id: str) -> dict:
    """Supprime une partie. Refuse (409) si elle contient encore des
    objectifs. Les précédences associées partent en cascade (FK ON DELETE
    CASCADE sur partie_precedences.partie_id).
    """
    _lire_partie(conn, partie_id)  # 404 si absente

    nb = conn.execute(
        "SELECT COUNT(*) AS n FROM objectifs WHERE partie_id = ?",
        (partie_id,),
    ).fetchone()["n"]
    if nb > 0:
        raise PartieNonVide(partie_id, nb)

    # Les précédences s'effacent en cascade (FK).
    conn.execute("DELETE FROM sequence_parties WHERE id = ?", (partie_id,))
    return {"partie_id": partie_id, "supprimee": True}


def renumeroter_partie(conn, partie_id: str, nouveau_numero: int) -> dict:
    """Change le numero d'une partie. 409 si le numéro cible est déjà
    utilisé par une autre partie dans la même séquence.

    Pas d'auto-renumérotation en cascade des autres parties : si
    l'utilisateur veut permuter 1↔2, il devra soit passer par un numéro
    temporaire (ex 99), soit utiliser un endpoint de permutation qu'on
    pourra ajouter plus tard. Ce choix simplifie R4e2 et respecte le
    principe d'atomicité simple.
    """
    partie = _lire_partie(conn, partie_id)
    nouveau_numero = _valider_numero(nouveau_numero)

    if partie["numero"] == nouveau_numero:
        # No-op idempotent
        return {
            "id": partie_id,
            "sequence_par_niveau_id": partie["sequence_par_niveau_id"],
            "numero": nouveau_numero,
        }

    conflit = conn.execute(
        "SELECT 1 FROM sequence_parties "
        "WHERE sequence_par_niveau_id = ? AND numero = ? AND id != ?",
        (partie["sequence_par_niveau_id"], nouveau_numero, partie_id),
    ).fetchone()
    if conflit:
        raise NumeroPartieDejaUtilise(nouveau_numero)

    conn.execute(
        "UPDATE sequence_parties SET numero = ? WHERE id = ?",
        (nouveau_numero, partie_id),
    )
    return {
        "id": partie_id,
        "sequence_par_niveau_id": partie["sequence_par_niveau_id"],
        "numero": nouveau_numero,
    }


def _valider_numero(numero) -> int:
    """Coerce en int et vérifie ≥ 1. Lève NumeroPartieInvalide sinon."""
    try:
        n = int(numero)
    except (TypeError, ValueError):
        raise NumeroPartieInvalide(numero)
    if n < 1:
        raise NumeroPartieInvalide(numero)
    return n


# ═════════════════════════════════════════════════════════════════════════════
# Précédences
# ═════════════════════════════════════════════════════════════════════════════

_NIVEAUX_CONNUS = ("N09", "N10", "N11", "N12")


def ajouter_precedence(
    conn,
    partie_id: str,
    precedent_niveau: str,
    precedent_seq: str,
) -> dict:
    """Ajoute une précédence sur une partie. 409 si déjà présente."""
    _lire_partie(conn, partie_id)
    _valider_precedence(precedent_niveau, precedent_seq)

    conflit = conn.execute(
        "SELECT 1 FROM partie_precedences "
        "WHERE partie_id = ? AND precedent_niveau = ? AND precedent_seq = ?",
        (partie_id, precedent_niveau, precedent_seq),
    ).fetchone()
    if conflit:
        raise PrecedenceDejaPresente(partie_id, precedent_niveau, precedent_seq)

    conn.execute(
        "INSERT INTO partie_precedences "
        "(partie_id, precedent_niveau, precedent_seq) VALUES (?, ?, ?)",
        (partie_id, precedent_niveau, precedent_seq),
    )
    return {
        "partie_id": partie_id,
        "precedent_niveau": precedent_niveau,
        "precedent_seq": precedent_seq,
    }


def supprimer_precedence(
    conn,
    partie_id: str,
    precedent_niveau: str,
    precedent_seq: str,
) -> dict:
    """Supprime une précédence. 404 si absente (distinguer d'un 409 pour
    clarifier l'origine de l'erreur côté UI)."""
    _lire_partie(conn, partie_id)

    cur = conn.execute(
        "DELETE FROM partie_precedences "
        "WHERE partie_id = ? AND precedent_niveau = ? AND precedent_seq = ?",
        (partie_id, precedent_niveau, precedent_seq),
    )
    if cur.rowcount == 0:
        raise PrecedenceIntrouvable(partie_id, precedent_niveau, precedent_seq)
    return {
        "partie_id": partie_id,
        "precedent_niveau": precedent_niveau,
        "precedent_seq": precedent_seq,
        "supprimee": True,
    }


def _valider_precedence(precedent_niveau, precedent_seq):
    if not isinstance(precedent_niveau, str) or not precedent_niveau:
        raise PrecedenceInvalide(
            "Niveau de précédence manquant ou vide",
            precedent_niveau=precedent_niveau,
        )
    if not isinstance(precedent_seq, str) or not precedent_seq:
        raise PrecedenceInvalide(
            "Séquence de précédence manquante ou vide",
            precedent_seq=precedent_seq,
        )
    # Sanity checks doux — on tolère les cas atypiques (N08 ?) sans
    # bloquer, mais on refuse les formats absurdes.
    if precedent_niveau not in _NIVEAUX_CONNUS and not (
        precedent_niveau.startswith("N") and precedent_niveau[1:].isdigit()
    ):
        raise PrecedenceInvalide(
            f"Format de niveau invalide : {precedent_niveau!r} "
            f"(attendu NXX)",
            precedent_niveau=precedent_niveau,
        )
    if not (precedent_seq.startswith("S") and precedent_seq[1:].isdigit()):
        raise PrecedenceInvalide(
            f"Format de séquence invalide : {precedent_seq!r} "
            f"(attendu SXX)",
            precedent_seq=precedent_seq,
        )


# ═════════════════════════════════════════════════════════════════════════════
# Réassignation d'objectif entre parties
# ═════════════════════════════════════════════════════════════════════════════

def reassigner_objectif_a_partie(
    conn,
    objectif_id: str,
    partie_id_cible: str,
) -> dict:
    """Déplace un objectif d'une partie à une autre, dans la même
    séquence par niveau.

    Refuse (409 ReassignationImpossible) si :
      - la partie cible appartient à une autre séquence par niveau
      - un objectif avec le même code existe déjà dans la partie cible
        (conflit UNIQUE(partie_id, code))

    NE renumérote PAS le code de l'objectif. La cohérence du code avec
    la nouvelle partie est une affaire de convention, signalée par
    `code_coherent_avec_partie()` côté UI.
    """
    obj = _lire_objectif(conn, objectif_id)
    partie_cible = _lire_partie(conn, partie_id_cible)

    partie_source = _lire_partie(conn, obj["partie_id"])

    # Même séquence par niveau ?
    if partie_source["sequence_par_niveau_id"] != partie_cible["sequence_par_niveau_id"]:
        raise ReassignationImpossible(
            "La partie cible appartient à une autre séquence par niveau. "
            "La réassignation n'est autorisée qu'à l'intérieur de la même "
            "séquence par niveau.",
            "partie_hors_sequence",
            objectif_id=objectif_id,
            partie_id_cible=partie_id_cible,
            sequence_par_niveau_source=partie_source["sequence_par_niveau_id"],
            sequence_par_niveau_cible=partie_cible["sequence_par_niveau_id"],
        )

    # No-op si déjà dans la partie cible.
    if obj["partie_id"] == partie_id_cible:
        return _format_retour_reassignation(obj, partie_cible, code_change=False)

    # Conflit de code dans la partie cible ?
    conflit = conn.execute(
        "SELECT 1 FROM objectifs "
        "WHERE partie_id = ? AND code = ? AND id != ?",
        (partie_id_cible, obj["code"], objectif_id),
    ).fetchone()
    if conflit:
        raise ReassignationImpossible(
            f"Un objectif avec le code {obj['code']!r} existe déjà dans "
            f"la partie cible. Renommer l'un des deux avant de réassigner.",
            "conflit_code_dans_partie_cible",
            objectif_id=objectif_id,
            partie_id_cible=partie_id_cible,
            code_objectif=obj["code"],
        )

    conn.execute(
        "UPDATE objectifs SET partie_id = ? WHERE id = ?",
        (partie_id_cible, objectif_id),
    )
    return _format_retour_reassignation(obj, partie_cible, code_change=True)


def _format_retour_reassignation(obj, partie_cible, code_change: bool):
    """Format de retour homogène : inclut un flag `code_coherent` pour
    que le frontend sache tout de suite s'il faut afficher le badge
    d'alerte, sans refaire le calcul."""
    return {
        "objectif_id": obj["id"],
        "code": obj["code"],
        "partie_id": partie_cible["id"],
        "numero_partie": partie_cible["numero"],
        "code_coherent": code_coherent_avec_partie(
            obj["code"], partie_cible["numero"]
        ),
        "deplace": code_change,
    }


# ═════════════════════════════════════════════════════════════════════════════
# R4e3 — Édition granulaire d'un objectif
# ═════════════════════════════════════════════════════════════════════════════
#
# Quatre fonctions de mutation, une par champ éditable :
#   - modifier_code_objectif    → change objectifs.code
#   - modifier_nom_objectif     → change objectifs.nom
#   - modifier_methode_objectif → change objectifs.methode_id (FK/NULL)
#   - modifier_criteres_objectif → change critere_F / critere_A / critere_E
#
# Et une fonction de lecture :
#   - lister_methodes_de_sequence → catalogue pour peupler le <select>
#
# Chaque mutation renvoie l'objectif mis à jour (incluant code_coherent
# avec sa partie, pour que le frontend puisse rafraîchir le badge
# d'alerte sans re-fetch complet).


def _valider_code_objectif(code) -> str:
    """Trim + validation. Accepte 1 à 4 caractères, pas d'espace interne.

    La convention usuelle est 2 chiffres ('01'..'29'), mais le projet
    permet aussi des codes alphanumériques (ex : 'Cours'). On reste
    permissif, la cohérence partie ↔ code est signalée ailleurs (badge
    UI) sans bloquer le service.
    """
    if not isinstance(code, str):
        raise CodeObjectifInvalide(code)
    c = code.strip()
    if not c or len(c) > 4 or ' ' in c or '\t' in c or '\n' in c:
        raise CodeObjectifInvalide(code)
    return c


def modifier_code_objectif(conn, objectif_id: str, nouveau_code: str) -> dict:
    """Renomme le code d'un objectif. 409 si un autre objectif de la
    même partie porte déjà ce code."""
    obj = _lire_objectif(conn, objectif_id)
    code = _valider_code_objectif(nouveau_code)

    if obj["code"] == code:
        # No-op idempotent : on renvoie l'état actuel, utile à l'UI.
        return _format_retour_objectif(conn, objectif_id)

    conflit = conn.execute(
        "SELECT 1 FROM objectifs "
        "WHERE partie_id = ? AND code = ? AND id != ?",
        (obj["partie_id"], code, objectif_id),
    ).fetchone()
    if conflit:
        raise CodeObjectifDejaUtilise(code, obj["partie_id"])

    conn.execute(
        "UPDATE objectifs SET code = ? WHERE id = ?",
        (code, objectif_id),
    )
    return _format_retour_objectif(conn, objectif_id)


def modifier_nom_objectif(conn, objectif_id: str, nouveau_nom) -> dict:
    """Change le nom. Accepte chaîne vide (tolérance pour les objectifs
    hérités sans intitulé propre). Strip systématique."""
    _lire_objectif(conn, objectif_id)
    nom = (nouveau_nom or "").strip() if isinstance(nouveau_nom, str) else ""
    conn.execute(
        "UPDATE objectifs SET nom = ? WHERE id = ?",
        (nom, objectif_id),
    )
    return _format_retour_objectif(conn, objectif_id)


def modifier_methode_objectif(conn, objectif_id: str, methode_id) -> dict:
    """Change la méthode liée. `methode_id = None` ou chaîne vide → détache
    la méthode (colonne methode_id = NULL). Sinon, vérifie l'existence
    dans la table `methodes`.

    v0.10.7 — Règles métier :
      - **Scope séquence** : une méthode ne peut être liée qu'à un objectif
        de sa séquence d'origine (`methodes.niveau == objectif.niveau`
        ET `methodes.sequence == objectif.sequence`). Tolérance legacy :
        si la méthode n'a pas de (niveau, sequence) posés, la liaison
        est autorisée.
      - **Cardinalité 1-1 méthode → objectif** : une méthode ne peut
        être liée qu'à un seul objectif. Si la méthode est déjà liée à
        un autre objectif, lève `MethodeDejaLiee`. Si elle est déjà
        liée à l'objectif demandé : no-op idempotent.
    """
    _lire_objectif(conn, objectif_id)

    if methode_id in (None, ""):
        conn.execute(
            "UPDATE objectifs SET methode_id = NULL WHERE id = ?",
            (objectif_id,),
        )
    else:
        # Vérifier que la méthode existe et lire son scope
        m = conn.execute(
            "SELECT id, niveau, sequence FROM methodes WHERE id = ?",
            (methode_id,),
        ).fetchone()
        if m is None:
            raise MethodeIntrouvable(methode_id)

        # v0.10.7 — Scope séquence (tolérance legacy si scope vide)
        m_niveau   = m["niveau"]   or ""
        m_sequence = m["sequence"] or ""
        if m_niveau and m_sequence:
            obj_niveau, obj_sequence = _lire_niv_seq_objectif(conn, objectif_id)
            if m_niveau != obj_niveau or m_sequence != obj_sequence:
                raise MethodeHorsSequence(
                    methode_id, m_niveau, m_sequence,
                    objectif_id, obj_niveau, obj_sequence,
                )

        # v0.10.7 — Cardinalité 1-1 : la méthode ne doit pas être déjà
        # liée à un autre objectif. Si liée à l'objectif courant, c'est
        # un no-op idempotent (UPDATE inoffensif).
        deja = conn.execute(
            "SELECT id FROM objectifs WHERE methode_id = ? AND id != ?",
            (methode_id, objectif_id),
        ).fetchone()
        if deja is not None:
            raise MethodeDejaLiee(
                methode_id, deja["id"], objectif_id,
            )

        conn.execute(
            "UPDATE objectifs SET methode_id = ? WHERE id = ?",
            (methode_id, objectif_id),
        )
    return _format_retour_objectif(conn, objectif_id)


def modifier_criteres_objectif(
    conn,
    objectif_id: str,
    critere_F=None,
    critere_A=None,
    critere_E=None,
) -> dict:
    """Change un ou plusieurs critères. Les paramètres à None ne sont PAS
    écrits (permet la mise à jour partielle via l'API). Pour effacer un
    critère, passer la chaîne vide `""` explicitement.

    Accepte du LaTeX libre, pas de validation de syntaxe.
    """
    _lire_objectif(conn, objectif_id)

    champs = []
    valeurs = []
    if critere_F is not None:
        champs.append("critere_F = ?")
        valeurs.append(critere_F if isinstance(critere_F, str) else "")
    if critere_A is not None:
        champs.append("critere_A = ?")
        valeurs.append(critere_A if isinstance(critere_A, str) else "")
    if critere_E is not None:
        champs.append("critere_E = ?")
        valeurs.append(critere_E if isinstance(critere_E, str) else "")

    if champs:
        valeurs.append(objectif_id)
        conn.execute(
            f"UPDATE objectifs SET {', '.join(champs)} WHERE id = ?",
            tuple(valeurs),
        )
    # Si aucun champ fourni : no-op silencieux, on renvoie l'état courant.
    return _format_retour_objectif(conn, objectif_id)


def _format_retour_objectif(conn, objectif_id: str) -> dict:
    """Retour standard pour toute mutation d'objectif : état frais de la
    ligne + calcul du flag `code_coherent` pour le badge UI + titre de
    la méthode liée si présente.

    Inclut `fin_cycle` (depuis v0.6.4 où la propriété a migré de methodes
    vers objectifs) et `notions` (table objectif_notions, créée par
    le script peuplement_15).

    v0.12.0 : inclut aussi `nb_seances` (plan de travail générique).
    Sélection défensive sur la colonne au cas où la base précède la
    migration v0.12.0.
    """
    # v0.12.0 — sélection défensive de nb_seances
    try:
        cols = {r["name"] for r in conn.execute(
            "PRAGMA table_info(objectifs)"
        ).fetchall()}
    except Exception:
        cols = set()
    expr_seances = (
        "COALESCE(ov.nb_seances, 0) AS nb_seances"
        if "nb_seances" in cols else "0 AS nb_seances"
    )
    row = conn.execute(
        f"""
        SELECT ov.id, ov.partie_id, ov.code, ov.nom,
               ov.methode_id, ov.critere_F, ov.critere_A, ov.critere_E,
               ov.fin_cycle,
               {expr_seances},
               sp.numero AS numero_partie,
               me.titre  AS methode_titre
        FROM objectifs ov
        JOIN sequence_parties sp ON sp.id = ov.partie_id
        LEFT JOIN methodes me ON me.id = ov.methode_id
        WHERE ov.id = ?
        """,
        (objectif_id,),
    ).fetchone()
    # _lire_objectif vérifie déjà l'existence, row ne peut pas être None ici.
    return {
        "id":            row["id"],
        "partie_id":     row["partie_id"],
        "code":          row["code"],
        "nom":           row["nom"],
        "methode_id":    row["methode_id"],
        "methode_titre": row["methode_titre"],
        "critere_F":     row["critere_F"],
        "critere_A":     row["critere_A"],
        "critere_E":     row["critere_E"],
        "fin_cycle":     row["fin_cycle"] or "N",
        "nb_seances":    row["nb_seances"],
        "notions":       _lister_notions_objectif(conn, objectif_id),
        "numero_partie": row["numero_partie"],
        "code_coherent": code_coherent_avec_partie(
            row["code"], row["numero_partie"]
        ),
    }


# ── v0.12.0 — Plan de travail générique : nb de séances ──────────────────────
#
# Deux mutations parallèles :
#   - modifier_seances_partie    → sequence_parties.nb_seances_R_AE
#   - modifier_seances_objectif  → objectifs.nb_seances
#
# Validation commune :
#   - accepte int, float, et chaîne convertible en float (pour tolérer
#     l'API HTTP où le payload JSON peut renvoyer "1.5" en string)
#   - refuse < 0, > 999, NaN, None, types incompatibles
#   - aucune contrainte sur les multiples de 0,5 (convention pédago, pas
#     un invariant de stockage)
#
# Pas de wrapper "no-op idempotent" : un PATCH avec la même valeur
# retourne le même état mais réécrit la ligne — sans effet de bord, et
# évite une lecture supplémentaire.

def _valider_nb_seances(valeur) -> float:
    """Valide et normalise un nombre de séances.

    Accepte : int, float, str convertible en float.
    Refuse  : None, types non numériques, < 0, > 999, NaN, infini.
    """
    if valeur is None:
        raise SeancesInvalides(valeur)
    if isinstance(valeur, bool):
        # bool est un int en Python ; on l'écarte explicitement par
        # sécurité (un booléen JSON arrivant ici est forcément une
        # erreur d'intégration côté client).
        raise SeancesInvalides(valeur)
    if isinstance(valeur, (int, float)):
        f = float(valeur)
    elif isinstance(valeur, str):
        try:
            f = float(valeur.strip().replace(",", "."))
        except (ValueError, AttributeError):
            raise SeancesInvalides(valeur)
    else:
        raise SeancesInvalides(valeur)
    # NaN ou infini
    if f != f or f in (float("inf"), float("-inf")):
        raise SeancesInvalides(valeur)
    if f < 0 or f > 999:
        raise SeancesInvalides(valeur)
    return f


def modifier_seances_partie(conn, partie_id: str, nb_seances) -> dict:
    """Met à jour `sequence_parties.nb_seances_R_AE` pour une partie.

    Lève PartieIntrouvable si l'id n'existe pas, SeancesInvalides si la
    valeur est invalide.

    Retourne : {"id": partie_id, "numero": ..., "nb_seances_R_AE": float}.
    """
    partie = _lire_partie(conn, partie_id)
    nb = _valider_nb_seances(nb_seances)
    conn.execute(
        "UPDATE sequence_parties SET nb_seances_R_AE = ? WHERE id = ?",
        (nb, partie_id),
    )
    return {
        "id":              partie_id,
        "numero":          partie["numero"],
        "nb_seances_R_AE": nb,
    }


def modifier_seances_objectif(conn, objectif_id: str, nb_seances) -> dict:
    """Met à jour `objectifs.nb_seances` pour un objectif.

    Cette valeur représente les séances prévues pour cet objectif dans
    le plan de travail générique :
      - pour l'objectif "cours" (code 01/11/21) : séances d'explication
        en classe par l'enseignant
      - pour les autres objectifs : séances de réalisation des exercices
        F/A/E

    Lève ObjectifIntrouvable si l'id n'existe pas, SeancesInvalides si
    la valeur est invalide.

    Retourne la structure habituelle d'un objectif (via
    `_format_retour_objectif`), ce qui permet au frontend de récupérer
    immédiatement la valeur normalisée et tous les champs à jour sans
    re-fetch complet.
    """
    _lire_objectif(conn, objectif_id)
    nb = _valider_nb_seances(nb_seances)
    conn.execute(
        "UPDATE objectifs SET nb_seances = ? WHERE id = ?",
        (nb, objectif_id),
    )
    return _format_retour_objectif(conn, objectif_id)


# ── Édition fin_cycle (v0.6.4) ────────────────────────────────────────────────

def modifier_fin_cycle_objectif(
    conn, objectif_id: str, fin_cycle
) -> dict:
    """Active/désactive le marqueur 'fin de cycle 4' sur un objectif.

    `fin_cycle` accepte :
      - 'O' / True  → marque l'objectif comme attendu de fin de cycle
      - 'N' / False / None / ''  → enlève le marqueur

    Stocké en BDD comme TEXT 'O' ou 'N' (cohérent avec methodes.fin_cycle
    historique). Le stockage en TEXT plutôt qu'en INTEGER respecte la
    convention déjà en place dans le projet pour éviter une migration
    de type sur la base existante.
    """
    _lire_objectif(conn, objectif_id)
    if isinstance(fin_cycle, bool):
        valeur = "O" if fin_cycle else "N"
    elif isinstance(fin_cycle, str):
        valeur = "O" if fin_cycle.strip().upper() in ("O", "OUI", "TRUE", "1") else "N"
    else:
        valeur = "N"
    conn.execute(
        "UPDATE objectifs SET fin_cycle = ? WHERE id = ?",
        (valeur, objectif_id),
    )
    return _format_retour_objectif(conn, objectif_id)


# ── Notions associées à un objectif (v0.6.4) ─────────────────────────────────

def _lister_notions_objectif(conn, objectif_id: str) -> list[dict]:
    """Liste les notions associées à un objectif, ordonnées par `ordre`
    puis par titre de notion. Retourne une liste possiblement vide.

    Chaque entrée contient : id, titre, ordre.
    """
    rows = conn.execute(
        """
        SELECT n.id, n.titre, on_.ordre
        FROM objectif_notions on_
        JOIN notions n ON n.id = on_.notion_id
        WHERE on_.objectif_id = ?
        ORDER BY on_.ordre, n.titre
        """,
        (objectif_id,),
    ).fetchall()
    return [
        {"id": r["id"], "titre": r["titre"] or "", "ordre": r["ordre"]}
        for r in rows
    ]


def ajouter_notion_objectif(
    conn, objectif_id: str, notion_id: str
) -> dict:
    """Associe une notion à un objectif.

    Erreurs possibles :
      - V2EditionErreur si l'objectif n'existe pas (via _lire_objectif)
      - V2EditionErreur si la notion n'existe pas
      - NotionHorsSequence si la notion appartient à une autre séquence
        (v0.10.7 ; tolérance legacy si scope vide)
      - V2EditionErreur si l'association existe déjà (idempotent : on
        ne lève pas mais on retourne silencieusement l'état courant)

    L'ordre est calculé automatiquement comme max(ordre) + 1 pour
    placer la nouvelle notion en fin de liste.

    v0.10.7 — Une notion peut être liée à PLUSIEURS objectifs (cardinalité
    M-N) — c'est même son utilité : par ex. une notion "fonction"
    peut être mobilisée par plusieurs obj exo de la même séquence.
    Mais elle est restreinte au scope (niveau, sequence) de la notion.
    """
    _lire_objectif(conn, objectif_id)
    # Vérifier que la notion existe et lire son scope
    n = conn.execute(
        "SELECT id, niveau, sequence FROM notions WHERE id = ?",
        (notion_id,),
    ).fetchone()
    if n is None:
        raise V2EditionErreur(
            f"Notion introuvable : {notion_id}",
            code="notion_introuvable",
        )

    # v0.10.7 — Scope séquence (tolérance legacy si scope vide)
    n_niveau   = n["niveau"]   or ""
    n_sequence = n["sequence"] or ""
    if n_niveau and n_sequence:
        obj_niveau, obj_sequence = _lire_niv_seq_objectif(conn, objectif_id)
        if n_niveau != obj_niveau or n_sequence != obj_sequence:
            raise NotionHorsSequence(
                notion_id, n_niveau, n_sequence,
                objectif_id, obj_niveau, obj_sequence,
            )

    # Si l'association existe déjà : no-op idempotent
    deja = conn.execute(
        "SELECT 1 FROM objectif_notions WHERE objectif_id = ? AND notion_id = ?",
        (objectif_id, notion_id),
    ).fetchone()
    if deja is None:
        ordre_max = conn.execute(
            "SELECT COALESCE(MAX(ordre), -1) FROM objectif_notions WHERE objectif_id = ?",
            (objectif_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO objectif_notions (objectif_id, notion_id, ordre) "
            "VALUES (?, ?, ?)",
            (objectif_id, notion_id, ordre_max + 1),
        )
    return _format_retour_objectif(conn, objectif_id)


def retirer_notion_objectif(
    conn, objectif_id: str, notion_id: str
) -> dict:
    """Dissocie une notion d'un objectif. Idempotent : aucune erreur si
    l'association n'existait pas."""
    _lire_objectif(conn, objectif_id)
    conn.execute(
        "DELETE FROM objectif_notions WHERE objectif_id = ? AND notion_id = ?",
        (objectif_id, notion_id),
    )
    return _format_retour_objectif(conn, objectif_id)


# ── Catalogue de méthodes (lecture seule) ────────────────────────────────────

def lister_methodes_de_sequence(conn, niveau: str, sequence: str) -> list[dict]:
    """Retourne les méthodes rattachées à une (niveau, sequence), triées
    par titre. Liste potentiellement vide (aucun throw).

    Filtre sur les métadonnées `niveau`/`sequence` de la table `methodes`
    — ces colonnes ont été ajoutées en v0.6.3e précisément pour ce type
    de requête.
    """
    rows = conn.execute(
        """
        SELECT id, titre, num_methode, num_objectif, fichier, etat_code
        FROM methodes
        WHERE niveau = ? AND sequence = ?
        ORDER BY num_methode, titre
        """,
        (niveau, sequence),
    ).fetchall()
    return [
        {
            "id":            r["id"],
            "titre":         r["titre"] or "",
            "num_methode":   r["num_methode"],
            "num_objectif":  r["num_objectif"],
            "fichier":       r["fichier"],
            # v0.10.4 — état d'édition pour badge dans la sidebar
            "etat_code":     r["etat_code"] or "en_cours",
        }
        for r in rows
    ]


def lister_notions_de_sequence(conn, niveau: str, sequence: str) -> list[dict]:
    """Retourne les notions rattachées à une (niveau, sequence), triées par
    num_connaissance puis titre.

    Symétrique de lister_methodes_de_sequence, utilisée par seqniv pour
    peupler le <select> d'ajout de notion à un objectif.
    """
    rows = conn.execute(
        """
        SELECT id, titre, num_connaissance, fichier, etat_code
        FROM notions
        WHERE niveau = ? AND sequence = ?
        ORDER BY num_connaissance, titre
        """,
        (niveau, sequence),
    ).fetchall()
    return [
        {
            "id":               r["id"],
            "titre":            r["titre"] or "",
            "num_connaissance": r["num_connaissance"],
            "fichier":          r["fichier"],
            # v0.10.4 — état d'édition pour badge dans la sidebar
            "etat_code":        r["etat_code"] or "en_cours",
        }
        for r in rows
    ]


# ═════════════════════════════════════════════════════════════════════════════
# R4e4b — Édition des exos d'un objectif par série
# ═════════════════════════════════════════════════════════════════════════════
#
# Cinq fonctions : ajouter, retirer, réordonner, + deux fonctions de
# catalogue (lister les exos disponibles à l'ajout, pour séries normales
# vs. série R).
#
# Contrats :
#   - Ajout : si série ∈ {EA, F, A, E}, origin_* doivent être tous NULL.
#             si série = R, origin_niveau, origin_seq, origin_serie sont
#             requis (origin_num optionnel, rempli auto depuis `exercices`).
#   - Retrait : après suppression, recompactage dense des ordres (1, 2, 3...).
#   - Réordonnancement : la liste passée doit contenir EXACTEMENT les
#     mêmes exercice_ids que l'ensemble actuel (ni création, ni suppression).
#
# Retour : toutes les mutations renvoient un dict avec la liste complète
# à jour des exos de la (objectif, série), au même format que celui de
# `v2_lecture._charger_exos_par_serie` pour un rafraîchissement simple
# côté UI.

_SERIES_VALIDES = ("AE", "F", "A", "E")  # v0.18.3 : 'EA'→'AE' (cf. SERIES_V2)

# Mapping série v2 → serie_code dans la table `exercices`.
# v0.18.3 — Unification : la série « approche » a pour code 'AE' partout
# (front, API, base, affichage). Le mapping est devenu une identité ; on le
# conserve pour ne pas disperser les call-sites et documenter l'intention.
# NB : ne pas confondre avec le RÔLE 'EA' (approche) d'un exo dans une partie
# (table partie_exos_revision_approche.type), qui reste 'EA' — c'est un rôle,
# pas un serie_code.
_SERIE_CODE_EQUIVALENT = {
    "AE": "AE",
    "F":  "F",
    "A":  "A",
    "E":  "E",
}


def _valider_serie(serie):
    if not isinstance(serie, str) or serie not in _SERIES_VALIDES:
        raise SerieInvalide(serie)
    return serie


def _lire_exercice(conn, exercice_id):
    row = conn.execute(
        "SELECT id, niveau, sequence, num, serie_code, fichier "
        "FROM exercices WHERE id = ?",
        (exercice_id,),
    ).fetchone()
    if row is None:
        raise ExerciceIntrouvable(exercice_id)
    return row


def _charger_exos_de_objectif_serie(conn, objectif_id: str, serie: str) -> list[dict]:
    """Retourne la liste des exos d'une (objectif, série) au format
    conforme à v2_lecture._charger_exos_par_serie, triée par ordre dense.

    Le frontend reçoit exactement le même objet qu'à la lecture initiale,
    ce qui permet une mise à jour incrémentale simple.
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
            ex.serie_code     AS exercice_serie_code
        FROM objectif_exos oe
        LEFT JOIN exercices ex ON ex.id = oe.exercice_id
        WHERE oe.objectif_id = ? AND oe.serie = ?
        ORDER BY oe.ordre
        """,
        (objectif_id, serie),
    ).fetchall()

    return [
        {
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
            },
        }
        for r in rows
    ]


def _formater_retour_exos(conn, objectif_id, serie):
    """Format de retour standard des mutations d'exos."""
    return {
        "objectif_id": objectif_id,
        "serie":       serie,
        "exos":        _charger_exos_de_objectif_serie(conn, objectif_id, serie),
    }


# ── Ajouter ──────────────────────────────────────────────────────────────────

def ajouter_exo_a_objectif(
    conn,
    objectif_id: str,
    serie: str,
    exercice_id: str,
    origin_niveau: str | None = None,
    origin_seq: str | None = None,
    origin_serie: str | None = None,
) -> dict:
    """Ajoute un exo à une (objectif, série). Calcule l'ordre suivant
    automatiquement (max + 1). Renseigne `origin_num` depuis
    `exercices.num` si connu, pour la traçabilité.

    Règles métier (v0.11.2 — simplifiée) :
      - séries EA/F/A/E : les 3 origin_* doivent être None ou absents.

    NB v0.11.2 : la série 'R' a été supprimée. Les colonnes
    objectif_exos.origin_* (qui ne servaient qu'à la série R) sont
    désormais toujours NULL pour toute nouvelle écriture. Elles
    persistent au schéma pour rétrocompatibilité (cf. roadmap 3-full).
    """
    _lire_objectif(conn, objectif_id)
    serie = _valider_serie(serie)
    exo_row = _lire_exercice(conn, exercice_id)

    # v0.11.2 — les colonnes origin_* n'ont plus de série qui les justifie.
    # On rejette toute tentative de les renseigner.
    origin_fournie = any(
        v is not None and v != "" for v in (origin_niveau, origin_seq, origin_serie)
    )
    if origin_fournie:
        raise OriginInvalide(
            f"Les champs origin_* ne sont plus autorisés (série {serie!r}). "
            "La série 'R' qui en faisait usage a été supprimée en v0.11.2.",
            serie=serie,
            origin_niveau=origin_niveau,
            origin_seq=origin_seq,
            origin_serie=origin_serie,
        )
    origin_niveau = origin_seq = origin_serie = None

    # Conflit : exo déjà présent dans cette (objectif, série) ?
    conflit = conn.execute(
        "SELECT 1 FROM objectif_exos "
        "WHERE objectif_id = ? AND serie = ? AND exercice_id = ?",
        (objectif_id, serie, exercice_id),
    ).fetchone()
    if conflit:
        raise ExoDejaPresent(objectif_id, serie, exercice_id)

    # Calcul de l'ordre suivant (max + 1, ou 1 si vide)
    max_row = conn.execute(
        "SELECT COALESCE(MAX(ordre), 0) AS m FROM objectif_exos "
        "WHERE objectif_id = ? AND serie = ?",
        (objectif_id, serie),
    ).fetchone()
    ordre_nouveau = (max_row["m"] or 0) + 1

    # origin_num : pour R, on reprend exercices.num de l'exo source.
    # Pour les autres séries, c'est une métadonnée non pertinente — on
    # met quand même exercices.num au cas où, c'est une info facultative.
    origin_num = exo_row["num"]

    conn.execute(
        "INSERT INTO objectif_exos "
        "(objectif_id, serie, exercice_id, ordre, "
        " origin_niveau, origin_seq, origin_serie, origin_num) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (objectif_id, serie, exercice_id, ordre_nouveau,
         origin_niveau, origin_seq, origin_serie, origin_num),
    )
    return _formater_retour_exos(conn, objectif_id, serie)


# ── Retirer ──────────────────────────────────────────────────────────────────

def retirer_exo_de_objectif(
    conn,
    objectif_id: str,
    serie: str,
    exercice_id: str,
) -> dict:
    """Retire l'exo de la (objectif, série) et recompacte les ordres
    (1, 2, 3... dense). 404 si la ligne n'existe pas."""
    _lire_objectif(conn, objectif_id)
    serie = _valider_serie(serie)

    existe = conn.execute(
        "SELECT 1 FROM objectif_exos "
        "WHERE objectif_id = ? AND serie = ? AND exercice_id = ?",
        (objectif_id, serie, exercice_id),
    ).fetchone()
    if not existe:
        raise ExoIntrouvableDansObjectif(objectif_id, serie, exercice_id)

    conn.execute(
        "DELETE FROM objectif_exos "
        "WHERE objectif_id = ? AND serie = ? AND exercice_id = ?",
        (objectif_id, serie, exercice_id),
    )

    _recompacter_ordres(conn, objectif_id, serie)
    return _formater_retour_exos(conn, objectif_id, serie)


def _recompacter_ordres(conn, objectif_id: str, serie: str) -> None:
    """Réécrit les `ordre` en 1, 2, 3... en respectant l'ordre courant.

    Technique : pour contourner UNIQUE(objectif_id, serie, ordre), on
    passe d'abord par des valeurs négatives temporaires, puis on fixe
    les valeurs finales.
    """
    rows = conn.execute(
        "SELECT exercice_id FROM objectif_exos "
        "WHERE objectif_id = ? AND serie = ? "
        "ORDER BY ordre",
        (objectif_id, serie),
    ).fetchall()

    if not rows:
        return

    # Phase 1 : ordres négatifs temporaires (−1, −2, ...)
    for i, r in enumerate(rows, start=1):
        conn.execute(
            "UPDATE objectif_exos SET ordre = ? "
            "WHERE objectif_id = ? AND serie = ? AND exercice_id = ?",
            (-i, objectif_id, serie, r["exercice_id"]),
        )
    # Phase 2 : ordres finaux (1, 2, ...)
    for i, r in enumerate(rows, start=1):
        conn.execute(
            "UPDATE objectif_exos SET ordre = ? "
            "WHERE objectif_id = ? AND serie = ? AND exercice_id = ?",
            (i, objectif_id, serie, r["exercice_id"]),
        )


# ── Réordonner ───────────────────────────────────────────────────────────────

def reordonner_exos(
    conn,
    objectif_id: str,
    serie: str,
    exercice_ids_dans_ordre: list[str],
) -> dict:
    """Réécrit les `ordre` selon la liste passée.

    Validation stricte : la liste doit contenir exactement les mêmes
    exercice_ids que ce qui est en base, ni plus, ni moins, sans
    doublon. On ne crée ni ne supprime d'exos ici.

    Technique : même astuce que dans _recompacter_ordres (passage par
    valeurs négatives pour éviter les collisions sur UNIQUE).
    """
    _lire_objectif(conn, objectif_id)
    serie = _valider_serie(serie)

    if not isinstance(exercice_ids_dans_ordre, list):
        raise ReordonnancementInvalide(
            "exercice_ids_dans_ordre doit être une liste.",
            recu=type(exercice_ids_dans_ordre).__name__,
        )

    # Doublons dans la liste ?
    if len(exercice_ids_dans_ordre) != len(set(exercice_ids_dans_ordre)):
        raise ReordonnancementInvalide(
            "La liste contient des doublons.",
            liste=exercice_ids_dans_ordre,
        )

    # Ensemble en base
    rows_base = conn.execute(
        "SELECT exercice_id FROM objectif_exos "
        "WHERE objectif_id = ? AND serie = ?",
        (objectif_id, serie),
    ).fetchall()
    ids_base = {r["exercice_id"] for r in rows_base}
    ids_demandes = set(exercice_ids_dans_ordre)

    if ids_base != ids_demandes:
        manquants = ids_base - ids_demandes
        ajouts = ids_demandes - ids_base
        raise ReordonnancementInvalide(
            "La liste ne correspond pas exactement aux exos présents : "
            f"manquants={sorted(manquants)}, inconnus={sorted(ajouts)}.",
            manquants=sorted(manquants),
            inconnus=sorted(ajouts),
        )

    # Phase 1 : ordres négatifs
    for i, exid in enumerate(exercice_ids_dans_ordre, start=1):
        conn.execute(
            "UPDATE objectif_exos SET ordre = ? "
            "WHERE objectif_id = ? AND serie = ? AND exercice_id = ?",
            (-i, objectif_id, serie, exid),
        )
    # Phase 2 : ordres finaux
    for i, exid in enumerate(exercice_ids_dans_ordre, start=1):
        conn.execute(
            "UPDATE objectif_exos SET ordre = ? "
            "WHERE objectif_id = ? AND serie = ? AND exercice_id = ?",
            (i, objectif_id, serie, exid),
        )

    return _formater_retour_exos(conn, objectif_id, serie)


# ── Catalogues d'exos disponibles à l'ajout ─────────────────────────────────

def lister_exos_disponibles(
    conn,
    niveau: str,
    sequence: str,
    serie_cible: str,
    objectif_id: str | None = None,
) -> list[dict]:
    """Retourne les exos de (niveau, sequence) compatibles avec serie_cible
    (EA/F/A/E), filtrés pour exclure ceux déjà présents dans la (objectif,
    serie_cible) si `objectif_id` est fourni.

    v0.11.2 — La série 'R' a été retirée. La fonction historique
    `lister_exos_disponibles_pour_revision` reste utilisée par l'atelier
    d'assemblage pour piocher des exos d'autres séquences (typiquement N-1
    série A) vers la table partie_exos_revision_approche, sans transiter
    par objectif_exos.
    """
    serie_cible = _valider_serie(serie_cible)
    # v0.11.2 — la branche `if serie_cible == "R": return []` a été retirée :
    # `_valider_serie` rejette désormais 'R' (n'est plus dans _SERIES_VALIDES).

    serie_code = _SERIE_CODE_EQUIVALENT.get(serie_cible)
    if serie_code is None:
        return []

    # Ensemble des exos déjà présents à exclure
    exclure: set[str] = set()
    if objectif_id:
        rows_dejapres = conn.execute(
            "SELECT exercice_id FROM objectif_exos "
            "WHERE objectif_id = ? AND serie = ?",
            (objectif_id, serie_cible),
        ).fetchall()
        exclure = {r["exercice_id"] for r in rows_dejapres}

    rows = conn.execute(
        """
        SELECT id, titre, fichier, niveau, sequence, num, serie_code, etat_code
        FROM exercices
        WHERE niveau = ? AND sequence = ? AND serie_code = ?
        ORDER BY num, fichier
        """,
        (niveau, sequence, serie_code),
    ).fetchall()

    return [
        {
            "id":         r["id"],
            "titre":      r["titre"] or "",
            "fichier":    r["fichier"] or "",
            "niveau":     r["niveau"] or "",
            "sequence":   r["sequence"] or "",
            "num":        r["num"],
            "serie_code": r["serie_code"] or "",
            # v0.10.4 — état d'édition pour badge dans la sidebar
            "etat_code":  r["etat_code"] or "en_cours",
        }
        for r in rows
        if r["id"] not in exclure
    ]


def lister_exos_disponibles_pour_revision(
    conn,
    origin_niveau: str,
    origin_seq: str,
) -> list[dict]:
    """Retourne tous les exos de (origin_niveau, origin_seq) pour piocher
    en série R. Inclut toutes les séries d'origine (F, A, E, AE) : c'est
    l'enseignant qui choisit. Le frontend affichera le serie_code de
    chaque entrée pour que le choix soit éclairé.

    Contrairement à lister_exos_disponibles, on ne filtre PAS ici sur
    les exos déjà présents — le même exercice peut légitimement apparaître
    en R d'un objectif ET en F d'un autre ; l'UI appelante peut appliquer
    un filtre d'exclusion si nécessaire via ?objectif_id= côté route.
    """
    rows = conn.execute(
        """
        SELECT id, titre, fichier, niveau, sequence, num, serie_code, etat_code
        FROM exercices
        WHERE niveau = ? AND sequence = ?
        ORDER BY serie_code, num, fichier
        """,
        (origin_niveau, origin_seq),
    ).fetchall()
    return [
        {
            "id":         r["id"],
            "titre":      r["titre"] or "",
            "fichier":    r["fichier"] or "",
            "niveau":     r["niveau"] or "",
            "sequence":   r["sequence"] or "",
            "num":        r["num"],
            "serie_code": r["serie_code"] or "",
            # v0.10.4 — état d'édition pour badge dans la sidebar
            "etat_code":  r["etat_code"] or "en_cours",
        }
        for r in rows
    ]


# ═════════════════════════════════════════════════════════════════════════════
# v0.10 — Atelier d'assemblage : nouveaux services
# ═════════════════════════════════════════════════════════════════════════════
#
# Trois axes :
#   1. Réordonnancement par drag-and-drop
#       - reordonner_parties        : les parties d'une séquence (renumérotation
#                                     1..N atomique)
#       - reordonner_objectifs_dans_partie : les objectifs *dans* une partie
#                                     (renomme les codes selon la position)
#       - reordonner_exos_revision_approche : les exos R/EA *dans* une partie
#   2. Activation de l'objectif "Connaître les notions et les méthodes"
#       - activer_objectif_connaitre : crée l'obj '0X' (X = numero_partie - 1)
#         avec critères pré-remplis fournis par l'appelant
#   3. Exos de révision/approche au niveau partie
#       - ajouter_exo_revision_approche / retirer_exo_revision_approche
#       - lister_exos_revision_approche
#
# Plus la persistance UI :
#   - lire_etat_ui_atelier_sequence / ecrire_etat_ui_atelier_sequence

# ── Helper : code de l'objectif "Connaître" pour une partie donnée ───────────

def code_objectif_connaitre(numero_partie: int) -> str:
    """Convention : '01' partie 1, '11' partie 2, '21' partie 3, etc.

    Lève NumeroPartieInvalide si numero_partie < 1.
    """
    n = _valider_numero(numero_partie)
    return f"{n - 1}1"


# ── Réordonnancement des parties ────────────────────────────────────────────

def reordonner_parties(
    conn,
    sequence_par_niveau_id: str,
    partie_ids_dans_ordre: list[str],
) -> list[dict]:
    """Réécrit les `numero` des parties de la séquence selon la liste passée.

    La nouvelle position dans la liste devient le nouveau numéro (1..N).
    La renumérotation est atomique : passage par numéros négatifs pour
    éviter les collisions sur UNIQUE(sequence_par_niveau_id, numero), comme
    dans reordonner_exos.

    **Effet de bord** : les codes des objectifs ne sont PAS automatiquement
    renumérotés. La convention "code 0X en partie 1, 1X en partie 2..." sera
    visible comme "incohérente" via code_coherent_avec_partie() si l'utilisateur
    ne lance pas en complément reordonner_objectifs_dans_partie() après le
    swap. C'est volontaire : on garde reordonner_parties() comme une primitive
    bas niveau ; l'orchestration code-renumérotation-après-swap est faite
    côté frontend (qui appelle les deux fonctions à la suite quand il faut).

    Validation stricte : la liste doit contenir exactement les mêmes
    partie_ids que ceux présents en base pour cette séquence.

    Retourne la liste finale [{id, numero}, ...] dans l'ordre demandé.
    """
    _lire_sequence_par_niveau(conn, sequence_par_niveau_id)

    if not isinstance(partie_ids_dans_ordre, list):
        raise ReordonnancementInvalide(
            "partie_ids_dans_ordre doit être une liste.",
            recu=type(partie_ids_dans_ordre).__name__,
        )
    if len(partie_ids_dans_ordre) != len(set(partie_ids_dans_ordre)):
        raise ReordonnancementInvalide(
            "La liste contient des doublons.",
            liste=partie_ids_dans_ordre,
        )

    rows_base = conn.execute(
        "SELECT id FROM sequence_parties WHERE sequence_par_niveau_id = ?",
        (sequence_par_niveau_id,),
    ).fetchall()
    ids_base = {r["id"] for r in rows_base}
    ids_demandes = set(partie_ids_dans_ordre)

    if ids_base != ids_demandes:
        manquants = ids_base - ids_demandes
        inconnus = ids_demandes - ids_base
        raise ReordonnancementInvalide(
            "La liste ne correspond pas exactement aux parties présentes : "
            f"manquants={sorted(manquants)}, inconnus={sorted(inconnus)}.",
            manquants=sorted(manquants),
            inconnus=sorted(inconnus),
        )

    # Phase 1 : numéros négatifs (évite collision UNIQUE)
    for i, pt_id in enumerate(partie_ids_dans_ordre, start=1):
        conn.execute(
            "UPDATE sequence_parties SET numero = ? WHERE id = ?",
            (-i, pt_id),
        )
    # Phase 2 : numéros finaux
    for i, pt_id in enumerate(partie_ids_dans_ordre, start=1):
        conn.execute(
            "UPDATE sequence_parties SET numero = ? WHERE id = ?",
            (i, pt_id),
        )

    return [
        {"id": pt_id, "numero": i}
        for i, pt_id in enumerate(partie_ids_dans_ordre, start=1)
    ]


# ── Réordonnancement des objectifs DANS une partie ──────────────────────────

def reordonner_objectifs_dans_partie(
    conn,
    partie_id: str,
    objectif_ids_dans_ordre: list[str],
) -> list[dict]:
    """Réécrit les codes des objectifs d'une partie selon leur nouvelle
    position dans la liste.

    Convention appliquée :
      - L'objectif "Connaître" (code se terminant par '1' avec premier chiffre
        cohérent : '01' en partie 1, '11' en partie 2, etc.) reste TOUJOURS
        en première position et garde son code. Si un tel objectif est dans
        la liste, il doit être en position 0 ; sinon ReordonnancementInvalide.
      - Les autres objectifs prennent successivement les codes 'X2', 'X3',
        'X4'... où X = numero_partie - 1.

    Validation stricte : la liste doit contenir exactement les mêmes objectif_ids
    que ceux présents dans la partie.

    Atomicité : pour éviter les collisions UNIQUE(partie_id, code), on passe
    par des codes temporaires '~0', '~1'... avant d'écrire les codes finaux.

    Retourne la liste finale [{id, code}, ...] dans l'ordre demandé.
    """
    partie = _lire_partie(conn, partie_id)
    numero = partie["numero"]
    prefixe = numero - 1   # 0 pour partie 1, 1 pour partie 2...
    code_connaitre = f"{prefixe}1"

    if not isinstance(objectif_ids_dans_ordre, list):
        raise ReordonnancementInvalide(
            "objectif_ids_dans_ordre doit être une liste.",
            recu=type(objectif_ids_dans_ordre).__name__,
        )
    if len(objectif_ids_dans_ordre) != len(set(objectif_ids_dans_ordre)):
        raise ReordonnancementInvalide(
            "La liste contient des doublons.",
            liste=objectif_ids_dans_ordre,
        )

    rows_base = conn.execute(
        "SELECT id, code FROM objectifs WHERE partie_id = ?",
        (partie_id,),
    ).fetchall()
    ids_base = {r["id"] for r in rows_base}
    ids_demandes = set(objectif_ids_dans_ordre)

    if ids_base != ids_demandes:
        manquants = ids_base - ids_demandes
        inconnus = ids_demandes - ids_base
        raise ReordonnancementInvalide(
            "La liste ne correspond pas exactement aux objectifs présents : "
            f"manquants={sorted(manquants)}, inconnus={sorted(inconnus)}.",
            manquants=sorted(manquants),
            inconnus=sorted(inconnus),
        )

    # Si un objectif "Connaître" existe (code = code_connaitre), il doit
    # être en première position.
    code_par_id = {r["id"]: r["code"] for r in rows_base}
    id_connaitre = next(
        (oid for oid, code in code_par_id.items() if code == code_connaitre),
        None,
    )
    if id_connaitre is not None:
        if not objectif_ids_dans_ordre or objectif_ids_dans_ordre[0] != id_connaitre:
            raise ReordonnancementInvalide(
                "L'objectif Connaître doit rester en première position dans "
                "sa partie.",
                code_connaitre=code_connaitre,
                objectif_connaitre_id=id_connaitre,
            )

    # Phase 1 : codes temporaires uniques (jamais en collision avec un
    # code numérique standard)
    for i, ob_id in enumerate(objectif_ids_dans_ordre, start=1):
        conn.execute(
            "UPDATE objectifs SET code = ? WHERE id = ?",
            (f"~tmp{i}", ob_id),
        )

    # Phase 2 : codes finaux
    nouveaux_codes: list[dict] = []
    for i, ob_id in enumerate(objectif_ids_dans_ordre):
        # Position 0 → code '0X1' (Connaître) ou code 'X2' selon présence
        # Si on a un Connaître, position 0 = code_connaitre ; positions 1..N = X2..
        # Si on n'a pas de Connaître, position 0..N-1 = X2..X(N+1)
        if i == 0 and id_connaitre is not None:
            nouveau = code_connaitre
        else:
            offset_dans_serie_normale = i if id_connaitre is None else (i - 1)
            # X2, X3, X4, ...
            nouveau = f"{prefixe}{offset_dans_serie_normale + 2}"
        conn.execute(
            "UPDATE objectifs SET code = ? WHERE id = ?",
            (nouveau, ob_id),
        )
        nouveaux_codes.append({"id": ob_id, "code": nouveau})

    return nouveaux_codes


# ── v0.12.3.0 — Déplacement atomique d'un objectif (inter-partie + position) ─

def deplacer_objectif_avec_position(
    conn,
    objectif_id: str,
    partie_cible_id: str,
    position_dans_cible: int,
) -> dict:
    """Déplace un objectif d'une partie à une autre dans la même séquence-niveau,
    en l'insérant à une position précise dans la partie cible. Recalcule les
    codes des objectifs des **deux** parties (source et cible) en cohérence
    avec leur nouvel ordre.

    Cette fonction est conçue pour le frontend drag-and-drop (v0.12.3.0) qui
    a porté cette fonctionnalité depuis l'éditeur v2 historique (supprimé
    en v0.12.3.1). Différence majeure avec `reassigner_objectif_a_partie` : cette dernière
    préserve le code de l'objectif et peut donc échouer en `conflit_code_dans_
    partie_cible`. Ici on **réordonne** dans les deux parties pour produire des
    codes cohérents avec les positions, ce qui exclut le conflit.

    Atomicité : le tout passe en une seule transaction sqlite (le `with conn`
    de l'appelant). Codes temporaires `~tmp1`, `~tmp2`... pour éviter les
    collisions UNIQUE pendant la phase intermédiaire.

    Cas particuliers :
      - Si `objectif_id` est l'objectif "Connaître" (code 01/11/21...) de sa
        partie source : refus (`ReordonnancementInvalide`, motif
        "connaitre_non_deplaceable"). Le Cours est ancré en position 1 de sa
        partie d'origine.
      - Si la partie cible a déjà un Cours : `position_dans_cible` doit être
        ≥ 1 (le Cours reste en 0). Sinon refus.
      - Si la partie cible n'a PAS de Cours : `position_dans_cible` peut être
        0 (l'objectif déplacé prendra le code "X2" de la partie cible).
      - Si partie source = partie cible : équivalent à un réordonnancement
        intra-partie ; on délègue à `reordonner_objectifs_dans_partie` (qui
        recalcule les codes).

    Lève `ReassignationImpossible` si :
      - les deux parties ne sont pas dans la même séquence-niveau
    Lève `ReordonnancementInvalide` si :
      - la position est hors bornes (négative, ou > nb_objs_cible_actuels)
      - on tente de déplacer le Cours depuis sa partie source
      - on tente de placer un objectif en position 0 alors qu'un Cours
        existe en position 0 de la partie cible

    Retourne :
      {
        "objectif_id":           id de l'objectif déplacé,
        "code_apres":            son nouveau code après recalcul cible,
        "partie_source_id":      id de la partie source,
        "partie_cible_id":       id de la partie cible,
        "objectifs_source":      [{id, code}, ...] dans l'ordre final,
        "objectifs_cible":       [{id, code}, ...] dans l'ordre final,
      }
    """
    obj = _lire_objectif(conn, objectif_id)
    partie_source = _lire_partie(conn, obj["partie_id"])
    partie_cible = _lire_partie(conn, partie_cible_id)

    # Hors séquence ?
    if partie_source["sequence_par_niveau_id"] != partie_cible["sequence_par_niveau_id"]:
        raise ReassignationImpossible(
            "La partie cible appartient à une autre séquence par niveau. "
            "Le déplacement n'est autorisé qu'à l'intérieur de la même "
            "séquence par niveau.",
            "partie_hors_sequence",
            objectif_id=objectif_id,
            partie_id_cible=partie_cible_id,
        )

    # Cours non déplaçable ?
    code_connaitre_source = f"{partie_source['numero'] - 1}1"
    if obj["code"] == code_connaitre_source:
        raise ReordonnancementInvalide(
            "L'objectif Connaître/Cours ne peut pas être déplacé : il reste "
            "ancré en première position de sa partie d'origine.",
            objectif_connaitre_id=objectif_id,
            code_connaitre=code_connaitre_source,
        )

    # Cas dégénéré : même partie ⇒ réordonnancement intra-partie pur.
    if partie_source["id"] == partie_cible["id"]:
        ids_actuels = [
            r["id"] for r in conn.execute(
                "SELECT id FROM objectifs WHERE partie_id = ? "
                "ORDER BY (CASE WHEN code = ? THEN 0 ELSE 1 END), code",
                (partie_cible_id, f"{partie_cible['numero'] - 1}1"),
            ).fetchall()
        ]
        ids_sans = [i for i in ids_actuels if i != objectif_id]
        position_clipped = max(0, min(position_dans_cible, len(ids_sans)))
        nouvel_ordre = (
            ids_sans[:position_clipped] + [objectif_id] + ids_sans[position_clipped:]
        )
        objs_cible = reordonner_objectifs_dans_partie(
            conn, partie_cible_id, nouvel_ordre,
        )
        # Code après : retrouver dans la liste retournée
        code_apres = next(
            (o["code"] for o in objs_cible if o["id"] == objectif_id),
            obj["code"],
        )
        return {
            "objectif_id":      objectif_id,
            "code_apres":       code_apres,
            "partie_source_id": partie_source["id"],
            "partie_cible_id":  partie_cible_id,
            "objectifs_source": objs_cible,   # même partie, même contenu
            "objectifs_cible":  objs_cible,
        }

    # Cas général : déplacement inter-partie.
    # 1. Préparer le nouvel ordre dans la partie cible.
    code_connaitre_cible = f"{partie_cible['numero'] - 1}1"
    rows_cible = conn.execute(
        "SELECT id, code FROM objectifs WHERE partie_id = ? "
        "ORDER BY (CASE WHEN code = ? THEN 0 ELSE 1 END), code",
        (partie_cible_id, code_connaitre_cible),
    ).fetchall()
    ids_cible_actuels = [r["id"] for r in rows_cible]
    has_connaitre_cible = any(r["code"] == code_connaitre_cible for r in rows_cible)

    # Vérifier la position demandée
    if position_dans_cible < 0 or position_dans_cible > len(ids_cible_actuels):
        raise ReordonnancementInvalide(
            f"Position {position_dans_cible} hors bornes pour la partie cible "
            f"({len(ids_cible_actuels)} objectifs actuellement présents). "
            f"Position attendue : 0 à {len(ids_cible_actuels)} inclus.",
            position=position_dans_cible,
            nb_objectifs_cible=len(ids_cible_actuels),
        )

    # Si Cours en partie cible, refuser position 0
    if has_connaitre_cible and position_dans_cible == 0:
        raise ReordonnancementInvalide(
            "Impossible de placer un objectif en position 0 : la partie cible "
            "contient déjà un objectif Connaître/Cours en première position.",
            partie_cible_id=partie_cible_id,
        )

    # Insérer objectif_id à position_dans_cible
    nouvel_ordre_cible = (
        ids_cible_actuels[:position_dans_cible]
        + [objectif_id]
        + ids_cible_actuels[position_dans_cible:]
    )

    # 2. Préparer le nouvel ordre dans la partie source (objectif retiré).
    rows_source = conn.execute(
        "SELECT id FROM objectifs WHERE partie_id = ? AND id != ? "
        "ORDER BY (CASE WHEN code = ? THEN 0 ELSE 1 END), code",
        (partie_source["id"], objectif_id, code_connaitre_source),
    ).fetchall()
    nouvel_ordre_source = [r["id"] for r in rows_source]

    # 3. Phase A : passer l'objectif déplacé à la partie cible avec un code
    #    temporaire unique. Cela libère son code dans la source.
    conn.execute(
        "UPDATE objectifs SET partie_id = ?, code = ? WHERE id = ?",
        (partie_cible_id, "~mig", objectif_id),
    )

    # 4. Phase B : recalculer les codes de la partie source (sans l'objectif
    #    qui en est sorti). Pas d'erreur attendue ici, l'ordre est complet.
    objs_source = reordonner_objectifs_dans_partie(
        conn, partie_source["id"], nouvel_ordre_source,
    )

    # 5. Phase C : recalculer les codes de la partie cible (avec l'objectif
    #    qui vient d'arriver, à la position voulue).
    objs_cible = reordonner_objectifs_dans_partie(
        conn, partie_cible_id, nouvel_ordre_cible,
    )

    code_apres = next(
        (o["code"] for o in objs_cible if o["id"] == objectif_id),
        "?",
    )
    return {
        "objectif_id":      objectif_id,
        "code_apres":       code_apres,
        "partie_source_id": partie_source["id"],
        "partie_cible_id":  partie_cible_id,
        "objectifs_source": objs_source,
        "objectifs_cible":  objs_cible,
    }


# ── Activation de l'objectif "Connaître" ────────────────────────────────────

def activer_objectif_connaitre(
    conn,
    partie_id: str,
    nom: str = "Connaître les notions et les méthodes",
    critere_F: str = "",
    critere_A: str = "",
    critere_E: str = "",
) -> dict:
    """Crée l'objectif "Connaître les notions et les méthodes" dans une partie.

    Le code est calculé automatiquement via code_objectif_connaitre() :
    '01' en partie 1, '11' en partie 2, '21' en partie 3...

    Refuse (409 ObjectifConnaitreDejaPresent) si un objectif avec ce code
    existe déjà dans la partie.

    Les critères pré-remplis sont passés par l'appelant (configurables côté
    UI Préférences). Si fournis vides, l'objectif sera créé avec critères
    vides — l'utilisateur les remplira ensuite.

    Retourne la structure habituelle d'un objectif (via _format_retour_objectif).
    """
    partie = _lire_partie(conn, partie_id)
    code = code_objectif_connaitre(partie["numero"])

    # Vérifier qu'il n'existe pas déjà
    deja = conn.execute(
        "SELECT id FROM objectifs WHERE partie_id = ? AND code = ?",
        (partie_id, code),
    ).fetchone()
    if deja:
        raise ObjectifConnaitreDejaPresent(partie_id, code)

    ob_id = nouveau_id_objectif()
    conn.execute(
        """
        INSERT INTO objectifs
            (id, partie_id, code, nom, methode_id,
             critere_F, critere_A, critere_E, fin_cycle)
        VALUES (?, ?, ?, ?, NULL, ?, ?, ?, 'N')
        """,
        (ob_id, partie_id, code, nom or "",
         critere_F or "", critere_A or "", critere_E or ""),
    )
    return _format_retour_objectif(conn, ob_id)


def creer_objectif_simple(
    conn,
    partie_id: str,
    nom: str = "",
    methode_id: str | None = None,
    critere_F: str = "",
    critere_A: str = "",
    critere_E: str = "",
) -> dict:
    """v0.10.1 — Crée un objectif "simple" dans une partie, avec un code
    auto-incrémenté respectant la convention '0X/1X/2X'.

    Stratégie de code :
      - prefixe = numero_partie - 1 (chiffre des dizaines)
      - on cherche le prochain code 'PX' libre, en commençant par
        prefixe*10+2 si prefixe*10+1 (= code Connaître) est pris,
        sinon prefixe*10+1.
      - en cas de débordement (>9 codes), on continue avec 'X10' etc. mais
        ce cas est extrêmement rare en usage pédagogique.

    Si `methode_id` est fourni, vérifie qu'il existe et le lie à l'objectif.

    Cas d'usage principal : drop d'une méthode dans une partie depuis le
    nouvel atelier d'assemblage (v0.10.1).

    Retourne la structure habituelle d'un objectif.
    """
    partie = _lire_partie(conn, partie_id)
    prefixe = partie["numero"] - 1   # 0 pour partie 1, 1 pour partie 2…

    if methode_id:
        # Vérifier existence
        ligne = conn.execute(
            "SELECT id FROM methodes WHERE id = ?",
            (methode_id,),
        ).fetchone()
        if ligne is None:
            raise MethodeIntrouvable(methode_id)

    # Codes déjà pris dans la partie
    pris = {
        r["code"] for r in conn.execute(
            "SELECT code FROM objectifs WHERE partie_id = ?",
            (partie_id,),
        )
    }

    # Trouver le prochain code libre. On essaie 1, 2, 3, ... 9 puis 10, 11...
    for chiffre in range(1, 100):
        code = f"{prefixe}{chiffre}"
        if code not in pris:
            break
    else:
        # Cas pathologique
        raise V2EditionErreur(
            "Impossible de trouver un code libre pour cette partie.",
            "code_objectif_invalide",
            partie_id=partie_id,
        )

    ob_id = nouveau_id_objectif()
    conn.execute(
        """
        INSERT INTO objectifs
            (id, partie_id, code, nom, methode_id,
             critere_F, critere_A, critere_E, fin_cycle)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'N')
        """,
        (ob_id, partie_id, code, nom or "", methode_id,
         critere_F or "", critere_A or "", critere_E or ""),
    )
    return _format_retour_objectif(conn, ob_id)


def supprimer_objectif(conn, objectif_id: str) -> dict:
    """v0.10.1 — Supprime un objectif et ses dépendances.

    Cascades automatiques (FK ON DELETE CASCADE) :
      - objectif_exos (exos R/EA/F/A/E rattachés)
      - objectif_notions (notions associées)

    Met à NULL les références éventuelles depuis ui_etat_atelier_sequence
    via FK ON DELETE SET NULL (l'utilisateur retombe sur "aucun ouvert").

    Retourne {"objectif_id", "supprime": True}.
    """
    _lire_objectif(conn, objectif_id)
    conn.execute(
        "DELETE FROM objectifs WHERE id = ?",
        (objectif_id,),
    )
    return {"objectif_id": objectif_id, "supprime": True}


# ── Exos de révision / approche au niveau partie ────────────────────────────

_TYPES_REVISION_APPROCHE = ("R", "EA")


def _valider_type_ra(type_):
    if type_ not in _TYPES_REVISION_APPROCHE:
        raise TypeRevisionApprocheInvalide(type_)
    return type_


def _formater_exo_ra(row) -> dict:
    """Format de retour pour un exo R/EA d'une partie. Mêmes champs que les
    exos d'objectif (ordre, exercice, origin_*) pour homogénéité côté UI."""
    return {
        "type":          row["type"],
        "ordre":         row["ordre"],
        "exercice_id":   row["exercice_id"],
        "origin_niveau": row["origin_niveau"],
        "origin_seq":    row["origin_seq"],
        "origin_serie":  row["origin_serie"],
        "origin_num":    row["origin_num"],
        "exercice": {
            "titre":      row["ex_titre"] or "",
            "fichier":    row["ex_fichier"] or "",
            "niveau":     row["ex_niveau"] or "",
            "sequence":   row["ex_sequence"] or "",
            "num":        row["ex_num"],
            "serie_code": row["ex_serie_code"] or "",
        },
    }


def lister_exos_revision_approche(conn, partie_id: str) -> dict:
    """Liste les exos R et EA d'une partie. Retourne un dict :
        {"R": [...], "EA": [...]}
    avec les exos triés par ordre dans chaque liste.
    """
    _lire_partie(conn, partie_id)

    rows = conn.execute(
        """
        SELECT
            pe.partie_id, pe.type, pe.ordre, pe.exercice_id,
            pe.origin_niveau, pe.origin_seq, pe.origin_serie, pe.origin_num,
            ex.titre      AS ex_titre,
            ex.fichier    AS ex_fichier,
            ex.niveau     AS ex_niveau,
            ex.sequence   AS ex_sequence,
            ex.num        AS ex_num,
            ex.serie_code AS ex_serie_code
        FROM partie_exos_revision_approche pe
        LEFT JOIN exercices ex ON ex.id = pe.exercice_id
        WHERE pe.partie_id = ?
        ORDER BY pe.type, pe.ordre
        """,
        (partie_id,),
    ).fetchall()

    resultat = {"R": [], "EA": []}
    for r in rows:
        resultat[r["type"]].append(_formater_exo_ra(r))
    return resultat


def ajouter_exo_revision_approche(
    conn,
    partie_id: str,
    type_: str,
    exercice_id: str,
    origin_niveau: str | None = None,
    origin_seq: str | None = None,
    origin_serie: str | None = None,
    origin_num: int | None = None,
) -> dict:
    """Ajoute un exo (R ou EA) à la fin de la liste de la partie.

    v0.10.2 — Validation métier stricte ajoutée :

    Pour `type_='EA'` (approche) :
      - L'exercice DOIT appartenir à la séquence-niveau courante (même
        niveau, même sequence_code que la séquence-niveau de la partie).
      - L'exercice DOIT être dans la série EA (serie_code='EA').

    Pour `type_='R'` (révision) :
      - L'exercice DOIT être dans la série A (serie_code='A').
      - La séquence d'origine de l'exercice (son niveau/sequence) DOIT
        figurer dans les précédences de la séquence-niveau courante
        (table sequence_par_niveau_precedences).

    Les métadonnées origin_* passées par le client sont IGNORÉES et
    remplacées par les valeurs lues depuis l'exercice lui-même : c'est
    le backend qui détient la vérité, pas le client. Garde le paramètre
    pour rétrocompatibilité de signature, mais ces valeurs ne sont plus
    transmises en BDD.

    Refuse (409) si l'exo est déjà présent dans cette (partie, type).

    Retourne la liste mise à jour {"R": [...], "EA": [...]}.
    """
    partie = _lire_partie(conn, partie_id)
    type_ = _valider_type_ra(type_)
    exo = _lire_exercice(conn, exercice_id)

    # Récupérer la séquence-niveau de la partie (pour les vérifications)
    sn = conn.execute(
        """
        SELECT id, niveau, sequence_code
        FROM sequences_par_niveau
        WHERE id = ?
        """,
        (partie["sequence_par_niveau_id"],),
    ).fetchone()
    if sn is None:
        # Très improbable (partie sans séquence) — défensif
        raise SequenceParNiveauIntrouvable(
            partie["sequence_par_niveau_id"], "?"
        )

    exo_niveau   = (exo["niveau"] or "").strip()
    exo_sequence = (exo["sequence"] or "").strip()
    exo_serie    = (exo["serie_code"] or "").strip()

    # ── Validation métier selon type ─────────────────────────────────────────
    # NB (v0.18.3) : `type_` est le RÔLE de l'exo dans la partie
    # ('R' = révision, 'EA' = approche) — à ne pas confondre avec le
    # serie_code de l'exercice. La série « approche » a pour serie_code 'AE'
    # (convention unifiée v0.18.3 : 'AE' partout, plus de 'EA' comme série).
    if type_ == "EA":
        # Doit appartenir à la séquence-niveau courante
        if exo_niveau != sn["niveau"] or exo_sequence != sn["sequence_code"]:
            raise ExoApprocheHorsSequence(
                partie_id, exercice_id, exo_niveau, exo_sequence,
            )
        # Doit être de la série approche (serie_code 'AE')
        if exo_serie != "AE":
            raise ExoApprocheMauvaiseSerie(
                partie_id, exercice_id, exo_serie,
            )
    elif type_ == "R":
        # Doit être de la série A
        if exo_serie != "A":
            raise ExoRevisionMauvaiseSerie(
                partie_id, exercice_id, exo_serie,
            )
        # Sa séquence d'origine doit figurer dans les précédences
        precedences = conn.execute(
            """
            SELECT precedent_niveau, precedent_seq
            FROM sequence_par_niveau_precedences
            WHERE sequence_par_niveau_id = ?
            """,
            (sn["id"],),
        ).fetchall()
        couples_autorises = {
            (r["precedent_niveau"], r["precedent_seq"]) for r in precedences
        }
        if (exo_niveau, exo_sequence) not in couples_autorises:
            raise ExoRevisionHorsPrecedences(
                partie_id, exercice_id, exo_niveau, exo_sequence,
            )

    deja = conn.execute(
        """
        SELECT 1 FROM partie_exos_revision_approche
        WHERE partie_id = ? AND type = ? AND exercice_id = ?
        """,
        (partie_id, type_, exercice_id),
    ).fetchone()
    if deja:
        raise ExoRevisionApprocheDejaPresent(partie_id, type_, exercice_id)

    # Ordre = max + 1 pour le (partie, type)
    row = conn.execute(
        """
        SELECT COALESCE(MAX(ordre), 0) AS m
        FROM partie_exos_revision_approche
        WHERE partie_id = ? AND type = ?
        """,
        (partie_id, type_),
    ).fetchone()
    ordre = (row["m"] or 0) + 1

    # Les origin_* sont remplis depuis les métadonnées de l'exo lui-même.
    # Pour EA, l'origine est la séquence courante (les colonnes restent
    # remplies pour cohérence d'affichage).
    conn.execute(
        """
        INSERT INTO partie_exos_revision_approche
            (partie_id, type, exercice_id, ordre,
             origin_niveau, origin_seq, origin_serie, origin_num)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            partie_id, type_, exercice_id, ordre,
            exo_niveau, exo_sequence, exo_serie, exo["num"],
        ),
    )

    return lister_exos_revision_approche(conn, partie_id)


def retirer_exo_revision_approche(
    conn, partie_id: str, type_: str, exercice_id: str,
) -> dict:
    """Retire un exo R/EA d'une partie. Recompacte les ordres restants
    (1, 2, 3... dense)."""
    _lire_partie(conn, partie_id)
    type_ = _valider_type_ra(type_)

    present = conn.execute(
        """
        SELECT 1 FROM partie_exos_revision_approche
        WHERE partie_id = ? AND type = ? AND exercice_id = ?
        """,
        (partie_id, type_, exercice_id),
    ).fetchone()
    if not present:
        raise ExoRevisionApprocheIntrouvable(partie_id, type_, exercice_id)

    conn.execute(
        """
        DELETE FROM partie_exos_revision_approche
        WHERE partie_id = ? AND type = ? AND exercice_id = ?
        """,
        (partie_id, type_, exercice_id),
    )

    # Recompactage atomique des ordres
    rows = conn.execute(
        """
        SELECT exercice_id FROM partie_exos_revision_approche
        WHERE partie_id = ? AND type = ?
        ORDER BY ordre
        """,
        (partie_id, type_),
    ).fetchall()
    # Phase 1 : ordres négatifs
    for i, r in enumerate(rows, start=1):
        conn.execute(
            """
            UPDATE partie_exos_revision_approche SET ordre = ?
            WHERE partie_id = ? AND type = ? AND exercice_id = ?
            """,
            (-i, partie_id, type_, r["exercice_id"]),
        )
    # Phase 2 : ordres finaux
    for i, r in enumerate(rows, start=1):
        conn.execute(
            """
            UPDATE partie_exos_revision_approche SET ordre = ?
            WHERE partie_id = ? AND type = ? AND exercice_id = ?
            """,
            (i, partie_id, type_, r["exercice_id"]),
        )

    return lister_exos_revision_approche(conn, partie_id)


def reordonner_exos_revision_approche(
    conn,
    partie_id: str,
    type_: str,
    exercice_ids_dans_ordre: list[str],
) -> dict:
    """Réécrit les `ordre` des exos R/EA d'une partie selon la liste passée.

    Validation stricte : la liste doit contenir exactement les mêmes
    exercice_ids que ce qui est en base pour ce (partie, type)."""
    _lire_partie(conn, partie_id)
    type_ = _valider_type_ra(type_)

    if not isinstance(exercice_ids_dans_ordre, list):
        raise ReordonnancementInvalide(
            "exercice_ids_dans_ordre doit être une liste.",
            recu=type(exercice_ids_dans_ordre).__name__,
        )
    if len(exercice_ids_dans_ordre) != len(set(exercice_ids_dans_ordre)):
        raise ReordonnancementInvalide(
            "La liste contient des doublons.",
            liste=exercice_ids_dans_ordre,
        )

    rows_base = conn.execute(
        """
        SELECT exercice_id FROM partie_exos_revision_approche
        WHERE partie_id = ? AND type = ?
        """,
        (partie_id, type_),
    ).fetchall()
    ids_base = {r["exercice_id"] for r in rows_base}
    ids_demandes = set(exercice_ids_dans_ordre)

    if ids_base != ids_demandes:
        manquants = ids_base - ids_demandes
        inconnus = ids_demandes - ids_base
        raise ReordonnancementInvalide(
            "La liste ne correspond pas exactement aux exos présents : "
            f"manquants={sorted(manquants)}, inconnus={sorted(inconnus)}.",
            manquants=sorted(manquants),
            inconnus=sorted(inconnus),
        )

    # Phase 1 : ordres négatifs
    for i, exid in enumerate(exercice_ids_dans_ordre, start=1):
        conn.execute(
            """
            UPDATE partie_exos_revision_approche SET ordre = ?
            WHERE partie_id = ? AND type = ? AND exercice_id = ?
            """,
            (-i, partie_id, type_, exid),
        )
    # Phase 2 : ordres finaux
    for i, exid in enumerate(exercice_ids_dans_ordre, start=1):
        conn.execute(
            """
            UPDATE partie_exos_revision_approche SET ordre = ?
            WHERE partie_id = ? AND type = ? AND exercice_id = ?
            """,
            (i, partie_id, type_, exid),
        )

    return lister_exos_revision_approche(conn, partie_id)


# ── État UI persistant : objectif ouvert ────────────────────────────────────

def lire_etat_ui_atelier_sequence(conn, sequence_par_niveau_id: str) -> dict:
    """Lit l'état UI de l'atelier d'assemblage pour une séquence par niveau.

    Retourne {"sequence_par_niveau_id": ..., "objectif_ouvert_id": ... | None,
              "derniere_maj": ... | None}.

    Si aucune ligne n'existe encore, retourne objectif_ouvert_id=None
    (pas d'erreur). 404 si la séquence elle-même n'existe pas.
    """
    _lire_sequence_par_niveau(conn, sequence_par_niveau_id)

    row = conn.execute(
        """
        SELECT objectif_ouvert_id, derniere_maj
        FROM ui_etat_atelier_sequence
        WHERE sequence_par_niveau_id = ?
        """,
        (sequence_par_niveau_id,),
    ).fetchone()

    if row is None:
        return {
            "sequence_par_niveau_id": sequence_par_niveau_id,
            "objectif_ouvert_id":     None,
            "derniere_maj":           None,
        }
    return {
        "sequence_par_niveau_id": sequence_par_niveau_id,
        "objectif_ouvert_id":     row["objectif_ouvert_id"],
        "derniere_maj":           row["derniere_maj"],
    }


def ecrire_etat_ui_atelier_sequence(
    conn,
    sequence_par_niveau_id: str,
    objectif_ouvert_id: str | None,
) -> dict:
    """Persiste l'objectif ouvert pour une séquence (UPSERT).

    Si objectif_ouvert_id est None : on stocke NULL (mode liste des
    méthodes à gauche, aucun objectif ouvert).

    Si objectif_ouvert_id est fourni mais que l'objectif n'existe pas
    OU n'appartient pas à cette séquence : ObjectifIntrouvable.
    """
    _lire_sequence_par_niveau(conn, sequence_par_niveau_id)

    if objectif_ouvert_id is not None:
        # Vérifier que l'objectif existe ET appartient à cette séquence
        row = conn.execute(
            """
            SELECT o.id
            FROM objectifs o
            JOIN sequence_parties p ON p.id = o.partie_id
            WHERE o.id = ? AND p.sequence_par_niveau_id = ?
            """,
            (objectif_ouvert_id, sequence_par_niveau_id),
        ).fetchone()
        if row is None:
            raise ObjectifIntrouvable(objectif_ouvert_id)

    conn.execute(
        """
        INSERT INTO ui_etat_atelier_sequence
            (sequence_par_niveau_id, objectif_ouvert_id, derniere_maj)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT (sequence_par_niveau_id) DO UPDATE SET
            objectif_ouvert_id = excluded.objectif_ouvert_id,
            derniere_maj       = excluded.derniere_maj
        """,
        (sequence_par_niveau_id, objectif_ouvert_id),
    )

    return lire_etat_ui_atelier_sequence(conn, sequence_par_niveau_id)


# ═════════════════════════════════════════════════════════════════════════════
# v0.10.2 — Précédences au niveau séquence-niveau
# ═════════════════════════════════════════════════════════════════════════════
#
# Fonctions :
#   - lister_precedences_sequence
#   - ajouter_precedence_sequence
#   - retirer_precedence_sequence
#
# Règles de validation :
#   - precedent_niveau et precedent_seq sont des chaînes non vides.
#   - Pas de validation que (niveau, seq) référence une séquence-niveau
#     existante en BDD : on autorise les pointeurs vers C03, C04 ou
#     n'importe quelle clé future, c'est l'utilisateur qui sait ce qu'il
#     veut référencer. Cohérent avec partie_precedences (legacy) qui ne
#     valide pas non plus.
#   - Pas de précédence circulaire (sn → sn) acceptée : on rejette.

def lister_precedences_sequence(conn, sequence_par_niveau_id: str) -> list[dict]:
    """Retourne la liste des précédences d'une séquence-niveau, dans
    l'ordre déclaré (champ `ordre`).

    Format :
      [{"precedent_niveau": "N10", "precedent_seq": "S03", "ordre": 1}, ...]
    """
    _lire_sequence_par_niveau(conn, sequence_par_niveau_id)
    rows = conn.execute(
        """
        SELECT precedent_niveau, precedent_seq, ordre
        FROM sequence_par_niveau_precedences
        WHERE sequence_par_niveau_id = ?
        ORDER BY ordre, precedent_niveau, precedent_seq
        """,
        (sequence_par_niveau_id,),
    ).fetchall()
    return [
        {
            "precedent_niveau": r["precedent_niveau"],
            "precedent_seq":    r["precedent_seq"],
            "ordre":            r["ordre"],
        }
        for r in rows
    ]


def ajouter_precedence_sequence(
    conn,
    sequence_par_niveau_id: str,
    precedent_niveau: str,
    precedent_seq: str,
) -> list[dict]:
    """Ajoute une précédence à la séquence-niveau. Refuse les doublons et
    les pointeurs circulaires (la séquence référencerait elle-même).

    Retourne la nouvelle liste complète des précédences (ordre conservé).
    """
    sn = _lire_sequence_par_niveau(conn, sequence_par_niveau_id)

    pn = (precedent_niveau or "").strip()
    ps = (precedent_seq or "").strip()
    if not pn or not ps:
        raise PrecedenceInvalide(
            "precedent_niveau et precedent_seq doivent être non vides.",
            precedent_niveau=pn, precedent_seq=ps,
        )

    # Refuser le pointeur circulaire (la séquence se référence elle-même).
    # Au passage, on accepte que sn["niveau"] commence par 'N' et pn aussi,
    # ou que sn["niveau"] soit autre chose et pn différent — pas d'autre
    # règle.
    if pn == sn["niveau"] and ps == sn["sequence_code"]:
        raise PrecedenceInvalide(
            "Une séquence ne peut pas être sa propre précédence.",
            precedent_niveau=pn, precedent_seq=ps,
            sequence_par_niveau_id=sequence_par_niveau_id,
        )

    # v0.10.3 — Règle (b) : le niveau précédent doit être ≤ niveau courant.
    # Comparaison lexicographique sur les codes 'NXX' qui correspond à
    # l'ordre numérique (N07 < N08 < ... < N12). Cohérent avec la sémantique
    # pédagogique : un cours de N12 peut prérequis un cours de N11 ou
    # d'une autre séquence du même N12, mais pas un cours de N13 (qui
    # n'existe pas) ni d'un niveau supérieur.
    #
    # Les niveaux NON préfixés par 'N' (par ex. 'C03' = cycle entier ou
    # niveaux virtuels futurs) ne sont pas comparables lexicographiquement
    # avec un 'NXX' ; on ne les compare pas et on les accepte tous (toute
    # référence vers un cycle antérieur reste légitime).
    sn_niveau = (sn["niveau"] or "").strip()
    if (sn_niveau.startswith("N") and pn.startswith("N")
            and pn > sn_niveau):
        raise PrecedenceInvalide(
            f"Niveau précédent ({pn}) supérieur au niveau courant "
            f"({sn_niveau}). Une séquence ne peut pas avoir comme "
            f"précédence une séquence d'un niveau supérieur.",
            precedent_niveau=pn, precedent_seq=ps,
            sequence_par_niveau_id=sequence_par_niveau_id,
            niveau_courant=sn_niveau,
        )

    # Doublon ?
    deja = conn.execute(
        """
        SELECT 1 FROM sequence_par_niveau_precedences
        WHERE sequence_par_niveau_id = ? AND precedent_niveau = ?
              AND precedent_seq = ?
        """,
        (sequence_par_niveau_id, pn, ps),
    ).fetchone()
    if deja:
        raise PrecedenceSeqDejaPresente(sequence_par_niveau_id, pn, ps)

    # Ordre = max + 1
    row = conn.execute(
        """
        SELECT COALESCE(MAX(ordre), 0) AS m
        FROM sequence_par_niveau_precedences
        WHERE sequence_par_niveau_id = ?
        """,
        (sequence_par_niveau_id,),
    ).fetchone()
    ordre = (row["m"] or 0) + 1

    conn.execute(
        """
        INSERT INTO sequence_par_niveau_precedences
            (sequence_par_niveau_id, precedent_niveau, precedent_seq, ordre)
        VALUES (?, ?, ?, ?)
        """,
        (sequence_par_niveau_id, pn, ps, ordre),
    )
    return lister_precedences_sequence(conn, sequence_par_niveau_id)


def retirer_precedence_sequence(
    conn,
    sequence_par_niveau_id: str,
    precedent_niveau: str,
    precedent_seq: str,
) -> list[dict]:
    """Retire une précédence. Recompacte les ordres restants.

    Lève PrecedenceSeqIntrouvable si la précédence n'existe pas."""
    _lire_sequence_par_niveau(conn, sequence_par_niveau_id)
    pn = (precedent_niveau or "").strip()
    ps = (precedent_seq or "").strip()

    present = conn.execute(
        """
        SELECT 1 FROM sequence_par_niveau_precedences
        WHERE sequence_par_niveau_id = ? AND precedent_niveau = ?
              AND precedent_seq = ?
        """,
        (sequence_par_niveau_id, pn, ps),
    ).fetchone()
    if not present:
        raise PrecedenceSeqIntrouvable(sequence_par_niveau_id, pn, ps)

    conn.execute(
        """
        DELETE FROM sequence_par_niveau_precedences
        WHERE sequence_par_niveau_id = ? AND precedent_niveau = ?
              AND precedent_seq = ?
        """,
        (sequence_par_niveau_id, pn, ps),
    )

    # Recompactage des ordres
    rows = conn.execute(
        """
        SELECT precedent_niveau, precedent_seq
        FROM sequence_par_niveau_precedences
        WHERE sequence_par_niveau_id = ?
        ORDER BY ordre
        """,
        (sequence_par_niveau_id,),
    ).fetchall()
    # Phase 1 : ordres négatifs
    for i, r in enumerate(rows, start=1):
        conn.execute(
            """
            UPDATE sequence_par_niveau_precedences SET ordre = ?
            WHERE sequence_par_niveau_id = ? AND precedent_niveau = ?
                  AND precedent_seq = ?
            """,
            (-i, sequence_par_niveau_id, r["precedent_niveau"], r["precedent_seq"]),
        )
    # Phase 2 : ordres finaux
    for i, r in enumerate(rows, start=1):
        conn.execute(
            """
            UPDATE sequence_par_niveau_precedences SET ordre = ?
            WHERE sequence_par_niveau_id = ? AND precedent_niveau = ?
                  AND precedent_seq = ?
            """,
            (i, sequence_par_niveau_id, r["precedent_niveau"], r["precedent_seq"]),
        )
    return lister_precedences_sequence(conn, sequence_par_niveau_id)


# ═════════════════════════════════════════════════════════════════════════════
# v0.16.9 — État validable de la séquence-niveau (régime mixte + verrou)
# ═════════════════════════════════════════════════════════════════════════════
#
# Une séquence-niveau porte désormais un `etat_code` ('en_cours' | 'valide'),
# sur le modèle des évaluations (services/evaluations.py) :
#   - 'en_cours' : modifiable librement (saisie + structure) ;
#   - 'valide'   : lecture seule. Toute route de modification de contenu pose
#                  `assert_sequence_modifiable` en garde → SequenceVerrouillee
#                  (HTTP 409). On peut toujours lire, compiler, et dévalider.
#
# Le passage → 'valide' déclenche un hook de validation pédagogique strict
# (cf. _valider_sequence_hook) ; en cas d'échec, ValidationSequenceErreur
# (HTTP 400) avec la liste des raisons.

_ETATS_SEQUENCE_VALIDES = ("en_cours", "valide")


def lire_etat_sequence(conn, sn_id: str) -> str:
    """Retourne le code d'état de la séquence-niveau ('en_cours'|'valide').

    Lève SequenceParNiveauIntrouvable si l'id est inconnu.
    """
    row = conn.execute(
        "SELECT etat_code FROM sequences_par_niveau WHERE id = ?",
        (sn_id,),
    ).fetchone()
    if row is None:
        raise SequenceParNiveauIntrouvable(sn_id)
    return row["etat_code"] or "en_cours"


def assert_sequence_modifiable(conn, sn_id: str) -> None:
    """Lève SequenceVerrouillee si la séquence est en état 'valide'.

    À appeler en garde au début de toute opération qui MODIFIE le contenu de
    la séquence (saisie d'objectif, ajout/retrait de composant, structure).
    NE PAS appeler sur la route de changement d'état (qui doit pouvoir
    dévalider) ni sur les lectures / compilations.

    Si la séquence est introuvable, on laisse passer : la couche appelante
    lèvera son propre 404 (on ne masque pas un 404 par un 409).
    """
    try:
        etat = lire_etat_sequence(conn, sn_id)
    except SequenceParNiveauIntrouvable:
        return
    if etat == "valide":
        raise SequenceVerrouillee(sn_id)


def assert_sequence_modifiable_par_partie(conn, partie_id: str) -> None:
    """Variante : garde via l'id d'une partie (remonte à sa séquence)."""
    row = conn.execute(
        "SELECT sequence_par_niveau_id FROM sequence_parties WHERE id = ?",
        (partie_id,),
    ).fetchone()
    if row is None:
        return  # 404 géré en aval
    assert_sequence_modifiable(conn, row["sequence_par_niveau_id"])


def assert_sequence_modifiable_par_objectif(conn, objectif_id: str) -> None:
    """Variante : garde via l'id d'un objectif (remonte à sa séquence)."""
    row = conn.execute(
        """
        SELECT p.sequence_par_niveau_id AS sn_id
        FROM objectifs ob
        JOIN sequence_parties p ON p.id = ob.partie_id
        WHERE ob.id = ?
        """,
        (objectif_id,),
    ).fetchone()
    if row is None:
        return  # 404 géré en aval
    assert_sequence_modifiable(conn, row["sn_id"])


def _valider_sequence_hook(conn, sn_id: str) -> None:
    """Hook de validation pédagogique strict d'une séquence-niveau (v0.16.9).

    Règles (décision Laurent D3) :
      1. La séquence a au moins une partie.
      2. Chaque partie a au moins un objectif « exo » (code NON terminé par
         le motif Cours `{numero-1}1`).
      3. Chaque objectif (cours ou exo) a un nom non vide ET les trois
         critères F, A, E non vides.
      4. Chaque objectif « exo » a au moins un exercice dans CHACUNE des
         trois séries F, A et E.

    Lève ValidationSequenceErreur(sn_id, raisons) si au moins une règle
    échoue. Les raisons sont libellées de façon actionnable (réutilisées
    telles quelles dans le toast côté UI).
    """
    raisons: list[str] = []

    parties = conn.execute(
        "SELECT id, numero FROM sequence_parties "
        "WHERE sequence_par_niveau_id = ? ORDER BY numero",
        (sn_id,),
    ).fetchall()

    # Règle 1
    if not parties:
        raisons.append("La séquence ne contient aucune partie.")

    for p in parties:
        objs = conn.execute(
            "SELECT id, code, nom, critere_F, critere_A, critere_E "
            "FROM objectifs WHERE partie_id = ? ORDER BY code",
            (p["id"],),
        ).fetchall()
        code_cours = code_objectif_connaitre(p["numero"])
        objs_exo = [o for o in objs if o["code"] != code_cours]

        # Règle 2
        if not objs_exo:
            raisons.append(
                f"La partie {p['numero']} n'a aucun objectif d'exercices."
            )

        for o in objs:
            est_cours = (o["code"] == code_cours)
            etiquette = f"L'objectif {o['code']}"

            # Règle 3 — nom + 3 critères (cours ET exo)
            if not (o["nom"] or "").strip():
                raisons.append(f"{etiquette} n'a pas de nom.")
            for champ, libelle in (
                ("critere_F", "F"), ("critere_A", "A"), ("critere_E", "E"),
            ):
                if not (o[champ] or "").strip():
                    raisons.append(
                        f"{etiquette} n'a pas de critère {libelle}."
                    )

            # Règle 4 — exos dans les 3 séries (exo seulement)
            if not est_cours:
                series_presentes = {
                    r["serie"] for r in conn.execute(
                        "SELECT DISTINCT serie FROM objectif_exos "
                        "WHERE objectif_id = ?",
                        (o["id"],),
                    ).fetchall()
                }
                manquantes = [s for s in ("F", "A", "E")
                              if s not in series_presentes]
                if manquantes:
                    raisons.append(
                        f"{etiquette} n'a pas d'exercice dans la série "
                        f"{', '.join(manquantes)}."
                    )

    if raisons:
        raise ValidationSequenceErreur(sn_id, raisons)


def valider_sequence_niveau(conn, sn_id: str) -> dict:
    """Passe la séquence en état 'valide' après le hook pédagogique.

    Idempotent : si déjà 'valide', retourne l'état sans relancer le hook.
    Lève SequenceParNiveauIntrouvable (404) si l'id est inconnu, ou
    ValidationSequenceErreur (400) si le hook échoue.

    Retourne {"id", "etat_code"}.
    """
    etat = lire_etat_sequence(conn, sn_id)  # lève si introuvable
    if etat == "valide":
        return {"id": sn_id, "etat_code": "valide"}
    _valider_sequence_hook(conn, sn_id)  # lève ValidationSequenceErreur si KO
    conn.execute(
        "UPDATE sequences_par_niveau SET etat_code = 'valide' WHERE id = ?",
        (sn_id,),
    )
    return {"id": sn_id, "etat_code": "valide"}


def devalider_sequence_niveau(conn, sn_id: str) -> dict:
    """Repasse la séquence en état 'en_cours' (toujours autorisé).

    Idempotent. Lève SequenceParNiveauIntrouvable (404) si l'id est inconnu.
    Retourne {"id", "etat_code"}.
    """
    etat = lire_etat_sequence(conn, sn_id)  # lève si introuvable
    if etat == "en_cours":
        return {"id": sn_id, "etat_code": "en_cours"}
    conn.execute(
        "UPDATE sequences_par_niveau SET etat_code = 'en_cours' WHERE id = ?",
        (sn_id,),
    )
    return {"id": sn_id, "etat_code": "en_cours"}


def changer_etat_sequence_niveau(conn, sn_id: str, nouvel_etat: str) -> dict:
    """Aiguillage générique en_cours ↔ valide (utilisé par la route /etat)."""
    if nouvel_etat not in _ETATS_SEQUENCE_VALIDES:
        raise EtatSequenceInvalide(nouvel_etat)
    if nouvel_etat == "valide":
        return valider_sequence_niveau(conn, sn_id)
    return devalider_sequence_niveau(conn, sn_id)
