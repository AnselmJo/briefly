"""Cross-platform scheduler abstraction for macOS (launchd) and Windows (Task Scheduler).

Encapsulates all logic for registering, unregistering, and checking the status
of the daily brief run task and the web server background task.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# Task names and identifiers
MACOS_DAILY_LABEL = "com.briefly.dailyrun"
MACOS_WEB_LABEL = "com.briefly.web"

WIN_DAILY_LABEL = "BrieflyDailyRun"
WIN_WEB_LABEL = "BrieflyWeb"


def is_macos() -> bool:
    """True if running on macOS."""
    return sys.platform == "darwin"


def is_windows() -> bool:
    """True if running on Windows."""
    return sys.platform == "win32" or sys.platform == "cygwin"


def register_daily_run(
    python_bin: Path,
    project_dir: Path,
    hour: int,
    minute: int,
    interactive: bool = True,
) -> bool:
    """Registers the daily brief run task (usually 05:30) on macOS or Windows."""
    if is_macos():
        return _register_daily_run_macos(python_bin, project_dir, hour, minute, interactive)
    elif is_windows():
        return _register_daily_run_windows(python_bin, project_dir, hour, minute, interactive)
    else:
        # Unsupported platforms
        return False


def register_web_server(
    python_bin: Path,
    project_dir: Path,
    host: str,
    port: int,
    interactive: bool = True,
) -> bool:
    """Registers the background web server task on macOS or Windows."""
    if is_macos():
        return _register_web_server_macos(python_bin, project_dir, host, port, interactive)
    elif is_windows():
        return _register_web_server_windows(python_bin, project_dir, host, port, interactive)
    else:
        # Unsupported platforms
        return False


def check_daily_run_status() -> tuple[bool, str]:
    """Checks the status of the daily run task.

    Returns:
        (status, details_string)
    """
    if is_macos():
        return _check_macos_service_status(MACOS_DAILY_LABEL, MACOS_DAILY_LABEL + ".plist")
    elif is_windows():
        return _check_windows_task_status(WIN_DAILY_LABEL)
    else:
        return False, "Nicht unterstützt auf dieser Plattform"


def check_web_server_status() -> tuple[bool, str]:
    """Checks the status of the web server background task.

    Returns:
        (status, details_string)
    """
    if is_macos():
        return _check_macos_service_status(MACOS_WEB_LABEL, MACOS_WEB_LABEL + ".plist")
    elif is_windows():
        return _check_windows_task_status(WIN_WEB_LABEL)
    else:
        return False, "Nicht unterstützt auf dieser Plattform"


# --- macOS (launchd) Implementation ---

def _register_daily_run_macos(
    python_bin: Path,
    project_dir: Path,
    hour: int,
    minute: int,
    interactive: bool,
) -> bool:
    plist_dir = project_dir / "output"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / f"{MACOS_DAILY_LABEL}.plist"

    # Load templates
    tpl_path = project_dir / "scripts" / "launchd" / f"{MACOS_DAILY_LABEL}.plist"
    if not tpl_path.exists():
        print(f"Fehler: launchd-Vorlage nicht gefunden unter: {tpl_path}", file=sys.stderr)
        return False

    try:
        content = tpl_path.read_text(encoding="utf-8")
        content = content.replace("__PYTHON_BIN__", str(python_bin.resolve()))
        content = content.replace("__PROJECT_DIR__", str(project_dir.resolve()))
        content = content.replace("<integer>5</integer>", f"<integer>{hour}</integer>")
        content = content.replace("<integer>30</integer>", f"<integer>{minute}</integer>")
        plist_path.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"Fehler beim Erstellen der launchd-Datei {MACOS_DAILY_LABEL}.plist: {e}", file=sys.stderr)
        return False

    launchagents_dir = Path.home() / "Library" / "LaunchAgents"
    launchagents_dir.mkdir(parents=True, exist_ok=True)
    return _install_launchd_plist(f"{MACOS_DAILY_LABEL}.plist", plist_path, launchagents_dir)


def _register_web_server_macos(
    python_bin: Path,
    project_dir: Path,
    host: str,
    port: int,
    interactive: bool,
) -> bool:
    plist_dir = project_dir / "output"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / f"{MACOS_WEB_LABEL}.plist"

    tpl_path = project_dir / "scripts" / "launchd" / f"{MACOS_WEB_LABEL}.plist"
    if not tpl_path.exists():
        print(f"Fehler: launchd-Vorlage nicht gefunden unter: {tpl_path}", file=sys.stderr)
        return False

    try:
        content = tpl_path.read_text(encoding="utf-8")
        content = content.replace("__PYTHON_BIN__", str(python_bin.resolve()))
        content = content.replace("__PROJECT_DIR__", str(project_dir.resolve()))
        content = content.replace("0.0.0.0", host)
        content = content.replace("8787", str(port))
        plist_path.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"Fehler beim Erstellen der launchd-Datei {MACOS_WEB_LABEL}.plist: {e}", file=sys.stderr)
        return False

    launchagents_dir = Path.home() / "Library" / "LaunchAgents"
    launchagents_dir.mkdir(parents=True, exist_ok=True)
    return _install_launchd_plist(f"{MACOS_WEB_LABEL}.plist", plist_path, launchagents_dir)


def _install_launchd_plist(plist_name: str, src_path: Path, dest_dir: Path) -> bool:
    dest_path = dest_dir / plist_name
    try:
        # Eventuell vorhandenen Dienst vorher entladen
        subprocess.run(["launchctl", "unload", str(dest_path)], capture_output=True, check=False)
        shutil.copy(src_path, dest_path)
        dest_path.chmod(0o644)
        result = subprocess.run(["launchctl", "load", "-w", str(dest_path)], capture_output=True, check=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Fehler bei launchd-Installation für {plist_name}: {e}", file=sys.stderr)
        return False


def _check_macos_service_status(label: str, plist_name: str) -> tuple[bool, str]:
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_path = plist_dir / plist_name
    if not plist_path.exists():
        return False, f"Datei fehlt in LaunchAgents: {plist_name}"

    try:
        res = subprocess.run(["launchctl", "list", label], capture_output=True, text=True)
        if res.returncode == 0:
            return True, "Dienst geladen und aktiv"
        else:
            return False, f"Dienst {label} nicht geladen"
    except Exception as e:
        return False, f"Fehler bei launchctl list: {e}"


# --- Windows (Task Scheduler) Implementation ---

def _register_daily_run_windows(
    python_bin: Path,
    project_dir: Path,
    hour: int,
    minute: int,
    interactive: bool,
) -> bool:
    task_name = WIN_DAILY_LABEL
    python_path = str(python_bin.resolve())
    time_str = f"{hour:02d}:{minute:02d}"

    # schtasks Command for daily run
    cmd = [
        "schtasks",
        "/create",
        "/tn",
        task_name,
        "/tr",
        f'"{python_path}" -m briefly.cli run',
        "/sc",
        "daily",
        "/st",
        time_str,
        "/f",
    ]

    try:
        # Delete existing task if present to avoid errors
        subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"], capture_output=True, check=False)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Fehler bei Windows-Taskregistrierung für {task_name}: {e}", file=sys.stderr)
        print("Hinweis: Windows Task Scheduler erfordert eventuell passende Rechte.", file=sys.stderr)
        return False


def _register_web_server_windows(
    python_bin: Path,
    project_dir: Path,
    host: str,
    port: int,
    interactive: bool,
) -> bool:
    task_name = WIN_WEB_LABEL
    python_path = str(python_bin.resolve())
    
    cmd = [
        "schtasks",
        "/create",
        "/tn",
        task_name,
        "/tr",
        f'"{python_path}" -m uvicorn briefly.web.app:app --host {host} --port {port}',
        "/sc",
        "onlogon",
        "/f",
    ]

    try:
        # Delete existing task if present to avoid errors
        subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"], capture_output=True, check=False)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Fehler bei Windows-Taskregistrierung für {task_name}: {e}", file=sys.stderr)
        return False


def _check_windows_task_status(task_name: str) -> tuple[bool, str]:
    try:
        res = subprocess.run(["schtasks", "/query", "/tn", task_name, "/fo", "LIST"], capture_output=True, text=True)
        if res.returncode == 0:
            status = "Registriert"
            for line in res.stdout.splitlines():
                if line.startswith("Status:") or line.startswith("Task To Run:") or "Status" in line:
                    status = line.strip()
            return True, f"Task registriert ({status})"
        else:
            return False, f"Task {task_name} nicht registriert"
    except Exception as e:
        return False, f"Fehler bei schtasks query: {e}"
