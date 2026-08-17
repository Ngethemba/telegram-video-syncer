import asyncio
import os
from pathlib import Path
import time
from typing import Callable, Optional, Union
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl import types
from tqdm import tqdm

from config import config
from database import DatabaseManager
from media_helper import MediaHelper
from channel_helper import ChannelHelper
from i18n import t


class VideoDownloader:
    """Safely downloads videos and photos from Telegram messages with progress bars and retry logic."""

    def __init__(self, client: TelegramClient, db: DatabaseManager):
        self.client = client
        self.db = db

    async def download_media(
        self,
        message: types.Message,
        source_chat_id: Union[int, str],
        allowed_media_type: str = "all",
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Optional[Path]:
        """Downloads media from Telegram message even in restricted channels."""
        media_info = ChannelHelper.extract_media_info(message, allowed_media_type=allowed_media_type)
        if not media_info:
            return None

        media_type = media_info["media_type"]
        file_size = media_info["file_size"]
        duration = media_info["duration"]
        file_unique_id = media_info["file_unique_id"]

        # Size filter
        if config.max_file_size_mb > 0 and file_size > 0:
            max_bytes = config.max_file_size_mb * 1024 * 1024
            if file_size > max_bytes:
                print(f"[SKIPPED] Media size ({file_size / (1024*1024):.1f} MB) exceeds limit ({config.max_file_size_mb} MB).")
                await self.db.register_or_update(
                    source_chat_id, message.id, file_unique_id,
                    media_info["file_name"], media_type, file_size, duration, status="SKIPPED"
                )
                return None

        # Duration filter for videos
        if media_type == "video" and config.min_duration_seconds > 0 and duration > 0 and duration < config.min_duration_seconds:
            print(f"[SKIPPED] Video duration ({duration}s) shorter than limit ({config.min_duration_seconds}s).")
            await self.db.register_or_update(
                source_chat_id, message.id, file_unique_id,
                media_info["file_name"], media_type, file_size, duration, status="SKIPPED"
            )
            return None

        safe_name = MediaHelper.sanitize_filename(media_info["file_name"])
        target_dir = config.download_dir / str(source_chat_id).replace("-100", "").replace("-", "")
        target_dir.mkdir(parents=True, exist_ok=True)
        destination_path = target_dir / f"{message.id}_{safe_name}"

        await self.db.register_or_update(
            source_chat_id,
            message.id,
            file_unique_id=file_unique_id,
            file_name=safe_name,
            media_type=media_type,
            file_size=file_size,
            duration=duration,
            status="DOWNLOADING",
        )

        retries = 0
        last_error = None
        type_label = t(media_type)

        while retries <= config.max_retries:
            pbar = None
            try:
                pbar = tqdm(
                    total=file_size if file_size > 0 else None,
                    unit="B",
                    unit_scale=True,
                    desc=f"[DOWNLOAD] ({type_label}) [Msg #{message.id}]",
                    ncols=90,
                    leave=False,
                )

                def internal_progress(current: int, total: int):
                    if pbar:
                        pbar.total = total
                        pbar.n = current
                        pbar.refresh()
                    if progress_callback:
                        progress_callback(current, total)

                downloaded_file = await self.client.download_media(
                    message,
                    file=str(destination_path),
                    progress_callback=internal_progress,
                )

                if pbar:
                    pbar.close()

                if downloaded_file and Path(downloaded_file).exists():
                    download_path = Path(downloaded_file)
                    actual_size = download_path.stat().st_size
                    await self.db.register_or_update(
                        source_chat_id,
                        message.id,
                        file_unique_id=file_unique_id,
                        file_name=safe_name,
                        media_type=media_type,
                        file_size=actual_size,
                        duration=duration,
                        status="DOWNLOADED",
                    )
                    await self.db.update_status(
                        source_chat_id=source_chat_id,
                        source_msg_id=message.id,
                        status="DOWNLOADED",
                        downloaded_path=str(download_path),
                    )
                    return download_path

            except FloodWaitError as e:
                if pbar:
                    pbar.close()
                wait_sec = e.seconds + 2
                print(f"\n{t('flood_wait', sec=wait_sec)}")
                await asyncio.sleep(wait_sec)
                retries += 1
                continue

            except Exception as e:
                if pbar:
                    pbar.close()
                last_error = str(e)
                retries += 1
                wait_sec = config.retry_delay_seconds * (2 ** (retries - 1))
                print(f"\n[ERROR] Download attempt {retries}/{config.max_retries}: {e}")
                
                if retries <= config.max_retries:
                    print(f"[RETRY] Retrying in {wait_sec} seconds...")
                    await asyncio.sleep(wait_sec)

        await self.db.update_status(
            source_chat_id=source_chat_id,
            source_msg_id=message.id,
            status="FAILED",
            error_message=f"Download failed after {config.max_retries} retries: {last_error}",
            increment_retry=True,
        )
        return None

    async def download_video(
        self,
        message: types.Message,
        source_chat_id: Union[int, str],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Optional[Path]:
        return await self.download_media(message, source_chat_id, allowed_media_type="all", progress_callback=progress_callback)
