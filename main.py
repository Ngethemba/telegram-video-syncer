import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import List, Optional, Union
from colorama import Fore, Style, init
from telethon import TelegramClient, events
from telethon.tl import types

from config import config
from database import DatabaseManager
from channel_helper import ChannelHelper
from downloader import VideoDownloader
from uploader import VideoUploader

# Colorama başlat
init(autoreset=True)


class TelegramSyncerApp:
    def __init__(self):
        self.db = DatabaseManager(config.db_path)
        self.client = TelegramClient(
            config.session_name,
            config.api_id,
            config.api_hash,
            connection_retries=10,
            retry_delay=5,
            auto_reconnect=True,
        )
        self.channel_helper = ChannelHelper(self.client)
        self.downloader = VideoDownloader(self.client, self.db)
        self.uploader = VideoUploader(self.client, self.db)
        self._is_running = True

    async def initialize(self):
        """Veritabanını başlatır ve Telegram istemcisine giriş yapar."""
        await self.db.init_db()
        print(Fore.CYAN + "🚀 Telegram istemcisi başlatılıyor...")
        
        # Telethon başlatma (Gerekirse terminalden doğrulama kodu ister)
        await self.client.start(phone=config.phone if config.phone else None)
        me = await self.client.get_me()
        print(Fore.GREEN + f"✅ Başarıyla giriş yapıldı: {me.first_name} (@{me.username or me.id})")

    async def process_single_message(
        self,
        message: types.Message,
        source_chat_id: Union[int, str],
        source_title: str = "",
    ) -> bool:
        """Tek bir mesajı inceler, video ise indirir ve hedef kanala yükler."""
        video_info = ChannelHelper.extract_video_info(message)
        if not video_info:
            return False

        file_size_mb = video_info["file_size"] / (1024 * 1024)
        file_name = video_info["file_name"]
        file_unique_id = video_info["file_unique_id"]

        print(Fore.YELLOW + f"\n🎥 Video Tespit Edildi: [Kanal: {source_title}] [Msg #{message.id}]")
        print(f"   📁 Dosya Adı : {file_name}")
        print(f"   📦 Boyut     : {file_size_mb:.2f} MB")
        print(f"   ⏱️ Süre      : {video_info['duration']} sn")

        # 1. Mükerrer Kontrolü (Daha önce başarıyla yüklendi mi?)
        is_completed = await self.db.is_already_completed(
            source_chat_id=source_chat_id,
            source_msg_id=message.id,
            file_unique_id=file_unique_id,
        )
        if is_completed:
            print(Fore.BLUE + f"   ⏭️ [Atlandı] Bu video daha önce başarıyla aktarılmış.")
            return False

        # 2. İndirme Aşaması
        download_path = await self.downloader.download_video(
            message=message,
            source_chat_id=source_chat_id,
        )
        if not download_path:
            print(Fore.RED + f"   ❌ Video indirilemedi veya filtreye takıldı.")
            return False

        print(Fore.GREEN + f"   ✅ İndirme Tamamlandı: {download_path.name}")

        # 3. Yükleme Aşaması
        sent_msg = await self.uploader.upload_video(
            video_path=download_path,
            source_chat_id=source_chat_id,
            source_msg_id=message.id,
            original_caption=video_info["caption"],
        )

        if sent_msg:
            print(Fore.GREEN + f"   🚀 Hedef Kanala Başarıyla Aktarıldı (Yeni Msg ID: #{sent_msg.id})")
            return True
        else:
            print(Fore.RED + f"   ❌ Hedef kanala yükleme başarısız oldu.")
            return False

    async def run_live_monitor(self):
        """Canlı izleme modu: Kaynak kanalları dinler ve yeni videoları anında aktarır."""
        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + "📡 CANLI İZLEME MODU (LIVE MONITOR) BAŞLATILDI")
        print(Fore.CYAN + "=" * 60)

        source_entities = []
        for src in config.source_channels:
            try:
                info = await self.channel_helper.get_chat_info(src)
                source_entities.append(info["entity"])
                prot = "🔒 Korumalı/Yasaklı" if info["noforwards"] else "🔓 Normal"
                forum = "💬 Forum/Topic" if info["is_forum"] else "📢 Standart"
                print(f"👉 İzlenen Kaynak: {info['title']} ({prot}, {forum})")
            except Exception as e:
                print(Fore.RED + f"⚠️ Kaynak kanal çözümlenemedi ({src}): {e}")

        # Hedef kanalı doğrula
        try:
            target_info = await self.channel_helper.get_chat_info(config.target_channel)
            print(Fore.GREEN + f"🎯 Hedef Kanal  : {target_info['title']} (ID: {target_info['id']})")
            if target_info["is_forum"]:
                print(Fore.YELLOW + f"   ℹ️ Hedef Kanal Forum Modunda! Hedef Konu ID: {config.target_topic_id}")
        except Exception as e:
            print(Fore.RED + f"❌ Hedef kanal doğrulanamadı: {e}")

        if not source_entities:
            print(Fore.RED + "❌ Hiçbir geçerli kaynak kanal bulunamadı. Program sonlandırılıyor.")
            return

        @self.client.on(events.NewMessage(chats=source_entities))
        async def handler(event: events.NewMessage.Event):
            try:
                chat = await event.get_chat()
                title = getattr(chat, "title", str(event.chat_id))
                await self.process_single_message(
                    message=event.message,
                    source_chat_id=event.chat_id,
                    source_title=title,
                )
            except Exception as ex:
                print(Fore.RED + f"❌ Olay işleme hatası: {ex}")

        print(Fore.GREEN + "\n🎧 Yeni videolar bekleniyor... (Çıkmak için Ctrl+C)\n")
        
        while self._is_running:
            await asyncio.sleep(1)

    async def run_history_sync(self, limit: int = 100, reverse: bool = True):
        """Geçmiş tarama modu: Belirtilen limit kadar geçmiş mesajları tarar."""
        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + f"📚 GEÇMİŞ TARAMA MODU (Limit: {'Tümü' if limit == 0 else limit})")
        print(Fore.CYAN + "=" * 60)

        for src in config.source_channels:
            try:
                chat_info = await self.channel_helper.get_chat_info(src)
                entity = chat_info["entity"]
                print(Fore.YELLOW + f"\n🔍 Kanal taranıyor: {chat_info['title']} (ID: {chat_info['id']})")

                effective_limit = None if limit == 0 else limit
                processed_count = 0
                synced_count = 0

                async for message in self.client.iter_messages(entity, limit=effective_limit, reverse=reverse):
                    if not self._is_running:
                        break

                    if message.media:
                        processed_count += 1
                        success = await self.process_single_message(
                            message=message,
                            source_chat_id=chat_info["id"],
                            source_title=chat_info["title"],
                        )
                        if success:
                            synced_count += 1

                print(Fore.GREEN + f"✅ {chat_info['title']} tamamlandı. (Toplam taranan medya: {processed_count}, Aktarılan: {synced_count})")

            except Exception as e:
                print(Fore.RED + f"❌ Kanal taranırken hata oluştu ({src}): {e}")

    async def run_interactive_selection(self):
        """Seçmeli mod: Kaynak kanaldaki videoları listeler ve kullanıcının seçmesini sağlar."""
        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + "📋 SEÇMELİ VİDEO AKTARIM MODU")
        print(Fore.CYAN + "=" * 60)

        if len(config.source_channels) > 1:
            print("Kaynak Kanallar:")
            for idx, ch in enumerate(config.source_channels, 1):
                print(f"[{idx}] {ch}")
            choice = input("Lütfen listelemek istediğiniz kanalın numarasını seçin (1-N): ").strip()
            try:
                chosen_channel = config.source_channels[int(choice) - 1]
            except Exception:
                chosen_channel = config.source_channels[0]
        else:
            chosen_channel = config.source_channels[0]

        chat_info = await self.channel_helper.get_chat_info(chosen_channel)
        print(Fore.YELLOW + f"\n🔍 '{chat_info['title']}' kanalından son videolar çekiliyor...")

        videos = []
        async for message in self.client.iter_messages(chat_info["entity"], limit=50):
            video_info = ChannelHelper.extract_video_info(message)
            if video_info:
                is_done = await self.db.is_already_completed(
                    chat_info["id"], message.id, video_info["file_unique_id"]
                )
                videos.append({
                    "message": message,
                    "info": video_info,
                    "is_done": is_done,
                })

        if not videos:
            print(Fore.RED + "❌ Kanalda uygun video bulunamadı.")
            return

        print(Fore.CYAN + f"\nBulunan Videolar (Son {len(videos)}):")
        for i, item in enumerate(videos, 1):
            info = item["info"]
            size_mb = info["file_size"] / (1024 * 1024)
            status_tag = Fore.GREEN + "[AKTARRILMIŞ]" if item["is_done"] else Fore.YELLOW + "[BEKLİYOR]"
            print(f"[{i:2d}] {status_tag} {info['file_name'][:40]:<40} | {size_mb:6.1f} MB | {info['duration']:4d}s (Msg #{item['message'].id})")

        print("\nİşlem yapmak istediğiniz video numaralarını girin.")
        print("Örnekler: '1,3,5' veya '1-5' veya 'hepsi'")
        selection = input("Seçiminiz: ").strip().lower()

        selected_indices = []
        if selection in ("hepsi", "all", "*"):
            selected_indices = list(range(len(videos)))
        else:
            parts = selection.split(",")
            for p in parts:
                p = p.strip()
                if "-" in p:
                    start, end = p.split("-")
                    for x in range(int(start), int(end) + 1):
                        if 1 <= x <= len(videos):
                            selected_indices.append(x - 1)
                elif p.isdigit():
                    idx = int(p)
                    if 1 <= idx <= len(videos):
                        selected_indices.append(idx - 1)

        selected_indices = sorted(list(set(selected_indices)))
        print(Fore.CYAN + f"\nToplam {len(selected_indices)} adet video sıraya alındı.")

        for idx in selected_indices:
            item = videos[idx]
            await self.process_single_message(
                message=item["message"],
                source_chat_id=chat_info["id"],
                source_title=chat_info["title"],
            )

    async def run_retry_failed(self):
        """Hata alan veya yarım kalan videoları tekrar dener."""
        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + "🔄 BAŞARISIZ İŞLEMLERİ YENİDEN DENEME MODU")
        print(Fore.CYAN + "=" * 60)

        failed_records = await self.db.get_failed_records(max_retries=config.max_retries)
        if not failed_records:
            print(Fore.GREEN + "✅ Yeniden denenecek başarısız kayıt bulunamadı.")
            return

        print(Fore.YELLOW + f"Bulunan başarısız işlem sayısı: {len(failed_records)}")

        for rec in failed_records:
            try:
                chat_entity = await self.client.get_entity(int(rec["source_chat_id"]) if rec["source_chat_id"].replace("-", "").isdigit() else rec["source_chat_id"])
                msg = await self.client.get_messages(chat_entity, ids=rec["source_msg_id"])
                if msg:
                    await self.process_single_message(
                        message=msg,
                        source_chat_id=rec["source_chat_id"],
                        source_title=getattr(chat_entity, "title", str(rec["source_chat_id"])),
                    )
            except Exception as e:
                print(Fore.RED + f"❌ Msg #{rec['source_msg_id']} yeniden denenirken hata: {e}")

    async def show_status(self):
        """Veritabanı ve aktarım istatistiklerini görüntüler."""
        stats = await self.db.get_stats()
        gb_transferred = stats["total_bytes_transferred"] / (1024 * 1024 * 1024)

        print(Fore.CYAN + "\n" + "=" * 50)
        print(Fore.CYAN + "📊 TELEGRAM SYNCER DURUM VE İSTATİSTİKLERİ")
        print(Fore.CYAN + "=" * 50)
        print(f"📁 Toplam İşlenen Kayıt  : {stats['total']}")
        print(Fore.GREEN + f"✅ Başarıyla Tamamlanan : {stats['completed']}")
        print(Fore.RED + f"❌ Başarısız / Hatalı    : {stats['failed']}")
        print(Fore.YELLOW + f"⏳ Bekleyen / İndirilen  : {stats['pending'] + stats['downloaded']}")
        print(Fore.CYAN + f"📦 Toplam Aktarılan Veri : {gb_transferred:.2f} GB")
        print("=" * 50 + "\n")

    def stop(self):
        self._is_running = False


