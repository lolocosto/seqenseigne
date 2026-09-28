# -*- coding: utf-8 -*-
"""Données des cartes d'automatisme 4e — LOT 3 : S07 à S14.

Même format que les lots 1 et 2. Cibles (4 cartes/semaine, plan de charge) :
S07=6, S08=6, S09=6, S10=14, S11=8, S12=20, S13=6, S14=6.
"""

CARTES = [

    # ══════════════════════ S07 — Probabilités ══════════════════════════════
    {
        "sequence": "S07", "num": 1, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Événement certain / impossible",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Quelle est la probabilité d'un événement \textbf{certain}? "
                 r"D'un événement \textbf{impossible}?",
        "verso": r"Certain : $1$ (soit $100\,\%$). Impossible : $0$.",
        "variables": "",
    },
    {
        "sequence": "S07", "num": 2, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Événements contraires",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"Que vaut la somme des probabilités de deux événements "
                 r"\textbf{contraires}?",
        "verso": r"$1$ : $P(E) + P(\overline{E}) = 1$, "
                 r"donc $P(\overline{E}) = 1 - P(E)$.",
        "variables": "",
    },
    {
        "sequence": "S07", "num": 3, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Somme des probabilités",
        "lien_type": "notion", "lien_num": "03",
        "recto": r"Que vaut la somme des probabilités de toutes les issues "
                 r"d'une expérience aléatoire?",
        "verso": r"$1$ (soit $100\,\%$).",
        "variables": "",
    },
    {
        "sequence": "S07", "num": 4, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Encadrement d'une probabilité",
        "lien_type": "methode", "lien_num": "4",
        "recto": r"Entre quelles valeurs est toujours comprise une "
                 r"probabilité?",
        "verso": r"Entre $0$ et $1$ : $0 \leq P(E) \leq 1$.",
        "variables": "",
    },
    {
        "sequence": "S07", "num": 5, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Probabilité d'un tirage",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Une urne contient $\xinttheiiexpr N11S07C05_t\relax$ boules "
                 r"dont $\xinttheiiexpr N11S07C05_f\relax$ rouges. "
                 r"Probabilité de tirer une rouge?",
        "verso": r"$\seqFrac{\xinttheiiexpr N11S07C05_f\relax}"
                 r"{\xinttheiiexpr N11S07C05_t\relax}$",
        "variables": r"\xintdefiivar N11S07C05_t := randrange(5,20);"
                     "\n\\xintdefiivar N11S07C05_f := "
                     r"randrange(1, N11S07C05_t);",
    },
    {
        "sequence": "S07", "num": 6, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Événement contraire (calcul)",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"La probabilité d'un événement est "
                 r"$\seqFrac{\xinttheiiexpr N11S07C06_a\relax}"
                 r"{\xinttheiiexpr N11S07C06_n\relax}$. "
                 r"Quelle est celle de son contraire?",
        "verso": r"$\seqFrac{\xinttheiiexpr N11S07C06_b\relax}"
                 r"{\xinttheiiexpr N11S07C06_n\relax}$",
        "variables": r"\xintdefiivar N11S07C06_n := randrange(4,12);"
                     "\n\\xintdefiivar N11S07C06_a := "
                     r"randrange(1, N11S07C06_n);"
                     "\n\\xintdefiivar N11S07C06_b := N11S07C06_n-N11S07C06_a;",
    },

    # ══════════════════════ S08 — Proportionnalité (produit en croix) ════════
    {
        "sequence": "S08", "num": 1, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Égalité des produits en croix",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Si $\seqFrac{a}{b} = \seqFrac{c}{d}$, quelle égalité de "
                 r"produits en croix a-t-on?",
        "verso": r"$a \times d = b \times c$.",
        "variables": "",
    },
    {
        "sequence": "S08", "num": 2, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "Proportionnalité graphique",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Comment reconnaît-on une situation de proportionnalité "
                 r"sur un graphique?",
        "verso": r"Les points sont \textbf{alignés avec l'origine} "
                 r"(droite passant par $O$).",
        "variables": "",
    },
    {
        "sequence": "S08", "num": 3, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Quatrième proportionnelle",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Comment calculer une \textbf{quatrième proportionnelle}?",
        "verso": r"Par le produit en croix : si "
                 r"$\seqFrac{a}{b} = \seqFrac{x}{d}$, alors "
                 r"$x = \seqFrac{a \times d}{b}$.",
        "variables": "",
    },
    {
        "sequence": "S08", "num": 4, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Quatrième proportionnelle (calcul)",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"$\xinttheiiexpr N11S08C04_a\relax$ objets coûtent "
                 r"$\xinttheiiexpr N11S08C04_p\relax$ €. Combien coûtent "
                 r"$\xinttheiiexpr N11S08C04_a2\relax$ objets?",
        "verso": r"$\xinttheiiexpr N11S08C04_p2\relax$ €",
        "variables": r"\xintdefiivar N11S08C04_a := randrange(2,6);"
                     "\n\\xintdefiivar N11S08C04_pu := randrange(2,9);"
                     "\n\\xintdefiivar N11S08C04_p := N11S08C04_a*N11S08C04_pu;"
                     "\n\\xintdefiivar N11S08C04_k := randrange(2,5);"
                     "\n\\xintdefiivar N11S08C04_a2 := N11S08C04_a*N11S08C04_k;"
                     "\n\\xintdefiivar N11S08C04_p2 := N11S08C04_p*N11S08C04_k;",
    },
    {
        "sequence": "S08", "num": 5, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Vérifier une proportion",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"$\seqFrac{\xinttheiiexpr N11S08C05_a\relax}"
                 r"{\xinttheiiexpr N11S08C05_b\relax}$ et "
                 r"$\seqFrac{\xinttheiiexpr N11S08C05_c\relax}"
                 r"{\xinttheiiexpr N11S08C05_d\relax}$ sont-elles égales?",
        "verso": r"Oui : $\xinttheiiexpr N11S08C05_a\relax \times "
                 r"\xinttheiiexpr N11S08C05_d\relax = "
                 r"\xinttheiiexpr N11S08C05_b\relax \times "
                 r"\xinttheiiexpr N11S08C05_c\relax$.",
        "variables": r"\xintdefiivar N11S08C05_a := randrange(2,6);"
                     "\n\\xintdefiivar N11S08C05_b := randrange(2,6);"
                     "\n\\xintdefiivar N11S08C05_k := randrange(2,5);"
                     "\n\\xintdefiivar N11S08C05_c := N11S08C05_a*N11S08C05_k;"
                     "\n\\xintdefiivar N11S08C05_d := N11S08C05_b*N11S08C05_k;",
    },
    {
        "sequence": "S08", "num": 6, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Coefficient de proportionnalité",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"Qu'est-ce que le \textbf{coefficient de "
                 r"proportionnalité}?",
        "verso": r"Le nombre par lequel on multiplie chaque valeur d'une "
                 r"grandeur pour obtenir l'autre.",
        "variables": "",
    },

    # ══════════════════════ S09 — Repérage, dépendance ═══════════════════════
    {
        "sequence": "S09", "num": 1, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Abscisse et ordonnée",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Dans un couple de coordonnées $(x\,;\,y)$, "
                 r"que sont $x$ et $y$?",
        "verso": r"$x$ est l'\textbf{abscisse} (axe horizontal), "
                 r"$y$ l'\textbf{ordonnée} (axe vertical).",
        "variables": "",
    },
    {
        "sequence": "S09", "num": 2, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Origine du repère",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Quelles sont les coordonnées de l'\textbf{origine} d'un "
                 r"repère?",
        "verso": r"$(0\,;\,0)$.",
        "variables": "",
    },
    {
        "sequence": "S09", "num": 3, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Lire des coordonnées",
        "lien_type": "methode", "lien_num": "3",
        "recto": r"Comment lit-on les coordonnées d'un point dans un repère?",
        "verso": r"\begin{seqColEnum}[nbCols=1]"
                 r"\item Lire l'\textbf{abscisse} sur l'axe horizontal."
                 r"\item Lire l'\textbf{ordonnée} sur l'axe vertical."
                 r"\end{seqColEnum}",
        "variables": "",
    },
    {
        "sequence": "S09", "num": 4, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "Ordre des coordonnées",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Dans le couple $(x\,;\,y)$, quelle coordonnée est écrite "
                 r"en premier?",
        "verso": r"L'\textbf{abscisse} $x$ (toujours avant l'ordonnée).",
        "variables": "",
    },
    {
        "sequence": "S09", "num": 5, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Dépendance de deux grandeurs",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Que représente une \textbf{formule} liant deux grandeurs "
                 r"comme $y = 3x$?",
        "verso": r"La \textbf{dépendance} d'une grandeur ($y$) en fonction "
                 r"de l'autre ($x$).",
        "variables": "",
    },
    {
        "sequence": "S09", "num": 6, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Évaluer une expression",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Pour $y = \xinttheiiexpr N11S09C06_a\relax x$, "
                 r"combien vaut $y$ quand $x = "
                 r"\xinttheiiexpr N11S09C06_x\relax$?",
        "verso": r"$y = \xinttheiiexpr N11S09C06_y\relax$",
        "variables": r"\xintdefiivar N11S09C06_a := randrange(2,10);"
                     "\n\\xintdefiivar N11S09C06_x := randrange(2,10);"
                     "\n\\xintdefiivar N11S09C06_y := N11S09C06_a*N11S09C06_x;",
    },

    # ══════════════════════ S10 — Volumes, grandeurs composées ═══════════════
    {
        "sequence": "S10", "num": 1, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Volume d'une pyramide",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Quelle est la formule du volume d'une \textbf{pyramide} "
                 r"(ou d'un cône)?",
        "verso": r"$V = \seqFrac{\mathcal{A}_{\text{base}} \times h}{3}$.",
        "variables": "",
    },
    {
        "sequence": "S10", "num": 2, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Volume d'un pavé droit",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Quelle est la formule du volume d'un \textbf{pavé droit}?",
        "verso": r"$V = L \times l \times h$ (longueur $\times$ largeur "
                 r"$\times$ hauteur).",
        "variables": "",
    },
    {
        "sequence": "S10", "num": 3, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Volume d'un cube",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Quelle est la formule du volume d'un \textbf{cube} "
                 r"d'arête $a$?",
        "verso": r"$V = a^3$.",
        "variables": "",
    },
    {
        "sequence": "S10", "num": 4, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Volume d'un cylindre",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Quelle est la formule du volume d'un \textbf{cylindre} "
                 r"(rayon $r$, hauteur $h$)?",
        "verso": r"$V = \pi \times r^2 \times h$.",
        "variables": "",
    },
    {
        "sequence": "S10", "num": 5, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Volume d'un pavé (calcul)",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Volume d'un pavé $\xinttheiiexpr N11S10C05_L\relax \times "
                 r"\xinttheiiexpr N11S10C05_l\relax \times "
                 r"\xinttheiiexpr N11S10C05_h\relax$ (cm)?",
        "verso": r"$\xinttheiiexpr N11S10C05_v\relax$ cm³",
        "variables": r"\xintdefiivar N11S10C05_L := randrange(2,10);"
                     "\n\\xintdefiivar N11S10C05_l := randrange(2,10);"
                     "\n\\xintdefiivar N11S10C05_h := randrange(2,10);"
                     "\n\\xintdefiivar N11S10C05_v := "
                     r"N11S10C05_L*N11S10C05_l*N11S10C05_h;",
    },
    {
        "sequence": "S10", "num": 6, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Volume d'un cube (calcul)",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Volume d'un cube d'arête "
                 r"$\xinttheiiexpr N11S10C06_a\relax$ cm?",
        "verso": r"$\xinttheiiexpr N11S10C06_v\relax$ cm³",
        "variables": r"\xintdefiivar N11S10C06_a := randrange(2,10);"
                     "\n\\xintdefiivar N11S10C06_v := N11S10C06_a^3;",
    },
    {
        "sequence": "S10", "num": 7, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Grandeur composée",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"Qu'est-ce qu'une \textbf{grandeur composée}?",
        "verso": r"Une grandeur obtenue en combinant d'autres grandeurs "
                 r"(produit ou quotient), ex. la vitesse (km/h).",
        "variables": "",
    },
    {
        "sequence": "S10", "num": 8, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Vitesse moyenne",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Quelle est la formule de la \textbf{vitesse moyenne}?",
        "verso": r"$v = \seqFrac{d}{t}$ (distance sur temps).",
        "variables": "",
    },
    {
        "sequence": "S10", "num": 9, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Calcul de vitesse",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Un mobile parcourt $\xinttheiiexpr N11S10C09_d\relax$ km "
                 r"en $\xinttheiiexpr N11S10C09_t\relax$ h. Sa vitesse "
                 r"moyenne?",
        "verso": r"$\xinttheiiexpr N11S10C09_v\relax$ km/h",
        "variables": r"\xintdefiivar N11S10C09_v := randrange(30,120);"
                     "\n\\xintdefiivar N11S10C09_t := randrange(2,6);"
                     "\n\\xintdefiivar N11S10C09_d := N11S10C09_v*N11S10C09_t;",
    },
    {
        "sequence": "S10", "num": 10, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Conversion cm³ / L",
        "lien_type": "methode", "lien_num": "3",
        "recto": r"À combien de litres correspond $1$ dm³? Et $1000$ cm³?",
        "verso": r"$1\ \text{dm}^3 = 1\ \text{L}$, "
                 r"et $1000\ \text{cm}^3 = 1\ \text{L}$.",
        "variables": "",
    },
    {
        "sequence": "S10", "num": 11, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Aire du disque",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Quelle est la formule de l'\textbf{aire d'un disque} de "
                 r"rayon $r$?",
        "verso": r"$\mathcal{A} = \pi \times r^2$.",
        "variables": "",
    },
    {
        "sequence": "S10", "num": 12, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Périmètre du cercle",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Quelle est la formule du \textbf{périmètre d'un cercle} "
                 r"de rayon $r$?",
        "verso": r"$P = 2 \times \pi \times r$.",
        "variables": "",
    },
    {
        "sequence": "S10", "num": 13, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Aire d'un rectangle",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Aire d'un rectangle "
                 r"$\xinttheiiexpr N11S10C13_L\relax \times "
                 r"\xinttheiiexpr N11S10C13_l\relax$ (cm)?",
        "verso": r"$\xinttheiiexpr N11S10C13_a\relax$ cm²",
        "variables": r"\xintdefiivar N11S10C13_L := randrange(3,15);"
                     "\n\\xintdefiivar N11S10C13_l := randrange(2,12);"
                     "\n\\xintdefiivar N11S10C13_a := N11S10C13_L*N11S10C13_l;",
    },
    {
        "sequence": "S10", "num": 14, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Convertir une durée",
        "lien_type": "methode", "lien_num": "3",
        "recto": r"Combien de minutes dans $1$ h $30$ min?",
        "verso": r"$90$ minutes ($60 + 30$).",
        "variables": "",
    },

    # ══════════════════════ S11 — Translations, rotations, triangles égaux ═══
    {
        "sequence": "S11", "num": 1, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Définition translation",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Par quoi est définie une \textbf{translation}?",
        "verso": r"Une \textbf{direction}, un \textbf{sens} et une "
                 r"\textbf{longueur} (donnés par deux points $A$ et $B$).",
        "variables": "",
    },
    {
        "sequence": "S11", "num": 2, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Définition rotation",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"Par quoi est définie une \textbf{rotation}?",
        "verso": r"Un \textbf{centre}, un \textbf{angle} et un \textbf{sens} "
                 r"de rotation.",
        "variables": "",
    },
    {
        "sequence": "S11", "num": 3, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Conservations",
        "lien_type": "notion", "lien_num": "03",
        "recto": r"Que conservent les translations et les rotations?",
        "verso": r"Les \textbf{longueurs}, les \textbf{angles}, "
                 r"l'\textbf{alignement} et les \textbf{aires} "
                 r"(ce sont des isométries).",
        "variables": "",
    },
    {
        "sequence": "S11", "num": 4, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Triangles égaux",
        "lien_type": "notion", "lien_num": "04",
        "recto": r"Que sont deux \textbf{triangles égaux}?",
        "verso": r"Deux triangles dont les côtés sont deux à deux de "
                 r"\textbf{même longueur} (superposables).",
        "variables": "",
    },
    {
        "sequence": "S11", "num": 5, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Image par translation",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Quelle est la nature de l'image d'un segment par une "
                 r"translation?",
        "verso": r"Un segment \textbf{parallèle} et de \textbf{même "
                 r"longueur}.",
        "variables": "",
    },
    {
        "sequence": "S11", "num": 6, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "Transformations dans une frise",
        "lien_type": "methode", "lien_num": "6",
        "recto": r"Quelle transformation permet de passer d'un motif au "
                 r"suivant dans une \textbf{frise}?",
        "verso": r"Le plus souvent une \textbf{translation} "
                 r"(parfois une symétrie ou une rotation).",
        "variables": "",
    },
    {
        "sequence": "S11", "num": 7, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Angle plein",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"Quelle rotation redonne la figure de départ?",
        "verso": r"Une rotation d'angle $360^\circ$ (un tour complet).",
        "variables": "",
    },
    {
        "sequence": "S11", "num": 8, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "Demi-tour",
        "lien_type": "methode", "lien_num": "4",
        "recto": r"À quelle transformation correspond une rotation de "
                 r"$180^\circ$?",
        "verso": r"Une \textbf{symétrie centrale} (demi-tour autour du "
                 r"centre).",
        "variables": "",
    },

    # ══════════════════════ S12 — Pythagore, Thalès, cosinus ═════════════════
    {
        "sequence": "S12", "num": 1, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Égalité de Pythagore",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Dans un triangle $ABC$ rectangle en $A$, quelle est "
                 r"l'égalité de Pythagore?",
        "verso": r"$BC^2 = AB^2 + AC^2$ (l'hypoténuse $[BC]$ au carré).",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 2, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Hypoténuse",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Qu'est-ce que l'\textbf{hypoténuse} d'un triangle "
                 r"rectangle?",
        "verso": r"Le côté \textbf{opposé à l'angle droit} "
                 r"(le plus long).",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 3, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Réciproque de Pythagore",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Comment prouver qu'un triangle est rectangle avec "
                 r"Pythagore?",
        "verso": r"Si le carré du plus grand côté \textbf{égale} la somme "
                 r"des carrés des deux autres, il est rectangle.",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 4, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Hypoténuse (triplet)",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Triangle rectangle de côtés "
                 r"$\xinttheiiexpr N11S12C04_a\relax$ et "
                 r"$\xinttheiiexpr N11S12C04_b\relax$. Hypoténuse?",
        "verso": r"$\xinttheiiexpr N11S12C04_c\relax$",
        # Triplets pythagoriciens : (3,4,5) mis à l'échelle → hypoténuse entière.
        "variables": r"\xintdefiivar N11S12C04_k := randrange(1,6);"
                     "\n\\xintdefiivar N11S12C04_a := 3*N11S12C04_k;"
                     "\n\\xintdefiivar N11S12C04_b := 4*N11S12C04_k;"
                     "\n\\xintdefiivar N11S12C04_c := 5*N11S12C04_k;",
    },
    {
        "sequence": "S12", "num": 5, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Théorème de Thalès (configuration)",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"Dans la configuration de Thalès (droites parallèles), "
                 r"que sont les rapports de longueurs?",
        "verso": r"Ils sont \textbf{égaux} : "
                 r"$\seqFrac{AD}{AB} = \seqFrac{AE}{AC} = \seqFrac{DE}{BC}$.",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 6, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Réciproque de Thalès",
        "lien_type": "methode", "lien_num": "4",
        "recto": r"Comment prouver que deux droites sont parallèles avec "
                 r"Thalès?",
        "verso": r"Si les rapports $\seqFrac{AD}{AB}$ et $\seqFrac{AE}{AC}$ "
                 r"sont \textbf{égaux} (points bien placés), les droites "
                 r"sont parallèles.",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 7, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Définition cosinus",
        "lien_type": "notion", "lien_num": "03",
        "recto": r"Dans un triangle rectangle, à quoi est égal le "
                 r"\textbf{cosinus} d'un angle aigu?",
        "verso": r"$\cos = \seqFrac{\text{côté adjacent}}"
                 r"{\text{hypoténuse}}$.",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 8, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Encadrement du cosinus",
        "lien_type": "notion", "lien_num": "03",
        "recto": r"Entre quelles valeurs est compris le cosinus d'un angle "
                 r"aigu?",
        "verso": r"Entre $0$ et $1$ : $0 < \cos(\widehat{A}) < 1$.",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 9, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Carré d'une longueur",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Combien vaut $\xinttheiiexpr N11S12C09_a\relax^2$?",
        "verso": r"$\xinttheiiexpr N11S12C09_c\relax$",
        "variables": r"\xintdefiivar N11S12C09_a := randrange(5,20);"
                     "\n\\xintdefiivar N11S12C09_c := N11S12C09_a^2;",
    },
    {
        "sequence": "S12", "num": 10, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "Côté adjacent",
        "lien_type": "notion", "lien_num": "03",
        "recto": r"Qu'est-ce que le côté \textbf{adjacent} à un angle dans "
                 r"un triangle rectangle?",
        "verso": r"Le côté qui \textbf{forme l'angle} avec l'hypoténuse "
                 r"(hors angle droit).",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 11, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Pythagore : calculer un côté",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Comment calculer un côté de l'angle droit avec "
                 r"Pythagore?",
        "verso": r"On \textbf{soustrait} : "
                 r"$AB^2 = BC^2 - AC^2$, puis on prend la racine carrée.",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 12, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Contraposée de Pythagore",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Que conclut-on si $BC^2 \neq AB^2 + AC^2$?",
        "verso": r"Le triangle \textbf{n'est pas rectangle}.",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 13, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Vérifier un triangle rectangle",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Un triangle a pour côtés $\xinttheiiexpr N11S12C13_a\relax$, "
                 r"$\xinttheiiexpr N11S12C13_b\relax$, "
                 r"$\xinttheiiexpr N11S12C13_c\relax$. Est-il rectangle?",
        "verso": r"Oui : $\xinttheiiexpr N11S12C13_a2\relax + "
                 r"\xinttheiiexpr N11S12C13_b2\relax = "
                 r"\xinttheiiexpr N11S12C13_c2\relax$.",
        "variables": r"\xintdefiivar N11S12C13_k := randrange(1,4);"
                     "\n\\xintdefiivar N11S12C13_a := 3*N11S12C13_k;"
                     "\n\\xintdefiivar N11S12C13_b := 4*N11S12C13_k;"
                     "\n\\xintdefiivar N11S12C13_c := 5*N11S12C13_k;"
                     "\n\\xintdefiivar N11S12C13_a2 := N11S12C13_a^2;"
                     "\n\\xintdefiivar N11S12C13_b2 := N11S12C13_b^2;"
                     "\n\\xintdefiivar N11S12C13_c2 := N11S12C13_c^2;",
    },
    {
        "sequence": "S12", "num": 14, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Cosinus de 60 degrés",
        "lien_type": "methode", "lien_num": "5",
        "recto": r"Combien vaut $\cos(60^\circ)$?",
        "verso": r"$\cos(60^\circ) = \seqFrac{1}{2} = 0{,}5$.",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 15, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Cosinus de 0 degré",
        "lien_type": "notion", "lien_num": "03",
        "recto": r"Combien vaut $\cos(0^\circ)$?",
        "verso": r"$\cos(0^\circ) = 1$.",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 16, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Thalès : calculer une longueur",
        "lien_type": "methode", "lien_num": "3",
        "recto": r"Comment calcule-t-on une longueur avec le théorème de "
                 r"Thalès?",
        "verso": r"En écrivant l'\textbf{égalité des rapports}, puis par "
                 r"produit en croix.",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 17, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "Triplet pythagoricien 3-4-5",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Cite le plus connu des triplets pythagoriciens.",
        "verso": r"$(3\,;\,4\,;\,5)$ : $3^2 + 4^2 = 5^2$.",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 18, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Somme de deux carrés",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Combien vaut $\xinttheiiexpr N11S12C18_a\relax^2 + "
                 r"\xinttheiiexpr N11S12C18_b\relax^2$?",
        "verso": r"$\xinttheiiexpr N11S12C18_s\relax$",
        "variables": r"\xintdefiivar N11S12C18_a := randrange(2,10);"
                     "\n\\xintdefiivar N11S12C18_b := randrange(2,10);"
                     "\n\\xintdefiivar N11S12C18_s := "
                     r"N11S12C18_a^2 + N11S12C18_b^2;",
    },
    {
        "sequence": "S12", "num": 19, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Côté opposé",
        "lien_type": "notion", "lien_num": "03",
        "recto": r"Dans un triangle rectangle, qu'est-ce que le côté "
                 r"\textbf{opposé} à un angle aigu?",
        "verso": r"Le côté qui \textbf{ne touche pas} cet angle "
                 r"(face à lui).",
        "variables": "",
    },
    {
        "sequence": "S12", "num": 20, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Configuration Thalès (papillon)",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"Thalès s'applique-t-il aussi dans la configuration "
                 r"\og papillon \fg{} (droites sécantes)?",
        "verso": r"Oui, si les droites sont \textbf{parallèles} : les "
                 r"rapports de longueurs restent égaux.",
        "variables": "",
    },

    # ══════════════════════ S13 — Espace, patrons, sections ══════════════════
    {
        "sequence": "S13", "num": 1, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Coordonnées dans l'espace",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Combien de nombres définissent un point dans un "
                 r"\textbf{repère de l'espace}?",
        "verso": r"Trois : \textbf{abscisse}, \textbf{ordonnée} et "
                 r"\textbf{altitude} (ou cote).",
        "variables": "",
    },
    {
        "sequence": "S13", "num": 2, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Patron d'un solide",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"Qu'est-ce que le \textbf{patron} d'un solide?",
        "verso": r"Une figure plane qui, une fois pliée, forme le solide.",
        "variables": "",
    },
    {
        "sequence": "S13", "num": 3, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Section plane",
        "lien_type": "notion", "lien_num": "03",
        "recto": r"Qu'est-ce que la \textbf{section plane} d'un solide?",
        "verso": r"La figure obtenue en coupant le solide par un plan.",
        "variables": "",
    },
    {
        "sequence": "S13", "num": 4, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "Faces d'un pavé droit",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Combien de faces, arêtes et sommets a un \textbf{pavé "
                 r"droit}?",
        "verso": r"$6$ faces, $12$ arêtes, $8$ sommets.",
        "variables": "",
    },
    {
        "sequence": "S13", "num": 5, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "Perspective cavalière",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"En perspective cavalière, comment sont dessinées les "
                 r"arêtes cachées?",
        "verso": r"En \textbf{pointillés}.",
        "variables": "",
    },
    {
        "sequence": "S13", "num": 6, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "Section d'un cylindre",
        "lien_type": "methode", "lien_num": "3",
        "recto": r"Quelle est la section d'un \textbf{cylindre} par un plan "
                 r"parallèle à sa base?",
        "verso": r"Un \textbf{disque} (identique à la base).",
        "variables": "",
    },

    # ══════════════════════ S14 — Algorithmique (Scratch) ════════════════════
    {
        "sequence": "S14", "num": 1, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Définition variable",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"En programmation, qu'est-ce qu'une \textbf{variable}?",
        "verso": r"Un objet nommé qui permet de \textbf{stocker} une "
                 r"information (que l'on peut lire et modifier).",
        "variables": "",
    },
    {
        "sequence": "S14", "num": 2, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Définition événement",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"En programmation, qu'est-ce qu'un \textbf{événement}?",
        "verso": r"Quelque chose qui \textbf{déclenche} une action "
                 r"(clic, touche, message…).",
        "variables": "",
    },
    {
        "sequence": "S14", "num": 3, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Boucle",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"À quoi sert une \textbf{boucle} dans un programme?",
        "verso": r"À \textbf{répéter} une ou plusieurs instructions.",
        "variables": "",
    },
    {
        "sequence": "S14", "num": 4, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Instruction conditionnelle",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"À quoi sert une instruction \textbf{« si … alors »}?",
        "verso": r"À exécuter une action \textbf{seulement si} une "
                 r"condition est vraie.",
        "variables": "",
    },
    {
        "sequence": "S14", "num": 5, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "Angles Scratch",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Dans Scratch, de combien de degrés tourner pour faire un "
                 r"carré?",
        "verso": r"$90^\circ$ à chaque coin (angle extérieur).",
        "variables": "",
    },
    {
        "sequence": "S14", "num": 6, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Répétitions d'une boucle",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Une boucle « répéter $\xinttheiiexpr N11S14C06_n\relax$ » "
                 r"contient $\xinttheiiexpr N11S14C06_k\relax$ instructions. "
                 r"Combien d'instructions exécutées en tout?",
        "verso": r"$\xinttheiiexpr N11S14C06_p\relax$",
        "variables": r"\xintdefiivar N11S14C06_n := randrange(3,10);"
                     "\n\\xintdefiivar N11S14C06_k := randrange(2,5);"
                     "\n\\xintdefiivar N11S14C06_p := N11S14C06_n*N11S14C06_k;",
    },
]
