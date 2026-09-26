"""
scanner_latex.py — Importe les atomes pédagogiques LaTeX dans la BdD Flask de seqenseigne.

Routes ajoutées dans app.py :
    POST /api/scanner/lancer   { chemin_sequences, niveau }
    GET  /api/scanner/apercu   ?chemin=...&niveau=...

Structure attendue sous chemin_sequences/NIVEAU/ :
    exercices/      N11S01F01.tex  N11S01A01.tex  N11S01E01.tex  N11S01AE01.tex
    notions/        N11_S01_Notion_01.tex  N11_S01_Notion_00.tex (multi-notions)
    methodes/       N11_S01_Methode_01.tex
    livrets/        N11_S01_Livret.tex
"""

import re
from persistence.ids import (
    nouveau_id_notion, nouveau_id_methode, nouveau_id_exercice,
)
import os
from pathlib import Path


# ── Helpers de parsing LaTeX ───────────────────────────────────────────────────

def _extract_balanced(src: str, start: int) -> str:
    """Extrait le contenu d'un bloc {...} en gérant les accolades imbriquées."""
    depth = 0
    i = start
    begin = None
    while i < len(src):
        if src[i] == '{':
            depth += 1
            if depth == 1:
                begin = i + 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[begin:i]
        i += 1
    return ''


def _skip_balanced(src: str, start: int) -> int:
    """Renvoie l'index AVANT le `}` fermant du bloc qui démarre à `start`
    (où src[start] == '{'). Symétrique à _extract_balanced mais retourne
    la position au lieu du contenu, pour avancer dans la chaîne après
    avoir consommé un argument.

    Si pas de `{` à `start`, retourne `start` inchangé.
    """
    if start >= len(src) or src[start] != '{':
        return start
    depth = 0
    i = start
    while i < len(src):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return i + 1   # AVANT serait i, on retourne après le }
        i += 1
    return len(src)


# ── v0.6.4 : Modèle universel à 2 niveaux (sections / items) ──────────────────
#
# Le parseur produit pour chaque atome (notion ou méthode) une liste ordonnée
# de sections, chacune ayant un titre libre et une liste d'items en LaTeX brut.
#
# Vocabulaire normalisé recommandé pour le titre des sections — l'import
# normalise les variantes courantes vers ce vocabulaire. Tout titre non
# reconnu est conservé tel quel (cas exotiques : « 'Equivalence entre la
# première définition et la deuxième définition », etc.).

# Mapping : titre brut (lowercased, sans accents) → titre normalisé
_NORMALISATION_TITRES = {
    # Pluriel = canonique pour ces 4 catégories (cohérent avec l'usage en classe)
    'exemple':      'Exemples',
    'exemples':     'Exemples',
    'example':      'Exemples',   # variante anglaise
    'examples':     'Exemples',   # variante anglaise
    'remarque':     'Remarques',
    'remarques':    'Remarques',
    'consequence':  'Conséquences',
    'consequences': 'Conséquences',
    'propriete':    'Propriétés',
    'proprietes':   'Propriétés',
    # Singulier = canonique pour Démonstration (et apparentés)
    'demonstration': 'Démonstration',
    'demonstrations': 'Démonstration',
}


def _retirer_accents(s: str) -> str:
    """Retire les accents pour la comparaison de titres (insensible aux
    variantes orthographiques)."""
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )


def _normaliser_titre_section(titre_brut: str) -> str:
    """Normalise le titre d'une section vers le vocabulaire canonique si
    on reconnaît une variante. Sinon retourne le titre tel quel (en
    préservant les espaces et accents originaux).

    Exemples :
      'Exemple'                            → 'Exemples'
      'Examples'                           → 'Exemples'
      'Conséquence'                        → 'Conséquences'
      'Remarques'                          → 'Remarques'
      'Démonstration de la réciproque'     → inchangé (titre composé)
      'Propriété'                          → 'Propriétés'
    """
    if not titre_brut:
        return titre_brut
    cle = _retirer_accents(titre_brut).strip().lower()
    if cle in _NORMALISATION_TITRES:
        return _NORMALISATION_TITRES[cle]
    return titre_brut.strip()


