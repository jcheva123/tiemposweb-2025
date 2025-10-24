@echo off
REM Ejecuta el parser de posiciones para un PDF y genera posiciones.json
REM Editá RUTAS según tu proyecto.

set PYTHON=python
set PDF_IN=FECHA10.pdf
set OUT_JSON=posiciones.json

%PYTHON% parse_posiciones.py "%PDF_IN%" --out "%OUT_JSON%" --pretty
if errorlevel 1 (
  echo Fallo el parseo. Verifica dependencias (pdftotext o pdfminer.six).
  pause
) else (
  echo OK. Archivo generado: %OUT_JSON%
  pause
)
