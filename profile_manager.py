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
]


class ProfileManager:
    """Ayar profillerini JSON formatinda disa/ice aktaran ve yoneten sinif."""

    @staticmethod
    def ensure_profiles_dir():
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_current_settings() -> Dict[str, str]:
        """Mevcut .env ayarlarini sozluk olarak okur."""
        settings = {}
        if ENV_PATH.exists():
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        settings[k.strip()] = v.strip()
        return settings

    @staticmethod
    def apply_settings(settings: Dict[str, str]) -> None:
        """Verilen ayarlar sozlugunu .env dosyasina kaydeder."""
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
"""
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def export_to_dict(profile_name: str = "default") -> Dict:
        """Mevcut ayarlari disari aktarilabilir bir profil objesi olarak doner."""
        settings = ProfileManager.get_current_settings()
        return {
            "profile_version": "1.0",
            "profile_name": profile_name,
            "exported_at": str(Path(".").stat().st_mtime if Path(".").exists() else ""),
            "settings": settings,
        }

    @staticmethod
    def export_to_file(filepath: Path, profile_name: str = "default") -> Path:
        """Mevcut ayarlari bir JSON dosyasina kaydeder."""
        data = ProfileManager.export_to_dict(profile_name=profile_name)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return filepath

    @staticmethod
    def import_from_dict(data: Dict) -> bool:
        """JSON profil objesinden ayarlari ice aktarip .env'ye yazar."""
        if not isinstance(data, dict):
            return False
        settings = data.get("settings", data)
        if not isinstance(settings, dict):
            return False
        ProfileManager.apply_settings(settings)
        return True

    @staticmethod
    def import_from_file(filepath: Path) -> bool:
        """JSON dosyasindan ayarlari ice aktarir."""
        if not filepath.exists():
            return False
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ProfileManager.import_from_dict(data)

    @staticmethod
    def list_saved_profiles() -> List[str]:
        """profiles/ dizinindeki kayitli profil isimlerini listeler."""
        ProfileManager.ensure_profiles_dir()
        profiles = []
        for p in PROFILES_DIR.glob("*.json"):
            profiles.append(p.stem)
        return sorted(profiles)

    @staticmethod
    def save_named_profile(name: str) -> Path:
        """Mevcut ayarlari profiles/<name>.json olarak kaydeder."""
        ProfileManager.ensure_profiles_dir()
        safe_name = "".join(c for c in name if c.isalnum() or c in ("-", "_")).strip()
        if not safe_name:
            safe_name = "profile"
        target_path = PROFILES_DIR / f"{safe_name}.json"
        return ProfileManager.export_to_file(target_path, profile_name=safe_name)

    @staticmethod
    def load_named_profile(name: str) -> bool:
        """profiles/<name>.json profilini yukleyip aktif eder."""
        target_path = PROFILES_DIR / f"{name}.json"
        return ProfileManager.import_from_file(target_path)
