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

    @staticmethod
    async def compress_video(
        video_path: Path,
        output_path: Optional[Path] = None,
        crf: int = 23,
        preset: str = "faster",
        max_resolution: Optional[int] = 1080,
    ) -> Optional[Path]:
        """
        FFmpeg ile videoyu görsel kalite kaybını minimumda tutarak (near-lossless CRF) sıkıştırır.
        - Codec: H.264 (libx264) - Telegram oynatıcısı ile %100 uyumlu
        - Pixel Format: yuv420p (tüm mobil/masaüstü cihazlarda tam destek)
        - Faststart: movflags +faststart (Telegram'da anında oynatma/stream desteği)
        - Audio: aac 128k (şeffaf ses kalitesi)
        - Scale: Çözünürlük max_resolution'dan büyükse orantılı küçültür (örn: 4K -> 1080p).
        
        Eğer sıkıştırılmış dosya orijinalinden daha büyük olursa None döner ve orijinali korur.
        """
        if not shutil.which("ffmpeg"):
            return None

        if not video_path.exists() or video_path.stat().st_size == 0:
            return None

        orig_size = video_path.stat().st_size
        if output_path is None:
            output_path = video_path.parent / f"compressed_{video_path.name}"

        vf_filters = []
        if max_resolution and max_resolution > 0:
            vf_filters.append(f"scale='min({max_resolution},iw)':-2")
        else:
            vf_filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

        vf_str = ",".join(vf_filters)

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-vf", vf_str,
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()

            if output_path.exists() and output_path.stat().st_size > 0:
                comp_size = output_path.stat().st_size
                if comp_size < orig_size:
                    return output_path
                else:
                    try:
                        output_path.unlink()
                    except Exception:
                        pass
                    return None
        except Exception:
            pass

        return None
