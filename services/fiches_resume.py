"""services/fiches_resume.py — v0.10.5

Gestion des fiches de résumé : CRUD, liaisons avec les objectifs Connaître,
helper d'aplatissement pour le bouton « Initialiser depuis... ».

Modèle (rappel) :
  - 1 fiche = 1 méthode = 1 objectif (cardinalité 1-1, Q3-1).
  - num_fiche : numérotation automatique par séquence (Q3-3).
  - Sections : réutilisent atome_sections avec entite_type='fiche_resume'.
  - etat_code : réutilise le mécanisme v0.10.4 (en_cours / valide).
  - Liaison fiche → obj Connaître via objectif_fiches (Q3-4/5/6).
"""

from __future__ import annotations
import uuid


# ── Erreurs de domaine ───────────────────────────────────────────────────────


class FicheErreur(Exception):
    """Erreur domaine pour les opérations sur les fiches de résumé."""
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class FicheIntrouvable(FicheErreur):
    def __init__(self, fiche_id):
        super().__init__(
            f"Fiche {fiche_id!r} introuvable.",
            "fiche_introuvable", fiche_id=fiche_id,
        )


class ObjectifIntrouvable(FicheErreur):
    def __init__(self, objectif_id):
        super().__init__(
            f"Objectif {objectif_id!r} introuvable.",
            "objectif_introuvable", objectif_id=objectif_id,
        )


class ObjectifDejaLie(FicheErreur):
    def __init__(self, objectif_id):
        super().__init__(
            f"Cet objectif a déjà une fiche de résumé.",
            "objectif_deja_lie", objectif_id=objectif_id,
        )


class FicheDejaPresente(FicheErreur):
    """Levée quand on tente d'attacher une fiche déjà présente sur l'obj."""
    def __init__(self, objectif_id, fiche_id):
        super().__init__(
            f"Fiche {fiche_id!r} déjà attachée à l'objectif {objectif_id!r}.",
            "fiche_deja_presente",
            objectif_id=objectif_id, fiche_id=fiche_id,
        )


# ── Helpers internes ─────────────────────────────────────────────────────────


def _rowid():
    return uuid.uuid4().hex


def _objectif_par_id(conn, objectif_id):
    """Lookup d'un objectif (objectifs) avec résolution de la
    (niveau, sequence) via la jointure partie → seqnav.

    Retourne un dict {id, code, nom, partie_id, niveau, sequence} ou None.
    """
    row = conn.execute(
        """
        SELECT o.id, o.code, o.nom, o.partie_id,
               sn.niveau, sn.sequence_code AS sequence
        FROM objectifs o
        JOIN sequence_parties p ON p.id = o.partie_id
        JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id
        WHERE o.id = ?
        """,
        (objectif_id,),
    ).fetchone()
    return row


def _max_num_fiche(conn, niveau: str, sequence: str) -> int:
    """Plus grand num_fiche existant pour cette (niveau, sequence)."""
    r = conn.execute(
        "SELECT MAX(num_fiche) AS m FROM fiches_resume "
        "WHERE niveau = ? AND sequence = ?",
        (niveau, sequence),
    ).fetchone()
    return (r["m"] or 0) if r else 0


# ── CRUD : créer / lire / modifier / supprimer ───────────────────────────────


