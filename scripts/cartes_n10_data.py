"""scripts/cartes_n10_data.py — Données de peuplement v0.13.6.2.3

Liste exhaustive des cartes d'automatisme pour le niveau N10 (5ème),
séquences S01 à S14.

Format : chaque carte est un dict avec les clés :
  - sequence    : 'S01' .. 'S14'
  - nom         : libellé court interne (affichage sidebar)
  - type_pedago : 'definition' | 'propriete' | 'reconnaissance'
                | 'calcul' | 'procedure'
  - type_tech   : 'fixe' | 'parametree'
  - lien        : ('notion', num_connaissance) ou ('methode', num_methode)
                  Le script résout l'ID en BDD à l'insertion.
  - recto       : LaTeX du recto
  - verso       : LaTeX du verso
  - variables   : LaTeX de définition xint (vide si type_tech='fixe')

Conventions xint (alignées sur les exercices N10/S01) :
  - `\\xintdefiivar nomvar := ... ;` pour définir un entier
  - `\\xintdeffloatvar nomvar := ... ;` pour définir un flottant
  - `\\xintiieval{nomvar}` pour afficher un entier
  - `\\xintfloateval{nomvar}` pour afficher un flottant (souvent dans `\\num{}`)
  - Préfixe de variable : `N10S<seq>C<num>_<role>` (C pour Carte),
    miroir des préfixes A/F/E des exercices, pour éviter toute
    collision sur une future planche A4.

Note Laurent (12 mai 2026) : insertion directe à l'état 'valide'.
Tu corrigeras à l'usage. Les zones de flou sont signalées par un
commentaire `# FLOU:` quand je suis incertain de ton angle pédagogique.
"""
from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────
# S01 — Représentations d'un nombre
# (17 cartes : refonte de propositions_cartes_N10_S01.md
#  avec syntaxe xint corrigée)
# ─────────────────────────────────────────────────────────────────────

CARTES_S01 = [
    {
        'sequence': 'S01',
        'nom': "Définition proportion",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 1),
        'recto': r"Qu'est-ce qu'une \textbf{proportion}?",
        'verso': (
            r"Un rapport relatif (= quotient) entre une grandeur "
            r"et une grandeur de référence."
            "\n\\smallskip\n\n"
            r"Peut s'écrire en \textbf{nombre décimal} ou en "
            r"\textbf{fraction}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S01',
        'nom': "Définition pourcentage",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Qu'est-ce qu'un \textbf{pourcentage}?",
        'verso': (
            r"Une proportion dont la \textbf{référence vaut 100}."
            "\n\\smallskip\n\n"
            r"Notation: numérateur suivi de $\%$."
            "\n\\smallskip\n\n"
            r"Exemple: $\seqFrac{37}{100} = 37\,\%$"
        ),
        'variables': '',
    },
    {
        'sequence': 'S01',
        'nom': "Pourcentage de 100",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('notion', 2),
        'recto': r"Combien font $\xintiieval{N10S01C04_p}\,\%$ de $100$?",
        'verso': r"$\xintiieval{N10S01C04_p}$",
        'variables': r"\xintdefiivar N10S01C04_p := randrange(5,95);",
    },
    {
        'sequence': 'S01',
        'nom': "Définition entier relatif",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 3),
        'recto': r"Qu'est-ce qu'un \textbf{entier relatif}?",
        'verso': (
            r"Un nombre entier précédé d'un \textbf{signe} ($+$ ou $-$)."
            "\n\\smallskip\n\n"
            r"Composé d'un \textbf{signe} et d'une "
            r"\textbf{distance à zéro}."
            "\n\\smallskip\n\n"
            r"Avec $+$ : \textbf{positif}. Avec $-$ : \textbf{négatif}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S01',
        'nom': "Distance à zéro",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('notion', 3),
        'recto': (
            r"Quelle est la \textbf{distance à zéro} de "
            r"$\xintiieval{N10S01C06_n}$?"
        ),
        # `abs(...)` n'existe pas en xint ; on fait la valeur absolue
        # à la définition via une condition.
        'verso': r"$\xintiieval{N10S01C06_abs}$",
        'variables': (
            r"\xintdefiivar N10S01C06_n := randrange(-50,50);"
            "\n"
            r"\xintdefiivar N10S01C06_abs := "
            r"(N10S01C06_n < 0) ? -N10S01C06_n : N10S01C06_n;"
        ),
    },
    {
        'sequence': 'S01',
        'nom': "Définition décimal",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 4),
        'recto': r"Qu'est-ce qu'un \textbf{décimal}?",
        'verso': (
            r"Le quotient d'un \textbf{entier relatif} divisé par "
            r"$1$, $10$, $100$, $1000$, \ldots"
            "\n\\smallskip\n\n"
            r"Exemples : $3,7 = \seqFrac{37}{10}$, "
            r"$-0,002 = \seqFrac{-2}{1000}$"
        ),
        'variables': '',
    },
    {
        'sequence': 'S01',
        'nom': "Définition rationnel",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 5),
        'recto': r"Qu'est-ce qu'un \textbf{rationnel}?",
        'verso': (
            r"Le quotient d'un \textbf{entier relatif} divisé par un "
            r"\textbf{autre entier relatif}, différent de zéro."
            "\n\\smallskip\n\n"
            r"Exemple : $\seqFrac{-3}{7}$ est un rationnel."
        ),
        'variables': '',
    },
    {
        'sequence': 'S01',
        'nom': "Composants repère droite",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 6),
        'recto': r"Quels sont les 3 éléments d'un \textbf{repère d'une droite}?",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Une \textbf{origine} (point d'abscisse 0)." "\n"
            r"  \item Un \textbf{sens} (flèche)." "\n"
            r"  \item Une \textbf{unité} (distance entre 0 et 1)." "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S01',
        'nom': "Notation A(x;y)",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 7),
        'recto': (
            r"Comment note-t-on les coordonnées d'un point $A$ dans un "
            r"\textbf{repère du plan}?"
        ),
        'verso': (
            r"$A(x \,;\, y)$"
            "\n\\smallskip\n\n"
            r"avec $x$ l'\textbf{abscisse} (en premier) "
            r"et $y$ l'\textbf{ordonnée} (en second)."
        ),
        'variables': '',
    },
    {
        'sequence': 'S01',
        'nom': "Décimal → fraction (1 chiffre)",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 1),
        'recto': (
            r"Écris sous forme de fraction décimale :"
            "\n\\smallskip\n\n"
            r"$\xintiieval{N10S01C11_a},\xintiieval{N10S01C11_b}$"
        ),
        'verso': r"$\seqFrac{\xintiieval{N10S01C11_num}}{10}$",
        'variables': (
            r"\xintdefiivar N10S01C11_a := randrange(1,9);" "\n"
            r"\xintdefiivar N10S01C11_b := randrange(1,9);" "\n"
            r"\xintdefiivar N10S01C11_num := 10*N10S01C11_a + N10S01C11_b;"
        ),
    },
    {
        'sequence': 'S01',
        'nom': "Décimal → fraction (2 chiffres)",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 1),
        'recto': (
            r"Écris sous forme de fraction décimale :"
            "\n\\smallskip\n\n"
            r"$\xintiieval{N10S01C12_a},"
            r"\xintiieval{N10S01C12_b}\xintiieval{N10S01C12_c}$"
        ),
        'verso': r"$\seqFrac{\xintiieval{N10S01C12_num}}{100}$",
        'variables': (
            r"\xintdefiivar N10S01C12_a := randrange(1,9);" "\n"
            r"\xintdefiivar N10S01C12_b := randrange(0,9);" "\n"
            r"\xintdefiivar N10S01C12_c := randrange(1,9);" "\n"
            r"\xintdefiivar N10S01C12_num := "
            r"100*N10S01C12_a + 10*N10S01C12_b + N10S01C12_c;"
        ),
    },
    {
        'sequence': 'S01',
        'nom': "Fraction décimale → décimal",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 1),
        'recto': (
            r"Donne l'écriture décimale de :"
            "\n\\smallskip\n\n"
            r"$\seqFrac{\xintiieval{N10S01C13_n}}{100}$"
        ),
        'verso': r"$\num{\xintfloateval{N10S01C13_res}}$",
        'variables': (
            r"\xintdefiivar N10S01C13_n := randrange(10,999);" "\n"
            r"\xintdeffloatvar N10S01C13_res := N10S01C13_n / 100;"
        ),
    },
    {
        'sequence': 'S01',
        'nom': "Pourcentage → décimal",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 2),
        'recto': (
            r"Écris sous forme décimale :"
            "\n\\smallskip\n\n"
            r"$\xintiieval{N10S01C14_p}\,\%$"
        ),
        'verso': r"$\num{\xintfloateval{N10S01C14_res}}$",
        'variables': (
            r"\xintdefiivar N10S01C14_p := randrange(5,95);" "\n"
            r"\xintdeffloatvar N10S01C14_res := N10S01C14_p / 100;"
        ),
    },
    {
        'sequence': 'S01',
        'nom': "Décimal → pourcentage",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 2),
        'recto': (
            r"Écris sous forme de pourcentage :"
            "\n\\smallskip\n\n"
            r"$0,\xintiieval{N10S01C15_p}$"
        ),
        'verso': r"$\xintiieval{N10S01C15_p}\,\%$",
        'variables': r"\xintdefiivar N10S01C15_p := randrange(10,95);",
    },
    {
        'sequence': 'S01',
        'nom': "Fraction → pourcentage simple",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 2),
        # ratio entre 1 et 9 dixièmes -> donne directement 10..90 %
        'recto': (
            r"Écris sous forme de pourcentage :"
            "\n\\smallskip\n\n"
            r"$\seqFrac{\xintiieval{N10S01C16_a}}{10}$"
        ),
        'verso': r"$\xintiieval{N10S01C16_pourcent}\,\%$",
        'variables': (
            r"\xintdefiivar N10S01C16_a := randrange(1,9);" "\n"
            r"\xintdefiivar N10S01C16_pourcent := 10 * N10S01C16_a;"
        ),
    },
    {
        'sequence': 'S01',
        'nom': "Étapes lecture abscisse",
        'type_pedago': 'procedure',
        'type_tech': 'fixe',
        'lien': ('methode', 3),
        'recto': (
            r"\textbf{Procédure} : lire l'abscisse d'un point sur "
            r"une droite graduée."
        ),
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Repérer l'\textbf{origine} (abscisse 0)." "\n"
            r"  \item Mesurer l'\textbf{unité} (distance 0--1)." "\n"
            r"  \item Sur quelle graduation le point tombe-t-il?" "\n"
            r"  \item Sinon : mesurer la distance origine--point." "\n"
            r"  \item Lire l'abscisse = distance $\div$ unité." "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S01',
        'nom': "Ordre coordonnées plan",
        'type_pedago': 'reconnaissance',
        'type_tech': 'fixe',
        'lien': ('methode', 3),
        'recto': (
            r"Dans la notation $A(3\,;\,-2)$, "
            r"que représentent $3$ et $-2$?"
        ),
        'verso': (
            r"$3$ : \textbf{abscisse} (axe horizontal)."
            "\n\\smallskip\n\n"
            r"$-2$ : \textbf{ordonnée} (axe vertical)."
            "\n\\smallskip\n\n"
            r"Ordre : abscisse \textbf{toujours en premier}."
        ),
        'variables': '',
    },
]


