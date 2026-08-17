@echo off
REM ==============================================================================
REM Telegram Media Syncer - Windows Installation Script
REM ==============================================================================

echo ====================================================
echo Telegram Media Syncer - Windows Installation
echo ====================================================

REM 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://www.python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

REM 2. Create Virtual Environment
echo [1/3] Creating virtual environment (venv)...
if not exist "venv" (
    python -m venv venv
    echo [OK] Virtual environment created.
) else (
    echo [OK] Existing virtual environment found.
)

REM 3. Install Requirements
echo [2/3] Installing Python dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo [OK] Dependencies installed successfully.

REM 4. Setup Configuration
echo [3/3] Checking configuration (.env)...
if not exist ".env" (
    copy .env.example .env >nul
    echo [OK] Created .env from .env.example template.
) else (
    echo [OK] .env file already exists.
)

echo.
echo ====================================================
echo Installation Complete!
echo ====================================================
echo You can start the application by running: run.bat
echo ====================================================
echo.
pause