def creer_fiche(
    conn, *,
    objectif_id: str | None = None,
    niveau: str | None = None,
    sequence: str | None = None,
    titre: str = "",
    sections: list[dict] | None = None,
) -> dict:
    """Crée une nouvelle fiche.

    Deux modes (v0.13.6.14 — chantier D) :

    1. **Avec objectif** (mode historique) : `objectif_id` fourni.
       L'objectif doit exister et ne pas déjà avoir une fiche
       (cardinalité 1:1 préservée). `niveau` et `sequence` sont déduits
       de l'objectif (les paramètres explicites éventuellement passés
       sont ignorés).

    2. **Sans objectif** (mode nouveau) : `objectif_id=None` ; les
       paramètres `niveau` et `sequence` deviennent obligatoires pour
       calculer `num_fiche` et alimenter les colonnes dénormalisées. La
       fiche reste orpheline tant qu'on ne la rattache pas à un objectif
       depuis l'atelier d'assemblage de séquence.

    La numérotation `num_fiche` est calculée automatiquement (max+1 dans
    la séquence).

    Le caller passe les sections (peut être vide ou None — au moins une
    sera créée par défaut côté service pour cohérence avec la spec Q3-2).

    Lève :
      - ObjectifIntrouvable si `objectif_id` fourni et inconnu
      - ObjectifDejaLie si `objectif_id` fourni et déjà rattaché
      - ValueError si `objectif_id=None` et `niveau`/`sequence` absents
    """
    if objectif_id is not None:
        # Mode historique : déduire niveau/sequence de l'objectif.
        obj = _objectif_par_id(conn, objectif_id)
        if obj is None:
            raise ObjectifIntrouvable(objectif_id)
        # Cardinalité 1-1 : refuser si l'objectif a déjà une fiche
        deja = conn.execute(
            "SELECT id FROM fiches_resume WHERE objectif_id = ?",
            (objectif_id,),
        ).fetchone()
        if deja is not None:
            raise ObjectifDejaLie(objectif_id)
        niveau_final = obj["niveau"] or ""
        sequence_final = obj["sequence"] or ""
    else:
        # Mode v0.13.6.14 : sans objectif, niveau/sequence explicites.
        if not niveau or not sequence:
            raise ValueError(
                "creer_fiche : si objectif_id est None, niveau et sequence "
                "doivent être fournis explicitement."
            )
        niveau_final = niveau
        sequence_final = sequence

    fiche_id = _rowid()
    num = _max_num_fiche(conn, niveau_final, sequence_final) + 1

    conn.execute(
        "INSERT INTO fiches_resume "
        "(id, titre, objectif_id, num_fiche, niveau, sequence, etat_code) "
        "VALUES (?, ?, ?, ?, ?, ?, 'en_cours')",
        (fiche_id, titre or "", objectif_id, num,
         niveau_final, sequence_final),
    )

    # Sections : si rien fourni, créer une zone vide par défaut.
    sections_a_ecrire = sections or [{"titre": "", "items": [""]}]
    _ecrire_sections_fiche(conn, fiche_id, sections_a_ecrire)

    return lire_fiche(conn, fiche_id)


def lire_fiche(conn, fiche_id: str) -> dict:
    """Retourne la fiche complète avec ses sections.

    Lève FicheIntrouvable si l'id n'existe pas en BDD.
    """
    row = conn.execute(
        "SELECT * FROM fiches_resume WHERE id = ?", (fiche_id,),
    ).fetchone()
    if row is None:
        raise FicheIntrouvable(fiche_id)

    return {
        "id":          row["id"],
        "titre":       row["titre"] or "",
        "objectif_id": row["objectif_id"],
        "num_fiche":   row["num_fiche"],
        "niveau":      row["niveau"] or "",
        "sequence":    row["sequence"] or "",
        "fichier":     row["fichier"] or "",
        "etat_code":   row["etat_code"] or "en_cours",
        "sections":    _lire_sections_fiche(conn, fiche_id),
    }


def lister_fiches(conn, *, niveau: str | None = None,
                  sequence: str | None = None) -> list[dict]:
    """Liste les fiches, optionnellement filtrées par (niveau, sequence).

    Inclut un résumé de l'objectif lié (code, nom) pour l'affichage dans
    la liste latérale de l'atelier. Les sections ne sont PAS chargées
    (perf — elles le seront au chargement individuel).
    """
    sql = """
        SELECT f.id, f.titre, f.objectif_id, f.num_fiche, f.niveau,
               f.sequence, f.etat_code,
               o.code AS objectif_code, o.nom AS objectif_nom
        FROM fiches_resume f
        LEFT JOIN objectifs o ON o.id = f.objectif_id
    """
    params: list = []
    where = []
    if niveau:
        where.append("f.niveau = ?")
        params.append(niveau)
    if sequence:
        where.append("f.sequence = ?")
        params.append(sequence)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY f.niveau, f.sequence, f.num_fiche"

    return [
        {
            "id":            r["id"],
            "titre":         r["titre"] or "",
            "objectif_id":   r["objectif_id"],
            "num_fiche":     r["num_fiche"],
            "niveau":        r["niveau"] or "",
            "sequence":      r["sequence"] or "",
            "etat_code":     r["etat_code"] or "en_cours",
            "objectif_code": r["objectif_code"] or "",
            "objectif_nom":  r["objectif_nom"] or "",
        }
        for r in conn.execute(sql, params).fetchall()
    ]


