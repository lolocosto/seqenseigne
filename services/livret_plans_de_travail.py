r"""
services/livret_plans_de_travail.py — Génération de plans de travail
au format LaTeX (v0.12.1, étendu v0.12.1.2).

Deux portées de génération :

- **Niveau** : `generer_livret_plans_de_travail(conn, niveau)` produit un
  livret annuel agrégeant *toutes* les pages de plan de travail du
  niveau, précédé d'une page de titre. Une page par partie de chaque
  séquence-niveau.

- **Séquence** (v0.12.1.2) : `generer_plan_de_travail_sequence(conn,
  niveau, sequence_code)` produit un mini-livret limité à une seule
  séquence-niveau, *sans page de titre*. Une page par partie de la
  séquence. Sortie pratique pour vérifier rapidement le rendu d'une
  séquence pendant l'édition.

Chaque page partie contient :
  - Boîte titre (\seqBoiteTitrePlan)
  - Bloc « Repères temporels » + « Niveaux atteints » (sans dépendance .dbtex)
  - Bloc Révisions avec liste des exos R (numérotation du livret de séquence)
  - Pour chaque objectif d'exo de la partie : nom de l'objectif, notions liées,
    listes F / A / E

Architecture
------------
Inspirée de livret_recap_cours.py mais beaucoup plus simple :
- Pas de chargement d'atomes (on n'inline ni notions ni méthodes ni exos
  dans leur intégralité — juste des références numériques)
- Pas de cycle annexes / corrigés
- Préambule construit sur mesure via construire_preambule, qui couvre les
  macros utilisées par seqBoiteTitrePlan + boitePaleNoBreak + seqColItem +
  blocReperesNiveaux + boiteTitreGen + seqSetColors

**Indépendance vis-à-vis de \seqLoadData.** À la différence du tex de
référence (N10_Plan_de_travail.tex), ces générateurs n'utilisent PAS
\seqLoadData / \seqConnaissanceGetNom / \seqObjectifGetNom /
\seqSequenceGetNom / \seqPlanReperesNiveaux / \seqPlanObjectif. Toutes ces
résolutions sont faites côté Python à partir de la BDD. La BDD est la
source de vérité ; les fichiers .dbtex sont des archives historiques qui
ne sont plus garanties d'être à jour. On n'utilise donc que les
ENVIRONNEMENTS et boîtes (boitePaleNoBreak, seqColItem, blocReperesNiveaux,
boiteTitreGen) qui ne dépendent pas des bases CSV.

v0.12.1 — Première livraison (portée niveau).
v0.12.1.2 — Ajout de la portée séquence + correction `_cycle_du_niveau`.
"""

from __future__ import annotations

import sqlite3

from services.preambule_atome import construire_preambule
from services.param_niveaux import lire_cycle


# ── Libellés de niveau pour la page de titre ─────────────────────────────────

LIBELLES_NIVEAUX_LATEX = {
    'N09': r'6\ieme{}',
    'N10': r'5\ieme{}',
    'N11': r'4\ieme{}',
    'N12': r'3\ieme{}',
}


# ── Récupération des données ─────────────────────────────────────────────────

# v0.15.5 — `_cycle_du_niveau` local supprimé. On appelle directement
# `services.param_niveaux.lire_cycle` (source unique de vérité). Le wrapper
# ne servait qu'à reformuler le message de l'exception ; or NiveauInconnu
# est déjà une LookupError et aucun appelant ne matche le texte du message
# (vérifié v0.15.5). Cf. test_v0_15_5_cycle_du_niveau.


def _lire_sequences_du_niveau(conn: sqlite3.Connection,
                                niveau: str,
                                cycle_code: str) -> list[dict]:
    """Liste toutes les séquences-niveau du niveau, ordonnées par numéro
    de séquence du cycle. Une séquence non encore assemblée par
    l'enseignant n'apparaît pas (elle n'est pas dans
    sequences_par_niveau).

    **Param `cycle_code` (v0.12.1.1)** : indispensable pour filtrer la
    jointure sur `sequences_du_cycle`. Sans lui, un même `sequence_code`
    (ex. 'S01') matcherait à la fois sur la ligne C03 (« Nombres
    entiers », cycle 3 / 6e) ET sur la ligne C04 (« Représentations
    d'un nombre », cycle 4 / 5e-4e-3e), produisant une duplication
    avec deux noms différents par séquence-niveau. Le filtre rétablit
    une correspondance 1-pour-1.

    Retourne une liste de dicts :
        {
          'sn_id': str,            # id de la séquence par niveau
          'sequence_code': str,    # 'S01', 'S02'…
          'numero': int,           # 1, 2, …
          'nom': str,              # 'Représentations d'un nombre'
          'theme_code_couleur': str,  # 'nombres', 'donnees'…
        }

    Le résultat ne contient PAS les parties — celles-ci seront chargées
    par `_lire_parties_de_sequence`.
    """
    cur = conn.execute("""
        SELECT
            spn.id              AS sn_id,
            spn.sequence_code   AS sequence_code,
            sdc.numero          AS numero,
            sdc.nom             AS nom,
            COALESCE(th.code_couleur, '')  AS theme_code_couleur
        FROM sequences_par_niveau spn
        JOIN sequences_du_cycle sdc
          ON spn.sequence_code = sdc.code
         AND sdc.cycle_code = ?
        LEFT JOIN themes th ON sdc.theme_id = th.id
        WHERE spn.niveau = ?
        ORDER BY sdc.numero
    """, (cycle_code, niveau))
    return [dict(r) for r in cur.fetchall()]


