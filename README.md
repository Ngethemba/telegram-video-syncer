# Telegram Media Syncer (Linux & Windows)

Telegram channel and group media downloader and uploader (sync tool) with restricted content support, topic/forum support, duplicate tracking via SQLite, automatic retries, and cross-platform compatibility (Linux & Windows).

---

## Language / Dil Secimi
- [Turkce Dokumantasyon](#turkce-dokumantasyon)
- [English Documentation](#english-documentation)

---

<a name="turkce-dokumantasyon"></a>
# Turkce Dokumantasyon

## Genel Bakis
Bu uygulama; Telegram kanallarindan veya gruplarindan (icerik indirme/kopyalama yasagi olan kisitli kanallar dahil) videolari ve fotograflari otomatik veya secmeli olarak indiren, hedef kanala (varsa Forum/Topic basligina) aktaran, kesintilerde otomatik tekrar deneyen ve SQLite ile ayni medyalari mukerrer indirmeyen cok yonlu bir aracdir.

## Temel Ozellikler
- **Video ve Fotograf Destegi:** Hem videolari hem fotograflari (MEDIA_TYPE=all), yalnizca videolari (MEDIA_TYPE=video) veya yalnizca fotograflari (MEDIA_TYPE=photo) senkronize edebilir.
- **Kisitli / Yasakli Kanal Destegi:** MTProto istemcisi (Telethon) kullandigindan, korumali (noforwards / protected_content) kanallardaki medyalari stream ederek indirebilir.
- **Forum ve Topic (Konu) Destegi:** Kaynak kanaldaki belirli bir konuyu (Topic ID) filtreleyebilir veya hedef kanaldaki belirli bir konuya yukleme yapabilir.
- **Mukerrer Kontrolu (SQLite):** Islenen her medyanin benzersiz kimligi (file_unique_id) veritabaninda saklanir. Dosyalar diskten silinse bile ayni medya tekrar indirilmez.
- **Akilli Hata Yonetimi ve FloodWait:** Ag kopmalarinda veya Telegram hiz sinirlarinda otomatik bekler ve logaritmik araliklarla tekrar dener.
- **FFmpeg Kucuk Resim ve Meta Veri:** Videolardan otomatik thumbnail uretir ve Telegram oynaticisina uygun formatta yukler.
- **Otomatik Disk Temizligi:** Yuklenen yerel dosyalar diskte yer kaplamamasi icin islem sonunda otomatik silinir.
- **Linux ve Windows Tam Uyumluluk:** Linux icin bash betikleri (install.sh, run.sh), Windows icin toplu is betikleri (install.bat, run.bat) ve web kontrol paneli icerir.

## Gereksinimler
- Python 3.8 veya uzeri
- FFmpeg ve Git

---

## Kurulum

### Linux Kurulumu
```bash
git clone https://github.com/Ngethemba/telegram-video-syncer.git
cd telegram-video-syncer
chmod +x install.sh run.sh
./install.sh
```

### Windows Kurulumu
1. Repoyu klonlayin veya indirin:
   ```cmd
   git clone https://github.com/Ngethemba/telegram-video-syncer.git
   cd telegram-video-syncer
   ```
2. Kurulum betigini calistirin:
   ```cmd
   install.bat
   ```

---

## Yapilandirma (.env Dosyasi)
`my.telegram.org` adresinden API ID ve API Hash bilgilerinizi aldiktan sonra `.env` dosyasini duzenleyin:

| Degisken | Aciklama | Ornek Deger |
| :--- | :--- | :--- |
| `TELEGRAM_API_ID` | Telegram API ID | `12345678` |
| `TELEGRAM_API_HASH` | Telegram API Hash | `0123456789abcdef0123456789abcdef` |
| `TELEGRAM_PHONE` | Telegram telefon numarasi | `+905551234567` |
| `MEDIA_TYPE` | Medya turu (`all`, `video`, `photo`) | `all` |
| `SOURCE_CHANNELS` | Kaynak kanal(lar) (virgulle ayrilmis) | `-1001234567890, @kaynak_kanal` |
| `SOURCE_TOPIC_IDS` | Kaynakta yalnizca belirli Topic(ler) (Bos = Tumu) | `5914` veya `5914, 1234` |
| `TARGET_CHANNEL` | Hedef kanal ID veya kullanici adi | `-1009876543210` veya `@hedef_kanal` |
| `TARGET_TOPIC_ID` | Hedef kanal Topic ID (Ana kanal = 0) | `5914` |
| `AUTO_CLEANUP` | Yuklenen dosyalari diskten sil | `true` |
| `MAX_FILE_SIZE_MB` | Maksimum dosya boyutu (MB) (0 = sinirsiz) | `0` |
| `MIN_DURATION_SECONDS` | Minimum video suresi (saniye) | `0` |
| `MAX_RETRIES` | Tekrar deneme sayisi | `5` |
| `DELAY_BETWEEN_UPLOADS`| Yuklemeler arasi bekleme suresi (sn) | `3` |

---

## Calistirma Secenekleri

### 1. Interaktif Menuyu Baslatma
- **Linux:** `./run.sh`
- **Windows:** `run.bat`

### 2. Web Kontrol Panelini Baslatma
Tarayiciniz uzerinden grafiksel kontrol paneli acmak icin:
```bash
python3 web_ui.py
```
Tarayicida `http://localhost:5000` adresini acin.

### 3. Komut Satiri Modlari
- **Canli Izleme:** `./run.sh live` (veya Windows: `run.bat live`)
- **Gecmis Medyalari Tara:** `./run.sh history` (veya Windows: `run.bat history`)
- **Yalnizca Fotograflari Tara:** `./run.sh history --type photo`
- **Yalnizca Videolari Tara:** `./run.sh history --type video`
- **Belirli Bir Konuyu Tara:** `./run.sh history --topic 5914`
- **Mukerrer Kontrolunu Atlayip Yeniden Indir:** `./run.sh history --force`
- **Konulari Listele:** `./run.sh list-topics`
- **Secmeli Aktar:** `./run.sh interactive`
- **Istatistikleri Gor:** `./run.sh status`

---

### Linux Systemd Servisi (7/24 Calistirma)
1. `telegram-syncer.service` dosyasindaki yollari kontrol edin.
2. Servisi yukleyin:
   ```bash
   sudo cp telegram-syncer.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now telegram-syncer
   ```
3. Loglari izleyin:
   ```bash
   journalctl -u telegram-syncer -f
   ```

---
---

<a name="english-documentation"></a>
# English Documentation

## Overview
Telegram Media Syncer is a cross-platform tool for Linux and Windows that downloads videos and photos from Telegram channels/groups (including restricted/protected channels where forwarding or saving is disabled), uploads them to a target channel (with forum topic support), prevents duplicates using an SQLite database, and handles network cuts with exponential backoff retries.

## Key Features
- **Video & Photo Syncing:** Sync both videos and photos (`MEDIA_TYPE=all`), videos only (`MEDIA_TYPE=video`), or photos only (`MEDIA_TYPE=photo`).
- **Restricted Channel Support:** Uses the official MTProto User API (Telethon) to stream and save media even if content protection (`noforwards` / `protected_content`) is enabled.
- **Forum & Topic Support:** Filter specific source topics by ID, or route uploads to a designated target forum topic.
- **Duplicate Prevention:** Tracks `file_unique_id` and message IDs in SQLite (`syncer_database.db`). Files will not be re-downloaded even if local files are deleted.
- **Resilience & Rate Limit Handling:** Handles Telegram FloodWait limits and connection drops with exponential backoff retries.
- **FFmpeg Integration:** Generates video thumbnails and extracts duration/dimensions for native video playback.
- **Automatic Cleanup:** Deletes downloaded media locally after successful upload to conserve disk space.
- **Cross-Platform:** Works on Linux (Debian, Ubuntu, Arch, Fedora, etc.) and Windows with native launcher scripts.

## Prerequisites
- Python 3.8+
- FFmpeg and Git

---

## Installation

### Linux Installation
```bash
git clone https://github.com/Ngethemba/telegram-video-syncer.git
cd telegram-video-syncer
chmod +x install.sh run.sh
./install.sh
```

### Windows Installation
1. Clone or download the repository:
   ```cmd
   git clone https://github.com/Ngethemba/telegram-video-syncer.git
   cd telegram-video-syncer
   ```
2. Run the installer:
   ```cmd
   install.bat
   ```

---

## Configuration (.env File)
Obtain your API ID and API Hash from `my.telegram.org` and configure `.env`:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `TELEGRAM_API_ID` | Telegram API ID | `12345678` |
| `TELEGRAM_API_HASH` | Telegram API Hash | `0123456789abcdef0123456789abcdef` |
| `TELEGRAM_PHONE` | Account phone number | `+905551234567` |
| `MEDIA_TYPE` | Media type filter (`all`, `video`, `photo`) | `all` |
| `SOURCE_CHANNELS` | Source channel(s) (comma-separated) | `-1001234567890, @source_channel` |
| `SOURCE_TOPIC_IDS` | Source Topic ID filter (empty = all) | `5914` or `5914, 1234` |
| `TARGET_CHANNEL` | Target channel ID or @username | `-1009876543210` or `@target_channel` |
| `TARGET_TOPIC_ID` | Target forum topic ID (0 = general) | `5914` |
| `AUTO_CLEANUP` | Delete local media after upload | `true` |
| `MAX_FILE_SIZE_MB` | Maximum file size in MB (0 = no limit) | `0` |
| `MIN_DURATION_SECONDS` | Minimum video duration in seconds | `0` |
| `MAX_RETRIES` | Retry attempts on failure | `5` |
| `DELAY_BETWEEN_UPLOADS`| Delay between uploads in seconds | `3` |

---

## Running the Application

### 1. Interactive Control Menu
- **Linux:** `./run.sh`
- **Windows:** `run.bat`

### 2. Web Control Panel
Start the lightweight web UI:
```bash
python3 web_ui.py
```
Open `http://localhost:5000` in your web browser.

### 3. Command-Line Usage
- **Live Monitor:** `./run.sh live` (Windows: `run.bat live`)
- **Batch History Sync:** `./run.sh history` (Windows: `run.bat history`)
- **Sync Photos Only:** `./run.sh history --type photo`
- **Sync Videos Only:** `./run.sh history --type video`
- **Sync Specific Topic:** `./run.sh history --topic 5914`
- **Force Re-download (Bypass Duplicate Check):** `./run.sh history --force`
- **List Channel Topics:** `./run.sh list-topics`
- **Interactive Selector:** `./run.sh interactive`
- **Show Statistics:** `./run.sh status`

---

### Running as a 24/7 Systemd Daemon (Linux)
1. Verify working directory in `telegram-syncer.service`.
2. Enable and start the service:
   ```bash
   sudo cp telegram-syncer.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now telegram-syncer
   ```
3. Inspect logs:
   ```bash
   journalctl -u telegram-syncer -f
   ```
