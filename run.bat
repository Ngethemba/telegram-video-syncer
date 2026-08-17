@echo off
REM ==============================================================================
REM Telegram Media Syncer - Windows Runner Script
REM ==============================================================================

setlocal

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [WARNING] Virtual environment not found. Running with global Python...
)

if "%~1"=="" (
    python app_menu.py
) else (
    python main.py %*
)

endlocal
