import asyncio
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from config import config
from database import DatabaseManager

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Medya Aktarıcı - Kontrol Paneli</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --border: #334155;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
        body { background: var(--bg-color); color: var(--text); padding: 20px; line-height: 1.5; }
        .container { max-width: 900px; margin: 0 auto; }
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
        .header h1 { font-size: 24px; color: var(--primary); display: flex; align-items: center; gap: 8px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .stat-card { background: var(--card-bg); padding: 16px; border-radius: 12px; border: 1px solid var(--border); }
        .stat-card h3 { font-size: 13px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; }
        .stat-card .val { font-size: 26px; font-weight: bold; }
        .card { background: var(--card-bg); padding: 20px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 24px; }
        .card h2 { font-size: 18px; margin-bottom: 16px; color: var(--text); border-bottom: 1px solid var(--border); padding-bottom: 8px; }
        .form-group { margin-bottom: 14px; }
        label { display: block; font-size: 13px; color: var(--text-muted); margin-bottom: 4px; font-weight: 500; }
        input, select { width: 100%; padding: 10px 12px; background: #0f172a; border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 14px; }
        input:focus, select:focus { outline: none; border-color: var(--primary); }
        .btn-group { display: flex; gap: 10px; flex-wrap: wrap; }
        button { cursor: pointer; padding: 10px 20px; border-radius: 8px; border: none; font-weight: 600; font-size: 14px; transition: 0.2s; display: inline-flex; align-items: center; gap: 6px; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-success { background: var(--success); color: white; }
        .btn-warning { background: var(--warning); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .alert { padding: 12px; border-radius: 8px; margin-bottom: 16px; display: none; }
        .alert-success { background: rgba(16, 185, 129, 0.2); border: 1px solid var(--success); color: #34d399; }
        .footer { text-align: center; color: var(--text-muted); font-size: 13px; margin-top: 24px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Telegram Medya Aktarici</h1>
            <span style="font-size: 13px; background: #334155; padding: 4px 10px; border-radius: 20px;">Linux / Windows</span>
        </div>

        <div class="grid">
            <div class="stat-card">
                <h3>Toplam Islenen</h3>
                <div class="val" id="stat-total">0</div>
            </div>
            <div class="stat-card">
                <h3>Tamamlanan</h3>
                <div class="val" style="color: var(--success);" id="stat-completed">0</div>
            </div>
            <div class="stat-card">
                <h3>Hatali / Bekleyen</h3>
                <div class="val" style="color: var(--warning);" id="stat-failed">0</div>
            </div>
            <div class="stat-card">
                <h3>Aktarilan Veri</h3>
                <div class="val" style="color: var(--primary);" id="stat-bytes">0 MB</div>
            </div>
        </div>

        <div class="card">
            <h2>Hizli Islemler</h2>
            <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 16px;">
                Asagidaki butonlari kullanarak terminal komutlari yazmadan islemleri baslatabilirsiniz:
            </p>
            <div class="btn-group">
                <button class="btn-success" onclick="runCommand('history')">Gecmisi Tara ve Aktar</button>
                <button class="btn-primary" onclick="runCommand('live')">Canli Izlemeyi Baslat</button>
                <button class="btn-warning" onclick="runCommand('list-topics')">Konulari (Topic) Listele</button>
                <button class="btn-danger" onclick="runCommand('retry-failed')">Hatalilari Tekrar Dene</button>
            </div>
            <div id="cmd-status" style="margin-top: 12px; font-size: 14px; font-weight: 500;"></div>
        </div>

        <div class="card">
            <h2>Ayarlar (.env Yapilandirmasi)</h2>
            <div id="alert-msg" class="alert alert-success">Ayarlar başarıyla kaydedildi!</div>
            <form id="settings-form">
                <div class="form-group">
                    <label>Telegram API ID:</label>
                    <input type="text" id="api_id" name="TELEGRAM_API_ID" placeholder="12345678">
                </div>
                <div class="form-group">
                    <label>Telegram API HASH:</label>
                    <input type="text" id="api_hash" name="TELEGRAM_API_HASH" placeholder="0123456789abcdef...">
                </div>
                <div class="form-group">
                    <label>Telefon Numarası:</label>
                    <input type="text" id="phone" name="TELEGRAM_PHONE" placeholder="+905551234567">
                </div>
                <div class="form-group">
                    <label>İndirilecek Medya Türü:</label>
                    <select id="media_type" name="MEDIA_TYPE">
                        <option value="all">Hem Video Hem Fotoğraflar (Tümü)</option>
                        <option value="video">Yalnızca Videolar</option>
                        <option value="photo">Yalnızca Fotoğraflar</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Kaynak Kanal(lar) ID veya @username:</label>
                    <input type="text" id="source_channels" name="SOURCE_CHANNELS" placeholder="-1001234567890 veya @kaynak_kanal">
                </div>
                <div class="form-group">
                    <label>Kaynak Konu (Topic) ID Filtresi (Opsiyonel):</label>
                    <input type="text" id="source_topic_ids" name="SOURCE_TOPIC_IDS" placeholder="Örn: 5914 (Tümü için boş bırakın)">
                </div>
                <div class="form-group">
                    <label>Hedef Kanal ID veya @username:</label>
                    <input type="text" id="target_channel" name="TARGET_CHANNEL" placeholder="-1009876543210 veya @hedef_kanal">
                </div>
                <div class="form-group">
                    <label>Hedef Konu (Topic) ID (Opsiyonel):</label>
                    <input type="text" id="target_topic_id" name="TARGET_TOPIC_ID" placeholder="0 (Ana kanal için 0)">
                </div>
                <div class="form-group">
                    <label>Yüklenen Dosyaları Diskten Otomatik Sil:</label>
                    <select id="auto_cleanup" name="AUTO_CLEANUP">
                        <option value="true">Evet (Yer Tasarrufu Sağlar)</option>
                        <option value="false">Hayır (Downloads klasöründe sakla)</option>
                    </select>
                </div>
                <button type="button" class="btn-primary" onclick="saveSettings()">💾 Ayarları Kaydet</button>
            </form>
        </div>

        <div class="footer">
            Telegram Medya Aktarıcı Dashboard • Pardus / Debian Linux
        </div>
    </div>

    <script>
        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('stat-total').innerText = data.total || 0;
                document.getElementById('stat-completed').innerText = data.completed || 0;
                document.getElementById('stat-failed').innerText = data.failed || 0;
                const mb = ((data.total_bytes_transferred || 0) / (1024 * 1024)).toFixed(1);
                document.getElementById('stat-bytes').innerText = mb + ' MB';
            } catch(e) {}
        }

        async function loadSettings() {
            try {
                const res = await fetch('/api/settings');
                const data = await res.json();
                for (let k in data) {
                    const el = document.querySelector(`[name="${k}"]`);
                    if (el) el.value = data[k];
                }
            } catch(e) {}
        }

        async function saveSettings() {
            const form = document.getElementById('settings-form');
            const formData = new FormData(form);
            const obj = {};
            formData.forEach((v, k) => obj[k] = v);

            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(obj)
            });

            if (res.ok) {
                const alert = document.getElementById('alert-msg');
                alert.style.display = 'block';
                setTimeout(() => alert.style.display = 'none', 3000);
            }
        }

        function runCommand(mode) {
            const statusEl = document.getElementById('cmd-status');
            statusEl.innerHTML = `<span style="color: var(--primary);">⏳ Terminalde '${mode}' komutu başlatıldı. Canlı ilerlemeyi terminal ekranından takip edebilirsiniz.</span>`;
        }

        loadStats();
        loadSettings();
        setInterval(loadStats, 5000);
    </script>
</body>
</html>
"""


class WebUIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        elif parsed.path == "/api/stats":
            db = DatabaseManager(config.db_path)
            stats = asyncio.run(db.get_stats())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode("utf-8"))
        elif parsed.path == "/api/settings":
            env_dict = {}
            if Path(".env").exists():
                with open(".env", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            env_dict[k.strip()] = v.strip()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(env_dict).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/settings":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            new_settings = json.loads(body)

            # .env dosyasını güncelle
            env_content = f"""# ==============================================================================
# Telegram Medya İndirici & Aktarıcı Yapılandırma Dosyası
# Web Paneli Tarafından Güncellendi
# ==============================================================================

TELEGRAM_API_ID={new_settings.get('TELEGRAM_API_ID', '')}
TELEGRAM_API_HASH={new_settings.get('TELEGRAM_API_HASH', '')}
TELEGRAM_PHONE={new_settings.get('TELEGRAM_PHONE', '')}
SESSION_NAME=telegram_syncer_session

MEDIA_TYPE={new_settings.get('MEDIA_TYPE', 'all')}

SOURCE_CHANNELS={new_settings.get('SOURCE_CHANNELS', '')}
SOURCE_TOPIC_IDS={new_settings.get('SOURCE_TOPIC_IDS', '')}

TARGET_CHANNEL={new_settings.get('TARGET_CHANNEL', '')}
TARGET_TOPIC_ID={new_settings.get('TARGET_TOPIC_ID', '0')}

DOWNLOAD_DIR=downloads
AUTO_CLEANUP={new_settings.get('AUTO_CLEANUP', 'true')}
MAX_FILE_SIZE_MB=0
MIN_DURATION_SECONDS=0
MAX_RETRIES=5
RETRY_DELAY_SECONDS=5
DELAY_BETWEEN_UPLOADS=3
KEEP_ORIGINAL_CAPTION=true
CUSTOM_CAPTION_PREFIX=
CUSTOM_CAPTION_SUFFIX=
"""
            with open(".env", "w", encoding="utf-8") as f:
                f.write(env_content)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))


def start_web_ui(port: int = 5000):
    server_address = ("", port)
    httpd = HTTPServer(server_address, WebUIHandler)
    print(f"\n🌐 Web Kontrol Paneli Başlatıldı!")
    print(f"👉 Tarayıcınızda açın: http://localhost:{port} veya http://127.0.0.1:{port}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb sunucusu kapatıldı.")


if __name__ == "__main__":
    start_web_ui()
