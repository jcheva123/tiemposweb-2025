@echo off
setlocal enabledelayedexpansion

rem === Config ===
set "REPO=C:\SHOWMIDGET\TIEMPOSWEB"
set "PY=python"  rem o py si así lo usás

cd /d "%REPO%" || (echo [ERROR] No se pudo entrar a %REPO% & exit /b 1)

echo.
echo === Repo: %REPO% ^| Rama: main ===
git status -s

rem 1) Generar/actualizar JSONs y manifiestos
echo.
echo [INFO] Ejecutando: %PY% process_pdfs.py
%PY% process_pdfs.py
if errorlevel 1 (
  echo [ATENCION] process_pdfs.py devolvio errorlevel distinto de 0. Revisar la salida arriba. Se detiene el script.
  exit /b 1
)

rem 2) Preparar commit
echo.
echo [INFO] Preparando commit...
git add -A

rem Si no hay cambios, no falla
git diff --cached --quiet
if errorlevel 1 (
  for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set FECHA=%%c-%%b-%%a
  for /f "tokens=1-2 delims=: " %%a in ('time /t') do set HORA=%%a%%b
  git commit -m "[auto] actualizar jsons y manifiestos %FECHA% %HORA%"
) else (
  echo [INFO] No hay cambios para commitear.
)

rem 3) Empujar SIEMPRE local -> remoto (pisa remoto con --force-with-lease)
echo.
echo [INFO] Sincronizando con GitHub (local -> remoto)...
git push --force-with-lease origin main
if errorlevel 1 (
  echo [ERROR] No se pudo pushear. Verificar red/credenciales o rama protegida.
  exit /b 1
)

echo.
echo [OK] Listo.
exit /b 0
