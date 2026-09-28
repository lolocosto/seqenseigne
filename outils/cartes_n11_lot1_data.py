# -*- coding: utf-8 -*-
"""Données des cartes d'automatisme 4e — LOT 1 : S01, S02, S03.

Chaque carte : dict avec sequence, num, type_pedago (definition|procedure|
calcul|propriete|reconnaissance), type_tech (fixe|parametree), titre, recto,
verso, variables (paramétrées), lien_type/lien_num (notion|methode + numéro
source, résolu en id par le script d'insertion).

Format LaTeX aligné sur les cartes 5e validées :
  - \\seqFrac{a}{b} pour les fractions,
  - variables paramétrées : \\xintdefiivar N11S<seq>C<num>_<suf> := ...,
    affichage \\xinttheiiexpr ...\\relax.
  - Les noms de variables sont préfixés N11S<seq>C<num>_ pour éviter toute
    collision entre cartes.
"""

CARTES = [

    # ══════════════════════ S01 — Puissances, racine carrée ══════════════════
    # Cible ~12 cartes (3 semaines × 4).
    {
        "sequence": "S01", "num": 1, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Définition puissance",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Que signifie $a^n$ (avec $n$ entier $\geq 1$)?",
        "verso": r"Le produit de $n$ facteurs tous égaux à $a$ :"
                 r"\smallskip\par $a^n = \underbrace{a \times a \times \cdots "
                 r"\times a}_{n \text{ facteurs}}$",
        "variables": "",
    },
    {
        "sequence": "S01", "num": 2, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Vocabulaire puissance",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Dans $a^n$, comment s'appellent $a$ et $n$?",
        "verso": r"$a$ est la \textbf{base}, $n$ est l'\textbf{exposant}.",
        "variables": "",
    },
    {
        "sequence": "S01", "num": 3, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Carré d'un entier",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Combien vaut $\xinttheiiexpr N11S01C03_a\relax^2$?",
        "verso": r"$\xinttheiiexpr N11S01C03_c\relax$",
        "variables": r"\xintdefiivar N11S01C03_a := randrange(2,13);"
                     "\n\\xintdefiivar N11S01C03_c := N11S01C03_a^2;",
    },
    {
        "sequence": "S01", "num": 4, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Cube d'un entier",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Combien vaut $\xinttheiiexpr N11S01C04_a\relax^3$?",
        "verso": r"$\xinttheiiexpr N11S01C04_c\relax$",
        "variables": r"\xintdefiivar N11S01C04_a := randrange(2,8);"
                     "\n\\xintdefiivar N11S01C04_c := N11S01C04_a^3;",
    },
    {
        "sequence": "S01", "num": 5, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Puissance de 10 positive",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"À quoi est égal $10^n$ (pour $n$ entier $> 0$)?",
        "verso": r"Le chiffre $1$ suivi de $n$ zéros."
                 r"\smallskip\par Ex. $10^4 = 10\,000$.",
        "variables": "",
    },
    {
        "sequence": "S01", "num": 6, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Puissance de 10 négative",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"À quoi est égal $10^{-n}$ (pour $n$ entier $> 0$)?",
        "verso": r"Le chiffre $0,0\ldots01$ avec $n$ zéros en tout. "
                 r"$10^{-n}$ est l'inverse de $10^{n}$.\smallskip\par "
                 r"Ex. $10^{-3} = \seqFrac{1}{1000} = 0{,}001$.",
        "variables": "",
    },
    {
        "sequence": "S01", "num": 7, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Écrire une puissance de 10",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Écris $10^{\xinttheiiexpr N11S01C07_n\relax}$ "
                 r"en écriture décimale.",
        "verso": r"$\xinttheiiexpr N11S01C07_v\relax$",
        "variables": r"\xintdefiivar N11S01C07_n := randrange(2,7);"
                     "\n\\xintdefiivar N11S01C07_v := 10^N11S01C07_n;",
    },
    {
        "sequence": "S01", "num": 8, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Écriture scientifique",
        "lien_type": "notion", "lien_num": "03",
        "recto": r"Quelle est la forme d'une \textbf{écriture scientifique}?",
        "verso": r"$a = p \times 10^n$ où $1 \leq p < 10$ "
                 r"($p$ : mantisse, $n$ : entier relatif).",
        "variables": "",
    },
    {
        "sequence": "S01", "num": 9, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "Mantisse valide?",
        "lien_type": "notion", "lien_num": "03",
        "recto": r"Parmi $0{,}7 \times 10^5$ et $7 \times 10^4$, "
                 r"laquelle est une écriture scientifique?",
        "verso": r"$7 \times 10^4$ (la mantisse doit vérifier "
                 r"$1 \leq p < 10$).",
        "variables": "",
    },
    {
        "sequence": "S01", "num": 10, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Définition racine carrée",
        "lien_type": "notion", "lien_num": "05",
        "recto": r"Qu'est-ce que la \textbf{racine carrée} de $a$ "
                 r"(avec $a \geq 0$)?",
        "verso": r"Le nombre \textbf{positif} $b$ tel que $b^2 = a$."
                 r"\smallskip\par On la note $\sqrt{a}$.",
        "variables": "",
    },
    {
        "sequence": "S01", "num": 11, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Racine d'un carré parfait",
        "lien_type": "methode", "lien_num": "4",
        "recto": r"Combien vaut $\sqrt{\xinttheiiexpr N11S01C11_c\relax}$?",
        "verso": r"$\xinttheiiexpr N11S01C11_a\relax$",
        "variables": r"\xintdefiivar N11S01C11_a := randrange(2,13);"
                     "\n\\xintdefiivar N11S01C11_c := N11S01C11_a^2;",
    },
    {
        "sequence": "S01", "num": 12, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Carrés parfaits",
        "lien_type": "notion", "lien_num": "06",
        "recto": r"Qu'est-ce qu'un \textbf{carré parfait}?",
        "verso": r"Un nombre dont la racine carrée est un entier."
                 r"\smallskip\par Les carrés parfait de 1 à 12 sont : "
                 r"$1, 4, 9, 16, 25, 36, 49, 64, 81, 100, 121, 144$.",
        "variables": "",
    },

    # ══════════════════════ S02 — Ordre, comparaison ═════════════════════════
    # Cible ~4 cartes (0,5 semaine, plancher 4).
    {
        "sequence": "S02", "num": 1, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Comparer deux fractions",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Comment comparer deux fractions?",
        "verso": r"\begin{seqColEnum}[nbCols=1]"
                 r"\item Les mettre au \textbf{même dénominateur}."
                 r"\item Comparer alors les \textbf{numérateurs}."
                 r"\end{seqColEnum}",
        "variables": "",
    },
    {
        "sequence": "S02", "num": 2, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Ordre des puissances de 10",
        "lien_type": "notion", "lien_num": "03",
        "recto": r"Compare $10^n$ et $10^{n+1}$ (pour $n$ entier).",
        "verso": r"$10^n < 10^{n+1}$ : plus l'exposant augmente, "
                 r"plus la puissance de 10 est grande.",
        "variables": "",
    },
    {
        "sequence": "S02", "num": 3, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Encadrer une racine",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Entre quels deux entiers consécutifs se trouve "
                 r"$\sqrt{\xinttheiiexpr N11S02C03_n\relax}$?",
        "verso": r"$\xinttheiiexpr N11S02C03_a\relax < "
                 r"\sqrt{\xinttheiiexpr N11S02C03_n\relax} < "
                 r"\xinttheiiexpr N11S02C03_b\relax$",
        "variables": r"\xintdefiivar N11S02C03_a := randrange(2,11);"
                     "\n\\xintdefiivar N11S02C03_b := N11S02C03_a + 1;"
                     "\n\\xintdefiivar N11S02C03_n := N11S02C03_a^2 + "
                     "randrange(1, 2*N11S02C03_a);",
    },
    {
        "sequence": "S02", "num": 4, "type_pedago": "reconnaissance",
        "type_tech": "fixe", "titre": "Ordre de grandeur",
        "lien_type": "notion", "lien_num": "04",
        "recto": r"Quel est l'ordre de grandeur de la taille d'un atome?",
        "verso": r"Environ $10^{-10}$ m.",
        "variables": "",
    },

    # ══════════════════════ S03 — Inverse, calcul fractionnaire ══════════════
    # Cible ~8 cartes (2 semaines × 4).
    {
        "sequence": "S03", "num": 1, "type_pedago": "definition",
        "type_tech": "fixe", "titre": "Définition inverse",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Qu'est-ce que l'\textbf{inverse} d'un nombre $a$ non nul?",
        "verso": r"Le nombre $b$ tel que $a \times b = 1$."
                 r"\smallskip\par On le note $\seqFrac{1}{a}$.",
        "variables": "",
    },
    {
        "sequence": "S03", "num": 2, "type_pedago": "propriete",
        "type_tech": "fixe", "titre": "Inverse d'une fraction",
        "lien_type": "notion", "lien_num": "02",
        "recto": r"Quel est l'inverse de $\seqFrac{a}{b}$ "
                 r"(avec $a \neq 0$, $b \neq 0$)?",
        "verso": r"$\seqFrac{b}{a}$ (on échange numérateur et dénominateur).",
        "variables": "",
    },
    {
        "sequence": "S03", "num": 3, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Inverse d'un entier",
        "lien_type": "notion", "lien_num": "01",
        "recto": r"Quel est l'inverse de $\xinttheiiexpr N11S03C03_a\relax$?",
        "verso": r"$\seqFrac{1}{\xinttheiiexpr N11S03C03_a\relax}$",
        "variables": r"\xintdefiivar N11S03C03_a := randrange(2,12);",
    },
    {
        "sequence": "S03", "num": 4, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Produit de fractions",
        "lien_type": "methode", "lien_num": "3",
        "recto": r"Calcule $\seqFrac{\xinttheiiexpr N11S03C04_a\relax}"
                 r"{\xinttheiiexpr N11S03C04_b\relax} \times "
                 r"\seqFrac{\xinttheiiexpr N11S03C04_c\relax}"
                 r"{\xinttheiiexpr N11S03C04_d\relax}$ "
                 r"(sans simplifier).",
        "verso": r"$\seqFrac{\xinttheiiexpr N11S03C04_num\relax}"
                 r"{\xinttheiiexpr N11S03C04_den\relax}$",
        "variables": r"\xintdefiivar N11S03C04_a := randrange(1,7);"
                     "\n\\xintdefiivar N11S03C04_b := randrange(2,7);"
                     "\n\\xintdefiivar N11S03C04_c := randrange(1,7);"
                     "\n\\xintdefiivar N11S03C04_d := randrange(2,7);"
                     "\n\\xintdefiivar N11S03C04_num := N11S03C04_a*N11S03C04_c;"
                     "\n\\xintdefiivar N11S03C04_den := N11S03C04_b*N11S03C04_d;",
    },
    {
        "sequence": "S03", "num": 5, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Diviser par une fraction",
        "lien_type": "methode", "lien_num": "3",
        "recto": r"Comment diviser par une fraction?",
        "verso": r"On multiplie par son \textbf{inverse} :"
                 r"\smallskip\par "
                 r"$\seqFrac{a}{b} \div \seqFrac{c}{d} = "
                 r"\seqFrac{a}{b} \times \seqFrac{d}{c}$.",
        "variables": "",
    },
    {
        "sequence": "S03", "num": 6, "type_pedago": "procedure",
        "type_tech": "fixe", "titre": "Additionner deux fractions",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Comment additionner deux fractions?",
        "verso": r"\begin{seqColEnum}[nbCols=1]"
                 r"\item Les mettre au \textbf{même dénominateur}."
                 r"\item \textbf{Additionner les numérateurs}, "
                 r"garder le dénominateur commun."
                 r"\end{seqColEnum}",
        "variables": "",
    },
    {
        "sequence": "S03", "num": 7, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Somme de fractions même dénom.",
        "lien_type": "methode", "lien_num": "2",
        "recto": r"Calcule $\seqFrac{\xinttheiiexpr N11S03C07_a\relax}"
                 r"{\xinttheiiexpr N11S03C07_d\relax} + "
                 r"\seqFrac{\xinttheiiexpr N11S03C07_b\relax}"
                 r"{\xinttheiiexpr N11S03C07_d\relax}$.",
        "verso": r"$\seqFrac{\xinttheiiexpr N11S03C07_s\relax}"
                 r"{\xinttheiiexpr N11S03C07_d\relax}$",
        "variables": r"\xintdefiivar N11S03C07_a := randrange(1,8);"
                     "\n\\xintdefiivar N11S03C07_b := randrange(1,8);"
                     "\n\\xintdefiivar N11S03C07_d := randrange(3,12);"
                     "\n\\xintdefiivar N11S03C07_s := N11S03C07_a+N11S03C07_b;",
    },
    {
        "sequence": "S03", "num": 8, "type_pedago": "calcul",
        "type_tech": "parametree", "titre": "Produit de décimaux",
        "lien_type": "methode", "lien_num": "1",
        "recto": r"Calcule $\xinttheiiexpr N11S03C08_a\relax "
                 r"\times \xinttheiiexpr N11S03C08_b\relax$.",
        "verso": r"$\xinttheiiexpr N11S03C08_p\relax$",
        "variables": r"\xintdefiivar N11S03C08_a := randrange(11,99);"
                     "\n\\xintdefiivar N11S03C08_b := randrange(2,9);"
                     "\n\\xintdefiivar N11S03C08_p := N11S03C08_a*N11S03C08_b;",
    },
]
