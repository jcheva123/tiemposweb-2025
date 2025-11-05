@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem === Config ===
set "REPO=C:\SHOWMIDGET\TIEMPOSWEB"
set "PY=python"
set "PRIME=1"   rem 1 = habilita priming CDN al final (acelera visibilidad)

cd /d "%REPO%" || (echo [ERROR] No se pudo entrar a %REPO% & exit /b 1)

echo.
echo === Repo: %REPO% ^| Rama: main ===
git status -s

rem Limpieza preventiva por si quedó un archivo basura accidental
if exist "remoto)" del /f /q "remoto)" >nul 2>&1

echo.
echo [INFO] Ejecutando: %PY% process_pdfs.py
%PY% process_pdfs.py
if errorlevel 1 (
  echo [ATENCION] process_pdfs.py devolvio errorlevel distinto de 0. Revisar la salida arriba. Se detiene el script.
  exit /b 1
)

echo.
echo [INFO] Preparando commit...
rem Scope acotado (incluye nueva seccion Series/)
git add resultados pdfs WEB Series process_pdfs.py *.bat .gitignore

rem Si hay cambios staged, commitear con fecha/hora
git diff --cached --quiet
if errorlevel 1 (
  for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set FECHA=%%c-%%b-%%a
  for /f "tokens=1-2 delims=: " %%a in ('time /t') do set HORA=%%a%%b
  git commit -m "[auto] actualizar jsons y manifiestos !FECHA! !HORA!"
) else (
  echo [INFO] No hay cambios para commitear.
)

echo.
echo [INFO] Sincronizando con GitHub (local -^> remoto)...
git push --force-with-lease origin main
if errorlevel 1 (
  echo [ERROR] No se pudo pushear. Verificar red/credenciales o rama protegida.
  exit /b 1
)

rem ====== PRIMING OPCIONAL DE CDNs PARA ACELERAR VISIBILIDAD ======
if "%PRIME%"=="1" (
  echo.
  echo [INFO] Priming de caches (RAW + jsDelivr + Statically)...
  set "BRAW=https://raw.githubusercontent.com/jcheva123/tiemposweb-2025/main/"
  set "BJS=https://cdn.jsdelivr.net/gh/jcheva123/tiemposweb-2025@main/"
  set "BST=https://cdn.statically.io/gh/jcheva123/tiemposweb-2025/main/"

  rem 1) fechas.json
  for %%U in ("%BRAW%resultados/fechas.json" "%BJS%resultados/fechas.json" "%BST%resultados/fechas.json") do (
    curl -s -o nul "%%~U?ts=!RANDOM!!RANDOM!" 2>nul
  )

  rem 2) todos los index.json presentes (para que aparezcan rápido las nuevas carreras)
  for /r "resultados" %%I in (*index.json) do (
    set "REL=%%I"
    set "REL=!REL:%REPO%\=!"
    set "REL=!REL:\=/!"
    for %%U in ("%BRAW%!REL!" "%BJS%!REL!" "%BST%!REL!") do (
      curl -s -o nul "%%~U?ts=!RANDOM!!RANDOM!" 2>nul
    )
  )
)

echo.
echo [OK] Listo.
exit /b 0
