"""RSS-ContentSource: liest konfigurierte Feed-URLs via `feedparser`.

Ein einzelner nicht erreichbarer Feed führt nicht zum Abbruch – er wird
geloggt und übersprungen (Briefing §2.5 Fehlertoleranz).
"""

from __future__ import annotations

import logging
from datetime import datetime
from time import mktime

import feedparser
import httpx

from briefly.config import RssFeedConfig
from briefly.models import Item

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 10.0


class RssSource:
    """Liest Items aus den konfigurierten RSS-Feed-URLs (Briefing §3)."""

    def __init__(self, feeds: list[RssFeedConfig]) -> None:
        self.feeds = feeds

    def fetch(self) -> list[Item]:
        items: list[Item] = []
        for feed_config in self.feeds:
            items.extend(self._fetch_feed(feed_config))
        return items

    def _fetch_feed(self, feed_config: RssFeedConfig) -> list[Item]:
        try:
            response = httpx.get(feed_config.url, timeout=_REQUEST_TIMEOUT_SECONDS, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.warning("RSS-Feed nicht erreichbar, wird übersprungen: %s", feed_config.url)
            return []

        parsed = feedparser.parse(response.content)
        feed_title = parsed.feed.get("title", feed_config.url)
        # Feed-Gewicht auf eine Priority-Skala abbilden (höheres Gewicht -> höhere Priorität).
        priority = round(feed_config.weight * 10)

        items: list[Item] = []
        for index, entry in enumerate(parsed.entries):
            items.append(
                Item(
                    id=f"rss:{feed_config.url}:{entry.get('id', index)}",
                    title=entry.get("title", ""),
                    content=entry.get("summary", entry.get("description", "")),
                    source_type="rss",
                    source_name=feed_title,
                    topic=feed_config.topic,
                    priority=priority,
                    published_at=_parse_published(entry),
                    url=entry.get("link"),
                )
            )
        return items


def _parse_published(entry: feedparser.FeedParserDict) -> datetime | None:
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed_time:
        return None
    return datetime.fromtimestamp(mktime(parsed_time))
