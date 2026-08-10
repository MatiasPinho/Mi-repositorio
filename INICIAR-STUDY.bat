@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

title University Study System

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        py -3 study.py
        if errorlevel 1 goto error
        goto end
    )
)

where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        python study.py
        if errorlevel 1 goto error
        goto end
    )
)

echo.
echo ERROR: Se necesita Python 3.10 o superior.
echo Instala una version actual de Python y habilita "Add Python to PATH".
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
