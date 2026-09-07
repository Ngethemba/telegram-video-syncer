import asyncio
import json
import os
import queue
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from config import config, _parse_topic_list, _parse_channel_list
from database import DatabaseManager
from channel_helper import ChannelHelper
from profile_manager import ProfileManager
from update_manager import UpdateManager
from telethon import TelegramClient


class TaskManager:
    """Arka plan islemlerini guvenli sekilde yoneten ve loglari anlik toplayan sinif."""

    def __init__(self):
        self.active_app = None
        self.current_mode = None
        self.worker_thread = None
        self.logs = []
        self.log_counter = 0
        self.lock = threading.RLock()

    def is_running(self) -> bool:
        with self.lock:
            return self.worker_thread is not None and self.worker_thread.is_alive()

    def start_task(self, mode: str, topic: str = "", media_type: str = "", force: bool = False) -> tuple:
        with self.lock:
            if self.worker_thread is not None and self.worker_thread.is_alive():
                return False, "Zaten calisan bir islem var. Lutfen once durdurun."

            # Yapılandırmayı tazele ve doğrula
            try:
                config.validate()
            except ValueError as e:
                err_msg = str(e).replace("\n", " ")
                self._add_log(f"[ERROR] {err_msg}")
                return False, err_msg

            self.current_mode = mode
            self.logs.clear()
            self._add_log(f"[INFO] '{mode}' islemi baslatiliyor...")

            self.worker_thread = threading.Thread(
                target=self._run_async_worker,
                args=(mode, topic, media_type, force),
                daemon=True
            )
            self.worker_thread.start()
            return True, "Baslatildi"

    def _run_async_worker(self, mode: str, topic: str, media_type: str, force: bool):
        import re
        ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        class WebLogger:
            def __init__(self, add_log_fn, orig_stdout):
                self.add_log_fn = add_log_fn
                self.orig_stdout = orig_stdout

            def write(self, msg):
                if msg:
                    for line in msg.splitlines():
                        clean = ANSI_ESCAPE.sub('', line).strip()
                        if clean:
                            # HTTP erişim loglarını canlı konsola yansıtma
                            if "HTTP/1.1\"" in clean or "GET /api/" in clean:
                                continue
                            self.add_log_fn(clean)
                if self.orig_stdout:
                    try:
                        self.orig_stdout.write(msg)
                    except Exception:
                        pass

            def flush(self):
                if self.orig_stdout:
                    try:
                        self.orig_stdout.flush()
                    except Exception:
                        pass

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = WebLogger(self._add_log, old_stdout)
        sys.stderr = WebLogger(self._add_log, old_stderr)

        try:
            loop.run_until_complete(self._execute_app(mode, topic, media_type, force))
        except Exception as ex:
            self._add_log(f"[ERROR] Islem hatasi: {ex}")
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            try:
                loop.close()
            except Exception:
                pass
            with self.lock:
                self.current_mode = None
                self.active_app = None

    async def _execute_app(self, mode: str, topic: str, media_type: str, force: bool):
        config.reload()
        from main import TelegramSyncerApp

        cli_topics = _parse_topic_list(topic) if topic else None
        cli_media = media_type if (media_type and media_type != "all") else None

        app = TelegramSyncerApp(override_topics=cli_topics, override_media_type=cli_media)
        with self.lock:
            self.active_app = app

        await app.initialize(interactive=False)

        if mode == "live":
            await app.run_live_monitor()
        elif mode == "history":
            await app.run_history_sync(limit=0, force=force)
        elif mode == "retry-failed":
            await app.run_retry_failed()
        elif mode == "list-topics":
            await app.list_source_topics()

        try:
            await app.client.disconnect()
        except Exception:
            pass

        self._add_log(f"[TAMAMLANDI / DONE] '{mode}' islemi basariyla bitti!")

    def stop_task(self) -> bool:
        with self.lock:
            if self.active_app:
                self.active_app.stop()
                self._add_log("[WARNING] Islem durduruluyor...")
                return True
            return False

    def _add_log(self, text: str):
        with self.lock:
            timestamp = time.strftime("%H:%M:%S")
            entry = f"[{timestamp}] {text}"
            self.log_counter += 1

            # Progress bar deduplication / in-place updating
            is_progress = ("%" in text or "%|" in text) and ("[DOWNLOAD]" in text or "[UPLOAD]" in text or "B/s" in text)
            if is_progress and self.logs:
                last_seq, last_entry = self.logs[-1]
                if ("[DOWNLOAD]" in last_entry or "[UPLOAD]" in last_entry) and ("%" in last_entry or "%|" in last_entry):
                    self.logs[-1] = (self.log_counter, entry)
                    return

            self.logs.append((self.log_counter, entry))
            if len(self.logs) > 1000:
                self.logs.pop(0)

    def get_logs(self, since: int = 0):
        with self.lock:
            if since <= 0 or since > self.log_counter:
                items = self.logs[-150:] if len(self.logs) > 150 else self.logs
                return [text for _, text in items], self.log_counter

            new_items = [text for seq, text in self.logs if seq > since]
            return new_items, self.log_counter


