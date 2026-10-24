# Lance RetainWall en mode serveur interne (sans Docker) sur le port 8000.
# Prérequis : backend/.venv installé, interface compilée (cd frontend ; npm run build),
# au moins un compte créé :  backend\.venv\Scripts\python -m sout.utilisateurs ajouter <nom>
# Par défaut le serveur n'écoute que sur ce poste (127.0.0.1), derrière le proxy HTTPS décrit dans
# docs/INSTALLATION.md ; pour l'exposer directement sur le réseau : $env:RETAINWALL_HOTE = "0.0.0.0".
$hote = if ($env:RETAINWALL_HOTE) { $env:RETAINWALL_HOTE } else { "127.0.0.1" }
Set-Location "$PSScriptRoot\backend"
if (-not (Test-Path "..\frontend\dist\index.html")) {
    Write-Host "Interface non compilée : lancez d'abord 'npm run build' dans le dossier frontend."
    exit 1
}
$authAvant = $env:RETAINWALL_AUTH
$env:RETAINWALL_AUTH = "1"
try {
    & .\.venv\Scripts\python.exe -m uvicorn sout.api:app --host $hote --port 8000 --workers 2
} finally {
    # ne pas laisser l'authentification active dans ce terminal (les tests et lancer_backend.ps1 la subiraient)
    if ($null -eq $authAvant) { Remove-Item Env:RETAINWALL_AUTH -ErrorAction SilentlyContinue } else { $env:RETAINWALL_AUTH = $authAvant }
}