def _extraire_items_seqColItem(contenu: str) -> list[str] | None:
    """Si `contenu` contient un \\begin{seqColItem}...\\end{seqColItem} au
    top-level, extrait la liste des `\\item` au top-level (en respectant
    les imbrications de seqColItem dans les items).

    Retourne :
      - la liste des items en LaTeX brut (chacun peut contenir des
        seqColItem, multicols, tikzpicture imbriqués)
      - None si le contenu ne contient pas de seqColItem au top-level
        (l'appelant traite alors le contenu comme un item unique)

    Le scan respecte les profondeurs : seuls les `\\item` à profondeur 0
    (= directement enfants du seqColItem top-level) sont des séparateurs.
    """
    # Trouver le 1er \begin{seqColItem} au top-level (depth = 0)
    # Note : avec des \begin{multicols} qui contiennent eux-mêmes des
    # \begin{seqColItem}, on veut le seqColItem top-level uniquement.
    begin_pos = _trouver_top_level(contenu, r'\begin{seqColItem}')
    if begin_pos < 0:
        return None

    # Avancer après la séquence \begin{seqColItem}[...]
    apres_begin = begin_pos + len(r'\begin{seqColItem}')
    # Sauter les options [...]
    if apres_begin < len(contenu) and contenu[apres_begin] == '[':
        depth_b = 0
        i = apres_begin
        while i < len(contenu):
            if contenu[i] == '[': depth_b += 1
            elif contenu[i] == ']':
                depth_b -= 1
                if depth_b == 0:
                    apres_begin = i + 1
                    break
            i += 1

    # Chercher \end{seqColItem} correspondant (équilibrage seqColItem)
    end_pos = _trouver_end_apparie(contenu, apres_begin, 'seqColItem')
    if end_pos < 0:
        return None

    corps_seqColItem = contenu[apres_begin:end_pos]

    # Découper sur les `\item` au top-level (profondeur 0 vis-à-vis de
    # seqColItem). On compte profondeur en suivant \begin{seqColItem} et
    # \end{seqColItem}.
    items_raw = _decouper_items_top_level(corps_seqColItem)
    return [it.strip() for it in items_raw if it.strip()]


def _trouver_top_level(s: str, motif: str) -> int:
    """Trouve l'index du 1er occurrence de `motif` au top-level (= depth 0
    vis-à-vis des \\begin{seqColItem}/\\end{seqColItem}, et hors options []).

    Retourne -1 si non trouvé.

    Implémentation simplifiée : si le motif est `\\begin{seqColItem}`, on
    le cherche directement dans la chaîne avec re.search puisqu'il est
    forcément à un niveau d'imbrication ; on retourne sa position.
    Le suivi de profondeur n'a de sens que pour les \\item, pas pour
    le 1er \\begin{seqColItem} (qui par définition ouvre la profondeur 0).
    """
    idx = s.find(motif)
    return idx if idx >= 0 else -1


def _trouver_end_apparie(s: str, start: int, env: str) -> int:
    """Trouve la position du `\\end{env}` apparié à un `\\begin{env}` ouvrant
    qui a déjà été consommé. `start` est l'index juste après `\\begin{env}`.

    Retourne l'index du `\\` du `\\end{env}` apparié, ou -1 si non trouvé.
    """
    begin_tok = r'\begin{' + env + '}'
    end_tok   = r'\end{'   + env + '}'
    depth = 1
    i = start
    while i < len(s):
        # Cherche le prochain begin OU end
        next_begin = s.find(begin_tok, i)
        next_end   = s.find(end_tok,   i)
        if next_end < 0:
            return -1
        if next_begin >= 0 and next_begin < next_end:
            depth += 1
            i = next_begin + len(begin_tok)
        else:
            depth -= 1
            if depth == 0:
                return next_end
            i = next_end + len(end_tok)
    return -1


