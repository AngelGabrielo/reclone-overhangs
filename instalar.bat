@echo off
setlocal
REM Instalacion local con doble clic. Es seguro repetirla: si ya existe una base
REM de datos, no la toca. Todo queda dentro de esta carpeta (.venv y .pg).
REM NOTA: este archivo debe ser ASCII (sin tildes); cmd lee mal los .bat con
REM caracteres no ASCII. La salida de Python si usa UTF-8 gracias a chcp.
cd /d "%~dp0"
chcp 65001 >nul

echo ============================================================
echo  Instalacion local de Reclone - solo en este equipo
echo ============================================================
echo.

REM 1) Buscar Python del sistema
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    echo [X ] No encontre Python. Instalalo desde https://www.python.org/downloads/
    echo      y marca "Add python.exe to PATH". Luego vuelve a abrir este archivo.
    goto :error
)

REM 2) Comprobar requisitos: Python 3.10 o superior, PostgreSQL y permisos
%PY% scripts\verificar_entorno.py
if errorlevel 1 goto :error
echo.

REM 3) Entorno de Python propio del proyecto
if not exist ".venv\Scripts\python.exe" (
    echo Creando el entorno de Python...
    %PY% -m venv .venv
    if errorlevel 1 goto :error
)

REM 4) Librerias. Si falla, se reintenta con los certificados de Windows por si
REM    un antivirus intercepta la conexion segura.
echo Instalando las librerias, puede tardar unos minutos...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo Reintentando con los certificados de Windows...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --use-feature=truststore -r requirements.txt
    if errorlevel 1 goto :error
)

REM 5) Base de datos local: solo si todavia no existe
if exist ".pg\datos\PG_VERSION" goto :base_existente

echo.
echo Creando la base de datos local y cargando los datos del taller...
".venv\Scripts\python.exe" -m reclone demo
if errorlevel 1 goto :error
echo.
echo Cargando las partes de Reclone...
".venv\Scripts\python.exe" -m reclone importar-reclone
if errorlevel 1 goto :error
goto :fin

:base_existente
echo.
echo Ya existe una base de datos local: no se modifica.
".venv\Scripts\python.exe" -m reclone db iniciar
if errorlevel 1 goto :error

:fin
echo.
echo ============================================================
echo  Instalacion terminada.
echo  Para usar la aplicacion haz doble clic en iniciar.bat
echo ============================================================
pause
exit /b 0

:error
echo.
echo La instalacion no se completo. Revisa el mensaje de arriba.
pause
exit /b 1
