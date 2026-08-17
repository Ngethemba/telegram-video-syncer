import asyncio
import os
from pathlib import Path
import re
import shutil
from typing import Optional, Tuple, Union
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser


class MediaHelper:
    """Videolar için küçük resim (thumbnail) oluşturma ve meta veri çıkarım yardımcısı."""

    @staticmethod
    def sanitize_filename(name: str, max_length: int = 100) -> str:
        """Dosya adındaki geçersiz karakterleri temizler."""
        if not name:
            return "telegram_video"
        # Linux ve genel dosya sistemleri için geçersiz karakterleri temizle
        clean = re.sub(r'[\\/*?:"<>|]', "", name)
        clean = clean.strip().replace(" ", "_")
        return clean[:max_length] if clean else "telegram_video"

    @staticmethod
    def get_video_metadata(video_path: Path) -> Tuple[int, int, int]:
        """
        Videonun süresini (saniye), genişliğini ve yüksekliğini döner.
        Dönüş: (duration_sec, width, height)
        """
        duration = 0
        width = 0
        height = 0

        try:
            parser = createParser(str(video_path))
            if parser:
                with parser:
                    metadata = extractMetadata(parser)
                    if metadata:
                        if metadata.has("duration"):
                            duration = int(metadata.get("duration").seconds)
                        if metadata.has("width"):
                            width = int(metadata.get("width"))
                        if metadata.has("height"):
                            height = int(metadata.get("height"))
        except Exception:
            pass

        return duration, width, height

    @staticmethod
    async def generate_thumbnail(video_path: Path, output_thumb_path: Optional[Path] = None) -> Optional[Path]:
        """
        FFmpeg kullanarak videonun 1. saniyesinden küçük resim (thumbnail) üretir.
        FFmpeg yoksa None döner.
        """
        if not shutil.which("ffmpeg"):
            return None

        if output_thumb_path is None:
            output_thumb_path = video_path.with_suffix(".jpg")

        # FFmpeg komutu ile 1. saniyeden frame yakala
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", "00:00:01",
            "-i", str(video_path),
            "-vframes", "1",
            "-vf", "scale=320:-1",
            str(output_thumb_path),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()

            if output_thumb_path.exists() and output_thumb_path.stat().st_size > 0:
                return output_thumb_path
        except Exception:
            pass

        return None

    @staticmethod
    def safe_delete_file(file_path: Optional[Union[str, Path]]) -> bool:
        """Dosyayı güvenli bir şekilde siler."""
        if not file_path:
            return False
        try:
            p = Path(file_path)
            if p.exists() and p.is_file():
                p.unlink()
                # Yanında aynı isimli .jpg thumbnail varsa onu da temizle
                thumb = p.with_suffix(".jpg")
                if thumb.exists() and thumb.is_file():
                    thumb.unlink()
                return True
        except Exception:
            pass
        return False
