@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Charlie Assistant

chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
) else (
    set "PY_EXE=python"
)

echo ============================================================
echo Starting Charlie Voice Assistant...
echo Using Python: !PY_EXE!
echo ============================================================

"!PY_EXE!" main.py %*
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% NEQ 0 (
    echo.
    echo ============================================================
    echo Charlie exited with status code %EXIT_CODE%.
    echo Check logs\charlie.log for detailed error logs.
    echo ============================================================
    echo.
    pause
)
