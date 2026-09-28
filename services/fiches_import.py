"""services/fiches_import.py — v0.11.1.x (bascule de syntaxe v0.11.1)

Import des fiches de résumé depuis les fichiers `.tex` du cycle complet
(format « Flashcards année complète » post-normalisation du paquet).

Format source attendu (depuis v0.11.1 — préfixe `seq` partout) :

    \\seqSetCodeSequence{S01}
    \\seqBoiteTitreFlashcard{Objectif 02}{}
    \\begin{seqBoiteContenuFlashcard}[titre=Définition]
        Un nombre décimal est ...
    \\end{seqBoiteContenuFlashcard}
    \\begin{seqBoiteContenuFlashcard}[titre=Méthode]
        Pour passer de ...
    \\end{seqBoiteContenuFlashcard}
    \\begin{seqBoiteFillContenuFlashcard}\\end{seqBoiteFillContenuFlashcard}
    \\seqBoiteTitreFlashcard{Objectif 03}{}
    ...

Note v0.11.1 — bascule franche depuis l'ancienne syntaxe :
  - `\\seqSetSequence`           → `\\seqSetCodeSequence`
  - `\\boiteTitreFlashcard`       → `\\seqBoiteTitreFlashcard`
  - `boiteContenuFlashcard` (env) → `seqBoiteContenuFlashcard`
  - `boiteFillContenuFlashcard`   → `seqBoiteFillContenuFlashcard`

Les anciens noms NE SONT PLUS reconnus. Les fichiers `.tex` legacy
doivent être régénérés (ou édités via un sed) avant import.

Le titre peut prendre 2 formes :
  - `\\seqBoiteTitreFlashcard{Objectif 02}{...}` (5e historique, 3e)
  - `\\seqBoiteTitreFlashcard{02}{...}` (4e adapté)

Convention :
  - Le numéro 2 chiffres = code de l'objectif (objectifs.code)
  - Plusieurs occurrences du même objectif = fiches multiples qu'on
    FUSIONNE en une seule fiche avec toutes les zones concaténées
    (cohérent avec la spec Q3-1 « 1 fiche = 1 méthode = 1 objectif »).

Idempotence (Q7-c) :
  - Si une fiche existe déjà pour (niveau, sequence, code_obj), on
    AJOUTE les nouvelles zones SANS toucher aux zones existantes.
  - Si la fiche n'existe pas, on la crée avec les zones extraites.

Si l'objectif `objectifs` (niveau, sequence, code) n'existe pas en
BDD (Q7-d) → fiche IGNORÉE et erreur loggée dans le rapport.
"""

from __future__ import annotations
import re
import uuid
from dataclasses import dataclass, field


# Niveau dérivé du nom de fichier (Q7-a)
NIVEAU_DEPUIS_GRADE = {
    "6e":  "N09",
    "5e":  "N10",
    "4e":  "N11",
    "3e":  "N12",
}


# ── Erreurs et structures ────────────────────────────────────────────────────


class FichesImportErreur(Exception):
    def __init__(self, message: str, code: str, **details):
        super().__init__(message)
        self.code = code
        self.details = details


@dataclass
class ZoneExtraite:
    """Une zone (= une seqBoiteContenuFlashcard) extraite du source."""
    titre: str        # ex: 'Définition', 'Propriété', 'Méthode'
    corps: str        # contenu LaTeX brut (entre \begin et \end)


@dataclass
class FicheExtraite:
    """Une fiche logique (regroupement de zones pour un objectif)."""
    niveau: str       # 'N10' etc.
    sequence: str     # 'S01' etc.
    code_objectif: str  # '02', '11' etc.
    zones: list[ZoneExtraite] = field(default_factory=list)


@dataclass
class RapportImport:
    """Résultat d'un import : ce qui a été créé, ajouté, ignoré."""
    fiches_creees: int = 0
    fiches_etendues: int = 0  # fiche existante, zones ajoutées
    zones_ajoutees: int = 0
    objectifs_introuvables: list[str] = field(default_factory=list)  # codes
    erreurs: list[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "fiches_creees":          self.fiches_creees,
            "fiches_etendues":        self.fiches_etendues,
            "zones_ajoutees":         self.zones_ajoutees,
            "objectifs_introuvables": self.objectifs_introuvables,
            "erreurs":                self.erreurs,
        }


# ── Parser ──────────────────────────────────────────────────────────────────


