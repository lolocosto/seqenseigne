"""
services/etablissements.py — Gestion des établissements scolaires.

Un établissement a deux états :
- 'propose' : créé automatiquement à l'import, ou manuellement ; les méta
  (académie, ville…) peuvent être vides ou devinées.
- 'valide' : validé via l'annuaire de l'Éducation Nationale par UAI.
  Tous les champs sont alors sourcés officiellement.

La validation par UAI est asynchrone (appel API) : `valider_par_uai`
interroge `data.education.gouv.fr/fr-en-annuaire-education` et met à jour
les champs depuis la réponse officielle. Si l'UAI est introuvable ou
l'API indisponible, l'établissement reste 'propose' et une exception est
levée.
"""

from __future__ import annotations
import json
import urllib.parse
import urllib.request
from typing import Optional

from persistence.ids import nouveau_id_etablissement


URL_ANNUAIRE = (
    "https://data.education.gouv.fr/api/explore/v2.1/catalog/"
    "datasets/fr-en-annuaire-education/records"
)


class DoublonEtablissement(ValueError):
    """
    Levée quand une opération (validation UAI, renommage) créerait un
    doublon sur la contrainte UNIQUE(nom) de la table etablissements.

    Expose `etab_cible_id` (celui qui porte déjà le nom) pour que l'UI
    puisse proposer une fusion.
    """
    def __init__(self, message: str, etab_cible_id: str, nom: str):
        super().__init__(message)
        self.etab_cible_id = etab_cible_id
        self.nom = nom


