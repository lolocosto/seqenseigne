"""services/cartes_automatisme.py — v0.13.6.1 (refondu en v0.13.6.1.2)

Service métier de l'atelier « Cartes d'automatisme ».

Une carte est un objet pédagogique recto/verso (format A8 imprimable)
utilisé en rituel Leitner (5 niveaux d'enveloppes) pour mémoriser des
automatismes mathématiques.

Périmètre v0.13.6.1.2 :
  - CRUD des cartes
  - Lien direct vers UNE notion OU UNE méthode (champs lien_type/lien_id)
  - Workflow valider/dévalider
  - Config atelier
  - Aides UI : lister les notions et méthodes disponibles dans la séquence

Refonte v0.13.6.1.2 (décision Laurent) :
  - 5 types pédagogiques unifiés : definition, propriete, reconnaissance,
    calcul, procedure (vs 4 en v0.13.6.1 : calcul_mental, methode,
    definition, reconnaissance)
  - Lien direct vers notion/méthode (vs many-to-many vers objectifs)
  - Suppression des fonctions liées aux objectifs

Hors périmètre v0.13.6.1.2 :
  - Génération du LaTeX de planche A4 (v0.13.6.2)
  - Saisie des résultats d'éval orale (v0.13.6.4)

Pattern aligné sur services/evaluations.py : exceptions typées avec code
stable et details, validation centralisée.
"""
from __future__ import annotations
import sqlite3
import uuid
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Constantes et configuration
# ─────────────────────────────────────────────────────────────────────────────

TYPES_PEDAGO = ('definition', 'propriete', 'reconnaissance',
                'calcul', 'procedure')
TYPES_TECH = ('fixe', 'parametree')
ETATS_CODE = ('en_cours', 'valide')
LIEN_TYPES = ('notion', 'methode')

DEFAULTS_CONFIG: dict[str, str] = {
    'cartes_param_nb_uniques': '16',
    # 'badges_actifs': 'non',  # v0.13.6.3
}


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────


class CarteErreur(Exception):
    """Erreur domaine. Convention CONVENTIONS.md : code stable + details."""
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class CarteIntrouvable(CarteErreur):
    def __init__(self, carte_id: str):
        super().__init__(
            f"Carte {carte_id!r} introuvable.",
            "carte_introuvable", carte_id=carte_id,
        )


class NumDejaUtilise(CarteErreur):
    def __init__(self, niveau: str, sequence: str, num: int):
        super().__init__(
            f"Numéro C{num:02d} déjà utilisé dans {niveau}/{sequence}.",
            "num_deja_utilise", niveau=niveau, sequence=sequence, num=num,
        )


class TypePedagoInvalide(CarteErreur):
    def __init__(self, valeur):
        super().__init__(
            f"Type pédagogique invalide : {valeur!r}. "
            f"Valeurs attendues : {TYPES_PEDAGO}.",
            "type_pedago_invalide", valeur=valeur,
            attendus=list(TYPES_PEDAGO),
        )


class TypeTechInvalide(CarteErreur):
    def __init__(self, valeur):
        super().__init__(
            f"Type technique invalide : {valeur!r}. "
            f"Valeurs attendues : {TYPES_TECH}.",
            "type_tech_invalide", valeur=valeur, attendus=list(TYPES_TECH),
        )


class EtatCodeInvalide(CarteErreur):
    def __init__(self, valeur):
        super().__init__(
            f"Code d'état invalide : {valeur!r}. "
            f"Valeurs attendues : {ETATS_CODE}.",
            "etat_code_invalide", valeur=valeur, attendus=list(ETATS_CODE),
        )


class NumInvalide(CarteErreur):
    def __init__(self, valeur):
        super().__init__(
            f"Numéro de carte invalide : {valeur!r}. "
            f"Doit être un entier entre 1 et 99 inclus.",
            "num_invalide", valeur=valeur,
        )


class LienTypeInvalide(CarteErreur):
    """v0.13.6.1.2 — Le type de lien n'est ni 'notion' ni 'methode'."""
    def __init__(self, valeur):
        super().__init__(
            f"Type de lien invalide : {valeur!r}. "
            f"Valeurs attendues : {LIEN_TYPES}.",
            "lien_type_invalide", valeur=valeur, attendus=list(LIEN_TYPES),
        )