# ─────────────────────────────────────────────────────────────────────
# S02 — Comparaison de nombres
# Notions : 0 enregistrées en BDD.
# Méthodes : M1 fractions égales, M2 compa décimaux, M3 compa fractions
# Stratégie : cartes orientées méthodes uniquement.
# ─────────────────────────────────────────────────────────────────────

CARTES_S02 = [
    {
        'sequence': 'S02',
        'nom': "Fractions égales : règle",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('methode', 1),
        'recto': r"Comment produire une \textbf{fraction égale} à une fraction donnée?",
        'verso': (
            r"On \textbf{multiplie (ou on divise)} le numérateur et "
            r"le dénominateur par un \textbf{même nombre non nul}."
            "\n\\smallskip\n\n"
            r"Exemple : "
            r"$\seqFrac{2}{3} = \seqFrac{2\times 5}{3\times 5} = \seqFrac{10}{15}$"
        ),
        'variables': '',
    },
    {
        'sequence': 'S02',
        'nom': "Fraction égale par multiplication",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 1),
        'recto': (
            r"Donne une fraction égale à "
            r"$\seqFrac{\xintiieval{N10S02C02_n}}{\xintiieval{N10S02C02_d}}$ "
            r"en multipliant par $\xintiieval{N10S02C02_k}$."
        ),
        'verso': (
            r"$\seqFrac{\xintiieval{N10S02C02_nn}}{\xintiieval{N10S02C02_dd}}$"
        ),
        'variables': (
            r"\xintdefiivar N10S02C02_n := randrange(2,9);" "\n"
            r"\xintdefiivar N10S02C02_d := randrange(2,9);" "\n"
            r"\xintdefiivar N10S02C02_k := randrange(2,5);" "\n"
            r"\xintdefiivar N10S02C02_nn := N10S02C02_n * N10S02C02_k;" "\n"
            r"\xintdefiivar N10S02C02_dd := N10S02C02_d * N10S02C02_k;"
        ),
    },
    {
        'sequence': 'S02',
        'nom': "Simplifier une fraction",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 1),
        'recto': (
            r"Simplifie la fraction "
            r"$\seqFrac{\xintiieval{N10S02C03_n}}{\xintiieval{N10S02C03_d}}$."
        ),
        'verso': (
            r"$\seqFrac{\xintiieval{N10S02C03_ns}}{\xintiieval{N10S02C03_ds}}$"
        ),
        'variables': (
            r"\xintdefiivar N10S02C03_ns := randrange(2,7);" "\n"
            r"\xintdefiivar N10S02C03_ds := randrange(3,9);" "\n"
            r"\xintdefiivar N10S02C03_k := randrange(2,5);" "\n"
            r"\xintdefiivar N10S02C03_n := N10S02C03_ns * N10S02C03_k;" "\n"
            r"\xintdefiivar N10S02C03_d := N10S02C03_ds * N10S02C03_k;"
        ),
    },
    {
        'sequence': 'S02',
        'nom': "Ranger 2 décimaux",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 2),
        'recto': (
            r"Compare avec $<$, $>$ ou $=$ :"
            "\n\\smallskip\n\n"
            r"$\num{\xintfloateval{N10S02C04_a}}$ "
            r"\;\dotfill\; "
            r"$\num{\xintfloateval{N10S02C04_b}}$"
        ),
        # Pour rester sur du contenu sûr : on tire deux entiers de
        # taille différente et on les divise par 100 ⇒ comparaison
        # déterministe.
        'verso': (
            r"$\num{\xintfloateval{N10S02C04_a}} "
            r"\xintifgtfloat{N10S02C04_a}{N10S02C04_b}{>}"
            r"{\xintifeqfloat{N10S02C04_a}{N10S02C04_b}{=}{<}} "
            r"\num{\xintfloateval{N10S02C04_b}}$"
        ),
        'variables': (
            r"\xintdefiivar N10S02C04_ia := randrange(100,999);" "\n"
            r"\xintdefiivar N10S02C04_ib := randrange(100,999);" "\n"
            r"\xintdeffloatvar N10S02C04_a := N10S02C04_ia / 100;" "\n"
            r"\xintdeffloatvar N10S02C04_b := N10S02C04_ib / 100;"
        ),
    },
    {
        'sequence': 'S02',
        'nom': "Procédure comparer décimaux",
        'type_pedago': 'procedure',
        'type_tech': 'fixe',
        'lien': ('methode', 2),
        'recto': r"\textbf{Procédure} : comparer deux nombres décimaux.",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Comparer les \textbf{parties entières}." "\n"
            r"  \item Si égales, comparer les \textbf{dixièmes}." "\n"
            r"  \item Si égales, comparer les \textbf{centièmes}." "\n"
            r"  \item Et ainsi de suite chiffre par chiffre." "\n"
            r"\end{seqColEnum}"
            "\n\\smallskip\n\n"
            r"\textbf{Attention} : $2,5 = 2,50 = 2,500$."
        ),
        'variables': '',
    },
    {
        'sequence': 'S02',
        'nom': "Comparer fractions même dénom.",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 3),
        'recto': (
            r"Compare :"
            "\n\\smallskip\n\n"
            r"$\seqFrac{\xintiieval{N10S02C06_a}}{\xintiieval{N10S02C06_d}}$ "
            r"\;\dotfill\; "
            r"$\seqFrac{\xintiieval{N10S02C06_b}}{\xintiieval{N10S02C06_d}}$"
        ),
        'verso': (
            r"$\seqFrac{\xintiieval{N10S02C06_a}}{\xintiieval{N10S02C06_d}} "
            r"\xintifgt{N10S02C06_a}{N10S02C06_b}{>}{<} "
            r"\seqFrac{\xintiieval{N10S02C06_b}}{\xintiieval{N10S02C06_d}}$"
        ),
        'variables': (
            r"\xintdefiivar N10S02C06_a := randrange(2,9);" "\n"
            r"\xintdefiivar N10S02C06_b := randrange(2,9);" "\n"
            r"\xintdefiivar N10S02C06_d := randrange(3,11);"
        ),
    },
    {
        'sequence': 'S02',
        'nom': "Règle compa. fractions",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('methode', 3),
        'recto': (
            r"Comment comparer deux fractions de \textbf{même dénominateur}?"
        ),
        'verso': (
            r"La plus grande est celle qui a "
            r"le \textbf{plus grand numérateur}."
            "\n\\smallskip\n\n"
            r"Exemple : "
            r"$\seqFrac{5}{7} > \seqFrac{3}{7}$ car $5 > 3$."
        ),
        'variables': '',
    },
]


# ─────────────────────────────────────────────────────────────────────
# S03 — Calcul numérique
# Notions : opérations, opérandes, résultats, opposé
# Méthodes : parenthèses, priorités, calcul décimaux, calcul fractions,
#            vraisemblance
# ─────────────────────────────────────────────────────────────────────