class ConflitFusion(ValueError):
    """
    Levée quand une fusion est impossible :
    - source est 'valide' (interdiction absolue)
    - une progression de source entre en conflit avec une progression de
      cible sur la même clé métier (niveau, annee).
    """
    def __init__(self, message: str, code: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def creer(store, nom: str, academie: str = "", ville: str = "",
          adresse: str = "", uai: str = "") -> dict:
    """
    Crée un nouvel établissement (état 'propose').
    Si un établissement du même nom existe déjà, retourne l'existant
    (pas d'écrasement).
    """
    existant = store.lire_etablissement_par_nom(nom)
    if existant:
        return existant

    etab = {
        "id":       nouveau_id_etablissement(),
        "nom":      nom,
        "uai":      uai,
        "academie": academie,
        "ville":    ville,
        "adresse":  adresse,
        "etat":     "propose",
    }
    store.ecrire_etablissement(etab)
    return etab


def lister(store) -> list:
    """Retourne tous les établissements."""
    return store.lire_etablissements()


def lire(store, etab_id: str) -> Optional[dict]:
    """Retourne un établissement par id, ou None."""
    return store.lire_etablissement_par_id(etab_id)


def mettre_a_jour(store, etab_id: str, champs: dict) -> Optional[dict]:
    """
    Met à jour les méta d'un établissement (académie, ville, adresse, nom, uai).
    L'état n'est PAS modifié ici — il ne passe à 'valide' que via
    `valider_par_uai`.
    Retourne l'établissement mis à jour, ou None si introuvable.
    """
    etab = store.lire_etablissement_par_id(etab_id)
    if not etab:
        return None
    for k in ("nom", "academie", "ville", "adresse", "uai"):
        if k in champs:
            etab[k] = champs[k]
    store.ecrire_etablissement(etab)
    return etab


def valider_par_uai(store, etab_id: str, uai: str) -> dict:
    """
    Valide un établissement en interrogeant l'annuaire de l'Éducation
    Nationale par son code UAI. Remplit automatiquement les champs
    académie, ville, adresse depuis la source officielle et passe l'état
    à 'valide'.

    Lève :
      - ValueError si l'UAI est introuvable dans l'annuaire.
      - DoublonEtablissement si le nom officiel remonté par l'annuaire
        correspond à un autre établissement déjà en base. L'UI doit alors
        proposer une fusion (ex: "Collège des Hautes Ourmes" validé par
        l'UAI remonte "Collège Les Hautes Ourmes" → conflit avec un autre
        établissement déjà nommé ainsi).
    """
    etab = store.lire_etablissement_par_id(etab_id)
    if not etab:
        raise ValueError(f"Établissement {etab_id} introuvable")

    infos = rechercher_uai(store, uai)
    if not infos:
        raise ValueError(f"UAI {uai} introuvable dans l'annuaire")

    nom_officiel = infos.get("nom_etablissement", etab["nom"])

    # Détection du doublon : si le nom officiel est porté par un AUTRE
    # établissement, on refuse la validation et on laisse l'UI proposer
    # la fusion. (On ne bloque pas si c'est le même établissement qui se
    # valide sur son propre nom.)
    existant = store.lire_etablissement_par_nom(nom_officiel)
    if existant and existant["id"] != etab_id:
        raise DoublonEtablissement(
            f"Un autre établissement porte déjà le nom '{nom_officiel}' "
            f"(id={existant['id']}, état={existant['etat']}). "
            f"Une fusion est nécessaire avant validation.",
            etab_cible_id=existant["id"],
            nom=nom_officiel,
        )

    etab["uai"]      = uai
    etab["nom"]      = nom_officiel
    etab["academie"] = infos.get("libelle_academie", etab.get("academie", ""))
    etab["ville"]    = infos.get("nom_commune", etab.get("ville", ""))
    etab["adresse"]  = infos.get("adresse_1", etab.get("adresse", ""))
    etab["etat"]     = "valide"

    store.ecrire_etablissement(etab)
    return etab


def fusionner(store, source_id: str, cible_id: str) -> dict:
    """
    Fusionne l'établissement `source` dans `cible`.

    Toutes les classes et progressions liées à source sont migrées vers
    cible, puis source est supprimé. La cible conserve ses champs (nom,
    académie, état, etc.) — s'il y a une coquille dans le nom de cible,
    elle sera corrigée à la validation UAI ultérieure.

    Règles :
    - Fusion atomique (transaction).
    - Interdit si source.etat == 'valide' : on ne supprime jamais un
      établissement validé (seule la cible peut l'être). Pour corriger
      un cas comme celui-ci, l'enseignant doit fusionner dans l'autre
      sens.
    - Si une progression de source entre en conflit avec une progression
      de cible sur (niveau, annee), la fusion est refusée avec ConflitFusion.
      L'enseignant doit résoudre manuellement.

    Retourne la cible mise à jour, avec un résumé :
      {**cible, classes_migrees: N, progressions_migrees: M}
    """
    source = store.lire_etablissement_par_id(source_id)
    if not source:
        raise ValueError(f"Établissement source {source_id} introuvable")
    cible = store.lire_etablissement_par_id(cible_id)
    if not cible:
        raise ValueError(f"Établissement cible {cible_id} introuvable")
    if source_id == cible_id:
        raise ValueError("Source et cible identiques")

    if source["etat"] == "valide":
        raise ConflitFusion(
            f"Impossible de supprimer un établissement validé "
            f"('{source['nom']}'). Inverse le sens de la fusion : "
            f"utilise '{source['nom']}' comme cible.",
            code="source_validee",
            details={"source_id": source_id, "source_nom": source["nom"]},
        )

    with store.conn() as conn:
        # Détecter les conflits sur progressions (même niveau+annee)
        conflits = conn.execute("""
            SELECT ps.id   AS source_prog_id,
                   ps.niveau, ps.annee,
                   pc.id   AS cible_prog_id
            FROM progressions ps
            JOIN progressions pc
              ON pc.niveau = ps.niveau
             AND pc.annee  = ps.annee
             AND pc.etablissement_id = ?
            WHERE ps.etablissement_id = ?
        """, (cible_id, source_id)).fetchall()

        if conflits:
            lignes = [dict(c) for c in conflits]
            raise ConflitFusion(
                f"{len(lignes)} progression(s) en conflit : même (niveau, "
                f"année) dans source et cible. Résoudre manuellement avant "
                f"la fusion.",
                code="conflit_progression",
                details={"conflits": lignes},
            )

        # Compter avant de migrer (pour le rapport)
        n_classes = conn.execute(
            "SELECT COUNT(*) FROM classes WHERE etablissement_id = ?",
            (source_id,)
        ).fetchone()[0]
        n_progs = conn.execute(
            "SELECT COUNT(*) FROM progressions WHERE etablissement_id = ?",
            (source_id,)
        ).fetchone()[0]

        # Migration
        conn.execute(
            "UPDATE classes SET etablissement_id = ? WHERE etablissement_id = ?",
            (cible_id, source_id)
        )
        conn.execute(
            "UPDATE progressions SET etablissement_id = ? WHERE etablissement_id = ?",
            (cible_id, source_id)
        )
        # v0.37.0 — Les salles suivent l'établissement (refus si un même nom
        # de salle existe des deux côtés).
        from services import salles as _salles
        try:
            n_salles = _salles.migrer_etablissement(conn, source_id, cible_id)
        except _salles.DonneesInvalides as e:
            raise ConflitFusion(str(e), code="conflit_salle",
                                details={"source_id": source_id})
        conn.execute("DELETE FROM etablissements WHERE id = ?", (source_id,))

    # Relire la cible et y ajouter le rapport
    cible = store.lire_etablissement_par_id(cible_id)
    cible["classes_migrees"] = n_classes
    cible["progressions_migrees"] = n_progs
    cible["salles_migrees"] = n_salles
    return cible


def rechercher_uai(store, uai: str) -> Optional[dict]:
    """
    Interroge l'annuaire EN pour un UAI donné. Retourne les champs de
    l'enregistrement, ou None si introuvable.

    Utilise le cache_api pour éviter les requêtes répétées (les UAI sont
    des identifiants stables).
    """
    cle = f"annuaire:{uai}"
    with store.conn() as conn:
        row = conn.execute(
            "SELECT payload FROM cache_api WHERE cle = ?", (cle,)
        ).fetchone()
        if row:
            return json.loads(row["payload"])

    # Not cached → interroger l'API
    params = {
        "limit":  "1",
        "where":  f'identifiant_de_l_etablissement="{uai}"',
    }
    url = URL_ANNUAIRE + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, headers={"User-Agent": "seqenseigne/0.6.3"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise ValueError(f"API annuaire indisponible : {e}")

    results = data.get("results", [])
    if not results:
        return None
    infos = results[0]

    # Cache positif
    from datetime import datetime, timezone
    with store.conn() as conn:
        conn.execute("""
            INSERT INTO cache_api (cle, payload, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(cle) DO UPDATE SET
              payload=excluded.payload,
              fetched_at=excluded.fetched_at
        """, (cle, json.dumps(infos, ensure_ascii=False),
              datetime.now(timezone.utc).isoformat(timespec="seconds")))

    return infos
