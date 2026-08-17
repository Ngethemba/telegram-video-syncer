# 🚀 Telegram Video İndirici & Aktarıcı (Debian / Pardus Linux Uyumlu)

Telegram kanallarından ve gruplarından (içerik kopyalama/indirme yasağı olan **kısıtlı kanallar dahil**) videoları otomatik veya seçmeli olarak indiren, hedef kanala (varsa **Forum/Topic** başlığına) aktaran, kesintilerde otomatik tekrar deneyen ve aynı videoları mükerrer işlemeyen tam teşekküllü Python uygulamasıdır.

---

## 🌟 Öne Çıkan Yetenekler

- 🔒 **Kısıtlı / Yasaklı Kanal Desteği (Restricted Content):** Telegram Bot API'nin aksine MTProto istemcisi (Telethon) kullandığından, kopyalama yasağı (`noforwards` / `protected_content`) bulunan kanallardaki videoları doğrudan stream ederek kaydeder ve aktarır.
- 💬 **Gelişmiş Forum & Topic (Konu) Filtreleme:** 
  - **Kaynak Topic Filtresi:** Kaynak kanaldaki tüm konuları değil, yalnızca istediğiniz belirli Topic/Konu ID'lerindeki videoları indirme imkanı.
  - **Telegram Web URL Desteği:** Telegram Web'deki URL'de görünen `&thread=4294973210` şeklindeki 64-bit ID'leri otomatik algılar ve gerçek Topic ID'sine (örn: `5914`) normalize eder.
  - **Hedef Topic Yükleme:** Videoları hedef kanaldaki istediğiniz Topic/Konu başlığına otomatik yükler.
- 🗄️ **SQLite Tabanlı Mükerrer Engelleme:** İndirilen ve yüklenen her videonun mesaj ID'si, dosya benzersiz kimliği (`file_unique_id`) ve boyutu veritabanında tutulur. Aynı video asla iki kez indirilmez veya yüklenmez.
- 🔄 **Akıllı Hata Yakalama & FloodWait:** Ağ kopmalarında veya Telegram hız sınırlarında (`FloodWaitError`) otomatik bekler ve logaritmik artan aralıklarla (exponential backoff) tekrar dener.
- 🎬 **FFmpeg Küçük Resim (Thumbnail) & Metadata:** Videolardan otomatik kapak resmi üretir, süre ve çözünürlük bilgilerini Telegram video oynatıcısına uygun formatta aktarır.
- 🧹 **Otomatik Disk Temizliği:** Yüklenen videolar diskte yer kaplamaması için aktarım bittikten sonra yerel diskten otomatik olarak silinir.
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
| `SOURCE_CHANNELS` | İzlenecek kaynak kanal(lar) (virgülle ayrılmış) | `-1001234567890, @kaynak_kanal` |
| `SOURCE_TOPIC_IDS` | **Kaynakta Yalnızca Belirli Topic(ler)i İndir** (Boşsa tümü) | `4294973210` veya `5914, 123` |
| `TARGET_CHANNEL` | Videoların yükleneceği hedef kanal | `-1009876543210` veya `@hedef_kanal` |
| `TARGET_TOPIC_ID` | Hedef kanal Forum ise yüklenecek Konu/Topic ID | `4294973210` veya `5` (Ana kanal için `0`) |
| `AUTO_CLEANUP` | Yüklenen videoları diskten sil | `true` |
| `MAX_FILE_SIZE_MB` | Maksimum dosya boyutu (MB) (0 = sınırsız) | `0` |
| `MIN_DURATION_SECONDS` | Minimum video süresi (saniye) (0 = sınırsız) | `0` |
| `MAX_RETRIES` | Başarısız işlemlerde tekrar deneme sayısı | `5` |
| `DELAY_BETWEEN_UPLOADS` | İki yükleme arası bekleme (saniye) | `3` |

---

## 🎯 Kaynak Topic (Konu) Filtreleme Nasıl Yapılır?

Kaynak kanalda birden fazla topic/konu varsa ve siz yalnızca belirli bir konudaki videoları almak istiyorsanız:

1. **Yöntem 1: `.env` Dosyasından Sabitleme**
   - `.env` dosyanızı açın:
     ```bash
     SOURCE_TOPIC_IDS=4294973210
     ```
   *(Telegram Web linkindeki `&thread=4294973210` sayısını doğrudan yapıştırabilirsiniz, uygulama bunu otomatik olarak tanır).*

2. **Yöntem 2: Komut Satırından Anlık Belirtme (`--topic`)**
   - Canlı izleme:
     ```bash
     ./run.sh live --topic 4294973210
     ```
   - Geçmiş tarama (Yalnızca bu konudaki videoları tarar):
     ```bash
     ./run.sh history --topic 4294973210 --limit 50
     ```
   - Seçmeli aktarım:
     ```bash
     ./run.sh interactive --topic 4294973210
     ```

---

## 🚀 Kullanım ve Çalıştırma Modları

### 1. Canlı İzleme Modu (Live Monitor)
Kaynak kanalları sürekli dinler. Kanala yeni bir video atıldığı anda anında indirir ve hedef kanala aktarır.
```bash
./run.sh live
```

### 2. Geçmiş Mesaj Tarama Modu (Batch History)
Kaynak kanaldaki geçmiş mesajları tarar ve henüz aktarılmamış tüm videoları sırayla aktarır.
```bash
# Son 100 mesajı tara:
./run.sh history --limit 100

# Kaynaktaki TÜM geçmiş videoları tara:
./run.sh history --limit 0
```

### 3. Seçmeli Aktarım Modu (Interactive Mode)
Kaynak kanaldaki son videoları başlık, konu, süre ve boyutlarıyla listeler. Terminal üzerinden istediğiniz videoları seçmenizi sağlar (örn: `1,3,5` veya `1-10` veya `hepsi`).
```bash
./run.sh interactive
```

### 4. Başarısızları Yeniden Deneme (Retry Failed)
Daha önce ağ kesintisi gibi nedenlerle tamamlanamamış videoları tekrar sıraya alır:
```bash
./run.sh retry-failed
```

### 5. Durum ve İstatistik Raporu (Status)
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

---

## 💡 İpuçları ve Sıkça Sorulan Sorular

- **Telegram Web'deki `thread=4294973210` nedir?**
  - Telegram Web K, konu (thread) ID'lerini 64-bit formatında gösterir (`4294967296 + 5914`). Uygulamamız bu sayıyı otomatik olarak gerçek konu ID'sine (`5914`) dönüştürür. URL'de gördüğünüz sayıyı aynen kopyalayıp kullanabilirsiniz.
- **Kanal ID'sini nasıl öğrenebilirim?**
  - Telegram Web'de kanalı açtığınızda URL adresindeki `https://web.telegram.org/k/#-100XXXXXXXXXX` ifadesinde yer alan `-100` ile başlayan sayı kanal ID'nizdir.
  - Veya `@username` kullanıcı adını doğrudan `.env` içinde kullanabilirsiniz.
- **Kısıtlı kanaldan indirirken banlanır mıyım?**
  - Uygulama resmi Telegram MTProto istemci protokolünü kullanır ve FloodWait koruması içerir. Ancak çok yüksek hacimli işlemlerde `DELAY_BETWEEN_UPLOADS` süresini 3-5 saniye tutmanız tavsiye edilir.
