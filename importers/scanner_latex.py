"""
importers/scanner_latex.py — Logique métier du scanner LaTeX + adaptation
SqliteStore.

Le parsing LaTeX (scanner_niveau, parse_*) vient du fichier
`scanner_latex.py` à la racine de `appli/` (inchangé).

`scanner_vers_bdd` orchestre deux étapes :

1. Résolution des macros nommantes (titres de notions et de méthodes)
   via `services.resoudre_macros`. Contexte chargé depuis les CSV de
   référence (param_niveaux.csv, C0X_sequences.csv, C0X_themes.csv,
   C0X_connaissances.csv, C0X_objectifs.csv). Les macros qui pointent
   vers une référence introuvable sont remplacées par `[à saisir]`
   avec un incident au rapport.

   ⚠ Seuls les champs de type « nom / libellé » (titre de notion,
   titre de méthode) sont résolus. Les champs de saisie LaTeX
   (corps / exemples / remarques / énoncés / corrigés) restent
   intacts : ce sont des fragments LaTeX pédagogiques que seule la
   compilation doit développer.

2. Persistance des atomes via le `SqliteStore`.

v0.14.6.b.2 — L'ancienne étape 3 (peuplement v2 via
services.scanner_vers_v2.peupler_v2_depuis_base) a été RETIRÉE. Le
fichier scanner_vers_v2.py dépendait entièrement de la table v1
`objectifs` (supprimée) et de `livret_exercices` (supprimée). La
BDD étant désormais source de vérité, l'enrichissement de la v2 par
re-scan des .tex n'a plus de sens : les tables v2 sont alimentées
directement par les ateliers (atelier d'assemblage séquence-niveau,
ateliers atomiques) qui écrivent dans `objectifs`, `objectif_exos`,
etc.
"""

import sys
import os

# Accès au scanner_latex.py historique à la racine de appli/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scanner_latex import (  # noqa: E402
    scanner_niveau,
    parse_notions_file,
    parse_methode_file,
    parse_exercice_file,
    parse_livret_file,
)

from services.resoudre_macros import (  # noqa: E402
    construire_contexte_global,
    resoudre,
    contient_macro_nommante,
)