def _lire_parties_de_sequence(conn: sqlite3.Connection,
                                sn_id: str) -> list[dict]:
    """Liste les parties d'une séquence-niveau, ordonnées par numéro,
    avec leur nb_seances_R_AE et leurs exos R+EA.

    Retourne :
        [
          {
            'partie_id': str,
            'numero': int,
            'nb_seances_R_AE': float,
            'exos_R': list[int],   # numéros d'ordre des exos R dans la partie
            'exos_EA': list[int],  # idem pour EA
          }, …
        ]
    """
    cur = conn.execute("""
        SELECT id, numero,
               COALESCE(nb_seances_R_AE, 0) AS nb_seances_R_AE
        FROM sequence_parties
        WHERE sequence_par_niveau_id = ?
        ORDER BY numero
    """, (sn_id,))
    parties = []
    for r in cur.fetchall():
        partie_id = r['id']
        # Exos R + EA dans l'ordre d'assemblage (rang dans la partie)
        cur_ra = conn.execute("""
            SELECT type, ordre
            FROM partie_exos_revision_approche
            WHERE partie_id = ?
            ORDER BY type, ordre
        """, (partie_id,))
        exos_R = []
        exos_EA = []
        for rr in cur_ra.fetchall():
            if rr['type'] == 'R':
                exos_R.append(rr['ordre'])
            elif rr['type'] == 'EA':
                exos_EA.append(rr['ordre'])
        parties.append({
            'partie_id': partie_id,
            'numero': r['numero'],
            'nb_seances_R_AE': r['nb_seances_R_AE'],
            'exos_R': exos_R,
            'exos_EA': exos_EA,
        })
    return parties


def _lire_objectifs_de_partie(conn: sqlite3.Connection,
                                partie_id: str) -> list[dict]:
    """Liste les objectifs d'une partie, ordonnés par code.

    Pour chaque objectif :
        {
          'id': str,
          'code': str,           # '01', '02', '11'…
          'nom': str,
          'nb_seances': float,
          'notions_titres': list[str],  # noms des notions liées (ordre)
          'exos_F': list[int],   # numéros d'ordre dans la série F
          'exos_A': list[int],
          'exos_E': list[int],
        }
    """
    cur = conn.execute("""
        SELECT id, code, nom,
               COALESCE(nb_seances, 0) AS nb_seances
        FROM objectifs
        WHERE partie_id = ?
        ORDER BY code
    """, (partie_id,))
    objectifs = []
    for r in cur.fetchall():
        obj_id = r['id']
        # Notions liées (titres, dans l'ordre de la table objectif_notions)
        cur_n = conn.execute("""
            SELECT n.titre
            FROM objectif_notions on_
            JOIN notions n ON n.id = on_.notion_id
            WHERE on_.objectif_id = ?
            ORDER BY on_.ordre, n.titre
        """, (obj_id,))
        notions_titres = [
            row['titre'] for row in cur_n.fetchall()
            if row['titre']  # ignore les notions à titre vide
        ]
        # Exos par série, dans l'ordre d'assemblage
        cur_e = conn.execute("""
            SELECT serie, ordre
            FROM objectif_exos
            WHERE objectif_id = ?
            ORDER BY serie, ordre
        """, (obj_id,))
        exos_F, exos_A, exos_E = [], [], []
        for re in cur_e.fetchall():
            if re['serie'] == 'F':
                exos_F.append(re['ordre'])
            elif re['serie'] == 'A':
                exos_A.append(re['ordre'])
            elif re['serie'] == 'E':
                exos_E.append(re['ordre'])
        objectifs.append({
            'id': obj_id,
            'code': r['code'],
            'nom': r['nom'] or '',
            'nb_seances': r['nb_seances'],
            'notions_titres': notions_titres,
            'exos_F': exos_F,
            'exos_A': exos_A,
            'exos_E': exos_E,
        })
    return objectifs


