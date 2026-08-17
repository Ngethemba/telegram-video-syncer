import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def _str_to_bool(value: str) -> bool:
    return str(value).lower() in ("true", "1", "yes", "on", "t")


def _normalize_topic_id(raw_id: Union[int, str]) -> int:
    """
    Normalizes 64-bit topic/thread IDs from Telegram Web URLs (e.g. thread=123456)
    and standard MTProto topic IDs (e.g. 5914).
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
            return val % 4294967296
        return val
    except Exception:
        return 0


def _format_channel_id(item: str) -> Union[int, str]:
    """
    Formats channel identifiers. Automatically prepends -100 prefix for supergroups if omitted.
    Example: -1234567890 or 1234567890 -> -1001234567890
    """
    item = str(item).strip()
    if not item:
        return ""
    
    if "#" in item:
        item = item.split("#")[-1]

    if "t.me/" in item:
        item = item.split("t.me/")[-1].replace("/", "")
        if not item.startswith("@") and not item.startswith("-100"):
            item = f"@{item}"

    digits_only = item.replace("-", "").strip()
    if digits_only.isdigit():
        if not item.startswith("-100"):
            return int(f"-100{digits_only}")
        return int(item)

    return item


def _parse_channel_list(value: str) -> List[Union[int, str]]:
    if not value:
        return []
    channels = []
    for item in value.split(","):
        formatted = _format_channel_id(item)
        if formatted:
            channels.append(formatted)
    return channels


def _parse_single_channel(value: str) -> Union[int, str]:
    if not value:
        return ""
    return _format_channel_id(value)


def _parse_topic_list(value: str) -> List[int]:
    if not value:
        return []
    topics = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        tid = _normalize_topic_id(item)
        if tid > 0:
            topics.append(tid)
    return topics


@dataclass
class AppConfig:
    # Language: tr or en
    language: str = field(default_factory=lambda: os.getenv("LANGUAGE", "tr").lower().strip())

    # Telegram API
    api_id: int = field(default_factory=lambda: int(os.getenv("TELEGRAM_API_ID", "0")))
    api_hash: str = field(default_factory=lambda: os.getenv("TELEGRAM_API_HASH", ""))
    phone: str = field(default_factory=lambda: os.getenv("TELEGRAM_PHONE", ""))
    session_name: str = field(default_factory=lambda: os.getenv("SESSION_NAME", "telegram_syncer_session"))

    # Media Type: all, video, photo
    media_type: str = field(
        default_factory=lambda: os.getenv("MEDIA_TYPE", "all").lower().strip()
    )

    # Channels
    source_channels: List[Union[int, str]] = field(
        default_factory=lambda: _parse_channel_list(os.getenv("SOURCE_CHANNELS", ""))
    )
    # Source topic filter (Optional: empty = all topics)
    source_topic_ids: List[int] = field(
        default_factory=lambda: _parse_topic_list(os.getenv("SOURCE_TOPIC_IDS", ""))
    )

    target_channel: Union[int, str] = field(
        default_factory=lambda: _parse_single_channel(os.getenv("TARGET_CHANNEL", ""))
    )
    target_topic_id: int = field(
        default_factory=lambda: _normalize_topic_id(os.getenv("TARGET_TOPIC_ID", "0"))
    )

    # Download & Upload settings
    download_dir: Path = field(
        default_factory=lambda: Path(os.getenv("DOWNLOAD_DIR", "downloads"))
    )
    auto_cleanup: bool = field(
        default_factory=lambda: _str_to_bool(os.getenv("AUTO_CLEANUP", "true"))
    )
    max_file_size_mb: float = field(
        default_factory=lambda: float(os.getenv("MAX_FILE_SIZE_MB", "0"))
    )
    min_duration_seconds: int = field(
        default_factory=lambda: int(os.getenv("MIN_DURATION_SECONDS", "0"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "5"))
    )
    retry_delay_seconds: int = field(
        default_factory=lambda: int(os.getenv("RETRY_DELAY_SECONDS", "5"))
    )
    delay_between_uploads: int = field(
        default_factory=lambda: int(os.getenv("DELAY_BETWEEN_UPLOADS", "3"))
    )

    # Captions
    keep_original_caption: bool = field(
        default_factory=lambda: _str_to_bool(os.getenv("KEEP_ORIGINAL_CAPTION", "true"))
    )
    custom_caption_prefix: str = field(
        default_factory=lambda: os.getenv("CUSTOM_CAPTION_PREFIX", "")
    )
    custom_caption_suffix: str = field(
        default_factory=lambda: os.getenv("CUSTOM_CAPTION_SUFFIX", "")
    )

    # Database
    db_path: Path = field(default_factory=lambda: Path("syncer_database.db"))

    def validate(self) -> None:
        """Validates configuration parameters."""
        errors = []
        if not self.api_id or self.api_id == 0:
            errors.append("TELEGRAM_API_ID is required and must be valid.")
        if not self.api_hash:
            errors.append("TELEGRAM_API_HASH is required.")
        if not self.source_channels:
            errors.append("At least one SOURCE_CHANNELS must be specified.")
        if not self.target_channel:
            errors.append("TARGET_CHANNEL must be specified.")

        if errors:
            raise ValueError("Configuration Error:\n- " + "\n- ".join(errors))

        self.download_dir.mkdir(parents=True, exist_ok=True)


config = AppConfig()
