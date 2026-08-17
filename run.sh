#!/usr/bin/env bash
# ==============================================================================
# Telegram Media Syncer Runner (Linux)
# ==============================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "[WARNING] Virtual environment not found. Please run './install.sh' first."
    exit 1
fi

if [ $# -eq 0 ]; then
    python3 app_menu.py
else
    python3 main.py "$@"
fi
