# 🚀 Telegram Medya (Video & Fotoğraf) İndirici ve Aktarıcı (Debian / Pardus Linux)

Telegram kanallarından ve gruplarından (içerik kopyalama/indirme yasağı olan **kısıtlı kanallar dahil**) videoları ve fotoğrafları otomatik veya seçmeli olarak indiren, hedef kanala (varsa **Forum/Topic** başlığına) aktaran, kesintilerde otomatik tekrar deneyen ve aynı medyaları mükerrer işlemeyen tam teşekküllü Python uygulamasıdır.

---

## 🌟 Öne Çıkan Yetenekler

- 📸 **Video & Fotoğraf Desteği:** İster hem video hem fotoğrafları (`MEDIA_TYPE=all`), ister yalnızca videoları (`MEDIA_TYPE=video`), isterseniz de yalnızca fotoğrafları (`MEDIA_TYPE=photo`) aktarın.
- 🔒 **Kısıtlı / Yasaklı Kanal Desteği (Restricted Content):** Telegram Bot API'nin aksine MTProto istemcisi (Telethon) kullandığından, kopyalama yasağı (`noforwards` / `protected_content`) bulunan kanallardaki video ve fotoğrafları doğrudan stream ederek kaydeder ve aktarır.
- 💬 **Gelişmiş Forum & Topic (Konu) Filtreleme:** 
  - **Kaynak Topic Filtresi:** Kaynak kanaldaki tüm konuları değil, yalnızca istediğiniz belirli Topic/Konu ID'lerindeki medyaları indirme imkanı.
  - **Telegram Web URL Desteği:** Telegram Web'deki URL'de görünen `&thread=...` şeklindeki 64-bit ID'leri otomatik algılar ve gerçek Topic ID'sine normalize eder.
  - **Hedef Topic Yükleme:** Medyaları hedef kanaldaki istediğiniz Topic/Konu başlığına otomatik yükler.
- 🗄️ **SQLite Tabanlı Mükerrer Engelleme:** İndirilen ve yüklenen her medyanın mesaj ID'si, dosya benzersiz kimliği (`file_unique_id`) ve boyutu veritabanında tutulur. Aynı medya asla iki kez indirilmez veya yüklenmez.
- 🔄 **Akıllı Hata Yakalama & FloodWait:** Ağ kopmalarında veya Telegram hız sınırlarında (`FloodWaitError`) otomatik bekler ve logaritmik artan aralıklarla (exponential backoff) tekrar dener.
- 🎬 **FFmpeg Küçük Resim (Thumbnail) & Metadata:** Videolardan otomatik kapak resmi üretir, süre ve çözünürlük bilgilerini Telegram video oynatıcısına uygun formatta aktarır.
- 🧹 **Otomatik Disk Temizliği:** Yüklenen medyalar diskte yer kaplamaması için aktarım bittikten sonra yerel diskten otomatik olarak silinir.
- 🐧 **Pardus & Debian Tam Uyumluluk:** Tek komut kurulum betiği (`install.sh`) ve 7/24 arka planda çalıştırabilmeniz için `systemd` servis şablonu içerir.

---

## 📋 Gereksinimler

- **İşletim Sistemi:** Pardus Linux, Debian 10/11/12, Ubuntu 20.04+ (veya herhangi bir Linux dağıtımı)
- **Python:** Python 3.8 veya üzeri
- **Sistem Paketleri:** `ffmpeg`, `git`, `python3-venv` (Kurulum betiği otomatik yükler)

---

## 🛠️ Pardus / Debian Linux Kurulum Rehberi

Debian veya Pardus bilgisayarınızda terminali açın ve şu adımları izleyin:

### 1. Projeyi Klonlayın
```bash
git clone https://github.com/Ngethemba/telegram-video-syncer.git
cd telegram-video-syncer
```

### 2. Kurulum Betiğini Çalıştırın
Kurulum betiği gerekli sistem paketlerini (`ffmpeg`, `python3-venv`), sanal ortamı (`venv`) ve Python bağımlılıklarını otomatik kuracaktır:
```bash
chmod +x install.sh run.sh
./install.sh
```

---

## ⚙️ Yapılandırma (.env Dosyası)

`install.sh` otomatik olarak bir `.env` dosyası oluşturur. Dosyayı düzenlemek için:
```bash
nano .env
```

