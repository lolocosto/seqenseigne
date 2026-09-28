"""
importers/sequencesdb.py — Construction d'une Progression depuis un SequencesDB.

Un répertoire SequencesDB contient :
  cycle4-sequences.csv      — référentiel des 14 séquences
  cycle4-themes.csv         — thèmes
  Sem1-sequences.csv        — séquences avec dates affectées au semestre 1
  Sem2-sequences.csv        — idem semestre 2
  FinAnnee-sequences.csv    — idem fin d'année
  N11S01Objectifs.csv       — objectifs de la séquence S01 pour le niveau N11
  N11S01Connaissances.csv   — connaissances de S01

Format Sem*-sequences.csv :
  Code, Numero, Nom, Theme, Debut, Fin
  (dates au format JJ/MM, sans année — à compléter avec l'année scolaire)

Format N1XSYYObjectifs.csv :
  Code, FinCycle, Nom, MaitriseTB, MaitriseS, MaitriseF
  MaitriseTB → critère niveau 4
  MaitriseS  → critère niveau 3
  MaitriseF  → critère niveau 2

Les codes d'objectifs peuvent être :
  "Objectif 01" ou "01" — normalisé en "01"
"""

from __future__ import annotations
import csv
import re
from pathlib import Path
from services.progression import progression_id, creneau_id
from services.niveaux import rang_creneau


# ── Helpers CSV ────────────────────────────────────────────────────────────────

