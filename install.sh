#!/usr/bin/env bash
# ==============================================================================
# Telegram Media Syncer - Linux Kurulum Betigi
# ==============================================================================

set -e

# Renkler
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}Telegram Media Syncer - Linux Kurulumu${NC}"
echo -e "${CYAN}====================================================${NC}"

# 1. Paket Yoneticisi ve Bagimliliklar
echo -e "\n${YELLOW}[1/4] Sistem bagimliliklari (Python, FFmpeg, Git) kontrol ediliyor...${NC}"

if command -v apt-get &> /dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-pip python3-venv ffmpeg git
elif command -v dnf &> /dev/null; then
    sudo dnf install -y python3 python3-pip ffmpeg git
elif command -v pacman &> /dev/null; then
    sudo pacman -Sy --noconfirm python python-pip ffmpeg git
else
    echo -e "${YELLOW}Paket yoneticisi bulunamadi, sistem paketlerinin kurulu oldugu varsayiliyor.${NC}"
fi

# 2. Python Sanal Ortami
echo -e "\n${YELLOW}[2/4] Python sanal ortami (venv) olusturuluyor...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}[OK] Sanal ortam (venv) basariyla olusturuldu.${NC}"
else
    echo -e "${GREEN}[OK] Mevcut sanal ortam (venv) bulundu.${NC}"
fi

# 3. Bagimliliklar
echo -e "\n${YELLOW}[3/4] Python kutuphaneleri yukleniyor...${NC}"
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}[OK] Tum Python bagimliliklari basariyla yuklendi.${NC}"

# 4. Yapilandirma Dosyasi
echo -e "\n${YELLOW}[4/4] Yapilandirma dosyasi (.env) kontrol ediliyor...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}[OK] .env dosyasi .env.example sablonundan olusturuldu.${NC}"
else
    echo -e "${GREEN}[OK] .env dosyasi zaten mevcut.${NC}"
fi

# Calistirma izinleri
chmod +x run.sh || true

echo -e "\n${GREEN}====================================================${NC}"
echo -e "${GREEN}Kurulum Basariyla Tamamlandi!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "Uygulamayi baslatmak icin: ${CYAN}./run.sh${NC}"
echo -e "====================================================\n"
