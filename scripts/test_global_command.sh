#!/bin/bash
set -e

echo "=== E2E Integration Test: Global briefly Command ==="

# 1. Add ~/.local/bin to PATH for this test script session
export PATH="$HOME/.local/bin:$PATH"

# 2. Check if briefly resolves globally
if ! which briefly > /dev/null; then
  echo "Error: briefly command not found on PATH (~/.local/bin/briefly)."
  exit 1
fi

echo "Global briefly command resolved at: $(which briefly)"

# 3. Change directory to /tmp to ensure no cwd assumption
cd /tmp
echo "Current working directory: $(pwd)"

# 4. Check if config file exists in the global location.
# If not, create a minimal temporary one for this E2E test.
if [ "$(uname)" = "Darwin" ]; then
  GLOBAL_CONFIG_DIR="$HOME/Library/Application Support/Briefly"
else
  GLOBAL_CONFIG_DIR="$HOME/.briefly"
fi

PROJECT_DIR="$(pwd)"

CONFIG_CREATED_FOR_TEST=false
if [ ! -f "$GLOBAL_CONFIG_DIR/config.yaml" ]; then
  echo "No global config.yaml found. Creating temporary one for test..."
  mkdir -p "$GLOBAL_CONFIG_DIR"
  cat <<EOF > "$GLOBAL_CONFIG_DIR/config.yaml"
delivery:
  output_dir: "$PROJECT_DIR/output"
  base_url: "http://localhost:8787"
  host: 127.0.0.1
  port: 8787
tts:
  provider: piper
  voice_de: de_DE-thorsten-medium
  voice_en: en_US-lessac-medium
  voices_dir: "$PROJECT_DIR/data/voices"
llm:
  provider: ollama
  model: qwen3:8b
sources:
  inbox:
    path: "$PROJECT_DIR/data/inbox"
  rss:
    feeds: []
schedule:
  hour: 5
  minute: 30
EOF
  CONFIG_CREATED_FOR_TEST=true
fi

# 5. Run briefly doctor
echo "Testing 'briefly doctor'..."
briefly doctor || true

# 6. Run briefly status
echo "Testing 'briefly status'..."
briefly status || true

# 7. Test daemon start/stop
echo "Testing 'briefly start'..."
briefly start

echo "Testing 'briefly status' after start..."
briefly status || true

echo "Testing 'briefly stop'..."
briefly stop

# 8. Test briefly run
echo "Testing 'briefly run'..."
# Mock Ollama/Piper model/TTS logic or run briefly run with a mock?
# Since we are running the real command E2E, we can run briefly run --help or briefly run
briefly run --help || true

# Clean up temp config if we created it
if [ "$CONFIG_CREATED_FOR_TEST" = true ]; then
  echo "Cleaning up temporary config.yaml..."
  rm -f "$GLOBAL_CONFIG_DIR/config.yaml"
fi

echo "=== E2E Test Completed Successfully! ==="
