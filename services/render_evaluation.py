"""services/render_evaluation.py — v0.13.5.3

Génération du .tex complet d'une évaluation depuis la BDD.

Pipeline (calqué sur services/latex_rendu_atome.py::generer_tex_atome) :
  1. Lecture de l'éval, de ses exos (avec champs métier), de ses objectifs
  2. Construction des sections .tex (titre, barème, objectifs, exos, fin)
  3. Détection des macros/envs utilisés → fermeture transitive du préambule
  4. Assemblage documentclass + préambule + body

Conventions visuelles (décisions Laurent v0.13.5.3, fix v0.13.5.5, v0.13.5.6) :
  - Init :    \\seqInitCorrigesEval (v0.13.5.6) émis avant
              \\seqTitreEval pour allouer le canal \\corrfileeval.
              Le paquet a été refactoré pour encapsuler l'allocation
              \\newwrite\\corrfileeval dans cette macro publique
              (cf. seqenseigne-core-eval.sty v0.13.5.6+) au lieu d'un
              top-level non indexé par la fermeture transitive.
  - Titre :   \\seqTitreEval[titre=..., etab={\\ldots}, classe={\\dots}]
              (theme= absent → la macro applique son défaut). Les
              valeurs etab/classe sont des placeholders non vides : la
              macro \\seqTitreEval requiert des tokens non vides pour
              ces clés à cause de l'expansion \\eue dans CorrList.tex
              (cf. _section_titre pour le détail).
  - Barème :  seqEvalBareme avec lignes « Exercice I & 4 points \\\\ »
              en chiffres romains (compteur Python interne). Item
              « langue française » émis SI champ BDD non vide ET
              mode_notation != 'criteres'.
  - Objectifs : seqEvalObjectifs avec code « S01.Obj. 02 »
                (séquence + numéro court)
  - Exos :    seqEvalExercice[titre=..., bareme=...] ; énoncé inséré
              tel quel (déjà du LaTeX prêt) ; \\seqEvalCorrigeExo{...}
              à l'intérieur (toujours émis, avec marque par défaut si
              corrigé BDD vide).
  - Corrigé final : \\seqEvalAfficheCorriges (toujours appelé ; la macro
                    gère elle-même un éventuel cas « rien à afficher »).

Cf. doc/finalisation_paquet_v0_13_5_2.md pour le contrat des macros et
environnements (paquet seqenseigne-core-eval).
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any

from services.latex_rendu_atome import (
    charger_atome,
    resoudre_macros_csv,
    detecter_options_paquet,
    detecter_paquets_tex_manquants,
)
from services.paquet_parseur import extraire_utilisations
from services.preambule_atome import construire_preambule
from services import evaluations as svc_eval


# ── Helpers ────────────────────────────────────────────────────────────────────


def _romain(n: int) -> str:
    """Conversion entier → chiffres romains. Cible : numéros d'exos d'une
    éval, donc valeurs typiquement entre 1 et 10, jamais > 50."""
    if n < 1:
        return ''
    pairs = [
        (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
        (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
        (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'),
        (1, 'I'),
    ]
    out = []
    for val, sym in pairs:
        while n >= val:
            out.append(sym)
            n -= val
    return ''.join(out)


def _label_objectif_court(o: dict) -> str:
    """Construit le code court d'un objectif pour le tableau d'objectifs
    du PDF : « S01.Obj. 02 » (décision Q4 Laurent).

    L'objectif vient de svc_eval.lister_objectifs_evaluation qui expose
    `sequence_code`, `partie_numero`, `code`. On utilise sequence_code +
    code, en formatant le code sur 2 chiffres si numérique.
    """
    sequence_code = o.get('sequence_code') or ''
    code = o.get('code') or ''
    # Si le code est numérique, on le passe sur 2 chiffres
    if code.isdigit():
        code = code.zfill(2)
    return f"{sequence_code}.Obj. {code}".strip('.')


def _bareme_exo_str(eb: dict, mode_notation: str) -> str:
    """Construit la chaîne « 4 points » à passer à `bareme=` de
    seqEvalExercice. Dépend du type_format et du mode_notation."""
    if mode_notation == 'criteres' or mode_notation == 'aucun':
        return ''  # pas de barème en mode critères ou aucun
    tf = (eb.get('type_format') or 'standard')
    if tf == 'qcm':
        # Pour un QCM, on totalise OK + partiel + KO ? Non : c'est la note max
        # qui est généralement OK seul (« 1 point » par bonne réponse complète).
        # Le « 4 points » du PDF de référence correspond visiblement au total
        # « tous corrects → 4 points ». Mais le scoring est variable.
        # Décision : afficher juste bareme_qcm_ok comme valeur affichée du
        # barème global (c'est la note max d'une question, multipliée par
        # le nombre de questions implicite à la lecture du PDF).
        # NB : selon le PDF, le barème indiqué dans seqEvalBareme est le
        # TOTAL de l'exo (« 4 points »). Pour un QCM, ce total est mal
        # déductible. On expose donc bareme_qcm_ok faute de mieux et on
        # documente côté UI que pour les QCM, ce barème global n'est qu'une
        # indication.
        pts = eb.get('bareme_qcm_ok')
    else:
        pts = eb.get('bareme_points')

    if pts is None:
        return ''
    # Format : « 4 points » ou « 1 point »
    p = float(pts)
    if abs(p - 1.0) < 1e-9:
        return '1 point'
    if p == int(p):
        return f"{int(p)} points"
    return f"{p:g} points"


def _bareme_langue_str(item_langue: Any, mode_notation: str) -> str:
    """Lit le champ item_langue_francaise (dict {'points': N}, déjà
    parsé par lire_evaluation) et renvoie soit la chaîne de barème
    pour la ligne dédiée, soit '' si la ligne ne doit pas être émise.

    Décision Q8 Laurent : on omet en mode 'criteres' ou si le champ
    est None/vide.
    """
    if mode_notation == 'criteres':
        return ''
    if not item_langue:
        return ''
    # lire_evaluation retourne un dict (JSON déjà parsé par
    # _row_vers_dict_evaluation). Tolérance pour le cas où on aurait
    # accidentellement une string : on retombe sur ses pieds.
    if isinstance(item_langue, str):
        try:
            import json
            item_langue = json.loads(item_langue)
        except (ValueError, TypeError):
            return ''
    if not isinstance(item_langue, dict):
        return ''
    pts = item_langue.get('points')
    if pts is None:
        return ''
    try:
        p = float(pts)
    except (ValueError, TypeError):
        return ''
    # v0.16.3 — L'item « langue française » est OPTIONNEL. Un total de 0 point
    # signifie « item désactivé » : on n'émet pas la ligne de barème. (À la
    # différence d'un exercice, qui est explicitement ajouté et dont un barème
    # à 0 est une erreur de validation — cf. _valider_bareme_exo.)
    if abs(p) < 1e-9:
        return ''
    if abs(p - 1.0) < 1e-9:
        return '1 point'
    if p == int(p):
        return f"{int(p)} points"
    return f"{p:g} points"


# ── Sections du .tex ───────────────────────────────────────────────────────────


def _section_titre(ev: dict) -> str:
    """Émet \\seqInitCorrigesEval puis \\seqTitreEval avec titre,
    etab=\\ldots, classe=\\dots, sans thème.

    Pourquoi \\seqInitCorrigesEval avant \\seqTitreEval (v0.13.5.6) :
    ---------------------------------------------------------------
    La macro \\seqTitreEval (paquet seqenseigne-core-eval.sty) ouvre
    le canal \\corrfileeval pour écrire dans CorrList.tex via :
        \\immediate\\openout\\corrfileeval=CorrList.tex

    Or \\corrfileeval est alloué par \\newwrite\\corrfileeval dans
    seqenseigne-core.sty. Tant qu'on chargeait le paquet entier via
    \\usepackage{seqenseigne}, l'allocation top-level passait. Avec
    le préambule auto-construit par fermeture transitive de
    services/preambule_atome.py, les \\newwrite top-level ne sont pas
    indexés (le parser de paquet ne les reconnaît pas comme des
    « définitions ») et l'allocation est perdue, provoquant
    « Undefined control sequence » sur \\corrfileeval.

    À partir de v0.13.5.6, le paquet expose une nouvelle macro
    publique \\seqInitCorrigesEval qui encapsule l'allocation
    (pendant exact de \\seqInitCorriges et \\seqInitAnnexes pour les
    autres canaux d'écriture). Le générateur l'appelle explicitement
    en tête de body — ainsi la fermeture transitive embarque
    naturellement la définition (puisque \\seqInitCorrigesEval est
    une \\newcommand correctement indexée) et l'allocation TeX
    s'effectue à l'exécution.

    Pourquoi etab={\\ldots} et classe={\\dots} (et pas vides) :
    -------------------------------------------------------------
    La macro \\seqTitreEval utilise \\eue{} (alias de
    \\expandafter\\unexpanded\\expandafter) sur ces valeurs pour les
    transporter intactes vers CorrList.tex via \\write — c'est ce qui
    permet aux macros saisies par l'enseignant de ne pas s'expanser
    prématurément. Or \\expandafter\\unexpanded\\expandafter ne tolère
    pas un argument vide (l'expansion bute sur l'accolade fermante
    juste derrière).

    En passant un token non vide (ici les ellipses \\ldots et \\dots),
    on respecte le contrat de la macro tout en produisant un placeholder
    visuel discret « … - … » à droite de la boîte de titre. Une
    variante B livrera plus tard des champs etab/classe saisissables
    dans l'UI éval.
    """
    titre = (ev.get('titre') or '').strip() or 'Évaluation'
    # Échapper les caractères qui posent problème dans une valeur key=value
    # de \pgfkeys (utilisé par seqTitreEval) : virgule et crochet fermant.
    # On encadre par accolades pour permettre la virgule.
    return (
        '\\seqInitCorrigesEval\n'
        '\\seqTitreEval[\n'
        f'    titre={{{titre}}},\n'
        '    etab={\\ldots},\n'
        '    classe={\\dots}\n'
        ']\n'
    )


def _section_bareme(exos: list[dict], mode_notation: str,
                    item_langue: str) -> str:
    """Émet l'environnement seqEvalBareme avec :
    - une ligne par exo numéroté en romain
    - une ligne « Présentation et usage de la langue française & X points »
      en fin SI item_langue rempli ET mode != 'criteres'

    En mode 'criteres' ou 'aucun', les colonnes points peuvent être
    vides ; on émet quand même la liste des exercices (utile comme
    sommaire) avec une chaîne vide à droite si pas de points.
    """
    lignes = []
    for idx, eb in enumerate(exos, start=1):
        rom = _romain(idx)
        bareme = _bareme_exo_str(eb, mode_notation)
        lignes.append(f"    Exercice {rom} & {bareme} \\\\")

    # Item langue française (conditionnel)
    bl = _bareme_langue_str(item_langue, mode_notation)
    if bl:
        lignes.append(
            f"    Présentation et usage de la langue française & {bl} \\\\"
        )

    if not lignes:
        # Cas pathologique : aucun exo et pas de langue. On émet une ligne
        # bidon pour ne pas casser l'environnement tabularray qui exige
        # au moins une ligne.
        lignes.append("    (aucun élément au barème) & \\\\")

    return (
        '\\begin{seqEvalBareme}\n'
        + '\n'.join(lignes) + '\n'
        + '\\end{seqEvalBareme}\n'
    )


def _section_objectifs(objectifs: list[dict]) -> str:
    """Émet seqEvalObjectifs. Si la liste est vide, retourne '' (la
    section est entièrement omise — décision implicite cohérente avec le
    fait que le tableau n'a pas de sens sans objectif déclaré).

    Chaque ligne : `code & libellé & ❑ & ❑ & ❑ & ❑ \\`
    où code = « S01.Obj. 02 » (décision Q4).
    """
    if not objectifs:
        return ''
    lignes = []
    for o in objectifs:
        code_court = _label_objectif_court(o)
        nom = (o.get('nom') or '').strip()
        # 4 cases ❑ correspondent aux 4 niveaux de maîtrise
        # (Insuffisant / À consolider / Satisfaisant / Très bon)
        lignes.append(
            f"    {code_court} & {nom}\n"
            f"        & \\ding{{113}} & \\ding{{113}} & \\ding{{113}} & \\ding{{113}} \\\\"
        )
    return (
        '\\begin{seqEvalObjectifs}\n'
        + '\n'.join(lignes) + '\n'
        + '\\end{seqEvalObjectifs}\n'
    )


def _section_exo(conn, eb: dict, mode_notation: str) -> str:
    """Émet un bloc complet pour UN exercice de l'éval :
    - bloc variables (si exo paramétré)
    - \\begin{seqEvalExercice}[titre=..., bareme=...]
        + énoncé brut (résolu pour les macros CSV)
        + \\seqEvalCorrigeExo{corrigé brut, ou marque par défaut}
      \\end{seqEvalExercice}

    Cohérence Q6/Q7 Laurent : énoncé inséré tel quel, corrigé toujours
    émis (avec marque \\emph{Corrigé non rédigé.} si BDD vide).
    """
    exo_id = eb['exercice_id']
    # v0.13.6.12 — `nom` → `titre` (uniformisation des champs d'exo).
    titre = (eb.get('titre') or '').strip()
    bareme = _bareme_exo_str(eb, mode_notation)

    # Charger l'exo complet (énoncé, corrigé, variables) via charger_atome
    # qui sait gérer la sérialisation niveau/sequence cohérente avec le
    # reste du pipeline.
    try:
        atome = charger_atome(conn, 'exercice', exo_id)
    except LookupError:
        # Cas dégénéré : l'exo a disparu de la BDD entre la création
        # du lien et la génération. On émet un placeholder visible.
        return (
            f'\\begin{{seqEvalExercice}}[titre={{{titre or "(exercice introuvable)"}}}, '
            f'bareme={{{bareme}}}]\n'
            f'    \\emph{{Exercice introuvable en base : {exo_id}}}\n'
            f'    \\seqEvalCorrigeExo{{\\emph{{Corrigé indisponible.}}}}\n'
            f'\\end{{seqEvalExercice}}\n'
        )

    # Résolution des macros CSV (seqObjectifGetNom etc.)
    enonce = resoudre_macros_csv(conn, atome.corps or '',
                                  atome.niveau, atome.sequence)
    corrige = resoudre_macros_csv(conn, atome.corrige or '',
                                   atome.niveau, atome.sequence)
    variables = resoudre_macros_csv(conn, atome.variables or '',
                                     atome.niveau, atome.sequence)

    parties = []

    # 1. Variables locales à l'exo (xintdef*, etc.), AVANT le bloc
    if variables.strip():
        parties.append('% ── Variables ──')
        parties.append(variables.rstrip())
        parties.append('')

    # 2. Bloc seqEvalExercice
    parties.append(
        f'\\begin{{seqEvalExercice}}[titre={{{titre}}}, bareme={{{bareme}}}]'
    )
    if enonce.strip():
        parties.append(enonce.rstrip())
    else:
        parties.append('    \\emph{Énoncé non rédigé.}')

    # 3. Corrigé (toujours émis — Q7)
    corrige_contenu = corrige.strip() or '\\emph{Corrigé non rédigé.}'
    parties.append(f'\\seqEvalCorrigeExo{{%')
    parties.append(corrige_contenu)
    parties.append('}')

    parties.append('\\end{seqEvalExercice}')

    return '\n'.join(parties) + '\n'


# ── Point d'entrée principal ───────────────────────────────────────────────────


def generer_tex_evaluation(
    conn: sqlite3.Connection,
    evaluation_id: str,
    tikz_libraries: list[str] | None = None,
    tblr_libraries: list[str] | None = None,
    *,
    gabarit: str | None = None,
    options: dict | None = None,
) -> str:
    """Génère le .tex complet d'une évaluation.

    v0.52.2 — `gabarit='sixieme'` : gabarit de l'équipe de 6e
    (generer_tex_evaluation_6e, options `sujet`, `version`, `calculatrice`).
    Sans gabarit (ou `cycle4`) : rendu du cycle 4, inchangé.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion BDD.
    evaluation_id : str
        Id de l'éval à rendre.
    tikz_libraries, tblr_libraries : list[str], optional
        Bibliothèques à charger inconditionnellement, idem que pour les
        atomes. L'appelant les lit depuis Configuration.

    Returns
    -------
    str
        Contenu .tex prêt à compiler.

    Raises
    ------
    services.evaluations.EvaluationIntrouvable
        Si l'éval n'existe pas.
    """
    if gabarit == 'sixieme':
        return generer_tex_evaluation_6e(conn, evaluation_id, options,
                                         tikz_libraries, tblr_libraries)
    # 1. Lecture de l'éval (lire_evaluation lève EvaluationIntrouvable si KO)
    ev = svc_eval.lire_evaluation(conn, evaluation_id)
    exos = svc_eval.lister_exos_evaluation(conn, evaluation_id)
    objectifs = svc_eval.lister_objectifs_evaluation(conn, evaluation_id)

    mode_notation = ev.get('mode_notation') or 'note'
    item_langue = ev.get('item_langue_francaise') or ''

    # 2. Construction des sections du body
    body_parties = [
        '\\begin{document}',
        '',
        _section_titre(ev),
        '',
        '%% Barème global',
        _section_bareme(exos, mode_notation, item_langue),
    ]

    section_obj = _section_objectifs(objectifs)
    if section_obj:
        body_parties.append('')
        body_parties.append('%% Tableau des objectifs et niveaux de maîtrise')
        body_parties.append(section_obj)

    # Exercices
    for eb in exos:
        body_parties.append('')
        body_parties.append(_section_exo(conn, eb, mode_notation))

    # Corrigé en fin
    body_parties.append('')
    body_parties.append('\\seqEvalAfficheCorriges')
    body_parties.append('\\end{document}')
    body = '\n'.join(body_parties)

    # 3. Détection des options paquet et paquets externes manquants à
    # partir du body assemblé. On construit un pseudo-Atome pour réutiliser
    # detecter_options_paquet et detecter_paquets_tex_manquants qui
    # attendent une dataclass Atome — mais en pratique elles regardent
    # juste les chaînes corps/corrige/variables. Pour rester simple et
    # éviter d'introduire de la dépendance, on duplique localement la
    # logique de détection sur le texte du body assemblé (qui contient
    # toutes les sources métier).
    #
    # En pratique, on utilise extraire_utilisations sur le body. C'est ce
    # qui pilote la fermeture transitive du préambule. detecter_options_paquet
    # et detecter_paquets_tex_manquants demanderaient une Atome ; on les
    # contourne en analysant directement les macros utilisées.
    macros_utilises, envs_utilises = extraire_utilisations(body)

    # 4. Options du paquet : pour une éval, on n'a pas de détection
    # par-exo (la fonction detecter_options_paquet attend une Atome). On
    # fait un OU logique sur les exos individuels.
    options_globales: set[str] = set()
    paquets_manquants_globaux: set[str] = set()
    for eb in exos:
        try:
            atome_exo = charger_atome(conn, 'exercice', eb['exercice_id'])
        except LookupError:
            continue
        for opt in detecter_options_paquet(conn, atome_exo):
            options_globales.add(opt)
        for pkg in detecter_paquets_tex_manquants(conn, atome_exo):
            paquets_manquants_globaux.add(pkg)

    # 5. Préambule sur mesure
    preambule = construire_preambule(
        conn, 'evaluation', macros_utilises, envs_utilises,
        options_atome=sorted(options_globales) if options_globales else None,
        paquets_tex_supplementaires=sorted(paquets_manquants_globaux) if paquets_manquants_globaux else None,
        tikz_libraries=tikz_libraries,
        tblr_libraries=tblr_libraries,
    )

    # 6. Assemblage final
    documentclass = r'\documentclass[a4paper,11pt]{article}'
    return '\n'.join([documentclass, preambule.texte, '', body]) + '\n'


# ═════════════════════════════════════════════════════════════════════════════
# v0.52.2 — Évaluation au gabarit de l'équipe de 6e (gabarit « sixieme »)
# ═════════════════════════════════════════════════════════════════════════════
#
# Rendu visé : les évaluations des lots S01–S03 (clé `evaluations`) et leurs
# pages dans les aperçus :
#
#     \seqIdentEleve
#     \seqTitreEvalSix{titre}{Séquence n --- Sujet A --- calculatrice interdite}
#     \seqBaremeCompetences{S01-02/9,S01-03/6,S01-04/5,Bonus/2}{20}
#     \seqExoEval{titre}{N pts --- S01-02}   (un par exercice)
#
# Décisions (doc/redemarrage_v0_52_2.md) :
#   - E1 Un exercice vise un seul objectif : le premier objectif de
#     l'évaluation (evaluation_objectifs) auquel il est relié par
#     objectif_exos (série EV d'abord). Barème par compétence = somme des
#     points par objectif, objectifs dans l'ordre du tableau des objectifs.
#   - B1 Bonus = exercice sans objectif de l'évaluation : colonne « Bonus »
#     du barème, étiquette « N pts --- bonus », hors total (il s'ajoute
#     « dans la limite » du total, comme dans les évaluations de l'équipe).
#   - E3 Sujet B = remed_enonce / remed_corrige de chaque exercice ; une
#     première ligne « % titre B : … » donne un titre propre au sujet B
#     (sinon titre de l'atome). Version corrigée = \seqVersionCorrigee
#     (macros de réponse) ; un corrigé non vide est une explication
#     (\seqLocExplication, visible en version corrigée seulement).
#   - E2 Mention « calculatrice » : option (interdite par défaut, comme les
#     sept évaluations des lots). v0.52.8 (C1, C2) : par défaut
#     (`selon_evaluation`), le réglage de l'évaluation, sinon le marquage de
#     ses exercices EV (un « autorisée » → autorisée ; sinon interdite) ;
#     une valeur explicite de l'option (rendu de l'atelier, document du
#     référentiel) s'impose.
#   - Une seule géométrie, celle du module de 6e (livret_sequence_6e.document).
#   - v0.52.9 — Sujet en deux parties, façon DNB (D1 à D5,
#     doc/redemarrage_v0_52_9.md, `parties_evaluation_6e`) : quand des
#     exercices EV interdisent la calculatrice et d'autres l'autorisent, la
#     partie 1 « sans calculatrice » (exercices `interdite`) est ramassée au
#     bout de N min et la partie 2 « calculatrice autorisée » (les autres)
#     commence sur une nouvelle feuille. Sinon : .tex de la v0.52.8, au
#     caractère près.

from services.gabarits_documents import CALCULATRICE_6E, SUJETS_6E  # noqa: E402
_MENTION_CALCULATRICE = {"interdite": "calculatrice interdite",
                         "autorisee": "calculatrice autorisée",
                         "non_precisee": "",
                         # v0.52.8 — résolu par generer_tex_evaluation_6e ;
                         # appel direct de corps_evaluation_6e : règle C1
                         # sans exercice marqué.
                         "selon_evaluation": "calculatrice interdite"}
MARQUE_TITRE_B = "% titre B :"


class Evaluation6eErreur(ValueError):
    pass


def options_evaluation_6e(options: dict | None) -> dict:
    o = {"sujet": "A", "version": "eleve", "calculatrice": "selon_evaluation"}
    for cle in o:
        if (options or {}).get(cle) not in (None, ""):
            o[cle] = (options or {})[cle]
    from services.gabarits_documents import VERSIONS_6E
    if o["sujet"] not in SUJETS_6E:
        raise Evaluation6eErreur(f"sujet invalide : {o['sujet']!r}")
    if o["version"] not in VERSIONS_6E:
        raise Evaluation6eErreur(f"version invalide : {o['version']!r}")
    if o["calculatrice"] not in CALCULATRICE_6E:
        raise Evaluation6eErreur(f"calculatrice invalide : {o['calculatrice']!r}")
    return o


def _points(p) -> str:
    """9 → '9' ; 1.5 → '1,5' (entre accolades dans les listes TikZ)."""
    p = float(p or 0)
    return str(int(p)) if p == int(p) else f"{p:g}".replace(".", ",")


def _sujet_b(remed_enonce: str, titre_a: str) -> tuple[str, str]:
    """(titre, énoncé) du sujet B : E3, ligne « % titre B : … » en tête."""
    texte = remed_enonce or ""
    premiere, _, reste = texte.partition("\n")
    if premiere.strip().startswith(MARQUE_TITRE_B):
        return premiere.strip()[len(MARQUE_TITRE_B):].strip() or titre_a, reste
    return titre_a, texte


def structure_evaluation_6e(conn: sqlite3.Connection, evaluation_id: str) -> dict:
    """Lecture : {titre, sequence, objectifs: [{id, etiquette, points}],
    exercices: [{…, objectif (étiquette ou None), points}], bonus, total}."""
    # v0.52.9 — lecture directe (titre, niveau) : `lire_evaluation` calcule
    # le découpage en deux parties, qui relit cette structure.
    r = conn.execute("SELECT titre, niveau FROM evaluations WHERE id = ?",
                     (evaluation_id,)).fetchone()
    if r is None:
        raise svc_eval.EvaluationIntrouvable(evaluation_id)
    ev = {"titre": r[0], "niveau": r[1]}
    exos = svc_eval.lister_exos_evaluation(conn, evaluation_id)
    objectifs = svc_eval.lister_objectifs_evaluation(conn, evaluation_id)
    etiquette = {o["id"]: f"{o['sequence_code']}-{o['code']}" for o in objectifs}
    points_obj = {o["id"]: 0.0 for o in objectifs}
    sortie, bonus = [], 0.0
    for eb in exos:
        oid = None
        for (lien,) in conn.execute(
                "SELECT objectif_id FROM objectif_exos WHERE exercice_id = ? "
                "ORDER BY (serie = 'EV') DESC, serie, ordre", (eb["exercice_id"],)):
            if lien in etiquette:
                oid = lien
                break
        pts = float(eb.get("bareme_points") or 0)
        if oid is None:
            bonus += pts
        else:
            points_obj[oid] += pts
        sortie.append({**eb, "objectif": etiquette.get(oid), "points": pts})
    seqs = [e["sequence"] for e in exos if e.get("sequence")]
    sequence = max(set(seqs), key=seqs.count) if seqs else ""
    return {"titre": (ev.get("titre") or "").strip() or "Évaluation", "niveau": ev["niveau"],
            "sequence": sequence,
            "objectifs": [{"id": o["id"], "etiquette": etiquette[o["id"]],
                           "points": points_obj[o["id"]]} for o in objectifs],
            "exercices": sortie, "bonus": bonus,
            "total": sum(points_obj.values())}


def _liste_nums(nums: list[str]) -> str:
    """['1'] → '1' ; ['1', '3', '4'] → '1, 3 et 4'."""
    return " et ".join([", ".join(nums[:-1]), nums[-1]]) if len(nums) > 1 else nums[0]


def parties_evaluation_6e(conn: sqlite3.Connection, evaluation_id: str,
                          st: dict | None = None) -> dict | None:
    """v0.52.9 — Découpage du sujet en deux parties (décisions D1 à D5).

    None si D1 ne s'applique pas (sujet d'un seul tenant, v0.52.8). Sinon :
    `parties` = [[exercices de la partie 1], [partie 2]] (dicts de
    `structure_evaluation_6e`, dans leur ordre — D2), `numeros`
    {exercice_id: numéro affiché} (numérotation continue, N1), `points`
    [partie 1, partie 2] hors bonus, `bonus` [partie 1, partie 2],
    `duree_auto` (D4), `duree_reglee` (`evaluations.duree_partie1`, None =
    automatique) et `duree` (celle du sujet)."""
    from services import marqueurs_exercices as mq
    marques = {}
    if mq.colonnes_presentes(conn):
        marques = {r[0]: {"calculatrice": r[1] or "", "serie": r[2]} for r in conn.execute(
            "SELECT e.id, e.calculatrice, e.serie_code FROM evaluation_exercices ee "
            "JOIN exercices e ON e.id = ee.exercice_id WHERE ee.evaluation_id = ?",
            (evaluation_id,))}
    if not mq.deux_parties([m for m in marques.values() if m["serie"] == "EV"]):
        return None
    if st is None:
        st = structure_evaluation_6e(conn, evaluation_id)
    parties: list[list[dict]] = [[], []]
    for e in st["exercices"]:
        parties[mq.partie_de(marques.get(e["exercice_id"], {})) - 1].append(e)
    numeros = {e["exercice_id"]: k for k, e in enumerate(parties[0] + parties[1], start=1)}
    points = [sum(e["points"] for e in p if e["objectif"]) for p in parties]
    bonus = [sum(e["points"] for e in p if not e["objectif"]) for p in parties]
    reglee = None
    if mq.colonne_duree_presente(conn):
        r = conn.execute("SELECT duree_partie1 FROM evaluations WHERE id = ?",
                         (evaluation_id,)).fetchone()
        reglee = r[0] if r and r[0] not in (None, "") else None
    auto = mq.duree_partie1_auto(points[0], st["total"])
    return {"parties": parties, "numeros": numeros, "points": points, "bonus": bonus,
            "duree_auto": auto, "duree_reglee": reglee,
            "duree": int(reglee) if reglee is not None else auto}


def exercices_affiches_6e(st: dict, decoupage: dict | None) -> list[tuple[int, dict]]:
    """[(numéro affiché, exercice)] dans l'ordre du sujet : celui de
    l'évaluation (v0.52.8), ou partie 1 puis partie 2 (D2, numérotation
    continue N1)."""
    if decoupage is None:
        return list(enumerate(st["exercices"], start=1))
    return list(enumerate(decoupage["parties"][0] + decoupage["parties"][1], start=1))


# v0.52.9 (D3, F1) — Nouvelle feuille pour la partie 2 : le sujet est
# photocopié recto-verso (documents 6e en `article` recto simple : rien ne le
# sait) ; on saute donc à une page impaire, en laissant au besoin le verso de
# la dernière page de la partie 1 blanc (mention discrète), et la partie 2
# repart à la page 1 (en-tête « … --- partie 2 -- page 1 »).
SAUT_FEUILLE_PARTIE2 = (
    r"\clearpage\ifodd\value{page}\else\null\thispagestyle{empty}\vfill"
    r"\begin{center}\small\itshape\color{seqSixGrisTexte}Page laissée blanche : "
    r"la partie 2 est sur une autre feuille.\end{center}\vfill\clearpage\fi"
    r"\setcounter{page}{1}")


def bandeau_partie_6e(partie: int, duree: int | None = None) -> str:
    """D3 — « Partie 1 --- sans calculatrice --- à rendre au bout de N min »
    / « Partie 2 --- calculatrice autorisée », encadré sous le titre (LaTeX
    de base : aucune macro nouvelle, le module 6e ne change pas)."""
    texte = (f"Partie 1 --- sans calculatrice --- à rendre au bout de {duree} min"
             if partie == 1 else "Partie 2 --- calculatrice autorisée")
    return (r"\begin{center}\fbox{\bfseries " + texte + r"}\end{center}")


def _lignes_exercice_6e(conn, e: dict, opts: dict) -> list[str]:
    """Lignes d'un exercice du sujet (A ou B), comme en v0.52.8."""
    L: list[str] = []
    atome = charger_atome(conn, "exercice", e["exercice_id"])
    if opts["sujet"] == "B":
        titre, enonce = _sujet_b(getattr(atome, "remed_enonce", "") or "", e["titre"])
        corrige = getattr(atome, "remed_corrige", "") or ""
        if not enonce.strip():
            enonce = r"\emph{Sujet B non rédigé.}"
    else:
        titre, enonce, corrige = e["titre"], atome.corps or "", atome.corrige or ""
    if (atome.variables or "").strip():
        L.append(atome.variables.rstrip())
    tag = f"{_points(e['points'])} pts --- {e['objectif'] or 'bonus'}"
    L.append("")
    L.append(r"\seqExoEval{" + titre + "}{" + tag + "}")
    L.append(enonce.strip())
    if corrige.strip():
        L.append(r"\seqLocExplication{" + corrige.strip() + "}")
    return L


