# -*- coding: utf-8 -*-
"""Données des cartes d'automatisme 4e — LOT 2 : S04, S05, S06.

Même format que le lot 1 (voir cartes_n11_lot1_data.py).
Cibles : S04 ~6, S05 ~8, S06 ~4.
"""

CARTES = [

    # ══════════════════════ S04 — Nombres premiers, fractions ════════════════
    {
        "sequence": "S04", "num": 1, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Définition nombre premier",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Qu'est-ce qu'un \textbf{nombre premier}?",
        "verso": r"Un entier qui a \textbf{exactement deux diviseurs} : "
                 r"$1$ et lui-même.",
        "variables": "",
    },
    {
        "sequence": "S04", "num": 2, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Premiers inférieurs à 30",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"Donne la liste des nombres premiers inférieurs à $30$.",
        "verso": r"$2, 3, 5, 7, 11, 13, 17, 19, 23, 29$.",
        "variables": "",
    },
    {
        "sequence": "S04", "num": 3, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "1 est-il premier?",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Le nombre $1$ est-il premier?",
        "verso": r"Non : il n'a qu'\textbf{un seul} diviseur ($1$), "
                 r"alors qu'un nombre premier en a exactement deux.",
        "variables": "",
    },
    {
        "sequence": "S04", "num": 4, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Simplifier une fraction",
        "lien_type": "methode", "lien_num": "5",
        "recto": r"Comment \textbf{simplifier} une fraction?",
        "verso": r"Diviser le numérateur et le dénominateur par un "
                 r"\textbf{même diviseur commun} (idéalement le PGCD).",
        "variables": "",
    },
    {
        "sequence": "S04", "num": 5, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Simplifier par un facteur",
        "lien_type": "methode", "lien_num": "5",
        "recto": r"Simplifie $\seqFrac{\xinttheiiexpr N11S04C05_num\relax}"
                 r"{\xinttheiiexpr N11S04C05_den\relax}$ par "
                 r"$\xinttheiiexpr N11S04C05_k\relax$.",
        "verso": r"$\seqFrac{\xinttheiiexpr N11S04C05_a\relax}"
                 r"{\xinttheiiexpr N11S04C05_b\relax}$",
        "variables": r"\xintdefiivar N11S04C05_a := randrange(1,9);"
                     "\n\\xintdefiivar N11S04C05_b := randrange(2,9);"
                     "\n\\xintdefiivar N11S04C05_k := randrange(2,6);"
                     "\n\\xintdefiivar N11S04C05_num := N11S04C05_a*N11S04C05_k;"
                     "\n\\xintdefiivar N11S04C05_den := N11S04C05_b*N11S04C05_k;",
    },
    {
        "sequence": "S04", "num": 6, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Décomposer en facteurs premiers",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Comment décomposer un entier en produit de "
                 r"\textbf{facteurs premiers}?",
        "verso": r"Le diviser successivement par les nombres premiers "
                 r"croissants ($2, 3, 5, 7, \ldots$) jusqu'à obtenir $1$.",
        "variables": "",
    },

    # ══════════════════════ S05 — Calcul littéral, équations ═════════════════
    {
        "sequence": "S05", "num": 1, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Définition équation",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Qu'est-ce qu'une \textbf{équation}?",
        "verso": r"Une égalité contenant une ou plusieurs "
                 r"\textbf{inconnues}, dont on cherche les valeurs qui la "
                 r"rendent vraie.",
        "variables": "",
    },
    {
        "sequence": "S05", "num": 2, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Distributivité simple",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"Développe $k(a+b)$.",
        "verso": r"$k(a+b) = ka + kb$.",
        "variables": "",
    },
    {
        "sequence": "S05", "num": 3, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Développer / factoriser",
        "lien_type": "notion", "lien_num": "03",
        "recto": r"Que veut dire \textbf{développer} et "
                 r"\textbf{factoriser}?",
        "verso": r"Développer : transformer un produit en somme. "
                 r"Factoriser : transformer une somme en produit.",
        "variables": "",
    },
    {
        "sequence": "S05", "num": 4, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Développer k(x+b)",
        "lien_type": "methode", "lien_num": "3",
        "recto": r"Développe $\xinttheiiexpr N11S05C04_k\relax"
                 r"(x + \xinttheiiexpr N11S05C04_b\relax)$.",
        "verso": r"$\xinttheiiexpr N11S05C04_k\relax x + "
                 r"\xinttheiiexpr N11S05C04_kb\relax$",
        "variables": r"\xintdefiivar N11S05C04_k := randrange(2,10);"
                     "\n\\xintdefiivar N11S05C04_b := randrange(2,10);"
                     "\n\\xintdefiivar N11S05C04_kb := N11S05C04_k*N11S05C04_b;",
    },
    {
        "sequence": "S05", "num": 5, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Réduire une expression",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Que signifie \textbf{réduire} une expression littérale?",
        "verso": r"Regrouper les termes de \textbf{même nature} "
                 r"(les « $x$ » ensemble, les nombres ensemble)."
                 r"\smallskip\par Ex. $3x + 5 + 2x = 5x + 5$.",
        "variables": "",
    },
    {
        "sequence": "S05", "num": 6, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Tester une solution",
        "lien_type": "methode", "lien_num": "5",
        "recto": r"Comment tester si un nombre est \textbf{solution} d'une "
                 r"équation?",
        "verso": r"Le remplacer à la place de l'inconnue et vérifier si "
                 r"l'\textbf{égalité est vraie}.",
        "variables": "",
    },
    {
        "sequence": "S05", "num": 7, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Résoudre ax = b",
        "lien_type": "methode", "lien_num": "7",
        "recto": r"Résous $\xinttheiiexpr N11S05C07_a\relax x = "
                 r"\xinttheiiexpr N11S05C07_b\relax$.",
        "verso": r"$x = \seqFrac{\xinttheiiexpr N11S05C07_b\relax}"
                 r"{\xinttheiiexpr N11S05C07_a\relax}$",
        "variables": r"\xintdefiivar N11S05C07_a := randrange(2,10);"
                     "\n\\xintdefiivar N11S05C07_x := randrange(2,10);"
                     "\n\\xintdefiivar N11S05C07_b := N11S05C07_a*N11S05C07_x;",
    },
    {
        "sequence": "S05", "num": 8, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Réduire ax + bx",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Réduis $\xinttheiiexpr N11S05C08_a\relax x + "
                 r"\xinttheiiexpr N11S05C08_b\relax x$.",
        "verso": r"$\xinttheiiexpr N11S05C08_s\relax x$",
        "variables": r"\xintdefiivar N11S05C08_a := randrange(2,9);"
                     "\n\\xintdefiivar N11S05C08_b := randrange(2,9);"
                     "\n\\xintdefiivar N11S05C08_s := N11S05C08_a+N11S05C08_b;",
    },

    # ══════════════════════ S06 — Statistiques ══════════════════════════════
    {
        "sequence": "S06", "num": 1, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Définition médiane",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Qu'est-ce que la \textbf{médiane} d'une série?",
        "verso": r"Une valeur qui partage la série ordonnée en deux : "
                 r"au moins la moitié des valeurs lui sont "
                 r"$\leq$, au moins la moitié lui sont $\geq$.",
        "variables": "",
    },
    {
        "sequence": "S06", "num": 2, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Calculer la médiane",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Comment trouver la médiane d'une liste de valeurs?",
        "verso": r"\begin{seqColEnum}[nbCols=1]"
                 r"\item \textbf{Ordonner} les valeurs."
                 r"\item Prendre la valeur \textbf{du milieu} (ou la moyenne "
                 r"des deux valeurs centrales si l'effectif est pair)."
                 r"\end{seqColEnum}",
        "variables": "",
    },
    {
        "sequence": "S06", "num": 3, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Angle d'un secteur",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Dans un diagramme circulaire, quel angle représente "
                 r"$\xinttheiiexpr N11S06C03_n\relax$ individus sur "
                 r"$\xinttheiiexpr N11S06C03_t\relax$?",
        "verso": r"$\xinttheiiexpr N11S06C03_ang\relax^\circ$",
        # Total fixé à 60 (divise 360) : l'angle n*360/60 = n*6 est entier.
        "variables": r"\xintdefiivar N11S06C03_t := 60;"
                     "\n\\xintdefiivar N11S06C03_n := randrange(5,55);"
                     "\n\\xintdefiivar N11S06C03_ang := N11S06C03_n*6;",
    },
    {
        "sequence": "S06", "num": 4, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Total d'un diagramme circulaire",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"À quel angle correspond l'effectif total dans un "
                 r"diagramme circulaire?",
        "verso": r"$360^\circ$ (le disque entier). Chaque secteur est "
                 r"\textbf{proportionnel} à son effectif.",
        "variables": "",
    },
]
