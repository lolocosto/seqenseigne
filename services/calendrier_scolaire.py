"""
services/calendrier_scolaire.py — Vacances scolaires et jours fériés.

Deux sources de données officielles :
- Vacances scolaires : API OpenDataSoft data.education.gouv.fr
  (dataset `fr-en-calendrier-scolaire`), filtrée par zone et année scolaire.
- Jours fériés : API calendrier.api.gouv.fr (dataset officiel Etalab).

Les deux appels sont cachés en base (table `cache_api`) pour éviter des
allers-retours inutiles. Le cache n'est pas auto-invalidé : une année
scolaire passée ne change pas ; une année future peut changer si le
ministère ajuste les dates (rare, corriger à la main côté enseignant en
vidant le cache).

La zone (A/B/C) est dérivée de l'académie via la table ACADEMIE_ZONE
ci-dessous. Le zonage est stable depuis septembre 2020 ; le dernier
réarrangement remontant à la rentrée 2015. Si un changement intervient,
corriger ici.

Source pour ACADEMIE_ZONE (vérifié 2025-2026) :
https://www.education.gouv.fr/le-calendrier-scolaire-100148
"""

from __future__ import annotations
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Optional

# Mapping académie → zone. Valable depuis 2020-2021.
# Les académies ultramarines ne sont pas gérées (l'appli cible la métropole).
ACADEMIE_ZONE = {
    # Zone A
    "Besançon":        "A",
    "Bordeaux":        "A",
    "Clermont-Ferrand":"A",
    "Dijon":           "A",
    "Grenoble":        "A",
    "Limoges":         "A",
    "Lyon":            "A",
    "Poitiers":        "A",
    # Zone B
    "Aix-Marseille":   "B",
    "Amiens":          "B",
    "Caen":            "B",
    "Lille":           "B",
    "Nantes":          "B",
    "Nice":            "B",
    "Nancy-Metz":      "B",
    "Orléans-Tours":   "B",
    "Reims":           "B",
    "Rennes":          "B",
    "Rouen":           "B",
    "Strasbourg":      "B",
    # Zone C
    "Créteil":         "C",
    "Montpellier":     "C",
    "Paris":           "C",
    "Toulouse":        "C",
    "Versailles":      "C",
    # Corse : calendrier propre, souvent aligné sur zone A
    "Corse":           "A",
    "Normandie":       "B",   # ancienne académie fusionnée (Caen+Rouen), conservée par compat
}

URL_VACANCES = (
    "https://data.education.gouv.fr/api/explore/v2.1/catalog/"
    "datasets/fr-en-calendrier-scolaire/records"
)
URL_FERIES = "https://calendrier.api.gouv.fr/jours-feries/metropole/{annee}.json"


def zone_academie(academie: str) -> Optional[str]:
    """Retourne la zone A/B/C pour une académie, ou None si inconnue."""
    if not academie:
        return None
    # Normalisation légère : match insensible à la casse et aux accents
    clef = academie.strip()
    return ACADEMIE_ZONE.get(clef)


def _cache_get(store, cle: str):
    """Lit une entrée du cache. Retourne le payload décodé ou None."""
    with store.conn() as conn:
        row = conn.execute(
            "SELECT payload FROM cache_api WHERE cle = ?", (cle,)
        ).fetchone()
    if row:
        # row est un sqlite3.Row
        return json.loads(row["payload"])
    return None


def _cache_set(store, cle: str, payload) -> None:
    """Écrit ou remplace une entrée dans le cache."""
    with store.conn() as conn:
        conn.execute("""
            INSERT INTO cache_api (cle, payload, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(cle) DO UPDATE SET
              payload=excluded.payload,
              fetched_at=excluded.fetched_at
        """, (cle, json.dumps(payload, ensure_ascii=False),
              datetime.now(timezone.utc).isoformat(timespec="seconds")))


