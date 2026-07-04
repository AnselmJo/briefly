"""LanguageModelProvider-Schnittstelle (Briefing §4).

Erzeugt aus kuratiertem Material das Sprechtext-Skript inkl. markierter
Segmentgrenzen.
"""

from __future__ import annotations

from typing import Protocol

from briefly.models import EpisodeScript, Item


class LanguageModelProvider(Protocol):
    def generate_script(
        self, items_by_segment: dict[str, list[Item]], target_language: str
    ) -> EpisodeScript:
        """Erzeugt ein Sprechtext-Skript mit einem Segment je Eintrag in `items_by_segment`."""
        ...
