"""services/recherche_atomes.py — v0.18.1 — Outil Recherche (Outils généraux).

Recherche transversale sur les cinq types d'atomes (notion, methode, exercice,
fiche, carte), tous niveaux et toutes séquences confondus si on le souhaite.

Différence avec `services.atomes_liste.lister_atomes_sequence` : celui-ci EXIGE
un couple (niveau, sequence). Ici, niveau et séquence sont des filtres
*optionnels* (chaîne vide = pas de filtre), ce qui permet l'« explorateur »
décidé en cadrage (D2) : un « Rechercher » avec texte vide liste tout ce qui
correspond aux filtres.

Décisions de cadrage (v0.18.1) encodées ici :

  D1 — Périmètre du texte cherché, par type (union des sources de texte) :
       - notion  : titre + corps + sections (atome_sections.titre +
                   atome_section_items.corps) — les exemples/remarques sont
                   des sections (titre 'Exemples'/'Remarques'), donc couverts
       - methode : idem notion
       - fiche   : titre + sections (entite_type='fiche_resume')
                   (pas de colonne `corps`)
       - exercice: titre + enonce + corrige + variables
                   + remed_enonce + remed_corrige
       - carte   : titre + recto + verso + variables

       NB — la table `items_texte` (catégories exemple/remarque) est de
       l'archive morte remplacée en v0.6.4 par atome_sections : elle n'est
       PAS interrogée (le contenu vivant est dans atome_sections).

  D2 — Explorateur : texte vide => le filtre texte ne s'applique pas.

  D4 — SENSIBLE AUX ACCENTS (« médiane » ne trouve pas « mediane ») : on ne
       déplie JAMAIS les diacritiques. INSENSIBLE À LA CASSE par défaut
       (`casse_sensible=False`). Le futur sélecteur de casse est prévu côté
       UI ; le service l'expose déjà via `casse_sensible`.

  D5 — Regex : `regex=True` applique `re.search` sur le même texte agrégé que
       la recherche substring. Insensibilité à la casse via `re.IGNORECASE`
       (jamais `re.UNICODE`-fold). Une regex invalide lève `RechercheRegexInvalide`
       (la route la traduit en 400, l'UI l'affiche inline — pas de 500).

  D6 — Tout en Python : on charge les lignes filtrées (niveau/séquence/état) en
       SQL, puis on agrège les 3 sources de texte par atome et on applique le
       test (substring ou regex). À l'échelle de la base (~1769 atomes) c'est
       instantané et le comportement accents/regex est exact.

Contrat de sortie : `rechercher` renvoie un dict groupé par type :

    {
      'notion':   [ {id, type, niveau, sequence, identifiant, titre,
                     etat_code}, ... ],
      'methode':  [ ... ],
      'exercice': [ ... ],
      'fiche':    [ ... ],
      'carte':    [ ... ],
      'total':    <int>,
    }

Les listes sont triées par (niveau, sequence, num, id) ; l'ordre des clés de
type suit `ORDRE_TYPES` (cours → fiches → cartes), réutilisé du rendu par lot
pour cohérence d'affichage.
"""

import re
import sqlite3

# On réutilise les helpers d'identifiant lisible et l'ordre des types du
# rendu par lot : une seule source de vérité pour « N10/S01/Notion 03 » etc.
from services.compilation_batch import (
    ORDRE_TYPES,
    _identifiant_notion,
    _identifiant_methode,
    _identifiant_exercice,
    _identifiant_fiche,
    _identifiant_carte,
)


# ── Constantes ────────────────────────────────────────────────────────────────

# Types acceptés par la recherche (les 5 types d'atomes).
TYPES_RECHERCHE = ('notion', 'methode', 'exercice', 'fiche', 'carte')

# États acceptés pour le filtre. '' (ou 'tous') = pas de filtre.
ETATS_RECHERCHE = ('en_cours', 'valide')

# Mapping type d'atome → entite_type utilisé dans atome_sections / items_texte.
# (Les fiches portent 'fiche_resume', pas 'fiche'.)
_ENTITE_TYPE = {
    'notion':   'notion',
    'methode':  'methode',
    'fiche':    'fiche_resume',
}


# ── Erreurs ──────────────────────────────────────────────────────────────────

class RechercheErreur(Exception):
    """Parent des erreurs de recherche, avec code string + details."""
    def __init__(self, message, code, **details):
        super().__init__(message)
        self.code = code
        self.details = details


class RechercheRegexInvalide(RechercheErreur):
    """Le motif fourni avec regex=True n'est pas une expression régulière valide."""
    def __init__(self, motif, raison):
        super().__init__(
            f"Expression régulière invalide : {raison}",
            "regex_invalide",
            motif=motif,
            raison=raison,
        )


# ── Agrégation du texte cherché (D1) ─────────────────────────────────────────