# Regex pour les blocs structurels (compilées au module)
# v0.11.1 — bascule sur la syntaxe `seq*` post-normalisation du paquet.
_RE_SEQ = re.compile(r"\\seqSetCodeSequence\s*\{\s*(S\d{2})\s*\}")
# Titre de fiche : capture le code objectif (avec ou sans préfixe "Objectif ")
_RE_TITRE_FICHE = re.compile(
    r"\\seqBoiteTitreFlashcard\s*\{\s*(?:Objectif\s+)?(\d{2})\s*\}"
)
_RE_DEBUT_BOX = re.compile(
    r"\\begin\{seqBoiteContenuFlashcard\}\s*(?:\[titre\s*=\s*([^\]]*?)\])?",
)
_RE_FIN_BOX = re.compile(r"\\end\{seqBoiteContenuFlashcard\}")
_RE_DEBUT_FILL = re.compile(r"\\begin\{seqBoiteFillContenuFlashcard\}")
_RE_FIN_FILL = re.compile(r"\\end\{seqBoiteFillContenuFlashcard\}")


def parser_tex(contenu: str, niveau: str) -> list[FicheExtraite]:
    """Parse un fichier `.tex` flashcards et retourne la liste des fiches.

    Convention du format source (v0.11.1 — syntaxe seq* post-normalisation) :
      - `\\seqSetCodeSequence{S0X}` pose la séquence courante.
      - Les `\\seqBoiteTitreFlashcard{Objectif XX}{...}` consécutifs au
        même endroit annoncent une SUITE de flashcards à venir (en file
        FIFO).
      - Chaque "section de flashcard" est une suite de
        `\\begin{seqBoiteContenuFlashcard}[titre=...]…\\end{...}` terminée
        par `\\begin{seqBoiteFillContenuFlashcard}…
        \\end{seqBoiteFillContenuFlashcard}`.
      - Au début de chaque section, on dépile le 1er titre de la file ;
        les zones de la section appartiennent à cet objectif.

    Plusieurs flashcards pour le même objectif (cas « 1ère fiche / 2ème
    fiche ») sont fusionnées dans une seule FicheExtraite (concat des
    zones).
    """
    pos = 0
    n = len(contenu)
    sequence_courante: str | None = None
    # File des titres (codes obj) annoncés par \seqBoiteTitreFlashcard et
    # pas encore consommés par une section.
    file_titres: list[str] = []
    # Objectif de la section EN COURS (si on est entre 1er
    # seqBoiteContenuFlashcard et le seqBoiteFillContenuFlashcard). Sinon
    # None.
    objectif_section: str | None = None
    # Map (niveau, sequence, code_obj) → FicheExtraite (mutée en place)
    fiches: dict[tuple[str, str, str], FicheExtraite] = {}

    def _zone_courante(zone: ZoneExtraite):
        if not sequence_courante or not objectif_section:
            return
        cle = (niveau, sequence_courante, objectif_section)
        fiche = fiches.get(cle)
        if fiche is None:
            fiche = FicheExtraite(
                niveau=niveau,
                sequence=sequence_courante,
                code_objectif=objectif_section,
            )
            fiches[cle] = fiche
        fiche.zones.append(zone)

    while pos < n:
        # Trouver le prochain motif d'intérêt :
        # - \seqSetCodeSequence
        # - \seqBoiteTitreFlashcard
        # - \begin{seqBoiteContenuFlashcard}
        # - \begin{seqBoiteFillContenuFlashcard}  (= fin de section)
        m_seq = _RE_SEQ.search(contenu, pos)
        m_titre = _RE_TITRE_FICHE.search(contenu, pos)
        m_debut = _RE_DEBUT_BOX.search(contenu, pos)
        m_fill = _RE_DEBUT_FILL.search(contenu, pos)
        candidats = [
            (m_seq, "seq"), (m_titre, "titre"),
            (m_debut, "debut"), (m_fill, "fill"),
        ]
        candidats = [(m, t) for (m, t) in candidats if m is not None]
        if not candidats:
            break
        candidats.sort(key=lambda x: x[0].start())
        m, type_ = candidats[0]

        if type_ == "seq":
            sequence_courante = m.group(1)
            file_titres.clear()
            objectif_section = None
            pos = m.end()
            continue

        if type_ == "titre":
            file_titres.append(m.group(1).zfill(2))
            pos = m.end()
            continue

        if type_ == "debut":
            # Début d'une section : si pas de section en cours, dépiler
            # le 1er titre de la file pour devenir l'objectif de cette
            # section.
            if objectif_section is None and file_titres:
                objectif_section = file_titres.pop(0)
            # Lire le titre de la zone (groupe 1, peut être None)
            titre_zone = (m.group(1) or "").strip()
            apres_debut = m.end()
            m_fin = _RE_FIN_BOX.search(contenu, apres_debut)
            if not m_fin:
                pos = apres_debut
                continue
            corps = contenu[apres_debut:m_fin.start()].strip()
            pos = m_fin.end()
            _zone_courante(ZoneExtraite(titre=titre_zone, corps=corps))
            continue

        if type_ == "fill":
            # Fin de section : on n'est plus dans la section en cours.
            # La prochaine `seqBoiteContenuFlashcard` consommera le
            # prochain titre de la file.
            objectif_section = None
            # Avancer après le \end{seqBoiteFillContenuFlashcard} pour
            # ne pas re-trigger le motif. _RE_FIN_FILL ne matche que sur
            # le \end (pas le \begin), donc on cherche la fin
            # explicitement.
            m_fin_fill = _RE_FIN_FILL.search(contenu, m.end())
            pos = m_fin_fill.end() if m_fin_fill else m.end()
            continue

    return sorted(
        fiches.values(),
        key=lambda f: (f.sequence, f.code_objectif),
    )


