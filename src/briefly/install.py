"""Installations- und Einrichtungs-Assistent für Briefly (Daily Cast).

Ermöglicht eine einfache Einrichtung auch für Python-Neulinge durch:
- Überprüfung von Abhängigkeiten, Ollama, Modellen und Piper-Stimmen.
- Automatisches Erstellen von Konfigurationsdatei und Verzeichnissen.
- Generieren und optionales Installieren von launchd-Diensten auf macOS.
- Überprüfung der Webserver-Konfiguration.
- Ausgeben eines detaillierten Diagnose- und Erfolgsberichts.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

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


def install_launchd_plist(
    plist_name: str, src_path: Path, dest_dir: Path, interactive: bool = True
) -> bool:
    """Kopiert und lädt eine launchd Plist-Datei auf macOS."""
    dest_path = dest_dir / plist_name
    try:
        # Eventuell vorhandenen Dienst vorher entladen
        subprocess.run(["launchctl", "unload", str(dest_path)], capture_output=True, check=False)
        
        # Kopieren
        shutil.copy(src_path, dest_path)
        
        # Berechtigungen sicherstellen (standardmäßig 644 für LaunchAgents)
        dest_path.chmod(0o644)
        
        # Dienst laden
        result = subprocess.run(["launchctl", "load", "-w", str(dest_path)], capture_output=True, check=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Fehler bei launchd-Installation für {plist_name}: {e}", file=sys.stderr)
        return False


def _get_project_root() -> Path:
    """Gibt den Wurzelordner des Projekts zurück."""
    return Path(__file__).resolve().parent.parent.parent


def run_install(interactive: bool = True) -> int:
    """Führt den kompletten Installations- und Einrichtungs-Assistenten aus."""
    print("======================================================================")
    print("          Briefly (Daily Cast) - Installations-Assistent")
    print("======================================================================")
    
    project_root = _get_project_root()
    has_errors = False

    
    # 1. Python-Version prüfen
    python_ok = sys.version_info >= (3, 12)
    
    # 2. Python-Abhängigkeiten prüfen
    missing_deps = check_python_dependencies()
    
    # 3. config.yaml anlegen/laden
    config_path = project_root / "config.yaml"
    config_created = False
    local_ip = get_local_ip()
    
    if not config_path.exists():
        example_config_path = project_root / "config" / "config.example.yaml"
        if example_config_path.exists():
            try:
                content = example_config_path.read_text(encoding="utf-8")
                # Lokale IP-Adresse direkt in die Konfiguration eintragen
                content = content.replace("http://<mac-lan-ip>:8787", f"http://{local_ip}:8787")
                config_path.write_text(content, encoding="utf-8")
                config_created = True
            except Exception as e:
                print(f"Fehler: Konfigurationsdatei konnte nicht erstellt werden: {e}", file=sys.stderr)
                has_errors = True
        else:
            print("Fehler: 'config/config.example.yaml' nicht gefunden.", file=sys.stderr)
            has_errors = True

    # Versuchen, die Konfiguration einzulesen (nur wenn keine schwerwiegenden Fehler vorliegen)
    config: Any = None
    if config_path.exists() and not missing_deps:
        try:
            from briefly.config import load_config
            config = load_config(config_path)
        except Exception as e:
            print(f"Fehler: Konfiguration konnte nicht geladen werden: {e}", file=sys.stderr)
            has_errors = True

    # 4. Verzeichnisse anlegen und Schreibrechte prüfen
    write_perms = {}
    if config:
        dirs_to_check = {
            "root": project_root,
            "inbox": project_root / config.sources.inbox.path,
            "voices": project_root / config.tts.voices_dir,
            "output": project_root / config.delivery.output_dir,
            "episodes": project_root / config.delivery.output_dir / "episodes",
        }
        for key, path in dirs_to_check.items():
            write_perms[key] = verify_write_permission(path)
            if not write_perms[key]:
                has_errors = True
    else:
        # Fallback-Verzeichnisse erstellen/prüfen
        for key, rel_path in [("root", ""), ("inbox", "data/inbox"), ("voices", "data/voices"), ("output", "output"), ("episodes", "output/episodes")]:
            path = project_root / rel_path
            write_perms[key] = verify_write_permission(path)

    # 5. ffmpeg prüfen
    ffmpeg_bin = shutil.which("ffmpeg")
    
    # 6. Ollama & Modell prüfen
    ollama_installed = check_ollama_cli() is not None
    ollama_running = is_ollama_running()
    model_name = config.llm.model if config else "qwen3:8b"
    model_ok = False
    
    if ollama_running:
        models = get_ollama_models()
        model_ok = is_model_installed(model_name, models)

    # 7. Piper-Stimmen prüfen
    voices_dir = project_root / (config.tts.voices_dir if config else Path("data/voices"))
    voice_de = config.tts.voice_de if config else "de_DE-thorsten-medium"
    voice_en = config.tts.voice_en if config else "en_US-lessac-medium"
    
    voice_de_ok = check_piper_voice(voice_de, voices_dir)
    voice_en_ok = check_piper_voice(voice_en, voices_dir)

    # 8. launchd Generierung
    launchd_generated = False
    dailyrun_plist = project_root / "output" / "com.briefly.dailyrun.plist"
    web_plist = project_root / "output" / "com.briefly.web.plist"
    
    if write_perms.get("output"):
        # Templates einlesen
        tpl_dir = project_root / "scripts" / "launchd"
        tpl_daily = tpl_dir / "com.briefly.dailyrun.plist"
        tpl_web = tpl_dir / "com.briefly.web.plist"
        
        if tpl_daily.exists() and tpl_web.exists():
            try:
                python_bin = sys.executable
                proj_dir_str = str(project_root.resolve())
                
                # Dailyrun bearbeiten
                content_daily = tpl_daily.read_text(encoding="utf-8")
                content_daily = content_daily.replace("__PYTHON_BIN__", python_bin)
                content_daily = content_daily.replace("__PROJECT_DIR__", proj_dir_str)
                dailyrun_plist.write_text(content_daily, encoding="utf-8")
                
                # Web-Server bearbeiten
                content_web = tpl_web.read_text(encoding="utf-8")
                content_web = content_web.replace("__PYTHON_BIN__", python_bin)
                content_web = content_web.replace("__PROJECT_DIR__", proj_dir_str)
                web_plist.write_text(content_web, encoding="utf-8")
                
                launchd_generated = True
            except Exception as e:
                print(f"Fehler: launchd-Konfigurationsdateien konnten nicht generiert werden: {e}", file=sys.stderr)

    # 9. launchd Installation (falls auf macOS und vom Benutzer bestätigt)
    is_macos = sys.platform == "darwin"
    launchd_installed = False
    
    if is_macos and launchd_generated:
        confirm = False
        if interactive:
            print("\n--- launchd-Dienste konfigurieren ---")
            print("Möchtest du launchd-Dienste auf deinem Mac installieren, um Briefly")
            print("täglich um 05:30 Uhr auszuführen und den Webserver im Hintergrund zu starten? (y/N): ", end="")
            sys.stdout.flush()
            try:
                response = sys.stdin.readline().strip().lower()
                confirm = response in ("y", "yes")
            except Exception:
                confirm = False
        
        if confirm:
            launchagents_dir = Path.home() / "Library" / "LaunchAgents"
            launchagents_dir.mkdir(parents=True, exist_ok=True)
            
            web_ok = install_launchd_plist("com.briefly.web.plist", web_plist, launchagents_dir, interactive)
            daily_ok = install_launchd_plist("com.briefly.dailyrun.plist", dailyrun_plist, launchagents_dir, interactive)
            launchd_installed = web_ok and daily_ok

    # 10. Webserver-Konfiguration prüfen
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
                "Für den Feed-Zugriff per Smartphone im Heim-WLAN sollte hier die lokale IP deines Macs eingetragen sein."
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
    print_status("ffmpeg Audio-Konverter", ffmpeg_bin is not None, info="Gefunden" if ffmpeg_bin else "Fehlt")
    print_status("Ollama Installation", ollama_installed, info="Installiert" if ollama_installed else "Fehlt")
    print_status("Ollama Dienst aktiv", ollama_running, info="Aktiv" if ollama_running else "Nicht aktiv")
    print_status(f"Ollama Modell '{model_name}'", model_ok, info="Vorhanden" if model_ok else "Fehlt")
    print_status("Piper Stimme (DE)", voice_de_ok, info="Geladen" if voice_de_ok else "Fehlt")
    print_status("Piper Stimme (EN)", voice_en_ok, info="Geladen" if voice_en_ok else "Fehlt")
    print_status("Webserver-Konfiguration", web_config_ok, warning=not web_config_ok, info="Optimal" if web_config_ok else "Warnung")
    
    if is_macos:
        print_status("launchd-Dienste", launchd_installed, warning=not launchd_installed and launchd_generated, info="Aktiv" if launchd_installed else "Generiert" if launchd_generated else "Fehlgeschlagen")
    else:
        print_status("launchd-Dienste", False, warning=True, info="Nur auf macOS verfügbar")
        
    print("=" * 70)

    # Behebungsanweisungen ausgeben falls Fehler vorhanden sind
    fatal_error = not python_ok or bool(missing_deps) or not dirs_ok
    
    if fatal_error or not ffmpeg_bin or not ollama_installed or not ollama_running or not model_ok or not voice_de_ok or not voice_en_ok or not web_config_ok:
        print("\n🛠️  FEHLERBEHEBUNG & EMPFEHLUNGEN:")
        
        if not python_ok:
            print("- Python: Bitte installiere Python 3.12 oder neuer auf deinem Mac.")
        if missing_deps:
            print(f"- Python-Pakete: Folgende Abhängigkeiten fehlen: {', '.join(missing_deps)}")
            print("  Behebung: Führe im Projektverzeichnis aus: pip install -e .")
        if not dirs_ok:
            print("- Schreibrechte: Bitte überprüfe die Berechtigungen für folgende Verzeichnisse:")
            for name, perm in write_perms.items():
                if not perm:
                    path_str = str((project_root / (config.sources.inbox.path if config and name == "inbox" else config.tts.voices_dir if config and name == "voices" else config.delivery.output_dir if config and name == "output" else config.delivery.output_dir / "episodes" if config and name == "episodes" else Path())).resolve())
                    print(f"  * {name} ({path_str})")
            print("  Behebung: Nutze 'chmod u+w <pfad>' oder 'chown' im Terminal.")
        if not ffmpeg_bin:
            print("- ffmpeg: Der Audio-Konverter wurde nicht gefunden.")
            print("  Behebung: Installiere ffmpeg auf deinem Mac mit: brew install ffmpeg")
        if not ollama_installed:
            print("- Ollama: Die Anwendung 'Ollama' ist nicht auf deinem System installiert.")
            print("  Behebung: Lade Ollama von https://ollama.com herunter und installiere es.")
        elif not ollama_running:
            print("- Ollama: Der Ollama-Hintergrunddienst läuft nicht.")
            print("  Behebung: Starte die App 'Ollama' über deine Programme.")
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
            print(f"  Behebung: Passe die Werte in der Datei config.yaml an. Empfohlene IP: http://{local_ip}:8787")
            
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
    if not model_ok or not voice_de_ok or not voice_en_ok:
        print("1. [Erforderlich] Lade die fehlenden Modelle und Stimmen herunter (siehe Fehlerbehebung oben).")
        print("2. Führe die Erstellung deines ersten Audio-Briefings aus:")
        print("   briefly run")
    else:
        print("1. Führe die Erstellung deines ersten Audio-Briefings aus:")
        print("   briefly run")
        
    # 2. Webserver starten erklären
    if launchd_installed:
        print("2. Der Webserver läuft bereits im Hintergrund über launchd.")
        print(f"   Du erreichst die Web-Oberfläche unter: http://{local_ip}:8787")
    else:
        print("2. Starte die Web-Oberfläche manuell im Terminal:")
        print(f"   uvicorn briefly.web.app:app --host 0.0.0.0 --port 8787")
        print(f"   Du erreichst sie im Browser unter: http://{local_ip}:8787")
        
    # 3. RSS-Feed abonnieren erklären
    print(f"3. Abonniere den Podcast-Feed in deiner Podcast-App (z. B. AntennaPod) über:")
    print(f"   http://{local_ip}:8787/feed.xml")
    
    print("\n(Du kannst deine RSS-Feeds, Themen und Einstellungen jederzeit über die")
    print("Web-Oberfläche oder direkt in der Datei 'config.yaml' anpassen.)")
    print("======================================================================\n")
    return 0
