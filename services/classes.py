"""
services/classes.py — Logique métier des classes et élèves.

Toutes les fonctions reçoivent les données en paramètre
et retournent les données modifiées. Aucun I/O.
"""

from __future__ import annotations
import re
from persistence.ids import nouveau_id_classe, nouveau_id_eleve


# ── Helpers ────────────────────────────────────────────────────────────────────

def slug(s: str) -> str:
    """'4EME 3 A' → '4EME3A' — utilisé pour le slug d'établissement, pas pour les ids."""
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def trouver_classe(classes_data: dict, cid: str) -> dict | None:
    """Retourne la classe avec cet id, ou None."""
    return next(
        (c for c in classes_data.get("classes", []) if c["id"] == cid),
        None,
    )


# Conservation des anciens noms en tant qu'alias pour rétrocompat des appels
# existants dans le codebase. Le paramètre `nom`/`existants` est ignoré : la
# garantie d'unicité est portée par l'UUID lui-même et par la contrainte SQL.
def generer_id_classe(nom: str = "", existants=None) -> str:
    return nouveau_id_classe()


def generer_id_eleve(existants=None) -> str:
    return nouveau_id_eleve()


# ── Opérations sur les classes ─────────────────────────────────────────────────

def creer_classe(classes_data: dict, nom: str, niveau: str,
                 annee: str, etablissement: str,
                 etablissement_id: str | None = None) -> tuple[dict, dict]:
    """
    Crée une nouvelle classe et l'ajoute à classes_data.
    Retourne (classes_data_modifié, nouvelle_classe).

    v0.41.2 — `etablissement_id` (choisi dans un sélecteur) est prioritaire ;
    le nom `etablissement` ne sert plus qu'aux imports.
    """
    existants = {c["id"] for c in classes_data.get("classes", [])}
    cid = generer_id_classe(nom, existants)
    nouvelle = {
        "id":             cid,
        "nom":            nom,
        "niveau":         niveau,
        "annee":          annee,
        "etablissement":  etablissement,
        "eleves":         [],
        **({"etablissement_id": etablissement_id} if etablissement_id else {}),
        "versions_actives":      {},
        "sequences_verouillees": [],
    }
    classes_data.setdefault("classes", []).append(nouvelle)
    return classes_data, nouvelle


def modifier_classe(classes_data: dict, cid: str, champs: dict) -> dict | None:
    """
    Met à jour les métadonnées d'une classe.
    Retourne la classe modifiée, ou None si introuvable.
    """
    for c in classes_data.get("classes", []):
        if c["id"] == cid:
            for k in ("nom", "niveau", "annee", "etablissement"):
                if k in champs:
                    c[k] = champs[k]
            for k in ("seances_A", "seances_B"):
                if k in champs:
                    try:
                        c[k] = max(0, int(champs[k] or 0))
                    except (TypeError, ValueError):
                        c[k] = 0
            if "mer_active" in champs:
                c["mer_active"] = 1 if champs["mer_active"] else 0
            if "mer_mode" in champs:
                mode = champs["mer_mode"]
                if mode in ("automatismes", "progression", "panache"):
                    c["mer_mode"] = mode
            return c
    return None


def supprimer_classe(classes_data: dict, suivi: dict,
                     niveaux: dict, cid: str) -> tuple[dict, dict, dict]:
    """
    Supprime une classe et nettoie les données de suivi associées.
    Retourne (classes_data, suivi, niveaux) modifiés.
    """
    classes_data["classes"] = [
        c for c in classes_data.get("classes", []) if c["id"] != cid
    ]
    suivi.pop(cid, None)
    niveaux.pop(cid, None)
    return classes_data, suivi, niveaux


# ── Opérations sur les élèves ──────────────────────────────────────────────────

def ajouter_eleve(classes_data: dict, cid: str,
                  nom: str, prenom: str) -> tuple[dict, dict | None]:
    """
    Ajoute un élève à une classe.
    Retourne (classes_data_modifié, élève_créé) ou (classes_data, None) si classe introuvable.
    """
    for c in classes_data.get("classes", []):
        if c["id"] == cid:
            existants = {e["id"] for e in c.get("eleves", [])}
            eid = generer_id_eleve(existants)
            eleve = {"id": eid, "nom": nom.upper(), "prenom": prenom}
            c.setdefault("eleves", []).append(eleve)
            c["eleves"].sort(key=lambda e: (e["nom"], e["prenom"]))
            return classes_data, eleve
    return classes_data, None