def _decouper_items_top_level(corps_seqColItem: str) -> list[str]:
    """Découpe `corps_seqColItem` (= contenu d'un \\begin{seqColItem}...
    \\end{seqColItem} sans les balises) sur les `\\item` au top-level.

    Un `\\item` est top-level s'il n'est pas dans un seqColItem imbriqué.
    Implémentation : on suit la profondeur de seqColItem et on splitte
    seulement à profondeur 0.
    """
    items = []
    courant = ''
    i = 0
    n = len(corps_seqColItem)
    depth = 0
    debut_item = -1   # début du contenu de l'item courant (après le \item)
    avant_premier_item = True

    while i < n:
        ch = corps_seqColItem[i]
        if ch == '\\':
            # Tester les motifs qui nous intéressent
            if corps_seqColItem.startswith(r'\begin{seqColItem}', i):
                depth += 1
                # Avancer jusqu'à la fin de \begin{seqColItem}[...]
                fin = i + len(r'\begin{seqColItem}')
                if fin < n and corps_seqColItem[fin] == '[':
                    db = 0
                    j = fin
                    while j < n:
                        if corps_seqColItem[j] == '[': db += 1
                        elif corps_seqColItem[j] == ']':
                            db -= 1
                            if db == 0:
                                fin = j + 1
                                break
                        j += 1
                i = fin
                continue
            elif corps_seqColItem.startswith(r'\end{seqColItem}', i):
                depth -= 1
                i += len(r'\end{seqColItem}')
                continue
            elif depth == 0 and corps_seqColItem.startswith(r'\item', i):
                # Vérifier que c'est bien \item et pas \itemize ou \itemX
                apres = i + len(r'\item')
                if apres >= n or corps_seqColItem[apres] in ' \t\n\r{[':
                    # Fin de l'item courant
                    if not avant_premier_item:
                        items.append(corps_seqColItem[debut_item:i])
                    avant_premier_item = False
                    debut_item = apres
                    i = apres
                    continue
        i += 1

    # Dernier item
    if not avant_premier_item:
        items.append(corps_seqColItem[debut_item:])
    return items


def _split_sections(body: str) -> list[dict]:
    """v0.6.4 — Découpe le corps d'un atome en sections au top-level.

    `body` est le contenu **après** la fermeture du 2e argument de
    \\begin{seqNotion} ou \\begin{seqMethode}, et **avant** \\end{...}.

    Retourne une liste ordonnée de sections : [{titre, items}].
    L'ordre est l'ordre d'apparition dans le source.

    Le découpage se fait sur les motifs `\\underline{...}:` au top-level.
    Chaque section produit :
      - titre : normalisé via _normaliser_titre_section
      - items : liste de chaînes LaTeX
                * si la section contient un \\begin{seqColItem} au
                  top-level → les items sont extraits via
                  _extraire_items_seqColItem
                * sinon → le contenu inline forme un item unique
                  (cas des Conséquences / Démonstrations en prose)
    """
    sections = []

    # Chercher tous les \underline{...}: dans le body. On suppose qu'au
    # top-level (= ce qui est passé en argument), tous les \underline
    # rencontrés sont des séparateurs de section. Les \underline qui
    # seraient à l'intérieur d'un autre environnement ne devraient pas
    # apparaître ici car body commence APRÈS la fermeture du corps.
    pattern = re.compile(r'\\underline\{([^}]+)\}\s*:')
    matches = list(pattern.finditer(body))

    if not matches:
        return sections

    for idx, m in enumerate(matches):
        titre_brut = m.group(1).strip()
        # Petit nettoyage : `\'E` → `É` (cas '\\'Equivalence...')
        titre_brut = re.sub(r"\\'E", 'É', titre_brut)
        titre_brut = re.sub(r"\\'e", 'é', titre_brut)
        titre_norm = _normaliser_titre_section(titre_brut)

        # Le contenu de la section = de la fin du \underline{...}: jusqu'au
        # début du prochain \underline{...}: (ou jusqu'à la fin du body
        # pour la dernière section).
        debut = m.end()
        fin = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        contenu = body[debut:fin].strip()
        # Retirer les \newline en tête (couramment écrit après le `:` pour
        # forcer un saut de ligne avant le contenu)
        contenu = re.sub(r'^\\newline\s*', '', contenu)
        # Retirer les \newline en queue
        contenu = re.sub(r'\s*\\newline\s*$', '', contenu)

        # Extraire les items
        items = _extraire_items_seqColItem(contenu)
        if items is None:
            # Pas de seqColItem : le contenu inline forme un item unique
            # (uniformité, cf. décision : tout passe en liste, même 1 item)
            items = [contenu] if contenu else []

        sections.append({
            'titre': titre_norm,
            'items': items,
        })

    return sections


# ── Parseur notions ────────────────────────────────────────────────────────────