CARTES_S03 = [
    {
        'sequence': 'S03',
        'nom': "Vocabulaire des opérations",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 3),
        'recto': r"Comment s'appelle le résultat de chaque opération?",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Addition $\to$ \textbf{somme}" "\n"
            r"  \item Soustraction $\to$ \textbf{différence}" "\n"
            r"  \item Multiplication $\to$ \textbf{produit}" "\n"
            r"  \item Division $\to$ \textbf{quotient}" "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S03',
        'nom': "Vocabulaire des opérandes",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Comment s'appellent les nombres qu'on opère?",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Addition / soustraction : \textbf{termes}" "\n"
            r"  \item Multiplication : \textbf{facteurs}" "\n"
            r"  \item Division : \textbf{dividende} et \textbf{diviseur}" "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S03',
        'nom': "Définition opposé",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 4),
        'recto': r"Qu'est-ce que l'\textbf{opposé} d'un nombre?",
        'verso': (
            r"Le nombre qui, ajouté au nombre de départ, donne $0$."
            "\n\\smallskip\n\n"
            r"On change simplement le \textbf{signe}."
            "\n\\smallskip\n\n"
            r"Exemples : opposé de $7$ est $-7$ ; opposé de $-3,5$ est $3,5$."
        ),
        'variables': '',
    },
    {
        'sequence': 'S03',
        'nom': "Opposé d'un nombre",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('notion', 4),
        'recto': (
            r"Donne l'\textbf{opposé} de $\xintiieval{N10S03C04_n}$."
        ),
        'verso': r"$\xintiieval{N10S03C04_opp}$",
        'variables': (
            r"\xintdefiivar N10S03C04_n := randrange(-50,50);" "\n"
            r"\xintdefiivar N10S03C04_opp := -N10S03C04_n;"
        ),
    },
    {
        'sequence': 'S03',
        'nom': "Règle des priorités",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('methode', 2),
        'recto': r"Quel est l'ordre des \textbf{priorités opératoires}?",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Les \textbf{parenthèses} d'abord (de l'intérieur)." "\n"
            r"  \item Les \textbf{multiplications/divisions} ensuite," "\n"
            r"    de gauche à droite." "\n"
            r"  \item Les \textbf{additions/soustractions} en dernier," "\n"
            r"    de gauche à droite." "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S03',
        'nom': "Priorité × sur +",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 2),
        'recto': (
            r"Calcule :"
            "\n\\smallskip\n\n"
            r"$\xintiieval{N10S03C06_a} + \xintiieval{N10S03C06_b} "
            r"\times \xintiieval{N10S03C06_c}$"
        ),
        'verso': r"$\xintiieval{N10S03C06_res}$",
        'variables': (
            r"\xintdefiivar N10S03C06_a := randrange(2,15);" "\n"
            r"\xintdefiivar N10S03C06_b := randrange(2,9);" "\n"
            r"\xintdefiivar N10S03C06_c := randrange(2,9);" "\n"
            r"\xintdefiivar N10S03C06_res := "
            r"N10S03C06_a + N10S03C06_b * N10S03C06_c;"
        ),
    },
    {
        'sequence': 'S03',
        'nom': "Addition de décimaux",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 3),
        'recto': (
            r"Calcule :"
            "\n\\smallskip\n\n"
            r"$\num{\xintfloateval{N10S03C07_a}} + "
            r"\num{\xintfloateval{N10S03C07_b}}$"
        ),
        'verso': r"$\num{\xintfloateval{N10S03C07_res}}$",
        'variables': (
            r"\xintdefiivar N10S03C07_ia := randrange(10,99);" "\n"
            r"\xintdefiivar N10S03C07_ib := randrange(10,99);" "\n"
            r"\xintdeffloatvar N10S03C07_a := N10S03C07_ia / 10;" "\n"
            r"\xintdeffloatvar N10S03C07_b := N10S03C07_ib / 10;" "\n"
            r"\xintdeffloatvar N10S03C07_res := N10S03C07_a + N10S03C07_b;"
        ),
    },
    {
        'sequence': 'S03',
        'nom': "Somme fractions même dénom.",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 4),
        'recto': (
            r"Calcule :"
            "\n\\smallskip\n\n"
            r"$\seqFrac{\xintiieval{N10S03C08_a}}{\xintiieval{N10S03C08_d}} + "
            r"\seqFrac{\xintiieval{N10S03C08_b}}{\xintiieval{N10S03C08_d}}$"
        ),
        'verso': (
            r"$\seqFrac{\xintiieval{N10S03C08_s}}{\xintiieval{N10S03C08_d}}$"
        ),
        'variables': (
            r"\xintdefiivar N10S03C08_a := randrange(1,6);" "\n"
            r"\xintdefiivar N10S03C08_b := randrange(1,6);" "\n"
            r"\xintdefiivar N10S03C08_d := randrange(3,11);" "\n"
            r"\xintdefiivar N10S03C08_s := N10S03C08_a + N10S03C08_b;"
        ),
    },
    {
        'sequence': 'S03',
        'nom': "Règle somme fractions",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('methode', 4),
        'recto': (
            r"Comment additionner deux fractions de "
            r"\textbf{même dénominateur}?"
        ),
        'verso': (
            r"On ajoute les \textbf{numérateurs}, "
            r"on \textbf{garde} le dénominateur."
            "\n\\smallskip\n\n"
            r"$\seqFrac{a}{d} + \seqFrac{b}{d} = \seqFrac{a+b}{d}$"
        ),
        'variables': '',
    },
    {
        'sequence': 'S03',
        'nom': "Ordre de grandeur",
        'type_pedago': 'procedure',
        'type_tech': 'fixe',
        'lien': ('methode', 5),
        'recto': (
            r"\textbf{Procédure} : contrôler un résultat par un "
            r"\textbf{ordre de grandeur}."
        ),
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Arrondir chaque nombre au plus simple" "\n"
            r"    (chiffre rond proche)." "\n"
            r"  \item Effectuer l'opération mentalement." "\n"
            r"  \item Comparer au résultat trouvé." "\n"
            r"\end{seqColEnum}"
            "\n\\smallskip\n\n"
            r"\textbf{Si très loin}, je refais le calcul."
        ),
        'variables': '',
    },
]


# ─────────────────────────────────────────────────────────────────────
# S04 — Divisibilité et nombres premiers
# Notions : multiple/diviseur, critères div., div. euclidienne
# Méthodes : quotient/reste, multiple ou diviseur, frac → entier + frac,
#            critères divisibilité
# ─────────────────────────────────────────────────────────────────────

CARTES_S04 = [
    {
        'sequence': 'S04',
        'nom': "Définition multiple/diviseur",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 1),
        'recto': r"Que signifie « $a$ est un \textbf{multiple} de $b$ »?",
        'verso': (
            r"$a$ est un multiple de $b$ si "
            r"$a = b \times k$ avec $k$ entier."
            "\n\\smallskip\n\n"
            r"On dit aussi que $b$ est un \textbf{diviseur} de $a$, "
            r"ou que $a$ est \textbf{divisible} par $b$."
            "\n\\smallskip\n\n"
            r"Exemple : $35 = 7 \times 5$, donc $35$ est multiple de $7$."
        ),
        'variables': '',
    },
    {
        'sequence': 'S04',
        'nom': "Vocabulaire div. euclidienne",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 3),
        'recto': r"Dans une \textbf{division euclidienne}, comment s'appellent les 4 nombres?",
        'verso': (
            r"$a = b \times q + r$ avec $0 \le r < b$"
            "\n\\smallskip\n\n"
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item $a$ : \textbf{dividende}" "\n"
            r"  \item $b$ : \textbf{diviseur}" "\n"
            r"  \item $q$ : \textbf{quotient}" "\n"
            r"  \item $r$ : \textbf{reste}" "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S04',
        'nom': "Critère divisibilité 2",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Critère de divisibilité par \textbf{$2$}?",
        'verso': (
            r"Le nombre est divisible par $2$ "
            r"\textbf{ssi son chiffre des unités est} "
            r"$0$, $2$, $4$, $6$ ou $8$."
            "\n\\smallskip\n\n"
            r"(= un \textbf{nombre pair})"
        ),
        'variables': '',
    },
    {
        'sequence': 'S04',
        'nom': "Critère divisibilité 3",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Critère de divisibilité par \textbf{$3$}?",
        'verso': (
            r"Le nombre est divisible par $3$ "
            r"\textbf{ssi la somme de ses chiffres} "
            r"est divisible par $3$."
            "\n\\smallskip\n\n"
            r"Exemple : $147 \to 1+4+7 = 12$, "
            r"et $12$ est divisible par $3$, donc $147$ aussi."
        ),
        'variables': '',
    },
    {
        'sequence': 'S04',
        'nom': "Critère divisibilité 5",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Critère de divisibilité par \textbf{$5$}?",
        'verso': (
            r"Le nombre est divisible par $5$ "
            r"\textbf{ssi son chiffre des unités est} "
            r"$0$ ou $5$."
        ),
        'variables': '',
    },
    {
        'sequence': 'S04',
        'nom': "Critère divisibilité 9",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Critère de divisibilité par \textbf{$9$}?",
        'verso': (
            r"Le nombre est divisible par $9$ "
            r"\textbf{ssi la somme de ses chiffres} "
            r"est divisible par $9$."
            "\n\\smallskip\n\n"
            r"Exemple : $738 \to 7+3+8 = 18$, "
            r"divisible par $9$, donc $738$ aussi."
        ),
        'variables': '',
    },
    {
        'sequence': 'S04',
        'nom': "Critère divisibilité 10",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Critère de divisibilité par \textbf{$10$}?",
        'verso': (
            r"Le nombre est divisible par $10$ "
            r"\textbf{ssi son chiffre des unités est} "
            r"$0$."
        ),
        'variables': '',
    },
    {
        'sequence': 'S04',
        'nom': "Quotient et reste",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 1),
        'recto': (
            r"Donne le quotient et le reste de la division euclidienne :"
            "\n\\smallskip\n\n"
            r"$\xintiieval{N10S04C08_a}$ \;\textbf{par}\; "
            r"$\xintiieval{N10S04C08_b}$"
        ),
        'verso': (
            r"Quotient : $\xintiieval{N10S04C08_q}$"
            "\n\\smallskip\n\n"
            r"Reste : $\xintiieval{N10S04C08_r}$"
        ),
        'variables': (
            r"\xintdefiivar N10S04C08_b := randrange(4,15);" "\n"
            r"\xintdefiivar N10S04C08_q := randrange(5,30);" "\n"
            r"\xintdefiivar N10S04C08_r := randrange(0,N10S04C08_b-1);" "\n"
            r"\xintdefiivar N10S04C08_a := "
            r"N10S04C08_b * N10S04C08_q + N10S04C08_r;"
        ),
    },
    {
        'sequence': 'S04',
        'nom': "Multiple ou diviseur?",
        'type_pedago': 'reconnaissance',
        'type_tech': 'parametree',
        'lien': ('methode', 2),
        'recto': (
            r"$\xintiieval{N10S04C09_a}$ est-il un \textbf{multiple} "
            r"de $\xintiieval{N10S04C09_b}$?"
        ),
        'verso': (
            r"$\xintiieval{N10S04C09_a} = "
            r"\xintiieval{N10S04C09_b} \times \xintiieval{N10S04C09_k}$"
            "\n\\smallskip\n\n"
            r"Oui, c'est un multiple de $\xintiieval{N10S04C09_b}$."
        ),
        # On force le cas « oui » pour avoir une réponse stable. Pour
        # une carte alternant oui/non, voir évolution future.
        'variables': (
            r"\xintdefiivar N10S04C09_b := randrange(3,12);" "\n"
            r"\xintdefiivar N10S04C09_k := randrange(3,12);" "\n"
            r"\xintdefiivar N10S04C09_a := N10S04C09_b * N10S04C09_k;"
        ),
    },
    {
        'sequence': 'S04',
        'nom': "Fraction → entier + fraction",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 3),
        'recto': (
            r"Décompose en somme d'un entier et d'une fraction inférieure à $1$ :"
            "\n\\smallskip\n\n"
            r"$\seqFrac{\xintiieval{N10S04C10_n}}{\xintiieval{N10S04C10_d}}$"
        ),
        'verso': (
            r"$\xintiieval{N10S04C10_q} + "
            r"\seqFrac{\xintiieval{N10S04C10_r}}{\xintiieval{N10S04C10_d}}$"
        ),
        'variables': (
            r"\xintdefiivar N10S04C10_d := randrange(3,9);" "\n"
            r"\xintdefiivar N10S04C10_q := randrange(2,6);" "\n"
            r"\xintdefiivar N10S04C10_r := randrange(1,N10S04C10_d-1);" "\n"
            r"\xintdefiivar N10S04C10_n := "
            r"N10S04C10_d * N10S04C10_q + N10S04C10_r;"
        ),
    },
]


