from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch


from briefly.config import Config, SegmentConfig
from briefly.models import Item
from briefly.pipeline import run_collect, run_script
from briefly.segments import IntroSegment, NewsSegment, get_segment_impl


def test_segment_retrieval():
    intro = get_segment_impl("intro")
    assert isinstance(intro, IntroSegment)
    
    news = get_segment_impl("news")
    assert isinstance(news, NewsSegment)
    
    invalid = get_segment_impl("nonexistent")
    assert invalid is None


def test_segment_ordering():
    config = Config()
    # Define custom ordering in segments
    config.segments = [
        SegmentConfig(id="outro", enabled=True),
        SegmentConfig(id="intro", enabled=True),
    ]
    
    # Check that segment_profile respects the ordering
    assert config.segment_profile == ["outro", "intro"]


def test_segment_enable_disable():
    config = Config()
    config.segments = [
        SegmentConfig(id="intro", enabled=True),
        SegmentConfig(id="news", enabled=False),
        SegmentConfig(id="topics", enabled=True),
        SegmentConfig(id="outro", enabled=False),
    ]
    
    assert config.segment_profile == ["intro", "topics"]


@patch("briefly.sources.rss.RssSource")
def test_collect_skips_disabled_segments(mock_rss_class, tmp_path):
    config = Config()
    config.sources.inbox.path = tmp_path / "inbox"
    config.sources.inbox.path.mkdir(parents=True, exist_ok=True)
    
    # Create an inbox file
    (config.sources.inbox.path / "note.txt").write_text("Inbox note content", encoding="utf-8")
    
    # Disable topics segment (which collects inbox and non-news RSS)
    config.segments = [
        SegmentConfig(id="intro", enabled=True),
        SegmentConfig(id="news", enabled=True),
        SegmentConfig(id="topics", enabled=False),
        SegmentConfig(id="outro", enabled=True),
    ]
    
    # Mock news rss items
    mock_source = MagicMock()
    mock_source.fetch.return_value = [
        Item(id="1", title="News Item", content="Content", source_type="rss", source_name="news-source", topic="news")
    ]
    mock_rss_class.return_value = mock_source
    
    items = run_collect(config)
    
    # Should only collect from enabled segments (news)
    # The inbox item in topics segment should be skipped because topics is disabled
    assert len(items) == 1
    assert items[0].title == "News Item"


def test_segment_script_failure_graceful_degradation():
    config = Config()
    config.segments = [
        SegmentConfig(id="intro", enabled=True),
        SegmentConfig(id="news", enabled=True),
    ]
    
    grouped = {
        "intro": [],
        "news": [Item(id="1", title="News", content="Content", source_type="rss", source_name="source", topic="news")]
    }
    
    mock_llm = MagicMock()
    # Mock script generation: intro segment succeeds, news segment raises exception
    def side_effect(prompt):
        if "news" in prompt:
            raise RuntimeError("LLM error during news script generation")
        return "Intro script generated successfully"
    mock_llm.generate_segment_text.side_effect = side_effect
    
    script = run_script(grouped, config, llm_provider=mock_llm)
    
    # The run should not crash and should produce script segments excluding the failed one
    assert len(script.segments) == 1
    assert script.segments[0].name == "intro"
    assert script.segments[0].text == "Intro script generated successfully"


def test_greeting_segment_en():
    config = Config()
    config.user_name = "Anselm"
    segment = get_segment_impl("greeting")
    
    # Saturday, July 4th, 2026
    d = date(2026, 7, 4)
    res = segment.script(config, None, None, "en", episode_date=d)
    assert res == "Good morning, Anselm. It's Saturday, July 4th."

    # Wednesday, July 1st, 2026 (1st suffix)
    d = date(2026, 7, 1)
    res = segment.script(config, None, None, "en", episode_date=d)
    assert res == "Good morning, Anselm. It's Wednesday, July 1st."

    # Thursday, July 2nd, 2026 (2nd suffix)
    d = date(2026, 7, 2)
    res = segment.script(config, None, None, "en", episode_date=d)
    assert res == "Good morning, Anselm. It's Thursday, July 2nd."

    # Friday, July 3rd, 2026 (3rd suffix)
    d = date(2026, 7, 3)
    res = segment.script(config, None, None, "en", episode_date=d)
    assert res == "Good morning, Anselm. It's Friday, July 3rd."

    # Year boundary / Leap year (Friday, Jan 1st, 2027)
    d = date(2027, 1, 1)
    res = segment.script(config, None, None, "en", episode_date=d)
    assert res == "Good morning, Anselm. It's Friday, January 1st."

    # Year boundary (Thursday, Dec 31st, 2026)
    d = date(2026, 12, 31)
    res = segment.script(config, None, None, "en", episode_date=d)
    assert res == "Good morning, Anselm. It's Thursday, December 31st."

    # Eleventh (11th suffix)
    d = date(2026, 7, 11)
    res = segment.script(config, None, None, "en", episode_date=d)
    assert res == "Good morning, Anselm. It's Saturday, July 11th."


