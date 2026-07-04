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
from piper.config import SynthesisConfig

from briefly.models import ScriptSegment
from briefly.tts.preprocessor import preprocess_text


class PiperSpeechSynthesisProvider:
    def __init__(
        self,
        voices_dir: Path,
        voice_de: str,
        voice_en: str,
        length_scale: float | None = None,
        sentence_pause_ms: int = 0,
        paragraph_pause_ms: int = 0,
    ) -> None:
        self.voices_dir = Path(voices_dir)
        self.voice_de = voice_de
        self.voice_en = voice_en
        self.length_scale = length_scale
        self.sentence_pause_ms = sentence_pause_ms
        self.paragraph_pause_ms = paragraph_pause_ms
        self._loaded_voices: dict[str, PiperVoice] = {}

    def synthesize_segment(
        self, segment: ScriptSegment, language: str, output_wav_path: Path
    ) -> None:
        voice = self._load_voice(language)
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)

        paragraphs = preprocess_text(segment.text, language)
        syn_config = SynthesisConfig(length_scale=self.length_scale)

        with wave.open(str(output_wav_path), "wb") as wav_file:
            # Set WAV parameters from voice configuration
            wav_file.setframerate(voice.config.sample_rate)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setnchannels(1)  # mono

            if not paragraphs:
                return

            for p_idx, paragraph in enumerate(paragraphs):
                sentences = list(voice.synthesize(paragraph, syn_config))
                for s_idx, chunk in enumerate(sentences):
                    wav_file.writeframes(chunk.audio_int16_bytes)

                    is_last_sentence_in_para = s_idx == len(sentences) - 1
                    pause_ms = (
                        self.paragraph_pause_ms
                        if is_last_sentence_in_para
                        else self.sentence_pause_ms
                    )

                    if pause_ms > 0:
                        silence_len = int(voice.config.sample_rate * (pause_ms / 1000.0))
                        silence_bytes = bytes(silence_len * 2)
                        wav_file.writeframes(silence_bytes)

    def _load_voice(self, language: str) -> PiperVoice:
        voice_name = self.voice_de if language.lower().startswith("de") else self.voice_en
        if voice_name not in self._loaded_voices:
            model_path = self.voices_dir / f"{voice_name}.onnx"
            self._loaded_voices[voice_name] = PiperVoice.load(str(model_path))
        return self._loaded_voices[voice_name]