def supprimer_eleve(classes_data: dict, suivi: dict,
                    niveaux: dict, cid: str,
                    eid: str) -> tuple[dict, dict, dict]:
    """
    Supprime un élève et nettoie ses données de suivi.
    Retourne (classes_data, suivi, niveaux) modifiés.
    """
    for c in classes_data.get("classes", []):
        if c["id"] == cid:
            c["eleves"] = [e for e in c.get("eleves", []) if e["id"] != eid]
            break
    for seq_data in suivi.get(cid, {}).values():
        seq_data.pop(eid, None)
    for seq_data in niveaux.get(cid, {}).values():
        seq_data.pop(eid, None)
    return classes_data, suivi, niveaux


def importer_eleves_csv(classes_data: dict, cid: str,
                        rows: list[dict],
                        col_nom: str, col_prenom: str) -> tuple[dict, dict]:
    """
    Importe une liste d'élèves depuis des lignes CSV parsées.
    Ignore les doublons (comparaison nom+prénom insensible à la casse).
    Retourne (classes_data_modifié, résumé {ajouts, ignores, eleves}).
    """
    classe = trouver_classe(classes_data, cid)
    if not classe:
        return classes_data, {"erreur": "classe introuvable"}

    existants_noms = {
        (e["nom"].upper(), e["prenom"].upper())
        for e in classe.get("eleves", [])
    }
    existants_ids = {e["id"] for e in classe.get("eleves", [])}

    ajouts = []
    ignores = []

    for row in rows:
        nom    = row.get(col_nom, "").strip().upper()
        prenom = row.get(col_prenom, "").strip()
        if not nom or not prenom:
            continue
        if (nom, prenom.upper()) in existants_noms:
            ignores.append(f"{nom} {prenom}")
            continue
        eid = generer_id_eleve(existants_ids)
        existants_ids.add(eid)
        existants_noms.add((nom, prenom.upper()))
        eleve = {"id": eid, "nom": nom, "prenom": prenom}
        classe.setdefault("eleves", []).append(eleve)
        ajouts.append(eleve)

    classe["eleves"].sort(key=lambda e: (e["nom"], e["prenom"]))
    return classes_data, {
        "ajouts":  len(ajouts),
        "ignores": len(ignores),
        "eleves":  classe["eleves"],
    }


# ── Verrous de séquence ────────────────────────────────────────────────────────

def verrouiller_sequence(classes_data: dict, cid: str,
                         niveau: str, seq: str) -> dict:
    """
    Verrouille une séquence pour une classe dès la première saisie.
    Retourne classes_data (potentiellement modifié).
    """
    classe = trouver_classe(classes_data, cid)
    if not classe:
        return classes_data
    key = f"{niveau}_{seq}"
    locked = classe.setdefault("sequences_verouillees", [])
    if key not in locked:
        locked.append(key)
    return classes_data


def est_verrouille(classe: dict, niveau: str, seq: str) -> bool:
    """Retourne True si la séquence est verrouillée pour cette classe."""
    key = f"{niveau}_{seq}"
    return key in classe.get("sequences_verouillees", [])


def definir_version_active(classes_data: dict, cid: str,
                           niveau: str, seq: str,
                           tag: str | None) -> tuple[dict, str | None]:
    """
    Définit la version active d'une séquence pour une classe.
    Retourne (classes_data, erreur_msg). erreur_msg est None si OK.
    """
    classe = trouver_classe(classes_data, cid)
    if not classe:
        return classes_data, "classe introuvable"
    if est_verrouille(classe, niveau, seq):
        return classes_data, (
            "Cette séquence est verrouillée (résultats déjà saisis). "
            "Créez une nouvelle version du livret pour continuer."
        )
    key = f"{niveau}_{seq}"
    classe.setdefault("versions_actives", {})[key] = tag
    return classes_data, None
