import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from briefly.install import (
    check_piper_voice,
    check_python_dependencies,
    get_local_ip,
    is_model_installed,
    is_ollama_running,
    run_install,
    verify_write_permission,
)


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


@patch("briefly.install.get_local_ip", return_value="192.168.1.100")
@patch("briefly.install.check_python_dependencies", return_value=[])
@patch("shutil.which")
@patch("briefly.install.is_ollama_running", return_value=True)
@patch("briefly.install.get_ollama_models", return_value=["qwen3:8b"])
@patch("sys.stdout")
def test_run_install_full_success(mock_stdout, mock_models, mock_running, mock_which, mock_deps, mock_ip, tmp_path):
    project_root = tmp_path / "briefly_project"
    project_root.mkdir()
    
    config_dir = project_root / "config"
    config_dir.mkdir()
    (config_dir / "config.example.yaml").write_text("delivery:\n  base_url: \"http://<mac-lan-ip>:8787\"\nllm:\n  model: qwen3:8b\ntts:\n  voice_de: de_voice\n  voice_en: en_voice\n  voices_dir: data/voices\nsources:\n  inbox:\n    path: data/inbox\nweb:\n  host: 0.0.0.0\n", encoding="utf-8")
    
    scripts_dir = project_root / "scripts" / "launchd"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "com.briefly.dailyrun.plist").write_text("__PYTHON_BIN__\n__PROJECT_DIR__")
    (scripts_dir / "com.briefly.web.plist").write_text("__PYTHON_BIN__\n__PROJECT_DIR__")
    
    # Piper voices setup
    voices_dir = project_root / "data" / "voices"
    voices_dir.mkdir(parents=True)
    (voices_dir / "de_voice.onnx").write_text("onnx")
    (voices_dir / "de_voice.onnx.json").write_text("json")
    (voices_dir / "en_voice.onnx").write_text("onnx")
    (voices_dir / "en_voice.onnx.json").write_text("json")
    
    mock_which.side_effect = lambda cmd: "/usr/local/bin/" + cmd
    
    with patch("briefly.install._get_project_root", return_value=project_root):
        ret = run_install(interactive=False)
        
        assert ret == 0
        assert (project_root / "config.yaml").exists()
        config_content = (project_root / "config.yaml").read_text(encoding="utf-8")
        assert "http://192.168.1.100:8787" in config_content
        
        # Verify launchd plists generated
        assert (project_root / "output" / "com.briefly.dailyrun.plist").exists()
        assert (project_root / "output" / "com.briefly.web.plist").exists()
        
        dailyrun_content = (project_root / "output" / "com.briefly.dailyrun.plist").read_text()
        assert sys.executable in dailyrun_content
        assert str(project_root.resolve()) in dailyrun_content


@patch("briefly.install.check_python_dependencies", return_value=["pydantic", "pyyaml"])
@patch("sys.stdout")
def test_run_install_missing_dependency(mock_stdout, mock_deps, tmp_path):
    project_root = tmp_path / "briefly_project"
    project_root.mkdir()
    
    config_dir = project_root / "config"
    config_dir.mkdir()
    (config_dir / "config.example.yaml").write_text("llm:\n  model: qwen3:8b", encoding="utf-8")
    
    with patch("briefly.install._get_project_root", return_value=project_root):
        ret = run_install(interactive=False)
        assert ret == 1

