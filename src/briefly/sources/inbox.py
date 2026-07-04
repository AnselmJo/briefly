"""Inbox-ContentSource: liest lokale Textdateien aus einem konfigurierten Ordner.

Einträge werden durch eine Zeile mit exakt `---` getrennt (Briefing §5).
Jeder Eintrag kann optional mit `#thema:`/`#prio:`-Kopfzeilen beginnen; fehlt
der Kopf, wird der Eintrag trotzdem verarbeitet (nur ohne Vorrang).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from briefly.models import Item

logger = logging.getLogger(__name__)

_ENTRY_SEPARATOR = re.compile(r"^---$", re.MULTILINE)
_TOPIC_HEADER = re.compile(r"^#thema:\s*(.+)$", re.IGNORECASE)
_PRIORITY_HEADER = re.compile(r"^#prio:\s*(\d+)$", re.IGNORECASE)


class InboxSource:
    """Liest Notizen/Gedanken/Links aus Textdateien in `path` (Briefing §3)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def fetch(self) -> list[Item]:
        if not self.path.is_dir():
            logger.warning("Inbox-Ordner nicht gefunden: %s", self.path)
            return []

        items: list[Item] = []
        for file_path in sorted(self.path.glob("*.txt")):
            try:
                items.extend(self._parse_file(file_path))
            except OSError:
                logger.warning("Inbox-Datei konnte nicht gelesen werden: %s", file_path)
        return items

    def _parse_file(self, file_path: Path) -> list[Item]:
        text = file_path.read_text(encoding="utf-8")
        published_at = datetime.fromtimestamp(file_path.stat().st_mtime)

        entries: list[Item] = []
        for index, block in enumerate(_ENTRY_SEPARATOR.split(text)):
            block = block.strip()
            if not block:
                continue
            topic, priority, content = _parse_entry_header(block)
            if not content:
                continue
            entries.append(
                Item(
                    id=f"inbox:{file_path.stem}:{index}",
                    title=_derive_title(content),
                    content=content,
                    source_type="inbox",
                    source_name=file_path.name,
                    topic=topic,
                    priority=priority,
                    published_at=published_at,
                )
            )
        return entries


def _parse_entry_header(block: str) -> tuple[str | None, int, str]:
    """Zieht optionale `#thema:`/`#prio:`-Kopfzeilen vom Anfang eines Eintrags ab."""
    lines = block.splitlines()
    topic: str | None = None
    priority = 0
    body_start = 0

    for line in lines:
        if match := _TOPIC_HEADER.match(line.strip()):
            topic = match.group(1).strip()
            body_start += 1
        elif match := _PRIORITY_HEADER.match(line.strip()):
            priority = int(match.group(1))
            body_start += 1
        else:
            break

    content = "\n".join(lines[body_start:]).strip()
    return topic, priority, content


def _derive_title(content: str) -> str:
    first_line = content.splitlines()[0].strip()
    return first_line[:80]
