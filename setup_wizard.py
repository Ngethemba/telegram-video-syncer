import os
import sys
from pathlib import Path
from colorama import Fore, Style, init

init(autoreset=True)

ENV_PATH = Path(".env")


def select_language_prompt() -> str:
    """Dil seçimi ekranı."""
    print(Fore.CYAN + "\n==================================================================")
    print(Fore.CYAN + "Language Selection / Dil Secimi")
    print(Fore.CYAN + "==================================================================")
    print("  [1] Turkce (TR)")
    print("  [2] English (EN)")
    choice = input(Fore.YELLOW + "Seciminiz / Your choice [1]: " + Fore.WHITE).strip()
    if choice == "2":
        return "en"
    return "tr"


def run_setup_wizard(initial_lang: str = None):
    """Setup wizard without nano, supporting English and Turkish."""
    lang = initial_lang or select_language_prompt()

    print(Fore.CYAN + "\n" + "=" * 65)
    if lang == "tr":
        print(Fore.CYAN + "TELEGRAM MEDYA AKTARICI - KOLAY KURULUM SIHIRBAZI")
        print(Fore.CYAN + "=" * 65)
        print(Fore.YELLOW + "Bu sihirbaz gerekli ayarlari adim adim sorarak .env dosyasina kaydeder.\n")
    else:
        print(Fore.CYAN + "TELEGRAM MEDIA SYNCER - SETUP WIZARD")
        print(Fore.CYAN + "=" * 65)
        print(Fore.YELLOW + "This wizard configures all required settings into the .env file.\n")

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
    if lang == "tr":
        print(Fore.GREEN + "1. Telegram API ID (my.telegram.org):")
    else:
        print(Fore.GREEN + "1. Telegram API ID (from my.telegram.org):")
    api_id = input(f"   API ID [{default_api_id}]: ").strip() or default_api_id
    while not api_id.isdigit():
        print(Fore.RED + "   [ERROR] API ID must contain only numbers.")
        api_id = input("   API ID: ").strip()

    # 2. API HASH
    default_api_hash = current_values.get("TELEGRAM_API_HASH", "")
    if lang == "tr":
        print(Fore.GREEN + "\n2. Telegram API Hash (my.telegram.org):")
    else:
        print(Fore.GREEN + "\n2. Telegram API Hash (from my.telegram.org):")
    api_hash = input(f"   API HASH [{default_api_hash}]: ").strip() or default_api_hash
    while len(api_hash) < 10:
        print(Fore.RED + "   [ERROR] Invalid API Hash.")
        api_hash = input("   API HASH: ").strip()

    # 3. PHONE NUMBER
    default_phone = current_values.get("TELEGRAM_PHONE", "+90")
    if lang == "tr":
        print(Fore.GREEN + "\n3. Telegram Telefon Numarasi (Ulke kodu ile, ornek: +905551234567):")
    else:
        print(Fore.GREEN + "\n3. Telegram Phone Number (with country code, e.g.: +1234567890):")
    phone = input(f"   Phone [{default_phone}]: ").strip() or default_phone

    # 4. MEDIA TYPE
    default_media_type = current_values.get("MEDIA_TYPE", "all")
    if lang == "tr":
        print(Fore.GREEN + "\n4. Indirilecek Medya Turu:")
        print("   [1] all   - Hem Video hem Fotograflar (Onerilen)")
        print("   [2] video - Yalnizca Videolar")
        print("   [3] photo - Yalnizca Fotograflar")
    else:
        print(Fore.GREEN + "\n4. Media Type to Sync:")
        print("   [1] all   - Both Videos and Photos (Recommended)")
        print("   [2] video - Videos Only")
        print("   [3] photo - Photos Only")
    type_choice = input(f"   Choice (1/2/3) [{default_media_type}]: ").strip()
    if type_choice == "1":
        media_type = "all"
    elif type_choice == "2":
        media_type = "video"
    elif type_choice == "3":
        media_type = "photo"
    else:
        media_type = default_media_type if default_media_type in ("all", "video", "photo") else "all"

    # 5. SOURCE CHANNELS
    default_source = current_values.get("SOURCE_CHANNELS", "")
    if lang == "tr":
        print(Fore.GREEN + "\n5. Kaynak Kanal ID veya Kullanici Adi (Ornek: -1001234567890 veya @kaynak_kanal):")
    else:
        print(Fore.GREEN + "\n5. Source Channel ID or Username (e.g. -1001234567890 or @source_channel):")
    source_channels = input(f"   Source [{default_source}]: ").strip() or default_source

    # 6. TARGET CHANNEL
    default_target = current_values.get("TARGET_CHANNEL", "")
    if lang == "tr":
        print(Fore.GREEN + "\n6. Hedef Kanal ID veya Kullanici Adi (Ornek: -1009876543210 veya @hedef_kanal):")
    else:
        print(Fore.GREEN + "\n6. Target Channel ID or Username (e.g. -1009876543210 or @target_channel):")
    target_channel = input(f"   Target [{default_target}]: ").strip() or default_target

    # 7. SOURCE TOPIC FILTER
    default_source_topics = current_values.get("SOURCE_TOPIC_IDS", "")
    if lang == "tr":
        print(Fore.GREEN + "\n7. Kaynak Kanal Konu (Topic) Filtresi (Opsiyonel):")
        print(Fore.LIGHTBLACK_EX + "   (Belirli konulari indirmek icin Topic ID yazin, tumu icin bos birakin)")
    else:
        print(Fore.GREEN + "\n7. Source Forum Topic Filter (Optional):")
        print(Fore.LIGHTBLACK_EX + "   (Enter Topic ID to filter specific topic, leave empty for all)")
    source_topic_ids = input(f"   Source Topic ID [{default_source_topics}]: ").strip() or default_source_topics

    # 8. TARGET TOPIC ID
    default_target_topic = current_values.get("TARGET_TOPIC_ID", "0")
    if lang == "tr":
        print(Fore.GREEN + "\n8. Hedef Kanal Forum ise Yuklenecek Topic ID (Opsiyonel, ana kanal icin 0):")
    else:
        print(Fore.GREEN + "\n8. Target Forum Topic ID (Optional, 0 for main/general):")
    target_topic_id = input(f"   Target Topic ID [{default_target_topic}]: ").strip() or default_target_topic

    # 9. AUTO CLEANUP
    if lang == "tr":
        print(Fore.GREEN + "\n9. Yuklenen medyalar yerel diskten otomatik silinsin mi?")
        print("   [1] Evet (Yer tasarrufu saglar)")
        print("   [2] Hayir (downloads/ klasorunde sakla)")
    else:
        print(Fore.GREEN + "\n9. Auto delete local media after successful upload?")
        print("   [1] Yes (Conserve disk space)")
        print("   [2] No (Keep in downloads/ directory)")
    cleanup_choice = input("   Choice [1]: ").strip()
    auto_cleanup = "false" if cleanup_choice == "2" else "true"

    env_content = f"""# ==============================================================================
# Telegram Media Syncer Configuration File
# Generated by Setup Wizard
# ==============================================================================

LANGUAGE={lang}

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
    if lang == "tr":
        print(Fore.GREEN + "[BASARILI] Ayarlar '.env' dosyasina kaydedildi!")
    else:
        print(Fore.GREEN + "[SUCCESS] Settings successfully saved to '.env'!")
    print(Fore.GREEN + "=" * 65 + "\n")


if __name__ == "__main__":
    run_setup_wizard()
