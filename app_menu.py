import os
import sys
import subprocess
from pathlib import Path
from colorama import Fore, Style, init

from setup_wizard import run_setup_wizard, select_language_prompt, ENV_PATH
from profile_manager import ProfileManager
from update_manager import UpdateManager
from i18n import t, get_active_language

init(autoreset=True)


def is_configured() -> bool:
    if not ENV_PATH.exists():
        return False
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        if "TELEGRAM_API_ID=" in content and "12345678" not in content and "TELEGRAM_API_HASH=" in content:
            return True
    return False


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def update_env_language(new_lang: str):
    """Updates LANGUAGE in .env file."""
    lines = []
    found = False
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("LANGUAGE="):
                    lines.append(f"LANGUAGE={new_lang}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.insert(0, f"LANGUAGE={new_lang}\n")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.environ["LANGUAGE"] = new_lang


def export_profile_interactive(lang: str):
    clear_screen()
    print(Fore.CYAN + "==================================================================")
    print(Fore.CYAN + t('menu_export_profile', lang))
    print(Fore.CYAN + "==================================================================")
    default_name = "telegram_syncer_profile.json"
    prompt_msg = f"Kaydedilecek dosya adi [{default_name}]: " if lang == "tr" else f"Target filename [{default_name}]: "
    fname = input(prompt_msg).strip() or default_name
    if not fname.endswith(".json"):
        fname += ".json"
    
    target_path = Path(fname)
    ProfileManager.export_to_file(target_path, profile_name=target_path.stem)
    print(Fore.GREEN + f"\n{t('profile_exported', lang, path=target_path.resolve())}\n")
    print(Fore.YELLOW + ("Bu dosyayi baska bir bilgisayara kopyalayip ice aktarabilirsiniz!" if lang == "tr" else "You can copy this file to another machine and import it!"))


def import_profile_interactive(lang: str):
    clear_screen()
    print(Fore.CYAN + "==================================================================")
    print(Fore.CYAN + t('menu_import_profile', lang))
    print(Fore.CYAN + "==================================================================")
    
    saved = ProfileManager.list_saved_profiles()
    if saved:
        print(Fore.YELLOW + ("Kayitli Profiller:" if lang == "tr" else "Saved Profiles:"))
        for idx, p in enumerate(saved, 1):
            print(f"  [{idx}] {p}")
        print()

    prompt_msg = "Ice aktarilacak profil dosyasi yolu (orn: telegram_syncer_profile.json): " if lang == "tr" else "Profile file path to import (e.g. telegram_syncer_profile.json): "
    fpath_str = input(prompt_msg).strip()
    if not fpath_str:
        if saved:
            fpath_str = f"profiles/{saved[0]}.json"
        else:
            fpath_str = "telegram_syncer_profile.json"

    fpath = Path(fpath_str)
    if not fpath.exists():
        candidate = Path("profiles") / f"{fpath_str}.json"
        if candidate.exists():
            fpath = candidate

    if ProfileManager.import_from_file(fpath):
        print(Fore.GREEN + f"\n{t('profile_imported', lang)}\n")
    else:
        print(Fore.RED + f"\n{t('profile_import_failed', lang)}\n")


def check_and_apply_update_interactive(lang: str):
    clear_screen()
    print(Fore.CYAN + "==================================================================")
    print(Fore.CYAN + t('menu_update', lang))
    print(Fore.CYAN + "==================================================================")
    print(Fore.YELLOW + t('checking_updates', lang) + "\n")
    
    info = UpdateManager.check_for_updates()
    if not info.get("success"):
        print(Fore.RED + t('update_failed', lang, error=info.get('error', 'Bilinmeyen hata')))
        return

    current = info.get("current_version", "unknown")
    print(Fore.CYAN + f"Mevcut Surum (Current): {current}")

    if not info.get("has_update"):
        print(Fore.GREEN + f"\n{t('update_not_available', lang)}\n")
        return

    latest = info.get("latest_version", "unknown")
    count = info.get("commits_behind", 1)
    changelog = info.get("changelog", [])
    
    print(Fore.YELLOW + f"En Son Surum (Latest): {latest} ({count} yeni guncelleme)")
    print(Fore.CYAN + "\nBekleyen Yenilikler / Changelog:")
    for c in changelog[:10]:
        print(f"  * {c}")
    if len(changelog) > 10:
        print(f"  ... ve {len(changelog) - 10} diger guncelleme")

    prompt = "\nGuncellemeyi simdi yuklemek istiyor musunuz? (E/H) [E]: " if lang == "tr" else "\nDo you want to install this update now? (Y/N) [Y]: "
    ans = input(Fore.YELLOW + prompt).strip().lower()
    if ans in ("", "e", "evet", "y", "yes"):
        print(Fore.YELLOW + "\nGuncelleniyor, lutfen bekleyin...")
        res = UpdateManager.apply_update()
        if res.get("success"):
            print(Fore.GREEN + f"\n{t('update_success', lang, version=res.get('new_version', 'latest'))}\n")
            print(Fore.YELLOW + ("Uygulamanin yeni ozelliklerini kullanmak icin menuden devam edebilirsiniz." if lang == "tr" else "You can continue from the menu to use the updated features."))
        else:
            print(Fore.RED + f"\n{t('update_failed', lang, error=res.get('error', 'Bilinmeyen hata'))}\n")
    else:
        print(Fore.YELLOW + ("Guncelleme iptal edildi." if lang == "tr" else "Update canceled."))


def main_menu():
    while True:
        lang = get_active_language()
        clear_screen()
        print(Fore.CYAN + "==================================================================")
        print(Fore.CYAN + f"{t('app_title', lang)} - {t('menu_title', lang)}")
        print(Fore.CYAN + "==================================================================")
        print(Fore.YELLOW + t('menu_prompt', lang) + "\n")
        print(f"  {Fore.GREEN}{t('menu_live', lang)}")
        print(f"  {Fore.GREEN}{t('menu_history', lang)}")
        print(f"  {Fore.GREEN}{t('menu_list_topics', lang)}")
        print(f"  {Fore.GREEN}{t('menu_interactive', lang)}")
        print(f"  {Fore.GREEN}{t('menu_retry', lang)}")
        print(f"  {Fore.GREEN}{t('menu_status', lang)}")
        print(f"  {Fore.GREEN}{t('menu_wizard', lang)}")
        print(f"  {Fore.GREEN}{t('menu_web', lang)}")
        print(f"  {Fore.CYAN}{t('menu_export_profile', lang)}")
        print(f"  {Fore.CYAN}{t('menu_import_profile', lang)}")
        print(f"  {Fore.MAGENTA}{t('menu_update', lang)}")
        print(f"  {Fore.YELLOW}{t('menu_lang', lang)}")
        print(f"  {Fore.RED}{t('menu_exit', lang)}")
        print(Fore.CYAN + "==================================================================")

        choice = input(Fore.YELLOW + t('choice_prompt', lang) + Fore.WHITE).strip()

        if choice == "1":
            clear_screen()
            subprocess.run([sys.executable, "main.py", "live"])
            input(Fore.YELLOW + "\n" + t('press_enter', lang))

        elif choice == "2":
            clear_screen()
            if lang == "tr":
                print(Fore.CYAN + "Gecmis tarama secenekleri:")
                print("  [1] Normal Tarama (Yalnizca eksik medyalari aktarir)")
                print("  [2] Force Tarama (Onceden aktarilanlari da bastan ceker)")
            else:
                print(Fore.CYAN + "Batch history sync options:")
                print("  [1] Normal Scan (Sync missing media only)")
                print("  [2] Force Scan (Re-download already processed media)")
            sub_c = input("Choice [1]: ").strip()
            
            cmd = [sys.executable, "main.py", "history"]
            if sub_c == "2":
                cmd.append("--force")

            prompt_top = "Topic ID (bos ise .env ayari gecerli olur): " if lang == "tr" else "Topic ID (empty for .env setting): "
            topic_in = input(prompt_top).strip()
            if topic_in:
                cmd.extend(["--topic", topic_in])

            clear_screen()
            subprocess.run(cmd)
            input(Fore.YELLOW + "\n" + t('press_enter', lang))

        elif choice == "3":
            clear_screen()
            subprocess.run([sys.executable, "main.py", "list-topics"])
            input(Fore.YELLOW + "\n" + t('press_enter', lang))

        elif choice == "4":
            clear_screen()
            subprocess.run([sys.executable, "main.py", "interactive"])
            input(Fore.YELLOW + "\n" + t('press_enter', lang))

        elif choice == "5":
            clear_screen()
            subprocess.run([sys.executable, "main.py", "retry-failed"])
            input(Fore.YELLOW + "\n" + t('press_enter', lang))

        elif choice == "6":
            clear_screen()
            subprocess.run([sys.executable, "main.py", "status"])
            input(Fore.YELLOW + "\n" + t('press_enter', lang))

        elif choice == "7":
            clear_screen()
            run_setup_wizard(initial_lang=lang)
            input(Fore.YELLOW + t('press_enter', lang))

        elif choice == "8":
            clear_screen()
            try:
                subprocess.run([sys.executable, "web_ui.py"])
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\n[BILGI] Web paneli durduruldu.")
                time.sleep(1)

        elif choice == "9":
            export_profile_interactive(lang)
            input(Fore.YELLOW + "\n" + t('press_enter', lang))

        elif choice == "10":
            import_profile_interactive(lang)
            input(Fore.YELLOW + "\n" + t('press_enter', lang))

        elif choice == "11":
            check_and_apply_update_interactive(lang)
            input(Fore.YELLOW + "\n" + t('press_enter', lang))

        elif choice == "12":
            clear_screen()
            new_lang = select_language_prompt()
            update_env_language(new_lang)

        elif choice == "0":
            print(Fore.GREEN + f"\n{t('goodbye', lang)}\n")
            break


if __name__ == "__main__":
    import time
    try:
        if not is_configured():
            run_setup_wizard()
        main_menu()
    except KeyboardInterrupt:
        print(Fore.GREEN + f"\n\n{t('goodbye', get_active_language())}\n")
