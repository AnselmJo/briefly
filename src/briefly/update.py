from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import briefly
from briefly.config import load_config, ConfigValidationError

logger = logging.getLogger(__name__)


def get_repo_dir() -> Path:
    p = Path(briefly.__file__).resolve().parent.parent.parent
    if (p / ".git").is_dir():
        return p
    p = Path.cwd()
    if (p / ".git").is_dir():
        return p
    raise RuntimeError("Repository-Verzeichnis konnte nicht bestimmt werden. Bitte führe den Befehl im Briefly-Ordner aus.")


def has_uncommitted_changes(repo_dir: Path) -> bool:
    res = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True, check=True)
    # Ignore untracked files (which start with '??')
    lines = [line for line in res.stdout.splitlines() if line.strip() and not line.startswith("??")]
    return len(lines) > 0


def run_update(config_path: Path) -> int:
    try:
        repo_dir = get_repo_dir()
    except RuntimeError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1

    if has_uncommitted_changes(repo_dir):
        print("❌ Update abgebrochen: Es gibt uncommittete Änderungen im Repository.", file=sys.stderr)
        print("Bitte committe deine Änderungen oder verwerfe sie ('git stash'), bevor du ein Update durchführst.", file=sys.stderr)
        return 1

    try:
        # Get old commit hash
        old_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()
        
        # Git pull
        print("Führe 'git pull' aus...")
        subprocess.run(["git", "pull"], cwd=repo_dir, check=True)
        
        # Get new commit hash
        new_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Fehler bei Git-Operation: {e}", file=sys.stderr)
        return 1

    if old_commit == new_commit:
        print("Briefly ist bereits auf dem neuesten Stand.")
        return 0

    # Print changes
    try:
        log_res = subprocess.run(
            ["git", "log", f"{old_commit}..{new_commit}", "--oneline"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True
        )
        print("\nÄnderungen seit dem letzten Update:")
        print(log_res.stdout)
    except Exception as e:
        logger.warning("Fehler beim Abrufen der Git-Historie: %s", e)

    # Check if pyproject.toml changed and re-run pip install -e .
    try:
        diff_res = subprocess.run(
            ["git", "diff", "--name-only", old_commit, new_commit],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True
        )
        changed_files = diff_res.stdout.splitlines()
        if "pyproject.toml" in changed_files:
            print("Abhängigkeiten haben sich geändert. Installiere neu (pip install)...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], cwd=repo_dir, check=True)
    except Exception as e:
        print(f"Warnung: Fehler beim Aktualisieren der Abhängigkeiten: {e}", file=sys.stderr)

    # Re-run config validation (warn, don't crash)
    try:
        load_config(config_path)
        print("Konfiguration erfolgreich validiert.")
    except ConfigValidationError as e:
        print(f"\n⚠️  WARNUNG: Neue oder ungültige Konfigurationswerte in '{config_path}' erkannt:", file=sys.stderr)
        print(f"  Schlüssel:       {e.key}", file=sys.stderr)
        print(f"  Ungültiger Wert: {e.invalid_value}", file=sys.stderr)
        print(f"  Fehlermeldung:   {e.msg}", file=sys.stderr)
        print(f"  Behebung:        {e.fix}", file=sys.stderr)
        print("Das Update wird fortgesetzt, aber bitte passe deine config.yaml an.\n", file=sys.stderr)
    except Exception as e:
        print(f"⚠️  WARNUNG: Fehler beim Laden/Validieren der Konfiguration: {e}", file=sys.stderr)

    # Restart background service if running
    try:
        from briefly.daemon import is_pid_running, stop_daemon, start_daemon
        from briefly.config import get_user_dir
        
        user_dir = get_user_dir()
        pid_file = user_dir / "web_server.pid"
        was_running = False
        
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text(encoding="utf-8").strip())
                if is_pid_running(pid):
                    was_running = True
            except Exception:
                pass

        if was_running:
            print("Neustart des Hintergrund-Webservers...")
            stop_daemon(config_path)
            start_daemon(config_path)
    except Exception as e:
        print(f"Warnung: Fehler beim Neustart des Hintergrunddienstes: {e}", file=sys.stderr)

    print("\n🎉 Update erfolgreich abgeschlossen!")
    return 0
