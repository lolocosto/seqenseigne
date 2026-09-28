r"""
services/livret_recap_exos.py — Génération du Livret d'exercices d'un niveau.

Produit le source LaTeX d'un livret agrégeant **tous les exercices d'un
niveau**, organisé par thème → séquence → série (Activités d'approche /
Fondamentale / Avancée / Exploration). Les corrigés sont **groupés à la
fin du livret, par séquence**.

Indépendant de Flask : prend une connexion sqlite3 et un code de niveau,
retourne une chaîne .tex prête à être compilée par pdflatex.

API
---
generer_recap_exos(conn, niveau) -> str
    Retourne le source .tex complet (documentclass + préambule + document).

Architecture
------------
Calque livret_recap_cours.py mais pour les exercices :
- On parcourt thèmes → séquences → séries → exos.
- Pour chaque exo, on génère un mini-bloc \\begin{seqExercice}...\\end{seqExercice}
  qu'on encadre dans \\begin{seqSerieExos}{N}...\\end{seqSerieExos}.
- Numérotation reset par séquence ET par série (l'utilisateur l'a demandé).
- Préambule construit sur mesure via construire_preambule (comme recap_cours).

Conflits techniques résolus
---------------------------
Le paquet seqenseigne stocke chaque corrigé d'exercice dans le fichier
``Corriges/c\\theSerieExosNum e\\theExoNum.tex``. Si on agrège plusieurs
séquences avec chacune une « série fondamentale » (SerieExosNum=1), tous
les exercices N°1 de série fondamentale écraseraient leurs corrigés
mutuels (collision sur le nom ``Corriges/c1e1.tex``). Idem pour les
labels ``\\label{exo:1-1}`` qui généreraient des doublons.

**Astuce option 2** : juste après ``\\begin{seqSerieExos}{X}``, on
ré-affecte ``\\setcounter{SerieExosNum}{<unique>}`` avec une valeur
unique au couple (séquence, série). Ainsi :
- le titre « Série fondamentale/avancée/exploration/révisions » a déjà
  été décidé sur la base de X (1/2/3/0) avant qu'on touche au compteur ;
- les fichiers Corriges/cNeM.tex auront des noms uniques ;
- les labels exo:N-M seront uniques.

Conséquence : pour grouper les corrigés par séquence à la fin du livret,
on intervient directement dans le flux d'écriture vers ``CorrList.tex``
via ``\\immediate\\write\\corrfile{...}`` pour insérer des titres entre
les blocs de corrigés de chaque séquence.

Le label ``\\label{corrigeExos\\theSerieExosNum}`` émis par
``\\seq@ecrit@corrige@serieExos`` est en doublon (X=1/2/3 répété entre
séquences) — mais c'est juste un warning LaTeX et non une erreur ; la
``\\pageref{corrigeExos1}`` du paquet pointera vers la dernière séquence,
mais on n'utilise pas cette pageref dans le récap (on a notre propre
structure de corrigés à la fin).
"""

from __future__ import annotations

import sqlite3

from services.latex_rendu_atome import (
    Atome,
    charger_atome,
    detecter_options_paquet,
    detecter_paquets_tex_manquants,
    resoudre_macros_csv,
)
from services.preambule_atome import construire_preambule
from services.paquet_parseur import extraire_utilisations
from services.param_niveaux import lire_cycle


# ── Constantes de structure ──────────────────────────────────────────────────

# Libellés des niveaux pour la page de garde.
LIBELLES_NIVEAUX = {
    'N09': '6\\ieme{}',
    'N10': '5\\ieme{}',
    'N11': '4\\ieme{}',
    'N12': '3\\ieme{}',
}

# Mapping serie_code (BDD) → numéro pour seqSerieExos.
# Les codes BDD sont 'F', 'A', 'E', 'AE'. Le paquet attend :
#   0 = Révisions, 1 = Fondamentale, 2 = Avancée, 3 = Exploration.
# Les AE (« Activités d'approche » en début de séquence pour les notions
# sans révision dédiée) sont sémantiquement des révisions → on les mappe
# vers la série 0 du paquet, dont le titre par défaut est « Révisions ».
_NUM_SERIE_PAR_CODE = {
    'AE': 0,
    'F':  1,
    'A':  2,
    'E':  3,
}

