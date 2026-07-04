"""Normalisiertes Item-Format zwischen den Pipeline-Stufen."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class Item(BaseModel):
    """Ein einzelner, normalisierter Inhalt aus einer beliebigen ContentSource."""

    id: str
    title: str
    content: str
    source_type: Literal["inbox", "rss"]
    source_name: str
    topic: str | None = None
    priority: int = 0
    published_at: datetime | None = None
    url: str | None = None


class ScriptSegment(BaseModel):
    """Ein Abschnitt des Sprechtext-Skripts (entspricht einem Kapitel)."""

    name: str
    text: str


class EpisodeScript(BaseModel):
    """Das vollständige, vom LLM erzeugte Sprechtext-Skript einer Folge."""

    segments: list[ScriptSegment]


class ChapterMark(BaseModel):
    """Eine Kapitelgrenze in der fertigen Audiodatei."""

    title: str
    start_ms: int
    end_ms: int


class EpisodeManifest(BaseModel):
    """Ergebnis der Audio-Stufe: fertige Audiodatei plus Begleitartefakte."""

    episode_date: date
    audio_path: Path
    transcript_path: Path
    chapters_json_path: Path
    chapters: list[ChapterMark]
