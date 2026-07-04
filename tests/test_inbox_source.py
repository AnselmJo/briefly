from briefly.sources.inbox import InboxSource


def test_parses_entries_separated_by_dashes(tmp_path):
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()
    (inbox_dir / "notes.txt").write_text(
        "#thema: books\n#prio: 2\nEin Buch über XY.\n---\nEinfacher Eintrag ohne Kopf.\n---\n",
        encoding="utf-8",
    )

    items = InboxSource(inbox_dir).fetch()

    assert len(items) == 2
    assert items[0].topic == "books"
    assert items[0].priority == 2
    assert items[0].content == "Ein Buch über XY."
    assert items[1].topic is None
    assert items[1].priority == 0


def test_missing_folder_returns_empty_list(tmp_path):
    items = InboxSource(tmp_path / "does-not-exist").fetch()
    assert items == []


def test_skips_empty_entries(tmp_path):
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()
    (inbox_dir / "notes.txt").write_text("---\n---\nEcht ein Eintrag.\n---\n", encoding="utf-8")

    items = InboxSource(inbox_dir).fetch()

    assert len(items) == 1
    assert items[0].content == "Echt ein Eintrag."
