"""
importers/scanner_latex.py — Logique métier du scanner LaTeX + adaptation
SqliteStore.

Le parsing LaTeX (scanner_niveau, parse_*) vient du fichier
`scanner_latex.py` à la racine de `appli/` (inchangé).

`scanner_vers_bdd` orchestre deux étapes :

1. Résolution des macros nommantes (titres de notions et de méthodes)
   via `services.resoudre_macros`. Contexte chargé depuis les CSV de
   référence (param_niveaux.csv, C0X_sequences.csv, C0X_themes.csv,
   C0X_connaissances.csv, C0X_objectifs.csv) puis, depuis v0.58.2,
   complété par les tables vivantes de la base, qui ont le dernier mot
   (`completer_depuis_base`). Les macros qui pointent vers une référence
   introuvable sont remplacées par `[à saisir]` avec un incident au
   rapport.

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
    completer_depuis_base,
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
    # v0.58.2 (P1) — Tables vivantes d'abord, CSV de départ en repli (rattachés
    # au code vivant A1 quand la séquence a le même nom) : après la migration
    # des codes, un titre `\seqObjectifGetNom{06}` d'un `.tex` de A1 prend le
    # nom de l'objectif 06 de A1 au lieu de « [à saisir] ».
    _completer_contexte(ctx, json_store)
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

    # v0.58.2 (P3) — Écriture **additive** : seules les notions et méthodes
    # dont le `fichier` est absent de la base sont insérées. Avant, la liste
    # complète était réécrite (DELETE + INSERT) : chaque scan effaçait les
    # liens objectif ↔ notion (`objectif_notions`, cascade) et refaisait les
    # liens méthode ↔ objectif d'après (niveau, séquence, num_objectif), ce
    # qui, après la migration, détachait ou intervertissait les méthodes
    # reclassées (liées par identifiant à leur objectif d'archive).

    # Notions
    notions = json_store.lire_notions()
    ids_n = {n.get("fichier", "") for n in notions if n.get("fichier")}
    nouvelles_n = [n for n in data["notions"] if n.get("fichier") not in ids_n]
    _ajouter(json_store, "notions", notions, nouvelles_n)

    # Objectifs — réhydratation depuis referentiel_objectifs.
    # Ce pont est indispensable : le `reset_reference` vide `objectifs`
    # mais pas `referentiel_objectifs`. Sans cette réhydratation, la
    # table `objectifs` reste vide après un reset + scan, et le
    # peuplement v2 ne peut pas créer les `objectifs` correspondants
    # — ce qui laisserait l'atelier Séquence avec « partie 1 vide ».
    # `ecrire_methodes` et `ecrire_exercices` consultent aussi
    # `objectifs` pour poser leurs liaisons, donc l'étape doit passer
    # avant.
    #
    # v0.58.2 (P2) — Seulement pour les séquences qui existent dans les
    # séquences du cycle du niveau (tables vivantes) : après la migration,
    # l'instantané d'un référentiel verrouillé en codes S… (2025_N11b) ne
    # recrée plus N11/S01…S14 dans l'atelier.
    try:
        _ecrire_objectifs(json_store)
    except Exception as e:
        # Non bloquant : si la réhydratation plante, on poursuit (les
        # objectifs peuvent avoir été peuplés autrement).
        data.setdefault("erreurs", []).append(f"ecrire_objectifs : {e}")

    # Méthodes
    methodes = json_store.lire_methodes()
    ids_m = {m.get("fichier", "") for m in methodes if m.get("fichier")}
    nouvelles_m = [m for m in data["methodes"] if m.get("fichier") not in ids_m]
    _ajouter(json_store, "methodes", methodes, nouvelles_m)

    # Exercices
    exercices = json_store.lire_exercices()
    ids_e = {e.get("fichier", "") for e in exercices if e.get("fichier")}
    nouveaux_e = [e for e in data["exercices"] if e.get("fichier") not in ids_e]
    exercices.extend(nouveaux_e)
    json_store.ecrire_exercices(exercices)

    # v0.51.11 — Les livrets scannés ne sont plus enregistrés (anciens
    # livrets importés retirés ; les livrets se construisent dans les ateliers).
    nouveaux_l = []

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


def _completer_contexte(ctx, json_store) -> None:
    """v0.58.2 — Superpose les tables vivantes de la base du magasin au
    contexte lu dans les CSV (sans effet si le magasin n'a pas de base)."""
    ouvrir = getattr(json_store, "_conn", None)
    if ouvrir is None:
        return
    try:
        with ouvrir() as conn:
            completer_depuis_base(ctx, conn)
    except Exception:
        pass


def _ajouter(json_store, quoi: str, existants: list, nouveaux: list) -> None:
    """Insère les seuls nouveaux atomes (`ajouter_notions`,
    `ajouter_methodes`). Magasin sans ces méthodes (doublures de test) :
    ancienne réécriture complète."""
    ajout = getattr(json_store, f"ajouter_{quoi}", None)
    if callable(ajout):
        ajout(nouveaux)
        return
    getattr(json_store, f"ecrire_{quoi}")(existants + nouveaux)


def _ecrire_objectifs(json_store):
    import inspect
    f = json_store.ecrire_objectifs
    try:
        params = inspect.signature(f).parameters
        accepte = ("seulement_sequences_du_cycle" in params
                   or any(p.kind is p.VAR_KEYWORD for p in params.values()))
    except (TypeError, ValueError):
        accepte = False
    if accepte:
        return f(seulement_sequences_du_cycle=True)
    return f()                        # doublure de test sans ce paramètre


def _contexte_vide():
    """Fallback si csv_store n'est pas accessible (tests autonomes)."""
    from services.resoudre_macros import Contexte
    return Contexte()
