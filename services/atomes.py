"""
services/atomes.py — Logique métier des atomes pédagogiques.

Opérations CRUD sur notions, méthodes et exercices.
Validation métier et génération d'identifiants.
"""

from __future__ import annotations
from persistence.ids import (
    nouveau_id_notion, nouveau_id_methode, nouveau_id_exercice
)

SERIES_VALIDES = frozenset(
    # v0.11.2 — 'révision' retiré. La notion de révision est portée
    # exclusivement par la table partie_exos_revision_approche (atelier
    # d'assemblage), pas comme attribut d'un exercice.
    {"fondamental", "avancé", "exploration", "approche"}
)

# v0.13.6.16.2 — Mapping série longue → code court utilisé en BdD.
# Doit rester cohérent avec persistence/sqlite_store.py:serie_vers_code
# (qui ajoute des alias de sécurité pour l'ancien vocabulaire). Ici on
# limite au strict nécessaire pour creer_exercice / modifier_exercice.
# Convention 'approche' → 'EA' côté frontend/sidebar ; certaines
# fonctions backend utilisent 'AE' (cf. v2_edition._SERIE_CODE_EQUIVALENT).
# On reste sur 'EA' qui est ce que la sidebar affiche.
_SERIE_VERS_CODE = {
    "fondamental": "F",
    "avancé":      "A",
    "exploration": "E",
    "approche":    "EA",
}


def _prochain_num_exercice(liste: list, niveau: str, sequence: str,
                            serie_code: str) -> int:
    """Calcule le prochain num libre pour un exercice dans une série
    donnée (niveau + sequence + serie_code). Convention : numérotation
    contigüe à partir de 1, donc on retourne max(num) + 1.

    v0.13.6.16.2 — Sans ce calcul, les exos créés via l'atelier
    héritaient de num=None et serie_code='', ce qui les rendait
    invisibles dans la sidebar (groupés dans le bucket « Autres » mal
    affiché).
    """
    nums_existants = [
        int(e.get("num", 0) or 0) for e in liste
        if (e.get("niveau") or "") == niveau
        and (e.get("sequence") or "") == sequence
        and (e.get("serie_code") or "") == serie_code
    ]
    return max(nums_existants, default=0) + 1


# ── Notions ────────────────────────────────────────────────────────────────────

# v0.6.4 — Modèle universel à 2 niveaux : les anciens champs `exemples`,
# `remarques` et `ordreExRem` sont remplacés par un champ unique `sections`,
# liste ordonnée de {titre, items} où items est une liste de chaînes LaTeX.
# Voir persistence/sqlite_store.py et services/latex_rendu_atome.py pour le
# format complet. Breaking change API assumé en alpha.

def creer_notion(liste: list, data: dict) -> tuple[list, dict, str | None]:
    """
    Crée une notion. Retourne (liste_modifiée, notion, erreur).

    v0.10.7 — Accepte les champs optionnels `niveau` et `sequence` qui
    fixent la séquence d'origine de la notion. Sans ces champs, la
    notion est créée hors-scope (legacy fallback). Le frontend les
    pose typiquement depuis le contexte courant ATL_FILTRE_NIVEAU /
    ATL_FILTRE_SEQ.

    v0.13.6.16 — Le titre n'est plus obligatoire à la création
    (modèle « en cours » : l'atome peut être incomplet, le hook de
    validation pédagogique exige le titre uniquement au passage en
    état `valide`). Pattern POST-direct unifié dans les ateliers.
    """
    notion = {
        "id":         nouveau_id_notion(),
        "titre":      data.get("titre", "").strip(),
        "corps":      data.get("corps", ""),
        "sections":   data.get("sections", []),
        # v0.10.7 — scope
        "niveau":     (data.get("niveau") or "").strip(),
        "sequence":   (data.get("sequence") or "").strip(),
    }
    liste.append(notion)
    return liste, notion, None


def modifier_notion(liste: list, notion_id: str,
                    data: dict) -> tuple[list, dict | None, str | None]:
    idx = next((i for i, n in enumerate(liste) if n["id"] == notion_id), None)
    if idx is None:
        return liste, None, "Notion non trouvée"
    # v0.10.7 — niveau/sequence ajoutés aux champs modifiables (pour
    # poser le scope sur une notion legacy ou corriger une erreur de
    # contexte).
    for champ in ("titre", "corps", "sections", "niveau", "sequence"):
        if champ in data:
            liste[idx][champ] = data[champ]
    if not liste[idx].get("titre", "").strip():
        return liste, None, "Le titre est obligatoire"
    return liste, liste[idx], None


