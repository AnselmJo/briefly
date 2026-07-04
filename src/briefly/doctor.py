"""Diagnose-Werkzeug 'briefly doctor' zur Überprüfung der Systemumgebung.

Führt umfassende Prüfungen für alle Komponenten durch und gibt eine farbige
Status-Tabelle sowie konkrete Behebungsschritte bei Fehlern aus.
"""

from __future__ import annotations

import os
import sys
import socket
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


class CheckResult:
    def __init__(
        self,
        name: str,
        status: bool,
        details: str,
        fix: str | None = None,
        is_warning: bool = False,
    ):
        self.name = name
        self.status = status
        self.details = details
        self.fix = fix
        self.is_warning = is_warning


def color_status(result: CheckResult) -> str:
    """Gibt das Status-Symbol farbig zurück, falls TTY unterstützt wird."""
    supports_color = sys.stdout.isatty() or os.environ.get("FORCE_COLOR") == "1"
    
    if result.is_warning:
        symbol = "[!] WARNUNG"
        return f"{YELLOW}{symbol}{RESET}" if supports_color else symbol
    elif result.status:
        symbol = "[✓] OK"
        return f"{GREEN}{symbol}{RESET}" if supports_color else symbol
    else:
        symbol = "[✗] FEHLER"
        return f"{RED}{symbol}{RESET}" if supports_color else symbol



def _get_project_root() -> Path:
    """Gibt den Wurzelordner des Projekts zurück."""
    return Path(__file__).resolve().parent.parent.parent


