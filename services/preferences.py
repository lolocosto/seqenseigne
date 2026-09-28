"""services/preferences.py — v0.10.5.2

Gestion des préférences utilisateur paramétrables via la table
`preferences_items(id, type, valeur, ordre)`.

Deux modes d'usage selon le type :
  - **Liste** : plusieurs items de même `type` représentent une liste
    triée par `ordre`. Ex: type='titre_zone_fiche' avec items
    Définition, Propriété, Méthode.
  - **Valeur unique** : un seul item de ce type, on ignore `ordre`.
    Ex: type='chemin_donnees_sequences' avec une seule valeur.

API :
  - lister_items(conn, type_)
  - ajouter_item(conn, type_, valeur, ordre=None)
  - modifier_item(conn, item_id, valeur=None, ordre=None)
  - supprimer_item(conn, item_id)
  - reordonner_items(conn, type_, liste_ids)  -- pour drag-and-drop
  - lire_valeur_unique(conn, type_)           -- helper pour types mono-valeur
  - definir_valeur_unique(conn, type_, valeur) -- idempotent (upsert)
"""

from __future__ import annotations
import uuid


# ── Erreurs de domaine ───────────────────────────────────────────────────────


class PreferencesErreur(Exception):
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class ItemIntrouvable(PreferencesErreur):
    def __init__(self, item_id):
        super().__init__(
            f"Item de préférences {item_id!r} introuvable.",
            "item_introuvable", item_id=item_id,
        )


class ValeurInvalide(PreferencesErreur):
    def __init__(self, valeur):
        super().__init__(
            f"Valeur invalide : {valeur!r}.",
            "valeur_invalide", valeur=valeur,
        )


def _rowid():
    return uuid.uuid4().hex


# ── API liste (multi-valeurs par type) ──────────────────────────────────────


def lister_items(conn, type_: str) -> list[dict]:
    """Liste les items d'un type, triés par `ordre` puis `valeur`."""
    rows = conn.execute(
        "SELECT id, valeur, ordre FROM preferences_items "
        "WHERE type = ? ORDER BY ordre, valeur",
        (type_,),
    ).fetchall()
    return [
        {"id": r["id"], "valeur": r["valeur"] or "", "ordre": r["ordre"]}
        for r in rows
    ]


def ajouter_item(
    conn, type_: str, valeur: str, *,
    ordre: int | None = None,
) -> dict:
    """Ajoute un item à la liste du type donné.

    Si `ordre` n'est pas fourni, place l'item à la fin (max+1).
    Lève ValeurInvalide si `valeur` est vide après strip.
    """
    val = (valeur or "").strip()
    if not val:
        raise ValeurInvalide(valeur)

    if ordre is None:
        r = conn.execute(
            "SELECT MAX(ordre) AS m FROM preferences_items WHERE type = ?",
            (type_,),
        ).fetchone()
        m = r["m"] if r and r["m"] is not None else 0
        ordre = m + 10  # incrément 10 pour laisser de la place aux insertions

    new_id = _rowid()
    conn.execute(
        "INSERT INTO preferences_items (id, type, valeur, ordre) "
        "VALUES (?, ?, ?, ?)",
        (new_id, type_, val, ordre),
    )
    return {"id": new_id, "valeur": val, "ordre": ordre, "type": type_}


def modifier_item(
    conn, item_id: str, *,
    valeur: str | None = None,
    ordre: int | None = None,
) -> dict:
    """Modifie la valeur et/ou l'ordre d'un item existant."""
    row = conn.execute(
        "SELECT type, valeur, ordre FROM preferences_items WHERE id = ?",
        (item_id,),
    ).fetchone()
    if row is None:
        raise ItemIntrouvable(item_id)

    nouvelle_val = row["valeur"]
    if valeur is not None:
        nouvelle_val = (valeur or "").strip()
        if not nouvelle_val:
            raise ValeurInvalide(valeur)

    nouvel_ordre = ordre if ordre is not None else row["ordre"]

    conn.execute(
        "UPDATE preferences_items SET valeur = ?, ordre = ? WHERE id = ?",
        (nouvelle_val, nouvel_ordre, item_id),
    )
    return {
        "id": item_id, "type": row["type"],
        "valeur": nouvelle_val, "ordre": nouvel_ordre,
    }


def supprimer_item(conn, item_id: str) -> None:
    """Supprime un item. Lève ItemIntrouvable si l'id n'existe pas."""
    row = conn.execute(
        "SELECT 1 FROM preferences_items WHERE id = ?", (item_id,),
    ).fetchone()
    if row is None:
        raise ItemIntrouvable(item_id)
    conn.execute("DELETE FROM preferences_items WHERE id = ?", (item_id,))


def reordonner_items(
    conn, type_: str, liste_ids: list[str],
) -> list[dict]:
    """Reorder les items d'un type selon l'ordre des ids fournis.

    Les items absents de la liste conservent leur ordre relatif
    après les items reordonnés. Ne lève pas si certains ids
    n'existent pas — ils sont simplement ignorés.
    """
    # Pose les ordres 10, 20, 30... pour les items dans liste_ids.
    for i, item_id in enumerate(liste_ids):
        conn.execute(
            "UPDATE preferences_items SET ordre = ? "
            "WHERE id = ? AND type = ?",
            ((i + 1) * 10, item_id, type_),
        )
    return lister_items(conn, type_)


# ── API valeur unique (un seul item par type) ──────────────────────────────


def lire_valeur_unique(conn, type_: str) -> str | None:
    """Retourne la valeur d'un type mono-valeur, ou None si absent.

    Pour les types qui ne devraient avoir qu'un seul item (ex.
    chemins). Si plusieurs items existent par erreur, retourne le
    premier (par `ordre` puis `id`).
    """
    row = conn.execute(
        "SELECT valeur FROM preferences_items "
        "WHERE type = ? ORDER BY ordre, id LIMIT 1",
        (type_,),
    ).fetchone()
    return row["valeur"] if row else None


def definir_valeur_unique(
    conn, type_: str, valeur: str,
) -> dict:
    """Pose une valeur unique pour le type (upsert).

    Si un item de ce type existe déjà, met à jour sa valeur. Sinon en
    crée un. Si plusieurs items existent par erreur, met à jour le
    premier et supprime les autres.
    """
    val = (valeur or "").strip()
    rows = conn.execute(
        "SELECT id FROM preferences_items WHERE type = ? ORDER BY ordre, id",
        (type_,),
    ).fetchall()
    if not rows:
        # Création
        return ajouter_item(conn, type_, val, ordre=10)
    # Mise à jour du premier ; suppression des autres
    premier = rows[0]["id"]
    conn.execute(
        "UPDATE preferences_items SET valeur = ?, ordre = 10 WHERE id = ?",
        (val, premier),
    )
    for r in rows[1:]:
        conn.execute(
            "DELETE FROM preferences_items WHERE id = ?", (r["id"],),
        )
    return {"id": premier, "type": type_, "valeur": val, "ordre": 10}