# Ordre d'affichage des séries dans une séquence : Activités d'approche
# d'abord (début de séquence), puis F → A → E.
_ORDRE_SERIES = ['AE', 'F', 'A', 'E']

# Libellés français pour la table des matières / titres internes.
LIBELLES_SERIES = {
    'AE': 'Activités d\'approche',
    'F':  'Série fondamentale',
    'A':  'Série avancée',
    'E':  'Série exploration',
}


# ── Récupération des données ─────────────────────────────────────────────────

# v0.15.5 — `_cycle_du_niveau` local supprimé. Le cycle d'un niveau se lit
# désormais via `services.param_niveaux.lire_cycle`, source unique de vérité
# (table `param_niveaux`). L'ancienne implémentation faisait une jointure
# `sequences_par_niveau × sequences_du_cycle` + `LIMIT 1` SANS filtre cycle,
# qui remontait C03 pour N10/N12 quand un code de séquence (ex. S01) existe
# à la fois en C03 et C04. Cf. test_v0_15_5_cycle_du_niveau.


def _lire_themes_du_cycle(conn: sqlite3.Connection,
                           cycle_code: str) -> list[dict]:
    """Liste les thèmes du cycle, dans l'ordre d'affichage."""
    cur = conn.execute("""
        SELECT id, code, nom, description, code_couleur, ordre
        FROM themes
        WHERE cycle_code = ?
        ORDER BY ordre
    """, (cycle_code,))
    return [dict(r) for r in cur.fetchall()]


def _lire_sequences_du_theme(conn: sqlite3.Connection,
                              theme_id: str) -> list[dict]:
    """Liste les séquences appartenant au thème (par theme_id), par numéro
    croissant."""
    cur = conn.execute("""
        SELECT code, numero, nom
        FROM sequences_du_cycle
        WHERE theme_id = ?
        ORDER BY numero
    """, (theme_id,))
    return [dict(r) for r in cur.fetchall()]


def _lire_exos_de_sequence_par_serie(conn: sqlite3.Connection,
                                      niveau: str,
                                      sequence: str) -> dict[str, list[str]]:
    """Récupère les exos d'une séquence groupés par serie_code.

    Returns
    -------
    dict {serie_code: [id, id, ...]} avec les ids triés par num croissant.
    Les séries non présentes sont absentes du dict (pas de clé vide).
    """
    cur = conn.execute("""
        SELECT id, serie_code FROM exercices
        WHERE niveau = ? AND sequence = ?
        ORDER BY serie_code, CAST(num AS INTEGER)
    """, (niveau, sequence))
    out: dict[str, list[str]] = {}
    for r in cur.fetchall():
        out.setdefault(r['serie_code'], []).append(r['id'])
    return out


# ── Génération du corps d'un exercice (avec corrigé) ─────────────────────────