# ─────────────────────────────────────────────────────────────────────
# S05 — Calcul littéral
# Notions : indéterminée, égalité, expression littérale, forme réduite,
#           omission ×, notation carré/cube
# Méthodes : produire expr litt., démontrer, réduire ax+b, substituer
# ─────────────────────────────────────────────────────────────────────

CARTES_S05 = [
    {
        'sequence': 'S05',
        'nom': "Indéterminée vs inconnue",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 1),
        'recto': r"Différence entre \textbf{indéterminée} et \textbf{inconnue}?",
        'verso': (
            r"\textbf{Indéterminée} : la lettre représente \textbf{n'importe quelle valeur}." "\n"
            r"\smallskip" "\n\n"
            r"\textbf{Inconnue} : la lettre représente \textbf{une valeur précise mais qu'on ne connaît pas encore} ; "
            r"on la \textbf{cherche}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S05',
        'nom': "Définition expression littérale",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 3),
        'recto': r"Qu'est-ce qu'une \textbf{expression littérale}?",
        'verso': (
            r"Une expression mathématique qui contient au moins "
            r"\textbf{une lettre}."
            "\n\\smallskip\n\n"
            r"Exemples : $3x + 2$ ; $a^2$ ; $4(x-1) + 5$."
        ),
        'variables': '',
    },
    {
        'sequence': 'S05',
        'nom': "Règle omission ×",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 5),
        'recto': r"Quand peut-on \textbf{omettre} le symbole $\times$?",
        'verso': (
            r"Devant une \textbf{lettre} ou une \textbf{parenthèse}." "\n"
            r"\smallskip" "\n\n"
            r"Exemples :" "\n"
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item $2 \times a = 2a$" "\n"
            r"  \item $3 \times (x+1) = 3(x+1)$" "\n"
            r"  \item $a \times b = ab$" "\n"
            r"\end{seqColEnum}" "\n"
            r"\smallskip" "\n\n"
            r"\textbf{Mais} : entre deux nombres, on garde le $\times$ "
            r"($3 \times 5$, jamais $35$)."
        ),
        'variables': '',
    },
    {
        'sequence': 'S05',
        'nom': "Notation carré et cube",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 6),
        'recto': r"Que signifient $a^2$ et $a^3$?",
        'verso': (
            r"$a^2 = a \times a$ (\textbf{carré} de $a$)"
            "\n\\smallskip\n\n"
            r"$a^3 = a \times a \times a$ (\textbf{cube} de $a$)"
        ),
        'variables': '',
    },
    {
        'sequence': 'S05',
        'nom': "Substituer une valeur",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 4),
        'recto': (
            r"Calcule $3x + \xintiieval{N10S05C05_b}$ pour "
            r"$x = \xintiieval{N10S05C05_x}$."
        ),
        'verso': r"$\xintiieval{N10S05C05_res}$",
        'variables': (
            r"\xintdefiivar N10S05C05_b := randrange(1,10);" "\n"
            r"\xintdefiivar N10S05C05_x := randrange(2,9);" "\n"
            r"\xintdefiivar N10S05C05_res := "
            r"3 * N10S05C05_x + N10S05C05_b;"
        ),
    },
    {
        'sequence': 'S05',
        'nom': "Réduire ax + bx",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 3),
        'recto': (
            r"Réduis :"
            "\n\\smallskip\n\n"
            r"$\xintiieval{N10S05C06_a}x + \xintiieval{N10S05C06_b}x$"
        ),
        'verso': r"$\xintiieval{N10S05C06_s}x$",
        'variables': (
            r"\xintdefiivar N10S05C06_a := randrange(2,9);" "\n"
            r"\xintdefiivar N10S05C06_b := randrange(2,9);" "\n"
            r"\xintdefiivar N10S05C06_s := N10S05C06_a + N10S05C06_b;"
        ),
    },
    {
        'sequence': 'S05',
        'nom': "Procédure réduction ax+b",
        'type_pedago': 'procedure',
        'type_tech': 'fixe',
        'lien': ('methode', 3),
        'recto': (
            r"\textbf{Procédure} : réduire une expression à la forme $ax+b$."
        ),
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Regrouper les termes avec $x$." "\n"
            r"  \item Additionner leurs coefficients." "\n"
            r"  \item Regrouper les termes sans $x$." "\n"
            r"  \item Les additionner entre eux." "\n"
            r"\end{seqColEnum}"
            "\n\\smallskip\n\n"
            r"\textbf{Attention} aux signes!"
        ),
        'variables': '',
    },
    {
        'sequence': 'S05',
        'nom': "Réduire 5x + 3 + 2x",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 3),
        'recto': (
            r"Réduis :"
            "\n\\smallskip\n\n"
            r"$\xintiieval{N10S05C08_a}x + \xintiieval{N10S05C08_b} + "
            r"\xintiieval{N10S05C08_c}x$"
        ),
        'verso': (
            r"$\xintiieval{N10S05C08_ax}x + \xintiieval{N10S05C08_b}$"
        ),
        'variables': (
            r"\xintdefiivar N10S05C08_a := randrange(2,9);" "\n"
            r"\xintdefiivar N10S05C08_b := randrange(2,9);" "\n"
            r"\xintdefiivar N10S05C08_c := randrange(2,9);" "\n"
            r"\xintdefiivar N10S05C08_ax := N10S05C08_a + N10S05C08_c;"
        ),
    },
]


# ─────────────────────────────────────────────────────────────────────
# S06 — Traitement, représentation et interprétation des données
# Notions : série stat, effectif total, effectif/fréquence,
#           étendue/moyenne
# Méthodes : tableau, eff. total et étendue, eff./fréq.,
#            moyenne, diagramme bâton
# ─────────────────────────────────────────────────────────────────────

