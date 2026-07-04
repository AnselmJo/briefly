import httpx

from briefly.config import RssFeedConfig
from briefly.sources.rss import RssSource

_SAMPLE_FEED = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Test Feed</title>
<item>
  <title>Hallo Welt</title>
  <description>Ein Testeintrag.</description>
  <link>https://example.com/1</link>
  <pubDate>Mon, 01 Jan 2024 08:00:00 GMT</pubDate>
</item>
</channel></rss>
"""


def test_fetch_parses_feed_items(monkeypatch):
    def fake_get(url, timeout=None, follow_redirects=True):
        return httpx.Response(200, content=_SAMPLE_FEED, request=httpx.Request("GET", url))

    monkeypatch.setattr("briefly.sources.rss.httpx.get", fake_get)

    feed_config = RssFeedConfig(url="https://example.com/rss", topic="news", weight=1.0)
    items = RssSource([feed_config]).fetch()

    assert len(items) == 1
    assert items[0].title == "Hallo Welt"
    assert items[0].topic == "news"
    assert items[0].priority == 10


def test_unreachable_feed_is_skipped_not_fatal(monkeypatch):
    def fake_get(url, timeout=None, follow_redirects=True):
        raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

    monkeypatch.setattr("briefly.sources.rss.httpx.get", fake_get)

    items = RssSource([RssFeedConfig(url="https://example.com/rss")]).fetch()

    assert items == []
