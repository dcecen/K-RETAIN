@echo off
rem ============================================================
rem  RetainWall - lanceur (double-clic)
rem  Installe ce qui manque la premiere fois, prepare l'interface,
rem  demarre le logiciel et ouvre le navigateur.
rem  Fermer cette fenetre arrete le logiciel.
rem ============================================================
chcp 65001 >nul
title RetainWall
cd /d "%~dp0"

rem --- Deja lance ? Si le code n'a pas change depuis son demarrage, on ouvre simplement le navigateur ;
rem     sinon (mise a jour du logiciel) on arrete l'ancienne instance pour repartir sur la version a jour.
rem     Code retour : 0 = a jour, 1 = perime, 2 = non lance.
powershell -NoProfile -Command "try { $s = Invoke-RestMethod http://127.0.0.1:8000/api/sante -TimeoutSec 2 } catch { exit 2 }; if (-not $s.demarrage) { exit 1 }; $t0 = [DateTimeOffset]::FromUnixTimeMilliseconds([long]($s.demarrage * 1000)).LocalDateTime; $b = Get-ChildItem backend\sout -Recurse -Filter *.py | Where-Object { $_.LastWriteTime -gt $t0 }; $d = 'frontend\dist\index.html'; if (-not (Test-Path $d)) { exit 1 }; $td = (Get-Item $d).LastWriteTime; $f = Get-ChildItem frontend\src, frontend\index.html -Recurse -File | Where-Object { $_.LastWriteTime -gt $td }; if ($b -or $f) { exit 1 } else { exit 0 }"
if errorlevel 2 goto lancement
if errorlevel 1 goto mise_a_jour
echo RetainWall est deja lance.
if not defined RETAINWALL_SANS_NAVIGATEUR start "" http://localhost:8000
exit /b 0

:mise_a_jour
echo RetainWall tourne avec une version perimee : redemarrage sur la version a jour...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }; Start-Sleep -Seconds 1"

:lancement

rem --- 1. Serveur de calcul : installation la premiere fois
if not exist "backend\.venv\Scripts\python.exe" (
  echo Installation du serveur de calcul, premiere fois seulement...
  py -3.12 -m venv backend\.venv
  if errorlevel 1 goto erreur_python
  pushd backend
  .venv\Scripts\python.exe -m pip install --upgrade pip
  .venv\Scripts\python.exe -m pip install -e ".[test]"
  if errorlevel 1 (
    popd
    goto erreur
  )
  popd
)

rem --- 2. Interface : installation la premiere fois
if not exist "frontend\node_modules" (
  echo Installation de l'interface, premiere fois seulement...
  pushd frontend
  call npm install
  if errorlevel 1 (
    popd
    goto erreur_node
  )
  popd
)

rem --- 3. Interface : compilation si absente ou si le code a change
powershell -NoProfile -Command "$d='frontend\dist\index.html'; if (-not (Test-Path $d)) { exit 1 }; $t=(Get-Item $d).LastWriteTime; $n=Get-ChildItem frontend\src, frontend\index.html -Recurse -File | Where-Object { $_.LastWriteTime -gt $t }; if ($n) { exit 1 } else { exit 0 }"
if errorlevel 1 (
  echo Preparation de l'interface, environ 30 secondes...
  pushd frontend
  call npm run build
  if errorlevel 1 (
    popd
    goto erreur
  )
  popd
)

rem --- 4. Ouverture du navigateur des que le serveur repond
if not defined RETAINWALL_SANS_NAVIGATEUR (
  start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for ($i = 0; $i -lt 90; $i++) { try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/sante -TimeoutSec 1 | Out-Null; Start-Process 'http://localhost:8000'; break } catch { Start-Sleep -Seconds 1 } }"
)

echo.
echo  RetainWall demarre : http://localhost:8000
echo  Laissez cette fenetre ouverte pendant l'utilisation.
echo  Fermez-la pour arreter le logiciel.
echo.
cd backend
.venv\Scripts\python.exe -m uvicorn sout.api:app --host 127.0.0.1 --port 8000
goto fin

:erreur_python
echo.
echo  Python 3.12 est introuvable. Installez-le depuis https://www.python.org
echo  en cochant "Add python.exe to PATH", puis relancez.
goto pause

:erreur_node
echo.
echo  Node.js est introuvable. Installez la version LTS depuis https://nodejs.org
echo  puis relancez.
goto pause

:erreur
echo.
echo  Une erreur est survenue : lisez les messages ci-dessus.

:pause
pause
exit /b 1

:fin
