# Lance tous les tests du calcul
Set-Location "$PSScriptRoot\backend"
& .\.venv\Scripts\python.exe -m pytest -q
