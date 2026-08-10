@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

title University Study System

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

rem Fail early instead of discovering a missing browser/dependency during /resumen.
%PYTHON_CMD% scripts\setup_env.py check >nul 2>&1
if errorlevel 1 goto incomplete_setup

%PYTHON_CMD% study.py
if errorlevel 1 goto error
goto end

:no_python
echo.
echo ERROR: Se necesita Python 3.10 o superior.
echo Instala una version actual de Python y habilita "Add Python to PATH".
echo.
pause
goto end

:incomplete_setup
echo.
echo ERROR: El entorno de University Study System esta incompleto.
echo Ejecuta INSTALAR-STUDY.bat una vez para instalar dependencias y Chromium.
echo.
%PYTHON_CMD% scripts\setup_env.py check
 echo.
pause
goto end

:error
echo.
echo El sistema termino con un error.
echo Revisa el mensaje anterior.
echo.
pause

:end
endlocal