def modifier_fiche(
    conn, fiche_id: str, *,
    titre: str | None = None,
    sections: list[dict] | None = None,
    objectif_id: str | None = None,
) -> dict:
    """Modifie les champs fournis d'une fiche existante.

    Si `objectif_id` change, le service met à jour `niveau`/`sequence` en
    conséquence et renumérote (sauf si la fiche reste dans la même
    séquence). La validation 1-1 est appliquée si on bascule sur un
    objectif qui a déjà une fiche.

    Préserve `etat_code` (Q2-N : pas de retour auto à 'en_cours' à la
    modification).
    """
    row = conn.execute(
        "SELECT * FROM fiches_resume WHERE id = ?", (fiche_id,),
    ).fetchone()
    if row is None:
        raise FicheIntrouvable(fiche_id)

    nouveau_titre = titre if titre is not None else row["titre"]
    nouvel_obj_id = objectif_id if objectif_id is not None else row["objectif_id"]

    # Si l'objectif change, valider et recalculer (niveau, sequence,
    # num_fiche).
    nouveau_niveau = row["niveau"]
    nouvelle_seq = row["sequence"]
    nouveau_num = row["num_fiche"]
    if objectif_id is not None and objectif_id != row["objectif_id"]:
        nouvel_obj = _objectif_par_id(conn, nouvel_obj_id)
        if nouvel_obj is None:
            raise ObjectifIntrouvable(nouvel_obj_id)
        # Refuser si le nouvel objectif a déjà une fiche
        deja = conn.execute(
            "SELECT id FROM fiches_resume "
            "WHERE objectif_id = ? AND id != ?",
            (nouvel_obj_id, fiche_id),
        ).fetchone()
        if deja is not None:
            raise ObjectifDejaLie(nouvel_obj_id)
        nouveau_niveau = nouvel_obj["niveau"] or ""
        nouvelle_seq = nouvel_obj["sequence"] or ""
        # Si on change de séquence, renuméroter dans la nouvelle.
        # Sinon on garde le même num_fiche pour stabilité.
        if (nouveau_niveau, nouvelle_seq) != (row["niveau"], row["sequence"]):
            nouveau_num = _max_num_fiche(conn, nouveau_niveau, nouvelle_seq) + 1

    conn.execute(
        "UPDATE fiches_resume SET titre = ?, objectif_id = ?, "
        "num_fiche = ?, niveau = ?, sequence = ? WHERE id = ?",
        (nouveau_titre, nouvel_obj_id, nouveau_num,
         nouveau_niveau, nouvelle_seq, fiche_id),
    )

    if sections is not None:
        _ecrire_sections_fiche(conn, fiche_id, sections)

    return lire_fiche(conn, fiche_id)


def supprimer_fiche(conn, fiche_id: str) -> None:
    """Supprime la fiche, ses sections (cascade) et ses liens
    objectif_fiches (cascade FK)."""
    row = conn.execute(
        "SELECT id FROM fiches_resume WHERE id = ?", (fiche_id,),
    ).fetchone()
    if row is None:
        raise FicheIntrouvable(fiche_id)
    # Sections : pas de FK avec CASCADE, on nettoie manuellement
    conn.execute(
        "DELETE FROM atome_sections "
        "WHERE entite_type = 'fiche_resume' AND entite_id = ?",
        (fiche_id,),
    )
    # objectif_fiches : ON DELETE CASCADE sur fiche_id (cf. schema.sql)
    conn.execute("DELETE FROM fiches_resume WHERE id = ?", (fiche_id,))


# ── Helpers sections (équivalents v0.6.4 mais pour fiche_resume) ────────────


def _lire_sections_fiche(conn, fiche_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, titre FROM atome_sections "
        "WHERE entite_type = 'fiche_resume' AND entite_id = ? "
        "ORDER BY ordre",
        (fiche_id,),
    ).fetchall()
    out = []
    for sr in rows:
        items = conn.execute(
            "SELECT corps FROM atome_section_items "
            "WHERE section_id = ? ORDER BY ordre",
            (sr["id"],),
        ).fetchall()
        out.append({
            "titre": sr["titre"] or "",
            "items": [ir["corps"] for ir in items],
        })
    return out


def _ecrire_sections_fiche(conn, fiche_id: str,
                           sections: list[dict]) -> None:
    """Remplace toutes les sections de la fiche par celles fournies."""
    conn.execute(
        "DELETE FROM atome_sections "
        "WHERE entite_type = 'fiche_resume' AND entite_id = ?",
        (fiche_id,),
    )
    for i, sec in enumerate(sections or []):
        section_id = _rowid()
        conn.execute(
            "INSERT INTO atome_sections "
            "(id, entite_type, entite_id, titre, ordre) "
            "VALUES (?, 'fiche_resume', ?, ?, ?)",
            (section_id, fiche_id, sec.get("titre", "") or "", i),
        )
        for j, corps in enumerate(sec.get("items", []) or []):
            conn.execute(
                "INSERT INTO atome_section_items "
                "(id, section_id, ordre, corps) VALUES (?, ?, ?, ?)",
                (_rowid(), section_id, j, corps),
            )


