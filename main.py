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
from i18n import t, get_active_language

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
        self.lang = get_active_language()

    async def initialize(self):
        await self.db.init_db()
        print(Fore.CYAN + f"[INIT] Telegram client initializing...")
        
        await self.client.start(phone=config.phone if config.phone else None)
        me = await self.client.get_me()
        print(Fore.GREEN + f"[AUTH] Logged in successfully: {me.first_name} (@{me.username or me.id})")
        
        type_str = t("type_all", self.lang) if self.media_type == "all" else f"{self.media_type.upper()}"
        print(Fore.CYAN + f"[CONFIG] Target Media: {type_str}")

        if self.source_topic_ids:
            print(Fore.YELLOW + f"[FILTER] Active Source Topic Filter: {self.source_topic_ids}")

    async def process_single_message(
        self,
        message: types.Message,
        source_chat_id: Union[int, str],
        source_title: str = "",
        force: bool = False,
    ) -> bool:
        media_info = ChannelHelper.extract_media_info(message, allowed_media_type=self.media_type)
        if not media_info:
            return False

        if self.source_topic_ids:
            if not ChannelHelper.is_message_in_topics(message, self.source_topic_ids):
                return False

        media_type = media_info["media_type"]
        file_size_mb = media_info["file_size"] / (1024 * 1024) if media_info["file_size"] > 0 else 0
        file_name = media_info["file_name"]
        file_unique_id = media_info["file_unique_id"]
        msg_topic = media_info.get("topic_id")
        topic_str = f" [Topic: #{msg_topic}]" if msg_topic else ""

        type_label = t(media_type, self.lang)
        print(Fore.YELLOW + f"\n[DETECTED] ({type_label}) [Channel: {source_title}]{topic_str} [Msg #{message.id}]")
        print(f"   File Name : {file_name}")
        if file_size_mb > 0:
            print(f"   File Size : {file_size_mb:.2f} MB")
        if media_type == "video" and media_info["duration"] > 0:
            print(f"   Duration  : {media_info['duration']}s")

        if not force:
            is_completed = await self.db.is_already_completed(
                source_chat_id=source_chat_id,
                source_msg_id=message.id,
                file_unique_id=file_unique_id,
            )
            if is_completed:
                print(Fore.BLUE + f"   [SKIPPED] {t('media_skipped', self.lang)}")
                return False

        download_path = await self.downloader.download_media(
            message=message,
            source_chat_id=source_chat_id,
            allowed_media_type=self.media_type,
        )
        if not download_path:
            print(Fore.RED + f"   [FAILED] {t('download_failed', self.lang)}")
            return False

        print(Fore.GREEN + f"   [OK] {t('download_complete', self.lang, name=download_path.name)}")

        sent_msg = await self.uploader.upload_media(
            media_path=download_path,
            source_chat_id=source_chat_id,
            source_msg_id=message.id,
            media_type=media_type,
            original_caption=media_info["caption"],
        )

        if sent_msg:
            print(Fore.GREEN + f"   [SUCCESS] {t('upload_complete', self.lang, msg_id=sent_msg.id)}")
            return True
        else:
            print(Fore.RED + f"   [FAILED] {t('upload_failed', self.lang)}")
            return False

    async def run_live_monitor(self):
        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + f"{t('live_started', self.lang)}")
        if self.source_topic_ids:
            print(Fore.YELLOW + f"[TOPIC FILTER] {self.source_topic_ids}")
        print(Fore.CYAN + "=" * 60)

        source_entities = []
        for src in config.source_channels:
            try:
                info = await self.channel_helper.get_chat_info(src)
                source_entities.append(info["entity"])
                prot = "Restricted" if info["noforwards"] else "Normal"
                forum = "Forum/Topic" if info["is_forum"] else "Standard"
                print(f"[SOURCE] {info['title']} ({prot}, {forum})")
            except Exception as e:
                print(Fore.RED + f"[ERROR] Source channel resolution failed ({src}): {e}")

        try:
            target_info = await self.channel_helper.get_chat_info(config.target_channel)
            print(Fore.GREEN + f"[TARGET] {target_info['title']} (ID: {target_info['id']})")
            if target_info["is_forum"]:
                print(Fore.YELLOW + f"[TARGET FORUM] Topic ID: {config.target_topic_id}")
        except Exception as e:
            print(Fore.RED + f"[ERROR] Target channel verification failed: {e}")

        if not source_entities:
            print(Fore.RED + "[FATAL] No valid source channels found. Exiting.")
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
                print(Fore.RED + f"[ERROR] Event handling error: {ex}")

        while self._is_running:
            await asyncio.sleep(1)

    async def run_history_sync(self, limit: int = 0, reverse: bool = False, force: bool = False):
        print(Fore.CYAN + "\n" + "=" * 60)
        limit_text = "ALL (Unlimited)" if limit == 0 else f"{limit} Messages"
        order_text = "Oldest First" if reverse else "Newest First"
        type_text = self.media_type.capitalize()
        print(Fore.CYAN + f"[HISTORY] Batch Sync ({limit_text} | Order: {order_text} | Media: {type_text})")
        if self.source_topic_ids:
            print(Fore.YELLOW + f"[TOPICS] {self.source_topic_ids}")
        if force:
            print(Fore.MAGENTA + "[FORCE] Re-downloading completed records is enabled.")
        print(Fore.CYAN + "=" * 60)

        for src in config.source_channels:
            try:
                chat_info = await self.channel_helper.get_chat_info(src)
                entity = chat_info["entity"]
                print(Fore.YELLOW + f"\n[SCANNING] Channel: {chat_info['title']} (ID: {chat_info['id']})")

                effective_limit = None if limit == 0 else limit

                if self.source_topic_ids:
                    for topic_id in self.source_topic_ids:
                        print(Fore.CYAN + f"\n   [TOPIC #{topic_id}] Scanning messages...")
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

                        print(Fore.GREEN + f"   [DONE] Topic #{topic_id}: {topic_scanned_count} msgs scanned, {topic_media_count} media found, {topic_synced_count} synced.")
                else:
                    print(Fore.CYAN + f"\n   [SCANNING] Scanning entire channel history...")
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

                    print(Fore.GREEN + f"[DONE] {chat_info['title']}: {scanned_count} msgs scanned, {media_count} media found, {synced_count} synced.")

            except Exception as e:
                print(Fore.RED + f"[ERROR] Channel scan failed ({src}): {e}")

    async def run_interactive_selection(self):
        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + f"[INTERACTIVE] {t('interactive_title', self.lang)}")
        if self.source_topic_ids:
            print(Fore.YELLOW + f"[TOPICS] {self.source_topic_ids}")
        print(Fore.CYAN + "=" * 60)

        if len(config.source_channels) > 1:
            print("Source Channels:")
            for idx, ch in enumerate(config.source_channels, 1):
                print(f"[{idx}] {ch}")
            choice = input("Select channel number (1-N): ").strip()
            try:
                chosen_channel = config.source_channels[int(choice) - 1]
            except Exception:
                chosen_channel = config.source_channels[0]
        else:
            chosen_channel = config.source_channels[0]

        chat_info = await self.channel_helper.get_chat_info(chosen_channel)
        print(Fore.YELLOW + f"\n[FETCHING] Recent media from '{chat_info['title']}'...")

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
            print(Fore.RED + "[ERROR] No matching media found.")
            return

        print(Fore.CYAN + f"\nFound Media (Last {len(media_list)}):")
        for i, item in enumerate(media_list, 1):
            info = item["info"]
            size_mb = info["file_size"] / (1024 * 1024) if info["file_size"] > 0 else 0
            status_tag = Fore.GREEN + "[SYNCED] " if item["is_done"] else Fore.YELLOW + "[PENDING]"
            type_tag = "[PHOTO]" if info["media_type"] == "photo" else "[VIDEO]"
            topic_label = f" [T:#{info['topic_id']}]" if info.get("topic_id") else ""
            dur_str = f" | {info['duration']:4d}s" if info["media_type"] == "video" else " | Photo"
            print(f"[{i:2d}] {status_tag} {type_tag}{topic_label} {info['file_name'][:30]:<30} | {size_mb:6.1f} MB{dur_str} (Msg #{item['message'].id})")

        print("\nEnter media numbers to sync (e.g. '1,3,5' or '1-5' or 'all'):")
        selection = input("Selection: ").strip().lower()

        selected_indices = []
        if selection in ("all", "hepsi", "*"):
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
        print(Fore.CYAN + f"\nTotal {len(selected_indices)} item(s) queued for sync.")

        for idx in selected_indices:
            item = media_list[idx]
            await self.process_single_message(
                message=item["message"],
                source_chat_id=chat_info["id"],
                source_title=chat_info["title"],
            )

    async def run_retry_failed(self):
        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + "[RETRY] Retrying Failed Records")
        print(Fore.CYAN + "=" * 60)

        failed_records = await self.db.get_failed_records(max_retries=config.max_retries)
        if not failed_records:
            print(Fore.GREEN + "[OK] No failed records to retry.")
            return

        print(Fore.YELLOW + f"[FOUND] Failed record count: {len(failed_records)}")

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
                print(Fore.RED + f"[ERROR] Msg #{rec['source_msg_id']} retry error: {e}")

    async def list_source_topics(self):
        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + f"[TOPICS] {t('topic_list_title', self.lang)}")
        print(Fore.CYAN + "=" * 60)

        for src in config.source_channels:
            try:
                chat_info = await self.channel_helper.get_chat_info(src)
                print(Fore.YELLOW + f"\n[CHANNEL] {chat_info['title']} (ID: {chat_info['id']})")
                
                if not chat_info["is_forum"]:
                    print("   [INFO] Channel is not in Forum mode (Standard channel).")
                    continue

                topics = await self.channel_helper.list_forum_topics(chat_info["entity"], limit=100)
                if not topics:
                    print(Fore.RED + "   [ERROR] No topics found or insufficient permissions.")
                    continue

                print(Fore.GREEN + f"   Total {len(topics)} topic(s) found:\n")
                print(f"   {'No':<4} | {'Topic ID':<10} | {'Topic Title'}")
                print("   " + "-" * 55)
                for idx, t_obj in enumerate(topics, 1):
                    print(f"   [{idx:2d}] | ID: {t_obj['id']:<6} | {t_obj['title']}")

                print(Fore.CYAN + "\n[TIP] Configure SOURCE_TOPIC_IDS in .env or run with:")
                print(f"   ./run.sh live --topic {topics[0]['id']}")
            except Exception as e:
                print(Fore.RED + f"[ERROR] Channel inspection error ({src}): {e}")

    async def show_status(self):
        stats = await self.db.get_stats()
        mb_transferred = stats["total_bytes_transferred"] / (1024 * 1024)

        print(Fore.CYAN + "\n" + "=" * 50)
        print(Fore.CYAN + f"{t('stats_title', self.lang)}")
        print(Fore.CYAN + "=" * 50)
        print(t('stats_total', self.lang, total=stats['total']))
        print(Fore.GREEN + t('stats_completed', self.lang, completed=stats['completed']))
        print(Fore.RED + t('stats_failed', self.lang, failed=stats['failed']))
        print(Fore.YELLOW + t('stats_pending', self.lang, pending=stats['pending'] + stats['downloaded']))
        print(Fore.CYAN + t('stats_transferred', self.lang, mb=mb_transferred))
        print("=" * 50 + "\n")

    def stop(self):
        self._is_running = False


