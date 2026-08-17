import asyncio
import os
from pathlib import Path
from typing import Callable, Optional, Union
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl import types
from tqdm import tqdm

from config import config
from database import DatabaseManager
from media_helper import MediaHelper
from channel_helper import ChannelHelper


class VideoUploader:
    """İndirilen videoları hedef kanala (forum/topic desteğiyle) yükleyen sınıf."""

    def __init__(self, client: TelegramClient, db: DatabaseManager):
        self.client = client
        self.db = db
        self.channel_helper = ChannelHelper(client)

    def _prepare_caption(self, original_caption: str) -> str:
        """Açıklama (caption) metnini yapılandırmaya göre biçimlendirir."""
        caption = original_caption if config.keep_original_caption else ""
        if config.custom_caption_prefix:
            caption = f"{config.custom_caption_prefix}\n{caption}".strip()
        if config.custom_caption_suffix:
            caption = f"{caption}\n{config.custom_caption_suffix}".strip()
        return caption

    async def upload_video(
        self,
        video_path: Path,
        source_chat_id: Union[int, str],
        source_msg_id: int,
        original_caption: str = "",
        target_chat: Optional[Union[int, str]] = None,
        target_topic_id: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Optional[types.Message]:
        """
        Videoyu hedef kanala/gruba ve varsa belirtilen Forum Topic ID'sine yükler.
        """
        if not video_path.exists():
            print(f"❌ Yüklenecek video dosyası bulunamadı: {video_path}")
            return None

        target_peer = target_chat if target_chat is not None else config.target_channel
        topic_id = target_topic_id if target_topic_id is not None else config.target_topic_id

        # Hedef kanal bilgilerini al
        chat_info = await self.channel_helper.get_chat_info(target_peer)
        is_forum = chat_info.get("is_forum", False)

        # Topic kontrolü ve uyarısı
        reply_to_arg = None
        if topic_id and topic_id > 0:
            reply_to_arg = topic_id
            if not is_forum:
                print(f"ℹ️ Bilgi: Hedef kanal ({chat_info['title']}) standart modda, ancak Topic ID ({topic_id}) yanıt olarak kullanılacak.")
            else:
                print(f"💬 Forum Modu Aktif: Video Topic ID #{topic_id} konusuna yüklenecek.")
        elif is_forum:
            print(f"⚠️ Dikkat: Hedef kanal ({chat_info['title']}) Forum modunda, ancak TARGET_TOPIC_ID belirtilmemiş (Genel Konuya yüklenecek).")

        # Video meta verilerini ve küçük resmini (thumbnail) hazırla
        file_size = video_path.stat().st_size
        duration, width, height = MediaHelper.get_video_metadata(video_path)
        thumb_path = await MediaHelper.generate_thumbnail(video_path)

        attributes = [
            types.DocumentAttributeVideo(
                duration=duration,
                w=width,
                h=height,
                supports_streaming=True,
            )
        ]

        caption = self._prepare_caption(original_caption)

        # Durumu UPLOADING yap
        await self.db.update_status(
            source_chat_id=source_chat_id,
            source_msg_id=source_msg_id,
            status="UPLOADING",
            target_chat_id=str(target_peer),
            target_topic_id=topic_id,
        )

        retries = 0
        last_error = None

        while retries <= config.max_retries:
            pbar = None
            try:
                pbar = tqdm(
                    total=file_size,
                    unit="B",
                    unit_scale=True,
                    desc=f"📤 Yükleniyor [Hedef: {chat_info['title'][:15]}]",
                    ncols=90,
                    leave=False,
                )

                def internal_progress(current: int, total: int):
                    if pbar:
                        pbar.n = current
                        pbar.refresh()
                    if progress_callback:
                        progress_callback(current, total)

                # Telethon send_file
                sent_msg = await self.client.send_file(
                    entity=target_peer,
                    file=video_path,
                    caption=caption,
                    thumb=str(thumb_path) if thumb_path else None,
                    attributes=attributes,
                    reply_to=reply_to_arg,
                    progress_callback=internal_progress,
                    supports_streaming=True,
                )

                if pbar:
                    pbar.close()

                if sent_msg:
                    # Başarılı kayıt
                    await self.db.update_status(
                        source_chat_id=source_chat_id,
                        source_msg_id=source_msg_id,
                        status="COMPLETED",
                        target_chat_id=str(target_peer),
                        target_msg_id=sent_msg.id,
                        target_topic_id=topic_id,
                    )

                    # Otomatik temizleme açıksa yerel dosyayı sil
                    if config.auto_cleanup:
                        MediaHelper.safe_delete_file(video_path)

                    # Yüklemeler arası bekleme (Flood koruması)
                    if config.delay_between_uploads > 0:
                        await asyncio.sleep(config.delay_between_uploads)

                    return sent_msg

            except FloodWaitError as e:
                if pbar:
                    pbar.close()
                wait_sec = e.seconds + 2
                print(f"\n⏳ [FloodWait] Telegram hız sınırına takıldı. {wait_sec} saniye bekleniyor...")
                await asyncio.sleep(wait_sec)
                retries += 1
                continue

            except Exception as e:
                if pbar:
                    pbar.close()
                last_error = str(e)
                retries += 1
                wait_sec = config.retry_delay_seconds * (2 ** (retries - 1))
                print(f"\n❌ [Yükleme Hatası - Deneme {retries}/{config.max_retries}]: {e}")
                
                if retries <= config.max_retries:
                    print(f"⏳ {wait_sec} saniye sonra tekrar denenecek...")
                    await asyncio.sleep(wait_sec)

        # Başarısızlık kaydı
        await self.db.update_status(
            source_chat_id=source_chat_id,
            source_msg_id=source_msg_id,
            status="FAILED",
            error_message=f"Upload failed after {config.max_retries} retries: {last_error}",
            increment_retry=True,
        )
        return None
