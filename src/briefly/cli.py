"""Kommandozeilen-Einstiegspunkt: jede Pipeline-Stufe einzeln aufrufbar (Briefing §2.7)."""

from __future__ import annotations

import sys

# Frühe Prüfung auf grundlegende Abhängigkeiten, um unschöne Tracebacks zu vermeiden
try:
    import yaml  # noqa: F401
    import pydantic  # noqa: F401
except ImportError as e:
    missing_name = e.name if hasattr(e, "name") else "pydantic/pyyaml"
    print(f"Fehler: Eine oder mehrere erforderliche Python-Abhängigkeiten fehlen ({missing_name}).", file=sys.stderr)
    print("Behebung: Bitte installiere die Abhängigkeiten mit: pip install -e .", file=sys.stderr)
    sys.exit(1)

import argparse
import logging
from datetime import date
from pathlib import Path

from briefly import pipeline
from briefly.config import Config, load_config, ConfigValidationError, get_default_config_path
from briefly.models import EpisodeManifest

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = get_default_config_path()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        args = _build_parser().parse_args(argv)
        
        if args.command == "install":
            from briefly.install import run_install
            return run_install(interactive=True)

        if args.command == "doctor":
            from briefly.doctor import run_doctor
            return run_doctor()

        if args.command == "update":
            from briefly.update import run_update
            return run_update(Path(args.config))

        if args.command in ("start", "stop", "status", "restart"):
            from briefly.daemon import start_daemon, stop_daemon, status_daemon, restart_daemon
            config_path = Path(args.config)
            if args.command in ("start", "restart", "status"):
                _load_config_or_exit(config_path)
            
            if args.command == "start":
                return start_daemon(config_path)
            elif args.command == "stop":
                return stop_daemon(config_path)
            elif args.command == "status":
                return status_daemon(config_path)
            elif args.command == "restart":
                return restart_daemon(config_path)

        config = _load_config_or_exit(Path(args.config))

        commands = {
            "run": _run_full,
            "collect": _run_collect,
            "curate": _run_curate,
            "script": _run_script,
            "audio": _run_audio,
            "deliver": _run_deliver,
        }
        commands[args.command](config)
        return 0
    except KeyboardInterrupt:
        print("\nAbgebrochen durch Benutzer.", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        if "ffmpeg" in str(e) or (hasattr(e, "filename") and e.filename == "ffmpeg"):
            print("Fehler: 'ffmpeg' wurde nicht im Systempfad gefunden.", file=sys.stderr)
            print("Behebung: Bitte installiere ffmpeg (z. B. via 'brew install ffmpeg' auf macOS).", file=sys.stderr)
        else:
            print(f"Fehler: Datei nicht gefunden: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        err_msg = str(e)
        if "ffmpeg" in err_msg:
            print("Fehler bei der Audio-Verarbeitung mit ffmpeg.", file=sys.stderr)
            print("Details:", err_msg, file=sys.stderr)
            print("Behebung: Bitte stelle sicher, dass ffmpeg korrekt installiert und lauffähig ist ('brew install ffmpeg').", file=sys.stderr)
        else:
            print(f"Fehler: {err_msg}", file=sys.stderr)
        return 1
    except Exception as e:
        err_type = type(e).__name__
        err_msg = str(e)
        if "ConnectError" in err_type or "ConnectTimeout" in err_type or "ConnectionRefusedError" in err_msg or "11434" in err_msg:
            print("Fehler: Verbindung zum Ollama-Server fehlgeschlagen.", file=sys.stderr)
            print("Behebung: Stelle sicher, dass Ollama läuft (https://ollama.com).", file=sys.stderr)
            return 1
        elif "ResponseError" in err_type or ("model" in err_msg.lower() and "not found" in err_msg.lower()):
            print("Fehler: Das konfigurierte Ollama-Modell konnte nicht geladen werden.", file=sys.stderr)
            print("Behebung: Bitte lade das Modell herunter, z.B. via: ollama pull qwen3:8b", file=sys.stderr)
            return 1
        elif "ValidationError" in err_type:
            print("Fehler: Ungültige Konfiguration in config.yaml.", file=sys.stderr)
            print("Details:", err_msg, file=sys.stderr)
            print("Behebung: Überprüfe die Werte und Typen in deiner config.yaml.", file=sys.stderr)
            return 1
        else:
            print(f"Unerwarteter Fehler: {e}", file=sys.stderr)
            return 1


def _run_full(config: Config) -> None:
    manifest = pipeline.run_all(config)
    logger.info("Episode erzeugt und ausgeliefert: %s", manifest.audio_path)


def _run_collect(config: Config) -> None:
    items = pipeline.run_collect(config)
    logger.info("%d Items gesammelt.", len(items))


def _run_curate(config: Config) -> None:
    items = pipeline.run_collect(config)
    grouped = pipeline.run_curate(items, config)
    for name, segment_items in grouped.items():
        logger.info("Segment '%s': %d Items", name, len(segment_items))


def _run_script(config: Config) -> None:
    grouped = pipeline.run_curate(pipeline.run_collect(config), config)
    script = pipeline.run_script(grouped, config)
    for segment in script.segments:
        print(f"## {segment.name}\n{segment.text}\n")


def _run_audio(config: Config) -> None:
    grouped = pipeline.run_curate(pipeline.run_collect(config), config)
    script = pipeline.run_script(grouped, config)
    manifest = pipeline.run_audio(script, config, date.today())
    logger.info("Audiodatei erzeugt: %s", manifest.audio_path)


def _run_deliver(config: Config) -> None:
    manifest = _latest_manifest(config)
    pipeline.run_deliver(manifest, config)
    logger.info("Feed aktualisiert: %s/feed.xml", config.delivery.output_dir)


def _latest_manifest(config: Config) -> EpisodeManifest:
    episodes_dir = config.delivery.output_dir / "episodes"
    audio_files = sorted(episodes_dir.glob("*.m4b"))
    if not audio_files:
        logger.error("Keine Episode in %s gefunden. Führe zuerst 'briefly audio' aus.", episodes_dir)
        sys.exit(1)
    latest_audio = audio_files[-1]
    return EpisodeManifest(
        episode_date=date.fromisoformat(latest_audio.stem),
        audio_path=latest_audio,
        transcript_path=latest_audio.with_suffix(".txt"),
        chapters_json_path=latest_audio.with_name(f"{latest_audio.stem}.chapters.json"),
        chapters=[],
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="briefly", description="Briefly – tägliches Audio-Briefing")
    parser.add_argument("--config", default=str(_DEFAULT_CONFIG_PATH), help="Pfad zur config.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "collect", "curate", "script", "audio", "deliver", "install", "doctor", "start", "stop", "status", "restart", "update"):
        subparsers.add_parser(name)
    return parser


def _load_config_or_exit(path: Path) -> Config:
    if not path.exists():
        print(f"Fehler: Konfigurationsdatei '{path}' nicht gefunden.", file=sys.stderr)
        print("Behebung: Führe 'briefly install' aus, um das Projekt einzurichten und eine Standard-Konfiguration zu erstellen.", file=sys.stderr)
        sys.exit(1)
    try:
        return load_config(path)
    except ConfigValidationError as e:
        print(f"Fehler: Ungültige Konfiguration in '{path}':", file=sys.stderr)
        print(f"  Schlüssel:       {e.key}", file=sys.stderr)
        print(f"  Ungültiger Wert: {e.invalid_value}", file=sys.stderr)
        print(f"  Fehlermeldung:   {e.msg}", file=sys.stderr)
        print(f"  Behebung:        {e.fix}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Fehler: Konfigurationsdatei '{path}' konnte nicht geladen werden.", file=sys.stderr)
        print("Details:", e, file=sys.stderr)
        print("Behebung: Überprüfe die YAML-Syntax in deiner Konfiguration.", file=sys.stderr)
        sys.exit(1)



if __name__ == "__main__":
    sys.exit(main())
