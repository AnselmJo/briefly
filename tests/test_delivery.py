from briefly.delivery.local_feed import LocalFeedDeliveryTarget
from briefly.models import ChapterMark, EpisodeManifest


def _make_manifest(episodes_dir, episode_date="2026-07-04"):
    audio_path = episodes_dir / f"{episode_date}.m4b"
    audio_path.write_bytes(b"fake-audio-bytes")
    chapters_path = episodes_dir / f"{episode_date}.chapters.json"
    chapters_path.write_text("{}", encoding="utf-8")
    transcript_path = episodes_dir / f"{episode_date}.txt"
    transcript_path.write_text("Transkript", encoding="utf-8")

    from datetime import date

    return EpisodeManifest(
        episode_date=date.fromisoformat(episode_date),
        audio_path=audio_path,
        transcript_path=transcript_path,
        chapters_json_path=chapters_path,
        chapters=[ChapterMark(title="Intro", start_ms=0, end_ms=1000)],
    )


def test_publish_writes_feed_with_enclosure_and_chapters_link(tmp_path):
    output_dir = tmp_path / "output"
    episodes_dir = output_dir / "episodes"
    episodes_dir.mkdir(parents=True)

    manifest = _make_manifest(episodes_dir)
    target = LocalFeedDeliveryTarget(output_dir=output_dir, base_url="http://192.168.1.10:8787")
    target.publish(manifest)

    feed_path = output_dir / "feed.xml"
    assert feed_path.is_file()

    feed_xml = feed_path.read_text(encoding="utf-8")
    assert "Briefly" in feed_xml
    assert "http://192.168.1.10:8787/episodes/2026-07-04.m4b" in feed_xml
    assert "2026-07-04.chapters.json" in feed_xml


def test_publish_lists_multiple_episodes_newest_first(tmp_path):
    output_dir = tmp_path / "output"
    episodes_dir = output_dir / "episodes"
    episodes_dir.mkdir(parents=True)

    _make_manifest(episodes_dir, episode_date="2026-07-01")
    manifest = _make_manifest(episodes_dir, episode_date="2026-07-04")

    target = LocalFeedDeliveryTarget(output_dir=output_dir, base_url="http://192.168.1.10:8787")
    target.publish(manifest)

    feed_xml = (output_dir / "feed.xml").read_text(encoding="utf-8")
    assert feed_xml.index("2026-07-04") < feed_xml.index("2026-07-01")
