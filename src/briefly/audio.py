"""Audio-Nachbearbeitung: Segmente zusammenführen und Kapitelmarken einbetten.

Technik (Briefing §9, Punkt 4): Segment-WAVs werden per `ffmpeg concat` zu
einer AAC/M4A-Datei zusammengeführt; parallel wird aus den Segment-Dauern
eine `;FFMETADATA1`-Datei mit Kapitel-Blöcken erzeugt und in einem finalen
verlustfreien Mux-Schritt (`-map_metadata 1 -codec copy`) eingebettet.
Zusätzlich wird eine Podcasting-2.0-`chapters.json` geschrieben, da
eingebettete MP4-Chapter-Atome laut AntennaPod-Issues nicht immer
zuverlässig gelesen werden.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from briefly.models import ChapterMark


def concat_with_chapters(segment_wavs: list[tuple[str, Path]], output_path: Path) -> list[ChapterMark]:
    """Fügt Segment-WAVs zu einer M4B-Datei zusammen, liefert die Kapitelmarken.

    `segment_wavs` ist eine Liste von (Kapitel-Titel, WAV-Pfad)-Paaren in der
    gewünschten Reihenfolge.
    """
    chapters = _build_chapters(segment_wavs)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workdir = output_path.parent
    concat_list_path = workdir / f"{output_path.stem}.concat.txt"
    chapters_meta_path = workdir / f"{output_path.stem}.chapters.ffmetadata"
    intermediate_path = workdir / f"{output_path.stem}.intermediate.m4a"

    _write_concat_list([path for _, path in segment_wavs], concat_list_path)
    _run_ffmpeg(
        [
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-c:a", "aac",
            "-b:a", "96k",
            str(intermediate_path),
        ]
    )

    _write_ffmetadata(chapters, chapters_meta_path)
    _run_ffmpeg(
        [
            "-y",
            "-i", str(intermediate_path),
            "-i", str(chapters_meta_path),
            "-map_metadata", "1",
            "-codec", "copy",
            "-f", "mp4",
            str(output_path),
        ]
    )

    concat_list_path.unlink(missing_ok=True)
    chapters_meta_path.unlink(missing_ok=True)
    intermediate_path.unlink(missing_ok=True)

    return chapters


def write_chapters_json(chapters: list[ChapterMark], output_path: Path) -> None:
    """Schreibt eine Podcasting-2.0-`chapters.json` (`<podcast:chapters>`) neben die Episode."""
    payload = {
        "version": "1.2.0",
        "chapters": [
            {"startTime": chapter.start_ms / 1000, "title": chapter.title} for chapter in chapters
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_chapters(segment_wavs: list[tuple[str, Path]]) -> list[ChapterMark]:
    chapters = []
    cursor_ms = 0
    for title, wav_path in segment_wavs:
        duration_ms = _probe_duration_ms(wav_path)
        chapters.append(ChapterMark(title=title, start_ms=cursor_ms, end_ms=cursor_ms + duration_ms))
        cursor_ms += duration_ms
    return chapters


def _probe_duration_ms(path: Path) -> int:
    result = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return round(float(result.stdout.strip()) * 1000)


def _write_concat_list(paths: list[Path], list_path: Path) -> None:
    lines = [f"file '{path.resolve()}'" for path in paths]
    list_path.write_text("\n".join(lines), encoding="utf-8")


def _write_ffmetadata(chapters: list[ChapterMark], path: Path) -> None:
    lines = [";FFMETADATA1"]
    for chapter in chapters:
        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={chapter.start_ms}")
        lines.append(f"END={chapter.end_ms}")
        lines.append(f"title={chapter.title}")
    path.write_text("\n".join(lines), encoding="utf-8")


def _run_ffmpeg(args: list[str]) -> None:
    _run(["ffmpeg", *args])


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"Befehl fehlgeschlagen ({command[0]}): {error.stderr}") from error