# ── Calculs ──────────────────────────────────────────────────────────────────

def _calculer_total_partie(partie: dict, objectifs: list[dict]) -> float:
    """Total des séances pour une partie : nb_seances_R_AE + somme des
    nb_seances de tous les objectifs (cours + exos confondus).

    Cohérent avec le 'total partie' affiché dans l'UI d'assemblage.
    """
    total = float(partie.get('nb_seances_R_AE') or 0)
    for o in objectifs:
        total += float(o.get('nb_seances') or 0)
    return total


def _est_objectif_cours(code_obj: str, numero_partie: int) -> bool:
    """Convention : l'objectif "cours" d'une partie a le code formé du
    chiffre `numero_partie - 1` suivi de '1' :
      partie 1 → code '01'
      partie 2 → code '11'
      partie 3 → code '21'
    """
    if not code_obj:
        return False
    attendu = f"{numero_partie - 1}1"
    return code_obj == attendu


# ── Formatage LaTeX ──────────────────────────────────────────────────────────

def _fmt_seances(n) -> str:
    """Formate un nombre de séances pour insertion LaTeX dans la liste
    « Repères temporels ». 0 → '\\ldots' (laisse à compléter à la main),
    entier → '2', décimal → '1,5' (virgule française).
    """
    if n is None:
        return r'\ldots'
    f = float(n)
    if f == 0:
        return r'\ldots'
    if f == int(f):
        return str(int(f))
    return f"{f:.1f}".replace('.', ',')


def _fmt_total_seances(total: float) -> str:
    """Comme _fmt_seances mais pour le total partie. 0 → '\\ldots'."""
    if total == 0:
        return r'\ldots'
    if total == int(total):
        return str(int(total))
    return f"{total:.1f}".replace('.', ',')


def _fmt_liste_exos(exos: list[int]) -> str:
    """Formate une liste de numéros d'exos pour le tex.
    Liste vide → '-' (convention paquet seqenseigne).
    """
    if not exos:
        return '-'
    return ','.join(str(n) for n in exos)


def _echapper_texte(s: str) -> str:
    """Échappement très minimal pour insertion dans des titres / noms.

    **Philosophie** : les noms d'objectifs et de notions saisis par
    l'enseignant peuvent contenir du **LaTeX intentionnel** (formules
    mathématiques `$x^2$`, accents `\\og`, espaces fines `\\;`,
    constructions `\\mbox{}` etc.) qu'on ne veut surtout pas
    neutraliser. Le service `livret_recap_cours.py` adopte la même
    approche pour les mêmes raisons (cf. son commentaire sur
    `_echapper`).

    On ne touche donc à rien — l'enseignant est responsable de
    l'échappement à la saisie. C'est cohérent avec le contrat des
    autres services de génération de livrets et avec le fait que
    les noms passent en BDD tels quels (pas de pré-traitement à
    l'écriture).

    Si une saisie utilisateur contient un caractère qui casse la
    compilation (ex. `&` brut hors d'un tableau), c'est à
    l'enseignant de corriger côté UI — l'erreur LaTeX est plus
    informative que ce qu'un échappement aveugle pourrait produire,
    et on évite d'invalider des saisies LaTeX volontaires.
    """
    return s or ''


# ── Émetteurs LaTeX par bloc ─────────────────────────────────────────────────

