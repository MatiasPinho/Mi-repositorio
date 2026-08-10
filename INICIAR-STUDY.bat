@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

title University Study System

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" goto incomplete_setup

rem Fail early instead of discovering a missing browser/dependency during a long study run.
"%VENV_PYTHON%" scripts\setup_env.py check >nul 2>&1
if errorlevel 1 goto incomplete_setup

"%VENV_PYTHON%" study.py
if errorlevel 1 goto error
goto end

:incomplete_setup
echo.
echo ERROR: El entorno aislado de University Study System esta incompleto.
echo Ejecuta INSTALAR-STUDY.bat para crear/reparar .venv e instalar Chromium.
echo.
if exist "%VENV_PYTHON%" "%VENV_PYTHON%" scripts\setup_env.py check
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
