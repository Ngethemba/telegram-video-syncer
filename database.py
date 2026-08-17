import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Union
import aiosqlite


class DatabaseManager:
    """Telegram videolarının indirilme ve yüklenme durumlarını takip eden SQLite yöneticisi."""

    def __init__(self, db_path: Union[str, Path] = "syncer_database.db"):
        self.db_path = str(db_path)
        self._lock = asyncio.Lock()

    async def init_db(self) -> None:
        """Veritabanını ve gerekli tabloları başlatır."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS processed_videos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_chat_id TEXT NOT NULL,
                        source_msg_id INTEGER NOT NULL,
                        file_unique_id TEXT,
                        file_name TEXT,
                        file_size INTEGER DEFAULT 0,
                        duration INTEGER DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'PENDING',
                        downloaded_path TEXT,
                        target_chat_id TEXT,
                        target_msg_id INTEGER,
                        target_topic_id INTEGER DEFAULT 0,
                        retry_count INTEGER DEFAULT 0,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(source_chat_id, source_msg_id)
                    )
                    """
                )
                await db.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chat_msg 
                    ON processed_videos(source_chat_id, source_msg_id)
                    """
                )
                await db.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_file_unique_id 
                    ON processed_videos(file_unique_id)
                    """
                )
                await db.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_status 
                    ON processed_videos(status)
                    """
                )
                await db.commit()

    async def is_already_completed(
        self, source_chat_id: Union[int, str], source_msg_id: int, file_unique_id: Optional[str] = None
    ) -> bool:
        """Videonun daha önce başarıyla tamamlanıp tamamlanmadığını kontrol eder."""
        chat_id_str = str(source_chat_id)
        async with aiosqlite.connect(self.db_path) as db:
            # 1. Kaynak kanal ve mesaj ID'sine göre kontrol
            async with db.execute(
                """
                SELECT status FROM processed_videos 
                WHERE source_chat_id = ? AND source_msg_id = ?
                """,
                (chat_id_str, source_msg_id),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0] == "COMPLETED":
                    return True

            # 2. Eğer file_unique_id varsa, başka bir mesajda yüklenip yüklenmediğini de kontrol et
            if file_unique_id:
                async with db.execute(
                    """
                    SELECT status FROM processed_videos 
                    WHERE file_unique_id = ? AND status = 'COMPLETED'
                    LIMIT 1
                    """,
                    (file_unique_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return True

        return False

    async def get_record(
        self, source_chat_id: Union[int, str], source_msg_id: int
    ) -> Optional[Dict]:
        """Belirtilen mesajın veritabanı kaydını döner."""
        chat_id_str = str(source_chat_id)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM processed_videos 
                WHERE source_chat_id = ? AND source_msg_id = ?
                """,
                (chat_id_str, source_msg_id),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def register_or_update(
        self,
        source_chat_id: Union[int, str],
        source_msg_id: int,
        file_unique_id: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size: int = 0,
        duration: int = 0,
        status: str = "PENDING",
    ) -> None:
        """Yeni bir işlem kaydı oluşturur veya günceller."""
        chat_id_str = str(source_chat_id)
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO processed_videos (
                        source_chat_id, source_msg_id, file_unique_id,
                        file_name, file_size, duration, status, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(source_chat_id, source_msg_id) DO UPDATE SET
                        file_unique_id = COALESCE(excluded.file_unique_id, processed_videos.file_unique_id),
                        file_name = COALESCE(excluded.file_name, processed_videos.file_name),
                        file_size = CASE WHEN excluded.file_size > 0 THEN excluded.file_size ELSE processed_videos.file_size END,
                        duration = CASE WHEN excluded.duration > 0 THEN excluded.duration ELSE processed_videos.duration END,
                        status = excluded.status,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (chat_id_str, source_msg_id, file_unique_id, file_name, file_size, duration, status),
                )
                await db.commit()

    async def update_status(
        self,
        source_chat_id: Union[int, str],
        source_msg_id: int,
        status: str,
        downloaded_path: Optional[str] = None,
        target_chat_id: Optional[Union[int, str]] = None,
        target_msg_id: Optional[int] = None,
        target_topic_id: Optional[int] = None,
        error_message: Optional[str] = None,
        increment_retry: bool = False,
    ) -> None:
        """İşlemin durumunu ve meta verilerini günceller."""
        chat_id_str = str(source_chat_id)
        target_chat_str = str(target_chat_id) if target_chat_id is not None else None

        query = """
            UPDATE processed_videos SET
                status = ?,
                downloaded_path = COALESCE(?, downloaded_path),
                target_chat_id = COALESCE(?, target_chat_id),
                target_msg_id = COALESCE(?, target_msg_id),
                target_topic_id = COALESCE(?, target_topic_id),
                error_message = ?,
                retry_count = retry_count + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE source_chat_id = ? AND source_msg_id = ?
        """

        retry_increment = 1 if increment_retry else 0

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    query,
                    (
                        status,
                        downloaded_path,
                        target_chat_str,
                        target_msg_id,
                        target_topic_id,
                        error_message,
                        retry_increment,
                        chat_id_str,
                        source_msg_id,
                    ),
                )
                await db.commit()

    async def get_failed_records(self, max_retries: int = 5) -> List[Dict]:
        """Tekrar denenebilir başarısız kayıtları döner."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM processed_videos 
                WHERE status = 'FAILED' AND retry_count < ?
                ORDER BY updated_at ASC
                """,
                (max_retries,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_stats(self) -> Dict[str, Union[int, float]]:
        """Veritabanı özet istatistiklerini hesaplar."""
        async with aiosqlite.connect(self.db_path) as db:
            stats = {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "pending": 0,
                "downloaded": 0,
                "total_bytes_transferred": 0,
            }
            async with db.execute(
                """
                SELECT status, COUNT(*), SUM(file_size) 
                FROM processed_videos 
                GROUP BY status
                """
            ) as cursor:
                async for row in cursor:
                    status_name = row[0].lower()
                    count = row[1]
                    size_sum = row[2] or 0

                    stats["total"] += count
                    if status_name in stats:
                        stats[status_name] = count

                    if status_name == "completed":
                        stats["total_bytes_transferred"] += size_sum

            return stats
