"""Installations- und Einrichtungs-Assistent für Briefly (Daily Cast).

Ermöglicht eine einfache Einrichtung auch für Python-Neulinge durch:
- Überprüfung von Abhängigkeiten, Ollama, Modellen und Piper-Stimmen.
- Automatisches Erstellen von Konfigurationsdatei und Verzeichnissen.
- Generieren und optionales Installieren von launchd-Diensten auf macOS
  oder Scheduled Tasks auf Windows.
- Überprüfung der Webserver-Konfiguration.
- Ausgeben eines detaillierten Diagnose- und Erfolgsberichts.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import shutil
import socket
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from briefly import scheduler
from briefly.config import get_default_config_path

# Globale Liste der benötigten Python-Pakete (Verteilungsschlüssel aus pyproject.toml)
REQUIRED_PACKAGES = {
    "pydantic": "pydantic",
    "pyyaml": "yaml",
    "feedparser": "feedparser",
    "httpx": "httpx",
    "ollama": "ollama",
    "piper-tts": "piper",
    "feedgen": "feedgen",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "jinja2": "jinja2",
    "python-multipart": "multipart",
}


def get_local_ip() -> str:
    """Ermittelt die lokale IP-Adresse im Heim-WLAN."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Muss nicht erreichbar sein, dient nur der Routing-Bestimmung
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
    except Exception:
        ip = "127.0.0.1"
    return ip


def check_python_dependencies() -> list[str]:
    """Prüft, ob all benötigten Python-Pakete importiert werden können."""
    missing = []
    for dist_name, import_name in REQUIRED_PACKAGES.items():
        # Erst über metadata probieren, da dies genauer ist
        try:
            importlib.metadata.distribution(dist_name)
        except importlib.metadata.PackageNotFoundError:
            # Fallback: Versuchen, das Modul direkt zu importieren
            try:
                importlib.import_module(import_name)
            except ImportError:
                missing.append(dist_name)
    return missing


def check_ollama_cli() -> str | None:
    """Gibt den Pfad zum Ollama-CLI zurück, falls gefunden."""
    return shutil.which("ollama")


def is_ollama_running() -> bool:
    """Prüft, ob der lokale Ollama-Server erreichbar ist."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def get_ollama_models() -> list[str]:
    """Gibt eine Liste der in Ollama geladenen Modelle zurück."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def is_model_installed(model_name: str, installed_models: list[str]) -> bool:
    """Prüft, ob ein Modell in der Liste der installierten Modelle existiert."""
    target = model_name
    if ":" not in target:
        target = f"{target}:latest"
    
    for m in installed_models:
        if m == target or m == model_name or m.startswith(target) or m.startswith(model_name):
            return True
    return False


def check_piper_voice(voice_name: str, voices_dir: Path) -> bool:
    """Prüft, ob die .onnx und .onnx.json Dateien für eine Piper-Stimme existieren."""
    onnx_file = voices_dir / f"{voice_name}.onnx"
    json_file = voices_dir / f"{voice_name}.onnx.json"
    return onnx_file.is_file() and json_file.is_file()


