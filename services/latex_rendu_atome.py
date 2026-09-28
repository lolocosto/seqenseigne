r"""
services/latex_rendu_atome.py — Génération du .tex d'un atome isolé.

Produit un fichier .tex complet et autonome (classe article + préambule +
document) à partir d'un atome (exercice, notion, méthode) stocké en BDD.

Principe général :

1. Détection des options du paquet seqenseigne selon les macros utilisées
   par l'atome (['geometrie'] si tkz-euclide/tikz, ['scratch'] si scratch3).
2. Résolution du thème depuis le référentiel (couleur de la séquence).
3. Résolution des macros CSV-dépendantes (\seqObjectifGetNom, etc.) par
   substitution directe des valeurs depuis la BDD.
4. Application des règles de réécriture (\seqCorrige inline, etc.).
5. Génération du corps : environnement seqExercice/seqNotion/seqMethode
   selon le type d'atome.

Note v0.10 : l'inclusion d'un fichier NXX_SYY_params.tex de séquence a été
supprimée. Les variables xint et les macros locales (\newcommand, etc.) sont
désormais stockées par exercice en base et inlinées directement dans le .tex
généré, ce qui rend le mécanisme de fichier partagé obsolète et stabilise
le hash de cache de compilation (auparavant dépendant du chemin absolu).

Entrée : un id d'atome + un type (exercices/notions/methodes).
Sortie : une chaîne .tex prête à être compilée par pdflatex.

Aucune dépendance externe. Importable par Flask et par les scripts.
"""

from __future__ import annotations
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from services.preambule_atome import construire_preambule


# ── Constantes ────────────────────────────────────────────────────────────────

# Paquets TeX qui déclenchent l'option [geometrie]
PAQUETS_GEOMETRIE = frozenset({
    'tkz-euclide', 'tkz-base', 'tkz-tab',
    # tikz est déjà chargé par le paquet sans option, mais si l'atome utilise
    # des macros tkz-euclide avancées, on active l'option pour cohérence.
})

# Paquets TeX qui déclenchent l'option [scratch]
PAQUETS_SCRATCH = frozenset({'scratch3'})

# Couleurs de thème valides (arguments de \seqSetColorsTheme)
THEMES_VALIDES = frozenset({
    'nombres', 'donnees', 'grandeurs', 'geometrie', 'algorithmique', 'gris',
})

# Types d'atomes et leurs tables associées
TABLES_ATOMES = {
    'exercice': 'exercices',
    'notion':   'notions',
    'methode':  'methodes',
    # v0.11.1 — Fiche de résumé. Le titre de la fiche est saisi librement
    # (pas de machinerie .dbtex contrairement aux \boiteTitreFlashcard du
    # livret annuel) et chaque section devient un \begin{boiteContenuFlashcard}
    # avec son propre titre. Cf. generer_corps_fiche.
    'fiche':    'fiches_resume',
}


# v0.14.2 — Élargissement du concept d'atome aux cartes d'automatisme.
# Les cartes ont un générateur .tex distinct (services.render_carte.generer_tex_carte)
# et leurs propres exceptions métier, mais du point de vue du pipeline
# « génère .tex → hash → cache → compile pdflatex », elles sont traitées
# comme n'importe quel autre atome.
#
# Cet ensemble inclut les 5 types pour les routes API unifiées
# (POST /api/atomes/<type>/<id>/rendu-pdf, GET /info, /rendu-tex, /rendu-log).
# Pour 4 types sur 5, la génération du .tex passe par generer_tex_atome
# ci-dessous ; pour 'carte', voir le dispatch generer_tex_par_type.
TYPES_ATOMES_TOUS = frozenset({'exercice', 'notion', 'methode', 'fiche', 'carte'})


# ── Structure d'un atome chargé ────────────────────────────────────────────────

@dataclass
class Atome:
    """Représentation uniforme d'un atome (exercice, notion ou méthode)."""
    id: str
    type_atome: str          # 'exercice' | 'notion' | 'methode'
    niveau: str              # 'N10', 'N11', 'N12'
    sequence: str            # 'S01' … 'S14'
    fichier: str             # nom du .tex d'origine (pour diagnostic)
    # Contenus LaTeX
    titre: str = ''
    corps: str = ''          # champ 'corps' pour notion/méthode, 'enonce' pour exercice
    corrige: str = ''        # uniquement exercice
    variables: str = ''      # uniquement exercice
    # Métadonnées spécifiques
    serie: str = ''          # exercice : 'F' | 'A' | 'E' | 'AE'
    num: int | None = None
    num_objectif: str = ''   # méthode : '02', '03'…
    num_connaissance: str = ''  # notion
    # v0.6.4 : 'fin_cycle' a été retiré de l'Atome méthode — c'est une
    # caractéristique d'OBJECTIF (programme officiel), jamais de méthode.
    # La propriété est désormais portée par objectifs.fin_cycle et éditée
    # dans seqniv. La colonne legacy methodes.fin_cycle subsiste en BDD
    # pour rétrocompatibilité avec l'ancien format methodes.json mais n'est
    # plus exposée par cette dataclass ni utilisée dans la chaîne de rendu.
    #
    # v0.6.4 (2e refacto) : les sections Exemples/Remarques sont remplacées
    # par un modèle universel à 2 niveaux. Une notion ou méthode peut avoir
    # un nombre arbitraire de sections, chacune avec un titre libre
    # (Exemples, Remarques, Conséquences, Démonstration, Démonstration de
    # la réciproque, Propriétés, etc.) et une liste d'items LaTeX.
    # Les items peuvent contenir des structures complexes (sous-listes
    # imbriquées, multicols, tikzpicture).
    sections: list[dict] = field(default_factory=list)
    # ordre_sections : conservé pour compatibilité avec d'anciennes
    # données. N'est plus utilisé pour le rendu (l'ordre est désormais
    # piloté par l'ordre des sections dans la liste `sections`).
    ordre_sections: str = 'ER'
    # v0.11.1.x — Pour fiche, nom de l'objectif lié (utilisé en fallback
    # si le titre est vide). Vide pour les autres types ou pour les
    # fiches sans objectif lié.
    objectif_nom: str = ''
    # v0.11.6 — Remédiation et cadre de réponse (exercices uniquement).
    # remed_enonce / remed_corrige : chaînes vides si l'exo n'a pas de
    # remédiation. Côté UI, le cadre Remédiation n'est affiché que pour
    # les exos de série F et A (pas pertinent pour E), mais côté backend
    # on accepte la remédiation pour n'importe quelle série.
    # cadre_reponse_lignes_principal / cadre_reponse_lignes_remed :
    # 0 = pas de cadre de réponse, sinon nombre de lignes (1-99).
    remed_enonce: str = ''
    remed_corrige: str = ''
    cadre_reponse_lignes_principal: int = 0
    cadre_reponse_lignes_remed: int = 0


def lire_codes_objectifs_de_exercice(conn: sqlite3.Connection,
                                      exercice_id: str) -> list[str]:
    """v0.11.6.2 — Liste des codes d'objectifs liés à un exercice.

    Un exercice peut être rattaché à plusieurs objectifs via la table
    objectif_exos (PK composite (objectif_id, serie, exercice_id)). Cette
    fonction renvoie les codes (champ objectifs.code) des objectifs
    associés, dédupliqués et triés par code.

    Sert principalement à passer ``obj=...`` à \\begin{seqExercice} pour
    afficher la liste des objectifs dans la boîte de titre (cf. demande
    Laurent v0.11.6.2).

    Tolère l'absence des tables objectif_exos / objectifs (cas des
    tests unitaires qui utilisent un schéma minimal) en renvoyant une
    liste vide.
    """
    try:
        rows = conn.execute(
            "SELECT DISTINCT o.code "
            "FROM objectif_exos oe "
            "JOIN objectifs o ON o.id = oe.objectif_id "
            "WHERE oe.exercice_id = ? "
            "ORDER BY o.code",
            (exercice_id,)
        ).fetchall()
    except sqlite3.OperationalError:
        # Table absente — environnement de test minimal. On dégrade
        # silencieusement : pas d'option obj=, le rendu fonctionne.
        return []
    return [r[0] for r in rows if r[0]]


