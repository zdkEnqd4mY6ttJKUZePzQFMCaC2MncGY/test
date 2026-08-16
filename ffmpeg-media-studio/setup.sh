#!/usr/bin/env bash
# ==============================================================================
# OmniMedia Studio - Ubuntu Setup & Launcher Script
# ==============================================================================

set -e

echo "======================================================"
echo "🎬 OmniMedia Studio - Ubuntu Installer & Launcher"
echo "======================================================"

# 1. Check for sudo / root privileges for apt
if [ "$EUID" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
else
    SUDO=""
fi

echo "📦 1/4 Updating system packages and installing FFmpeg..."
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq ffmpeg python3 python3-pip python3-venv curl jq

# 2. Setup Virtual Environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🐍 2/4 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

# 3. Install Python Dependencies & update yt-dlp
echo "⬇️ 3/4 Installing Python packages and updating yt-dlp to latest version..."
pip install --upgrade pip setuptools wheel --quiet
pip install -r requirements.txt --quiet
pip install --upgrade yt-dlp --quiet

# 4. Prepare data directories
mkdir -p data/uploads data/outputs data/temp

# 5. Launch Service
PORT=${PORT:-7860}
HOST=${HOST:-0.0.0.0}

echo "======================================================"
echo "🚀 4/4 Starting OmniMedia Studio Server..."
echo "📍 Access Web UI at: http://localhost:$PORT"
echo "======================================================"

export OMNIMEDIA_DATA_DIR="$SCRIPT_DIR/data"
export PORT="$PORT"
export HOST="$HOST"

python3 app.py
