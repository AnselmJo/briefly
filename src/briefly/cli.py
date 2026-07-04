"""Kommandozeilen-Einstiegspunkt: jede Pipeline-Stufe einzeln aufrufbar (Briefing §2.7)."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from briefly import pipeline
from briefly.config import Config, load_config
from briefly.models import EpisodeManifest

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path("config.yaml")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    args = _build_parser().parse_args(argv)
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
    for name in ("run", "collect", "curate", "script", "audio", "deliver"):
        subparsers.add_parser(name)
    return parser


def _load_config_or_exit(path: Path) -> Config:
    if not path.exists():
        logger.error(
            "Konfigurationsdatei nicht gefunden: %s. Kopiere config/config.example.yaml nach config.yaml.",
            path,
        )
        sys.exit(1)
    return load_config(path)


if __name__ == "__main__":
    sys.exit(main())