def _sections_par_entite(conn, entite_type, ids):
    """Renvoie {entite_id: [textes...]} pour les sections d'un ensemble d'atomes.

    Agrège, pour chaque atome, les titres de section (atome_sections.titre) et
    les corps d'items (atome_section_items.corps). Une seule requête joignant
    les deux tables, filtrée sur l'ensemble d'ids fourni.
    """
    if not ids:
        return {}
    place = ','.join('?' * len(ids))
    rows = conn.execute(f"""
        SELECT s.entite_id  AS eid,
               s.titre       AS stitre,
               i.corps       AS icorps
          FROM atome_sections s
          LEFT JOIN atome_section_items i ON i.section_id = s.id
         WHERE s.entite_type = ?
           AND s.entite_id IN ({place})
    """, (entite_type, *ids)).fetchall()
    out = {}
    for r in rows:
        bucket = out.setdefault(r['eid'], [])
        if r['stitre']:
            bucket.append(r['stitre'])
        if r['icorps']:
            bucket.append(r['icorps'])
    return out


# ── Chargement filtré + agrégation par type ──────────────────────────────────

def _charger_type(conn, type_atome, niveau, sequence, etat):
    """Charge les atomes d'un type avec leur texte agrégé, filtrés en SQL.

    Renvoie une liste de dicts :
        {id, type, niveau, sequence, num, identifiant, titre, etat_code,
         _texte}  (où _texte est la chaîne agrégée pour le test, retirée
                   avant le retour au client par `rechercher`).

    Les filtres niveau/sequence/etat sont appliqués en SQL (chaîne vide =
    pas de filtre). Le filtre texte est appliqué plus tard, en Python.
    """
    conds = []
    params = []
    if niveau:
        conds.append("niveau = ?")
        params.append(niveau)
    if sequence:
        conds.append("sequence = ?")
        params.append(sequence)
    if etat:
        conds.append("etat_code = ?")
        params.append(etat)
    where = (" WHERE " + " AND ".join(conds)) if conds else ""

    # SELECT par type : colonnes texte propres au type + métadonnées.
    # Important : on garde les noms de colonnes de num TELS QUELS
    # (num_connaissance, num_methode, num_fiche, num) parce que les helpers
    # _identifiant_* du rendu par lot les lisent par leur nom d'origine.
    # On dérive un `num` uniforme pour le tri à partir de la bonne colonne.
    if type_atome == 'notion':
        sql = f"""SELECT id, titre, corps, niveau, sequence,
                         num_connaissance, etat_code
                    FROM notions{where}"""
        col_num = 'num_connaissance'
    elif type_atome == 'methode':
        sql = f"""SELECT id, titre, corps, niveau, sequence,
                         num_methode, etat_code
                    FROM methodes{where}"""
        col_num = 'num_methode'
    elif type_atome == 'exercice':
        sql = f"""SELECT id, titre, enonce, corrige, variables,
                         remed_enonce, remed_corrige,
                         niveau, sequence, num, serie_code, etat_code
                    FROM exercices{where}"""
        col_num = 'num'
    elif type_atome == 'fiche':
        sql = f"""SELECT id, titre, niveau, sequence,
                         num_fiche, etat_code
                    FROM fiches_resume{where}"""
        col_num = 'num_fiche'
    elif type_atome == 'carte':
        sql = f"""SELECT id, titre, recto, verso, variables,
                         niveau, sequence, num, etat_code
                    FROM cartes_automatisme{where}"""
        col_num = 'num'
    else:
        raise RechercheErreur(
            f"Type de recherche invalide : {type_atome!r}.",
            "type_invalide", type=type_atome,
        )

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return []

    ids = [r['id'] for r in rows]

    # Source auxiliaire de texte : les sections (atome_sections +
    # atome_section_items), chargées en bloc. Elles couvrent aussi les
    # exemples/remarques (sections titrées 'Exemples'/'Remarques').
    sections = {}
    entite_type = _ENTITE_TYPE.get(type_atome)
    if entite_type:
        sections = _sections_par_entite(conn, entite_type, ids)

    identifiant_fn = {
        'notion':   _identifiant_notion,
        'methode':  _identifiant_methode,
        'exercice': _identifiant_exercice,
        'fiche':    _identifiant_fiche,
        'carte':    _identifiant_carte,
    }[type_atome]

    out = []
    for r in rows:
        d = dict(r)
        # Texte agrégé = titre + colonnes texte directes + sections.
        morceaux = [d.get('titre') or '']
        for col in ('corps', 'enonce', 'corrige', 'variables',
                    'remed_enonce', 'remed_corrige', 'recto', 'verso'):
            if col in d and d[col]:
                morceaux.append(d[col])
        morceaux.extend(sections.get(d['id'], []))

        # num pour le tri : entier si possible, sinon None (placé en fin).
        # Lu depuis la colonne réelle (col_num) pour ce type.
        num_brut = d.get(col_num)
        try:
            num_int = int(num_brut) if num_brut is not None else None
        except (TypeError, ValueError):
            num_int = None

        out.append({
            'id':          d['id'],
            'type':        type_atome,
            'niveau':      d.get('niveau') or '',
            'sequence':    d.get('sequence') or '',
            'num':         num_int,
            # d porte les noms de colonnes d'origine (num_connaissance, etc.) :
            # les helpers _identifiant_* y trouvent ce qu'ils attendent.
            'identifiant': identifiant_fn(d),
            'titre':       d.get('titre') or '',
            'etat_code':   d.get('etat_code') or 'en_cours',
            '_texte':      '\n'.join(morceaux),
        })
    return out