def _lire_csv(path: Path) -> list[dict]:
    """Lit un CSV UTF-8 avec BOM, retourne une liste de dicts."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _normaliser_code_obj(raw: str) -> str:
    """'Objectif 01', 'objectif 11', '01', '1' → '01' ou '11'."""
    m = re.search(r'\d+', raw.strip())
    return m.group(0).zfill(2) if m else raw.strip()


def _normaliser_code_seq(raw: str) -> str:
    """
    Normalise un code séquence issu des Sem*-sequences.csv.
    Exemples : 'S03A' → 'S03', 'S11B' → 'S11', 'S3' → 'S03', 'S03' → 'S03'.
    La lettre suffixe (A/B/C) identifie la partie mais n'est pas dans le code canonique.
    """
    m = re.match(r'S(\d+)', raw.strip(), re.IGNORECASE)
    if m:
        return f"S{int(m.group(1)):02d}"
    return raw.strip()


def _suffixe_partie(raw: str) -> str | None:
    """
    Extrait le suffixe de partie d'un code séquence, si présent.
    'S03A' → 'A', 'S11B' → 'B', 'S03' → None.
    """
    m = re.match(r'S\d+([A-Za-z]+)$', raw.strip())
    return m.group(1).upper() if m else None


def _date_complete(jj_mm: str, annee: str, mois_pivot: int = 7) -> str | None:
    """
    Convertit 'JJ/MM' en 'AAAA-MM-JJ' en déduisant l'année depuis l'année scolaire.
    annee : '2023-2024'
    mois_pivot : mois à partir duquel on utilise la première année (défaut : juillet)
    """
    if not jj_mm or jj_mm.strip() == "-":
        return None
    try:
        parts = jj_mm.strip().split("/")
        if len(parts) != 2:
            return None
        jj, mm = int(parts[0]), int(parts[1])
        annees = annee.split("-")
        an1, an2 = int(annees[0]), int(annees[1])
        an = an1 if mm >= mois_pivot else an2
        return f"{an:04d}-{mm:02d}-{jj:02d}"
    except (ValueError, IndexError):
        return None


# ── Parseur principal ──────────────────────────────────────────────────────────

def _resoudre_fichier(dossiers: list[Path], noms_candidats: list[str]) -> Path | None:
    """
    Cherche le premier fichier existant parmi une liste de noms candidats,
    dans l'ordre des dossiers fournis, en tolérant la casse (utile pour
    Periodes.CSV / periodes.csv / PERIODES.CSV sur systèmes case-sensitive).
    Retourne le chemin trouvé ou None.
    """
    noms_lower = {n.lower() for n in noms_candidats}
    for dossier in dossiers:
        if not dossier or not dossier.is_dir():
            continue
        # D'abord tentative exacte (plus rapide)
        for nom in noms_candidats:
            p = dossier / nom
            if p.exists():
                return p
        # Puis recherche insensible à la casse
        for entry in dossier.iterdir():
            if entry.is_file() and entry.name.lower() in noms_lower:
                return entry
    return None


def _lire_periodes_csv(chemin_suivi: Path | None, base: Path) -> list[str]:
    """
    Lit le fichier Periodes.CSV (ou variante de casse) et retourne la liste
    ordonnée des périodes qu'il contient. Cherche d'abord dans chemin_suivi,
    puis dans base et son parent.
    Si aucun fichier n'est trouvé, retourne la liste par défaut Sem1/Sem2/FinAnnee.
    """
    dossiers = [chemin_suivi, base, base.parent] if chemin_suivi else [base, base.parent]
    dossiers = [d for d in dossiers if d]
    f = _resoudre_fichier(dossiers, ["Periodes.CSV", "periodes.csv", "PERIODES.CSV"])
    if not f:
        # Fallback legacy
        return ["Sem1", "Sem2", "FinAnnee"]

    rows = _lire_csv(f)
    periodes = []
    for row in rows:
        # Colonne 'Periode' attendue, mais on tolère d'autres casses
        val = None
        for k, v in row.items():
            if k and k.strip().lower() == "periode":
                val = (v or "").strip()
                break
        if val:
            periodes.append(val)
    return periodes or ["Sem1", "Sem2", "FinAnnee"]


def lire_sequencesdb(chemin: str | Path, niveau: str, annee: str,
                     chemin_suivi: str | Path | None = None,
                     etablissement: str = "") -> dict:
    """
    Lit un répertoire SequencesDB et construit une Progression complète.

    chemin        : dossier contenant les N11S*Objectifs.csv et N11S*Connaissances.csv
    niveau        : ex. 'N11'
    annee         : ex. '2023-2024'
    chemin_suivi  : dossier contenant Periodes.CSV et <periode>-sequences.csv.
                    Si None, cherche d'abord dans chemin, puis dans le dossier parent.

    Les périodes sont découvertes dynamiquement depuis Periodes.CSV (pour
    supporter les années en trimestres T1/T2/T3 comme les années en semestres
    Sem1/Sem2/FinAnnee). Si aucun Periodes.CSV n'est trouvé, fallback sur
    Sem1/Sem2/FinAnnee.

    Retourne un dict Progression prêt à être persisté via JsonStore.
    """
    base = Path(chemin)
    chemin_suivi_p = Path(chemin_suivi) if chemin_suivi else None
    erreurs = []

    # Dossiers où chercher les fichiers *-sequences.csv, par priorité
    dossiers_sem = [chemin_suivi_p, base, base.parent]
    dossiers_sem = [d for d in dossiers_sem if d]

    # ── 1. Découvrir les périodes et leurs fichiers-sequences.csv ──────────────
    periodes = _lire_periodes_csv(chemin_suivi_p, base)
    periodes_fichiers = {}
    for p in periodes:
        fpath = _resoudre_fichier(
            dossiers_sem,
            [f"{p}-sequences.csv", f"{p}-Sequences.csv", f"{p}-SEQUENCES.CSV"]
        )
        if fpath:
            periodes_fichiers[p] = fpath
        else:
            erreurs.append(f"Périodes.CSV cite '{p}' mais {p}-sequences.csv introuvable")

    creneaux = []
    periodes_trouvees = []
    ordre = 1

    for periode, fpath in periodes_fichiers.items():
        rows = _lire_csv(fpath)
        if not rows:
            continue
        periodes_trouvees.append(periode)
        for row in rows:
            code_brut = row.get("Code", "").strip()
            if not code_brut:
                continue
            seq_code = _normaliser_code_seq(code_brut)

            # Partie : depuis le suffixe du code (S03A → "A") ou depuis le nom
            suffixe = _suffixe_partie(code_brut)
            nom_raw = row.get("Nom", "").strip()
            partie = None
            m = re.search(r'\(([^)]+partie[^)]*)\)', nom_raw, re.IGNORECASE)
            if m:
                partie = m.group(1).strip()
            elif suffixe:
                # Pas de libellé "partie" dans le nom, mais suffixe explicite
                partie = f"{suffixe}e partie"

            # Objectifs et connaissances depuis les CSV N1XSYYObjectifs.csv
            objectifs, connaissances = _lire_objectifs_connaissances(
                base, niveau, seq_code, erreurs
            )

            # Filtrer les objectifs selon le rang du créneau si multi-créneau
            rang = _rang_creneau_pour_sequence(creneaux, seq_code)
            objectifs_filtres = [
                o for o in objectifs
                if rang_creneau(o["code"]) == rang
            ]

            creneaux.append({
                "id":           creneau_id(),
                "sequence":     seq_code,
                "partie_debut": rang,
                "partie_fin":   rang,
                "partie":       partie,
                "periode":      periode,
                "date_debut":   _date_complete(row.get("Debut", ""), annee),
                "date_fin":     _date_complete(row.get("Fin", ""), annee),
                "revisions":    "",
                "ordre":        ordre,
                "objectifs":    objectifs_filtres,
                "connaissances": connaissances if rang == 1 else [],
            })
            ordre += 1

    # ── 2. Progression finale ──────────────────────────────────────────────────
    progression = {
        "id":            progression_id(niveau, annee, etablissement),
        "niveau":        niveau,
        "annee":         annee,
        "etablissement": etablissement,
        "source":        "sequencesdb",
        "periodes":      periodes_trouvees,
        "creneaux":      creneaux,
        "erreurs":       erreurs,
    }

    return progression


def _rang_creneau_pour_sequence(creneaux_existants: list, seq_code: str) -> int:
    """
    Détermine le partie_debut du prochain créneau pour une séquence.
    1 si pas encore de créneau, max(partie_fin)+1 sinon.
    Accepte les anciennes clés rang_debut / rang_fin pour rétrocompat.
    """
    existants = [c for c in creneaux_existants if c["sequence"] == seq_code]
    if not existants:
        return 1
    def _partie_fin(c):
        return c.get("partie_fin", c.get("rang_fin",
                                         c.get("partie_debut",
                                               c.get("rang_debut", 1))))
    return max(_partie_fin(c) for c in existants) + 1


def _lire_objectifs_connaissances(
    base: Path, niveau: str, seq_code: str, erreurs: list
) -> tuple[list, list]:
    """
    Lit N1XSYYObjectifs.csv et N1XSYYConnaissances.csv.
    Retourne (objectifs, connaissances).
    """
    # Normaliser seq_code : S01, S1, S001 → S01
    m = re.match(r'S(\d+)', seq_code)
    seq_norm = f"S{int(m.group(1)):02d}" if m else seq_code

    obj_path  = base / f"{niveau}{seq_norm}Objectifs.csv"
    conn_path = base / f"{niveau}{seq_norm}Connaissances.csv"

    objectifs = []
    rows_obj = _lire_csv(obj_path)
    for row in rows_obj:
        code_raw = row.get("Code", "").strip()
        if not code_raw:
            continue
        code = _normaliser_code_obj(code_raw)
        objectifs.append({
            "code":      code,
            "nom":       row.get("Nom", "").strip(),
            "fin_cycle": row.get("FinCycle", "N").strip().upper() == "O",
            "criteres": {
                "4": row.get("MaitriseTB", "").strip(),
                "3": row.get("MaitriseS",  "").strip(),
                "2": row.get("MaitriseF",  "").strip(),
            },
        })

    connaissances = []
    for row in _lire_csv(conn_path):
        code = row.get("Code", "").strip()
        nom  = row.get("Nom", "").strip()
        if code and nom:
            connaissances.append({"code": code, "nom": nom})

    return objectifs, connaissances


# ── Import du suivi historique (SXXsuivi.csv) ─────────────────────────────────

def _est_colonne_objectif(k: str) -> bool:
    """
    Retourne True si la colonne k est une colonne d'objectif.
    Accepte : "Objectif 01", "objectif 11", "01", "02", "1", "11", "21".
    Rejette : "Nom", "Prenom", "Numero", "Note", etc.
    """
    k = k.strip()
    # "Objectif XX" avec ou sans espace
    if re.match(r'objectif\s*\d+', k, re.IGNORECASE):
        return True
    # Juste un nombre (entier, potentiellement avec zéro de tête) : "01", "02", "11"
    if re.fullmatch(r'\d+', k):
        n = int(k)
        # On s'assure que c'est un code objectif plausible (1-99)
        # et pas un numéro de ligne ("1", "2"...) — les numéros de ligne
        # sont dans une colonne nommée "Numero", pas numérique brute
        return 1 <= n <= 99
    return False


def lire_suivi_historique(
    chemin_classe: str | Path,
    progression: dict,
    eleves: list[dict],
) -> dict:
    """
    Lit les fichiers SXXsuivi.csv d'un répertoire de classe historique
    et construit le suivi élèves lié à la progression fournie.

    chemin_classe : dossier contenant S01suivi.csv, S02suivi.csv, …
    progression   : dict Progression (doit avoir des créneaux avec objectifs)
    eleves        : liste de dicts {id, nom, prenom} déjà créés

    Retourne un dict suivi :
    {
      "progression_id": "N11-2023-2024-HAUTES_OURMES",
      "eleves": {
        "e01": {
          "cr_abc12345": {        ← id du créneau
            "S01": {
              "01": {"niveau": "3", "source": "csv_historique"},
              "02": {"niveau": "2", "source": "csv_historique"},
            }
          }
        }
      }
    }
    """
    from services.niveaux import migrer_ancien_code

    base = Path(chemin_classe)
    suivi_eleves: dict[str, dict] = {e["id"]: {} for e in eleves}

    # Index élèves par (NOM_UPPER, PRENOM_UPPER) → id
    index_eleves = {
        (e["nom"].upper(), e["prenom"].upper()): e["id"]
        for e in eleves
    }

    # Index créneaux : (sequence, rang) → créneau
    index_creneaux: dict[tuple, dict] = {}
    compteur_seq: dict[str, int] = {}
    for c in progression.get("creneaux", []):
        seq = c["sequence"]
        rang = compteur_seq.get(seq, 0) + 1
        compteur_seq[seq] = rang
        index_creneaux[(seq, rang)] = c

    # Lire chaque S0Xsuivi.csv
    for fpath in sorted(base.glob("S*suivi.csv")):
        m = re.match(r'S(\d+)suivi\.csv', fpath.name, re.IGNORECASE)
        if not m:
            continue
        seq_num = int(m.group(1))
        seq_code = f"S{seq_num:02d}"

        rows = _lire_csv(fpath)
        if not rows:
            continue

        # Colonnes objectifs depuis les en-têtes (ignorer clés None/vides)
        # Accepte : "Objectif 01", "objectif01", "01", "1", "11"
        cols_obj = [
            k for k in rows[0].keys()
            if k and _est_colonne_objectif(k)
        ]

        for row in rows:
            nom    = (row.get("Nom") or "").strip().upper()
            prenom = (row.get("Prenom") or "").strip().upper()
            eid    = index_eleves.get((nom, prenom))
            if not eid:
                continue  # élève non trouvé dans la liste

            for col in cols_obj:
                code_raw  = re.search(r'\d+', col)
                if not code_raw:
                    continue
                code_obj  = code_raw.group(0).zfill(2)
                valeur    = (row.get(col) or "").strip()

                # Migrer le code
                try:
                    niveau_new = migrer_ancien_code(valeur, "csv_historique")
                except ValueError:
                    niveau_new = "NE"

                # Trouver le bon créneau selon le rang de l'objectif
                rang = rang_creneau(code_obj)
                creneau = index_creneaux.get((seq_code, rang))
                if not creneau:
                    # créneau non trouvé dans la progression → on crée une entrée générique
                    creneau_key = f"hors_progression_{seq_code}_rang{rang}"
                else:
                    creneau_key = creneau["id"]

                # Écrire dans la structure suivi
                suivi_eleves.setdefault(eid, {})
                suivi_eleves[eid].setdefault(creneau_key, {})
                suivi_eleves[eid][creneau_key].setdefault(seq_code, {})
                suivi_eleves[eid][creneau_key][seq_code][code_obj] = {
                    "niveau": niveau_new,
                    "source": "csv_historique",
                }

    return {
        "progression_id": progression["id"],
        "eleves": suivi_eleves,
    }


# ── Import complet d'une classe historique ─────────────────────────────────────

def importer_classe_historique(
    chemin_classe: str | Path,
    chemin_sequencesdb: str | Path,
    niveau: str,
    annee: str,
    nom_classe: str,
    etablissement: str,
    store=None,
) -> dict:
    """
    Import complet d'une classe historique depuis ses CSV.

    Si `store` est fourni, un référentiel versionné est construit depuis
    SequencesDB/ puis rattaché à la progression. Si un référentiel équivalent
    (même niveau, mêmes thèmes/séquences/objectifs) existe déjà, il est
    réutilisé plutôt que dupliqué. Les référentiels importés sont verrouillés
    d'office (ils ont servi à évaluer des élèves).

    Retourne un dict avec :
    {
      "progression": {...},  # contient referentiel_id si store fourni
      "classe": {...},
      "eleves": [...],
      "suivi": {...},
      "erreurs": [...],
      "referentiel_id": "..."  # ou None
    }
    """
    base_classe = Path(chemin_classe)
    erreurs = []

    # 1. Lire la liste des élèves
    eleves = _lire_liste_eleves(base_classe / "liste_eleves.csv", erreurs)

    # 2. Construire la progression depuis SequencesDB
    # chemin_classe contient parfois les Sem*-sequences.csv (côte à côte avec les SXXsuivi.csv)
    progression = lire_sequencesdb(chemin_sequencesdb, niveau, annee,
                               chemin_suivi=chemin_classe,
                               etablissement=etablissement)
    erreurs.extend(progression.pop("erreurs", []))

    # 2bis. Construire ou retrouver le référentiel (si store fourni)
    referentiel_id = None
    if store is not None:
        try:
            from importers.referentiel_builder import retrouver_ou_creer_referentiel
            referentiel_id = retrouver_ou_creer_referentiel(
                store, Path(chemin_sequencesdb), niveau, annee
            )
            progression["referentiel_id"] = referentiel_id
        except Exception as e:
            erreurs.append(f"Référentiel non construit : {e}")

    # 3. Lire le suivi historique
    suivi_dir = base_classe / "Suivi"
    if not suivi_dir.exists():
        suivi_dir = base_classe  # les CSV sont directement dans le dossier classe
    suivi = lire_suivi_historique(suivi_dir, progression, eleves)

    # 4. Construire la structure classe
    from persistence.ids import nouveau_id_classe
    classe = {
        "id":            nouveau_id_classe(),
        "nom":           nom_classe,
        "niveau":        niveau,
        "annee":         annee,
        "etablissement": etablissement,
        "eleves":        eleves,
        "progression_id": progression["id"],
        "versions_actives":      {},
        "sequences_verouillees": [],
    }

    return {
        "progression": progression,
        "classe":      classe,
        "eleves":      eleves,
        "suivi":       suivi,
        "erreurs":     erreurs,
        "referentiel_id": referentiel_id,
    }


def _lire_liste_eleves(path: Path, erreurs: list) -> list[dict]:
    """
    Lit liste_eleves.csv (format Pronote) et retourne une liste {id, nom, prenom}.

    Les eid sont générés en UUID court ('e_xxxxxxxx') pour garantir l'unicité
    à l'échelle de la base — sinon collision sur la table globale `eleves`
    de SqliteStore lors de l'import d'une seconde classe.
    """
    from services.classes import generer_id_eleve

    rows = _lire_csv(path)
    if not rows:
        erreurs.append(f"liste_eleves.csv introuvable ou vide : {path}")
        return []

    cols = {k.strip().lower(): k for k in rows[0].keys() if k}
    col_nom    = cols.get("nom")
    col_prenom = cols.get("prenom") or cols.get("prénom")
    if not col_nom or not col_prenom:
        erreurs.append(f"Colonnes Nom/Prenom introuvables dans {path.name}")
        return []

    eleves = []
    vus = set()
    for row in rows:
        nom    = row.get(col_nom, "").strip().upper()
        prenom = row.get(col_prenom, "").strip()
        if not nom or not prenom:
            continue
        cle = (nom, prenom.upper())
        if cle in vus:
            continue
        vus.add(cle)
        eleves.append({"id": generer_id_eleve(), "nom": nom, "prenom": prenom})

    eleves.sort(key=lambda e: (e["nom"], e["prenom"]))
    return eleves


def suivi_historique_vers_niveaux(suivi_historique: dict) -> dict:
    """
    Convertit la structure suivi_historique au format niveaux.json
    attendu par le front-end et l'API /api/niveaux.

    Entrée  : { progression_id, eleves: { eid: { cr_id: { seq: { obj: {niveau, source} } } } } }
    Sortie  : { seq: { eid: { obj: niveau_code } } }

    La structure niveaux.json est plate (pas de créneau) : tous les objectifs
    de toutes les séquences sont regroupés par séquence puis par élève.
    """
    niveaux: dict = {}
    for eid, creneaux in suivi_historique.get("eleves", {}).items():
        for cr_id, seqs in creneaux.items():
            for seq_code, objectifs in seqs.items():
                niveaux.setdefault(seq_code, {}).setdefault(eid, {})
                for obj_code, data in objectifs.items():
                    niveau = data["niveau"] if isinstance(data, dict) else data
                    niveaux[seq_code][eid][obj_code] = niveau
    return niveaux
