@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   LocalToolkit Windows Build Script
echo ========================================================
echo.

cd /d "%~dp0"

:: Activate virtual environment if present
if exist ".venv\Scripts\activate.bat" (
    echo Activating .venv virtual environment...
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    echo Activating venv virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Using current Python environment...
)

:: Ensure PyInstaller is installed
echo Checking PyInstaller...
python -m pip install --quiet pyinstaller

:: Clean previous build outputs
echo Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist\LocalToolkit" rmdir /s /q "dist\LocalToolkit"

:: Run PyInstaller
echo.
echo Building LocalToolkit in --onedir mode...
python -m PyInstaller build.spec --clean

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Build failed! Review errors above.
    exit /b %ERRORLEVEL%
)

echo.
echo ========================================================
echo   BUILD SUCCESSFUL!
echo ========================================================
echo Standalone directory:
echo   %~dp0dist\LocalToolkit
echo.
echo One-click launcher:
echo   %~dp0dist\LocalToolkit\LocalToolkit.exe
echo ========================================================
echo.

