#!/bin/bash
set -e

DRY_RUN=false
for arg in "$@"; do
  if [ "$arg" = "--dry-run" ] || [ "$arg" = "-d" ]; then
    DRY_RUN=true
  fi
done

run_cmd() {
  if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Would run: $*"
  else
    echo "Executing: $*"
    "$@"
  fi
}

echo "=== Briefly Installer ==="
if [ "$DRY_RUN" = true ]; then
  echo "Running in DRY RUN mode. No changes will be made to your system."
fi

# 1. Check for Homebrew
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is missing. Installing Homebrew..."
  run_cmd /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Load homebrew for the current session if just installed
  if [ -f /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [ -f /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
else
  echo "Homebrew is already installed."
fi

# 2. Check and install system packages
pkgs_to_install=()
if ! command -v python3 >/dev/null 2>&1; then
  pkgs_to_install+=("python")
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  pkgs_to_install+=("ffmpeg")
fi
if ! command -v ollama >/dev/null 2>&1; then
  pkgs_to_install+=("ollama")
fi
if ! command -v git >/dev/null 2>&1; then
  pkgs_to_install+=("git")
fi

if [ ${#pkgs_to_install[@]} -gt 0 ]; then
  echo "Installing missing packages: ${pkgs_to_install[*]}"
  for pkg in "${pkgs_to_install[@]}"; do
    run_cmd brew install "$pkg"
  done
else
  echo "All system packages (Python, FFmpeg, Ollama, Git) are already present."
fi

# 3. Determine project folder
if [ -f "src/briefly/__init__.py" ]; then
  PROJECT_DIR="$(pwd)"
  echo "Running from an existing checkout at $PROJECT_DIR."
else
  PROJECT_DIR="$HOME/Developer/briefly"
  if [ ! -d "$PROJECT_DIR" ]; then
    echo "Cloning Briefly to $PROJECT_DIR..."
    run_cmd mkdir -p "$HOME/Developer"
    run_cmd git clone https://github.com/AnselmJo/briefly.git "$PROJECT_DIR"
  else
    echo "Using existing repository checkout at $PROJECT_DIR."
  fi
fi

# 4. Create virtual environment
if [ ! -d "$PROJECT_DIR/.venv" ]; then
  echo "Creating virtual environment..."
  run_cmd python3 -m venv "$PROJECT_DIR/.venv"
else
  echo "Virtual environment already exists."
fi

# 5. Install Briefly in editable mode
echo "Installing Briefly dependencies..."
if [ "$DRY_RUN" = true ]; then
  run_cmd "$PROJECT_DIR/.venv/bin/pip" install -e .
else
  cd "$PROJECT_DIR"
  "$PROJECT_DIR/.venv/bin/pip" install -e .
fi

# 6. Run Briefly installer assistant
echo "Running setup assistant..."
if [ "$DRY_RUN" = true ]; then
  run_cmd "$PROJECT_DIR/.venv/bin/briefly" install
else
  "$PROJECT_DIR/.venv/bin/briefly" install
fi

echo "=== Briefly Setup Completed successfully ==="
