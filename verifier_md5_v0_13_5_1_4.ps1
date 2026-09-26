# =============================================================================
# verifier_md5_v0_13_5_1_4.ps1
#
# Vérifie que les fichiers livrés dans la version v0.13.5.1.4 sont arrivés
# intacts sur le poste après décompression du ZIP.
#
# Utilisation :
#   1. Place ce script à la racine de  D:\Enseignement\seqenseigne\appli
#   2. Ouvre PowerShell dans ce dossier
#   3. Lance :  .\verifier_md5_v0_13_5_1_4.ps1
# =============================================================================

# Force l'output console en UTF-8 pour que les accents s'affichent
# correctement sur les terminaux PowerShell configurés en cp1252.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$reference = @(
  @{ Path = "persistence\schema.sql";                 Size = 44047;  Md5 = "7e5ec612d887e85521e689ff86d5f026" }
  @{ Path = "persistence\sqlite_store.py";            Size = 112177; Md5 = "73cc93a7c1aea858c37fc6d6a102d2f7" }
  @{ Path = "services\referentiels.py";               Size = 28012;  Md5 = "a97375e5a1da3972238f65dcb22efc0c" }
  @{ Path = "routes\referentiels.py";                 Size = 8090;   Md5 = "e7e36f9dd8d6636df26aed6b98e1512f" }
  @{ Path = "templates\index.html";                   Size = 125150; Md5 = "42b6a3947fc9dd5e0328071bf8c90444" }
  @{ Path = "static\app.js";                          Size = 288588; Md5 = "985e10c5f2a59a66a4c20d17a5ce945f" }
  @{ Path = "static\atelier_referentiel.js";          Size = 26638;  Md5 = "a20350ebe0bbec95721ef95691bf7d63" }
  @{ Path = "doc\scoping_v0_13_5_referentiels.md";    Size = 14457;  Md5 = "8fb22cea0fbd0efebdf473240d1d12c9" }
  @{ Path = "doc\redemarrage_v0_13_5_1.md";           Size = 13386;  Md5 = "5c2496aa8bcb20ea95f9f301a0ad3c51" }
  @{ Path = "doc\redemarrage_v0_13_5_1_1.md";         Size = 3296;   Md5 = "be92cd618852e9b675c33b17625624de" }
  @{ Path = "doc\redemarrage_v0_13_5_1_2.md";         Size = 5094;   Md5 = "a141aba5fb26db8ccaf1a0333b478445" }
  @{ Path = "doc\redemarrage_v0_13_5_1_3.md";         Size = 2935;   Md5 = "8f94a83b0ce0c094903c4642c773d326" }
  @{ Path = "doc\redemarrage_v0_13_5_1_4.md";         Size = 2751;   Md5 = "db6f7b320cc43f4d88d1411d945d9672" }
  @{ Path = "tests\test_v0_13_5_1_referentiels.py";   Size = 27135;  Md5 = "2a2f5f719ea69f97471d956a79ca4a49" }
)

Write-Host ""
Write-Host "Vérification de la livraison v0.13.5.1.4 dans : $(Get-Location)" -ForegroundColor Cyan
Write-Host ("=" * 90)

$nbOk = 0
$nbKo = 0
$nbAbs = 0
$problemes = @()

foreach ($f in $reference) {
  $path = $f.Path

  if (-not (Test-Path $path)) {
    Write-Host ("[ABSENT] {0}" -f $path) -ForegroundColor Red
    $nbAbs++
    $problemes += $path
    continue
  }

  $taille = (Get-Item $path).Length
  $md5    = (Get-FileHash -Algorithm MD5 $path).Hash.ToLower()

  $tailleOk = ($taille -eq $f.Size)
  $md5Ok    = ($md5    -eq $f.Md5)

  if ($tailleOk -and $md5Ok) {
    Write-Host ("[OK    ] {0}" -f $path) -ForegroundColor Green
    $nbOk++
  } else {
    Write-Host ("[KO    ] {0}" -f $path) -ForegroundColor Red
    Write-Host ("           taille attendue : {0}, obtenue : {1}" -f $f.Size, $taille) -ForegroundColor Red
    Write-Host ("           md5    attendu  : {0}" -f $f.Md5) -ForegroundColor Red
    Write-Host ("           md5    obtenu   : {0}" -f $md5)   -ForegroundColor Red
    $nbKo++
    $problemes += $path
  }
}

Write-Host ("=" * 90)
Write-Host ""

if ($nbKo -eq 0 -and $nbAbs -eq 0) {
  Write-Host ("TOUT EST OK ({0} fichiers vérifiés)" -f $nbOk) -ForegroundColor Green
  exit 0
} else {
  Write-Host ("Bilan : {0} OK, {1} corrompus, {2} absents" -f $nbOk, $nbKo, $nbAbs) -ForegroundColor Yellow
  Write-Host ""
  Write-Host "Fichiers à récupérer :" -ForegroundColor Yellow
  foreach ($p in $problemes) {
    Write-Host ("  - {0}" -f $p) -ForegroundColor Yellow
  }
  Write-Host ""
  Write-Host "Demande un mini-ZIP de récupération avec ces fichiers." -ForegroundColor Yellow
  exit 1
}