CARTES_S06 = [
    {
        'sequence': 'S06',
        'nom': "Définition effectif",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 3),
        'recto': r"Qu'est-ce que l'\textbf{effectif} d'une valeur?",
        'verso': (
            r"Le \textbf{nombre de fois} où cette valeur apparaît "
            r"dans la série statistique."
        ),
        'variables': '',
    },
    {
        'sequence': 'S06',
        'nom': "Définition fréquence",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 3),
        'recto': r"Qu'est-ce que la \textbf{fréquence} d'une valeur?",
        'verso': (
            r"Le quotient $\seqFrac{\text{effectif}}{\text{effectif total}}$."
            "\n\\smallskip\n\n"
            r"S'exprime souvent en \textbf{pourcentage}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S06',
        'nom': "Définition étendue",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 4),
        'recto': r"Qu'est-ce que l'\textbf{étendue} d'une série?",
        'verso': (
            r"La \textbf{différence} entre la \textbf{plus grande} "
            r"valeur et la \textbf{plus petite} valeur de la série."
            "\n\\smallskip\n\n"
            r"$\text{étendue} = \max - \min$"
        ),
        'variables': '',
    },
    {
        'sequence': 'S06',
        'nom': "Définition moyenne",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 4),
        'recto': r"Comment calcule-t-on la \textbf{moyenne} d'une série?",
        'verso': (
            r"$\text{moyenne} = "
            r"\seqFrac{\text{somme des valeurs}}{\text{effectif total}}$"
        ),
        'variables': '',
    },
    {
        'sequence': 'S06',
        'nom': "Étendue d'une mini-série",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 2),
        'recto': (
            r"Calcule l'étendue de la série :"
            "\n\\smallskip\n\n"
            r"$\xintiieval{N10S06C05_a}$ ; "
            r"$\xintiieval{N10S06C05_b}$ ; "
            r"$\xintiieval{N10S06C05_c}$ ; "
            r"$\xintiieval{N10S06C05_d}$"
        ),
        'verso': r"$\xintiieval{N10S06C05_e}$",
        # On tire 4 valeurs avec min/max forcés, étendue déterministe.
        'variables': (
            r"\xintdefiivar N10S06C05_min := randrange(2,8);" "\n"
            r"\xintdefiivar N10S06C05_e := randrange(8,20);" "\n"
            r"\xintdefiivar N10S06C05_max := N10S06C05_min + N10S06C05_e;" "\n"
            r"\xintdefiivar N10S06C05_a := N10S06C05_max;" "\n"
            r"\xintdefiivar N10S06C05_b := "
            r"N10S06C05_min + randrange(1,N10S06C05_e-1);" "\n"
            r"\xintdefiivar N10S06C05_c := N10S06C05_min;" "\n"
            r"\xintdefiivar N10S06C05_d := "
            r"N10S06C05_min + randrange(1,N10S06C05_e-1);"
        ),
    },
    {
        'sequence': 'S06',
        'nom': "Moyenne de 4 valeurs",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 4),
        'recto': (
            r"Calcule la moyenne :"
            "\n\\smallskip\n\n"
            r"$\xintiieval{N10S06C06_a}$ ; "
            r"$\xintiieval{N10S06C06_b}$ ; "
            r"$\xintiieval{N10S06C06_c}$ ; "
            r"$\xintiieval{N10S06C06_d}$"
        ),
        'verso': r"$\xintiieval{N10S06C06_m}$",
        # Pour avoir une moyenne entière simple : on tire 4 valeurs
        # de somme = 4*m.
        'variables': (
            r"\xintdefiivar N10S06C06_m := randrange(8,20);" "\n"
            r"\xintdefiivar N10S06C06_a := N10S06C06_m + randrange(-3,3);" "\n"
            r"\xintdefiivar N10S06C06_b := N10S06C06_m + randrange(-3,3);" "\n"
            r"\xintdefiivar N10S06C06_c := N10S06C06_m + randrange(-3,3);" "\n"
            r"\xintdefiivar N10S06C06_d := "
            r"4*N10S06C06_m - N10S06C06_a - N10S06C06_b - N10S06C06_c;"
        ),
    },
    {
        'sequence': 'S06',
        'nom': "Procédure tableau effectifs",
        'type_pedago': 'procedure',
        'type_tech': 'fixe',
        'lien': ('methode', 1),
        'recto': (
            r"\textbf{Procédure} : organiser des données brutes en "
            r"tableau d'effectifs."
        ),
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Lister les \textbf{valeurs distinctes} (ordre croissant)." "\n"
            r"  \item Pour chaque valeur, \textbf{compter ses occurrences}." "\n"
            r"  \item Reporter en bas la ligne \textbf{Total}." "\n"
            r"  \item Vérifier que la somme = effectif total." "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
]


# ─────────────────────────────────────────────────────────────────────
# S07 — Probabilités
# Notions : expérience aléatoire, issue/événement, probabilité,
#           équiprobabilité
# Méthodes : échelle de prob., calcul en équiprob.
# ─────────────────────────────────────────────────────────────────────

CARTES_S07 = [
    {
        'sequence': 'S07',
        'nom': "Expérience aléatoire",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 1),
        'recto': r"Qu'est-ce qu'une \textbf{expérience aléatoire}?",
        'verso': (
            r"Une expérience dont on \textbf{ne peut pas prédire} "
            r"avec certitude le résultat."
            "\n\\smallskip\n\n"
            r"Exemples : lancer un dé, tirer une carte, jouer à pile ou face."
        ),
        'variables': '',
    },
    {
        'sequence': 'S07',
        'nom': "Issue vs événement",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Différence entre \textbf{issue} et \textbf{événement}?",
        'verso': (
            r"\textbf{Issue} : un \textbf{résultat possible} de l'expérience."
            "\n\\smallskip\n\n"
            r"\textbf{Événement} : un \textbf{ensemble d'issues} qu'on regroupe."
            "\n\\smallskip\n\n"
            r"Ex. dé : issue = $\{3\}$ ; événement « obtenir un nombre pair » = "
            r"$\{2;\,4;\,6\}$."
        ),
        'variables': '',
    },
    {
        'sequence': 'S07',
        'nom': "Encadrement d'une probabilité",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 3),
        'recto': r"Entre quelles valeurs une \textbf{probabilité} se situe-t-elle?",
        'verso': (
            r"$0 \le P(\text{événement}) \le 1$"
            "\n\\smallskip\n\n"
            r"$P=0$ : \textbf{impossible}." "\n"
            r"$P=1$ : \textbf{certain}." "\n"
            r"$P=0,5$ : « \textbf{une chance sur deux} »."
        ),
        'variables': '',
    },
    {
        'sequence': 'S07',
        'nom': "Définition équiprobabilité",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 4),
        'recto': r"Qu'est-ce que l'\textbf{équiprobabilité}?",
        'verso': (
            r"Une situation où toutes les issues ont "
            r"\textbf{la même probabilité}."
            "\n\\smallskip\n\n"
            r"Alors : "
            r"$P(\text{événement}) = "
            r"\seqFrac{\text{nb issues favorables}}{\text{nb issues totales}}$"
        ),
        'variables': '',
    },
    {
        'sequence': 'S07',
        'nom': "Proba pair avec un dé",
        'type_pedago': 'calcul',
        'type_tech': 'fixe',
        'lien': ('methode', 2),
        'recto': r"On lance un dé à $6$ faces. Quelle est la probabilité d'obtenir un \textbf{nombre pair}?",
        'verso': (
            r"Issues favorables : $\{2;\,4;\,6\}$, soit $3$." "\n"
            r"Issues totales : $6$." "\n"
            r"\smallskip" "\n\n"
            r"$P = \seqFrac{3}{6} = \seqFrac{1}{2}$"
        ),
        'variables': '',
    },
    {
        'sequence': 'S07',
        'nom': "Proba issue précise avec un dé",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 2),
        'recto': (
            r"On lance un dé à $6$ faces. "
            r"Probabilité d'obtenir $\xintiieval{N10S07C06_v}$?"
        ),
        'verso': r"$\seqFrac{1}{6}$",
        'variables': r"\xintdefiivar N10S07C06_v := randrange(1,6);",
    },
    {
        'sequence': 'S07',
        'nom': "Échelle de probabilité",
        'type_pedago': 'procedure',
        'type_tech': 'fixe',
        'lien': ('methode', 1),
        'recto': r"\textbf{Procédure} : placer un événement sur l'\textbf{échelle de probabilité}.",
        'verso': (
            r"Axe gradué de $0$ à $1$." "\n"
            r"\smallskip" "\n\n"
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Impossible $\to 0$" "\n"
            r"  \item Peu probable $\to$ proche de $0$" "\n"
            r"  \item Une chance sur deux $\to 0,5$" "\n"
            r"  \item Très probable $\to$ proche de $1$" "\n"
            r"  \item Certain $\to 1$" "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
]


# ─────────────────────────────────────────────────────────────────────
# S08 — Proportionnalité
# Notions : tableau et coef, passage à l'unité, linéarité, ratio, échelle
# Méthodes : reconnaître prop., 4e prop., ratio, échelle, problèmes
# ─────────────────────────────────────────────────────────────────────

CARTES_S08 = [
    {
        'sequence': 'S08',
        'nom': "Définition coefficient de prop.",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 1),
        'recto': r"Qu'est-ce que le \textbf{coefficient de proportionnalité}?",
        'verso': (
            r"Le nombre \textbf{constant} par lequel on passe de la "
            r"première ligne du tableau à la seconde."
            "\n\\smallskip\n\n"
            r"$\text{ligne 2} = \text{ligne 1} \times k$"
        ),
        'variables': '',
    },
    {
        'sequence': 'S08',
        'nom': "Reconnaître une situation prop.",
        'type_pedago': 'reconnaissance',
        'type_tech': 'fixe',
        'lien': ('methode', 1),
        'recto': r"Comment \textbf{reconnaître} une situation de proportionnalité dans un tableau?",
        'verso': (
            r"On vérifie que le \textbf{quotient ligne 2 / ligne 1} "
            r"est le \textbf{même} pour toutes les colonnes."
            "\n\\smallskip\n\n"
            r"Si oui $\to$ proportionnalité, et ce quotient est le "
            r"\textbf{coefficient}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S08',
        'nom': "Passage à l'unité",
        'type_pedago': 'procedure',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"\textbf{Procédure} : calculer une 4e proportionnelle par passage à l'unité.",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Diviser pour obtenir la valeur \textbf{pour $1$}." "\n"
            r"  \item Multiplier par la quantité voulue." "\n"
            r"\end{seqColEnum}"
            "\n\\smallskip\n\n"
            r"Ex. : si $3$ kg coûtent $9$ €, alors $1$ kg coûte $3$ €, "
            r"donc $5$ kg coûtent $15$ €."
        ),
        'variables': '',
    },
    {
        'sequence': 'S08',
        'nom': "Quatrième proportionnelle",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 2),
        'recto': (
            r"Si $\xintiieval{N10S08C04_a}$ articles coûtent "
            r"$\xintiieval{N10S08C04_pa}$ €, "
            r"combien coûtent $\xintiieval{N10S08C04_b}$ articles?"
        ),
        'verso': r"$\xintiieval{N10S08C04_pb}$ €",
        # Pour rester avec des entiers : on tire un prix unitaire entier
        'variables': (
            r"\xintdefiivar N10S08C04_pu := randrange(2,9);" "\n"
            r"\xintdefiivar N10S08C04_a := randrange(2,7);" "\n"
            r"\xintdefiivar N10S08C04_b := randrange(2,8);" "\n"
            r"\xintdefiivar N10S08C04_pa := N10S08C04_pu * N10S08C04_a;" "\n"
            r"\xintdefiivar N10S08C04_pb := N10S08C04_pu * N10S08C04_b;"
        ),
    },
    {
        'sequence': 'S08',
        'nom': "Définition ratio",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 4),
        'recto': r"Qu'est-ce qu'un \textbf{ratio}?",
        'verso': (
            r"Une comparaison de plusieurs grandeurs sous forme "
            r"$a : b$ (ou $a : b : c$)." "\n"
            r"\smallskip" "\n\n"
            r"Indique la \textbf{proportion relative} de chaque part."
            "\n\\smallskip\n\n"
            r"Ex. : ratio $2 : 3$ $\to$ pour $2$ parts de l'un, "
            r"$3$ parts de l'autre."
        ),
        'variables': '',
    },
    {
        'sequence': 'S08',
        'nom': "Définition échelle",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 5),
        'recto': r"Qu'est-ce que l'\textbf{échelle} d'un plan?",
        'verso': (
            r"$\text{échelle} = "
            r"\seqFrac{\text{distance sur le plan}}{\text{distance en réalité}}$"
            "\n\\smallskip\n\n"
            r"\textbf{Les deux distances doivent être dans la même unité}!"
            "\n\\smallskip\n\n"
            r"Ex. : $1/100$ signifie $1$ cm sur le plan = $100$ cm = $1$ m en réalité."
        ),
        'variables': '',
    },
    {
        'sequence': 'S08',
        'nom': "Pourcentage d'une quantité",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 5),
        'recto': (
            r"Calcule $\xintiieval{N10S08C07_p}\,\%$ de "
            r"$\xintiieval{N10S08C07_q}$."
        ),
        'verso': r"$\xintiieval{N10S08C07_res}$",
        # Choix tirage : on contraint q à être multiple de 100/p
        # pour garder un résultat entier. Plus simple : p ∈ {10,20,25,50}
        # et q multiple raisonnable.
        'variables': (
            r"\xintdefiivar N10S08C07_p := 10*randrange(1,9);" "\n"
            r"\xintdefiivar N10S08C07_k := randrange(2,15);" "\n"
            r"\xintdefiivar N10S08C07_q := 10 * N10S08C07_k;" "\n"
            r"\xintdefiivar N10S08C07_res := "
            r"N10S08C07_p * N10S08C07_q / 100;"
        ),
    },
    {
        'sequence': 'S08',
        'nom': "Linéarité",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 3),
        'recto': r"Que dit la \textbf{linéarité} dans un tableau de proportionnalité?",
        'verso': (
            r"\textbf{Additive} : si on ajoute deux colonnes, "
            r"on additionne aussi leurs grandeurs correspondantes." "\n"
            r"\smallskip" "\n\n"
            r"\textbf{Multiplicative} : si on multiplie une colonne par $k$, "
            r"on multiplie aussi sa grandeur correspondante par $k$."
        ),
        'variables': '',
    },
]