def _generer_corps_exercice_continu(atome: Atome,
                                      inclure_remediation: bool = False,
                                      conn=None,
                                      ) -> tuple[str, str]:
    """Génère le bloc seqExercice pour un exo dans le livret agrégé.

    Différences avec generer_corps_exercice (rendu isolé) :
    - PAS de \\seqInitCorriges / \\seqInitAnnexes (faits une seule fois
      en tête de livret).
    - PAS de \\begin{seqSerieExos} : c'est l'orchestrateur qui le pose,
      une fois pour le bloc de toutes les exos de la même série dans la
      même séquence.
    - PAS de \\seqAfficheAnnexes / \\seqAfficheCorriges : faits une
      seule fois en fin de livret.
    - PAS de \\renewcommand{\\seqCorrigesExos}{oui} : fait une fois en
      tête de livret.
    - PAS de \\setcounter{ExoNum}{...} avec le num de l'atome : la
      numérotation est continue dans la série/séquence (le compteur a
      été reset par l'orchestrateur au début de la série, et incrémenté
      par chaque \\begin{seqExercice} via \\refstepcounter).

    v0.11.6 — Émission conditionnelle :
    - \\seqCadreReponse{N} après l'énoncé si
      atome.cadre_reponse_lignes_principal > 0
    - \\seqRemediation{enonce}{corrige} après \\seqCorrige si
      inclure_remediation=True ET atome a une remédiation non vide.
      Le cadre de réponse de remédiation (\\seqCadreReponse{N}) est
      placé à l'intérieur du premier argument de \\seqRemediation,
      à la suite de l'énoncé de remédiation, si
      atome.cadre_reponse_lignes_remed > 0.

    v0.11.6.2 — Options de \\begin{seqExercice} :
    - obj={code1, code2, ...} si conn fourni et exo lié à des objectifs
      (codes joints par ", " pour gérer le cas multi-objectifs)
    - remediation=oui si inclure_remediation=True et exo a une remédiation
      (active l'affichage de « Remédiation p. XX » dans la boîte de titre
      via le label posé par \\seq@ecrit@remediation@enonce)

    Parameters
    ----------
    atome : Atome
        L'exercice à rendre.
    inclure_remediation : bool, default False
        Si True, émet \\seqRemediation{...}{...} quand l'atome a des
        champs remed_enonce/remed_corrige non vides. Si False, la
        remédiation est ignorée même si l'atome en a (cas du récap exos
        transverse niveau, par exemple, où on ne veut que les énoncés
        principaux). Le livret de séquence passe True.
    conn : sqlite3.Connection or None, default None
        Si fournie, sert à interroger objectif_exos pour passer la liste
        des codes d'objectifs liés à l'exo via l'option obj=. Si None,
        on n'émet pas obj= (rétrocompatible).

    Returns
    -------
    (variables, bloc_exercice)
        variables : le bloc des variables/_param.tex à émettre AVANT le
                    \\begin{seqExercice} (tcolorbox limite la profondeur
                    des \\newcommand imbriqués dans des breakable).
        bloc_exercice : le \\begin{seqExercice}...\\end{seqExercice}
                        complet, prêt à être inséré entre les boîtes.
    """
    variables = ''
    if atome.variables:
        variables = atome.variables.strip()

    # Détection précoce de la remédiation : conditionne à la fois
    # l'émission du bloc \seqRemediation et l'option remediation=oui.
    remed_enonce = (getattr(atome, 'remed_enonce', '') or '').strip()
    remed_corrige = (getattr(atome, 'remed_corrige', '') or '').strip()
    a_remediation = inclure_remediation and (remed_enonce or remed_corrige)

    parties = []
    nom_exo = atome.titre or ''
    opts = []
    if nom_exo:
        opts.append(f'nom={{{nom_exo}}}')
    # v0.11.6.2 — Codes d'objectifs liés à l'exercice
    if conn is not None:
        # Import local pour éviter une dépendance circulaire au top-level
        # (livret_recap_exos est importé par livret_sequence, qui est lui
        # aussi appelé depuis le même graphe que latex_rendu_atome).
        from services.latex_rendu_atome import lire_codes_objectifs_de_exercice
        codes = lire_codes_objectifs_de_exercice(conn, atome.id)
        if codes:
            opts.append('obj={' + ', '.join(codes) + '}')
    # v0.11.6.2 — remediation=oui si l'exo a une remédiation à inclure
    if a_remediation:
        opts.append('remediation=oui')
    opts_str = f'[{",".join(opts)}]' if opts else ''
    parties.append(f'\\begin{{seqExercice}}{opts_str}')
    parties.append((atome.corps or '').strip())

    # v0.11.6 — Cadre de réponse principal (option A : juste après l'énoncé,
    # avant \seqCorrige). Émis seulement si > 0.
    lignes_princ = getattr(atome, 'cadre_reponse_lignes_principal', 0) or 0
    if lignes_princ > 0:
        parties.append(f'\\seqCadreReponse{{{int(lignes_princ)}}}')

    # Corrigé : on émet \seqCorrige même si vide, pour que la machinerie
    # du paquet écrive un fichier Corriges/cNeM.tex (au moins vide). Sinon
    # \seq@ecrit@corrige@Exo va référencer un fichier inexistant via
    # \input{Corriges/cNeM.tex} → erreur fatale au moment de
    # \seqAfficheCorriges.
    corrige_clean = (atome.corrige or '').strip()
    if corrige_clean:
        parties.append(r'\seqCorrige{%')
        parties.append(corrige_clean)
        parties.append('}')
    else:
        # Encart vide explicite. On utilise \emph pour que ça apparaisse
        # discrètement dans le bloc des corrigés, signalant à l'utilisateur
        # qu'il a oublié de rédiger le corrigé.
        parties.append(r'\seqCorrige{%')
        parties.append(r'\emph{Corrigé non rédigé.}')
        parties.append('}')

    # v0.11.6 — Remédiation (paquet seqenseigne ≥ 1.0.5-dev).
    # Émise après \seqCorrige (peu importe l'ordre relatif côté paquet,
    # \seqCorrige et \seqRemediation accumulent indépendamment dans deux
    # streams distincts). Convention v0.11.6 : on n'émet \seqRemediation
    # que si l'énoncé OU le corrigé de remédiation est non vide. Si l'un
    # des deux est vide, on l'envoie quand même au paquet (chaîne vide
    # → \emph{...} de fallback comme pour le corrigé principal).
    # v0.11.6.2 : a_remediation est calculé en début de fonction (booléen
    # qui couvre inclure_remediation ET présence d'au moins un des deux
    # champs). On réutilise les variables remed_enonce/remed_corrige
    # déjà extraites.
    if a_remediation:
        # Préparer l'énoncé (avec cadre de réponse de remédiation
        # éventuel à la suite, comme pour le principal).
        enonce_complet = remed_enonce
        lignes_remed = getattr(atome, 'cadre_reponse_lignes_remed', 0) or 0
        if lignes_remed > 0:
            enonce_complet = (enonce_complet + '\n'
                              + f'\\seqCadreReponse{{{int(lignes_remed)}}}')
        # Fallback sur l'énoncé/corrigé manquant
        if not enonce_complet.strip():
            enonce_complet = r'\emph{Énoncé de remédiation non rédigé.}'
        corrige_remed = remed_corrige or r'\emph{Corrigé de remédiation non rédigé.}'
        parties.append(r'\seqRemediation{%')
        parties.append(enonce_complet)
        parties.append('}{%')
        parties.append(corrige_remed)
        parties.append('}')

    parties.append(r'\end{seqExercice}')
    return variables, '\n'.join(parties)


