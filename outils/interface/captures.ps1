# Compile l'interface, la sert sur le port 8011 (serveur de test, distinct du 8000 du lanceur), lance le test de
# fumée fumee.mjs (captures d'écran + erreurs console) et arrête le serveur.
# Usage : powershell -File outils\interface\captures.ps1 [-Prefixe apres] [-Dossier docs\captures\x] [-SansBuild]
param(
    [string]$Prefixe = "capture",
    [string]$Dossier = "",
    [switch]$SansBuild
)
$ErrorActionPreference = "Continue"
$racine = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if ($Dossier -eq "") { $Dossier = Join-Path $racine "docs\captures\fumee" }
if (-not $SansBuild) {
    Push-Location (Join-Path $racine "frontend")
    npm run build
    if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "Compilation de l'interface en echec" -ForegroundColor Red; exit 1 }
    Pop-Location
}
$python = Join-Path $racine "backend\.venv\Scripts\python.exe"
$serveur = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "sout.api:app", "--port", "8011", "--log-level", "warning" -WorkingDirectory (Join-Path $racine "backend") -PassThru -WindowStyle Hidden
$pret = $false
for ($i = 0; $i -lt 60 -and -not $pret; $i++) {
    try { Invoke-RestMethod -Uri "http://127.0.0.1:8011/api/sante" -TimeoutSec 2 | Out-Null; $pret = $true } catch { Start-Sleep -Seconds 1 }
}
if (-not $pret) { Stop-Process -Id $serveur.Id -Force; Write-Host "Serveur de test injoignable" -ForegroundColor Red; exit 1 }
node (Join-Path $PSScriptRoot "fumee.mjs") "http://127.0.0.1:8011/" $Dossier $Prefixe
$code = $LASTEXITCODE
Stop-Process -Id $serveur.Id -Force -ErrorAction SilentlyContinue
if ($code -ne 0) { Write-Host "Fumee : erreurs relevees (code $code)" -ForegroundColor Red } else { Write-Host "Fumee : aucune erreur" -ForegroundColor Green }
exit $code
