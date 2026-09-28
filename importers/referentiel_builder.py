"""
importers/referentiel_builder.py — Construction d'un référentiel versionné
depuis un dossier SequencesDB de classe historique.

Un référentiel fige la structure pédagogique d'un niveau :
- thèmes (depuis cycle4-themes.csv)
- séquences (depuis cycle4-sequences.csv)
- objectifs (depuis les N1XS??Objectifs.csv de chaque séquence)

Le script d'import utilise ce module pour :
1. Construire la structure du référentiel qu'utilisait la classe.
2. Chercher un référentiel équivalent déjà en base (clé canonique normalisée).
3. Sinon, créer un nouveau référentiel et le verrouiller immédiatement.

Format attendu des CSV (lu via _lire_csv tolérant BOM UTF-8) :
  cycle4-themes.csv    : Code, Nom, CodeCouleur, [Description]
  cycle4-sequences.csv : Code, Numero, Nom, Theme
  N1XSYYObjectifs.csv  : Code, FinCycle, Nom, MaitriseTB, MaitriseS, MaitriseF
"""

from __future__ import annotations
import re
from pathlib import Path


def _lire_csv(path: Path) -> list[dict]:
    """Délègue au helper de sequencesdb pour rester cohérent (UTF-8 avec BOM)."""
    from importers.sequencesdb import _lire_csv as _lire
    return _lire(path)


def _trouver_cycle_file(sequencesdb: Path, prefixes: list[str]) -> Path | None:
    """
    Trouve un fichier cycleN-<suffixe>.csv dans sequencesdb/, avec tolérance
    de casse. prefixes est une liste de préfixes possibles (ex: ['sequences',
    'themes']). Cherche cycle4-, cycle3-, etc.
    """
    # Exemple : on cherche cycle4-themes.csv, cycle4-Themes.csv, cycle3-themes.csv…
    for entry in sequencesdb.iterdir():
        if not entry.is_file():
            continue
        name_lower = entry.name.lower()
        m = re.match(r"cycle\d+-(\w+)\.csv$", name_lower)
        if m and m.group(1) in prefixes:
            return entry
    return None


def construire_referentiel(
    sequencesdb: Path,
    niveau: str,
    version: str,
    description: str = "",
) -> dict:
    """
    Construit un référentiel complet depuis le dossier SequencesDB/.

    version : identifiant de version (ex: '2021-2022', '2024-2025').
              L'id du référentiel sera '{niveau}_v{version}'.

    Retourne un dict prêt pour SqliteStore.creer_referentiel :
      { id, niveau, version, description, verrouille: True,
        themes: [...], sequences: [{code, numero, nom, theme_code, objectifs: [...]}] }

    Ne crée pas encore le référentiel en base — c'est l'appelant qui décide
    (retrouver_ou_creer_referentiel ci-dessous le fait).
    """
    sequencesdb = Path(sequencesdb)
    if not sequencesdb.is_dir():
        raise FileNotFoundError(f"SequencesDB introuvable : {sequencesdb}")

    # ── Thèmes ────────────────────────────────────────────────────────────────
    themes_file = _trouver_cycle_file(sequencesdb, ["themes"])
    themes = []
    if themes_file:
        for row in _lire_csv(themes_file):
            code = (row.get("Code") or "").strip()
            nom  = (row.get("Nom") or "").strip()
            if not code or not nom:
                continue
            themes.append({
                "code":    code,
                "nom":     nom,
                "couleur": (row.get("CodeCouleur") or "").strip(),
            })

    # ── Séquences (entête) ────────────────────────────────────────────────────
    seqs_file = _trouver_cycle_file(sequencesdb, ["sequences"])
    sequences_entete = []
    if seqs_file:
        for row in _lire_csv(seqs_file):
            code = (row.get("Code") or "").strip()
            nom  = (row.get("Nom") or "").strip()
            if not code or not nom:
                continue
            try:
                numero = int((row.get("Numero") or "").strip())
            except ValueError:
                numero = 0
            sequences_entete.append({
                "code":       code,
                "numero":     numero,
                "nom":        nom,
                "theme_code": (row.get("Theme") or "").strip() or None,
            })

    # ── Objectifs par séquence ────────────────────────────────────────────────
    # Pour chaque séquence listée, on cherche N{niveau}S{code}Objectifs.csv.
    # Si pas trouvé (ex: séquence déclarée mais pas encore de fichier objectifs),
    # on laisse la liste vide — la séquence existe, mais sans objectifs.
    for seq in sequences_entete:
        objectifs = _lire_objectifs_sequence(sequencesdb, niveau, seq["code"])
        seq["objectifs"] = objectifs

    # ── Référentiel complet ───────────────────────────────────────────────────
    # État 'verrouille' d'office : ces référentiels proviennent d'imports
    # historiques, donc ils ont servi à évaluer des élèves et ne sont pas
    # modifiables. Si l'utilisateur a besoin de les retoucher, la roadmap
    # prévoit un déverrouillage manuel (après export/suppression des
    # évaluations) via l'écran d'administration des référentiels.
    ref_id = f"{niveau}_v{version}"
    return {
        "id":           ref_id,
        "niveau":       niveau,
        "version":      version,
        "description":  description,
        "etat":         "verrouille",
        "themes":       themes,
        "sequences":    sequences_entete,
    }


