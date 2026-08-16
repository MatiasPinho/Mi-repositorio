@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

title Instalar University Study System

set "BASE_PYTHON="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 set "BASE_PYTHON=py -3"
)

if not defined BASE_PYTHON (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
        if not errorlevel 1 set "BASE_PYTHON=python"
    )
)

if not defined BASE_PYTHON goto no_python

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

echo.
echo [1/6] Preparando entorno virtual aislado...
if not exist "%VENV_PYTHON%" (
    %BASE_PYTHON% -m venv .venv
    if errorlevel 1 goto error
)
"%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 goto broken_venv

echo.
echo [2/6] Actualizando pip dentro de .venv...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto error

echo.
echo [3/6] Instalando dependencias completas dentro de .venv...
"%VENV_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto error

echo.
echo [4/6] Instalando Chromium para Playwright...
"%VENV_PYTHON%" -m playwright install chromium
if errorlevel 1 goto error

echo.
echo [5/6] Verificando entorno aislado...
"%VENV_PYTHON%" -m pip check
if errorlevel 1 goto error
"%VENV_PYTHON%" scripts\setup_env.py check
if errorlevel 1 goto error

echo.
echo [6/6] Configurando OpenCode y el MCP local...
"%VENV_PYTHON%" scripts\configure_opencode.py
if errorlevel 1 goto error

echo.
echo ==============================================
echo University Study System listo para usar.
echo Dependencias aisladas en .venv.
echo OpenCode configurado para university-study.
echo Ya podes ejecutar INICIAR-STUDY.bat.
echo ==============================================
echo.
pause
goto end

:broken_venv
echo.
echo ERROR: La carpeta .venv existe pero no contiene un Python valido.
echo Borra la carpeta .venv y vuelve a ejecutar INSTALAR-STUDY.bat.
echo.
pause
goto end

:no_python
echo.
echo ERROR: Se necesita Python 3.10 o superior para crear .venv.
echo Instala una version actual de Python y habilita "Add Python to PATH".
echo.
pause
goto end

:error
echo.
echo ERROR: La instalacion aislada no pudo completarse.
echo Revisa el mensaje anterior y vuelve a ejecutar INSTALAR-STUDY.bat.
echo.
pause

:end
endlocal
