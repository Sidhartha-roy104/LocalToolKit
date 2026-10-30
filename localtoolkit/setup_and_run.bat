@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo               LocalToolkit Launcher
echo ===================================================
echo.

:: Detect Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERROR] Python is not installed or not in your PATH.
        echo Please install Python 3.10+ from https://www.python.org/
        echo Make sure to check "Add Python to PATH" during installation.
        echo.
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=py
    )
) else (
    set PYTHON_CMD=python
)

:: Create venv if missing
if not exist "venv" (
    echo [1/3] Creating virtual environment (venv)...
    !PYTHON_CMD! -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate venv
echo [2/3] Activating virtual environment...
call venv\Scripts\activate.bat

:: Install requirements
echo [3/3] Checking and installing dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

:: Start application
echo.
echo Starting LocalToolkit...
echo.
python run.py

pause