# ─────────────────────────────────────────────────────────────────────
# S09 — Fonctions (introduction très light en 5e)
# Notions : variable, variables dépendantes
# Méthodes : représenter par un tableau de valeurs
# ─────────────────────────────────────────────────────────────────────

CARTES_S09 = [
    {
        'sequence': 'S09',
        'nom': "Définition variable",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 1),
        'recto': r"Qu'est-ce qu'une \textbf{variable}?",
        'verso': (
            r"Une grandeur dont la valeur peut \textbf{changer}."
            "\n\\smallskip\n\n"
            r"Ex. : la \textbf{température}, l'\textbf{âge}, "
            r"le \textbf{prix} en fonction de la quantité."
        ),
        'variables': '',
    },
    {
        'sequence': 'S09',
        'nom': "Variables dépendantes",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Quand deux variables sont-elles \textbf{dépendantes}?",
        'verso': (
            r"Quand la valeur de l'une \textbf{dépend} de la valeur "
            r"de l'autre."
            "\n\\smallskip\n\n"
            r"Ex. : la \textbf{durée d'un trajet} dépend de la "
            r"\textbf{vitesse}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S09',
        'nom': "Tableau de valeurs",
        'type_pedago': 'procedure',
        'type_tech': 'fixe',
        'lien': ('methode', 1),
        'recto': (
            r"\textbf{Procédure} : représenter une relation entre "
            r"deux grandeurs par un tableau."
        ),
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Première ligne : \textbf{variable indépendante}." "\n"
            r"  \item Seconde ligne : \textbf{variable dépendante}." "\n"
            r"  \item Une colonne par couple de valeurs." "\n"
            r"  \item Légender chaque ligne (avec l'unité)." "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
]


# ─────────────────────────────────────────────────────────────────────
# S10 — Calcul de grandeurs
# Notions : périmètre, aire, conv. long./aire, durée, volume, conv. vol.
# Méthodes : P, A, conv. L/A, durées/horaires, conv. durée, V,
#            conv. V, unités cohérentes
# ─────────────────────────────────────────────────────────────────────

CARTES_S10 = [
    {
        'sequence': 'S10',
        'nom': "Périmètre rectangle",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 1),
        'recto': r"Formule du \textbf{périmètre} d'un rectangle?",
        'verso': (
            r"$P = 2 \times (L + \ell)$"
            "\n\\smallskip\n\n"
            r"avec $L$ la longueur et $\ell$ la largeur."
        ),
        'variables': '',
    },
    {
        'sequence': 'S10',
        'nom': "Périmètre cercle",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 1),
        'recto': r"Formule du \textbf{périmètre} d'un cercle de rayon $r$?",
        'verso': (
            r"$P = 2 \pi r$"
            "\n\\smallskip\n\n"
            r"(ou $P = \pi \times d$ avec $d$ le diamètre)"
        ),
        'variables': '',
    },
    {
        'sequence': 'S10',
        'nom': "Aire rectangle",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Formule de l'\textbf{aire} d'un rectangle?",
        'verso': (
            r"$A = L \times \ell$"
            "\n\\smallskip\n\n"
            r"avec $L$ la longueur et $\ell$ la largeur."
        ),
        'variables': '',
    },
    {
        'sequence': 'S10',
        'nom': "Aire triangle",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Formule de l'\textbf{aire} d'un triangle?",
        'verso': (
            r"$A = \seqFrac{\text{base} \times \text{hauteur}}{2}$"
            "\n\\smallskip\n\n"
            r"La \textbf{hauteur} est perpendiculaire à la base choisie."
        ),
        'variables': '',
    },
    {
        'sequence': 'S10',
        'nom': "Aire parallélogramme",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Formule de l'\textbf{aire} d'un parallélogramme?",
        'verso': (
            r"$A = \text{base} \times \text{hauteur}$"
            "\n\\smallskip\n\n"
            r"La \textbf{hauteur} est perpendiculaire à la base choisie."
        ),
        'variables': '',
    },
    {
        'sequence': 'S10',
        'nom': "Aire disque",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Formule de l'\textbf{aire} d'un disque de rayon $r$?",
        'verso': r"$A = \pi r^2$",
        'variables': '',
    },
    {
        'sequence': 'S10',
        'nom': "Volume pavé droit",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 5),
        'recto': r"Formule du \textbf{volume} d'un pavé droit?",
        'verso': (
            r"$V = L \times \ell \times h$"
            "\n\\smallskip\n\n"
            r"(longueur $\times$ largeur $\times$ hauteur)"
        ),
        'variables': '',
    },
    {
        'sequence': 'S10',
        'nom': "Volume prisme/cylindre",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 5),
        'recto': r"Formule du \textbf{volume} d'un prisme droit ou d'un cylindre?",
        'verso': (
            r"$V = \text{aire de base} \times \text{hauteur}$"
        ),
        'variables': '',
    },
    {
        'sequence': 'S10',
        'nom': "Périmètre rectangle (calcul)",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 1),
        'recto': (
            r"Périmètre d'un rectangle de $\xintiieval{N10S10C09_L}$ cm "
            r"sur $\xintiieval{N10S10C09_l}$ cm?"
        ),
        'verso': r"$\xintiieval{N10S10C09_p}$ cm",
        'variables': (
            r"\xintdefiivar N10S10C09_L := randrange(5,20);" "\n"
            r"\xintdefiivar N10S10C09_l := randrange(2,N10S10C09_L);" "\n"
            r"\xintdefiivar N10S10C09_p := 2*(N10S10C09_L + N10S10C09_l);"
        ),
    },
    {
        'sequence': 'S10',
        'nom': "Aire rectangle (calcul)",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 2),
        'recto': (
            r"Aire d'un rectangle de $\xintiieval{N10S10C10_L}$ cm "
            r"sur $\xintiieval{N10S10C10_l}$ cm?"
        ),
        'verso': r"$\xintiieval{N10S10C10_a}$ cm$^2$",
        'variables': (
            r"\xintdefiivar N10S10C10_L := randrange(5,15);" "\n"
            r"\xintdefiivar N10S10C10_l := randrange(2,12);" "\n"
            r"\xintdefiivar N10S10C10_a := N10S10C10_L * N10S10C10_l;"
        ),
    },
    {
        'sequence': 'S10',
        'nom': "Conversion km en m",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 3),
        'recto': (
            r"Convertis en mètres :"
            "\n\\smallskip\n\n"
            r"$\xintiieval{N10S10C11_k}$ km"
        ),
        'verso': r"$\xintiieval{N10S10C11_m}$ m",
        'variables': (
            r"\xintdefiivar N10S10C11_k := randrange(2,99);" "\n"
            r"\xintdefiivar N10S10C11_m := 1000 * N10S10C11_k;"
        ),
    },
    {
        'sequence': 'S10',
        'nom': "Conversion cm² en mm²",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 3),
        'recto': (
            r"Convertis en mm$^2$ :"
            "\n\\smallskip\n\n"
            r"$\xintiieval{N10S10C12_c}$ cm$^2$"
        ),
        'verso': r"$\xintiieval{N10S10C12_mm}$ mm$^2$",
        'variables': (
            r"\xintdefiivar N10S10C12_c := randrange(2,99);" "\n"
            r"\xintdefiivar N10S10C12_mm := 100 * N10S10C12_c;"
        ),
    },
    {
        'sequence': 'S10',
        'nom': "Durée entre 2 horaires",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('methode', 4),
        'recto': (
            r"Durée entre "
            r"$\xintiieval{N10S10C13_hd}$h$\xintiieval{N10S10C13_md}$ et "
            r"$\xintiieval{N10S10C13_hf}$h$\xintiieval{N10S10C13_mf}$?"
        ),
        'verso': (
            r"$\xintiieval{N10S10C13_dh}$h$\xintiieval{N10S10C13_dm}$"
        ),
        # On contraint : départ avant arrivée même heure ou plus tard,
        # et minutes choisies de sorte que la durée reste positive.
        'variables': (
            r"\xintdefiivar N10S10C13_hd := randrange(7,10);" "\n"
            r"\xintdefiivar N10S10C13_md := 5*randrange(0,11);" "\n"
            r"\xintdefiivar N10S10C13_dh := randrange(1,4);" "\n"
            r"\xintdefiivar N10S10C13_dm := 5*randrange(1,11);" "\n"
            r"\xintdefiivar N10S10C13_hf := "
            r"N10S10C13_hd + N10S10C13_dh + "
            r"((N10S10C13_md + N10S10C13_dm) >= 60 ? 1 : 0);" "\n"
            r"\xintdefiivar N10S10C13_mf := "
            r"(N10S10C13_md + N10S10C13_dm) "
            r"- ((N10S10C13_md + N10S10C13_dm) >= 60 ? 60 : 0);"
        ),
    },
    {
        'sequence': 'S10',
        'nom': "Conversion litres ↔ dm³",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('methode', 7),
        'recto': r"Quelle est l'\textbf{équivalence} entre litre et dm$^3$?",
        'verso': (
            r"$1$ L $= 1$ dm$^3$"
            "\n\\smallskip\n\n"
            r"Et donc : $1$ m$^3$ $= 1000$ L."
        ),
        'variables': '',
    },
]


