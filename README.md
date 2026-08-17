# 🚀 Telegram Medya (Video & Fotoğraf) İndirici ve Aktarıcı (Debian / Pardus Linux)

Telegram kanallarından ve gruplarından (içerik kopyalama/indirme yasağı olan **kısıtlı kanallar dahil**) videoları ve fotoğrafları otomatik veya seçmeli olarak indiren, hedef kanala (varsa **Forum/Topic** başlığına) aktaran, kesintilerde otomatik tekrar deneyen ve aynı medyaları mükerrer işlemeyen tam teşekküllü Python uygulamasıdır.

---

## 🌟 Öne Çıkan Yetenekler

- 📱 **Nano Gerektirmeyen Kolay Arayüz:** Kullanıcı dostu interaktif kontrol menüsü, adım adım kurulum sihirbazı ve Web tarayıcı kontrol paneli.
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
- 🐧 **Pardus & Debian Tam Uyumluluk:** Tek komut kurulum betiği (`install.sh`), masaüstü kısayolu (`.desktop`) ve 7/24 arka planda çalıştırma için `systemd` servis şablonu.

---

## 🛠️ Pardus / Debian Hızlı Başlangıç (Tek Komutla Çalıştırın)

Debian veya Pardus bilgisayarınızda terminali açın:

```bash
# 1. Projeyi İndirin
git clone https://github.com/Ngethemba/telegram-video-syncer.git
cd telegram-video-syncer

# 2. Kurulumu Yapın
chmod +x install.sh run.sh
./install.sh

# 3. Uygulamayı Başlatın (İnteraktif Menü Açılır)
./run.sh
```

---

## 📱 Kullanım Seçenekleri

### 1. 🎮 İnteraktif Kontrol Menüsü (Tavsiye Edilen)
Hiçbir karmaşık komutla veya `nano` ile uğraşmadan yalnızca `./run.sh` yazmanız yeterlidir:

```bash
./run.sh
```
Karşınıza gelen renkli Türkçe menüden yapmak istediğiniz işlemin numarasını (1-8) tuşlamanız yeterlidir:
* `[1]` 📡 Canlı İzleme Modu (Yeni medyaları anında aktarır)
* `[2]` 📚 Geçmiş Medyaları Tara & Aktar (Seçili konudaki tüm medyaları çeker)
* `[3]` 📑 Kaynak Kanaldaki Konuları (Topic) Listele
* `[4]` 📋 Seçmeli Aktarım Modu (Listeden tek tek seçerek)
* `[5]` 🔄 Başarısız / Yarım Kalanları Tekrar Dene
* `[6]` 📊 Durum ve İstatistik Raporu
* `[7]` ⚙️ Ayarları Düzenle (Kolay Kurulum Sihirbazı)
* `[8]` 🌐 Web Kontrol Panelini Başlat (Tarayıcıdan Yönetim)

---

### 2. 🌐 Web Kontrol Paneli (Tarayıcıdan Yönetim)
Dilerseniz uygulamayı doğrudan web tarayıcınızdan (Chrome, Firefox vb.) yönetebilirsiniz:

```bash
python3 web_ui.py
```
Tarayıcınızda **`http://localhost:5000`** adresine gidin:
- Tek tıkla ayarları düzenleyip kaydedin.
- Anlık aktarım istatistiklerini grafiksel olarak görün.
- Butonlara basarak indirme ve tarama işlemlerini başlatın.

---

### 3. 🧙 Kolay Kurulum Sihirbazı (Ayarları Değiştirmek İçin)
Ayarları `nano` editörü açmadan, adım adım soru-cevap şeklinde değiştirmek için:
```bash
python3 setup_wizard.py
```

---

### 4. ⚡ Hızlı Terminal Komutları

* **Canlı İzleme:** `./run.sh live`
* **Geçmiş Medyaları Tara:** `./run.sh history`
* **Yalnızca Fotoğrafları Tara:** `./run.sh history --type photo`
* **Yalnızca Videoları Tara:** `./run.sh history --type video`
* **Belirli Bir Konuyu Tara:** `./run.sh history --topic 5914`
* **Önceden İndirilenleri Sıfırdan Tekrar İndir:** `./run.sh history --force`
* **Konuları Listele:** `./run.sh list-topics`
* **Seçmeli Mod:** `./run.sh interactive`

---

## 🔄 7/24 Arka Planda Çalıştırma (Systemd Servisi)

Pardus veya Debian sunucunuzda uygulamanın sürekli (arka planda) çalışması için `systemd` servisi olarak tanımlayabilirsiniz:

1. `telegram-syncer.service` dosyasındaki dizin yollarını kontrol edin.
2. Servis dosyasını sistem dizinine kopyalayın:
   ```bash
   sudo cp telegram-syncer.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable telegram-syncer
   sudo systemctl start telegram-syncer
   ```
3. Canlı logları izlemek için:
   ```bash
   journalctl -u telegram-syncer -f
   ```