# ── Construction du prédicat texte (D4/D5) ───────────────────────────────────

def _construire_predicat(motif, regex, casse_sensible):
    """Renvoie une fonction texte -> bool, ou None si pas de filtre texte.

    - regex=False : test substring. Sensible aux accents toujours (pas de
      normalisation). Casse selon `casse_sensible`.
    - regex=True  : re.search. IGNORECASE si non casse_sensible. Lève
      RechercheRegexInvalide si le motif ne compile pas.
    """
    motif = (motif or '')
    if motif == '':
        return None  # D2 : explorateur, pas de filtre texte.

    if regex:
        # MULTILINE : ^ et $ s'ancrent sur chaque ligne du texte agrégé
        # (titre + corps + sections sont joints par des \n), ce qui rend
        # l'ancrage intuitif pour l'utilisateur. DOTALL n'est PAS activé :
        # « . » ne traverse pas les sauts de ligne.
        flags = re.MULTILINE
        if not casse_sensible:
            flags |= re.IGNORECASE
        try:
            patt = re.compile(motif, flags)
        except re.error as e:
            raise RechercheRegexInvalide(motif, str(e))
        return lambda texte: patt.search(texte) is not None

    # Substring. On NE normalise PAS les accents (D4). Pour l'insensibilité à
    # la casse on abaisse les deux côtés (str.lower respecte les accents :
    # 'É'.lower() == 'é', sans dépliage vers 'e').
    if casse_sensible:
        return lambda texte: motif in texte
    motif_bas = motif.lower()
    return lambda texte: motif_bas in texte.lower()


# ── API publique ─────────────────────────────────────────────────────────────

def rechercher(store, *, type='', niveau='', sequence='', etat='',
               texte='', regex=False, casse_sensible=False):
    """Recherche transversale d'atomes. Voir l'en-tête du module.

    Paramètres (tous optionnels) :
      - type      : '' (tous) | 'notion' | 'methode' | 'exercice' | 'fiche' | 'carte'
      - niveau    : '' (tous) | 'N09' | 'N10' | 'N11' | 'N12' | …
      - sequence  : '' (toutes) | 'S01' | … | 'S14'
      - etat      : '' / 'tous' (tous) | 'en_cours' | 'valide'
      - texte     : motif recherché ('' = explorateur, D2)
      - regex     : interpréter `texte` comme expression régulière (D5)
      - casse_sensible : recherche sensible à la casse (défaut False, D4)

    Renvoie le dict groupé par type décrit dans l'en-tête.
    Lève RechercheRegexInvalide si regex=True et motif invalide.
    Lève RechercheErreur(code='type_invalide') si `type` hors TYPES_RECHERCHE.
    """
    # Normalisation des filtres « tous ».
    if etat in ('', 'tous'):
        etat = ''
    if type in ('', 'tous'):
        type = ''
    if type and type not in TYPES_RECHERCHE:
        raise RechercheErreur(
            f"Type de recherche invalide : {type!r}.",
            "type_invalide", type=type,
        )

    types_a_chercher = (type,) if type else ORDRE_TYPES
    # ORDRE_TYPES utilise 'carte'/'fiche' comme nos clés : cohérent.

    predicat = _construire_predicat(texte, regex, casse_sensible)

    resultat = {}
    total = 0
    with store._conn() as conn:
        for t in types_a_chercher:
            atomes = _charger_type(conn, t, niveau, sequence, etat)
            if predicat is not None:
                atomes = [a for a in atomes if predicat(a['_texte'])]
            # Tri (niveau, sequence, num, id). num None en fin via sentinelle.
            atomes.sort(key=lambda a: (
                a['niveau'], a['sequence'],
                (a['num'] is None, a['num'] if a['num'] is not None else 0),
                a['id'],
            ))
            # On retire le champ interne _texte avant retour au client.
            for a in atomes:
                a.pop('_texte', None)
            resultat[t] = atomes
            total += len(atomes)

    # Contrat de sortie : les 5 clés de type sont TOUJOURS présentes (liste
    # vide si non recherchée ou sans résultat), pour simplifier l'UI.
    for t in TYPES_RECHERCHE:
        resultat.setdefault(t, [])

    resultat['total'] = total
    return resultat
