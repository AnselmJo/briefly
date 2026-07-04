from briefly.tts.preprocessor import preprocess_text


def test_preprocess_removes_html():
    text = "<p>Hello <b>world</b>! <a href='http://test.com'>Link</a></p>"
    paragraphs = preprocess_text(text)
    assert paragraphs == ["Hello world! Link"]


def test_preprocess_removes_fenced_code_blocks():
    text = "Intro text.\n```python\ndef hello():\n    print('world')\n```\nOutro text."
    paragraphs = preprocess_text(text)
    assert paragraphs == ["Intro text.", "Outro text."]


def test_preprocess_removes_tables():
    text = "Text before.\n| Col 1 | Col 2 |\n|---|---|\n| val 1 | val 2 |\nText after."
    paragraphs = preprocess_text(text)
    assert paragraphs == ["Text before.", "Text after."]


def test_preprocess_removes_headings():
    text = "# Heading 1\nSome text.\n## Heading 2\nMore text."
    paragraphs = preprocess_text(text)
    assert paragraphs == ["Some text.", "More text."]


def test_preprocess_strips_bullets():
    text = "- First item\n* Second item\n+ Third item\n1. Fourth item\nRegular text."
    paragraphs = preprocess_text(text)
    assert paragraphs == [
        "First item",
        "Second item",
        "Third item",
        "Fourth item",
        "Regular text.",
    ]


def test_preprocess_strips_markdown_formatting_and_links():
    text = "This is **bold**, __bold__, *italic*, _italic_, ~~strike~~, and `code`.\n\nCheck out [Google](https://google.com)."
    paragraphs = preprocess_text(text)
    assert paragraphs == [
        "This is bold, bold, italic, italic, strike, and code.",
        "Check out Google.",
    ]


def test_preprocess_normalizes_punctuation_and_whitespace():
    text = "„Smart quotes“ and “curly quotes”...\nLet's test dashes—and double  spaces.\nWait!!! What???"
    paragraphs = preprocess_text(text)
    assert paragraphs == [
        '"Smart quotes" and "curly quotes". Let\'s test dashes-and double spaces. Wait! What?'
    ]


def test_preprocess_splits_paragraphs_on_double_newlines():
    text = "Paragraph 1.\n\nParagraph 2.\nWith a second line."
    paragraphs = preprocess_text(text)
    assert paragraphs == [
        "Paragraph 1.",
        "Paragraph 2. With a second line.",
    ]