def parse_notions_file(path: Path, niveau: str, seq: str) -> list:
    """
    Parse un fichier N11_S01_Notion_XX.tex.
    Un fichier peut contenir plusieurs \\begin{seqNotion}...\\end{seqNotion}.
    Retourne une liste de dicts notion.

    v0.6.4 : retourne `sections` (liste de {titre, items}) au lieu de
    `exemples` / `remarques`.
    """
    src = path.read_text(encoding='utf-8', errors='replace')
    notions = []

    for m in re.finditer(r'\\begin\{seqNotion\}', src):
        pos = m.end()

        # Argument 1 : titre — _extract_balanced lit le contenu entre {}
        # mais ne fait pas avancer pos. On utilise _skip_balanced pour
        # avancer après la fermeture.
        titre_raw = _extract_balanced(src, pos)
        pos_apres_titre = _skip_balanced(src, _trouver_accolade(src, pos))

        # Argument 2 : corps
        corps_raw = _extract_balanced(src, pos_apres_titre)
        pos_apres_corps = _skip_balanced(src, _trouver_accolade(src, pos_apres_titre))

        # Numéro de connaissance si \seqConnaissanceGetNom{N}
        num_match = re.search(r'\\seqConnaissanceGetNom\{(\d+)\}', titre_raw)
        num_conn = num_match.group(1) if num_match else None

        # ── v0.6.4 (fix) : full_body part APRÈS la fermeture du 2e argument
        # et s'arrête au \end{seqNotion}. Avant, le code partait à l'ouverture
        # du 2e argument, ce qui faisait considérer les \underline{...} du
        # corps comme des sections top-level (bug majeur avec les méthodes).
        end_match = re.search(r'\\end\{seqNotion\}', src[pos_apres_corps:])
        if end_match:
            full_body = src[pos_apres_corps: pos_apres_corps + end_match.start()]
        else:
            full_body = ''

        sections = _split_sections(full_body)

        notion = {
            'id': nouveau_id_notion(),
            'niveau': niveau,
            'sequence': seq,
            'num_connaissance': num_conn,
            'titre': titre_raw.strip(),
            'corps': corps_raw.strip(),
            'sections': sections,           # v0.6.4
            'ordreExRem': True,             # legacy, conservé pour rendu
            'fichier': path.name,
        }
        notions.append(notion)

    return notions


def _trouver_accolade(src: str, start: int) -> int:
    """Renvoie l'index de la 1re `{` à partir de `start`, ou len(src)."""
    i = start
    while i < len(src) and src[i] != '{':
        i += 1
    return i


# ── Parseur méthodes ───────────────────────────────────────────────────────────

def parse_methode_file(path: Path, niveau: str, seq: str, num_methode: str) -> dict:
    """
    Parse un fichier N11_S01_Methode_01.tex.
    Retourne un dict méthode.

    v0.6.4 : retourne `sections` au lieu de `exemples`/`remarques`.
    Corrige aussi le bug qui faisait prendre les \\underline{...} du corps
    comme des sections top-level.
    """
    src = path.read_text(encoding='utf-8', errors='replace')

    m = re.search(r'\\begin\{seqMethode\}', src)
    if not m:
        return None

    pos = m.end()

    # Argument 1 : titre
    titre_raw = _extract_balanced(src, pos)
    pos_apres_titre = _skip_balanced(src, _trouver_accolade(src, pos))

    # Argument 2 : corps
    corps_raw = _extract_balanced(src, pos_apres_titre)
    pos_apres_corps = _skip_balanced(src, _trouver_accolade(src, pos_apres_titre))

    # Numéro d'objectif
    num_match = re.search(r'\\seqObjectifGetNom\{(\d+)\}', titre_raw)
    num_obj = num_match.group(1) if num_match else num_methode

    # full_body : APRÈS la fermeture du 2e argument, jusqu'à \end{seqMethode}
    end_match = re.search(r'\\end\{seqMethode\}', src[pos_apres_corps:])
    full_body = src[pos_apres_corps: pos_apres_corps + end_match.start()] if end_match else ''

    sections = _split_sections(full_body)

    methode = {
        'id': nouveau_id_methode(),
        'niveau': niveau,
        'sequence': seq,
        'num_methode': num_methode,
        'num_objectif': num_obj,
        'titre': titre_raw.strip(),
        'corps': corps_raw.strip(),
        'sections': sections,             # v0.6.4
        'ordreExRem': True,
        'notions': [],
        'finCycle': 'N',
        'criteres': {'fondamental': '', 'avancé': '', 'exploration': ''},
        'fichier': path.name,
    }
    return methode


