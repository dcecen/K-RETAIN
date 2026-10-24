# Lance tous les contrôles, dans l'ordre : calcul (pytest), qualité du code Python (ruff, s'il est installé),
# typage de l'interface (tsc), lint de l'interface (eslint), tests de l'interface (vitest).
# Code de retour 1 dès qu'une étape échoue ; chaque étape est annoncée pour savoir laquelle a échoué.
$ErrorActionPreference = "Continue"
$echecs = @()

function Etape($nom, $bloc) {
    Write-Host ""
    Write-Host "=== $nom" -ForegroundColor Cyan
    & $bloc
    if ($LASTEXITCODE -ne 0) {
        Write-Host "--- ECHEC : $nom (code $LASTEXITCODE)" -ForegroundColor Red
        $script:echecs += $nom
    } else {
        Write-Host "--- OK : $nom" -ForegroundColor Green
    }
}

Set-Location "$PSScriptRoot\backend"
Etape "Tests du calcul (pytest)" { & .\.venv\Scripts\python.exe -m pytest -q }
& .\.venv\Scripts\python.exe -m ruff --version *> $null
if ($LASTEXITCODE -eq 0) {
    Etape "Qualité du code Python (ruff)" { & .\.venv\Scripts\python.exe -m ruff check sout tests outils }
} else {
    Write-Host "(ruff absent : pip install -e `".[dev]`" dans backend pour l'activer)" -ForegroundColor DarkGray
}

Set-Location "$PSScriptRoot\frontend"
Etape "Typage de l'interface (tsc)" { & npx tsc --noEmit -p tsconfig.app.json }
Etape "Lint de l'interface (eslint)" { & npm run --silent lint }
Etape "Tests de l'interface (vitest)" { & npm test --silent }

Write-Host ""
if ($echecs.Count -gt 0) {
    Write-Host "Étapes en échec : $($echecs -join ' ; ')" -ForegroundColor Red
    exit 1
}
Write-Host "Tout est vert." -ForegroundColor Green
exit 0