def _lire_objectifs_sequence(sequencesdb: Path, niveau: str, seq_code: str) -> list[dict]:
    """
    Lit le fichier N{niveau}S{YY}Objectifs.csv pour une séquence donnée
    et retourne la liste des objectifs au format référentiel.
    """
    # Normalisation du seq_code : S01, S1, S001 → S01
    m = re.match(r"S(\d+)", seq_code)
    seq_norm = f"S{int(m.group(1)):02d}" if m else seq_code

    # Tolérance de casse sur le nom de fichier
    cible_lower = f"{niveau}{seq_norm}objectifs.csv".lower()
    obj_path = None
    for entry in sequencesdb.iterdir():
        if entry.is_file() and entry.name.lower() == cible_lower:
            obj_path = entry
            break
    if not obj_path:
        return []

    objectifs = []
    for row in _lire_csv(obj_path):
        code_raw = (row.get("Code") or "").strip()
        if not code_raw:
            continue
        # "Objectif 01", "01", "1" → "01"
        code_match = re.search(r"\d+", code_raw)
        if not code_match:
            continue
        code = code_match.group(0).zfill(2)

        nom = (row.get("Nom") or "").strip()
        fin_cycle = (row.get("FinCycle") or "").strip().upper() == "O"

        objectifs.append({
            "code":      code,
            "nom":       nom,
            "fin_cycle": fin_cycle,
            # Les critères : MaitriseF → critere_f, MaitriseS → critere_a, MaitriseTB → critere_e
            # Convention du projet : F = fondamental (niveau minimal), A = avancé, E = excellent
            "critere_f": (row.get("MaitriseF")  or "").strip(),
            "critere_a": (row.get("MaitriseS")  or "").strip(),
            "critere_e": (row.get("MaitriseTB") or "").strip(),
        })
    return objectifs


def _annee_civile_rentree(annee_scolaire: str) -> str:
    """
    Extrait l'année civile de rentrée depuis une chaîne d'année scolaire.

      '2024-2025' → '2024'
      '2021-2022' → '2021'
      '2024'      → '2024'  (déjà au format attendu)

    Cette forme compacte sert d'identifiant de version du référentiel ;
    un référentiel mis en place à la rentrée 2024 s'appelle 'N11_v2024'
    qu'il ait servi une ou plusieurs années scolaires.
    """
    a = (annee_scolaire or "").strip()
    # Prendre ce qui est avant le tiret ou l'espace, ou tout si pas de séparateur
    m = re.match(r"(\d{4})", a)
    return m.group(1) if m else a


def retrouver_ou_creer_referentiel(
    store,
    sequencesdb: Path,
    niveau: str,
    annee: str,
) -> str:
    """
    Stratégie principale appelée par l'importeur :

    1. Construit le référentiel théorique depuis le SequencesDB de la classe.
    2. Cherche un référentiel équivalent en base (même niveau, même contenu
       normalisé). Si trouvé → retourne son id, rien d'autre à faire.
    3. Sinon, crée le référentiel en base avec l'année civile de rentrée
       comme version (ex: 'N11_v2024' pour 2024-2025), le verrouille, et
       retourne son id.

    Gère les collisions d'id (un autre référentiel mis en place la même
    année scolaire, contenu différent) en suffixant : 'N11_v2024b', 'c', …
    """
    version_rentree = _annee_civile_rentree(annee)
    referentiel = construire_referentiel(
        sequencesdb=sequencesdb,
        niveau=niveau,
        version=version_rentree,
        description=f"Mis en place à la rentrée {version_rentree}",
    )

    # Détection d'équivalent existant
    existant_id = store.trouver_referentiel_equivalent(
        niveau=niveau,
        themes=referentiel["themes"],
        sequences=referentiel["sequences"],
    )
    if existant_id:
        return existant_id

    # Création ; gestion des collisions d'id par suffixe b, c, d…
    base_id = referentiel["id"]
    suffixes = [""] + list("bcdefghijklmnopqrstuvwxyz")
    for suffixe in suffixes:
        candidate_id = base_id + suffixe
        referentiel["id"] = candidate_id
        referentiel["version"] = f"{version_rentree}{suffixe}" if suffixe \
                                 else version_rentree
        try:
            store.creer_referentiel(referentiel)
            return candidate_id
        except Exception as e:
            # UNIQUE constraint : id déjà pris → essayer le suffixe suivant
            msg = str(e).lower()
            if "unique" in msg or "primary key" in msg:
                continue
            raise
    raise RuntimeError(
        f"Impossible de créer un référentiel pour {niveau} {annee} : "
        f"tous les suffixes sont pris."
    )
