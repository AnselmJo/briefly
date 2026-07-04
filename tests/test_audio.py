import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from briefly.audio import concat_with_chapters, write_chapters_json
from briefly.models import ChapterMark

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg nicht installiert")


def _write_silence_wav(path: Path, seconds: float) -> None:
    framerate = 16000
    frame_count = int(seconds * framerate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(framerate)
        wav_file.writeframes(b"\x00\x00" * frame_count)


def test_concat_with_chapters_embeds_chapter_marks(tmp_path):
    wav_a, wav_b = tmp_path / "a.wav", tmp_path / "b.wav"
    _write_silence_wav(wav_a, 1.0)
    _write_silence_wav(wav_b, 1.0)

    output_path = tmp_path / "episode.m4b"
    chapters = concat_with_chapters([("Intro", wav_a), ("News", wav_b)], output_path)

    assert output_path.exists()
    assert [chapter.title for chapter in chapters] == ["Intro", "News"]

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_chapters", "-of", "json", str(output_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Intro" in result.stdout
    assert "News" in result.stdout


def test_write_chapters_json(tmp_path):
    chapters = [ChapterMark(title="Intro", start_ms=0, end_ms=1000)]
    output_path = tmp_path / "episode.chapters.json"

    write_chapters_json(chapters, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "Intro" in content
    assert '"startTime": 0.0' in content