def scanner_vers_bdd(data: dict, json_store, csv_store=None,
                     plans_dir=None) -> dict:
    """
    Résout les titres, persiste les atomes, peuple les tables v2.

    Paramètres
    ----------
    data : dict
        Résultat de `scanner_niveau(chemin, niveau)` — contient les
        clés `niveau`, `notions`, `methodes`, `exercices`, `livrets`,
        `erreurs`.

    json_store : SqliteStore
        Magasin de persistance des atomes.

    csv_store : CsvStore | None
        Pour charger les référentiels utilisés par le résolveur. Si
        None, on tente de le lire depuis Flask (current_app.csv_store).
        À défaut, la résolution fonctionne toujours mais sur un
        contexte vide (tout devient `[à saisir]` avec incident).

    plans_dir : pathlib.Path | str | None
        Dossier racine des sources LaTeX (contenant `N10/`, `N11/`,
        `N12/` et les `N1X_Plan_de_travail.tex`). Nécessaire pour
        l'étape de peuplement v2. Si None, cette étape est sautée
        silencieusement (les tables v2 restent vides pour le niveau
        concerné).

    Retour
    ------
    {
      "notions":   {"total": N, "nouvelles": M},
      "methodes":  {"total": N, "nouvelles": M},
      "exercices": {"total": N, "nouvelles": M},
      "livrets":   {"total": N, "nouvelles": M},
      "erreurs":   [...],           # erreurs fatales de parsing
      "incidents_macros": [...],    # macros non résolues (titre + fichier)
      "v2": {                       # compteurs du peuplement v2
          "niveau": "N11", "sequences_par_niveau": 14,
          "parties": 18, "objectifs": 76, "objectif_exos": 243,
      },
    }

    Format des incidents macros :
      { "fichier": "N11_S01_Methode_02.tex", "champ": "titre",
        "macro":   "\\seqObjectifGetNom{02}",
        "raison":  "objectif 02 introuvable pour N11/S01" }
    """
    # ── 1. Contexte de résolution depuis les CSV ─────────────────────────
    if csv_store is None:
        try:
            from flask import current_app
            csv_store = current_app.csv_store
        except Exception:
            csv_store = None

    ctx = construire_contexte_global(csv_store) if csv_store else _contexte_vide()
    incidents_globaux: list[dict] = []

    # ── 2. Résoudre les titres des notions et des méthodes ──────────────
    # Les titres sont la seule surface impactée par la résolution au
    # moment de l'import. Les champs libres (corps, exemples, remarques,
    # énoncés, corrigés) restent tels quels — ce sont des fragments
    # LaTeX pédagogiques.
    for notion in data.get("notions", []):
        _resoudre_champ(notion, "titre", ctx, incidents_globaux)

    for methode in data.get("methodes", []):
        _resoudre_champ(methode, "titre", ctx, incidents_globaux)

    # Le champ `nom` d'un exercice est un libellé tapé manuellement dans
    # l'option `nom=` du \begin{seqExercice}[...], sans macro nommante.
    # Si ça évolue, ajouter ici un appel symétrique.

    # ── 3. Persistance ─────────────────────────────────────────────────
    # Ordre imposé par les dépendances :
    #   notions
    #   objectifs (réhydratés depuis referentiel_objectifs)
    #   methodes (pose methode_id sur les objectifs par (niveau, seq, code))
    #   exercices (résout les objectifs_codes en ids via niveau+seq+code)
    #   livrets_importes
    #   peuplement v2 (lit objectifs → crée parties + objectifs + objectif_exos)

    # Notions
    notions = json_store.lire_notions()
    ids_n = {n.get("fichier", "") for n in notions if n.get("fichier")}
    nouvelles_n = [n for n in data["notions"] if n.get("fichier") not in ids_n]
    notions.extend(nouvelles_n)
    json_store.ecrire_notions(notions)

    # Objectifs — réhydratation depuis referentiel_objectifs.
    # Ce pont est indispensable : le `reset_reference` vide `objectifs`
    # mais pas `referentiel_objectifs`. Sans cette réhydratation, la
    # table `objectifs` reste vide après un reset + scan, et le
    # peuplement v2 ne peut pas créer les `objectifs` correspondants
    # — ce qui laisserait l'atelier Séquence avec « partie 1 vide ».
    # `ecrire_methodes` et `ecrire_exercices` consultent aussi
    # `objectifs` pour poser leurs liaisons, donc l'étape doit passer
    # avant.
    try:
        json_store.ecrire_objectifs()
    except Exception as e:
        # Non bloquant : si la réhydratation plante, on poursuit (les
        # objectifs peuvent avoir été peuplés autrement).
        data.setdefault("erreurs", []).append(f"ecrire_objectifs : {e}")

    # Méthodes
    methodes = json_store.lire_methodes()
    ids_m = {m.get("fichier", "") for m in methodes if m.get("fichier")}
    nouvelles_m = [m for m in data["methodes"] if m.get("fichier") not in ids_m]
    methodes.extend(nouvelles_m)
    json_store.ecrire_methodes(methodes)

    # Exercices
    exercices = json_store.lire_exercices()
    ids_e = {e.get("fichier", "") for e in exercices if e.get("fichier")}
    nouveaux_e = [e for e in data["exercices"] if e.get("fichier") not in ids_e]
    exercices.extend(nouveaux_e)
    json_store.ecrire_exercices(exercices)

    # Livrets
    livrets = json_store.lire_livrets_importes()
    ids_l = {(l["niveau"], l["sequence"]) for l in livrets}
    nouveaux_l = [l for l in data["livrets"]
                  if (l["niveau"], l["sequence"]) not in ids_l]
    livrets.extend(nouveaux_l)
    json_store.ecrire_livrets_importes(livrets)

    # v0.14.6.b.2 — Étape 4 (Peuplement v2 via scanner_vers_v2)
    # supprimée : voir docstring du module. Les tables v2 sont alimentées
    # par les ateliers, pas par re-scan des .tex.

    return {
        "notions":          {"total": len(data["notions"]),   "nouvelles": len(nouvelles_n)},
        "methodes":         {"total": len(data["methodes"]),  "nouvelles": len(nouvelles_m)},
        "exercices":        {"total": len(data["exercices"]), "nouvelles": len(nouveaux_e)},
        "livrets":          {"total": len(data["livrets"]),   "nouvelles": len(nouveaux_l)},
        "erreurs":          data["erreurs"],
        "incidents_macros": incidents_globaux,
        # v0.14.6.b.2 — clé "v2" retirée du rapport ; le rapport est
        # désormais purement sur les atomes (notions/méthodes/exercices/
        # livrets).
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internes
# ─────────────────────────────────────────────────────────────────────────────

def _resoudre_champ(atome: dict, champ: str, ctx, incidents_globaux: list[dict]) -> None:
    """
    Résout les macros nommantes du champ `atome[champ]` en place.
    Positionne le contexte séquence courant sur l'atome (niveau, seq).
    Chaque incident collecté est enrichi avec le fichier et le champ,
    puis ajouté à `incidents_globaux`.
    """
    valeur = atome.get(champ, "") or ""
    if not contient_macro_nommante(valeur):
        return

    ctx.niveau_courant = atome.get("niveau", "") or ""
    ctx.sequence_courante = atome.get("sequence", "") or ""

    resolu, incidents = resoudre(valeur, ctx)
    atome[champ] = resolu

    if incidents:
        fichier = atome.get("fichier", "") or "(sans fichier)"
        for inc in incidents:
            incidents_globaux.append({
                "fichier": fichier,
                "champ":   champ,
                "macro":   inc["macro"],
                "raison":  inc["raison"],
            })


# v0.14.6.b.2 — Helper `_peupler_v2` retiré. Voir docstring du module.


def _contexte_vide():
    """Fallback si csv_store n'est pas accessible (tests autonomes)."""
    from services.resoudre_macros import Contexte
    return Contexte()
