#!/usr/bin/env bash
# ==============================================================================
# Telegram Video İndirici & Aktarıcı - Pardus / Debian Kurulum Betiği
# ==============================================================================

set -e

# Renkler
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}🐧 Pardus / Debian Telegram Video Syncer Kurulumu 🐧${NC}"
echo -e "${CYAN}====================================================${NC}"

# 1. Root / Sudo kontrolü ve Sistem Paketlerinin Yüklenmesi
echo -e "\n${YELLOW}[1/4] Sistem bağımlılıkları (Python, FFmpeg, Git) kontrol ediliyor...${NC}"

if command -v apt-get &> /dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-pip python3-venv ffmpeg git
else
    echo -e "${YELLOW}apt-get bulunamadı, sistem paketlerinin önceden kurulu olduğu varsayılıyor.${NC}"
fi

# 2. Python Sanal Ortamının (venv) Oluşturulması
echo -e "\n${YELLOW}[2/4] Python sanal ortamı (venv) oluşturuluyor...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Sanal ortam (venv) başarıyla oluşturuldu.${NC}"
else
    echo -e "${GREEN}✓ Mevcut sanal ortam (venv) bulundu.${NC}"
fi

# 3. Python Bağımlılıklarının Kurulması
echo -e "\n${YELLOW}[3/4] Python kütüphaneleri yükleniyor (Telethon, FFmpeg helper vb.)...${NC}"
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ Tüm Python bağımlılıkları başarıyla yüklendi.${NC}"

# 4. Yapılandırma Dosyası (.env) Kontrolü
echo -e "\n${YELLOW}[4/4] Yapılandırma dosyası (.env) hazırlanıyor...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ '.env' dosyası '.env.example' şablonundan oluşturuldu.${NC}"
    echo -e "${YELLOW}⚠️ LÜTFEN '.env' DOSYASINI DÜZENLEYEREK TELEGRAM API VE KANAL BİLGİLERİNİZİ GİRİN:${NC}"
    echo -e "   nano .env"
else
    echo -e "${GREEN}✓ '.env' dosyası zaten mevcut.${NC}"
fi

# Çalıştırma izinlerini ver
chmod +x run.sh || true

echo -e "\n${GREEN}====================================================${NC}"
echo -e "${GREEN}🎉 KURULUM BAŞARIYLA TAMAMLANDI! 🎉${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "Kullanım Adımları:"
echo -e " 1. Ayarları düzenleyin       : ${CYAN}nano .env${NC}"
echo -e " 2. Canlı Modda Başlatın      : ${CYAN}./run.sh live${NC}"
echo -e " 3. Geçmiş Videoları Aktarın  : ${CYAN}./run.sh history --limit 50${NC}"
echo -e " 4. Seçmeli Modda Başlatın    : ${CYAN}./run.sh interactive${NC}"
echo -e " 5. İstatistikleri İnceleyin  : ${CYAN}./run.sh status${NC}"
echo -e "====================================================\n"