# ── Parseur exercices ──────────────────────────────────────────────────────────

_SERIE_MAP = {'F': 'fondamental', 'A': 'avancé', 'E': 'exploration', 'AE': 'approche'}

def parse_exercice_file(path: Path, niveau: str, seq: str,
                        serie_code: str, num: str) -> dict:
    """
    Parse un fichier N11S01F01.tex.
    Retourne un dict exercice.
    """
    src = path.read_text(encoding='utf-8', errors='replace')

    # Trouver \begin{seqExercice}[...] ou \begin{seqExercice}
    m = re.search(r'\\begin\{seqExercice\}(\[[^\]]*\])?', src)
    if not m:
        return None

    # Options : nom=..., obj=...
    # v0.13.6.12 — L'option LaTeX `nom=` est conservée pour ne pas casser
    # les .tex existants. En interne (BDD/JSON/JS), on stocke ce libellé
    # dans le champ `titre` (uniformisation avec les autres atomes).
    opts_raw = m.group(1) or ''
    titre = ''
    objectifs = []
    nom_m = re.search(r'nom=([^,\]]+)', opts_raw)
    if nom_m:
        titre = nom_m.group(1).strip()
    obj_m = re.search(r'obj=([^,\]]+)', opts_raw)
    if obj_m:
        objectifs = [o.strip() for o in obj_m.group(1).split(',')]

    pos = m.end()

    # Corps jusqu'à \seqCorrige{ ou \end{seqExercice}
    corrige_pos = src.find(r'\seqCorrige{', pos)
    end_pos_match = re.search(r'\\end\{seqExercice\}', src[pos:])
    end_abs = pos + end_pos_match.start() if end_pos_match else len(src)

    if corrige_pos != -1 and corrige_pos < end_abs:
        enonce = src[pos:corrige_pos].strip()
        corrige = _extract_balanced(src, corrige_pos + len(r'\seqCorrige{') - 1)
    else:
        enonce = src[pos:end_abs].strip()
        corrige = ''

    # Nettoyer les \r
    enonce = enonce.replace('\r\n', '\n').replace('\r', '\n').strip()
    corrige = corrige.replace('\r\n', '\n').replace('\r', '\n').strip()

    # Variables : chercher fichier _param.tex référencé dans le livret (pas ici)
    # On stocke juste les variables xintexpr si présentes dans l'exercice
    variables = ''
    xint_matches = re.findall(r'\\xint(?:defiivar|deffloatvar|defvar)\s+[^\n]+;', src)
    if xint_matches:
        variables = '\n'.join(xint_matches)

    return {
        'id': nouveau_id_exercice(),
        'niveau': niveau,
        'sequence': seq,
        'serie': _SERIE_MAP.get(serie_code, serie_code.lower()),
        'serie_code': serie_code,
        'num': num,
        'titre': titre,
        'objectifs_codes': objectifs,
        'variables': variables,
        'enonce': enonce,
        'corrige': corrige,
        'fichier': path.name,
    }


def parse_param_file(path: Path) -> str:
    """Lit un fichier _param.tex et retourne son contenu brut."""
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ''


# ── Parseur livrets ────────────────────────────────────────────────────────────

