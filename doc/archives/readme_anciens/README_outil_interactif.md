# seqenseigne — Outil interactif de résolution des liaisons `a_completer`

Script `peuplement_06_resoudre_liaisons_interactif.py` pour traiter
rapidement les 117 entrées `a_completer: true` restantes dans
`config/liaisons_objectifs.yaml`.

## Installation

Un seul fichier à déposer dans `appli/scripts/`.

## Utilisation

```powershell
cd D:\Enseignement\seqenseigne\appli
..\outils\python\python.exe scripts\peuplement_06_resoudre_liaisons_interactif.py
```

Pour chaque objectif `a_completer`, l'outil affiche les 5 meilleurs
candidats au niveau N-1 avec leur similarité (0.00 à 1.00) et un marqueur
`◆` pour ceux de la même séquence.

## Touches

| Touche | Action |
|---|---|
| `a` à `e` | choisir le candidat correspondant (pose `precedent:`) |
| `n` | marquer l'objectif comme nouveau (`est_nouveau: true`) |
| `s` | passer sans décider (reste `a_completer`) |
| `m` | saisir manuellement un précédent (niveau/séquence/code) |
| `?` | afficher l'aide |
| `q` | sauvegarder et quitter |

Le YAML est **sauvegardé après chaque décision**. Tu peux interrompre à
tout moment (`q` ou Ctrl-C) et reprendre plus tard : l'outil filtre les
entrées déjà résolues et reprend aux `a_completer` restants.

## Workflow recommandé

1. Lancer l'outil, traiter ~20-30 entrées, `q` pour sauvegarder
2. Faire une pause (pas besoin de tout faire d'un coup)
3. Relancer, continuer là où on s'est arrêté
4. Quand tout est fait (0 `a_completer` restants), lancer :
   ```powershell
   ..\outils\python\python.exe scripts\peuplement_04_appliquer_liaisons.py
   ```

## Affichage

Chaque entrée ressemble à ceci :

```
══════════════════════════════════════════════════════════════════════════════
[42/117]  N11.S03.05
  Calculer une fraction d'un nombre

  Candidats en N10 (triés par similarité):
    [a] ◆ N10.S03.04     0.98  Calculer une fraction d'un entier
    [b] ◆ N10.S03.05     0.67  Simplifier une fraction
    [c]   N10.S01.02     0.32  Additionner des décimaux
    ◆ = même séquence

  [a-e] choisir un candidat     [n] marquer nouveau     [s] skip
  [m] saisir manuellement       [?] aide               [q] sauvegarder et quitter
  >
```

Similarités code couleur :
- **vert** : ≥ 0.85 (très proche, probablement le bon)
- **jaune** : 0.60 à 0.85 (à examiner)
- **gris** : < 0.60 (probablement sans rapport)

## Notes

- Les candidats sont **classés par similarité de libellé** avec un bonus
  de +0.10 pour les candidats de la même séquence que l'objectif
  courant.
- Même si un candidat à 1.00 est proposé, c'est à toi de valider :
  par exemple "Simplifier une fraction" peut exister en N10 et N11 avec
  des contextes différents (entiers vs rationnels).
- `m` (saisie manuelle) accepte un niveau/séquence/code qui n'existe
  pas en base ; un warning s'affiche alors et le script 04 signalera
  la liaison absente.