# ── Import en BDD ───────────────────────────────────────────────────────────


def _rowid():
    return uuid.uuid4().hex


def _trouver_objectif_v2(conn, niveau: str, sequence: str, code_obj: str):
    """Cherche l'objectif_v2.id qui correspond à (niveau, sequence, code_obj).

    Retourne la ligne {id, partie_id} ou None.
    """
    return conn.execute(
        """
        SELECT o.id, o.partie_id
        FROM objectifs o
        JOIN sequence_parties p ON p.id = o.partie_id
        JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id
        WHERE sn.niveau = ? AND sn.sequence_code = ? AND o.code = ?
        """,
        (niveau, sequence, code_obj),
    ).fetchone()


def _trouver_fiche_existante(conn, objectif_id: str):
    """Cherche une fiche existante pour cet objectif. Retourne la ligne
    fiches_resume ou None."""
    return conn.execute(
        "SELECT id, num_fiche FROM fiches_resume WHERE objectif_id = ?",
        (objectif_id,),
    ).fetchone()


def _max_num_fiche(conn, niveau: str, sequence: str) -> int:
    r = conn.execute(
        "SELECT MAX(num_fiche) AS m FROM fiches_resume "
        "WHERE niveau = ? AND sequence = ?",
        (niveau, sequence),
    ).fetchone()
    return (r["m"] or 0) if r else 0


def _max_ordre_section(conn, fiche_id: str) -> int:
    r = conn.execute(
        "SELECT MAX(ordre) AS m FROM atome_sections "
        "WHERE entite_type = 'fiche_resume' AND entite_id = ?",
        (fiche_id,),
    ).fetchone()
    m = r["m"] if r and r["m"] is not None else -1
    return m


def importer_fiches(
    conn, *,
    contenu_tex: str,
    niveau: str,
) -> RapportImport:
    """Importe toutes les fiches extraites du contenu `.tex` en BDD.

    Comportement (Q7-c) : pour chaque fiche extraite,
      - si pas de fiche en BDD pour (niveau, sequence, code_obj) → créer
      - sinon → ajouter les zones extraites à la fin (sans toucher
        aux zones existantes)

    Si l'objectif n'existe pas (Q7-d) → ignorer + log.

    Le rapport retourné détaille fiches créées / étendues / objectifs
    introuvables.
    """
    rapport = RapportImport()
    fiches_extraites = parser_tex(contenu_tex, niveau)

    for fe in fiches_extraites:
        # Trouver l'objectif_v2
        obj = _trouver_objectif_v2(
            conn, fe.niveau, fe.sequence, fe.code_objectif,
        )
        if obj is None:
            cle = f"{fe.niveau}/{fe.sequence}/{fe.code_objectif}"
            rapport.objectifs_introuvables.append(cle)
            rapport.erreurs.append(
                f"Objectif introuvable : {cle} — fiche ignorée."
            )
            continue

        # Existe-t-il déjà une fiche pour cet objectif ?
        fiche_existante = _trouver_fiche_existante(conn, obj["id"])
        if fiche_existante is None:
            # Création
            fiche_id = _rowid()
            num = _max_num_fiche(conn, fe.niveau, fe.sequence) + 1
            conn.execute(
                "INSERT INTO fiches_resume "
                "(id, titre, objectif_id, num_fiche, niveau, sequence, etat_code) "
                "VALUES (?, '', ?, ?, ?, ?, 'en_cours')",
                (fiche_id, obj["id"], num, fe.niveau, fe.sequence),
            )
            ordre_base = 0
            rapport.fiches_creees += 1
        else:
            fiche_id = fiche_existante["id"]
            ordre_base = _max_ordre_section(conn, fiche_id) + 1
            rapport.fiches_etendues += 1

        # Ajouter les zones
        for i, zone in enumerate(fe.zones):
            section_id = _rowid()
            conn.execute(
                "INSERT INTO atome_sections "
                "(id, entite_type, entite_id, titre, ordre) "
                "VALUES (?, 'fiche_resume', ?, ?, ?)",
                (section_id, fiche_id, zone.titre, ordre_base + i),
            )
            conn.execute(
                "INSERT INTO atome_section_items "
                "(id, section_id, ordre, corps) VALUES (?, ?, 0, ?)",
                (_rowid(), section_id, zone.corps),
            )
            rapport.zones_ajoutees += 1

    return rapport