def _emettre_bloc_reperes(partie_num: int,
                           parties_count: int,
                           partie: dict,
                           objectifs: list[dict]) -> list[str]:
    """Émet le bloc 2-colonnes « Repères temporels » | « Niveaux atteints ».

    Reproduit \\seqPlanReperesNiveaux mais en LaTeX direct, à partir des
    données BDD passées en paramètres. Pas de dépendance .dbtex.

    `partie_num` : 1, 2, 3 — numéro de la partie courante.
    `parties_count` : nombre total de parties de la séquence (pour
                       décider si on affiche « N partie » ou pas).
    """
    lignes = []
    # Calcul du total partie
    total = _calculer_total_partie(partie, objectifs)
    # Repérage de l'objectif cours et des objectifs d'exo
    obj_cours = next(
        (o for o in objectifs if _est_objectif_cours(o['code'], partie_num)),
        None,
    )
    objs_exo = [
        o for o in objectifs
        if not _est_objectif_cours(o['code'], partie_num)
    ]

    lignes.append(r'\begin{multicols}{2}')
    # ── Colonne 1 : Repères temporels ──
    lignes.append(r'\begin{blocReperesNiveaux}{Repères temporels}')
    lignes.append(r'\item Dates: du \ldots/\ldots~au~\ldots/\ldots')
    lignes.append(
        rf'\item Travail en classe: {_fmt_total_seances(total)}~séances'
    )
    lignes.append(r'\begin{seqColItem}[nbCols=1,label=\ding{51}]')
    lignes.append(
        rf'\item Révisions: '
        rf'{_fmt_seances(partie.get("nb_seances_R_AE"))}~séances'
    )
    if obj_cours is not None:
        lignes.append(
            rf'\item Cours: {_fmt_seances(obj_cours.get("nb_seances"))}~séances'
        )
    for o in objs_exo:
        lignes.append(
            rf'\item Objectif {o["code"]}: '
            rf'{_fmt_seances(o.get("nb_seances"))}~séances'
        )
    lignes.append(r'\end{seqColItem}')
    lignes.append(r'\end{blocReperesNiveaux}')
    lignes.append(r'\columnbreak')
    # ── Colonne 2 : Niveaux atteints ──
    lignes.append(r'\begin{blocReperesNiveaux}{Niveaux atteints}')
    if obj_cours is not None:
        lignes.append(
            rf'\item Objectif {obj_cours["code"]}: \ldots'
        )
    for o in objs_exo:
        lignes.append(rf'\item Objectif {o["code"]}: \ldots')
    lignes.append(
        r'\item \begin{minipage}[c][3em][c]{\linewidth} '
        r'\textbf{Note équivalente: \ldots/20} \end{minipage}'
    )
    lignes.append(r'\end{blocReperesNiveaux}')
    lignes.append(r'\end{multicols}')
    return lignes


def _emettre_bloc_revisions(partie: dict) -> list[str]:
    """Émet le bloc « Révisions et découverte » (renommé v0.12.1).

    Affiche deux lignes :
      - Révisions: <liste exos R, ou ->
      - Découverte: <liste exos EA, ou ->

    Si la partie n'a aucun exo R ni EA, le bloc affiche '-' sur les
    deux lignes (cohérent avec les exemples de Laurent où certaines
    séquences n'ont pas de révisions ni de découverte).

    NB : Le titre de `boitePaleNoBreak` doit être encadré par des
    accolades doubles `{{...}}` parce que tcolorbox parse son argument
    comme une liste de clés `key=value` et les virgules dans le titre
    seraient sinon interprétées comme des séparateurs (cause du bug
    « Incomplete \\iffalse » lors des compilations agrégées). Voir
    aussi `_emettre_objectif_exo` pour le même mécanisme.
    """
    lignes = []
    lignes.append(
        r'\begin{boitePaleNoBreak}{{\textbf{Révisions et découverte}}}'
    )
    lignes.append(r'\begin{seqColItem}[nbCols=1,label=\ding{109}]')
    liste_R = _fmt_liste_exos(partie['exos_R'])
    liste_EA = _fmt_liste_exos(partie['exos_EA'])
    lignes.append(rf'\item Révisions: {liste_R}')
    lignes.append(rf'\item Découverte: {liste_EA}')
    lignes.append(r'\end{seqColItem}')
    lignes.append(r'\end{boitePaleNoBreak}')
    return lignes


def _emettre_objectif_exo(o: dict) -> list[str]:
    """Émet un bloc d'objectif (non-cours) : nom + notions + listes F/A/E.

    Reproduit \\seqPlanObjectif mais en LaTeX direct, en passant le nom
    de l'objectif et les noms des notions résolus depuis la BDD.

    NB : Le titre de `boitePaleNoBreak` est encadré par des accolades
    doubles `{{\\begin{minipage}…\\end{minipage}}}`. tcolorbox parse
    l'argument titre comme une liste `key=value`, donc une virgule
    dans le titre (ex. « Pour les nombres décimaux, passer… ») est
    interprétée comme séparateur de clé et plante avec une erreur
    « Incomplete \\iffalse ». Le double `{{...}}` force tcolorbox à
    traiter le contenu comme un seul argument littéral.
    """
    lignes = []
    nom_obj = _echapper_texte(o['nom']) or '(sans nom)'
    lignes.append(
        r'\begin{boitePaleNoBreak}'
        r'{{\begin{minipage}{0.6\textwidth} '
        rf'\textbf{{{o["code"]}}}: {nom_obj} '
        r'\end{minipage}}}'
    )
    # Notions
    if o['notions_titres']:
        notions_fmt = ', '.join(
            rf'\og {_echapper_texte(t)} \fg{{}}'
            for t in o['notions_titres']
        )
    else:
        notions_fmt = '-'
    lignes.append(r'\begin{seqColItem}[nbCols=1,label=\ding{109}]')
    lignes.append(rf'\item Notions: {notions_fmt}')
    lignes.append(r'\end{seqColItem}')
    # Listes F / A / E
    exos_F = _fmt_liste_exos(o['exos_F'])
    exos_A = _fmt_liste_exos(o['exos_A'])
    exos_E = _fmt_liste_exos(o['exos_E'])
    lignes.append(r'\begin{itemize*}[label=\qquad\ding{109}]')
    lignes.append(rf'\item Série fondamentale: {exos_F} ')
    lignes.append(rf'\item Série avancée: {exos_A} ')
    lignes.append(rf'\item Série exploration: {exos_E}')
    lignes.append(r'\end{itemize*}')
    lignes.append(r'\end{boitePaleNoBreak}')
    return lignes


