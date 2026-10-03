@echo off
REM Inicia PostgreSQL local y la interfaz web (doble clic).
cd /d "%~dp0"
".venv\Scripts\python.exe" -m reclone db iniciar
if errorlevel 1 (
    pause
    exit /b 1
)
start "" http://127.0.0.1:8501
".venv\Scripts\python.exe" -m streamlit run app.py