def corps_evaluation_6e(conn: sqlite3.Connection, st: dict, opts: dict,
                        decoupage: dict | None = None) -> list[str]:
    """Lignes du sujet. `decoupage` (v0.52.9, `parties_evaluation_6e`) :
    None = sujet d'un seul tenant, exactement comme en v0.52.8."""
    from services.livret_sequence_6e import _nom_sequence, entete
    nom, numero = _nom_sequence(conn, st["niveau"], st["sequence"]) if st["sequence"] \
        else ("", None)
    corrigee = opts["version"] == "corrigee"
    # v0.52.9 (D2) — en deux parties, les mentions de calculatrice sont
    # celles des bandeaux de partie : le sous-titre ne porte plus la mention C1.
    # v0.53.0 (MR5) — test court d'une mise en route : « Mise en route n »
    # (le numéro de la séquence du cycle, 200 + n, n'a pas de sens affiché).
    from services.mises_en_route_6e import est_sequence_mer, libelle_mer
    sequence_affichee = (libelle_mer(st["sequence"]) if est_sequence_mer(st["sequence"])
                         else f"Séquence {numero}" if numero else "")
    sous_titre = " --- ".join(x for x in (
        sequence_affichee, f"Sujet {opts['sujet']}",
        _MENTION_CALCULATRICE[opts["calculatrice"]] if decoupage is None else "") if x)
    colonnes = [f"{o['etiquette']}/{{{_points(o['points'])}}}" for o in st["objectifs"]]
    if st["bonus"]:
        colonnes.append(f"Bonus/{{{_points(st['bonus'])}}}")
    nom_doc = nom or st["titre"]
    L = [entete({"nom": nom_doc if decoupage is None else nom_doc + " --- partie 1"},
                corrigee),
         r"\setcounter{seqExoEval}{0}",
         r"\seqIdentEleve",
         r"\seqTitreEvalSix{" + st["titre"] + "}{" + sous_titre + "}"]
    if decoupage is not None:
        L.append(bandeau_partie_6e(1, decoupage["duree"]))
    # D5 — un seul tableau de barème, en tête de la partie 1.
    L.append(r"\seqBaremeCompetences{" + ",".join(colonnes) + "}{" + _points(st["total"]) + "}")
    affiches = exercices_affiches_6e(st, decoupage)
    if st["bonus"]:
        # Légende (comme les évaluations de l'équipe qui ont un bonus) :
        # exercices de chaque compétence, et la règle du bonus.
        par_obj: dict = {}
        for k, e in affiches:
            if e["objectif"]:
                par_obj.setdefault(e["objectif"], []).append(str(k))
        morceaux = []
        for o in st["objectifs"]:
            nums = par_obj.get(o["etiquette"])
            if nums:
                morceaux.append(f"{o['etiquette']} : ex. " + _liste_nums(nums))
        L.append(r"{\scriptsize\color{seqSixGrisTexte}" + " ; ".join(morceaux)
                 + f". Le bonus s'ajoute dans la limite de {_points(st['total'])}.}}")
    if decoupage is not None:
        # D5 — rappel des exercices de chaque partie sous le barème unique
        # (un objectif évalué dans les deux parties reste une seule colonne).
        morceaux = []
        for i, p in enumerate(decoupage["parties"]):
            nums = [str(decoupage["numeros"][e["exercice_id"]]) for e in p]
            pts = _points(decoupage["points"][i]) + " pts" \
                + (" + bonus" if decoupage["bonus"][i] else "")
            morceaux.append(f"artie {i + 1} : ex. {_liste_nums(nums)} ({pts})")
        L.append(r"\par{\scriptsize\color{seqSixGrisTexte}P" + " ; p".join(morceaux) + ".}")
    if decoupage is None:
        for e in st["exercices"]:
            L += _lignes_exercice_6e(conn, e, opts)
        return L
    for e in decoupage["parties"][0]:
        L += _lignes_exercice_6e(conn, e, opts)
    # D3 — partie 2 sur une nouvelle feuille, avec son propre en-tête
    # d'identification et le rappel de la partie ; numérotation continue (N1).
    L += ["", SAUT_FEUILLE_PARTIE2,
          entete({"nom": nom_doc + " --- partie 2"}, corrigee),
          r"\seqIdentEleve",
          r"\seqTitreEvalSix{" + st["titre"] + "}{" + sous_titre + "}",
          bandeau_partie_6e(2)]
    for e in decoupage["parties"][1]:
        L += _lignes_exercice_6e(conn, e, opts)
    return L


