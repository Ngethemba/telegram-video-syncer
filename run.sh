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
    echo "[WARNING] Virtual environment not found. Running install.sh..."
    chmod +x install.sh 2>/dev/null || true
    ./install.sh
    source venv/bin/activate 2>/dev/null || true
fi

if [ $# -eq 0 ]; then
    python3 app_menu.py
elif [ "$1" == "web" ] || [ "$1" == "webui" ] || [ "$1" == "gui" ]; then
    python3 web_ui.py
else
    python3 main.py "$@"
fi
