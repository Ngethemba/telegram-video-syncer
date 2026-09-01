import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


class UpdateManager:
    """Git tabanli guncelleme kontrolu ve tek tikla guncelleme yoneticisi."""

    @staticmethod
    def is_git_repo() -> bool:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            return res.returncode == 0 and "true" in res.stdout.lower()
        except Exception:
            return False

    @staticmethod
    def get_current_commit() -> str:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            return res.stdout.strip() if res.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    @staticmethod
    def check_for_updates() -> Dict:
        """
        origin/main ile yerel commit'i karsilastirir.
        Guncelleme varsa degisiklik listesini ve commit sayisini doner.
        """
        if not UpdateManager.is_git_repo():
            return {
                "success": False,
                "has_update": False,
                "error": "Git deposu bulunamadi."
            }

        try:
            # Uzak depodaki en son bilgiyi cek (yerel degisiklik yapmaz)
            subprocess.run(
                ["git", "fetch", "origin", "main"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=15
            )

            local_res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            remote_res = subprocess.run(
                ["git", "rev-parse", "origin/main"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )

            if local_res.returncode != 0 or remote_res.returncode != 0:
                return {
                    "success": False,
                    "has_update": False,
                    "error": "Git commit bilgileri okunamadi."
                }

            local_hash = local_res.stdout.strip()
            remote_hash = remote_res.stdout.strip()

            local_short = local_hash[:7]
            remote_short = remote_hash[:7]

            if local_hash == remote_hash:
                return {
                    "success": True,
                    "has_update": False,
                    "current_version": local_short,
                    "message": "Uygulamaniz guncel! (En son surumu kullaniyorsunuz)"
                }

            # Bekleyen degisikliklerin ozetini al
            log_res = subprocess.run(
                ["git", "log", f"{local_hash}..{remote_hash}", "--oneline"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            changelog = log_res.stdout.strip().splitlines() if log_res.returncode == 0 else []

            return {
                "success": True,
                "has_update": True,
                "current_version": local_short,
                "latest_version": remote_short,
                "commits_behind": len(changelog),
                "changelog": changelog,
                "message": f"Yeni bir guncelleme mevcut! ({len(changelog)} yeni commit)"
            }
        except Exception as e:
            return {
                "success": False,
                "has_update": False,
                "error": str(e)
            }

    @staticmethod
    def apply_update() -> Dict:
        """
        En son surume gunceller (git reset --hard origin/main).
        Gerekirse dosya izinlerini gunceller.
        """
        if not UpdateManager.is_git_repo():
            return {
                "success": False,
                "error": "Git deposu bulunamadi."
            }

        try:
            # Once en son degisiklikleri cek
            subprocess.run(
                ["git", "fetch", "origin", "main"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=20
            )

            # Calisma agacini origin/main seviyesine guncelle
            reset_res = subprocess.run(
                ["git", "reset", "--hard", "origin/main"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=20
            )

            if reset_res.returncode != 0:
                err = reset_res.stderr.strip() or "Git guncelleme komutu basarisiz."
                return {"success": False, "error": err}

            # Linux/Unix ise script izinlerini yenile
            if sys.platform != "win32":
                try:
                    subprocess.run(["chmod", "+x", "run.sh", "install.sh"], check=False)
                except Exception:
                    pass

            new_commit = UpdateManager.get_current_commit()
            return {
                "success": True,
                "new_version": new_commit,
                "message": f"Uygulama basariyla guncellendi! (Yeni Surum: {new_commit})"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
