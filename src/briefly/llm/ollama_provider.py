"""Lokale LanguageModelProvider-Implementierung via Ollama.

Modellwahl (Briefing §9, Punkt 2): Default `qwen3:8b` – gute
Mehrsprachigkeit (inkl. Deutsch) und Instruction-Following-Qualität, passt in
16 GB Unified Memory. `qwen3:14b` als optionale High-Quality-Alternative bei
mehr verfügbarem RAM (siehe `config.example.yaml`).
"""

from __future__ import annotations

import logging
import re

import ollama

from briefly.models import EpisodeScript, Item, ScriptSegment

logger = logging.getLogger(__name__)

_SEGMENT_HEADER = re.compile(r"^##\s*SEGMENT:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_MAX_ITEMS_PER_SEGMENT = 15


class OllamaLanguageModelProvider:
    """Erzeugt das Sprechtext-Skript über das offizielle `ollama`-Python-Paket."""

    def __init__(self, model: str, target_minutes: int = 10) -> None:
        self.model = model
        self.target_minutes = target_minutes

    def generate_segment_text(self, prompt: str) -> str:
        response = ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"].strip()

    def generate_script(
        self, items_by_segment: dict[str, list[Item]], target_language: str
    ) -> EpisodeScript:
        prompt = _build_prompt(items_by_segment, target_language, self.target_minutes)
        response = ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}])
        content = response["message"]["content"]

        segments = _parse_segments(content)
        if not segments:
            logger.warning(
                "LLM-Antwort enthielt keine erkennbaren '## SEGMENT:'-Marker, "
                "nutze Rohtext als einzelnes Segment."
            )
            segments = [ScriptSegment(name="topics", text=content.strip())]
        return EpisodeScript(segments=segments)


def _build_prompt(
    items_by_segment: dict[str, list[Item]], target_language: str, target_minutes: int
) -> str:
    segment_names = ", ".join(items_by_segment.keys())
    lines = [
        "Du schreibst das Sprechtext-Skript für 'Briefly', ein persönliches "
        "tägliches Audio-Briefing.",
        f"Schreibe die gesamte Ausgabe konsequent auf {target_language}, auch wenn "
        "das Quellmaterial gemischtsprachig ist.",
        f"Ziel-Gesamtlänge über alle Segmente: ca. {target_minutes} Minuten Sprechzeit.",
        "Gliedere die Ausgabe exakt mit einer eigenen Zeile '## SEGMENT: <name>' vor "
        f"jedem Abschnitt, in genau dieser Reihenfolge und mit genau diesen Namen: "
        f"{segment_names}.",
        "Für Segmente ohne Quellmaterial (z.B. Intro/Outro) schreibe eine kurze, "
        "freundliche Anmoderation bzw. Verabschiedung passend zum Rest der Folge.",
        "",
    ]

    for name, items in items_by_segment.items():
        if not items:
            continue
        lines.append(f"### Quellmaterial für Segment '{name}':")
        for item in items[:_MAX_ITEMS_PER_SEGMENT]:
            lines.append(f"- {item.title}: {item.content}")
        lines.append("")

    return "\n".join(lines)


def _parse_segments(text: str) -> list[ScriptSegment]:
    matches = list(_SEGMENT_HEADER.finditer(text))
    segments: list[ScriptSegment] = []
    for index, match in enumerate(matches):
        name = match.group(1).strip().lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            segments.append(ScriptSegment(name=name, text=body))
    return segments