# ── Page de titre ────────────────────────────────────────────────────────────

def _emettre_page_titre(niveau: str) -> list[str]:
    """Page de titre minimaliste. Année / collège / classe restent à
    \\ldots — l'élève les complète à la rentrée à la main.
    """
    lignes = []
    libelle = LIBELLES_NIVEAUX_LATEX.get(niveau, niveau)
    lignes.append(r'\thispagestyle{empty}')
    lignes.append(r'\begin{center}')
    lignes.append(r'\vspace*{4em}')
    lignes.append(r'{\Huge\bfseries Plans de travail}\\[2em]')
    lignes.append(rf'{{\LARGE Classe de {libelle}}}\\[4em]')
    lignes.append(r'\vfill')
    lignes.append(r'{\large \textit{Année}\ \ldots/\ldots}\\[1em]')
    lignes.append(r'{\large \textit{Établissement}\ \ldots}\\[1em]')
    lignes.append(r'{\large \textit{Classe}\ \ldots}')
    lignes.append(r'\vspace*{4em}')
    lignes.append(r'\end{center}')
    lignes.append(r'\newpage')
    return lignes


# ── Page d'une partie ────────────────────────────────────────────────────────

def _suffixe_partie(partie_num: int, parties_count: int) -> str:
    """Si la séquence a plusieurs parties, retourne le suffixe '(1\\iere{}
    partie)' / '(2\\ieme{} partie)' etc. Si une seule partie, chaîne vide.
    """
    if parties_count <= 1:
        return ''
    if partie_num == 1:
        return r' (1\iere{} partie)'
    return rf' ({partie_num}\ieme{{}} partie)'


def _emettre_page_partie(seq: dict,
                          partie: dict,
                          objectifs: list[dict],
                          parties_count: int) -> list[str]:
    """Émet une page entière de plan de travail pour (séquence, partie)."""
    lignes = []
    sequence_code = seq['sequence_code']
    nom_seq = _echapper_texte(seq['nom'])
    suffixe = _suffixe_partie(partie['numero'], parties_count)

    # Activation des couleurs de thème pour cette séquence
    lignes.append(rf'\seqSetCodeSequence{{{sequence_code}}}')
    if seq.get('theme_code_couleur'):
        lignes.append(rf'\seqSetColorsTheme{{{seq["theme_code_couleur"]}}}')
    lignes.append(r'\newpage')
    # Boîte de titre : on reproduit la mécanique de \seqBoiteTitrePlan
    # mais sans dépendance \seqSequenceGetNom (lu depuis la BDD côté Python).
    # \seqBoiteTitrePlan accepte un titre libre, on lui passe le nom déjà
    # résolu pour qu'il s'affiche dans la boîte. afficheSeq=oui (par
    # défaut) → la boîte affiche bien « Séquence Sxx » dans son en-tête.
    lignes.append(
        rf'\seqBoiteTitrePlan[titre={{{nom_seq}{suffixe}}}]'
    )
    # Bloc 2-colonnes Repères temporels / Niveaux atteints
    lignes.extend(
        _emettre_bloc_reperes(
            partie['numero'], parties_count, partie, objectifs,
        )
    )
    # Bloc Révisions
    lignes.extend(_emettre_bloc_revisions(partie))
    # Pour chaque objectif d'exo, son bloc \seqPlanObjectif équivalent
    for o in objectifs:
        if _est_objectif_cours(o['code'], partie['numero']):
            continue
        lignes.extend(_emettre_objectif_exo(o))
    return lignes


# ── Génération principale ────────────────────────────────────────────────────

