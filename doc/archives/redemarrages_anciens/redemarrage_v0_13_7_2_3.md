# Redémarrage v0.13.7.2.3 — Hotfix : détection des compteurs dans la fermeture transitive

## Périmètre

**Deuxième hotfix** sur la chaîne d'import du paquet, sur le même fil
QCM que v0.13.7.2.2.

Une fois v0.13.7.2.2 déployée et le paquet réimporté, la clé
`explication` du `seqQcm` est bien définie dans le préambule régénéré.
Mais une nouvelle erreur apparaît à la compilation :

```
! LaTeX Error: No counter 'seq@qcm@alphcode' defined.
```

L'analyse révèle un **autre angle mort** du parseur : il ne détectait
pas les compteurs LaTeX référencés par leur **nom textuel** (sans
backslash). Comme pour v0.13.7.2.2, c'est un cas particulier des
primitives LaTeX manipulables qui n'avait pas de traitement dédié.

## Diagnostic

Le `seqQcm` fait dans son corps :

```latex
\setcounter{seq@qcm@alphcode}{40}
\forloop{seq@qcm@iter}{0}{\value{seq@qcm@iter} < \cmdseq@seqQcm@nbReps}
{\stepcounter{seq@qcm@alphcode} ...}
```

Les compteurs `seq@qcm@alphcode` et `seq@qcm@iter` sont **bien indexés
en BdD** comme `type_latex='counter'` (via `\newcounter` dans
`seqenseigne-core.sty`).

**Mais** `seqQcm.macros_appelees` ne les contenait pas. La fonction
`analyser_corps` cherchait des macros au pattern `\macroname` (avec
backslash). Les compteurs passés en argument à `\setcounter`,
`\stepcounter`, `\value`, `\forloop` sont des **noms sans backslash**
et passaient sous le radar.

Résultat : la fermeture transitive ne trouvait pas ces compteurs comme
dépendances, ne les incluait pas dans le préambule, et à la
compilation `\setcounter{seq@qcm@alphcode}{40}` échouait avec
« No counter defined ».

### Pourquoi `\theseq@qcm@alphcode` était bien détecté