# ── Génération principale ────────────────────────────────────────────────────

def generer_recap_exos(conn: sqlite3.Connection,
                        niveau: str,
                        tikz_libraries: list[str] | None = None,
                        tblr_libraries: list[str] | None = None) -> str:
    """Génère le source .tex complet du Récap exos pour un niveau.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion à la BDD seqenseigne.
    niveau : str
        Code de niveau ('N09', 'N10', 'N11', 'N12').
    tikz_libraries : list[str], optional
        Bibliothèques tikz à charger via \\usetikzlibrary{...}.
    tblr_libraries : list[str], optional
        Bibliothèques tabularray à charger via \\UseTblrLibrary{...}.

    Returns
    -------
    str
        Source .tex complet, prêt à être compilé.
    """
    # 1. Récupérer la structure thèmes → séquences → séries → exos,
    #    en chargeant chaque exo et en générant son bloc.
    cycle_code = lire_cycle(conn, niveau)
    themes = _lire_themes_du_cycle(conn, cycle_code)

    # On collecte tous les blocs et tous les textes pour pouvoir construire
    # le préambule sur mesure.
    structure = []  # liste de {theme, sequences:[{sequence, series:[{serie_code, num_unique, exos:[(variables,bloc)]}]}]}
    tous_textes_atomes = []

    # Compteur global pour générer un SerieExosNum unique par (séquence, série).
    # On démarre à 100 pour ne pas collisionner avec les valeurs 0/1/2/3 que
    # le paquet utilise pour décider du titre. La valeur 100 et plus va dans
    # la branche \ifnum>3 du switch d'affichage du paquet, mais on intervient
    # APRÈS ce switch — donc le titre est déjà figé sur la base du num passé
    # à \begin{seqSerieExos}.
    compteur_unique = 100

    for theme in themes:
        sequences = _lire_sequences_du_theme(conn, theme['id'])
        seqs_avec_atomes = []
        for seq in sequences:
            exos_par_serie = _lire_exos_de_sequence_par_serie(
                conn, niveau, seq['code'])
            series_de_la_seq = []
            # Collecte des blocs `variables` distincts pour la séquence,
            # à émettre AU NIVEAU TOP du document (avant les seqSerieExos).
            # Les groupes ouverts par seqSerieExos (multicols × boitePale)
            # rendent locales toute définition LaTeX qui y serait émise :
            # les \newcommand disparaissent à \end{seqSerieExos}, et les
            # \xintdef*var aussi (sauf si \xintglobaldefstrue est actif).
            # En sortant les variables au niveau séquence, on garantit que
            # toutes les définitions restent globales pour la suite (énoncé,
            # corrigés lus en fin de livret par \seqAfficheCorriges, etc.).
            #
            # On dédoublonne car le pattern courant est que tous les exos
            # d'une séquence partagent le même bloc complet (audit montre
            # 28 exos × 1 bloc identique pour N11/S03 par ex.). La dédup
            # évite des centaines de \xintdefiivar redondants dans le tex
            # et limite les warnings sur \xint*var déjà défini.
            blocs_variables_seq = []  # liste ordonnée, sans doublons
            blocs_vus = set()
            # Parcourir dans l'ordre canonique
            for code in _ORDRE_SERIES:
                ids = exos_par_serie.get(code, [])
                if not ids:
                    continue
                blocs_exos = []  # liste de bloc_exo (variables sorties au niveau séquence)
                for exo_id in ids:
                    atome = charger_atome(conn, 'exercice', exo_id)
                    # Résoudre les getters CSV (au cas où)
                    atome.corps = resoudre_macros_csv(
                        conn, atome.corps, atome.niveau, atome.sequence)
                    if atome.corrige:
                        atome.corrige = resoudre_macros_csv(
                            conn, atome.corrige,
                            atome.niveau, atome.sequence)
                    if atome.variables:
                        atome.variables = resoudre_macros_csv(
                            conn, atome.variables,
                            atome.niveau, atome.sequence)
                    variables, bloc = _generer_corps_exercice_continu(atome, conn=conn)
                    # Ranger les variables au niveau séquence en dédoublonnant
                    if variables and variables not in blocs_vus:
                        blocs_variables_seq.append(variables)
                        blocs_vus.add(variables)
                    blocs_exos.append(bloc)
                    tous_textes_atomes.append(
                        (atome.corps or '') + (atome.corrige or '') +
                        (atome.variables or '') + bloc)

                compteur_unique += 1
                series_de_la_seq.append({
                    'serie_code': code,
                    'num_paquet': _NUM_SERIE_PAR_CODE[code],
                    'num_unique': compteur_unique,
                    'exos': blocs_exos,
                })

            if series_de_la_seq:
                seqs_avec_atomes.append({
                    'sequence': seq,
                    'variables': blocs_variables_seq,
                    'series': series_de_la_seq,
                })

        if seqs_avec_atomes:
            structure.append({'theme': theme, 'sequences': seqs_avec_atomes})

    # 2. Construire le préambule sur mesure (cf. livret_recap_cours).
    texte_global = '\n'.join(tous_textes_atomes)
    macros_utilisees, envs_utilises = extraire_utilisations(texte_global)
    atome_global = Atome(
        id='_recap_exos_',
        type_atome='exercice',
        niveau=niveau,
        sequence='',
        fichier='',
        corps=texte_global,
    )
    options = detecter_options_paquet(conn, atome_global)
    paquets_manquants = detecter_paquets_tex_manquants(conn, atome_global)

    preambule = construire_preambule(
        conn, 'exercice',
        macros_utilisees, envs_utilises,
        options_atome=options,
        paquets_tex_supplementaires=paquets_manquants,
        tikz_libraries=tikz_libraries,
        tblr_libraries=tblr_libraries,
    )

    # 3. Assemblage du .tex
    lignes: list[str] = []
    lignes.append(r'%% Livret Récap exos — généré pour rendu agrégé.')
    lignes.append(f'%% Niveau : {niveau}')
    lignes.append('')
    lignes.append(r'\documentclass[a4paper,11pt,twoside]{article}')
    lignes.append('')
    lignes.append(preambule.texte)
    lignes.append('')
    # Paquets supplémentaires
    lignes.append(r'\usepackage{titlesec}')
    lignes.append(r'\usepackage{fancyhdr}')
    lignes.append(r'\usepackage{lastpage}')
    lignes.append('')
    lignes.append(r'\geometry{vmargin=70pt,hmargin=50pt,headheight=50pt,'
                  r'headsep=15pt,footskip=20pt}')
    lignes.append('')
    # Entêtes et pieds de page
    lignes.append(r'\pagestyle{fancy}')
    lignes.append(r'\fancyhf{}')
    lignes.append(r'\lhead{\leftmark}')
    lignes.append(r'\rhead{\rightmark}')
    lignes.append(r'\rfoot{Page \thepage/\pageref{LastPage}}')
    lignes.append(r'\lfoot{Le \today}')
    lignes.append(r'\renewcommand{\sectionmark}[1]{\markboth{#1}{}}')
    lignes.append(r'\renewcommand{\subsectionmark}[1]{\markright{#1}}')
    lignes.append(r'\renewcommand{\headrulewidth}{0.4pt}')
    lignes.append(r'\renewcommand{\footrulewidth}{0pt}')
    lignes.append('')
    # Format des titres (mêmes que recap cours)
    lignes.append(
        r'\titleformat{\section}[frame]{\normalfont}'
        r'{\filright\footnotesize\enspace SECTION \thesection\enspace}'
        r'{30pt}{\huge\bfseries\filcenter}')
    lignes.append(
        r'\titleformat{\subsection}[block]{\normalfont\sffamily}'
        r'{\thesubsection}{.5em}'
        r'{\titlerule[2pt]\\[1em]\bfseries\sc\Large\filcenter}'
        r'[\vspace{2ex}\titlerule]')
    lignes.append(
        r'\titleformat{\subsubsection}{\normalfont\bfseries}'
        r'{\thesubsubsection}{1em}{}')
    lignes.append('')
    lignes.append(r'\setcounter{tocdepth}{2}')
    lignes.append('')
    lignes.append(r'\begin{document}')
    lignes.append('')
    # Forcer les définitions xint (\xintdefiivar, \xintdeffloatvar, \xintdefvar)
    # à être globales. Sans ce drapeau, ces définitions sont locales au groupe
    # courant : émises à l'intérieur d'un seqSerieExos (qui ouvre multicols ×
    # boitePale), elles disparaissent au \end{seqSerieExos} et ne sont plus
    # disponibles au moment de \seqAfficheCorriges en fin de livret, ce qui
    # plante avec « N10S01A01_numA unknown » sur Corriges/c<N>e<M>.tex.
    # C'est la même mesure que les livrets normaux émettent juste après
    # \begin{document}.
    #
    # Conditionnel : si aucun exo du livret n'utilise xint (cas N12 par
    # exemple), le paquet xint n'est pas chargé par construire_preambule
    # et \xintglobaldefstrue serait alors une commande inconnue. On le
    # protège donc avec \ifcsname...\endcsname (primitive eTeX, sans @).
    lignes.append(
        r'\ifcsname xintglobaldefstrue\endcsname\xintglobaldefstrue\fi')
    lignes.append('')
    # Fallbacks pour \theHxxx (hyperref non chargé)
    lignes.append(r'\providecommand{\theHExoNum}{\theExoNum}')
    lignes.append(r'\providecommand{\theHNotionNum}{\theNotionNum}')
    lignes.append(r'\providecommand{\theHMethodeNum}{\theMethodeNum}')
    lignes.append(r'\providecommand{\theHDefinitionNum}{\theDefinitionNum}')
    lignes.append(r'\providecommand{\theHProprieteNum}{\theProprieteNum}')
    lignes.append('')
    lignes.append(r'\seqCreeCompteurs')
    lignes.append(r'\seqSetCodeNiveau{' + niveau + '}')
    # Ouvrir les writeouts UNE SEULE FOIS pour tout le livret
    lignes.append(r'\seqInitCorriges')
    lignes.append(r'\seqInitAnnexes')
    # Forcer l'écriture de tous les corrigés (pas juste révisions+fonda)
    lignes.append(r'\renewcommand{\seqCorrigesExos}{oui}')
    # Mécanisme de protection contre les \newcommand dupliqués entre exos
    # agrégés. Les blocs `variables` de plusieurs exercices peuvent contenir
    # le MÊME `\newcommand\X{...}` (c'est le cas pour \tkzFExoI, \tkzMyHomFig,
    # \cerclePlein, \denomTexte... 4 noms × ~16 occurrences chacun en N10).
    # Sans protection, la 2e émission plante avec « Command \X already
    # defined ».
    # Convention : dans la base, "même nom de commande = même sémantique
    # attendue" — donc il est sans danger d'ignorer silencieusement la 2e
    # déclaration. \providecommand a exactement cette sémantique : crée si
    # inexistant, no-op si déjà existant. On applique \let\newcommand=
    # \providecommand globalement pour tout le livret.
    # Justifications :
    # - Les éventuels \renewcommand qui suivent dans le même bloc (cf.
    #   N10/S03/A6 avec \denomTexte) fonctionnent toujours, puisque la
    #   commande aura été créée par le premier passage.
    # - Le paquet seqenseigne n'utilise pas \newcommand à l'intérieur du
    #   corps des exercices/notions/méthodes (vérifié), donc l'override
    #   global ne casse rien côté paquet.
    # - L'utilisateur n'a pas à connaître l'état du livret pour rédiger
    #   son bloc `variables` : tout \newcommand qu'il écrit deviendra
    #   silencieusement idempotent dans le contexte agrégé.
    lignes.append(r'\let\newcommand=\providecommand')
    lignes.append('')

    # 4. Page de garde
    lignes.extend(_page_de_garde(niveau, structure))

    # 5. Table des matières
    lignes.append(r'\thispagestyle{empty}')
    lignes.append(r'\tableofcontents')
    lignes.append(r'\newpage')
    lignes.append('')

    # 6. Pour chaque thème → section ; pour chaque séquence → subsection ;
    #    pour chaque série → subsubsection avec son seqSerieExos.
    for bloc in structure:
        theme = bloc['theme']
        lignes.append(r'\cleardoublepage')
        lignes.append(f"\\seqSetColorsTheme{{{theme['code_couleur']}}}")
        lignes.append(f"\\section{{{_echapper(theme['nom'])}}}")
        if theme.get('description'):
            lignes.append(theme['description'])
        lignes.append('')

        for sb in bloc['sequences']:
            seq = sb['sequence']
            lignes.append(f"\\seqSetCodeSequence{{{seq['code']}}}")
            lignes.append(f"\\subsection{{{_echapper(seq['nom'])}}}")
            lignes.append('')

            # Émettre les blocs `variables` de la séquence AU NIVEAU TOP
            # (= avant l'ouverture du premier seqSerieExos qui ouvre des
            # groupes multicols + boitePale). C'est crucial pour deux raisons :
            #
            # 1. Variables xint : \xintdefiivar fait \XINT_global \edef qui
            #    n'est global QUE si \xintglobaldefs est vrai. On a bien posé
            #    \xintglobaldefstrue en tête de livret, mais sortir les défs
            #    au top level reste plus propre (cohérent avec ce que fait
            #    le rendu d'un atome isolé).
            #
            # 2. Macros utilisateur (\newcommand) : la directive
            #    \let\newcommand=\providecommand fait que \newcommand devient
            #    \providecommand, qui à son tour fait un \def. \def étant local
            #    par défaut, une définition émise à l'intérieur d'un groupe
            #    seqSerieExos disparaît à \end{seqSerieExos}, et plus rien ne
            #    la voit ensuite. Conséquence : `\touche` défini dans le bloc
            #    variables d'un exo, utilisé dans le corrigé via Corriges/cNeM,
            #    plante avec « Undefined control sequence \touche » au moment
            #    de \seqAfficheCorriges.
            #
            # Solution : émettre les variables au top level de la séquence
            # (avant les seqSerieExos), donc hors de tout groupe → définitions
            # globales naturellement.
            for variables in sb.get('variables', []):
                lignes.append('')
                lignes.append("% ── Variables d'exercices de la séquence ──")
                lignes.append(variables)
                lignes.append('')

            # Marqueur dans le flux des corrigés : on insère une « section »
            # de séquence dans CorrList.tex via \immediate\write\corrfile.
            # Ainsi quand \seqAfficheCorriges sera appelé en fin de livret,
            # les corrigés seront groupés par séquence.
            # On utilise \subsection pour rester dans la même hiérarchie que
            # la partie énoncés (qui utilise \subsection pour les séquences).
            # IMPORTANT : on enveloppe le titre dans \unexpanded{...} pour
            # que ses caractères non-ASCII (accents UTF-8) soient écrits dans
            # CorrList.tex tels quels, sans expansion ni encodage altéré.
            # C'est exactement la technique utilisée par le paquet seqenseigne
            # dans \seq@ecrit@corrige@serieExos pour ses propres titres
            # (« Corrigés des exercices de la série fondamentale », etc.).
            # Sans \unexpanded, on obtient « Invalid UTF-8 byte sequence »
            # au moment du \input{CorrList.tex} dans \seqAfficheCorriges.
            titre_corr = _echapper(seq['nom'])
            lignes.append(
                r'\immediate\write\corrfile{'
                r'\noexpand\subsection{\unexpanded{' + titre_corr + r'}}}')
            lignes.append('')

            for serie in sb['series']:
                code = serie['serie_code']
                # Sous-sous-section pour la série (pour la TOC)
                lignes.append(
                    f"\\subsubsection*{{{LIBELLES_SERIES[code]}}}")
                # Ouverture de la série au sens du paquet : titre, multicols,
                # boîte jaune. Le numéro passé pilote le titre affiché (0/1/2/3).
                lignes.append(
                    f"\\begin{{seqSerieExos}}{{{serie['num_paquet']}}}")
                # ── Hack option 2 : on remplace la valeur du compteur par
                # une valeur unique, juste après l'ouverture. Avant ce
                # \setcounter, le paquet a déjà :
                #   - écrit l'éventuel \label{corrigeExos<num_paquet>} dans
                #     CorrList.tex (sera en doublon entre séquences mais
                #     sans gravité — on n'utilise pas la pageref) ;
                #   - écrit l'entête « Série fondamentale/avancée/... » dans
                #     CorrList.tex avec le bon libellé.
                # Après ce \setcounter :
                #   - les noms de fichiers Corriges/cNeM.tex sont uniques ;
                #   - les \label{exo:N-M} générés par seqExercice sont uniques.
                lignes.append(
                    r'\setcounter{SerieExosNum}{' + str(serie['num_unique'])
                    + '}')
                # Reset du compteur d'exo pour avoir 1, 2, 3... dans CETTE série.
                lignes.append(r'\setcounter{ExoNum}{0}')

                # Émettre les blocs seqExercice. Les variables ont déjà été
                # émises au niveau de la séquence (cf. plus haut), pour rester
                # globales hors des groupes ouverts par seqSerieExos.
                for bloc_exo in serie['exos']:
                    lignes.append(bloc_exo)

                lignes.append(r'\end{seqSerieExos}')
                lignes.append('')

    # 7. Affichage des annexes et corrigés en fin de livret
    lignes.append(r'\cleardoublepage')
    lignes.append(r'\seqAfficheAnnexes')
    lignes.append(r'\cleardoublepage')
    # Section globale pour les corrigés (titre de plus haut niveau)
    lignes.append(r'\section*{Corrigés}')
    lignes.append(r'\addcontentsline{toc}{section}{Corrigés}')
    lignes.append(r'\seqAfficheCorriges')
    lignes.append(r'\end{document}')
    return '\n'.join(lignes)