def supprimer_notion(liste: list, notion_id: str) -> tuple[list, str | None]:
    avant = len(liste)
    liste = [n for n in liste if n["id"] != notion_id]
    if len(liste) == avant:
        return liste, "Notion non trouvée"
    return liste, None


# ── Méthodes ───────────────────────────────────────────────────────────────────

def creer_methode(liste: list, data: dict) -> tuple[list, dict, str | None]:
    """v0.10.7 — Idem creer_notion : accepte niveau/sequence.
    v0.13.6.16 — Titre non obligatoire à la création (modèle « en cours »).
    """
    methode = {
        "id":         nouveau_id_methode(),
        "titre":      data.get("titre", "").strip(),
        "corps":      data.get("corps", ""),
        "sections":   data.get("sections", []),
        "notions":    data.get("notions", []),
        "finCycle":   data.get("finCycle", "N"),
        "criteres":   data.get("criteres", {"2": "", "3": "", "4": ""}),
        # v0.10.7 — scope
        "niveau":     (data.get("niveau") or "").strip(),
        "sequence":   (data.get("sequence") or "").strip(),
    }
    liste.append(methode)
    return liste, methode, None


def modifier_methode(liste: list, methode_id: str,
                     data: dict) -> tuple[list, dict | None, str | None]:
    idx = next((i for i, m in enumerate(liste) if m["id"] == methode_id), None)
    if idx is None:
        return liste, None, "Méthode non trouvée"
    # v0.10.7 — niveau/sequence ajoutés.
    for champ in ("titre", "corps", "sections",
                  "notions", "finCycle", "criteres",
                  "niveau", "sequence"):
        if champ in data:
            liste[idx][champ] = data[champ]
    if not liste[idx].get("titre", "").strip():
        return liste, None, "Le titre est obligatoire"
    return liste, liste[idx], None


def supprimer_methode(liste: list, methode_id: str) -> tuple[list, str | None]:
    avant = len(liste)
    liste = [m for m in liste if m["id"] != methode_id]
    if len(liste) == avant:
        return liste, "Méthode non trouvée"
    return liste, None


# ── Exercices ──────────────────────────────────────────────────────────────────

# v0.13.5.2.3 — Déduction automatique de type_format depuis l'énoncé.
#
# Décision (Laurent) : type_format n'est pas saisi par l'enseignant, il est
# *dérivé* de la présence de l'environnement LaTeX `seqQcm` dans l'énoncé.
# La règle de détection est binaire : si l'énoncé contient `\begin{seqQcm}`,
# l'exercice est un QCM ; sinon il est standard.
#
# Cette déduction est appelée à chaque écriture (création + modification),
# pour que la valeur en BDD soit toujours synchronisée avec le contenu.
# Pas de UI à mettre à jour : le champ est purement dérivé.

import re

# Regex tolérant :
#   - les espaces et tabulations entre \begin et {seqQcm}
#   - les commentaires LaTeX (% ... \n) ne sont pas filtrés ici : si un
#     `\begin{seqQcm}` apparaît en commentaire, on classe quand même en
#     QCM. C'est cohérent : la présence du marqueur dans le source compte,
#     pas son rendu effectif. Cas marginal qui ne mérite pas plus de
#     complexité.
_RE_SEQQCM = re.compile(r"\\begin\s*\{seqQcm\}")


def _deduire_type_format(enonce: str) -> str:
    """Retourne 'qcm' si l'énoncé contient \\begin{seqQcm}, sinon 'standard'.

    Détection binaire, basée uniquement sur le contenu de l'énoncé
    (cf. décision Q1 v0.13.5.2.3 : on regarde uniquement `enonce`, pas
    `corrige` ni `remed_enonce`).
    """
    if not enonce:
        return "standard"
    return "qcm" if _RE_SEQQCM.search(enonce) else "standard"


def valider_exercice(data: dict) -> str | None:
    """Retourne un message d'erreur si les données sont invalides, None sinon.

    v0.13.6.16 — Seule `serie` reste obligatoire à la création (modèle
    « en cours » : énoncé et corrigé peuvent être saisis après création
    via PUT, exigés au passage en état `valide` par le hook de
    validation pédagogique).
    """
    if not data.get("serie", "").strip():
        return "Champ obligatoire manquant : serie"
    if data["serie"] not in SERIES_VALIDES:
        return f"serie doit être parmi : {', '.join(sorted(SERIES_VALIDES))}"
    return None


