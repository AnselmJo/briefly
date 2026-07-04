"""Lokale DeliveryTarget-Implementierung: lokaler Ordner + RSS-XML-Feed.

Feed-Erzeugung (Briefing §9, Punkt 4/5): `feedgen`, trotz seltener Releases
die reifste verfügbare Bibliothek mit vollständigem iTunes-Podcast-Namespace
für Enclosures/Kapiteldauer. Die eingebetteten M4B-Kapitelmarken (siehe
`audio.py`) sind der primäre Kapitel-Mechanismus für Podcast-Apps; die
`chapters.json` wird zusätzlich erzeugt und in den Shownotes verlinkt.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from feedgen.feed import FeedGenerator

from briefly.models import EpisodeManifest

_FEED_TITLE = "Briefly"
_FEED_DESCRIPTION = "Briefly – deine Themen, kurz und persönlich gesprochen, jeden Morgen."


class LocalFeedDeliveryTarget:
    def __init__(self, output_dir: Path, base_url: str) -> None:
        self.output_dir = Path(output_dir)
        self.episodes_dir = self.output_dir / "episodes"
        self.base_url = base_url.rstrip("/")

    def publish(self, manifest: EpisodeManifest) -> None:
        self.episodes_dir.mkdir(parents=True, exist_ok=True)
        self._write_feed()

    def _write_feed(self) -> None:
        feed_generator = FeedGenerator()
        feed_generator.load_extension("podcast")
        feed_generator.title(_FEED_TITLE)
        feed_generator.link(href=f"{self.base_url}/feed.xml", rel="self")
        feed_generator.description(_FEED_DESCRIPTION)
        feed_generator.language("de")

        for audio_path in sorted(self.episodes_dir.glob("*.m4b"), reverse=True):
            self._add_episode_entry(feed_generator, audio_path)

        feed_generator.rss_file(str(self.output_dir / "feed.xml"))

    def _add_episode_entry(self, feed_generator: FeedGenerator, audio_path: Path) -> None:
        episode_date = _parse_episode_date(audio_path)
        audio_url = f"{self.base_url}/episodes/{audio_path.name}"
        chapters_path = audio_path.with_name(f"{audio_path.stem}.chapters.json")

        # order="append": wir iterieren bereits neueste zuerst; feedgens Default
        # ("prepend") würde diese Reihenfolge nochmal umdrehen.
        entry = feed_generator.add_entry(order="append")
        entry.id(audio_url)
        entry.title(f"Briefly – {episode_date:%Y-%m-%d}")
        entry.enclosure(audio_url, str(audio_path.stat().st_size), "audio/mp4")
        entry.published(episode_date.replace(tzinfo=timezone.utc))

        description = f"Episode vom {episode_date:%Y-%m-%d}."
        if chapters_path.exists():
            description += f" Kapitelübersicht: {self.base_url}/episodes/{chapters_path.name}"
        entry.description(description)


def _parse_episode_date(audio_path: Path) -> datetime:
    try:
        return datetime.strptime(audio_path.stem, "%Y-%m-%d")
    except ValueError:
        return datetime.fromtimestamp(audio_path.stat().st_mtime)
