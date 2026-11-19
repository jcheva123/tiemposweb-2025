@echo off
setlocal
cd /d "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo Falta preparar Python. Abri 1-Preparar.cmd del kit de la notebook.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" publicar_fecha.py %*
set "RESULTADO=%ERRORLEVEL%"
pause
exit /b %RESULTADO%