async def main():
    parser = argparse.ArgumentParser(
        description="Telegram Media Syncer (Linux and Windows)"
    )
    parser.add_argument(
        "mode",
        choices=["live", "history", "interactive", "status", "retry-failed", "list-topics"],
        nargs="?",
        default="live",
        help="Operation mode: live, history, interactive, status, retry-failed, list-topics",
    )
    parser.add_argument(
        "--type",
        "--media-type",
        choices=["all", "video", "photo"],
        default=None,
        help="Media type filter: all, video, photo",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Message scan limit for history mode (0 = unlimited / all media)",
    )
    parser.add_argument(
        "--topic",
        "--source-topic",
        type=str,
        default="",
        help="Source Topic ID filter (e.g. 5914)",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        default=False,
        help="Scan from oldest to newest (Default: newest first)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Re-download and re-upload even if already completed",
    )

    args = parser.parse_args()

    if args.mode not in ("status", "list-topics"):
        try:
            config.validate()
        except ValueError as e:
            print(Fore.RED + f"\n{e}\n")
            print(Fore.YELLOW + "Please configure your .env file or run 'python setup_wizard.py'")
            sys.exit(1)

    cli_topics = _parse_topic_list(args.topic) if args.topic else None
    cli_media_type = args.type if args.type else None

    app = TelegramSyncerApp(override_topics=cli_topics, override_media_type=cli_media_type)

    loop = asyncio.get_running_loop()

    def signal_handler():
        print(Fore.YELLOW + "\n[SHUTDOWN] Signal received, shutting down gracefully...")
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
        print(Fore.CYAN + "[EXIT] Session disconnected.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
