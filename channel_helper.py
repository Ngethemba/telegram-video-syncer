from typing import Any, Dict, Optional, Tuple, Union
from telethon import TelegramClient
from telethon.tl import types
from telethon.tl.functions.messages import GetForumTopicsRequest


class ChannelHelper:
    """Telegram kanal, grup ve forum/topic yapılarını analiz eden yardımcı sınıf."""

    def __init__(self, client: TelegramClient):
        self.client = client

    async def get_chat_info(self, chat_peer: Union[int, str]) -> Dict[str, Any]:
        """
        Kanalın/grubun temel bilgilerini, kısıtlılık durumunu ve Forum modunu çözümler.
        """
        entity = await self.client.get_entity(chat_peer)

        title = getattr(entity, "title", str(chat_peer))
        username = getattr(entity, "username", None)
        is_channel = isinstance(entity, types.Channel)
        is_megagroup = getattr(entity, "megagroup", False)
        
        # Forum/Topic Modu Kontrolü
        # Telegram'da forum modundaki kanallar/gruplar forum=True özelliğine sahiptir.
        is_forum = getattr(entity, "forum", False)

        # İçerik koruması / indirme yasağı (noforwards)
        noforwards = getattr(entity, "noforwards", False)

        return {
            "entity": entity,
            "id": entity.id,
            "title": title,
            "username": username,
            "is_channel": is_channel,
            "is_megagroup": is_megagroup,
            "is_forum": is_forum,
            "noforwards": noforwards,
        }

    async def list_forum_topics(self, chat_peer: Union[int, str], limit: int = 50) -> list:
        """Kanal forum modundaysa mevcut topic (konu) listesini döner."""
        try:
            entity = await self.client.get_entity(chat_peer)
            if not getattr(entity, "forum", False):
                return []

            result = await self.client(GetForumTopicsRequest(
                peer=entity,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=limit
            ))
            topics = []
            for topic in result.topics:
                if isinstance(topic, types.ForumTopic):
                    topics.append({
                        "id": topic.id,
                        "title": topic.title,
                        "top_message": topic.top_message,
                    })
            return topics
        except Exception:
            return []

    @staticmethod
    def extract_video_info(message: types.Message) -> Optional[Dict[str, Any]]:
        """
        Mesajın bir video veya video belgesi (document) içerip içermediğini tespit eder.
        Dönüş: Video meta verileri veya video yoksa None.
        """
        if not message or not message.media:
            return None

        # 1. Doğrudan MessageMediaDocument veya MessageMediaUnsupported
        media = message.media
        if not isinstance(media, types.MessageMediaDocument):
            return None

        doc = media.document
        if not isinstance(doc, types.Document):
            return None

        mime_type = getattr(doc, "mime_type", "")
        file_size = getattr(doc, "size", 0)
        file_name = None
        duration = 0
        width = 0
        height = 0
        is_video = False

        # Video niteliklerini incele
        for attr in doc.attributes:
            if isinstance(attr, types.DocumentAttributeVideo):
                is_video = True
                duration = getattr(attr, "duration", 0)
                width = getattr(attr, "w", 0)
                height = getattr(attr, "h", 0)
            elif isinstance(attr, types.DocumentAttributeFilename):
                file_name = attr.file_name

        # Mime type kontrolü (video/mp4, video/mkv, video/x-matroska, video/webm, vb.)
        if mime_type.startswith("video/"):
            is_video = True

        if not is_video and file_name:
            lower_name = file_name.lower()
            if lower_name.endswith((".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".ts", ".m4v")):
                is_video = True

        if not is_video:
            return None

        if not file_name:
            ext = ".mp4"
            if mime_type:
                ext = f".{mime_type.split('/')[-1]}"
            file_name = f"video_{message.id}_{doc.id}{ext}"

        file_unique_id = f"{doc.id}_{doc.access_hash}"

        return {
            "document": doc,
            "file_unique_id": file_unique_id,
            "file_name": file_name,
            "file_size": file_size,
            "duration": duration,
            "width": width,
            "height": height,
            "mime_type": mime_type,
            "caption": message.text or "",
        }
