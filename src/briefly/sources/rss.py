"""RSS-ContentSource: liest konfigurierte Feed-URLs via `feedparser`.

Ein einzelner nicht erreichbarer Feed führt nicht zum Abbruch – er wird
geloggt und übersprungen (Briefing §2.5 Fehlertoleranz).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from time import mktime
from typing import Any

import feedparser
import httpx

from briefly.config import RssFeedConfig, get_user_dir
from briefly.models import Item

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 10.0


def check_feed_health(url: str) -> dict[str, Any]:
    """Fetches the feed URL and checks its health, returning status, errors, and suggested fixes."""
    result = {
        "status": "ok",
        "error_message": None,
        "suggested_fix": None,
        "item_count": 0,
        "parsed": None,
    }

    try:
        response = httpx.get(url, timeout=_REQUEST_TIMEOUT_SECONDS, follow_redirects=True)
        if response.status_code == 404:
            result["status"] = "error"
            result["error_message"] = "HTTP 404 Not Found"
            result["suggested_fix"] = "Please check the URL. The server returned a 404 error."
            return result
        response.raise_for_status()
    except httpx.ConnectTimeout:
        result["status"] = "error"
        result["error_message"] = "Connection Timeout"
        result["suggested_fix"] = "The server timed out. Check if the connection is slow or the server is down."
        return result
    except httpx.HTTPStatusError as e:
        result["status"] = "error"
        result["error_message"] = f"HTTP Error {e.response.status_code}"
        result["suggested_fix"] = f"Please check the URL. The server returned HTTP {e.response.status_code}."
        return result
    except (httpx.ConnectError, httpx.RequestError) as e:
        result["status"] = "error"
        result["error_message"] = "Wrong URL or DNS Resolution Failed"
        result["suggested_fix"] = "Please check the URL. The domain could not be resolved or is invalid."
        return result
    except Exception as e:
        result["status"] = "error"
        result["error_message"] = f"Request failed: {str(e)}"
        result["suggested_fix"] = "An unexpected error occurred while fetching the URL."
        return result

    try:
        parsed = feedparser.parse(response.content)
        entries = parsed.get("entries", [])

        if not parsed.feed.get("title") and not entries:
            result["status"] = "error"
            result["error_message"] = "Not a valid RSS/Atom feed"
            result["suggested_fix"] = "This URL does not point to a valid RSS or Atom feed. Please verify the URL."
            return result

        result["item_count"] = len(entries)
        result["parsed"] = parsed
    except Exception as e:
        result["status"] = "error"
        result["error_message"] = f"Failed to parse feed: {str(e)}"
        result["suggested_fix"] = "This URL does not point to a valid RSS or Atom feed. Please verify the URL."
        return result

    return result


def load_feed_health() -> dict[str, dict[str, Any]]:
    health_path = get_user_dir() / "feed_health.json"
    if health_path.exists():
        try:
            return json.loads(health_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_feed_health(health_data: dict[str, dict[str, Any]]):
    health_path = get_user_dir() / "feed_health.json"
    try:
        health_path.parent.mkdir(parents=True, exist_ok=True)
        health_path.write_text(json.dumps(health_data), encoding="utf-8")
    except Exception:
        pass


def update_feed_health_status(url: str, check_result: dict[str, Any]):
    health = load_feed_health()
    now_str = datetime.now().isoformat()

    feed_health = health.get(url, {})
    feed_health["last_attempt"] = now_str
    feed_health["status"] = check_result["status"]
    feed_health["error_message"] = check_result["error_message"]
    feed_health["suggested_fix"] = check_result["suggested_fix"]
    feed_health["item_count"] = check_result["item_count"]

    if check_result["status"] == "ok":
        feed_health["last_success"] = now_str

    health[url] = feed_health
    save_feed_health(health)


class RssSource:
    """Liest Items aus den konfigurierten RSS-Feed-URLs (Briefing §3)."""

    def __init__(self, feeds: list[RssFeedConfig]) -> None:
        self.feeds = feeds

    def fetch(self) -> list[Item]:
        items: list[Item] = []
        for feed_config in self.feeds:
            if not getattr(feed_config, "enabled", True):
                continue
            items.extend(self._fetch_feed(feed_config))
        return items

    def _fetch_feed(self, feed_config: RssFeedConfig) -> list[Item]:
        check_res = check_feed_health(feed_config.url)
        update_feed_health_status(feed_config.url, check_res)

        if check_res["status"] == "error":
            logger.warning("RSS-Feed nicht erreichbar, wird übersprungen: %s", feed_config.url)
            return []

        parsed = check_res.get("parsed")
        if not parsed:
            return []

        feed_title = parsed.feed.get("title", feed_config.url)
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
