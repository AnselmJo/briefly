import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from briefly.config import Config, save_config
from briefly.daemon import (
    is_pid_running,
    restart_daemon,
    start_daemon,
    status_daemon,
    stop_daemon,
    terminate_pid,
)


@pytest.fixture
def mock_config(tmp_path):
    project_root = tmp_path / "briefly_project"
    project_root.mkdir(parents=True, exist_ok=True)
    config_path = project_root / "config.yaml"
    config = Config()
    config.delivery.output_dir = project_root / "output"
    config.sources.inbox.path = project_root / "inbox"
    config.delivery.port = 8787
    save_config(config, config_path)
    return config_path


def test_is_pid_running_invalid():
    assert is_pid_running(-1) is False
    assert is_pid_running(0) is False


def test_is_pid_running_active():
    if sys.platform == "win32":
        with patch("ctypes.windll.kernel32.OpenProcess", return_value=123), \
             patch("ctypes.windll.kernel32.GetExitCodeProcess", side_effect=lambda h, code: setattr(code, 'value', 259) or True), \
             patch("ctypes.windll.kernel32.CloseHandle", return_value=True):
            assert is_pid_running(9999) is True
    else:
        with patch("os.kill", return_value=None):
            assert is_pid_running(9999) is True


def test_is_pid_running_dead():
    if sys.platform == "win32":
        with patch("ctypes.windll.kernel32.OpenProcess", return_value=0):
            assert is_pid_running(9999) is False
    else:
        with patch("os.kill", side_effect=OSError("Process not found")):
            assert is_pid_running(9999) is False


def test_terminate_pid():
    with patch("briefly.daemon.is_pid_running", side_effect=[True, False]):
        if sys.platform == "win32":
            with patch("os.kill", return_value=None):
                assert terminate_pid(9999) is True
        else:
            with patch("os.kill", return_value=None):
                assert terminate_pid(9999) is True


@patch("subprocess.Popen")
@patch("socket.socket")
@patch("briefly.scheduler.register_daily_run", return_value=True)
@patch("urllib.request.urlopen")
@patch("briefly.daemon.get_local_ip", return_value="192.168.1.50")
def test_start_daemon_success(mock_get_ip, mock_urlopen, mock_register, mock_socket, mock_popen, mock_config):
    # Mock socket connect fails (port is free)
    mock_socket.return_value.connect.side_effect = Exception("Free")
    
    # Mock urlopen returns 200 response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_popen.return_value = mock_proc

    with patch("briefly.daemon.is_pid_running", return_value=False):
        ret = start_daemon(mock_config)
        assert ret == 0
        
        # Verify pid file is written
        from briefly.config import get_user_dir
        pid_file = get_user_dir() / "web_server.pid"
        assert pid_file.exists()
        assert pid_file.read_text(encoding="utf-8") == "12345"


@patch("socket.socket")
@patch("briefly.daemon.get_local_ip", return_value="192.168.1.50")
def test_start_daemon_port_busy(mock_get_ip, mock_socket, mock_config):
    # Mock socket connect succeeds (port is busy)
    mock_socket.return_value.connect.return_value = None

    with patch("briefly.daemon.is_pid_running", return_value=False):
        ret = start_daemon(mock_config)
        assert ret == 1


def test_stop_daemon_not_active(mock_config):
    from briefly.config import get_user_dir
    pid_file = get_user_dir() / "web_server.pid"
    pid_file.unlink(missing_ok=True)
    
    ret = stop_daemon(mock_config)
    assert ret == 0


@patch("briefly.daemon.terminate_pid", return_value=True)
@patch("briefly.daemon.is_pid_running", return_value=True)
def test_stop_daemon_success(mock_running, mock_terminate, mock_config):
    from briefly.config import get_user_dir
    pid_file = get_user_dir() / "web_server.pid"
    pid_file.write_text("54321", encoding="utf-8")
    
    ret = stop_daemon(mock_config)
    assert ret == 0
    assert not pid_file.exists()


@patch("briefly.scheduler.check_daily_run_status", return_value=(True, "OK"))
@patch("briefly.daemon.is_pid_running", return_value=True)
@patch("urllib.request.urlopen")
@patch("briefly.daemon.get_local_ip", return_value="192.168.1.50")
def test_status_daemon_active(mock_get_ip, mock_urlopen, mock_running, mock_check, mock_config, capsys):
    from briefly.config import get_user_dir
    pid_file = get_user_dir() / "web_server.pid"
    pid_file.write_text("12345", encoding="utf-8")
    
    # Mock urlopen returns 200 response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    # Write mock last_run.json
    last_run_file = get_user_dir() / "last_run.json"
    last_run_file.write_text(
        json.dumps({"timestamp": "2026-07-05T05:30:00", "success": True, "error": None}),
        encoding="utf-8"
    )
    
    ret = status_daemon(mock_config)
    assert ret == 0
    captured = capsys.readouterr()
    assert "Prozess läuft:       Ja" in captured.out
    assert "Lokal erreichbar:    Ja" in captured.out
    assert "WLAN/LAN erreichbar: Ja" in captured.out


@patch("briefly.scheduler.check_daily_run_status", return_value=(False, "Uninstalled"))
@patch("briefly.daemon.is_pid_running", return_value=False)
@patch("urllib.request.urlopen")
@patch("briefly.daemon.get_local_ip", return_value="192.168.1.50")
def test_status_daemon_inactive(mock_get_ip, mock_urlopen, mock_running, mock_check, mock_config, capsys):
    from briefly.config import get_user_dir
    pid_file = get_user_dir() / "web_server.pid"
    pid_file.unlink(missing_ok=True)
    
    # Mock urlopen fails (inactive)
    mock_urlopen.side_effect = Exception("Unreachable")
    
    ret = status_daemon(mock_config)
    assert ret == 1  # 1 because web server is inactive / scheduler is missing
    captured = capsys.readouterr()
    assert "Prozess läuft:       Nein" in captured.out
    assert "Lokal erreichbar:    Nein" in captured.out
    assert "WLAN/LAN erreichbar: Nein" in captured.out


@patch("briefly.daemon.stop_daemon", return_value=0)
@patch("briefly.daemon.start_daemon", return_value=0)
def test_restart_daemon(mock_start, mock_stop, mock_config):
    ret = restart_daemon(mock_config)
    assert ret == 0
    mock_stop.assert_called_once_with(mock_config)
    mock_start.assert_called_once_with(mock_config)
