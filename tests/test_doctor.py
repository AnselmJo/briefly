import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from briefly.doctor import (
    CheckResult,
    check_config,
    check_feed_generation,
    check_feed_xml,
    check_ffmpeg,
    check_internet,
    check_installed_model,
    check_launchd_services,
    check_ollama_installation,
    check_ollama_server,
    check_output_folders,
    check_piper,
    check_python,
    check_rss_feeds,
    check_voices,
    check_web_server,
    check_global_briefly,
    color_status,
    run_doctor,
)


@pytest.fixture(autouse=True)
def mock_default_config_path(tmp_path):
    with patch("briefly.config.get_default_config_path", return_value=tmp_path / "config.yaml"):
        yield



def test_color_status_success():
    result = CheckResult("Test", True, "Details")
    with patch("sys.stdout.isatty", return_value=True):
        status = color_status(result)
        assert "\033[92m" in status
        
    with patch("sys.stdout.isatty", return_value=False):
        status = color_status(result)
        assert "\033[92m" not in status
        assert status == "[✓] OK"


def test_color_status_warning():
    result = CheckResult("Test", True, "Details", is_warning=True)
    with patch("sys.stdout.isatty", return_value=True):
        status = color_status(result)
        assert "\033[93m" in status


def test_color_status_failure():
    result = CheckResult("Test", False, "Details")
    with patch("sys.stdout.isatty", return_value=True):
        status = color_status(result)
        assert "\033[91m" in status


def test_check_python_success():
    with patch("briefly.install.check_python_dependencies", return_value=[]):
        res = check_python()
        assert res.status is True
        assert "Abhängigkeiten OK" in res.details


def test_check_python_dependencies_missing():
    with patch("briefly.install.check_python_dependencies", return_value=["pydantic"]):
        res = check_python()
        assert res.status is False
        assert "Pakete fehlen" in res.details
        assert "pip install" in res.fix


def test_check_config_missing(tmp_path):
    res, config = check_config(tmp_path)
    assert res.status is False
    assert "nicht gefunden" in res.details.lower() or "not found" in res.details.lower()
    assert config is None