def parse_livret_file(path: Path, niveau: str, seq: str) -> dict:
    """
    Parse un fichier N11_S01_Livret.tex.
    Extrait la structure : révisions, notions, méthodes, exercices par série.
    """
    src = path.read_text(encoding='utf-8', errors='replace')

    livret = {
        'niveau': niveau,
        'sequence': seq,
        'fichier': path.name,
        'paquets_supplementaires': [],
        'fichier_param': None,
        'prerequis': {'type': 'révision', 'exercices_revision': []},
        'notions': [],    # ['N11_S01_Notion_01.tex', ...]
        'methodes': [],   # ['N11_S01_Methode_01.tex', ...]
        'exercices': {    # { 'fondamental': [1,2,3], 'avancé': [...], ... }
            'fondamental': [], 'avancé': [], 'exploration': [], 'approche': []
        },
    }

    # Paquets supplémentaires (hors seqenseigne)
    for pkg_m in re.finditer(r'\\usepackage(?:\[[^\]]*\])?\{(?!seqenseigne)([^}]+)\}', src):
        livret['paquets_supplementaires'].append(pkg_m.group(0).strip())

    # Fichier param
    param_m = re.search(r'\\input\{([^}]*_param\.tex)\}', src)
    if param_m:
        livret['fichier_param'] = param_m.group(1)

    # Révisions dans seqSerieExos{0}
    rev_block = re.search(
        r'\\begin\{seqSerieExos\}\{0\}(.*?)\\end\{seqSerieExos\}', src, re.DOTALL)
    if rev_block:
        rev_inputs = re.findall(r'\\input\{([^}]+)\}', rev_block.group(1))
        for inp in rev_inputs:
            # Ex : N10S01A01.tex → niveau_prev=N10, seq=S01, serie=A, num=01
            m = re.match(r'(N\d+)(S\d+)([A-Z]+)(\d+)\.tex', inp)
            if m:
                niv_prev, seq_prev, serie, num = m.groups()
                livret['prerequis']['exercices_revision'].append({
                    'niveau': niv_prev, 'sequence': seq_prev,
                    'serie': _SERIE_MAP.get(serie, serie.lower()),
                    'num': int(num)
                })

    # Notions (inputs dans seqTitreSection{Connaissances})
    notion_inputs = re.findall(r'\\input\{(\.\./notions/[^}]+)\}', src)
    livret['notions'] = [Path(n).name for n in notion_inputs]

    # Méthodes
    methode_inputs = re.findall(r'\\input\{(\.\./methodes/[^}]+)\}', src)
    livret['methodes'] = [Path(m).name for m in methode_inputs]

    # Exercices par série
    serie_num_map = {'1': 'fondamental', '2': 'avancé', '3': 'exploration', '4': 'approche'}
    for bloc_m in re.finditer(
            r'\\begin\{seqSerieExos\}\{([1-4])\}(.*?)\\end\{seqSerieExos\}',
            src, re.DOTALL):
        serie_key = serie_num_map.get(bloc_m.group(1))
        if not serie_key:
            continue
        exo_inputs = re.findall(r'\\input\{([^}]+)\}', bloc_m.group(2))
        nums = []
        for inp in exo_inputs:
            em = re.match(r'N\d+S\d+[A-Z]+(\d+)\.tex', Path(inp).name)
            if em:
                nums.append(int(em.group(1)))
        livret['exercices'][serie_key] = nums

    return livret


# ── Scanner principal ──────────────────────────────────────────────────────────

