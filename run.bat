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
) else if "%~1"=="web" (
    python web_ui.py
) else if "%~1"=="update" (
    echo [INFO] Checking and applying updates from GitHub...
    python -c "from update_manager import UpdateManager; res = UpdateManager.apply_update(); print(res.get('message', res))"
) else (
    python main.py %*
)

endlocal