def generer_tex_evaluation_6e(conn: sqlite3.Connection, evaluation_id: str,
                              options: dict | None = None,
                              tikz_libraries: list[str] | None = None,
                              tblr_libraries: list[str] | None = None) -> str:
    """Évaluation au gabarit de l'équipe de 6e (options : sujet A|B,
    version eleve|corrigee, calculatrice)."""
    from services.livret_sequence_6e import document
    opts = options_evaluation_6e(options)
    if opts["calculatrice"] == "selon_evaluation":                  # v0.52.8 (C1)
        from services.marqueurs_exercices import calculatrice_evaluation
        opts["calculatrice"] = calculatrice_evaluation(conn, evaluation_id)["valeur"]
    st = structure_evaluation_6e(conn, evaluation_id)
    titre = f"Évaluation 6e — {st['titre']} — sujet {opts['sujet']}"
    # v0.52.9 (D1) — le découpage ne dépend que du marquage des exercices :
    # ni l'option du rendu ni le réglage de l'évaluation ne l'empêchent (ils
    # ne règlent que la mention d'un sujet d'un seul tenant).
    decoupage = parties_evaluation_6e(conn, evaluation_id, st)
    return document(conn, st["niveau"], titre, corps_evaluation_6e(conn, st, opts, decoupage),
                    opts["version"] == "corrigee", tikz_libraries, tblr_libraries)