def test_greeting_segment_de():
    config = Config()
    config.user_name = "Anselm"
    segment = get_segment_impl("greeting")
    
    # Saturday, July 4th, 2026
    d = date(2026, 7, 4)
    res = segment.script(config, None, None, "de", episode_date=d)
    assert res == "Guten Morgen, Anselm. Es ist Samstag, der 4. Juli."

    # Wednesday, July 1st, 2026
    d = date(2026, 7, 1)
    res = segment.script(config, None, None, "de", episode_date=d)
    assert res == "Guten Morgen, Anselm. Es ist Mittwoch, der 1. Juli."

    # Year boundary (Friday, Jan 1st, 2027)
    d = date(2027, 1, 1)
    res = segment.script(config, None, None, "de", episode_date=d)
    assert res == "Guten Morgen, Anselm. Es ist Freitag, der 1. Januar."

    # Year boundary (Thursday, Dec 31st, 2026)
    d = date(2026, 12, 31)
    res = segment.script(config, None, None, "de", episode_date=d)
    assert res == "Guten Morgen, Anselm. Es ist Donnerstag, der 31. Dezember."


@patch("httpx.get")
def test_weather_collect_and_geocode(mock_get, tmp_path, monkeypatch):
    # Mock config user dir to tmp_path
    monkeypatch.setattr("briefly.segments.get_user_dir", lambda: tmp_path)
    
    config = Config()
    config.weather.location = "Berlin"
    config.weather.latitude = None
    config.weather.longitude = None
    
    # 1. Geocode API response
    mock_geocode_resp = MagicMock()
    mock_geocode_resp.status_code = 200
    mock_geocode_resp.json.return_value = {
        "results": [{"latitude": 52.5243, "longitude": 13.4105}]
    }
    
    # 2. Weather API response
    mock_weather_resp = MagicMock()
    mock_weather_resp.status_code = 200
    mock_weather_resp.json.return_value = {
        "current": {"temperature_2m": 18.5, "weather_code": 3, "wind_speed_10m": 12.0},
        "daily": {
            "temperature_2m_max": [22.0],
            "temperature_2m_min": [14.0],
            "precipitation_probability_max": [40.0]
        }
    }
    
    mock_get.side_effect = [mock_geocode_resp, mock_weather_resp]
    
    segment = get_segment_impl("weather")
    data = segment.collect(config)
    
    assert data is not None
    assert data["current"]["temperature_2m"] == 18.5
    
    # Verify coordinates cache was saved
    cache_file = tmp_path / "weather_cache.json"
    assert cache_file.exists()
    
    # 3. Test Cache Hit: calling again should NOT trigger httpx.get because it's cached!
    mock_get.reset_mock()
    data_cached = segment.collect(config)
    assert data_cached == data
    mock_get.assert_not_called()


@patch("httpx.get")
def test_weather_collect_offline_graceful_degradation(mock_get, tmp_path, monkeypatch):
    monkeypatch.setattr("briefly.segments.get_user_dir", lambda: tmp_path)
    
    config = Config()
    config.weather.location = "Berlin"
    config.weather.latitude = None
    config.weather.longitude = None
    
    # Simulate API down/timeout
    mock_get.side_effect = Exception("Connection timed out")
    
    segment = get_segment_impl("weather")
    data = segment.collect(config)
    
    # Should not crash, just returns None
    assert data is None
    
    # Script on None returns empty string
    res = segment.script(config, data, None, "de")
    assert res == ""


def test_weather_script_en():
    config = Config()
    config.weather.location = "Berlin"
    segment = get_segment_impl("weather")
    
    mock_data = {
        "current": {"temperature_2m": 18.2, "weather_code": 3, "wind_speed_10m": 8.0},
        "daily": {
            "temperature_2m_max": [22.4],
            "temperature_2m_min": [14.1],
            "precipitation_probability_max": [40.0]
        }
    }
    
    res = segment.script(config, mock_data, None, "en")
    assert res == "The weather in Berlin: Currently, it's 18 degrees and overcast. Today's forecast shows a high of 22 degrees and a low of 14 degrees. There is a 40% chance of rain with light winds."


