r"""services/sequence_tout_compiler.py — v0.54.2

D-TOUT-SEQ — « Tout compiler » pour **toute séquence** de l'atelier (onglet
« Rendu PDF »), demande de Laurent du 26 octobre 2026 : tous les documents que
le modèle du référentiel sait produire pour la séquence, compilés en série
avec le même mécanisme que celui des mises en route (v0.53.3,
`services/mer_tout_compiler.py` : flux SSE, statuts, log d'un échec, cache
`cache_rendus`, annulation, abandon sur erreurs d'infrastructure, archive ZIP).
Les mises en route (Mnn) gardent leur liste et leur route.

Choix (nommés dans doc/redemarrage_v0_54_2.md) :

  - D-LISTE — **une table par modèle** : `DOCUMENTS_SEQUENCE_FICHES` (modèle
    « Fiches de résumé par objectif », valeur technique `sixieme`) et
    `DOCUMENTS_SEQUENCE_NOTIONS` (« Notions et méthodes », `cycle4`). Chaque
    ligne nomme un type du **catalogue du modèle**
    (`gabarits_documents.catalogue`, la source des « Documents à publier » et
    des producteurs de l'orchestrateur), sa racine de nom de fichier et ses
    déclinaisons (version, sujet). Les types du catalogue qui ne se
    rapportent pas à une séquence sont listés dans `EXCLUS_FICHES` /
    `EXCLUS_NOTIONS` avec leur raison. Un test exige que table et exclusions
    couvrent exactement le catalogue : un type ajouté plus tard au catalogue
    doit être rangé dans l'une ou l'autre (sinon le test échoue), donc compilé
    par « Tout compiler » dès qu'il concerne une séquence.
  - Les documents d'une même ligne sont énumérés comme pour la publication du
    référentiel (`referentiel_documents_compilation._cibles_evaluations_6e`,
    `_cibles_documents_6e`) puis filtrés sur la séquence : une évaluation
    appartient à la séquence de la majorité de ses exercices.
  - Même .tex que les boutons de l'onglet : le livret et le plan de travail
    passent par les mêmes générateurs avec les mêmes options (tests).
  - Aucune écriture en base : les générateurs lisent ; seuls le cache de
    compilation et les dossiers `cache_rendus/echecs_mer/` et `rapports/`
    reçoivent des fichiers.
  - Noms des fichiers : préfixe = la séquence en 6e (N09 : `S03_…`, comme
    `M03_…` pour les mises en route), niveau et séquence ailleurs
    (`N11_S04_…`) ; puis la racine et la déclinaison :
    `S03_livret_eleve.pdf`, `S03_eval2_A_corrige.pdf`, `S03_TP01_eleve.pdf`,
    `N11_S04_notions_methodes.pdf`, `N10_S01_eval1.pdf`…
"""

from __future__ import annotations

from dataclasses import dataclass

# ── D-LISTE : les tables par modèle ──────────────────────────────────────────

_VERSIONS = (("eleve", "élève", {"version": "eleve"}),
             ("corrige", "corrigé", {"version": "corrigee"}))
_SUJETS_VERSIONS = tuple((f"{s}_{suf}", f"sujet {s}, {lib}", {"sujet": s, **o})
                         for s in ("A", "B") for suf, lib, o in _VERSIONS)
_UNIQUE = (("", "", {}),)


@dataclass(frozen=True)
class DocumentSequence:
    """Une ligne de table : un type du catalogue du modèle.

    - `type_document` : clé du catalogue (`gabarits_documents`) ;
    - `racine`        : racine du nom de fichier (`{rang}` : rang de
                        l'évaluation dans la séquence ; `{code}` : TP01…) ;
    - `libelle`       : libellé affiché ;
    - `declinaisons`  : ((suffixe, libellé, options), …) — une par PDF ;
    - `portee`        : `sequence` (un document pour la séquence, s'il a un
                        contenu), `evaluations` (une par évaluation de la
                        séquence), `serie` (un par atome TP, AC ou AT) ;
    - `producteur`    : clé de `orchestrateur_compilation.REGISTRE`, ou
                        `plan_sequence_cycle4` (plan de travail du bouton de
                        l'onglet, cycle 4)."""
    type_document: str
    racine: str
    libelle: str
    declinaisons: tuple = _UNIQUE
    portee: str = "sequence"
    producteur: str = ""

    @property
    def cle_producteur(self) -> str:
        return self.producteur or self.type_document


