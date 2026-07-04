import httpx
import pytest

from briefly.sources.rss import check_feed_health

_VALID_FEED = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Valid Feed</title>
<item>
  <title>Title 1</title>
  <description>Desc 1</description>
</item>
</channel></rss>
"""

_HTML_PAGE = b"""<!DOCTYPE html>
<html>
<head><title>Not a feed</title></head>
<body>Hello world</body>
</html>
"""


def test_check_feed_health_success(monkeypatch):
    def fake_get(url, timeout=None, follow_redirects=True):
        return httpx.Response(200, content=_VALID_FEED, request=httpx.Request("GET", url))

    monkeypatch.setattr("briefly.sources.rss.httpx.get", fake_get)

    result = check_feed_health("https://example.com/rss")
    assert result["status"] == "ok"
    assert result["error_message"] is None
    assert result["suggested_fix"] is None
    assert result["item_count"] == 1
    assert result["parsed"] is not None
    assert result["parsed"].feed.title == "Valid Feed"


def test_check_feed_health_timeout(monkeypatch):
    def fake_get(url, timeout=None, follow_redirects=True):
        raise httpx.ConnectTimeout("connection timed out", request=httpx.Request("GET", url))

    monkeypatch.setattr("briefly.sources.rss.httpx.get", fake_get)

    result = check_feed_health("https://example.com/rss")
    assert result["status"] == "error"
    assert "Timeout" in result["error_message"]
    assert "timed out" in result["suggested_fix"].lower()


def test_check_feed_health_not_found_404(monkeypatch):
    def fake_get(url, timeout=None, follow_redirects=True):
        response = httpx.Response(404, request=httpx.Request("GET", url))
        return response

    monkeypatch.setattr("briefly.sources.rss.httpx.get", fake_get)

    result = check_feed_health("https://example.com/rss")
    assert result["status"] == "error"
    assert "404" in result["error_message"]
    assert "404" in result["suggested_fix"]


def test_check_feed_health_wrong_url(monkeypatch):
    def fake_get(url, timeout=None, follow_redirects=True):
        raise httpx.ConnectError("Wrong URL", request=httpx.Request("GET", url))

    monkeypatch.setattr("briefly.sources.rss.httpx.get", fake_get)

    result = check_feed_health("https://example.invalid")
    assert result["status"] == "error"
    assert "Wrong URL" in result["error_message"] or "Resolution" in result["error_message"]
    assert "domain" in result["suggested_fix"].lower() or "url" in result["suggested_fix"].lower()


def test_check_feed_health_not_rss(monkeypatch):
    def fake_get(url, timeout=None, follow_redirects=True):
        return httpx.Response(200, content=_HTML_PAGE, request=httpx.Request("GET", url))

    monkeypatch.setattr("briefly.sources.rss.httpx.get", fake_get)

    result = check_feed_health("https://example.com/not-rss")
    assert result["status"] == "error"
    assert "not a valid rss" in result["error_message"].lower() or "not a valid rss" in result["suggested_fix"].lower()
