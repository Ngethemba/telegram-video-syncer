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

from config import config, _normalize_topic_id, _parse_topic_list
from database import DatabaseManager
from channel_helper import ChannelHelper
from downloader import VideoDownloader
from uploader import VideoUploader

# Colorama başlat
init(autoreset=True)


class TelegramSyncerApp:
    def __init__(self, override_topics: Optional[List[int]] = None, override_media_type: Optional[str] = None):
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
        self.source_topic_ids = override_topics if override_topics is not None else config.source_topic_ids
        self.media_type = (override_media_type or config.media_type).lower().strip()
        self._is_running = True

    async def initialize(self):
        """Veritabanını başlatır ve Telegram istemcisine giriş yapar."""
        await self.db.init_db()
        print(Fore.CYAN + "🚀 Telegram istemcisi başlatılıyor...")
        
        await self.client.start(phone=config.phone if config.phone else None)
        me = await self.client.get_me()
        print(Fore.GREEN + f"✅ Başarıyla giriş yapıldı: {me.first_name} (@{me.username or me.id})")
        
        type_str = "Tüm Medyalar (Video + Fotoğraf)" if self.media_type == "all" else f"Yalnızca {self.media_type.upper()}"
        print(Fore.CYAN + f"📦 Hedef Medya Türü: {type_str}")

        if self.source_topic_ids:
            print(Fore.YELLOW + f"🎯 Kaynak Topic Filtresi Aktif: {self.source_topic_ids} (Yalnızca bu konulardaki medyalar indirilecek)")

    async def process_single_message(
        self,
        message: types.Message,
        source_chat_id: Union[int, str],
        source_title: str = "",
        force: bool = False,
    ) -> bool:
        """Tek bir mesajı inceler, video veya fotoğraf ise indirir ve hedef kanala yükler."""
        media_info = ChannelHelper.extract_media_info(message, allowed_media_type=self.media_type)
        if not media_info:
            return False

        # Kaynak Topic Filtresi Kontrolü
        if self.source_topic_ids:
            if not ChannelHelper.is_message_in_topics(message, self.source_topic_ids):
                return False

        media_type = media_info["media_type"]
        file_size_mb = media_info["file_size"] / (1024 * 1024) if media_info["file_size"] > 0 else 0
        file_name = media_info["file_name"]
        file_unique_id = media_info["file_unique_id"]
        msg_topic = media_info.get("topic_id")
        topic_str = f" [Topic/Konu: #{msg_topic}]" if msg_topic else ""

        type_icon = "📷 Fotoğraf" if media_type == "photo" else "🎥 Video"
        print(Fore.YELLOW + f"\n{type_icon} Tespit Edildi: [Kanal: {source_title}]{topic_str} [Msg #{message.id}]")
        print(f"   📁 Dosya Adı : {file_name}")
        if file_size_mb > 0:
            print(f"   📦 Boyut     : {file_size_mb:.2f} MB")
        if media_type == "video" and media_info["duration"] > 0:
            print(f"   ⏱️ Süre      : {media_info['duration']} sn")

        # 1. Mükerrer Kontrolü (force aktif değilse)
        if not force:
            is_completed = await self.db.is_already_completed(
                source_chat_id=source_chat_id,
                source_msg_id=message.id,
                file_unique_id=file_unique_id,
            )
            if is_completed:
                print(Fore.BLUE + f"   ⏭️ [Atlandı] Bu {type_icon.lower()} daha önce başarıyla aktarılmış (Yeniden indirmek için --force kullanın).")
                return False

        # 2. İndirme Aşaması
        download_path = await self.downloader.download_media(
            message=message,
            source_chat_id=source_chat_id,
            allowed_media_type=self.media_type,
        )
        if not download_path:
            print(Fore.RED + f"   ❌ Medya indirilemedi veya filtreye takıldı.")
            return False

        print(Fore.GREEN + f"   ✅ İndirme Tamamlandı: {download_path.name}")

        # 3. Yükleme Aşaması
        sent_msg = await self.uploader.upload_media(
            media_path=download_path,
            source_chat_id=source_chat_id,
            source_msg_id=message.id,
            media_type=media_type,
            original_caption=media_info["caption"],
        )

        if sent_msg:
            print(Fore.GREEN + f"   🚀 Hedef Kanala Başarıyla Aktarıldı (Yeni Msg ID: #{sent_msg.id})")
            return True
        else:
            print(Fore.RED + f"   ❌ Hedef kanala yükleme başarısız oldu.")
            return False

    async def run_live_monitor(self):
        """Canlı izleme modu: Kaynak kanalları dinler ve yeni medyaları anında aktarır."""
        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + "📡 CANLI İZLEME MODU (LIVE MONITOR) BAŞLATILDI")
        if self.source_topic_ids:
            print(Fore.YELLOW + f"🎯 Yalnızca Hedef Kaynak Topic(ler): {self.source_topic_ids}")
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

        print(Fore.GREEN + "\n🎧 Yeni medyalar bekleniyor... (Çıkmak için Ctrl+C)\n")
        
        while self._is_running:
            await asyncio.sleep(1)

    async def run_history_sync(self, limit: int = 0, reverse: bool = False, force: bool = False):
        """Geçmiş tarama modu: Belirtilen konulardaki tüm medyaları eksiksiz tarar ve aktarır."""
        print(Fore.CYAN + "\n" + "=" * 60)
        limit_text = "TÜM GEÇMİŞ (Sınırsız)" if limit == 0 else f"{limit} Mesaj"
        order_text = "Eskiden Yeniye" if reverse else "Yeniden Eskiye (En güncel medyalar)"
        type_text = "Video ve Fotoğraf" if self.media_type == "all" else self.media_type.capitalize()
        print(Fore.CYAN + f"📚 GEÇMİŞ TARAMA MODU ({limit_text} | Sıralama: {order_text} | Tür: {type_text})")
        if self.source_topic_ids:
            print(Fore.YELLOW + f"🎯 Taranacak Topic(ler): {self.source_topic_ids}")
        if force:
            print(Fore.MAGENTA + "⚠️ FORCE MODU AKTİF: Önceden indirilmiş medyalar da tekrar aktarılacak.")
        print(Fore.CYAN + "=" * 60)

        for src in config.source_channels:
            try:
                chat_info = await self.channel_helper.get_chat_info(src)
                entity = chat_info["entity"]
                print(Fore.YELLOW + f"\n🔍 Kanal taranıyor: {chat_info['title']} (ID: {chat_info['id']})")

                effective_limit = None if limit == 0 else limit

                # Eğer belirli topic ID'leri belirtilmişse sırayla her topic'in TÜM medyalarını tara
                if self.source_topic_ids:
                    for topic_id in self.source_topic_ids:
                        print(Fore.CYAN + f"\n   📂 [Topic #{topic_id}] Taraması Başlatıldı (Tüm mesajlar inceleniyor)...")
                        topic_scanned_count = 0
                        topic_media_count = 0
                        topic_synced_count = 0

                        async for message in self.client.iter_messages(
                            entity, limit=effective_limit, reply_to=topic_id, reverse=reverse
                        ):
                            if not self._is_running:
                                break
                            topic_scanned_count += 1

                            if message.media:
                                is_media = ChannelHelper.extract_media_info(message, allowed_media_type=self.media_type) is not None
                                if is_media:
                                    topic_media_count += 1
                                    success = await self.process_single_message(
                                        message=message,
                                        source_chat_id=chat_info["id"],
                                        source_title=chat_info["title"],
                                        force=force,
                                    )
                                    if success:
                                        topic_synced_count += 1

                        print(Fore.GREEN + f"   ✅ Topic #{topic_id} tamamlandı: {topic_scanned_count} mesaj incelendi, {topic_media_count} medya bulundu, {topic_synced_count} aktarıldı.")
                else:
                    # Tüm kanalı tara
                    print(Fore.CYAN + f"\n   📢 Kanalın tüm geçmişi taranıyor...")
                    scanned_count = 0
                    media_count = 0
                    synced_count = 0

                    async for message in self.client.iter_messages(entity, limit=effective_limit, reverse=reverse):
                        if not self._is_running:
                            break
                        scanned_count += 1

                        if message.media:
                            is_media = ChannelHelper.extract_media_info(message, allowed_media_type=self.media_type) is not None
                            if is_media:
                                media_count += 1
                                success = await self.process_single_message(
                                    message=message,
                                    source_chat_id=chat_info["id"],
                                    source_title=chat_info["title"],
                                    force=force,
                                )
                                if success:
                                    synced_count += 1

                    print(Fore.GREEN + f"✅ {chat_info['title']} tamamlandı: {scanned_count} mesaj incelendi, {media_count} medya bulundu, {synced_count} aktarıldı.")

            except Exception as e:
                print(Fore.RED + f"❌ Kanal taranırken hata oluştu ({src}): {e}")

    async def run_interactive_selection(self):
        """Seçmeli mod: Kaynak kanaldaki medya dosyalarını listeler ve kullanıcının seçmesini sağlar."""
        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + "📋 SEÇMELİ MEDYA AKTARIM MODU")
        if self.source_topic_ids:
            print(Fore.YELLOW + f"🎯 Filtrelenen Topic(ler): {self.source_topic_ids}")
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
        print(Fore.YELLOW + f"\n🔍 '{chat_info['title']}' kanalından son medyalar çekiliyor...")

        media_list = []
        
        if self.source_topic_ids:
            for tid in self.source_topic_ids:
                async for message in self.client.iter_messages(chat_info["entity"], limit=50, reply_to=tid):
                    info = ChannelHelper.extract_media_info(message, allowed_media_type=self.media_type)
                    if info:
                        is_done = await self.db.is_already_completed(
                            chat_info["id"], message.id, info["file_unique_id"]
                        )
                        media_list.append({
                            "message": message,
                            "info": info,
                            "is_done": is_done,
                        })
        else:
            async for message in self.client.iter_messages(chat_info["entity"], limit=50):
                info = ChannelHelper.extract_media_info(message, allowed_media_type=self.media_type)
                if info:
                    is_done = await self.db.is_already_completed(
                        chat_info["id"], message.id, info["file_unique_id"]
                    )
                    media_list.append({
                        "message": message,
                        "info": info,
                        "is_done": is_done,
                    })

        if not media_list:
            print(Fore.RED + "❌ Belirtilen kriterlerde uygun medya bulunamadı.")
            return

        print(Fore.CYAN + f"\nBulunan Medyalar (Son {len(media_list)}):")
        for i, item in enumerate(media_list, 1):
            info = item["info"]
            size_mb = info["file_size"] / (1024 * 1024) if info["file_size"] > 0 else 0
            status_tag = Fore.GREEN + "[AKTARILMIŞ]" if item["is_done"] else Fore.YELLOW + "[BEKLİYOR]"
            type_tag = "[FOTOĞRAF]" if info["media_type"] == "photo" else "[VİDEO]   "
            topic_label = f" [T:#{info['topic_id']}]" if info.get("topic_id") else ""
            dur_str = f" | {info['duration']:4d}s" if info["media_type"] == "video" else " | Fotoğraf"
            print(f"[{i:2d}] {status_tag} {type_tag}{topic_label} {info['file_name'][:30]:<30} | {size_mb:6.1f} MB{dur_str} (Msg #{item['message'].id})")

        print("\nİşlem yapmak istediğiniz medya numaralarını girin.")
        print("Örnekler: '1,3,5' veya '1-5' veya 'hepsi'")
        selection = input("Seçiminiz: ").strip().lower()

        selected_indices = []
        if selection in ("hepsi", "all", "*"):
            selected_indices = list(range(len(media_list)))
        else:
            parts = selection.split(",")
            for p in parts:
                p = p.strip()
                if "-" in p:
                    start, end = p.split("-")
                    for x in range(int(start), int(end) + 1):
                        if 1 <= x <= len(media_list):
                            selected_indices.append(x - 1)
                elif p.isdigit():
                    idx = int(p)
                    if 1 <= idx <= len(media_list):
                        selected_indices.append(idx - 1)

        selected_indices = sorted(list(set(selected_indices)))
        print(Fore.CYAN + f"\nToplam {len(selected_indices)} adet medya sıraya alındı.")

        for idx in selected_indices:
            item = media_list[idx]
            await self.process_single_message(
                message=item["message"],
                source_chat_id=chat_info["id"],
                source_title=chat_info["title"],
            )

    async def run_retry_failed(self):
        """Hata alan veya yarım kalan medyaları tekrar dener."""
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

    async def list_source_topics(self):
        """Kaynak kanallardaki tüm topic (konu) başlıklarını ve ID'lerini listeler."""
        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + "📑 KAYNAK KANAL TOPIC (KONU) LİSTESİ")
        print(Fore.CYAN + "=" * 60)

        for src in config.source_channels:
            try:
                chat_info = await self.channel_helper.get_chat_info(src)
                print(Fore.YELLOW + f"\n📢 Kanal: {chat_info['title']} (ID: {chat_info['id']})")
                
                if not chat_info["is_forum"]:
                    print("   ℹ️ Bu kanal Forum modunda değil (Standart kanal).")
                    continue

                topics = await self.channel_helper.list_forum_topics(chat_info["entity"], limit=100)
                if not topics:
                    print(Fore.RED + "   ❌ Konu başlığı bulunamadı veya yetki yetersiz.")
                    continue

                print(Fore.GREEN + f"   Toplam {len(topics)} konu bulundu:\n")
                print(f"   {'No':<4} | {'Topic ID':<10} | {'Konu Başlığı'}")
                print("   " + "-" * 55)
                for idx, t in enumerate(topics, 1):
                    print(f"   [{idx:2d}] | ID: {t['id']:<6} | {t['title']}")

                print(Fore.CYAN + "\n💡 İpucu: İndirmek istediğiniz konuların ID'lerini .env dosyasına yazabilirsiniz:")
                sample_ids = ", ".join(str(t['id']) for t in topics[:2])
                print(f"   SOURCE_TOPIC_IDS={sample_ids}")
                print(Fore.CYAN + "   Veya komutla tek seferlik çalıştırabilirsiniz:")
                print(f"   ./run.sh live --topic {topics[0]['id']}")
            except Exception as e:
                print(Fore.RED + f"❌ Kanal incelenirken hata ({src}): {e}")

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
        description="Telegram Medya (Video & Fotoğraf) İndirici ve Aktarıcı (Debian/Pardus Linux Uyumlu)"
    )
    parser.add_argument(
        "mode",
        choices=["live", "history", "interactive", "status", "retry-failed", "list-topics"],
        nargs="?",
        default="live",
        help="Çalışma modu: live, history, interactive, status, retry-failed, list-topics",
    )
    parser.add_argument(
        "--type",
        "--media-type",
        choices=["all", "video", "photo"],
        default=None,
        help="İndirilecek medya türü: all (video + fotoğraf), video (yalnızca video), photo (yalnızca fotoğraf)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Geçmiş tarama modu için taranacak mesaj sayısı (0 = sınırsız / konudaki TÜM medyalar)",
    )
    parser.add_argument(
        "--topic",
        "--source-topic",
        type=str,
        default="",
        help="Kaynak kanaldan yalnızca belirli bir Topic/Konu ID'sini indirmek için (Örn: 5914 veya thread linki)",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        default=False,
        help="Geçmiş taramada en eski mesajdan başla (Varsayılan: En yeni videolardan başlar)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Daha önce indirilmiş medyaları mükerrer kontrolünü atlayarak tekrar indir ve yükle",
    )

    args = parser.parse_args()

    # Yapılandırmayı doğrula (status modu hariç)
    if args.mode not in ("status", "list-topics"):
        try:
            config.validate()
        except ValueError as e:
            print(Fore.RED + f"\n{e}\n")
            print(Fore.YELLOW + "Lütfen .env dosyasını doldurduğunuzdan emin olun. (.env.example dosyasını kopyalayabilirsiniz)")
            sys.exit(1)

    # CLI üzerinden topic parametresi geldiyse onu öncelikli kıl
    cli_topics = _parse_topic_list(args.topic) if args.topic else None
    cli_media_type = args.type if args.type else None

    app = TelegramSyncerApp(override_topics=cli_topics, override_media_type=cli_media_type)

    # Graceful shutdown handler
    loop = asyncio.get_running_loop()

    def signal_handler():
        print(Fore.YELLOW + "\n⚠️ Kapatma sinyali alındı, uygulama güvenli bir şekilde kapatılıyor...")
        app.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    await app.initialize()

    try:
        if args.mode == "live":
            await app.run_live_monitor()
        elif args.mode == "history":
            await app.run_history_sync(limit=args.limit, reverse=args.reverse, force=args.force)
        elif args.mode == "interactive":
            await app.run_interactive_selection()
        elif args.mode == "retry-failed":
            await app.run_retry_failed()
        elif args.mode == "status":
            await app.show_status()
        elif args.mode == "list-topics":
            await app.list_source_topics()
    finally:
        await app.client.disconnect()
        print(Fore.CYAN + "👋 Oturum kapatıldı.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram kullanıcı tarafından sonlandırıldı.")