class LienIntrouvable(CarteErreur):
    """v0.13.6.1.2 — La notion/méthode pointée n'existe pas."""
    def __init__(self, lien_type: str, lien_id: str):
        super().__init__(
            f"{lien_type.capitalize()} {lien_id!r} introuvable.",
            "lien_introuvable", lien_type=lien_type, lien_id=lien_id,
        )


class LienIncoherent(CarteErreur):
    """v0.13.6.1.2 — lien_type et lien_id incohérents."""
    def __init__(self, lien_type, lien_id):
        super().__init__(
            f"Lien incohérent : lien_type={lien_type!r} et "
            f"lien_id={lien_id!r}. Soit les deux sont fournis, "
            "soit les deux sont vides.",
            "lien_incoherent", lien_type=lien_type, lien_id=lien_id,
        )


class ChampInvalide(CarteErreur):
    def __init__(self, champs_invalides: list[str],
                 champs_autorises: list[str]):
        super().__init__(
            f"Champ(s) inconnu(s) ou non modifiable(s) : "
            f"{sorted(champs_invalides)}. "
            f"Champs autorisés : {sorted(champs_autorises)}.",
            "champ_invalide",
            invalides=list(champs_invalides),
            autorises=list(champs_autorises),
        )


class CleConfigInconnue(CarteErreur):
    def __init__(self, cle: str):
        super().__init__(
            f"Clé de config inconnue : {cle!r}. "
            f"Clés attendues : {sorted(DEFAULTS_CONFIG)}.",
            "cle_config_inconnue",
            cle=cle, attendues=sorted(DEFAULTS_CONFIG),
        )


