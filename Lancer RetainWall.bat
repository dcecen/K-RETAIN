@echo off
rem ============================================================
rem  RetainWall - lanceur (double-clic)
rem  Installe ce qui manque la premiere fois (ou quand les dependances
rem  changent), prepare l'interface, demarre le logiciel et ouvre le navigateur.
rem  Fermer cette fenetre arrete le logiciel.
rem  Journal des erreurs de demarrage : %LOCALAPPDATA%\RetainWall\demarrage.log
rem ============================================================
chcp 65001 >nul
title RetainWall
cd /d "%~dp0"
set "DOSSIER_JOURNAL=%LOCALAPPDATA%\RetainWall"
set "JOURNAL=%DOSSIER_JOURNAL%\demarrage.log"
if not exist "%DOSSIER_JOURNAL%" mkdir "%DOSSIER_JOURNAL%" >nul 2>&1

rem --- Deja lance ? Codes : 0 = RetainWall a jour, 1 = RetainWall perime (code modifie depuis son
rem     demarrage), 2 = rien sur le port 8000, 3 = un AUTRE programme occupe le port 8000.
rem     Seul un serveur qui repond "statut: ok" avec son heure de demarrage est reconnu comme RetainWall.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; try { $s = Invoke-RestMethod http://127.0.0.1:8000/api/sante -TimeoutSec 2 } catch { if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 3 } else { exit 2 } }; if (-not ($s -is [System.Management.Automation.PSCustomObject]) -or $s.statut -ne 'ok' -or -not $s.demarrage) { exit 3 }; $t0 = [DateTimeOffset]::FromUnixTimeMilliseconds([long]($s.demarrage * 1000)).LocalDateTime; $b = Get-ChildItem backend\sout -Recurse -Filter *.py | Where-Object { $_.LastWriteTime -gt $t0 }; $d = 'frontend\dist\index.html'; if (-not (Test-Path $d)) { exit 1 }; $td = (Get-Item $d).LastWriteTime; $f = Get-ChildItem frontend\src, frontend\index.html, frontend\package.json, frontend\vite.config.ts -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt $td }; if (Test-Path frontend\public) { $f += Get-ChildItem frontend\public -Recurse -File | Where-Object { $_.LastWriteTime -gt $td } }; if ($b -or $f) { exit 1 } else { exit 0 }"
if errorlevel 3 goto port_occupe
if errorlevel 2 goto lancement
if errorlevel 1 goto mise_a_jour
echo RetainWall est deja lance.
if not defined RETAINWALL_SANS_NAVIGATEUR start "" http://localhost:8000
exit /b 0

:mise_a_jour
echo RetainWall tourne avec une version perimee : redemarrage sur la version a jour...
type nul > "%DOSSIER_JOURNAL%edemarrage_demande"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }; Start-Sleep -Seconds 1"

:lancement

rem --- 1. Serveur de calcul : installation la premiere fois, ou quand pyproject.toml a change
rem     (temoin backend\.venv\.installe ecrit apres une installation reussie).
powershell -NoProfile -ExecutionPolicy Bypass -Command "$t = 'backend\.venv\.installe'; if (-not (Test-Path 'backend\.venv\Scripts\python.exe') -or -not (Test-Path $t)) { exit 1 }; if ((Get-Item 'backend\pyproject.toml').LastWriteTime -gt (Get-Item $t).LastWriteTime) { exit 1 }; if ((Test-Path 'backend\requirements.lock.txt') -and (Get-Item 'backend\requirements.lock.txt').LastWriteTime -gt (Get-Item $t).LastWriteTime) { exit 1 }; exit 0"
if errorlevel 1 (
  echo Installation ou mise a jour du serveur de calcul...
  if not exist "backend\.venv\Scripts\python.exe" call :creer_venv
  if not exist "backend\.venv\Scripts\python.exe" goto erreur_python
  pushd backend
  .venv\Scripts\python.exe -m pip install --upgrade pip
  if exist requirements.lock.txt (
    .venv\Scripts\python.exe -m pip install -e ".[test]" -c requirements.lock.txt
  ) else (
    .venv\Scripts\python.exe -m pip install -e ".[test]"
  )
  if errorlevel 1 (
    popd
    echo Installation du serveur de calcul en echec ^(voir les messages ci-dessus^). >> "%JOURNAL%"
    goto erreur
  )
  popd
  type nul > "backend\.venv\.installe"
)