# ── Page de garde ────────────────────────────────────────────────────────────

def _page_de_garde(niveau: str,
                    structure: list[dict]) -> list[str]:
    """Page de garde : titre, niveau, liste des séquences.

    Calque _page_de_garde de livret_recap_cours.
    """
    lignes = [r'\thispagestyle{empty}']
    libelle_niveau = LIBELLES_NIVEAUX.get(niveau, niveau)
    lignes.append(r'\begin{center}')
    lignes.append(r'\vspace*{2em}')
    lignes.append(r"{\Huge\bfseries Livret d'exercices}\\[2em]")
    lignes.append(r'{\Large Collège}\\[1em]')
    lignes.append(rf'{{\LARGE Classe de {libelle_niveau}}}\\[3em]')
    lignes.append(r'\end{center}')
    lignes.append('')

    lignes.append(r'\begin{itemize}')
    for bloc in structure:
        for sb in bloc['sequences']:
            seq = sb['sequence']
            lignes.append(f"  \\item {_echapper(seq['nom'])}")
    lignes.append(r'\end{itemize}')
    lignes.append('')

    lignes.append(r'\newpage')
    lignes.append('')
    return lignes


# ── Utilitaires ──────────────────────────────────────────────────────────────

def _echapper(texte: str) -> str:
    """Échappement minimal pour insertion dans un titre LaTeX.

    Comme livret_recap_cours._echapper, on ne fait PAS d'échappement
    de \\ et de & : les noms peuvent contenir du LaTeX intentionnel.
    """
    return texte or ''
