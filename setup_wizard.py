import os
import sys
from pathlib import Path
from colorama import Fore, Style, init

init(autoreset=True)

ENV_PATH = Path(".env")


def run_setup_wizard():
    """Kullanıcıya nano kullandırmadan adım adım .env dosyasını oluşturan sihirbaz."""
    print(Fore.CYAN + "\n" + "=" * 65)
    print(Fore.CYAN + "🧙 TELEGRAM MEDYA AKTARICI - KOLAY KURULUM SİHİRBAZI 🧙")
    print(Fore.CYAN + "=" * 65)
    print(Fore.YELLOW + "Bu sihirbaz, gerekli tüm ayarları adım adım sorarak otomatik kaydedecektir.\n")

    # Mevcut değerleri oku (varsa)
    current_values = {}
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    current_values[k.strip()] = v.strip()

    # 1. API ID
    default_api_id = current_values.get("TELEGRAM_API_ID", "")
    print(Fore.GREEN + "1. Telegram API ID (my.telegram.org adresinden aldığınız sayı):")
    api_id = input(f"   API ID [{default_api_id}]: ").strip() or default_api_id
    while not api_id.isdigit():
        print(Fore.RED + "   ❌ API ID yalnızca rakamlardan oluşmalıdır.")
        api_id = input("   API ID: ").strip()

    # 2. API HASH
    default_api_hash = current_values.get("TELEGRAM_API_HASH", "")
    print(Fore.GREEN + "\n2. Telegram API Hash (my.telegram.org adresindeki 32 haneli kod):")
    api_hash = input(f"   API HASH [{default_api_hash}]: ").strip() or default_api_hash
    while len(api_hash) < 10:
        print(Fore.RED + "   ❌ API Hash geçersiz görünüyor.")
        api_hash = input("   API HASH: ").strip()

    # 3. TELEFON NUMARASI
    default_phone = current_values.get("TELEGRAM_PHONE", "+90")
    print(Fore.GREEN + "\n3. Telegram Telefon Numaranız (Ülke kodu ile birlikte, örn: +905551234567):")
    phone = input(f"   Telefon Numarası [{default_phone}]: ").strip() or default_phone

    # 4. MEDYA TÜRÜ
    default_media_type = current_values.get("MEDIA_TYPE", "all")
    print(Fore.GREEN + "\n4. İndirilecek Medya Türü:")
    print("   [1] all   - Hem Video hem Fotoğraflar (Önerilen)")
    print("   [2] video - Yalnızca Videolar")
    print("   [3] photo - Yalnızca Fotoğraflar")
    type_choice = input(f"   Seçiminiz (1/2/3) [{default_media_type}]: ").strip()
    if type_choice == "1":
        media_type = "all"
    elif type_choice == "2":
        media_type = "video"
    elif type_choice == "3":
        media_type = "photo"
    else:
        media_type = default_media_type if default_media_type in ("all", "video", "photo") else "all"

    # 5. KAYNAK KANAL(LAR)
    default_source = current_values.get("SOURCE_CHANNELS", "")
    print(Fore.GREEN + "\n5. Kaynak Kanal ID'si veya Kullanıcı Adı (Medyanın indirileceği yer):")
    print(Fore.LIGHTBLACK_EX + "   (Örn: -1001234567890 veya @kaynak_kanal)")
    source_channels = input(f"   Kaynak Kanal [{default_source}]: ").strip() or default_source

    # 6. HEDEF KANAL
    default_target = current_values.get("TARGET_CHANNEL", "")
    print(Fore.GREEN + "\n6. Hedef Kanal ID'si veya Kullanıcı Adı (Medyanın yükleneceği yer):")
    print(Fore.LIGHTBLACK_EX + "   (Örn: -1009876543210 veya @hedef_kanal)")
    target_channel = input(f"   Hedef Kanal [{default_target}]: ").strip() or default_target

    # 7. KAYNAK TOPIC FILTRESI (OPSIYONEL)
    default_source_topics = current_values.get("SOURCE_TOPIC_IDS", "")
    print(Fore.GREEN + "\n7. Kaynak Kanal Topic (Konu) Filtresi (Opsiyonel):")
    print(Fore.LIGHTBLACK_EX + "   (Belirli konuları indirmek için Topic ID veya linkteki uzun sayıyı yazın, tümü için boş bırakın)")
    source_topic_ids = input(f"   Kaynak Topic ID [{default_source_topics}]: ").strip() or default_source_topics

    # 8. HEDEF TOPIC ID (OPSIYONEL)
    default_target_topic = current_values.get("TARGET_TOPIC_ID", "0")
    print(Fore.GREEN + "\n8. Hedef Kanal Forum ise Yüklenecek Topic ID (Opsiyonel):")
    print(Fore.LIGHTBLACK_EX + "   (Ana kanala yüklemek için 0 veya boş bırakın)")
    target_topic_id = input(f"   Hedef Topic ID [{default_target_topic}]: ").strip() or default_target_topic

    # 9. OTOMATİK DİSK TEMİZLİĞİ
    print(Fore.GREEN + "\n9. Yüklenen medyalar diskte yer kaplamaması için otomatik silinsin mi?")
    print("   [1] Evet (Önerilen - Yer tasarrufu sağlar)")
    print("   [2] Hayır (İndirilen dosyalar downloads/ klasöründe kalsın)")
    cleanup_choice = input("   Seçiminiz (1/2) [1]: ").strip()
    auto_cleanup = "false" if cleanup_choice == "2" else "true"

    # .env dosyasını oluştur
    env_content = f"""# ==============================================================================
# Telegram Medya İndirici & Aktarıcı Yapılandırma Dosyası
# Kolay Kurulum Sihirbazı Tarafından Oluşturuldu
# ==============================================================================

TELEGRAM_API_ID={api_id}
TELEGRAM_API_HASH={api_hash}
TELEGRAM_PHONE={phone}
SESSION_NAME=telegram_syncer_session

MEDIA_TYPE={media_type}

SOURCE_CHANNELS={source_channels}
SOURCE_TOPIC_IDS={source_topic_ids}

TARGET_CHANNEL={target_channel}
TARGET_TOPIC_ID={target_topic_id}

DOWNLOAD_DIR=downloads
AUTO_CLEANUP={auto_cleanup}
MAX_FILE_SIZE_MB=0
MIN_DURATION_SECONDS=0
MAX_RETRIES=5
RETRY_DELAY_SECONDS=5
DELAY_BETWEEN_UPLOADS=3
KEEP_ORIGINAL_CAPTION=true
CUSTOM_CAPTION_PREFIX=
CUSTOM_CAPTION_SUFFIX=
"""

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(env_content)

    print(Fore.GREEN + "\n" + "=" * 65)
    print(Fore.GREEN + "🎉 HARİKA! Ayarlarınız '.env' dosyasına başarıyla kaydedildi! 🎉")
    print(Fore.GREEN + "=" * 65 + "\n")


if __name__ == "__main__":
    run_setup_wizard()
