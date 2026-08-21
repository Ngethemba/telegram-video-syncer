import asyncio
import json
import os
import queue
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from config import config, _parse_topic_list, _parse_channel_list
from database import DatabaseManager
from channel_helper import ChannelHelper
from telethon import TelegramClient


class TaskManager:
    """Arka plan islemlerini guvenli sekilde yoneten ve loglari anlik toplayan sinif."""

    def __init__(self):
        self.active_app = None
        self.current_mode = None
        self.worker_thread = None
        self.logs = []
        self.lock = threading.Lock()

    def is_running(self) -> bool:
        with self.lock:
            return self.worker_thread is not None and self.worker_thread.is_alive()

    def start_task(self, mode: str, topic: str = "", media_type: str = "", force: bool = False) -> bool:
        with self.lock:
            if self.worker_thread is not None and self.worker_thread.is_alive():
                return False

            self.current_mode = mode
            self.logs.clear()
            self._add_log(f"[INFO] '{mode}' islemi baslatildi.")

            self.worker_thread = threading.Thread(
                target=self._run_async_worker,
                args=(mode, topic, media_type, force),
                daemon=True
            )
            self.worker_thread.start()
            return True

    def _run_async_worker(self, mode: str, topic: str, media_type: str, force: bool):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        class WebLogger:
            def __init__(self, add_log_fn, orig_stdout):
                self.add_log_fn = add_log_fn
                self.orig_stdout = orig_stdout

            def write(self, msg):
                if msg:
                    for line in msg.splitlines():
                        clean = line.strip()
                        if clean:
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
        load_dotenv(override=True)
        from main import TelegramSyncerApp

        config.validate()

        cli_topics = _parse_topic_list(topic) if topic else None
        cli_media = media_type if (media_type and media_type != "all") else None

        app = TelegramSyncerApp(override_topics=cli_topics, override_media_type=cli_media)
        with self.lock:
            self.active_app = app

        await app.initialize()

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

        self._add_log(f"[DONE] '{mode}' islemi tamamlandi.")

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
            self.logs.append(f"[{timestamp}] {text}")
            if len(self.logs) > 3000:
                self.logs.pop(0)

    def get_logs(self, since: int = 0):
        with self.lock:
            if since < len(self.logs):
                return self.logs[since:], len(self.logs)
            return [], len(self.logs)


task_manager = TaskManager()


async def fetch_topics_async():
    """Telegram istemcisini baslatip kaynak kanallardaki konulari ceker."""
    load_dotenv(override=True)
    client = TelegramClient(
        config.session_name,
        config.api_id,
        config.api_hash,
    )
    try:
        await client.start(phone=config.phone if config.phone else None)
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
        
        /* Terminal Log Ekranı */
        .terminal-container { background: var(--terminal-bg); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-top: 16px; }
        .terminal-header { background: #1e293b; padding: 8px 14px; font-size: 12px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); }
        .terminal-logs { padding: 14px; height: 350px; overflow-y: auto; font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; color: #a7f3d0; white-space: pre-wrap; word-break: break-all; }
        .terminal-logs .log-error { color: #f87171; }
        .terminal-logs .log-warn { color: #fbbf24; }
        .terminal-logs .log-info { color: #60a5fa; }
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
            <h1>Telegram Medya Aktarici</h1>
            <span style="font-size: 12px; background: #334155; padding: 4px 10px; border-radius: 20px;">Web Dashboard</span>
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
            
            <div class="btn-group" style="margin-bottom: 16px;">
                <button class="btn-success" id="btn-history" onclick="runAction('history')">Gecmisi Tara ve Aktar</button>
                <button class="btn-primary" id="btn-live" onclick="runAction('live')">Canli Izlemeyi Baslat</button>
                <button class="btn-warning" id="btn-topics" onclick="loadTopicsList()">Konulari (Topic) Listele</button>
                <button class="btn-secondary" id="btn-retry" onclick="runAction('retry-failed')">Hatalilari Tekrar Dene</button>
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
                if (data.logs && data.logs.length > 0) {
                    const term = document.getElementById('terminal');
                    if (logIndex === 0) term.innerText = '';
                    
                    data.logs.forEach(line => {
                        const div = document.createElement('div');
                        if (line.includes('[ERROR]') || line.includes('[FAILED]')) {
                            div.className = 'log-error';
                        } else if (line.includes('[WARN]') || line.includes('[WARNING]') || line.includes('[FLOODWAIT]')) {
                            div.className = 'log-warn';
                        } else if (line.includes('[INFO]') || line.includes('[DETECTED]') || line.includes('[OK]') || line.includes('[AUTH]') || line.includes('[DONE]')) {
                            div.className = 'log-info';
                        }
                        div.innerText = line;
                        term.appendChild(div);
                    });

                    logIndex = data.next_index;
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
            await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: mode, topic: topic, media_type: mediaType, force: force })
            });

            checkStatus();
            fetchLogs();
        }

        async function stopAction() {
            await fetch('/api/stop', { method: 'POST' });
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

        function clearLogs() {
            document.getElementById('terminal').innerText = '';
            logIndex = 0;
        }

        loadStats();
        loadSettings();
        checkStatus();

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
        if parsed.path == "/api/run":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            data = json.loads(body) if body else {}

            mode = data.get("mode", "live")
            topic = data.get("topic", "")
            media_type = data.get("media_type", "all")
            force = data.get("force", False)

            success = task_manager.start_task(mode=mode, topic=topic, media_type=media_type, force=force)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode("utf-8"))

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

            env_content = f"""# ==============================================================================
# Telegram Media Syncer Configuration File
# Updated by Web Dashboard
# ==============================================================================

LANGUAGE={new_settings.get('LANGUAGE', 'tr')}

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
    print(f"\n[INFO] Web Dashboard started on http://localhost:{port} (or http://127.0.0.1:{port})\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Web server stopped.")


if __name__ == "__main__":
    start_web_ui()
