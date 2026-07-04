"""Daemon management for Briefly: start, stop, restart, and status.

Handles background execution of the FastAPI server and checking the OS scheduler status.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path

from briefly import scheduler
from briefly.config import get_user_dir, load_config


def is_pid_running(pid: int) -> bool:
    """Checks cross-platform if a process PID is currently running."""
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32" or sys.platform == "cygwin":
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                exit_code = ctypes.c_ulong()
                ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                ctypes.windll.kernel32.CloseHandle(handle)
                return exit_code.value == 259  # STILL_ACTIVE
            return False
        else:
            os.kill(pid, 0)
            return True
    except OSError:
        return False


def terminate_pid(pid: int) -> bool:
    """Terminates a process PID cross-platform, falling back to force kill if needed."""
    try:
        if sys.platform == "win32" or sys.platform == "cygwin":
            import signal
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
            for _ in range(10):
                if not is_pid_running(pid):
                    return True
                time.sleep(0.1)
            try:
                # Force termination using taskkill on Windows if still running
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, check=False)
            except Exception:
                pass
        else:
            import signal
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
            for _ in range(10):
                if not is_pid_running(pid):
                    return True
                time.sleep(0.1)
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        return not is_pid_running(pid)
    except OSError:
        return False


def start_daemon(config_path: Path) -> int:
    """Starts the web server in the background and registers the scheduler."""
    config = load_config(config_path)
    user_dir = get_user_dir()
    pid_file = user_dir / "web_server.pid"
    
    # Check if already running
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            if is_pid_running(pid):
                print(f"Webserver läuft bereits (PID {pid}, http://{config.web.host}:{config.web.port})")
                return 0
        except ValueError:
            pass

    # Port availability check (to prevent double startup)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(("127.0.0.1", config.web.port))
        s.close()
        print(f"Fehler: Port {config.web.port} wird bereits verwendet. Ist der Webserver schon aktiv?")
        return 1
    except Exception:
        pass

    # Start web server in the background
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "briefly.web.app:app",
        "--host",
        config.web.host,
        "--port",
        str(config.web.port),
    ]
    
    log_file_path = user_dir / "web_server.log"
    try:
        user_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_file_path.open("a", encoding="utf-8")
    except Exception as e:
        print(f"Fehler: Log-Datei konnte nicht geöffnet werden: {e}", file=sys.stderr)
        return 1

    try:
        if sys.platform == "win32" or sys.platform == "cygwin":
            DETACHED_PROCESS = 0x00000008
            p = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                close_fds=True,
                creationflags=DETACHED_PROCESS,
            )
        else:
            p = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                close_fds=True,
                start_new_session=True,
            )
        log_file.close()
        
        # Write PID
        pid_file.write_text(str(p.pid), encoding="utf-8")
        print(f"Webserver im Hintergrund gestartet (PID {p.pid}, http://{config.web.host}:{config.web.port})")
    except Exception as e:
        print(f"Fehler beim Starten des Webservers: {e}", file=sys.stderr)
        return 1

    # Trigger scheduler registration/checks in the background
    try:
        python_bin = Path(sys.executable)
        project_root = config_path.parent
        # Try to register the daily run task using the hour/minute configured
        scheduler.register_daily_run(
            python_bin=python_bin,
            project_dir=project_root,
            hour=config.schedule.hour,
            minute=config.schedule.minute,
            interactive=False
        )
        print("Scheduler registriert / überprüft.")
    except Exception as e:
        print(f"Hinweis: Scheduler konnte nicht automatisch registriert werden: {e}", file=sys.stderr)

    return 0


def stop_daemon(config_path: Path) -> int:
    """Stops the background web server."""
    user_dir = get_user_dir()
    pid_file = user_dir / "web_server.pid"
    
    if not pid_file.exists():
        print("Webserver ist nicht aktiv (keine PID-Datei gefunden).")
        return 0

    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except ValueError:
        print("Ungültige PID-Datei. Lösche sie...")
        pid_file.unlink(missing_ok=True)
        return 0

    if not is_pid_running(pid):
        print(f"Webserver (PID {pid}) läuft nicht. Lösche veraltete PID-Datei...")
        pid_file.unlink(missing_ok=True)
        return 0

    print(f"Beende Webserver (PID {pid})...")
    success = terminate_pid(pid)
    pid_file.unlink(missing_ok=True)
    
    if success:
        print("Webserver erfolgreich gestoppt.")
        return 0
    else:
        print("Fehler: Webserver konnte nicht gestoppt werden.", file=sys.stderr)
        return 1


def status_daemon(config_path: Path) -> int:
    """Outputs status report and returns 0 if all green (running/installed) or 1 otherwise."""
    config = load_config(config_path)
    user_dir = get_user_dir()
    pid_file = user_dir / "web_server.pid"
    
    # 1. Web server check
    web_active = False
    web_pid = None
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            if is_pid_running(pid):
                web_active = True
                web_pid = pid
        except ValueError:
            pass

    # Also double check with socket connection if PID check says active
    if web_active:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(("127.0.0.1", config.web.port))
            s.close()
        except Exception:
            web_active = False

    # 2. Scheduler check
    sched_installed, _ = scheduler.check_daily_run_status()

    # 3. Last generation time and result
    last_run_file = user_dir / "last_run.json"
    last_run_str = "Keine Daten vorhanden"
    if last_run_file.exists():
        try:
            data = json.loads(last_run_file.read_text(encoding="utf-8"))
            ts = datetime.fromisoformat(data["timestamp"])
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            status = "Erfolgreich" if data["success"] else f"Fehlgeschlagen ({data['error']})"
            last_run_str = f"{ts_str} ({status})"
        except Exception:
            pass
    else:
        # Fallback: check episodes folder
        episodes_dir = config.delivery.output_dir / "episodes"
        if episodes_dir.is_dir():
            audio_files = sorted(episodes_dir.glob("*.m4b"))
            if audio_files:
                latest = audio_files[-1]
                mtime = datetime.fromtimestamp(latest.stat().st_mtime)
                last_run_str = f"{mtime.strftime('%Y-%m-%d %H:%M:%S')} (Erfolgreich - Audiodatei vorhanden)"

    # 4. Next scheduled run
    now = datetime.now()
    sched_time = dt_time(config.schedule.hour, config.schedule.minute)
    sched_today = datetime.combine(now.date(), sched_time)
    if sched_today > now:
        next_run = sched_today
    else:
        next_run = sched_today + timedelta(days=1)
    next_run_str = next_run.strftime("%Y-%m-%d %H:%M:%S")

    # Print status report
    print("======================================================================")
    print("                      Briefly System-Status")
    print("======================================================================")
    web_status_text = f"Aktiv (PID {web_pid}, http://{config.web.host}:{config.web.port})" if web_active else "Inaktiv"
    print(f"Webserver:      {web_status_text}")
    print(f"Scheduler:      {'Installiert' if sched_installed else 'Nicht installiert'}")
    print(f"Letzter Lauf:   {last_run_str}")
    print(f"Nächster Lauf:  {next_run_str}")
    print("======================================================================")

    # Return exit code: 0 if web server is active and scheduler is installed
    return 0 if (web_active and sched_installed) else 1


def restart_daemon(config_path: Path) -> int:
    """Restarts the background web server."""
    print("Starte Briefly-Dienste neu...")
    stop_daemon(config_path)
    time.sleep(0.5)
    return start_daemon(config_path)