def scanner_niveau(chemin_sequences: str, niveau: str) -> dict:
    """
    Scanne tous les fichiers d'un niveau et retourne les données structurées.
    chemin_sequences : chemin vers le dossier qui contient N10/, N11/, N12/
    niveau           : 'N10', 'N11', 'N12'
    """
    base = Path(chemin_sequences) / niveau
    result = {
        'niveau': niveau,
        'notions': [],
        'methodes': [],
        'exercices': [],
        'livrets': [],
        'erreurs': [],
    }

    if not base.exists():
        result['erreurs'].append(f"Dossier introuvable : {base}")
        return result

    # ── Notions ────────────────────────────────────────────────────────────────
    notions_dir = base / 'notions'
    if notions_dir.exists():
        for f in sorted(notions_dir.glob('*.tex')):
            m = re.match(r'(N\d+)_(S\d+)_Notion_(\d+)\.tex', f.name)
            if not m:
                continue
            niv, seq, num = m.groups()
            try:
                notions = parse_notions_file(f, niv, seq)
                result['notions'].extend(notions)
            except Exception as e:
                result['erreurs'].append(f"{f.name} : {e}")

    # ── Méthodes ───────────────────────────────────────────────────────────────
    methodes_dir = base / 'methodes'
    if methodes_dir.exists():
        for f in sorted(methodes_dir.glob('*.tex')):
            m = re.match(r'(N\d+)_(S\d+)_Methode_(\d+)\.tex', f.name)
            if not m:
                continue
            niv, seq, num = m.groups()
            try:
                methode = parse_methode_file(f, niv, seq, num)
                if methode:
                    result['methodes'].append(methode)
            except Exception as e:
                result['erreurs'].append(f"{f.name} : {e}")

    # ── Exercices ──────────────────────────────────────────────────────────────
    exercices_dir = base / 'exercices'
    if exercices_dir.exists():
        # Charger les _param.tex d'abord
        params = {}
        for pf in sorted(exercices_dir.glob('*_param.tex')):
            pm = re.match(r'(N\d+)(S\d+)_param\.tex', pf.name)
            if pm:
                key = pm.group(1) + pm.group(2)
                params[key] = parse_param_file(pf)

        for f in sorted(exercices_dir.glob('*.tex')):
            if '_param' in f.name or f.name.endswith('_enonce.tex'):
                continue
            # Nom : N11S01F01.tex ou N11S01AE01.tex
            m = re.match(r'(N\d+)(S\d+)(AE|[FAE])(\d+)\.tex', f.name)
            if not m:
                continue
            niv, seq, serie, num = m.groups()
            try:
                exo = parse_exercice_file(f, niv, seq, serie, num)
                if exo:
                    # Attacher les variables du fichier param si pas dans l'exercice
                    if not exo['variables']:
                        exo['variables'] = params.get(niv + seq, '')
                    result['exercices'].append(exo)
            except Exception as e:
                result['erreurs'].append(f"{f.name} : {e}")

    # ── Livrets ────────────────────────────────────────────────────────────────
    livrets_dir = base / 'livrets_de_sequence'
    if not livrets_dir.exists():
        livrets_dir = base / 'livrets'  # fallback
    if livrets_dir.exists():
        for f in sorted(livrets_dir.glob('*_Livret.tex')):
            m = re.match(r'(N\d+)_(S\d+)_Livret\.tex', f.name)
            if not m:
                continue
            niv, seq = m.groups()
            try:
                livret = parse_livret_file(f, niv, seq)
                result['livrets'].append(livret)
            except Exception as e:
                result['erreurs'].append(f"{f.name} : {e}")

    return result


def scanner_vers_bdd(data: dict, rj_func, wj_func) -> dict:
    """
    Injecte les données scannées dans les fichiers JSON de la BdD Flask.
    rj_func / wj_func : les helpers rj() et wj() de app.py
    Retourne un résumé des compteurs.
    """
    # Notions
    notions_existantes = rj_func('notions.json').get('notions', [])
    ids_existants = {n.get('fichier', '') for n in notions_existantes}
    nouvelles_notions = [n for n in data['notions']
                         if n.get('fichier') not in ids_existants]
    notions_existantes.extend(nouvelles_notions)
    wj_func('notions.json', {'notions': notions_existantes})

    # Méthodes
    methodes_existantes = rj_func('methodes.json').get('methodes', [])
    ids_m = {m.get('fichier', '') for m in methodes_existantes}
    nouvelles_methodes = [m for m in data['methodes']
                          if m.get('fichier') not in ids_m]
    methodes_existantes.extend(nouvelles_methodes)
    wj_func('methodes.json', {'methodes': methodes_existantes})

    # Exercices
    exercices_existants = rj_func('exercices.json').get('exercices', [])
    ids_e = {e.get('fichier', '') for e in exercices_existants}
    nouveaux_exos = [e for e in data['exercices']
                     if e.get('fichier') not in ids_e]
    exercices_existants.extend(nouveaux_exos)
    wj_func('exercices.json', {'exercices': exercices_existants})

    # Livrets → YAML : stockés séparément dans livrets_importes.json
    livrets_existants = rj_func('livrets_importes.json').get('livrets', [])
    ids_l = {(l['niveau'], l['sequence']) for l in livrets_existants}
    nouveaux_livrets = [l for l in data['livrets']
                        if (l['niveau'], l['sequence']) not in ids_l]
    livrets_existants.extend(nouveaux_livrets)
    wj_func('livrets_importes.json', {'livrets': livrets_existants})

    return {
        'notions':  {'total': len(data['notions']),  'nouvelles': len(nouvelles_notions)},
        'methodes': {'total': len(data['methodes']), 'nouvelles': len(nouvelles_methodes)},
        'exercices':{'total': len(data['exercices']),'nouvelles': len(nouveaux_exos)},
        'livrets':  {'total': len(data['livrets']),  'nouvelles': len(nouveaux_livrets)},
        'erreurs':  data['erreurs'],
    }