# Macros et environnements utilisés par le livret (pour le préambule
# sur mesure). Ces noms doivent matcher exactement ceux indexés dans la
# table `paquet_definitions` lors du peuplement_14 :
#   - les commandes LaTeX (`\newcommand`) sont indexées avec leur `\` initial
#     (ex. `\seqBoiteTitrePlan`)
#   - les environnements `tcolorbox` (`\newtcolorbox`) sont indexés sans
#     `\` initial (ex. `boitePaleNoBreak`)
#   - les environnements LaTeX classiques (`\newenvironment`) sont indexés
#     sans `\` initial (ex. `blocReperesNiveaux`, `seqColItem`)
#
# `construire_preambule` filtre la graine sur `set(index.keys())`, donc
# tout nom mal orthographié est silencieusement ignoré (pas d'erreur,
# juste une définition manquante au runtime LaTeX).
_MACROS_LIVRET = {
    # Commandes (préfixe \ obligatoire, cf. paquet_definitions.nom)
    '\\seqBoiteTitrePlan',
    '\\seqSetCodeSequence',
    '\\seqSetCodeNiveau',
    '\\seqSetColorsTheme',
    '\\seqCreeCompteurs',
}

_ENVIRONNEMENTS_LIVRET = {
    # tcolorbox (sans backslash)
    'boitePaleNoBreak',
    'boiteTitreGen',
    # newenvironment (sans backslash)
    'blocReperesNiveaux',
    'seqColItem',
    # `multicols`, `itemize*`, `minipage`, `center`, `tabular` etc. sont
    # fournis par les paquets noyau (multicol, enumitem) chargés
    # systématiquement par construire_preambule — pas besoin de les
    # mentionner ici.
}


# Macros qui ont `statut_rendu_atome='ignore'` dans paquet_definitions
# (parce qu'elles ne sont pas pertinentes pour un rendu d'atome isolé)
# mais que **ce livret** a besoin d'inliner explicitement. La fermeture
# transitive de `construire_preambule` ne les inclut pas, mais leurs
# DÉPENDANCES (qui sont en statut 'reutilise') sont tirées normalement
# tant que la macro figure dans la graine `_MACROS_LIVRET`.
#
# Le texte_complet est récupéré depuis paquet_definitions au moment de
# la génération et inséré juste après le préambule.
_MACROS_A_INLINER = (
    r'\seqBoiteTitrePlan',
)


def _recuperer_texte_macro(conn: sqlite3.Connection, nom: str) -> str:
    """Récupère le `texte_complet` d'une définition du paquet par son
    nom canonique (avec `\\` initial pour les commandes).

    Lève LookupError si la définition n'existe pas. Robustesse : on ne
    gère pas le cas d'un paquet pas peuplé — c'est un état pathologique
    qui doit être détecté tôt.
    """
    row = conn.execute(
        "SELECT texte_complet FROM paquet_definitions WHERE nom = ?",
        (nom,),
    ).fetchone()
    if not row:
        raise LookupError(
            f"Définition introuvable dans paquet_definitions : {nom!r}. "
            "Le paquet seqenseigne n'a peut-être pas été peuplé "
            "(scripts/peuplement_14_paquet_vers_base.py)."
        )
    return row['texte_complet']


