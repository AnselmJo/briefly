from briefly.config import Config, load_config, save_config


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
