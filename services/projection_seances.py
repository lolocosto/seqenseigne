"""services/projection_seances.py — v0.19.1.18

Projection de l'emploi du temps d'une classe en un planning de séances datées
sur l'année scolaire, en tenant compte des vacances, des jours fériés et de la
convention d'alternance A/B.

Fonction pure et testable (pas d'accès réseau ni base) : elle reçoit les
vacances et fériés déjà récupérés. L'orchestration (récupération via
`calendrier_scolaire`) est faite dans la route.

Conventions (cf. doc/cadrage_mises_en_route_automatismes.md) :
  - Bornes de l'année scolaire "YYYY-YYYY" : 1er août YYYY → 31 juillet YYYY+1
    (en France la rentrée est toujours en septembre ; le 1er août est une borne
    neutre entre deux années scolaires).
  - La semaine de rentrée (1re semaine calendaire avec des jours de cours) n'est
    PAS comptée (administratif).
  - La 1re semaine comptée (= 2e semaine) est étiquetée B, puis A, B, A…
  - Une semaine ENTIÈREMENT en vacances est sautée : l'alternance A/B ne
    progresse pas (pas d'étiquette consommée).
  - Une semaine partiellement en vacances compte normalement ; seuls les jours
    fériés / en vacances individuels sont sautés.
  - Le numéro de séance est continu sur l'année, par classe (rang de la séance
    dans l'année), pour permettre la cadence Leitner ultérieure.
"""

from __future__ import annotations
from datetime import date, timedelta

JOURS = ("lun", "mar", "mer", "jeu", "ven", "sam", "dim")
_JOUR_INDEX = {j: i for i, j in enumerate(JOURS)}


def bornes_annee(annee_scolaire: str) -> tuple[date, date]:
    """Retourne (debut, fin) = (1er août YYYY, 31 juillet YYYY+1)."""
    d = int(annee_scolaire.split("-")[0])
    return date(d, 8, 1), date(d + 1, 7, 31)


def _lundi_de(d: date) -> date:
    """Lundi de la semaine contenant d."""
    return d - timedelta(days=d.weekday())


def _iso(d: date) -> str:
    return d.isoformat()


def _en_vacances(jour: date, periodes_vacances: list) -> bool:
    """Vrai si `jour` tombe dans une période de vacances.

    Chaque période est un dict {start_date, end_date} en ISO. Convention des
    données education.gouv : start_date = premier jour de vacances (soir du
    dernier jour de cours enregistré comme début), end_date = jour de reprise.
    On considère [start_date, end_date) : le jour de reprise est un jour de
    cours, pas de vacances.
    """
    iso = _iso(jour)
    for p in periodes_vacances:
        deb = p.get("start_date") or ""
        fin = p.get("end_date") or ""
        if deb and fin and deb <= iso < fin:
            return True
        # période dégénérée (un seul jour) : start seul
        if deb and not fin and iso == deb:
            return True
    return False


def _semaine_sans_cours(lundi: date, jours_ouvres: list[int],
                        periodes_vacances: list, feries: dict,
                        debut: date, fin: date) -> bool:
    """Vrai si aucun jour ouvré de la semaine n'est un jour de cours effectif :
    tous sont hors de l'année scolaire, en vacances, ou fériés."""
    for offset in jours_ouvres:
        j = lundi + timedelta(days=offset)
        if not (debut <= j <= fin):
            continue  # hors année → pas un jour de cours
        if _en_vacances(j, periodes_vacances):
            continue
        if _iso(j) in feries:
            continue
        return False  # au moins un jour de cours effectif
    return True