DOCUMENTS_SEQUENCE_FICHES = (
    DocumentSequence("livret_sequence_6e", "livret", "Livret", _VERSIONS),
    DocumentSequence("fiches_cours_6e", "fiches_cours", "Fiches de cours (complètes)"),
    DocumentSequence("plans_travail_6e", "plan_de_travail", "Plan de travail"),
    DocumentSequence("evaluation_6e", "eval{rang}", "Évaluation", _SUJETS_VERSIONS,
                     portee="evaluations"),
    DocumentSequence("travaux_personnels_6e", "{code}", "Travail personnel", _VERSIONS,
                     portee="serie"),
    DocumentSequence("activites_complementaires_6e", "{code}", "Activité complémentaire",
                     _VERSIONS, portee="serie"),
    DocumentSequence("seances_atelier_6e", "{code}", "Séance d'atelier", _VERSIONS,
                     portee="serie"),
)

EXCLUS_FICHES = {
    "corriges_6e": ("pour une séquence, c'est le livret corrigé (même corps, seul le "
                    "titre interne change) ; son intérêt est le recueil annuel"),
}

DOCUMENTS_SEQUENCE_NOTIONS = (
    DocumentSequence("livret_sequence", "livret", "Livret de séquence"),
    DocumentSequence("livret_sequence", "notions_methodes", "Notions et méthodes",
                     (("", "", {"contenu": "cours_seul"}),)),
    DocumentSequence("livret_plans", "plan_de_travail", "Plan de travail",
                     producteur="plan_sequence_cycle4"),
    DocumentSequence("livret_fiches", "fiches", "Fiches de résumé",
                     (("a_completer", "à compléter", {"version_fiches": "a_completer"}),
                      ("completes", "complètes", {"version_fiches": "completes"}))),
    DocumentSequence("livret_cartes_planches", "cartes_planches",
                     "Planches de cartes d'automatisme"),
    DocumentSequence("evaluation", "eval{rang}", "Évaluation", portee="evaluations"),
)

EXCLUS_NOTIONS = {
    "livret_exercices": "livret annuel du niveau (toutes les séquences)",
    "livret_cours": "livret annuel du niveau (notions et méthodes de la séquence : "
                    "« notions_methodes »)",
    "livret_corriges": "livret annuel du niveau",
    "livret_cartes_recap": "récapitulatif annuel du niveau (8 cartes par page)",
}

TABLES = {"sixieme": (DOCUMENTS_SEQUENCE_FICHES, EXCLUS_FICHES),
          "cycle4": (DOCUMENTS_SEQUENCE_NOTIONS, EXCLUS_NOTIONS)}


class SequenceToutCompilerErreur(ValueError):
    pass


def table(gabarit: str) -> tuple:
    from services.gabarits_documents import normaliser
    return TABLES[normaliser(gabarit)][0]


def prefixe(niveau: str, sequence: str) -> str:
    """`S03` en 6e (N09), `N11_S04` ailleurs."""
    return sequence if niveau == "N09" else f"{niveau}_{sequence}"


# ── Énumération des documents d'une séquence ────────────────────────────────

def _a_contenu(conn, niveau: str, sequence: str, type_document: str) -> bool:
    """Un document « par séquence » n'est listé que si la séquence a de quoi
    le remplir (fiches de résumé, cartes validées) ; sinon le générateur
    échouerait à coup sûr (« aucune fiche »)."""
    if type_document in ("fiches_cours_6e", "livret_fiches"):
        return conn.execute("SELECT 1 FROM fiches_resume WHERE niveau=? AND sequence=? LIMIT 1",
                            (niveau, sequence)).fetchone() is not None
    if type_document == "livret_cartes_planches":
        return conn.execute("SELECT 1 FROM cartes_automatisme WHERE niveau=? AND sequence=? "
                            "AND etat_code='valide' LIMIT 1", (niveau, sequence)).fetchone() is not None
    return True


def _titre(c: dict) -> str:
    return (c.get("titre_doc") or "").replace(" --- ", " — ")


