import os
from typing import Dict

MESSAGES: Dict[str, Dict[str, str]] = {
    "tr": {
        "lang_name": "Turkce",
        "app_title": "Telegram Medya Aktarici (Linux ve Windows)",
        "menu_title": "ANA KONTROL MENUSU",
        "menu_prompt": "Lutfen yapmak istediginiz islemin numarasini secin:",
        "menu_live": "[1] Canli Izleme Modu (Live Monitor - Yeni medyalari aninda aktarir)",
        "menu_history": "[2] Gecmis Medyalari Tara ve Aktar (History - Konudaki tum medyalari ceker)",
        "menu_list_topics": "[3] Kaynak Kanaldaki Konulari (Topic) Listele",
        "menu_interactive": "[4] Secmeli Aktarim Modu (Interactive - Listeden secerek)",
        "menu_retry": "[5] Basarisiz / Yarim Kalan Islemleri Tekrar Dene",
        "menu_status": "[6] Durum ve Istatistik Raporu",
        "menu_wizard": "[7] Ayarlari Duzenle (Kurulum Sihirbazi)",
        "menu_web": "[8] Web Kontrol Panelini Baslat (Tarayicidan Yonetim)",
        "menu_lang": "[9] Dil Secimi / Language Selection (TR / EN)",
        "menu_exit": "[0] Cikis",
        "choice_prompt": "Seciminiz: ",
        "live_started": "[BILGI] Canli izleme modu baslatildi. Yeni medyalar bekleniyor... (Cikmak icin Ctrl+C)",
        "history_started": "[BILGI] Gecmis tarama modu baslatildi",
        "interactive_title": "SECMELI MEDYA AKTARIM MODU",
        "topic_list_title": "KAYNAK KANAL KONU (TOPIC) LISTESI",
        "media_detected": "[TESPIT EDILDI] Medya: [Kanal: {title}]{topic} [Msg #{msg_id}]",
        "media_skipped": "[ATLANDI] Bu medya daha once basariyla aktarilmis (Tekrar indirmek icin --force kullanin).",
        "download_started": "[INDIRILIYOR] ({type}) [Msg #{msg_id}]",
        "download_complete": "[TAMAMLANDI] Indirme: {name}",
        "download_failed": "[HATA] Medya indirilemedi veya filtreye takildi.",
        "upload_started": "[YUKLENIYOR] ({type}) [Hedef: {title}]",
        "upload_complete": "[BASARILI] Hedef Kanala Aktarildi (Yeni Msg ID: #{msg_id})",
        "upload_failed": "[HATA] Hedef kanala yukleme basarisiz oldu.",
        "flood_wait": "[BEKLEME] Telegram hiz siniri. {sec} saniye bekleniyor...",
        "retry_attempt": "[TEKRAR] Deneme {current}/{max}: {error}",
        "stats_title": "TELEGRAM MEDYA AKTARICI ISTATISTIKLERI",
        "stats_total": "Toplam Islenen Kayit  : {total}",
        "stats_completed": "Basariyla Tamamlanan   : {completed}",
        "stats_failed": "Basarisiz / Hatali     : {failed}",
        "stats_pending": "Bekleyen / Indirilen   : {pending}",
        "stats_transferred": "Toplam Aktarilan Veri  : {mb:.2f} MB",
        "press_enter": "Devam etmek icin ENTER tusuna basin...",
        "goodbye": "Gule gule!",
        "video": "Video",
        "photo": "Fotograf",
        "type_all": "Tum Medyalar (Video ve Fotograf)",
        "type_video_only": "Yalnizca Video",
        "type_photo_only": "Yalnizca Fotograf",
    },
    "en": {
        "lang_name": "English",
        "app_title": "Telegram Media Syncer (Linux & Windows)",
        "menu_title": "MAIN CONTROL MENU",
        "menu_prompt": "Please select an option number:",
        "menu_live": "[1] Live Monitor Mode (Monitors and syncs new media instantly)",
        "menu_history": "[2] Batch History Sync (Syncs all past media in topic/channel)",
        "menu_list_topics": "[3] List Source Channel Forum Topics",
        "menu_interactive": "[4] Interactive Selector Mode (Select media from list)",
        "menu_retry": "[5] Retry Failed / Interrupted Media",
        "menu_status": "[6] Status and Statistics Report",
        "menu_wizard": "[7] Edit Settings (Setup Wizard)",
        "menu_web": "[8] Start Web Control Dashboard (Browser Management)",
        "menu_lang": "[9] Dil Secimi / Language Selection (TR / EN)",
        "menu_exit": "[0] Exit",
        "choice_prompt": "Your choice: ",
        "live_started": "[INFO] Live monitoring started. Waiting for new media... (Press Ctrl+C to exit)",
        "history_started": "[INFO] Batch history sync started",
        "interactive_title": "INTERACTIVE MEDIA SELECTOR",
        "topic_list_title": "SOURCE CHANNEL FORUM TOPICS",
        "media_detected": "[DETECTED] Media: [Channel: {title}]{topic} [Msg #{msg_id}]",
        "media_skipped": "[SKIPPED] This media was already synced (Use --force to re-download).",
        "download_started": "[DOWNLOADING] ({type}) [Msg #{msg_id}]",
        "download_complete": "[DONE] Download complete: {name}",
        "download_failed": "[ERROR] Media download failed or filtered out.",
        "upload_started": "[UPLOADING] ({type}) [Target: {title}]",
        "upload_complete": "[SUCCESS] Uploaded to target channel (New Msg ID: #{msg_id})",
        "upload_failed": "[ERROR] Target upload failed.",
        "flood_wait": "[FLOODWAIT] Telegram rate limit. Waiting for {sec} seconds...",
        "retry_attempt": "[RETRY] Attempt {current}/{max}: {error}",
        "stats_title": "TELEGRAM MEDIA SYNCER STATISTICS",
        "stats_total": "Total Processed Records: {total}",
        "stats_completed": "Successfully Completed : {completed}",
        "stats_failed": "Failed / Errors        : {failed}",
        "stats_pending": "Pending / Downloaded   : {pending}",
        "stats_transferred": "Total Data Transferred : {mb:.2f} MB",
        "press_enter": "Press ENTER to continue...",
        "goodbye": "Goodbye!",
        "video": "Video",
        "photo": "Photo",
        "type_all": "All Media (Video and Photo)",
        "type_video_only": "Video Only",
        "type_photo_only": "Photo Only",
    }
}


def get_active_language() -> str:
    """Aktif dili döner (Varsayılan: .env içindeki LANGUAGE veya 'tr')."""
    return os.getenv("LANGUAGE", "tr").lower().strip()


def t(key: str, lang: str = None, **kwargs) -> str:
    """Belirtilen anahtar ve dilde metni formatlayarak döner."""
    if not lang:
        lang = get_active_language()
    if lang not in MESSAGES:
        lang = "tr"
    
    text = MESSAGES[lang].get(key, MESSAGES["en"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