def generer_livret_plans_de_travail(conn: sqlite3.Connection,
                                      niveau: str,
                                      tikz_libraries: list[str] | None = None,
                                      tblr_libraries: list[str] | None = None,
                                      ) -> str:
    """Génère le source LaTeX complet du livret annuel des plans de
    travail pour un niveau (N09, N10, N11, N12).

    Paramètres :
        conn          — connexion sqlite3 (row_factory=Row recommandée).
        niveau        — code de niveau ('N09', 'N10', 'N11', 'N12').
        tikz_libraries / tblr_libraries — listes de bibliothèques
            additionnelles à charger dans le préambule (passées telles
            quelles à `construire_preambule`).

    Retour : string `.tex` complet (documentclass + préambule + document).
    """
    cycle_code = lire_cycle(conn, niveau)
    sequences = _lire_sequences_du_niveau(conn, niveau, cycle_code)

    # 1. Construction du préambule sur mesure.
    # On passe directement nos ensembles de macros et d'environnements ;
    # `construire_preambule` calcule la fermeture transitive sur le
    # graphe paquet_definitions à partir de cet ensemble graine.
    preambule = construire_preambule(
        conn, 'exercice',
        macros_atome=_MACROS_LIVRET,
        envs_atome=_ENVIRONNEMENTS_LIVRET,
        options_atome=[],
        paquets_tex_supplementaires=[],
        tikz_libraries=tikz_libraries,
        tblr_libraries=tblr_libraries,
    )

    # 2. Assemblage du .tex.
    L: list[str] = []
    L.append(r'%% Livret annuel des plans de travail — généré v0.12.1')
    L.append(rf'%% Niveau : {niveau} (cycle {cycle_code})')
    L.append('')
    L.append(r'\documentclass[a4paper,11pt]{article}')
    L.append('')
    L.append(preambule.texte)
    L.append('')
    # v0.12.1 — Inliner les macros qui sont marquées `ignore` dans
    # paquet_definitions (donc filtrées par `construire_preambule`)
    # mais que ce livret a besoin d'utiliser. Les dépendances de ces
    # macros sont déjà tirées par la fermeture transitive ci-dessus
    # parce qu'elles figurent en graine `_MACROS_LIVRET`.
    #
    # IMPORTANT : ces macros utilisent des identificateurs avec `@`
    # (ex. `\cmdseq@boiteTitrePlan@afficheSeq` créés via xkeyval). Le
    # préambule construit par `construire_preambule` se ferme par
    # `\makeatother`, donc on doit ré-ouvrir la zone `@`-letter pour
    # définir nos macros sans casser le scope du préambule principal.
    L.append(r'%% v0.12.1 — Définitions complémentaires (macros marquées')
    L.append(r'%% "ignore" dans paquet_definitions, mais utilisées par le')
    L.append(r'%% livret des plans de travail).')
    L.append(r'\makeatletter')
    for macro in _MACROS_A_INLINER:
        L.append(_recuperer_texte_macro(conn, macro))
    L.append(r'\makeatother')
    L.append('')
    # Paquets supplémentaires nécessaires (lastpage pour le pied de page,
    # fancyhdr pour les en-têtes, datetime pour la commande \datemoisannee
    # éventuellement utilisée dans la boîte de titre).
    L.append(r'\usepackage{lastpage}')
    L.append(r'\usepackage{fancyhdr}')
    L.append(r'\usepackage{datetime}')
    L.append('')
    # Géométrie A4 portrait, marges modérées (proches du tex de
    # référence N10_Plan_de_travail.tex).
    L.append(r'\geometry{vmargin=25pt,hmargin=20pt}')
    L.append(r'\pagestyle{empty}')
    L.append(r'\raggedcolumns')
    L.append('')
    # Format de date français pour la boîte de titre (\datemoisannee\today).
    L.append(r'\newdateformat{datemoisannee}{\monthname\;\THEYEAR}')
    L.append('')
    L.append(r'\begin{document}')
    L.append('')
    # v0.12.1 — Fallbacks pour \theHxxx (hyperref n'est pas chargé par
    # le préambule sur mesure). Sans eux, \seqCreeCompteurs plante avec
    # « Command \theHExoNum undefined ».
    L.append(r'\providecommand{\theHExoNum}{\theExoNum}')
    L.append(r'\providecommand{\theHNotionNum}{\theNotionNum}')
    L.append(r'\providecommand{\theHMethodeNum}{\theMethodeNum}')
    L.append(r'\providecommand{\theHDefinitionNum}{\theDefinitionNum}')
    L.append(r'\providecommand{\theHProprieteNum}{\theProprieteNum}')
    L.append('')
    # Compteurs nécessaires aux environnements (seqExercice etc. pas
    # utilisés ici, mais seqCreeCompteurs est sans effet de bord).
    L.append(r'\seqCreeCompteurs')
    L.append(rf'\seqSetCodeNiveau{{{niveau}}}')
    L.append(r'\seqSetCodeSequence{S00}')
    L.append('')
    # 3. Page de titre
    L.extend(_emettre_page_titre(niveau))
    L.append('')
    # 4. Une page par (séquence-niveau, partie)
    for seq in sequences:
        parties = _lire_parties_de_sequence(conn, seq['sn_id'])
        if not parties:
            # Séquence-niveau créée mais sans aucune partie : on saute.
            continue
        parties_count = len(parties)
        for partie in parties:
            objectifs = _lire_objectifs_de_partie(conn, partie['partie_id'])
            L.extend(_emettre_page_partie(
                seq, partie, objectifs, parties_count,
            ))
            L.append('')
    L.append(r'\end{document}')
    return '\n'.join(L)


# ── Portée séquence (v0.12.1.2) ──────────────────────────────────────────────

class SequenceParNiveauIntrouvable(LookupError):
    """Levée par `generer_plan_de_travail_sequence` quand le couple
    (niveau, sequence_code) n'est pas dans `sequences_par_niveau` (ou
    l'est mais sans aucune partie). Permet aux routes HTTP de renvoyer
    un 404 plutôt qu'un 500.
    """
    def __init__(self, niveau: str, sequence_code: str, motif: str = ''):
        msg = (f"Séquence-niveau introuvable : {niveau} / {sequence_code}"
               + (f" ({motif})" if motif else ''))
        super().__init__(msg)
        self.niveau = niveau
        self.sequence_code = sequence_code
        self.motif = motif


