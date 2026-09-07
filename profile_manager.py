import json
import os
from pathlib import Path
from typing import Dict, List, Optional

ENV_PATH = Path(".env")
PROFILES_DIR = Path("profiles")

DEFAULT_KEYS = [
    "LANGUAGE",
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_PHONE",
    "SESSION_NAME",
    "MEDIA_TYPE",
    "SOURCE_CHANNELS",
    "SOURCE_TOPIC_IDS",
    "TARGET_CHANNEL",
    "TARGET_TOPIC_ID",
    "DOWNLOAD_DIR",
    "AUTO_CLEANUP",
    "MAX_FILE_SIZE_MB",
    "MIN_DURATION_SECONDS",
    "MAX_RETRIES",
    "RETRY_DELAY_SECONDS",
    "DELAY_BETWEEN_UPLOADS",
    "KEEP_ORIGINAL_CAPTION",
    "CUSTOM_CAPTION_PREFIX",
    "CUSTOM_CAPTION_SUFFIX",
    "COMPRESS_VIDEOS",
    "COMPRESS_CRF",
    "COMPRESS_MIN_SIZE_MB",
    "COMPRESS_MAX_RESOLUTION",
]


class ProfileManager:
    """Ayar profillerini JSON formatinda disa/ice aktaran ve yoneten sinif."""
    ENV_PATH = Path(".env")
    PROFILES_DIR = Path("profiles")

    @classmethod
    def ensure_profiles_dir(cls):
        cls.PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_current_settings(cls, env_path: Optional[Path] = None) -> Dict[str, str]:
        """Mevcut .env ayarlarini sozluk olarak okur."""
        target = env_path or cls.ENV_PATH
        settings = {}
        if target.exists():
            with open(target, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        settings[k.strip()] = v.strip()
        return settings

    @classmethod
    def apply_settings(cls, settings: Dict[str, str], env_path: Optional[Path] = None) -> None:
        """Verilen ayarlar sozlugunu .env dosyasina kaydeder."""
        target = env_path or cls.ENV_PATH
        content = f"""# ==============================================================================
# Telegram Media Syncer Configuration File
# Managed by ProfileManager
# ==============================================================================

LANGUAGE={settings.get('LANGUAGE', 'tr')}

TELEGRAM_API_ID={settings.get('TELEGRAM_API_ID', '')}
TELEGRAM_API_HASH={settings.get('TELEGRAM_API_HASH', '')}
TELEGRAM_PHONE={settings.get('TELEGRAM_PHONE', '')}
SESSION_NAME={settings.get('SESSION_NAME', 'telegram_syncer_session')}

MEDIA_TYPE={settings.get('MEDIA_TYPE', 'all')}

SOURCE_CHANNELS={settings.get('SOURCE_CHANNELS', '')}
SOURCE_TOPIC_IDS={settings.get('SOURCE_TOPIC_IDS', '')}

TARGET_CHANNEL={settings.get('TARGET_CHANNEL', '')}
TARGET_TOPIC_ID={settings.get('TARGET_TOPIC_ID', '0')}

DOWNLOAD_DIR={settings.get('DOWNLOAD_DIR', 'downloads')}
AUTO_CLEANUP={settings.get('AUTO_CLEANUP', 'true')}
MAX_FILE_SIZE_MB={settings.get('MAX_FILE_SIZE_MB', '0')}
MIN_DURATION_SECONDS={settings.get('MIN_DURATION_SECONDS', '0')}
MAX_RETRIES={settings.get('MAX_RETRIES', '5')}
RETRY_DELAY_SECONDS={settings.get('RETRY_DELAY_SECONDS', '5')}
DELAY_BETWEEN_UPLOADS={settings.get('DELAY_BETWEEN_UPLOADS', '3')}
KEEP_ORIGINAL_CAPTION={settings.get('KEEP_ORIGINAL_CAPTION', 'true')}
CUSTOM_CAPTION_PREFIX={settings.get('CUSTOM_CAPTION_PREFIX', '')}
CUSTOM_CAPTION_SUFFIX={settings.get('CUSTOM_CAPTION_SUFFIX', '')}

COMPRESS_VIDEOS={settings.get('COMPRESS_VIDEOS', 'false')}
COMPRESS_CRF={settings.get('COMPRESS_CRF', '23')}
COMPRESS_MIN_SIZE_MB={settings.get('COMPRESS_MIN_SIZE_MB', '20')}
COMPRESS_MAX_RESOLUTION={settings.get('COMPRESS_MAX_RESOLUTION', '1080')}
"""
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

    @classmethod
    def export_to_dict(cls, profile_name: str = "default", env_path: Optional[Path] = None) -> Dict:
        """Mevcut ayarlari disari aktarilabilir bir profil objesi olarak doner."""
        settings = cls.get_current_settings(env_path=env_path)
        return {
            "profile_version": "1.0",
            "profile_name": profile_name,
            "exported_at": str(Path(".").stat().st_mtime if Path(".").exists() else ""),
            "settings": settings,
        }

    @classmethod
    def export_to_file(cls, filepath: Path, profile_name: str = "default", env_path: Optional[Path] = None) -> Path:
        """Mevcut ayarlari bir JSON dosyasina kaydeder."""
        data = cls.export_to_dict(profile_name=profile_name, env_path=env_path)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return filepath

    @classmethod
    def import_from_dict(cls, data: Dict, env_path: Optional[Path] = None) -> bool:
        """JSON profil objesinden ayarlari ice aktarip .env'ye yazar."""
        if not isinstance(data, dict):
            return False
        settings = data.get("settings", data)
        if not isinstance(settings, dict):
            return False
        cls.apply_settings(settings, env_path=env_path)
        return True

    @classmethod
    def import_from_file(cls, filepath: Path, env_path: Optional[Path] = None) -> bool:
        """JSON dosyasindan ayarlari ice aktarir."""
        if not filepath.exists():
            return False
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.import_from_dict(data, env_path=env_path)

    @classmethod
    def list_saved_profiles(cls) -> List[str]:
        """profiles/ dizinindeki kayitli profil isimlerini listeler."""
        cls.ensure_profiles_dir()
        profiles = []
        for p in cls.PROFILES_DIR.glob("*.json"):
            profiles.append(p.stem)
        return sorted(profiles)

    @classmethod
    def save_named_profile(cls, name: str) -> Path:
        """Mevcut ayarlari profiles/<name>.json olarak kaydeder."""
        cls.ensure_profiles_dir()
        safe_name = "".join(c for c in name if c.isalnum() or c in ("-", "_")).strip()
        if not safe_name:
            safe_name = "profile"
        target_path = cls.PROFILES_DIR / f"{safe_name}.json"
        return cls.export_to_file(target_path, profile_name=safe_name)

    @classmethod
    def load_named_profile(cls, name: str) -> bool:
        """profiles/<name>.json profilini yukleyip aktif eder."""
        target_path = cls.PROFILES_DIR / f"{name}.json"
        return cls.import_from_file(target_path)
