"""Kuratierung: Filtern nach Themen/Ausschluss-Stichwörtern, Zuordnung zu Segmenten."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from briefly.config import Config, get_user_dir
from briefly.models import Item

_MIN_DATETIME = datetime.min


def token_similarity(text1: str, text2: str) -> float:
    """Calculates lowercase word token Jaccard similarity between two texts."""
    words1 = set(re.findall(r"\w+", text1.lower()))
    words2 = set(re.findall(r"\w+", text2.lower()))
    if not words1 or not words2:
        return 0.0
    return len(words1.intersection(words2)) / len(words1.union(words2))


def _is_better_item(item1: Item, item2: Item) -> bool:
    """Returns True if item1 is preferred over item2 (higher priority, or newer)."""
    if item1.priority != item2.priority:
        return item1.priority > item2.priority
    dt1 = item1.published_at or _MIN_DATETIME
    dt2 = item2.published_at or _MIN_DATETIME
    return dt1 > dt2


def deduplicate_items(items: list[Item]) -> list[Item]:
    """Merges near-duplicate news items across sources based on title/content similarity."""
    merged: list[Item] = []
    for item in items:
        duplicate_found = False
        for existing in merged:
            t_sim = token_similarity(item.title, existing.title)
            c_sim = token_similarity(item.content, existing.content)

            if t_sim > 0.6 or c_sim > 0.4:
                # Merge: prefer higher priority or newer post, but combine source names
                sources1 = [s.strip() for s in existing.source_name.split(",")]
                sources2 = [s.strip() for s in item.source_name.split(",")]
                combined_sources = []
                for src in sources1 + sources2:
                    if src not in combined_sources:
                        combined_sources.append(src)
                new_source_name = ", ".join(combined_sources)

                if _is_better_item(item, existing):
                    existing.id = item.id
                    existing.title = item.title
                    existing.content = item.content
                    existing.priority = item.priority
                    existing.published_at = item.published_at
                    existing.url = item.url
                    existing.topic = item.topic
                    existing.source_type = item.source_type

                existing.source_name = new_source_name
                duplicate_found = True
                break
        if not duplicate_found:
            merged.append(item.model_copy())
    return merged


def load_history() -> list[dict[str, Any]]:
    """Loads covered topics and titles history from local user data directory."""
    history_path = get_user_dir() / "history.json"
    if history_path.exists():
        try:
            return json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_history(history: list[dict[str, Any]]):
    """Saves covered topics/titles history."""
    history_path = get_user_dir() / "history.json"
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(json.dumps(history), encoding="utf-8")
    except Exception:
        pass


def update_history(selected_items: list[Item]):
    """Appends currently selected items to the history list (retaining last 7 runs), replacing any entry for today."""
    history = load_history()
    today_str = date.today().isoformat()

    # Filter out any existing entries for today
    history = [entry for entry in history if entry.get("date") != today_str]

    entry = {
        "date": today_str,
        "titles": [item.title for item in selected_items],
        "topics": [item.topic for item in selected_items if item.topic],
    }
    history.append(entry)
    history = history[-7:]
    save_history(history)


def is_recent_repeat(item: Item, history: list[dict[str, Any]]) -> bool:
    """Checks if the item topic or title repeats content covered in recent runs."""
    for entry in history:
        # Ignore generic categories/topics like "news" and None (untagged)
        topics = entry.get("topics") or []
        if item.topic and item.topic != "news" and item.topic in topics:
            return True
        titles = entry.get("titles") or []
        for hist_title in titles:
            if token_similarity(item.title, hist_title) > 0.4:
                return True
    return False


def get_item_budget(config: Config) -> int:
    """Calculates dynamic item budget based on config target duration and active segments."""
    total_words = config.target_minutes * 150
    enabled_ids = {s.id for s in config.segments if s.enabled}

    non_rss_words = 0
    if "intro" in enabled_ids:
        non_rss_words += 50
    if "outro" in enabled_ids:
        non_rss_words += 50
    if "greeting" in enabled_ids:
        non_rss_words += 30
    if "weather" in enabled_ids:
        non_rss_words += 80
    if "calendar" in enabled_ids:
        non_rss_words += 80
    if "inbox" in enabled_ids:
        non_rss_words += 100
    if "affirmation" in enabled_ids:
        non_rss_words += 30
    if "funfact" in enabled_ids:
        non_rss_words += 50

    remaining_words = max(total_words - non_rss_words, 150)
    # Estimate 100 words per curated item script
    return max(remaining_words // 100, 1)


def select_items(items: list[Item], config: Config, history: list[dict[str, Any]] | None = None) -> list[Item]:
    """Applies exclude filters, scores items by diversity/relevance, and selects within target budget."""
    # 1. Base Exclude Filters
    selected = [item for item in items if item.topic not in config.topics.exclude]
    selected = [item for item in selected if not _matches_exclude_keyword(item, config.exclude_keywords)]

    if config.topics.include:
        selected = [
            item for item in selected if item.topic is None or item.topic in config.topics.include
        ]

    # 2. Merge duplicate/near-duplicate news across sources
    selected = deduplicate_items(selected)

    # 3. Read history if not injected
    if history is None:
        history = load_history()

    # 4. Score and Select items incrementally to prefer diversity and balance
    budget = get_item_budget(config)
    final_selection: list[Item] = []
    remaining_candidates = list(selected)

    while len(final_selection) < budget and remaining_candidates:
        scored_candidates = []
        for item in remaining_candidates:
            # Importance score (priority * 10)
            score = item.priority * 10

            # Source diversity penalty: check overlap with already selected items
            item_sources = {s.strip() for s in item.source_name.split(",") if s.strip()}
            source_overlap_count = 0
            for sel in final_selection:
                sel_sources = {s.strip() for s in sel.source_name.split(",") if s.strip()}
                if item_sources & sel_sources:
                    source_overlap_count += 1
            score -= source_overlap_count * 5

            # Category balancing penalty
            if item.topic:
                topic_count = sum(1 for sel in final_selection if sel.topic == item.topic)
                score -= topic_count * 6

            # History repeat penalty
            if is_recent_repeat(item, history):
                score -= 25

            scored_candidates.append((score, item))

        # Sort by score descending, then by priority, then by published_at
        scored_candidates.sort(
            key=lambda x: (
                x[0],
                x[1].priority,
                x[1].published_at.timestamp() if x[1].published_at else 0,
            ),
            reverse=True,
        )

        best_score, best_item = scored_candidates[0]
        final_selection.append(best_item)
        remaining_candidates.remove(best_item)

    return final_selection


def group_by_segment(items: list[Item], segment_profile: list[str]) -> dict[str, list[Item]]:
    """Ordnet kuratierte Items den konfigurierten Segmenten zu.

    Konvention: Items mit `topic == "news"` gehen ins `news`-Segment (falls im
    Profil vorhanden), alle übrigen Items (Inbox + sonstige Themen) ins
    `topics`-Segment. Segmente ohne zugeordnete Items (z.B. `intro`/`outro`)
    bleiben als leere Liste bestehen – das LLM erzeugt sie aus einer
    Standard-Anweisung ohne Materialgrundlage.
    """
    buckets: dict[str, list[Item]] = {name: [] for name in segment_profile}
    fallback_segment = _fallback_segment(segment_profile)

    for item in items:
        if item.topic == "news" and "news" in buckets:
            buckets["news"].append(item)
        elif "topics" in buckets:
            buckets["topics"].append(item)
        elif fallback_segment is not None:
            buckets[fallback_segment].append(item)

    return buckets


def _matches_exclude_keyword(item: Item, exclude_keywords: list[str]) -> bool:
    haystack = f"{item.title} {item.content}".lower()
    return any(keyword.lower() in haystack for keyword in exclude_keywords)


def _fallback_segment(segment_profile: list[str]) -> str | None:
    for name in segment_profile:
        if name not in ("intro", "outro"):
            return name
    return segment_profile[-1] if segment_profile else None
