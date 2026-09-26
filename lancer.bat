@echo off
setlocal

cd /d "%~dp0"

REM ============================================================================
REM  seqenseigne - Lancement avec verification d'integrite
REM ============================================================================
REM
REM  Ce script est dans appli/. Il appelle le Python portable qui est dans
REM  ..\outils\python\, et l'outil de verification dans .\outils\.
REM
REM  Avant de demarrer le serveur Flask, on verifie que l'arborescence n'a
REM  pas ete corrompue depuis la derniere livraison validee (cf. GOTCHAS.md
REM  #4 fichier Python tronque sans erreur de syntaxe + #19 antivirus/cloud).
REM
REM  La reference est appli_inventaire.txt (a la racine de appli/), qui doit
REM  etre regenere apres chaque livraison validee (cf. CONVENTIONS.md).
REM
REM  Pour regenerer la reference apres avoir valide une livraison :
REM     ..\outils\python\python.exe outils\verifier_md5.py
REM        --racine . --generer --manifest appli_inventaire.txt
REM
REM  Pour outrepasser temporairement la verification (cas exceptionnel) :
REM     .\lancer.bat --skip-verify
REM ============================================================================

echo.
echo  seqenseigne
echo.

REM --- Detection de l'option --skip-verify ------------------------------------
if /I "%~1"=="--skip-verify" goto :launch_skip
if /I "%~1"=="--no-verify"   goto :launch_skip

REM --- Verification des prerequis --------------------------------------------
if not exist "appli_inventaire.txt"   goto :err_no_manifest
if not exist "outils\verifier_md5.py" goto :err_no_tool

REM --- Verification de l'integrite des fichiers ------------------------------
echo  Verification d'integrite des fichiers...
"..\outils\python\python.exe" "outils\verifier_md5.py" --racine . --manifest appli_inventaire.txt --silencieux
set RC=%ERRORLEVEL%

if "%RC%"=="2" goto :err_manifest_illisible
if "%RC%"=="1" goto :err_divergence

echo  [OK] Integrite verifiee
echo.
goto :launch


REM ============================================================================
REM  Cibles : lancement (normal ou bypass)
REM ============================================================================

:launch_skip
echo  [!] Verification MD5 desactivee par --skip-verify
echo.
goto :launch

:launch
echo  Demarrage du serveur sur http://localhost:5000
echo  (Ctrl+C pour arreter)
echo.
"..\outils\python\python.exe" app.py
pause
exit /b 0


REM ============================================================================
REM  Cibles : erreurs
REM ============================================================================

:err_no_manifest
echo  [!] appli_inventaire.txt absent
echo      Reference d'integrite manquante. Pour la generer :
echo         ..\outils\python\python.exe outils\verifier_md5.py
echo            --racine . --generer --manifest appli_inventaire.txt
echo.
echo      Ou relancer avec --skip-verify pour ignorer cette verification.
echo.
pause
exit /b 2

:err_no_tool
echo  [!] outils\verifier_md5.py absent
echo      L'outil de verification d'integrite n'est pas installe.
echo      Verifier la derniere livraison ou relancer avec --skip-verify.
echo.
pause
exit /b 2

:err_manifest_illisible
echo.
echo  [X] Erreur : reference d'integrite illisible.
echo      Verifier appli_inventaire.txt ou regenerer la reference.
echo.
pause
exit /b 2

:err_divergence
echo.
echo  [X] DIVERGENCE DETECTEE entre l'arborescence et la reference.
echo      Detail :
echo.
"..\outils\python\python.exe" "outils\verifier_md5.py" --racine . --manifest appli_inventaire.txt
echo.
echo  [!] Le serveur n'a PAS ete demarre.
echo.
echo      Causes possibles :
echo        a) une livraison n'a pas ete deployee proprement (fichier tronque,
echo           ZIP partiel). Solution : redeployer le dernier ZIP livre.
echo        b) une livraison vient d'etre deployee mais la reference n'a pas
echo           ete regeneree. Solution : apres validation des tests, regenerer
echo           avec :
echo               ..\outils\python\python.exe outils\verifier_md5.py
echo                  --racine . --generer --manifest appli_inventaire.txt
echo        c) un fichier a ete edite localement de bonne foi (developpement
echo           en cours). Solution : regenerer la reference, ou relancer avec
echo           --skip-verify.
echo.
pause
exit /b 1