def verify_write_permission(path: Path) -> bool:
    """Testet, ob Schreibrechte im angegebenen Pfad vorhanden sind."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        return True
    except Exception:
        return False


def check_disk_space(project_root: Path, min_gb: float = 5.0) -> tuple[bool, str]:
    """Prüft, ob genügend Speicherplatz auf dem Datenträger vorhanden ist.

    Returns:
        (success, status_info)
    """
    try:
        usage = shutil.disk_usage(project_root)
        free_gb = usage.free / (1024**3)
        return free_gb >= min_gb, f"{free_gb:.1f} GB frei"
    except Exception as e:
        return False, f"Fehler: {e}"


def check_port_availability(host: str, port: int) -> tuple[bool, str]:
    """Prüft, ob ein Port frei ist.

    Returns:
        (success, status_info)
    """
    try:
        bind_host = "127.0.0.1" if host == "0.0.0.0" else host
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((bind_host, port))
        return True, "Frei"
    except Exception:
        return False, f"Belegt (Port {port})"


def _get_project_root() -> Path:
    """Gibt den Wurzelordner des Projekts zurück."""
    return Path(__file__).resolve().parent.parent.parent


_TTY_NOTICE_PRINTED = False

def read_input_from_tty(prompt_message: str, default_if_no_tty: str = "") -> tuple[str, bool]:
    """Attempts to read from a TTY, falling back to safe defaults if not available."""
    global _TTY_NOTICE_PRINTED
    # Print prompt
    print(prompt_message, end="")
    sys.stdout.flush()
    
    # Try stdin if it's a TTY
    if sys.stdin.isatty():
        try:
            return sys.stdin.readline().strip().lower(), True
        except Exception:
            return "", True
            
    # Try opening /dev/tty or CON
    tty_path = "CON" if sys.platform == "win32" else "/dev/tty"
    try:
        with open(tty_path, "r", encoding="utf-8") as tty:
            return tty.readline().strip().lower(), True
    except Exception:
        # No TTY is available
        if not _TTY_NOTICE_PRINTED:
            print("\nNo terminal detected, skipping interactive prompts, defaults applied")
            _TTY_NOTICE_PRINTED = True
        return default_if_no_tty, False


def run_install(interactive: bool = True, assume_yes: bool = False) -> int:
    """Führt den kompletten Installations- und Einrichtungs-Assistenten aus."""
    print("======================================================================")
    print("          Briefly (Daily Cast) - Installations-Assistent")
    print("======================================================================")
    
    project_root = _get_project_root()
    
    # 1. Python-Version prüfen
    python_ok = sys.version_info >= (3, 12)
    
    # 2. Python-Abhängigkeiten prüfen
    missing_deps = check_python_dependencies()
    
    # 3. config.yaml anlegen/laden
    config_path = get_default_config_path()
    config_created = False
    local_ip = get_local_ip()
    
    if not config_path.exists():
        # Ensure parent folder of config.yaml exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        example_config_path = project_root / "config" / "config.example.yaml"
        if example_config_path.exists():
            try:
                content = example_config_path.read_text(encoding="utf-8")
                content = content.replace("http://<mac-lan-ip>:8787", f"http://{local_ip}:8787")
                config_path.write_text(content, encoding="utf-8")
                config_created = True
            except Exception as e:
                print(f"Fehler: Konfigurationsdatei konnte nicht erstellt werden: {e}", file=sys.stderr)
        else:
            print("Fehler: 'config/config.example.yaml' nicht gefunden.", file=sys.stderr)

    # Versuchen, die Konfiguration einzulesen
    config: Any = None
    config_load_error = None
    if config_path.exists() and not missing_deps:
        try:
            from briefly.config import load_config
            config = load_config(config_path)
        except Exception as e:
            config_load_error = e

    # Wenn die Konfiguration nicht geladen werden konnte, fahre nicht mit den Verzeichnis-Checks fort
    # sondern breche mit einer verständlichen Fehlermeldung ab.
    if config_load_error:
        print("\n❌ Die Konfiguration konnte nicht geladen werden.", file=sys.stderr)
        print("Details:", config_load_error, file=sys.stderr)
        print("Behebung: Bitte überprüfe die YAML-Syntax in deiner 'config.yaml'.", file=sys.stderr)
        return 1

    # 4. Verzeichnisse anlegen und Schreibrechte prüfen
    write_perms = {}
    config_dir = config_path.parent
    if config:
        dirs_to_check = {
            "root": config_dir,
            "inbox": config.sources.inbox.path,
            "voices": config.tts.voices_dir,
            "output": config.delivery.output_dir,
            "episodes": config.delivery.output_dir / "episodes",
        }
        for key, path in dirs_to_check.items():
            write_perms[key] = verify_write_permission(path)
    else:
        # Fallback-Verzeichnisse erstellen/prüfen
        for key, rel_path in [("root", ""), ("inbox", "data/inbox"), ("voices", "data/voices"), ("output", "output"), ("episodes", "output/episodes")]:
            path = config_dir / rel_path
            write_perms[key] = verify_write_permission(path)

    # 5. Speicherplatz prüfen (mindestens 5 GB erforderlich)
    disk_space_ok, disk_space_info = check_disk_space(config_dir, 5.0)

    # 6. ffmpeg prüfen und verifizieren
    ffmpeg_bin = shutil.which("ffmpeg")
    ffmpeg_ok = False
    if ffmpeg_bin:
        try:
            res = subprocess.run([ffmpeg_bin, "-version"], capture_output=True, text=True, timeout=2)
            ffmpeg_ok = res.returncode == 0
        except Exception:
            ffmpeg_ok = False

    # 7. Port-Verfügbarkeit prüfen
    web_host = config.web.host if config else "0.0.0.0"
    web_port = config.web.port if config else 8787
    port_ok, port_info = check_port_availability(web_host, web_port)

    # 8. Ollama & Modell prüfen
    ollama_installed = check_ollama_cli() is not None
    ollama_running = is_ollama_running()
    model_name = config.llm.model if config else "qwen3:8b"
    model_ok = False
    
    if ollama_running:
        models = get_ollama_models()
        model_ok = is_model_installed(model_name, models)
        if not model_ok:
            print(f"\nOllama-Modell '{model_name}' fehlt. Lade Modell herunter (ollama pull {model_name})...")
            try:
                subprocess.run(["ollama", "pull", model_name], check=True)
                models = get_ollama_models()
                model_ok = is_model_installed(model_name, models)
            except Exception as e:
                print(f"Fehler beim Herunterladen des Modells via 'ollama pull': {e}")

    # 9. Piper-Stimmen prüfen
    voices_dir = config.tts.voices_dir if config else config_path.parent / "data" / "voices"
    voice_de = config.tts.voice_de if config else "de_DE-thorsten-medium"
    voice_en = config.tts.voice_en if config else "en_US-lessac-medium"
    
    voice_de_ok = check_piper_voice(voice_de, voices_dir)
    voice_en_ok = check_piper_voice(voice_en, voices_dir)

    # 10. Scheduler Registrierung
    scheduler_installed = False
    scheduler_prompted = False
    
    hour = config.schedule.hour if config else 5
    minute = config.schedule.minute if config else 30
    
    no_tty_skipped_scheduler = False
    if scheduler.is_macos() or scheduler.is_windows():
        confirm = False
        if assume_yes:
            confirm = True
        elif interactive:
            platform_name = "launchd-Dienste" if scheduler.is_macos() else "Scheduled Tasks"
            schedule_msg = "täglich um 05:30 Uhr auszuführen" if not config else f"täglich um {hour:02d}:{minute:02d} Uhr auszuführen"
            print(f"\n--- {platform_name} konfigurieren ---")
            prompt_str = f"Möchtest du die Hintergrunddienste installieren, um Briefly\n{schedule_msg} und den Webserver im Hintergrund zu starten? (y/N): "
            response, tty_available = read_input_from_tty(prompt_str, default_if_no_tty="n")
            if tty_available:
                confirm = response in ("y", "yes")
            else:
                confirm = False
                no_tty_skipped_scheduler = True
            scheduler_prompted = True
        
        if confirm:
            python_bin = Path(sys.executable)
            web_ok = scheduler.register_web_server(python_bin, project_root, web_host, web_port, interactive)
            daily_ok = scheduler.register_daily_run(python_bin, project_root, hour, minute, interactive)
            scheduler_installed = web_ok and daily_ok

    # 11. Webserver-Konfiguration prüfen (Warnungen)
    web_config_ok = True
    web_warnings = []
    if config:
        if config.web.host != "0.0.0.0":
            web_config_ok = False
            web_warnings.append(
                f"Webserver-Host ist auf '{config.web.host}' statt '0.0.0.0' eingestellt. "
                "Er wird im Heim-WLAN nicht erreichbar sein."
            )
        if "localhost" in config.delivery.base_url or "127.0.0.1" in config.delivery.base_url:
            web_config_ok = False
            web_warnings.append(
                f"delivery.base_url verwendet '{config.delivery.base_url}'. "
                "Für den Feed-Zugriff per Smartphone im Heim-WLAN sollte hier die lokale IP deines Macs/Rechners eingetragen sein."
            )
    else:
        web_config_ok = False

    # Detaillierter Diagnose- und Erfolgsbericht ausgeben
    print("\n" + "=" * 70)
    print("                      SETUP-DIAGNOSEBERICHT")
    print("=" * 70)
    
    def print_status(label: str, success: bool, warning: bool = False, info: str = "") -> None:
        if success:
            mark = " [✓] "
        elif warning:
            mark = " [!] "
        else:
            mark = " [✗] "
        padding = " " * (45 - len(label))
        print(f"{mark}{label}{padding}{info}")

    print_status("Python-Version (>= 3.12)", python_ok, info=f"Python {sys.version.split()[0]}")
    print_status("Python-Abhängigkeiten", not missing_deps, info="Installiert" if not missing_deps else f"{len(missing_deps)} fehlen")
    print_status("Konfigurationsdatei (config.yaml)", config_path.exists(), info="Erstellt" if config_created else "Bereits vorhanden" if config_path.exists() else "Fehlt")
    
    dirs_ok = all(write_perms.values())
    print_status("Verzeichnisse & Schreibrechte", dirs_ok, info="Berechtigungen OK" if dirs_ok else "Schreibrechte fehlen")
    print_status("Speicherplatz (> 5 GB)", disk_space_ok, info=disk_space_info)
    print_status("ffmpeg Audio-Konverter", ffmpeg_ok, info="Gefunden & funktionstüchtig" if ffmpeg_ok else "Fehlgeschlagen/Fehlt" if ffmpeg_bin else "Fehlt")
    print_status("Port-Verfügbarkeit", port_ok, info=port_info)
    print_status("Ollama Installation", ollama_installed, info="Installiert" if ollama_installed else "Fehlt")
    print_status("Ollama Dienst aktiv", ollama_running, info="Aktiv" if ollama_running else "Nicht aktiv")
    print_status(f"Ollama Modell '{model_name}'", model_ok, info="Vorhanden" if model_ok else "Fehlt")
    print_status("Piper Stimme (DE)", voice_de_ok, warning=not voice_de_ok, info="Geladen" if voice_de_ok else "Fehlt (kann gleich installiert werden)")
    print_status("Piper Stimme (EN)", voice_en_ok, warning=not voice_en_ok, info="Geladen" if voice_en_ok else "Fehlt (kann gleich installiert werden)")
    print_status("Webserver-Konfiguration", web_config_ok, warning=not web_config_ok, info="Optimal" if web_config_ok else "Warnung")
    
    if scheduler.is_macos():
        if no_tty_skipped_scheduler:
            print_status("launchd-Dienste", False, warning=True, info="skipped: no interactive terminal")
        else:
            print_status("launchd-Dienste", scheduler_installed, warning=not scheduler_installed and scheduler_prompted, info="Aktiv" if scheduler_installed else "Fehlgeschlagen/Abgelehnt")
    elif scheduler.is_windows():
        if no_tty_skipped_scheduler:
            print_status("Windows Scheduled Tasks", False, warning=True, info="skipped: no interactive terminal")
        else:
            print_status("Windows Scheduled Tasks", scheduler_installed, warning=not scheduler_installed and scheduler_prompted, info="Aktiv" if scheduler_installed else "Fehlgeschlagen/Abgelehnt")
    else:
        print_status("Hintergrund-Dienste", False, warning=True, info="Nur auf macOS/Windows verfügbar")
        
    print("=" * 70)

    # 12. Piper-Stimmen herunterladen falls erforderlich
    download_de = not voice_de_ok
    download_en = not voice_en_ok
    
    if download_de or download_en:
        confirm_download = False
        if assume_yes:
            confirm_download = True
        elif interactive:
            print("\n--- Piper-Stimmen herunterladen ---")
            print("Folgende benötigte Stimmen fehlen auf deinem System:")
            if download_de:
                print(f"  * Deutsch: {voice_de}")
            if download_en:
                print(f"  * Englisch: {voice_en}")
            prompt_str = "Möchtest du diese Stimmen jetzt automatisch herunterladen? (Y/n): "
            response, tty_available = read_input_from_tty(prompt_str, default_if_no_tty="y")
            if tty_available:
                confirm_download = response in ("", "y", "yes")
            else:
                confirm_download = True  # Safe default: download missing voices
        else:
            confirm_download = True
            
        if confirm_download:
            voices_dir.mkdir(parents=True, exist_ok=True)
            for lang, voice, needed in [("DE", voice_de, download_de), ("EN", voice_en, download_en)]:
                if needed:
                    print(f"Lade Stimme ({lang}) herunter: {voice}...")
                    try:
                        subprocess.run(
                            [sys.executable, "-m", "piper.download_voices", voice, "--data-dir", str(voices_dir)],
                            check=True
                        )
                        if lang == "DE":
                            voice_de_ok = True
                        else:
                            voice_en_ok = True
                    except Exception as e:
                        print(f"Fehler beim Herunterladen der Stimme {voice}: {e}")

    # Behebungsanweisungen ausgeben falls Fehler vorhanden sind
    fatal_error = not python_ok or bool(missing_deps) or not dirs_ok or not disk_space_ok or not ffmpeg_ok or not port_ok or not ollama_installed or not ollama_running or not model_ok or not voice_de_ok or not voice_en_ok
    
    if fatal_error or not web_config_ok:
        print("\n🛠️  FEHLERBEHEBUNG & EMPFEHLUNGEN:")
        
        if not python_ok:
            print("- Python-Version veraltet: Briefly benötigt mindestens Python 3.12.")
            print("  Behebung: Bitte installiere Python 3.12 oder neuer auf deinem System.")
        if missing_deps:
            print(f"- Python-Pakete: Folgende Abhängigkeiten fehlen: {', '.join(missing_deps)}")
            print("  Behebung: Führe im Projektverzeichnis aus: pip install -e .")
        if not dirs_ok:
            print("- Schreibrechte: Bitte überprüfe die Berechtigungen für folgende Verzeichnisse:")
            for name, perm in write_perms.items():
                if not perm:
                    if config:
                        p = (config.sources.inbox.path if name == "inbox" else config.tts.voices_dir if name == "voices" else config.delivery.output_dir if name == "output" else config.delivery.output_dir / "episodes" if name == "episodes" else Path())
                    else:
                        p = config_path.parent / ("data/inbox" if name == "inbox" else "data/voices" if name == "voices" else "output" if name == "output" else "output/episodes" if name == "episodes" else "")
                    path_str = str(p.resolve())
                    print(f"  * {name} ({path_str})")
            if scheduler.is_windows():
                print("  Behebung: Führe in cmd/Powershell für die betroffenen Pfade aus:")
                print("    icacls \"<pfad>\" /grant %username%:F")
            else:
                print("  Behebung: Nutze 'chmod u+w <pfad>' oder 'chown' im Terminal.")
        if not disk_space_ok:
            print(f"- Speicherplatz: {disk_space_info} vorhanden.")
            print("  Behebung: Lösche nicht benötigte Dateien oder deinstalliere ungenutzte Ollama-Modelle (z.B. mit 'ollama rm <modell>'), um mindestens 5 GB freien Speicherplatz freizugeben.")
        if not ffmpeg_ok:
            print("- ffmpeg: Der Audio-Konverter wurde nicht gefunden oder funktioniert nicht.")
            if scheduler.is_windows():
                print("  Behebung: Installiere ffmpeg unter Windows mit: winget install Gyan.FFmpeg")
            else:
                print("  Behebung: Installiere ffmpeg auf deinem Mac mit: brew install ffmpeg")
        if not port_ok:
            print(f"- Port belegt: Port {web_port} wird bereits von einem anderen Prozess verwendet.")
            if scheduler.is_windows():
                print("  Behebung: Beende den blockierenden Prozess in cmd/Powershell mit:")
                print(f"    netstat -ano | findstr :{web_port}")
                print("    taskkill /F /PID <PID>")
            else:
                print("  Behebung: Beende den blockierenden Prozess mit:")
                print(f"    lsof -i :{web_port}")
                print("    kill -9 <PID>")
            print("  Oder passe den Port in config.yaml an (z.B. port: 8788).")
        if not ollama_installed:
            print("- Ollama: Die Anwendung 'Ollama' ist nicht auf deinem System installiert.")
            if scheduler.is_windows():
                print("  Behebung: Installiere Ollama via winget mit: winget install Ollama.Ollama")
            else:
                print("  Behebung: Installiere Ollama via Homebrew mit: brew install --cask ollama")
            print("  Alternativ lade es direkt von https://ollama.com herunter.")
        elif not ollama_running:
            print("- Ollama: Der Ollama-Hintergrunddienst läuft nicht.")
            if scheduler.is_windows():
                print("  Behebung: Starte die App 'Ollama' über das Startmenü oder in der Powershell mit:")
                print("    start \"\" \"%LocalAppData%\\Programs\\Ollama\\Ollama.exe\"")
            else:
                print("  Behebung: Starte die App 'Ollama' über deine Programme oder im Terminal mit:")
                print("    open /Applications/Ollama.app")
        elif not model_ok:
            print(f"- Ollama Modell: Das Modell '{model_name}' ist nicht in Ollama geladen.")
            print(f"  Behebung: Führe aus: ollama pull {model_name}")
        if not voice_de_ok:
            print(f"- Piper-Stimme (DE): Die deutsche Stimme '{voice_de}' fehlt.")
            print(f"  Behebung: Führe aus: python -m piper.download_voices {voice_de} --data-dir {voices_dir}")
        if not voice_en_ok:
            print(f"- Piper-Stimme (EN): Die englische Stimme '{voice_en}' fehlt.")
            print(f"  Behebung: Führe aus: python -m piper.download_voices {voice_en} --data-dir {voices_dir}")
        if not web_config_ok and web_warnings:
            for warn in web_warnings:
                print(f"- Webserver: {warn}")
            print(f"  Behebung: Passe die Werte in der Datei config.yaml an. Empfohlene IP: http://{local_ip}:{web_port}")
            
        print("=" * 70)

    if fatal_error:
        print("\n❌ Die Installation konnte aufgrund schwerwiegender Fehler nicht vollständig abgeschlossen werden.")
        print("Bitte behebe die fatalen Probleme und führe 'briefly install' erneut aus.")
        return 1

    # Finaler Erfolgsbildschirm
    print("\n🎉 SETUP ERFOLGREICH ABGESCHLOSSEN!")
    print("======================================")
    print("Briefly ist bereit für den Einsatz!")
    print("\nNÄCHSTE SCHRITTE:")
    
    # 1. Ersten Lauf erklären
    print("1. Starte den ersten Pipeline-Lauf manuell, um dein erstes Audio-Briefing zu erzeugen:")
    print("   briefly run")
        
    # 2. Webserver starten erklären
    if scheduler_installed:
        service_mgr = "launchd" if scheduler.is_macos() else "Task Scheduler"
        print(f"2. Der Webserver läuft bereits im Hintergrund (über {service_mgr}).")
        print(f"   Du erreichst das Dashboard unter: http://{local_ip}:{web_port}")
    else:
        print("2. Starte den Webserver im Hintergrund:")
        print("   briefly start")
        print(f"   Du erreichst das Dashboard unter: http://{local_ip}:{web_port}")
        
    # 3. RSS-Feed abonnieren erklären
    print("3. Abonniere den Podcast-Feed in deiner Podcast-App (z. B. AntennaPod) über:")
    print(f"   http://{local_ip}:{web_port}/feed.xml")
    
    print("\n(Du kannst deine RSS-Feeds, Themen und Einstellungen jederzeit über die")
    print("Web-Oberfläche oder direkt in der Datei 'config.yaml' anpassen.)")
    print("======================================================================\n")
    return 0