class ValeurConfigInvalide(CarteErreur):
    def __init__(self, cle: str, valeur, raison: str):
        super().__init__(
            f"Valeur invalide pour {cle!r} : {raison} (reçu : {valeur!r}).",
            "valeur_config_invalide",
            cle=cle, valeur=valeur, raison=raison,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internes
# ─────────────────────────────────────────────────────────────────────────────


def _rowid() -> str:
    return 'crt_' + uuid.uuid4().hex[:12]


def _carte_par_id(conn: sqlite3.Connection,
                  carte_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM cartes_automatisme WHERE id = ?", (carte_id,)
    ).fetchone()


def _row_vers_dict_carte(row: sqlite3.Row) -> dict:
    """v0.13.6.1.2 : inclut lien_type et lien_id (potentiellement NULL).
    v0.13.6.13   : ajoute objectif_ids (liste des objectifs liés via la table
                   de liaison objectif_cartes). Les champs lien_type/lien_id
                   sont conservés pour rétrocompat (donnée historique) mais
                   ne sont plus la source de vérité du lien : c'est
                   objectif_cartes qui pilote l'affichage et la validation.
    v0.13.6.15   : colonne `nom` renommée en `titre` (harmonisation avec
                   les autres atomes). Plus de mapping côté JS.
    """
    if row is None:
        return None
    return {
        'id':          row['id'],
        'niveau':      row['niveau'],
        'sequence':    row['sequence'],
        'num':         row['num'],
        'type_pedago': row['type_pedago'],
        'type_tech':   row['type_tech'],
        'titre':       row['titre'] or '',
        'lien_type':   row['lien_type'],   # None si pas encore lié (legacy)
        'lien_id':     row['lien_id'],     # None si pas encore lié (legacy)
        'recto':       row['recto'] or '',
        'verso':       row['verso'] or '',
        'variables':   row['variables'] or '',
        'etat_code':   row['etat_code'],
        'ordre':       row['ordre'],
        'mtime':       row['mtime'],
        # v0.13.6.13 : la clé `objectif_ids` est ajoutée par lire_carte/
        # lister_cartes via _enrichir_objectif_ids. Pas dans _row_vers_dict_carte
        # pour ne pas faire de requête à chaque ligne d'un SELECT * lourd.
    }


def _objectifs_de_carte(conn: sqlite3.Connection, carte_id: str) -> list[str]:
    """v0.13.6.13 — Retourne la liste des objectif_id liés à la carte,
    triés par ordre puis par objectif_id pour un résultat déterministe.

    Retourne [] si la carte n'a aucun lien (carte orpheline)."""
    rows = conn.execute(
        "SELECT objectif_id FROM objectif_cartes "
        "WHERE carte_id = ? ORDER BY ordre, objectif_id",
        (carte_id,),
    ).fetchall()
    return [r['objectif_id'] for r in rows]


def _enrichir_objectif_ids(conn: sqlite3.Connection, carte: dict) -> dict:
    """v0.13.6.13 — Helper : ajoute la clé `objectif_ids` au dict carte.
    No-op si carte est None."""
    if carte is None:
        return None
    carte['objectif_ids'] = _objectifs_de_carte(conn, carte['id'])
    return carte


def _remplacer_liens_objectifs(conn: sqlite3.Connection,
                                carte_id: str,
                                objectif_ids: list[str]) -> None:
    """v0.13.6.13 — Remplace toutes les liaisons d'une carte vers des
    objectifs. Atomique : DELETE puis INSERT (le PRIMARY KEY composite
    garantit l'unicité).

    Le caller doit avoir validé que les objectif_id existent (sinon la
    FK sur objectifs lèvera IntegrityError).

    Les doublons dans `objectif_ids` sont silencieusement ignorés via
    INSERT OR IGNORE. Une liste vide supprime toutes les liaisons
    (carte orpheline)."""
    conn.execute(
        "DELETE FROM objectif_cartes WHERE carte_id = ?",
        (carte_id,),
    )
    for ordre, obj_id in enumerate(objectif_ids, start=1):
        conn.execute(
            "INSERT OR IGNORE INTO objectif_cartes "
            "(objectif_id, carte_id, ordre) VALUES (?, ?, ?)",
            (obj_id, carte_id, ordre),
        )


def _deriver_objectif_ids_depuis_lien_legacy(
    conn: sqlite3.Connection, lien_type, lien_id
) -> list[str]:
    """v0.13.6.13 — Pour les appels rétrocompat qui fournissent encore
    lien_type/lien_id, dérive la liste d'objectifs correspondante (même
    règle que la migration des données existantes).

    - lien_type='methode' : 0 ou 1 objectif via objectifs.methode_id
    - lien_type='notion'  : 0..N objectifs via objectif_notions
    - lien_type None/vide : [] (carte orpheline)

    Pas de validation : suppose que _valider_lien a déjà tourné en amont.
    """
    if not lien_type or not lien_id:
        return []
    if lien_type == 'methode':
        rows = conn.execute(
            "SELECT id FROM objectifs WHERE methode_id = ? ORDER BY id",
            (lien_id,),
        ).fetchall()
    elif lien_type == 'notion':
        rows = conn.execute(
            "SELECT objectif_id FROM objectif_notions "
            "WHERE notion_id = ? ORDER BY objectif_id",
            (lien_id,),
        ).fetchall()
    else:
        return []
    return [r[0] for r in rows]


def _valider_objectif_ids(conn: sqlite3.Connection,
                           objectif_ids: list[str]) -> list[str]:
    """v0.13.6.13 — Valide qu'une liste d'objectif_id n'a que des id
    existants dans objectifs. Lève LienIntrouvable au premier
    introuvable. Dédoublonne en préservant l'ordre.

    Accepte None ou liste vide → retourne []."""
    if not objectif_ids:
        return []
    # Dédoublonner en préservant l'ordre
    vu = set()
    uniques = []
    for oid in objectif_ids:
        if oid and oid not in vu:
            vu.add(oid)
            uniques.append(oid)
    # Vérifier l'existence
    for oid in uniques:
        row = conn.execute(
            "SELECT 1 FROM objectifs WHERE id = ?", (oid,)
        ).fetchone()
        if row is None:
            # Réutilise LienIntrouvable, plus simple que d'introduire un
            # nouveau type d'erreur (l'API REST renvoie déjà 404 dessus).
            raise LienIntrouvable('objectif', oid)
    return uniques


def _valider_type_pedago(valeur: str) -> None:
    if valeur not in TYPES_PEDAGO:
        raise TypePedagoInvalide(valeur)


def _valider_type_tech(valeur: str) -> None:
    if valeur not in TYPES_TECH:
        raise TypeTechInvalide(valeur)


def _valider_etat_code(valeur: str) -> None:
    if valeur not in ETATS_CODE:
        raise EtatCodeInvalide(valeur)


def _valider_num(valeur: Any) -> int:
    try:
        n = int(valeur)
    except (TypeError, ValueError):
        raise NumInvalide(valeur)
    if n < 1 or n > 99:
        raise NumInvalide(valeur)
    return n


def _valider_lien(conn: sqlite3.Connection,
                  lien_type, lien_id) -> tuple[str | None, str | None]:
    """v0.13.6.1.2 — Valide la cohérence du couple (lien_type, lien_id).

    Soit les deux NULL → carte non liée (acceptée à la création, refusée
    à la validation pédagogique).
    Soit les deux fournis → lien_type ∈ LIEN_TYPES et l'élément existe.

    Lève LienIncoherent / LienTypeInvalide / LienIntrouvable.
    Retourne le couple normalisé (None, None) ou (lien_type, lien_id).
    """
    # Normaliser les vides en None
    if lien_type == '':
        lien_type = None
    if lien_id == '':
        lien_id = None

    if lien_type is None and lien_id is None:
        return None, None

    if lien_type is None or lien_id is None:
        raise LienIncoherent(lien_type, lien_id)

    if lien_type not in LIEN_TYPES:
        raise LienTypeInvalide(lien_type)

    table = 'notions' if lien_type == 'notion' else 'methodes'
    row = conn.execute(
        f"SELECT 1 FROM {table} WHERE id = ?", (lien_id,)
    ).fetchone()
    if row is None:
        raise LienIntrouvable(lien_type, lien_id)
    return lien_type, lien_id


def _prochain_num(conn: sqlite3.Connection,
                  niveau: str,
                  sequence: str) -> int:
    row = conn.execute(
        "SELECT MAX(num) FROM cartes_automatisme "
        "WHERE niveau = ? AND sequence = ?",
        (niveau, sequence),
    ).fetchone()
    return (row[0] or 0) + 1


# ─────────────────────────────────────────────────────────────────────────────
# CRUD principal
# ─────────────────────────────────────────────────────────────────────────────


def creer_carte(
    conn: sqlite3.Connection,
    *,
    niveau: str,
    sequence: str,
    type_pedago: str = 'definition',
    type_tech: str = 'fixe',
    titre: str = '',
    recto: str = '',
    verso: str = '',
    variables: str = '',
    lien_type=None,
    lien_id=None,
    objectif_ids: list[str] | None = None,
    num: int | None = None,
    ordre: int | None = None,
) -> dict:
    """Crée une nouvelle carte dans la séquence indiquée.

    Si `num` est None, on attribue max(num) + 1 dans la séquence.
    Lien (v0.13.6.1.2) : optionnel à la création.

    v0.13.6.13 : nouvelle interface `objectif_ids` (liste optionnelle).
      - Si `objectif_ids` est fourni : la liste est validée puis écrite
        dans objectif_cartes. Les anciens paramètres lien_type/lien_id
        sont alors ignorés.
      - Si seuls `lien_type`/`lien_id` sont fournis (rétrocompat) : on
        valide le lien legacy, on écrit dans cartes_automatisme.lien_*
        comme avant, ET on dérive automatiquement les objectif_ids
        correspondants pour les écrire dans objectif_cartes (cohérence).
      - Si rien n'est fourni : carte orpheline (aucune liaison).

    v0.13.6.15 : paramètre `nom` renommé en `titre` (harmonisation avec
    les autres atomes).

    Lève TypePedagoInvalide, TypeTechInvalide, NumInvalide,
    NumDejaUtilise, LienIncoherent, LienTypeInvalide, LienIntrouvable.
    """
    _valider_type_pedago(type_pedago)
    _valider_type_tech(type_tech)

    # v0.13.6.13 — Disjonction lien legacy vs objectif_ids
    if objectif_ids is not None:
        # Nouvelle interface : objectif_ids prime, on ignore lien_*
        objectif_ids_valides = _valider_objectif_ids(conn, objectif_ids)
        # On nettoie lien_type/lien_id à la valeur historique neutre
        lien_type, lien_id = None, None
    else:
        # Rétrocompat : on valide le lien legacy si fourni
        lien_type, lien_id = _valider_lien(conn, lien_type, lien_id)
        # Et on dérive automatiquement les objectif_ids correspondants
        objectif_ids_valides = _deriver_objectif_ids_depuis_lien_legacy(
            conn, lien_type, lien_id
        )

    if num is None:
        num_final = _prochain_num(conn, niveau, sequence)
    else:
        num_final = _valider_num(num)
        existant = conn.execute(
            "SELECT 1 FROM cartes_automatisme "
            "WHERE niveau = ? AND sequence = ? AND num = ?",
            (niveau, sequence, num_final),
        ).fetchone()
        if existant:
            raise NumDejaUtilise(niveau, sequence, num_final)

    if ordre is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(ordre), 0) + 1 FROM cartes_automatisme "
            "WHERE niveau = ? AND sequence = ?",
            (niveau, sequence),
        ).fetchone()
        ordre_final = row[0]
    else:
        ordre_final = int(ordre)

    carte_id = _rowid()
    conn.execute(
        "INSERT INTO cartes_automatisme "
        "(id, niveau, sequence, num, type_pedago, type_tech, titre, "
        " lien_type, lien_id, recto, verso, variables, etat_code, ordre) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'en_cours', ?)",
        (carte_id, niveau, sequence, num_final, type_pedago, type_tech,
         titre, lien_type, lien_id, recto, verso, variables, ordre_final),
    )
    # v0.13.6.13 — Peuple objectif_cartes (vide si pas de liens)
    _remplacer_liens_objectifs(conn, carte_id, objectif_ids_valides)
    conn.commit()
    return lire_carte(conn, carte_id)


