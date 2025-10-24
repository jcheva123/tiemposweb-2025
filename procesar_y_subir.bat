@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ========= CONFIG =========
set "REPO=C:\SHOWMIDGET\TIEMPOSWEB"
set "PYTHON_EXE=python"          REM Cambiar si no tenes python en PATH. Ej: C:\Users\TuUsuario\AppData\Local\Programs\Python\Python311\python.exe
set "BRANCH=main"
set "FORCE_FLAG=--force-with-lease"  REM Para aplastar sin mirar: --force
set "COMMIT_MSG=Auto: procesar PDFs y subir resultados"
REM ==========================

REM (OPCIONAL) Pedir admin si necesitás permisos elevados en esa carpeta.
REM Descomenta el bloque siguiente si hace falta:
REM net session >nul 2>&1
REM if %errorlevel% neq 0 (
REM   echo Solicitando permisos de administrador...
REM   powershell -Command "Start-Process '%~f0' -Verb RunAs"
REM   exit /b
REM )

echo.
echo === Repo: %REPO% ^| Rama: %BRANCH% ===
echo.

REM 1) Ir al repo
cd /d "%REPO%" 2>nul || (
  echo [ERROR] No existe la ruta del repo: "%REPO%"
  pause
  exit /b 1
)

REM 2) Verificar git
git --version >nul 2>&1 || (
  echo [ERROR] No se encontro 'git' en el PATH.
  pause
  exit /b 1
)

REM 3) Asegurar rama seleccionada (crea/reset al commit actual)
git checkout -B "%BRANCH%" || (
  echo [ERROR] No se pudo cambiar/crear la rama "%BRANCH%".
  pause
  exit /b 1
)

REM 4) Ejecutar el procesamiento de PDFs (esto tambien intenta ejecutar subir_jsons si esta disponible)
echo.
echo [INFO] Ejecutando: %PYTHON_EXE% process_pdfs.py
"%PYTHON_EXE%" process_pdfs.py
if errorlevel 1 (
  echo [ATENCION] process_pdfs.py devolvio errorlevel distinto de 0.
  echo           Revisar la salida arriba. Se detiene el script.
  pause
  exit /b 1
)

REM 5) Preparar commit si hay cambios
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
  echo [INFO] No hay cambios para commitear; igual se forzara el push (por si no existe rama remota).
)

REM 6) Verificar remoto
git remote get-url origin >nul 2>&1 || (
  echo [ERROR] No existe remoto 'origin'. Agregalo con:
  echo        git remote add origin https://github.com/usuario/repositorio.git
  pause
  exit /b 1
)

REM 7) Push forzado
echo.
echo [INFO] Enviando a origin/%BRANCH% con %FORCE_FLAG% ...
git push -u %FORCE_FLAG% origin "%BRANCH%" || (
  echo [ERROR] Fallo el push forzado.
  pause
  exit /b 1
)

echo.
echo [OK] Todo listo: PDFs procesados y push forzado a origin/%BRANCH%.
echo.
pause
exit /b 0
