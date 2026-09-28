# Redémarrage — atelier séquence-dans-niveau

## Où on en est

### Récap exos : terminé ✅

L'atelier Récap exos compile pour les trois niveaux N10, N11, N12. Validation
visuelle OK sur N10 (193 pages, structure conforme aux livrets normaux,
variables xint évaluées correctement dans énoncés et corrigés, `\touche` et
autres macros utilisateur fonctionnelles partout).

**Dernière livraison** : `/mnt/user-data/outputs/xintguard/services/livret_recap_exos.py`

### Coquilles cosmétiques connues, en attente

1. **Numérotation `5.2` à `5.15` des subsections de corrigés** — héritée de la
   continuation du compteur de section depuis « Algorithmique et programmation ».
   À résoudre soit en remettant le compteur à zéro avant `\section*{Corrigés}`,
   soit en passant la section Corrigés en numérotée.
2. **Entête de page « Algorithmique et programmation »** sur la première page
   des corrigés — héritée de la dernière section vue. Probablement résolu en
   même temps que (1).
3. **« Livret déxercices »** sur la page de garde — déjà corrigé dans le code
   (utilisation de guillemets doubles autour de l'apostrophe pour éviter
   l'interprétation babel comme accent aigu).

### Mécanismes de génération de livrets agrégés (à réutiliser pour la suite)

Trois patterns techniques ont été établis sur récap exos. Ils s'appliqueront
aussi aux autres ateliers de génération de docs.

1. **`\xintglobaldefstrue` conditionnel en tête de livret**
   ```latex
   \ifcsname xintglobaldefstrue\endcsname\xintglobaldefstrue\fi
   ```
   Active le drapeau xint qui rend toutes les définitions `\xintdefiivar`
   globales. Conditionnel parce que xint n'est pas chargé dans tous les
   livrets (cas N12 sans aucune variable xint).

2. **`\let\newcommand=\providecommand`**
   En tête de livret. Rend les `\newcommand` idempotents pour gérer le cas
   où un même `\X` est défini dans `variables` de plusieurs exos
   (`\tkzFExoI`, `\tkzMyHomFig`, `\cerclePlein`, `\denomTexte`...).
   Convention : « même nom = même sémantique attendue », donc redéfinitions
   silencieuses sans danger.

3. **Émission des blocs `variables` au niveau séquence (top level)**
   Pas à l'intérieur des `seqSerieExos` qui ouvrent des groupes
   (multicols × boitePale). Les définitions LaTeX y seraient locales et
   disparaîtraient à `\end{seqSerieExos}`, ce qui ferait planter
   `\seqAfficheCorriges` qui lit les `Corriges/cNeM.tex` en fin de livret.
   On dédoublonne au passage les blocs identiques entre exos d'une même
   séquence (économie : 28 émissions × 1 bloc identique → 1 seule en N11/S03).

## Roadmap rappelée

1. ✅ Atelier Récap exos
2. ⏭️ **Atelier d'assemblage d'une séquence-dans-niveau** ← prochaine étape
3. ⏭️ Atelier des plans de travail (dépend de 2)
4. ⏭️ Atelier des référentiels millésimés (les tables `referentiel_*`
   entrent en service à cette étape, pas avant)
5. ⏭️ Reprise du suivi des classes / progressions annuelles

## Atelier séquence-dans-niveau — ce qu'on a établi

### Distinction séquence-cycle vs séquence-niveau

- **séquence-cycle** (portée Cycle) : la séquence indépendamment d'un niveau.
  Métadonnées partagées entre les trois niveaux du cycle 4 — nom, code, thème,
  couleur, ordre, description. Source : table `sequences_du_cycle`.

- **séquence-niveau** (portée Séquence) : la déclinaison d'une séquence pour
  un niveau donné. Contient les notions, méthodes, exercices, paramètres
  spécifiques à ce niveau. Tables : `sequences_par_niveau`, plus tous les
  atomes (`exercices`, `notions`, `methodes`).

Le livret papier classique `NXX_SXX_Livret.tex` est par nature un objet
séquence-niveau : *cette* séquence dans *ce* niveau précis.

### Questions ouvertes pour démarrer (à reposer en début de prochaine session)

1. **État actuel de l'atelier** dans l'appli : déjà existant et à faire
   évoluer, coquille vide à implémenter, ou à créer de zéro ?
2. **Livrable principal** : un livret de séquence type `NXX_SXX_Livret.tex`
   (notions + méthodes + exos), un assemblage configurable où l'utilisateur
   choisit ce qu'il inclut, ou autre chose ?
3. **Articulation avec l'atelier séquence-cycle** : qui produit quoi, qui
   contient quoi ?

### Pistes à explorer une fois ces questions tranchées

- Si livret type `NXX_SXX_Livret.tex` : très probablement on s'inspire de
  l'atelier Récap exos (orchestration des atomes, dédup variables, etc.)
  mais avec une portée plus restreinte (1 séquence × 1 niveau au lieu de
  toutes les séquences d'un niveau).
- Quelle granularité pour la sélection des atomes inclus ? Tous par défaut ?
  Choisir notion par notion, méthode par méthode, exos par série ?
- Faut-il un mécanisme de prérequis (cf. clé `prerequis` du JSON
  `livrets_de_sequence` qu'on a aperçu — révision d'exos d'un niveau
  inférieur) ?

## Pratiques de travail (rappel)

- Localisation BDD courante : `/mnt/user-data/uploads/seqenseigne.db`
  (à recopier vers `/tmp/seqenseigne_new.db` pour permission RW).
- Repo : `/home/claude/appli/appli/` (services, routes, static, templates,
  tests). Suite de tests : `pytest tests/` (1434 tests, ~2 min).
- Pour livrer un fichier : copier dans `/mnt/user-data/outputs/<nom_dossier>/`
  en respectant l'arborescence `services/`, `routes/`, etc.
- Quand un log de compilation arrive : `grep -n "^!\|! LaTeX Error\|!
  Undefined" log` pour trouver la ligne d'erreur, puis `view` ±15 lignes
  autour.

## Mémoire à jour

Les 7 entrées de mémoire utilisateur reflètent l'état actuel. Pas besoin de
les remettre à jour à l'ouverture de la prochaine session.