def generer_plan_de_travail_sequence(conn: sqlite3.Connection,
                                       niveau: str,
                                       sequence_code: str,
                                       tikz_libraries: list[str] | None = None,
                                       tblr_libraries: list[str] | None = None,
                                       ) -> str:
    """Génère le plan de travail d'une seule séquence-niveau.

    Sortie : une page par partie, *sans page de titre* (calqué sur le
    livret de séquence). Pratique pour vérifier rapidement le rendu
    pendant l'édition de la séquence.

    Paramètres :
        conn          — connexion sqlite3 (row_factory=Row recommandée).
        niveau        — code de niveau ('N09'..'N12').
        sequence_code — code séquence ('S01'..'S14').
        tikz_libraries / tblr_libraries — listes additionnelles passées
            telles quelles à `construire_preambule`.

    Lève `SequenceParNiveauIntrouvable` si :
      - le couple (niveau, sequence_code) n'existe pas dans
        `sequences_par_niveau`, OU
      - la séquence-niveau existe mais n'a aucune partie (rien à émettre).

    Retour : string `.tex` complet (documentclass + préambule + document).
    """
    cycle_code = lire_cycle(conn, niveau)
    sequences = _lire_sequences_du_niveau(conn, niveau, cycle_code)
    seq = next((s for s in sequences if s['sequence_code'] == sequence_code), None)
    if seq is None:
        raise SequenceParNiveauIntrouvable(
            niveau, sequence_code,
            "non trouvée dans sequences_par_niveau"
        )
    parties = _lire_parties_de_sequence(conn, seq['sn_id'])
    if not parties:
        raise SequenceParNiveauIntrouvable(
            niveau, sequence_code,
            "aucune partie assemblée"
        )

    # 1. Préambule (idem livret niveau).
    preambule = construire_preambule(
        conn, 'exercice',
        macros_atome=_MACROS_LIVRET,
        envs_atome=_ENVIRONNEMENTS_LIVRET,
        options_atome=[],
        paquets_tex_supplementaires=[],
        tikz_libraries=tikz_libraries,
        tblr_libraries=tblr_libraries,
    )

    # 2. Assemblage du .tex (entête identique au livret niveau, sauf qu'on
    # ne génère PAS de page de titre).
    L: list[str] = []
    L.append(r'%% Plan de travail (portée séquence) — généré v0.12.1.2')
    L.append(rf'%% Niveau : {niveau} (cycle {cycle_code})')
    L.append(rf'%% Séquence : {sequence_code}')
    L.append('')
    L.append(r'\documentclass[a4paper,11pt]{article}')
    L.append('')
    L.append(preambule.texte)
    L.append('')
    L.append(r'%% v0.12.1 — Définitions complémentaires (macros marquées')
    L.append(r'%% "ignore" dans paquet_definitions, mais utilisées par le')
    L.append(r'%% plan de travail).')
    L.append(r'\makeatletter')
    for macro in _MACROS_A_INLINER:
        L.append(_recuperer_texte_macro(conn, macro))
    L.append(r'\makeatother')
    L.append('')
    L.append(r'\usepackage{lastpage}')
    L.append(r'\usepackage{fancyhdr}')
    L.append(r'\usepackage{datetime}')
    L.append('')
    L.append(r'\geometry{vmargin=25pt,hmargin=20pt}')
    L.append(r'\pagestyle{empty}')
    L.append(r'\raggedcolumns')
    L.append('')
    L.append(r'\newdateformat{datemoisannee}{\monthname\;\THEYEAR}')
    L.append('')
    L.append(r'\begin{document}')
    L.append('')
    L.append(r'\providecommand{\theHExoNum}{\theExoNum}')
    L.append(r'\providecommand{\theHNotionNum}{\theNotionNum}')
    L.append(r'\providecommand{\theHMethodeNum}{\theMethodeNum}')
    L.append(r'\providecommand{\theHDefinitionNum}{\theDefinitionNum}')
    L.append(r'\providecommand{\theHProprieteNum}{\theProprieteNum}')
    L.append('')
    L.append(r'\seqCreeCompteurs')
    L.append(rf'\seqSetCodeNiveau{{{niveau}}}')
    L.append(rf'\seqSetCodeSequence{{{sequence_code}}}')
    L.append('')
    # 3. Une page par partie de la séquence (pas de page de titre).
    parties_count = len(parties)
    for partie in parties:
        objectifs = _lire_objectifs_de_partie(conn, partie['partie_id'])
        L.extend(_emettre_page_partie(
            seq, partie, objectifs, parties_count,
        ))
        L.append('')
    L.append(r'\end{document}')
    return '\n'.join(L)