task_manager = TaskManager()


async def fetch_topics_async():
    """Telegram istemcisini baslatip kaynak kanallardaki konulari ceker."""
    config.reload()
    client = TelegramClient(
        config.session_name,
        config.api_id,
        config.api_hash,
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return {"success": False, "error": "Telegram oturumu acilmamis! Lutfen once terminalden './run.sh' ile giris yapin."}
        helper = ChannelHelper(client)
        results = []

        for src in config.source_channels:
            try:
                info = await helper.get_chat_info(src)
                topics = []
                if info["is_forum"]:
                    raw_topics = await helper.list_forum_topics(info["entity"], limit=100)
                    for t in raw_topics:
                        topics.append({
                            "id": t["id"],
                            "title": t["title"],
                        })
                results.append({
                    "channel_title": info["title"],
                    "channel_id": info["id"],
                    "is_forum": info["is_forum"],
                    "topics": topics,
                })
            except Exception as e:
                results.append({
                    "channel_title": str(src),
                    "channel_id": str(src),
                    "is_forum": False,
                    "topics": [],
                    "error": str(e)
                })

        return {"success": True, "channels": results}
    except Exception as ex:
        return {"success": False, "error": str(ex)}
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Medya Aktarici - Web Dashboard</title>
    <style>
        :root {
            --bg-color: #0b1120;
            --card-bg: #1e293b;
            --terminal-bg: #030712;
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
        .container { max-width: 1000px; margin: 0 auto; }
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
        .header h1 { font-size: 22px; color: var(--primary); display: flex; align-items: center; gap: 8px; font-weight: 700; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .stat-card { background: var(--card-bg); padding: 16px; border-radius: 10px; border: 1px solid var(--border); }
        .stat-card h3 { font-size: 12px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.5px; }
        .stat-card .val { font-size: 24px; font-weight: bold; }
        .card { background: var(--card-bg); padding: 20px; border-radius: 10px; border: 1px solid var(--border); margin-bottom: 24px; }
        .card h2 { font-size: 16px; margin-bottom: 16px; color: var(--text); border-bottom: 1px solid var(--border); padding-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
        .form-group { margin-bottom: 14px; }
        label { display: block; font-size: 13px; color: var(--text-muted); margin-bottom: 4px; font-weight: 500; }
        input, select { width: 100%; padding: 10px 12px; background: #0f172a; border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 14px; }
        input:focus, select:focus { outline: none; border-color: var(--primary); }
        .btn-group { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
        button { cursor: pointer; padding: 9px 18px; border-radius: 6px; border: none; font-weight: 600; font-size: 13px; transition: 0.2s; display: inline-flex; align-items: center; gap: 6px; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover:not(:disabled) { background: var(--primary-hover); }
        .btn-success { background: var(--success); color: white; }
        .btn-warning { background: var(--warning); color: #1e293b; font-weight: bold; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-secondary { background: #334155; color: white; }
        .alert { padding: 12px; border-radius: 6px; margin-bottom: 16px; display: none; font-size: 14px; }
        .alert-success { background: rgba(16, 185, 129, 0.2); border: 1px solid var(--success); color: #34d399; }
        .alert-danger { background: rgba(239, 68, 68, 0.2); border: 1px solid var(--danger); color: #f87171; }
        
        /* Terminal Log Ekranı */
        .terminal-container { background: var(--terminal-bg); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-top: 16px; }
        .terminal-header { background: #1e293b; padding: 8px 14px; font-size: 12px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); }
        .terminal-logs { padding: 14px; height: 350px; overflow-y: auto; font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; color: #a7f3d0; white-space: pre-wrap; word-break: break-all; }
        .terminal-logs .log-error { color: #f87171; }
        .terminal-logs .log-warn { color: #fbbf24; }
        .terminal-logs .log-info { color: #60a5fa; }
        .terminal-logs .log-done { color: #34d399; font-weight: bold; }
        .status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }
        .status-idle { background: #334155; color: #cbd5e1; }
        .status-running { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }

        /* Konu / Topic Tablosu */
        .topic-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        .topic-table th, .topic-table td { padding: 10px 12px; border-bottom: 1px solid var(--border); text-align: left; font-size: 13px; }
        .topic-table th { background: #0f172a; color: var(--text-muted); }
        .topic-table tr:hover { background: #0f172a; }
        .badge-id { background: #334155; padding: 2px 8px; border-radius: 4px; font-family: monospace; font-size: 12px; }
        .footer { text-align: center; color: var(--text-muted); font-size: 13px; margin-top: 24px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <h1>Telegram Medya Aktarici</h1>
                <span class="badge-id" id="top-version-badge" style="font-size: 12px; background: #1e293b; border: 1px solid var(--border);">Surum: Denetleniyor...</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <button class="btn-primary" id="btn-top-check-update" onclick="checkForUpdates()" style="padding: 5px 12px; font-size: 12px;">Guncellemeleri Denetle</button>
                <button class="btn-success" id="btn-top-apply-update" onclick="applyUpdate()" style="display: none; padding: 5px 12px; font-size: 12px; font-weight: bold;">Simdi Guncelle</button>
                <span style="font-size: 12px; background: #334155; padding: 4px 10px; border-radius: 20px;">Web Dashboard</span>
            </div>
        </div>

        <!-- UST GUNCELLEME BILDIRIM BANDI -->
        <div id="top-update-banner" style="display: none; background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; border-radius: 8px; padding: 12px 18px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div>
                    <div style="color: #34d399; font-weight: bold; font-size: 14px;" id="banner-title">Yeni bir guncelleme mevcut!</div>
                    <div style="color: var(--text); font-size: 13px; margin-top: 2px;" id="banner-changelog"></div>
                </div>
                <button class="btn-success" onclick="applyUpdate()" style="padding: 8px 18px; font-size: 13px; font-weight: bold; white-space: nowrap;">
                    Simdi Otomatik Guncelle
                </button>
            </div>
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

        <!-- ISLEM KONTROLU VE CANLI KONSOL -->
        <div class="card">
            <h2>
                <span>Islem Kontrolu ve Canli Konsol</span>
                <span id="app-status-badge" class="status-badge status-idle">DURUM: BEKLEMEDE (IDLE)</span>
            </h2>

            <div id="action-alert" class="alert"></div>
            
            <div class="btn-group" style="margin-bottom: 16px;">
                <button class="btn-success" id="btn-history" onclick="runAction('history')">Gecmisi Tara ve Aktar</button>
                <button class="btn-primary" id="btn-live" onclick="runAction('live')">Canli Izlemeyi Baslat</button>
                <button class="btn-warning" id="btn-topics" onclick="loadTopicsList()">Konulari (Topic) Listele</button>
                <button class="btn-secondary" id="btn-retry" onclick="runAction('retry-failed')">Hatalilari Tekrar Dene</button>
                <button class="btn-secondary" id="btn-action-update" onclick="checkForUpdates()">Guncellemeleri Denetle</button>
                <button class="btn-danger" id="btn-stop" onclick="stopAction()" disabled>Durdur (Stop)</button>
            </div>

            <!-- Parametre Secenekleri -->
            <div style="background: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid var(--border); margin-bottom: 16px; display: flex; gap: 16px; flex-wrap: wrap; align-items: center;">
                <div style="flex: 1; min-width: 160px;">
                    <label style="font-size: 12px;">Secili Topic ID:</label>
                    <input type="text" id="action-topic" placeholder="Orn: 5914 (Bos ise .env gecerli)" style="padding: 6px 10px; font-size: 13px;">
                </div>
                <div style="flex: 1; min-width: 160px;">
                    <label style="font-size: 12px;">Medya Turu:</label>
                    <select id="action-type" style="padding: 6px 10px; font-size: 13px;">
                        <option value="all">Tum Medyalar (Video + Foto)</option>
                        <option value="video">Yalnizca Video</option>
                        <option value="photo">Yalnizca Fotograf</option>
                    </select>
                </div>
                <div style="display: flex; align-items: center; gap: 6px; margin-top: 18px;">
                    <input type="checkbox" id="action-force" style="width: auto;">
                    <label for="action-force" style="margin: 0; font-size: 12px; cursor: pointer;">Mukerrer Kontrolunu Atla (--force)</label>
                </div>
            </div>

            <!-- TOPIC LISTELEME ALANI -->
            <div id="topics-container" style="display: none; margin-bottom: 16px; background: #0f172a; border: 1px solid var(--border); border-radius: 8px; padding: 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <h3 style="font-size: 14px; color: var(--primary);">Kaynak Kanaldaki Konu (Topic) Basliklari</h3>
                    <button class="btn-secondary" onclick="document.getElementById('topics-container').style.display='none'" style="padding: 3px 8px; font-size: 11px;">Kapat</button>
                </div>
                <div id="topics-loading" style="display: none; color: var(--warning); font-size: 13px;">Konular Telegram'dan cekiliyor, lutfen bekleyin...</div>
                <div id="topics-content"></div>
            </div>

            <!-- CANLI TERMINAL KONSOLU -->
            <div class="terminal-container">
                <div class="terminal-header">
                    <span>CANLI KONSOL CIKTISI (LIVE TERMINAL OUTPUT)</span>
                    <button class="btn-secondary" onclick="clearLogs()" style="padding: 3px 10px; font-size: 11px;">Temizle</button>
                </div>
                <div id="terminal" class="terminal-logs">Konsol ciktisi bekleniyor...</div>
            </div>
        </div>

        <!-- PROFIL YONETIMI (DISA / ICE AKTAR) -->
        <div class="card">
            <h2>
                <span>Profil ve Ayar Paylasimi (Disa / Ice Aktar)</span>
            </h2>
            <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 14px;">
                Ayarlarinizi bilgisayarlar arasinda (Laptop, Masaustu vb.) kolayca paylasmak icin profil dosyasi (.json) olarak disa aktarabilir veya baska cihazdan gelen profil dosyasini yukleyebilirsiniz.
            </p>
            <div id="profile-alert" class="alert alert-success"></div>
            
            <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center; background: #0f172a; padding: 14px; border-radius: 6px; border: 1px solid var(--border);">
                <!-- Dışa Aktar -->
                <div>
                    <a href="/api/profile/export" download="telegram_syncer_profile.json" style="text-decoration: none;">
                        <button type="button" class="btn-primary">Profili Disa Aktar (JSON Indir)</button>
                    </a>
                </div>

                <!-- İçe Aktar -->
                <div style="display: flex; align-items: center; gap: 8px;">
                    <input type="file" id="profile-file-input" accept=".json" style="display: none;" onchange="importProfileFile(event)">
                    <button type="button" class="btn-success" onclick="document.getElementById('profile-file-input').click()">Profil Dosyasi Yukle (Ice Aktar)</button>
                </div>

                <!-- Kayıtlı Profiller -->
                <div style="display: flex; align-items: center; gap: 6px; margin-left: auto;">
                    <select id="saved-profiles-select" style="padding: 7px 10px; font-size: 13px; width: auto; min-width: 140px;">
                        <option value="">Kayitli Profiller...</option>
                    </select>
                    <button type="button" class="btn-secondary" style="padding: 7px 12px;" onclick="loadSelectedNamedProfile()">Yukle</button>
                    <button type="button" class="btn-secondary" style="padding: 7px 12px;" onclick="saveCurrentAsNamedProfile()">Farkli Kaydet</button>
                </div>
            </div>
        </div>

        <!-- AYARLAR (.ENV) -->
        <div class="card">
            <h2>Ayarlar (.env Yapilandirmasi)</h2>
            <div id="alert-msg" class="alert alert-success">Ayarlar basariyla kaydedildi!</div>
            <form id="settings-form">
                <div class="form-group">
                    <label>Dil / Language:</label>
                    <select id="language" name="LANGUAGE">
                        <option value="tr">Turkce (TR)</option>
                        <option value="en">English (EN)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Telegram API ID:</label>
                    <input type="text" id="api_id" name="TELEGRAM_API_ID" placeholder="12345678">
                </div>
                <div class="form-group">
                    <label>Telegram API HASH:</label>
                    <input type="text" id="api_hash" name="TELEGRAM_API_HASH" placeholder="0123456789abcdef...">
                </div>
                <div class="form-group">
                    <label>Telefon Numarasi:</label>
                    <input type="text" id="phone" name="TELEGRAM_PHONE" placeholder="+905551234567">
                </div>
                <div class="form-group">
                    <label>Indirilecek Medya Turu:</label>
                    <select id="media_type" name="MEDIA_TYPE">
                        <option value="all">Hem Video Hem Fotograflar (Tumu)</option>
                        <option value="video">Yalnizca Videolar</option>
                        <option value="photo">Yalnizca Fotograflar</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Kaynak Kanal(lar) ID veya @username:</label>
                    <input type="text" id="source_channels" name="SOURCE_CHANNELS" placeholder="-1001234567890 veya @kaynak_kanal">
                </div>
                <div class="form-group">
                    <label>Kaynak Konu (Topic) ID Filtresi (Opsiyonel):</label>
                    <input type="text" id="source_topic_ids" name="SOURCE_TOPIC_IDS" placeholder="Orn: 5914 (Tumu icin bos birakin)">
                </div>
                <div class="form-group">
                    <label>Hedef Kanal ID veya @username:</label>
                    <input type="text" id="target_channel" name="TARGET_CHANNEL" placeholder="-1009876543210 veya @hedef_kanal">
                </div>
                <div class="form-group">
                    <label>Hedef Konu (Topic) ID (Opsiyonel):</label>
                    <input type="text" id="target_topic_id" name="TARGET_TOPIC_ID" placeholder="0 (Ana kanal icin 0)">
                </div>
                <div class="form-group">
                    <label>Yuklenen Dosyalari Diskten Otomatik Sil:</label>
                    <select id="auto_cleanup" name="AUTO_CLEANUP">
                        <option value="true">Evet (Yer Tasarrufu Saglar)</option>
                        <option value="false">Hayir (Downloads klasorunde sakla)</option>
                    </select>
                </div>
                <button type="button" class="btn-primary" onclick="saveSettings()">Ayarlari Kaydet</button>
            </form>
        </div>

        <!-- SISTEM VE GUNCELLEMELER -->
        <div class="card">
            <h2>
                <span>Sistem ve Guncellemeler (GitHub)</span>
                <span id="version-badge" class="badge-id" style="font-size: 12px;">Surum: yukleniyor...</span>
            </h2>
            <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 14px;">
                Uygulamanin yeni surumlerini tek bir tiklama ile kontrol edebilir ve terminale komut girmeden guncelleyebilirsiniz.
            </p>

            <div id="update-alert" class="alert"></div>

            <div style="background: #0f172a; padding: 14px; border-radius: 6px; border: 1px solid var(--border); display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                <button type="button" class="btn-primary" id="btn-check-update" onclick="checkForUpdates()">Guncellemeleri Denetle</button>
                <button type="button" class="btn-success" id="btn-apply-update" style="display: none;" onclick="applyUpdate()">Simdi Otomatik Guncelle</button>
                <span id="update-status-text" style="font-size: 13px; color: var(--text-muted);"></span>
            </div>

            <div id="changelog-container" style="display: none; margin-top: 14px; background: #0b1120; border: 1px solid var(--border); border-radius: 6px; padding: 12px;">
                <div style="font-size: 12px; color: var(--warning); font-weight: bold; margin-bottom: 6px;">YENI SURUM ILE GELECEK DEGISIKLIKLER:</div>
                <ul id="changelog-list" style="padding-left: 20px; font-size: 13px; color: var(--text);"></ul>
            </div>
        </div>

        <div class="footer">
            Telegram Media Syncer Dashboard - Linux and Windows
        </div>
    </div>

    <script>
        let logIndex = 0;
        let isAutoScroll = true;

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

        async function loadSavedProfiles() {
            try {
                const res = await fetch('/api/profile/list');
                const data = await res.json();
                const sel = document.getElementById('saved-profiles-select');
                sel.innerHTML = '<option value="">Kayitli Profiller...</option>';
                if (data.profiles) {
                    data.profiles.forEach(p => {
                        const opt = document.createElement('option');
                        opt.value = p;
                        opt.innerText = p;
                        sel.appendChild(opt);
                    });
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

        async function importProfileFile(event) {
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = async function(e) {
                try {
                    const jsonContent = JSON.parse(e.target.result);
                    const res = await fetch('/api/profile/import', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(jsonContent)
                    });
                    const result = await res.json();
                    if (result.success) {
                        showProfileAlert('Profil basariyla ice aktarildi ve ayarlar guncellendi!');
                        loadSettings();
                    } else {
                        showProfileAlert('Hata: Profil dosyasi uygulanamadi.', true);
                    }
                } catch(err) {
                    showProfileAlert('Gecersiz JSON dosyasi: ' + err, true);
                }
            };
            reader.readAsText(file);
            event.target.value = '';
        }

        async function saveCurrentAsNamedProfile() {
            const name = prompt('Kaydedilecek profil ismi girin (orn: Laptop-Dersler):');
            if (!name) return;
            const res = await fetch('/api/profile/save_named', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name })
            });
            const data = await res.json();
            if (data.success) {
                showProfileAlert(`'${name}' profili basariyla kaydedildi!`);
                loadSavedProfiles();
            }
        }

        async function loadSelectedNamedProfile() {
            const sel = document.getElementById('saved-profiles-select');
            const name = sel.value;
            if (!name) {
                alert('Lutfen listeden bir profil secin.');
                return;
            }
            const res = await fetch('/api/profile/load_named', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name })
            });
            const data = await res.json();
            if (data.success) {
                showProfileAlert(`'${name}' profili yuklendi ve ayarlar guncellendi!`);
                loadSettings();
            }
        }

        function showProfileAlert(msg, isError = false) {
            const el = document.getElementById('profile-alert');
            el.innerText = msg;
            el.className = isError ? 'alert alert-danger' : 'alert alert-success';
            el.style.display = 'block';
            setTimeout(() => el.style.display = 'none', 4000);
        }

        function showActionAlert(msg, isError = false) {
            const el = document.getElementById('action-alert');
            el.innerText = msg;
            el.className = isError ? 'alert alert-danger' : 'alert alert-success';
            el.style.display = 'block';
            setTimeout(() => el.style.display = 'none', 5000);
        }

        async function checkStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                const badge = document.getElementById('app-status-badge');
                const btnStop = document.getElementById('btn-stop');
                const actionBtns = ['btn-history', 'btn-live', 'btn-retry'];

                if (data.running) {
                    badge.className = 'status-badge status-running';
                    badge.innerText = `DURUM: CALISIYOR (${data.mode})`;
                    btnStop.disabled = false;
                    actionBtns.forEach(id => document.getElementById(id).disabled = true);
                } else {
                    badge.className = 'status-badge status-idle';
                    badge.innerText = 'DURUM: BEKLEMEDE (IDLE)';
                    btnStop.disabled = true;
                    actionBtns.forEach(id => document.getElementById(id).disabled = false);
                }
            } catch(e) {}
        }

        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs?since=' + logIndex);
                const data = await res.json();
                
                if (data.next_index !== undefined) {
                    logIndex = data.next_index;
                }

                if (data.logs && data.logs.length > 0) {
                    const term = document.getElementById('terminal');
                    if (term.innerText === 'Konsol ciktisi bekleniyor...') {
                        term.innerText = '';
                    }
                    
                    const fragment = document.createDocumentFragment();
                    data.logs.forEach(line => {
                        const isProgress = (line.includes('[DOWNLOAD]') || line.includes('[UPLOAD]')) && line.includes('%');
                        const lastChild = fragment.lastElementChild || term.lastElementChild;
                        if (isProgress && lastChild && (lastChild.innerText.includes('[DOWNLOAD]') || lastChild.innerText.includes('[UPLOAD]')) && lastChild.innerText.includes('%')) {
                            lastChild.innerText = line;
                            return;
                        }

                        const div = document.createElement('div');
                        if (line.includes('[ERROR]') || line.includes('[FAILED]')) {
                            div.className = 'log-error';
                        } else if (line.includes('[WARN]') || line.includes('[WARNING]') || line.includes('[FLOODWAIT]')) {
                            div.className = 'log-warn';
                        } else if (line.includes('[TAMAMLANDI]') || line.includes('[DONE]') || line.includes('[COMPLETED]')) {
                            div.className = 'log-done';
                        } else if (line.includes('[INFO]') || line.includes('[DETECTED]') || line.includes('[OK]') || line.includes('[AUTH]')) {
                            div.className = 'log-info';
                        }
                        div.innerText = line;
                        fragment.appendChild(div);
                    });

                    if (fragment.childNodes.length > 0) {
                        term.appendChild(fragment);
                    }

                    // DOM aşırı büyümesini önle
                    while (term.children.length > 300) {
                        term.removeChild(term.firstChild);
                    }

                    if (isAutoScroll) {
                        term.scrollTop = term.scrollHeight;
                    }
                }
            } catch(e) {}
        }

        async function runAction(mode) {
            const topic = document.getElementById('action-topic').value.trim();
            const mediaType = document.getElementById('action-type').value;
            const force = document.getElementById('action-force').checked;

            clearLogs();
            appendLocalLog(`[INFO] '${mode}' islemi baslatma istegi gonderiliyor...`);

            try {
                const res = await fetch('/api/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: mode, topic: topic, media_type: mediaType, force: force })
                });
                const data = await res.json();
                if (!data.success) {
                    showActionAlert(data.error || 'Islem baslatilamadi.', true);
                    appendLocalLog(`[ERROR] ${data.error || 'Islem baslatilamadi.'}`);
                } else {
                    showActionAlert(`'${mode}' islemi basariyla baslatildi.`);
                }
            } catch(err) {
                showActionAlert('Sunucu ile iletisim hatasi: ' + err, true);
                appendLocalLog(`[ERROR] Baglanti hatasi: ${err}`);
            }

            checkStatus();
        }

        async function stopAction() {
            appendLocalLog('[UI] Durdurma istegi gonderiliyor...');
            try {
                const res = await fetch('/api/stop', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    showActionAlert('Durdurma sinyali gonderildi.');
                }
            } catch(err) {
                showActionAlert('Durdurma hatasi: ' + err, true);
            }
            checkStatus();
        }

        async function loadTopicsList() {
            const container = document.getElementById('topics-container');
            const loading = document.getElementById('topics-loading');
            const content = document.getElementById('topics-content');

            container.style.display = 'block';
            loading.style.display = 'block';
            content.innerHTML = '';

            try {
                const res = await fetch('/api/topics');
                const data = await res.json();
                loading.style.display = 'none';

                if (!data.success) {
                    content.innerHTML = `<div style="color: var(--danger); font-size: 13px;">Hata: ${data.error}</div>`;
                    return;
                }

                let html = '';
                data.channels.forEach(ch => {
                    html += `<div style="margin-bottom: 12px;"><strong style="color: var(--text);">${ch.channel_title}</strong> (ID: ${ch.channel_id})`;
                    if (!ch.is_forum) {
                        html += ` <span style="color: var(--text-muted); font-size: 12px;">(Bu kanal forum modunda degil)</span>`;
                    } else if (ch.topics.length === 0) {
                        html += ` <span style="color: var(--warning); font-size: 12px;">(Konu bulunamadi)</span>`;
                    } else {
                        html += `<table class="topic-table">
                            <thead>
                                <tr>
                                    <th>Topic ID</th>
                                    <th>Konu Basligi</th>
                                    <th>Islem</th>
                                </tr>
                            </thead>
                            <tbody>`;
                        ch.topics.forEach(t => {
                            html += `<tr>
                                <td><span class="badge-id">#${t.id}</span></td>
                                <td><strong>${t.title}</strong></td>
                                <td>
                                    <button class="btn-success" style="padding: 4px 10px; font-size: 12px;" onclick="selectAndSyncTopic(${t.id})">Bu Konuyu Sec ve Tara</button>
                                </td>
                            </tr>`;
                        });
                        html += `</tbody></table>`;
                    }
                    html += `</div>`;
                });

                content.innerHTML = html;
            } catch(e) {
                loading.style.display = 'none';
                content.innerHTML = `<div style="color: var(--danger); font-size: 13px;">Baglanti hatasi: ${e}</div>`;
            }
        }

        function selectAndSyncTopic(topicId) {
            document.getElementById('action-topic').value = topicId;
            runAction('history');
        }

        function appendLocalLog(text) {
            const term = document.getElementById('terminal');
            if (term.innerText === 'Konsol ciktisi bekleniyor...') term.innerText = '';
            const div = document.createElement('div');
            div.className = text.includes('[ERROR]') ? 'log-error' : 'log-info';
            const now = new Date().toTimeString().split(' ')[0];
            div.innerText = `[${now}] ${text}`;
            term.appendChild(div);
            term.scrollTop = term.scrollHeight;
        }

        function clearLogs() {
            const term = document.getElementById('terminal');
            if (term) term.innerText = '';
        }

        async function checkForUpdates() {
            const btn = document.getElementById('btn-check-update');
            const topBtn = document.getElementById('btn-top-check-update');
            const topApplyBtn = document.getElementById('btn-top-apply-update');
            const statusText = document.getElementById('update-status-text');
            const applyBtn = document.getElementById('btn-apply-update');
            const changelogBox = document.getElementById('changelog-container');
            const changelogList = document.getElementById('changelog-list');
            const alertEl = document.getElementById('update-alert');
            const topBanner = document.getElementById('top-update-banner');
            const topBadge = document.getElementById('top-version-badge');
            const versionBadge = document.getElementById('version-badge');

            if (btn) btn.disabled = true;
            if (topBtn) topBtn.disabled = true;
            if (statusText) statusText.innerText = 'Guncellemeler denetleniyor...';
            if (alertEl) alertEl.style.display = 'none';

            try {
                const res = await fetch('/api/update/check');
                const data = await res.json();
                if (btn) btn.disabled = false;
                if (topBtn) topBtn.disabled = false;

                if (!data.success) {
                    if (statusText) statusText.innerText = '';
                    showUpdateAlert(data.error || 'Guncelleme kontrolu basarisiz.', true);
                    return;
                }

                const verText = `Surum: ${data.current_version}`;
                if (versionBadge) versionBadge.innerText = verText;
                if (topBadge) topBadge.innerText = verText + (data.has_update ? ' (Guncelleme Var!)' : ' (Guncel)');

                if (data.has_update) {
                    if (statusText) statusText.innerText = `${data.commits_behind} yeni guncelleme mevcut!`;
                    if (applyBtn) applyBtn.style.display = 'inline-flex';
                    if (topApplyBtn) topApplyBtn.style.display = 'inline-flex';

                    // Ust Bildirim Bandini Goster
                    if (topBanner) {
                        document.getElementById('banner-title').innerText = `Yeni bir surum (${data.latest_version}) yayinlandi! (${data.commits_behind} yeni guncelleme)`;
                        const preview = data.changelog && data.changelog.length > 0 ? data.changelog.slice(0, 2).join(' • ') : '';
                        document.getElementById('banner-changelog').innerText = preview;
                        topBanner.style.display = 'block';
                    }

                    if (changelogList) {
                        changelogList.innerHTML = '';
                        if (data.changelog) {
                            data.changelog.forEach(item => {
                                const li = document.createElement('li');
                                li.innerText = item;
                                changelogList.appendChild(li);
                            });
                        }
                    }
                    if (changelogBox) changelogBox.style.display = 'block';
                    showUpdateAlert(`Yeni surum (${data.latest_version}) bulundu! 'Simdi Otomatik Guncelle' butonuna basarak tek tikla yukleyebilirsiniz.`);
                } else {
                    if (statusText) statusText.innerText = 'Uygulamaniz guncel.';
                    if (applyBtn) applyBtn.style.display = 'none';
                    if (topApplyBtn) topApplyBtn.style.display = 'none';
                    if (topBanner) topBanner.style.display = 'none';
                    if (changelogBox) changelogBox.style.display = 'none';
                    showUpdateAlert('Uygulamaniz en son surumdedir! Herhangi bir guncelleme gerekmiyor.');
                }
            } catch(e) {
                if (btn) btn.disabled = false;
                if (topBtn) topBtn.disabled = false;
                if (statusText) statusText.innerText = '';
                showUpdateAlert('Baglanti hatasi: ' + e, true);
            }
        }

        async function applyUpdate() {
            const applyBtn = document.getElementById('btn-apply-update');
            const topApplyBtn = document.getElementById('btn-top-apply-update');
            const statusText = document.getElementById('update-status-text');

            if (!confirm('Uygulama en son surume guncellenecek ve sunucu otomatik olarak yeniden baslatilacak. Devam etmek istiyor musunuz?')) {
                return;
            }

            if (applyBtn) applyBtn.disabled = true;
            if (topApplyBtn) topApplyBtn.disabled = true;
            if (statusText) statusText.innerText = 'Guncelleme yukleniyor ve sunucu yeniden baslatiliyor...';

            try {
                const res = await fetch('/api/update/apply', { method: 'POST' });
                const data = await res.json();

                if (data.success) {
                    showUpdateAlert(`Uygulama basariyla ${data.new_version} surumune guncellendi! Sunucu yeniden baslatiliyor, sayfa 3 saniye icinde otomatik yenilenecek...`);
                    const topBanner = document.getElementById('top-update-banner');
                    if (topBanner) {
                        topBanner.innerHTML = `<div style="color: #34d399; font-weight: bold;">Guncelleme basariyla tamamlandi! Sayfa yenileniyor...</div>`;
                    }
                    setTimeout(() => {
                        window.location.reload(true);
                    }, 3000);
                } else {
                    if (applyBtn) applyBtn.disabled = false;
                    if (topApplyBtn) topApplyBtn.disabled = false;
                    showUpdateAlert(data.error || 'Guncelleme yuklenemedi.', true);
                    if (statusText) statusText.innerText = '';
                }
            } catch(e) {
                if (applyBtn) applyBtn.disabled = false;
                if (topApplyBtn) topApplyBtn.disabled = false;
                if (statusText) statusText.innerText = '';
                showUpdateAlert('Guncelleme sirasinda sunucu yeniden baslatilmis olabilir. Sayfayi yenileyebilirsiniz: ' + e, false);
                setTimeout(() => {
                    window.location.reload(true);
                }, 4000);
            }
        }

        function showUpdateAlert(msg, isError = false) {
            const el = document.getElementById('update-alert');
            if (el) {
                el.innerText = msg;
                el.className = isError ? 'alert alert-danger' : 'alert alert-success';
                el.style.display = 'block';
            }
        }

        loadStats();
        loadSettings();
        loadSavedProfiles();
        checkStatus();
        checkForUpdates();

        setInterval(loadStats, 5000);
        setInterval(checkStatus, 1500);
        setInterval(fetchLogs, 500);
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
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))

        elif parsed.path == "/api/status":
            running = task_manager.is_running()
            mode = task_manager.current_mode or "idle"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"running": running, "mode": mode}).encode("utf-8"))

        elif parsed.path == "/api/logs":
            params = parse_qs(parsed.query)
            since = int(params.get("since", [0])[0])
            new_logs, total_len = task_manager.get_logs(since=since)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"logs": new_logs, "next_index": total_len}).encode("utf-8"))

        elif parsed.path == "/api/topics":
            result = asyncio.run(fetch_topics_async())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))

        elif parsed.path == "/api/profile/export":
            profile_data = ProfileManager.export_to_dict()
            json_str = json.dumps(profile_data, indent=4, ensure_ascii=False)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=telegram_syncer_profile.json")
            self.end_headers()
            self.wfile.write(json_str.encode("utf-8"))

        elif parsed.path == "/api/profile/list":
            profiles = ProfileManager.list_saved_profiles()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"profiles": profiles}).encode("utf-8"))

        elif parsed.path == "/api/stats":
            db = DatabaseManager(config.db_path)
            stats = asyncio.run(db.get_stats())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode("utf-8"))

        elif parsed.path == "/api/settings":
            env_dict = ProfileManager.get_current_settings()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(env_dict).encode("utf-8"))

        elif parsed.path == "/api/update/check":
            result = UpdateManager.check_for_updates()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/run":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            data = json.loads(body) if body else {}

            mode = data.get("mode", "live")
            topic = data.get("topic", "")
            media_type = data.get("media_type", "all")
            force = data.get("force", False)

            success, msg = task_manager.start_task(mode=mode, topic=topic, media_type=media_type, force=force)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "error": msg if not success else ""}).encode("utf-8"))

        elif parsed.path == "/api/stop":
            success = task_manager.stop_task()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode("utf-8"))

        elif parsed.path == "/api/settings":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            new_settings = json.loads(body)
            ProfileManager.apply_settings(new_settings)
            config.reload()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))

        elif parsed.path == "/api/profile/import":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            profile_data = json.loads(body)
            success = ProfileManager.import_from_dict(profile_data)
            config.reload()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode("utf-8"))

        elif parsed.path == "/api/profile/save_named":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            data = json.loads(body)
            name = data.get("name", "profile")
            saved_path = ProfileManager.save_named_profile(name)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "path": str(saved_path)}).encode("utf-8"))

        elif parsed.path == "/api/profile/load_named":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            data = json.loads(body)
            name = data.get("name", "")
            success = ProfileManager.load_named_profile(name)
            config.reload()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode("utf-8"))

        elif parsed.path == "/api/update/apply":
            result = UpdateManager.apply_update()
            config.reload()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))
            if result.get("success"):
                threading.Thread(target=UpdateManager.restart_process, daemon=True).start()


def start_web_ui(port: int = 5000):
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, WebUIHandler)
    print(f"\n[INFO] Web Dashboard started on http://localhost:{port} (or http://127.0.0.1:{port})\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Web server stopped.")


if __name__ == "__main__":
    start_web_ui()
