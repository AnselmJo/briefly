import pytest
import sys
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

from briefly.install import (
    check_piper_voice,
    check_python_dependencies,
    get_local_ip,
    is_model_installed,
    is_ollama_running,
    run_install,
    verify_write_permission,
    check_disk_space,
    check_port_availability,
)

@pytest.fixture(autouse=True)
def mock_default_config_path(tmp_path):
    project_root = tmp_path / "briefly_project"
    with patch("briefly.install.get_default_config_path", return_value=project_root / "config.yaml"):
        yield



def test_get_local_ip():
    with patch("socket.socket") as mock_socket:
        mock_instance = MagicMock()
        mock_instance.getsockname.return_value = ["192.168.1.50"]
        mock_socket.return_value = mock_instance
        
        ip = get_local_ip()
        assert ip == "192.168.1.50"


def test_get_local_ip_failure():
    with patch("socket.socket", side_effect=Exception("Connection failed")):
        ip = get_local_ip()
        assert ip == "127.0.0.1"


def test_check_python_dependencies_success():
    with patch("importlib.metadata.distribution") as mock_dist:
        mock_dist.return_value = MagicMock()
        missing = check_python_dependencies()
        assert len(missing) == 0


def test_check_python_dependencies_missing():
    def side_effect(name):
        import importlib.metadata
        if name in ["piper-tts", "feedgen"]:
            raise importlib.metadata.PackageNotFoundError()
        return MagicMock()

    with patch("importlib.metadata.distribution", side_effect=side_effect):
        with patch("importlib.import_module", side_effect=ImportError("Module not found")):
            missing = check_python_dependencies()
            assert "piper-tts" in missing
            assert "feedgen" in missing
            assert "pydantic" not in missing


def test_is_ollama_running_success():
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__.return_value = mock_response
    with patch("urllib.request.urlopen", return_value=mock_response):
        assert is_ollama_running() is True


def test_is_ollama_running_failure():
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        assert is_ollama_running() is False


def test_is_model_installed():
    models = ["qwen3:8b", "llama3:latest"]
    assert is_model_installed("qwen3:8b", models) is True
    assert is_model_installed("qwen3", models) is True
    assert is_model_installed("llama3", models) is True
    assert is_model_installed("missing_model", models) is False


def test_check_piper_voice(tmp_path):
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    
    assert check_piper_voice("de_voice", voices_dir) is False
    
    (voices_dir / "de_voice.onnx").write_text("dummy")
    (voices_dir / "de_voice.onnx.json").write_text("dummy json")
    
    assert check_piper_voice("de_voice", voices_dir) is True


def test_verify_write_permission(tmp_path):
    assert verify_write_permission(tmp_path) is True
    
    # Read-only directory simulation
    read_only_dir = tmp_path / "readonly"
    read_only_dir.mkdir()
    
    with patch.object(Path, "mkdir", side_effect=PermissionError("Permission denied")):
        assert verify_write_permission(read_only_dir) is False


def test_check_disk_space():
    with patch("shutil.disk_usage", return_value=MagicMock(free=10 * 1024**3)):
        success, info = check_disk_space(Path("."), 5.0)
        assert success is True
        assert "10.0 GB" in info

    with patch("shutil.disk_usage", return_value=MagicMock(free=2 * 1024**3)):
        success, info = check_disk_space(Path("."), 5.0)
        assert success is False
        assert "2.0 GB" in info


def test_check_port_availability():
    # Free port
    with patch("socket.socket"):
        success, info = check_port_availability("0.0.0.0", 8787)
        assert success is True

    # Busy port
    with patch("socket.socket", side_effect=Exception("Port in use")):
        success, info = check_port_availability("0.0.0.0", 8787)
        assert success is False
        assert "Belegt" in info


def _setup_mock_project_root(project_root):
    project_root.mkdir(parents=True, exist_ok=True)
    config_dir = project_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.example.yaml").write_text(
        "delivery:\n  base_url: \"http://<mac-lan-ip>:8787\"\n  output_dir: output\n"
        "llm:\n  model: qwen3:8b\n"
        "tts:\n  voice_de: de_voice\n  voice_en: en_voice\n  voices_dir: data/voices\n"
        "sources:\n  inbox:\n    path: data/inbox\n"
        "web:\n  host: 0.0.0.0\n  port: 8787\n"
        "schedule:\n  hour: 5\n  minute: 30\n",
        encoding="utf-8"
    )
    
    scripts_dir = project_root / "scripts" / "launchd"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "com.briefly.dailyrun.plist").write_text("__PYTHON_BIN__\n__PROJECT_DIR__")
    (scripts_dir / "com.briefly.web.plist").write_text("__PYTHON_BIN__\n__PROJECT_DIR__")
    
    voices_dir = project_root / "data" / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)
    (voices_dir / "de_voice.onnx").write_text("onnx")
    (voices_dir / "de_voice.onnx.json").write_text("json")
    (voices_dir / "en_voice.onnx").write_text("onnx")
    (voices_dir / "en_voice.onnx.json").write_text("json")


