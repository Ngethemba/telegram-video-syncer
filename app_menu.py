import os
import sys
import subprocess
from pathlib import Path
from colorama import Fore, Style, init

from setup_wizard import run_setup_wizard, ENV_PATH

init(autoreset=True)


def is_configured() -> bool:
    """Uygulamanın yapılandırılıp yapılandırılmadığını kontrol eder."""
    if not ENV_PATH.exists():
        return False
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        if "TELEGRAM_API_ID=" in content and "12345678" not in content and "TELEGRAM_API_HASH=" in content:
            return True
    return False


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def main_menu():
    while True:
        clear_screen()
        print(Fore.CYAN + "==================================================================")
        print(Fore.CYAN + "🚀 TELEGRAM MEDYA AKTARICI - ANA KONTROL MENÜSÜ 🚀")
        print(Fore.CYAN + "==================================================================")
        print(Fore.YELLOW + "Lütfen yapmak istediğiniz işlemin numarasını seçin:\n")
        print(f"  {Fore.GREEN}[1]{Fore.WHITE} 📡 Canlı İzleme Modu (Live Monitor - Yeni medyaları anında aktarır)")
        print(f"  {Fore.GREEN}[2]{Fore.WHITE} 📚 Geçmiş Medyaları Tara & Aktar (History - Konudaki tüm medyaları çeker)")
        print(f"  {Fore.GREEN}[3]{Fore.WHITE} 📑 Kaynak Kanaldaki Konuları (Topic) Listele")
        print(f"  {Fore.GREEN}[4]{Fore.WHITE} 📋 Seçmeli Aktarım Modu (Interactive - Listeden tek tek seçerek)")
        print(f"  {Fore.GREEN}[5]{Fore.WHITE} 🔄 Başarısız / Yarım Kalan İşlemleri Tekrar Dene")
        print(f"  {Fore.GREEN}[6]{Fore.WHITE} 📊 Durum ve İstatistik Raporu")
        print(f"  {Fore.GREEN}[7]{Fore.WHITE} ⚙️ Ayarları Düzenle (Kolay Kurulum Sihirbazı)")
        print(f"  {Fore.GREEN}[8]{Fore.WHITE} 🌐 Web Kontrol Panelini Başlat (Tarayıcıdan Yönetim)")
        print(f"  {Fore.RED}[0]{Fore.WHITE} ❌ Çıkış")
        print(Fore.CYAN + "==================================================================")

        choice = input(Fore.YELLOW + "Seçiminiz (0-8): " + Fore.WHITE).strip()

        if choice == "1":
            clear_screen()
            print(Fore.CYAN + "📡 Canlı izleme modu başlatılıyor...\n")
            subprocess.run([sys.executable, "main.py", "live"])
            input(Fore.YELLOW + "\nDevam etmek için ENTER tuşuna basın...")

        elif choice == "2":
            clear_screen()
            print(Fore.CYAN + "📚 Geçmiş tarama seçenekleri:")
            print("  [1] Normal Tarama (Yalnızca aktarılmamış eksik medyaları çeker)")
            print("  [2] Force Tarama (Önceden aktarılanları da sıfırdan tekrar çeker)")
            sub_c = input("Seçiminiz [1]: ").strip()
            
            cmd = [sys.executable, "main.py", "history"]
            if sub_c == "2":
                cmd.append("--force")

            topic_in = input("Yalnızca belirli bir Topic ID'sini taramak ister misiniz? (Boşsa .env ayarı geçerli olur): ").strip()
            if topic_in:
                cmd.extend(["--topic", topic_in])

            clear_screen()
            subprocess.run(cmd)
            input(Fore.YELLOW + "\nDevam etmek için ENTER tuşuna basın...")

        elif choice == "3":
            clear_screen()
            subprocess.run([sys.executable, "main.py", "list-topics"])
            input(Fore.YELLOW + "\nDevam etmek için ENTER tuşuna basın...")

        elif choice == "4":
            clear_screen()
            subprocess.run([sys.executable, "main.py", "interactive"])
            input(Fore.YELLOW + "\nDevam etmek için ENTER tuşuna basın...")

        elif choice == "5":
            clear_screen()
            subprocess.run([sys.executable, "main.py", "retry-failed"])
            input(Fore.YELLOW + "\nDevam etmek için ENTER tuşuna basın...")

        elif choice == "6":
            clear_screen()
            subprocess.run([sys.executable, "main.py", "status"])
            input(Fore.YELLOW + "\nDevam etmek için ENTER tuşuna basın...")

        elif choice == "7":
            clear_screen()
            run_setup_wizard()
            input(Fore.YELLOW + "Devam etmek için ENTER tuşuna basın...")

        elif choice == "8":
            clear_screen()
            print(Fore.CYAN + "🌐 Web kontrol paneli başlatılıyor...")
            subprocess.run([sys.executable, "web_ui.py"])

        elif choice == "0":
            print(Fore.GREEN + "\nGüle güle! 👋\n")
            break


if __name__ == "__main__":
    if not is_configured():
        run_setup_wizard()
    main_menu()
