import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from briefly.config import ConfigValidationError
from briefly.update import get_repo_dir, has_uncommitted_changes, run_update


def test_get_repo_dir():
    # It should resolve the Briefly project dir or fall back to cwd
    with patch("briefly.update.Path") as mock_path:
        mock_path.return_value.resolve.return_value.parent.parent.parent = Path("/test/briefly")
        # Simulate .git folder exists
        with patch.object(Path, "is_dir", return_value=True):
            p = get_repo_dir()
            assert p is not None


def test_has_uncommitted_changes_clean():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        assert has_uncommitted_changes(Path("/dummy")) is False


def test_has_uncommitted_changes_dirty():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=" M src/briefly/cli.py\n", returncode=0)
        assert has_uncommitted_changes(Path("/dummy")) is True


def test_has_uncommitted_changes_untracked_only_is_clean():
    # Untracked files only (?? config.yaml) should not count as uncommitted repository changes
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="?? config.yaml\n", returncode=0)
        assert has_uncommitted_changes(Path("/dummy")) is False


def test_run_update_dirty_aborts(tmp_path):
    config_path = tmp_path / "config.yaml"
    with patch("briefly.update.get_repo_dir", return_value=tmp_path), \
         patch("briefly.update.has_uncommitted_changes", return_value=True):
        ret = run_update(config_path)
        assert ret == 1


def test_run_update_up_to_date(tmp_path):
    config_path = tmp_path / "config.yaml"
    
    def mock_run_cmd(cmd, *args, **kwargs):
        if "rev-parse" in cmd:
            return MagicMock(stdout="commit-123\n")
        elif "pull" in cmd:
            return MagicMock(returncode=0)
        elif "status" in cmd:
            return MagicMock(stdout="")
        return MagicMock()

    with patch("briefly.update.get_repo_dir", return_value=tmp_path), \
         patch("briefly.update.has_uncommitted_changes", return_value=False), \
         patch("subprocess.run", side_effect=mock_run_cmd):
        ret = run_update(config_path)
        assert ret == 0


def test_run_update_success_with_pyproject_change_and_daemon_restart(tmp_path):
    config_path = tmp_path / "config.yaml"
    
    called_cmds = []

    def mock_run_cmd(cmd, *args, **kwargs):
        called_cmds.append(cmd)
        if "rev-parse" in cmd:
            # First rev-parse (old) -> commit-1, second (new) -> commit-2
            if len([c for c in called_cmds if "rev-parse" in c]) == 1:
                return MagicMock(stdout="commit-1\n")
            else:
                return MagicMock(stdout="commit-2\n")
        elif "pull" in cmd:
            return MagicMock(returncode=0)
        elif "diff" in cmd:
            # Return pyproject.toml as changed
            return MagicMock(stdout="pyproject.toml\nsrc/briefly/cli.py\n")
        elif "log" in cmd:
            return MagicMock(stdout="commit-2: Feat: added update command\n")
        return MagicMock(returncode=0)

    # Mock daemon PID existence to trigger web server restart
    mock_pid_file = MagicMock()
    mock_pid_file.exists.return_value = True
    mock_pid_file.read_text.return_value = "9999"

    with patch("briefly.update.get_repo_dir", return_value=tmp_path), \
         patch("briefly.update.has_uncommitted_changes", return_value=False), \
         patch("subprocess.run", side_effect=mock_run_cmd), \
         patch("briefly.update.load_config") as mock_load_config, \
         patch("briefly.config.get_user_dir", return_value=tmp_path), \
         patch("pathlib.Path.__truediv__", return_value=mock_pid_file), \
         patch("briefly.update.sys.executable", "python"), \
         patch("briefly.update.ConfigValidationError") as mock_validation_err, \
         patch("briefly.daemon.is_pid_running", return_value=True), \
         patch("briefly.daemon.stop_daemon") as mock_stop, \
         patch("briefly.daemon.start_daemon") as mock_start:
         
        ret = run_update(config_path)
        assert ret == 0
        
        # Verify dependency re-installation was triggered
        any_pip_install = any("pip" in cmd and "install" in cmd for cmd in called_cmds)
        assert any_pip_install is True

        # Verify config loading was triggered
        mock_load_config.assert_called_once_with(config_path)

        # Verify background daemon restart was triggered
        mock_stop.assert_called_once_with(config_path)
        mock_start.assert_called_once_with(config_path)


def test_run_update_invalid_config_warns_only(tmp_path):
    config_path = tmp_path / "config.yaml"

    def mock_run_cmd(cmd, *args, **kwargs):
        if "rev-parse" in cmd:
            if "commit-2" in str(cmd):
                return MagicMock(stdout="commit-2\n")
            # Alternate values
            return MagicMock(stdout="commit-1\n" if "commit-1" not in cmd else "commit-2\n")
        return MagicMock(returncode=0)

    # Make load_config raise validation error
    with patch("briefly.update.get_repo_dir", return_value=tmp_path), \
         patch("briefly.update.has_uncommitted_changes", return_value=False), \
         patch("subprocess.run", return_value=MagicMock(stdout="commit-2\n", returncode=0)), \
         patch("briefly.update.load_config", side_effect=ConfigValidationError("test.key", "bad_val", "validation failed", "fix it")), \
         patch("briefly.config.get_user_dir", return_value=tmp_path):
         
        # We manually stub subprocess.run to yield diff commits
        call_count = 0
        def side_effect_run(cmd, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if "rev-parse" in cmd:
                if call_count == 1:
                    return MagicMock(stdout="commit-1\n")
                else:
                    return MagicMock(stdout="commit-2\n")
            if "diff" in cmd:
                return MagicMock(stdout="")
            return MagicMock(returncode=0)
            
        with patch("subprocess.run", side_effect=side_effect_run):
            ret = run_update(config_path)
            # The update should complete with 0 (success) even if config validation warns
            assert ret == 0