def charger_atome(conn: sqlite3.Connection, type_atome: str, atome_id: str) -> Atome:
    """Charge un atome depuis la BDD par son type et son id.

    Lève ValueError si type_atome est inconnu, LookupError si l'atome n'existe pas.
    """
    if type_atome not in TABLES_ATOMES:
        raise ValueError(
            f"type_atome inconnu : {type_atome!r}. "
            f"Valeurs attendues : {sorted(TABLES_ATOMES)}"
        )
    table = TABLES_ATOMES[type_atome]

    if type_atome == 'exercice':
        # v0.11.6 — Lecture des champs de remédiation et cadre de réponse.
        # Ces colonnes ont été ajoutées par la migration _migrer_schema_post_ddl
        # (sqlite_store.py). Elles sont peuplées soit par l'UI atelier exercice
        # (PUT /api/exercices/<id>) soit laissées à leurs valeurs par défaut
        # ('' / 0) pour les exos importés depuis le filesystem (le scanner
        # LaTeX n'a pas de notion de remédiation côté .tex source).
        row = conn.execute(
            "SELECT id, niveau, sequence, fichier, titre, serie, num, "
            "       enonce, corrige, variables, "
            "       remed_enonce, remed_corrige, "
            "       cadre_reponse_lignes_principal, cadre_reponse_lignes_remed "
            "FROM exercices WHERE id = ?", (atome_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Exercice introuvable : {atome_id!r}")
        return Atome(
            id=row[0], type_atome='exercice',
            niveau=row[1], sequence=row[2], fichier=row[3],
            titre=row[4], serie=row[5], num=row[6],
            corps=row[7] or '', corrige=row[8] or '', variables=row[9] or '',
            remed_enonce=row[10] or '',
            remed_corrige=row[11] or '',
            cadre_reponse_lignes_principal=row[12] or 0,
            cadre_reponse_lignes_remed=row[13] or 0,
        )

    if type_atome == 'notion':
        row = conn.execute(
            "SELECT id, niveau, sequence, fichier, titre, corps, "
            "       num_connaissance, ordre_sections "
            "FROM notions WHERE id = ?", (atome_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Notion introuvable : {atome_id!r}")
        return Atome(
            id=row[0], type_atome='notion',
            niveau=row[1], sequence=row[2], fichier=row[3],
            titre=row[4], corps=row[5] or '',
            num_connaissance=row[6],
            ordre_sections=row[7] or 'ER',
            sections=_charger_sections(conn, 'notion', row[0]),
        )

    if type_atome == 'methode':
        row = conn.execute(
            "SELECT id, niveau, sequence, fichier, titre, corps, "
            "       num_objectif, num_methode, ordre_sections "
            "FROM methodes WHERE id = ?", (atome_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Méthode introuvable : {atome_id!r}")
        return Atome(
            id=row[0], type_atome='methode',
            niveau=row[1], sequence=row[2], fichier=row[3],
            titre=row[4], corps=row[5] or '',
            num_objectif=row[6], num=row[7],
            ordre_sections=row[8] or 'ER',
            sections=_charger_sections(conn, 'methode', row[0]),
        )

    # v0.11.1 — fiche de résumé.
    # NB : en BDD, entite_type='fiche_resume' (et non 'fiche'). C'est volontaire :
    # côté API on reste cohérent avec le singleton du dispatcher TABLES_ATOMES
    # ('fiche'), mais côté table atome_sections on respecte le nom historique
    # utilisé par services/fiches_resume.py et services/fiches_import.py.
    #
    # v0.11.1.x — JOIN sur objectifs pour récupérer le nom de l'objectif
    # lié, utilisé en fallback dans generer_corps_fiche si le titre est
    # vide. LEFT JOIN parce qu'une fiche peut être créée sans objectif
    # (pendant l'édition) ; dans ce cas objectif_nom reste vide.
    row = conn.execute(
        "SELECT f.id, f.niveau, f.sequence, f.fichier, f.titre, "
        "       COALESCE(o.nom, '') AS objectif_nom "
        "FROM fiches_resume f "
        "LEFT JOIN objectifs o ON o.id = f.objectif_id "
        "WHERE f.id = ?", (atome_id,)
    ).fetchone()
    if not row:
        raise LookupError(f"Fiche introuvable : {atome_id!r}")
    return Atome(
        id=row[0], type_atome='fiche',
        niveau=row[1] or '', sequence=row[2] or '',
        fichier=row[3] or '',
        titre=row[4] or '',
        objectif_nom=row[5] or '',
        sections=_charger_sections(conn, 'fiche_resume', row[0]),
    )


def _charger_sections(conn: sqlite3.Connection,
                      entite_type: str,
                      entite_id: str) -> list[dict]:
    """v0.6.4 — Charge les sections d'un atome dans l'ordre.

    Retourne une liste [{'titre': str, 'items': list[str]}] où l'ordre
    de la liste est l'ordre d'affichage. Les items contiennent du LaTeX
    brut, prêt à être inséré dans le rendu sans modification.
    """
    sections_rows = conn.execute(
        "SELECT id, titre FROM atome_sections "
        "WHERE entite_type = ? AND entite_id = ? ORDER BY ordre",
        (entite_type, entite_id),
    ).fetchall()
    out = []
    for sr in sections_rows:
        items_rows = conn.execute(
            "SELECT corps FROM atome_section_items "
            "WHERE section_id = ? ORDER BY ordre",
            (sr[0],),
        ).fetchall()
        out.append({
            'titre': sr[1],
            'items': [ir[0] for ir in items_rows],
        })
    return out


def _charger_items_texte(conn: sqlite3.Connection,
                         entite_type: str,
                         entite_id: str) -> tuple[list[str], list[str]]:
    """v0.6.4 — Fonction conservée à des fins de compatibilité avec
    d'éventuels appelants externes. Renvoie maintenant deux listes vides
    (la table items_texte a été remplacée par atome_sections /
    atome_section_items). Les nouveaux appels doivent passer par
    `_charger_sections` qui rend la liste de sections du modèle universel.
    """
    return [], []


# ── 1. Détection des paquets TeX utilisés par l'atome ────────────────────────

# Certaines valeurs de MACROS_PAQUETS_EXTERNES sont des étiquettes, pas des
# paquets TeX à charger. On les filtre.
_PSEUDO_PAQUETS = frozenset({
    'tex-primitive',   # primitives TeX pures, rien à charger
    'babel-french',    # déjà couvert par \usepackage{babel}
})


# v0.8.2 — Profondeur maximale autorisée pour la récursion sur les items de
# section. Aujourd'hui les items sont des chaînes plates (profondeur 0), mais
# le commentaire historique du dataclass Atome évoque la possibilité de
# « sous-listes imbriquées, multicols, tikzpicture » dans des items dict ou
# list. Cette limite garde la fonction défensive sans masquer une éventuelle
# évolution du format : si un jour un item dépasse 4 niveaux, le code
# remonte une RecursionError explicite plutôt que de tronquer silencieusement
# le texte analysé (ce qui ferait à nouveau manquer des macros, donc
# manquer des paquets, donc casser la compilation).
_PROFONDEUR_MAX_ITEMS = 4


def _aplatir_textes(noeud, profondeur: int = 0) -> list[str]:
    r"""Aplatit récursivement un nœud d'item de section en chaînes LaTeX.

    Le format des sections est documenté dans la dataclass Atome comme
    pouvant contenir, à terme, des structures complexes : un item peut
    être une string, ou un dict (clés→strings/sous-structures), ou une
    list de sous-items.

    En pratique aujourd'hui (BDD v0.8) tous les items sont des strings,
    mais on fait la fonction robuste pour ne pas avoir à y revenir si
    le format évolue.

    Lève RecursionError si la profondeur dépasse _PROFONDEUR_MAX_ITEMS.
    Cette limite est volontaire : une structure plus profonde signalerait
    un changement de format qui doit être pris en compte explicitement
    (et pas silencieusement, ce qui pourrait à nouveau causer la
    régression v0.8 où des macros tkz dans des items n'étaient pas
    détectées comme appartenant au paquet tkz-euclide).
    """
    if profondeur > _PROFONDEUR_MAX_ITEMS:
        raise RecursionError(
            f"Profondeur d'item > {_PROFONDEUR_MAX_ITEMS} : structure "
            f"d'item plus complexe qu'attendu — vérifier que le format "
            f"des sections n'a pas évolué et adapter _aplatir_textes "
            f"(et son test associé) en conséquence."
        )
    if noeud is None:
        return []
    if isinstance(noeud, str):
        return [noeud]
    if isinstance(noeud, list):
        out: list[str] = []
        for x in noeud:
            out.extend(_aplatir_textes(x, profondeur + 1))
        return out
    if isinstance(noeud, dict):
        out = []
        for v in noeud.values():
            out.extend(_aplatir_textes(v, profondeur + 1))
        return out
    # Type inattendu (int, bool…) : ignoré, ne contient pas de LaTeX.
    return []


def _texte_complet_atome(atome: Atome) -> str:
    r"""Concatène tout le contenu LaTeX d'un atome en un seul texte.

    Inclut :
      - les champs scalaires : titre, corps, corrige, variables ;
      - le contenu de chaque section (titre + items aplatis récursivement).

    Cette concaténation est utilisée pour détecter les macros et
    environnements LaTeX réellement employés par l'atome, afin d'en
    déduire les paquets externes à charger.

    v0.8.2 (correctif) : avant cette version, seuls corps/corrige/variables
    étaient inclus. Pour les notions et méthodes (modèle universel à
    2 niveaux), le contenu LaTeX réel vit dans `sections[].items[]`,
    donc l'analyse était faite sur un texte essentiellement vide → option
    [geometrie] non détectée → tkz-base non chargé → \tkzLabelX undefined
    à la compilation. Ce bug touchait toutes les notions/méthodes
    utilisant tkz-euclide ou scratch3 dans leurs sections.
    """
    morceaux: list[str] = [
        atome.titre or '',
        atome.corps or '',
        atome.corrige or '',
        atome.variables or '',
    ]
    for sec in (atome.sections or []):
        morceaux.append(sec.get('titre', '') or '')
        for item in (sec.get('items', []) or []):
            morceaux.extend(_aplatir_textes(item))
    return '\n'.join(morceaux)


def _analyser_paquets_utilises(atome: Atome) -> set[str]:
    """Retourne l'ensemble des paquets TeX que l'atome utilise, selon l'analyse
    des macros appelées dans son texte.

    Pseudo-paquets filtrés. Ensemble brut : peut contenir des paquets déjà
    chargés par seqenseigne (filtrage en aval).
    """
    from services.paquet_parseur import (
        MACROS_PAQUETS_EXTERNES, extraire_utilisations,
    )

    texte_complet = _texte_complet_atome(atome)
    macros, envs = extraire_utilisations(texte_complet)
    noms_utilises = macros | envs

    paquets = {
        MACROS_PAQUETS_EXTERNES[n]
        for n in noms_utilises
        if n in MACROS_PAQUETS_EXTERNES
    }
    return paquets - _PSEUDO_PAQUETS


def detecter_options_paquet(conn: sqlite3.Connection, atome: Atome) -> list[str]:
    """Retourne les options à passer au paquet seqenseigne pour cet atome.

    Analyse les macros LaTeX utilisées dans le corps de l'atome et consulte
    MACROS_PAQUETS_EXTERNES pour savoir à quel paquet TeX elles appartiennent.
    """
    paquets_utilises = _analyser_paquets_utilises(atome)
    options = []
    if paquets_utilises & PAQUETS_GEOMETRIE:
        options.append('geometrie')
    if paquets_utilises & PAQUETS_SCRATCH:
        options.append('scratch')
    return options


def detecter_paquets_tex_manquants(conn: sqlite3.Connection,
                                    atome: Atome) -> list[str]:
    """Retourne la liste des paquets TeX utilisés par l'atome qui ne sont
    PAS déjà chargés par seqenseigne.

    Ces paquets devront être ajoutés au préambule via \\usepackage.

    Les paquets déjà chargés par seqenseigne sont exclus (ils seraient
    rechargés sans effet mais c'est plus propre de ne pas le faire).
    Les paquets correspondant aux options [geometrie] et [scratch] sont
    aussi exclus car ils sont chargés conditionnellement par le paquet
    lui-même via ses options.
    """
    paquets_utilises = _analyser_paquets_utilises(atome)

    # Paquets déjà chargés par le paquet lui-même (base + options)
    deja_charges = _paquets_deja_charges_par_seqenseigne(conn)
    # Paquets chargés par les options [geometrie] et [scratch]
    deja_charges |= PAQUETS_GEOMETRIE
    deja_charges |= PAQUETS_SCRATCH

    manquants = sorted(paquets_utilises - deja_charges)
    return manquants


def _paquets_deja_charges_par_seqenseigne(conn: sqlite3.Connection) -> set[str]:
    """Retourne l'ensemble des paquets TeX que **notre préambule reconstruit**
    charge déjà — pas ceux que `\\usepackage{seqenseigne}` chargerait s'il
    était utilisé en entier.

    HISTORIQUE / BUG v0.8.5 : avant ce correctif, cette fonction lisait la
    table `paquet_requirepackage` qui reflète ce que `seqenseigne.sty` charge
    en entier (~35 paquets). Or notre préambule sur mesure n'en charge que
    ~28 (PAQUETS_NOYAU + options [geometrie] et [scratch] selon l'atome).
    Les 11 paquets restants étaient marqués à tort comme « déjà chargés » et
    n'étaient donc jamais ajoutés au préambule reconstruit.

    Conséquence concrète : `xltabular` (chargé par seqenseigne complet mais
    pas par notre reconstruction) faisait planter à la compilation deux
    notions de N10 (S10/03 et S10/06) avec :

        ! LaTeX Error: Environment xltabular undefined.

    alors même que ces notions utilisent `\\begin{xltabular}` dans leur
    contenu et que `xltabular` est correctement mappé dans
    MACROS_PAQUETS_EXTERNES. Le code détectait bien que le paquet est utile,
    mais le filtrait ensuite comme « inutile car déjà chargé ».

    Le fix consiste à se baser sur la liste réelle de ce que nous chargeons,
    importée depuis `services/preambule_atome.py` qui en est l'autorité.

    Inclut les équivalences classiques (graphicx ⇆ graphics, tikz tire
    pgf+graphicx+xcolor) pour éviter les rechargements redondants.
    """
    # Import local pour éviter une dépendance circulaire au chargement
    # du module (preambule_atome importe latex_rendu_atome via Atome).
    from services.preambule_atome import (
        PAQUETS_NOYAU, _PAQUETS_GEOMETRIE, _PAQUETS_SCRATCH,
    )
    noms = (
        {nom for nom, _opts in PAQUETS_NOYAU}
        | set(_PAQUETS_GEOMETRIE)
        | set(_PAQUETS_SCRATCH)
    )
    # Équivalences classiques : éviter de recharger un paquet équivalent.
    if 'graphics' in noms:
        noms.add('graphicx')
    if 'graphicx' in noms:
        noms.add('graphics')
    # tikz tire automatiquement pgf, graphicx, xcolor.
    if 'tikz' in noms:
        noms |= {'pgf', 'graphics', 'graphicx', 'xcolor'}
    return noms


# ── 2. Résolution du thème de la séquence ─────────────────────────────────────

# v0.13.4.1 — Tri déterministe pour sélectionner LE référentiel pertinent
# d'un niveau, en remplacement du filtre `date_fin IS NULL` qui pouvait
# remonter plusieurs candidats si la base était incohérente.
#
# Préférence par état : verrouille (en usage actif pour le suivi) >
# fige (compilé et autonomisé) > valide (auto, attend figeage) > en_cours
# (en construction) > tout autre cas. À versions équivalentes, on prend
# la version la plus récente (lexico décroissant : '2025' > '2024').
#
# `fige` est inclus dans le CASE en anticipation de la v0.13.5.1 qui
# l'ajoutera au CHECK constraint. Pas de risque ici : c'est juste un
# CASE WHEN côté SQL, indépendant du CHECK.
# v0.15.3 — Ordre de priorité des états (`fige` fusionné dans
# `verrouille`, `utilise` ajouté en tête).
_REF_ORDER_BY = """
    ORDER BY
      CASE rn.etat WHEN 'utilise'    THEN 0
                   WHEN 'verrouille' THEN 1
                   WHEN 'valide'     THEN 2
                   WHEN 'en_cours'   THEN 3
                   ELSE 4 END,
      rn.version DESC
"""


def resoudre_theme(conn: sqlite3.Connection,
                   niveau: str, sequence: str) -> str:
    """Retourne la couleur de thème pour une (niveau, sequence).

    Valeurs attendues : 'nombres', 'donnees', 'grandeurs', 'geometrie',
    'algorithmique'. Retourne 'gris' en secours si la séquence est introuvable
    ou si son thème n'a pas de couleur renseignée.
    """
    row = conn.execute(f"""
        SELECT rt.couleur
        FROM referentiel_sequences rs
        JOIN referentiel_niveaux rn ON rs.referentiel_id = rn.id
        LEFT JOIN referentiel_themes rt
            ON rt.referentiel_id = rs.referentiel_id
           AND rt.code = rs.theme_code
        WHERE rn.niveau = ? AND rs.code = ?
        {_REF_ORDER_BY}
        LIMIT 1
    """, (niveau, sequence)).fetchone()

    if not row or not row[0]:
        return 'gris'
    couleur = row[0].strip()
    if couleur not in THEMES_VALIDES:
        return 'gris'
    return couleur


# ── 3. Résolution des macros CSV-dépendantes ──────────────────────────────────

# Regex pour capturer \seqObjectifGetNom{02}, \seqSequenceGetNom{}, etc.
# On capture le nom de macro et son argument principal.
_RE_GETTER_CSV = re.compile(
    r'\\(seqObjectifGetNom'
    r'|seqObjectifGetFinCycle'
    r'|seqSequenceGetNom'
    r'|seqSequenceGetNumero'
    r'|seqSequenceGetTheme'
    r'|seqThemeGetNom'
    r'|seqNiveauGetNomCourt'
    r'|seqNiveauGetNomLong'
    r'|seqConnaissanceGetNom)'
    r'\s*\{([^{}]*)\}'
)


def resoudre_macros_csv(conn: sqlite3.Connection, texte: str,
                        niveau: str, sequence: str) -> str:
    """Substitue les getters CSV-dépendants par leurs valeurs depuis la BDD.

    Si une valeur est introuvable, utilise un placeholder lisible pour que
    la compilation LaTeX ne casse pas et que l'auteur voie ce qui manque.
    """
    if not texte:
        return texte

    def _resoudre(m: re.Match) -> str:
        macro = m.group(1)
        arg = m.group(2).strip()

        if macro == 'seqObjectifGetNom':
            # v0.14.6.b.1 — Lecture v2 (objectifs) via JOIN sur partie
            # et sequence_par_niveau pour retrouver (niveau, sequence, code).
            row = conn.execute(
                "SELECT ov2.nom FROM objectifs ov2 "
                "JOIN sequence_parties      p  ON p.id  = ov2.partie_id "
                "JOIN sequences_par_niveau  sn ON sn.id = p.sequence_par_niveau_id "
                "WHERE sn.niveau = ? AND sn.sequence_code = ? AND ov2.code = ?",
                (niveau, sequence, arg),
            ).fetchone()
            return row[0] if row and row[0] else f'[OBJ-{arg}]'

        if macro == 'seqObjectifGetFinCycle':
            # v0.14.6.b.1 — Le champ `est_nouveau` n'existe pas en v2.
            # Décision validée avec Laurent : ce concept est remplacé par
            # le mécanisme des précédences inter-parties en v2 (cf.
            # `partie_precedences`). La macro retourne donc toujours 'N'
            # ("pas en fin de cycle"). À déprécier complètement quand
            # tous les paquets utilisateurs auront été mis à jour.
            # Note : l'audit v0.14.5 sur la BDD de prod a confirmé que 0
            # objectif v1 avait est_nouveau=1 (toujours la valeur par
            # défaut), donc ce changement ne modifie aucun rendu existant.
            return 'N'

        if macro == 'seqSequenceGetNom':
            # L'argument est facultatif : si vide on prend la séquence courante
            code_seq = arg or sequence
            row = conn.execute(f"""
                SELECT rs.nom FROM referentiel_sequences rs
                JOIN referentiel_niveaux rn ON rs.referentiel_id = rn.id
                WHERE rn.niveau = ? AND rs.code = ?
                {_REF_ORDER_BY}
                LIMIT 1
            """, (niveau, code_seq)).fetchone()
            return row[0] if row else f'[SEQ-{code_seq}]'

        if macro == 'seqSequenceGetNumero':
            code_seq = arg or sequence
            row = conn.execute(f"""
                SELECT rs.numero FROM referentiel_sequences rs
                JOIN referentiel_niveaux rn ON rs.referentiel_id = rn.id
                WHERE rn.niveau = ? AND rs.code = ?
                {_REF_ORDER_BY}
                LIMIT 1
            """, (niveau, code_seq)).fetchone()
            return str(row[0]) if row else f'[NUM-{code_seq}]'

        if macro == 'seqSequenceGetTheme':
            code_seq = arg or sequence
            row = conn.execute(f"""
                SELECT rs.theme_code FROM referentiel_sequences rs
                JOIN referentiel_niveaux rn ON rs.referentiel_id = rn.id
                WHERE rn.niveau = ? AND rs.code = ?
                {_REF_ORDER_BY}
                LIMIT 1
            """, (niveau, code_seq)).fetchone()
            return row[0] if row and row[0] else '[THEME]'

        if macro == 'seqThemeGetNom':
            row = conn.execute(f"""
                SELECT rt.nom FROM referentiel_themes rt
                JOIN referentiel_niveaux rn ON rt.referentiel_id = rn.id
                WHERE rn.niveau = ? AND rt.code = ?
                {_REF_ORDER_BY}
                LIMIT 1
            """, (niveau, arg)).fetchone()
            return row[0] if row else f'[TH-{arg}]'

        if macro == 'seqNiveauGetNomCourt':
            # 'N10' → '5e', 'N11' → '4e', 'N12' → '3e'
            code = arg or niveau
            mapping = {'N09': '6e', 'N10': '5e', 'N11': '4e', 'N12': '3e'}
            return mapping.get(code, f'[N-{code}]')

        if macro == 'seqNiveauGetNomLong':
            code = arg or niveau
            mapping = {
                'N09': 'Sixième', 'N10': 'Cinquième',
                'N11': 'Quatrième', 'N12': 'Troisième',
            }
            return mapping.get(code, f'[N-{code}]')

        if macro == 'seqConnaissanceGetNom':
            # arg = code de connaissance, ex '01'
            row = conn.execute(
                "SELECT titre FROM notions "
                "WHERE niveau = ? AND sequence = ? AND num_connaissance = ?",
                (niveau, sequence, arg),
            ).fetchone()
            return row[0] if row else f'[CO-{arg}]'

        # Fallback (ne devrait pas arriver vu la regex)
        return m.group(0)

    return _RE_GETTER_CSV.sub(_resoudre, texte)


# ── 4. Collecte des réécritures applicables ───────────────────────────────────

def collecter_reecritures(conn: sqlite3.Connection,
                          macros_utilisees: set[str]) -> list[str]:
    """Retourne les `contenu_atome` des macros `reecrit` en BDD.

    HISTORIQUE : Cette fonction émettait toutes les réécritures dans le
    préambule du .tex généré (avant l'arrivée du préambule sur mesure).
    Depuis v0.6.4, la résolution se fait dans `services.preambule_atome` :
    quand une définition est traversée par la fermeture transitive et que
    son statut est 'reecrit', son `contenu_atome` est émis à la place de
    `texte_complet`. Cette fonction n'est donc plus utilisée par
    `generer_tex_atome`, mais elle reste exposée pour les tests et les
    scripts de diagnostic.

    Pour simplifier, elle émet TOUTES les réécritures en statut 'reecrit'
    sans tenir compte de macros_utilisees (paramètre non lu).
    """
    rows = conn.execute("""
        SELECT nom, contenu_atome
        FROM paquet_definitions
        WHERE statut_rendu_atome = 'reecrit'
        ORDER BY nom
    """).fetchall()

    return [contenu for nom, contenu in rows if contenu]


# ── 6. Génération du corps de l'atome selon son type ──────────────────────────

def _echapper_titre_latex(titre: str) -> str:
    """Échappe les caractères LaTeX dangereux dans un titre simple.

    On ne touche pas aux backslash (les titres peuvent contenir du LaTeX
    volontaire), seulement aux caractères de contrôle manifestes.
    """
    # Pour l'instant, on fait confiance au titre tel qu'il est en BDD :
    # il a été saisi par un enseignant qui écrit du LaTeX de toute façon.
    return titre or ''


# Mapping série CSV → numéro utilisé par seqSerieExos{N}.
# Cohérent avec les branches du paquet dans \seqTitreSection (core.sty ligne 835+) :
#   0 = Révisions, 1 = Fondamentale, 2 = Avancée, 3 = Exploration.
_NUM_SERIE_PAR_CODE = {
    'fondamental': 1,
    'avancé':      2,
    'avance':      2,   # tolérance si l'accent manque quelque part
    'exploration': 3,
    'revisions':   0,
    'révisions':   0,
}


def generer_corps_exercice(atome: Atome, conn=None) -> str:
    """Produit le corps LaTeX pour un exercice isolé.

    Stratégie : on reproduit fidèlement la structure d'un livret.

    1. \\seqInitCorriges ouvre le \\newwrite vers Corriges/CorrList.tex et
       \\seqInitAnnexes fait de même pour les annexes. Normalement appelés
       par \\seqTitreLivret — qu'on saute en mode atomique.
       v0.11.6 : \\seqInitRemediation ouvre les writeouts de remédiation
       (sinon \\seqRemediation est silencieux — cf. test sur
       \\seq@remediation@active dans seqenseigne-core-exos.dtx).
    2. \\begin{seqSerieExos}{N} ouvre un multicols*{2} dans une boîte jaune.
       Le numéro N correspond à la série de l'atome (voir _NUM_SERIE_PAR_CODE).
    3. \\begin{seqExercice}[nom=...] affiche l'énoncé. La machinerie interne
       écrit l'énoncé+corrigé dans Corriges/cNeM.tex.
    4. \\end{seqSerieExos} ferme la boîte et le multicols.
    5. \\seqAfficheAnnexes puis \\seqAfficheCorriges incluent les annexes et
       corrigés en 1 colonne, pleine largeur, sur fond blanc — même mise en
       page que dans un livret. v0.11.6 : suivi de \\seqAfficheRemediations
       et \\seqAfficheCorrigesRemediation pour les sections de remédiation.

    v0.11.6 — Cadre de réponse et remédiation :
    - \\seqCadreReponse{N} émis après l'énoncé si
      atome.cadre_reponse_lignes_principal > 0.
    - \\seqRemediation{enonce}{corrige} émis après \\seqCorrige si l'atome a
      des champs remed_enonce/remed_corrige non vides. Le cadre de réponse
      de remédiation est placé à l'intérieur du premier argument de
      \\seqRemediation, à la suite de l'énoncé, si
      atome.cadre_reponse_lignes_remed > 0.
    Modèle aligné sur livret_recap_exos._generer_corps_exercice_continu.

    v0.11.6.2 — Options de \\begin{seqExercice} :
    - obj={code1, code2, ...} si conn fourni et exo lié à des objectifs
    - remediation=oui si l'exo a une remédiation (active l'affichage de
      « Remédiation p. XX » dans la boîte de titre).

    Parameters
    ----------
    atome : Atome
        L'exercice à rendre.
    conn : sqlite3.Connection or None, default None
        Si fournie, sert à interroger objectif_exos pour passer la liste
        des codes d'objectifs liés à l'exo via l'option obj=. Si None,
        on n'émet pas obj= (rétrocompatible).

    IMPORTANT : les dossiers Corriges/ et Remediation/ doivent exister dans
    le dossier de compilation (tcbverbatimwrite l'exige). C'est le rôle du
    service compilateur_pdf.py avant le lancement de pdflatex.
    """
    parties = []

    # 1. Initialisation des writeouts (normalement fait par \seqTitreLivret).
    parties.append(r'\seqInitCorriges')
    parties.append(r'\seqInitAnnexes')
    # v0.11.6 — Activer la remédiation pour le rendu atomique également.
    # Sans \seqInitRemediation, \seqRemediation et \seqAfficheRemediations
    # sont silencieuses (cf. test \ifcsname seq@remediation@active dans
    # seqenseigne-core-exos.sty).
    parties.append(r'\seqInitRemediation')

    # 1bis. Forcer l'écriture des corrigés quelle que soit la série.
    # Dans un livret, seuls les corrigés des révisions et de la série
    # fondamentale sont systématiquement écrits ; pour les séries avancée
    # et exploration, il faut passer [corriges=oui] à \seqTitreLivret.
    # On saute \seqTitreLivret en mode atomique, donc on définit directement
    # le flag interne que le paquet consulte (voir seqenseigne-core.sty
    # lignes 838 et 870).
    parties.append(r'\renewcommand{\seqCorrigesExos}{oui}')

    # 2. Variables locales à l'exercice (bloc _param.tex) — doivent être
    #    définies AVANT l'environnement seqExercice qui va les utiliser.
    if atome.variables:
        parties.append('')
        parties.append("% ── Variables de l'exercice ──")
        parties.append(atome.variables.strip())

    # 3. Numéro de l'atome dans sa série (sert de cale au compteur ExoNum)
    num_exo = atome.num or 1
    num_serie = _NUM_SERIE_PAR_CODE.get(atome.serie, 1)

    # Détection précoce de la remédiation : conditionne à la fois l'option
    # remediation=oui et l'émission du bloc \seqRemediation plus bas.
    remed_enonce = (getattr(atome, 'remed_enonce', '') or '').strip()
    remed_corrige = (getattr(atome, 'remed_corrige', '') or '').strip()
    a_remediation = bool(remed_enonce or remed_corrige)

    # 4. Ouverture de la série + exercice + corrigé
    parties.append('')
    parties.append(r'% ── Énoncé ──')
    parties.append(f'\\begin{{seqSerieExos}}{{{num_serie}}}')
    # Positionner le compteur pour que l'exercice s'affiche avec son vrai numéro
    # (\refstepcounter incrémente en entrée de seqExercice).
    parties.append(r'\setcounter{ExoNum}{' + str(max(0, num_exo - 1)) + '}')

    nom_exo = atome.titre or ''
    opts = []
    if nom_exo:
        opts.append(f'nom={{{nom_exo}}}')
    # v0.11.6.2 — Codes d'objectifs liés à l'exercice
    if conn is not None:
        codes = lire_codes_objectifs_de_exercice(conn, atome.id)
        if codes:
            opts.append('obj={' + ', '.join(codes) + '}')
    # v0.11.6.2 — remediation=oui si l'exo a une remédiation
    if a_remediation:
        opts.append('remediation=oui')
    opts_str = f'[{",".join(opts)}]' if opts else ''
    parties.append(f'\\begin{{seqExercice}}{opts_str}')
    parties.append(atome.corps.strip())

    # v0.11.6 — Cadre de réponse principal (juste après l'énoncé, avant le
    # corrigé). Émis seulement si > 0.
    lignes_princ = getattr(atome, 'cadre_reponse_lignes_principal', 0) or 0
    if lignes_princ > 0:
        parties.append(f'\\seqCadreReponse{{{int(lignes_princ)}}}')

    # Corrigé
    if atome.corrige.strip():
        parties.append(r'\seqCorrige{%')
        parties.append(atome.corrige.strip())
        parties.append('}')

    # v0.11.6 — Remédiation (paquet seqenseigne ≥ 1.0.5-dev).
    # Émise après \seqCorrige (peu importe l'ordre relatif côté paquet,
    # \seqCorrige et \seqRemediation accumulent dans deux streams distincts).
    # On émet \seqRemediation que si l'énoncé OU le corrigé de remédiation
    # est non vide, avec fallback \emph{...} pour le côté manquant — modèle
    # identique à livret_recap_exos._generer_corps_exercice_continu.
    if a_remediation:
        enonce_complet = remed_enonce
        lignes_remed = getattr(atome, 'cadre_reponse_lignes_remed', 0) or 0
        if lignes_remed > 0:
            enonce_complet = (enonce_complet + '\n'
                              + f'\\seqCadreReponse{{{int(lignes_remed)}}}')
        if not enonce_complet.strip():
            enonce_complet = r'\emph{Énoncé de remédiation non rédigé.}'
        corrige_remed = remed_corrige or r'\emph{Corrigé de remédiation non rédigé.}'
        parties.append(r'\seqRemediation{%')
        parties.append(enonce_complet)
        parties.append('}{%')
        parties.append(corrige_remed)
        parties.append('}')

    parties.append(r'\end{seqExercice}')
    parties.append(r'\end{seqSerieExos}')

    # 5. Affichage des annexes, corrigés et sections remédiation
    parties.append('')
    parties.append(r'% ── Annexes, corrigés et remédiation ──')
    parties.append(r'\seqAfficheAnnexes')
    parties.append(r'\seqAfficheCorriges')
    # v0.11.6 — Sections remédiation (énoncés puis corrigés). Si
    # \seqInitRemediation n'a pas été appelée, ces deux macros ne font rien
    # (test sur \seq@remediation@active dans seqenseigne-core-exos.sty) —
    # ici on l'a appelée, donc elles affichent les blocs accumulés.
    parties.append(r'\seqAfficheRemediations')
    parties.append(r'\seqAfficheCorrigesRemediation')

    return '\n'.join(parties)


def _rendu_sections(atome: Atome) -> str:
    r"""v0.6.4 — Construit le bloc LaTeX des sections d'un atome.

    Dans un livret seqenseigne, les sections (Exemples, Remarques,
    Conséquences, Démonstration, Démonstration de la réciproque,
    Propriétés, etc.) sont placées **entre** la fermeture du 2e argument
    et \end{seqNotion}/\end{seqMethode}. L'environnement utilise
    \tcblower (voir seqenseigne-core.sty ligne 778) pour séparer cette
    zone basse du corps principal.

    Modèle universel à 2 niveaux (introduit en v0.6.4) : chaque section
    a un titre libre et une liste d'items. L'ordre de la liste
    `atome.sections` détermine l'ordre d'affichage.

    Chaque section est rendue avec un \underline{titre}: \newline suivi
    d'un seqColItem à 1 colonne, même avec un seul item — uniformité
    décidée pour les conséquences inline.
    """
    if not atome.sections:
        return ''

    blocs = []
    for sec in atome.sections:
        titre = (sec.get('titre') or '').strip()
        items = sec.get('items') or []
        if not titre and not items:
            continue
        lignes = [fr'\underline{{{titre}}} : \newline',
                  r'\begin{seqColItem}[nbCols=1]']
        for item in items:
            lignes.append(r'\item ' + (item or '').strip())
        lignes.append(r'\end{seqColItem}')
        blocs.append('\n'.join(lignes))

    return '\n'.join(blocs)


# Alias rétrocompatible : du code interne du fichier appelle encore
# _sections_exemples_remarques (cf. generer_corps_notion / generer_corps_methode).
def _sections_exemples_remarques(atome: Atome) -> str:
    return _rendu_sections(atome)


def generer_corps_notion(atome: Atome,
                         inclure_init_annexes: bool = True) -> str:
    r"""Produit le corps LaTeX pour une notion isolée.

    La signature du paquet est \begin{seqNotion}{titre}{corps}. Le numéro
    est calé par \refstepcounter ; on initialise NotionNum pour qu'il
    reflète le numéro réel dans la séquence.

    Si la notion a des exemples ou des remarques, ils sont insérés entre
    la fermeture du 2e argument et \end{seqNotion} pour occuper la zone
    basse (\tcblower) de la boîte.

    Comme pour seqMethode, le `corps` finit dans un \newtcolorbox via
    pgfkeys ; on compresse les blocs de 2+ lignes vides pour éviter
    un \par parasite qui ferait planter pgfkeys.

    v0.9.1 — On encadre par \seqInitAnnexes / \seqAfficheAnnexes même
    quand la notion n'utilise pas \seqAnnexe. Coût visuel : zéro
    (\seqAfficheAnnexes inclut AnnList.tex uniquement si AnnexeNum > 0,
    cf. seqenseigne-core.dtx). Bénéfice : si la notion contient un
    \seqAnnexe (cas observé sur N11/S04 méthodes), le \newwrite\annfile
    est ouvert, ce qui évite un « Undefined control sequence » fatal
    sur \annfile dans \immediate\write\annfile.

    Parameters
    ----------
    inclure_init_annexes : bool, default True
        Si True (rendu unitaire), encadre par \\seqInitAnnexes /
        \\seqAfficheAnnexes (comportement v0.9.1). Si False (rendu agrégé,
        ex. livret recap cours), n'émet PAS ces macros : l'appelant doit
        alors les placer une seule fois en début/fin de document. C'est
        nécessaire car \\seqInitAnnexes appelle \\newwrite, et TeX limite
        à 16 streams ouverts simultanément ; émettre 122 cycles dans un
        livret agrégé déclenche « No room for a new \\write ».
    """
    parties = []
    if inclure_init_annexes:
        # v0.9.1 — \seqInitAnnexes ouvre \newwrite\annfile (no-op visuel
        # si la notion n'a aucun \seqAnnexe, voir docstring).
        parties.append(r'\seqInitAnnexes')
    num_str = (atome.num_connaissance or '1').lstrip('0') or '1'
    # Initialiser à num-1 car \refstepcounter incrémente en entrée
    parties.append(
        r'\setcounter{NotionNum}{' + str(max(0, int(num_str) - 1)) + '}'
    )
    parties.append('')
    titre = _echapper_titre_latex(atome.titre)
    corps = _compresser_lignes_vides_corps(atome.corps.strip())
    parties.append(f'\\begin{{seqNotion}}{{{titre}}}{{{corps}}}')
    sections = _sections_exemples_remarques(atome)
    if sections:
        parties.append(sections)
    parties.append(r'\end{seqNotion}')
    if inclure_init_annexes:
        # v0.9.1 — \seqAfficheAnnexes ferme \annfile et inclut AnnList.tex
        # ssi AnnexeNum > 0 (sinon no-op).
        parties.append(r'\seqAfficheAnnexes')
    return '\n'.join(parties)


def generer_corps_methode(atome: Atome,
                          inclure_init_annexes: bool = True) -> str:
    r"""Produit le corps LaTeX pour une méthode isolée.

    Signature : \begin{seqMethode}{titre}{corps}. Numéro calé par compteur.
    Exemples et remarques : même traitement que pour notion, insérés dans
    la zone basse de la boîte.

    Précaution importante : le `corps` est passé tel-quel comme 2e argument
    à \begin{seqMethode}, qui en interne le donne à \begin{boitePaleBreakFitHeight}
    — un \newtcolorbox. tcolorbox utilise pgfkeys pour parser ses options
    et sa machinerie n'aime pas les `\par` (lignes vides) à l'intérieur
    d'un argument :

        ! Paragraph ended before \pgfkeys@addpath was complete.

    Si l'enseignant a mis des lignes vides pour aérer son code source, on
    les compresse à 1 maximum — ce qui évite le \par sans changer la
    mise en page (LaTeX traite "\n" et "\n\n\n" comme un simple espace
    inter-mot quand il n'y a pas de \par).

    v0.9.1 — Même fix que pour generer_corps_notion : \seqInitAnnexes
    et \seqAfficheAnnexes encadrent le corps. Cas concret qui motivait
    le fix : N11/S04/Méthode 01 et 02 (« Déterminer si un nombre entier
    est premier » et « Décomposer en produit de facteurs premiers »)
    utilisent \seqAnnexe pour insérer un algorithme en annexe ; sans
    \seqInitAnnexes, le \immediate\write\annfile dans \seqAnnexe plante
    avec « Undefined control sequence » sur \annfile.

    Parameters
    ----------
    inclure_init_annexes : bool, default True
        Cf. generer_corps_notion. Passer False pour le rendu agrégé
        (livret recap cours), où l'appelant gère un cycle init/affiche
        unique en début/fin de document pour éviter « No room for a
        new \\write ».
    """
    parties = []
    if inclure_init_annexes:
        # v0.9.1 — Init annexes (no-op visuel si la méthode n'utilise pas
        # \seqAnnexe, voir generer_corps_notion docstring).
        parties.append(r'\seqInitAnnexes')
    if atome.num is not None:
        parties.append(
            r'\setcounter{MethodeNum}{' + str(max(0, atome.num - 1)) + '}'
        )
    parties.append('')
    titre = _echapper_titre_latex(atome.titre)
    corps = _compresser_lignes_vides_corps(atome.corps.strip())
    parties.append(f'\\begin{{seqMethode}}{{{titre}}}{{{corps}}}')
    sections = _sections_exemples_remarques(atome)
    if sections:
        parties.append(sections)
    parties.append(r'\end{seqMethode}')
    if inclure_init_annexes:
        # v0.9.1 — Affichage des annexes (no-op si AnnexeNum == 0).
        parties.append(r'\seqAfficheAnnexes')
    return '\n'.join(parties)


def _compresser_lignes_vides_corps(texte: str) -> str:
    r"""Compresse les blocs de 2+ lignes vides consécutives en 1.

    Identique à services.preambule_atome._compresser_lignes_vides mais
    redéfini ici pour éviter une dépendance circulaire à l'import.

    Une ligne vide isolée (1 seule) est conservée pour la lisibilité et
    n'engendre PAS de \par (LaTeX a besoin d'AU MOINS deux retours à la
    ligne consécutifs sans contenu pour produire un \par). On supprime
    donc seulement les paquets de 2+ vides qui, eux, produisent un \par.
    """
    if not texte:
        return texte
    lignes = [l if l.strip() else '' for l in texte.split('\n')]
    out = []
    n_vides = 0
    for l in lignes:
        if l == '':
            n_vides += 1
            if n_vides == 1:
                out.append(l)
        else:
            n_vides = 0
            out.append(l)
    return '\n'.join(out)


def generer_corps_fiche(atome: Atome) -> str:
    r"""v0.11.1 — Produit le corps LaTeX pour une fiche de résumé isolée.

    Structure :
      \seqTitreSection{<titre de la fiche>}
      \begin{seqBoiteContenuFlashcard}[titre=<titre section 1>]
        <items section 1, séparés par newline>
      \end{seqBoiteContenuFlashcard}
      ...
      \begin{seqBoiteFillContenuFlashcard}\end{seqBoiteFillContenuFlashcard}

    Note v0.11.1.1 — convention de nommage : on émet les environnements
    sous leur nom canonique tel qu'indexé dans la table paquet_definitions
    (préfixe `seq` cohérent avec seqNotion / seqMethode / seqExercice). Un
    ancien `.tex` du livret annuel utilisait les noms courts sans préfixe
    (`boiteContenuFlashcard`), mais ce livret n'avait pas été recompilé
    depuis la normalisation du paquet — les noms publics actuels sont
    bien préfixés `seq`.

    Choix de design (cf. cadrage v0.11.1 avec Laurent) :
      * `\seqTitreSection{...}` reçoit le titre tel quel — pas de machinerie
        \seqBoiteTitreFlashcard{<code>}{...} qui irait chercher des infos
        dans les .dbtex (volontairement écarté pour rester atomique).
      * Le `\begin{seqBoiteFillContenuFlashcard}` final est ajouté
        systématiquement — comble l'espace résiduel sur la page si la fiche
        est plus courte qu'attendu, et garantit un rendu cohérent avec ce
        que sera la même fiche dans un livret annuel.
      * Les `\acompleter{...}` éventuels présents dans le contenu produisent
        des trous soulignés (version élève par défaut). La macro est
        définie par le préambule (cf. preambule_atome.py).

    Parameters
    ----------
    atome : Atome
        Atome de type 'fiche' (titre + sections).

    Returns
    -------
    str
        Corps LaTeX complet du document, sans préambule ni \\begin{document}.
    """
    parties: list[str] = []
    # v0.11.1.x — Fallback titre depuis l'objectif lié.
    # Si le champ titre de la fiche est vide ET qu'elle est liée à un
    # objectif, on utilise le nom de l'objectif comme titre LaTeX. Si
    # pas d'objectif lié, le titre reste vide (le \seqTitreSection
    # produit un titre vide, c'est volontaire — l'utilisateur peut
    # encore créer la fiche sans objectif pendant l'édition).
    titre_brut = (atome.titre or '').strip()
    if not titre_brut and atome.objectif_nom:
        titre_brut = atome.objectif_nom
    titre = _echapper_titre_latex(titre_brut)
    parties.append(f'\\seqTitreSection{{{titre}}}')

    for sec in atome.sections or []:
        titre_sec = (sec.get('titre') or '').strip()
        items = sec.get('items') or []
        # On ne saute pas une section vide de titre (l'utilisateur peut
        # vouloir un bloc anonyme), mais on saute si à la fois titre vide
        # ET aucun item (cohérent avec _rendu_sections pour notion/méthode).
        if not titre_sec and not items:
            continue
        # seqBoiteContenuFlashcard : la clé `titre` accepte le titre brut ;
        # si vide, on génère sans la clé pour laisser le paquet utiliser
        # son rendu par défaut (boîte sans bandeau).
        if titre_sec:
            parties.append(
                f'\\begin{{seqBoiteContenuFlashcard}}[titre={titre_sec}]'
            )
        else:
            parties.append(r'\begin{seqBoiteContenuFlashcard}')
        # Items concaténés par newline (cohérent avec le format saisi
        # dans l'atelier fiche : un item = un paragraphe LaTeX libre).
        for item in items:
            t = (item or '').strip()
            if t:
                parties.append(t)
        parties.append(r'\end{seqBoiteContenuFlashcard}')

    # Boîte fill finale — même quand 0 sections (cas dégénéré : fiche
    # créée sans contenu, le fill évite une page vide insolite).
    parties.append(r'\begin{seqBoiteFillContenuFlashcard}\end{seqBoiteFillContenuFlashcard}')

    return '\n'.join(parties)


def generer_corps(atome: Atome, conn=None) -> str:
    """Dispatch selon le type d'atome.

    v0.11.6.2 : `conn` optionnel — propagé à generer_corps_exercice pour
    récupérer les codes d'objectifs liés. Sans conn, le rendu fonctionne
    quand même mais sans option obj= dans la boîte de titre.
    """
    if atome.type_atome == 'exercice':
        return generer_corps_exercice(atome, conn=conn)
    if atome.type_atome == 'notion':
        return generer_corps_notion(atome)
    if atome.type_atome == 'methode':
        return generer_corps_methode(atome)
    if atome.type_atome == 'fiche':
        return generer_corps_fiche(atome)
    raise ValueError(f"type_atome inconnu : {atome.type_atome!r}")


# ── 7. Assemblage final ──────────────────────────────────────────────────────

def generer_tex_atome(conn: sqlite3.Connection,
                      type_atome: str, atome_id: str,
                      racine_sources: Path | None = None,
                      tikz_libraries: list[str] | None = None,
                      tblr_libraries: list[str] | None = None) -> str:
    """Génère le fichier .tex complet pour un atome isolé.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion à la BDD seqenseigne.
    type_atome : {'exercice', 'notion', 'methode', 'fiche'}
    atome_id : str
        Identifiant opaque de l'atome en BDD.
    racine_sources : Path, optional
        Conservé pour compatibilité de signature avec les appelants
        existants. **Ignoré depuis v0.10** : le mécanisme de fichier
        NXX_SYY_params.tex partagé par séquence a été supprimé (voir le
        docstring du module). À retirer lorsque tous les appelants auront
        été nettoyés.
    tikz_libraries : list[str], optional
        v0.8.5 — Liste des bibliothèques tikz à charger inconditionnellement
        via `\\usetikzlibrary{...}` dans le préambule. Sert de filet de
        sécurité pour les bibliothèques utilisées via styles/clés non
        détectables par analyse de macros (ex. `\\node[decision]` →
        shapes.geometric, `>=Latex` → arrows.meta). Si None, aucune
        bibliothèque n'est ajoutée par ce mécanisme. Dans le pipeline
        normal, l'appelant lit la valeur depuis `Configuration.tikz_libraries()`
        et la passe ici.
    tblr_libraries : list[str], optional
        v0.9.1 — Liste des bibliothèques tabularray à charger via
        `\\UseTblrLibrary{...}`. Pendant frontal exact de tikz_libraries
        pour les fonctionnalités tabularray qui requièrent une lib
        chargée explicitement (booktabs pour \\toprule, varwidth pour
        `measure=`). Lue par l'appelant via Configuration.tblr_libraries().

    Returns
    -------
    str
        Contenu .tex complet (documentclass + préambule + document).
    """
    atome = charger_atome(conn, type_atome, atome_id)

    # 1. Options du paquet selon les macros utilisées
    options = detecter_options_paquet(conn, atome)

    # 1bis. Paquets TeX externes utilisés par l'atome que seqenseigne ne charge pas
    paquets_manquants = detecter_paquets_tex_manquants(conn, atome)

    # 2. Thème de la séquence
    theme = resoudre_theme(conn, atome.niveau, atome.sequence)

    # 3. Résolution des macros CSV dans tous les champs textuels
    atome.corps = resoudre_macros_csv(conn, atome.corps,
                                       atome.niveau, atome.sequence)
    atome.corrige = resoudre_macros_csv(conn, atome.corrige,
                                         atome.niveau, atome.sequence)
    atome.variables = resoudre_macros_csv(conn, atome.variables,
                                           atome.niveau, atome.sequence)

    # 4. Corps de l'atome
    corps_tex = generer_corps(atome, conn=conn)

    # 5. Préambule sur mesure : fermeture transitive des macros effectivement
    # utilisées par l'atome, au lieu de \usepackage{seqenseigne} qui chargerait
    # ~110 paquets LaTeX. Gain typique : facteur 2-3 sur le temps de compilation.
    from services.paquet_parseur import extraire_utilisations
    texte_atome = '\n'.join([
        atome.corps or '', atome.corrige or '', atome.variables or '',
        corps_tex,
    ])
    macros_atome, envs_atome = extraire_utilisations(texte_atome)
    preambule = construire_preambule(
        conn, atome.type_atome, macros_atome, envs_atome,
        options_atome=options,
        paquets_tex_supplementaires=paquets_manquants,
        tikz_libraries=tikz_libraries,
        tblr_libraries=tblr_libraries,
    )

    # ── Assemblage ────────────────────────────────────────────────────────────

    lignes: list[str] = []
    lignes.append(r'%% Document généré pour rendu atomique — ne pas éditer à la main')
    lignes.append(f'%% Atome : {atome.type_atome} {atome.niveau}/{atome.sequence} — '
                  f'{atome.fichier or atome.id}')
    lignes.append(f'%% Préambule sur mesure : {preambule.nb_definitions_emises} '
                  f'définitions inlinées, {len(preambule.paquets_externes)} paquets externes')
    lignes.append('')
    lignes.append(r'\documentclass[11pt,a4paper]{article}')
    lignes.append('')
    lignes.append(preambule.texte)
    lignes.append('')

    lignes.append(r'%% Thème de la séquence')
    lignes.append(f'\\seqSetColorsTheme{{{theme}}}')
    lignes.append(f'\\seqSetCodeNiveau{{{atome.niveau}}}')
    lignes.append(f'\\seqSetCodeSequence{{{atome.sequence}}}')
    lignes.append('')

    lignes.append(r'\begin{document}')
    lignes.append('')
    # \seqCreeCompteurs fait des \renewcommand{\theHExoNum}{...} et autres
    # \theHxxx, qui sont normalement créés par hyperref (qu'on ne charge pas
    # dans le préambule sur mesure pour des raisons de performance). On
    # fournit donc des \providecommand pour que les \renewcommand qui suivent
    # ne plantent pas. Si hyperref est néanmoins chargé (par un paquet
    # supplémentaire ou via les params_file), \providecommand est silencieux.
    lignes.append(r'%% Fallback pour les \theHxxx normalement définis par hyperref.')
    lignes.append(r'\providecommand{\theHExoNum}{\theExoNum}')
    lignes.append(r'\providecommand{\theHNotionNum}{\theNotionNum}')
    lignes.append(r'\providecommand{\theHMethodeNum}{\theMethodeNum}')
    lignes.append(r'\providecommand{\theHDefinitionNum}{\theDefinitionNum}')
    lignes.append(r'\providecommand{\theHProprieteNum}{\theProprieteNum}')
    lignes.append('')
    # Le paquet définit \seqCreeCompteurs qui crée les compteurs dont se
    # servent les environnements (SerieExosNum, ExoNum, NotionNum, MethodeNum…).
    # En usage livret, il est appelé par \seqTitreLivret ; en mode atomique,
    # où on saute cette macro, on doit l'appeler explicitement.
    lignes.append(r'\seqCreeCompteurs')
    lignes.append('')
    lignes.append(corps_tex)
    lignes.append('')
    lignes.append(r'\end{document}')

    return '\n'.join(lignes)


# ─────────────────────────────────────────────────────────────────────────────
# v0.14.2 — Dispatch unifié de génération .tex pour tous les types d'atomes.
# ─────────────────────────────────────────────────────────────────────────────

def generer_tex_par_type(conn: sqlite3.Connection,
                         type_atome: str, atome_id: str,
                         racine_sources: Path | None = None,
                         tikz_libraries: list[str] | None = None,
                         tblr_libraries: list[str] | None = None) -> str:
    """Génère le .tex d'un atome quel que soit son type, en dispatchant
    vers le bon générateur interne.

    Cette fonction sert de point d'entrée unique aux routes API
    `/api/atomes/<type>/<id>/...`. Elle masque la divergence
    historique entre :

      - `generer_tex_atome` (services.latex_rendu_atome) pour les 4
        types « atome classique » (exercice, notion, methode, fiche),
        qui partage le pipeline pédagogique (titre, série, objectif,
        boîtes flashcard, etc.) ;
      - `generer_tex_carte` (services.render_carte) pour les cartes
        d'automatisme, qui ont un format A8 spécifique recto/verso et
        un mécanisme propre de variables xint préambule.

    Du point de vue de l'appelant (routes), tous les types se
    comportent désormais de la même manière :

        tex = generer_tex_par_type(conn, type_atome, atome_id, ...)
        # → str, ou
        # → LookupError si atome introuvable
        # → ValueError si type_atome inconnu

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion BDD.
    type_atome : str
        L'un de : 'exercice', 'notion', 'methode', 'fiche', 'carte'.
    atome_id : str
        Id BDD de l'atome.
    racine_sources, tikz_libraries, tblr_libraries
        Paramètres forwardés à `generer_tex_atome` pour les 4 types
        classiques. Ignorés pour 'carte' (le générateur de carte a
        son propre préambule autonome).

    Returns
    -------
    str
        Le .tex prêt à compiler.

    Raises
    ------
    ValueError
        Si type_atome n'est pas dans TYPES_ATOMES_TOUS.
    LookupError
        Si l'atome n'existe pas en BDD. Pour les cartes,
        CarteIntrouvable est automatiquement reconverti en LookupError
        pour homogénéité du contrat des routes.
    """
    if type_atome not in TYPES_ATOMES_TOUS:
        raise ValueError(
            f"type_atome inconnu : {type_atome!r}. "
            f"Valeurs attendues : {sorted(TYPES_ATOMES_TOUS)}"
        )

    if type_atome == 'carte':
        # Import local pour éviter une dépendance circulaire au
        # chargement du module (render_carte ne dépend pas de
        # latex_rendu_atome aujourd'hui, mais on garde la fragilité
        # minimale).
        from services.render_carte import generer_tex_carte
        try:
            return generer_tex_carte(conn, atome_id)
        except Exception as e:
            # Homogénéisation : les services render_carte / cartes_automatisme
            # lèvent CarteIntrouvable (sous-classe de CarteErreur). Pour les
            # routes API unifiées, on remonte un LookupError standard qui se
            # traduit en 404 côté HTTP (cf. routes/rendu_atome.py).
            #
            # On ne capture pas tout (Exception) à l'aveugle : on filtre par
            # nom de classe pour ne convertir que CarteIntrouvable / CarteErreur,
            # et on laisse remonter ce qui n'est pas une erreur métier
            # (sqlite3.OperationalError, KeyboardInterrupt, etc.).
            nom = type(e).__name__
            if nom in ('CarteIntrouvable', 'CarteErreur'):
                raise LookupError(str(e)) from e
            raise

    # 4 types classiques : délégation à generer_tex_atome.
    return generer_tex_atome(
        conn, type_atome, atome_id,
        racine_sources=racine_sources,
        tikz_libraries=tikz_libraries,
        tblr_libraries=tblr_libraries,
    )

