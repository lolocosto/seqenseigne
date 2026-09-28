# Redémarrage v0.13.5.1.6.1 — Fix lancer.bat (parsing cmd.exe)

Date : 10 mai 2026
Périmètre : 1 fichier corrigé (`appli/lancer.bat`)

---

## Problème

Après application de v0.13.5.1.6, le lancement de `.\lancer.bat` chez
Laurent affiche :

```
 seqenseigne
 Verification d'integrite des fichiers...
-> était inattendu.
```

→ Le script plante immédiatement après l'invocation de `verifier_md5`,
alors que la vérification d'intégrité elle-même a réussi (le script
Python a tourné, l'arborescence est saine — `2112 passed` côté pytest).

## Cause

Deux pièges de cmd.exe combinés :

1. **Parsing des blocs `( ... )` au chargement, pas à l'exécution.**
   cmd.exe parse l'intégralité d'un bloc `if "%RC%"=="1" ( ... )` au
   moment où il rencontre le `if`, **même si la condition est fausse**.
   Si le bloc contient un caractère mal échappé, ça plante avant que la
   branche soit prise.

2. **`-^>` dans un `echo` à l'intérieur d'un bloc parenthésé.** Hors
   bloc, `echo -^>` affiche bien `->`. Mais dans un bloc `( ... )`, le
   parsing est différent et `-^>` est interprété comme une redirection
   après `-`, d'où le message `-> était inattendu.`.

C'est précisément le 3e bloc (`if "%RC%"=="1" ( ... )`, lignes 76-97 de
l'ancienne version) qui contenait ces séquences dans ses messages
d'erreur.

## Fix

Refonte structurelle du `lancer.bat` : **plus aucun bloc parenthésé
complexe**, tout passe par des `goto :label`. Pattern idiomatique cmd.exe
pour les branches conditionnelles avec contenu non-trivial.

```batch
REM AVANT (cassait à cause du parsing du bloc)
if "%RC%"=="1" (
    echo  ...
    echo  -^> redeployer  ←  PLANTE LE PARSING
    pause
    exit /b 1
)

REM APRES (chaque cible est un label autonome)
if "%RC%"=="1" goto :err_divergence
...
:err_divergence
echo ...
echo Solution : redeployer  ←  texte simple, pas d'echappement
pause
exit /b 1
```

En plus du fix structurel :

- Remplacement des `-^>` (caractère `→` flèche) par des formulations
  textuelles (`Solution : ...`, `a)`, `b)`, `c)`) pour éliminer tout
  risque d'échappement parasite.
- Suppression des `^^` de continuation de ligne dans les `echo` (mis
  en plusieurs lignes textuelles à la place).
- Code mieux lisible : section "lancement" et section "erreurs" bien
  séparées en bas du fichier, avec `:label` autodocumenté.

## Validation

Plus aucun caractère problématique :

```
grep "\^\^"   lancer.bat  →  rien
grep "\-\^>"  lancer.bat  →  rien
grep "if .* (" lancer.bat →  rien (plus aucun bloc parenthésé)
```

Comportement fonctionnel inchangé :
- Cas intégrité OK   → `[OK] Integrite verifiee` puis démarrage Flask
- Cas divergence     → exit 1, message explicatif avec 3 causes
- Cas manifest absent → exit 2, instructions de génération
- Cas outil absent   → exit 2, instructions de déploiement
- `--skip-verify`    → bypass de la vérif, démarrage direct

## Pourquoi ce piège n'a pas été détecté en sandbox

Mon environnement de test est Linux. Je ne peux pas simuler cmd.exe et
son parsing des blocs `( ... )`. La logique Python (codes retour de
`verifier_md5`) avait été validée correctement, mais le wrapper batch
non — il aurait fallu un test fonctionnel sur Windows pour le voir.

Pour l'avenir : ajouter dans GOTCHAS.md une entrée sur le parsing des
blocs cmd.exe (à faire en suite, fait dans la prochaine livraison ou
en édition manuelle de ta part).

## Fichiers livrés (1)

| Fichier | Action | Taille |
|---|---|---|
| `appli/lancer.bat` | Refondu (en remplacement) | 3858 octets |

MD5 dans `MANIFEST.md5` à la racine du ZIP.

## Déploiement

1. Décompresser le ZIP à la racine de `D:\Enseignement\seqenseigne\`
   (le seul fichier modifié est `appli\lancer.bat`).

2. Régénérer `appli_inventaire.txt` pour intégrer le nouveau MD5 du
   `lancer.bat`, sinon `lancer.bat` se plaindra lui-même à la
   prochaine exécution :

   ```powershell
   cd D:\Enseignement\seqenseigne\appli
   ..\outils\python\python.exe outils\verifier_md5.py ^
      --racine . --generer --manifest appli_inventaire.txt
   ```

3. Lancer :

   ```powershell
   .\lancer.bat
   ```

   Attendu :
   ```
    seqenseigne

    Verification d'integrite des fichiers...
    [OK] Integrite verifiee

    Demarrage du serveur sur http://localhost:5000
   ```
