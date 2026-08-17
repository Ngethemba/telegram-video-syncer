import os
import sys
import subprocess
from pathlib import Path
from colorama import Fore, Style, init

from setup_wizard import run_setup_wizard, select_language_prompt, ENV_PATH
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
            subprocess.run([sys.executable, "web_ui.py"])

        elif choice == "9":
            clear_screen()
            new_lang = select_language_prompt()
            update_env_language(new_lang)

        elif choice == "0":
            print(Fore.GREEN + f"\n{t('goodbye', lang)}\n")
            break


if __name__ == "__main__":
    if not is_configured():
        run_setup_wizard()
    main_menu()