def lire_carte(conn: sqlite3.Connection, carte_id: str) -> dict:
    """Lit une carte par ID. Lève CarteIntrouvable si absente.

    v0.13.6.13 : enrichit le dict avec la clé `objectif_ids` (liste).
    """
    row = _carte_par_id(conn, carte_id)
    if row is None:
        raise CarteIntrouvable(carte_id)
    return _enrichir_objectif_ids(conn, _row_vers_dict_carte(row))


def lister_cartes(conn: sqlite3.Connection,
                  niveau: str,
                  sequence: str) -> list[dict]:
    """Liste les cartes d'une séquence, triées par ordre puis num.

    v0.13.6.13 : enrichit chaque dict avec la clé `objectif_ids`.
    """
    rows = conn.execute(
        "SELECT * FROM cartes_automatisme "
        "WHERE niveau = ? AND sequence = ? "
        "ORDER BY ordre, num",
        (niveau, sequence),
    ).fetchall()
    return [_enrichir_objectif_ids(conn, _row_vers_dict_carte(r))
            for r in rows]


def modifier_carte(
    conn: sqlite3.Connection,
    carte_id: str,
    **champs,
) -> dict:
    """Modifie une carte existante (pattern PATCH).

    Champs modifiables : type_pedago, type_tech, titre, recto, verso,
    variables, num, ordre, lien_type, lien_id, objectif_ids (v0.13.6.13).

    Note : lien_type et lien_id doivent être modifiés ensemble si l'un
    des deux change. L'UI doit envoyer le couple.

    v0.13.6.13 — Si `objectif_ids` (liste) est dans `champs` :
      - La liste remplace intégralement les liaisons de la carte
        (DELETE + INSERT atomique).
      - Si `lien_type`/`lien_id` aussi présents, ils sont ignorés
        (objectif_ids prime).
      - Si `objectif_ids` est une liste vide, toutes les liaisons sont
        supprimées (carte orpheline).

    Si seuls `lien_type`/`lien_id` sont fournis (rétrocompat), on valide
    le couple comme avant, on écrit dans cartes_automatisme.lien_*, ET
    on dérive automatiquement objectif_ids pour mettre à jour
    objectif_cartes en cohérence.

    Pour modifier etat_code, utiliser le mécanisme unifié :
    services.etats_edition.changer_etat_atome(conn, 'carte', carte_id, etat).
    La validation pédagogique est appliquée via le hook
    _valider_carte_hook enregistré au chargement de ce module.
    """
    if _carte_par_id(conn, carte_id) is None:
        raise CarteIntrouvable(carte_id)

    champs_autorises = {
        'type_pedago', 'type_tech', 'titre', 'recto', 'verso',
        'variables', 'num', 'ordre', 'lien_type', 'lien_id',
        'objectif_ids',  # v0.13.6.13
    }
    invalides = set(champs) - champs_autorises
    if invalides:
        raise ChampInvalide(list(invalides), list(champs_autorises))

    if 'type_pedago' in champs:
        _valider_type_pedago(champs['type_pedago'])
    if 'type_tech' in champs:
        _valider_type_tech(champs['type_tech'])

    # v0.13.6.13 — Disjonction lien legacy vs objectif_ids
    # `objectif_ids` est traité séparément (table de liaison), pas via
    # UPDATE cartes_automatisme. On l'extrait du dict champs avant la
    # construction du SET.
    objectif_ids_a_ecrire = None
    if 'objectif_ids' in champs:
        objectif_ids_a_ecrire = _valider_objectif_ids(
            conn, champs.pop('objectif_ids')
        )
        # Si objectif_ids fourni, on ignore lien_type/lien_id legacy
        champs.pop('lien_type', None)
        champs.pop('lien_id', None)
    elif 'lien_type' in champs or 'lien_id' in champs:
        # Rétrocompat : validation lien + dérivation des objectif_ids
        carte_actuelle = lire_carte(conn, carte_id)
        lien_type = champs.get('lien_type', carte_actuelle['lien_type'])
        lien_id = champs.get('lien_id', carte_actuelle['lien_id'])
        lien_type, lien_id = _valider_lien(conn, lien_type, lien_id)
        champs['lien_type'] = lien_type
        champs['lien_id'] = lien_id
        objectif_ids_a_ecrire = _deriver_objectif_ids_depuis_lien_legacy(
            conn, lien_type, lien_id
        )

    if 'num' in champs:
        num_final = _valider_num(champs['num'])
        carte = lire_carte(conn, carte_id)
        if num_final != carte['num']:
            collision = conn.execute(
                "SELECT 1 FROM cartes_automatisme "
                "WHERE niveau = ? AND sequence = ? AND num = ? AND id != ?",
                (carte['niveau'], carte['sequence'], num_final, carte_id),
            ).fetchone()
            if collision:
                raise NumDejaUtilise(carte['niveau'],
                                     carte['sequence'], num_final)
        champs['num'] = num_final

    # UPDATE cartes_automatisme uniquement s'il reste des champs après
    # extraction d'objectif_ids
    if champs:
        sets = ', '.join(f"{k} = ?" for k in champs)
        values = list(champs.values())
        values.append(carte_id)
        conn.execute(
            f"UPDATE cartes_automatisme SET {sets}, mtime = CURRENT_TIMESTAMP "
            f"WHERE id = ?",
            values,
        )

    # v0.13.6.13 — Mise à jour des liaisons objectif_cartes si nécessaire
    if objectif_ids_a_ecrire is not None:
        _remplacer_liens_objectifs(conn, carte_id, objectif_ids_a_ecrire)

    conn.commit()
    return lire_carte(conn, carte_id)


