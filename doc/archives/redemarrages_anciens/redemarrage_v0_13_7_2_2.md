# Redémarrage v0.13.7.2.2 — Hotfix parseur : `\define@choicekey`

## Périmètre

**Hotfix urgent** identifié pendant que je codais la v0.13.7.3 (wrapping
de sélection + générateurs QCM/liste). Tu as essayé de mettre un QCM
dans un exercice et la compilation échoue parce que la clé `explication`
de l'environnement `seqQcm` n'est pas définie au moment du
`\setkeys[seq]{seqQcm}{nbReps,explication,#1}` du préambule régénéré.

Cette livraison ne touche **que** au parseur du paquet. Elle est
**indépendante** du chantier v0.13.7.3 et peut être déployée
immédiatement. On reprend v0.13.7.3 juste après.

## Diagnostic

### Symptôme

Compilation d'un exercice contenant `\begin{seqQcm}` :

```
! Package xkeyval Error: `explication' undefined in families `seq@seqQcm'.
```

### Cause racine

Le parseur `services/paquet_parseur.py` connaissait `\define@cmdkey`
mais **pas** `\define@choicekey`. Or dans le `.dtx` du paquet, la clé
`explication` de `seqQcm` est définie par `\define@choicekey` (et pas
par `\define@cmdkey` comme les 4 autres clés `ptOK`, `ptPartiel`,
`ptKO`, `nbReps`) parce qu'elle a une liste de choix `{oui,non}`.

Résultat : à l'import du paquet, la directive `\define@choicekey` était
**silencieusement ignorée**, donc `\cmdseq@seqQcm@explication` n'était
pas indexée dans `paquet_definitions`. Au moment de générer le préambule
d'un atome contenant `seqQcm`, la fermeture transitive cherchait cette
macro (référencée dans `seqQcm.macros_appelees`) mais ne la trouvait
pas → directive absente du préambule → erreur xkeyval.

### Diagnostic confirmé par 3 indices

```sql
-- 1. La macro est référencée par seqQcm
SELECT macros_appelees FROM paquet_definitions WHERE nom='seqQcm';
-- ... '\cmdseq@seqQcm@explication', ...  ← présente

-- 2. Mais la macro elle-même n'est pas dans la table
SELECT * FROM paquet_definitions WHERE nom='\cmdseq@seqQcm@explication';
-- aucune ligne

-- 3. Et aucune définition n'a "define@choicekey" dans son texte_complet
SELECT COUNT(*) FROM paquet_definitions
  WHERE texte_complet LIKE '%define@choicekey%';
-- 0
```

## Correctif

Dans `services/paquet_parseur.py`, ajout d'un cas analogue au
traitement existant pour `\define@cmdkey`, juste après celui-ci :

```python
# Signature xkeyval :
#   \define@choicekey[<prefix>]{<famille>}{<cle>}[<store>]
#                     {<choix>}[<default>]{<action>}
# Signature pour _read_args : '[{{[{[{'
for m in re.finditer(r'\\define@choicekey\b', src_clean):
    debut = m.start()
    args, fin = _read_args(src_clean, m.end(), '[{{[{[{')
    prefix = (args[0] or '').strip()
    famille = (args[1] or '').strip()
    cle = (args[2] or '').strip()
    nom = (f'\\cmd{prefix}@{famille}@{cle}'
           if prefix else f'\\cmd{famille}@{cle}')
    defs.append(Definition(
        type_latex='cmdkey',
        nom=nom,
        ...
        texte_complet=src_clean[debut:fin],
        ...
    ))
