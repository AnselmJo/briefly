from pathlib import Path
from unittest.mock import MagicMock
import wave
import numpy as np

from piper import AudioChunk
from briefly.models import ScriptSegment
from briefly.tts.piper_provider import PiperSpeechSynthesisProvider


def test_piper_provider_adds_pauses(tmp_path):
    # Setup mock PiperVoice
    mock_voice = MagicMock()
    mock_voice.config.sample_rate = 16000

    # Simulate voice.synthesize yielding sentence chunks
    def mock_synthesize(text, syn_config=None):
        assert syn_config is not None
        assert syn_config.length_scale == 1.2
        if "first sentence" in text:
            return [
                AudioChunk(
                    sample_rate=16000,
                    sample_width=2,
                    sample_channels=1,
                    audio_float_array=np.zeros(1600, dtype=np.float32),  # 100ms
                    phonemes=[],
                    phoneme_ids=[],
                ),
                AudioChunk(
                    sample_rate=16000,
                    sample_width=2,
                    sample_channels=1,
                    audio_float_array=np.zeros(1600, dtype=np.float32),  # 100ms
                    phonemes=[],
                    phoneme_ids=[],
                ),
            ]
        elif "second paragraph" in text:
            return [
                AudioChunk(
                    sample_rate=16000,
                    sample_width=2,
                    sample_channels=1,
                    audio_float_array=np.zeros(1600, dtype=np.float32),  # 100ms
                    phonemes=[],
                    phoneme_ids=[],
                )
            ]
        return []

    mock_voice.synthesize.side_effect = mock_synthesize

    provider = PiperSpeechSynthesisProvider(
        voices_dir=Path("fake_dir"),
        voice_de="fake_de",
        voice_en="fake_en",
        length_scale=1.2,
        sentence_pause_ms=200,  # 200ms pause
        paragraph_pause_ms=500,  # 500ms pause
    )
    # Mock _load_voice to return our mock_voice
    provider._load_voice = MagicMock(return_value=mock_voice)

    segment = ScriptSegment(
        name="test",
        text="This is the first sentence. And another sentence.\n\nThis is the second paragraph.",
    )
    wav_path = tmp_path / "output.wav"
    provider.synthesize_segment(segment, "en", wav_path)

    # Let's read the output WAV and verify total samples / duration
    assert wav_path.exists()
    with wave.open(str(wav_path), "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2

        # Let's count frames:
        # Paragraph 1 sentences: 2 sentences * 100ms audio = 200ms
        # Paragraph 1 sentence pause: 1 pause * 200ms = 200ms
        # Paragraph 1 paragraph pause (ends paragraph): 1 pause * 500ms = 500ms
        # Paragraph 2 sentences: 1 sentence * 100ms audio = 100ms
        # Paragraph 2 paragraph pause (ends paragraph): 1 pause * 500ms = 500ms
        # Total expected audio duration = 200ms + 200ms + 500ms + 100ms + 500ms = 1500ms = 1.5s
        # Total frames = 1.5s * 16000 = 24000
        total_frames = w.getnframes()
        assert total_frames == 24000