def test_check_config_valid(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("language:\n  target: de\n", encoding="utf-8")
    
    res, config = check_config(tmp_path)
    assert res.status is True
    assert config is not None
    assert config.language.target == "de"


def test_check_config_invalid(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("invalid_field: [unbalanced", encoding="utf-8")
    
    res, config = check_config(tmp_path)
    assert res.status is False
    assert "Validierungsfehler" in res.details or "invalid" in res.details or "YAML" in res.fix


def test_check_output_folders_success(tmp_path):
    from briefly.config import Config
    config = Config()
    config.sources.inbox.path = Path("inbox")
    config.tts.voices_dir = Path("voices")
    config.delivery.output_dir = Path("output")
    
    # Mock verify_write_permission
    with patch("briefly.install.verify_write_permission", return_value=True):
        res = check_output_folders(tmp_path, config)
        assert res.status is True


def test_check_output_folders_failure(tmp_path):
    from briefly.config import Config
    config = Config()
    
    with patch("briefly.install.verify_write_permission", return_value=False):
        res = check_output_folders(tmp_path, config)
        assert res.status is False
        assert "Schreibrechte fehlen" in res.details


def test_check_internet_success():
    mock_res = MagicMock()
    mock_res.status = 200
    mock_res.__enter__.return_value = mock_res
    with patch("urllib.request.urlopen", return_value=mock_res):
        res = check_internet()
        assert res.status is True


def test_check_internet_failure():
    with patch("urllib.request.urlopen", side_effect=Exception("Offline")):
        res = check_internet()
        assert res.status is False
        assert "Keine Verbindung" in res.details


def test_check_rss_feeds_success():
    from briefly.config import Config, RssFeedConfig
    config = Config()
    config.sources.rss.feeds = [RssFeedConfig(url="https://test.com/rss")]
    
    mock_res = MagicMock()
    mock_res.status = 200
    mock_res.read.return_value = b"<rss><channel><title>Test</title><item><title>Entry</title></item></channel></rss>"
    mock_res.__enter__.return_value = mock_res
    
    with patch("urllib.request.urlopen", return_value=mock_res):
        res = check_rss_feeds(config)
        assert res.status is True


def test_check_rss_feeds_failure():
    from briefly.config import Config, RssFeedConfig
    config = Config()
    config.sources.rss.feeds = [RssFeedConfig(url="https://test.com/rss")]
    
    with patch("urllib.request.urlopen", side_effect=Exception("Failed connection")):
        res = check_rss_feeds(config)
        assert res.status is False
        assert "Feeds fehlerhaft" in res.details


def test_check_ollama_installation_success():
    with patch("briefly.install.check_ollama_cli", return_value="/usr/local/bin/ollama"):
        res = check_ollama_installation()
        assert res.status is True


def test_check_ollama_installation_failure():
    with patch("briefly.install.check_ollama_cli", return_value=None):
        res = check_ollama_installation()
        assert res.status is False


def test_check_ollama_server_success():
    with patch("briefly.install.is_ollama_running", return_value=True):
        res = check_ollama_server()
        assert res.status is True


def test_check_ollama_server_failure():
    with patch("briefly.install.is_ollama_running", return_value=False):
        res = check_ollama_server()
        assert res.status is False


def test_check_installed_model_success():
    from briefly.config import Config
    config = Config()
    config.llm.model = "test-model"
    
    with patch("briefly.install.is_ollama_running", return_value=True):
        with patch("briefly.install.get_ollama_models", return_value=["test-model:latest"]):
            res = check_installed_model(config)
            assert res.status is True


def test_check_installed_model_missing():
    from briefly.config import Config
    config = Config()
    config.llm.model = "test-model"
    
    with patch("briefly.install.is_ollama_running", return_value=True):
        with patch("briefly.install.get_ollama_models", return_value=["llama3:latest"]):
            res = check_installed_model(config)
            assert res.status is False
            assert "fehlt in Ollama" in res.details


def test_check_piper_success():
    with patch.dict(sys.modules, {"piper": MagicMock()}):
        res = check_piper()
        assert res.status is True


def test_check_voices_success(tmp_path):
    from briefly.config import Config
    config = Config()
    
    with patch("briefly.install.check_piper_voice", return_value=True):
        res = check_voices(tmp_path, config)
        assert res.status is True


def test_check_voices_missing(tmp_path):
    from briefly.config import Config
    config = Config()
    
    with patch("briefly.install.check_piper_voice", return_value=False):
        res = check_voices(tmp_path, config)
        assert res.status is False
        assert "Fehlend:" in res.details


def test_check_web_server_localhost_warning():
    from briefly.config import Config
    config = Config()
    config.web.host = "127.0.0.1"
    config.delivery.base_url = "http://localhost:8787"
    
    with patch("socket.socket") as mock_socket:
        mock_instance = MagicMock()
        mock_socket.return_value = mock_instance
        res = check_web_server(config)
        assert res.status is True
        assert res.is_warning is True
        assert "localhost" in res.details


def test_check_web_server_unreachable():
    from briefly.config import Config
    config = Config()
    
    with patch("socket.socket", side_effect=Exception("Connection refused")):
        res = check_web_server(config)
        assert res.status is False
        assert "nicht erreichbar" in res.details
        assert "uvicorn" in res.fix


def test_check_feed_generation_success():
    res = check_feed_generation()
    assert res.status is True


def test_check_ffmpeg_success():
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        res = check_ffmpeg()
        assert res.status is True
        assert "funktionsfähig" in res.details


def test_check_ffmpeg_missing():
    with patch("shutil.which", return_value=None):
        res = check_ffmpeg()
        assert res.status is False
        assert "nicht im PATH gefunden" in res.details


def test_check_feed_xml_missing(tmp_path):
    from briefly.config import Config
    config = Config()
    config.delivery.output_dir = tmp_path / "output"
    
    res = check_feed_xml(config)
    assert res.status is False
    assert "existiert noch nicht" in res.details


def test_check_feed_xml_success(tmp_path):
    from briefly.config import Config
    config = Config()
    config.delivery.output_dir = tmp_path / "output"
    config.delivery.output_dir.mkdir(parents=True, exist_ok=True)
    feed_file = config.delivery.output_dir / "feed.xml"
    feed_file.write_text('<rss version="2.0"><channel><title>Briefly Feed</title></channel></rss>', encoding="utf-8")
    
    res = check_feed_xml(config)
    assert res.status is True
    assert "valides XML" in res.details


def test_check_feed_xml_invalid(tmp_path):
    from briefly.config import Config
    config = Config()
    config.delivery.output_dir = tmp_path / "output"
    config.delivery.output_dir.mkdir(parents=True, exist_ok=True)
    feed_file = config.delivery.output_dir / "feed.xml"
    feed_file.write_text('this is not XML', encoding="utf-8")
    
    res = check_feed_xml(config)
    assert res.status is False
    assert "Fehler beim XML-Parsen" in res.details


def test_check_launchd_services():
    # Test macOS/Windows cross-platform logic using mocks
    if sys.platform == "darwin":
        with patch("briefly.scheduler.check_daily_run_status", return_value=(True, "OK")):
            with patch("briefly.scheduler.check_web_server_status", return_value=(True, "OK")):
                res = check_launchd_services()
                assert res.status is True
                assert res.name == "launchd-Dienste"
    elif sys.platform in ("win32", "cygwin"):
        with patch("briefly.scheduler.check_daily_run_status", return_value=(True, "OK")):
            with patch("briefly.scheduler.check_web_server_status", return_value=(True, "OK")):
                res = check_launchd_services()
                assert res.status is True
                assert res.name == "Windows Scheduled Tasks"
    else:
        res = check_launchd_services()
        assert res.status is True
        assert res.is_warning is True



@patch("briefly.doctor.check_python", return_value=CheckResult("Python", True, "OK"))
@patch("briefly.doctor.check_config", return_value=(CheckResult("Config", True, "OK"), MagicMock()))
@patch("briefly.doctor.check_output_folders", return_value=CheckResult("Folders", True, "OK"))
@patch("briefly.doctor.check_internet", return_value=CheckResult("Internet", True, "OK"))
@patch("briefly.doctor.check_rss_feeds", return_value=CheckResult("Feeds", True, "OK"))
@patch("briefly.doctor.check_ollama_installation", return_value=CheckResult("Ollama CLI", True, "OK"))
@patch("briefly.doctor.check_ollama_server", return_value=CheckResult("Ollama Server", True, "OK"))
@patch("briefly.doctor.check_installed_model", return_value=CheckResult("Model", True, "OK"))
@patch("briefly.doctor.check_piper", return_value=CheckResult("Piper", True, "OK"))
@patch("briefly.doctor.check_voices", return_value=CheckResult("Voices", True, "OK"))
@patch("briefly.doctor.check_web_server", return_value=CheckResult("Web", True, "OK"))
@patch("briefly.doctor.check_feed_generation", return_value=CheckResult("Feed Gen", True, "OK"))
@patch("briefly.doctor.check_feed_xml", return_value=CheckResult("Feed XML", True, "OK"))
@patch("briefly.doctor.check_ffmpeg", return_value=CheckResult("FFmpeg", True, "OK"))
@patch("briefly.doctor.check_launchd_services", return_value=CheckResult("Launchd", True, "OK"))
@patch("briefly.doctor.check_global_briefly", return_value=CheckResult("Global PATH", True, "OK"))
@patch("sys.stdout")
def test_run_doctor_all_success(*args):
    # Tests full doctor run when all checks succeed
    ret = run_doctor()
    assert ret == 0


def test_check_global_briefly_success():
    with patch("sys.executable", "/project/briefly/.venv/bin/python"), \
         patch("os.environ", {"PATH": "/usr/local/bin:/project/briefly/.venv/bin"}), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("os.access", return_value=True):
        res = check_global_briefly()
        assert res.status is True
        assert res.name == "briefly command is globally available"
        assert res.details == "yes"


def test_check_global_briefly_failure():
    with patch("sys.executable", "/project/briefly/.venv/bin/python"), \
         patch("os.environ", {"PATH": "/project/briefly/.venv/bin"}), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("os.access", return_value=True):
        res = check_global_briefly()
        assert res.status is False
        assert res.is_warning is True
        assert res.name == "briefly command is globally available"
        assert res.details == "no"
