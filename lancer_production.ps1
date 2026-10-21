# Lance RetainWall en mode serveur interne (sans Docker) sur le port 8000.
# Prérequis : backend/.venv installé, interface compilée (cd frontend ; npm run build),
# au moins un compte créé :  backend\.venv\Scripts\python -m sout.utilisateurs ajouter <nom>
$env:RETAINWALL_AUTH = "1"
Set-Location "$PSScriptRoot\backend"
if (-not (Test-Path "..\frontend\dist\index.html")) {
    Write-Host "Interface non compilée : lancez d'abord 'npm run build' dans le dossier frontend."
    exit 1
}
& .\.venv\Scripts\python.exe -m uvicorn sout.api:app --host 0.0.0.0 --port 8000 --workers 2
