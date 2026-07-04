"""Orchestriert die fünf Pipeline-Stufen: Sammeln, Kuratieren, Skript, Audio, Ausliefern.

Jede Stufe ist einzeln aufrufbar/testbar (Briefing §2.7); `run_all` verdrahtet
die Default-Provider (Ollama, Piper, lokaler Feed) für den nächtlichen
Standardlauf.
"""

from __future__ import annotations

import logging
import tempfile
from datetime import date
from pathlib import Path

from briefly.audio import concat_with_chapters, write_chapters_json
from briefly.config import Config
from briefly.curation import group_by_segment, select_items, update_history
from briefly.delivery.base import DeliveryTarget
from briefly.delivery.local_feed import LocalFeedDeliveryTarget
from briefly.llm.base import LanguageModelProvider
from briefly.llm.ollama_provider import OllamaLanguageModelProvider
from briefly.models import EpisodeManifest, EpisodeScript, Item
from briefly.tts.base import SpeechSynthesisProvider
from briefly.tts.piper_provider import PiperSpeechSynthesisProvider

logger = logging.getLogger(__name__)


def run_collect(config: Config) -> list[Item]:
    """Stufe 1: sammelt Items aus allen aktivierten Segmenten.

    Fällt eine Quelle aus, wird das geloggt und übersprungen – kein
    Totalausfall wegen einer einzelnen Quelle (Briefing §2.5).
    """
    from briefly.segments import get_segment_impl
    items: list[Item] = []
    
    for seg_conf in config.segments:
        if not seg_conf.enabled:
            continue
        segment_impl = get_segment_impl(seg_conf.id)
        if not segment_impl:
            continue
        try:
            res = segment_impl.collect(config)
            if isinstance(res, list):
                for item in res:
                    if item not in items:
                        items.append(item)
        except Exception:
            logger.exception("Segment %s konnte keine Daten sammeln, wird übersprungen.", seg_conf.id)
            
    return items


def run_curate(items: list[Item], config: Config) -> dict[str, list[Item]]:
    """Stufe 2: filtert nach Themen/Ausschluss-Stichwörtern und gruppiert nach Segment."""
    selected = select_items(items, config)
    update_history(selected)
    return group_by_segment(selected, config.segment_profile)


def run_script(
    grouped_items: dict[str, list[Item]],
    config: Config,
    llm_provider: LanguageModelProvider | None = None,
    episode_date: date | None = None,
) -> EpisodeScript:
    """Stufe 3: lässt das LLM das Sprechtext-Skript segmentweise schreiben."""
    from briefly.segments import get_segment_impl
    from briefly.models import ScriptSegment

    provider = llm_provider or OllamaLanguageModelProvider(
        model=config.llm.model, target_minutes=config.target_minutes
    )
    
    script_segments: list[ScriptSegment] = []
    
    for seg_conf in config.segments:
        if not seg_conf.enabled:
            continue
            
        segment_id = seg_conf.id
        segment_impl = get_segment_impl(segment_id)
        if not segment_impl:
            logger.warning("Keine Implementierung für Segment %s gefunden, wird übersprungen.", segment_id)
            continue
            
        data = grouped_items.get(segment_id, [])
        try:
            text = segment_impl.script(config, data, provider, config.tts.language, episode_date=episode_date)
            if text:
                script_segments.append(ScriptSegment(name=segment_id, text=text))
        except Exception:
            logger.exception("Fehler beim Generieren des Skripts für Segment %s. Wird übersprungen.", segment_id)
            
    return EpisodeScript(segments=script_segments)


def run_audio(
    script: EpisodeScript,
    config: Config,
    episode_date: date,
    tts_provider: SpeechSynthesisProvider | None = None,
) -> EpisodeManifest:
    """Stufe 4: synthetisiert die Segmente und baut die finale Audiodatei mit Kapiteln."""
    provider = tts_provider or PiperSpeechSynthesisProvider(
        voices_dir=config.tts.voices_dir,
        voice_de=config.tts.voice_de,
        voice_en=config.tts.voice_en,
        length_scale=config.tts.length_scale,
        sentence_pause_ms=config.tts.sentence_pause_ms,
        paragraph_pause_ms=config.tts.paragraph_pause_ms,
    )
    episodes_dir = config.delivery.output_dir / "episodes"
    episodes_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="briefly-segments-") as tmp_dir:
        segment_wavs: list[tuple[str, Path]] = []
        for index, segment in enumerate(script.segments):
            wav_path = Path(tmp_dir) / f"{index:02d}-{segment.name}.wav"
            provider.synthesize_segment(segment, config.language.target, wav_path)
            segment_wavs.append((segment.name, wav_path))

        audio_path = episodes_dir / f"{episode_date:%Y-%m-%d}.m4b"
        chapters = concat_with_chapters(segment_wavs, audio_path)

    chapters_json_path = episodes_dir / f"{episode_date:%Y-%m-%d}.chapters.json"
    write_chapters_json(chapters, chapters_json_path)

    # Lauftext zusätzlich als Textdatei ablegen (Nachvollzug/Debugging, Briefing §3).
    transcript_path = episodes_dir / f"{episode_date:%Y-%m-%d}.txt"
    transcript_path.write_text(_render_transcript(script), encoding="utf-8")

    return EpisodeManifest(
        episode_date=episode_date,
        audio_path=audio_path,
        transcript_path=transcript_path,
        chapters_json_path=chapters_json_path,
        chapters=chapters,
    )


def run_deliver(
    manifest: EpisodeManifest,
    config: Config,
    delivery_target: DeliveryTarget | None = None,
) -> None:
    """Stufe 5: macht die Episode über den lokalen RSS-Feed auffindbar."""
    target = delivery_target or LocalFeedDeliveryTarget(
        output_dir=config.delivery.output_dir, base_url=config.delivery.base_url
    )
    target.publish(manifest)


def run_all(config: Config, episode_date: date | None = None) -> EpisodeManifest:
    """Führt alle fünf Stufen nacheinander aus (nächtlicher Standardlauf)."""
    import json
    from datetime import datetime
    from briefly.config import get_user_dir

    resolved_date = episode_date or date.today()
    try:
        items = run_collect(config)
        grouped = run_curate(items, config)
        script = run_script(grouped, config, episode_date=resolved_date)
        manifest = run_audio(script, config, resolved_date)
        run_deliver(manifest, config)
        
        # Save success state
        try:
            state = {
                "timestamp": datetime.now().isoformat(),
                "success": True,
                "error": None
            }
            user_dir = get_user_dir()
            user_dir.mkdir(parents=True, exist_ok=True)
            (user_dir / "last_run.json").write_text(json.dumps(state), encoding="utf-8")
        except Exception:
            pass
            
        return manifest
    except Exception as e:
        # Save failure state
        try:
            state = {
                "timestamp": datetime.now().isoformat(),
                "success": False,
                "error": str(e)
            }
            user_dir = get_user_dir()
            user_dir.mkdir(parents=True, exist_ok=True)
            (user_dir / "last_run.json").write_text(json.dumps(state), encoding="utf-8")
        except Exception:
            pass
        raise e


def _render_transcript(script: EpisodeScript) -> str:
    parts = [f"## {segment.name}\n\n{segment.text}" for segment in script.segments]
    return "\n\n".join(parts)