rem --- 2. Interface : installation la premiere fois, ou quand package-lock.json / package.json a change
powershell -NoProfile -ExecutionPolicy Bypass -Command "$t = 'frontend\node_modules\.installe'; if (-not (Test-Path 'frontend\node_modules') -or -not (Test-Path $t)) { exit 1 }; $ref = if (Test-Path 'frontend\package-lock.json') { 'frontend\package-lock.json' } else { 'frontend\package.json' }; if ((Get-Item $ref).LastWriteTime -gt (Get-Item $t).LastWriteTime) { exit 1 }; exit 0"
if errorlevel 1 (
  echo Installation ou mise a jour de l'interface...
  pushd frontend
  call npm install
  if errorlevel 1 (
    popd
    goto erreur_node
  )
  popd
  type nul > "frontend\node_modules\.installe"
)

rem --- 3. Interface : compilation si absente ou si le code a change
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d = 'frontend\dist\index.html'; if (-not (Test-Path $d)) { exit 1 }; $t = (Get-Item $d).LastWriteTime; $n = Get-ChildItem frontend\src, frontend\index.html, frontend\package.json, frontend\vite.config.ts -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt $t }; if (Test-Path frontend\public) { $n += Get-ChildItem frontend\public -Recurse -File | Where-Object { $_.LastWriteTime -gt $t } }; if ($n) { exit 1 } else { exit 0 }"
if errorlevel 1 (
  echo Preparation de l'interface, environ 30 secondes...
  pushd frontend
  call npm run build
  if errorlevel 1 (
    popd
    echo Compilation de l'interface en echec ^(npm run build^). >> "%JOURNAL%"
    goto erreur
  )
  popd
)

rem --- 4. Controle rapide : le serveur de calcul se charge-t-il ? (erreur de code visible et journalisee)
pushd backend
.venv\Scripts\python.exe -c "import sout.api" > "%JOURNAL%.tmp" 2>&1
if errorlevel 1 (
  popd
  echo.
  echo  Le serveur de calcul ne demarre pas ^(erreur dans le code ou dependance manquante^) :
  type "%JOURNAL%.tmp"
  type "%JOURNAL%.tmp" >> "%JOURNAL%"
  del "%JOURNAL%.tmp" >nul 2>&1
  goto erreur
)
popd
del "%JOURNAL%.tmp" >nul 2>&1

rem --- 5. Ouverture du navigateur des que le serveur repond
if not defined RETAINWALL_SANS_NAVIGATEUR (
  start "" /b powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "for ($i = 0; $i -lt 90; $i++) { try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/sante -TimeoutSec 1 | Out-Null; Start-Process 'http://localhost:8000'; break } catch { Start-Sleep -Seconds 1 } }"
)

echo.
echo  RetainWall demarre : http://localhost:8000
echo  Laissez cette fenetre ouverte pendant l'utilisation.
echo  Fermez-la pour arreter le logiciel.
echo.
cd backend
.venv\Scripts\python.exe -m uvicorn sout.api:app --host 127.0.0.1 --port 8000
set "CODE=%ERRORLEVEL%"
cd ..
if exist "%DOSSIER_JOURNAL%edemarrage_demande" (
  rem arret provoque par un lanceur plus recent (mise a jour) : cette fenetre se ferme simplement
  del "%DOSSIER_JOURNAL%edemarrage_demande" >nul 2>&1
  goto fin
)
if not "%CODE%"=="0" (
  echo.
  echo  Le serveur de calcul s'est arrete avec le code %CODE% ^(lisez les messages ci-dessus^).
  echo  Serveur arrete avec le code %CODE% le %DATE% %TIME%. >> "%JOURNAL%"
  goto pause
)
goto fin

:creer_venv
rem Python 3.12 de preference, sinon toute version >= 3.12 trouvee par "py -3" ou "python".
py -3.12 -m venv backend\.venv 2>nul
if exist "backend\.venv\Scripts\python.exe" exit /b 0
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" 2>nul && py -3 -m venv backend\.venv
if exist "backend\.venv\Scripts\python.exe" exit /b 0
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" 2>nul && python -m venv backend\.venv
exit /b 0

:port_occupe
echo.
echo  Le port 8000 est occupe par un autre programme que RetainWall : fermez-le, puis relancez.
echo  ^(Pour savoir lequel : netstat -ano ^| findstr :8000 ^)
goto pause

:erreur_python
echo.
echo  Python 3.12 ou plus recent est introuvable. Installez-le depuis https://www.python.org
echo  en cochant "Add python.exe to PATH", puis relancez.
goto pause

:erreur_node
echo.
echo  Node.js est introuvable ou l'installation de l'interface a echoue. Installez la version LTS
echo  depuis https://nodejs.org puis relancez.
goto pause

:erreur
echo.
echo  Une erreur est survenue : lisez les messages ci-dessus ^(journal : %JOURNAL%^).

:pause
pause
exit /b 1

:fin