# ─────────────────────────────────────────────────────────────────────
# S11 — Transformations géométriques
# Notions : image et invariant, symétrie axiale, symétrie centrale,
#           conservations
# Méthodes : constructions, transformer figure, frises/pavages/rosaces
# ─────────────────────────────────────────────────────────────────────

CARTES_S11 = [
    {
        'sequence': 'S11',
        'nom': "Définition image",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 1),
        'recto': r"Qu'est-ce que l'\textbf{image} d'un point par une transformation?",
        'verso': (
            r"Le point obtenu \textbf{après application} de la transformation."
            "\n\\smallskip\n\n"
            r"Si $A'$ est l'image de $A$, on écrit $A \to A'$."
        ),
        'variables': '',
    },
    {
        'sequence': 'S11',
        'nom': "Point invariant",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 1),
        'recto': r"Qu'est-ce qu'un \textbf{point invariant}?",
        'verso': (
            r"Un point qui est sa \textbf{propre image} par la transformation."
            "\n\\smallskip\n\n"
            r"$M = M'$"
        ),
        'variables': '',
    },
    {
        'sequence': 'S11',
        'nom': "Symétrie axiale (définition)",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"$A'$ est le symétrique de $A$ par rapport à la droite $(d)$. Que vérifie $(d)$?",
        'verso': (
            r"$(d)$ est la \textbf{médiatrice} du segment $[AA']$." "\n"
            r"\smallskip" "\n\n"
            r"C'est-à-dire :" "\n"
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item $(d) \perp (AA')$" "\n"
            r"  \item $(d)$ passe par le milieu de $[AA']$" "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S11',
        'nom': "Symétrie centrale (définition)",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 3),
        'recto': r"$A'$ est le symétrique de $A$ par rapport au point $O$. Que vérifie $O$?",
        'verso': (
            r"$O$ est le \textbf{milieu} du segment $[AA']$."
        ),
        'variables': '',
    },
    {
        'sequence': 'S11',
        'nom': "Conservations des symétries",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 4),
        'recto': r"Que \textbf{conservent} les symétries (axiale et centrale)?",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Les \textbf{longueurs}" "\n"
            r"  \item Les \textbf{angles}" "\n"
            r"  \item Les \textbf{aires}" "\n"
            r"  \item L'\textbf{alignement}" "\n"
            r"  \item Le \textbf{parallélisme} et la \textbf{perpendicularité}" "\n"
            r"\end{seqColEnum}"
            "\n\\smallskip\n\n"
            r"En résumé : la figure et son image sont \textbf{superposables}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S11',
        'nom': "Procédure sym. axiale (point)",
        'type_pedago': 'procedure',
        'type_tech': 'fixe',
        'lien': ('methode', 1),
        'recto': r"\textbf{Procédure} : construire le symétrique d'un point par rapport à une droite.",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Tracer la \textbf{perpendiculaire} à $(d)$ passant par $A$." "\n"
            r"  \item Reporter la \textbf{même distance} de l'autre côté." "\n"
            r"  \item Marquer $A'$." "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S11',
        'nom': "Procédure sym. centrale (point)",
        'type_pedago': 'procedure',
        'type_tech': 'fixe',
        'lien': ('methode', 2),
        'recto': r"\textbf{Procédure} : construire le symétrique d'un point par rapport à un point $O$.",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Tracer la \textbf{demi-droite} $[AO)$." "\n"
            r"  \item Reporter $OA$ \textbf{après} $O$ sur la même droite." "\n"
            r"  \item Marquer $A'$ : $O$ est milieu de $[AA']$." "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
]


# ─────────────────────────────────────────────────────────────────────
# S12 — Géométrie plane
# Notions : codage, angles (op. sommet, alt-int, corresp.),
#           inégalité triang., tri. particuliers, somme angles,
#           médiatrices, hauteurs, parallélogramme, centre sym.,
#           parallélo. particuliers
# Méthodes : démontrer angles, démontrer triangles, construire //,
#           démontrer //, programme de construction
# ─────────────────────────────────────────────────────────────────────

CARTES_S12 = [
    {
        'sequence': 'S12',
        'nom': "Angles opposés par sommet",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Que peut-on dire des angles \textbf{opposés par le sommet}?",
        'verso': r"Ils ont la \textbf{même mesure}.",
        'variables': '',
    },
    {
        'sequence': 'S12',
        'nom': "Angles alt.-int. et //",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 3),
        'recto': (
            r"Que sait-on des angles \textbf{alternes-internes} "
            r"formés par deux droites parallèles?"
        ),
        'verso': (
            r"Si les deux droites sont \textbf{parallèles}, "
            r"alors les angles alternes-internes sont \textbf{égaux}."
            "\n\\smallskip\n\n"
            r"Et \textbf{réciproquement}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S12',
        'nom': "Inégalité triangulaire",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 5),
        'recto': r"Quelle est l'\textbf{inégalité triangulaire}?",
        'verso': (
            r"Dans un triangle, la \textbf{longueur d'un côté} "
            r"est \textbf{inférieure ou égale} à la somme des deux autres."
            "\n\\smallskip\n\n"
            r"$AC \le AB + BC$"
            "\n\\smallskip\n\n"
            r"\textbf{Cas d'égalité}: les 3 points sont \textbf{alignés}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S12',
        'nom': "Somme des angles",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 7),
        'recto': r"\textbf{Somme} des angles d'un triangle?",
        'verso': r"$180°$",
        'variables': '',
    },
    {
        'sequence': 'S12',
        'nom': "Calculer le 3e angle",
        'type_pedago': 'calcul',
        'type_tech': 'parametree',
        'lien': ('notion', 7),
        'recto': (
            r"Dans un triangle, deux angles mesurent "
            r"$\xintiieval{N10S12C05_a}°$ et $\xintiieval{N10S12C05_b}°$. "
            r"Mesure du troisième?"
        ),
        'verso': r"$\xintiieval{N10S12C05_c}°$",
        'variables': (
            r"\xintdefiivar N10S12C05_a := randrange(30,80);" "\n"
            r"\xintdefiivar N10S12C05_b := randrange(30,80);" "\n"
            r"\xintdefiivar N10S12C05_c := 180 - N10S12C05_a - N10S12C05_b;"
        ),
    },
    {
        'sequence': 'S12',
        'nom': "Triangle isocèle",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 6),
        'recto': r"Qu'est-ce qu'un triangle \textbf{isocèle}?",
        'verso': (
            r"Un triangle ayant \textbf{deux côtés de même longueur}."
            "\n\\smallskip\n\n"
            r"Conséquence : \textbf{deux angles à la base sont égaux}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S12',
        'nom': "Triangle équilatéral",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 6),
        'recto': r"Qu'est-ce qu'un triangle \textbf{équilatéral}?",
        'verso': (
            r"Un triangle ayant \textbf{trois côtés de même longueur}."
            "\n\\smallskip\n\n"
            r"Conséquence : ses \textbf{trois angles mesurent $60°$}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S12',
        'nom': "Médiatrice",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 8),
        'recto': r"Qu'est-ce que la \textbf{médiatrice} d'un segment $[AB]$?",
        'verso': (
            r"La droite \textbf{perpendiculaire} à $[AB]$ "
            r"passant par son \textbf{milieu}."
            "\n\\smallskip\n\n"
            r"Propriété : tout point de la médiatrice est "
            r"\textbf{équidistant} de $A$ et $B$."
        ),
        'variables': '',
    },
    {
        'sequence': 'S12',
        'nom': "Hauteur d'un triangle",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 9),
        'recto': r"Qu'est-ce qu'une \textbf{hauteur} d'un triangle?",
        'verso': (
            r"La droite passant par un \textbf{sommet} "
            r"et \textbf{perpendiculaire} au côté opposé."
            "\n\\smallskip\n\n"
            r"Un triangle a \textbf{3 hauteurs}, "
            r"concourantes en l'\textbf{orthocentre}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S12',
        'nom': "Définition parallélogramme",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 10),
        'recto': r"Donne 3 \textbf{définitions équivalentes} d'un parallélogramme.",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Quadrilatère dont les \textbf{côtés opposés sont parallèles}." "\n"
            r"  \item Quadrilatère dont les \textbf{diagonales se coupent en leur milieu}." "\n"
            r"  \item Quadrilatère dont les \textbf{côtés opposés sont de même longueur}." "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S12',
        'nom': "Losange caractérisation",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 12),
        'recto': r"Qu'est-ce qu'un \textbf{losange}?",
        'verso': (
            r"Un parallélogramme dont les \textbf{4 côtés sont de même longueur}."
            "\n\\smallskip\n\n"
            r"Propriété : ses \textbf{diagonales} sont \textbf{perpendiculaires} "
            r"et se coupent en leur milieu."
        ),
        'variables': '',
    },
    {
        'sequence': 'S12',
        'nom': "Rectangle caractérisation",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 12),
        'recto': r"Qu'est-ce qu'un \textbf{rectangle}?",
        'verso': (
            r"Un parallélogramme dont les \textbf{4 angles sont droits}."
            "\n\\smallskip\n\n"
            r"Propriété : ses \textbf{diagonales} sont \textbf{de même longueur} "
            r"et se coupent en leur milieu."
        ),
        'variables': '',
    },
    {
        'sequence': 'S12',
        'nom': "Carré caractérisation",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 12),
        'recto': r"Qu'est-ce qu'un \textbf{carré}?",
        'verso': (
            r"Un parallélogramme qui est \textbf{à la fois} un "
            r"\textbf{rectangle} et un \textbf{losange}."
            "\n\\smallskip\n\n"
            r"Ses diagonales sont \textbf{de même longueur}, "
            r"\textbf{perpendiculaires} et se coupent en leur milieu."
        ),
        'variables': '',
    },
]