def supprimer_carte(conn: sqlite3.Connection, carte_id: str) -> None:
    """Supprime une carte. Lève CarteIntrouvable si absente."""
    if _carte_par_id(conn, carte_id) is None:
        raise CarteIntrouvable(carte_id)
    conn.execute("DELETE FROM cartes_automatisme WHERE id = ?", (carte_id,))
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Sélecteurs de lien : notions et méthodes disponibles
# ─────────────────────────────────────────────────────────────────────────────


def lister_notions_disponibles(conn: sqlite3.Connection,
                               niveau: str,
                               sequence: str) -> list[dict]:
    """v0.13.6.1.2 — Liste les notions de la séquence pour le sélecteur
    de lien. Triées par num_connaissance puis titre.
    """
    rows = conn.execute(
        "SELECT id, titre, num_connaissance, etat_code "
        "FROM notions "
        "WHERE niveau = ? AND sequence = ? "
        "ORDER BY num_connaissance, titre",
        (niveau, sequence),
    ).fetchall()
    return [dict(r) for r in rows]


def lister_methodes_disponibles(conn: sqlite3.Connection,
                                niveau: str,
                                sequence: str) -> list[dict]:
    """v0.13.6.1.2 — Liste les méthodes de la séquence pour le sélecteur
    de lien. Triées par num_methode puis titre.
    """
    rows = conn.execute(
        "SELECT id, titre, num_methode, num_objectif, etat_code "
        "FROM methodes "
        "WHERE niveau = ? AND sequence = ? "
        "ORDER BY num_methode, titre",
        (niveau, sequence),
    ).fetchall()
    return [dict(r) for r in rows]


