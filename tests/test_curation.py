from datetime import datetime, timedelta

from briefly.config import Config, SegmentConfig
from briefly.curation import group_by_segment, select_items, get_item_budget, token_similarity
from briefly.models import Item


def _make_item(**overrides) -> Item:
    item_id = overrides.get("id", "1")
    defaults = dict(
        id=item_id,
        title=f"title_{item_id}",
        content=f"content_{item_id}",
        source_type="inbox",
        source_name="s"
    )
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


def test_select_items_deduplicates_near_duplicates():
    # Item 1 and Item 2 have very similar titles, but different sources and priorities
    items = [
        _make_item(id="1", title="US Election results are in", content="The results of the US election are finalized.", priority=1, source_name="CNN"),
        _make_item(id="2", title="US Election results finalized", content="The results of the US election are finalized.", priority=2, source_name="BBC"),
        _make_item(id="3", title="Entirely unrelated news article", content="Weather is nice today.", priority=0, source_name="Reuters"),
    ]
    
    config = Config()
    selected = select_items(items, config)
    
    # BBC has higher priority (2 vs 1), so item 2 should be preferred, and source names should be merged
    assert len(selected) == 2
    assert {item.id for item in selected} == {"2", "3"}
    
    merged_item = next(item for item in selected if item.id == "2")
    assert "BBC" in merged_item.source_name
    assert "CNN" in merged_item.source_name


def test_select_items_balances_categories():
    # Target minutes = 2 so budget is very small
    config = Config()
    config.target_minutes = 2  # remaining_words will be small, budget will be capped to 1 or 2
    config.segments = [
        SegmentConfig(id="news", enabled=True),
    ]
    # Enabled only news segment, so non_rss_words is 0.
    # total_words = 2 * 150 = 300.
    # remaining_words = 300.
    # budget = 300 // 100 = 3.
    
    items = [
        # Tech category items
        _make_item(id="1", topic="tech", priority=2),
        _make_item(id="2", topic="tech", priority=2),
        _make_item(id="3", topic="tech", priority=2),
        # Sports category items
        _make_item(id="4", topic="sports", priority=1),
        _make_item(id="5", topic="sports", priority=1),
    ]
    
    selected = select_items(items, config)
    # The budget should select 3 items. Because of category balancing penalty,
    # it should select 2 tech items (higher priority initially) and then 1 sports item
    # instead of a 3rd tech item (as the penalty for tech increases).
    assert len(selected) == 3
    selected_topics = [item.topic for item in selected]
    assert selected_topics.count("tech") == 2
    assert selected_topics.count("sports") == 1


def test_select_items_avoids_history_repeats():
    history = [
        {
            "date": "2026-07-04",
            "titles": ["US election results are in"],
            "topics": ["tech"],
        }
    ]
    
    config = Config()
    # We want to select 1 item
    config.target_minutes = 1  # budget = 1
    config.segments = [SegmentConfig(id="news", enabled=True)]
    
    items = [
        # Item 1 is in history (tech topic repeat)
        _make_item(id="1", topic="tech", priority=2, title="New iphone announced"),
        # Item 2 is in history (title similarity repeat)
        _make_item(id="2", topic="politics", priority=3, title="US election results finalized"),
        # Item 3 is completely new
        _make_item(id="3", topic="sports", priority=1, title="Local team wins game"),
    ]
    
    selected = select_items(items, config, history=history)
    # Even though items 1 and 2 have higher priority (2 and 3), they suffer history repeat penalties.
    # Item 3 (priority 1) should be selected instead.
    assert len(selected) == 1
    assert selected[0].id == "3"


def test_get_item_budget():
    config = Config()
    config.target_minutes = 10
    config.segments = [
        SegmentConfig(id="intro", enabled=True),
        SegmentConfig(id="outro", enabled=True),
        SegmentConfig(id="greeting", enabled=True),
        SegmentConfig(id="weather", enabled=False),
        SegmentConfig(id="calendar", enabled=False),
        SegmentConfig(id="inbox", enabled=False),
        SegmentConfig(id="affirmation", enabled=True),
        SegmentConfig(id="funfact", enabled=False),
    ]
    # total_words = 1500
    # non_rss_words = 50 (intro) + 50 (outro) + 30 (greeting) + 30 (affirmation) = 160
    # remaining_words = 1500 - 160 = 1340
    # budget = 1340 // 100 = 13
    assert get_item_budget(config) == 13


def test_update_history_and_load_history(monkeypatch, tmp_path):
    monkeypatch.setattr("briefly.curation.get_user_dir", lambda: tmp_path)

    from briefly.curation import update_history, load_history

    items = [
        _make_item(id="1", title="Title A", topic="tech"),
        _make_item(id="2", title="Title B", topic=None),
    ]

    update_history(items)

    history = load_history()
    assert len(history) == 1
    assert history[0]["titles"] == ["Title A", "Title B"]
    assert history[0]["topics"] == ["tech"]