# ── Liens fiche ↔ objectif (drop sur Connaître) ─────────────────────────────


def attacher_fiche_a_objectif(
    conn, *, objectif_id: str, fiche_id: str,
) -> dict:
    """Attache une fiche à un objectif (typiquement le Connaître d'une
    partie). Idempotent : si la fiche est déjà attachée, lève
    FicheDejaPresente.

    L'ordre est calculé automatiquement (max+1 dans cet objectif).
    """
    if _objectif_par_id(conn, objectif_id) is None:
        raise ObjectifIntrouvable(objectif_id)
    fiche = conn.execute(
        "SELECT id FROM fiches_resume WHERE id = ?", (fiche_id,),
    ).fetchone()
    if fiche is None:
        raise FicheIntrouvable(fiche_id)

    deja = conn.execute(
        "SELECT 1 FROM objectif_fiches "
        "WHERE objectif_id = ? AND fiche_id = ?",
        (objectif_id, fiche_id),
    ).fetchone()
    if deja:
        raise FicheDejaPresente(objectif_id, fiche_id)

    r = conn.execute(
        "SELECT MAX(ordre) AS m FROM objectif_fiches WHERE objectif_id = ?",
        (objectif_id,),
    ).fetchone()
    # Subtilité Python : `(r["m"] or -1) + 1` casse pour ordre=0
    # (faux-comme-Python). On teste explicitement None.
    m = r["m"] if r and r["m"] is not None else -1
    ordre = m + 1

    conn.execute(
        "INSERT INTO objectif_fiches (objectif_id, fiche_id, ordre) "
        "VALUES (?, ?, ?)",
        (objectif_id, fiche_id, ordre),
    )
    return {"objectif_id": objectif_id, "fiche_id": fiche_id, "ordre": ordre}


def detacher_fiche_de_objectif(
    conn, *, objectif_id: str, fiche_id: str,
) -> None:
    """Détache une fiche d'un objectif. No-op si la liaison n'existe pas."""
    conn.execute(
        "DELETE FROM objectif_fiches "
        "WHERE objectif_id = ? AND fiche_id = ?",
        (objectif_id, fiche_id),
    )


def lister_fiches_attachees(conn, objectif_id: str) -> list[dict]:
    """Retourne les fiches attachées à un objectif, dans l'ordre."""
    rows = conn.execute(
        """
        SELECT f.id, f.titre, f.num_fiche, f.niveau, f.sequence,
               f.etat_code, of.ordre
        FROM objectif_fiches of
        JOIN fiches_resume f ON f.id = of.fiche_id
        WHERE of.objectif_id = ?
        ORDER BY of.ordre, f.num_fiche
        """,
        (objectif_id,),
    ).fetchall()
    return [
        {
            "id":         r["id"],
            "titre":      r["titre"] or "",
            "num_fiche":  r["num_fiche"],
            "niveau":     r["niveau"] or "",
            "sequence":   r["sequence"] or "",
            "etat_code":  r["etat_code"] or "en_cours",
            "ordre":      r["ordre"],
        }
        for r in rows
    ]


def lister_fiches_de_partie(conn, partie_id: str) -> list[dict]:
    """Pour la sidebar de l'assemblage en mode "obj Connaître ouvert" :
    liste les fiches dont l'objectif lié est dans la même partie de
    séquence (Q3-4/5/6).

    Retourne fiches triées par code de l'objectif lié.
    """
    rows = conn.execute(
        """
        SELECT f.id, f.titre, f.num_fiche, f.niveau, f.sequence,
               f.etat_code, f.objectif_id,
               o.code AS objectif_code, o.nom AS objectif_nom
        FROM fiches_resume f
        JOIN objectifs o ON o.id = f.objectif_id
        WHERE o.partie_id = ?
        ORDER BY o.code
        """,
        (partie_id,),
    ).fetchall()
    return [
        {
            "id":            r["id"],
            "titre":         r["titre"] or "",
            "num_fiche":     r["num_fiche"],
            "niveau":        r["niveau"] or "",
            "sequence":      r["sequence"] or "",
            "etat_code":     r["etat_code"] or "en_cours",
            "objectif_id":   r["objectif_id"],
            "objectif_code": r["objectif_code"] or "",
            "objectif_nom":  r["objectif_nom"] or "",
        }
        for r in rows
    ]


