#!/usr/bin/env bash
# ==============================================================================
# Telegram Video Syncer Hızlı Başlatıcı (Pardus / Debian)
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

# Uygulamayı çalıştır ve argümanları ilet
python3 main.py "$@"