def creer_exercice(liste: list, data: dict) -> tuple[list, dict, str | None]:
    erreur = valider_exercice(data)
    if erreur:
        return liste, {}, erreur
    enonce = data.get("enonce", "")
    # v0.13.6.16.2 — Calcul de serie_code et num à la création (sans ça,
    # l'exo restait invisible dans la sidebar qui regroupe par série
    # via le préfixe du code). serie_code est dérivé de serie via le
    # mapping _SERIE_VERS_CODE ; num est le prochain entier libre dans
    # (niveau, sequence, serie_code).
    niveau   = (data.get("niveau") or "").strip()
    sequence = (data.get("sequence") or "").strip()
    serie    = data["serie"]
    serie_code = _SERIE_VERS_CODE.get(serie, "")
    num = _prochain_num_exercice(liste, niveau, sequence, serie_code)
    exercice = {
        "id":        nouveau_id_exercice(),
        "serie":     serie,
        "serie_code": serie_code,
        "num":       num,
        "titre":     data.get("titre", "").strip(),
        # v0.10.7 — champ `objectifs` retiré du payload accepté.
        # La liaison exercice ↔ objectif passe par l'atelier
        # d'assemblage (table objectif_exos). On initialise à [] pour
        # que `ecrire_exercices` ne tente pas de poser de liaisons
        # legacy.
        "objectifs": [],
        "variables": data.get("variables", ""),
        "enonce":    enonce,
        "corrige":   data.get("corrige", ""),
        # v0.13.5.2.3 — type_format dérivé de l'énoncé. La valeur passée
        # dans `data` est ignorée volontairement : le champ est purement
        # calculé, pas saisi.
        "type_format": _deduire_type_format(enonce),
        # v0.13.6.16 — scope niveau/sequence également stockés
        # (le pattern POST-direct des ateliers les pose systématiquement).
        "niveau":    niveau,
        "sequence":  sequence,
    }
    liste.append(exercice)
    return liste, exercice, None


def modifier_exercice(liste: list, exo_id: str,
                      data: dict) -> tuple[list, dict | None, str | None]:
    idx = next((i for i, e in enumerate(liste) if e["id"] == exo_id), None)
    if idx is None:
        return liste, None, "Exercice non trouvé"
    # v0.10.7 — `objectifs` retiré des champs modifiables : la liaison
    # passe par l'atelier d'assemblage.
    # v0.11.6 — Ajout des champs de remédiation et de cadre de réponse.
    # remed_enonce / remed_corrige : chaînes (vide = pas de remédiation).
    # cadre_reponse_lignes_principal / cadre_reponse_lignes_remed : entiers
    # (0 = pas de cadre, sinon hauteur en lignes). Côté UI le cadre
    # Remédiation n'est affiché que pour les exos de série F et A
    # (cadrage v0.11.6 Q2 option β), mais côté backend on accepte la
    # remédiation pour n'importe quelle série — l'UI fait juste de
    # l'auto-discipline.
    for champ in ("serie", "titre", "enonce", "corrige", "variables",
                  "remed_enonce", "remed_corrige"):
        if champ in data:
            liste[idx][champ] = data[champ]
    # v0.13.6.16.2 — Si la série a changé, recalculer serie_code et num
    # pour rester cohérent avec la BdD (l'exo doit pouvoir être retrouvé
    # par (niveau, sequence, serie_code) qui sert de clé fonctionnelle
    # dans les livrets et l'assemblage). num est ré-attribué car l'ancien
    # numéro était relatif à l'ancienne série, et pourrait entrer en
    # collision dans la nouvelle.
    if "serie" in data:
        nouvelle_serie_code = _SERIE_VERS_CODE.get(liste[idx]["serie"], "")
        ancienne_serie_code = liste[idx].get("serie_code", "")
        if nouvelle_serie_code != ancienne_serie_code:
            liste[idx]["serie_code"] = nouvelle_serie_code
            # Calcul du nouveau num en excluant l'exo courant de la liste
            # pour éviter d'incrémenter par rapport à soi-même si serie_code
            # est resté vide à l'origine.
            autres = [e for e in liste if e["id"] != exo_id]
            liste[idx]["num"] = _prochain_num_exercice(
                autres,
                liste[idx].get("niveau", "") or "",
                liste[idx].get("sequence", "") or "",
                nouvelle_serie_code,
            )
    for champ_int in ("cadre_reponse_lignes_principal",
                      "cadre_reponse_lignes_remed"):
        if champ_int in data:
            try:
                v = int(data[champ_int])
            except (TypeError, ValueError):
                v = 0
            # Borner pour éviter les valeurs absurdes (un cadre de 1000
            # lignes casserait la mise en page silencieusement).
            if v < 0:
                v = 0
            elif v > 99:
                v = 99
            liste[idx][champ_int] = v
    # v0.13.5.2.3 — Recalculer type_format à chaque modification, qu'il
    # ait été passé dans `data` ou non. Le champ est purement dérivé du
    # contenu de l'énoncé : si l'énoncé courant (après merge ci-dessus)
    # contient `\begin{seqQcm}`, on a un QCM, sinon standard.
    # On lit `liste[idx]["enonce"]` plutôt que `data` parce que `data`
    # peut être une modification partielle qui ne contient pas `enonce`.
    liste[idx]["type_format"] = _deduire_type_format(liste[idx].get("enonce", ""))
    erreur = valider_exercice(liste[idx])
    if erreur:
        return liste, None, erreur
    return liste, liste[idx], None


