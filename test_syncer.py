import asyncio
import os
import shutil
import tempfile
from pathlib import Path
import unittest

from database import DatabaseManager
from config import AppConfig, _parse_channel_list, _parse_single_channel, _normalize_topic_id, _parse_topic_list
from media_helper import MediaHelper
from channel_helper import ChannelHelper


class TestTelegramSyncer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_syncer.db"
        self.db = DatabaseManager(self.db_path)
        await self.db.init_db()

    async def asyncTearDown(self):
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_database_lifecycle_and_duplicate_prevention(self):
        # 1. Kayıt oluştur (Video)
        await self.db.register_or_update(
            source_chat_id="-1001234567890",
            source_msg_id=42,
            file_unique_id="unique_vid_999",
            file_name="sample_video.mp4",
            media_type="video",
            file_size=10485760,  # 10 MB
            duration=120,
            status="PENDING",
        )

        rec = await self.db.get_record("-1001234567890", 42)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["status"], "PENDING")
        self.assertEqual(rec["media_type"], "video")
        self.assertEqual(rec["file_size"], 10485760)

        # 2. Kayıt oluştur (Fotoğraf)
        await self.db.register_or_update(
            source_chat_id="-1001234567890",
            source_msg_id=43,
            file_unique_id="unique_photo_888",
            file_name="sample_photo.jpg",
            media_type="photo",
            file_size=204800,
            duration=0,
            status="PENDING",
        )

        photo_rec = await self.db.get_record("-1001234567890", 43)
        self.assertIsNotNone(photo_rec)
        self.assertEqual(photo_rec["media_type"], "photo")

        # 3. Tamamlandı kontrolü (Henüz tamamlanmadı)
        self.assertFalse(await self.db.is_already_completed("-1001234567890", 42))

        # 4. Durumu COMPLETED yap
        await self.db.update_status(
            source_chat_id="-1001234567890",
            source_msg_id=42,
            status="COMPLETED",
            target_chat_id="-1009876543210",
            target_msg_id=101,
            target_topic_id=5,
        )

        # 5. Artık tamamlandı olarak dönmeli
        self.assertTrue(await self.db.is_already_completed("-1001234567890", 42))
        # Unique ID ile de mükerrer kontrolü çalışmalı
        self.assertTrue(await self.db.is_already_completed("-1009999999999", 1, file_unique_id="unique_vid_999"))

    async def test_database_stats(self):
        await self.db.register_or_update("-1001", 1, "uid1", "v1.mp4", "video", 5000, 10, "COMPLETED")
        await self.db.update_status("-1001", 1, "COMPLETED")
        await self.db.register_or_update("-1001", 2, "uid2", "v2.mp4", "video", 7000, 10, "FAILED")
        await self.db.update_status("-1001", 2, "FAILED", error_message="Network error", increment_retry=True)

        stats = await self.db.get_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["total_bytes_transferred"], 5000)

    def test_config_parsing(self):
        channels = _parse_channel_list("-1001234567890, @testchannel, https://t.me/anotherchannel")
        self.assertEqual(len(channels), 3)
        self.assertEqual(channels[0], -1001234567890)
        self.assertEqual(channels[1], "@testchannel")
        self.assertEqual(channels[2], "@anotherchannel")

        single = _parse_single_channel("https://t.me/targetchannel")
        self.assertEqual(single, "@targetchannel")

    def test_topic_normalization(self):
        # 4294973210 = 4294967296 + 5914 (Telegram Web URL formatı)
        normalized = _normalize_topic_id(4294973210)
        self.assertEqual(normalized, 5914)

        from_url_param = _normalize_topic_id("&thread=4294973210")
        self.assertEqual(from_url_param, 5914)

        standard_id = _normalize_topic_id(5914)
        self.assertEqual(standard_id, 5914)

        topics = _parse_topic_list("4294973210, 1234, thread=4294973210")
        self.assertIn(5914, topics)
        self.assertIn(1234, topics)

    def test_media_sanitization(self):
        clean = MediaHelper.sanitize_filename("test / video: name * <?.mp4")
        self.assertNotIn(":", clean)
        self.assertNotIn("/", clean)
        self.assertNotIn("*", clean)


if __name__ == "__main__":
    unittest.main()
