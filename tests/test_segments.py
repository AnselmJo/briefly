from datetime import date
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