def supprimer_exercice(liste: list, exo_id: str) -> tuple[list, str | None]:
    avant = len(liste)
    liste = [e for e in liste if e["id"] != exo_id]
    if len(liste) == avant:
        return liste, "Exercice non trouvé"
    return liste, None


# ── Diagnostics qualité (routes admin) ────────────────────────────────────────

def exercices_sans_corrige(exercices: list) -> list:
    """Retourne les exercices dont le corrigé est absent ou vide."""
    return [
        {"id": e["id"], "serie": e.get("serie"), "titre": e.get("titre", ""),
         "niveau": e.get("niveau", ""), "sequence": e.get("sequence", "")}
        for e in exercices
        if not e.get("corrige", "").strip()
    ]


def notions_sans_exemple(notions: list) -> list:
    """Retourne les notions sans aucune section (Exemples, Remarques, etc.).

    v0.6.4 — Le critère est désormais : la notion n'a aucune section avec
    au moins un item non vide. Le nom de la fonction est conservé pour
    la compatibilité avec les appelants (rapports de couverture, etc.).
    """
    return [
        {"id": n["id"], "titre": n["titre"]}
        for n in notions
        if not _a_des_items(n)
    ]


def methodes_sans_exemple(methodes: list) -> list:
    """Retourne les méthodes sans aucune section non vide.

    v0.6.4 — cf. notions_sans_exemple : critère adapté au modèle universel.
    """
    return [
        {"id": m["id"], "titre": m["titre"]}
        for m in methodes
        if not _a_des_items(m)
    ]


def _a_des_items(atome: dict) -> bool:
    """Helper v0.6.4 — True si l'atome a au moins une section avec au moins
    un item non vide. Utilisé par les rapports de couverture pour signaler
    les notions/méthodes incomplètes.
    """
    for sec in atome.get("sections", []) or []:
        for item in sec.get("items", []) or []:
            if (item or "").strip():
                return True
    return False


def atomes_non_affectes(notions: list, methodes: list,
                        exercices: list, livrets: list) -> dict:
    """
    Retourne les atomes non référencés dans aucun livret.
    Un atome est "affecté" si son champ 'fichier' apparaît dans un livret.
    """
    fichiers_notions_livrets = {
        f for l in livrets for f in l.get("notions", [])
    }
    fichiers_methodes_livrets = {
        f for l in livrets for f in l.get("methodes", [])
    }
    # Pour les exercices, on vérifie niveau+sequence+serie+num
    exos_livrets: set[tuple] = set()
    for l in livrets:
        niv, seq = l.get("niveau", ""), l.get("sequence", "")
        for serie, nums in l.get("exercices", {}).items():
            for num in nums:
                exos_livrets.add((niv, seq, serie, num))

    notions_orphelines = [
        {"id": n["id"], "titre": n["titre"], "fichier": n.get("fichier", "")}
        for n in notions
        if n.get("fichier", "") not in fichiers_notions_livrets
    ]
    methodes_orphelines = [
        {"id": m["id"], "titre": m["titre"], "fichier": m.get("fichier", "")}
        for m in methodes
        if m.get("fichier", "") not in fichiers_methodes_livrets
    ]
    exercices_orphelins = [
        {"id": e["id"], "serie": e.get("serie"), "fichier": e.get("fichier", "")}
        for e in exercices
        if (e.get("niveau"), e.get("sequence"),
            e.get("serie_code"), e.get("num")) not in exos_livrets
    ]

    return {
        "notions":   notions_orphelines,
        "methodes":  methodes_orphelines,
        "exercices": exercices_orphelins,
    }


