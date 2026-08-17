#!/usr/bin/env bash
# ==============================================================================
# Telegram Medya Aktarıcı Hızlı Başlatıcı (Pardus / Debian)
# ==============================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Sanal ortamı tespit et
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "⚠️ Sanal ortam (venv) bulunamadı. Lütfen önce './install.sh' çalıştırın."
    exit 1
fi

# Eğer hiçbir argüman verilmediyse doğrudan İnteraktif Menüyü aç
if [ $# -eq 0 ]; then
    python3 app_menu.py
else
    python3 main.py "$@"
fi
