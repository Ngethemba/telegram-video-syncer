#!/usr/bin/env bash
# ==============================================================================
# Telegram Media Syncer - Tek Tikla Otomatik Guncelleme Scripti
# ==============================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "=================================================================="
echo " Telegram Media Syncer Guncelleniyor..."
echo "=================================================================="

echo "[1/3] GitHub uzerinden en son kodlar cekiliyor (git fetch origin main)..."
git fetch origin main

echo "[2/3] Dosyalar en son surume guncelleniyor (git reset --hard origin/main)..."
git reset --hard origin/main

echo "[3/3] Calistirma izinleri ayarlaniyor (chmod +x)..."
chmod +x run.sh install.sh update.sh 2>/dev/null || true

echo ""
echo "=================================================================="
echo " [BASARILI] Telegram Media Syncer basariyla en son surume guncellendi!"
echo " Yeni Surum: $(git rev-parse --short HEAD)"
echo "=================================================================="
echo ""
echo "Web panelini baslatmak icin: ./run.sh web"
echo "Ana menuyu baslatmak icin  : ./run.sh"
echo ""
