import warnings
import pytest

from briefly.config import Config, ConfigValidationError, load_config, save_config


def test_load_config_applies_defaults_for_missing_fields(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("language:\n  target: de\n", encoding="utf-8")

    config = load_config(config_path)

    assert config.language.target == "de"
    assert config.llm.model == "qwen3:8b"
    assert "war" in config.exclude_keywords


def test_save_and_reload_roundtrip(tmp_path):
    config_path = tmp_path / "config.yaml"
    config = Config()
    config.topics.include = ["news", "books"]
    config.segment_profile = ["intro", "news", "outro"]

    save_config(config, config_path)
    reloaded = load_config(config_path)

    assert reloaded.topics.include == ["news", "books"]
    assert reloaded.segment_profile == ["intro", "news", "outro"]


def test_load_valid_config(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_content = """
delivery:
  provider: local_feed
  output_dir: output
  base_url: https://mybriefing.local
  host: 127.0.0.1
  port: 9000
tts:
  provider: piper
  voice_de: voice1
  voice_en: voice2
  voices_dir: my_voices
  length_scale: 1.15
  sentence_pause_ms: 100
  paragraph_pause_ms: 200
  language: de
llm:
  provider: ollama
  model: mymodel
sources:
  inbox:
    path: my_inbox
  rss:
    feeds:
      - url: https://feed1.com/rss
        topic: news
        weight: 1.5
  topics:
    include: [tag1]
    exclude: [tag2]
  exclude_keywords: [badword]
segments:
  profile: [intro, outro]
  target_minutes: 5
schedule:
  hour: 6
  minute: 15
"""
    config_path.write_text(config_content, encoding="utf-8")
    config = load_config(config_path)
    
    assert config.delivery.base_url == "https://mybriefing.local"
    assert config.delivery.host == "127.0.0.1"
    assert config.delivery.port == 9000
    assert config.tts.language == "de"
    assert config.tts.length_scale == 1.15
    assert config.tts.sentence_pause_ms == 100
    assert config.tts.paragraph_pause_ms == 200
    assert config.llm.model == "mymodel"
    assert config.sources.inbox.path == (config_path.parent / "my_inbox").resolve()
    assert config.sources.rss.feeds[0].url == "https://feed1.com/rss"
    assert config.sources.rss.feeds[0].weight == 1.5
    assert config.sources.topics.include == ["tag1"]
    assert config.sources.exclude_keywords == ["badword"]
    assert config.segments.profile == ["intro", "outro"]
    assert config.segments.target_minutes == 5
    assert config.schedule.hour == 6
    assert config.schedule.minute == 15


@pytest.mark.parametrize(
    "invalid_yaml,expected_key",
    [
        ("delivery:\n  base_url: invalid_url", "delivery.base_url"),
        ("delivery:\n  host: '   '", "delivery.host"),
        ("delivery:\n  port: -5", "delivery.port"),
        ("delivery:\n  port: 800000", "delivery.port"),
        ("tts:\n  length_scale: -0.5", "tts.length_scale"),
        ("tts:\n  sentence_pause_ms: -1", "tts.sentence_pause_ms"),
        ("tts:\n  paragraph_pause_ms: -10", "tts.paragraph_pause_ms"),
        ("tts:\n  language: ''", "tts.language"),
        ("llm:\n  model: ''", "llm.model"),
        ("segments:\n  target_minutes: 0", "segments.target_minutes"),
        ("segments:\n  profile: []", "segments.profile"),
        ("segments:\n  profile: ['']", "segments.profile"),
        ("schedule:\n  hour: 25", "schedule.hour"),
        ("schedule:\n  minute: -1", "schedule.minute"),
        ("sources:\n  rss:\n    feeds:\n      - url: invalid_url", "sources.rss.feeds.0.url"),
        ("sources:\n  rss:\n    feeds:\n      - url: https://ok.com\n        weight: -1", "sources.rss.feeds.0.weight"),
        ("sources:\n  topics:\n    include: ['']", "sources.topics.include"),
        ("sources:\n  topics:\n    exclude: ['']", "sources.topics.exclude"),
        ("sources:\n  exclude_keywords: ['']", "sources.exclude_keywords"),
        ("sources:\n  inbox:\n    path: ''", "sources.inbox.path"),
        ("tts:\n  voices_dir: ''", "tts.voices_dir"),
        ("delivery:\n  output_dir: ''", "delivery.output_dir"),
        ("llm:\n  provider: invalid", "llm.provider"),
        ("tts:\n  provider: invalid", "tts.provider"),
        ("delivery:\n  provider: invalid", "delivery.provider"),
        ("sources:\n  rss:\n    feeds:\n      - topic: news", "sources.rss.feeds.0.url"),
    ]
)
def test_invalid_config_cases(tmp_path, invalid_yaml, expected_key):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(invalid_yaml, encoding="utf-8")
    
    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(config_path)
        
    assert exc_info.value.key == expected_key
    assert exc_info.value.fix is not None
    assert str(exc_info.value) != ""


def test_unknown_keys_warnings(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_content = """
delivery:
  provider: local_feed
  unknown_delivery_key: 123
unknown_top_level_key: 'hello'
"""
    config_path.write_text(config_content, encoding="utf-8")
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        config = load_config(config_path)
        
        # Check warnings
        user_warnings = [str(warn.message) for warn in w if issubclass(warn.category, UserWarning)]
        assert any("unknown_delivery_key" in msg for msg in user_warnings)
        assert any("unknown_top_level_key" in msg for msg in user_warnings)
        
    # Should still load defaults successfully
    assert config.delivery.provider == "local_feed"


def test_sys_excepthook(capsys):
    import sys
    from briefly.config import ConfigValidationError
    
    # Trigger our hook manually
    exc = ConfigValidationError("some_key", "bad_val", "Msg", "Fix it")
    
    with pytest.raises(SystemExit) as exc_info:
        sys.excepthook(ConfigValidationError, exc, None)
        
    assert exc_info.value.code == 1
    
    captured = capsys.readouterr()
    assert "Fehler: Ungültige Konfiguration:" in captured.err
    assert "some_key" in captured.err
    assert "bad_val" in captured.err
    assert "Msg" in captured.err
    assert "Fix it" in captured.err