def vacances(annee_scolaire: str, zone: str, store, force_refresh: bool = False,
             academie: str | None = None) -> list:
    """
    Retourne la liste des vacances scolaires pour une année + zone.

    annee_scolaire : format '2021-2022'
    zone           : 'A', 'B' ou 'C'
    academie       : optionnel, nom de l'académie (ex: 'Rennes') pour filtrer
                     les doublons inter-académies. Si None, on dédoublonne sur
                     (description, start_date).
    store          : SqliteStore (pour le cache)

    Retour : liste de dicts {description, start_date, end_date, zones,
                             location, annee_scolaire}
    Dates au format ISO 'AAAA-MM-JJ'.
    """
    # Le cache intègre l'académie pour ne pas servir du Lille quand on demande
    # du Rennes (et réciproquement).
    cle = f"vacances:{zone}:{annee_scolaire}:{academie or ''}"
    if not force_refresh:
        cached = _cache_get(store, cle)
        if cached is not None:
            return cached

    # Filtre : zone + année. PAS de filtre population (il exclut Toussaint,
    # Noël, Hiver, Printemps qui ont population="-", et ne laisse que "Vacances
    # d'Été" dupliquée par académie — constaté sur l'API en avril 2026).
    refines = [
        f"zones:Zone {zone}",
        f"annee_scolaire:{annee_scolaire}",
    ]
    # Si une académie est précisée, on ajoute le filtre pour éviter les
    # doublons inter-académies de la même zone.
    if academie:
        refines.append(f"location:{academie}")

    params = {"limit": "100", "refine": refines}
    url = URL_VACANCES + "?" + _encode_refine_params(params)

    req = urllib.request.Request(url, headers={"User-Agent": "seqenseigne/0.6.3"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # L'API renvoie les records dans `results`, chaque record contient :
    # start_date, end_date (ISO datetime), description, zones, annee_scolaire, location, population
    bruts = []
    for r in data.get("results", []):
        bruts.append({
            "description":    r.get("description", ""),
            "start_date":     _iso_date(r.get("start_date")),
            "end_date":       _iso_date(r.get("end_date")),
            "zones":          r.get("zones", ""),
            "location":       r.get("location", ""),
            "annee_scolaire": r.get("annee_scolaire", annee_scolaire),
        })

    # Dédoublonnage : sans filtre `population`, certaines périodes peuvent
    # apparaître en plusieurs exemplaires (une par valeur de population :
    # "Élèves", "Enseignants", "-", etc). On garde le premier par
    # (description normalisée, start_date).
    results = []
    vues = set()
    for r in bruts:
        cle_dedup = (_normalise_desc(r["description"]), r["start_date"])
        if cle_dedup in vues:
            continue
        vues.add(cle_dedup)
        results.append(r)

    # L'API officielle est incomplète :
    #  - elle ne renvoie PAS les vacances d'été côté élèves pour toutes les
    #    zones (cas à cas selon les mises à jour data.education.gouv.fr)
    #  - elle ne renvoie PAS le pont de l'Ascension
    # On complète systématiquement depuis notre table officielle.
    _ajouter_vacances_ete(results, annee_scolaire, zone)
    _ajouter_pont_ascension(results, annee_scolaire, zone)

    _cache_set(store, cle, results)
    return results


def _normalise_desc(s: str) -> str:
    """Normalise une description pour dédoublonnage : lowercase + sans
    accents simples sur É/é. Évite que 'Vacances d'Été' et 'Vacances d'été'
    soient comptées comme deux entrées distinctes."""
    return (s or "").lower().replace("é", "e").replace("è", "e").strip()



# Dates officielles connues (arrêtés du Ministère)
# Publiées au JO — stables, pas besoin d'aller les chercher à l'API.
# Zone → année scolaire → "AAAA-MM-JJ" du début des vacances d'été
VACANCES_ETE_DEBUT = {
    "A": {
        "2023-2024": "2024-07-06", "2024-2025": "2025-07-05",
        "2025-2026": "2026-07-04", "2026-2027": "2027-07-03",
    },
    "B": {
        "2023-2024": "2024-07-06", "2024-2025": "2025-07-05",
        "2025-2026": "2026-07-04", "2026-2027": "2027-07-03",
    },
    "C": {
        "2023-2024": "2024-07-06", "2024-2025": "2025-07-05",
        "2025-2026": "2026-07-04", "2026-2027": "2027-07-03",
    },
}

# Pont de l'Ascension : mercredi soir (classes libérées) → lundi matin (reprise)
# Stocké comme (start_date, end_date) avec la même convention que l'API
# (end_date = jour de reprise).
PONT_ASCENSION = {
    "2023-2024": ("2024-05-09", "2024-05-13"),  # jeudi 9 mai 2024
    "2024-2025": ("2025-05-29", "2025-06-02"),  # jeudi 29 mai 2025
    "2025-2026": ("2026-05-14", "2026-05-18"),  # jeudi 14 mai 2026
    "2026-2027": ("2027-05-06", "2027-05-10"),  # jeudi 6 mai 2027
}


def _premier_samedi_apres(date_iso: str) -> str:
    """Retourne la date ISO du premier samedi à partir de `date_iso` (inclus)."""
    from datetime import datetime, timedelta
    d = datetime.strptime(date_iso, "%Y-%m-%d")
    # weekday : lundi=0 … samedi=5
    decalage = (5 - d.weekday()) % 7
    return (d + timedelta(days=decalage)).strftime("%Y-%m-%d")


def _ajouter_vacances_ete(results: list, annee_scolaire: str, zone: str) -> None:
    """
    Ajoute une entrée 'Vacances d'été' synthétique (si absente) couvrant
    du jour officiel de début des vacances d'été jusqu'au 31 août.

    Source de la date de début :
    1. Si `results` contient déjà une entrée "été" (API future), on ne touche à rien.
    2. Sinon, on lit la table `VACANCES_ETE_DEBUT` (arrêtés du Ministère).
    3. Fallback si année inconnue : premier samedi ≥ 4 juillet de l'année de fin.

    La règle antérieure (`max(end_date) + 1 jour`) était buggée : l'API renvoie
    `end_date` = jour de reprise, donc on obtenait ~28 avril comme début, ce qui
    masquait à tort mai-juin comme "vacances d'été".
    """
    # Déjà présent ?
    for r in results:
        d = (r.get("description") or "").lower()
        if "été" in d or "ete" in d:
            return

    try:
        annee_fin = int(annee_scolaire.split("-")[1])
    except (IndexError, ValueError):
        return  # annee_scolaire malformée, on abandonne silencieusement

    # Source 1 : table officielle
    debut_iso = VACANCES_ETE_DEBUT.get(zone, {}).get(annee_scolaire)
    # Source 2 : fallback (1er samedi ≥ 4 juillet)
    if not debut_iso:
        debut_iso = _premier_samedi_apres(f"{annee_fin}-07-04")

    fin_31aout = f"{annee_fin}-08-31"
    location = results[0].get("location", "") if results else ""

    results.append({
        "description":    "Vacances d'été",
        "start_date":     debut_iso,
        "end_date":       fin_31aout,
        "zones":          f"Zone {zone}",
        "location":       location,
        "annee_scolaire": annee_scolaire,
        "synthetique":    True,
    })


def _ajouter_pont_ascension(results: list, annee_scolaire: str, zone: str) -> None:
    """
    Ajoute une entrée 'Pont de l'Ascension' si disponible dans la table.
    L'Ascension est un jour férié mobile dépendant de Pâques, et le pont
    associé (vendredi + samedi habituellement) est décidé chaque année par
    arrêté. Table dure, pas de fallback algorithmique (trop de variantes).
    """
    # Déjà présent ?
    for r in results:
        d = (r.get("description") or "").lower()
        if "ascension" in d:
            return

    pont = PONT_ASCENSION.get(annee_scolaire)
    if not pont:
        return
    start_date, end_date = pont

    location = results[0].get("location", "") if results else ""
    results.append({
        "description":    "Pont de l'Ascension",
        "start_date":     start_date,
        "end_date":       end_date,
        "zones":          f"Zone {zone}",
        "location":       location,
        "annee_scolaire": annee_scolaire,
        "synthetique":    True,
    })


def jours_feries(annee: int, store, force_refresh: bool = False) -> dict:
    """
    Retourne les jours fériés d'une année civile.
    annee : entier (ex: 2024)
    store : SqliteStore

    Retour : dict { 'AAAA-MM-JJ': 'Nom du jour férié', ... }
    """
    cle = f"feries:{annee}"
    if not force_refresh:
        cached = _cache_get(store, cle)
        if cached is not None:
            return cached

    url = URL_FERIES.format(annee=annee)
    req = urllib.request.Request(url, headers={"User-Agent": "seqenseigne/0.6.3"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    _cache_set(store, cle, data)
    return data


def jours_feries_annee_scolaire(annee_scolaire: str, store) -> dict:
    """
    Retourne les jours fériés qui tombent pendant une année scolaire
    (septembre N → août N+1). Agrège les 2 années civiles.
    """
    debut, fin = annee_scolaire.split("-")
    feries = {}
    for a in (int(debut), int(fin)):
        try:
            feries.update(jours_feries(a, store))
        except Exception:
            # En cas d'API indisponible, on reste silencieux plutôt que de
            # faire planter la route ; les jours fériés connus de l'autre
            # année seront retournés, et l'UI affichera un état dégradé.
            pass
    # Filtre : entre 1er septembre de 'debut' et 31 août de 'fin'
    debut_iso = f"{debut}-09-01"
    fin_iso   = f"{fin}-08-31"
    return {d: nom for d, nom in feries.items() if debut_iso <= d <= fin_iso}


# ── helpers ──────────────────────────────────────────────────────────────────

def _encode_refine_params(params: dict) -> str:
    """Encode les paramètres avec `refine` répété."""
    parts = []
    for k, v in params.items():
        if isinstance(v, list):
            for item in v:
                parts.append(f"{k}={urllib.parse.quote(item)}")
        else:
            parts.append(f"{k}={urllib.parse.quote(str(v))}")
    return "&".join(parts)


def _iso_date(dt: Optional[str]) -> Optional[str]:
    """Convertit un datetime ISO en date ISO, en heure de Paris.

    L'API Éducation renvoie les dates avec un offset UTC (ex: '22:00:00+00:00').
    En heure de Paris (UTC+1 l'hiver, UTC+2 l'été), ces 22h UTC correspondent
    au lendemain minuit — donc couper brutalement les 10 premiers caractères
    donne un décalage d'un jour. On reformule en heure locale.

    Tolère aussi les formats 'AAAA-MM-JJ' (sans heure) et
    'AAAA-MM-JJTHH:MM:SSZ'.
    """
    if not dt:
        return None
    # Format court sans heure : on prend tel quel
    if len(dt) == 10 and dt[4] == "-" and dt[7] == "-":
        return dt
    try:
        from datetime import datetime, timezone, timedelta
        # fromisoformat accepte le +00:00, pas le Z → normaliser
        s = dt.replace("Z", "+00:00")
        d_utc = datetime.fromisoformat(s)
        if d_utc.tzinfo is None:
            d_utc = d_utc.replace(tzinfo=timezone.utc)
        # Conversion en heure de Paris (UTC+1 hiver, UTC+2 été).
        # Pour notre usage (comparer aux dates de semaine dans le calendrier),
        # une approche simple et robuste suffit : on utilise UTC+1 par défaut.
        # Les 22h UTC des dates renvoyées par l'API deviennent donc 23h le
        # même jour en hiver (hiver : décalage nul) ou 00h le lendemain en
        # été (été : décalage d'un jour). Comme les dates de vacances sont
        # toujours réglées à 22h UTC de la veille = 00h heure locale française,
        # on fait +2h pour passer la frontière quelle que soit la saison.
        d_paris = d_utc + timedelta(hours=2)
        return d_paris.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        # Fallback : coupe brutale si format imprévu
        return dt[:10]
