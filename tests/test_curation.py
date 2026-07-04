from datetime import datetime, timedelta

from briefly.config import Config
from briefly.curation import group_by_segment, select_items
from briefly.models import Item


def _make_item(**overrides) -> Item:
    defaults = dict(id="1", title="t", content="c", source_type="inbox", source_name="s")
    defaults.update(overrides)
    return Item(**defaults)


def test_select_items_filters_exclude_keywords():
    config = Config()
    config.exclude_keywords = ["Krieg"]
    items = [_make_item(id="1", title="Krieg in X"), _make_item(id="2", title="Normale Nachricht")]

    selected = select_items(items, config)

    assert [item.id for item in selected] == ["2"]


def test_select_items_topic_include_keeps_untagged_items():
    config = Config()
    config.topics.include = ["books"]
    items = [
        _make_item(id="1", topic="books"),
        _make_item(id="2", topic="sports"),
        _make_item(id="3", topic=None),
    ]

    selected = select_items(items, config)

    assert {item.id for item in selected} == {"1", "3"}


def test_select_items_sorts_by_priority_then_recency():
    now = datetime.now()
    items = [
        _make_item(id="1", priority=0, published_at=now),
        _make_item(id="2", priority=5, published_at=now - timedelta(days=1)),
    ]

    selected = select_items(items, Config())

    assert [item.id for item in selected] == ["2", "1"]


def test_group_by_segment_routes_news_and_topics():
    items = [
        _make_item(id="1", source_type="rss", topic="news"),
        _make_item(id="2", source_type="inbox", topic="books"),
    ]

    grouped = group_by_segment(items, ["intro", "news", "topics", "outro"])

    assert [item.id for item in grouped["news"]] == ["1"]
    assert [item.id for item in grouped["topics"]] == ["2"]
    assert grouped["intro"] == []
    assert grouped["outro"] == []
