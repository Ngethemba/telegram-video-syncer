@echo off
REM ==============================================================================
REM Telegram Media Syncer - Windows One-Click Update Script
REM ==============================================================================

echo ==================================================================
echo  Updating Telegram Media Syncer...
echo ==================================================================

echo [1/2] Fetching latest updates from GitHub (git fetch origin main)...
git fetch origin main

echo [2/2] Updating files to latest version (git reset --hard origin/main)...
git reset --hard origin/main

echo.
echo ==================================================================
echo  [SUCCESS] Telegram Media Syncer updated to latest version!
echo ==================================================================
echo.
echo Start web panel: run.bat web
echo Start main menu: run.bat
echo.
