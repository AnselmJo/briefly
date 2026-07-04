"""Laden und Validieren der YAML-Konfiguration (pydantic)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

# Default-Ausschluss-Themen laut Briefing §2.5: Krieg/Kriminalität/Katastrophen.
DEFAULT_EXCLUDE_KEYWORDS = [
    "Krieg",
    "Kriminalität",
    "Katastrophe",
    "war",
    "crime",
    "disaster",
]

DEFAULT_SEGMENT_PROFILE = ["intro", "news", "topics", "outro"]


class LanguageConfig(BaseModel):
    target: str = "en"


class TopicsConfig(BaseModel):
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class InboxSourceConfig(BaseModel):
    path: Path = Path("data/inbox")


class RssFeedConfig(BaseModel):
    url: str
    topic: str | None = None
    weight: float = 1.0


class RssSourceConfig(BaseModel):
    feeds: list[RssFeedConfig] = Field(default_factory=list)


class SourcesConfig(BaseModel):
    inbox: InboxSourceConfig = Field(default_factory=InboxSourceConfig)
    rss: RssSourceConfig = Field(default_factory=RssSourceConfig)


class LlmConfig(BaseModel):
    provider: Literal["ollama"] = "ollama"
    model: str = "qwen3:8b"


class TtsConfig(BaseModel):
    provider: Literal["piper"] = "piper"
    voice_de: str = "de_DE-thorsten-medium"
    voice_en: str = "en_US-lessac-medium"
    voices_dir: Path = Path("data/voices")


class WebConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8787


class DeliveryConfig(BaseModel):
    provider: Literal["local_feed"] = "local_feed"
    output_dir: Path = Path("output")
    base_url: str = "http://localhost:8787"


class EpisodeConfig(BaseModel):
    target_minutes: int = 10


class Config(BaseModel):
    language: LanguageConfig = Field(default_factory=LanguageConfig)
    topics: TopicsConfig = Field(default_factory=TopicsConfig)
    exclude_keywords: list[str] = Field(default_factory=lambda: list(DEFAULT_EXCLUDE_KEYWORDS))
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    segment_profile: list[str] = Field(default_factory=lambda: list(DEFAULT_SEGMENT_PROFILE))
    llm: LlmConfig = Field(default_factory=LlmConfig)
    tts: TtsConfig = Field(default_factory=TtsConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    episode: EpisodeConfig = Field(default_factory=EpisodeConfig)


def load_config(path: Path) -> Config:
    """Liest eine YAML-Konfigurationsdatei ein und validiert sie."""
    with Path(path).open(encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file) or {}
    return Config.model_validate(raw)


def save_config(config: Config, path: Path) -> None:
    """Schreibt eine Config zurück nach YAML (z.B. aus der Web-Oberfläche)."""
    data = config.model_dump(mode="json")
    with Path(path).open("w", encoding="utf-8") as config_file:
        yaml.safe_dump(data, config_file, sort_keys=False, allow_unicode=True)
