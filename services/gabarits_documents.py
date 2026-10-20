"""services/gabarits_documents.py — v0.52.1 (types 6e complétés en v0.52.2)

Gabarit de documents d'un référentiel : la liste des documents qu'il
publie et leur mise en forme. Champ `referentiel_niveaux.gabarit_documents` :

  - « cycle4 »  : les 9 types historiques (services/referentiel_documents.py),
                  mêmes clés, mêmes options — **rien ne change** ;
  - « sixieme » : documents au style de l'équipe de 6e (module LaTeX
                  `seqenseigne-style6e`) : livret de séquence 6e, fiches de
                  cours 6e, corrigés enseignant 6e ; v0.52.2 : évaluations,
                  travaux personnels, activités complémentaires, séances
                  d'atelier.

Décisions (cadrage du 19 octobre, `doc/redemarrage_v0_52_1.md`) :

  - G1 Défaut `cycle4` pour tous les référentiels existants (colonne ajoutée
    avec DEFAULT) ; à la création, valeur proposée selon le niveau : N09 →
    `sixieme`, N10 à N12 → `cycle4`.
  - G2 Modifiable tant que le référentiel est « en_cours », figé ensuite.
  - G3 Aucune clé de type n'est renommée : les chaînes `type|cible` sont
    enregistrées côté classe (progression_doc). Les types du gabarit 6e ont
    des clés nouvelles.
  - G4 La contrainte CHECK qui figeait les 9 types sur
    `referentiel_documents.type_document` est levée (reconstruction unique,
    sauvegarde JSON) ; la validation se fait ici, d'après le catalogue.
  - G5 Changer de gabarit ne supprime rien : les lignes de l'autre gabarit
    restent en base (options conservées), simplement non affichées ni
    compilées ni proposées.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

GABARITS = ("cycle4", "sixieme")
GABARIT_DEFAUT = "cycle4"

# v0.52.4 (M1) — Le gabarit est un **modèle de référentiel** (conception et
# mise en forme), indépendant du niveau : tout référentiel de N09 à N12 peut
# choisir l'un ou l'autre. Les valeurs techniques (`cycle4`, `sixieme`)
# restent en base et dans le format d'échange ; seuls les libellés changent.
LIBELLES_GABARITS = {"cycle4": "Notions et méthodes",
                     "sixieme": "Fiches de résumé par objectif"}

# Description affichée à la création et dans « Documents à publier » :
# documents produits, séries proposées, règles de complétude.
MODELES = {
    "cycle4": {
        "libelle": LIBELLES_GABARITS["cycle4"],
        "resume": ("Chaque objectif reçoit une méthode et des notions ; "
                   "livrets du cycle 4."),
        "documents": ("livret de séquence, livrets d'exercices, de cours, de fiches, "
                      "de plans de travail et de corrigés, évaluations, cartes "
                      "d'automatisme"),
        "series": "F, A, E ; révisions et activités d'approche",
        "completude": ("par objectif d'exercices : au moins un exercice F, A et E, "
                       "critères F, A et E ; notions, méthodes et cartes validées"),
    },
    "sixieme": {
        "libelle": LIBELLES_GABARITS["sixieme"],
        "resume": ("Pas de notions ni de méthodes : une fiche de résumé par objectif, "
                   "à compléter dans le livret d'exercices, complète dans le plan de "
                   "travail, distribuée pour le cahier de cours."),
        "documents": ("livret de séquence (fiches à compléter), fiches de cours, plans "
                      "de travail, corrigés, évaluations par compétence, travaux "
                      "personnels, activités complémentaires, séances d'atelier"),
        "series": ("F, A, E (facultative) ; activités d'introduction ; TP, AC, AT ; "
                   "EV (sujet B dans la remédiation)"),
        "completude": ("par objectif d'exercices : au moins un exercice F et un "
                       "exercice A, critères F et A, la fiche de résumé de l'objectif"),
    },
}


def est_modele_fiches(gabarit) -> bool:
    """Modèle « Fiches de résumé par objectif » (valeur technique `sixieme`)."""
    return normaliser(gabarit) == "sixieme"

# Niveaux dont le gabarit proposé à la création est « sixieme ».
NIVEAUX_SIXIEME = ("N09",)


class GabaritErreur(Exception):
    def __init__(self, message: str, code: str = "gabarit_invalide"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TypeDocument:
    """Un type de document d'un gabarit.

    - `cle`        : type_document en base (jamais renommé, G3) ;
    - `libelle`    : titre affiché dans « Documents à publier » ;
    - `description`: sous-titre ;
    - `options`    : options par défaut (dont `actif`) ;
    - `valeurs`    : valeurs permises des options énumérées ;
    - `generateur` : producteur enregistré dans
                     services/orchestrateur_compilation.REGISTRE (même clé) ;
    - `champs`     : options à afficher (clé, libellé), pour l'interface
                     générique des nouveaux types (les 9 types du cycle 4
                     gardent leur interface propre).
    """
    cle: str
    libelle: str
    description: str
    options: dict
    valeurs: dict = field(default_factory=dict)
    generateur: str = ""
    champs: tuple = ()

    def options_par_defaut(self) -> dict:
        return dict(self.options)


# ── Gabarit cycle 4 : les 9 types historiques, à l'identique ────────────────

_LIBELLES_CYCLE4 = {
    "livret_sequence": ("Livret de séquence",
                        "Un livret par séquence. Mêmes options pour toutes les séquences."),
    "livret_exercices": ("Livret d'exercices",
                         "Tous les exercices du niveau, organisés par séquence."),
    "livret_cours": ("Livret de cours",
                     "Toutes les notions et méthodes du niveau, par séquence."),
    "livret_fiches": ("Livret de fiches de résumé",
                      "Toutes les fiches de résumé du niveau, par séquence."),
    "livret_plans": ("Livret de plans de travail",
                     "Plans de travail des séquences du niveau."),
    "livret_corriges": ("Livret de corrigés d'exercices",
                        "Tous les corrigés du niveau, organisés par séquence."),
    "evaluation": ("Évaluations",
                   "Une page par évaluation déclarée."),
    "livret_cartes_recap": ("Récap des cartes d'automatisme",
                            "Pour l'enseignant : 8 cartes par page."),
    "livret_cartes_planches": ("Planches de cartes d'automatisme",
                               "Pour les élèves : 16 exemplaires par carte par feuille."),
}

_GENERATEURS_CYCLE4 = {
    "livret_sequence": "services.livret_sequence.generer_livret_sequence",
    "livret_exercices": "services.livret_recap_exos.generer_recap_exos",
    "livret_cours": "services.livret_recap_cours.generer_recap_cours",
    "livret_fiches": "services.livret_fiches.generer_livret_fiches",
    "livret_plans": "services.livret_plans_de_travail.generer_livret_plans_de_travail",
    "livret_corriges": "services.livret_corriges.generer_livret_corriges",
    "evaluation": "services.render_evaluation.generer_tex_evaluation",
    "livret_cartes_recap": "services.livret_cartes_recap.generer_livret_cartes_recap",
    "livret_cartes_planches":
        "services.livret_cartes_planches.generer_livret_cartes_planches",
}


def _catalogue_cycle4() -> tuple:
    # Source des clés et options : services/referentiel_documents.py
    # (TYPES_DOCUMENT, OPTIONS_PAR_DEFAUT, ENUMS), inchangé depuis v0.48.1.
    from services import referentiel_documents as rd
    out = []
    for cle in rd.TYPES_DOCUMENT:
        defaut = rd.OPTIONS_PAR_DEFAUT[cle]
        valeurs = {k: tuple(v) for k, v in rd.ENUMS.items() if k in defaut}
        lib, desc = _LIBELLES_CYCLE4[cle]
        out.append(TypeDocument(cle=cle, libelle=lib, description=desc,
                                options=dict(defaut), valeurs=valeurs,
                                generateur=_GENERATEURS_CYCLE4[cle]))
    return tuple(out)


# ── Gabarit 6e ───────────────────────────────────────────────────────────────

VERSIONS_6E = ("eleve", "corrigee")
FICHES_PLAN_6E = ("texte_complet", "titre")             # v0.52.3
REMEDIATIONS_6E = ("apres_exercice", "en_fin", "aucune")
DECOUPAGES_6E = ("par_sequence", "annuel", "les_deux")
SUJETS_6E = ("A", "B")                                   # v0.52.2
# v0.52.8 (C2) — « selon_evaluation » (nouveau défaut) : chaque évaluation
# suit son réglage, sinon le marquage de ses exercices (règle C1) ; les autres
# valeurs imposent la mention à toutes les évaluations du niveau.
CALCULATRICE_6E = ("selon_evaluation", "interdite", "autorisee", "non_precisee")

_CATALOGUE_SIXIEME = (
    TypeDocument(
        cle="livret_sequence_6e",
        libelle="Livret de séquence",
        description=("Un livret d'exercices par séquence : par objectif, "
                     "activités d'introduction, fiche de résumé à compléter, "
                     "exercices F, A, E et remédiations."),
        options={"actif": False, "version": "eleve", "inclure_activites": True,
                 "inclure_serie_E": True, "remediations": "apres_exercice"},
        valeurs={"version": VERSIONS_6E, "remediations": REMEDIATIONS_6E},
        generateur="services.livret_sequence_6e.generer_livret_sequence_6e",
        champs=(("version", "Version", (("eleve", "élève"), ("corrigee", "corrigée"))),
                ("inclure_activites", "Activités d'introduction", None),
                ("inclure_serie_E", "Exercices d'expertise (E)", None),
                ("remediations", "Remédiations",
                 (("apres_exercice", "après l'exercice"), ("en_fin", "en fin de livret"),
                  ("aucune", "aucune")))),
    ),
    TypeDocument(
        cle="fiches_cours_6e",
        libelle="Fiches de cours",
        description="Les fiches de résumé en version complète.",
        options={"actif": False, "decoupage": "par_sequence"},
        valeurs={"decoupage": DECOUPAGES_6E},
        generateur="services.livret_sequence_6e.generer_fiches_cours_6e",
        champs=(("decoupage", "Découpage",
                 (("par_sequence", "par séquence"), ("annuel", "un livret annuel"),
                  ("les_deux", "les deux"))),),
    ),
    TypeDocument(
        cle="corriges_6e",
        libelle="Corrigés enseignant",
        description="Le livret en version corrigée, remédiations comprises.",
        options={"actif": False, "decoupage": "par_sequence", "inclure_activites": True,
                 "inclure_serie_E": True},
        valeurs={"decoupage": DECOUPAGES_6E},
        generateur="services.livret_sequence_6e.generer_corriges_6e",
        champs=(("decoupage", "Découpage",
                 (("par_sequence", "par séquence"), ("annuel", "un livret annuel"),
                  ("les_deux", "les deux"))),
                ("inclure_activites", "Activités d'introduction", None),
                ("inclure_serie_E", "Exercices d'expertise (E)", None)),
    ),
    # v0.52.2 — Évaluations (module Évaluations, exercices de la série EV :
    # sujet A dans l'énoncé, sujet B dans la remédiation) et documents rangés
    # dans l'atelier d'exercices (séries TP, AC, AT : un atome = un document).
    TypeDocument(
        cle="evaluation_6e",
        libelle="Évaluations",
        description=("Une par évaluation du niveau : barème par compétence, "
                     "sujet A ou B (le sujet B sert à la remédiation)."),
        options={"actif": False, "sujet": "A", "version": "eleve",
                 "calculatrice": "selon_evaluation"},
        valeurs={"sujet": SUJETS_6E, "version": VERSIONS_6E,
                 "calculatrice": CALCULATRICE_6E},
        generateur="services.render_evaluation.generer_tex_evaluation_6e",
        champs=(("sujet", "Sujet", (("A", "A"), ("B", "B"))),
                ("version", "Version", (("eleve", "élève"), ("corrigee", "corrigée"))),
                ("calculatrice", "Calculatrice",
                 (("selon_evaluation", "selon l'évaluation"), ("interdite", "interdite"),
                  ("autorisee", "autorisée"), ("non_precisee", "non précisée")))),
    ),
    TypeDocument(
        cle="travaux_personnels_6e",
        libelle="Travaux personnels",
        description="Un document par travail personnel (série TP de l'atelier d'exercices).",
        options={"actif": False, "version": "eleve"},
        valeurs={"version": VERSIONS_6E},
        generateur="services.documents_6e.generer_document_6e",
        champs=(("version", "Version", (("eleve", "élève"), ("corrigee", "corrigée"))),),
    ),
    TypeDocument(
        cle="activites_complementaires_6e",
        libelle="Activités complémentaires",
        description="Un document par activité complémentaire (série AC).",
        options={"actif": False, "version": "eleve"},
        valeurs={"version": VERSIONS_6E},
        generateur="services.documents_6e.generer_document_6e",
        champs=(("version", "Version", (("eleve", "élève"), ("corrigee", "corrigée"))),),
    ),
    # v0.52.3 — Plan de travail de l'équipe de 6e (une cible par séquence).
    TypeDocument(
        cle="plans_travail_6e",
        libelle="Plans de travail",
        description=("Un plan de travail par séquence : "
                     "objectifs, activités, à retenir, exercices du livret O / ( ) / [ ], "
                     "travaux personnels, synthèse et évaluation."),
        options={"actif": False, "fiches": "texte_complet"},
        valeurs={"fiches": FICHES_PLAN_6E},
        generateur="services.plan_travail_6e.generer_plan_travail_6e",
        champs=(("fiches", "À retenir",
                 (("texte_complet", "fiche en entier"), ("titre", "titre seulement"))),),
    ),
    TypeDocument(
        cle="seances_atelier_6e",
        libelle="Séances d'atelier",
        description="Un document par séance d'atelier (série AT).",
        options={"actif": False, "version": "eleve"},
        valeurs={"version": VERSIONS_6E},
        generateur="services.documents_6e.generer_document_6e",
        champs=(("version", "Version", (("eleve", "élève"), ("corrigee", "corrigée"))),),
    ),
)


def catalogue(gabarit: str) -> tuple:
    """Types de documents du gabarit, dans l'ordre d'affichage."""
    g = normaliser(gabarit)
    return _catalogue_cycle4() if g == "cycle4" else _CATALOGUE_SIXIEME


def types(gabarit: str) -> tuple:
    return tuple(t.cle for t in catalogue(gabarit))


def tous_les_types() -> dict:
    """{clé: TypeDocument} de tous les gabarits (les clés sont uniques)."""
    out = {}
    for g in GABARITS:
        for t in catalogue(g):
            out[t.cle] = t
    return out


def type_document(cle: str) -> TypeDocument | None:
    return tous_les_types().get(cle)


def gabarit_du_type(cle: str) -> str | None:
    for g in GABARITS:
        if cle in types(g):
            return g
    return None


def normaliser(valeur) -> str:
    """Valeur absente (fichier d'échange 1.0, base ancienne) → `cycle4`."""
    v = (valeur or "").strip() if isinstance(valeur, str) else ""
    return v if v in GABARITS else GABARIT_DEFAUT


def valider_gabarit(valeur) -> str:
    if valeur not in GABARITS:
        raise GabaritErreur(f"Gabarit de documents inconnu : {valeur!r} "
                            f"(attendu : {', '.join(GABARITS)}).")
    return valeur


def gabarit_par_defaut(niveau: str) -> str:
    """G1 — Valeur proposée à la création d'un référentiel."""
    return "sixieme" if (niveau or "").strip() in NIVEAUX_SIXIEME else GABARIT_DEFAUT


def referentiel_atelier_du_niveau(conn, niveau: str) -> str | None:
    """Règle R1b (v0.52.4) — référentiel de l'atelier d'un niveau : le
    référentiel **interne principal** du niveau, **quel que soit son état
    sauf « annule »** (en_cours, valide, verrouille, utilise), le plus récent
    (version décroissante, puis id). Avant v0.52.4 (R1), seul l'état
    « en_cours » comptait : un référentiel auto-validé ou verrouillé faisait
    retomber l'atelier sur le défaut du niveau."""
    try:
        r = conn.execute(
            "SELECT id FROM referentiel_niveaux WHERE niveau = ? AND etat <> 'annule' "
            "AND COALESCE(source, 'interne') <> 'externe' "
            "AND COALESCE(type_ref, 'principal') = 'principal' "
            "ORDER BY version DESC, id DESC LIMIT 1", (niveau,)).fetchone()
    except Exception:
        r = None
    return r[0] if r is not None else None


def gabarit_atelier_du_niveau(conn, niveau: str) -> str:
    """Décision R1 (v0.52.1), partagée en v0.52.2 avec le module
    Évaluations, règle R1b depuis v0.52.4 : gabarit des documents que
    l'atelier produit pour un niveau sans paramètre explicite = celui du
    référentiel de l'atelier (`referentiel_atelier_du_niveau`), sinon la
    valeur proposée pour le niveau (N09 → sixieme, N10 à N12 → cycle4)."""
    ref = referentiel_atelier_du_niveau(conn, niveau)
    if ref is not None:
        return gabarit_du_referentiel(conn, ref)
    return gabarit_par_defaut(niveau)


def gabarits_atelier(conn) -> dict:
    """{niveau: gabarit} de l'atelier (R1b) pour les niveaux connus
    (param_niveaux, sinon N09 à N12) — mis à disposition de l'interface."""
    try:
        niveaux = [r[0] for r in conn.execute("SELECT code FROM param_niveaux ORDER BY ordre")]
    except Exception:
        niveaux = []
    niveaux = niveaux or ["N09", "N10", "N11", "N12"]
    return {n: gabarit_atelier_du_niveau(conn, n) for n in niveaux}


def types_du_referentiel(conn, ref_id: str) -> tuple:
    """D2 (v0.52.4) — Types de documents du gabarit du référentiel : seuls
    ceux-là comptent pour la validation, le figeage et la publication (un
    document actif d'un autre gabarit reste en base, sans effet)."""
    return types(gabarit_du_referentiel(conn, ref_id))


# ── Validation des options (G4) ──────────────────────────────────────────────

def valider_options(cle_type: str, options: dict) -> dict:
    """Valide un dict d'options *partiel* d'après le catalogue du type.

    Clés autorisées : celles des options par défaut ; type conservé (bool,
    str) ; valeurs énumérées dans `valeurs`. Lève
    referentiel_documents.DocumentErreur (même contrat que v0.13.6.4)."""
    from services.referentiel_documents import DocumentErreur
    t = type_document(cle_type)
    if t is None:
        raise DocumentErreur(f"Type de document inconnu : {cle_type!r}",
                             code="type_inconnu")
    if not isinstance(options, dict):
        raise DocumentErreur("Options doit être un objet/dict", code="options_non_dict")
    autorisees = t.options
    erreurs, sortie = [], {}
    for cle, val in options.items():
        if cle not in autorisees:
            erreurs.append(f"clé inconnue pour {cle_type!r} : {cle!r}")
            continue
        attendu = type(autorisees[cle])
        if attendu is bool:
            if not isinstance(val, bool):
                erreurs.append(f"{cle!r} attend bool, reçu {type(val).__name__}")
                continue
        elif attendu is str:
            if not isinstance(val, str):
                erreurs.append(f"{cle!r} attend str, reçu {type(val).__name__}")
                continue
            if cle in t.valeurs and val not in t.valeurs[cle]:
                erreurs.append(f"{cle!r} : valeur {val!r} non autorisée "
                               f"(attendu : {', '.join(t.valeurs[cle])})")
                continue
        else:
            erreurs.append(f"{cle!r} : type interne inattendu")
            continue
        sortie[cle] = val
    if erreurs:
        raise DocumentErreur("Options invalides", code="options_invalides",
                             details={"erreurs": erreurs})
    return sortie


def description_interface(cle_type: str) -> dict:
    """Libellé, sous-titre et champs d'options (interface générique)."""
    t = type_document(cle_type)
    if t is None:
        return {"libelle": cle_type, "description": "", "champs": []}
    champs = []
    for cle, lib, choix in t.champs:
        if choix is None:
            champs.append({"cle": cle, "libelle": lib, "type": "bool"})
        else:
            champs.append({"cle": cle, "libelle": lib, "type": "choix",
                           "valeurs": [list(c) for c in choix]})
    return {"libelle": t.libelle, "description": t.description, "champs": champs}


# ── Lecture / écriture du champ ──────────────────────────────────────────────

def _a_colonne(conn) -> bool:
    return "gabarit_documents" in {r[1] for r in conn.execute(
        "PRAGMA table_info(referentiel_niveaux)")}


def gabarit_du_referentiel(conn, ref_id: str) -> str:
    """Gabarit d'un référentiel (`cycle4` si inconnu ou colonne absente)."""
    if not ref_id or not _a_colonne(conn):
        return GABARIT_DEFAUT
    r = conn.execute("SELECT gabarit_documents FROM referentiel_niveaux WHERE id=?",
                     (ref_id,)).fetchone()
    return normaliser(r[0] if r else None)


def poser_a_la_creation(conn, ref_id: str, niveau: str, gabarit=None) -> str:
    """Gabarit choisi à la création (liste préremplie selon le niveau, G1).
    `gabarit` absent → valeur proposée pour le niveau."""
    g = gabarit_par_defaut(niveau) if gabarit in (None, "") else valider_gabarit(gabarit)
    if _a_colonne(conn):
        conn.execute("UPDATE referentiel_niveaux SET gabarit_documents=? WHERE id=?",
                     (g, ref_id))
    return g


# G2b (v0.52.4) — États où le modèle se modifie : « en_cours » et
# « valide » (auto-validation, qui retombe en « en_cours » dès que les
# documents ne sont plus à jour) ; figé au verrouillage.
ETATS_MODIFIABLES = ("en_cours", "valide")


def modifier(conn, ref_id: str, gabarit: str) -> str:
    """G2 / G2b — Change le gabarit d'un référentiel « en_cours » ou
    « valide » ; figé au verrouillage. Un référentiel « valide » est réévalué
    aussitôt (ses documents du nouveau modèle ne sont pas compilés)."""
    valider_gabarit(gabarit)
    r = conn.execute("SELECT etat FROM referentiel_niveaux WHERE id=?", (ref_id,)).fetchone()
    if r is None:
        raise GabaritErreur(f"Référentiel introuvable : {ref_id}", code="introuvable")
    if r[0] not in ETATS_MODIFIABLES:
        raise GabaritErreur("Le modèle du référentiel est figé : il ne se modifie plus "
                            "après le verrouillage.", code="fige")
    conn.execute("UPDATE referentiel_niveaux SET gabarit_documents=? WHERE id=?",
                 (gabarit, ref_id))
    conn.commit()
    if r[0] == "valide":
        try:
            from services.referentiel_documents import initialiser_documents_defaut
            from services.referentiel_validation import maj_etat_lazy
            initialiser_documents_defaut(conn, ref_id)
            maj_etat_lazy(conn, ref_id)
        except Exception:
            pass
    return gabarit


def documents_actifs_hors_modele(conn, ref_id: str) -> int:
    """Nombre de documents actifs d'un autre modèle que celui du référentiel
    (restés en base après un changement de modèle, sans effet)."""
    import json
    garder = set(types_du_referentiel(conn, ref_id))
    n = 0
    for t, o in conn.execute("SELECT type_document, options FROM referentiel_documents "
                             "WHERE referentiel_id=?", (ref_id,)).fetchall():
        if t in garder:
            continue
        try:
            if json.loads(o or "{}").get("actif"):
                n += 1
        except (TypeError, ValueError):
            pass
    return n


def description_modeles() -> list:
    """M1 — Les deux modèles, pour l'interface (création, Documents à publier)."""
    return [{"valeur": g, **MODELES[g]} for g in GABARITS]


# ── Migration (idempotente, appelée par persistence/sqlite_store.py) ─────────

def _ddl_referentiel_documents(conn) -> str:
    r = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' "
                     "AND name='referentiel_documents'").fetchone()
    return (r[0] if r else "") or ""


