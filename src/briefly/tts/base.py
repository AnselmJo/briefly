"""SpeechSynthesisProvider-Schnittstelle (Briefing §4).

Erzeugt aus einem Sprechtext-Segment eine WAV-Datei.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from briefly.models import ScriptSegment


class SpeechSynthesisProvider(Protocol):
    def synthesize_segment(
        self, segment: ScriptSegment, language: str, output_wav_path: Path
    ) -> None:
        """Schreibt die gesprochene Version von `segment.text` nach `output_wav_path`."""
        ...