@patch("briefly.install.get_local_ip", return_value="192.168.1.100")
@patch("briefly.install.check_python_dependencies", return_value=[])
@patch("shutil.which")
@patch("briefly.install.is_ollama_running", return_value=True)
@patch("briefly.install.get_ollama_models", return_value=["qwen3:8b"])
@patch("briefly.install.check_disk_space", return_value=(True, "10.0 GB frei"))
@patch("briefly.install.check_port_availability", return_value=(True, "Frei"))
@patch("subprocess.run")
def test_run_install_full_success(
    mock_run, mock_port, mock_disk, mock_models, mock_running, mock_which, mock_deps, mock_ip, tmp_path, capsys
):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)
    
    mock_which.side_effect = lambda cmd: "/usr/local/bin/" + cmd
    mock_run.return_value = MagicMock(returncode=0)
    
    with patch("briefly.install._get_project_root", return_value=project_root):
        ret = run_install(interactive=False)
        assert ret == 0
        assert (project_root / "config.yaml").exists()
        config_content = (project_root / "config.yaml").read_text(encoding="utf-8")
        assert "http://192.168.1.100:8787" in config_content


# Failure path tests using context manager mocks

def test_run_install_missing_dependency(tmp_path, capsys):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=["pydantic", "pyyaml"]):
        
        ret = run_install(interactive=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "Python-Pakete" in captured.out or "Python-Pakete" in captured.err
        assert "pip install -e ." in captured.out or "pip install -e ." in captured.err


def test_run_install_config_syntax_error(tmp_path, capsys):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)
    
    # Write invalid config.yaml first to trigger load error
    (project_root / "config.yaml").write_text("invalid_yaml: [unbalanced", encoding="utf-8")

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=[]):
        
        ret = run_install(interactive=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "Konfiguration konnte nicht geladen werden" in captured.err or "Konfiguration konnte nicht geladen werden" in captured.out


def test_run_install_no_write_permission(tmp_path, capsys):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=[]), \
         patch("briefly.install.verify_write_permission", return_value=False):
        
        ret = run_install(interactive=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "Schreibrechte fehlen" in captured.out or "Schreibrechte" in captured.err


def test_run_install_low_disk_space(tmp_path, capsys):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=[]), \
         patch("briefly.install.check_disk_space", return_value=(False, "1.2 GB frei")):
        
        ret = run_install(interactive=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "Speicherplatz" in captured.out or "Speicherplatz" in captured.err


def test_run_install_ffmpeg_missing(tmp_path, capsys):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=[]), \
         patch("briefly.install.check_disk_space", return_value=(True, "10 GB")), \
         patch("shutil.which", side_effect=lambda name: None if name == "ffmpeg" else "/usr/local/bin/" + name):
        
        ret = run_install(interactive=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "ffmpeg" in captured.out or "ffmpeg" in captured.err


def test_run_install_port_in_use(tmp_path, capsys):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=[]), \
         patch("briefly.install.check_disk_space", return_value=(True, "10 GB")), \
         patch("shutil.which", return_value="/usr/local/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run, \
         patch("briefly.install.check_port_availability", return_value=(False, "Belegt")):
         
        mock_run.return_value = MagicMock(returncode=0)
        ret = run_install(interactive=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "Port belegt" in captured.out or "Port" in captured.err


def test_run_install_ollama_missing(tmp_path, capsys):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=[]), \
         patch("briefly.install.check_disk_space", return_value=(True, "10 GB")), \
         patch("shutil.which", side_effect=lambda name: "/usr/local/bin/ffmpeg" if name == "ffmpeg" else None), \
         patch("subprocess.run") as mock_run, \
         patch("briefly.install.check_port_availability", return_value=(True, "Frei")):
         
        mock_run.return_value = MagicMock(returncode=0)
        ret = run_install(interactive=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "Ollama: Die Anwendung 'Ollama' ist nicht auf deinem System installiert" in captured.out


def test_run_install_ollama_not_running(tmp_path, capsys):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=[]), \
         patch("briefly.install.check_disk_space", return_value=(True, "10 GB")), \
         patch("shutil.which", return_value="/usr/local/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run, \
         patch("briefly.install.check_port_availability", return_value=(True, "Frei")), \
         patch("briefly.install.is_ollama_running", return_value=False):
         
        mock_run.return_value = MagicMock(returncode=0)
        ret = run_install(interactive=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "Ollama-Hintergrunddienst läuft nicht" in captured.out


def test_run_install_ollama_model_missing(tmp_path, capsys):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=[]), \
         patch("briefly.install.check_disk_space", return_value=(True, "10 GB")), \
         patch("shutil.which", return_value="/usr/local/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run, \
         patch("briefly.install.check_port_availability", return_value=(True, "Frei")), \
         patch("briefly.install.is_ollama_running", return_value=True), \
         patch("briefly.install.get_ollama_models", return_value=["different-model:latest"]):
         
        mock_run.return_value = MagicMock(returncode=0)
        ret = run_install(interactive=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "Ollama Modell: Das Modell" in captured.out


def test_run_install_voices_missing(tmp_path, capsys):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=[]), \
         patch("briefly.install.check_disk_space", return_value=(True, "10 GB")), \
         patch("shutil.which", return_value="/usr/local/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run, \
         patch("briefly.install.check_port_availability", return_value=(True, "Frei")), \
         patch("briefly.install.is_ollama_running", return_value=True), \
         patch("briefly.install.get_ollama_models", return_value=["qwen3:8b"]), \
         patch("briefly.install.check_piper_voice", side_effect=[False, False, True, True]):
         
        mock_run.return_value = MagicMock(returncode=0)
        ret = run_install(interactive=False)
        assert ret == 0
        
        # Verify subprocess.run was called to download the voice packages
        mock_run.assert_any_call(
            [sys.executable, "-m", "piper.download_voices", "de_voice", "--data-dir", ANY],
            check=True
        )
        mock_run.assert_any_call(
            [sys.executable, "-m", "piper.download_voices", "en_voice", "--data-dir", ANY],
            check=True
        )


def test_run_install_voices_missing_download_fails(tmp_path, capsys):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)

    def side_effect_run(cmd, *args, **kwargs):
        if "piper.download_voices" in cmd:
            raise subprocess.CalledProcessError(1, cmd, stderr="Network error")
        return MagicMock(returncode=0)

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=[]), \
         patch("briefly.install.check_disk_space", return_value=(True, "10 GB")), \
         patch("shutil.which", return_value="/usr/local/bin/ffmpeg"), \
         patch("subprocess.run", side_effect=side_effect_run), \
         patch("briefly.install.check_port_availability", return_value=(True, "Frei")), \
         patch("briefly.install.is_ollama_running", return_value=True), \
         patch("briefly.install.get_ollama_models", return_value=["qwen3:8b"]), \
         patch("briefly.install.check_piper_voice", return_value=False):
         
        ret = run_install(interactive=False)
        assert ret == 1
        captured = capsys.readouterr()
        assert "Fehler beim Herunterladen der Stimme" in captured.out


def test_run_install_ollama_model_missing_pulls_automatically(tmp_path):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=[]), \
         patch("briefly.install.check_disk_space", return_value=(True, "10 GB")), \
         patch("shutil.which", return_value="/usr/local/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run, \
         patch("briefly.install.check_port_availability", return_value=(True, "Frei")), \
         patch("briefly.install.is_ollama_running", return_value=True), \
         patch("briefly.install.get_ollama_models", return_value=["different-model:latest"]):
         
        mock_run.return_value = MagicMock(returncode=0)
        run_install(interactive=False)
        
        # Verify subprocess.run was called to pull the missing model
        mock_run.assert_any_call(["ollama", "pull", "qwen3:8b"], check=True)


def test_run_install_ollama_model_already_present_short_circuits(tmp_path):
    project_root = tmp_path / "briefly_project"
    _setup_mock_project_root(project_root)

    with patch("briefly.install._get_project_root", return_value=project_root), \
         patch("briefly.install.check_python_dependencies", return_value=[]), \
         patch("briefly.install.check_disk_space", return_value=(True, "10 GB")), \
         patch("shutil.which", return_value="/usr/local/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run, \
         patch("briefly.install.check_port_availability", return_value=(True, "Frei")), \
         patch("briefly.install.is_ollama_running", return_value=True), \
         patch("briefly.install.get_ollama_models", return_value=["qwen3:8b"]):
         
        mock_run.return_value = MagicMock(returncode=0)
        run_install(interactive=False)
        
        # Verify subprocess.run was NOT called to pull qwen3:8b since it is already present
        for call in mock_run.call_args_list:
            assert "pull" not in call[0][0]
