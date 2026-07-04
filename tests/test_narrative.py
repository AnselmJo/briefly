from datetime import date, datetime
from unittest.mock import MagicMock

from briefly.config import Config, SegmentConfig
from briefly.curation import select_items
from briefly.models import Item
from briefly.pipeline import run_script
from briefly.segments import OutroSegment, _build_segment_prompt


def _make_item(**overrides) -> Item:
    item_id = overrides.get("id", "1")
    defaults = dict(
        id=item_id,
        title=f"title_{item_id}",
        content=f"content_{item_id}",
        source_type="rss",
        source_name="s",
        topic="news"
    )
    defaults.update(overrides)
    return Item(**defaults)


def test_narrative_order_selected_items():
    # Setup items with mixed topics
    items = [
        _make_item(id="1", topic="news", priority=1),
        _make_item(id="2", topic="tech", priority=1),
        _make_item(id="3", topic="news", priority=1),
        _make_item(id="4", topic="sports", priority=1),
        _make_item(id="5", topic="tech", priority=1),
    ]

    config = Config()
    config.target_minutes = 10  # budget will be 10, enough to select all items
    config.segments = [SegmentConfig(id="news", enabled=True)]

    selected = select_items(items, config)

    # The order of topics first seen is news -> tech -> sports
    # So news items should be together, tech items together, and sports items together.
    # Check that they are grouped adjacent
    topics = [item.topic for item in selected]
    
    # We should have all "news" first, then all "tech", then all "sports"
    assert topics == ["news", "news", "tech", "tech", "sports"]


def test_narrative_segment_transitions():
    config = Config()
    config.tts.language = "en"
    config.segments = [
        SegmentConfig(id="greeting", enabled=True),
        SegmentConfig(id="weather", enabled=True),
        SegmentConfig(id="news", enabled=True),
    ]

    grouped_items = {
        "greeting": [],
        "weather": {"current": {"temperature_2m": 20, "weather_code": 0, "wind_speed_10m": 5}},
        "news": [_make_item(id="1", topic="news")]
    }

    mock_llm = MagicMock()
    mock_llm.generate_segment_text.return_value = "Mocked news content."

    # run_script calls script on segments
    script = run_script(grouped_items, config, llm_provider=mock_llm)

    # Verify that transitions are prepended between segments in the final script
    # GreetingSegment is the first segment, so no transition is prepended
    greeting_seg = next(s for s in script.segments if s.name == "greeting")
    assert "Good morning" in greeting_seg.text
    assert "forecast" not in greeting_seg.text

    # WeatherSegment is second. Transition should be prepended:
    # "Let's check the weather forecast next."
    weather_seg = next(s for s in script.segments if s.name == "weather")
    assert weather_seg.text.startswith("Let's check the weather forecast next.")

    # NewsSegment is third. Transition should be prepended:
    # "Turning now to the latest news,"
    news_seg = next(s for s in script.segments if s.name == "news")
    assert news_seg.text.startswith("Turning now to the latest news,")


def test_narrative_outro_dynamic_closing():
    outro = OutroSegment("outro")

    # Case 1: Weather and Calendar enabled
    config_enabled = Config()
    config_enabled.segments = [
        SegmentConfig(id="weather", enabled=True),
        SegmentConfig(id="calendar", enabled=True),
        SegmentConfig(id="outro", enabled=True),
    ]

    mock_llm_1 = MagicMock()
    mock_llm_1.generate_segment_text.return_value = "Outro content"

    outro.script(config_enabled, None, mock_llm_1, "en")
    prompt_1 = mock_llm_1.generate_segment_text.call_args[0][0]
    # Check that prompt instructions reference upcoming weather or day's schedule
    assert "upcoming weather or the day's schedule" in prompt_1

    # Case 2: Weather and Calendar disabled
    config_disabled = Config()
    config_disabled.segments = [
        SegmentConfig(id="weather", enabled=False),
        SegmentConfig(id="calendar", enabled=False),
        SegmentConfig(id="outro", enabled=True),
    ]

    mock_llm_2 = MagicMock()
    mock_llm_2.generate_segment_text.return_value = "Outro content"

    outro.script(config_disabled, None, mock_llm_2, "en")
    prompt_2 = mock_llm_2.generate_segment_text.call_args[0][0]
    # Check that prompt instructions do NOT reference weather or calendar
    assert "upcoming weather or the day's schedule" not in prompt_2


def test_narrative_news_transitions_in_prompt():
    items = [
        _make_item(id="1", title="US election", content="Election finalized"),
        _make_item(id="2", title="Tech stock", content="Stock rises"),
    ]

    prompt = _build_segment_prompt("news", items, "en", 10)
    assert "smooth, natural transitions" in prompt
    assert "Connect the stories" in prompt
    assert "Do not list items or jump abruptly" in prompt