```

### Choix de design : type_latex='cmdkey' (pas 'choicekey')

J'ai choisi de garder `type_latex='cmdkey'` pour les `\define@choicekey`
plutôt que de créer un nouveau type. Justifications :

1. **Côté LaTeX**, les deux types de clés se consomment de la même
   manière (`\setkeys[<prefix>]{<famille>}{<cle>=<val>}`). La distinction
   `cmdkey` vs `choicekey` est interne à `xkeyval`, pas visible côté
   appelant.

2. **Côté fermeture transitive** (`services/preambule_atome.py`), aucun
   traitement spécifique : la macro synthétique
   `\cmd<prefix>@<famille>@<cle>` est tirée via sa présence dans
   `macros_appelees` de l'environnement parent, peu importe son type.

3. **Côté filtrage UI** (`services/paquet_expose.py`), les types
   exposés sont `{command, environment, tcolorbox}`. `cmdkey` est déjà
   exclu (c'est de la plomberie). Pas besoin d'ajouter une 4e exclusion.

Si une distinction devenait nécessaire à l'avenir (ex. générateur de
documentation qui afficherait les valeurs autorisées des choicekey),
on créera alors un type `'choicekey'` dédié. Pas de premature optimization.

## Action requise après déploiement

**Re-importer le paquet** dans l'app, comme tu l'as fait avant de
constater le bug, mais cette fois avec le parseur corrigé. La table
`paquet_definitions` se peuplera correctement, avec
`\cmdseq@seqQcm@explication` ajoutée comme entrée séparée de type
`cmdkey`.

Une fois la ré-importation faite, recompile l'exercice contenant le
QCM : il doit passer.

## Fichiers livrés

```
MODIFIÉS
appli/services/paquet_parseur.py             (+33 lignes : cas \define@choicekey)
appli/tests/test_paquet_parseur.py           (+4 tests)
appli/doc/redemarrage_v0_13_7_2_2.md         (NEW)
```

Aucun fichier nouveau côté services/routes/static. C'est un fix
strictement ciblé sur le parseur.

## Vérifications

- Suite pytest : **3257 passed, 5 skipped, 0 failed** (3253 baseline
  + 4 nouveaux tests pour `\define@choicekey`)
- Test unitaire sur le snippet réel de ton `.dtx` : la macro
  synthétique `\cmdseq@seqQcm@explication` est désormais indexée avec
  un `texte_complet` de 173 octets contenant la directive complète

## À tester chez toi

### Scénario A — Recompilation d'un exercice avec QCM

1. **Re-importer le paquet** dans l'app (workflow habituel).
2. Vérifier (via une requête sur la BdD si tu veux) que
   `\cmdseq@seqQcm@explication` apparaît bien dans `paquet_definitions` :
   ```sql
   SELECT nom, type_latex FROM paquet_definitions
     WHERE nom = '\cmdseq@seqQcm@explication';
   ```
   → tu dois voir 1 ligne, type `cmdkey`.
3. Ouvrir l'exercice qui contenait le `\begin{seqQcm}` qui ne compilait
   pas.
4. **Compiler** : il doit maintenant passer sans erreur xkeyval.

### Scénario B — Vérifier qu'on ne casse rien sur les exercices déjà OK

1. Reprendre n'importe quel exercice **sans QCM** déjà testé en
   production.
2. Compiler.
3. **Vérifier** : compilation identique à avant (aucune régression).

### Scénario C — Diagnostic d'éventuels autres `\define@choicekey`

Le paquet seqenseigne pourrait avoir d'autres `\define@choicekey` qui
ne se manifestaient pas (car la clé n'était jamais utilisée dans un
contexte où le défaut n'aurait pas suffi). Avec le fix, ces clés
seront désormais indexées et leur définition propagée.

Pour repérer s'il y en a d'autres :

```sql
SELECT nom, fichier_source FROM paquet_definitions
  WHERE type_latex = 'cmdkey'
    AND texte_complet LIKE '%define@choicekey%';
```

→ liste les choicekey nouvellement indexés. Aucun problème attendu, mais
ça permet de prendre conscience du périmètre.

## Reprise du chantier v0.13.7.3

Sitôt ce hotfix validé en production, on reprend la v0.13.7.3 :

- Wrapping de la sélection avec marqueur `•` (BULLET, comme Texmaker)
- Commandes additionnelles : `\newline`, `\smallskip`, `\ldots`
- Générateur de QCM (paramètre : nombre de questions)
- Générateur de liste (type, nombre d'items, puce `\ding` avec palette
  pré-construite)

Les décisions de cadrage sont toutes prises, le code n'attend que la
reprise.
