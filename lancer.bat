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
REM
REM  v0.51.0 - Profil de lancement (premier ou second parametre) :
REM     .\lancer.bat              profil complet, port 5000 (comme avant)
REM     .\lancer.bat atelier      conception des referentiels, port 5000
REM     .\lancer.bat classe       suivi des classes, port 5001
REM  Les deux profils peuvent tourner en meme temps (deux fenetres).
REM  Exemple combine : .\lancer.bat classe --skip-verify
REM
REM  v0.51.3 - Base separee pour le profil classe (essai de l'import de
REM  paquets sur une base vide, dossier data_classe\, cree au besoin) :
REM     .\lancer.bat classe --base-classe
REM ============================================================================

echo.
echo  seqenseigne
echo.

REM --- v0.51.0 : lecture des parametres (profil, --skip-verify) ---------------
set "SEQ_PROFIL=complet"
set "SEQ_PORT=5000"
set "SKIP_VERIFY="
set "SEQ_DATA="
:lire_params
if "%~1"=="" goto :params_lus
if /I "%~1"=="--skip-verify" set "SKIP_VERIFY=1"
if /I "%~1"=="--no-verify"   set "SKIP_VERIFY=1"
if /I "%~1"=="complet"       set "SEQ_PROFIL=complet"
if /I "%~1"=="atelier"       set "SEQ_PROFIL=atelier"
if /I "%~1"=="classe"        set "SEQ_PROFIL=classe"
if /I "%~1"=="--base-classe" set "SEQ_DATA=data_classe"
shift
goto :lire_params
:params_lus
if /I "%SEQ_PROFIL%"=="classe" set "SEQ_PORT=5001"
title seqenseigne - %SEQ_PROFIL%
echo  Profil : %SEQ_PROFIL%

REM --- Detection de l'option --skip-verify ------------------------------------
if "%SKIP_VERIFY%"=="1" goto :launch_skip

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
echo  Demarrage du serveur sur http://localhost:%SEQ_PORT%
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
