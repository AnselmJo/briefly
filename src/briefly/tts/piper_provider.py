"""Lokale SpeechSynthesisProvider-Implementierung via Piper.

TTS-Wahl (Briefing §9, Punkt 1): `piper-tts` – aktiv gepflegt unter der Open
Home Foundation (`OHF-Voice/piper1-gpl`, Nachfolger von `rhasspy/piper`),
läuft ohne Kompilieren auf Apple Silicon (native ARM64-Wheels) und bietet
brauchbare deutsche und englische Stimmen. Voice-Modelle (`.onnx` +
`.onnx.json`) müssen vorab in `voices_dir` liegen (siehe README).
"""

from __future__ import annotations

import wave
from pathlib import Path

from piper import PiperVoice

from briefly.models import ScriptSegment


class PiperSpeechSynthesisProvider:
    def __init__(self, voices_dir: Path, voice_de: str, voice_en: str) -> None:
        self.voices_dir = Path(voices_dir)
        self.voice_de = voice_de
        self.voice_en = voice_en
        self._loaded_voices: dict[str, PiperVoice] = {}

    def synthesize_segment(
        self, segment: ScriptSegment, language: str, output_wav_path: Path
    ) -> None:
        voice = self._load_voice(language)
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_wav_path), "wb") as wav_file:
            voice.synthesize_wav(segment.text, wav_file)

    def _load_voice(self, language: str) -> PiperVoice:
        voice_name = self.voice_de if language.lower().startswith("de") else self.voice_en
        if voice_name not in self._loaded_voices:
            model_path = self.voices_dir / f"{voice_name}.onnx"
            self._loaded_voices[voice_name] = PiperVoice.load(str(model_path))
        return self._loaded_voices[voice_name]