_RE_CHECK_TYPES = re.compile(r"CHECK\s*\(\s*type_document\s+IN\s*\(", re.IGNORECASE)


def contrainte_types_presente(conn) -> bool:
    """La contrainte CHECK historique (9 types) est-elle encore là ?"""
    return bool(_RE_CHECK_TYPES.search(_ddl_referentiel_documents(conn)))


def migrer(conn, data_dir=None) -> dict:
    """1. colonne `gabarit_documents` (DEFAULT 'cycle4') ;
    2. G4 — reconstruction unique de `referentiel_documents` sans la
       contrainte CHECK sur `type_document`, après sauvegarde JSON du contenu
       dans `<data>/sauvegardes/` (même procédure que les reconstructions de
       sqlite_store : nouvelle table, INSERT … SELECT, DROP, RENAME, FK
       désactivées le temps de l'opération). Détectée par la présence de la
       contrainte : ne se refait jamais."""
    res = {"colonne": False, "reconstruction": False, "sauvegarde": ""}
    cols = {r[1] for r in conn.execute("PRAGMA table_info(referentiel_niveaux)")}
    if cols and "gabarit_documents" not in cols:
        conn.execute("ALTER TABLE referentiel_niveaux ADD COLUMN gabarit_documents "
                     "TEXT NOT NULL DEFAULT 'cycle4'")
        conn.commit()
        res["colonne"] = True
    if not contrainte_types_presente(conn):
        return res
    if data_dir is not None:
        from services.retraits import _sauvegarder
        res["sauvegarde"] = str(_sauvegarder(conn, data_dir, "contrainte_referentiel_documents",
                                             ("referentiel_documents",)))
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            BEGIN;
            CREATE TABLE referentiel_documents_v0521 (
                id              TEXT PRIMARY KEY,
                referentiel_id  TEXT NOT NULL
                                REFERENCES referentiel_niveaux(id) ON DELETE CASCADE,
                type_document   TEXT NOT NULL,
                options         TEXT NOT NULL DEFAULT '{}',
                ordre           INTEGER NOT NULL DEFAULT 0,
                mtime           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                compile_ok       INTEGER,
                compile_date     DATETIME,
                compile_log      TEXT,
                compile_en_cours INTEGER NOT NULL DEFAULT 0,
                UNIQUE (referentiel_id, type_document)
            );
            INSERT INTO referentiel_documents_v0521
                (id, referentiel_id, type_document, options, ordre, mtime,
                 compile_ok, compile_date, compile_log, compile_en_cours)
            SELECT id, referentiel_id, type_document, options, ordre, mtime,
                   compile_ok, compile_date, compile_log, compile_en_cours
              FROM referentiel_documents;
            DROP TABLE referentiel_documents;
            ALTER TABLE referentiel_documents_v0521 RENAME TO referentiel_documents;
            CREATE INDEX IF NOT EXISTS idx_referentiel_documents_referentiel_id
                ON referentiel_documents(referentiel_id);
            COMMIT;
        """)
        res["reconstruction"] = True
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    return res

