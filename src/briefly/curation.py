"""Kuratierung: Filtern nach Themen/Ausschluss-Stichwörtern, Zuordnung zu Segmenten."""

from __future__ import annotations

from datetime import datetime

from briefly.config import Config
from briefly.models import Item

# Items ohne Topic gelten laut Briefing §5 weiterhin als verarbeitbar, nur
# ohne Themen-Vorrang – daher werden sie beim Include-Filter nicht verworfen.
_MIN_DATETIME = datetime.min


def select_items(items: list[Item], config: Config) -> list[Item]:
    """Wendet Ausschluss-Filter an und sortiert nach Priorität/Aktualität."""
    selected = [item for item in items if item.topic not in config.topics.exclude]
    selected = [item for item in selected if not _matches_exclude_keyword(item, config.exclude_keywords)]

    if config.topics.include:
        selected = [
            item for item in selected if item.topic is None or item.topic in config.topics.include
        ]

    selected.sort(key=lambda item: (item.priority, item.published_at or _MIN_DATETIME), reverse=True)
    return selected


def group_by_segment(items: list[Item], segment_profile: list[str]) -> dict[str, list[Item]]:
    """Ordnet kuratierte Items den konfigurierten Segmenten zu.

    Konvention: Items mit `topic == "news"` gehen ins `news`-Segment (falls im
    Profil vorhanden), alle übrigen Items (Inbox + sonstige Themen) ins
    `topics`-Segment. Segmente ohne zugeordnete Items (z.B. `intro`/`outro`)
    bleiben als leere Liste bestehen – das LLM erzeugt sie aus einer
    Standard-Anweisung ohne Materialgrundlage.
    """
    buckets: dict[str, list[Item]] = {name: [] for name in segment_profile}
    fallback_segment = _fallback_segment(segment_profile)

    for item in items:
        if item.topic == "news" and "news" in buckets:
            buckets["news"].append(item)
        elif "topics" in buckets:
            buckets["topics"].append(item)
        elif fallback_segment is not None:
            buckets[fallback_segment].append(item)

    return buckets


def _matches_exclude_keyword(item: Item, exclude_keywords: list[str]) -> bool:
    haystack = f"{item.title} {item.content}".lower()
    return any(keyword.lower() in haystack for keyword in exclude_keywords)


def _fallback_segment(segment_profile: list[str]) -> str | None:
    for name in segment_profile:
        if name not in ("intro", "outro"):
            return name
    return segment_profile[-1] if segment_profile else None