Le pattern `\macroname` détecte bien `\theseq@qcm@alphcode` (auto-générée
par `\newcounter`). Cette macro **fait partie** des `macros_appelees`,
mais elle n'est **pas** dans la table `paquet_definitions` en tant
qu'entrée indépendante (les `\theXXX` ne sont pas indexées séparément
par `\newcounter`). Donc la fermeture transitive l'ignorait
silencieusement (comportement normal : macro non dans l'index → ignorée).

Le compteur sous-jacent `seq@qcm@alphcode`, lui, **est dans l'index**
mais n'était pas référencé via son nom textuel. C'est le maillon
manquant.

## Correctif

Dans `services/paquet_parseur.py`, fonction `analyser_corps()` : ajout
d'une regex qui détecte les primitives prenant un compteur en 1er
argument et qui stocke le nom du compteur (sans backslash) dans
`macros_appelees` :

```python
_RE_COMPTEURS = re.compile(
    r'\\(?:setcounter|stepcounter|refstepcounter|addtocounter|value'
    r'|forloop|arabic|roman|alph|Alph|Roman)\s*\{([^}]+)\}'
)
for m in _RE_COMPTEURS.finditer(corps_total):
    nom_compteur = m.group(1).strip()
    if nom_compteur:
        d.macros_appelees.add(nom_compteur)
```

### Choix de design : nom sans backslash dans `macros_appelees`

`macros_appelees` mélange désormais deux conventions :
- Les macros (`\setcounter`, `\seqFrac`, etc.) avec `\` initial
- Les compteurs (`seq@qcm@alphcode`, `flashcardnb`, etc.) **sans** `\`

C'est cohérent avec la manière dont les compteurs sont indexés dans
`paquet_definitions` (toujours sans backslash, parce que LaTeX les
manipule sous cette forme). Et c'est ce qui permet à la fermeture
transitive de fonctionner sans modification : `index.get('seq@qcm@alphcode')`
retourne directement le compteur indexé.

Renommer le champ en `dependances` (plus générique) serait plus
honnête sémantiquement, mais c'est un changement invasif qui touche
plusieurs services. Pour ce hotfix, on garde le nom et on documente
la dualité en commentaire.

### Faux positifs sur les compteurs LaTeX standard

Les compteurs LaTeX standard (`page`, `section`, `equation`, `footnote`,
`figure`, `table`, `chapter`, etc.) sont aussi détectés par la regex
quand ils apparaissent dans un `\setcounter{equation}{0}` ou similaire.
**Pas grave** : la fermeture transitive (`preambule_atome._fermeture_transitive`)
les ignore silencieusement parce qu'ils ne sont pas dans la table
`paquet_definitions`. Comportement attendu et documenté.

## Action requise après déploiement

**Re-importer le paquet** dans l'app. Sans cette étape, les
`macros_appelees` des définitions existantes ne sont pas mises à jour
(le re-parsing du paquet doit avoir lieu).

Une fois réimporté, vérifie via une requête SQL que les compteurs
sont bien référencés :

```sql
SELECT macros_appelees FROM paquet_definitions WHERE nom = 'seqQcm';
-- Doit maintenant inclure : "seq@qcm@alphcode", "seq@qcm@iter"
```

Et la compilation de l'exercice avec QCM doit passer.

## Fichiers livrés

```
MODIFIÉS (cumule v0.13.7.2.2 + v0.13.7.2.3)
appli/services/paquet_parseur.py             (parseur + analyser_corps)
appli/tests/test_paquet_parseur.py           (+10 tests pour les compteurs)
appli/doc/redemarrage_v0_13_7_2_3.md         (NEW)
```

Le `paquet_parseur.py` livré cumule les deux fixes :
- v0.13.7.2.2 : reconnaissance de `\define@choicekey`
- v0.13.7.2.3 : détection des compteurs par nom textuel

Si tu n'as pas encore déployé v0.13.7.2.2, déploie directement cette
livraison v0.13.7.2.3 — elle contient les deux fixes.

## Vérifications

- Suite pytest : **3267 passed, 5 skipped, 0 failed** (3257 baseline
  v0.13.7.2.2 + 10 nouveaux tests pour la détection des compteurs)
- Test unitaire sur le snippet réel de `seqQcm` : les deux compteurs
  `seq@qcm@alphcode` et `seq@qcm@iter` sont désormais détectés

## À tester chez toi

### Scénario A — Recompilation de l'exercice avec QCM

1. **Re-importer le paquet** dans l'app.
2. Vérifier la BdD :
   ```sql
   SELECT macros_appelees FROM paquet_definitions WHERE nom = 'seqQcm';
   ```
   La sortie doit maintenant inclure `seq@qcm@alphcode` et
   `seq@qcm@iter`.
3. Compiler l'exercice avec QCM.
4. **Doit maintenant passer** sans erreur (ni clé `explication`, ni
   compteur manquant).

### Scénario B — Effet cumulatif : autres définitions corrigées

Le fix ne profite pas qu'au QCM. Les définitions qui utilisaient des
compteurs locaux par leur nom textuel bénéficient toutes du nouveau
parseur. Pour en avoir une liste :

```sql
SELECT nom, fichier_source
FROM paquet_definitions
WHERE type_latex='counter';
-- Liste les 5 compteurs locaux : flashcardnb, seq@qcm@alphcode,
-- seq@qcm@iter, seq@tmp@i, seqBilanExoNum
```

Pour chacun, repère quelles définitions le référencent :

```sql
SELECT nom FROM paquet_definitions
WHERE macros_appelees LIKE '%"flashcardnb"%';
```

Les corrections deviennent visibles uniquement pour des atomes qui
utilisaient ces définitions et compilaient « par chance » (ou ne
compilaient pas).

### Scénario C — Pas de régression sur les exercices déjà OK

1. Reprendre un exercice standard qui compilait déjà.
2. Recompiler.
3. **Vérifier** : compilation identique à avant.

## Note pour la suite

Ces deux hotfixes (v0.13.7.2.2 + v0.13.7.2.3) ont mis en lumière une
**faiblesse structurelle** du parseur : il fonctionne par cas
particuliers ajoutés au fil des bugs découverts. À chaque nouvelle
primitive LaTeX rencontrée dans le paquet, il faut potentiellement
ajouter une règle.

Pour l'instant, cette dette est tolérable :
- Le paquet seqenseigne évolue peu en termes de primitives utilisées
- Les bugs se manifestent dès la compilation, donc on les voit vite

Si on devait élargir massivement le paquet, il faudrait envisager
un parseur plus systématique (en s'appuyant sur LuaLaTeX ou en
écrivant un mini-interpréteur xkeyval). Pas pour aujourd'hui.

## Reprise du chantier v0.13.7.3

Sitôt ce 2e hotfix validé, on reprend v0.13.7.3 (wrapping de sélection
avec `•`, commandes additionnelles, générateurs QCM et liste). Les
décisions de cadrage sont prises, le code n'attend que la reprise.
