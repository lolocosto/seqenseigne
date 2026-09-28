"""services/atomes_liste.py — v0.13.6.15

Service générique de liste légère d'atomes pour la sidebar des ateliers
d'édition de portée séquence.

Objectif : éliminer les « subtilités importantes » entre les ateliers
en exposant un contrat de retour uniforme, indépendant du type d'atome.

Contrat de retour : `list[dict]`, chaque dict contenant exactement
ces 6 clés, ni plus ni moins :

    {
        'id':        str,             # identifiant unique de l'atome
        'titre':     str,             # libellé affiché (jamais None)
        'num':       int | None,      # numéro brut pour le tri
        'code':      str,             # identifiant compact préfixé,
                                      #   ex. 'N01', 'M02', 'E01', 'A03',
                                      #       'CA01', 'FR03'
        'etat_code': str,             # 'en_cours' | 'valide'
        'liens':     list[dict],      # liens objectifs au format _lien_obj
                                      #   (cf. services/liaisons_atomes.py)
    }

L'appelant (route HTTP) renvoie tel quel ; on ne filtre pas davantage
(décision v0.13.6.15 : « assumed safe », tests garantissent le contrat).

Note : ce service est séparé des services métier (atomes.py,
fiches_resume.py, cartes_automatisme.py) pour éviter une dépendance
circulaire avec liaisons_atomes.py et marquer clairement le périmètre
« lecture pour sidebar » (par opposition aux services CRUD complets).
"""

from __future__ import annotations
import sqlite3

from services.liaisons_atomes import enrichir_liste_atomes


# Types d'atomes supportés. La liste est figée — toute extension doit
# passer par une mise à jour explicite ici, des routes consommatrices et
# des tests associés.
TYPES_ATOMES_SUPPORTES = frozenset({
    'notion', 'methode', 'exercice', 'carte', 'fiche',
})


class TypeAtomeInvalide(ValueError):
    """Levée quand type_atome n'est pas dans TYPES_ATOMES_SUPPORTES."""

    def __init__(self, type_atome: str):
        super().__init__(
            f"Type d'atome inconnu : {type_atome!r}. "
            f"Attendu parmi : {sorted(TYPES_ATOMES_SUPPORTES)}."
        )
        self.type_atome = type_atome


def _code_atome(type_atome: str, atome_row: sqlite3.Row) -> str:
    """Construit le code compact préfixé d'un atome.

    Décision v0.13.6.15 : ce code est calculé centralement, ce qui élimine
    la logique de préfixe dispersée dans chaque `rendreItem` côté JS.

    Préfixes :
      - notion    : 'N' + num_connaissance         → 'N01', 'N12'
      - methode   : 'M' + num_methode (padding 2)  → 'M01', 'M12'
      - exercice  : serie_code + num (padding 2)   → 'E01', 'A03', 'F02'
      - carte     : 'CA' + num (padding 2)         → 'CA01'
      - fiche     : 'FR' + num_fiche (padding 2)   → 'FR01'

    Les num qui sont stockés en TEXT (notion.num_connaissance) sont
    passés tels quels (ils contiennent déjà leur padding). Les num INTEGER
    sont paddés à 2 chiffres. Si le num est manquant, on tombe sur '??'
    (donnée incohérente, mais on ne plante pas la sidebar).
    """
    if type_atome == 'notion':
        num = atome_row['num']
        if num is None or str(num).strip() == '':
            return 'N??'
        return f"N{str(num).zfill(2)}"

    if type_atome == 'methode':
        num = atome_row['num']
        return f"M{int(num):02d}" if num is not None else 'M??'

    if type_atome == 'exercice':
        num = atome_row['num']
        serie = atome_row['serie_code'] or '?'
        return f"{serie}{int(num):02d}" if num is not None else f"{serie}??"

    if type_atome == 'carte':
        num = atome_row['num']
        return f"CA{int(num):02d}" if num is not None else 'CA??'

    if type_atome == 'fiche':
        num = atome_row['num']
        return f"FR{int(num):02d}" if num is not None else 'FR??'

    raise TypeAtomeInvalide(type_atome)


def lister_atomes_sequence(
    conn: sqlite3.Connection,
    type_atome: str,
    niveau: str,
    sequence: str,
) -> list[dict]:
    """Liste les atomes d'un type donné pour un niveau.

    Si `sequence` est non vide : atomes de cette séquence (comportement
    historique). Si `sequence` est vide/None : atomes de TOUTES les séquences du
    niveau (mode « toutes séquences »), chaque atome portant sa clé `sequence`
    pour permettre le regroupement à l'affichage.

    Voir le contrat de retour en tête de module.

    Lève :
      - TypeAtomeInvalide si type_atome n'est pas supporté
      - ValueError si niveau est vide
    """
    if type_atome not in TYPES_ATOMES_SUPPORTES:
        raise TypeAtomeInvalide(type_atome)
    if not niveau:
        raise ValueError(
            "lister_atomes_sequence : niveau est obligatoire."
        )
    toutes_sequences = not sequence

    # Chaque type : (table, colonne num, ordre). On construit le WHERE selon
    # le mode (une séquence, ou toutes) et on ramène toujours `sequence`.
    _CONF = {
        'notion':   ("notions", "num_connaissance",
                     "CAST(num_connaissance AS INTEGER), id"),
        'methode':  ("methodes", "num_methode", "num_methode, id"),
        'exercice': ("exercices", "num", "serie_code, num, id"),
        'carte':    ("cartes_automatisme", "num", "ordre, num, id"),
        'fiche':    ("fiches_resume", "num_fiche", "num_fiche, id"),
    }
    table, col_num, ordre = _CONF[type_atome]
    # serie_code n'existe que pour les exercices.
    extra = ", serie_code" if type_atome == 'exercice' else ""
    where = "niveau = ?" + ("" if toutes_sequences else " AND sequence = ?")
    params = (niveau,) if toutes_sequences else (niveau, sequence)
    # En mode toutes séquences, trier d'abord par séquence pour un regroupement
    # naturel.
    ordre_final = ("sequence, " + ordre) if toutes_sequences else ordre
    rows = conn.execute(
        f"SELECT id, titre, {col_num} AS num, etat_code, sequence{extra} "
        f"FROM {table} WHERE {where} ORDER BY {ordre_final}", params
    ).fetchall()

    # ── Projection sur le contrat à 6 clés ──────────────────────────────────

    atomes = []
    for r in rows:
        # Pour les num stockés en TEXT (notion), on cast en int seulement
        # pour `num` (clé contrat) — `_code_atome` lit la valeur brute.
        num_brut = r['num']
        try:
            num_int = int(num_brut) if num_brut is not None else None
        except (TypeError, ValueError):
            num_int = None

        atomes.append({
            'id':        r['id'],
            'titre':     r['titre'] or '',
            'num':       num_int,
            'code':      _code_atome(type_atome, r),
            'etat_code': r['etat_code'] or 'en_cours',
            'sequence':  r['sequence'] or '',
        })

    # ── Enrichissement liens (commun à tous les types) ──────────────────────
    # `enrichir_liste_atomes` mute la liste sur place pour ajouter
    # `liens: [...]` à chaque atome. Le type passé doit être celui que
    # connaît liaisons_atomes — la liste s'aligne sur la nôtre.

    enrichir_liste_atomes(conn, atomes, type_atome)

    return atomes
