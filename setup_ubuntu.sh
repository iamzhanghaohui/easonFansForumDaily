#!/usr/bin/env bash
set -euo pipefail

# One-shot setup script for Ubuntu server/local machine.
# It installs system packages, uv, Python 3.10 venv, and Python deps.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "==> [1/5] Installing system packages..."
sudo apt-get update
sudo apt-get install -y \
  curl \
  unzip \
  ca-certificates \
  tesseract-ocr \
  chromium-browser \
  chromium-chromedriver

echo "==> [2/5] Installing uv (if missing)..."
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Ensure uv is available in this shell too
if [ -f "$HOME/.cargo/env" ]; then
  # shellcheck disable=SC1090
  source "$HOME/.cargo/env"
fi
export PATH="$HOME/.local/bin:$PATH"

echo "==> [3/5] Installing Python 3.10 with uv..."
uv python install 3.10
uv python pin 3.10

echo "==> [4/5] Creating virtualenv and installing requirements..."
uv venv --python 3.10 .venv
uv pip install --python .venv/bin/python -r requirements.txt

echo "==> [5/5] Verifying runtime..."
uv run python --version
uv run python -c "import selenium, bs4, pytesseract, openai; print('python_deps_ok')"
which chromium-browser || true
which chromedriver || true

echo
echo "Setup done."
echo "Next steps:"
echo "  1) Fill config.json"
echo "  2) Run: uv run python dailyMission.py --local --headless"