def test_weather_script_de():
    config = Config()
    config.weather.location = "Berlin"
    segment = get_segment_impl("weather")
    
    mock_data = {
        "current": {"temperature_2m": 18.2, "weather_code": 3, "wind_speed_10m": 15.0},
        "daily": {
            "temperature_2m_max": [22.4],
            "temperature_2m_min": [14.1],
            "precipitation_probability_max": [40.0]
        }
    }
    
    res = segment.script(config, mock_data, None, "de")
    assert res == "Das Wetter in Berlin: Aktuell sind es 18 Grad und es ist bedeckt. Heute werden Höchstwerte von 22 Grad und Tiefstwerte von 14 Grad erwartet. Die Regenwahrscheinlichkeit liegt bei 40 Prozent bei mäßigem Wind."


def test_calendar_collect_and_parse(monkeypatch, tmp_path):
    monkeypatch.setattr("briefly.segments.get_user_dir", lambda: tmp_path)
    
    config = Config()
    ics_path = Path(__file__).parent / "fixtures" / "test_calendar.ics"
    
    from briefly.config import CalendarFeedConfig
    config.calendar.feeds = [
        CalendarFeedConfig(url=str(ics_path), include=[], exclude=["excludable"])
    ]
    
    segment = get_segment_impl("calendar")
    data = segment.collect(config)
    
    assert data is not None
    assert len(data) == 5
    
    d = date(2026, 7, 5)
    
    res_de = segment.script(config, data, None, "de", episode_date=d)
    assert "Heute hat Lisa Geburtstag." in res_de
    assert "Meeting with Anselm" in res_de
    assert "Excludable appointment" not in res_de
    assert "Includable task" in res_de
    
    res_en = segment.script(config, data, None, "en", episode_date=d)
    assert "Today is Lisa's birthday." in res_en
    assert "Meeting with Anselm" in res_en
    assert "Excludable appointment" not in res_en


@patch("httpx.get")
def test_calendar_remote_fetch_and_cache(mock_get, tmp_path, monkeypatch):
    monkeypatch.setattr("briefly.segments.get_user_dir", lambda: tmp_path)
    
    config = Config()
    from briefly.config import CalendarFeedConfig
    config.calendar.feeds = [
        CalendarFeedConfig(url="https://remote.com/my_events.ics")
    ]
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Remote Event\nDTSTART:20260705T120000Z\nEND:VEVENT\nEND:VCALENDAR"
    mock_get.return_value = mock_resp
    
    segment = get_segment_impl("calendar")
    data = segment.collect(config)
    
    assert data is not None
    assert len(data) == 1
    assert data[0]["event"]["SUMMARY"]["value"] == "Remote Event"
    
    import hashlib
    url_hash = hashlib.md5("https://remote.com/my_events.ics".encode("utf-8")).hexdigest()
    cache_file = tmp_path / "calendar_cache" / f"{url_hash}.ics"
    assert cache_file.exists()
    
    mock_get.reset_mock()
    data_cached = segment.collect(config)
    assert len(data_cached) == 1
    mock_get.assert_not_called()


@patch("httpx.get")
def test_calendar_fetch_failure_fallback_cache(mock_get, tmp_path, monkeypatch):
    monkeypatch.setattr("briefly.segments.get_user_dir", lambda: tmp_path)
    
    config = Config()
    from briefly.config import CalendarFeedConfig
    config.calendar.feeds = [
        CalendarFeedConfig(url="https://remote.com/my_events.ics")
    ]
    
    import hashlib
    url_hash = hashlib.md5("https://remote.com/my_events.ics".encode("utf-8")).hexdigest()
    cache_dir = tmp_path / "calendar_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{url_hash}.ics"
    cache_file.write_text("BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Cached Old Event\nDTSTART:20260705T120000Z\nEND:VEVENT\nEND:VCALENDAR", encoding="utf-8")
    
    mock_get.side_effect = Exception("Network down")
    
    segment = get_segment_impl("calendar")
    data = segment.collect(config)
    
    assert data is not None
    assert len(data) == 1
    assert data[0]["event"]["SUMMARY"]["value"] == "Cached Old Event"
