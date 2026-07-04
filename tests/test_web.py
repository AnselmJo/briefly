import pytest
from fastapi.testclient import TestClient

import briefly.web.app as web_app
from briefly.config import Config, save_config


@pytest.fixture
def client(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config = Config()
    config.delivery.output_dir = tmp_path / "output"
    config.sources.inbox.path = tmp_path / "inbox"
    save_config(config, config_path)

    monkeypatch.setattr(web_app, "_CONFIG_PATH", config_path)
    return TestClient(web_app.app)


def test_dashboard_without_episode(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Briefly" in response.text


def test_settings_roundtrip(client):
    response = client.post(
        "/settings",
        data={
            "language_target": "de",
            "segment_profile": "intro\nnews\noutro",
            "topics_include": "books",
            "topics_exclude": "",
            "exclude_keywords": "Krieg",
            "tts_length_scale": "1.25",
            "tts_sentence_pause_ms": "350",
            "tts_paragraph_pause_ms": "750",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    settings_page = client.get("/settings")
    assert "books" in settings_page.text
    assert "Krieg" in settings_page.text
    assert "1.25" in settings_page.text
    assert "350" in settings_page.text
    assert "750" in settings_page.text


def test_feeds_add_and_delete(client):
    add_response = client.post(
        "/feeds",
        data={"url": "https://example.com/rss", "topic": "news", "weight": "1.0"},
        follow_redirects=False,
    )
    assert add_response.status_code == 303
    assert "example.com/rss" in client.get("/feeds").text

    delete_response = client.post(
        "/feeds/delete", data={"url": "https://example.com/rss"}, follow_redirects=False
    )
    assert delete_response.status_code == 303
    assert "example.com/rss" not in client.get("/feeds").text


def test_inbox_add_and_delete(client, tmp_path):
    add_response = client.post(
        "/inbox",
        data={"topic": "books", "priority": "1", "content": "Ein Buch über Y."},
        follow_redirects=False,
    )
    assert add_response.status_code == 303

    inbox_files = list((tmp_path / "inbox").glob("*.txt"))
    assert len(inbox_files) == 1
    assert "#thema: books" in inbox_files[0].read_text(encoding="utf-8")

    delete_response = client.post(
        "/inbox/delete", data={"filename": inbox_files[0].name}, follow_redirects=False
    )
    assert delete_response.status_code == 303
    assert not inbox_files[0].exists()


def test_episode_file_rejects_path_traversal(client):
    response = client.get("/episodes/..%2f..%2fconfig.yaml")
    assert response.status_code == 404


def test_feeds_toggle_move_test_preview(client, monkeypatch):
    import briefly.sources.rss as rss_source

    mock_health = {
        "status": "ok",
        "error_message": None,
        "suggested_fix": None,
        "item_count": 5,
        "parsed": None,
    }
    monkeypatch.setattr(rss_source, "check_feed_health", lambda url: mock_health)

    # 1. Add two feeds
    client.post("/feeds", data={"url": "https://example.com/feed1", "topic": "news", "weight": "1.0"})
    client.post("/feeds", data={"url": "https://example.com/feed2", "topic": "tech", "weight": "1.0"})

    # Check order
    feeds_html = client.get("/feeds").text
    assert "feed1" in feeds_html
    assert "feed2" in feeds_html

    # 2. Toggle enabled state of feed1
    toggle_res = client.post("/feeds/toggle", data={"url": "https://example.com/feed1"}, follow_redirects=False)
    assert toggle_res.status_code == 303
    
    # 3. Move feed2 up (should put feed2 before feed1)
    move_res = client.post("/feeds/move-up", data={"url": "https://example.com/feed2"}, follow_redirects=False)
    assert move_res.status_code == 303
    
    # 4. Test feed1
    test_res = client.post("/feeds/test", data={"url": "https://example.com/feed1"}, follow_redirects=False)
    assert test_res.status_code == 303

    # 5. Preview feed1
    preview_res = client.get("/feeds/preview?url=https://example.com/feed1")
    assert preview_res.status_code == 200
    assert "Feed-Vorschau" in preview_res.text
