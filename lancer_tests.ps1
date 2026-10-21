# Lance tous les tests : calcul (pytest) puis vue 3D de l'interface (vitest)
Set-Location "$PSScriptRoot\backend"
& .\.venv\Scripts\python.exe -m pytest -q
$codeCalcul = $LASTEXITCODE
Set-Location "$PSScriptRoot\frontend"
& npm test
if ($codeCalcul -ne 0 -or $LASTEXITCODE -ne 0) { exit 1 }