def projeter(annee_scolaire: str, edt_classe: list, grille: list,
             vacances: list, feries: dict,
             date_min: str | None = None,
             indisponibilites: list | None = None,
             classe_id: str | None = None) -> list:
    """Projette les séances datées d'une classe sur l'année scolaire.

    Paramètres
    ----------
    annee_scolaire : "YYYY-YYYY"
    edt_classe     : cases EDT de la classe DÉJÀ filtrées sur les usages
                     comptés (chaque dict : jour, creneau_code, semaine).
    grille         : créneaux de la grille horaire de l'établissement
                     (chaque dict : code, heure_debut, heure_fin, ordre).
    vacances       : liste de périodes {start_date, end_date} (ISO).
    feries         : dict {date_iso: nom}.
    date_min       : borne basse ISO optionnelle (ex. "2025-09-01"). Aucune
                     séance n'est projetée avant cette date. Sert de filet de
                     sécurité quand les vacances d'été officielles sont absentes
                     (en France la rentrée est toujours en septembre).
    indisponibilites : liste d'indisponibilités (dicts). Les séances couvertes
                     sont retirées AVANT numérotation, ce qui décale la suite.
    classe_id      : classe projetée (pour la portée 'classes' des indispos).

    Retour : liste ordonnée de séances datées :
      {numero, date, jour, creneau_code, heure_debut, heure_fin,
       semaine_label}
    """
    debut, fin = bornes_annee(annee_scolaire)
    if date_min:
        try:
            dm = date.fromisoformat(date_min)
            if dm > debut:
                debut = dm
        except ValueError:
            pass
    horaires = {g["code"]: g for g in grille}

    # Cases EDT groupées par jour, avec leur applicabilité de semaine.
    # Chaque case : (jour, creneau_code, semaine ∈ {A,B,AB}).
    cases = []
    for c in edt_classe:
        jour = (c.get("jour") or "").lower()
        if jour not in _JOUR_INDEX:
            continue
        cases.append({
            "edt_creneau_id": c.get("id"),
            "jour": jour,
            "creneau_code": c.get("creneau_code", ""),
            "semaine": c.get("semaine", "AB"),
        })
    # Jours ouvrés = offsets des jours où la classe a au moins une case.
    jours_ouvres = sorted({_JOUR_INDEX[c["jour"]] for c in cases})

    seances = []
    label = None            # None tant que la 1re semaine comptée n'a pas eu lieu
    premiere_comptee_passee = False
    semaine_rentree_ignoree = False

    lundi = _lundi_de(debut)
    # On borne le parcours à la fin de l'année scolaire.
    while lundi <= fin:
        # Semaine sans aucun jour de cours effectif (hors année, vacances ou
        # fériés) → sautée : ni rentrée, ni alternance A/B ne progressent.
        if _semaine_sans_cours(lundi, jours_ouvres, vacances, feries,
                               debut, fin):
            lundi += timedelta(days=7)
            continue

        # Première semaine « travaillée » = rentrée, ignorée (une seule fois).
        if not semaine_rentree_ignoree:
            semaine_rentree_ignoree = True
            lundi += timedelta(days=7)
            continue

        # À partir d'ici, semaine comptée. Étiquette : B en premier, puis A/B…
        if not premiere_comptee_passee:
            label = "B"
            premiere_comptee_passee = True
        else:
            label = "A" if label == "B" else "B"

        # Cases applicables cette semaine (semaine == label ou 'AB').
        applicables = [c for c in cases
                       if c["semaine"] == label or c["semaine"] == "AB"]
        # Tri par jour puis par ordre du créneau dans la grille.
        def _cle(c):
            g = horaires.get(c["creneau_code"], {})
            return (_JOUR_INDEX[c["jour"]], g.get("ordre", 999),
                    c["creneau_code"])
        applicables.sort(key=_cle)

        for c in applicables:
            j = lundi + timedelta(days=_JOUR_INDEX[c["jour"]])
            if not (debut <= j <= fin):
                continue
            if _en_vacances(j, vacances) or _iso(j) in feries:
                continue
            g = horaires.get(c["creneau_code"], {})
            seances.append({
                "date": _iso(j),
                "jour": c["jour"],
                "creneau_code": c["creneau_code"],
                "edt_creneau_id": c.get("edt_creneau_id"),
                "heure_debut": g.get("heure_debut", ""),
                "heure_fin": g.get("heure_fin", ""),
                "semaine_label": label,
            })

        lundi += timedelta(days=7)

    # Retirer les séances couvertes par une indisponibilité (AVANT
    # numérotation, pour que le décalage soit intrinsèque).
    if indisponibilites:
        from services import indisponibilites as _ind
        seances = _ind.filtrer_seances(seances, indisponibilites,
                                       classe_id, grille)

    # Numérotation continue finale.
    for i, s in enumerate(seances, start=1):
        s["numero"] = i
    return seances