def _instances(conn, niveau: str, sequence: str, ligne: DocumentSequence) -> list[tuple]:
    """[(racine du nom, libellé, cible)] d'une ligne de table pour la séquence."""
    from services import referentiel_documents_compilation as rdc
    base = {"niveau": niveau, "sequence": sequence}
    if ligne.portee == "sequence":
        if not _a_contenu(conn, niveau, sequence, ligne.type_document):
            return []
        return [(ligne.racine, ligne.libelle, base)]
    if ligne.portee == "evaluations":
        evals = [c for c in rdc._cibles_evaluations_6e(conn, niveau)
                 if c.get("sequence") == sequence]
        return [(ligne.racine.format(rang=rang),
                 f"{ligne.libelle} {rang} : {_titre(c)}".rstrip(" :"),
                 {**base, "eval_id": c["eval_id"]})
                for rang, c in enumerate(evals, start=1)]
    if ligne.portee == "serie":
        out = []
        for c in rdc._cibles_documents_6e(conn, niveau, ligne.type_document):
            if c.get("sequence") != sequence:
                continue
            code = c["cible_id"].split("/")[0]
            out.append((ligne.racine.format(code=code),
                        f"{code} : {_titre(c)}".rstrip(" :"),
                        {**base, "exercice_id": c["exercice_id"]}))
        return out
    raise SequenceToutCompilerErreur(f"portée inconnue : {ligne.portee!r}")


def documents_a_compiler(conn, niveau: str, sequence: str, gabarit: str) -> list[dict]:
    """D-LISTE — [{nom, libelle, type_document, producteur, cible, options}]
    de la séquence, dans l'ordre de la table du modèle."""
    pre = prefixe(niveau, sequence)
    out: list[dict] = []
    for ligne in table(gabarit):
        for racine, libelle, cible in _instances(conn, niveau, sequence, ligne):
            for suffixe, lib_decl, options in ligne.declinaisons:
                nom = f"{pre}_{racine}" + (f"_{suffixe}" if suffixe else "") + ".pdf"
                out.append({"nom": nom,
                            "libelle": libelle + (f" — {lib_decl}" if lib_decl else ""),
                            "type_document": ligne.type_document,
                            "producteur": ligne.cle_producteur,
                            "cible": dict(cible), "options": dict(options)})
    return out


# ── Production du .tex ───────────────────────────────────────────────────────

def generer_tex(conn, doc: dict, tikz_libraries=None, tblr_libraries=None) -> str:
    """Le .tex d'un document de la liste : producteur de l'orchestrateur (le
    même que pour la publication du référentiel), ou le plan de travail de la
    séquence du cycle 4 (celui du bouton « Compiler le plan de travail »)."""
    cible, options = doc["cible"], doc["options"]
    if doc["producteur"] == "plan_sequence_cycle4":
        from services.livret_plans_de_travail import generer_plan_de_travail_sequence
        return generer_plan_de_travail_sequence(conn, cible["niveau"], cible["sequence"],
                                                tikz_libraries=tikz_libraries,
                                                tblr_libraries=tblr_libraries)
    from services import orchestrateur_compilation as orch
    producteur = orch.REGISTRE.get(doc["producteur"])
    if producteur is None:
        raise SequenceToutCompilerErreur(f"producteur inconnu : {doc['producteur']!r}")
    return producteur(conn, cible, options, tikz_libraries or [], tblr_libraries or [])


def nom_archive(niveau: str, sequence: str, maintenant=None) -> str:
    """`S03_sequence_documents_<date>.zip`, `N11_S04_sequence_documents_<date>.zip`."""
    from services.mer_tout_compiler import nom_archive as _nom
    return _nom(prefixe(niveau, sequence), None, maintenant)


def iter_tout_compiler(conn_factory, niveau: str, sequence: str, gabarit: str, *,
                       compiler, tikz_libraries=None, tblr_libraries=None,
                       dossier_echecs, dossier_archives,
                       max_erreurs_consecutives: int = 5, maintenant=None):
    """D-TOUT-SEQ — mêmes événements que `mer_tout_compiler.iter_tout_compiler`
    (debut, document, fin | abandon) ; un document qui échoue n'arrête pas
    les autres."""
    from services.mer_tout_compiler import iter_compiler_documents
    with conn_factory() as conn:
        docs = documents_a_compiler(conn, niveau, sequence, gabarit)

    def generer(conn, doc):
        return generer_tex(conn, doc, tikz_libraries, tblr_libraries)

    yield from iter_compiler_documents(
        conn_factory, [(d["nom"], d) for d in docs], generer, compiler=compiler,
        prefixe_echecs=prefixe(niveau, sequence), dossier_echecs=dossier_echecs,
        dossier_archives=dossier_archives,
        archive=nom_archive(niveau, sequence, maintenant),
        max_erreurs_consecutives=max_erreurs_consecutives)