# ── v0.13.6.16 — Hooks de validation pédagogique ──────────────────────────
#
# Suite à la relâche des contraintes de création (titre/énoncé/corrigé
# vides autorisés pour permettre le pattern POST-direct unifié des
# ateliers), on ajoute des hooks au passage en état `valide` pour
# refuser la validation d'atomes incomplets.
#
# Pattern aligné sur `_valider_carte_hook` dans services/cartes_automatisme.py :
# le hook lit l'atome via SQLite, accumule les raisons d'échec, et lève
# ValidationPedagogiqueErreur si la liste n'est pas vide.

def _valider_notion_hook(conn, notion_id: str) -> None:
    """Refuse le passage en `valide` si la notion est incomplète.

    Règles : titre non vide.
    """
    from services.etats_edition import ValidationPedagogiqueErreur as VPE

    row = conn.execute(
        "SELECT titre FROM notions WHERE id = ?", (notion_id,),
    ).fetchone()
    if row is None:
        return  # changer_etat_atome a déjà vérifié l'existence.

    raisons = []
    if not (row["titre"] or "").strip():
        raisons.append("Le titre est vide.")

    if raisons:
        raise VPE(
            "La notion ne peut pas être validée en l'état.",
            raisons=raisons,
            type_atome='notion',
            atome_id=notion_id,
        )


def _valider_methode_hook(conn, methode_id: str) -> None:
    """Refuse le passage en `valide` si la méthode est incomplète.

    Règles : titre non vide.
    """
    from services.etats_edition import ValidationPedagogiqueErreur as VPE

    row = conn.execute(
        "SELECT titre FROM methodes WHERE id = ?", (methode_id,),
    ).fetchone()
    if row is None:
        return

    raisons = []
    if not (row["titre"] or "").strip():
        raisons.append("Le titre est vide.")

    if raisons:
        raise VPE(
            "La méthode ne peut pas être validée en l'état.",
            raisons=raisons,
            type_atome='methode',
            atome_id=methode_id,
        )


def _valider_exercice_hook(conn, exo_id: str) -> None:
    """Refuse le passage en `valide` si l'exercice est incomplet.

    Règles :
      - énoncé et corrigé non vides (le corrigé est toujours présent
        sur les exos validés, c'est une règle d'or du projet) ;
      - v0.14.8 — symétrie de remédiation : soit les deux champs
        remed_enonce et remed_corrige sont vides (= pas de remédiation),
        soit les deux sont non vides (= remédiation complète). Une
        remédiation partielle (un seul des deux rempli) est interdite
        au passage en `valide`.

    L'activation de la remédiation est dérivée des champs (cf. cadrage
    v0.14.8 Q2=a) : pas de champ booléen explicite en base.
    """
    from services.etats_edition import ValidationPedagogiqueErreur as VPE

    # Schéma exercices : enonce, corrige, remed_enonce, remed_corrige
    # sont tous dans la table.
    row = conn.execute(
        "SELECT enonce, corrige, remed_enonce, remed_corrige "
        "FROM exercices WHERE id = ?",
        (exo_id,),
    ).fetchone()
    if row is None:
        return

    raisons = []
    if not (row["enonce"] or "").strip():
        raisons.append("L'énoncé est vide.")
    if not (row["corrige"] or "").strip():
        raisons.append("Le corrigé est vide.")

    # v0.14.8 — Remédiation : si l'un des deux champs est rempli,
    # l'autre doit l'être aussi.
    remed_en = (row["remed_enonce"]  or "").strip()
    remed_co = (row["remed_corrige"] or "").strip()
    if remed_en and not remed_co:
        raisons.append(
            "Remédiation activée : le corrigé de remédiation est vide."
        )
    elif remed_co and not remed_en:
        raisons.append(
            "Remédiation activée : l'énoncé de remédiation est vide."
        )

    if raisons:
        raise VPE(
            "L'exercice ne peut pas être validé en l'état.",
            raisons=raisons,
            type_atome='exercice',
            atome_id=exo_id,
        )


def _enregistrer_hooks_validation_atomes() -> None:
    """Enregistre les hooks au chargement du module. Le service est
    importé par les routes au démarrage Flask, donc les hooks sont en
    place avant les premiers appels HTTP."""
    from services.etats_edition import enregistrer_hook_validation
    enregistrer_hook_validation('notion',   _valider_notion_hook)
    enregistrer_hook_validation('methode',  _valider_methode_hook)
    enregistrer_hook_validation('exercice', _valider_exercice_hook)


_enregistrer_hooks_validation_atomes()