def lire_lien_label(conn: sqlite3.Connection,
                    lien_type: str | None,
                    lien_id: str | None) -> str | None:
    """v0.13.6.1.2 — Libellé court pour le lien d'une carte.
    Renvoie None si lien_type/lien_id sont NULL.
    """
    if lien_type is None or lien_id is None:
        return None
    if lien_type == 'notion':
        row = conn.execute(
            "SELECT num_connaissance, titre FROM notions WHERE id = ?",
            (lien_id,),
        ).fetchone()
        if row:
            num = row['num_connaissance'] or '?'
            return f"N{num} — {row['titre'] or '(sans titre)'}"
    elif lien_type == 'methode':
        row = conn.execute(
            "SELECT num_methode, titre FROM methodes WHERE id = ?",
            (lien_id,),
        ).fetchone()
        if row:
            num = row['num_methode'] or '?'
            return f"M{num} — {row['titre'] or '(sans titre)'}"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Validation pédagogique (hook pour etats_edition)
# ─────────────────────────────────────────────────────────────────────────────
#
# v0.13.6.8.2 — Les routes /valider et /devalider sont supprimées au profit
# du mécanisme unifié PATCH /api/atomes/<type>/<id>/etat. La validation
# pédagogique reste, mais sous forme de hook enregistré dans le registre
# de etats_edition. Au passage → 'valide', etats_edition.changer_etat_atome
# appelle ce hook qui peut lever ValidationPedagogiqueErreur (celle d'
# etats_edition, pas celle de carte).


