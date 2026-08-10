@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

title Instalar University Study System

set "PYTHON_CMD="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD goto no_python

echo.
echo [1/4] Actualizando pip...
%PYTHON_CMD% -m pip install --upgrade pip
if errorlevel 1 goto error

echo.
echo [2/4] Instalando dependencias completas...
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto error

echo.
echo [3/4] Instalando Chromium para Playwright...
%PYTHON_CMD% -m playwright install chromium
if errorlevel 1 goto error

echo.
echo [4/4] Verificando entorno...
%PYTHON_CMD% -m pip check
if errorlevel 1 goto error
%PYTHON_CMD% scripts\setup_env.py check
if errorlevel 1 goto error

echo.
echo ==============================================
echo University Study System listo para usar.
echo Ya podes ejecutar INICIAR-STUDY.bat.
echo ==============================================
echo.
pause
goto end

:no_python
echo.
echo ERROR: Se necesita Python 3.10 o superior.
echo Instala una version actual de Python y habilita "Add Python to PATH".
echo.
pause
goto end

:error
echo.
echo ERROR: La instalacion no pudo completarse.
echo Revisa el mensaje anterior y vuelve a ejecutar INSTALAR-STUDY.bat.
echo.
pause

:end
endlocal
