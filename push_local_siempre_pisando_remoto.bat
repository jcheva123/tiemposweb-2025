@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ======== CONFIGURACION ========
set "REPO=C:\SHOWMIDGET\TIEMPOSWEB"
set "BRANCH=main"
set "COMMIT_MSG=WIP: push forzado (pisar remoto)"
REM FORCE_FLAG: --force-with-lease (recomendado) o --force
set "FORCE_FLAG=--force-with-lease"
REM ================================

REM 1) Chequear git
git --version >nul 2>&1 || (
  echo [ERROR] No se encontro 'git' en el PATH.
  pause
  exit /b 1
)

REM 2) Ir al repo
cd /d "%REPO%" 2>nul || (
  echo [ERROR] No existe la ruta del repo: "%REPO%"
  pause
  exit /b 1
)

echo.
echo === Repo: %REPO% ^| Rama destino: %BRANCH% ===
echo.

REM 3) Asegurar que estamos en una rama llamada %BRANCH%
REM    -B crea o resetea la rama al commit actual
git checkout -B "%BRANCH%" || (
  echo [ERROR] No se pudo cambiar/crear la rama "%BRANCH%".
  pause
  exit /b 1
)

REM 4) Staging y commit si hay cambios
git add -A
git diff --cached --quiet
if errorlevel 1 (
  echo [INFO] Creando commit...
  git commit -m "%COMMIT_MSG%" || (
    echo [ERROR] No se pudo crear el commit.
    pause
    exit /b 1
  )
) else (
  echo [INFO] No hay cambios para commitear. Se forzara el push igual.
)

REM 5) Verificar remoto 'origin'
git remote get-url origin >nul 2>&1 || (
  echo [ERROR] No existe remoto 'origin'.
  echo        Agregalo con:
  echo        git remote add origin https://github.com/usuario/repositorio.git
  pause
  exit /b 1
)

REM 6) Push forzado
echo.
echo [INFO] Enviando a origin/%BRANCH% con %FORCE_FLAG% ...
git push -u %FORCE_FLAG% origin "%BRANCH%" || (
  echo [ERROR] Fallo el push forzado.
  pause
  exit /b 1
)

echo.
echo [OK] Listo: tu version local ahora pisa origin/%BRANCH%.
echo.
pause
exit /b 0