### Telegram API Bilgilerini Alma:
1. [my.telegram.org](https://my.telegram.org) adresine gidin ve Telegram numaranızla giriş yapın.
2. **"API development tools"** bölümüne tıklayın.
3. Yeni bir uygulama tanımlayarak `api_id` ve `api_hash` değerlerinizi alın.

### `.env` Değişkenleri:

| Değişken | Açıklama | Örnek Değer |
| :--- | :--- | :--- |
| `TELEGRAM_API_ID` | Telegram API ID | `12345678` |
| `TELEGRAM_API_HASH` | Telegram API Hash | `0123456789abcdef0123456789abcdef` |
| `TELEGRAM_PHONE` | Hesabınızın telefon numarası | `+905551234567` |
| `MEDIA_TYPE` | İndirilecek medya türü (`all`, `video`, `photo`) | `all` |
| `SOURCE_CHANNELS` | İzlenecek kaynak kanal(lar) (virgülle ayrılmış) | `-1001234567890, @kaynak_kanal` |
| `SOURCE_TOPIC_IDS` | Kaynakta Yalnızca Belirli Topic(ler)i İndir (Boşsa tümü) | `5914` veya `5914, 1234` |
| `TARGET_CHANNEL` | Medyaların yükleneceği hedef kanal | `-1009876543210` veya `@hedef_kanal` |
| `TARGET_TOPIC_ID` | Hedef kanal Forum ise yüklenecek Konu/Topic ID | `5914` (Ana kanal için `0`) |
| `AUTO_CLEANUP` | Yüklenen medyaları yerel diskten sil | `true` |
| `MAX_FILE_SIZE_MB` | Maksimum dosya boyutu (MB) (0 = sınırsız) | `0` |
| `MIN_DURATION_SECONDS` | Minimum video süresi (saniye) (0 = sınırsız) | `0` |
| `MAX_RETRIES` | Başarısız işlemlerde tekrar deneme sayısı | `5` |
| `DELAY_BETWEEN_UPLOADS` | İki yükleme arası bekleme (saniye) | `3` |

---

## 🚀 Kullanım ve Çalıştırma Modları

### 1. Medya Türü Seçerek Çalıştırma (`--type`)
```bash
# Hem video hem fotoğrafları aktar (Varsayılan):
./run.sh live --type all

# Yalnızca videoları aktar:
./run.sh live --type video

# Yalnızca fotoğrafları aktar:
./run.sh live --type photo
```

### 2. Canlı İzleme Modu (Live Monitor)
Kaynak kanalları dinler ve yeni gelen medyaları hedefe aktarır:
```bash
./run.sh live
```

### 3. Geçmiş Mesaj Tarama Modu (Batch History)
Kaynak kanaldaki geçmiş mesajları tarar ve henüz aktarılmamış tüm medyaları aktarır:
```bash
# Seçili konudaki TÜM geçmiş medyaları tara:
./run.sh history

# Yalnızca belirli bir konunun geçmiş fotoğraflarını tara:
./run.sh history --topic 5914 --type photo

# Daha önce indirilmiş olanları da sıfırdan tekrar indir:
./run.sh history --force
```

### 4. Konuları Listeleme (`list-topics`)
Kaynak kanaldaki tüm konu başlıklarını ve Topic ID'lerini listeler:
```bash
./run.sh list-topics
```

### 5. Seçmeli Aktarım Modu (Interactive Mode)
Kaynak kanaldaki son video ve fotoğrafları listeler, terminalden seçtiğiniz medyaları aktarır:
```bash
./run.sh interactive
```

### 6. Başarısızları Yeniden Deneme (Retry Failed)
Daha önce ağ kesintisi gibi nedenlerle tamamlanamamış medyaları tekrar sıraya alır:
```bash
./run.sh retry-failed
```

### 7. Durum ve İstatistik Raporu (Status)
Veritabanında kayıtlı aktarımların özetini görüntüler:
```bash
./run.sh status
```

---

## 🔄 7/24 Arka Planda Çalıştırma (Systemd Servisi)

Pardus veya Debian sunucunuzda uygulamanın sürekli (arka planda) çalışması için `systemd` servisi olarak tanımlayabilirsiniz:

1. `telegram-syncer.service` dosyasındaki dizin yollarını kontrol edin:
   ```bash
   nano telegram-syncer.service
   ```
2. Servis dosyasını sistem dizinine kopyalayın:
   ```bash
   sudo cp telegram-syncer.service /etc/systemd/system/
   ```
3. Servisi aktifleştirin ve başlatın:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable telegram-syncer
   sudo systemctl start telegram-syncer
   ```
4. Canlı logları izlemek için:
   ```bash
   journalctl -u telegram-syncer -f
   ```
