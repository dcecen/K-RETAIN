# Lance le serveur de calcul sur http://127.0.0.1:8000
Set-Location "$PSScriptRoot\backend"
& .\.venv\Scripts\python.exe -m uvicorn sout.api:app --reload --port 8000