def _valider_carte_hook(conn: sqlite3.Connection, carte_id: str) -> None:
    """Hook de validation pédagogique au passage → 'valide' pour les cartes.

    Vérifie :
      - recto non vide
      - verso non vide
      - lien (lien_type + lien_id) défini
      - si type_tech='parametree', variables non vide

    Lève etats_edition.ValidationPedagogiqueErreur si une règle échoue.
    L'exception sera capturée par routes/etats_edition.py et retournée
    en HTTP 400 avec details.raisons.

    Ne modifie PAS l'état : c'est etats_edition.changer_etat_atome qui
    fait l'UPDATE après le hook.
    """
    # Import local pour éviter une dépendance circulaire au chargement
    # du module (etats_edition n'importe pas cartes_automatisme).
    from services.etats_edition import ValidationPedagogiqueErreur as VPE

    carte = lire_carte(conn, carte_id)
    raisons = []
    if not carte['recto'].strip():
        raisons.append("Le recto est vide.")
    if not carte['verso'].strip():
        raisons.append("Le verso est vide.")
    # v0.13.6.13 — La condition de lien porte désormais sur objectif_cartes
    # (table de liaison N:M). Avant : on exigeait lien_type/lien_id non NULL
    # (lien direct vers notion ou méthode). Maintenant : on exige au moins
    # une liaison vers un objectif.
    if not carte.get('objectif_ids'):
        raisons.append("La carte n'est liée à aucun objectif.")
    if carte['type_tech'] == 'parametree' and not carte['variables'].strip():
        raisons.append(
            "Carte paramétrée : le champ 'variables' ne doit pas être vide."
        )

    if raisons:
        raise VPE(
            "La carte ne peut pas être validée en l'état.",
            raisons=raisons,
            type_atome='carte',
            atome_id=carte_id,
        )


# Enregistrement du hook au chargement du module. Le service est importé
# par les routes au démarrage Flask, donc le hook est en place avant les
# premiers appels HTTP.
def _enregistrer_hook_validation_carte() -> None:
    from services.etats_edition import enregistrer_hook_validation
    enregistrer_hook_validation('carte', _valider_carte_hook)


_enregistrer_hook_validation_carte()


# ─────────────────────────────────────────────────────────────────────────────
# Wrappers dépréciés (v0.13.6.8.2.1)
# ─────────────────────────────────────────────────────────────────────────────
#
# Les routes /api/cartes/<id>/valider et /devalider ont été supprimées en
# v0.13.6.8.2 au profit du mécanisme unifié etats_edition. Mais certains
# scripts (scripts/peupler_cartes_n10.py) et tests
# (test_v0_13_6_2_3_peuplement_cartes_n10.py, test_v0_13_6_3_2_assemblage_cartes.py,
# test_v0_13_6_3_referentiel_eval_cartes.py) appellent encore directement
# cartes_automatisme.valider_carte() et devalider_carte() pour préparer
# leurs fixtures.
#
# Plutôt que d'adapter ces 4 fichiers dans l'urgence, on restaure des
# wrappers minimaux qui délèguent au nouveau mécanisme. Code mort à
# nettoyer en v0.14 quand on aura adapté les appelants.
#
# Différences avec l'ancien comportement :
# - Plus d'exceptions DejaValide / DejaEnCours : appeler ces fonctions
#   sur un atome déjà à l'état cible est maintenant idempotent (pas
#   d'erreur). Les fichiers concernés ne dépendent pas de ces erreurs
#   (vérifié dans les logs d'échec v0.13.6.8.2).
# - L'exception ValidationPedagogiqueErreur levée par valider_carte() est
#   maintenant celle d'etats_edition, pas plus celle de cartes_automatisme
#   (qui n'existe plus depuis v0.13.6.8.2).


