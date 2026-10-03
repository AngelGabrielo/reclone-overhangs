@echo off
REM Inicia PostgreSQL local y la aplicacion web (doble clic).
REM Al cerrar esta ventana (X), con Ctrl+C o con "Apagar todo" en la aplicacion,
REM se apagan tambien la aplicacion y la base de datos.
REM NOTA: archivo ASCII y con saltos CRLF (ver README).
cd /d "%~dp0"
title Reclone - cierra esta ventana para apagar todo
".venv\Scripts\python.exe" -m reclone app
if errorlevel 1 pause
