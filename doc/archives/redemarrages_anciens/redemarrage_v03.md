# Redémarrage — projet seqenseigne v0.3
_Préparé le 13 avril 2026_

---

## Contexte général

Laurent Coste, enseignant collège (cycle 4).
Niveaux : N09=6ème, N10=5ème, N11=4ème, N12=3ème (14 séquences chacun).
Paquet LaTeX custom `seqenseigne` + application Flask de conception pédagogique.
Dépôt : `forge.apps.education.fr/laurentcoste/seqenseigne`
Environnement : clé USB MiKTeX portable x64 (MiKTeX 26.2), Python portable, Windows, `lancer.bat`.
Structure : `F:\Enseignement\seqenseigne\` avec `appli\`, `reference\`, `outils\`.

---

## Ce qui a été résolu dans cette session

### Paquet LaTeX — bugs datatool v3

Deux bugs liés à la migration datatool v2 → v3 ont été diagnostiqués et corrigés
par des tests minimaux ciblés avant toute modification du paquet :

**Bug 1 — `seq@bases@filter@cycle` (connaissances et objectifs annuels)**
Symptôme : toutes les séquences affichaient les données de la première séquence
dans les tableaux récapitulatifs des documents annuels.
Cause : `\DTLifstringeq` ne fonctionne pas dans ce contexte en datatool v3.
Fix : remplacement par `\ifthenelse{\equal{...}{...}}` avec `\dtlexpandnewvalue`
déplacé dans chaque branche.
Fichier : `seqenseigne-data.dtx`

**Bug 2 — `seq@prerequis@annee` (liste des prérequis dans les livrets)**
Symptôme : `missing \item` dans `\seqTableauPrerequis` pour N11/N12 — la liste
de prérequis était vide alors qu'elle ne devrait pas l'être.
Cause : `\DTLifeq{\DTLrowcount{base}}{0}` retourne toujours FAUX en datatool v3
quand `\DTLrowcount` n'est pas pré-expandé.
Fix : `\edef\seq@tmp@rowcount{\DTLrowcount{base}}` avant chaque `\DTLifeq`.
Fichier : `seqenseigne-data.dtx`

**Méthode de diagnostic utilisée** : tests `.tex` minimaux autonomes compilables
sur le poste avant toute modification du paquet. À conserver comme méthode de
référence pour les bugs datatool futurs.

### Compilation N11 et N12

Tous les livrets de séquence N11 compilent. Tous les documents annuels N11
compilent. N12 : à vérifier en début de prochaine session.

### Corrigés N11

16 exercices sans corrigé identifiés et corrigés produits :
N11S01E10, N11S01E11, N11S04A06, N11S04E05, N11S07A04, N11S07E01,
N11S07E02, N11S08E09, N11S10A02, N11S10A05, N11S10E03, N11S11E01,
N11S11E07, N11S12A09, N11S13E01, N11S13E02.
Fichier livré : `corriges_N11.tex` (contenu des `\seqCorrige{...}` à intégrer).
Points de vigilance :
- N11S07A04 : "tirer le nom d'une femme" (pas "tirer une femme")
- N11S07E01 : corrigé réécrit par Laurent (2 configurations valides subsistent)

### Application Flask

**Scanner LaTeX → BdD** (`scanner_latex.py`) :
- Parse notions, méthodes, exercices, livrets depuis les .tex existants
- Détecte les atomes nouveaux vs déjà en base (par nom de fichier)
- Routes Flask : `GET /api/scanner/apercu`, `GET /api/scanner/detail`,
  `POST /api/scanner/lancer`
- Interface UI dans l'onglet Administration → Importer des fichiers .tex
- Testé sur N11 : 78 notions, 57 méthodes, 281 exercices, 14 livrets, 0 erreur

**Corrections app.py** :
- `sys.path.insert(0, str(Path(__file__).parent))` pour Python portable
- `if __name__ == "__main__"` déplacé en dernière position (ligne ~1214)
- Route `/api/scanner/detail` ajoutée

**Documentation scratch3** : la doc complète du paquet scratch3 v0.19 a été
fournie et lue. Toutes les macros scratch à utiliser dans les corrigés doivent
être conformes à cette doc. Macros valides retenues :
`\blockmove`, `\blocklook`, `\blocksound`, `\blockpen`, `\blockvariable`,
`\blocklist`, `\blockevent`, `\blockcontrol`, `\blocksensing`, `\blockmoreblocks`,
`\blockinit`, `\blockinitclone`, `\blockstop`, `\blockrepeat{}{corps}`,
`\blockinfloop{}{corps}`, `\blockif{}{corps}`, `\blockifelse{}{vrai}{faux}`,
`\ovalnum{}`, `\oval<suffixe>{}`, `\oval<suffixe>*{}`, `\booloperator`,
`\boolsensing`, `\boollist`, `\boolempty`, `\selectmenu{}`, `\greenflag`,
`\turnleft{}`, `\turnright{}`, `\pencolor{}`, `\ovalvariable{}`, `\blockspace`.

---

## État des fichiers à déployer

Tous les fichiers listés ci-dessous sont dans les outputs de la session précédente
et doivent être copiés aux emplacements indiqués :

| Fichier | Destination |
|---------|-------------|
| `seqenseigne-data.dtx` | `reference\paquet\` puis `make install` |
| `scanner_latex.py` | `appli\` |
| `app.py` | `appli\` |
| `index.html` | `appli\templates\` |
| `app.js` | `appli\static\` |
| `corriges_N11.tex` | À intégrer manuellement dans les .tex exercices |

---

## Points en suspens

### Paquet LaTeX
- [ ] Vérifier compilation complète N12 (livrets + documents annuels)
- [ ] N09 (6ème) : migration notions/méthodes non encore faite
- [ ] Script migration `\usepackage[geometrie]` dans les 17 livrets concernés
- [ ] Test et mesure des formats précompilés `.fmt`

### Application Flask
- [ ] Tester l'import effectif depuis l'UI (bouton "Importer" après scan)
- [ ] Vérifier le CSS badges admin (`badge-import`, `admin-atom-row`) dans `app.css`
- [ ] Atelier Progression annuelle (drag & drop calendrier)
- [ ] Migration CSV/JSON → SQLite
- [ ] Périodes d'évaluation S1/S2 + vue bulletin + export CSV
- [ ] Données N09
- [ ] Option compilation dyslexie : xeLaTeX + OpenDyslexic + A3 + LetterSpace=20
  + WordSpace=1.5 + baselinestretch=1.2 + unicode-math/latinmodern-math.otf
  (à commenter dans le .tex, activer à la demande)

### Contenu pédagogique
- [ ] Intégrer les 16 corrigés N11 dans les fichiers .tex exercices
- [ ] Vérifier N12 : exercices sans corrigé (même démarche que N11)

---

## Roadmap v0.3 → v0.4 (prochaine session)

Priorités suggérées :
1. Valider l'import complet N11 depuis l'UI (scan → résumé → import)
2. Vérifier N12
3. CSS badges admin si nécessaire
4. Premiers tests de l'atelier Exercice avec données importées