def get_local_ip() -> str:
    """Ermittelt die lokale IP-Adresse im Heim-WLAN."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
    except Exception:
        ip = "127.0.0.1"
    return ip


def check_python() -> CheckResult:
    """Prüft Python-Version und Abhängigkeiten."""
    version_str = sys.version.split()[0]
    if sys.version_info < (3, 12):
        return CheckResult(
            name="Python",
            status=False,
            details=f"Python {version_str} ist zu alt (< 3.12)",
            fix="Bitte installiere Python 3.12 oder neuer auf deinem Mac.",
        )
    
    # Abhängigkeiten prüfen
    from briefly.install import check_python_dependencies
    missing = check_python_dependencies()
    if missing:
        return CheckResult(
            name="Python",
            status=False,
            details=f"Python {version_str} ({len(missing)} Pakete fehlen)",
            fix=f"Fehlende Pakete: {', '.join(missing)}. Behebung: pip install -e .",
        )
    
    return CheckResult(
        name="Python",
        status=True,
        details=f"Python {version_str} (Abhängigkeiten OK)",
    )


def check_config(project_root: Path) -> tuple[CheckResult, Any | None]:
    """Prüft, ob config.yaml vorhanden und valide ist."""
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        return CheckResult(
            name="Konfiguration",
            status=False,
            details="config.yaml nicht gefunden",
            fix="Führe 'briefly install' aus, um eine Standard-Konfiguration zu erstellen.",
        ), None
    
    try:
        from briefly.config import load_config
        config = load_config(config_path)
        return CheckResult(
            name="Konfiguration",
            status=True,
            details="config.yaml geladen und validiert",
        ), config
    except Exception as e:
        return CheckResult(
            name="Konfiguration",
            status=False,
            details=f"Validierungsfehler: {e}",
            fix="Überprüfe die Einstellungen und die YAML-Syntax in deiner config.yaml.",
        ), None


def check_output_folders(project_root: Path, config: Any | None) -> CheckResult:
    """Prüft, ob die benötigten Verzeichnisse vorhanden und beschreibbar sind."""
    from briefly.install import verify_write_permission
    
    dirs = {
        "data/inbox": project_root / (config.sources.inbox.path if config else Path("data/inbox")),
        "data/voices": project_root / (config.tts.voices_dir if config else Path("data/voices")),
        "output": project_root / (config.delivery.output_dir if config else Path("output")),
        "output/episodes": project_root / ((config.delivery.output_dir / "episodes") if config else Path("output/episodes")),
    }
    
    failed_dirs = []
    for name, path in dirs.items():
        if not verify_write_permission(path):
            failed_dirs.append(name)
            
    if failed_dirs:
        return CheckResult(
            name="Ausgabeordner",
            status=False,
            details=f"Schreibrechte fehlen in: {', '.join(failed_dirs)}",
            fix="Passe die Ordner-Rechte im Terminal an (z.B. mit chmod u+w <pfad>).",
        )
    return CheckResult(
        name="Ausgabeordner",
        status=True,
        details="Alle Ordner vorhanden und beschreibbar",
    )


def check_internet() -> CheckResult:
    """Prüft, ob eine Internetverbindung besteht."""
    # Wir pingen Github und Google per HTTP GET
    urls = ["https://www.google.com", "https://github.com"]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BrieflyDoctor/1.0"})
            with urllib.request.urlopen(req, timeout=3) as res:
                if res.status == 200:
                    return CheckResult(
                        name="Internetverbindung",
                        status=True,
                        details="Verbunden mit Google/GitHub",
                    )
        except Exception:
            continue
            
    return CheckResult(
        name="Internetverbindung",
        status=False,
        details="Keine Verbindung zu Google/GitHub möglich",
        fix="Überprüfe deine WLAN-Verbindung, Netzwerkeinstellungen oder Proxy-Konfiguration.",
    )


def check_rss_feeds(config: Any | None) -> CheckResult:
    """Prüft, ob alle konfigurierten RSS-Feeds erreichbar und lesbar sind."""
    if not config:
        return CheckResult(
            name="RSS-Feeds",
            status=False,
            details="Übersprungen (Konfiguration fehlt)",
            is_warning=True,
        )
        
    feeds = config.sources.rss.feeds
    if not feeds:
        return CheckResult(
            name="RSS-Feeds",
            status=True,
            details="Keine Feeds konfiguriert",
        )
        
    import feedparser
    failed_feeds = []
    
    for feed in feeds:
        try:
            req = urllib.request.Request(feed.url, headers={"User-Agent": "BrieflyDoctor/1.0"})
            with urllib.request.urlopen(req, timeout=3) as res:
                content = res.read()
                parsed = feedparser.parse(content)
                if parsed.bozo and not parsed.entries:
                    failed_feeds.append(f"{feed.url} (Ungültiges Format)")
        except Exception as e:
            failed_feeds.append(f"{feed.url} ({e})")
            
    if failed_feeds:
        return CheckResult(
            name="RSS-Feeds",
            status=False,
            details=f"{len(failed_feeds)} von {len(feeds)} Feeds fehlerhaft",
            fix="Überprüfe die Erreichbarkeit und URLs der Feeds in der config.yaml:\n  " + "\n  ".join(failed_feeds),
        )
        
    return CheckResult(
        name="RSS-Feeds",
        status=True,
        details=f"Alle {len(feeds)} Feeds erfolgreich eingelesen",
    )


def check_ollama_installation() -> CheckResult:
    """Prüft, ob das Ollama-CLI installiert ist."""
    from briefly.install import check_ollama_cli
    path = check_ollama_cli()
    if not path:
        return CheckResult(
            name="Ollama-Installation",
            status=False,
            details="Ollama-CLI nicht im PATH gefunden",
            fix="Lade Ollama von https://ollama.com herunter und installiere es.",
        )
    return CheckResult(
        name="Ollama-Installation",
        status=True,
        details=f"Gefunden unter {path}",
    )


def check_ollama_server() -> CheckResult:
    """Prüft, ob der Ollama-Hintergrunddienst erreichbar ist."""
    from briefly.install import is_ollama_running
    if not is_ollama_running():
        return CheckResult(
            name="Ollama-Server",
            status=False,
            details="Server unter localhost:11434 nicht erreichbar",
            fix="Starte die Anwendung 'Ollama' auf deinem Mac.",
        )
    return CheckResult(
        name="Ollama-Server",
        status=True,
        details="Server aktiv auf localhost:11434",
    )


def check_installed_model(config: Any | None) -> CheckResult:
    """Prüft, ob das konfigurierte LLM-Modell geladen ist."""
    model_name = config.llm.model if config else "qwen3:8b"
    
    from briefly.install import is_ollama_running, get_ollama_models, is_model_installed
    if not is_ollama_running():
        return CheckResult(
            name="Installiertes Modell",
            status=False,
            details="Übersprungen (Ollama-Server offline)",
            is_warning=True,
        )
        
    models = get_ollama_models()
    if not is_model_installed(model_name, models):
        return CheckResult(
            name="Installiertes Modell",
            status=False,
            details=f"Modell '{model_name}' fehlt in Ollama",
            fix=f"Führe im Terminal aus: ollama pull {model_name}",
        )
        
    return CheckResult(
        name="Installiertes Modell",
        status=True,
        details=f"Modell '{model_name}' vorhanden",
    )


def check_piper() -> CheckResult:
    """Prüft, ob das piper-tts Paket importiert werden kann."""
    try:
        import piper  # noqa: F401
        return CheckResult(
            name="Piper-Synthesizer",
            status=True,
            details="Piper-Bibliothek importierbar",
        )
    except ImportError:
        return CheckResult(
            name="Piper-Synthesizer",
            status=False,
            details="piper-tts Paket kann nicht importiert werden",
            fix="Führe aus: pip install -e .",
        )


def check_voices(project_root: Path, config: Any | None) -> CheckResult:
    """Prüft, ob die konfigurierten Stimmen heruntergeladen wurden."""
    voices_dir = project_root / (config.tts.voices_dir if config else Path("data/voices"))
    voice_de = config.tts.voice_de if config else "de_DE-thorsten-medium"
    voice_en = config.tts.voice_en if config else "en_US-lessac-medium"
    
    from briefly.install import check_piper_voice
    
    de_ok = check_piper_voice(voice_de, voices_dir)
    en_ok = check_piper_voice(voice_en, voices_dir)
    
    missing = []
    if not de_ok:
        missing.append(f"Deutsch ({voice_de})")
    if not en_ok:
        missing.append(f"Englisch ({voice_en})")
        
    if missing:
        fix_lines = []
        if not de_ok:
            fix_lines.append(f"python -m piper.download_voices {voice_de} --data-dir {voices_dir}")
        if not en_ok:
            fix_lines.append(f"python -m piper.download_voices {voice_en} --data-dir {voices_dir}")
            
        return CheckResult(
            name="Piper-Stimmen",
            status=False,
            details=f"Fehlend: {', '.join(missing)}",
            fix="Lade die Stimmen herunter:\n  " + "\n  ".join(fix_lines),
        )
        
    return CheckResult(
        name="Piper-Stimmen",
        status=True,
        details="Stimmen für DE und EN vorhanden",
    )


def check_web_server(config: Any | None) -> CheckResult:
    """Prüft die Webserver- und Netzwerk-Einstellungen sowie die Erreichbarkeit."""
    if not config:
        return CheckResult(
            name="Web-Server",
            status=False,
            details="Übersprungen (Konfiguration fehlt)",
            is_warning=True,
        )
        
    local_ip = get_local_ip()
    warnings = []
    
    if config.web.host != "0.0.0.0":
        warnings.append(f"Host ist '{config.web.host}' statt '0.0.0.0' (nur lokal erreichbar)")
        
    if "localhost" in config.delivery.base_url or "127.0.0.1" in config.delivery.base_url:
        warnings.append("delivery.base_url zeigt auf localhost (Podcast-Wiedergabe am Handy scheitert)")
        
    # Reachability check
    port = config.web.port
    reachable = False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect(("127.0.0.1", port))
        s.close()
        reachable = True
    except Exception:
        pass

    if not reachable:
        return CheckResult(
            name="Web-Server",
            status=False,
            details=f"Server unter Port {port} nicht erreichbar",
            fix=f"Starte den Webserver mit: uvicorn briefly.web.app:app --host {config.web.host} --port {port}",
        )
        
    if warnings:
        return CheckResult(
            name="Web-Server",
            status=True,
            is_warning=True,
            details="Erreichbar; " + "; ".join(warnings),
            fix=f"Passe config.yaml an. Empfohlene IP für WLAN-Zugriff: http://{local_ip}:{config.web.port}",
        )
        
    return CheckResult(
        name="Web-Server",
        status=True,
        details=f"Erreichbar und optimal konfiguriert (http://{local_ip}:{config.web.port})",
    )


def check_feed_generation() -> CheckResult:
    """Prüft, ob der XML-Podcast-Feed erzeugt werden kann."""
    try:
        from feedgen.feed import FeedGenerator
        fg = FeedGenerator()
        fg.title("Briefly Doctor Test")
        fg.link(href="http://localhost")
        fg.description("Test Feed Generation")
        fg.rss_str()
        
        return CheckResult(
            name="Feed-Generierung",
            status=True,
            details="FeedGenerator erzeugt XML erfolgreich",
        )
    except Exception as e:
        return CheckResult(
            name="Feed-Generierung",
            status=False,
            details=f"Fehler bei FeedGenerator: {e}",
            fix="Installiere feedgen neu: pip install feedgen",
        )


def check_ffmpeg() -> CheckResult:
    """Prüft, ob ffmpeg installiert und funktionsfähig ist."""
    import shutil
    import subprocess
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        cmd = "winget install Gyan.FFmpeg" if sys.platform == "win32" or sys.platform == "cygwin" else "brew install ffmpeg"
        return CheckResult(
            name="ffmpeg",
            status=False,
            details="ffmpeg nicht im PATH gefunden",
            fix=f"Installiere ffmpeg: {cmd}",
        )
    try:
        res = subprocess.run([ffmpeg_bin, "-version"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            return CheckResult(
                name="ffmpeg",
                status=True,
                details="ffmpeg installiert und funktionsfähig",
            )
        else:
            return CheckResult(
                name="ffmpeg",
                status=False,
                details=f"ffmpeg lieferte Fehlercode {res.returncode}",
                fix="Installiere ffmpeg neu.",
            )
    except Exception as e:
        return CheckResult(
            name="ffmpeg",
            status=False,
            details=f"Fehler beim Ausführen von ffmpeg: {e}",
            fix="Überprüfe deine ffmpeg-Installation.",
        )


def check_feed_xml(config: Any | None) -> CheckResult:
    """Prüft, ob die Datei feed.xml vorhanden und ein gültiges XML-Dokument ist."""
    if not config:
        return CheckResult(
            name="feed.xml-Validierung",
            status=False,
            details="Übersprungen (Konfiguration fehlt)",
            is_warning=True,
        )
    
    feed_path = config.delivery.output_dir / "feed.xml"
    if not feed_path.exists():
        return CheckResult(
            name="feed.xml-Validierung",
            status=False,
            details="feed.xml existiert noch nicht",
            fix="Erzeuge das erste Briefing mit: briefly run",
        )
        
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(feed_path)
        root = tree.getroot()
        if "feed" not in root.tag and "rss" not in root.tag:
            return CheckResult(
                name="feed.xml-Validierung",
                status=False,
                details="feed.xml ist kein gültiger RSS/Atom-Feed",
                fix="Erzeuge die Datei neu mit: briefly run",
            )
        return CheckResult(
            name="feed.xml-Validierung",
            status=True,
            details="feed.xml vorhanden und valides XML",
        )
    except Exception as e:
        return CheckResult(
            name="feed.xml-Validierung",
            status=False,
            details=f"Fehler beim XML-Parsen von feed.xml: {e}",
            fix="Lösche die defekte Datei und erzeuge sie neu mit: briefly run",
        )


def check_launchd_services() -> CheckResult:
    """Prüft, ob die launchd-Dienste (macOS) oder Scheduled Tasks (Windows) geladen sind."""
    from briefly import scheduler
    
    if sys.platform == "darwin":
        plist_dir = Path.home() / "Library" / "LaunchAgents"
        ok_daily, msg_daily = scheduler.check_daily_run_status()
        ok_web, msg_web = scheduler.check_web_server_status()
        
        if not ok_daily or not ok_web:
            unloaded = []
            if not ok_daily:
                unloaded.append(scheduler.MACOS_DAILY_LABEL)
            if not ok_web:
                unloaded.append(scheduler.MACOS_WEB_LABEL)
            fix_lines = [f"launchctl load -w {plist_dir}/{srv}.plist" for srv in unloaded]
            return CheckResult(
                name="launchd-Dienste",
                status=False,
                details=f"Dienste nicht geladen: {', '.join(unloaded)}",
                fix="Lade die Dienste manuell:\n  " + "\n  ".join(fix_lines),
            )
        return CheckResult(
            name="launchd-Dienste",
            status=True,
            details="Dienste geladen und aktiv",
        )
    elif sys.platform == "win32" or sys.platform == "cygwin":
        ok_daily, msg_daily = scheduler.check_daily_run_status()
        ok_web, msg_web = scheduler.check_web_server_status()
        
        if not ok_daily or not ok_web:
            unregistered = []
            if not ok_daily:
                unregistered.append(scheduler.WIN_DAILY_LABEL)
            if not ok_web:
                unregistered.append(scheduler.WIN_WEB_LABEL)
            return CheckResult(
                name="Windows Scheduled Tasks",
                status=False,
                details=f"Tasks nicht registriert: {', '.join(unregistered)}",
                fix="Führe 'briefly install' aus, um die Scheduled Tasks unter Windows einzurichten.",
            )
        return CheckResult(
            name="Windows Scheduled Tasks",
            status=True,
            details="Tasks registriert und aktiv",
        )
    else:
        return CheckResult(
            name="launchd-Dienste",
            status=True,
            is_warning=True,
            details="Übersprungen (Nicht auf macOS/Windows)",
        )



def run_doctor() -> int:
    """Führt alle Diagnose-Checks aus und gibt die Status-Tabelle aus."""
    from briefly.config import get_default_config_path
    project_root = get_default_config_path().parent
    
    print("======================================================================")
    print("                      Briefly (Daily Cast) Doctor")
    print("======================================================================")
    print("Führe System- und Konfigurationsprüfungen durch...\n")
    
    results: list[CheckResult] = []
    
    # 1. Python
    results.append(check_python())
    
    # 2. Config (wichtig für nachfolgende Checks)
    cfg_result, config = check_config(project_root)
    results.append(cfg_result)
    
    # 3. Output folders
    results.append(check_output_folders(project_root, config))
    
    # 4. Internet
    results.append(check_internet())
    
    # 5. RSS-Feeds
    results.append(check_rss_feeds(config))
    
    # 6. Ollama CLI
    results.append(check_ollama_installation())
    
    # 7. Ollama Server
    results.append(check_ollama_server())
    
    # 8. Installed model
    results.append(check_installed_model(config))
    
    # 9. Piper TTS library
    results.append(check_piper())
    
    # 10. Voices
    results.append(check_voices(project_root, config))
    
    # 11. Web Server
    results.append(check_web_server(config))
    
    # 12. Feed generation
    results.append(check_feed_generation())
    
    # 13. feed.xml validation
    results.append(check_feed_xml(config))
    
    # 14. ffmpeg check
    results.append(check_ffmpeg())
    
    # 15. launchd services
    results.append(check_launchd_services())
    
    # Status-Tabelle ausgeben
    print(f"{BOLD}{'Prüfung':<25} {'Status':<15} {'Details'}{RESET}")
    print("-" * 70)
    for r in results:
        status_str = color_status(r)
        # Status-Symbol kann farbige ESC-Sequenzen enthalten, deshalb getrennte Spaltenausgabe
        print(f"{r.name:<25} {status_str:<24} {r.details}")
    print("-" * 70)
    
    # Fehler und Warnungen auflisten
    failures = [r for r in results if not r.status and not r.is_warning]
    warnings = [r for r in results if r.is_warning or (not r.status and r.is_warning)]
    
    if warnings:
        print(f"\n{YELLOW}{BOLD}⚠️  WARNUNGEN:{RESET}")
        for w in warnings:
            print(f"\n* {BOLD}{w.name}{RESET}: {w.details}")
            if w.fix:
                indented_fix = "\n  ".join(w.fix.split("\n"))
                print(f"  {BOLD}Empfehlung:{RESET}\n  {indented_fix}")
                
    if failures:
        print(f"\n{RED}{BOLD}❌ FEHLER GEFUNDEN ({len(failures)}):{RESET}")
        for f in failures:
            print(f"\n* {BOLD}{f.name}{RESET}: {f.details}")
            if f.fix:
                indented_fix = "\n  ".join(f.fix.split("\n"))
                print(f"  {BOLD}Behebungschritt:{RESET}\n  {indented_fix}")
        print("\n" + "=" * 70)
        print("Bitte behebe die aufgelisteten Fehler, damit Briefly einwandfrei läuft.")
        print("=" * 70 + "\n")
        return 1
        
    print(f"\n{GREEN}{BOLD}🎉 ALLES BESTENS! Briefly ist voll funktionsfähig.{RESET}\n")
    return 0