async def main():
    parser = argparse.ArgumentParser(
        description="Telegram Video İndirici & Aktarıcı (Debian/Pardus Linux Uyumlu)"
    )
    parser.add_argument(
        "mode",
        choices=["live", "history", "interactive", "status", "retry-failed"],
        nargs="?",
        default="live",
        help="Çalışma modu: live (canlı izleme), history (geçmiş tarama), interactive (seçmeli), status (istatistik), retry-failed (hatalıları tekrar dene)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Geçmiş tarama modu için taranacak mesaj sayısı (0 = tüm geçmiş)",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        default=True,
        help="Geçmiş taramada en eski videodan başlayarak sırayla aktar",
    )

    args = parser.parse_args()

    # Yapılandırmayı doğrula (status modu hariç)
    if args.mode != "status":
        try:
            config.validate()
        except ValueError as e:
            print(Fore.RED + f"\n{e}\n")
            print(Fore.YELLOW + "Lütfen .env dosyasını doldurduğunuzdan emin olun. (.env.example dosyasını kopyalayabilirsiniz)")
            sys.exit(1)

    app = TelegramSyncerApp()

    # Graceful shutdown handler
    loop = asyncio.get_running_loop()

    def signal_handler():
        print(Fore.YELLOW + "\n⚠️ Kapatma sinyali alındı, uygulama güvenli bir şekilde kapatılıyor...")
        app.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows uyumluluğu için
            pass

    await app.initialize()

    try:
        if args.mode == "live":
            await app.run_live_monitor()
        elif args.mode == "history":
            await app.run_history_sync(limit=args.limit, reverse=args.reverse)
        elif args.mode == "interactive":
            await app.run_interactive_selection()
        elif args.mode == "retry-failed":
            await app.run_retry_failed()
        elif args.mode == "status":
            await app.show_status()
    finally:
        await app.client.disconnect()
        print(Fore.CYAN + "👋 Oturum kapatıldı.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram kullanıcı tarafından sonlandırıldı.")