def valider_carte(conn: sqlite3.Connection, carte_id: str) -> dict:
    """[DEPRECATED v0.13.6.8.2.1] Wrapper vers etats_edition.changer_etat_atome.

    Préfère :
        from services.etats_edition import changer_etat_atome
        changer_etat_atome(conn, 'carte', carte_id, 'valide')

    Comportement :
      - Passage à l'état 'valide' (idempotent : pas d'erreur si déjà valide)
      - Validation pédagogique appliquée via le hook _valider_carte_hook
        enregistré dans etats_edition.HOOKS_VALIDATION_PEDAGOGIQUE
      - Lève etats_edition.ValidationPedagogiqueErreur si la validation
        pédagogique échoue (recto/verso vide, lien absent, etc.)
      - Met à jour mtime = CURRENT_TIMESTAMP

    Retourne la carte complète après update (pour rester rétrocompatible
    avec l'ancienne signature qui retournait dict).
    """
    from services.etats_edition import changer_etat_atome
    changer_etat_atome(conn, 'carte', carte_id, 'valide')
    conn.commit()
    return lire_carte(conn, carte_id)


def devalider_carte(conn: sqlite3.Connection, carte_id: str) -> dict:
    """[DEPRECATED v0.13.6.8.2.1] Wrapper vers etats_edition.changer_etat_atome.

    Préfère :
        from services.etats_edition import changer_etat_atome
        changer_etat_atome(conn, 'carte', carte_id, 'en_cours')

    Comportement :
      - Passage à l'état 'en_cours' (idempotent : pas d'erreur si déjà
        en cours)
      - Pas de hook (les hooks ne s'exécutent qu'au passage → 'valide')
      - Met à jour mtime

    Retourne la carte complète après update.
    """
    from services.etats_edition import changer_etat_atome
    changer_etat_atome(conn, 'carte', carte_id, 'en_cours')
    conn.commit()
    return lire_carte(conn, carte_id)


# Alias rétrocompat pour ValidationPedagogiqueErreur. Certains tests
# l'importent depuis cartes_automatisme. On expose celle d'etats_edition.
from services.etats_edition import ValidationPedagogiqueErreur  # noqa: E402, F401


# ─────────────────────────────────────────────────────────────────────────────
# Configuration atelier
# ─────────────────────────────────────────────────────────────────────────────


def lire_config(conn: sqlite3.Connection, cle: str) -> str:
    if cle not in DEFAULTS_CONFIG:
        raise CleConfigInconnue(cle)
    row = conn.execute(
        "SELECT valeur FROM cartes_atelier_config WHERE cle = ?", (cle,)
    ).fetchone()
    if row is None:
        return DEFAULTS_CONFIG[cle]
    return row['valeur']


def modifier_config(conn: sqlite3.Connection, cle: str, valeur: str) -> None:
    """Définit (ou met à jour) une valeur de config.

    Lève CleConfigInconnue ou ValeurConfigInvalide.
    """
    if cle not in DEFAULTS_CONFIG:
        raise CleConfigInconnue(cle)
    if cle == 'cartes_param_nb_uniques':
        try:
            n = int(valeur)
        except (TypeError, ValueError):
            raise ValeurConfigInvalide(cle, valeur, "doit être un entier")
        if n < 16 or n > 256 or n % 16 != 0:
            raise ValeurConfigInvalide(
                cle, valeur, "doit être un multiple de 16 entre 16 et 256"
            )
    conn.execute(
        "INSERT INTO cartes_atelier_config (cle, valeur) VALUES (?, ?) "
        "ON CONFLICT (cle) DO UPDATE SET valeur = excluded.valeur",
        (cle, str(valeur)),
    )
    conn.commit()
