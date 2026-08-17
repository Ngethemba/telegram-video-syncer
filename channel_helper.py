from typing import Any, Dict, List, Optional, Tuple, Union
from telethon import TelegramClient
from telethon.tl import types
from telethon.tl.functions.messages import GetForumTopicsRequest


class ChannelHelper:
    """Telegram kanal, grup ve forum/topic yapılarını analiz eden yardımcı sınıf."""

    def __init__(self, client: TelegramClient):
        self.client = client

    @staticmethod
    def normalize_topic_id(raw_id: Union[int, str]) -> int:
        """
        Telegram Web URL'lerinden gelen 64-bit topic ID'lerini (örn: 4294973210 veya thread=4294973210)
        ve standart MTProto topic ID'lerini (örn: 5914) çözer ve normalize eder.
        """
        try:
            if isinstance(raw_id, str):
                raw_id = raw_id.strip()
                if "thread=" in raw_id:
                    raw_id = raw_id.split("thread=")[-1].split("&")[0]
                if "topic/" in raw_id:
                    raw_id = raw_id.split("topic/")[-1].split("?")[0].split("/")[0]
            val = int(raw_id)
            if val > 4294967296:
                return val % 4294967296  # Telegram Web ID (2^32 bit) -> gerçek Topic ID
            return val
        except Exception:
            return 0

    @staticmethod
    def get_message_topic_id(message: types.Message) -> Optional[int]:
        """Mesajın ait olduğu topic (konu/thread) ID'sini tespit eder."""
        if not message:
            return None

        # Telethon'da forum konularındaki mesajlar reply_to başlığı taşır
        if message.reply_to:
            # reply_to_top_id forum başlığının kök mesaj ID'sidir (Topic ID)
            top_id = getattr(message.reply_to, "reply_to_top_id", None)
            if top_id:
                return top_id

            # Eğer forum_topic True ise reply_to_msg_id doğrudan Topic ID olabilir
            if getattr(message.reply_to, "forum_topic", False):
                return getattr(message.reply_to, "reply_to_msg_id", None)

            # Doğrudan reply_to_msg_id
            msg_id = getattr(message.reply_to, "reply_to_msg_id", None)
            if msg_id:
                return msg_id

        return None

    @staticmethod
    def is_message_in_topics(message: types.Message, allowed_topic_ids: List[int]) -> bool:
        """Mesajın izin verilen topic ID'lerinden birine ait olup olmadığını kontrol eder."""
        if not allowed_topic_ids:
            return True  # Filtre yoksa tüm topic'ler geçerli

        msg_topic = ChannelHelper.get_message_topic_id(message)
        if msg_topic is None:
            # Topic'siz ana mesajlar. Eğer listede 0 varsa izin ver, yoksa atla
            return 0 in allowed_topic_ids

        normalized_msg_topic = ChannelHelper.normalize_topic_id(msg_topic)
        for allowed in allowed_topic_ids:
            norm_allowed = ChannelHelper.normalize_topic_id(allowed)
            if normalized_msg_topic == norm_allowed or msg_topic == allowed:
                return True
        return False

    async def resolve_peer_entity(self, chat_peer: Union[int, str]):
        """Kanal veya grup varlığını güvenli şekilde çözümler (-100 eksik girilse bile düzeltir)."""
        # 1. Doğrudan dene
        try:
            return await self.client.get_entity(chat_peer)
        except Exception:
            pass

        # 2. String/Int ise -100 prefixi veya PeerChannel ile dene
        peer_str = str(chat_peer).strip().replace("@", "")
        if peer_str.replace("-", "").isdigit():
            clean_digits = peer_str.replace("-", "")
            if not peer_str.startswith("-100"):
                try:
                    return await self.client.get_entity(int(f"-100{clean_digits}"))
                except Exception:
                    pass
            try:
                return await self.client.get_entity(types.PeerChannel(int(clean_digits)))
            except Exception:
                pass

        # 3. Son olarak asıl çağrıyı yapıp hatayı fırlat
        return await self.client.get_entity(chat_peer)

    async def get_chat_info(self, chat_peer: Union[int, str]) -> Dict[str, Any]:
        """
        Kanalın/grubun temel bilgilerini, kısıtlılık durumunu ve Forum modunu çözümler.
        """
        entity = await self.resolve_peer_entity(chat_peer)

        title = getattr(entity, "title", str(chat_peer))
        username = getattr(entity, "username", None)
        is_channel = isinstance(entity, types.Channel)
        is_megagroup = getattr(entity, "megagroup", False)
        
        # Forum/Topic Modu Kontrolü
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
            entity = await self.resolve_peer_entity(chat_peer)
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
        topic_id = ChannelHelper.get_message_topic_id(message)

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
            "topic_id": topic_id,
        }
