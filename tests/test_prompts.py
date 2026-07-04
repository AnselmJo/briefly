import pytest

from unittest.mock import MagicMock

from briefly.config import Config
from briefly.models import Item
from briefly.segments import (
    get_segment_impl,
    _build_segment_prompt,
    _build_calendar_prompt,
    _build_funfact_prompt,
    _build_summarize_prompt,
)


def validate_script_output(output: str):
    """Regression check for LLM outputs to ensure hard bans are respected."""
    # Hard bans
    assert "#" not in output, "Output contains section headers or hash signs."
    assert "**" not in output, "Output contains markdown bold formatting."
    assert "__" not in output, "Output contains markdown bold formatting."
    assert "*" not in output, "Output contains markdown bullet points or formatting."
    
    # Check for bullet point lines or list items
    lines = output.splitlines()
    for line in lines:
        stripped = line.strip()
        assert not stripped.startswith("-"), "Output contains bullet lists."
        assert not stripped.startswith("+"), "Output contains bullet lists."
        if stripped:
            # Check number list pattern: "1. "
            import re
            assert not re.match(r"^\d+\.\s+", stripped), "Output contains numbered lists."

    # Check for banned phrases / meta comments
    banned_phrases = [
        "Here is today's summary",
        "Here's today's summary",
        "This is the news segment",
        "I hope you enjoyed this fact",
        "Hier ist die Zusammenfassung",
        "Das war das Nachrichtensegment",
    ]
    for phrase in banned_phrases:
        assert phrase.lower() not in output.lower(), f"Output contains banned phrase: {phrase}"

    # Check length
    word_count = len(output.split())
    assert word_count > 0, "Output is empty."
    assert word_count < 1000, "Output exceeds reasonable length targets."


def test_prompt_regression_instructions():
    # Verify that all builder prompts contain the SYSTEM_INSTRUCTIONS content
    config = Config()
    items = [Item(id="1", title="A", content="B", source_type="rss", source_name="s", topic="news")]
    
    prompt1 = _build_segment_prompt("news", items, "en", 10)
    prompt2 = _build_calendar_prompt([{"summary": "Meeting", "time": "10:00", "is_all_day": False}], "en")
    prompt3 = _build_funfact_prompt("nature", "en")
    prompt4 = _build_summarize_prompt("Long text...", 50, "en")
    
    # Retrieve segment script prompts
    mock_llm = MagicMock()
    mock_llm.generate_segment_text.return_value = "Result"
    
    intro_seg = get_segment_impl("intro")
    intro_seg.script(config, None, mock_llm, "en")
    prompt5 = mock_llm.generate_segment_text.call_args[0][0]
    
    mock_llm.reset_mock()
    outro_seg = get_segment_impl("outro")
    outro_seg.script(config, None, mock_llm, "en")
    prompt6 = mock_llm.generate_segment_text.call_args[0][0]
    
    for p in [prompt1, prompt2, prompt3, prompt4, prompt5, prompt6]:
        # Assert key radio host constraints are in the prompt
        assert "radio host" in p.lower()
        assert "short, punchy sentences" in p.lower() or "short sentences" in p.lower()
        assert "never use markdown" in p.lower()
        assert "never output bullet points" in p.lower() or "no lists" in p.lower()
        assert "never output titles" in p.lower() or "no headings" in p.lower()
        assert "never output meta-commentary" in p.lower() or "no comments" in p.lower()


def test_validate_script_output_passes():
    # Natural spoken text matching morning radio host style should pass
    good_text = (
        "Good morning! Today we have some interesting updates for you. "
        "The weather is looking nice and clear. According to one report, "
        "we might see some light rain later in the evening, so keep that in mind. "
        "Have a fantastic day ahead!"
    )
    validate_script_output(good_text)


def test_validate_script_output_fails_on_markdown():
    bad_text = "Here is some **bold** text."
    with pytest.raises(AssertionError):
        validate_script_output(bad_text)


def test_validate_script_output_fails_on_bullet_list():
    bad_text = "Here is a list:\n- First item\n- Second item"
    with pytest.raises(AssertionError):
        validate_script_output(bad_text)


def test_validate_script_output_fails_on_numbered_list():
    bad_text = "Steps:\n1. Open door\n2. Walk in"
    with pytest.raises(AssertionError):
        validate_script_output(bad_text)


def test_validate_script_output_fails_on_header():
    bad_text = "# Daily Briefing\nHello Anselm."
    with pytest.raises(AssertionError):
        validate_script_output(bad_text)


def test_validate_script_output_fails_on_meta_comment():
    bad_text = "Here is today's summary of the news."
    with pytest.raises(AssertionError):
        validate_script_output(bad_text)