# ─────────────────────────────────────────────────────────────────────
# S13 — Représentation en trois dimensions
# Notions : perspective cavalière, patron, section plane
# Méthodes : reconnaître solide, perspective↔patron, section, logiciel
# ─────────────────────────────────────────────────────────────────────

CARTES_S13 = [
    {
        'sequence': 'S13',
        'nom': "Définition perspective cavalière",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 1),
        'recto': r"Qu'est-ce que la \textbf{perspective cavalière}?",
        'verso': (
            r"Une manière de représenter un solide en \textbf{2D}."
            "\n\\smallskip\n\n"
            r"\textbf{Règles} :" "\n"
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Faces parallèles au plan : \textbf{vraies dimensions}." "\n"
            r"  \item Arêtes fuyantes : \textbf{même direction}." "\n"
            r"  \item Arêtes cachées : en \textbf{pointillés}." "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S13',
        'nom': "Définition patron",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Qu'est-ce qu'un \textbf{patron} d'un solide?",
        'verso': (
            r"Le \textbf{développement à plat} de toutes les faces, "
            r"tel qu'on puisse \textbf{reconstituer} le solide en pliant."
        ),
        'variables': '',
    },
    {
        'sequence': 'S13',
        'nom': "Faces d'un pavé droit",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 2),
        'recto': r"Combien de \textbf{faces}, \textbf{arêtes} et \textbf{sommets} pour un pavé droit?",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item $6$ \textbf{faces} (rectangles, opposées deux à deux égales)" "\n"
            r"  \item $12$ \textbf{arêtes}" "\n"
            r"  \item $8$ \textbf{sommets}" "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S13',
        'nom': "Section pavé par plan //",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 3),
        'recto': (
            r"Section d'un pavé droit par un plan \textbf{parallèle à une face}?"
        ),
        'verso': (
            r"Un \textbf{rectangle} de mêmes dimensions que la face parallèle."
        ),
        'variables': '',
    },
    {
        'sequence': 'S13',
        'nom': "Section cylindre par plan ⊥",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('notion', 3),
        'recto': (
            r"Section d'un cylindre par un plan \textbf{perpendiculaire à l'axe}?"
        ),
        'verso': r"Un \textbf{disque} de même rayon que la base.",
        'variables': '',
    },
    {
        'sequence': 'S13',
        'nom': "Patron cylindre composé",
        'type_pedago': 'propriete',
        'type_tech': 'fixe',
        'lien': ('methode', 2),
        'recto': r"De quoi est composé le \textbf{patron d'un cylindre}?",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item $2$ \textbf{disques} (bases)" "\n"
            r"  \item $1$ \textbf{rectangle} dont une dimension = " "\n"
            r"        \textbf{périmètre de la base}, l'autre = \textbf{hauteur}" "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
]


# ─────────────────────────────────────────────────────────────────────
# S14 — Algorithmique et programmation
# Notions : algorithme/programme, instructions conditionnelles,
#           boucles, mise au point
# Méthodes : algo. débranchée, blocs, prog. géométrie
# ─────────────────────────────────────────────────────────────────────

CARTES_S14 = [
    {
        'sequence': 'S14',
        'nom': "Définition algorithme",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 1),
        'recto': r"Qu'est-ce qu'un \textbf{algorithme}?",
        'verso': (
            r"Une \textbf{suite finie d'instructions}, ordonnées et précises, "
            r"qui résout un problème ou accomplit une tâche."
            "\n\\smallskip\n\n"
            r"Un \textbf{programme} = un algorithme \textbf{écrit dans un langage} "
            r"compréhensible par un ordinateur."
        ),
        'variables': '',
    },
    {
        'sequence': 'S14',
        'nom': "Instruction conditionnelle",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 11),
        'recto': r"Qu'est-ce qu'une \textbf{instruction conditionnelle}?",
        'verso': (
            r"Une instruction qui exécute des blocs \textbf{différents} "
            r"selon qu'une condition est \textbf{vraie} ou \textbf{fausse}."
            "\n\\smallskip\n\n"
            r"Forme : \textbf{Si} \ldots\ \textbf{alors} \ldots\ "
            r"\textbf{sinon} \ldots\ \textbf{Fin si}."
        ),
        'variables': '',
    },
    {
        'sequence': 'S14',
        'nom': "Boucle",
        'type_pedago': 'definition',
        'type_tech': 'fixe',
        'lien': ('notion', 12),
        'recto': r"Qu'est-ce qu'une \textbf{boucle}?",
        'verso': (
            r"Une structure qui \textbf{répète plusieurs fois} une "
            r"même série d'instructions."
            "\n\\smallskip\n\n"
            r"Deux types courants :" "\n"
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item Boucle \textbf{« répéter $N$ fois »}" "\n"
            r"  \item Boucle \textbf{« tant que }$\ldots$\textbf{ »}" "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S14',
        'nom': "Mise au point d'un programme",
        'type_pedago': 'procedure',
        'type_tech': 'fixe',
        'lien': ('notion', 13),
        'recto': r"\textbf{Procédure} : mettre au point un programme qui ne fait pas ce qu'on attend.",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item \textbf{Tester} sur un cas simple connu." "\n"
            r"  \item Observer ce qui sort \textbf{vs} attendu." "\n"
            r"  \item \textbf{Localiser} l'écart (impression, point d'arrêt)." "\n"
            r"  \item \textbf{Corriger}, puis \textbf{retester}." "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
    {
        'sequence': 'S14',
        'nom': "Carré avec une boucle",
        'type_pedago': 'reconnaissance',
        'type_tech': 'fixe',
        'lien': ('methode', 3),
        'recto': r"En Scratch, comment tracer un \textbf{carré} de côté $100$ avec une boucle?",
        'verso': (
            r"\begin{seqColEnum}[nbCols=1]" "\n"
            r"  \item \textbf{répéter $4$ fois} :" "\n"
            r"    \begin{seqColEnum}[nbCols=1]" "\n"
            r"      \item avancer de $100$" "\n"
            r"      \item tourner de $90°$" "\n"
            r"    \end{seqColEnum}" "\n"
            r"\end{seqColEnum}"
        ),
        'variables': '',
    },
]


# ─────────────────────────────────────────────────────────────────────
# Liste maître
# ─────────────────────────────────────────────────────────────────────

TOUTES_CARTES_N10 = (
    CARTES_S01 + CARTES_S02 + CARTES_S03 + CARTES_S04 +
    CARTES_S05 + CARTES_S06 + CARTES_S07 + CARTES_S08 +
    CARTES_S09 + CARTES_S10 + CARTES_S11 + CARTES_S12 +
    CARTES_S13 + CARTES_S14
)


# Décompte rapide pour info dans le log de peuplement
COMPTE_PAR_SEQUENCE = {
    'S01': len(CARTES_S01),
    'S02': len(CARTES_S02),
    'S03': len(CARTES_S03),
    'S04': len(CARTES_S04),
    'S05': len(CARTES_S05),
    'S06': len(CARTES_S06),
    'S07': len(CARTES_S07),
    'S08': len(CARTES_S08),
    'S09': len(CARTES_S09),
    'S10': len(CARTES_S10),
    'S11': len(CARTES_S11),
    'S12': len(CARTES_S12),
    'S13': len(CARTES_S13),
    'S14': len(CARTES_S14),
}
