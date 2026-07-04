"""Segment architecture for Briefly.

Each segment represents a discrete module in the daily brief run.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from briefly.config import Config
from briefly.llm.base import LanguageModelProvider
from briefly.models import Item

logger = logging.getLogger(__name__)


WEEKDAYS_EN = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

WEEKDAYS_DE = {
    0: "Montag",
    1: "Dienstag",
    2: "Mittwoch",
    3: "Donnerstag",
    4: "Freitag",
    5: "Samstag",
    6: "Sonntag",
}

MONTHS_EN = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}

MONTHS_DE = {
    1: "Januar",
    2: "Februar",
    3: "März",
    4: "April",
    5: "Mai",
    6: "Juni",
    7: "Juli",
    8: "August",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Dezember",
}


class BaseSegment:
    """Base class for all segment modules."""

    def __init__(self, segment_id: str, enabled: bool = True) -> None:
        self.id = segment_id
        self.enabled = enabled

    def collect(self, config: Config) -> Any:
        """Sammelt Daten für dieses Segment."""
        return None

    def script(
        self,
        config: Config,
        data: Any,
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        """Erzeugt das Skript (Sprechtext) für dieses Segment."""
        return ""


class GreetingSegment(BaseSegment):
    """Greeting segment for the daily episode."""

    def script(
        self,
        config: Config,
        data: Any,
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        d = episode_date or date.today()
        user_name = getattr(config, "user_name", "Anselm")
        
        weekday_idx = d.weekday()
        month_idx = d.month
        
        if language == "de":
            weekday = WEEKDAYS_DE.get(weekday_idx, "")
            month = MONTHS_DE.get(month_idx, "")
            return f"Guten Morgen, {user_name}. Es ist {weekday}, der {d.day}. {month}."
        else:
            weekday = WEEKDAYS_EN.get(weekday_idx, "")
            month = MONTHS_EN.get(month_idx, "")
            
            day = d.day
            if 11 <= day <= 13:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
                
            return f"Good morning, {user_name}. It's {weekday}, {month} {day}{suffix}."


class IntroSegment(BaseSegment):
    """Intro/Begrüßung des täglichen Briefings."""

    def script(
        self,
        config: Config,
        data: Any,
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        prompt = (
            f"Schreibe ein kurzes, freundliches Intro für das persönliche tägliche Audio-Briefing 'Briefly' auf {language}.\n"
            "Begrüße den Hörer und stimme ihn kurz auf den Tag ein. Schreibe ausschließlich den Sprechtext ohne jeglichen Begleittext."
        )
        return llm_provider.generate_segment_text(prompt)


class NewsSegment(BaseSegment):
    """Nachrichten-Segment aus konfigurierten RSS-Feeds (topic == 'news')."""

    def collect(self, config: Config) -> list[Item]:
        from briefly.curation import select_items
        from briefly.sources.rss import RssSource
        
        source = RssSource(config.sources.rss.feeds)
        items = source.fetch()
        selected = select_items(items, config)
        return [item for item in selected if item.topic == "news"]

    def script(
        self,
        config: Config,
        data: list[Item],
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        if not data:
            return ""
        prompt = _build_segment_prompt("news", data, language, config.target_minutes)
        return llm_provider.generate_segment_text(prompt)


class TopicsSegment(BaseSegment):
    """Themen/Inbox-Segment für sonstige RSS-Feeds und persönliche Notizen."""

    def collect(self, config: Config) -> list[Item]:
        from briefly.curation import select_items
        from briefly.sources.inbox import InboxSource
        from briefly.sources.rss import RssSource

        items = []
        try:
            items.extend(InboxSource(config.sources.inbox.path).fetch())
        except Exception as e:
            logger.warning("InboxSource im Topics-Segment fehlgeschlagen: %s", e)

        try:
            items.extend(RssSource(config.sources.rss.feeds).fetch())
        except Exception as e:
            logger.warning("RssSource im Topics-Segment fehlgeschlagen: %s", e)

        selected = select_items(items, config)
        return [item for item in selected if item.topic != "news"]

    def script(
        self,
        config: Config,
        data: list[Item],
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        if not data:
            return ""
        prompt = _build_segment_prompt("topics", data, language, config.target_minutes)
        return llm_provider.generate_segment_text(prompt)


class OutroSegment(BaseSegment):
    """Abschluss und Verabschiedung."""

    def script(
        self,
        config: Config,
        data: Any,
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        prompt = (
            f"Schreibe ein kurzes, freundliches Outro für das persönliche tägliche Audio-Briefing 'Briefly' auf {language}.\n"
            "Verabschiede den Hörer und wünsche ihm einen schönen Tag. Schreibe ausschließlich den Sprechtext ohne jeglichen Begleittext."
        )
        return llm_provider.generate_segment_text(prompt)


def _build_segment_prompt(
    segment_id: str, items: list[Item], language: str, target_minutes: int
) -> str:
    lines = [
        f"Du schreibst den Sprechtext für das Segment '{segment_id}' von 'Briefly', ein persönliches tägliches Audio-Briefing.",
        f"Schreibe die gesamte Ausgabe konsequent auf {language}, auch wenn das Quellmaterial gemischtsprachig ist.",
        f"Dieses Segment hat eine Ziel-Sprechzeit im Verhältnis zur Gesamtlänge von ca. {target_minutes} Minuten.",
        "Schreibe ausschließlich den fertigen Sprechtext für dieses Segment, ohne jegliche Einleitung, ohne Begleittext, und ohne Überschriften.",
        "",
    ]
    if items:
        lines.append(f"### Quellmaterial für das Segment '{segment_id}':")
        for item in items[:15]:
            lines.append(f"- {item.title}: {item.content}")
        lines.append("")
    return "\n".join(lines)


# Registry of segment implementations
_REGISTRY: dict[str, BaseSegment] = {
    "greeting": GreetingSegment("greeting"),
    "intro": IntroSegment("intro"),
    "news": NewsSegment("news"),
    "topics": TopicsSegment("topics"),
    "outro": OutroSegment("outro"),
}


def get_segment_impl(segment_id: str) -> BaseSegment | None:
    """Returns the segment implementation class based on its ID."""
    return _REGISTRY.get(segment_id)
