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
) -> str:
    """Génère le .tex complet d'une évaluation.

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