# ── Helper d'aplatissement « hors exemples » (Q3-2 + QF) ────────────────────


# Titres de sections à exclure lors de l'aplatissement, comparaison
# case-insensitive (QF.1-QF.2).
_TITRES_EXEMPLES_EXCLUS = {"exemple", "exemples", "ex", "ex."}


def aplatir_atome_pour_initialisation(
    conn, *, type_atome: str, atome_id: str,
) -> str:
    """Lit le corps + sections d'une notion ou d'une méthode, exclut
    les sections de type "Exemples", et retourne un bloc LaTeX prêt à
    être posé dans une zone de fiche (QE.2).

    Format :

        {corps}

        \\textbf{titre section 1}
        {item 1}

        {item 2}

        \\textbf{titre section 2}
        ...

    Si la notion/méthode n'a pas de corps (uniquement des sections),
    on commence directement par la première section.
    """
    if type_atome not in ("notion", "methode"):
        raise FicheErreur(
            f"Type d'atome non supporté pour aplatissement : {type_atome!r}",
            "type_atome_invalide",
            type_atome=type_atome,
        )

    table = "notions" if type_atome == "notion" else "methodes"
    row = conn.execute(
        f"SELECT corps FROM {table} WHERE id = ?", (atome_id,),
    ).fetchone()
    if row is None:
        # Pas une exception métier ; on retourne juste vide.
        return ""

    morceaux: list[str] = []
    corps = (row["corps"] or "").strip()
    if corps:
        morceaux.append(corps)

    sections = conn.execute(
        "SELECT id, titre FROM atome_sections "
        "WHERE entite_type = ? AND entite_id = ? ORDER BY ordre",
        (type_atome, atome_id),
    ).fetchall()
    for sec in sections:
        titre = (sec["titre"] or "").strip()
        # Filtre Exemples (case-insensitive sur le titre normalisé)
        if titre.lower() in _TITRES_EXEMPLES_EXCLUS:
            continue
        items = conn.execute(
            "SELECT corps FROM atome_section_items "
            "WHERE section_id = ? ORDER BY ordre",
            (sec["id"],),
        ).fetchall()
        items_non_vides = [
            (it["corps"] or "").strip() for it in items
            if (it["corps"] or "").strip()
        ]
        if not items_non_vides and not titre:
            continue
        if titre:
            morceaux.append(f"\\textbf{{{titre}}}")
        for corps_item in items_non_vides:
            morceaux.append(corps_item)

    return "\n\n".join(morceaux)


# ── v0.13.6.16 — Hook de validation pédagogique ───────────────────────────
#
# Suite à la relâche des contraintes de création (titre vide autorisé,
# nécessaire pour le pattern POST-direct unifié des ateliers), on ajoute
# un hook au passage en état `valide` pour refuser la validation de
# fiches incomplètes.

def _valider_fiche_hook(conn, fiche_id: str) -> None:
    """Refuse le passage en `valide` si la fiche est incomplète.

    Règles :
      - titre non vide
      - au moins une section avec du contenu (textes non vides)
    """
    from services.etats_edition import ValidationPedagogiqueErreur as VPE

    row = conn.execute(
        "SELECT titre FROM fiches_resume WHERE id = ?", (fiche_id,),
    ).fetchone()
    if row is None:
        return  # changer_etat_atome a déjà vérifié l'existence.

    raisons = []
    if not (row["titre"] or "").strip():
        raisons.append("Le titre est vide.")

    # Vérifier qu'il y a au moins une section avec contenu non vide
    # (titre de section OU au moins un item non vide).
    sections = _lire_sections_fiche(conn, fiche_id)
    a_du_contenu = False
    for sec in sections:
        if (sec.get("titre") or "").strip():
            a_du_contenu = True
            break
        items = sec.get("items") or []
        if any((it or "").strip() for it in items):
            a_du_contenu = True
            break
    if not a_du_contenu:
        raisons.append("Aucune section avec contenu (titre ou item).")

    if raisons:
        raise VPE(
            "La fiche ne peut pas être validée en l'état.",
            raisons=raisons,
            type_atome='fiche_resume',
            atome_id=fiche_id,
        )


def _enregistrer_hook_validation_fiche() -> None:
    from services.etats_edition import enregistrer_hook_validation
    enregistrer_hook_validation('fiche_resume', _valider_fiche_hook)


_enregistrer_hook_validation_fiche()
